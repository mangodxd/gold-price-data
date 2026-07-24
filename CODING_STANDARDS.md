# CODING STANDARDS — Python Conventions

## Language & Runtime

- Python 3.12+ only.
- No type-ignored files. Every `.py` file must pass `mypy --strict` (where configured).

## Linting & Formatting

- Use **ruff** for both linting and formatting.
- Run `ruff check src/` and `ruff format --check src/` before every commit.
- Max line length: **100 characters**.

## Type Annotations

- All function signatures **must** have type hints.
- All module-level variables **must** have type hints.
- Use `from __future__ import annotations` at the top of every module for deferred evaluation.
- Prefer `|` over `Optional[]` (e.g. `str | None` not `Optional[str]`).

## Docstrings

- **Google style** for all public functions, methods, and classes.
- Structure: `Args:`, `Returns:`, `Raises:` sections.
- One-line docstrings acceptable for trivial getters/setters.

```python
def compute_ohlc(prices: list[float]) -> dict[str, float]:
    """Compute OHLC from a list of tick prices.

    Args:
        prices: Chronologically ordered list of prices.

    Returns:
        Dict with keys opening, high, low, closing.

    Raises:
        ValueError: If prices is empty.
    """
```

## Imports

Order: **stdlib → third-party → local**, each group separated by a blank line. Within each group, sort alphabetically.

```python
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest

from gold_pipeline.models import GoldPrice
```

## Naming Conventions

| Construct | Convention | Example |
|---|---|---|
| Functions & variables | `snake_case` | `compute_ohlc`, `db_path` |
| Classes | `PascalCase` | `GoldCollector`, `DatabaseRepository` |
| Constants | `UPPER_CASE` | `MAX_RETRIES`, `API_TIMEOUT` |
| Private members | `_leading_underscore` | `_validate_response` |
| Modules | `snake_case` | `collectors.py`, `storage.py` |

## File System

- Use `pathlib.Path` everywhere. Never `os.path`.
- Always use context managers (`with open(...)` / `with db_connection(...)`).

```python
from pathlib import Path

DB_PATH = Path("data") / "gold_pipeline.db"
```

## Error Handling

- Define custom exception classes in `exceptions.py`.
- Never use bare `except:`.
- Use specific exception types (`except httpx.HTTPError:` not `except Exception:`).
- Wrap external API calls with retry logic (max 3, exponential backoff).
- Log errors via the `api_logs` table, never `print()`.

```python
class CollectorError(Exception):
    """Base exception for collector failures."""

class ValidationError(CollectorError):
    """Raised when API response fails validation."""
```

## Testing

- Use **pytest** as the test runner.
- Mirror the `src/` directory structure under `tests/`.
- Use `httpx_mock` (pytest-httpx) for HTTP client mocking.
- Name test files with `test_` prefix: `test_collectors.py`.
- Test files must contain at least one docstring per test describing the scenario.

```
src/
  collectors.py
  models.py
tests/
  test_collectors.py
  test_models.py
```

## Retry Policy

```python
MAX_RETRIES = 3
BASE_DELAY_SECONDS = 1.0
BACKOFF_FACTOR = 2.0
# Retry on: httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError (5xx)
# Do NOT retry on: client errors (4xx except 429)
```

## Database Conventions

- SQLite in WAL mode for concurrent reads during analytics.
- All timestamp columns stored as ISO 8601 UTC text.
- Integer prices stored as VND x 1 (no decimal). World spot as REAL.
- UNIQUE constraints used for idempotent inserts via `INSERT OR IGNORE`.
