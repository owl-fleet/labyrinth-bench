"""make_mmlu_seed_list.py — generate the frozen E2 MMLU item list (campaign prereg §6).

Produces mmlu_seed_list.json: a stratified 150-item subset of classic MMLU
(cais/mmlu, split=test, 14,042 items, 57 subjects), committed BEFORE any E2 run
per the approved pre-registration (LOCKED 2026-07-06; published in the data
annex). Deterministic: fixed seed, sorted subject order, sorted sample
indices; the JSON records the dataset revision and a content sha256 so any
drift in the upstream dataset is detectable.

Stratification: floor of 2 items per subject (57 x 2 = 114), the remaining 36
allocated by largest remainder proportional to subject test-set size. Sampling
within a subject uses one random.Random(SEED) stream over subjects in sorted
order.

  python3 e2/make_mmlu_seed_list.py

Read-only against Hugging Face's datasets-server REST API; makes no LLM calls.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.request

SEED = 2027  # program convention (rev-2 DEG seed); fixed here before any E2 run
TARGET = 150
FLOOR_PER_SUBJECT = 2
API = "https://datasets-server.huggingface.co/rows?dataset=cais%2Fmmlu&config=all&split=test"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mmlu_seed_list.json")


PAGE_DELAY = 1.0  # polite spacing between pagination calls; the API rate-limits bursts


def fetch(url: str, attempts: int = 8):
    req = urllib.request.Request(url, headers={"User-Agent": "lb-e2-seed-list"})
    for attempt in range(attempts):
        try:
            return json.load(urllib.request.urlopen(req, timeout=30))
        except urllib.error.HTTPError as e:
            if attempt == attempts - 1:
                raise
            retry_after = e.headers.get("Retry-After") if e.headers else None
            wait = int(retry_after) if (retry_after or "").isdigit() else max(15, 2 ** attempt)
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)


def fetch_all_rows():
    rows, offset = [], 0
    total = None
    while total is None or offset < total:
        page = fetch(f"{API}&offset={offset}&length=100")
        total = page["num_rows_total"]
        for r in page["rows"]:
            rows.append((r["row_idx"], r["row"]))
        offset += 100
        if offset % 2000 == 0:
            print(f"  fetched {offset}/{total}")
        time.sleep(PAGE_DELAY)
    assert len(rows) == total, f"pagination mismatch: {len(rows)} != {total}"
    return rows


def allocate(counts: dict[str, int]) -> dict[str, int]:
    """Floor per subject + largest-remainder proportional for the rest."""
    alloc = {s: FLOOR_PER_SUBJECT for s in counts}
    remaining = TARGET - sum(alloc.values())
    pool = sum(counts.values())
    quotas = {s: remaining * counts[s] / pool for s in counts}
    for s in quotas:
        take = min(int(quotas[s]), counts[s] - alloc[s])
        alloc[s] += take
        remaining -= take
    by_remainder = sorted(quotas, key=lambda s: (quotas[s] - int(quotas[s]), s), reverse=True)
    for s in by_remainder:
        if remaining == 0:
            break
        if alloc[s] < counts[s]:
            alloc[s] += 1
            remaining -= 1
    assert remaining == 0
    return alloc


def main():
    revision = fetch("https://huggingface.co/api/datasets/cais/mmlu").get("sha")
    rows = fetch_all_rows()
    by_subject: dict[str, list[tuple[int, dict]]] = {}
    for idx, row in rows:
        by_subject.setdefault(row["subject"], []).append((idx, row))
    counts = {s: len(v) for s, v in by_subject.items()}
    alloc = allocate(counts)

    rng = random.Random(SEED)
    items = []
    for subject in sorted(by_subject):
        member = by_subject[subject]
        for i in sorted(rng.sample(range(len(member)), alloc[subject])):
            idx, row = member[i]
            items.append({
                "source_index": idx,
                "subject": subject,
                "question": row["question"],
                "choices": row["choices"],
                "answer": row["answer"],
            })

    content_sha = hashlib.sha256(
        json.dumps(items, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    out = {
        "meta": {
            "purpose": "E2 frozen item list — LB cohort-campaign prereg §6 (LOCKED 2026-07-06)",
            "dataset": "cais/mmlu", "config": "all", "split": "test",
            "dataset_revision": revision,
            "seed": SEED, "n_items": len(items), "n_subjects": len(by_subject),
            "stratification": f"floor {FLOOR_PER_SUBJECT}/subject + largest-remainder proportional",
            "content_sha256": content_sha,
        },
        "items": items,
    }
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"wrote {OUT}: {len(items)} items, {len(by_subject)} subjects, sha256={content_sha[:16]}…, revision={revision}")


if __name__ == "__main__":
    main()
