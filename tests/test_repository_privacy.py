import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_EXAMPLES = (
    "findings/session.yaml",
    "findings/nested/session.json",
    "synthesis/2026-08-18-cross-session.md",
    "prompts/ORIGIN-2026-08-18.md",
    "prompts/PR-REVIEW-PROMPT.md",
    "prompts/repo-steward-SEED.md",
    "out/reduction.md",
    "out/nested/transcript.jsonl",
    ".claude/settings.local.json",
    ".claude/projects/session.jsonl",
    ".superpowers/review.md",
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


@unittest.skipUnless((ROOT / ".git").exists(), "requires a Git worktree")
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
            or path.startswith("synthesis/")
            or path.startswith("prompts/ORIGIN-")
            or path in {"prompts/PR-REVIEW-PROMPT.md", "prompts/repo-steward-SEED.md"}
            or path.startswith(".superpowers/")
        ]
        self.assertEqual([], private)


if __name__ == "__main__":
    unittest.main()
