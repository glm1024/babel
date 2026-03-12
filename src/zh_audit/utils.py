import fnmatch
import hashlib
import re
from pathlib import Path
from typing import List, Match, Tuple


HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
UNICODE_ESCAPE_RE = re.compile(r"(?:\\u[0-9a-fA-F]{4})+")
CONDITION_BRANCH_RE = re.compile(r"\b(?:else\s+if|if|while|switch|case|assert)\b")
LOGIC_STRING_METHOD_RE = re.compile(
    r"\b(?:contains|containsignorecase|equals|equalsignorecase|contentequals|regionmatches|startswith|startswithignorecase|endswith|endswithignorecase|matches|indexof|lastindexof|compareto|comparetoignorecase|includes|match|test|hasprefix|hassuffix|equalfold|replace|replaceall|replacefirst|split|remove|removestart|removeend|substringbefore|substringafter|substringbeforelast|substringafterlast)\s*\("
)
PLAIN_MUTATOR_METHOD_RE = re.compile(r"\.\s*(?:add|addall|append|push|insert|put|set)\s*\(")
CONDITION_OPERATOR_RE = re.compile(r"(?:===|!==|==|!=)")
RELATIONAL_LITERAL_COMPARE_RE = re.compile(
    r"(?:[A-Za-z0-9_\)\]\.]+\s*(?:>=|<=|>|<)\s*['\"`][^'\"`]+['\"`]|['\"`][^'\"`]+['\"`]\s*(?:>=|<=|>|<)\s*[A-Za-z0-9_\(\[]+)"
)
PYTHON_IN_RE = re.compile(r"\b(?:not\s+in|in)\b")
ASSERT_API_RE = re.compile(
    r"\b(?:assert|assertions|preconditions|validate|objects)\s*(?:\.\s*)?(?:assert[a-z0-9_]*|checkargument|checkstate|checknotnull|istrue|state|notnull|hastext|haslength|notempty|notblank|isinstanceof|assignable|requirenonnull)\s*\("
)
COMMENT_LINE_PREFIXES = ("#", "//", "--", ";", "*")
SQL_COMMENT_HINT_RE = re.compile(
    r"\b(?:select|insert|update|delete|from|where|join|left|right|inner|outer|group|order|having|distinct|nullif|case|when|then|else|end|union|limit|offset)\b",
    re.IGNORECASE,
)
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


def extract_hit_text(text):
    value = decode_unicode_escapes(str(text or ""))
    return "".join(HAN_RE.findall(value))


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


def is_i18n_messages_file(path_str):
    normalized = str(path_str).replace("\\", "/").lower()
    return "i18n/messages" in normalized or "i18n.messages" in normalized


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
    if find_sql_comment_start(line, language) >= 0:
        return True
    return False


def find_sql_comment_start(line, language=""):
    text = str(line or "")
    if not text:
        return -1
    language_name = str(language or "").lower()
    if language_name not in {"sql", "xml", "vm"} and not SQL_COMMENT_HINT_RE.search(text):
        return -1

    quote = ""
    escaped = False
    index = 0
    while index < len(text) - 1:
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            index += 1
            continue

        if char in {'"', "'", "`"}:
            quote = char
            index += 1
            continue

        if text.startswith("--", index):
            prev = text[index - 1] if index > 0 else ""
            next_char = text[index + 2] if index + 2 < len(text) else ""
            if (index == 0 or prev.isspace() or prev in "(),") and next_char != "-":
                return index
        index += 1

    return -1


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


def looks_like_condition_expression_literal(snippet, context="", language="", extra_context=""):
    snippet_text = decode_unicode_escapes(str(snippet or ""))
    context_text = decode_unicode_escapes(str(context or ""))
    extra_text = decode_unicode_escapes(str(extra_context or ""))

    snippet_lower = snippet_text.lower()
    context_lower = context_text.lower()
    extra_lower = extra_text.lower()
    nearby_lower = "{} {}".format(snippet_lower, context_lower).strip()
    extended_lower = "{} {}".format(nearby_lower, extra_lower).strip()

    if not extended_lower:
        return False
    if snippet_lower.lstrip().startswith("case ") and ":" in snippet_lower:
        return True
    if "switch" in snippet_lower:
        return True
    if LOGIC_STRING_METHOD_RE.search(nearby_lower):
        return True
    if _looks_like_plain_mutator_statement(snippet_text):
        return False

    has_branch = bool(CONDITION_BRANCH_RE.search(nearby_lower) or CONDITION_BRANCH_RE.search(extra_lower))
    if not has_branch and not ("?" in extended_lower and ":" in extended_lower):
        return False

    if CONDITION_OPERATOR_RE.search(context_lower):
        return True
    if RELATIONAL_LITERAL_COMPARE_RE.search(extended_lower):
        return True
    if str(language or "").lower() == "python" and PYTHON_IN_RE.search(context_lower):
        return True
    return False


def looks_like_assert_api_literal(snippet, context="", extra_context=""):
    snippet_text = decode_unicode_escapes(str(snippet or ""))
    context_text = decode_unicode_escapes(str(context or ""))
    extra_text = decode_unicode_escapes(str(extra_context or ""))
    nearby_lower = "{} {}".format(snippet_text.lower(), context_text.lower()).strip()
    if not nearby_lower:
        return False
    if ASSERT_API_RE.search(nearby_lower):
        return True
    if _looks_like_plain_mutator_statement(snippet_text):
        return False

    stripped = snippet_text.strip()
    looks_like_argument_continuation = stripped.startswith(('"', "'", "`")) or stripped.endswith(",")
    if not looks_like_argument_continuation or not extra_text:
        return False
    return bool(ASSERT_API_RE.search("{} {}".format(nearby_lower, extra_text.lower()).strip()))


def _looks_like_plain_mutator_statement(snippet):
    snippet_text = decode_unicode_escapes(str(snippet or ""))
    snippet_lower = snippet_text.strip().lower()
    if not snippet_lower:
        return False
    return bool(PLAIN_MUTATOR_METHOD_RE.search(snippet_lower))
