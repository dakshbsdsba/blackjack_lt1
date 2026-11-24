"""Tests for hand evaluation."""

from __future__ import annotations

import pytest

from blackjack import Hand, hand_from_cards


def test_soft_ace_counts_eleven() -> None:
    """Ace plus six is a soft seventeen."""
    hand = hand_from_cards(["AS", "6H"])
    assert hand.total == 17
    assert hand.hard_total == 7
    assert hand.is_soft


def test_ace_reverts_to_one() -> None:
    """Adding a ten turns the same hand hard without busting."""
    hand = hand_from_cards(["AS", "6H", "10D"])
    assert hand.total == 17
    assert hand.hard_total == 17
    assert not hand.is_soft


def test_two_aces_are_twelve() -> None:
    """Two aces are soft twelve, not twenty-two."""
    hand = hand_from_cards(["AS", "AH"])
    assert hand.total == 12
    assert hand.is_soft
    assert hand.num_aces == 2


def test_multiple_aces_only_one_is_eleven() -> None:
    """Only one ace can count as eleven at a time."""
    hand = hand_from_cards(["AS", "AH", "9D", "5C"])
    assert hand.hard_total == 16
    assert hand.total == 16
    assert not hand.is_soft


def test_blackjack_detection() -> None:
    """A two-card twenty-one is a natural."""
    hand = hand_from_cards(["AS", "KH"])
    assert hand.is_blackjack
    assert hand.total == 21


def test_three_card_twenty_one_is_not_blackjack() -> None:
    """A twenty-one made with three cards is not a natural."""
    hand = hand_from_cards(["7S", "7H", "7D"])
    assert hand.total == 21
    assert not hand.is_blackjack


def test_split_hand_is_not_blackjack() -> None:
    """A split ace and ten is twenty-one, not a natural."""
    hand = Hand(is_split_hand=True)
    hand.add(hand_from_cards(["AS"]).cards[0])
    hand.add(hand_from_cards(["10H"]).cards[0])
    assert hand.total == 21
    assert not hand.is_blackjack


def test_pair_detection() -> None:
    """Ten-valued cards form a pair for splitting purposes."""
    assert hand_from_cards(["10S", "JH"]).pair_rank == "10"
    assert hand_from_cards(["AS", "AH"]).pair_rank == "A"
    assert hand_from_cards(["9S", "9H"]).is_pair
    assert not hand_from_cards(["9S", "8H"]).is_pair
    assert not hand_from_cards(["9S", "9H", "9D"]).is_pair


def test_bust_and_finished() -> None:
    """Bust hands are finished and cannot be hit."""
    hand = hand_from_cards(["10S", "9H", "5D"])
    hand.stood = False
    assert hand.is_bust
    assert hand.total == 24
    assert hand.is_finished


def test_copy_is_independent() -> None:
    """Copying a hand does not share the card list."""
    hand = hand_from_cards(["8S", "8H"], bet=10)
    clone = hand.copy()
    clone.add(hand_from_cards(["2C"]).cards[0])
    assert len(hand.cards) == 2
    assert len(clone.cards) == 3
    assert clone.bet == 10
    assert clone is not hand


def test_display_marks_soft() -> None:
    """The display string identifies soft hands."""
    hand = hand_from_cards(["AS", "7H"])
    assert "soft" in hand.display
    assert "18" in hand.display


def test_invalid_hand_text() -> None:
    """Bad card strings surface a ValueError."""
    with pytest.raises(ValueError):
        hand_from_cards(["ZZ"])
