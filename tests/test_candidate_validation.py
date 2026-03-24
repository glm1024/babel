import unittest

from zh_audit.candidate_validation import normalize_english_punctuation, normalize_review_result


class CandidateValidationTest(unittest.TestCase):
    def test_normalize_english_punctuation_rewrites_common_cjk_symbols(self):
        normalized = normalize_english_punctuation('单击“确定”按钮（推荐）……【立即创建】')
        self.assertEqual(normalized, '单击"确定"按钮(推荐)...[立即创建]')

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

    def test_normalize_review_result_ignores_issue_when_expected_term_already_exists(self):
        normalized = normalize_review_result(
            {
                "decision": "fail",
                "issues": [
                    {
                        "code": "missing_term",
                        "message": "未准确翻译，'云物理机'应为'Cloud Physical Server'",
                        "expected_term": "Cloud Physical Server",
                    }
                ],
            },
            source_text="删除云物理机",
            candidate_text="Delete Cloud Physical Server instance",
        )

        self.assertEqual(normalized["decision"], "pass")
        self.assertEqual(normalized["issues"], [])

    def test_normalize_review_result_downgrades_style_suggestions_to_warnings(self):
        normalized = normalize_review_result(
            {
                "decision": "fail",
                "issues": [
                    {
                        "code": "style",
                        "message": "表达可更自然，建议调整措辞",
                        "severity": "warning",
                    }
                ],
            },
            source_text="删除目录",
            candidate_text="Delete directory",
        )

        self.assertEqual(normalized["decision"], "pass")
        self.assertEqual(normalized["issues"], [])
        self.assertEqual(normalized["warnings"], ["表达可更自然，建议调整措辞"])

    def test_normalize_review_result_normalizes_english_term_issue_to_chinese(self):
        normalized = normalize_review_result(
            {
                "decision": "fail",
                "issues": [
                    {
                        "code": "terminology",
                        "message": "The term 'Floating IP' should be 'EIP' as per standard terminology.",
                        "expected_term": "EIP",
                    }
                ],
            },
            source_text="云主机解绑浮动ip",
            candidate_text="Elastic Compute Service unbind Floating IP",
        )

        self.assertEqual(normalized["decision"], "fail")
        self.assertEqual(normalized["issues"], ["术语不一致：应使用'EIP'"])
