import argparse
import json
import sys
import threading
import webbrowser
from pathlib import Path

from zh_audit.annotations import resolve_annotation_path
from zh_audit.app_server import serve_app
from zh_audit.config import DEFAULT_APP_CONFIG_NAME, load_scan_settings
from zh_audit.validation import validate_report


class ScanProgressReporter(object):
    def __init__(self, stream=None, width=24):
        self.stream = stream or sys.stderr
        self.width = width
        self.enabled = hasattr(self.stream, "isatty") and self.stream.isatty()
        self.last_length = 0

    def __call__(self, stage, **payload):
        if not self.enabled:
            return
        if stage == "start":
            total = int(payload.get("total", 0))
            if total == 0:
                self._write("扫描进度 [{}] 0/0 100.0% 无可扫描文件".format("-" * self.width))
                self.stream.write("\n")
                self.stream.flush()
            return
        if stage == "file":
            line = format_scan_progress_line(
                processed=int(payload.get("processed", 0)),
                total=int(payload.get("total", 0)),
                repo=str(payload.get("repo", "")),
                relative_path=str(payload.get("relative_path", "")),
                width=self.width,
            )
            self._write(line)
            return
        if stage == "done":
            processed = int(payload.get("processed", 0))
            total = int(payload.get("total", 0))
            if total == 0:
                return
            line = format_scan_progress_line(
                processed=processed,
                total=total,
                repo="",
                relative_path="扫描完成",
                width=self.width,
            )
            self._write(line)
            self.stream.write("\n")
            self.stream.flush()

    def _write(self, line):
        padding = ""
        if self.last_length > len(line):
            padding = " " * (self.last_length - len(line))
        self.stream.write("\r{}{}".format(line, padding))
        self.stream.flush()
        self.last_length = len(line)


def format_scan_progress_line(processed, total, repo, relative_path, width=24):
    safe_total = max(int(total), 1)
    safe_processed = min(max(int(processed), 0), safe_total)
    filled = int(round((float(safe_processed) / safe_total) * width))
    filled = min(max(filled, 0), width)
    bar = "#" * filled + "-" * (width - filled)
    percent = (float(safe_processed) / safe_total) * 100.0
    tail = "{} {}".format(repo, relative_path).strip()
    tail = _truncate_progress_text(tail, 56)
    return "扫描进度 [{}] {}/{} {:>5.1f}% {}".format(bar, safe_processed, safe_total, percent, tail)


def _truncate_progress_text(text, limit):
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return text[: limit - 3] + "..."


def build_parser():
    parser = argparse.ArgumentParser(prog="zh-audit")
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Serve the local audit application.")
    serve_parser.add_argument("--annotations", type=Path, help="Optional annotations file path.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    serve_parser.add_argument("--port", type=int, default=8765, help="Port to bind.")
    serve_parser.add_argument("--no-browser", action="store_true", help="Do not open the default browser automatically.")
    serve_parser.add_argument("--config", type=Path, help="Optional path to zh-audit.config.json.")

    validate_parser = subparsers.add_parser("validate", help="Validate a generated report against a repository.")
    validate_parser.add_argument("--repo", required=True, type=Path, help="Path to the repository root.")
    validate_parser.add_argument("--summary", required=True, type=Path, help="Path to summary.json.")
    validate_parser.add_argument("--findings", required=True, type=Path, help="Path to findings.json.")
    validate_parser.add_argument("--out", type=Path, help="Directory for validation outputs. Defaults to the summary directory.")
    validate_parser.add_argument("--scan-policy", type=Path, help="Optional scan policy override.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.error("A command is required.")

    try:
        if args.command == "serve":
            out_dir = Path("results").resolve()
            project_config_path = args.config.resolve() if args.config else (Path.cwd() / DEFAULT_APP_CONFIG_NAME)
            server = serve_app(
                out_dir=out_dir,
                host=args.host,
                port=args.port,
                annotations_path=args.annotations.resolve() if args.annotations else None,
                project_config_path=project_config_path,
            )
            address = server.server_address
            url = "http://{}:{}/".format(address[0], address[1])
            print(json.dumps({
                "mode": "serve",
                "url": url,
                "annotations": str(resolve_annotation_path(out_dir, args.annotations.resolve() if args.annotations else None)),
            }, ensure_ascii=False, indent=2))
            if not args.no_browser:
                _open_browser_later(url)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
            return 0
        if args.command == "validate":
            out_dir = args.out or args.summary.parent
            artifacts = validate_report(
                repo_root=args.repo.resolve(),
                summary_path=args.summary.resolve(),
                findings_path=args.findings.resolve(),
                out_dir=out_dir.resolve(),
                scan_settings=load_scan_settings(args.scan_policy) if args.scan_policy else None,
            )
            print(json.dumps(artifacts, ensure_ascii=False, indent=2))
            return 0
    except Exception as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1

    parser.error("Unsupported command: {}".format(args.command))
    return 2


def _open_browser_later(url):
    timer = threading.Timer(0.2, _open_browser, args=(url,))
    timer.daemon = True
    timer.start()
    return timer


def _open_browser(url):
    try:
        webbrowser.open(url, new=2)
        return True
    except Exception:
        return False
