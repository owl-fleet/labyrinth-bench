"""Deterministic reasoning-pathology detectors over LB run logs — reasoning-monitor slice 1.

Pure post-hoc analysis: JSONL run logs in, per-run per-turn signal timelines out, plus a
validation report scoring each detector against its target failure class.

INPUT / ANSWER-KEY SEPARATION (the discipline that makes the result mean anything):
the detectors consume ONLY the model-/harness-visible stream — `turns_log[].action_parsed`
and `engine_text` — reconstructing state online the way a live monitor would (its OWN ledger
from observed [STATE] blocks and CORRECT'd set-gates, its OWN visit counts from `Location:`
lines). The engine's ground-truth fields (`failure_reason`, `loop_trapped`, `out_of_lives`,
...) are the held-out answer key, read ONLY inside `score_corpus()` — never as detector input.

Detectors (deterministic rules, stream-only; thresholds are explicit and reported):
  loop        -> targets loop_trapped:   re-entry to a location seen as DEAD_END, or any
                 location entered >= K_LOOP times.
  stall       -> targets budget_exhausted / out_of_lives: N_STALL turns elapsed without
                 discovering a NEW location (locked gates / wrong answers keep you put).
  discrepancy -> targets out_of_lives:   a committed answer that conflicts with the stream —
                 either repeating an answer already marked WRONG at the same location, or
                 contradicting the online-reconstructed ledger on a parseable gate problem.
  thrash      -> the 120B re-verification jitter (descriptive; no terminal class in corpus):
                 >= K_THRASH consecutive informational actions (observe/pull/note) without a
                 commit, or re-committing at a gate that already returned CORRECT (reverify).

Validation per detector vs its target class: precision / recall, lead-time (turns between
first fire and the terminal event — zero-lead fires don't count as flags), and the
false-positive rate on clean exits (the alert-fatigue / gravity-budget check). Thresholds
are defaults chosen a priori; --sweep tunes on the even-hash split and reports the chosen
values on the odd-hash holdout, so reported numbers are not tuned-on-test.

Usage (inside the sandbox container, repo mounted at /app, results at /results):
    python cli/detect_pathologies.py --results /results --out /results/pathology
    python cli/detect_pathologies.py --results /results --out /results/pathology --sweep
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import statistics
from collections import Counter, defaultdict

# ---------------------------------------------------------------------------
# Stream parsing (model-/harness-visible text only)
# ---------------------------------------------------------------------------

LOC_RE = re.compile(r"^Location:\s*(\S+)", re.MULTILINE)
HERE_RE = re.compile(r"(\w+) \(here\)")  # nav-generation MAP overlays
STATE_VAR_RE = re.compile(r"\b([A-H])\s*=\s*(-?\d+)\b")
GATE_PATH_RE = re.compile(r"^\s*(\w+):.*?\[GATE\s+([a-z0-9_]+):\s*([^\]]+)\]", re.MULTILINE)
SET_GATE_RE = re.compile(r"\bSet\s+([A-H])\s+to\s+(-?\d+)", re.IGNORECASE)

INFO_ACTIONS = {"observe", "pull", "note"}

# Gate-problem grammar (rev-2 family). Unparseable problems simply aren't evaluated —
# coverage is counted and reported rather than guessed at.
_P_ADD = re.compile(
    r"Add the current value of ([A-H]) to the current value of ([A-H])", re.IGNORECASE)
_P_SUB = re.compile(
    r"Subtract the current value of ([A-H]) from the current value of ([A-H])", re.IGNORECASE)
_P_LARGER = re.compile(
    r"larger of the current values of ([A-H]) and ([A-H])", re.IGNORECASE)
_P_LARGER_SUMS = re.compile(
    r"larger of \(current ([A-H]) \+ current ([A-H])\) and \(current ([A-H]) \+ current ([A-H])\)",
    re.IGNORECASE)
_P_SUM_ALL = re.compile(r"Add the current values of all eight variables", re.IGNORECASE)


def eval_gate_problem(text, ledger):
    """Return (expected_answer, parseable) for a gate problem against the online ledger.

    expected_answer is None when the problem references a variable the stream hasn't
    revealed yet (honest online reconstruction — a live monitor wouldn't know it either).
    """
    m = SET_GATE_RE.search(text)
    if m:
        return int(m.group(2)), True
    m = _P_ADD.search(text)
    if m:
        a, b = m.group(1), m.group(2)
        if a in ledger and b in ledger:
            return ledger[a] + ledger[b], True
        return None, True
    m = _P_SUB.search(text)
    if m:
        a, b = m.group(1), m.group(2)
        if a in ledger and b in ledger:
            return ledger[b] - ledger[a], True
        return None, True
    m = _P_LARGER_SUMS.search(text)
    if m:
        a, b, c, d = m.groups()
        if all(v in ledger for v in (a, b, c, d)):
            return max(ledger[a] + ledger[b], ledger[c] + ledger[d]), True
        return None, True
    m = _P_LARGER.search(text)
    if m:
        a, b = m.group(1), m.group(2)
        if a in ledger and b in ledger:
            return max(ledger[a], ledger[b]), True
        return None, True
    if _P_SUM_ALL.search(text):
        if all(v in ledger for v in "ABCDEFGH"):
            return sum(ledger[v] for v in "ABCDEFGH"), True
        return None, True
    return None, False


def parse_turn(turn):
    """Extract the stream-visible facts from one turn."""
    ap = turn.get("action_parsed") or {}
    et = turn.get("engine_text") or ""
    loc = None
    m = LOC_RE.search(et)
    if m:
        loc = m.group(1)
    else:
        m = HERE_RE.search(et)
        if m:
            loc = m.group(1)
    gates = {}  # path_id -> (gate_id, problem_text), at the location shown in this text
    for path_id, gate_id, prob in GATE_PATH_RE.findall(et):
        gates[path_id] = (gate_id, prob.strip())
    return {
        "turn": turn.get("turn"),
        "action": ap.get("action"),
        "path_id": ap.get("path_id"),
        "answer": ap.get("answer"),
        "loc": loc,
        "dead_end": "--- DEAD_END ---" in et,
        "correct": "Gate answer: CORRECT" in et,
        "wrong": "Gate answer: WRONG" in et,
        "state_vars": STATE_VAR_RE.findall(et) if "[STATE" in et else [],
        "gates": gates,
    }


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------

DEFAULTS = {"k_loop": 3, "n_stall": 8, "k_thrash": 4}


def detect_run(turns_log, k_loop, n_stall, k_thrash):
    """Run all detectors over one run's visible stream. Returns the event timeline."""
    events = []
    visits = Counter()
    dead_ends = set()
    seen_locs = set()
    prev_loc = None
    last_new_loc_turn = 0
    stall_armed = True
    consec_info = 0
    thrash_armed = True
    ledger = {}
    wrong_history = defaultdict(set)      # loc -> {answers marked WRONG there}
    correct_locs = set()                  # locations whose gate already returned CORRECT
    pending_gates = {}                    # loc -> {path_id: (gate_id, problem_text)}
    dead_paths = set()                    # (loc, path_id) whose commit led to DEAD_END
    last_commit = None                    # (loc, path_id) of the most recent commit
    parse_cov = Counter()

    for raw in turns_log:
        t = parse_turn(raw)
        tn = t["turn"] or 0

        # --- online ledger from the stream
        for var, val in t["state_vars"]:
            ledger[var] = int(val)

        # --- loop (interception form): committing a path already seen to lead to a DEAD_END.
        # This is the guardian's all-dead-destination rule reconstructed from the stream; it
        # fires AT the fatal action (usually the terminal turn), so it scores as
        # "interceptable", not as pre-terminal warning.
        if t["action"] == "commit" and prev_loc is not None and t["path_id"] is not None:
            if (prev_loc, t["path_id"]) in dead_paths:
                events.append({"turn": tn, "det": "loop",
                               "detail": "dead_path_commit@%s:%s" % (prev_loc, t["path_id"])})
            last_commit = (prev_loc, t["path_id"])

        # --- discrepancy: evaluated at commit time, against state BEFORE this turn's feedback
        if t["action"] == "commit" and t["answer"] is not None and prev_loc is not None:
            ans = str(t["answer"]).strip()
            if ans in wrong_history[prev_loc]:
                events.append({"turn": tn, "det": "discrepancy",
                               "detail": "repeat_wrong@%s=%s" % (prev_loc, ans)})
            gates_here = pending_gates.get(prev_loc, {})
            gate = gates_here.get(t["path_id"]) or (
                next(iter(gates_here.values())) if len(gates_here) == 1 else None)
            if gate is not None:
                expected, parseable = eval_gate_problem(gate[1], ledger)
                parse_cov["parseable" if parseable else "unparseable"] += 1
                if expected is not None:
                    try:
                        if int(float(ans)) != expected:
                            events.append({"turn": tn, "det": "discrepancy",
                                           "detail": "ledger_conflict@%s:%s ans=%s exp=%s"
                                           % (prev_loc, gate[0], ans, expected)})
                    except ValueError:
                        pass

        # --- thrash: informational churn without commits; reverify of a CORRECT'd gate
        if t["action"] in INFO_ACTIONS:
            consec_info += 1
            if consec_info >= k_thrash and thrash_armed:
                events.append({"turn": tn, "det": "thrash",
                               "detail": "info_churn=%d" % consec_info})
                thrash_armed = False
        else:
            consec_info = 0
            thrash_armed = True
        if (t["action"] == "commit" and t["answer"] is not None
                and prev_loc in correct_locs):
            events.append({"turn": tn, "det": "thrash",
                           "detail": "reverify@%s" % prev_loc})

        # --- feedback bookkeeping (this turn's engine response)
        if t["wrong"] and prev_loc is not None and t["answer"] is not None:
            wrong_history[prev_loc].add(str(t["answer"]).strip())
        if t["correct"] and prev_loc is not None:
            correct_locs.add(prev_loc)

        # --- location transitions: loop + stall
        loc = t["loc"]
        if loc is not None and loc != prev_loc:
            visits[loc] += 1
            if loc in dead_ends:
                events.append({"turn": tn, "det": "loop",
                               "detail": "dead_end_reentry@%s visit=%d" % (loc, visits[loc])})
            elif visits[loc] >= k_loop:
                events.append({"turn": tn, "det": "loop",
                               "detail": "revisit@%s visit=%d" % (loc, visits[loc])})
            if loc not in seen_locs:
                seen_locs.add(loc)
                last_new_loc_turn = tn
                stall_armed = True
            prev_loc = loc
        if t["dead_end"]:
            if loc is not None:
                dead_ends.add(loc)
            if last_commit is not None:
                dead_paths.add(last_commit)
        if stall_armed and tn - last_new_loc_turn >= n_stall:
            events.append({"turn": tn, "det": "stall",
                           "detail": "no_new_loc_for=%d" % (tn - last_new_loc_turn)})
            stall_armed = False

        if loc is not None and t["gates"]:
            pending_gates[loc] = t["gates"]

    return events, dict(parse_cov)


# ---------------------------------------------------------------------------
# Corpus + scoring (the ONLY place answer-key fields are read)
# ---------------------------------------------------------------------------

FAILURE_CLASSES = {"loop_trapped", "out_of_lives", "impossible",
                   "budget_exhausted", "dead_end_trapped"}
TARGETS = {
    "loop": {"loop_trapped"},
    "stall": {"budget_exhausted", "out_of_lives"},
    "discrepancy": {"out_of_lives"},
    # thrash: descriptive — no terminal class in this corpus (its targets exited cleanly)
}


def load_corpus(results_dir):
    """Pre-registered corpus filter: full turns_log + (clean exit | named failure class)."""
    corpus = []
    for fn in sorted(glob.glob(os.path.join(results_dir, "*.jsonl"))):
        with open(fn) as fh:
            for idx, line in enumerate(fh):
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not r.get("turns_log"):
                    continue
                # ---- answer key (held out from detectors) ----
                if r.get("found_exit"):
                    cls = "exit"
                elif r.get("failure_reason") in FAILURE_CLASSES:
                    cls = r["failure_reason"]
                else:
                    continue
                rid = "%s:%d" % (os.path.basename(fn), idx)
                split = "tune" if int(hashlib.sha1(rid.encode()).hexdigest(), 16) % 2 == 0 \
                    else "holdout"
                corpus.append({"rid": rid, "file": os.path.basename(fn), "idx": idx,
                               "model": r.get("model"), "label": r.get("run_label"),
                               "cls": cls, "split": split,
                               "terminal_turn": (r["turns_log"][-1].get("turn")
                                                 or len(r["turns_log"])),
                               "turns_log": r["turns_log"]})
    return corpus


def run_detectors(corpus, params):
    out = []
    for rec in corpus:
        events, cov = detect_run(rec["turns_log"], params["k_loop"],
                                 params["n_stall"], params["k_thrash"])
        first_fire = {}
        for ev in events:
            d = ev["det"]
            if d not in first_fire:
                first_fire[d] = ev["turn"]
        out.append({"rid": rec["rid"], "file": rec["file"], "idx": rec["idx"],
                    "model": rec["model"], "label": rec["label"], "cls": rec["cls"],
                    "split": rec["split"], "terminal_turn": rec["terminal_turn"],
                    "events": events, "first_fire": first_fire, "parse_cov": cov})
    return out


def score(results, split=None):
    """Per-detector precision/recall vs target class, lead-time, FP rate on clean exits.

    A run counts as flagged only if the first fire PRECEDES the terminal turn
    (zero-lead fires re-state the outcome and don't count).
    """
    rows = [r for r in results if split is None or r["split"] == split]
    exits = [r for r in rows if r["cls"] == "exit"]
    table = {}
    for det, targets in TARGETS.items():
        flagged = [r for r in rows if det in r["first_fire"]
                   and r["first_fire"][det] < r["terminal_turn"]]
        in_class = [r for r in rows if r["cls"] in targets]
        tp = [r for r in flagged if r["cls"] in targets]
        fp_exit = [r for r in exits if det in r["first_fire"]
                   and r["first_fire"][det] < r["terminal_turn"]]
        leads = [r["terminal_turn"] - r["first_fire"][det] for r in tp]
        # interception: ANY fire up to and including the terminal turn (the guardian's
        # use — block at dispatch — as opposed to pre-terminal warning)
        intercept = [r for r in in_class if det in r["first_fire"]]
        table[det] = {
            "targets": "/".join(sorted(targets)),
            "n_class": len(in_class), "flagged": len(flagged), "tp": len(tp),
            "precision": len(tp) / len(flagged) if flagged else None,
            "recall": len(tp) / len(in_class) if in_class else None,
            "fp_exit_rate": len(fp_exit) / len(exits) if exits else None,
            "lead_median": statistics.median(leads) if leads else None,
            "lead_min": min(leads) if leads else None,
            "interceptable": len(intercept) / len(in_class) if in_class else None,
        }
    # fire matrix: detector x class (counts of pre-terminal flags)
    matrix = defaultdict(Counter)
    for r in rows:
        for det, t0 in r["first_fire"].items():
            if t0 < r["terminal_turn"]:
                matrix[det][r["cls"]] += 1
    return table, matrix, Counter(r["cls"] for r in rows)


def fmt_pct(x):
    return "  --" if x is None else "%4.0f%%" % (100 * x)


def print_report(results, params, title):
    print("=" * 78)
    print(title)
    print("thresholds: k_loop=%(k_loop)d  n_stall=%(n_stall)d  k_thrash=%(k_thrash)d" % params)
    for split in (None, "tune", "holdout"):
        table, matrix, census = score(results, split)
        name = split or "ALL"
        print("-" * 78)
        print("[%s]  census: %s" % (name, dict(census)))
        print("%-12s %-28s %5s %5s %5s %6s %6s %7s %9s" %
              ("detector", "target", "prec", "rec", "intc", "FPexit", "n_tgt", "flagged",
               "lead(med/min)"))
        for det, row in table.items():
            lead = ("%s/%s" % (row["lead_median"], row["lead_min"])
                    if row["lead_median"] is not None else "--")
            print("%-12s %-28s %s %s %s %s %6d %7d %9s" %
                  (det, row["targets"], fmt_pct(row["precision"]), fmt_pct(row["recall"]),
                   fmt_pct(row["interceptable"]), fmt_pct(row["fp_exit_rate"]),
                   row["n_class"], row["flagged"], lead))
        print("fire matrix (pre-terminal first-fires per class):")
        for det in sorted(matrix):
            print("  %-12s %s" % (det, dict(matrix[det])))


def sweep(corpus):
    """Tune thresholds on the even-hash split (best F1 vs target, FP-penalized)."""
    best = dict(DEFAULTS)
    grids = {"k_loop": [2, 3, 4, 5], "n_stall": [5, 8, 12, 16], "k_thrash": [3, 4, 6, 8]}
    for key, values in grids.items():
        scores = []
        for v in values:
            params = dict(best, **{key: v})
            results = run_detectors([c for c in corpus if c["split"] == "tune"], params)
            table, _, _ = score(results)
            f1s = []
            for det, row in table.items():
                p, r = row["precision"], row["recall"]
                if p and r:
                    f1s.append(2 * p * r / (p + r) - 0.5 * (row["fp_exit_rate"] or 0))
            scores.append((statistics.mean(f1s) if f1s else 0.0, v))
        best[key] = max(scores)[1]
        print("sweep %s: %s -> chose %s" % (key, [(round(s, 3), v) for s, v in scores], best[key]))
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--results", default="/results")
    ap.add_argument("--out", default="/results/pathology")
    ap.add_argument("--k-loop", type=int, default=DEFAULTS["k_loop"])
    ap.add_argument("--n-stall", type=int, default=DEFAULTS["n_stall"])
    ap.add_argument("--k-thrash", type=int, default=DEFAULTS["k_thrash"])
    ap.add_argument("--sweep", action="store_true",
                    help="tune thresholds on the even-hash split first")
    args = ap.parse_args()

    corpus = load_corpus(args.results)
    print("corpus: %d runs (%s)" % (len(corpus), dict(Counter(c["cls"] for c in corpus))))

    params = {"k_loop": args.k_loop, "n_stall": args.n_stall, "k_thrash": args.k_thrash}
    if args.sweep:
        params = sweep(corpus)

    results = run_detectors(corpus, params)
    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, "timelines.jsonl")
    with open(out_path, "w") as fh:
        for r in results:
            fh.write(json.dumps(r) + "\n")
    cov = Counter()
    for r in results:
        cov.update(r["parse_cov"])
    print("gate-problem parse coverage at commit time: %s" % dict(cov))
    print("timelines written: %s" % out_path)
    print_report(results, params, "Pathology-detector validation (reasoning-monitor slice 1)")


if __name__ == "__main__":
    main()
