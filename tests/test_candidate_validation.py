import unittest

from zh_audit.candidate_validation import normalize_review_result


class CandidateValidationTest(unittest.TestCase):
    def test_normalize_review_result_ignores_case_only_terminology_issue(self):
        normalized = normalize_review_result(
            {
                "decision": "fail",
                "issues": ["术语不一致：'镜像'应翻译为'Image'，但'Image'未大写"],
            },
            source_text="删除镜像",
            target_text="delete image",
            candidate_text="delete image",
        )

        self.assertEqual(normalized["decision"], "pass")
        self.assertEqual(normalized["issues"], [])

    def test_normalize_review_result_keeps_real_terminology_mismatch_issue(self):
        normalized = normalize_review_result(
            {
                "decision": "fail",
                "issues": ["术语不一致：'镜像'应翻译为'Image'，但候选文本使用了'snapshot'"],
            },
            source_text="删除镜像",
            target_text="delete image",
            candidate_text="delete snapshot",
        )

        self.assertEqual(normalized["decision"], "fail")
        self.assertEqual(normalized["issues"], ["术语不一致：'镜像'应翻译为'Image'，但候选文本使用了'snapshot'"])
