"use client";

import { Fragment, createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

type Language = "zh" | "en";
type View = "overview" | "scanner" | "metrics" | "portfolio" | "events" | "backtest" | "data";
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
  origin_date?: string;
  origin_price?: number | null;
  median_return?: number | null;
  p10_return?: number | null;
  p50_return?: number | null;
  p90_return?: number | null;
  p10_price?: number | null;
  p50_price?: number | null;
  p90_price?: number | null;
  positive_probability?: number | null;
  analog_dates?: string[];
  actual_status?: "complete" | "pending";
  actual_target?: {
    date: string;
    close: number;
    return: number | null;
    forecast_percentile: number | null;
  } | null;
  actual_window?: {
    session_offset: number;
    date: string;
    close: number;
  }[];
  actual_window_complete?: boolean;
  actual_data_cutoff?: string | null;
};
type EventSource = { title: string; url: string; language?: string };
type EventTranslationZh = {
  title?: string;
  summary?: string;
  why_markets_care?: string;
  market_expectations?: string[];
  bullish_scenario?: string;
  bearish_scenario?: string;
  impact_rationale?: string;
  watch_items?: string[];
};
type MarketImpactAssessment = {
  magnitude_score: number;
  breadth: string;
  direction: string;
  time_horizons: string[];
  categories: string[];
  rationale: string;
};
type PortfolioMatch = {
  symbol: string;
  display_name: string;
  matched_categories: string[];
  direct_company_match: boolean;
};
type InstrumentClassification = {
  symbol: string;
  updated_at: string;
  display_name: string;
  instrument_type: string;
  categories: string[];
  summary: string;
  summary_zh: string;
  sources: EventSource[];
  model: string;
  prompt_version: string;
};
type EventReturn = {
  status: "complete" | "pending";
  symbol_return: number | null;
  benchmark_return: number | null;
  excess_return: number | null;
  target_date: string | null;
};
type ResearchEvent = {
  event_id: string;
  first_seen_at: string;
  updated_at: string;
  scope: "world" | "company";
  symbol: string | null;
  event_type: string;
  status: string;
  title: string;
  summary: string;
  event_date_start: string | null;
  event_date_end: string | null;
  release_timing: string | null;
  importance: number;
  confidence: number;
  regions: string[];
  affected_assets: string[];
  watch_items: string[];
  expectations: Record<string, unknown>;
  actual: Record<string, unknown>;
  reaction: {
    status?: string;
    benchmark?: string;
    reaction_session?: string;
    reaction_volume_zscore_20?: number | null;
    returns?: Record<string, EventReturn>;
    data_cutoff?: string;
  };
  sources: EventSource[];
  provider: string;
  model: string;
  prompt_version: string;
  forecast_horizons?: number[];
  portfolio_matches?: PortfolioMatch[];
};
type EventCenter = {
  provider: string | null;
  provider_configured: boolean;
  configuration_error: string | null;
  model: string | null;
  prompt_version: string;
  due_event_count: number;
  events: ResearchEvent[];
  portfolio_classifications: InstrumentClassification[];
  classification_coverage: {
    tracked_count: number;
    classified_count: number;
    unclassified_symbols: string[];
  };
  runs: {
    run_id: string;
    created_at: string;
    scope: string;
    status: string;
    model: string;
    error: string | null;
  }[];
};
type ConfidenceSnapshot = {
  snapshot_key: string;
  created_at: string;
  symbol: string;
  dimension: "institution" | "company_long_term";
  entity: string | null;
  frequency: "weekly" | "monthly";
  period_start: string;
  score: number | null;
  coverage_status: string;
  evidence_count: number;
  components: {
    scores?: Record<string, number | null>;
    evidence?: {
      institution: string | null;
      category: string;
      stance: number;
      statement: string;
      rationale: string;
      published_date: string;
      confidence: number;
    }[];
  };
  sources: EventSource[];
  data_cutoff: string | null;
  provider: string;
  model: string;
  prompt_version: string;
};
type ConfidenceCenter = {
  provider: string | null;
  provider_configured: boolean;
  configuration_error: string | null;
  model: string | null;
  prompt_version: string;
  snapshots: ConfidenceSnapshot[];
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
  forecast_horizon_ends: Record<string, string>;
  scheduled_events: ResearchEvent[];
  series: { date: string; close: number }[];
};
type MetricDefinition = {
  name: string;
  display_name: string;
  display_name_zh: string;
  description: string;
  description_zh: string;
  formula: string;
  required_inputs: string[];
  output_type: string;
  unit: string;
  version: string;
};
type ScoreTerm = {
  key: string;
  metric: string;
  weight: number;
  label: string;
  label_zh: string;
  description: string;
  description_zh: string;
  transform: string;
  invert_percentile: boolean;
};
type ScoreHorizon = {
  horizon: string;
  metric: string | null;
  amplitude: number;
  scale: number;
  label: string;
  label_zh: string;
  formula: string;
};
type ScoreModel = {
  id: string;
  version: string;
  label: string;
  label_zh: string;
  description: string;
  description_zh: string;
  formula: string;
  base_formula?: string;
  terms: ScoreTerm[];
  horizons: ScoreHorizon[];
};
type MetricCatalog = {
  items: MetricDefinition[];
  score_models: ScoreModel[];
};
type ForecastSurfacePoint = {
  origin_date: string;
  target_date: string;
  actual_price: number;
  p10_price: number;
  p50_price: number;
  p90_price: number;
  sample_count: number;
};
type ForecastSurfaceResult = {
  status: "complete" | "insufficient_data";
  horizon_sessions: number;
  bar_count: number;
  required_sessions: number;
  minimum_surface_points: number;
  minimum_analog_samples: number;
  point_count?: number;
  candidate_point_count?: number;
  sampling_interval_sessions?: number;
  data_cutoff?: string;
  selected_start?: string;
  selected_end?: string;
  sources?: string[];
  points: ForecastSurfacePoint[];
};
type ForecastSurfaceJob = {
  job_id: string;
  status: "queued" | "running" | "complete" | "insufficient_data" | "cancelled" | "failed";
  progress: number;
  created_at: string;
  symbol: string;
  start_date: string;
  end_date: string;
  horizon_sessions: number;
  result: ForecastSurfaceResult | null;
  error: string | null;
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
type PortfolioLot = {
  lot_id: string;
  holding_id: string;
  shares: number;
  unit_cost: number;
  cost_basis: number;
  acquired_date: string | null;
  source: string;
  source_reference: string | null;
  created_at: string;
  updated_at: string;
};
type PortfolioHolding = {
  holding_id: string;
  account_name: string;
  symbol: string;
  shares: number;
  average_cost: number;
  acquired_date: string | null;
  source: string;
  source_reference: string | null;
  created_at: string;
  updated_at: string;
  cost_basis: number;
  latest_price: number | null;
  price_date: string | null;
  data_cutoff: string | null;
  market_value: number | null;
  unrealized_pl: number | null;
  unrealized_percent: number | null;
  lots: PortfolioLot[];
};
type PortfolioCenter = {
  items: PortfolioHolding[];
  summary: {
    holding_count: number;
    lot_count: number;
    account_count: number;
    priced_count: number;
    pricing_complete: boolean;
    missing_price_symbols: string[];
    total_cost_basis: number;
    priced_cost_basis: number;
    market_value: number | null;
    unrealized_pl: number | null;
    unrealized_percent: number | null;
    holdings_updated_at: string | null;
    market_synced_at: string | null;
    last_updated_at: string | null;
  };
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
  portfolio: { zh: "我的持倉", en: "My holdings" },
  events: { zh: "世界與公司事件", en: "World & company events" },
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
  portfolioEyebrow: { zh: "本機持倉快照・不執行交易", en: "Local holdings snapshot · no trading" },
  portfolioTitle: { zh: "把實際持倉接進研究流程。", en: "Connect your real holdings to research." },
  portfolioCopy: {
    zh: "股數與成本只存在本機 DuckDB；估值只使用 Prism 已儲存的 Massive 收盤價。缺少價格時保持空白。",
    en: "Shares and cost basis stay in local DuckDB. Valuation uses only Massive closes already stored by Prism; missing prices remain blank.",
  },
  addHolding: { zh: "新增持倉明細", en: "Add holding lot" },
  accountName: { zh: "帳戶名稱", en: "Account name" },
  sharesHeld: { zh: "持有股數", en: "Shares held" },
  averageCost: { zh: "平均成本", en: "Average cost" },
  acquiredDate: { zh: "取得日期", en: "Acquired date" },
  saveHolding: { zh: "儲存這一筆", en: "Save lot" },
  updateHolding: { zh: "更新持倉明細", en: "Update holding lot" },
  editHolding: { zh: "編輯", en: "Edit" },
  cancelEdit: { zh: "取消", en: "Cancel" },
  deleteHolding: { zh: "刪除", en: "Delete" },
  savingHolding: { zh: "儲存中…", en: "Saving…" },
  localHoldingFormCopy: {
    zh: "每次儲存都會保留為一筆明細；相同帳戶與股票會自動彙總股數與加權平均成本。",
    en: "Each save keeps a separate lot. Matching account-symbol lots are summarized with total shares and weighted average cost.",
  },
  noHoldings: { zh: "尚未建立持倉", en: "No holdings yet" },
  noHoldingsCopy: {
    zh: "請在左側手動填入。Prism 只保存本機快照，不會產生任何交易指令。",
    en: "Enter a holding with the form. Prism stores only a local snapshot and never creates trading instructions.",
  },
  holdingCount: { zh: "持倉筆數", en: "Holdings" },
  lotCount: { zh: "明細筆數", en: "Lots" },
  holdingLots: { zh: "持倉明細", en: "Holding details" },
  unitCost: { zh: "每股成本", en: "Unit cost" },
  enteredAt: { zh: "輸入時間", en: "Entered at" },
  lastUpdatedAt: { zh: "上次更新時間", en: "Last updated" },
  neverUpdated: { zh: "尚未更新", en: "Never updated" },
  expandHolding: { zh: "展開持倉明細", en: "Expand holding details" },
  collapseHolding: { zh: "收合持倉明細", en: "Collapse holding details" },
  accountCount: { zh: "帳戶數", en: "Accounts" },
  costBasis: { zh: "成本基礎", en: "Cost basis" },
  marketValue: { zh: "已定價市值", en: "Priced market value" },
  unrealizedPL: { zh: "未實現損益", en: "Unrealized P/L" },
  pricingCoverage: { zh: "價格覆蓋", en: "Price coverage" },
  latestStoredPrice: { zh: "最新儲存價", en: "Latest stored price" },
  holdingSource: { zh: "資料來源", en: "Source" },
  missingStoredPrice: { zh: "缺少已儲存價格", en: "Missing stored prices" },
  missingPriceCopy: {
    zh: "以下持倉不會被估值，直到你從 Massive 同步相應標的：",
    en: "These holdings remain unvalued until their symbols are synchronized from Massive:",
  },
  openDataSyncShort: { zh: "前往同步", en: "Open data sync" },
  holdingSaved: { zh: "持倉明細已儲存", en: "Holding lot saved" },
  holdingDeleted: { zh: "持倉明細已刪除", en: "Holding lot deleted" },
  confirmDeleteHolding: { zh: "確定要刪除這筆持倉明細嗎？", en: "Delete this holding lot?" },
  rangeMetricsTitle: { zh: "用你選擇的時間區間計算。", en: "Calculate over your selected timeline." },
  rangeMetrics: { zh: "Metrics 時間區間", en: "Metrics timeline" },
  rangeMetricsCopy: {
    zh: "拖曳起點與終點，Prism 只使用該區間內、在 cutoff 前可得的真實日線計算 metrics 與歷史類比 forecast。",
    en: "Drag the start and end points. Prism uses only real bars available inside that interval for metrics and historical-analog forecasts.",
  },
  selectStock: { zh: "選擇股票", en: "Select symbol" },
  startDate: { zh: "開始日期", en: "Start date" },
  endDate: { zh: "結束日期", en: "End date" },
  calculating: { zh: "計算中…", en: "Calculating…" },
  autoCalculate: { zh: "選項變更後自動重算", en: "Recalculates automatically after changes" },
  analysisTab: { zh: "區間分析", en: "Range analysis" },
  methodologyTab: { zh: "Metrics 方法與權重", en: "Metrics methodology & weights" },
  liveMetrics: { zh: "目前區間數值", en: "Current range values" },
  formula: { zh: "公式", en: "Formula" },
  inputs: { zh: "輸入", en: "Inputs" },
  weight: { zh: "權重", en: "Weight" },
  scoreModels: { zh: "分數模型", en: "Score models" },
  rawMetrics: { zh: "原始 Metrics", en: "Raw metrics" },
  implementationSource: { zh: "實作唯一來源", en: "Single implementation source" },
  implementationSourceCopy: {
    zh: "以下公式與權重由後端實際計算所迭代的同一組定義產生；前端不另外保存權重副本。",
    en: "These formulas and weights are serialized from the same definitions iterated by the backend calculations; the frontend keeps no separate weight copy.",
  },
  scoreDistinction: {
    zh: "掃描分數與 Walk-forward 特徵分數用途不同，請勿直接互相比較。",
    en: "The scanner score and walk-forward feature score serve different purposes and are not directly comparable.",
  },
  horizonAdjustment: { zh: "期間調整", en: "Horizon adjustment" },
  noMetricCatalog: { zh: "Metrics 方法資料目前無法取得；不顯示替代內容。", en: "Metric methodology is unavailable; no substitute content is shown." },
  shiftRange: { zh: "平移整段時間", en: "Shift the whole range" },
  shiftDays: { zh: "天", en: "days" },
  moveEarlier: { zh: "往左移", en: "Move earlier" },
  moveLater: { zh: "往右移", en: "Move later" },
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
  forecastPrices: { zh: "Forecast 價格點位", en: "Forecast price levels" },
  p10Price: { zh: "10% 下緣", en: "10% lower" },
  p50Price: { zh: "50% 中位", en: "50% median" },
  p90Price: { zh: "90% 上緣", en: "90% upper" },
  historicalActual: { zh: "歷史真值", en: "Historical actual" },
  forecastPercentile: { zh: "模型分布百分位", en: "Forecast distribution percentile" },
  forecastPercentileCopy: {
    zh: "真實報酬在本次歷史類比 forward-return 樣本中的 mid-rank 百分位。",
    en: "Mid-rank percentile of the realized return within this forecast's historical-analog forward-return sample.",
  },
  actualWindow: { zh: "目標日前後 5 個交易日", en: "Five sessions before and after target" },
  actualPending: {
    zh: "所選區間後尚無足夠的已儲存真值；保持空白。",
    en: "No stored realized value exists after this range yet; it remains empty.",
  },
  partialActualWindow: {
    zh: "已有目標日真值，但前後 5 個交易日尚未完整。",
    en: "The target actual is available, but the ±5-session window is incomplete.",
  },
  positiveProbability: { zh: "正報酬比例", en: "Positive-return share" },
  analogSamples: { zh: "類似樣本", en: "analog samples" },
  insufficient: { zh: "樣本不足，不產生 forecast", en: "Insufficient samples; no forecast produced" },
  forecastDisclaimer: {
    zh: "Metrics 與類比只使用選定區間；只有下方歷史真值驗證會讀取區間後已儲存的日線。不是即時報價、保證或交易建議。",
    en: "Metrics and analogs use only the selected range. Only the realized-history check below reads stored bars after it. This is not a live quote, guarantee, or trading advice.",
  },
  eventResearch: { zh: "AI 來源化事件研究", en: "AI source-grounded event research" },
  eventResearchTitle: { zh: "把預告、結果與市場反應連成資料。", en: "Connect previews, outcomes, and market reactions." },
  eventResearchCopy: {
    zh: "本機 Codex CLI 只負責查找與彙整有來源的世界時事、財報及重大發表；價格反應由 Massive 日線計算並存入本機 DuckDB。",
    en: "The local Codex CLI finds and summarizes sourced world events, earnings, and major announcements; Prism computes price reactions from Massive bars and stores them in local DuckDB.",
  },
  refreshWorld: { zh: "更新世界事件", en: "Refresh world events" },
  resolveDue: { zh: "補齊到期事件", en: "Resolve due events" },
  refreshReactions: { zh: "重算市場反應", en: "Recompute reactions" },
  refreshingEvents: { zh: "研究中…", en: "Researching…" },
  aiKeyMissing: { zh: "Codex CLI 尚未連線", en: "Codex CLI is not connected" },
  aiKeyMissingCopy: {
    zh: "請先在本機終端執行 codex login，完成 ChatGPT 登入後重啟 Prism API。Massive API 不受影響，Prism 也不會顯示 AI 預設事件。",
    en: "Run codex login locally, sign in with ChatGPT, then restart the Prism API. Massive remains unaffected and Prism will not show placeholder AI events.",
  },
  noStoredEvents: { zh: "尚無已研究事件", en: "No researched events are stored" },
  noStoredEventsCopy: {
    zh: "按下更新後才會呼叫 AI；沒有結果時保持空白，不把「未研究」誤當成「沒有事件」。",
    en: "AI is called only when you refresh. Empty means not yet researched, not proof that no events exist.",
  },
  worldEvents: { zh: "世界事件", en: "World events" },
  companyEvents: { zh: "公司事件", en: "Company events" },
  expectations: { zh: "市場預期／情境", en: "Expectations / scenarios" },
  actualResult: { zh: "實際結果", en: "Actual result" },
  marketReaction: { zh: "本機市場反應", en: "Local market reaction" },
  watchItems: { zh: "觀察重點", en: "Watch items" },
  sources: { zh: "來源", en: "Sources" },
  sourceLanguage: { zh: "來源語言", en: "Source language" },
  sourceLanguageUnknown: { zh: "未記錄", en: "Not recorded" },
  viewOriginal: { zh: "查看原文", en: "View original" },
  marketImpact: { zh: "可能市場影響", en: "Potential market impact" },
  impactMagnitude: { zh: "影響規模", en: "Magnitude" },
  impactBreadth: { zh: "影響範圍", en: "Breadth" },
  impactDirection: { zh: "可能方向", en: "Potential direction" },
  impactHorizon: { zh: "時間尺度", en: "Time horizon" },
  portfolioConnections: { zh: "追蹤標的連結", en: "Tracked-symbol connections" },
  classificationTitle: { zh: "追蹤標的事前分類", en: "Tracked-symbol classification" },
  classificationCopy: {
    zh: "以有來源的業務與基金曝險分類，新聞只透過共同分類連結；未分類時不猜測。",
    en: "Classify sourced business and fund exposures first; news links only through shared categories, with no guessing for unclassified symbols.",
  },
  refreshClassifications: { zh: "更新追蹤分類", en: "Refresh classifications" },
  classifying: { zh: "分類中…", en: "Classifying…" },
  classificationCoverage: { zh: "分類覆蓋", en: "Classification coverage" },
  translationUnavailable: {
    zh: "此舊資料尚無中文翻譯；重新研究後才會補齊。",
    en: "This older record has no Chinese translation yet; refresh research to add it.",
  },
  resolveEvent: { zh: "查詢實際結果", en: "Research actual outcome" },
  eventDate: { zh: "事件日期", en: "Event date" },
  confidence: { zh: "信心", en: "Confidence" },
  importance: { zh: "重要度", en: "Importance" },
  researchForecastEvents: { zh: "研究 forecast 期間事件", en: "Research forecast-window events" },
  noForecastEvents: {
    zh: "此 forecast 區間尚無已儲存的事件研究；這不代表沒有事件。",
    en: "No event research is stored for this forecast window; this does not mean no events exist.",
  },
  forecastWindowEvents: { zh: "Forecast 區間事件", en: "Forecast-window events" },
  confidenceTracking: { zh: "信心指數時間序列", en: "Confidence index time series" },
  confidenceTrackingCopy: {
    zh: "每週保存各機構的公開立場；每月保存由價格趨勢、機構觀點與品牌證據組成的長期信心。分項缺失時不補值。",
    en: "Store public institutional stances weekly and a monthly long-term confidence composite from price trend, institutions, and brand evidence. Missing components remain missing.",
  },
  refreshConfidence: { zh: "更新所選股票信心", en: "Refresh selected confidence" },
  institutionalWeekly: { zh: "機構信心・每週", en: "Institution confidence · weekly" },
  longTermMonthly: { zh: "公司長期信心・每月", en: "Company long-term confidence · monthly" },
  noConfidence: {
    zh: "尚無信心 snapshot。更新前保持空白。",
    en: "No confidence snapshot is stored. It remains empty until refreshed.",
  },
  coverage: { zh: "覆蓋", en: "Coverage" },
  evidence: { zh: "證據", en: "Evidence" },
  marketPriceComponent: { zh: "市場價格", en: "Market price" },
  institutionComponent: { zh: "機構", en: "Institutional" },
  brandComponent: { zh: "品牌證據", en: "Brand evidence" },
  aiRunHistory: { zh: "AI 研究執行紀錄", en: "AI research run history" },
  noAiRuns: { zh: "尚未執行 AI 研究。", en: "No AI research has been run." },
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
  forecastSurface: { zh: "3D Forecast 歷史驗證", en: "3D forecast history validation" },
  forecastSurfaceCopy: {
    zh: "單一個股的時間 × 資料來源 × 股價；每個預測點只使用當時可見資料，歷史真值只供事後比較。",
    en: "Time × data source × price for one stock. Every forecast uses only information available at its origin; actual prices are comparisons only.",
  },
  autoSurface: { zh: "隨區間自動重算", en: "Recompute with range" },
  autoSurfaceCopy: {
    zh: "開啟後，股票、區間、平移或 horizon 改變會取消舊任務並在背景重算；切到其他頁面不會中斷目前任務。",
    en: "When enabled, stock, range, shift, or horizon changes cancel stale work and recompute in the background. Visiting another page does not interrupt the active job.",
  },
  surfaceDisabled: {
    zh: "3D 計算預設關閉。勾選後才會使用目前區間進行 rolling forecast。",
    en: "3D computation is off by default. Enable it to run rolling forecasts over the selected range.",
  },
  surfaceCalculating: { zh: "背景計算中", en: "Computing in background" },
  surfaceContinueBrowsing: {
    zh: "可繼續查看其他頁面；變更條件時會取消這次計算。",
    en: "You can keep browsing. Changing inputs cancels this computation.",
  },
  surfaceInsufficient: { zh: "所選區間的交易日不足", en: "The selected range has too few trading sessions" },
  surfaceMinimum: { zh: "最低需求", en: "Minimum required" },
  surfaceActual: { zh: "歷史真值", en: "Historical actual" },
  surfaceP10: { zh: "10% 預測", en: "10% forecast" },
  surfaceP50: { zh: "50% 預測", en: "50% forecast" },
  surfaceP90: { zh: "90% 預測", en: "90% forecast" },
  surfacePoints: { zh: "驗證點", en: "validation points" },
  samplingEvery: { zh: "抽樣間距", en: "sampling interval" },
  surfaceFailed: { zh: "3D Forecast 計算失敗", en: "3D forecast computation failed" },
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

const marketCategoryLabels: Record<string, { zh: string; en: string }> = {
  broad_market: { zh: "總體市場", en: "Broad market" },
  technology: { zh: "科技股", en: "Technology" },
  semiconductors: { zh: "半導體", en: "Semiconductors" },
  software: { zh: "軟體", en: "Software" },
  cloud: { zh: "雲端", en: "Cloud" },
  artificial_intelligence: { zh: "人工智慧", en: "Artificial intelligence" },
  communication_services: { zh: "通訊服務", en: "Communication services" },
  consumer_discretionary: { zh: "非必需消費", en: "Consumer discretionary" },
  consumer_staples: { zh: "必需消費", en: "Consumer staples" },
  financials: { zh: "金融股", en: "Financials" },
  industrials: { zh: "工業股", en: "Industrials" },
  defense: { zh: "國防／軍工", en: "Defense" },
  aerospace: { zh: "航太", en: "Aerospace" },
  energy: { zh: "能源", en: "Energy" },
  materials: { zh: "原物料", en: "Materials" },
  healthcare: { zh: "醫療保健", en: "Healthcare" },
  utilities: { zh: "公用事業", en: "Utilities" },
  real_estate: { zh: "房地產", en: "Real estate" },
  transportation: { zh: "運輸", en: "Transportation" },
  government_bonds: { zh: "政府債券", en: "Government bonds" },
  interest_rates: { zh: "利率", en: "Interest rates" },
  currencies: { zh: "匯率", en: "Currencies" },
  commodities: { zh: "大宗商品", en: "Commodities" },
  crypto: { zh: "加密資產", en: "Crypto" },
  international: { zh: "國際市場", en: "International markets" },
};
const breadthLabels: Record<string, { zh: string; en: string }> = {
  single_company: { zh: "單一公司", en: "Single company" },
  industry: { zh: "產業鏈", en: "Industry" },
  sector: { zh: "單一板塊", en: "Sector" },
  multi_sector: { zh: "跨板塊", en: "Multiple sectors" },
  broad_market: { zh: "總體市場", en: "Broad market" },
  global_cross_asset: { zh: "全球跨資產", en: "Global cross-asset" },
};
const directionLabels: Record<string, { zh: string; en: string }> = {
  positive: { zh: "偏正向", en: "Positive" },
  negative: { zh: "偏負向", en: "Negative" },
  mixed: { zh: "多空混合", en: "Mixed" },
  uncertain: { zh: "方向不確定", en: "Uncertain" },
};
const horizonLabels: Record<string, { zh: string; en: string }> = {
  immediate: { zh: "即時", en: "Immediate" },
  short_term: { zh: "短期", en: "Short term" },
  medium_term: { zh: "中期", en: "Medium term" },
  long_term: { zh: "長期", en: "Long term" },
};

function localizedTaxonomyLabel(
  labels: Record<string, { zh: string; en: string }>,
  value: string,
  language: Language,
) {
  return labels[value]?.[language] ?? value.replaceAll("_", " ");
}

function impactMagnitudeLabel(score: number, language: Language) {
  const labels = language === "zh"
    ? ["", "有限", "小型", "中等", "重大", "系統性"]
    : ["", "Limited", "Small", "Moderate", "Major", "Systemic"];
  return labels[Math.max(1, Math.min(5, Math.round(score)))];
}

function localizedEventContent(event: ResearchEvent, language: Language) {
  const candidate = event.expectations.translation_zh;
  const translation = candidate && typeof candidate === "object" && !Array.isArray(candidate)
    ? candidate as EventTranslationZh
    : null;
  const expectations = Object.fromEntries(
    Object.entries(event.expectations)
      .filter(([key]) => !["translation_zh", "impact_assessment"].includes(key))
      .map(([key, value]) => [
        key,
        language === "zh" && translation?.[key as keyof EventTranslationZh] != null
          ? translation[key as keyof EventTranslationZh]
          : value,
      ]),
  );
  const impactCandidate = event.expectations.impact_assessment;
  const impact = impactCandidate && typeof impactCandidate === "object" && !Array.isArray(impactCandidate)
    ? impactCandidate as MarketImpactAssessment
    : null;
  return {
    title: language === "zh" && translation?.title ? translation.title : event.title,
    summary: language === "zh" && translation?.summary ? translation.summary : event.summary,
    watchItems: language === "zh" && translation?.watch_items
      ? translation.watch_items
      : event.watch_items,
    expectations,
    impact: impact
      ? {
          ...impact,
          rationale: language === "zh" && translation?.impact_rationale
            ? translation.impact_rationale
            : impact.rationale,
        }
      : null,
    hasChineseTranslation: Boolean(translation?.title && translation?.summary),
  };
}

function EventSourceLinks({ sources, heading = true }: { sources: EventSource[]; heading?: boolean }) {
  const { language, t } = useI18n();
  return <div className="event-source-links">
    {heading && <strong>{t("sources")}</strong>}
    <div className="event-source-list">{sources.map((source) => {
      const sourceName = source.title || new URL(source.url).hostname;
      return <div className="event-source-item" key={source.url}>
        <span className="event-source-name">{sourceName}</span>
        <span className="source-language">{t("sourceLanguage")}{language === "zh" ? "：" : ": "}{source.language || t("sourceLanguageUnknown")}</span>
        <a href={source.url} target="_blank" rel="noopener noreferrer" aria-label={`${t("viewOriginal")}: ${sourceName}`}>{t("viewOriginal")} ↗</a>
      </div>;
    })}</div>
  </div>;
}

function MarketImpactPanel({
  impact,
  matches,
  onOpenSymbol,
}: {
  impact: MarketImpactAssessment;
  matches: PortfolioMatch[];
  onOpenSymbol: (symbol: string) => void;
}) {
  const { language, t } = useI18n();
  return <div className="event-impact-panel">
    <div className="impact-heading"><strong>{t("marketImpact")}</strong><span className={`impact-score impact-${impact.magnitude_score}`}>{impact.magnitude_score}/5 · {impactMagnitudeLabel(impact.magnitude_score, language)}</span></div>
    <div className="impact-facts">
      <span><small>{t("impactBreadth")}</small><b>{localizedTaxonomyLabel(breadthLabels, impact.breadth, language)}</b></span>
      <span><small>{t("impactDirection")}</small><b>{localizedTaxonomyLabel(directionLabels, impact.direction, language)}</b></span>
      <span><small>{t("impactHorizon")}</small><b>{impact.time_horizons.map((item) => localizedTaxonomyLabel(horizonLabels, item, language)).join(" · ")}</b></span>
    </div>
    <p>{impact.rationale}</p>
    <div className="impact-category-list">{impact.categories.map((category) => <span className="tiny-badge" key={category}>{localizedTaxonomyLabel(marketCategoryLabels, category, language)}</span>)}</div>
    {matches.length > 0 && <div className="portfolio-connections"><strong>{t("portfolioConnections")}</strong><div className="portfolio-match-list">{matches.map((match) => <button className="portfolio-match" key={match.symbol} onClick={() => onOpenSymbol(match.symbol)}><span>{match.symbol}</span><small>{match.direct_company_match ? (language === "zh" ? "公司直接相關" : "Direct company match") : match.matched_categories.map((category) => localizedTaxonomyLabel(marketCategoryLabels, category, language)).join(" · ")}</small><b>→</b></button>)}</div></div>}
  </div>;
}

function ClassificationPanel({
  center,
  busy,
  refresh,
}: {
  center: EventCenter | null;
  busy: boolean;
  refresh: () => Promise<void>;
}) {
  const { language, t } = useI18n();
  const coverage = center?.classification_coverage;
  return <section className="panel classification-panel">
    <div className="panel-header"><div><h2 className="panel-title">{t("classificationTitle")}</h2><p className="panel-subtitle">{t("classificationCopy")}</p></div><div className="heading-actions"><span className="tiny-badge live">{t("classificationCoverage")} {coverage?.classified_count ?? 0}/{coverage?.tracked_count ?? 0}</span><button className="secondary-button" disabled={busy || !center?.provider_configured} onClick={() => void refresh()}>{busy ? t("classifying") : t("refreshClassifications")}</button></div></div>
    {center?.portfolio_classifications.length ? <div className="classification-grid">{center.portfolio_classifications.map((item) => <article className="classification-card" key={item.symbol}><div><strong>{item.symbol}</strong><span>{item.display_name}</span></div><p>{language === "zh" ? item.summary_zh : item.summary}</p><div className="impact-category-list">{item.categories.map((category) => <span className="tiny-badge" key={category}>{localizedTaxonomyLabel(marketCategoryLabels, category, language)}</span>)}</div></article>)}</div> : <div className="empty-state">{language === "zh" ? "尚未執行追蹤標的分類。" : "Tracked symbols have not been classified yet."}</div>}
    {coverage?.unclassified_symbols.length ? <small className="classification-missing">{language === "zh" ? "尚未分類：" : "Unclassified: "}{coverage.unclassified_symbols.join(", ")}</small> : null}
  </section>;
}

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

function MetricLabel({
  children,
  definition,
  scoreModel,
}: {
  children: React.ReactNode;
  definition?: MetricDefinition;
  scoreModel?: ScoreModel;
}) {
  const { language, t } = useI18n();
  const description = definition
    ? (language === "zh" ? definition.description_zh : definition.description)
    : scoreModel
      ? (language === "zh" ? scoreModel.description_zh : scoreModel.description)
      : "";
  const formula = definition?.formula ?? scoreModel?.formula;
  return <span className="metric-label-with-help">
    <span>{children}</span>
    {(description || formula) && <span className="metric-info-trigger" tabIndex={0} title={[description, formula].filter(Boolean).join("\n")} aria-label={`${children}: ${description}`}>
      i
      <span className="metric-tooltip" role="tooltip">
        {description && <span>{description}</span>}
        {formula && <code><b>{t("formula")}</b>{language === "zh" ? "：" : ": "}{formula}</code>}
      </span>
    </span>}
  </span>;
}

function MetricsMethodology({ catalog }: { catalog: MetricCatalog | null }) {
  const { language, t } = useI18n();
  if (!catalog) return <div className="panel empty-market"><p>{t("noMetricCatalog")}</p></div>;
  return <div className="methodology-stack">
    <div className="methodology-source">
      <span className="tiny-badge live">{t("implementationSource")}</span>
      <p>{t("implementationSourceCopy")}</p>
    </div>
    <section className="panel methodology-panel">
      <div className="panel-header"><div><h2 className="panel-title">{t("rawMetrics")}</h2><p className="panel-subtitle">{catalog.items[0]?.version ?? "—"}</p></div></div>
      <div className="metric-definition-grid">{catalog.items.map((metric) => <article className="metric-definition-card" key={metric.name}>
        <div className="metric-definition-heading"><div><strong>{language === "zh" ? metric.display_name_zh : metric.display_name}</strong><code>{metric.name}</code></div><span className="tiny-badge">{metric.unit}</span></div>
        <p>{language === "zh" ? metric.description_zh : metric.description}</p>
        <div className="formula-block"><span>{t("formula")}</span><code>{metric.formula}</code></div>
        <div className="metric-definition-meta"><span>{t("inputs")}</span><strong className="mono">{metric.required_inputs.join(", ")}</strong></div>
      </article>)}</div>
    </section>
    <section className="panel methodology-panel">
      <div className="panel-header"><div><h2 className="panel-title">{t("scoreModels")}</h2><p className="panel-subtitle">{t("scoreDistinction")}</p></div></div>
      <div className="score-model-list">{catalog.score_models.map((model) => <article className="score-model-card" key={model.id}>
        <div className="score-model-heading"><div><h3>{language === "zh" ? model.label_zh : model.label}</h3><p>{language === "zh" ? model.description_zh : model.description}</p></div><span className="tiny-badge">{model.version}</span></div>
        <div className="formula-block"><span>{t("formula")}</span><code>{model.formula}</code>{model.base_formula && <code>{model.base_formula}</code>}</div>
        <div className="weight-table">{model.terms.map((term) => <div className="weight-term" key={term.key}>
          <div><strong>{language === "zh" ? term.label_zh : term.label}</strong><code>{term.key}</code><p>{language === "zh" ? term.description_zh : term.description}</p></div>
          <span className={`weight-chip ${term.weight < 0 ? "negative" : ""}`}>{t("weight")} {(term.weight * 100).toFixed(0)}%</span>
        </div>)}</div>
        {model.horizons.length > 0 && <div className="horizon-methods"><strong>{t("horizonAdjustment")}</strong><div>{model.horizons.map((horizon) => <span key={horizon.horizon}><b>{horizon.horizon}</b><small>{language === "zh" ? horizon.label_zh : horizon.label}</small><code>{horizon.formula}</code></span>)}</div></div>}
      </article>)}</div>
    </section>
  </div>;
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

function StockTable({ stocks, active, setActive, horizon, search, catalog }: { stocks: Stock[]; active: Stock | null; setActive: (stock: Stock) => void; horizon: Horizon; search: string; catalog: MetricCatalog | null }) {
  const { t } = useI18n();
  const visible = useMemo(() => stocks.filter((stock) => stock.symbol.includes(search.trim().toUpperCase())).sort((a, b) => scoreFor(b, horizon) - scoreFor(a, horizon)), [stocks, search, horizon]);
  const metric = (name: string) => catalog?.items.find((item) => item.name === name);
  const scannerModel = catalog?.score_models.find((item) => item.id === "scanner_relative_score");
  return <div className="table-wrap"><table className="data-table"><thead><tr><th>{t("symbol")}</th><th>{t("latestClose")}</th><th><MetricLabel definition={metric("return_5d")}>{t("return5")}</MetricLabel></th><th><MetricLabel definition={metric("return_20d")}>{t("return20")}</MetricLabel></th><th><MetricLabel definition={metric("realized_volatility_20d")}>{t("volatility20")}</MetricLabel></th><th><MetricLabel definition={metric("drawdown_60d")}>{t("drawdown60")}</MetricLabel></th><th><MetricLabel scoreModel={scannerModel}>{horizon} {t("score")}</MetricLabel></th><th>{t("rows")}</th></tr></thead><tbody>
    {visible.map((stock) => <tr key={stock.symbol} className={active?.symbol === stock.symbol ? "selected" : ""} onClick={() => setActive(stock)} tabIndex={0} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setActive(stock); }}>
      <td><strong>{stock.symbol}</strong><div className="company-name">{stock.source}</div></td>
      <td className="mono">${stock.price.toFixed(2)}<div className={stock.change != null && stock.change >= 0 ? "positive-text" : "negative-text"}>{stock.change == null ? "—" : `${stock.change >= 0 ? "+" : ""}${stock.change.toFixed(2)}%`}</div></td>
      <td className="mono">{formatPercent(stock.metrics.return_5d)}</td><td className="mono">{formatPercent(stock.metrics.return_20d)}</td><td className="mono">{formatPercent(stock.metrics.realized_volatility_20d, 1)}</td><td className="mono">{formatPercent(stock.metrics.drawdown_60d)}</td>
      <td><span className={`score-pill ${scoreFor(stock, horizon) >= 60 ? "positive" : scoreFor(stock, horizon) < 40 ? "negative" : "neutral"}`}>{scoreFor(stock, horizon).toFixed(1)}</span></td><td className="mono">{stock.bar_count}</td>
    </tr>)}
  </tbody></table>{!visible.length && <div className="empty-state">{t("noMatch")}</div>}</div>;
}

function StockDetail({ stock, horizon, catalog }: { stock: Stock; horizon: Horizon; catalog: MetricCatalog | null }) {
  const { t } = useI18n();
  const format = useFormatters();
  const score = scoreFor(stock, horizon);
  const signal = score >= 65 ? t("positiveSetup") : score <= 35 ? t("weakSetup") : t("neutralSetup");
  return <div className="panel detail-card">
    <div className="detail-hero"><div className="stock-identity"><div><h2 className="stock-symbol">{stock.symbol}</h2><div className="stock-sector">{stock.source} · {format.date(stock.last_observation)}</div></div><span className="tiny-badge live">{t("stored")}</span></div><div className="stock-price"><span className="price-main">${stock.price.toFixed(2)}</span><span className={stock.change != null && stock.change >= 0 ? "price-change" : "price-change negative-text"}>{stock.change == null ? "—" : `${stock.change >= 0 ? "+" : ""}${stock.change.toFixed(2)}%`}</span></div><div className="chart-area">{stock.bars.map((height, index) => <span className="chart-bar" style={{ height: `${height}%` }} key={index} />)}</div></div>
    <div className="signal-block"><div className="signal-top"><span className="signal-label"><MetricLabel scoreModel={catalog?.score_models.find((item) => item.id === "scanner_relative_score")}>{horizon} {t("relativeScore")}</MetricLabel></span><span className="score-pill positive">{score.toFixed(1)}</span></div><div className="signal-status">{signal}</div><p className="signal-copy">{t("noFallback")}.</p></div>
    <div className="driver-list"><p className="driver-title">{t("crossRanks")}</p><div className="driver"><span className="driver-dot" /><MetricLabel definition={catalog?.items.find((item) => item.name === "return_20d")}>{t("momentum20")}</MetricLabel><span className="driver-value">{stock.momentum.toFixed(1)}p</span></div><div className="driver"><span className="driver-dot" /><MetricLabel scoreModel={catalog?.score_models.find((item) => item.id === "scanner_relative_score")}>{t("relativeStrength")}</MetricLabel><span className="driver-value">{stock.relativeStrength.toFixed(1)}p</span></div><div className="driver"><span className="driver-dot risk" /><MetricLabel definition={catalog?.items.find((item) => item.name === "realized_volatility_20d")}>{t("realizedVol")}</MetricLabel><span className="driver-value">{stock.volatility.toFixed(1)}p</span></div></div>
    <div className="snapshot-meta"><span>{t("metricVersion")}</span><strong className="mono">{stock.metric_version}</strong><span>{t("availableAt")}</span><strong>{format.date(stock.data_cutoff)}</strong><span>{t("dataQuality")}</span><strong>{stock.dataQuality.toFixed(0)}%</strong></div>
  </div>;
}

function ForecastBandChart({ forecast }: { forecast: Forecast }) {
  const { t } = useI18n();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const p10 = forecast.p10_price;
  const p50 = forecast.p50_price;
  const p90 = forecast.p90_price;
  const actuals = useMemo(
    () => forecast.actual_window ?? [],
    [forecast.actual_window],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || p10 == null || p50 == null || p90 == null) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    const width = canvas.width;
    const height = canvas.height;
    const plot = { left: 34, right: width - 58, top: 20, bottom: height - 28 };
    const values = [p10, p50, p90, ...actuals.map((item) => item.close)];
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    const padding = Math.max((maximum - minimum) * 0.12, maximum * 0.01, 0.5);
    const low = minimum - padding;
    const high = maximum + padding;
    const y = (value: number) => plot.bottom - ((value - low) / (high - low)) * (plot.bottom - plot.top);

    context.clearRect(0, 0, width, height);
    context.fillStyle = "#fbfcf8";
    context.fillRect(0, 0, width, height);
    context.fillStyle = "rgba(181, 228, 67, 0.16)";
    context.fillRect(plot.left, y(p90), plot.right - plot.left, y(p10) - y(p90));

    const drawLevel = (value: number, label: string, dashed: boolean, color: string) => {
      context.beginPath();
      context.setLineDash(dashed ? [6, 5] : []);
      context.strokeStyle = color;
      context.lineWidth = dashed ? 1.5 : 2.5;
      context.moveTo(plot.left, y(value));
      context.lineTo(plot.right, y(value));
      context.stroke();
      context.setLineDash([]);
      context.fillStyle = color;
      context.font = "600 10px ui-monospace, SFMono-Regular, Menlo, monospace";
      context.fillText(`${label} $${value.toFixed(2)}`, plot.right + 5, y(value) + 3);
    };
    drawLevel(p10, "10%", true, "#688346");
    drawLevel(p90, "90%", true, "#688346");
    drawLevel(p50, "50%", false, "#152d22");

    if (actuals.length) {
      const x = (index: number) => (
        actuals.length === 1
          ? (plot.left + plot.right) / 2
          : plot.left + index / (actuals.length - 1) * (plot.right - plot.left)
      );
      context.beginPath();
      actuals.forEach((item, index) => {
        if (index === 0) context.moveTo(x(index), y(item.close));
        else context.lineTo(x(index), y(item.close));
      });
      context.strokeStyle = "#df6846";
      context.lineWidth = 2;
      context.stroke();
      actuals.forEach((item, index) => {
        context.beginPath();
        context.fillStyle = item.session_offset === 0 ? "#152d22" : "#df6846";
        context.arc(x(index), y(item.close), item.session_offset === 0 ? 4 : 2.5, 0, Math.PI * 2);
        context.fill();
      });
      context.fillStyle = "#6b756d";
      context.font = "10px ui-monospace, SFMono-Regular, Menlo, monospace";
      context.fillText(`${actuals[0].session_offset}`, plot.left, height - 9);
      context.fillText("0", (plot.left + plot.right) / 2 - 3, height - 9);
      context.fillText(`+${actuals[actuals.length - 1].session_offset}`, plot.right - 12, height - 9);
    }
  }, [actuals, p10, p50, p90]);

  if (p10 == null || p50 == null || p90 == null) return null;
  return <div className="forecast-band">
    <canvas
      ref={canvasRef}
      width={420}
      height={210}
      aria-label={`${t("forecastPrices")}: 10% $${p10.toFixed(2)}, 50% $${p50.toFixed(2)}, 90% $${p90.toFixed(2)}`}
      role="img"
    />
    <div className="forecast-chart-legend"><span className="forecast-legend actual" />{t("historicalActual")}<span className="forecast-legend median" />50%<span className="forecast-legend interval" />10–90%</div>
    {forecast.actual_status === "complete" && forecast.actual_target ? <>
      <div className="actual-target"><span>{t("historicalActual")}</span><strong className="mono">{forecast.actual_target.date} · ${forecast.actual_target.close.toFixed(2)} · {formatPercent(forecast.actual_target.return)}</strong></div>
      <div className="actual-percentile" title={t("forecastPercentileCopy")}><span>{t("forecastPercentile")}</span><strong className="mono">{forecast.actual_target.forecast_percentile == null ? "—" : `P${forecast.actual_target.forecast_percentile.toFixed(1)}`}</strong></div>
      {!forecast.actual_window_complete && <small className="coverage-warning compact">{t("partialActualWindow")}</small>}
      <div className="actual-window-title">{t("actualWindow")}</div>
      <div className="actual-window" role="table" aria-label={t("actualWindow")}>
        {actuals.map((item) => <div className={item.session_offset === 0 ? "actual-row target" : "actual-row"} role="row" key={`${item.date}-${item.session_offset}`}>
          <span className="mono" role="cell">{item.session_offset > 0 ? `+${item.session_offset}` : item.session_offset}</span>
          <span className="mono" role="cell">{item.date}</span>
          <strong className="mono" role="cell">${item.close.toFixed(2)}</strong>
        </div>)}
      </div>
    </> : <div className="empty-state compact">{t("actualPending")}</div>}
  </div>;
}

function ForecastSurfaceChart({ result }: { result: ForecastSurfaceResult }) {
  const { t } = useI18n();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sources = useMemo(() => [
    { key: "actual_price" as const, label: t("surfaceActual"), color: "#152d22" },
    { key: "p10_price" as const, label: t("surfaceP10"), color: "#df6846" },
    { key: "p50_price" as const, label: t("surfaceP50"), color: "#427493" },
    { key: "p90_price" as const, label: t("surfaceP90"), color: "#7ca344" },
  ], [t]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !result.points.length) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    const width = canvas.width;
    const height = canvas.height;
    const values = result.points.flatMap((point) => sources.map((source) => point[source.key]));
    const low = Math.min(...values);
    const high = Math.max(...values);
    const project = (timeIndex: number, sourceIndex: number, value: number) => {
      const xRatio = result.points.length <= 1 ? 0.5 : timeIndex / (result.points.length - 1);
      const depthRatio = sources.length <= 1 ? 0.5 : sourceIndex / (sources.length - 1);
      const zRatio = high === low ? 0.5 : (value - low) / (high - low);
      return {
        x: 88 + xRatio * 650 + depthRatio * 102,
        y: 348 - depthRatio * 86 - zRatio * 218,
      };
    };

    context.clearRect(0, 0, width, height);
    context.fillStyle = "#fbfcf8";
    context.fillRect(0, 0, width, height);

    context.strokeStyle = "rgba(101, 116, 105, 0.18)";
    context.lineWidth = 1;
    for (let priceStep = 0; priceStep <= 4; priceStep += 1) {
      const price = low + ((high - low) * priceStep) / 4;
      const front = project(0, 0, price);
      const right = project(result.points.length - 1, 0, price);
      const back = project(result.points.length - 1, sources.length - 1, price);
      context.beginPath();
      context.moveTo(front.x, front.y);
      context.lineTo(right.x, right.y);
      context.lineTo(back.x, back.y);
      context.stroke();
      context.fillStyle = "#68756c";
      context.font = "10px ui-monospace, SFMono-Regular, Menlo, monospace";
      context.fillText(`$${price.toFixed(2)}`, 24, front.y + 3);
    }

    sources.forEach((source, sourceIndex) => {
      if (sourceIndex < sources.length - 1) {
        for (let timeIndex = 0; timeIndex < result.points.length - 1; timeIndex += 1) {
          const current = result.points[timeIndex];
          const next = result.points[timeIndex + 1];
          const points = [
            project(timeIndex, sourceIndex, current[source.key]),
            project(timeIndex + 1, sourceIndex, next[source.key]),
            project(timeIndex + 1, sourceIndex + 1, next[sources[sourceIndex + 1].key]),
            project(timeIndex, sourceIndex + 1, current[sources[sourceIndex + 1].key]),
          ];
          context.beginPath();
          context.moveTo(points[0].x, points[0].y);
          points.slice(1).forEach((point) => context.lineTo(point.x, point.y));
          context.closePath();
          context.fillStyle = `${source.color}12`;
          context.fill();
          context.strokeStyle = "rgba(21, 45, 34, 0.08)";
          context.lineWidth = 0.6;
          context.stroke();
        }
      }

      context.beginPath();
      result.points.forEach((point, timeIndex) => {
        const projected = project(timeIndex, sourceIndex, point[source.key]);
        if (timeIndex === 0) context.moveTo(projected.x, projected.y);
        else context.lineTo(projected.x, projected.y);
      });
      context.strokeStyle = source.color;
      context.lineWidth = sourceIndex === 0 || sourceIndex === 2 ? 2.4 : 1.8;
      context.stroke();
      result.points.forEach((point, timeIndex) => {
        const projected = project(timeIndex, sourceIndex, point[source.key]);
        context.beginPath();
        context.fillStyle = source.color;
        context.arc(projected.x, projected.y, timeIndex === result.points.length - 1 ? 3.2 : 1.5, 0, Math.PI * 2);
        context.fill();
      });
    });

    context.strokeStyle = "#8d9a8f";
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(88, 348);
    context.lineTo(738, 348);
    context.lineTo(840, 262);
    context.stroke();
    context.fillStyle = "#5e6b62";
    context.font = "11px ui-monospace, SFMono-Regular, Menlo, monospace";
    context.fillText(result.points[0].target_date, 88, 376);
    context.fillText(result.points[result.points.length - 1].target_date, 664, 376);
    sources.forEach((source, sourceIndex) => {
      const axisPoint = project(result.points.length - 1, sourceIndex, low);
      context.fillStyle = source.color;
      context.fillText(source.label, axisPoint.x + 6, axisPoint.y + 4);
    });
  }, [result, sources]);

  return <div className="forecast-surface">
    <canvas ref={canvasRef} width={920} height={400} role="img" aria-label={t("forecastSurface")} />
    <div className="surface-legend">{sources.map((source) => <span key={source.key}><i style={{ background: source.color }} />{source.label}</span>)}</div>
  </div>;
}

function MetricsView({ stocks, catalog }: { stocks: Stock[]; catalog: MetricCatalog | null }) {
  const { language, t } = useI18n();
  const initialStock = stocks.find((stock) => stock.symbol === "AAPL") ?? stocks[0] ?? null;
  const [symbol, setSymbol] = useState(initialStock?.symbol ?? "");
  const selected = stocks.find((stock) => stock.symbol === symbol) ?? initialStock;
  const minDay = selected ? dateToDay(selected.first_observation) : dateToDay(DEFAULT_ANALYSIS_START);
  const maxDay = selected ? dateToDay(selected.last_observation) : dateToDay(DEFAULT_SYNC_END);
  const [startDay, setStartDay] = useState(selected ? dateToDay(selected.first_observation) : minDay);
  const [endDay, setEndDay] = useState(selected ? dateToDay(selected.last_observation) : maxDay);
  const [tab, setTab] = useState<"analysis" | "methodology">("analysis");
  const [analysis, setAnalysis] = useState<RangeAnalysis | null>(null);
  const [running, setRunning] = useState(false);
  const [eventRefreshing, setEventRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [shiftDays, setShiftDays] = useState(1);
  const [surfaceEnabled, setSurfaceEnabled] = useState(false);
  const [surfaceHorizon, setSurfaceHorizon] = useState<10 | 30 | 90>(10);
  const [surfaceJob, setSurfaceJob] = useState<ForecastSurfaceJob | null>(null);
  const [surfaceError, setSurfaceError] = useState("");
  const requestSequence = useRef(0);
  const surfaceJobId = useRef<string | null>(null);
  const invalidateAnalysis = () => {
    setAnalysis(null);
    setSurfaceJob(null);
    setSurfaceError("");
  };

  const chooseSymbol = (value: string) => {
    const stock = stocks.find((item) => item.symbol === value);
    setSymbol(value);
    if (stock) {
      setStartDay(dateToDay(stock.first_observation));
      setEndDay(dateToDay(stock.last_observation));
    }
    invalidateAnalysis();
    setError("");
  };
  const run = useCallback(async (signal?: AbortSignal) => {
    const currentSymbol = selected?.symbol;
    if (!currentSymbol) return;
    const requestId = ++requestSequence.current;
    setRunning(true);
    setError("");
    try {
      const result = await api<RangeAnalysis>("/analyses", {
        method: "POST",
        signal,
        body: JSON.stringify({
          symbol: currentSymbol,
          start_date: dayToDate(startDay),
          end_date: dayToDate(endDay),
        }),
      });
      if (requestId === requestSequence.current) setAnalysis(result);
    } catch (requestError) {
      if ((requestError as { name?: string })?.name === "AbortError") return;
      if (requestId === requestSequence.current) {
        setAnalysis(null);
        setError(requestError instanceof Error ? requestError.message : translations.apiError[language]);
      }
    } finally {
      if (requestId === requestSequence.current) setRunning(false);
    }
  }, [endDay, language, selected?.symbol, startDay]);
  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => void run(controller.signal), 320);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [run, selected]);
  useEffect(() => {
    if (!surfaceEnabled || !analysis || !selected) return;
    let active = true;
    let jobId: string | null = null;
    let terminal = false;
    const terminalStatuses = new Set(["complete", "insufficient_data", "cancelled", "failed"]);
    const compute = async () => {
      try {
        let job = await api<ForecastSurfaceJob>("/analyses/surface-jobs", {
          method: "POST",
          body: JSON.stringify({
            symbol: selected.symbol,
            start_date: analysis.requested_start,
            end_date: analysis.requested_end,
            horizon_sessions: surfaceHorizon,
          }),
        });
        jobId = job.job_id;
        surfaceJobId.current = jobId;
        if (!active) {
          await api(`/analyses/surface-jobs/${jobId}`, { method: "DELETE" }).catch(() => undefined);
          return;
        }
        setSurfaceJob(job);
        while (active && !terminalStatuses.has(job.status)) {
          await new Promise((resolve) => window.setTimeout(resolve, 500));
          if (!active) break;
          job = await api<ForecastSurfaceJob>(`/analyses/surface-jobs/${jobId}`);
          if (!active) break;
          setSurfaceJob(job);
        }
        terminal = terminalStatuses.has(job.status);
      } catch (requestError) {
        if (active) setSurfaceError(requestError instanceof Error ? requestError.message : "Forecast surface computation failed");
      }
    };
    void compute();
    return () => {
      active = false;
      if (jobId && !terminal) {
        void api(`/analyses/surface-jobs/${jobId}`, { method: "DELETE" }).catch(() => undefined);
      }
      if (surfaceJobId.current === jobId) surfaceJobId.current = null;
    };
  }, [analysis, selected, surfaceEnabled, surfaceHorizon]);
  const setStartDate = (value: string) => {
    const parsed = dateToDay(value);
    if (Number.isFinite(parsed)) {
      invalidateAnalysis();
      setStartDay(Math.min(parsed, endDay - 1));
    }
  };
  const setEndDate = (value: string) => {
    const parsed = dateToDay(value);
    if (Number.isFinite(parsed)) {
      invalidateAnalysis();
      setEndDay(Math.max(parsed, startDay + 1));
    }
  };
  const shiftRange = (direction: -1 | 1) => {
    const span = endDay - startDay;
    const requestedShift = direction * shiftDays;
    const shiftedStart = Math.max(minDay, Math.min(maxDay - span, startDay + requestedShift));
    invalidateAnalysis();
    setStartDay(shiftedStart);
    setEndDay(shiftedStart + span);
  };
  const researchForecastEvents = async () => {
    if (!selected || !analysis) return;
    setEventRefreshing(true);
    setError("");
    try {
      await api("/events/company/refresh", {
        method: "POST",
        body: JSON.stringify({
          symbol: selected.symbol,
          start_date: dayToDate(dateToDay(analysis.actual_end) + 1),
          end_date: analysis.forecast_horizon_ends["90"],
        }),
      });
      await run();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t("apiError"));
    } finally {
      setEventRefreshing(false);
    }
  };
  const chartValues = analysis?.series.map((item) => item.close) ?? [];
  const chartLow = chartValues.length ? Math.min(...chartValues) : 0;
  const chartHigh = chartValues.length ? Math.max(...chartValues) : 1;
  const metricDefinitions = useMemo(
    () => new Map((catalog?.items ?? []).map((item) => [item.name, item])),
    [catalog],
  );
  const liveMetricKeys = [
    ["return_5d", t("return5"), "percent"],
    ["return_20d", t("return20"), "percent"],
    ["realized_volatility_20d", t("volatility20"), "percent"],
    ["drawdown_60d", t("drawdown60"), "percent"],
  ] as const;

  if (!selected) return <EmptyMarket onOpenData={() => undefined} />;
  return <div className="page-section">
    <Header eyebrow={t("rangeMetrics")} title={t("rangeMetricsTitle")} copy={t("rangeMetricsCopy")}>
      <label className="inline-control">{t("selectStock")}<select className="filter-select" value={selected.symbol} onChange={(event) => chooseSymbol(event.target.value)}>{stocks.map((stock) => <option key={stock.symbol}>{stock.symbol}</option>)}</select></label>
    </Header>
    <div className="metrics-tabs" role="tablist" aria-label={t("metrics")}>
      <button role="tab" aria-selected={tab === "analysis"} className={tab === "analysis" ? "active" : ""} onClick={() => setTab("analysis")}>{t("analysisTab")}</button>
      <button role="tab" aria-selected={tab === "methodology"} className={tab === "methodology" ? "active" : ""} onClick={() => setTab("methodology")}>{t("methodologyTab")}</button>
    </div>
    {tab === "analysis" ? <>
    <div className="metrics-sticky-toolbar">
      <div className="sticky-range-summary"><span>{selected.symbol} · {t("shiftRange")}</span><strong className="mono">{dayToDate(startDay)} → {dayToDate(endDay)}</strong></div>
      <div className="range-shift-controls">
        <div><label><input type="number" min={1} max={365} value={shiftDays} onChange={(event) => setShiftDays(Math.max(1, Math.min(365, Number(event.target.value) || 1)))} /> {t("shiftDays")}</label></div>
        <button className="secondary-button" disabled={startDay <= minDay} onClick={() => shiftRange(-1)} aria-label={`${t("moveEarlier")} ${shiftDays} ${t("shiftDays")}`}>← {t("moveEarlier")} {shiftDays}</button>
        <button className="secondary-button" disabled={endDay >= maxDay} onClick={() => shiftRange(1)} aria-label={`${t("moveLater")} ${shiftDays} ${t("shiftDays")}`}>{t("moveLater")} {shiftDays} →</button>
      </div>
      <div className="sticky-live-metrics" aria-live="polite">
        {liveMetricKeys.map(([key, label, kind]) => <div key={key}><MetricLabel definition={metricDefinitions.get(key)}>{label}</MetricLabel><strong className="mono">{analysis ? (kind === "percent" ? formatPercent(analysis.metrics[key]) : analysis.metrics[key].toFixed(3)) : "—"}</strong></div>)}
      </div>
      <span className={`tiny-badge ${running ? "" : "live"}`}>{running ? t("calculating") : t("autoCalculate")}</span>
    </div>
    <div className="panel timeline-panel">
      <div className="timeline-dates"><label>{t("startDate")}<input type="date" value={dayToDate(startDay)} min={dayToDate(minDay)} max={dayToDate(endDay - 1)} onChange={(event) => setStartDate(event.target.value)} /></label><label>{t("endDate")}<input type="date" value={dayToDate(endDay)} min={dayToDate(startDay + 1)} max={dayToDate(maxDay)} onChange={(event) => setEndDate(event.target.value)} /></label></div>
      <div className="dual-range" aria-label={t("rangeMetrics")}><input type="range" min={minDay} max={maxDay} value={startDay} onChange={(event) => { invalidateAnalysis(); setStartDay(Math.min(Number(event.target.value), endDay - 1)); }} /><input type="range" min={minDay} max={maxDay} value={endDay} onChange={(event) => { invalidateAnalysis(); setEndDay(Math.max(Number(event.target.value), startDay + 1)); }} /></div>
      <div className="timeline-caption"><span>{dayToDate(minDay)}</span><strong>{dayToDate(startDay)} → {dayToDate(endDay)}</strong><span>{dayToDate(maxDay)}</span></div>
      {error && <div className="workspace-notice error">{error}</div>}
    </div>
    <div className="panel pipeline surface-panel">
      <div className="panel-header"><div><h2 className="panel-title">{t("forecastSurface")}</h2><p className="panel-subtitle">{t("forecastSurfaceCopy")}</p></div><div className="surface-controls">
        <div className="segments">{([10, 30, 90] as const).map((horizon) => <button key={horizon} className={`segment-button ${surfaceHorizon === horizon ? "active" : ""}`} onClick={() => { setSurfaceHorizon(horizon); setSurfaceJob(null); setSurfaceError(""); }}>{horizon}D</button>)}</div>
        <label className="surface-toggle" title={t("autoSurfaceCopy")}><input type="checkbox" checked={surfaceEnabled} onChange={(event) => {
          setSurfaceEnabled(event.target.checked);
          setSurfaceJob(null);
          setSurfaceError("");
        }} /><span>{t("autoSurface")}</span></label>
      </div></div>
      {!surfaceEnabled && <div className="empty-state">{t("surfaceDisabled")}</div>}
      {surfaceEnabled && (!analysis || !surfaceJob) && !surfaceError && <div className="surface-progress-card"><div><strong>{t("surfaceCalculating")}</strong><span>{t("surfaceContinueBrowsing")}</span></div><div className="surface-progress"><i style={{ width: analysis ? "2%" : "0%" }} /></div></div>}
      {surfaceEnabled && surfaceJob && ["queued", "running"].includes(surfaceJob.status) && <div className="surface-progress-card" aria-live="polite"><div><strong>{t("surfaceCalculating")} · {Math.round(surfaceJob.progress)}%</strong><span>{t("surfaceContinueBrowsing")}</span></div><div className="surface-progress"><i style={{ width: `${Math.max(2, surfaceJob.progress)}%` }} /></div></div>}
      {surfaceEnabled && surfaceJob?.status === "insufficient_data" && surfaceJob.result && <div className="empty-state"><strong>{t("surfaceInsufficient")}</strong><span className="mono">{surfaceJob.result.bar_count} / {surfaceJob.result.required_sessions} {t("sessions")}</span><small>{t("surfaceMinimum")}: {surfaceJob.result.minimum_analog_samples} analogs · {surfaceJob.result.minimum_surface_points} {t("surfacePoints")}</small></div>}
      {surfaceEnabled && surfaceJob?.status === "complete" && surfaceJob.result && <><ForecastSurfaceChart result={surfaceJob.result} /><div className="surface-meta mono"><span>{surfaceJob.result.point_count} {t("surfacePoints")}</span><span>{t("samplingEvery")} {surfaceJob.result.sampling_interval_sessions ?? 1} {t("sessions")}</span><span>Cutoff {surfaceJob.result.data_cutoff}</span></div></>}
      {surfaceEnabled && (surfaceError || surfaceJob?.status === "failed") && <div className="workspace-notice error">{surfaceError || surfaceJob?.error || t("surfaceFailed")}</div>}
    </div>
    {analysis && <>
      <div className="panel coverage-panel"><div><span>{t("requestedRange")}</span><strong className="mono">{analysis.requested_start} → {analysis.requested_end}</strong></div><div><span>{t("actualCoverage")}</span><strong className="mono">{analysis.actual_start} → {analysis.actual_end}</strong></div><div><span>{t("sessions")}</span><strong className="mono">{analysis.bar_count}</strong></div>{analysis.coverage_warnings.length > 0 && <p className="coverage-warning">{t("coverageGap")}</p>}</div>
      <div className="panel range-chart"><div className="panel-header"><div><h2 className="panel-title">{analysis.symbol}</h2><p className="panel-subtitle">{analysis.source} · {analysis.metric_version}</p></div></div><div className="range-chart-bars">{analysis.series.map((point) => <span key={point.date} title={`${point.date}: ${point.close}`} style={{ height: `${chartHigh === chartLow ? 50 : 10 + 85 * (point.close - chartLow) / (chartHigh - chartLow)}%` }} />)}</div></div>
      <div className="panel pipeline"><div className="panel-header"><div><h2 className="panel-title">{t("metricsSnapshot")}</h2><p className="panel-subtitle">Cutoff {analysis.data_cutoff}</p></div></div><div className="result-grid metric-results">
        {[["return_5d", t("return5"), "percent"], ["return_20d", t("return20"), "percent"], ["realized_volatility_20d", t("volatility20"), "percent"], ["volume_zscore_20d", t("volumeZ"), "decimal"], ["distance_ma20", t("distanceMa"), "percent"], ["drawdown_60d", t("drawdown60"), "percent"]].map(([key, label, kind]) => <div className="result-card" key={key}><div className="result-label"><MetricLabel definition={metricDefinitions.get(key)}>{label}</MetricLabel></div><div className="result-value mono">{kind === "percent" ? formatPercent(analysis.metrics[key]) : analysis.metrics[key].toFixed(3)}</div></div>)}
      </div></div>
      <div className="panel pipeline"><div className="panel-header"><div><h2 className="panel-title">{t("forecast")}</h2><p className="panel-subtitle">{t("forecastDisclaimer")}</p></div></div><div className="forecast-grid">
        {[10, 30, 90].map((horizon) => {
          const forecast = analysis.forecasts[String(horizon)];
          const medianReturn = forecast.p50_return ?? forecast.median_return;
          const displayedDirection = medianReturn == null || Math.abs(medianReturn) < 0.00005
            ? "neutral"
            : medianReturn > 0
              ? "up"
              : "down";
          return <div className={`forecast-card forecast-${displayedDirection}`} key={horizon}>
            <div className="forecast-top"><strong>{horizon} {t("sessions")}</strong><span className="tiny-badge">{forecast.status}</span></div>
            {forecast.status === "complete" ? <>
              <div><span>{t("medianReturn")} (50%)</span><strong className="mono">{formatPercent(medianReturn)}</strong></div>
              <div><span>{t("range1090")}</span><strong className="mono">{formatPercent(forecast.p10_return)} → {formatPercent(forecast.p90_return)}</strong></div>
              <div className="forecast-price-heading"><span>{t("forecastPrices")}</span><small>{forecast.origin_date} · ${forecast.origin_price?.toFixed(2)}</small></div>
              <div className="forecast-price-levels">
                <div><span>{t("p10Price")}</span><strong className="mono">${forecast.p10_price?.toFixed(2)}</strong></div>
                <div className="median"><span>{t("p50Price")}</span><strong className="mono">${forecast.p50_price?.toFixed(2)}</strong></div>
                <div><span>{t("p90Price")}</span><strong className="mono">${forecast.p90_price?.toFixed(2)}</strong></div>
              </div>
              <ForecastBandChart forecast={forecast} />
              <div><span>{t("positiveProbability")}</span><strong className="mono">{formatPercent(forecast.positive_probability, 1)}</strong></div>
              <small>{forecast.sample_count} {t("analogSamples")}</small>
            </> : <p>{t("insufficient")} ({forecast.sample_count})</p>}
          </div>;
        })}
      </div></div>
      <div className="panel pipeline"><div className="panel-header"><div><h2 className="panel-title">{t("forecastWindowEvents")}</h2><p className="panel-subtitle">{analysis.actual_end} → {analysis.forecast_horizon_ends["90"]}</p></div><button className="secondary-button" disabled={eventRefreshing} onClick={() => void researchForecastEvents()}>{eventRefreshing ? t("refreshingEvents") : t("researchForecastEvents")}</button></div>
        {analysis.scheduled_events.length ? <div className="forecast-event-list">{analysis.scheduled_events.map((event) => {
          const content = localizedEventContent(event, language);
          return <article className="forecast-event-row" key={event.event_id}><div><div className="event-card-top"><span className="tiny-badge">{event.event_type}</span><strong>{event.symbol} · {content.title}</strong></div><p>{content.summary}</p><div className="note-tags">{event.forecast_horizons?.map((item) => <span className="tiny-badge live" key={item}>{item}D</span>)}</div></div><div><strong className="mono">{event.event_date_start ?? "—"}</strong><EventSourceLinks sources={event.sources} heading={false} /></div></article>;
        })}</div> : <div className="empty-state">{t("noForecastEvents")}</div>}
      </div>
      <p className="forecast-footnote">{language === "zh" ? "此 forecast 僅供研究與回測設計，不構成投資建議。" : "This forecast supports research and backtest design only; it is not investment advice."}</p>
    </>}
    </> : <MetricsMethodology catalog={catalog} />}
  </div>;
}

function EventCard({ event, onResolve, onOpenSymbol, busy }: { event: ResearchEvent; onResolve: (eventId: string) => Promise<void>; onOpenSymbol: (symbol: string) => void; busy: boolean }) {
  const { language, t } = useI18n();
  const content = localizedEventContent(event, language);
  const actualResults = Array.isArray(event.actual.actual_results)
    ? event.actual.actual_results.filter((item): item is string => typeof item === "string")
    : [];
  const reactionReturns = event.reaction.returns ?? {};
  const canResolve = event.scope === "company" && ["scheduled", "date_uncertain"].includes(event.status);
  return <article className="event-card">
    <div className="event-card-top"><div className="note-tags"><span className={`tiny-badge ${event.status === "occurred" ? "live" : ""}`}>{event.status}</span><span className="tiny-badge">{event.event_type}</span>{event.symbol && <span className="tiny-badge">{event.symbol}</span>}</div><span className="mono event-date">{event.event_date_start ?? "—"}</span></div>
    <h3>{content.title}</h3><p>{content.summary}</p>
    {language === "zh" && !content.hasChineseTranslation && <small className="translation-unavailable">{t("translationUnavailable")}</small>}
    <div className="event-facts"><span>{t("importance")} <strong>{event.importance}/5</strong></span><span>{t("confidence")} <strong>{formatPercent(event.confidence, 0)}</strong></span><span>{event.model}</span></div>
    {content.impact && <MarketImpactPanel impact={content.impact} matches={event.portfolio_matches ?? []} onOpenSymbol={onOpenSymbol} />}
    {Object.keys(content.expectations).length > 0 && <div className="event-detail"><strong>{t("expectations")}</strong>{Object.entries(content.expectations).map(([key, value]) => Array.isArray(value) ? <div key={key}><small>{key.replaceAll("_", " ")}</small><ul>{value.filter((item): item is string => typeof item === "string").map((item) => <li key={item}>{item}</li>)}</ul></div> : value ? <p key={key}><small>{key.replaceAll("_", " ")}</small>{String(value)}</p> : null)}</div>}
    {content.watchItems.length > 0 && <div className="event-detail"><strong>{t("watchItems")}</strong><ul>{content.watchItems.map((item) => <li key={item}>{item}</li>)}</ul></div>}
    {actualResults.length > 0 && <div className="event-detail actual"><strong>{t("actualResult")}</strong><ul>{actualResults.map((item) => <li key={item}>{item}</li>)}</ul></div>}
    {Object.keys(reactionReturns).length > 0 && <div className="event-detail reaction"><strong>{t("marketReaction")}</strong><div className="reaction-grid">{[1, 5, 20].map((sessions) => { const item = reactionReturns[`${sessions}_session`]; return <div key={sessions}><small>{sessions}D</small><b className="mono">{formatPercent(item?.symbol_return)}</b><span className="mono">excess {formatPercent(item?.excess_return)}</span></div>; })}</div><small>{event.reaction.benchmark ?? "SPY"} · cutoff {event.reaction.data_cutoff ?? "—"}</small></div>}
    <div className="event-card-footer"><EventSourceLinks sources={event.sources} />{canResolve && <button className="secondary-button" disabled={busy} onClick={() => void onResolve(event.event_id)}>{t("resolveEvent")}</button>}</div>
  </article>;
}

function ConfidencePanel({ center, stocks, onRefresh, busy }: { center: ConfidenceCenter | null; stocks: Stock[]; onRefresh: (symbol: string) => Promise<void>; busy: boolean }) {
  const { t } = useI18n();
  const [symbol, setSymbol] = useState(stocks.find((stock) => stock.symbol === "AAPL")?.symbol ?? stocks[0]?.symbol ?? "");
  const snapshots = center?.snapshots.filter((item) => item.symbol === symbol) ?? [];
  const institutions = snapshots.filter((item) => item.dimension === "institution");
  const longTerm = snapshots.filter((item) => item.dimension === "company_long_term");
  return <section className="panel confidence-panel"><div className="panel-header"><div><h2 className="panel-title">{t("confidenceTracking")}</h2><p className="panel-subtitle">{t("confidenceTrackingCopy")}</p></div><div className="heading-actions"><select className="filter-select" value={symbol} onChange={(event) => setSymbol(event.target.value)}>{stocks.map((stock) => <option key={stock.symbol}>{stock.symbol}</option>)}</select><button className="secondary-button" disabled={busy || !symbol || !center?.provider_configured} onClick={() => void onRefresh(symbol)}>{busy ? t("refreshingEvents") : t("refreshConfidence")}</button></div></div>
    {!snapshots.length ? <div className="empty-state">{t("noConfidence")}</div> : <div className="confidence-columns"><div><h3>{t("institutionalWeekly")}</h3>{institutions.map((snapshot) => <div className="confidence-row" key={snapshot.snapshot_key}><div><strong>{snapshot.entity}</strong><small>{snapshot.period_start} · {snapshot.evidence_count} {t("evidence")}</small></div><span className="confidence-score mono">{snapshot.score?.toFixed(1) ?? "—"}</span></div>)}</div><div><h3>{t("longTermMonthly")}</h3>{longTerm.map((snapshot) => <div className="long-confidence" key={snapshot.snapshot_key}><div className="confidence-hero"><span className="confidence-score mono">{snapshot.score?.toFixed(1) ?? "—"}</span><div><strong>{snapshot.period_start}</strong><small>{t("coverage")}: {snapshot.coverage_status}</small></div></div><div className="confidence-components">{[["market_price", t("marketPriceComponent")], ["institutional", t("institutionComponent")], ["brand_evidence", t("brandComponent")]].map(([key, label]) => <div key={key}><span>{label}</span><strong className="mono">{snapshot.components.scores?.[key]?.toFixed(1) ?? "—"}</strong></div>)}</div><div className="event-source-links">{snapshot.sources.map((source) => <a key={source.url} href={source.url} target="_blank" rel="noopener noreferrer">{source.title || new URL(source.url).hostname}</a>)}</div></div>)}</div></div>}
  </section>;
}

function EventsView({ center, confidence, stocks, reload, onOpenSymbol }: { center: EventCenter | null; confidence: ConfidenceCenter | null; stocks: Stock[]; reload: () => Promise<void>; onOpenSymbol: (symbol: string) => void }) {
  const { t } = useI18n();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const act = async (name: string, path: string, body?: object) => {
    setBusy(name); setError("");
    try {
      await api(path, { method: "POST", body: JSON.stringify(body ?? {}) });
      await reload();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t("apiError"));
    } finally {
      setBusy("");
    }
  };
  const world = center?.events.filter((event) => event.scope === "world") ?? [];
  const company = center?.events.filter((event) => event.scope === "company") ?? [];
  return <div className="page-section"><Header eyebrow={t("eventResearch")} title={t("eventResearchTitle")} copy={t("eventResearchCopy")}><button className="secondary-button" disabled={Boolean(busy) || !center?.provider_configured} onClick={() => void act("world", "/events/world/refresh")}>{busy === "world" ? t("refreshingEvents") : t("refreshWorld")}</button><button className="secondary-button" disabled={Boolean(busy) || !center?.provider_configured || !center.due_event_count} onClick={() => void act("due", "/events/due/resolve", { limit: 5 })}>{t("resolveDue")} ({center?.due_event_count ?? 0})</button><button className="secondary-button" disabled={Boolean(busy)} onClick={() => void act("reaction", "/events/reactions/refresh")}>{t("refreshReactions")}</button></Header>
    {error && <div className="workspace-notice error">{error}</div>}
    {!center?.provider_configured && <div className="panel empty-market"><span className="tiny-badge">{t("emptyByDesign")}</span><h2>{t("aiKeyMissing")}</h2><p>{t("aiKeyMissingCopy")}</p>{center?.configuration_error && <small className="mono negative-text">{center.configuration_error}</small>}</div>}
    <ClassificationPanel center={center} busy={busy === "classifications"} refresh={() => act("classifications", "/instruments/classifications/refresh")} />
    {center?.provider_configured && !center.events.length && <div className="panel empty-market"><h2>{t("noStoredEvents")}</h2><p>{t("noStoredEventsCopy")}</p></div>}
    {world.length > 0 && <section><div className="section-heading"><h2>{t("worldEvents")}</h2><span>{world.length}</span></div><div className="event-grid">{world.map((event) => <EventCard key={event.event_id} event={event} busy={Boolean(busy)} onOpenSymbol={onOpenSymbol} onResolve={(eventId) => act(`event-${eventId}`, `/events/${eventId}/resolve`)} />)}</div></section>}
    {company.length > 0 && <section><div className="section-heading"><h2>{t("companyEvents")}</h2><span>{company.length}</span></div><div className="event-grid">{company.map((event) => <EventCard key={event.event_id} event={event} busy={Boolean(busy)} onOpenSymbol={onOpenSymbol} onResolve={(eventId) => act(`event-${eventId}`, `/events/${eventId}/resolve`)} />)}</div></section>}
    <ConfidencePanel center={confidence} stocks={stocks} busy={Boolean(busy)} onRefresh={(symbol) => act(`confidence-${symbol}`, "/confidence/refresh", { symbol })} />
    <section className="panel pipeline"><div className="panel-header"><div><h2 className="panel-title">{t("aiRunHistory")}</h2><p className="panel-subtitle">{center?.prompt_version}</p></div></div><div className="activity-list">{center?.runs.length ? center.runs.map((run) => <div className="activity-row" key={run.run_id}><span className={`tiny-badge ${run.status === "complete" ? "live" : ""}`}>{run.status}</span><span>{run.scope} · {run.model}</span><time>{new Date(run.created_at).toLocaleString()}</time>{run.error && <small className="negative-text">{run.error}</small>}</div>) : <div className="empty-state">{t("noAiRuns")}</div>}</div></section>
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

function PortfolioView({
  center,
  setCenter,
  onOpenData,
  notify,
}: {
  center: PortfolioCenter;
  setCenter: (center: PortfolioCenter) => void;
  onOpenData: () => void;
  notify: (message: string) => void;
}) {
  const { language, t } = useI18n();
  const [account, setAccount] = useState("");
  const [symbol, setSymbol] = useState("");
  const [shares, setShares] = useState("");
  const [averageCost, setAverageCost] = useState("");
  const [acquiredDate, setAcquiredDate] = useState("");
  const [editing, setEditing] = useState<{ holding: PortfolioHolding; lot: PortfolioLot } | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const [busy, setBusy] = useState<"save" | "delete" | "">("");
  const [error, setError] = useState("");
  const money = (value: number | null) => value == null
    ? "—"
    : new Intl.NumberFormat(language === "zh" ? "zh-TW" : "en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 2,
    }).format(value);
  const resetForm = () => {
    setAccount("");
    setSymbol("");
    setShares("");
    setAverageCost("");
    setAcquiredDate("");
    setEditing(null);
  };
  const dateTime = (value: string | null) => value
    ? new Intl.DateTimeFormat(language === "zh" ? "zh-TW" : "en-US", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value))
    : t("neverUpdated");
  const startEdit = (holding: PortfolioHolding, lot: PortfolioLot) => {
    setEditing({ holding, lot });
    setAccount(holding.account_name);
    setSymbol(holding.symbol);
    setShares(String(lot.shares));
    setAverageCost(String(lot.unit_cost));
    setAcquiredDate(lot.acquired_date ?? "");
    setError("");
  };
  const toggleExpanded = (holdingId: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(holdingId)) next.delete(holdingId);
      else next.add(holdingId);
      return next;
    });
  };
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy("save");
    setError("");
    try {
      const result = await api<PortfolioCenter>("/portfolio/holdings", {
        method: "POST",
        body: JSON.stringify({
          lot_id: editing?.lot.lot_id ?? null,
          account_name: account.trim(),
          symbol: symbol.trim().toUpperCase(),
          shares: Number(shares),
          average_cost: Number(averageCost),
          acquired_date: acquiredDate || null,
        }),
      });
      setCenter(result);
      resetForm();
      notify(t("holdingSaved"));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t("apiError"));
    } finally {
      setBusy("");
    }
  };
  const remove = async (lot: PortfolioLot) => {
    if (!window.confirm(t("confirmDeleteHolding"))) return;
    setBusy("delete");
    setError("");
    try {
      const result = await api<PortfolioCenter>(`/portfolio/holding-lots/${lot.lot_id}`, { method: "DELETE" });
      setCenter(result);
      if (editing?.lot.lot_id === lot.lot_id) resetForm();
      notify(t("holdingDeleted"));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t("apiError"));
    } finally {
      setBusy("");
    }
  };
  const canSave = account.trim() && symbol.trim() && Number(shares) > 0 && Number(averageCost) >= 0;
  return <div className="page-section">
    <Header eyebrow={t("portfolioEyebrow")} title={t("portfolioTitle")} copy={t("portfolioCopy")} />
    {error && <div className="workspace-notice error">{error}</div>}
    <div className="summary-grid portfolio-summary">
      <div className="summary-card featured"><div className="summary-card-label">{t("holdingCount")}</div><div className="summary-value mono">{center.summary.holding_count}</div><div className="summary-meta">{center.summary.account_count} {t("accountCount")}</div></div>
      <div className="summary-card"><div className="summary-card-label">{t("costBasis")}</div><div className="summary-value mono">{money(center.summary.total_cost_basis)}</div><div className="summary-meta">{center.summary.lot_count} {t("lotCount")}</div></div>
      <div className="summary-card"><div className="summary-card-label">{t("marketValue")}</div><div className="summary-value mono">{money(center.summary.market_value)}</div><div className="summary-meta">{t("pricingCoverage")} {center.summary.priced_count}/{center.summary.holding_count}</div></div>
      <div className="summary-card"><div className="summary-card-label">{t("unrealizedPL")}</div><div className={`summary-value mono ${(center.summary.unrealized_pl ?? 0) >= 0 ? "positive-text" : "negative-text"}`}>{money(center.summary.unrealized_pl)}</div><div className="summary-meta">{formatPercent(center.summary.unrealized_percent)}</div></div>
    </div>
    {center.summary.missing_price_symbols.length > 0 && <div className="portfolio-price-warning"><div><strong>{t("missingStoredPrice")}</strong><p>{t("missingPriceCopy")} <span className="mono">{center.summary.missing_price_symbols.join(", ")}</span></p></div><button className="secondary-button" onClick={onOpenData}>{t("openDataSyncShort")}</button></div>}
    <div className="portfolio-layout">
      <section className="panel portfolio-form-panel">
        <div className="panel-header"><div><h2 className="panel-title">{editing ? t("updateHolding") : t("addHolding")}</h2><p className="panel-subtitle">{t("localHoldingFormCopy")}</p></div></div>
        <form className="portfolio-form" onSubmit={(event) => void save(event)}>
          <label>{t("accountName")}<input value={account} readOnly={Boolean(editing)} onChange={(event) => setAccount(event.target.value)} placeholder="Robinhood / Fidelity / Etrade" /></label>
          <label>{t("symbol")}<input className="mono" value={symbol} readOnly={Boolean(editing)} onChange={(event) => setSymbol(event.target.value.toUpperCase())} placeholder="AAPL" /></label>
          <div className="portfolio-form-pair"><label>{t("sharesHeld")}<input type="number" min="0.00000001" step="any" value={shares} onChange={(event) => setShares(event.target.value)} /></label><label>{t("averageCost")}<input type="number" min="0" step="any" value={averageCost} onChange={(event) => setAverageCost(event.target.value)} /></label></div>
          <label>{t("acquiredDate")}<input type="date" value={acquiredDate} max={DEFAULT_SYNC_END} onChange={(event) => setAcquiredDate(event.target.value)} /></label>
          <div className="portfolio-form-actions"><button className="primary-button" disabled={!canSave || Boolean(busy)}>{busy === "save" ? t("savingHolding") : editing ? t("updateHolding") : t("saveHolding")}</button>{editing && <button type="button" className="secondary-button" onClick={resetForm}>{t("cancelEdit")}</button>}</div>
        </form>
      </section>
      <section className="panel portfolio-table-panel">
        <div className="panel-header"><div><h2 className="panel-title">{t("portfolio")}</h2><p className="panel-subtitle">{t("portfolioEyebrow")}</p></div><div className="portfolio-update-time"><span>{t("lastUpdatedAt")}</span><strong>{dateTime(center.summary.last_updated_at)}</strong></div></div>
        {center.items.length ? <div className="table-wrap"><table className="data-table portfolio-table"><thead><tr><th>{t("accountName")}</th><th>{t("symbol")}</th><th>{t("sharesHeld")}</th><th>{t("averageCost")}</th><th>{t("latestStoredPrice")}</th><th>{t("marketValue")}</th><th>{t("unrealizedPL")}</th><th>{t("lotCount")}</th><th>{t("holdingSource")}</th><th /></tr></thead><tbody>
          {center.items.map((holding) => {
            const isExpanded = expanded.has(holding.holding_id);
            return <Fragment key={holding.holding_id}>
              <tr className={`portfolio-summary-row ${isExpanded ? "expanded" : ""}`} onClick={() => toggleExpanded(holding.holding_id)}>
                <td><div className="portfolio-account-cell"><button className="holding-expander" aria-label={isExpanded ? t("collapseHolding") : t("expandHolding")} aria-expanded={isExpanded} onClick={(event) => { event.stopPropagation(); toggleExpanded(holding.holding_id); }}>{isExpanded ? "−" : "+"}</button><strong>{holding.account_name}</strong></div></td>
                <td><strong className="mono">{holding.symbol}</strong></td>
                <td className="mono">{holding.shares.toLocaleString(undefined, { maximumFractionDigits: 6 })}</td>
                <td className="mono">{money(holding.average_cost)}</td>
                <td className="mono">{holding.latest_price == null ? "—" : <>{money(holding.latest_price)}<small>{holding.price_date}</small></>}</td>
                <td className="mono">{money(holding.market_value)}</td>
                <td className={`mono ${(holding.unrealized_pl ?? 0) >= 0 ? "positive-text" : "negative-text"}`}>{money(holding.unrealized_pl)}<small>{formatPercent(holding.unrealized_percent)}</small></td>
                <td><span className="lot-count-badge">{holding.lots.length}</span></td>
                <td><span className="tiny-badge">{holding.source}</span></td>
                <td><span className="row-expand-copy">{isExpanded ? t("collapseHolding") : t("expandHolding")}</span></td>
              </tr>
              {isExpanded && <tr className="portfolio-detail-row"><td colSpan={10}>
                <div className="holding-detail">
                  <div className="holding-detail-title"><strong>{holding.symbol} · {t("holdingLots")}</strong><span>{holding.lots.length} {t("lotCount")}</span></div>
                  <div className="holding-lot-list">
                    {holding.lots.map((lot, index) => <div className="holding-lot" key={lot.lot_id}>
                      <div className="lot-number mono">#{index + 1}</div>
                      <div><span>{t("acquiredDate")}</span><strong className="mono">{lot.acquired_date ?? "—"}</strong></div>
                      <div><span>{t("sharesHeld")}</span><strong className="mono">{lot.shares.toLocaleString(undefined, { maximumFractionDigits: 6 })}</strong></div>
                      <div><span>{t("unitCost")}</span><strong className="mono">{money(lot.unit_cost)}</strong></div>
                      <div><span>{t("costBasis")}</span><strong className="mono">{money(lot.cost_basis)}</strong></div>
                      <div><span>{t("enteredAt")}</span><strong>{dateTime(lot.created_at)}</strong></div>
                      <div className="holding-actions"><button className="table-action" onClick={(event) => { event.stopPropagation(); startEdit(holding, lot); }}>{t("editHolding")}</button><button className="table-action danger" disabled={busy === "delete"} onClick={(event) => { event.stopPropagation(); void remove(lot); }}>{t("deleteHolding")}</button></div>
                    </div>)}
                  </div>
                </div>
              </td></tr>}
            </Fragment>;
          })}
        </tbody></table></div> : <div className="empty-market portfolio-empty"><h2>{t("noHoldings")}</h2><p>{t("noHoldingsCopy")}</p></div>}
      </section>
    </div>
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
  const [eventCenter, setEventCenter] = useState<EventCenter | null>(null);
  const [confidenceCenter, setConfidenceCenter] = useState<ConfidenceCenter | null>(null);
  const [metricCatalog, setMetricCatalog] = useState<MetricCatalog | null>(null);
  const [portfolioCenter, setPortfolioCenter] = useState<PortfolioCenter | null>(null);
  const [horizon, setHorizon] = useState<Horizon>("30D");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [running, setRunning] = useState(false);
  const navItems: { id: View; label: string; icon: string }[] = [
    { id: "overview", label: t("overview"), icon: "⌁" }, { id: "scanner", label: t("scanner"), icon: "◎" }, { id: "metrics", label: t("metrics"), icon: "↔" }, { id: "portfolio", label: t("portfolio"), icon: "◫" }, { id: "events", label: t("events"), icon: "◉" }, { id: "backtest", label: t("backtests"), icon: "ƒ" }, { id: "data", label: t("dataPipeline"), icon: "⇄" },
  ];

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [overviewResult, scannerResult, pipelineResult, backtestResult, eventResult, confidenceResult, metricResult, portfolioResult] = await Promise.all([api<Overview>("/overview"), api<{ items: Stock[] }>("/scanner?horizon=30D"), api<Pipeline>("/pipeline"), api<{ items: Backtest[] }>("/backtests"), api<EventCenter>("/events"), api<ConfidenceCenter>("/confidence"), api<MetricCatalog>("/metrics/catalog"), api<PortfolioCenter>("/portfolio")]);
      setOverview(overviewResult); setStocks(scannerResult.items); setPipeline(pipelineResult); setBacktests(backtestResult.items); setEventCenter(eventResult); setConfidenceCenter(confidenceResult); setMetricCatalog(metricResult); setPortfolioCenter(portfolioResult);
      setActiveStock((current) => scannerResult.items.find((stock) => stock.symbol === current?.symbol) ?? scannerResult.items[0] ?? null);
    } catch (loadError) {
      setOverview(null); setStocks([]); setActiveStock(null); setPipeline(null); setBacktests([]); setEventCenter(null); setConfidenceCenter(null); setMetricCatalog(null); setPortfolioCenter(null); setError(loadError instanceof Error ? loadError.message : "API unavailable");
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
        {!loading && !error && view === "overview" && overview && <div className="page-section"><Header eyebrow={t("realStoredData")} title={t("researchStored")} copy={t("researchStoredCopy")} />{overview.market.bar_count === 0 ? <EmptyMarket onOpenData={() => setView("data")} /> : <><SummaryCards overview={overview} /><div className="content-grid"><div className="panel"><div className="panel-header"><div><h2 className="panel-title">{t("storedUniverse")}</h2><p className="panel-subtitle">{t("realCrossSection")}</p></div><button className="secondary-button" onClick={() => setView("scanner")}>{t("viewScanner")}</button></div><StockTable stocks={stocks} active={activeStock} setActive={setActiveStock} horizon={horizon} search={search} catalog={metricCatalog} /></div>{activeStock && <StockDetail stock={activeStock} horizon={horizon} catalog={metricCatalog} />}</div></>}</div>}
        {!loading && !error && view === "scanner" && <div className="page-section"><Header eyebrow="Massive EOD" title={t("compareReal")} copy={t("compareRealCopy")}><div className="segments">{(["10D", "30D", "90D"] as Horizon[]).map((item) => <button key={item} className={`segment-button ${horizon === item ? "active" : ""}`} onClick={() => setHorizon(item)}>{item}</button>)}</div></Header>{!stocks.length ? <EmptyMarket onOpenData={() => setView("data")} /> : <div className="content-grid"><div className="panel"><StockTable stocks={stocks} active={activeStock} setActive={setActiveStock} horizon={horizon} search={search} catalog={metricCatalog} /></div>{activeStock && <StockDetail stock={activeStock} horizon={horizon} catalog={metricCatalog} />}</div>}</div>}
        {!loading && !error && <div className={view === "metrics" ? "" : "view-hidden"} aria-hidden={view !== "metrics"}><MetricsView stocks={stocks} catalog={metricCatalog} /></div>}
        {!loading && !error && view === "portfolio" && portfolioCenter && <PortfolioView center={portfolioCenter} setCenter={setPortfolioCenter} onOpenData={() => setView("data")} notify={setToast} />}
        {!loading && !error && view === "events" && <EventsView center={eventCenter} confidence={confidenceCenter} stocks={stocks} reload={load} onOpenSymbol={(symbol) => { const stock = stocks.find((item) => item.symbol === symbol); if (stock) { setActiveStock(stock); setSearch(symbol); setView("scanner"); } }} />}
        {!loading && !error && view === "backtest" && <BacktestView backtests={backtests} run={runBacktest} running={running} />}
        {!loading && !error && view === "data" && <DataView pipeline={pipeline} sync={sync} syncing={syncing} />}
      </main></div>{toast && <div className="toast">{toast}</div>}</div>;
}

export function PrismApp({ initialUser }: { initialUser: PrismUser | null }) {
  const [language, setLanguage] = useState<Language>("zh");
  return <LanguageContext.Provider value={language}><AppContent initialUser={initialUser} language={language} setLanguage={setLanguage} /></LanguageContext.Provider>;
}
