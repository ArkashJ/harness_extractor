import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_EXAMPLES = (
    "findings/session.yaml",
    "findings/nested/session.json",
    "out/reduction.md",
    "out/nested/transcript.jsonl",
    ".claude/settings.local.json",
    ".claude/projects/session.jsonl",
    ".env",
    ".env.local",
)


def git(*args: str, input: str | None = None) -> str:
    return subprocess.run(
        ("git", "-c", "core.excludesFile=/dev/null", *args),
        cwd=ROOT,
        input=input,
        text=True,
        check=True,
        capture_output=True,
    ).stdout


class RepositoryPrivacyTest(unittest.TestCase):
    def test_private_artifacts_are_ignored_by_the_repository(self) -> None:
        ignored = git("check-ignore", "--stdin", input="\n".join(PRIVATE_EXAMPLES)).splitlines()
        self.assertEqual(list(PRIVATE_EXAMPLES), ignored)

    def test_private_artifacts_are_not_tracked(self) -> None:
        tracked = git("ls-files").splitlines()
        private = [
            path
            for path in tracked
            if path == ".env"
            or path.startswith((".env.", ".claude/", "findings/", "out/"))
        ]
        self.assertEqual([], private)


if __name__ == "__main__":
    unittest.main()
