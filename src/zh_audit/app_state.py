import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from zh_audit.models import ScanSettings


APP_STATE_VERSION = 1
MODEL_PROVIDER = "openai compatible"
MODEL_CONFIG_FIELDS = ("base_url", "api_key", "model", "max_tokens")
DEFAULT_MODEL_MAX_TOKENS = 100


def default_model_config():
    return {
        "provider": MODEL_PROVIDER,
        "base_url": "",
        "api_key": "",
        "model": "",
        "max_tokens": DEFAULT_MODEL_MAX_TOKENS,
    }


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
        "model_config_overrides": {},
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
    model_config_overrides = normalize_model_config_overrides(
        payload.get("model_config_overrides", {}),
        path=path,
        field_name="model_config_overrides",
    )
    return {
        "version": APP_STATE_VERSION,
        "scan_roots": roots,
        "scan_policy": scan_policy,
        "model_config_overrides": model_config_overrides,
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


def normalize_model_config(raw_config, path=None):
    normalized = default_model_config()
    normalized.update(normalize_model_config_overrides(raw_config, path=path))
    return normalized


def normalize_model_config_overrides(raw_config, path=None, field_name="model_config"):
    if raw_config is None:
        return {}
    if not isinstance(raw_config, dict):
        raise ValueError(_format_error(path, "{} must be an object.".format(field_name)))
    normalized = {}
    if "base_url" in raw_config:
        normalized["base_url"] = normalize_model_base_url(raw_config.get("base_url"), path=path)
    if "api_key" in raw_config:
        normalized["api_key"] = _normalize_model_text(raw_config.get("api_key"))
    if "model" in raw_config:
        normalized["model"] = _normalize_model_text(raw_config.get("model"))
    if "max_tokens" in raw_config:
        normalized["max_tokens"] = _normalize_max_tokens(raw_config.get("max_tokens"))
    return normalized


def merge_model_config(*configs):
    merged = default_model_config()
    for raw_config in configs:
        if raw_config is None:
            continue
        merged.update(normalize_model_config_overrides(raw_config))
    merged["provider"] = MODEL_PROVIDER
    return merged


def diff_model_config_overrides(model_config, baseline_config):
    normalized = normalize_model_config(model_config)
    baseline = normalize_model_config(baseline_config)
    overrides = {}
    for key in MODEL_CONFIG_FIELDS:
        if normalized[key] != baseline[key]:
            overrides[key] = normalized[key]
    return overrides


def normalize_model_base_url(raw_value, path=None):
    value = _normalize_model_text(raw_value)
    if not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(_format_error(path, "model_config.base_url must be an absolute http(s) URL."))
    normalized_path = parsed.path.rstrip("/")
    if normalized_path.endswith("/chat/completions"):
        normalized_path = normalized_path[: -len("/chat/completions")]
    if not normalized_path:
        normalized_path = "/v1"
    elif not normalized_path.endswith("/v1"):
        normalized_path = normalized_path + "/v1"
    return urlunsplit((parsed.scheme, parsed.netloc, normalized_path, "", ""))


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


def _normalize_model_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _normalize_max_tokens(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_MODEL_MAX_TOKENS
    if parsed < 1:
        return DEFAULT_MODEL_MAX_TOKENS
    return parsed
