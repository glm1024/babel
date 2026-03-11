import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from zh_audit.annotations import apply_annotation_store, upsert_annotation
from zh_audit.app_server import AppServiceState


def _base_finding():
    return {
        "id": "demo-1",
        "project": "repo",
        "path": "src/App.java",
        "lang": "java",
        "line": 1,
        "column": 1,
        "surface_kind": "string_literal",
        "symbol": "",
        "text": "操作异常！",
        "normalized_text": "操作异常！",
        "hit_text": "操作异常",
        "snippet": 'return "操作异常！";',
        "category": "USER_VISIBLE_COPY",
        "action": "fix",
        "confidence": 0.91,
        "high_risk": True,
        "end_user_visible": True,
        "reason": "String literal with Chinese text.",
        "file_role": "",
        "candidate_roles": [],
        "annotated": False,
        "annotation_reason": "",
        "annotation_updated_at": "",
        "original_category": "",
        "original_action": "",
        "annotation_key": "",
        "metadata": {},
    }


class AnnotationSmokeTest(unittest.TestCase):
    def _wait_for_done(self, state: AppServiceState, timeout: float = 15.0) -> None:
        deadline = time.time() + timeout
        latest_status = state.scan_status_payload()
        while time.time() < deadline:
            latest_status = state.scan_status_payload()
            if latest_status["status"] in {"done", "failed"}:
                break
            time.sleep(0.1)
        self.assertEqual(latest_status["status"], "done")

    def _run_service_scan(self, state: AppServiceState, repo_root: Path) -> None:
        status = state.start_scan(
            {
                "scan_roots": [str(repo_root)],
                "scan_policy": {
                    "max_file_size_bytes": 5 * 1024 * 1024,
                    "context_lines": 1,
                    "exclude_globs": ["**/static/ajax/libs/**"],
                },
            }
        )
        self.assertEqual(status["status"], "running")
        self._wait_for_done(state)

    def test_service_state_fails_on_invalid_annotations_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            out_dir = temp_path / "out"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "annotations.json").write_text("{invalid", encoding="utf-8")

            with self.assertRaises(ValueError):
                AppServiceState(out_dir=out_dir)

            self.assertFalse((out_dir / "findings.json").exists())
            self.assertFalse((out_dir / "summary.json").exists())

    def test_service_state_persists_annotation_and_restore(self) -> None:
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
            self._run_service_scan(state, repo)
            target = next(item for item in state.findings if item["action"] == "fix")
            original_category = target["category"]
            original_action = target["action"]
            response = state.annotate(target["id"], "协议兼容文案")

            finding = next(item for item in response["findings"] if item["id"] == target["id"])
            self.assertEqual(finding["category"], "ANNOTATED_NO_CHANGE")
            self.assertEqual(finding["action"], "keep")
            self.assertTrue(finding["annotated"])
            self.assertEqual(finding["annotation_reason"], "协议兼容文案")
            self.assertEqual(finding["original_category"], original_category)
            self.assertEqual(finding["original_action"], original_action)

            annotations_path = out_dir / "annotations.json"
            findings_path = out_dir / "findings.json"
            summary_path = out_dir / "summary.json"
            annotation_store = json.loads(annotations_path.read_text(encoding="utf-8"))
            self.assertEqual(annotation_store["version"], 1)
            self.assertEqual(len(annotation_store["items"]), 1)
            self.assertTrue(any(item["reason"] == "协议兼容文案" for item in annotation_store["items"].values()))

            persisted_findings = json.loads(findings_path.read_text(encoding="utf-8"))
            self.assertTrue(persisted_findings[0]["annotated"])
            self.assertEqual(persisted_findings[0]["category"], "ANNOTATED_NO_CHANGE")

            persisted_summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted_summary["by_action"]["keep"], 1)
            self.assertEqual(persisted_summary["annotations"]["applied"], 1)

            report = (out_dir / "report.html").read_text(encoding="utf-8")
            self.assertIn("标注无需修改", report)
            self.assertIn("当前报告为只读模式，请使用 zh-audit serve 打开本地服务版本。", report)

            restored = state.remove_annotation(target["id"])
            original = next(item for item in restored["findings"] if item["id"] == target["id"])
            self.assertEqual(original["category"], original_category)
            self.assertEqual(original["action"], original_action)
            self.assertFalse(original["annotated"])

            annotation_store = json.loads(annotations_path.read_text(encoding="utf-8"))
            self.assertEqual(annotation_store["items"], {})

    def test_service_rescan_reapplies_annotation_after_changed_snippet(self) -> None:
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

            out_dir = root / "out"
            state = AppServiceState(out_dir=out_dir)
            self._run_service_scan(state, repo)
            fix_finding = next(item for item in state.findings if item["action"] == "fix")
            original_category = fix_finding["category"]
            original_action = fix_finding["action"]
            state.annotate(fix_finding["id"], "兼容保留")

            java_file.write_text(
                'class App { String fail(){ return warn("操作异常！"); } }\n',
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "add", "."],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self._run_service_scan(state, repo)

            findings = json.loads((out_dir / "findings.json").read_text(encoding="utf-8"))
            annotated = next(item for item in findings if item["text"] == "操作异常！")
            self.assertTrue(annotated["annotated"])
            self.assertEqual(annotated["category"], "ANNOTATED_NO_CHANGE")
            self.assertEqual(annotated["action"], "keep")
            self.assertEqual(annotated["annotation_reason"], "兼容保留")
            self.assertEqual(annotated["original_category"], original_category)
            self.assertEqual(annotated["original_action"], original_action)

    def test_fallback_annotation_is_not_applied_when_multiple_matches_exist(self) -> None:
        store = {"version": 1, "items": {}}
        original = _base_finding()
        key, _record = upsert_annotation(store, original, "避免误伤", updated_at="2026-03-11T10:00:00+08:00")
        self.assertIn(key, store["items"])

        findings = [
            {
                **_base_finding(),
                "id": "candidate-1",
                "snippet": 'return warn("操作异常！");',
            },
            {
                **_base_finding(),
                "id": "candidate-2",
                "snippet": 'return fail("操作异常！");',
            },
        ]

        stats = apply_annotation_store(findings, store)

        self.assertEqual(stats["loaded"], 1)
        self.assertEqual(stats["applied"], 0)
        self.assertEqual(stats["stale"], 1)
        self.assertFalse(any(item["annotated"] for item in findings))


if __name__ == "__main__":
    unittest.main()
