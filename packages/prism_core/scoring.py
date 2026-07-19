from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

from .metrics import CATALOG


SCORE_VERSION = "cross-sectional-alpha-risk-v0.2"
MINIMUM_CROSS_SECTION = 3


@dataclass(frozen=True)
class FactorTerm:
    metric: str
    direction: float
    label: str
    label_zh: str


@dataclass(frozen=True)
class FactorDefinition:
    key: str
    weight: float
    label: str
    label_zh: str
    description: str
    description_zh: str
    terms: tuple[FactorTerm, ...]


@dataclass(frozen=True)
class ScoreModel:
    id: str
    horizon: str
    role: str
    label: str
    label_zh: str
    description: str
    description_zh: str
    factors: tuple[FactorDefinition, ...]


def _term(
    metric: str,
    label: str,
    label_zh: str,
    *,
    direction: float = 1.0,
) -> FactorTerm:
    return FactorTerm(metric, direction, label, label_zh)


def _factor(
    key: str,
    weight: float,
    label: str,
    label_zh: str,
    description: str,
    description_zh: str,
    *terms: FactorTerm,
) -> FactorDefinition:
    return FactorDefinition(
        key=key,
        weight=weight,
        label=label,
        label_zh=label_zh,
        description=description,
        description_zh=description_zh,
        terms=tuple(terms),
    )


def _alpha_model(
    horizon: str,
    relative_metric: str,
    efficiency_metric: str,
    distance_metric: str,
) -> ScoreModel:
    return ScoreModel(
        id=f"alpha_{horizon.lower()}",
        horizon=horizon,
        role="alpha",
        label=f"{horizon} alpha baseline",
        label_zh=f"{horizon} Alpha 基線",
        description=(
            "Equal-weight, point-in-time cross-sectional baseline. Each factor is "
            "the mean of tie-aware metric ranks normalized to [-1, 1]."
        ),
        description_zh=(
            "等權、point-in-time 橫截面基線。每個 factor 先將同名次取平均排名，"
            "正規化至 [-1, 1]，再對 factor 等權平均。"
        ),
        factors=(
            _factor(
                "market_adjusted",
                0.50,
                "Market-adjusted momentum",
                "市場調整動能",
                (
                    "Return after removing beta-scaled SPY movement. Absolute return "
                    "is retained as context but is not double-counted in the score."
                ),
                (
                    "扣除 Beta 倍數之 SPY 同期報酬後的動能。絕對報酬保留作脈絡，"
                    "但不在分數中重複加權。"
                ),
                _term(relative_metric, "Beta-adjusted return", "Beta 調整報酬"),
            ),
            _factor(
                "trend_quality",
                0.50,
                "Trend quality",
                "趨勢品質",
                "Directional path efficiency and position within the recent range.",
                "方向路徑效率與近期價格區間位置。",
                _term(efficiency_metric, "Trend efficiency", "趨勢效率"),
                _term("range_position_60d", "Range position", "區間位置"),
                _term(distance_metric, "Distance from moving average", "距移動平均"),
            ),
        ),
    )


def _risk_model(
    horizon: str,
    volatility_metric: str,
    downside_metric: str,
) -> ScoreModel:
    return ScoreModel(
        id=f"risk_{horizon.lower()}",
        horizon=horizon,
        role="risk",
        label=f"{horizon} risk baseline",
        label_zh=f"{horizon} 風險基線",
        description=(
            "Equal-weight cross-sectional risk score. Higher values mean higher "
            "observed price risk, not lower expected return."
        ),
        description_zh=(
            "等權橫截面風險分數；數值越高代表觀察到的價格風險越高，"
            "不等同預期報酬較低。"
        ),
        factors=(
            _factor(
                "volatility_level",
                1.0 / 3.0,
                "Volatility level",
                "波動水準",
                (
                    "Realized and downside volatility share one bucket so their high "
                    "correlation does not create two independent weights."
                ),
                (
                    "已實現波動與下行半波動放在同一 bucket，避免兩個高度相關"
                    "指標各自取得一份權重。"
                ),
                _term(volatility_metric, "Realized volatility", "已實現波動"),
                _term(downside_metric, "Downside semivolatility", "下行半波動"),
            ),
            _factor(
                "drawdown_severity",
                1.0 / 3.0,
                "Drawdown severity",
                "回撤嚴重度",
                "Deeper trailing drawdowns receive higher risk ranks.",
                "近期回撤越深，風險排名越高。",
                _term(
                    "drawdown_60d",
                    "Inverted drawdown",
                    "反向回撤",
                    direction=-1.0,
                ),
            ),
            _factor(
                "volatility_expansion",
                1.0 / 3.0,
                "Volatility expansion",
                "波動擴張",
                "Recent volatility relative to the medium-term baseline.",
                "近期波動相對中期基準的擴張程度。",
                _term(
                    "volatility_ratio_20d_60d",
                    "20D / 60D volatility",
                    "20D／60D 波動",
                ),
            ),
        ),
    )


ALPHA_MODELS = (
    _alpha_model(
        "10D",
        "beta_adjusted_return_20d",
        "trend_efficiency_20d",
        "distance_ma20",
    ),
    _alpha_model(
        "30D",
        "beta_adjusted_return_20d",
        "trend_efficiency_20d",
        "distance_ma50",
    ),
    _alpha_model(
        "90D",
        "beta_adjusted_return_60d",
        "trend_efficiency_60d",
        "distance_ma50",
    ),
)

RISK_MODELS = (
    _risk_model(
        "10D",
        "realized_volatility_20d",
        "downside_semivolatility_20d",
    ),
    _risk_model(
        "30D",
        "realized_volatility_20d",
        "downside_semivolatility_20d",
    ),
    _risk_model(
        "90D",
        "realized_volatility_60d",
        "downside_semivolatility_60d",
    ),
)

SCORE_MODELS = ALPHA_MODELS + RISK_MODELS


def _midrank_percentiles(
    values_by_symbol: Mapping[str, float],
) -> dict[str, float]:
    """Return deterministic, tie-aware ranks on [0, 100]."""
    if len(values_by_symbol) < MINIMUM_CROSS_SECTION:
        return {}
    ordered = sorted(values_by_symbol.items(), key=lambda item: (item[1], item[0]))
    result: dict[str, float] = {}
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        average_rank = (index + end - 1) / 2.0
        percentile = 100.0 * average_rank / (len(ordered) - 1)
        for position in range(index, end):
            result[ordered[position][0]] = percentile
        index = end
    return result


def _required_metrics(models: Iterable[ScoreModel]) -> set[str]:
    return {
        term.metric
        for model in models
        for factor in model.factors
        for term in factor.terms
    }


def _validate_score_models() -> None:
    registered_metrics = {definition.name for definition in CATALOG}
    model_ids = [model.id for model in SCORE_MODELS]
    duplicate_model_ids = sorted(
        {model_id for model_id in model_ids if model_ids.count(model_id) > 1}
    )
    unknown_metrics = sorted(
        _required_metrics(SCORE_MODELS) - registered_metrics
    )
    invalid_models = [
        model.id
        for model in SCORE_MODELS
        if not model.factors
        or abs(sum(factor.weight for factor in model.factors) - 1.0) > 1e-12
        or any(
            not factor.terms
            or factor.weight <= 0
            or any(term.direction not in {-1.0, 1.0} for term in factor.terms)
            for factor in model.factors
        )
    ]
    if duplicate_model_ids or unknown_metrics or invalid_models:
        raise RuntimeError(
            "Invalid score-model registry: "
            f"duplicate_model_ids={duplicate_model_ids}, "
            f"unknown_metrics={unknown_metrics}, "
            f"invalid_models={invalid_models}"
        )


_validate_score_models()


def _score_model(
    model: ScoreModel,
    symbol: str,
    normalized_metric_ranks: Mapping[str, Mapping[str, float]],
) -> tuple[float | None, dict[str, float | None]]:
    factor_scores: dict[str, float | None] = {}
    for factor in model.factors:
        term_values: list[float] = []
        for term in factor.terms:
            value = normalized_metric_ranks.get(term.metric, {}).get(symbol)
            if value is None:
                term_values = []
                break
            term_values.append(term.direction * value)
        factor_scores[factor.key] = (
            sum(term_values) / len(term_values) if term_values else None
        )
    if any(value is None for value in factor_scores.values()):
        return None, factor_scores
    score = sum(
        factor.weight * float(factor_scores[factor.key])
        for factor in model.factors
    )
    return score, factor_scores


def _score_model_cross_section(
    model: ScoreModel,
    metrics_by_symbol: Mapping[str, Mapping[str, float | None]],
) -> tuple[
    dict[str, float | None],
    dict[str, dict[str, float | None]],
    dict[str, dict[str, float]],
]:
    required = _required_metrics((model,))
    eligible = [
        symbol
        for symbol, metrics in metrics_by_symbol.items()
        if all(metrics.get(metric) is not None for metric in required)
    ]
    normalized: dict[str, dict[str, float]] = {}
    percentiles: dict[str, dict[str, float]] = {}
    for metric in sorted(required):
        ranks = _midrank_percentiles(
            {
                symbol: float(metrics_by_symbol[symbol][metric])
                for symbol in eligible
                if metrics_by_symbol[symbol][metric] is not None
            }
        )
        percentiles[metric] = ranks
        normalized[metric] = {
            symbol: 2.0 * percentile / 100.0 - 1.0
            for symbol, percentile in ranks.items()
        }
    scores: dict[str, float | None] = {}
    factors: dict[str, dict[str, float | None]] = {}
    for symbol in metrics_by_symbol:
        score, factor_scores = _score_model(model, symbol, normalized)
        scores[symbol] = score
        factors[symbol] = factor_scores
    return scores, factors, percentiles


def score_cross_section(
    metrics_by_symbol: Mapping[str, Mapping[str, float | None]],
) -> dict[str, dict]:
    """
    Apply the exact same point-in-time scoring implementation for live scans and
    historical walk-forward evaluation.

    Missing inputs remain null. A model is not scored unless every factor is
    available, and no one-symbol/empty-universe 50-point fallback is created.
    """
    symbols = sorted(metrics_by_symbol)
    metric_percentiles: dict[str, dict[str, float]] = {}
    for metric in sorted(_required_metrics(SCORE_MODELS)):
        usable = {
            symbol: float(metrics_by_symbol[symbol][metric])
            for symbol in symbols
            if metrics_by_symbol[symbol].get(metric) is not None
        }
        ranks = _midrank_percentiles(usable)
        metric_percentiles[metric] = ranks

    results = {
        symbol: {
            "metric_percentiles": {
                metric: ranks[symbol]
                for metric, ranks in metric_percentiles.items()
                if symbol in ranks
            },
            "horizons": {},
        }
        for symbol in symbols
    }
    for horizon in ("10D", "30D", "90D"):
        alpha_model = next(model for model in ALPHA_MODELS if model.horizon == horizon)
        risk_model = next(model for model in RISK_MODELS if model.horizon == horizon)
        alpha_scores, alpha_factors, alpha_percentiles = (
            _score_model_cross_section(alpha_model, metrics_by_symbol)
        )
        risk_scores, risk_factors, risk_percentiles = (
            _score_model_cross_section(risk_model, metrics_by_symbol)
        )
        alpha_ranks = _midrank_percentiles(
            {
                symbol: float(score)
                for symbol, score in alpha_scores.items()
                if score is not None
            }
        )
        risk_ranks = _midrank_percentiles(
            {
                symbol: float(score)
                for symbol, score in risk_scores.items()
                if score is not None
            }
        )
        for symbol in symbols:
            results[symbol]["horizons"][horizon] = {
                "alpha_score": alpha_scores[symbol],
                "risk_score": risk_scores[symbol],
                "alpha_factors": alpha_factors[symbol],
                "risk_factors": risk_factors[symbol],
                "alpha_rank": alpha_ranks.get(symbol),
                "risk_rank": risk_ranks.get(symbol),
                "alpha_metric_percentiles": {
                    metric: ranks[symbol]
                    for metric, ranks in alpha_percentiles.items()
                    if symbol in ranks
                },
                "risk_metric_percentiles": {
                    metric: ranks[symbol]
                    for metric, ranks in risk_percentiles.items()
                    if symbol in ranks
                },
            }
    return results


def scoring_methodology() -> list[dict]:
    result: list[dict] = []
    for model in SCORE_MODELS:
        payload = asdict(model)
        payload.update(
            {
                "version": SCORE_VERSION,
                "normalization": (
                    "tie-aware cross-sectional midrank percentile, then "
                    "2 * percentile / 100 - 1"
                ),
                "minimum_cross_section": MINIMUM_CROSS_SECTION,
                "missing_policy": "null_if_any_factor_is_unavailable",
                "formula": "sum(factor.weight * mean(signed normalized term ranks))",
            }
        )
        result.append(payload)
    return result
