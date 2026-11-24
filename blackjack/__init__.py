"""Blackjack simulator package.

Public entry points are grouped here so the notebook and tests can import a
small, stable surface instead of reaching into individual modules.
"""

from __future__ import annotations

from .analytics import Analytics, bankroll_series, drawdown_series, outcome_counts
from .bots import (
    BasicStrategyBot,
    BetContext,
    Bot,
    FlatBetBot,
    HiLoSpreadBot,
    KellyBot,
    MartingaleBot,
)
from .cards import Card, Shoe, card_from_text, cards_from_text
from .counting import HiLoCounter, count_cards
from .engine import (
    BlackjackGame,
    Decision,
    GameState,
    HandResult,
    Outcome,
    basic_strategy_policy,
)
from .hand import Hand, hand_from_cards
from .rules import Rules
from .simulation import (
    LeaderboardEntry,
    SimResult,
    compare_bots,
    run_bot,
    run_competition,
    run_simulation,
)
from .strategy import Action, basic_strategy_action, optimal_action, strategy_rows

__version__ = "1.0.0"

__all__ = [
    "Action",
    "Analytics",
    "BasicStrategyBot",
    "BetContext",
    "BlackjackGame",
    "Bot",
    "Card",
    "Decision",
    "FlatBetBot",
    "GameState",
    "Hand",
    "HandResult",
    "HiLoCounter",
    "HiLoSpreadBot",
    "KellyBot",
    "LeaderboardEntry",
    "MartingaleBot",
    "Outcome",
    "Rules",
    "Shoe",
    "SimResult",
    "bankroll_series",
    "basic_strategy_action",
    "basic_strategy_policy",
    "card_from_text",
    "cards_from_text",
    "compare_bots",
    "count_cards",
    "drawdown_series",
    "hand_from_cards",
    "optimal_action",
    "outcome_counts",
    "run_bot",
    "run_competition",
    "run_simulation",
    "strategy_rows",
]
