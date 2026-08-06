#!/usr/bin/env python3
"""Reduce Claude Code session transcripts to the parts worth reading.

A transcript is millions of tokens; the reusable signal is a few dozen turns.
This does the MECHANICAL reduction only — find the real human turns, pair each
with what the assistant did next, flag the ones that look like corrections.
Judgement is the model's job (see prompts/harvest.md); heuristics here exist to
rank what a model reads first, not to decide anything.

  ./harvest.py --list                     # sessions on disk, newest first
  ./harvest.py <file.jsonl>               # reduce one session to markdown
  ./harvest.py --json <file.jsonl>        # same, machine-readable
  ./harvest.py --repeats <a.jsonl> <b...> # corrections recurring across sessions

stdlib only, no install.
"""
import argparse
import json
import pathlib
import re
import sys
from collections import Counter

ROOT = pathlib.Path.home() / ".claude" / "projects"

# A repeated instruction is the strongest signal in a transcript: it means a
# default behaviour is wrong. These patterns are deliberately over-inclusive —
# a false positive costs a model one line of reading, a false negative loses
# the finding entirely.
CORRECTION = re.compile(
    r"\b(no|nope|wrong|incorrect|actually|instead|don'?t|stop|not what|"
    r"why (did|are) you|i (told|said|asked)|again|still|but what about|"
    r"you (missed|forgot|always|never)|be honest|challenge)\b",
    re.I,
)
# Frustration and emphasis track cost better than politeness does.
EMPHASIS = re.compile(r"[!?]{2,}|\b[A-Z]{4,}\b")

# Injected into the user channel by the harness, not typed by a human. Missing these
# is not cosmetic: on a multi-agent session they outnumber real turns ~20:1 and every
# one matches the correction regex ("don't", "still", "again"), so the corrections
# count — the whole metric — becomes noise. Found by running this on a real
# 49-turn orchestration session, not by reading the code.
NOISE = (
    "<local-command-",
    "<command-name>",
    "<system-reminder>",
    "<task-notification>",
    "<teammate-message",
    "Another Claude session sent a message",
    "Caveat: The messages below",
    "[SYSTEM NOTIFICATION",
)


def text_of(msg) -> str:
    """Flatten a message's content to plain text; '' if it is not human prose."""
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if not isinstance(c, list):
        return ""
    out = []
    for b in c:
        if not isinstance(b, dict):
            continue
        # A user record carrying tool_result is the harness replying, not a human.
        if b.get("type") == "tool_result":
            return ""
        if b.get("type") == "text":
            out.append(b.get("text", ""))
    return "\n".join(out)


def err_tail(b) -> str | None:
    """First 160 chars of a failed tool_result; None if the result succeeded."""
    if not b.get("is_error"):
        return None
    c = b.get("content")
    if isinstance(c, list):
        c = " ".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text")
    if not isinstance(c, str):
        return None
    return " ".join(c.split())[:160] or None


def records(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def reduce_session(path):
    """-> (meta, turns). A turn is one human prompt + what the assistant did next."""
    meta, turns, pending = {}, [], None
    tools = Counter()

    for rec in records(path):
        msg = rec.get("message")
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        meta.setdefault("session", rec.get("sessionId"))
        meta.setdefault("cwd", rec.get("cwd"))
        meta.setdefault("start", rec.get("timestamp"))
        if rec.get("gitBranch"):
            meta["branch"] = rec["gitBranch"]
        meta["end"] = rec.get("timestamp") or meta.get("end")

        if role == "user":
            # Tool results ride the user channel. Before skipping them, mine failures —
            # without this, every gate that fired is invisible and gate-saves cannot be
            # harvested (the #1 blind spot named by all 21 harvests of 2026-08).
            if pending is not None and isinstance(msg.get("content"), list):
                for b in msg["content"]:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        tail = err_tail(b)
                        if tail and len(pending["failed"]) < 8:
                            pending["failed"].append(tail)
            if rec.get("isMeta"):
                continue
            body = text_of(msg).strip()
            # A slash-command invocation is signal (when did the human arm /start,
            # /wrap...), but its text must not feed the correction metric.
            cmd = re.search(r"<command-name>(/[\w:-]+)</command-name>", body)
            is_cmd = cmd is not None and not body.startswith("<local-command-")
            if cmd and is_cmd:
                body = f"[invoked {cmd.group(1)}]"
            # `!`-prefix shell passthrough: the command and its output are worth
            # reading (the human debugging by hand), but they are not human prose —
            # stderr usage text matches EMPHASIS and pollutes the metrics.
            is_shell = body.startswith(("<bash-input>", "<bash-stdout>"))
            not_prose = is_cmd or is_shell
            if not body or (not not_prose and body.startswith(NOISE)):
                continue
            if pending:
                turns.append(pending)
            pending = {
                "n": len(turns) + 1,
                "at": rec.get("timestamp"),
                "human": body,
                "correction": False if not_prose else bool(CORRECTION.search(body)),
                "emphatic": False if not_prose else bool(EMPHASIS.search(body)),
                "reply": "",
                "tools": [],
                "cmds": [],
                "failed": [],
            }
        elif role == "assistant" and pending is not None:
            for b in msg.get("content") or []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    name = b.get("name", "?")
                    tools[name] += 1
                    if len(pending["tools"]) < 12:
                        pending["tools"].append(name)
                    if name == "Bash" and len(pending["cmds"]) < 20:
                        cmd = " ".join(((b.get("input") or {}).get("command") or "").split())
                        if cmd:
                            pending["cmds"].append(cmd[:90])
                elif b.get("type") == "text" and len(pending["reply"]) < 700:
                    pending["reply"] += b.get("text", "")

    if pending:
        turns.append(pending)
    meta["human_turns"] = len(turns)
    meta["corrections"] = sum(t["correction"] for t in turns)
    meta["tool_failures"] = sum(len(t["failed"]) for t in turns)
    meta["tools"] = tools.most_common(8)
    return meta, turns


def as_markdown(meta, turns, cap):
    L = [f"# Session {meta.get('session','?')}", ""]
    L += [
        f"- repo: `{meta.get('cwd','?')}`  branch: `{meta.get('branch','?')}`",
        f"- {meta.get('start','?')} → {meta.get('end','?')}",
        f"- human turns: **{meta['human_turns']}**, likely corrections: "
        f"**{meta['corrections']}**, failed tool results: **{meta['tool_failures']}**",
        f"- tools: {', '.join(f'{k}×{v}' for k, v in meta['tools'])}",
        "",
        "Turns marked ⚠ matched a correction heuristic. That is a reading order, "
        "not a verdict — read the turn and decide.",
        "",
    ]
    for t in turns:
        flag = "⚠ " if t["correction"] else ""
        star = "‼️ " if t["emphatic"] else ""
        L.append(f"## {flag}{star}Turn {t['n']} · {t['at']}")
        L.append("")
        L.append("**Human:**")
        L.append("```")
        L.append(t["human"][:cap])
        L.append("```")
        if t["tools"]:
            L.append(f"**Did:** {', '.join(t['tools'])}")
        if t["cmds"]:
            L.append("**Ran:** " + " · ".join(f"`{c}`" for c in t["cmds"]))
        if t["failed"]:
            L.append(f"**Failed ({len(t['failed'])}):** " + " | ".join(t["failed"]))
        if t["reply"].strip():
            L.append("")
            L.append("**Said:** " + " ".join(t["reply"].split())[:400])
        L.append("")
    return "\n".join(L)


def find_repeats(paths):
    """Corrections whose wording recurs across sessions — a default that keeps failing."""
    seen = {}
    for p in paths:
        _, turns = reduce_session(p)
        for t in turns:
            if not t["correction"]:
                continue
            # crude shingle: content words, order-independent, len>3
            key = frozenset(w for w in re.findall(r"[a-z]{4,}", t["human"].lower()))
            for other, (op, otext) in list(seen.items()):
                if op == p:
                    continue
                inter = key & other
                union = key | other
                if union and len(inter) / len(union) > 0.25:
                    yield (p, t["human"][:180], op, otext[:180])
            seen[key] = (p, t["human"])


def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("paths", nargs="*", type=pathlib.Path)
    ap.add_argument("--list", action="store_true", help="sessions on disk, newest first")
    ap.add_argument("--since", metavar="YYYY-MM-DD", help="with --list: only sessions modified on/after this date")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--repeats", action="store_true", help="cross-session repeated corrections")
    ap.add_argument("--only-corrections", action="store_true")
    ap.add_argument("--cap", type=int, default=1600, help="max chars per human turn")
    a = ap.parse_args()

    if a.list:
        # The enumeration is the completeness contract: always print the untruncated
        # total, and mark what is already harvested. A silently capped listing caused
        # a real miss (2026-08-06: "3 new sessions" concluded when there were 19).
        files = sorted(ROOT.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if a.since:
            import datetime
            cut = datetime.datetime.fromisoformat(a.since).timestamp()
            files = [p for p in files if p.stat().st_mtime >= cut]
        findings_dir = pathlib.Path(__file__).resolve().parent / "findings"
        harvested = {f.stem.removeprefix("codex-")[:8] for f in findings_dir.glob("*.yaml")}
        shown = files if a.since else files[:40]
        for p in shown:
            mark = "  harvested" if p.stem[:8] in harvested else ""
            print(f"{p.stat().st_size / 1e6:7.1f}MB  {p}{mark}")
        new = sum(1 for p in files if p.stem[:8] not in harvested)
        tail = "" if len(shown) == len(files) else f" — SHOWING ONLY {len(shown)}, use --since"
        print(f"-- {len(files)} sessions, {new} unharvested{tail}")
        if not files:
            print(f"no transcripts under {ROOT}", file=sys.stderr)
        return

    if not a.paths:
        ap.error("give one or more .jsonl paths, or --list")

    if a.repeats:
        hits = list(find_repeats(a.paths))
        if not hits:
            print("no repeated corrections across these sessions.")
        for p, txt, op, otxt in hits:
            print(f"\n--- recurs across two sessions ---\n[{p.name}] {txt}\n[{op.name}] {otxt}")
        return

    for path in a.paths:
        meta, turns = reduce_session(path)
        if a.only_corrections:
            turns = [t for t in turns if t["correction"] or t["emphatic"]]
        if a.json:
            json.dump({"meta": meta, "turns": turns}, sys.stdout, indent=1, default=str)
            print()
        else:
            print(as_markdown(meta, turns, a.cap))


if __name__ == "__main__":
    main()
