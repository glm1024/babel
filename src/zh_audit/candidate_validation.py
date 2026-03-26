from __future__ import absolute_import

import json
import re

from zh_audit.utils import contains_han, decode_unicode_escapes


MAX_GENERATION_ATTEMPTS_PER_ITEM = 3
# Backward compatibility for older imports and serialized state readers.
MAX_MODEL_CALLS_PER_ITEM = MAX_GENERATION_ATTEMPTS_PER_ITEM
PLACEHOLDER_PATTERN = re.compile(
    r"\$\{[^{}\r\n]+\}|\{[^{}\r\n]*\}|%(?:\d+\$)?[#0\- +,(]*\d*(?:\.\d+)?[A-Za-z]"
)
SQL_POLLUTION_PATTERN = re.compile(
    r"^\s*(?:update\s+\S+\s+set|insert\s+into|delete\s+from|replace\s+into|select\s+.+\s+from)\b|^\s*--",
    re.IGNORECASE | re.DOTALL,
)
QUOTED_REVIEW_TOKEN_PATTERN = re.compile(r"[\"'“”‘’]([^\"'“”‘’]{2,})[\"'“”‘’]")
ENGLISH_PROSE_HINT_PATTERN = re.compile(
    r"\b(?:the|a|an|and|or|to|be|as|per|for|with|should|must|could|would|match|source|target|text|candidate|translation|term|because|also|not|is|are|was|were|use|using|translated|translate|capitalized|capitalize|capitalization|wording|natural|style|suggestion|accurate|accuracy|action|replace|review)\b",
    re.IGNORECASE,
)
RETRY_STRATEGY_NAMES = {
    1: "标准生成",
    2: "结构化修复",
    3: "保守最小修改",
}
VALIDATION_ISSUE_CODES = {
    "候选为空": "candidate_empty",
    "候选包含多行内容": "candidate_multiline",
    "候选包含 key": "candidate_contains_key",
    "候选包含 SQL 内容": "candidate_contains_sql",
    "候选未满足术语词典要求": "terminology_mismatch",
    "候选未保留占位符": "placeholders_mismatch",
    "候选仍含中文": "candidate_contains_han",
    "候选与中文源文相同": "candidate_same_as_source",
}
ENGLISH_PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        "＂": '"',
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "＇": "'",
        "，": ",",
        "。": ".",
        "；": ";",
        "：": ":",
        "！": "!",
        "？": "?",
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "｛": "{",
        "｝": "}",
        "［": "[",
        "］": "]",
        "｟": "(",
        "｠": ")",
        "、": ",",
        "％": "%",
        "／": "/",
        "＼": "\\",
        "＋": "+",
        "＝": "=",
        "＆": "&",
        "＠": "@",
        "＃": "#",
        "｜": "|",
        "～": "~",
        "－": "-",
        "「": '"',
        "」": '"',
        "『": '"',
        "』": '"',
        "〈": '"',
        "〉": '"',
        "《": '"',
        "》": '"',
        "　": " ",
    }
)
LOCKED_TERM_WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9'-]*")
UI_ACTION_HINT_PATTERN = re.compile(
    r"\b(?:click|select|choose|open|go to|enter|press|tap|navigate to|access)\b",
    re.IGNORECASE,
)
UI_CONTAINER_HINT_PATTERN = re.compile(
    r"\b(?:button|tab|menu|page|dialog|window|wizard|panel|pane|column|field|link|option|view)\b",
    re.IGNORECASE,
)


def sanitize_candidate_text(value):
    text = decode_unicode_escapes(str(value or ""))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s*\n+\s*", " ", text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    return text.strip()


def normalize_english_punctuation(value):
    text = decode_unicode_escapes(str(value or ""))
    if not text:
        return ""
    text = text.replace("……", "...")
    text = text.replace("…", "...")
    text = text.replace("——", "-")
    text = text.replace("—", "-")
    return text.translate(ENGLISH_PUNCTUATION_TRANSLATION)


def normalize_locked_term_grammar_case(candidate, locked_terms):
    text = decode_unicode_escapes(str(candidate or ""))
    if not text or not locked_terms:
        return text

    replacements = []
    occupied = []
    targets = []
    for term in locked_terms or []:
        target = decode_unicode_escapes(str(term.get("target", "") or "")).strip()
        if target:
            targets.append(target)
    for target in sorted(set(targets), key=lambda value: (-len(value), value.casefold())):
        pattern = re.compile(re.escape(target), re.IGNORECASE)
        for match in pattern.finditer(text):
            start, end = match.span()
            if _ranges_overlap(occupied, start, end):
                continue
            if not _has_term_boundary(text, start, end):
                continue
            if _is_ui_style_locked_term_occurrence(text, start, end):
                replacement = target
            else:
                replacement = _normalized_locked_term_surface(
                    target,
                    sentence_initial=_is_sentence_initial_term_occurrence(text, start),
                )
            replacements.append(
                (
                    start,
                    end,
                    replacement,
                )
            )
            occupied.append((start, end))
    if not replacements:
        return text
    replacements.sort(key=lambda item: item[0])
    pieces = []
    last_index = 0
    for start, end, replacement in replacements:
        pieces.append(text[last_index:start])
        pieces.append(replacement)
        last_index = end
    pieces.append(text[last_index:])
    return "".join(pieces)


def extract_placeholders(text):
    value = str(text or "")
    return [match.group(0) for match in PLACEHOLDER_PATTERN.finditer(value)]


def has_matching_placeholders(source_text, candidate_text):
    return extract_placeholders(source_text) == extract_placeholders(candidate_text)


def contains_locked_terms(candidate, locked_terms):
    value = decode_unicode_escapes(str(candidate or ""))
    lowered_value = value.casefold()
    for term in locked_terms or []:
        target = decode_unicode_escapes(str(term.get("target", "") or "")).strip()
        if target and target.casefold() not in lowered_value:
            return False
    return True


def missing_locked_terms(candidate, locked_terms):
    value = decode_unicode_escapes(str(candidate or ""))
    lowered_value = value.casefold()
    missing = []
    for term in locked_terms or []:
        target = decode_unicode_escapes(str(term.get("target", "") or "")).strip()
        if target and target.casefold() not in lowered_value:
            missing.append(
                {
                    "source": decode_unicode_escapes(str(term.get("source", "") or "")).strip(),
                    "target": target,
                }
            )
    return missing


def validate_candidate_text(
    source_text,
    candidate_text,
    *,
    raw_candidate_text=None,
    locked_terms=None,
    key="",
    check_sql_pollution=False,
    enforce_placeholders=True,
):
    raw_value = decode_unicode_escapes(str(raw_candidate_text if raw_candidate_text is not None else candidate_text or ""))
    sanitized = sanitize_candidate_text(candidate_text)
    if not sanitized:
        return "候选为空"
    if "\n" in raw_value or "\r" in raw_value:
        return "候选包含多行内容"
    if key and re.match(r"^\s*{}\s*[:=]".format(re.escape(str(key))), sanitized):
        return "候选包含 key"
    if check_sql_pollution and SQL_POLLUTION_PATTERN.search(sanitized):
        return "候选包含 SQL 内容"
    if locked_terms and not contains_locked_terms(sanitized, locked_terms):
        return "候选未满足术语词典要求"
    if enforce_placeholders and not has_matching_placeholders(source_text, sanitized):
        return "候选未保留占位符"
    if contains_han(_strip_placeholders(sanitized)):
        return "候选仍含中文"
    if _normalize_for_compare(source_text) and _normalize_for_compare(source_text) == _normalize_for_compare(sanitized):
        return "候选与中文源文相同"
    return ""


def normalize_review_result(result, *, source_text="", target_text="", candidate_text="", locked_terms=None):
    payload = dict(result or {})
    decision = str(payload.get("decision", "") or payload.get("verdict", "") or "").strip().lower()
    issues = payload.get("issues", [])
    if isinstance(issues, str):
        issues = [issues]
    elif not isinstance(issues, list):
        issues = []
    normalized_issues = []
    for issue in issues:
        normalized = _normalize_review_issue(issue)
        if normalized.get("message"):
            normalized_issues.append(normalized)
    filtered_issues = []
    warning_issues = []
    for issue in normalized_issues:
        if _should_ignore_review_issue(
            issue,
            source_text=source_text,
            target_text=target_text,
            candidate_text=candidate_text,
            locked_terms=locked_terms,
        ):
            continue
        if _is_warning_review_issue(issue):
            warning_issues.append(issue)
            continue
        filtered_issues.append(issue)
    filtered_messages = [issue["message"] for issue in filtered_issues]
    warning_messages = [issue["message"] for issue in warning_issues]
    if decision in {"pass", "passed", "approve", "approved", "ok"}:
        return {
            "decision": "pass",
            "issues": filtered_messages,
            "warnings": warning_messages,
            "issue_details": filtered_issues,
            "warning_details": warning_issues,
        }
    if decision in {"fail", "failed", "reject", "rejected"}:
        if normalized_issues and not filtered_issues:
            return {
                "decision": "pass",
                "issues": [],
                "warnings": warning_messages,
                "issue_details": [],
                "warning_details": warning_issues,
            }
        return {
            "decision": "fail",
            "issues": filtered_messages or ["AI复核未通过"],
            "warnings": warning_messages,
            "issue_details": filtered_issues,
            "warning_details": warning_issues,
        }
    return {
        "decision": "fail",
        "issues": filtered_messages or ["AI复核未返回有效结论"],
        "warnings": warning_messages,
        "issue_details": filtered_issues,
        "warning_details": warning_issues,
    }


def is_chinese_explanation_text(value):
    text = decode_unicode_escapes(str(value or "")).strip()
    if not text or not contains_han(text):
        return False
    stripped = QUOTED_REVIEW_TOKEN_PATTERN.sub(" ", text)
    stripped = PLACEHOLDER_PATTERN.sub(" ", stripped)
    return len(ENGLISH_PROSE_HINT_PATTERN.findall(stripped)) < 2


def validation_message(issue):
    value = str(issue or "").strip()
    if not value:
        value = "校验未通过"
    return "{}，请重新生成".format(value)


def exhausted_validation_message(issue, attempts):
    value = str(issue or "").strip()
    if not value:
        value = "校验未通过"
    return "已重试 {} 次仍未通过，失败原因：{}，请重新生成".format(
        int(attempts or MAX_GENERATION_ATTEMPTS_PER_ITEM),
        value,
    )


def _normalize_for_compare(text):
    value = decode_unicode_escapes(str(text or ""))
    value = _strip_placeholders(value)
    value = re.sub(r"[\W_]+", "", value, flags=re.UNICODE)
    return value.lower().strip()


def _strip_placeholders(text):
    value = decode_unicode_escapes(str(text or ""))
    value = PLACEHOLDER_PATTERN.sub(" ", value)
    return value.strip()


def retry_strategy_name(attempt_number):
    try:
        attempt = int(attempt_number or 1)
    except (TypeError, ValueError):
        attempt = 1
    return RETRY_STRATEGY_NAMES.get(attempt, "结构化修复")


def _ranges_overlap(ranges, start, end):
    for current_start, current_end in ranges:
        if start < current_end and end > current_start:
            return True
    return False


def _has_term_boundary(text, start, end):
    if start > 0 and _is_word_char(text[start - 1]) and _is_word_char(text[start]):
        return False
    if end < len(text) and _is_word_char(text[end - 1]) and _is_word_char(text[end]):
        return False
    return True


def _is_word_char(char):
    return bool(char) and (char.isalnum() or char == "_")


def _is_sentence_initial_term_occurrence(text, start):
    index = int(start) - 1
    while index >= 0:
        current = text[index]
        if current.isspace():
            index -= 1
            continue
        if current in "\"'([{":
            index -= 1
            continue
        return current in ".!?:;\n"
    return True


def _is_ui_style_locked_term_occurrence(text, start, end):
    quoted = _quoted_ui_segment(text, start, end)
    if quoted is None:
        return False
    open_index, close_index, body = quoted
    if ">" in body or "|" in body or "/" in body:
        return True
    before = text[max(0, open_index - 48) : open_index]
    after = text[close_index : min(len(text), close_index + 48)]
    return bool(UI_ACTION_HINT_PATTERN.search(before) or UI_CONTAINER_HINT_PATTERN.search(after))


def _quoted_ui_segment(text, start, end):
    for open_quote, close_quote in (('"', '"'), ("“", "”")):
        open_index = text.rfind(open_quote, 0, start)
        if open_index < 0:
            continue
        close_index = text.find(close_quote, end)
        if close_index < 0:
            continue
        if start < open_index + len(open_quote) or end > close_index:
            continue
        return (
            open_index,
            close_index + len(close_quote),
            text[open_index + len(open_quote) : close_index],
        )
    return None


def _normalized_locked_term_surface(target, sentence_initial):
    pieces = []
    last_index = 0
    first_word = True
    for match in LOCKED_TERM_WORD_PATTERN.finditer(str(target or "")):
        pieces.append(target[last_index:match.start()])
        pieces.append(_normalized_locked_term_word(match.group(0), capitalize=sentence_initial and first_word))
        first_word = False
        last_index = match.end()
    pieces.append(target[last_index:])
    return "".join(pieces)


def _normalized_locked_term_word(word, capitalize):
    value = str(word or "")
    if not value:
        return value
    if any(char.isdigit() for char in value):
        return value
    if value.isupper() and len(value) > 1:
        return value
    if any(char.isupper() for char in value[1:]) and any(char.islower() for char in value):
        return value
    normalized = value.lower()
    if capitalize:
        return normalized[:1].upper() + normalized[1:]
    return normalized


def build_retry_context(
    *,
    phase,
    issue_code,
    issue_message,
    previous_candidate="",
    source_text="",
    locked_terms=None,
    candidate_text="",
    must_keep_placeholders=None,
    missing_meaning="",
    expected_term="",
    forbidden_rewrite="",
    style_warning="",
):
    terms = missing_locked_terms(candidate_text, locked_terms)
    return {
        "phase": str(phase or ""),
        "issue_code": str(issue_code or ""),
        "issue_message": str(issue_message or "").strip(),
        "previous_candidate": sanitize_candidate_text(previous_candidate),
        "must_use_terms": terms,
        "missing_meaning": str(missing_meaning or "").strip(),
        "must_keep_placeholders": list(must_keep_placeholders or extract_placeholders(source_text)),
        "expected_term": str(expected_term or "").strip(),
        "forbidden_rewrite": str(forbidden_rewrite or "").strip(),
        "style_warning": str(style_warning or "").strip(),
    }


def retry_context_preview(retry_context):
    payload = dict(retry_context or {})
    message = str(payload.get("issue_message", "") or "").strip()
    phase = str(payload.get("phase", "") or "").strip()
    phase = {
        "model_format": "模型格式",
        "local_validation": "本地校验",
        "ai_review": "AI复核",
    }.get(phase, phase)
    if phase and message:
        return "{}：{}".format(phase, message)
    if message:
        return message
    return ""


def structured_retry_prompt(base_extra_prompt, retry_context, attempt_number):
    parts = []
    strategy = retry_strategy_name(attempt_number)
    if retry_context:
        parts.append("当前重试策略：{}。".format(strategy))
        if int(attempt_number or 1) == 2:
            parts.append("请仅修复 retry_context 指出的硬失败问题，不要改动已经正确的片段。")
        elif int(attempt_number or 1) >= 3:
            parts.append("请以 previous_candidate 为基底做最小修改，只修补术语、缺失语义、占位符或短语表达问题。")
        parts.append("retry_context JSON:")
        parts.append(json.dumps(retry_context, ensure_ascii=False, indent=2, sort_keys=True))
    if base_extra_prompt:
        parts.append(str(base_extra_prompt).strip())
    return "\n".join(part for part in parts if part).strip()


def validation_issue_code(issue):
    return VALIDATION_ISSUE_CODES.get(str(issue or "").strip(), "validation_failed")


def build_validation_retry_context(source_text, previous_candidate, locked_terms, issue_message):
    return build_retry_context(
        phase="local_validation",
        issue_code=validation_issue_code(issue_message),
        issue_message=issue_message,
        previous_candidate=previous_candidate,
        source_text=source_text,
        locked_terms=locked_terms,
        candidate_text=previous_candidate,
    )


def build_review_retry_context(source_text, previous_candidate, locked_terms, issue_detail, warning_details=None):
    detail = _normalize_review_issue(issue_detail)
    warnings = [_normalize_review_issue(item).get("message", "") for item in (warning_details or [])]
    return build_retry_context(
        phase="ai_review",
        issue_code=detail.get("code", "") or "ai_review_failed",
        issue_message=detail.get("message", "") or "AI复核未通过",
        previous_candidate=previous_candidate,
        source_text=source_text,
        locked_terms=locked_terms,
        candidate_text=previous_candidate,
        missing_meaning=_extract_missing_meaning(detail, source_text),
        expected_term=_first_expected_term(detail),
        forbidden_rewrite=_extract_forbidden_rewrite(detail),
        style_warning="；".join(message for message in warnings if message)[:300],
    )


def build_attempt_history_entry(
    attempt_number,
    candidate_text,
    *,
    failure_phase="",
    failure_issue="",
    warnings=None,
    reason="",
    retry_context=None,
):
    return {
        "attempt": int(attempt_number or 0),
        "strategy": retry_strategy_name(attempt_number),
        "candidate_text": sanitize_candidate_text(candidate_text),
        "failure_phase": str(failure_phase or ""),
        "failure_issue": str(failure_issue or ""),
        "warnings": [str(message or "").strip() for message in (warnings or []) if str(message or "").strip()],
        "reason": str(reason or "").strip(),
        "retry_context_preview": retry_context_preview(retry_context),
        "status": "failed" if failure_issue else "passed",
    }


def _normalize_review_issue(issue):
    if isinstance(issue, dict):
        expected_term = decode_unicode_escapes(str(issue.get("expected_term", "") or "")).strip()
        message = _normalize_review_message(
            issue.get("message", ""),
            code=issue.get("code", ""),
            expected_term=expected_term,
        )
        return {
            "code": decode_unicode_escapes(str(issue.get("code", "") or "")).strip(),
            "message": message,
            "severity": decode_unicode_escapes(str(issue.get("severity", "") or "")).strip().lower(),
            "evidence": _normalize_review_evidence(issue.get("evidence", "")),
            "expected_term": expected_term,
        }
    value = _normalize_review_message(issue)
    return {
        "code": "",
        "message": value,
        "severity": "",
        "evidence": "",
        "expected_term": "",
    }


def _should_ignore_review_issue(issue, *, source_text="", target_text="", candidate_text="", locked_terms=None):
    value = decode_unicode_escapes(str(issue.get("message", "") or "")).strip()
    candidate_value = decode_unicode_escapes(str(candidate_text or ""))
    lower_issue = value.lower()

    if any(token in value for token in ("目标文本", "当前英文")) and any(
        token in value for token in ("不匹配", "不一致", "不符", "不同")
    ):
        return True

    if candidate_value and target_text and candidate_value.strip() != decode_unicode_escapes(str(target_text or "")).strip():
        if any(
            token in value
            for token in (
                "候选文本与目标文本不匹配",
                "候选文本与目标文本不一致",
                "候选文本与当前英文不匹配",
                "候选文本与当前英文不一致",
            )
        ):
            return True

    if "拼写" in value:
        quoted_tokens = [match.group(1).strip() for match in QUOTED_REVIEW_TOKEN_PATTERN.finditer(value)]
        if quoted_tokens and all(token and token not in candidate_value for token in quoted_tokens):
            return True

    if source_text and candidate_value and _normalize_for_compare(source_text) == _normalize_for_compare(candidate_value):
        if "目标文本" in value and any(token in lower_issue for token in ("mismatch", "different")):
            return True

    if candidate_value and locked_terms and contains_locked_terms(candidate_value, locked_terms):
        if "术语" in value and any(token in value for token in ("缺失", "不一致", "未满足", "未翻译")):
            expected_terms = _extract_expected_terms(issue)
            if not expected_terms or all(
                term and decode_unicode_escapes(term).casefold() in candidate_value.casefold()
                for term in expected_terms
            ):
                return True

    if candidate_value and _is_case_only_terminology_issue(value, candidate_value):
        return True

    expected_terms = _extract_expected_terms(issue)
    if expected_terms and any(
        term and decode_unicode_escapes(term).casefold() in candidate_value.casefold()
        for term in expected_terms
    ):
        if any(token in value for token in ("应为", "应包含", "未准确翻译", "术语", "缺失")):
            return True

    return False


def _is_case_only_terminology_issue(issue, candidate_text):
    value = decode_unicode_escapes(str(issue or "")).strip()
    candidate_value = decode_unicode_escapes(str(candidate_text or ""))
    if not value or not candidate_value:
        return False
    if not any(token in value for token in ("术语", "大写", "小写", "大小写", "首字母")):
        return False

    quoted_tokens = [match.group(1).strip() for match in QUOTED_REVIEW_TOKEN_PATTERN.finditer(value)]
    latin_tokens = [token for token in quoted_tokens if token and re.search(r"[A-Za-z]", token)]
    if not latin_tokens:
        return False

    candidate_folded = candidate_value.casefold()
    for token in latin_tokens:
        token_folded = token.casefold()
        if token_folded and token_folded in candidate_folded and token not in candidate_value:
            return True
    return False


def _is_warning_review_issue(issue):
    severity = str(issue.get("severity", "") or "").strip().lower()
    if severity in {"warning", "warn", "info", "suggestion", "minor"}:
        return True
    value = decode_unicode_escapes(str(issue.get("message", "") or "")).strip()
    if not value:
        return False
    if any(token in value for token in ("术语", "占位符", "未翻译", "缺失", "遗漏", "破坏", "错误", "不准确", "不完整")):
        return False
    return any(token in value for token in ("更自然", "可更自然", "更简洁", "可更简洁", "可优化", "更地道", "更顺畅", "建议", "风格", "措辞"))


def _normalize_review_message(message, *, code="", expected_term=""):
    value = decode_unicode_escapes(str(message or "")).strip()
    if not value:
        return ""
    if is_chinese_explanation_text(value):
        return value

    lower_value = value.lower()
    normalized_code = decode_unicode_escapes(str(code or "")).strip().lower()
    expected = decode_unicode_escapes(str(expected_term or "")).strip()

    if normalized_code == "style" or any(
        token in lower_value for token in ("style", "natural", "wording", "concise", "fluent", "read better", "readability")
    ):
        return "表达可更自然，建议调整措辞"
    if any(token in lower_value for token in ("placeholder", "placeholders")):
        return "候选未保留占位符"
    if any(token in lower_value for token in ("contains chinese", "still contains chinese", "untranslated chinese")):
        return "候选仍含中文"
    if expected:
        return "术语不一致：应使用'{}'".format(expected)

    quoted_terms = [term for term in _extract_quoted_terms(value) if re.search(r"[A-Za-z]", term)]
    if "term" in lower_value and "should" in lower_value and quoted_terms:
        return "术语不一致：应使用'{}'".format(quoted_terms[-1])
    if any(token in lower_value for token in ("missing", "omits", "omit", "incomplete", "not accurate", "inaccurate")):
        return "译文未完整覆盖源文语义"
    return "AI复核未通过"


def _normalize_review_evidence(evidence):
    value = decode_unicode_escapes(str(evidence or "")).strip()
    if not value:
        return ""
    if is_chinese_explanation_text(value):
        return value
    return ""


def _extract_expected_terms(issue):
    expected = decode_unicode_escapes(str(issue.get("expected_term", "") or "")).strip()
    if expected:
        return [expected]
    value = decode_unicode_escapes(str(issue.get("message", "") or "")).strip()
    for marker in ("应翻译为", "应为", "应包含"):
        if marker in value:
            suffix = value.split(marker, 1)[1]
            terms = [token for token in _extract_quoted_terms(suffix) if re.search(r"[A-Za-z]", token)]
            if terms:
                return [terms[0]]
    return [token for token in _extract_quoted_terms(value) if re.search(r"[A-Za-z]", token)]


def _extract_quoted_terms(value):
    return [match.group(1).strip() for match in QUOTED_REVIEW_TOKEN_PATTERN.finditer(str(value or ""))]


def _first_expected_term(issue):
    for term in _extract_expected_terms(issue):
        if term:
            return term
    return ""


def _extract_missing_meaning(issue, source_text):
    evidence = decode_unicode_escapes(str(issue.get("evidence", "") or "")).strip()
    if evidence:
        return evidence
    value = decode_unicode_escapes(str(issue.get("message", "") or "")).strip()
    quoted_terms = _extract_quoted_terms(value)
    han_terms = [term for term in quoted_terms if contains_han(term)]
    if han_terms:
        return han_terms[0]
    if "源文本" in value and source_text:
        return decode_unicode_escapes(str(source_text or "")).strip()
    return ""


def _extract_forbidden_rewrite(issue):
    value = decode_unicode_escapes(str(issue.get("message", "") or "")).strip()
    if not value:
        return ""
    if "不要" in value or "不应" in value:
        return value
    return ""
