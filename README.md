# harness-extractor

Reduce Claude Code session transcripts to the human turns worth reviewing.

## Install

```bash
brew install ArkashJ/tap/harness-extractor
pipx install https://github.com/ArkashJ/harness_extractor/releases/download/v1.0.0/harness_extractor-1.0.0-py3-none-any.whl
python -m pip install https://github.com/ArkashJ/harness_extractor/releases/download/v1.0.0/harness_extractor-1.0.0.tar.gz
```

## CLI

List locally available sessions, then reduce a chosen JSONL transcript to Markdown:

```bash
harness-extractor --list
mkdir -p out
harness-extractor session.jsonl > out/session.md
```

Use `--json` for machine-readable output, `--only-corrections` to narrow the review,
and `--repeats` with multiple transcript paths to find recurring corrections. Run
`harness-extractor --help` for every option.

## Library

```python
from harness_extractor import as_markdown, reduce_session

meta, turns = reduce_session("session.jsonl")
print(as_markdown(meta, turns, cap=1600))
```

The public module also exposes `records`, `find_repeats`, `dedupe_forks`, and `main`.

## Privacy

**Reductions may contain verbatim private content from their source transcripts.** Treat
both input transcripts and generated reductions as confidential unless reviewed. Do not
commit, publish, or attach them to issues or pull requests.

The tool makes no network calls. It reads local JSONL files and writes its reduction to
standard output.

## Development

The runtime uses only the Python standard library and requires Python 3.10 or newer.

```bash
python3 -m unittest discover -s tests -v
uv build
uvx twine check dist/*
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution expectations and
[SECURITY.md](SECURITY.md) for private vulnerability reporting.

## How it works

```
local session.jsonl
        |
        v
parse records -> keep human turns -> pair assistant activity -> flag likely corrections
        |
        v
Markdown or JSON for human review
```

Flags identify a reading order, not a verdict. Review the original context before drawing
conclusions from a reduction.

## License

MIT. See [LICENSE](LICENSE).
