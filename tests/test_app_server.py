import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from zh_audit.app_server import AppServiceState


def _model_and_review_response(**kwargs):
    system_prompt = str(kwargs.get("system_prompt", "") or "")
    if "strict QA reviewer" in system_prompt:
        return {
            "decision": "pass",
            "issues": [],
        }
    return {
        "verdict": "needs_update",
        "candidate_translation": "create link: {0}",
        "reason": "ok",
    }


class AppServerSmokeTest(unittest.TestCase):
    def _wait_for_scan_done(self, state, timeout=10):
        deadline = time.time() + timeout
        latest_status = state.scan_status_payload()
        while time.time() < deadline:
            latest_status = state.scan_status_payload()
            if latest_status["status"] in {"done", "failed"}:
                break
            time.sleep(0.1)
        self.assertEqual(latest_status["status"], "done")
        return latest_status

    def test_app_state_persists_config_without_loading_old_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            state = AppServiceState(out_dir=out_dir)
            with patch("zh_audit.app_server.probe_openai_compatible_model", return_value={"message": "OK"}):
                payload = state.save_config(
                    {
                        "scan_roots": ["/tmp/repo-a", "/tmp/repo-b"],
                        "scan_policy": {
                            "max_file_size_bytes": 1234,
                            "context_lines": 3,
                            "exclude_globs": ["**/vendor/**"],
                        },
                        "model_config": {
                            "provider": "custom",
                            "base_url": "http://127.0.0.1:8000/v1/chat/completions",
                            "api_key": "sk-local",
                            "model": "deepseek-v3",
                            "max_tokens": 256,
                        },
                        "custom_keep_categories": [
                            {
                                "name": "历史兼容文案",
                                "enabled": True,
                                "rules": [
                                    {
                                        "type": "keyword",
                                        "pattern": "操作异常",
                                        "path_globs": ["src/**"],
                                    }
                                ],
                            }
                        ],
                    }
                )

            self.assertFalse(payload["has_results"])
            self.assertEqual(payload["config"]["scan_roots"], ["/tmp/repo-a", "/tmp/repo-b"])
            self.assertEqual(payload["config"]["scan_policy"]["context_lines"], 3)
            self.assertEqual(payload["config"]["model_config"]["provider"], "openai compatible")
            self.assertEqual(payload["config"]["model_config"]["base_url"], "http://127.0.0.1:8000/v1")
            self.assertEqual(payload["config"]["model_config"]["model"], "deepseek-v3")
            self.assertEqual(payload["config"]["model_config"]["max_tokens"], 256)
            self.assertEqual(payload["config"]["custom_keep_categories"][0]["name"], "历史兼容文案")
            self.assertTrue((out_dir / "app_state.json").exists())

            reloaded = AppServiceState(out_dir=out_dir)
            bootstrap = reloaded.bootstrap_payload()
            self.assertEqual(bootstrap["config"]["scan_roots"], ["/tmp/repo-a", "/tmp/repo-b"])
            self.assertEqual(bootstrap["config"]["scan_policy"]["max_file_size_bytes"], 1234)
            self.assertEqual(bootstrap["config"]["model_config"]["base_url"], "http://127.0.0.1:8000/v1")
            self.assertEqual(bootstrap["config"]["model_config"]["api_key"], "sk-local")
            self.assertEqual(bootstrap["config"]["custom_keep_categories"][0]["rules"][0]["type"], "keyword")
            self.assertFalse(bootstrap["has_results"])
            self.assertEqual(bootstrap["findings"], [])

    def test_project_model_config_defaults_and_local_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            out_dir = root / "results"
            config_path = root / "zh-audit.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "model_config": {
                            "provider": "ignored",
                            "base_url": "http://100.7.69.249:7777/v1/chat/completions",
                            "api_key": "sk-shared",
                            "model": "deepseek-v3",
                            "max_tokens": 100,
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            state = AppServiceState(out_dir=out_dir, project_config_path=config_path)
            bootstrap = state.bootstrap_payload()
            self.assertEqual(bootstrap["config"]["model_config"]["provider"], "openai compatible")
            self.assertEqual(bootstrap["config"]["model_config"]["base_url"], "http://100.7.69.249:7777/v1")
            self.assertEqual(bootstrap["config"]["model_config"]["api_key"], "sk-shared")

            with patch("zh_audit.app_server.probe_openai_compatible_model", return_value={"message": "OK"}):
                updated = state.save_config(
                    {
                        "model_config": {
                            "base_url": "http://127.0.0.1:9000",
                            "api_key": "",
                            "model": "deepseek-v3.1",
                            "max_tokens": 180,
                        }
                    }
                )
            self.assertEqual(updated["config"]["model_config"]["base_url"], "http://127.0.0.1:9000/v1")
            self.assertEqual(updated["config"]["model_config"]["api_key"], "")
            self.assertEqual(updated["config"]["model_config"]["model"], "deepseek-v3.1")
            self.assertEqual(updated["config"]["model_config"]["max_tokens"], 180)

            persisted = json.loads((out_dir / "app_state.json").read_text(encoding="utf-8"))
            self.assertEqual(
                persisted["model_config_overrides"],
                {
                    "api_key": "",
                    "base_url": "http://127.0.0.1:9000/v1",
                    "max_tokens": 180,
                    "model": "deepseek-v3.1",
                },
            )

            reloaded = AppServiceState(out_dir=out_dir, project_config_path=config_path)
            reloaded_bootstrap = reloaded.bootstrap_payload()
            self.assertEqual(reloaded_bootstrap["config"]["model_config"]["api_key"], "")
            self.assertEqual(reloaded_bootstrap["config"]["model_config"]["base_url"], "http://127.0.0.1:9000/v1")

    def test_invalid_project_config_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            out_dir = root / "results"
            config_path = root / "zh-audit.config.json"
            config_path.write_text("{", encoding="utf-8")

            with self.assertRaises(ValueError):
                AppServiceState(out_dir=out_dir, project_config_path=config_path)

    def test_service_scan_state_roundtrip(self) -> None:
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
            java_file = repo / "src" / "App.java"
            java_file.parent.mkdir(parents=True)
            java_file.write_text(
                'class App { String fail(){ return "操作异常！"; } }\n',
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "add", "."],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            out_dir = root / "results"
            state = AppServiceState(out_dir=out_dir)

            html = state.render_home()
            self.assertIn("scrollbar-gutter: stable;", html)
            self.assertIn("overflow-y: scroll;", html)
            self.assertIn("扫描目录", html)
            self.assertIn("扫描结果", html)
            self.assertIn("免改规则", html)
            self.assertIn("国际化文件", html)
            self.assertIn("数据库数据", html)
            self.assertIn("国际化文件中英文校对和翻译", html)
            self.assertIn("数据库数据中英文校对和翻译", html)
            self.assertIn("模型配置", html)
            self.assertIn("免改规则配置", html)
            self.assertIn("规则分组", html)
            self.assertIn("新增分组", html)
            self.assertIn("保存规则", html)
            self.assertIn('.split(/\\n|,/)', html)
            self.assertIn('.join("\\n")', html)
            self.assertIn("Base URL", html)
            self.assertIn("保存模型配置", html)
            self.assertIn("id=\"settingsStatusBanner\"", html)
            self.assertIn("测试并保存中...", html)
            self.assertIn("开始校译", html)
            self.assertIn("继续任务", html)
            self.assertIn("处理记录", html)
            self.assertIn("跳过手动审批，自动接受后续全部 AI 翻译", html)
            self.assertIn("主键字段名", html)
            self.assertIn('placeholder="请输入数据库脚本目录绝对路径"', html)
            self.assertIn('placeholder="请输入目标表名"', html)
            self.assertIn('placeholder="请输入主键字段名，默认 id"', html)
            self.assertIn('placeholder="请输入中文文案字段名"', html)
            self.assertIn('placeholder="请输入英文文案字段名"', html)
            self.assertIn("输出文件", html)
            self.assertIn("重试轮次：", html)
            self.assertIn("接受", html)
            self.assertIn("重新生成", html)
            self.assertIn("正在重新生成当前条目，完成后会自动刷新。", html)
            self.assertIn("@keyframes zh-audit-spin", html)
            self.assertIn(".pill.is-loading::before", html)
            self.assertIn(".progress-meta-value.is-loading", html)
            self.assertIn(".status-banner.is-loading", html)
            self.assertIn('translationCurrentStatus.classList.toggle("is-loading"', html)
            self.assertIn('sqlTranslationCurrentStatus.classList.toggle("is-loading"', html)
            self.assertNotIn("模型调用：", html)
            self.assertIn("复制路径", html)
            self.assertNotIn("最近完成", html)
            self.assertNotIn("Local Service", html)
            self.assertNotIn("首页先配置扫描目录，再启动扫描。", html)
            self.assertIn('class="root-remove-btn"', html)
            self.assertIn('aria-label="删除目录"', html)
            self.assertNotIn('>删除<', html)
            self.assertIn('data-tab="results"', html)
            self.assertIn('data-tab="customKeep"', html)
            self.assertIn('id="viewResultsBtn"', html)
            self.assertIn('id="resultsReportHost"', html)
            self.assertIn('id="customKeepPage"', html)
            self.assertIn('id="customKeepCategoryList"', html)
            self.assertIn("window.ZhAuditReport", html)
            self.assertNotIn("<iframe", html)
            self.assertNotIn("标注无需修改", html)
            self.assertNotIn("/api/annotations", html)
            self.assertIn("overflow-wrap: anywhere;", html)
            self.assertIn("min-width: 0;", html)
            self.assertIn("margin: 0 auto;", html)
            self.assertIn(".settings-workspace {", html)
            self.assertIn("height: calc(100vh - 124px);", html)
            self.assertIn(".translation-page-shell {", html)
            self.assertIn(".translation-top-grid {", html)
            self.assertIn(".translation-bottom-grid {", html)
            self.assertIn(".translation-top-card {", html)
            self.assertIn(".translation-stat-row {", html)
            self.assertIn(".translation-details {", html)
            self.assertIn(".translation-validation-note {", html)
            self.assertIn(".translation-call-budget {", html)
            self.assertIn("line-height: 1.55;", html)
            self.assertNotIn("已加载术语", html)
            self.assertNotIn("更多信息", html)
            self.assertIn("更多进度", html)
            self.assertNotIn(".translation-stats {", html)
            self.assertNotIn("grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);", html)
            self.assertIn('data-layout=\\"embedded\\"] .table-wrap {', html)
            self.assertIn(".findings-table col.col-sequence { width: 84px; }", html)
            self.assertIn(".findings-table col.col-action { width: 140px; }", html)
            self.assertIn(".findings-table col.col-operation { width: 160px; }", html)
            self.assertIn('data-sort-key=\\"location\\"', html)
            self.assertIn('data-sort-key=\\"text\\"', html)
            self.assertIn("标记已整改", html)
            self.assertIn("重新打开", html)
            self.assertIn("transform: translateY(-1px);", html)
            self.assertIn("scale(0.98)", html)
            self.assertIn("保存模型配置时会先做一次连通性测试。", html)
            self.assertIn("当前还没有扫描结果，请先到首页配置扫描目录并点击“开始扫描”。", html)
            self.assertNotIn("扫描设置", html)
            self.assertNotIn("最大文件大小（字节）", html)
            self.assertFalse(state.bootstrap_payload()["has_results"])

            status = state.start_scan(
                {
                    "scan_roots": [str(repo)],
                    "scan_policy": {
                        "max_file_size_bytes": 5 * 1024 * 1024,
                        "context_lines": 1,
                        "exclude_globs": ["**/static/ajax/libs/**"],
                    },
                }
            )
            self.assertEqual(status["status"], "running")
            self._wait_for_scan_done(state)

            bootstrap = state.bootstrap_payload()
            self.assertTrue(bootstrap["has_results"])
            self.assertEqual(
                [item["sequence"] for item in bootstrap["findings"]],
                list(range(1, len(bootstrap["findings"]) + 1)),
            )
            self.assertTrue(any(item["text"] == "操作异常！" for item in bootstrap["findings"]))
            self.assertTrue((out_dir / "findings.json").exists())
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "report.html").exists())
            self.assertTrue((out_dir / "app_state.json").exists())

    def test_resolve_and_reopen_persist_across_restart(self) -> None:
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
            java_file = repo / "src" / "App.java"
            java_file.parent.mkdir(parents=True)
            java_file.write_text(
                'class App { String fail(){ return "操作异常！"; } }\n',
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "add", "."],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            out_dir = root / "results"
            state = AppServiceState(out_dir=out_dir)
            state.start_scan(
                {
                    "scan_roots": [str(repo)],
                    "scan_policy": {
                        "max_file_size_bytes": 5 * 1024 * 1024,
                        "context_lines": 1,
                        "exclude_globs": ["**/static/ajax/libs/**"],
                    },
                }
            )
            self._wait_for_scan_done(state)

            target = next(item for item in state.findings if item["text"] == "操作异常！")
            resolved_payload = state.resolve_finding(target["id"])
            resolved_target = next(item for item in resolved_payload["findings"] if item["id"] == target["id"])
            self.assertEqual(resolved_target["action"], "resolved")
            self.assertTrue((out_dir / "remediation_state.json").exists())

            remediation_state = json.loads((out_dir / "remediation_state.json").read_text(encoding="utf-8"))
            self.assertEqual(remediation_state["version"], 1)
            self.assertEqual(len(remediation_state["items"]), 1)
            self.assertTrue(any(item["status"] == "resolved" for item in remediation_state["items"].values()))

            reloaded = AppServiceState(out_dir=out_dir)
            restored = next(item for item in reloaded.findings if item["text"] == "操作异常！")
            self.assertEqual(restored["action"], "resolved")
            self.assertEqual(reloaded.summary["by_action"]["resolved"], 1)

            reopened_payload = reloaded.reopen_finding(restored["id"])
            reopened_target = next(item for item in reopened_payload["findings"] if item["id"] == restored["id"])
            self.assertEqual(reopened_target["action"], "fix")

            remediation_state = json.loads((out_dir / "remediation_state.json").read_text(encoding="utf-8"))
            self.assertEqual(remediation_state["items"], {})

            reopened = AppServiceState(out_dir=out_dir)
            reopened_restored = next(item for item in reopened.findings if item["text"] == "操作异常！")
            self.assertEqual(reopened_restored["action"], "fix")

    def test_resolved_state_reapplies_after_rescan(self) -> None:
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
            java_file = repo / "src" / "App.java"
            java_file.parent.mkdir(parents=True)
            java_file.write_text(
                'class App { String fail(){ return "操作异常！"; } }\n',
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "add", "."],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            out_dir = root / "results"
            state = AppServiceState(out_dir=out_dir)
            scan_payload = {
                "scan_roots": [str(repo)],
                "scan_policy": {
                    "max_file_size_bytes": 5 * 1024 * 1024,
                    "context_lines": 1,
                    "exclude_globs": ["**/static/ajax/libs/**"],
                },
            }
            state.start_scan(scan_payload)
            self._wait_for_scan_done(state)

            target = next(item for item in state.findings if item["text"] == "操作异常！")
            state.resolve_finding(target["id"])

            java_file.write_text(
                "// moved\nclass App { String fail(){ return \"操作异常！\"; } }\n",
                encoding="utf-8",
            )

            state.start_scan(scan_payload)
            self._wait_for_scan_done(state)

            rescanned = next(item for item in state.findings if item["text"] == "操作异常！")
            self.assertEqual(rescanned["action"], "resolved")

    def test_invalid_scan_directory_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir) / "results"
            state = AppServiceState(out_dir=out_dir)
            with self.assertRaises(ValueError):
                state.start_scan({"scan_roots": ["/path/not/exist"]})

    def test_invalid_custom_keep_regex_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir) / "results"
            state = AppServiceState(out_dir=out_dir)
            with self.assertRaises(ValueError):
                state.save_config(
                    {
                        "custom_keep_categories": [
                            {
                                "name": "坏规则",
                                "enabled": True,
                                "rules": [
                                    {
                                        "type": "regex",
                                        "pattern": "[",
                                        "path_globs": [],
                                    }
                                ],
                            }
                        ]
                    }
                )

    def test_custom_keep_categories_override_scan_classification(self) -> None:
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

            template = repo / "templates" / "view.html"
            template.parent.mkdir(parents=True)
            template.write_text('<div title="noop">系统繁忙</div>\n', encoding="utf-8")

            java_file = repo / "src" / "App.java"
            java_file.parent.mkdir(parents=True)
            java_file.write_text(
                'class App { String fail(){ return "系统繁忙"; } }\n',
                encoding="utf-8",
            )

            subprocess.run(
                ["git", "add", "."],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            out_dir = root / "results"
            state = AppServiceState(out_dir=out_dir)
            state.save_config(
                {
                    "custom_keep_categories": [
                        {
                            "name": "模板白名单",
                            "enabled": True,
                            "rules": [
                                {
                                    "type": "regex",
                                    "pattern": "系统繁忙",
                                    "path_globs": ["templates/**"],
                                }
                            ],
                        },
                        {
                            "name": "通用白名单",
                            "enabled": True,
                            "rules": [
                                {
                                    "type": "keyword",
                                    "pattern": "系统繁忙",
                                    "path_globs": [],
                                }
                            ],
                        },
                    ]
                }
            )

            state.start_scan(
                {
                    "scan_roots": [str(repo)],
                    "scan_policy": {
                        "max_file_size_bytes": 5 * 1024 * 1024,
                        "context_lines": 1,
                        "exclude_globs": ["**/static/ajax/libs/**"],
                    },
                }
            )
            self._wait_for_scan_done(state)

            template_finding = next(item for item in state.findings if item["path"] == "templates/view.html")
            java_finding = next(item for item in state.findings if item["path"] == "src/App.java")

            self.assertEqual(template_finding["category"], "模板白名单")
            self.assertEqual(template_finding["action"], "keep")
            self.assertEqual(template_finding["reason"], "Custom keep category rule matched.")
            self.assertEqual(template_finding["metadata"]["custom_keep_matched_field"], "normalized_text")

            self.assertEqual(java_finding["category"], "通用白名单")
            self.assertEqual(java_finding["action"], "keep")
            self.assertEqual(java_finding["metadata"]["custom_keep_rule_type"], "keyword")

    def test_scan_progress_keeps_latest_repo_context_for_multi_repo_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir) / "results"
            state = AppServiceState(out_dir=out_dir)

            state._scan_progress("start", total=10)
            state._scan_progress("repo", repo="repo-a", repo_total=4, total=10)
            state._scan_progress("file", repo="repo-a", processed=4, total=10, relative_path="src/A.java")
            state._scan_progress("repo", repo="repo-b", repo_total=6, total=10)
            state._scan_progress("file", repo="repo-b", processed=5, total=10, relative_path="src/B.java")

            running = state.scan_status_payload()
            self.assertEqual(running["current_repo"], "repo-b")
            self.assertEqual(running["current_path"], "src/B.java")

            state._scan_progress("done", processed=10, total=10)
            finished = state.scan_status_payload()
            self.assertEqual(finished["current_repo"], "repo-b")
            self.assertEqual(finished["current_path"], "扫描完成")

    def test_translation_task_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            out_dir = root / "results"
            source = root / "messages_zh.properties"
            target = root / "messages_en.properties"
            source.write_text("RESOURCE_POOL=资源池\nNETWORK_LINK_ADD=创建对等连接：{0}\n", encoding="utf-8")
            target.write_text("RESOURCE_POOL=wrong\nNETWORK_LINK_ADD=wrong value: {0}\n", encoding="utf-8")

            config_path = root / "zh-audit.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "model_config": {
                            "base_url": "http://127.0.0.1:8000/v1",
                            "api_key": "sk-local",
                            "model": "demo",
                            "max_tokens": 120,
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            state = AppServiceState(out_dir=out_dir, project_config_path=config_path)

            with patch("zh_audit.app_server.call_openai_compatible_json") as mocked:
                mocked.side_effect = _model_and_review_response
                payload = state.start_translation(
                    {
                        "source_path": str(source),
                        "target_path": str(target),
                        "auto_accept": False,
                    }
                )
                self.assertIn(payload["status"]["status"], {"running", "done"})

                deadline = time.time() + 10
                latest = payload
                while time.time() < deadline:
                    latest = state.translation_payload()
                    if latest["status"]["status"] in {"done", "failed", "stopped"}:
                        break
                    time.sleep(0.1)

                self.assertEqual(latest["status"]["status"], "done")
                self.assertEqual(latest["status"]["counts"]["glossary_applied"], 1)
                self.assertEqual(latest["status"]["counts"]["pending"], 1)
                pending = latest["pending_items"][0]
                self.assertEqual(pending["candidate_text"], "create link: {0}")
                self.assertTrue(pending["can_accept"])
                self.assertEqual(pending["generation_attempts_used"], 1)
                self.assertGreaterEqual(pending["model_calls_used"], 2)

                accepted = state.translation_accept(pending["id"])
                self.assertEqual(accepted["status"]["counts"]["accepted"], 2)
                target_text = target.read_text(encoding="utf-8")
                self.assertIn("RESOURCE_POOL=resource pool", target_text)
                self.assertIn("NETWORK_LINK_ADD=create link: {0}", target_text)
                self.assertNotIn("# Added by zh-audit 码值校译", target_text)
                self.assertFalse(any(path.name.startswith("messages_en.properties.bak.") for path in root.iterdir()))

    def test_translation_task_does_not_interrupt_on_retryable_model_format_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            out_dir = root / "results"
            source = root / "messages_zh.properties"
            target = root / "messages_en.properties"
            source.write_text("AUTH_RETRY=适配服务器无法处理请求站点连接需要更新认证信息，请重试。\n", encoding="utf-8")
            target.write_text("AUTH_RETRY=Adapter server is not ready for request.\n", encoding="utf-8")

            config_path = root / "zh-audit.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "model_config": {
                            "base_url": "http://127.0.0.1:8000/v1",
                            "api_key": "sk-local",
                            "model": "demo",
                            "max_tokens": 120,
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            state = AppServiceState(out_dir=out_dir, project_config_path=config_path)
            with patch(
                "zh_audit.app_server.call_openai_compatible_json",
                side_effect=ValueError('Model response does not contain a valid JSON object: {"verdict": “needs_update”}'),
            ):
                state.start_translation(
                    {
                        "source_path": str(source),
                        "target_path": str(target),
                        "auto_accept": False,
                    }
                )
                deadline = time.time() + 10
                latest = state.translation_payload()
                while time.time() < deadline:
                    latest = state.translation_payload()
                    if latest["status"]["status"] in {"done", "failed", "stopped", "interrupted"}:
                        break
                    time.sleep(0.1)

            self.assertEqual(latest["status"]["status"], "done")
            pending = latest["pending_items"][0]
            self.assertEqual(pending["validation_state"], "failed")
            self.assertFalse(pending["can_accept"])
            self.assertEqual(pending["generation_attempts_used"], 5)
            self.assertIn("模型返回格式不规范", pending["validation_message"])

    def test_translation_session_restores_and_resumes_after_model_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            out_dir = root / "results"
            source = root / "messages_zh.properties"
            target = root / "messages_en.properties"
            source.write_text("NETWORK_LINK_ADD=创建对等连接：{0}\n", encoding="utf-8")
            target.write_text("NETWORK_LINK_ADD=wrong value: {0}\n", encoding="utf-8")

            config_path = root / "zh-audit.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "model_config": {
                            "base_url": "http://127.0.0.1:8000/v1",
                            "api_key": "sk-local",
                            "model": "demo",
                            "max_tokens": 120,
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            state = AppServiceState(out_dir=out_dir, project_config_path=config_path)
            with patch("zh_audit.app_server.call_openai_compatible_json", side_effect=ValueError("model unavailable")):
                state.start_translation(
                    {
                        "source_path": str(source),
                        "target_path": str(target),
                        "auto_accept": False,
                    }
                )
                deadline = time.time() + 10
                latest = state.translation_payload()
                while time.time() < deadline:
                    latest = state.translation_payload()
                    if latest["status"]["status"] == "interrupted":
                        break
                    time.sleep(0.1)

            self.assertEqual(latest["status"]["status"], "interrupted")
            self.assertTrue(latest["status"]["resume_available"])
            self.assertTrue((out_dir / "translation_session.json").exists())

            reloaded = AppServiceState(out_dir=out_dir, project_config_path=config_path)
            restored = reloaded.translation_payload()
            self.assertEqual(restored["status"]["status"], "interrupted")
            self.assertTrue(restored["status"]["resume_available"])
            self.assertIn("任务已中断，可继续执行", reloaded.render_home())

            with patch("zh_audit.app_server.call_openai_compatible_json") as mocked:
                mocked.side_effect = _model_and_review_response
                resumed = reloaded.resume_translation()
                self.assertEqual(resumed["status"]["status"], "running")

                deadline = time.time() + 10
                latest = resumed
                while time.time() < deadline:
                    latest = reloaded.translation_payload()
                    if latest["status"]["status"] in {"done", "failed", "stopped", "interrupted"}:
                        break
                    time.sleep(0.1)

                self.assertEqual(latest["status"]["status"], "done")
                pending = latest["pending_items"][0]
                accepted = reloaded.translation_accept(pending["id"])
                self.assertEqual(accepted["status"]["counts"]["accepted"], 1)
                self.assertIn("NETWORK_LINK_ADD=create link: {0}", target.read_text(encoding="utf-8"))

    def test_sql_translation_task_roundtrip_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            out_dir = root / "results"
            sql_dir = root / "sql"
            sql_dir.mkdir()
            (sql_dir / "demo.sql").write_text(
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('1', '资源池', 'wrong');\n"
                "INSERT INTO t_demo (id, name_zh, name_en) VALUES ('2', '创建对等连接：{0}', 'wrong');\n",
                encoding="utf-8",
            )

            config_path = root / "zh-audit.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "model_config": {
                            "base_url": "http://127.0.0.1:8000/v1",
                            "api_key": "sk-local",
                            "model": "demo",
                            "max_tokens": 120,
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            state = AppServiceState(out_dir=out_dir, project_config_path=config_path)
            with patch("zh_audit.app_server.call_openai_compatible_json", side_effect=ValueError("model unavailable")):
                state.start_sql_translation(
                    {
                        "directory_path": str(sql_dir),
                        "table_name": "t_demo",
                        "primary_key_field": "id",
                        "source_field": "name_zh",
                        "target_field": "name_en",
                    }
                )
                deadline = time.time() + 10
                latest = state.sql_translation_payload()
                while time.time() < deadline:
                    latest = state.sql_translation_payload()
                    if latest["status"]["status"] == "interrupted":
                        break
                    time.sleep(0.1)

            self.assertEqual(latest["status"]["status"], "interrupted")
            self.assertTrue(latest["status"]["resume_available"])
            output_path = Path(latest["status"]["output_path"])
            self.assertTrue(output_path.exists())
            self.assertTrue((out_dir / "sql_translation_session.json").exists())

            reloaded = AppServiceState(out_dir=out_dir, project_config_path=config_path)
            restored = reloaded.sql_translation_payload()
            self.assertEqual(restored["status"]["status"], "interrupted")
            self.assertTrue(restored["status"]["resume_available"])
            self.assertEqual(restored["status"]["output_path"], str(output_path))
            self.assertIn("任务已中断，可继续执行", reloaded.render_home())

            with patch("zh_audit.app_server.call_openai_compatible_json") as mocked:
                mocked.side_effect = _model_and_review_response
                resumed = reloaded.resume_sql_translation()
                self.assertEqual(resumed["status"]["status"], "running")

                deadline = time.time() + 10
                latest = resumed
                while time.time() < deadline:
                    latest = reloaded.sql_translation_payload()
                    if latest["status"]["status"] in {"done", "failed", "stopped", "interrupted"}:
                        break
                    time.sleep(0.1)

                self.assertEqual(latest["status"]["status"], "done")
                by_source = dict((item["source_text"], item) for item in latest["pending_items"])
                accepted = reloaded.sql_translation_accept(by_source["资源池"]["id"])
                self.assertEqual(accepted["status"]["counts"]["accepted"], 1)
                content = output_path.read_text(encoding="utf-8")
                self.assertIn("-- item:", content)
                self.assertIn("UPDATE t_demo SET name_en = 'resource pool' WHERE id = '1';", content)
                self.assertEqual(content.count("-- item:"), 1)


if __name__ == "__main__":
    unittest.main()
