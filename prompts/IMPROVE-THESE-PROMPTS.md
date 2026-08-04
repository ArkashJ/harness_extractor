# Improving these prompts

Hand this to a strong model when you want the prompts here made better.

## The one rule

**Improve a prompt by running it, not by reading it.**

Reading a prompt and "improving" it produces a longer, prettier, more generic prompt. Every
model does this — it is the path of least resistance and it always feels productive. The result
is prompts that read beautifully and produce worse output.

The only evidence that a prompt got better is that **its output on real input got better**. So
every proposed change must come with: the input it was run on, what the output was before, what
it was after, and why the after is better on a stated criterion.

A change with no before/after is a stylistic opinion. Reject it.

## What is here, and its validation state

| Prompt | Purpose | Ever run? |
|---|---|---|
| `harvest.md` | extract corrections/falsifications/surprises/rework/gate-saves from one reduced session | **No** |
| `harvest.md` (synthesis section) | cross-session pattern-finding with a hold-out test | **No** — needs n≥5, corpus currently has ~2 usable |
| `repo-steward-SEED.md` | spec for a skill: preflight, propagation, visual verification | **No** — it is a spec, not a skill |
| `../RUNBOOK.md` | the end-to-end operator prompt | **No** |
| `PR-REVIEW-PROMPT.md` (in the Chantanl_175 repo, `docs/plans/`) | review a PR mixing QA evidence with fixes | **No** — written for PR #371, never used on it |

**None have been executed.** Treat all of them as v1 drafts with plausible-looking structure and
unknown behaviour. That is the honest starting point, and it means the highest-value work is
running them once, not restructuring them.

## What "better" means here, in priority order

1. **Produces findings the human would act on.** The named failure mode: harvest output that
   reads like generic engineering advice ("verify assumptions", "read the docs first"). True,
   useless, already written down. If a finding would apply to any project, the prompt failed.
2. **Falsifiable.** Every claim in the output should name evidence that could be checked, and
   the prompt should force the model to say what it could NOT determine.
3. **Shorter, at equal specificity.** These prompts are long because each paragraph exists to
   prevent a specific observed failure. Cutting a paragraph is good *if* you can name why that
   failure will not occur; cutting it because the prompt is long is not.
4. **Resistant to the model's own fluency.** The dangerous output here is a confident, coherent
   synthesis that is not true. The synthesis prompt's hold-out step exists for exactly this.
   Strengthen that pressure; do not soften it.

## Known weaknesses to attack

- **Category boundaries in `harvest.md` are fuzzy.** "Surprise" vs. "falsification" overlap. Does
  that ambiguity actually change the output? Test it before rewriting the definitions.
- **The five categories are asserted, not validated.** They came from introspecting one session.
  Run the harvest and check: do real findings fall cleanly into five buckets, or are there
  findings with nowhere to go, or empty buckets?
- **`repo-steward-SEED.md` mixes rules with the evidence for the rules.** Good for a human
  deciding whether to trust it; possibly bad as a skill, where it becomes noise. Splitting it may
  help — but only test that when converting it to a skill, not now.
- **`RUNBOOK.md` step 2 stops for human approval.** Verify a model actually stops there rather
  than steamrolling to step 3. If it does not stop, that instruction needs to be structural, not
  polite.
- **The synthesis prompt has never seen a real corpus.** It may ask for things that do not exist
  in actual findings files.

## The procedure

````
Improve the prompts in ~/developer/personal/extractor/prompts/ (and ../RUNBOOK.md).

Read IMPROVE-THESE-PROMPTS.md first. The rule it states is binding: improve by RUNNING, not by
reading. I will reject any change that arrives without before/after output on real input.

## Step 1 — establish the baseline before changing anything

Reduce a real session:
    cd ~/developer/personal/extractor
    ./harvest.py --list
    ./harvest.py <a substantial transcript> > out/baseline.md

Run harvest.md against out/baseline.md AS WRITTEN. Save the output to out/baseline-findings.yaml.
Do not fix the prompt yet. I want to see what it actually does.

## Step 2 — judge the baseline against criterion 1

For each finding, ask: would a competent engineer change their behaviour because of this?
Count how many are:
  (a) actionable and specific to this repo/workflow
  (b) true but generic — would apply to any project
  (c) restatements of what the session did
Report the counts. (b) and (c) are failures. If (b)+(c) is most of the output, the prompt's
problem is its extraction targets, not its wording — say so plainly rather than polishing prose.

## Step 3 — change ONE thing, re-run, diff

Pick the single largest cause of (b)/(c) findings. Change only that. Re-run on the SAME input.
Show me the before/after diff of the findings and state which criterion improved.

Repeat, one change at a time. Do not batch changes — with one input and no ground truth you
cannot attribute an improvement to a specific edit if you make five at once.

## Step 4 — adversarial pass on your own improvements

For each change you kept, argue the opposite case: how could this change make output worse on a
session unlike the one you tested? These prompts will run on sessions with very different shapes
(a 2-turn question, a 49-turn multi-agent orchestration). A change tuned to one shape can break
another.

Where you cannot rule that out, say so in the prompt itself as a known limitation rather than
pretending it generalises.

## Step 5 — report

- what you changed, and the before/after evidence for each
- what you deliberately did NOT change, and why
- which weaknesses in IMPROVE-THESE-PROMPTS.md you confirmed, and which turned out not to matter
- whether n=1 test session is enough to justify your changes, honestly

Do not lengthen these prompts unless the added text prevents a failure you actually observed.
````

## After improving

Re-run the whole `RUNBOOK.md` loop end to end once, and record in `synthesis/` what the improved
prompts produced versus what the originals did. That is the only durable evidence that this round
of work was worth doing — and if it was not, that is worth writing down too.
