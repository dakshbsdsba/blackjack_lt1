"""Plotly charts for the simulator dashboard.

The functions return plain :class:`plotly.graph_objects.Figure` objects, so
they render inline in Jupyter/Colab and can also be written to standalone
HTML files without any extra plumbing.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .analytics import Analytics, bucket_by_true_count, outcome_counts
from .simulation import LeaderboardEntry, SimResult

INK = "#111827"
MUTED = "#6b7280"
GRID = "#e5e7eb"
BLUE = "#2563eb"
GREEN = "#059669"
RED = "#dc2626"
AMBER = "#d97706"
PURPLE = "#7c3aed"

DEALER_COLUMNS: tuple[str, ...] = (
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "A",
)


def _layout(fig: go.Figure, title: str, height: int = 420) -> go.Figure:
    """Apply the shared chart layout."""
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color=INK)),
        template="plotly_white",
        height=height,
        margin=dict(l=60, r=30, t=70, b=50),
        font=dict(family="Inter, Arial, sans-serif", color=INK),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return fig


def _downsample(values: np.ndarray, max_points: int = 4000) -> np.ndarray:
    """Return evenly spaced indices so huge runs stay responsive."""
    length = len(values)
    if length <= max_points:
        return np.arange(length)
    return np.linspace(0, length - 1, max_points, dtype=int)


def expected_value_curve(
    result: SimResult,
    *,
    theoretical_edge: float = 0.005,
) -> np.ndarray:
    """Return the theoretical bankroll path at a fixed house edge."""
    if not result.hands:
        return np.array([result.starting_bankroll], dtype=float)
    average_bet = float(np.mean(result.bets)) if len(result.bets) else 0.0
    per_hand = -theoretical_edge * average_bet
    steps = np.arange(result.hands + 1)
    return result.starting_bankroll + steps * per_hand


def bankroll_trajectory(
    result: SimResult,
    *,
    theoretical_edge: float = 0.005,
    title: str | None = None,
) -> go.Figure:
    """Plot the bankroll curve against the theoretical EV line."""
    curve = result.bankroll
    indices = _downsample(curve)
    ev = expected_value_curve(result, theoretical_edge=theoretical_edge)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=indices,
            y=curve[indices],
            mode="lines",
            name="Bankroll",
            line=dict(color=BLUE, width=2),
            hovertemplate="Hand %{x}<br>Bankroll $%{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=np.arange(result.hands + 1),
            y=ev,
            mode="lines",
            name="Theoretical EV",
            line=dict(color=MUTED, width=2, dash="dash"),
            hovertemplate="Hand %{x}<br>EV $%{y:,.0f}<extra></extra>",
        )
    )
    fig.add_hline(
        y=result.starting_bankroll,
        line=dict(color=GRID, width=1, dash="dot"),
    )
    _layout(
        fig,
        title or f"Bankroll trajectory: {result.label}",
        height=460,
    )
    fig.update_xaxes(title_text="Settled hands")
    fig.update_yaxes(title_text="Bankroll ($)", tickprefix="$")
    return fig


def outcome_distribution(result: SimResult, *, title: str | None = None) -> go.Figure:
    """Plot counts of wins, losses, pushes, blackjacks and surrenders."""
    counts = outcome_counts(result.outcomes)
    order = ["blackjack", "win", "push", "loss", "surrender"]
    labels = [label.title() for label in order]
    values = [counts.get(label, 0) for label in order]
    colors = [GREEN, "#22c55e", MUTED, RED, AMBER]
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=values,
            textposition="outside",
            hovertemplate="%{x}: %{y} hands<extra></extra>",
        )
    )
    _layout(fig, title or f"Outcome distribution: {result.label}", height=380)
    fig.update_yaxes(title_text="Hands")
    return fig


def strategy_adherence(result: SimResult, *, title: str | None = None) -> go.Figure:
    """Plot correct versus incorrect basic-strategy decisions."""
    stats = result.analytics()
    correct = stats.strategy_correct
    incorrect = max(0, stats.strategy_decisions - correct)
    fig = go.Figure(
        go.Bar(
            x=["Correct", "Incorrect"],
            y=[correct, incorrect],
            marker_color=[GREEN, RED],
            text=[correct, incorrect],
            textposition="outside",
            hovertemplate="%{x}: %{y} decisions<extra></extra>",
        )
    )
    _layout(
        fig,
        title or f"Strategy adherence: {stats.adherence_percent:.1f}%",
        height=380,
    )
    fig.update_yaxes(title_text="Decisions")
    return fig


def drawdown_chart(result: SimResult, *, title: str | None = None) -> go.Figure:
    """Plot the underwater curve, the distance below the running peak."""
    from .analytics import drawdown_series

    curve = drawdown_series(result.nets.tolist(), result.starting_bankroll)
    indices = _downsample(np.asarray(curve, dtype=float))
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=indices,
            y=np.asarray(curve)[indices],
            mode="lines",
            fill="tozeroy",
            line=dict(color=RED, width=2),
            name="Drawdown",
            hovertemplate="Hand %{x}<br>Drawdown $%{y:,.0f}<extra></extra>",
        )
    )
    _layout(fig, title or f"Underwater curve: {result.label}", height=380)
    fig.update_xaxes(title_text="Settled hands")
    fig.update_yaxes(title_text="Below peak ($)", tickprefix="$")
    return fig


def dashboard(result: SimResult, *, theoretical_edge: float = 0.005) -> go.Figure:
    """Build the four-panel dashboard: bankroll, outcomes, drawdown, adherence."""
    from .analytics import drawdown_series

    stats = result.analytics()
    curve = result.bankroll
    indices = _downsample(curve)
    ev = expected_value_curve(result, theoretical_edge=theoretical_edge)
    drawdown = np.asarray(
        drawdown_series(result.nets.tolist(), result.starting_bankroll)
    )
    dd_indices = _downsample(drawdown)

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=(
            "Bankroll vs theoretical EV",
            "Win / loss / push distribution",
            "Underwater drawdown",
            "Strategy adherence",
        ),
        specs=[[{"type": "xy"}, {"type": "xy"}], [{"type": "xy"}, {"type": "xy"}]],
        vertical_spacing=0.16,
        horizontal_spacing=0.09,
    )

    fig.add_trace(
        go.Scatter(
            x=indices,
            y=curve[indices],
            mode="lines",
            name="Bankroll",
            line=dict(color=BLUE, width=2),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=np.arange(result.hands + 1),
            y=ev,
            mode="lines",
            name="Theoretical EV",
            line=dict(color=MUTED, width=2, dash="dash"),
        ),
        row=1,
        col=1,
    )

    counts = outcome_counts(result.outcomes)
    order = ["blackjack", "win", "push", "loss", "surrender"]
    fig.add_trace(
        go.Bar(
            x=[label.title() for label in order],
            y=[counts.get(label, 0) for label in order],
            marker_color=[GREEN, "#22c55e", MUTED, RED, AMBER],
            showlegend=False,
            text=[counts.get(label, 0) for label in order],
            textposition="outside",
        ),
        row=1,
        col=2,
    )

    fig.add_trace(
        go.Scatter(
            x=dd_indices,
            y=drawdown[dd_indices],
            mode="lines",
            fill="tozeroy",
            line=dict(color=RED, width=1.5),
            name="Drawdown",
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Bar(
            x=["Correct", "Incorrect"],
            y=[
                stats.strategy_correct,
                max(0, stats.strategy_decisions - stats.strategy_correct),
            ],
            marker_color=[GREEN, RED],
            showlegend=False,
            text=[
                stats.strategy_correct,
                max(0, stats.strategy_decisions - stats.strategy_correct),
            ],
            textposition="outside",
        ),
        row=2,
        col=2,
    )

    _layout(fig, f"Session dashboard: {result.label}", height=760)
    fig.update_xaxes(title_text="Settled hands", row=1, col=1)
    fig.update_xaxes(title_text="Settled hands", row=2, col=1)
    fig.update_yaxes(title_text="Bankroll ($)", tickprefix="$", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown ($)", tickprefix="$", row=2, col=1)
    fig.update_yaxes(title_text="Hands", row=1, col=2)
    fig.update_yaxes(title_text="Decisions", row=2, col=2)
    return fig


def _heatmap_grids(
    result: SimResult,
) -> tuple[list[list[float | None]], list[list[float | None]]]:
    """Aggregate edge and win rate by starting total and dealer upcard."""
    totals = list(range(4, 22))
    row_of = {total: index for index, total in enumerate(totals)}
    col_of = {card: index for index, card in enumerate(DEALER_COLUMNS)}
    net_sum = np.zeros((len(totals), len(DEALER_COLUMNS)))
    bet_sum = np.zeros((len(totals), len(DEALER_COLUMNS)))
    wins = np.zeros((len(totals), len(DEALER_COLUMNS)))
    counts = np.zeros((len(totals), len(DEALER_COLUMNS)))

    for net, bet, outcome, total, upcard in zip(
        result.nets,
        result.bets,
        result.outcomes,
        result.start_totals,
        result.dealer_upcards,
    ):
        if total not in row_of or upcard not in col_of:
            continue
        row, col = row_of[int(total)], col_of[upcard]
        net_sum[row, col] += float(net)
        bet_sum[row, col] += float(bet)
        counts[row, col] += 1
        if outcome in ("win", "blackjack"):
            wins[row, col] += 1

    edge = [
        [
            (net_sum[row, col] / bet_sum[row, col]) if bet_sum[row, col] else None
            for col in range(len(DEALER_COLUMNS))
        ]
        for row in range(len(totals))
    ]
    win_rate = [
        [
            (wins[row, col] / counts[row, col]) if counts[row, col] else None
            for col in range(len(DEALER_COLUMNS))
        ]
        for row in range(len(totals))
    ]
    return edge, win_rate


def risk_heatmap(result: SimResult) -> go.Figure:
    """Heatmaps of player edge per unit and win rate by hand and upcard."""
    edge, win_rate = _heatmap_grids(result)
    rows = [str(total) for total in range(4, 22)]
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Player edge per unit", "Win rate"),
        horizontal_spacing=0.12,
    )
    fig.add_trace(
        go.Heatmap(
            z=edge,
            x=list(DEALER_COLUMNS),
            y=rows,
            colorscale="RdYlGn",
            zmid=0.0,
            colorbar=dict(title="EV / bet", x=0.44, len=0.85),
            hovertemplate="Total %{y} vs %{x}<br>EV per unit %{z:.3f}<extra></extra>",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Heatmap(
            z=win_rate,
            x=list(DEALER_COLUMNS),
            y=rows,
            colorscale="Blues",
            zmin=0.0,
            zmax=1.0,
            colorbar=dict(title="Win rate", x=1.0, len=0.85),
            hovertemplate="Total %{y} vs %{x}<br>Win rate %{z:.1%}<extra></extra>",
        ),
        row=1,
        col=2,
    )
    _layout(fig, "Risk heatmap: starting total vs dealer upcard", height=620)
    fig.update_xaxes(title_text="Dealer upcard", row=1, col=1)
    fig.update_xaxes(title_text="Dealer upcard", row=1, col=2)
    fig.update_yaxes(title_text="Player starting total", row=1, col=1)
    return fig


def count_profitability(
    result: SimResult,
    *,
    low: int = -4,
    high: int = 6,
) -> go.Figure:
    """Plot player EV per unit by true-count bucket, with hand counts."""
    buckets = bucket_by_true_count(
        result.true_counts.tolist(),
        result.nets.tolist(),
        result.bets.tolist(),
        result.outcomes,
        low=low,
        high=high,
    )
    labels = [bucket.label for bucket in buckets]
    edge = [-bucket.edge for bucket in buckets]
    hands = [bucket.hands for bucket in buckets]
    colors = [GREEN if value > 0 else RED for value in edge]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=labels,
            y=edge,
            name="Player EV per unit",
            marker_color=colors,
            text=[f"{value:+.1%}" for value in edge],
            textposition="outside",
            hovertemplate="True count %{x}<br>EV per unit %{y:.2%}<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=hands,
            name="Hands",
            mode="lines+markers",
            line=dict(color=PURPLE, width=2),
            marker=dict(size=7),
            hovertemplate="True count %{x}<br>%{y} hands<extra></extra>",
        ),
        secondary_y=True,
    )
    fig.add_hline(y=0.0, line=dict(color=INK, width=1))
    _layout(fig, f"Count profitability: {result.label}", height=440)
    fig.update_xaxes(title_text="True count bucket")
    fig.update_yaxes(
        title_text="Player EV per unit", tickformat=".0%", secondary_y=False
    )
    fig.update_yaxes(title_text="Hands", secondary_y=True)
    return fig


def leaderboard_chart(
    entries: Sequence[LeaderboardEntry],
    *,
    starting_bankroll: float | None = None,
) -> go.Figure:
    """Horizontal bars of final bankroll for the bot leaderboard."""
    ordered = list(reversed(list(entries)))
    names = [entry.name for entry in ordered]
    finals = [entry.final_bankroll for entry in ordered]
    colors = [GREEN if entry.net >= 0 else RED for entry in ordered]
    fig = go.Figure(
        go.Bar(
            x=finals,
            y=names,
            orientation="h",
            marker_color=colors,
            text=[f"${value:,.0f}" for value in finals],
            textposition="outside",
            hovertemplate="%{y}<br>Final bankroll $%{x:,.0f}<extra></extra>",
        )
    )
    if starting_bankroll is not None:
        fig.add_vline(
            x=starting_bankroll,
            line=dict(color=MUTED, width=2, dash="dash"),
        )
    _layout(fig, "Bot leaderboard: final bankroll", height=100 + 70 * len(entries))
    fig.update_xaxes(title_text="Final bankroll ($)", tickprefix="$")
    return fig


def compare_curves(
    results: dict[str, SimResult],
    *,
    max_points: int = 3000,
    show_ev: bool = True,
    expected_edges: dict[str, float] | None = None,
) -> go.Figure:
    """Plot bankroll and expected-value paths for several strategies.

    ``expected_edges`` is an optional mapping from strategy name to house edge
    as a decimal. When omitted, each strategy's realised house edge is used.
    A negative edge means a player edge, so that EV line slopes upward.
    """
    fig = go.Figure()
    palette = [BLUE, GREEN, AMBER, PURPLE, RED, "#0891b2", "#be185d"]
    for index, (name, result) in enumerate(results.items()):
        color = palette[index % len(palette)]
        curve = result.bankroll
        indices = _downsample(curve, max_points)
        fig.add_trace(
            go.Scatter(
                x=indices,
                y=curve[indices],
                mode="lines",
                name=name,
                line=dict(color=color, width=2),
                hovertemplate="Hand %{x}<br>%{y:$,.0f}<extra></extra>",
            )
        )
        if show_ev:
            edge = (
                expected_edges[name]
                if expected_edges is not None and name in expected_edges
                else result.analytics().house_edge
            )
            ev = expected_value_curve(result, theoretical_edge=edge)
            ev_indices = _downsample(np.arange(len(ev)), max_points)
            fig.add_trace(
                go.Scatter(
                    x=ev_indices,
                    y=ev[ev_indices],
                    mode="lines",
                    name=f"{name} EV",
                    line=dict(color=color, width=1.5, dash="dash"),
                    opacity=0.7,
                    hovertemplate="Hand %{x}<br>EV $%{y:,.0f}<extra></extra>",
                )
            )
    _layout(fig, "Bankroll and EV by strategy", height=480)
    fig.update_xaxes(title_text="Settled hands")
    fig.update_yaxes(title_text="Bankroll ($)", tickprefix="$")
    return fig


def summary_figure(stats: Analytics) -> go.Figure:
    """A compact scorecard of the headline metrics."""
    labels = [
        "Hands",
        "Wagered",
        "Net",
        "House edge",
        "Win rate",
        "Adherence",
        "Max drawdown",
    ]
    values = [
        f"{stats.hands:,}",
        f"${stats.wagered:,.0f}",
        f"${stats.net:,.0f}",
        f"{stats.house_edge_percent:.2f}%",
        f"{stats.win_rate * 100:.1f}%",
        f"{stats.adherence_percent:.1f}%",
        f"${stats.max_drawdown:,.0f}",
    ]
    fig = go.Figure(
        go.Table(
            header=dict(
                values=["Metric", "Value"],
                fill_color="#f3f4f6",
                font=dict(color=INK, size=13),
                align="left",
            ),
            cells=dict(
                values=[labels, values],
                fill_color="white",
                font=dict(color=INK, size=13),
                align="left",
                height=28,
            ),
        )
    )
    fig.update_layout(
        title=dict(text="Run summary", font=dict(size=18, color=INK)),
        template="plotly_white",
        height=340,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return fig
