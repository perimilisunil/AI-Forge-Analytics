"""
src/github/api_client.py
─────────────────────────
GitHub REST API v3 Client — Public Repo Mode.

Fetches merged Pull Requests from 19 hand-picked world-class public
repos (no org, no private access required).  Each repo is mapped to
a department via TARGET_REPOS in config.py.

Before/After AI boundary: GitHub Copilot public launch 21 Jun 2022.
PRs merged before that date  → period = "Before"
PRs merged on/after that date → period = "After"

Rate limit:  5,000 requests / hour with a personal token.
             Each page = 1 request (100 PRs/page).
             19 repos × 400 PRs = ~7,600 PRs → ~76 API calls → ~2 min.
"""

import time
import sqlite3
from datetime import datetime, timedelta, timezone, date
from typing import Optional

import pandas as pd
from loguru import logger

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import (
    GITHUB_TOKEN,
    TARGET_REPOS,
    REPO_TO_DEPT,
    COPILOT_LAUNCH_DATE,
    MAX_PRS_PER_REPO,
    GITHUB_DAYS_BACK,
    DB_PATH,
)


# ─── Auth ─────────────────────────────────────────────────

def _get_client():
    """
    Return an authenticated PyGithub client.
    Prints rate-limit status so the developer can see headroom.
    Returns None if token is missing or auth fails.
    """
    if not GITHUB_TOKEN:
        logger.warning(
            "GITHUB_TOKEN not set in .env\n"
            "Add:  GITHUB_TOKEN=ghp_your_token_here\n"
            "GitHub data will be unavailable until set."
        )
        return None
    try:
        from github import Github
        g = Github(GITHUB_TOKEN, per_page=100, retry=3, timeout=30)
        rl = g.get_rate_limit()
        logger.info(
            f"GitHub authenticated  |  "
            f"Rate limit: {rl.core.remaining:,}/{rl.core.limit:,} remaining  |  "
            f"Resets: {rl.core.reset.strftime('%H:%M UTC')}"
        )
        if rl.core.remaining < 200:
            logger.warning(
                f"Low rate limit ({rl.core.remaining} remaining). "
                "Consider reducing MAX_PRS_PER_REPO or waiting for reset."
            )
        return g
    except Exception as exc:
        logger.error(f"GitHub authentication failed: {exc}")
        return None


# ─── Period label ─────────────────────────────────────────

def _period(merged_at: datetime) -> str:
    """
    Label a PR as Before or After the Copilot public launch.
    merged_at must be a timezone-aware datetime.
    """
    cutoff = datetime(
        COPILOT_LAUNCH_DATE.year,
        COPILOT_LAUNCH_DATE.month,
        COPILOT_LAUNCH_DATE.day,
        tzinfo=timezone.utc,
    )
    return "After" if merged_at >= cutoff else "Before"


# ─── Core fetcher ─────────────────────────────────────────

def fetch_all_repos(
    days_back:       int  = GITHUB_DAYS_BACK,
    max_per_repo:    int  = MAX_PRS_PER_REPO,
    username_map:    dict = None,
    progress_cb      = None,   # optional callable(repo_name, fetched, total_repos)
) -> pd.DataFrame:
    """
    Fetch merged PRs from every repo in TARGET_REPOS.

    Args:
        days_back:      How many calendar days back to fetch PRs from.
        max_per_repo:   Hard cap on PRs per repo (protects rate limit).
        username_map:   {github_username: user_id} from users_master.
                        Pass None if you don't need internal user mapping.
        progress_cb:    Optional callback for UI progress reporting.

    Returns:
        DataFrame with columns matching the github_metrics schema.
        Returns empty DataFrame if token is missing.
    """
    g = _get_client()
    if g is None:
        return pd.DataFrame()

    from github import GithubException, RateLimitExceededException

    since   = datetime.now(timezone.utc) - timedelta(days=days_back)
    all_rows: list[dict] = []
    total_repos = len(TARGET_REPOS)

    for repo_idx, (full_name, department) in enumerate(TARGET_REPOS.items(), 1):
        logger.info(
            f"[{repo_idx:02d}/{total_repos}] Fetching: {full_name}  "
            f"(dept={department})"
        )
        if progress_cb:
            progress_cb(full_name, repo_idx, total_repos)

        repo_rows: list[dict] = []
        try:
            repo  = g.get_repo(full_name)
            pulls = repo.get_pulls(state="closed", sort="updated", direction="desc")

            for pr in pulls:
                # Stop if we have enough PRs for this repo
                if len(repo_rows) >= max_per_repo:
                    break

                # Stop scanning if PR is older than our window
                # (pulls are sorted by updated desc, so this is safe)
                if pr.created_at < since:
                    break

                # Only merged PRs (closed ≠ merged)
                if not pr.merged_at:
                    continue

                cycle_hours = (
                    (pr.merged_at - pr.created_at).total_seconds() / 3600
                )
                gh_user = pr.user.login if pr.user else "unknown"
                uid     = (username_map or {}).get(gh_user)

                repo_rows.append({
                    "pr_id":            f"{repo.name}#{pr.number}",
                    "user_id":          uid,
                    "github_username":  gh_user,
                    "repo_name":        repo.name,
                    "repo_full_name":   full_name,
                    "department":       department,
                    "pr_title":         (pr.title or "")[:200],
                    "pr_state":         "merged",
                    "created_at":       pr.created_at.isoformat(),
                    "merged_at":        pr.merged_at.isoformat(),
                    "cycle_time_hours": round(cycle_hours, 2),
                    "lines_added":      pr.additions   or 0,
                    "lines_removed":    pr.deletions   or 0,
                    "review_count":     pr.review_comments or 0,
                    "commit_count":     pr.commits     or 0,
                    "rework_ratio":     round(
                        (pr.deletions or 0) / max((pr.additions or 1), 1), 3
                    ),
                    "period":           _period(pr.merged_at),
                })

                # Gentle throttle every 100 PRs to avoid secondary rate limits
                if len(repo_rows) % 100 == 0:
                    time.sleep(0.5)

            logger.info(
                f"  ✓ {full_name}: {len(repo_rows)} PRs fetched  "
                f"(Before={sum(1 for r in repo_rows if r['period']=='Before')}, "
                f"After={sum(1 for r in repo_rows if r['period']=='After')})"
            )
            all_rows.extend(repo_rows)

        except RateLimitExceededException:
            logger.error(
                "GitHub rate limit hit. "
                "Wait for reset or reduce MAX_PRS_PER_REPO in config.py."
            )
            break
        except GithubException as exc:
            logger.warning(f"  ✗ Skipping {full_name}: {exc.status} {exc.data}")
            continue
        except Exception as exc:
            logger.warning(f"  ✗ Unexpected error on {full_name}: {exc}")
            continue

    if not all_rows:
        logger.warning("No PR data fetched. Check GITHUB_TOKEN and network access.")
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)

    # Numeric coercion
    for col in ["cycle_time_hours", "lines_added", "lines_removed",
                "review_count", "commit_count", "rework_ratio"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["merged_at"]  = pd.to_datetime(df["merged_at"],  errors="coerce")

    logger.info(
        f"GitHub sync complete — "
        f"{len(df):,} total PRs across {df['repo_name'].nunique()} repos  |  "
        f"Before={len(df[df['period']=='Before']):,}  "
        f"After={len(df[df['period']=='After']):,}"
    )
    return df


# ─── Single-repo fetch (for incremental updates) ──────────

def fetch_single_repo(
    full_name:    str,
    max_prs:      int  = MAX_PRS_PER_REPO,
    days_back:    int  = GITHUB_DAYS_BACK,
    username_map: dict = None,
) -> pd.DataFrame:
    """
    Fetch PRs from one specific repo.
    Useful for incremental updates without re-syncing everything.
    full_name format: 'owner/repo'  e.g. 'microsoft/vscode'
    """
    if full_name not in TARGET_REPOS:
        logger.warning(
            f"{full_name} is not in TARGET_REPOS. "
            f"Valid repos: {list(TARGET_REPOS.keys())}"
        )
        return pd.DataFrame()

    dept = TARGET_REPOS[full_name]
    tmp  = {full_name: dept}

    # Temporarily override TARGET_REPOS for one call
    import src.config as cfg
    original = cfg.TARGET_REPOS.copy()
    cfg.TARGET_REPOS = tmp
    df = fetch_all_repos(days_back=days_back, max_per_repo=max_prs,
                         username_map=username_map)
    cfg.TARGET_REPOS = original
    return df


# ─── Rate limit checker ───────────────────────────────────

def check_rate_limit() -> dict:
    """
    Return current rate limit status.
    Useful to call before a large sync.
    """
    g = _get_client()
    if g is None:
        return {"remaining": 0, "limit": 0, "reset": None}
    rl = g.get_rate_limit()
    return {
        "remaining": rl.core.remaining,
        "limit":     rl.core.limit,
        "reset":     rl.core.reset.isoformat(),
        "pct_used":  round((1 - rl.core.remaining / rl.core.limit) * 100, 1),
    }


# ─── Contributor map builder ──────────────────────────────

def build_username_map_from_db() -> dict:
    """
    Load {github_username: user_id} from users_master in DB.
    Pass to fetch_all_repos() for internal user linking.
    """
    if not DB_PATH.exists():
        return {}
    try:
        conn = sqlite3.connect(DB_PATH)
        df   = pd.read_sql(
            "SELECT user_id, github_username FROM users_master "
            "WHERE github_username IS NOT NULL AND github_username != ''",
            conn,
        )
        conn.close()
        return dict(zip(df["github_username"], df["user_id"]))
    except Exception as exc:
        logger.warning(f"Could not build username map: {exc}")
        return {}


# ─── Department summary helper ────────────────────────────

def dept_summary_from_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-department PR stats from a fetched DataFrame.
    Useful for quick sanity check after sync.
    """
    if df.empty:
        return pd.DataFrame()
    return (
        df.groupby(["department", "period"])
        .agg(
            pr_count=("pr_id", "count"),
            avg_cycle_hrs=("cycle_time_hours", "mean"),
            avg_rework=("rework_ratio", "mean"),
            unique_contributors=("github_username", "nunique"),
        )
        .round(2)
        .reset_index()
        .sort_values(["department", "period"])
    )
