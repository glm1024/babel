import tempfile
import unittest
from pathlib import Path

from zh_audit.po_rst_protection import protect_rst_text, validate_protected_candidate
from zh_audit.po_translation_workflow import (
    PoTranslationSession,
    build_po_translation_system_prompt,
    build_po_translation_review_system_prompt,
    build_po_translation_review_user_prompt,
)
from zh_audit.terminology_xlsx import normalize_terminology_catalog


def _pass_review(**kwargs):
    return {
        "decision": "pass",
        "issues": [],
    }


class PoTranslationWorkflowTest(unittest.TestCase):
    def test_po_translation_session_processing_log_keeps_recent_1000_events(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Project-Id-Version: Demo\\\\n"\n'
                '\n'
                '#: ../../source/demo.rst:1\n'
                'msgid "创建全新虚拟机"\n'
                'msgstr ""\n',
                encoding="utf-8",
            )

            session = PoTranslationSession(
                po_path=po_path,
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 200},
                model_runner=lambda **kwargs: {"verdict": "accurate", "slot_translations": {}, "reason": "ok"},
                reviewer_runner=_pass_review,
            )

            for index in range(1005):
                session._push_event(
                    "测试",
                    {"entry_id": "po-{}".format(index), "references": [], "source_text": "源文案 {}".format(index)},
                    "译文 {}".format(index),
                )

            self.assertEqual(len(session.events), 1000)
            self.assertEqual(session.events[0]["entry_id"], "po-1004")
            self.assertEqual(session.events[-1]["entry_id"], "po-5")

    def test_po_translation_review_prompt_ignores_previous_english_value(self):
        prompt = build_po_translation_review_system_prompt()
        self.assertIn("Ignore any previous English wording.", prompt)
        self.assertNotIn("current_target_text", prompt)
        self.assertIn(
            "issues must be either an array of short Simplified Chinese strings or an array of objects with keys code, message, severity, evidence, and expected_term.",
            prompt,
        )
        self.assertIn("Do not report that a term should be X if candidate_text already contains X.", prompt)
        self.assertIn("Do not treat style-only suggestions such as 'could be more natural' as hard failures.", prompt)
        self.assertIn("keeps Chinese-style punctuation in otherwise English text", prompt)

    def test_po_translation_system_prompt_requires_english_punctuation(self):
        prompt = build_po_translation_system_prompt()
        self.assertIn("Use standard half-width English punctuation inside translated English text.", prompt)

    def test_po_translation_review_user_prompt_does_not_include_current_target_text(self):
        prompt = build_po_translation_review_user_prompt(
            entry_id="po-1",
            references=["../../source/demo.rst:1"],
            source_text="单击“是”按钮。",
            candidate_text='Click the "Yes" button.',
            protected_source={"summary": "rst protected", "frontend_glossary_enabled": False, "frontend_ui_slots": [], "active_frontend_terms": []},
            locked_terms=[{"source": "按钮", "target": "button"}],
            target_missing=True,
            extra_prompt="",
        )

        self.assertIn('"candidate_text": "Click the \\"Yes\\" button."', prompt)
        self.assertNotIn("current_target_text", prompt)

    def test_validate_protected_candidate_detects_anchor_change(self):
        protected = protect_rst_text('详见 :ref:`增加主机<5.2.1-addHost>` 章节。')
        issue = validate_protected_candidate(
            protected,
            'See :ref:`Add Host<other-anchor>` for details.',
        )
        self.assertEqual(issue, "候选改动了 rst role target")

    def test_protect_rst_text_supports_single_backtick_interpreted_text(self):
        protected = protect_rst_text("密码必须包含数字、字母和特殊字符 (`!@#$%^&*?._`)，长度范围为8~30字符。")
        self.assertTrue(protected["supported"])
        self.assertEqual(
            [slot["type"] for slot in protected["slots"]],
            ["text", "interpreted_text", "text"],
        )
        self.assertEqual(
            [slot["type"] for slot in protected["translatable_slots"]],
            ["text", "text"],
        )

    def test_protect_rst_text_prefers_reference_and_link_over_interpreted_text(self):
        reference = protect_rst_text("详见 `快速入门`_。")
        self.assertTrue(reference["supported"])
        self.assertEqual(
            [slot["type"] for slot in reference["slots"]],
            ["text", "reference_label", "text"],
        )

        link = protect_rst_text("访问 `产品文档 <index.html>`_。")
        self.assertTrue(link["supported"])
        self.assertEqual(
            [slot["type"] for slot in link["slots"]],
            ["text", "link_label", "text"],
        )

    def test_protect_rst_text_supports_directive_argument_translation(self):
        protected = protect_rst_text(".. note:: 这是重要说明")
        self.assertTrue(protected["supported"])
        self.assertEqual(
            [slot["type"] for slot in protected["slots"]],
            ["directive_prefix", "directive_argument"],
        )
        self.assertEqual(
            [slot["type"] for slot in protected["translatable_slots"]],
            ["directive_argument"],
        )

    def test_validate_protected_candidate_rejects_non_translatable_directive_argument_change(self):
        protected = protect_rst_text(".. image:: /static/demo.png")
        issue = validate_protected_candidate(protected, ".. image:: /static/other.png")
        self.assertEqual(issue, "候选改动了 rst 指令参数")

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

    def test_po_translation_session_copies_non_chinese_msgid_into_empty_msgstr(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Project-Id-Version: Demo\\\\n"\n'
                '\n'
                '#: ../../source/demo.rst:2\n'
                'msgid "Elastic Compute Service"\n'
                'msgstr ""\n',
                encoding="utf-8",
            )

            session = PoTranslationSession(
                po_path=po_path,
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 200},
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "slot_translations": {},
                    "reason": "ok",
                },
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["status"], "done")
            self.assertEqual(snapshot["status"]["counts"]["accepted"], 1)
            self.assertEqual(snapshot["status"]["counts"]["filled"], 1)
            self.assertEqual(snapshot["status"]["counts"]["skipped"], 0)
            self.assertIn('msgstr "Elastic Compute Service"', po_path.read_text(encoding="utf-8"))

    def test_po_translation_session_overwrites_existing_msgstr_with_non_chinese_msgid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Project-Id-Version: Demo\\\\n"\n'
                '\n'
                '#: ../../source/demo.rst:3\n'
                'msgid "Floating IP"\n'
                'msgstr "Old translation"\n',
                encoding="utf-8",
            )

            session = PoTranslationSession(
                po_path=po_path,
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 200},
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "slot_translations": {},
                    "reason": "ok",
                },
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            snapshot = session.snapshot()
            self.assertEqual(snapshot["status"]["status"], "done")
            self.assertEqual(snapshot["status"]["counts"]["accepted"], 1)
            self.assertEqual(snapshot["status"]["counts"]["updated"], 1)
            self.assertEqual(snapshot["status"]["counts"]["skipped"], 0)
            self.assertIn('msgstr "Floating IP"', po_path.read_text(encoding="utf-8"))

    def test_po_translation_session_handles_single_backtick_rst_without_skip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Project-Id-Version: Demo\\\\n"\n'
                '\n'
                '#: ../../source/demo.rst:3\n'
                'msgid "密码必须包含数字、字母和特殊字符 (`!@#$%^&*?._`)，长度范围为8~30字符。"\n'
                'msgstr ""\n',
                encoding="utf-8",
            )

            def fake_model(**kwargs):
                slots = kwargs["protected_source"]["translatable_slots"]
                return {
                    "verdict": "needs_update",
                    "slot_translations": {
                        slots[0]["slot_id"]: "The password must contain digits, letters, and special characters (",
                        slots[1]["slot_id"]: "), and must be 8 to 30 characters long.",
                    },
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
            self.assertEqual(snapshot["status"]["counts"]["unsupported"], 0)
            self.assertEqual(snapshot["status"]["counts"]["pending"], 1)
            pending = snapshot["pending_items"][0]
            self.assertIn("`!@#$%^&*?._`", pending["candidate_text"])
            self.assertNotIn("已跳过：rst 结构暂不支持", [item["label"] for item in snapshot["events"]])

    def test_po_translation_session_normalizes_cjk_punctuation_in_slot_translation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Project-Id-Version: Demo\\\\n"\n'
                '\n'
                '#: ../../source/demo.rst:3\n'
                'msgid "单击“确定”按钮。"\n'
                'msgstr ""\n',
                encoding="utf-8",
            )

            def fake_model(**kwargs):
                slots = kwargs["protected_source"]["translatable_slots"]
                return {
                    "verdict": "needs_update",
                    "slot_translations": {
                        slots[0]["slot_id"]: 'Click “OK” button。',
                    },
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

            pending = session.snapshot()["pending_items"][0]
            self.assertEqual(pending["candidate_text"], 'Click "OK" button.')

    def test_po_translation_session_normalizes_locked_term_case_mid_sentence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Project-Id-Version: Demo\\\\n"\n'
                '\n'
                '#: ../../source/demo.rst:3\n'
                'msgid "裸金属服务器名称超过最大长度。"\n'
                'msgstr ""\n',
                encoding="utf-8",
            )

            def fake_model(**kwargs):
                slots = kwargs["protected_source"]["translatable_slots"]
                return {
                    "verdict": "needs_update",
                    "slot_translations": {
                        slots[0]["slot_id"]: "The Bare Metal Server name exceeds the maximum length.",
                    },
                    "reason": "ok",
                }

            session = PoTranslationSession(
                po_path=po_path,
                glossary={"裸金属服务器": "Bare Metal Server"},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 200},
                model_runner=fake_model,
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            pending = session.snapshot()["pending_items"][0]
            self.assertEqual(pending["candidate_text"], "The bare metal server name exceeds the maximum length.")

    def test_po_translation_session_normalizes_exact_glossary_term_case_for_sentence_start(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Project-Id-Version: Demo\\\\n"\n'
                '\n'
                '#: ../../source/demo.rst:3\n'
                'msgid "裸金属服务器"\n'
                'msgstr ""\n',
                encoding="utf-8",
            )

            session = PoTranslationSession(
                po_path=po_path,
                glossary={"裸金属服务器": "Bare Metal Server"},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 200},
                model_runner=lambda **kwargs: (_ for _ in ()).throw(AssertionError("model should not be called")),
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            self.assertIn('msgstr "Bare metal server"', po_path.read_text(encoding="utf-8"))

    def test_po_translation_session_accept_writes_unescaped_quotes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Project-Id-Version: Demo\\\\n"\n'
                '\n'
                '#: ../../source/demo.rst:3\n'
                'msgid "单击“确定”按钮。"\n'
                'msgstr ""\n',
                encoding="utf-8",
            )

            def fake_model(**kwargs):
                slots = kwargs["protected_source"]["translatable_slots"]
                return {
                    "verdict": "needs_update",
                    "slot_translations": {
                        slots[0]["slot_id"]: 'Click "OK" button.',
                    },
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

            pending = session.snapshot()["pending_items"][0]
            session.accept(pending["id"])

            content = po_path.read_text(encoding="utf-8")
            self.assertIn('msgstr "Click "OK" button."\n', content)
            self.assertNotIn('\\"OK\\"', content)

    def test_po_translation_session_translates_directive_argument_without_skip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Project-Id-Version: Demo\\\\n"\n'
                '\n'
                '#: ../../source/demo.rst:4\n'
                'msgid ".. note:: 这是重要说明"\n'
                'msgstr ""\n',
                encoding="utf-8",
            )

            def fake_model(**kwargs):
                slots = kwargs["protected_source"]["translatable_slots"]
                return {
                    "verdict": "needs_update",
                    "slot_translations": {
                        slots[0]["slot_id"]: "This is an important note",
                    },
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
            self.assertEqual(snapshot["status"]["counts"]["unsupported"], 0)
            self.assertEqual(snapshot["status"]["counts"]["pending"], 1)
            pending = snapshot["pending_items"][0]
            self.assertEqual(pending["candidate_text"], ".. note:: This is an important note")

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
            self.assertIn('msgstr "On the current page, select the host to be used and click [|view2|] in the "Operation" column to view the details of the local storage pool."', content)

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

    def test_po_translation_session_ignores_frontend_terms_without_ui_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Project-Id-Version: Demo\\\\n"\n'
                '\n'
                '#: ../../source/demo.rst:6\n'
                'msgid "是否自动装机不能为空。"\n'
                'msgstr "register type can not be null."\n',
                encoding="utf-8",
            )
            glossary = normalize_terminology_catalog({"资源池": "resource pool"})
            glossary.add_entry(module="前端", source="是", target="Yes")
            glossary.add_entry(module="前端", source="否", target="No")

            session = PoTranslationSession(
                po_path=po_path,
                glossary=glossary,
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 200},
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "slot_translations": [
                        {
                            "slot_id": kwargs["protected_source"]["translatable_slots"][0]["slot_id"],
                            "translation": "Whether automatic provisioning is enabled cannot be null.",
                            "frontend_ui_context": False,
                        }
                    ],
                    "reason": "ok",
                },
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            pending = session.snapshot()["pending_items"][0]
            self.assertEqual(pending["validation_state"], "passed")
            self.assertFalse(pending["frontend_glossary_enabled"])
            self.assertEqual(pending["active_frontend_terms"], [])

    def test_po_translation_session_enables_frontend_terms_for_ui_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Project-Id-Version: Demo\\\\n"\n'
                '\n'
                '#: ../../source/demo.rst:7\n'
                'msgid "单击“是”按钮。"\n'
                'msgstr ""\n',
                encoding="utf-8",
            )
            glossary = normalize_terminology_catalog({"按钮": "button"})
            glossary.add_entry(module="前端", source="是", target="Yes")

            session = PoTranslationSession(
                po_path=po_path,
                glossary=glossary,
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 200},
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "slot_translations": [
                        {
                            "slot_id": kwargs["protected_source"]["translatable_slots"][0]["slot_id"],
                            "translation": 'Click the "Yes" button.',
                            "frontend_ui_context": True,
                        }
                    ],
                    "reason": "ok",
                },
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            pending = session.snapshot()["pending_items"][0]
            self.assertEqual(pending["validation_state"], "passed")
            self.assertTrue(pending["frontend_glossary_enabled"])
            self.assertEqual(pending["frontend_ui_slots"], ["slot_1"])
            self.assertEqual(pending["active_frontend_terms"][0]["source"], "是")

            restored = PoTranslationSession.from_saved_state(
                payload=session.save_state(),
                glossary=glossary,
                model_config=session.model_config,
                model_runner=session.model_runner,
                reviewer_runner=_pass_review,
            )
            restored_pending = restored.snapshot()["pending_items"][0]
            self.assertTrue(restored_pending["frontend_glossary_enabled"])
            self.assertEqual(restored_pending["frontend_ui_slots"], ["slot_1"])

    def test_po_translation_session_downgrades_style_review_suggestion_to_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Project-Id-Version: Demo\\\\n"\n'
                '\n'
                '#: ../../source/demo.rst:8\n'
                'msgid "删除目录"\n'
                'msgstr ""\n',
                encoding="utf-8",
            )

            session = PoTranslationSession(
                po_path=po_path,
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 200},
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "slot_translations": [
                        {
                            "slot_id": kwargs["protected_source"]["translatable_slots"][0]["slot_id"],
                            "translation": "Delete directory",
                            "frontend_ui_context": False,
                        }
                    ],
                    "reason": "ok",
                },
                reviewer_runner=lambda **kwargs: {
                    "decision": "fail",
                    "issues": [
                        {
                            "code": "style",
                            "message": "表达可更自然，建议调整措辞",
                            "severity": "warning",
                        }
                    ],
                },
            )
            session.start()
            session.run(lambda: False)

            pending = session.snapshot()["pending_items"][0]
            self.assertEqual(pending["validation_state"], "passed")
            self.assertTrue(pending["can_accept"])
            self.assertEqual(pending["warnings"], ["表达可更自然，建议调整措辞"])

    def test_po_translation_session_ignores_expected_term_issue_when_term_already_present(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Project-Id-Version: Demo\\\\n"\n'
                '\n'
                '#: ../../source/demo.rst:9\n'
                'msgid "删除云物理机"\n'
                'msgstr ""\n',
                encoding="utf-8",
            )

            session = PoTranslationSession(
                po_path=po_path,
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 200},
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "slot_translations": [
                        {
                            "slot_id": kwargs["protected_source"]["translatable_slots"][0]["slot_id"],
                            "translation": "Delete Cloud Physical Server instance",
                            "frontend_ui_context": False,
                        }
                    ],
                    "reason": "ok",
                },
                reviewer_runner=lambda **kwargs: {
                    "decision": "fail",
                    "issues": [
                        {
                            "code": "missing_term",
                            "message": "未准确翻译，'云物理机'应为'Cloud Physical Server'",
                            "expected_term": "Cloud Physical Server",
                        }
                    ],
                },
            )
            session.start()
            session.run(lambda: False)

            pending = session.snapshot()["pending_items"][0]
            self.assertEqual(pending["validation_state"], "passed")
            self.assertTrue(pending["can_accept"])
            self.assertEqual(pending["candidate_text"], "Delete Cloud Physical Server instance")

    def test_po_translation_session_allows_manual_accept_after_failed_validation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Project-Id-Version: Demo\\\\n"\n'
                '\n'
                '#: ../../source/demo.rst:8\n'
                'msgid "详见 :ref:`增加主机<5.2.1-addHost>` 章节。"\n'
                'msgstr ""\n',
                encoding="utf-8",
            )

            session = PoTranslationSession(
                po_path=po_path,
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 200},
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "slot_translations": [
                        {
                            "slot_id": kwargs["protected_source"]["translatable_slots"][0]["slot_id"],
                            "translation": "详见 ",
                            "frontend_ui_context": False,
                        },
                        {
                            "slot_id": kwargs["protected_source"]["translatable_slots"][1]["slot_id"],
                            "translation": "增加主机",
                            "frontend_ui_context": False,
                        },
                        {
                            "slot_id": kwargs["protected_source"]["translatable_slots"][2]["slot_id"],
                            "translation": " section.",
                            "frontend_ui_context": False,
                        },
                    ],
                    "reason": "ok",
                },
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            pending = session.snapshot()["pending_items"][0]
            self.assertEqual(pending["validation_state"], "failed")

            accepted = session.accept(
                pending["id"],
                candidate_text="See :ref:`Add Host<5.2.1-addHost>` section.",
            )
            self.assertEqual(accepted["status"]["counts"]["accepted"], 1)
            self.assertIn('msgstr "See :ref:`Add Host<5.2.1-addHost>` section."', po_path.read_text(encoding="utf-8"))

    def test_po_translation_manual_accept_rejects_rst_structure_break(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                'msgid ""\n'
                'msgstr ""\n'
                '"Project-Id-Version: Demo\\\\n"\n'
                '\n'
                '#: ../../source/demo.rst:9\n'
                'msgid "详见 :ref:`增加主机<5.2.1-addHost>` 章节。"\n'
                'msgstr ""\n',
                encoding="utf-8",
            )

            session = PoTranslationSession(
                po_path=po_path,
                glossary={},
                model_config={"base_url": "http://example/v1", "api_key": "sk", "model": "demo", "max_tokens": 200},
                model_runner=lambda **kwargs: {
                    "verdict": "needs_update",
                    "slot_translations": [
                        {
                            "slot_id": kwargs["protected_source"]["translatable_slots"][0]["slot_id"],
                            "translation": "See ",
                            "frontend_ui_context": False,
                        },
                        {
                            "slot_id": kwargs["protected_source"]["translatable_slots"][1]["slot_id"],
                            "translation": "Add Host",
                            "frontend_ui_context": False,
                        },
                        {
                            "slot_id": kwargs["protected_source"]["translatable_slots"][2]["slot_id"],
                            "translation": " section.",
                            "frontend_ui_context": False,
                        },
                    ],
                    "reason": "ok",
                },
                reviewer_runner=_pass_review,
            )
            session.start()
            session.run(lambda: False)

            pending = session.snapshot()["pending_items"][0]
            with self.assertRaisesRegex(ValueError, "breaks RST structure"):
                session.accept(
                    pending["id"],
                    candidate_text="See :ref:`Add Host<other-anchor>` section.",
                )

            still_pending = session.snapshot()["pending_items"][0]
            self.assertEqual(still_pending["id"], pending["id"])
            self.assertEqual(still_pending["candidate_text"], "See :ref:`Add Host<5.2.1-addHost>` section.")
