import tempfile
import unittest
from pathlib import Path

from zh_audit.app_state import (
    default_model_config,
    load_app_state,
    normalize_app_state,
    normalize_model_config,
    normalize_model_config_overrides,
    write_app_state,
)


class AppStateSmokeTest(unittest.TestCase):
    def test_default_model_config_uses_think_fast_execution_strategy(self) -> None:
        self.assertEqual(default_model_config()["execution_strategy"], "think_fast")
        self.assertEqual(default_model_config()["max_tokens"], 128000)
        self.assertEqual(normalize_model_config({})["execution_strategy"], "think_fast")
        self.assertEqual(normalize_model_config({})["max_tokens"], 128000)

    def test_normalize_model_config_overrides_accepts_and_validates_execution_strategy(self) -> None:
        self.assertEqual(
            normalize_model_config_overrides({"execution_strategy": "standard"}),
            {"execution_strategy": "standard"},
        )
        self.assertEqual(
            normalize_model_config_overrides({"execution_strategy": "think_fast"}),
            {"execution_strategy": "think_fast"},
        )
        with self.assertRaises(ValueError):
            normalize_model_config_overrides({"execution_strategy": "reasoning"})

    def test_legacy_app_state_migrates_default_max_tokens_override_to_new_default(self) -> None:
        normalized = normalize_app_state(
            {
                "version": 1,
                "model_config_overrides": {
                    "base_url": "http://127.0.0.1:8000/v1",
                    "api_key": "sk-local",
                    "model": "demo",
                    "max_tokens": 4096,
                },
            }
        )

        self.assertEqual(normalized["version"], 4)
        self.assertEqual(normalized["model_config_overrides"]["max_tokens"], 128000)

    def test_v2_app_state_migrates_explicit_4096_max_tokens_to_new_default(self) -> None:
        normalized = normalize_app_state(
            {
                "version": 2,
                "model_config_overrides": {
                    "base_url": "http://127.0.0.1:8000/v1",
                    "api_key": "sk-local",
                    "model": "demo",
                    "max_tokens": 4096,
                },
            }
        )

        self.assertEqual(normalized["version"], 4)
        self.assertEqual(normalized["model_config_overrides"]["max_tokens"], 128000)

    def test_v3_app_state_migrates_explicit_4096_max_tokens_to_new_default(self) -> None:
        normalized = normalize_app_state(
            {
                "version": 3,
                "model_config_overrides": {
                    "base_url": "http://127.0.0.1:8000/v1",
                    "api_key": "sk-local",
                    "model": "demo",
                    "max_tokens": 4096,
                },
            }
        )

        self.assertEqual(normalized["version"], 4)
        self.assertEqual(normalized["model_config_overrides"]["max_tokens"], 128000)

    def test_current_app_state_preserves_explicit_4096_max_tokens(self) -> None:
        normalized = normalize_app_state(
            {
                "version": 4,
                "model_config_overrides": {
                    "base_url": "http://127.0.0.1:8000/v1",
                    "api_key": "sk-local",
                    "model": "demo",
                    "max_tokens": 4096,
                },
            }
        )

        self.assertEqual(normalized["version"], 4)
        self.assertEqual(normalized["model_config_overrides"]["max_tokens"], 4096)

    def test_missing_custom_keep_categories_defaults_to_empty_list(self) -> None:
        normalized = normalize_app_state({"version": 4})
        self.assertEqual(normalized["custom_keep_categories"], [])

    def test_custom_keep_categories_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "app_state.json"
            state = normalize_app_state(
                {
                    "version": 1,
                    "scan_roots": ["/tmp/repo-a"],
                    "custom_keep_categories": [
                        {
                            "name": "历史兼容文案",
                            "enabled": True,
                            "rules": [
                                {
                                    "type": "path",
                                    "pattern": "templates/view.html",
                                    "path_globs": ["templates/**"],
                                }
                            ],
                        }
                    ],
                }
            )

            self.assertEqual(
                state["custom_keep_categories"][0]["rules"][0],
                {
                    "type": "path",
                    "pattern": "templates/view.html",
                },
            )

            write_app_state(target, state)
            reloaded = load_app_state(target)

            self.assertEqual(reloaded["custom_keep_categories"], state["custom_keep_categories"])

    def test_duplicate_custom_keep_category_names_rejected(self) -> None:
        with self.assertRaises(ValueError):
            normalize_app_state(
                {
                    "version": 1,
                    "custom_keep_categories": [
                        {
                            "name": "重复分类",
                            "enabled": True,
                            "rules": [{"type": "keyword", "pattern": "系统繁忙"}],
                        },
                        {
                            "name": "重复分类",
                            "enabled": True,
                            "rules": [{"type": "keyword", "pattern": "系统超时"}],
                        },
                    ],
                }
            )

    def test_invalid_custom_keep_regex_rejected(self) -> None:
        with self.assertRaises(ValueError):
            normalize_app_state(
                {
                    "version": 1,
                    "custom_keep_categories": [
                        {
                            "name": "坏规则",
                            "enabled": True,
                            "rules": [{"type": "regex", "pattern": "["}],
                        }
                    ],
                }
            )

    def test_invalid_custom_keep_regex_error_message_is_localized(self) -> None:
        with self.assertRaises(ValueError) as context:
            normalize_app_state(
                {
                    "version": 1,
                    "custom_keep_categories": [
                        {
                            "name": "坏规则",
                            "enabled": True,
                            "rules": [{"type": "regex", "pattern": "["}],
                        }
                    ],
                }
            )

        self.assertEqual(
            str(context.exception),
            "免改规则配置无效：规则分组 1 的规则 1 的正则表达式格式不正确。",
        )

    def test_invalid_custom_keep_rule_type_error_message_mentions_path(self) -> None:
        with self.assertRaises(ValueError) as context:
            normalize_app_state(
                {
                    "version": 1,
                    "custom_keep_categories": [
                        {
                            "name": "坏规则",
                            "enabled": True,
                            "rules": [{"type": "unknown", "pattern": "src/demo"}],
                        }
                    ],
                }
            )

        self.assertEqual(
            str(context.exception),
            "免改规则配置无效：规则分组 1 的规则 1 的规则类型只能是“关键字”“正则”或“文件路径”。",
        )

    def test_empty_custom_keep_category_name_and_rules_rejected(self) -> None:
        with self.assertRaises(ValueError):
            normalize_app_state(
                {
                    "version": 1,
                    "custom_keep_categories": [
                        {
                            "name": "   ",
                            "enabled": True,
                            "rules": [],
                        }
                    ],
                }
            )


if __name__ == "__main__":
    unittest.main()
