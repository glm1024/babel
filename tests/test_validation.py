from __future__ import annotations

import csv
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from zh_audit.validation import validate_report


class ValidationSmokeTest(unittest.TestCase):
    def test_validate_report_generates_deliverables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

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

            subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)

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


if __name__ == "__main__":
    unittest.main()
