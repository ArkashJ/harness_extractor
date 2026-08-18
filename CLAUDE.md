# Repository instructions

- Runtime dependencies: Python standard library only.
- Python floor: 3.10 (`requires-python = ">=3.10"`).
- Private paths: `out/`, `findings/`, `synthesis/`, selected local prompts, `.claude/`, `.superpowers/`, and `.env*` stay untracked; the privacy test is authoritative.
- Version source: `harness_extractor.__version__`.
- Test: `python3 -m unittest discover -s tests -v`.
- Build: `uv build` and `uvx twine check dist/*`.
