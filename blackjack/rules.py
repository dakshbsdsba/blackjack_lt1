"""Table rules for the blackjack simulator."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rules:
    """A complete, validated set of table rules.

    Defaults describe a common six-deck American game: dealer stands on all
    seventeens, blackjack pays 3:2, double after split is allowed, up to four
    hands from splits, late surrender available, insurance offered.
    """

    num_decks: int = 6
    penetration: float = 0.75
    dealer_stands_soft_17: bool = True
    blackjack_payout: float = 1.5
    double_after_split: bool = True
    max_split_hands: int = 4
    resplit_aces: bool = False
    hit_split_aces: bool = False
    late_surrender: bool = True
    insurance_enabled: bool = True
    min_bet: float = 1.0
    max_bet: float = 10_000.0

    def __post_init__(self) -> None:
        if not 1 <= self.num_decks <= 8:
            raise ValueError("num_decks must be between 1 and 8")
        if not 0.0 < self.penetration <= 1.0:
            raise ValueError("penetration must be in (0, 1]")
        if not 0.0 < self.blackjack_payout <= 2.0:
            raise ValueError("blackjack_payout must be in (0, 2]")
        if not 2 <= self.max_split_hands <= 8:
            raise ValueError("max_split_hands must be between 2 and 8")
        if self.min_bet <= 0:
            raise ValueError("min_bet must be positive")
        if self.max_bet < self.min_bet:
            raise ValueError("max_bet must be at least min_bet")

    @property
    def dealer_hits_soft_17(self) -> bool:
        """Return True when the dealer hits soft seventeen."""
        return not self.dealer_stands_soft_17

    def describe(self) -> str:
        """Return a short human readable summary of the rules."""
        s17 = "S17" if self.dealer_stands_soft_17 else "H17"
        das = "DAS" if self.double_after_split else "no DAS"
        surrender = "late surrender" if self.late_surrender else "no surrender"
        return (
            f"{self.num_decks} decks, {s17}, {das}, "
            f"{self.blackjack_payout:g}:1 blackjack, {surrender}"
        )
