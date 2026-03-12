import tempfile
import unittest
from pathlib import Path

from zh_audit.sql_translation_workflow import (
    SqlTranslationSession,
    parse_sql_translation_file,
    scan_sql_translation_directory,
)


class SqlTranslationWorkflowTest(unittest.TestCase):
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
                    "candidate_translation": "create peer connection: {0}",
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
            )
            session.start()
            output_path = Path(session.output_path)
            self.assertTrue(output_path.exists())
            self.assertIn("Generated by zh-audit SQL校译", output_path.read_text(encoding="utf-8"))

            session.run()
            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["counts"]["pending"], 2)
            by_source = dict((item["source_text"], item) for item in snapshot["pending_items"])
            self.assertEqual(by_source["创建对等连接：{0}"]["candidate_text"], "create link: {0}")

            session.accept(by_source["资源池"]["id"])
            session.reject(by_source["创建对等连接：{0}"]["id"])

            content = output_path.read_text(encoding="utf-8")
            self.assertIn("-- item:", content)
            self.assertIn("UPDATE t_demo SET name_en = 'resource pool' WHERE id = '1';", content)
            self.assertNotIn("create link: {0}", content)
            self.assertGreaterEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
