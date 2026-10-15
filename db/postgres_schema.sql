-- ============================================================================
--  OEE Smart Factory - PostgreSQL 14 schema (metadata, alerts, maintenance, feedback)
--  Idempotent: safe to run any number of times.
--
--    docker cp db/postgres_schema.sql oee-postgres:/schema.sql
--    docker exec -it oee-postgres psql -U oee_user -d oee_db -f /schema.sql
-- ============================================================================

-- ---------------------------------------------------------------- machines
CREATE TABLE IF NOT EXISTS machines (
    id             TEXT PRIMARY KEY,
    name           TEXT             NOT NULL,
    kind           TEXT,
    ideal_cycle_s  DOUBLE PRECISION NOT NULL DEFAULT 10,
    temp_limit     DOUBLE PRECISION NOT NULL DEFAULT 85,     -- hard Red threshold (deg C)
    vib_limit      DOUBLE PRECISION NOT NULL DEFAULT 7,      -- hard Red threshold (mm/s)
    active         BOOLEAN          NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ      NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ      NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- users (HTTP Basic auth, single tenant)
CREATE TABLE IF NOT EXISTS users (
    username       TEXT PRIMARY KEY,
    role           TEXT        NOT NULL,
    password_hash  TEXT        NOT NULL,                      -- pbkdf2_sha256$iterations$salt$hash
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- alerts
CREATE TABLE IF NOT EXISTS alerts (
    id           BIGINT PRIMARY KEY,
    machine_id   TEXT        NOT NULL REFERENCES machines(id) ON UPDATE CASCADE,
    level        TEXT        NOT NULL CHECK (level IN ('yellow', 'orange', 'red')),
    kind         TEXT        NOT NULL,
    status       TEXT        NOT NULL CHECK (status IN ('open', 'acknowledged', 'cleared', 'resolved')),
    active       BOOLEAN     NOT NULL DEFAULT TRUE,
    title        TEXT,
    message      TEXT,
    value        DOUBLE PRECISION,
    threshold    DOUBLE PRECISION,
    eta_s        DOUBLE PRECISION,
    score        DOUBLE PRECISION,
    opened_at    TIMESTAMPTZ NOT NULL,
    cleared_at   TIMESTAMPTZ,
    acked_by     TEXT,
    acked_at     TIMESTAMPTZ,
    technician   TEXT,
    resolved_by  TEXT,
    resolved_at  TIMESTAMPTZ,
    resolution_notes TEXT,
    payload      JSONB       NOT NULL,                        -- full alert object (source of truth for reload)
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_alerts_machine_time ON alerts (machine_id, opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_level        ON alerts (level);
CREATE INDEX IF NOT EXISTS idx_alerts_active       ON alerts (active) WHERE active;

-- ---------------------------------------------------------------- operator feedback on ML cautions
CREATE TABLE IF NOT EXISTS feedback (
    id          BIGSERIAL PRIMARY KEY,
    alert_id    BIGINT      NOT NULL UNIQUE REFERENCES alerts(id) ON DELETE CASCADE,
    verdict     TEXT        NOT NULL CHECK (verdict IN ('true_positive', 'false_positive')),
    given_by    TEXT,
    comment     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_feedback_verdict ON feedback (verdict);

-- ---------------------------------------------------------------- maintenance log
CREATE TABLE IF NOT EXISTS maintenance_logs (
    id          BIGINT PRIMARY KEY,
    machine_id  TEXT        NOT NULL REFERENCES machines(id) ON UPDATE CASCADE,
    alert_id    BIGINT      REFERENCES alerts(id) ON DELETE SET NULL,
    action      TEXT        NOT NULL,
    notes       TEXT,
    technician  TEXT,
    status      TEXT        NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'closed')),
    created_by  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload     JSONB       NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_maint_machine_time ON maintenance_logs (machine_id, created_at DESC);

-- ---------------------------------------------------------------- ML model registry
CREATE TABLE IF NOT EXISTS ml_models (
    id          BIGSERIAL PRIMARY KEY,
    algorithm   TEXT        NOT NULL,
    trained_at  TIMESTAMPTZ NOT NULL,
    threshold   DOUBLE PRECISION,
    metrics     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (algorithm, trained_at)
);

-- ---------------------------------------------------------------- seed: the five machines of the SRS
INSERT INTO machines (id, name, kind, ideal_cycle_s, temp_limit, vib_limit) VALUES
    ('CNC-01',      'CNC Mill',        'Machining', 12, 85, 7.0),
    ('Press-02',    'Hydraulic Press', 'Forming',    6, 85, 8.0),
    ('Conveyor-03', 'Main Conveyor',   'Transport',  2, 80, 5.0),
    ('Welder-04',   'Robotic Welder',  'Joining',    9, 90, 6.0),
    ('Packer-05',   'Packaging Unit',  'Packaging',  4, 80, 5.5)
ON CONFLICT (id) DO NOTHING;
