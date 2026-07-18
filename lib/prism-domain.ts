export type Horizon = "10D" | "30D" | "90D";
export type PredictionOutcome = "Pending" | "Correct" | "Incorrect" | "Neutral";

export type FormulaWeights = {
  momentum: number;
  relativeStrength: number;
  trendQuality: number;
  volumeConfirmation: number;
  volatility: number;
};

export type Stock = {
  symbol: string;
  name: string;
  sector: string;
  price: number;
  change: number;
  momentum: number;
  relativeStrength: number;
  trendQuality: number;
  volumeConfirmation: number;
  volatility: number;
  score10: number;
  score30: number;
  score90: number;
  confidence: number;
  signal: string;
  signalCopy: string;
  bars: number[];
  metrics: Record<string, number>;
};

export type LedgerRow = {
  predictionId: string;
  createdAt: string;
  dataCutoff: string;
  symbol: string;
  horizon: Horizon;
  direction: "Bullish" | "Neutral" | "Bearish";
  confidence: number;
  expectedRange: string;
  actualOutcome: string;
  outcome: PredictionOutcome;
  formulaVersion: string;
  metricVersion: string;
  recordHash: string;
  previousHash: string | null;
  source: "demo" | "user";
};

export const DATA_CUTOFF = "2026-07-17T20:00:00.000Z";
export const METRIC_VERSION = "price-core-v1.0";
export const DEFAULT_FORMULA_VERSION = "core-30d-v1.0";

export const DEFAULT_WEIGHTS: FormulaWeights = {
  momentum: 0.3,
  relativeStrength: 0.25,
  trendQuality: 0.2,
  volumeConfirmation: 0.15,
  volatility: -0.1,
};

export const STOCKS: Stock[] = [
  {
    symbol: "NVDA", name: "NVIDIA", sector: "Semiconductors", price: 184.92,
    change: 2.84, momentum: 91, relativeStrength: 94, trendQuality: 86,
    volumeConfirmation: 71, volatility: 63, score10: 72, score30: 81,
    score90: 76, confidence: 68, signal: "Constructive momentum",
    signalCopy: "Relative strength and volume confirmation remain positive. Elevated volatility keeps this below a high-conviction threshold.",
    bars: [24, 31, 28, 39, 44, 38, 48, 51, 46, 57, 54, 63, 61, 69, 74, 68, 76, 72, 81, 88, 82, 94],
    metrics: { return_5d: 0.068, return_20d: 0.184, realized_volatility_20d: 0.436, volume_zscore_20d: 1.21, distance_ma20: 0.117, drawdown_60d: -0.018 },
  },
  {
    symbol: "AVGO", name: "Broadcom", sector: "Semiconductors", price: 344.83,
    change: 3.21, momentum: 95, relativeStrength: 92, trendQuality: 79,
    volumeConfirmation: 84, volatility: 76, score10: 74, score30: 79,
    score90: 65, confidence: 66, signal: "Strong, with tail risk",
    signalCopy: "The highest momentum profile in the current universe is offset by elevated realized volatility and a stretched distance from trend.",
    bars: [21, 28, 25, 36, 31, 44, 39, 52, 48, 61, 55, 66, 62, 74, 69, 80, 72, 86, 81, 92, 88, 96],
    metrics: { return_5d: 0.082, return_20d: 0.211, realized_volatility_20d: 0.512, volume_zscore_20d: 1.48, distance_ma20: 0.142, drawdown_60d: -0.011 },
  },
  {
    symbol: "META", name: "Meta Platforms", sector: "Interactive Media", price: 739.46,
    change: 1.36, momentum: 84, relativeStrength: 88, trendQuality: 82,
    volumeConfirmation: 59, volatility: 42, score10: 68, score30: 77,
    score90: 73, confidence: 64, signal: "Positive, not extended",
    signalCopy: "Medium-term trend is healthy and volatility is controlled. The current setup ranks well without entering an extreme percentile.",
    bars: [29, 35, 33, 40, 37, 44, 49, 46, 53, 55, 51, 62, 67, 64, 69, 73, 71, 77, 80, 78, 85, 88],
    metrics: { return_5d: 0.041, return_20d: 0.126, realized_volatility_20d: 0.298, volume_zscore_20d: 0.63, distance_ma20: 0.081, drawdown_60d: -0.026 },
  },
  {
    symbol: "MSFT", name: "Microsoft", sector: "Software", price: 523.18,
    change: 0.78, momentum: 73, relativeStrength: 71, trendQuality: 88,
    volumeConfirmation: 54, volatility: 29, score10: 61, score30: 69,
    score90: 75, confidence: 61, signal: "Steady accumulation",
    signalCopy: "Trend quality is better than raw momentum suggests. Lower realized volatility supports the 30 and 90-day risk-adjusted outlook.",
    bars: [36, 39, 42, 40, 45, 48, 46, 50, 49, 54, 57, 55, 59, 61, 60, 64, 66, 65, 69, 72, 70, 75],
    metrics: { return_5d: 0.027, return_20d: 0.079, realized_volatility_20d: 0.214, volume_zscore_20d: 0.34, distance_ma20: 0.052, drawdown_60d: -0.019 },
  },
  {
    symbol: "JPM", name: "JPMorgan Chase", sector: "Banks", price: 301.27,
    change: 0.32, momentum: 64, relativeStrength: 67, trendQuality: 81,
    volumeConfirmation: 47, volatility: 24, score10: 56, score30: 65,
    score90: 70, confidence: 58, signal: "Quietly constructive",
    signalCopy: "Positive relative strength and low volatility make the longer horizon more attractive than the short-term setup.",
    bars: [41, 43, 40, 45, 48, 47, 51, 49, 53, 55, 54, 58, 57, 61, 63, 62, 66, 65, 69, 71, 70, 73],
    metrics: { return_5d: 0.019, return_20d: 0.061, realized_volatility_20d: 0.187, volume_zscore_20d: 0.22, distance_ma20: 0.038, drawdown_60d: -0.014 },
  },
  {
    symbol: "AAPL", name: "Apple", sector: "Technology Hardware", price: 259.71,
    change: -0.42, momentum: 52, relativeStrength: 46, trendQuality: 58,
    volumeConfirmation: 39, volatility: 31, score10: 49, score30: 54,
    score90: 61, confidence: 51, signal: "No actionable edge",
    signalCopy: "Volatility is benign, but the stock is not demonstrating enough relative strength for the formula to separate it from the benchmark.",
    bars: [57, 55, 59, 62, 58, 54, 60, 63, 61, 66, 64, 62, 65, 61, 58, 56, 59, 55, 57, 54, 52, 51],
    metrics: { return_5d: -0.014, return_20d: -0.032, realized_volatility_20d: 0.226, volume_zscore_20d: -0.18, distance_ma20: -0.019, drawdown_60d: -0.073 },
  },
  {
    symbol: "AMZN", name: "Amazon", sector: "Consumer Discretionary", price: 238.64,
    change: -1.12, momentum: 44, relativeStrength: 39, trendQuality: 46,
    volumeConfirmation: 32, volatility: 38, score10: 42, score30: 47,
    score90: 56, confidence: 48, signal: "Watch for repair",
    signalCopy: "Short-term momentum has weakened. A recovery in sector-relative strength is required before this returns to candidate status.",
    bars: [72, 75, 70, 78, 74, 69, 66, 71, 68, 63, 65, 59, 61, 57, 54, 58, 55, 51, 53, 48, 46, 44],
    metrics: { return_5d: -0.031, return_20d: -0.084, realized_volatility_20d: 0.281, volume_zscore_20d: -0.42, distance_ma20: -0.056, drawdown_60d: -0.118 },
  },
  {
    symbol: "XOM", name: "Exxon Mobil", sector: "Energy", price: 119.38,
    change: -0.88, momentum: 38, relativeStrength: 33, trendQuality: 41,
    volumeConfirmation: 28, volatility: 35, score10: 36, score30: 41,
    score90: 48, confidence: 47, signal: "Below candidate threshold",
    signalCopy: "Weak sector-relative momentum dominates an otherwise ordinary risk profile. The system assigns no current directional edge.",
    bars: [68, 66, 69, 65, 62, 64, 59, 61, 57, 55, 58, 53, 51, 54, 49, 52, 47, 45, 48, 43, 41, 39],
    metrics: { return_5d: -0.027, return_20d: -0.071, realized_volatility_20d: 0.263, volume_zscore_20d: -0.31, distance_ma20: -0.048, drawdown_60d: -0.096 },
  },
];

export const DEMO_LEDGER: LedgerRow[] = [
  ["demo-1", "2026-07-18T20:15:00.000Z", "NVDA", "30D", "Bullish", 68, "+2.1% to +7.4%", "Matures Aug 31", "Pending", "core-v0.1"],
  ["demo-2", "2026-07-18T20:15:00.000Z", "META", "30D", "Bullish", 64, "+1.2% to +5.8%", "Matures Aug 31", "Pending", "core-v0.1"],
  ["demo-3", "2026-06-26T20:15:00.000Z", "MSFT", "10D", "Bullish", 61, "+0.4% to +3.2%", "+2.6%", "Correct", "core-v0.1"],
  ["demo-4", "2026-06-18T20:15:00.000Z", "AMZN", "30D", "Neutral", 52, "-1.8% to +2.0%", "-3.1%", "Incorrect", "core-v0.1"],
  ["demo-5", "2026-05-29T20:15:00.000Z", "JPM", "30D", "Bullish", 59, "+0.8% to +4.0%", "+3.4%", "Correct", "core-v0.1"],
  ["demo-6", "2026-04-17T20:15:00.000Z", "XOM", "90D", "Bearish", 56, "-5.0% to +1.0%", "-2.7%", "Correct", "core-v0.1"],
].map(([predictionId, createdAt, symbol, horizon, direction, confidence, expectedRange, actualOutcome, outcome, formulaVersion]) => ({
  predictionId: String(predictionId),
  createdAt: String(createdAt),
  dataCutoff: ["demo-1", "demo-2"].includes(String(predictionId))
    ? DATA_CUTOFF
    : String(createdAt).replace("20:15:00.000Z", "20:00:00.000Z"),
  symbol: String(symbol),
  horizon: horizon as Horizon,
  direction: direction as LedgerRow["direction"],
  confidence: Number(confidence),
  expectedRange: String(expectedRange),
  actualOutcome: String(actualOutcome),
  outcome: outcome as PredictionOutcome,
  formulaVersion: String(formulaVersion),
  metricVersion: "price-core-v0.1",
  recordHash: `demo-${String(predictionId)}`,
  previousHash: null,
  source: "demo" as const,
}));

export function scoreFor(stock: Stock, horizon: Horizon): number {
  return horizon === "10D" ? stock.score10 : horizon === "30D" ? stock.score30 : stock.score90;
}

export function evaluateFormula(horizon: Horizon, weights: FormulaWeights) {
  const quality =
    weights.momentum * 20 +
    weights.relativeStrength * 25 +
    weights.trendQuality * 14 +
    weights.volumeConfirmation * 8 -
    Math.abs(weights.volatility) * 5;
  const directionAccuracy = Math.min(0.648, Math.max(0.491, 0.543 + quality / 2800));
  const spread = Math.min(0.059, 0.017 + quality / 4200);
  const informationCoefficient = Math.min(0.14, 0.027 + quality / 1500);
  const instability = Math.max(...Object.values(weights).map(Math.abs)) > 0.55;

  return {
    status: "complete",
    scope: "demo-walk-forward",
    holdoutStatus: "locked",
    horizon,
    metrics: {
      directionAccuracy,
      alwaysUpBaseline: 0.537,
      topBottomRelativeSpread: spread,
      spearmanIc: informationCoefficient,
      maxDrawdown: -0.081,
      turnover: 0.22,
    },
    decileRelativeReturns: [-0.018, -0.012, -0.008, -0.003, 0.001, 0.004, 0.008, 0.012, 0.017, 0.025],
    warnings: [
      "Illustrative demo data is not evidence of a tradeable edge.",
      "The final time holdout remains locked.",
      ...(instability ? ["A concentrated weight makes this candidate less stable."] : []),
    ],
  };
}

export function expectedRange(direction: LedgerRow["direction"]): string {
  return direction === "Bullish"
    ? "+0.8% to +5.0%"
    : direction === "Bearish"
      ? "-5.0% to +0.8%"
      : "-2.0% to +2.0%";
}
