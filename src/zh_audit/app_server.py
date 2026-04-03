import json
import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import urlparse

from zh_audit.app_state import (
    default_custom_keep_categories,
    default_app_state,
    default_po_translation_config,
    default_sql_translation_config,
    default_translation_config,
    diff_model_config_overrides,
    load_app_state,
    merge_model_config,
    normalize_custom_keep_categories,
    normalize_po_translation_config,
    normalize_scan_policy,
    normalize_scan_roots,
    normalize_sql_translation_config,
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
from zh_audit.remediation_state import (
    apply_remediation_state,
    default_remediation_state,
    load_remediation_state,
    remove_resolved,
    upsert_resolved,
    write_remediation_state,
)
from zh_audit.report import render_report
from zh_audit.session_store import load_json_file, write_json_atomically
from zh_audit.po_translation_workflow import (
    PoTranslationSession,
    build_po_translation_review_system_prompt,
    build_po_translation_review_user_prompt,
    build_po_translation_system_prompt,
    build_po_translation_user_prompt,
)
from zh_audit.plain_translation_prompts import (
    build_plain_translation_review_system_prompt,
    build_plain_translation_review_user_prompt,
    build_plain_translation_system_prompt,
    build_plain_translation_user_prompt,
)
from zh_audit.single_translation import translate_single_text
from zh_audit.sql_translation_workflow import (
    SqlTranslationSession,
    build_sql_translation_review_system_prompt,
    build_sql_translation_review_user_prompt,
    build_sql_translation_system_prompt,
    build_sql_translation_user_prompt,
)
from zh_audit.terminology_xlsx import load_terminology_xlsx, normalize_terminology_catalog
from zh_audit.translation_workflow import (
    TranslationSession,
    build_translation_review_system_prompt,
    build_translation_review_user_prompt,
    build_translation_system_prompt,
    build_translation_user_prompt,
)


class AppServiceState(object):
    def __init__(self, out_dir, app_state_path=None, project_config_path=None):
        self.out_dir = Path(out_dir)
        self.findings_path = self.out_dir / "findings.json"
        self.summary_path = self.out_dir / "summary.json"
        self.report_path = self.out_dir / "report.html"
        self.remediation_state_path = self.out_dir / "remediation_state.json"
        self.translation_session_path = self.out_dir / "translation_session.json"
        self.po_translation_session_path = self.out_dir / "po_translation_session.json"
        self.sql_translation_session_path = self.out_dir / "sql_translation_session.json"
        self.app_state_path = Path(app_state_path) if app_state_path is not None else (self.out_dir / "app_state.json")
        self.project_config_path = Path(project_config_path) if project_config_path is not None else None
        self.lock = threading.RLock()
        self.scan_thread = None
        self.translation_thread = None
        self.po_translation_thread = None
        self.sql_translation_thread = None
        self.results_revision = 0
        self.summary = {}
        self.findings = []
        self.remediation_state = default_remediation_state()
        self.translation_session = None
        self.po_translation_session = None
        self.sql_translation_session = None
        self.single_translation_source_text = ""
        self.single_translation_result = _default_single_translation_result()
        self.project_model_config = (
            load_project_model_config(self.project_config_path) if self.project_config_path is not None else {}
        )
        self.app_state = load_app_state(self.app_state_path)
        self.translation_auto_accept = bool(self.app_state.get("translation_config", {}).get("auto_accept", False))
        self.po_translation_auto_accept = bool(self.app_state.get("po_translation_config", {}).get("auto_accept", False))
        self.sql_translation_auto_accept = bool(
            self.app_state.get("sql_translation_config", {}).get("auto_accept", False)
        )
        self.scan_status = self._idle_scan_status()
        self.terminology_path = Path(__file__).resolve().parents[2] / "resources" / "国际化专业术语词典.xlsx"
        self.terminology = normalize_terminology_catalog({})
        self.terminology_error = ""
        self._reload_terminology()
        self._restore_remediation_state()
        self._restore_results()
        self._restore_translation_session()
        self._restore_po_translation_session()
        self._restore_sql_translation_session()

    def render_home(self):
        return render_app_shell(
            self.bootstrap_payload(),
            client_config={
                "bootstrap_api_path": "/api/bootstrap",
                "config_api_path": "/api/config",
                "scan_start_api_path": "/api/scan/start",
                "scan_status_api_path": "/api/scan/status",
                "finding_resolve_api_path": "/api/findings/resolve",
                "finding_reopen_api_path": "/api/findings/reopen",
                "translation_start_api_path": "/api/translation/start",
                "translation_stop_api_path": "/api/translation/stop",
                "translation_resume_api_path": "/api/translation/resume",
                "translation_status_api_path": "/api/translation/status",
                "translation_accept_api_path": "/api/translation/accept",
                "translation_regenerate_api_path": "/api/translation/regenerate",
                "translation_reject_api_path": "/api/translation/reject",
                "po_translation_start_api_path": "/api/po-translation/start",
                "po_translation_stop_api_path": "/api/po-translation/stop",
                "po_translation_resume_api_path": "/api/po-translation/resume",
                "po_translation_status_api_path": "/api/po-translation/status",
                "po_translation_accept_api_path": "/api/po-translation/accept",
                "po_translation_regenerate_api_path": "/api/po-translation/regenerate",
                "po_translation_reject_api_path": "/api/po-translation/reject",
                "sql_translation_start_api_path": "/api/sql-translation/start",
                "sql_translation_stop_api_path": "/api/sql-translation/stop",
                "sql_translation_resume_api_path": "/api/sql-translation/resume",
                "sql_translation_status_api_path": "/api/sql-translation/status",
                "sql_translation_accept_api_path": "/api/sql-translation/accept",
                "sql_translation_regenerate_api_path": "/api/sql-translation/regenerate",
                "sql_translation_reject_api_path": "/api/sql-translation/reject",
                "single_translation_translate_api_path": "/api/single-translation/translate",
                "single_translation_reset_api_path": "/api/single-translation/reset",
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
                "po_translation": self.po_translation_payload_locked(),
                "sql_translation": self.sql_translation_payload_locked(),
                "single_translation": self.single_translation_payload_locked(),
            }

    def scan_status_payload(self):
        with self.lock:
            return dict(self.scan_status)

    def resolve_finding(self, finding_id):
        with self.lock:
            finding = self._find_finding_by_id_locked(finding_id)
            if finding is None:
                raise KeyError("Unknown finding id: {}".format(finding_id))
            if str(finding.get("action", "")) != "fix":
                raise ValueError("Only fix findings can be marked as resolved.")
            upsert_resolved(self.remediation_state, finding, self._timestamp())
            finding["action"] = "resolved"
            self._refresh_and_persist_remediation_locked()
            return self._finding_update_payload_locked(finding)

    def reopen_finding(self, finding_id):
        with self.lock:
            finding = self._find_finding_by_id_locked(finding_id)
            if finding is None:
                raise KeyError("Unknown finding id: {}".format(finding_id))
            if str(finding.get("action", "")) != "resolved":
                raise ValueError("Only resolved findings can be reopened.")
            remove_resolved(self.remediation_state, finding)
            finding["action"] = "fix"
            self._refresh_and_persist_remediation_locked()
            return self._finding_update_payload_locked(finding)

    def save_config(self, payload):
        with self.lock:
            next_app_state = self._build_updated_app_state(payload)
            if payload and "model_config" in payload:
                self._validate_model_config(next_app_state)
            self.app_state = next_app_state
            self.translation_auto_accept = bool(self.app_state["translation_config"].get("auto_accept", False))
            self.po_translation_auto_accept = bool(self.app_state["po_translation_config"].get("auto_accept", False))
            self.sql_translation_auto_accept = bool(self.app_state["sql_translation_config"].get("auto_accept", False))
            self._persist_app_state()
            return self.bootstrap_payload()

    def start_scan(self, payload):
        with self.lock:
            if self.scan_status["status"] == "running":
                raise ValueError("A scan is already running.")
            if self._has_running_task_locked():
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
            custom_keep_categories = list(self.app_state.get("custom_keep_categories", default_custom_keep_categories()))
            self.scan_thread = threading.Thread(
                target=self._run_scan_job,
                args=(repos, scan_settings, custom_keep_categories),
                name="zh-audit-scan",
                daemon=True,
            )
            self.scan_thread.start()
            return self.scan_status_payload()

    def start_translation(self, payload):
        with self.lock:
            if self.scan_status["status"] == "running":
                raise ValueError("A scan is already running.")
            if self._has_running_task_locked():
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
            model_config = self._require_model_config()
            self._reload_terminology()
            if self.terminology_error:
                raise ValueError(self.terminology_error)
            self.translation_session = TranslationSession(
                source_path=source_path.resolve(),
                target_path=target_path.resolve(),
                glossary=self._translation_glossary(),
                model_config=model_config,
                model_runner=self._translation_model_runner,
                reviewer_runner=self._translation_reviewer_runner,
                persist_callback=self._persist_translation_session,
            )
            self.translation_session.start()
            self._start_translation_thread_locked(self.translation_session)
            return self.translation_payload_locked()

    def resume_translation(self):
        with self.lock:
            if self.scan_status["status"] == "running":
                raise ValueError("A scan is already running.")
            if self.sql_translation_session is not None and self._session_status(self.sql_translation_session) == "running":
                raise ValueError("A SQL translation task is already running.")
            if self.po_translation_session is not None and self._session_status(self.po_translation_session) == "running":
                raise ValueError("A PO translation task is already running.")
            session = self._require_translation_session()
            model_config = self._require_model_config()
            self._reload_terminology()
            if self.terminology_error:
                raise ValueError(self.terminology_error)
            with session.lock:
                session.model_config = dict(model_config)
                session.glossary = self._translation_glossary()
                session.reviewer_runner = self._translation_reviewer_runner
            session.resume()
            self._start_translation_thread_locked(session)
            return self.translation_payload_locked()

    def stop_translation(self):
        with self.lock:
            session = self._require_translation_session()
            session.stop()
            return self.translation_payload_locked()

    def translation_accept(self, item_id, candidate_text=""):
        with self.lock:
            session = self._require_translation_session()
        session.accept(item_id, candidate_text=candidate_text)
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

    def start_po_translation(self, payload):
        with self.lock:
            if self.scan_status["status"] == "running":
                raise ValueError("A scan is already running.")
            if self._has_running_task_locked():
                raise ValueError("A translation task is already running.")
            self._update_config({"po_translation_config": payload})
            self._persist_app_state()
            po_config = self.app_state.get("po_translation_config", default_po_translation_config())
            po_path = Path(po_config.get("po_path", "")).expanduser()
            if not po_path.exists():
                raise ValueError("PO file does not exist: {}".format(po_path))
            if po_path.is_dir():
                raise ValueError("PO path must point to a file, not a directory.")
            model_config = self._require_model_config()
            self._reload_terminology()
            if self.terminology_error:
                raise ValueError(self.terminology_error)
            self.po_translation_session = PoTranslationSession(
                po_path=po_path.resolve(),
                glossary=self._po_translation_glossary(),
                model_config=model_config,
                model_runner=self._po_translation_model_runner,
                reviewer_runner=self._po_translation_reviewer_runner,
                persist_callback=self._persist_po_translation_session,
            )
            self.po_translation_session.start()
            self._start_po_translation_thread_locked(self.po_translation_session)
            return self.po_translation_payload_locked()

    def resume_po_translation(self):
        with self.lock:
            if self.scan_status["status"] == "running":
                raise ValueError("A scan is already running.")
            if self.translation_session is not None and self._session_status(self.translation_session) == "running":
                raise ValueError("An i18n translation task is already running.")
            if self.sql_translation_session is not None and self._session_status(self.sql_translation_session) == "running":
                raise ValueError("A SQL translation task is already running.")
            session = self._require_po_translation_session()
            model_config = self._require_model_config()
            self._reload_terminology()
            if self.terminology_error:
                raise ValueError(self.terminology_error)
            with session.lock:
                session.model_config = dict(model_config)
                session.set_glossary(self._po_translation_glossary())
                session.reviewer_runner = self._po_translation_reviewer_runner
            session.resume()
            self._start_po_translation_thread_locked(session)
            return self.po_translation_payload_locked()

    def stop_po_translation(self):
        with self.lock:
            session = self._require_po_translation_session()
            session.stop()
            return self.po_translation_payload_locked()

    def po_translation_accept(self, item_id, candidate_text=""):
        with self.lock:
            session = self._require_po_translation_session()
        session.accept(item_id, candidate_text=candidate_text)
        return self.po_translation_payload()

    def po_translation_regenerate(self, item_id, prompt):
        with self.lock:
            session = self._require_po_translation_session()
        session.regenerate(item_id, prompt)
        return self.po_translation_payload()

    def po_translation_reject(self, item_id):
        with self.lock:
            session = self._require_po_translation_session()
        session.reject(item_id)
        return self.po_translation_payload()

    def po_translation_payload(self):
        with self.lock:
            return self.po_translation_payload_locked()

    def start_sql_translation(self, payload):
        with self.lock:
            if self.scan_status["status"] == "running":
                raise ValueError("A scan is already running.")
            if self._has_running_task_locked():
                raise ValueError("A translation task is already running.")
            self._update_config({"sql_translation_config": payload})
            self._persist_app_state()
            sql_config = self.app_state.get("sql_translation_config", default_sql_translation_config())
            directory_path = Path(sql_config.get("directory_path", "")).expanduser()
            table_name = str(sql_config.get("table_name", "") or "").strip()
            source_field = str(sql_config.get("source_field", "") or "").strip()
            target_field = str(sql_config.get("target_field", "") or "").strip()
            primary_key_field = str(sql_config.get("primary_key_field", "") or "id").strip() or "id"
            schema_sql = str(sql_config.get("schema_sql", "") or "")
            if not directory_path.exists():
                raise ValueError("SQL directory does not exist: {}".format(directory_path))
            if not directory_path.is_dir():
                raise ValueError("SQL path is not a directory: {}".format(directory_path))
            if not table_name or not source_field or not target_field:
                raise ValueError("SQL translation config requires table_name, source_field and target_field.")
            model_config = self._require_model_config()
            self._reload_terminology()
            if self.terminology_error:
                raise ValueError(self.terminology_error)
            self.sql_translation_session = SqlTranslationSession(
                directory_path=directory_path.resolve(),
                table_name=table_name,
                primary_key_field=primary_key_field,
                source_field=source_field,
                target_field=target_field,
                schema_sql=schema_sql,
                glossary=self._sql_translation_glossary(),
                model_config=model_config,
                model_runner=self._sql_translation_model_runner,
                reviewer_runner=self._sql_translation_reviewer_runner,
                persist_callback=self._persist_sql_translation_session,
            )
            self.sql_translation_session.start()
            self._start_sql_translation_thread_locked(self.sql_translation_session)
            return self.sql_translation_payload_locked()

    def resume_sql_translation(self):
        with self.lock:
            if self.scan_status["status"] == "running":
                raise ValueError("A scan is already running.")
            if self.translation_session is not None and self._session_status(self.translation_session) == "running":
                raise ValueError("A translation task is already running.")
            if self.po_translation_session is not None and self._session_status(self.po_translation_session) == "running":
                raise ValueError("A PO translation task is already running.")
            session = self._require_sql_translation_session()
            model_config = self._require_model_config()
            self._reload_terminology()
            if self.terminology_error:
                raise ValueError(self.terminology_error)
            with session.lock:
                session.model_config = dict(model_config)
                session.glossary = self._sql_translation_glossary()
                session.reviewer_runner = self._sql_translation_reviewer_runner
            session.resume()
            self._start_sql_translation_thread_locked(session)
            return self.sql_translation_payload_locked()

    def stop_sql_translation(self):
        with self.lock:
            session = self._require_sql_translation_session()
            session.stop()
            return self.sql_translation_payload_locked()

    def sql_translation_accept(self, item_id, candidate_text=""):
        with self.lock:
            session = self._require_sql_translation_session()
        session.accept(item_id, candidate_text=candidate_text)
        return self.sql_translation_payload()

    def sql_translation_regenerate(self, item_id, prompt):
        with self.lock:
            session = self._require_sql_translation_session()
        session.regenerate(item_id, prompt)
        return self.sql_translation_payload()

    def sql_translation_reject(self, item_id):
        with self.lock:
            session = self._require_sql_translation_session()
        session.reject(item_id)
        return self.sql_translation_payload()

    def sql_translation_payload(self):
        with self.lock:
            return self.sql_translation_payload_locked()

    def translate_single_text(self, payload):
        source_text = str((payload or {}).get("source_text", "") or "")
        with self.lock:
            self.single_translation_source_text = source_text.strip()
            try:
                model_config = self._require_model_config()
            except Exception as exc:
                self.single_translation_result = _failed_single_translation_result(str(exc), mode="")
                return self.single_translation_payload_locked()
            self._reload_terminology()
            if self.terminology_error:
                self.single_translation_result = _failed_single_translation_result(self.terminology_error, mode="")
                return self.single_translation_payload_locked()
            glossary = self.terminology

        try:
            result = translate_single_text(
                source_text=source_text,
                glossary=glossary,
                model_config=model_config,
                plain_model_runner=self._single_translation_plain_model_runner,
                plain_reviewer_runner=self._single_translation_plain_reviewer_runner,
                rst_model_runner=self._single_translation_rst_model_runner,
                rst_reviewer_runner=self._single_translation_rst_reviewer_runner,
            )
        except Exception as exc:
            result = _failed_single_translation_result(str(exc), mode="")

        with self.lock:
            self.single_translation_result = dict(result)
            return self.single_translation_payload_locked()

    def reset_single_translation(self):
        with self.lock:
            self.single_translation_source_text = ""
            self.single_translation_result = _default_single_translation_result()
            return self.single_translation_payload_locked()

    def _run_scan_job(self, repos, scan_settings, custom_keep_categories):
        try:
            artifacts = run_scan(
                repos,
                scan_settings=scan_settings,
                custom_keep_categories=custom_keep_categories,
                run_id=datetime.now().strftime("%Y%m%d-%H%M%S"),
                progress_callback=self._scan_progress,
            )
            findings = [item.to_dict() for item in artifacts.findings]
            with self.lock:
                self._reset_resolved_actions_locked(findings)
                apply_remediation_state(findings, self.remediation_state)
                self.findings = findings
                self.summary = refresh_summary(dict(artifacts.summary), self.findings)
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
                self._refresh_and_persist_results_locked()
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
            session.interrupt(str(exc))
        finally:
            with self.lock:
                if self.translation_session is session:
                    self.translation_thread = None

    def _run_po_translation_job(self, session):
        try:
            session.run(should_auto_accept=self._po_translation_auto_accept)
        except Exception as exc:
            session.interrupt(str(exc))
        finally:
            with self.lock:
                if self.po_translation_session is session:
                    self.po_translation_thread = None

    def _run_sql_translation_job(self, session):
        try:
            session.run(should_auto_accept=self._sql_translation_auto_accept)
        except Exception as exc:
            session.interrupt(str(exc))
        finally:
            with self.lock:
                if self.sql_translation_session is session:
                    self.sql_translation_thread = None

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
        custom_keep_categories = payload.get(
            "custom_keep_categories",
            self.app_state.get("custom_keep_categories", default_custom_keep_categories()),
        )
        translation_config = payload.get("translation_config", self.app_state.get("translation_config", {}))
        po_translation_config = payload.get("po_translation_config", self.app_state.get("po_translation_config", {}))
        sql_translation_config = payload.get("sql_translation_config", self.app_state.get("sql_translation_config", {}))
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
            "custom_keep_categories": normalize_custom_keep_categories(custom_keep_categories),
            "translation_config": normalize_translation_config(translation_config),
            "po_translation_config": normalize_po_translation_config(po_translation_config),
            "sql_translation_config": normalize_sql_translation_config(sql_translation_config),
        }

    def _update_config(self, payload):
        self.app_state = self._build_updated_app_state(payload)
        self.translation_auto_accept = bool(self.app_state["translation_config"].get("auto_accept", False))
        self.po_translation_auto_accept = bool(self.app_state["po_translation_config"].get("auto_accept", False))
        self.sql_translation_auto_accept = bool(self.app_state["sql_translation_config"].get("auto_accept", False))

    def _persist_app_state(self):
        write_app_state(self.app_state_path, self.app_state)

    def _write_text_atomically(self, path, text):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target.with_name(target.name + ".tmp")
        temp_path.write_text(text, encoding="utf-8")
        os.replace(str(temp_path), str(target))

    def _write_results_artifacts(self, summary_payload, findings_payload):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        write_json_atomically(self.findings_path, findings_payload)
        write_json_atomically(self.summary_path, summary_payload)
        self._write_text_atomically(
            self.report_path,
            render_report(
                summary_payload,
                findings_payload,
                client_config={
                    "mode": "static",
                },
            ),
        )

    def _persist_results(self):
        self._write_results_artifacts(dict(self.summary), [dict(item) for item in self.findings])

    def _persist_remediation_state(self):
        write_remediation_state(self.remediation_state_path, self.remediation_state)

    def _persist_translation_session(self, payload):
        write_json_atomically(self.translation_session_path, payload)

    def _persist_po_translation_session(self, payload):
        write_json_atomically(self.po_translation_session_path, payload)

    def _persist_sql_translation_session(self, payload):
        write_json_atomically(self.sql_translation_session_path, payload)

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
            "custom_keep_categories": list(
                self.app_state.get("custom_keep_categories", default_custom_keep_categories())
            ),
            "translation_config": dict(self.app_state.get("translation_config", default_translation_config())),
            "po_translation_config": dict(
                self.app_state.get("po_translation_config", default_po_translation_config())
            ),
            "sql_translation_config": dict(
                self.app_state.get("sql_translation_config", default_sql_translation_config())
            ),
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

    def _require_model_config(self):
        model_config = self._effective_model_config()
        if not model_config.get("base_url") or not model_config.get("api_key") or not model_config.get("model"):
            raise ValueError("Model config is incomplete. Please complete Base URL, API Key and model first.")
        return model_config

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
            self.terminology = normalize_terminology_catalog({})
            self.terminology_error = str(exc)

    def _terminology_count(self):
        return int(getattr(self.terminology, "count", len(self.terminology)) or 0)

    def _translation_glossary(self):
        return dict(getattr(self.terminology, "non_frontend_glossary", {}) or {})

    def _sql_translation_glossary(self):
        return dict(getattr(self.terminology, "non_frontend_glossary", {}) or {})

    def _po_translation_glossary(self):
        return self.terminology

    def _restore_translation_session(self):
        payload = load_json_file(self.translation_session_path)
        if not isinstance(payload, dict):
            return
        try:
            self.translation_session = TranslationSession.from_saved_state(
                payload=payload,
                glossary=self._translation_glossary(),
                model_config=self._effective_model_config(),
                model_runner=self._translation_model_runner,
                reviewer_runner=self._translation_reviewer_runner,
                persist_callback=self._persist_translation_session,
            )
            self._persist_translation_session(self.translation_session.save_state())
        except Exception:
            self.translation_session = None

    def _restore_po_translation_session(self):
        payload = load_json_file(self.po_translation_session_path)
        if not isinstance(payload, dict):
            return
        try:
            self.po_translation_session = PoTranslationSession.from_saved_state(
                payload=payload,
                glossary=self._po_translation_glossary(),
                model_config=self._effective_model_config(),
                model_runner=self._po_translation_model_runner,
                reviewer_runner=self._po_translation_reviewer_runner,
                persist_callback=self._persist_po_translation_session,
            )
            self._persist_po_translation_session(self.po_translation_session.save_state())
        except Exception:
            self.po_translation_session = None

    def _restore_remediation_state(self):
        try:
            self.remediation_state = load_remediation_state(self.remediation_state_path)
        except Exception:
            self.remediation_state = default_remediation_state()

    def _restore_results(self):
        try:
            findings_payload = load_json_file(self.findings_path)
            summary_payload = load_json_file(self.summary_path)
        except Exception:
            return
        if not isinstance(findings_payload, list):
            return
        restored_findings = [dict(item) for item in findings_payload if isinstance(item, dict)]
        if not restored_findings:
            return
        self._reset_resolved_actions_locked(restored_findings)
        apply_remediation_state(restored_findings, self.remediation_state)
        self.findings = restored_findings
        base_summary = dict(summary_payload) if isinstance(summary_payload, dict) else {}
        self.summary = refresh_summary(base_summary, self.findings)
        self.results_revision = 1

    def _refresh_and_persist_results_locked(self):
        self.summary = refresh_summary(dict(self.summary), self.findings)
        self.results_revision += 1
        self._persist_remediation_state()
        self._persist_results()

    def _refresh_and_persist_remediation_locked(self):
        self.summary = refresh_summary(dict(self.summary), self.findings)
        self.results_revision += 1
        self._persist_remediation_state()

    def _find_finding_by_id_locked(self, finding_id):
        for finding in self.findings:
            if str(finding.get("id", "")) == str(finding_id):
                return finding
        return None

    def _reset_resolved_actions_locked(self, findings):
        for finding in findings:
            if str(finding.get("action", "")) == "resolved":
                finding["action"] = "fix"

    def _results_payload_locked(self):
        return {
            "summary": dict(self.summary),
            "findings": [dict(item) for item in self.findings],
            "has_results": bool(self.findings),
            "results_revision": self.results_revision,
        }

    def _finding_update_payload_locked(self, finding):
        return {
            "summary": dict(self.summary),
            "finding": dict(finding),
            "has_results": bool(self.findings),
            "results_revision": self.results_revision,
        }

    def _restore_sql_translation_session(self):
        payload = load_json_file(self.sql_translation_session_path)
        if not isinstance(payload, dict):
            return
        try:
            self.sql_translation_session = SqlTranslationSession.from_saved_state(
                payload=payload,
                glossary=self._sql_translation_glossary(),
                model_config=self._effective_model_config(),
                model_runner=self._sql_translation_model_runner,
                reviewer_runner=self._sql_translation_reviewer_runner,
                persist_callback=self._persist_sql_translation_session,
            )
            self._persist_sql_translation_session(self.sql_translation_session.save_state())
        except Exception:
            self.sql_translation_session = None

    def translation_payload_locked(self):
        self._reload_terminology()
        session_snapshot = None
        if self.translation_session is not None:
            session_snapshot = self.translation_session.snapshot()
        if session_snapshot is None:
            session_snapshot = _default_translation_payload()
        session_snapshot["config"] = dict(self.app_state.get("translation_config", default_translation_config()))
        session_snapshot["terminology"] = {
            "path": str(self.terminology_path),
            "count": self._terminology_count(),
            "error": self.terminology_error,
        }
        self._attach_resume_status(session_snapshot["status"])
        return session_snapshot

    def po_translation_payload_locked(self):
        self._reload_terminology()
        session_snapshot = None
        if self.po_translation_session is not None:
            session_snapshot = self.po_translation_session.snapshot()
        if session_snapshot is None:
            session_snapshot = _default_po_translation_payload()
        session_snapshot["config"] = dict(
            self.app_state.get("po_translation_config", default_po_translation_config())
        )
        session_snapshot["terminology"] = {
            "path": str(self.terminology_path),
            "count": self._terminology_count(),
            "error": self.terminology_error,
        }
        self._attach_resume_status(session_snapshot["status"])
        return session_snapshot

    def sql_translation_payload_locked(self):
        self._reload_terminology()
        session_snapshot = None
        if self.sql_translation_session is not None:
            session_snapshot = self.sql_translation_session.snapshot()
        if session_snapshot is None:
            session_snapshot = _default_sql_translation_payload()
        session_snapshot["config"] = dict(
            self.app_state.get("sql_translation_config", default_sql_translation_config())
        )
        session_snapshot["terminology"] = {
            "path": str(self.terminology_path),
            "count": self._terminology_count(),
            "error": self.terminology_error,
        }
        self._attach_resume_status(session_snapshot["status"], output_path=session_snapshot["status"].get("output_path", ""))
        return session_snapshot

    def single_translation_payload_locked(self):
        self._reload_terminology()
        payload = _default_single_translation_payload()
        payload["config"] = {
            "source_text": str(self.single_translation_source_text or ""),
        }
        payload["result"] = dict(self.single_translation_result or _default_single_translation_result())
        payload["terminology"] = {
            "path": str(self.terminology_path),
            "count": self._terminology_count(),
            "error": self.terminology_error,
        }
        return payload

    def _attach_resume_status(self, status, output_path=""):
        resume_available = str(status.get("status", "") or "") in ("interrupted", "stopped")
        if resume_available:
            prefix = "任务已中断，可继续执行" if status.get("status") == "interrupted" else "任务已停止，可继续执行"
            if output_path:
                resume_message = "{}；已生成内容保留在：{}".format(prefix, output_path)
            else:
                resume_message = prefix
        else:
            resume_message = ""
        status["resume_available"] = resume_available
        status["resume_message"] = resume_message
        return status

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

    def _translation_reviewer_runner(self, key, source_text, candidate_text, locked_terms, model_config, target_missing, extra_prompt):
        response = call_openai_compatible_json(
            model_config=model_config,
            system_prompt=build_translation_review_system_prompt(),
            user_prompt=build_translation_review_user_prompt(
                key=key,
                source_text=source_text,
                candidate_text=candidate_text,
                locked_terms=locked_terms,
                target_missing=target_missing,
                extra_prompt=extra_prompt,
            ),
            max_tokens=model_config.get("max_tokens"),
        )
        return response

    def _po_translation_model_runner(
        self,
        entry_id,
        references,
        source_text,
        target_text,
        protected_source,
        locked_terms,
        model_config,
        extra_prompt,
        target_missing,
    ):
        response = call_openai_compatible_json(
            model_config=model_config,
            system_prompt=build_po_translation_system_prompt(),
            user_prompt=build_po_translation_user_prompt(
                entry_id=entry_id,
                references=references,
                source_text=source_text,
                target_text=target_text,
                protected_source=protected_source,
                locked_terms=locked_terms,
                extra_prompt=extra_prompt,
                target_missing=target_missing,
            ),
            max_tokens=model_config.get("max_tokens"),
        )
        return response

    def _po_translation_reviewer_runner(
        self,
        entry_id,
        references,
        source_text,
        candidate_text,
        protected_source,
        locked_terms,
        model_config,
        target_missing,
        extra_prompt,
    ):
        response = call_openai_compatible_json(
            model_config=model_config,
            system_prompt=build_po_translation_review_system_prompt(),
            user_prompt=build_po_translation_review_user_prompt(
                entry_id=entry_id,
                references=references,
                source_text=source_text,
                candidate_text=candidate_text,
                protected_source=protected_source,
                locked_terms=locked_terms,
                target_missing=target_missing,
                extra_prompt=extra_prompt,
            ),
            max_tokens=model_config.get("max_tokens"),
        )
        return response

    def _sql_translation_model_runner(
        self,
        source_path,
        line,
        table_name,
        primary_key_field,
        primary_key_value,
        source_field,
        source_text,
        target_field,
        target_text,
        target_missing,
        locked_terms,
        model_config,
        extra_prompt,
    ):
        response = call_openai_compatible_json(
            model_config=model_config,
            system_prompt=build_sql_translation_system_prompt(),
            user_prompt=build_sql_translation_user_prompt(
                source_path=source_path,
                line=line,
                table_name=table_name,
                primary_key_field=primary_key_field,
                primary_key_value=primary_key_value,
                source_field=source_field,
                source_text=source_text,
                target_field=target_field,
                target_text=target_text,
                target_missing=target_missing,
                locked_terms=locked_terms,
                extra_prompt=extra_prompt,
            ),
            max_tokens=model_config.get("max_tokens"),
        )
        return response

    def _sql_translation_reviewer_runner(
        self,
        source_path,
        line,
        table_name,
        primary_key_field,
        primary_key_value,
        source_field,
        source_text,
        target_field,
        candidate_text,
        target_missing,
        locked_terms,
        model_config,
        extra_prompt,
    ):
        response = call_openai_compatible_json(
            model_config=model_config,
            system_prompt=build_sql_translation_review_system_prompt(),
            user_prompt=build_sql_translation_review_user_prompt(
                source_path=source_path,
                line=line,
                table_name=table_name,
                primary_key_field=primary_key_field,
                primary_key_value=primary_key_value,
                source_field=source_field,
                source_text=source_text,
                target_field=target_field,
                candidate_text=candidate_text,
                target_missing=target_missing,
                locked_terms=locked_terms,
                extra_prompt=extra_prompt,
            ),
            max_tokens=model_config.get("max_tokens"),
        )
        return response

    def _translation_auto_accept(self):
        return bool(self.translation_auto_accept)

    def _po_translation_auto_accept(self):
        return bool(self.po_translation_auto_accept)

    def _sql_translation_auto_accept(self):
        return bool(self.sql_translation_auto_accept)

    def _single_translation_plain_model_runner(
        self,
        source_text,
        target_text,
        locked_terms,
        model_config,
        extra_prompt,
        target_missing,
    ):
        payload = {
            "source_text": source_text,
            "target_text": target_text,
            "target_missing": bool(target_missing),
            "locked_terms": [
                {"source": term["source"], "target": term["target"]}
                for term in locked_terms
            ],
            "extra_prompt": extra_prompt or "",
        }
        return call_openai_compatible_json(
            model_config=model_config,
            system_prompt=build_plain_translation_system_prompt(
                role_description="single-line Chinese to English translations",
                candidate_requirement="candidate_translation must contain only the translated English text.",
            ),
            user_prompt=build_plain_translation_user_prompt(payload=payload, extra_prompt=extra_prompt),
            max_tokens=model_config.get("max_tokens"),
        )

    def _single_translation_plain_reviewer_runner(
        self,
        source_text,
        candidate_text,
        locked_terms,
        model_config,
        target_missing,
        extra_prompt,
    ):
        payload = {
            "source_text": source_text,
            "candidate_text": candidate_text,
            "target_missing": bool(target_missing),
            "locked_terms": [
                {"source": term["source"], "target": term["target"]}
                for term in locked_terms
            ],
            "extra_prompt": extra_prompt or "",
        }
        return call_openai_compatible_json(
            model_config=model_config,
            system_prompt=build_plain_translation_review_system_prompt(
                review_description="English single-text translations",
            ),
            user_prompt=build_plain_translation_review_user_prompt(payload=payload, extra_prompt=extra_prompt),
            max_tokens=model_config.get("max_tokens"),
        )

    def _single_translation_rst_model_runner(
        self,
        source_text,
        target_text,
        protected_source,
        locked_terms,
        model_config,
        extra_prompt,
        target_missing,
    ):
        return call_openai_compatible_json(
            model_config=model_config,
            system_prompt=build_po_translation_system_prompt(),
            user_prompt=build_po_translation_user_prompt(
                entry_id="single_translation",
                references=[],
                source_text=source_text,
                target_text=target_text,
                protected_source=protected_source,
                locked_terms=locked_terms,
                extra_prompt=extra_prompt,
                target_missing=target_missing,
            ),
            max_tokens=model_config.get("max_tokens"),
        )

    def _single_translation_rst_reviewer_runner(
        self,
        source_text,
        candidate_text,
        protected_source,
        locked_terms,
        model_config,
        target_missing,
        extra_prompt,
    ):
        return call_openai_compatible_json(
            model_config=model_config,
            system_prompt=build_po_translation_review_system_prompt(),
            user_prompt=build_po_translation_review_user_prompt(
                entry_id="single_translation",
                references=[],
                source_text=source_text,
                candidate_text=candidate_text,
                protected_source=protected_source,
                locked_terms=locked_terms,
                target_missing=target_missing,
                extra_prompt=extra_prompt,
            ),
            max_tokens=model_config.get("max_tokens"),
        )

    def _start_translation_thread_locked(self, session):
        self.translation_thread = threading.Thread(
            target=self._run_translation_job,
            args=(session,),
            name="zh-audit-translation",
            daemon=True,
        )
        self.translation_thread.start()

    def _start_po_translation_thread_locked(self, session):
        self.po_translation_thread = threading.Thread(
            target=self._run_po_translation_job,
            args=(session,),
            name="zh-audit-po-translation",
            daemon=True,
        )
        self.po_translation_thread.start()

    def _start_sql_translation_thread_locked(self, session):
        self.sql_translation_thread = threading.Thread(
            target=self._run_sql_translation_job,
            args=(session,),
            name="zh-audit-sql-translation",
            daemon=True,
        )
        self.sql_translation_thread.start()

    def _require_translation_session(self):
        if self.translation_session is None:
            raise ValueError("No translation task has been created yet.")
        return self.translation_session

    def _require_po_translation_session(self):
        if self.po_translation_session is None:
            raise ValueError("No PO translation task has been created yet.")
        return self.po_translation_session

    def _require_sql_translation_session(self):
        if self.sql_translation_session is None:
            raise ValueError("No SQL translation task has been created yet.")
        return self.sql_translation_session

    def _has_running_task_locked(self):
        return (
            self.translation_session is not None and self._session_status(self.translation_session) == "running"
        ) or (
            self.po_translation_session is not None and self._session_status(self.po_translation_session) == "running"
        ) or (
            self.sql_translation_session is not None and self._session_status(self.sql_translation_session) == "running"
        )

    def _session_status(self, session):
        return session.snapshot()["status"]["status"]

    def _timestamp(self):
        return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _default_translation_payload():
    return {
        "config": dict(default_translation_config()),
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


def _default_sql_translation_payload():
    return {
        "config": dict(default_sql_translation_config()),
        "status": {
            "status": "idle",
            "message": "等待校译",
            "error": "",
            "started_at": "",
            "finished_at": "",
            "output_path": "",
            "schema_source": "",
            "schema_error": "",
            "current": {"file_path": "", "primary_key_value": "", "source_text": "", "status": ""},
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


def _default_po_translation_payload():
    return {
        "config": dict(default_po_translation_config()),
        "status": {
            "status": "idle",
            "message": "等待校译",
            "error": "",
            "started_at": "",
            "finished_at": "",
            "current": {"entry_id": "", "references": [], "msgid_preview": "", "status": ""},
            "counts": {
                "total": 0,
                "processed": 0,
                "pending": 0,
                "accepted": 0,
                "updated": 0,
                "filled": 0,
                "skipped": 0,
                "unsupported": 0,
                "failed": 0,
                "rejected": 0,
                "regenerated": 0,
            },
        },
        "pending_items": [],
        "recent_items": [],
        "events": [],
    }


def _default_single_translation_result():
    return {
        "status": "idle",
        "translated_text": "",
        "error": "",
        "reason": "",
        "mode": "",
        "validation_state": "passed",
        "validation_message": "",
        "locked_terms": [],
        "warnings": [],
        "updated_at": "",
    }


def _failed_single_translation_result(error_message, mode):
    payload = _default_single_translation_result()
    payload["status"] = "failed"
    payload["error"] = str(error_message or "").strip()
    payload["mode"] = str(mode or "")
    payload["updated_at"] = datetime.now().astimezone().replace(microsecond=0).isoformat()
    return payload


def _default_single_translation_payload():
    return {
        "config": {
            "source_text": "",
        },
        "result": _default_single_translation_result(),
        "terminology": {
            "path": "",
            "count": 0,
            "error": "",
        },
    }


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
        if parsed.path == "/api/po-translation/status":
            self._send_json(200, self.server.app_state.po_translation_payload())
            return
        if parsed.path == "/api/sql-translation/status":
            self._send_json(200, self.server.app_state.sql_translation_payload())
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
            if parsed.path == "/api/findings/resolve":
                self._send_json(200, self.server.app_state.resolve_finding(payload.get("finding_id", "")))
                return
            if parsed.path == "/api/findings/reopen":
                self._send_json(200, self.server.app_state.reopen_finding(payload.get("finding_id", "")))
                return
            if parsed.path == "/api/translation/start":
                self._send_json(200, self.server.app_state.start_translation(payload))
                return
            if parsed.path == "/api/translation/stop":
                self._send_json(200, self.server.app_state.stop_translation())
                return
            if parsed.path == "/api/translation/resume":
                self._send_json(200, self.server.app_state.resume_translation())
                return
            if parsed.path == "/api/translation/accept":
                self._send_json(
                    200,
                    self.server.app_state.translation_accept(
                        payload.get("item_id", ""),
                        payload.get("candidate_text", ""),
                    ),
                )
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
            if parsed.path == "/api/po-translation/start":
                self._send_json(200, self.server.app_state.start_po_translation(payload))
                return
            if parsed.path == "/api/po-translation/stop":
                self._send_json(200, self.server.app_state.stop_po_translation())
                return
            if parsed.path == "/api/po-translation/resume":
                self._send_json(200, self.server.app_state.resume_po_translation())
                return
            if parsed.path == "/api/po-translation/accept":
                self._send_json(
                    200,
                    self.server.app_state.po_translation_accept(
                        payload.get("item_id", ""),
                        payload.get("candidate_text", ""),
                    ),
                )
                return
            if parsed.path == "/api/po-translation/regenerate":
                self._send_json(
                    200,
                    self.server.app_state.po_translation_regenerate(payload.get("item_id", ""), payload.get("prompt", "")),
                )
                return
            if parsed.path == "/api/po-translation/reject":
                self._send_json(200, self.server.app_state.po_translation_reject(payload.get("item_id", "")))
                return
            if parsed.path == "/api/sql-translation/start":
                self._send_json(200, self.server.app_state.start_sql_translation(payload))
                return
            if parsed.path == "/api/sql-translation/stop":
                self._send_json(200, self.server.app_state.stop_sql_translation())
                return
            if parsed.path == "/api/sql-translation/resume":
                self._send_json(200, self.server.app_state.resume_sql_translation())
                return
            if parsed.path == "/api/sql-translation/accept":
                self._send_json(
                    200,
                    self.server.app_state.sql_translation_accept(
                        payload.get("item_id", ""),
                        payload.get("candidate_text", ""),
                    ),
                )
                return
            if parsed.path == "/api/sql-translation/regenerate":
                self._send_json(
                    200,
                    self.server.app_state.sql_translation_regenerate(payload.get("item_id", ""), payload.get("prompt", "")),
                )
                return
            if parsed.path == "/api/sql-translation/reject":
                self._send_json(200, self.server.app_state.sql_translation_reject(payload.get("item_id", "")))
                return
            if parsed.path == "/api/single-translation/translate":
                self._send_json(200, self.server.app_state.translate_single_text(payload))
                return
            if parsed.path == "/api/single-translation/reset":
                self._send_json(200, self.server.app_state.reset_single_translation())
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


def serve_app(out_dir, host="127.0.0.1", port=8765, app_state_path=None, project_config_path=None):
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    state = AppServiceState(
        out_dir=output_dir,
        app_state_path=app_state_path,
        project_config_path=project_config_path,
    )
    server = _ThreadingHTTPServer((host, int(port)), AppRequestHandler)
    server.app_state = state
    return server
