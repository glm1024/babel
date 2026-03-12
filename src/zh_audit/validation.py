import csv
import json
import random
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Match, Optional, Set, Tuple

from zh_audit.extractor import _java_task_description_ranges
from zh_audit.models import (
    CATEGORY_ANNOTATED_NO_CHANGE,
    CATEGORY_COMMENT,
    CATEGORY_CONDITION_EXPRESSION_LITERAL,
    CATEGORY_CONFIG_ITEM,
    CATEGORY_DATABASE_SCRIPT,
    CATEGORY_ERROR_VALIDATION_MESSAGE,
    CATEGORY_GENERIC_DOCUMENTATION,
    CATEGORY_I18N_FILE,
    CATEGORY_LOG_AUDIT_DEBUG,
    CATEGORY_NAMED_FILE,
    CATEGORY_PROTOCOL_OR_PERSISTED_LITERAL,
    CATEGORY_SHELL_SCRIPT,
    CATEGORY_SWAGGER_DOCUMENTATION,
    CATEGORY_TASK_DESCRIPTION,
    CATEGORY_TEST_SAMPLE_FIXTURE,
    CATEGORY_UNKNOWN,
    CATEGORY_USER_VISIBLE_COPY,
    CATEGORY_ORDER as MODEL_CATEGORY_ORDER,
    ScanSettings,
)
from zh_audit.utils import (
    guess_language,
    find_sql_comment_start,
    is_i18n_messages_file,
    is_named_keep_file,
    looks_like_assert_api_literal,
    looks_like_condition_expression_literal,
    matches_any_glob,
)


HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
UNICODE_ESCAPE_RE = re.compile(r"(?:\\u[0-9a-fA-F]{4})+")
TRACKED_ENCODINGS = ("utf-8", "utf-8-sig", "gb18030")
SENSITIVE_EXTENSIONS = {".html", ".xml", ".vm", ".js", ".css"}
ACCEPTANCE_EXTENSIONS = {".html", ".xml", ".vm"}
HIGH_RISK_CATEGORIES = {
    CATEGORY_ERROR_VALIDATION_MESSAGE,
    CATEGORY_PROTOCOL_OR_PERSISTED_LITERAL,
    CATEGORY_UNKNOWN,
}
SAMPLED_CATEGORIES = {
    CATEGORY_USER_VISIBLE_COPY,
    CATEGORY_ANNOTATED_NO_CHANGE,
    CATEGORY_COMMENT,
    CATEGORY_SWAGGER_DOCUMENTATION,
    CATEGORY_GENERIC_DOCUMENTATION,
    CATEGORY_DATABASE_SCRIPT,
    CATEGORY_SHELL_SCRIPT,
    CATEGORY_NAMED_FILE,
    CATEGORY_I18N_FILE,
    CATEGORY_CONDITION_EXPRESSION_LITERAL,
    CATEGORY_TASK_DESCRIPTION,
    CATEGORY_LOG_AUDIT_DEBUG,
    CATEGORY_TEST_SAMPLE_FIXTURE,
    CATEGORY_CONFIG_ITEM,
}
CATEGORY_ORDER = list(MODEL_CATEGORY_ORDER)
SLICE_ORDER = ["first_party", "third_party_lib", "demo", "sql_doc"]
LOG_CONTEXT_RE = re.compile(r"(?<![A-Za-z0-9_])(?:logger|log|logging|console)\s*(?:\.|\()")
LOG_ANNOTATION_RE = re.compile(r"@\s*log\s*\(")
PROTOCOL_CONTEXT_RES = [
    re.compile(r"\b(?:private|public)\s+static\s+final\b"),
    re.compile(r"\benum\b"),
    re.compile(r"\bcase\b"),
    re.compile(r"\bdicttype\b"),
    re.compile(r"\bdict_type\b"),
    re.compile(r"\bdictdata\b"),
    re.compile(r"\bstatus\s*[:=]"),
    re.compile(r"\btype\s*[:=]"),
    re.compile(r"\bstate\s*[:=]"),
    re.compile(r"\bkind\s*[:=]"),
    re.compile(r"\bbusinesstype\b"),
    re.compile(r"\boperator_type\b"),
    re.compile(r"\brequest_method\b"),
]


class BaselineFile(object):
    __slots__ = ("path", "lines", "han_lines", "slice_name", "first_party_focus")

    def __init__(self, path, lines, han_lines, slice_name, first_party_focus):
        self.path = path
        self.lines = lines
        self.han_lines = han_lines
        self.slice_name = slice_name
        self.first_party_focus = first_party_focus


def validate_report(
    repo_root: Path,
    summary_path: Path,
    findings_path: Path,
    out_dir: Path,
    scan_settings: Optional[ScanSettings] = None,
) -> Dict[str, Any]:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    effective_scan_settings = scan_settings or _scan_settings_from_summary(summary)
    tracked_files = _tracked_files(repo_root)
    in_scope_tracked_files = [
        path
        for path in tracked_files
        if not matches_any_glob(path, effective_scan_settings.exclude_globs)
    ]
    baseline = _build_baseline(repo_root, in_scope_tracked_files)
    coverage_rows, coverage_metrics = _build_coverage_diff(
        baseline,
        findings,
        exclude_globs=effective_scan_settings.exclude_globs,
        excluded_tracked_count=len(tracked_files) - len(in_scope_tracked_files),
    )
    review_rows, review_metrics = _build_classification_review(repo_root, baseline, findings)
    verdict, checks = _determine_verdict(summary, tracked_files, coverage_metrics, review_metrics)

    out_dir.mkdir(parents=True, exist_ok=True)
    coverage_path = out_dir / "coverage_diff.csv"
    review_path = out_dir / "classification_review.csv"
    summary_md_path = out_dir / "validation_summary.md"

    _write_csv(coverage_path, coverage_rows)
    _write_csv(review_path, review_rows)
    summary_md_path.write_text(
        _render_validation_summary(
            repo_root=repo_root,
            summary=summary,
            tracked_files=tracked_files,
            scan_settings=effective_scan_settings,
            baseline=baseline,
            coverage_metrics=coverage_metrics,
            review_metrics=review_metrics,
            verdict=verdict,
            checks=checks,
            coverage_rows=coverage_rows,
            review_rows=review_rows,
        ),
        encoding="utf-8",
    )

    return {
        "verdict": verdict,
        "validation_summary": str(summary_md_path),
        "coverage_diff": str(coverage_path),
        "classification_review": str(review_path),
    }


def _tracked_files(repo_root: Path) -> List[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return _iter_git_paths(proc.stdout)


def _iter_git_paths(output):
    if isinstance(output, bytes):
        items = output.split(b"\0")
        return [
            item.decode("utf-8", errors="surrogateescape")
            for item in items
            if item
        ]
    return [item for item in output.split("\0") if item]


def _scan_settings_from_summary(summary: Dict[str, Any]) -> ScanSettings:
    raw = summary.get("scan_policy")
    if not isinstance(raw, dict):
        return ScanSettings()
    exclude_globs = raw.get("exclude_globs")
    if not isinstance(exclude_globs, list) or not all(isinstance(item, str) for item in exclude_globs):
        exclude_globs = ScanSettings().exclude_globs
    return ScanSettings(
        max_file_size_bytes=int(raw.get("max_file_size_bytes", 5 * 1024 * 1024)),
        context_lines=int(raw.get("context_lines", 1)),
        exclude_globs=list(exclude_globs),
    )


def _build_baseline(repo_root: Path, tracked_files: List[str]) -> Dict[str, BaselineFile]:
    baseline: Dict[str, BaselineFile] = {}
    for relative_path in tracked_files:
        path = repo_root / relative_path
        content = _read_text(path)
        if content is None:
            continue
        lines = content.splitlines()
        han_lines: Dict[int, str] = {}
        for index, line in enumerate(lines, start=1):
            if _contains_han(line):
                han_lines[index] = line.rstrip("\n")
        if not han_lines:
            continue
        baseline[relative_path] = BaselineFile(
            path=relative_path,
            lines=lines,
            han_lines=han_lines,
            slice_name=_slice_for_path(relative_path),
            first_party_focus=_is_first_party_focus(relative_path),
        )
    return baseline


def _read_text(path: Path) -> Optional[str]:
    for encoding in TRACKED_ENCODINGS:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except OSError:
            return None
    return None


def _contains_han(text: str) -> bool:
    decoded = UNICODE_ESCAPE_RE.sub(_decode_escape_match, text)
    return bool(HAN_RE.search(decoded))


def _decode_escape_match(match: Match[str]) -> str:
    raw = match.group(0)
    try:
        return raw.encode("ascii").decode("unicode_escape")
    except UnicodeDecodeError:
        return raw


def _slice_for_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    if "static/ajax/libs/" in normalized:
        return "third_party_lib"
    if "/demo/" in normalized or normalized.startswith("ruoyi-admin/src/main/resources/templates/demo/"):
        return "demo"
    if (
        normalized.startswith("sql/")
        or normalized.startswith("doc/")
        or normalized == "README.md"
        or normalized.endswith(".pdm")
    ):
        return "sql_doc"
    return "first_party"


def _is_first_party_focus(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if _slice_for_path(normalized) != "first_party":
        return False
    if normalized.startswith("bin/") or normalized in {"ry.bat", "ry.sh", "pom.xml", "LICENSE"}:
        return False
    if "/src/main/" in normalized or normalized.startswith("ruoyi-admin/src/main/resources/templates/"):
        return True
    return normalized.startswith("ruoyi-")


def _build_coverage_diff(
    baseline: Dict[str, BaselineFile],
    findings: List[Dict[str, Any]],
    exclude_globs: List[str],
    excluded_tracked_count: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    findings_by_path: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    findings_by_path_line: Set[Tuple[str, int]] = set()
    for finding in findings:
        findings_by_path[finding["path"]].append(finding)
        findings_by_path_line.add((finding["path"], int(finding["line"])))

    missing_files = 0
    missing_lines_total = 0
    missing_first_party_sensitive_lines = 0
    missing_first_party_acceptance_lines = 0
    han_tracked_files = len(baseline)
    han_first_party_files = 0
    han_sensitive_lines_total = 0
    han_sensitive_first_party_lines = 0
    han_acceptance_first_party_lines = 0
    excluded_path_findings = 0

    for path, entry in baseline.items():
        if entry.first_party_focus:
            han_first_party_files += 1
        if path not in findings_by_path:
            missing_files += 1
            rows.append(
                {
                    "scope": "full_repo",
                    "kind": "missing_file",
                    "slice": entry.slice_name,
                    "path": path,
                    "line": "",
                    "text": "",
                    "reason": "tracked file contains Chinese text but has no findings",
                    "reported_category": "",
                    "reported_action": "",
                }
            )
        for line_no, line_text in entry.han_lines.items():
            ext = Path(path).suffix.lower()
            if ext in SENSITIVE_EXTENSIONS:
                han_sensitive_lines_total += 1
                if entry.first_party_focus:
                    han_sensitive_first_party_lines += 1
                    if ext in ACCEPTANCE_EXTENSIONS:
                        han_acceptance_first_party_lines += 1
                if (path, line_no) not in findings_by_path_line:
                    missing_lines_total += 1
                    if entry.first_party_focus:
                        missing_first_party_sensitive_lines += 1
                        if ext in ACCEPTANCE_EXTENSIONS:
                            missing_first_party_acceptance_lines += 1
                    rows.append(
                        {
                            "scope": "first_party_focus" if entry.first_party_focus else "full_repo",
                            "kind": "missing_line",
                            "slice": entry.slice_name,
                            "path": path,
                            "line": line_no,
                            "text": _compact_text(line_text),
                            "reason": "sensitive line contains Chinese text but line not present in findings",
                            "reported_category": "",
                            "reported_action": "",
                        }
                    )

    baseline_lines = {(path, line_no) for path, entry in baseline.items() for line_no in entry.han_lines}
    extra_findings = 0
    for finding in findings:
        if matches_any_glob(finding["path"], exclude_globs):
            excluded_path_findings += 1
            rows.append(
                {
                    "scope": "full_repo",
                    "kind": "policy_violation",
                    "slice": _slice_for_path(finding["path"]),
                    "path": finding["path"],
                    "line": finding["line"],
                    "text": _compact_text(finding.get("normalized_text") or finding.get("text", "")),
                    "reason": "finding exists under excluded policy path",
                    "reported_category": finding["category"],
                    "reported_action": finding["action"],
                }
            )
            continue
        key = (finding["path"], int(finding["line"]))
        if key in baseline_lines:
            continue
        extra_findings += 1
        rows.append(
            {
                "scope": "full_repo",
                "kind": "extra_finding",
                "slice": _slice_for_path(finding["path"]),
                "path": finding["path"],
                "line": finding["line"],
                "text": _compact_text(finding.get("normalized_text") or finding.get("text", "")),
                "reason": "finding line not matched by independent baseline",
                "reported_category": finding["category"],
                "reported_action": finding["action"],
            }
        )

    metrics = {
        "tracked_han_files": han_tracked_files,
        "tracked_first_party_han_files": han_first_party_files,
        "missing_files": missing_files,
        "missing_sensitive_lines": missing_lines_total,
        "missing_first_party_sensitive_lines": missing_first_party_sensitive_lines,
        "missing_first_party_acceptance_lines": missing_first_party_acceptance_lines,
        "sensitive_lines_total": han_sensitive_lines_total,
        "first_party_sensitive_lines_total": han_sensitive_first_party_lines,
        "first_party_acceptance_lines_total": han_acceptance_first_party_lines,
        "extra_findings": extra_findings,
        "excluded_tracked_files": excluded_tracked_count,
        "excluded_path_findings": excluded_path_findings,
    }
    return rows, metrics


def _build_classification_review(
    repo_root: Path,
    baseline: Dict[str, BaselineFile],
    findings: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    selected = _select_review_findings(findings)
    rows: List[Dict[str, Any]] = []

    stats = {
        "full_repo": _blank_stats(),
        "first_party_focus": _blank_stats(),
        "high_risk": _blank_stats(),
    }

    for finding in selected:
        baseline_entry = baseline.get(finding["path"])
        source_content = _read_text(repo_root / finding["path"]) or ""
        source_line = _source_line(repo_root, finding["path"], int(finding["line"]))
        source_context = _source_context(repo_root, finding["path"], int(finding["line"]))
        expected_category, governance_in_scope, reason = _expected_category(
            finding=finding,
            source_line=source_line,
            source_context=source_context,
            source_content=source_content,
            slice_name=baseline_entry.slice_name if baseline_entry else _slice_for_path(finding["path"]),
        )
        status = "match" if finding["category"] == expected_category else "mismatch"
        row = {
            "review_scope": "full" if finding["category"] in HIGH_RISK_CATEGORIES else "sample",
            "slice": baseline_entry.slice_name if baseline_entry else _slice_for_path(finding["path"]),
            "path": finding["path"],
            "line": finding["line"],
            "text": _compact_text(finding.get("normalized_text") or finding.get("text", "")),
            "reported_category": finding["category"],
            "expected_category": expected_category,
            "status": status,
            "governance_in_scope": "yes" if governance_in_scope else "no",
            "reason": reason,
        }
        rows.append(row)
        _record_review_stat(stats["full_repo"], row)
        if baseline_entry and baseline_entry.first_party_focus:
            _record_review_stat(stats["first_party_focus"], row)
        if finding["category"] in HIGH_RISK_CATEGORIES:
            _record_review_stat(stats["high_risk"], row)

    metrics = {
        "full_repo": _finalize_stats(stats["full_repo"]),
        "first_party_focus": _finalize_stats(stats["first_party_focus"]),
        "high_risk": _finalize_stats(stats["high_risk"]),
    }
    return rows, metrics


def _blank_stats() -> Dict[str, Any]:
    return {
        "reviewed": 0,
        "matched": 0,
        "by_category": {category: {"reviewed": 0, "matched": 0} for category in CATEGORY_ORDER},
    }


def _record_review_stat(target: Dict[str, Any], row: Dict[str, Any]) -> None:
    target["reviewed"] += 1
    if row["status"] == "match":
        target["matched"] += 1
    category_bucket = target["by_category"].setdefault(
        row["reported_category"],
        {"reviewed": 0, "matched": 0},
    )
    category_bucket["reviewed"] += 1
    if row["status"] == "match":
        category_bucket["matched"] += 1


def _finalize_stats(stats: Dict[str, Any]) -> Dict[str, Any]:
    reviewed = stats["reviewed"]
    matched = stats["matched"]
    precision = (matched / reviewed) if reviewed else 1.0
    by_category = {}
    for category, bucket in stats["by_category"].items():
        if bucket["reviewed"] == 0:
            continue
        by_category[category] = {
            "reviewed": bucket["reviewed"],
            "matched": bucket["matched"],
            "precision": (bucket["matched"] / bucket["reviewed"]) if bucket["reviewed"] else 1.0,
        }
    return {
        "reviewed": reviewed,
        "matched": matched,
        "precision": precision,
        "by_category": by_category,
    }


def _select_review_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for finding in findings:
        grouped[finding["category"]].append(finding)

    for category in HIGH_RISK_CATEGORIES:
        selected.extend(grouped.get(category, []))

    rng = random.Random(0)
    for category in SAMPLED_CATEGORIES:
        items = grouped.get(category, [])
        by_slice: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for item in items:
            by_slice[_slice_for_path(item["path"])].append(item)
        chosen: List[Dict[str, Any]] = []
        active_groups = [slice_name for slice_name in SLICE_ORDER if by_slice.get(slice_name)]
        if not active_groups:
            continue
        quota = 40
        base = quota // len(active_groups)
        remainder = quota % len(active_groups)
        for index, slice_name in enumerate(active_groups):
            pool = list(by_slice[slice_name])
            rng.shuffle(pool)
            take = min(len(pool), base + (1 if index < remainder else 0))
            chosen.extend(pool[:take])
            by_slice[slice_name] = pool[take:]
        if len(chosen) < min(quota, len(items)):
            leftovers: List[Dict[str, Any]] = []
            for slice_name in SLICE_ORDER:
                leftovers.extend(by_slice.get(slice_name, []))
            rng.shuffle(leftovers)
            chosen.extend(leftovers[: min(quota, len(items)) - len(chosen)])
        selected.extend(chosen[: min(quota, len(items))])
    return selected


def _source_line(repo_root: Path, relative_path: str, line_no: int) -> str:
    content = _read_text(repo_root / relative_path)
    if content is None:
        return ""
    lines = content.splitlines()
    if 1 <= line_no <= len(lines):
        return lines[line_no - 1]
    return ""


def _source_context(repo_root: Path, relative_path: str, line_no: int) -> str:
    content = _read_text(repo_root / relative_path)
    if content is None:
        return ""
    lines = content.splitlines()
    if not lines:
        return ""
    start = max(1, line_no - 1)
    end = min(len(lines), line_no + 1)
    return "\n".join(lines[index - 1] for index in range(start, end + 1))


def _expected_category(
    finding: Dict[str, Any],
    source_line: str,
    source_context: str,
    source_content: str,
    slice_name: str,
) -> Tuple[str, bool, str]:
    path = finding["path"]
    ext = Path(path).suffix.lower()
    text = str(finding.get("normalized_text") or finding.get("text", ""))
    source_lower = source_line.lower()
    text_lower = text.lower()
    governance_in_scope = slice_name == "first_party"
    language = guess_language(Path(path))

    if finding.get("annotated") or finding.get("category") == CATEGORY_ANNOTATED_NO_CHANGE:
        return CATEGORY_ANNOTATED_NO_CHANGE, False, "当前命中来自历史人工保留记录。"
    if is_named_keep_file(path):
        return CATEGORY_NAMED_FILE, False, "排除文件中的中文统一归为排除文件。"
    if is_i18n_messages_file(path):
        return CATEGORY_I18N_FILE, False, "国际化文件中的中文统一归为国际化文件。"
    if ext == ".sql":
        return CATEGORY_DATABASE_SCRIPT, False, "SQL 文件中的中文统一归为数据库脚本。"
    if ext in {".bat", ".sh", ".bash", ".zsh"}:
        return CATEGORY_SHELL_SCRIPT, False, "Shell 脚本中的中文统一归为 Shell 脚本。"
    if slice_name == "demo":
        return CATEGORY_TEST_SAMPLE_FIXTURE, False, "示例或演示路径应视为样例内容。"
    if (
        path.startswith("doc/")
        or path.startswith("docs/")
        or path.startswith("wiki/")
        or "readme" in path.lower()
        or ext == ".pdm"
        or path.endswith("ruoyi.html")
    ):
        return CATEGORY_GENERIC_DOCUMENTATION, False, "文档资产中的中文应归为普通文档。"
    if finding.get("surface_kind") == "comment" or _looks_like_comment(source_line, language):
        return CATEGORY_COMMENT, governance_in_scope, "注释语法或注释上下文。"
    if "swagger_annotation" in finding.get("candidate_roles", []):
        return CATEGORY_SWAGGER_DOCUMENTATION, governance_in_scope, "Swagger/OpenAPI 注解中的中文应视为 Swagger 文档。"
    if _finding_in_task_description_annotation(finding, source_content):
        return CATEGORY_TASK_DESCRIPTION, False, "当前命中位于任务描述注解中。"
    if slice_name == "third_party_lib":
        if finding.get("surface_kind") == "comment":
            return CATEGORY_COMMENT, False, "第三方库中的注释文本。"
        return CATEGORY_USER_VISIBLE_COPY, False, "第三方前端库中的中文通常属于界面展示文案。"
    if _looks_like_log_context(source_lower):
        return CATEGORY_LOG_AUDIT_DEBUG, governance_in_scope, "日志或控制台输出上下文。"
    if looks_like_assert_api_literal(source_line, source_line, extra_context=source_context):
        return CATEGORY_CONDITION_EXPRESSION_LITERAL, False, "当前命中用于逻辑判断或字符串处理。"
    if any(token in source_lower for token in ("ajaxresult.warn(", "ajaxresult.error(", "throw ", " alertwarning(", " alerterror(", "$.modal.alert", "return error(", "return fail(", "return warn(")):
        return CATEGORY_ERROR_VALIDATION_MESSAGE, governance_in_scope, "异常、告警或失败返回上下文。"
    if looks_like_condition_expression_literal(source_line, source_line, language=language, extra_context=source_context):
        return CATEGORY_CONDITION_EXPRESSION_LITERAL, False, "当前命中用于逻辑判断或字符串处理。"
    if any(token in text for token in ("失败", "异常", "错误", "不能为空", "不允许", "不存在", "已存在", "非法")) and "static/ajax/libs/" not in path:
        return CATEGORY_ERROR_VALIDATION_MESSAGE, governance_in_scope, "文本语义更接近错误或校验提示。"
    if ext in {".yaml", ".yml", ".properties", ".json", ".toml"}:
        return CATEGORY_CONFIG_ITEM, governance_in_scope, "配置文件中的中文更接近配置项。"
    if ext in {".html", ".vm", ".js", ".css"} or "<" in source_line or "</" in source_line:
        return CATEGORY_USER_VISIBLE_COPY, governance_in_scope, "模板或前端资源中的中文通常面向用户可见。"
    if _looks_like_protocol_literal(source_lower, text_lower):
        return CATEGORY_PROTOCOL_OR_PERSISTED_LITERAL, governance_in_scope, "文本更接近协议、状态或持久化字面量。"
    if ext == ".xml":
        return CATEGORY_CONFIG_ITEM, governance_in_scope, "XML 非注释中文默认视为配置项。"
    if finding.get("surface_kind") == "string_literal":
        return CATEGORY_USER_VISIBLE_COPY, governance_in_scope, "默认字符串字面量更接近用户可见文案。"
    return CATEGORY_UNKNOWN, governance_in_scope, "独立规则无法稳定判断，建议归入 UNKNOWN。"


def _looks_like_comment(source_line: str, language: str) -> bool:
    stripped = source_line.strip()
    return stripped.startswith(("//", "#", "/*", "*", "--", "<!--", "rem ")) or find_sql_comment_start(source_line, language) >= 0


def _looks_like_log_context(source_lower: str) -> bool:
    return bool(
        LOG_CONTEXT_RE.search(source_lower)
        or LOG_ANNOTATION_RE.search(source_lower)
        or "system.out." in source_lower
        or "system.err." in source_lower
        or "printstacktrace(" in source_lower
    )


def _finding_in_task_description_annotation(finding: Dict[str, Any], source_content: str) -> bool:
    if "task_description_annotation" in finding.get("candidate_roles", []):
        return True
    if not source_content or guess_language(Path(finding["path"])) != "java":
        return False
    line_ranges = _java_task_description_ranges(source_content).get(int(finding.get("line", 0)), [])
    if not line_ranges:
        return False
    column = finding.get("column")
    if not isinstance(column, int):
        return True
    start = max(0, column - 1)
    text = str(finding.get("text") or finding.get("normalized_text") or "")
    end = start + len(text)
    return any(max(range_start, start) < min(range_end, end) for range_start, range_end in line_ranges)


def _looks_like_protocol_literal(source_lower: str, text_lower: str) -> bool:
    hint_tokens = ("状态", "类型", "字典", "枚举", "category", "status", "type", "code", "state", "kind", "dict_")
    if any(token in text_lower for token in hint_tokens):
        return True
    if "insert into" in source_lower and any(token in text_lower for token in hint_tokens):
        return True
    if any(pattern.search(source_lower) for pattern in PROTOCOL_CONTEXT_RES):
        short_text = len(text_lower) <= 24
        return short_text
    return False


def _determine_verdict(
    summary: Dict[str, Any],
    tracked_files: List[str],
    coverage_metrics: Dict[str, Any],
    review_metrics: Dict[str, Any],
) -> Tuple[str, Dict[str, bool]]:
    tracked_count_ok = len(tracked_files) == (summary.get("eligible_files", 0) + summary.get("skipped_files", 0))
    first_party_sensitive_ok = coverage_metrics["missing_first_party_acceptance_lines"] == 0
    excluded_policy_ok = coverage_metrics["excluded_path_findings"] == 0
    high_risk_ok = all(
        bucket["precision"] >= 0.95
        for category, bucket in review_metrics["high_risk"]["by_category"].items()
        if category in HIGH_RISK_CATEGORIES
    )
    first_party_precision_ok = review_metrics["first_party_focus"]["precision"] >= 0.90

    checks = {
        "tracked_count_ok": tracked_count_ok,
        "first_party_sensitive_ok": first_party_sensitive_ok,
        "excluded_policy_ok": excluded_policy_ok,
        "high_risk_ok": high_risk_ok,
        "first_party_precision_ok": first_party_precision_ok,
    }
    verdict = "PASS" if all(checks.values()) else "FAIL"
    return verdict, checks


def _render_validation_summary(
    repo_root: Path,
    summary: Dict[str, Any],
    tracked_files: List[str],
    scan_settings: ScanSettings,
    baseline: Dict[str, BaselineFile],
    coverage_metrics: Dict[str, Any],
    review_metrics: Dict[str, Any],
    verdict: str,
    checks: Dict[str, bool],
    coverage_rows: List[Dict[str, Any]],
    review_rows: List[Dict[str, Any]],
) -> str:
    ignored_targets = sorted(str(path.relative_to(repo_root)) for path in repo_root.rglob("target") if path.is_dir())
    confirmed_coverage = _prioritized_coverage_examples(coverage_rows)
    confirmed_classification = _prioritized_classification_examples(review_rows)
    high_risk_details = _high_risk_summary(review_metrics["high_risk"])
    lines = [
        "# RuoYi 扫描结果验证结论",
        "",
        f"- 验证仓库：`{repo_root}`",
        f"- 报告批次：`{summary.get('run_id', '')}`",
        f"- 最终判定：`{verdict}`",
        "",
        "## 总评",
        "",
        f"- 当前报告文件清单口径 {'通过' if checks['tracked_count_ok'] else '未通过'}：tracked 文件数 `{len(tracked_files)}`，报告文件口径 `{summary.get('eligible_files', 0) + summary.get('skipped_files', 0)}`。",
        f"- 当前报告 first-party HTML/XML/VM 行召回 {'通过' if checks['first_party_sensitive_ok'] else '未通过'}：缺失 `{coverage_metrics['missing_first_party_acceptance_lines']}` 行。",
        f"- 当前报告策略排除路径 {'通过' if checks['excluded_policy_ok'] else '未通过'}：被排除路径中的 finding `{coverage_metrics['excluded_path_findings']}` 条。",
        f"- 当前报告高风险分类 {'通过' if checks['high_risk_ok'] else '未通过'}：{high_risk_details}。",
        f"- 当前报告一方整体 precision {'通过' if checks['first_party_precision_ok'] else '未通过'}：`{review_metrics['first_party_focus']['precision']:.2%}`。",
        "",
        "## 覆盖率基线",
        "",
        f"- tracked 文件总数：`{len(tracked_files)}`",
        f"- 报告口径文件总数：`{summary.get('eligible_files', 0) + summary.get('skipped_files', 0)}`",
        f"- 策略排除 tracked 文件数：`{coverage_metrics['excluded_tracked_files']}`",
        f"- 含中文 tracked 文件数：`{coverage_metrics['tracked_han_files']}`",
        f"- first-party 含中文文件数：`{coverage_metrics['tracked_first_party_han_files']}`",
        f"- 缺失文件数：`{coverage_metrics['missing_files']}`",
        f"- 敏感格式缺失行数：`{coverage_metrics['missing_sensitive_lines']}`",
        f"- first-party 敏感格式缺失行数：`{coverage_metrics['missing_first_party_sensitive_lines']}`",
        f"- first-party HTML/XML/VM 缺失行数：`{coverage_metrics['missing_first_party_acceptance_lines']}`",
        f"- 被排除路径中的 finding 数：`{coverage_metrics['excluded_path_findings']}`",
        f"- baseline 未覆盖但报告命中的额外 finding：`{coverage_metrics['extra_findings']}`",
        "",
        "## 分类准确率",
        "",
        f"- full_repo：复核 `{review_metrics['full_repo']['reviewed']}` 条，precision `{review_metrics['full_repo']['precision']:.2%}`",
        f"- first_party_focus：复核 `{review_metrics['first_party_focus']['reviewed']}` 条，precision `{review_metrics['first_party_focus']['precision']:.2%}`",
        f"- high_risk：复核 `{review_metrics['high_risk']['reviewed']}` 条，precision `{review_metrics['high_risk']['precision']:.2%}`",
        "",
        "### High-risk 分类分项",
        "",
        "| 类别 | 复核数 | 命中数 | Precision |",
        "| --- | ---: | ---: | ---: |",
    ]
    for category, bucket in review_metrics["high_risk"]["by_category"].items():
        lines.append(f"| `{category}` | {bucket['reviewed']} | {bucket['matched']} | {bucket['precision']:.2%} |")

    lines.extend(
        [
            "",
            "## 扫描策略说明",
            "",
            f"- 生效的排除规则：`{', '.join(scan_settings.exclude_globs)}`",
            "- 以下 `target/` 目录在当前仓库中存在，但不属于 tracked 文件，不纳入这次正确性判定：",
        ]
    )
    lines.extend([f"  - `{path}`" for path in ignored_targets] if ignored_targets else ["- 无"])

    lines.extend(["", "## 已确认问题样例", "", "### 召回问题"])
    lines.extend(
        [
            f"- `{_path_line_label(row['path'], row['line'])}`：`{row['text']}`，原因：{row['reason']}"
            for row in confirmed_coverage
        ]
        if confirmed_coverage
        else ["- 未发现"]
    )

    lines.extend(["", "### 分类问题"])
    lines.extend(
        [
            f"- `{_path_line_label(row['path'], row['line'])}`：报告为 `{row['reported_category']}`，独立复核应为 `{row['expected_category']}`。{row['reason']}"
            for row in confirmed_classification
        ]
        if confirmed_classification
        else ["- 未发现"]
    )

    lines.extend(
        [
            "",
            "## 结论",
            "",
        ]
    )
    if verdict == "PASS":
        lines.extend(
            [
                "- 当前报告已经满足既定验收门槛，可作为整改盘点基线使用。",
                "- 仍然建议结合 `classification_review.csv` 中的少量边界样例持续优化规则，但不会阻塞当前批次使用。",
                "- 详细差异见 `coverage_diff.csv` 和 `classification_review.csv`。",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "- 这份报告不能直接视为完全可信，当前更适合作为“问题发现线索”，不适合作为无复核的整改清单。",
                "- 主要风险在于：HTML/XML/VM 等敏感格式的系统性漏报，或高风险类别中仍存在明显误分类。",
                "- 详细差异见 `coverage_diff.csv` 和 `classification_review.csv`。",
                "",
            ]
        )
    return "\n".join(lines)


def _high_risk_summary(high_risk_metrics: Dict[str, Any]) -> str:
    overall = f"汇总 precision `{high_risk_metrics['precision']:.2%}`"
    by_category = high_risk_metrics.get("by_category", {})
    present = {
        category: bucket
        for category, bucket in by_category.items()
        if category in HIGH_RISK_CATEGORIES and bucket.get("reviewed", 0) > 0
    }
    if not present:
        return overall

    failures = [
        f"`{category}` `{bucket['precision']:.2%}`"
        for category, bucket in present.items()
        if bucket["precision"] < 0.95
    ]
    if failures:
        return overall + "，未达标分项：" + "、".join(failures)

    lowest_category, lowest_bucket = min(
        present.items(),
        key=lambda item: item[1]["precision"],
    )
    return overall + f"，最低分项 `{lowest_category}` `{lowest_bucket['precision']:.2%}`"


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if rows:
        fieldnames = list(rows[0].keys())
    else:
        fieldnames = []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(rows)


def _compact_text(text: str, limit: int = 180) -> str:
    value = re.sub(r"\s+", " ", text).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _prioritized_coverage_examples(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    preferred_paths = [
        "ruoyi-admin/src/main/resources/templates/error/service.html",
        "ruoyi-quartz/src/main/resources/mapper/quartz/SysJobLogMapper.xml",
        "ruoyi-system/src/main/resources/mapper/system/SysOperLogMapper.xml",
        "ruoyi-system/src/main/resources/mapper/system/SysDictTypeMapper.xml",
        "ruoyi-system/src/main/resources/mapper/system/SysLogininforMapper.xml",
        "ruoyi-admin/src/main/resources/static/html/ie.html",
        "ruoyi-admin/src/main/resources/static/ruoyi/js/ry-ui.js",
    ]
    by_key: Dict[Tuple[str, Any], Dict[str, Any]] = {}
    for row in rows:
        if row["kind"] not in {"missing_line", "missing_file"}:
            continue
        by_key.setdefault((row["path"], row["line"]), row)

    picked: List[Dict[str, Any]] = []
    for path in preferred_paths:
        for key, row in by_key.items():
            if row["path"] == path:
                picked.append(row)
                break

    if len(picked) < 10:
        remaining = [
            row
            for row in by_key.values()
            if row not in picked
        ]
        remaining.sort(
            key=lambda row: (
                row["scope"] != "first_party_focus",
                row["slice"],
                row["path"],
                _line_sort_value(row["line"]),
            )
        )
        picked.extend(remaining[: 10 - len(picked)])
    return picked[:10]


def _prioritized_classification_examples(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    preferred_paths = [
        "ruoyi-admin/src/main/java/com/ruoyi/web/controller/system/SysMenuController.java",
        "ruoyi-admin/src/main/resources/static/ajax/libs/datapicker/bootstrap-datetimepicker.min.js",
        "ruoyi-admin/src/main/resources/static/ajax/libs/bootstrap-fileinput/fileinput.min.js",
        "ruoyi-admin/src/main/resources/static/ajax/libs/suggest/bootstrap-suggest.min.js",
    ]
    unique: Dict[Tuple[str, Any, str, str], Dict[str, Any]] = {}
    for row in rows:
        if row["status"] != "mismatch":
            continue
        unique.setdefault((row["path"], row["line"], row["reported_category"], row["expected_category"]), row)

    picked: List[Dict[str, Any]] = []
    for path in preferred_paths:
        for row in unique.values():
            if row["path"] == path and row not in picked:
                picked.append(row)
                break

    if len(picked) < 10:
        remaining = [row for row in unique.values() if row not in picked]
        remaining.sort(
            key=lambda row: (
                row["slice"] != "first_party",
                row["path"],
                _line_sort_value(row["line"]),
            )
        )
        picked.extend(remaining[: 10 - len(picked)])
    return picked[:10]


def _line_sort_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _path_line_label(path: str, line: Any) -> str:
    try:
        return f"{path}:{int(line)}"
    except (TypeError, ValueError):
        return path
