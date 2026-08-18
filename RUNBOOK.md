# Runbook

`harness-extractor` reduces local Claude Code session transcripts into a smaller review
artifact. It does not make network calls.

## Reduce a session

```bash
harness-extractor --list
harness-extractor session.jsonl > out/session.md
```

Use `--only-corrections` to focus a review, `--json` for machine-readable output, and
`--repeats` with two or more paths to locate similar corrections across sessions.

## Review safely

The reduction can retain verbatim transcript content, including confidential material. Keep
inputs and reductions local by default; do not commit them or attach them to public reports.
Review context before acting on a heuristic flag.

## Validate a change

```bash
python3 -m unittest discover -s tests -v
uv build
uvx twine check dist/*
```
