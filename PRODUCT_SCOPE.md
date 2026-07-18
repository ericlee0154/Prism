# Prism product scope

## Non-negotiable principles

- [x] Local-only market research.
- [x] No order placement, trade execution, or brokerage custody.
- [x] No runtime demo data or market-value fallback.
- [x] Empty or failed sources remain visibly empty or failed.
- [x] Provider, observation date, availability cutoff, and metric version are
  visible.
- [x] API credentials remain in the local server process.

## Real market data

- [x] Load `MASSIVE_API_KEY` from the ignored local `.env`.
- [x] Download adjusted Massive daily aggregates for explicitly entered
  symbols.
- [x] Store idempotent OHLCV rows in local DuckDB.
- [x] Preserve observation time, availability time, source, and fetch time.
- [x] Retain complete, partial, and failed synchronization history.
- [x] Stop the active sync batch immediately on provider quota or rate-limit
  responses; do not retry or request remaining symbols.
- [x] Show actual symbol count, row count, date coverage, cutoff, and database
  size.

## Research metrics

- [x] Compute returns, volatility, volume confirmation, moving-average
  distance, and drawdown from stored bars.
- [x] Allow an explicit start and end date for every range analysis.
- [x] Provide synchronized date inputs and a draggable two-ended timeline.
- [x] Record requested coverage separately from actual provider coverage.
- [x] Produce 10-, 30-, and 90-session historical-analog forecasts using only
  earlier outcomes inside the selected interval.
- [x] Refuse to produce forecast values when fewer than ten analog samples
  exist.
- [x] Rank symbols only against the currently stored universe.
- [x] Provide 10-, 30-, and 90-session research scores derived from stored
  metrics.
- [x] Clearly separate research scores from recommendations.
- [x] Refuse to calculate a symbol when insufficient real bars exist.

## Backtesting

- [x] Run walk-forward diagnostics using only prior observations.
- [x] Support 10-, 30-, and 90-session horizons.
- [x] Store every backtest run and its parameters in DuckDB.
- [x] Report observation count, evaluation dates, Spearman IC, top-bottom
  spread, and direction accuracy.
- [x] Return `insufficient_data` instead of fabricated results.
- [ ] Add delisted-symbol membership history before treating results as
  survivorship-bias-safe.
- [ ] Add transaction costs, slippage, taxes, and borrow assumptions.
- [ ] Add train/validation/final-holdout partitions for formula selection.
- [ ] Add metric and formula version comparison across successive universes.

## Events and confidence

- [x] Track source-grounded world events in DuckDB without placeholder content.
- [x] Run AI research through a local ChatGPT-authenticated Codex CLI without
  exposing the Massive credential.
- [x] Store English and Traditional Chinese event research together, with
  per-source language labels and original-page links.
- [x] Separate potential impact magnitude from market breadth and fixed
  sector/theme categories.
- [x] Source and store tracked-symbol classifications, then link events through
  explicit category intersections without guessed exposure.
- [x] Track scheduled earnings and major company announcements inside forecast
  horizons.
- [x] Append sourced post-event outcomes without rewriting historical
  observations.
- [x] Calculate 1-, 5-, and 20-session local market reactions and SPY-relative
  excess returns.
- [x] Stop AI research immediately on quota responses without retrying.
- [x] Store weekly institution-by-institution confidence snapshots.
- [x] Store monthly long-term company confidence with separate market,
  institution, and brand components.
- [x] Preserve null components and explicit coverage instead of neutral fills.
- [ ] Add a local scheduler for weekly, monthly, due-event, and reaction refresh.
- [ ] Add a licensed structured analyst-ratings adapter as an optional source.
- [ ] Add point-in-time consensus revisions and earnings-surprise normalization.

## Portfolio data

- [ ] Add local CSV import for Robinhood, Fidelity, and E*TRADE.
- [ ] Normalize holdings, cash, balances, and cost basis without brokerage
  trading permissions.
- [ ] Compare portfolio exposure with stored research metrics.

## Internationalization

- [x] Support Traditional Chinese and English throughout the local Web UI.
- [x] Format dates according to the selected language.
- [x] Provide English and Traditional Chinese operating documentation.

## Explicit non-goals

- Automated or assisted order placement.
- Broker username/password storage.
- Claims of investment advice or guaranteed performance.
- Hidden fallback data of any kind.
