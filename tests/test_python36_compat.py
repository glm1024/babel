import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_FILES = [
    path
    for path in (list((ROOT / "src").rglob("*.py")) + list((ROOT / "tests").rglob("*.py")))
    if path.name != "test_python36_compat.py"
]
FORBIDDEN_PATTERNS = [
    (re.compile(r"from __future__ import annotations"), "future annotations"),
    (re.compile(r"@dataclass\(slots=True\)"), "dataclass slots"),
    (re.compile(r"\|\s*None"), "pep604 optional union"),
    (re.compile(r"\blist\["), "pep585 list generic"),
    (re.compile(r"\bdict\["), "pep585 dict generic"),
    (re.compile(r"\btuple\["), "pep585 tuple generic"),
    (re.compile(r"\bset\["), "pep585 set generic"),
    (re.compile(r"re\.Match\["), "pep585/modern re.Match generic"),
    (re.compile(r"capture_output\s*="), "subprocess capture_output"),
    (re.compile(r"\btext\s*=\s*True\b"), "subprocess text=True"),
    (re.compile(r"\.removeprefix\("), "str.removeprefix"),
    (re.compile(r"add_subparsers\([^\n]*required\s*="), "argparse add_subparsers(required=...)"),
]


class Python36CompatTest(unittest.TestCase):
    def test_no_known_python36_incompatibilities_remain(self):
        offenders = []
        for path in PYTHON_FILES:
            text = path.read_text(encoding="utf-8")
            for pattern, label in FORBIDDEN_PATTERNS:
                if pattern.search(text):
                    offenders.append("{}: {}".format(path.relative_to(ROOT), label))
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_runtime_docs_call_out_python36_and_no_python2(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Python 3.6.1+", readme)
        self.assertIn("不支持 Python 2", readme)


if __name__ == "__main__":
    unittest.main()
