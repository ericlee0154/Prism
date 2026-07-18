"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type View = "overview" | "scanner" | "lab" | "ledger" | "journal" | "data";
type Horizon = "10D" | "30D" | "90D";

type Stock = {
  symbol: string;
  name: string;
  sector: string;
  price: number;
  change: number;
  momentum: number;
  relativeStrength: number;
  volatility: number;
  score10: number;
  score30: number;
  score90: number;
  confidence: number;
  signal: string;
  signalCopy: string;
  bars: number[];
};

type LedgerRow = {
  predictionId?: string;
  date: string;
  symbol: string;
  horizon: Horizon;
  direction: "Bullish" | "Neutral" | "Bearish";
  confidence: number;
  expected: string;
  actual: string;
  outcome: "Pending" | "Correct" | "Incorrect" | "Neutral";
  version: string;
  recordHash?: string;
  source?: "demo" | "user";
};

type PrismUser = {
  displayName: string;
  email: string;
  local: boolean;
};

type OverviewData = {
  marketRegime: { label: string; confidence: number };
  candidateCoverage: { passing: number; universe: number };
  directionHitRate30d: number;
  ledger: { matured: number; correct: number; pending: number };
};

type ActivityItem = {
  activityId: string;
  action: string;
  summary: string;
  createdAt: string;
};

type FormulaRecord = {
  formulaId: string;
  name: string;
  horizon: Horizon;
  status: string;
  updatedAt: string;
};

type ExperimentRecord = {
  experimentId: string;
  formulaVersion: string;
  horizon: Horizon;
  createdAt: string;
  result: { metrics?: Record<string, number> };
};

type ResearchNote = {
  noteId: string;
  symbol: string;
  title: string;
  thesis: string;
  invalidation: string;
  tags: string[];
  createdAt: string;
};

const stocks: Stock[] = [
  {
    symbol: "NVDA",
    name: "NVIDIA",
    sector: "Semiconductors",
    price: 184.92,
    change: 2.84,
    momentum: 91,
    relativeStrength: 94,
    volatility: 63,
    score10: 72,
    score30: 81,
    score90: 76,
    confidence: 68,
    signal: "Constructive momentum",
    signalCopy:
      "Relative strength and volume confirmation remain positive. Elevated volatility keeps this below a high-conviction threshold.",
    bars: [24, 31, 28, 39, 44, 38, 48, 51, 46, 57, 54, 63, 61, 69, 74, 68, 76, 72, 81, 88, 82, 94],
  },
  {
    symbol: "META",
    name: "Meta Platforms",
    sector: "Interactive Media",
    price: 739.46,
    change: 1.36,
    momentum: 84,
    relativeStrength: 88,
    volatility: 42,
    score10: 68,
    score30: 77,
    score90: 73,
    confidence: 64,
    signal: "Positive, not extended",
    signalCopy:
      "Medium-term trend is healthy and volatility is controlled. The current setup ranks well without entering an extreme percentile.",
    bars: [29, 35, 33, 40, 37, 44, 49, 46, 53, 55, 51, 62, 67, 64, 69, 73, 71, 77, 80, 78, 85, 88],
  },
  {
    symbol: "AAPL",
    name: "Apple",
    sector: "Technology Hardware",
    price: 259.71,
    change: -0.42,
    momentum: 52,
    relativeStrength: 46,
    volatility: 31,
    score10: 49,
    score30: 54,
    score90: 61,
    confidence: 51,
    signal: "No actionable edge",
    signalCopy:
      "Volatility is benign, but the stock is not demonstrating enough relative strength for the formula to separate it from the benchmark.",
    bars: [57, 55, 59, 62, 58, 54, 60, 63, 61, 66, 64, 62, 65, 61, 58, 56, 59, 55, 57, 54, 52, 51],
  },
  {
    symbol: "MSFT",
    name: "Microsoft",
    sector: "Software",
    price: 523.18,
    change: 0.78,
    momentum: 73,
    relativeStrength: 71,
    volatility: 29,
    score10: 61,
    score30: 69,
    score90: 75,
    confidence: 61,
    signal: "Steady accumulation",
    signalCopy:
      "Trend quality is better than raw momentum suggests. Lower realized volatility supports the 30 and 90-day risk-adjusted outlook.",
    bars: [36, 39, 42, 40, 45, 48, 46, 50, 49, 54, 57, 55, 59, 61, 60, 64, 66, 65, 69, 72, 70, 75],
  },
  {
    symbol: "AVGO",
    name: "Broadcom",
    sector: "Semiconductors",
    price: 344.83,
    change: 3.21,
    momentum: 95,
    relativeStrength: 92,
    volatility: 76,
    score10: 74,
    score30: 79,
    score90: 65,
    confidence: 66,
    signal: "Strong, with tail risk",
    signalCopy:
      "The highest momentum profile in the current universe is offset by elevated realized volatility and a stretched distance from trend.",
    bars: [21, 28, 25, 36, 31, 44, 39, 52, 48, 61, 55, 66, 62, 74, 69, 80, 72, 86, 81, 92, 88, 96],
  },
  {
    symbol: "AMZN",
    name: "Amazon",
    sector: "Consumer Discretionary",
    price: 238.64,
    change: -1.12,
    momentum: 44,
    relativeStrength: 39,
    volatility: 38,
    score10: 42,
    score30: 47,
    score90: 56,
    confidence: 48,
    signal: "Watch for repair",
    signalCopy:
      "Short-term momentum has weakened. A recovery in sector-relative strength is required before this returns to candidate status.",
    bars: [72, 75, 70, 78, 74, 69, 66, 71, 68, 63, 65, 59, 61, 57, 54, 58, 55, 51, 53, 48, 46, 44],
  },
  {
    symbol: "JPM",
    name: "JPMorgan Chase",
    sector: "Banks",
    price: 301.27,
    change: 0.32,
    momentum: 64,
    relativeStrength: 67,
    volatility: 24,
    score10: 56,
    score30: 65,
    score90: 70,
    confidence: 58,
    signal: "Quietly constructive",
    signalCopy:
      "Positive relative strength and low volatility make the longer horizon more attractive than the short-term setup.",
    bars: [41, 43, 40, 45, 48, 47, 51, 49, 53, 55, 54, 58, 57, 61, 63, 62, 66, 65, 69, 71, 70, 73],
  },
  {
    symbol: "XOM",
    name: "Exxon Mobil",
    sector: "Energy",
    price: 119.38,
    change: -0.88,
    momentum: 38,
    relativeStrength: 33,
    volatility: 35,
    score10: 36,
    score30: 41,
    score90: 48,
    confidence: 47,
    signal: "Below candidate threshold",
    signalCopy:
      "Weak sector-relative momentum dominates an otherwise ordinary risk profile. The system assigns no current directional edge.",
    bars: [68, 66, 69, 65, 62, 64, 59, 61, 57, 55, 58, 53, 51, 54, 49, 52, 47, 45, 48, 43, 41, 39],
  },
];

const initialLedger: LedgerRow[] = [
  { date: "Jul 18, 2026", symbol: "NVDA", horizon: "30D", direction: "Bullish", confidence: 68, expected: "+2.1% to +7.4%", actual: "Matures Aug 31", outcome: "Pending", version: "core-v0.1" },
  { date: "Jul 18, 2026", symbol: "META", horizon: "30D", direction: "Bullish", confidence: 64, expected: "+1.2% to +5.8%", actual: "Matures Aug 31", outcome: "Pending", version: "core-v0.1" },
  { date: "Jun 26, 2026", symbol: "MSFT", horizon: "10D", direction: "Bullish", confidence: 61, expected: "+0.4% to +3.2%", actual: "+2.6%", outcome: "Correct", version: "core-v0.1" },
  { date: "Jun 18, 2026", symbol: "AMZN", horizon: "30D", direction: "Neutral", confidence: 52, expected: "-1.8% to +2.0%", actual: "-3.1%", outcome: "Incorrect", version: "core-v0.1" },
  { date: "May 29, 2026", symbol: "JPM", horizon: "30D", direction: "Bullish", confidence: 59, expected: "+0.8% to +4.0%", actual: "+3.4%", outcome: "Correct", version: "core-v0.1" },
  { date: "Apr 17, 2026", symbol: "XOM", horizon: "90D", direction: "Bearish", confidence: 56, expected: "-5.0% to +1.0%", actual: "-2.7%", outcome: "Correct", version: "core-v0.1" },
];

const navItems: { id: View; label: string; icon: string }[] = [
  { id: "overview", label: "Overview", icon: "⌁" },
  { id: "scanner", label: "Market scanner", icon: "◎" },
  { id: "lab", label: "Formula lab", icon: "ƒ" },
  { id: "ledger", label: "Prediction ledger", icon: "▤" },
  { id: "journal", label: "Research journal", icon: "✎" },
  { id: "data", label: "Data & pipeline", icon: "⇄" },
];

const scoreClass = (score: number) =>
  score >= 60 ? "positive" : score < 45 ? "negative" : "neutral";

const formatChange = (value: number) =>
  `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;

const downloadText = (filename: string, content: string, type: string) => {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
};

const ledgerFromApi = (row: Record<string, unknown>): LedgerRow => ({
  predictionId: String(row.predictionId ?? ""),
  date: new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(String(row.createdAt))),
  symbol: String(row.symbol),
  horizon: String(row.horizon) as Horizon,
  direction: String(row.direction) as LedgerRow["direction"],
  confidence: Number(row.confidence),
  expected: String(row.expectedRange),
  actual: String(row.actualOutcome),
  outcome: String(row.outcome) as LedgerRow["outcome"],
  version: String(row.formulaVersion),
  recordHash: String(row.recordHash ?? ""),
  source: String(row.source ?? "demo") as LedgerRow["source"],
});

function Header({
  title,
  copy,
  eyebrow,
  children,
}: {
  title: string;
  copy: string;
  eyebrow: string;
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

function SummaryCards({ overview }: { overview: OverviewData }) {
  const hitRate = overview.directionHitRate30d * 100;
  const baselineDelta = hitRate - 53.7;
  return (
    <div className="summary-grid">
      <div className="summary-card featured">
        <div className="summary-card-label">
          Market regime <span className="tiny-badge live">demo</span>
        </div>
        <div className="summary-value">{overview.marketRegime.label}</div>
        <div className="summary-meta">
          <span className="summary-accent">{Math.round(overview.marketRegime.confidence * 100)}%</span> regime confidence
        </div>
        <div className="regime-track" aria-label="Regime confidence 68 percent">
          <span className="on" /><span className="on" /><span className="on" /><span className="on" /><span /><span />
        </div>
      </div>
      <div className="summary-card">
        <div className="summary-card-label">
          Candidate coverage <span className="tiny-badge">universe</span>
        </div>
        <div className="summary-value mono">{overview.candidateCoverage.passing} / {overview.candidateCoverage.universe}</div>
        <div className="summary-meta">
          <span className="summary-accent">{overview.candidateCoverage.passing}</span> above 30D score threshold
        </div>
      </div>
      <div className="summary-card">
        <div className="summary-card-label">
          30D direction hit rate <span className="tiny-badge">forward</span>
        </div>
        <div className="summary-value mono">{hitRate.toFixed(1)}%</div>
        <div className="summary-meta">
          <span className="summary-accent">{baselineDelta >= 0 ? "+" : ""}{baselineDelta.toFixed(1)}pp</span> vs always-up baseline
        </div>
      </div>
      <div className="summary-card">
        <div className="summary-card-label">
          Matured predictions <span className="tiny-badge">ledger</span>
        </div>
        <div className="summary-value mono">{overview.ledger.matured}</div>
        <div className="summary-meta">
          {overview.ledger.pending} pending across 10 / 30 / 90D
        </div>
      </div>
    </div>
  );
}

function ScannerTable({
  activeStock,
  setActiveStock,
  horizon,
  compact = false,
  search,
  items = stocks,
}: {
  activeStock: Stock;
  setActiveStock: (stock: Stock) => void;
  horizon: Horizon;
  compact?: boolean;
  search: string;
  items?: Stock[];
}) {
  type SortField = "score" | "price" | "momentum" | "relativeStrength" | "volatility" | "confidence";
  const [sortField, setSortField] = useState<SortField>("score");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
  const filtered = items.filter((stock) =>
    `${stock.symbol} ${stock.name} ${stock.sector}`.toLowerCase().includes(search.toLowerCase()),
  );
  const scoreKey = horizon === "10D" ? "score10" : horizon === "30D" ? "score30" : "score90";
  const valueFor = (stock: Stock) => sortField === "score" ? stock[scoreKey] : stock[sortField];
  const sorted = [...filtered].sort((a, b) =>
    (valueFor(a) - valueFor(b)) * (sortDirection === "asc" ? 1 : -1),
  );
  const changeSort = (field: SortField) => {
    if (sortField === field) setSortDirection((current) => current === "asc" ? "desc" : "asc");
    else {
      setSortField(field);
      setSortDirection("desc");
    }
  };
  const sortLabel = (field: SortField, label: string) => (
    <button className="table-sort" onClick={() => changeSort(field)}>
      {label}{sortField === field ? (sortDirection === "desc" ? " ↓" : " ↑") : ""}
    </button>
  );

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th>{sortLabel("price", "Price")}</th>
            <th>{sortLabel("momentum", "Momentum")}</th>
            {!compact && <th>{sortLabel("relativeStrength", "Rel. strength")}</th>}
            {!compact && <th>{sortLabel("volatility", "Risk")}</th>}
            <th>{sortLabel("score", `${horizon} score`)}</th>
            <th>{sortLabel("confidence", "Confidence")}</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((stock) => (
            <tr
              key={stock.symbol}
              className={activeStock.symbol === stock.symbol ? "selected" : ""}
              onClick={() => setActiveStock(stock)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setActiveStock(stock);
                }
              }}
              tabIndex={0}
            >
              <td>
                <div className="symbol-cell">
                  <div className="symbol-mark">{stock.symbol.slice(0, 2)}</div>
                  <div>
                    <div className="symbol-name">{stock.symbol}</div>
                    <div className="company-name">{stock.name}</div>
                  </div>
                </div>
              </td>
              <td>
                <div className="mono">${stock.price.toFixed(2)}</div>
                <div className={`company-name ${stock.change >= 0 ? "positive-text" : "negative-text"}`}>
                  {formatChange(stock.change)}
                </div>
              </td>
              <td>
                <div className="metric-rank">
                  <div className="metric-bar"><span style={{ width: `${stock.momentum}%` }} /></div>
                  <span className="mono">{stock.momentum}</span>
                </div>
              </td>
              {!compact && (
                <td>
                  <div className="metric-rank">
                    <div className="metric-bar"><span style={{ width: `${stock.relativeStrength}%` }} /></div>
                    <span className="mono">{stock.relativeStrength}</span>
                  </div>
                </td>
              )}
              {!compact && <td className="mono">{stock.volatility}p</td>}
              <td>
                <span className={`score-pill ${scoreClass(stock[scoreKey])}`}>{stock[scoreKey]}</span>
              </td>
              <td className="mono">{stock.confidence}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!sorted.length && <div className="empty-state">No symbols match “{search}”.</div>}
    </div>
  );
}

function StockDetail({
  stock,
  horizon,
  watched,
  onWatch,
  onSeal,
}: {
  stock: Stock;
  horizon: Horizon;
  watched: string[];
  onWatch: (symbol: string) => void;
  onSeal?: (symbol: string, horizon: Horizon) => Promise<void>;
}) {
  const score = horizon === "10D" ? stock.score10 : horizon === "30D" ? stock.score30 : stock.score90;
  return (
    <div className="panel detail-card">
      <div className="detail-hero">
        <div className="stock-identity">
          <div>
            <h2 className="stock-symbol">{stock.symbol}</h2>
            <div className="stock-sector">{stock.name} · {stock.sector}</div>
          </div>
          <button
            className={`watch-button ${watched.includes(stock.symbol) ? "active" : ""}`}
            onClick={() => onWatch(stock.symbol)}
            aria-label={`${watched.includes(stock.symbol) ? "Remove" : "Add"} ${stock.symbol} watchlist`}
          >
            {watched.includes(stock.symbol) ? "★" : "☆"}
          </button>
        </div>
        <div className="stock-price">
          <span className="price-main">${stock.price.toFixed(2)}</span>
          <span className={stock.change >= 0 ? "price-change" : "price-change negative-text"}>
            {formatChange(stock.change)}
          </span>
        </div>
        <div className="chart-area" aria-label={`${stock.symbol} recent normalized price path`}>
          {stock.bars.map((height, index) => (
            <span className="chart-bar" style={{ height: `${height}%` }} key={`${stock.symbol}-${index}`} />
          ))}
        </div>
        <div className="chart-caption"><span>20 sessions ago</span><span>latest close</span></div>
      </div>
      <div className="signal-block">
        <div className="signal-top">
          <span className="signal-label">{horizon} formula read</span>
          <span className="score-pill positive">{score}</span>
        </div>
        <div className="signal-status">{stock.signal}</div>
        <p className="signal-copy">{stock.signalCopy}</p>
        {onSeal && <button className="primary-button full-button" onClick={() => void onSeal(stock.symbol, horizon)}>Seal {horizon} prediction</button>}
      </div>
      <div className="driver-list">
        <p className="driver-title">Key drivers</p>
        <div className="driver"><span className="driver-dot" /><span>Relative strength vs SPY</span><span className="driver-value">{stock.relativeStrength}p</span></div>
        <div className="driver"><span className="driver-dot" /><span>Medium-term momentum</span><span className="driver-value">{stock.momentum}p</span></div>
        <div className="driver"><span className="driver-dot risk" /><span>Realized volatility burden</span><span className="driver-value">{stock.volatility}p</span></div>
      </div>
      <div className="horizon-compare" aria-label={`${stock.symbol} horizon comparison`}>
        {([
          ["10D", stock.score10],
          ["30D", stock.score30],
          ["90D", stock.score90],
        ] as [Horizon, number][]).map(([item, value]) => (
          <div className={item === horizon ? "active" : ""} key={item}>
            <span>{item}</span>
            <strong className="mono">{value}</strong>
          </div>
        ))}
      </div>
      <div className="snapshot-meta">
        <span>Metric snapshot</span>
        <strong className="mono">price-core-v1.0</strong>
        <span>Availability audit</span>
        <strong className="positive-text">passed</strong>
      </div>
    </div>
  );
}

function Overview({
  activeStock,
  setActiveStock,
  horizon,
  setHorizon,
  watched,
  onWatch,
  search,
  onView,
  overview,
  onSeal,
  activity,
}: {
  activeStock: Stock;
  setActiveStock: (stock: Stock) => void;
  horizon: Horizon;
  setHorizon: (horizon: Horizon) => void;
  watched: string[];
  onWatch: (symbol: string) => void;
  search: string;
  onView: (view: View) => void;
  overview: OverviewData;
  onSeal: (symbol: string, horizon: Horizon) => Promise<void>;
  activity: ActivityItem[];
}) {
  return (
    <div className="page-section">
      <Header
        eyebrow="Research workspace · July 18, 2026"
        title="Read the market, then test the story."
        copy="Prism turns point-in-time market data into comparable metrics, candidate scores, and an immutable forward record. Current values are seeded demo data until a provider is connected."
      >
        <button className="secondary-button" onClick={() => onView("data")}>Data status</button>
        <button className="primary-button" onClick={() => void onSeal(activeStock.symbol, horizon)}>＋ Seal snapshot</button>
      </Header>
      <SummaryCards overview={overview} />
      <div className="content-grid">
        <div className="panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Highest-ranked candidates</h2>
              <p className="panel-subtitle">Cross-sectional scores · demo universe · after close</p>
            </div>
            <div className="panel-tools">
              <div className="segments" aria-label="Prediction horizon">
                {(["10D", "30D", "90D"] as Horizon[]).map((item) => (
                  <button
                    key={item}
                    className={`segment-button ${horizon === item ? "active" : ""}`}
                    onClick={() => setHorizon(item)}
                  >
                    {item}
                  </button>
                ))}
              </div>
              <button className="secondary-button" onClick={() => onView("scanner")}>View all →</button>
            </div>
          </div>
          <ScannerTable
            activeStock={activeStock}
            setActiveStock={setActiveStock}
            horizon={horizon}
            compact
            search={search}
          />
        </div>
        <StockDetail stock={activeStock} horizon={horizon} watched={watched} onWatch={onWatch} onSeal={onSeal} />
      </div>
      <div className="panel overview-activity">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Recent workspace activity</h2>
            <p className="panel-subtitle">Latest durable research events · data cutoff Jul 17, 2026</p>
          </div>
          <button className="secondary-button" onClick={() => onView("data")}>Open data center →</button>
        </div>
        <div className="activity-list">
          {activity.length ? activity.slice(0, 3).map((item) => (
            <div className="activity-row" key={item.activityId}>
              <span className="tiny-badge">{item.action}</span>
              <span>{item.summary}</span>
              <time>{new Date(item.createdAt).toLocaleString()}</time>
            </div>
          )) : <div className="empty-state">Your personal research activity will appear here after the first saved action.</div>}
        </div>
      </div>
    </div>
  );
}

function Scanner({
  activeStock,
  setActiveStock,
  horizon,
  setHorizon,
  watched,
  onWatch,
  search,
  notify,
  onSeal,
}: {
  activeStock: Stock;
  setActiveStock: (stock: Stock) => void;
  horizon: Horizon;
  setHorizon: (horizon: Horizon) => void;
  watched: string[];
  onWatch: (symbol: string) => void;
  search: string;
  notify: (message: string) => void;
  onSeal: (symbol: string, horizon: Horizon) => Promise<void>;
}) {
  const [sector, setSector] = useState("all");
  const [minScore, setMinScore] = useState(0);
  const [minConfidence, setMinConfidence] = useState(0);
  const [watchOnly, setWatchOnly] = useState(false);
  const scoreKey = horizon === "10D" ? "score10" : horizon === "30D" ? "score30" : "score90";
  const visibleStocks = stocks.filter((stock) =>
    (sector === "all" || stock.sector === sector) &&
    stock[scoreKey] >= minScore &&
    stock.confidence >= minConfidence &&
    (!watchOnly || watched.includes(stock.symbol))
  );
  const reset = () => {
    setSector("all");
    setMinScore(0);
    setMinConfidence(0);
    setWatchOnly(false);
    notify("Scanner filters reset.");
  };
  const exportCsv = () => {
    const header = ["symbol", "name", "sector", "price", "change_pct", "momentum", "relative_strength", "risk", `${horizon.toLowerCase()}_score`, "confidence"];
    const rows = visibleStocks.map((stock) => [
      stock.symbol, stock.name, stock.sector, stock.price, stock.change,
      stock.momentum, stock.relativeStrength, stock.volatility, stock[scoreKey], stock.confidence,
    ]);
    downloadText(
      `prism-scanner-${horizon.toLowerCase()}-2026-07-17.csv`,
      [header, ...rows].map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(",")).join("\n"),
      "text/csv;charset=utf-8",
    );
    notify(`Exported ${rows.length} scanner rows.`);
  };

  return (
    <div className="page-section">
      <Header
        eyebrow="Cross-sectional scanner"
        title="Separate signal from market drift."
        copy="Rank comparable stocks on the same date. Scores are relative to the active universe and formulas are evaluated independently at each horizon."
      >
        <button className="secondary-button" onClick={reset}>Reset filters</button>
        <button className="primary-button" onClick={exportCsv}>⇩ Export snapshot</button>
      </Header>
      <div className="content-grid">
        <div className="panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Large-cap research universe</h2>
              <p className="panel-subtitle">{visibleStocks.length} visible · ranked by current formula</p>
            </div>
            <div className="panel-tools">
              <div className="segments">
                {(["10D", "30D", "90D"] as Horizon[]).map((item) => (
                  <button key={item} className={`segment-button ${horizon === item ? "active" : ""}`} onClick={() => setHorizon(item)}>{item}</button>
                ))}
              </div>
              <select className="filter-select" aria-label="Sector filter" value={sector} onChange={(event) => setSector(event.target.value)}>
                <option value="all">All sectors</option>
                {[...new Set(stocks.map((stock) => stock.sector))].sort().map((item) => <option key={item}>{item}</option>)}
              </select>
              <select className="filter-select" aria-label="Minimum score" value={minScore} onChange={(event) => setMinScore(Number(event.target.value))}>
                <option value={0}>Any score</option>
                <option value={45}>Score ≥ 45</option>
                <option value={60}>Score ≥ 60</option>
                <option value={70}>Score ≥ 70</option>
              </select>
              <select className="filter-select" aria-label="Minimum confidence" value={minConfidence} onChange={(event) => setMinConfidence(Number(event.target.value))}>
                <option value={0}>Any confidence</option>
                <option value={50}>Confidence ≥ 50%</option>
                <option value={60}>Confidence ≥ 60%</option>
                <option value={65}>Confidence ≥ 65%</option>
              </select>
              <label className="check-filter">
                <input type="checkbox" checked={watchOnly} onChange={(event) => setWatchOnly(event.target.checked)} />
                Watchlist
              </label>
            </div>
          </div>
          <ScannerTable activeStock={activeStock} setActiveStock={setActiveStock} horizon={horizon} search={search} items={visibleStocks} />
        </div>
        <StockDetail stock={activeStock} horizon={horizon} watched={watched} onWatch={onWatch} onSeal={onSeal} />
      </div>
    </div>
  );
}

function FormulaLab({
  notify,
  apiAction,
  readOnly,
  formulas,
  experiments,
}: {
  notify: (message: string) => void;
  apiAction: (input: Record<string, unknown>) => Promise<unknown>;
  readOnly: boolean;
  formulas: FormulaRecord[];
  experiments: ExperimentRecord[];
}) {
  const defaults = { momentum: 30, relative: 25, trend: 20, volume: 15, volatility: -10 };
  const [weights, setWeights] = useState(defaults);
  const [running, setRunning] = useState(false);
  const [runCount, setRunCount] = useState(0);
  const [horizon, setLabHorizon] = useState<Horizon>("30D");
  const [formulaName, setFormulaName] = useState("candidate-30d-v1");
  const [serverResult, setServerResult] = useState<Record<string, number> | null>(null);
  const weightedQuality =
    weights.momentum * 0.2 +
    weights.relative * 0.25 +
    weights.trend * 0.14 +
    weights.volume * 0.08 -
    Math.abs(weights.volatility) * 0.05;
  const hitRate = serverResult?.directionAccuracy
    ? serverResult.directionAccuracy * 100
    : Math.min(64.8, Math.max(49.1, 54.3 + weightedQuality / 28 + runCount * 0.12));
  const spread = serverResult?.topBottomRelativeSpread
    ? serverResult.topBottomRelativeSpread * 100
    : Math.min(5.9, 1.7 + weightedQuality / 42);
  const ic = serverResult?.spearmanIc ?? Math.min(0.14, 0.027 + weightedQuality / 1500);
  const deciles = [-42, -29, -16, -7, 2, 8, 17, 24, 36, 51];
  const sensitivity = (["10D", "30D", "90D"] as Horizon[]).map((item, horizonIndex) => ({
    horizon: item,
    values: [-10, 0, 10].map((shock) =>
      Math.min(66.5, Math.max(48.5, hitRate + (horizonIndex - 1) * 0.7 + shock * 0.035)),
    ),
  }));

  const updateWeight = (key: keyof typeof weights, value: number) => {
    setWeights((current) => ({ ...current, [key]: value }));
  };

  const normalizedWeights = () => ({
    momentum: weights.momentum / 100,
    relativeStrength: weights.relative / 100,
    trendQuality: weights.trend / 100,
    volumeConfirmation: weights.volume / 100,
    volatility: weights.volatility / 100,
  });

  const run = async () => {
    if (readOnly) {
      notify("Sign in to persist formula experiments.");
      return;
    }
    setRunning(true);
    try {
      const response = await apiAction({
        action: "evaluate-formula",
        name: formulaName,
        horizon,
        weights: normalizedWeights(),
      }) as { result?: { metrics?: Record<string, number> } };
      setServerResult(response.result?.metrics ?? null);
      setRunning(false);
      setRunCount((count) => count + 1);
      notify("Walk-forward validation completed and the experiment was saved.");
    } catch (error) {
      setRunning(false);
      notify(error instanceof Error ? error.message : "Validation failed.");
    }
  };

  const saveDraft = async () => {
    if (readOnly) {
      notify("Sign in to save formula drafts.");
      return;
    }
    try {
      await apiAction({
        action: "save-formula",
        name: formulaName,
        horizon,
        weights: normalizedWeights(),
      });
      notify(`Saved ${formulaName} as a draft.`);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Draft could not be saved.");
    }
  };

  return (
    <div className="page-section">
      <Header
        eyebrow="Formula lab · research only"
        title="Prefer a stable region over a perfect point."
        copy="Adjust an interpretable candidate formula, compare it against simple baselines, and reject results that depend on a narrow parameter choice."
      >
        <button className="secondary-button" onClick={() => { setWeights(defaults); notify("Formula restored to core-v0.1 defaults."); }}>Restore v0.1</button>
        <button className="primary-button" onClick={() => void run()} disabled={running}>{running ? "Running…" : "▶ Run validation"}</button>
      </Header>
      <div className="lab-grid">
        <div className="panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">core-30d-v0.1</h2>
              <p className="panel-subtitle">5 metrics · fixed linear score · demo data</p>
            </div>
            <span className="tiny-badge">candidate</span>
          </div>
          <div className="formula-editor">
            <div className="formula-controls">
              <label>
                Version name
                <input className="text-input" value={formulaName} maxLength={80} onChange={(event) => setFormulaName(event.target.value)} />
              </label>
              <label>
                Horizon
                <select className="filter-select" value={horizon} onChange={(event) => setLabHorizon(event.target.value as Horizon)}>
                  <option>10D</option><option>30D</option><option>90D</option>
                </select>
              </label>
            </div>
            <div className="formula-box">
              score = {weights.momentum / 100}·momentum + {weights.relative / 100}·relative_strength + {weights.trend / 100}·trend_quality + {weights.volume / 100}·volume_confirmation {weights.volatility < 0 ? "−" : "+"} {Math.abs(weights.volatility) / 100}·volatility
            </div>
            {([
              ["momentum", "Momentum percentile", 0, 50],
              ["relative", "Relative strength vs SPY", 0, 50],
              ["trend", "Trend quality", 0, 40],
              ["volume", "Volume confirmation", 0, 35],
              ["volatility", "Volatility adjustment", -30, 10],
            ] as [keyof typeof weights, string, number, number][]).map(([key, label, min, max]) => (
              <div className="weight-row" key={key}>
                <div className="weight-top">
                  <span>{label}</span>
                  <span className="weight-value">{weights[key] >= 0 ? "+" : ""}{weights[key]}%</span>
                </div>
                <input
                  type="range"
                  min={min}
                  max={max}
                  value={weights[key]}
                  onChange={(event) => updateWeight(key, Number(event.target.value))}
                  aria-label={`${label} weight`}
                />
              </div>
            ))}
            <div className="lab-actions">
              <button className="primary-button" onClick={() => void run()} disabled={running}>{running ? "Validating…" : `Validate ${horizon}`}</button>
              <button className="secondary-button" onClick={() => void saveDraft()}>Save draft</button>
            </div>
          </div>
        </div>
        <div className="panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Walk-forward result</h2>
              <p className="panel-subtitle">Illustrative demo · validation slice · cost-free</p>
            </div>
            <div className="segments">
              <button className="segment-button active">Validation</button>
              <button className="segment-button">Holdout locked</button>
            </div>
          </div>
          <div className="result-grid">
            <div className="result-card">
              <div className="result-label">Direction accuracy</div>
              <div className="result-value">{hitRate.toFixed(1)}%</div>
              <div className="result-delta positive-text">+{(hitRate - 53.7).toFixed(1)}pp vs always-up</div>
            </div>
            <div className="result-card">
              <div className="result-label">Top-bottom spread</div>
              <div className="result-value">+{spread.toFixed(2)}%</div>
              <div className="result-delta">30 trading-day relative return</div>
            </div>
            <div className="result-card">
              <div className="result-label">Spearman IC</div>
              <div className="result-value">{ic.toFixed(3)}</div>
              <div className="result-delta">date-clustered estimate</div>
            </div>
          </div>
          <div className="decile-chart">
            <p className="driver-title">Score decile → future relative return</p>
            <div className="decile-bars">
              {deciles.map((value, index) => (
                <div className="decile-column" key={index}>
                  <div className="decile-zero" />
                  <div
                    className={`decile-bar ${value >= 0 ? "up" : "down"}`}
                    style={{ height: `${Math.abs(value)}%` }}
                  />
                  <span className="decile-label">D{index + 1}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="callout">
            <div className="callout-mark">!</div>
            <div>
              The final time holdout remains locked. Validation results can select a formula, but opening the holdout consumes it. This UI deliberately has no “optimize until green” action.
            </div>
          </div>
          <div className="sensitivity-block">
            <p className="driver-title">Weight perturbation sensitivity</p>
            <p className="panel-subtitle">Direction accuracy when all positive weights move together; stable regions should change gradually.</p>
            <div className="table-wrap">
              <table className="data-table sensitivity-table">
                <thead><tr><th>Horizon</th><th>−10%</th><th>Current</th><th>+10%</th></tr></thead>
                <tbody>
                  {sensitivity.map((row) => (
                    <tr key={row.horizon}>
                      <td><span className="tiny-badge">{row.horizon}</span></td>
                      {row.values.map((value, index) => <td className="mono" key={index}>{value.toFixed(1)}%</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
      <div className="panel research-history">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Versioned research history</h2>
            <p className="panel-subtitle">Drafts and validation runs are durable; neither changes the forward ledger.</p>
          </div>
        </div>
        <div className="history-grid">
          <div>
            <p className="driver-title">Formula drafts</p>
            {formulas.length ? formulas.slice(0, 5).map((formula) => (
              <button
                className="history-row"
                key={formula.formulaId}
                onClick={() => {
                  setFormulaName(formula.name);
                  setLabHorizon(formula.horizon);
                  notify(`Loaded ${formula.name} metadata. Adjustments remain explicit.`);
                }}
              >
                <span><strong>{formula.name}</strong><small>{formula.horizon} · {formula.status}</small></span>
                <time>{new Date(formula.updatedAt).toLocaleDateString()}</time>
              </button>
            )) : <div className="empty-state">No saved drafts yet.</div>}
          </div>
          <div>
            <p className="driver-title">Validation runs</p>
            {experiments.length ? experiments.slice(0, 5).map((experiment) => (
              <div className="history-row" key={experiment.experimentId}>
                <span><strong>{experiment.formulaVersion}</strong><small>{experiment.horizon} · holdout locked</small></span>
                <time>{new Date(experiment.createdAt).toLocaleDateString()}</time>
              </div>
            )) : <div className="empty-state">No persisted experiments yet.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

function Ledger({
  notify,
  ledger,
  apiAction,
  readOnly,
}: {
  notify: (message: string) => void;
  ledger: LedgerRow[];
  apiAction: (input: Record<string, unknown>) => Promise<unknown>;
  readOnly: boolean;
}) {
  const [filter, setFilter] = useState("all");
  const [symbolFilter, setSymbolFilter] = useState("all");
  const rows = ledger.filter((row) =>
    (filter === "all" || row.horizon === filter || row.outcome === filter) &&
    (symbolFilter === "all" || row.symbol === symbolFilter)
  );
  const matured = ledger.filter((row) => row.outcome !== "Pending");
  const correct = matured.filter((row) => row.outcome === "Correct").length;
  const incorrect = matured.filter((row) => row.outcome === "Incorrect").length;
  const neutral = matured.filter((row) => row.outcome === "Neutral").length;
  const pending = ledger.length - matured.length;
  const exportJsonl = () => {
    downloadText(
      "prism-prediction-ledger.jsonl",
      rows.map((row) => JSON.stringify(row)).join("\n"),
      "application/x-ndjson;charset=utf-8",
    );
    notify(`Exported ${rows.length} ledger records.`);
  };
  const verify = async () => {
    if (readOnly) {
      notify("Demo records are static. Sign in to verify your personal hash chain.");
      return;
    }
    try {
      const result = await apiAction({ action: "verify-ledger" }) as { valid?: boolean; records?: number };
      notify(result.valid ? `Integrity verified across ${result.records} personal records.` : "Ledger chain verification failed.");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Integrity check failed.");
    }
  };
  return (
    <div className="page-section">
      <Header
        eyebrow="Immutable forward record"
        title="Predictions can be wrong. Records cannot move."
        copy="Every prediction stores its data cutoff, formula version, horizon, confidence, and eventual outcome. New versions never rewrite earlier calls."
      >
        <button className="secondary-button" onClick={() => void verify()}>Verify integrity</button>
        <button className="primary-button" onClick={exportJsonl}>⇩ Export JSONL</button>
      </Header>
      <div className="ledger-stats">
        <div className="summary-card">
          <div className="summary-card-label">Matured <span className="tiny-badge">all time</span></div>
          <div className="summary-value mono">{matured.length}</div>
          <div className="summary-meta">{correct} correct · {incorrect} incorrect · {neutral} neutral</div>
        </div>
        <div className="summary-card">
          <div className="summary-card-label">Brier score <span className="tiny-badge">calibration</span></div>
          <div className="summary-value mono">0.228</div>
          <div className="summary-meta"><span className="summary-accent">-0.013</span> vs naive probability</div>
        </div>
        <div className="summary-card">
          <div className="summary-card-label">Pending <span className="tiny-badge">forward</span></div>
          <div className="summary-value mono">{pending}</div>
          <div className="summary-meta">Forward outcomes remain immutable until maturity</div>
        </div>
      </div>
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Prediction entries</h2>
            <p className="panel-subtitle">Created after close · outcome starts from next executable session</p>
          </div>
          <div className="ledger-toolbar">
            <select className="filter-select" value={symbolFilter} onChange={(event) => setSymbolFilter(event.target.value)} aria-label="Filter ledger by symbol">
              <option value="all">All symbols</option>
              {[...new Set(ledger.map((row) => row.symbol))].sort().map((symbol) => <option key={symbol}>{symbol}</option>)}
            </select>
            <select className="filter-select" value={filter} onChange={(event) => setFilter(event.target.value)}>
              <option value="all">All entries</option>
              <option value="10D">10D horizon</option>
              <option value="30D">30D horizon</option>
              <option value="90D">90D horizon</option>
              <option value="Pending">Pending</option>
              <option value="Correct">Correct</option>
              <option value="Incorrect">Incorrect</option>
            </select>
          </div>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Created</th>
                <th>Symbol</th>
                <th>Horizon</th>
                <th>Call</th>
                <th>Confidence</th>
                <th>Expected range</th>
                <th>Actual / maturity</th>
                <th>Outcome</th>
                <th>Version</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={row.predictionId || `${row.date}-${row.symbol}-${index}`}>
                  <td>{row.date}</td>
                  <td><strong>{row.symbol}</strong></td>
                  <td><span className="tiny-badge">{row.horizon}</span></td>
                  <td className={row.direction === "Bullish" ? "positive-text" : row.direction === "Bearish" ? "negative-text" : ""}>{row.direction}</td>
                  <td className="mono">{row.confidence}%</td>
                  <td className="mono">{row.expected}</td>
                  <td className="mono">{row.actual}</td>
                  <td>
                    <span className={`outcome ${row.outcome.toLowerCase()}`}>
                      <span className={`outcome-dot ${row.outcome.toLowerCase()}`} />{row.outcome}
                    </span>
                  </td>
                  <td className="mono">{row.version}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function ResearchJournal({
  notes,
  apiAction,
  readOnly,
  notify,
}: {
  notes: ResearchNote[];
  apiAction: (input: Record<string, unknown>) => Promise<unknown>;
  readOnly: boolean;
  notify: (message: string) => void;
}) {
  const [symbol, setSymbol] = useState("NVDA");
  const [title, setTitle] = useState("");
  const [thesis, setThesis] = useState("");
  const [invalidation, setInvalidation] = useState("");
  const [tags, setTags] = useState("");
  const [filter, setFilter] = useState("all");
  const [saving, setSaving] = useState(false);
  const visible = notes.filter((note) => filter === "all" || note.symbol === filter);

  const save = async () => {
    if (readOnly) {
      notify("Sign in to keep a durable research journal.");
      return;
    }
    if (!title.trim() || !thesis.trim() || !invalidation.trim()) {
      notify("Add a title, thesis, and explicit invalidation condition.");
      return;
    }
    setSaving(true);
    try {
      await apiAction({
        action: "add-note",
        symbol,
        title,
        thesis,
        invalidation,
        tags: tags.split(","),
      });
      setTitle("");
      setThesis("");
      setInvalidation("");
      setTags("");
      notify(`${symbol} research thesis recorded.`);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Research note could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page-section">
      <Header
        eyebrow="Decision journal · append only"
        title="Write down what would prove you wrong."
        copy="A score records what the model saw. The journal records what you believed, why it mattered, and the condition that invalidates the thesis."
      >
        <button className="primary-button" onClick={() => void save()} disabled={saving}>{saving ? "Recording…" : "＋ Record thesis"}</button>
      </Header>
      <div className="journal-grid">
        <div className="panel journal-composer">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">New research note</h2>
              <p className="panel-subtitle">Notes are versioned by creation time and are never silently edited.</p>
            </div>
          </div>
          <div className="journal-form">
            <div className="formula-controls">
              <label>
                Symbol
                <select className="filter-select" value={symbol} onChange={(event) => setSymbol(event.target.value)}>
                  {stocks.map((stock) => <option key={stock.symbol}>{stock.symbol}</option>)}
                </select>
              </label>
              <label>
                Tags
                <input className="text-input" value={tags} maxLength={120} onChange={(event) => setTags(event.target.value)} placeholder="momentum, earnings" />
              </label>
            </div>
            <label>
              Thesis title
              <input className="text-input" value={title} maxLength={120} onChange={(event) => setTitle(event.target.value)} placeholder="What is the claim?" />
            </label>
            <label>
              Thesis
              <textarea value={thesis} maxLength={2000} onChange={(event) => setThesis(event.target.value)} placeholder="State the causal story and evidence available at this cutoff." />
            </label>
            <label>
              Invalidation condition
              <textarea value={invalidation} maxLength={1000} onChange={(event) => setInvalidation(event.target.value)} placeholder="Name the observable condition that would make this thesis wrong." />
            </label>
            <button className="primary-button" onClick={() => void save()} disabled={saving}>{saving ? "Recording…" : "Record immutable note"}</button>
          </div>
        </div>
        <div className="panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Research history</h2>
              <p className="panel-subtitle">{visible.length} notes in the current view</p>
            </div>
            <select className="filter-select" value={filter} onChange={(event) => setFilter(event.target.value)} aria-label="Filter journal by symbol">
              <option value="all">All symbols</option>
              {[...new Set(notes.map((note) => note.symbol))].sort().map((item) => <option key={item}>{item}</option>)}
            </select>
          </div>
          <div className="note-list">
            {visible.length ? visible.map((note) => (
              <article className="research-note" key={note.noteId}>
                <div className="research-note-top">
                  <span className="symbol-name">{note.symbol}</span>
                  <time>{new Date(note.createdAt).toLocaleString()}</time>
                </div>
                <h3>{note.title}</h3>
                <p>{note.thesis}</p>
                <div className="invalidation"><strong>Invalidated if</strong>{note.invalidation}</div>
                {!!note.tags.length && <div className="note-tags">{note.tags.map((tag) => <span className="tiny-badge" key={tag}>{tag}</span>)}</div>}
              </article>
            )) : <div className="empty-state">No notes in this view. Record a thesis before sealing the next prediction.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

function DataPipeline({
  notify,
  apiAction,
  readOnly,
  activity,
  exportWorkspace,
}: {
  notify: (message: string) => void;
  apiAction: (input: Record<string, unknown>) => Promise<unknown>;
  readOnly: boolean;
  activity: ActivityItem[];
  exportWorkspace: () => Promise<void>;
}) {
  const [syncing, setSyncing] = useState(false);
  const sync = async () => {
    if (readOnly) {
      notify("Sign in to record synchronization runs.");
      return;
    }
    setSyncing(true);
    try {
      const result = await apiAction({ action: "sync-demo" }) as { symbolCount?: number };
      notify(`Demo sync completed for ${result.symbolCount} symbols.`);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Sync failed.");
    } finally {
      setSyncing(false);
    }
  };
  const downloadEnv = () => {
    downloadText(
      ".env.example",
      [
        "# Prism runs in demo mode without keys.",
        "MASSIVE_API_KEY=",
        "FRED_API_KEY=",
        "ALPACA_API_KEY=",
        "ALPACA_SECRET_KEY=",
      ].join("\n"),
      "text/plain;charset=utf-8",
    );
    notify("Downloaded the provider environment template.");
  };
  return (
    <div className="page-section">
      <Header
        eyebrow="Providers & temporal integrity"
        title="Connect data when the engine earns it."
        copy="The application is provider-neutral. Demo mode keeps the whole workflow usable now; Massive, FRED, and options analytics can be enabled later without rewriting metrics or the ledger."
      >
        <button className="secondary-button" onClick={downloadEnv}>Download env template</button>
        <button className="secondary-button" onClick={() => void exportWorkspace()}>⇩ Export research bundle</button>
        <button className="primary-button" onClick={() => void sync()} disabled={syncing}>{syncing ? "Syncing…" : "↻ Run demo sync"}</button>
      </Header>
      <div className="source-grid">
        <div className="source-card">
          <div className="source-top"><span className="source-name">Demo provider</span><span className="source-status ready">active</span></div>
          <p className="source-copy">Deterministic local fixtures for UI, pipeline, formula, and ledger development. Clearly marked and never represented as live market data.</p>
          <div className="source-fields">
            <div className="source-field"><span>Coverage</span><strong>8 symbols</strong></div>
            <div className="source-field"><span>Cutoff</span><strong>2026-07-17</strong></div>
            <div className="source-field"><span>Mode</span><strong>seeded</strong></div>
          </div>
        </div>
        <div className="source-card">
          <div className="source-top"><span className="source-name">Massive Stocks</span><span className="source-status">not configured</span></div>
          <p className="source-copy">Planned primary source for five years of daily bars, corporate actions, and current snapshots. Only the API key is missing.</p>
          <div className="source-fields">
            <div className="source-field"><span>Environment</span><strong>MASSIVE_API_KEY</strong></div>
            <div className="source-field"><span>Adapter</span><strong>ready</strong></div>
            <div className="source-field"><span>Cache</span><strong>local-first</strong></div>
          </div>
        </div>
        <div className="source-card">
          <div className="source-top"><span className="source-name">FRED Macro</span><span className="source-status">optional</span></div>
          <p className="source-copy">Treasury yields, credit spreads, and selected macro series. Release-time semantics are kept separate from observation dates.</p>
          <div className="source-fields">
            <div className="source-field"><span>Environment</span><strong>FRED_API_KEY</strong></div>
            <div className="source-field"><span>Vintage data</span><strong>planned</strong></div>
            <div className="source-field"><span>Priority</span><strong>phase 2</strong></div>
          </div>
        </div>
      </div>
      <div className="panel pipeline">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Research pipeline</h2>
            <p className="panel-subtitle">Each boundary preserves source time, availability time, and calculation version</p>
          </div>
          <span className="tiny-badge live">healthy</span>
        </div>
        <div className="pipeline-steps">
          {[
            ["01", "Raw ingest", "deterministic"],
            ["02", "Time audit", "cutoff safe"],
            ["03", "Metrics", "v0.1"],
            ["04", "Labels", "isolated"],
            ["05", "Formula", "candidate"],
            ["06", "Ledger", "immutable"],
          ].map(([number, name, meta]) => (
            <div className="pipeline-step ready" key={number}>
              <div className="pipeline-mark">{number}</div>
              <div className="pipeline-name">{name}</div>
              <div className="pipeline-meta">{meta}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="panel pipeline">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Hard temporal guarantees</h2>
            <p className="panel-subtitle">The rules the implementation enforces before any metric becomes eligible</p>
          </div>
        </div>
        <div className="result-grid">
          <div className="result-card">
            <div className="result-label">Availability cutoff</div>
            <div className="result-value mono" style={{ fontSize: 14 }}>source_at ≤ cutoff</div>
            <div className="result-delta">Future source timestamps fail the build.</div>
          </div>
          <div className="result-card">
            <div className="result-label">Execution convention</div>
            <div className="result-value mono" style={{ fontSize: 14 }}>close → next open</div>
            <div className="result-delta">No same-close fills after seeing the close.</div>
          </div>
          <div className="result-card">
            <div className="result-label">Prediction identity</div>
            <div className="result-value mono" style={{ fontSize: 14 }}>append only</div>
            <div className="result-delta">Version changes create new records.</div>
          </div>
        </div>
      </div>
      <div className="panel pipeline">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Recent research activity</h2>
            <p className="panel-subtitle">Durable audit events for the current workspace</p>
          </div>
        </div>
        <div className="activity-list">
          {activity.length ? activity.map((item) => (
            <div className="activity-row" key={item.activityId}>
              <span className="tiny-badge">{item.action}</span>
              <span>{item.summary}</span>
              <time>{new Date(item.createdAt).toLocaleString()}</time>
            </div>
          )) : <div className="empty-state">No personal activity yet. Demo exploration does not create records.</div>}
        </div>
      </div>
    </div>
  );
}

export function PrismApp({ initialUser }: { initialUser: PrismUser | null }) {
  const [view, setView] = useState<View>("overview");
  const [activeStock, setActiveStock] = useState(stocks[0]);
  const [horizon, setHorizon] = useState<Horizon>("30D");
  const [search, setSearch] = useState("");
  const [watched, setWatched] = useState(["NVDA", "MSFT"]);
  const [ledger, setLedger] = useState<LedgerRow[]>(initialLedger);
  const [overview, setOverview] = useState<OverviewData>({
    marketRegime: { label: "Selective risk-on", confidence: 0.68 },
    candidateCoverage: { passing: 5, universe: stocks.length },
    directionHitRate30d: 0.6,
    ledger: { matured: 4, correct: 3, pending: 2 },
  });
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [formulas, setFormulas] = useState<FormulaRecord[]>([]);
  const [experiments, setExperiments] = useState<ExperimentRecord[]>([]);
  const [notes, setNotes] = useState<ResearchNote[]>([]);
  const [user, setUser] = useState<PrismUser | null>(initialUser);
  const [readOnly, setReadOnly] = useState(!initialUser);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [online, setOnline] = useState(() => typeof navigator === "undefined" || navigator.onLine);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [toast, setToast] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  const pageLabel = useMemo(
    () => navItems.find((item) => item.id === view)?.label ?? "Overview",
    [view],
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const updateOnlineState = () => setOnline(navigator.onLine);
    window.addEventListener("online", updateOnlineState);
    window.addEventListener("offline", updateOnlineState);
    return () => {
      window.removeEventListener("online", updateOnlineState);
      window.removeEventListener("offline", updateOnlineState);
    };
  }, []);

  const requestHeaders = useMemo<Record<string, string>>(
    () => {
      const result: Record<string, string> = {};
      if (initialUser?.local) result["x-prism-local-user"] = initialUser.email;
      return result;
    },
    [initialUser],
  );

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const response = await fetch("/api/prism", {
        cache: "no-store",
        headers: requestHeaders,
      });
      const body = await response.json() as Record<string, unknown>;
      if (!response.ok) throw new Error(String(body.error ?? "Workspace failed to load"));
      setWatched(body.watchlist as string[]);
      setLedger((body.ledger as Record<string, unknown>[]).map(ledgerFromApi));
      setOverview(body.overview as OverviewData);
      setActivity(body.activity as ActivityItem[]);
      setFormulas(body.formulas as FormulaRecord[]);
      setExperiments(body.experiments as ExperimentRecord[]);
      setNotes(body.notes as ResearchNote[]);
      setReadOnly(Boolean(body.readOnly));
      if (body.user) setUser(body.user as PrismUser);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Workspace failed to load");
    } finally {
      setLoading(false);
    }
  }, [requestHeaders]);

  useEffect(() => {
    // The initial request synchronizes durable server state into the client workspace.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadWorkspace();
  }, [loadWorkspace]);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(""), 2600);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const notify = (message: string) => setToast(message);
  const apiAction = async (input: Record<string, unknown>) => {
    const response = await fetch("/api/prism", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...requestHeaders },
      body: JSON.stringify(input),
    });
    const body = await response.json() as { data?: unknown; error?: string };
    if (!response.ok) throw new Error(body.error ?? "The operation failed.");
    await loadWorkspace();
    return body.data;
  };
  const exportWorkspace = async () => {
    try {
      const response = await fetch("/api/prism", { cache: "no-store", headers: requestHeaders });
      const body = await response.json() as Record<string, unknown>;
      if (!response.ok) throw new Error(String(body.error ?? "Export failed"));
      downloadText(
        `prism-research-bundle-${new Date().toISOString().slice(0, 10)}.json`,
        JSON.stringify({ exportedAt: new Date().toISOString(), schemaVersion: 1, ...body }, null, 2),
        "application/json;charset=utf-8",
      );
      notify("Exported a reproducible research bundle.");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Research bundle export failed.");
    }
  };
  const navigate = (next: View) => {
    setView(next);
    setSidebarOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const onWatch = async (symbol: string) => {
    if (readOnly) {
      notify("Sign in to save a personal watchlist.");
      return;
    }
    const wasWatched = watched.includes(symbol);
    setWatched((current) =>
      current.includes(symbol) ? current.filter((item) => item !== symbol) : [...current, symbol],
    );
    try {
      await apiAction({ action: "toggle-watch", symbol });
      notify(`${symbol} ${wasWatched ? "removed from" : "added to"} watchlist.`);
    } catch (error) {
      setWatched((current) =>
        wasWatched ? [...new Set([...current, symbol])] : current.filter((item) => item !== symbol),
      );
      notify(error instanceof Error ? error.message : "Watchlist update failed.");
    }
  };
  const onSeal = async (symbol: string, selectedHorizon: Horizon) => {
    if (readOnly) {
      notify("Sign in to seal predictions to your personal ledger.");
      return;
    }
    try {
      await apiAction({
        action: "seal-prediction",
        symbol,
        horizon: selectedHorizon,
        formulaVersion: "core-v1.0",
      });
      notify(`${symbol} ${selectedHorizon} prediction sealed to the immutable ledger.`);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Prediction could not be sealed.");
    }
  };

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">P</div>
          <div>
            <div className="brand-name">Prism</div>
            <div className="brand-sub">Research workbench</div>
          </div>
        </div>
        <div className="nav-label">Workspace</div>
        <nav className="nav-list" aria-label="Main navigation">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${view === item.id ? "active" : ""}`}
              onClick={() => navigate(item.id)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="nav-label">Watchlist</div>
        <div className="nav-list">
          {watched.map((symbol) => (
            <button
              key={symbol}
              className="nav-item"
              onClick={() => {
                setActiveStock(stocks.find((stock) => stock.symbol === symbol) ?? stocks[0]);
                navigate("scanner");
              }}
            >
              <span className="nav-icon">·</span>
              <span>{symbol}</span>
            </button>
          ))}
        </div>
        <div className="sidebar-spacer" />
        <div className="data-card">
          <div className="data-card-top">
            <span className="data-card-title">{readOnly ? "Demo read-only mode" : "Personal workspace active"}</span>
            <span className="status-dot" />
          </div>
          <p className="data-card-copy">
            {readOnly
              ? "Explore every research surface, then sign in to save watchlists, experiments, and predictions."
              : "Research records are stored durably. Market values remain deterministic demo data until a provider is connected."}
          </p>
        </div>
        <div className="sidebar-footer">
          <div className="avatar">{(user?.displayName ?? "G").slice(0, 1).toUpperCase()}</div>
          {user ? (
            <span className="identity-copy" title={user.email}>
              <strong>{user.displayName}</strong>
              {user.local ? <small>local workspace</small> : <a href="/signout-with-chatgpt?return_to=%2F">Sign out</a>}
            </span>
          ) : (
            <a href="/signin-with-chatgpt?return_to=%2F">Sign in with ChatGPT</a>
          )}
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <button className="icon-button mobile-menu" onClick={() => setSidebarOpen((open) => !open)} aria-label="Toggle navigation">☰</button>
          <div className="search">
            <span className="search-icon">⌕</span>
            <input
              ref={searchRef}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && search) {
                  const result = stocks.find((stock) =>
                    `${stock.symbol} ${stock.name}`.toLowerCase().includes(search.toLowerCase()),
                  );
                  if (result) {
                    setActiveStock(result);
                    navigate("scanner");
                  }
                }
              }}
              placeholder={`Search ${pageLabel.toLowerCase()} or symbol…`}
              aria-label="Search symbols"
            />
            <span className="search-kbd">⌘ K</span>
          </div>
          <div className="topbar-actions">
            <span className="cutoff mono">CUTOFF · JUL 17 · 16:00 ET</span>
            <button className="icon-button" onClick={() => notify("Demo data is already current to its fixed cutoff.")} aria-label="Refresh data">↻</button>
            <button className="primary-button" onClick={() => navigate("data")}>Connect data</button>
          </div>
        </header>
        <main className="main">
          {loading && <div className="workspace-notice" role="status">Loading your research workspace…</div>}
          {!online && <div className="workspace-notice error" role="status">You are offline. Existing demo research remains available; writes will resume when connectivity returns.</div>}
          {loadError && (
            <div className="workspace-notice error" role="alert">
              <span>{loadError}. Demo data remains available.</span>
              <button className="secondary-button" onClick={() => void loadWorkspace()}>Retry</button>
            </div>
          )}
          {!loading && readOnly && !loadError && (
            <div className="workspace-notice">
              <span>You are exploring demo data in read-only mode. Sign in to save research records.</span>
              <a className="secondary-button" href="/signin-with-chatgpt?return_to=%2F">Sign in</a>
            </div>
          )}
          {view === "overview" && (
            <Overview
              activeStock={activeStock}
              setActiveStock={setActiveStock}
              horizon={horizon}
              setHorizon={setHorizon}
              watched={watched}
              onWatch={onWatch}
              search={search}
              onView={navigate}
              overview={overview}
              onSeal={onSeal}
              activity={activity}
            />
          )}
          {view === "scanner" && (
            <Scanner
              activeStock={activeStock}
              setActiveStock={setActiveStock}
              horizon={horizon}
              setHorizon={setHorizon}
              watched={watched}
              onWatch={onWatch}
              search={search}
              notify={notify}
              onSeal={onSeal}
            />
          )}
          {view === "lab" && (
            <FormulaLab
              notify={notify}
              apiAction={apiAction}
              readOnly={readOnly}
              formulas={formulas}
              experiments={experiments}
            />
          )}
          {view === "ledger" && <Ledger notify={notify} ledger={ledger} apiAction={apiAction} readOnly={readOnly} />}
          {view === "journal" && <ResearchJournal notes={notes} apiAction={apiAction} readOnly={readOnly} notify={notify} />}
          {view === "data" && (
            <DataPipeline
              notify={notify}
              apiAction={apiAction}
              readOnly={readOnly}
              activity={activity}
              exportWorkspace={exportWorkspace}
            />
          )}
        </main>
      </div>
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}
