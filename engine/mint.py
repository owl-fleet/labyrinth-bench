"""Season mint — value-permuted isomorphs of a LOCK-corridor DEG template.

The leaderboard dealer deals each submitter a fresh instance of the sealed DEG:
same topology, same gate-role sequence, same derived-gate programs — different
literal values. `extract_template` lifts the structure from a base manifest
(`degs/rev-2.yaml` is the reference template); `mint_instance` is a pure
function of (template, seed); `simulate_solve` walks the corridor exactly as
`engine/runner.py` would and is the REAL correctness check — `bfs_verify` is a
near no-op on a pure LOCK corridor (every edge is "correct" regardless of value
consistency), so run both.

Scope: LOCK-corridor templates ONLY (rev-2's shape — single path, every gate
`wrong_destination: None`). Branchy DEGs (nav-1/2/3: junctions, dead ends,
wrong-destinations) raise harder isomorphism questions and are out of scope.

Isomorphism invariants:
- FIXED per season: node/edge topology + IDs; the ordered gate-role sequence;
  every derived gate's depends_on, answer_fn, and problem text (they contain no
  literals — never rewritten); the revision schedule incl. recall-vs-fresh
  flags; meta gameplay fields (optimal_commits, gate_count, budgets,
  optimal_path, briefing verbatim).
- FREE per instance: the establish literals + each fresh-revision literal
  (independent draws from the template's inferred range; a fresh revision
  re-draws while equal to the variable's current value, so every revision
  ACTUALLY changes the value — the property the re-ask traps depend on);
  recall revisions copy-forward the earlier minted value; provenance metadata
  (meta.id/season/instance_seed/parent_deg/manifest_sha256).

Accepted per-instance variance (recorded, not constrained in v1): reasoning-gate
branch outcomes (rsn_*) and max-style trap pairs can resolve differently across
instances — even the ORIGINAL rev-2 has use_7/use_8 both resolve to 9 (G=9
dominates F's 6→7). Holding those constant is the deferred `--balance-branches`
stretch flag (Dealer-service item), not v1.
"""
from __future__ import annotations

import copy
import hashlib
import random
from pathlib import Path

import yaml

from engine.graph import DEG, bfs_verify, load_deg_dict

# Per-role problem/answer text for sets_var gates. Derived gates are never rewritten.
_ESTABLISH_PROBLEM = "Variable {var} is initialized to {val}. What is the value of {var}?"
_REVISE_PROBLEM = "{var} changes: {var} is now {val}. Answer {val} to set it."

_GENERATED_HEADER = (
    "# GENERATED (deterministic, seed={seed}) — minted isomorph of {parent}; do not hand-edit.\n"
)


def classify_gate(gate_id: str) -> str:
    """Gate role from the id prefix (the rev-2 convention; proven in the M-figure pipeline)."""
    if gate_id.startswith("set_"):
        return "establish"
    if gate_id.startswith("rev_"):
        return "revise"
    if gate_id.startswith("rsn_"):
        return "reasoning"
    if gate_id.startswith("syn_"):
        return "synthesis"
    return "use"


def _corridor_gates(deg_dict: dict) -> list[dict]:
    """Ordered (node_id, path_dict, gate_dict) walk of meta.optimal_path.

    LOCK-corridor guard: exactly one path per non-terminal node, no wrong_destination.
    """
    nodes = {n["id"]: n for n in deg_dict["nodes"]}
    out = []
    for nid in deg_dict["meta"]["optimal_path"]:
        node = nodes[nid]
        if node.get("terminal"):
            continue
        paths = node.get("paths", [])
        if len(paths) != 1:
            raise ValueError(f"not a LOCK corridor: node {nid!r} has {len(paths)} paths")
        gate = paths[0].get("gate")
        if gate is None:
            raise ValueError(f"not a LOCK corridor: node {nid!r} path is ungated")
        if gate.get("wrong_destination") is not None:
            raise ValueError(f"not a LOCK corridor: gate {gate.get('gate_id')!r} has wrong_destination")
        if not gate.get("gate_id"):
            # the runner only records gate_results for truthy gate_ids — an id-less corridor
            # gate would diverge between simulate_solve and a real run, so refuse it outright
            raise ValueError(f"corridor gate at node {nid!r} has no gate_id")
        out.append({"node": nid, "gate": gate})
    return out


def extract_template(deg_dict: dict, source_bytes: bytes | None = None) -> dict:
    """Lift the mintable structure from a raw manifest dict.

    Walks the corridor with a value ledger to split revisions into FRESH (new
    literal, free per instance) vs RECALL (returns a variable to a value it held
    earlier — a designed difficulty feature, preserved by copy-forward from the
    matching earlier gate, never re-drawn). rev-2 has exactly one recall:
    rev_c_2 → set_c. Detection is by simulation (value equals an earlier ledger
    value of the same var), not by hardcoded gate ids.
    """
    slots = []          # one entry per sets_var gate, in corridor order
    literals = []       # every establish/fresh-revision literal (range inference)
    history: dict[str, list[tuple[str, str]]] = {}  # var -> [(gate_id, value), ...]

    for item in _corridor_gates(deg_dict):
        g = item["gate"]
        role = classify_gate(g.get("gate_id", ""))
        if not g.get("sets_var"):
            continue
        if role not in ("establish", "revise"):
            raise ValueError(f"sets_var gate {g.get('gate_id')!r} has unexpected role {role!r}")
        var, val = g["sets_var"], str(g["answer"])
        # The mint rewrites this gate's text from the per-role templates, so the template
        # must OWN the phrasing: verify the original text is exactly what we would render
        # for it, else a differently-worded template would be silently rewritten.
        tpl = _ESTABLISH_PROBLEM if role == "establish" else _REVISE_PROBLEM
        expected_text = tpl.format(var=var, val=val)
        if g["problem"] != expected_text:
            raise ValueError(
                f"gate {g['gate_id']!r}: problem text does not match the {role} template — "
                f"minting would rewrite its wording; got {g['problem']!r}")
        recall_of = None
        if role == "revise":
            prior = history.get(var, [])
            if not prior:
                raise ValueError(f"revision {g['gate_id']!r} before {var!r} was established")
            earlier = [gid for gid, v in prior if v == val]
            if earlier:
                recall_of = earlier[0]  # designed recall: copy-forward from this gate
        slots.append({
            "gate_id": g["gate_id"], "role": role, "var": var,
            "original": val, "recall_of": recall_of,
        })
        if recall_of is None:
            literals.append(int(val))
        history.setdefault(var, []).append((g["gate_id"], val))

    if not literals:
        raise ValueError("template has no free literals (no establish/fresh-revision slots) — nothing to mint")

    parent = deg_dict["meta"]["id"]
    return {
        "base": copy.deepcopy(deg_dict),
        "parent_deg": parent,
        "slots": slots,
        "value_range": (min(literals), max(literals)),
        "manifest_sha256": sha256_bytes(source_bytes) if source_bytes else None,
    }


def load_template(path: Path) -> dict:
    source = Path(path).read_bytes()
    return extract_template(yaml.safe_load(source), source_bytes=source)


def mint_instance(template: dict, seed: int, *, season: str, instance_id: str,
                  value_range: tuple[int, int] | None = None,
                  values: dict[str, int] | None = None) -> dict:
    """Pure function (template, seed) → instance manifest dict.

    `values` overrides the draw per gate_id (the round-trip selftest re-renders
    with the template's ORIGINAL values); normal minting leaves it None.
    """
    rng = random.Random(seed)
    lo, hi = value_range or template["value_range"]
    if not (isinstance(lo, int) and isinstance(hi, int)) or lo > hi:
        raise ValueError(f"invalid value range {lo!r}..{hi!r} (need integers with lo <= hi)")
    if hi == lo and any(s["role"] == "revise" and s["recall_of"] is None for s in template["slots"]):
        raise ValueError(
            f"value range {lo}..{hi} spans a single value — cannot enforce revision != current value")
    if values is not None:
        missing = [s["gate_id"] for s in template["slots"] if s["gate_id"] not in values]
        if missing:
            raise ValueError(f"values override is missing gate(s): {missing}")
    inst = copy.deepcopy(template["base"])

    ledger: dict[str, int] = {}          # var -> current minted value
    minted: dict[str, int] = {}          # gate_id -> minted value
    for slot in template["slots"]:
        gid, var = slot["gate_id"], slot["var"]
        if values is not None:
            val = int(values[gid])
        elif slot["recall_of"] is not None:
            val = minted[slot["recall_of"]]
        elif slot["role"] == "establish":
            val = rng.randint(lo, hi)
        else:  # fresh revision: must ACTUALLY change the value
            val = rng.randint(lo, hi)
            while val == ledger[var]:
                val = rng.randint(lo, hi)
        minted[gid] = val
        ledger[var] = val

    # Rewrite the sets_var gates in place; derived gates stay byte-identical.
    problem_tpl = {"establish": _ESTABLISH_PROBLEM, "revise": _REVISE_PROBLEM}
    by_gid = {s["gate_id"]: s for s in template["slots"]}
    for item in _corridor_gates(inst):
        g = item["gate"]
        slot = by_gid.get(g.get("gate_id"))
        if slot is None:
            continue
        val = minted[slot["gate_id"]]
        g["problem"] = problem_tpl[slot["role"]].format(var=slot["var"], val=val)
        g["answer"] = str(val)

    meta = inst["meta"]
    meta["id"] = instance_id
    meta["season"] = season
    meta["instance_seed"] = seed
    meta["parent_deg"] = template["parent_deg"]
    if template.get("manifest_sha256"):
        meta["parent_manifest_sha256"] = template["manifest_sha256"]
    return inst


def simulate_solve(deg: DEG) -> dict[str, str]:
    """Walk the corridor via Gate.resolved_answer exactly as the runner does.

    Maintains gate_results + the sets_var ledger; raises on __UNRESOLVABLE__ or
    a non-terminal end. Returns gate_id → resolved answer.
    """
    gate_results: dict[str, str] = {}
    var_ledger: dict[str, str] = {}
    resolved: dict[str, str] = {}
    node = deg.start
    for expected in deg.optimal_path[1:]:
        path = node.paths[0]
        gate = path.gate
        ans = gate.resolved_answer(gate_results, var_ledger)
        if ans == "__UNRESOLVABLE__":
            raise ValueError(f"{deg.id}: gate {gate.gate_id!r} unresolvable at node {node.id!r}")
        resolved[gate.gate_id] = ans
        gate_results[gate.gate_id] = ans
        if gate.sets_var:
            var_ledger[gate.sets_var] = ans
        if path.destination != expected:
            raise ValueError(f"{deg.id}: corridor diverges from optimal_path at {node.id!r}")
        node = deg.node(path.destination)
    if not node.terminal:
        raise ValueError(f"{deg.id}: optimal_path ends at non-terminal {node.id!r}")
    return resolved


def validate_instance(rendered: str) -> DEG:
    """Generation-time validation of a rendered instance — the gate every minted
    instance must pass BEFORE it is written or ledgered, wherever the caller lives
    (CLI season mint or a future Dealer service). Parses the rendered text (so the
    exact bytes headed for disk are what get validated), builds the engine DEG,
    checks the bfs_verify commit count against optimal_commits, and walks the full
    corridor via simulate_solve. Raises ValueError on any failure."""
    deg = load_deg_dict(yaml.safe_load(rendered))
    _, commits = bfs_verify(deg)
    if commits != deg.optimal_commits:
        raise ValueError(f"{deg.id}: bfs commit count {commits} != optimal_commits {deg.optimal_commits}")
    simulate_solve(deg)
    return deg


def render_yaml(instance: dict) -> str:
    """Deterministic serialization: same instance dict → identical bytes."""
    header = _GENERATED_HEADER.format(
        seed=instance["meta"]["instance_seed"], parent=instance["meta"]["parent_deg"])
    body = yaml.dump(instance, sort_keys=False, default_flow_style=False,
                     allow_unicode=False, width=100)
    return header + body


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))
