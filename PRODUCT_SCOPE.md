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

- [x] Compute versioned raw price metrics for return, realized and downside
  volatility, volatility expansion, volume behavior, trend path, moving-average
  distance, range position, drawdown, liquidity, SPY beta, and beta-adjusted
  return.
- [x] Publish formula, inputs, trading-session window, price basis, minimum
  observations, `ddof`, cutoff rule, and null policy from the same registry the
  calculator executes.
- [x] Keep insufficient inputs and contract-declared undefined metrics null;
  never inject zero, a neutral rank, or demo fallback for missing data.
- [x] Allow an explicit start and end date for every range analysis.
- [x] Provide synchronized date inputs and a draggable two-ended timeline.
- [x] Recalculate automatically after range changes and shift a fixed-width
  interval earlier or later by a configurable number of days.
- [x] Record requested coverage separately from actual provider coverage.
- [x] Produce 10-, 30-, and 90-session historical-analog forecasts using only
  earlier outcomes inside the selected interval.
- [x] Report 10%, 50%, and 90% forecast returns and price levels.
- [x] Attach realized target prices and ±5-session context only inside forecast
  validation, without leaking post-range bars into metrics or analogs.
- [x] Refuse to produce forecast values when fewer than ten analog samples
  exist.
- [x] Provide an optional single-symbol 3D forecast-history surface with target
  time, source (actual/P10/P50/P90), and price axes.
- [x] Rank symbols only at one common as-of session and availability cutoff
  against the exact currently stored universe.
- [x] Store the scanner universe definition, symbol-list hash,
  eligible/excluded symbols, and per-horizon score coverage.
- [x] Store the backtest requested-universe hash, eligibility counts, coverage,
  and exclusion reasons.
- [x] Report tie-aware cross-sectional metric percentiles only when at least
  three comparable symbols exist.
- [x] Report historical metric percentiles against strictly earlier
  point-in-time observations, with a 60-observation minimum and no neutral
  fallback.
- [x] Use one versioned cross-sectional scoring implementation for both the
  scanner and walk-forward evaluation.
- [x] Keep 10-, 30-, and 90-session alpha ranks separate from observed-price
  risk ranks.
- [x] Use equal-weight factor buckets so correlated raw metrics inside one
  bucket do not silently receive independent weights.
- [x] Use beta-adjusted SPY-relative return for the market-adjusted alpha
  bucket; retain absolute returns as context rather than double-counting them.
- [x] Clearly separate research scores from recommendations.
- [x] Refuse to calculate a symbol when insufficient real bars exist.
- [ ] Add audited point-in-time sector classifications and sector-benchmark
  history before introducing sector-relative return.
- [ ] Add a dividend-aware total-return source before interpreting the
  split-adjusted price metrics as shareholder total return.
- [ ] Add AI formula/weight exploration only behind a trial registry,
  validation set, and untouched final holdout; AI event research must not
  mutate production formulas.

## Backtesting

- [x] Rebuild the production raw metrics and cross-sectional scorer at each
  historical point-in-time cutoff using only then-available observations.
- [x] Support 10-, 30-, and 90-session horizons.
- [x] Store every backtest run and its parameters in DuckDB.
- [x] Use next-session open to horizon close, minus the aligned SPY return, as
  the primary label while retaining close-to-close return as a diagnostic.
- [x] Report observation count, eligible evaluation dates, mean/median and
  positive-date Spearman IC, SPY-excess top-bottom spread, and direction
  accuracy against its majority baseline.
- [x] Report future maximum drawdown/gain and risk-score IC against forward
  realized volatility and drawdown severity.
- [x] Report alpha-factor ablation and cross-factor correlation diagnostics.
- [x] Keep sealed-prediction confidence null until forward calibration exists;
  preserve rank extremity only as explicitly labeled context.
- [x] Warn that overlapping forward windows are not independent observations.
- [x] Disclose that split-adjusted price returns exclude dividends and that
  current stored-universe tests are not survivorship-bias-safe.
- [x] Return `insufficient_data` instead of fabricated results.
- [ ] Add delisted-symbol membership history before treating results as
  survivorship-bias-safe.
- [ ] Add transaction costs, slippage, taxes, and borrow assumptions.
- [ ] Add train/validation/final-holdout partitions for formula selection.
- [ ] Add metric and formula version comparison across successive universes.
- [ ] Add non-overlapping evaluation or HAC/block-bootstrap uncertainty
  estimates before interpreting observation count as effective sample size.

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
