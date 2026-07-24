# ADR Template — Architecture Decision Record

Use this template to record any significant architecture decision. Fill in all sections truthfully; if a section is not applicable, write "N/A".

---

```markdown
# ADR-NNN: Title

## Status

[Proposed | Accepted | Deprecated | Superseded]

## Context

Describe the problem, constraint, or situation that requires a decision.

- Why is this decision needed?
- What forces are at play? (Technical, business, operational, etc.)
- What are the constraints? (Time, budget, scale, team skill, etc.)

## Decision

State the decision clearly.

"We will use [technology / approach / pattern] because [reason]."

## Consequences

List the trade-offs, impacts, and follow-up work this decision introduces.

- Positive: what becomes easier or possible
- Negative: what becomes harder or is sacrificed
- Neutral: what changes but isn't better or worse
- Migration: what needs to change if this decision is reversed

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Option A | [Reason] |
| Option B | [Reason] |

## Compliance

How to verify this decision is followed in code and reviews.

- [ ] Automated check (e.g., CI rule, linter)
- [ ] Manual review check
- [ ] Documentation reference

## Notes

- Related ADRs: [ADR-NNN]
- References: [links to docs, issues, RFCs]
```