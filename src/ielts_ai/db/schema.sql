-- IELTS Writing AI — SQLite schema
-- Run via: python scripts/init_db.py

CREATE TABLE IF NOT EXISTS essays (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_email TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    essay_text  TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ai_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    essay_id    INTEGER NOT NULL REFERENCES essays(id),
    version     INTEGER NOT NULL DEFAULT 1,
    result_json TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_results_essay_version
    ON ai_results (essay_id, version);

CREATE TABLE IF NOT EXISTS reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    essay_id        INTEGER NOT NULL REFERENCES essays(id),
    final_bands_json TEXT NOT NULL,
    examiner_comment TEXT NOT NULL,
    approved_at     TEXT,
    action          TEXT NOT NULL DEFAULT 'accept'
);

CREATE TABLE IF NOT EXISTS regrade_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    essay_id INTEGER NOT NULL REFERENCES essays(id),
    criterion TEXT NOT NULL,
    feedback TEXT NOT NULL,
    from_version INTEGER NOT NULL,
    to_version INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS emails (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    essay_id    INTEGER NOT NULL REFERENCES essays(id),
    to_email    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    error       TEXT,
    sent_at     TEXT
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL DEFAULT (datetime('now')),
    essay_id    INTEGER,
    step        TEXT NOT NULL,
    latency_ms  REAL NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    retries     INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'ok',
    error       TEXT
);
