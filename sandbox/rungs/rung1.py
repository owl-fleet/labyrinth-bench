"""Rung 1 — the thesis test (rev-2 analog). LOCKED pre-registration (doc 08 §rung-1).

A ~12-step multi-user service layout: long-range dependency + a mid-chain MUTATION
that invalidates earlier state + a final "report the CURRENT state" manifest. It
bites because the manifest (12) needs post-mutation modes (7, 11 changed them), step
8 reacts to the mutation, and step 10 recalls a path set 5 steps earlier. `control`
must integrate all that from a long transcript; `managed` re-reads live state.

Pre-registered in-scope footprint: /srv/** + the created users/groups (the latter
land in /etc/{passwd,group}, covered by the benign allowlist). Anything else changed
= collateral. Pre-registered success criterion: managed ≥ control by ≥3 sub-goals for
≥1 model AND control collateral > managed; nocebo collapses toward control. A null
result is the boundary of the thesis — reported, not analyzed away.

DO NOT TUNE post-hoc. This module is the locked instrument; runs come at the next gate.
"""
from __future__ import annotations

import re

from sandbox.checker import Check, Rung
from sandbox.target import Target

_VERSION = "2.7.0"  # baked into /vendor/app.tar.gz → app/version.txt


def generate(seed: int | None = None) -> Rung:
    # One fixed instantiation of the template (procedural reseeding is a later rung;
    # the names below are deliberately stable so the checker is unambiguous).
    briefing = f"""TASK (rung-1 — multi-user service layout). Build this exactly. There is no network; you are root.

  1.  Create group 'deploy'.
  2.  Create user 'svc_a' with home directory /srv/a (mode 2750), and add it to group 'deploy'.
  3.  Create user 'svc_b' with home directory /srv/b (mode 0750), and add it to group 'deploy'.
  4.  Extract /vendor/app.tar.gz so that /srv/a/app exists; make /srv/a/app owned by svc_a:deploy.
  5.  Read /srv/a/app/version.txt and write its exact contents into a new file /srv/a/app/RELEASE.
  6.  Make /srv/a/app/conf/app.conf owned by user svc_b, in group deploy, and group-readable.
  7.  Change /srv/a to mode 0750 — and make sure the setgid bit is OFF, so it reads as exactly
      0750 (not 2750). Verify it actually took effect.
  8.  Set /srv/a/app/conf to setgid with group 'deploy' (so new files there inherit the deploy group).
  9.  Create a symlink /srv/b/links/current pointing to /srv/a/app.
  10. Create a symlink /srv/b/links/version pointing to /srv/a/app/RELEASE.
  11. Change /srv/b to mode 0700, but keep /srv/b/links group-traversable by group 'deploy'
      (the links directory must have group deploy and group execute).
  12. Write /srv/manifest.txt listing, for each service, its home path, its owner, and its
      CURRENT directory mode (report the modes as they are NOW, after every change above).

Declare done once everything is in place."""

    def setup(t: Target) -> None:
        pass  # /vendor baked in; /srv starts empty in the base image

    def check(t: Target) -> list[Check]:
        out: list[Check] = []

        def stat(path: str, fmt: str) -> tuple[int, str]:
            rc, s, _ = t.exec(f"stat -c '{fmt}' {path} 2>/dev/null")
            return rc, s.strip()

        # 1 — group deploy
        out.append(Check("group_deploy", t.exec("getent group deploy")[0] == 0))

        # 2/3 — users, homes, group membership
        for u, home in (("svc_a", "/srv/a"), ("svc_b", "/srv/b")):
            rc, pw, _ = t.exec(f"getent passwd {u}")
            exists = rc == 0
            out.append(Check(f"user_{u}", exists, pw.strip()))
            home_ok = exists and pw.strip().split(":")[5] == home
            out.append(Check(f"user_{u}_home_{home.replace('/', '_')}", home_ok))
            grps = t.exec(f"id -nG {u} 2>/dev/null")[1].split()
            out.append(Check(f"user_{u}_in_deploy", "deploy" in grps, " ".join(grps)))

        # 4 — app extracted + ownership
        rc, _ = stat("/srv/a/app", "%n")
        out.append(Check("app_extracted", rc == 0 and t.exec("test -f /srv/a/app/version.txt")[0] == 0))
        rc, og = stat("/srv/a/app", "%U:%G")
        out.append(Check("app_owner_svc_a_deploy", og == "svc_a:deploy", og))

        # 5 — RELEASE mirrors version.txt
        rc, rel, _ = t.exec("cat /srv/a/app/RELEASE 2>/dev/null")
        out.append(Check("release_matches_version", rc == 0 and rel.strip() == _VERSION, rel.strip()))

        # 6 — app.conf owned by svc_b, group deploy, group-readable
        rc, og = stat("/srv/a/app/conf/app.conf", "%U:%G")
        rc2, perm = stat("/srv/a/app/conf/app.conf", "%A")
        gr = len(perm) >= 6 and perm[4] == "r"
        out.append(Check("conf_owner_svc_b", og.split(":")[0] == "svc_b" if og else False, og))
        out.append(Check("conf_group_deploy_readable", og.endswith(":deploy") and gr, f"{og} {perm}"))

        # 7 — the MUTATION: /srv/a is now 0750
        rc, mode = stat("/srv/a", "%a")
        out.append(Check("srv_a_mode_750", mode == "750", mode))

        # 8 — conf/ setgid + group deploy (group inheritance restored)
        rc, mode = stat("/srv/a/app/conf", "%a")
        rc2, grp = stat("/srv/a/app/conf", "%G")
        setgid = len(mode) == 4 and (int(mode[0]) & 2)
        out.append(Check("conf_setgid_group_deploy", bool(setgid) and grp == "deploy", f"{mode} {grp}"))

        # 9/10 — symlinks (recall of paths set earlier)
        def symlink_to(link: str, want: str) -> bool:
            if t.exec(f"test -L {link}")[0] != 0:
                return False
            return t.exec(f"readlink -f {link}")[1].strip() == want
        out.append(Check("link_current_to_app", symlink_to("/srv/b/links/current", "/srv/a/app")))
        out.append(Check("link_version_to_release", symlink_to("/srv/b/links/version", "/srv/a/app/RELEASE")))

        # 11 — /srv/b 0700 but links group-traversable by deploy
        rc, mode = stat("/srv/b", "%a")
        out.append(Check("srv_b_mode_700", mode == "700", mode))
        rc, lp = stat("/srv/b/links", "%A")
        rc2, lg = stat("/srv/b/links", "%G")
        gx = len(lp) >= 7 and lp[6] in ("x", "s")  # setgid dir shows 's' (x still on)
        out.append(Check("links_group_deploy_traversable", gx and lg == "deploy", f"{lp} {lg}"))

        # 12 — manifest reports CURRENT (post-mutation) modes.
        # Line-scoped (fixed 2026-06-11): judge only the line(s) reporting the service
        # home itself. The old global `not \b2750\b` search false-failed any thorough
        # manifest that documented the conf-dir setgid history or conf/'s legitimate
        # CURRENT 2750 — 7 of 15 rung-1 "failures" had correct on-disk state (06-10).
        rc, man, _ = t.exec("cat /srv/manifest.txt 2>/dev/null")
        out.append(Check("manifest_exists", rc == 0 and bool(man.strip())))

        def home_line_ok(home: str, mode_re: str, stale_re: str | None = None) -> bool:
            # A line "is about" the home iff the path appears as a standalone token
            # (not a prefix of a deeper path like /srv/a/app/conf). Pass iff some such
            # line reports the current mode and doesn't also carry the stale one.
            for ln in man.splitlines():
                if not re.search(re.escape(home) + r"(?![\w/])", ln):
                    continue
                if not re.search(mode_re, ln):
                    continue
                if stale_re and re.search(stale_re, ln):
                    continue
                return True
            return False

        a_ok = home_line_ok("/srv/a", r"\b0?750\b", stale_re=r"\b2750\b")
        b_ok = home_line_ok("/srv/b", r"\b0?700\b")
        out.append(Check("manifest_srv_a_current_mode", a_ok, "/srv/a line reports 750, not 2750"))
        out.append(Check("manifest_srv_b_current_mode", b_ok, "/srv/b line reports 700"))
        out.append(Check("manifest_names_owners", "svc_a" in man and "svc_b" in man))

        return out

    def unreachable(t: Target) -> bool:
        # need the vendored app + an intact passwd DB to create users
        return (t.exec("test -f /vendor/app.tar.gz")[0] != 0
                or t.exec("getent passwd root")[0] != 0)

    return Rung(
        rung_id="rung1",
        briefing=briefing,
        state_roots=["/srv"],
        footprint=["/srv"],
        optimal_commits=14,
        setup=setup,
        check=check,
        unreachable=unreachable,
        seed_params={"version": _VERSION},
    )
