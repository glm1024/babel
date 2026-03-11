import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from zh_audit.config import load_manifest, load_scan_settings
from zh_audit.pipeline import run_scan
from zh_audit.report import render_report
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

    scan_parser = subparsers.add_parser("scan", help="Scan repositories for Chinese text.")
    scan_parser.add_argument("--manifest", required=True, type=Path, help="Path to repos manifest.")
    scan_parser.add_argument("--out", required=False, type=Path, help="Output directory.")
    scan_parser.add_argument("--scan-policy", type=Path, help="Optional scan policy.")
    scan_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON outputs.")

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
        if args.command == "scan":
            run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
            out_dir = args.out or Path("results")
            out_dir.mkdir(parents=True, exist_ok=True)

            repos = load_manifest(args.manifest)
            scan_settings = load_scan_settings(args.scan_policy)
            progress_reporter = ScanProgressReporter()
            artifacts = run_scan(
                repos,
                scan_settings=scan_settings,
                run_id=run_id,
                progress_callback=progress_reporter,
            )

            indent = 2 if args.pretty else None
            findings_path = out_dir / "findings.json"
            summary_path = out_dir / "summary.json"
            report_path = out_dir / "report.html"

            findings_payload = [finding.to_dict() for finding in artifacts.findings]
            findings_path.write_text(
                json.dumps(findings_payload, ensure_ascii=False, indent=indent),
                encoding="utf-8",
            )
            summary_path.write_text(
                json.dumps(artifacts.summary, ensure_ascii=False, indent=indent),
                encoding="utf-8",
            )
            report_path.write_text(
                render_report(artifacts.summary, findings_payload),
                encoding="utf-8",
            )

            print(json.dumps({
                "run_id": artifacts.summary["run_id"],
                "summary": str(summary_path),
                "findings": str(findings_path),
                "report": str(report_path),
            }, ensure_ascii=False, indent=2))
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
