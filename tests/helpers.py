"""Shared test helpers for scripted deals."""

from __future__ import annotations

from typing import Iterable

from blackjack import BlackjackGame
from blackjack.cards import Card, card_from_text
from blackjack.engine import GameState


def rig_shoe(game: BlackjackGame, cards: Iterable[str | Card]) -> None:
    """Stack the shoe so the next cards are dealt in the given order."""
    parsed = [card_from_text(card) if isinstance(card, str) else card for card in cards]
    game.shoe._cards = list(reversed(parsed))
    game.shoe._dealt = []
    game.shoe.shuffle_count = max(1, game.shoe.shuffle_count)
    game.counter.reset()
    game._count_index = 0


def start(game: BlackjackGame, cards: Iterable[str | Card], bet: float = 25.0) -> None:
    """Stack the shoe, start a hand, and decline insurance if offered."""
    rig_shoe(game, cards)
    game.start_hand(bet)
    if game.state is GameState.INSURANCE:
        game.take_insurance(False)
