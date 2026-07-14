"""classify_failures.py — wrong-answer mechanism classifier over rev-2 results JSONL.

The registered mechanism metric for the look-gate + cohort addendum
(plans/lb-hud-orchestration/13-look-gate-and-cohort-addendum.md). Promoted from the
2026-07-05 Wali-navigator failure postmortem, which found 46/48 wrong answers across
both arms were UNOBSERVED GUESSES (a commit answering a gate at a node never observed
since arrival, on gates whose answers are stated in the problem text).

For each wrong commit in each run it classifies:
  unobserved-guess  — answered a gate at a node not observed since arrival
  stale-value       — answer equals an EARLIER value of the asked variable (interference)
  other-var-value   — answer equals the current value of a DIFFERENT variable
  other-wrong       — observed, wrong, none of the above

Reads the DEG yaml (for the ladder + variable timeline) and one-or-more results JSONL
files; prints per-run rows and per-file aggregates. Read-only.

  docker exec labyrinth-bench-sandbox python cli/classify_failures.py \
      --deg rev-2 /results/rev2-look-gate-14b.jsonl /results/rev2-control-14b-topup.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import re

import yaml


def load_ladder(deg_id: str, degs_dir: str):
    """Walk the DEG from start following gated paths → ordered [(gate_id, sets_var, answer, problem)]
    and a per-variable value timeline."""
    deg = yaml.safe_load(open(os.path.join(degs_dir, f"{deg_id}.yaml")))
    node_by_id = {n["id"]: n for n in deg["nodes"]}
    gates = []
    cur = deg["nodes"][0]["id"]
    seen = set()
    while cur and cur not in seen:
        seen.add(cur)
        node = node_by_id.get(cur)
        if not node:
            break
        nxt = None
        for p in node.get("paths", []):
            if p.get("gate"):
                g = p["gate"]
                gates.append((g.get("gate_id", "?"), g.get("sets_var") or "",
                              str(g.get("answer", "")), g.get("problem", "")))
                nxt = p.get("destination")
                break
        cur = nxt
    var_history: dict[str, list[tuple[int, str]]] = {}
    for i, (gid, sets, ans, prob) in enumerate(gates):
        if sets:
            m = re.search(r"(?:initialized to|is now)\s+(-?\d+)", prob)
            var_history.setdefault(sets, []).append((i, m.group(1) if m else ans))
    return gates, var_history


def asked_var(prob: str):
    m = re.search(r"value of ([A-H])\b", prob)
    return m.group(1) if m else None


def classify_run(row: dict, gates, var_history):
    def vals_before(var, gi):
        return [v for i, v in var_history.get(var, []) if i < gi]

    def current_values_at(gi):
        out = {}
        for var, hist in var_history.items():
            vs = [v for i, v in hist if i < gi]
            if vs:
                out[var] = vs[-1]
        return out

    gate_idx = 0
    observed_here = True  # control/look-gate both bootstrap an observe
    classes: dict[str, int] = {}
    wrongs: list[tuple[int, str, str, str]] = []  # (1-based ladder pos, gate_id, class, given)
    observes = commits = 0
    for t in row.get("turns_log", []):
        ap = t.get("action_parsed") or {}
        act = ap.get("action")
        etext = t.get("engine_text", "") or ""
        if act == "observe":
            observes += 1
            observed_here = True
        elif act == "commit" and str(ap.get("answer") or "").strip():
            commits += 1
            gid, sets, true_ans, prob = gates[gate_idx] if gate_idx < len(gates) else ("?", "", "?", "")
            given = str(ap.get("answer", ""))
            if "WRONG" in etext:
                v = asked_var(prob) or sets
                if not observed_here:
                    k = "unobserved-guess"
                elif v and given in vals_before(v, gate_idx)[:-1]:
                    k = "stale-value"
                elif given in [val for kv, val in current_values_at(gate_idx).items() if kv != v]:
                    k = "other-var-value"
                else:
                    k = "other-wrong"
                classes[k] = classes.get(k, 0) + 1
                wrongs.append((gate_idx + 1, gid, k, given))
            elif "CORRECT" in etext:
                gate_idx += 1
                observed_here = False
        elif act == "commit":
            observed_here = False
    return {"observes": observes, "commits": commits, "classes": classes, "wrongs": wrongs}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deg", default="rev-2")
    ap.add_argument("--degs-dir", default=os.environ.get("DEGS_DIR", "/app/degs"))
    ap.add_argument("--label", help="only rows whose run_label matches (for interleaved multi-arm files)")
    ap.add_argument("--detail", action="store_true", help="print each wrong commit's ladder position + gate_id")
    ap.add_argument("files", nargs="+", help="results JSONL file(s)")
    args = ap.parse_args()

    gates, var_history = load_ladder(args.deg, args.degs_dir)
    print(f"DEG {args.deg}: {len(gates)} gates; init ladder = read-and-echo through the first sets_var run\n")
    grand: dict[str, int] = {}
    tot_obs = tot_cmt = 0
    for path in args.files:
        rows = [json.loads(l) for l in open(path) if l.strip() and "error" not in json.loads(l)]
        if args.label:
            rows = [r for r in rows if r.get("run_label") == args.label]
        label_s = f" label={args.label}" if args.label else ""
        print(f"== {os.path.basename(path)}{label_s} ({len(rows)} runs) ==")
        fobs = fcmt = 0
        fclasses: dict[str, int] = {}
        for r in rows:
            st = classify_run(r, gates, var_history)
            fobs += st["observes"]; fcmt += st["commits"]
            for k, v in st["classes"].items():
                fclasses[k] = fclasses.get(k, 0) + v
            lg = r.get("look_gate_interceptions")
            lg_s = f" look_gate_intercepts={lg}" if lg is not None else ""
            print(f"  depth={r.get('ramp_depth'):>2}  obs/cmt={st['observes']}/{st['commits']}"
                  f"  wrong={st['classes']}{lg_s}")
            if args.detail:
                for pos, gid, k, given in st["wrongs"]:
                    print(f"      gate {pos:>2} ({gid}): {k}  given={given}")
        print(f"  FILE: obs/commit={fobs/max(fcmt,1):.2f}  wrong-classes={fclasses}\n")
        tot_obs += fobs; tot_cmt += fcmt
        for k, v in fclasses.items():
            grand[k] = grand.get(k, 0) + v
    print(f"GRAND: obs/commit={tot_obs/max(tot_cmt,1):.2f}  wrong-classes={grand}")


if __name__ == "__main__":
    main()
