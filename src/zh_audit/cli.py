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
            out_dir = args.out or Path("results") / run_id
            out_dir.mkdir(parents=True, exist_ok=True)

            repos = load_manifest(args.manifest)
            scan_settings = load_scan_settings(args.scan_policy)
            artifacts = run_scan(
                repos,
                scan_settings=scan_settings,
                run_id=run_id,
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
