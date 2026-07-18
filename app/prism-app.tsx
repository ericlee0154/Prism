"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

type Language = "zh" | "en";
type View = "overview" | "scanner" | "metrics" | "backtest" | "data";
type Horizon = "10D" | "30D" | "90D";

type PrismUser = { displayName: string; email: string; local: boolean };
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
  signal: string;
  dataQuality: number;
};
type Forecast = {
  status: "complete" | "insufficient_data";
  version: string;
  horizon_sessions: number;
  sample_count: number;
  median_return?: number | null;
  p10_return?: number | null;
  p90_return?: number | null;
  positive_probability?: number | null;
  analog_dates?: string[];
};
type RangeAnalysis = {
  analysis_id: string;
  symbol: string;
  requested_start: string;
  requested_end: string;
  actual_start: string;
  actual_end: string;
  bar_count: number;
  data_cutoff: string;
  source: string;
  metric_version: string;
  metrics: Record<string, number>;
  coverage_warnings: string[];
  forecasts: Record<string, Forecast>;
  series: { date: string; close: number }[];
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
};
type Pipeline = {
  status: "ready" | "empty";
  provider: string | null;
  provider_configured: boolean;
  market: MarketSummary;
  sync_runs: {
    sync_id: string;
    started_at: string;
    provider: string;
    symbols: string[];
    status: string;
    rows_written: number;
    error: string | null;
  }[];
  backtests: Backtest[];
  analyses: unknown[];
  metric_version: string;
};

const API_BASE = "/api/v1";
const LanguageContext = createContext<Language>("zh");
const DEFAULT_SYNC_END = new Date().toISOString().slice(0, 10);
const DEFAULT_SYNC_START = new Date(
  new Date(`${DEFAULT_SYNC_END}T12:00:00Z`).getTime() - 366 * 2 * 86_400_000,
).toISOString().slice(0, 10);
const DEFAULT_ANALYSIS_START = new Date(
  new Date(`${DEFAULT_SYNC_END}T12:00:00Z`).setUTCFullYear(
    new Date(`${DEFAULT_SYNC_END}T12:00:00Z`).getUTCFullYear() - 10,
  ),
).toISOString().slice(0, 10);

const translations = {
  overview: { zh: "總覽", en: "Overview" },
  scanner: { zh: "市場掃描", en: "Market scanner" },
  metrics: { zh: "區間 Metrics", en: "Range metrics" },
  backtests: { zh: "回測", en: "Backtests" },
  dataPipeline: { zh: "資料與管線", en: "Data & pipeline" },
  workspace: { zh: "工作區", en: "Workspace" },
  localWorkbench: { zh: "本機研究工作台", en: "Local research workbench" },
  realStoredData: { zh: "真實儲存資料", en: "Real stored data" },
  noMarketData: { zh: "沒有市場資料", en: "No market data" },
  noFallback: { zh: "沒有 demo fallback", en: "No demo fallback" },
  emptyByDesign: { zh: "刻意保持空白", en: "EMPTY BY DESIGN" },
  noStoredMarketData: { zh: "尚未儲存市場資料", en: "No stored market data" },
  emptyExplanation: {
    zh: "Prism 不會補入範例價格、分數、預測或回測結果。請先從 Massive 同步股票資料。",
    en: "Prism will not substitute sample prices, scores, predictions, or backtest results. Synchronize symbols from Massive first.",
  },
  openDataSync: { zh: "開啟資料同步", en: "Open data sync" },
  loading: { zh: "正在讀取本機 DuckDB…", en: "Loading local DuckDB…" },
  retry: { zh: "重試", en: "Retry" },
  apiError: {
    zh: "本機 API 無法使用；畫面不會顯示替代資料。",
    en: "The local API is unavailable; no substitute data is displayed.",
  },
  filterSymbols: { zh: "篩選已儲存股票…", en: "Filter stored symbols…" },
  syncData: { zh: "同步資料", en: "Sync data" },
  noData: { zh: "無資料", en: "No data" },
  researchStored: { zh: "只研究真正儲存的資料。", en: "Research what is actually stored." },
  researchStoredCopy: {
    zh: "Prism 僅使用本機 DuckDB 中的 Massive 日線。缺失、過期或失敗的資料會如實標示。",
    en: "Prism uses only Massive daily bars in local DuckDB. Missing, stale, or failed data remains visibly missing.",
  },
  storedUniverse: { zh: "已儲存股票池", en: "Stored universe" },
  realDailyBars: { zh: "筆真實日線", en: "real daily bars" },
  latestObservation: { zh: "最新觀察日", en: "Latest observation" },
  positiveBreadth: { zh: "20 日正報酬廣度", en: "Positive 20-session breadth" },
  latestIc: { zh: "最新 Walk-forward IC", en: "Latest walk-forward IC" },
  noBacktest: { zh: "尚未執行回測", en: "No backtest has been run" },
  viewScanner: { zh: "查看掃描器 →", en: "View scanner →" },
  realCrossSection: { zh: "同一 cutoff 的真實橫截面 metrics", en: "Real cross-sectional metrics at one cutoff" },
  symbol: { zh: "股票", en: "Symbol" },
  latestClose: { zh: "最新收盤", en: "Latest close" },
  return5: { zh: "5 日報酬", en: "5-session return" },
  return20: { zh: "20 日報酬", en: "20-session return" },
  volatility20: { zh: "20 日年化波動", en: "20-session volatility" },
  drawdown60: { zh: "60 日回撤", en: "60-session drawdown" },
  score: { zh: "分數", en: "score" },
  rows: { zh: "筆數", en: "Rows" },
  noMatch: { zh: "沒有符合的已儲存股票。", en: "No stored symbols match this filter." },
  relativeScore: { zh: "相對 metric 分數", en: "relative metric score" },
  stored: { zh: "已儲存", en: "stored" },
  crossRanks: { zh: "橫截面百分位", en: "Cross-sectional ranks" },
  momentum20: { zh: "20 日動能", en: "20-session momentum" },
  relativeStrength: { zh: "相對強度", en: "Relative strength" },
  realizedVol: { zh: "已實現波動", en: "Realized volatility" },
  metricVersion: { zh: "Metric 版本", en: "Metric version" },
  availableAt: { zh: "資料可用時間", en: "Available at" },
  dataQuality: { zh: "資料完整度", en: "Data quality" },
  compareReal: { zh: "比較真實觀察資料。", en: "Compare real observations." },
  compareRealCopy: {
    zh: "分數只由目前儲存的股票池計算，僅供研究，不是投資建議或交易指令。",
    en: "Scores use only the stored universe and are research metrics, not recommendations or order instructions.",
  },
  rangeMetricsTitle: { zh: "用你選擇的時間區間計算。", en: "Calculate over your selected timeline." },
  rangeMetrics: { zh: "Metrics 時間區間", en: "Metrics timeline" },
  rangeMetricsCopy: {
    zh: "拖曳起點與終點，Prism 只使用該區間內、在 cutoff 前可得的真實日線計算 metrics 與歷史類比 forecast。",
    en: "Drag the start and end points. Prism uses only real bars available inside that interval for metrics and historical-analog forecasts.",
  },
  selectStock: { zh: "選擇股票", en: "Select symbol" },
  startDate: { zh: "開始日期", en: "Start date" },
  endDate: { zh: "結束日期", en: "End date" },
  calculate: { zh: "計算 Metrics 與 Forecast", en: "Calculate metrics & forecast" },
  calculating: { zh: "計算中…", en: "Calculating…" },
  requestedRange: { zh: "請求區間", en: "Requested range" },
  actualCoverage: { zh: "實際資料覆蓋", en: "Actual coverage" },
  sessions: { zh: "個交易日", en: "sessions" },
  coverageGap: {
    zh: "實際覆蓋短於請求區間；Prism 沒有補值。可能是方案歷史限制或尚未同步。",
    en: "Actual coverage is shorter than requested. Prism did not fill the gap; the plan limit or sync coverage may be responsible.",
  },
  metricsSnapshot: { zh: "區間末端 Metrics", en: "End-of-range metrics" },
  forecast: { zh: "未來歷史類比 Forecast", en: "Historical-analog forecast" },
  medianReturn: { zh: "中位數報酬", en: "Median return" },
  range1090: { zh: "10–90% 區間", en: "10–90% range" },
  positiveProbability: { zh: "正報酬比例", en: "Positive-return share" },
  analogSamples: { zh: "類似樣本", en: "analog samples" },
  insufficient: { zh: "樣本不足，不產生 forecast", en: "Insufficient samples; no forecast produced" },
  forecastDisclaimer: {
    zh: "Forecast 是所選歷史區間內相似 metric 狀態的結果分布，不是即時報價、保證或交易建議。",
    en: "Forecasts are outcome distributions for similar metric states inside the selected history, not live quotes, guarantees, or trade advice.",
  },
  walkForward: { zh: "Walk-forward 驗證・只用已儲存日線", en: "Walk-forward validation · stored bars only" },
  testWithoutInventing: { zh: "不捏造結果地測試 metrics。", en: "Test metrics without inventing outcomes." },
  testWithoutInventingCopy: {
    zh: "所有結果都由本機 Massive 歷史重算；資料不足時只會回報 insufficient_data。",
    en: "Every result is recomputed from local Massive history; insufficient data is reported as insufficient_data.",
  },
  runBacktest: { zh: "執行真實回測", en: "Run real backtest" },
  running: { zh: "執行中…", en: "Running…" },
  noBacktestResults: { zh: "尚無回測結果", en: "No backtest results" },
  backtestEmptyCopy: {
    zh: "先同步足夠期間與多檔股票，再執行第一個 walk-forward 回測。",
    en: "Synchronize sufficient history across several symbols, then run the first walk-forward backtest.",
  },
  meanIc: { zh: "平均 Spearman IC", en: "Mean Spearman IC" },
  spread: { zh: "Top-bottom spread", en: "Top-bottom spread" },
  directionAccuracy: { zh: "方向準確率", en: "Direction accuracy" },
  observations: { zh: "觀察值", en: "Observations" },
  methodLimits: { zh: "方法限制", en: "Method limits" },
  localOnly: { zh: "Massive → DuckDB・僅限本機", en: "Massive → DuckDB · local only" },
  syncRealHistory: { zh: "同步真實歷史資料。", en: "Synchronize real history." },
  syncRealHistoryCopy: {
    zh: "輸入你要的股票與日期；Prism 不會建立預設股票池，也不會在失敗時替換 demo 日線。",
    en: "Enter the symbols and dates you want. Prism creates no default universe and substitutes no demo bars on failure.",
  },
  newSync: { zh: "新增同步", en: "New synchronization" },
  keyLocal: { zh: "Massive key 只存在本機 API 程序。", en: "Your Massive key remains in the local API process." },
  symbols: { zh: "股票代碼", en: "Symbols" },
  syncToDuckdb: { zh: "同步至 DuckDB", en: "Synchronize to DuckDB" },
  syncing: { zh: "正在同步真實日線…", en: "Synchronizing real bars…" },
  planLimit: {
    zh: "免費方案通常限制兩年歷史與每分鐘五次請求；實際回傳範圍會在完成後顯示。",
    en: "The free plan typically limits history to two years and five calls per minute; actual returned coverage is shown after completion.",
  },
  localStorage: { zh: "本機儲存", en: "Local storage" },
  provider: { zh: "資料來源", en: "Provider" },
  configured: { zh: "Massive 已設定", en: "Massive configured" },
  missingKey: { zh: "缺少 API key", en: "Missing API key" },
  dailyBars: { zh: "日線筆數", en: "Daily bars" },
  duckdbFile: { zh: "DuckDB 檔案", en: "DuckDB file" },
  firstObservation: { zh: "最早觀察日", en: "First observation" },
  syncHistory: { zh: "同步歷程", en: "Synchronization history" },
  syncHistoryCopy: {
    zh: "部分成功與失敗都會保留，且永遠不觸發 fallback。",
    en: "Partial and failed runs remain visible and never trigger fallback.",
  },
  noSync: { zh: "尚未執行同步。", en: "No synchronization has been run." },
  completed: { zh: "完成", en: "complete" },
  partial: { zh: "部分完成", en: "partial" },
  failed: { zh: "失敗", en: "failed" },
  cutoff: { zh: "資料截止", en: "Cutoff" },
  volumeZ: { zh: "成交量 z-score", en: "Volume z-score" },
  distanceMa: { zh: "距離 20 日均線", en: "Distance MA20" },
  broadPositive: { zh: "廣泛正向", en: "Broad positive breadth" },
  broadNegative: { zh: "廣泛負向", en: "Broad negative breadth" },
  mixedBreadth: { zh: "多空混合", en: "Mixed breadth" },
  positiveSetup: { zh: "相對狀態偏正向", en: "Positive relative setup" },
  weakSetup: { zh: "相對狀態偏弱", en: "Weak relative setup" },
  neutralSetup: { zh: "沒有明顯相對優勢", en: "No strong relative edge" },
  localResearcher: { zh: "本機研究者", en: "Local researcher" },
  language: { zh: "EN", en: "中文" },
} as const;

type TranslationKey = keyof typeof translations;
function useI18n() {
  const language = useContext(LanguageContext);
  return {
    language,
    t: (key: TranslationKey) => translations[key][language],
  };
}

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
  if (!response.ok) throw new Error(body.detail ?? `API ${response.status}`);
  return body;
}

const isoDate = (value: string) => value.slice(0, 10);
const dateToDay = (value: string) => Math.floor(new Date(`${isoDate(value)}T12:00:00Z`).getTime() / 86_400_000);
const dayToDate = (value: number) => new Date(value * 86_400_000).toISOString().slice(0, 10);
const formatPercent = (value: number | null | undefined, digits = 2) => value == null ? "—" : `${(value * 100).toFixed(digits)}%`;
const scoreFor = (stock: Stock, horizon: Horizon) => horizon === "10D" ? stock.score10 : horizon === "30D" ? stock.score30 : stock.score90;

function useFormatters() {
  const { language } = useI18n();
  return {
    date: (value: string | null) => value
      ? new Intl.DateTimeFormat(language === "zh" ? "zh-TW" : "en-US", {
        year: "numeric", month: "short", day: "numeric", timeZone: "America/New_York",
      }).format(new Date(value))
      : "—",
    bytes: (bytes: number) => {
      if (!bytes) return "0 B";
      const units = ["B", "KB", "MB", "GB", "TB"];
      const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
      return `${(bytes / 1024 ** index).toFixed(index > 1 ? 2 : 0)} ${units[index]}`;
    },
  };
}

function Header({ eyebrow, title, copy, children }: { eyebrow: string; title: string; copy: string; children?: React.ReactNode }) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1 className="page-title">{title}</h1><p className="page-copy">{copy}</p></div>{children ? <div className="heading-actions">{children}</div> : null}</div>;
}

function EmptyMarket({ onOpenData }: { onOpenData: () => void }) {
  const { t } = useI18n();
  return <div className="panel empty-market"><span className="tiny-badge">{t("emptyByDesign")}</span><h2>{t("noStoredMarketData")}</h2><p>{t("emptyExplanation")}</p><button className="primary-button" onClick={onOpenData}>{t("openDataSync")}</button></div>;
}

function SummaryCards({ overview }: { overview: Overview }) {
  const { t } = useI18n();
  const format = useFormatters();
  const latest = overview.latest_backtest?.result ?? overview.latest_backtest;
  const breadthLabel = overview.market_regime.breadth == null
    ? t("noData")
    : overview.market_regime.breadth >= 0.65
      ? t("broadPositive")
      : overview.market_regime.breadth <= 0.35
        ? t("broadNegative")
        : t("mixedBreadth");
  return <div className="summary-grid">
    <div className="summary-card featured"><div className="summary-card-label">{t("storedUniverse")} <span className="tiny-badge live">Massive EOD</span></div><div className="summary-value mono">{overview.market.symbol_count}</div><div className="summary-meta">{overview.market.bar_count.toLocaleString()} {t("realDailyBars")}</div></div>
    <div className="summary-card"><div className="summary-card-label">{t("latestObservation")}</div><div className="summary-value summary-date">{format.date(overview.market.last_observation)}</div><div className="summary-meta">{t("cutoff")} {format.date(overview.market.data_cutoff)}</div></div>
    <div className="summary-card"><div className="summary-card-label">{t("positiveBreadth")}</div><div className="summary-value mono">{formatPercent(overview.market_regime.breadth, 1)}</div><div className="summary-meta">{breadthLabel}</div></div>
    <div className="summary-card"><div className="summary-card-label">{t("latestIc")}</div><div className="summary-value mono">{latest?.mean_spearman_ic == null ? "—" : latest.mean_spearman_ic.toFixed(3)}</div><div className="summary-meta">{latest ? `${latest.observation_count} ${t("observations")}` : t("noBacktest")}</div></div>
  </div>;
}

function StockTable({ stocks, active, setActive, horizon, search }: { stocks: Stock[]; active: Stock | null; setActive: (stock: Stock) => void; horizon: Horizon; search: string }) {
  const { t } = useI18n();
  const visible = useMemo(() => stocks.filter((stock) => stock.symbol.includes(search.trim().toUpperCase())).sort((a, b) => scoreFor(b, horizon) - scoreFor(a, horizon)), [stocks, search, horizon]);
  return <div className="table-wrap"><table className="data-table"><thead><tr><th>{t("symbol")}</th><th>{t("latestClose")}</th><th>{t("return5")}</th><th>{t("return20")}</th><th>{t("volatility20")}</th><th>{t("drawdown60")}</th><th>{horizon} {t("score")}</th><th>{t("rows")}</th></tr></thead><tbody>
    {visible.map((stock) => <tr key={stock.symbol} className={active?.symbol === stock.symbol ? "selected" : ""} onClick={() => setActive(stock)} tabIndex={0} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setActive(stock); }}>
      <td><strong>{stock.symbol}</strong><div className="company-name">{stock.source}</div></td>
      <td className="mono">${stock.price.toFixed(2)}<div className={stock.change != null && stock.change >= 0 ? "positive-text" : "negative-text"}>{stock.change == null ? "—" : `${stock.change >= 0 ? "+" : ""}${stock.change.toFixed(2)}%`}</div></td>
      <td className="mono">{formatPercent(stock.metrics.return_5d)}</td><td className="mono">{formatPercent(stock.metrics.return_20d)}</td><td className="mono">{formatPercent(stock.metrics.realized_volatility_20d, 1)}</td><td className="mono">{formatPercent(stock.metrics.drawdown_60d)}</td>
      <td><span className={`score-pill ${scoreFor(stock, horizon) >= 60 ? "positive" : scoreFor(stock, horizon) < 40 ? "negative" : "neutral"}`}>{scoreFor(stock, horizon).toFixed(1)}</span></td><td className="mono">{stock.bar_count}</td>
    </tr>)}
  </tbody></table>{!visible.length && <div className="empty-state">{t("noMatch")}</div>}</div>;
}

function StockDetail({ stock, horizon }: { stock: Stock; horizon: Horizon }) {
  const { t } = useI18n();
  const format = useFormatters();
  const score = scoreFor(stock, horizon);
  const signal = score >= 65 ? t("positiveSetup") : score <= 35 ? t("weakSetup") : t("neutralSetup");
  return <div className="panel detail-card">
    <div className="detail-hero"><div className="stock-identity"><div><h2 className="stock-symbol">{stock.symbol}</h2><div className="stock-sector">{stock.source} · {format.date(stock.last_observation)}</div></div><span className="tiny-badge live">{t("stored")}</span></div><div className="stock-price"><span className="price-main">${stock.price.toFixed(2)}</span><span className={stock.change != null && stock.change >= 0 ? "price-change" : "price-change negative-text"}>{stock.change == null ? "—" : `${stock.change >= 0 ? "+" : ""}${stock.change.toFixed(2)}%`}</span></div><div className="chart-area">{stock.bars.map((height, index) => <span className="chart-bar" style={{ height: `${height}%` }} key={index} />)}</div></div>
    <div className="signal-block"><div className="signal-top"><span className="signal-label">{horizon} {t("relativeScore")}</span><span className="score-pill positive">{score.toFixed(1)}</span></div><div className="signal-status">{signal}</div><p className="signal-copy">{t("noFallback")}.</p></div>
    <div className="driver-list"><p className="driver-title">{t("crossRanks")}</p><div className="driver"><span className="driver-dot" /><span>{t("momentum20")}</span><span className="driver-value">{stock.momentum.toFixed(1)}p</span></div><div className="driver"><span className="driver-dot" /><span>{t("relativeStrength")}</span><span className="driver-value">{stock.relativeStrength.toFixed(1)}p</span></div><div className="driver"><span className="driver-dot risk" /><span>{t("realizedVol")}</span><span className="driver-value">{stock.volatility.toFixed(1)}p</span></div></div>
    <div className="snapshot-meta"><span>{t("metricVersion")}</span><strong className="mono">{stock.metric_version}</strong><span>{t("availableAt")}</span><strong>{format.date(stock.data_cutoff)}</strong><span>{t("dataQuality")}</span><strong>{stock.dataQuality.toFixed(0)}%</strong></div>
  </div>;
}

function MetricsView({ stocks }: { stocks: Stock[] }) {
  const { language, t } = useI18n();
  const initialStock = stocks.find((stock) => stock.symbol === "AAPL") ?? stocks[0] ?? null;
  const [symbol, setSymbol] = useState(initialStock?.symbol ?? "");
  const selected = stocks.find((stock) => stock.symbol === symbol) ?? initialStock;
  const minDay = dateToDay(DEFAULT_ANALYSIS_START);
  const maxDay = dateToDay(DEFAULT_SYNC_END);
  const [startDay, setStartDay] = useState(selected ? dateToDay(selected.first_observation) : minDay);
  const [endDay, setEndDay] = useState(selected ? dateToDay(selected.last_observation) : maxDay);
  const [analysis, setAnalysis] = useState<RangeAnalysis | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  const chooseSymbol = (value: string) => {
    const stock = stocks.find((item) => item.symbol === value);
    setSymbol(value);
    if (stock) {
      setStartDay(dateToDay(stock.first_observation));
      setEndDay(dateToDay(stock.last_observation));
    }
    setAnalysis(null);
    setError("");
  };
  const run = async () => {
    if (!selected) return;
    setRunning(true);
    setError("");
    try {
      const result = await api<RangeAnalysis>("/analyses", { method: "POST", body: JSON.stringify({ symbol: selected.symbol, start_date: dayToDate(startDay), end_date: dayToDate(endDay) }) });
      setAnalysis(result);
    } catch (requestError) {
      setAnalysis(null);
      setError(requestError instanceof Error ? requestError.message : t("apiError"));
    } finally {
      setRunning(false);
    }
  };
  const setStartDate = (value: string) => setStartDay(Math.min(dateToDay(value), endDay - 1));
  const setEndDate = (value: string) => setEndDay(Math.max(dateToDay(value), startDay + 1));
  const chartValues = analysis?.series.map((item) => item.close) ?? [];
  const chartLow = chartValues.length ? Math.min(...chartValues) : 0;
  const chartHigh = chartValues.length ? Math.max(...chartValues) : 1;

  if (!selected) return <EmptyMarket onOpenData={() => undefined} />;
  return <div className="page-section">
    <Header eyebrow={t("rangeMetrics")} title={t("rangeMetricsTitle")} copy={t("rangeMetricsCopy")}>
      <label className="inline-control">{t("selectStock")}<select className="filter-select" value={selected.symbol} onChange={(event) => chooseSymbol(event.target.value)}>{stocks.map((stock) => <option key={stock.symbol}>{stock.symbol}</option>)}</select></label>
    </Header>
    <div className="panel timeline-panel">
      <div className="timeline-dates"><label>{t("startDate")}<input type="date" value={dayToDate(startDay)} min={dayToDate(minDay)} max={dayToDate(endDay - 1)} onChange={(event) => setStartDate(event.target.value)} /></label><label>{t("endDate")}<input type="date" value={dayToDate(endDay)} min={dayToDate(startDay + 1)} max={dayToDate(maxDay)} onChange={(event) => setEndDate(event.target.value)} /></label></div>
      <div className="dual-range" aria-label={t("rangeMetrics")}><input type="range" min={minDay} max={maxDay} value={startDay} onChange={(event) => setStartDay(Math.min(Number(event.target.value), endDay - 1))} /><input type="range" min={minDay} max={maxDay} value={endDay} onChange={(event) => setEndDay(Math.max(Number(event.target.value), startDay + 1))} /></div>
      <div className="timeline-caption"><span>{dayToDate(minDay)}</span><strong>{dayToDate(startDay)} → {dayToDate(endDay)}</strong><span>{dayToDate(maxDay)}</span></div>
      <button className="primary-button" disabled={running} onClick={() => void run()}>{running ? t("calculating") : t("calculate")}</button>
      {error && <div className="workspace-notice error">{error}</div>}
    </div>
    {analysis && <>
      <div className="panel coverage-panel"><div><span>{t("requestedRange")}</span><strong className="mono">{analysis.requested_start} → {analysis.requested_end}</strong></div><div><span>{t("actualCoverage")}</span><strong className="mono">{analysis.actual_start} → {analysis.actual_end}</strong></div><div><span>{t("sessions")}</span><strong className="mono">{analysis.bar_count}</strong></div>{analysis.coverage_warnings.length > 0 && <p className="coverage-warning">{t("coverageGap")}</p>}</div>
      <div className="panel range-chart"><div className="panel-header"><div><h2 className="panel-title">{analysis.symbol}</h2><p className="panel-subtitle">{analysis.source} · {analysis.metric_version}</p></div></div><div className="range-chart-bars">{analysis.series.map((point) => <span key={point.date} title={`${point.date}: ${point.close}`} style={{ height: `${chartHigh === chartLow ? 50 : 10 + 85 * (point.close - chartLow) / (chartHigh - chartLow)}%` }} />)}</div></div>
      <div className="panel pipeline"><div className="panel-header"><div><h2 className="panel-title">{t("metricsSnapshot")}</h2><p className="panel-subtitle">Cutoff {analysis.data_cutoff}</p></div></div><div className="result-grid metric-results">
        {[["return_5d", t("return5"), "percent"], ["return_20d", t("return20"), "percent"], ["realized_volatility_20d", t("volatility20"), "percent"], ["volume_zscore_20d", t("volumeZ"), "decimal"], ["distance_ma20", t("distanceMa"), "percent"], ["drawdown_60d", t("drawdown60"), "percent"]].map(([key, label, kind]) => <div className="result-card" key={key}><div className="result-label">{label}</div><div className="result-value mono">{kind === "percent" ? formatPercent(analysis.metrics[key]) : analysis.metrics[key].toFixed(3)}</div></div>)}
      </div></div>
      <div className="panel pipeline"><div className="panel-header"><div><h2 className="panel-title">{t("forecast")}</h2><p className="panel-subtitle">{t("forecastDisclaimer")}</p></div></div><div className="forecast-grid">
        {[10, 30, 90].map((horizon) => { const forecast = analysis.forecasts[String(horizon)]; return <div className="forecast-card" key={horizon}><div className="forecast-top"><strong>{horizon} {t("sessions")}</strong><span className="tiny-badge">{forecast.status}</span></div>{forecast.status === "complete" ? <><div><span>{t("medianReturn")}</span><strong className="mono">{formatPercent(forecast.median_return)}</strong></div><div><span>{t("range1090")}</span><strong className="mono">{formatPercent(forecast.p10_return)} → {formatPercent(forecast.p90_return)}</strong></div><div><span>{t("positiveProbability")}</span><strong className="mono">{formatPercent(forecast.positive_probability, 1)}</strong></div><small>{forecast.sample_count} {t("analogSamples")}</small></> : <p>{t("insufficient")} ({forecast.sample_count})</p>}</div>; })}
      </div></div>
      <p className="forecast-footnote">{language === "zh" ? "此 forecast 僅供研究與回測設計，不構成投資建議。" : "This forecast supports research and backtest design only; it is not investment advice."}</p>
    </>}
  </div>;
}

function BacktestView({ backtests, run, running }: { backtests: Backtest[]; run: (horizon: number) => Promise<void>; running: boolean }) {
  const { language, t } = useI18n();
  const [horizon, setHorizon] = useState(30);
  const latest = backtests[0];
  const result = latest?.result ?? latest;
  return <div className="page-section"><Header eyebrow={t("walkForward")} title={t("testWithoutInventing")} copy={t("testWithoutInventingCopy")}><select className="filter-select" value={horizon} onChange={(event) => setHorizon(Number(event.target.value))}><option value={10}>10 {t("sessions")}</option><option value={30}>30 {t("sessions")}</option><option value={90}>90 {t("sessions")}</option></select><button className="primary-button" disabled={running} onClick={() => void run(horizon)}>{running ? t("running") : t("runBacktest")}</button></Header>
    {!latest ? <div className="panel empty-market"><h2>{t("noBacktestResults")}</h2><p>{t("backtestEmptyCopy")}</p></div> : <><div className="result-grid"><div className="result-card"><div className="result-label">{t("meanIc")}</div><div className="result-value mono">{result.mean_spearman_ic == null ? "—" : result.mean_spearman_ic.toFixed(3)}</div></div><div className="result-card"><div className="result-label">{t("spread")}</div><div className="result-value mono">{formatPercent(result.mean_top_bottom_spread)}</div></div><div className="result-card"><div className="result-label">{t("directionAccuracy")}</div><div className="result-value mono">{formatPercent(result.direction_accuracy)}</div></div><div className="result-card"><div className="result-label">{t("observations")}</div><div className="result-value mono">{result.observation_count}</div><div className="result-delta">{result.symbol_count} {t("symbols")}</div></div></div><div className="panel pipeline"><div className="panel-header"><div><h2 className="panel-title">{t("methodLimits")}</h2><p className="panel-subtitle">{result.version}</p></div></div><div className="note-list">{result.warnings.map((warning, index) => <div className="research-note" key={warning}>{language === "zh" ? (index === 0 ? "結果未計入手續費、滑價、稅務、借券成本與存活者偏差修正。" : "這是研究診斷，不是投資建議或交易指令。") : warning}</div>)}</div></div></>}
  </div>;
}

function DataView({ pipeline, sync, syncing }: { pipeline: Pipeline | null; sync: (symbols: string[], start: string, end: string) => Promise<void>; syncing: boolean }) {
  const { t } = useI18n();
  const format = useFormatters();
  const latestSymbols = pipeline?.sync_runs[0]?.symbols.join(", ") ?? "";
  const [symbols, setSymbols] = useState(latestSymbols);
  const [start, setStart] = useState(DEFAULT_SYNC_START);
  const [end, setEnd] = useState(DEFAULT_SYNC_END);
  const parsed = [...new Set(symbols.split(/[\s,]+/).map((item) => item.trim().toUpperCase()).filter(Boolean))];
  return <div className="page-section"><Header eyebrow={t("localOnly")} title={t("syncRealHistory")} copy={t("syncRealHistoryCopy")} />
    <div className="content-grid data-sync-grid"><div className="panel journal-composer"><div className="panel-header"><div><h2 className="panel-title">{t("newSync")}</h2><p className="panel-subtitle">{t("keyLocal")}</p></div></div><div className="journal-form"><label>{t("symbols")}<textarea value={symbols} onChange={(event) => setSymbols(event.target.value)} placeholder="AAPL, MSFT, NVDA, SPY" /></label><div className="timeline-dates"><label>{t("startDate")}<input type="date" value={start} max={end} onChange={(event) => setStart(event.target.value)} /></label><label>{t("endDate")}<input type="date" value={end} min={start} max={DEFAULT_SYNC_END} onChange={(event) => setEnd(event.target.value)} /></label></div><p className="panel-subtitle">{parsed.length} {t("symbols")} · {t("planLimit")}</p><button className="primary-button" disabled={syncing || !parsed.length || start >= end} onClick={() => void sync(parsed, start, end)}>{syncing ? t("syncing") : t("syncToDuckdb")}</button></div></div>
      <div className="panel"><div className="panel-header"><div><h2 className="panel-title">{t("localStorage")}</h2></div></div><div className="source-fields storage-fields"><div className="source-field"><span>{t("provider")}</span><strong>{pipeline?.provider_configured ? t("configured") : t("missingKey")}</strong></div><div className="source-field"><span>{t("symbols")}</span><strong>{pipeline?.market.symbol_count ?? 0}</strong></div><div className="source-field"><span>{t("dailyBars")}</span><strong>{(pipeline?.market.bar_count ?? 0).toLocaleString()}</strong></div><div className="source-field"><span>{t("duckdbFile")}</span><strong>{format.bytes(pipeline?.market.database_bytes ?? 0)}</strong></div><div className="source-field"><span>{t("firstObservation")}</span><strong>{format.date(pipeline?.market.first_observation ?? null)}</strong></div><div className="source-field"><span>{t("latestObservation")}</span><strong>{format.date(pipeline?.market.last_observation ?? null)}</strong></div></div></div>
    </div>
    <div className="panel pipeline"><div className="panel-header"><div><h2 className="panel-title">{t("syncHistory")}</h2><p className="panel-subtitle">{t("syncHistoryCopy")}</p></div></div><div className="activity-list">{pipeline?.sync_runs.length ? pipeline.sync_runs.map((run) => <div className="activity-row" key={run.sync_id}><span className={`tiny-badge ${run.status === "complete" ? "live" : ""}`}>{run.status === "complete" ? t("completed") : run.status === "partial" ? t("partial") : run.status === "failed" ? t("failed") : run.status}</span><span>{run.symbols.join(", ")} · {run.rows_written.toLocaleString()} {t("rows")}</span><time>{new Date(run.started_at).toLocaleString()}</time>{run.error ? <small className="negative-text">{run.error}</small> : null}</div>) : <div className="empty-state">{t("noSync")}</div>}</div></div>
  </div>;
}

function AppContent({ initialUser, language, setLanguage }: { initialUser: PrismUser | null; language: Language; setLanguage: (language: Language) => void }) {
  const { t } = useI18n();
  const format = useFormatters();
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
  const navItems: { id: View; label: string; icon: string }[] = [
    { id: "overview", label: t("overview"), icon: "⌁" }, { id: "scanner", label: t("scanner"), icon: "◎" }, { id: "metrics", label: t("metrics"), icon: "↔" }, { id: "backtest", label: t("backtests"), icon: "ƒ" }, { id: "data", label: t("dataPipeline"), icon: "⇄" },
  ];

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [overviewResult, scannerResult, pipelineResult, backtestResult] = await Promise.all([api<Overview>("/overview"), api<{ items: Stock[] }>("/scanner?horizon=30D"), api<Pipeline>("/pipeline"), api<{ items: Backtest[] }>("/backtests")]);
      setOverview(overviewResult); setStocks(scannerResult.items); setPipeline(pipelineResult); setBacktests(backtestResult.items);
      setActiveStock((current) => scannerResult.items.find((stock) => stock.symbol === current?.symbol) ?? scannerResult.items[0] ?? null);
    } catch (loadError) {
      setOverview(null); setStocks([]); setActiveStock(null); setPipeline(null); setBacktests([]); setError(loadError instanceof Error ? loadError.message : "API unavailable");
    } finally { setLoading(false); }
  }, []);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);
  useEffect(() => { if (!toast) return; const timeout = window.setTimeout(() => setToast(""), 3500); return () => window.clearTimeout(timeout); }, [toast]);

  const sync = async (symbols: string[], start: string, end: string) => {
    setSyncing(true);
    try {
      const result = await api<{ status: string; rows_written: number; failures: unknown[]; coverage: Record<string, { first_observation: string | null; last_observation: string | null }> }>("/sync", { method: "POST", body: JSON.stringify({ symbols, start_date: start, end_date: end }) });
      const firstCoverage = result.coverage[symbols[0]];
      setToast(language === "zh" ? `${result.status}：寫入 ${result.rows_written.toLocaleString()} 筆；實際覆蓋 ${firstCoverage?.first_observation?.slice(0, 10) ?? "—"} → ${firstCoverage?.last_observation?.slice(0, 10) ?? "—"}` : `${result.status}: ${result.rows_written.toLocaleString()} rows; actual coverage ${firstCoverage?.first_observation?.slice(0, 10) ?? "—"} → ${firstCoverage?.last_observation?.slice(0, 10) ?? "—"}`);
      await load();
    } catch (syncError) { setToast(syncError instanceof Error ? syncError.message : t("apiError")); } finally { setSyncing(false); }
  };
  const runBacktest = async (horizonSessions: number) => {
    setRunning(true);
    try { const result = await api<Backtest>("/backtests", { method: "POST", body: JSON.stringify({ horizon_sessions: horizonSessions }) }); setToast(result.status === "complete" ? t("completed") : t("insufficient")); await load(); } catch (runError) { setToast(runError instanceof Error ? runError.message : t("apiError")); } finally { setRunning(false); }
  };

  return <div className="app-shell"><aside className="sidebar"><div className="brand"><div className="brand-mark">P</div><div><div className="brand-name">Prism</div><div className="brand-sub">{t("localWorkbench")}</div></div></div><div className="nav-label">{t("workspace")}</div><nav className="nav-list">{navItems.map((item) => <button key={item.id} className={`nav-item ${view === item.id ? "active" : ""}`} onClick={() => setView(item.id)}><span className="nav-icon">{item.icon}</span><span>{item.label}</span></button>)}</nav><div className="sidebar-spacer" /><div className="data-card"><div className="data-card-top"><span className="data-card-title">{overview?.market.bar_count ? t("realStoredData") : t("noMarketData")}</span><span className={`status-dot ${overview?.market.bar_count ? "" : "status-dot-empty"}`} /></div><p className="data-card-copy">{overview?.market.bar_count ? `${overview.market.symbol_count} ${t("symbols")} · Massive · ${t("noFallback")}` : t("emptyExplanation")}</p></div><div className="sidebar-footer"><div className="avatar">{(initialUser?.displayName ?? t("localResearcher")).slice(0, 1)}</div><span className="identity-copy"><strong>{initialUser?.displayName ?? t("localResearcher")}</strong><small>{t("localOnly")}</small></span></div></aside>
    <div className="workspace"><header className="topbar"><div className="search"><span className="search-icon">⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("filterSymbols")} /></div><div className="topbar-actions"><span className="cutoff mono">{overview?.market.data_cutoff ? `MASSIVE EOD · ${format.date(overview.market.data_cutoff)}` : t("noMarketData")}</span><button className="language-button" onClick={() => setLanguage(language === "zh" ? "en" : "zh")}>{t("language")}</button><button className="icon-button" onClick={() => void load()}>↻</button><button className="primary-button" onClick={() => setView("data")}>{t("syncData")}</button></div></header>
      <main className="main">{loading && <div className="workspace-notice">{t("loading")}</div>}{error && <div className="workspace-notice error"><span>{t("apiError")} {error}</span><button className="secondary-button" onClick={() => void load()}>{t("retry")}</button></div>}
        {!loading && !error && view === "overview" && overview && <div className="page-section"><Header eyebrow={t("realStoredData")} title={t("researchStored")} copy={t("researchStoredCopy")} />{overview.market.bar_count === 0 ? <EmptyMarket onOpenData={() => setView("data")} /> : <><SummaryCards overview={overview} /><div className="content-grid"><div className="panel"><div className="panel-header"><div><h2 className="panel-title">{t("storedUniverse")}</h2><p className="panel-subtitle">{t("realCrossSection")}</p></div><button className="secondary-button" onClick={() => setView("scanner")}>{t("viewScanner")}</button></div><StockTable stocks={stocks} active={activeStock} setActive={setActiveStock} horizon={horizon} search={search} /></div>{activeStock && <StockDetail stock={activeStock} horizon={horizon} />}</div></>}</div>}
        {!loading && !error && view === "scanner" && <div className="page-section"><Header eyebrow="Massive EOD" title={t("compareReal")} copy={t("compareRealCopy")}><div className="segments">{(["10D", "30D", "90D"] as Horizon[]).map((item) => <button key={item} className={`segment-button ${horizon === item ? "active" : ""}`} onClick={() => setHorizon(item)}>{item}</button>)}</div></Header>{!stocks.length ? <EmptyMarket onOpenData={() => setView("data")} /> : <div className="content-grid"><div className="panel"><StockTable stocks={stocks} active={activeStock} setActive={setActiveStock} horizon={horizon} search={search} /></div>{activeStock && <StockDetail stock={activeStock} horizon={horizon} />}</div>}</div>}
        {!loading && !error && view === "metrics" && <MetricsView stocks={stocks} />}
        {!loading && !error && view === "backtest" && <BacktestView backtests={backtests} run={runBacktest} running={running} />}
        {!loading && !error && view === "data" && <DataView pipeline={pipeline} sync={sync} syncing={syncing} />}
      </main></div>{toast && <div className="toast">{toast}</div>}</div>;
}

export function PrismApp({ initialUser }: { initialUser: PrismUser | null }) {
  const [language, setLanguage] = useState<Language>("zh");
  return <LanguageContext.Provider value={language}><AppContent initialUser={initialUser} language={language} setLanguage={setLanguage} /></LanguageContext.Provider>;
}
