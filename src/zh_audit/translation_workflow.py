from __future__ import absolute_import

import json
import shutil
import threading
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from zh_audit.candidate_validation import (
    MAX_MODEL_CALLS_PER_ITEM,
    contains_locked_terms,
    has_matching_placeholders,
    normalize_review_result,
    sanitize_candidate_text,
    validate_candidate_text,
    validation_message,
)
from zh_audit.properties_file import load_properties_document
from zh_audit.terminology_xlsx import exact_terminology_translation, match_locked_terms
from zh_audit.utils import contains_han, decode_unicode_escapes


TRANSLATION_SESSION_VERSION = 1


def default_translation_config():
    return {
        "source_path": "",
        "target_path": "",
        "auto_accept": False,
    }


class TranslationSession(object):
    def __init__(
        self,
        source_path,
        target_path,
        glossary,
        model_config,
        model_runner,
        reviewer_runner=None,
        persist_callback=None,
    ):
        self.lock = threading.RLock()
        self.source_path = str(source_path)
        self.target_path = str(target_path)
        self.glossary = OrderedDict(glossary)
        self.model_config = dict(model_config)
        self.model_runner = model_runner
        self.reviewer_runner = reviewer_runner
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
    def from_saved_state(
        cls,
        payload,
        glossary,
        model_config,
        model_runner,
        reviewer_runner=None,
        persist_callback=None,
    ):
        source_path = Path(str(payload.get("source_path", "") or "")).expanduser()
        target_path = Path(str(payload.get("target_path", "") or "")).expanduser()
        session = cls(
            source_path=source_path,
            target_path=target_path,
            glossary=glossary,
            model_config=model_config,
            model_runner=model_runner,
            reviewer_runner=reviewer_runner,
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
                source_text = _display_text(source_entry.value)
                self.current = {
                    "key": source_entry.key,
                    "source_text": source_text,
                    "status": "处理中",
                }
                self._persist_locked()

            self._process_entry(source_entry, should_auto_accept)

            with self.lock:
                self.next_index += 1
                self.current = {
                    "key": source_entry.key,
                    "source_text": source_text,
                    "status": "已处理",
                }
                self._persist_locked()

    def accept(self, item_id):
        with self.lock:
            item = self._require_pending_item(item_id)
            if not item.get("can_accept", True):
                raise ValueError(item.get("validation_message") or "Candidate validation failed.")
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
        normalized = self._build_candidate_with_guardrails(
            key=key,
            source_text=source_text,
            current_target=current_target,
            locked_terms=locked_terms,
            target_missing=target_missing,
            base_extra_prompt=extra_prompt,
        )
        with self.lock:
            self._update_item_validation(item, normalized)
            item["status"] = "pending"
            item["updated_at"] = _timestamp()
            item["regeneration_prompt"] = extra_prompt
            self.regenerated += 1
            self._push_event(self._pending_event_label(item, "已重生成"), item["key"], item["source_text"], item.get("candidate_text", ""))
            self._persist_locked()
            return self.snapshot()

    def _process_entry(self, source_entry, should_auto_accept):
        key = source_entry.key
        source_text = _display_text(source_entry.value)
        if not source_text.strip():
            with self.lock:
                self.processed += 1
                self.skipped += 1
                self._push_event("已跳过：中文为空", key, source_text, "")
                self._persist_locked()
            return

        target_entry = self.target_document.find(key)
        target_text = _display_text(target_entry.value) if target_entry is not None else ""
        exact_translation = exact_terminology_translation(source_text, self.glossary)
        locked_terms = match_locked_terms(source_text, self.glossary)

        if exact_translation:
            if target_text.strip() == exact_translation.strip():
                with self.lock:
                    self.processed += 1
                    self.skipped += 1
                    self.glossary_applied += 1
                    self._push_event("已跳过：术语已符合词典", key, source_text, target_text)
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
                validation_state="passed",
                validation_message="",
                validation_issue="",
                can_accept=True,
                model_calls_used=0,
            )
            with self.lock:
                self.glossary_applied += 1
                self._finalize_item(item, should_auto_accept=should_auto_accept(), force_accept=True, event_label="术语直出")
            return

        normalized = self._build_candidate_with_guardrails(
            key=key,
            source_text=source_text,
            current_target=target_text,
            locked_terms=locked_terms,
            target_missing=target_entry is None,
            base_extra_prompt="",
        )

        if (
            normalized["validation_state"] == "passed"
            and normalized["verdict"] == "accurate"
            and target_entry is not None
        ):
            with self.lock:
                self.processed += 1
                self.skipped += 1
                self._push_event("已跳过：翻译准确，无需更新", key, source_text, target_text)
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
            validation_state=normalized["validation_state"],
            validation_message=normalized["validation_message"],
            validation_issue=normalized.get("validation_issue", ""),
            can_accept=normalized["can_accept"],
            model_calls_used=normalized["model_calls_used"],
        )
        with self.lock:
            self._finalize_item(item, should_auto_accept=should_auto_accept(), force_accept=False, event_label="待审批")

    def _build_candidate_with_guardrails(self, key, source_text, current_target, locked_terms, target_missing, base_extra_prompt):
        model_calls_used = 0
        retry_issue = ""
        last_result = {
            "verdict": "needs_update",
            "candidate_text": sanitize_candidate_text(current_target),
            "reason": "",
            "validation_state": "failed",
            "validation_message": validation_message("校验未通过"),
            "validation_issue": "校验未通过",
            "can_accept": False,
            "model_calls_used": 0,
        }
        while model_calls_used < MAX_MODEL_CALLS_PER_ITEM:
            raw_result = self.model_runner(
                key=key,
                source_text=source_text,
                target_text=current_target,
                locked_terms=locked_terms,
                model_config=self.model_config,
                extra_prompt=self._build_retry_prompt(base_extra_prompt, retry_issue),
                target_missing=target_missing,
            )
            model_calls_used += 1
            normalized = self._normalize_model_result(
                {
                    "key": key,
                    "source_text": source_text,
                    "target_text": current_target,
                    "target_missing": target_missing,
                    "locked_terms": locked_terms,
                },
                raw_result,
                current_target,
            )
            candidate_text = normalized["candidate_text"]
            validation_issue = validate_candidate_text(
                source_text,
                candidate_text,
                raw_candidate_text=raw_result.get("candidate_translation", candidate_text),
                locked_terms=locked_terms,
                key=key,
                enforce_placeholders=True,
            )
            if validation_issue:
                retry_issue = validation_issue
                last_result = {
                    "verdict": "needs_update",
                    "candidate_text": candidate_text,
                    "reason": normalized["reason"],
                    "validation_state": "failed",
                    "validation_message": validation_message(validation_issue),
                    "validation_issue": validation_issue,
                    "can_accept": False,
                    "model_calls_used": model_calls_used,
                }
                continue
            if self.reviewer_runner is not None:
                if model_calls_used >= MAX_MODEL_CALLS_PER_ITEM:
                    retry_issue = "已达到最大模型调用次数，未完成AI复核"
                    break
                review_result = self.reviewer_runner(
                    key=key,
                    source_text=source_text,
                    target_text=current_target,
                    candidate_text=candidate_text,
                    locked_terms=locked_terms,
                    model_config=self.model_config,
                    target_missing=target_missing,
                )
                model_calls_used += 1
                reviewed = normalize_review_result(review_result)
                if reviewed["decision"] != "pass":
                    retry_issue = reviewed["issues"][0]
                    last_result = {
                        "verdict": "needs_update",
                        "candidate_text": candidate_text,
                        "reason": normalized["reason"],
                        "validation_state": "failed",
                        "validation_message": validation_message(retry_issue),
                        "validation_issue": retry_issue,
                        "can_accept": False,
                        "model_calls_used": model_calls_used,
                    }
                    continue
            return {
                "verdict": normalized["verdict"],
                "candidate_text": candidate_text,
                "reason": normalized["reason"],
                "validation_state": "passed",
                "validation_message": "",
                "validation_issue": "",
                "can_accept": True,
                "model_calls_used": model_calls_used,
            }
        failure_issue = retry_issue or last_result.get("validation_issue") or "已达到最大模型调用次数"
        last_result["validation_state"] = "failed"
        last_result["validation_message"] = validation_message(failure_issue)
        last_result["validation_issue"] = failure_issue
        last_result["can_accept"] = False
        last_result["model_calls_used"] = min(model_calls_used, MAX_MODEL_CALLS_PER_ITEM)
        return last_result

    def _normalize_model_result(self, item, result, current_target):
        verdict = str(result.get("verdict", "") or "").strip().lower()
        candidate = sanitize_candidate_text(result.get("candidate_translation", ""))
        reason = _display_text(result.get("reason", "")).strip()
        if verdict not in ("accurate", "needs_update"):
            verdict = "needs_update"
        locked_terms = list(item.get("locked_terms", []))
        target_missing = bool(item.get("target_missing"))
        if verdict == "accurate" and target_missing:
            verdict = "needs_update"
        if verdict == "accurate":
            if locked_terms and not contains_locked_terms(current_target, locked_terms):
                verdict = "needs_update"
                reason = "现有英文未满足术语词典要求。"
            else:
                return {
                    "verdict": verdict,
                    "candidate_text": sanitize_candidate_text(current_target),
                    "reason": _normalize_reason(reason, fallback="现有英文翻译准确。"),
                }
        if not candidate:
            raise ValueError("Model did not return candidate_translation for key {}".format(item["key"]))
        return {
            "verdict": "needs_update",
            "candidate_text": candidate,
            "reason": _normalize_reason(
                reason,
                fallback="目标英文缺失，建议补充候选英文。" if target_missing else "现有英文翻译不够准确，建议更新为候选英文。",
            ),
        }

    def _build_retry_prompt(self, base_extra_prompt, retry_issue):
        parts = []
        if retry_issue:
            parts.append("上一版候选未通过系统校验，请严格修复这个问题：{}。".format(retry_issue))
        if base_extra_prompt:
            parts.append(str(base_extra_prompt).strip())
        return "\n".join(part for part in parts if part).strip()

    def _create_item(
        self,
        key,
        source_text,
        target_text,
        candidate_text,
        locked_terms,
        reason,
        verdict,
        target_missing,
        validation_state,
        validation_message,
        validation_issue,
        can_accept,
        model_calls_used,
    ):
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
                "validation_state": str(validation_state or "passed"),
                "validation_message": str(validation_message or ""),
                "validation_issue": str(validation_issue or ""),
                "can_accept": bool(can_accept),
                "model_calls_used": int(model_calls_used or 0),
                "status": "pending",
                "updated_at": _timestamp(),
            }
            self.items[item_id] = item
            self._persist_locked()
            return item

    def _update_item_validation(self, item, normalized):
        item["candidate_text"] = normalized["candidate_text"]
        item["reason"] = normalized["reason"]
        item["verdict"] = normalized["verdict"]
        item["validation_state"] = normalized["validation_state"]
        item["validation_message"] = normalized["validation_message"]
        item["validation_issue"] = normalized.get("validation_issue", "")
        item["can_accept"] = bool(normalized["can_accept"])
        item["model_calls_used"] = int(normalized["model_calls_used"])

    def _finalize_item(self, item, should_auto_accept, force_accept, event_label):
        self.processed += 1
        if force_accept or (should_auto_accept and item.get("can_accept", True)):
            self._apply_item(item, "accepted", event_label)
            return
        item["status"] = "pending"
        item["updated_at"] = _timestamp()
        self.pending_ids.append(item["id"])
        self.pending += 1
        if item.get("validation_state") == "failed":
            self.failed += 1
        self._push_event(self._pending_event_label(item, event_label), item["key"], item["source_text"], item.get("candidate_text", ""))
        self._persist_locked()

    def _pending_event_label(self, item, default_label):
        if item.get("validation_state") == "failed":
            return "候选未通过校验：{}".format(item.get("validation_issue") or "请重生成")
        return default_label

    def _apply_item(self, item, status, reason):
        entry, appended = self._write_candidate(item["key"], item["candidate_text"], item.get("source_text", ""))
        item["candidate_text"] = entry.value
        item["target_text"] = entry.value
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

    def _write_candidate(self, key, candidate_text, source_text):
        normalized_candidate = sanitize_candidate_text(candidate_text)
        if not normalized_candidate:
            raise ValueError("Candidate translation is empty for key {}".format(key))
        if not has_matching_placeholders(source_text, normalized_candidate):
            raise ValueError("Candidate translation lost placeholders for key {}".format(key))
        entry, appended = self.target_document.set_value(key, normalized_candidate, separator="=")
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
            "validation_state": item.get("validation_state", "passed"),
            "validation_message": item.get("validation_message", ""),
            "can_accept": bool(item.get("can_accept", True)),
            "model_calls_used": int(item.get("model_calls_used", 0) or 0),
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
            restored.setdefault("validation_state", "passed")
            restored.setdefault("validation_message", "")
            restored.setdefault("validation_issue", "")
            restored.setdefault("can_accept", True)
            restored.setdefault("model_calls_used", 0)
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
        "candidate_translation must be natural English and must not directly copy the Chinese source text.\n"
        "candidate_translation must not include Chinese explanations, SQL, JSON, or multiple lines.\n"
        "reason must be written in Simplified Chinese.\n"
        "Do not output English in reason unless it is a required technical term quoted from the source or target text.\n"
        "Preserve placeholders exactly, including {0}, {}, %s, ${name} and similar forms.\n"
        "If locked_terms are provided, candidate_translation must use the target terms exactly as given.\n"
        "If target_text is already accurate, set verdict=accurate and candidate_translation to the unchanged target_text."
    )


def build_translation_review_user_prompt(key, source_text, target_text, candidate_text, locked_terms, target_missing):
    payload = {
        "key": key,
        "source_text": source_text,
        "target_text": target_text,
        "candidate_text": candidate_text,
        "target_missing": bool(target_missing),
        "locked_terms": [
            {"source": term["source"], "target": term["target"]}
            for term in locked_terms
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def build_translation_review_system_prompt():
    return (
        "You are a strict QA reviewer for English i18n properties translations.\n"
        "Return JSON only with keys: decision, issues.\n"
        "decision must be either pass or fail.\n"
        "issues must be an array of short Simplified Chinese strings.\n"
        "Fail when the candidate is not natural English, still contains untranslated Chinese, omits source meaning, or breaks placeholders.\n"
        "Pass only when the candidate is a complete and accurate English translation of the source text."
    )


def _timestamp():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _display_text(value):
    return decode_unicode_escapes(str(value or ""))


def _normalize_reason(reason, fallback):
    value = _display_text(reason).strip()
    if contains_han(value):
        return value
    return str(fallback or "").strip()
