import math

import pytest

from packages.prism_core.metrics import CATALOG, METRIC_CALCULATORS
from packages.prism_core.scoring import (
    BACKTEST_SCORE_TERMS,
    SCANNER_HORIZON_ADJUSTMENTS,
    SCANNER_SCORE_TERMS,
    compute_backtest_feature_score,
    compute_scanner_scores,
    scoring_methodology,
)


def test_every_catalog_metric_uses_a_registered_calculator() -> None:
    assert {item.name for item in CATALOG} == set(METRIC_CALCULATORS)


def test_scanner_methodology_serializes_the_terms_used_by_calculation() -> None:
    components = {
        "momentum": 72.0,
        "relative_strength": 64.0,
        "trend_quality": 58.0,
        "volume_confirmation": 55.0,
        "volatility_percentile": 80.0,
    }
    metrics = {"return_5d": 0.03, "drawdown_60d": -0.08}
    scores = compute_scanner_scores(components, metrics)
    methodology = scoring_methodology()[0]

    assert methodology["terms"] == [
        {
            "key": term.key,
            "metric": term.metric,
            "weight": term.weight,
            "label": term.label,
            "label_zh": term.label_zh,
            "description": term.description,
            "description_zh": term.description_zh,
            "transform": term.transform,
            "invert_percentile": term.invert_percentile,
        }
        for term in SCANNER_SCORE_TERMS
    ]
    base = sum(
        term.weight
        * (
            100 - components[term.key]
            if term.invert_percentile
            else components[term.key]
        )
        for term in SCANNER_SCORE_TERMS
    )
    for adjustment in SCANNER_HORIZON_ADJUSTMENTS:
        delta = (
            adjustment.amplitude
            * math.tanh(adjustment.scale * metrics[adjustment.metric])
            if adjustment.metric
            else 0.0
        )
        assert scores[adjustment.horizon] == round(
            max(0.0, min(100.0, base + delta)),
            1,
        )


def test_backtest_methodology_weights_are_the_executed_weights() -> None:
    features = {
        "return_20d": 0.1,
        "return_60d": 0.2,
        "distance_ma20": 0.03,
        "volume_zscore_20d": 9.0,
        "realized_volatility_20d": 0.4,
    }
    expected = sum(
        term.weight
        * (
            max(-3.0, min(3.0, features[term.key]))
            if term.transform == "clip(-3, 3)"
            else features[term.key]
        )
        for term in BACKTEST_SCORE_TERMS
    )
    assert compute_backtest_feature_score(features) == pytest.approx(expected)
    assert scoring_methodology()[1]["terms"] == [
        {
            "key": term.key,
            "metric": term.metric,
            "weight": term.weight,
            "label": term.label,
            "label_zh": term.label_zh,
            "description": term.description,
            "description_zh": term.description_zh,
            "transform": term.transform,
            "invert_percentile": term.invert_percentile,
        }
        for term in BACKTEST_SCORE_TERMS
    ]
