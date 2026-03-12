from __future__ import absolute_import

import json
import os
from pathlib import Path


def load_json_file(path):
    target = Path(path)
    if not target.exists():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError("Invalid session snapshot {}: {}".format(target, exc))


def write_json_atomically(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target.with_name(target.name + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(str(temp_path), str(target))
