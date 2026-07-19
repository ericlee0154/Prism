from __future__ import annotations

import math
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

import packages.prism_core.backtest as backtest_module
from packages.prism_core.backtest import (
    LABEL_VERSION,
    UNIVERSE_VERSION,
    _future_close_max_drawdown,
    _spearman,
    walk_forward_backtest,
)
from packages.prism_core.models import Bar


START = datetime(2025, 1, 2, 21, 0, tzinfo=UTC)


def make_history(
    symbol: str,
    *,
    count: int = 75,
    default_open: float,
    default_close: float,
    entry_open: float | None = None,
    target_close: float | None = None,
) -> list[Bar]:
    result: list[Bar] = []
    for index in range(count):
        open_price = entry_open if index == 61 and entry_open is not None else default_open
        close = target_close if index == 70 and target_close is not None else default_close
        timestamp = START + timedelta(days=index)
        result.append(
            Bar(
                symbol=symbol,
                timestamp=timestamp,
                available_at=timestamp,
                open=open_price,
                high=max(open_price, close) * 1.01,
                low=min(open_price, close) * 0.99,
                close=close,
                volume=1_000_000 + index,
                source="test",
            )
        )
    return result


def test_spearman_uses_midranks_for_ties() -> None:
    assert _spearman([1.0, 1.0, 0.0], [2.0, 1.0, 0.0]) == pytest.approx(
        math.sqrt(3) / 2
    )
    assert _spearman([1.0, 1.0, 1.0], [2.0, 1.0, 0.0]) is None


def test_future_drawdown_uses_running_close_peak() -> None:
    bars = make_history(
        "PATH",
        count=4,
        default_open=100.0,
        default_close=100.0,
    )
    closes = [110.0, 130.0, 117.0, 125.0]
    bars = [
        Bar(
            **{
                **bar.__dict__,
                "close": closes[index],
            }
        )
        for index, bar in enumerate(bars)
    ]
    assert _future_close_max_drawdown(100.0, bars) == pytest.approx(-0.10)


def test_walk_forward_uses_common_calendar_next_open_spy_excess_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    histories = {
        "SPY": make_history(
            "SPY",
            default_open=100.0,
            default_close=100.0,
            entry_open=80.0,
            target_close=100.0,
        ),
        "A": make_history(
            "A",
            default_open=50.0,
            default_close=50.0,
            entry_open=50.0,
            target_close=100.0,
        ),
        "B": make_history(
            "B",
            default_open=100.0,
            default_close=100.0,
            entry_open=100.0,
            target_close=110.0,
        ),
        "C": make_history(
            "C",
            default_open=200.0,
            default_close=200.0,
            entry_open=200.0,
            target_close=100.0,
        ),
        "D": make_history(
            "D",
            default_open=100.0,
            default_close=100.0,
            entry_open=100.0,
            target_close=125.0,
        ),
        "E": make_history(
            "E",
            default_open=120.0,
            default_close=120.0,
            entry_open=120.0,
            target_close=126.0,
        ),
    }
    # A missing intermediate forward session must not shift the target to the
    # candidate's tenth local row; labels are anchored to the SPY calendar.
    histories["B"] = [
        bar
        for index, bar in enumerate(histories["B"])
        if index != 65
    ]
    histories["E"][60] = replace(
        histories["E"][60],
        available_at=histories["E"][61].timestamp + timedelta(hours=1),
    )

    def fake_metrics(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(values={})

    alpha = {"A": 1.0, "B": 0.5, "C": -1.0, "D": 0.0, "E": 0.25}

    def fake_scores(metrics_by_symbol: dict[str, dict]) -> dict[str, dict]:
        return {
            symbol: {
                "horizons": {
                    "10D": {
                        "alpha_score": alpha[symbol],
                        "risk_score": None,
                        "alpha_factors": {"synthetic": alpha[symbol]},
                    }
                }
            }
            for symbol in metrics_by_symbol
        }

    captured: dict[str, list] = {}

    def capture_ablation(per_date: dict[str, list]) -> list[dict]:
        captured.update(per_date)
        return []

    monkeypatch.setattr(backtest_module, "compute_price_metrics", fake_metrics)
    monkeypatch.setattr(backtest_module, "score_cross_section", fake_scores)
    monkeypatch.setattr(backtest_module, "_factor_ablation", capture_ablation)

    result = walk_forward_backtest(
        histories,
        horizon_sessions=10,
        rebalance_every=5,
    )

    assert result["status"] == "complete"
    assert result["label_version"] == LABEL_VERSION
    assert "next-open" in LABEL_VERSION
    assert result["evaluation_dates"] == 1
    assert result["observation_count"] == 3
    assert result["mean_spearman_ic"] == pytest.approx(1.0)
    assert result["mean_top_bottom_spread"] == pytest.approx(1.5)
    assert result["direction_accuracy"] == pytest.approx(1.0)
    assert result["direction_baseline"] == pytest.approx(2 / 3)
    assert result["direction_accuracy_delta"] == pytest.approx(1 / 3)

    observations = next(iter(captured.values()))
    by_symbol = {observation.symbol: observation for observation in observations}
    assert "B" not in by_symbol
    assert "E" not in by_symbol
    assert by_symbol["A"].diagnostic_return == pytest.approx(1.0)
    assert by_symbol["A"].executable_return == pytest.approx(1.0)
    assert by_symbol["A"].benchmark_executable_return == pytest.approx(0.25)
    assert by_symbol["A"].excess_return == pytest.approx(0.75)
    assert by_symbol["D"].executable_return == pytest.approx(0.25)
    assert by_symbol["D"].benchmark_executable_return == pytest.approx(0.25)
    assert by_symbol["D"].excess_return == pytest.approx(0.0)
    assert by_symbol["C"].executable_return == pytest.approx(-0.50)
    assert by_symbol["C"].excess_return == pytest.approx(-0.75)

    universe = result["universe"]
    assert universe["definition_version"] == UNIVERSE_VERSION
    assert universe["benchmark_symbols"] == ["SPY"]
    assert universe["requested_symbols"] == ["A", "B", "C", "D", "E"]
    assert universe["requested_count"] == 5
    assert len(universe["symbol_list_hash"]) == 64
    assert universe["eligible_evaluation_dates"] == 1
    assert universe["coverage_ratio"] == pytest.approx(1.0)
    assert universe["eligible_count_min"] == 3
    assert universe["eligible_count_median"] == 3
    assert universe["eligible_count_max"] == 3
    assert universe["excluded_reason_counts"]["incomplete_forward_path"] == 1
    assert universe["excluded_reason_counts"]["signal_late_for_next_session"] == 1


def test_walk_forward_insufficient_universe_keeps_auditable_snapshot() -> None:
    histories = {
        "SPY": make_history(
            "SPY",
            default_open=100.0,
            default_close=100.0,
        ),
        "ONLY_ONE": make_history(
            "ONLY_ONE",
            default_open=50.0,
            default_close=50.0,
        ),
    }
    result = walk_forward_backtest(histories, horizon_sessions=10)

    assert result["status"] == "insufficient_data"
    assert result["observation_count"] == 0
    assert result["universe"]["definition_version"] == UNIVERSE_VERSION
    assert result["universe"]["requested_symbols"] == ["ONLY_ONE"]
    assert result["universe"]["requested_count"] == 1
    assert result["universe"]["symbol_list_hash"]
    assert result["factor_ablation"] == []
