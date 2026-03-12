from __future__ import absolute_import

import json
from urllib import error as urllib_error
from urllib import request as urllib_request


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
        raise ValueError("模型响应不是合法 JSON：{}".format(raw[:200]))
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("模型响应中缺少 message content。")
    if isinstance(content, list):
        fragments = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                fragments.append(item.get("text", ""))
        content = "".join(fragments)
    parsed = _extract_json_object(content)
    if not isinstance(parsed, dict):
        raise ValueError("模型响应 JSON 必须是对象。")
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
    try:
        return json.loads(text)
    except ValueError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except ValueError:
            pass
    raise ValueError("Model response does not contain a valid JSON object: {}".format(text[:200]))
