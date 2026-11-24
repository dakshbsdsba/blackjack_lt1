"""Fixtures shared by the test suite."""

from __future__ import annotations

import pytest

from blackjack import BlackjackGame, Rules


@pytest.fixture
def game() -> BlackjackGame:
    """A fresh table with a large bankroll and decision logging on."""
    return BlackjackGame(Rules(), 1000.0, seed=1)


@pytest.fixture
def rich_game() -> BlackjackGame:
    """A table with enough chips for doubles and repeated splits."""
    return BlackjackGame(Rules(), 1000.0, seed=2)
