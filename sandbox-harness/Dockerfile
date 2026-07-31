# lb-sandbox-harness — the TRUSTED driver for the external-validation sandbox.
#
# This is the only container that touches the host Docker socket. It uses it
# solely to spawn / exec / `docker diff` ephemeral `--network none` lb-target
# containers (see sandbox/target.py). The MODEL never reaches this socket — it
# only ever runs commands *inside* a target via `docker exec`. Kept separate
# from the maze API container so the privileged socket
# is not co-located with a network-exposed service.
FROM python:3.12-slim

# docker CLI only (talks to the mounted host socket; no daemon here).
COPY --from=docker:cli /usr/local/bin/docker /usr/local/bin/docker

RUN pip install --no-cache-dir httpx

WORKDIR /app
CMD ["sleep", "infinity"]
