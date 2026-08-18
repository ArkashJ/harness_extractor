import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import harness_extractor as extractor


class LibraryTest(unittest.TestCase):
    def test_version_and_reduction_are_public(self) -> None:
        self.assertEqual("1.0.0", extractor.__version__)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            rows = [
                {"timestamp": "2026-08-18T00:00:00Z", "sessionId": "abc", "cwd": "/repo", "message": {"role": "user", "content": "No, use the shared helper."}},
                {"timestamp": "2026-08-18T00:00:01Z", "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/repo/app.py"}}]}},
                {"timestamp": "2026-08-18T00:00:02Z", "message": {"role": "user", "content": [{"type": "tool_result", "is_error": True, "content": "permission denied"}]}},
            ]
            path.write_text("not json\n[]\n" + "\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            meta, turns = extractor.reduce_session(path)

        self.assertEqual("abc", meta["session"])
        self.assertEqual(1, meta["human_turns"])
        self.assertTrue(turns[0]["correction"])
        self.assertEqual(["Edit(repo/app.py)"], turns[0]["tools"])
        self.assertEqual(["permission denied"], turns[0]["failed"])


class CliTest(unittest.TestCase):
    def test_version_exits_zero(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as error:
            extractor.main(["--version"])

        self.assertEqual(0, error.exception.code)

    def test_script_version_prints_version(self) -> None:
        result = subprocess.run(
            [sys.executable, "harness_extractor.py", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, result.returncode)
        self.assertEqual("harness_extractor.py 1.0.0\n", result.stdout)
        self.assertEqual("", result.stderr)

    def test_json_writes_a_literal_payload_array(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            path.write_text(
                '{"timestamp":"2026-08-18T00:00:00Z","sessionId":"abc","cwd":"/repo","message":{"role":"user","content":"hello"}}\n',
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(0, extractor.main(["--json", str(path)]))

        self.assertEqual(
            [{
                "meta": {
                    "session": "abc",
                    "cwd": "/repo",
                    "start": "2026-08-18T00:00:00Z",
                    "end": "2026-08-18T00:00:00Z",
                    "human_turns": 1,
                    "corrections": 0,
                    "tool_failures": 0,
                    "tools": [],
                },
                "turns": [{
                    "n": 1,
                    "at": "2026-08-18T00:00:00Z",
                    "human": "hello",
                    "correction": False,
                    "emphatic": False,
                    "reply": "",
                    "tools": [],
                    "cmds": [],
                    "failed": [],
                }],
            }],
            json.loads(stdout.getvalue()),
        )

    def test_invalid_arguments_exit_two(self) -> None:
        for argv in (["--cap", "0"], ["--list", "--since", "not-a-date"], ["--since", "2026-08-18"]):
            with self.subTest(argv=argv):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    extractor.main(argv)
                self.assertEqual(2, error.exception.code)

    def test_missing_input_returns_one_with_one_line_error(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(1, extractor.main(["missing.jsonl"]))

        self.assertEqual(1, len(stderr.getvalue().splitlines()))
        self.assertTrue(stderr.getvalue().startswith("harness-extractor: "))

    def test_list_marks_harvested_session_from_supplied_locations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            session = root / "project" / "abcdef12-session.jsonl"
            session.parent.mkdir(parents=True)
            session.write_text("{}\n", encoding="utf-8")
            findings = Path(directory) / "findings"
            findings.mkdir()
            (findings / "codex-abcdef12.yaml").write_text("", encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(
                    0,
                    extractor.main(["--list", "--root", str(root), "--findings-dir", str(findings)]),
                )

        self.assertIn("harvested", stdout.getvalue())
