"""Command line entry point tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from blackjack.cli import build_parser, main


def test_parser_defaults() -> None:
    """The parser exposes the documented defaults."""
    args = build_parser().parse_args([])
    assert args.bankroll == 1000.0
    assert args.bet == 25.0
    assert args.decks == 6
    assert args.penetration == 0.75
    assert not args.hit_soft_17
    assert not args.demo
    assert args.simulate == 0


def test_simulate_report(capsys: pytest.CaptureFixture[str]) -> None:
    """The non-interactive report runs and prints the headline metrics."""
    code = main(
        ["--simulate", "500", "--bet", "5", "--bankroll", "1000", "--seed", "61"]
    )
    assert code == 0
    output = capsys.readouterr().out
    assert "House edge" in output
    assert "Player edge" in output
    assert "Strategy adherence" in output
    assert "Settled hands" in output
    assert "Hi-Lo spread" in output


def test_demo_report(capsys: pytest.CaptureFixture[str]) -> None:
    """The bot demo prints a leaderboard with full bot names."""
    code = main(["--demo", "--rounds", "120", "--seed", "62"])
    assert code == 0
    output = capsys.readouterr().out
    assert "Rank" in output
    assert "Martingale" in output
    assert "Hi-Lo spread" in output
    assert "Basic strategy" in output


def test_interactive_round_and_quit(capsys: pytest.CaptureFixture[str]) -> None:
    """A complete interactive round can be played and the table closed."""
    answers = iter(["25", "stand", "q"])
    with patch("blackjack.cli.Prompt.ask", side_effect=lambda *a, **k: next(answers)):
        with patch("blackjack.cli.Confirm.ask", return_value=False):
            code = main(["--seed", "1", "--bankroll", "1000"])
    assert code == 0
    output = capsys.readouterr().out
    assert "Table open" in output
    assert "Table closed" in output
    assert "Round:" in output


def test_interactive_quit_at_bet_prompt(capsys: pytest.CaptureFixture[str]) -> None:
    """Quitting immediately closes the table without dealing."""
    with patch("blackjack.cli.Prompt.ask", return_value="q"):
        code = main(["--seed", "2"])
    assert code == 0
    output = capsys.readouterr().out
    assert "Table closed" in output
    assert "Dealer" not in output


def test_interactive_rejects_bad_bets(capsys: pytest.CaptureFixture[str]) -> None:
    """Non-numeric and out-of-range bets are rejected, then quit works."""
    answers = iter(["abc", "0", "999999", "q"])
    with patch("blackjack.cli.Prompt.ask", side_effect=lambda *a, **k: next(answers)):
        code = main(["--seed", "3", "--bankroll", "100"])
    assert code == 0
    output = capsys.readouterr().out
    assert "Enter a number" in output
    assert "table minimum" in output
    assert "table maximum" in output


def test_trainer_and_hint_flags(capsys: pytest.CaptureFixture[str]) -> None:
    """Trainer mode shows the count and hints show the strategy suggestion."""
    answers = iter(["25", "stand", "q"])
    with patch("blackjack.cli.Prompt.ask", side_effect=lambda *a, **k: next(answers)):
        with patch("blackjack.cli.Confirm.ask", return_value=False):
            code = main(["--seed", "1", "--trainer", "--hint"])
    assert code == 0
    output = capsys.readouterr().out
    assert "Running" in output
    assert "Bet guide" in output
    assert output.index("Bet guide") < output.index("Seat")
    assert "Basic strategy says" in output

    answers = iter(["25", "n", "stand", "q"])
    with patch("blackjack.cli.Prompt.ask", side_effect=lambda *a, **k: next(answers)):
        with patch("blackjack.cli.Confirm.ask", return_value=False):
            code = main(["--seed", "4", "--trainer"])
    assert code == 0
    output = capsys.readouterr().out
    assert "Insurance hint: DECLINE" in output


def test_table_rules_can_be_configured(capsys: pytest.CaptureFixture[str]) -> None:
    """Deck count, penetration and H17 are passed through to the table."""
    answers = iter(["q"])
    with patch("blackjack.cli.Prompt.ask", side_effect=lambda *a, **k: next(answers)):
        code = main(["--decks", "2", "--penetration", "0.5", "--hit-soft-17"])
    assert code == 0
    output = capsys.readouterr().out
    assert "2 decks" in output
    assert "H17" in output
