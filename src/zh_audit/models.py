from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CATEGORY_USER_VISIBLE_COPY = "USER_VISIBLE_COPY"
CATEGORY_ERROR_VALIDATION_MESSAGE = "ERROR_VALIDATION_MESSAGE"
CATEGORY_LOG_AUDIT_DEBUG = "LOG_AUDIT_DEBUG"
CATEGORY_COMMENT_DOCUMENTATION = "COMMENT_DOCUMENTATION"
CATEGORY_TEST_SAMPLE_FIXTURE = "TEST_SAMPLE_FIXTURE"
CATEGORY_CONFIG_METADATA = "CONFIG_METADATA"
CATEGORY_PROTOCOL_OR_PERSISTED_LITERAL = "PROTOCOL_OR_PERSISTED_LITERAL"
CATEGORY_UNKNOWN = "UNKNOWN"

CATEGORY_ORDER = [
    CATEGORY_USER_VISIBLE_COPY,
    CATEGORY_ERROR_VALIDATION_MESSAGE,
    CATEGORY_LOG_AUDIT_DEBUG,
    CATEGORY_COMMENT_DOCUMENTATION,
    CATEGORY_TEST_SAMPLE_FIXTURE,
    CATEGORY_CONFIG_METADATA,
    CATEGORY_PROTOCOL_OR_PERSISTED_LITERAL,
    CATEGORY_UNKNOWN,
]

DEFAULT_EXCLUDE_GLOBS = [
    "**/target/**",
    "**/node_modules/**",
    "**/vendor/**",
    "**/webjars/**",
    "**/static/ajax/libs/**",
]


@dataclass(slots=True)
class RepoSpec:
    path: Path

    @property
    def name(self) -> str:
        return self.path.name or str(self.path)


@dataclass(slots=True)
class ScanSettings:
    max_file_size_bytes: int = 5 * 1024 * 1024
    context_lines: int = 1
    exclude_globs: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDE_GLOBS))


@dataclass(slots=True)
class FileRecord:
    repo: str
    path: Path
    relative_path: str
    eligible: bool
    scanned: bool
    skip_reason: str = ""
    skip_detail: str = ""
    encoding: str = ""
    lang: str = ""
    size_bytes: int = 0


@dataclass(slots=True)
class RawFinding:
    id: str
    project: str
    path: str
    lang: str
    line: int
    column: int
    surface_kind: str
    symbol: str
    text: str
    normalized_text: str
    snippet: str
    context_window: str
    file_role: str
    candidate_roles: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ClassifiedFinding:
    id: str
    project: str
    path: str
    lang: str
    line: int
    column: int
    surface_kind: str
    symbol: str
    text: str
    normalized_text: str
    snippet: str
    category: str
    action: str
    confidence: float
    high_risk: bool
    end_user_visible: bool
    reason: str
    file_role: str
    candidate_roles: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RunArtifacts:
    findings: list[ClassifiedFinding]
    file_records: list[FileRecord]
    summary: dict[str, Any]
