import ast
import io
import re
import tokenize
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from zh_audit.models import RawFinding
from zh_audit.utils import (
    compact_snippet,
    contains_han,
    decode_unicode_escapes,
    file_role_from_path,
    guess_language,
    is_probable_comment_line,
    normalize_text,
    sha1_text,
)


STRING_SURFACE = "string_literal"
COMMENT_SURFACE = "comment"
TEXT_SURFACE = "text"
MARKUP_LANGUAGES = {"html", "xml", "vm"}
LOCAL_CONTEXT_WINDOW = 40
ASSIGNMENT_PATTERN = re.compile(r"([A-Za-z_][A-Za-z0-9_\.]{0,80})\s*[:=]\s*.+")
SYMBOL_PATTERNS = [
    re.compile(r"\b(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    re.compile(r"\bfunc\s+(?:\([^)]+\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\("),
    re.compile(
        r"^\s*(?:(?:public|private|protected|static|final|synchronized|abstract)\s+)*[A-Za-z_<>\[\], ?]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*(?:\{|$)"
    ),
    re.compile(r"\b(?:interface|enum|type)\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
]
JAVA_IMPORT_RE = re.compile(r"^\s*import\s+([A-Za-z_][A-Za-z0-9_$.]*(?:\.\*)?)\s*;", re.MULTILINE)
JAVA_ANNOTATION_RE = re.compile(r"@([A-Za-z_][A-Za-z0-9_$.]*)")
JAVA_SWAGGER_PACKAGE_PREFIXES = (
    "io.swagger.annotations",
    "com.wordnik.swagger.annotations",
    "io.swagger.v3.oas.annotations",
)
JAVA_SWAGGER_ANNOTATIONS = {
    "Api",
    "ApiIgnore",
    "ApiImplicitParam",
    "ApiImplicitParams",
    "ApiKeyAuthDefinition",
    "ApiModel",
    "ApiModelProperty",
    "ApiOperation",
    "ApiParam",
    "ApiResponse",
    "ApiResponses",
    "Authorization",
    "AuthorizationScope",
    "BasicAuthDefinition",
    "Callback",
    "Callbacks",
    "Components",
    "Contact",
    "Content",
    "DiscriminatorMapping",
    "Encoding",
    "Example",
    "ExampleObject",
    "ExampleProperty",
    "Extension",
    "ExtensionProperty",
    "ExternalDocs",
    "ExternalDocumentation",
    "Header",
    "Hidden",
    "Info",
    "License",
    "Link",
    "LinkParameter",
    "OAuth2Definition",
    "OAuthFlow",
    "OAuthFlows",
    "OAuthScope",
    "OpenAPIDefinition",
    "Operation",
    "Parameter",
    "Parameters",
    "RequestBody",
    "ResponseHeader",
    "Schema",
    "Scope",
    "SecurityDefinition",
    "SecurityRequirement",
    "SecurityRequirements",
    "SecurityScheme",
    "SecuritySchemes",
    "Server",
    "ServerVariable",
    "ServerVariables",
    "Servers",
    "SwaggerDefinition",
    "Tag",
    "Tags",
}


class Fragment(object):
    __slots__ = ("start", "end", "text", "surface_kind")

    def __init__(self, start, end, text, surface_kind):
        self.start = start
        self.end = end
        self.text = text
        self.surface_kind = surface_kind


def extract_file(repo, path, content, context_lines):
    language = guess_language(path)
    if language == "python":
        findings = list(_extract_python(repo, path, content, context_lines))
    else:
        findings = list(_extract_line_based(repo, path, content, context_lines, language))
    return _dedupe_findings(findings)


def _extract_python(repo, path, content, context_lines):
    lines = content.splitlines()
    relative_path = path.as_posix()
    file_role = file_role_from_path(relative_path)
    symbol_map = _python_symbol_map(content)

    for token in tokenize.generate_tokens(io.StringIO(content).readline):
        if token.type not in {tokenize.STRING, tokenize.COMMENT}:
            continue
        line_no, column = token.start
        end_column = token.end[1]
        line_text = lines[line_no - 1] if line_no - 1 < len(lines) else token.string
        local_context = _local_context(line_text, column, end_column)

        if token.type == tokenize.STRING:
            decoded = decode_unicode_escapes(token.string)
            if not contains_han(decoded):
                continue
            text = _literal_text(token.string)
            if not contains_han(text):
                continue
            yield _build_finding(
                repo=repo,
                relative_path=relative_path,
                language="python",
                line_no=line_no,
                column=column + 1,
                surface_kind=STRING_SURFACE,
                symbol=_nearest_symbol(symbol_map, line_no),
                raw_text=text,
                snippet=line_text,
                context_window=_context(lines, line_no, context_lines),
                file_role=file_role,
                candidate_roles=_candidate_roles(local_context, line_text, "python", file_role, STRING_SURFACE),
                metadata={"local_context": local_context},
            )
            continue

        decoded = decode_unicode_escapes(token.string)
        if not contains_han(decoded):
            continue
        yield _build_finding(
            repo=repo,
            relative_path=relative_path,
            language="python",
            line_no=line_no,
            column=column + 1,
            surface_kind=COMMENT_SURFACE,
            symbol=_nearest_symbol(symbol_map, line_no),
            raw_text=token.string,
            snippet=line_text,
            context_window=_context(lines, line_no, context_lines),
            file_role=file_role,
            candidate_roles=_candidate_roles(local_context, line_text, "python", file_role, COMMENT_SURFACE),
            metadata={"local_context": local_context},
        )


def _extract_line_based(repo, path, content, context_lines, language):
    lines = content.splitlines()
    relative_path = path.as_posix()
    file_role = file_role_from_path(relative_path)
    current_symbol = ""
    block_comment_state = None
    swagger_annotation_lines = _java_swagger_annotation_lines(content) if language == "java" else set()

    for index, line in enumerate(lines, start=1):
        symbol = _line_symbol(line)
        if symbol:
            current_symbol = symbol

        if language in MARKUP_LANGUAGES:
            fragments, block_comment_state = _markup_fragments(line, block_comment_state)
        else:
            fragments, block_comment_state = _code_fragments(line, block_comment_state, language)

        for fragment in fragments:
            text = fragment.text.strip()
            if not text:
                continue
            if not contains_han(decode_unicode_escapes(text)):
                continue
            local_context = _local_context(line, fragment.start, fragment.end)
            candidate_roles = _candidate_roles(local_context, line, language, file_role, fragment.surface_kind)
            if index in swagger_annotation_lines and "swagger_annotation" not in candidate_roles:
                candidate_roles.append("swagger_annotation")
            yield _build_finding(
                repo=repo,
                relative_path=relative_path,
                language=language,
                line_no=index,
                column=fragment.start + 1,
                surface_kind=fragment.surface_kind,
                symbol=current_symbol,
                raw_text=text,
                snippet=compact_snippet(line),
                context_window=_context(lines, index, context_lines),
                file_role=file_role,
                candidate_roles=candidate_roles,
                metadata={"local_context": local_context},
            )


def _markup_fragments(line, block_state):
    fragments = []
    sanitized = list(line)
    index = 0
    active_state = block_state

    while index < len(line):
        if active_state == "xml_comment":
            end = line.find("-->", index)
            if end == -1:
                _append_fragment(fragments, index, len(line), line[index:], COMMENT_SURFACE)
                _blank(sanitized, index, len(line))
                return fragments, "xml_comment"
            _append_fragment(fragments, index, end, line[index:end], COMMENT_SURFACE)
            _blank(sanitized, index, end + 3)
            index = end + 3
            active_state = None
            continue

        if line.startswith("<!--", index):
            end = line.find("-->", index + 4)
            if end == -1:
                _append_fragment(fragments, index + 4, len(line), line[index + 4 :], COMMENT_SURFACE)
                _blank(sanitized, index, len(line))
                return fragments, "xml_comment"
            _append_fragment(fragments, index + 4, end, line[index + 4 : end], COMMENT_SURFACE)
            _blank(sanitized, index, end + 3)
            index = end + 3
            continue

        if line[index] in {'"', "'"}:
            quote_end = _find_quote_end(line, index)
            value_end = quote_end if quote_end < len(line) else len(line)
            _append_fragment(fragments, index + 1, value_end, line[index + 1 : value_end], STRING_SURFACE)
            _blank(sanitized, index, min(len(line), quote_end + 1))
            index = min(len(line), quote_end + 1)
            continue

        index += 1

    masked_line = "".join(sanitized)
    for match in re.finditer(r">([^<]+)<|>([^<]+)$", masked_line):
        text = match.group(1) if match.group(1) is not None else match.group(2)
        if text is None:
            continue
        start = match.start(1) if match.group(1) is not None else match.start(2)
        _append_fragment(fragments, start, start + len(text), text, TEXT_SURFACE)

    fragments.extend(_loose_text_fragments(masked_line))
    return fragments, None


def _code_fragments(line, block_state, language):
    fragments = []
    sanitized = list(line)
    index = 0
    active_state = block_state

    while index < len(line):
        if active_state == "c_comment":
            end = line.find("*/", index)
            if end == -1:
                _append_fragment(fragments, index, len(line), line[index:], COMMENT_SURFACE)
                _blank(sanitized, index, len(line))
                return fragments, "c_comment"
            _append_fragment(fragments, index, end, line[index:end], COMMENT_SURFACE)
            _blank(sanitized, index, end + 2)
            index = end + 2
            active_state = None
            continue

        if line.startswith("/*", index):
            end = line.find("*/", index + 2)
            if end == -1:
                _append_fragment(fragments, index + 2, len(line), line[index + 2 :], COMMENT_SURFACE)
                _blank(sanitized, index, len(line))
                return fragments, "c_comment"
            _append_fragment(fragments, index + 2, end, line[index + 2 : end], COMMENT_SURFACE)
            _blank(sanitized, index, end + 2)
            index = end + 2
            continue

        if line.startswith("//", index):
            _append_fragment(fragments, index + 2, len(line), line[index + 2 :], COMMENT_SURFACE)
            _blank(sanitized, index, len(line))
            break

        if language == "sql" and line.startswith("--", index):
            _append_fragment(fragments, index + 2, len(line), line[index + 2 :], COMMENT_SURFACE)
            _blank(sanitized, index, len(line))
            break

        if language in {"shell", "yaml", "properties"} and line[index] == "#":
            _append_fragment(fragments, index + 1, len(line), line[index + 1 :], COMMENT_SURFACE)
            _blank(sanitized, index, len(line))
            break

        if line[index] in {'"', "'", "`"}:
            quote_end = _find_quote_end(line, index)
            value_end = quote_end if quote_end < len(line) else len(line)
            _append_fragment(fragments, index + 1, value_end, line[index + 1 : value_end], STRING_SURFACE)
            _blank(sanitized, index, min(len(line), quote_end + 1))
            index = min(len(line), quote_end + 1)
            continue

        index += 1

    fragments.extend(_loose_text_fragments("".join(sanitized)))
    return fragments, None


def _loose_text_fragments(line):
    fragments = []
    for match in re.finditer(r"[^\s<>{}\[\]()]+(?:\s+[^\s<>{}\[\]()]+)*", line):
        text = match.group(0)
        if contains_han(decode_unicode_escapes(text)):
            _append_fragment(fragments, match.start(), match.end(), text, TEXT_SURFACE)
    return fragments


def _append_fragment(fragments, start, end, text, surface_kind):
    value = text.strip()
    if not value:
        return
    fragments.append(Fragment(start=start, end=max(end, start + 1), text=value, surface_kind=surface_kind))


def _find_quote_end(line, start):
    quote = line[start]
    index = start + 1
    escaped = False
    while index < len(line):
        char = line[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == quote:
            return index
        index += 1
    return len(line)


def _blank(chars, start, end):
    for index in range(max(0, start), min(len(chars), end)):
        chars[index] = " "


def _dedupe_findings(findings):
    deduped = []
    seen = set()
    for finding in findings:
        key = (finding.path, finding.line, finding.column, finding.normalized_text, finding.surface_kind)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped


def _build_finding(
    repo,
    relative_path,
    language,
    line_no,
    column,
    surface_kind,
    symbol,
    raw_text,
    snippet,
    context_window,
    file_role,
    candidate_roles,
    metadata=None,
):
    normalized = normalize_text(raw_text)
    finding_id = sha1_text(f"{repo}|{relative_path}|{line_no}|{column}|{normalized}|{surface_kind}")[:16]
    return RawFinding(
        id=finding_id,
        project=repo,
        path=relative_path,
        lang=language,
        line=line_no,
        column=column,
        surface_kind=surface_kind,
        symbol=symbol,
        text=raw_text.strip(),
        normalized_text=normalized,
        snippet=compact_snippet(snippet),
        context_window=context_window,
        file_role=file_role,
        candidate_roles=candidate_roles,
        metadata=metadata or {},
    )


def _literal_text(raw):
    try:
        value = ast.literal_eval(raw)
    except Exception:
        value = raw
    if isinstance(value, str):
        return value
    return str(value)


def _python_symbol_map(content):
    try:
        root = ast.parse(content)
    except SyntaxError:
        return []
    mapping = []
    for node in ast.walk(root):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            mapping.append((node.lineno, node.name))
    return sorted(mapping, key=lambda item: item[0])


def _nearest_symbol(mapping, line_no):
    symbol = ""
    for symbol_line, name in mapping:
        if symbol_line > line_no:
            break
        symbol = name
    return symbol


def _context(lines, line_no, context_lines):
    start = max(1, line_no - context_lines)
    end = min(len(lines), line_no + context_lines)
    return "\n".join(f"{idx}: {lines[idx - 1]}" for idx in range(start, end + 1))


def _candidate_roles(local_context, line, language, file_role, surface_kind):
    roles = [file_role]
    lower = local_context.lower()
    if surface_kind == COMMENT_SURFACE or is_probable_comment_line(line, language) or "<!--" in line:
        roles.append("comment")
    if any(
        token in lower
        for token in (
            "logger.",
            "logger(",
            "log.",
            "log(",
            "logging.",
            "console.",
            "@log(",
            "system.out.",
            "system.err.",
            "printstacktrace(",
        )
    ):
        roles.append("log")
    if any(
        token in lower
        for token in ("ajaxresult.warn(", "ajaxresult.error(", "return error(", "return fail(", "return warn(", "throw ", "raise ", "panic(", "errors.new(", "fmt.errorf(")
    ):
        roles.append("error")
    if any(token in lower for token in ("message", "msg", "title", "label", "placeholder", "desc", "description", "tip", "help", "toast", "alert", "notice", "subtitle")):
        roles.append("user_visible")
    if ASSIGNMENT_PATTERN.search(local_context) or ASSIGNMENT_PATTERN.search(line):
        roles.append("assignment")
    return roles


def _local_context(line, start, end):
    anchor_end = max(end, start + 1)
    return line[max(0, start - LOCAL_CONTEXT_WINDOW) : min(len(line), anchor_end + LOCAL_CONTEXT_WINDOW)]


def _line_symbol(line):
    for pattern in SYMBOL_PATTERNS:
        match = pattern.search(line)
        if match:
            return match.group(1)
    return ""


def _java_swagger_annotation_lines(content):
    explicit_imports = {}
    wildcard_imports = set()
    for match in JAVA_IMPORT_RE.finditer(content):
        imported = match.group(1)
        if imported.endswith(".*"):
            package_name = imported[:-2]
            if _is_java_swagger_package(package_name):
                wildcard_imports.add(package_name)
            continue
        package_name, _, simple_name = imported.rpartition(".")
        if simple_name and _is_java_swagger_package(package_name):
            explicit_imports[simple_name] = imported

    lines = set()
    for match in JAVA_ANNOTATION_RE.finditer(content):
        annotation_name = match.group(1)
        if not _is_java_swagger_annotation(annotation_name, explicit_imports, wildcard_imports):
            continue
        start_line = _line_number_for_offset(content, match.start())
        end_line = _java_annotation_end_line(content, match.end(), start_line)
        for line_no in range(start_line, end_line + 1):
            lines.add(line_no)
    return lines


def _is_java_swagger_annotation(annotation_name, explicit_imports, wildcard_imports):
    if "." in annotation_name:
        package_name, _, simple_name = annotation_name.rpartition(".")
        return simple_name in JAVA_SWAGGER_ANNOTATIONS and _is_java_swagger_package(package_name)
    if annotation_name not in JAVA_SWAGGER_ANNOTATIONS:
        return False
    if annotation_name in explicit_imports:
        return True
    return bool(wildcard_imports)


def _is_java_swagger_package(package_name):
    for prefix in JAVA_SWAGGER_PACKAGE_PREFIXES:
        if package_name == prefix or package_name.startswith(prefix + "."):
            return True
    return False


def _line_number_for_offset(content, offset):
    return content.count("\n", 0, offset) + 1


def _java_annotation_end_line(content, annotation_end, start_line):
    index = annotation_end
    while index < len(content) and content[index].isspace():
        index += 1
    if index >= len(content) or content[index] != "(":
        return start_line

    depth = 0
    quote = ""
    escaped = False
    cursor = index
    while cursor < len(content):
        char = content[cursor]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
        else:
            if char in {'"', "'"}:
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return _line_number_for_offset(content, cursor)
        cursor += 1
    return _line_number_for_offset(content, len(content))
