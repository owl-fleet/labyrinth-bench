#!/usr/bin/env python3
"""Null-baseline control: a seeded random walker with zero knowledge, entered on the board.

The negative control the board publishes so "gates can't be passed by chance" is a datum,
not a claim: at every turn the walker commits to a uniformly-random path from the current
node (including back, when available) with a uniformly-random answer drawn from
{TRUE, FALSE, random integer 0–100} for gated paths. No model, no observation reading,
no memory — chance-level everything. A nonzero median depth here would mean the gate bank
is guessable and the instrument is broken.

Deterministic: the whole campaign is a pure function of (--deg, --runs, --seed). Output:
  results/null-baseline/null_random_walk.jsonl  — one score row per run, replay-verifiable
                                                  with cli/verify.py (turns_log included)
  entries/control-null-random-walk.json         — the board entry, control_row=true

Usage: python3 cli/run_null_baseline.py [--deg nav-3] [--runs 200] [--seed 1337]
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli.seed_entries import (  # noqa: E402
    BOOTSTRAP_B, BOOTSTRAP_LEVEL, BOOTSTRAP_SEED, bootstrap_ci_lower,
)
from engine.graph import load_all_degs  # noqa: E402
from engine.runner import new_session  # noqa: E402


def random_answer(rng: random.Random) -> str:
    pick = rng.randrange(3)
    if pick == 0:
        return "TRUE"
    if pick == 1:
        return "FALSE"
    return str(rng.randint(0, 100))


def run_one(deg, rng: random.Random, max_turns: int = 500) -> dict:
    session = new_session(deg)
    turns_log = []
    turn = 0
    while not session.completed and turn < max_turns:
        turn += 1
        node = session.current_node
        options = [p.id for p in node.paths]
        if session.traversal_stack:
            options.append("back")
        if not options:  # dead end with no way back: only the engine's traps can end this
            session.observe()
            turns_log.append({"turn": turn, "action_parsed": {"action": "observe"}, "engine_text": ""})
            continue
        path_id = rng.choice(options)
        answer = random_answer(rng)
        session.commit(path_id, answer)
        turns_log.append({
            "turn": turn,
            "action_parsed": {"action": "commit", "path_id": path_id, "answer": answer},
            "engine_text": "",
        })
    score = session.score()
    score["model"] = "null-random-walk"
    score["turns"] = turn
    score["turns_log"] = turns_log
    return score


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deg", default="nav-3", help="DEG id to walk (default: nav-3, the cohort corridor)")
    ap.add_argument("--runs", type=int, default=200)
    ap.add_argument("--seed", type=int, default=BOOTSTRAP_SEED)
    ap.add_argument("--degs", type=Path, default=Path(__file__).resolve().parent.parent / "degs")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent)
    args = ap.parse_args()

    degs = load_all_degs(args.degs)
    if args.deg not in degs:
        print(f"ERROR: unknown DEG {args.deg!r}", file=sys.stderr)
        return 2
    deg = degs[args.deg]

    campaign_seed = f"{args.seed}:null-random-walk:{args.deg}"
    rng = random.Random(campaign_seed)
    rows = [run_one(deg, rng) for _ in range(args.runs)]

    results_dir = args.out / "results" / "null-baseline"
    results_dir.mkdir(parents=True, exist_ok=True)
    results_path = results_dir / "null_random_walk.jsonl"
    with open(results_path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    depths = [r["ramp_depth"] for r in rows]
    exits = sum(1 for r in rows if r["found_exit"])
    entry_seed = f"{args.seed}:null-random-walk:{args.deg}:entry"
    entry = {
        "schema_version": 1,
        "entry_id": "control-null-random-walk",
        "lane": "model",
        "origin": "board-seed",
        "control_row": True,
        "season": 0,
        "source": {
            "dataset": str(results_path.relative_to(args.out)),
            "arm": "null",
            "campaign_seed": campaign_seed,
            "deg_id": args.deg,
        },
        "declared": {"planned_n": args.runs, "source": "cli/run_null_baseline.py --runs"},
        "artifacts": {"harness_container": None, "model_file": None},
        "model": {
            "id": "null-random-walk",
            "display": "Random walk",
            "quantization": None,
            "digest": None,
        },
        "harness": {
            "name": "null",
            "summary": ("Negative control — seeded random path + random answer, no model. "
                        "Proves gates aren't guessable; a nonzero median here would indict "
                        "the instrument, not celebrate the walker."),
            "open": True,
        },
        "ceiling_row": False,
        "runs": {
            "n": len(rows),
            "depths": depths,
            "n_exit": exits,
            "exit_rate": exits / len(rows),
            "turns_mean": statistics.mean(r["turns"] for r in rows),
            "turns_per_gate_mean": None,
            "consistency_mean": None,
            "elapsed_mean_s": 0.0,
        },
        "score": {
            "depth_median": statistics.median(depths),
            "ci_lower_median": bootstrap_ci_lower(depths, random.Random(entry_seed)),
            "bootstrap": {"B": BOOTSTRAP_B, "level": BOOTSTRAP_LEVEL, "seed": entry_seed},
        },
    }
    entry_path = args.out / "entries" / "control-null-random-walk.json"
    entry_path.write_text(json.dumps(entry, indent=1) + "\n")

    dist = {d: depths.count(d) for d in sorted(set(depths))}
    print(f"{args.runs} runs on {args.deg} (campaign seed {campaign_seed!r})")
    print(f"  depth distribution: {dist}")
    print(f"  median {entry['score']['depth_median']}, CI lower bound "
          f"{entry['score']['ci_lower_median']}, exits {exits}")
    print(f"  wrote {results_path} and {entry_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
