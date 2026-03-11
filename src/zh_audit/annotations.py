import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from zh_audit.models import CATEGORY_ANNOTATED_NO_CHANGE
from zh_audit.utils import compact_snippet, sha1_text


ANNOTATION_STORE_VERSION = 1
ANNOTATION_STATS_DEFAULT = {
    "loaded": 0,
    "applied": 0,
    "stale": 0,
    "exact_applied": 0,
    "fallback_applied": 0,
}


def default_annotation_store():
    return {"version": ANNOTATION_STORE_VERSION, "items": {}}


def resolve_annotation_path(out_dir, annotation_path=None):
    if annotation_path is not None:
        return Path(annotation_path)
    return Path(out_dir) / "annotations.json"


def load_annotation_store(path):
    annotation_path = Path(path)
    if not annotation_path.exists():
        return default_annotation_store()
    try:
        payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError("Invalid annotations file {}: {}".format(annotation_path, exc))

    if not isinstance(payload, dict):
        raise ValueError("Invalid annotations file {}: root must be an object.".format(annotation_path))
    version = payload.get("version")
    if version != ANNOTATION_STORE_VERSION:
        raise ValueError(
            "Invalid annotations file {}: unsupported version {}.".format(annotation_path, version)
        )
    items = payload.get("items")
    if not isinstance(items, dict):
        raise ValueError("Invalid annotations file {}: items must be an object.".format(annotation_path))
    normalized_items = {}
    for key, item in items.items():
        if not isinstance(key, str) or not isinstance(item, dict):
            raise ValueError(
                "Invalid annotations file {}: annotation entries must be object values keyed by string.".format(
                    annotation_path
                )
            )
        normalized_items[key] = {
            "project": str(item.get("project", "")),
            "path": str(item.get("path", "")),
            "surface_kind": str(item.get("surface_kind", "")),
            "normalized_text": str(item.get("normalized_text", "")),
            "snippet": compact_snippet(str(item.get("snippet", ""))),
            "original_category": str(item.get("original_category", "")),
            "original_action": str(item.get("original_action", "")),
            "reason": str(item.get("reason", "")),
            "updated_at": str(item.get("updated_at", "")),
        }
    return {"version": ANNOTATION_STORE_VERSION, "items": normalized_items}


def write_annotation_store(path, store):
    annotation_path = Path(path)
    annotation_path.parent.mkdir(parents=True, exist_ok=True)
    annotation_path.write_text(
        json.dumps(store, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def current_timestamp():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def ensure_annotation_fields(finding):
    if _get(finding, "annotated", None) is None:
        _set(finding, "annotated", False)
    if _get(finding, "annotation_reason", None) is None:
        _set(finding, "annotation_reason", "")
    if _get(finding, "annotation_updated_at", None) is None:
        _set(finding, "annotation_updated_at", "")
    if _get(finding, "original_category", None) is None:
        _set(finding, "original_category", "")
    if _get(finding, "original_action", None) is None:
        _set(finding, "original_action", "")
    if _get(finding, "annotation_key", None) is None:
        _set(finding, "annotation_key", "")


def build_annotation_exact_key(project, path, surface_kind, normalized_text, snippet):
    signature = "exact|{}|{}|{}|{}|{}".format(
        str(project or ""),
        str(path or ""),
        str(surface_kind or ""),
        str(normalized_text or ""),
        compact_snippet(str(snippet or "")),
    )
    return sha1_text(signature)[:24]


def build_annotation_fallback_key(project, path, surface_kind, normalized_text):
    signature = "fallback|{}|{}|{}|{}".format(
        str(project or ""),
        str(path or ""),
        str(surface_kind or ""),
        str(normalized_text or ""),
    )
    return sha1_text(signature)[:24]


def finding_annotation_exact_key(finding):
    return build_annotation_exact_key(
        _get(finding, "project", ""),
        _get(finding, "path", ""),
        _get(finding, "surface_kind", ""),
        _get(finding, "normalized_text", "") or _get(finding, "text", ""),
        _get(finding, "snippet", ""),
    )


def finding_annotation_fallback_key(finding):
    return build_annotation_fallback_key(
        _get(finding, "project", ""),
        _get(finding, "path", ""),
        _get(finding, "surface_kind", ""),
        _get(finding, "normalized_text", "") or _get(finding, "text", ""),
    )


def restore_finding_from_annotation(finding):
    ensure_annotation_fields(finding)
    if _get(finding, "annotated", False) and _get(finding, "category", "") == CATEGORY_ANNOTATED_NO_CHANGE:
        original_category = _get(finding, "original_category", "")
        original_action = _get(finding, "original_action", "")
        if original_category:
            _set(finding, "category", original_category)
        if original_action:
            _set(finding, "action", original_action)
    _set(finding, "annotated", False)
    _set(finding, "annotation_reason", "")
    _set(finding, "annotation_updated_at", "")
    _set(finding, "original_category", "")
    _set(finding, "original_action", "")
    _set(finding, "annotation_key", "")


def apply_annotation_record(finding, annotation_key, record):
    ensure_annotation_fields(finding)
    current_category = _get(finding, "category", "")
    current_action = _get(finding, "action", "")
    if current_category == CATEGORY_ANNOTATED_NO_CHANGE:
        current_category = _get(finding, "original_category", "") or current_category
        current_action = _get(finding, "original_action", "") or current_action

    _set(finding, "original_category", record.get("original_category") or current_category)
    _set(finding, "original_action", record.get("original_action") or current_action)
    _set(finding, "annotated", True)
    _set(finding, "annotation_reason", str(record.get("reason", "")))
    _set(finding, "annotation_updated_at", str(record.get("updated_at", "")))
    _set(finding, "annotation_key", str(annotation_key))
    _set(finding, "category", CATEGORY_ANNOTATED_NO_CHANGE)
    _set(finding, "action", "keep")


def upsert_annotation(store, finding, reason, updated_at=None):
    ensure_annotation_fields(finding)
    timestamp = updated_at or current_timestamp()
    original_category = _get(finding, "original_category", "") or _get(finding, "category", "")
    original_action = _get(finding, "original_action", "") or _get(finding, "action", "")
    key = finding_annotation_exact_key(finding)
    store.setdefault("version", ANNOTATION_STORE_VERSION)
    store.setdefault("items", {})
    store["items"][key] = {
        "project": str(_get(finding, "project", "")),
        "path": str(_get(finding, "path", "")),
        "surface_kind": str(_get(finding, "surface_kind", "")),
        "normalized_text": str(_get(finding, "normalized_text", "") or _get(finding, "text", "")),
        "snippet": compact_snippet(str(_get(finding, "snippet", ""))),
        "original_category": str(original_category),
        "original_action": str(original_action),
        "reason": str(reason or ""),
        "updated_at": str(timestamp),
    }
    return key, store["items"][key]


def remove_annotation(store, finding):
    ensure_annotation_fields(finding)
    key = _get(finding, "annotation_key", "") or finding_annotation_exact_key(finding)
    items = store.setdefault("items", {})
    if key in items:
        del items[key]
        return True
    return False


def apply_annotation_store(findings, store):
    stats = dict(ANNOTATION_STATS_DEFAULT)
    items = dict((key, value) for key, value in store.get("items", {}).items())
    stats["loaded"] = len(items)

    exact_matches = defaultdict(list)
    fallback_matches = defaultdict(list)

    for finding in findings:
        ensure_annotation_fields(finding)
        if _get(finding, "annotated", False):
            restore_finding_from_annotation(finding)
        exact_matches[finding_annotation_exact_key(finding)].append(finding)
        fallback_matches[finding_annotation_fallback_key(finding)].append(finding)

    used_store_keys = set()
    applied_keys = set()

    for key, record in items.items():
        matches = exact_matches.get(key, [])
        if not matches:
            continue
        used_store_keys.add(key)
        for finding in matches:
            apply_annotation_record(finding, key, record)
            stats["applied"] += 1
            stats["exact_applied"] += 1

    fallback_groups = defaultdict(list)
    for key, record in items.items():
        if key in used_store_keys:
            continue
        fallback_groups[_annotation_record_fallback_key(record)].append((key, record))

    for fallback_key, records in fallback_groups.items():
        matches = fallback_matches.get(fallback_key, [])
        if len(records) != 1 or len(matches) != 1:
            continue
        key, record = records[0]
        if key in applied_keys:
            continue
        apply_annotation_record(matches[0], key, record)
        used_store_keys.add(key)
        applied_keys.add(key)
        stats["applied"] += 1
        stats["fallback_applied"] += 1

    stats["stale"] = max(0, stats["loaded"] - len(used_store_keys))
    return stats


def _annotation_record_fallback_key(record):
    return build_annotation_fallback_key(
        record.get("project", ""),
        record.get("path", ""),
        record.get("surface_kind", ""),
        record.get("normalized_text", ""),
    )


def _get(item, name, default=""):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _set(item, name, value):
    if isinstance(item, dict):
        item[name] = value
    else:
        setattr(item, name, value)
