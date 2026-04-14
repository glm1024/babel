import json
import unittest
from unittest import mock

from zh_audit.model_client import (
    ModelResponseFormatError,
    _extract_json_object,
    call_openai_compatible_json,
    probe_openai_compatible_model,
)


class ModelClientTest(unittest.TestCase):
    def test_extract_json_object_tolerates_smart_quotes(self):
        parsed = _extract_json_object(
            '{"verdict": “needs_update”, "candidate_translation": “The adapter server cannot process the request.”, "reason": “ok”}'
        )

        self.assertEqual(parsed["verdict"], "needs_update")
        self.assertEqual(parsed["candidate_translation"], "The adapter server cannot process the request.")
        self.assertEqual(parsed["reason"], "ok")

    def test_extract_json_object_tolerates_markdown_fence_and_trailing_comma(self):
        parsed = _extract_json_object(
            """```json
            {
              "decision": "pass",
              "issues": [],
            }
            ```"""
        )

        self.assertEqual(parsed["decision"], "pass")
        self.assertEqual(parsed["issues"], [])

    def test_call_openai_compatible_json_uses_content_after_think_tag(self):
        raw_response = json.dumps(
            {"choices": [{"message": {"content": 'Thinking Process:\n1. Analyze\n</think>\n{"decision":"pass","issues":[]}'}}]}
        )
        with mock.patch("zh_audit.model_client._post_chat_completion", return_value=raw_response):
            parsed = call_openai_compatible_json(
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo"},
                system_prompt="system",
                user_prompt="user",
            )

        self.assertEqual(parsed["decision"], "pass")
        self.assertEqual(parsed["issues"], [])

    def test_call_openai_compatible_json_ignores_json_like_thinking_content(self):
        raw_response = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": 'Thinking Process:\n{"draft": true}\n</think>\n{"decision":"pass","issues":[]}'
                        }
                    }
                ]
            }
        )
        with mock.patch("zh_audit.model_client._post_chat_completion", return_value=raw_response):
            parsed = call_openai_compatible_json(
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo"},
                system_prompt="system",
                user_prompt="user",
            )

        self.assertEqual(parsed["decision"], "pass")
        self.assertEqual(parsed["issues"], [])

    def test_call_openai_compatible_json_tolerates_fenced_json_after_think_tag(self):
        raw_response = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": 'Thinking Process:\n1. Analyze\n</think>\n```json\n{"decision":"pass","issues":[],}\n```'
                        }
                    }
                ]
            }
        )
        with mock.patch("zh_audit.model_client._post_chat_completion", return_value=raw_response):
            parsed = call_openai_compatible_json(
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo"},
                system_prompt="system",
                user_prompt="user",
            )

        self.assertEqual(parsed["decision"], "pass")
        self.assertEqual(parsed["issues"], [])

    def test_call_openai_compatible_json_exposes_raw_content_on_invalid_inner_json(self):
        raw_response = (
            '{"choices":[{"message":{"content":"verdict=needs_update\\n'
            'candidate_translation=AZ cannot be empty.\\n'
            'reason=现有英文过于简略。"}}]}'
        )
        with mock.patch("zh_audit.model_client._post_chat_completion", return_value=raw_response):
            with self.assertRaises(ModelResponseFormatError) as ctx:
                call_openai_compatible_json(
                    model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo"},
                    system_prompt="system",
                    user_prompt="user",
                )

        self.assertIn("valid JSON object", str(ctx.exception))
        self.assertIn("candidate_translation=AZ cannot be empty.", ctx.exception.raw_content)
        self.assertIn('"choices"', ctx.exception.raw_response)
        self.assertEqual(ctx.exception.extracted_candidate_text, "AZ cannot be empty.")
        self.assertEqual(ctx.exception.extracted_reason, "现有英文过于简略。")
        self.assertIn("valid JSON object", ctx.exception.parse_error_detail)

    def test_call_openai_compatible_json_exposes_sanitized_raw_content_after_think_tag(self):
        raw_response = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": "Thinking Process:\n1. Analyze\ncandidate_translation=should not leak\n</think>\nnot json"
                        }
                    }
                ]
            }
        )
        with mock.patch("zh_audit.model_client._post_chat_completion", return_value=raw_response):
            with self.assertRaises(ModelResponseFormatError) as ctx:
                call_openai_compatible_json(
                    model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo"},
                    system_prompt="system",
                    user_prompt="user",
                )

        self.assertEqual(ctx.exception.raw_content, "not json")
        self.assertNotIn("Thinking Process", ctx.exception.raw_content)
        self.assertEqual(ctx.exception.extracted_candidate_text, "")
        self.assertIn("not json", ctx.exception.parse_error_detail)

    def test_call_openai_compatible_json_treats_empty_content_after_think_tag_as_empty(self):
        raw_response = json.dumps(
            {"choices": [{"message": {"content": "Thinking Process:\n1. Analyze\n</think>\n\n"}}]}
        )
        with mock.patch("zh_audit.model_client._post_chat_completion", return_value=raw_response):
            with self.assertRaises(ModelResponseFormatError) as ctx:
                call_openai_compatible_json(
                    model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo"},
                    system_prompt="system",
                    user_prompt="user",
                )

        self.assertEqual(ctx.exception.raw_content, "")
        self.assertIn("content is empty", ctx.exception.parse_error_detail)

    def test_probe_openai_compatible_model_returns_content_after_think_tag(self):
        raw_response = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": "Thinking Process\n"},
                                {"type": "text", "text": "</think>\nOK"},
                            ]
                        }
                    }
                ]
            }
        )
        with mock.patch("zh_audit.model_client._post_chat_completion", return_value=raw_response):
            result = probe_openai_compatible_model(
                {"base_url": "http://example/v1", "api_key": "sk", "model": "demo"}
            )

        self.assertEqual(result["message"], "OK")


if __name__ == "__main__":
    unittest.main()
