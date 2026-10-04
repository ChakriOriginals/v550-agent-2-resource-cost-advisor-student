# Calculation and Readiness Rules

All arithmetic runs through `scripts/cost_engine.py` with `Decimal`. The language model never calculates or reconciles numbers in prose.

## Formulas and rounding

- Labor value = hours × approved hourly rate.
- Cash cost = quantity × approved unit cost.
- PERT expected hours = (O + 4M + P) / 6.
- Base plan uses M for every work package.
- Contingency minimum = sum(E - M) across exactly three uncertainty packages.
- Contingency maximum = sum(P - M) across those same packages.
- Estimates use 0.5-hour steps and have a one-hour minimum.
- PERT expected hours round upward to the next 0.5 hour.
- Aggregate unrounded values before displaying dollars rounded to the nearest whole dollar.
- Facilitator quantity uses half-day increments. Software always charges at least 12 months.

The student selects contingency within the calculated range and gives its holder, phase, and reason. A flat percentage is management reserve and does not satisfy the required contingency.

## Hard readiness blockers

Formal status is NOT YET for an invalid WBS; duplicate or missing identifiers; fewer than three or more than four phases; invalid phase mapping; missing or multiple owners; missing estimates, methods, or evidence; malformed cash quantities; not exactly three uncertainty packages; unordered O/M/P values; contingency outside its range or missing holder, phase, or reason; pre-vote hours over 525; post-vote hours over 65.5; a person above paper capacity in a phase; cash over $35,000; excluded cash; work after June 1; an approved deliverable with no work; unlabeled new work; unreconciled deterministic totals; or missing final explanation.

Calendar pressure, weak evidence, or realistic-capacity concern is advisory unless it also creates a hard blocker. A student may retain an advisory flag only with a recorded reason. Hard blockers cannot be overridden.

Labor and cash remain separate. Cash status is calculated using the fixed unit costs; the obsolete labor-only status is not used.

