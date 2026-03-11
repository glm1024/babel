import re
from pathlib import Path

from zh_audit.models import (
    CATEGORY_COMMENT,
    CATEGORY_CONDITION_EXPRESSION_LITERAL,
    CATEGORY_CONFIG_ITEM,
    CATEGORY_DATABASE_SCRIPT,
    CATEGORY_ERROR_VALIDATION_MESSAGE,
    CATEGORY_GENERIC_DOCUMENTATION,
    CATEGORY_I18N_FILE,
    CATEGORY_LOG_AUDIT_DEBUG,
    CATEGORY_NAMED_FILE,
    CATEGORY_PROTOCOL_OR_PERSISTED_LITERAL,
    CATEGORY_SHELL_SCRIPT,
    CATEGORY_SWAGGER_DOCUMENTATION,
    CATEGORY_TASK_DESCRIPTION,
    CATEGORY_TEST_SAMPLE_FIXTURE,
    CATEGORY_UNKNOWN,
    CATEGORY_USER_VISIBLE_COPY,
    ClassifiedFinding,
    RawFinding,
)
from zh_audit.utils import (
    is_i18n_messages_file,
    is_named_keep_file,
    looks_like_assert_api_literal,
    looks_like_condition_expression_literal,
)


CONFIG_LANGS = {"yaml", "json", "properties", "toml"}
FRONTEND_LANGS = {"html", "vm", "js", "css"}
ERROR_TEXT_HINTS = ("失败", "异常", "错误", "不能为空", "不允许", "不存在", "已存在", "非法", "未停用")
ERROR_CONTEXT_HINTS = (
    "ajaxresult.warn(",
    "ajaxresult.error(",
    "return error(",
    "return fail(",
    "return warn(",
    "$.modal.alert",
    "throw ",
    "raise ",
    "panic(",
    "errors.new(",
    "fmt.errorf(",
)
ERROR_CONTEXT_RE = re.compile(
    r"(?:throw\s+new\s+\w*exception|new\s+\w*exception|\w*exception\s*\()"
)
PROTOCOL_TEXT_HINTS = ("状态", "类型", "字典", "枚举")
LOG_CONTEXT_RE = re.compile(r"(?<![A-Za-z0-9_])(?:logger|log|logging|console)\s*(?:\.|\()")
LOG_ANNOTATION_RE = re.compile(r"@\s*log\s*\(")
PROTOCOL_CONTEXT_RES = [
    re.compile(r"\b(?:private|public|protected)?\s*static\s+final\b"),
    re.compile(r"\benum\b"),
    re.compile(r"\bcase\b"),
    re.compile(r"\bdicttype\b"),
    re.compile(r"\bdict_type\b"),
    re.compile(r"\bdictdata\b"),
    re.compile(r"\bstatus\s*[:=]"),
    re.compile(r"\btype\s*[:=]"),
    re.compile(r"\bstate\s*[:=]"),
    re.compile(r"\bkind\s*[:=]"),
    re.compile(r"\bbusinesstype\b"),
    re.compile(r"\boperator_type\b"),
    re.compile(r"\brequest_method\b"),
]


def classify_rule(raw: RawFinding) -> ClassifiedFinding:
    path = raw.path.lower().replace("\\", "/")
    ext = Path(path).suffix.lower()
    text = raw.normalized_text or raw.text
    text_lower = text.lower()
    snippet_context = str(raw.snippet or "")
    local_context = str(raw.metadata.get("local_context") or "")
    context = local_context or snippet_context
    context_lower = context.lower()
    evidence_context = " ".join(part for part in (snippet_context, local_context) if part)
    evidence_context_lower = evidence_context.lower() if evidence_context else context_lower
    condition_extra_context = raw.context_window or ""

    category = CATEGORY_UNKNOWN
    action = "fix"
    confidence = 0.55
    high_risk = False
    end_user_visible = False
    reason = "No strong rule matched."

    if is_named_keep_file(path):
        category = CATEGORY_NAMED_FILE
        confidence = 0.99
        reason = "Named file context."
        action = "keep"
    elif is_i18n_messages_file(path):
        category = CATEGORY_I18N_FILE
        confidence = 0.99
        reason = "I18n messages file context."
        action = "keep"
    elif raw.lang == "sql":
        category = CATEGORY_DATABASE_SCRIPT
        confidence = 0.93
        reason = "Database script context."
        action = "keep"
    elif raw.lang == "shell":
        category = CATEGORY_SHELL_SCRIPT
        confidence = 0.93
        reason = "Shell script context."
        action = "keep"
    elif raw.file_role == "test_or_sample":
        category = CATEGORY_TEST_SAMPLE_FIXTURE
        action = "keep"
        confidence = 0.97
        reason = "Test/sample path context."
    elif raw.surface_kind == "comment" or "comment" in raw.candidate_roles:
        category = CATEGORY_COMMENT
        action = "keep"
        confidence = 0.98
        reason = "Comment context."
    elif "swagger_annotation" in raw.candidate_roles:
        category = CATEGORY_SWAGGER_DOCUMENTATION
        action = "keep"
        confidence = 0.98
        reason = "Swagger/OpenAPI annotation context."
    elif "task_description_annotation" in raw.candidate_roles:
        category = CATEGORY_TASK_DESCRIPTION
        action = "keep"
        confidence = 0.98
        reason = "Task description annotation context."
    elif _is_doc_asset(path):
        if _looks_like_protocol_context(evidence_context_lower, text, text_lower):
            category = CATEGORY_PROTOCOL_OR_PERSISTED_LITERAL
            action = "fix"
            confidence = 0.72
            high_risk = True
            reason = "Looks like protocol or persisted value."
        else:
            category = CATEGORY_GENERIC_DOCUMENTATION
            action = "keep"
            confidence = 0.93
            reason = "Documentation asset context."
    elif _looks_like_log_context(evidence_context_lower):
        category = CATEGORY_LOG_AUDIT_DEBUG
        action = "keep"
        confidence = 0.96
        reason = "Logging API context."
    elif raw.surface_kind == "string_literal" and looks_like_assert_api_literal(
        raw.snippet,
        context,
        extra_context=condition_extra_context,
    ):
        category = CATEGORY_CONDITION_EXPRESSION_LITERAL
        action = "keep"
        confidence = 0.94
        reason = "Logic processing literal context."
    elif _looks_like_error_context(evidence_context_lower):
        category = CATEGORY_ERROR_VALIDATION_MESSAGE
        action = "fix"
        confidence = 0.95
        end_user_visible = True
        reason = "Error/exception context."
    elif raw.surface_kind == "string_literal" and looks_like_condition_expression_literal(
        raw.snippet,
        context,
        language=raw.lang,
        extra_context=condition_extra_context,
    ):
        category = CATEGORY_CONDITION_EXPRESSION_LITERAL
        action = "keep"
        confidence = 0.92
        reason = "Logic processing literal context."
    elif raw.file_role == "template" or raw.lang in FRONTEND_LANGS:
        category = CATEGORY_USER_VISIBLE_COPY
        action = "fix"
        confidence = 0.9 if raw.lang in {"html", "vm"} else 0.86
        end_user_visible = True
        reason = "Markup or front-end text context."
    elif _looks_like_protocol_context(evidence_context_lower, text, text_lower):
        category = CATEGORY_PROTOCOL_OR_PERSISTED_LITERAL
        action = "fix"
        confidence = 0.72
        high_risk = True
        reason = "Looks like protocol or persisted value."
    elif raw.surface_kind == "string_literal" and any(token in text for token in ERROR_TEXT_HINTS):
        category = CATEGORY_ERROR_VALIDATION_MESSAGE
        action = "fix"
        confidence = 0.74
        end_user_visible = True
        reason = "Error semantics in string literal."
    elif raw.file_role == "config" or raw.lang in CONFIG_LANGS:
        if any(token in text for token in ERROR_TEXT_HINTS):
            category = CATEGORY_ERROR_VALIDATION_MESSAGE
            action = "fix"
            confidence = 0.8
            end_user_visible = True
            reason = "Error semantics in string literal."
        else:
            category = CATEGORY_CONFIG_ITEM
            action = "fix"
            confidence = 0.88
            reason = "Configuration item context."
    elif raw.surface_kind == "string_literal":
        category = CATEGORY_USER_VISIBLE_COPY
        action = "fix"
        confidence = 0.7
        end_user_visible = True
        reason = "String literal with Chinese text."
    elif raw.lang == "xml":
        category = CATEGORY_CONFIG_ITEM
        action = "fix"
        confidence = 0.68
        reason = "Configuration item context."

    return ClassifiedFinding(
        id=raw.id,
        project=raw.project,
        path=raw.path,
        lang=raw.lang,
        line=raw.line,
        column=raw.column,
        surface_kind=raw.surface_kind,
        symbol=raw.symbol,
        text=raw.text,
        normalized_text=raw.normalized_text,
        hit_text=raw.hit_text,
        snippet=raw.snippet,
        category=category,
        action=action,
        confidence=confidence,
        high_risk=high_risk,
        end_user_visible=end_user_visible,
        reason=reason,
        file_role=raw.file_role,
        candidate_roles=list(raw.candidate_roles),
        metadata=dict(raw.metadata),
    )


def _is_doc_asset(path: str) -> bool:
    return (
        path.startswith("doc/")
        or path.startswith("docs/")
        or path.startswith("wiki/")
        or "readme" in path
        or path.endswith(".pdm")
        or path.endswith("/ruoyi.html")
    )


def _looks_like_log_context(context_lower: str) -> bool:
    return bool(
        LOG_CONTEXT_RE.search(context_lower)
        or LOG_ANNOTATION_RE.search(context_lower)
        or "system.out." in context_lower
        or "system.err." in context_lower
        or "printstacktrace(" in context_lower
    )


def _looks_like_error_context(context_lower: str) -> bool:
    return any(token in context_lower for token in ERROR_CONTEXT_HINTS) or bool(
        ERROR_CONTEXT_RE.search(context_lower)
    )


def _looks_like_protocol_context(context_lower: str, text: str, text_lower: str) -> bool:
    if any(token in text for token in ERROR_TEXT_HINTS):
        return False
    if any(pattern.search(context_lower) for pattern in PROTOCOL_CONTEXT_RES):
        return len(text.strip()) <= 40
    if "insert into" in context_lower and any(token in text for token in PROTOCOL_TEXT_HINTS):
        return True
    if any(token in text for token in PROTOCOL_TEXT_HINTS) and any(
        marker in context_lower for marker in (" status", " type", " state", " kind", "dict", "category")
    ):
        return True
    return False
