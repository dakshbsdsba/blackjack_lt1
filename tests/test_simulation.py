"""Simulation engine and bot tests (Tier 3)."""

from __future__ import annotations

import numpy as np
import pytest

from blackjack import (
    BasicStrategyBot,
    BetContext,
    FlatBetBot,
    HiLoSpreadBot,
    KellyBot,
    MartingaleBot,
    Rules,
    run_bot,
    run_competition,
    run_simulation,
)

RULES = Rules()


def context(bankroll: float = 1000.0, true_count: float = 0.0) -> BetContext:
    """Build a betting context for unit tests."""
    return BetContext(
        bankroll=bankroll,
        true_count=true_count,
        running_count=int(round(true_count * 2)),
        hands_played=0,
        last_net=0.0,
        rules=RULES,
    )


def test_run_simulation_shapes() -> None:
    """The result arrays line up hand for hand."""
    result = run_simulation(500, bet=5, starting_bankroll=1000, seed=51)
    assert result.rounds == 500
    assert result.hands >= 500
    assert len(result.nets) == len(result.bets) == len(result.outcomes)
    assert (
        len(result.true_counts)
        == len(result.dealer_upcards)
        == len(result.start_totals)
    )
    assert len(result.bankroll) == result.hands + 1
    assert result.bankroll[0] == pytest.approx(1000.0)
    assert result.bankroll[-1] == pytest.approx(1000.0 + result.nets.sum())
    assert min(result.bets) == 5.0
    assert all(bet % 5 == 0 for bet in result.bets)


def test_run_simulation_is_reproducible() -> None:
    """The same seed produces the same cards and the same result."""
    first = run_simulation(200, bet=5, starting_bankroll=1000, seed=52)
    second = run_simulation(200, bet=5, starting_bankroll=1000, seed=52)
    assert np.array_equal(first.nets, second.nets)
    assert first.outcomes == second.outcomes


def test_run_bot_logs_decisions() -> None:
    """Decision logging records every action and scores adherence."""
    result = run_bot(
        BasicStrategyBot(unit=10),
        200,
        starting_bankroll=1000,
        seed=53,
        track_decisions=True,
    )
    assert result.decisions
    assert result.analytics().adherence == pytest.approx(1.0)


def test_run_bot_can_skip_decision_logging() -> None:
    """Turning logging off produces no decision objects."""
    result = run_bot(
        BasicStrategyBot(unit=10),
        100,
        starting_bankroll=1000,
        seed=54,
        track_decisions=False,
    )
    assert result.decisions == []
    assert result.analytics().strategy_decisions == 0


def test_run_bot_respects_bankroll() -> None:
    """A bot never wagers more than it has and never goes negative."""
    result = run_bot(
        FlatBetBot(unit=100),
        100,
        starting_bankroll=50,
        seed=55,
        track_decisions=False,
    )
    assert all(bet <= 50 for bet in result.bets)
    assert result.bankroll[-1] >= 0


def test_run_competition_ranks_bots() -> None:
    """The leaderboard is sorted by final bankroll with contiguous ranks."""
    bots = [
        BasicStrategyBot(name="basic", unit=10),
        MartingaleBot(name="martingale", unit=10),
        HiLoSpreadBot(name="count", unit=10, spread=6),
    ]
    entries, results = run_competition(bots, 400, starting_bankroll=1000, seed=56)
    assert len(entries) == 3
    assert [entry.rank for entry in entries] == [1, 2, 3]
    assert (
        entries[0].final_bankroll
        >= entries[1].final_bankroll
        >= entries[2].final_bankroll
    )
    assert set(results) == {"basic", "martingale", "count"}
    for entry in entries:
        assert entry.hands > 0
        assert entry.wins + entry.losses + entry.pushes <= entry.hands


def test_martingale_progression() -> None:
    """The Martingale doubles after losses, caps, and resets on a win."""
    bot = MartingaleBot(unit=10, max_multiplier=8)
    ctx = context(bankroll=10_000)
    assert bot.bet(ctx) == 10
    bot.on_result(-10)
    assert bot.bet(ctx) == 20
    bot.on_result(-20)
    assert bot.bet(ctx) == 40
    bot.on_result(-40)
    assert bot.bet(ctx) == 80
    bot.on_result(-80)
    assert bot.bet(ctx) == 80
    bot.on_result(80)
    assert bot.bet(ctx) == 10


def test_martingale_resets_after_push() -> None:
    """A push also clears the progression."""
    bot = MartingaleBot(unit=10)
    bot.on_result(-10)
    assert bot.bet(context()) == 20
    bot.on_result(0)
    assert bot.bet(context()) == 10


def test_hilo_spread_scales_with_true_count() -> None:
    """The spread stays at one unit until the count justifies more."""
    bot = HiLoSpreadBot(unit=10, spread=8, min_true_count=1)
    assert bot.bet(context(true_count=0.4)) == 10
    assert bot.bet(context(true_count=1.0)) == 10
    assert bot.bet(context(true_count=2.0)) == 20
    assert bot.bet(context(true_count=5.0)) == 50
    assert bot.bet(context(true_count=9.0)) == 80


def test_hilo_takes_insurance_at_high_counts() -> None:
    """Insurance is taken only when the count is high enough."""
    bot = HiLoSpreadBot(unit=10, insurance_true_count=3.0)
    assert not bot.wants_insurance(2.0)
    assert bot.wants_insurance(3.0)
    assert bot.wants_insurance(5.0)


def test_kelly_bet_is_fractional_and_capped() -> None:
    """Kelly scales with bankroll and is capped by the table and risk limit."""
    bot = KellyBot(unit=1, fraction=0.5, max_fraction=0.05)
    low = bot.bet(context(bankroll=1000, true_count=0.0))
    mid = bot.bet(context(bankroll=1000, true_count=5.0))
    high = bot.bet(context(bankroll=1000, true_count=20.0))
    assert low == 1
    assert 1 < mid < high
    assert high <= 50


def test_bets_are_clamped_to_the_table_limits() -> None:
    """A huge unit is capped by the maximum bet and the bankroll."""
    bot = FlatBetBot(unit=100_000)
    assert bot.bet(context(bankroll=1000)) == min(1000, RULES.max_bet)
    assert bot.bet(context(bankroll=0)) == 0


@pytest.fixture(scope="module")
def counting_results():
    """A paired flat-bet and counting run on the same shoe seed."""
    flat = run_bot(
        BasicStrategyBot(name="flat", unit=10),
        40_000,
        starting_bankroll=100_000,
        seed=7,
        track_decisions=False,
    )
    counting = run_bot(
        HiLoSpreadBot(name="count", unit=10, spread=8),
        40_000,
        starting_bankroll=100_000,
        seed=7,
        track_decisions=False,
    )
    return flat, counting


@pytest.mark.slow
def test_counting_improves_the_edge(counting_results) -> None:
    """A Hi-Lo spread beats flat betting on the same cards."""
    flat, counting = counting_results
    flat_stats = flat.analytics()
    counting_stats = counting.analytics()
    assert counting_stats.avg_bet > flat_stats.avg_bet
    assert counting_stats.house_edge < flat_stats.house_edge - 0.003


@pytest.mark.slow
def test_high_true_counts_are_profitable(counting_results) -> None:
    """Aggregated play at true counts of three or more has positive EV."""
    _, counting = counting_results
    mask = counting.true_counts >= 3.0
    assert mask.sum() > 200
    net = float(counting.nets[mask].sum())
    wagered = float(counting.bets[mask].sum())
    assert -net / wagered < 0.0


@pytest.mark.slow
def test_house_edge_converges_to_theoretical() -> None:
    """Long flat-bet basic strategy play lands near the published edge."""
    result = run_simulation(
        300_000,
        bet=10,
        starting_bankroll=1_000_000,
        seed=101,
        track_decisions=False,
    )
    stats = result.analytics()
    assert 100_000 < stats.hands < 400_000
    assert 0.15 < stats.house_edge_percent < 0.85
