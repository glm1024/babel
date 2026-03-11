import json
from pathlib import Path

from zh_audit.models import ScanSettings


APP_STATE_VERSION = 1


def default_app_state():
    defaults = ScanSettings()
    return {
        "version": APP_STATE_VERSION,
        "scan_roots": [],
        "scan_policy": {
            "max_file_size_bytes": defaults.max_file_size_bytes,
            "context_lines": defaults.context_lines,
            "exclude_globs": list(defaults.exclude_globs),
        },
    }


def load_app_state(path):
    state_path = Path(path)
    if not state_path.exists():
        return default_app_state()
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError("Invalid app state file {}: {}".format(state_path, exc))
    return normalize_app_state(payload, path=state_path)


def write_app_state(path, state):
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(normalize_app_state(state), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def normalize_app_state(payload, path=None):
    if not isinstance(payload, dict):
        raise ValueError(_format_error(path, "root must be an object."))
    version = payload.get("version", APP_STATE_VERSION)
    if version != APP_STATE_VERSION:
        raise ValueError(_format_error(path, "unsupported version {}.".format(version)))

    roots = normalize_scan_roots(payload.get("scan_roots", []), path=path)
    scan_policy = normalize_scan_policy(payload.get("scan_policy", {}), path=path)
    return {
        "version": APP_STATE_VERSION,
        "scan_roots": roots,
        "scan_policy": scan_policy,
    }


def normalize_scan_roots(raw_roots, path=None):
    if raw_roots is None:
        return []
    if not isinstance(raw_roots, list):
        raise ValueError(_format_error(path, "scan_roots must be a list."))
    roots = []
    seen = set()
    for item in raw_roots:
        if not isinstance(item, str):
            raise ValueError(_format_error(path, "scan_roots entries must be strings."))
        candidate = item.strip()
        if not candidate or candidate in seen:
            continue
        roots.append(candidate)
        seen.add(candidate)
    return roots


def normalize_scan_policy(raw_policy, path=None):
    defaults = ScanSettings()
    if raw_policy is None:
        raw_policy = {}
    if not isinstance(raw_policy, dict):
        raise ValueError(_format_error(path, "scan_policy must be an object."))
    exclude_globs = raw_policy.get("exclude_globs", list(defaults.exclude_globs))
    if not isinstance(exclude_globs, list) or not all(
        isinstance(item, str) and item.strip() for item in exclude_globs
    ):
        raise ValueError(_format_error(path, "scan_policy.exclude_globs must be a list of non-empty strings."))
    return {
        "max_file_size_bytes": int(raw_policy.get("max_file_size_bytes", defaults.max_file_size_bytes)),
        "context_lines": int(raw_policy.get("context_lines", defaults.context_lines)),
        "exclude_globs": [item.strip() for item in exclude_globs],
    }


def scan_settings_from_state(state):
    normalized = normalize_app_state(state)
    policy = normalized["scan_policy"]
    return ScanSettings(
        max_file_size_bytes=int(policy["max_file_size_bytes"]),
        context_lines=int(policy["context_lines"]),
        exclude_globs=list(policy["exclude_globs"]),
    )


def _format_error(path, message):
    if path is None:
        return "Invalid app state: {}".format(message)
    return "Invalid app state file {}: {}".format(path, message)
