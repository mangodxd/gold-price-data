# ADR-001: Technology Stack Selection

## Status

Accepted

## Context

The Gold Market Data Pipeline needs a technology stack suitable for a free-tier data engineering portfolio project. Constraints:

- **Zero cost**: No paid services, no cloud credits, no VPS.
- **No long-running process**: GitHub Actions runners are ephemeral (max 6 hours).
- **No external database host**: GHA runners have no persistent storage.
- **Portfolio quality**: Stack should be modern, idiomatic, and demonstrate data engineering best practices.
- **Single developer**: Simple tooling, minimal configuration overhead.

## Decision

We will use the following technology stack:

| Component | Choice | Version |
|---|---|---|
| Language | Python | 3.12+ |
| Async HTTP | httpx | latest |
| Database | SQLite | 3.x (stdlib) |
| ORM | SQLAlchemy | 2.x |
| Scheduling | GitHub Actions cron | N/A |
| CI/CD | GitHub Actions | N/A |
| Linting & Formatting | ruff | latest |
| Testing | pytest + pytest-httpx | latest |
| Dependency Management | pip + requirements.txt | N/A |
| Container | Not used | N/A |

## Consequences

### Positive

- **Zero infrastructure cost**: All tools are free. SQLite is a single file. GHA is free for public repos.
- **No API keys needed**: All three target APIs (vang.today, xaus.com, exchangerate.fun) are free and require no authentication.
- **Modern Python pattern**: asyncio + httpx for parallel I/O, SQLAlchemy 2.x ORM, Pydantic v2 for validation.
- **Single-file database**: SQLite artifact uploads easily to GHA. Simple backup = copy the file.
- **Fast iteration**: pip + requirements.txt has zero build-tool learning curve.
- **Industry standard testing**: pytest is the de facto Python testing framework.

### Negative

- **SQLite limitations**: No JSONB, no concurrent writes, limited ALTER TABLE, no row-level security.
- **No containerization**: Without Docker, environment reproducibility depends on requirements.txt pinning.
- **No migration tool**: Without Alembic, schema changes are manual via SQLAlchemy create_all().
- **GHA ephemerality**: Each run starts from scratch. No long-running in-memory cache. No warm connections.
- **Single file concurrency**: SQLite in WAL mode allows concurrent reads but only one writer. Mitigated by sequential write pattern.

### Neutral

- **APScheduler removed**: Originally planned, but GHA cron replaces it entirely. Main.py becomes a single-run entry point, not a daemon.

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| **PostgreSQL** | Requires a hosted service (Supabase, Neon, AWS RDS). Free tiers exist but add external dependency, network latency, and credential management. Overkill for portfolio project. |
| **DuckDB** | Excellent for analytics but less mature for incremental row-by-row inserts. No ORM support. Good future option for data warehouse phase. |
| **MongoDB** | Document store adds complexity without benefit. Gold price data is structured and relational. |
| **APScheduler** | Requires a long-running process. GHA runners are ephemeral — APScheduler process would terminate after 6 hours. |
| **Poetry / uv** | Adds a build-tool dependency. pip + requirements.txt is universally understood and sufficient for a single-module project. |
| **Docker Compose** | Adds complexity. No services to compose (single Python process + SQLite file). GHA runners support Python directly. |
| **Django / FastAPI** | Web framework overhead for a pipeline with no HTTP API. |
| **Apache Airflow** | Extremely heavy for a 3-collector pipeline. Requires a database backend, scheduler, and web server. GHA cron is equivalent to a simple DAG with one task. |
| **Prefect / Dagster** | Overkill for same reason as Airflow. GHA provides sufficient orchestration. |

## Compliance

- [ ] All dependencies must be pinned in `requirements.txt` with exact versions.
- [ ] No import from non-standard-library without a corresponding entry in `requirements.txt`.
- [ ] ruff configuration in `pyproject.toml` with line length 100.
- [ ] All functions must have type annotations.
- [ ] No `print()` statements — use Python logging module exclusively.

## Notes

- Related ADRs: None yet
- References:
  - httpx: https://www.python-httpx.org/
  - SQLAlchemy 2.x: https://docs.sqlalchemy.org/
  - ruff: https://docs.astral.sh/ruff/
  - GitHub Actions cron: https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule