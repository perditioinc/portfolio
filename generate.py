"""Generate portfolio README.md from live GitHub data."""

from __future__ import annotations

import json
import logging
import os
import re
import time
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
REPORIUM_API_URL = "https://reporium-api-573778300586.us-central1.run.app"
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
        pushedAt
        issues(states: [OPEN]) { totalCount }
        repositoryTopics(first: 5) { nodes { topic { name } } }
      }
    }
  }
}
"""


def _load_projects_config(path: str = "projects.json") -> dict[str, dict]:
    """Load override config from projects.json.

    Args:
        path: Path to the projects.json file.

    Returns:
        Mapping of repo name → config dict.
    """
    try:
        return json.loads(open(path).read())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load %s: %s", path, exc)
        return {}


async def _graphql_repos(token: str, username: str) -> list[dict[str, Any]]:
    """Fetch non-fork repos for a user via GraphQL.

    Args:
        token: GitHub personal access token.
        username: GitHub username or org.

    Returns:
        List of raw GraphQL repo node dicts.
    """
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


async def _fetch_metrics_json(token: str, owner_repo: str, file_path: str) -> Optional[dict]:
    """Fetch a JSON metrics file from a GitHub repo via raw URL.

    Args:
        token: GitHub personal access token.
        owner_repo: e.g. 'perditioinc/reporium-db'.
        file_path: e.g. 'data/index.json'.

    Returns:
        Parsed dict or None on failure.
    """
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
    """Fetch a markdown metrics file from a GitHub repo via raw URL.

    Args:
        token: GitHub personal access token.
        owner_repo: e.g. 'perditioinc/forksync'.
        file_path: e.g. 'SYNC_REPORT.md'.

    Returns:
        Raw text or None on failure.
    """
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


def _resolve_field(data: dict, dotted_path: str) -> Any:
    """Resolve a dotted field path from a nested dict.

    Args:
        data: The source dict.
        dotted_path: e.g. 'meta.total'.

    Returns:
        The resolved value or None.
    """
    parts = dotted_path.split(".")
    current: Any = data
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _extract_md_metrics(text: str, fields: list[str]) -> dict[str, Any]:
    """Parse metric values from markdown using regex.

    Args:
        text: Raw markdown content.
        fields: List of field names to extract (e.g. ['duration_seconds']).

    Returns:
        Mapping of field name → extracted value (str).
    """
    result: dict[str, Any] = {}
    for field in fields:
        # Match "- field_name: value" where underscores can be spaces or underscores
        field_pattern = "[_ ]".join(re.escape(p) for p in field.split("_"))
        pattern = rf"-\s*{field_pattern}[:\s]+([^\n]+)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result[field] = match.group(1).strip()
    return result


async def _fetch_api_metrics(endpoint: str, fields: list[str]) -> Optional[str]:
    """Fetch metrics from the live reporium-api.

    Args:
        endpoint: API endpoint path e.g. 'stats'.
        fields: List of "field as label" or plain field names.

    Returns:
        Formatted metrics string or None on failure.
    """
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
            # Count dict keys for language_count-style fields
            if isinstance(val, dict):
                val = len(val)
            metric_parts.append(f"{label}: {val}")
    return " · ".join(metric_parts) if metric_parts else None


async def _get_metrics(token: str, config: dict) -> Optional[str]:
    """Fetch and format metrics for a project from its metrics_source.

    Args:
        token: GitHub PAT.
        config: Project config dict (may have metrics_source and metrics_fields).

    Returns:
        Formatted metrics string or None.
    """
    source = config.get("metrics_source", "")
    fields = config.get("metrics_fields", [])
    if not source or not fields:
        return None

    # Handle API-based metrics source: "api:endpoint"
    if source.startswith("api:"):
        endpoint = source.split(":", 1)[1]
        return await _fetch_api_metrics(endpoint, fields)

    # Parse "owner/repo:path/to/file"
    parts = source.split(":", 1)
    if len(parts) != 2:
        return None
    owner_repo, file_path = parts

    if file_path.endswith(".json"):
        data = await _fetch_metrics_json(token, owner_repo, file_path)
        if data is None:
            return None
        # If data is a list (e.g. metrics.json), use last entry
        if isinstance(data, list):
            if not data:
                return None
            data = {"_last_date": data[-1].get("date", "—"), "_entries": len(data)}
        metric_parts = []
        for field_def in fields:
            # Support "field.path as label" syntax
            if " as " in field_def:
                path, label = field_def.split(" as ", 1)
                label = label.strip()
            else:
                path = field_def
                label = field_def.split(".")[-1]
            val = _resolve_field(data, path.strip())
            if val is not None:
                # Count dict keys for dict-type fields (e.g. languages)
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


def _format_date(iso: Optional[str]) -> str:
    """Format an ISO date as a short human-readable date.

    Args:
        iso: ISO-8601 timestamp string or None.

    Returns:
        e.g. '2026-03-17' or '—'.
    """
    if not iso:
        return "—"
    return iso[:10]


def _build_row(
    repo: dict[str, Any],
    config: dict,
    metrics_str: Optional[str],
) -> str:
    """Build a single markdown table row for a project.

    Args:
        repo: Raw GraphQL repo node.
        config: Project config from projects.json.
        metrics_str: Optional formatted metrics string.

    Returns:
        Markdown table row string.
    """
    name = repo["name"]
    owner_name = repo["nameWithOwner"]
    description = repo.get("description") or "—"
    stars = repo["stargazerCount"]
    last_commit = _format_date(repo.get("pushedAt"))
    link = config.get("link", "")
    link_cell = f"[link]({link})" if link else "—"
    metrics_cell = metrics_str or "—"
    repo_link = f"[{name}](https://github.com/{owner_name})"
    return (
        f"| {repo_link} | {description} | {stars} | {last_commit} | {metrics_cell} | {link_cell} |"
    )


def build_readme(rows: list[str], generated_at: str) -> str:
    """Assemble the full README from project rows.

    Args:
        rows: List of markdown table row strings.
        generated_at: ISO-8601 timestamp of generation.

    Returns:
        Complete README.md markdown string.
    """
    table_body = "\n".join(rows)
    return f"""# Kim Loza — AI PM & Builder
<!-- perditio-badges-start -->
[![Tests](https://github.com/perditioinc/portfolio/actions/workflows/test.yml/badge.svg)](https://github.com/perditioinc/portfolio/actions/workflows/test.yml)
[![Nightly](https://github.com/perditioinc/portfolio/actions/workflows/update.yml/badge.svg)](https://github.com/perditioinc/portfolio/actions/workflows/update.yml)
![Last Commit](https://img.shields.io/github/last-commit/perditioinc/portfolio)
![python](https://img.shields.io/badge/python-3.11%2B-3776ab)
![suite](https://img.shields.io/badge/suite-Kim%20Loza-0ea5e9)
<!-- perditio-badges-end -->

> Auto-updated nightly from live GitHub data.

## Projects

| Project | Description | Stars | Last Commit | Metrics | Link |
|---------|-------------|-------|-------------|---------|------|
{table_body}

---
*Generated at {generated_at} from live GitHub data.*
"""


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

    # Sort: active repos first (per projects.json), then by stars
    def _sort_key(n: dict) -> tuple[int, int]:
        cfg = config_map.get(n["name"], {})
        is_active = 0 if cfg.get("status") == "active" else 1
        return (is_active, -n["stargazerCount"])

    nodes.sort(key=_sort_key)

    rows: list[str] = []
    for repo in nodes:
        name = repo["name"]
        cfg = config_map.get(name, {})
        metrics_str = await _get_metrics(token, cfg) if cfg else None
        rows.append(_build_row(repo, cfg, metrics_str))

    generated_at = datetime.now(timezone.utc).isoformat()
    readme = build_readme(rows, generated_at)

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme)

    elapsed = time.monotonic() - t0
    logger.info("Portfolio README generated in %.2fs - %d projects", elapsed, len(rows))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
