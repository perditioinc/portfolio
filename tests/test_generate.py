"""Tests for portfolio generate.py."""

from __future__ import annotations

import json

import httpx
import respx

from generate import (
    _extract_md_metrics,
    _fetch_metrics_json,
    _get_metrics,
    _graphql_repos,
    _load_projects_config,
    _resolve_field,
    build_readme,
    format_last_updated,
)
from tests.conftest import make_gql_node

GRAPHQL_URL = "https://api.github.com/graphql"
RAW_BASE = "https://raw.githubusercontent.com"


# ── _load_projects_config ─────────────────────────────────────────────────────


def test_load_projects_config(tmp_path, monkeypatch):
    """Loads projects.json correctly."""
    cfg = {"myrepo": {"status": "active"}}
    p = tmp_path / "projects.json"
    p.write_text(json.dumps(cfg))
    monkeypatch.chdir(tmp_path)
    result = _load_projects_config()
    assert result["myrepo"]["status"] == "active"


def test_load_projects_config_missing(tmp_path, monkeypatch):
    """Returns empty dict when projects.json is missing."""
    monkeypatch.chdir(tmp_path)
    result = _load_projects_config()
    assert result == {}


# ── _resolve_field ────────────────────────────────────────────────────────────


def test_resolve_field_simple():
    """Resolves a top-level key."""
    assert _resolve_field({"total": 5}, "total") == 5


def test_resolve_field_nested():
    """Resolves a nested dotted path."""
    assert _resolve_field({"meta": {"total": 805}}, "meta.total") == 805


def test_resolve_field_missing():
    """Returns None for missing paths."""
    assert _resolve_field({}, "meta.total") is None


# ── _extract_md_metrics ───────────────────────────────────────────────────────


def test_extract_md_metrics_finds_field():
    """Parses a metric line from markdown."""
    text = "- duration_seconds: 68\n- repos_checked: 805"
    result = _extract_md_metrics(text, ["duration_seconds", "repos_checked"])
    assert result["duration_seconds"] == "68"
    assert result["repos_checked"] == "805"


def test_extract_md_metrics_missing_field():
    """Returns empty dict when field is not present."""
    result = _extract_md_metrics("no metrics here", ["duration_seconds"])
    assert result == {}


# ── format_last_updated ──────────────────────────────────────────────────────


def test_format_last_updated_iso():
    """Formats ISO timestamp as unambiguous date."""
    result = format_last_updated("2026-03-17T05:00:00Z")
    assert result == "Mar 17, 2026"


def test_format_last_updated_none():
    """Returns dash for empty input."""
    assert format_last_updated("") == "—"
    assert format_last_updated(None) == "—"


def test_format_last_updated_future():
    """Returns 'recently' for future dates."""
    result = format_last_updated("2099-12-31T00:00:00Z")
    assert result == "recently"


# ── build_readme ──────────────────────────────────────────────────────────────


def test_build_readme_has_header():
    """README contains the author header."""
    readme = build_readme({}, [], "Mar 17, 2026 05:00 UTC")
    assert "Kim Loza" in readme


def test_build_readme_has_suite_structure():
    """README with suite data contains suite headers."""
    node = make_gql_node("reporium", stars=100)
    cfg = {"suite": "Reporium", "group": "Core Platform", "order": 1}
    suite_groups = {"Reporium": {"Core Platform": [(node, cfg, None)]}}
    readme = build_readme(suite_groups, [], "Mar 17, 2026")
    assert "## Reporium Suite" in readme
    assert "### Core Platform" in readme
    assert "reporium" in readme


def test_build_readme_other_repos():
    """README includes Other Projects section."""
    node = make_gql_node("my-tool", stars=50)
    readme = build_readme({}, [(node, {}, None)], "Mar 17, 2026")
    assert "## Other Projects" in readme
    assert "my-tool" in readme


def test_build_readme_footer():
    """README includes footer with date disclaimer."""
    readme = build_readme({}, [], "Mar 17, 2026")
    assert "Last Updated reflects" in readme


# ── _graphql_repos (mocked) ───────────────────────────────────────────────────


@respx.mock
async def test_graphql_repos_returns_non_forks():
    """Fetches repos and returns raw nodes."""
    nodes = [make_gql_node("reporium"), make_gql_node("forksync")]
    payload = {"data": {"user": {"repositories": {"nodes": nodes}}}}
    respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=payload))

    result = await _graphql_repos("test-token", "testuser")
    assert len(result) == 2


# ── _fetch_metrics_json ───────────────────────────────────────────────────────


@respx.mock
async def test_fetch_metrics_json_success():
    """Returns parsed dict on 200."""
    url = f"{RAW_BASE}/perditioinc/reporium-db/main/data/index.json"
    respx.get(url).mock(return_value=httpx.Response(200, json={"meta": {"total": 5}}))
    result = await _fetch_metrics_json("tok", "perditioinc/reporium-db", "data/index.json")
    assert result == {"meta": {"total": 5}}


@respx.mock
async def test_fetch_metrics_json_returns_none_on_error():
    """Returns None when source is unavailable."""
    url = f"{RAW_BASE}/perditioinc/reporium-db/main/data/index.json"
    respx.get(url).mock(return_value=httpx.Response(404))
    result = await _fetch_metrics_json("tok", "perditioinc/reporium-db", "data/index.json")
    assert result is None


# ── _get_metrics ─────────────────────────────────────────────────────────────


@respx.mock
async def test_get_metrics_json_source():
    """Resolves dotted field paths and formats as label: value."""
    url = f"{RAW_BASE}/perditioinc/reporium-db/main/data/index.json"
    respx.get(url).mock(return_value=httpx.Response(200, json={"meta": {"total": 805}}))
    cfg = {
        "metrics_source": "perditioinc/reporium-db:data/index.json",
        "metrics_fields": ["meta.total as repos_tracked"],
    }
    result = await _get_metrics("tok", cfg)
    assert result is not None
    assert "repos_tracked" in result
    assert "805" in result


async def test_get_metrics_no_source():
    """Returns None when config has no metrics_source."""
    result = await _get_metrics("tok", {})
    assert result is None
