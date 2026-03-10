import fnmatch
import subprocess
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from zh_audit.classifier import classify_rule
from zh_audit.extractor import extract_file
from zh_audit.models import (
    CATEGORY_ORDER,
    CATEGORY_UNKNOWN,
    FileRecord,
    RepoSpec,
    RunArtifacts,
    ScanSettings,
)
from zh_audit.utils import contains_han, decode_unicode_escapes, guess_language, matches_any_glob, sniff_text_file


ENCODINGS = ("utf-8", "utf-8-sig", "gb18030")


def run_scan(repos, scan_settings, run_id):
    file_records = []
    raw_findings = []

    for repo in repos:
        for path in _walk_files(repo.path):
            relative = path.relative_to(repo.path).as_posix()
            lang = guess_language(path)
            if matches_any_glob(relative, scan_settings.exclude_globs):
                matched_glob = _matched_glob(relative, scan_settings.exclude_globs)
                file_records.append(
                    FileRecord(
                        repo=repo.name,
                        path=path,
                        relative_path=relative,
                        eligible=False,
                        scanned=False,
                        skip_reason="excluded_by_policy",
                        skip_detail=_skip_detail_for_policy(relative, matched_glob),
                        lang=lang,
                        size_bytes=path.stat().st_size if path.exists() else 0,
                    )
                )
                continue
            eligible, skip_reason = sniff_text_file(path, scan_settings.max_file_size_bytes)
            if not eligible:
                file_records.append(
                    FileRecord(
                        repo=repo.name,
                        path=path,
                        relative_path=relative,
                        eligible=False,
                        scanned=False,
                        skip_reason=skip_reason,
                        skip_detail=_skip_detail_for_file(path, skip_reason, scan_settings.max_file_size_bytes),
                        lang=lang,
                        size_bytes=path.stat().st_size if path.exists() else 0,
                    )
                )
                continue

            content, encoding = _read_text(path)
            if content is None:
                file_records.append(
                    FileRecord(
                        repo=repo.name,
                        path=path,
                        relative_path=relative,
                        eligible=True,
                        scanned=False,
                        skip_reason="decode_error",
                        skip_detail="尝试 utf-8、utf-8-sig、gb18030 后仍无法按文本解码。",
                        lang=lang,
                        size_bytes=path.stat().st_size if path.exists() else 0,
                    )
                )
                continue

            if not contains_han(decode_unicode_escapes(content)):
                file_records.append(
                    FileRecord(
                        repo=repo.name,
                        path=path,
                        relative_path=relative,
                        eligible=True,
                        scanned=True,
                        encoding=encoding,
                        lang=lang,
                        size_bytes=path.stat().st_size if path.exists() else 0,
                    )
                )
                continue

            file_records.append(
                FileRecord(
                    repo=repo.name,
                    path=path,
                    relative_path=relative,
                    eligible=True,
                    scanned=True,
                    encoding=encoding,
                    lang=lang,
                    size_bytes=path.stat().st_size if path.exists() else 0,
                )
            )
            raw_findings.extend(
                extract_file(repo=repo.name, path=Path(relative), content=content, context_lines=scan_settings.context_lines)
            )

    classified = [classify_rule(finding) for finding in raw_findings]
    summary = _build_summary(repos, file_records, classified, run_id=run_id, scan_settings=scan_settings)
    return RunArtifacts(findings=classified, file_records=file_records, summary=summary)


def _walk_files(root):
    try:
        top_level_proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True,
        )
        top_level = top_level_proc.stdout.strip()
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        proc = None
        top_level = ""
    if proc is not None and Path(top_level).resolve() == root.resolve():
        for relative_path in _iter_git_paths(proc.stdout):
            path = root / relative_path
            if path.is_file():
                yield path
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue
        yield path


def _iter_git_paths(output):
    if isinstance(output, bytes):
        items = output.split(b"\0")
        return [
            item.decode("utf-8", errors="surrogateescape")
            for item in items
            if item
        ]
    return [item for item in output.split("\0") if item]


def _read_text(path):
    for encoding in ENCODINGS:
        try:
            return path.read_text(encoding=encoding), encoding
        except UnicodeDecodeError:
            continue
        except OSError:
            return None, ""
    return None, ""


def _build_summary(repos, file_records, findings, run_id, scan_settings):
    by_project = Counter()
    by_lang = Counter()
    by_category = Counter(dict((category, 0) for category in CATEGORY_ORDER))
    by_action = Counter()
    by_skip_reason = Counter()
    by_project_files = Counter()
    unknown_count = 0

    top_files = Counter()
    top_texts = Counter()
    top_high_risk = Counter()

    for record in file_records:
        if record.scanned:
            by_project_files[record.repo] += 1
        if record.skip_reason:
            by_skip_reason[record.skip_reason] += 1

    project_high_risk = Counter()
    for finding in findings:
        by_project[finding.project] += 1
        by_lang[finding.lang] += 1
        by_category[finding.category] += 1
        by_action[finding.action] += 1
        top_files["{}:{}".format(finding.project, finding.path)] += 1
        top_texts[finding.normalized_text] += 1
        if finding.category == CATEGORY_UNKNOWN:
            unknown_count += 1
        if finding.high_risk:
            top_high_risk["{}:{}:{}".format(finding.project, finding.path, finding.normalized_text)] += 1
            project_high_risk[finding.project] += 1

    eligible_files = sum(1 for record in file_records if record.eligible)
    scanned_files = sum(1 for record in file_records if record.scanned)
    skipped_files = sum(1 for record in file_records if record.skip_reason)
    excluded_files = sum(1 for record in file_records if record.skip_reason == "excluded_by_policy")
    unique_text_count = len(set(finding.normalized_text for finding in findings))

    return {
        "run_id": run_id,
        "scanned_projects": [repo.name for repo in repos],
        "eligible_files": eligible_files,
        "scanned_files": scanned_files,
        "skipped_files": skipped_files,
        "excluded_files": excluded_files,
        "skip_reasons": dict(by_skip_reason),
        "occurrence_count": len(findings),
        "unique_text_count": unique_text_count,
        "unknown_rate": round((float(unknown_count) / len(findings)) if findings else 0.0, 4),
        "by_project": dict(by_project),
        "by_project_files": dict(by_project_files),
        "by_lang": dict(by_lang),
        "by_category": dict(by_category),
        "by_action": dict(by_action),
        "top_projects": _top(by_project),
        "top_files": _top(top_files),
        "top_texts": _top(top_texts),
        "top_high_risk": _top(top_high_risk),
        "project_high_risk": dict(project_high_risk),
        "scan_policy": {
            "max_file_size_bytes": scan_settings.max_file_size_bytes,
            "context_lines": scan_settings.context_lines,
            "exclude_globs": list(scan_settings.exclude_globs),
        },
        "files": [_file_record_payload(record) for record in file_records],
    }


def _file_record_payload(record):
    payload = record.to_dict()
    payload["path"] = str(record.path)
    return payload


def _top(counter, limit=20):
    return [{"name": name, "count": count} for name, count in counter.most_common(limit)]


def _matched_glob(path_str, patterns):
    normalized = path_str.replace("\\", "/")
    for pattern in patterns:
        candidates = [pattern]
        if pattern.startswith("**/"):
            candidates.append(pattern[3:])
        for candidate in candidates:
            if fnmatch.fnmatch(normalized, candidate) or Path(normalized).match(candidate):
                return pattern
    return ""


def _skip_detail_for_policy(relative_path, matched_glob):
    normalized = relative_path.replace("\\", "/").lower()
    if any(token in normalized for token in ("static/ajax/libs/", "node_modules/", "vendor/", "webjars/")):
        base = "第三方依赖目录"
    elif "target/" in normalized:
        base = "构建产物目录"
    else:
        base = "命中路径排除规则"
    if matched_glob:
        return "{}，匹配规则 {}。".format(base, matched_glob)
    return "{}。".format(base)


def _skip_detail_for_file(path, skip_reason, max_file_size_bytes):
    if skip_reason == "binary_extension":
        suffix = path.suffix.lower() or "无扩展名"
        return "扩展名 {} 按二进制文件处理。".format(suffix)
    if skip_reason == "binary_content":
        return "文件内容包含二进制字节特征（如 NUL 字节）。"
    if skip_reason == "too_large":
        size = path.stat().st_size if path.exists() else 0
        actual_mb = size / float(1024 * 1024)
        limit_mb = max_file_size_bytes / float(1024 * 1024)
        return "文件大小 {:.1f} MB，超过扫描上限 {:.1f} MB。".format(actual_mb, limit_mb)
    if skip_reason == "read_error":
        return "读取文件内容失败。"
    if skip_reason == "stat_error":
        return "读取文件状态失败。"
    return ""
