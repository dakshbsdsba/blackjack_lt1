"""Analytics tests."""

from __future__ import annotations

import pytest

from blackjack import Analytics, run_simulation
from blackjack.analytics import (
    bankroll_series,
    bucket_by_true_count,
    drawdown_series,
    outcome_counts,
)


def test_bankroll_series() -> None:
    """The curve starts at the opening bankroll and adds each net."""
    assert bankroll_series([10, -5, 0], 100) == [100, 110, 105, 105]


def test_drawdown_series() -> None:
    """Drawdown measures the distance below the running peak."""
    curve = drawdown_series([10, -30, 5, -10], 100)
    assert curve == [0, 0, 30, 25, 35]


def test_analytics_from_arrays() -> None:
    """Headline metrics are derived correctly from raw results."""
    stats = Analytics.from_arrays(
        [10, -5, 0, 20, -10],
        ["win", "loss", "push", "blackjack", "loss"],
        [10, 10, 10, 10, 10],
        starting_bankroll=100,
        decisions_correct=3,
        decisions_total=4,
    )
    assert stats.hands == 5
    assert stats.net == 15
    assert stats.wagered == 50
    assert stats.house_edge == pytest.approx(-0.3)
    assert stats.house_edge_percent == pytest.approx(-30.0)
    assert stats.wins == 2
    assert stats.losses == 2
    assert stats.pushes == 1
    assert stats.blackjacks == 1
    assert stats.win_rate == pytest.approx(0.4)
    assert stats.decisive_win_rate == pytest.approx(0.5)
    assert stats.max_drawdown == 10
    assert stats.peak_bankroll == 125
    assert stats.final_bankroll == 115
    assert stats.adherence == pytest.approx(0.75)
    assert stats.roi == pytest.approx(0.15)


def test_streaks_with_pushes_breaking_runs() -> None:
    """Pushes end both a win and a loss streak."""
    stats = Analytics.from_arrays(
        [1, 1, -1, -1, -1, 0, 1],
        ["win", "win", "loss", "loss", "loss", "push", "win"],
        [1, 1, 1, 1, 1, 1, 1],
        starting_bankroll=0,
    )
    assert stats.longest_win_streak == 2
    assert stats.longest_loss_streak == 3


def test_outcome_counts_include_empty_categories() -> None:
    """Every outcome category appears even when it never happened."""
    counts = outcome_counts(["win", "win", "push"])
    assert counts["win"] == 2
    assert counts["push"] == 1
    assert counts["loss"] == 0
    assert counts["blackjack"] == 0
    assert counts["surrender"] == 0


def test_bucket_by_true_count() -> None:
    """Hands are grouped into rounded true-count bands."""
    buckets = bucket_by_true_count(
        [-2.4, 0.2, 2.1, 2.4, 4.0],
        [-10, 0, 10, 10, 20],
        [10, 10, 10, 10, 10],
        ["loss", "push", "win", "win", "win"],
        low=-2,
        high=4,
    )
    by_label = {bucket.label: bucket for bucket in buckets}
    assert by_label["-2"].hands == 1
    assert by_label["0"].hands == 1
    assert by_label["+2"].hands == 2
    assert by_label["+2"].net == 20
    assert by_label["+2"].edge == pytest.approx(-1.0)
    assert by_label["+4+"].hands == 1
    assert by_label["+4+"].edge == pytest.approx(-2.0)


def test_combine_sessions() -> None:
    """Combining two sessions adds their money and decisions."""
    first = Analytics.from_arrays(
        [10, -5],
        ["win", "loss"],
        [10, 10],
        starting_bankroll=100,
        decisions_correct=1,
        decisions_total=2,
    )
    second = Analytics.from_arrays(
        [-5],
        ["loss"],
        [10],
        starting_bankroll=50,
        decisions_correct=2,
        decisions_total=2,
    )
    merged = Analytics.combine([first, second])
    assert merged.hands == 3
    assert merged.net == 0
    assert merged.strategy_decisions == 4
    assert merged.strategy_correct == 3


def test_simulation_analytics_matches_result_arrays() -> None:
    """SimResult.analytics agrees with the raw arrays it holds."""
    result = run_simulation(200, bet=5, starting_bankroll=1000, seed=41)
    stats = result.analytics()
    assert stats.hands == len(result.nets)
    assert stats.wagered == pytest.approx(float(result.bets.sum()))
    assert stats.net == pytest.approx(float(result.nets.sum()))
    assert stats.final_bankroll == pytest.approx(1000 + float(result.nets.sum()))
