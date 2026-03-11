import csv
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from zh_audit.pipeline import _iter_git_paths as iter_scan_git_paths
from zh_audit.validation import validate_report
from zh_audit.validation import _iter_git_paths as iter_validation_git_paths


class ValidationSmokeTest(unittest.TestCase):
    def test_git_z_output_accepts_bytes_and_text(self) -> None:
        expected = ["src/App.java", "templates/error.html"]
        raw_bytes = b"src/App.java\x00templates/error.html\x00"
        raw_text = "src/App.java\x00templates/error.html\x00"

        self.assertEqual(iter_scan_git_paths(raw_bytes), expected)
        self.assertEqual(iter_scan_git_paths(raw_text), expected)
        self.assertEqual(iter_validation_git_paths(raw_bytes), expected)
        self.assertEqual(iter_validation_git_paths(raw_text), expected)

    def test_validate_report_generates_deliverables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            template = repo / "templates" / "error.html"
            template.parent.mkdir(parents=True)
            template.write_text('<div title="noop">操作异常！</div>\n', encoding="utf-8")

            java_file = repo / "src" / "App.java"
            java_file.parent.mkdir(parents=True)
            java_file.write_text(
                'class App { Object fail(){ return AjaxResult.warn("菜单已分配,不允许删除"); } }\n',
                encoding="utf-8",
            )

            vendor_file = repo / "static" / "ajax" / "libs" / "vendor.js"
            vendor_file.parent.mkdir(parents=True)
            vendor_file.write_text('const title = "第三方控件";\n', encoding="utf-8")

            subprocess.run(
                ["git", "add", "."],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            findings_path = root / "findings.json"
            summary_path = root / "summary.json"
            out_dir = root / "validation"

            findings_path.write_text(
                json.dumps(
                    [
                        {
                            "project": "repo",
                            "path": "src/App.java",
                            "line": 1,
                            "category": "PROTOCOL_OR_PERSISTED_LITERAL",
                            "action": "review",
                            "surface_kind": "string_literal",
                            "normalized_text": "菜单已分配,不允许删除",
                            "text": "菜单已分配,不允许删除",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            summary_path.write_text(
                json.dumps(
                    {
                        "run_id": "demo",
                        "eligible_files": 2,
                        "skipped_files": 1,
                        "scan_policy": {
                            "exclude_globs": ["**/static/ajax/libs/**"],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = validate_report(
                repo_root=repo,
                summary_path=summary_path,
                findings_path=findings_path,
                out_dir=out_dir,
            )

            self.assertEqual(result["verdict"], "FAIL")
            self.assertTrue((out_dir / "validation_summary.md").exists())
            self.assertTrue((out_dir / "coverage_diff.csv").exists())
            self.assertTrue((out_dir / "classification_review.csv").exists())

            summary_text = (out_dir / "validation_summary.md").read_text(encoding="utf-8")
            self.assertIn("最终判定：`FAIL`", summary_text)
            self.assertIn("templates/error.html", summary_text)
            self.assertIn("未达标分项：`PROTOCOL_OR_PERSISTED_LITERAL`", summary_text)

            with (out_dir / "coverage_diff.csv").open(encoding="utf-8", newline="") as handle:
                coverage_rows = list(csv.DictReader(handle))
            self.assertTrue(any(row["path"] == "templates/error.html" for row in coverage_rows))
            self.assertFalse(any(row["path"] == "static/ajax/libs/vendor.js" for row in coverage_rows))

            with (out_dir / "classification_review.csv").open(encoding="utf-8", newline="") as handle:
                review_rows = list(csv.DictReader(handle))
            self.assertTrue(
                any(
                    row["path"] == "src/App.java"
                    and row["reported_category"] == "PROTOCOL_OR_PERSISTED_LITERAL"
                    and row["expected_category"] == "ERROR_VALIDATION_MESSAGE"
                    for row in review_rows
                )
            )

    def test_validate_report_matches_condition_expression_literal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            java_file = repo / "src" / "ConditionExpressions.java"
            java_file.parent.mkdir(parents=True)
            java_file.write_text(
                'class ConditionExpressions { boolean check(String message) { if (message.contains("SnowFlakeGenerator:时钟回拨")) { return true; } return false; } }\n',
                encoding="utf-8",
            )

            subprocess.run(
                ["git", "add", "."],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            findings_path = root / "findings.json"
            summary_path = root / "summary.json"
            out_dir = root / "validation"

            findings_path.write_text(
                json.dumps(
                    [
                        {
                            "project": "repo",
                            "path": "src/ConditionExpressions.java",
                            "line": 1,
                            "category": "CONDITION_EXPRESSION_LITERAL",
                            "action": "keep",
                            "surface_kind": "string_literal",
                            "normalized_text": "SnowFlakeGenerator:时钟回拨",
                            "text": "SnowFlakeGenerator:时钟回拨",
                            "hit_text": "时钟回拨",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            summary_path.write_text(
                json.dumps(
                    {
                        "run_id": "condition-demo",
                        "eligible_files": 1,
                        "skipped_files": 0,
                        "scan_policy": {
                            "exclude_globs": ["**/static/ajax/libs/**"],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            validate_report(
                repo_root=repo,
                summary_path=summary_path,
                findings_path=findings_path,
                out_dir=out_dir,
            )

            with (out_dir / "classification_review.csv").open(encoding="utf-8", newline="") as handle:
                review_rows = list(csv.DictReader(handle))
            self.assertTrue(
                any(
                    row["path"] == "src/ConditionExpressions.java"
                    and row["reported_category"] == "CONDITION_EXPRESSION_LITERAL"
                    and row["expected_category"] == "CONDITION_EXPRESSION_LITERAL"
                    and row["status"] == "match"
                    for row in review_rows
                )
            )

    def test_validate_report_matches_replace_style_condition_expression_literal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            java_file = repo / "src" / "ConditionExpressions.java"
            java_file.parent.mkdir(parents=True)
            java_file.write_text(
                'class ConditionExpressions { boolean check(String message) { if (message.replace("错误前缀:", "").equals("停止服务")) { return true; } return false; } }\n',
                encoding="utf-8",
            )

            subprocess.run(
                ["git", "add", "."],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            findings_path = root / "findings.json"
            summary_path = root / "summary.json"
            out_dir = root / "validation"

            findings_path.write_text(
                json.dumps(
                    [
                        {
                            "project": "repo",
                            "path": "src/ConditionExpressions.java",
                            "line": 1,
                            "category": "CONDITION_EXPRESSION_LITERAL",
                            "action": "keep",
                            "surface_kind": "string_literal",
                            "normalized_text": "错误前缀:",
                            "text": "错误前缀:",
                            "hit_text": "错误前缀",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            summary_path.write_text(
                json.dumps(
                    {
                        "run_id": "replace-demo",
                        "eligible_files": 1,
                        "skipped_files": 0,
                        "scan_policy": {
                            "exclude_globs": ["**/static/ajax/libs/**"],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            validate_report(
                repo_root=repo,
                summary_path=summary_path,
                findings_path=findings_path,
                out_dir=out_dir,
            )

            with (out_dir / "classification_review.csv").open(encoding="utf-8", newline="") as handle:
                review_rows = list(csv.DictReader(handle))
            self.assertTrue(
                any(
                    row["path"] == "src/ConditionExpressions.java"
                    and row["reported_category"] == "CONDITION_EXPRESSION_LITERAL"
                    and row["expected_category"] == "CONDITION_EXPRESSION_LITERAL"
                    and row["status"] == "match"
                    for row in review_rows
                )
            )

    def test_validate_report_matches_assert_api_condition_expression_literal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            java_file = repo / "src" / "ConditionExpressions.java"
            java_file.parent.mkdir(parents=True)
            java_file.write_text(
                'class ConditionExpressions { void guard(String value) { Assert.hasText(value, "名称不能为空"); } }\n',
                encoding="utf-8",
            )

            subprocess.run(
                ["git", "add", "."],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            findings_path = root / "findings.json"
            summary_path = root / "summary.json"
            out_dir = root / "validation"

            findings_path.write_text(
                json.dumps(
                    [
                        {
                            "project": "repo",
                            "path": "src/ConditionExpressions.java",
                            "line": 1,
                            "category": "CONDITION_EXPRESSION_LITERAL",
                            "action": "keep",
                            "surface_kind": "string_literal",
                            "normalized_text": "名称不能为空",
                            "text": "名称不能为空",
                            "hit_text": "名称不能为空",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            summary_path.write_text(
                json.dumps(
                    {
                        "run_id": "assert-demo",
                        "eligible_files": 1,
                        "skipped_files": 0,
                        "scan_policy": {
                            "exclude_globs": ["**/static/ajax/libs/**"],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            validate_report(
                repo_root=repo,
                summary_path=summary_path,
                findings_path=findings_path,
                out_dir=out_dir,
            )

            with (out_dir / "classification_review.csv").open(encoding="utf-8", newline="") as handle:
                review_rows = list(csv.DictReader(handle))
            self.assertTrue(
                any(
                    row["path"] == "src/ConditionExpressions.java"
                    and row["reported_category"] == "CONDITION_EXPRESSION_LITERAL"
                    and row["expected_category"] == "CONDITION_EXPRESSION_LITERAL"
                    and row["status"] == "match"
                    for row in review_rows
                )
            )

    def test_validate_report_matches_i18n_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            prop_file = repo / "config" / "i18n.messages.properties"
            prop_file.parent.mkdir(parents=True)
            prop_file.write_text("system.busy=系统繁忙\n", encoding="utf-8")

            subprocess.run(
                ["git", "add", "."],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            findings_path = root / "findings.json"
            summary_path = root / "summary.json"
            out_dir = root / "validation"

            findings_path.write_text(
                json.dumps(
                    [
                        {
                            "project": "repo",
                            "path": "config/i18n.messages.properties",
                            "line": 1,
                            "category": "I18N_FILE",
                            "action": "keep",
                            "surface_kind": "text",
                            "normalized_text": "system.busy=系统繁忙",
                            "text": "system.busy=系统繁忙",
                            "hit_text": "系统繁忙",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            summary_path.write_text(
                json.dumps(
                    {
                        "run_id": "i18n-demo",
                        "eligible_files": 1,
                        "skipped_files": 0,
                        "scan_policy": {
                            "exclude_globs": ["**/static/ajax/libs/**"],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            validate_report(
                repo_root=repo,
                summary_path=summary_path,
                findings_path=findings_path,
                out_dir=out_dir,
            )

            with (out_dir / "classification_review.csv").open(encoding="utf-8", newline="") as handle:
                review_rows = list(csv.DictReader(handle))
            self.assertTrue(
                any(
                    row["path"] == "config/i18n.messages.properties"
                    and row["reported_category"] == "I18N_FILE"
                    and row["expected_category"] == "I18N_FILE"
                    and row["status"] == "match"
                    for row in review_rows
                )
            )

    def test_validate_report_matches_multiline_task_description_annotation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(
                ["git", "init"],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            java_file = repo / "src" / "TaskDescriptionProcess.java"
            java_file.parent.mkdir(parents=True)
            java_file.write_text(
                "\n".join(
                    [
                        "class TaskDescriptionProcess {",
                        "    @AsynTask(",
                        '        opType = "JOB_DISABLE_HOST",',
                        "        description =",
                        '            "停用主机"',
                        "    )",
                        "    void disableHost() {}",
                        "}",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            subprocess.run(
                ["git", "add", "."],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            findings_path = root / "findings.json"
            summary_path = root / "summary.json"
            out_dir = root / "validation"

            findings_path.write_text(
                json.dumps(
                    [
                        {
                            "project": "repo",
                            "path": "src/TaskDescriptionProcess.java",
                            "line": 5,
                            "category": "TASK_DESCRIPTION",
                            "action": "keep",
                            "surface_kind": "string_literal",
                            "normalized_text": "停用主机",
                            "text": "停用主机",
                            "hit_text": "停用主机",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            summary_path.write_text(
                json.dumps(
                    {
                        "run_id": "task-description-demo",
                        "eligible_files": 1,
                        "skipped_files": 0,
                        "scan_policy": {
                            "exclude_globs": ["**/static/ajax/libs/**"],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            validate_report(
                repo_root=repo,
                summary_path=summary_path,
                findings_path=findings_path,
                out_dir=out_dir,
            )

            with (out_dir / "classification_review.csv").open(encoding="utf-8", newline="") as handle:
                review_rows = list(csv.DictReader(handle))
            self.assertTrue(
                any(
                    row["path"] == "src/TaskDescriptionProcess.java"
                    and row["reported_category"] == "TASK_DESCRIPTION"
                    and row["expected_category"] == "TASK_DESCRIPTION"
                    and row["status"] == "match"
                    for row in review_rows
                )
            )


if __name__ == "__main__":
    unittest.main()
