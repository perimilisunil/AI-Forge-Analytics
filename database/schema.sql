-- ═══════════════════════════════════════════════════════
-- AIFORGE Analytics Platform — Database Schema
-- ═══════════════════════════════════════════════════════

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ─────────────────────────────────────────────────────────
-- 1. USERS MASTER
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users_master (
    user_id           TEXT PRIMARY KEY,
    employee_name     TEXT    NOT NULL,
    department        TEXT    NOT NULL,
    role              TEXT    NOT NULL,
    license_type      TEXT    NOT NULL,
    hourly_rate       REAL    DEFAULT 0.0,
    ai_adoption_date  TEXT,
    employment_status TEXT    DEFAULT 'Active',
    github_username   TEXT    UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_users_dept   ON users_master(department);
CREATE INDEX IF NOT EXISTS idx_users_github ON users_master(github_username);

-- ─────────────────────────────────────────────────────────
-- 2. AI USAGE LOGS
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_usage_logs (
    prompt_id    TEXT    PRIMARY KEY,
    user_id      TEXT    NOT NULL,
    timestamp    TEXT    NOT NULL,
    department   TEXT    NOT NULL,
    model_name   TEXT    NOT NULL,
    prompt_text  TEXT,
    token_count  INTEGER DEFAULT 0,
    cost_usd     REAL    DEFAULT 0.0,
    risk_flag    INTEGER DEFAULT 0,
    risk_score   REAL    DEFAULT 0.0,
    risk_level   TEXT    DEFAULT 'Low',
    FOREIGN KEY (user_id) REFERENCES users_master(user_id)
);

CREATE INDEX IF NOT EXISTS idx_logs_user  ON ai_usage_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_logs_dept  ON ai_usage_logs(department);
CREATE INDEX IF NOT EXISTS idx_logs_ts    ON ai_usage_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_risk  ON ai_usage_logs(risk_level);
CREATE INDEX IF NOT EXISTS idx_logs_model ON ai_usage_logs(model_name);

-- ─────────────────────────────────────────────────────────
-- 3. JIRA TICKETS (SYNTHETIC)
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jira_tickets_synthetic (
    jira_issue_id               TEXT    PRIMARY KEY,
    user_id                     TEXT    NOT NULL,
    department                  TEXT    NOT NULL,
    created_at                  TEXT    NOT NULL,
    resolved_at                 TEXT,
    cycle_time_hours            REAL    DEFAULT 0.0,
    story_points                INTEGER DEFAULT 1,
    priority                    TEXT    DEFAULT 'Medium',
    period                      TEXT    NOT NULL
        CHECK (period IN ('Before', 'After')),
    avg_ticket_resolution_hours REAL    DEFAULT 0.0,
    jira_tickets_closed         INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users_master(user_id)
);

CREATE INDEX IF NOT EXISTS idx_jira_user     ON jira_tickets_synthetic(user_id);
CREATE INDEX IF NOT EXISTS idx_jira_dept     ON jira_tickets_synthetic(department);
CREATE INDEX IF NOT EXISTS idx_jira_period   ON jira_tickets_synthetic(period);
CREATE INDEX IF NOT EXISTS idx_jira_priority ON jira_tickets_synthetic(priority);

-- ─────────────────────────────────────────────────────────
-- 4. GITHUB METRICS
--    Stores both synthetic seed data and live API data.
--    period column uses Copilot launch (21 Jun 2022) as boundary.
--    repo_full_name: 'owner/repo'  e.g. 'microsoft/vscode'
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS github_metrics (
    pr_id               TEXT    PRIMARY KEY,
    user_id             TEXT,
    github_username     TEXT    NOT NULL,
    repo_name           TEXT    NOT NULL,
    repo_full_name      TEXT,                    -- 'owner/repo'
    department          TEXT,                    -- mapped from repo in config.py
    pr_title            TEXT,
    pr_state            TEXT    DEFAULT 'open',
    created_at          TEXT    NOT NULL,
    merged_at           TEXT,
    cycle_time_hours    REAL    DEFAULT 0.0,
    lines_added         INTEGER DEFAULT 0,
    lines_removed       INTEGER DEFAULT 0,
    review_count        INTEGER DEFAULT 0,
    commit_count        INTEGER DEFAULT 0,
    rework_ratio        REAL    DEFAULT 0.0,
    period              TEXT    DEFAULT 'Unknown'
        CHECK (period IN ('Before', 'After', 'Unknown')),
    FOREIGN KEY (user_id) REFERENCES users_master(user_id)
);

CREATE INDEX IF NOT EXISTS idx_gh_user       ON github_metrics(github_username);
CREATE INDEX IF NOT EXISTS idx_gh_dept       ON github_metrics(department);
CREATE INDEX IF NOT EXISTS idx_gh_repo       ON github_metrics(repo_name);
CREATE INDEX IF NOT EXISTS idx_gh_period     ON github_metrics(period);
CREATE INDEX IF NOT EXISTS idx_gh_full_name  ON github_metrics(repo_full_name);

-- ─────────────────────────────────────────────────────────
-- 5. ANALYTICS CACHE
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analytics_cache (
    cache_id             TEXT    PRIMARY KEY,
    user_id              TEXT    NOT NULL,
    department           TEXT    NOT NULL,
    month_year           TEXT    NOT NULL,
    total_ai_cost        REAL    DEFAULT 0.0,
    total_tokens         INTEGER DEFAULT 0,
    tickets_before_avg   REAL    DEFAULT 0.0,
    tickets_after_avg    REAL    DEFAULT 0.0,
    hours_saved          REAL    DEFAULT 0.0,
    dollar_value_saved   REAL    DEFAULT 0.0,
    net_roi              REAL    DEFAULT 0.0,
    dept_risk_score      REAL    DEFAULT 0.0,
    pii_violations       INTEGER DEFAULT 0,
    pr_cycle_time_avg    REAL    DEFAULT 0.0,
    computed_at          TEXT,
    FOREIGN KEY (user_id) REFERENCES users_master(user_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cache_user_month
    ON analytics_cache(user_id, month_year);
