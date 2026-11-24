"""Session analytics for blackjack play and simulation.

Everything here is derived from settled hand results, so the numbers shown in
the notebook, the CLI dashboard and the Monte Carlo report all come from the
same definitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .engine import Decision, HandResult, Outcome


def bankroll_series(
    nets: Sequence[float], starting_bankroll: float = 0.0
) -> list[float]:
    """Build a bankroll curve from per-hand net results."""
    curve = [float(starting_bankroll)]
    current = float(starting_bankroll)
    for net in nets:
        current += float(net)
        curve.append(round(current, 2))
    return curve


def drawdown_series(
    nets: Sequence[float], starting_bankroll: float = 0.0
) -> list[float]:
    """Build an underwater curve: distance below the running peak."""
    peak = float(starting_bankroll)
    current = float(starting_bankroll)
    curve = [0.0]
    for net in nets:
        current += float(net)
        peak = max(peak, current)
        curve.append(round(peak - current, 2))
    return curve


def _streaks(outcomes: Sequence[str]) -> tuple[int, int]:
    """Return the longest win and loss streaks, with pushes breaking runs."""
    best_win = best_loss = 0
    current_win = current_loss = 0
    for outcome in outcomes:
        if outcome in (Outcome.WIN.value, Outcome.BLACKJACK.value):
            current_win += 1
            current_loss = 0
            best_win = max(best_win, current_win)
        elif outcome == Outcome.LOSS.value:
            current_loss += 1
            current_win = 0
            best_loss = max(best_loss, current_loss)
        else:
            current_win = current_loss = 0
    return best_win, best_loss


@dataclass(frozen=True)
class Analytics:
    """Aggregate performance for a session or a simulation run."""

    hands: int
    wagered: float
    net: float
    house_edge: float
    wins: int
    losses: int
    pushes: int
    blackjacks: int
    surrenders: int
    win_rate: float
    decisive_win_rate: float
    longest_win_streak: int
    longest_loss_streak: int
    max_drawdown: float
    peak_bankroll: float
    final_bankroll: float
    starting_bankroll: float
    strategy_decisions: int
    strategy_correct: int
    adherence: float
    avg_bet: float
    roi: float

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------
    @classmethod
    def from_arrays(
        cls,
        nets: Sequence[float],
        outcomes: Sequence[str | Outcome],
        bets: Sequence[float],
        *,
        starting_bankroll: float = 0.0,
        decisions_correct: int = 0,
        decisions_total: int = 0,
    ) -> "Analytics":
        """Build analytics from parallel result arrays."""
        if not (len(nets) == len(outcomes) == len(bets)):
            raise ValueError("nets, outcomes and bets must have the same length")
        hands = len(nets)
        outcome_values = [
            item.value if isinstance(item, Outcome) else str(item) for item in outcomes
        ]
        net = round(sum(float(value) for value in nets), 2)
        wagered = round(sum(float(value) for value in bets), 2)
        wins = sum(1 for item in outcome_values if item in ("win", "blackjack"))
        losses = sum(1 for item in outcome_values if item == "loss")
        pushes = sum(1 for item in outcome_values if item == "push")
        blackjacks = outcome_values.count("blackjack")
        surrenders = outcome_values.count("surrender")
        decisive = wins + losses
        win_streak, loss_streak = _streaks(outcome_values)

        curve = bankroll_series(nets, starting_bankroll)
        peak = max(curve) if curve else starting_bankroll
        underwater = drawdown_series(nets, starting_bankroll)
        max_drawdown = max(underwater) if underwater else 0.0

        adherence = decisions_correct / decisions_total if decisions_total else 0.0
        return cls(
            hands=hands,
            wagered=wagered,
            net=net,
            house_edge=(-net / wagered) if wagered else 0.0,
            wins=wins,
            losses=losses,
            pushes=pushes,
            blackjacks=blackjacks,
            surrenders=surrenders,
            win_rate=(wins / hands) if hands else 0.0,
            decisive_win_rate=(wins / decisive) if decisive else 0.0,
            longest_win_streak=win_streak,
            longest_loss_streak=loss_streak,
            max_drawdown=round(max_drawdown, 2),
            peak_bankroll=round(peak, 2),
            final_bankroll=round(starting_bankroll + net, 2),
            starting_bankroll=round(starting_bankroll, 2),
            strategy_decisions=decisions_total,
            strategy_correct=decisions_correct,
            adherence=adherence,
            avg_bet=round(wagered / hands, 2) if hands else 0.0,
            roi=(net / starting_bankroll) if starting_bankroll else 0.0,
        )

    @classmethod
    def from_results(
        cls,
        results: Sequence[HandResult],
        *,
        starting_bankroll: float = 0.0,
        decisions: Sequence[Decision] = (),
    ) -> "Analytics":
        """Build analytics from settled :class:`HandResult` objects."""
        return cls.from_arrays(
            [result.net for result in results],
            [result.outcome for result in results],
            [result.wagered for result in results],
            starting_bankroll=starting_bankroll,
            decisions_correct=sum(1 for decision in decisions if decision.correct),
            decisions_total=len(decisions),
        )

    @classmethod
    def combine(cls, sessions: Iterable["Analytics"]) -> "Analytics":
        """Merge several independent sessions into one summary.

        Streaks and drawdowns are not additive across sessions, so the merged
        value takes the worst (largest) figure from the inputs. Money and
        decision counts add normally.
        """
        items = list(sessions)
        hands = sum(item.hands for item in items)
        wagered = round(sum(item.wagered for item in items), 2)
        net = round(sum(item.net for item in items), 2)
        wins = sum(item.wins for item in items)
        losses = sum(item.losses for item in items)
        starting = round(sum(item.starting_bankroll for item in items), 2)
        decisions = sum(item.strategy_decisions for item in items)
        correct = sum(item.strategy_correct for item in items)
        return cls(
            hands=hands,
            wagered=wagered,
            net=net,
            house_edge=(-net / wagered) if wagered else 0.0,
            wins=wins,
            losses=losses,
            pushes=sum(item.pushes for item in items),
            blackjacks=sum(item.blackjacks for item in items),
            surrenders=sum(item.surrenders for item in items),
            win_rate=(wins / hands) if hands else 0.0,
            decisive_win_rate=(wins / (wins + losses)) if wins + losses else 0.0,
            longest_win_streak=max(
                (item.longest_win_streak for item in items), default=0
            ),
            longest_loss_streak=max(
                (item.longest_loss_streak for item in items), default=0
            ),
            max_drawdown=max((item.max_drawdown for item in items), default=0.0),
            peak_bankroll=max((item.peak_bankroll for item in items), default=0.0),
            final_bankroll=round(sum(item.final_bankroll for item in items), 2),
            starting_bankroll=starting,
            strategy_decisions=decisions,
            strategy_correct=correct,
            adherence=(correct / decisions) if decisions else 0.0,
            avg_bet=(wagered / hands) if hands else 0.0,
            roi=(net / starting) if starting else 0.0,
        )

    # ------------------------------------------------------------------
    # Presentation
    # ------------------------------------------------------------------
    @property
    def house_edge_percent(self) -> float:
        """House edge as a percentage of total money wagered."""
        return self.house_edge * 100.0

    @property
    def adherence_percent(self) -> float:
        """Strategy adherence as a percentage."""
        return self.adherence * 100.0

    def as_dict(self) -> dict[str, float | int]:
        """Return the summary as a plain dictionary."""
        return {
            "hands": self.hands,
            "wagered": self.wagered,
            "net": self.net,
            "avg_bet": self.avg_bet,
            "roi_pct": round(self.roi * 100.0, 2),
            "house_edge_pct": round(self.house_edge_percent, 4),
            "wins": self.wins,
            "losses": self.losses,
            "pushes": self.pushes,
            "blackjacks": self.blackjacks,
            "surrenders": self.surrenders,
            "win_rate_pct": round(self.win_rate * 100.0, 2),
            "longest_win_streak": self.longest_win_streak,
            "longest_loss_streak": self.longest_loss_streak,
            "max_drawdown": self.max_drawdown,
            "final_bankroll": self.final_bankroll,
            "strategy_decisions": self.strategy_decisions,
            "adherence_pct": round(self.adherence_percent, 2),
        }


def outcome_counts(outcomes: Sequence[str | Outcome]) -> dict[str, int]:
    """Count outcomes by category, always including every category."""
    counts = {item.value: 0 for item in Outcome}
    for outcome in outcomes:
        key = outcome.value if isinstance(outcome, Outcome) else str(outcome)
        counts[key] = counts.get(key, 0) + 1
    return counts


@dataclass(frozen=True)
class CountBucket:
    """Aggregated performance for a band of true counts."""

    label: str
    hands: int
    wagered: float
    net: float
    edge: float
    win_rate: float


def bucket_by_true_count(
    true_counts: Sequence[float],
    nets: Sequence[float],
    bets: Sequence[float],
    outcomes: Sequence[str | Outcome],
    *,
    low: int = -5,
    high: int = 6,
) -> list[CountBucket]:
    """Group hands into true-count buckets for profitability analysis."""
    if not (len(true_counts) == len(nets) == len(bets) == len(outcomes)):
        raise ValueError("all inputs must have the same length")
    buckets: dict[int, list[int]] = {value: [] for value in range(low, high + 1)}
    for index, count in enumerate(true_counts):
        key = int(round(count))
        key = max(low, min(high, key))
        buckets[key].append(index)

    results: list[CountBucket] = []
    for key in range(low, high + 1):
        indices = buckets[key]
        if not indices:
            continue
        wagered = sum(float(bets[index]) for index in indices)
        net = sum(float(nets[index]) for index in indices)
        wins = sum(
            1
            for index in indices
            if str(
                outcomes[index].value
                if isinstance(outcomes[index], Outcome)
                else outcomes[index]
            )
            in ("win", "blackjack")
        )
        if key == low:
            label = f"{low}"
        elif key == high:
            label = f"+{high}+"
        elif key == 0:
            label = "0"
        else:
            label = f"{key:+d}"
        results.append(
            CountBucket(
                label=label,
                hands=len(indices),
                wagered=round(wagered, 2),
                net=round(net, 2),
                edge=(-net / wagered) if wagered else 0.0,
                win_rate=wins / len(indices),
            )
        )
    return results
