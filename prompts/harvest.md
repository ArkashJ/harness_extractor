# Session harvest prompt

Point this at one or more **reductions** produced by `harvest.py` (see RUNBOOK Phase A) to
extract the reusable signal. If you only have raw JSONL, run `./harvest.py <transcript>` first —
transcripts live at `~/.claude/projects/<url-encoded-cwd>/<session-uuid>.jsonl`.

---

## Design decision behind this prompt

Do **not** ask a model to extract "learnings". You will get generic advice — "read the docs
first", "verify assumptions" — which is true, useless, and already written down everywhere.

The signal in a session transcript is concentrated in a few dozen tokens out of millions, at
exactly these moments:

1. **Corrections** — the human said the model was wrong, or redirected it.
2. **Falsifications** — the model asserted something, tested it, and was wrong.
3. **Surprises** — reality differed from what a doc, a comment, or a plan claimed.
4. **Rework** — work that had to be redone, and what would have prevented it.
5. **Gate saves** — an automated check caught something a human/model missed.

Everything else is throughput, not signal. A harvest that summarises the *work* produces a
status report. A harvest that extracts the *corrections* produces something you can act on.

---

## The prompt

````
Harvest reusable engineering signal from the session reduction(s) at:
<PATHS>

The input is a REDUCTION produced by harvest.py, not a raw transcript. Its format: a header
(repo, branch, duration, human-turn and tool counts), then one section per human turn with the
human's text (long turns truncated), a `**Did:**` line listing tool names — file-touching tools
carry their path, `Edit(docs/roadmap.md)`, so this line is how you tell WHAT a session changed,
not merely that it edited something — a `**Ran:**` line
with the turn's Bash commands (truncated at 90 chars each), a `**Failed (N):**` line with the
first 160 chars of each failed tool result, and a `**Said:**` excerpt of the assistant's prose
(truncated at ~400 chars). Turns marked ⚠ matched a correction heuristic — that is a reading
order, not a verdict. `**Failed**` lines are gate-fire candidates: a failure the model then
fixed without human help is a GATE SAVE; a failure the human had to point out is not. But
`Failed (N)` **over-counts gate fires**: a working script that exits 1 lands in that list, and
in one session 5 of 8 "failures" were a single commit-replay script succeeding noisily
(4a337317). Read the text before scoring a failure as a gate.

Remaining blind spots — say when a finding is limited by them: successful tool output is still
elided, and truncated prose hides self-noticed falsifications.

**Write the header one key per line.** 35 of the first 84 findings files fail `yaml.safe_load`
because the header packed `repo: X    branch: Y` onto one line, which makes the corpus
greppable but not parseable — and the whole point of findings is aggregating them.

## Extract ONLY these five categories

For each, capture: what happened, the evidence, and — most important — **what cheap check would
have caught it earlier**.

1. CORRECTIONS. Human turns that push back, redirect, or say the model was wrong.
   Signals: "no", "actually", "that's wrong", "why did you", "I told you", "don't", "instead",
   frustration, or a repeated instruction. Repeated instructions are the strongest signal in the
   whole transcript — they mean a default behaviour is wrong.

2. FALSIFICATIONS. The model asserted something, then tested it, and the test disagreed.
   These are gold: they are the only places you can see the difference between plausible and
   true. Note whether the model noticed on its own or had to be told.

3. SURPRISES. Reality differed from a documented claim — a doc, a code comment, a plan, a
   ticket. Record which artifact was wrong, and whether it was auto-loaded into context (agent
   instruction files) or read voluntarily. Auto-loaded drift is far more expensive.

4. REWORK. Work redone, discarded, or reconciled. For each, name the single earliest point at
   which it could have been avoided.

5. GATE SAVES. An automated check (test, linter, type check, CI assertion) caught something no
   human or model spotted. These tell you which gates are earning their keep — and by absence,
   which classes of bug have no gate.

One finding per root cause. If a miss and the rework it caused share a root cause, report ONE
finding — categorized by the root cause — with the rework in `cost`. Two findings that share an
`earliest_catch` are one finding. Name any subsumed lesson inside the merged finding rather than
dropping it (a falsification absorbed into a bigger miss still carries its own behavioral rule).

## Deliberately do NOT extract

- Summaries of what was built. You have the diff for that.
- Anything derivable from the code or the git history.
- Generic advice. If it would apply to any project, it is not signal.
- Praise, or narrative of successful work.

## Output

```yaml
session: <uuid>
repo: <cwd>            branch: <gitBranch>       duration: <first→last timestamp>
human_turns: <n>       corrections: <n>          falsifications: <n>

findings:
  - id: <slug>
    category: correction | falsification | surprise | rework | gate-save
    what: <one sentence>
    evidence: <quote or file:line — must be verifiable in the transcript>
    cost: <time, rework, or wrong output that resulted>
    earliest_catch: <the cheapest check that would have caught it, as a command if possible>
    generality: repo-specific | workflow-specific | general
    recurring: <true if this same finding appears elsewhere in the session>
```

`generality` matters more than it looks. Only `general` findings belong in a skill;
`repo-specific` ones belong in that repo's agent-instruction file; `workflow-specific` ones
belong in your personal setup. Mixing them is why most extracted "learnings" are unusable.

## Then, and only then

Rank findings by `cost × recurring`. Report the top five with a concrete proposed change, and
state explicitly which of those changes is a **gate** (automated, permanent) versus a
**practice** (relies on someone remembering). Prefer gates. A practice that relies on memory has
already failed once in this transcript.

Finally: state what you could NOT determine from the transcript, and why.
````

---

## Cross-session synthesis (run after ~5+ harvests)

````
You have <N> harvest outputs from separate sessions at <PATHS>.

Find findings that RECUR across sessions. A finding appearing once is an anecdote; the same
failure in three different repos is a law worth encoding.

For each recurring finding:
- how many sessions, and were the repos/stacks different? (same-repo recurrence is much weaker
  evidence than cross-repo)
- is the proposed fix a gate or a practice?
- what would falsify it — i.e. what would you expect to see if it were NOT a real pattern?

**Hold out at least one session.** Derive your conclusions from the rest, then check them
against the held-out one. Report every conclusion the held-out session contradicts. A synthesis
that survives no held-out test is a plausible narrative, not a finding — and plausible narrative
is exactly what a strong model produces most fluently.

Report separately:
- CROSS-REPO patterns (candidates for a skill or tooling)
- SINGLE-REPO patterns (belong in that repo's instruction file)
- PERSONAL workflow patterns (belong in your global config)

Do not merge those three. That merge is the most common way this kind of synthesis becomes
unusable.
````
