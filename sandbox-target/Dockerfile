# lb-target — the hermetic sysadmin sandbox the model drives through a shell.
#
# Built ONCE (network only at build time). At RUN time the harness launches it
# `docker run -d --rm --network none ...` so it is offline + ephemeral: a fresh
# clean filesystem per run, and a model `rm -rf /` only destroys the throwaway
# writable layer. Vendored artifacts (tool.tar.gz / app.tar.gz) are baked in so
# tasks need no apt/pip at run time.
FROM debian:bookworm-slim

# Fail-fast: the rung tasks need exactly these tools. If the base image ever
# drops one, the build breaks here instead of silently failing mid-eval.
RUN set -eux; for c in useradd groupadd getent stat tar chown chmod chgrp ln cat bash; do \
      command -v "$c" >/dev/null || { echo "MISSING TOOL: $c"; exit 1; }; \
    done

# A baseline non-root user for rung-0 (the 2-3 step harness-validation task).
RUN useradd -m -s /bin/bash appuser

# Vendored artifacts: committed as plain source, tarred at build time into /vendor.
# (Tarring locally at build time is fine — the offline guarantee is about RUN time.)
COPY artifacts-src/ /artifacts-src/
RUN set -eux; \
    mkdir -p /vendor; \
    chmod +x /artifacts-src/tool/bin/tool; \
    tar -C /artifacts-src/tool -czf /vendor/tool.tar.gz bin; \
    tar -C /artifacts-src      -czf /vendor/app.tar.gz  app; \
    rm -rf /artifacts-src

CMD ["sleep", "infinity"]
