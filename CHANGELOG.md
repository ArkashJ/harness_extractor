# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-09-02

### Added

- Codex rollout support. Codex records are normalised to the Claude transcript shape inside
  `records()`, so reduction, JSON output, and repeat detection all read both harnesses.
  `--list` scans `~/.codex/sessions` alongside `~/.claude/projects` (`--codex-root` overrides),
  and fork snapshots collapse by session id — Codex writes dozens of files per session.
- Re-ask detection. A human turn that restates an earlier one with more specificity or force
  is flagged `reask` and marked `↩` in Markdown. A user who re-asks for something already
  reported done is correcting it, usually with no correction word anywhere in the turn.

### Changed

- A reduction with no human turns now exits non-zero and says so on stderr. It previously
  printed an empty reduction and returned success, which made an unparseable transcript
  indistinguishable from a quiet session.
- `find_repeats` requires six content words per turn, skips long near-verbatim blocks, and
  treats a leading slash command as an invocation rather than prose. Over a 195-transcript
  corpus this cut 61 reported pairs to 39 and template reuse from 16 pairs to 2.
- The compaction preamble is recognised as harness output rather than a human turn.

## [1.0.0] - 2026-08-18

### Added

- Importable `harness_extractor` library with transcript reduction and Markdown rendering.
- `harness-extractor` command-line interface, including JSON, inventory, and repeat-detection modes.
- Build metadata, a source distribution, a universal wheel, and a console entry point.
- Privacy boundaries that keep transcript-derived artifacts out of the repository by default.
- Public documentation, contribution and security policies, and GitHub contribution templates.
- Continuous-integration and Homebrew release readiness.
- Executable release-contract guards for workflow authentication, version coherence, and artifact smokes.
