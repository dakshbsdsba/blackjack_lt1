"""Autonomous players for simulation and the bot leaderboard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .hand import Hand
from .rules import Rules
from .strategy import Action, basic_strategy_action


@dataclass(frozen=True)
class BetContext:
    """Everything a betting system is allowed to know before a hand."""

    bankroll: float
    true_count: float
    running_count: int
    hands_played: int
    last_net: float
    rules: Rules


class Bot:
    """Base class: flat betting plus perfect basic strategy."""

    name = "Bot"

    def __init__(
        self,
        name: str | None = None,
        unit: float = 10.0,
    ) -> None:
        self.name = name or self.name
        self.unit = float(unit)

    def reset(self) -> None:
        """Reset any internal progression state."""

    def bet(self, context: BetContext) -> float:
        """Return the wager for the next hand."""
        return self._clamp(self.unit, context)

    def action(
        self,
        hand: Hand,
        dealer_upcard: object,
        rules: Rules,
        available: Sequence[str],
    ) -> Action:
        """Choose a playing action."""
        return basic_strategy_action(
            hand,
            dealer_upcard,  # type: ignore[arg-type]
            rules,
            can_double="double" in available,
            can_split="split" in available,
            can_surrender="surrender" in available,
        )

    def wants_insurance(self, true_count: float) -> bool:
        """Basic strategy never takes insurance."""
        return False

    def on_result(self, net: float) -> None:
        """Observe the net result of the previous round."""

    def _clamp(self, amount: float, context: BetContext) -> float:
        """Clamp a wager to the table limits and the remaining bankroll."""
        rules = context.rules
        amount = max(amount, rules.min_bet)
        amount = min(amount, rules.max_bet, context.bankroll)
        if amount < rules.min_bet:
            return 0.0
        return round(amount, 2)


class FlatBetBot(Bot):
    """Always bets the same unit. The control group for every comparison."""

    name = "Flat bettor"


class MartingaleBot(Bot):
    """Doubles the bet after a loss and resets after a win or push."""

    name = "Martingale"

    def __init__(
        self,
        name: str | None = None,
        unit: float = 10.0,
        max_multiplier: float = 8.0,
    ) -> None:
        super().__init__(name=name, unit=unit)
        self.max_multiplier = max(1.0, max_multiplier)
        self.loss_streak = 0

    def reset(self) -> None:
        """Clear the progression."""
        self.loss_streak = 0

    def bet(self, context: BetContext) -> float:
        """Bet unit times two to the loss streak, capped by max_multiplier."""
        multiplier = min(2.0**self.loss_streak, self.max_multiplier)
        return self._clamp(self.unit * multiplier, context)

    def on_result(self, net: float) -> None:
        """Advance the progression after a loss, reset otherwise."""
        if net < 0:
            self.loss_streak += 1
        else:
            self.loss_streak = 0


class HiLoSpreadBot(Bot):
    """Raises the bet with the true count using a simple unit spread."""

    name = "Hi-Lo spread"

    def __init__(
        self,
        name: str | None = None,
        unit: float = 10.0,
        spread: int = 8,
        min_true_count: float = 1.0,
        insurance_true_count: float = 3.0,
    ) -> None:
        super().__init__(name=name, unit=unit)
        self.spread = max(1, spread)
        self.min_true_count = min_true_count
        self.insurance_true_count = insurance_true_count

    def bet(self, context: BetContext) -> float:
        """Bet one unit below the threshold, then scale with the true count."""
        if context.true_count < self.min_true_count:
            units = 1
        else:
            units = min(self.spread, max(1, int(round(context.true_count))))
        return self._clamp(self.unit * units, context)

    def wants_insurance(self, true_count: float) -> bool:
        """Take insurance once the count is high enough."""
        return true_count >= self.insurance_true_count


class KellyBot(Bot):
    """Sizes bets with a fractional Kelly stake driven by the true count."""

    name = "Fractional Kelly"

    def __init__(
        self,
        name: str | None = None,
        unit: float = 10.0,
        fraction: float = 0.5,
        edge_per_true_count: float = 0.005,
        variance: float = 1.3,
        max_fraction: float = 0.05,
        insurance_true_count: float = 3.0,
    ) -> None:
        super().__init__(name=name, unit=unit)
        self.fraction = fraction
        self.edge_per_true_count = edge_per_true_count
        self.variance = variance
        self.max_fraction = max_fraction
        self.insurance_true_count = insurance_true_count

    def bet(self, context: BetContext) -> float:
        """Bet a fraction of Kelly, floored at one unit and capped."""
        edge = max(0.0, self.edge_per_true_count * context.true_count)
        kelly = context.bankroll * edge / self.variance
        stake = kelly * self.fraction
        cap = context.bankroll * self.max_fraction
        amount = min(max(stake, self.unit), cap)
        return self._clamp(amount, context)

    def wants_insurance(self, true_count: float) -> bool:
        """Take insurance once the count is high enough."""
        return true_count >= self.insurance_true_count


class BasicStrategyBot(FlatBetBot):
    """A flat bettor whose decisions are pure basic strategy."""

    name = "Basic strategy"
