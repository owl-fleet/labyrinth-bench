"""lb verify — replay-check a results JSONL (or an entry file) against the sealed manifests.

"Re-derivable by anyone from the trace" as one command. Two levels, applied per run row:

  Level 1 (always): walk the recorded `events` against the DEG manifest — every transition
    must be a legal edge (correct destination on a correct/ungated commit, a wrong_destination
    on a wrong routing commit, stay-put on a locked gate, stack-pop on back), step accounting
    must re-derive, and the row's score fields (ramp_depth, found_exit, failure_reason,
    gate_accuracy, lives_used) must match what the walk re-computes.
  Level 2 (when the row carries `turns_log`): re-drive a fresh engine Session from the
    dispatched actions (`action_parsed`) and require the regenerated event stream to equal
    the submitted one byte-for-byte — the full deterministic replay, gate answers included.

Entry mode (--entry): recheck an entries/*.json score block — n, median, and the seeded
bootstrap lower bound re-computed from the entry's own run distribution.

What this does NOT prove (METHODOLOGY §4): that the claimed model produced the trace, or
that unfavorable runs were also submitted. Replay proves internal consistency; provenance
and selection are the dealer ledger's and the reproduction rungs' jobs.

Usage:
  python3 cli/verify.py results.jsonl [more.jsonl ...] [--degs degs] [-v]
  python3 cli/verify.py --entry entries/seed-model-qwen3-14b.json

Exit codes: 0 = everything verified; 1 = at least one row/entry failed; 2 = usage/IO error.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.graph import DEG, load_all_degs  # noqa: E402
from engine.runner import new_session  # noqa: E402

# Non-consuming actions; commit/pull consume one step (locked commits included).
_FREE_ACTIONS = {"observe", "inspect", "note"}
# Terminal outcomes a run may end on, mapped to the row's failure_reason vocabulary.
_END_OUTCOMES = {
    "exit": "exit",
    "out_of_lives": "out_of_lives",
    "budget_exhausted": "budget_exhausted",
    "dead_end_trapped": "dead_end_trapped",
    "loop_trapped": "loop_trapped",
    "impossible": "impossible",
}


class RowFailure(Exception):
    """A verification check failed for this row."""


def _fail(cond: bool, msg: str) -> None:
    if not cond:
        raise RowFailure(msg)


# ---------------------------------------------------------------------------
# Level 1 — events walk
# ---------------------------------------------------------------------------

def walk_events(row: dict, deg: DEG) -> dict:
    """Re-walk the recorded events against the manifest; return re-derived score fields."""
    events = row.get("events") or []
    _fail(bool(events), "row has no events array")

    pos = deg.start_node_id
    stack: list[str] = []
    steps = 0
    lives = 0
    total_gates = 0
    correct_gates = 0
    passed_gate_ids: set = set()
    ambiguous_correct = 0  # correct gated commits whose gate couldn't be uniquely attributed
    found_exit = False
    end_reason: str | None = None

    for i, ev in enumerate(events):
        action = ev.get("action")
        dst = ev.get("node_id")
        outcome = ev.get("outcome")
        gate_correct = ev.get("gate_correct")
        _fail(end_reason is None or i == len(events) - 1,
              f"event {i}: events continue after terminal outcome {end_reason!r}")

        if action in _FREE_ACTIONS:
            _fail(dst == pos, f"event {i}: {action} reports node {dst!r} but position is {pos!r}")
            if outcome == "dead_end_trapped":
                end_reason = "dead_end_trapped"
            else:
                _fail(outcome is None, f"event {i}: unexpected {action} outcome {outcome!r}")
        elif action == "pull":
            _fail(dst == pos, f"event {i}: pull reports node {dst!r} but position is {pos!r}")
            steps += 1
            if outcome == "budget_exhausted":
                end_reason = "budget_exhausted"
                _fail(steps >= deg.step_budget, f"event {i}: budget_exhausted at {steps}/{deg.step_budget}")
        elif action == "commit":
            if outcome == "back":
                _fail(bool(stack), f"event {i}: back with empty traversal stack")
                expected = stack.pop()
                _fail(dst == expected, f"event {i}: back landed on {dst!r}, stack says {expected!r}")
                pos = dst
                steps += 1
            elif outcome in ("locked", "out_of_lives") or (
                outcome == "budget_exhausted" and dst == pos and gate_correct is False
            ):
                # Lock gate: wrong answer, stay put, spend a step (and a life in ramp mode).
                _fail(gate_correct is False, f"event {i}: {outcome} without gate_correct=false")
                _fail(dst == pos, f"event {i}: {outcome} moved {pos!r}→{dst!r} (locks stay put)")
                node = deg.node(pos)
                _fail(any(p.is_gated and p.gate.wrong_destination is None for p in node.paths),
                      f"event {i}: {outcome} at {pos!r} but node has no lock gate")
                total_gates += 1
                if deg.max_wrong:  # lives are a ramp-mode budget; engine counts them only then
                    lives += 1
                steps += 1
                if outcome == "out_of_lives":
                    _fail(deg.max_wrong > 0 and lives >= deg.max_wrong,
                          f"event {i}: out_of_lives at {lives} wrong (max_wrong={deg.max_wrong})")
                    end_reason = "out_of_lives"
                elif outcome == "budget_exhausted":
                    _fail(steps >= deg.step_budget, f"event {i}: budget_exhausted at {steps}/{deg.step_budget}")
                    end_reason = "budget_exhausted"
            else:
                # A move: correct/ungated commit follows a declared destination; a wrong
                # routing commit follows some gated path's wrong_destination.
                node = deg.node(pos)
                if gate_correct is False:
                    candidates = [p for p in node.paths
                                  if p.is_gated and p.gate.wrong_destination == dst]
                    _fail(bool(candidates),
                          f"event {i}: wrong-gate move {pos!r}→{dst!r} matches no wrong_destination")
                    total_gates += 1
                    if deg.max_wrong:
                        lives += 1
                else:
                    candidates = [p for p in node.paths if p.destination == dst]
                    _fail(bool(candidates),
                          f"event {i}: move {pos!r}→{dst!r} matches no declared path")
                    if gate_correct is True:
                        gated = [p for p in candidates if p.is_gated]
                        _fail(bool(gated),
                              f"event {i}: gate_correct=true on {pos!r}→{dst!r} but no gated path there")
                        total_gates += 1
                        correct_gates += 1
                        with_id = [p.gate.gate_id for p in gated if p.gate.gate_id]
                        if len(gated) == 1 and with_id:
                            passed_gate_ids.add(with_id[0])
                        elif with_id:
                            ambiguous_correct += 1
                stack.append(pos)
                pos = dst
                steps += 1
                if outcome == "exit":
                    _fail(deg.node(dst).terminal, f"event {i}: exit outcome on non-terminal {dst!r}")
                    found_exit = True
                    end_reason = "exit"
                elif outcome in ("loop_trapped", "impossible", "budget_exhausted"):
                    end_reason = outcome
                    if outcome == "budget_exhausted":
                        _fail(steps >= deg.step_budget,
                              f"event {i}: budget_exhausted at {steps}/{deg.step_budget}")
                elif outcome not in ("ok", "wrong", "dead_end"):
                    raise RowFailure(f"event {i}: unknown commit outcome {outcome!r}")
        else:
            raise RowFailure(f"event {i}: unknown action {action!r}")

        _fail(ev.get("steps_used") == steps,
              f"event {i}: steps_used={ev.get('steps_used')} but walk re-derives {steps}")
        _fail(steps <= deg.step_budget,
              f"event {i}: steps {steps} exceed budget {deg.step_budget}")

    # Distinct gates passed; ambiguous attributions bound the count from above.
    ramp_lo = len(passed_gate_ids)
    ramp_hi = ramp_lo + ambiguous_correct
    return {
        "found_exit": found_exit,
        "failure_reason": end_reason,
        "ramp_depth_range": (ramp_lo, ramp_hi),
        "lives_used": lives,
        "total_gates_encountered": total_gates,
        "correct_gates": correct_gates,
        "final_steps": steps,
    }


def check_row_level1(row: dict, deg: DEG) -> None:
    derived = walk_events(row, deg)
    for key in ("found_exit", "lives_used", "total_gates_encountered", "correct_gates"):
        _fail(row.get(key) == derived[key],
              f"{key}: row says {row.get(key)!r}, replay derives {derived[key]!r}")
    _fail(row.get("failure_reason") == derived["failure_reason"],
          f"failure_reason: row says {row.get('failure_reason')!r}, "
          f"replay derives {derived['failure_reason']!r}")
    lo, hi = derived["ramp_depth_range"]
    _fail(lo <= (row.get("ramp_depth") or 0) <= hi,
          f"ramp_depth: row says {row.get('ramp_depth')!r}, replay derives [{lo}, {hi}]")
    total, correct = derived["total_gates_encountered"], derived["correct_gates"]
    expected_acc = (correct / total) if total else None
    acc = row.get("gate_accuracy")
    if expected_acc is None:
        _fail(acc is None, f"gate_accuracy: row says {acc!r}, no gates encountered in replay")
    else:
        _fail(acc is not None and abs(acc - expected_acc) < 1e-9,
              f"gate_accuracy: row says {acc!r}, replay derives {expected_acc!r}")
    if row.get("found_exit"):
        _fail(row.get("steps_to_exit") == derived["final_steps"],
              f"steps_to_exit: row says {row.get('steps_to_exit')!r}, "
              f"replay derives {derived['final_steps']}")


# ---------------------------------------------------------------------------
# Level 2 — full session re-drive from the dispatched actions
# ---------------------------------------------------------------------------

def redrive_session(row: dict, deg: DEG) -> None:
    session = new_session(deg)
    for t in row["turns_log"]:
        action = dict(t.get("action_parsed") or {})
        # A 400→observe fallback dispatched an observe regardless of what was parsed.
        if str(t.get("engine_text", "")).startswith("[400→observe]"):
            action = {"action": "observe"}
        kind = action.get("action") or "observe"
        if kind == "commit":
            session.commit(str(action.get("path_id") or ""), str(action.get("answer") or ""))
        elif kind == "note":
            session.note_action(str(action.get("text") or ""))
        elif kind == "pull":
            session.pull_state()
        elif kind == "inspect":
            session.inspect(str(action.get("path_id") or ""))
        else:
            session.observe()
        if session.completed:
            break
    replayed = session.score()
    # The initial harness observe (pre-loop) is part of the recorded stream; the re-drive
    # starts at the first logged turn, so align on the common suffix-defining fields.
    submitted = row.get("events") or []
    regenerated = replayed["events"]
    offset = len(submitted) - len(regenerated)
    _fail(0 <= offset <= 1,
          f"event count: submitted {len(submitted)}, re-drive produced {len(regenerated)}")
    _fail(submitted[offset:] == regenerated,
          "re-driven event stream diverges from the submitted one")
    for key in ("found_exit", "failure_reason", "ramp_depth", "lives_used",
                "gate_accuracy", "total_gates_encountered", "correct_gates",
                "chain_accuracy", "knowledge_state_consistency"):
        _fail(row.get(key) == replayed[key],
              f"{key}: row says {row.get(key)!r}, re-drive derives {replayed[key]!r}")


# ---------------------------------------------------------------------------
# Entry mode
# ---------------------------------------------------------------------------

def check_entry(path: Path) -> list[str]:
    entry = json.loads(path.read_text())
    problems: list[str] = []
    runs, score = entry.get("runs") or {}, entry.get("score") or {}
    depths = runs.get("depths") or []
    if runs.get("n") != len(depths):
        problems.append(f"runs.n={runs.get('n')} but {len(depths)} depths recorded")
    if not depths:
        problems.append("no run depths recorded")
        return problems
    median = statistics.median(depths)
    if score.get("depth_median") != median:
        problems.append(f"depth_median={score.get('depth_median')} but depths give {median}")
    boot = score.get("bootstrap") or {}
    b, level, seed = boot.get("B"), boot.get("level"), boot.get("seed")
    if all(v is not None for v in (b, level, seed)):
        rng = random.Random(seed)
        n = len(depths)
        medians = sorted(statistics.median(rng.choices(depths, k=n)) for _ in range(b))
        lower = medians[max(0, min(int((1 - level) * b), b - 1))]
        if score.get("ci_lower_median") != lower:
            problems.append(
                f"ci_lower_median={score.get('ci_lower_median')} but seeded recompute gives {lower}")
    else:
        problems.append("score.bootstrap missing B/level/seed — bound not re-derivable")
    declared = entry.get("declared") or {}
    planned = declared.get("planned_n")
    if planned is not None and len(depths) < planned:
        # Shortfall is a visible badge on the board, not an integrity failure — but an
        # UNDECLARED shortfall can't exist once the declaration is present, so say it loudly.
        print(f"  NOTE {path.name}: partial cohort — {len(depths)}/{planned} declared runs present")
    return problems


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", type=Path, help="results JSONL file(s) to replay-check")
    ap.add_argument("--entry", type=Path, action="append", default=[],
                    help="entry JSON file to recheck (repeatable)")
    ap.add_argument("--degs", type=Path, default=Path(__file__).resolve().parent.parent / "degs",
                    help="directory of DEG manifests (default: repo degs/)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if not args.files and not args.entry:
        ap.error("nothing to verify — pass a results JSONL and/or --entry")

    failures = 0
    checked = 0

    if args.files:
        try:
            degs = load_all_degs(args.degs)
        except Exception as e:
            print(f"ERROR: cannot load DEG manifests from {args.degs}: {e}", file=sys.stderr)
            return 2
        for f in args.files:
            try:
                lines = f.read_text().splitlines()
            except OSError as e:
                print(f"ERROR: {e}", file=sys.stderr)
                return 2
            for lineno, line in enumerate(lines, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if "events" not in row:
                    if args.verbose:
                        print(f"  SKIP {f}:{lineno} — no events (error row: {row.get('error')!r})")
                    continue
                checked += 1
                label = f"{f}:{lineno} [{row.get('deg_id')}] {row.get('model', '?')}"
                deg = degs.get(row.get("deg_id"))
                try:
                    _fail(deg is not None, f"unknown deg_id {row.get('deg_id')!r} in {args.degs}")
                    check_row_level1(row, deg)
                    level = "replay(L1)"
                    if row.get("turns_log"):
                        redrive_session(row, deg)
                        level = "replay(L1+L2)"
                    print(f"  PASS {label} — {level}: depth={row.get('ramp_depth')} "
                          f"reason={row.get('failure_reason')}")
                except RowFailure as e:
                    failures += 1
                    print(f"  FAIL {label} — {e}")

    for epath in args.entry:
        checked += 1
        problems = check_entry(epath)
        if problems:
            failures += 1
            print(f"  FAIL {epath}\n" + "\n".join(f"       - {p}" for p in problems))
        else:
            print(f"  PASS {epath} — score block re-derives from its run distribution")

    print(f"\n{checked - failures}/{checked} verified" + (f", {failures} FAILED" if failures else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
