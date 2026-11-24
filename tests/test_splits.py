"""Split-hand state and payout tests (Tier 2 validation)."""

from __future__ import annotations

import pytest

from blackjack import BlackjackGame, Outcome, Rules
from tests.helpers import start


def test_split_creates_two_independent_hands(rich_game: BlackjackGame) -> None:
    """Splitting posts a second bet and deals one card to each hand."""
    start(rich_game, ["8S", "9C", "8H", "7D", "3C", "2D", "10C"], bet=25.0)
    assert "split" in rich_game.available_actions()
    rich_game.act("split")

    assert len(rich_game.hands) == 2
    assert rich_game.bankroll == pytest.approx(950.0)
    assert [hand.bet for hand in rich_game.hands] == [25.0, 25.0]
    assert [len(hand.cards) for hand in rich_game.hands] == [2, 2]
    assert [hand.start_total for hand in rich_game.hands] == [11, 10]
    assert all(hand.is_split_hand for hand in rich_game.hands)

    rich_game.act("stand")
    rich_game.act("stand")
    assert len(rich_game.round_results) == 2
    assert all(result.outcome is Outcome.WIN for result in rich_game.round_results)
    assert rich_game.bankroll == pytest.approx(1050.0)


def test_split_hands_pay_out_without_state_bleed(rich_game: BlackjackGame) -> None:
    """One split hand can lose while the other wins."""
    start(
        rich_game,
        ["8S", "9C", "8H", "7D", "10C", "5D", "10H", "10D"],
        bet=25.0,
    )
    rich_game.act("split")
    rich_game.act("stand")  # eighteen stands
    rich_game.act("hit")  # thirteen draws ten and busts
    assert rich_game.state.value == "settled"

    outcomes = [result.outcome for result in rich_game.round_results]
    assert outcomes == [Outcome.WIN, Outcome.LOSS]
    assert [result.net for result in rich_game.round_results] == [25.0, -25.0]
    assert rich_game.bankroll == pytest.approx(1000.0)


def test_split_aces_get_one_card_each(rich_game: BlackjackGame) -> None:
    """Split aces receive a single card and stand automatically."""
    start(rich_game, ["AS", "9C", "AH", "7D", "10C", "9D", "10H"], bet=25.0)
    rich_game.act("split")

    assert len(rich_game.hands) == 2
    assert all(len(hand.cards) == 2 for hand in rich_game.hands)
    assert all(hand.stood for hand in rich_game.hands)
    assert rich_game.state.value == "settled"
    assert len(rich_game.round_results) == 2
    assert all(result.outcome is Outcome.WIN for result in rich_game.round_results)
    assert rich_game.bankroll == pytest.approx(1050.0)


def test_split_twenty_one_is_not_blackjack(rich_game: BlackjackGame) -> None:
    """An ace-ten after a split pays even money, not 3:2."""
    start(rich_game, ["AS", "9C", "AH", "7D", "10C", "9D", "10H"], bet=25.0)
    rich_game.act("split")
    first = rich_game.round_results[0]
    assert first.player_total == 21
    assert not first.is_blackjack
    assert first.net == 25.0


def test_resplit_is_allowed_up_to_the_limit(rich_game: BlackjackGame) -> None:
    """Three hands can be produced from two splits of eights."""
    start(
        rich_game,
        ["8S", "9C", "8H", "7D", "8C", "2D", "3C", "4D", "10H"],
        bet=25.0,
    )
    rich_game.act("split")
    assert len(rich_game.hands) == 2
    assert "split" in rich_game.available_actions()
    rich_game.act("split")
    assert len(rich_game.hands) == 3
    assert rich_game.bankroll == pytest.approx(925.0)

    for _ in range(3):
        rich_game.act("stand")
    assert len(rich_game.round_results) == 3
    assert all(result.outcome is Outcome.WIN for result in rich_game.round_results)
    assert rich_game.bankroll == pytest.approx(1075.0)


def test_max_split_hands_is_enforced() -> None:
    """No further split is offered once the hand limit is reached."""
    rules = Rules(max_split_hands=2)
    game = BlackjackGame(rules, 1000.0, seed=21)
    start(game, ["8S", "9C", "8H", "7D", "8C", "2D"], bet=25.0)
    game.act("split")
    assert len(game.hands) == 2
    assert "split" not in game.available_actions()


def test_resplit_aces_disallowed_by_default() -> None:
    """A second ace pair cannot be split unless the rules allow it."""
    rules = Rules(hit_split_aces=True, resplit_aces=False)
    game = BlackjackGame(rules, 1000.0, seed=24)
    start(game, ["AS", "9C", "AH", "7D", "AC", "2D", "10H"], bet=25.0)
    game.act("split")
    assert game.hands[0].from_split_aces
    assert "split" not in game.available_actions()
    assert "hit" in game.available_actions()


def test_resplit_aces_allowed_when_configured() -> None:
    """The resplit-aces rule re-enables the split action."""
    rules = Rules(hit_split_aces=True, resplit_aces=True)
    game = BlackjackGame(rules, 1000.0, seed=25)
    start(game, ["AS", "9C", "AH", "7D", "AC", "2D", "10H"], bet=25.0)
    game.act("split")
    assert "split" in game.available_actions()


def test_ten_valued_pair_can_be_split_by_the_engine(rich_game: BlackjackGame) -> None:
    """Splitting tens is legal at the table even though strategy says stand."""
    start(rich_game, ["10S", "9C", "JH", "7D", "2C", "3D"], bet=25.0)
    assert "split" in rich_game.available_actions()
    rich_game.act("split")
    assert len(rich_game.hands) == 2


def test_split_requires_a_second_bet() -> None:
    """A player with no chips behind cannot split."""
    game = BlackjackGame(Rules(), 25.0, seed=22)
    start(game, ["8S", "9C", "8H", "7D"], bet=25.0)
    assert "split" not in game.available_actions()


def test_surrender_is_not_available_after_split(rich_game: BlackjackGame) -> None:
    """Surrender belongs to the original two-card hand only."""
    start(rich_game, ["8S", "9C", "8H", "7D", "3C", "2D"], bet=25.0)
    rich_game.act("split")
    assert "surrender" not in rich_game.available_actions()


def test_double_after_split_is_available(rich_game: BlackjackGame) -> None:
    """DAS allows a two-card split hand to double."""
    start(
        rich_game,
        ["8S", "9C", "8H", "7D", "3C", "2D", "10C", "10H"],
        bet=25.0,
    )
    rich_game.act("split")
    assert "double" in rich_game.available_actions()
    rich_game.act("double")
    assert rich_game.hands[0].is_doubled
    assert rich_game.hands[0].bet == 50.0
    assert rich_game.bankroll == pytest.approx(925.0)
    rich_game.act("stand")
    assert len(rich_game.round_results) == 2
    assert rich_game.round_results[0].net == 50.0
    assert rich_game.round_results[1].net == 25.0
    assert rich_game.bankroll == pytest.approx(1075.0)


def test_double_after_split_disabled() -> None:
    """With DAS off, a split hand cannot double."""
    rules = Rules(double_after_split=False)
    game = BlackjackGame(rules, 1000.0, seed=23)
    start(game, ["8S", "9C", "8H", "7D", "3C", "2D"], bet=25.0)
    game.act("split")
    assert "double" not in game.available_actions()


def test_split_hands_have_independent_wagers(rich_game: BlackjackGame) -> None:
    """Doubling one split hand does not change the other hand's bet."""
    start(
        rich_game,
        ["8S", "9C", "8H", "7D", "3C", "2D", "10C", "10H"],
        bet=25.0,
    )
    rich_game.act("split")
    rich_game.act("double")
    assert rich_game.hands[0].bet == 50.0
    assert rich_game.hands[1].bet == 25.0
    assert rich_game.total_wagered == pytest.approx(75.0)
