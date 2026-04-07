from __future__ import absolute_import

import json
import threading
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from zh_audit.candidate_validation import (
    MAX_GENERATION_ATTEMPTS_PER_ITEM,
    build_attempt_history_entry,
    build_retry_context,
    build_review_retry_context,
    build_validation_retry_context,
    contains_locked_terms,
    exhausted_validation_message,
    has_matching_placeholders,
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
from zh_audit.model_client import describe_retryable_model_response_error, model_response_debug_payload
from zh_audit.po_file import load_po_document
from zh_audit.po_rst_protection import (
    build_slot_translation_payload,
    compose_protected_text,
    protect_rst_text,
    validate_protected_candidate,
)
from zh_audit.terminology_xlsx import exact_terminology_translation, match_locked_terms, normalize_terminology_catalog
from zh_audit.utils import contains_han, decode_unicode_escapes


PO_TRANSLATION_SESSION_VERSION = 2
PO_TRANSLATION_EVENT_HISTORY_LIMIT = 1000


def default_po_translation_config():
    return {
        "po_path": "",
        "auto_accept": False,
    }


class PoTranslationSession(object):
    def __init__(
        self,
        po_path,
        glossary,
        model_config,
        model_runner,
        reviewer_runner=None,
        persist_callback=None,
    ):
        self.lock = threading.RLock()
        self.po_path = str(po_path)
        self.set_glossary(glossary)
        self.model_config = dict(model_config)
        self.model_runner = model_runner
        self.reviewer_runner = reviewer_runner
        self.persist_callback = persist_callback
        self.document = load_po_document(po_path)
        self.entries = [entry for entry in self.document.entries() if not entry.is_header]
        self.items = OrderedDict()
        self.pending_ids = []
        self.recent_ids = []
        self.events = []
        self.total = len(self.entries)
        self.processed = 0
        self.pending = 0
        self.accepted = 0
        self.updated = 0
        self.filled = 0
        self.skipped = 0
        self.unsupported = 0
        self.failed = 0
        self.rejected = 0
        self.regenerated = 0
        self.current = {
            "entry_id": "",
            "references": [],
            "msgid_preview": "",
            "status": "",
        }
        self.status = "idle"
        self.message = "等待校译"
        self.error = ""
        self.started_at = ""
        self.finished_at = ""
        self.stop_requested = False
        self.next_id = 1
        self.next_index = 0

    def set_glossary(self, glossary):
        self.glossary_catalog = normalize_terminology_catalog(glossary)
        self.glossary = OrderedDict(self.glossary_catalog.non_frontend_glossary)
        self.frontend_glossary = OrderedDict(self.glossary_catalog.frontend_glossary)

    @classmethod
    def from_saved_state(
        cls,
        payload,
        glossary,
        model_config,
        model_runner,
        reviewer_runner=None,
        persist_callback=None,
    ):
        session = cls(
            po_path=Path(str(payload.get("po_path", "") or "")).expanduser(),
            glossary=glossary,
            model_config=model_config,
            model_runner=model_runner,
            reviewer_runner=reviewer_runner,
            persist_callback=persist_callback,
        )
        session._restore_saved_state(payload)
        return session

    def start(self):
        with self.lock:
            self.status = "running"
            self.message = "校译中"
            self.error = ""
            self.started_at = _timestamp()
            self.finished_at = ""
            self.stop_requested = False
            self.next_index = 0
            self._persist_locked()

    def stop(self):
        with self.lock:
            self.stop_requested = True
            if self.status == "running":
                self.message = "停止中"
            self._persist_locked()

    def resume(self):
        with self.lock:
            if not self.can_resume():
                raise ValueError("PO translation task cannot be resumed.")
            self.status = "running"
            self.message = "校译中"
            self.error = ""
            self.finished_at = ""
            self.stop_requested = False
            if self.current.get("entry_id"):
                self.current["status"] = "处理中"
            self._persist_locked()

    def can_resume(self):
        return self.status in ("interrupted", "stopped") and self.next_index < self.total

    def mark_restarted(self):
        with self.lock:
            if self.status == "running":
                self.status = "interrupted"
                self.message = "服务重启，可从上次位置继续"
                self.error = ""
                self.finished_at = _timestamp()
                if self.current.get("entry_id"):
                    self.current["status"] = "等待继续"
                self.stop_requested = False
                self._persist_locked()

    def interrupt(self, error_message):
        with self.lock:
            self.status = "interrupted"
            self.message = "校译中断"
            self.error = str(error_message)
            self.finished_at = _timestamp()
            self.stop_requested = False
            if self.current.get("entry_id"):
                self.current["status"] = "等待继续"
            self._persist_locked()

    def snapshot(self):
        with self.lock:
            pending_items = [
                self._public_item(self.items[item_id])
                for item_id in self.pending_ids
                if item_id in self.items and self.items[item_id].get("status") == "pending"
            ]
            recent_items = [self._public_item(self.items[item_id]) for item_id in self.recent_ids]
            return {
                "config": {
                    "po_path": self.po_path,
                },
                "status": {
                    "status": self.status,
                    "message": self.message,
                    "error": self.error,
                    "started_at": self.started_at,
                    "finished_at": self.finished_at,
                    "current": dict(self.current),
                    "counts": self._counts_payload(),
                },
                "pending_items": pending_items,
                "recent_items": recent_items,
                "events": list(self.events),
            }

    def save_state(self):
        with self.lock:
            return self._saved_state_locked()

    def run(self, should_auto_accept):
        while True:
            with self.lock:
                if self.stop_requested:
                    self.status = "stopped"
                    self.message = "已停止"
                    self.finished_at = _timestamp()
                    self.current = {
                        "entry_id": "",
                        "references": [],
                        "msgid_preview": "",
                        "status": "",
                    }
                    self._persist_locked()
                    return
                if self.next_index >= self.total:
                    if self.status == "running":
                        self.status = "done"
                        self.message = "校译完成"
                        self.finished_at = _timestamp()
                        self.current = {
                            "entry_id": "",
                            "references": [],
                            "msgid_preview": "",
                            "status": "",
                        }
                        self._persist_locked()
                    return
                entry = self.entries[self.next_index]
                source_text = _display_text(entry.msgid_text())
                self.current = {
                    "entry_id": entry.block_id,
                    "references": list(entry.references),
                    "msgid_preview": _preview(source_text),
                    "status": "处理中",
                }
                self._persist_locked()

            self._process_entry(entry, should_auto_accept)

            with self.lock:
                self.next_index += 1
                self.current = {
                    "entry_id": entry.block_id,
                    "references": list(entry.references),
                    "msgid_preview": _preview(source_text),
                    "status": "已处理",
                }
                self._persist_locked()

    def accept(self, item_id, candidate_text=""):
        with self.lock:
            item = self._require_pending_item(item_id)
            manual_candidate = str(candidate_text if candidate_text is not None else "")
            reason = "人工接受（跳过系统校验）" if item.get("validation_state") == "failed" else "人工接受"
            if manual_candidate.strip():
                item["candidate_text"] = self._validated_candidate_text(item, manual_candidate)
                item["raw_candidate_text"] = manual_candidate
                reason = "手动录入后接受"
            else:
                item["candidate_text"] = self._validated_candidate_text(item)
            self._apply_item(item, "accepted", reason)
            return self.snapshot()

    def reject(self, item_id):
        with self.lock:
            item = self._require_pending_item(item_id)
            item["status"] = "rejected"
            item["updated_at"] = _timestamp()
            self.pending_ids.remove(item_id)
            self.pending -= 1
            self.rejected += 1
            self._push_recent(item_id)
            self._push_event("已忽略", item, item.get("candidate_text", ""))
            self._persist_locked()
            return self.snapshot()

    def regenerate(self, item_id, extra_prompt):
        with self.lock:
            item = self._require_pending_item(item_id)
            if item_id in self.pending_ids:
                self.pending_ids.remove(item_id)
                self.pending = max(self.pending - 1, 0)
            item["status"] = "regenerating"
            item["updated_at"] = _timestamp()
            self._persist_locked()
            protected = dict(item.get("protected_source", {}))
            locked_terms = list(item.get("locked_terms", []))
            target_missing = bool(item.get("target_missing", False))
            references = list(item.get("references", []))
            entry_id = item.get("entry_id", "")
            source_text = item.get("source_text", "")
            current_target = item.get("target_text", "")

        try:
            normalized = self._build_candidate_with_guardrails(
                entry_id=entry_id,
                references=references,
                source_text=source_text,
                current_target=current_target,
                protected_source=protected,
                locked_terms=locked_terms,
                target_missing=target_missing,
                base_extra_prompt=extra_prompt,
            )
        except Exception:
            with self.lock:
                item["status"] = "pending"
                item["updated_at"] = _timestamp()
                if item_id not in self.pending_ids:
                    self.pending_ids.append(item_id)
                    self.pending += 1
                self._persist_locked()
            raise
        with self.lock:
            self._update_item_validation(item, normalized)
            item["status"] = "pending"
            item["updated_at"] = _timestamp()
            item["regeneration_prompt"] = extra_prompt
            if item_id not in self.pending_ids:
                self.pending_ids.append(item_id)
                self.pending += 1
            self.regenerated += 1
            self._push_event(self._pending_event_label(item, "已重新生成"), item, item.get("candidate_text", ""))
            self._persist_locked()
            return self.snapshot()

    def _process_entry(self, entry, should_auto_accept):
        source_text = _display_text(entry.msgid_text())
        target_text = _display_text(entry.msgstr_text())
        if not source_text.strip():
            with self.lock:
                self.processed += 1
                self.skipped += 1
                self._push_event("已跳过：msgid 为空", entry, "")
                self._persist_locked()
            return
        if entry.unsupported_reason:
            with self.lock:
                self.processed += 1
                self.unsupported += 1
                self._push_event("已跳过：结构暂不支持", entry, entry.unsupported_reason)
                self._persist_locked()
            return
        if not contains_han(source_text):
            if sanitize_candidate_text(target_text) == sanitize_candidate_text(source_text):
                with self.lock:
                    self.processed += 1
                    self.skipped += 1
                    self._push_event("已跳过：msgid 已原样回填", entry, target_text)
                    self._persist_locked()
                return
            item = self._create_item(
                entry=entry,
                source_text=source_text,
                target_text=target_text,
                protected_source=protect_rst_text(source_text),
                candidate_text=source_text,
                locked_terms=[],
                active_frontend_terms=[],
                frontend_glossary_enabled=False,
                frontend_ui_slots=[],
                reason="msgid 不含中文，已原样回填到 msgstr。",
                verdict="needs_update",
                target_missing=not target_text.strip(),
                validation_state="passed",
                validation_message="",
                validation_issue="",
                can_accept=True,
                generation_attempts_used=0,
                model_calls_used=0,
            )
            with self.lock:
                self._finalize_item(item, should_auto_accept=should_auto_accept(), force_accept=True, event_label="非中文原文回填")
            return

        protected_source = protect_rst_text(source_text)
        if not protected_source.get("supported", False):
            with self.lock:
                self.processed += 1
                self.unsupported += 1
                self._push_event("已跳过：rst 结构暂不支持", entry, protected_source.get("reason", ""))
                self._persist_locked()
            return

        protected_source = self._attach_slot_terminology(protected_source)
        locked_terms = match_locked_terms(source_text, self.glossary)
        exact_translation = ""
        slots = protected_source.get("slots", [])
        if len(slots) == 1 and slots[0].get("type") == "text":
            exact_translation = exact_terminology_translation(source_text, self.glossary)
        normalized_exact_translation = normalize_locked_term_grammar_case(
            normalize_english_punctuation(exact_translation),
            locked_terms,
        )
        if exact_translation:
            if sanitize_candidate_text(target_text) == sanitize_candidate_text(normalized_exact_translation):
                with self.lock:
                    self.processed += 1
                    self.skipped += 1
                    self._push_event("已跳过：术语已准确", entry, target_text)
                    self._persist_locked()
                return
            item = self._create_item(
                entry=entry,
                source_text=source_text,
                target_text=target_text,
                protected_source=protected_source,
                candidate_text=normalized_exact_translation,
                locked_terms=locked_terms,
                active_frontend_terms=[],
                frontend_glossary_enabled=False,
                frontend_ui_slots=[],
                reason="整句命中术语词典。",
                verdict="needs_update",
                target_missing=not target_text.strip(),
                validation_state="passed",
                validation_message="",
                validation_issue="",
                can_accept=True,
                generation_attempts_used=0,
                model_calls_used=0,
            )
            with self.lock:
                self._finalize_item(item, should_auto_accept=should_auto_accept(), force_accept=True, event_label="术语直出")
            return

        normalized = self._build_candidate_with_guardrails(
            entry_id=entry.block_id,
            references=list(entry.references),
            source_text=source_text,
            current_target=target_text,
            protected_source=protected_source,
            locked_terms=locked_terms,
            target_missing=not target_text.strip(),
            base_extra_prompt="",
        )
        if normalized["validation_state"] == "passed" and normalized["verdict"] == "accurate" and target_text.strip():
            with self.lock:
                self.processed += 1
                self.skipped += 1
                self._push_event("已跳过：译文准确，无需更新", entry, target_text)
                self._persist_locked()
            return

        item = self._create_item(
            entry=entry,
            source_text=source_text,
            target_text=target_text,
            protected_source=protected_source,
            candidate_text=normalized["candidate_text"],
            locked_terms=normalized["locked_terms"],
            active_frontend_terms=normalized["active_frontend_terms"],
            frontend_glossary_enabled=normalized["frontend_glossary_enabled"],
            frontend_ui_slots=normalized["frontend_ui_slots"],
            reason=normalized["reason"],
            verdict=normalized["verdict"],
            target_missing=not target_text.strip(),
            validation_state=normalized["validation_state"],
            validation_message=normalized["validation_message"],
            validation_issue=normalized.get("validation_issue", ""),
            can_accept=normalized["can_accept"],
            generation_attempts_used=normalized["generation_attempts_used"],
            model_calls_used=normalized["model_calls_used"],
            raw_candidate_text=normalized.get("raw_candidate_text", ""),
            raw_failure_content=normalized.get("raw_failure_content", ""),
            raw_failure_response=normalized.get("raw_failure_response", ""),
            raw_reason_text=normalized.get("raw_reason_text", ""),
            parse_error_detail=normalized.get("parse_error_detail", ""),
            failure_phase=normalized.get("failure_phase", ""),
            warnings=normalized.get("warnings", []),
            attempt_history=normalized.get("attempt_history", []),
            retry_context_preview=normalized.get("retry_context_preview", ""),
        )
        with self.lock:
            self._finalize_item(item, should_auto_accept=should_auto_accept(), force_accept=False, event_label="待审批")

    def _build_candidate_with_guardrails(
        self,
        entry_id,
        references,
        source_text,
        current_target,
        protected_source,
        locked_terms,
        target_missing,
        base_extra_prompt,
    ):
        generation_attempts_used = 0
        model_calls_used = 0
        retry_context = {}
        attempt_history = []
        last_result = {
            "verdict": "needs_update",
            "candidate_text": sanitize_candidate_text(current_target),
            "raw_candidate_text": "",
            "raw_failure_content": "",
            "raw_failure_response": "",
            "raw_reason_text": "",
            "parse_error_detail": "",
            "failure_phase": "",
            "reason": "",
            "locked_terms": [dict(term) for term in locked_terms],
            "active_frontend_terms": [],
            "frontend_glossary_enabled": False,
            "frontend_ui_slots": [],
            "validation_state": "failed",
            "validation_message": validation_message("校验未通过"),
            "validation_issue": "校验未通过",
            "can_accept": False,
            "warnings": [],
            "attempt_history": [],
            "retry_context_preview": "",
            "generation_attempts_used": 0,
            "model_calls_used": 0,
        }
        while generation_attempts_used < MAX_GENERATION_ATTEMPTS_PER_ITEM:
            attempt_number = generation_attempts_used + 1
            try:
                raw_result = self.model_runner(
                    entry_id=entry_id,
                    references=references,
                    source_text=source_text,
                    target_text=current_target,
                    protected_source=protected_source,
                    locked_terms=locked_terms,
                    model_config=self.model_config,
                    extra_prompt=self._build_retry_prompt(base_extra_prompt, retry_context, attempt_number),
                    target_missing=target_missing,
                )
            except Exception as exc:
                generation_attempts_used += 1
                model_calls_used += 1
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
                    previous_candidate=extracted_candidate or sanitize_candidate_text(current_target),
                    source_text=source_text,
                    locked_terms=locked_terms,
                    candidate_text=extracted_candidate or sanitize_candidate_text(current_target),
                )
                attempt_history.append(
                    build_attempt_history_entry(
                        generation_attempts_used,
                        extracted_candidate or sanitize_candidate_text(current_target),
                        failure_phase="模型",
                        failure_issue=retry_issue,
                        reason=extracted_reason,
                        retry_context=retry_context,
                    )
                )
                last_result = {
                    "verdict": "needs_update",
                    "candidate_text": extracted_candidate or sanitize_candidate_text(current_target),
                    "raw_candidate_text": extracted_candidate,
                    "raw_failure_content": _display_text(debug_payload.get("raw_content", "")).strip(),
                    "raw_failure_response": _display_text(debug_payload.get("raw_response", "")).strip(),
                    "raw_reason_text": extracted_reason,
                    "parse_error_detail": _display_text(debug_payload.get("parse_error_detail", "")).strip(),
                    "failure_phase": "模型",
                    "reason": extracted_reason,
                    "locked_terms": [dict(term) for term in locked_terms],
                    "active_frontend_terms": [],
                    "frontend_glossary_enabled": False,
                    "frontend_ui_slots": [],
                    "warnings": [],
                    "attempt_history": list(attempt_history),
                    "retry_context_preview": retry_context_preview(retry_context),
                    "validation_state": "failed",
                    "validation_message": validation_message(retry_issue),
                    "validation_issue": retry_issue,
                    "can_accept": False,
                    "generation_attempts_used": generation_attempts_used,
                    "model_calls_used": model_calls_used,
                }
                continue
            generation_attempts_used += 1
            model_calls_used += 1
            normalized = self._normalize_model_result(
                item={
                    "entry_id": entry_id,
                    "source_text": source_text,
                    "target_text": current_target,
                    "target_missing": target_missing,
                    "protected_source": protected_source,
                    "locked_terms": locked_terms,
                },
                result=raw_result,
                current_target=current_target,
            )
            candidate_text = normalized["candidate_text"]
            raw_candidate_text = _display_text(raw_result.get("candidate_translation", "")).strip()
            validation_issue = self._validate_candidate(
                source_text=source_text,
                candidate_text=candidate_text,
                raw_candidate_text=candidate_text,
                protected_source=protected_source,
                locked_terms=normalized["locked_terms"],
                current_target=current_target,
                verdict=normalized["verdict"],
            )
            if validation_issue:
                retry_context = build_validation_retry_context(
                    source_text,
                    candidate_text,
                    normalized["locked_terms"],
                    validation_issue,
                )
                attempt_history.append(
                    build_attempt_history_entry(
                        generation_attempts_used,
                        candidate_text,
                        failure_phase="本地校验",
                        failure_issue=validation_issue,
                        reason=normalized["reason"],
                        retry_context=retry_context,
                    )
                )
                last_result = {
                    "verdict": "needs_update",
                    "candidate_text": candidate_text,
                    "raw_candidate_text": raw_candidate_text,
                    "raw_failure_content": "",
                    "raw_failure_response": "",
                    "raw_reason_text": "",
                    "parse_error_detail": "",
                    "failure_phase": "本地校验",
                    "reason": normalized["reason"],
                    "locked_terms": [dict(term) for term in normalized["locked_terms"]],
                    "active_frontend_terms": [dict(term) for term in normalized["active_frontend_terms"]],
                    "frontend_glossary_enabled": bool(normalized["frontend_glossary_enabled"]),
                    "frontend_ui_slots": list(normalized["frontend_ui_slots"]),
                    "warnings": [],
                    "attempt_history": list(attempt_history),
                    "retry_context_preview": retry_context_preview(retry_context),
                    "validation_state": "failed",
                    "validation_message": validation_message(validation_issue),
                    "validation_issue": validation_issue,
                    "can_accept": False,
                    "generation_attempts_used": generation_attempts_used,
                    "model_calls_used": model_calls_used,
                }
                continue
            if self.reviewer_runner is not None:
                try:
                    review_result = self.reviewer_runner(
                        entry_id=entry_id,
                        references=references,
                        source_text=source_text,
                        candidate_text=candidate_text,
                        protected_source=self._review_protected_source(
                            protected_source,
                            normalized["frontend_glossary_enabled"],
                            normalized["frontend_ui_slots"],
                            normalized["active_frontend_terms"],
                        ),
                        locked_terms=normalized["locked_terms"],
                        model_config=self.model_config,
                        target_missing=target_missing,
                        extra_prompt=base_extra_prompt,
                    )
                except Exception as exc:
                    model_calls_used += 1
                    retry_issue = describe_retryable_model_response_error(exc, phase="AI复核")
                    if not retry_issue:
                        raise
                    debug_payload = model_response_debug_payload(exc)
                    extracted_reason = _display_text(debug_payload.get("extracted_reason", "")).strip()
                    retry_context = build_retry_context(
                        phase="model_format",
                        issue_code="review_model_format_invalid",
                        issue_message=retry_issue,
                        previous_candidate=candidate_text,
                        source_text=source_text,
                        locked_terms=normalized["locked_terms"],
                        candidate_text=candidate_text,
                    )
                    attempt_history.append(
                        build_attempt_history_entry(
                            generation_attempts_used,
                            candidate_text,
                            failure_phase="AI复核",
                            failure_issue=retry_issue,
                            reason=extracted_reason or normalized["reason"],
                            retry_context=retry_context,
                        )
                    )
                    last_result = {
                        "verdict": "needs_update",
                        "candidate_text": candidate_text,
                        "raw_candidate_text": raw_candidate_text,
                        "raw_failure_content": _display_text(debug_payload.get("raw_content", "")).strip(),
                        "raw_failure_response": _display_text(debug_payload.get("raw_response", "")).strip(),
                        "raw_reason_text": extracted_reason,
                        "parse_error_detail": _display_text(debug_payload.get("parse_error_detail", "")).strip(),
                        "failure_phase": "AI复核",
                        "reason": extracted_reason or normalized["reason"],
                        "locked_terms": [dict(term) for term in normalized["locked_terms"]],
                        "active_frontend_terms": [dict(term) for term in normalized["active_frontend_terms"]],
                        "frontend_glossary_enabled": bool(normalized["frontend_glossary_enabled"]),
                        "frontend_ui_slots": list(normalized["frontend_ui_slots"]),
                        "warnings": [],
                        "attempt_history": list(attempt_history),
                        "retry_context_preview": retry_context_preview(retry_context),
                        "validation_state": "failed",
                        "validation_message": validation_message(retry_issue),
                        "validation_issue": retry_issue,
                        "can_accept": False,
                        "generation_attempts_used": generation_attempts_used,
                        "model_calls_used": model_calls_used,
                    }
                    continue
                model_calls_used += 1
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
                    attempt_history.append(
                        build_attempt_history_entry(
                            generation_attempts_used,
                            candidate_text,
                            failure_phase="AI复核",
                            failure_issue=retry_issue,
                            warnings=warning_messages,
                            reason=normalized["reason"],
                            retry_context=retry_context,
                        )
                    )
                    last_result = {
                        "verdict": "needs_update",
                        "candidate_text": candidate_text,
                        "raw_candidate_text": raw_candidate_text,
                        "raw_failure_content": "",
                        "raw_failure_response": "",
                        "raw_reason_text": "",
                        "parse_error_detail": "",
                        "failure_phase": "AI复核",
                        "reason": normalized["reason"],
                        "locked_terms": [dict(term) for term in normalized["locked_terms"]],
                        "active_frontend_terms": [dict(term) for term in normalized["active_frontend_terms"]],
                        "frontend_glossary_enabled": bool(normalized["frontend_glossary_enabled"]),
                        "frontend_ui_slots": list(normalized["frontend_ui_slots"]),
                        "warnings": warning_messages,
                        "attempt_history": list(attempt_history),
                        "retry_context_preview": retry_context_preview(retry_context),
                        "validation_state": "failed",
                        "validation_message": validation_message(retry_issue),
                        "validation_issue": retry_issue,
                        "can_accept": False,
                        "generation_attempts_used": generation_attempts_used,
                        "model_calls_used": model_calls_used,
                    }
                    continue
            else:
                warning_messages = []
            attempt_history.append(
                build_attempt_history_entry(
                    generation_attempts_used,
                    candidate_text,
                    warnings=warning_messages,
                    reason=normalized["reason"],
                )
            )
            return {
                "verdict": normalized["verdict"],
                "candidate_text": candidate_text,
                "raw_candidate_text": raw_candidate_text,
                "raw_failure_content": "",
                "raw_failure_response": "",
                "raw_reason_text": "",
                "parse_error_detail": "",
                "failure_phase": "",
                "reason": normalized["reason"],
                "locked_terms": [dict(term) for term in normalized["locked_terms"]],
                "active_frontend_terms": [dict(term) for term in normalized["active_frontend_terms"]],
                "frontend_glossary_enabled": bool(normalized["frontend_glossary_enabled"]),
                "frontend_ui_slots": list(normalized["frontend_ui_slots"]),
                "warnings": warning_messages,
                "attempt_history": list(attempt_history),
                "retry_context_preview": "",
                "validation_state": "passed",
                "validation_message": "",
                "validation_issue": "",
                "can_accept": True,
                "generation_attempts_used": generation_attempts_used,
                "model_calls_used": model_calls_used,
            }
        failure_issue = last_result.get("validation_issue") or "校验未通过"
        last_result["validation_state"] = "failed"
        last_result["validation_message"] = exhausted_validation_message(
            failure_issue,
            generation_attempts_used or MAX_GENERATION_ATTEMPTS_PER_ITEM,
        )
        last_result["validation_issue"] = failure_issue
        last_result["can_accept"] = False
        last_result["generation_attempts_used"] = min(
            generation_attempts_used,
            MAX_GENERATION_ATTEMPTS_PER_ITEM,
        )
        last_result["model_calls_used"] = model_calls_used
        return last_result

    def _normalize_model_result(self, item, result, current_target):
        verdict = str(result.get("verdict", "") or "").strip().lower()
        reason = _display_text(result.get("reason", "")).strip()
        if verdict not in ("accurate", "needs_update"):
            verdict = "needs_update"
        locked_terms = [dict(term) for term in item.get("locked_terms", [])]
        target_missing = bool(item.get("target_missing", not str(current_target or "").strip()))
        protected_source = dict(item.get("protected_source", {}))
        normalized_current_target = _normalize_protected_english_candidate_text(current_target, locked_terms)
        if verdict == "accurate" and target_missing:
            verdict = "needs_update"
        if verdict == "accurate":
            if locked_terms and not contains_locked_terms(current_target, locked_terms):
                verdict = "needs_update"
                reason = "现有英文未满足术语词典要求。"
            elif normalized_current_target != sanitize_candidate_text(current_target):
                return {
                    "verdict": "needs_update",
                    "candidate_text": normalized_current_target,
                    "reason": _normalize_reason(reason, fallback="现有英文标点需要规范为英文半角标点。"),
                    "locked_terms": [dict(term) for term in locked_terms],
                    "active_frontend_terms": [],
                    "frontend_glossary_enabled": False,
                    "frontend_ui_slots": [],
                }
            else:
                return {
                    "verdict": verdict,
                    "candidate_text": sanitize_candidate_text(current_target),
                    "reason": _normalize_reason(reason, fallback="现有英文翻译准确。"),
                    "locked_terms": [dict(term) for term in locked_terms],
                    "active_frontend_terms": [],
                    "frontend_glossary_enabled": False,
                    "frontend_ui_slots": [],
                }
        slot_payload = build_slot_translation_payload(result.get("slot_translations"))
        slot_translations = {
            slot_id: normalize_english_punctuation(payload.get("translation", ""))
            for slot_id, payload in slot_payload.items()
        }
        candidate = compose_protected_text(protected_source, slot_translations)
        candidate = sanitize_candidate_text(normalize_locked_term_grammar_case(candidate, locked_terms))
        if not candidate:
            raise ValueError("Model did not return candidate translation for PO entry {}".format(item.get("entry_id", "")))
        frontend_ui_slots = sorted(
            [
                slot_id
                for slot_id, payload in slot_payload.items()
                if payload.get("frontend_ui_context", False)
            ]
        )
        active_frontend_terms = self._active_frontend_terms(protected_source, frontend_ui_slots)
        return {
            "verdict": "needs_update",
            "candidate_text": candidate,
            "reason": _normalize_reason(
                reason,
                fallback="目标英文缺失，建议补充候选英文。" if target_missing else "现有英文翻译不够准确，建议更新为候选英文。",
            ),
            "locked_terms": self._merge_locked_terms(locked_terms, active_frontend_terms),
            "active_frontend_terms": active_frontend_terms,
            "frontend_glossary_enabled": bool(frontend_ui_slots),
            "frontend_ui_slots": frontend_ui_slots,
        }

    def _validate_candidate(
        self,
        source_text,
        candidate_text,
        raw_candidate_text,
        protected_source,
        locked_terms,
        current_target,
        verdict,
    ):
        issue = validate_candidate_text(
            source_text,
            candidate_text,
            raw_candidate_text=raw_candidate_text,
            locked_terms=locked_terms,
            enforce_placeholders=True,
        )
        if issue:
            return issue
        issue = validate_protected_candidate(protected_source, candidate_text)
        if issue:
            return issue
        if verdict == "accurate" and sanitize_candidate_text(candidate_text) != sanitize_candidate_text(current_target):
            return "verdict=accurate 时候选必须等于当前 msgstr"
        return ""

    def _attach_slot_terminology(self, protected_source):
        enriched = dict(protected_source or {})
        enriched_slots = []
        for slot in protected_source.get("translatable_slots", []):
            source_text = slot.get("source_text", "")
            enriched_slot = dict(slot)
            enriched_slot["non_frontend_locked_terms"] = match_locked_terms(source_text, self.glossary)
            enriched_slot["frontend_locked_terms"] = match_locked_terms(source_text, self.frontend_glossary)
            enriched_slots.append(enriched_slot)
        enriched["translatable_slots"] = enriched_slots
        return enriched

    def _active_frontend_terms(self, protected_source, frontend_ui_slots):
        active = []
        active_slot_ids = set(frontend_ui_slots or [])
        for slot in protected_source.get("translatable_slots", []):
            slot_id = str(slot.get("slot_id", "") or "")
            if slot_id not in active_slot_ids:
                continue
            for term in slot.get("frontend_locked_terms", []):
                active.append(
                    {
                        "source": term.get("source", ""),
                        "target": term.get("target", ""),
                        "slot_id": slot_id,
                    }
                )
        return self._dedupe_terms(active)

    def _merge_locked_terms(self, base_terms, extra_terms):
        merged = [dict(term) for term in base_terms or []]
        merged.extend(dict(term) for term in extra_terms or [])
        return self._dedupe_terms(merged)

    def _dedupe_terms(self, terms):
        deduped = []
        seen = set()
        for term in terms or []:
            source = str(term.get("source", "") or "")
            target = str(term.get("target", "") or "")
            slot_id = str(term.get("slot_id", "") or "")
            key = (source, target, slot_id)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(dict(term))
        return deduped

    def _review_protected_source(self, protected_source, frontend_glossary_enabled, frontend_ui_slots, active_frontend_terms):
        payload = dict(protected_source or {})
        payload["frontend_glossary_enabled"] = bool(frontend_glossary_enabled)
        payload["frontend_ui_slots"] = list(frontend_ui_slots or [])
        payload["active_frontend_terms"] = [dict(term) for term in active_frontend_terms or []]
        return payload

    def _build_retry_prompt(self, base_extra_prompt, retry_context, attempt_number):
        return structured_retry_prompt(base_extra_prompt, retry_context, attempt_number)

    def _create_item(
        self,
        entry,
        source_text,
        target_text,
        protected_source,
        candidate_text,
        locked_terms,
        active_frontend_terms,
        frontend_glossary_enabled,
        frontend_ui_slots,
        reason,
        verdict,
        target_missing,
        validation_state,
        validation_message,
        validation_issue,
        can_accept,
        generation_attempts_used,
        model_calls_used,
        raw_candidate_text="",
        raw_failure_content="",
        raw_failure_response="",
        raw_reason_text="",
        parse_error_detail="",
        failure_phase="",
        warnings=None,
        attempt_history=None,
        retry_context_preview="",
    ):
        with self.lock:
            item_id = "po-{}".format(self.next_id)
            self.next_id += 1
            item = {
                "id": item_id,
                "entry_id": entry.block_id,
                "references": list(entry.references),
                "source_text": source_text,
                "target_text": target_text,
                "candidate_text": candidate_text,
                "raw_candidate_text": str(raw_candidate_text or ""),
                "raw_failure_content": str(raw_failure_content or ""),
                "raw_failure_response": str(raw_failure_response or ""),
                "raw_reason_text": str(raw_reason_text or ""),
                "parse_error_detail": str(parse_error_detail or ""),
                "failure_phase": str(failure_phase or ""),
                "warnings": [str(message or "").strip() for message in (warnings or []) if str(message or "").strip()],
                "attempt_history": [dict(entry) for entry in (attempt_history or [])],
                "retry_context_preview": str(retry_context_preview or ""),
                "protected_summary": protected_source.get("summary", ""),
                "protected_source": dict(protected_source),
                "locked_terms": [dict(term) for term in locked_terms],
                "active_frontend_terms": [dict(term) for term in active_frontend_terms],
                "frontend_glossary_enabled": bool(frontend_glossary_enabled),
                "frontend_ui_slots": list(frontend_ui_slots or []),
                "reason": reason,
                "verdict": verdict,
                "target_missing": bool(target_missing),
                "validation_state": str(validation_state or "passed"),
                "validation_message": str(validation_message or ""),
                "validation_issue": str(validation_issue or ""),
                "can_accept": bool(can_accept),
                "generation_attempts_used": int(generation_attempts_used or 0),
                "model_calls_used": int(model_calls_used or 0),
                "status": "pending",
                "updated_at": _timestamp(),
            }
            self.items[item_id] = item
            self._persist_locked()
            return item

    def _update_item_validation(self, item, normalized):
        item["candidate_text"] = normalized["candidate_text"]
        item["raw_candidate_text"] = str(normalized.get("raw_candidate_text", ""))
        item["raw_failure_content"] = str(normalized.get("raw_failure_content", ""))
        item["raw_failure_response"] = str(normalized.get("raw_failure_response", ""))
        item["raw_reason_text"] = str(normalized.get("raw_reason_text", ""))
        item["parse_error_detail"] = str(normalized.get("parse_error_detail", ""))
        item["failure_phase"] = str(normalized.get("failure_phase", ""))
        item["warnings"] = [str(message or "").strip() for message in normalized.get("warnings", []) if str(message or "").strip()]
        item["attempt_history"] = [dict(entry) for entry in normalized.get("attempt_history", [])]
        item["retry_context_preview"] = str(normalized.get("retry_context_preview", ""))
        item["reason"] = normalized["reason"]
        item["verdict"] = normalized["verdict"]
        item["locked_terms"] = [dict(term) for term in normalized.get("locked_terms", item.get("locked_terms", []))]
        item["active_frontend_terms"] = [dict(term) for term in normalized.get("active_frontend_terms", item.get("active_frontend_terms", []))]
        item["frontend_glossary_enabled"] = bool(normalized.get("frontend_glossary_enabled", item.get("frontend_glossary_enabled", False)))
        item["frontend_ui_slots"] = list(normalized.get("frontend_ui_slots", item.get("frontend_ui_slots", [])))
        item["validation_state"] = normalized["validation_state"]
        item["validation_message"] = normalized["validation_message"]
        item["validation_issue"] = normalized.get("validation_issue", "")
        item["can_accept"] = bool(normalized["can_accept"])
        item["generation_attempts_used"] = int(normalized.get("generation_attempts_used", item.get("generation_attempts_used", 0)) or 0)
        item["model_calls_used"] = int(normalized["model_calls_used"])

    def _finalize_item(self, item, should_auto_accept, force_accept, event_label):
        self.processed += 1
        if force_accept:
            self._apply_item(item, "accepted", event_label)
            return
        if should_auto_accept and item.get("can_accept", True):
            self._apply_item(item, "accepted", "已自动审批")
            return
        item["status"] = "pending"
        item["updated_at"] = _timestamp()
        self.pending_ids.append(item["id"])
        self.pending += 1
        if item.get("validation_state") == "failed":
            self.failed += 1
        self._push_event(self._pending_event_label(item, event_label), item, item.get("candidate_text", ""))
        self._persist_locked()

    def _pending_event_label(self, item, default_label):
        if item.get("validation_state") == "failed":
            phase = str(item.get("failure_phase", "") or "本地校验")
            if phase == "模型":
                prefix = "候选生成失败"
            elif phase == "AI复核":
                prefix = "候选通过 AI复核失败"
            else:
                prefix = "候选通过本地校验失败"
            return "{}：{}".format(prefix, item.get("validation_issue") or "请重新生成")
        return default_label

    def _apply_item(self, item, status, reason):
        target_had_value = bool(str(item.get("target_text", "") or "").strip())
        entry = self.document.find_entry(item["entry_id"])
        if entry is None:
            raise ValueError("PO entry not found in document: {}".format(item["entry_id"]))
        candidate_text = self._validated_candidate_text(item)
        entry.set_msgstr_value(candidate_text)
        self.document.write()
        item["target_text"] = entry.msgstr_text()
        item["candidate_text"] = entry.msgstr_text()
        item["status"] = status
        item["updated_at"] = _timestamp()
        item["accepted_reason"] = reason
        if item["id"] in self.pending_ids:
            self.pending_ids.remove(item["id"])
            self.pending -= 1
        self.accepted += 1
        if target_had_value:
            self.updated += 1
        else:
            self.filled += 1
        self._push_recent(item["id"])
        self._push_event(reason, item, item.get("candidate_text", ""))
        self._persist_locked()

    def _validated_candidate_text(self, item, candidate_text=None):
        value = sanitize_candidate_text(item.get("candidate_text", "") if candidate_text is None else candidate_text)
        if not value:
            raise ValueError("Candidate translation is empty for PO entry {}".format(item["entry_id"]))
        if not has_matching_placeholders(item.get("source_text", ""), value):
            raise ValueError("Candidate translation lost placeholders for PO entry {}".format(item["entry_id"]))
        if not contains_han(item.get("source_text", "")) and value == sanitize_candidate_text(item.get("source_text", "")):
            return value
        issue = validate_protected_candidate(item.get("protected_source", {}), value)
        if issue:
            raise ValueError("Candidate translation breaks RST structure for PO entry {}: {}".format(item["entry_id"], issue))
        return value

    def _push_recent(self, item_id):
        if item_id in self.recent_ids:
            self.recent_ids.remove(item_id)
        self.recent_ids.insert(0, item_id)
        del self.recent_ids[50:]

    def _push_event(self, label, item, detail):
        references = item.references if hasattr(item, "references") else item.get("references", [])
        source_text = item.msgid_text() if hasattr(item, "msgid_text") else item.get("source_text", "")
        entry_id = item.block_id if hasattr(item, "block_id") else item.get("entry_id", "")
        self.events.insert(
            0,
            {
                "at": _timestamp(),
                "label": label,
                "entry_id": entry_id,
                "references": list(references or []),
                "source_text": source_text,
                "target_text": detail,
            },
        )
        del self.events[PO_TRANSLATION_EVENT_HISTORY_LIMIT:]

    def _require_pending_item(self, item_id):
        item = self.items.get(item_id)
        if item is None:
            raise KeyError("Unknown PO translation item: {}".format(item_id))
        if item.get("status") != "pending":
            raise ValueError("PO translation item is not pending: {}".format(item_id))
        return item

    def _public_item(self, item):
        return {
            "id": item["id"],
            "entry_id": item.get("entry_id", ""),
            "references": list(item.get("references", [])),
            "source_text": item.get("source_text", ""),
            "target_text": item.get("target_text", ""),
            "candidate_text": item.get("candidate_text", ""),
            "raw_candidate_text": item.get("raw_candidate_text", ""),
            "raw_failure_content": item.get("raw_failure_content", ""),
            "raw_failure_response": item.get("raw_failure_response", ""),
            "raw_reason_text": item.get("raw_reason_text", ""),
            "parse_error_detail": item.get("parse_error_detail", ""),
            "failure_phase": item.get("failure_phase", ""),
            "warnings": list(item.get("warnings", [])),
            "attempt_history": [dict(entry) for entry in item.get("attempt_history", [])],
            "retry_context_preview": item.get("retry_context_preview", ""),
            "protected_summary": item.get("protected_summary", ""),
            "locked_terms": [dict(term) for term in item.get("locked_terms", [])],
            "active_frontend_terms": [dict(term) for term in item.get("active_frontend_terms", [])],
            "frontend_glossary_enabled": bool(item.get("frontend_glossary_enabled", False)),
            "frontend_ui_slots": list(item.get("frontend_ui_slots", [])),
            "reason": item.get("reason", ""),
            "verdict": item.get("verdict", ""),
            "status": item.get("status", ""),
            "target_missing": bool(item.get("target_missing", False)),
            "validation_state": item.get("validation_state", "passed"),
            "validation_message": item.get("validation_message", ""),
            "can_accept": bool(item.get("can_accept", True)),
            "generation_attempts_used": int(item.get("generation_attempts_used", item.get("model_calls_used", 0)) or 0),
            "model_calls_used": int(item.get("model_calls_used", 0) or 0),
            "updated_at": item.get("updated_at", ""),
        }

    def _counts_payload(self):
        return {
            "total": self.total,
            "processed": self.processed,
            "pending": self.pending,
            "accepted": self.accepted,
            "updated": self.updated,
            "filled": self.filled,
            "skipped": self.skipped,
            "unsupported": self.unsupported,
            "failed": self.failed,
            "rejected": self.rejected,
            "regenerated": self.regenerated,
        }

    def _saved_state_locked(self):
        return {
            "version": PO_TRANSLATION_SESSION_VERSION,
            "po_path": self.po_path,
            "counts": self._counts_payload(),
            "items": [dict(item) for item in self.items.values()],
            "pending_ids": list(self.pending_ids),
            "recent_ids": list(self.recent_ids),
            "events": list(self.events),
            "current": dict(self.current),
            "status": self.status,
            "message": self.message,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "stop_requested": bool(self.stop_requested),
            "next_id": self.next_id,
            "next_index": self.next_index,
        }

    def _restore_saved_state(self, payload):
        counts = dict(payload.get("counts", {}))
        self.items = OrderedDict()
        for item in payload.get("items", []):
            item_id = str(item.get("id", "") or "")
            if not item_id:
                continue
            restored = dict(item)
            restored["id"] = item_id
            restored.setdefault("validation_state", "passed")
            restored.setdefault("validation_message", "")
            restored.setdefault("validation_issue", "")
            restored.setdefault("raw_candidate_text", "")
            restored.setdefault("raw_failure_content", "")
            restored.setdefault("raw_failure_response", "")
            restored.setdefault("raw_reason_text", "")
            restored.setdefault("parse_error_detail", "")
            restored.setdefault("failure_phase", "")
            restored.setdefault("warnings", [])
            restored.setdefault("attempt_history", [])
            restored.setdefault("retry_context_preview", "")
            restored.setdefault("active_frontend_terms", [])
            restored.setdefault("frontend_glossary_enabled", False)
            restored.setdefault("frontend_ui_slots", [])
            restored.setdefault("can_accept", True)
            restored.setdefault(
                "generation_attempts_used",
                min(int(restored.get("model_calls_used", 0) or 0), MAX_GENERATION_ATTEMPTS_PER_ITEM),
            )
            restored.setdefault("model_calls_used", 0)
            self.items[item_id] = restored
        pending_ids = []
        pending_seen = set()
        for item_id in payload.get("pending_ids", []):
            item = self.items.get(item_id)
            if item is None:
                continue
            if item.get("status") == "regenerating":
                item["status"] = "pending"
                item["updated_at"] = _timestamp()
            if item.get("status") != "pending" or item_id in pending_seen:
                continue
            pending_ids.append(item_id)
            pending_seen.add(item_id)
        for item_id, item in self.items.items():
            if item.get("status") == "regenerating":
                item["status"] = "pending"
                item["updated_at"] = _timestamp()
            if item.get("status") != "pending" or item_id in pending_seen:
                continue
            pending_ids.append(item_id)
            pending_seen.add(item_id)
        self.pending_ids = pending_ids
        self.recent_ids = [item_id for item_id in payload.get("recent_ids", []) if item_id in self.items]
        self.events = list(payload.get("events", []))
        self.processed = int(counts.get("processed", 0))
        self.pending = len(self.pending_ids)
        self.accepted = int(counts.get("accepted", 0))
        self.updated = int(counts.get("updated", 0))
        self.filled = int(counts.get("filled", 0))
        self.skipped = int(counts.get("skipped", 0))
        self.unsupported = int(counts.get("unsupported", 0))
        self.failed = int(counts.get("failed", 0))
        self.rejected = int(counts.get("rejected", 0))
        self.regenerated = int(counts.get("regenerated", 0))
        self.current = dict(payload.get("current", {}))
        self.status = str(payload.get("status", "idle") or "idle")
        self.message = str(payload.get("message", "等待校译") or "等待校译")
        self.error = str(payload.get("error", "") or "")
        self.started_at = str(payload.get("started_at", "") or "")
        self.finished_at = str(payload.get("finished_at", "") or "")
        self.stop_requested = bool(payload.get("stop_requested", False))
        self.next_id = max(int(payload.get("next_id", 1)), 1)
        try:
            next_index = int(payload.get("next_index", self.processed))
        except (TypeError, ValueError):
            next_index = self.processed
        self.next_index = min(max(next_index, 0), self.total)
        if self.status == "running":
            self.status = "interrupted"
            self.message = "服务重启，可从上次位置继续"
            self.error = ""
            self.finished_at = _timestamp()
            if self.current.get("entry_id"):
                self.current["status"] = "等待继续"
            self.stop_requested = False

    def _persist_locked(self):
        if self.persist_callback is None:
            return
        self.persist_callback(self._saved_state_locked())


def build_po_translation_user_prompt(entry_id, references, source_text, target_text, protected_source, locked_terms, extra_prompt, target_missing):
    payload = {
        "entry_id": entry_id,
        "references": list(references or []),
        "source_text": source_text,
        "target_text": target_text,
        "target_missing": bool(target_missing),
        "protected_summary": protected_source.get("summary", ""),
        "translatable_slots": [
            {
                "slot_id": slot.get("slot_id", ""),
                "type": slot.get("type", ""),
                "source_text": slot.get("source_text", ""),
                "non_frontend_locked_terms": [
                    {"source": term["source"], "target": term["target"]}
                    for term in slot.get("non_frontend_locked_terms", [])
                ],
                "frontend_locked_terms": [
                    {"source": term["source"], "target": term["target"]}
                    for term in slot.get("frontend_locked_terms", [])
                ],
                "frontend_ui_context_rule": (
                    "Set frontend_ui_context=true only when this slot clearly refers to visible front-end UI elements "
                    "such as buttons, tabs, menus, links, labels, or page controls. Otherwise return false."
                ),
            }
            for slot in protected_source.get("translatable_slots", [])
        ],
        "locked_terms": [
            {"source": term["source"], "target": term["target"]}
            for term in locked_terms
        ],
        "extra_prompt": extra_prompt or "",
    }
    sections = []
    extra_instruction = str(extra_prompt or "").strip()
    if extra_instruction:
        sections.append(
            "High-priority additional instruction from user: {}. Follow it unless it conflicts with source_text meaning, placeholders, locked_terms, or protected rst structure.".format(
                extra_instruction
            )
        )
    sections.append("Task payload JSON:")
    sections.append(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return "\n".join(sections)


def build_po_translation_system_prompt():
    return (
        "You are a professional translator for gettext PO documentation strings that may contain protected reStructuredText fragments.\n"
        "Return JSON only with keys: verdict, slot_translations, reason.\n"
        "verdict must be either accurate or needs_update.\n"
        "slot_translations must be either an object mapping slot_id to English translation or an array of objects with keys slot_id, translation, and frontend_ui_context.\n"
        "Translate only the provided translatable_slots. Never recreate the full sentence on your own.\n"
        "Do not change rst role names, anchors, substitution tokens, inline literals, placeholders, or any immutable markup.\n"
        "When a text slot is adjacent to a protected substitution token such as |name|, translate only the surrounding connective text. Do not spell out, translate, or paraphrase the protected token inside the neighboring text slot.\n"
        "For role_label, link_label, reference_label, strong_text, emphasis_text, interpreted_text, or directive_argument slots, translate only the visible user-facing text for that slot.\n"
        "Use standard half-width English punctuation inside translated English text. Do not keep Chinese-style punctuation such as “ ” ‘ ’ ， 。 ： ； （ ） 【 】 ！ ？ 、 or …… unless it is part of immutable protected markup.\n"
        "For each translated slot, return frontend_ui_context=true only when the slot is clearly talking about visible UI elements such as buttons, tabs, menus, links, labels, or page controls.\n"
        "When frontend_ui_context=false, ignore frontend_locked_terms entirely.\n"
        "When frontend_ui_context=true, use frontend_locked_terms exactly as given if they are relevant.\n"
        "For quoted UI labels, menu paths, button text, and page titles that users select, click, open, or enter, keep glossary capitalization as visible UI text instead of lowercasing it for sentence grammar.\n"
        "Each translation must be natural English and must not contain Chinese explanations, JSON, or multiple lines.\n"
        "reason must be written in Simplified Chinese.\n"
        "If locked_terms are provided, the translated slots must use the glossary wording but adjust capitalization to fit English grammar.\n"
        "When a locked term appears at the start of a sentence, capitalize only the first ordinary word as needed.\n"
        "When a locked term appears mid-sentence, use normal lowercase for ordinary words instead of copying title case from the glossary. Preserve acronyms such as IP, ECS, or CPU.\n"
        "If extra_prompt is provided, treat it as a high-priority additional instruction unless it conflicts with source meaning, placeholders, locked_terms, or protected rst structure.\n"
        "If target_text is already accurate, set verdict=accurate and slot_translations to an empty object."
    )


def build_po_translation_review_user_prompt(entry_id, references, source_text, candidate_text, protected_source, locked_terms, target_missing, extra_prompt):
    payload = {
        "entry_id": entry_id,
        "references": list(references or []),
        "source_text": source_text,
        "candidate_text": candidate_text,
        "target_missing": bool(target_missing),
        "protected_summary": protected_source.get("summary", ""),
        "locked_terms": [
            {"source": term["source"], "target": term["target"]}
            for term in locked_terms
        ],
        "frontend_glossary_enabled": bool(protected_source.get("frontend_glossary_enabled", False)),
        "frontend_ui_slots": list(protected_source.get("frontend_ui_slots", [])),
        "active_frontend_terms": [
            {"source": term["source"], "target": term["target"]}
            for term in protected_source.get("active_frontend_terms", [])
        ],
        "extra_prompt": extra_prompt or "",
    }
    sections = []
    extra_instruction = str(extra_prompt or "").strip()
    if extra_instruction:
        sections.append(
            "High-priority additional instruction from user: {}. Review whether candidate_text follows it unless the instruction conflicts with source meaning, placeholders, locked_terms, or protected rst structure.".format(
                extra_instruction
            )
        )
    sections.append("Review payload JSON:")
    sections.append(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return "\n".join(sections)


def build_po_translation_review_system_prompt():
    return (
        "You are a strict QA reviewer for English PO translations generated from Chinese documentation text.\n"
        "Return JSON only with keys: decision, issues.\n"
        "decision must be either pass or fail.\n"
        "issues must be either an array of short Simplified Chinese strings or an array of objects with keys code, message, severity, evidence, and expected_term.\n"
        "For object issues, message and evidence must be written in Simplified Chinese. expected_term may contain English terminology.\n"
        "Ignore any previous English wording. Review candidate_text on its own merits against source_text.\n"
        "Protected rst structure is checked by the system separately. Focus on translation accuracy, natural English, placeholders, locked_terms, and extra_prompt.\n"
        "Do not fail solely because a locked term uses different capitalization. Treat locked_terms matching as case-insensitive.\n"
        "Do not report that a term should be X if candidate_text already contains X.\n"
        "Do not treat style-only suggestions such as 'could be more natural' as hard failures.\n"
        "Do not output English in message or evidence unless it is a required technical term quoted from source_text, candidate_text, or locked_terms.\n"
        "Fail when candidate_text still contains untranslated Chinese, keeps Chinese-style punctuation in otherwise English text, omits source meaning, or is not natural English.\n"
        "Pass only when candidate_text is a complete and accurate English translation of the source text."
    )


def _timestamp():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _display_text(value):
    return decode_unicode_escapes(str(value or ""))


def _normalize_reason(reason, fallback):
    value = _display_text(reason).strip()
    if is_chinese_explanation_text(value):
        return value
    return str(fallback or "").strip()


def _normalize_protected_english_candidate_text(candidate_text, locked_terms=None):
    value = sanitize_candidate_text(candidate_text)
    if not value:
        return ""
    protected = protect_rst_text(value)
    if not protected.get("supported", False):
        return sanitize_candidate_text(
            normalize_locked_term_grammar_case(
                normalize_english_punctuation(value),
                locked_terms,
            )
        )
    slot_translations = {}
    for slot in protected.get("translatable_slots", []):
        slot_id = str(slot.get("slot_id", "") or "")
        if not slot_id:
            continue
        slot_translations[slot_id] = normalize_english_punctuation(slot.get("source_text", ""))
    return sanitize_candidate_text(
        normalize_locked_term_grammar_case(
            compose_protected_text(protected, slot_translations),
            locked_terms,
        )
    )


def _preview(value, limit=60):
    text = _display_text(value).strip()
    if len(text) <= limit:
        return text
    return "{}...".format(text[:limit])
