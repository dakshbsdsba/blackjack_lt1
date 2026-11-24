"""Generate real simulator data for the presentation deck."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from blackjack import (
    BasicStrategyBot,
    FlatBetBot,
    HiLoSpreadBot,
    KellyBot,
    MartingaleBot,
    run_bot,
    run_competition,
    run_simulation,
)
from blackjack.analytics import drawdown_series, outcome_counts
from blackjack.strategy import DEALER_COLUMNS, HARD_TABLE, PAIR_TABLE, SOFT_TABLE

OUT = Path("/tmp/presentation_data.json")
ROWS = list(range(4, 22))


def downsample(values, count=420):
    """Return evenly spaced x indices and values."""
    length = len(values)
    if length <= count:
        indices = list(range(length))
    else:
        indices = np.linspace(0, length - 1, count).astype(int).tolist()
    return indices, [round(float(values[i]), 2) for i in indices]


def bankroll_payload(result, label, color):
    stats = result.analytics()
    curve = result.bankroll
    indices, values = downsample(curve, 420)
    dd = drawdown_series(result.nets.tolist(), result.starting_bankroll)
    dd_indices, dd_values = downsample(dd, 420)
    per_hand_ev = 0.005 * float(np.mean(result.bets))
    ev = [result.starting_bankroll - per_hand_ev * i for i in range(result.hands + 1)]
    return {
        "label": label,
        "color": color,
        "indices": indices,
        "bankroll": values,
        "drawdown_indices": dd_indices,
        "drawdown": dd_values,
        "ev": [round(ev[i], 2) for i in indices],
        "start": result.starting_bankroll,
        "hands": stats.hands,
        "rounds": result.rounds,
        "edge": round(stats.house_edge_percent, 4),
        "net": round(stats.net, 2),
        "wagered": round(stats.wagered, 2),
        "avg_bet": round(stats.avg_bet, 2),
        "final": round(stats.final_bankroll, 2),
        "max_drawdown": round(stats.max_drawdown, 2),
        "wins": stats.wins,
        "losses": stats.losses,
        "pushes": stats.pushes,
        "blackjacks": stats.blackjacks,
        "surrender": stats.surrenders,
        "adherence": round(stats.adherence_percent, 2),
    }


def heatmap_payload(result):
    net = np.zeros((len(ROWS), len(DEALER_COLUMNS)))
    bet = np.zeros((len(ROWS), len(DEALER_COLUMNS)))
    wins = np.zeros((len(ROWS), len(DEALER_COLUMNS)))
    hands = np.zeros((len(ROWS), len(DEALER_COLUMNS)))
    row_of = {total: i for i, total in enumerate(ROWS)}
    col_of = {card: i for i, card in enumerate(DEALER_COLUMNS)}
    for n, b, outcome, total, upcard in zip(
        result.nets,
        result.bets,
        result.outcomes,
        result.start_totals,
        result.dealer_upcards,
    ):
        if int(total) not in row_of or upcard not in col_of:
            continue
        r, c = row_of[int(total)], col_of[upcard]
        net[r, c] += float(n)
        bet[r, c] += float(b)
        hands[r, c] += 1
        if outcome in ("win", "blackjack"):
            wins[r, c] += 1
    ev = [
        [
            round(float(net[r, c] / bet[r, c]), 3) if bet[r, c] else None
            for c in range(len(DEALER_COLUMNS))
        ]
        for r in range(len(ROWS))
    ]
    win = [
        [
            round(float(wins[r, c] / hands[r, c]), 3) if hands[r, c] else None
            for c in range(len(DEALER_COLUMNS))
        ]
        for r in range(len(ROWS))
    ]
    counts = [
        [int(hands[r, c]) for c in range(len(DEALER_COLUMNS))] for r in range(len(ROWS))
    ]
    return {
        "rows": [str(r) for r in ROWS],
        "cols": list(DEALER_COLUMNS),
        "ev": ev,
        "win": win,
        "hands": counts,
    }


def pooled_buckets(results, low=-4, high=5):
    """Aggregate true-count buckets across several independent runs."""
    buckets = {
        key: {"net": 0.0, "bet": 0.0, "hands": 0, "wins": 0}
        for key in range(low, high + 1)
    }
    for result in results:
        for net, bet, outcome, count in zip(
            result.nets, result.bets, result.outcomes, result.true_counts
        ):
            key = max(low, min(high, int(round(float(count)))))
            bucket = buckets[key]
            bucket["net"] += float(net)
            bucket["bet"] += float(bet)
            bucket["hands"] += 1
            if outcome in ("win", "blackjack"):
                bucket["wins"] += 1
    rows = []
    for key in range(low, high + 1):
        bucket = buckets[key]
        label = f"{key}" if key < high else f"+{high}+"
        edge = -bucket["net"] / bucket["bet"] if bucket["bet"] else 0.0
        rows.append(
            {
                "label": label,
                "hands": bucket["hands"],
                "ev": round(edge * 100, 2),
                "win": (
                    round(100 * bucket["wins"] / bucket["hands"], 1)
                    if bucket["hands"]
                    else 0.0
                ),
            }
        )
    return rows


def main():
    flat = run_simulation(
        100_000,
        bet=10,
        starting_bankroll=100_000,
        seed=7,
        label="Flat basic strategy",
        track_decisions=True,
    )
    print("flat done", flat.analytics().as_dict())

    counting = run_bot(
        HiLoSpreadBot(name="Hi-Lo spread", unit=10, spread=8),
        100_000,
        starting_bankroll=100_000,
        seed=7,
        track_decisions=False,
    )
    print("counting done", counting.analytics().as_dict())

    pooled_results = [counting]
    for seed in (11, 21):
        extra = run_bot(
            HiLoSpreadBot(name=f"Hi-Lo {seed}", unit=10, spread=8),
            100_000,
            starting_bankroll=100_000,
            seed=seed,
            track_decisions=False,
        )
        pooled_results.append(extra)
        print("pooled seed", seed, "done", extra.analytics().house_edge_percent)

    pooled_net = sum(float(r.nets.sum()) for r in pooled_results)
    pooled_wagered = sum(float(r.bets.sum()) for r in pooled_results)
    pooled_hands = sum(int(len(r.nets)) for r in pooled_results)
    pooled_edge = -pooled_net / pooled_wagered * 100
    count_buckets = pooled_buckets(pooled_results)
    print("pooled", pooled_hands, round(pooled_edge, 3), round(pooled_net, 2))

    bots = [
        BasicStrategyBot(name="Basic strategy", unit=10),
        FlatBetBot(name="Flat bettor", unit=10),
        MartingaleBot(name="Martingale", unit=10, max_multiplier=8),
        HiLoSpreadBot(name="Hi-Lo spread", unit=10, spread=8),
        KellyBot(name="Half Kelly", unit=10, fraction=0.5),
    ]
    entries, _ = run_competition(bots, 1000, starting_bankroll=1000, seed=9)
    leaderboard = [
        {
            "rank": e.rank,
            "name": e.name,
            "final": round(e.final_bankroll, 2),
            "net": round(e.net, 2),
            "edge": round(e.edge * 100, 2),
            "drawdown": round(e.max_drawdown, 2),
            "adherence": round(e.adherence * 100, 1),
            "hands": e.hands,
        }
        for e in entries
    ]

    flat_stats = flat.analytics()
    counting_stats = counting.analytics()
    data = {
        "strategy": {
            "hard": {str(k): v for k, v in HARD_TABLE.items()},
            "soft": {str(k): v for k, v in SOFT_TABLE.items()},
            "pair": dict(PAIR_TABLE),
            "dealers": list(DEALER_COLUMNS),
        },
        "flat": bankroll_payload(flat, "Flat basic strategy", "#22d3ee"),
        "counting": bankroll_payload(counting, "Hi-Lo spread", "#34d399"),
        "outcomes": outcome_counts(flat.outcomes),
        "heatmap": heatmap_payload(flat),
        "count_buckets": count_buckets,
        "leaderboard": leaderboard,
        "stats": {
            "tests": 513,
            "quick_tests": 510,
            "strategy_cases": 376,
            "flat_hands": flat_stats.hands,
            "flat_edge": round(flat_stats.house_edge_percent, 4),
            "flat_net": round(flat_stats.net, 2),
            "flat_bj": flat_stats.blackjacks,
            "flat_surrender": flat_stats.surrenders,
            "count_hands": counting_stats.hands,
            "count_edge": round(counting_stats.house_edge_percent, 4),
            "count_net": round(counting_stats.net, 2),
            "count_avg_bet": round(counting_stats.avg_bet, 2),
            "flat_avg_bet": round(flat_stats.avg_bet, 2),
            "flat_drawdown": round(flat_stats.max_drawdown, 2),
            "count_drawdown": round(counting_stats.max_drawdown, 2),
            "pooled_hands": pooled_hands,
            "pooled_edge": round(pooled_edge, 4),
            "pooled_net": round(pooled_net, 2),
        },
    }
    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("wrote", OUT, OUT.stat().st_size, "bytes")
    print("leaderboard", leaderboard)
    print("buckets", count_buckets)


if __name__ == "__main__":
    main()
