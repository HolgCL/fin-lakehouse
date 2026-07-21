# AGENTS.md — working agreement for `fin-lakehouse`

This project is run as **agent engineering, not vibe coding**. The human owns the spec, the
contracts, and the correctness oracles; the agent is a fast executor inside those boundaries.
The full spec lives in [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md) — read it before starting
any task. This file is the durable protocol; keep it updated as the working agreement evolves.

## Ground rules

1. **The human owns the spec and the contracts.** Data schemas, function signatures, XBRL tag
   priorities, metric definitions, rule thresholds are decided in the project brief or by the
   human before code is written. On any design fork not covered there (e.g. how to average
   balances for CCC, dbt model granularity), **stop, state 2–3 options with a recommendation,
   and wait for a decision.** Do not resolve architecture by taste.

2. **Plan before code, on every milestone.** Post a short plan — files touched, approach, how it
   will be verified — and wait for approval before implementing. No plan, no code.

3. **Small, reviewable diffs.** One milestone = one coherent change set. Show the diff and stop.
   Never dump many unreviewed files at once. Conventional-commit messages. Every diff should be
   justifiable line by line, as if reviewed by a human like a PR from a junior engineer.

4. **Tests are the spec, and their oracles come from the human — not the agent.** The failure
   mode being engineered against: the agent writing both a metric and its "expected" value from
   the same code path, so the test only proves the code agrees with itself.
   - Expected values in metric tests must come from an independent source: a hand-computed number
     the human provides, or a figure derived by a *different method* than the production code
     (e.g. hand-written arithmetic on raw line items in the test, not a call into the metric
     function under test).
   - For Kraft Heinz (`KHC`) fixtures specifically, ask the human to confirm oracle numbers before
     asserting on them. Any self-generated expected value must be marked
     `# UNVERIFIED — needs human oracle` and flagged for review; it must never sit silently in a
     passing test.

5. **Verification gates are objective, but green ≠ correct.** Before presenting a diff, run
   `ruff`, `mypy`, `pytest`, and (once it exists) `dbt build`. These prove self-consistency, not
   domain correctness — that judgment call belongs to the human at each review gate.

6. **Fail loud, never silent.** A missing XBRL tag is a warning naming the company and year, never
   a silent coercion to 0. Division by zero is a null plus a flag, never a silent number. Every
   assumption made along the way is written into the run log and the PR note.

7. **Context hygiene.** The spec lives in the repo, not in chat memory. Prefer a fresh session per
   milestone that re-reads `docs/PROJECT_BRIEF.md` and this file, over one long drifting thread.

8. **Reversibility.** Every change must be revertable with a single `git revert`. No irreversible
   actions — force-push, history rewrite, deleting `data/` — without explicit approval.

## Self-check before presenting any diff

- Can every line be justified?
- Do the test oracles come from an independent source the human has confirmed?
- Does the pipeline fail loudly on bad input, rather than silently producing a wrong number?
- Can this change be reverted in one command?

If any answer is "no," it is not ready to show.

## Milestone rhythm

Each milestone in `docs/PROJECT_BRIEF.md` §9 follows: **PLAN → approve → small diff → self-verify
→ STOP for human review.** Do not proceed to the next milestone without an explicit go-ahead.

## Verification commands

```bash
make lint   # ruff check + mypy
make test   # pytest
make build  # dbt build (once transform/ has models — milestone 3+)
```

## Milestone log

- **Milestone 0**: repo scaffold, tooling config, CI skeleton, README stub,
  `AGENTS.md`. No pipeline logic yet — `config.py` only, plus placeholder package `__init__.py`
  files under `src/fin_lakehouse/{edgar,bronze,silver,detector}/` establishing the layout from
  brief §8. `ruff`, `mypy`, `pytest` all green on this minimal surface.
- **Milestone 1**: `edgar/client.py` (UA header, retry+backoff+jitter, ~10 req/s rate limit,
  on-disk cache), `edgar/cik.py` (ticker→CIK resolution), `bronze/land.py` (verbatim landing,
  partitioned `cik={cik10}/landed={date}` — see brief §8 note on the "filed" partition being
  ambiguous for a whole-history payload; resolved as ingestion date, human-confirmed).
  `ingest.py` wires these into `make ingest`. Ran a real live pull for KHC (CIK `0001637459`,
  "Kraft Heinz Co") to prove the path end to end and to source `tests/fixtures/*.json` — trimmed
  but real SEC data, not fabricated. All 15 tests run against the fixtures via
  `httpx.MockTransport`, never the live API.
