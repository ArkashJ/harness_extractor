import json
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
