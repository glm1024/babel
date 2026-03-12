from __future__ import absolute_import

import re

from zh_audit.utils import contains_han, decode_unicode_escapes


MAX_MODEL_CALLS_PER_ITEM = 5
PLACEHOLDER_PATTERN = re.compile(
    r"\$\{[^{}\r\n]+\}|\{[^{}\r\n]*\}|%(?:\d+\$)?[#0\- +,(]*\d*(?:\.\d+)?[A-Za-z]"
)
SQL_POLLUTION_PATTERN = re.compile(
    r"^\s*(?:update\s+\S+\s+set|insert\s+into|delete\s+from|replace\s+into|select\s+.+\s+from)\b|^\s*--",
    re.IGNORECASE | re.DOTALL,
)


def sanitize_candidate_text(value):
    text = decode_unicode_escapes(str(value or ""))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s*\n+\s*", " ", text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    return text.strip()


def extract_placeholders(text):
    value = str(text or "")
    return [match.group(0) for match in PLACEHOLDER_PATTERN.finditer(value)]


def has_matching_placeholders(source_text, candidate_text):
    return extract_placeholders(source_text) == extract_placeholders(candidate_text)


def contains_locked_terms(candidate, locked_terms):
    value = str(candidate or "")
    for term in locked_terms or []:
        if term["target"] not in value:
            return False
    return True


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


def normalize_review_result(result):
    payload = dict(result or {})
    decision = str(payload.get("decision", "") or payload.get("verdict", "") or "").strip().lower()
    issues = payload.get("issues", [])
    if isinstance(issues, str):
        issues = [issues]
    elif not isinstance(issues, list):
        issues = []
    normalized_issues = []
    for issue in issues:
        value = decode_unicode_escapes(str(issue or "")).strip()
        if value:
            normalized_issues.append(value)
    if decision in {"pass", "passed", "approve", "approved", "ok"}:
        return {
            "decision": "pass",
            "issues": normalized_issues,
        }
    if decision in {"fail", "failed", "reject", "rejected"}:
        return {
            "decision": "fail",
            "issues": normalized_issues or ["AI复核未通过"],
        }
    return {
        "decision": "fail",
        "issues": normalized_issues or ["AI复核未返回有效结论"],
    }


def validation_message(issue):
    value = str(issue or "").strip()
    if not value:
        value = "校验未通过"
    return "{}，请重生成".format(value)


def _normalize_for_compare(text):
    value = decode_unicode_escapes(str(text or ""))
    value = _strip_placeholders(value)
    value = re.sub(r"[\W_]+", "", value, flags=re.UNICODE)
    return value.lower().strip()


def _strip_placeholders(text):
    value = decode_unicode_escapes(str(text or ""))
    value = PLACEHOLDER_PATTERN.sub(" ", value)
    return value.strip()
