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
from zh_audit.translation_workflow import (
    TranslationSession,
    build_translation_review_system_prompt,
    build_translation_system_prompt,
)


def _pass_review(**kwargs):
    return {
        "decision": "pass",
        "issues": [],
    }


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
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["status"], "done")
            self.assertEqual(snapshot["status"]["counts"]["accepted"], 1)
            self.assertEqual(snapshot["status"]["counts"]["glossary_applied"], 1)
            self.assertEqual(target.read_text(encoding="utf-8"), "HOST_GROUP=host group\n")

    def test_translation_session_pending_regenerate_and_accept_replace_rhs_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "zh.properties"
            target = Path(temp_dir) / "en.properties"
            source.write_text("NETWORK_LINK_ADD=创建对等连接：{0}\n", encoding="utf-8")
            target.write_text("NETWORK_LINK_ADD=wrong value: {0}\n", encoding="utf-8")

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
                    "candidate_translation": "create peer connection:\n{0}",
                    "reason": "initial",
                }

            session = TranslationSession(
                source_path=source,
                target_path=target,
                glossary={"对等连接": "link"},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=fake_model,
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["counts"]["pending"], 1)
            pending_item = snapshot["pending_items"][0]
            self.assertIn("对等连接", pending_item["source_text"])
            self.assertIn("create link: {0}", pending_item["candidate_text"])
            self.assertEqual(pending_item["reason"], "现有英文翻译不够准确，建议更新为候选英文。")

            regenerated = session.regenerate(pending_item["id"], "更简洁一点")
            self.assertEqual(regenerated["status"]["counts"]["regenerated"], 1)
            self.assertEqual(
                regenerated["pending_items"][0]["reason"],
                "现有英文翻译不够准确，建议更新为候选英文。",
            )

            accepted = session.accept(pending_item["id"])
            self.assertEqual(accepted["status"]["counts"]["accepted"], 1)
            self.assertEqual(accepted["status"]["counts"]["appended"], 0)
            content = target.read_text(encoding="utf-8")
            self.assertIn("NETWORK_LINK_ADD=create link: {0}", content)
            self.assertNotIn("# Added by zh-audit 码值校译", content)
            self.assertNotIn("\n\n", content)
            self.assertGreaterEqual(len(calls), 2)

    def test_translation_session_retries_when_candidate_loses_placeholder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "zh.properties"
            target = Path(temp_dir) / "en.properties"
            source.write_text("NETWORK_LINK_ADD=创建对等连接：{0}\n", encoding="utf-8")
            target.write_text("NETWORK_LINK_ADD=wrong value: {0}\n", encoding="utf-8")

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
                    "candidate_translation": "create link",
                    "reason": "initial",
                }

            session = TranslationSession(
                source_path=source,
                target_path=target,
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=fake_model,
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["counts"]["pending"], 1)
            self.assertEqual(snapshot["pending_items"][0]["candidate_text"], "create link: {0}")
            self.assertGreaterEqual(len(calls), 2)

    def test_translation_session_allows_sentence_initial_capitalization_for_locked_terms(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "zh.properties"
            target = Path(temp_dir) / "en.properties"
            source.write_text("HOST_GROUP_EXCEPTION=主机组异常\n", encoding="utf-8")
            target.write_text("", encoding="utf-8")

            session = TranslationSession(
                source_path=source,
                target_path=target,
                glossary={"主机组": "host group"},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "candidate_translation": "Host group exception",
                    "reason": "ok",
                },
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            pending = snapshot["pending_items"][0]
            self.assertEqual(pending["validation_state"], "passed")
            self.assertTrue(pending["can_accept"])
            self.assertEqual(pending["candidate_text"], "Host group exception")

    def test_translation_session_appends_missing_target_key_after_accept(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "zh.properties"
            target = Path(temp_dir) / "en.properties"
            source.write_text("NETWORK_LINK_ADD=创建对等连接：{0}\n", encoding="utf-8")
            target.write_text("", encoding="utf-8")

            session = TranslationSession(
                source_path=source,
                target_path=target,
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "candidate_translation": "create link: {0}",
                    "reason": "ok",
                },
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["counts"]["skipped"], 0)
            self.assertEqual(snapshot["status"]["counts"]["pending"], 1)
            self.assertEqual(snapshot["pending_items"][0]["target_text"], "")
            self.assertTrue(snapshot["pending_items"][0]["target_missing"])
            self.assertEqual(snapshot["events"][0]["label"], "待审批")

            accepted = session.accept(snapshot["pending_items"][0]["id"])
            self.assertEqual(accepted["status"]["counts"]["accepted"], 1)
            self.assertEqual(accepted["status"]["counts"]["appended"], 1)
            self.assertEqual(target.read_text(encoding="utf-8"), "NETWORK_LINK_ADD=create link: {0}\n")

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
                reviewer_runner=_pass_review,
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
        review_prompt = build_translation_review_system_prompt()
        self.assertIn("current_target_text is only the existing English value", review_prompt)
        self.assertIn("Do not fail merely because candidate_text differs from current_target_text.", review_prompt)

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
                reviewer_runner=_pass_review,
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
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["counts"]["skipped"], 1)
            self.assertEqual(snapshot["events"][0]["label"], "已跳过：翻译准确，无需更新")

    def test_translation_session_ignores_reviewer_issue_about_target_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "zh.properties"
            target = Path(temp_dir) / "en.properties"
            source.write_text("AUTH_RETRY=适配服务器无法处理请求站点连接需要更新认证信息，请重试。\n", encoding="utf-8")
            target.write_text("AUTH_RETRY=Adapter server is not ready for request.\n", encoding="utf-8")

            session = TranslationSession(
                source_path=source,
                target_path=target,
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "candidate_translation": "The adapter server cannot process the request because the site connection requires updated authentication. Please try again.",
                    "reason": "ok",
                },
                reviewer_runner=lambda **kwargs: {
                    "decision": "fail",
                    "issues": ["候选文本与目标文本不匹配"],
                },
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            pending = snapshot["pending_items"][0]
            self.assertEqual(pending["validation_state"], "passed")
            self.assertTrue(pending["can_accept"])
            self.assertEqual(pending["generation_attempts_used"], 1)
            self.assertEqual(pending["candidate_text"], "The adapter server cannot process the request because the site connection requires updated authentication. Please try again.")

    def test_translation_session_ignores_hallucinated_spelling_issue(self):
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
                    "candidate_translation": "Adapter service API not found.",
                    "reason": "ok",
                },
                reviewer_runner=lambda **kwargs: {
                    "decision": "fail",
                    "issues": ["拼写错误：'adpter' 应为 'adapter'"],
                },
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            pending = snapshot["pending_items"][0]
            self.assertEqual(pending["validation_state"], "passed")
            self.assertTrue(pending["can_accept"])
            self.assertEqual(pending["generation_attempts_used"], 1)

    def test_translation_session_marks_failed_candidate_unacceptable_after_retry_budget(self):
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
                    "candidate_translation": "适配服务接口不存在。",
                    "reason": "ok",
                },
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            pending = snapshot["pending_items"][0]
            self.assertEqual(pending["validation_state"], "failed")
            self.assertFalse(pending["can_accept"])
            self.assertEqual(pending["generation_attempts_used"], 5)
            self.assertIn("已重试 5 次仍未通过", pending["validation_message"])
            self.assertIn("失败原因：候选仍含中文", pending["validation_message"])
            self.assertIn("候选未通过校验：候选仍含中文", snapshot["events"][0]["label"])
            with self.assertRaises(ValueError):
                session.accept(pending["id"])


if __name__ == "__main__":
    unittest.main()
