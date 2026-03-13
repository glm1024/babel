import unittest

from zh_audit.model_client import _extract_json_object


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


if __name__ == "__main__":
    unittest.main()
