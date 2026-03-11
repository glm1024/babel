from __future__ import absolute_import

from collections import Counter
from pathlib import Path


class PropertiesEntry(object):
    def __init__(self, kind, raw_line, line_number, key="", value="", before_value="", newline="\n"):
        self.kind = kind
        self.raw_line = raw_line
        self.line_number = int(line_number)
        self.key = key
        self.value = value
        self.before_value = before_value
        self.newline = newline

    def render(self):
        if self.kind != "property":
            return self.raw_line
        return "{}{}{}".format(self.before_value, self.value, self.newline)


class PropertiesDocument(object):
    def __init__(self, path, entries, default_newline="\n"):
        self.path = Path(path)
        self.entries = list(entries)
        self.default_newline = default_newline or "\n"
        self._rebuild_index()

    def property_entries(self):
        return [entry for entry in self.entries if entry.kind == "property"]

    def find(self, key):
        return self._first_by_key.get(key)

    def duplicate_keys(self):
        return [key for key, count in self._counts_by_key.items() if count > 1]

    def set_value(self, key, value, separator="="):
        entry = self.find(key)
        if entry is not None:
            entry.value = value
            return entry, False
        self._ensure_trailing_newline()
        before_value = "{}{}".format(key, separator)
        appended = PropertiesEntry(
            kind="property",
            raw_line="",
            line_number=len(self.entries) + 1,
            key=key,
            value=value,
            before_value=before_value,
            newline=self.default_newline,
        )
        self.entries.append(appended)
        self._rebuild_index()
        return appended, True

    def append_comment_once(self, comment_text):
        marker = comment_text.strip()
        for entry in self.entries:
            if entry.kind == "comment" and entry.raw_line.strip() == marker:
                return
        self._ensure_trailing_newline()
        comment_line = marker
        if not comment_line.startswith("#"):
            comment_line = "# {}".format(comment_line)
        self.entries.append(
            PropertiesEntry(
                kind="comment",
                raw_line="{}{}".format(comment_line, self.default_newline),
                line_number=len(self.entries) + 1,
            )
        )

    def render(self):
        return "".join(entry.render() for entry in self.entries)

    def write(self, path=None):
        target = Path(path) if path is not None else self.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.render(), encoding="utf-8")

    def _ensure_trailing_newline(self):
        if not self.entries:
            return
        last = self.entries[-1]
        if last.kind == "property" and not last.newline:
            last.newline = self.default_newline
        if last.kind != "property" and not last.raw_line.endswith(("\n", "\r")):
            last.raw_line = "{}{}".format(last.raw_line, self.default_newline)

    def _rebuild_index(self):
        self._first_by_key = {}
        self._counts_by_key = Counter()
        for entry in self.entries:
            if entry.kind != "property":
                continue
            self._counts_by_key[entry.key] += 1
            if entry.key not in self._first_by_key:
                self._first_by_key[entry.key] = entry


def load_properties_document(path):
    document_path = Path(path)
    with document_path.open(encoding="utf-8-sig", newline="") as handle:
        text = handle.read()
    entries = []
    newline_counter = Counter()
    for line_number, raw_line in enumerate(text.splitlines(True), 1):
        entry = _parse_line(raw_line, line_number)
        entries.append(entry)
        if entry.kind == "property":
            newline = entry.newline or ""
        else:
            newline = raw_line[len(raw_line.rstrip("\r\n")) :]
        if newline:
            newline_counter[newline] += 1
    if text and not entries:
        entries.append(PropertiesEntry(kind="raw", raw_line=text, line_number=1))
    default_newline = "\n"
    if newline_counter:
        default_newline = newline_counter.most_common(1)[0][0]
    return PropertiesDocument(path=document_path, entries=entries, default_newline=default_newline)


def _parse_line(raw_line, line_number):
    line = raw_line.rstrip("\r\n")
    newline = raw_line[len(line) :]
    stripped = line.lstrip()
    if not stripped:
        return PropertiesEntry(kind="blank", raw_line=raw_line, line_number=line_number)
    if stripped.startswith("#") or stripped.startswith("!"):
        return PropertiesEntry(kind="comment", raw_line=raw_line, line_number=line_number)

    separator_index = _find_separator_index(line)
    if separator_index < 0:
        return PropertiesEntry(kind="raw", raw_line=raw_line, line_number=line_number)

    key = line[:separator_index].strip()
    if not key:
        return PropertiesEntry(kind="raw", raw_line=raw_line, line_number=line_number)

    value_start = separator_index + 1
    while value_start < len(line) and line[value_start] in " \t\f":
        value_start += 1
    before_value = line[:value_start]
    value = line[value_start:]
    return PropertiesEntry(
        kind="property",
        raw_line=raw_line,
        line_number=line_number,
        key=key,
        value=value,
        before_value=before_value,
        newline=newline,
    )


def _find_separator_index(line):
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char in ("=", ":"):
            return index
    return -1
