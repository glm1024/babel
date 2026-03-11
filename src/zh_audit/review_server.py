import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import urlparse

from zh_audit.annotations import (
    apply_annotation_store,
    load_annotation_store,
    remove_annotation,
    resolve_annotation_path,
    upsert_annotation,
    write_annotation_store,
)
from zh_audit.pipeline import refresh_summary
from zh_audit.report import render_report


class ReviewState(object):
    def __init__(self, out_dir, summary_path, findings_path, annotations_path):
        self.out_dir = Path(out_dir)
        self.summary_path = Path(summary_path)
        self.findings_path = Path(findings_path)
        self.report_path = self.out_dir / "report.html"
        self.annotations_path = Path(annotations_path)
        self.lock = threading.RLock()
        self.summary = {}
        self.findings = []
        self.annotation_store = {}
        self.annotation_stats = {}
        self.load()

    def load(self):
        self.summary = json.loads(self.summary_path.read_text(encoding="utf-8"))
        self.findings = json.loads(self.findings_path.read_text(encoding="utf-8"))
        self.annotation_store = load_annotation_store(self.annotations_path)
        self.annotation_stats = apply_annotation_store(self.findings, self.annotation_store)
        self.summary = refresh_summary(self.summary, self.findings, annotation_stats=self.annotation_stats)
        if self.annotation_store.get("items") or any(item.get("annotated") for item in self.findings):
            self._persist_static_artifacts()

    def render_review_report(self):
        return render_report(
            self.summary,
            self.findings,
            client_config={
                "mode": "review",
                "annotation_api_path": "/api/annotations",
                "annotation_remove_api_path": "/api/annotations/remove",
                "readonly_message": "",
                "annotation_path": str(self.annotations_path),
            },
        )

    def annotate(self, finding_id, reason):
        with self.lock:
            finding = self._find_by_id(finding_id)
            if finding is None:
                raise KeyError("Unknown finding id: {}".format(finding_id))
            if finding.get("action") != "fix" and not finding.get("annotated"):
                raise ValueError("Only fix findings can be annotated as no-change.")
            upsert_annotation(self.annotation_store, finding, reason)
            self._reapply_and_persist()
            return self._response_payload(finding_id)

    def remove_annotation(self, finding_id):
        with self.lock:
            finding = self._find_by_id(finding_id)
            if finding is None:
                raise KeyError("Unknown finding id: {}".format(finding_id))
            if not finding.get("annotated"):
                raise ValueError("Finding is not annotated.")
            remove_annotation(self.annotation_store, finding)
            self._reapply_and_persist()
            return self._response_payload(finding_id)

    def _reapply_and_persist(self):
        self.annotation_stats = apply_annotation_store(self.findings, self.annotation_store)
        self.summary = refresh_summary(self.summary, self.findings, annotation_stats=self.annotation_stats)
        self._persist_static_artifacts()

    def _persist_static_artifacts(self):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        write_annotation_store(self.annotations_path, self.annotation_store)
        self.findings_path.write_text(
            json.dumps(self.findings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.summary_path.write_text(
            json.dumps(self.summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.report_path.write_text(
            render_report(
                self.summary,
                self.findings,
                client_config={
                    "mode": "static",
                    "annotation_api_path": "",
                    "annotation_remove_api_path": "",
                    "readonly_message": "当前报告为只读模式，请使用 zh-audit review 打开可编辑版本。",
                    "annotation_path": str(self.annotations_path),
                },
            ),
            encoding="utf-8",
        )

    def _response_payload(self, finding_id):
        finding = self._find_by_id(finding_id)
        return {
            "summary": self.summary,
            "finding": dict(finding) if finding is not None else None,
        }

    def _find_by_id(self, finding_id):
        for item in self.findings:
            if item.get("id") == finding_id:
                return item
        return None


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class ReviewRequestHandler(BaseHTTPRequestHandler):
    server_version = "ZhAuditReview/1.0"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            content = self.server.review_state.render_review_report().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if parsed.path == "/api/health":
            self._send_json(200, {"ok": True})
            return
        self._send_json(404, {"error": "not_found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/annotations":
            payload = self._read_json_body()
            try:
                response = self.server.review_state.annotate(
                    payload.get("finding_id", ""),
                    payload.get("reason", ""),
                )
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, response)
            return
        if parsed.path == "/api/annotations/remove":
            payload = self._read_json_body()
            try:
                response = self.server.review_state.remove_annotation(payload.get("finding_id", ""))
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, response)
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

    def _send_json(self, status, payload):
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def serve_review(out_dir, host="127.0.0.1", port=8765, annotations_path=None):
    output_dir = Path(out_dir)
    summary_path = output_dir / "summary.json"
    findings_path = output_dir / "findings.json"
    if not summary_path.exists() or not findings_path.exists():
        raise ValueError("Missing findings.json or summary.json under {}.".format(output_dir))

    state = ReviewState(
        out_dir=output_dir,
        summary_path=summary_path,
        findings_path=findings_path,
        annotations_path=resolve_annotation_path(output_dir, annotations_path),
    )

    server = _ThreadingHTTPServer((host, int(port)), ReviewRequestHandler)
    server.review_state = state
    return server
