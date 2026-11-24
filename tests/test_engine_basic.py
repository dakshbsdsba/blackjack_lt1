"""Core rules engine tests: dealing, dealer logic, settlement, bankroll."""

from __future__ import annotations

import pytest

from blackjack import BlackjackGame, GameState, Outcome, Rules
from tests.helpers import rig_shoe, start


def test_initial_deal_and_bankroll(game: BlackjackGame) -> None:
    """A bet is posted and both sides receive two cards."""
    start(game, ["10S", "9C", "7H", "7D", "10C"])
    assert game.bankroll == 975.0
    assert game.state is GameState.PLAYER
    assert len(game.hands) == 1
    assert len(game.hands[0].cards) == 2
    assert len(game.dealer.cards) == 2
    assert game.hands[0].total == 17
    assert game.dealer.total == 16
    assert game.rules.dealer_stands_soft_17


def test_stand_win_pays_even_money(game: BlackjackGame) -> None:
    """A winning hand returns the stake plus an equal profit."""
    start(game, ["10S", "9C", "7H", "7D", "10C"])
    game.act("stand")
    assert game.state is GameState.SETTLED
    result = game.round_results[0]
    assert result.outcome is Outcome.WIN
    assert result.net == 25.0
    assert game.bankroll == 1025.0


def test_blackjack_pays_three_to_two(game: BlackjackGame) -> None:
    """A natural pays 3:2 and settles immediately."""
    start(game, ["AS", "9C", "10H", "7D"])
    assert game.state is GameState.SETTLED
    result = game.round_results[0]
    assert result.outcome is Outcome.BLACKJACK
    assert result.is_blackjack
    assert result.net == pytest.approx(37.5)
    assert game.bankroll == pytest.approx(1037.5)


def test_blackjack_on_later_rounds_still_pays(game: BlackjackGame) -> None:
    """A natural in a later round is not skipped by stale state."""
    start(game, ["AS", "9C", "10H", "7D"])
    assert game.bankroll == pytest.approx(1037.5)
    start(game, ["AH", "8C", "KH", "9D"])
    assert game.round_results[0].outcome is Outcome.BLACKJACK
    assert game.bankroll == pytest.approx(1075.0)


def test_blackjack_push_against_dealer_natural(game: BlackjackGame) -> None:
    """Two naturals push and the stake comes back."""
    start(game, ["AS", "AC", "10H", "KC"])
    result = game.round_results[0]
    assert result.outcome is Outcome.PUSH
    assert result.net == 0.0
    assert game.bankroll == 1000.0


def test_dealer_blackjack_beats_twenty(game: BlackjackGame) -> None:
    """A dealer natural beats a normal twenty."""
    start(game, ["10S", "AC", "QH", "KD"])
    assert game.state is GameState.SETTLED
    result = game.round_results[0]
    assert result.outcome is Outcome.LOSS
    assert result.net == -25.0
    assert game.bankroll == 975.0


def test_regular_push(game: BlackjackGame) -> None:
    """Equal totals push and the stake is returned."""
    start(game, ["10S", "9C", "8H", "9D"])
    game.act("stand")
    result = game.round_results[0]
    assert result.outcome is Outcome.PUSH
    assert result.net == 0.0
    assert game.bankroll == 1000.0


def test_bust_loses_and_dealer_does_not_draw(game: BlackjackGame) -> None:
    """A busted player loses and the dealer has no reason to draw."""
    start(game, ["10S", "9C", "6H", "7D", "10C"])
    game.act("hit")
    assert game.hands[0].is_bust
    result = game.round_results[0]
    assert result.outcome is Outcome.LOSS
    assert result.player_total == 26
    assert len(game.dealer.cards) == 2
    assert game.bankroll == 975.0


def test_dealer_hits_until_seventeen(game: BlackjackGame) -> None:
    """The dealer draws on sixteen and stands on the resulting total."""
    start(game, ["10S", "9C", "8H", "7D", "2C"])
    game.act("stand")
    assert game.dealer.total == 18
    assert len(game.dealer.cards) == 3
    assert game.round_results[0].outcome is Outcome.PUSH


def test_dealer_stands_on_soft_seventeen(game: BlackjackGame) -> None:
    """In an S17 game the dealer stands on ace-six."""
    start(game, ["10S", "AC", "8H", "6C"])
    assert game.dealer.total == 17
    assert game.dealer.is_soft
    game.act("stand")
    assert len(game.dealer.cards) == 2
    assert game.round_results[0].outcome is Outcome.WIN
    assert game.bankroll == 1025.0


def test_dealer_hits_soft_seventeen_when_configured() -> None:
    """In an H17 game the dealer takes another card on soft seventeen."""
    rules = Rules(dealer_stands_soft_17=False)
    game = BlackjackGame(rules, 1000.0, seed=3)
    start(game, ["10S", "AC", "8H", "6C", "3D"])
    game.act("stand")
    assert game.dealer.total == 20
    assert len(game.dealer.cards) == 3
    assert game.round_results[0].outcome is Outcome.LOSS
    assert game.bankroll == 975.0


def test_dealer_bust_pays_the_player(game: BlackjackGame) -> None:
    """A dealer bust pays every live hand."""
    start(game, ["10S", "6C", "8H", "10D", "10C"])
    game.act("stand")
    assert game.dealer.is_bust
    assert game.round_results[0].outcome is Outcome.WIN
    assert game.bankroll == 1025.0


def test_custom_blackjack_payout() -> None:
    """The payout ratio is taken from the rules."""
    rules = Rules(blackjack_payout=1.2)
    game = BlackjackGame(rules, 100.0, seed=4)
    start(game, ["AS", "9C", "10H", "7D"], bet=10)
    assert game.round_results[0].net == pytest.approx(12.0)
    assert game.bankroll == pytest.approx(112.0)


def test_bankroll_never_negative_and_ledger_balances() -> None:
    """Across hundreds of random hands the books always balance."""
    game = BlackjackGame(Rules(min_bet=1.0), 200.0, seed=13, log_decisions=False)
    starting = game.bankroll
    for _ in range(300):
        if game.bankroll < 1.0:
            break
        bet = min(5.0, game.bankroll)
        game.play_hand(bet)
        assert game.bankroll >= 0.0
        assert game.bankroll == pytest.approx(
            starting + sum(result.net for result in game.history), abs=1e-6
        )
        assert game.total_net == pytest.approx(
            sum(result.net for result in game.history), abs=1e-6
        )


def test_invalid_bets_are_rejected(game: BlackjackGame) -> None:
    """Bets outside the table limits or above the bankroll do not start a hand."""
    for bet in (0.0, -5.0, 1000.01, 20_000.0):
        with pytest.raises(ValueError):
            game.start_hand(bet)
    assert game.state is GameState.IDLE
    assert game.bankroll == 1000.0


def test_all_in_bet_is_allowed_and_can_reach_zero() -> None:
    """A legal all-in bet is allowed and a loss can leave exactly zero."""
    game = BlackjackGame(Rules(), 25.0, seed=5)
    start(game, ["10S", "9C", "6H", "7D", "10C"], bet=25.0)
    game.act("hit")
    assert game.bankroll == 0.0
    assert game.round_results[0].net == -25.0
    with pytest.raises(ValueError):
        game.start_hand(1.0)


def test_insurance_is_offered_only_on_ace(game: BlackjackGame) -> None:
    """The insurance state appears only when the dealer shows an ace."""
    start(game, ["10S", "KC", "7H", "6D"])
    assert game.state is GameState.PLAYER
    assert game.insurance_bet == 0.0

    second = BlackjackGame(Rules(), 1000.0, seed=17)
    rig_shoe(second, ["10S", "AC", "7H", "6D"])
    second.start_hand(25.0)
    assert second.state is GameState.INSURANCE
    second.take_insurance(False)
    assert second.state is GameState.PLAYER
    assert second.insurance_bet == 0.0


def test_insurance_lost_when_dealer_has_no_blackjack() -> None:
    """Insurance is a separate losing bet when the dealer is not natural."""
    game = BlackjackGame(Rules(), 1000.0, seed=6)
    rig_shoe(game, ["10S", "AC", "7H", "9D"])
    game.start_hand(25.0)
    assert game.state is GameState.INSURANCE
    game.take_insurance(True)
    assert game.insurance_bet == 12.5
    assert game.bankroll == pytest.approx(962.5)
    assert game.state is GameState.PLAYER
    game.act("stand")
    assert game.round_results[0].outcome is Outcome.LOSS
    assert game.bankroll == pytest.approx(962.5)
    assert game.total_wagered == pytest.approx(37.5)


def test_insurance_pays_two_to_one_on_dealer_blackjack() -> None:
    """Insurance exactly offsets the main bet when the dealer is natural."""
    game = BlackjackGame(Rules(), 1000.0, seed=7)
    rig_shoe(game, ["10S", "AC", "7H", "KD"])
    game.start_hand(25.0)
    game.take_insurance(True)
    assert game.bankroll == pytest.approx(1000.0)
    assert game.round_results[0].outcome is Outcome.LOSS
    assert game.round_results[0].net == -25.0
    assert game.insurance_bet == 12.5


def test_declining_insurance_keeps_the_chips() -> None:
    """Declining insurance costs nothing extra."""
    game = BlackjackGame(Rules(), 1000.0, seed=8)
    rig_shoe(game, ["10S", "AC", "7H", "KD"])
    game.start_hand(25.0)
    game.take_insurance(False)
    assert game.bankroll == 975.0
    assert game.insurance_bet == 0.0


def test_double_posts_a_second_bet_and_draws_once(game: BlackjackGame) -> None:
    """Doubling doubles the wager, takes one card, and then stands."""
    start(game, ["5S", "9C", "6H", "7D", "10C", "10D"])
    assert "double" in game.available_actions()
    game.act("double")
    hand = game.hands[0]
    assert hand.is_doubled
    assert hand.bet == 50.0
    assert len(hand.cards) == 3
    assert game.bankroll == pytest.approx(1050.0)
    result = game.round_results[0]
    assert result.net == 50.0
    assert result.wagered == 50.0


def test_double_not_available_after_a_hit(game: BlackjackGame) -> None:
    """Doubling is a two-card action only."""
    start(game, ["5S", "9C", "6H", "7D", "2C"])
    game.act("hit")
    assert "double" not in game.available_actions()


def test_double_not_available_without_bankroll() -> None:
    """A player cannot double with no chips behind."""
    game = BlackjackGame(Rules(), 25.0, seed=9)
    start(game, ["5S", "9C", "6H", "7D"], bet=25.0)
    assert "double" not in game.available_actions()
    assert "split" not in game.available_actions()


def test_surrender_returns_half_the_bet(game: BlackjackGame) -> None:
    """Late surrender gives back half the stake and records the loss."""
    start(game, ["10S", "10C", "6H", "7D"])
    assert "surrender" in game.available_actions()
    game.act("surrender")
    result = game.round_results[0]
    assert result.outcome is Outcome.SURRENDER
    assert result.net == pytest.approx(-12.5)
    assert game.bankroll == pytest.approx(987.5)


def test_surrender_not_available_after_hit(game: BlackjackGame) -> None:
    """Surrender is only available on the first two cards."""
    start(game, ["5S", "9C", "6H", "7D", "2C"])
    game.act("hit")
    assert "surrender" not in game.available_actions()


def test_available_actions_for_a_plain_hand(game: BlackjackGame) -> None:
    """A two-card non-pair has hit, stand, double and surrender."""
    start(game, ["10S", "9C", "7H", "7D"])
    assert set(game.available_actions()) == {"hit", "stand", "double", "surrender"}


def test_illegal_action_raises(game: BlackjackGame) -> None:
    """An action outside the legal set is rejected."""
    start(game, ["10S", "9C", "7H", "7D"])
    with pytest.raises(ValueError):
        game.act("split")


def test_hitting_to_twenty_one_auto_stands(game: BlackjackGame) -> None:
    """A hand that reaches twenty-one is finished automatically."""
    start(game, ["5S", "9C", "6H", "7D", "10C", "2D"])
    game.act("hit")
    assert game.hands[0].total == 21
    assert game.hands[0].stood
    assert game.state is GameState.SETTLED


def test_round_history_accumulates(game: BlackjackGame) -> None:
    """Each settled round is appended to the session history."""
    start(game, ["10S", "9C", "8H", "9D"])
    game.act("stand")
    start(game, ["10S", "9C", "8H", "9D"])
    game.act("stand")
    assert len(game.history) == 2
    assert game.hands_played == 2
    assert game.bankroll == 1000.0


def test_shoe_status_shape(game: BlackjackGame) -> None:
    """The UI snapshot exposes the expected keys."""
    start(game, ["10S", "9C", "8H", "9D"])
    status = game.shoe_status()
    for key in (
        "cards_remaining",
        "total_cards",
        "decks_remaining",
        "discard_tray",
        "penetration",
        "needs_shuffle",
        "shuffle_count",
        "running_count",
        "true_count",
    ):
        assert key in status
    assert 0 <= status["cards_remaining"] <= 312
