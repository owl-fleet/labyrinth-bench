"""Rung 2 — the control-stress thesis test (~35 interlocking steps).

rung-1 was too short: control (accumulating transcript) never overflowed 16k, so it
won by memory and managed-note merely tied it. rung-2 scales to a 4-service fleet with
cross-service ownership rotation, mid-chain mutations (incl. the setgid-drop), a group
revocation, an 8-symlink registry, and three "report CURRENT state" manifests. The point:
make control's transcript BLOAT (many verbose `ls -laR`/`stat` reads accumulate) and force
long-range recall + post-mutation current-state, so the accumulating arm drifts/overflows
while managed-note reasons over a clean wiped context + notes + authoritative state.

Spec is data-driven (SERVICES) so the briefing and checker can't drift apart. Validated by
sandbox/selftest.py (canonical solution must score 100%).
"""
from __future__ import annotations

import re

from sandbox.checker import Check, Rung
from sandbox.target import Target

_VERSION = "2.7.0"  # /vendor/app.tar.gz → app/version.txt

# key, home,    user,    init_mode, final_mode, conf_owner (rotation)
SERVICES = [
    ("a", "/srv/a", "svc_a", "2750", "750", "svc_b"),
    ("b", "/srv/b", "svc_b", "0750", "700", "svc_c"),
    ("c", "/srv/c", "svc_c", "2750", "700", "svc_d"),
    ("d", "/srv/d", "svc_d", "0750", "750", "svc_a"),
]
_OPS_INIT = {"svc_c", "svc_d"}   # added to ops
_OPS_FINAL = {"svc_c"}           # svc_d revoked
_CONF_SETGID_REPAIR = {"a", "c"}  # confs whose group-inheritance the mutation broke


def generate(seed: int | None = None) -> Rung:
    briefing = f"""TASK (rung-2 — multi-service fleet). Build this EXACTLY. No network; you are root.

GROUPS: create group 'deploy' and group 'ops'.

USERS (all four, each with the given home, each in group 'deploy'):
  - svc_a home /srv/a
  - svc_b home /srv/b
  - svc_c home /srv/c   (ALSO add to group 'ops')
  - svc_d home /srv/d   (ALSO add to group 'ops')

PER SERVICE (for each of svc_a..svc_d, in its home /srv/<x>):
  - Extract /vendor/app.tar.gz so /srv/<x>/app exists; make /srv/<x>/app owned by svc_<x>:deploy.
  - Read /srv/<x>/app/version.txt and write its exact contents into /srv/<x>/app/RELEASE.

CROSS-SERVICE CONFIG OWNERSHIP (rotate; each group 'deploy' and group-readable):
  - /srv/a/app/conf/app.conf owned by user svc_b
  - /srv/b/app/conf/app.conf owned by user svc_c
  - /srv/c/app/conf/app.conf owned by user svc_d
  - /srv/d/app/conf/app.conf owned by user svc_a

HOME MODES: /srv/a=2750, /srv/b=0750, /srv/c=2750, /srv/d=0750.

MUTATIONS (apply AFTER everything above — these change current state):
  - /srv/a -> mode 0750 with setgid OFF (exactly 0750, not 2750).
  - /srv/c -> mode 0700 with setgid OFF (exactly 0700).
  - /srv/b -> mode 0700.
  - Remove user svc_d from group 'ops' (svc_d stays in 'deploy').

REPAIRS (the mutations broke group inheritance):
  - Set /srv/a/app/conf and /srv/c/app/conf to setgid (2750) with group 'deploy'.

REGISTRY: create /srv/registry (group 'deploy', group-traversable: group execute), containing symlinks:
  - /srv/registry/<x>-app -> /srv/<x>/app           (for x in a,b,c,d)
  - /srv/registry/<x>-rel -> /srv/<x>/app/RELEASE    (for x in a,b,c,d)

REPORTS (report the CURRENT state, after all mutations):
  - /srv/manifest.txt    : one line per service: "<home> <owner> <current-mode>"  e.g.  /srv/a svc_a 750
  - /srv/conf_owners.txt : one line per service: "/srv/<x>/app/conf/app.conf <current-owner>"
  - /srv/ops_members.txt : the current members of group 'ops'

Declare done when everything is in place."""

    def setup(t: Target) -> None:
        pass

    def check(t: Target) -> list[Check]:
        out: list[Check] = []

        def stat(path: str, fmt: str) -> str:
            return t.exec(f"stat -c '{fmt}' {path} 2>/dev/null")[1].strip()

        # groups
        out.append(Check("group_deploy", t.exec("getent group deploy")[0] == 0))
        out.append(Check("group_ops", t.exec("getent group ops")[0] == 0))

        # users / homes / deploy membership / ops membership
        for k, home, user, _im, _fm, _co in SERVICES:
            rc, pw, _ = t.exec(f"getent passwd {user}")
            out.append(Check(f"user_{user}", rc == 0, pw.strip()))
            out.append(Check(f"{user}_home", rc == 0 and pw.strip().split(":")[5] == home))
            grps = set(t.exec(f"id -nG {user} 2>/dev/null")[1].split())
            out.append(Check(f"{user}_in_deploy", "deploy" in grps, " ".join(sorted(grps))))
            in_ops = "ops" in grps
            out.append(Check(f"{user}_ops_correct", in_ops == (user in _OPS_FINAL),
                             f"in_ops={in_ops} want={user in _OPS_FINAL}"))

        # per-service: app extracted + owned, RELEASE, conf owner+group+readable, final home mode
        for k, home, user, _im, final_mode, conf_owner in SERVICES:
            app = f"{home}/app"
            out.append(Check(f"{k}_app_extracted",
                             t.exec(f"test -f {app}/version.txt")[0] == 0))
            out.append(Check(f"{k}_app_owner", stat(app, "%U:%G") == f"{user}:deploy", stat(app, "%U:%G")))
            rel = t.exec(f"cat {app}/RELEASE 2>/dev/null")
            out.append(Check(f"{k}_release", rel[0] == 0 and rel[1].strip() == _VERSION, rel[1].strip()))
            conf = f"{app}/conf/app.conf"
            og = stat(conf, "%U:%G")
            perm = stat(conf, "%A")
            gr = len(perm) >= 6 and perm[4] == "r"
            out.append(Check(f"{k}_conf_owner", og == f"{conf_owner}:deploy", og))
            out.append(Check(f"{k}_conf_group_readable", gr, perm))
            out.append(Check(f"{k}_home_mode_{final_mode}", stat(home, "%a") == final_mode, stat(home, "%a")))

        # conf setgid repairs
        for k in sorted(_CONF_SETGID_REPAIR):
            conf_dir = f"/srv/{k}/app/conf"
            mode = stat(conf_dir, "%a")
            grp = stat(conf_dir, "%G")
            setgid = len(mode) == 4 and (int(mode[0]) & 2)
            out.append(Check(f"{k}_conf_setgid_deploy", bool(setgid) and grp == "deploy", f"{mode} {grp}"))

        # registry: dir group-traversable by deploy + the 8 symlinks
        rperm = stat("/srv/registry", "%A")
        rgrp = stat("/srv/registry", "%G")
        rgx = len(rperm) >= 7 and rperm[6] in ("x", "s")
        out.append(Check("registry_group_deploy_traversable", rgx and rgrp == "deploy", f"{rperm} {rgrp}"))

        def symlink_to(link: str, want: str) -> bool:
            if t.exec(f"test -L {link}")[0] != 0:
                return False
            return t.exec(f"readlink -f {link}")[1].strip() == want

        for k, home, *_ in SERVICES:
            out.append(Check(f"registry_{k}_app",
                             symlink_to(f"/srv/registry/{k}-app", f"{home}/app")))
            out.append(Check(f"registry_{k}_rel",
                             symlink_to(f"/srv/registry/{k}-rel", f"{home}/app/RELEASE")))

        # reports
        manifest = t.exec("cat /srv/manifest.txt 2>/dev/null")[1]
        conf_owners = t.exec("cat /srv/conf_owners.txt 2>/dev/null")[1]
        ops_members = t.exec("cat /srv/ops_members.txt 2>/dev/null")[1]
        out.append(Check("manifest_exists", bool(manifest.strip())))
        for k, home, user, _im, _fm, conf_owner in SERVICES:
            cur = stat(home, "%a")
            mline = next((l for l in manifest.splitlines() if home in l.split()), "")
            mode_ok = bool(re.search(rf"(?<!\d){cur}(?!\d)", mline)) or bool(re.search(rf"\b0{cur}\b", mline))
            out.append(Check(f"manifest_{k}", bool(mline) and user in mline and mode_ok,
                             f"cur={cur} line={mline!r}"))
            cline = next((l for l in conf_owners.splitlines() if f"/srv/{k}/app/conf" in l), "")
            out.append(Check(f"conf_owners_{k}", conf_owner in cline, cline))
        out.append(Check("ops_members_svc_c", "svc_c" in ops_members, ops_members.strip()))
        out.append(Check("ops_members_not_svc_d", "svc_d" not in ops_members, ops_members.strip()))

        return out

    def unreachable(t: Target) -> bool:
        return (t.exec("test -f /vendor/app.tar.gz")[0] != 0
                or t.exec("getent passwd root")[0] != 0)

    return Rung(
        rung_id="rung2",
        briefing=briefing,
        state_roots=["/srv"],
        footprint=["/srv"],
        optimal_commits=35,
        setup=setup,
        check=check,
        unreachable=unreachable,
        seed_params={"version": _VERSION, "services": [s[0] for s in SERVICES]},
    )
