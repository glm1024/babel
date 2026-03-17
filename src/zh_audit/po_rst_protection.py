from __future__ import absolute_import

import re


ROLE_PATTERN = re.compile(r":(?P<role>[A-Za-z0-9_-]+):`(?P<body>[^`\r\n]+)`")
INLINE_LINK_PATTERN = re.compile(r"`(?P<label>[^`<>]+?)\s*<(?P<target>[^`<>]+)>`_")
SUBSTITUTION_PATTERN = re.compile(r"\|[^|\r\n]+\|")
INLINE_LITERAL_PATTERN = re.compile(r"``[^`\r\n]+``")
UNHANDLED_RST_PATTERN = re.compile(r"`|:[A-Za-z0-9_-]+:|\.\.\s+\S")


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
        slot = dict(match["slot"])
        if slot.get("type") in ("role_label", "link_label"):
            slot_index += 1
            slot["slot_id"] = "slot_{}".format(slot_index)
        slots.append(slot)
        if slot["type"] in ("text", "role_label", "link_label"):
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
        elif slot_type == "inline_literal":
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
    source_slots = source_protected.get("slots", [])
    candidate_slots = candidate.get("slots", [])
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
        if slot_type == "role_label":
            if source_slot.get("role", "") != candidate_slot.get("role", ""):
                return "候选改动了 rst role 名称"
            if source_slot.get("target", "") != candidate_slot.get("target", ""):
                return "候选改动了 rst role target"
        if slot_type == "link_label" and source_slot.get("target", "") != candidate_slot.get("target", ""):
            return "候选改动了 rst 链接 target"
    return ""


def build_slot_translation_map(raw_slot_translations):
    normalized_payload = build_slot_translation_payload(raw_slot_translations)
    return {
        slot_id: item.get("translation", "")
        for slot_id, item in normalized_payload.items()
    }


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
    for pattern_name, pattern in (
        ("role", ROLE_PATTERN),
        ("link", INLINE_LINK_PATTERN),
        ("literal", SUBSTITUTION_PATTERN),
        ("inline_literal", INLINE_LITERAL_PATTERN),
    ):
        match = pattern.search(source, start)
        if match is None:
            continue
        candidates.append((match.start(), match.end(), pattern_name, match))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    start_index, end_index, pattern_name, match = candidates[0]
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
    if pattern_name == "literal":
        return {
            "start": start_index,
            "end": end_index,
            "slot": {
                "type": "literal",
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
    sanitized = ROLE_PATTERN.sub(" ", str(text))
    sanitized = INLINE_LINK_PATTERN.sub(" ", sanitized)
    sanitized = SUBSTITUTION_PATTERN.sub(" ", sanitized)
    sanitized = INLINE_LITERAL_PATTERN.sub(" ", sanitized)
    return bool(UNHANDLED_RST_PATTERN.search(sanitized))
