-- ═══════════════════════════════════════════════════════
-- AIFORGE Analytics — Reusable Analytics Queries
-- All department values now reflect the 7 real departments
-- mapped from 19 public GitHub repos.
-- Before/After boundary = GitHub Copilot launch 21 Jun 2022.
-- ═══════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────
-- Q1: Full ROI Summary per User (Jira-based)
-- ─────────────────────────────────────────────────────────
SELECT
    u.user_id,
    u.employee_name,
    u.department,
    u.role,
    u.hourly_rate,
    u.license_type,
    u.github_username,

    COALESCE(cost_agg.total_cost,   0) AS total_ai_cost,
    COALESCE(cost_agg.total_tokens, 0) AS total_tokens,
    COALESCE(cost_agg.prompt_count, 0) AS total_prompts,

    COALESCE(jb.avg_cycle, 0)    AS avg_cycle_before_hrs,
    COALESCE(jb.ticket_count, 0) AS tickets_before,
    COALESCE(ja.avg_cycle, 0)    AS avg_cycle_after_hrs,
    COALESCE(ja.ticket_count, 0) AS tickets_after,

    ROUND(COALESCE(jb.avg_cycle,0) - COALESCE(ja.avg_cycle,0), 2) AS hours_saved_per_ticket,

    ROUND(
        (COALESCE(jb.avg_cycle,0) - COALESCE(ja.avg_cycle,0))
        / NULLIF(COALESCE(jb.avg_cycle,0), 0) * 100, 1
    ) AS pct_improvement,

    ROUND(
        (COALESCE(jb.avg_cycle,0) - COALESCE(ja.avg_cycle,0))
        * COALESCE(ja.ticket_count,0) * u.hourly_rate, 2
    ) AS dollar_value_saved,

    ROUND(
        (COALESCE(jb.avg_cycle,0) - COALESCE(ja.avg_cycle,0))
        * COALESCE(ja.ticket_count,0) * u.hourly_rate
        - COALESCE(cost_agg.total_cost, 0), 2
    ) AS net_roi

FROM users_master u

LEFT JOIN (
    SELECT user_id,
           SUM(cost_usd)    AS total_cost,
           SUM(token_count) AS total_tokens,
           COUNT(prompt_id) AS prompt_count
    FROM   ai_usage_logs
    GROUP  BY user_id
) cost_agg ON u.user_id = cost_agg.user_id

LEFT JOIN (
    SELECT user_id, AVG(cycle_time_hours) AS avg_cycle, COUNT(*) AS ticket_count
    FROM   jira_tickets_synthetic WHERE period = 'Before'
    GROUP  BY user_id
) jb ON u.user_id = jb.user_id

LEFT JOIN (
    SELECT user_id,
           AVG(cycle_time_hours)    AS avg_cycle,
           SUM(jira_tickets_closed) AS ticket_count
    FROM   jira_tickets_synthetic WHERE period = 'After'
    GROUP  BY user_id
) ja ON u.user_id = ja.user_id

ORDER BY net_roi DESC;


-- ─────────────────────────────────────────────────────────
-- Q2: Department ROI Rollup (Jira)
-- ─────────────────────────────────────────────────────────
SELECT
    u.department,
    COUNT(DISTINCT u.user_id)          AS headcount,
    ROUND(SUM(cost_agg.total_cost), 2) AS dept_ai_spend,
    ROUND(AVG(jb.avg_cycle), 2)        AS avg_cycle_before,
    ROUND(AVG(ja.avg_cycle), 2)        AS avg_cycle_after,
    ROUND(
        (AVG(jb.avg_cycle) - AVG(ja.avg_cycle))
        / NULLIF(AVG(jb.avg_cycle), 0) * 100, 1
    ) AS dept_efficiency_pct,
    ROUND(AVG(risk_agg.avg_risk), 2)   AS avg_risk_score

FROM users_master u

LEFT JOIN (
    SELECT user_id, SUM(cost_usd) AS total_cost
    FROM ai_usage_logs GROUP BY user_id
) cost_agg ON u.user_id = cost_agg.user_id

LEFT JOIN (
    SELECT user_id, AVG(cycle_time_hours) AS avg_cycle
    FROM jira_tickets_synthetic WHERE period = 'Before' GROUP BY user_id
) jb ON u.user_id = jb.user_id

LEFT JOIN (
    SELECT user_id, AVG(cycle_time_hours) AS avg_cycle
    FROM jira_tickets_synthetic WHERE period = 'After' GROUP BY user_id
) ja ON u.user_id = ja.user_id

LEFT JOIN (
    SELECT user_id, AVG(risk_score) AS avg_risk
    FROM ai_usage_logs WHERE risk_score > 0 GROUP BY user_id
) risk_agg ON u.user_id = risk_agg.user_id

GROUP BY u.department
ORDER BY dept_efficiency_pct DESC;


-- ─────────────────────────────────────────────────────────
-- Q3: GitHub PR Efficiency — Before vs After Copilot
--     Groups by department and period using the 19 public repos
-- ─────────────────────────────────────────────────────────
SELECT
    department,
    period,
    COUNT(pr_id)                     AS pr_count,
    ROUND(AVG(cycle_time_hours), 2)  AS avg_cycle_hrs,
    ROUND(AVG(rework_ratio), 3)      AS avg_rework_ratio,
    ROUND(AVG(review_count), 1)      AS avg_reviews,
    COUNT(DISTINCT github_username)  AS unique_contributors,
    SUM(lines_added)                 AS total_lines_added,
    SUM(lines_removed)               AS total_lines_removed
FROM   github_metrics
WHERE  pr_state = 'merged'
  AND  period   IN ('Before', 'After')
GROUP  BY department, period
ORDER  BY department, period;


-- ─────────────────────────────────────────────────────────
-- Q4: GitHub Efficiency Delta per Department
--     Self-join Before vs After to compute improvement
-- ─────────────────────────────────────────────────────────
SELECT
    b.department,
    ROUND(b.avg_cycle, 2)                                AS before_avg_hrs,
    ROUND(a.avg_cycle, 2)                                AS after_avg_hrs,
    ROUND(b.avg_cycle - a.avg_cycle, 2)                  AS hours_saved,
    ROUND((b.avg_cycle - a.avg_cycle)
          / NULLIF(b.avg_cycle, 0) * 100, 1)             AS pct_improvement,
    ROUND(b.avg_rework - a.avg_rework, 3)                AS rework_improvement,
    b.pr_count                                           AS before_prs,
    a.pr_count                                           AS after_prs

FROM (
    SELECT department, AVG(cycle_time_hours) AS avg_cycle,
           AVG(rework_ratio) AS avg_rework, COUNT(*) AS pr_count
    FROM github_metrics WHERE period='Before' AND pr_state='merged'
    GROUP BY department
) b
JOIN (
    SELECT department, AVG(cycle_time_hours) AS avg_cycle,
           AVG(rework_ratio) AS avg_rework, COUNT(*) AS pr_count
    FROM github_metrics WHERE period='After' AND pr_state='merged'
    GROUP BY department
) a ON b.department = a.department
ORDER BY pct_improvement DESC;


-- ─────────────────────────────────────────────────────────
-- Q5: Per-Repo Statistics (all 19 repos)
-- ─────────────────────────────────────────────────────────
SELECT
    repo_full_name,
    repo_name,
    department,
    period,
    COUNT(pr_id)                       AS pr_count,
    ROUND(AVG(cycle_time_hours), 2)    AS avg_cycle_hrs,
    ROUND(MEDIAN(cycle_time_hours), 2) AS median_cycle_hrs,
    ROUND(AVG(rework_ratio), 3)        AS avg_rework,
    COUNT(DISTINCT github_username)    AS contributors,
    SUM(lines_added)                   AS total_additions,
    SUM(lines_removed)                 AS total_deletions
FROM   github_metrics
WHERE  pr_state = 'merged'
GROUP  BY repo_full_name, period
ORDER  BY department, repo_name, period;


-- ─────────────────────────────────────────────────────────
-- Q6: Top 20 GitHub Contributors (by PRs merged, After period)
-- ─────────────────────────────────────────────────────────
SELECT
    github_username,
    department,
    COUNT(pr_id)                      AS prs_merged,
    ROUND(AVG(cycle_time_hours), 2)   AS avg_cycle_hrs,
    ROUND(AVG(rework_ratio), 3)       AS avg_rework,
    COUNT(DISTINCT repo_name)         AS repos_contributed,
    SUM(lines_added)                  AS total_lines_added
FROM   github_metrics
WHERE  pr_state = 'merged'
  AND  period   = 'After'
GROUP  BY github_username
ORDER  BY prs_merged DESC
LIMIT  20;


-- ─────────────────────────────────────────────────────────
-- Q7: Zombie Licence Detection
-- ─────────────────────────────────────────────────────────
SELECT
    u.user_id,
    u.employee_name,
    u.department,
    u.role,
    u.license_type,
    COALESCE(cost_agg.total_cost,   0) AS total_ai_cost,
    COALESCE(cost_agg.prompt_count, 0) AS total_prompts,
    COALESCE(ja.tickets_closed,     0) AS tickets_after_ai,
    COALESCE(gh.pr_count,           0) AS prs_merged,
    'Zombie'                           AS classification
FROM users_master u
LEFT JOIN (
    SELECT user_id, SUM(cost_usd) AS total_cost, COUNT(*) AS prompt_count
    FROM ai_usage_logs GROUP BY user_id
) cost_agg ON u.user_id = cost_agg.user_id
LEFT JOIN (
    SELECT user_id, SUM(jira_tickets_closed) AS tickets_closed
    FROM jira_tickets_synthetic WHERE period='After' GROUP BY user_id
) ja ON u.user_id = ja.user_id
LEFT JOIN (
    SELECT user_id, COUNT(*) AS pr_count
    FROM github_metrics WHERE pr_state='merged' GROUP BY user_id
) gh ON u.user_id = gh.user_id
WHERE
    COALESCE(cost_agg.total_cost, 0) > (
        SELECT AVG(total_cost) FROM (
            SELECT user_id, SUM(cost_usd) AS total_cost
            FROM ai_usage_logs GROUP BY user_id
        )
    )
    AND COALESCE(ja.tickets_closed, 0) = 0
    AND COALESCE(gh.pr_count, 0) = 0
ORDER BY total_ai_cost DESC;


-- ─────────────────────────────────────────────────────────
-- Q8: Risk Events — Top 25 Worst Prompts
-- ─────────────────────────────────────────────────────────
SELECT
    l.prompt_id,
    l.user_id,
    l.department,
    l.model_name,
    l.timestamp,
    l.risk_score,
    l.risk_level,
    SUBSTR(l.prompt_text, 1, 100) || '...' AS prompt_preview
FROM   ai_usage_logs l
WHERE  l.risk_score > 0
ORDER  BY l.risk_score DESC
LIMIT  25;


-- ─────────────────────────────────────────────────────────
-- Q9: Monthly Trend — Cost + Tokens over time
-- ─────────────────────────────────────────────────────────
SELECT
    STRFTIME('%Y-%m', timestamp)   AS month_year,
    department,
    COUNT(prompt_id)               AS prompt_count,
    SUM(token_count)               AS total_tokens,
    ROUND(SUM(cost_usd), 4)        AS total_cost,
    COUNT(DISTINCT user_id)        AS active_users,
    SUM(risk_flag)                 AS pii_violations
FROM   ai_usage_logs
GROUP  BY month_year, department
ORDER  BY month_year, department;
