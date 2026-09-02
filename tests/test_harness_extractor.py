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
        self.assertEqual("1.1.0", extractor.__version__)
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
            human = "No, stop rewriting it — use the shared retry helper again instead."
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
        self.assertEqual("harness_extractor.py 1.1.0\n", result.stdout)
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
                    "reasks": 0,
                    "tool_failures": 0,
                    "tools": [],
                },
                "turns": [{
                    "n": 1,
                    "at": "2026-08-18T00:00:00Z",
                    "human": "hello",
                    "correction": False,
                    "emphatic": False,
                    "reask": False,
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


def codex_rollout(session_id, turns, cwd="/repo"):
    """A minimal Codex rollout: session_meta, then response_item records."""
    rows = [{"timestamp": "2026-09-02T00:00:00Z", "type": "session_meta",
             "payload": {"session_id": session_id, "id": session_id, "cwd": cwd}}]
    for i, (role, text) in enumerate(turns):
        rows.append({"timestamp": f"2026-09-02T00:00:{i:02d}Z", "type": "response_item",
                     "payload": {"type": "message", "role": role,
                                 "content": [{"type": "input_text", "text": text}]}})
    return "\n".join(json.dumps(r) for r in rows) + "\n"


class CodexTest(unittest.TestCase):
    def test_codex_rollout_reduces_to_human_turns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout.jsonl"
            path.write_text(codex_rollout("01a0", [
                ("user", "No, stop rewriting it — use the shared retry helper instead."),
                ("assistant", "Understood."),
            ]), encoding="utf-8")
            meta, turns = extractor.reduce_session(path)

        self.assertEqual("01a0", meta["session"])
        self.assertEqual("/repo", meta["cwd"])
        self.assertEqual(1, meta["human_turns"])
        self.assertTrue(turns[0]["correction"])

    def test_codex_shell_call_and_failed_output_are_recovered(self) -> None:
        rows = [
            {"timestamp": "2026-09-02T00:00:00Z", "type": "session_meta",
             "payload": {"session_id": "01a1", "cwd": "/repo"}},
            {"timestamp": "2026-09-02T00:00:01Z", "type": "response_item",
             "payload": {"type": "message", "role": "user",
                         "content": [{"type": "input_text", "text": "run the suite"}]}},
            {"timestamp": "2026-09-02T00:00:02Z", "type": "response_item",
             "payload": {"type": "custom_tool_call", "name": "exec", "call_id": "c1",
                         "input": "pytest -q"}},
            {"timestamp": "2026-09-02T00:00:03Z", "type": "response_item",
             "payload": {"type": "custom_tool_call_output", "call_id": "c1",
                         "output": [{"type": "input_text", "text": "Traceback (most recent call last)"}]}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            meta, turns = extractor.reduce_session(path)

        self.assertEqual(["Bash"], turns[0]["tools"])
        self.assertEqual(["pytest -q"], turns[0]["cmds"])
        self.assertEqual(1, meta["tool_failures"])

    def test_codex_goal_boilerplate_is_not_a_human_turn(self) -> None:
        goal = ("Continue working toward the active thread goal.\n\n"
                "<objective>\nport the wizard\n</objective>\n\nContinuation behavior: keep going.")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout.jsonl"
            path.write_text(codex_rollout("01a2", [
                ("user", "# AGENTS.md instructions\nnever ask for auth"),
                ("user", goal),
                ("user", goal),
            ]), encoding="utf-8")
            meta, turns = extractor.reduce_session(path)

        # The instructions block is harness noise and the goal restates one objective.
        self.assertEqual(1, meta["human_turns"])
        self.assertEqual("port the wizard", turns[0]["human"])

    def test_codex_forks_collapse_to_one_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            short = Path(directory) / "rollout-a.jsonl"
            long = Path(directory) / "rollout-b.jsonl"
            short.write_text(codex_rollout("01a3", [("user", "first ask")]), encoding="utf-8")
            long.write_text(codex_rollout("01a3", [("user", "first ask"), ("user", "second ask")]), encoding="utf-8")

            kept, dropped = extractor.dedupe_forks([short, long])

        self.assertEqual([long], kept)
        self.assertEqual([short], dropped)


class ReaskTest(unittest.TestCase):
    def test_restating_a_request_with_more_force_is_flagged(self) -> None:
        rows = [
            {"timestamp": "2026-09-02T00:00:00Z", "sessionId": "one", "cwd": "/repo",
             "message": {"role": "user", "content": "link the pull requests onto the kanban board"}},
            {"timestamp": "2026-09-02T00:00:01Z",
             "message": {"role": "assistant", "content": [{"type": "text", "text": "Done, 42 items added."}]}},
            {"timestamp": "2026-09-02T00:00:02Z", "sessionId": "one",
             "message": {"role": "user", "content": "link the pull requests onto the kanban board with quarters and dates!!"}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            meta, turns = extractor.reduce_session(path)

        self.assertEqual(1, meta["reasks"])
        self.assertTrue(turns[1]["reask"])
        # The re-ask carries no correction word; that is the whole point of the signal.
        self.assertFalse(turns[1]["correction"])
        self.assertIn("↩", extractor.as_markdown(meta, turns))

    def test_an_unrelated_follow_up_is_not_a_reask(self) -> None:
        rows = [
            {"timestamp": "2026-09-02T00:00:00Z", "sessionId": "one", "cwd": "/repo",
             "message": {"role": "user", "content": "link the pull requests onto the kanban board"}},
            {"timestamp": "2026-09-02T00:00:02Z", "sessionId": "one",
             "message": {"role": "user", "content": "now write the deployment runbook for staging"}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            meta, _ = extractor.reduce_session(path)

        self.assertEqual(0, meta["reasks"])


class EmptyReductionTest(unittest.TestCase):
    def test_a_transcript_with_no_human_turns_exits_non_zero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            path.write_text('{"unrecognised": true}\n', encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
                code = extractor.main([str(path)])

        self.assertEqual(1, code)
        self.assertIn("no human turns", stderr.getvalue())


class RepeatFloorTest(unittest.TestCase):
    def test_short_turns_do_not_manufacture_repeats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.jsonl"
            second = Path(directory) / "second.jsonl"
            for path, session in ((first, "one"), (second, "two")):
                path.write_text(json.dumps({
                    "timestamp": "2026-09-02T00:00:00Z", "sessionId": session, "cwd": "/repo",
                    "message": {"role": "user", "content": "no, try again"}}) + "\n", encoding="utf-8")

            self.assertEqual([], list(extractor.find_repeats([first, second])))
