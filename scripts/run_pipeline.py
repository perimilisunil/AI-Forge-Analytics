"""
scripts/run_pipeline.py
────────────────────────
Full pipeline orchestrator.

Usage:
  python scripts/run_pipeline.py --mode synthetic   # re-run analytics on existing DB
  python scripts/run_pipeline.py --mode live        # fetch real GitHub PRs + analytics
  python scripts/run_pipeline.py --mode github-only # only sync GitHub, skip PII scan
  python scripts/run_pipeline.py --mode analyze     # just re-compute analytics cache

Flags:
  --skip-pii      skip PII re-scoring
  --skip-github   skip GitHub API sync
  --skip-export   skip CSV export
  --repo OWNER/REPO  sync a single repo only (live mode)
  --max-prs N     override max PRs per repo (default from config)
"""

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from src.config import (
    DB_PATH, PROCESSED_DIR, TARGET_REPOS, DEPARTMENTS,
    MAX_PRS_PER_REPO, GITHUB_DAYS_BACK, COPILOT_LAUNCH_DATE, logger,
)
from src.data.loader import (
    load_users, load_usage_logs, load_jira, load_github,
)
from src.data.preprocessor import (
    enrich_usage_logs, compute_dept_performance, compute_user_summary,
    save_processed,
)
from src.governance.analyzer import batch_analyze
from src.governance.redactor import redact_dataframe
from src.analysis.metrics import populate_analytics_cache, executive_kpis
from src.analysis.optimizer import classify_users, optimisation_summary
from src.github.api_client import (
    fetch_all_repos, fetch_single_repo,
    build_username_map_from_db, check_rate_limit, dept_summary_from_df,
)
from src.github.pr_analyzer import (
    ensure_period_column, enrich_department,
    pr_performance_summary, compute_pr_efficiency_delta,
)


# ═══════════════════════════════════════════════════════
# STAGE 1 — PII SCAN
# ═══════════════════════════════════════════════════════

def stage_pii_scan():
    """Re-score risk_score / risk_level for all usage logs via spaCy NER."""
    logger.info("─── Stage 1: PII Scan ───────────────────────────")

    logs = load_usage_logs()
    if logs.empty:
        logger.warning("No usage logs — skipping PII scan")
        return

    records = logs[["prompt_id", "prompt_text"]].to_dict("records")
    logger.info(f"Scanning {len(records):,} prompts…")

    results = batch_analyze(records)

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    for r in results:
        cur.execute(
            "UPDATE ai_usage_logs SET risk_score=?, risk_level=?, risk_flag=? "
            "WHERE prompt_id=?",
            (r.risk_score, r.risk_level, r.risk_flag, r.prompt_id),
        )
    conn.commit()
    conn.close()
    logger.info(f"PII scan complete — {sum(1 for r in results if r.risk_flag)} flagged")


# ═══════════════════════════════════════════════════════
# STAGE 2 — GITHUB SYNC (Public Repos)
# ═══════════════════════════════════════════════════════

def stage_github_sync(single_repo: str = None, max_prs: int = None):
    """
    Fetch merged PRs from all 19 public repos (or one specific repo).
    Each PR is labelled Before/After based on COPILOT_LAUNCH_DATE.
    """
    logger.info("─── Stage 2: GitHub Sync ────────────────────────")
    logger.info(f"  Copilot launch boundary: {COPILOT_LAUNCH_DATE}")
    logger.info(f"  Target repos: {len(TARGET_REPOS)}")

    # Check rate limit before starting
    rl = check_rate_limit()
    if rl["remaining"] == 0:
        logger.error("GitHub rate limit exhausted. Cannot sync.")
        return
    logger.info(f"  Rate limit headroom: {rl['remaining']:,}/{rl['limit']:,}")

    username_map = build_username_map_from_db()
    kw = {}
    if max_prs:
        kw["max_per_repo"] = max_prs

    if single_repo:
        logger.info(f"  Single-repo mode: {single_repo}")
        df = fetch_single_repo(single_repo, username_map=username_map, **kw)
    else:
        df = fetch_all_repos(username_map=username_map, **kw)

    if df.empty:
        logger.warning("No GitHub data fetched — check token and network")
        return

    # Ensure all enrichment columns present
    df = ensure_period_column(df)
    df = enrich_department(df)

    # Write to DB
    conn = sqlite3.connect(DB_PATH)
    if single_repo:
        # Incremental: delete old rows for this repo then insert fresh
        repo_name = single_repo.split("/")[1]
        conn.execute(
            "DELETE FROM github_metrics WHERE repo_name = ?", (repo_name,)
        )
        conn.commit()
        df.to_sql("github_metrics", conn, if_exists="append", index=False)
    else:
        df.to_sql("github_metrics", conn, if_exists="replace", index=False)
    conn.close()

    # Print a clean department summary
    summary = dept_summary_from_df(df)
    if not summary.empty:
        logger.info("\n  Department × Period summary:")
        for _, row in summary.iterrows():
            logger.info(
                f"  {row['department']:<15} {row['period']:<8} "
                f"{int(row['pr_count']):>5} PRs  "
                f"avg {row['avg_cycle_hrs']:.1f}h  "
                f"rework {row['avg_rework']:.2f}"
            )

    # Efficiency delta
    perf = pr_performance_summary(df)
    delta = compute_pr_efficiency_delta(perf)
    if not delta.empty:
        logger.info("\n  PR Efficiency Gain (After vs Before Copilot):")
        for _, row in delta.iterrows():
            logger.info(
                f"  {row['department']:<15} "
                f"{row['pct_improvement']:+.1f}%  "
                f"({row['before_avg']:.1f}h → {row['after_avg']:.1f}h)"
            )


# ═══════════════════════════════════════════════════════
# STAGE 3 — ANALYTICS
# ═══════════════════════════════════════════════════════

def stage_analytics():
    """Compute user summary, populate analytics cache, print KPIs."""
    logger.info("─── Stage 3: Analytics ─────────────────────────")

    users  = load_users()
    logs   = load_usage_logs()
    jira   = load_jira()
    github = load_github()

    if users.empty or logs.empty:
        logger.error("Missing core data — cannot run analytics")
        return

    enriched     = enrich_usage_logs(logs, users)
    user_summary = compute_user_summary(logs, jira, users, github)
    classified   = classify_users(user_summary)

    n_rows    = populate_analytics_cache(user_summary, enriched)
    kpis      = executive_kpis(logs, jira, user_summary)
    opt       = optimisation_summary(classified)

    # ── Write processed CSVs to data/processed/ ──────────
    dept_perf = compute_dept_performance(jira)
    save_processed(enriched, dept_perf, user_summary, github)

    logger.info("\n  ── Executive KPIs ─────────────────────────")
    logger.info(f"  Total AI Spend:       ${kpis['total_spend']:,.2f}")
    logger.info(f"  Efficiency Gain:      {kpis['pct_improvement']:.1f}%")
    logger.info(f"  Total Tokens:         {kpis['total_tokens']:,}")
    logger.info(f"  High/Critical Risk:   {kpis['high_risk_events']} events")
    logger.info(f"  GitHub Matched:       {kpis['github_matched']} users")
    logger.info(f"\n  ── Cost Optimisation ──────────────────────")
    logger.info(f"  Zombie Users:         {opt['zombie_count']} ({opt['zombie_pct']}%)")
    logger.info(f"  Monthly Savings:      ${opt['total_monthly_saving']:,.2f}")
    logger.info(f"  Annual Projection:    ${opt['annual_saving_projection']:,.2f}")
    logger.info(f"  Analytics cache:      {n_rows} rows written")


# ═══════════════════════════════════════════════════════
# STAGE 4 — EXPORT
# ═══════════════════════════════════════════════════════

def stage_export():
    """Write processed, redacted CSVs to data/processed/."""
    logger.info("─── Stage 4: Export ────────────────────────────")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    users  = load_users()
    logs   = load_usage_logs()
    jira   = load_jira()
    github = load_github()

    enriched     = enrich_usage_logs(logs, users)
    dept_perf    = compute_dept_performance(jira)
    user_summary = compute_user_summary(logs, jira, users, github)
    classified   = classify_users(user_summary)

    # Redact PII before export
    safe_logs = redact_dataframe(enriched, text_col="prompt_text")
    safe_logs.to_csv(PROCESSED_DIR / "usage_logs_redacted.csv",  index=False)
    dept_perf.to_csv( PROCESSED_DIR / "dept_performance.csv",    index=False)
    classified.to_csv(PROCESSED_DIR / "user_summary.csv",         index=False)

    if not github.empty:
        # Export GitHub data without user_id (privacy)
        gh_export = github.drop(columns=["user_id"], errors="ignore")
        gh_export.to_csv(PROCESSED_DIR / "github_pr_data.csv", index=False)

    logger.info(f"  Exports written to {PROCESSED_DIR}")
    logger.info(f"  Files: usage_logs_redacted.csv, dept_performance.csv, "
                f"user_summary.csv, github_pr_data.csv")


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="AIFORGE Pipeline Orchestrator",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["synthetic", "live", "github-only", "analyze"],
        default="synthetic",
        help=(
            "synthetic    : analytics only, uses existing DB data\n"
            "live         : full sync — PII scan + GitHub + analytics\n"
            "github-only  : only sync GitHub PRs\n"
            "analyze      : re-compute analytics cache only"
        ),
    )
    parser.add_argument("--skip-pii",    action="store_true")
    parser.add_argument("--skip-github", action="store_true")
    parser.add_argument("--skip-export", action="store_true")
    parser.add_argument(
        "--repo",
        default=None,
        help="Sync a single repo only (e.g. microsoft/vscode). Live mode only.",
    )
    parser.add_argument(
        "--max-prs",
        type=int,
        default=None,
        help=f"Override max PRs per repo (default: {MAX_PRS_PER_REPO})",
    )
    args = parser.parse_args()

    logger.info("═══════════════════════════════════════════════")
    logger.info(f"  AIFORGE Pipeline  |  mode: {args.mode}")
    logger.info(f"  DB: {DB_PATH}")
    logger.info(f"  Repos: {len(TARGET_REPOS)}  |  Depts: {len(DEPARTMENTS)}")
    logger.info(f"  Copilot boundary: {COPILOT_LAUNCH_DATE}")
    logger.info("═══════════════════════════════════════════════")

    if not DB_PATH.exists() and args.mode != "live":
        logger.error("Database not found. Run first: python scripts/setup_db.py")
        sys.exit(1)

    if args.mode == "synthetic":
        if not args.skip_pii:
            stage_pii_scan()
        stage_analytics()
        if not args.skip_export:
            stage_export()

    elif args.mode == "live":
        if not args.skip_pii:
            stage_pii_scan()
        if not args.skip_github:
            stage_github_sync(single_repo=args.repo, max_prs=args.max_prs)
        stage_analytics()
        if not args.skip_export:
            stage_export()

    elif args.mode == "github-only":
        stage_github_sync(single_repo=args.repo, max_prs=args.max_prs)

    elif args.mode == "analyze":
        stage_analytics()
        if not args.skip_export:
            stage_export()

    logger.info("Pipeline complete.")


if __name__ == "__main__":
    main()
