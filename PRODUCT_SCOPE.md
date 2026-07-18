# Prism product scope

Prism is a personal, point-in-time market research workbench. It is designed
to help a researcher form, test, record, and later evaluate a market view
without silently rewriting history or leaking future information into a
decision.

## Product principles

- Research before prediction: every call must be explainable from a sealed
  input snapshot.
- Point-in-time correctness: source availability is checked independently from
  its observation date.
- Honest evaluation: validation, locked holdout, and forward results are kept
  separate.
- Useful without paid data: deterministic demo mode supports the complete
  workflow and is always clearly labelled.
- Durable personal state: watchlists, formula drafts, experiments, predictions,
  and activity survive browser sessions.
- No trade execution: Prism is a research and evaluation tool, not an
  investment adviser or brokerage interface.

## Functional areas and acceptance criteria

### 1. Identity and workspace

- [x] Read the authenticated workspace or ChatGPT user on the server.
- [x] Keep user-owned records isolated by an opaque owner key.
- [x] Allow anonymous visitors to inspect demo data without granting writes.
- [x] Provide clear sign-in and sign-out affordances where supported.

### 2. Research overview

- [x] Show market regime, candidate coverage, forward hit rate, and ledger
  maturity using one consistent data cutoff.
- [x] Show highest-ranked candidates and current symbol detail.
- [x] Show data freshness, mode, and recent research activity.
- [x] Allow a prediction to be sealed from the overview.

### 3. Market scanner

- [x] Search by ticker, company, or sector.
- [x] Filter by horizon, sector, score, confidence, and watchlist membership.
- [x] Sort every quantitative column.
- [x] Provide useful empty states and a one-click reset.
- [x] Export the currently filtered snapshot as CSV with its cutoff metadata.

### 4. Symbol research

- [x] Present price, recent path, score, confidence, signal, and key drivers.
- [x] Compare 10D, 30D, and 90D scores.
- [x] Expose point-in-time metric values and their calculation version.
- [x] Add or remove the symbol from a durable watchlist.
- [x] Seal a prediction with an explicit horizon and formula version.

### 5. Formula lab

- [x] Edit interpretable factor weights within safe bounds.
- [x] Name and save versioned formula drafts.
- [x] Restore the stable default formula.
- [x] Run validation without changing the prediction ledger.
- [x] Show accuracy, baseline delta, spread, IC, drawdown, turnover, deciles,
  and stability warnings.
- [x] Persist experiment inputs and results.

### 6. Backtesting and research discipline

- [x] Use walk-forward validation semantics.
- [x] Keep the final holdout visibly locked.
- [x] Compare against a simple always-up baseline.
- [x] Report cross-sectional ranking quality and risk, not only hit rate.
- [x] Reject source records unavailable at the requested cutoff.

### 7. Prediction ledger

- [x] Append predictions; never update their sealed inputs.
- [x] Store cutoff, formula and metric versions, confidence, expected range,
  input snapshot, owner, creation time, and content hash.
- [x] Filter by horizon, outcome, and symbol.
- [x] Verify the hash chain and report integrity.
- [x] Export the current ledger as JSON Lines.
- [x] Track pending, correct, incorrect, and neutral outcomes.

### 8. Data center

- [x] Show provider configuration and active mode.
- [x] Run deterministic demo synchronization.
- [x] Report pipeline step health, versions, and last activity.
- [x] Document external provider environment variables.
- [x] Surface temporal-integrity guarantees and degraded/error states.

### 9. Durable storage

- [x] Use D1 for watchlists, formula drafts, experiments, predictions, and
  activity.
- [x] Keep schema and generated migrations in source control.
- [x] Initialize local preview storage safely and idempotently.
- [x] Never use browser storage as the source of truth for research records.

### 10. Security and reliability

- [x] Authorize writes on the server.
- [x] Validate symbols, horizons, formula names, filters, and weight ranges.
- [x] Return structured errors without exposing secrets.
- [x] Include loading, retry, empty, read-only, and partial-failure states.
- [x] Preserve availability timestamps and forbid same-close look-ahead.

### 11. Usability and accessibility

- [x] Work on desktop, tablet, and mobile layouts.
- [x] Support keyboard navigation and Cmd/Ctrl-K search.
- [x] Use accessible names, live status messages, visible focus, and reduced
  motion.
- [x] Make downloads real and provide honest operation feedback.

### 12. Engineering delivery

- [x] Keep TypeScript, Python research core, API contracts, and documentation
  aligned.
- [x] Pass lint, unit, API, integration, and production-build checks.
- [x] Provide local setup and operating instructions.
- [ ] Create a clean Git history and publish the validated site.
- [x] Perform a final product review and a second ideation pass.

## Second-pass enhancements

- [x] Add an append-only research journal with thesis, invalidation condition,
  tags, symbol ownership, and durable activity history.
- [x] Add a cross-horizon formula sensitivity matrix so a stable region is
  visible instead of only a single optimized point.
- [x] Add a reproducible workspace bundle export containing data versions,
  watchlist, formulas, experiments, predictions, journal, and activity.
- [x] Prevent a prediction from being sealed against a future data cutoff.

## Explicit non-goals for this release

- Automated order placement or portfolio custody.
- Claims of investment advice or guaranteed performance.
- Unlocking the final holdout repeatedly to tune a formula.
- Shipping paid-provider credentials in the client or repository.
