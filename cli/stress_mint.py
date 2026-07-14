"""Mint stress harness — consistency proof + variance census at season scale.

Proves the INSTRUMENT (engine/mint.py), not a model, before a real season is
sealed. Runs the full per-instance pipeline (mint → render → validate) for
every seed in the sweep and reports:

1. VALIDATION — bfs_verify + simulate_solve must pass on every instance.
2. DISTINCTNESS — empirical collision counts for the full (gate_id → answer)
   mapping and the gameplay-content hash across the sweep.
3. DETERMINISM — every Nth seed is re-minted and byte-compared in-process, and
   the run prints a single SWEEP DIGEST (sha256 over all rendered instances in
   seed order): run the harness twice — in separate containers — and compare
   digests to prove cross-process/cross-invocation byte determinism.
4. VARIANCE CENSUS (rev-2-specific semantics, marked below) — the per-instance
   spread the mint deliberately allows: which branch each conditional
   reasoning gate takes, and how many re-ask trap pairs are LIVE (the answer
   actually changes between the two asks). The original rev-2 has 5/7 pairs
   live (use_7/8 and use_11/12 are dead: max() saturates). This distribution
   is the datum for the --balance-branches decision before real seasons.

Usage (transient container, repo mounted at /app):
    python cli/stress_mint.py [--count 10000] [--seed-base 100000] [--recheck-every 100]
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine import mint  # noqa: E402

DEFAULT_BASE = Path(__file__).resolve().parent.parent / "degs" / "rev-2.yaml"

# --- rev-2-specific census semantics (a census tool, not the validator) -----
# Conditional gates: (condition on the CURRENT ledger, value-if-true, value-if-false)
_BRANCH_GATES = {
    "rsn_1": ("int(E) > int(C)", "F", "H"),
    "rsn_4": ("int(D) > int(B)", "A", "F"),
}
# max-of-sums gates: (left expr, right expr) — census records which side wins
_MAXSUM_GATES = {
    "rsn_2": ("int(C) + int(G)", "int(D) + int(H)"),
    "rsn_3": ("int(E) + int(G)", "int(D) + int(F)"),
}
_SAFE = {"__builtins__": {}, "int": int}


def _corridor(template: dict) -> list[dict]:
    """Ordered corridor gate dicts from the template base."""
    nodes = {n["id"]: n for n in template["base"]["nodes"]}
    out = []
    for nid in template["base"]["meta"]["optimal_path"]:
        node = nodes[nid]
        if not node.get("terminal"):
            out.append(node["paths"][0]["gate"])
    return out


def _trap_pairs(corridor: list[dict]) -> list[tuple[str, str]]:
    """(first, second) gate_id pairs with byte-identical problem text (the re-ask trap).
    Identified on the TEMPLATE (derived-gate text is instance-invariant)."""
    seen: dict[str, str] = {}
    pairs = []
    for g in corridor:
        if g.get("sets_var"):
            continue
        prob = g["problem"]
        if prob in seen:
            pairs.append((seen[prob], g["gate_id"]))
        else:
            seen[prob] = g["gate_id"]
    return pairs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", type=Path, default=DEFAULT_BASE)
    ap.add_argument("--count", type=int, default=10000)
    ap.add_argument("--seed-base", type=int, default=100000)
    ap.add_argument("--recheck-every", type=int, default=100,
                    help="re-mint every Nth seed and byte-compare (in-process determinism)")
    args = ap.parse_args()

    template = mint.load_template(args.base)
    corridor = _corridor(template)
    pairs = _trap_pairs(corridor)
    sets_var_by_gid = {g["gate_id"]: g["sets_var"] for g in corridor if g.get("sets_var")}
    print(f"template {template['parent_deg']}: {len(template['slots'])} slots, "
          f"range {template['value_range']}, {len(pairs)} trap pairs: "
          + ", ".join(f"{a}/{b}" for a, b in pairs))

    t0 = time.time()
    mappings: dict[tuple, int] = {}
    content_keys: dict[str, int] = {}
    sweep_digest = hashlib.sha256()
    recheck_fail = validation_fail = 0
    live_counts: Counter = Counter()
    branch_counts = {gid: Counter() for gid in list(_BRANCH_GATES) + list(_MAXSUM_GATES)}
    per_pair_live: Counter = Counter()

    for i in range(args.count):
        seed = args.seed_base + i
        inst = mint.mint_instance(template, seed, season="stress",
                                  instance_id=f"{template['parent_deg']}-stress-i{i:05d}")
        rendered = mint.render_yaml(inst)
        sweep_digest.update(rendered.encode("utf-8"))

        try:
            deg = mint.validate_instance(rendered)
            resolved = mint.simulate_solve(deg)
        except ValueError as e:
            validation_fail += 1
            print(f"  ! VALIDATION FAIL seed={seed}: {e}")
            continue

        mapping = tuple(sorted(resolved.items()))
        mappings.setdefault(mapping, seed)
        ck_parts = [f"{g['gate_id']}|{resolved[g['gate_id']]}" for g in corridor]
        content_keys.setdefault(mint.sha256_text("\n".join(ck_parts)), seed)

        if args.recheck_every and i % args.recheck_every == 0:
            again = mint.render_yaml(mint.mint_instance(
                template, seed, season="stress",
                instance_id=f"{template['parent_deg']}-stress-i{i:05d}"))
            if again != rendered:
                recheck_fail += 1
                print(f"  ! DETERMINISM FAIL seed={seed}")

        # census: walk the corridor maintaining the ledger; classify branch gates + live pairs
        ledger: dict[str, str] = {}
        for g in corridor:
            gid = g["gate_id"]
            if gid in _BRANCH_GATES:
                cond, tval, fval = _BRANCH_GATES[gid]
                taken = tval if eval(cond, _SAFE, dict(ledger)) else fval
                branch_counts[gid][taken] += 1
            elif gid in _MAXSUM_GATES:
                lexpr, rexpr = _MAXSUM_GATES[gid]
                lv, rv = eval(lexpr, _SAFE, dict(ledger)), eval(rexpr, _SAFE, dict(ledger))
                branch_counts[gid]["left" if lv > rv else "right" if rv > lv else "tie"] += 1
            if gid in sets_var_by_gid:
                ledger[sets_var_by_gid[gid]] = resolved[gid]
        live = 0
        for a, b in pairs:
            if resolved[a] != resolved[b]:
                live += 1
                per_pair_live[f"{a}/{b}"] += 1
        live_counts[live] += 1

    n = args.count
    print(f"\n=== SWEEP ({n} seeds {args.seed_base}..{args.seed_base + n - 1}, "
          f"{time.time() - t0:.1f}s) ===")
    print(f"validation failures:        {validation_fail}")
    print(f"determinism recheck fails:  {recheck_fail} "
          f"({(n + args.recheck_every - 1) // args.recheck_every} seeds rechecked)")
    print(f"answer-mapping collisions:  {n - len(mappings)}")
    print(f"content-hash collisions:    {n - len(content_keys)}")
    print(f"SWEEP DIGEST: {sweep_digest.hexdigest()}")
    print("\n=== VARIANCE CENSUS ===")
    print("live trap pairs per instance (original rev-2 = 5/7):")
    for k in sorted(live_counts):
        print(f"  {k}/7 live: {live_counts[k]:6d}  ({100 * live_counts[k] / n:.1f}%)")
    print("per-pair live rate:")
    for a, b in pairs:
        c = per_pair_live[f"{a}/{b}"]
        print(f"  {a}/{b}: {100 * c / n:5.1f}%")
    print("branch gates:")
    for gid, counter in branch_counts.items():
        dist = "  ".join(f"{k}={100 * v / n:.1f}%" for k, v in sorted(counter.items()))
        print(f"  {gid}: {dist}")

    ok = validation_fail == 0 and recheck_fail == 0 and len(mappings) == n
    print("\n" + ("STRESS PASS" if ok else "STRESS FAILURES — do not seal a season"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
