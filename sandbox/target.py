"""Target container lifecycle — the hermetic shell the model drives.

Every run gets a fresh `docker run -d --rm --network none lb-target` so state is
clean and a destructive command (`rm -rf /`) only wrecks the throwaway writable
layer. The harness talks to the target ONLY through the host Docker socket
(exec / diff); the model never sees the socket — it just issues commands that we
forward into the target via `docker exec`. Command strings are passed as a single
argv element (list form), so a model command is interpreted by the *target's*
bash, never by a host shell.
"""
from __future__ import annotations

import subprocess
import uuid

DOCKER = "docker"


class Target:
    # Resource caps. The model has root in here and we never pre-block destructive
    # commands, so we cap the host-shared resources a `--network none` container can
    # still abuse: PIDs (fork-bomb), memory (blowout), CPU. Escape to the host still
    # needs a kernel/runc 0-day — the knowingly-accepted residual of a shared kernel.
    PIDS_LIMIT = 512
    MEMORY = "2g"
    CPUS = "2"
    # Disk: `--storage-opt size=` is silently NOT enforced on some Docker storage
    # drivers (btrfs without qgroups — verified: a 3g write succeeded). So we
    # enforce a real PER-FILE cap via `ulimit -f` in exec() instead (verified: caps at
    # 1.5g, SIGXFSZ). RESIDUAL: a multi-file write loop in one run is not hard-capped —
    # bounded only by EXEC_TIMEOUT per command + per-run `--rm` reset + Grafana cache-pool
    # monitoring. True total cap = btrfs qgroups / xfs-pquota / the microVM path (later).
    FSIZE_KB = 1_572_864   # 1.5 GiB per file (bash ulimit -f is in 1024-byte blocks)

    def __init__(self, image: str = "lb-target:latest"):
        self.image = image
        self.name = f"lbtgt-{uuid.uuid4().hex[:12]}"
        self._started = False

    def start(self) -> None:
        subprocess.run(
            [DOCKER, "run", "-d", "--rm", "--network", "none",
             "--pids-limit", str(self.PIDS_LIMIT),
             "--memory", self.MEMORY, "--cpus", self.CPUS,
             "--name", self.name, self.image, "sleep", "infinity"],
            check=True, capture_output=True, text=True,
        )
        self._started = True

    def exec(self, cmd: str, timeout: int = 30) -> tuple[int, str, str]:
        """Run `cmd` in the target's bash. Returns (exit_code, stdout, stderr).
        A timeout returns code 124 (the model's command can hang; the container
        is ephemeral so we don't bother killing the inner process). The `ulimit -f`
        prefix enforces the per-file disk cap (docker exec does NOT inherit the run-time
        --ulimit, so we set it here where it actually applies to the model's command)."""
        wrapped = f"ulimit -f {self.FSIZE_KB} 2>/dev/null; {cmd}"
        try:
            p = subprocess.run(
                [DOCKER, "exec", self.name, "bash", "-c", wrapped],
                capture_output=True, text=True, timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
            return p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"[timeout after {timeout}s]"

    def diff(self) -> list[tuple[str, str]]:
        """`docker diff` — (kind, path) for every change vs the immutable image.
        kind is A(dded) / C(hanged) / D(eleted). This is the collateral primitive."""
        p = subprocess.run([DOCKER, "diff", self.name], capture_output=True, text=True)
        out: list[tuple[str, str]] = []
        for line in p.stdout.splitlines():
            line = line.rstrip()
            if not line:
                continue
            kind, _, path = line.partition(" ")
            out.append((kind, path))
        return out

    def stop(self) -> None:
        if self._started:
            subprocess.run([DOCKER, "rm", "-f", self.name], capture_output=True, text=True)
            self._started = False

    def __enter__(self) -> "Target":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
