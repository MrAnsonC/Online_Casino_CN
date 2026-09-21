from __future__ import annotations
import sys as _account_sys
from pathlib import Path as _AccountPath
_account_root = next((p for p in (_AccountPath(__file__).resolve().parent, *_AccountPath(__file__).resolve().parents) if (p / "A_Tools" / "Account" / "secure_json.py").is_file()), None)
if _account_root is None:
    raise RuntimeError("Cannot locate encrypted account storage")
if str(_account_root) not in _account_sys.path:
    _account_sys.path.insert(0, str(_account_root))
from A_Tools.Account import install_secure_json as _install_secure_json
_install_secure_json()
del _install_secure_json, _account_root, _AccountPath, _account_sys


import argparse
import json
import math
import os
import random
import sys
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox
from typing import Callable, Optional, Sequence

try:
    from .slot_machine import EmbeddedGamePage
except ImportError:
    try:
        from Slot_Machine.slot_machine import EmbeddedGamePage
    except ImportError:
        EmbeddedGamePage = None


VERSION = "SlotMachine-TopDollar-ClassicEstimated-AAB72-V4"
BASE_WAGER_DOLLARS = 5.0

# Internal symbols. HIDDEN_SPACE is a real blank physical stop and is not drawn.
HIDDEN_SPACE = "<HIDDEN_SPACE>"
CHERRY = "CHERRY"
BAR = "BAR"
DOUBLE_BAR = "DOUBLE_BAR"
TRIPLE_BAR = "TRIPLE_BAR"
SEVEN = "SEVEN"
DOUBLE_DIAMOND = "DOUBLE_DIAMOND"
CASH = "CASH"

BAR_SYMBOLS = frozenset({BAR, DOUBLE_BAR, TRIPLE_BAR})
VISIBLE_SYMBOLS = frozenset(
    {CHERRY, BAR, DOUBLE_BAR, TRIPLE_BAR, SEVEN, DOUBLE_DIAMOND, CASH}
)
ROW_OFFSETS = (-1, 0, 1)


# ---------------------------------------------------------------------------
# Classic-style 22-stop A-A-B physical reels and independent 72-stop maps
# ---------------------------------------------------------------------------

TOTAL_VIRTUAL_STOPS = 72

# Reels 1 and 2 share strip A. Reel 3 uses strip B and contains the CASH trigger.
A_PHYSICAL_REEL_ORDER: tuple[str, ...] = (
    HIDDEN_SPACE,      #  1
    SEVEN,             #  2
    HIDDEN_SPACE,      #  3
    BAR,               #  4
    HIDDEN_SPACE,      #  5
    CHERRY,            #  6
    HIDDEN_SPACE,      #  7
    DOUBLE_DIAMOND,    #  8
    HIDDEN_SPACE,      #  9
    BAR,               # 10
    HIDDEN_SPACE,      # 11
    TRIPLE_BAR,        # 12
    HIDDEN_SPACE,      # 13
    BAR,               # 14
    HIDDEN_SPACE,      # 15
    DOUBLE_BAR,        # 16
    HIDDEN_SPACE,      # 17
    DOUBLE_DIAMOND,    # 18
    HIDDEN_SPACE,      # 19
    TRIPLE_BAR,        # 20
    HIDDEN_SPACE,      # 21
    BAR,               # 22
)

B_PHYSICAL_REEL_ORDER: tuple[str, ...] = (
    HIDDEN_SPACE,      #  1
    SEVEN,             #  2
    HIDDEN_SPACE,      #  3
    BAR,               #  4
    HIDDEN_SPACE,      #  5
    CHERRY,            #  6
    HIDDEN_SPACE,      #  7
    DOUBLE_DIAMOND,    #  8
    HIDDEN_SPACE,      #  9
    BAR,               # 10
    HIDDEN_SPACE,      # 11
    TRIPLE_BAR,        # 12
    HIDDEN_SPACE,      # 13
    DOUBLE_BAR,        # 14
    HIDDEN_SPACE,      # 15
    BAR,               # 16
    HIDDEN_SPACE,      # 17
    DOUBLE_BAR,        # 18
    HIDDEN_SPACE,      # 19
    DOUBLE_DIAMOND,    # 20
    HIDDEN_SPACE,      # 21
    CASH,              # 22 — R3 center-line bonus trigger
)

FIXED_PHYSICAL_REELS: tuple[tuple[str, ...], ...] = (
    A_PHYSICAL_REEL_ORDER,
    A_PHYSICAL_REEL_ORDER,
    B_PHYSICAL_REEL_ORDER,
)

# Every physical stop has at least one virtual stop. Each tuple totals 72.
A_VIRTUAL_STOP_COUNTS: tuple[int, ...] = (
    4, 1, 4, 3, 4, 3, 4, 2, 4, 3, 4,
    2, 4, 3, 4, 2, 4, 2, 4, 3, 5, 3,
)

# CASH has one virtual stop, so the Top Dollar feature occurs once per 72 spins
# on average. The other 71 outcomes resolve to normal Reel-3 symbols.
"""
B_VIRTUAL_STOP_COUNTS: tuple[int, ...] = (
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 51
)
"""
B_VIRTUAL_STOP_COUNTS: tuple[int, ...] = (
    4, 2, 4, 3, 4, 2, 4, 1, 4, 3, 4,
    3, 4, 3, 4, 4, 4, 4, 3, 2, 5, 1,
)

REEL_VIRTUAL_STOP_COUNTS: tuple[tuple[int, ...], ...] = (
    A_VIRTUAL_STOP_COUNTS,
    A_VIRTUAL_STOP_COUNTS,
    B_VIRTUAL_STOP_COUNTS,
)


def _ranges_from_counts(counts: Sequence[int]) -> tuple[tuple[int, int], ...]:
    """Convert positive per-physical-stop weights into inclusive 1..72 ranges."""
    ranges: list[tuple[int, int]] = []
    next_stop = 1
    for count in counts:
        count = int(count)
        if count <= 0:
            raise ValueError("Every physical stop must have at least one virtual stop")
        end_stop = next_stop + count - 1
        ranges.append((next_stop, end_stop))
        next_stop = end_stop + 1
    if next_stop != TOTAL_VIRTUAL_STOPS + 1:
        raise ValueError(f"Virtual-stop weights must total {TOTAL_VIRTUAL_STOPS}")
    return tuple(ranges)


REEL_VIRTUAL_STOP_RANGES: tuple[tuple[tuple[int, int], ...], ...] = tuple(
    _ranges_from_counts(counts) for counts in REEL_VIRTUAL_STOP_COUNTS
)

REEL_VIRTUAL_STOP_TO_PHYSICAL: tuple[tuple[int, ...], ...] = tuple(
    tuple(
        physical_index
        for physical_index, count in enumerate(counts)
        for _ in range(count)
    )
    for counts in REEL_VIRTUAL_STOP_COUNTS
)

PHYSICAL_REEL_ORDER = A_PHYSICAL_REEL_ORDER
VIRTUAL_STOP_COUNTS = A_VIRTUAL_STOP_COUNTS
VIRTUAL_STOP_RANGES = REEL_VIRTUAL_STOP_RANGES[0]
VIRTUAL_STOP_TO_PHYSICAL = REEL_VIRTUAL_STOP_TO_PHYSICAL[0]

# Initial Top Dollar has no post-stop nudge feature.
A_POST_STOP_NUDGE_TARGETS: dict[int, int] = {}
B_POST_STOP_NUDGE_TARGETS: dict[int, int] = {}
REEL_POST_STOP_NUDGE_TARGETS: tuple[dict[int, int], ...] = ({}, {}, {})
POST_STOP_NUDGE_TARGETS: dict[int, int] = {}

# No diamond-backed BAR detents are used by this version.
A_DIAMOND_BACKED_BAR_STOPS: dict[int, str] = {}
B_DIAMOND_BACKED_BAR_STOPS: dict[int, str] = {}
REEL_DIAMOND_BACKED_BAR_STOPS: tuple[dict[int, str], ...] = ({}, {}, {})
DIAMOND_BACKED_BAR_STOPS: dict[int, str] = {}

# Photo-matched BAR diamond artwork.  These named values control only the UI;
# they do not affect reel probabilities, nudge behavior, payouts, RTP, or hit rate.
BAR_DIAMOND_ARTWORK: dict[str, float | str] = {
    # Overall dimensions inside the 146 x 215 reel window.
    "width": 72.0,
    "height": 82.0,

    # Outer silhouette, expressed as proportions of width/height.
    "top_half_x": 0.26,
    "shoulder_half_x": 0.48,
    "top_y": -0.43,
    "shoulder_y": -0.12,
    "tip_y": 0.49,

    # Internal facet grid.
    "inner_top_half_x": 0.15,
    "belt_half_x": 0.22,
    "belt_y": -0.10,
    "lower_half_x": 0.29,
    "lower_y": 0.13,

    # Printed-reel colors.
    "body": "#F8F7EF",
    "white": "#FFFDF7",
    "cool_white": "#E4E3E9",
    "gold": "#E4B52E",
    "pale_gold": "#F0CF55",
    "outline": "#343638",
    "facet": "#77797B",
    "shadow": "#232527",
}

# Initial center symbols: A-stop 4, A-stop 12, B-stop 14.
INITIAL_PHYSICAL_STOPS: tuple[int, int, int] = (4, 12, 14)


def _validate_physical_strip(strip: Sequence[str]) -> None:
    """Validate one 22-stop strip without merging duplicate-looking stops."""
    normalized = tuple(map(str, strip))
    if len(normalized) != 22:
        raise ValueError("Physical strip must contain exactly 22 stops")
    invalid = set(normalized) - (VISIBLE_SYMBOLS | {HIDDEN_SPACE})
    if invalid:
        raise ValueError(f"Unknown reel symbol(s): {sorted(invalid)}")

def resolve_post_stop_physical_index(
    physical_stop_index: int,
    reel_index: int = 0,
) -> int:
    """Return the zero-based final stop after the selected reel's nudge."""
    reel_index = int(reel_index)
    if not 0 <= reel_index < 3:
        raise ValueError("reel_index must be 0, 1, or 2")
    stop_number = int(physical_stop_index) + 1
    target_number = REEL_POST_STOP_NUDGE_TARGETS[reel_index].get(
        stop_number, stop_number
    )
    return target_number - 1


def physical_stop_has_diamond_bar(
    physical_stop_index: int,
    reel_index: int = 0,
) -> bool:
    """Whether this reel's one-based physical stop has diamond-backed BAR art."""
    reel_index = int(reel_index)
    if not 0 <= reel_index < 3:
        return False
    return (
        int(physical_stop_index) + 1
        in REEL_DIAMOND_BACKED_BAR_STOPS[reel_index]
    )


@dataclass(frozen=True)
class ReelStopSelection:
    """One reel's independently generated 72-stop selection for the current spin."""

    secret_number: int
    winning_virtual_stop: int
    physical_stop_index: int
    symbol: str
    temporary_numbers_by_virtual_stop: tuple[int, ...]


def select_reel_stop(rng, reel_index: int = 0) -> ReelStopSelection:
    """Shuffle 1..72, draw one secret, and resolve it on the selected reel."""
    reel_index = int(reel_index)
    if not 0 <= reel_index < 3:
        raise ValueError("reel_index must be 0, 1, or 2")

    temporary_numbers = list(range(1, TOTAL_VIRTUAL_STOPS + 1))
    rng.shuffle(temporary_numbers)
    secret_number = int(rng.choice(temporary_numbers))
    winning_virtual_stop = temporary_numbers.index(secret_number) + 1
    physical_stop_index = REEL_VIRTUAL_STOP_TO_PHYSICAL[reel_index][
        winning_virtual_stop - 1
    ]
    return ReelStopSelection(
        secret_number=secret_number,
        winning_virtual_stop=winning_virtual_stop,
        physical_stop_index=physical_stop_index,
        symbol=FIXED_PHYSICAL_REELS[reel_index][physical_stop_index],
        temporary_numbers_by_virtual_stop=tuple(temporary_numbers),
    )

# ---------------------------------------------------------------------------
# Top Dollar offer model
# ---------------------------------------------------------------------------

# Estimated classic first-generation Top Dollar topper:
#   two $5 lamps, two $10 lamps, two $20 lamps, two $50 lamps,
#   one $100 lamp, plus an independent $1,000 TOP DOLLAR award.
#
# The exact IGT PAR sheet is not public.  This implementation uses the
# maximum-entropy reconstruction described for this project: all 511 non-empty
# combinations of the nine stackable lamps are possible; their weights decay
# exponentially with the displayed total.  The independent $1,000 award has a
# 0.05% probability per generated offer and never stacks with another lamp.
# The resulting mean of one generated offer is exactly $48.00 at 1x.
# Because the existing four independent TAKE/LEAVE offers are retained,
# optimal play has a higher feature EV ($78.2967 at 1x); no base-game or
# trigger-frequency settings are altered to compensate for that increase.
TOP_DOLLAR_LAMP_VALUES: dict[str, int] = {
    "JACKPOT": 1000,
    "L50_TOP": 50,
    "C20_TOP": 20,
    "R10_TOP": 10,
    "L50_MID": 50,
    "C10_MID": 10,
    "R5_MID": 5,
    "L20_LOW": 20,
    "C5_LOW": 5,
    "R100_LOW": 100,
}

# id, amount, center-x, center-y, width, height, skew.  Coordinates retain the
# existing 746 x 536 staggered topper presentation; only the classic amounts
# and identifiers are changed.
TOP_DOLLAR_LAMP_LAYOUT: tuple[tuple[str, int, float, float, float, float, float], ...] = (
    ("JACKPOT", 1000, 365.0, 70.0, 184.0, 66.0, 0.0),
    ("L50_TOP", 50, 185.0, 167.0, 128.0, 58.0, -9.0),
    ("C20_TOP", 20, 365.0, 151.0, 128.0, 58.0, 2.0),
    ("R10_TOP", 10, 545.0, 167.0, 128.0, 58.0, 9.0),
    ("L50_MID", 50, 151.0, 250.0, 128.0, 58.0, -8.0),
    ("C10_MID", 10, 365.0, 239.0, 128.0, 58.0, 0.0),
    ("R5_MID", 5, 579.0, 250.0, 128.0, 58.0, 8.0),
    ("L20_LOW", 20, 115.0, 337.0, 128.0, 58.0, -7.0),
    ("C5_LOW", 5, 365.0, 329.0, 128.0, 58.0, 0.0),
    ("R100_LOW", 100, 615.0, 337.0, 128.0, 58.0, 7.0),
)

TOP_DOLLAR_STACKABLE_LAMP_IDS: tuple[str, ...] = (
    "L50_TOP",
    "C20_TOP",
    "R10_TOP",
    "L50_MID",
    "C10_MID",
    "R5_MID",
    "L20_LOW",
    "C5_LOW",
    "R100_LOW",
)

TOP_DOLLAR_JACKPOT_PROBABILITY = 0.0005
TOP_DOLLAR_TARGET_OFFER_MEAN = 48.0
TOP_DOLLAR_MAX_ENTROPY_LAMBDA = 0.03309770543455315


def _build_top_dollar_offer_distribution(
) -> tuple[tuple[tuple[str, ...], ...], tuple[float, ...]]:
    """Build all non-empty classic lamp combinations plus independent $1,000."""
    patterns: list[tuple[str, ...]] = []
    raw_weights: list[float] = []

    lamp_count = len(TOP_DOLLAR_STACKABLE_LAMP_IDS)
    for mask in range(1, 1 << lamp_count):
        pattern = tuple(
            lamp_id
            for index, lamp_id in enumerate(TOP_DOLLAR_STACKABLE_LAMP_IDS)
            if mask & (1 << index)
        )
        amount = sum(TOP_DOLLAR_LAMP_VALUES[lamp_id] for lamp_id in pattern)
        patterns.append(pattern)
        raw_weights.append(math.exp(-TOP_DOLLAR_MAX_ENTROPY_LAMBDA * amount))

    raw_total = sum(raw_weights)
    non_jackpot_probability = 1.0 - TOP_DOLLAR_JACKPOT_PROBABILITY
    normalized_weights = [
        non_jackpot_probability * weight / raw_total
        for weight in raw_weights
    ]

    # The $1,000 plaque is mutually exclusive with all stackable lamps.
    patterns.append(("JACKPOT",))
    normalized_weights.append(TOP_DOLLAR_JACKPOT_PROBABILITY)
    return tuple(patterns), tuple(normalized_weights)


TOP_DOLLAR_OFFER_PATTERNS, TOP_DOLLAR_OFFER_WEIGHTS = (
    _build_top_dollar_offer_distribution()
)


def top_dollar_pattern_value(pattern: Sequence[str]) -> int:
    """Return the displayed dollar total for one illuminated lamp pattern."""
    return sum(TOP_DOLLAR_LAMP_VALUES[str(lamp_id)] for lamp_id in pattern)


def draw_top_dollar_offer_pattern(rng) -> tuple[str, ...]:
    """Draw one maximum-entropy classic topper-lamp combination."""
    return tuple(
        rng.choices(
            TOP_DOLLAR_OFFER_PATTERNS,
            weights=TOP_DOLLAR_OFFER_WEIGHTS,
            k=1,
        )[0]
    )


def draw_top_dollar_offer(rng) -> int:
    """Compatibility helper returning the dollar total of one offer."""
    return top_dollar_pattern_value(draw_top_dollar_offer_pattern(rng))


def split_top_dollar_offer(amount: int, rng) -> tuple[int, ...]:
    """Compatibility helper; select a matching pattern using model weights."""
    matching_patterns: list[tuple[str, ...]] = []
    matching_weights: list[float] = []
    for pattern, weight in zip(
        TOP_DOLLAR_OFFER_PATTERNS, TOP_DOLLAR_OFFER_WEIGHTS
    ):
        if top_dollar_pattern_value(pattern) == int(amount):
            matching_patterns.append(pattern)
            matching_weights.append(weight)
    if not matching_patterns:
        return (int(amount),)
    pattern = tuple(
        rng.choices(matching_patterns, weights=matching_weights, k=1)[0]
    )
    return tuple(TOP_DOLLAR_LAMP_VALUES[lamp_id] for lamp_id in pattern)


def calculate_offer_strategy_values() -> tuple[float, float, float, float]:
    """Return optimal continuation values for Offers 1..4, in dollars at 1x."""
    offer_values = tuple(
        top_dollar_pattern_value(pattern)
        for pattern in TOP_DOLLAR_OFFER_PATTERNS
    )
    total_weight = float(sum(TOP_DOLLAR_OFFER_WEIGHTS))
    continuation = sum(
        value * weight
        for value, weight in zip(offer_values, TOP_DOLLAR_OFFER_WEIGHTS)
    ) / total_weight
    values = [continuation]
    for _ in range(3):
        continuation = sum(
            max(float(value), continuation) * weight
            for value, weight in zip(offer_values, TOP_DOLLAR_OFFER_WEIGHTS)
        ) / total_weight
        values.append(continuation)
    return tuple(reversed(values))  # Offers 1, 2, 3, 4


# ---------------------------------------------------------------------------
# Paytable and result evaluation
# ---------------------------------------------------------------------------

BASE_PAY_CREDITS: dict[str, int] = {
    "ONE_CHERRY": 2,
    "TWO_CHERRIES": 5,
    "THREE_CHERRIES": 10,
    "ANY_BAR": 5,
    "THREE_BAR": 10,
    "THREE_DOUBLE_BAR": 25,
    "THREE_TRIPLE_BAR": 40,
    "THREE_SEVEN": 80,
    "THREE_DOUBLE_DIAMOND": 1000,
}


@dataclass(frozen=True)
class PayResult:
    """One evaluated center-payline result."""

    award_credits: int
    description: str
    base_credits: int = 0
    diamond_count: int = 0
    diamond_multiplier: int = 1
    winning_reels: tuple[int, ...] = ()
    paytable_key: str = ""

    @property
    def is_win(self) -> bool:
        return self.award_credits > 0


def evaluate_payline(symbols: Sequence[str]) -> PayResult:
    """Evaluate exactly three center symbols.

    A Cherry result requires at least one real Cherry.  Double Diamond does not
    independently create a Cherry win; each Double Diamond on a real-Cherry line
    doubles the already-selected one/two/three-Cherry base award.  For Seven/BAR
    wins, Double Diamond is a wild and also doubles the regular award.
    """
    if len(symbols) != 3:
        raise ValueError("Double Diamond requires exactly three center symbols")

    line = tuple(str(symbol) for symbol in symbols)
    invalid = set(line) - (VISIBLE_SYMBOLS | {HIDDEN_SPACE})
    if invalid:
        raise ValueError(f"Unknown payline symbol(s): {sorted(invalid)}")

    diamond_count = line.count(DOUBLE_DIAMOND)

    if diamond_count == 3:
        return PayResult(
            award_credits=BASE_PAY_CREDITS["THREE_DOUBLE_DIAMOND"],
            description="三个 Double Diamond",
            base_credits=BASE_PAY_CREDITS["THREE_DOUBLE_DIAMOND"],
            diamond_count=3,
            diamond_multiplier=1,
            winning_reels=(0, 1, 2),
            paytable_key="THREE_DOUBLE_DIAMOND",
        )

    regular_multiplier = 2**diamond_count
    candidates: list[PayResult] = []

    real_cherry_count = line.count(CHERRY)
    if real_cherry_count > 0:
        key = {
            1: "ONE_CHERRY",
            2: "TWO_CHERRIES",
            3: "THREE_CHERRIES",
        }[real_cherry_count]
        base = BASE_PAY_CREDITS[key]
        winning = tuple(
            index
            for index, symbol in enumerate(line)
            if symbol in {CHERRY, DOUBLE_DIAMOND}
        )
        candidates.append(
            PayResult(
                award_credits=base * regular_multiplier,
                description={
                    1: "任意一个樱桃",
                    2: "任意两个樱桃",
                    3: "三个樱桃",
                }[real_cherry_count],
                base_credits=base,
                diamond_count=diamond_count,
                diamond_multiplier=regular_multiplier,
                winning_reels=winning,
                paytable_key=key,
            )
        )

    if SEVEN in line and all(
        symbol in {SEVEN, DOUBLE_DIAMOND} for symbol in line
    ):
        base = BASE_PAY_CREDITS["THREE_SEVEN"]
        candidates.append(
            PayResult(
                award_credits=base * regular_multiplier,
                description="三个 7",
                base_credits=base,
                diamond_count=diamond_count,
                diamond_multiplier=regular_multiplier,
                winning_reels=(0, 1, 2),
                paytable_key="THREE_SEVEN",
            )
        )

    real_bars = tuple(symbol for symbol in line if symbol in BAR_SYMBOLS)
    if real_bars and all(
        symbol in BAR_SYMBOLS or symbol == DOUBLE_DIAMOND for symbol in line
    ):
        distinct_bars = set(real_bars)
        if len(distinct_bars) == 1:
            bar_symbol = real_bars[0]
            key = {
                BAR: "THREE_BAR",
                DOUBLE_BAR: "THREE_DOUBLE_BAR",
                TRIPLE_BAR: "THREE_TRIPLE_BAR",
            }[bar_symbol]
            label = {
                BAR: "三个 BAR",
                DOUBLE_BAR: "三个 Double BAR",
                TRIPLE_BAR: "三个 Triple BAR",
            }[bar_symbol]
        else:
            key = "ANY_BAR"
            label = "任意三个 BAR"
        base = BASE_PAY_CREDITS[key]
        candidates.append(
            PayResult(
                award_credits=base * regular_multiplier,
                description=label,
                base_credits=base,
                diamond_count=diamond_count,
                diamond_multiplier=regular_multiplier,
                winning_reels=(0, 1, 2),
                paytable_key=key,
            )
        )

    if not candidates:
        return PayResult(award_credits=0, description="未中奖", paytable_key="")

    return max(candidates, key=lambda result: result.award_credits)


def evaluate_cash_trigger_base(symbols: Sequence[str]) -> PayResult:
    """Evaluate only R1/R2 base-game value when R3 is the CASH trigger.

    CASH does not participate in the base payline.  Replacing it with a physical
    blank gives the intended two-reel Cherry behavior while preventing CASH from
    completing a BAR, Seven, or Double Diamond line.  In particular:
    CHERRY + DOUBLE_DIAMOND + CASH pays one Cherry with the x2 diamond multiplier.
    """
    if len(symbols) != 3:
        raise ValueError("Cash-trigger evaluation requires exactly three symbols")
    line = tuple(str(symbol) for symbol in symbols)
    if line[2] != CASH:
        return evaluate_payline(line)
    return evaluate_payline((line[0], line[1], HIDDEN_SPACE))


def _final_symbol_counts_for_reel(reel_index: int) -> dict[str, int]:
    """Count displayed symbols across one reel's 72 virtual outcomes."""
    symbols = (
        HIDDEN_SPACE, CHERRY, BAR, DOUBLE_BAR, TRIPLE_BAR,
        SEVEN, DOUBLE_DIAMOND, CASH,
    )
    counts = {symbol: 0 for symbol in symbols}
    strip = FIXED_PHYSICAL_REELS[reel_index]
    for physical_index in REEL_VIRTUAL_STOP_TO_PHYSICAL[reel_index]:
        counts[strip[physical_index]] += 1
    return counts


def calculate_theoretical_statistics() -> dict[str, object]:
    """Enumerate base outcomes and combine them with optimal bonus strategy."""
    reel_counts = tuple(_final_symbol_counts_for_reel(index) for index in range(3))
    total_combinations = TOTAL_VIRTUAL_STOPS ** 3
    total_base_award_credits = 0
    base_winning_combinations = 0
    bonus_combinations = 0
    any_event_combinations = 0

    for symbol_1, count_1 in reel_counts[0].items():
        for symbol_2, count_2 in reel_counts[1].items():
            for symbol_3, count_3 in reel_counts[2].items():
                combinations = count_1 * count_2 * count_3
                result = evaluate_payline((symbol_1, symbol_2, symbol_3))
                is_bonus = symbol_3 == CASH
                total_base_award_credits += combinations * result.award_credits
                if result.is_win:
                    base_winning_combinations += combinations
                if is_bonus:
                    bonus_combinations += combinations
                if result.is_win or is_bonus:
                    any_event_combinations += combinations

    base_ev_per_line_credit = total_base_award_credits / total_combinations
    bonus_trigger_rate = bonus_combinations / total_combinations
    offer_strategy_values = calculate_offer_strategy_values()
    optimal_bonus_ev = offer_strategy_values[0]

    # One wager buys both the base game and Top Dollar.  Base awards scale with
    # the $5 line wager; topper amounts are actual dollars at 1x and scale only
    # with the selected multiplier.
    optimal_bonus_rtp = (
        bonus_trigger_rate * optimal_bonus_ev / BASE_WAGER_DOLLARS
    )
    total_optimal_rtp = base_ev_per_line_credit + optimal_bonus_rtp

    return {
        "total_combinations": total_combinations,
        "total_base_award_credits": total_base_award_credits,
        "base_winning_combinations": base_winning_combinations,
        "bonus_combinations": bonus_combinations,
        "base_ev_per_line_credit": base_ev_per_line_credit,
        "base_game_rtp_on_total_wager": base_ev_per_line_credit,
        "base_hit_rate": base_winning_combinations / total_combinations,
        "base_hit_rate_percent": 100.0 * base_winning_combinations / total_combinations,
        "bonus_trigger_rate": bonus_trigger_rate,
        "bonus_trigger_percent": 100.0 * bonus_trigger_rate,
        "any_event_rate": any_event_combinations / total_combinations,
        "any_event_percent": 100.0 * any_event_combinations / total_combinations,
        "offer_strategy_values": offer_strategy_values,
        "optimal_bonus_ev_dollars_at_1x": optimal_bonus_ev,
        "optimal_bonus_ev_credits_equivalent": optimal_bonus_ev / BASE_WAGER_DOLLARS,
        "optimal_bonus_rtp_on_total_wager": optimal_bonus_rtp,
        "total_optimal_rtp": total_optimal_rtp,
        "total_optimal_rtp_percent": 100.0 * total_optimal_rtp,
        "final_symbol_counts": reel_counts,
    }


def calculate_virtual_stop_audit() -> dict[str, object]:
    """Return every A-A-B physical/virtual mapping and theoretical statistics."""
    reels: list[dict[str, object]] = []
    for reel_index, (strip, ranges, counts) in enumerate(
        zip(FIXED_PHYSICAL_REELS, REEL_VIRTUAL_STOP_RANGES, REEL_VIRTUAL_STOP_COUNTS)
    ):
        rows: list[dict[str, object]] = []
        for physical_number, (symbol, stop_range, count) in enumerate(
            zip(strip, ranges, counts), start=1
        ):
            start_stop, end_stop = stop_range
            rows.append(
                {
                    "physical_stop": physical_number,
                    "symbol": symbol,
                    "virtual_stop_start": start_stop,
                    "virtual_stop_end": end_stop,
                    "weight_count": count,
                    "weight_fraction": f"{count}/{TOTAL_VIRTUAL_STOPS}",
                }
            )
        reels.append(
            {
                "reel": reel_index + 1,
                "strip_type": "B" if reel_index == 2 else "A",
                "physical_stops": rows,
                "final_symbol_counts": _final_symbol_counts_for_reel(reel_index),
            }
        )

    return {
        "version": VERSION,
        "model": "three independent 72-stop virtual reels -> A-A-B physical strips -> no nudge",
        "physical_stop_count_per_reel": 22,
        "virtual_stop_count_per_reel": TOTAL_VIRTUAL_STOPS,
        "top_dollar_trigger": "Reel 3 CASH on the center payline",
        "top_dollar_offer_count": 4,
        "wager_model": "one $5 wager per multiplier; no separate feature charge",
        "topper_style": "fixed illuminated Cash Dollar plaques",
        "reels": reels,
        "theoretical_statistics": calculate_theoretical_statistics(),
    }


# ---------------------------------------------------------------------------
# Account persistence compatibility
# ---------------------------------------------------------------------------


def get_data_file_path() -> str:
    """Preserve the Cash Machine V20 A_Tools/Account/saving_data.json location convention."""
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "../A_Tools/Account/saving_data.json"
    )


def load_user_data() -> list:
    try:
        with open(get_data_file_path(), "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return []


def save_user_data(users: list) -> None:
    try:
        path = get_data_file_path()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(users, file, ensure_ascii=False, indent=4)
    except OSError:
        # Keep game play available even when the host's save path is read-only.
        pass


def update_balance_in_json(username: str, new_balance: float) -> None:
    users = load_user_data()
    for user in users:
        if user.get("user_name") == username:
            user["cash"] = f"{float(new_balance):.2f}"
            save_user_data(users)
            return
    users.append({"user_name": username, "cash": f"{float(new_balance):.2f}"})
    save_user_data(users)


# ---------------------------------------------------------------------------
# UI primitives
# ---------------------------------------------------------------------------


class Theme:
    APP_BG = "#B9B2AA"
    PANEL = "#EFEAE3"
    PANEL_ALT = "#E2DBD1"
    PANEL_HOVER = "#D4CBC0"
    CANVAS_BG = "#271C3A"
    BORDER = "#8D8378"
    BORDER_SOFT = "#B8AEA3"

    TEXT = "#252A2E"
    TEXT_MUTED = "#5A6167"
    TEXT_DIM = "#7C8287"

    ACCENT = "#5C3E82"
    ACCENT_HOVER = "#493168"
    ACCENT_SOFT = "#D9CBEA"
    GREEN = "#41744B"
    GREEN_HOVER = "#315A39"
    RED = "#A44747"
    GOLD = "#CDAF4C"
    GOLD_SOFT = "#F3E5A9"

    REEL_WELL = "#151019"
    REEL_FACE = "#FBF8F1"
    REEL_EDGE = "#8E7A55"
    REEL_TEXT = "#252A2E"
    REEL_FADE = "#9A9A9A"
    PAYLINE = "#D8B640"
    WIN = "#3D9B51"

    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )


class ModernButton(tk.Button):
    def __init__(
        self,
        master,
        *,
        text: str,
        command: Optional[Callable[[], None]] = None,
        background: str = Theme.PANEL_HOVER,
        hover_background: str = Theme.BORDER,
        foreground: str = Theme.TEXT,
        font_size: int = 12,
        bold: bool = False,
        **kwargs,
    ) -> None:
        self.normal_background = background
        self.hover_background = hover_background
        self.normal_foreground = foreground
        super().__init__(
            master,
            text=text,
            command=command,
            bg=background,
            fg=foreground,
            activebackground=hover_background,
            activeforeground=foreground,
            disabledforeground=Theme.TEXT_DIM,
            font=(Theme.FONT_CJK, font_size, "bold" if bold else "normal"),
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            **kwargs,
        )
        self.bind("<Enter>", self._enter, add="+")
        self.bind("<Leave>", self._leave, add="+")

    def _enter(self, _event) -> None:
        if str(self.cget("state")) != tk.DISABLED:
            super().configure(bg=self.hover_background)

    def _leave(self, _event) -> None:
        super().configure(bg=self.normal_background)


class MetricTile(tk.Frame):
    def __init__(
        self,
        master,
        label: str,
        variable: tk.StringVar,
        accent: str,
        *,
        width: int,
        height: int,
        value_font_size: int = 15,
    ) -> None:
        super().__init__(
            master,
            width=width,
            height=height,
            bg=Theme.PANEL_ALT,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        self.pack_propagate(False)
        self.grid_propagate(False)

        tk.Label(
            self,
            text=label,
            bg=Theme.PANEL_ALT,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9),
            anchor=tk.W,
        ).place(x=12, y=8, width=width - 24, height=18)

        tk.Label(
            self,
            textvariable=variable,
            bg=Theme.PANEL_ALT,
            fg=accent,
            font=(Theme.FONT, value_font_size, "bold"),
            anchor=tk.W,
        ).place(x=12, y=29, width=width - 24, height=28)


# ---------------------------------------------------------------------------
# Main game
# ---------------------------------------------------------------------------


class TopDollarSlotMachine:
    WINDOW_WIDTH = 1150
    WINDOW_HEIGHT = 750
    SHELL_WIDTH = 1110
    SHELL_HEIGHT = 714
    HEADER_HEIGHT = 70
    BODY_TOP = 84
    BODY_HEIGHT = 630
    GAME_PANEL_WIDTH = 748
    SIDEBAR_WIDTH = 348
    PANEL_GAP = 14
    CANVAS_WIDTH = 746
    CANVAS_HEIGHT = 536

    BASE_BET = BASE_WAGER_DOLLARS
    CREDIT_VALUE = 1.0
    MAX_MULTIPLIER = 20

    REEL_WIDTH = 146
    REEL_HEIGHT = 215
    REEL_GAP = 22
    REEL_TOP_Y = 65
    REEL_SPACING = 60

    MIN_TRAVEL_STOPS = (116, 154, 192)
    MAX_EXTRA_CYCLES = (2, 3, 4)
    SPIN_DURATIONS = ((2.90, 3.25), (3.30, 3.70), (3.75, 4.15))
    POST_STOP_NUDGE_DURATION = 0.400

    # Classic offer-title timing: wait 0.5 s, fade in 1.5 s, hold 4 s,
    # fade out 1.5 s, then begin illuminating the offer lamps.
    OFFER_TITLE_WAIT_MS = 500
    OFFER_TITLE_FADE_MS = 500
    OFFER_TITLE_HOLD_MS = 1500
    OFFER_TITLE_FRAME_MS = 33

    # key, symbols, base multiplier, renderer.  ANY ONE / ANY TWO deliberately
    # use original-style English labels followed by a Cherry graphic.
    PAYTABLE_ROWS: tuple[tuple[str, tuple[str, ...], int, str], ...] = (
        ("THREE_DOUBLE_DIAMOND", (DOUBLE_DIAMOND, DOUBLE_DIAMOND, DOUBLE_DIAMOND), 1000, "icons"),
        ("THREE_SEVEN", (SEVEN, SEVEN, SEVEN), 80, "icons"),
        ("THREE_TRIPLE_BAR", (TRIPLE_BAR, TRIPLE_BAR, TRIPLE_BAR), 40, "icons"),
        ("THREE_DOUBLE_BAR", (DOUBLE_BAR, DOUBLE_BAR, DOUBLE_BAR), 25, "icons"),
        ("THREE_BAR", (BAR, BAR, BAR), 10, "icons"),
        ("ANY_BAR", (BAR, DOUBLE_BAR, TRIPLE_BAR), 5, "icons"),
        ("THREE_CHERRIES", (CHERRY, CHERRY, CHERRY), 10, "icons"),
        ("TWO_CHERRIES", (CHERRY,), 5, "any_two"),
        ("ONE_CHERRY", (CHERRY,), 2, "any_one"),
    )

    def __init__(self, root, initial_balance: float, username: str):
        self.root = root
        self._configure_root()

        self.balance = float(initial_balance)
        self.username = str(username)
        self.multiplier = 1
        self.last_win = 0.0
        self.last_win_expression = ""
        self.last_pay_result = PayResult(0, "未中奖")
        self.round_reel_selections: list[ReelStopSelection] = []
        self.selected_center_symbols: tuple[str, str, str] = (
            HIDDEN_SPACE, HIDDEN_SPACE, HIDDEN_SPACE
        )

        self.rng = random.SystemRandom()
        self.reel_sequences: list[tuple[str, ...]] = [
            tuple(reel) for reel in FIXED_PHYSICAL_REELS
        ]
        for reel in self.reel_sequences:
            _validate_physical_strip(reel)

        initial_indices = tuple(stop_number - 1 for stop_number in INITIAL_PHYSICAL_STOPS)
        self.reel_positions = [
            float(initial_indices[index] % len(self.reel_sequences[index]))
            for index in range(3)
        ]
        self.reel_start_positions = list(self.reel_positions)
        self.reel_target_positions = list(self.reel_positions)
        self.selected_stop_indices = [
            int(position) % len(self.reel_sequences[index])
            for index, position in enumerate(self.reel_positions)
        ]
        self.final_stop_indices = list(self.selected_stop_indices)
        self.nudge_start_positions = list(self.reel_positions)
        self.nudge_target_positions = list(self.reel_positions)
        self.nudge_started = 0.0
        self.nudging = False
        self.reel_spin_started = [0.0, 0.0, 0.0]
        self.reel_spin_durations = [0.0, 0.0, 0.0]
        self.reel_display_speeds = [0.0, 0.0, 0.0]
        self.reel_states = ["idle", "idle", "idle"]

        self.spinning = False
        self.after_id: Optional[str] = None
        self.last_frame_time = 0.0
        self.light_mode = "idle"
        self.winning_reels: set[int] = set()
        self.winning_paytable_key = ""
        self.paytable_flash_on = False
        self.paytable_impact_active = False
        self.paytable_impact_progress = 0.0
        self.paytable_impact_count = 0
        self.win_animation_after_id: Optional[str] = None
        self.diamond_rule_highlight = 0

        # Top Dollar state.
        self.bonus_active = False
        self.bonus_after_id: Optional[str] = None
        self.offer_number = 0
        self.current_offer = 0
        self.offer_history: list[int] = []
        self.offer_components: tuple[int, ...] = ()
        self.offer_lamp_ids: tuple[str, ...] = ()
        self.offer_revealed_count = 0
        self.offer_intro_active = False
        self.offer_intro_number = 0
        self.offer_intro_text = ""
        self.offer_intro_alpha = 0.0
        self.offer_intro_started = 0.0
        sparkle_rng = random.Random(0x544F50444F4C4C41)
        self.offer_sparkles: tuple[tuple[int, int, int], ...] = tuple(
            (
                sparkle_rng.randint(32, self.CANVAS_WIDTH - 32),
                sparkle_rng.randint(24, 432),
                sparkle_rng.randint(0, 2),
            )
            for _ in range(190)
        )
        self.bonus_base_payout = 0.0
        self.bonus_accepted = False

        self.center_symbols = [
            self._symbol_from_position(index) for index in range(3)
        ]

        self.balance_var = tk.StringVar()
        self.bet_var = tk.StringVar()
        self.last_win_var = tk.StringVar()
        self.multiplier_var = tk.StringVar()
        self.result_var = tk.StringVar(value="按下“开始抽奖”")
        self.status_var = tk.StringVar(
            value="中央中奖线 · A-A-B · R3 CASH 激活 Top Dollar"
        )
        self.motion_var = tk.StringVar(value="静止")

        self.multiplier_quick_buttons: list[ModernButton] = []
        self.reel_canvases: list[tk.Canvas] = []
        self.paytable_canvas: Optional[tk.Canvas] = None
        self.diamond_rule_canvas: Optional[tk.Canvas] = None
        self.offer_frame: Optional[tk.Frame] = None
        self.offer_canvas: Optional[tk.Canvas] = None
        self.take_offer_button: Optional[ModernButton] = None
        self.leave_offer_button: Optional[ModernButton] = None

        self.create_widgets()
        self.update_display()

    # ------------------------------------------------------------------
    # Root and layout
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("Top Dollar 最高奖金老虎机")
            self.root.geometry("1150x750+50+10")
            self.root.resizable(False, False)
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        else:
            self.root.configure(width=self.WINDOW_WIDTH, height=self.WINDOW_HEIGHT)
            try:
                self.root.pack_propagate(False)
                self.root.grid_propagate(False)
            except tk.TclError:
                pass
        self.root.configure(bg=Theme.APP_BG)

    @staticmethod
    def _card(master, *, width: int, height: int, padding: int = 12) -> tk.Frame:
        outer = tk.Frame(
            master,
            width=width,
            height=height,
            bg=Theme.PANEL,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        outer.pack_propagate(False)
        outer.grid_propagate(False)
        inner = tk.Frame(outer, bg=Theme.PANEL)
        inner.place(
            x=padding,
            y=padding,
            width=max(1, width - padding * 2),
            height=max(1, height - padding * 2),
        )
        outer.content = inner
        return outer

    @staticmethod
    def _section_title(master, text: str) -> tk.Label:
        return tk.Label(
            master,
            text=text,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 10, "bold"),
            anchor=tk.W,
        )

    def create_widgets(self) -> None:
        shell = tk.Frame(
            self.root,
            width=self.SHELL_WIDTH,
            height=self.SHELL_HEIGHT,
            bg=Theme.APP_BG,
        )
        shell.pack(padx=20, pady=18)
        shell.pack_propagate(False)

        self._build_header(shell)

        body = tk.Frame(
            shell,
            width=self.SHELL_WIDTH,
            height=self.BODY_HEIGHT,
            bg=Theme.APP_BG,
        )
        body.place(
            x=0,
            y=self.BODY_TOP,
            width=self.SHELL_WIDTH,
            height=self.BODY_HEIGHT,
        )

        self._build_game_panel(body)
        self._build_sidebar(body)

    def _build_header(self, shell: tk.Frame) -> None:
        header = tk.Frame(
            shell,
            width=self.SHELL_WIDTH,
            height=self.HEADER_HEIGHT,
            bg=Theme.PANEL,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        header.place(x=0, y=0, width=self.SHELL_WIDTH, height=self.HEADER_HEIGHT)

        icon = tk.Canvas(
            header, width=68, height=52, bg=Theme.PANEL, bd=0, highlightthickness=0
        )
        icon.place(x=10, y=9)
        icon.create_rectangle(8, 7, 60, 45, fill="#265D3A", outline=Theme.GOLD, width=3)
        icon.create_text(34, 26, text="$", fill="#F7DE76", font=(Theme.FONT, 27, "bold"))

        tk.Label(
            header,
            text="Top Dollar 最高奖金老虎机",
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT, 18, "bold"),
            anchor=tk.W,
        ).place(x=88, y=10, width=470, height=27)

        tk.Label(
            header,
            text="三轴固定滚轮",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 10, "bold"),
            anchor=tk.W,
        ).place(x=88, y=39, width=590, height=20)

        balance_box = tk.Frame(
            header,
            width=206,
            height=46,
            bg=Theme.PANEL_ALT,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        balance_box.place(x=self.SHELL_WIDTH - 220, y=12, width=206, height=46)

        tk.Label(
            balance_box,
            text="账户余额",
            bg=Theme.PANEL_ALT,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9),
            anchor=tk.W,
        ).place(x=12, y=4, width=90, height=17)

        tk.Label(
            balance_box,
            textvariable=self.balance_var,
            bg=Theme.PANEL_ALT,
            fg=Theme.ACCENT,
            font=(Theme.FONT, 15, "bold"),
            anchor=tk.E,
        ).place(x=12, y=20, width=182, height=22)

    def _build_game_panel(self, master: tk.Frame) -> None:
        panel = self._card(
            master, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT, padding=0
        )
        panel.place(x=0, y=0, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT)
        self.game_panel = panel

        top = tk.Frame(panel, width=self.CANVAS_WIDTH, height=70, bg=Theme.PANEL)
        top.place(x=0, y=0, width=self.CANVAS_WIDTH, height=70)

        tk.Label(
            top,
            textvariable=self.result_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 14, "bold"),
            anchor=tk.W,
        ).place(x=18, y=9, width=550, height=28)

        tk.Label(
            top,
            textvariable=self.status_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.W,
        ).place(x=18, y=40, width=560, height=18)

        tk.Label(
            top,
            textvariable=self.motion_var,
            bg=Theme.ACCENT_SOFT,
            fg=Theme.ACCENT,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.CENTER,
        ).place(x=584, y=18, width=142, height=30)

        self.game_canvas = tk.Canvas(
            panel,
            width=self.CANVAS_WIDTH,
            height=self.CANVAS_HEIGHT,
            bg=Theme.CANVAS_BG,
            bd=0,
            highlightthickness=0,
        )
        self.game_canvas.place(x=1, y=70, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT)

        reel_total = self.REEL_WIDTH * 3 + self.REEL_GAP * 2
        reel_start_x = int(round((self.CANVAS_WIDTH - reel_total) / 2))
        for reel_index in range(3):
            x = 1 + reel_start_x + reel_index * (self.REEL_WIDTH + self.REEL_GAP)
            y = 70 + self.REEL_TOP_Y
            reel_canvas = tk.Canvas(
                panel,
                width=self.REEL_WIDTH,
                height=self.REEL_HEIGHT,
                bg=Theme.REEL_FACE,
                bd=0,
                highlightthickness=3,
                highlightbackground=Theme.REEL_EDGE,
            )
            reel_canvas.place(x=x, y=y, width=self.REEL_WIDTH, height=self.REEL_HEIGHT)
            self.reel_canvases.append(reel_canvas)

        # This frame covers the complete left game area when Top Dollar starts.
        # The cash plaques are rendered procedurally so this remains one portable
        # Python file with no external image dependency.
        self.offer_frame = tk.Frame(panel, bg="#111B32", bd=0, highlightthickness=0)
        self.offer_canvas = tk.Canvas(
            self.offer_frame,
            width=self.CANVAS_WIDTH,
            height=self.CANVAS_HEIGHT,
            bg="#111B32",
            bd=0,
            highlightthickness=0,
        )
        self.offer_canvas.place(
            x=0, y=0, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT
        )

        self.leave_offer_button = ModernButton(
            self.offer_frame,
            text="接受报价",
            command=self.leave_offer,
            background="#741E25",
            hover_background="#5E171D",
            foreground="#FFF7DE",
            font_size=13,
            bold=True,
        )
        self.leave_offer_button.place(x=66, y=466, width=142, height=52)

        self.take_offer_button = ModernButton(
            self.offer_frame,
            text="再来一次",
            command=self.take_offer,
            background="#A42B2F",
            hover_background="#7E2024",
            foreground="#FFF7DE",
            font_size=13,
            bold=True,
        )
        self.take_offer_button.place(x=538, y=466, width=142, height=52)
        self.offer_frame.place_forget()

        self.draw_scene()

    def _build_sidebar(self, master: tk.Frame) -> None:
        sidebar = tk.Frame(
            master,
            width=self.SIDEBAR_WIDTH,
            height=self.BODY_HEIGHT,
            bg=Theme.APP_BG,
        )
        sidebar.place(
            x=self.GAME_PANEL_WIDTH + self.PANEL_GAP,
            y=0,
            width=self.SIDEBAR_WIDTH,
            height=self.BODY_HEIGHT,
        )

        MetricTile(
            sidebar,
            "本局下注",
            self.bet_var,
            Theme.ACCENT,
            width=169,
            height=68,
        ).place(x=0, y=0, width=169, height=68)
        MetricTile(
            sidebar,
            "上局返还",
            self.last_win_var,
            Theme.GREEN,
            width=169,
            height=68,
        ).place(x=179, y=0, width=169, height=68)

        info = self._card(sidebar, width=348, height=372, padding=9)
        info.place(x=0, y=74, width=348, height=372)
        self._section_title(info.content, "中央线赔付表").place(
            x=0, y=0, width=145, height=18
        )

        tk.Label(
            info.content,
            text="中奖图案",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8, "bold"),
            anchor=tk.CENTER,
        ).place(x=0, y=23, width=205, height=21)
        tk.Label(
            info.content,
            text="当前获胜奖金",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8, "bold"),
            anchor=tk.CENTER,
        ).place(x=205, y=23, width=117, height=21)

        self.paytable_canvas = tk.Canvas(
            info.content,
            width=322,
            height=257,
            bg=Theme.PANEL_ALT,
            bd=0,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        self.paytable_canvas.place(x=0, y=45, width=322, height=257)

        self.diamond_rule_canvas = tk.Canvas(
            info.content,
            width=322,
            height=47,
            bg=Theme.ACCENT_SOFT,
            bd=0,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        self.diamond_rule_canvas.place(x=0, y=307, width=322, height=47)

        self._draw_paytable()
        self._draw_diamond_rule_panel()

        multiplier_card = self._card(sidebar, width=348, height=100, padding=9)
        multiplier_card.place(x=0, y=452, width=348, height=100)
        self._section_title(multiplier_card.content, "选择下注倍数").place(
            x=0, y=0, width=130, height=18
        )

        self.minus_button = ModernButton(
            multiplier_card.content,
            text="−",
            command=lambda: self.change_multiplier(-1),
            background=Theme.PANEL_ALT,
            hover_background=Theme.PANEL_HOVER,
            foreground=Theme.TEXT,
            font_size=15,
            bold=True,
        )
        self.minus_button.place(x=0, y=22, width=58, height=30)

        tk.Label(
            multiplier_card.content,
            textvariable=self.multiplier_var,
            bg=Theme.ACCENT_SOFT,
            fg=Theme.ACCENT,
            font=(Theme.FONT, 13, "bold"),
            anchor=tk.CENTER,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        ).place(x=68, y=22, width=186, height=30)

        self.plus_button = ModernButton(
            multiplier_card.content,
            text="+",
            command=lambda: self.change_multiplier(1),
            background=Theme.PANEL_ALT,
            hover_background=Theme.PANEL_HOVER,
            foreground=Theme.TEXT,
            font_size=15,
            bold=True,
        )
        self.plus_button.place(x=264, y=22, width=58, height=30)

        self.multiplier_quick_buttons = []
        for index, mult in enumerate((1, 5, 10, 20)):
            button = ModernButton(
                multiplier_card.content,
                text=f"{mult}×",
                command=lambda value=mult: self.set_multiplier(value),
                background=Theme.PANEL_ALT,
                hover_background=Theme.PANEL_HOVER,
                foreground=Theme.TEXT,
                font_size=9,
                bold=True,
            )
            button.place(x=index * 81, y=59, width=76, height=23)
            self.multiplier_quick_buttons.append(button)

        actions = self._card(sidebar, width=348, height=72, padding=9)
        actions.place(x=0, y=558, width=348, height=72)
        self.spin_button = ModernButton(
            actions.content,
            text="开始抽奖",
            command=self.start_spin,
            background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF",
            font_size=16,
            bold=True,
        )
        self.spin_button.place(x=0, y=0, width=322, height=45)

    def _paytable_row_geometry(self, key: str) -> tuple[float, float, float]:
        height = 257.0
        row_h = height / len(self.PAYTABLE_ROWS)
        for row_index, (row_key, _symbols, _multiplier, _renderer) in enumerate(
            self.PAYTABLE_ROWS
        ):
            if row_key == key:
                y1 = row_index * row_h
                return y1, y1 + row_h, y1 + row_h / 2.0
        return 0.0, row_h, row_h / 2.0

    def _draw_diamond_rule_panel(self) -> None:
        """Draw the split one-Double/X2 and two-Double/X4 rule panel."""
        canvas = self.diamond_rule_canvas
        if canvas is None:
            return

        canvas.delete("all")

        width = 322.0
        height = 47.0

        # 左侧占 3/8，右侧占 5/8
        split_x = width * 3.1 / 8.0

        left_active = self.diamond_rule_highlight == 1
        right_active = self.diamond_rule_highlight == 2

        left_fill = Theme.GOLD_SOFT if left_active else Theme.ACCENT_SOFT
        right_fill = Theme.GOLD_SOFT if right_active else Theme.ACCENT_SOFT

        canvas.create_rectangle(
            0,
            0,
            split_x,
            height,
            fill=left_fill,
            outline=Theme.GOLD if left_active else Theme.BORDER_SOFT,
            width=2 if left_active else 1,
        )

        canvas.create_rectangle(
            split_x,
            0,
            width,
            height,
            fill=right_fill,
            outline=Theme.GOLD if right_active else Theme.BORDER_SOFT,
            width=2 if right_active else 1,
        )

        canvas.create_line(
            split_x,
            1,
            split_x,
            height - 1,
            fill=(
                Theme.GOLD
                if left_active or right_active
                else Theme.BORDER_SOFT
            ),
            width=2 if left_active or right_active else 1,
        )

        # -------------------------------------------------------
        # 左侧：一个 Double Diamond + 赔付X2
        # -------------------------------------------------------

        self._draw_double_diamond_icon(
            canvas,
            40.0,
            height / 2.0,
            13,
            compact=True,
            fade=False,
        )

        canvas.create_text(
            76.0,
            height / 2.0,
            text="赔付X2",
            fill=Theme.ACCENT,
            font=(Theme.FONT_CJK, 10, "bold"),
            anchor=tk.W,
        )

        # -------------------------------------------------------
        # 右侧：两个 Double Diamond + 赔付X4
        # -------------------------------------------------------

        self._draw_double_diamond_icon(
            canvas,
            split_x + 37.0,
            height / 2.0,
            13,
            compact=True,
            fade=False,
        )

        self._draw_double_diamond_icon(
            canvas,
            split_x + 95.0,
            height / 2.0,
            13,
            compact=True,
            fade=False,
        )

        canvas.create_text(
            split_x + 131.0,
            height / 2.0,
            text="赔付X4",
            fill=Theme.ACCENT,
            font=(Theme.FONT_CJK, 11, "bold"),
            anchor=tk.W,
        )

    def _draw_paytable(self) -> None:
        """绘制图案赔付表、当前下注奖金和中奖撞击动画。"""
        canvas = self.paytable_canvas
        if canvas is None:
            return

        canvas.delete("all")

        width = 322
        height = 257
        symbol_area_w = 205

        # 不修改 PAYTABLE_ROWS 原始定义，仅在显示时交换：
        # THREE_CHERRIES ↔ ANY_BAR
        display_rows = list(self.PAYTABLE_ROWS)

        try:
            three_cherries_index = next(
                index
                for index, row in enumerate(display_rows)
                if row[0] == "THREE_CHERRIES"
            )
            any_bar_index = next(
                index
                for index, row in enumerate(display_rows)
                if row[0] == "ANY_BAR"
            )

            display_rows[three_cherries_index], display_rows[any_bar_index] = (
                display_rows[any_bar_index],
                display_rows[three_cherries_index],
            )
        except StopIteration:
            # 如果以后删除或重命名了其中一行，则保持原顺序，避免程序崩溃。
            pass

        row_h = height / len(display_rows)

        for row_index, (
            key,
            symbols,
            base_multiplier,
            renderer,
        ) in enumerate(display_rows):
            y1 = row_index * row_h
            y2 = (row_index + 1) * row_h
            cy = (y1 + y2) / 2

            is_winner = (
                key == self.winning_paytable_key
                and self.paytable_flash_on
            )

            row_bg = (
                Theme.GOLD_SOFT
                if is_winner
                else (
                    Theme.PANEL_ALT
                    if row_index % 2 == 0
                    else Theme.PANEL
                )
            )

            outline = Theme.GOLD if is_winner else ""

            canvas.create_rectangle(
                0,
                y1,
                width,
                y2,
                fill=row_bg,
                outline=outline,
                width=3 if is_winner else 0,
            )

            canvas.create_line(
                0,
                y2,
                width,
                y2,
                fill=Theme.BORDER_SOFT,
                width=1,
            )

            canvas.create_line(
                symbol_area_w,
                y1,
                symbol_area_w,
                y2,
                fill=Theme.BORDER_SOFT,
                width=1,
            )

            # --------------------------------------------------------------
            # 左侧中奖组合
            # --------------------------------------------------------------

            if renderer == "any_two":
                canvas.create_text(
                    30,
                    cy,
                    text="ANY TWO",
                    fill=Theme.TEXT,
                    font=(Theme.FONT, 16, "bold"),
                    anchor=tk.W,
                )

                self._draw_symbol(
                    canvas,
                    CHERRY,
                    155,
                    cy,
                    0.31,
                    fade=False,
                    compact=True,
                )

            elif renderer == "any_one":
                canvas.create_text(
                    30,
                    cy,
                    text="ANY ONE",
                    fill=Theme.TEXT,
                    font=(Theme.FONT, 16, "bold"),
                    anchor=tk.W,
                )

                self._draw_symbol(
                    canvas,
                    CHERRY,
                    155,
                    cy,
                    0.31,
                    fade=False,
                    compact=True,
                )

            else:
                symbol_count = len(symbols)

                if symbol_count == 1:
                    symbol_positions = (
                        symbol_area_w / 2,
                    )

                elif symbol_count == 2:
                    symbol_positions = (
                        symbol_area_w / 2 - 28,
                        symbol_area_w / 2 + 28,
                    )

                else:
                    symbol_positions = (
                        symbol_area_w / 2 - 52,
                        symbol_area_w / 2,
                        symbol_area_w / 2 + 52,
                    )

                for x, symbol in zip(symbol_positions, symbols):
                    self._draw_symbol(
                        canvas,
                        symbol,
                        x,
                        cy,
                        0.31,
                        fade=False,
                        compact=True,
                    )

            # --------------------------------------------------------------
            # 右侧当前下注对应的实际奖金
            # --------------------------------------------------------------

            payout = self.line_bet * float(base_multiplier)

            canvas.create_text(
                width - 10,
                cy,
                text=f"${payout:,.0f}",
                fill=Theme.GREEN,
                font=(Theme.FONT, 9, "bold"),
                anchor=tk.E,
            )

        # ------------------------------------------------------------------
        # Double Diamond 撞向中奖赔付格的动画
        #
        # 因为上面改变了显示顺序，这里也必须根据 display_rows 重新计算
        # 目标行，不能继续调用基于原始 PAYTABLE_ROWS 的几何位置。
        # ------------------------------------------------------------------

        if self.paytable_impact_active and self.winning_paytable_key:
            target_y = row_h / 2

            for row_index, (
                key,
                _symbols,
                _base_multiplier,
                _renderer,
            ) in enumerate(display_rows):
                if key == self.winning_paytable_key:
                    target_y = row_index * row_h + row_h / 2
                    break

            progress = max(
                0.0,
                min(1.0, self.paytable_impact_progress),
            )

            impact_x = -18.0 + progress * 188.0

            for index in range(self.paytable_impact_count):
                offset_y = (
                    index
                    - (self.paytable_impact_count - 1) / 2.0
                ) * 9.0

                self._draw_double_diamond_icon(
                    canvas,
                    impact_x - index * 12.0,
                    target_y + offset_y,
                    7.5,
                    compact=True,
                    fade=False,
                )

    # ------------------------------------------------------------------
    # Betting and outcome selection
    # ------------------------------------------------------------------

    @property
    def line_bet(self) -> float:
        """One line-credit unit used to scale all displayed awards."""
        return self.BASE_BET * self.multiplier

    @property
    def current_bet(self) -> float:
        """One $5 wager per multiplier buys both base play and Top Dollar."""
        return self.line_bet

    def set_multiplier(self, value: int) -> None:
        if self.spinning or self.bonus_active:
            return
        self.multiplier = max(1, min(self.MAX_MULTIPLIER, int(value)))
        self.winning_reels.clear()
        self.light_mode = "idle"
        self.update_display()

    def change_multiplier(self, delta: int) -> None:
        self.set_multiplier(self.multiplier + int(delta))

    def _set_controls_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled) and not self.spinning and not self.bonus_active
        self.spin_button.configure(state=tk.NORMAL if enabled else tk.DISABLED)
        if not enabled:
            self.minus_button.configure(state=tk.DISABLED)
            self.plus_button.configure(state=tk.DISABLED)
            for button in self.multiplier_quick_buttons:
                button.configure(state=tk.DISABLED)
            return

        self.minus_button.configure(
            state=tk.NORMAL if self.multiplier > 1 else tk.DISABLED
        )
        self.plus_button.configure(
            state=tk.NORMAL if self.multiplier < self.MAX_MULTIPLIER else tk.DISABLED
        )
        for button in self.multiplier_quick_buttons:
            button.configure(state=tk.NORMAL)

    def _select_round_reel_stops(self) -> list[ReelStopSelection]:
        """Generate three independent temporary-number maps and secret draws."""
        return [select_reel_stop(self.rng, reel_index) for reel_index in range(3)]

    def _future_target_for_stop(
        self,
        reel_index: int,
        physical_stop_index: int,
    ) -> int:
        """Choose a future revolution landing on one exact physical stop index."""
        sequence = self.reel_sequences[reel_index]
        period = len(sequence)
        stop_index = int(physical_stop_index)
        if not 0 <= stop_index < period:
            raise ValueError(
                f"Physical stop index {stop_index} is outside reel {reel_index + 1}"
            )

        current = int(round(self.reel_positions[reel_index]))
        minimum = self.MIN_TRAVEL_STOPS[reel_index]
        first_candidate = current + minimum
        adjustment = (stop_index - (first_candidate % period)) % period
        target = first_candidate + adjustment

        extra_cycles = self.rng.randint(0, self.MAX_EXTRA_CYCLES[reel_index])
        target += extra_cycles * period
        if target % period != stop_index:
            raise RuntimeError("Exact physical-stop target calculation failed")
        return int(target)

    @staticmethod
    def _minimum_jerk(u: float) -> float:
        """Smooth 0-to-1 trajectory with zero endpoint velocity/acceleration."""
        u = max(0.0, min(1.0, float(u)))
        return 10.0 * u**3 - 15.0 * u**4 + 6.0 * u**5

    def start_spin(self) -> None:
        if self.spinning or self.bonus_active or self.win_animation_after_id is not None:
            return

        if self.balance < self.current_bet:
            messagebox.showwarning(
                "余额不足",
                f"本局需要 ${self.current_bet:,.2f}。",
                parent=self.root,
            )
            return

        self.round_reel_selections = self._select_round_reel_stops()
        self.selected_stop_indices = [
            selection.physical_stop_index for selection in self.round_reel_selections
        ]
        self.final_stop_indices = list(self.selected_stop_indices)
        self.nudging = False
        self.selected_center_symbols = tuple(
            selection.symbol for selection in self.round_reel_selections
        )
        targets = [
            self._future_target_for_stop(index, selection.physical_stop_index)
            for index, selection in enumerate(self.round_reel_selections)
        ]

        self.balance -= self.current_bet
        self.last_win = 0.0
        self.last_win_expression = ""
        self.last_pay_result = PayResult(0, "未中奖")
        self.winning_reels.clear()
        self.winning_paytable_key = ""
        self.paytable_flash_on = False
        self.paytable_impact_active = False
        self.diamond_rule_highlight = 0
        self.light_mode = "spin"
        update_balance_in_json(self.username, self.balance)

        now = time.monotonic()
        self.last_frame_time = now
        for index in range(3):
            start = int(round(self.reel_positions[index]))
            target = targets[index]
            self.reel_positions[index] = float(start)
            self.reel_start_positions[index] = float(start)
            self.reel_target_positions[index] = float(target)
            self.reel_spin_started[index] = now
            self.reel_spin_durations[index] = self.rng.uniform(*self.SPIN_DURATIONS[index])
            self.reel_display_speeds[index] = 0.0
            self.reel_states[index] = "accelerating"

        self.spinning = True
        self.result_var.set("滚轮转动中...")
        self.status_var.set("R3 中线出现 CASH 将激活 Top Dollar")
        self.motion_var.set("滚动中")
        self._set_controls_enabled(False)
        self.update_display()
        self._physics_frame()

    # ------------------------------------------------------------------
    # Animation and settlement
    # ------------------------------------------------------------------

    def _physics_frame(self) -> None:
        if not self.spinning:
            return

        now = time.monotonic()
        dt = max(0.001, min(0.050, now - self.last_frame_time))
        self.last_frame_time = now

        all_stopped = True
        for index in range(3):
            state = self.reel_states[index]
            if state not in {"accelerating", "cruising", "decelerating"}:
                self.reel_display_speeds[index] = 0.0
                continue

            all_stopped = False
            duration = max(0.001, self.reel_spin_durations[index])
            raw_u = (now - self.reel_spin_started[index]) / duration
            u = max(0.0, min(1.0, raw_u))
            eased = self._minimum_jerk(u)

            old_position = self.reel_positions[index]
            start = self.reel_start_positions[index]
            target = self.reel_target_positions[index]
            new_position = start + (target - start) * eased
            self.reel_positions[index] = new_position
            self.reel_display_speeds[index] = abs(new_position - old_position) / dt

            if raw_u >= 1.0:
                # The analytic trajectory already equals the exact integer target.
                self.reel_positions[index] = float(int(round(target)))
                self.reel_display_speeds[index] = 0.0
                self.reel_states[index] = "stopped"
            elif u < 0.30:
                self.reel_states[index] = "accelerating"
            elif u < 0.64:
                self.reel_states[index] = "cruising"
            else:
                self.reel_states[index] = "decelerating"

        self.draw_scene()

        if all(
            state == "stopped" for state in self.reel_states
        ):
            self._finish_spin()
            return

        self.after_id = self.root.after(16, self._physics_frame)

    def _symbol_from_position(self, reel_index: int, row_offset: int = 0) -> str:
        sequence = self.reel_sequences[reel_index]
        center_index = int(round(self.reel_positions[reel_index]))
        return str(sequence[(center_index + int(row_offset)) % len(sequence)])

    def _window_for_reel(self, reel_index: int) -> tuple[str, str, str]:
        return tuple(
            self._symbol_from_position(reel_index, row_offset)
            for row_offset in ROW_OFFSETS
        )  # type: ignore[return-value]

    def _finish_spin(self) -> None:
        """Verify the exact 72-stop selections and settle without any nudge."""
        self.after_id = None
        actual_indices = [
            int(round(self.reel_positions[index])) % len(self.reel_sequences[index])
            for index in range(3)
        ]
        if actual_indices != self.selected_stop_indices:
            raise RuntimeError(
                "Reel animation ended on different stops than selected: "
                f"selected={self.selected_stop_indices}, actual={actual_indices}"
            )

        actual_symbols = tuple(self._symbol_from_position(index, 0) for index in range(3))
        if actual_symbols != tuple(self.selected_center_symbols):
            raise RuntimeError(
                "Displayed symbols differ from selected physical stops: "
                f"selected={self.selected_center_symbols}, displayed={actual_symbols}"
            )

        self.final_stop_indices = list(self.selected_stop_indices)
        self.spinning = False
        self._settle_final_display()

    def _start_post_stop_nudge(self) -> None:
        """Compatibility hook: this Top Dollar model has no nudge feature."""
        self.nudging = False
        self.spinning = False
        self.final_stop_indices = list(self.selected_stop_indices)
        self._settle_final_display()

    def _nudge_frame(self) -> None:
        """Compatibility hook retained for hosts; no nudge animation is used."""
        self.nudging = False
        self.spinning = False
        self.after_id = None
        self.final_stop_indices = list(self.selected_stop_indices)
        self._settle_final_display()

    def _settle_final_display(self) -> None:
        """Evaluate the center line, then start Top Dollar when R3 shows CASH."""
        self.center_symbols = [
            self._symbol_from_position(index, 0) for index in range(3)
        ]
        actual_indices = [
            int(round(self.reel_positions[index])) % len(self.reel_sequences[index])
            for index in range(3)
        ]
        if actual_indices != self.final_stop_indices:
            raise RuntimeError(
                "Final result ended on different physical stops: "
                f"expected={self.final_stop_indices}, actual={actual_indices}"
            )

        expected_symbols = tuple(
            self.reel_sequences[index][self.final_stop_indices[index]]
            for index in range(3)
        )
        if tuple(self.center_symbols) != expected_symbols:
            raise RuntimeError(
                "Displayed symbols differ from final physical stops: "
                f"expected={expected_symbols}, displayed={self.center_symbols}"
            )

        cash_triggered = self.center_symbols[2] == CASH
        # When R3 is CASH, it is a bonus trigger rather than a base-game symbol.
        # Evaluate R1 and R2 as one base-game unit by replacing R3 with a blank.
        # This explicitly preserves CHERRY + DOUBLE DIAMOND = one-Cherry ×2
        # before the Top Dollar feature begins.
        result = (
            evaluate_cash_trigger_base(self.center_symbols)
            if cash_triggered
            else evaluate_payline(self.center_symbols)
        )
        self.last_pay_result = result
        self.winning_reels = set(result.winning_reels)

        if cash_triggered:
            base_payout = self.line_bet * float(result.award_credits)
            self.last_win = base_payout
            if result.is_win:
                self.balance += base_payout
                self.light_mode = "win"
                self.winning_paytable_key = result.paytable_key
                self.paytable_flash_on = True
                self.diamond_rule_highlight = (
                    result.diamond_count if result.diamond_count in {1, 2} else 0
                )
            else:
                self.light_mode = "idle"
                self.winning_reels.clear()
                self.winning_paytable_key = ""
                self.paytable_flash_on = False
                self.diamond_rule_highlight = 0

            update_balance_in_json(self.username, self.balance)
            self.result_var.set("CASH！TOP DOLLAR 已激活")
            if base_payout > 0:
                self.status_var.set(f"基础线先支付 ${base_payout:,.2f}，然后进入报价奖励")
            else:
                self.status_var.set("中奖 CASH 对应的灯箱位置会逐个亮起")
            self.motion_var.set("BONUS")
            self.update_display()
            self._start_top_dollar_bonus(base_payout)
            return

        if result.is_win:
            self._settle_win(result)
        else:
            self._settle_loss()

    def _settle_win(self, result: PayResult) -> None:
        payout = self.line_bet * float(result.award_credits)
        base_payout = self.line_bet * float(result.base_credits)
        self.last_win = payout
        self.balance += payout
        self.light_mode = "win"
        self.winning_paytable_key = result.paytable_key
        self.paytable_flash_on = True
        self.diamond_rule_highlight = (
            result.diamond_count if result.diamond_count in {1, 2} else 0
        )

        if result.diamond_count == 1:
            self.last_win_expression = f"${base_payout:,.0f} × 2 = ${payout:,.0f}"
        elif result.diamond_count == 2:
            self.last_win_expression = f"${base_payout:,.0f} × 2 × 2 = ${payout:,.0f}"
        else:
            self.last_win_expression = ""

        self.result_var.set(f"中奖：{result.description}")
        if self.last_win_expression:
            self.status_var.set(self.last_win_expression)
        else:
            self.status_var.set(
                f"线注 ${self.line_bet:,.2f} × {result.award_credits:,} = ${payout:,.2f}"
            )
        self.motion_var.set("中奖")
        update_balance_in_json(self.username, self.balance)
        self.update_display()
        self._set_controls_enabled(True)

    def _start_paytable_impact(self, diamond_count: int) -> None:
        if self.win_animation_after_id is not None:
            try:
                self.root.after_cancel(self.win_animation_after_id)
            except tk.TclError:
                pass
        self.paytable_impact_count = max(1, min(2, int(diamond_count)))
        self.paytable_impact_progress = 0.0
        self.paytable_impact_active = True
        self.paytable_flash_on = False
        self._set_controls_enabled(False)
        self._animate_paytable_impact(0)

    def _animate_paytable_impact(self, frame: int) -> None:
        self.win_animation_after_id = None
        total_frames = 22
        frame = max(0, int(frame))
        self.paytable_impact_progress = min(1.0, frame / total_frames)

        # Gold flash begins as the moving diamond reaches the winning row.
        if frame >= total_frames - 4:
            self.paytable_flash_on = (frame % 2 == 0) or frame >= total_frames
        self._draw_paytable()

        if frame >= total_frames:
            self.paytable_impact_active = False
            self.paytable_flash_on = True
            self._draw_paytable()
            self._set_controls_enabled(True)
            return

        try:
            self.win_animation_after_id = self.root.after(
                18, lambda: self._animate_paytable_impact(frame + 1)
            )
        except tk.TclError:
            self.win_animation_after_id = None
            self.paytable_impact_active = False

    def _settle_loss(self) -> None:
        self.last_win = 0.0
        self.last_win_expression = ""
        self.light_mode = "idle"
        self.winning_reels.clear()
        self.winning_paytable_key = ""
        self.paytable_flash_on = False
        self.paytable_impact_active = False
        self.diamond_rule_highlight = 0
        self.result_var.set("未中奖，祝您下局好运！")
        self.status_var.set("本局结束")
        self.motion_var.set("结束")
        update_balance_in_json(self.username, self.balance)
        self.update_display()
        self._set_controls_enabled(True)

    # ------------------------------------------------------------------
    # Top Dollar bonus
    # ------------------------------------------------------------------

    def _cancel_bonus_timer(self) -> None:
        if self.bonus_after_id is not None:
            try:
                self.root.after_cancel(self.bonus_after_id)
            except tk.TclError:
                pass
            self.bonus_after_id = None

    def _show_offer_panel(self) -> None:
        if self.offer_frame is None:
            return
        self.offer_frame.place(
            x=1, y=70, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT
        )
        self.offer_frame.lift()

    def _hide_offer_panel(self) -> None:
        if self.offer_frame is not None:
            self.offer_frame.place_forget()

    def _start_top_dollar_bonus(self, base_payout: float) -> None:
        self._cancel_bonus_timer()
        self.bonus_active = True
        self.bonus_base_payout = float(base_payout)
        self.bonus_accepted = False
        self.offer_number = 0
        self.current_offer = 0
        self.offer_history = []
        self.offer_components = ()
        self.offer_lamp_ids = ()
        self.offer_revealed_count = 0
        self.offer_intro_active = False
        self.offer_intro_number = 0
        self.offer_intro_text = ""
        self.offer_intro_alpha = 0.0
        self._set_controls_enabled(False)
        self._show_offer_panel()
        self._begin_offer_intro(1)

    @staticmethod
    def _offer_intro_label(offer_number: int) -> str:
        return {
            1: "FIRST OFFER",
            2: "SECOND OFFER",
            3: "THIRD OFFER",
            4: "FINAL OFFER",
        }.get(int(offer_number), "OFFER")

    def _begin_offer_intro(self, offer_number: int) -> None:
        """Run the title sequence before one of the four actual offers."""
        if not self.bonus_active or not 1 <= int(offer_number) <= 4:
            return

        self._cancel_bonus_timer()
        self.offer_intro_active = True
        self.offer_intro_number = int(offer_number)
        self.offer_intro_text = self._offer_intro_label(offer_number)
        self.offer_intro_alpha = 0.0
        self.offer_intro_started = 0.0

        # Clear the rejected/previous offer before presenting the next title.
        self.current_offer = 0
        self.offer_components = ()
        self.offer_lamp_ids = ()
        self.offer_revealed_count = 0
        self.bonus_accepted = False

        if self.take_offer_button is not None:
            self.take_offer_button.configure(state=tk.DISABLED, text="接受报价")
        if self.leave_offer_button is not None:
            self.leave_offer_button.configure(state=tk.DISABLED, text="再来一次")

        self.result_var.set(f"最高奖金 · 当前第 {self.offer_number} / 4 轮")
        self.status_var.set("准备下一次报价...")
        self.motion_var.set("最高奖金")
        self._draw_top_dollar_offer_screen()
        self.bonus_after_id = self.root.after(
            self.OFFER_TITLE_WAIT_MS, self._start_offer_intro_fade_in
        )

    def _start_offer_intro_fade_in(self) -> None:
        self.bonus_after_id = None
        if not self.bonus_active or not self.offer_intro_active:
            return
        self.offer_intro_started = time.monotonic()
        self._animate_offer_intro_fade_in()

    def _animate_offer_intro_fade_in(self) -> None:
        self.bonus_after_id = None
        if not self.bonus_active or not self.offer_intro_active:
            return
        elapsed_ms = (time.monotonic() - self.offer_intro_started) * 1000.0
        progress = max(0.0, min(1.0, elapsed_ms / self.OFFER_TITLE_FADE_MS))
        self.offer_intro_alpha = self._minimum_jerk(progress)
        self._draw_top_dollar_offer_screen()
        if progress >= 1.0:
            self.offer_intro_alpha = 1.0
            self._draw_top_dollar_offer_screen()
            self.bonus_after_id = self.root.after(
                self.OFFER_TITLE_HOLD_MS, self._start_offer_intro_fade_out
            )
            return
        self.bonus_after_id = self.root.after(
            self.OFFER_TITLE_FRAME_MS, self._animate_offer_intro_fade_in
        )

    def _start_offer_intro_fade_out(self) -> None:
        self.bonus_after_id = None
        if not self.bonus_active or not self.offer_intro_active:
            return
        self.offer_intro_started = time.monotonic()
        self._animate_offer_intro_fade_out()

    def _animate_offer_intro_fade_out(self) -> None:
        self.bonus_after_id = None
        if not self.bonus_active or not self.offer_intro_active:
            return
        elapsed_ms = (time.monotonic() - self.offer_intro_started) * 1000.0
        progress = max(0.0, min(1.0, elapsed_ms / self.OFFER_TITLE_FADE_MS))
        self.offer_intro_alpha = 1.0 - self._minimum_jerk(progress)
        self._draw_top_dollar_offer_screen()
        if progress >= 1.0:
            self.offer_intro_alpha = 0.0
            self.offer_intro_active = False
            self._draw_top_dollar_offer_screen()
            self._generate_next_offer()
            return
        self.bonus_after_id = self.root.after(
            self.OFFER_TITLE_FRAME_MS, self._animate_offer_intro_fade_out
        )

    def _generate_next_offer(self) -> None:
        if not self.bonus_active or self.offer_number >= 4:
            return
        self._cancel_bonus_timer()
        self.offer_intro_active = False
        self.offer_intro_alpha = 0.0
        self.offer_intro_text = ""
        self.offer_intro_number = 0
        self.offer_number += 1
        self.offer_lamp_ids = draw_top_dollar_offer_pattern(self.rng)
        self.offer_components = tuple(
            TOP_DOLLAR_LAMP_VALUES[lamp_id]
            for lamp_id in self.offer_lamp_ids
        )
        self.current_offer = sum(self.offer_components)
        self.offer_history.append(self.current_offer)
        self.offer_revealed_count = 0
        self.bonus_accepted = False

        if self.take_offer_button is not None:
            self.take_offer_button.configure(state=tk.DISABLED, text="接受报价")
        if self.leave_offer_button is not None:
            self.leave_offer_button.configure(state=tk.DISABLED, text="再来一次")

        self.result_var.set(f"最高奖金 · 当前第 {self.offer_number} / 4 轮")
        self.status_var.set("正在生成报价...")
        self.motion_var.set("最高奖金")
        self._draw_top_dollar_offer_screen()
        self.bonus_after_id = self.root.after(260, self._reveal_next_offer_component)

    def _reveal_next_offer_component(self) -> None:
        self.bonus_after_id = None
        if not self.bonus_active:
            return
        if self.offer_revealed_count < len(self.offer_components):
            self.offer_revealed_count += 1
            self._draw_top_dollar_offer_screen()

        if self.offer_revealed_count < len(self.offer_components):
            self.bonus_after_id = self.root.after(430, self._reveal_next_offer_component)
            return

        is_top_dollar = self.offer_lamp_ids == ("JACKPOT",)
        payout = float(self.multiplier) * self.current_offer

        if is_top_dollar:
            # The independent $1,000 TOP DOLLAR award is automatically accepted
            # and cannot be combined with, rejected for, or followed by another offer.
            if self.take_offer_button is not None:
                self.take_offer_button.configure(state=tk.DISABLED, text="最高奖金")
            if self.leave_offer_button is not None:
                self.leave_offer_button.configure(state=tk.DISABLED, text="最高奖金")
            self.status_var.set(
                f"TOP DOLLAR：${self.current_offer:,.0f} × {self.multiplier} "
                f"= ${payout:,.2f}，自动领取"
            )
            self.motion_var.set("TOP DOLLAR 最高奖金老虎机")
            self._draw_top_dollar_offer_screen()
            self.bonus_after_id = self.root.after(900, self.take_offer)
            return

        if self.take_offer_button is not None:
            self.take_offer_button.configure(
                state=tk.NORMAL,
                text="接受报价 · 最终" if self.offer_number == 4 else "接受报价",
            )
        if self.leave_offer_button is not None:
            if self.offer_number == 4:
                self.leave_offer_button.configure(state=tk.DISABLED, text="最后报价")
            else:
                self.leave_offer_button.configure(state=tk.NORMAL, text="再来一次")

        if self.offer_number == 4:
            self.status_var.set(
                f"最终报价：${self.current_offer:,.0f} × {self.multiplier} "
                f"= ${payout:,.2f}，必须领取"
            )
        else:
            self.status_var.set(
                f"当前报价：${self.current_offer:,.0f} × {self.multiplier} "
                f"= ${payout:,.2f}"
            )
        self._draw_top_dollar_offer_screen()

    def leave_offer(self) -> None:
        if (
            not self.bonus_active
            or self.offer_intro_active
            or self.offer_number >= 4
            or self.offer_revealed_count < len(self.offer_components)
        ):
            return
        self.result_var.set(f"已拒绝 OFFER {self.offer_number}")
        self.status_var.set("等待下一次报价标题...")
        self.motion_var.set("REJECTED")
        self._begin_offer_intro(self.offer_number + 1)

    def take_offer(self) -> None:
        if (
            not self.bonus_active
            or self.offer_intro_active
            or self.offer_revealed_count < len(self.offer_components)
            or self.current_offer <= 0
        ):
            return

        self._cancel_bonus_timer()
        if self.take_offer_button is not None:
            self.take_offer_button.configure(state=tk.DISABLED)
        if self.leave_offer_button is not None:
            self.leave_offer_button.configure(state=tk.DISABLED)

        bonus_payout = float(self.multiplier) * float(self.current_offer)
        self.balance += bonus_payout
        self.last_win = self.bonus_base_payout + bonus_payout
        self.bonus_accepted = True
        self.light_mode = "win"
        self.result_var.set(
            f"已接受 第 {self.offer_number} 轮报价，${self.current_offer:,.0f}"
        )
        self.status_var.set(
            f"最高奖金 支付 ${bonus_payout:,.2f} · 本局总返还 ${self.last_win:,.2f}"
        )
        self.motion_var.set("TAKEN")
        update_balance_in_json(self.username, self.balance)
        self.update_display()
        self._draw_top_dollar_offer_screen()
        self.bonus_after_id = self.root.after(1100, self._finish_top_dollar_bonus)

    def _finish_top_dollar_bonus(self) -> None:
        self.bonus_after_id = None
        self.bonus_active = False
        self._hide_offer_panel()
        self.result_var.set(f"最高奖金 完成 · 本局返还 ${self.last_win:,.2f}")
        self.status_var.set("按下“开始抽奖”进入下一局")
        self.motion_var.set("结束")
        self.update_display()
        self._set_controls_enabled(True)

    @staticmethod
    def _blend_hex_colors(background: str, foreground: str, fraction: float) -> str:
        """Blend two #RRGGBB colors for a Canvas-compatible fade effect."""
        fraction = max(0.0, min(1.0, float(fraction)))
        bg = background.lstrip("#")
        fg = foreground.lstrip("#")
        if len(bg) != 6 or len(fg) != 6:
            return foreground
        channels = []
        for offset in (0, 2, 4):
            start = int(bg[offset:offset + 2], 16)
            end = int(fg[offset:offset + 2], 16)
            channels.append(round(start + (end - start) * fraction))
        return "#" + "".join(f"{value:02X}" for value in channels)

    @staticmethod
    def _cash_lamp_polygon(
        cx: float,
        cy: float,
        width: float,
        height: float,
        skew: float,
        scale: float = 1.0,
    ) -> tuple[float, ...]:
        """Return a slightly skewed banknote polygon."""
        half_w = width * scale / 2.0
        half_h = height * scale / 2.0
        skew = skew * scale
        return (
            cx - half_w + skew, cy - half_h,
            cx + half_w + skew, cy - half_h,
            cx + half_w - skew, cy + half_h,
            cx - half_w - skew, cy + half_h,
        )

    def _draw_cash_lamp(
        self,
        canvas: tk.Canvas,
        *,
        lamp_id: str,
        amount: int,
        cx: float,
        cy: float,
        width: float,
        height: float,
        skew: float,
        illuminated: bool,
    ) -> None:
        """Draw one fixed cash plaque, including a bright electromechanical glow."""
        jackpot = lamp_id == "JACKPOT"
        angle = -4 if skew < -1 else (4 if skew > 1 else 0)

        if illuminated:
            for scale, fill in (
                (1.22, "#655A19"),
                (1.14, "#A98A22"),
                (1.07, "#E2C54F"),
            ):
                canvas.create_polygon(
                    *self._cash_lamp_polygon(cx, cy, width, height, skew, scale),
                    fill=fill,
                    outline="",
                )

        outer_fill = "#F7E8A0" if illuminated else "#4B493B"
        outer_outline = "#FFF7C6" if illuminated else "#766D4D"
        canvas.create_polygon(
            *self._cash_lamp_polygon(cx, cy, width, height, skew),
            fill=outer_fill,
            outline=outer_outline,
            width=3 if illuminated else 2,
        )

        inset_scale = 0.84
        inner_fill = (
            "#F4F0CE" if illuminated and jackpot
            else "#D8E5BF" if illuminated
            else "#606050"
        )
        canvas.create_polygon(
            *self._cash_lamp_polygon(
                cx, cy, width, height, skew, inset_scale
            ),
            fill=inner_fill,
            outline="#7B713D" if illuminated else "#403E34",
            width=1,
        )

        # Banknote corner medallions and center denomination.
        medallion_fill = "#B7C995" if illuminated else "#515344"
        for dx in (-width * 0.31, width * 0.31):
            canvas.create_oval(
                cx + dx - 8,
                cy - 8,
                cx + dx + 8,
                cy + 8,
                fill=medallion_fill,
                outline="#6D744D" if illuminated else "#3C3E34",
            )

        value_fill = "#8B1D23" if jackpot and illuminated else (
            "#255F47" if illuminated else "#292D28"
        )
        value_font = 25 if jackpot else 22
        canvas.create_text(
            cx,
            cy - 1,
            text=f"${amount:,}",
            fill=value_fill,
            font=(Theme.FONT, value_font, "bold"),
            angle=angle,
        )

        if illuminated:
            # Small incandescent bulbs around the plaque make the selected CASH
            # position visibly light up rather than merely changing color.
            bulb_points = (
                (-0.40, -0.52), (-0.20, -0.54), (0.0, -0.55),
                (0.20, -0.54), (0.40, -0.52),
                (-0.43, 0.52), (-0.20, 0.54), (0.0, 0.55),
                (0.20, 0.54), (0.43, 0.52),
            )
            radius = 3.2 if jackpot else 2.8
            for px, py in bulb_points:
                bx = cx + px * width
                by = cy + py * height
                canvas.create_oval(
                    bx - radius,
                    by - radius,
                    bx + radius,
                    by + radius,
                    fill="#FFF5A6",
                    outline="#F5C63F",
                    width=1,
                )

    def _draw_top_dollar_logo(self, canvas: tk.Canvas) -> None:
        """Paint a compact hand-lettered topper logo inspired by the cabinet."""
        canvas.create_text(
            115, 54,
            text="TOP",
            fill="#E9C866",
            font=(Theme.FONT, 25, "bold"),
            anchor=tk.CENTER,
        )
        canvas.create_text(
            115, 82,
            text="DOLLAR",
            fill="#D87B67",
            font=(Theme.FONT, 23, "bold"),
            anchor=tk.CENTER,
        )
        canvas.create_text(
            115, 104,
            text="CASH FEATURE",
            fill="#EBD89D",
            font=(Theme.FONT, 8, "bold"),
            anchor=tk.CENTER,
        )

    def _draw_top_dollar_offer_screen(self) -> None:
        canvas = self.offer_canvas
        if canvas is None:
            return
        canvas.delete("all")
        width = float(self.CANVAS_WIDTH)
        height = float(self.CANVAS_HEIGHT)

        # Chrome frame and deep-blue dotted glass, close to the early topper.
        canvas.create_rectangle(0, 0, width, height, fill="#171717", outline="")
        canvas.create_rectangle(
            10, 8, width - 10, height - 8,
            fill="#8B8175", outline="#D5CCC0", width=3,
        )
        canvas.create_rectangle(
            22, 18, width - 22, height - 18,
            fill="#0F2240", outline="#B7923E", width=4,
        )
        canvas.create_rectangle(
            30, 26, width - 30, 440,
            fill="#132B50", outline="#6C5E3B", width=2,
        )

        sparkle_colors = ("#3B5D85", "#57799D", "#A88B4B")
        for x, y, shade in self.offer_sparkles:
            r = 1 if shade < 2 else 2
            canvas.create_oval(
                x - r, y - r, x + r, y + r,
                fill=sparkle_colors[shade], outline="",
            )

        self._draw_top_dollar_logo(canvas)

        # Four-offer indicator in the upper-right, styled as a small glass panel.
        display_offer_number = (
            self.offer_intro_number if self.offer_intro_active else self.offer_number
        )
        canvas.create_rectangle(
            568, 42, 684, 104,
            fill="#D8D1B2", outline="#A58537", width=3,
        )
        canvas.create_text(
            626, 57, text="4 OFFERS",
            fill="#443C32", font=(Theme.FONT, 9, "bold"),
        )
        for index in range(4):
            active = index == display_offer_number - 1
            x = 590 + index * 24
            canvas.create_oval(
                x - 7, 72, x + 7, 86,
                fill="#FFF09A" if active else "#5B5548",
                outline="#C59627" if active else "#34312B",
                width=2,
            )
            canvas.create_text(
                x, 94, text=str(index + 1),
                fill="#4B4233" if active else "#C3B89C",
                font=(Theme.FONT, 7, "bold"),
            )

        revealed_lamps = set(self.offer_lamp_ids[: self.offer_revealed_count])
        for lamp_id, amount, cx, cy, lamp_w, lamp_h, skew in TOP_DOLLAR_LAMP_LAYOUT:
            self._draw_cash_lamp(
                canvas,
                lamp_id=lamp_id,
                amount=amount,
                cx=cx,
                cy=cy,
                width=lamp_w,
                height=lamp_h,
                skew=skew,
                illuminated=lamp_id in revealed_lamps,
            )

        fully_revealed = bool(self.offer_lamp_ids) and (
            self.offer_revealed_count >= len(self.offer_lamp_ids)
        )

        # Original-style lower meter and square red choice buttons.
        canvas.create_rectangle(
            226, 458, 520, 522,
            fill="#B7C8C9", outline="#E5DFBD", width=3,
        )
        canvas.create_rectangle(
            236, 467, 510, 513,
            fill="#354E52", outline="#223537", width=2,
        )
        if self.offer_intro_active:
            meter_text = "最高奖金"
            meter_subtext = "下个报价"
        elif fully_revealed:
            payout = float(self.multiplier) * float(self.current_offer)
            meter_text = f"本轮报价 ${self.current_offer:,.0f}"
            meter_subtext = f"总赔付 ${payout:,.2f}"
        else:
            meter_text = "进行下个报价"
            meter_subtext = "灯光亮起中，请稍后"
        canvas.create_text(
            373, 483, text=meter_text,
            fill="#EAFBEB", font=(Theme.FONT, 18, "bold"),
        )
        canvas.create_text(
            373, 504, text=meter_subtext,
            fill="#AEE2C4", font=(Theme.FONT, 9, "bold"),
        )

        canvas.create_rectangle(
            54, 456, 220, 526,
            fill="#3D2528", outline="#D1B15B", width=3,
        )
        canvas.create_rectangle(
            526, 456, 692, 526,
            fill="#3D2528", outline="#D1B15B", width=3,
        )

        if self.bonus_accepted:
            helper = "接受报价！恭喜您！"
        elif self.offer_intro_active:
            helper = "请稍后..."
        elif fully_revealed and self.offer_lamp_ids == ("JACKPOT",):
            helper = "最高奖金 — 最高赔付，自动接受报价！"
        elif self.offer_number == 4 and fully_revealed:
            helper = "最后报价 — 必须按下“接受报价”按钮"
        elif fully_revealed:
            helper = "按下“接受报价”获取当前奖金 或 按下“再来一次”获取下一个报价"
        else:
            helper = f"报价 {max(1, self.offer_number)} / 4"
        canvas.create_text(
            width / 2,
            430,
            text=helper,
            fill="#F0D891",
            font=(Theme.FONT, 10, "bold"),
        )

        # Tk Canvas has no per-item alpha channel.  Fade the title by blending
        # its text color into the topper's blue background over timed frames.
        if self.offer_intro_active and self.offer_intro_text:
            intro_bg = "#132B50"
            title_color = self._blend_hex_colors(
                intro_bg, "#FFF3B0", self.offer_intro_alpha
            )
            shadow_color = self._blend_hex_colors(
                intro_bg, "#684C18", self.offer_intro_alpha
            )
            canvas.create_rectangle(
                108, 196, width - 108, 318,
                fill=intro_bg, outline="#836B32", width=2,
            )
            canvas.create_text(
                width / 2 + 3, 260 + 3,
                text=self.offer_intro_text,
                fill=shadow_color,
                font=(Theme.FONT, 34, "bold"),
            )
            canvas.create_text(
                width / 2, 260,
                text=self.offer_intro_text,
                fill=title_color,
                font=(Theme.FONT, 34, "bold"),
            )

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    @staticmethod
    @staticmethod
    def _symbol_short_name(symbol: str) -> str:
        return {
            HIDDEN_SPACE: "空白",
            CHERRY: "樱桃",
            BAR: "BAR",
            DOUBLE_BAR: "2BAR",
            TRIPLE_BAR: "3BAR",
            SEVEN: "7",
            DOUBLE_DIAMOND: "钻石",
            CASH: "CASH",
        }.get(symbol, symbol)

    def _format_center_result(self, symbols: Sequence[str]) -> str:
        return "  ".join(
            f"[{self._symbol_short_name(str(symbol)):^4}]" for symbol in symbols
        )

    @staticmethod
    def _draw_double_diamond_icon(
        canvas: tk.Canvas,
        x: float,
        y: float,
        size: float,
        *,
        compact: bool = False,
        fade: bool = False,
    ) -> None:
        """Draw the photographed turquoise/purple Double Diamond reel badge."""
        del fade
        size = max(2.0, float(size))
        outer_w = size * 4.78
        outer_h = size * 2.56
        edge_w = max(1, int(round(size * 0.14)))

        # Heavy black edge and lower-right shadow reproduce the printed reel art.
        canvas.create_oval(
            x - outer_w / 2 + size * 0.10,
            y - outer_h / 2 + size * 0.12,
            x + outer_w / 2 + size * 0.10,
            y + outer_h / 2 + size * 0.12,
            fill="#111315",
            outline="",
        )
        canvas.create_oval(
            x - outer_w / 2,
            y - outer_h / 2,
            x + outer_w / 2,
            y + outer_h / 2,
            fill="#183C43",
            outline="#080A0B",
            width=edge_w,
        )

        rim_w = outer_w * 0.88
        rim_h = outer_h * 0.80
        canvas.create_oval(
            x - rim_w / 2,
            y - rim_h / 2,
            x + rim_w / 2,
            y + rim_h / 2,
            fill="#29AAA9",
            outline="#80DCD4",
            width=max(1, int(round(size * 0.10))),
        )

        # Dark inner keyline and magenta/purple centre.
        inner_w = rim_w * 0.68
        inner_h = rim_h * 0.67
        canvas.create_oval(
            x - inner_w / 2,
            y - inner_h / 2,
            x + inner_w / 2,
            y + inner_h / 2,
            fill="#46264F",
            outline="#153B42",
            width=max(1, int(round(size * 0.11))),
        )
        canvas.create_oval(
            x - inner_w * 0.43,
            y - inner_h * 0.39,
            x + inner_w * 0.43,
            y + inner_h * 0.39,
            fill="#75406F",
            outline="#B77EAB",
            width=max(1, int(round(size * 0.06))),
        )

        # Four turquoise ornaments are visible on the original oval ring.
        ornament_r = max(0.8, size * 0.085)
        for ox, oy in (
            (-rim_w * 0.39, 0.0),
            (rim_w * 0.39, 0.0),
            (-rim_w * 0.27, -rim_h * 0.31),
            (rim_w * 0.27, rim_h * 0.31),
        ):
            canvas.create_oval(
                x + ox - ornament_r,
                y + oy - ornament_r,
                x + ox + ornament_r,
                y + oy + ornament_r,
                fill="#B4EEE5",
                outline="#176C70",
                width=1,
            )

        def draw_gem(cx: float, cy: float, gem_size: float) -> None:
            gem_w = gem_size * 1.12
            gem_h = gem_size * 0.98
            top_y = cy - gem_h * 0.45
            crown_y = cy - gem_h * 0.08
            tip_y = cy + gem_h * 0.52
            left_x = cx - gem_w * 0.50
            right_x = cx + gem_w * 0.50
            top_left_x = cx - gem_w * 0.27
            top_right_x = cx + gem_w * 0.27

            # Small dark offset gives each printed gem a crisp sticker edge.
            canvas.create_polygon(
                cx + size * 0.035, tip_y + size * 0.035,
                left_x + size * 0.035, crown_y + size * 0.035,
                top_left_x + size * 0.035, top_y + size * 0.035,
                top_right_x + size * 0.035, top_y + size * 0.035,
                right_x + size * 0.035, crown_y + size * 0.035,
                fill="#222327", outline="",
            )
            canvas.create_polygon(
                cx, tip_y,
                left_x, crown_y,
                top_left_x, top_y,
                top_right_x, top_y,
                right_x, crown_y,
                fill="#F8F7EF",
                outline="#4B4D50",
                width=max(1, int(round(size * 0.045))),
            )

            # Yellow outside facets and cool white/lilac centre match the photo.
            canvas.create_polygon(
                left_x, crown_y,
                top_left_x, top_y,
                cx - gem_w * 0.05, crown_y,
                cx - gem_w * 0.29, cy + gem_h * 0.16,
                fill="#E9B82E", outline="",
            )
            canvas.create_polygon(
                right_x, crown_y,
                top_right_x, top_y,
                cx + gem_w * 0.05, crown_y,
                cx + gem_w * 0.29, cy + gem_h * 0.16,
                fill="#E9B82E", outline="",
            )
            canvas.create_polygon(
                cx - gem_w * 0.29, cy + gem_h * 0.16,
                cx - gem_w * 0.05, crown_y,
                cx, tip_y,
                fill="#D8D4E1", outline="",
            )
            canvas.create_polygon(
                cx + gem_w * 0.29, cy + gem_h * 0.16,
                cx + gem_w * 0.05, crown_y,
                cx, tip_y,
                fill="#FDFCF7", outline="",
            )
            facet = "#77797C"
            line_w = max(1, int(round(size * 0.035)))
            canvas.create_line(left_x, crown_y, right_x, crown_y, fill=facet, width=line_w)
            canvas.create_line(top_left_x, top_y, cx, crown_y, fill=facet, width=line_w)
            canvas.create_line(top_right_x, top_y, cx, crown_y, fill=facet, width=line_w)
            canvas.create_line(cx, top_y, cx, tip_y, fill=facet, width=line_w)
            canvas.create_line(left_x, crown_y, cx, tip_y, fill=facet, width=line_w)
            canvas.create_line(right_x, crown_y, cx, tip_y, fill=facet, width=line_w)

        gem_size = size * (0.72 if compact else 0.76)
        # The two gems slightly overlap, as on the photographed centre emblem.
        draw_gem(x - size * 0.27, y + size * 0.02, gem_size)
        draw_gem(x + size * 0.27, y - size * 0.02, gem_size)

        if not compact:
            font_size = max(5, int(round(size * 0.31)))
            ring_text_color = "#155E68"
            canvas.create_text(
                x,
                y - outer_h * 0.33,
                text="DOUBLE",
                fill=ring_text_color,
                font=(Theme.FONT, font_size, "bold"),
            )
            canvas.create_text(
                x,
                y + outer_h * 0.33,
                text="DIAMOND",
                fill=ring_text_color,
                font=(Theme.FONT, font_size, "bold"),
            )

    @staticmethod
    def _draw_single_diamond_background(
        canvas: tk.Canvas,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        point_up: bool,
    ) -> None:
        """Draw the photographed white/yellow faceted diamond behind BARs.

        Geometry is defined in normalized coordinates so the same artwork can be
        flipped vertically for UP/DWN reel-strip symbols without changing its
        proportions.  The wider shoulders, narrow crown, pale centre facets and
        dark printed keyline are tuned to the uploaded physical-reel photos.
        """
        width = max(8.0, float(width))
        height = max(12.0, float(height))
        cfg = BAR_DIAMOND_ARTWORK

        def point(nx: float, ny: float) -> tuple[float, float]:
            if point_up:
                ny = -ny
            return x + nx * width, y + ny * height

        def flat(*pairs: tuple[float, float]) -> tuple[float, ...]:
            return tuple(value for pair in pairs for value in pair)

        top_y = float(cfg["top_y"])
        shoulder_y = float(cfg["shoulder_y"])
        tip_y = float(cfg["tip_y"])
        top_half_x = float(cfg["top_half_x"])
        shoulder_half_x = float(cfg["shoulder_half_x"])
        inner_top_half_x = float(cfg["inner_top_half_x"])
        belt_half_x = float(cfg["belt_half_x"])
        belt_y = float(cfg["belt_y"])
        lower_half_x = float(cfg["lower_half_x"])
        lower_y = float(cfg["lower_y"])

        top_left = point(-top_half_x, top_y)
        top_right = point(top_half_x, top_y)
        left_shoulder = point(-shoulder_half_x, shoulder_y)
        right_shoulder = point(shoulder_half_x, shoulder_y)
        tip = point(0.0, tip_y)
        outer = (tip, left_shoulder, top_left, top_right, right_shoulder)

        # The original strip has a thin, slightly offset charcoal print shadow.
        shadow_offset = max(1.0, min(width, height) * 0.017)
        shadow = tuple(
            (px + shadow_offset, py + shadow_offset) for px, py in outer
        )
        canvas.create_polygon(
            flat(*shadow),
            fill=str(cfg["shadow"]),
            outline="",
        )
        canvas.create_polygon(
            flat(*outer),
            fill=str(cfg["body"]),
            outline=str(cfg["outline"]),
            width=2,
        )

        top_inner_left = point(-inner_top_half_x, top_y)
        top_mid = point(0.0, top_y)
        top_inner_right = point(inner_top_half_x, top_y)
        belt_left = point(-belt_half_x, belt_y)
        belt_mid = point(0.0, belt_y)
        belt_right = point(belt_half_x, belt_y)
        lower_left = point(-lower_half_x, lower_y)
        lower_mid = point(0.0, lower_y)
        lower_right = point(lower_half_x, lower_y)

        body = str(cfg["body"])
        white = str(cfg["white"])
        cool_white = str(cfg["cool_white"])
        gold = str(cfg["gold"])
        pale_gold = str(cfg["pale_gold"])

        # Upper crown: yellow outer wings, mostly white centre facets.
        canvas.create_polygon(
            flat(left_shoulder, top_left, top_inner_left, belt_left),
            fill=gold, outline="",
        )
        canvas.create_polygon(
            flat(top_left, top_inner_left, belt_left),
            fill=pale_gold, outline="",
        )
        canvas.create_polygon(
            flat(top_inner_left, top_mid, belt_mid, belt_left),
            fill=white, outline="",
        )
        canvas.create_polygon(
            flat(top_mid, top_inner_right, belt_right, belt_mid),
            fill=cool_white, outline="",
        )
        canvas.create_polygon(
            flat(top_inner_right, top_right, right_shoulder, belt_right),
            fill=gold, outline="",
        )
        canvas.create_polygon(
            flat(top_inner_right, top_right, belt_right),
            fill=pale_gold, outline="",
        )

        # Lower pavilion: narrow yellow sides and alternating white/grey centre.
        canvas.create_polygon(
            flat(left_shoulder, belt_left, lower_left, tip),
            fill=pale_gold, outline="",
        )
        canvas.create_polygon(
            flat(belt_left, belt_mid, lower_mid, lower_left),
            fill=cool_white, outline="",
        )
        canvas.create_polygon(
            flat(belt_mid, belt_right, lower_right, lower_mid),
            fill=white, outline="",
        )
        canvas.create_polygon(
            flat(right_shoulder, belt_right, lower_right, tip),
            fill=gold, outline="",
        )
        canvas.create_polygon(
            flat(lower_left, lower_mid, tip),
            fill=body, outline="",
        )
        canvas.create_polygon(
            flat(lower_mid, lower_right, tip),
            fill=white, outline="",
        )

        # Facet keylines.  Keep these thin: the reel photo uses grey, not black,
        # internal lines, while the outside silhouette carries the dark keyline.
        facet = str(cfg["facet"])
        facet_lines = (
            (left_shoulder, right_shoulder),
            (top_left, belt_left),
            (top_inner_left, belt_mid),
            (top_mid, lower_mid),
            (top_inner_right, belt_mid),
            (top_right, belt_right),
            (left_shoulder, tip),
            (belt_left, tip),
            (belt_right, tip),
            (right_shoulder, tip),
            (lower_left, lower_right),
        )
        for a, b in facet_lines:
            canvas.create_line(*a, *b, fill=facet, width=1)

        # Redraw the outside keyline last so facet fills never soften its edge.
        canvas.create_line(
            *flat(*outer, outer[0]),
            fill=str(cfg["outline"]),
            width=2,
            joinstyle=tk.MITER,
        )

    def _bar_background_orientation(
        self,
        reel_index: Optional[int],
        physical_stop_index: Optional[int],
    ) -> Optional[str]:
        """Return ``up``/``down`` for permanent diamond-backed BAR-family stops."""
        if reel_index is None or physical_stop_index is None:
            return None
        reel_index = int(reel_index)
        if not 0 <= reel_index < 3:
            return None
        return REEL_DIAMOND_BACKED_BAR_STOPS[reel_index].get(
            int(physical_stop_index) + 1
        )

    def _draw_symbol(
        self,
        canvas: tk.Canvas,
        symbol: str,
        x: float,
        y: float,
        scale: float,
        *,
        fade: bool,
        compact: bool = False,
        reel_index: Optional[int] = None,
        physical_stop_index: Optional[int] = None,
    ) -> None:
        """绘制老虎机图案，特殊钻石 BAR 与转动中的普通 BAR 使用相同配色。"""
        del fade

        if symbol == HIDDEN_SPACE:
            return

        s = max(0.28 if compact else 0.55, float(scale))

        if symbol == SEVEN:
            font_size = 20 if compact else max(30, int(58 * s))
            canvas.create_text(
                x + (1 if compact else 3 * s),
                y + (1 if compact else 3 * s),
                text="7",
                fill="#2A0B0B",
                font=(Theme.FONT, font_size, "bold"),
            )
            canvas.create_text(
                x,
                y,
                text="7",
                fill="#E52B2F",
                font=(Theme.FONT, font_size, "bold"),
            )
            return

        if symbol == CHERRY:
            radius = 5.1 if compact else 11.3 * s
            stem_width = 1 if compact else max(2, int(2.4 * s))
            left_cx = x - radius * 0.78
            right_cx = x + radius * 0.66
            fruit_top = y + radius * 0.02
            fruit_bottom = y + radius * 1.78

            canvas.create_line(
                left_cx + radius * 0.10,
                y - radius * 0.08,
                x - radius * 0.22,
                y - radius * 1.04,
                x + radius * 0.10,
                y - radius * 1.72,
                fill="#235F2F",
                width=stem_width,
                smooth=True,
            )
            canvas.create_line(
                right_cx - radius * 0.08,
                y - radius * 0.06,
                x + radius * 0.30,
                y - radius * 0.96,
                x + radius * 0.10,
                y - radius * 1.72,
                fill="#235F2F",
                width=stem_width,
                smooth=True,
            )
            canvas.create_polygon(
                x + radius * 0.04,
                y - radius * 1.74,
                x + radius * 0.98,
                y - radius * 2.05,
                x + radius * 0.55,
                y - radius * 1.28,
                x + radius * 0.20,
                y - radius * 1.32,
                fill="#4AAE51",
                outline="#1A5B26",
                width=1,
            )

            for cx, tilt in ((left_cx, -1.0), (right_cx, 1.0)):
                canvas.create_oval(
                    cx - radius,
                    fruit_top,
                    cx + radius,
                    fruit_bottom,
                    fill="#DB1E2E",
                    outline="#7B0F17",
                    width=1 if compact else 2,
                )
                canvas.create_oval(
                    cx - radius * 0.18 + tilt * radius * 0.04,
                    fruit_top + radius * 0.18,
                    cx + radius * 0.34 + tilt * radius * 0.04,
                    fruit_top + radius * 0.62,
                    fill="#FFB4BE",
                    outline="",
                )
                canvas.create_arc(
                    cx - radius * 0.92,
                    fruit_top + radius * 0.10,
                    cx + radius * 0.92,
                    fruit_bottom,
                    start=200 if tilt < 0 else 160,
                    extent=120 if tilt < 0 else -120,
                    style=tk.ARC,
                    outline="#A9101E",
                    width=1,
                )
            return

        if symbol == CASH:
            width = 50.0 if compact else 112.0 * s
            height = 23.0 if compact else 66.0 * s
            canvas.create_polygon(
                x - width / 2, y - height / 2,
                x + width / 2, y - height / 2,
                x + width / 2 - 7 * s, y,
                x + width / 2, y + height / 2,
                x - width / 2, y + height / 2,
                x - width / 2 + 7 * s, y,
                fill="#2E7B49",
                outline="#D8B640",
                width=2 if not compact else 1,
            )
            canvas.create_text(
                x,
                y - (5 * s if not compact else 2),
                text="CASH",
                fill="#FFF1A8",
                font=(Theme.FONT, 10 if compact else max(20, int(28 * s)), "bold"),
            )
            if not compact:
                canvas.create_text(
                    x,
                    y + 19 * s,
                    text="TOP DOLLAR",
                    fill="#FFFFFF",
                    font=(Theme.FONT, max(7, int(9 * s)), "bold"),
                )
            return

        if symbol == DOUBLE_DIAMOND:
            icon_size = 9.2 if compact else 20.0 * s
            self._draw_double_diamond_icon(
                canvas,
                x,
                y,
                icon_size,
                compact=compact,
                fade=False,
            )
            return

        if symbol in BAR_SYMBOLS:
            count = {
                BAR: 1,
                DOUBLE_BAR: 2,
                TRIPLE_BAR: 3,
            }[symbol]

            orientation = self._bar_background_orientation(
                reel_index,
                physical_stop_index,
            )
            is_special_bar = orientation is not None and not compact

            if compact:
                bar_width = 42.0
                bar_height = 6.2
                gap = 1.3
                font_size = 5
            else:
                bar_width = 120 * s
                bar_height = 20 * s
                gap = 2.5 * s
                font_size = 18

            total_height = count * bar_height + (count - 1) * gap
            top = y - total_height / 2

            # 普通停点和 INITIAL_PHYSICAL_STOPS 统一使用同一套颜色。
            bar_fill = "#111014"
            bar_outline = "#7A257F"
            top_highlight = "#D56BDA"
            bottom_shadow = "#50205A"

            bar_text_color = {
                BAR: "#7DDCFF",
                DOUBLE_BAR: "#D84CDF",
                TRIPLE_BAR: "#F4F06A",
            }[symbol]

            def draw_bar_plate(index: int) -> None:
                y1 = top + index * (bar_height + gap)
                y2 = y1 + bar_height

                canvas.create_rectangle(
                    x - bar_width / 2,
                    y1,
                    x + bar_width / 2,
                    y2,
                    fill=bar_fill,
                    outline=bar_outline,
                    width=1 if compact else 2,
                )
                canvas.create_line(
                    x - bar_width / 2 + 2,
                    y1 + 2,
                    x + bar_width / 2 - 2,
                    y1 + 2,
                    fill=top_highlight,
                    width=1,
                )
                canvas.create_line(
                    x - bar_width / 2 + 2,
                    y2 - 2,
                    x + bar_width / 2 - 2,
                    y2 - 2,
                    fill=bottom_shadow,
                    width=1,
                )
                # BAR 字样改成三个字母独立绘制，
                # 使用更宽、更粗的字体，并扩大横向排列宽度。
                bar_text_y = (y1 + y2) / 2

                if compact:
                    letter_spacing = 7.5
                    letter_font_size = 6
                else:
                    letter_spacing = 27.0 * s
                    letter_font_size = max(17, int(19 * s))

                bar_font = (
                    "Arial Black",
                    letter_font_size,
                    "bold",
                )

                for letter, offset_x in zip(
                    "BAR",
                    (-letter_spacing, 0.0, letter_spacing),
                ):
                    # 轻微黑色阴影，让字样更像实体卷带印刷
                    canvas.create_text(
                        x + offset_x + (0.6 if compact else 1.2),
                        bar_text_y + (0.5 if compact else 1.0),
                        text=letter,
                        fill="#231728",
                        font=bar_font,
                    )

                    canvas.create_text(
                        x + offset_x,
                        bar_text_y,
                        text=letter,
                        fill=bar_text_color,
                        font=bar_font,
                    )

            if is_special_bar:
                diamond_width = float(BAR_DIAMOND_ARTWORK["width"])
                diamond_height = float(BAR_DIAMOND_ARTWORK["height"])

                if count == 1:
                    bars_behind_diamond = (0,)
                    bars_in_front_of_diamond = ()
                elif count == 2:
                    bars_behind_diamond = (0,)
                    bars_in_front_of_diamond = (1,)
                else:
                    bars_behind_diamond = (0, 2)
                    bars_in_front_of_diamond = (1,)

                for index in bars_behind_diamond:
                    draw_bar_plate(index)

                self._draw_single_diamond_background(
                    canvas,
                    x,
                    y,
                    diamond_width,
                    diamond_height,
                    point_up=(orientation == "up"),
                )

                for index in bars_in_front_of_diamond:
                    draw_bar_plate(index)
            else:
                for index in range(count):
                    draw_bar_plate(index)

            return

        canvas.create_text(
            x,
            y,
            text=str(symbol),
            fill=Theme.REEL_TEXT,
            font=(Theme.FONT, int(22 * s), "bold"),
        )

    def draw_scene(self) -> None:
        c = self.game_canvas
        c.delete("all")

        w = self.CANVAS_WIDTH
        h = self.CANVAS_HEIGHT

        if self.light_mode == "win":
            canvas_bg = "#253829"
            cabinet_fill = "#ECE8F0"
            cabinet_outline = Theme.WIN
            lamp_fill = "#66C677"
            glow = Theme.WIN
        elif self.light_mode == "spin":
            canvas_bg = "#2B2040"
            cabinet_fill = "#EEE7F4"
            cabinet_outline = "#8E6DB5"
            lamp_fill = "#C7AEE2"
            glow = "#BFA0DD"
        else:
            canvas_bg = Theme.CANVAS_BG
            cabinet_fill = "#EEE7F4"
            cabinet_outline = "#80629F"
            lamp_fill = "#D5C0EA"
            glow = Theme.GOLD

        c.create_rectangle(0, 0, w, h, fill=canvas_bg, outline="")
        c.create_rectangle(
            68,
            25,
            w - 68,
            374,
            fill=cabinet_fill,
            outline=cabinet_outline,
            width=3,
        )
        c.create_rectangle(
            92,
            50,
            w - 92,
            305,
            fill=Theme.REEL_WELL,
            outline=Theme.GOLD,
            width=3,
        )

        for lamp_y in (40, 358):
            for lamp_x in range(112, w - 112, 46):
                c.create_oval(
                    lamp_x - 8,
                    lamp_y - 8,
                    lamp_x + 8,
                    lamp_y + 8,
                    fill=lamp_fill,
                    outline="#F0DEAA",
                    width=1,
                )

        reel_total = self.REEL_WIDTH * 3 + self.REEL_GAP * 2
        reel_start_x = (w - reel_total) / 2
        center_y = self.REEL_TOP_Y + self.REEL_HEIGHT / 2

        # Labels above each physical reel.
        for index in range(3):
            x = reel_start_x + index * (self.REEL_WIDTH + self.REEL_GAP)
            c.create_text(
                x + self.REEL_WIDTH / 2,
                69,
                text=f"REEL {index + 1}",
                fill="#E7D8F3",
                font=(Theme.FONT, 8, "bold"),
            )

        # Draw each reel in its own clipped canvas.
        for reel_index, reel_canvas in enumerate(self.reel_canvases):
            reel_canvas.delete("all")
            reel_canvas.configure(
                bg=Theme.REEL_FACE,
                highlightbackground=(
                    Theme.WIN
                    if reel_index in self.winning_reels
                    else Theme.REEL_EDGE
                ),
            )

            sequence = self.reel_sequences[reel_index]
            position = self.reel_positions[reel_index]
            local_center_y = self.REEL_HEIGHT / 2
            base_index = math.floor(position)
            center_index = int(round(position))

            for absolute_index in range(base_index - 4, base_index + 5):
                symbol = str(sequence[absolute_index % len(sequence)])
                y = local_center_y + (
                    absolute_index - position
                ) * self.REEL_SPACING
                distance = abs(y - local_center_y)
                if y < -65 or y > self.REEL_HEIGHT + 65:
                    continue
                if symbol == HIDDEN_SPACE:
                    # Hidden detent occupies a full physical stop but draws nothing.
                    continue

                # Reel symbols keep the exact center-line size at all positions.
                scale = 1.0
                fade = False

                logical_row = absolute_index - center_index
                if (
                    reel_index in self.winning_reels
                    and logical_row == 0
                    and distance < 24
                ):
                    reel_canvas.create_rectangle(
                        8,
                        y - 43,
                        self.REEL_WIDTH - 8,
                        y + 43,
                        outline=Theme.WIN,
                        width=4,
                    )

                self._draw_symbol(
                    reel_canvas,
                    symbol,
                    self.REEL_WIDTH / 2,
                    y,
                    scale,
                    fade=fade,
                    reel_index=reel_index,
                    physical_stop_index=(absolute_index % len(sequence)),
                )

            reel_canvas.create_line(
                0,
                local_center_y,
                self.REEL_WIDTH,
                local_center_y,
                fill=Theme.PAYLINE,
                width=4,
            )
            reel_canvas.create_line(
                0,
                local_center_y - 5,
                self.REEL_WIDTH,
                local_center_y - 5,
                fill=Theme.GOLD_SOFT,
                width=1,
            )

        global_payline_y = 70 + center_y
        c.create_line(
            98,
            center_y,
            w - 98,
            center_y,
            fill=Theme.PAYLINE,
            width=4,
        )
        c.create_text(
            104,
            center_y - 15,
            text="CENTER PAYLINE",
            fill=glow,
            font=(Theme.FONT, 8, "bold"),
            anchor=tk.W,
        )

        # Motion/status cards.
        card_y = 399
        card_w = 181
        card_gap = 18
        total_cards = card_w * 3 + card_gap * 2
        card_start = (w - total_cards) / 2
        state_labels = {
            "idle": "待机",
            "accelerating": "加速",
            "cruising": "匀速",
            "decelerating": "减速",
            "nudging": "快速移位",
            "stopped": "停止",
        }

        for index in range(3):
            x1 = card_start + index * (card_w + card_gap)
            x2 = x1 + card_w
            state = self.reel_states[index]
            c.create_rectangle(
                x1,
                card_y,
                x2,
                card_y + 78,
                fill=Theme.PANEL_ALT,
                outline=Theme.BORDER_SOFT,
                width=1,
            )
            c.create_text(
                x1 + 12,
                card_y + 18,
                text=f"滚轮 {index + 1}",
                fill=Theme.TEXT_MUTED,
                font=(Theme.FONT_CJK, 8, "bold"),
                anchor=tk.W,
            )
            c.create_text(
                x1 + 12,
                card_y + 43,
                text=state_labels.get(state, state),
                fill=Theme.ACCENT,
                font=(Theme.FONT_CJK, 11, "bold"),
                anchor=tk.W,
            )
            c.create_text(
                x2 - 12,
                card_y + 43,
                text=f"{self.reel_display_speeds[index]:.1f}",
                fill=Theme.TEXT,
                font=(Theme.FONT, 11, "bold"),
                anchor=tk.E,
            )
            c.create_text(
                x2 - 12,
                card_y + 62,
                text="格/秒",
                fill=Theme.TEXT_DIM,
                font=(Theme.FONT_CJK, 7),
                anchor=tk.E,
            )

        c.create_text(
            52,
            508,
            text=(
                f"本局下注 ${self.current_bet:,.0f}"
            ),
            fill="#F1E8F8",
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.W,
        )

    # ------------------------------------------------------------------
    # Display and closing
    # ------------------------------------------------------------------

    def update_display(self) -> None:
        self.balance_var.set(f"${self.balance:,.2f}")
        self.bet_var.set(f"${self.current_bet:,.2f}")
        self.last_win_var.set(f"${self.last_win:,.2f}")
        self.multiplier_var.set(
            f"{self.multiplier}× · 本局下注 ${self.current_bet:,.0f}"
        )
        self.spin_button.configure(text=f"开始抽奖 · ${self.current_bet:,.0f}")

        self._draw_paytable()
        self._draw_diamond_rule_panel()
        if not self.spinning and not self.bonus_active:
            self._set_controls_enabled(True)
        else:
            self._set_controls_enabled(False)
        self.draw_scene()

    def on_closing(self) -> None:
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None

        if self.win_animation_after_id is not None:
            try:
                self.root.after_cancel(self.win_animation_after_id)
            except tk.TclError:
                pass
            self.win_animation_after_id = None

        self._cancel_bonus_timer()
        self.spinning = False
        self.nudging = False
        self.bonus_active = False
        update_balance_in_json(self.username, self.balance)

        finish = getattr(self.root, "finish", None)
        if callable(finish):
            finish(self.balance)
        else:
            self.root.destroy()


# Backward-friendly aliases for existing hosts.
NumberSlotMachine = TopDollarSlotMachine
DoubleDiamondSlotMachine = TopDollarSlotMachine


def main(
    initial_balance=1000.0,
    username="Guest",
    *,
    parent=None,
    balance=None,
    user=None,
    on_back=None,
    on_balance_change=None,
):
    """Launch standalone or inside the existing EmbeddedGamePage host."""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        if EmbeddedGamePage is None:
            raise RuntimeError(
                "EmbeddedGamePage is unavailable. Place slot_machine.py inside "
                "the Small_Games package or make small_games.py importable."
            )
        page = EmbeddedGamePage(
            parent,
            title="TOP DOLLAR 最高奖金老虎机",
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        page.set_requested_size(1150, 750)
        game = TopDollarSlotMachine(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = TopDollarSlotMachine(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


def _print_audit() -> None:
    print(json.dumps(calculate_virtual_stop_audit(), ensure_ascii=False, indent=2))


def _run_self_tests() -> None:
    tests = {
        (DOUBLE_DIAMOND, DOUBLE_DIAMOND, DOUBLE_DIAMOND): 1000,
        (SEVEN, SEVEN, SEVEN): 80,
        (DOUBLE_DIAMOND, SEVEN, SEVEN): 160,
        (TRIPLE_BAR, TRIPLE_BAR, TRIPLE_BAR): 40,
        (BAR, DOUBLE_BAR, TRIPLE_BAR): 5,
        (CHERRY, HIDDEN_SPACE, HIDDEN_SPACE): 2,
        (CHERRY, CHERRY, HIDDEN_SPACE): 5,
        (CHERRY, DOUBLE_DIAMOND, HIDDEN_SPACE): 4,
        (CHERRY, HIDDEN_SPACE, CASH): 2,
        (DOUBLE_DIAMOND, HIDDEN_SPACE, CASH): 0,
        (BAR, BAR, CASH): 0,
    }
    for line, expected in tests.items():
        actual = evaluate_payline(line).award_credits
        if actual != expected:
            raise AssertionError(
                f"evaluate_payline({line}) returned {actual}; expected {expected}"
            )

    cash_base_tests = {
        (CHERRY, DOUBLE_DIAMOND, CASH): 4,
        (DOUBLE_DIAMOND, CHERRY, CASH): 4,
        (CHERRY, CHERRY, CASH): 5,
        (BAR, BAR, CASH): 0,
    }
    for line, expected in cash_base_tests.items():
        actual = evaluate_cash_trigger_base(line).award_credits
        if actual != expected:
            raise AssertionError(
                f"evaluate_cash_trigger_base({line}) returned {actual}; "
                f"expected {expected}"
            )

    if FIXED_PHYSICAL_REELS != (
        A_PHYSICAL_REEL_ORDER, A_PHYSICAL_REEL_ORDER, B_PHYSICAL_REEL_ORDER
    ):
        raise AssertionError("The configured physical structure must be A-A-B")
    if INITIAL_PHYSICAL_STOPS != (4, 12, 14):
        raise AssertionError("Initial physical stops are incorrect")
    if any(REEL_POST_STOP_NUDGE_TARGETS):
        raise AssertionError("Top Dollar must not contain post-stop nudges")

    for reel_index, mapping in enumerate(REEL_VIRTUAL_STOP_TO_PHYSICAL):
        if len(mapping) != TOTAL_VIRTUAL_STOPS:
            raise AssertionError(f"Reel {reel_index + 1} must map exactly 72 stops")
        if sum(REEL_VIRTUAL_STOP_COUNTS[reel_index]) != TOTAL_VIRTUAL_STOPS:
            raise AssertionError(f"Reel {reel_index + 1} weights must total 72")

    if CASH in A_PHYSICAL_REEL_ORDER:
        raise AssertionError("CASH must not appear on strip A")
    if B_PHYSICAL_REEL_ORDER.count(CASH) != 1:
        raise AssertionError("Strip B must contain one physical CASH symbol")
    cash_index = B_PHYSICAL_REEL_ORDER.index(CASH)
    if B_VIRTUAL_STOP_COUNTS[cash_index] != 1:
        raise AssertionError("CASH must have exactly one virtual stop")

    if len(TOP_DOLLAR_OFFER_PATTERNS) != 512:
        raise AssertionError("Top Dollar must contain 511 stackable combinations plus jackpot")
    if abs(sum(TOP_DOLLAR_OFFER_WEIGHTS) - 1.0) > 1e-12:
        raise AssertionError("Top Dollar offer probabilities must total 1.0")
    known_lamps = set(TOP_DOLLAR_LAMP_VALUES)
    for pattern in TOP_DOLLAR_OFFER_PATTERNS:
        if not pattern or not set(pattern) <= known_lamps:
            raise AssertionError(f"Invalid Top Dollar lamp pattern: {pattern}")
        if len(pattern) != len(set(pattern)):
            raise AssertionError(f"A lamp cannot be lit twice in one offer: {pattern}")
        if "JACKPOT" in pattern and pattern != ("JACKPOT",):
            raise AssertionError("The $1,000 TOP DOLLAR award must be independent")

    jackpot_index = TOP_DOLLAR_OFFER_PATTERNS.index(("JACKPOT",))
    if abs(
        TOP_DOLLAR_OFFER_WEIGHTS[jackpot_index]
        - TOP_DOLLAR_JACKPOT_PROBABILITY
    ) > 1e-15:
        raise AssertionError("The TOP DOLLAR jackpot probability is incorrect")

    raw_offer_mean = sum(
        top_dollar_pattern_value(pattern) * weight
        for pattern, weight in zip(
            TOP_DOLLAR_OFFER_PATTERNS, TOP_DOLLAR_OFFER_WEIGHTS
        )
    )
    if abs(raw_offer_mean - TOP_DOLLAR_TARGET_OFFER_MEAN) > 1e-9:
        raise AssertionError(
            f"Top Dollar mean offer {raw_offer_mean} != {TOP_DOLLAR_TARGET_OFFER_MEAN}"
        )

    expected_lamp_marginals = {
        "R5_MID": 0.47236553622331806,
        "C5_LOW": 0.47236553622331806,
        "R10_TOP": 0.4304353305800252,
        "C10_MID": 0.4304353305800252,
        "C20_TOP": 0.3504221558980562,
        "L20_LOW": 0.3504221558980562,
        "L50_TOP": 0.16522194964699605,
        "L50_MID": 0.16522194964699605,
        "R100_LOW": 0.03628556825544438,
    }
    for lamp_id, expected in expected_lamp_marginals.items():
        actual = sum(
            weight
            for pattern, weight in zip(
                TOP_DOLLAR_OFFER_PATTERNS, TOP_DOLLAR_OFFER_WEIGHTS
            )
            if lamp_id in pattern
        )
        if abs(actual - expected) > 1e-12:
            raise AssertionError(
                f"Lamp marginal {lamp_id} {actual} != {expected}"
            )

    strategy = calculate_offer_strategy_values()
    expected_strategy = (
        78.29669972759442,
        71.37780130870792,
        62.09142790738855,
        48.0,
    )
    for actual, expected in zip(strategy, expected_strategy):
        if abs(actual - expected) > 1e-9:
            raise AssertionError(f"Offer strategy value {actual} != {expected}")

    deterministic_rng = random.Random(20260729)
    for reel_index in range(3):
        for _ in range(200):
            selection = select_reel_stop(deterministic_rng, reel_index)
            if sorted(selection.temporary_numbers_by_virtual_stop) != list(range(1, 73)):
                raise AssertionError("Temporary numbers must be a unique 1..72 permutation")
            expected_physical = REEL_VIRTUAL_STOP_TO_PHYSICAL[reel_index][
                selection.winning_virtual_stop - 1
            ]
            if selection.physical_stop_index != expected_physical:
                raise AssertionError("Virtual stop resolved to the wrong physical stop")

    stats = calculate_theoretical_statistics()
    total_rtp = float(stats["total_optimal_rtp"])
    expected_total_rtp = 1.1371849769525086
    if abs(total_rtp - expected_total_rtp) > 1e-12:
        raise AssertionError(
            f"Total optimal RTP {total_rtp:.9%} != {expected_total_rtp:.9%}"
        )
    if abs(float(stats["bonus_trigger_rate"]) - 1 / 72) > 1e-12:
        raise AssertionError("Bonus trigger frequency must be exactly 1/72")

    print(
        f"{len(tests)} payline tests passed; A-A-B 22/72 reels, no nudges, "
        f"R3 CASH frequency {stats['bonus_trigger_percent']:.6f}%, single-wager "
        f"optimal total RTP {stats['total_optimal_rtp_percent']:.6f}% passed."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Print the Top Dollar 22-stop / 72-virtual-stop configuration and exit.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run evaluator/reel validation tests and exit.",
    )
    args = parser.parse_args()

    if args.self_test:
        _run_self_tests()
    elif args.audit:
        _print_audit()
    else:
        main(10000.0, "demo_player")