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
            self.assertIn("LOG_AUDIT_DEBUG", categories)
            self.assertIn("COMMENT", categories)
            self.assertIn("SWAGGER_DOCUMENTATION", categories)
            self.assertIn("GENERIC_DOCUMENTATION", categories)
            self.assertIn("DATABASE_SCRIPT", categories)
            self.assertIn("SHELL_SCRIPT", categories)
            self.assertIn("NAMED_FILE", categories)
            self.assertIn("I18N_FILE", categories)
            self.assertIn("CONDITION_EXPRESSION_LITERAL", categories)
            self.assertIn("TEST_SAMPLE_FIXTURE", categories)
            self.assertIn("CONFIG_ITEM", categories)
            self.assertIn("PROTOCOL_OR_PERSISTED_LITERAL", categories)
            self.assertEqual(summary["occurrence_count"], len(findings))
            self.assertIn("excluded_files", summary)
            self.assertIn("scan_policy", summary)
            self.assertIn("**/static/ajax/libs/**", summary["scan_policy"]["exclude_globs"])
            self.assertEqual(summary["excluded_files"], 1)
            self.assertNotIn("named_file", summary["skip_reasons"])
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
                any(
                    item["path"] == "Jekinsfiles.slim"
                    and item["category"] == "NAMED_FILE"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["hit_text"] == "系统繁忙"
                    and item["path"] == "config/i18n.messages.properties"
                    and item["category"] == "I18N_FILE"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(item["text"] == "操作异常！" and item["category"] == "USER_VISIBLE_COPY" for item in findings)
            )
            self.assertTrue(
                any(item["text"] == "开始时间检索" and item["category"] == "COMMENT" for item in findings)
            )
            self.assertTrue(
                any(item["text"] == "编码类型" and item["category"] == "COMMENT" for item in findings)
            )
            self.assertTrue(
                any("// 编码类型" in item["snippet"] for item in findings if item["category"] == "COMMENT")
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
                any(
                    item["text"] == "部门管理"
                    and item["category"] == "LOG_AUDIT_DEBUG"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "日志输出中文"
                    and item["category"] == "LOG_AUDIT_DEBUG"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "控制台输出中文"
                    and item["category"] == "LOG_AUDIT_DEBUG"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "错误流输出中文"
                    and item["category"] == "LOG_AUDIT_DEBUG"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "任务执行超时"
                    and item["category"] == "LOG_AUDIT_DEBUG"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "查询用户列表"
                    and item["category"] == "SWAGGER_DOCUMENTATION"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "创建用户"
                    and item["category"] == "SWAGGER_DOCUMENTATION"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "用户名称"
                    and item["category"] == "SWAGGER_DOCUMENTATION"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "年龄字段"
                    and item["category"] == "SWAGGER_DOCUMENTATION"
                    and item["action"] == "keep"
                    and "swagger_annotation" in item["candidate_roles"]
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "标签接口"
                    and item["category"] == "SWAGGER_DOCUMENTATION"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "请求成功"
                    and item["category"] == "SWAGGER_DOCUMENTATION"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "请求体说明"
                    and item["category"] == "SWAGGER_DOCUMENTATION"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "# 示例项目说明"
                    and item["path"] == "README.md"
                    and item["category"] == "GENERIC_DOCUMENTATION"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "通知状态"
                    and item["path"] == "src/ProtocolConstants.java"
                    and item["category"] == "PROTOCOL_OR_PERSISTED_LITERAL"
                    and item["action"] == "fix"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "通知类型"
                    and item["path"] == "sql/demo.sql"
                    and item["category"] == "DATABASE_SCRIPT"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "发布完成"
                    and item["path"] == "scripts/deploy.sh"
                    and item["category"] == "SHELL_SCRIPT"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "SnowFlakeGenerator:时钟回拨"
                    and item["hit_text"] == "时钟回拨"
                    and item["path"] == "src/ConditionExpressions.java"
                    and item["category"] == "CONDITION_EXPRESSION_LITERAL"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "不能为null"
                    and item["hit_text"] == "不能为"
                    and item["path"] == "src/ConditionExpressions.java"
                    and item["category"] == "CONDITION_EXPRESSION_LITERAL"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "停止服务"
                    and item["hit_text"] == "停止服务"
                    and item["path"] == "src/ConditionExpressions.java"
                    and item["category"] == "CONDITION_EXPRESSION_LITERAL"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "断言命中"
                    and item["hit_text"] == "断言命中"
                    and item["path"] == "src/ConditionExpressions.java"
                    and item["category"] == "CONDITION_EXPRESSION_LITERAL"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "错误前缀:"
                    and item["hit_text"] == "错误前缀"
                    and item["path"] == "src/ConditionExpressions.java"
                    and item["category"] == "CONDITION_EXPRESSION_LITERAL"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "租户[0-9]+"
                    and item["hit_text"] == "租户"
                    and item["path"] == "src/ConditionExpressions.java"
                    and item["category"] == "CONDITION_EXPRESSION_LITERAL"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "提示:"
                    and item["hit_text"] == "提示"
                    and item["path"] == "src/ConditionExpressions.java"
                    and item["category"] == "CONDITION_EXPRESSION_LITERAL"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "忽略"
                    and item["hit_text"] == "忽略"
                    and item["path"] == "src/ConditionExpressions.java"
                    and item["category"] == "CONDITION_EXPRESSION_LITERAL"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "前缀"
                    and item["hit_text"] == "前缀"
                    and item["path"] == "src/ConditionExpressions.java"
                    and item["category"] == "CONDITION_EXPRESSION_LITERAL"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "名称不能为空"
                    and item["hit_text"] == "名称不能为空"
                    and item["path"] == "src/ConditionExpressions.java"
                    and item["category"] == "CONDITION_EXPRESSION_LITERAL"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "状态非法"
                    and item["hit_text"] == "状态非法"
                    and item["path"] == "src/ConditionExpressions.java"
                    and item["category"] == "CONDITION_EXPRESSION_LITERAL"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "前缀"
                    and item["hit_text"] == "前缀"
                    and item["path"] == "src/ConditionExpressions.java"
                    and item["category"] == "CONDITION_EXPRESSION_LITERAL"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "启用"
                    and item["hit_text"] == "启用"
                    and item["path"] == "src/ConditionExpressions.java"
                    and item["category"] == "CONDITION_EXPRESSION_LITERAL"
                    and item["action"] == "keep"
                    for item in findings
                )
            )
            self.assertTrue(
                any(
                    item["text"] == "启用"
                    and item["hit_text"] == "启用"
                    and item["path"] == "src/ConditionExpressions.java"
                    and item["category"] == "USER_VISIBLE_COPY"
                    and item["action"] == "fix"
                    for item in findings
                )
            )
            self.assertFalse(any(item["action"] == "review" for item in findings))
            self.assertIn("用户可见文案", report)
            self.assertIn("注释", report)
            self.assertIn("Swagger 文档", report)
            self.assertIn("普通文档", report)
            self.assertIn("数据库脚本", report)
            self.assertIn("Shell 脚本", report)
            self.assertIn("指定文件", report)
            self.assertIn("国际化文件", report)
            self.assertIn("条件判断字面量", report)
            self.assertIn("配置项", report)
            self.assertIn("协议/持久化字面量", report)
            self.assertIn("扫描摘要", report)
            self.assertIn("明细筛选", report)
            self.assertIn("命中文本", report)
            self.assertIn("每页条数", report)
            self.assertIn("上一页", report)
            self.assertIn("下一页", report)
            self.assertIn("当前筛选条件下没有命中记录", report)
            self.assertLess(report.index('id="projectFilter"'), report.index('id="actionFilter"'))
            self.assertLess(report.index('id="actionFilter"'), report.index('id="categoryFilter"'))
            self.assertLess(report.index('id="categoryFilter"'), report.index('id="langFilter"'))
            self.assertIn("copy-btn", report)
            self.assertIn("查看跳过详情", report)
            self.assertIn('id="skipDialog"', report)
            self.assertIn('id="skipReasonChips"', report)
            self.assertIn('id="skipRows"', report)
            self.assertIn("第三方依赖目录", report)
            self.assertIn("当前命中位于国际化文件中。", report)
            self.assertIn("Swagger/OpenAPI 注解上下文", report)
            self.assertIn("当前命中用于条件判断表达式。", report)
            self.assertIn("// 编码类型", report)
            self.assertNotIn("展开详情", report)
            self.assertNotIn("项目与覆盖率", report)
            self.assertNotIn("summaryToggle", report)
            self.assertNotIn("高风险命中", report)
            self.assertNotIn("去重文本", report)
            self.assertNotIn("模型复核", report)
            self.assertNotIn("llm_status", report)
            self.assertNotIn("sourceFilter", report)
            self.assertNotIn("需要复核", report)
            self.assertNotIn("注释与文档", report)
            self.assertNotIn("配置与元数据", report)
            self.assertIn("导出全部结果到 Excel", report)
            self.assertIn("const PAGE_SIZES = [10, 100, 500];", report)
            self.assertIn("pageSize: 10", report)
            self.assertIn('action: "fix"', report)
            self.assertIn('}>${value} 条</option>`;', report)
            self.assertIn("function availableValues(filterKey) {", report)
            self.assertIn("function renderFilterOptions() {", report)
            self.assertIn('{ key: "project", node: projectFilter, label: "项目", group: "project" }', report)
            self.assertIn('{ key: "action", node: actionFilter, label: "动作", group: "action" }', report)
            self.assertIn('{ key: "category", node: categoryFilter, label: "分类", group: "category" }', report)
            self.assertIn('{ key: "lang", node: langFilter, label: "语言", group: "language" }', report)
            self.assertIn('if (excludedKey !== "action" && state.filters.action && item.action !== state.filters.action) return false;', report)
            self.assertIn('if (excludedKey !== "category" && state.filters.category && item.category !== state.filters.category) return false;', report)
            self.assertIn('state.filters[key] = node.value;', report)
            self.assertIn("renderFilterOptions();", report)
            self.assertIn("const pageSize = state.pageSize;", report)
            self.assertIn("const totalPages = Math.max(1, Math.ceil(total / pageSize));", report)
            self.assertIn('state.pageSize = Number.parseInt(pageSizeSelect.value, 10) || 10;', report)
            self.assertIn('const tableWrap = document.querySelector(".table-wrap");', report)
            self.assertIn("function scrollResultsToTop() {", report)
            self.assertIn("tableWrap.scrollTop = 0;", report)
            self.assertIn("window.scrollTo(0, 0);", report)
            self.assertIn('const headers = ["项目", "位置", "命中文本", "文本", "分类", "动作", "说明"];', report)
            self.assertIn('new Blob(["\\ufeff", lines.join("\\n")], { type: "text/csv;charset=utf-8" })', report)
            self.assertIn("function findingText(item) {", report)
            self.assertIn("if (item.hit_text) {", report)
            self.assertIn("return item.hit_text;", report)
            self.assertIn("function displaySnippet(item) {", report)
            self.assertIn('return item.snippet || item.normalized_text || item.text || "";', report)
            self.assertIn('${item.path} ${item.hit_text || ""} ${item.text} ${item.snippet || ""} ${item.reason}', report)
            self.assertIn('<td class="hit-text-cell">${escapeHtml(findingText(item) || "-")}</td>', report)
            self.assertNotIn('<td class="hit-text-cell"><strong>', report)
            self.assertIn(".hit-text-cell {", report)
            self.assertIn("font-weight: 400;", report)
            self.assertIn(".position-cell {", report)
            self.assertIn("width: 100%;", report)
            self.assertIn("flex: 1 1 auto;", report)
            self.assertIn("margin-left: auto;", report)
            self.assertIn('const extensionIndex = fileName.lastIndexOf(".");', report)
            self.assertIn("return extensionIndex > 0 ? fileName.slice(0, extensionIndex) : fileName;", report)
            self.assertIn("overflow: hidden;", report)
            self.assertIn("height: calc(100vh - 68px);", report)
            self.assertIn(".findings-table thead th {", report)
            self.assertIn("position: sticky;", report)
            self.assertIn('rows.innerHTML = `<tr><td colspan="7" class="empty-row">当前筛选条件下没有命中记录</td></tr>`;', report)
            self.assertNotIn('setOptions(projectFilter, findings.map(item => item.project), "项目", "project");', report)
            self.assertNotIn('setOptions(categoryFilter, findings.map(item => item.category), "分类", "category");', report)

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
