import unittest

from zh_audit.single_translation import translate_single_text
from zh_audit.terminology_xlsx import normalize_terminology_catalog


def _pass_plain_review(**kwargs):
    return {
        "decision": "pass",
        "issues": [],
    }


class SingleTranslationTest(unittest.TestCase):
    def test_exact_glossary_hit_returns_without_model(self):
        result = translate_single_text(
            source_text="主机组",
            glossary={"主机组": "host group"},
            model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
            plain_model_runner=lambda **kwargs: (_ for _ in ()).throw(AssertionError("model should not run")),
            plain_reviewer_runner=_pass_plain_review,
        )

        self.assertEqual(result["status"], "done")
        self.assertEqual(result["mode"], "plain")
        self.assertEqual(result["translated_text"], "Host group")
        self.assertEqual(result["validation_state"], "passed")

    def test_plain_mode_retries_until_locked_term_and_placeholder_pass(self):
        attempts = []

        def plain_model_runner(**kwargs):
            attempts.append(kwargs.get("extra_prompt", ""))
            if kwargs.get("extra_prompt"):
                return {
                    "verdict": "needs_update",
                    "candidate_translation": "Create peer connection: {0}",
                    "reason": "已按术语修正。",
                }
            return {
                "verdict": "needs_update",
                "candidate_translation": "Create link: {0}",
                "reason": "初次生成。",
            }

        result = translate_single_text(
            source_text="创建对等连接：{0}",
            glossary={"对等连接": "peer connection"},
            model_config={
                "base_url": "http://example/v1",
                "api_key": "sk",
                "model": "demo",
                "max_tokens": 100,
                "execution_strategy": "standard",
            },
            plain_model_runner=plain_model_runner,
            plain_reviewer_runner=_pass_plain_review,
        )

        self.assertEqual(result["mode"], "plain")
        self.assertEqual(result["translated_text"], "Create peer connection: {0}")
        self.assertEqual(result["validation_state"], "passed")
        self.assertGreaterEqual(len(attempts), 2)

    def test_plain_mode_default_think_fast_skips_reviewer_and_limits_to_one_attempt(self):
        attempts = []
        review_calls = []

        def plain_model_runner(**kwargs):
            attempts.append(kwargs)
            return {
                "verdict": "needs_update",
                "candidate_translation": "创建连接",
                "reason": "初次生成。",
            }

        result = translate_single_text(
            source_text="创建连接",
            glossary={},
            model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
            plain_model_runner=plain_model_runner,
            plain_reviewer_runner=lambda **kwargs: review_calls.append(kwargs) or _pass_plain_review(**kwargs),
        )

        self.assertEqual(result["mode"], "plain")
        self.assertEqual(result["validation_state"], "failed")
        self.assertEqual(result["translated_text"], "创建连接")
        self.assertEqual(len(attempts), 1)
        self.assertEqual(review_calls, [])
        self.assertIn("已重试 1 次仍未通过", result["validation_message"])

    def test_plain_mode_preserves_multiple_placeholder_forms(self):
        result = translate_single_text(
            source_text="删除资源池 %s，所属资源组 ${name}",
            glossary={"资源池": "resource pool", "资源组": "resource group"},
            model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
            plain_model_runner=lambda **kwargs: {
                "verdict": "needs_update",
                "candidate_translation": "Delete resource pool %s, resource group ${name}",
                "reason": "ok",
            },
            plain_reviewer_runner=_pass_plain_review,
        )

        self.assertEqual(result["validation_state"], "passed")
        self.assertIn("%s", result["translated_text"])
        self.assertIn("${name}", result["translated_text"])

    def test_rst_mode_translates_protected_slots(self):
        def rst_model_runner(**kwargs):
            slots = kwargs["protected_source"]["translatable_slots"]
            return {
                "verdict": "needs_update",
                "slot_translations": {
                    slots[0]["slot_id"]: "Click ",
                    slots[1]["slot_id"]: "OK",
                    slots[2]["slot_id"]: " button.",
                },
                "reason": "ok",
            }

        result = translate_single_text(
            source_text="单击 :guilabel:`确定` 按钮。",
            glossary=normalize_terminology_catalog({}),
            model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
            plain_model_runner=lambda **kwargs: (_ for _ in ()).throw(AssertionError("plain runner should not run")),
            plain_reviewer_runner=_pass_plain_review,
            rst_model_runner=rst_model_runner,
            rst_reviewer_runner=lambda **kwargs: {"decision": "pass", "issues": []},
        )

        self.assertEqual(result["mode"], "rst")
        self.assertEqual(result["validation_state"], "passed")
        self.assertEqual(result["translated_text"], 'Click :guilabel:`OK` button.')

    def test_unsupported_rst_returns_error(self):
        with self.assertRaises(ValueError) as context:
            translate_single_text(
                source_text="请参考 `未闭合标记",
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
                plain_model_runner=lambda **kwargs: {"verdict": "needs_update", "candidate_translation": "unused", "reason": "ok"},
                plain_reviewer_runner=_pass_plain_review,
                rst_model_runner=lambda **kwargs: {"verdict": "needs_update", "slot_translations": {}, "reason": "ok"},
                rst_reviewer_runner=lambda **kwargs: {"decision": "pass", "issues": []},
            )

        self.assertIn("rst", str(context.exception).lower())

    def test_retry_exhaustion_returns_best_candidate_and_failed_validation(self):
        result = translate_single_text(
            source_text="创建连接",
            glossary={},
            model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 100},
            plain_model_runner=lambda **kwargs: {
                "verdict": "needs_update",
                "candidate_translation": "创建连接",
                "reason": "ok",
            },
            plain_reviewer_runner=_pass_plain_review,
        )

        self.assertEqual(result["status"], "done")
        self.assertEqual(result["validation_state"], "failed")
        self.assertEqual(result["translated_text"], "创建连接")
        self.assertIn("已重试", result["validation_message"])


if __name__ == "__main__":
    unittest.main()
