import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import urlparse

from zh_audit.annotations import (
    ANNOTATION_STATS_DEFAULT,
    apply_annotation_store,
    load_annotation_store,
    remove_annotation,
    resolve_annotation_path,
    upsert_annotation,
    write_annotation_store,
)
from zh_audit.app_state import (
    default_app_state,
    default_translation_config,
    diff_model_config_overrides,
    load_app_state,
    merge_model_config,
    normalize_scan_policy,
    normalize_scan_roots,
    normalize_translation_config,
    scan_settings_from_state,
    write_app_state,
)
from zh_audit.app_ui import render_app_shell
from zh_audit.config import load_project_model_config
from zh_audit.model_client import call_openai_compatible_json
from zh_audit.model_client import probe_openai_compatible_model
from zh_audit.models import RepoSpec
from zh_audit.pipeline import refresh_summary, run_scan
from zh_audit.report import render_report
from zh_audit.terminology_xlsx import ensure_default_terminology_xlsx, load_terminology_xlsx
from zh_audit.translation_workflow import (
    TranslationSession,
    build_translation_system_prompt,
    build_translation_user_prompt,
)


class AppServiceState(object):
    def __init__(self, out_dir, annotations_path=None, app_state_path=None, project_config_path=None):
        self.out_dir = Path(out_dir)
        self.findings_path = self.out_dir / "findings.json"
        self.summary_path = self.out_dir / "summary.json"
        self.report_path = self.out_dir / "report.html"
        self.annotations_path = resolve_annotation_path(self.out_dir, annotations_path)
        self.app_state_path = Path(app_state_path) if app_state_path is not None else (self.out_dir / "app_state.json")
        self.project_config_path = Path(project_config_path) if project_config_path is not None else None
        self.lock = threading.RLock()
        self.scan_thread = None
        self.translation_thread = None
        self.results_revision = 0
        self.summary = {}
        self.findings = []
        self.translation_session = None
        self.annotation_store = load_annotation_store(self.annotations_path)
        self.annotation_stats = dict(ANNOTATION_STATS_DEFAULT)
        self.project_model_config = (
            load_project_model_config(self.project_config_path) if self.project_config_path is not None else {}
        )
        self.app_state = load_app_state(self.app_state_path)
        self.translation_auto_accept = bool(self.app_state.get("translation_config", {}).get("auto_accept", False))
        self.scan_status = self._idle_scan_status()
        self.terminology_path = ensure_default_terminology_xlsx(Path(__file__).resolve().parents[2] / "resources" / "terminology.xlsx")
        self.terminology = {}
        self.terminology_error = ""
        self._reload_terminology()

    def render_home(self):
        return render_app_shell(
            self.bootstrap_payload(),
            client_config={
                "bootstrap_api_path": "/api/bootstrap",
                "config_api_path": "/api/config",
                "scan_start_api_path": "/api/scan/start",
                "scan_status_api_path": "/api/scan/status",
                "annotation_api_path": "/api/annotations",
                "annotation_remove_api_path": "/api/annotations/remove",
                "translation_start_api_path": "/api/translation/start",
                "translation_stop_api_path": "/api/translation/stop",
                "translation_status_api_path": "/api/translation/status",
                "translation_accept_api_path": "/api/translation/accept",
                "translation_regenerate_api_path": "/api/translation/regenerate",
                "translation_reject_api_path": "/api/translation/reject",
            },
        )

    def bootstrap_payload(self):
        with self.lock:
            return {
                "config": self._config_payload(),
                "scan_status": dict(self.scan_status),
                "summary": dict(self.summary),
                "findings": [dict(item) for item in self.findings],
                "has_results": bool(self.findings),
                "results_revision": self.results_revision,
                "translation": self.translation_payload_locked(),
            }

    def scan_status_payload(self):
        with self.lock:
            return dict(self.scan_status)

    def save_config(self, payload):
        with self.lock:
            next_app_state = self._build_updated_app_state(payload)
            if payload and "model_config" in payload:
                self._validate_model_config(next_app_state)
            self.app_state = next_app_state
            self.translation_auto_accept = bool(self.app_state["translation_config"].get("auto_accept", False))
            self._persist_app_state()
            return self.bootstrap_payload()

    def start_scan(self, payload):
        with self.lock:
            if self.scan_status["status"] == "running":
                raise ValueError("A scan is already running.")
            if self.translation_session is not None and self.translation_session.snapshot()["status"]["status"] == "running":
                raise ValueError("A translation task is already running.")
            self._update_config(payload)
            repos = self._build_repos(self.app_state["scan_roots"])
            self._persist_app_state()
            self.scan_status = {
                "status": "running",
                "message": "扫描中",
                "total": 0,
                "processed": 0,
                "current_repo": "",
                "current_path": "",
                "started_at": self._timestamp(),
                "finished_at": "",
                "error": "",
            }
            scan_settings = scan_settings_from_state(self.app_state)
            self.scan_thread = threading.Thread(
                target=self._run_scan_job,
                args=(repos, scan_settings),
                name="zh-audit-scan",
                daemon=True,
            )
            self.scan_thread.start()
            return self.scan_status_payload()

    def start_translation(self, payload):
        with self.lock:
            if self.scan_status["status"] == "running":
                raise ValueError("A scan is already running.")
            if self.translation_session is not None and self.translation_session.snapshot()["status"]["status"] == "running":
                raise ValueError("A translation task is already running.")
            self._update_config({"translation_config": payload})
            self._persist_app_state()
            translation_config = self.app_state.get("translation_config", default_translation_config())
            source_path = Path(translation_config.get("source_path", "")).expanduser()
            target_path = Path(translation_config.get("target_path", "")).expanduser()
            if not source_path.exists():
                raise ValueError("Chinese properties file does not exist: {}".format(source_path))
            if not target_path.exists():
                raise ValueError("English properties file does not exist: {}".format(target_path))
            if source_path.is_dir() or target_path.is_dir():
                raise ValueError("Translation paths must point to files, not directories.")
            model_config = self._effective_model_config()
            if not model_config.get("base_url") or not model_config.get("api_key") or not model_config.get("model"):
                raise ValueError("Model config is incomplete. Please complete Base URL, API Key and model first.")
            self._reload_terminology()
            if self.terminology_error:
                raise ValueError(self.terminology_error)
            self.translation_session = TranslationSession(
                source_path=source_path.resolve(),
                target_path=target_path.resolve(),
                glossary=self.terminology,
                model_config=model_config,
                model_runner=self._translation_model_runner,
            )
            self.translation_session.start()
            self.translation_thread = threading.Thread(
                target=self._run_translation_job,
                args=(self.translation_session,),
                name="zh-audit-translation",
                daemon=True,
            )
            self.translation_thread.start()
            return self.translation_payload_locked()

    def stop_translation(self):
        with self.lock:
            session = self._require_translation_session()
            session.stop()
            return self.translation_payload_locked()

    def translation_accept(self, item_id):
        with self.lock:
            session = self._require_translation_session()
        session.accept(item_id)
        return self.translation_payload()

    def translation_regenerate(self, item_id, prompt):
        with self.lock:
            session = self._require_translation_session()
        session.regenerate(item_id, prompt)
        return self.translation_payload()

    def translation_reject(self, item_id):
        with self.lock:
            session = self._require_translation_session()
        session.reject(item_id)
        return self.translation_payload()

    def translation_payload(self):
        with self.lock:
            return self.translation_payload_locked()

    def annotate(self, finding_id, reason):
        with self.lock:
            finding = self._find_by_id(finding_id)
            if finding is None:
                raise KeyError("Unknown finding id: {}".format(finding_id))
            if finding.get("action") != "fix" and not finding.get("annotated"):
                raise ValueError("Only fix findings can be annotated as no-change.")
            upsert_annotation(self.annotation_store, finding, reason)
            self._reapply_annotations_and_persist()
            return self.bootstrap_payload()

    def remove_annotation(self, finding_id):
        with self.lock:
            finding = self._find_by_id(finding_id)
            if finding is None:
                raise KeyError("Unknown finding id: {}".format(finding_id))
            if not finding.get("annotated"):
                raise ValueError("Finding is not annotated.")
            remove_annotation(self.annotation_store, finding)
            self._reapply_annotations_and_persist()
            return self.bootstrap_payload()

    def _run_scan_job(self, repos, scan_settings):
        try:
            artifacts = run_scan(
                repos,
                scan_settings=scan_settings,
                run_id=datetime.now().strftime("%Y%m%d-%H%M%S"),
                progress_callback=self._scan_progress,
                annotation_store=self.annotation_store,
            )
            findings = [item.to_dict() for item in artifacts.findings]
            with self.lock:
                self.findings = findings
                self.summary = dict(artifacts.summary)
                self.annotation_stats = dict(self.summary.get("annotations", ANNOTATION_STATS_DEFAULT))
                self.results_revision += 1
                self.scan_status = {
                    "status": "done",
                    "message": "扫描完成",
                    "total": int(self.scan_status.get("total", 0)),
                    "processed": int(self.scan_status.get("processed", 0)),
                    "current_repo": self.scan_status.get("current_repo", ""),
                    "current_path": "扫描完成",
                    "started_at": self.scan_status.get("started_at", ""),
                    "finished_at": self._timestamp(),
                    "error": "",
                }
                self._persist_results()
        except Exception as exc:
            with self.lock:
                self.scan_status = {
                    "status": "failed",
                    "message": "扫描失败",
                    "total": int(self.scan_status.get("total", 0)),
                    "processed": int(self.scan_status.get("processed", 0)),
                    "current_repo": self.scan_status.get("current_repo", ""),
                    "current_path": self.scan_status.get("current_path", ""),
                    "started_at": self.scan_status.get("started_at", ""),
                    "finished_at": self._timestamp(),
                    "error": str(exc),
                }
        finally:
            with self.lock:
                self.scan_thread = None

    def _run_translation_job(self, session):
        try:
            session.run(should_auto_accept=self._translation_auto_accept)
        except Exception as exc:
            with session.lock:
                session.status = "failed"
                session.message = "校译失败"
                session.error = str(exc)
                session.finished_at = self._timestamp()
                session.current = {"key": "", "source_text": "", "status": ""}
        finally:
            with self.lock:
                self.translation_thread = None

    def _scan_progress(self, stage, **payload):
        with self.lock:
            current = dict(self.scan_status)
            if stage == "start":
                current["total"] = int(payload.get("total", 0))
                current["processed"] = 0
                current["current_repo"] = ""
                current["current_path"] = ""
                current["message"] = "准备扫描"
            elif stage == "repo":
                current["current_repo"] = str(payload.get("repo", ""))
                current["current_path"] = "准备扫描项目"
                current["message"] = "切换项目"
            elif stage == "file":
                current["processed"] = int(payload.get("processed", current.get("processed", 0)))
                current["total"] = int(payload.get("total", current.get("total", 0)))
                current["current_repo"] = str(payload.get("repo", ""))
                current["current_path"] = str(payload.get("relative_path", ""))
                current["message"] = "扫描中"
            elif stage == "done":
                current["processed"] = int(payload.get("processed", current.get("processed", 0)))
                current["total"] = int(payload.get("total", current.get("total", 0)))
                current["current_path"] = "扫描完成"
                current["message"] = "整理结果"
            self.scan_status = current

    def _build_updated_app_state(self, payload):
        payload = payload or {}
        roots = payload.get("scan_roots", self.app_state.get("scan_roots", []))
        scan_policy = payload.get("scan_policy", self.app_state.get("scan_policy", {}))
        translation_config = payload.get("translation_config", self.app_state.get("translation_config", {}))
        model_config_overrides = dict(self.app_state.get("model_config_overrides", {}))
        if "model_config" in payload:
            try:
                model_config_overrides = diff_model_config_overrides(payload.get("model_config"), self._base_model_config())
            except ValueError as exc:
                if "model_config.base_url" in str(exc):
                    raise ValueError("模型配置中的 Base URL 格式不正确，必须是完整的 http(s) 地址。")
                raise
        return {
            "version": self.app_state.get("version", default_app_state()["version"]),
            "scan_roots": normalize_scan_roots(roots),
            "scan_policy": normalize_scan_policy(scan_policy),
            "model_config_overrides": model_config_overrides,
            "translation_config": normalize_translation_config(translation_config),
        }

    def _update_config(self, payload):
        self.app_state = self._build_updated_app_state(payload)
        self.translation_auto_accept = bool(self.app_state["translation_config"].get("auto_accept", False))

    def _persist_app_state(self):
        write_app_state(self.app_state_path, self.app_state)

    def _persist_results(self):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.findings_path.write_text(
            json.dumps(self.findings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.summary_path.write_text(
            json.dumps(self.summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        write_annotation_store(self.annotations_path, self.annotation_store)
        self.report_path.write_text(
            render_report(
                self.summary,
                self.findings,
                client_config={
                    "mode": "static",
                    "annotation_api_path": "",
                    "annotation_remove_api_path": "",
                    "readonly_message": "当前报告为只读模式，请使用 zh-audit serve 打开本地服务版本。",
                    "annotation_path": str(self.annotations_path),
                },
            ),
            encoding="utf-8",
        )

    def _reapply_annotations_and_persist(self):
        self.annotation_stats = apply_annotation_store(self.findings, self.annotation_store)
        self.summary = refresh_summary(self.summary, self.findings, annotation_stats=self.annotation_stats)
        self.results_revision += 1
        self._persist_results()

    def _find_by_id(self, finding_id):
        for item in self.findings:
            if item.get("id") == finding_id:
                return item
        return None

    def _build_repos(self, roots):
        if not roots:
            raise ValueError("At least one scan directory is required.")
        repos = []
        for root in roots:
            path = Path(root).expanduser()
            if not path.exists():
                raise ValueError("Scan directory does not exist: {}".format(root))
            if not path.is_dir():
                raise ValueError("Scan directory is not a directory: {}".format(root))
            repos.append(RepoSpec(path=path.resolve()))
        return repos

    def _config_payload(self):
        return {
            "scan_roots": list(self.app_state.get("scan_roots", [])),
            "scan_policy": dict(self.app_state.get("scan_policy", default_app_state()["scan_policy"])),
            "model_config": self._effective_model_config(),
            "translation_config": dict(self.app_state.get("translation_config", default_translation_config())),
            "out_dir": str(self.out_dir),
        }

    def _base_model_config(self):
        return merge_model_config(self.project_model_config)

    def _effective_model_config(self, app_state=None):
        effective_state = self.app_state if app_state is None else app_state
        return merge_model_config(self.project_model_config, effective_state.get("model_config_overrides", {}))

    def _validate_model_config(self, app_state=None):
        model_config = self._effective_model_config(app_state)
        probe_openai_compatible_model(model_config)

    def _idle_scan_status(self):
        return {
            "status": "idle",
            "message": "等待扫描",
            "total": 0,
            "processed": 0,
            "current_repo": "",
            "current_path": "",
            "started_at": "",
            "finished_at": "",
            "error": "",
        }

    def _reload_terminology(self):
        try:
            self.terminology = load_terminology_xlsx(self.terminology_path)
            self.terminology_error = ""
        except Exception as exc:
            self.terminology = {}
            self.terminology_error = str(exc)

    def translation_payload_locked(self):
        self._reload_terminology()
        session_snapshot = None
        if self.translation_session is not None:
            session_snapshot = self.translation_session.snapshot()
        if session_snapshot is None:
            session_snapshot = {
                "config": dict(self.app_state.get("translation_config", default_translation_config())),
                "status": {
                    "status": "idle",
                    "message": "等待校译",
                    "error": "",
                    "started_at": "",
                    "finished_at": "",
                    "backup_path": "",
                    "current": {"key": "", "source_text": "", "status": ""},
                    "counts": {
                        "total": 0,
                        "processed": 0,
                        "skipped": 0,
                        "pending": 0,
                        "accepted": 0,
                        "appended": 0,
                        "failed": 0,
                        "rejected": 0,
                        "regenerated": 0,
                        "glossary_applied": 0,
                    },
                },
                "pending_items": [],
                "recent_items": [],
                "events": [],
            }
        session_snapshot["config"] = dict(self.app_state.get("translation_config", default_translation_config()))
        session_snapshot["terminology"] = {
            "path": str(self.terminology_path),
            "count": len(self.terminology),
            "error": self.terminology_error,
        }
        return session_snapshot

    def _translation_model_runner(self, key, source_text, target_text, locked_terms, model_config, extra_prompt, target_missing):
        response = call_openai_compatible_json(
            model_config=model_config,
            system_prompt=build_translation_system_prompt(),
            user_prompt=build_translation_user_prompt(
                key=key,
                source_text=source_text,
                target_text=target_text,
                locked_terms=locked_terms,
                extra_prompt=extra_prompt,
                target_missing=target_missing,
            ),
            max_tokens=model_config.get("max_tokens"),
        )
        return response

    def _translation_auto_accept(self):
        return bool(self.translation_auto_accept)

    def _require_translation_session(self):
        if self.translation_session is None:
            raise ValueError("No translation task has been created yet.")
        return self.translation_session

    def _timestamp(self):
        return datetime.now().astimezone().replace(microsecond=0).isoformat()


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class AppRequestHandler(BaseHTTPRequestHandler):
    server_version = "ZhAuditApp/1.0"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._send_html(self.server.app_state.render_home())
            return
        if parsed.path == "/api/bootstrap":
            self._send_json(200, self.server.app_state.bootstrap_payload())
            return
        if parsed.path == "/api/scan/status":
            self._send_json(200, self.server.app_state.scan_status_payload())
            return
        if parsed.path == "/api/translation/status":
            self._send_json(200, self.server.app_state.translation_payload())
            return
        self._send_json(404, {"error": "not_found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        payload = self._read_json_body()
        try:
            if parsed.path == "/api/config":
                self._send_json(200, self.server.app_state.save_config(payload))
                return
            if parsed.path == "/api/scan/start":
                self._send_json(200, self.server.app_state.start_scan(payload))
                return
            if parsed.path == "/api/annotations":
                self._send_json(
                    200,
                    self.server.app_state.annotate(payload.get("finding_id", ""), payload.get("reason", "")),
                )
                return
            if parsed.path == "/api/annotations/remove":
                self._send_json(200, self.server.app_state.remove_annotation(payload.get("finding_id", "")))
                return
            if parsed.path == "/api/translation/start":
                self._send_json(200, self.server.app_state.start_translation(payload))
                return
            if parsed.path == "/api/translation/stop":
                self._send_json(200, self.server.app_state.stop_translation())
                return
            if parsed.path == "/api/translation/accept":
                self._send_json(200, self.server.app_state.translation_accept(payload.get("item_id", "")))
                return
            if parsed.path == "/api/translation/regenerate":
                self._send_json(
                    200,
                    self.server.app_state.translation_regenerate(payload.get("item_id", ""), payload.get("prompt", "")),
                )
                return
            if parsed.path == "/api/translation/reject":
                self._send_json(200, self.server.app_state.translation_reject(payload.get("item_id", "")))
                return
        except Exception as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(404, {"error": "not_found"})

    def log_message(self, fmt, *args):
        return

    def _read_json_body(self):
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except ValueError:
            payload = {}
        if not isinstance(payload, dict):
            return {}
        return payload

    def _send_html(self, body):
        content = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, status, payload):
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def serve_app(out_dir, host="127.0.0.1", port=8765, annotations_path=None, app_state_path=None, project_config_path=None):
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    state = AppServiceState(
        out_dir=output_dir,
        annotations_path=annotations_path,
        app_state_path=app_state_path,
        project_config_path=project_config_path,
    )
    server = _ThreadingHTTPServer((host, int(port)), AppRequestHandler)
    server.app_state = state
    return server
