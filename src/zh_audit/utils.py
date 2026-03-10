import fnmatch
import hashlib
import re
from pathlib import Path
from typing import List, Match, Tuple


HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
UNICODE_ESCAPE_RE = re.compile(r"(?:\\u[0-9a-fA-F]{4})+")
COMMENT_LINE_PREFIXES = ("#", "//", "--", ";", "*")
SOURCE_CODE_EXTENSIONS = {
    ".java",
    ".go",
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".vue",
    ".kt",
    ".groovy",
    ".scala",
}

TEXT_EXTENSIONS = {
    ".java",
    ".go",
    ".py",
    ".yml",
    ".yaml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".env",
    ".properties",
    ".html",
    ".htm",
    ".md",
    ".markdown",
    ".txt",
    ".sql",
    ".sh",
    ".bash",
    ".zsh",
    ".xml",
    ".csv",
    ".tsv",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".vue",
}

BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".jar",
    ".war",
    ".gz",
    ".tar",
    ".tgz",
    ".mp3",
    ".mp4",
    ".mov",
    ".avi",
    ".class",
    ".so",
    ".dylib",
    ".exe",
}

NAMED_KEEP_FILE_NAMES = {
    "jenkinsfile",
    "jenkinsfile.slim",
    "jekinsfile",
    "jekinsfile.slim",
    "jekinsfiles.slim",
}


def sha1_text(value):
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def contains_han(text):
    return bool(HAN_RE.search(text))


def decode_unicode_escapes(text):
    def repl(match):
        raw = match.group(0)
        try:
            return raw.encode("ascii").decode("unicode_escape")
        except UnicodeDecodeError:
            return raw

    return UNICODE_ESCAPE_RE.sub(repl, text)


def normalize_text(text):
    value = decode_unicode_escapes(text)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def sniff_text_file(path, max_size_bytes):
    try:
        stat = path.stat()
    except OSError:
        return False, "stat_error"
    if stat.st_size > max_size_bytes:
        return False, "too_large"

    suffix = path.suffix.lower()
    if suffix in BINARY_EXTENSIONS:
        return False, "binary_extension"
    if suffix in TEXT_EXTENSIONS:
        return True, ""

    try:
        with path.open("rb") as handle:
            chunk = handle.read(4096)
    except OSError:
        return False, "read_error"

    if b"\x00" in chunk:
        return False, "binary_content"
    return True, ""


def _suffix_name(suffix):
    if suffix.startswith("."):
        return suffix[1:]
    return suffix or "text"


def guess_language(path):
    suffix = path.suffix.lower()
    mapping = {
        ".java": "java",
        ".go": "go",
        ".py": "python",
        ".js": "js",
        ".css": "css",
        ".vm": "vm",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".json": "json",
        ".toml": "toml",
        ".properties": "properties",
        ".html": "html",
        ".htm": "html",
        ".sql": "sql",
        ".md": "markdown",
        ".txt": "text",
        ".sh": "shell",
        ".bash": "shell",
        ".zsh": "shell",
        ".bat": "shell",
        ".xml": "xml",
    }
    return mapping.get(suffix, _suffix_name(suffix))


def is_named_keep_file(path_str):
    normalized = str(path_str).replace("\\", "/")
    file_name = normalized.rsplit("/", 1)[-1].lower()
    return file_name in NAMED_KEEP_FILE_NAMES


def file_role_from_path(path_str):
    lower = path_str.lower().replace("\\", "/")
    parts = [part for part in lower.split("/") if part]
    suffix = Path(lower).suffix.lower()
    if any(
        part in {"test", "tests", "__tests__", "fixture", "fixtures", "mock", "mocks", "sample", "samples", "demo", "demos"}
        for part in parts
    ):
        return "test_or_sample"
    if any(part in {"docs", "doc", "wiki"} for part in parts) or "readme" in lower:
        return "documentation"
    if any(part in {"templates", "views", "webapp", "pages"} for part in parts):
        return "template"
    if any(part in {"config", "configs", ".github", "deploy", "helm"} for part in parts) and suffix not in SOURCE_CODE_EXTENSIONS:
        return "config"
    return "source"


def is_probable_comment_line(line, language):
    stripped = line.strip()
    if not stripped:
        return False
    if language in {"python", "shell", "yaml", "properties"} and stripped.startswith("#"):
        return True
    if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*") or stripped.startswith("--"):
        return True
    if language in {"html", "xml", "vm"} and stripped.startswith("<!--"):
        return True
    return False


def compact_snippet(line):
    return line.strip().replace("\t", " ")


def matches_any_glob(path_str, patterns):
    normalized = path_str.replace("\\", "/")
    for pattern in patterns:
        candidates = [pattern]
        if pattern.startswith("**/"):
            candidates.append(pattern[3:])
        for candidate in candidates:
            if fnmatch.fnmatch(normalized, candidate) or Path(normalized).match(candidate):
                return True
    return False
