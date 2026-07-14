-- LabyrinthBench TimescaleDB schema
-- Run once against the existing timescaledb instance (ai stack)
-- Pattern mirrors thunderdome_results; one run row per session.

CREATE TABLE IF NOT EXISTS labyrinth_runs (
    ts               TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    session_id       UUID            NOT NULL,
    model            TEXT            NOT NULL,
    deg_id           TEXT            NOT NULL,
    found_exit       BOOLEAN         NOT NULL,
    steps_to_exit    INT,                      -- NULL if DNF
    step_budget      INT             NOT NULL,
    optimal_commits  INT             NOT NULL,
    normalized_efficiency FLOAT,              -- optimal / actual; NULL if DNF
    gate_accuracy    FLOAT,                   -- NULL if no gates encountered
    path_correctness FLOAT,
    recovery_rate    FLOAT,
    chain_gate_count INT,                     -- dependent (chain) gates declared in this DEG
    chain_accuracy   FLOAT,                   -- first-attempt correctness on ATTEMPTED chain gates
    knowledge_state_consistency FLOAT,        -- chain answers derivable from model's OWN prior answer (did it execute the program?)
    note_used        BOOLEAN         NOT NULL DEFAULT FALSE,
    elapsed_seconds  FLOAT,
    turns            INT,                     -- total model turns (including observe/inspect)
    run_label        TEXT,                    -- e.g. "baseline-20260520"
    representation   TEXT            NOT NULL DEFAULT 'abstract'
);

SELECT create_hypertable('labyrinth_runs', 'ts', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS lb_model_deg_ts  ON labyrinth_runs (model, deg_id, ts DESC);
CREATE INDEX IF NOT EXISTS lb_session       ON labyrinth_runs (session_id);
CREATE INDEX IF NOT EXISTS lb_label_ts      ON labyrinth_runs (run_label, ts DESC);

-- Phase 1 re-instrumentation (2026-06-02): chain-reasoning metrics. Additive + idempotent,
-- safe to re-run against an existing labyrinth_runs table.
ALTER TABLE labyrinth_runs ADD COLUMN IF NOT EXISTS chain_gate_count INT;
ALTER TABLE labyrinth_runs ADD COLUMN IF NOT EXISTS chain_accuracy FLOAT;
ALTER TABLE labyrinth_runs ADD COLUMN IF NOT EXISTS knowledge_state_consistency FLOAT;
