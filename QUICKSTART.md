# LabyrinthBench — Quickstart

Get a local model running the maze and watch it live in your browser. No git, no Python setup — you need Docker and a model server you already use.

## What you need

1. **Docker Desktop** — [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop). Install it, start it, leave it running.
2. **A local model server.** These steps use **LM Studio**; Ollama differences are at the bottom.
3. **This repo as a ZIP** — green **Code** button on the GitHub page → **Download ZIP** → extract it somewhere you can find (e.g. `Documents\labyrinth-bench`).

## Step 1 — start your model server

In LM Studio:

1. Load the model you want to test (something in the 7B–14B range is a good first run).
2. Open the **Developer** tab and start the server. Note the port — default is **1234**.
3. Note the **model identifier** LM Studio shows for the loaded model (e.g. `qwen3-14b-instruct`) — you'll pass it on the command line.

## Step 2 — start LabyrinthBench

Open a terminal (PowerShell is fine) in the extracted folder and run:

```sh
docker compose -f docker-compose.standalone.yml up -d
```

First run takes a few minutes while the image builds. When it returns, LabyrinthBench is up.

## Step 3 — run the maze

```sh
docker compose -f docker-compose.standalone.yml exec labyrinth-bench python cli/run_eval.py --model <your-model-id> --base-url http://host.docker.internal:1234/v1
```

Replace `<your-model-id>` with the identifier from Step 1. If it's a Qwen3-family "thinking" model (e.g. `qwen3-14b`), add `--no-think` for comparable runs. The terminal prints progress as the model plays.

## Step 4 — watch

Open **<http://localhost:8090/watch>** in your browser and click the newest session. You're watching the model navigate turn by turn: what it observed, what it answered, how deep it got.

A run ends when the model reaches the exit, runs out of wrong-answer budget, or stalls. Depth reached is the score. Run it again — same command — and see if it's consistent.

## If something breaks

- **`connection refused` / a run that immediately records DNF with barely any steps** — the model server isn't reachable from Docker (a failed connection scores as a DNF row rather than crashing). Most common cause: **the server is listening on localhost only, which containers can't reach.** In LM Studio, enable **Serve on Local Network** in the server settings (headless CLI installs: set `"networkInterface": "0.0.0.0"` in `~/.lmstudio/.internal/http-server-config.json`, then `lms server stop && lms server start`). For Ollama: `OLLAMA_HOST=0.0.0.0`. Also check the port in `--base-url` matches the server.
- **`host.docker.internal` not found** (mostly Linux) — replace it with your machine's LAN IP, e.g. `http://192.168.1.50:1234/v1`.
- **You hit Ctrl-C but a session is still running** — the run continues server-side and a lock blocks new runs until it finishes; watch it wind down at `localhost:8090/watch` or wait it out. It still scores at the depth it reached.
- **Nothing at localhost:8090** — `docker compose -f docker-compose.standalone.yml ps` should show the container up; if not, re-run Step 2 and read the error.
- **The model answers gibberish or instantly fails** — some models need a bigger context window than the server default; raise it in LM Studio's model settings (8k+ recommended).

Write down anything that confused you, in the order it happened — that list is exactly what this test is for.

## Ollama instead of LM Studio

Ollama serves on port **11434** and uses its own model tags:

```sh
docker compose -f docker-compose.standalone.yml exec labyrinth-bench python cli/run_eval.py --model qwen3:14b --base-url http://host.docker.internal:11434/v1
```

Qwen3-family "thinking" models: add `--no-think` for comparable runs.
