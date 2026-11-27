# Blackjack simulator

A playable blackjack table and a Monte Carlo research tool in one Python project. The rules engine, basic strategy chart, Hi-Lo counter, betting bots and Plotly charts are separate modules. A demonstration notebook walks through every tier, and the same functions are covered by 513 pytest tests.

Built as a group project for PROG1301, a Python programming course, by Daksh, Julia, Clark, Victoria and Ziah.

## Division of labor

All five members listed below are part of the project and the submission. The roles match the presenter assignments in the 13-slide deck. The codebase is shared, but each person owned the following areas and was the primary presenter for the listed slides.

| Member | Role | Primary ownership | Deck slides |
| --- | --- | --- | --- |
| Daksh | Lead: integration and flow | End-to-end system, round state machine, module handoffs, repo integration, final demo, CLI Live Demo | 1, 4, 9 |
| Julia | Technical: strategy and numbers | Basic strategy chart, Hi-Lo counting, Monte Carlo, risk charts, numerical checks | 7, 8, 10 |
| Clark | Engine: rules and tests | Cards, hand values, dealer policy, settlement, pytest suite, engine edge cases | 5, 11 |
| Victoria | Delivery: demo and speaking | Table walkthrough, player actions, terminal UI polish, live narration, limits and next | 3, 12 |
| Ziah | Framing: rules and recall | Rules and edge framing, key terms, payout definitions, Q&A prompts | 2, 6 |

**Shared work.** Every member can run the app and the notebook, reviewed the deck, and contributed to the final integration. The table is the primary division, not a fence around contributions.

Slide 13 is the group Q&A, hosted by all five.

**Artifacts by area.**

- Daksh: `blackjack/engine.py` state machine, `blackjack/cli.py` integration, `presentation/` delivery.
- Julia: `blackjack/strategy.py`, `blackjack/counting.py`, `blackjack/simulation.py`, `blackjack/charts.py`, notebook analysis.
- Clark: `blackjack/cards.py`, `blackjack/hand.py`, `blackjack/rules.py`, dealer and settlement paths in `blackjack/engine.py`, `tests/`.
- Victoria: `blackjack/cli.py` table flow, demo script, `presentation/` narration, UI checks and the limits slide.
- Ziah: rules-and-edge framing, glossary, definitions, payout definitions, Q&A prompts.

The 13-slide deck is `presentation/blackjack_presentation.html`. The previous 22-slide build remains in commit history, and the notebook still demonstrates the material that was cut from the talk.

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

Place a bet, then use `h` hit, `s` stand, `d` double, `p` split and `r` surrender. `python -m blackjack --help` lists the table options. `--trainer` shows the running and true count, the pre-bet unit guide and the insurance hint, and `--hint` shows the basic strategy recommendation before you act.

Run the automated bot competition:

```bash
python -m blackjack --demo --rounds 1000
```

Run a flat and Hi-Lo Monte Carlo comparison:

```bash
python -m blackjack --simulate 100000 --bet 10 --bankroll 1000000 --seed 7
```

Add `--html comparison.html` to write the bankroll and EV comparison chart.

Open the notebook:

```bash
jupyter notebook notebooks/Prog_Project.ipynb
```

## Presentation

`presentation/blackjack_presentation.html` is a single self-contained 13-slide deck with live demos, speaker notes, a timer and keyboard controls. The presented slides are deliberately sparse. The detailed mechanics live in the speaker notes. Open it directly in a browser, or serve the folder with `python3 presentation/serve.py --port 8088 --root presentation --state /tmp/blackjack-notes` to enable the editable shared notes. See `presentation/README.md` for the controls, notes API and data builder.

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
tests/           513 pytest tests
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
7. A 100,000 hand Monte Carlo run for flat and Hi-Lo, plus the interactive dashboard.
8. Count profitability buckets and a comparison of flat betting with a Hi-Lo spread.
9. The five-bot leaderboard.
10. The test suite result.
11. Trainer mode with the bet guide and insurance hint.

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

## Run the Monte Carlo comparison

The full flat-versus-Hi-Lo simulation is:

```bash
python -m blackjack --simulate 100000 --bet 10 --bankroll 1000000
```

It runs both strategies on the same seed, prints the side-by-side result table, and reports both house edge and player edge. Add `--html comparison.html` to write the bankroll and EV comparison chart.

## Why the core simulator is loop-based, not vectorized

The engine is intentionally a per-hand loop. Blackjack is path-dependent: each card changes the legal actions, a split creates several hands with independent bets and state, and the dealer only plays after the player finishes. A vectorized version would need masks for every state, split hand, dealer draw and settlement path. That would make the rules harder to read and much easier to get subtly wrong.

The loop keeps one hand as one explicit path through the state machine. That is the main design tradeoff: readability and rule fidelity over raw throughput. The 100,000-round comparison takes seconds, which is fast enough for this project. The loop is also why the tests can assert exact transitions and hand results.

Vectorization is used where it fits. NumPy handles the settled-hand arrays, drawdowns and chart series, and pandas builds the comparison tables. If throughput became the priority, the next step would be parallel independent trials with multiprocessing or Numba, not vectorizing the inside of a single hand.

## Results from the verification run

| Check | Result |
| --- | --- |
| Full test suite | 513 passed |
| Flat basic strategy, 300,000 rounds | House edge 0.347 percent over 308,277 settled hands |
| Flat basic strategy, notebook run | House edge 0.121 percent over 102,755 settled hands |
| Hi-Lo spread, 100,000 rounds | Player edge 0.501 percent over 102,755 settled hands |
| black | 25 files unchanged |
| flake8 | No findings |
| Notebook | Executed end to end with no error outputs |

The slow tests in `tests/test_simulation.py` enforce the Monte Carlo tolerances. The notebook cells reproduce the charts and the summary numbers.

## Notes

The strategy chart is the standard multi-deck chart for a game with dealer stands on soft 17, double after split and late surrender. It assumes the American peek rule, which is why eleven doubles against an ace.

The bots in the competition share one shoe and take turns, so every card dealt to one bot is seen by the others. Each bot keeps its own bankroll, decisions and drawdown.

The terminal UI is built with Rich. It uses the app's own prompts, not browser dialogs.
