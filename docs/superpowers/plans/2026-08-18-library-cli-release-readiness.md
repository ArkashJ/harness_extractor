# Harness Extractor Library and CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a tested `harness-extractor` 1.0.0 Python library and CLI with public documentation, CI, and build artifacts while keeping all harvested data local.

**Architecture:** Keep the implementation in one stdlib-only `harness_extractor.py` module and retain `harvest.py` as a compatibility launcher. Package that module with setuptools, exercise it through `unittest`, and use GitHub Actions only for repeatable test/build/release gates.

**Tech Stack:** Python 3.10–3.14 stdlib, setuptools, unittest, GitHub Actions, Homebrew validation in the later release plan.

**Spec:** `docs/superpowers/specs/2026-08-18-public-release-design.md`

## Global Constraints

- Distribution and CLI name: `harness-extractor`; import name: `harness_extractor`.
- Version: `1.0.0`; release tag: `v1.0.0`.
- Python: `>=3.10`; CI: 3.10, 3.11, 3.12, 3.13, 3.14.
- Runtime dependencies: none.
- No network calls, telemetry, model calls, plugin system, or configuration framework.
- `out/`, `findings/`, `synthesis/`, `.claude/`, and `prompts/ORIGIN-*.md` remain ignored and untracked.
- Every behavior change follows RED → GREEN with `python3 -m unittest discover -s tests -v`.
- Do not tag, release, merge, rewrite history, or force-push in this plan.

---

### Task 1: Importable library with compatibility launcher

**Files:**
- Create: `harness_extractor.py`
- Modify: `harvest.py`
- Create: `tests/test_harness_extractor.py`

**Interfaces:**
- Consumes: the existing functions and constants in `harvest.py`.
- Produces: importable `harness_extractor.__version__`, `records`, `reduce_session`, `as_markdown`, `find_repeats`, `dedupe_forks`, and `main`; compatible `./harvest.py` launcher.

- [ ] **Step 1: Write the failing import and reduction tests**

Create a temporary JSONL file containing one human message, one assistant tool call, one failed
tool result, and one malformed/non-object line. Assert literal results:

```python
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
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python3 -m unittest tests/test_harness_extractor.py -v`

Expected: import failure for `harness_extractor`.

- [ ] **Step 3: Move the implementation and add the launcher**

Move the current `harvest.py` implementation unchanged into `harness_extractor.py`, add:

```python
__version__ = "1.0.0"
```

Replace `harvest.py` with:

```python
#!/usr/bin/env python3
from harness_extractor import main


if __name__ == "__main__":
    raise SystemExit(main())
```

In `records`, skip decoded values that are not dictionaries before yielding them.

- [ ] **Step 4: Run GREEN and compatibility checks**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile harness_extractor.py harvest.py
python3 harvest.py --help
```

Expected: all tests pass; both modules compile; legacy help prints.

- [ ] **Step 5: Commit**

```bash
git add harness_extractor.py harvest.py tests/test_harness_extractor.py
git commit -m "Expose transcript reducer as a library"
```

---

### Task 2: Stable, testable CLI

**Files:**
- Modify: `harness_extractor.py`
- Modify: `tests/test_harness_extractor.py`

**Interfaces:**
- Consumes: Task 1's public module and `__version__`.
- Produces: `main(argv: list[str] | None = None) -> int`, `--root`, `--findings-dir`, `--version`, valid JSON arrays, and concise errors.

- [ ] **Step 1: Write failing CLI tests**

Use `contextlib.redirect_stdout`, `redirect_stderr`, and temporary paths. Add tests that assert:

```python
self.assertEqual(0, extractor.main(["--version"]))
self.assertEqual(0, extractor.main(["--json", str(path)]))
self.assertEqual([{"meta": meta, "turns": turns}], json.loads(stdout.getvalue()))
```

Also assert `SystemExit(2)` for `--cap 0`, invalid `--since`, and `--since` without `--list`;
assert return code 1 and a one-line stderr message for a missing input; assert `--list --root
<temporary-root> --findings-dir <temporary-findings>` marks a matching session as harvested.

- [ ] **Step 2: Run the CLI tests and verify RED**

Run: `python3 -m unittest tests/test_harness_extractor.py -v`

Expected: failures because `main` does not accept argv, new flags do not exist, and JSON is not an array.

- [ ] **Step 3: Implement only the tested CLI contract**

Change the entry point to:

```python
def main(argv=None):
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument("--root", type=pathlib.Path, default=ROOT)
    ap.add_argument("--findings-dir", type=pathlib.Path, default=pathlib.Path.cwd() / "findings")
    # retain the existing arguments
    a = ap.parse_args(argv)
```

Validate incompatible flags with `ap.error`. Parse `--since` inside a `try` and convert invalid
dates to `ap.error("--since must be YYYY-MM-DD")`. Accumulate JSON payloads and dump the list once.
Catch `OSError` around input reduction, print `harness-extractor: <message>` to stderr, and return
1. Return 0 on every successful path. Use `a.root` and `a.findings_dir` instead of module-relative
state.

- [ ] **Step 4: Run GREEN and CLI smoke checks**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 harness_extractor.py --version
python3 harvest.py --version
python3 harness_extractor.py --list --since 2999-01-01
```

Expected: tests pass; both version commands print `1.0.0`; future inventory reports zero sessions without a traceback.

- [ ] **Step 5: Commit**

```bash
git add harness_extractor.py tests/test_harness_extractor.py
git commit -m "Harden the harness-extractor CLI"
```

---

### Task 3: Buildable Python distribution

**Files:**
- Create: `pyproject.toml`
- Create: `tests/test_distribution.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `harness_extractor.__version__` and `main`.
- Produces: `harness-extractor` sdist, universal wheel, metadata, and console entry point.

- [ ] **Step 1: Write the failing metadata test**

```python
import tomllib
import unittest
from pathlib import Path


class DistributionTest(unittest.TestCase):
    def test_project_metadata_matches_public_contract(self) -> None:
        project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
        self.assertEqual("harness-extractor", project["name"])
        self.assertEqual(">=3.10", project["requires-python"])
        self.assertEqual([], project["dependencies"])
        self.assertEqual("harness_extractor:main", project["scripts"]["harness-extractor"])
```

- [ ] **Step 2: Run the metadata test and verify RED**

Run: `python3 -m unittest tests/test_distribution.py -v`

Expected: `FileNotFoundError` for `pyproject.toml`.

- [ ] **Step 3: Add minimal package metadata**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "harness-extractor"
dynamic = ["version"]
description = "Reduce Claude Code session transcripts to the turns worth reviewing"
readme = "README.md"
requires-python = ">=3.10"
license = "MIT"
dependencies = []
keywords = ["claude-code", "transcripts", "cli"]
classifiers = [
  "Development Status :: 5 - Production/Stable",
  "Environment :: Console",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3 :: Only",
]

[project.urls]
Homepage = "https://github.com/ArkashJ/harness_extractor"
Issues = "https://github.com/ArkashJ/harness_extractor/issues"
Changelog = "https://github.com/ArkashJ/harness_extractor/blob/main/CHANGELOG.md"

[project.scripts]
harness-extractor = "harness_extractor:main"

[tool.setuptools]
py-modules = ["harness_extractor"]

[tool.setuptools.dynamic]
version = {attr = "harness_extractor.__version__"}
```

Ensure `.gitignore` retains `build/`, `dist/`, and `*.egg-info/`.

- [ ] **Step 4: Build, inspect, install, and test both artifacts**

Run:

```bash
python3 -m unittest discover -s tests -v
uv build
uvx twine check dist/*
uv venv /private/tmp/harness-extractor-wheel-venv
uv pip install --python /private/tmp/harness-extractor-wheel-venv/bin/python dist/*.whl
/private/tmp/harness-extractor-wheel-venv/bin/harness-extractor --version
uv venv /private/tmp/harness-extractor-sdist-venv
uv pip install --python /private/tmp/harness-extractor-sdist-venv/bin/python dist/*.tar.gz
/private/tmp/harness-extractor-sdist-venv/bin/harness-extractor --version
```

Expected: metadata checks pass; one `py3-none-any.whl` and one sdist build; both clean installs print `1.0.0`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/test_distribution.py .gitignore
git commit -m "Package harness-extractor 1.0.0"
```

---

### Task 4: Public documentation and governance

**Files:**
- Modify: `README.md`
- Modify: `RUNBOOK.md`
- Create: `CHANGELOG.md`
- Create: `LICENSE`
- Create: `CODE_OF_CONDUCT.md`
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `CLAUDE.md`
- Create: `AGENTS.md`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`

**Interfaces:**
- Consumes: Tasks 1–3's exact package, import, CLI, test, and privacy contracts.
- Produces: public install/usage/security/contribution instructions with no private corpus references.

- [ ] **Step 1: Rewrite README around the public product**

Use these exact top-level sections: `Install`, `CLI`, `Library`, `Privacy`, `Development`,
`How it works`, `License`. Include commands:

```bash
brew install ArkashJ/tap/harness-extractor
pipx install harness-extractor
python -m pip install harness-extractor
harness-extractor --list
harness-extractor session.jsonl > out/session.md
```

Include library usage:

```python
from harness_extractor import as_markdown, reduce_session

meta, turns = reduce_session("session.jsonl")
print(as_markdown(meta, turns, cap=1600))
```

State prominently that reductions may contain verbatim private content and the tool makes no network calls.

- [ ] **Step 2: Add governance files with concrete policies**

- `LICENSE`: canonical MIT text, copyright `2026 Arkash Jain`.
- `CODE_OF_CONDUCT.md`: Contributor Covenant 2.1 with enforcement contact `https://github.com/ArkashJ/harness_extractor/security`.
- `CONTRIBUTING.md`: fork/branch, `python3 -m unittest discover -s tests -v`, `uv build`, `uvx twine check dist/*`, privacy rule, PR expectations.
- `SECURITY.md`: supported version `1.x`, private GitHub vulnerability reporting, never attach transcripts/reductions/findings to public reports.
- `CHANGELOG.md`: Keep a Changelog header plus `1.0.0 - 2026-08-18` entries for library, CLI, packaging, privacy boundary, docs, CI, and Homebrew readiness.
- `CLAUDE.md`: stable invariants only: stdlib runtime, Python floor, private paths, version source, canonical test/build commands.
- `AGENTS.md`: exactly `See [CLAUDE.md](CLAUDE.md) for repository instructions.`

- [ ] **Step 3: Add evidence-oriented GitHub templates**

The PR template requires summary, test commands/output, privacy review, and release impact. The bug form requires version, OS/Python, command, expected/actual behavior, reproduction without private transcripts, and confirmation that no confidential data is attached.

- [ ] **Step 4: Verify docs against code**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 harness_extractor.py --help
git grep -n "Python 3.9\|stdlib only, no install\|findings.*committed\|synthesis.*committed"
git diff --check
```

Expected: tests and help pass; stale-claim grep returns no matches; diff check is clean.

- [ ] **Step 5: Commit**

```bash
git add README.md RUNBOOK.md CHANGELOG.md LICENSE CODE_OF_CONDUCT.md CONTRIBUTING.md SECURITY.md CLAUDE.md AGENTS.md .github
git commit -m "Document and govern the public project"
```

---

### Task 5: Continuous integration and release artifact workflow

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/release.yml`
- Modify: `tests/test_distribution.py`

**Interfaces:**
- Consumes: Tasks 1–4's test/build commands and `v1.0.0` tag convention.
- Produces: least-privilege CI and GitHub release artifact automation.

- [ ] **Step 1: Extend distribution tests to inspect workflows**

Parse the workflow files as text and assert consumer-visible policy: CI mentions every supported
Python version, runs the canonical unittest command and `uv build`, and release triggers only on
`v*` tags with `contents: write`. This is a narrow repository-policy test; do not assert formatting.

- [ ] **Step 2: Run the workflow policy test and verify RED**

Run: `python3 -m unittest tests/test_distribution.py -v`

Expected: missing workflow file failure.

- [ ] **Step 3: Add least-privilege workflows**

Use `actions/checkout@v6` and `actions/setup-python@v6`.

`ci.yml`:

```yaml
name: CI
on:
  push:
  pull_request:
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python: ["3.10", "3.11", "3.12", "3.13", "3.14"]
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: ${{ matrix.python }}
      - run: python -m unittest discover -s tests -v
      - run: python -m py_compile harness_extractor.py harvest.py
  package:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.14"
      - run: python -m pip install --disable-pip-version-check build twine
      - run: python -m build
      - run: python -m twine check dist/*
      - run: python -m pip install dist/*.whl
      - run: harness-extractor --version
```

`release.yml` triggers on `v*` tags, checks out with `contents: read`, builds/checks artifacts,
then a separate job with `contents: write` downloads the artifacts and runs:

```bash
gh release create "$GITHUB_REF_NAME" dist/* --generate-notes --verify-tag
```

- [ ] **Step 4: Run GREEN and local equivalent checks**

Run:

```bash
python3 -m unittest discover -s tests -v
uv build
uvx twine check dist/*
git diff --check
```

Expected: all tests and artifact checks pass.

- [ ] **Step 5: Commit and push**

```bash
git add .github/workflows tests/test_distribution.py
git commit -m "Add test and release workflows"
git push
```

Then read the draft PR checks from GitHub and fix any CI-only failure before proceeding.

---

### Task 6: Local release-readiness audit and handoff

**Files:**
- Modify: `CHANGELOG.md` only if the actual diff exposes a missing entry.
- Modify: draft PR description and rolling checkpoint comment on GitHub.

**Interfaces:**
- Consumes: all previous tasks and the design acceptance ledger.
- Produces: a clean, pushed branch ready for adversarial review and a separate history/release plan based on actual artifact hashes.

- [ ] **Step 1: Run the complete local gate**

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile harness_extractor.py harvest.py
uv build
uvx twine check dist/*
git diff --check
git status --short
```

Expected: all tests pass, artifacts validate, diff check is clean, and status is empty.

- [ ] **Step 2: Inspect public artifacts**

List wheel and sdist contents and verify no path starts with `findings/`, `synthesis/`, `out/`,
`.claude/`, or `prompts/ORIGIN-`. Install both artifacts into clean temporary environments and
run `harness-extractor --version`, `--help`, and a fixture reduction.

- [ ] **Step 3: Run an adversarial review**

Use `superpowers:requesting-code-review` with a fresh reviewer asked to refute every acceptance
claim, especially privacy, CLI compatibility, packaging metadata, and docs/code drift. Fix every
confirmed finding with TDD and rerun Step 1.

- [ ] **Step 4: Update the draft PR handoff**

Record exact commits, test/build outputs, artifact names, CI check URLs, what remains unverified,
and these deliberately deferred destructive/external actions:

```text
rewrite public Git history and force-push rewritten refs
merge PR #1
create tag/release v1.0.0
create ArkashJ/homebrew-tap and publish the formula with the observed release SHA-256
```

- [ ] **Step 5: Write the next plan from authoritative release state**

After CI is green, create `docs/superpowers/plans/2026-08-18-history-release-homebrew.md` with
the actual release commit, artifact names, GitHub URLs, and exact history-rewrite verification.
Request fresh confirmation immediately before force-push and again before merge, as required by
the repository's blast-radius rules.
