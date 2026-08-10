# extractor

Turn Claude Code session transcripts into things that change how you work.

Transcripts already exist — every session is written to
`~/.claude/projects/<encoded-cwd>/<uuid>.jsonl`. Nothing needs instrumenting. The problem is
that a session is millions of tokens and the reusable signal is a few dozen turns.

```bash
./harvest.py --list                          # what's on disk, newest first
./harvest.py <file.jsonl> > out/session.md   # 5.5MB → 16KB
./harvest.py --only-corrections <file.jsonl> # just the pushback
./harvest.py --repeats a.jsonl b.jsonl c...  # corrections recurring ACROSS sessions
```

stdlib only. Python 3.9+. No install, no deps.

## The split

**The script does mechanics. The model does judgement.** That line is deliberate and worth
keeping — semantic classification in Python would be worse than a model's, and a model reading
5 MB of raw JSONL would be worse than reading a 16 KB reduction.

So: `harvest.py` finds real human turns (a user record carrying `tool_result` is the harness
replying, not you), pairs each with what the assistant did next, and flags likely corrections.
The regex flags are a **reading order, not a verdict** — deliberately over-inclusive, because a
false positive costs one line of reading and a false negative loses the finding.

Then `prompts/harvest.md` tells a model what to extract from the reduction.

## Why corrections, not "learnings"

Ask a model for "learnings" and you get *"verify assumptions, read the docs first"* — true,
useless, already written down. The signal is concentrated at five points:

1. **Corrections** — you pushed back or redirected
2. **Falsifications** — a claim was tested and was wrong
3. **Surprises** — reality differed from a doc, comment, or plan
4. **Rework** — work redone, and what would have prevented it
5. **Gate saves** — an automated check caught what nobody spotted

A **repeated instruction is the strongest signal in any transcript**: it means a default
behaviour is wrong, and it survived being corrected once.

## Workflow

Full procedure + the end-to-end prompt: **[RUNBOOK.md](RUNBOOK.md)**.

```
1. ./harvest.py --list                      pick sessions
2. ./harvest.py <f> > out/<name>.md         reduce (seconds)
3. feed out/<name>.md + prompts/harvest.md  to a strong model → findings YAML
4. after ~5 sessions: cross-session synthesis prompt (bottom of prompts/harvest.md)
   ** hold out ≥1 session and test conclusions against it **
5. convert surviving findings to GATES (CI assertions), not documents
```

Step 4's hold-out is not optional. A strong model handed 10 transcripts produces a fluent,
plausible synthesis; plausible is not true, and there's no compiler to disagree with it.

## The metric

**Repeat-correction rate** — does a correction from session 1 reappear in session 8?

If yes, the loop isn't closing and the tooling is theatre. `--repeats` measures it. It's the
only honest test of whether any of this works, and it's computable from transcripts you already
have.

## Sorting findings

Three buckets, never merged:

| Bucket | Goes to |
|---|---|
| Cross-repo pattern | a skill, or this tooling |
| Single-repo pattern | that repo's `CLAUDE.md` |
| Personal workflow | your global config |

Merging them is the most common way extracted learnings become unusable.

## Files

```
harvest.py                     the extractor
RUNBOOK.md                     storage rules + the one prompt that drives the loop
prompts/harvest.md             what to extract, + cross-session synthesis
prompts/IMPROVE-THESE-PROMPTS.md  how to make these better (run them, don't read them)
prompts/PR-REVIEW-PROMPT.md    reviewing a PR that mixes evidence with fixes
prompts/repo-steward-SEED.md   spec for a skill built from these findings
prompts/ORIGIN-2026-08-04.md   the session this came from, with the evidence table
out/                           reductions — GITIGNORED, they carry raw client content
findings/                      model findings, committed (patterns, never payloads)
synthesis/                     cross-session synthesis + held-out results, committed
```

## Prompt validation state

`prompts/harvest.md` has now been executed across **87 sessions** (2026-08-04 → 08-10) and
holds up: pointed at 32 reductions in one batch it returned ~190 findings and zero sessions of
generic advice. The synthesis and PR-review prompts are still **v1 drafts nobody has run**. See
`prompts/IMPROVE-THESE-PROMPTS.md` — the improvement rule is *run them, don't read them*,
because reading produces longer, prettier, more generic prompts that perform worse.

What running them at scale exposed was not in the prompts but in the **instrument**, twice:

- `Did:` logged tool names without file paths, so a reduction could not answer "what did this
  session change". Four sessions in a directory named `doc_recon`, one of them running
  `Edit×11` against `docs/`, measured as **zero doc edits**. Every synthesis written before
  2026-08-10 was built on reductions with that hole in them.
- Forked sessions were counted twice — same run, two uuids, byte-identical to the millisecond.
  `--repeats` is the honest metric, so a fork manufactures the precise cross-session recurrence
  the loop exists to detect.

Both are fixed. The lesson generalises past this repo: **when a corpus disagrees with you,
suspect the instrument before the corpus.** The measurement said the cleanup ritual happened in
55% of sessions; it was really the reduction that could not see it.

## Scope, honestly

N sessions from one person across a few repos yields *your* workflow patterns, not general
laws. That's still worth having when the same hands are on 15 projects — just don't oversell it
to yourself.
