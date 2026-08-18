# Harness Extractor Public Release Design

## Goal

Turn the existing transcript reducer into a versioned, dependency-free Python library and CLI
that can be installed from a wheel, source archive, or Homebrew tap without publishing the
operator's transcripts, findings, syntheses, or provenance notes.

The first public release is `1.0.0`. The distribution and CLI are `harness-extractor`; the
import is `harness_extractor`.

## Product boundary

Harness Extractor performs mechanical reduction only. It reads local Claude Code JSONL session
records, extracts human turns and nearby assistant activity, and emits Markdown or JSON. It does
not classify findings semantically, call a model, upload data, add telemetry, or manage a corpus.

```text
~/.claude/projects/**/*.jsonl
              |
              v
     harness_extractor.py       stdlib-only mechanical reduction
              |
       +------+------+
       |             |
       v             v
    Markdown      JSON array
       |             |
       +------+------+
              |
              v
       local out/ only          ignored; may contain verbatim private content
              |
              v
   local findings/synthesis     ignored; never part of the public package
              |
              v
      reviewed gates/docs       the only derived artifacts eligible for Git
```

## Files and responsibilities

```text
harness_extractor.py            library implementation and testable CLI main(argv)
harvest.py                      compatibility launcher for existing ./harvest.py usage
pyproject.toml                  build metadata, version source, console entry point
tests/                          stdlib unittest behavior and repository privacy guards
docs/                           public usage and release design/plan
.github/workflows/ci.yml        test, build, install, and CLI smoke gate
.github/workflows/release.yml   build and attach artifacts for v* tags
Formula/harness-extractor.rb    formula source retained with the project for validation

Local-only, ignored:
out/                            reductions
findings/                       per-session model output
synthesis/                      cross-session private analysis
prompts/ORIGIN-*.md             provenance notes that identify local projects
```

No package directory, plugin system, configuration framework, logging framework, or runtime
dependency is introduced. The current program already fits in one module.

## Library API

The existing functions become the initial public API rather than being wrapped in speculative
classes:

- `records(path)` streams valid object records and skips malformed or non-object JSON lines.
- `reduce_session(path)` returns `(meta, turns)`.
- `as_markdown(meta, turns, cap=1600)` renders a reduction.
- `find_repeats(paths)` yields cross-session correction candidates.
- `dedupe_forks(files)` returns `(kept, dropped)` paths.
- `main(argv=None)` runs the CLI and returns an exit status.

`path` arguments accept `str` and `os.PathLike` values through `pathlib.Path`. Returned metadata
and turn dictionaries remain JSON-serializable. The API performs no writes or network calls.

`__version__ = "1.0.0"` is the single version source; `pyproject.toml` reads it dynamically.

## CLI contract

The installed executable is `harness-extractor`. `./harvest.py` remains a compatibility alias.
Existing flags remain available:

```text
harness-extractor --list [--since YYYY-MM-DD] [--root PATH] [--findings-dir PATH]
harness-extractor [--only-corrections] [--cap N] SESSION.jsonl [...]
harness-extractor --json SESSION.jsonl [...]
harness-extractor --repeats SESSION.jsonl [...]
harness-extractor --version
```

- `--root` defaults to `~/.claude/projects` and only affects session discovery.
- `--findings-dir` defaults to `./findings` and only affects harvested markers.
- `--json` emits one valid JSON array for any number of input files.
- Markdown remains the default output.
- Output goes to stdout; diagnostics go to stderr.
- Invalid dates, non-positive caps, and incompatible option combinations are argparse errors
  with exit code 2.
- Missing or unreadable input files produce one concise diagnostic and exit code 1, without a
  traceback.
- A missing transcript root is a successful empty inventory with a warning, preserving current
  automation behavior.

## Packaging

`pyproject.toml` uses setuptools as the build backend and declares:

- Python `>=3.10`, matching the current union-type syntax.
- MIT license.
- no runtime dependencies.
- `harness-extractor = "harness_extractor:main"` under `[project.scripts]`.
- project URLs for source, issues, and changelog.
- inclusion of the README, license, and typed metadata needed by package indexes.

Both sdist and universal wheel are required. A clean environment must install each artifact and
run `harness-extractor --version` and one fixture reduction.

## Privacy and repository history

The current branch stops tracking private artifacts, but those files remain in the existing Git
history and on GitHub's `main`. Before public release, history must be rewritten to remove:

```text
findings/**
synthesis/**
prompts/ORIGIN-*.md
```

```text
current public history
        |
        v
local private bundle backup
        |
        v
git-filter-repo on a disposable mirror
        |
        v
verify forbidden paths absent from every ref
        |
        v
fresh approval: force-push rewritten refs
        |
        v
re-clone/read back GitHub + rerun privacy test
```

The force-push is a separate destructive action and requires fresh confirmation immediately
before execution. Until then, release tagging is prohibited.

## Tests and CI

Tests use `unittest` and temporary JSONL fixtures; no testing dependency is needed. The minimum
behavior ledger covers:

1. text flattening and tool-result exclusion;
2. malformed/non-object record tolerance;
3. reduction metadata, corrections, tool paths, commands, and failed-tool tails;
4. Markdown rendering and cap behavior;
5. fork deduplication;
6. repeat detection across sessions;
7. CLI Markdown, JSON, list, error, and version paths;
8. repository privacy: generated/private paths are ignored and untracked.

CI runs on Python 3.10 through 3.14. One job runs tests and compilation on the matrix. A packaging
job builds wheel and sdist, checks metadata, installs each artifact into a clean virtual
environment, and invokes the CLI. CI must not read the operator's home transcript directory.

## Documentation and community files

The public repository includes:

- `README.md`: purpose, security warning, pip/pipx/Homebrew install, CLI examples, library API,
  and development commands;
- `CHANGELOG.md`: Keep a Changelog structure with `1.0.0` release notes;
- `LICENSE`: MIT text;
- `CODE_OF_CONDUCT.md`: Contributor Covenant 2.1;
- `CONTRIBUTING.md`: small local setup/test/release instructions;
- `SECURITY.md`: private vulnerability reporting and explicit transcript-confidentiality scope;
- `CLAUDE.md`: stable repository invariants and verification commands only;
- `AGENTS.md`: one-line pointer to `CLAUDE.md` so agent conventions have one source;
- GitHub issue and pull-request templates only where they prevent missing reproduction or
  verification evidence.

## Release and Homebrew flow

```text
feature commits
      |
      v
draft PR #1 -> CI green -> adversarial review
      |
      v
fresh merge approval
      |
      v
main readback -> tag v1.0.0 -> GitHub release + wheel + sdist
      |
      v
Formula/harness-extractor.rb gets immutable release URL + SHA-256
      |
      v
brew audit --new --formula + brew install + brew test
      |
      v
ArkashJ/homebrew-tap/Formula/harness-extractor.rb
      |
      v
brew install ArkashJ/tap/harness-extractor
```

The tap is a separate public repository named `ArkashJ/homebrew-tap`. Its formula depends on a
supported Homebrew Python and installs the project in a virtual environment. Bottles, PyPI
publishing, release bots, telemetry, and auto-update frameworks are excluded from 1.0.0 because
the source formula and GitHub artifacts satisfy the requested install paths without additional
accounts or infrastructure.

## Acceptance criteria

The release is complete only when all of the following are proven from authoritative state:

- no private artifact path exists in any public Git ref;
- the privacy regression test, unit tests, compile check, and build/install checks pass;
- wheel and sdist metadata report `harness-extractor 1.0.0`, Python `>=3.10`, and MIT;
- `./harvest.py` and installed `harness-extractor` produce equivalent fixture output;
- GitHub Actions is green on the release commit;
- GitHub tag and release `v1.0.0` exist and assets install successfully;
- `brew audit`, formula install, formula test, and the documented tap install command succeed;
- README, changelog, CLI help, package metadata, formula, tag, and release all agree on name and
  version;
- the worktree is clean and the final PR handoff records what was and was not verified.
