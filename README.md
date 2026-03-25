# Kim Loza — AI Product Leader & Systems Builder

<!-- perditio-badges-start -->
[![Tests](https://github.com/perditioinc/portfolio/actions/workflows/test.yml/badge.svg)](https://github.com/perditioinc/portfolio/actions/workflows/test.yml)
[![Nightly](https://github.com/perditioinc/portfolio/actions/workflows/update.yml/badge.svg)](https://github.com/perditioinc/portfolio/actions/workflows/update.yml)
![Last Commit](https://img.shields.io/github/last-commit/perditioinc/portfolio)
![python](https://img.shields.io/badge/python-3.11%2B-3776ab)
![suite](https://img.shields.io/badge/suite-Kim%20Loza-0ea5e9)
<!-- perditio-badges-end -->

AI Product Manager building at the intersection of developer tooling, AI infrastructure, and open source.
Currently building the Reporium platform — a discovery and intelligence layer for AI development tools on GitHub.

[GitHub](https://github.com/perditioinc)

## Reporium Suite

> A platform for discovering, tracking, and understanding AI development tools on GitHub.
> [reporium.com](https://reporium.com) · [API Docs](https://reporium-api-573778300586.us-central1.run.app/docs)

### Core Platform

| Repo | Description | Stars | Language | Last Updated | Metrics | Link |
|------|------|------|------|------|------|------|
| [reporium](https://github.com/perditioinc/reporium) | Your GitHub repos as a living AI-native knowledge graph library tool - an AI trend intelligence system that speaks to the people who need to understand what developers are building. Your curation, your lens, your industry perspective. Insights compounds, getting smarter every day. | 1 | TypeScript | Mar 25, 2026 | repos_tracked: 1459 | [link](https://reporium.com) |
| [reporium-api](https://github.com/perditioinc/reporium-api) | Backend API for Reporium : read/write access to repository database, designed for public queries and private ingestion updates. Gatekeeper API that talks to the database, handles authorized writes, serves data to clients/frontends. Public-facing, but writes are only authorized. | 1 | Python | Mar 25, 2026 | — | [link](https://reporium-api-573778300586.us-central1.run.app/docs) |
| [reporium-db](https://github.com/perditioinc/reporium-db) | Nightly GitHub metadata sync — powers reporium.com. Supports 100K repos via GraphQL tiers, checkpointing, and partitioned output. | 1 | Python | Mar 24, 2026 | repos_tracked: 1459 | — |
| [reporium-ingestion](https://github.com/perditioinc/reporium-ingestion) | Local data ingestion and analysis scripts for Reporium : fetch, process, and generate embeddings for repositories, communicating with Reporium API. AI-native analysis, embeddings, scraping, tagging. Pushes updates to API. Standalone and private by default. | 1 | Python | Mar 25, 2026 | — | — |

### Automation & Sync

| Repo | Description | Stars | Language | Last Updated | Metrics |
|------|------|------|------|------|------|
| [forksync](https://github.com/perditioinc/forksync) | Tooling ⚙️: Keep your GitHub forks updated automatically. Runs nightly. | 1 | Python | Mar 23, 2026 | duration_seconds: 143 · repos_checked: 792 |

### Infrastructure

| Repo | Description | Stars | Language | Last Updated |
|------|------|------|------|------|
| [reporium-events](https://github.com/perditioinc/reporium-events) | Event schema definitions and Python publisher client for Reporium platform — GCP Pub/Sub | 1 | Python | Mar 23, 2026 |

### Observability & Health

| Repo | Description | Stars | Language | Last Updated |
|------|------|------|------|------|
| [reporium-metrics](https://github.com/perditioinc/reporium-metrics) | Platform performance tracking over time — ASCII trend charts, nightly collection. | 1 | Python | Mar 24, 2026 |
| [reporium-audit](https://github.com/perditioinc/reporium-audit) | Nightly automated audit of the entire Reporium platform — verified health checks | 1 | Python | Mar 24, 2026 |
| [reporium-security](https://github.com/perditioinc/reporium-security) | Automated security scanning for the Reporium suite — grades every public repo A through F nightly | 1 | Python | Mar 21, 2026 |
| [reporium-scoring](https://github.com/perditioinc/reporium-scoring) | Score any GitHub repo 0-100 for the Reporium platform — README quality, activity, community health, CI/CD | 1 | Python | Mar 21, 2026 |

### Documentation & Discovery

| Repo | Description | Stars | Language | Last Updated |
|------|------|------|------|------|
| [reporium-dataset](https://github.com/perditioinc/reporium-dataset) | Public dataset mirror for reporium.com — nightly-updated AI dev tool stats from reporium-db. | 1 | Python | Mar 25, 2026 |
| [reporium-roadmap](https://github.com/perditioinc/reporium-roadmap) | Public product roadmap for reporium.com — auto-updated nightly with live GitHub stats. | 1 | Python | Mar 24, 2026 |
| [reporium-system-design](https://github.com/perditioinc/reporium-system-design) | Architecture decisions, tradeoffs, CAP theorem analysis, and diagrams for the Reporium platform | 1 | Python | Mar 21, 2026 |

## Perditio Suite

> Shared tooling and infrastructure for Perditio projects.

### Shared Tooling

| Repo | Description | Stars | Language | Last Updated |
|------|------|------|------|------|
| [perditio-devkit](https://github.com/perditioinc/perditio-devkit) | Shared tooling for Perditio projects — badges, GitHub client, file utilities | 1 | Python | Mar 23, 2026 |

## Other Projects

> Public repos not part of a suite.

| Repo | Description | Stars | Language | Last Updated |
|------|------|------|------|------|
| [reporium-mcp](https://github.com/perditioinc/reporium-mcp) | MCP server for Reporium — query your AI repo library from Claude | 1 | Python | Mar 24, 2026 |
| [portfolio](https://github.com/perditioinc/portfolio) | Portfolio of AI discovery tools, developer tooling, and automation systems built by Kim Loza | 1 | Python | Mar 24, 2026 |

---
*Last Updated reflects the most recent push including automated nightly workflow runs.*
*Generated at Mar 25, 2026 07:35 UTC from live GitHub data.*
