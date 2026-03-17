import tempfile
import unittest
from pathlib import Path

from zh_audit.po_rst_protection import protect_rst_text, validate_protected_candidate
from zh_audit.po_translation_workflow import PoTranslationSession


def _pass_review(**kwargs):
    return {
        "decision": "pass",
        "issues": [],
    }


class PoTranslationWorkflowTest(unittest.TestCase):
    def test_validate_protected_candidate_detects_anchor_change(self):
        protected = protect_rst_text('详见 :ref:`增加主机<5.2.1-addHost>` 章节。')
        issue = validate_protected_candidate(
            protected,
            'See :ref:`Add Host<other-anchor>` for details.',
        )
        self.assertEqual(issue, "候选改动了 rst role target")

    def test_po_translation_session_skips_accurate_existing_msgstr(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Project-Id-Version: Demo\\\\n"\n'
                '\n'
                '#: ../../source/demo.rst:1\n'
                'msgid "创建全新虚拟机"\n'
                'msgstr "Create a new VM"\n',
                encoding="utf-8",
            )

            session = PoTranslationSession(
                po_path=po_path,
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 200},
                model_runner=lambda **kwargs: {
                    "verdict": "accurate",
                    "slot_translations": {},
                    "reason": "ok",
                },
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["status"], "done")
            self.assertEqual(snapshot["status"]["counts"]["skipped"], 1)
            self.assertEqual(snapshot["pending_items"], [])

    def test_po_translation_session_fills_empty_msgstr_after_accept(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Project-Id-Version: Demo\\\\n"\n'
                '\n'
                '#: ../../source/demo.rst:4\n'
                'msgid "在当前页面，选中待使用的主机，单击“操作”栏中的【|view2|】按钮，可查看本地存储池详情。"\n'
                'msgstr ""\n',
                encoding="utf-8",
            )

            def fake_model(**kwargs):
                protected = kwargs["protected_source"]
                translations = {}
                for slot in protected["translatable_slots"]:
                    if slot["source_text"].endswith("【"):
                        translations[slot["slot_id"]] = 'On the current page, select the host to be used and click ['
                    else:
                        translations[slot["slot_id"]] = '] in the "Operation" column to view the details of the local storage pool.'
                return {
                    "verdict": "needs_update",
                    "slot_translations": translations,
                    "reason": "ok",
                }

            session = PoTranslationSession(
                po_path=po_path,
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 200},
                model_runner=fake_model,
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["counts"]["pending"], 1)
            pending = snapshot["pending_items"][0]
            self.assertIn("|view2|", pending["candidate_text"])

            accepted = session.accept(pending["id"])
            self.assertEqual(accepted["status"]["counts"]["accepted"], 1)
            self.assertEqual(accepted["status"]["counts"]["filled"], 1)
            content = po_path.read_text(encoding="utf-8")
            self.assertIn('|view2|', content)
            self.assertIn('msgstr "On the current page, select the host to be used and click [|view2|] in the \\"Operation\\" column to view the details of the local storage pool."', content)

    def test_po_translation_session_retries_when_slot_translation_still_contains_chinese(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Project-Id-Version: Demo\\\\n"\n'
                '\n'
                '#: ../../source/demo.rst:5\n'
                'msgid "详见 :ref:`增加主机<5.2.1-addHost>` 章节。"\n'
                'msgstr ""\n',
                encoding="utf-8",
            )

            calls = []

            def fake_model(**kwargs):
                calls.append(kwargs)
                protected = kwargs["protected_source"]
                translations = {}
                for slot in protected["translatable_slots"]:
                    if slot["type"] == "role_label":
                        translations[slot["slot_id"]] = "Add Host" if kwargs.get("extra_prompt") else "增加主机"
                    elif slot["source_text"].startswith("详见"):
                        translations[slot["slot_id"]] = "See "
                    else:
                        translations[slot["slot_id"]] = " section."
                return {
                    "verdict": "needs_update",
                    "slot_translations": translations,
                    "reason": "ok",
                }

            session = PoTranslationSession(
                po_path=po_path,
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 200},
                model_runner=fake_model,
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["counts"]["pending"], 1)
            self.assertIn("Add Host", snapshot["pending_items"][0]["candidate_text"])
            self.assertGreaterEqual(len(calls), 2)
            self.assertIn("候选仍含中文", calls[-1]["extra_prompt"])

