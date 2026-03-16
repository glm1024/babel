import tempfile
import unittest
from pathlib import Path

from zh_audit.app_state import load_app_state, normalize_app_state, write_app_state


class AppStateSmokeTest(unittest.TestCase):
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
                                    "type": "keyword",
                                    "pattern": "系统繁忙",
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
                    "type": "keyword",
                    "pattern": "系统繁忙",
                },
            )

            write_app_state(target, state)
            reloaded = load_app_state(target)

            self.assertEqual(reloaded["custom_keep_categories"], state["custom_keep_categories"])

    def test_missing_custom_keep_categories_defaults_to_empty_list(self) -> None:
        normalized = normalize_app_state({"version": 1})
        self.assertEqual(normalized["custom_keep_categories"], [])

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
