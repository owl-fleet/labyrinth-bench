"""Honest analysis for the LB Design 2 accumulation eval.

The head-to-head mandate (Will, non-negotiable): every claim is A1-minus-A0 (or A2-minus-A1),
reported as a DISTRIBUTION with a bootstrap CI — never a single number, never a lucky max. This
module loads per-arm JSONL result files, prints the learning curve (per-run-index means), the
overall distributions, an integrity audit (silent write drops, A0 reads), and a bootstrap CI on
the arm delta for a chosen metric. Pure stdlib so it runs in the sandbox/toolbox container.

Usage (in-container):
  python3 /app/design2/analyze.py --metric normalized_efficiency \
      A0=/results/g2_a0.jsonl A1=/results/g2_a1.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from typing import Optional


def _load(path: str) -> list[dict]:
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _vals(rows: list[dict], metric: str) -> list[float]:
    """Numeric values for a metric, skipping None (e.g. efficiency is None on a DNF)."""
    out = []
    for r in rows:
        v = r.get(metric)
        if v is not None:
            out.append(float(v))
    return out


def _bootstrap_ci(a: list[float], b: list[float], iters: int = 10000,
                  seed: int = 1729) -> tuple[float, float, float]:
    """Bootstrap CI for mean(b) - mean(a). Returns (delta, lo95, hi95). Robust at small N where
    normality fails for skewed step counts / 0-1 exit. Resample each arm with replacement."""
    if not a or not b:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    delta = statistics.mean(b) - statistics.mean(a)
    deltas = []
    for _ in range(iters):
        ra = [a[rng.randrange(len(a))] for _ in a]
        rb = [b[rng.randrange(len(b))] for _ in b]
        deltas.append(statistics.mean(rb) - statistics.mean(ra))
    deltas.sort()
    lo = deltas[int(0.025 * iters)]
    hi = deltas[int(0.975 * iters)]
    return delta, lo, hi


def _integrity(arm: str, rows: list[dict]) -> list[str]:
    """Audit the flattery/robustness guards from the plan."""
    flags = []
    drops = [r.get("run_index", i) for i, r in enumerate(rows) if r.get("arm") and not r.get("memory_written")]
    if drops:
        flags.append(f"{arm}: {len(drops)} SILENT WRITE DROP(S) at runs {drops} — learning curve corrupted")
    if arm == "A0":
        reads = [i for i, r in enumerate(rows) if (r.get("memory_retrievals") or 0) > 0]
        if reads:
            flags.append(f"A0: read memory on runs {reads} — control contaminated (must be 0)")
    return flags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metric", default="normalized_efficiency",
                    help="primary learning-curve metric (normalized_efficiency | ramp_depth | steps_to_exit)")
    ap.add_argument("--baseline", default="A0", help="the honest baseline arm key")
    ap.add_argument("arms", nargs="+", help="ARM=path.jsonl  (e.g. A0=/results/g2_a0.jsonl A1=...)")
    args = ap.parse_args()

    data = {}
    for spec in args.arms:
        arm, path = spec.split("=", 1)
        data[arm] = _load(path)

    print(f"=== metric: {args.metric} ===\n")

    # integrity audit first — a corrupted run invalidates the contrast
    all_flags = []
    for arm, rows in data.items():
        all_flags += _integrity(arm, rows)
    if all_flags:
        print("INTEGRITY FLAGS:")
        for f in all_flags:
            print(f"  !! {f}")
        print()
    else:
        print("integrity: clean (no silent write drops; A0 never read)\n")

    # per-arm distribution + learning curve
    for arm, rows in data.items():
        vals = _vals(rows, args.metric)
        exits = sum(1 for r in rows if r.get("found_exit"))
        curve = [r.get(args.metric) for r in rows]            # by run-index (the learning curve)
        steps = [r.get("steps_to_exit") for r in rows]
        mean = statistics.mean(vals) if vals else float("nan")
        med = statistics.median(vals) if vals else float("nan")
        sd = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        print(f"{arm}: n={len(rows)} exits={exits}/{len(rows)} "
              f"{args.metric} mean={mean:.3f} median={med:.3f} sd={sd:.3f}")
        print(f"    curve (by run): {curve}")
        print(f"    steps_to_exit:  {steps}")

    # bootstrap delta vs baseline
    base = data.get(args.baseline)
    if base is not None:
        ba = _vals(base, args.metric)
        print(f"\n=== bootstrap delta vs {args.baseline} (10k resamples, 95% CI) ===")
        for arm, rows in data.items():
            if arm == args.baseline:
                continue
            d, lo, hi = _bootstrap_ci(ba, _vals(rows, args.metric))
            sep = "SEPARATED from 0" if (lo > 0 or hi < 0) else "overlaps 0 (underpowered / null)"
            print(f"  {arm} - {args.baseline}: {d:+.3f}  95%CI [{lo:+.3f}, {hi:+.3f}]  -> {sep}")

        # exit-rate contrast — the right readout when the metric is degenerate (e.g. all-DNF poison,
        # where normalized_efficiency is undefined). Bootstrap CI on the exit-rate difference.
        print(f"\n=== exit-rate delta vs {args.baseline} (the oracle; robust to all-DNF) ===")
        bex = [1.0 if r.get("found_exit") else 0.0 for r in base]
        for arm, rows in data.items():
            if arm == args.baseline:
                continue
            aex = [1.0 if r.get("found_exit") else 0.0 for r in rows]
            d, lo, hi = _bootstrap_ci(bex, aex)
            sep = "SEPARATED from 0" if (lo > 0 or hi < 0) else "overlaps 0"
            print(f"  {arm}: {sum(aex):.0f}/{len(aex)} exits vs {args.baseline} {sum(bex):.0f}/{len(bex)}  "
                  f"delta={d:+.3f} 95%CI [{lo:+.3f}, {hi:+.3f}] -> {sep}")


if __name__ == "__main__":
    main()
