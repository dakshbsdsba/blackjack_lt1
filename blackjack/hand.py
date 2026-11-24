"""Hand evaluation for blackjack, including soft totals and split state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .cards import Card


@dataclass
class Hand:
    """A player hand.

    A hand tracks its own bet so split hands can carry independent wagers and
    payouts. ``start_total`` is filled in by the engine when the hand first
    becomes playable, which lets the analytics layer group outcomes by the
    total the player started from.
    """

    cards: list[Card] = field(default_factory=list)
    bet: float = 0.0
    is_split_hand: bool = False
    from_split_aces: bool = False
    is_doubled: bool = False
    stood: bool = False
    surrendered: bool = False
    start_total: int = 0

    # ------------------------------------------------------------------
    # Cards and totals
    # ------------------------------------------------------------------
    def add(self, card: Card) -> None:
        """Append a card to the hand."""
        self.cards.append(card)

    @property
    def total(self) -> int:
        """Best total: aces count eleven while that does not bust the hand."""
        total = sum(card.base_value for card in self.cards)
        if any(card.is_ace for card in self.cards) and total + 10 <= 21:
            return total + 10
        return total

    @property
    def hard_total(self) -> int:
        """Total with every ace counted as one."""
        return sum(card.base_value for card in self.cards)

    @property
    def is_soft(self) -> bool:
        """Return True when an ace is currently counted as eleven."""
        return self.total != self.hard_total

    @property
    def num_aces(self) -> int:
        """Number of aces in the hand."""
        return sum(1 for card in self.cards if card.is_ace)

    @property
    def is_bust(self) -> bool:
        """Return True when the hand is over 21."""
        return self.total > 21

    @property
    def is_blackjack(self) -> bool:
        """Return True for a natural: two cards totalling 21 on the first hand."""
        return len(self.cards) == 2 and self.total == 21 and not self.is_split_hand

    @property
    def is_21(self) -> bool:
        """Return True for any hand totalling 21, natural or not."""
        return self.total == 21

    @property
    def is_finished(self) -> bool:
        """Return True when the hand can no longer be acted on."""
        return self.stood or self.is_bust or self.surrendered

    @property
    def can_hit(self) -> bool:
        """Return True when hitting is still legal."""
        return len(self.cards) >= 2 and not self.is_finished

    @property
    def is_pair(self) -> bool:
        """Return True when the first two cards form a splittable pair."""
        if len(self.cards) != 2:
            return False
        return self.pair_rank is not None

    @property
    def pair_rank(self) -> str | None:
        """Return a normalised pair key: ``A``, ``10`` or the rank itself."""
        if len(self.cards) != 2:
            return None
        first, second = self.cards
        if first.value == 10 and second.value == 10:
            return "10"
        if first.rank == second.rank:
            return first.rank
        return None

    @property
    def is_ten_pair(self) -> bool:
        """Return True for a pair of ten-valued cards."""
        return self.pair_rank == "10"

    @property
    def display(self) -> str:
        """Compact human readable form, for example ``A♠ 7♥ (18 soft)``."""
        cards = " ".join(str(card) for card in self.cards)
        soft = " soft" if self.is_soft else ""
        return f"{cards} ({self.total}{soft})"

    def copy(self) -> "Hand":
        """Return a deep-enough copy of the hand."""
        return Hand(
            cards=list(self.cards),
            bet=self.bet,
            is_split_hand=self.is_split_hand,
            from_split_aces=self.from_split_aces,
            is_doubled=self.is_doubled,
            stood=self.stood,
            surrendered=self.surrendered,
            start_total=self.start_total,
        )

    def __len__(self) -> int:
        return len(self.cards)

    def __repr__(self) -> str:
        return f"Hand({self.display}, bet={self.bet})"


def hand_from_cards(cards: Sequence[Card | str], bet: float = 0.0) -> Hand:
    """Build a hand from cards or compact strings such as ``"AS 7H"``."""
    from .cards import card_from_text

    hand = Hand(bet=bet)
    for card in cards:
        hand.add(card_from_text(card) if isinstance(card, str) else card)
    return hand
