-- Precomputed analysis lives here; the API only ever reads it.
--
-- Identity note: customer and agent ids are slugs derived from NAME, not from
-- the dataset's speaker_id. speaker_id is per-recording, not per-person — one
-- customer name appears under 14 different speaker_ids — so keying on it would
-- silently shatter every customer's call history. See pipeline/metadata.py.

CREATE TABLE IF NOT EXISTS customers (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS agents (
    id   TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS calls (
    id                        TEXT PRIMARY KEY,
    customer_id               TEXT NOT NULL REFERENCES customers(id),
    agent_id                  TEXT NOT NULL REFERENCES agents(id),
    started_at                TEXT NOT NULL,           -- ISO 8601 UTC
    duration_seconds          REAL NOT NULL,
    audio_path                TEXT NOT NULL,
    transcript_provider       TEXT NOT NULL,           -- "assemblyai" | "whisper"

    session                   TEXT,                    -- recording batch
    caller_mos                REAL,                    -- audio quality 1-5; low predicts worse WER

    intent_label              TEXT,
    resolution_status         TEXT,                    -- "resolved" | "unresolved" | "partial"
    summary                   TEXT,                    -- <= 40 words
    mood_shift_turn_id        INTEGER,

    attention_score           INTEGER,                 -- 0-100
    attention_factors_json    TEXT,                    -- [{factor, weight, evidence_id?}]

    transcribed_at            TEXT,                    -- transcript stored
    analyzed_at               TEXT                     -- reasoning stored; NULL = needs analysis
);
CREATE INDEX IF NOT EXISTS idx_calls_customer   ON calls(customer_id);
CREATE INDEX IF NOT EXISTS idx_calls_agent      ON calls(agent_id);
CREATE INDEX IF NOT EXISTS idx_calls_started_at ON calls(started_at);
CREATE INDEX IF NOT EXISTS idx_calls_attention  ON calls(attention_score DESC);

CREATE TABLE IF NOT EXISTS turns (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id          TEXT NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    turn_index       INTEGER NOT NULL,
    speaker          TEXT NOT NULL CHECK (speaker IN ('agent', 'customer')),
    start_seconds    REAL NOT NULL,
    end_seconds      REAL NOT NULL,
    text             TEXT NOT NULL,
    words_json       TEXT,                             -- [{text, start, end, confidence}]
    mood_score       REAL,                             -- customer turns only
    overlapping      INTEGER NOT NULL DEFAULT 0,
    UNIQUE (call_id, turn_index)
);
CREATE INDEX IF NOT EXISTS idx_turns_call ON turns(call_id, turn_index);

-- Every citation the system shows, as rows rather than buried in JSON columns.
-- This is what makes the eval harness's headline number a single SQL query:
--   SELECT AVG(verified) FROM evidence;
-- and what lets the dashboard render an unverified claim AS unverified instead
-- of silently presenting it as fact.
CREATE TABLE IF NOT EXISTS evidence (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id       TEXT NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    claim_type    TEXT NOT NULL,      -- "intent" | "resolution" | "mood_shift" | "attention_factor"
                                      -- | "resolution_contradiction_agent" | "resolution_contradiction_customer"
    claim_text    TEXT NOT NULL,      -- the claim this evidence is meant to support
    turn_id       INTEGER REFERENCES turns(id),
    timestamp     TEXT NOT NULL,      -- "HH:MM:SS"
    quote         TEXT NOT NULL,      -- verbatim, looked up from turns — never LLM-authored
    match_score   REAL,               -- rapidfuzz span score
    support_score REAL,               -- claim-vs-quote entailment / similarity
    verified      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_evidence_call ON evidence(call_id, claim_type);

CREATE TABLE IF NOT EXISTS issue_clusters (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    label      TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS call_clusters (
    call_id    TEXT NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    cluster_id INTEGER NOT NULL REFERENCES issue_clusters(id),
    PRIMARY KEY (call_id, cluster_id)
);
