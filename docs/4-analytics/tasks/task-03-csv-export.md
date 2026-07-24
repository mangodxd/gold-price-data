# Task: Export Daily CSVs and Commit to Repo

## Description

Export all three data tables to CSV files named by Vietnam date, then commit and push the files to the repository.

## File Naming

| File | Source | Naming Pattern |
|---|---|---|
| Domestic gold prices | gold_prices | `gold_prices_YYYY-MM-DD.csv` |
| World gold prices | world_gold_prices | `world_gold_prices_YYYY-MM-DD.csv` |
| Exchange rates | exchange_rates | `exchange_rates_YYYY-MM-DD.csv` |

Date format: Vietnam date (UTC+7). If today is 2026-07-25 00:05 UTC+7, yesterday was 2026-07-24.

## CSV Format

- UTF-8 encoding with BOM
- Comma-separated values
- Header row with column names (snake_case, matches database columns)
- Data rows ordered by recorded_at ASC
- Strings quoted only if they contain commas or newlines
- null/None values written as empty string
- REAL values formatted with appropriate precision (2 decimals for USD prices, 0 decimals for VND)

### Example: gold_prices_2026-07-24.csv

```csv
id,source,product_name,category,purity,buy_price,sell_price,recorded_at,created_at
1,vang.today,SJL1L10,VÀNG MIẾNG,,87000000,88500000,2026-07-24T00:00:00Z,2026-07-24T00:00:05Z
2,vang.today,SJ9999,VÀNG NHẪN,,86500000,88000000,2026-07-24T00:00:00Z,2026-07-24T00:00:05Z
```

### Example: world_gold_prices_2026-07-24.csv

```csv
id,source,spot_usd_oz,per_gram_usd,per_kg_usd,currency,unit,recorded_at,created_at
1,xaus.com,4061.70,130.59,130586.69,USD,troy_oz,2026-07-24T14:50:09.811Z,2026-07-24T14:50:10Z
```

### Example: exchange_rates_2026-07-24.csv

```csv
id,base_currency,target_currency,rate,recorded_at,created_at
1,USD,VND,24350.00,2026-07-24T00:00:00Z,2026-07-24T00:00:05Z
```

## Export Directory

Files are written to `exports/` at the repository root. This directory is gitignored except for the CSV files that are committed.

## Git Operations

After generating all CSVs:

1. `git add exports/*.csv`
2. `git commit -m "chore(export): add daily CSVs for YYYY-MM-DD"`
3. `git push`

Use the GITHUB_TOKEN provided by the Actions runner for authentication.

## Edge Cases

| Scenario | Handling |
|---|---|
| No data for a table | Create file with header row only |
| File already exists (re-run) | Overwrite (same day, same data) |
| Git commit fails | Log ERROR, workflow fails (GHA sends email) |
| One table has data, others empty | Create all 3 files (some may be header-only) |
| API returns no data for entire day | All 3 files are header-only |

## Acceptance Criteria

- [ ] CSVs are valid UTF-8 and parseable by Excel/Google Sheets
- [ ] File dates use Vietnam timezone
- [ ] Empty tables produce header-only files (not missing files)
- [ ] Committed CSVs appear in the repo under exports/
- [ ] git push succeeds using GITHUB_TOKEN