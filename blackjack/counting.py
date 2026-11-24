"""Hi-Lo card counting utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .cards import Card
from .hand import Hand


def hi_lo_value(card: Card) -> int:
    """Return the Hi-Lo tag for one card: low cards +1, high cards -1."""
    return card.hi_lo_value


def count_cards(cards: Iterable[Card]) -> int:
    """Return the Hi-Lo running count for a sequence of cards."""
    return sum(card.hi_lo_value for card in cards)


@dataclass
class HiLoCounter:
    """Tracks a running Hi-Lo count and converts it to a true count.

    The counter only observes cards. The caller decides when to reset it,
    which should happen on every shuffle.
    """

    num_decks: int = 6
    running_count: int = 0
    cards_seen: int = 0
    _seen_by_rank: dict[str, int] = field(default_factory=dict, repr=False)

    def observe(self, card: Card) -> int:
        """Add one card to the count and return the new running count."""
        self.running_count += card.hi_lo_value
        self.cards_seen += 1
        self._seen_by_rank[card.rank] = self._seen_by_rank.get(card.rank, 0) + 1
        return self.running_count

    def observe_many(self, cards: Iterable[Card]) -> int:
        """Add several cards to the count and return the new running count."""
        for card in cards:
            self.observe(card)
        return self.running_count

    def reset(self) -> None:
        """Clear the count, for example after a shuffle."""
        self.running_count = 0
        self.cards_seen = 0
        self._seen_by_rank.clear()

    @property
    def decks_seen(self) -> float:
        """Number of decks observed since the last reset."""
        return self.cards_seen / 52.0

    def true_count(self, decks_remaining: float) -> float:
        """Return running count divided by decks remaining.

        The divisor is floored at half a deck so the value stays finite when
        the shoe is nearly empty.
        """
        return self.running_count / max(0.5, decks_remaining)

    def true_count_for_shoe(self, shoe: object) -> float:
        """Return the true count using a shoe's remaining decks."""
        decks = getattr(shoe, "decks_remaining")
        return self.true_count(float(decks))

    def remaining_estimate(self, num_decks: int | None = None) -> dict[str, int]:
        """Estimate the remaining rank composition from the cards seen."""
        decks = self.num_decks if num_decks is None else num_decks
        per_deck = {
            "A": 4,
            "2": 4,
            "3": 4,
            "4": 4,
            "5": 4,
            "6": 4,
            "7": 4,
            "8": 4,
            "9": 4,
            "10": 16,
        }
        remaining = {rank: per_deck[rank] * decks for rank in per_deck}
        for rank, seen in self._seen_by_rank.items():
            if rank in remaining:
                remaining[rank] = max(0, remaining[rank] - seen)
        return remaining

    def snapshot(self, decks_remaining: float) -> dict[str, float | int]:
        """Return a small dictionary suitable for a UI footer."""
        return {
            "running_count": self.running_count,
            "true_count": round(self.true_count(decks_remaining), 2),
            "cards_seen": self.cards_seen,
        }


def count_hand(hand: Hand) -> int:
    """Return the Hi-Lo count contribution of every card in a hand."""
    return count_cards(hand.cards)
