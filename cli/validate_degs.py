#!/usr/bin/env python3
"""Validate every DEG manifest in degs/ — the CI gate for map changes.

Checks, per manifest:
  1. It parses and loads into an engine DEG.
  2. bfs_verify finds a start→terminal path and its commit count matches the declared
     optimal_commits (the same parity check every minted instance passes at mint time).
  3. Corridor DEGs (every non-terminal node on optimal_path has exactly one onward path)
     additionally full-walk via simulate_solve — dependent gates resolve, sets_var ledger
     flows, the corridor ends terminal. Branching mazes skip this (it is corridor-only
     by construction).

Usage: python3 cli/validate_degs.py [--degs degs]
Exit codes: 0 = all valid; 1 = at least one failure.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.graph import bfs_verify, load_deg  # noqa: E402
from engine.mint import simulate_solve  # noqa: E402


def is_corridor(deg) -> bool:
    """Single onward path at every non-terminal optimal_path node — simulate_solve's contract."""
    for node_id in deg.optimal_path[:-1]:
        node = deg.nodes.get(node_id)
        if node is None or node.terminal or len(node.paths) != 1:
            return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--degs", type=Path, default=Path(__file__).resolve().parent.parent / "degs")
    args = ap.parse_args()

    failures = 0
    manifests = sorted(args.degs.glob("*.yaml"))
    if not manifests:
        print(f"ERROR: no DEG manifests in {args.degs}", file=sys.stderr)
        return 1
    for f in manifests:
        try:
            deg = load_deg(f)
            _, commits = bfs_verify(deg)
            if commits != deg.optimal_commits:
                raise ValueError(f"bfs commit count {commits} != declared optimal_commits {deg.optimal_commits}")
            if is_corridor(deg):
                simulate_solve(deg)
                print(f"  PASS {f.name} [{deg.id}] — load + bfs parity ({commits}) + corridor walk")
            else:
                print(f"  PASS {f.name} [{deg.id}] — load + bfs parity ({commits}); branching (no corridor walk)")
        except Exception as e:
            failures += 1
            print(f"  FAIL {f.name} — {e}")

    total = len(manifests)
    print(f"\n{total - failures}/{total} valid" + (f", {failures} FAILED" if failures else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
