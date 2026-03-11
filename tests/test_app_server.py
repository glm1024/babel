import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from zh_audit.app_server import AppServiceState


class AppServerSmokeTest(unittest.TestCase):
    def test_app_state_persists_config_without_loading_old_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            state = AppServiceState(out_dir=out_dir)
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
                }
            )

            self.assertFalse(payload["has_results"])
            self.assertEqual(payload["config"]["scan_roots"], ["/tmp/repo-a", "/tmp/repo-b"])
            self.assertEqual(payload["config"]["scan_policy"]["context_lines"], 3)
            self.assertEqual(payload["config"]["model_config"]["provider"], "openai compatible")
            self.assertEqual(payload["config"]["model_config"]["base_url"], "http://127.0.0.1:8000/v1")
            self.assertEqual(payload["config"]["model_config"]["model"], "deepseek-v3")
            self.assertEqual(payload["config"]["model_config"]["max_tokens"], 256)
            self.assertTrue((out_dir / "app_state.json").exists())

            reloaded = AppServiceState(out_dir=out_dir)
            bootstrap = reloaded.bootstrap_payload()
            self.assertEqual(bootstrap["config"]["scan_roots"], ["/tmp/repo-a", "/tmp/repo-b"])
            self.assertEqual(bootstrap["config"]["scan_policy"]["max_file_size_bytes"], 1234)
            self.assertEqual(bootstrap["config"]["model_config"]["base_url"], "http://127.0.0.1:8000/v1")
            self.assertEqual(bootstrap["config"]["model_config"]["api_key"], "sk-local")
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

    def test_service_scan_state_and_annotation_roundtrip(self) -> None:
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
            self.assertIn("扫描目录", html)
            self.assertIn("扫描结果", html)
            self.assertIn("标注管理", html)
            self.assertIn("模型配置", html)
            self.assertIn("Base URL", html)
            self.assertIn("保存模型配置", html)
            self.assertNotIn("Local Service", html)
            self.assertNotIn("首页先配置扫描目录，再启动扫描。", html)
            self.assertIn('class="root-remove-btn"', html)
            self.assertIn('aria-label="删除目录"', html)
            self.assertNotIn('>删除<', html)
            self.assertIn('data-tab="results"', html)
            self.assertIn('id="viewResultsBtn"', html)
            self.assertIn('id="resultsReportHost"', html)
            self.assertIn("window.ZhAuditReport", html)
            self.assertNotIn("<iframe", html)
            self.assertNotIn("resultsFullscreenBtn", html)
            self.assertNotIn("resultsCloseFullscreenBtn", html)
            self.assertIn("overflow-wrap: anywhere;", html)
            self.assertIn("min-width: 0;", html)
            self.assertIn("margin: 0 auto;", html)
            self.assertIn("height: calc(100vh - 124px);", html)
            self.assertIn('data-layout=\\"embedded\\"] .table-wrap {', html)
            self.assertIn(".findings-table col.col-action { width: 280px; }", html)
            self.assertIn("transform: translateY(-1px);", html)
            self.assertIn("scale(0.98)", html)
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

            deadline = time.time() + 10
            latest_status = status
            while time.time() < deadline:
                latest_status = state.scan_status_payload()
                if latest_status["status"] in {"done", "failed"}:
                    break
                time.sleep(0.1)
            self.assertEqual(latest_status["status"], "done")

            bootstrap = state.bootstrap_payload()
            self.assertTrue(bootstrap["has_results"])
            self.assertTrue(any(item["text"] == "操作异常！" for item in bootstrap["findings"]))
            self.assertTrue((out_dir / "findings.json").exists())
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "report.html").exists())
            self.assertTrue((out_dir / "app_state.json").exists())

            target = next(item for item in bootstrap["findings"] if item["action"] == "fix")
            updated = state.annotate(target["id"], "本地保留")
            annotated = next(item for item in updated["findings"] if item["id"] == target["id"])
            self.assertTrue(annotated["annotated"])
            self.assertEqual(annotated["category"], "ANNOTATED_NO_CHANGE")

            reverted = state.remove_annotation(target["id"])
            original = next(item for item in reverted["findings"] if item["id"] == target["id"])
            self.assertFalse(original["annotated"])

    def test_invalid_scan_directory_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir) / "results"
            state = AppServiceState(out_dir=out_dir)
            with self.assertRaises(ValueError):
                state.start_scan({"scan_roots": ["/path/not/exist"]})


if __name__ == "__main__":
    unittest.main()
