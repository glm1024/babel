import io
import unittest

from zh_audit.cli import ScanProgressReporter, format_scan_progress_line


class _TtyBuffer(io.StringIO):
    def isatty(self):
        return True


class CliTest(unittest.TestCase):
    def test_format_scan_progress_line_contains_progress_and_tail(self):
        line = format_scan_progress_line(
            processed=6,
            total=20,
            repo="repo-a",
            relative_path="src/service.html",
            width=10,
        )

        self.assertIn("扫描进度 [###-------] 6/20", line)
        self.assertIn("30.0%", line)
        self.assertIn("repo-a", line)
        self.assertIn("service.html", line)

    def test_progress_reporter_writes_terminal_updates(self):
        stream = _TtyBuffer()
        reporter = ScanProgressReporter(stream=stream, width=10)

        reporter(stage="start", total=2)
        reporter(stage="file", processed=1, total=2, repo="repo-a", relative_path="src/App.java")
        reporter(stage="done", processed=2, total=2)

        output = stream.getvalue()
        self.assertIn("扫描进度 [#####-----] 1/2", output)
        self.assertIn("扫描完成", output)
        self.assertTrue(output.endswith("\n"))


if __name__ == "__main__":
    unittest.main()
