import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def release_contract_errors(root: Path) -> list[str]:
    workflows = root / ".github" / "workflows"
    ci = (workflows / "ci.yml").read_text(encoding="utf-8")
    release = (workflows / "release.yml").read_text(encoding="utf-8")
    checks = {
        "release job must authenticate gh with github.token": "GH_TOKEN: ${{ github.token }}" in release,
        "release command must name the target repository": '--repo "$GITHUB_REPOSITORY"' in release,
        "release tag must match the package version": (
            'test "$GITHUB_REF_NAME" = "v$package_version"' in release
        ),
        "release must smoke both built artifacts": all(
            marker in release
            for marker in (
                "for kind in wheel sdist; do",
                '"$environment/bin/harness-extractor" --help',
                '"$environment/bin/harness-extractor" "$fixture"',
            )
        ),
        "CI must run the extracted sdist test suite": "python -m unittest discover -s tests -v" in ci,
        "CI must smoke separate wheel and sdist installs": all(
            marker in ci for marker in ("harness-extractor-wheel", "harness-extractor-sdist")
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

        self.assertEqual(6, len(errors))
        self.assertIn("release job must authenticate gh with github.token", errors)

    @unittest.skipUnless((ROOT / ".github" / "workflows").is_dir(), "requires repository workflows")
    def test_repository_release_workflows_cover_the_publication_contract(self) -> None:
        self.assertEqual([], release_contract_errors(ROOT))


if __name__ == "__main__":
    unittest.main()
