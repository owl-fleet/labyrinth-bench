"""The curator — the `managed` arm's truth channel.

Each turn it re-reads the FULL live state of the work area (general system
inspection: `ls -laR` of the rung's state roots + non-system users/groups) and
hands the model an authoritative snapshot. This is the rev-2 overlay-only
generalization applied to a real OS: full-state-first, NOT task-specific curation
(scoped/selective curation, which reintroduces relevance-judgment, is a later rung).

`corrupt_state` is the NOCEBO: it perturbs the snapshot (perms/owners altered)
while the engine still scores against the TRUE state. If `managed` survives a
wrong read, the model isn't depending on the ledger → the result is an artifact.
"""
from __future__ import annotations

import re
import shlex

from sandbox.target import Target


def read_state(target: Target, state_roots: list[str]) -> str:
    parts = ["[SYSTEM STATE]  (re-read live this turn — authoritative; trust this over memory)"]
    for root in state_roots:
        rc, out, _ = target.exec(f"ls -laR {shlex.quote(root)} 2>/dev/null")
        body = out.strip() if rc == 0 and out.strip() else "(absent)"
        parts.append(f"\n# {root}  (ls -laR)\n{body}")
    rc, out, _ = target.exec(
        "getent passwd | awk -F: '$3>=1000 && $3<65534 {print $1\":\"$3\" home=\"$6}'")
    parts.append(f"\n# users (uid>=1000)  name:uid home=...\n{out.strip() or '(none)'}")
    rc, out, _ = target.exec(
        "getent group | awk -F: '$3>=1000 && $3<65534 {print $1\":\"$3\" members=\"$4}'")
    parts.append(f"\n# groups (gid>=1000)  name:gid members=...\n{out.strip() or '(none)'}")
    return "\n".join(parts)


# ls long-format line: type, 9 perm chars, links, owner, group, rest…
_LS_RE = re.compile(r"^([-dlbcps])([rwxXsStT-]{9})(\s+\d+\s+)(\S+)(\s+)(\S+)(\s+.*)$")


def corrupt_state(text: str) -> str:
    """NOCEBO: toggle the group-read bit and swap owner/group on every ls line —
    plausible but wrong (breaks both perms and ownership), so the model can't
    trivially detect-and-compensate. Leaves headers/getent intact enough to look real."""
    def fix(line: str) -> str:
        m = _LS_RE.match(line)
        if not m:
            return line
        typ, perm, mid, owner, sp, group, rest = m.groups()
        pl = list(perm)
        pl[3] = "-" if pl[3] == "r" else "r"  # toggle group-read
        if owner != group:
            owner, group = group, owner          # swap ownership
        return f"{typ}{''.join(pl)}{mid}{owner}{sp}{group}{rest}"
    return "\n".join(fix(l) for l in text.splitlines())
