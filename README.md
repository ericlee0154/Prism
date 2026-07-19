# Prism

[繁體中文說明](./README.zh-TW.md)

Prism is a local-only, point-in-time market research workbench. It downloads
real adjusted daily stock bars from Massive, stores them in DuckDB, derives
versioned metrics, and runs walk-forward research diagnostics.

Prism does not place trades. It has no order, cancel-order, or brokerage
execution path.

## Data truth policy

- Runtime demo data does not exist.
- An empty database produces an empty UI.
- Provider failures never substitute sample prices, scores, or backtests.
- A Massive HTTP 429 stops the active batch immediately; Prism does not retry
  or request the remaining symbols.
- Previously stored real data remains available and is visibly timestamped.
- Every displayed market value names its provider and availability cutoff.
- Test fixtures exist only inside tests and are never loaded by the application.

## Architecture

```text
React / Vinext UI (local browser)
              |
              +-- same-origin local API route
                         |
                         +-- FastAPI on 127.0.0.1:8000
                         |
                         +-- Massive adjusted daily bars
                         +-- local Codex CLI source-grounded research
                         +-- point-in-time metrics
                         +-- walk-forward backtests
                         +-- event and confidence snapshots
                         +-- local DuckDB
```

The Massive key is read only by FastAPI from the local process environment.
It is never sent to the browser and must not use a `NEXT_PUBLIC_*` name.
AI research uses the locally installed Codex CLI and its cached ChatGPT login.
Prism explicitly pins `gpt-5.6-sol` so research runs do not change when
Codex's recommended model changes. Use `PRISM_CODEX_MODEL` only when
intentionally comparing models.

## Requirements

- Node.js 22.13 or newer
- Python 3.12 or newer
- A Massive API key
- Codex CLI signed in with ChatGPT for event and confidence research

## Setup

```bash
make setup
cp .env.example .env
```

Set the key in the ignored `.env`:

```dotenv
MASSIVE_API_KEY=your-key
PRISM_AI_PROVIDER=codex_cli
PRISM_CODEX_MODEL=gpt-5.6-sol
PRISM_CODEX_TIMEOUT_SECONDS=300
PRISM_DATABASE_PATH=./data/prism.duckdb
```

Check the local AI login once:

```bash
codex login status
```

If needed, run `codex login`. No OpenAI Platform API key is required for the
default AI provider.

Then start both local processes:

```bash
make dev
```

Open the local URL printed by Vinext. In **Data & pipeline**, enter the exact
symbols and date range you want, then synchronize. Prism does not create a
default symbol universe.

## Metrics and scoring

`price-core-v0.2` is a deterministic price-research baseline, not a trained or
calibrated return model. Every raw metric is calculated from split-adjusted
daily OHLCV bars whose observation time and `available_at` are no later than
the declared cutoff. Insufficient history, a missing aligned SPY observation,
or a denominator that the metric contract declares undefined produces `null`.
Mathematically meaningful no-movement results can still be zero where the
catalog explicitly says so; Prism never substitutes zero, a neutral score, or
a demo value for missing data. The catalog exposed in the UI is generated from
the same definitions used by the calculator and records each metric's formula,
inputs, trading-session window, minimum observations, price basis, `ddof`,
cutoff rule, and null/zero-denominator policy.

The v0.2 raw catalog contains:

- close-to-close returns over 5, 20, and 60 sessions;
- annualized realized volatility and downside semivolatility over 20 and 60
  sessions, plus the 20D/60D volatility ratio;
- an inclusive 20-session volume z-score, a current-volume surprise against
  the preceding 20 sessions, and 20-session up/down volume balance;
- distance from MA20 and MA50, 60-session drawdown, 20D and 60D trend
  efficiency, and position in the 60-session closing-price range;
- 20-session median dollar volume as a liquidity diagnostic; and
- 60-session beta to SPY plus 20D and 60D beta-adjusted price returns.

`cross-sectional-alpha-risk-v0.2` is the one scoring implementation used by
both the current scanner and historical walk-forward evaluation. A scanner
snapshot records the exact stored candidate universe, symbol-list hash, common
as-of session, common availability cutoff, eligible and excluded symbols, and
per-horizon score coverage. SPY is a benchmark and is not ranked as a candidate.
At least three complete candidates are required.

For each usable metric, Prism computes a tie-aware cross-sectional midrank
percentile and maps it from 0–100 to -1–1. Alpha and observed price risk are
kept separate:

- The alpha baseline has two equal-weight factor buckets. Market-adjusted
  momentum uses beta-adjusted SPY-relative return. Trend quality averages trend
  efficiency, 60-session range position, and distance from the applicable
  moving average. The 10D/30D models use 20D beta-adjusted return; the 90D model
  uses 60D beta-adjusted return. The 10D model uses 20D trend efficiency and
  MA20, while 30D/90D use MA50 and 90D uses 60D trend efficiency.
- The risk baseline has three equal-weight buckets: realized/downside
  volatility level, 60-session drawdown severity, and 20D/60D volatility
  expansion. The volatility pair shares one bucket so correlated measures do
  not receive two independent weights. Higher risk means higher observed price
  risk; it is not treated as lower expected return.

Every bucket first averages its signed metric ranks, then the bucket weights
are applied. A model is `null` if any required bucket is unavailable. Raw
alpha/risk values remain on -1–1 and receive separate 0–100 cross-sectional
ranks for display; these ranks are relative positions in the stored universe,
not probabilities or confidence calibration.

Sealed v0.2 research predictions therefore use relative-outperformance /
relative-underperformance labels. Their database `confidence` is `null` until
forward calibration exists; rank extremity is retained separately in the
immutable input snapshot and is explicitly not presented as a probability.

The scanner also reports two distinct metric contexts. A cross-sectional
percentile compares symbols at the same snapshot cutoff. A historical
percentile compares the current metric only with strictly earlier point-in-time
values for that symbol, using at most the prior 252 endpoints and requiring at
least 60 usable observations. Neither context is a claim of predictive
validity, and a percentile is left `null` when its comparison set is too small.

## Walk-forward diagnostics

The v0.2 walk-forward engine rebuilds the same raw metrics and the same
cross-sectional alpha/risk scores at each historical evaluation cutoff. It
requires aligned SPY data and at least three candidate symbols, evaluates
10-, 30-, or 90-session horizons at five-session rebalance intervals, and
records the requested-universe hash, eligible counts, coverage, and exclusion
reasons.

The diagnostic close-to-close label remains visible, but the primary research
label is:

```text
(stock close[t+h] / stock open[t+1] - 1)
-
(SPY close[t+h] / SPY open[t+1] - 1)
```

Results include date-level Spearman IC, median and positive-IC summaries,
top-minus-bottom SPY-excess spread, directional accuracy versus its majority
baseline, forward maximum drawdown/gain, risk IC against forward realized
volatility and drawdown severity, factor ablation, and factor-correlation
diagnostics. These are diagnostics for rejecting or revising a formula, not
evidence that the baseline is profitable.

Important limits remain: forward windows overlap and therefore are not
independent observations; the universe consists of symbols currently stored
in DuckDB and is not yet protected against survivorship bias; returns use
split-adjusted prices and exclude dividends; and results exclude fees,
slippage, taxes, borrow costs, and market-impact assumptions. Point-in-time
sector-relative returns, total-return data, and AI-driven formula or weight
optimization are deliberately deferred until their data lineage and
out-of-sample validation can be made auditable. AI event research does not
change the v0.2 formulas.

The **Range metrics** screen provides synchronized date inputs and a draggable
two-ended timeline. Any symbol or range change recalculates automatically, and
the complete interval can be shifted earlier or later by a chosen number of
days for continuity checks. It calculates the v0.2 point-in-time raw metric
snapshot at the chosen end date and builds 10-, 30-, and 90-session historical-analog
forecasts using only earlier outcomes inside the selected interval. If fewer
than ten eligible analogs exist, no forecast values are produced.

Completed forecasts expose 10%, 50%, and 90% return and price levels. When
stored bars exist after a historical analysis cutoff, only the forecast
validation section reads them and displays the realized target plus the five
sessions before and after it. Those future bars never enter the metric
snapshot, selected-range series, or analog generation.

Range metrics also contains an optional single-symbol 3D forecast history
view. Its axes are target time, data source (actual, P10, P50, and P90), and
price. For every target, the 10D, 30D, or 90D forecast is rebuilt from a prefix
ending exactly that many trading sessions earlier. At least 30 completed
analogs and five validation targets are required, which means selected ranges
need at least 114, 154, or 274 sessions respectively. The browser submits this
as a cancellable background job, polls progress while other screens remain
usable, cancels stale work after an input change, and caps the displayed
surface at 80 evenly spaced validation targets. The Backtest screen remains
focused on cross-sectional walk-forward diagnostics and no longer shows an
all-symbol volatility surface.

## Portfolio records

The local portfolio screen records manual holdings only; it cannot place or
route trades. Each entry is stored as a separate lot, while matching
account-symbol pairs display aggregate shares and weighted average cost.
Expanding an aggregate exposes the source lot, acquisition date, entry time,
and edit/delete controls. Valuations use only stored DuckDB prices; missing
prices remain blank and are never replaced by defaults.

## Event and confidence research

The **World & company events** screen makes explicit, user-triggered local
`codex exec --search` requests. Codex runs non-interactively in an isolated,
read-only temporary directory and receives no Massive credential. Prism
requires schema-valid JSON, records the CLI search activity, retains sourced
events, and stores the provider, model, prompt version, run status, usage, and
source list. It never substitutes generated events when login, network,
evidence, or ChatGPT/Codex usage is unavailable. Usage-limit failures stop the
operation immediately without retry.

New world and company event records contain both English research text and a
faithful Traditional Chinese translation. Each citation records the page's
source language and exposes a separate direct **View original** link. Older
records without translation metadata remain visibly untranslated until the
next sourced refresh.

Each event separately reports potential impact magnitude, transmission breadth,
direction, time horizon, and fixed market categories. Locally tracked symbols
are classified from sourced business or fund exposures and linked to an event
only through explicit category intersections or a direct company match.

Company events can be researched directly from a forecast window. Scheduled
earnings and major announcements are attached to every applicable 10-, 30-, or
90-session horizon. After the event, Prism stores a sourced outcome and
calculates 1-, 5-, and 20-session returns, SPY-relative excess returns, and
reaction volume from locally stored Massive bars. Pending horizons remain
pending.

The same screen stores two point-in-time confidence series:

- Weekly institution-by-institution evidence indices. AI extracts sourced
  ordinal stances; Prism converts the fixed -2 to +2 scale to 0–100.
- Monthly company long-term confidence. It is an explicit composite of stored
  6/12-month price behavior, the weekly institutional component, and sourced
  brand evidence.

Every component exposes its coverage. Missing components remain null and make
the composite `partial`; they are never replaced with neutral scores. Refresh
is manual in this version, so a missing week or month means it was not
researched. See [EVENT_RESEARCH.md](./EVENT_RESEARCH.md) for formulas and data
lineage.

## Local API

- `GET /api/v1/health`
- `GET /api/v1/overview`
- `GET /api/v1/scanner`
- `GET /api/v1/stocks/{symbol}`
- `GET /api/v1/metrics/catalog`
- `POST /api/v1/sync`
- `GET /api/v1/pipeline`
- `POST /api/v1/backtests`
- `GET /api/v1/backtests`
- `POST /api/v1/analyses`
- `GET /api/v1/analyses`
- `GET /api/v1/events`
- `GET /api/v1/instruments/classifications`
- `POST /api/v1/instruments/classifications/refresh`
- `POST /api/v1/events/world/refresh`
- `POST /api/v1/events/company/refresh`
- `POST /api/v1/events/due/resolve`
- `POST /api/v1/events/{event_id}/resolve`
- `POST /api/v1/events/reactions/refresh`
- `GET /api/v1/confidence`
- `POST /api/v1/confidence/refresh`
- `GET /api/v1/predictions`
- `POST /api/v1/predictions/seal`

Interactive documentation is available at
`http://127.0.0.1:8000/docs` while the API is running.

## Validation

```bash
make test
npm run lint
npx tsc --noEmit
```

Downloaded data and DuckDB files are ignored by Git.
