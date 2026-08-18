import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def job(text: str, name: str) -> str:
    lines = text.splitlines()
    header = f"  {name}:"
    try:
        start = lines.index(header)
    except ValueError:
        return ""
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("  ") and not lines[index].startswith("    ")),
        len(lines),
    )
    return "\n".join(lines[start:end])


def step(job_text: str, name: str) -> str:
    blocks = ("      - " + block for block in job_text.split("\n      - ")[1:])
    return next((block for block in blocks if f"name: {name}" in block), "")


def step_containing(job_text: str, marker: str) -> str:
    blocks = ("      - " + block for block in job_text.split("\n      - ")[1:])
    return next((block for block in blocks if marker in block), "")


def release_contract_errors(root: Path) -> list[str]:
    workflows = root / ".github" / "workflows"
    ci = (workflows / "ci.yml").read_text(encoding="utf-8")
    release = (workflows / "release.yml").read_text(encoding="utf-8")
    release_job = job(release, "release")
    release_smoke = step(release_job, "Smoke both release artifacts and verify tag version")
    release_command = step_containing(release_job, "gh release create")
    ci_package = job(ci, "package")
    wheel_smoke = step(ci_package, "Smoke wheel in a clean environment")
    sdist_smoke = step(ci_package, "Smoke sdist in a clean environment")
    sdist_tests = step(ci_package, "Run tests from the extracted sdist")
    checks = {
        "release job must authenticate gh with github.token": "GH_TOKEN: ${{ github.token }}" in release_job,
        "release command must name the target repository": (
            'gh release create "$GITHUB_REF_NAME"' in release_command
            and '--repo "$GITHUB_REPOSITORY"' in release_command
        ),
        "release tag must match the package version": (
            'test "$GITHUB_REF_NAME" = "v$package_version"' in release_smoke
        ),
        "release must install and smoke both built artifacts": all(
            marker in release_smoke
            for marker in (
                "for kind in wheel sdist; do",
                'artifact="${wheels[0]}"',
                'test "$kind" = wheel || artifact="${sdists[0]}"',
                'pip install --disable-pip-version-check "$artifact"',
                'harness-extractor" --version',
                '"$environment/bin/harness-extractor" --help',
                '"$environment/bin/harness-extractor" "$fixture"',
            )
        ),
        "CI must smoke a clean wheel install": all(
            marker in wheel_smoke
            for marker in ("python -m venv", "pip install", "dist/*.whl", "--version", "--help", "ci-smoke")
        ),
        "CI must smoke a clean sdist install": all(
            marker in sdist_smoke
            for marker in ("python -m venv", "pip install", "dist/*.tar.gz", "--version", "--help", "ci-smoke")
        ),
        "CI must run tests from inside the extracted sdist": all(
            marker in sdist_tests
            for marker in ("tar -xzf", 'cd "$source_dir"', "python -m unittest discover -s tests -v")
        ),
    }
    return [message for message, passed in checks.items() if not passed]


class ReleaseContractTest(unittest.TestCase):
    def test_broken_workflows_name_every_missing_release_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workflows = Path(directory) / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "ci.yml").write_text("name: CI\n", encoding="utf-8")
            (workflows / "release.yml").write_text("name: Release\n", encoding="utf-8")

            errors = release_contract_errors(Path(directory))

        self.assertEqual(
            [
                "release job must authenticate gh with github.token",
                "release command must name the target repository",
                "release tag must match the package version",
                "release must install and smoke both built artifacts",
                "CI must smoke a clean wheel install",
                "CI must smoke a clean sdist install",
                "CI must run tests from inside the extracted sdist",
            ],
            errors,
        )

    @unittest.skipUnless((ROOT / ".github" / "workflows").is_dir(), "requires repository workflows")
    def test_repository_release_workflows_cover_the_publication_contract(self) -> None:
        self.assertEqual([], release_contract_errors(ROOT))


if __name__ == "__main__":
    unittest.main()
