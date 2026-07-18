# Prism

Prism is a local-only, point-in-time market research workbench. It downloads
real adjusted daily stock bars from Massive, stores them in DuckDB, derives
versioned metrics, and runs walk-forward research diagnostics.

Prism does not place trades. It has no order, cancel-order, or brokerage
execution path.

## Data truth policy

- Runtime demo data does not exist.
- An empty database produces an empty UI.
- Provider failures never substitute sample prices, scores, or backtests.
- Previously stored real data remains available and is visibly timestamped.
- Every displayed market value names its provider and availability cutoff.
- Test fixtures exist only inside tests and are never loaded by the application.

## Architecture

```text
React / Vinext UI (local browser)
              |
              +-- FastAPI on 127.0.0.1:8000
                         |
                         +-- Massive adjusted daily bars
                         +-- point-in-time metrics
                         +-- walk-forward backtests
                         +-- local DuckDB
```

The Massive key is read only by FastAPI from the local process environment.
It is never sent to the browser and must not use a `NEXT_PUBLIC_*` name.

## Requirements

- Node.js 22.13 or newer
- Python 3.12 or newer
- A Massive API key

## Setup

```bash
make setup
cp .env.example .env
```

Set the key in the ignored `.env`:

```dotenv
MASSIVE_API_KEY=your-key
PRISM_DATABASE_PATH=./data/prism.duckdb
```

Then start both local processes:

```bash
make dev
```

Open the local URL printed by Vinext. In **Data & pipeline**, enter the exact
symbols and history length you want, then synchronize. Prism does not create a
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
