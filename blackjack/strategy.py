"""Basic strategy for a six-deck, dealer-stands-on-soft-17 game.

The tables below are the standard multi-deck basic strategy chart for a game
with double after split and late surrender. Each row is a string of ten
decisions, indexed by the dealer upcard in the order 2, 3, 4, 5, 6, 7, 8, 9,
10, A. Upper-case codes are H (hit), S (stand), D (double else hit), P (split)
and R (surrender).
"""

from __future__ import annotations

from typing import Literal

from .cards import Card, TEN_RANKS
from .hand import Hand
from .rules import Rules

Action = Literal["hit", "stand", "double", "split", "surrender"]

DEALER_COLUMNS: tuple[str, ...] = (
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "A",
)

HARD_TABLE: dict[int, str] = {
    5: "HHHHHHHHHH",
    6: "HHHHHHHHHH",
    7: "HHHHHHHHHH",
    8: "HHHHHHHHHH",
    9: "HDDDDHHHHH",
    10: "DDDDDDDDHH",
    11: "DDDDDDDDDD",
    12: "HHSSSHHHHH",
    13: "SSSSSHHHHH",
    14: "SSSSSHHHHH",
    15: "SSSSSHHHHH",
    16: "SSSSSHHHHH",
    17: "SSSSSSSSSS",
    18: "SSSSSSSSSS",
    19: "SSSSSSSSSS",
    20: "SSSSSSSSSS",
    21: "SSSSSSSSSS",
}

SOFT_TABLE: dict[int, str] = {
    12: "HHHHHHHHHH",
    13: "HHHDDHHHHH",
    14: "HHHDDHHHHH",
    15: "HHDDDHHHHH",
    16: "HHDDDHHHHH",
    17: "HDDDDHHHHH",
    18: "SddddSSHHH",
    19: "SSSSSSSSSS",
    20: "SSSSSSSSSS",
    21: "SSSSSSSSSS",
}

PAIR_TABLE: dict[str, str] = {
    "A": "PPPPPPPPPP",
    "10": "SSSSSSSSSS",
    "9": "PPPPPSPPSS",
    "8": "PPPPPPPPPP",
    "7": "PPPPPPHHHH",
    "6": "PPPPPHHHHH",
    "5": "DDDDDDDDHH",
    "4": "HHHPPHHHHH",
    "3": "PPPPPPHHHH",
    "2": "PPPPPPHHHH",
}

CODE_TO_ACTION: dict[str, Action] = {
    "H": "hit",
    "S": "stand",
    "D": "double",
    "d": "double",
    "P": "split",
    "R": "surrender",
}


def dealer_rank(dealer_upcard: Card | str) -> str:
    """Return the dealer column key for a card or a rank string."""
    if isinstance(dealer_upcard, Card):
        if dealer_upcard.value == 10:
            return "10"
        return dealer_upcard.rank
    rank = dealer_upcard.strip().upper()
    if rank in TEN_RANKS:
        return "10"
    if rank == "A" or rank.isdigit():
        return rank
    raise ValueError(f"Unknown dealer upcard: {dealer_upcard!r}")


def _column(dealer_upcard: Card | str) -> int:
    rank = dealer_rank(dealer_upcard)
    try:
        return DEALER_COLUMNS.index(rank)
    except ValueError as exc:
        raise ValueError(f"Dealer upcard {rank!r} is not in 2..A") from exc


def _should_surrender(hand: Hand, column: int) -> bool:
    """Return True for the standard late-surrender cells."""
    if hand.is_soft or len(hand.cards) != 2:
        return False
    total = hand.total
    if total == 16 and DEALER_COLUMNS[column] in {"9", "10", "A"}:
        return True
    if total == 15 and DEALER_COLUMNS[column] == "10":
        return True
    return False


def basic_strategy_action(
    hand: Hand,
    dealer_upcard: Card | str,
    rules: Rules | None = None,
    *,
    can_double: bool = True,
    can_split: bool = True,
    can_surrender: bool = True,
) -> Action:
    """Return the basic-strategy action for ``hand`` against ``dealer_upcard``.

    ``can_double``, ``can_split`` and ``can_surrender`` describe what the table
    actually permits on this decision. When the chart asks for an action that
    is not available the function falls back the same way a player would:
    double becomes hit, and an unavailable split falls through to the total
    based chart.
    """
    column = _column(dealer_upcard)
    rules = rules or Rules()

    if hand.is_pair and can_split:
        pair_code = PAIR_TABLE[hand.pair_rank or ""][column]
        if pair_code == "P":
            return "split"

    if can_surrender and rules.late_surrender and _should_surrender(hand, column):
        return "surrender"

    if hand.is_soft:
        code = SOFT_TABLE.get(hand.total, "SSSSSSSSSS")[column]
    else:
        default_row = "SSSSSSSSSS" if hand.total >= 17 else "HHHHHHHHHH"
        code = HARD_TABLE.get(hand.total, default_row)[column]

    if code == "D":
        return "double" if can_double else "hit"
    if code == "d":
        return "double" if can_double else "stand"
    if code == "P":  # pragma: no cover - pair table only emits P for pairs
        return "split" if can_split else "hit"
    return CODE_TO_ACTION[code]


def optimal_action(
    hand: Hand,
    dealer_upcard: Card | str,
    rules: Rules | None = None,
    *,
    can_double: bool = True,
    can_split: bool = True,
    can_surrender: bool = True,
) -> Action:
    """Alias for :func:`basic_strategy_action`, used by analytics code."""
    return basic_strategy_action(
        hand,
        dealer_upcard,
        rules,
        can_double=can_double,
        can_split=can_split,
        can_surrender=can_surrender,
    )


def strategy_rows() -> list[tuple[str, str]]:
    """Return chart rows as ``(label, decisions)`` pairs for display."""
    rows: list[tuple[str, str]] = []
    for label, total in (
        ("Hard 5-8", 8),
        ("Hard 9", 9),
        ("Hard 10", 10),
        ("Hard 11", 11),
    ):
        rows.append((label, HARD_TABLE[total]))
    for total in range(12, 18):
        rows.append((f"Hard {total}", HARD_TABLE[total]))
    for label, total in (
        ("Soft 13", 13),
        ("Soft 14", 14),
        ("Soft 15", 15),
        ("Soft 16", 16),
    ):
        rows.append((label, SOFT_TABLE[total]))
    rows.append(("Soft 17", SOFT_TABLE[17]))
    rows.append(("Soft 18", SOFT_TABLE[18]))
    for rank in ("A", "10", "9", "8", "7", "6", "5", "4", "3", "2"):
        rows.append((f"Pair {rank}", PAIR_TABLE[rank]))
    return rows
