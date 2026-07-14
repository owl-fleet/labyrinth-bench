"""mint_instances — one-command season mint for the LB leaderboard dealer.

Deals value-permuted isomorphs of a LOCK-corridor DEG (see engine/mint.py for
the isomorphism invariants and scope). Every instance is validated at
generation: bfs_verify + a full simulate_solve corridor walk.

Output: instance YAMLs in --out-dir (default sealed/ — gitignored, and the
out-dir writes itself a `*` .gitignore so custom paths never leak answer keys;
the practice set is public, sealed instances never are) + an append-only
sealed/ledger.jsonl with one row per instance (sha256 is of the instance file
bytes; created_at lives in the ledger ONLY, never in the YAML, so same-seed
mints stay byte-identical). Sealed-season guards refuse: overwriting an
existing instance file, re-using a ledgered instance_id, re-using a (base,
seed) across seasons, and duplicate full answer mappings within a run.

Usage (transient container, repo mounted at /app):
    python cli/mint_instances.py --base degs/rev-2.yaml --season s1 --seed 41 --count 20
    python cli/mint_instances.py --selftest
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine import mint  # noqa: E402
from engine.graph import bfs_verify, load_deg_dict  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DEFAULT_BASE = REPO / "degs" / "rev-2.yaml"

# meta keys added by the mint — excluded from the round-trip structural compare
_PROVENANCE_KEYS = ("season", "instance_seed", "parent_deg", "parent_manifest_sha256")


def _read_ledger(ledger_path: Path) -> list[dict]:
    if not ledger_path.exists():
        return []
    with open(ledger_path) as f:
        return [json.loads(line) for line in f if line.strip()]


def mint_season(base: Path, season: str, seed: int, count: int,
                value_range: tuple[int, int] | None, out_dir: Path) -> list[dict]:
    template = mint.load_template(base)
    recalls = [f"{s['gate_id']}<-{s['recall_of']}" for s in template["slots"] if s["recall_of"]]
    print(f"template {template['parent_deg']}: {len(template['slots'])} value slots, "
          f"range {template['value_range']}, recall schedule: {', '.join(recalls) or 'none'}")

    out_dir.mkdir(parents=True, exist_ok=True)
    gitignore = out_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n")  # sealed output ignores itself wherever --out-dir points

    # Sealed-season guards: never overwrite a minted instance, never duplicate a
    # ledger instance_id, never reuse a (base, seed) across seasons (same seed →
    # identical values → cross-season answer leak).
    ledger_path = out_dir / "ledger.jsonl"
    prior = _read_ledger(ledger_path)
    prior_ids = {r["instance_id"] for r in prior}
    prior_seeds = {(r["base_deg_id"], r["seed"]) for r in prior}

    rows: list[dict] = []
    mappings: set = set()
    for i in range(count):
        inst_seed = seed + i
        instance_id = f"{template['parent_deg']}-{season}-i{i + 1:02d}"
        out_path = out_dir / f"{instance_id}.yaml"
        if instance_id in prior_ids:
            raise SystemExit(f"REFUSED: {instance_id} already in {ledger_path} — seasons are "
                             "sealed; pick a new --season id (or clear the out-dir to re-mint)")
        if (template["parent_deg"], inst_seed) in prior_seeds:
            raise SystemExit(f"REFUSED: seed {inst_seed} already used for "
                             f"{template['parent_deg']} in {ledger_path} — seed reuse mints "
                             "identical values across seasons")
        if out_path.exists():
            raise SystemExit(f"REFUSED: {out_path} exists — will not overwrite a sealed instance")

        inst = mint.mint_instance(template, inst_seed, season=season,
                                  instance_id=instance_id, value_range=value_range)
        rendered = mint.render_yaml(inst)
        deg = mint.validate_instance(rendered)  # raises before anything is written
        mapping = tuple(sorted(mint.simulate_solve(deg).items()))
        if mapping in mappings:
            raise SystemExit(f"REFUSED: {instance_id} duplicates another instance's full answer "
                             "mapping in this run — widen --value-range or change --seed")
        mappings.add(mapping)

        out_path.write_text(rendered)
        row = {
            "instance_id": instance_id, "season": season,
            "base_deg_id": template["parent_deg"], "seed": inst_seed,
            "sha256": mint.sha256_text(rendered), "gate_count": deg.gate_count,
            "optimal_commits": deg.optimal_commits,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        with open(ledger_path, "a") as f:
            f.write(json.dumps(row) + "\n")
        rows.append(row)
    return rows


# ---------------------------------------------------------------- selftest

def selftest(base: Path) -> bool:
    """7 deterministic checks — proves the mint, not a model (sandbox/selftest.py style)."""
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail and not ok else ""))

    source = base.read_bytes()
    original = yaml.safe_load(source)
    template = mint.extract_template(original, source_bytes=source)
    print(f"template: {template['parent_deg']}  slots={len(template['slots'])}  "
          f"range={template['value_range']}  "
          f"recalls={[s['gate_id'] for s in template['slots'] if s['recall_of']]}")

    # 1. Round-trip: original values back in → field-for-field identical to the base.
    orig_values = {s["gate_id"]: int(s["original"]) for s in template["slots"]}
    rt = mint.mint_instance(template, 0, season="roundtrip",
                            instance_id=original["meta"]["id"], values=orig_values)
    rt_cmp = copy.deepcopy(rt)
    for k in _PROVENANCE_KEYS:
        rt_cmp["meta"].pop(k, None)
    check("1 round-trip field-for-field", rt_cmp == original,
          "re-rendered template with original values differs from the base manifest")

    # Mint the reference set for checks 2-7.
    seeds = list(range(1, 21))
    instances, rendered, degs = {}, {}, {}
    for s in seeds:
        inst = mint.mint_instance(template, s, season="selftest",
                                  instance_id=f"{template['parent_deg']}-selftest-i{s:02d}")
        instances[s] = inst
        rendered[s] = mint.render_yaml(inst)
        degs[s] = load_deg_dict(yaml.safe_load(rendered[s]))

    # 2. Topology invariance + bfs_verify on every instance.
    def topo(deg_dict: dict):
        return [(n["id"], n.get("terminal", False),
                 tuple((p["id"], p["destination"], p["gate"]["gate_id"])
                       for p in n.get("paths", [])))
                for n in deg_dict["nodes"]]
    base_topo = topo(original)
    topo_ok, bfs_ok = True, True
    for s in seeds:
        if topo(instances[s]) != base_topo:
            topo_ok = False
        path_nodes, commits = bfs_verify(degs[s])
        if commits != degs[s].optimal_commits:
            bfs_ok = False
    check("2 topology invariance + bfs_verify (seeds 1..20)", topo_ok and bfs_ok,
          f"topo_ok={topo_ok} bfs_ok={bfs_ok}")

    # 3. simulate_solve clean on every instance.
    sim_answers, sim_ok, sim_err = {}, True, ""
    for s in seeds:
        try:
            sim_answers[s] = mint.simulate_solve(degs[s])
        except ValueError as e:
            sim_ok, sim_err = False, str(e)
    check("3 simulate_solve clean (seeds 1..20)", sim_ok, sim_err)

    # 4. Recall feature + the enforce-≠ constraint in every instance.
    recall_slots = [s for s in template["slots"] if s["recall_of"]]
    recall_ok = bool(recall_slots)
    for s in seeds:
        ledger: dict[str, str] = {}
        for slot in template["slots"]:
            gid, var = slot["gate_id"], slot["var"]
            ans = sim_answers[s][gid]
            if slot["recall_of"]:
                # genuine return: equals the recalled gate's value AND differs from current
                if ans != sim_answers[s][slot["recall_of"]] or ans == ledger[var]:
                    recall_ok = False
            elif slot["role"] == "revise" and ans == ledger[var]:
                recall_ok = False  # a fresh revision that changed nothing
            ledger[var] = ans
    check("4 recall preserved + every revision actually changes its value", recall_ok)

    # 5. Determinism: same seed → identical bytes → identical sha256.
    det_ok = all(
        mint.render_yaml(mint.mint_instance(
            template, s, season="selftest",
            instance_id=f"{template['parent_deg']}-selftest-i{s:02d}")) == rendered[s]
        for s in seeds)
    check("5 determinism (same seed → identical YAML bytes)", det_ok)

    # 6. Distinctness: no two seeds share the full gate_id → answer mapping.
    mappings = [tuple(sorted(sim_answers[s].items())) for s in seeds]
    check("6 answer-mapping distinctness across seeds", len(set(mappings)) == len(seeds))

    # 7. Gameplay-content hash distinctness. Whole-file hashes are trivially distinct
    #    (header + meta embed the seed), so hash ONLY what the player sees: the corridor's
    #    (gate_id, problem, answer) sequence, meta/provenance excluded.
    def content_key(inst: dict) -> str:
        parts = []
        for n in inst["nodes"]:
            for p in n.get("paths", []):
                g = p.get("gate")
                if g:
                    parts.append(f"{g.get('gate_id')}|{g.get('problem')}|{g.get('answer')}")
        return mint.sha256_text("\n".join(parts))
    check("7 gameplay-content hash distinctness across seeds",
          len({content_key(instances[s]) for s in seeds}) == len(seeds))

    ok = all(r[1] for r in results)
    print(f"\n{sum(r[1] for r in results)}/{len(results)} checks  "
          + ("ALL PASS — mint validated" if ok else "FAILURES — fix before sealing a season"))
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", type=Path, default=DEFAULT_BASE,
                    help="template DEG manifest (default degs/rev-2.yaml)")
    ap.add_argument("--season", help="season id (required unless --selftest)")
    ap.add_argument("--seed", type=int, default=2027,
                    help="base seed; instance i uses seed+i (default 2027, program convention)")
    ap.add_argument("--count", type=int, default=1, help="instances to mint")
    ap.add_argument("--value-range", metavar="LO,HI",
                    help="literal draw range override (default: inferred from the template)")
    ap.add_argument("--out-dir", type=Path, default=REPO / "sealed",
                    help="output dir (default sealed/ — gitignored)")
    ap.add_argument("--selftest", action="store_true", help="run the 7-check selftest and exit")
    args = ap.parse_args()

    if args.selftest:
        return 0 if selftest(args.base) else 1

    if not args.season:
        ap.error("--season is required unless --selftest")
    vrange = None
    if args.value_range:
        try:
            parts = [int(x) for x in args.value_range.split(",")]
        except ValueError:
            ap.error(f"--value-range must be two integers LO,HI (got {args.value_range!r})")
        if len(parts) != 2:
            ap.error(f"--value-range must be exactly LO,HI (got {args.value_range!r})")
        if parts[0] > parts[1]:
            ap.error(f"--value-range LO must be <= HI (got {parts[0]},{parts[1]})")
        vrange = (parts[0], parts[1])

    try:
        rows = mint_season(args.base, args.season, args.seed, args.count, vrange, args.out_dir)
    except ValueError as e:
        raise SystemExit(f"REFUSED: {e}")
    for r in rows:
        print(f"minted {r['instance_id']}  seed={r['seed']}  sha256={r['sha256'][:12]}…")
    print(f"{len(rows)} instance(s) → {args.out_dir}  (ledger: {args.out_dir / 'ledger.jsonl'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
