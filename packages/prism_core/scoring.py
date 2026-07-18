from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Mapping


SCANNER_SCORE_VERSION = "cross-sectional-score-v1.0"
BACKTEST_SCORE_VERSION = "walk-forward-feature-v1.0"


@dataclass(frozen=True)
class ScoreTerm:
    key: str
    metric: str
    weight: float
    label: str
    label_zh: str
    description: str
    description_zh: str
    transform: str = "identity"
    invert_percentile: bool = False


@dataclass(frozen=True)
class HorizonAdjustment:
    horizon: str
    metric: str | None
    amplitude: float
    scale: float
    label: str
    label_zh: str


SCANNER_SCORE_TERMS = (
    ScoreTerm(
        key="momentum",
        metric="return_20d",
        weight=0.30,
        label="20-session momentum percentile",
        label_zh="20 日動能百分位",
        description="Percentile rank of return_20d in the stored universe.",
        description_zh="return_20d 在目前已儲存股票池中的百分位排名。",
    ),
    ScoreTerm(
        key="relative_strength",
        metric="return_20d_minus_spy",
        weight=0.25,
        label="Relative-strength percentile",
        label_zh="相對強度百分位",
        description=(
            "Percentile rank of return_20d minus SPY return_20d. Subtracting the "
            "same benchmark preserves the cross-sectional rank."
        ),
        description_zh=(
            "return_20d 減去 SPY return_20d 後的百分位排名；所有股票減去同一"
            "基準不會改變橫截面排序。"
        ),
    ),
    ScoreTerm(
        key="trend_quality",
        metric="distance_ma20",
        weight=0.20,
        label="Trend-quality percentile",
        label_zh="趨勢品質百分位",
        description="Percentile rank of distance_ma20 in the stored universe.",
        description_zh="distance_ma20 在目前已儲存股票池中的百分位排名。",
    ),
    ScoreTerm(
        key="volume_confirmation",
        metric="volume_zscore_20d",
        weight=0.15,
        label="Volume-confirmation percentile",
        label_zh="成交量確認百分位",
        description="Percentile rank of volume_zscore_20d in the stored universe.",
        description_zh="volume_zscore_20d 在目前已儲存股票池中的百分位排名。",
    ),
    ScoreTerm(
        key="volatility_percentile",
        metric="realized_volatility_20d",
        weight=0.10,
        label="Inverse-volatility percentile",
        label_zh="反向波動百分位",
        description=(
            "100 minus the percentile rank of realized_volatility_20d, so lower "
            "volatility receives a higher component value."
        ),
        description_zh=(
            "100 減去 realized_volatility_20d 的百分位，因此較低波動會得到"
            "較高的分項值。"
        ),
        invert_percentile=True,
    ),
)

SCANNER_HORIZON_ADJUSTMENTS = (
    HorizonAdjustment(
        horizon="10D",
        metric="return_5d",
        amplitude=4.0,
        scale=10.0,
        label="Short-horizon momentum adjustment",
        label_zh="短期動能調整",
    ),
    HorizonAdjustment(
        horizon="30D",
        metric=None,
        amplitude=0.0,
        scale=0.0,
        label="No horizon adjustment",
        label_zh="不做期間調整",
    ),
    HorizonAdjustment(
        horizon="90D",
        metric="drawdown_60d",
        amplitude=4.0,
        scale=3.0,
        label="Drawdown adjustment",
        label_zh="回撤調整",
    ),
)

BACKTEST_SCORE_TERMS = (
    ScoreTerm(
        key="return_20d",
        metric="return_20d",
        weight=0.30,
        label="20-session return",
        label_zh="20 日報酬",
        description="Raw 20-session close-to-close return at the evaluation point.",
        description_zh="評估時點的原始 20 日收盤價報酬。",
    ),
    ScoreTerm(
        key="return_60d",
        metric="return_60d",
        weight=0.25,
        label="60-session return",
        label_zh="60 日報酬",
        description="Raw 60-session close-to-close return at the evaluation point.",
        description_zh="評估時點的原始 60 日收盤價報酬。",
    ),
    ScoreTerm(
        key="distance_ma20",
        metric="distance_ma20",
        weight=0.20,
        label="Distance from MA20",
        label_zh="距 20 日均線",
        description="Latest close divided by the trailing 20-session mean minus one.",
        description_zh="最新收盤價除以過去 20 日均價再減一。",
    ),
    ScoreTerm(
        key="volume_zscore_20d",
        metric="volume_zscore_20d",
        weight=0.05,
        label="Clipped volume z-score",
        label_zh="截斷成交量 z-score",
        description="The 20-session volume z-score clipped to the interval [-3, 3].",
        description_zh="將 20 日成交量 z-score 截斷在 [-3, 3] 區間。",
        transform="clip(-3, 3)",
    ),
    ScoreTerm(
        key="realized_volatility_20d",
        metric="realized_volatility_20d",
        weight=-0.10,
        label="Realized-volatility penalty",
        label_zh="已實現波動懲罰",
        description="Annualized 20-session realized volatility, applied negatively.",
        description_zh="20 日年化已實現波動，以負權重計入。",
    ),
)


def _apply_transform(value: float, transform: str) -> float:
    if transform == "clip(-3, 3)":
        return max(-3.0, min(3.0, value))
    if transform == "identity":
        return value
    raise ValueError(f"Unknown score transform: {transform}")


def compute_scanner_scores(
    component_percentiles: Mapping[str, float],
    metrics: Mapping[str, float],
) -> dict[str, float]:
    base_score = sum(
        term.weight
        * (
            100.0 - float(component_percentiles[term.key])
            if term.invert_percentile
            else float(component_percentiles[term.key])
        )
        for term in SCANNER_SCORE_TERMS
    )
    scores: dict[str, float] = {}
    for adjustment in SCANNER_HORIZON_ADJUSTMENTS:
        horizon_adjustment = (
            adjustment.amplitude
            * math.tanh(adjustment.scale * float(metrics[adjustment.metric]))
            if adjustment.metric
            else 0.0
        )
        scores[adjustment.horizon] = round(
            max(0.0, min(100.0, base_score + horizon_adjustment)),
            1,
        )
    return scores


def compute_backtest_feature_score(features: Mapping[str, float]) -> float:
    return sum(
        term.weight
        * _apply_transform(float(features[term.key]), term.transform)
        for term in BACKTEST_SCORE_TERMS
    )


def _weighted_formula(terms: tuple[ScoreTerm, ...]) -> str:
    parts: list[str] = []
    for index, term in enumerate(terms):
        transformed = term.key
        if term.transform == "clip(-3, 3)":
            transformed = f"clip({term.key}, -3, 3)"
        if term.invert_percentile:
            transformed = f"(100 - {term.key})"
        magnitude = abs(term.weight)
        if index == 0:
            prefix = "-" if term.weight < 0 else ""
        else:
            prefix = "- " if term.weight < 0 else "+ "
        parts.append(f"{prefix}{magnitude:.2f} × {transformed}")
    return " ".join(parts)


def scoring_methodology() -> list[dict]:
    scanner_terms = [asdict(term) for term in SCANNER_SCORE_TERMS]
    horizons = []
    for adjustment in SCANNER_HORIZON_ADJUSTMENTS:
        payload = asdict(adjustment)
        payload["formula"] = (
            f"{adjustment.amplitude:g} × tanh("
            f"{adjustment.scale:g} × {adjustment.metric})"
            if adjustment.metric
            else "0"
        )
        horizons.append(payload)
    return [
        {
            "id": "scanner_relative_score",
            "version": SCANNER_SCORE_VERSION,
            "label": "Scanner relative score",
            "label_zh": "市場掃描相對分數",
            "description": (
                "A 0–100 cross-sectional score computed only from the currently "
                "stored universe at one data cutoff."
            ),
            "description_zh": (
                "只使用同一資料 cutoff 下目前已儲存股票池計算的 0–100 "
                "橫截面分數。"
            ),
            "formula": (
                "clip(weighted base score + horizon adjustment, 0, 100)"
            ),
            "base_formula": _weighted_formula(SCANNER_SCORE_TERMS),
            "terms": scanner_terms,
            "horizons": horizons,
        },
        {
            "id": "walk_forward_feature_score",
            "version": BACKTEST_SCORE_VERSION,
            "label": "Walk-forward feature score",
            "label_zh": "Walk-forward 特徵分數",
            "description": (
                "Raw feature score evaluated at each historical rebalance point. "
                "It is not the scanner's 0–100 percentile score."
            ),
            "description_zh": (
                "在每個歷史再平衡時點計算的原始特徵分數；它不是掃描器的 "
                "0–100 百分位分數。"
            ),
            "formula": _weighted_formula(BACKTEST_SCORE_TERMS),
            "terms": [asdict(term) for term in BACKTEST_SCORE_TERMS],
            "horizons": [],
        },
    ]
