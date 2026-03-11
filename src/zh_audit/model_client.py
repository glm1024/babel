from __future__ import absolute_import

import json
from urllib import error as urllib_error
from urllib import request as urllib_request


def call_openai_compatible_json(model_config, system_prompt, user_prompt, max_tokens=None, timeout=90):
    base_url = str(model_config.get("base_url", "") or "").rstrip("/")
    api_key = str(model_config.get("api_key", "") or "").strip()
    model = str(model_config.get("model", "") or "").strip()
    if not base_url or not api_key or not model:
        raise ValueError("Model config must include base_url, api_key and model.")

    url = "{}/chat/completions".format(base_url)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": int(max_tokens or model_config.get("max_tokens") or 256),
    }
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
        raise ValueError("Model request failed with HTTP {}: {}".format(exc.code, details))
    except urllib_error.URLError as exc:
        raise ValueError("Model request failed: {}".format(exc))

    try:
        payload = json.loads(raw)
    except ValueError:
        raise ValueError("Model response is not valid JSON: {}".format(raw[:200]))
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("Model response does not contain message content.")
    if isinstance(content, list):
        fragments = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                fragments.append(item.get("text", ""))
        content = "".join(fragments)
    parsed = _extract_json_object(content)
    if not isinstance(parsed, dict):
        raise ValueError("Model response JSON must be an object.")
    return parsed


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
