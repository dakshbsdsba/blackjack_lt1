"""Monte Carlo simulation and the bot leaderboard."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Sequence

import numpy as np

from .analytics import Analytics
from .bots import BetContext, Bot, FlatBetBot
from .cards import Shoe
from .engine import (
    BlackjackGame,
    Decision,
    HandResult,
    InsurancePolicy,
    Policy,
    basic_strategy_policy,
)
from .rules import Rules


@dataclass
class SimResult:
    """The per-hand record of a simulation run."""

    label: str
    starting_bankroll: float
    nets: np.ndarray
    bets: np.ndarray
    outcomes: list[str]
    true_counts: np.ndarray
    dealer_upcards: list[str]
    start_totals: np.ndarray
    decisions: list[Decision] = field(default_factory=list)
    rounds: int = 0

    @property
    def hands(self) -> int:
        """Number of settled hands, including split hands."""
        return int(len(self.nets))

    @property
    def bankroll(self) -> np.ndarray:
        """Bankroll path including the starting stake at index zero."""
        if not len(self.nets):
            return np.array([self.starting_bankroll], dtype=float)
        return np.concatenate(
            [
                np.array([self.starting_bankroll], dtype=float),
                self.starting_bankroll + np.cumsum(self.nets),
            ]
        )

    def analytics(self) -> Analytics:
        """Return the aggregate metrics for the run."""
        return Analytics.from_arrays(
            self.nets.tolist(),
            self.outcomes,
            self.bets.tolist(),
            starting_bankroll=self.starting_bankroll,
            decisions_correct=sum(1 for d in self.decisions if d.correct),
            decisions_total=len(self.decisions),
        )

    def tail(self, count: int = 10) -> list[dict[str, object]]:
        """Return the last few hands as dictionaries, for a quick inspection."""
        rows: list[dict[str, object]] = []
        for index in range(max(0, self.hands - count), self.hands):
            rows.append(
                {
                    "hand": index + 1,
                    "bet": float(self.bets[index]),
                    "net": float(self.nets[index]),
                    "outcome": self.outcomes[index],
                    "true_count": round(float(self.true_counts[index]), 2),
                }
            )
        return rows


@dataclass(frozen=True)
class LeaderboardEntry:
    """One row of the bot leaderboard."""

    rank: int
    name: str
    final_bankroll: float
    net: float
    roi: float
    hands: int
    wins: int
    losses: int
    pushes: int
    max_drawdown: float
    edge: float
    adherence: float


def _empty_result(label: str, starting_bankroll: float, rounds: int = 0) -> SimResult:
    """Build an empty result with correctly typed arrays."""
    return SimResult(
        label=label,
        starting_bankroll=starting_bankroll,
        nets=np.array([], dtype=float),
        bets=np.array([], dtype=float),
        outcomes=[],
        true_counts=np.array([], dtype=float),
        dealer_upcards=[],
        start_totals=np.array([], dtype=int),
        decisions=[],
        rounds=rounds,
    )


def _append_round(
    nets: list[float],
    bets: list[float],
    outcomes: list[str],
    true_counts: list[float],
    dealer_upcards: list[str],
    start_totals: list[int],
    results: Sequence[HandResult],
    true_count: float,
) -> None:
    """Append every settled hand from one round to the running arrays."""
    for result in results:
        nets.append(float(result.net))
        bets.append(float(result.wagered))
        outcomes.append(result.outcome.value)
        true_counts.append(float(true_count))
        dealer_upcards.append(result.dealer_upcard)
        start_totals.append(int(result.start_total))


def _make_result(
    label: str,
    starting_bankroll: float,
    nets: list[float],
    bets: list[float],
    outcomes: list[str],
    true_counts: list[float],
    dealer_upcards: list[str],
    start_totals: list[int],
    decisions: list[Decision],
    rounds: int,
) -> SimResult:
    """Convert accumulated Python lists into a :class:`SimResult`."""
    return SimResult(
        label=label,
        starting_bankroll=starting_bankroll,
        nets=np.asarray(nets, dtype=float),
        bets=np.asarray(bets, dtype=float),
        outcomes=outcomes,
        true_counts=np.asarray(true_counts, dtype=float),
        dealer_upcards=dealer_upcards,
        start_totals=np.asarray(start_totals, dtype=int),
        decisions=decisions,
        rounds=rounds,
    )


def _insurance_policy(bot: Bot, true_count: float) -> InsurancePolicy | None:
    """Return an insurance policy that only bets when the stake is affordable."""
    if not bot.wants_insurance(true_count):
        return None

    def policy(game: BlackjackGame) -> bool:
        if not game.hands:
            return False
        return game.bankroll + 1e-9 >= game.hands[0].bet / 2

    return policy


def run_bot(
    bot: Bot,
    rounds: int,
    *,
    starting_bankroll: float = 10_000.0,
    rules: Rules | None = None,
    seed: int = 42,
    track_decisions: bool = True,
) -> SimResult:
    """Run one bot for ``rounds`` rounds and return its hand-by-hand record."""
    if rounds <= 0:
        raise ValueError("rounds must be positive")
    rules = rules or Rules()
    game = BlackjackGame(
        rules,
        starting_bankroll,
        seed=seed,
        log_decisions=track_decisions,
    )
    bot.reset()

    nets: list[float] = []
    bets: list[float] = []
    outcomes: list[str] = []
    true_counts: list[float] = []
    dealer_upcards: list[str] = []
    start_totals: list[int] = []
    decisions: list[Decision] = []
    last_net = 0.0
    completed = 0

    for _ in range(rounds):
        if game.bankroll + 1e-9 < rules.min_bet:
            break
        true_count = game.true_count
        context = BetContext(
            bankroll=game.bankroll,
            true_count=true_count,
            running_count=game.running_count,
            hands_played=completed,
            last_net=last_net,
            rules=rules,
        )
        wager = bot.bet(context)
        if wager + 1e-9 < rules.min_bet:
            break
        wager = min(wager, game.bankroll, rules.max_bet)
        wager = round(wager, 2)

        insurance = _insurance_policy(bot, true_count)
        results = game.play_hand(
            wager,
            policy=bot.action,
            insurance_policy=insurance,
        )
        _append_round(
            nets,
            bets,
            outcomes,
            true_counts,
            dealer_upcards,
            start_totals,
            results,
            true_count,
        )
        decisions.extend(game.round_decisions)
        last_net = game.round_net
        bot.on_result(last_net)
        completed += 1

    return _make_result(
        bot.name,
        starting_bankroll,
        nets,
        bets,
        outcomes,
        true_counts,
        dealer_upcards,
        start_totals,
        decisions,
        completed,
    )


def run_simulation(
    rounds: int,
    *,
    bet: float = 10.0,
    starting_bankroll: float = 10_000.0,
    rules: Rules | None = None,
    seed: int = 42,
    label: str = "Basic strategy",
    policy: Policy = basic_strategy_policy,
    track_decisions: bool = True,
) -> SimResult:
    """Run a flat-bet simulation, the standard house-edge experiment."""
    bot = FlatBetBot(name=label, unit=bet)
    if policy is not basic_strategy_policy:
        bot.action = policy  # type: ignore[method-assign]
    return run_bot(
        bot,
        rounds,
        starting_bankroll=starting_bankroll,
        rules=rules,
        seed=seed,
        track_decisions=track_decisions,
    )


def compare_bots(
    bots: Sequence[Bot],
    rounds: int,
    *,
    starting_bankroll: float = 10_000.0,
    rules: Rules | None = None,
    seed: int = 42,
    track_decisions: bool = True,
) -> dict[str, SimResult]:
    """Run several bots on identical shoes and return their results."""
    return {
        bot.name: run_bot(
            bot,
            rounds,
            starting_bankroll=starting_bankroll,
            rules=rules,
            seed=seed,
            track_decisions=track_decisions,
        )
        for bot in bots
    }


def run_competition(
    bots: Sequence[Bot],
    rounds: int,
    *,
    starting_bankroll: float = 10_000.0,
    rules: Rules | None = None,
    seed: int = 42,
    track_decisions: bool = True,
) -> tuple[list[LeaderboardEntry], dict[str, SimResult]]:
    """Run bots against one shared shoe and rank them by final bankroll.

    The bots take turns on the same shoe, so every card dealt to one bot is
    seen by the others. Each bot keeps its own bankroll, hands and decisions.
    """
    if rounds <= 0:
        raise ValueError("rounds must be positive")
    if not bots:
        raise ValueError("at least one bot is required")
    rules = rules or Rules()
    shoe = Shoe(rules.num_decks, rules.penetration, seed=seed)

    games = {
        bot.name: BlackjackGame(
            rules,
            starting_bankroll,
            shoe=shoe,
            log_decisions=track_decisions,
        )
        for bot in bots
    }
    for bot in bots:
        bot.reset()

    data: dict[str, dict[str, list[object]]] = {
        bot.name: {
            "nets": [],
            "bets": [],
            "outcomes": [],
            "true_counts": [],
            "dealer_upcards": [],
            "start_totals": [],
            "decisions": [],
        }
        for bot in bots
    }
    last_net = {bot.name: 0.0 for bot in bots}
    completed = {bot.name: 0 for bot in bots}

    for _ in range(rounds):
        for bot in bots:
            game = games[bot.name]
            if game.bankroll + 1e-9 < rules.min_bet:
                continue
            true_count = game.true_count
            context = BetContext(
                bankroll=game.bankroll,
                true_count=true_count,
                running_count=game.running_count,
                hands_played=completed[bot.name],
                last_net=last_net[bot.name],
                rules=rules,
            )
            wager = bot.bet(context)
            if wager + 1e-9 < rules.min_bet:
                continue
            wager = min(wager, game.bankroll, rules.max_bet)
            wager = round(wager, 2)
            insurance = _insurance_policy(bot, true_count)
            results = game.play_hand(
                wager,
                policy=bot.action,
                insurance_policy=insurance,
            )
            bucket = data[bot.name]
            _append_round(
                bucket["nets"],  # type: ignore[arg-type]
                bucket["bets"],  # type: ignore[arg-type]
                bucket["outcomes"],  # type: ignore[arg-type]
                bucket["true_counts"],  # type: ignore[arg-type]
                bucket["dealer_upcards"],  # type: ignore[arg-type]
                bucket["start_totals"],  # type: ignore[arg-type]
                results,
                true_count,
            )
            bucket["decisions"].extend(  # type: ignore[attr-defined]
                game.round_decisions
            )
            last_net[bot.name] = game.round_net
            bot.on_result(last_net[bot.name])
            completed[bot.name] += 1

    results_by_name: dict[str, SimResult] = {}
    entries: list[LeaderboardEntry] = []
    for bot in bots:
        bucket = data[bot.name]
        result = _make_result(
            bot.name,
            starting_bankroll,
            bucket["nets"],  # type: ignore[arg-type]
            bucket["bets"],  # type: ignore[arg-type]
            bucket["outcomes"],  # type: ignore[arg-type]
            bucket["true_counts"],  # type: ignore[arg-type]
            bucket["dealer_upcards"],  # type: ignore[arg-type]
            bucket["start_totals"],  # type: ignore[arg-type]
            bucket["decisions"],  # type: ignore[arg-type]
            completed[bot.name],
        )
        results_by_name[bot.name] = result
        stats = result.analytics()
        entries.append(
            LeaderboardEntry(
                rank=0,
                name=bot.name,
                final_bankroll=stats.final_bankroll,
                net=stats.net,
                roi=stats.roi,
                hands=stats.hands,
                wins=stats.wins,
                losses=stats.losses,
                pushes=stats.pushes,
                max_drawdown=stats.max_drawdown,
                edge=stats.house_edge,
                adherence=stats.adherence,
            )
        )

    entries.sort(key=lambda entry: entry.final_bankroll, reverse=True)
    ranked = [replace(entry, rank=index + 1) for index, entry in enumerate(entries)]
    return ranked, results_by_name
