# Weekly harvest mission (run headless by cron)

You are in ~/Developer/personal/extractor. Read RUNBOOK.md and prompts/harvest.md first.

1. REDUCE: `./harvest.py --list`; reduce every transcript newer than the newest file in
   findings/ and ≥5 human turns to out/. Sanity-check human-turn counts per RUNBOOK Phase A.
2. HARVEST: apply prompts/harvest.md to each new reduction (cheap-model subagents are fine).
   Write findings/<uuid8>.yaml. Patterns, not payloads — no client names/addresses/credentials.
3. SYNTHESIZE: if ≥3 new findings files, re-run the cross-session synthesis with at least one
   held-out session; write synthesis/<date>.md including contradicted conclusions.
4. ATTRIBUTE: for each new finding, check ~/.claude/commands/*.md — did a rule exist that
   should have prevented it? Tag each finding: rule-failed(<command>:<rule>) | no-rule |
   rule-working. Also compute the nag-turn metric: count of human turns matching
   status-polling / commit-nagging / are-you-sure per session, and compare with the baseline in
   synthesis/2026-08-04-cross-session.md §4.
5. PROPOSE: for rule-failed and no-rule findings, create a branch in ~/.claude/commands
   (`git -C ~/.claude/commands checkout -b patch/<date>`), commit the proposed command edits
   with the transcript evidence and expected metric in the commit message. NEVER merge —
   leave the branch for human review. Return to the previous branch after.
6. COMMIT here: findings/ and synthesis/ in logical commits. Do not push anything anywhere
   without a configured remote already existing.

Hard rules: no merges, no pushes to new remotes, no deletions outside out/, nothing
irreversible. If a step fails, record it in out/cron-failures.log and continue.
