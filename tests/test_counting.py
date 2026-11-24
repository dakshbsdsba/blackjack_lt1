"""Hi-Lo counting tests (Tier 3 validation)."""

from __future__ import annotations

import pytest

from blackjack import BlackjackGame, HiLoCounter, Rules, count_cards
from blackjack.cards import card_from_text
from tests.helpers import start


def test_count_cards_sequence() -> None:
    """The running count follows the Hi-Lo tags."""
    cards = [card_from_text(token) for token in "2S 6H 10C AS 7D 9S 3C".split()]
    assert count_cards(cards) == 1 + 1 - 1 - 1 + 0 + 0 + 1


def test_counter_observe_and_reset() -> None:
    """Observing cards updates the running count and cards seen."""
    counter = HiLoCounter(num_decks=6)
    counter.observe(card_from_text("5S"))
    counter.observe(card_from_text("KH"))
    counter.observe_many([card_from_text("2C"), card_from_text("9D")])
    assert counter.running_count == 1
    assert counter.cards_seen == 4
    assert counter.decks_seen == pytest.approx(4 / 52)
    counter.reset()
    assert counter.running_count == 0
    assert counter.cards_seen == 0


def test_true_count_divides_by_remaining_decks() -> None:
    """True count is the running count divided by decks remaining."""
    counter = HiLoCounter()
    counter.observe_many([card_from_text("5S"), card_from_text("6H")])
    assert counter.true_count(2.0) == pytest.approx(1.0)
    assert counter.true_count(0.0) == pytest.approx(4.0)  # floor of half a deck


def test_engine_counter_matches_dealt_history() -> None:
    """After every settled round the counter equals the shoe's history."""
    game = BlackjackGame(Rules(), 10_000.0, seed=31, log_decisions=False)
    for _ in range(200):
        game.play_hand(10.0)
        dealt = game.shoe.dealt_cards
        assert game.counter.cards_seen == len(dealt)
        assert game.counter.running_count == count_cards(dealt)
        assert game.true_count == pytest.approx(
            game.counter.running_count / max(0.5, game.shoe.decks_remaining)
        )


def test_counter_resets_when_the_shoe_is_shuffled() -> None:
    """A shuffle clears the count, and the counter tracks the new shoe."""
    rules = Rules(num_decks=1, penetration=0.15)
    game = BlackjackGame(rules, 10_000.0, seed=32, log_decisions=False)
    shuffle_seen = 0
    for _ in range(200):
        before = game.shoe.shuffle_count
        game.play_hand(5.0)
        if game.shoe.shuffle_count > before:
            shuffle_seen += 1
        dealt = game.shoe.dealt_cards
        assert game.counter.cards_seen == len(dealt)
        assert game.counter.running_count == count_cards(dealt)
    assert shuffle_seen > 0


def test_count_accounting_over_a_scripted_split() -> None:
    """Counts include every card dealt during a split round."""
    game = BlackjackGame(Rules(), 1000.0, seed=33, log_decisions=False)
    start(game, ["8S", "9C", "8H", "7D", "3C", "2D", "10C"], bet=25.0)
    game.act("split")
    game.act("stand")
    game.act("stand")
    dealt = game.shoe.dealt_cards
    assert game.counter.cards_seen == len(dealt) == 7
    assert game.counter.running_count == count_cards(dealt)


def test_starting_count_includes_preexisting_discards() -> None:
    """A game attached to a used shoe starts with the correct count."""
    from blackjack.cards import Shoe

    shoe = Shoe(6, 0.75, seed=34)
    shoe.draw(20)
    game = BlackjackGame(Rules(), 1000.0, shoe=shoe, log_decisions=False)
    assert game.counter.cards_seen == 20
    assert game.counter.running_count == count_cards(shoe.dealt_cards)


def test_snapshot_shape() -> None:
    """The UI snapshot contains the running and true counts."""
    counter = HiLoCounter()
    counter.observe(card_from_text("5S"))
    snapshot = counter.snapshot(3.0)
    assert snapshot["running_count"] == 1
    assert snapshot["true_count"] == pytest.approx(0.33)
    assert snapshot["cards_seen"] == 1


def test_remaining_estimate_never_negative() -> None:
    """The estimated remaining composition subtracts every seen card."""
    counter = HiLoCounter(num_decks=1)
    counter.observe_many([card_from_text("AS") for _ in range(4)])
    remaining = counter.remaining_estimate()
    assert remaining["A"] == 0
    assert remaining["10"] == 16
