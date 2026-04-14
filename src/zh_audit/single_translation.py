from __future__ import absolute_import

from collections import OrderedDict
from datetime import datetime

from zh_audit.candidate_validation import (
    MAX_GENERATION_ATTEMPTS_PER_ITEM,
    build_attempt_history_entry,
    build_retry_context,
    build_review_retry_context,
    build_validation_retry_context,
    contains_locked_terms,
    exhausted_validation_message,
    is_chinese_explanation_text,
    normalize_english_punctuation,
    normalize_locked_term_grammar_case,
    normalize_review_result,
    retry_context_preview,
    sanitize_candidate_text,
    structured_retry_prompt,
    validate_candidate_text,
    validation_message,
)
from zh_audit.model_execution import resolve_model_execution_strategy
from zh_audit.model_client import describe_retryable_model_response_error, model_response_debug_payload
from zh_audit.po_rst_protection import (
    build_slot_translation_payload,
    compose_protected_text,
    protect_rst_text,
    validate_protected_candidate,
)
from zh_audit.terminology_xlsx import exact_terminology_translation, match_locked_terms, normalize_terminology_catalog
from zh_audit.utils import contains_han, decode_unicode_escapes


def translate_single_text(
    source_text,
    glossary,
    model_config,
    plain_model_runner,
    plain_reviewer_runner=None,
    rst_model_runner=None,
    rst_reviewer_runner=None,
):
    source_value = _display_text(source_text).strip()
    if not source_value:
        raise ValueError("请输入待翻译中文。")

    glossary_catalog = normalize_terminology_catalog(glossary)
    protected_source = protect_rst_text(source_value)
    has_rst_markup = (not protected_source.get("supported", True)) or any(
        slot.get("type") != "text" for slot in protected_source.get("slots", [])
    )

    if not contains_han(source_value):
        mode = "rst" if has_rst_markup else "plain"
        return _build_result(
            status="done",
            translated_text=source_value,
            reason="原文不含中文，无需翻译。",
            mode=mode,
            validation_state="passed",
            validation_message="",
            locked_terms=[],
            warnings=[],
        )

    if has_rst_markup:
        if not protected_source.get("supported", False):
            raise ValueError(protected_source.get("reason", "包含暂不支持的 rst 语法。"))
        if rst_model_runner is None:
            raise ValueError("RST 翻译服务未配置。")
        return _translate_rst_text(
            source_text=source_value,
            glossary_catalog=glossary_catalog,
            protected_source=protected_source,
            model_config=model_config,
            model_runner=rst_model_runner,
            reviewer_runner=rst_reviewer_runner,
        )

    if plain_model_runner is None:
        raise ValueError("单条翻译服务未配置。")
    return _translate_plain_text(
        source_text=source_value,
        glossary_map=OrderedDict(glossary_catalog.non_frontend_glossary),
        model_config=model_config,
        model_runner=plain_model_runner,
        reviewer_runner=plain_reviewer_runner,
    )


def _translate_plain_text(source_text, glossary_map, model_config, model_runner, reviewer_runner=None):
    execution_policy = resolve_model_execution_strategy(model_config)
    exact_translation = exact_terminology_translation(source_text, glossary_map)
    locked_terms = match_locked_terms(source_text, glossary_map)
    normalized_exact_translation = normalize_locked_term_grammar_case(
        normalize_english_punctuation(exact_translation),
        locked_terms,
    )
    if exact_translation:
        return _build_result(
            status="done",
            translated_text=sanitize_candidate_text(normalized_exact_translation),
            reason="整句命中术语词典。",
            mode="plain",
            validation_state="passed",
            validation_message="",
            locked_terms=locked_terms,
            warnings=[],
        )

    return _build_plain_candidate_with_guardrails(
        source_text=source_text,
        locked_terms=locked_terms,
        model_config=model_config,
        model_runner=model_runner,
        reviewer_runner=reviewer_runner if execution_policy["enable_reviewer"] else None,
        max_generation_attempts=execution_policy["max_generation_attempts"],
    )


def _translate_rst_text(source_text, glossary_catalog, protected_source, model_config, model_runner, reviewer_runner=None):
    execution_policy = resolve_model_execution_strategy(model_config)
    protected_payload = _attach_slot_terminology(
        protected_source,
        OrderedDict(glossary_catalog.non_frontend_glossary),
        OrderedDict(glossary_catalog.frontend_glossary),
    )
    locked_terms = match_locked_terms(source_text, glossary_catalog.non_frontend_glossary)
    exact_translation = ""
    slots = protected_payload.get("slots", [])
    if len(slots) == 1 and slots[0].get("type") == "text":
        exact_translation = exact_terminology_translation(source_text, glossary_catalog.non_frontend_glossary)
    normalized_exact_translation = normalize_locked_term_grammar_case(
        normalize_english_punctuation(exact_translation),
        locked_terms,
    )
    if exact_translation:
        return _build_result(
            status="done",
            translated_text=sanitize_candidate_text(normalized_exact_translation),
            reason="整句命中术语词典。",
            mode="rst",
            validation_state="passed",
            validation_message="",
            locked_terms=locked_terms,
            warnings=[],
        )

    return _build_rst_candidate_with_guardrails(
        source_text=source_text,
        protected_source=protected_payload,
        locked_terms=locked_terms,
        model_config=model_config,
        model_runner=model_runner,
        reviewer_runner=reviewer_runner if execution_policy["enable_reviewer"] else None,
        max_generation_attempts=execution_policy["max_generation_attempts"],
    )


def _build_plain_candidate_with_guardrails(
    source_text,
    locked_terms,
    model_config,
    model_runner,
    reviewer_runner=None,
    max_generation_attempts=MAX_GENERATION_ATTEMPTS_PER_ITEM,
):
    generation_attempts_used = 0
    retry_context = {}
    last_result = {
        "translated_text": "",
        "reason": "",
        "warnings": [],
        "validation_issue": "校验未通过",
        "locked_terms": [dict(term) for term in locked_terms],
    }

    while generation_attempts_used < max_generation_attempts:
        attempt_number = generation_attempts_used + 1
        try:
            raw_result = model_runner(
                source_text=source_text,
                target_text="",
                locked_terms=locked_terms,
                model_config=model_config,
                extra_prompt=structured_retry_prompt("", retry_context, attempt_number),
                target_missing=True,
            )
        except Exception as exc:
            generation_attempts_used += 1
            retry_issue = describe_retryable_model_response_error(exc, phase="模型")
            if not retry_issue:
                raise
            debug_payload = model_response_debug_payload(exc)
            extracted_candidate = sanitize_candidate_text(debug_payload.get("extracted_candidate_text", ""))
            extracted_reason = _display_text(debug_payload.get("extracted_reason", "")).strip()
            retry_context = build_retry_context(
                phase="model_format",
                issue_code="model_format_invalid",
                issue_message=retry_issue,
                previous_candidate=extracted_candidate,
                source_text=source_text,
                locked_terms=locked_terms,
                candidate_text=extracted_candidate,
            )
            last_result = {
                "translated_text": extracted_candidate,
                "reason": extracted_reason,
                "warnings": [],
                "validation_issue": retry_issue,
                "locked_terms": [dict(term) for term in locked_terms],
                "retry_context_preview": retry_context_preview(retry_context),
            }
            continue

        generation_attempts_used += 1
        normalized = _normalize_plain_model_result(source_text, raw_result, locked_terms)
        candidate_text = normalized["translated_text"]
        validation_issue = validate_candidate_text(
            source_text,
            candidate_text,
            raw_candidate_text=raw_result.get("candidate_translation", candidate_text),
            locked_terms=locked_terms,
            enforce_placeholders=True,
        )
        if validation_issue:
            retry_context = build_validation_retry_context(
                source_text,
                candidate_text,
                locked_terms,
                validation_issue,
            )
            last_result = {
                "translated_text": candidate_text,
                "reason": normalized["reason"],
                "warnings": [],
                "validation_issue": validation_issue,
                "locked_terms": [dict(term) for term in locked_terms],
                "retry_context_preview": retry_context_preview(retry_context),
            }
            continue

        warning_messages = []
        if reviewer_runner is not None:
            try:
                review_result = reviewer_runner(
                    source_text=source_text,
                    candidate_text=candidate_text,
                    locked_terms=locked_terms,
                    model_config=model_config,
                    target_missing=True,
                    extra_prompt="",
                )
            except Exception as exc:
                retry_issue = describe_retryable_model_response_error(exc, phase="AI复核")
                if not retry_issue:
                    raise
                debug_payload = model_response_debug_payload(exc)
                retry_context = build_retry_context(
                    phase="model_format",
                    issue_code="review_model_format_invalid",
                    issue_message=retry_issue,
                    previous_candidate=candidate_text,
                    source_text=source_text,
                    locked_terms=locked_terms,
                    candidate_text=candidate_text,
                )
                last_result = {
                    "translated_text": candidate_text,
                    "reason": _display_text(debug_payload.get("extracted_reason", "")).strip() or normalized["reason"],
                    "warnings": [],
                    "validation_issue": retry_issue,
                    "locked_terms": [dict(term) for term in locked_terms],
                    "retry_context_preview": retry_context_preview(retry_context),
                }
                continue

            reviewed = normalize_review_result(
                review_result,
                source_text=source_text,
                candidate_text=candidate_text,
                locked_terms=locked_terms,
            )
            warning_messages = list(reviewed.get("warnings", []))
            if reviewed["decision"] != "pass":
                retry_issue = reviewed["issues"][0]
                retry_context = build_review_retry_context(
                    source_text,
                    candidate_text,
                    locked_terms,
                    (reviewed.get("issue_details") or [{}])[0],
                    reviewed.get("warning_details", []),
                )
                last_result = {
                    "translated_text": candidate_text,
                    "reason": normalized["reason"],
                    "warnings": warning_messages,
                    "validation_issue": retry_issue,
                    "locked_terms": [dict(term) for term in locked_terms],
                    "retry_context_preview": retry_context_preview(retry_context),
                }
                continue

        return _build_result(
            status="done",
            translated_text=candidate_text,
            reason=normalized["reason"],
            mode="plain",
            validation_state="passed",
            validation_message="",
            locked_terms=locked_terms,
            warnings=warning_messages,
        )

    failure_issue = last_result.get("validation_issue") or "校验未通过"
    return _build_result(
        status="done",
        translated_text=last_result.get("translated_text", ""),
        reason=last_result.get("reason", ""),
        mode="plain",
        validation_state="failed",
        validation_message=exhausted_validation_message(
            failure_issue,
            generation_attempts_used or max_generation_attempts,
        ),
        locked_terms=last_result.get("locked_terms", locked_terms),
        warnings=last_result.get("warnings", []),
    )


def _build_rst_candidate_with_guardrails(
    source_text,
    protected_source,
    locked_terms,
    model_config,
    model_runner,
    reviewer_runner=None,
    max_generation_attempts=MAX_GENERATION_ATTEMPTS_PER_ITEM,
):
    generation_attempts_used = 0
    retry_context = {}
    last_result = {
        "translated_text": "",
        "reason": "",
        "warnings": [],
        "validation_issue": "校验未通过",
        "locked_terms": [dict(term) for term in locked_terms],
        "active_frontend_terms": [],
        "frontend_glossary_enabled": False,
        "frontend_ui_slots": [],
    }

    while generation_attempts_used < max_generation_attempts:
        attempt_number = generation_attempts_used + 1
        try:
            raw_result = model_runner(
                source_text=source_text,
                target_text="",
                protected_source=protected_source,
                locked_terms=locked_terms,
                model_config=model_config,
                extra_prompt=structured_retry_prompt("", retry_context, attempt_number),
                target_missing=True,
            )
        except Exception as exc:
            generation_attempts_used += 1
            retry_issue = describe_retryable_model_response_error(exc, phase="模型")
            if not retry_issue:
                raise
            debug_payload = model_response_debug_payload(exc)
            extracted_reason = _display_text(debug_payload.get("extracted_reason", "")).strip()
            retry_context = build_retry_context(
                phase="model_format",
                issue_code="model_format_invalid",
                issue_message=retry_issue,
                previous_candidate="",
                source_text=source_text,
                locked_terms=locked_terms,
                candidate_text="",
            )
            last_result = {
                "translated_text": "",
                "reason": extracted_reason,
                "warnings": [],
                "validation_issue": retry_issue,
                "locked_terms": [dict(term) for term in locked_terms],
                "active_frontend_terms": [],
                "frontend_glossary_enabled": False,
                "frontend_ui_slots": [],
                "retry_context_preview": retry_context_preview(retry_context),
            }
            continue

        generation_attempts_used += 1
        normalized = _normalize_rst_model_result(
            source_text=source_text,
            protected_source=protected_source,
            locked_terms=locked_terms,
            result=raw_result,
        )
        candidate_text = normalized["translated_text"]
        validation_issue = _validate_rst_candidate(
            source_text=source_text,
            candidate_text=candidate_text,
            protected_source=protected_source,
            locked_terms=normalized["locked_terms"],
        )
        if validation_issue:
            retry_context = build_validation_retry_context(
                source_text,
                candidate_text,
                normalized["locked_terms"],
                validation_issue,
            )
            last_result = {
                "translated_text": candidate_text,
                "reason": normalized["reason"],
                "warnings": [],
                "validation_issue": validation_issue,
                "locked_terms": [dict(term) for term in normalized["locked_terms"]],
                "active_frontend_terms": [dict(term) for term in normalized["active_frontend_terms"]],
                "frontend_glossary_enabled": bool(normalized["frontend_glossary_enabled"]),
                "frontend_ui_slots": list(normalized["frontend_ui_slots"]),
                "retry_context_preview": retry_context_preview(retry_context),
            }
            continue

        warning_messages = []
        if reviewer_runner is not None:
            try:
                review_result = reviewer_runner(
                    source_text=source_text,
                    candidate_text=candidate_text,
                    protected_source=_review_protected_source(
                        protected_source,
                        normalized["frontend_glossary_enabled"],
                        normalized["frontend_ui_slots"],
                        normalized["active_frontend_terms"],
                    ),
                    locked_terms=normalized["locked_terms"],
                    model_config=model_config,
                    target_missing=True,
                    extra_prompt="",
                )
            except Exception as exc:
                retry_issue = describe_retryable_model_response_error(exc, phase="AI复核")
                if not retry_issue:
                    raise
                debug_payload = model_response_debug_payload(exc)
                retry_context = build_retry_context(
                    phase="model_format",
                    issue_code="review_model_format_invalid",
                    issue_message=retry_issue,
                    previous_candidate=candidate_text,
                    source_text=source_text,
                    locked_terms=normalized["locked_terms"],
                    candidate_text=candidate_text,
                )
                last_result = {
                    "translated_text": candidate_text,
                    "reason": _display_text(debug_payload.get("extracted_reason", "")).strip() or normalized["reason"],
                    "warnings": [],
                    "validation_issue": retry_issue,
                    "locked_terms": [dict(term) for term in normalized["locked_terms"]],
                    "active_frontend_terms": [dict(term) for term in normalized["active_frontend_terms"]],
                    "frontend_glossary_enabled": bool(normalized["frontend_glossary_enabled"]),
                    "frontend_ui_slots": list(normalized["frontend_ui_slots"]),
                    "retry_context_preview": retry_context_preview(retry_context),
                }
                continue

            reviewed = normalize_review_result(
                review_result,
                source_text=source_text,
                candidate_text=candidate_text,
                locked_terms=normalized["locked_terms"],
            )
            warning_messages = list(reviewed.get("warnings", []))
            if reviewed["decision"] != "pass":
                retry_issue = reviewed["issues"][0]
                retry_context = build_review_retry_context(
                    source_text,
                    candidate_text,
                    normalized["locked_terms"],
                    (reviewed.get("issue_details") or [{}])[0],
                    reviewed.get("warning_details", []),
                )
                last_result = {
                    "translated_text": candidate_text,
                    "reason": normalized["reason"],
                    "warnings": warning_messages,
                    "validation_issue": retry_issue,
                    "locked_terms": [dict(term) for term in normalized["locked_terms"]],
                    "active_frontend_terms": [dict(term) for term in normalized["active_frontend_terms"]],
                    "frontend_glossary_enabled": bool(normalized["frontend_glossary_enabled"]),
                    "frontend_ui_slots": list(normalized["frontend_ui_slots"]),
                    "retry_context_preview": retry_context_preview(retry_context),
                }
                continue

        return _build_result(
            status="done",
            translated_text=candidate_text,
            reason=normalized["reason"],
            mode="rst",
            validation_state="passed",
            validation_message="",
            locked_terms=normalized["locked_terms"],
            warnings=warning_messages,
        )

    failure_issue = last_result.get("validation_issue") or "校验未通过"
    return _build_result(
        status="done",
        translated_text=last_result.get("translated_text", ""),
        reason=last_result.get("reason", ""),
        mode="rst",
        validation_state="failed",
        validation_message=exhausted_validation_message(
            failure_issue,
            generation_attempts_used or max_generation_attempts,
        ),
        locked_terms=last_result.get("locked_terms", locked_terms),
        warnings=last_result.get("warnings", []),
    )


def _normalize_plain_model_result(source_text, result, locked_terms):
    verdict = str(result.get("verdict", "") or "").strip().lower()
    candidate = sanitize_candidate_text(
        normalize_locked_term_grammar_case(
            normalize_english_punctuation(result.get("candidate_translation", "")),
            locked_terms,
        )
    )
    if verdict not in ("accurate", "needs_update"):
        verdict = "needs_update"
    if verdict == "accurate":
        verdict = "needs_update"
    if not candidate:
        raise ValueError("Model did not return candidate_translation for single text.")
    return {
        "verdict": verdict,
        "translated_text": candidate,
        "reason": _normalize_reason(
            result.get("reason", ""),
            fallback="建议更新为候选英文。",
        ),
        "locked_terms": [dict(term) for term in locked_terms],
    }


def _normalize_rst_model_result(source_text, protected_source, locked_terms, result):
    verdict = str(result.get("verdict", "") or "").strip().lower()
    if verdict not in ("accurate", "needs_update"):
        verdict = "needs_update"
    if verdict == "accurate":
        verdict = "needs_update"

    slot_payload = build_slot_translation_payload(result.get("slot_translations"))
    slot_translations = {
        slot_id: normalize_english_punctuation(payload.get("translation", ""))
        for slot_id, payload in slot_payload.items()
    }
    candidate = compose_protected_text(protected_source, slot_translations)
    candidate = sanitize_candidate_text(normalize_locked_term_grammar_case(candidate, locked_terms))
    if not candidate:
        raise ValueError("Model did not return candidate translation for single text RST input.")

    frontend_ui_slots = sorted(
        [
            slot_id
            for slot_id, payload in slot_payload.items()
            if payload.get("frontend_ui_context", False)
        ]
    )
    active_frontend_terms = _active_frontend_terms(protected_source, frontend_ui_slots)
    return {
        "verdict": verdict,
        "translated_text": candidate,
        "reason": _normalize_reason(result.get("reason", ""), fallback="建议更新为候选英文。"),
        "locked_terms": _merge_locked_terms(locked_terms, active_frontend_terms),
        "active_frontend_terms": active_frontend_terms,
        "frontend_glossary_enabled": bool(frontend_ui_slots),
        "frontend_ui_slots": frontend_ui_slots,
    }


def _validate_rst_candidate(source_text, candidate_text, protected_source, locked_terms):
    issue = validate_candidate_text(
        source_text,
        candidate_text,
        raw_candidate_text=candidate_text,
        locked_terms=locked_terms,
        enforce_placeholders=True,
    )
    if issue:
        return issue
    return validate_protected_candidate(protected_source, candidate_text)


def _attach_slot_terminology(protected_source, non_frontend_glossary, frontend_glossary):
    enriched = dict(protected_source or {})
    enriched_slots = []
    for slot in protected_source.get("translatable_slots", []):
        source_text = slot.get("source_text", "")
        enriched_slot = dict(slot)
        enriched_slot["non_frontend_locked_terms"] = match_locked_terms(source_text, non_frontend_glossary)
        enriched_slot["frontend_locked_terms"] = match_locked_terms(source_text, frontend_glossary)
        enriched_slots.append(enriched_slot)
    enriched["translatable_slots"] = enriched_slots
    return enriched


def _active_frontend_terms(protected_source, frontend_ui_slots):
    active = []
    active_slot_ids = set(frontend_ui_slots or [])
    for slot in protected_source.get("translatable_slots", []):
        if slot.get("slot_id") not in active_slot_ids:
            continue
        for term in slot.get("frontend_locked_terms", []):
            if not any(item["source"] == term["source"] and item["target"] == term["target"] for item in active):
                active.append({"source": term["source"], "target": term["target"]})
    return active


def _merge_locked_terms(base_terms, extra_terms):
    merged = []
    for term in list(base_terms or []) + list(extra_terms or []):
        normalized = {"source": term.get("source", ""), "target": term.get("target", "")}
        if not normalized["source"] or not normalized["target"]:
            continue
        if any(item["source"] == normalized["source"] and item["target"] == normalized["target"] for item in merged):
            continue
        merged.append(normalized)
    return merged


def _review_protected_source(protected_source, frontend_glossary_enabled, frontend_ui_slots, active_frontend_terms):
    payload = dict(protected_source or {})
    payload["frontend_glossary_enabled"] = bool(frontend_glossary_enabled)
    payload["frontend_ui_slots"] = list(frontend_ui_slots or [])
    payload["active_frontend_terms"] = [dict(term) for term in (active_frontend_terms or [])]
    return payload


def _build_result(status, translated_text, reason, mode, validation_state, validation_message, locked_terms, warnings):
    return {
        "status": str(status or "done"),
        "translated_text": sanitize_candidate_text(translated_text),
        "error": "",
        "reason": str(reason or "").strip(),
        "mode": str(mode or "plain"),
        "validation_state": str(validation_state or "passed"),
        "validation_message": str(validation_message or "").strip(),
        "locked_terms": [dict(term) for term in (locked_terms or [])],
        "warnings": [str(item or "").strip() for item in (warnings or []) if str(item or "").strip()],
        "updated_at": _timestamp(),
    }


def _display_text(value):
    return decode_unicode_escapes(str(value or ""))


def _normalize_reason(reason, fallback):
    value = _display_text(reason).strip()
    if is_chinese_explanation_text(value):
        return value
    return str(fallback or "").strip()


def _timestamp():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()
