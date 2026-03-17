import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from zh_audit.models import ScanSettings


APP_STATE_VERSION = 1
MODEL_PROVIDER = "openai compatible"
MODEL_CONFIG_FIELDS = ("base_url", "api_key", "model", "max_tokens")
DEFAULT_MODEL_MAX_TOKENS = 4096


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
        "custom_keep_categories": default_custom_keep_categories(),
        "translation_config": default_translation_config(),
        "po_translation_config": default_po_translation_config(),
        "sql_translation_config": default_sql_translation_config(),
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
    custom_keep_categories = normalize_custom_keep_categories(
        payload.get("custom_keep_categories", []),
        path=path,
    )
    translation_config = normalize_translation_config(payload.get("translation_config", {}), path=path)
    po_translation_config = normalize_po_translation_config(payload.get("po_translation_config", {}), path=path)
    sql_translation_config = normalize_sql_translation_config(payload.get("sql_translation_config", {}), path=path)
    return {
        "version": APP_STATE_VERSION,
        "scan_roots": roots,
        "scan_policy": scan_policy,
        "model_config_overrides": model_config_overrides,
        "custom_keep_categories": custom_keep_categories,
        "translation_config": translation_config,
        "po_translation_config": po_translation_config,
        "sql_translation_config": sql_translation_config,
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


def default_translation_config():
    return {
        "source_path": "",
        "target_path": "",
        "auto_accept": False,
    }


def default_custom_keep_categories():
    return []


def default_po_translation_config():
    return {
        "po_path": "",
        "auto_accept": False,
    }


def normalize_custom_keep_categories(raw_categories, path=None):
    if raw_categories is None:
        return []
    if not isinstance(raw_categories, list):
        raise ValueError(_format_custom_keep_error(path, "免改规则配置必须是数组。"))
    normalized = []
    seen_names = set()
    for index, raw_category in enumerate(raw_categories):
        if not isinstance(raw_category, dict):
            raise ValueError(
                _format_custom_keep_error(
                    path,
                    "{} 的配置格式不正确。".format(_custom_keep_category_label(index)),
                )
            )
        name = _normalize_model_text(raw_category.get("name"))
        if not name:
            raise ValueError(
                _format_custom_keep_error(
                    path,
                    "{} 的分类名称不能为空。".format(_custom_keep_category_label(index)),
                )
            )
        if name in seen_names:
            raise ValueError(_format_custom_keep_error(path, '规则分组名称“{}”重复，请保持唯一。'.format(name)))
        rules = normalize_custom_keep_rules(raw_category.get("rules"), path=path, category_index=index)
        normalized.append(
            {
                "name": name,
                "enabled": bool(raw_category.get("enabled", True)),
                "rules": rules,
            }
        )
        seen_names.add(name)
    return normalized


def normalize_custom_keep_rules(raw_rules, path=None, category_index=0):
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ValueError(
            _format_custom_keep_error(
                path,
                "{} 至少需要一条规则。".format(_custom_keep_category_label(category_index)),
            )
        )
    normalized = []
    for rule_index, raw_rule in enumerate(raw_rules):
        if not isinstance(raw_rule, dict):
            raise ValueError(
                _format_custom_keep_error(
                    path,
                    "{} 的配置格式不正确。".format(_custom_keep_rule_label(category_index, rule_index)),
                )
            )
        rule_type = _normalize_model_text(raw_rule.get("type")).lower()
        if rule_type not in ("keyword", "regex"):
            raise ValueError(
                _format_custom_keep_error(
                    path,
                    "{} 的规则类型只能是“关键字”或“正则”。".format(
                        _custom_keep_rule_label(category_index, rule_index),
                    ),
                )
            )
        pattern = _normalize_model_text(raw_rule.get("pattern"))
        if not pattern:
            raise ValueError(
                _format_custom_keep_error(
                    path,
                    "{} 的关键字或正则不能为空。".format(
                        _custom_keep_rule_label(category_index, rule_index),
                    ),
                )
            )
        if rule_type == "regex":
            try:
                re.compile(pattern)
            except re.error:
                raise ValueError(
                    _format_custom_keep_error(
                        path,
                        "{} 的正则表达式格式不正确。".format(_custom_keep_rule_label(category_index, rule_index)),
                    )
                )
        normalized.append(
            {
                "type": rule_type,
                "pattern": pattern,
            }
        )
    return normalized


def normalize_translation_config(raw_config, path=None):
    defaults = default_translation_config()
    if raw_config is None:
        return dict(defaults)
    if not isinstance(raw_config, dict):
        raise ValueError(_format_error(path, "translation_config must be an object."))
    return {
        "source_path": _normalize_model_text(raw_config.get("source_path", defaults["source_path"])),
        "target_path": _normalize_model_text(raw_config.get("target_path", defaults["target_path"])),
        "auto_accept": bool(raw_config.get("auto_accept", defaults["auto_accept"])),
    }


def normalize_po_translation_config(raw_config, path=None):
    defaults = default_po_translation_config()
    if raw_config is None:
        return dict(defaults)
    if not isinstance(raw_config, dict):
        raise ValueError(_format_error(path, "po_translation_config must be an object."))
    return {
        "po_path": _normalize_model_text(raw_config.get("po_path", defaults["po_path"])),
        "auto_accept": bool(raw_config.get("auto_accept", defaults["auto_accept"])),
    }


def default_sql_translation_config():
    return {
        "directory_path": "",
        "table_name": "",
        "primary_key_field": "id",
        "source_field": "",
        "target_field": "",
        "auto_accept": False,
    }


def normalize_sql_translation_config(raw_config, path=None):
    defaults = default_sql_translation_config()
    if raw_config is None:
        return dict(defaults)
    if not isinstance(raw_config, dict):
        raise ValueError(_format_error(path, "sql_translation_config must be an object."))
    return {
        "directory_path": _normalize_model_text(raw_config.get("directory_path", defaults["directory_path"])),
        "table_name": _normalize_model_text(raw_config.get("table_name", defaults["table_name"])),
        "primary_key_field": _normalize_model_text(raw_config.get("primary_key_field", defaults["primary_key_field"]))
        or defaults["primary_key_field"],
        "source_field": _normalize_model_text(raw_config.get("source_field", defaults["source_field"])),
        "target_field": _normalize_model_text(raw_config.get("target_field", defaults["target_field"])),
        "auto_accept": bool(raw_config.get("auto_accept", defaults["auto_accept"])),
    }


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


def _format_custom_keep_error(path, message):
    if path is None:
        return "免改规则配置无效：{}".format(message)
    return "应用状态文件 {} 中的免改规则配置无效：{}".format(path, message)


def _custom_keep_category_label(index):
    return "规则分组 {}".format(int(index) + 1)


def _custom_keep_rule_label(category_index, rule_index):
    return "{} 的规则 {}".format(
        _custom_keep_category_label(category_index),
        int(rule_index) + 1,
    )


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
