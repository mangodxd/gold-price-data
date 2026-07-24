<div align="center">
  <img src="https://img.shields.io/badge/python-3.12%2B-blue?style=flat&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/github/actions/workflow/status/mangodxd/gold-price-data/.github/workflows/ci.yml?branch=master&label=CI&logo=github&style=flat" alt="CI">
  <img src="https://img.shields.io/badge/coverage-90%25-brightgreen?style=flat" alt="Coverage">
  <img src="https://img.shields.io/badge/license-MIT-yellow?style=flat" alt="License">
</div>

<h1 align="center">🥇 Gold Market Data Pipeline</h1>

<p align="center">
  Automated ETL pipeline collecting Vietnamese gold prices, XAU/USD spot, and VND/USD FX rates<br>
  every <strong>5 minutes</strong>. Runs entirely on <strong>GitHub Actions free tier</strong>.
  <br><br>
  <a href="#-architecture">Architecture</a> ·
  <a href="#-scheduling">Schedule</a> ·
  <a href="#-quick-start">Quick Start</a> ·
  <a href="#-project-structure">Structure</a> ·
  <a href="#-tech-stack">Tech Stack</a>
</p>

---

## 📡 Data Sources

| Source | Data | Frequency |
|---|---|---|
| [vang.today](https://www.vang.today) | Domestic Vietnamese gold prices — 11 brands (SJC, DOJI, PNJ, etc.) | Every 5 min |
| [xaus.com](https://xaus.com) | World gold XAU/USD spot price (USD/oz) | Every 5 min |
| [exchangerate.fun](https://exchangerate.fun) | VND/USD exchange rate | Every 5 min |

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────┐
│  GitHub Actions (cron)                                   │
│  ┌──────────────────────┐  ┌────────────────────────┐   │
│  │  collect.yml         │  │  analytics.yml         │   │
│  │  every 5 min         │  │  daily 00:05 UTC+7     │   │
│  └──────────┬───────────┘  └───────────┬────────────┘   │
└─────────────┼──────────────────────────┼────────────────┘
              │                          │
              ▼                          ▼
┌─────────────────────────┐  ┌─────────────────────────┐
│  main.py collect mode   │  │  main.py analytics mode │
│                         │  │                         │
│  asyncio.gather(        │  │  ohlc.run_analytics()   │
│    DomesticCollector,   │  │  → OHLC + StdDev        │
│    WorldCollector,      │  │  → CSV export (3 files) │
│    FXCollector          │  │  → git commit & push    │
│  )                      │  │                         │
│  → Pipeline (stale      │  └─────────────────────────┘
│    detection + insert)  │
│  → SQLite               │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│  SQLite Database (6 tables)                             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │ gold_prices  │ │ world_gold_  │ │ exchange_    │   │
│  │              │ │ prices       │ │ rates        │   │
│  ├──────────────┤ ├──────────────┤ ├──────────────┤   │
│  │gold_daily_   │ │world_gold_   │ │ api_logs     │   │
│  │summary       │ │daily_summary │ │              │   │
│  └──────────────┘ └──────────────┘ └──────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Key Features

- **⚡ Parallel collection** — 3 APIs fetched simultaneously via `asyncio.gather`
- **🔄 Retry with backoff** — Timeout, network error, 429, and 5xx retried up to 3× (1s → 2s → 4s)
- **🔍 Stale detection** — Skips insert when prices unchanged (domestic: buy+sell, world: spot, FX: rate)
- **🧩 Partial failure tolerance** — One API down doesn't block others
- **📊 Idempotent inserts** — UNIQUE constraints prevent duplicates
- **📈 Daily OHLC analytics** — Opening, high, low, closing, volatility, population stddev, tick count
- **📄 CSV export** — 3 daily files with UTF-8 BOM, committed to repo

## ⏰ Scheduling

| Workflow | Cron | Description |
|---|---|---|
| **collect.yml** | `*/5 * * * *` | Every 5 minutes, 24/7 |
| **analytics.yml** | `5 17 * * *` | Daily at 00:05 UTC+7 |
| **ci.yml** | Push / PR to `master` | Lint (ruff) + test (pytest) |

- ~288 collection runs/day
- ~1 analytics run/day
- ~26,000 API calls/month across all collectors (3 APIs × 288 runs/day × 30 days)
- Entirely GitHub Actions free tier (no server, no cost)

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/mangodxd/gold-price-data.git
cd gold-price-data

# Install
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Run collection (uses in-memory SQLite for testing)
PYTHONPATH=. python src/main.py

# Run analytics + CSV export
PYTHONPATH=. python src/main.py analytics

# Run tests
pytest tests/ -v
```

## 📁 Project Structure

```
├── .github/workflows/
│   ├── collect.yml          # Every 5 min collection
│   ├── analytics.yml        # Daily OHLC + CSV export
│   └── ci.yml               # Lint + test on push
├── src/
│   ├── collectors/          # 3 async HTTP collectors
│   │   ├── base.py          # BaseCollector + retry logic
│   │   ├── domestic.py      # vang.today API
│   │   ├── world.py         # xaus.com API
│   │   └── fx.py            # exchangerate.fun API
│   ├── parsers/             # Response parsers per API
│   ├── storage/
│   │   ├── connection.py    # SQLite engine (WAL mode)
│   │   ├── repository.py    # Generic CRUD + stale detection
│   │   └── pipeline.py      # Collector → DB orchestration
│   ├── analytics/
│   │   └── ohlc.py          # OHLC + StdDev computation
│   ├── export/
│   │   └── csv_writer.py    # Daily CSV export
│   ├── models.py            # SQLAlchemy ORM (6 tables)
│   ├── exceptions.py        # Custom exception hierarchy
│   └── main.py              # Orchestrator entry point
├── tests/                   # 109 tests, 90% coverage
├── docs/                    # Architecture docs
├── exports/                 # Daily CSV exports
├── requirements.txt
└── pyproject.toml
```

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.12+ |
| HTTP | `httpx` (async) |
| Database | SQLite via SQLAlchemy |
| Scheduling | GitHub Actions cron |
| Testing | `pytest` + `pytest-httpx` + `pytest-cov` |
| Linting | `ruff` |
| Analytics | Population stddev, OHLC |

## 📊 Data Flow Per Run

```
Collectors ──► Pipeline ──► Repository ──► SQLite
    │              │              │
    │         Stale check    UNIQUE constraint
    │         API logging    INSERT OR IGNORE
    │
    └─► 3 parallel HTTP calls
        Domestic: ~11 products (SJC, DOJI, PNJ...)
        World:    XAU/USD spot price
        FX:       VND/USD rate
```

**Partial failure:** If one API is down, the other two still collect and store data. Failed collectors are logged to `api_logs`.

## 📄 License

MIT — free as in free.
