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

Python 3.10+; runtime dependencies: none.
"""
import argparse
import datetime
import json
import pathlib
import re
import sys
from collections import Counter

__version__ = "1.0.0"

ROOT = pathlib.Path.home() / ".claude" / "projects"

CORRECTION = re.compile(
    r"\b(no|nope|wrong|incorrect|actually|instead|don'?t|stop|not what|"
    r"why (did|are) you|i (told|said|asked)|again|still|but what about|"
    r"you (missed|forgot|always|never)|be honest|challenge)\b",
    re.I,
)
EMPHASIS = re.compile(r"[!?]{2,}|\b[A-Z]{4,}\b")
# Harness notifications can outnumber human turns and contain correction keywords.
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
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                yield record


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
            # Failed results arrive as harness-authored user records on the pending turn.
            if pending is not None and isinstance(msg.get("content"), list):
                for b in msg["content"]:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        tail = err_tail(b)
                        if tail and len(pending["failed"]) < 8:
                            pending["failed"].append(tail)
            if rec.get("isMeta"):
                continue
            body = text_of(msg).strip()
            cmd = re.search(r"<command-name>(/[\w:-]+)</command-name>", body)
            is_cmd = cmd is not None and not body.startswith("<local-command-")
            if cmd and is_cmd:
                body = f"[invoked {cmd.group(1)}]"
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
                    # Bare tool names hide which artifact changed; retain a short path label.
                    fp = (b.get("input") or {}).get("file_path")
                    label = f"{name}({'/'.join(pathlib.Path(fp).parts[-2:])})" if fp else name
                    if len(pending["tools"]) < 12:
                        pending["tools"].append(label)
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


def as_markdown(meta, turns, cap=1600):
    L = [f"# Session {meta.get('session','?')}", ""]
    L += [
        f"- repo: `{meta.get('cwd','?')}`  branch: `{meta.get('branch','?')}`",
        f"- {meta.get('start','?')} → {meta.get('end','?')}",
        f"- human turns: **{meta['human_turns']}**, likely corrections: **{meta['corrections']}**, failed tool results: **{meta['tool_failures']}**",
        f"- tools: {', '.join(f'{k}×{v}' for k, v in meta['tools'])}", "",
        "Turns marked ⚠ matched a correction heuristic. That is a reading order, not a verdict — read the turn and decide.", "",
    ]
    for t in turns:
        flag = "⚠ " if t["correction"] else ""
        star = "‼️ " if t["emphatic"] else ""
        L.append(f"## {flag}{star}Turn {t['n']} · {t['at']}")
        L.append("")
        L.append("**Human:**")
        human = t["human"][:cap]
        fence = "`" * max(3, max((len(run) for run in re.findall(r"`+", human)), default=0) + 1)
        L.append(fence)
        L.append(human)
        L.append(fence)
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
            key = frozenset(w for w in re.findall(r"[a-z]{4,}", t["human"].lower()))
            for other, (op, otext) in list(seen.items()):
                if op == p:
                    continue
                inter = key & other
                union = key | other
                if union and len(inter) / len(union) > 0.25:
                    yield (p, t["human"][:180], op, otext[:180])
            seen[key] = (p, t["human"])


def dedupe_forks(files):
    """-> (kept, dropped). Keep the longer continuation of each session fork."""
    # Forks share cwd/first timestamp; counting both manufactures repeat evidence.
    files = [pathlib.Path(path) for path in files]
    best = {}
    for p in files:
        key = None
        try:
            with p.open(encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh):
                    if i >= 50:
                        break
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if rec.get("timestamp"):
                        key = (rec.get("cwd"), rec["timestamp"])
                        break
        except Exception:
            key = None
        if key is None:
            key = (None, str(p))
        prev = best.get(key)
        if prev is None or p.stat().st_size > prev.stat().st_size:
            best[key] = p
    kept = set(best.values())
    return [p for p in files if p in kept], [p for p in files if p not in kept]


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0], allow_abbrev=False)
    ap.add_argument("paths", nargs="*", type=pathlib.Path)
    ap.add_argument("--list", action="store_true", default=argparse.SUPPRESS, help="sessions on disk, newest first")
    ap.add_argument("--since", metavar="YYYY-MM-DD", default=argparse.SUPPRESS, help="with --list: only sessions modified on/after this date")
    ap.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="machine-readable output")
    ap.add_argument("--repeats", action="store_true", default=argparse.SUPPRESS, help="cross-session repeated corrections")
    ap.add_argument("--only-corrections", action="store_true", default=argparse.SUPPRESS)
    ap.add_argument("--cap", type=int, default=argparse.SUPPRESS, help="max chars per human turn")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument("--root", type=pathlib.Path, default=argparse.SUPPRESS)
    ap.add_argument("--findings-dir", type=pathlib.Path, default=argparse.SUPPRESS)
    a = ap.parse_args(arguments)

    supplied = set(vars(a))
    list_mode = getattr(a, "list", False)
    repeats_mode = getattr(a, "repeats", False)
    if "cap" in supplied and a.cap <= 0:
        ap.error("--cap must be positive")
    if "since" in supplied and not list_mode:
        ap.error("--since requires --list")
    if not list_mode and supplied & {"root", "findings_dir"}:
        ap.error("--root and --findings-dir require --list")
    if list_mode and supplied & {"json", "repeats", "only_corrections", "cap"}:
        ap.error("--list does not accept --json, --repeats, --only-corrections, or --cap")
    if repeats_mode and supplied & {"json", "only_corrections", "cap"}:
        ap.error("--repeats does not accept --json, --only-corrections, or --cap")
    if list_mode and a.paths:
        ap.error("--list does not accept input paths")

    a.list = list_mode
    a.repeats = repeats_mode
    a.json = getattr(a, "json", False)
    a.only_corrections = getattr(a, "only_corrections", False)
    a.cap = getattr(a, "cap", 1600)
    a.since = getattr(a, "since", None)
    a.root = getattr(a, "root", ROOT)
    a.findings_dir = getattr(a, "findings_dir", pathlib.Path.cwd() / "findings")

    if a.list:
        files = sorted(a.root.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        files, dupes = dedupe_forks(files)
        if "since" in supplied:
            try:
                cut = datetime.date.fromisoformat(a.since)
                if cut.isoformat() != a.since:
                    raise ValueError
            except ValueError:
                ap.error("--since must be YYYY-MM-DD")
            cut = datetime.datetime.combine(cut, datetime.time()).timestamp()
            files = [p for p in files if p.stat().st_mtime >= cut]
        harvested = {f.stem.removeprefix("codex-")[:8] for f in a.findings_dir.glob("*.yaml")}
        shown = files if a.since else files[:40]
        for p in shown:
            mark = "  harvested" if p.stem[:8] in harvested else ""
            print(f"{p.stat().st_size / 1e6:7.1f}MB  {p}{mark}")
        new = sum(1 for p in files if p.stem[:8] not in harvested)
        tail = "" if len(shown) == len(files) else f" — SHOWING ONLY {len(shown)}, use --since"
        dupe_note = f", {len(dupes)} fork duplicate(s) hidden" if dupes else ""
        print(f"-- {len(files)} sessions, {new} unharvested{dupe_note}{tail}")
        if not files:
            print(f"no transcripts under {a.root}", file=sys.stderr)
        return 0

    if not a.paths:
        ap.error("give one or more .jsonl paths, or --list")

    if a.repeats:
        try:
            hits = list(find_repeats(a.paths))
        except OSError as error:
            print(f"harness-extractor: {error}", file=sys.stderr)
            return 1
        if not hits:
            print("no repeated corrections across these sessions.")
        for p, txt, op, otxt in hits:
            print(f"\n--- recurs across two sessions ---\n[{p.name}] {txt}\n[{op.name}] {otxt}")
        return 0

    payloads = []
    try:
        for path in a.paths:
            meta, turns = reduce_session(path)
            if a.only_corrections:
                turns = [t for t in turns if t["correction"] or t["emphatic"]]
            payloads.append((meta, turns))
    except OSError as error:
        print(f"harness-extractor: {error}", file=sys.stderr)
        return 1

    if a.json:
        json.dump([{"meta": meta, "turns": turns} for meta, turns in payloads], sys.stdout, indent=1, default=str)
        print()
    else:
        for meta, turns in payloads:
            print(as_markdown(meta, turns, a.cap))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
