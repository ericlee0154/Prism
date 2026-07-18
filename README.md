# Prism

Prism is a personal, point-in-time market research workbench. It ranks a
comparable stock universe, explains the drivers behind each score, lets a
researcher test versioned formulas, and records forward predictions in an
append-only, hash-linked ledger.

Prism is a research tool. It does not place trades and does not provide
investment advice.

## What is included

- Research overview with regime, coverage, performance, and data freshness.
- Searchable, filterable, sortable multi-horizon market scanner.
- Symbol detail with signal explanation, driver percentiles, horizon
  comparison, and temporal-integrity status.
- Durable personal watchlist.
- Formula lab with bounded weights, versioned drafts, walk-forward validation,
  baseline comparison, deciles, IC, drawdown, turnover, and locked holdout.
- Append-only prediction ledger with a SHA-256 content and predecessor chain.
- CSV and JSON Lines exports.
- Data center with provider status, synchronization history, pipeline versions,
  and audit activity.
- Deterministic demo provider and a working Massive daily-bar adapter.
- D1 persistence for watchlists, formulas, experiments, predictions, sync
  history, and activity.
- Optional ChatGPT/workspace identity. Anonymous production visitors are
  read-only; authenticated users receive isolated personal records.
- Python research core and FastAPI surface for local quantitative work.

The full acceptance checklist is in [PRODUCT_SCOPE.md](./PRODUCT_SCOPE.md).

## Architecture

```text
Vinext / React UI
       |
       +-- /api/prism -------- D1 personal workspace
       |
       +-- deterministic market domain and formula evaluator

Python FastAPI (local research surface)
       |
       +-- prism_core -------- metrics, providers, repository, service
       |
       +-- DuckDB ------------ local append-only research records
```

The hosted application uses Cloudflare-compatible Vinext and D1. The Python
surface is intentionally local: it is useful for deeper metric development and
provider validation without putting a Python service in the hosted request
path.

## Requirements

- Node.js 22.13 or newer
- Python 3.12 or newer

## Setup

```bash
make setup
make dev
```

`make dev` starts the local FastAPI research API on port 8000 and the Vinext
application on its printed local URL.

The web application works end-to-end with deterministic demo data and no API
keys. Local development uses an isolated local-researcher identity so durable
write flows can be exercised without production authentication.

## Useful commands

```bash
npm run dev          # web development server
npm run build        # production Worker build
npm run lint         # TypeScript and React static checks
npm test             # production build and web contract tests
npm run db:generate  # generate D1 migration after schema changes

.venv/bin/python -m pytest -q
make test             # Python and web test suites
make api              # FastAPI only
```

## Data providers

Demo mode is the default and is always labelled in the UI. To use the local
Massive daily aggregate adapter, set `MASSIVE_API_KEY` in an ignored `.env`
file or the shell environment. Never expose provider keys through
`NEXT_PUBLIC_*` variables.

The adapter uses Massive's official custom-bars endpoint, requests adjusted
daily data, enforces a timeout, and assigns a conservative post-close
availability time before metrics may consume a bar.

Other variables in `.env.example` are reserved integration boundaries. They do
not imply that credentials are present or that unsupported live data is shown.

## Local research API

The FastAPI service exposes:

- `GET /api/v1/health`
- `GET /api/v1/overview`
- `GET /api/v1/scanner`
- `GET /api/v1/stocks/{symbol}`
- `GET /api/v1/metrics/catalog`
- `POST /api/v1/formulas/evaluate`
- `GET /api/v1/predictions`
- `POST /api/v1/predictions/seal`
- `GET /api/v1/pipeline`
- `POST /api/v1/sync`

Interactive API documentation is available at `/docs` while the service runs.

## Temporal integrity

Every market bar carries both an observation timestamp and an availability
timestamp. A metric snapshot rejects any input that was not available by its
prediction cutoff. Sealed predictions store the exact metric snapshot, data
cutoff, formula version, metric version, content hash, and previous-record
hash.

The final holdout is deliberately represented as locked. Formula experiments
are saved separately and never rewrite predictions.

## Authentication and privacy

Production writes require the platform-provided ChatGPT/workspace identity.
The server derives an opaque owner key from the authenticated email and applies
it to every personal query. Identity and authorization checks happen on the
server; client controls are not trusted.

The app never stores provider credentials in D1 or sends them to the browser.
Hosted runtime variables belong in the Sites environment configuration.
