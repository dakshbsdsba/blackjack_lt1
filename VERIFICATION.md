# Verification report

Project: Blackjack simulator
Environment: Python 3.12.3, Linux arm64, virtual environment in `.venv`

This report maps every requirement in the proposal to the code that implements it, the test that proves it, and the place a reviewer can see it running.

## Gate results

| Gate | Command | Result |
| --- | --- | --- |
| Full test suite | `python -m pytest -q` | 513 passed in 28.22s |
| Quick test suite | `python -m pytest -q -m "not slow"` | 510 passed, 3 deselected |
| Formatting | `python -m black --check blackjack tests` | 25 files unchanged |
| Linting | `python -m flake8 blackjack tests` | Exit 0, no findings |
| Notebook execution | `nbclient` with the project kernel | Executed end to end, zero error outputs |
| CLI smoke test | `python -m blackjack --simulate 2000` | Report rendered, exit 0 |
| Bot demo | `python -m blackjack --demo --rounds 300` | Five ranked bots, exit 0 |

## Tier 1: basic goals

| Requirement | Implementation | Proof |
| --- | --- | --- |
| Deal initial cards | `BlackjackGame.start_hand` in `blackjack/engine.py` | `tests/test_engine_basic.py::test_initial_deal_and_bankroll` |
| Flexible ace values | `Hand.total`, `Hand.is_soft`, `Hand.hard_total` in `blackjack/hand.py` | `tests/test_hand.py` (six ace cases) |
| Hit and stand | `BlackjackGame.act`, `_advance` | `test_stand_win_pays_even_money`, `test_hitting_to_twenty_one_auto_stands` |
| Dealer hits until 17 | `_dealer_play` | `test_dealer_hits_until_seventeen` |
| Dealer stands on soft 17 | `_dealer_play` with `Rules.dealer_stands_soft_17` | `test_dealer_stands_on_soft_seventeen`, `test_dealer_hits_soft_seventeen_when_configured` |
| Wins, losses and pushes | `_settle` | `test_stand_win_pays_even_money`, `test_regular_push`, `test_bust_loses_and_dealer_does_not_draw` |
| Blackjack pays 3:2 | `_settle` with `Rules.blackjack_payout` | `test_blackjack_pays_three_to_two`, `test_custom_blackjack_payout` |
| Clean user interface, bets, hands, shoe, chips | `blackjack/cli.py` with Rich | `python -m blackjack`, notebook Tier 1 |
| Chip balance never negative on valid bets | `start_hand` validation, `available_actions` bankroll guards | `test_invalid_bets_are_rejected`, `test_bankroll_never_negative_and_ledger_balances` |
| Dealer soft-17 sanity across multi-hand play | Dealer rule is independent of hand count | `test_dealer_stands_on_soft_seventeen`, plus 300,000 hand Monte Carlo run |

## Tier 2: intermediate goals

| Requirement | Implementation | Proof |
| --- | --- | --- |
| Double down | `act("double")`, second bet posted, one card, auto stand | `test_double_posts_a_second_bet_and_draws_once`, `test_double_not_available_after_a_hit` |
| Splitting pairs | `_split`, up to four hands | `tests/test_splits.py` |
| Re-splitting rules | `max_split_hands`, `resplit_aces`, `double_after_split` | `test_resplit_is_allowed_up_to_the_limit`, `test_max_split_hands_is_enforced`, `test_resplit_aces_disallowed_by_default` |
| Surrender | Late surrender, original two-card hand only | `test_surrender_returns_half_the_bet`, `test_surrender_not_available_after_hit`, `test_surrender_is_not_available_after_split` |
| Insurance | Half-unit side bet, pays 2:1, offered on ace | `test_insurance_lost_when_dealer_has_no_blackjack`, `test_insurance_pays_two_to_one_on_dealer_blackjack`, `test_declining_insurance_keeps_the_chips` |
| Basic strategy matrix | `blackjack/strategy.py` hard, soft and pair tables with fallbacks | `tests/test_strategy.py`, 376 cases |
| Strategy consistency benchmarking | Independent rule-based reference chart in the test file, all totals and upcards | 376 parameterised cases across hard 5-21, soft 12-20, all pairs, four availability combinations |
| Session analytics | `blackjack/analytics.py` | `tests/test_analytics.py`, notebook session cell |
| House edge calculation | Net result divided by total wagered | `test_analytics_from_arrays` |
| Win, loss and push streaks | `_streaks` | `test_streaks_with_pushes_breaking_runs` |
| Bankroll drawdown curve | `drawdown_series`, `max_drawdown` | `test_drawdown_series`, dashboard chart |
| Strategy adherence | Decision log with optimal action comparison | `test_run_bot_logs_decisions`, notebook session cell shows 100 percent |
| Split state without bleed | Independent `Hand` objects and bets | `test_split_hands_pay_out_without_state_bleed`, `test_split_hands_have_independent_wagers`, `test_split_twenty_one_is_not_blackjack` |

## Tier 3: advanced goals

| Requirement | Implementation | Proof |
| --- | --- | --- |
| Multi-deck shoe | `Shoe` in `blackjack/cards.py`, 1 to 8 decks | `test_shoe_composition` |
| Automatic shuffle at the cut card | `Shoe.needs_shuffle`, `shuffle_if_needed` | `test_cut_card_and_shuffle`, `test_counter_resets_when_the_shoe_is_shuffled` |
| Discard tray management | `Shoe.discard_tray`, cleared on shuffle | `test_draw_removes_cards_and_fills_discard`, penetration notebook cell |
| Hi-Lo system | `HiLoCounter`, `Card.hi_lo_value` | `tests/test_counting.py` |
| Running count | `HiLoCounter.observe` | `test_count_cards_sequence`, `test_counter_observe_and_reset` |
| True count from remaining decks | `true_count`, floored at half a deck | `test_true_count_divides_by_remaining_decks` |
| Count accounting against dealing history | Engine syncs every settled card | `test_engine_counter_matches_dealt_history`, `test_count_accounting_over_a_scripted_split` |
| Batch simulations | `run_simulation`, `run_bot` in `blackjack/simulation.py` | `test_run_simulation_shapes`, `test_run_simulation_is_reproducible` |
| Betting bots that scale with the count | `HiLoSpreadBot`, `KellyBot` | `test_hilo_spread_scales_with_true_count`, `test_kelly_bet_is_fractional_and_capped` |
| Progression bot | `MartingaleBot` | `test_martingale_progression`, `test_martingale_resets_after_push` |
| Concurrent leaderboard | `run_competition`, shared shoe | `test_run_competition_ranks_bots`, notebook leaderboard cell |
| Monte Carlo house edge convergence | Slow test with 300,000 rounds | `test_house_edge_converges_to_theoretical`, observed 0.347 percent |
| Counting profitability | Slow paired comparison and count buckets | `test_counting_improves_the_edge`, `test_high_true_counts_are_profitable`, notebook chart |

## Visualisations and readability

| Requirement | Implementation | Proof |
| --- | --- | --- |
| PEP8 and formatting | black and flake8, line length 88 | Both gates clean |
| Full type hints | Every public function and method annotated | Source inspection |
| Comprehensive docstrings | Every module, class and public method | Source inspection |
| Multi-pane interactive Plotly dashboard | `charts.dashboard` with bankroll, outcomes, drawdown and adherence | Notebook output |
| Bankroll trajectory and theoretical EV | `charts.bankroll_trajectory`, `expected_value_curve` | Notebook output |
| Win, loss and push distribution | `charts.outcome_distribution` | Dashboard panel |
| Strategy adherence | `charts.strategy_adherence` and dashboard panel | Dashboard output |
| Risk heatmap by hand and upcard | `charts.risk_heatmap` | Notebook output |
| Underwater drawdown plot | `charts.drawdown_chart` and dashboard panel | Notebook output |
| Count profitability chart | `charts.count_profitability` | Notebook output |

## Observed Monte Carlo results

Flat basic strategy, 300,000 rounds, seed 101:

| Metric | Value |
| --- | --- |
| Settled hands | 308,277 |
| Total wagered | 3,405,060 |
| Net result | -11,805 |
| House edge | 0.3467 percent |
| Wins | 131,415 |
| Losses | 138,157 |
| Pushes | 25,432 |
| Blackjacks | 13,472 |
| Surrenders | 13,273 |

Flat basic strategy, 200,000 rounds, notebook seed 7:

| Metric | Value |
| --- | --- |
| Settled hands | 205,529 |
| House edge | 0.3935 percent |
| Net result | -8,925 |
| Strategy adherence | 100 percent |

Hi-Lo spread, 100,000 rounds, notebook seed 7:

| Metric | Value |
| --- | --- |
| Settled hands | 102,755 |
| Average bet | 16.00 |
| House edge | -0.5082 percent, a player edge |
| Net result | +8,355 |

The flat-bet runs land inside the tolerance enforced by `test_house_edge_converges_to_theoretical` (0.15 to 0.85 percent). The counting run beats flat betting on the same shoe seed by about 0.9 percentage points of edge.

## Reproducing the report

```bash
cd blackjack-simulator
python -m pytest -q
python -m pytest -q -m "not slow"
python -m black --check blackjack tests
python -m flake8 blackjack tests
python -m blackjack --demo --rounds 1000
python -m blackjack --simulate 100000 --bet 10 --bankroll 1000000
```

Notebook:

```bash
python -m ipykernel install --user --name blackjack-venv
jupyter nbconvert --to notebook --execute notebooks/Prog_Project.ipynb \
  --ExecutePreprocessor.kernel_name=blackjack-venv --output /tmp/Prog_Project_executed.ipynb
```

The notebook stored in the repository already contains the outputs from that execution.
