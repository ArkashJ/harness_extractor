# Runbook — transcripts → findings → gates

Where things live, and the one prompt that drives the whole loop.

## Storage

| Path | Contents | Committed? | Why |
|---|---|---|---|
| `~/.claude/projects/**/*.jsonl` | raw transcripts | n/a — outside repo | written automatically, never edit |
| `out/` | reductions from `harvest.py` | **no** | regenerable, and they carry **verbatim client content** — a real reduction here contains a client name, street address and a `CONFIDENTIAL` marking |
| `findings/` | model harvest output, one file per session | **yes** | model judgement; not reproducible by re-running |
| `synthesis/` | cross-session synthesis + held-out results | **yes** | the actual deliverable |

**The rule that keeps this safe to commit: findings record *patterns*, not *payloads*.**
"An agent-instruction file asserted a directory was untracked; it was tracked" is a pattern.
Quoting the client's name is a payload. If a finding cannot be written without the payload, it is
repo-specific and belongs in that repo, not here.

---

## Phase A — reduce (mechanical, seconds, no model)

```bash
cd ~/developer/personal/extractor
./harvest.py --list                                   # pick sessions
./harvest.py <transcript.jsonl> > out/<label>.md      # 5.5MB → ~16KB
```

Sanity-check before spending model time: does `human turns` look like the number of things you
actually typed? If a 49-turn session shows 200, the noise filter is missing a new harness message
type — fix `NOISE` in `harvest.py` first. Everything downstream inherits that error silently.

## Phase B — harvest one session (model)

Start with **one**. If the findings read as generic advice, fix the prompt before scaling —
do not burn ten sessions on a bad extractor.

## Phase C — harvest the rest, then synthesize with a hold-out

## Phase D — convert survivors to gates

A finding that becomes a CI assertion is enforced across every project, forever, without anyone
remembering. A finding that becomes a paragraph relies on memory — and it already failed once,
which is why it is in the corpus.

---

## The prompt

Paste this into a fresh session in `~/developer/personal/extractor`.

````
You are running a learning-harvest over my Claude Code session transcripts.

REPO: ~/developer/personal/extractor   (harvest.py, prompts/, findings/, synthesis/)
Read README.md and prompts/harvest.md before starting.

## Ground rules

- `harvest.py` does mechanics; you do judgement. Do not re-implement classification in Python,
  and do not read raw .jsonl into context — always work from a reduction in out/.
- Reductions contain verbatim client content. Never paste them into a committed file, an issue,
  or a PR. findings/ records patterns, not payloads.
- If you cannot determine something from the transcript, say so. Do not infer intent from
  absence — a thing not appearing in a transcript usually means it was not attempted, not that
  it failed.

## Step 1 — reduce and sanity-check

Run `./harvest.py --list`, pick the N most recent substantial sessions (skip <5 turns), and
reduce each to out/<repo>-<date>.md.

Then verify the reduction is sound before trusting it: for each, does `human turns` roughly match
a plausible number of typed messages? Harness-injected blocks (`<task-notification>`,
`<teammate-message>`, `[SYSTEM NOTIFICATION`) are NOT human turns and every one of them matches
the correction regex. If counts look inflated, add the offending prefix to NOISE in harvest.py,
re-run, and say what you changed. This has already happened once: a 49-turn session reported 39
corrections where there were 4.

## Step 2 — harvest ONE session first

Apply prompts/harvest.md to a single reduction. Extract only: corrections, falsifications,
surprises, rework, gate-saves. Write findings/<session>.yaml.

Then STOP and show me. I want to judge whether these are things I would act on before you do
nine more. If they read like generic engineering advice ("verify assumptions", "read the docs"),
the extraction is wrong — say so rather than continuing.

## Step 3 — harvest the rest

Only after I approve step 2. One findings/<session>.yaml per session.
Tag every finding `repo-specific | workflow-specific | general`. Never merge those buckets —
that merge is the main way extracted learnings become unusable.

## Step 4 — synthesize, with a hold-out

Use the cross-session prompt at the bottom of prompts/harvest.md.

HOLD OUT at least one session. Derive conclusions from the rest, then test them against the
held-out one and report every conclusion it contradicts. A synthesis that survives no held-out
test is a plausible narrative, not a finding — and plausible narrative is what a strong model
produces most fluently. Write synthesis/<date>.md including the failures.

Also compute the honest metric: **repeat-correction rate**. Run `./harvest.py --repeats` over
all sessions. Does a correction from an early session recur in a later one? If yes, the loop is
not closing. Note that the similarity threshold (0.25 Jaccard) is UNTUNED — it found nothing at
n=3, which could mean "no repeats" or "too strict". Tune it now that n is larger, and say what
you tuned it to and why.

## Step 5 — route the output, and prefer gates

For each surviving finding, propose exactly one destination:
  - general        → a skill (see prompts/repo-steward-SEED.md) or harvest.py itself
  - repo-specific  → that repo's CLAUDE.md, as a CONCLUSION not a state fact
  - workflow       → my global config

For each, say whether it can be a GATE (a CI assertion, a test, a hook — automated and
permanent) or only a PRACTICE (relies on someone remembering). Prefer gates and say so
explicitly. A practice has already failed once, which is why it is in the corpus.

## Step 6 — report

Top five findings by (cost × recurrence). For each: what, evidence, cheapest earliest catch,
destination, gate-or-practice.

Then tell me plainly:
  - what you could NOT determine, and why
  - whether the corpus is large enough to support the conclusions, or whether I am
    over-reading N sessions from one person across a few repos
  - which of my existing habits this evidence says I should STOP doing

Be adversarial on that last one. I do not want a list of things to add.
````

---

## Cadence

Harvest after any session that felt like it went badly, and monthly regardless. The bad ones
carry the most signal; the routine ones tell you whether the last change worked.
