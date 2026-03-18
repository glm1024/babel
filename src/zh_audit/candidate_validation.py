from __future__ import absolute_import

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
    value = decode_unicode_escapes(str(candidate or ""))
    lowered_value = value.casefold()
    for term in locked_terms or []:
        target = decode_unicode_escapes(str(term.get("target", "") or "")).strip()
        if target and target.casefold() not in lowered_value:
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


def normalize_review_result(result, *, source_text="", target_text="", candidate_text=""):
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
    filtered_issues = [
        issue
        for issue in normalized_issues
        if not _should_ignore_review_issue(
            issue,
            source_text=source_text,
            target_text=target_text,
            candidate_text=candidate_text,
        )
    ]
    if decision in {"pass", "passed", "approve", "approved", "ok"}:
        return {
            "decision": "pass",
            "issues": filtered_issues,
        }
    if decision in {"fail", "failed", "reject", "rejected"}:
        if normalized_issues and not filtered_issues:
            return {
                "decision": "pass",
                "issues": [],
            }
        return {
            "decision": "fail",
            "issues": filtered_issues or ["AI复核未通过"],
        }
    return {
        "decision": "fail",
        "issues": filtered_issues or ["AI复核未返回有效结论"],
    }


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


def _should_ignore_review_issue(issue, *, source_text="", target_text="", candidate_text=""):
    value = decode_unicode_escapes(str(issue or "")).strip()
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

    if candidate_value and _is_case_only_terminology_issue(value, candidate_value):
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
