import io
import unittest
from unittest import mock

from zh_audit.cli import _open_browser, build_parser, ScanProgressReporter, format_scan_progress_line


class _TtyBuffer(io.StringIO):
    def isatty(self):
        return True


class CliTest(unittest.TestCase):
    def test_parser_accepts_serve_command(self):
        parser = build_parser()
        args = parser.parse_args(["serve", "--no-browser"])
        self.assertEqual(args.command, "serve")
        self.assertTrue(args.no_browser)

    def test_parser_rejects_scan_and_review_commands(self):
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["scan"])
        with self.assertRaises(SystemExit):
            parser.parse_args(["review"])
        with self.assertRaises(SystemExit):
            parser.parse_args(["serve", "--out", "results"])

    def test_open_browser_returns_true_when_backend_succeeds(self):
        with mock.patch("zh_audit.cli.webbrowser.open", return_value=True) as mocked:
            self.assertTrue(_open_browser("http://127.0.0.1:8765/"))
            mocked.assert_called_once()

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
