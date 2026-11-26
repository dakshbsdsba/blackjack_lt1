"""The blackjack rules engine.

The engine is deliberately UI-free. It owns the shoe, the player's hands, the
dealer hand, the bankroll and the settlement math. A command line table, a
notebook demo or a Monte Carlo simulator all drive the same object, which is
what keeps the rules consistent across every entry point.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Sequence

from .cards import Card, Shoe
from .counting import HiLoCounter
from .hand import Hand
from .rules import Rules
from .strategy import Action, basic_strategy_action

InsurancePolicy = Callable[["BlackjackGame"], bool]
Policy = Callable[[Hand, Card, Rules, Sequence[str]], Action]


class GameState(str, Enum):
    """Lifecycle of one round."""

    IDLE = "idle"
    INSURANCE = "insurance"
    PLAYER = "player"
    SETTLED = "settled"


class Outcome(str, Enum):
    """Settlement category for one hand."""

    BLACKJACK = "blackjack"
    WIN = "win"
    LOSS = "loss"
    PUSH = "push"
    SURRENDER = "surrender"

    @property
    def is_win(self) -> bool:
        """Return True for a win or a natural blackjack."""
        return self in (Outcome.WIN, Outcome.BLACKJACK)


@dataclass(frozen=True)
class HandResult:
    """The settled result of one player hand."""

    hand_index: int
    bet: float
    net: float
    outcome: Outcome
    player_total: int
    dealer_total: int
    is_blackjack: bool
    is_doubled: bool
    is_split: bool
    surrendered: bool
    start_total: int
    dealer_upcard: str
    cards: tuple[str, ...]
    insurance_bet: float = 0.0
    insurance_net: float = 0.0

    @property
    def wagered(self) -> float:
        """Amount at risk on the hand, including a double and insurance."""
        return round(self.bet + self.insurance_bet, 2)


@dataclass(frozen=True)
class Decision:
    """One player decision, compared with basic strategy."""

    hand_index: int
    player_total: int
    is_soft: bool
    dealer_upcard: str
    action: Action
    optimal: Action
    correct: bool
    cards: tuple[str, ...]


def basic_strategy_policy(
    hand: Hand,
    dealer_upcard: Card,
    rules: Rules,
    available: Sequence[str],
) -> Action:
    """Choose an action using the basic strategy chart and legal actions."""
    return basic_strategy_action(
        hand,
        dealer_upcard,
        rules,
        can_double="double" in available,
        can_split="split" in available,
        can_surrender="surrender" in available,
    )


class BlackjackGame:
    """A single-player blackjack table with a persistent shoe and bankroll."""

    def __init__(
        self,
        rules: Rules | None = None,
        bankroll: float = 1000.0,
        *,
        shoe: Shoe | None = None,
        seed: int | None = None,
        log_decisions: bool = True,
    ) -> None:
        self.rules = rules or Rules()
        if bankroll < 0:
            raise ValueError("bankroll must not be negative")
        self.bankroll = float(bankroll)
        self.shoe = shoe or Shoe(
            self.rules.num_decks,
            self.rules.penetration,
            seed=seed,
        )
        self.log_decisions = log_decisions

        self.counter = HiLoCounter(self.rules.num_decks)
        self._count_index = 0
        self._sync_counter()

        self.state: GameState = GameState.IDLE
        self.hands: list[Hand] = []
        self.dealer: Hand = Hand()
        self.current = 0
        self.insurance_bet = 0.0
        self.round_results: list[HandResult] = []
        self.round_decisions: list[Decision] = []
        self.history: list[HandResult] = []
        self.decision_history: list[Decision] = []
        self.total_wagered = 0.0
        self.total_net = 0.0
        self.hands_played = 0

    # ------------------------------------------------------------------
    # Convenience state
    # ------------------------------------------------------------------
    @property
    def player_hand(self) -> Hand:
        """The hand currently being acted on."""
        if not self.hands:
            raise RuntimeError("No hand is in progress")
        return self.hands[self.current]

    @property
    def true_count(self) -> float:
        """True count for the current shoe, including every settled card."""
        return self.counter.true_count(self.shoe.decks_remaining)

    @property
    def running_count(self) -> int:
        """Hi-Lo running count for the current shoe."""
        return self.counter.running_count

    @property
    def round_net(self) -> float:
        """Net result of the round in progress, or the last finished round."""
        return round(sum(result.net for result in self.round_results), 2)

    @property
    def is_round_over(self) -> bool:
        """Return True when the round has been settled."""
        return self.state is GameState.SETTLED

    # ------------------------------------------------------------------
    # Round setup
    # ------------------------------------------------------------------
    def start_hand(self, bet: float) -> None:
        """Post a bet, deal the cards, and offer insurance when relevant."""
        if self.state not in (GameState.IDLE, GameState.SETTLED):
            raise RuntimeError("Finish the current round before starting another")
        bet = round(float(bet), 2)
        if bet < self.rules.min_bet:
            raise ValueError(f"Bet must be at least {self.rules.min_bet:g}")
        if bet > self.rules.max_bet:
            raise ValueError(f"Bet must be at most {self.rules.max_bet:g}")
        if bet > self.bankroll + 1e-9:
            raise ValueError("Bet exceeds the available bankroll")

        self._sync_counter()
        if self.shoe.needs_shuffle:
            self.shoe.shuffle()
            self.counter.reset()
            self._count_index = 0

        self.hands = [Hand(bet=bet)]
        self.dealer = Hand()
        self.current = 0
        self.insurance_bet = 0.0
        self.round_results = []
        self.round_decisions = []
        self.state = GameState.PLAYER
        self._last_bankroll = self.bankroll

        self.bankroll = round(self.bankroll - bet, 2)
        self.total_wagered += bet
        self.hands_played += 1

        player = self.hands[0]
        player.add(self._draw())
        self.dealer.add(self._draw())
        player.add(self._draw())
        self.dealer.add(self._draw())
        player.start_total = player.total

        upcard = self.dealer.cards[0]
        if self.rules.insurance_enabled and upcard.is_ace:
            self.state = GameState.INSURANCE
            return
        if self._resolve_naturals():
            return
        self.state = GameState.PLAYER

    def take_insurance(self, take: bool) -> None:
        """Resolve the insurance offer and continue or settle the round."""
        if self.state is not GameState.INSURANCE:
            raise RuntimeError("Insurance is not on offer")
        if take:
            amount = round(self.hands[0].bet / 2, 2)
            if amount > self.bankroll + 1e-9:
                raise ValueError("Not enough bankroll for insurance")
            self.bankroll = round(self.bankroll - amount, 2)
            self.insurance_bet = amount
            self.total_wagered += amount

        if self.dealer.is_blackjack:
            if self.insurance_bet:
                self.bankroll = round(self.bankroll + self.insurance_bet * 3, 2)
            self._settle(dealer_blackjack=True)
            return
        # The insurance bet is lost when the dealer does not have blackjack.
        if self.hands[0].is_blackjack:
            self._settle()
            return
        self.state = GameState.PLAYER

    def _resolve_naturals(self) -> bool:
        """Settle a natural or a dealer blackjack. Return True when settled."""
        upcard = self.dealer.cards[0]
        if (upcard.is_ace or upcard.is_ten) and self.dealer.is_blackjack:
            self._settle(dealer_blackjack=True)
            return True
        if self.hands[0].is_blackjack:
            self._settle()
            return True
        return False

    # ------------------------------------------------------------------
    # Legal actions
    # ------------------------------------------------------------------
    def available_actions(self) -> list[Action]:
        """Return the legal actions for the current hand."""
        if self.state is not GameState.PLAYER or not self.hands:
            return []
        hand = self.player_hand
        if hand.is_finished:
            return []

        actions: list[Action] = ["hit", "stand"]
        can_double = (
            len(hand.cards) == 2
            and self.bankroll + 1e-9 >= hand.bet
            and (not hand.is_split_hand or self.rules.double_after_split)
            and not (hand.from_split_aces and not self.rules.hit_split_aces)
        )
        if can_double:
            actions.append("double")
        if self._can_split(hand):
            actions.append("split")
        if (
            self.rules.late_surrender
            and len(hand.cards) == 2
            and not hand.is_split_hand
        ):
            actions.append("surrender")
        return actions

    def _can_split(self, hand: Hand) -> bool:
        """Return True when the hand may be split under the table rules."""
        if not hand.is_pair:
            return False
        if len(self.hands) >= self.rules.max_split_hands:
            return False
        if self.bankroll + 1e-9 < hand.bet:
            return False
        if hand.from_split_aces and not self.rules.resplit_aces:
            return False
        return True

    # ------------------------------------------------------------------
    # Player actions
    # ------------------------------------------------------------------
    def act(self, action: str) -> None:
        """Apply one player action to the current hand."""
        if self.state is not GameState.PLAYER:
            raise RuntimeError("The table is not accepting player actions")
        action = action.lower().strip()
        available = self.available_actions()
        if action not in available:
            raise ValueError(f"Illegal action {action!r}; legal actions: {available}")

        hand = self.player_hand
        if self.log_decisions:
            optimal = basic_strategy_action(
                hand,
                self.dealer.cards[0],
                self.rules,
                can_double="double" in available,
                can_split="split" in available,
                can_surrender="surrender" in available,
            )
            decision = Decision(
                hand_index=self.current,
                player_total=hand.total,
                is_soft=hand.is_soft,
                dealer_upcard=self._dealer_key(),
                action=action,  # type: ignore[arg-type]
                optimal=optimal,
                correct=action == optimal,
                cards=tuple(str(card) for card in hand.cards),
            )
            self.round_decisions.append(decision)
            self.decision_history.append(decision)

        if action == "hit":
            hand.add(self._draw())
            if hand.is_bust or hand.total == 21:
                hand.stood = True
            self._advance()
        elif action == "stand":
            hand.stood = True
            self._advance()
        elif action == "double":
            self.bankroll = round(self.bankroll - hand.bet, 2)
            self.total_wagered += hand.bet
            hand.bet = round(hand.bet * 2, 2)
            hand.is_doubled = True
            hand.add(self._draw())
            hand.stood = True
            self._advance()
        elif action == "split":
            self._split(hand)
        elif action == "surrender":
            hand.surrendered = True
            hand.stood = True
            self._advance()

    def _split(self, hand: Hand) -> None:
        """Split the current hand into two independent hands."""
        if not self._can_split(hand):
            raise ValueError("Hand cannot be split")
        second = hand.cards.pop()
        ace_split = hand.cards[0].is_ace
        new_hand = Hand(
            cards=[second],
            bet=hand.bet,
            is_split_hand=True,
            from_split_aces=ace_split,
        )
        hand.is_split_hand = True
        hand.from_split_aces = ace_split

        self.bankroll = round(self.bankroll - hand.bet, 2)
        self.total_wagered += hand.bet

        hand.add(self._draw())
        new_hand.add(self._draw())
        self.hands.insert(self.current + 1, new_hand)
        hand.start_total = hand.total
        new_hand.start_total = new_hand.total

        if ace_split and not self.rules.hit_split_aces:
            hand.stood = True
            new_hand.stood = True
        else:
            if hand.total == 21:
                hand.stood = True
            if new_hand.total == 21:
                new_hand.stood = True
        self._advance()

    def _advance(self) -> None:
        """Move to the next unfinished hand, then run the dealer and settle."""
        while self.current < len(self.hands) and self.hands[self.current].is_finished:
            self.current += 1
        if self.current >= len(self.hands):
            live = any(not hand.is_bust and not hand.surrendered for hand in self.hands)
            if live:
                self._dealer_play()
            self._settle()

    # ------------------------------------------------------------------
    # Dealer and settlement
    # ------------------------------------------------------------------
    def _dealer_play(self) -> None:
        """Draw for the dealer until the table's standing rule is met."""
        while True:
            total = self.dealer.total
            if total < 17:
                self.dealer.add(self._draw())
            elif total == 17 and self.dealer.is_soft and self.rules.dealer_hits_soft_17:
                self.dealer.add(self._draw())
            else:
                return

    def _settle(self, dealer_blackjack: bool = False) -> None:
        """Pay every hand, record results, and close the round."""
        if self.state is GameState.SETTLED:
            return
        dealer_total = self.dealer.total
        upcard = self._dealer_key()

        for index, hand in enumerate(self.hands):
            bet = hand.bet
            if hand.surrendered:
                payout = round(bet / 2, 2)
                net = round(-bet / 2, 2)
                outcome = Outcome.SURRENDER
            elif dealer_blackjack:
                if hand.is_blackjack:
                    payout = bet
                    net = 0.0
                    outcome = Outcome.PUSH
                else:
                    payout = 0.0
                    net = -bet
                    outcome = Outcome.LOSS
            elif hand.is_blackjack:
                payout = round(bet * (1 + self.rules.blackjack_payout), 2)
                net = round(bet * self.rules.blackjack_payout, 2)
                outcome = Outcome.BLACKJACK
            elif hand.is_bust:
                payout = 0.0
                net = -bet
                outcome = Outcome.LOSS
            elif self.dealer.is_bust or hand.total > dealer_total:
                payout = round(bet * 2, 2)
                net = bet
                outcome = Outcome.WIN
            elif hand.total < dealer_total:
                payout = 0.0
                net = -bet
                outcome = Outcome.LOSS
            else:
                payout = bet
                net = 0.0
                outcome = Outcome.PUSH

            insurance_bet = 0.0
            insurance_net = 0.0
            if index == 0 and self.insurance_bet:
                insurance_bet = self.insurance_bet
                insurance_net = (
                    round(self.insurance_bet * 2, 2)
                    if dealer_blackjack
                    else -self.insurance_bet
                )
                net = round(net + insurance_net, 2)

            self.bankroll = round(self.bankroll + payout, 2)
            self.total_net = round(self.total_net + net, 2)
            result = HandResult(
                hand_index=index,
                bet=bet,
                net=net,
                outcome=outcome,
                player_total=hand.total,
                dealer_total=dealer_total,
                is_blackjack=hand.is_blackjack,
                is_doubled=hand.is_doubled,
                is_split=hand.is_split_hand,
                surrendered=hand.surrendered,
                start_total=hand.start_total or hand.total,
                dealer_upcard=upcard,
                cards=tuple(str(card) for card in hand.cards),
                insurance_bet=insurance_bet,
                insurance_net=insurance_net,
            )
            self.round_results.append(result)
            self.history.append(result)

        self._sync_counter()
        self.state = GameState.SETTLED

    # ------------------------------------------------------------------
    # Automation helpers
    # ------------------------------------------------------------------
    def play_hand(
        self,
        bet: float,
        policy: Policy = basic_strategy_policy,
        insurance_policy: InsurancePolicy | None = None,
        *,
        max_actions: int = 100,
    ) -> list[HandResult]:
        """Play one complete round with a policy and return its results."""
        self.start_hand(bet)
        if self.state is GameState.INSURANCE:
            take = bool(insurance_policy(self)) if insurance_policy else False
            self.take_insurance(take)

        steps = 0
        while self.state is GameState.PLAYER:
            hand = self.player_hand
            available = self.available_actions()
            if not available:
                raise RuntimeError("No legal actions but the round is still live")
            action = policy(hand, self.dealer.cards[0], self.rules, available)
            if action not in available:
                raise ValueError(
                    f"Policy chose {action!r}; legal actions are {available}"
                )
            self.act(action)
            steps += 1
            if steps > max_actions:
                raise RuntimeError("Round exceeded the action limit")
        return list(self.round_results)

    # ------------------------------------------------------------------
    # Internals and status
    # ------------------------------------------------------------------
    def _draw(self) -> Card:
        """Draw one card from the shoe."""
        return self.shoe.draw_one()

    def _dealer_key(self) -> str:
        """Normalised dealer upcard key."""
        if not self.dealer.cards:
            return ""
        upcard = self.dealer.cards[0]
        return "10" if upcard.value == 10 else upcard.rank

    def _sync_counter(self) -> None:
        """Feed every newly dealt card into the Hi-Lo counter."""
        dealt = self.shoe.dealt_cards
        if len(dealt) < self._count_index:
            # The shoe was shuffled outside this game object.
            self.counter.reset()
            self._count_index = 0
        if len(dealt) > self._count_index:
            self.counter.observe_many(dealt[self._count_index :])
            self._count_index = len(dealt)

    def shoe_status(self) -> dict[str, float | int | bool]:
        """Return a snapshot of the shoe for a UI footer."""
        return {
            "cards_remaining": self.shoe.cards_remaining,
            "total_cards": self.shoe.total_cards,
            "decks_remaining": round(self.shoe.decks_remaining, 2),
            "discard_tray": self.shoe.discard_tray,
            "penetration": round(self.shoe.penetration_actual, 4),
            "needs_shuffle": self.shoe.needs_shuffle,
            "shuffle_count": self.shoe.shuffle_count,
            "running_count": self.counter.running_count,
            "true_count": round(self.true_count, 2),
        }
