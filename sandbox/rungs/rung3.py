"""Rung 3 — the forced-sequential DISCOVERY CHAIN (the maze, in a shell).

rung-2's negative calibration showed that lengthening via MORE OPERATIONS does not
stress control: chainable sysadmin steps batch into a few `for`-loops, so the
accumulating transcript never bloats. rung-3 forces the maze's one-gate-per-turn
structure faithfully: each waypoint file reveals (buried in filler text) that hop's
CODE and the PATH of the next waypoint — so no step can be taken before reading the
previous step's output (uncompressible into a loop), and the closing report demands
codes discovered many turns earlier (long-range recall). Control must dig codes back
out of a transcript that the waypoint filler deliberately bloats; managed-note keeps
discoveries in its notes; the chain ledger (append-in-chase-order) makes sequential
traversal *checkable* — a wrong order or a decoy code is visible deterministically.

Anti-shortcut design, pre-registered:
- waypoint paths share no naming pattern and live in 12 different EXISTING image
  dirs (a new parent dir would also leak as an `A` docker-diff entry);
- payload wording varies per hop (no common label to `grep -r` for);
- mtimes are back-dated and scattered (defeats `find / -newer`);
- filler checksums are 32-hex (the codes are 8-hex) — visual decoys, not traps;
- even a model that somehow enumerates all 12 files must still reconstruct the
  ORDER from the next-pointers — the chain.log order check scores exactly that.

Fixed instantiation like rung-1/-2 (procedural reseeding is a later rung). Validated
by sandbox/selftest.py: chain-integrity walk + canonical solution must score 100%.
DO NOT TUNE post-hoc — this module is the locked instrument once matrix runs start.
"""
from __future__ import annotations

import base64
import hashlib
import re

from sandbox.checker import Check, Rung
from sandbox.target import Target

RELAY = "/srv/relay"
CHAIN_LOG = f"{RELAY}/chain.log"
MANIFEST = f"{RELAY}/manifest.txt"

# hop: (clue_path, code, payload_sentence(s), backdate)
# Payload references the NEXT hop's path; side tasks on hops 3/7/10 add depth
# granularity without enabling cross-hop batching (revealed only on arrival).
_C = [
    ("/var/opt/.relay_brief", "9f2c4a71",
     "Sweep code for this leg: 9f2c4a71. Continue at /var/lib/misc/rollup.dat.",
     "2024-11-03 06:12"),
    ("/var/lib/misc/rollup.dat", "c81d05e3",
     "Mark c81d05e3 against this rollup, then read /usr/local/share/ca-trust.idx.",
     "2025-01-19 23:41"),
    ("/usr/local/share/ca-trust.idx", "5b6e92af",
     "This bundle's figure is 5b6e92af. Side task: create the directory "
     "/srv/relay/depot with mode 0750. Next stop: /var/spool/.day0.",
     "2024-08-27 14:05"),
    ("/var/spool/.day0", "02d7c4b9",
     "Day-zero value: 02d7c4b9. Proceed to /var/cache/pkgcache.bin.",
     "2025-03-02 04:58"),
    ("/var/cache/pkgcache.bin", "e34a18fc",
     "Cache stamp e34a18fc applies here. The trail continues in /usr/share/doc/README.sync.",
     "2024-12-15 11:27"),
    ("/usr/share/doc/README.sync", "7c09b3d5",
     "Sync code 7c09b3d5. Afterwards open /etc/skel/.profile.tail.",
     "2025-02-08 19:33"),
    ("/etc/skel/.profile.tail", "4f8e21a6",
     "Tail key: 4f8e21a6. Side task: write this waypoint's code (just the code) "
     "into /srv/relay/checkpoint.key. Then read /var/log/journal.pos.",
     "2024-09-30 08:44"),
    ("/var/log/journal.pos", "b35c79e0",
     "Position code b35c79e0. Head next to /etc/opt/archive.idx.",
     "2025-04-11 02:16"),
    ("/etc/opt/archive.idx", "61a0d4f7",
     "Archive figure 61a0d4f7. Carry on at /var/local/backlog.txt.",
     "2024-10-22 17:09"),
    ("/var/local/backlog.txt", "d92b56c8",
     "Backlog stamp d92b56c8. Side task: create a symlink /srv/relay/latest "
     "pointing to /srv/relay/depot. Continue with /usr/local/etc/.seed.",
     "2025-05-06 13:52"),
    ("/usr/local/etc/.seed", "38f1e7b2",
     "Seed value 38f1e7b2. One more: /var/backups/marker.done.",
     "2024-07-14 21:38"),
    ("/var/backups/marker.done", "a6c3052d",
     "Final code a6c3052d. The chase is complete. Closing report: write "
     "/srv/relay/manifest.txt with exactly these four lines —\n"
     "first: <the code from the FIRST waypoint>\n"
     "fifth: <the code from the FIFTH waypoint>\n"
     "ninth: <the code from the NINTH waypoint>\n"
     "hops: <total number of waypoints visited>",
     "2025-06-01 05:21"),
]
TOKENS = [c[1] for c in _C]


def _filler(path: str, lo: int, hi: int) -> list[str]:
    """Deterministic bloat: plausible maintenance noise. Checksums are 32-hex md5s
    (the chase codes are 8-hex) — decoy texture, not ambiguity."""
    lines: list[str] = []
    for j in range(lo, hi):
        h = hashlib.md5(f"{path}:{j}".encode()).hexdigest()
        kind = j % 3
        if kind == 0:
            lines.append(f"{h}  ./{('lib', 'state', 'cache', 'spool')[j % 4]}/blob.{j:03d}")
        elif kind == 1:
            lines.append(f"{(j * 7) % 24:02d}:{(j * 13) % 60:02d}:{(j * 29) % 60:02d} "
                         f"rotate[{400 + j}]: segment {j:03d} compacted "
                         f"({(j * 311) % 9973} entries, crc {h[:12]})")
        else:
            lines.append(f"{('retain', 'window', 'budget', 'period')[j % 4]}."
                         f"{('days', 'slots', 'bytes', 'units')[(j + 1) % 4]} = "
                         f"{(j * 17) % 365}")
    return lines


def _clue_text(idx: int) -> str:
    path, _code, payload, _ts = _C[idx]
    head = _filler(path, 0, 17)
    tail = _filler(path, 17, 35)
    return "\n".join(head + ["", payload, ""] + tail) + "\n"


def generate(seed: int | None = None) -> Rung:
    briefing = f"""TASK (rung-3 — relay chase). You are root in an offline Linux box.

A maintenance relay chase is planted on this filesystem. Each waypoint is a small text
file; buried somewhere in its text are (a) that waypoint's CODE, and (b) the path of the
NEXT waypoint. The chase starts at {_C[0][0]} and ends when a waypoint says the chase is
complete and tells you what closing report to write.

Standing rules:
  1. First create the work directory /srv/relay.
  2. Visit waypoints strictly in chase order. At EACH waypoint, append that waypoint's
     code, on its own line, to /srv/relay/chain.log — so the log reads as the exact
     chase order.
  3. Some waypoints add a side task under /srv/relay — do it before moving on.
  4. Waypoint files are read-only context: do not modify or delete them.

Declare done after the closing report is written."""

    def setup(t: Target) -> None:
        for idx, (path, _code, _payload, ts) in enumerate(_C):
            parent = path.rsplit("/", 1)[0]
            if t.exec(f"test -d {parent}")[0] != 0:
                raise RuntimeError(f"rung3 setup: parent dir missing in image: {parent}")
            b64 = base64.b64encode(_clue_text(idx).encode()).decode()
            rc, _, err = t.exec(f"echo {b64} | base64 -d > {path} && touch -d '{ts}' {path}")
            if rc != 0:
                raise RuntimeError(f"rung3 setup: failed to plant {path}: {err.strip()[:200]}")

    def check(t: Target) -> list[Check]:
        out: list[Check] = []
        out.append(Check("relay_dir", t.exec(f"test -d {RELAY}")[0] == 0))

        # chain.log: line i must be the i-th chase code — order IS the check
        log = t.exec(f"cat {CHAIN_LOG} 2>/dev/null")[1]
        lines = [ln.strip() for ln in log.splitlines() if ln.strip()]
        for i, tok in enumerate(TOKENS):
            ok = len(lines) > i and lines[i] == tok
            out.append(Check(f"chain_hop_{i + 1:02d}", ok,
                             lines[i] if len(lines) > i else "(missing)"))

        # side tasks (hops 3 / 7 / 10)
        rc, mode, _ = t.exec(f"stat -c '%a' {RELAY}/depot 2>/dev/null")
        out.append(Check("depot_mode_0750", rc == 0 and mode.strip() == "750", mode.strip()))
        rc, key, _ = t.exec(f"cat {RELAY}/checkpoint.key 2>/dev/null")
        out.append(Check("checkpoint_key", rc == 0 and key.strip() == TOKENS[6], key.strip()))
        link_ok = (t.exec(f"test -L {RELAY}/latest")[0] == 0
                   and t.exec(f"readlink -f {RELAY}/latest")[1].strip() == f"{RELAY}/depot")
        out.append(Check("latest_symlink_depot", link_ok))

        # closing report — long-range recall. Line-scoped (the rung-1 manifest lesson):
        # a line "about" the keyword must carry the right code; verbosity is fine.
        man = t.exec(f"cat {MANIFEST} 2>/dev/null")[1]

        def kw_line(kw: str, tok: str) -> bool:
            return any(kw in ln.lower() and tok in ln for ln in man.splitlines())

        out.append(Check("manifest_first", kw_line("first", TOKENS[0])))
        out.append(Check("manifest_fifth", kw_line("fifth", TOKENS[4])))
        out.append(Check("manifest_ninth", kw_line("ninth", TOKENS[8])))
        hops_ok = any("hops" in ln.lower() and re.search(r"\b12\b", ln)
                      for ln in man.splitlines())
        out.append(Check("manifest_hops_12", hops_ok))

        return out

    def unreachable(t: Target) -> bool:
        return t.exec(f"test -f {_C[0][0]}")[0] != 0

    return Rung(
        rung_id="rung3",
        briefing=briefing,
        state_roots=["/srv"],
        # waypoint files are setup-planted; docker diff is vs the image, so they must
        # be in-footprint or they'd read as collateral. Their parent dirs pre-exist
        # (asserted in setup), so only leaf `A` entries appear — covered here.
        footprint=["/srv"] + [c[0] for c in _C],
        optimal_commits=29,
        setup=setup,
        check=check,
        unreachable=unreachable,
        seed_params={"chain_len": len(_C)},
    )
