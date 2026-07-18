"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type View = "overview" | "scanner" | "backtest" | "data";
type Horizon = "10D" | "30D" | "90D";

type PrismUser = {
  displayName: string;
  email: string;
  local: boolean;
};

type MarketSummary = {
  bar_count: number;
  symbol_count: number;
  first_observation: string | null;
  last_observation: string | null;
  data_cutoff: string | null;
  last_synced_at: string | null;
  database_bytes: number;
};

type Stock = {
  symbol: string;
  price: number;
  change: number | null;
  bars: number[];
  bar_count: number;
  first_observation: string;
  last_observation: string;
  data_cutoff: string;
  source: string;
  metric_version: string;
  metrics: Record<string, number>;
  momentum: number;
  relativeStrength: number;
  trendQuality: number;
  volumeConfirmation: number;
  volatility: number;
  score10: number;
  score30: number;
  score90: number;
  score: number;
  signal: string;
  signalCopy: string;
  dataQuality: number;
};

type Backtest = {
  backtest_id: string;
  created_at?: string;
  status: "complete" | "insufficient_data";
  version: string;
  horizon_sessions: number;
  symbol_count: number;
  observation_count: number;
  evaluation_dates: number;
  mean_spearman_ic: number | null;
  mean_top_bottom_spread: number | null;
  direction_accuracy: number | null;
  warnings: string[];
  result?: Omit<Backtest, "backtest_id" | "created_at" | "result">;
};

type Overview = {
  provider: string | null;
  provider_configured: boolean;
  market: MarketSummary;
  market_regime: { label: string | null; breadth: number | null };
  candidate_coverage: { passing: number; universe: number };
  latest_backtest: Backtest | null;
  ledger: { records: number };
};

type Pipeline = {
  status: "ready" | "empty";
  provider: string | null;
  provider_configured: boolean;
  market: MarketSummary;
  sync_runs: {
    sync_id: string;
    started_at: string;
    completed_at: string | null;
    provider: string;
    symbols: string[];
    status: string;
    rows_written: number;
    error: string | null;
  }[];
  backtests: Backtest[];
  metric_version: string;
};

const API_BASE = "http://127.0.0.1:8000/api/v1";

const navItems: { id: View; label: string; icon: string }[] = [
  { id: "overview", label: "Overview", icon: "⌁" },
  { id: "scanner", label: "Market scanner", icon: "◎" },
  { id: "backtest", label: "Backtests", icon: "ƒ" },
  { id: "data", label: "Data & pipeline", icon: "⇄" },
];

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  const body = await response.json() as T & { detail?: string };
  if (!response.ok) {
    throw new Error(body.detail ?? `API request failed (${response.status})`);
  }
  return body;
}

function formatDate(value: string | null): string {
  if (!value) return "No data";
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "America/New_York",
  }).format(new Date(value));
}

function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index > 1 ? 2 : 0)} ${units[index]}`;
}

function scoreFor(stock: Stock, horizon: Horizon): number {
  return horizon === "10D" ? stock.score10 : horizon === "30D" ? stock.score30 : stock.score90;
}

function Header({
  eyebrow,
  title,
  copy,
  children,
}: {
  eyebrow: string;
  title: string;
  copy: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="page-title">{title}</h1>
        <p className="page-copy">{copy}</p>
      </div>
      {children ? <div className="heading-actions">{children}</div> : null}
    </div>
  );
}

function EmptyMarket({ onOpenData }: { onOpenData: () => void }) {
  return (
    <div className="panel empty-market">
      <span className="tiny-badge">EMPTY BY DESIGN</span>
      <h2>No stored market data</h2>
      <p>
        Prism will not substitute sample prices, scores, predictions, or backtest
        results. Synchronize symbols from Massive to populate this workspace.
      </p>
      <button className="primary-button" onClick={onOpenData}>Open data sync</button>
    </div>
  );
}

function SummaryCards({ overview }: { overview: Overview }) {
  const latestResult = overview.latest_backtest?.result ?? overview.latest_backtest;
  return (
    <div className="summary-grid">
      <div className="summary-card featured">
        <div className="summary-card-label">
          Stored universe <span className="tiny-badge live">Massive EOD</span>
        </div>
        <div className="summary-value mono">{overview.market.symbol_count}</div>
        <div className="summary-meta">{overview.market.bar_count.toLocaleString()} real daily bars</div>
      </div>
      <div className="summary-card">
        <div className="summary-card-label">Latest observation</div>
        <div className="summary-value summary-date">{formatDate(overview.market.last_observation)}</div>
        <div className="summary-meta">Source cutoff {formatDate(overview.market.data_cutoff)}</div>
      </div>
      <div className="summary-card">
        <div className="summary-card-label">Positive 20-session breadth</div>
        <div className="summary-value mono">
          {overview.market_regime.breadth === null
            ? "—"
            : `${(overview.market_regime.breadth * 100).toFixed(1)}%`}
        </div>
        <div className="summary-meta">{overview.market_regime.label ?? "Insufficient data"}</div>
      </div>
      <div className="summary-card">
        <div className="summary-card-label">Latest walk-forward IC</div>
        <div className="summary-value mono">
          {latestResult?.mean_spearman_ic == null
            ? "—"
            : latestResult.mean_spearman_ic.toFixed(3)}
        </div>
        <div className="summary-meta">
          {latestResult ? `${latestResult.observation_count} observations` : "No backtest has been run"}
        </div>
      </div>
    </div>
  );
}

function StockTable({
  stocks,
  active,
  setActive,
  horizon,
  search,
}: {
  stocks: Stock[];
  active: Stock | null;
  setActive: (stock: Stock) => void;
  horizon: Horizon;
  search: string;
}) {
  const visible = useMemo(
    () => stocks
      .filter((stock) => stock.symbol.includes(search.trim().toUpperCase()))
      .sort((left, right) => scoreFor(right, horizon) - scoreFor(left, horizon)),
    [stocks, search, horizon],
  );
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Latest close</th>
            <th>5-session return</th>
            <th>20-session return</th>
            <th>20-session volatility</th>
            <th>60-session drawdown</th>
            <th>{horizon} score</th>
            <th>Rows</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((stock) => (
            <tr
              key={stock.symbol}
              className={active?.symbol === stock.symbol ? "selected" : ""}
              onClick={() => setActive(stock)}
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") setActive(stock);
              }}
            >
              <td><strong>{stock.symbol}</strong><div className="company-name">{stock.source}</div></td>
              <td className="mono">${stock.price.toFixed(2)}<div className={stock.change != null && stock.change >= 0 ? "positive-text" : "negative-text"}>{stock.change == null ? "—" : `${stock.change >= 0 ? "+" : ""}${stock.change.toFixed(2)}%`}</div></td>
              <td className="mono">{(stock.metrics.return_5d * 100).toFixed(2)}%</td>
              <td className="mono">{(stock.metrics.return_20d * 100).toFixed(2)}%</td>
              <td className="mono">{(stock.metrics.realized_volatility_20d * 100).toFixed(1)}%</td>
              <td className="mono">{(stock.metrics.drawdown_60d * 100).toFixed(2)}%</td>
              <td><span className={`score-pill ${scoreFor(stock, horizon) >= 60 ? "positive" : scoreFor(stock, horizon) < 40 ? "negative" : "neutral"}`}>{scoreFor(stock, horizon).toFixed(1)}</span></td>
              <td className="mono">{stock.bar_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!visible.length && <div className="empty-state">No stored symbols match this filter.</div>}
    </div>
  );
}

function StockDetail({ stock, horizon }: { stock: Stock; horizon: Horizon }) {
  return (
    <div className="panel detail-card">
      <div className="detail-hero">
        <div className="stock-identity">
          <div>
            <h2 className="stock-symbol">{stock.symbol}</h2>
            <div className="stock-sector">{stock.source} · {formatDate(stock.last_observation)}</div>
          </div>
          <span className="tiny-badge live">stored</span>
        </div>
        <div className="stock-price">
          <span className="price-main">${stock.price.toFixed(2)}</span>
          <span className={stock.change != null && stock.change >= 0 ? "price-change" : "price-change negative-text"}>
            {stock.change == null ? "—" : `${stock.change >= 0 ? "+" : ""}${stock.change.toFixed(2)}%`}
          </span>
        </div>
        <div className="chart-area" aria-label={`${stock.symbol} actual normalized close path`}>
          {stock.bars.map((height, index) => (
            <span className="chart-bar" style={{ height: `${height}%` }} key={`${stock.symbol}-${index}`} />
          ))}
        </div>
        <div className="chart-caption"><span>22 stored sessions ago</span><span>latest close</span></div>
      </div>
      <div className="signal-block">
        <div className="signal-top">
          <span className="signal-label">{horizon} relative metric score</span>
          <span className="score-pill positive">{scoreFor(stock, horizon).toFixed(1)}</span>
        </div>
        <div className="signal-status">{stock.signal}</div>
        <p className="signal-copy">{stock.signalCopy}</p>
      </div>
      <div className="driver-list">
        <p className="driver-title">Cross-sectional ranks</p>
        <div className="driver"><span className="driver-dot" /><span>20-session momentum</span><span className="driver-value">{stock.momentum.toFixed(1)}p</span></div>
        <div className="driver"><span className="driver-dot" /><span>Relative strength</span><span className="driver-value">{stock.relativeStrength.toFixed(1)}p</span></div>
        <div className="driver"><span className="driver-dot risk" /><span>Realized volatility</span><span className="driver-value">{stock.volatility.toFixed(1)}p</span></div>
      </div>
      <div className="snapshot-meta">
        <span>Metric version</span><strong className="mono">{stock.metric_version}</strong>
        <span>Available at</span><strong>{formatDate(stock.data_cutoff)}</strong>
        <span>Data quality</span><strong>{stock.dataQuality.toFixed(0)}%</strong>
      </div>
    </div>
  );
}

function BacktestView({
  backtests,
  run,
  running,
}: {
  backtests: Backtest[];
  run: (horizon: number) => Promise<void>;
  running: boolean;
}) {
  const [horizon, setHorizon] = useState(30);
  const latest = backtests[0];
  const result = latest?.result ?? latest;
  const metric = (value: number | null | undefined, format: "percent" | "decimal") => {
    if (value == null) return "—";
    return format === "percent" ? `${(value * 100).toFixed(2)}%` : value.toFixed(3);
  };
  return (
    <div className="page-section">
      <Header
        eyebrow="Walk-forward validation · stored bars only"
        title="Test metrics without inventing outcomes."
        copy="Every result is recomputed from local Massive history. If there are not enough symbols or observations, Prism reports insufficient data instead of filling example numbers."
      >
        <select className="filter-select" value={horizon} onChange={(event) => setHorizon(Number(event.target.value))}>
          <option value={10}>10 sessions</option>
          <option value={30}>30 sessions</option>
          <option value={90}>90 sessions</option>
        </select>
        <button className="primary-button" disabled={running} onClick={() => void run(horizon)}>
          {running ? "Running…" : "Run real backtest"}
        </button>
      </Header>
      {!latest ? (
        <div className="panel empty-market">
          <h2>No backtest results</h2>
          <p>Synchronize sufficient history for several symbols, then run the first walk-forward test.</p>
        </div>
      ) : (
        <>
          <div className="result-grid">
            <div className="result-card"><div className="result-label">Mean Spearman IC</div><div className="result-value mono">{metric(result.mean_spearman_ic, "decimal")}</div><div className="result-delta">Rank correlation across evaluation dates</div></div>
            <div className="result-card"><div className="result-label">Top-bottom spread</div><div className="result-value mono">{metric(result.mean_top_bottom_spread, "percent")}</div><div className="result-delta">Average forward-return separation</div></div>
            <div className="result-card"><div className="result-label">Direction accuracy</div><div className="result-value mono">{metric(result.direction_accuracy, "percent")}</div><div className="result-delta">Diagnostic only; not trading advice</div></div>
            <div className="result-card"><div className="result-label">Observations</div><div className="result-value mono">{result.observation_count}</div><div className="result-delta">{result.symbol_count} symbols · {result.evaluation_dates} dates</div></div>
          </div>
          <div className="panel pipeline">
            <div className="panel-header"><div><h2 className="panel-title">Method limits</h2><p className="panel-subtitle">{result.version}</p></div><span className="tiny-badge">{result.status}</span></div>
            <div className="note-list">{result.warnings.map((warning) => <div className="research-note" key={warning}>{warning}</div>)}</div>
          </div>
        </>
      )}
    </div>
  );
}

function DataView({
  pipeline,
  sync,
  syncing,
}: {
  pipeline: Pipeline | null;
  sync: (symbols: string[], years: number) => Promise<void>;
  syncing: boolean;
}) {
  const [symbols, setSymbols] = useState("");
  const [years, setYears] = useState(2);
  const parsed = symbols
    .split(/[\s,]+/)
    .map((symbol) => symbol.trim().toUpperCase())
    .filter(Boolean);
  return (
    <div className="page-section">
      <Header
        eyebrow="Massive → DuckDB · local only"
        title="Synchronize real history."
        copy="Enter only the symbols you want. Prism never inserts a default universe and never substitutes demo bars when a request fails."
      />
      <div className="content-grid data-sync-grid">
        <div className="panel journal-composer">
          <div className="panel-header"><div><h2 className="panel-title">New synchronization</h2><p className="panel-subtitle">Your Massive key stays in the local API process.</p></div></div>
          <div className="journal-form">
            <label>
              Symbols
              <textarea
                value={symbols}
                onChange={(event) => setSymbols(event.target.value)}
                placeholder="AAPL, MSFT, NVDA, SPY"
                aria-label="Symbols to synchronize"
              />
            </label>
            <label>
              History
              <select className="filter-select" value={years} onChange={(event) => setYears(Number(event.target.value))}>
                <option value={1}>1 year</option>
                <option value={2}>2 years — Basic plan limit</option>
                <option value={5}>5 years</option>
                <option value={10}>10 years</option>
                <option value={20}>20 years</option>
              </select>
            </label>
            <p className="panel-subtitle">{parsed.length} unique input symbols. Free Massive accounts are limited to five API calls per minute and two years of history.</p>
            <button
              className="primary-button"
              disabled={syncing || !parsed.length}
              onClick={() => void sync(parsed, years)}
            >
              {syncing ? "Synchronizing real bars…" : "Synchronize to DuckDB"}
            </button>
          </div>
        </div>
        <div className="panel">
          <div className="panel-header"><div><h2 className="panel-title">Local storage</h2><p className="panel-subtitle">No cloud database is used by the local research API.</p></div></div>
          <div className="source-fields storage-fields">
            <div className="source-field"><span>Provider</span><strong>{pipeline?.provider_configured ? "Massive configured" : "Missing API key"}</strong></div>
            <div className="source-field"><span>Symbols</span><strong>{pipeline?.market.symbol_count ?? 0}</strong></div>
            <div className="source-field"><span>Daily bars</span><strong>{(pipeline?.market.bar_count ?? 0).toLocaleString()}</strong></div>
            <div className="source-field"><span>DuckDB file</span><strong>{formatBytes(pipeline?.market.database_bytes ?? 0)}</strong></div>
            <div className="source-field"><span>First observation</span><strong>{formatDate(pipeline?.market.first_observation ?? null)}</strong></div>
            <div className="source-field"><span>Latest observation</span><strong>{formatDate(pipeline?.market.last_observation ?? null)}</strong></div>
          </div>
        </div>
      </div>
      <div className="panel pipeline">
        <div className="panel-header"><div><h2 className="panel-title">Synchronization history</h2><p className="panel-subtitle">Partial and failed runs remain visible; they never trigger fallback data.</p></div></div>
        <div className="activity-list">
          {pipeline?.sync_runs.length ? pipeline.sync_runs.map((run) => (
            <div className="activity-row" key={run.sync_id}>
              <span className={`tiny-badge ${run.status === "complete" ? "live" : ""}`}>{run.status}</span>
              <span>{run.symbols.join(", ")} · {run.rows_written.toLocaleString()} rows</span>
              <time>{new Date(run.started_at).toLocaleString()}</time>
              {run.error ? <small className="negative-text">{run.error}</small> : null}
            </div>
          )) : <div className="empty-state">No synchronization has been run.</div>}
        </div>
      </div>
    </div>
  );
}

export function PrismApp({ initialUser }: { initialUser: PrismUser | null }) {
  const [view, setView] = useState<View>("overview");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [activeStock, setActiveStock] = useState<Stock | null>(null);
  const [backtests, setBacktests] = useState<Backtest[]>([]);
  const [horizon, setHorizon] = useState<Horizon>("30D");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [running, setRunning] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [overviewResult, scannerResult, pipelineResult, backtestResult] = await Promise.all([
        api<Overview>("/overview"),
        api<{ items: Stock[] }>("/scanner?horizon=30D"),
        api<Pipeline>("/pipeline"),
        api<{ items: Backtest[] }>("/backtests"),
      ]);
      setOverview(overviewResult);
      setStocks(scannerResult.items);
      setPipeline(pipelineResult);
      setBacktests(backtestResult.items);
      setActiveStock((current) =>
        scannerResult.items.find((stock) => stock.symbol === current?.symbol)
        ?? scannerResult.items[0]
        ?? null
      );
    } catch (loadError) {
      setOverview(null);
      setStocks([]);
      setActiveStock(null);
      setPipeline(null);
      setBacktests([]);
      setError(loadError instanceof Error ? loadError.message : "Local API unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Initial client hydration reads the independent local FastAPI process.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(""), 3200);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const sync = async (symbols: string[], years: number) => {
    setSyncing(true);
    try {
      const result = await api<{ status: string; rows_written: number; failures: { symbol: string; error: string }[] }>("/sync", {
        method: "POST",
        body: JSON.stringify({ symbols, years }),
      });
      setToast(`${result.status}: ${result.rows_written.toLocaleString()} real bars stored${result.failures.length ? `; ${result.failures.length} symbols failed` : ""}.`);
      await load();
    } catch (syncError) {
      setToast(syncError instanceof Error ? syncError.message : "Synchronization failed");
    } finally {
      setSyncing(false);
    }
  };

  const runBacktest = async (horizonSessions: number) => {
    setRunning(true);
    try {
      const result = await api<Backtest>("/backtests", {
        method: "POST",
        body: JSON.stringify({ horizon_sessions: horizonSessions }),
      });
      setToast(result.status === "complete" ? "Real walk-forward backtest completed." : "Not enough stored data for this backtest.");
      await load();
    } catch (runError) {
      setToast(runError instanceof Error ? runError.message : "Backtest failed");
    } finally {
      setRunning(false);
    }
  };

  const cutoff = overview?.market.data_cutoff;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark">P</div><div><div className="brand-name">Prism</div><div className="brand-sub">Local research workbench</div></div></div>
        <div className="nav-label">Workspace</div>
        <nav className="nav-list">
          {navItems.map((item) => (
            <button key={item.id} className={`nav-item ${view === item.id ? "active" : ""}`} onClick={() => setView(item.id)}>
              <span className="nav-icon">{item.icon}</span><span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-spacer" />
        <div className="data-card">
          <div className="data-card-top"><span className="data-card-title">{overview?.market.bar_count ? "Real stored data" : "No market data"}</span><span className={`status-dot ${overview?.market.bar_count ? "" : "status-dot-empty"}`} /></div>
          <p className="data-card-copy">
            {overview?.market.bar_count
              ? `${overview.market.symbol_count} symbols from Massive. No demo fallback.`
              : "Prism intentionally remains empty until a successful Massive synchronization."}
          </p>
        </div>
        <div className="sidebar-footer"><div className="avatar">{(initialUser?.displayName ?? "L").slice(0, 1)}</div><span className="identity-copy"><strong>{initialUser?.displayName ?? "Local researcher"}</strong><small>read-only market integration</small></span></div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="search">
            <span className="search-icon">⌕</span>
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Filter stored symbols…" aria-label="Filter stored symbols" />
          </div>
          <div className="topbar-actions">
            <span className="cutoff mono">{cutoff ? `MASSIVE EOD · ${formatDate(cutoff)}` : "NO MARKET DATA"}</span>
            <button className="icon-button" onClick={() => void load()} aria-label="Reload stored data">↻</button>
            <button className="primary-button" onClick={() => setView("data")}>Sync data</button>
          </div>
        </header>
        <main className="main">
          {loading && <div className="workspace-notice">Loading local DuckDB state…</div>}
          {error && <div className="workspace-notice error"><span>{error}. No fallback data is displayed.</span><button className="secondary-button" onClick={() => void load()}>Retry</button></div>}
          {!loading && !error && view === "overview" && overview && (
            <div className="page-section">
              <Header eyebrow="Local-only · provider truth" title="Research what is actually stored." copy="Prism uses only Massive bars persisted in your local DuckDB. Missing, stale, or failed data remains visibly missing." />
              {overview.market.bar_count === 0 ? <EmptyMarket onOpenData={() => setView("data")} /> : (
                <>
                  <SummaryCards overview={overview} />
                  <div className="content-grid">
                    <div className="panel"><div className="panel-header"><div><h2 className="panel-title">Stored universe</h2><p className="panel-subtitle">Real cross-sectional metrics at one cutoff</p></div><button className="secondary-button" onClick={() => setView("scanner")}>View scanner →</button></div><StockTable stocks={stocks} active={activeStock} setActive={setActiveStock} horizon={horizon} search={search} /></div>
                    {activeStock ? <StockDetail stock={activeStock} horizon={horizon} /> : null}
                  </div>
                </>
              )}
            </div>
          )}
          {!loading && !error && view === "scanner" && (
            <div className="page-section">
              <Header eyebrow="Stored Massive history" title="Compare real observations." copy="Scores are derived from the currently stored universe. They are research metrics, not recommendations or order instructions.">
                <div className="segments">{(["10D", "30D", "90D"] as Horizon[]).map((item) => <button key={item} className={`segment-button ${horizon === item ? "active" : ""}`} onClick={() => setHorizon(item)}>{item}</button>)}</div>
              </Header>
              {!stocks.length ? <EmptyMarket onOpenData={() => setView("data")} /> : <div className="content-grid"><div className="panel"><StockTable stocks={stocks} active={activeStock} setActive={setActiveStock} horizon={horizon} search={search} /></div>{activeStock ? <StockDetail stock={activeStock} horizon={horizon} /> : null}</div>}
            </div>
          )}
          {!loading && !error && view === "backtest" && <BacktestView backtests={backtests} run={runBacktest} running={running} />}
          {!loading && !error && view === "data" && <DataView pipeline={pipeline} sync={sync} syncing={syncing} />}
        </main>
      </div>
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}
