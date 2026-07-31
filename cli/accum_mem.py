"""Cross-run memory faculty for the LB Design 2 accumulation eval.

The organism-level LTM test: does an accumulating, self-curating KOS memory make the
loop measurably better over repeated runs? This module is the *only* place the LB harness
touches the real knowledge store — through the HTTP /search + /ingest/document API on
the ingestion worker, NOT the raw-SQL labyrinth_session path in run_oracle.py (which
bypasses embedding/geometry/the currency dam and would test a WHERE clause, not the organism).

Three arms, one axis (cross-run memory). The WITHIN-run HUD config is held identical across
arms; only the read/curate policy here changes:

  A0  control   — never retrieves (write still happens, so the store is identical across arms)
  A1  naive     — flat vector search, equal weight, no outcome/recency/currency filter
  A2  organism  — route + currency-dam + fork, then LB-layer outcome-demote + recency

Write is byte-identical across arms (only metadata.arm differs) so memory is reliably
load-bearing and we never confound on "A2 wrote a richer record."

Run the Gate 1a plumbing smoke (write one record -> retrieve it through /search, assert it
round-trips, clears the 0.60 floor, and the A2 flags are honoured) with:

    python3 cli/accum_mem.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any, Optional

import httpx

_K_RE = re.compile(r"\bK=(\d+)")        # extract the forged constant from a record's raw_text
_RUN_RE = re.compile(r"run #(\d+)")     # extract the originating run_index (the recency signal) from raw_text


def _record_k(row: dict) -> Optional[str]:
    """The forged constant K a retrieved record asserts (for the live/stale differentiation metric)."""
    m = _K_RE.search(row.get("raw_text", "") or "")
    return m.group(1) if m else None


def _row_run_index(row: dict) -> int:
    """The run_index a record was written on — the recency signal, parsed from raw_text (/search returns
    slim rows without metadata JSONB). Higher = more recent; -1 if absent."""
    m = _RUN_RE.search(row.get("raw_text", "") or "")
    return int(m.group(1)) if m else -1

# Point MEM_INGEST_URL at your ingestion endpoint if it is not on localhost.
DEFAULT_INGEST_URL = os.environ.get("MEM_INGEST_URL", "http://localhost:8080")

# The score_threshold the in-maze query must clear. Kept explicit (not the server default)
# so the recall-floor guard (B-6) is visible and tunable from the harness.
RECALL_FLOOR = float(os.environ.get("MEM_SCORE_THRESHOLD", "0.55"))

# Design-2 follow-on (recency curation): the A2W/A2R arms widen the retrieval window so the currency
# dam isn't STARVED of fresh candidates — the default top_k=6 is dominated by stale epoch-1 twins, so
# the fresh value rarely reaches the dam to survive. Widen → the dam drops the stale, fresh remains.
_WIDE_TOP_K = int(os.environ.get("MEM_WIDE_TOP_K", "40"))

# Per-arm /search flag presets. EXPLICIT on every field so the env-gated defaults
# (KOS_ROUTE_DEFAULT / KOS_FLOW_DEFAULT / KOS_FORK_DEFAULT) can never silently turn the
# organism's faculties off and make A2 == A1+sort (flattery audit A-1).
ARM_PRESETS: dict[str, Optional[dict]] = {
    "A0": None,                                                  # never search
    "A1": {"route": False, "currency": "", "fork": False},       # naive flat
    "A2": {"route": True, "currency": "current", "fork": True},  # organism
    # Design-2 follow-on (recency curation): same dam as A2, differing only downstream of /search —
    # A2W widens the window so the dam sees fresh candidates; A2R also applies the recency sort the
    # retrieve_memory_block docstring promises but never implemented. (top_k + sort handled below.)
    "A2W": {"route": True, "currency": "current", "fork": True},  # dam + WIDE window, no recency sort
    "A2R": {"route": True, "currency": "current", "fork": True},  # dam + WIDE window + recency sort
    # ablations (only wired when A2 wins):
    "A3": {"route": False, "currency": "current", "fork": True},  # trust, no geometry
    "A4": {"route": True, "currency": "", "fork": False},         # geometry, no trust
}

# Outcomes that mark a record as from a FAILED run, untrustworthy for the A2 outcome-demote (LB-layer).
_BAD_OUTCOMES = {"stale", "failed", "dnf", "out_of_lives", "budget_exhausted",
                 "dead_end_trapped", "loop_trapped", "impossible"}
_OUTCOME_RE = re.compile(r"Outcome:\s*([A-Za-z_]+)")


def deg_family(deg_id: str) -> str:
    """`macguffin-shift-1` -> `macguffin-shift`; `replay-pos-0` -> `replay-pos`.

    Trailing `-<int>` is the variant index; everything before it is the family."""
    parts = deg_id.rsplit("-", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0]
    return deg_id


def build_query(deg_id: str, briefing: str = "") -> str:
    """The in-maze retrieval query. Overlaps the record's vocabulary ("forged constants",
    "gate answers", "route to the exit") so it clears the recall floor (B-6); the briefing
    sharpens it per family. Collection-scoping does the family isolation, so the query only
    has to surface this family's own records above the floor."""
    fam = deg_family(deg_id)
    base = (f"{fam} task: notes from my past runs — forged constants and their values, "
            f"gate answers, the route to the exit, and which values went stale.")
    return (base + " " + briefing.strip())[:500] if briefing else base


class MemoryClient:
    """Thin httpx client over the dev KOS HTTP API. Pure I/O — arm policy lives in the caller."""

    def __init__(self, ingest_url: str = DEFAULT_INGEST_URL, timeout: float = 120.0):
        self.ingest_url = ingest_url.rstrip("/")
        # embedding (ingest + query) can take a few seconds on the 8b embed model
        self._http = httpx.Client(base_url=self.ingest_url, timeout=timeout)

    def close(self) -> None:
        self._http.close()

    # ---- write -----------------------------------------------------------------
    def ingest_record(self, record: dict, retries: int = 4) -> dict:
        """POST /ingest/document. Synchronous + idempotent (content_hash dedup on raw_text).

        Retries on transient failures: the worker embeds synchronously against the shared embed
        model on .11, which under eval load (14b inference + 8b embed on the same GPU) can time out
        or 5xx. A SILENTLY dropped write breaks the learning curve, so we retry with backoff and
        raise loudly on exhaustion rather than let one missing record corrupt the accumulation."""
        last_err: str = "unknown"
        for attempt in range(retries):
            try:
                r = self._http.post("/ingest/document", json=record)
                r.raise_for_status()
                body = r.json()
                # CRITICAL: a 202 does NOT mean a chunk landed. Under embed contention the worker
                # returns 200/202 with chunks_written=0 (the embed failed server-side, no exception)
                # — a SILENT drop that fakes success and breaks the learning curve. Verify a chunk
                # actually persisted (written, or skipped == already there) before trusting it.
                if (body.get("chunks_written", 0) + body.get("chunks_skipped", 0)) >= 1:
                    return body
                last_err = f"202 but chunks_written=0 (embed dropped): {body}"
            except (httpx.HTTPError, httpx.HTTPStatusError) as e:
                last_err = str(e)
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))      # 1.5s, 3s, 4.5s backoff for the embed to drain
        raise RuntimeError(f"ingest_record failed after {retries} attempts: {last_err}")

    # ---- read ------------------------------------------------------------------
    def search(
        self,
        query_text: str,
        *,
        route: bool,
        currency: str,
        fork: bool,
        top_k: int = 6,
        collection: str = "",
        source_type_filter: str = "labyrinth_session",
        score_threshold: float = RECALL_FLOOR,
    ) -> tuple[list[dict], Optional[dict], dict]:
        """POST /search with EXPLICIT route/currency/fork. Returns (results, verdict, raw).

        Handles both response shapes: a bare list (no fork/fact_route) and the wrapped
        {results, verdict} (fork on). currency mutates rows in place (currency_dammed)."""
        body = {
            "query_text": query_text,
            "top_k": top_k,
            "score_threshold": score_threshold,
            "route": route,
            "currency": currency,
            "fork": fork,
            "source_type_filter": source_type_filter,
            # CACHE BUST (accumulation correctness): /search has a 300s query-keyed result cache
            # that ingest does NOT invalidate (main.py:1099). Within one --runs N invocation we write
            # between reads, so run N MUST see runs 1..N-1's records. currency/fork already bypass the
            # cache, but A1 (naive) sets neither — without this it would read a frozen run-1 view, an
            # asymmetry that silently flatters A2. include_lineage=True forces the bypass for every arm.
            "include_lineage": True,
        }
        if collection:
            body["collection"] = collection
            body["collection_subtree"] = True
        resp = self._http.post("/search", json=body)
        resp.raise_for_status()
        raw = resp.json()
        if isinstance(raw, dict):
            return raw.get("results", []), raw.get("verdict"), raw
        return raw, None, {"results": raw}


def build_record(
    arm: str,
    deg_id: str,
    deg_variant: str,
    run_index: int,
    score: dict,
    session_state: Optional[dict] = None,
    macguffin_slot: Optional[str] = None,
) -> dict:
    """Assemble the deterministic, arm-identical run-record.

    Only metadata.arm + collection's <arm> segment differ across arms — everything
    else (raw_text, retention, asserted_facts) is byte-identical so A1 and A2 read the
    same store (flattery audit A-5). `derived` carries the in-session var_ledger (the
    forged constants, e.g. K); `gate_answers` the gate_results map. asserted_facts is
    what the currency dam's pass-2 reads against fresh Oath canon at Gate 4."""
    state = session_state or {}
    gate_answers: dict = state.get("gate_results", {}) or {}
    derived: dict = state.get("var_ledger", {}) or {}
    outcome = score.get("failure_reason") or ("exit" if score.get("found_exit") else "dnf")
    fam = deg_family(deg_id)
    sid = str(state.get("session_id", score.get("session_id", "unknown")))
    # Each record is a DISTINCT run; its text must be globally unique or the KOS content_hash dedup
    # (md5 of raw_text, collection-blind) silently collapses identical-summary records ACROSS arms —
    # whichever arm runs second gets chunks_skipped and an EMPTY store. A0 run0 and A1 run0 otherwise
    # produce byte-identical text. A short session ref (like a real note id) keeps A-5's INTENT (no arm
    # gets richer info; the ref is symmetric + opaque) while guaranteeing uniqueness.
    sid8 = sid[:8]

    # vocabulary in raw_text must overlap the in-maze retrieval query or it never clears
    # the recall floor (B-6): name the family, the forged constants, and the outcome.
    derived_str = ", ".join(f"{k}={v}" for k, v in sorted(derived.items())) or "none recorded"
    record_text = (
        f"LabyrinthBench run on {deg_id} (variant {deg_variant}, run #{run_index}). "
        f"Forged constants: {derived_str}. "
        f"Gates passed: {len(gate_answers)} (ramp_depth {score.get('ramp_depth', '?')}). "
        f"Outcome: {outcome.upper()}. "
        f"To clear the door, recall the constant K and compute the seal value from it. "
        f"[ref {sid8}]"
    )

    asserted_facts = []
    if macguffin_slot and "K" in derived:
        asserted_facts = [{"slot": macguffin_slot, "value": str(derived["K"])}]

    return {
        "source_uri": f"labyrinth://{arm}/{deg_id}/{state.get('session_id', score.get('session_id', 'unknown'))}",
        "source_type": "labyrinth_session",
        "collection": f"labyrinth/{arm}/{fam}",
        "retention": "prunable",           # IDENTICAL across arms — never vary by outcome (A-5)
        "text": record_text,
        "metadata": {
            "arm": arm,
            "deg_id": deg_id,
            "deg_family": fam,
            "deg_variant": deg_variant,
            "run_index": run_index,
            "outcome": outcome,
            "found_exit": bool(score.get("found_exit")),
            "ramp_depth": score.get("ramp_depth"),
            "gate_answers": gate_answers,
            "derived": derived,
            "ts": time.time(),
            "asserted_facts": asserted_facts,
        },
    }


def retrieve_memory_block(
    client: MemoryClient,
    arm: str,
    query_text: str,
    deg_id: str,
    *,
    top_k: int = 6,
) -> tuple[str, dict]:
    """Arm-appropriate retrieval -> a [MEMORY] block for the system prompt + a debug dict.

    A0 returns ("", {...}) and NEVER calls /search (guarantee-A0-never-reads). A1 injects
    raw equal-weight. A2/A3 retrieve with the organism flags, then apply the currency dam +
    LB-layer outcome-demote (NO recency sort — that gap is the Design-2 follow-on). A2W widens
    the window (un-starve the dam); A2R adds the recency sort (newest-first) on top of A2W."""
    debug: dict[str, Any] = {"arm": arm, "retrievals": 0, "query": query_text}
    preset = ARM_PRESETS.get(arm)
    if preset is None:                         # A0: never read
        return "", debug

    fam = deg_family(deg_id)
    eff_top_k = _WIDE_TOP_K if arm in ("A2W", "A2R") else top_k  # recency follow-on: don't starve the dam
    results, verdict, raw = client.search(
        query_text, top_k=eff_top_k, collection=f"labyrinth/{arm}/{fam}", **preset
    )
    # Differentiation instrumentation (live/stale): record, in RANK ORDER, the forged constant K each
    # retrieved record asserts and whether the currency dam flagged it stale. On a shifted family this
    # exposes the stale twin (e.g. 5056) vs the fresh value (e.g. 4970) and which one ranked first.
    debug.update(retrievals=1, n_results=len(results), verdict=verdict, raw_request=preset,
                 retrieved_k=[_record_k(r) for r in results],
                 dammed_k=[_record_k(r) for r in results if r.get("currency_dammed")],
                 dammed=[r.get("source_uri") for r in results if r.get("currency_dammed")])

    if arm in ("A2", "A3", "A2W", "A2R"):
        # (1) THE CURRENCY DAM (server-side real oath_adjudicate, currency="current"): DROP records the
        #     dam flagged stale vs FRESH fact-store canon. The dam's verdict = do not trust this value now.
        #     This is the mechanism that catches a stale-but-SUCCESSFUL record (outcome=exit) — the
        #     poison the outcome-demote structurally cannot see.
        before = len(results)
        results = [r for r in results if not r.get("currency_dammed")]
        debug["dam_dropped"] = before - len(results)
        # (2) LB-layer OUTCOME-DEMOTE (attributed separately): drop records from FAILED runs. Parsed
        #     from raw_text because /search returns slim rows (no metadata JSONB). Orthogonal to the dam.
        kept = [r for r in results if _row_outcome(r) not in _BAD_OUTCOMES]
        debug["outcome_demoted"] = len(results) - len(kept)
        results = kept
        if arm == "A2R":   # the recency sort the docstring above promises but never implemented:
            results.sort(key=_row_run_index, reverse=True)   # newest-first → the fresh K outranks the stale twins
            debug["recency_sorted"] = len(results)

    if not results:
        return "", debug

    lines = ["[MEMORY — notes from your own past runs on this task family]"]
    for r in results:
        tag = " (FLAGGED STALE)" if r.get("currency_dammed") else ""
        lines.append(f"- {r.get('raw_text', '').strip()}{tag}")
    return "\n".join(lines) + "\n", debug


def _row_outcome(r: dict) -> str:
    """The run outcome a record reports. /search returns slim rows (no metadata JSONB), so parse it
    from raw_text ('... Outcome: EXIT ...')."""
    m = _OUTCOME_RE.search(r.get("raw_text", "") or "")
    return m.group(1).lower() if m else ""


# ---------------------------------------------------------------------------
# Gate 1a — the plumbing smoke. The cheapest thing that can break (mandate):
# write one record, retrieve it through the REAL /search HTTP API with both the
# A1 (flat) and A2 (route+currency+fork) flag sets, and assert it round-trips,
# clears the recall floor, and the organism path runs without error.
# ---------------------------------------------------------------------------
def _gate1a_smoke() -> int:
    ingest_url = os.environ.get("MEM_INGEST_URL", DEFAULT_INGEST_URL)
    print(f"[gate1a] ingest_url = {ingest_url}")
    client = MemoryClient(ingest_url)
    fails: list[str] = []

    # an isolated collection so the smoke doesn't depend on / disturb other dev rows
    smoke_arm = "_smoke"
    smoke_deg = "macguffin-shift-1"
    fam = deg_family(smoke_deg)
    session_id = f"g1a-{int(time.time())}"
    record = build_record(
        arm=smoke_arm, deg_id=smoke_deg, deg_variant="v0", run_index=1,
        score={"found_exit": True, "failure_reason": "exit", "ramp_depth": 8,
               "session_id": session_id},
        session_state={"session_id": session_id,
                       "gate_results": {"forge_K": "90", "door_K": "272"},
                       "var_ledger": {"P": 14, "Q": 23, "R": 9, "K": 90}},
        macguffin_slot="fact://lab/macguffin/k",
    )
    print(f"[gate1a] writing record: {record['source_uri']}")
    ing = client.ingest_record(record)
    print(f"[gate1a] /ingest/document -> {json.dumps(ing)[:300]}")
    if not ing.get("chunks_written") and not ing.get("chunks_skipped"):
        fails.append("ingest wrote 0 chunks (and none skipped) — write path broken")

    # the in-maze query an agent at the door would issue: shares vocab with the record
    query = "recall the forged constant K to compute the door seal value"

    for arm, expect_wrap in (("A1", False), ("A2", True)):
        preset = ARM_PRESETS[arm]
        results, verdict, raw = client.search(
            query, collection=f"labyrinth/{smoke_arm}/{fam}", **preset)
        scores = [round(r.get("score", 0.0), 4) for r in results]
        uris = [r.get("source_uri") for r in results]
        print(f"\n[gate1a] arm={arm} flags={preset}")
        print(f"[gate1a]   n_results={len(results)} scores={scores}")
        print(f"[gate1a]   uris={uris}")
        if verdict is not None:
            print(f"[gate1a]   verdict={verdict}")
        # B-6: record must come back and clear the floor
        if record["source_uri"] not in uris:
            fails.append(f"{arm}: record did NOT round-trip through /search (recall floor / scope)")
        else:
            top = next(r for r in results if r["source_uri"] == record["source_uri"])
            if top.get("score", 0.0) < RECALL_FLOOR:
                fails.append(f"{arm}: record score {top.get('score'):.4f} < floor {RECALL_FLOOR}")
        # A-1: the A2 organism path must actually run (wrapped response = fork fired)
        if expect_wrap and not isinstance(raw, dict):
            fails.append(f"{arm}: expected wrapped {{results,verdict}} (fork on) — got bare list")

    client.close()
    print("\n" + ("=" * 60))
    if fails:
        print("[gate1a] FAIL — first breaks found (this is the point):")
        for f in fails:
            print(f"  ✗ {f}")
        return 1
    print("[gate1a] PASS — record round-trips through the real /search for A1 and A2,")
    print("         clears the recall floor, and the organism (route+currency+fork) path runs.")
    return 0


if __name__ == "__main__":
    sys.exit(_gate1a_smoke())
