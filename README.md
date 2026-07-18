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

## Current metrics

The `price-core-v0.1` snapshot derives:

- 5-session return
- 20-session return
- annualized 20-session realized volatility
- 20-session volume z-score
- distance from the 20-session moving average
- trailing 60-session drawdown

The scanner ranks only the symbols currently present in DuckDB. The
walk-forward baseline evaluates 10, 30, or 90 future sessions at five-session
rebalance intervals and reports observation count, Spearman IC, top-minus-
bottom spread, and directional accuracy. Results exclude fees, slippage, taxes,
borrow costs, and survivorship corrections.

The **Range metrics** screen provides synchronized date inputs and a draggable
two-ended timeline. It calculates a point-in-time metric snapshot at the chosen
end date and builds 10-, 30-, and 90-session historical-analog forecasts using
only earlier outcomes inside the selected interval. If fewer than ten eligible
analogs exist, no forecast values are produced.

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
