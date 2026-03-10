import json
import tempfile
import unittest
from pathlib import Path

from zh_audit.cli import main
from zh_audit.report import render_report


class ScanSmokeTest(unittest.TestCase):
    def test_scan_generates_json_and_report(self) -> None:
        fixture_repo = Path(__file__).parent / "fixtures" / "repo_a"
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            manifest_path = temp_path / "repos.json"
            out_dir = temp_path / "out"
            manifest_path.write_text(
                json.dumps([str(fixture_repo)], ensure_ascii=False),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "scan",
                    "--manifest",
                    str(manifest_path),
                    "--out",
                    str(out_dir),
                    "--pretty",
                ]
            )

            self.assertEqual(exit_code, 0)
            findings = json.loads((out_dir / "findings.json").read_text(encoding="utf-8"))
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            report = (out_dir / "report.html").read_text(encoding="utf-8")

            categories = {item["category"] for item in findings}
            self.assertIn("USER_VISIBLE_COPY", categories)
            self.assertIn("ERROR_VALIDATION_MESSAGE", categories)
            self.assertIn("TEST_SAMPLE_FIXTURE", categories)
            self.assertIn("CONFIG_METADATA", categories)
            self.assertEqual(summary["occurrence_count"], len(findings))
            self.assertIn("excluded_files", summary)
            self.assertIn("scan_policy", summary)
            self.assertIn("**/static/ajax/libs/**", summary["scan_policy"]["exclude_globs"])
            self.assertEqual(summary["excluded_files"], 1)
            self.assertFalse(any("static/ajax/libs/" in item["path"] for item in findings))
            self.assertTrue(
                any(
                    item["skip_reason"] == "excluded_by_policy"
                    and "第三方依赖目录" in item["skip_detail"]
                    and "**/static/ajax/libs/**" in item["skip_detail"]
                    for item in summary["files"]
                )
            )
            self.assertTrue(
                any(item["text"] == "操作异常！" and item["category"] == "USER_VISIBLE_COPY" for item in findings)
            )
            self.assertTrue(
                any(item["text"] == "开始时间检索" and item["category"] == "COMMENT_DOCUMENTATION" for item in findings)
            )
            self.assertTrue(
                any(item["text"] == "编码类型" and item["category"] == "COMMENT_DOCUMENTATION" for item in findings)
            )
            self.assertTrue(
                any(
                    item["text"] == "菜单已分配,不允许删除"
                    and item["category"] == "ERROR_VALIDATION_MESSAGE"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "%1$s已分配,不能删除"
                    and item["category"] == "ERROR_VALIDATION_MESSAGE"
                    for item in findings
                )
            )
            self.assertTrue(
                any(item["text"] == "部门管理" and item["category"] == "LOG_AUDIT_DEBUG" for item in findings)
            )
            self.assertIn("用户可见文案", report)
            self.assertIn("扫描摘要", report)
            self.assertIn("明细筛选", report)
            self.assertIn("每页条数", report)
            self.assertIn("上一页", report)
            self.assertIn("下一页", report)
            self.assertIn("当前筛选条件下没有命中记录", report)
            self.assertIn("copy-btn", report)
            self.assertIn("查看跳过详情", report)
            self.assertIn('id="skipDialog"', report)
            self.assertIn('id="skipReasonChips"', report)
            self.assertIn('id="skipRows"', report)
            self.assertIn("第三方依赖目录", report)
            self.assertNotIn("展开详情", report)
            self.assertNotIn("项目与覆盖率", report)
            self.assertNotIn("summaryToggle", report)
            self.assertNotIn("高风险命中", report)
            self.assertNotIn("去重文本", report)
            self.assertNotIn("模型复核", report)
            self.assertNotIn("llm_status", report)
            self.assertNotIn("sourceFilter", report)
            self.assertIn("导出全部结果到 Excel", report)
            self.assertIn("pageSize: 20", report)
            self.assertIn('state.pageSize = Number.parseInt(pageSizeSelect.value, 10) || 20;', report)
            self.assertIn('const headers = ["项目", "位置", "文本", "分类", "动作", "说明"];', report)
            self.assertIn('new Blob(["\\ufeff", lines.join("\\n")], { type: "text/csv;charset=utf-8" })', report)
            self.assertIn(".position-cell {", report)
            self.assertIn("width: 100%;", report)
            self.assertIn("flex: 1 1 auto;", report)
            self.assertIn("margin-left: auto;", report)

            report_without_skips = render_report(
                {
                    **summary,
                    "skipped_files": 0,
                    "excluded_files": 0,
                    "skip_reasons": {},
                    "files": [item for item in summary["files"] if not item["skip_reason"]],
                },
                findings,
            )
            self.assertIn("暂无跳过文件", report_without_skips)
            self.assertIn('openSkipDialogBtn.disabled = true;', report_without_skips)
            self.assertIn('openSkipDialogBtn.textContent = "暂无跳过文件";', report_without_skips)


if __name__ == "__main__":
    unittest.main()
