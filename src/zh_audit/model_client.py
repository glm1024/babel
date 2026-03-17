from __future__ import absolute_import

import json
import re
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
TRAILING_COMMA_PATTERN = re.compile(r",(\s*[}\]])")
CODE_FENCE_PATTERN = re.compile(r"^\s*```(?:json)?\s*([\s\S]*?)\s*```\s*$", re.IGNORECASE)
RETRYABLE_MODEL_RESPONSE_MARKERS = (
    "模型响应不是合法 JSON",
    "模型响应中缺少 message content",
    "模型响应 JSON 必须是对象",
    "Model response content is empty.",
    "Model response does not contain a valid JSON object",
    "Model did not return candidate_translation",
)


class ModelResponseFormatError(ValueError):
    def __init__(self, message, *, raw_response="", raw_content=""):
        ValueError.__init__(self, message)
        self.raw_response = str(raw_response or "")
        self.raw_content = str(raw_content or "")


def call_openai_compatible_json(model_config, system_prompt, user_prompt, max_tokens=None, timeout=90):
    payload = {
        "model": _required_model_value(model_config, "model"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": int(max_tokens or model_config.get("max_tokens") or 256),
    }
    raw = _post_chat_completion(model_config, payload, timeout=timeout)
    try:
        payload = json.loads(raw)
    except ValueError:
        raise ModelResponseFormatError(
            "模型响应不是合法 JSON：{}".format(raw[:200]),
            raw_response=raw,
        )
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ModelResponseFormatError(
            "模型响应中缺少 message content。",
            raw_response=raw,
        )
    if isinstance(content, list):
        fragments = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                fragments.append(item.get("text", ""))
        content = "".join(fragments)
    try:
        parsed = _extract_json_object(content)
    except ValueError as exc:
        raise ModelResponseFormatError(
            str(exc),
            raw_response=raw,
            raw_content=content,
        )
    if not isinstance(parsed, dict):
        raise ModelResponseFormatError(
            "模型响应 JSON 必须是对象。",
            raw_response=raw,
            raw_content=content,
        )
    return parsed


def probe_openai_compatible_model(model_config, timeout=15):
    payload = {
        "model": _required_model_value(model_config, "model"),
        "messages": [
            {"role": "system", "content": "You are a connectivity probe."},
            {"role": "user", "content": "Reply with OK."},
        ],
        "temperature": 0,
        "max_tokens": 4,
    }
    raw = _post_chat_completion(model_config, payload, timeout=timeout)
    try:
        response = json.loads(raw)
    except ValueError:
        raise ValueError("连通性测试失败：模型接口返回的不是合法 JSON。")
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("连通性测试失败：模型接口返回中缺少 choices.message.content。")
    if isinstance(content, list):
        content = "".join(
            item.get("text", "") for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    return {
        "message": str(content or "").strip() or "OK",
    }


def _post_chat_completion(model_config, payload, timeout):
    base_url = str(model_config.get("base_url", "") or "").rstrip("/")
    api_key = str(model_config.get("api_key", "") or "").strip()
    if not base_url:
        raise ValueError("模型配置缺少 Base URL。")
    if not api_key:
        raise ValueError("模型配置缺少 API Key。")

    url = "{}/chat/completions".format(base_url)
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
    except urllib_error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise ValueError("连通性测试失败：模型接口返回 HTTP {}。{}".format(exc.code, details[:300]))
    except urllib_error.URLError as exc:
        raise ValueError("连通性测试失败：无法访问模型地址 {}。{}".format(url, exc))
    return raw


def _required_model_value(model_config, field_name):
    value = str(model_config.get(field_name, "") or "").strip()
    if not value:
        if field_name == "model":
            raise ValueError("模型配置缺少模型名称。")
        raise ValueError("模型配置缺少 {}。".format(field_name))
    return value


def _extract_json_object(content):
    text = str(content or "").strip()
    if not text:
        raise ValueError("Model response content is empty.")
    for candidate in _json_object_candidates(text):
        try:
            return json.loads(candidate)
        except ValueError:
            pass
    raise ValueError("Model response does not contain a valid JSON object: {}".format(text[:200]))


def describe_retryable_model_response_error(error, phase="模型"):
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
    message = str(error or "")
    return any(marker in message for marker in RETRYABLE_MODEL_RESPONSE_MARKERS)


def model_response_debug_payload(error):
    return {
        "raw_response": str(getattr(error, "raw_response", "") or ""),
        "raw_content": str(getattr(error, "raw_content", "") or ""),
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
    value = TRAILING_COMMA_PATTERN.sub(r"\1", value)
    return value
