from __future__ import absolute_import

import posixpath
import zipfile
from collections import OrderedDict
from pathlib import Path
from xml.etree import ElementTree as ET


XLSX_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

TERMINOLOGY_HEADERS = ("中文", "英文")
DEFAULT_TERMINOLOGY_ROWS = [
    ("资源池", "resource pool"),
    ("主机组", "host group"),
    ("主机", "host"),
    ("云主机", "Elastic Compute Service"),
    ("云主机模板", "Elastic Compute Service Template"),
    ("控制台", "console"),
    ("云主机备份", "ECS backup"),
    ("云主机快照", "ECS snapshot"),
    ("软驱", "floppy driver"),
    ("镜像", "Image"),
    ("镜像库", "Image library"),
    ("弹性伸缩", "Elastic Scaling Service"),
    ("伸缩组", "Elastic Scaling Group"),
    ("全局内容库", "GLobal Content Library"),
    ("回收站", "recycle bin"),
    ("分组", "resource Group"),
    ("标签", "resource label"),
    ("管理地址", "Management IP Address"),
    ("芯片型号", "Processor Type"),
    ("主机型号", "Model"),
    ("防病毒", "Antivirus Status"),
    ("超分比", "Overcommit"),
    ("分配比", "Allocation"),
    ("CPU厂商", "CPU Vendor"),
    ("芯片厂商", "CPU Vendor"),
    ("引导选项", "Boot Orders"),
    ("崩溃策略", "Crash Recovery Policy"),
    ("周期备份", "scheduled backup"),
    ("全量备份", "Full backup"),
]


def ensure_default_terminology_xlsx(path):
    glossary_path = Path(path)
    if glossary_path.exists():
        return glossary_path
    glossary_path.parent.mkdir(parents=True, exist_ok=True)
    write_terminology_xlsx(glossary_path, DEFAULT_TERMINOLOGY_ROWS)
    return glossary_path


def load_terminology_xlsx(path):
    glossary_path = Path(path)
    if not glossary_path.exists():
        raise ValueError("Terminology file does not exist: {}".format(glossary_path))

    with zipfile.ZipFile(str(glossary_path), "r") as workbook:
        shared_strings = _read_shared_strings(workbook)
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml")

    rows = _read_sheet_rows(sheet_xml, shared_strings)
    if not rows:
        raise ValueError("Terminology file is empty: {}".format(glossary_path))

    headers = rows[0]
    if len(headers) < 2 or headers[0] != TERMINOLOGY_HEADERS[0] or headers[1] != TERMINOLOGY_HEADERS[1]:
        raise ValueError("Terminology file {} must start with headers: 中文, 英文".format(glossary_path))

    glossary = OrderedDict()
    for row_index, row in enumerate(rows[1:], 2):
        source = row[0].strip() if len(row) > 0 else ""
        target = row[1].strip() if len(row) > 1 else ""
        if not source and not target:
            continue
        if not source or not target:
            raise ValueError("Terminology file {} has an incomplete row at line {}.".format(glossary_path, row_index))
        if source in glossary:
            raise ValueError("Terminology file {} has duplicate Chinese term: {}".format(glossary_path, source))
        glossary[source] = target
    if not glossary:
        raise ValueError("Terminology file {} does not contain any terminology rows.".format(glossary_path))
    return glossary


def write_terminology_xlsx(path, rows):
    glossary_path = Path(path)
    workbook_xml = _build_workbook_xml()
    worksheet_xml = _build_worksheet_xml(rows)
    content_types_xml = _build_content_types_xml()
    root_rels_xml = _build_root_rels_xml()
    workbook_rels_xml = _build_workbook_rels_xml()

    with zipfile.ZipFile(str(glossary_path), "w", compression=zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", content_types_xml)
        workbook.writestr("_rels/.rels", root_rels_xml)
        workbook.writestr("xl/workbook.xml", workbook_xml)
        workbook.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        workbook.writestr("xl/worksheets/sheet1.xml", worksheet_xml)


def match_locked_terms(text, glossary):
    if not text:
        return []
    matches = []
    occupied = []
    for source in sorted(glossary.keys(), key=lambda item: (-len(item), item)):
        start = text.find(source)
        while start >= 0:
            end = start + len(source)
            if not _overlaps(occupied, start, end):
                occupied.append((start, end))
                matches.append(
                    {
                        "source": source,
                        "target": glossary[source],
                        "start": start,
                        "end": end,
                    }
                )
            start = text.find(source, start + 1)
    matches.sort(key=lambda item: item["start"])
    return matches


def exact_terminology_translation(text, glossary):
    normalized = str(text or "").strip()
    if not normalized:
        return ""
    return glossary.get(normalized, "")


def _overlaps(ranges, start, end):
    for current_start, current_end in ranges:
        if start < current_end and end > current_start:
            return True
    return False


def _read_shared_strings(workbook):
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    values = []
    for item in root.findall("{%s}si" % XLSX_NS):
        values.append(_text_from_node(item))
    return values


def _read_sheet_rows(sheet_xml, shared_strings):
    root = ET.fromstring(sheet_xml)
    rows = []
    for row in root.findall(".//{%s}row" % XLSX_NS):
        cell_values = OrderedDict()
        for cell in row.findall("{%s}c" % XLSX_NS):
            ref = cell.attrib.get("r", "")
            column_index = _column_index(ref)
            cell_values[column_index] = _read_cell_value(cell, shared_strings)
        if not cell_values:
            rows.append([])
            continue
        max_index = max(cell_values.keys())
        values = []
        for index in range(max_index + 1):
            values.append(cell_values.get(index, ""))
        rows.append(values)
    return rows


def _read_cell_value(cell, shared_strings):
    cell_type = cell.attrib.get("t", "")
    if cell_type == "s":
        value = cell.findtext("{%s}v" % XLSX_NS, default="0")
        try:
            shared_index = int(value)
        except ValueError:
            return ""
        if 0 <= shared_index < len(shared_strings):
            return shared_strings[shared_index]
        return ""
    if cell_type == "inlineStr":
        return _text_from_node(cell.find("{%s}is" % XLSX_NS))
    if cell_type == "str":
        return cell.findtext("{%s}v" % XLSX_NS, default="")
    return cell.findtext("{%s}v" % XLSX_NS, default="")


def _text_from_node(node):
    if node is None:
        return ""
    fragments = []
    for text_node in node.iter("{%s}t" % XLSX_NS):
        fragments.append(text_node.text or "")
    return "".join(fragments)


def _column_index(reference):
    letters = []
    for char in reference:
        if char.isalpha():
            letters.append(char.upper())
        else:
            break
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return max(index - 1, 0)


def _build_content_types_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""


def _build_root_rels_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""


def _build_workbook_rels_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""


def _build_workbook_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Terminology" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""


def _build_worksheet_xml(rows):
    worksheet = ET.Element("{%s}worksheet" % XLSX_NS)
    sheet_data = ET.SubElement(worksheet, "{%s}sheetData" % XLSX_NS)
    all_rows = [TERMINOLOGY_HEADERS] + list(rows)
    for row_index, row in enumerate(all_rows, 1):
        row_node = ET.SubElement(sheet_data, "{%s}row" % XLSX_NS, {"r": str(row_index)})
        for column_index, value in enumerate(row, 1):
            cell_ref = "{}{}".format(_column_name(column_index), row_index)
            cell = ET.SubElement(row_node, "{%s}c" % XLSX_NS, {"r": cell_ref, "t": "inlineStr"})
            inline = ET.SubElement(cell, "{%s}is" % XLSX_NS)
            text_node = ET.SubElement(inline, "{%s}t" % XLSX_NS)
            text_node.text = str(value)
    return ET.tostring(worksheet, encoding="utf-8", xml_declaration=True)


def _column_name(index):
    value = int(index)
    parts = []
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        parts.append(chr(ord("A") + remainder))
    return "".join(reversed(parts))
