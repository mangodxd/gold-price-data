# GIT STANDARDS — Branching, Commits & PRs

## Branch Naming

| Prefix | Use Case | Example |
|---|---|---|
| `feature/` | New feature or capability | `feature/domestic-collector` |
| `fix/` | Bug fix | `fix/stale-detection-bug` |
| `chore/` | Tooling, config, deps, CI | `chore/setup-ruff` |
| `docs/` | Documentation only | `docs/add-roadmap` |

Branch names should be kebab-case after the prefix. Keep them under 50 characters.

## Commit Message Format

Use **Conventional Commits** (v1.0):

```
<type>(<scope>): <description>

[optional body]
```

**Types:** `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `style`, `perf`, `ci`

**Scopes:** `collector`, `db`, `analytics`, `export`, `ci`, `config`, `deps`, `docs`

**Examples:**

```
feat(collector): add domestic gold collector with vang.today API
fix(db): handle UNIQUE constraint violation on re-run
chore(ci): add ruff lint step to CI workflow
docs(readme): add setup instructions
```

- First line max **72 characters**.
- Body wraps at **72 characters**.
- Use imperative mood ("add" not "added" / "adds").

## Pull Request Guidelines

- Target branch is always `main`.
- Use **squash merge** — the squashed commit title becomes the merge commit message.
- PR title must follow conventional commit format (same as commit message).
- Ensure all CI checks pass before requesting review.
- Keep PRs focused on a single concern; split large changes into multiple PRs.
- No direct pushes to `main` — all changes must go through a PR.

## Branch Lifecycle

```
main
  └── feature/my-feature    (branched from main)
        └── commits ...     (conventional commits)
              └── PR ── squash merge ──▶ main
                                           └── delete feature branch
```

## Prohibited

- ❌ Direct commits to `main`.
- ❌ Merge commits (use squash or rebase).
- ❌ Force-pushing to shared branches.
- ❌ Committing secrets, tokens, or `.env` files.
- ❌ Committing the SQLite database file (it is an artifact, not source).
- ❌ Committing large binary files (>10 MB).

## .gitignore Essentials

```
# Database
data/*.db
data/*.db-wal
data/*.db-shm

# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/

# Environment
.env
.env.local

# OS
.DS_Store
Thumbs.db

# Export artifacts (keep .gitkeep)
exports/*.csv
```
