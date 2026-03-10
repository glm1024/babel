from pathlib import Path
from typing import Any, Dict, Iterable, List


CATEGORY_USER_VISIBLE_COPY = "USER_VISIBLE_COPY"
CATEGORY_ERROR_VALIDATION_MESSAGE = "ERROR_VALIDATION_MESSAGE"
CATEGORY_LOG_AUDIT_DEBUG = "LOG_AUDIT_DEBUG"
CATEGORY_COMMENT = "COMMENT"
CATEGORY_SWAGGER_DOCUMENTATION = "SWAGGER_DOCUMENTATION"
CATEGORY_GENERIC_DOCUMENTATION = "GENERIC_DOCUMENTATION"
CATEGORY_DATABASE_SCRIPT = "DATABASE_SCRIPT"
CATEGORY_SHELL_SCRIPT = "SHELL_SCRIPT"
CATEGORY_NAMED_FILE = "NAMED_FILE"
CATEGORY_TEST_SAMPLE_FIXTURE = "TEST_SAMPLE_FIXTURE"
CATEGORY_CONFIG_ITEM = "CONFIG_ITEM"
CATEGORY_PROTOCOL_OR_PERSISTED_LITERAL = "PROTOCOL_OR_PERSISTED_LITERAL"
CATEGORY_UNKNOWN = "UNKNOWN"

CATEGORY_ORDER = [
    CATEGORY_USER_VISIBLE_COPY,
    CATEGORY_ERROR_VALIDATION_MESSAGE,
    CATEGORY_CONFIG_ITEM,
    CATEGORY_PROTOCOL_OR_PERSISTED_LITERAL,
    CATEGORY_UNKNOWN,
    CATEGORY_COMMENT,
    CATEGORY_SWAGGER_DOCUMENTATION,
    CATEGORY_GENERIC_DOCUMENTATION,
    CATEGORY_DATABASE_SCRIPT,
    CATEGORY_SHELL_SCRIPT,
    CATEGORY_NAMED_FILE,
    CATEGORY_LOG_AUDIT_DEBUG,
    CATEGORY_TEST_SAMPLE_FIXTURE,
]

DEFAULT_EXCLUDE_GLOBS = [
    "**/target/**",
    "**/node_modules/**",
    "**/vendor/**",
    "**/webjars/**",
    "**/static/ajax/libs/**",
]


def _copy_value(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [_copy_value(item) for item in value]
    if isinstance(value, dict):
        return dict((key, _copy_value(item)) for key, item in value.items())
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


class Serializable(object):
    __slots__ = ()

    def to_dict(self):
        data = {}
        for name in self.__slots__:
            data[name] = _copy_value(getattr(self, name))
        return data


class RepoSpec(object):
    __slots__ = ("path",)

    def __init__(self, path):
        self.path = path

    @property
    def name(self):
        return self.path.name or str(self.path)


class ScanSettings(object):
    __slots__ = ("max_file_size_bytes", "context_lines", "exclude_globs")

    def __init__(self, max_file_size_bytes=5 * 1024 * 1024, context_lines=1, exclude_globs=None):
        self.max_file_size_bytes = max_file_size_bytes
        self.context_lines = context_lines
        self.exclude_globs = list(exclude_globs) if exclude_globs is not None else list(DEFAULT_EXCLUDE_GLOBS)


class FileRecord(Serializable):
    __slots__ = (
        "repo",
        "path",
        "relative_path",
        "eligible",
        "scanned",
        "skip_reason",
        "skip_detail",
        "encoding",
        "lang",
        "size_bytes",
    )

    def __init__(
        self,
        repo,
        path,
        relative_path,
        eligible,
        scanned,
        skip_reason="",
        skip_detail="",
        encoding="",
        lang="",
        size_bytes=0,
    ):
        self.repo = repo
        self.path = path
        self.relative_path = relative_path
        self.eligible = eligible
        self.scanned = scanned
        self.skip_reason = skip_reason
        self.skip_detail = skip_detail
        self.encoding = encoding
        self.lang = lang
        self.size_bytes = size_bytes


class RawFinding(Serializable):
    __slots__ = (
        "id",
        "project",
        "path",
        "lang",
        "line",
        "column",
        "surface_kind",
        "symbol",
        "text",
        "normalized_text",
        "snippet",
        "context_window",
        "file_role",
        "candidate_roles",
        "metadata",
    )

    def __init__(
        self,
        id,
        project,
        path,
        lang,
        line,
        column,
        surface_kind,
        symbol,
        text,
        normalized_text,
        snippet,
        context_window,
        file_role,
        candidate_roles,
        metadata=None,
    ):
        self.id = id
        self.project = project
        self.path = path
        self.lang = lang
        self.line = line
        self.column = column
        self.surface_kind = surface_kind
        self.symbol = symbol
        self.text = text
        self.normalized_text = normalized_text
        self.snippet = snippet
        self.context_window = context_window
        self.file_role = file_role
        self.candidate_roles = list(candidate_roles)
        self.metadata = dict(metadata or {})


class ClassifiedFinding(Serializable):
    __slots__ = (
        "id",
        "project",
        "path",
        "lang",
        "line",
        "column",
        "surface_kind",
        "symbol",
        "text",
        "normalized_text",
        "snippet",
        "category",
        "action",
        "confidence",
        "high_risk",
        "end_user_visible",
        "reason",
        "file_role",
        "candidate_roles",
        "metadata",
    )

    def __init__(
        self,
        id,
        project,
        path,
        lang,
        line,
        column,
        surface_kind,
        symbol,
        text,
        normalized_text,
        snippet,
        category,
        action,
        confidence,
        high_risk,
        end_user_visible,
        reason,
        file_role,
        candidate_roles,
        metadata=None,
    ):
        self.id = id
        self.project = project
        self.path = path
        self.lang = lang
        self.line = line
        self.column = column
        self.surface_kind = surface_kind
        self.symbol = symbol
        self.text = text
        self.normalized_text = normalized_text
        self.snippet = snippet
        self.category = category
        self.action = action
        self.confidence = confidence
        self.high_risk = high_risk
        self.end_user_visible = end_user_visible
        self.reason = reason
        self.file_role = file_role
        self.candidate_roles = list(candidate_roles)
        self.metadata = dict(metadata or {})


class RunArtifacts(object):
    __slots__ = ("findings", "file_records", "summary")

    def __init__(self, findings, file_records, summary):
        self.findings = list(findings)
        self.file_records = list(file_records)
        self.summary = summary

    def to_dict(self):
        return {
            "findings": [_copy_value(item) for item in self.findings],
            "file_records": [_copy_value(item) for item in self.file_records],
            "summary": _copy_value(self.summary),
        }
