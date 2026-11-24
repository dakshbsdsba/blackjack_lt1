"""Card and shoe primitives for the blackjack simulator.

The shoe behaves like a real casino dealing shoe: it holds a whole number of
52-card decks, deals from the top, and carries a cut card at a configurable
penetration. When the cut card is reached the caller shuffles, which also
empties the discard tray.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, Sequence

RANKS: tuple[str, ...] = (
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "J",
    "Q",
    "K",
    "A",
)
SUITS: tuple[str, ...] = (
    "\u2660",
    "\u2665",
    "\u2666",
    "\u2663",
)  # spades hearts diamonds clubs
RED_SUITS: frozenset[str] = frozenset({"\u2665", "\u2666"})
TEN_RANKS: frozenset[str] = frozenset({"10", "J", "Q", "K"})


@dataclass(frozen=True, slots=True)
class Card:
    """A single playing card.

    ``value`` is the blackjack counting value with an ace counted as eleven.
    ``base_value`` counts an ace as one, which is what :class:`Hand` uses when
    it decides whether the ace can still be soft.
    """

    rank: str
    suit: str

    def __post_init__(self) -> None:
        if self.rank not in RANKS:
            raise ValueError(f"Unknown rank: {self.rank!r}")
        if self.suit not in SUITS:
            raise ValueError(f"Unknown suit: {self.suit!r}")

    @property
    def value(self) -> int:
        """Return the card value with an ace counted as eleven."""
        if self.rank == "A":
            return 11
        if self.rank in TEN_RANKS:
            return 10
        return int(self.rank)

    @property
    def base_value(self) -> int:
        """Return the card value with an ace counted as one."""
        return 1 if self.rank == "A" else self.value

    @property
    def is_ace(self) -> bool:
        """Return True when the card is an ace."""
        return self.rank == "A"

    @property
    def is_ten(self) -> bool:
        """Return True for any ten-valued card."""
        return self.value == 10

    @property
    def hi_lo_value(self) -> int:
        """Return the Hi-Lo count tag for the card."""
        if self.rank in {"2", "3", "4", "5", "6"}:
            return 1
        if self.rank in {"7", "8", "9"}:
            return 0
        return -1

    @property
    def is_red(self) -> bool:
        """Return True for hearts and diamonds."""
        return self.suit in RED_SUITS

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"


def card_from_text(text: str) -> Card:
    """Build a card from a compact string such as ``"AS"`` or ``"10H"``.

    The final character is the suit, everything before it is the rank. Both
    the Unicode suit symbols and the letters S/H/D/C are accepted.
    """
    cleaned = text.strip().upper()
    if len(cleaned) < 2:
        raise ValueError(f"Card text too short: {text!r}")
    rank, suit_token = cleaned[:-1], cleaned[-1]
    suit_map = {
        "S": "\u2660",
        "H": "\u2665",
        "D": "\u2666",
        "C": "\u2663",
        "\u2660": "\u2660",
        "\u2665": "\u2665",
        "\u2666": "\u2666",
        "\u2663": "\u2663",
    }
    if suit_token not in suit_map:
        raise ValueError(f"Unknown suit token: {suit_token!r}")
    return Card(rank=rank, suit=suit_map[suit_token])


def cards_from_text(text: str) -> list[Card]:
    """Build a list of cards from a whitespace or comma separated string."""
    tokens = text.replace(",", " ").split()
    return [card_from_text(token) for token in tokens]


class Shoe:
    """A multi-deck dealing shoe with a cut card and a discard tray."""

    def __init__(
        self,
        num_decks: int = 6,
        penetration: float = 0.75,
        *,
        seed: int | None = None,
        rng: random.Random | None = None,
    ) -> None:
        if num_decks < 1:
            raise ValueError("num_decks must be at least 1")
        if not 0.0 < penetration <= 1.0:
            raise ValueError("penetration must be in (0, 1]")
        self.num_decks = num_decks
        self.penetration = penetration
        self._rng = rng if rng is not None else random.Random(seed)
        self._cards: list[Card] = []
        self._dealt: list[Card] = []
        self.shuffle_count = 0
        self.shuffle()

    # ------------------------------------------------------------------
    # Deck lifecycle
    # ------------------------------------------------------------------
    def shuffle(self) -> None:
        """Rebuild the full shoe, shuffle it, and clear the discard tray."""
        self._cards = [
            Card(rank=rank, suit=suit)
            for _ in range(self.num_decks)
            for suit in SUITS
            for rank in RANKS
        ]
        self._rng.shuffle(self._cards)
        self._dealt = []
        self.shuffle_count += 1

    def shuffle_if_needed(self) -> bool:
        """Shuffle when the cut card has been reached. Return True if shuffled."""
        if self.needs_shuffle:
            self.shuffle()
            return True
        return False

    def stack(self, cards: Iterable[Card | str]) -> None:
        """Replace the shoe with a known card order.

        This is a teaching and testing helper. The cards are listed in the
        order they should be dealt, and the discard tray is cleared.
        """
        parsed = [
            card_from_text(card) if isinstance(card, str) else card for card in cards
        ]
        self._cards = list(reversed(parsed))
        self._dealt = []

    # ------------------------------------------------------------------
    # Dealing
    # ------------------------------------------------------------------
    def draw_one(self) -> Card:
        """Remove and return the top card of the shoe."""
        if not self._cards:
            raise ValueError("Cannot draw from an empty shoe")
        card = self._cards.pop()
        self._dealt.append(card)
        return card

    def draw(self, n: int = 1) -> list[Card]:
        """Remove and return ``n`` cards from the top of the shoe."""
        if n < 0:
            raise ValueError("n must not be negative")
        if n > len(self._cards):
            raise ValueError(
                f"Cannot draw {n} cards; only {len(self._cards)} remaining"
            )
        drawn = [self._cards.pop() for _ in range(n)]
        self._dealt.extend(drawn)
        return drawn

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    @property
    def cards_remaining(self) -> int:
        """Number of cards still in the shoe."""
        return len(self._cards)

    @property
    def total_cards(self) -> int:
        """Number of cards in a full shoe of this many decks."""
        return 52 * self.num_decks

    @property
    def cards_dealt(self) -> int:
        """Number of cards dealt since the last shuffle."""
        return len(self._dealt)

    @property
    def discard_tray(self) -> int:
        """Number of cards sitting in the discard tray."""
        return len(self._dealt)

    @property
    def decks_remaining(self) -> float:
        """Fractional number of decks left in the shoe."""
        return len(self._cards) / 52.0

    @property
    def true_count_divisor(self) -> float:
        """Decks remaining, floored at half a deck to keep counts finite."""
        return max(0.5, self.decks_remaining)

    @property
    def cut_card_index(self) -> int:
        """Number of cards that must be dealt before the cut card is reached."""
        return int(self.total_cards * self.penetration)

    @property
    def penetration_actual(self) -> float:
        """Fraction of the shoe already dealt."""
        return len(self._dealt) / self.total_cards

    @property
    def needs_shuffle(self) -> bool:
        """Return True when the cut card has been reached."""
        return len(self._dealt) >= self.cut_card_index or not self._cards

    @property
    def dealt_cards(self) -> Sequence[Card]:
        """Cards dealt since the last shuffle, in dealing order."""
        return tuple(self._dealt)

    def remaining_counts(self) -> dict[str, int]:
        """Count the cards still in the shoe, keyed by rank."""
        counts = {rank: 0 for rank in RANKS}
        for card in self._cards:
            counts[card.rank] += 1
        return counts

    def __len__(self) -> int:
        return len(self._cards)

    def __repr__(self) -> str:
        return (
            f"Shoe(num_decks={self.num_decks}, remaining={len(self._cards)}, "
            f"dealt={len(self._dealt)})"
        )
