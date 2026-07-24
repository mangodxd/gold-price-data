# GitHub Actions — Workflow Specifications

## Overview

Three GitHub Actions workflows orchestrate the pipeline. All run on `ubuntu-latest` with Python 3.12. No secrets or API keys are needed (all target APIs are public).

---

## collect.yml

**Name:** `Gold Collection`

**Trigger:**
- `schedule: - cron: '*/5 * * * *'` (every 5 minutes)
- `workflow_dispatch:` (manual trigger for testing)

**Concurrency:**
```yaml
concurrency:
  group: collect
  cancel-in-progress: false
```
Queue mode — if a run takes longer than 5 minutes, the next run waits. No runs are canceled.

**Steps:**

```yaml
jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run collectors
        run: python src/main.py
        env:
          DATABASE_PATH: data/gold_pipeline.db
          LOG_LEVEL: INFO

      - name: Upload SQLite artifact
        uses: actions/upload-artifact@v4
        with:
          name: gold-pipeline-db
          path: data/gold_pipeline.db
          retention-days: 90
```

**Environment variables:**

| Variable | Value | Description |
|---|---|---|
| `DATABASE_PATH` | `data/gold_pipeline.db` | SQLite file location |
| `LOG_LEVEL` | `INFO` | Python logging level |

**Notes:**
- No secrets needed (all APIs are public)
- SQLite artifact retained for 90 days per GHA free tier policy
- GHA automatically sends failure email to the repo owner (no configuration needed)

---

## analytics.yml

**Name:** `Gold Analytics & Export`

**Trigger:**
- `schedule: - cron: '5 17 * * *'` (17:05 UTC = 00:05 UTC+7 next day)
- `workflow_dispatch:` (manual trigger)

**Steps:**

```yaml
jobs:
  analytics:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Compute daily analytics
        run: python -m src.analytics.ohlc
        env:
          DATABASE_PATH: data/gold_pipeline.db

      - name: Export daily CSVs
        run: python -m src.export.csv_writer
        env:
          DATABASE_PATH: data/gold_pipeline.db

      - name: Commit CSVs to repo
        run: |
          git config user.name "gold-pipeline-bot"
          git config user.email "bot@gold-pipeline.dev"
          git add exports/*.csv
          git diff --staged --quiet || git commit -m "chore(export): add daily CSVs for $(date -u -d '+7 hours' '+%Y-%m-%d')"
          git push
```

**Notes:**
- Uses `GITHUB_TOKEN` for git push (automatically provided)
- Git commit only happens if there are changes (`git diff --staged --quiet` check)
- Date in commit message is Vietnam date

---

## ci.yml

**Name:** `CI`

**Trigger:**
- `push: branches: [main]`
- `pull_request: branches: [main]`

**Steps:**

```yaml
jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Lint with ruff
        run: ruff check src/

      - name: Check formatting with ruff
        run: ruff format --check src/

      - name: Run tests
        run: pytest tests/ -v
```

**Notes:**
- Runs on every push and pull request to main
- Fails if linting, formatting, or any test fails
- No secrets or environment variables needed

---

## Timing Notes

- GitHub Actions cron has approximately 1-minute precision. A `*/5 * * * *` schedule may trigger at :02, :07, :12, etc. rather than exactly :00, :05, :10.
- The 5-minute interval is sufficient for gold prices (which also update every 5 minutes according to vang.today).
- If a run takes longer than 5 minutes (unlikely — collectors are sub-second), the next run queues and waits.
- The midnight analytics workflow uses `5 17 * * *` (17:05 UTC) which is 00:05 UTC+7, ensuring the previous day's data is complete.