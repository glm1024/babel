from __future__ import absolute_import

from collections import defaultdict
from pathlib import Path

from zh_audit.session_store import load_json_file, write_json_atomically
from zh_audit.utils import sha1_text


REMEDIATION_STATE_VERSION = 1


def default_remediation_state():
    return {
        "version": REMEDIATION_STATE_VERSION,
        "items": {},
    }


def load_remediation_state(path):
    target = Path(path)
    payload = load_json_file(target)
    if payload is None:
        return default_remediation_state()
    if not isinstance(payload, dict):
        raise ValueError("Invalid remediation state {}: root must be an object.".format(target))
    version = int(payload.get("version", REMEDIATION_STATE_VERSION))
    if version != REMEDIATION_STATE_VERSION:
        raise ValueError(
            "Invalid remediation state {}: unsupported version {}.".format(target, version)
        )
    raw_items = payload.get("items", {})
    if not isinstance(raw_items, dict):
        raise ValueError("Invalid remediation state {}: items must be an object.".format(target))
    items = {}
    for key, value in raw_items.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            raise ValueError(
                "Invalid remediation state {}: items must be object values keyed by string.".format(target)
            )
        items[str(key)] = {
            "status": str(value.get("status", "")),
            "updated_at": str(value.get("updated_at", "")),
            "exact_key": str(value.get("exact_key", "")),
            "fallback_key": str(value.get("fallback_key", "")),
        }
    return {
        "version": REMEDIATION_STATE_VERSION,
        "items": items,
    }


def write_remediation_state(path, store):
    payload = default_remediation_state()
    items = payload["items"]
    raw_items = {}
    if isinstance(store, dict):
        raw_items = store.get("items", {}) or {}
    for key, value in raw_items.items():
        if not isinstance(value, dict):
            continue
        items[str(key)] = {
            "status": str(value.get("status", "")),
            "updated_at": str(value.get("updated_at", "")),
            "exact_key": str(value.get("exact_key", "")),
            "fallback_key": str(value.get("fallback_key", "")),
        }
    write_json_atomically(path, payload)


def remediation_exact_key(finding):
    return sha1_text(
        "|".join(
            [
                _finding_value(finding, "project", ""),
                _finding_value(finding, "path", ""),
                _finding_value(finding, "surface_kind", ""),
                _finding_value(finding, "normalized_text", ""),
                _finding_value(finding, "snippet", ""),
            ]
        )
    )


def remediation_fallback_key(finding):
    return sha1_text(
        "|".join(
            [
                _finding_value(finding, "project", ""),
                _finding_value(finding, "path", ""),
                _finding_value(finding, "surface_kind", ""),
                _finding_value(finding, "normalized_text", ""),
            ]
        )
    )


def upsert_resolved(store, finding, updated_at):
    exact_key = remediation_exact_key(finding)
    record = {
        "status": "resolved",
        "updated_at": str(updated_at or ""),
        "exact_key": exact_key,
        "fallback_key": remediation_fallback_key(finding),
    }
    store.setdefault("items", {})[exact_key] = record
    return exact_key, record


def remove_resolved(store, finding):
    exact_key = remediation_exact_key(finding)
    items = store.setdefault("items", {})
    return items.pop(exact_key, None) is not None


def apply_remediation_state(findings, store):
    exact_matches = defaultdict(list)
    fallback_matches = defaultdict(list)
    for finding in findings:
        if _finding_value(finding, "action", "") == "keep":
            continue
        exact_matches[remediation_exact_key(finding)].append(finding)
        fallback_matches[remediation_fallback_key(finding)].append(finding)

    applied = 0
    items = {}
    if isinstance(store, dict):
        items = store.get("items", {}) or {}
    for record in items.values():
        if not isinstance(record, dict) or record.get("status") != "resolved":
            continue
        exact_key = str(record.get("exact_key", ""))
        fallback_key = str(record.get("fallback_key", ""))
        matches = exact_matches.get(exact_key, [])
        if matches:
            for finding in matches:
                applied += _apply_resolved(finding)
            continue
        fallback = fallback_matches.get(fallback_key, [])
        if len(fallback) == 1:
            applied += _apply_resolved(fallback[0])
    return {"applied": applied}


def _apply_resolved(finding):
    action = _finding_value(finding, "action", "")
    if action == "keep":
        return 0
    if isinstance(finding, dict):
        finding["action"] = "resolved"
    else:
        finding.action = "resolved"
    return 1


def _finding_value(finding, name, default=""):
    if isinstance(finding, dict):
        return str(finding.get(name, default) or "")
    return str(getattr(finding, name, default) or "")
