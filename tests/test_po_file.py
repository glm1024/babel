import tempfile
import unittest
from pathlib import Path

from zh_audit.po_file import load_po_document


class PoFileTest(unittest.TestCase):
    def test_po_document_tolerates_unescaped_quotes_and_preserves_newline_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "demo.po"
            po_path.write_text(
                '#, fuzzy\r\n'
                'msgid ""\r\n'
                'msgstr ""\r\n'
                '"Project-Id-Version: Demo\\\\n"\r\n'
                '\r\n'
                '#: ../../source/demo.rst:1\r\n'
                'msgid "集群列表"\r\n'
                'msgstr "In the "Cluster List" module"\r\n',
                encoding="utf-8",
                newline="",
            )

            document = load_po_document(po_path)
            entries = document.entries()
            self.assertEqual(entries[0].msgid_text(), "")
            self.assertEqual(entries[1].msgid_text(), "集群列表")
            self.assertEqual(entries[1].msgstr_text(), 'In the "Cluster List" module')

            entries[1].set_msgstr_value('In the "Cluster List" section')
            document.write()

            with po_path.open(encoding="utf-8", newline="") as handle:
                rendered = handle.read()
            self.assertIn('#, fuzzy\r\nmsgid ""\r\nmsgstr ""\r\n"Project-Id-Version: Demo\\\\n"\r\n', rendered)
            self.assertIn('msgstr "In the \\"Cluster List\\" section"\r\n', rendered)
            self.assertNotIn('msgstr "In the "Cluster List" module"\r\n', rendered)

    def test_po_document_updates_only_target_msgstr_block(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / "doc.po"
            po_path.write_text(
                '#: ../../source/demo.rst:3\n'
                'msgid ""\n'
                '"在当前页面，单击【增加数据存储】按钮，可进入增加数据存储页面，详见本文档 "\n'
                '":ref:`存储池管理与配置<7-storeManagerConfig>` 章节。"\n'
                'msgstr ""\n'
                '\n'
                '#: ../../source/demo.rst:8\n'
                'msgid "创建全新虚拟机"\n'
                'msgstr "Create a new VM"\n',
                encoding="utf-8",
            )

            document = load_po_document(po_path)
            first_entry = document.entries()[0]
            first_entry.set_msgstr_value(
                'See :ref:`Storage Management and Configuration<7-storeManagerConfig>` for details.'
            )
            document.write()

            rendered = po_path.read_text(encoding="utf-8")
            self.assertIn('#: ../../source/demo.rst:3\nmsgid ""\n"在当前页面，单击【增加数据存储】按钮，可进入增加数据存储页面，详见本文档 "\n', rendered)
            self.assertIn(
                'msgstr "See :ref:`Storage Management and Configuration<7-storeManagerConfig>` for details."\n',
                rendered,
            )
            self.assertIn('msgid "创建全新虚拟机"\nmsgstr "Create a new VM"\n', rendered)
