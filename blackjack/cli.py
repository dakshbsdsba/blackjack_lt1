"""Interactive command line table for the blackjack simulator."""

from __future__ import annotations

import argparse
import time
from typing import Sequence

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from . import __version__
from .analytics import Analytics
from .bots import BasicStrategyBot, FlatBetBot, HiLoSpreadBot, KellyBot, MartingaleBot
from .engine import BlackjackGame, GameState, Outcome
from .rules import Rules
from .simulation import run_bot, run_competition, run_simulation
from .strategy import basic_strategy_action

OUTCOME_STYLES = {
    Outcome.BLACKJACK: "bold green",
    Outcome.WIN: "green",
    Outcome.PUSH: "yellow",
    Outcome.LOSS: "red",
    Outcome.SURRENDER: "magenta",
}

STATUS_LABELS = {
    "playing": "Playing",
    "stand": "Stand",
    "bust": "Bust",
    "blackjack": "Blackjack",
    "doubled": "Doubled",
    "surrender": "Surrender",
    "split": "Split",
}


def _card_text(card: object, *, hidden: bool = False) -> Text:
    """Render one card with a colour for red suits."""
    if hidden:
        return Text("??", style="dim")
    from .cards import Card

    assert isinstance(card, Card)
    style = "bold red" if card.is_red else "bold"
    return Text(str(card), style=style)


def _hand_status(hand: object, *, is_current: bool) -> str:
    """Return the short status label for a hand."""
    from .hand import Hand

    assert isinstance(hand, Hand)
    if hand.surrendered:
        return STATUS_LABELS["surrender"]
    if hand.is_blackjack:
        return STATUS_LABELS["blackjack"]
    if hand.is_bust:
        return STATUS_LABELS["bust"]
    if hand.is_doubled:
        return STATUS_LABELS["doubled"]
    if hand.stood:
        return STATUS_LABELS["stand"]
    if is_current:
        return STATUS_LABELS["playing"]
    return STATUS_LABELS["split"] if hand.is_split_hand else STATUS_LABELS["playing"]


TRAINER_SPREAD = 8
TRAINER_INSURANCE_TC = 3.0


def _trainer_true_count(game: BlackjackGame, reveal_dealer: bool) -> tuple[int, float]:
    """Return the count visible to the player, hiding the dealer hole card."""
    hole = game.dealer.cards[1] if len(game.dealer.cards) >= 2 else None
    running = 0
    for card in game.shoe.dealt_cards:
        if not reveal_dealer and card is hole:
            continue
        running += card.hi_lo_value
    true_count = running / max(0.5, game.shoe.decks_remaining)
    return running, true_count


def _trainer_bet_units(true_count: float) -> int:
    """Return a simple 1-to-8 unit spread from the true count."""
    if true_count < 1.0:
        return 1
    return min(TRAINER_SPREAD, max(1, int(round(true_count))))


def _trainer_bet_guide(game: BlackjackGame, unit: float) -> tuple[float, int, float]:
    """Return the pre-bet true count, units and recommended amount."""
    _, true_count = _trainer_true_count(game, True)
    units = _trainer_bet_units(true_count)
    amount = min(unit * units, game.rules.max_bet, max(game.bankroll, 0.0))
    return true_count, units, round(amount, 2)


def _print_trainer_bet_guide(
    console: Console, game: BlackjackGame, unit: float
) -> float:
    """Print the pre-bet guide and return the recommended amount."""
    true_count, units, amount = _trainer_bet_guide(game, unit)
    console.print(
        f"[bold cyan]Bet guide[/bold cyan]  ${unit:,.0f} unit  "
        f"TC {true_count:+.2f}  →  {units} unit"
        f"{'s' if units != 1 else ''} = ${amount:,.2f}"
    )
    return amount


def render_table(
    console: Console,
    game: BlackjackGame,
    *,
    reveal_dealer: bool,
    trainer: bool = False,
    hint: bool = False,
) -> None:
    """Draw the table for the current round."""
    table = Table(
        box=box.ROUNDED,
        expand=True,
        show_header=True,
        header_style="bold",
        padding=(0, 1),
    )
    table.add_column("Seat", width=10)
    table.add_column("Cards", ratio=3)
    table.add_column("Bet", justify="right", width=10)
    table.add_column("Total", justify="right", width=8)
    table.add_column("Status", width=12)

    dealer_cards = Text(" ")
    if game.dealer.cards:
        dealer_cards = Text(" ")
        dealer_cards.append_text(_card_text(game.dealer.cards[0]))
        dealer_cards.append(" ")
        dealer_cards.append_text(
            _card_text(game.dealer.cards[1], hidden=not reveal_dealer)
        )
        if len(game.dealer.cards) > 2:
            for card in game.dealer.cards[2:]:
                dealer_cards.append(" ")
                dealer_cards.append_text(_card_text(card))
    dealer_total = str(game.dealer.total) if reveal_dealer else "?"
    dealer_status = ""
    if reveal_dealer:
        dealer_status = (
            "Blackjack"
            if game.dealer.is_blackjack
            else "Bust" if game.dealer.is_bust else "Stand"
        )
    table.add_row(
        Text("Dealer", style="bold"),
        dealer_cards,
        "",
        dealer_total,
        dealer_status,
    )

    for index, hand in enumerate(game.hands):
        current = index == game.current and game.state is GameState.PLAYER
        seat = Text(f"{'> ' if current else '  '}Hand {index + 1}")
        cards = Text(" ")
        for position, card in enumerate(hand.cards):
            if position:
                cards.append(" ")
            cards.append_text(_card_text(card))
        table.add_row(
            seat,
            cards,
            f"${hand.bet:,.2f}",
            str(hand.total),
            _hand_status(hand, is_current=current),
        )

    console.print(table)

    status = game.shoe_status()
    footer = Text()
    footer.append(f"Bankroll ${game.bankroll:,.2f}", style="bold")
    footer.append(
        f"  |  Shoe {status['cards_remaining']}/{status['total_cards']} cards"
        f"  |  Discard {status['discard_tray']}"
        f"  |  Shuffles {status['shuffle_count']}"
    )
    true_count = 0.0
    if trainer:
        running, true_count = _trainer_true_count(game, reveal_dealer)
        footer.append(
            f"  |  Running {running:+d}  |  True {true_count:+.2f}",
            style="cyan",
        )
    console.print(footer)

    if hint and game.state is GameState.PLAYER:
        actions = game.available_actions()
        suggestion = basic_strategy_action(
            game.player_hand,
            game.dealer.cards[0],
            game.rules,
            can_double="double" in actions,
            can_split="split" in actions,
            can_surrender="surrender" in actions,
        )
        console.print(f"[cyan]Basic strategy says:[/cyan] {suggestion}")


def render_result(console: Console, game: BlackjackGame) -> None:
    """Print the settled round and the running session summary."""
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    table.add_column("Hand")
    table.add_column("Cards")
    table.add_column("Total", justify="right")
    table.add_column("Outcome")
    table.add_column("Net", justify="right")

    for index, result in enumerate(game.round_results):
        style = OUTCOME_STYLES[result.outcome]
        net = f"{result.net:+,.2f}"
        table.add_row(
            f"{index + 1}",
            " ".join(result.cards),
            str(result.player_total),
            Text(result.outcome.value.title(), style=style),
            Text(net, style=style),
        )
    console.print(table)

    total = game.round_net
    style = "green" if total > 0 else "red" if total < 0 else "yellow"
    dealer = game.dealer
    console.print(
        f"[bold]Dealer:[/bold] {' '.join(str(card) for card in dealer.cards)} "
        f"({dealer.total})   [bold]Round:[/bold] [{style}]{total:+,.2f}[/{style}]"
    )


def session_summary(game: BlackjackGame, starting_bankroll: float) -> Analytics:
    """Build the running analytics for the current session."""
    return Analytics.from_results(
        game.history,
        starting_bankroll=starting_bankroll,
        decisions=game.decision_history,
    )


def print_session_line(
    console: Console, game: BlackjackGame, starting_bankroll: float
) -> None:
    """Print one compact line of session statistics."""
    stats = session_summary(game, starting_bankroll)
    console.print(
        f"[dim]Hands {stats.hands}  |  Net {stats.net:+,.2f}  |  "
        f"House edge {stats.house_edge_percent:.2f}%  |  "
        f"Adherence {stats.adherence_percent:.1f}%  |  "
        f"Max drawdown {stats.max_drawdown:,.2f}[/dim]"
    )


def ask_bet(
    console: Console,
    game: BlackjackGame,
    default_bet: float,
    *,
    suggested_bet: float | None = None,
) -> float | None:
    """Ask for a wager. Return None when the player wants to leave."""
    while True:
        if game.bankroll + 1e-9 < game.rules.min_bet:
            console.print("[red]You are out of chips.[/red]")
            return None
        suggested = (
            suggested_bet
            if suggested_bet is not None
            else min(default_bet, game.bankroll)
        )
        suggested = min(suggested, game.rules.max_bet, game.bankroll)
        suggested = max(game.rules.min_bet, suggested)
        try:
            raw = Prompt.ask(
                f"[bold]Bet[/bold] (bankroll ${game.bankroll:,.2f}, "
                f"limits ${game.rules.min_bet:g}-${game.rules.max_bet:g})",
                default=f"{suggested:g}",
            )
        except (EOFError, KeyboardInterrupt):
            return None
        command = raw.strip().lower()
        if command in {"q", "quit", "exit"}:
            return None
        if command in {"s", "shoe"}:
            status = game.shoe_status()
            console.print(
                f"Shoe: {status['cards_remaining']} of {status['total_cards']} cards, "
                f"{status['decks_remaining']} decks left, "
                f"{status['discard_tray']} in the discard tray, "
                f"{status['shuffle_count']} shuffles so far."
            )
            continue
        if command in {"h", "help", "?"}:
            print_help(console)
            continue
        try:
            bet = float(command.replace("$", "").replace(",", ""))
        except ValueError:
            console.print("[red]Enter a number, or q to quit.[/red]")
            continue
        if bet < game.rules.min_bet:
            console.print(f"[red]The table minimum is ${game.rules.min_bet:g}.[/red]")
            continue
        if bet > game.rules.max_bet:
            console.print(f"[red]The table maximum is ${game.rules.max_bet:g}.[/red]")
            continue
        if bet > game.bankroll + 1e-9:
            console.print("[red]That is more than your bankroll.[/red]")
            continue
        return bet


def print_help(console: Console) -> None:
    """Show the command reference."""
    console.print(
        Panel(
            "[bold]At the bet prompt[/bold]\n"
            "  number      place that bet\n"
            "  s           shoe status\n"
            "  h           this help\n"
            "  q           leave the table\n\n"
            "[bold]During a hand[/bold]\n"
            "  h  hit      s  stand     d  double\n"
            "  p  split    r  surrender",
            title="Commands",
            box=box.ROUNDED,
        )
    )


def play_interactive(args: argparse.Namespace) -> int:
    """Run the playable table."""
    console = Console()
    rules = Rules(
        num_decks=args.decks,
        penetration=args.penetration,
        dealer_stands_soft_17=not args.hit_soft_17,
    )
    game = BlackjackGame(
        rules,
        bankroll=args.bankroll,
        seed=args.seed,
    )
    starting_bankroll = game.bankroll

    console.print(
        Panel(
            f"[bold]Blackjack[/bold]  v{__version__}\n"
            f"{rules.describe()}\n"
            f"Bankroll ${game.bankroll:,.2f}   Table limits "
            f"${rules.min_bet:g}-${rules.max_bet:g}",
            title="Table open",
            box=box.DOUBLE,
        )
    )
    console.print("Type [bold]h[/bold] at the bet prompt for commands.\n")

    while True:
        suggested_bet = None
        if args.trainer:
            suggested_bet = _print_trainer_bet_guide(console, game, args.bet)
        bet = ask_bet(
            console,
            game,
            args.bet,
            suggested_bet=suggested_bet,
        )
        if bet is None:
            break
        try:
            game.start_hand(bet)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            continue

        render_table(
            console,
            game,
            reveal_dealer=False,
            trainer=args.trainer,
            hint=args.hint,
        )

        if game.state is GameState.INSURANCE:
            take_default = False
            if args.trainer:
                _, insurance_tc = _trainer_true_count(game, False)
                take_default = insurance_tc >= TRAINER_INSURANCE_TC
                console.print(
                    f"[cyan]Insurance hint:[/cyan] "
                    f"{'TAKE' if take_default else 'DECLINE'}  "
                    f"(TC {insurance_tc:+.2f} vs +{TRAINER_INSURANCE_TC:.2f})"
                )
            try:
                take = Confirm.ask(
                    f"Dealer shows an Ace. Insurance for ${bet / 2:,.2f}?",
                    default=take_default,
                )
            except (EOFError, KeyboardInterrupt):
                take = take_default
            try:
                game.take_insurance(take)
            except ValueError as exc:
                console.print(f"[red]{exc}[/red]")
                game.take_insurance(False)
            if game.state is not GameState.PLAYER:
                render_table(
                    console,
                    game,
                    reveal_dealer=True,
                    trainer=args.trainer,
                )
                render_result(console, game)
                print_session_line(console, game, starting_bankroll)
                console.print()
                continue

        while game.state is GameState.PLAYER:
            actions = game.available_actions()
            hint = ""
            if args.hint:
                suggestion = basic_strategy_action(
                    game.player_hand,
                    game.dealer.cards[0],
                    rules,
                    can_double="double" in actions,
                    can_split="split" in actions,
                    can_surrender="surrender" in actions,
                )
                hint = f" [cyan](strategy: {suggestion})[/cyan]"
            try:
                action = Prompt.ask(
                    f"Action [{'/'.join(actions)}]{hint}",
                    choices=actions,
                    default="hit",
                    show_choices=False,
                )
            except (EOFError, KeyboardInterrupt):
                action = "stand"
            try:
                game.act(action)
            except ValueError as exc:
                console.print(f"[red]{exc}[/red]")
                continue
            if game.state is GameState.PLAYER:
                render_table(
                    console,
                    game,
                    reveal_dealer=False,
                    trainer=args.trainer,
                    hint=args.hint,
                )

        render_table(
            console,
            game,
            reveal_dealer=True,
            trainer=args.trainer,
        )
        render_result(console, game)
        print_session_line(console, game, starting_bankroll)
        console.print()

    stats = session_summary(game, starting_bankroll)
    console.print(
        Panel(
            f"Hands {stats.hands}   Net {stats.net:+,.2f}   "
            f"House edge {stats.house_edge_percent:.2f}%   "
            f"Adherence {stats.adherence_percent:.1f}%\n"
            f"Final bankroll ${game.bankroll:,.2f}",
            title="Table closed",
            box=box.ROUNDED,
        )
    )
    return 0


def run_demo(args: argparse.Namespace) -> int:
    """Run the bot competition and print the leaderboard."""
    console = Console()
    rules = Rules(num_decks=args.decks, penetration=args.penetration)
    unit = args.bet
    bots = [
        BasicStrategyBot(name="Basic strategy", unit=unit),
        FlatBetBot(name="Flat bettor", unit=unit),
        MartingaleBot(name="Martingale", unit=unit, max_multiplier=8),
        HiLoSpreadBot(name="Hi-Lo spread", unit=unit, spread=8),
        KellyBot(name="Half Kelly", unit=unit, fraction=0.5),
    ]
    console.print(
        f"Running {args.rounds:,} rounds per bot on a shared "
        f"{rules.num_decks}-deck shoe..."
    )
    started = time.perf_counter()
    entries, results = run_competition(
        bots,
        args.rounds,
        starting_bankroll=args.bankroll,
        rules=rules,
        seed=args.seed if args.seed is not None else 7,
    )
    elapsed = time.perf_counter() - started

    table = Table(box=box.ROUNDED, header_style="bold", expand=True)
    table.add_column("Rank", justify="center", width=5)
    table.add_column("Bot", min_width=18, no_wrap=True)
    table.add_column("Final bankroll", justify="right", no_wrap=True)
    table.add_column("Net", justify="right", no_wrap=True)
    table.add_column("Edge", justify="right", no_wrap=True)
    for entry in entries:
        style = "green" if entry.net > 0 else "red"
        table.add_row(
            str(entry.rank),
            entry.name,
            f"${entry.final_bankroll:,.0f}",
            Text(f"{entry.net:+,.0f}", style=style),
            f"{entry.edge * 100:+.1f}%",
        )
    console.print(table)
    console.print(
        f"[dim]{len(entries)} bots, {args.rounds:,} rounds each, "
        f"{elapsed:.1f}s. Edge is positive when the house wins.[/dim]"
    )
    return 0


def run_report(args: argparse.Namespace) -> int:
    """Run flat and Hi-Lo Monte Carlo simulations and compare them."""
    console = Console()
    rules = Rules(num_decks=args.decks, penetration=args.penetration)
    seed = args.seed if args.seed is not None else 42
    console.print(f"Simulating {args.simulate:,} rounds for flat and Hi-Lo...")
    started = time.perf_counter()
    flat = run_simulation(
        args.simulate,
        bet=args.bet,
        starting_bankroll=args.bankroll,
        rules=rules,
        seed=seed,
        track_decisions=True,
    )
    hilo = run_bot(
        HiLoSpreadBot(name="Hi-Lo spread", unit=args.bet, spread=8),
        args.simulate,
        starting_bankroll=args.bankroll,
        rules=rules,
        seed=seed,
        track_decisions=True,
    )
    elapsed = time.perf_counter() - started
    flat_stats = flat.analytics()
    hilo_stats = hilo.analytics()

    table = Table(box=box.ROUNDED, header_style="bold")
    table.add_column("Metric")
    table.add_column("Flat basic", justify="right")
    table.add_column("Hi-Lo spread", justify="right")
    rows = [
        ("Settled hands", f"{flat_stats.hands:,}", f"{hilo_stats.hands:,}"),
        ("Average bet", f"${flat_stats.avg_bet:,.2f}", f"${hilo_stats.avg_bet:,.2f}"),
        (
            "Total wagered",
            f"${flat_stats.wagered:,.2f}",
            f"${hilo_stats.wagered:,.2f}",
        ),
        ("Net result", f"{flat_stats.net:+,.2f}", f"{hilo_stats.net:+,.2f}"),
        (
            "House edge",
            f"{flat_stats.house_edge_percent:+.3f}%",
            f"{hilo_stats.house_edge_percent:+.3f}%",
        ),
        (
            "Player edge",
            f"{-flat_stats.house_edge_percent:+.3f}%",
            f"{-hilo_stats.house_edge_percent:+.3f}%",
        ),
        (
            "Strategy adherence",
            f"{flat_stats.adherence_percent:.2f}%",
            f"{hilo_stats.adherence_percent:.2f}%",
        ),
        (
            "Final bankroll",
            f"${flat_stats.final_bankroll:,.2f}",
            f"${hilo_stats.final_bankroll:,.2f}",
        ),
    ]
    for label, flat_value, hilo_value in rows:
        table.add_row(label, flat_value, hilo_value)
    console.print(table)
    console.print(
        f"[dim]{elapsed:.1f}s for {args.simulate:,} rounds each. "
        "House edge is positive when the house wins, so a negative "
        "house edge is a player edge.[/dim]"
    )

    if args.html:
        from .charts import compare_curves

        compare_curves({"Flat basic": flat, "Hi-Lo spread": hilo}).write_html(
            args.html, include_plotlyjs="cdn"
        )
        console.print(f"Comparison chart written to {args.html}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command line parser."""
    parser = argparse.ArgumentParser(
        prog="blackjack",
        description="Playable blackjack table and Monte Carlo simulator.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument("--bankroll", type=float, default=1000.0, help="starting chips")
    parser.add_argument("--bet", type=float, default=25.0, help="default wager")
    parser.add_argument("--decks", type=int, default=6, help="decks per shoe")
    parser.add_argument(
        "--penetration",
        type=float,
        default=0.75,
        help="fraction of the shoe dealt before the cut card",
    )
    parser.add_argument(
        "--hit-soft-17",
        action="store_true",
        help="dealer hits soft 17 (default is stand on soft 17)",
    )
    parser.add_argument(
        "--trainer",
        action="store_true",
        help="show the Hi-Lo count, bet guide and insurance hint",
    )
    parser.add_argument(
        "--hint", action="store_true", help="show the basic strategy hint"
    )
    parser.add_argument("--demo", action="store_true", help="run the bot leaderboard")
    parser.add_argument(
        "--simulate",
        type=int,
        default=0,
        metavar="N",
        help="run N rounds for flat and Hi-Lo and print the comparison",
    )
    parser.add_argument(
        "--rounds", type=int, default=1000, help="rounds per bot in demo"
    )
    parser.add_argument("--seed", type=int, default=None, help="random seed")
    parser.add_argument(
        "--html", default=None, help="write a comparison chart HTML file"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for ``python -m blackjack``."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.demo:
        return run_demo(args)
    if args.simulate > 0:
        return run_report(args)
    return play_interactive(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
