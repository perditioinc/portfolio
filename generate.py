"""Generate portfolio README.md from live GitHub data — grouped by suite."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

GITHUB_GRAPHQL = "https://api.github.com/graphql"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com"
REPORIUM_API_URL = os.getenv(
    "REPORIUM_API_URL",
    "https://reporium-api-573778300586.us-central1.run.app",
)
TIMEOUT = 15

REPO_QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(
      first: 100
      ownerAffiliations: OWNER
      isFork: false
      orderBy: {field: STARGAZERS, direction: DESC}
    ) {
      nodes {
        nameWithOwner name description
        stargazerCount forkCount
        primaryLanguage { name }
        pushedAt isPrivate
        issues(states: [OPEN]) { totalCount }
        repositoryTopics(first: 5) { nodes { topic { name } } }
      }
    }
  }
}
"""

# Suite definitions — order matters for README section ordering
SUITE_ORDER = ["Reporium", "Perditio"]

# Group ordering within each suite
GROUP_ORDER = {
    "Reporium": [
        "Core Platform",
        "Automation & Sync",
        "Observability & Health",
        "Documentation & Discovery",
    ],
    "Perditio": ["Shared Tooling"],
}

SUITE_DESCRIPTIONS = {
    "Reporium": (
        "A platform for discovering, tracking, and understanding AI development "
        "tools on GitHub.\n"
        "> [reporium.com](https://reporium.com) · "
        "[API Docs](https://reporium-api-573778300586.us-central1.run.app/docs)"
    ),
    "Perditio": "Shared tooling and infrastructure for Perditio projects.",
}


def _load_projects_config(path: str = "projects.json") -> dict[str, dict]:
    """Load project config from projects.json."""
    try:
        return json.loads(open(path).read())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load %s: %s", path, exc)
        return {}


async def _graphql_repos(token: str, username: str) -> list[dict[str, Any]]:
    """Fetch non-fork repos via GraphQL."""
    headers = {"Authorization": f"bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            GITHUB_GRAPHQL,
            json={"query": REPO_QUERY, "variables": {"login": username}},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
    return data["data"]["user"]["repositories"]["nodes"]


def _resolve_field(data: dict, dotted_path: str) -> Any:
    """Resolve a dotted field path from a nested dict."""
    parts = dotted_path.split(".")
    current: Any = data
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


async def _fetch_metrics_json(token: str, owner_repo: str, file_path: str) -> Optional[dict]:
    """Fetch a JSON file from a GitHub repo."""
    url = f"{GITHUB_RAW_BASE}/{owner_repo}/main/{file_path}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not fetch %s: %s", url, exc)
        return None


async def _fetch_metrics_md(token: str, owner_repo: str, file_path: str) -> Optional[str]:
    """Fetch a markdown file from a GitHub repo."""
    url = f"{GITHUB_RAW_BASE}/{owner_repo}/main/{file_path}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not fetch %s: %s", url, exc)
        return None


def _extract_md_metrics(text: str, fields: list[str]) -> dict[str, Any]:
    """Parse metric values from markdown using regex."""
    result: dict[str, Any] = {}
    for field in fields:
        field_pattern = "[_ ]".join(re.escape(p) for p in field.split("_"))
        pattern = rf"-\s*{field_pattern}[:\s]+([^\n]+)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result[field] = match.group(1).strip()
    return result


async def _fetch_api_metrics(endpoint: str, fields: list[str]) -> Optional[str]:
    """Fetch metrics from the live reporium-api."""
    url = f"{REPORIUM_API_URL}/{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not fetch %s: %s — showing —", url, exc)
        return None

    metric_parts = []
    for field_def in fields:
        if " as " in field_def:
            path, label = field_def.split(" as ", 1)
            label = label.strip()
        else:
            path = field_def
            label = field_def
        val = data.get(path.strip())
        if val is not None:
            if isinstance(val, dict):
                val = len(val)
            metric_parts.append(f"{label}: {val}")
    return " · ".join(metric_parts) if metric_parts else None


async def _get_metrics(token: str, config: dict) -> Optional[str]:
    """Fetch and format metrics for a project from its metrics_source."""
    source = config.get("metrics_source", "")
    fields = config.get("metrics_fields", [])
    if not source or not fields:
        return None

    if source.startswith("api:"):
        endpoint = source.split(":", 1)[1]
        return await _fetch_api_metrics(endpoint, fields)

    parts = source.split(":", 1)
    if len(parts) != 2:
        return None
    owner_repo, file_path = parts

    if file_path.endswith(".json"):
        data = await _fetch_metrics_json(token, owner_repo, file_path)
        if data is None:
            return None
        if isinstance(data, list):
            if not data:
                return None
            data = {"_last_date": data[-1].get("date", "—"), "_entries": len(data)}
        metric_parts = []
        for field_def in fields:
            if " as " in field_def:
                path, label = field_def.split(" as ", 1)
                label = label.strip()
            else:
                path = field_def
                label = field_def.split(".")[-1]
            val = _resolve_field(data, path.strip())
            if val is not None:
                if isinstance(val, dict):
                    val = len(val)
                metric_parts.append(f"{label}: {val}")
        return " · ".join(metric_parts) if metric_parts else None

    if file_path.endswith(".md"):
        text = await _fetch_metrics_md(token, owner_repo, file_path)
        if text is None:
            return None
        extracted = _extract_md_metrics(text, fields)
        return " · ".join(f"{k}: {v}" for k, v in extracted.items()) or None

    return None


def format_last_updated(pushed_at: str) -> str:
    """Format pushed_at date from GitHub API.

    Returns date in unambiguous format: 'Mar 20, 2026'.
    Never returns a date in the future — if pushed_at is after today UTC,
    something is wrong, log a warning and return 'recently'.
    """
    if not pushed_at:
        return "—"
    try:
        dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        today = datetime.now(timezone.utc)
        if dt > today:
            logger.warning("pushed_at %s is in the future — using 'recently'", pushed_at)
            return "recently"
        return dt.strftime("%b %d, %Y")
    except Exception:  # noqa: BLE001
        return "unknown"


def _build_row(
    repo: dict[str, Any],
    config: dict,
    metrics_str: Optional[str],
) -> str:
    """Build a single markdown table row for a project."""
    name = repo["name"]
    owner_name = repo["nameWithOwner"]
    description = repo.get("description") or "—"
    stars = repo["stargazerCount"]
    language = (repo.get("primaryLanguage") or {}).get("name", "—")
    last_updated = format_last_updated(repo.get("pushedAt", ""))
    link = config.get("link", "")
    repo_link = f"[{name}](https://github.com/{owner_name})"

    if link and metrics_str:
        link_cell = f"[link]({link})"
        return f"| {repo_link} | {description} | {stars} | {language} | {last_updated} | {metrics_str} | {link_cell} |"
    if link:
        link_cell = f"[link]({link})"
        return f"| {repo_link} | {description} | {stars} | {language} | {last_updated} | {link_cell} |"
    if metrics_str:
        return f"| {repo_link} | {description} | {stars} | {language} | {last_updated} | {metrics_str} |"
    return f"| {repo_link} | {description} | {stars} | {language} | {last_updated} |"


def _build_group_table(repos_with_config: list[tuple[dict, dict, Optional[str]]], has_metrics: bool, has_link: bool) -> str:
    """Build a markdown table for a group of repos."""
    header_cols = ["Repo", "Description", "Stars", "Language", "Last Updated"]
    if has_metrics:
        header_cols.append("Metrics")
    if has_link:
        header_cols.append("Link")

    header = "| " + " | ".join(header_cols) + " |"
    sep = "|" + "|".join(["------" for _ in header_cols]) + "|"

    rows = [header, sep]
    for repo, cfg, metrics_str in repos_with_config:
        name = repo["name"]
        owner_name = repo["nameWithOwner"]
        description = repo.get("description") or "—"
        stars = repo["stargazerCount"]
        language = (repo.get("primaryLanguage") or {}).get("name", "—")
        last_updated = format_last_updated(repo.get("pushedAt", ""))
        repo_link = f"[{name}](https://github.com/{owner_name})"

        cells = [repo_link, description, str(stars), language, last_updated]
        if has_metrics:
            cells.append(metrics_str or "—")
        if has_link:
            link = cfg.get("link", "")
            cells.append(f"[link]({link})" if link else "—")
        rows.append("| " + " | ".join(cells) + " |")

    return "\n".join(rows)


def build_readme(
    suite_groups: dict[str, dict[str, list[tuple[dict, dict, Optional[str]]]]],
    other_repos: list[tuple[dict, dict, Optional[str]]],
    generated_at: str,
) -> str:
    """Assemble the full README grouped by suite and group."""
    sections: list[str] = []

    # Bio header
    sections.append("""# Kim Loza — AI Product Leader & Systems Builder

<!-- perditio-badges-start -->
[![Tests](https://github.com/perditioinc/portfolio/actions/workflows/test.yml/badge.svg)](https://github.com/perditioinc/portfolio/actions/workflows/test.yml)
[![Nightly](https://github.com/perditioinc/portfolio/actions/workflows/update.yml/badge.svg)](https://github.com/perditioinc/portfolio/actions/workflows/update.yml)
![Last Commit](https://img.shields.io/github/last-commit/perditioinc/portfolio)
![python](https://img.shields.io/badge/python-3.11%2B-3776ab)
![suite](https://img.shields.io/badge/suite-Kim%20Loza-0ea5e9)
<!-- perditio-badges-end -->

AI Product Manager building at the intersection of developer tooling, AI infrastructure, and open source.
Currently building the Reporium platform — a discovery and intelligence layer for AI development tools on GitHub.

[GitHub](https://github.com/perditioinc)""")
    # TODO: add real LinkedIn URL when confirmed — omit from output until then

    # Suite sections
    for suite_name in SUITE_ORDER:
        groups = suite_groups.get(suite_name, {})
        if not groups:
            continue

        desc = SUITE_DESCRIPTIONS.get(suite_name, "")
        sections.append(f"\n## {suite_name} Suite\n\n> {desc}")

        group_names = GROUP_ORDER.get(suite_name, list(groups.keys()))
        for group_name in group_names:
            repos_in_group = groups.get(group_name, [])
            if not repos_in_group:
                continue

            # Determine if this group needs metrics or link columns
            has_metrics = any(m is not None for _, _, m in repos_in_group)
            has_link = any(c.get("link") for _, c, _ in repos_in_group)

            sections.append(f"\n### {group_name}\n")
            sections.append(_build_group_table(repos_in_group, has_metrics, has_link))

    # Other projects section
    if other_repos:
        sections.append("\n## Other Projects\n\n> Public repos not part of a suite.\n")
        has_metrics = any(m is not None for _, _, m in other_repos)
        sections.append(_build_group_table(other_repos, has_metrics, False))

    # Footer
    sections.append(f"""
---
*Last Updated reflects the most recent push including automated nightly workflow runs.*
*Generated at {generated_at} from live GitHub data.*""")

    return "\n".join(sections) + "\n"


async def main() -> None:
    """Fetch live GitHub data and generate portfolio README.md."""
    t0 = time.monotonic()

    token = os.getenv("GH_TOKEN", "")
    username = os.getenv("GH_USERNAME", "")
    if not token:
        raise ValueError("GH_TOKEN is required")
    if not username:
        raise ValueError("GH_USERNAME is required")

    config_map = _load_projects_config()
    nodes = await _graphql_repos(token, username)

    # Filter out private repos (GraphQL shouldn't return them but guard anyway)
    nodes = [n for n in nodes if not n.get("isPrivate")]

    # Build grouped structure: suite → group → list of (repo, config, metrics)
    suite_groups: dict[str, dict[str, list[tuple[dict, dict, Optional[str]]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    other_repos: list[tuple[dict, dict, Optional[str]]] = []

    for repo in nodes:
        name = repo["name"]
        cfg = config_map.get(name, {})
        metrics_str = await _get_metrics(token, cfg) if cfg.get("metrics_source") else None

        suite = cfg.get("suite")
        group = cfg.get("group")

        if suite and group:
            suite_groups[suite][group].append((repo, cfg, metrics_str))
        else:
            other_repos.append((repo, cfg, metrics_str))

    # Sort repos within each group by their order field
    for suite_name in suite_groups:
        for group_name in suite_groups[suite_name]:
            suite_groups[suite_name][group_name].sort(
                key=lambda item: item[1].get("order", 99)
            )

    # Sort other repos by stars descending
    other_repos.sort(key=lambda item: -item[0]["stargazerCount"])

    generated_at = datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")
    readme = build_readme(dict(suite_groups), other_repos, generated_at)

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme)

    elapsed = time.monotonic() - t0
    total_repos = sum(
        len(repos)
        for groups in suite_groups.values()
        for repos in groups.values()
    ) + len(other_repos)
    logger.info("Portfolio README generated in %.2fs - %d projects", elapsed, total_repos)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
