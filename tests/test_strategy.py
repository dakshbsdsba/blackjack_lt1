"""Basic strategy consistency tests against an independent chart.

The reference implementation below is written as explicit if/elif rules
rather than as a copy of the tables in ``blackjack.strategy``. That makes the
test a real cross-check: a typo in a table row or a wrong column index will
disagree with the rules and fail.
"""

from __future__ import annotations

import pytest

from blackjack import Rules, basic_strategy_action, hand_from_cards, strategy_rows

DEALERS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "A")


def reference_action(
    hand: object,
    dealer: str,
    *,
    can_double: bool = True,
    can_split: bool = True,
    can_surrender: bool = True,
) -> str:
    """An independent, rule-based basic strategy chart for 6-deck S17."""
    from blackjack.hand import Hand

    assert isinstance(hand, Hand)

    if hand.is_pair and can_split:
        pair = hand.pair_rank
        if pair in ("A", "8"):
            return "split"
        if pair == "10":
            return "stand"
        if pair == "9":
            return "split" if dealer in ("2", "3", "4", "5", "6", "8", "9") else "stand"
        if pair == "7":
            return "split" if dealer in ("2", "3", "4", "5", "6", "7") else "hit"
        if pair == "6":
            return "split" if dealer in ("2", "3", "4", "5", "6") else "hit"
        if pair == "4":
            return "split" if dealer in ("5", "6") else "hit"
        if pair in ("2", "3"):
            return "split" if dealer in ("2", "3", "4", "5", "6", "7") else "hit"
        # Five-five is played as a hard ten and falls through below.

    if can_surrender and not hand.is_soft and len(hand.cards) == 2:
        if hand.total == 16 and dealer in ("9", "10", "A"):
            return "surrender"
        if hand.total == 15 and dealer == "10":
            return "surrender"

    if hand.is_soft:
        total = hand.total
        if total <= 12:
            return "hit"
        if total in (13, 14):
            wants_double = dealer in ("5", "6")
            return "double" if wants_double and can_double else "hit"
        if total in (15, 16):
            wants_double = dealer in ("4", "5", "6")
            return "double" if wants_double and can_double else "hit"
        if total == 17:
            wants_double = dealer in ("3", "4", "5", "6")
            return "double" if wants_double and can_double else "hit"
        if total == 18:
            if dealer in ("3", "4", "5", "6"):
                return "double" if can_double else "stand"
            if dealer in ("2", "7", "8"):
                return "stand"
            return "hit"
        return "stand"

    total = hand.total
    if total >= 17:
        return "stand"
    if total <= 8:
        return "hit"
    if total == 9:
        return "double" if dealer in ("3", "4", "5", "6") and can_double else "hit"
    if total == 10:
        return (
            "double"
            if dealer in ("2", "3", "4", "5", "6", "7", "8", "9") and can_double
            else "hit"
        )
    if total == 11:
        return "double" if can_double else "hit"
    if total == 12:
        return "stand" if dealer in ("4", "5", "6") else "hit"
    return "stand" if dealer in ("2", "3", "4", "5", "6") else "hit"


HARD_HANDS = {
    5: "2S 3H",
    6: "2S 4H",
    7: "3S 4H",
    8: "2S 6H",
    9: "4S 5H",
    10: "4S 6H",
    11: "5S 6H",
    12: "5S 7H",
    13: "6S 7H",
    14: "6S 8H",
    15: "7S 8H",
    16: "7S 9H",
    17: "8S 9H",
    18: "8S 10H",
    19: "9S 10H",
    20: "JS QH",
    21: "7S 7H 7D",
}

SOFT_HANDS = {
    12: "AS AH",
    13: "AS 2H",
    14: "AS 3H",
    15: "AS 4H",
    16: "AS 5H",
    17: "AS 6H",
    18: "AS 7H",
    19: "AS 8H",
    20: "AS 9H",
}

PAIR_HANDS = {
    "A": "AS AH",
    "10": "10S JH",
    "9": "9S 9H",
    "8": "8S 8H",
    "7": "7S 7H",
    "6": "6S 6H",
    "5": "5S 5H",
    "4": "4S 4H",
    "3": "3S 3H",
    "2": "2S 2H",
}


@pytest.mark.parametrize("total", sorted(HARD_HANDS))
@pytest.mark.parametrize("dealer", DEALERS)
def test_hard_totals_match_reference(total: int, dealer: str) -> None:
    """Every hard total agrees with the independent chart."""
    hand = hand_from_cards(HARD_HANDS[total].split())
    assert hand.total == total
    expected = reference_action(hand, dealer)
    assert basic_strategy_action(hand, dealer, Rules()) == expected


@pytest.mark.parametrize("total", sorted(SOFT_HANDS))
@pytest.mark.parametrize("dealer", DEALERS)
def test_soft_totals_match_reference(total: int, dealer: str) -> None:
    """Every soft total agrees with the independent chart."""
    hand = hand_from_cards(SOFT_HANDS[total].split())
    assert hand.total == total
    assert hand.is_soft
    expected = reference_action(hand, dealer)
    assert basic_strategy_action(hand, dealer, Rules()) == expected


@pytest.mark.parametrize("pair", sorted(PAIR_HANDS))
@pytest.mark.parametrize("dealer", DEALERS)
def test_pairs_match_reference(pair: str, dealer: str) -> None:
    """Every pair agrees with the independent chart."""
    hand = hand_from_cards(PAIR_HANDS[pair].split())
    assert hand.pair_rank == pair
    expected = reference_action(hand, dealer)
    assert basic_strategy_action(hand, dealer, Rules()) == expected


@pytest.mark.parametrize("can_double", [True, False])
@pytest.mark.parametrize("can_split", [True, False])
@pytest.mark.parametrize("can_surrender", [True, False])
def test_availability_fallbacks(
    can_double: bool, can_split: bool, can_surrender: bool
) -> None:
    """The chart falls back correctly when an action is unavailable."""
    for cards in ("10S 6H", "8S 8H", "AS 7H", "5S 6H", "9S 9H", "4S 4H"):
        hand = hand_from_cards(cards.split())
        for dealer in DEALERS:
            action = basic_strategy_action(
                hand,
                dealer,
                Rules(),
                can_double=can_double,
                can_split=can_split,
                can_surrender=can_surrender,
            )
            expected = reference_action(
                hand,
                dealer,
                can_double=can_double,
                can_split=can_split,
                can_surrender=can_surrender,
            )
            assert action == expected
            legal = {"hit", "stand"}
            if can_double and len(hand.cards) == 2:
                legal.add("double")
            if can_split and hand.is_pair:
                legal.add("split")
            if can_surrender and not hand.is_soft and len(hand.cards) == 2:
                legal.add("surrender")
            assert action in legal


def test_eleven_doubles_against_everything() -> None:
    """With a US peek game, eleven doubles even against an ace."""
    hand = hand_from_cards(["5S", "6H"])
    for dealer in DEALERS:
        assert basic_strategy_action(hand, dealer, Rules()) == "double"
    assert basic_strategy_action(hand, "A", Rules()) == "double"


def test_soft_eighteen_double_else_stand() -> None:
    """Soft eighteen doubles against 3-6 and stands when doubling is barred."""
    hand = hand_from_cards(["AS", "7H"])
    for dealer in ("3", "4", "5", "6"):
        assert basic_strategy_action(hand, dealer, Rules()) == "double"
        assert basic_strategy_action(hand, dealer, Rules(), can_double=False) == "stand"
    for dealer in ("2", "7", "8"):
        assert basic_strategy_action(hand, dealer, Rules()) == "stand"
    for dealer in ("9", "10", "A"):
        assert basic_strategy_action(hand, dealer, Rules()) == "hit"


def test_surrender_cells() -> None:
    """Late surrender only applies to the standard two-card cells."""
    sixteen = hand_from_cards(["10S", "6H"])
    for dealer in ("9", "10", "A"):
        assert basic_strategy_action(sixteen, dealer, Rules()) == "surrender"
        assert (
            basic_strategy_action(sixteen, dealer, Rules(), can_surrender=False)
            == "hit"
        )
    fifteen = hand_from_cards(["7S", "8H"])
    assert basic_strategy_action(fifteen, "10", Rules()) == "surrender"
    assert basic_strategy_action(fifteen, "A", Rules()) == "hit"
    assert basic_strategy_action(fifteen, "9", Rules()) == "hit"


def test_pair_exceptions() -> None:
    """Aces and eights always split, tens and fives never split."""
    for dealer in DEALERS:
        assert (
            basic_strategy_action(hand_from_cards(["AS", "AH"]), dealer, Rules())
            == "split"
        )
        assert (
            basic_strategy_action(hand_from_cards(["8S", "8H"]), dealer, Rules())
            == "split"
        )
        assert (
            basic_strategy_action(hand_from_cards(["10S", "JH"]), dealer, Rules())
            == "stand"
        )
        assert (
            basic_strategy_action(hand_from_cards(["5S", "5H"]), dealer, Rules())
            != "split"
        )


def test_pair_nine_and_four_edges() -> None:
    """The close pair cells follow the published chart."""
    nine = hand_from_cards(["9S", "9H"])
    assert basic_strategy_action(nine, "7", Rules()) == "stand"
    assert basic_strategy_action(nine, "8", Rules()) == "split"
    four = hand_from_cards(["4S", "4H"])
    assert basic_strategy_action(four, "5", Rules()) == "split"
    assert basic_strategy_action(four, "4", Rules()) == "hit"


def test_dealer_rank_normalisation() -> None:
    """Face cards and ten all map to the same dealer column."""
    from blackjack.cards import Card, card_from_text
    from blackjack.strategy import dealer_rank

    assert dealer_rank("J") == "10"
    assert dealer_rank("Q") == "10"
    assert dealer_rank("K") == "10"
    assert dealer_rank("10") == "10"
    assert dealer_rank(Card("A", "\u2660")) == "A"
    assert dealer_rank(card_from_text("9D")) == "9"


def test_strategy_rows_shape() -> None:
    """Every display row is ten decisions long and uses valid codes."""
    rows = strategy_rows()
    assert len(rows) == 26
    for label, row in rows:
        assert len(row) == 10, label
        assert set(row) <= set("HSDPd"), label


def test_invalid_dealer_raises() -> None:
    """A dealer upcard outside 2..A is rejected."""
    hand = hand_from_cards(["10S", "7H"])
    with pytest.raises(ValueError):
        basic_strategy_action(hand, "1", Rules())
