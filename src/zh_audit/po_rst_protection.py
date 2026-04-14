from __future__ import absolute_import

import json
import re

from zh_audit.utils import contains_han

DIRECTIVE_WITH_ARGUMENT_PATTERN = re.compile(
    r"(?m)^(?P<indent>[ \t]*)\.\.\s+(?P<name>[A-Za-z0-9_-]+)::(?P<spacing>[ \t]*)(?P<argument>[^\r\n]*)"
)
EXPLICIT_MARKUP_LINE_PATTERN = re.compile(r"(?m)^[ \t]*\.\.\s+\S[^\r\n]*")
ROLE_PATTERN = re.compile(r":(?P<role>[A-Za-z0-9_-]+):`(?P<body>[^`\r\n]+)`")
INLINE_LINK_PATTERN = re.compile(r"`(?P<label>[^`<>]+?)\s*<(?P<target>[^`<>]+)>`_")
REFERENCE_PATTERN = re.compile(r"`(?P<label>[^`\r\n<>]+?)`(?P<suffix>__|_)")
FOOTNOTE_REFERENCE_PATTERN = re.compile(r"\[(?P<label>[^\]\r\n]+?)\](?P<suffix>__|_)")
SUBSTITUTION_PATTERN = re.compile(r"\|[^|\r\n]+\|")
INLINE_LITERAL_PATTERN = re.compile(r"``[^`\r\n]+``")
STRONG_PATTERN = re.compile(r"(?<!\\)\*\*(?P<body>[^*\r\n]+?)\*\*")
EMPHASIS_PATTERN = re.compile(r"(?<![\w\\*])\*(?P<body>[^*\r\n]+?)\*(?![\w*])")
INTERPRETED_TEXT_PATTERN = re.compile(r"`(?P<body>[^`\r\n]+?)`")
UNHANDLED_RST_PATTERN = re.compile(r"`|:[A-Za-z0-9_-]+:|\.\.\s+\S")
TRANSLATABLE_SLOT_TYPES = {
    "text",
    "role_label",
    "link_label",
    "reference_label",
    "strong_text",
    "emphasis_text",
    "interpreted_text",
    "directive_argument",
}
OPEN_QUOTE_CHARS = set(['"', "'", "“", "‘"])
CLOSE_QUOTE_CHARS = set(['"', "'", "”", "’"])
OPEN_BRACKET_CHARS = set(["(", "[", "{", "<", "（", "【", "｛", "〈", "《"])
CLOSE_BRACKET_CHARS = set([")", "]", "}", ">", "）", "】", "｝", "〉", "》"])


def protect_rst_text(text):
    source = str(text or "")
    slots = []
    translatable_slots = []
    index = 0
    slot_index = 0
    while index < len(source):
        match = _next_markup_match(source, index)
        if match is None:
            remaining = source[index:]
            if remaining:
                slot_index += 1
                slot = {
                    "slot_id": "slot_{}".format(slot_index),
                    "type": "text",
                    "source_text": remaining,
                }
                slots.append(slot)
                translatable_slots.append(dict(slot))
            break
        if match["start"] > index:
            slot_index += 1
            slot = {
                "slot_id": "slot_{}".format(slot_index),
                "type": "text",
                "source_text": source[index : match["start"]],
            }
            slots.append(slot)
            translatable_slots.append(dict(slot))
        matched_slots = match.get("slots")
        if matched_slots is None:
            matched_slots = [match["slot"]]
        for raw_slot in matched_slots:
            slot = dict(raw_slot)
            is_translatable = bool(slot.get("translatable", slot.get("type") in TRANSLATABLE_SLOT_TYPES))
            if is_translatable and slot.get("type") != "text":
                slot_index += 1
                slot["slot_id"] = "slot_{}".format(slot_index)
            slots.append(slot)
            if is_translatable:
                translatable_slots.append(dict(slot))
        index = match["end"]

    if _contains_unhandled_rst(source):
        return {
            "supported": False,
            "reason": "包含暂不支持的 rst 语法。",
            "source_text": source,
            "slots": slots,
            "translatable_slots": translatable_slots,
            "summary": _summarize_slots(slots),
        }
    return {
        "supported": True,
        "reason": "",
        "source_text": source,
        "slots": slots,
        "translatable_slots": translatable_slots,
        "summary": _summarize_slots(slots),
    }


def compose_protected_text(protected, slot_translations):
    translations = dict(slot_translations or {})
    rendered = []
    for slot in protected.get("slots", []):
        slot_type = slot.get("type")
        if slot_type == "text":
            rendered.append(str(translations.get(slot["slot_id"], slot.get("source_text", ""))))
        elif slot_type == "literal":
            rendered.append(slot.get("raw", ""))
        elif slot_type == "role_label":
            label = str(translations.get(slot["slot_id"], slot.get("source_text", "")))
            if slot.get("has_target", False):
                rendered.append(":{}:`{}<{}>`".format(slot.get("role", ""), label, slot.get("target", "")))
            else:
                rendered.append(":{}:`{}`".format(slot.get("role", ""), label))
        elif slot_type == "link_label":
            label = str(translations.get(slot["slot_id"], slot.get("source_text", "")))
            rendered.append("`{} <{}>`_".format(label, slot.get("target", "")))
        elif slot_type == "reference_label":
            label = str(translations.get(slot["slot_id"], slot.get("source_text", "")))
            rendered.append("`{}`{}".format(label, slot.get("suffix", "_")))
        elif slot_type == "strong_text":
            rendered.append("**{}**".format(str(translations.get(slot["slot_id"], slot.get("source_text", "")))))
        elif slot_type == "emphasis_text":
            rendered.append("*{}*".format(str(translations.get(slot["slot_id"], slot.get("source_text", "")))))
        elif slot_type == "directive_prefix":
            rendered.append(slot.get("raw", ""))
        elif slot_type == "directive_argument":
            if slot.get("translatable", False):
                rendered.append(str(translations.get(slot["slot_id"], slot.get("source_text", ""))))
            else:
                rendered.append(slot.get("source_text", ""))
        elif slot_type == "inline_literal":
            rendered.append(slot.get("raw", ""))
        elif slot_type == "interpreted_text":
            if slot.get("translatable", False):
                rendered.append("`{}`".format(str(translations.get(slot["slot_id"], slot.get("source_text", "")))))
            else:
                rendered.append(slot.get("raw", ""))
        elif slot_type == "footnote_reference":
            rendered.append(slot.get("raw", ""))
        elif slot_type == "directive_line":
            rendered.append(slot.get("raw", ""))
        else:
            rendered.append(slot.get("raw", slot.get("source_text", "")))
    return "".join(rendered)


def validate_protected_candidate(source_protected, candidate_text):
    if not source_protected.get("supported", False):
        return source_protected.get("reason", "rst 结构暂不支持。")
    candidate = protect_rst_text(candidate_text)
    if not candidate.get("supported", False):
        return candidate.get("reason", "候选 rst 结构暂不支持。")
    source_slots = _structural_slots(source_protected.get("slots", []))
    candidate_slots = _structural_slots(candidate.get("slots", []))
    if len(source_slots) != len(candidate_slots):
        return "候选改变了 rst 槽位数量"
    for source_slot, candidate_slot in zip(source_slots, candidate_slots):
        if source_slot.get("type") != candidate_slot.get("type"):
            return "候选改变了 rst 槽位顺序"
        slot_type = source_slot.get("type")
        if slot_type == "literal" and source_slot.get("raw", "") != candidate_slot.get("raw", ""):
            return "候选未保留 rst 替换标记"
        if slot_type == "inline_literal" and source_slot.get("raw", "") != candidate_slot.get("raw", ""):
            return "候选未保留 rst 行内字面量"
        if slot_type == "interpreted_text" and not source_slot.get("translatable", False) and source_slot.get("raw", "") != candidate_slot.get("raw", ""):
            return "候选未保留 rst 解释文本"
        if slot_type == "footnote_reference" and source_slot.get("raw", "") != candidate_slot.get("raw", ""):
            return "候选改动了 rst 脚注引用"
        if slot_type == "directive_prefix" and source_slot.get("raw", "") != candidate_slot.get("raw", ""):
            return "候选改动了 rst 指令前缀"
        if slot_type == "directive_argument" and not source_slot.get("translatable", False):
            if source_slot.get("source_text", "") != candidate_slot.get("source_text", ""):
                return "候选改动了 rst 指令参数"
        if slot_type == "directive_line" and source_slot.get("raw", "") != candidate_slot.get("raw", ""):
            return "候选改动了 rst 指令行"
        if slot_type == "role_label":
            if source_slot.get("role", "") != candidate_slot.get("role", ""):
                return "候选改动了 rst role 名称"
            if source_slot.get("target", "") != candidate_slot.get("target", ""):
                return "候选改动了 rst role target"
        if slot_type == "link_label" and source_slot.get("target", "") != candidate_slot.get("target", ""):
            return "候选改动了 rst 链接 target"
        if slot_type == "reference_label" and source_slot.get("suffix", "") != candidate_slot.get("suffix", ""):
            return "候选改动了 rst 引用后缀"
        if slot_type in {"literal", "inline_literal"}:
            if not _preserves_literal_boundaries(source_slot, candidate_slot):
                return "候选把受保护 rst 标记并入了相邻文本"
    return ""


def _structural_slots(slots):
    structural = []
    raw_slots = list(slots or [])
    for index, slot in enumerate(raw_slots):
        if slot.get("type") == "text":
            continue
        item = dict(slot)
        item["previous_text"] = _adjacent_text_slot(raw_slots, index, -1)
        item["next_text"] = _adjacent_text_slot(raw_slots, index, 1)
        structural.append(item)
    return structural


def _adjacent_text_slot(slots, index, direction):
    current = int(index) + int(direction)
    while 0 <= current < len(slots):
        slot = slots[current]
        if slot.get("type") == "text":
            return str(slot.get("source_text", "") or "")
        if slot.get("type") is not None:
            return ""
        current += int(direction)
    return ""


def _preserves_literal_boundaries(source_slot, candidate_slot):
    required_before = _boundary_requirement_before(source_slot.get("previous_text", ""))
    required_after = _boundary_requirement_after(source_slot.get("next_text", ""))
    if required_before and _boundary_requirement_before(candidate_slot.get("previous_text", "")) != required_before:
        return False
    if required_after and _boundary_requirement_after(candidate_slot.get("next_text", "")) != required_after:
        return False
    return True


def _boundary_requirement_before(text):
    for char in reversed(str(text or "")):
        if char.isspace():
            continue
        if char in OPEN_QUOTE_CHARS:
            return "quote"
        if char in OPEN_BRACKET_CHARS:
            return "bracket"
        return ""
    return ""


def _boundary_requirement_after(text):
    for char in str(text or ""):
        if char.isspace():
            continue
        if char in CLOSE_QUOTE_CHARS:
            return "quote"
        if char in CLOSE_BRACKET_CHARS:
            return "bracket"
        return ""
    return ""


def build_slot_translation_map(raw_slot_translations):
    normalized_payload = build_slot_translation_payload(raw_slot_translations)
    return {
        slot_id: item.get("translation", "")
        for slot_id, item in normalized_payload.items()
    }


def extract_slot_translation_payload_from_text(text):
    fragment = _extract_json_field_fragment(text, "slot_translations")
    if not fragment:
        return {}
    try:
        parsed = json.loads(_normalize_json_fragment(fragment))
    except ValueError:
        return {}
    return build_slot_translation_payload(parsed)


def build_slot_translation_payload(raw_slot_translations):
    if isinstance(raw_slot_translations, dict):
        normalized = {}
        for key, value in raw_slot_translations.items():
            slot_id = str(key or "")
            if not slot_id:
                continue
            if isinstance(value, dict):
                translation = str(value.get("translation", value.get("translated_text", "")) or "")
                frontend_ui_context = _coerce_bool(value.get("frontend_ui_context", False))
            else:
                translation = str(value or "")
                frontend_ui_context = False
            normalized[slot_id] = {
                "translation": translation,
                "frontend_ui_context": frontend_ui_context,
            }
        return normalized
    normalized = {}
    if isinstance(raw_slot_translations, list):
        for item in raw_slot_translations:
            if not isinstance(item, dict):
                continue
            slot_id = str(item.get("slot_id", "") or "")
            if not slot_id:
                continue
            normalized[slot_id] = {
                "translation": str(item.get("translation", item.get("translated_text", "")) or ""),
                "frontend_ui_context": _coerce_bool(item.get("frontend_ui_context", False)),
            }
    return normalized


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in ("1", "true", "yes", "y", "on")


def _extract_json_field_fragment(text, field_name):
    value = str(text or "")
    patterns = [
        re.compile(r'"{}"\s*:\s*'.format(re.escape(field_name))),
        re.compile(r"'{}'\s*:\s*".format(re.escape(field_name))),
    ]
    for pattern in patterns:
        match = pattern.search(value)
        if not match:
            continue
        index = _skip_whitespace(value, match.end())
        if index >= len(value) or value[index] not in "[{":
            continue
        return _extract_balanced_json_fragment(value, index)
    return ""


def _extract_balanced_json_fragment(text, start_index):
    value = str(text or "")
    if start_index < 0 or start_index >= len(value):
        return ""
    opening = value[start_index]
    closing = "]" if opening == "[" else "}"
    depth = 0
    in_string = False
    escape_next = False
    for index in range(start_index, len(value)):
        char = value[index]
        if in_string:
            if escape_next:
                escape_next = False
                continue
            if char == "\\":
                escape_next = True
                continue
            if char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == opening:
            depth += 1
            continue
        if char == closing:
            depth -= 1
            if depth == 0:
                return value[start_index : index + 1]
    return ""


def _normalize_json_fragment(text):
    value = str(text or "").strip()
    if not value:
        return ""
    value = value.translate(
        str.maketrans(
            {
                "\u2018": "'",
                "\u2019": "'",
                "\u201a": "'",
                "\u201b": "'",
                "\u201c": '"',
                "\u201d": '"',
                "\u201e": '"',
                "\u201f": '"',
                "\u300c": '"',
                "\u300d": '"',
                "\u300e": '"',
                "\u300f": '"',
                "\uff02": '"',
                "\uff07": "'",
            }
        )
    )
    value = _escape_inner_quotes_in_json_fragment(value)
    value = re.sub(r",(\s*[}\]])", r"\1", value)
    return value


def _escape_inner_quotes_in_json_fragment(text):
    value = str(text or "")
    if not value or '"' not in value:
        return value
    result = []
    stack = []
    in_string = False
    escape_next = False
    string_role = "value"
    for index, char in enumerate(value):
        if in_string:
            if escape_next:
                result.append(char)
                escape_next = False
                continue
            if char == "\\":
                result.append(char)
                escape_next = True
                continue
            if char == '"':
                next_char = _next_non_space_char(value, index + 1)
                if _is_valid_fragment_string_terminator(string_role, next_char):
                    result.append(char)
                    in_string = False
                    _mark_fragment_container_after_string(stack, string_role)
                else:
                    result.append('\\"')
                continue
            result.append(char)
            continue

        result.append(char)
        if char == '"':
            in_string = True
            escape_next = False
            string_role = _current_fragment_string_role(stack)
            continue
        if char.isspace():
            continue
        if char == "{":
            stack.append({"type": "object", "expect": "key_or_end"})
            continue
        if char == "[":
            stack.append({"type": "array", "expect": "value_or_end"})
            continue
        if char == ":":
            if stack and stack[-1]["type"] == "object":
                stack[-1]["expect"] = "value"
            continue
        if char == ",":
            if stack:
                stack[-1]["expect"] = "key" if stack[-1]["type"] == "object" else "value"
            continue
        if char == "}":
            if stack and stack[-1]["type"] == "object":
                stack.pop()
                _mark_fragment_parent_after_value(stack)
            continue
        if char == "]":
            if stack and stack[-1]["type"] == "array":
                stack.pop()
                _mark_fragment_parent_after_value(stack)
            continue
    return "".join(result)


def _skip_whitespace(text, index):
    value = str(text or "")
    current = int(index)
    while current < len(value) and value[current].isspace():
        current += 1
    return current


def _next_non_space_char(text, start_index):
    value = str(text or "")
    index = int(start_index)
    while index < len(value):
        if not value[index].isspace():
            return value[index]
        index += 1
    return None


def _current_fragment_string_role(stack):
    if not stack:
        return "value"
    current = stack[-1]
    if current.get("type") == "object" and current.get("expect") in ("key", "key_or_end"):
        return "key"
    return "value"


def _is_valid_fragment_string_terminator(string_role, next_char):
    if string_role == "key":
        return next_char in (":", None)
    return next_char in (",", "}", "]", None)


def _mark_fragment_container_after_string(stack, string_role):
    if not stack:
        return
    current = stack[-1]
    if current.get("type") == "object":
        current["expect"] = "colon" if string_role == "key" else "after_value"
    elif current.get("type") == "array" and string_role == "value":
        current["expect"] = "after_value"


def _mark_fragment_parent_after_value(stack):
    if not stack:
        return
    stack[-1]["expect"] = "after_value"


def _summarize_slots(slots):
    if not slots:
        return "纯文本"
    parts = []
    for slot in slots:
        slot_type = slot.get("type")
        if slot_type == "text":
            parts.append("{}:{}".format(slot.get("slot_id", ""), _preview(slot.get("source_text", ""))))
        elif slot_type == "literal":
            parts.append("literal:{}".format(slot.get("raw", "")))
        elif slot_type == "inline_literal":
            parts.append("inline-literal:{}".format(slot.get("raw", "")))
        elif slot_type == "role_label":
            parts.append(
                "role:{}<{}>".format(slot.get("role", ""), slot.get("target", ""))
            )
        elif slot_type == "link_label":
            parts.append("link:<{}>".format(slot.get("target", "")))
        elif slot_type == "reference_label":
            parts.append("ref:{}".format(slot.get("suffix", "_")))
        elif slot_type == "strong_text":
            parts.append("strong:{}".format(_preview(slot.get("source_text", ""))))
        elif slot_type == "emphasis_text":
            parts.append("emphasis:{}".format(_preview(slot.get("source_text", ""))))
        elif slot_type == "directive_prefix":
            parts.append("directive-prefix:{}".format(slot.get("raw", "")))
        elif slot_type == "directive_argument":
            mode = "text" if slot.get("translatable", False) else "raw"
            parts.append("directive-arg:{}:{}".format(mode, _preview(slot.get("source_text", ""))))
        elif slot_type == "interpreted_text":
            mode = "text" if slot.get("translatable", False) else "raw"
            parts.append("interpreted:{}:{}".format(mode, _preview(slot.get("source_text", ""))))
        elif slot_type == "footnote_reference":
            parts.append("footnote:{}".format(slot.get("raw", "")))
        elif slot_type == "directive_line":
            parts.append("directive:{}".format(slot.get("raw", "")))
        else:
            parts.append(str(slot_type or "unknown"))
    return " | ".join(parts)


def _preview(value, limit=24):
    text = str(value or "")
    if len(text) <= limit:
        return text
    return "{}...".format(text[:limit])


def _next_markup_match(source, start):
    candidates = []
    for priority, (pattern_name, pattern) in enumerate((
        ("directive_with_argument", DIRECTIVE_WITH_ARGUMENT_PATTERN),
        ("directive_line", EXPLICIT_MARKUP_LINE_PATTERN),
        ("role", ROLE_PATTERN),
        ("link", INLINE_LINK_PATTERN),
        ("reference", REFERENCE_PATTERN),
        ("footnote_reference", FOOTNOTE_REFERENCE_PATTERN),
        ("literal", SUBSTITUTION_PATTERN),
        ("inline_literal", INLINE_LITERAL_PATTERN),
        ("strong", STRONG_PATTERN),
        ("emphasis", EMPHASIS_PATTERN),
        ("interpreted_text", INTERPRETED_TEXT_PATTERN),
    )):
        match = pattern.search(source, start)
        if match is None:
            continue
        candidates.append((match.start(), priority, -(match.end() - match.start()), pattern_name, match))
    if not candidates:
        return None
    candidates.sort()
    start_index, _, _, pattern_name, match = candidates[0]
    end_index = match.end()
    if pattern_name == "directive_with_argument":
        directive_name = str(match.group("name") or "")
        prefix = "{}.. {}::{}".format(
            str(match.group("indent") or ""),
            directive_name,
            str(match.group("spacing") or ""),
        )
        argument = str(match.group("argument") or "")
        slots = [{"type": "directive_prefix", "raw": prefix}]
        if argument:
            slots.append(
                {
                    "type": "directive_argument",
                    "directive_name": directive_name,
                    "source_text": argument,
                    "translatable": _directive_argument_translatable(directive_name, argument),
                }
            )
        return {
            "start": start_index,
            "end": end_index,
            "slots": slots,
        }
    if pattern_name == "directive_line":
        return {
            "start": start_index,
            "end": end_index,
            "slot": {
                "type": "directive_line",
                "raw": match.group(0),
            },
        }
    if pattern_name == "role":
        body = str(match.group("body") or "")
        label, target, has_target = _split_role_body(body)
        return {
            "start": start_index,
            "end": end_index,
            "slot": {
                "type": "role_label",
                "role": str(match.group("role") or ""),
                "target": target,
                "has_target": has_target,
                "source_text": label,
                "raw": match.group(0),
            },
        }
    if pattern_name == "link":
        return {
            "start": start_index,
            "end": end_index,
            "slot": {
                "type": "link_label",
                "target": str(match.group("target") or ""),
                "source_text": str(match.group("label") or ""),
                "raw": match.group(0),
            },
        }
    if pattern_name == "reference":
        return {
            "start": start_index,
            "end": end_index,
            "slot": {
                "type": "reference_label",
                "source_text": str(match.group("label") or ""),
                "suffix": str(match.group("suffix") or "_"),
                "raw": match.group(0),
            },
        }
    if pattern_name == "footnote_reference":
        return {
            "start": start_index,
            "end": end_index,
            "slot": {
                "type": "footnote_reference",
                "raw": match.group(0),
            },
        }
    if pattern_name == "literal":
        return {
            "start": start_index,
            "end": end_index,
            "slot": {
                "type": "literal",
                "raw": match.group(0),
            },
        }
    if pattern_name == "strong":
        return {
            "start": start_index,
            "end": end_index,
            "slot": {
                "type": "strong_text",
                "source_text": str(match.group("body") or ""),
                "raw": match.group(0),
            },
        }
    if pattern_name == "emphasis":
        return {
            "start": start_index,
            "end": end_index,
            "slot": {
                "type": "emphasis_text",
                "source_text": str(match.group("body") or ""),
                "raw": match.group(0),
            },
        }
    if pattern_name == "interpreted_text":
        body = str(match.group("body") or "")
        return {
            "start": start_index,
            "end": end_index,
            "slot": {
                "type": "interpreted_text",
                "source_text": body,
                "translatable": contains_han(body),
                "raw": match.group(0),
            },
        }
    return {
        "start": start_index,
        "end": end_index,
        "slot": {
            "type": "inline_literal",
            "raw": match.group(0),
        },
    }


def _split_role_body(body):
    payload = str(body or "")
    if "<" in payload and payload.endswith(">"):
        index = payload.rfind("<")
        label = payload[:index].strip()
        target = payload[index + 1 : -1].strip()
        if label and target:
            return label, target, True
    return payload, "", False


def _contains_unhandled_rst(text):
    if not text:
        return False
    sanitized = DIRECTIVE_WITH_ARGUMENT_PATTERN.sub(" ", str(text))
    sanitized = EXPLICIT_MARKUP_LINE_PATTERN.sub(" ", sanitized)
    sanitized = ROLE_PATTERN.sub(" ", sanitized)
    sanitized = INLINE_LINK_PATTERN.sub(" ", sanitized)
    sanitized = REFERENCE_PATTERN.sub(" ", sanitized)
    sanitized = FOOTNOTE_REFERENCE_PATTERN.sub(" ", sanitized)
    sanitized = SUBSTITUTION_PATTERN.sub(" ", sanitized)
    sanitized = INLINE_LITERAL_PATTERN.sub(" ", sanitized)
    sanitized = STRONG_PATTERN.sub(" ", sanitized)
    sanitized = EMPHASIS_PATTERN.sub(" ", sanitized)
    sanitized = INTERPRETED_TEXT_PATTERN.sub(" ", sanitized)
    return bool(UNHANDLED_RST_PATTERN.search(sanitized))


def _directive_argument_translatable(name, argument):
    directive_name = str(name or "").strip().lower()
    value = str(argument or "").strip()
    if not value:
        return False
    if directive_name in {
        "image",
        "figure",
        "include",
        "literalinclude",
        "code-block",
        "sourcecode",
        "toctree",
        "highlight",
        "math",
    }:
        return False
    if re.match(r"^(https?://|/|\.?/|\.\./)", value):
        return False
    if not contains_han(value) and re.match(r"^[A-Za-z0-9_./:#-]+$", value):
        return False
    return True
