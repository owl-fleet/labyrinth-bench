"""One-shot re-score of stored rung-1 JSONLs against the fixed (line-scoped)
manifest_srv_a/b_current_mode checks — closes the 06-10 ~47% false-fail artifact
without re-running models.

The checker ran live against the target, so the manifest text isn't stored as a
check detail. Recovery, in order: (1) stdout of the LAST command that read
/srv/manifest.txt (cat/head/tail/less/more); (2) the LAST write command
(printf/echo/heredoc redirect into manifest.txt), replayed through bash in a
throwaway container-free way is overkill — we just regex-extract printf/echo
payloads. Unrecoverable runs are reported as such, never guessed.

Usage (inside lb-sandbox-harness): python sandbox/rescore_rung1_manifest.py
Output: per-run old→new for the two manifest checks + corrected depth; summary
table per file. Read-only — does NOT rewrite the JSONLs.

VERDICT (2026-06-11, the one run of this): offline recovery is NOT trustworthy.
Zero rung-1 runs read the manifest back (no `cat` stdout to recover), and
write-extract produced NEGATIVE deltas — impossible for a fix that only rescues
false-fails, so the extraction (printf format-vs-args, command substitution,
multi-arg quoting) reconstructs wrong text. The 06-10 scores stand with the
documented arm-symmetric artifact caveat (plan 08 §B); the post-fix 120b column
is the clean data. Kept as the reproducible record of the attempt.
"""
from __future__ import annotations

import glob
import json
import re


def home_line_ok(man: str, home: str, mode_re: str, stale_re: str | None = None) -> bool:
    # Mirrors rung1.py (2026-06-11 line-scoped fix) — keep in sync.
    for ln in man.splitlines():
        if not re.search(re.escape(home) + r"(?![\w/])", ln):
            continue
        if not re.search(mode_re, ln):
            continue
        if stale_re and re.search(stale_re, ln):
            continue
        return True
    return False


def recover_manifest(turns: list[dict]) -> tuple[str | None, str]:
    man, how = None, "unrecoverable"
    for t in turns:
        cmd = (t.get("cmd") or "").strip()
        out = t.get("stdout") or ""
        if not cmd or "manifest.txt" not in cmd:
            continue
        # 1 — a read of the file wins (it's the file's true content at that point)
        if re.match(r"(cat|head|tail|less|more)\b", cmd) and ">" not in cmd and out.strip():
            man, how = out, "read-back"
            continue
        # 2 — a write: extract printf/echo payload (best-effort)
        m = re.search(r"(?:printf|echo(?:\s+-e)?)\s+(['\"])(.*?)\1\s*>{1,2}\s*\S*manifest\.txt", cmd, re.S)
        if m:
            payload = m.group(2)
            payload = payload.replace("\\n", "\n").replace("\\t", "\t")
            man, how = payload, "write-extract"
        # heredoc write
        m = re.search(r"<<-?\s*['\"]?(\w+)['\"]?(.*?)\n\1", cmd, re.S)
        if m and re.search(r">{1,2}\s*\S*manifest\.txt", cmd):
            man, how = m.group(2), "heredoc-extract"
    return man, how


def main() -> None:
    files = sorted(glob.glob("/results/rung1*-*.jsonl"))
    for path in files:
        rows = []
        for line in open(path):
            r = json.loads(line)
            if r.get("error") or not r.get("checks"):
                continue
            checks = {c["name"]: c["ok"] for c in r["checks"]}
            man, how = recover_manifest(r.get("turns_log", []))
            if man is None:
                rows.append((r["arm"], r["seed"], r["checks_passed"], None, how, None))
                continue
            new_a = home_line_ok(man, "/srv/a", r"\b0?750\b", r"\b2750\b")
            new_b = home_line_ok(man, "/srv/b", r"\b0?700\b")
            delta = (int(new_a) - int(checks.get("manifest_srv_a_current_mode", False))
                     + int(new_b) - int(checks.get("manifest_srv_b_current_mode", False)))
            rows.append((r["arm"], r["seed"], r["checks_passed"],
                         r["checks_passed"] + delta, how, delta))
        if not rows:
            continue
        print(f"\n{path}")
        for arm, seed, old, new, how, delta in rows:
            tag = f"{old}->{new} ({'+' if delta and delta > 0 else ''}{delta})" if new is not None else f"{old} [{how}]"
            print(f"  {arm:<13} seed={seed}  {tag}  via {how}")


if __name__ == "__main__":
    main()
