from __future__ import absolute_import

import json
import shutil
import threading
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from zh_audit.properties_file import load_properties_document
from zh_audit.terminology_xlsx import exact_terminology_translation, match_locked_terms


TRANSLATION_APPEND_COMMENT = "# Added by zh-audit 码值校译"
TRANSLATION_SESSION_VERSION = 1


def default_translation_config():
    return {
        "source_path": "",
        "target_path": "",
        "auto_accept": False,
    }


class TranslationSession(object):
    def __init__(self, source_path, target_path, glossary, model_config, model_runner, persist_callback=None):
        self.lock = threading.RLock()
        self.source_path = str(source_path)
        self.target_path = str(target_path)
        self.glossary = OrderedDict(glossary)
        self.model_config = dict(model_config)
        self.model_runner = model_runner
        self.persist_callback = persist_callback
        self.source_document = load_properties_document(source_path)
        self.target_document = load_properties_document(target_path)
        self.source_entries = self.source_document.property_entries()
        self.duplicate_keys = {
            "source": self.source_document.duplicate_keys(),
            "target": self.target_document.duplicate_keys(),
        }
        self.items = OrderedDict()
        self.pending_ids = []
        self.recent_ids = []
        self.events = []
        self.total = len(self.source_entries)
        self.processed = 0
        self.skipped = 0
        self.pending = 0
        self.accepted = 0
        self.appended = 0
        self.failed = 0
        self.rejected = 0
        self.regenerated = 0
        self.glossary_applied = 0
        self.current = {
            "key": "",
            "source_text": "",
            "status": "",
        }
        self.status = "idle"
        self.message = "等待校译"
        self.error = ""
        self.started_at = ""
        self.finished_at = ""
        self.stop_requested = False
        self.next_id = 1
        self.backup_path = ""
        self.next_index = 0

    @classmethod
    def from_saved_state(cls, payload, glossary, model_config, model_runner, persist_callback=None):
        source_path = Path(str(payload.get("source_path", "") or "")).expanduser()
        target_path = Path(str(payload.get("target_path", "") or "")).expanduser()
        session = cls(
            source_path=source_path,
            target_path=target_path,
            glossary=glossary,
            model_config=model_config,
            model_runner=model_runner,
            persist_callback=persist_callback,
        )
        session._restore_saved_state(payload)
        return session

    def start(self):
        with self.lock:
            self.status = "running"
            self.message = "校译中"
            self.error = ""
            self.started_at = _timestamp()
            self.finished_at = ""
            self.stop_requested = False
            self.next_index = 0
            self.backup_path = self._backup_target_file()
            if self.duplicate_keys["source"] or self.duplicate_keys["target"]:
                duplicates = []
                if self.duplicate_keys["source"]:
                    duplicates.append("中文文件重复 key: {}".format(", ".join(self.duplicate_keys["source"][:5])))
                if self.duplicate_keys["target"]:
                    duplicates.append("英文文件重复 key: {}".format(", ".join(self.duplicate_keys["target"][:5])))
                raise ValueError("；".join(duplicates))
            self._persist_locked()

    def stop(self):
        with self.lock:
            self.stop_requested = True
            if self.status == "running":
                self.message = "停止中"
            self._persist_locked()

    def resume(self):
        with self.lock:
            if not self.can_resume():
                raise ValueError("Translation task cannot be resumed.")
            self.status = "running"
            self.message = "校译中"
            self.error = ""
            self.finished_at = ""
            self.stop_requested = False
            if self.current.get("key"):
                self.current["status"] = "处理中"
            self._persist_locked()

    def can_resume(self):
        return self.status in ("interrupted", "stopped") and self.next_index < self.total

    def mark_restarted(self):
        with self.lock:
            if self.status == "running":
                self.status = "interrupted"
                self.message = "服务重启，可从上次位置继续"
                self.error = ""
                self.finished_at = _timestamp()
                if self.current.get("key"):
                    self.current["status"] = "等待继续"
                self.stop_requested = False
                self._persist_locked()

    def interrupt(self, error_message):
        with self.lock:
            self.status = "interrupted"
            self.message = "校译中断"
            self.error = str(error_message)
            self.finished_at = _timestamp()
            self.stop_requested = False
            if self.current.get("key"):
                self.current["status"] = "等待继续"
            self._persist_locked()

    def snapshot(self):
        with self.lock:
            pending_items = [self._public_item(self.items[item_id]) for item_id in self.pending_ids]
            recent_items = [self._public_item(self.items[item_id]) for item_id in self.recent_ids]
            return {
                "config": {
                    "source_path": self.source_path,
                    "target_path": self.target_path,
                },
                "status": {
                    "status": self.status,
                    "message": self.message,
                    "error": self.error,
                    "started_at": self.started_at,
                    "finished_at": self.finished_at,
                    "backup_path": self.backup_path,
                    "current": dict(self.current),
                    "counts": self._counts_payload(),
                },
                "pending_items": pending_items,
                "recent_items": recent_items,
                "events": list(self.events),
            }

    def save_state(self):
        with self.lock:
            return self._saved_state_locked()

    def run(self, should_auto_accept):
        while True:
            with self.lock:
                if self.stop_requested:
                    self.status = "stopped"
                    self.message = "已停止"
                    self.finished_at = _timestamp()
                    self.current = {"key": "", "source_text": "", "status": ""}
                    self._persist_locked()
                    return
                if self.next_index >= self.total:
                    if self.status == "running":
                        self.status = "done"
                        self.message = "校译完成"
                        self.finished_at = _timestamp()
                        self.current = {"key": "", "source_text": "", "status": ""}
                        self._persist_locked()
                    return
                source_entry = self.source_entries[self.next_index]
                self.current = {
                    "key": source_entry.key,
                    "source_text": source_entry.value,
                    "status": "处理中",
                }
                self._persist_locked()

            self._process_entry(source_entry, should_auto_accept)

            with self.lock:
                self.next_index += 1
                self.current = {
                    "key": source_entry.key,
                    "source_text": source_entry.value,
                    "status": "已处理",
                }
                self._persist_locked()

    def accept(self, item_id):
        with self.lock:
            item = self._require_pending_item(item_id)
            self._apply_item(item, "accepted", "人工接收")
            return self.snapshot()

    def reject(self, item_id):
        with self.lock:
            item = self._require_pending_item(item_id)
            item["status"] = "rejected"
            item["updated_at"] = _timestamp()
            self.pending_ids.remove(item_id)
            self.pending -= 1
            self.rejected += 1
            self._push_recent(item_id)
            self._push_event("已忽略", item["key"], item["source_text"], item.get("candidate_text", ""))
            self._persist_locked()
            return self.snapshot()

    def regenerate(self, item_id, extra_prompt):
        with self.lock:
            item = self._require_pending_item(item_id)
            item["status"] = "regenerating"
            item["updated_at"] = _timestamp()
            key = item["key"]
            source_text = item["source_text"]
            current_target = item.get("target_text", "")
            locked_terms = list(item.get("locked_terms", []))
            target_missing = item.get("target_missing", False)
            self._persist_locked()
        result = self.model_runner(
            key=key,
            source_text=source_text,
            target_text=current_target,
            locked_terms=locked_terms,
            model_config=self.model_config,
            extra_prompt=extra_prompt,
            target_missing=target_missing,
        )
        normalized = self._normalize_model_result(item, result, current_target)
        with self.lock:
            item["candidate_text"] = normalized["candidate_text"]
            item["reason"] = normalized["reason"]
            item["verdict"] = normalized["verdict"]
            item["status"] = "pending"
            item["updated_at"] = _timestamp()
            item["regeneration_prompt"] = extra_prompt
            self.regenerated += 1
            self._push_event("已重生成", item["key"], item["source_text"], item.get("candidate_text", ""))
            self._persist_locked()
            return self.snapshot()

    def _process_entry(self, source_entry, should_auto_accept):
        key = source_entry.key
        source_text = source_entry.value
        if not source_text.strip():
            with self.lock:
                self.processed += 1
                self.skipped += 1
                self._push_event("已跳过", key, source_text, "")
                self._persist_locked()
            return

        target_entry = self.target_document.find(key)
        target_text = target_entry.value if target_entry is not None else ""
        exact_translation = exact_terminology_translation(source_text, self.glossary)
        locked_terms = match_locked_terms(source_text, self.glossary)

        if exact_translation:
            if target_text.strip() == exact_translation.strip():
                with self.lock:
                    self.processed += 1
                    self.skipped += 1
                    self.glossary_applied += 1
                    self._push_event("术语已准确", key, source_text, target_text)
                    self._persist_locked()
                return
            item = self._create_item(
                key=key,
                source_text=source_text,
                target_text=target_text,
                candidate_text=exact_translation,
                locked_terms=locked_terms,
                reason="整句命中术语词典。",
                verdict="needs_update",
                target_missing=target_entry is None,
            )
            with self.lock:
                self.glossary_applied += 1
                self._finalize_item(item, should_auto_accept=should_auto_accept(), force_accept=True, event_label="术语直出")
            return

        result = self.model_runner(
            key=key,
            source_text=source_text,
            target_text=target_text,
            locked_terms=locked_terms,
            model_config=self.model_config,
            extra_prompt="",
            target_missing=target_entry is None,
        )
        normalized = self._normalize_model_result(
            {
                "key": key,
                "source_text": source_text,
                "target_text": target_text,
                "target_missing": target_entry is None,
                "locked_terms": locked_terms,
            },
            result,
            target_text,
        )

        if normalized["verdict"] == "accurate" and target_entry is not None:
            with self.lock:
                self.processed += 1
                self.skipped += 1
                self._push_event("已跳过", key, source_text, target_text)
                self._persist_locked()
            return

        item = self._create_item(
            key=key,
            source_text=source_text,
            target_text=target_text,
            candidate_text=normalized["candidate_text"],
            locked_terms=locked_terms,
            reason=normalized["reason"],
            verdict=normalized["verdict"],
            target_missing=target_entry is None,
        )
        with self.lock:
            self._finalize_item(item, should_auto_accept=should_auto_accept(), force_accept=False, event_label="待审批")

    def _normalize_model_result(self, item, result, current_target):
        verdict = str(result.get("verdict", "") or "").strip().lower()
        candidate = str(result.get("candidate_translation", "") or "").strip()
        reason = str(result.get("reason", "") or "").strip()
        if verdict not in ("accurate", "needs_update"):
            verdict = "needs_update"
        locked_terms = list(item.get("locked_terms", []))
        target_missing = bool(item.get("target_missing"))
        if verdict == "accurate" and target_missing:
            verdict = "needs_update"
        if verdict == "accurate":
            if locked_terms and not _contains_locked_terms(current_target, locked_terms):
                verdict = "needs_update"
                reason = "现有英文未满足术语词典要求。"
            return {
                "verdict": verdict,
                "candidate_text": current_target,
                "reason": reason or "现有英文准确。",
            }
        if not candidate:
            raise ValueError("Model did not return candidate_translation for key {}".format(item["key"]))
        if locked_terms and not _contains_locked_terms(candidate, locked_terms):
            retry_prompt = "候选英文必须严格包含这些术语：{}。请只返回符合要求的英文。".format(
                ", ".join("{}={}".format(term["source"], term["target"]) for term in locked_terms)
            )
            retried = self.model_runner(
                key=item["key"],
                source_text=item["source_text"],
                target_text=current_target,
                locked_terms=locked_terms,
                model_config=self.model_config,
                extra_prompt=retry_prompt,
                target_missing=target_missing,
            )
            retry_candidate = str(retried.get("candidate_translation", "") or "").strip()
            retry_reason = str(retried.get("reason", "") or "").strip()
            if retry_candidate and _contains_locked_terms(retry_candidate, locked_terms):
                return {
                    "verdict": "needs_update",
                    "candidate_text": retry_candidate,
                    "reason": retry_reason or "按术语词典重试后生成。",
                }
            return {
                "verdict": "needs_update",
                "candidate_text": retry_candidate or candidate,
                "reason": "术语不符合：{}".format(
                    ", ".join("{}={}".format(term["source"], term["target"]) for term in locked_terms)
                ),
            }
        return {
            "verdict": "needs_update",
            "candidate_text": candidate,
            "reason": reason or "模型建议更新英文翻译。",
        }

    def _create_item(self, key, source_text, target_text, candidate_text, locked_terms, reason, verdict, target_missing):
        with self.lock:
            item_id = "tx-{}".format(self.next_id)
            self.next_id += 1
            item = {
                "id": item_id,
                "key": key,
                "source_text": source_text,
                "target_text": target_text,
                "candidate_text": candidate_text,
                "locked_terms": [dict(term) for term in locked_terms],
                "reason": reason,
                "verdict": verdict,
                "target_missing": bool(target_missing),
                "status": "pending",
                "updated_at": _timestamp(),
            }
            self.items[item_id] = item
            self._persist_locked()
            return item

    def _finalize_item(self, item, should_auto_accept, force_accept, event_label):
        self.processed += 1
        if force_accept or should_auto_accept:
            self._apply_item(item, "accepted", event_label)
            return
        item["status"] = "pending"
        item["updated_at"] = _timestamp()
        self.pending_ids.append(item["id"])
        self.pending += 1
        self._push_event(event_label, item["key"], item["source_text"], item.get("candidate_text", ""))
        self._persist_locked()

    def _apply_item(self, item, status, reason):
        _, appended = self._write_candidate(item["key"], item["candidate_text"])
        item["target_text"] = item["candidate_text"]
        item["status"] = status
        item["updated_at"] = _timestamp()
        item["accepted_reason"] = reason
        if item["id"] in self.pending_ids:
            self.pending_ids.remove(item["id"])
            self.pending -= 1
        self.accepted += 1
        if appended:
            self.appended += 1
        self._push_recent(item["id"])
        self._push_event(reason, item["key"], item["source_text"], item.get("candidate_text", ""))
        self._persist_locked()

    def _write_candidate(self, key, candidate_text):
        if self.target_document.find(key) is None:
            self.target_document.append_comment_once(TRANSLATION_APPEND_COMMENT)
        entry, appended = self.target_document.set_value(key, candidate_text, separator="=")
        self.target_document.write()
        return entry, appended

    def _push_recent(self, item_id):
        if item_id in self.recent_ids:
            self.recent_ids.remove(item_id)
        self.recent_ids.insert(0, item_id)
        del self.recent_ids[50:]

    def _push_event(self, label, key, source_text, target_text):
        self.events.insert(
            0,
            {
                "at": _timestamp(),
                "label": label,
                "key": key,
                "source_text": source_text,
                "target_text": target_text,
            },
        )
        del self.events[100:]

    def _backup_target_file(self):
        target = Path(self.target_path)
        backup_name = "{}.bak.{}".format(target.name, datetime.now().strftime("%Y%m%d-%H%M%S"))
        backup_path = target.with_name(backup_name)
        shutil.copyfile(str(target), str(backup_path))
        return str(backup_path)

    def _require_pending_item(self, item_id):
        item = self.items.get(item_id)
        if item is None:
            raise KeyError("Unknown translation item: {}".format(item_id))
        if item.get("status") != "pending":
            raise ValueError("Translation item is not pending: {}".format(item_id))
        return item

    def _public_item(self, item):
        return {
            "id": item["id"],
            "key": item["key"],
            "source_text": item["source_text"],
            "target_text": item.get("target_text", ""),
            "candidate_text": item.get("candidate_text", ""),
            "locked_terms": [dict(term) for term in item.get("locked_terms", [])],
            "reason": item.get("reason", ""),
            "verdict": item.get("verdict", ""),
            "status": item.get("status", ""),
            "target_missing": bool(item.get("target_missing")),
            "updated_at": item.get("updated_at", ""),
        }

    def _counts_payload(self):
        return {
            "total": self.total,
            "processed": self.processed,
            "skipped": self.skipped,
            "pending": self.pending,
            "accepted": self.accepted,
            "appended": self.appended,
            "failed": self.failed,
            "rejected": self.rejected,
            "regenerated": self.regenerated,
            "glossary_applied": self.glossary_applied,
        }

    def _saved_state_locked(self):
        return {
            "version": TRANSLATION_SESSION_VERSION,
            "source_path": self.source_path,
            "target_path": self.target_path,
            "counts": self._counts_payload(),
            "items": [dict(item) for item in self.items.values()],
            "pending_ids": list(self.pending_ids),
            "recent_ids": list(self.recent_ids),
            "events": list(self.events),
            "current": dict(self.current),
            "status": self.status,
            "message": self.message,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "stop_requested": bool(self.stop_requested),
            "next_id": self.next_id,
            "backup_path": self.backup_path,
            "duplicate_keys": {
                "source": list(self.duplicate_keys.get("source", [])),
                "target": list(self.duplicate_keys.get("target", [])),
            },
            "next_index": self.next_index,
        }

    def _restore_saved_state(self, payload):
        counts = dict(payload.get("counts", {}))
        self.items = OrderedDict()
        for item in payload.get("items", []):
            item_id = str(item.get("id", "") or "")
            if not item_id:
                continue
            restored = dict(item)
            restored["id"] = item_id
            self.items[item_id] = restored
        self.pending_ids = [item_id for item_id in payload.get("pending_ids", []) if item_id in self.items]
        self.recent_ids = [item_id for item_id in payload.get("recent_ids", []) if item_id in self.items]
        self.events = list(payload.get("events", []))
        self.processed = int(counts.get("processed", 0))
        self.skipped = int(counts.get("skipped", 0))
        self.pending = int(counts.get("pending", len(self.pending_ids)))
        self.accepted = int(counts.get("accepted", 0))
        self.appended = int(counts.get("appended", 0))
        self.failed = int(counts.get("failed", 0))
        self.rejected = int(counts.get("rejected", 0))
        self.regenerated = int(counts.get("regenerated", 0))
        self.glossary_applied = int(counts.get("glossary_applied", 0))
        self.current = dict(payload.get("current", {}))
        self.status = str(payload.get("status", "idle") or "idle")
        self.message = str(payload.get("message", "等待校译") or "等待校译")
        self.error = str(payload.get("error", "") or "")
        self.started_at = str(payload.get("started_at", "") or "")
        self.finished_at = str(payload.get("finished_at", "") or "")
        self.stop_requested = bool(payload.get("stop_requested", False))
        self.next_id = max(int(payload.get("next_id", 1)), 1)
        self.backup_path = str(payload.get("backup_path", "") or "")
        duplicate_keys = dict(payload.get("duplicate_keys", {}))
        self.duplicate_keys = {
            "source": list(duplicate_keys.get("source", self.duplicate_keys.get("source", []))),
            "target": list(duplicate_keys.get("target", self.duplicate_keys.get("target", []))),
        }
        try:
            next_index = int(payload.get("next_index", self.processed))
        except (TypeError, ValueError):
            next_index = self.processed
        self.next_index = min(max(next_index, 0), self.total)
        if self.status == "running":
            self.status = "interrupted"
            self.message = "服务重启，可从上次位置继续"
            self.error = ""
            self.finished_at = _timestamp()
            if self.current.get("key"):
                self.current["status"] = "等待继续"
            self.stop_requested = False

    def _persist_locked(self):
        if self.persist_callback is None:
            return
        self.persist_callback(self._saved_state_locked())


def build_translation_user_prompt(key, source_text, target_text, locked_terms, extra_prompt, target_missing):
    payload = {
        "key": key,
        "source_text": source_text,
        "target_text": target_text,
        "target_missing": bool(target_missing),
        "locked_terms": [
            {"source": term["source"], "target": term["target"]}
            for term in locked_terms
        ],
        "extra_prompt": extra_prompt or "",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def build_translation_system_prompt():
    return (
        "You are a professional translator and reviewer for i18n properties files.\n"
        "Return JSON only with keys: verdict, candidate_translation, reason.\n"
        "verdict must be either accurate or needs_update.\n"
        "candidate_translation must contain only the translated RHS text, never include the key.\n"
        "Preserve placeholders exactly, including {0}, {}, %s, ${name} and similar forms.\n"
        "If locked_terms are provided, candidate_translation must use the target terms exactly as given.\n"
        "If target_text is already accurate, set verdict=accurate and candidate_translation to the unchanged target_text."
    )


def _contains_locked_terms(candidate, locked_terms):
    value = str(candidate or "")
    for term in locked_terms:
        if term["target"] not in value:
            return False
    return True


def _timestamp():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()
