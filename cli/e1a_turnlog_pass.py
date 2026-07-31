#!/usr/bin/env python3
"""E1a turns_log content pass — re-derivation volume + perseveration check.

Two questions the Table-1 brief left open (both read straight from the campaign
JSONLs' ``turns_log``; no new runs):

1. RE-DERIVATION (the wall-clock anomaly): wiped runs finish in fewer turns but
   often MORE wall-clock. Hypothesis (Will, 2026-07-14): the wipe discards the
   model's own derivation chain, so it re-derives from the recall block every
   turn — visible as per-turn output volume (``model_reasoning`` + ``model_text``
   chars) rising in the wiped arm vs control.

2. PERSEVERATION (the llama3.3:70b reversal): its wiped runs stall at the same
   depth every time. Do the 4 life-burning wrong commits repeat the SAME answer
   at the SAME gate (perseveration proper), or scatter (arithmetic failure)?

Usage:
  python3 e1a_turnlog_pass.py --results-dir <dir of e1a-*.jsonl> [--wrong-detail MODEL ...]
"""
import argparse
import glob
import json
import os
import re

_FNAME_RE = re.compile(r"^e1a-(?P<safe>.+)-(?P<arm>control|wiped)\.jsonl$")
_CORRECT_RE = re.compile(r"Gate answer: (CORRECT|INCORRECT|WRONG)")
_LOC_RE = re.compile(r"Location: (\S+)")


def rows(path):
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "error" not in r:
                yield r


def discover(results_dir):
    cells = {}
    for p in sorted(glob.glob(os.path.join(results_dir, "e1a-*.jsonl"))):
        m = _FNAME_RE.match(os.path.basename(p))
        if m:
            cells.setdefault(m.group("safe"), {})[m.group("arm")] = list(rows(p))
    return cells


def volume_pass(cells):
    print("== Re-derivation pass: per-turn output volume (chars/turn, cell mean) ==")
    print(f"{'model':<42} {'arm':<8} {'reason':>8} {'text':>6} {'total':>7} {'turns':>6} {'sec/turn':>9}")
    for safe, arms in sorted(cells.items()):
        if "wiped" not in arms:
            continue
        for arm in ("control", "wiped"):
            runs = arms.get(arm) or []
            rl = tl = n = 0
            secs = turns = 0.0
            for r in runs:
                for t in r.get("turns_log") or []:
                    rl += len(t.get("model_reasoning") or "")
                    tl += len(t.get("model_text") or "")
                    n += 1
                secs += r.get("elapsed_seconds") or 0.0
                turns += r.get("turns") or 0
            if n:
                print(f"{safe:<42} {arm:<8} {rl/n:>8.0f} {tl/n:>6.0f} {(rl+tl)/n:>7.0f} "
                      f"{n:>6} {secs/turns if turns else 0:>9.1f}")
        print()


def wrong_commits(run):
    """(location, answer, correct_bool) per gate-scored commit, in turn order."""
    out = []
    loc = "start"
    for t in run.get("turns_log") or []:
        ap = t.get("action_parsed") or {}
        et = t.get("engine_text") or ""
        m = _CORRECT_RE.search(et)
        if ap.get("action") == "commit" and m:
            out.append((loc, str(ap.get("answer")), m.group(1) == "CORRECT"))
        ml = _LOC_RE.search(et)
        if ml:
            loc = ml.group(1)
    return out


def perseveration_pass(cells, models):
    print("== Perseveration pass: wrong-commit sequences (location, answer) ==")
    for safe in models:
        arms = cells.get(safe)
        if not arms:
            print(f"{safe}: no data")
            continue
        for arm in ("control", "wiped"):
            for i, run in enumerate(arms.get(arm) or []):
                wrongs = [(l, a) for l, a, ok in wrong_commits(run) if not ok]
                uniq_ans = {a for _, a in wrongs}
                uniq_loc = {l for l, _ in wrongs}
                tag = ""
                if len(wrongs) >= 2 and len(uniq_ans) == 1 and len(uniq_loc) == 1:
                    tag = "  <- PERSEVERATION (same gate, same answer)"
                print(f"{safe} {arm} run{i}: depth={run.get('ramp_depth')} "
                      f"wrongs={wrongs}{tag}")
        print()


def main():
    ap = argparse.ArgumentParser(description="E1a turns_log content pass")
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--wrong-detail", nargs="*", default=["llama3-3-70b", "llama4-scout"],
                    help="models for the perseveration pass (safe names)")
    args = ap.parse_args()
    cells = discover(args.results_dir)
    volume_pass(cells)
    perseveration_pass(cells, args.wrong_detail)


if __name__ == "__main__":
    main()
