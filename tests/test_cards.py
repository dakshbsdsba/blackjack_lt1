"""Tests for cards and the dealing shoe."""

from __future__ import annotations

import pytest

from blackjack.cards import (
    RANKS,
    SUITS,
    Card,
    Shoe,
    card_from_text,
    cards_from_text,
)


@pytest.mark.parametrize(
    ("rank", "value"),
    [
        ("2", 2),
        ("3", 3),
        ("4", 4),
        ("5", 5),
        ("6", 6),
        ("7", 7),
        ("8", 8),
        ("9", 9),
        ("10", 10),
        ("J", 10),
        ("Q", 10),
        ("K", 10),
        ("A", 11),
    ],
)
def test_card_values(rank: str, value: int) -> None:
    """Every rank has the expected blackjack value."""
    card = Card(rank, "\u2660")
    assert card.value == value
    assert card.base_value == (1 if rank == "A" else value)


@pytest.mark.parametrize(
    ("rank", "tag"),
    [
        ("2", 1),
        ("3", 1),
        ("4", 1),
        ("5", 1),
        ("6", 1),
        ("7", 0),
        ("8", 0),
        ("9", 0),
        ("10", -1),
        ("J", -1),
        ("Q", -1),
        ("K", -1),
        ("A", -1),
    ],
)
def test_hi_lo_tags(rank: str, tag: int) -> None:
    """The Hi-Lo tag is correct for every rank."""
    assert Card(rank, "\u2665").hi_lo_value == tag


def test_card_flags() -> None:
    """Aces, ten cards and red suits are identified correctly."""
    assert Card("A", "\u2660").is_ace
    assert Card("K", "\u2666").is_ten
    assert Card("Q", "\u2665").is_red
    assert not Card("9", "\u2663").is_red
    assert str(Card("10", "\u2663")) == "10\u2663"


def test_invalid_card_raises() -> None:
    """Unknown ranks and suits are rejected at construction."""
    with pytest.raises(ValueError):
        Card("1", "\u2660")
    with pytest.raises(ValueError):
        Card("A", "X")


def test_card_from_text() -> None:
    """Compact strings parse in both letter and symbol suit form."""
    assert card_from_text("AS") == Card("A", "\u2660")
    assert card_from_text("10h") == Card("10", "\u2665")
    assert card_from_text("Qd") == Card("Q", "\u2666")
    assert card_from_text("7\u2663") == Card("7", "\u2663")
    cards = cards_from_text("AS 10H, 2D")
    assert [card.rank for card in cards] == ["A", "10", "2"]


def test_invalid_card_text() -> None:
    """Bad compact strings raise a ValueError."""
    with pytest.raises(ValueError):
        card_from_text("X")
    with pytest.raises(ValueError):
        card_from_text("AZ")


def test_shoe_composition() -> None:
    """A fresh shoe has exactly the right number of every rank."""
    shoe = Shoe(6, 0.75, seed=3)
    assert len(shoe) == 312
    counts = shoe.remaining_counts()
    for rank in RANKS:
        assert counts[rank] == 24
    assert sum(counts[rank] for rank in ("10", "J", "Q", "K")) == 96
    assert len(SUITS) == 4


def test_draw_removes_cards_and_fills_discard() -> None:
    """Drawing reduces the shoe and grows the discard tray."""
    shoe = Shoe(1, 0.75, seed=4)
    first = shoe.draw_one()
    assert len(shoe) == 51
    assert shoe.discard_tray == 1
    assert first not in shoe.dealt_cards[:-1]
    more = shoe.draw(4)
    assert len(more) == 4
    assert len(shoe) == 47
    assert shoe.discard_tray == 5


def test_draw_too_many_raises() -> None:
    """Drawing more cards than remain is rejected."""
    shoe = Shoe(1, 1.0, seed=5)
    with pytest.raises(ValueError):
        shoe.draw(53)
    with pytest.raises(ValueError):
        shoe.draw(-1)


def test_cut_card_and_shuffle() -> None:
    """The cut card triggers a shuffle and the tray is emptied."""
    shoe = Shoe(1, 0.1, seed=6)
    assert shoe.cut_card_index == 5
    shoe.draw(4)
    assert not shoe.needs_shuffle
    shoe.draw(1)
    assert shoe.needs_shuffle
    shuffles = shoe.shuffle_count
    assert shoe.shuffle_if_needed()
    assert shoe.shuffle_count == shuffles + 1
    assert shoe.discard_tray == 0
    assert len(shoe) == 52
    assert not shoe.needs_shuffle


def test_penetration_and_decks_remaining() -> None:
    """Penetration and fractional decks track the dealt cards."""
    shoe = Shoe(2, 0.5, seed=7)
    assert shoe.total_cards == 104
    assert shoe.cut_card_index == 52
    assert shoe.decks_remaining == 2.0
    shoe.draw(26)
    assert shoe.decks_remaining == 1.5
    assert shoe.penetration_actual == pytest.approx(0.25)


def test_stack_controls_deal_order() -> None:
    """The stack helper deals cards in the order given."""
    shoe = Shoe(1, 0.75, seed=10)
    shoe.stack(["AS", "10H", "2D"])
    assert str(shoe.draw_one()) == "A\u2660"
    assert str(shoe.draw_one()) == "10\u2665"
    assert str(shoe.draw_one()) == "2\u2666"
    assert shoe.discard_tray == 3


def test_seed_is_reproducible() -> None:
    """Two shoes with the same seed deal the same cards."""
    first = [shoe_card for shoe_card in Shoe(2, 0.75, seed=99).draw(20)]
    second = [shoe_card for shoe_card in Shoe(2, 0.75, seed=99).draw(20)]
    assert first == second


def test_true_count_divisor_floor() -> None:
    """The true-count divisor never falls below half a deck."""
    shoe = Shoe(1, 1.0, seed=8)
    shoe.draw(51)
    assert shoe.decks_remaining == pytest.approx(1 / 52)
    assert shoe.true_count_divisor == 0.5
