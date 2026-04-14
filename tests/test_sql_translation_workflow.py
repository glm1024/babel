import tempfile
import unittest
from pathlib import Path

from zh_audit.model_client import ModelResponseFormatError
from zh_audit.sql_translation_workflow import (
    SqlTranslationSession,
    build_sql_translation_review_system_prompt,
    build_sql_translation_review_user_prompt,
    build_sql_translation_system_prompt,
    build_sql_translation_user_prompt,
    parse_sql_translation_file,
    scan_sql_translation_directory,
)
from zh_audit.terminology_xlsx import normalize_terminology_catalog


def _pass_review(**kwargs):
    return {
        "decision": "pass",
        "issues": [],
    }


def _standard_model_config(max_tokens=100, **overrides):
    config = {
        "base_url": "http://example/v1",
        "api_key": "sk",
        "model": "demo",
        "max_tokens": max_tokens,
        "execution_strategy": "standard",
    }
    config.update(overrides)
    return config


class SqlTranslationWorkflowTest(unittest.TestCase):
    def test_sql_translation_session_processing_log_keeps_recent_1000_events(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '中文', 'English');\n",
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
                model_runner=lambda **kwargs: {"verdict": "accurate", "candidate_translation": "English", "reason": "ok"},
                reviewer_runner=_pass_review,
                rows=[],
                scan_events=[],
            )

            for index in range(1005):
                session._push_event(
                    "测试",
                    {
                        "source_path": "demo.sql",
                        "line": index + 1,
                        "primary_key_display": str(index),
                        "source_text": "源文案 {}".format(index),
                        "reason": "",
                        "parse_phase": "",
                        "statement_preview": "",
                    },
                    "译文 {}".format(index),
                )

            self.assertEqual(len(session.events), 1000)
            self.assertEqual(session.events[0]["line"], 1005)
            self.assertEqual(session.events[-1]["line"], 6)

    def test_sql_translation_review_prompt_ignores_previous_english_value(self):
        prompt = build_sql_translation_review_system_prompt()
        self.assertIn("Judge candidate_text against source_text, placeholders, locked_terms, and extra_prompt", prompt)
        self.assertIn("Ignore any previous English wording.", prompt)
        self.assertNotIn("current_target_text", prompt)
        self.assertIn("Treat locked_terms matching as case-insensitive.", prompt)
        self.assertIn("Do not report that a term should be X if candidate_text already contains X.", prompt)
        self.assertIn("Do not treat style-only suggestions such as 'could be more natural' as hard failures.", prompt)
        self.assertIn("For object issues, message and evidence must be written in Simplified Chinese.", prompt)
        self.assertIn("Do not output English in message or evidence unless it is a required technical term", prompt)
        self.assertIn("keeps Chinese-style punctuation in otherwise English text", prompt)
        self.assertIn(
            "issues must be either an array of short Simplified Chinese strings or an array of objects with keys code, message, severity, evidence, and expected_term.",
            prompt,
        )

    def test_sql_translation_system_prompt_requires_chinese_reason(self):
        prompt = build_sql_translation_system_prompt()
        self.assertIn("reason must be written in Simplified Chinese.", prompt)
        self.assertIn("Do not output English in reason unless it is a required technical term quoted", prompt)
        self.assertIn("Use standard half-width English punctuation.", prompt)

    def test_sql_translation_session_normalizes_cjk_punctuation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '单击“确定”按钮。', '');\n",
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
                    "candidate_translation": 'Click “OK” button。',
                    "reason": "ok",
                },
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            pending = session.snapshot()["pending_items"][0]
            self.assertEqual(pending["candidate_text"], 'Click "OK" button.')

    def test_sql_translation_session_reuses_non_han_source_text_without_model_call(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES\n"
                "('1', 'VPC', ''),\n"
                "('2', 'AZ', 'AZ');\n",
                encoding="utf-8",
            )

            def fail_if_called(**kwargs):
                raise AssertionError("model_runner should not be called for non-Han source text")

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=fail_if_called,
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["counts"]["pending"], 0)
            self.assertEqual(snapshot["status"]["counts"]["skipped"], 1)
            self.assertEqual(snapshot["status"]["counts"]["accepted"], 1)
            self.assertEqual(snapshot["status"]["counts"]["appended"], 1)
            self.assertEqual(snapshot["pending_items"], [])
            accepted = snapshot["recent_items"][0]
            self.assertEqual(accepted["source_text"], "VPC")
            self.assertEqual(accepted["target_text"], "VPC")
            self.assertEqual(accepted["candidate_text"], "VPC")
            self.assertEqual(accepted["status"], "accepted")
            self.assertEqual(accepted["validation_state"], "passed")
            self.assertTrue(accepted["can_accept"])
            self.assertEqual(accepted["generation_attempts_used"], 0)
            self.assertEqual(accepted["model_calls_used"], 0)
            output = Path(snapshot["status"]["output_path"]).read_text(encoding="utf-8")
            self.assertIn("UPDATE t_demo SET name_en = 'VPC' WHERE id = '1';", output)

    def test_sql_translation_user_prompt_omits_sql_trace_fields(self):
        prompt = build_sql_translation_user_prompt(
            source_path="demo.sql",
            line=12,
            table_name="t_demo",
            primary_key_field="id",
            primary_key_value="1",
            source_field="name_zh",
            source_text="删除云物理机",
            target_field="name_en",
            target_text="delete cloud host",
            target_missing=False,
            locked_terms=[{"source": "云物理机", "target": "cloud physical machine"}],
            extra_prompt="",
        )
        self.assertIn('"source_text": "删除云物理机"', prompt)
        self.assertIn('"target_text": "delete cloud host"', prompt)
        self.assertNotIn("source_path", prompt)
        self.assertNotIn("table_name", prompt)
        self.assertNotIn("primary_key_field", prompt)
        self.assertNotIn("primary_key_value", prompt)
        self.assertNotIn("source_field", prompt)
        self.assertNotIn("target_field", prompt)

    def test_sql_translation_review_user_prompt_does_not_include_current_target_text(self):
        prompt = build_sql_translation_review_user_prompt(
            source_path="demo.sql",
            line=12,
            table_name="t_demo",
            primary_key_field="id",
            primary_key_value="1",
            source_field="name_zh",
            source_text="删除云物理机",
            target_field="name_en",
            candidate_text="delete cloud physical machine instance",
            target_missing=False,
            locked_terms=[{"source": "云物理机", "target": "cloud physical machine"}],
            extra_prompt="",
        )
        self.assertIn('"candidate_text": "delete cloud physical machine instance"', prompt)
        self.assertNotIn("current_target_text", prompt)
        self.assertNotIn("source_path", prompt)
        self.assertNotIn("table_name", prompt)
        self.assertNotIn("primary_key_field", prompt)
        self.assertNotIn("primary_key_value", prompt)
        self.assertNotIn("source_field", prompt)
        self.assertNotIn("target_field", prompt)

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
            self.assertIn("INSERT 未写列名，且未能推导当前表结构，请粘贴当前建表 SQL。", reasons)

    def test_scan_sql_translation_directory_keeps_latest_duplicate_by_script_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "V6.10.0.20230721.0__seed.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '资源池', 'wrong');\n",
                encoding="utf-8",
            )
            (root / "V6.10.0.20230830.0__seed.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '资源池', 'newest value');\n",
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
            skipped = [item for item in parsed["rows"] if item["skip_reason"]]
            kept = [item for item in parsed["rows"] if not item["skip_reason"]]
            self.assertEqual(len(skipped), 1)
            self.assertEqual(len(kept), 1)
            self.assertEqual(kept[0]["target_text"], "newest value")
            self.assertIn("V6.10.0.20230830.0__seed.sql", skipped[0]["skip_reason"])

    def test_parse_sql_translation_file_keeps_statement_preview_for_skip_events(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sql_path = Path(temp_dir) / "demo.sql"
            sql_path.write_text(
                "INSERT INTO t_demo VALUES ('1', '中文', 'English');\n",
                encoding="utf-8",
            )

            parsed = parse_sql_translation_file(
                path=sql_path,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
            )

            self.assertEqual(parsed["events"][0]["reason"], "INSERT 未写列名，且未能推导当前表结构，请粘贴当前建表 SQL。")
            self.assertEqual(parsed["events"][0]["parse_phase"], "DDL 自动推导")
            self.assertIn("INSERT INTO t_demo VALUES", parsed["events"][0]["statement_preview"])

    def test_scan_sql_translation_directory_inferrs_schema_for_insert_without_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "001_schema.sql").write_text(
                "CREATE TABLE t_demo (\n"
                "  id varchar(32) NOT NULL,\n"
                "  name_zh varchar(255) NOT NULL,\n"
                "  name_en varchar(255) DEFAULT NULL,\n"
                "  PRIMARY KEY (id)\n"
                ");\n",
                encoding="utf-8",
            )
            (root / "002_data.sql").write_text(
                "INSERT INTO t_demo VALUES ('1', '资源池', 'resource pool');\n",
                encoding="utf-8",
            )

            parsed = scan_sql_translation_directory(
                directory_path=root,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
            )

            self.assertEqual(parsed["schema_source"], "目录自动推导")
            self.assertEqual(parsed["schema_error"], "")
            self.assertEqual(len(parsed["rows"]), 1)
            self.assertEqual(parsed["rows"][0]["primary_key_display"], "1")
            self.assertEqual(parsed["rows"][0]["source_text"], "资源池")
            self.assertEqual(parsed["rows"][0]["target_text"], "resource pool")
            self.assertTrue(any(item["label"] == "Schema 已就绪" for item in parsed["events"]))

    def test_scan_sql_translation_directory_replays_alter_table_column_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "001_schema.sql").write_text(
                "CREATE TABLE t_demo (\n"
                "  id varchar(32) NOT NULL,\n"
                "  name_zh varchar(255) NOT NULL,\n"
                "  name_en varchar(255) DEFAULT NULL,\n"
                ");\n",
                encoding="utf-8",
            )
            (root / "002_alter.sql").write_text(
                "ALTER TABLE t_demo ADD COLUMN code varchar(32) AFTER id;\n"
                "ALTER TABLE t_demo CHANGE COLUMN name_zh zh_name varchar(255) AFTER code;\n"
                "ALTER TABLE t_demo MODIFY COLUMN name_en varchar(255) AFTER zh_name;\n",
                encoding="utf-8",
            )
            (root / "003_data.sql").write_text(
                "INSERT INTO t_demo VALUES ('1', 'C1', '中文名', 'English name');\n",
                encoding="utf-8",
            )

            parsed = scan_sql_translation_directory(
                directory_path=root,
                table_name="t_demo",
                primary_key_field="id",
                source_field="zh_name",
                target_field="name_en",
            )

            self.assertEqual(parsed["schema_error"], "")
            self.assertEqual(len(parsed["rows"]), 1)
            self.assertEqual(parsed["rows"][0]["primary_key_display"], "1")
            self.assertEqual(parsed["rows"][0]["source_text"], "中文名")
            self.assertEqual(parsed["rows"][0]["target_text"], "English name")

    def test_scan_sql_translation_directory_prefers_manual_schema_sql(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "001_data.sql").write_text(
                "INSERT INTO t_demo VALUES ('1', '资源池', 'resource pool');\n",
                encoding="utf-8",
            )

            parsed = scan_sql_translation_directory(
                directory_path=root,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
                schema_sql=(
                    "CREATE TABLE t_demo (\n"
                    "  id varchar(32) NOT NULL,\n"
                    "  name_zh varchar(255) NOT NULL,\n"
                    "  name_en varchar(255) DEFAULT NULL\n"
                    ");"
                ),
            )

            self.assertEqual(parsed["schema_source"], "手工建表 SQL")
            self.assertEqual(parsed["schema_error"], "")
            self.assertEqual(len(parsed["rows"]), 1)
            self.assertEqual(parsed["rows"][0]["source_text"], "资源池")

    def test_scan_sql_translation_directory_reports_schema_inference_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "001_schema.sql").write_text(
                "CREATE TABLE t_demo (id varchar(32), name_zh varchar(255), name_en varchar(255));\n",
                encoding="utf-8",
            )
            (root / "002_alter.sql").write_text(
                "ALTER TABLE t_demo ADD INDEX idx_name_zh (name_zh);\n",
                encoding="utf-8",
            )
            (root / "003_data.sql").write_text(
                "INSERT INTO t_demo VALUES ('1', '资源池', 'resource pool');\n",
                encoding="utf-8",
            )

            parsed = scan_sql_translation_directory(
                directory_path=root,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
            )

            self.assertEqual(parsed["schema_source"], "")
            self.assertIn("不支持的索引或约束变更", parsed["schema_error"])
            self.assertTrue(any("不支持的索引或约束变更" in item["reason"] for item in parsed["events"]))
            self.assertTrue(any("INSERT 未写列名" in item["reason"] for item in parsed["events"]))

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
                model_config=_standard_model_config(),
                model_runner=fake_model,
                reviewer_runner=_pass_review,
            )
            session.start()
            output_path = Path(session.output_path)
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "")

            session.run(lambda: False)
            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["counts"]["pending"], 2)
            by_source = dict((item["source_text"], item) for item in snapshot["pending_items"])
            self.assertEqual(by_source["创建对等连接：{0}"]["candidate_text"], "create link: {0}")
            self.assertEqual(by_source["创建对等连接：{0}"]["validation_state"], "passed")
            self.assertTrue(by_source["创建对等连接：{0}"]["can_accept"])
            self.assertIn("retry_context JSON:", calls[-1]["extra_prompt"])
            self.assertIn('"phase": "local_validation"', calls[-1]["extra_prompt"])
            self.assertIn('"must_use_terms"', calls[-1]["extra_prompt"])

            session.accept(by_source["资源池"]["id"])
            session.reject(by_source["创建对等连接：{0}"]["id"])

            content = output_path.read_text(encoding="utf-8")
            self.assertIn("UPDATE t_demo SET name_en = 'Resource pool' WHERE id = '1';", content)
            self.assertNotIn("create link: {0}", content)
            self.assertNotIn("--", content)
            self.assertGreaterEqual(len(calls), 2)

    def test_sql_translation_session_default_think_fast_skips_reviewer_and_limits_to_one_attempt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '适配服务接口不存在。', 'API not found in adapter server.');\n",
                encoding="utf-8",
            )

            model_calls = []
            review_calls = []

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=lambda **kwargs: model_calls.append(kwargs) or {
                    "verdict": "needs_update",
                    "candidate_translation": "适配服务接口不存在。",
                    "reason": "ok",
                },
                reviewer_runner=lambda **kwargs: review_calls.append(kwargs) or _pass_review(**kwargs),
            )
            session.start()
            session.run(lambda: False)

            pending = session.snapshot()["pending_items"][0]
            self.assertEqual(pending["validation_state"], "failed")
            self.assertEqual(pending["generation_attempts_used"], 1)
            self.assertEqual(len(model_calls), 1)
            self.assertEqual(review_calls, [])

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
                model_config=_standard_model_config(),
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
                model_config=_standard_model_config(),
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
            self.assertEqual(pending["generation_attempts_used"], 3)
            self.assertIn("已重试 3 次仍未通过", pending["validation_message"])
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

    def test_sql_translation_session_normalizes_locked_term_case_mid_sentence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '裸金属服务器名称超过最大长度。', '');\n",
                encoding="utf-8",
            )

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
                glossary={"裸金属服务器": "Bare Metal Server"},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "candidate_translation": "The Bare Metal Server name exceeds the maximum length.",
                    "reason": "ok",
                },
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            pending = session.snapshot()["pending_items"][0]
            self.assertEqual(pending["candidate_text"], "The bare metal server name exceeds the maximum length.")

    def test_sql_translation_session_normalizes_exact_glossary_term_case_for_sentence_start(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            sql_path = sql_dir / "demo.sql"
            sql_path.write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '裸金属服务器', '');\n",
                encoding="utf-8",
            )

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
                glossary={"裸金属服务器": "Bare Metal Server"},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=lambda **kwargs: (_ for _ in ()).throw(AssertionError("model should not be called")),
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["counts"]["pending"], 1)
            self.assertEqual(snapshot["pending_items"][0]["candidate_text"], "Bare metal server")

    def test_sql_translation_session_ignores_case_only_terminology_review_issue(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '删除镜像', '');\n",
                encoding="utf-8",
            )

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
                glossary={"镜像": "Image"},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "candidate_translation": "delete image",
                    "reason": "ok",
                },
                reviewer_runner=lambda **kwargs: {
                    "decision": "fail",
                    "issues": ["术语不一致：'镜像'应翻译为'Image'，但'Image'未大写"],
                },
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            pending = snapshot["pending_items"][0]
            self.assertEqual(pending["validation_state"], "passed")
            self.assertTrue(pending["can_accept"])
            self.assertEqual(pending["candidate_text"], "delete image")

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

    def test_sql_translation_session_falls_back_to_chinese_reason_for_english_prose(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '云主机解绑浮动ip', 'VM remove floating ip');\n",
                encoding="utf-8",
            )

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
                glossary={"云主机": "Elastic Compute Service"},
                model_config=_standard_model_config(),
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "candidate_translation": "Elastic Compute Service unbind Floating IP",
                    "reason": "The term '云主机' must be translated as 'Elastic Compute Service' per locked_terms. Also, 'remove' should be 'unbind'.",
                },
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            pending = session.snapshot()["pending_items"][0]
            self.assertEqual(pending["reason"], "模型建议更新英文翻译。")
            self.assertEqual(pending["attempt_history"][0]["reason"], "模型建议更新英文翻译。")

    def test_sql_translation_session_normalizes_english_review_issue_to_chinese(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '云主机解绑浮动ip', 'VM remove floating ip');\n",
                encoding="utf-8",
            )

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
                glossary={"云主机": "Elastic Compute Service"},
                model_config=_standard_model_config(),
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "candidate_translation": "Elastic Compute Service unbind Floating IP",
                    "reason": "建议更新术语。",
                },
                reviewer_runner=lambda **kwargs: {
                    "decision": "fail",
                    "issues": [
                        {
                            "code": "terminology",
                            "message": "The term 'Floating IP' should be 'EIP' as per standard terminology.",
                            "expected_term": "EIP",
                        }
                    ],
                },
            )
            session.start()
            session.run(lambda: False)

            pending = session.snapshot()["pending_items"][0]
            self.assertEqual(pending["validation_state"], "failed")
            self.assertIn("术语不一致：应使用'EIP'，请重新生成", pending["validation_message"])
            self.assertEqual(pending["retry_context_preview"], "AI复核：术语不一致：应使用'EIP'")
            self.assertEqual(pending["attempt_history"][0]["failure_issue"], "术语不一致：应使用'EIP'")

    def test_sql_translation_session_downgrades_style_review_suggestion_to_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '删除目录', '');\n",
                encoding="utf-8",
            )

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
                glossary={},
                model_config=_standard_model_config(),
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "candidate_translation": "Delete directory",
                    "reason": "ok",
                },
                reviewer_runner=lambda **kwargs: {
                    "decision": "fail",
                    "issues": [
                        {
                            "code": "style",
                            "message": "表达可更自然，建议调整措辞",
                            "severity": "warning",
                        }
                    ],
                },
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            pending = snapshot["pending_items"][0]
            self.assertEqual(pending["validation_state"], "passed")
            self.assertTrue(pending["can_accept"])
            self.assertEqual(pending["warnings"], ["表达可更自然，建议调整措辞"])

    def test_sql_translation_session_ignores_expected_term_issue_when_term_already_present(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '删除云物理机', '');\n",
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
                    "candidate_translation": "Delete Cloud Physical Server instance",
                    "reason": "ok",
                },
                reviewer_runner=lambda **kwargs: {
                    "decision": "fail",
                    "issues": [
                        {
                            "code": "missing_term",
                            "message": "未准确翻译，'云物理机'应为'Cloud Physical Server'",
                            "expected_term": "Cloud Physical Server",
                        }
                    ],
                },
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            pending = snapshot["pending_items"][0]
            self.assertEqual(pending["validation_state"], "passed")
            self.assertTrue(pending["can_accept"])
            self.assertEqual(pending["candidate_text"], "Delete Cloud Physical Server instance")

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
                model_config=_standard_model_config(),
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
            self.assertEqual(pending["generation_attempts_used"], 3)
            self.assertIn("模型返回格式不规范", pending["validation_message"])
            self.assertIn("候选生成失败：模型返回格式不规范", snapshot["events"][0]["label"])

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
                "UPDATE t_demo SET name_en = 'Resource pool' WHERE id = '1';",
                Path(session.output_path).read_text(encoding="utf-8"),
            )

    def test_sql_translation_restore_keeps_written_item_ids_without_sql_comments(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '资源池', '');\n"
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('2', '创建对等连接：{0}', '');\n",
                encoding="utf-8",
            )

            def fake_model(**kwargs):
                if kwargs["source_text"] == "资源池":
                    return {
                        "verdict": "needs_update",
                        "candidate_translation": "Resource pool",
                        "reason": "ok",
                    }
                return {
                    "verdict": "needs_update",
                    "candidate_translation": "Create peering connection: {0}",
                    "reason": "ok",
                }

            session = SqlTranslationSession(
                directory_path=sql_dir,
                table_name="t_demo",
                primary_key_field="id",
                source_field="name_zh",
                target_field="name_en",
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=fake_model,
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            first_pending = next(item for item in session.snapshot()["pending_items"] if item["source_text"] == "资源池")
            session.accept(first_pending["id"])
            saved = session.save_state()

            restored = SqlTranslationSession.from_saved_state(
                saved,
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                model_runner=fake_model,
                reviewer_runner=_pass_review,
            )

            self.assertEqual(restored.written_item_ids, {first_pending["id"]})
            content = Path(restored.output_path).read_text(encoding="utf-8")
            self.assertNotIn("--", content)
            self.assertEqual(content.count("UPDATE "), 1)

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
