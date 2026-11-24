# Blackjack simulator

A playable blackjack table and a Monte Carlo research tool in one Python project. The rules engine, basic strategy chart, Hi-Lo counter, betting bots and Plotly charts are separate modules. A demonstration notebook walks through every tier, and the same functions are covered by 510 pytest tests.

Built as a group project for a Python programming course.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Play at the terminal:

```bash
python -m blackjack
```

Place a bet, then use `h` hit, `s` stand, `d` double, `p` split and `r` surrender. `python -m blackjack --help` lists the table options. `--trainer` shows the running and true count on every hand, and `--hint` shows the basic strategy recommendation before you act.

Run the automated bot competition:

```bash
python -m blackjack --demo --rounds 1000
```

Run a flat-bet Monte Carlo report:

```bash
python -m blackjack --simulate 100000 --bet 10 --bankroll 1000000
```

Open the notebook:

```bash
jupyter notebook notebooks/Prog_Project.ipynb
```

## Rules implemented

| Rule | Default |
| --- | --- |
| Decks | 6, configurable from 1 to 8 |
| Cut card | 75 percent penetration, configurable |
| Dealer | Hits to 17, stands on soft 17 |
| Blackjack | Pays 3:2 |
| Double | Any two cards, after split allowed |
| Split | Up to 4 hands, same-rank pairs |
| Re-split aces | Off by default |
| Split aces | One card each, no hit |
| Surrender | Late surrender, two-card original hand only |
| Insurance | Offered on an ace, pays 2:1 |
| Dealer peek | On ace or ten, American rules |

The table can run H17 with `--hit-soft-17`. The `Rules` dataclass validates every setting.

## Project layout

```text
blackjack/
  cards.py       Card, multi-deck shoe, cut card, discard tray
  hand.py        Hand totals, soft aces, pairs, split flags
  rules.py       Validated table rules
  engine.py      Round state machine, dealer play, settlement
  strategy.py    Full basic strategy chart and fallbacks
  counting.py    Hi-Lo running count and true count
  analytics.py   House edge, streaks, drawdown, adherence
  bots.py        Flat, Martingale, Hi-Lo spread and Kelly bots
  simulation.py  Monte Carlo runs and shared-shoe leaderboard
  charts.py      Plotly dashboard, curves and heatmaps
  cli.py         Rich terminal table, demo and report modes
tests/           510 pytest tests
notebooks/
  Prog_Project.ipynb   Tier by tier demonstration with live outputs
pyproject.toml   Package metadata, pytest, black and flake8 config
requirements.txt
```

## The notebook

`notebooks/Prog_Project.ipynb` is the presentation layer requested for the project. It imports the package and demonstrates:

1. Card values, flexible aces and the shoe.
2. A complete hand through the engine and a 3:2 natural payout.
3. Splits, surrender, insurance availability and the strategy chart.
4. Session analytics with strategy adherence.
5. Shoe penetration and shuffling.
6. Hi-Lo running and true count accounting.
7. A 200,000 hand Monte Carlo run and the interactive dashboard.
8. Count profitability buckets and a comparison of flat betting with a Hi-Lo spread.
9. The five-bot leaderboard.
10. The test suite result.

The notebook is executed end to end, and its outputs are stored in the file.

## Testing and code quality

```bash
python -m pytest -q                 # full suite, including slow Monte Carlo tests
python -m pytest -q -m "not slow"   # quick suite
python -m black --check blackjack tests
python -m flake8 blackjack tests
```

The suite covers chip accounting, all payout types, dealer soft-17 behaviour, every basic strategy cell against an independent chart, split state isolation, count accounting, Monte Carlo convergence, bot bet sizing, analytics math and the CLI.

## Bankroll accounting

A bet is deducted when the hand starts. A win returns the stake plus an equal profit, a blackjack returns the stake plus 1.5 times the stake, a push returns the stake, and a surrender returns half the stake. Doubles and splits post an additional bet of the original size. Insurance is a separate half-unit bet that pays 2:1 when the dealer has a natural. `total_wagered` includes insurance, so the reported house edge is the net result divided by all money put at risk.

## Results from the verification run

| Check | Result |
| --- | --- |
| Full test suite | 510 passed |
| Flat basic strategy, 300,000 rounds | House edge 0.347 percent over 308,277 settled hands |
| Flat basic strategy, notebook run | House edge 0.394 percent over 205,529 settled hands |
| Hi-Lo spread, 100,000 rounds | Player edge 0.508 percent over 102,755 settled hands |
| black | 25 files unchanged |
| flake8 | No findings |
| Notebook | Executed end to end with no error outputs |

The slow tests in `tests/test_simulation.py` enforce the Monte Carlo tolerances. The notebook cells reproduce the charts and the summary numbers.

## Notes

The strategy chart is the standard multi-deck chart for a game with dealer stands on soft 17, double after split and late surrender. It assumes the American peek rule, which is why eleven doubles against an ace.

The bots in the competition share one shoe and take turns, so every card dealt to one bot is seen by the others. Each bot keeps its own bankroll, decisions and drawdown.

The terminal UI is built with Rich. It uses the app's own prompts, not browser dialogs.
