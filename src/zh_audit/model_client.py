from __future__ import absolute_import

import json
import multiprocessing
import re
import socket
import time
from urllib import error as urllib_error
from urllib import request as urllib_request


SMART_QUOTE_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u300c": '"',
        "\u300d": '"',
        "\u300e": '"',
        "\u300f": '"',
        "\uff02": '"',
        "\uff07": "'",
    }
)
DEFAULT_CHAT_COMPLETION_TIMEOUT_SECONDS = 600
DEFAULT_PROBE_TIMEOUT_SECONDS = 15
TRAILING_COMMA_PATTERN = re.compile(r",(\s*[}\]])")
CODE_FENCE_PATTERN = re.compile(r"^\s*```(?:json)?\s*([\s\S]*?)\s*```\s*$", re.IGNORECASE)
THINK_END_TAG_PATTERN = re.compile(r"</think>", re.IGNORECASE)
JSON_STRING_FIELD_TEMPLATE = r'"{field}"\s*:\s*"((?:\\.|[^"\\])*)"'
JSON_SINGLE_QUOTED_FIELD_TEMPLATE = r"'{field}'\s*:\s*'((?:\\.|[^'\\])*)'"
LINE_FIELD_TEMPLATE = r"(?mi)^\s*{field}\s*[:=]\s*(.+?)\s*$"
MODEL_REQUEST_POLL_INTERVAL_SECONDS = 0.2
RETRYABLE_MODEL_RESPONSE_MARKERS = (
    "模型响应不是合法 JSON",
    "模型响应中缺少 message content",
    "模型响应 JSON 必须是对象",
    "Model response content is empty.",
    "Model response does not contain a valid JSON object",
    "Model did not return candidate_translation",
)


class ModelResponseFormatError(ValueError):
    def __init__(
        self,
        message,
        *,
        raw_response="",
        raw_content="",
        parse_error_detail="",
        extracted_candidate_text="",
        extracted_reason="",
    ):
        ValueError.__init__(self, message)
        self.raw_response = str(raw_response or "")
        self.raw_content = str(raw_content or "")
        self.parse_error_detail = str(parse_error_detail or "")
        self.extracted_candidate_text = str(extracted_candidate_text or "")
        self.extracted_reason = str(extracted_reason or "")


class ModelRequestTimeoutError(TimeoutError):
    pass


class ModelRequestCancelledError(Exception):
    pass


def call_openai_compatible_json(
    model_config,
    system_prompt,
    user_prompt,
    max_tokens=None,
    timeout=DEFAULT_CHAT_COMPLETION_TIMEOUT_SECONDS,
    cancel_event=None,
):
    payload = {
        "model": _required_model_value(model_config, "model"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": int(max_tokens or model_config.get("max_tokens") or 256),
    }
    raw = _post_chat_completion(model_config, payload, timeout=timeout, cancel_event=cancel_event)
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        extracted = _extract_debug_fields(raw)
        raise ModelResponseFormatError(
            "模型响应不是合法 JSON：{}".format(raw[:200]),
            raw_response=raw,
            parse_error_detail=str(exc),
            extracted_candidate_text=extracted.get("candidate_translation", ""),
            extracted_reason=extracted.get("reason", ""),
        )
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ModelResponseFormatError(
            "模型响应中缺少 message content。",
            raw_response=raw,
        )
    content = _normalize_message_content(content)
    try:
        parsed = _extract_json_object(content)
    except ValueError as exc:
        extracted = _extract_debug_fields(content)
        raise ModelResponseFormatError(
            str(exc),
            raw_response=raw,
            raw_content=content,
            parse_error_detail=str(exc),
            extracted_candidate_text=extracted.get("candidate_translation", ""),
            extracted_reason=extracted.get("reason", ""),
        )
    if not isinstance(parsed, dict):
        extracted = _extract_debug_fields(content)
        raise ModelResponseFormatError(
            "模型响应 JSON 必须是对象。",
            raw_response=raw,
            raw_content=content,
            extracted_candidate_text=extracted.get("candidate_translation", ""),
            extracted_reason=extracted.get("reason", ""),
        )
    return parsed


def probe_openai_compatible_model(model_config, timeout=DEFAULT_PROBE_TIMEOUT_SECONDS, cancel_event=None):
    payload = {
        "model": _required_model_value(model_config, "model"),
        "messages": [
            {"role": "system", "content": "You are a connectivity probe."},
            {"role": "user", "content": "Reply with OK."},
        ],
        "temperature": 0,
        "max_tokens": 4,
    }
    raw = _post_chat_completion(model_config, payload, timeout=timeout, cancel_event=cancel_event)
    try:
        response = json.loads(raw)
    except ValueError:
        raise ValueError("连通性测试失败：模型接口返回的不是合法 JSON。")
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("连通性测试失败：模型接口返回中缺少 choices.message.content。")
    content = _normalize_message_content(content)
    return {
        "message": str(content or "").strip() or "OK",
    }


def _post_chat_completion(model_config, payload, timeout, cancel_event=None):
    base_url = str(model_config.get("base_url", "") or "").rstrip("/")
    api_key = str(model_config.get("api_key", "") or "").strip()
    if not base_url:
        raise ValueError("模型配置缺少 Base URL。")
    if not api_key:
        raise ValueError("模型配置缺少 API Key。")

    timeout_seconds = float(timeout or 0)
    if timeout_seconds <= 0:
        timeout_seconds = DEFAULT_CHAT_COMPLETION_TIMEOUT_SECONDS

    ctx = multiprocessing.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    process = ctx.Process(
        target=_post_chat_completion_worker,
        args=(base_url, api_key, payload, timeout_seconds, child_conn),
        name="zh-audit-model-request",
    )
    process.start()
    child_conn.close()
    deadline = time.monotonic() + timeout_seconds
    try:
        while True:
            if parent_conn.poll(MODEL_REQUEST_POLL_INTERVAL_SECONDS):
                message = parent_conn.recv()
                break
            if cancel_event is not None and cancel_event.is_set():
                _terminate_request_process(process)
                raise ModelRequestCancelledError("模型请求已取消。")
            if time.monotonic() >= deadline:
                _terminate_request_process(process)
                raise ModelRequestTimeoutError("模型请求超时（{}s）".format(int(timeout_seconds)))
            if not process.is_alive():
                message = None
                break
        if not message:
            raise ValueError("连通性测试失败：模型请求进程异常退出。")
        if message.get("ok"):
            return str(message.get("raw", ""))
        kind = str(message.get("kind", "") or "")
        if kind == "timeout":
            raise ModelRequestTimeoutError("模型请求超时（{}s）".format(int(timeout_seconds)))
        if kind == "http_error":
            raise ValueError(
                "连通性测试失败：模型接口返回 HTTP {}。{}".format(
                    int(message.get("code", 0)),
                    str(message.get("details", "") or "")[:300],
                )
            )
        if kind == "url_error":
            raise ValueError(
                "连通性测试失败：无法访问模型地址 {}。{}".format(
                    str(message.get("url", "") or ""),
                    str(message.get("message", "") or ""),
                )
            )
        raise ValueError("连通性测试失败：{}".format(str(message.get("message", "") or "模型请求失败。")))
    finally:
        parent_conn.close()
        if process.is_alive():
            process.join(0.1)
        if process.is_alive():
            _terminate_request_process(process)
        process.join(0.1)


def _post_chat_completion_worker(base_url, api_key, payload, timeout, conn):
    url = "{}/chat/completions".format(str(base_url or "").rstrip("/"))
    data = json.dumps(payload).encode("utf-8")
    request = urllib_request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(api_key),
        },
    )
    try:
        response = urllib_request.urlopen(request, timeout=timeout)
        raw = response.read().decode("utf-8")
        conn.send({"ok": True, "raw": raw})
    except socket.timeout as exc:
        conn.send({"ok": False, "kind": "timeout", "message": str(exc)})
    except urllib_error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        conn.send({"ok": False, "kind": "http_error", "code": exc.code, "details": details[:300]})
    except urllib_error.URLError as exc:
        reason = exc.reason
        message = str(reason if reason is not None else exc)
        if isinstance(reason, socket.timeout) or "timed out" in message.lower():
            conn.send({"ok": False, "kind": "timeout", "message": message})
        else:
            conn.send({"ok": False, "kind": "url_error", "url": url, "message": message})
    except Exception as exc:
        conn.send({"ok": False, "kind": "unexpected", "message": str(exc)})
    finally:
        conn.close()


def _terminate_request_process(process):
    if process is None or not process.is_alive():
        return
    process.terminate()
    process.join(0.5)
    if process.is_alive() and hasattr(process, "kill"):
        process.kill()
        process.join(0.5)


def _required_model_value(model_config, field_name):
    value = str(model_config.get(field_name, "") or "").strip()
    if not value:
        if field_name == "model":
            raise ValueError("模型配置缺少模型名称。")
        raise ValueError("模型配置缺少 {}。".format(field_name))
    return value


def _normalize_message_content(content):
    if isinstance(content, list):
        fragments = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                fragments.append(item.get("text", ""))
        content = "".join(fragments)
    return _strip_thinking_content(content)


def _strip_thinking_content(content):
    value = str(content or "")
    last_match = None
    for match in THINK_END_TAG_PATTERN.finditer(value):
        last_match = match
    if last_match is not None:
        value = value[last_match.end():]
    return value.strip()


def _extract_json_object(content):
    text = str(content or "").strip()
    if not text:
        raise ValueError("Model response content is empty.")
    last_error = ""
    for candidate in _json_object_candidates(text):
        try:
            return json.loads(candidate)
        except ValueError as exc:
            if not last_error:
                last_error = str(exc)
    message = "Model response does not contain a valid JSON object: {}".format(text[:200])
    if last_error:
        message = "{}; parser error: {}".format(message, last_error)
    raise ValueError(message)


def describe_retryable_model_response_error(error, phase="模型"):
    if isinstance(error, ModelRequestTimeoutError):
        return "{}请求超时".format(str(phase or "模型").strip() or "模型")
    if not is_retryable_model_response_error(error):
        return ""
    message = str(error or "")
    phase_name = str(phase or "模型").strip() or "模型"
    if "did not return candidate_translation" in message:
        return "{}未返回候选英文".format(phase_name)
    if "message content" in message or "content is empty" in message:
        return "{}未返回有效正文".format(phase_name)
    return "{}返回格式不规范".format(phase_name)


def is_retryable_model_response_error(error):
    if isinstance(error, ModelRequestTimeoutError):
        return True
    message = str(error or "")
    return any(marker in message for marker in RETRYABLE_MODEL_RESPONSE_MARKERS)


def model_response_debug_payload(error):
    return {
        "raw_response": str(getattr(error, "raw_response", "") or ""),
        "raw_content": str(getattr(error, "raw_content", "") or ""),
        "parse_error_detail": str(getattr(error, "parse_error_detail", "") or ""),
        "extracted_candidate_text": str(getattr(error, "extracted_candidate_text", "") or ""),
        "extracted_reason": str(getattr(error, "extracted_reason", "") or ""),
    }


def _json_object_candidates(text):
    seen = set()
    candidates = []
    values = [text, _extract_braced_object(text)]
    for value in values:
        normalized = _normalize_json_like_text(value)
        for candidate in (value, normalized, _extract_braced_object(normalized)):
            if not candidate:
                continue
            key = str(candidate)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
    return candidates


def _extract_braced_object(text):
    value = str(text or "").strip()
    if not value:
        return ""
    start = value.find("{")
    end = value.rfind("}")
    if start >= 0 and end > start:
        return value[start : end + 1]
    return ""


def _normalize_json_like_text(text):
    value = str(text or "").strip().replace("\ufeff", "")
    if not value:
        return ""
    fence_match = CODE_FENCE_PATTERN.match(value)
    if fence_match:
        value = fence_match.group(1).strip()
    value = value.translate(SMART_QUOTE_TRANSLATION)
    value = _escape_inner_quotes_in_json_like_text(value)
    value = TRAILING_COMMA_PATTERN.sub(r"\1", value)
    return value


def _escape_inner_quotes_in_json_like_text(text):
    value = str(text or "")
    if not value or '"' not in value:
        return value
    result = []
    stack = []
    in_string = False
    escape_next = False
    string_role = "value"
    for index, char in enumerate(value):
        if in_string:
            if escape_next:
                result.append(char)
                escape_next = False
                continue
            if char == "\\":
                result.append(char)
                escape_next = True
                continue
            if char == '"':
                next_char = _next_non_space_char(value, index + 1)
                if _is_valid_string_terminator(string_role, next_char):
                    result.append(char)
                    in_string = False
                    _mark_container_after_string(stack, string_role)
                else:
                    result.append('\\"')
                continue
            result.append(char)
            continue

        result.append(char)
        if char == '"':
            in_string = True
            escape_next = False
            string_role = _current_string_role(stack)
            continue
        if char.isspace():
            continue
        if char == "{":
            stack.append({"type": "object", "expect": "key_or_end"})
            continue
        if char == "[":
            stack.append({"type": "array", "expect": "value_or_end"})
            continue
        if char == ":":
            if stack and stack[-1]["type"] == "object":
                stack[-1]["expect"] = "value"
            continue
        if char == ",":
            if stack:
                stack[-1]["expect"] = "key" if stack[-1]["type"] == "object" else "value"
            continue
        if char == "}":
            if stack and stack[-1]["type"] == "object":
                stack.pop()
                _mark_parent_after_value(stack)
            continue
        if char == "]":
            if stack and stack[-1]["type"] == "array":
                stack.pop()
                _mark_parent_after_value(stack)
            continue
    return "".join(result)


def _next_non_space_char(text, start_index):
    value = str(text or "")
    index = int(start_index)
    while index < len(value):
        if not value[index].isspace():
            return value[index]
        index += 1
    return None


def _current_string_role(stack):
    if not stack:
        return "value"
    current = stack[-1]
    if current.get("type") == "object" and current.get("expect") in ("key", "key_or_end"):
        return "key"
    return "value"


def _is_valid_string_terminator(string_role, next_char):
    if string_role == "key":
        return next_char in (":", None)
    return next_char in (",", "}", "]", None)


def _mark_container_after_string(stack, string_role):
    if not stack:
        return
    current = stack[-1]
    if current.get("type") == "object":
        current["expect"] = "colon" if string_role == "key" else "after_value"
    elif current.get("type") == "array" and string_role == "value":
        current["expect"] = "after_value"


def _mark_parent_after_value(stack):
    if not stack:
        return
    current = stack[-1]
    if current.get("type") in ("object", "array"):
        current["expect"] = "after_value"


def _extract_debug_fields(text):
    value = _normalize_json_like_text(text)
    return {
        "candidate_translation": _extract_debug_field(value, "candidate_translation"),
        "reason": _extract_debug_field(value, "reason"),
    }


def _extract_debug_field(text, field_name):
    if not text:
        return ""
    field = re.escape(str(field_name or ""))
    for template in (JSON_STRING_FIELD_TEMPLATE, JSON_SINGLE_QUOTED_FIELD_TEMPLATE):
        match = re.search(template.format(field=field), text)
        if not match:
            continue
        try:
            return json.loads('"{}"'.format(match.group(1)))
        except ValueError:
            return match.group(1)
    line_match = re.search(LINE_FIELD_TEMPLATE.format(field=field), text)
    if not line_match:
        return ""
    value = line_match.group(1).strip().strip(",")
    if value[:1] == value[-1:] and value[:1] in ('"', "'"):
        value = value[1:-1]
    return value.strip()
