import json
from pathlib import Path
from typing import Any, List, Optional

from zh_audit.models import RepoSpec, ScanSettings


def _load_yaml_like(path):
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except ValueError:
        pass

    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise ValueError(
            "{} is not valid JSON and PyYAML is not installed for YAML parsing.".format(path)
        )

    return yaml.safe_load(text)


def load_manifest(path):
    data = _load_yaml_like(path)
    if not isinstance(data, list):
        raise ValueError("Manifest must be a list of repositories.")

    repos = []
    for entry in data:
        if not isinstance(entry, str):
            raise ValueError("Manifest entries must be repository path strings.")
        repo_path = entry.strip()
        if not repo_path:
            raise ValueError("Manifest entries must be non-empty repository path strings.")
        repos.append(RepoSpec(path=Path(repo_path).expanduser().resolve()))
    return repos


def load_scan_settings(path):
    if path is None:
        return ScanSettings()
    data = _load_yaml_like(path)
    if not isinstance(data, dict):
        raise ValueError("Scan policy must be an object.")
    exclude_globs = data.get("exclude_globs")
    if exclude_globs is None:
        resolved_globs = ScanSettings().exclude_globs
    elif isinstance(exclude_globs, list) and all(isinstance(item, str) and item.strip() for item in exclude_globs):
        resolved_globs = [item.strip() for item in exclude_globs]
    else:
        raise ValueError("scan_policy.exclude_globs must be a list of non-empty strings.")
    return ScanSettings(
        max_file_size_bytes=int(data.get("max_file_size_bytes", 5 * 1024 * 1024)),
        context_lines=int(data.get("context_lines", 1)),
        exclude_globs=resolved_globs,
    )
