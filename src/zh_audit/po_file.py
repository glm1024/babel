from __future__ import absolute_import

from collections import Counter
from pathlib import Path


class PoPart(object):
    def render(self, default_newline):
        raise NotImplementedError


class RawPoPart(PoPart):
    def __init__(self, lines):
        self.lines = list(lines)

    def render(self, default_newline):
        return "".join(self.lines)


class PoStringFieldPart(PoPart):
    def __init__(self, keyword, lines, value, newline):
        self.keyword = str(keyword)
        self.lines = list(lines)
        self.value = str(value or "")
        self.newline = newline
        self.updated_value = None

    def render(self, default_newline):
        if self.updated_value is None:
            return "".join(self.lines)
        newline = self.newline or default_newline or "\n"
        return _render_po_string_field(self.keyword, self.updated_value, newline)


class PoBlock(object):
    def __init__(self, block_id, parts, separator="", default_newline="\n"):
        self.block_id = str(block_id)
        self.parts = list(parts)
        self.separator = str(separator or "")
        self.default_newline = default_newline or "\n"
        self._analyze()

    def is_entry(self):
        return self.msgid_part is not None

    def is_supported_translation_entry(self):
        return self.is_entry() and not self.is_header and not self.unsupported_reason

    def msgid_text(self):
        return self.msgid_part.value if self.msgid_part is not None else ""

    def msgstr_text(self):
        return self.msgstr_part.value if self.msgstr_part is not None else ""

    def msgctxt_text(self):
        return self.msgctxt_part.value if self.msgctxt_part is not None else ""

    def set_msgstr_value(self, value):
        if self.msgstr_part is None:
            raise ValueError("PO entry does not contain msgstr: {}".format(self.block_id))
        text = str(value or "")
        self.msgstr_part.updated_value = text
        self.msgstr_part.value = text

    def render(self):
        return "".join(part.render(self.default_newline) for part in self.parts) + self.separator

    def _analyze(self):
        self.msgctxt_part = None
        self.msgid_part = None
        self.msgstr_part = None
        self.references = []
        self.flags = []
        self.has_plural = False
        self.has_obsolete = False
        self.has_unknown_raw = False
        for part in self.parts:
            if isinstance(part, RawPoPart):
                for line in part.lines:
                    stripped = line.lstrip()
                    if stripped.startswith("#~"):
                        self.has_obsolete = True
                    elif stripped.startswith("#:"):
                        payload = stripped[2:].strip()
                        if payload:
                            self.references.extend(payload.split())
                    elif stripped.startswith("#,"):
                        payload = stripped[2:].strip()
                        if payload:
                            self.flags.extend([item.strip() for item in payload.split(",") if item.strip()])
                    elif stripped.startswith("#") or not stripped.strip():
                        continue
                    else:
                        self.has_unknown_raw = True
            elif isinstance(part, PoStringFieldPart):
                if part.keyword == "msgctxt":
                    if self.msgctxt_part is None:
                        self.msgctxt_part = part
                    else:
                        self.has_unknown_raw = True
                elif part.keyword == "msgid":
                    if self.msgid_part is None:
                        self.msgid_part = part
                    else:
                        self.has_unknown_raw = True
                elif part.keyword == "msgstr":
                    if self.msgstr_part is None:
                        self.msgstr_part = part
                    else:
                        self.has_unknown_raw = True
                elif part.keyword == "msgid_plural" or part.keyword.startswith("msgstr["):
                    self.has_plural = True
                else:
                    self.has_unknown_raw = True
            else:
                self.has_unknown_raw = True

        self.is_header = self.msgid_part is not None and self.msgid_part.value == ""
        self.unsupported_reason = self._build_unsupported_reason()

    def _build_unsupported_reason(self):
        if self.msgid_part is None:
            return ""
        if self.has_obsolete:
            return "obsolete 条目暂不支持。"
        if self.has_plural:
            return "plural 条目暂不支持。"
        if self.msgstr_part is None:
            return "缺少 msgstr。"
        if self.has_unknown_raw:
            return "条目结构暂不支持。"
        return ""


class PoDocument(object):
    def __init__(self, path, blocks, leading_text="", default_newline="\n"):
        self.path = Path(path)
        self.blocks = list(blocks)
        self.leading_text = str(leading_text or "")
        self.default_newline = default_newline or "\n"
        self._rebuild_index()

    def entries(self):
        return [block for block in self.blocks if block.is_entry()]

    def find_entry(self, block_id):
        return self._entries_by_id.get(str(block_id))

    def render(self):
        return self.leading_text + "".join(block.render() for block in self.blocks)

    def write(self, path=None):
        target = Path(path) if path is not None else self.path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as handle:
            handle.write(self.render())

    def _rebuild_index(self):
        self._entries_by_id = {}
        for block in self.blocks:
            if block.is_entry():
                self._entries_by_id[block.block_id] = block


def load_po_document(path):
    document_path = Path(path)
    with document_path.open(encoding="utf-8-sig", newline="") as handle:
        text = handle.read()
    lines = text.splitlines(True)
    newline_counter = Counter()
    for line in lines:
        newline = _line_newline(line)
        if newline:
            newline_counter[newline] += 1
    default_newline = newline_counter.most_common(1)[0][0] if newline_counter else "\n"

    leading_lines = []
    index = 0
    while index < len(lines) and _is_blank_line(lines[index]):
        leading_lines.append(lines[index])
        index += 1

    blocks = []
    block_number = 0
    while index < len(lines):
        block_lines = []
        while index < len(lines) and not _is_blank_line(lines[index]):
            block_lines.append(lines[index])
            index += 1
        separator_lines = []
        while index < len(lines) and _is_blank_line(lines[index]):
            separator_lines.append(lines[index])
            index += 1
        block_number += 1
        blocks.append(
            PoBlock(
                block_id="po-block-{}".format(block_number),
                parts=_parse_block_parts(block_lines, default_newline),
                separator="".join(separator_lines),
                default_newline=default_newline,
            )
        )
    return PoDocument(
        path=document_path,
        blocks=blocks,
        leading_text="".join(leading_lines),
        default_newline=default_newline,
    )


def _parse_block_parts(lines, default_newline):
    parts = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.lstrip()
        if stripped.startswith("#"):
            comment_lines = [line]
            index += 1
            while index < len(lines) and lines[index].lstrip().startswith("#"):
                comment_lines.append(lines[index])
                index += 1
            parts.append(RawPoPart(comment_lines))
            continue
        field = _parse_string_field(lines, index, default_newline)
        if field is None:
            parts.append(RawPoPart([line]))
            index += 1
            continue
        parts.append(field["part"])
        index = field["next_index"]
    return parts


def _parse_string_field(lines, index, default_newline):
    line = lines[index]
    stripped = line.lstrip()
    keywords = (
        "msgctxt",
        "msgid_plural",
        "msgid",
        "msgstr",
    )
    keyword = ""
    for candidate in keywords:
        if stripped.startswith(candidate):
            keyword = candidate
            break
    if not keyword and stripped.startswith("msgstr["):
        closing = stripped.find("]")
        if closing > len("msgstr["):
            keyword = stripped[: closing + 1]
    if not keyword:
        return None
    first_value = stripped[len(keyword) :].strip()
    if not first_value.startswith('"') or not first_value.endswith('"'):
        return None
    raw_lines = [line]
    decoded_fragments = [_decode_po_quoted_string(first_value)]
    next_index = index + 1
    while next_index < len(lines):
        continuation = lines[next_index].lstrip()
        if not continuation.startswith('"') or not continuation.rstrip("\r\n").endswith('"'):
            break
        raw_lines.append(lines[next_index])
        decoded_fragments.append(_decode_po_quoted_string(continuation.rstrip("\r\n")))
        next_index += 1
    newline = _line_newline(raw_lines[0]) or default_newline
    return {
        "part": PoStringFieldPart(
            keyword=keyword,
            lines=raw_lines,
            value="".join(decoded_fragments),
            newline=newline,
        ),
        "next_index": next_index,
    }


def _render_po_string_field(keyword, value, newline):
    text = str(value or "")
    if "\n" not in text:
        return "{} {}\n".format(keyword, _encode_po_quoted_string(text)).replace("\n", newline)
    chunks = text.split("\n")
    rendered = ["{} \"\"{}".format(keyword, newline)]
    for index, chunk in enumerate(chunks):
        suffix = "\n" if index < len(chunks) - 1 else ""
        rendered.append("{}{}".format(_encode_po_quoted_string(chunk + suffix), newline))
    return "".join(rendered)


def _decode_po_quoted_string(raw):
    value = str(raw or "").strip()
    if len(value) < 2 or not value.startswith('"') or not value.endswith('"'):
        return value
    inner = value[1:-1]
    result = []
    index = 0
    while index < len(inner):
        char = inner[index]
        if char != "\\" or index + 1 >= len(inner):
            result.append(char)
            index += 1
            continue
        index += 1
        escaped = inner[index]
        if escaped == "n":
            result.append("\n")
        elif escaped == "r":
            result.append("\r")
        elif escaped == "t":
            result.append("\t")
        elif escaped in ('"', "\\"):
            result.append(escaped)
        else:
            result.append(escaped)
        index += 1
    return "".join(result)


def _encode_po_quoted_string(value):
    escaped = []
    for char in str(value or ""):
        if char == "\\":
            escaped.append("\\\\")
        elif char == "\n":
            escaped.append("\\n")
        elif char == "\r":
            escaped.append("\\r")
        elif char == "\t":
            escaped.append("\\t")
        else:
            escaped.append(char)
    return '"{}"'.format("".join(escaped))


def _is_blank_line(raw_line):
    return not str(raw_line or "").strip()


def _line_newline(raw_line):
    line = str(raw_line or "")
    stripped = line.rstrip("\r\n")
    return line[len(stripped) :]
