import tempfile
import unittest
from pathlib import Path

from zh_audit.model_client import ModelResponseFormatError
from zh_audit.sql_translation_workflow import (
    SqlTranslationSession,
    build_sql_translation_review_system_prompt,
    parse_sql_translation_file,
    scan_sql_translation_directory,
)
from zh_audit.terminology_xlsx import normalize_terminology_catalog


def _pass_review(**kwargs):
    return {
        "decision": "pass",
        "issues": [],
    }


class SqlTranslationWorkflowTest(unittest.TestCase):
    def test_sql_translation_review_prompt_treats_current_target_as_context_only(self):
        prompt = build_sql_translation_review_system_prompt()
        self.assertIn("current_target_text is only the existing English value", prompt)
        self.assertIn("Do not fail merely because candidate_text differs from current_target_text.", prompt)
        self.assertIn("Judge candidate_text against source_text, placeholders, locked_terms, and extra_prompt", prompt)

    def test_parse_sql_translation_file_handles_schema_multiline_and_escaped_strings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sql_path = Path(temp_dir) / "demo.sql"
            sql_path.write_text(
                "INSERT INTO `ibase`.`t_demo`\n"
                "(`id`, `name_zh`, `name_en`, `note`)\n"
                "VALUES\n"
                "('1', '资源池', 'resource pool', 'a''b'),\n"
                "('2', '创建对等连接：{0}', 'wrong', NOW());\n",
                encoding="utf-8",
            )

            parsed = parse_sql_translation_file(
                path=sql_path,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
            )

            self.assertEqual(len(parsed["rows"]), 2)
            self.assertEqual(parsed["rows"][0]["table_expression"], "`ibase`.`t_demo`")
            self.assertEqual(parsed["rows"][0]["primary_key_display"], "1")
            self.assertEqual(parsed["rows"][0]["source_text"], "资源池")
            self.assertEqual(parsed["rows"][1]["source_text"], "创建对等连接：{0}")
            self.assertEqual(parsed["rows"][1]["target_text"], "wrong")
            self.assertEqual(parsed["events"], [])

    def test_parse_sql_translation_file_skips_unsupported_insert_shapes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sql_path = Path(temp_dir) / "demo.sql"
            sql_path.write_text(
                "REPLACE INTO t_demo (id, name_zh, name_en) VALUES ('1', '中文', 'English');\n"
                "INSERT INTO t_demo SELECT * FROM other_table;\n"
                "INSERT INTO t_demo VALUES ('2', '中文', 'English');\n",
                encoding="utf-8",
            )

            parsed = parse_sql_translation_file(
                path=sql_path,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
            )

            reasons = [item["target_text"] for item in parsed["events"]]
            self.assertIn("REPLACE INTO 暂不支持。", reasons)
            self.assertIn("仅支持 INSERT ... VALUES 语句。", reasons)
            self.assertIn("未显式声明列名，暂不支持。", reasons)

    def test_scan_sql_translation_directory_marks_duplicate_primary_keys(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "a.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '资源池', 'wrong');\n",
                encoding="utf-8",
            )
            (root / "nested").mkdir()
            (root / "nested" / "b.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '资源池', 'wrong again');\n",
                encoding="utf-8",
            )

            parsed = scan_sql_translation_directory(
                directory_path=root,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
            )

            self.assertEqual(len(parsed["rows"]), 2)
            self.assertTrue(all(item["skip_reason"] == "主键值重复，无法唯一定位 update。" for item in parsed["rows"]))

    def test_sql_translation_session_creates_output_and_appends_only_on_accept(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES\n"
                "('1', '资源池', 'wrong'),\n"
                "('2', '创建对等连接：{0}', 'wrong');\n",
                encoding="utf-8",
            )

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
                    "candidate_translation": "create peer connection",
                    "reason": "initial",
                }

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
                glossary={"资源池": "resource pool", "对等连接": "link"},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=fake_model,
                reviewer_runner=_pass_review,
            )
            session.start()
            output_path = Path(session.output_path)
            self.assertTrue(output_path.exists())
            self.assertIn("Generated by zh-audit SQL校译", output_path.read_text(encoding="utf-8"))

            session.run(lambda: False)
            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["counts"]["pending"], 2)
            by_source = dict((item["source_text"], item) for item in snapshot["pending_items"])
            self.assertEqual(by_source["创建对等连接：{0}"]["candidate_text"], "create link: {0}")
            self.assertEqual(by_source["创建对等连接：{0}"]["validation_state"], "passed")
            self.assertTrue(by_source["创建对等连接：{0}"]["can_accept"])
            self.assertIn("上一版候选未通过系统校验，请严格修复这个问题：", calls[-1]["extra_prompt"])

            session.accept(by_source["资源池"]["id"])
            session.reject(by_source["创建对等连接：{0}"]["id"])

            content = output_path.read_text(encoding="utf-8")
            self.assertIn("-- item:", content)
            self.assertIn("UPDATE t_demo SET name_en = 'resource pool' WHERE id = '1';", content)
            self.assertNotIn("create link: {0}", content)
            self.assertGreaterEqual(len(calls), 2)

    def test_sql_translation_regenerate_passes_extra_prompt_to_reviewer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '适配服务接口不存在。', 'API not found in adapter server.');\n",
                encoding="utf-8",
            )

            review_calls = []

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "candidate_translation": "Cloud server API not found.",
                    "reason": "ok",
                },
                reviewer_runner=lambda **kwargs: review_calls.append(kwargs) or {
                    "decision": "pass",
                    "issues": [],
                },
            )
            session.start()
            session.run(lambda: False)

            pending_item = session.snapshot()["pending_items"][0]
            session.regenerate(pending_item["id"], "把 server 统一替换为 cloud server")

            self.assertEqual(review_calls[-1]["extra_prompt"], "把 server 统一替换为 cloud server")

    def test_sql_translation_session_marks_failed_candidate_unacceptable_after_retry_budget(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '适配服务接口不存在。', 'API not found in adapter server.');\n",
                encoding="utf-8",
            )

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
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
            accepted = session.accept(pending["id"], candidate_text="Adapter service API not found.")
            self.assertEqual(accepted["status"]["counts"]["accepted"], 1)
            self.assertEqual(accepted["recent_items"][0]["target_text"], "Adapter service API not found.")

    def test_sql_translation_session_ignores_frontend_module_terms(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '用户操作超出权限范围。', 'user no operation permission.');\n",
                encoding="utf-8",
            )
            glossary = normalize_terminology_catalog({"权限范围": "permission scope"})
            glossary.add_entry(module="前端", source="操作", target="Operate")

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
                glossary=glossary.non_frontend_glossary,
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "candidate_translation": "User operation exceeds permission scope.",
                    "reason": "ok",
                },
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            pending = session.snapshot()["pending_items"][0]
            self.assertEqual(pending["validation_state"], "passed")
            self.assertTrue(pending["can_accept"])

    def test_sql_translation_session_allows_sentence_initial_capitalization_for_locked_terms(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '主机组异常', '');\n",
                encoding="utf-8",
            )

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
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

    def test_sql_translation_session_ignores_reviewer_issue_about_target_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '适配服务器无法处理请求站点连接需要更新认证信息，请重试。', 'Adapter server is not ready for request.');\n",
                encoding="utf-8",
            )

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
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

    def test_sql_translation_session_retries_retryable_model_format_errors_without_interrupting_task(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '主机组异常', 'Host group exception');\n",
                encoding="utf-8",
            )

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=lambda **kwargs: (_ for _ in ()).throw(
                    ValueError('模型响应不是合法 JSON：{"verdict": “needs_update”, "candidate_translation": "x"}')
                ),
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            pending = snapshot["pending_items"][0]
            self.assertEqual(snapshot["status"]["status"], "done")
            self.assertEqual(pending["validation_state"], "failed")
            self.assertFalse(pending["can_accept"])
            self.assertEqual(pending["generation_attempts_used"], 5)
            self.assertIn("模型返回格式不规范", pending["validation_message"])
            self.assertIn("候选未通过校验：模型返回格式不规范", snapshot["events"][0]["label"])

    def test_sql_translation_session_keeps_raw_model_debug_text_for_format_errors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('17020009', '可用区不能为空。', 'az can not be null.');\n",
                encoding="utf-8",
            )

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=lambda **kwargs: (_ for _ in ()).throw(
                    ModelResponseFormatError(
                        "Model response does not contain a valid JSON object: verdict=needs_update",
                        raw_response='{"choices":[{"message":{"content":"verdict=needs_update\\ncandidate_translation=AZ cannot be empty.\\nreason=现有英文过于简略。"}}]}',
                        raw_content="verdict=needs_update\ncandidate_translation=AZ cannot be empty.\nreason=现有英文过于简略。",
                        parse_error_detail="Model response does not contain a valid JSON object: verdict=needs_update; parser error: Expecting value: line 1 column 1 (char 0)",
                        extracted_candidate_text="AZ cannot be empty.",
                        extracted_reason="现有英文过于简略。",
                    )
                ),
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            pending = session.snapshot()["pending_items"][0]
            self.assertEqual(pending["failure_phase"], "模型")
            self.assertEqual(pending["candidate_text"], "AZ cannot be empty.")
            self.assertEqual(pending["raw_candidate_text"], "AZ cannot be empty.")
            self.assertIn("candidate_translation=AZ cannot be empty.", pending["raw_failure_content"])
            self.assertEqual(pending["raw_reason_text"], "现有英文过于简略。")
            self.assertIn("parser error", pending["parse_error_detail"])
            self.assertIn('"choices"', pending["raw_failure_response"])

    def test_sql_translation_session_auto_accept_appends_candidate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '资源池', 'wrong');\n",
                encoding="utf-8",
            )

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
                glossary={"资源池": "resource pool"},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "candidate_translation": "resource pool",
                    "reason": "ok",
                },
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: True)

            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["status"], "done")
            self.assertEqual(snapshot["status"]["counts"]["accepted"], 1)
            self.assertEqual(snapshot["status"]["counts"]["pending"], 0)
            self.assertEqual(snapshot["events"][0]["label"], "已自动审批")
            self.assertIn(
                "UPDATE t_demo SET name_en = 'resource pool' WHERE id = '1';",
                Path(session.output_path).read_text(encoding="utf-8"),
            )

    def test_sql_translation_manual_accept_rejects_missing_placeholders(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '创建对等连接：{0}', 'wrong');\n",
                encoding="utf-8",
            )

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "candidate_translation": "Create peering connection: {0}",
                    "reason": "ok",
                },
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            pending = session.snapshot()["pending_items"][0]
            with self.assertRaisesRegex(ValueError, "lost placeholders"):
                session.accept(pending["id"], candidate_text="Create peering connection.")

            still_pending = session.snapshot()["pending_items"][0]
            self.assertEqual(still_pending["id"], pending["id"])
            self.assertEqual(still_pending["candidate_text"], "Create peering connection: {0}")


if __name__ == "__main__":
    unittest.main()
