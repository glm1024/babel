import tempfile
import unittest
from pathlib import Path

from zh_audit.properties_file import load_properties_document
from zh_audit.terminology_xlsx import (
    DEFAULT_TERMINOLOGY_ROWS,
    exact_terminology_translation,
    load_terminology_xlsx,
    match_locked_terms,
    write_terminology_xlsx,
)
from zh_audit.translation_workflow import TranslationSession, build_translation_system_prompt


class TranslationWorkflowTest(unittest.TestCase):
    def test_terminology_xlsx_roundtrip_and_longest_match(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            glossary_path = Path(temp_dir) / "terminology.xlsx"
            write_terminology_xlsx(glossary_path, DEFAULT_TERMINOLOGY_ROWS)
            glossary = load_terminology_xlsx(glossary_path)

            self.assertEqual(glossary["资源池"], "resource pool")
            self.assertEqual(exact_terminology_translation("云主机模板", glossary), "Elastic Compute Service Template")

            matches = match_locked_terms("创建云主机模板", glossary)
            self.assertEqual(matches[0]["source"], "云主机模板")
            self.assertNotIn("云主机", [item["source"] for item in matches])

    def test_properties_document_preserves_structure_and_appends(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "messages.properties"
            target.write_text(
                "# comment\r\nKEY_A = old value\r\n\r\n",
                encoding="utf-8",
            )
            document = load_properties_document(target)
            document.set_value("KEY_A", "new value")
            document.append_comment_once("# Added by zh-audit 码值校译")
            document.set_value("KEY_B", "new item")
            document.write()

            with target.open(encoding="utf-8", newline="") as handle:
                rendered = handle.read()
            self.assertIn("# comment\r\nKEY_A = new value\r\n\r\n", rendered)
            self.assertIn("# Added by zh-audit 码值校译\r\nKEY_B=new item\r\n", rendered)

    def test_translation_session_applies_exact_glossary_without_model(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "zh.properties"
            target = Path(temp_dir) / "en.properties"
            source.write_text("HOST_GROUP=主机组\n", encoding="utf-8")
            target.write_text("HOST_GROUP=wrong value\n", encoding="utf-8")

            session = TranslationSession(
                source_path=source,
                target_path=target,
                glossary={"主机组": "host group"},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=lambda **kwargs: (_ for _ in ()).throw(AssertionError("model should not be called")),
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["status"], "done")
            self.assertEqual(snapshot["status"]["counts"]["accepted"], 1)
            self.assertEqual(snapshot["status"]["counts"]["glossary_applied"], 1)
            self.assertEqual(target.read_text(encoding="utf-8"), "HOST_GROUP=host group\n")

    def test_translation_session_pending_regenerate_and_accept_append(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "zh.properties"
            target = Path(temp_dir) / "en.properties"
            source.write_text("NETWORK_LINK_ADD=创建对等连接：{0}\n", encoding="utf-8")
            target.write_text("", encoding="utf-8")

            calls = []

            def fake_model(**kwargs):
                calls.append(kwargs)
                if kwargs.get("extra_prompt"):
                    return {
                        "verdict": "needs_update",
                        "candidate_translation": "create link: {0}",
                        "reason": "retry",
                    }
                return {
                    "verdict": "needs_update",
                    "candidate_translation": "create peer connection: {0}",
                    "reason": "initial",
                }

            session = TranslationSession(
                source_path=source,
                target_path=target,
                glossary={"对等连接": "link"},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=fake_model,
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["counts"]["pending"], 1)
            pending_item = snapshot["pending_items"][0]
            self.assertIn("对等连接", pending_item["source_text"])
            self.assertIn("create link: {0}", pending_item["candidate_text"])
            self.assertEqual(pending_item["reason"], "按术语词典重试后生成。")

            regenerated = session.regenerate(pending_item["id"], "更简洁一点")
            self.assertEqual(regenerated["status"]["counts"]["regenerated"], 1)
            self.assertEqual(
                regenerated["pending_items"][0]["reason"],
                "目标英文缺失，建议补充候选英文。",
            )

            accepted = session.accept(pending_item["id"])
            self.assertEqual(accepted["status"]["counts"]["accepted"], 1)
            self.assertEqual(accepted["status"]["counts"]["appended"], 1)
            content = target.read_text(encoding="utf-8")
            self.assertIn("# Added by zh-audit 码值校译", content)
            self.assertIn("NETWORK_LINK_ADD=create link: {0}", content)
            self.assertGreaterEqual(len(calls), 2)

    def test_translation_session_decodes_unicode_escapes_for_glossary_and_display(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "zh.properties"
            target = Path(temp_dir) / "en.properties"
            source.write_text("HOST_GROUP=\\u4e3b\\u673a\\u7ec4\n", encoding="utf-8")
            target.write_text("HOST_GROUP=wrong value\n", encoding="utf-8")

            session = TranslationSession(
                source_path=source,
                target_path=target,
                glossary={"主机组": "host group"},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=lambda **kwargs: (_ for _ in ()).throw(AssertionError("model should not be called")),
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["counts"]["glossary_applied"], 1)
            self.assertEqual(snapshot["recent_items"][0]["source_text"], "主机组")
            self.assertEqual(snapshot["events"][0]["source_text"], "主机组")
            self.assertEqual(snapshot["events"][0]["label"], "术语直出")
            self.assertEqual(target.read_text(encoding="utf-8"), "HOST_GROUP=host group\n")

    def test_translation_system_prompt_and_reason_fallback_are_chinese(self):
        prompt = build_translation_system_prompt()
        self.assertIn("reason must be written in Simplified Chinese.", prompt)

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "zh.properties"
            target = Path(temp_dir) / "en.properties"
            source.write_text("API_NOT_FOUND=适配服务接口不存在。\n", encoding="utf-8")
            target.write_text("API_NOT_FOUND=API not found in adapter server.\n", encoding="utf-8")

            session = TranslationSession(
                source_path=source,
                target_path=target,
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "candidate_translation": "Adapter server interface not found.",
                    "reason": "The source text is more specific than the current target text.",
                },
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            self.assertEqual(snapshot["pending_items"][0]["reason"], "现有英文翻译不够准确，建议更新为候选英文。")

    def test_translation_session_uses_clear_skip_label_for_accurate_translation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "zh.properties"
            target = Path(temp_dir) / "en.properties"
            source.write_text("API_NOT_FOUND=适配服务接口不存在。\n", encoding="utf-8")
            target.write_text("API_NOT_FOUND=Adapter server interface not found.\n", encoding="utf-8")

            session = TranslationSession(
                source_path=source,
                target_path=target,
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=lambda **kwargs: {
                    "verdict": "accurate",
                    "candidate_translation": "Adapter server interface not found.",
                    "reason": "翻译准确。",
                },
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["counts"]["skipped"], 1)
            self.assertEqual(snapshot["events"][0]["label"], "已跳过：翻译准确，无需更新")


if __name__ == "__main__":
    unittest.main()
