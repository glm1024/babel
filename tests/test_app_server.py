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
                }
            )

            self.assertFalse(payload["has_results"])
            self.assertEqual(payload["config"]["scan_roots"], ["/tmp/repo-a", "/tmp/repo-b"])
            self.assertEqual(payload["config"]["scan_policy"]["context_lines"], 3)
            self.assertTrue((out_dir / "app_state.json").exists())

            reloaded = AppServiceState(out_dir=out_dir)
            bootstrap = reloaded.bootstrap_payload()
            self.assertEqual(bootstrap["config"]["scan_roots"], ["/tmp/repo-a", "/tmp/repo-b"])
            self.assertEqual(bootstrap["config"]["scan_policy"]["max_file_size_bytes"], 1234)
            self.assertFalse(bootstrap["has_results"])
            self.assertEqual(bootstrap["findings"], [])

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
            self.assertIn("标注管理", html)
            self.assertIn("设置", html)
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

            embedded = state.render_embedded_report()
            self.assertIn("明细筛选", embedded)
            self.assertNotIn("当前报告为只读模式", embedded)

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
