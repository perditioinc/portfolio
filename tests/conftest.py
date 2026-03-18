"""Shared fixtures for portfolio tests."""

from __future__ import annotations

import pytest


def make_gql_node(
    name: str = "my-repo",
    owner: str = "testuser",
    stars: int = 50,
    description: str = "A project",
    language: str = "Python",
    pushed_at: str = "2026-03-16T10:00:00Z",
    is_fork: bool = False,
) -> dict:
    """Build a minimal GraphQL repository node."""
    return {
        "nameWithOwner": f"{owner}/{name}",
        "name": name,
        "description": description,
        "stargazerCount": stars,
        "forkCount": 0,
        "primaryLanguage": {"name": language} if language else None,
        "pushedAt": pushed_at,
        "issues": {"totalCount": 0},
        "repositoryTopics": {"nodes": []},
    }


@pytest.fixture
def sample_nodes() -> list[dict]:
    """Three sample repos with varying star counts."""
    return [
        make_gql_node("reporium", stars=100, description="AI tool discovery"),
        make_gql_node("forksync", stars=50, description="Fork sync tool"),
        make_gql_node("my-fork", stars=5, is_fork=True),
    ]
