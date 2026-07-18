from packages.prism_core.forecast import _percentile_rank


def test_realized_percentile_uses_midrank_for_ties() -> None:
    distribution = [0.01, 0.02, 0.02, 0.04]

    assert _percentile_rank(distribution, 0.0) == 0.0
    assert _percentile_rank(distribution, 0.02) == 50.0
    assert _percentile_rank(distribution, 0.05) == 100.0
