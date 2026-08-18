import contextlib
import io
import inspect
import json
import os
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

    def test_markdown_defaults_to_1600_char_turns(self) -> None:
        meta = {
            "session": "abc",
            "human_turns": 1,
            "corrections": 0,
            "tool_failures": 0,
            "tools": [],
        }
        turn = {
            "n": 1,
            "at": "now",
            "human": "x" * 1601,
            "correction": False,
            "emphatic": False,
            "reply": "",
            "tools": [],
            "cmds": [],
            "failed": [],
        }

        markdown = extractor.as_markdown(meta, [turn])

        self.assertEqual(1600, inspect.signature(extractor.as_markdown).parameters["cap"].default)
        self.assertIn("\n```\n" + "x" * 1600 + "\n```\n", markdown)
        self.assertNotIn("x" * 1601, markdown)

    def test_markdown_cap_and_fence_handle_backticks(self) -> None:
        meta = {
            "session": "abc",
            "human_turns": 1,
            "corrections": 0,
            "tool_failures": 0,
            "tools": [],
        }
        turn = {
            "n": 1,
            "at": "now",
            "human": "before ``` and ```` after",
            "correction": False,
            "emphatic": False,
            "reply": "",
            "tools": [],
            "cmds": [],
            "failed": [],
        }

        markdown = extractor.as_markdown(meta, [turn], cap=21)

        self.assertIn("\n`````\nbefore ``` and ```` a\n`````\n", markdown)

    def test_dedupe_forks_accepts_string_paths_and_keeps_longer_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.jsonl"
            second = Path(directory) / "second.jsonl"
            shared = '{"cwd":"/repo","timestamp":"2026-08-18T00:00:00Z"}\n'
            first.write_text(shared, encoding="utf-8")
            second.write_text(shared + "{}\n", encoding="utf-8")

            kept, dropped = extractor.dedupe_forks([str(first), second])

        self.assertEqual([second], kept)
        self.assertEqual([first], dropped)

    def test_repeat_detection_finds_matching_corrections_across_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.jsonl"
            second = Path(directory) / "second.jsonl"
            human = "No, use the shared helper again."
            first.write_text(json.dumps({"timestamp": "2026-08-18T00:00:00Z", "sessionId": "one", "cwd": "/repo", "message": {"role": "user", "content": human}}) + "\n", encoding="utf-8")
            second.write_text(json.dumps({"timestamp": "2026-08-18T00:00:00Z", "sessionId": "two", "cwd": "/repo", "message": {"role": "user", "content": human}}) + "\n", encoding="utf-8")

            repeats = list(extractor.find_repeats([first, second]))

        self.assertEqual(1, len(repeats))

    def test_reduction_extracts_bash_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            rows = [
                {"timestamp": "2026-08-18T00:00:00Z", "sessionId": "one", "cwd": "/repo", "message": {"role": "user", "content": "hello"}},
                {"timestamp": "2026-08-18T00:00:01Z", "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Bash", "input": {"command": "python -m unittest\n--verbose"}}]}},
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

            _, turns = extractor.reduce_session(path)

        self.assertEqual(["python -m unittest --verbose"], turns[0]["cmds"])


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
        for argv in (["--cap", "0"], ["--list", "--since", ""], ["--list", "--since", "not-a-date"], ["--list", "--since", "20260818"], ["--since", "2026-08-18"], ["--lis"]):
            with self.subTest(argv=argv):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    extractor.main(argv)
                self.assertEqual(2, error.exception.code)

    def test_discarded_mode_options_exit_two(self) -> None:
        for argv in (
            ["--list", "--json"],
            ["--list", "--repeats"],
            ["--list", "--only-corrections"],
            ["--list", "--cap", "20"],
            ["--repeats", "--json", "one.jsonl", "two.jsonl"],
            ["--repeats", "--only-corrections", "one.jsonl"],
            ["--repeats", "--cap", "20", "one.jsonl"],
        ):
            with self.subTest(argv=argv):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    extractor.main(argv)
                self.assertEqual(2, error.exception.code)

    def test_listing_only_arguments_exit_two_outside_inventory(self) -> None:
        for argv in (["--root", ".", "session.jsonl"], ["--findings-dir", ".", "session.jsonl"], ["--list", "session.jsonl"]):
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

    def test_double_dash_allows_option_named_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "--root"
            path.write_text(
                '{"timestamp":"2026-08-18T00:00:00Z","sessionId":"dash","cwd":"/repo","message":{"role":"user","content":"hello"}}\n',
                encoding="utf-8",
            )
            previous = Path.cwd()
            stdout = io.StringIO()
            try:
                os.chdir(directory)
                with contextlib.redirect_stdout(stdout):
                    self.assertEqual(0, extractor.main(["--", "--root"]))
            finally:
                os.chdir(previous)

        self.assertIn("# Session dash", stdout.getvalue())

    def test_cli_writes_markdown_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            path.write_text(
                '{"timestamp":"2026-08-18T00:00:00Z","sessionId":"markdown","cwd":"/repo","message":{"role":"user","content":"hello"}}\n',
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(0, extractor.main([str(path)]))

        self.assertIn("# Session markdown", stdout.getvalue())

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
