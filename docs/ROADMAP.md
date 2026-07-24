# ROADMAP — Phased Execution Plan

## Phase 1 — Project Initialization

- [ ] Create Python package structure: `src/`, `tests/`, `data/`, `exports/`
- [ ] Write `requirements.txt` with pinned deps: httpx, SQLAlchemy, pytest, pytest-httpx, ruff
- [ ] Create `pyproject.toml` with ruff configuration
- [ ] Create `.gitignore` (DB, pycache, env, export CSVs)
- [ ] Initialize git repo, initial commit
- [ ] Write `CODING_STANDARDS.md`, `GIT_STANDARDS.md`, `AGENTS.md`, `PROJECT_OVERVIEW.md`

## Phase 2 — Database Layer

- [ ] Define SQLAlchemy ORM models for all 6 tables
- [ ] Configure SQLite engine with WAL mode
- [ ] Implement `create_tables()` with idempotent schema creation
- [ ] Define UNIQUE constraints for deduplication
- [ ] Test table creation with in-memory SQLite

## Phase 3 — Domestic Gold Collector

- [ ] Create `collectors/base.py` with abstract `BaseCollector` class
- [ ] Implement `collectors/domestic.py`: GET request to vang.today API
- [ ] Parse JSON response, extract domestic brands (exclude XAUUSD)
- [ ] Validate response shape: product_name, buy_price, sell_price
- [ ] Convert buy/sell prices to INTEGER VND
- [ ] Test with mocked httpx responses

## Phase 4 — World Gold & FX Collectors

- [ ] Implement `collectors/world.py`: GET request to xaus.com API
- [ ] Parse minimal world gold response: spot_usd_oz, currency, unit, recorded_at
- [ ] Implement `collectors/fx.py`: GET request to exchangerate.fun API
- [ ] Parse VND/USD exchange rate
- [ ] Test both collectors with mocked responses

## Phase 5 — Storage Layer

- [ ] Implement `storage/repository.py` with Repository pattern
- [ ] Batch insert methods for each table (INSERT OR IGNORE)
- [ ] Stale detection: compare buy AND sell prices before insert
- [ ] API logging: write success/failure to `api_logs` table
- [ ] Handle first-run empty DB gracefully
- [ ] Test repository operations with SQLite in-memory

## Phase 6 — Orchestration

- [ ] Implement `main.py`: run all 3 collectors in parallel via `asyncio.gather()`
- [ ] Partial failure: continue if one collector fails
- [ ] Retry logic: max 3 retries, exponential backoff (1s → 2s → 4s)
- [ ] Pass collected data to storage layer
- [ ] Log all collector runs to `api_logs`
- [ ] Test end-to-end with mocked APIs

## Phase 7 — GitHub Actions Workflows

- [ ] Create `.github/workflows/collect.yml` — every 5 minutes
  - Checkout, setup Python, pip install, run `python src/main.py`
  - Upload SQLite artifact (90-day retention)
- [ ] Create `.github/workflows/analytics.yml` — 00:05 UTC+7 daily
  - Compute OHLC + StdDev per product
  - Export 3 daily CSVs (Vietnam date)
  - Commit CSVs to repo
- [ ] Configure GHA queue (no cancel-in-progress)
- [ ] Rely on GHA built-in failure notification email

## Phase 8 — Analytics

- [ ] Implement OHLC computation from tick data per product
- [ ] Compute population StdDev
- [ ] Store results in `gold_daily_summary` and `world_gold_daily_summary`
- [ ] Handle empty days (no data collected) gracefully — skip, don't crash
- [ ] Test analytics with known price sequences

## Phase 9 — Testing & CI

- [ ] Write unit tests for all parsers (valid input, missing fields, wrong types)
- [ ] Write unit tests for validation logic
- [ ] Write unit tests for repository (insert, dedup, stale detection)
- [ ] Write unit tests for analytics (OHLC + StdDev)
- [ ] Write integration test with mocked HTTP and in-memory DB
- [ ] Create `.github/workflows/ci.yml` — on push/PR to main
  - ruff check + ruff format --check
  - pytest with coverage
- [ ] Conftest fixtures for shared test helpers

## Phase 10 — Polish

- [ ] Data-quality logging: track null values, outliers, unexpected status codes
- [ ] Add README.md with setup, usage, and architecture summary
- [ ] Verify all GitHub Action workflows end-to-end on a test repo
- [ ] Final code review against CODING_STANDARDS.md
- [ ] Run `ruff check` and `ruff format --check` on entire codebase
- [ ] Final git clean-up and squash
