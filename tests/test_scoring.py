from __future__ import annotations

from dataclasses import asdict

import pytest

from packages.prism_core.metrics import CATALOG
from packages.prism_core.scoring import (
    MINIMUM_CROSS_SECTION,
    SCORE_MODELS,
    SCORE_VERSION,
    score_cross_section,
    scoring_methodology,
)


def metric_row(alpha: float, risk: float) -> dict[str, float | None]:
    return {
        "beta_adjusted_return_20d": alpha,
        "beta_adjusted_return_60d": alpha,
        "trend_efficiency_20d": alpha,
        "trend_efficiency_60d": alpha,
        "range_position_60d": alpha,
        "distance_ma20": alpha,
        "distance_ma50": alpha,
        "realized_volatility_20d": risk,
        "realized_volatility_60d": risk,
        "downside_semivolatility_20d": risk,
        "downside_semivolatility_60d": risk,
        "drawdown_60d": -risk,
        "volatility_ratio_20d_60d": risk,
    }


def tied_cross_section() -> dict[str, dict[str, float | None]]:
    return {
        "A": metric_row(0.0, 0.0),
        "B": metric_row(1.0, 1.0),
        "C": metric_row(1.0, 1.0),
        "D": metric_row(2.0, 2.0),
    }


def test_score_models_only_reference_registered_metrics_and_normalized_weights() -> None:
    catalog_names = {definition.name for definition in CATALOG}
    assert {model.horizon for model in SCORE_MODELS} == {"10D", "30D", "90D"}
    assert {model.role for model in SCORE_MODELS} == {"alpha", "risk"}
    assert len({model.id for model in SCORE_MODELS}) == len(SCORE_MODELS)
    for model in SCORE_MODELS:
        assert sum(factor.weight for factor in model.factors) == pytest.approx(1.0)
        assert all(factor.terms for factor in model.factors)
        assert {
            term.metric
            for factor in model.factors
            for term in factor.terms
        } <= catalog_names


def test_tie_aware_cross_sectional_ranks_and_scores() -> None:
    scores = score_cross_section(tied_cross_section())

    for horizon in ("10D", "30D", "90D"):
        assert scores["A"]["horizons"][horizon]["alpha_score"] == pytest.approx(-1.0)
        assert scores["A"]["horizons"][horizon]["alpha_rank"] == pytest.approx(0.0)
        assert scores["B"]["horizons"][horizon]["alpha_score"] == pytest.approx(0.0)
        assert scores["B"]["horizons"][horizon]["alpha_rank"] == pytest.approx(50.0)
        assert scores["C"]["horizons"][horizon]["alpha_score"] == pytest.approx(0.0)
        assert scores["C"]["horizons"][horizon]["alpha_rank"] == pytest.approx(50.0)
        assert scores["D"]["horizons"][horizon]["alpha_score"] == pytest.approx(1.0)
        assert scores["D"]["horizons"][horizon]["alpha_rank"] == pytest.approx(100.0)

        assert scores["A"]["horizons"][horizon]["risk_score"] == pytest.approx(-1.0)
        assert scores["A"]["horizons"][horizon]["risk_rank"] == pytest.approx(0.0)
        assert scores["B"]["horizons"][horizon]["risk_score"] == pytest.approx(0.0)
        assert scores["B"]["horizons"][horizon]["risk_rank"] == pytest.approx(50.0)
        assert scores["C"]["horizons"][horizon]["risk_score"] == pytest.approx(0.0)
        assert scores["C"]["horizons"][horizon]["risk_rank"] == pytest.approx(50.0)
        assert scores["D"]["horizons"][horizon]["risk_score"] == pytest.approx(1.0)
        assert scores["D"]["horizons"][horizon]["risk_rank"] == pytest.approx(100.0)


def test_fewer_than_three_eligible_symbols_never_creates_a_neutral_default() -> None:
    scores = score_cross_section(
        {
            "A": metric_row(0.0, 0.0),
            "B": metric_row(1.0, 1.0),
        }
    )
    assert MINIMUM_CROSS_SECTION == 3
    for symbol in ("A", "B"):
        for horizon in ("10D", "30D", "90D"):
            row = scores[symbol]["horizons"][horizon]
            assert row["alpha_score"] is None
            assert row["risk_score"] is None
            assert row["alpha_rank"] is None
            assert row["risk_rank"] is None
            assert all(value is None for value in row["alpha_factors"].values())
            assert all(value is None for value in row["risk_factors"].values())


def test_missing_alpha_input_does_not_fabricate_alpha_or_erase_risk() -> None:
    rows = {
        "A": metric_row(0.0, 0.0),
        "B": metric_row(1.0, 1.0),
        "C": metric_row(2.0, 2.0),
    }
    rows["C"]["beta_adjusted_return_20d"] = None
    scores = score_cross_section(rows)

    for symbol in rows:
        for horizon in ("10D", "30D"):
            assert scores[symbol]["horizons"][horizon]["alpha_score"] is None
            assert scores[symbol]["horizons"][horizon]["alpha_rank"] is None
            assert scores[symbol]["horizons"][horizon]["risk_score"] is not None
            assert scores[symbol]["horizons"][horizon]["risk_rank"] is not None

    assert scores["C"]["horizons"]["90D"]["alpha_score"] is not None


def test_alpha_and_risk_are_reported_as_independent_dimensions() -> None:
    scores = score_cross_section(
        {
            "HIGH_ALPHA_LOW_RISK": metric_row(2.0, 0.0),
            "MIDDLE": metric_row(1.0, 1.0),
            "LOW_ALPHA_HIGH_RISK": metric_row(0.0, 2.0),
        }
    )
    row = scores["HIGH_ALPHA_LOW_RISK"]["horizons"]["30D"]
    assert row["alpha_rank"] == pytest.approx(100.0)
    assert row["risk_rank"] == pytest.approx(0.0)
    assert row["alpha_score"] == pytest.approx(1.0)
    assert row["risk_score"] == pytest.approx(-1.0)


def test_methodology_is_the_exact_model_executed_by_scoring() -> None:
    methodologies = {item["id"]: item for item in scoring_methodology()}
    assert set(methodologies) == {model.id for model in SCORE_MODELS}
    scores = score_cross_section(tied_cross_section())

    for model in SCORE_MODELS:
        methodology = methodologies[model.id]
        serialized = asdict(model)
        for key, value in serialized.items():
            assert methodology[key] == value
        assert methodology["version"] == SCORE_VERSION
        assert methodology["minimum_cross_section"] == MINIMUM_CROSS_SECTION
        assert methodology["missing_policy"] == (
            "null_if_any_factor_is_unavailable"
        )

        executed = scores["D"]["horizons"][model.horizon]
        metric_percentiles = executed[f"{model.role}_metric_percentiles"]
        expected_factors: dict[str, float] = {}
        for factor in methodology["factors"]:
            term_values = [
                term["direction"]
                * (2.0 * metric_percentiles[term["metric"]] / 100.0 - 1.0)
                for term in factor["terms"]
            ]
            expected_factors[factor["key"]] = sum(term_values) / len(term_values)
        expected_score = sum(
            factor["weight"] * expected_factors[factor["key"]]
            for factor in methodology["factors"]
        )
        assert executed[f"{model.role}_factors"] == pytest.approx(expected_factors)
        assert executed[f"{model.role}_score"] == pytest.approx(expected_score)
