from __future__ import annotations

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


VERSION = "SlotMachine-DoubleDiamond-ABA72-R2-PhotoDiamond-V13"

# Internal symbols. HIDDEN_SPACE is an actual blank physical stop and is not drawn.
HIDDEN_SPACE = "<HIDDEN_SPACE>"
CHERRY = "CHERRY"
BAR = "BAR"
DOUBLE_BAR = "DOUBLE_BAR"
TRIPLE_BAR = "TRIPLE_BAR"
SEVEN = "SEVEN"
DOUBLE_DIAMOND = "DOUBLE_DIAMOND"

BAR_SYMBOLS = frozenset({BAR, DOUBLE_BAR, TRIPLE_BAR})
VISIBLE_SYMBOLS = frozenset(
    {CHERRY, BAR, DOUBLE_BAR, TRIPLE_BAR, SEVEN, DOUBLE_DIAMOND}
)
ROW_OFFSETS = (-1, 0, 1)


# ---------------------------------------------------------------------------
# Fixed 22-stop A-B-A physical reels and independent 72-stop virtual mappings
# ---------------------------------------------------------------------------

TOTAL_VIRTUAL_STOPS = 72

# Reel A is the existing first/third-reel strip used by this simulator.  Its
# numbering is retained so older saved positions and the photographed BAR UI
# remain compatible.
A_PHYSICAL_REEL_ORDER: tuple[str, ...] = (
    HIDDEN_SPACE,     #  1 blank
    SEVEN,            #  2 7
    HIDDEN_SPACE,     #  3 blank
    BAR,              #  4 1 BAR / diamond-backed
    HIDDEN_SPACE,     #  5 blank -> nudge to 4
    CHERRY,           #  6 cherry
    HIDDEN_SPACE,     #  7 blank
    DOUBLE_DIAMOND,   #  8 Double Diamond
    HIDDEN_SPACE,     #  9 blank
    BAR,              # 10 1 BAR
    HIDDEN_SPACE,     # 11 blank
    TRIPLE_BAR,       # 12 3 BAR / diamond-backed
    HIDDEN_SPACE,     # 13 blank -> nudge to 12
    SEVEN,            # 14 7
    HIDDEN_SPACE,     # 15 blank -> nudge to 16
    BAR,              # 16 1 BAR / diamond-backed
    HIDDEN_SPACE,     # 17 blank
    DOUBLE_DIAMOND,   # 18 Double Diamond
    HIDDEN_SPACE,     # 19 blank -> nudge to 20
    DOUBLE_BAR,       # 20 2 BAR / diamond-backed
    HIDDEN_SPACE,     # 21 blank
    BAR,              # 22 1 BAR
)

# Reel B follows the published Double Diamond Deluxe ABA strip, line-for-line:
# CH, blank, 2B, blank, 3B-DWN, blank, 1B, blank, 1B-UP, blank,
# 7, blank, 3B-UP, blank, 2B, 1B-UP, blank, blank, DD, blank,
# 2B-DWN, blank.
B_PHYSICAL_REEL_ORDER: tuple[str, ...] = (
    CHERRY,            #  1 CH
    HIDDEN_SPACE,      #  2 blank
    DOUBLE_BAR,        #  3 2B
    HIDDEN_SPACE,      #  4 blank
    TRIPLE_BAR,        #  5 3B DWN
    HIDDEN_SPACE,      #  6 blank -> nudge to 5
    BAR,               #  7 1B
    HIDDEN_SPACE,      #  8 blank -> nudge to 9
    BAR,               #  9 1B UP
    HIDDEN_SPACE,      # 10 blank
    SEVEN,             # 11 7
    HIDDEN_SPACE,      # 12 blank -> nudge to 13
    TRIPLE_BAR,        # 13 3B UP
    HIDDEN_SPACE,      # 14 blank
    DOUBLE_BAR,        # 15 2B
    HIDDEN_SPACE,      # 16 blank -> nudge to 17
    BAR,               # 17 1B
    HIDDEN_SPACE,      # 18 blank
    DOUBLE_DIAMOND,    # 19 DD
    HIDDEN_SPACE,      # 20 blank
    DOUBLE_BAR,        # 21 2B DWN
    HIDDEN_SPACE,      # 22 blank -> nudge to 21
)

FIXED_PHYSICAL_REELS: tuple[tuple[str, ...], ...] = (
    A_PHYSICAL_REEL_ORDER,
    B_PHYSICAL_REEL_ORDER,
    A_PHYSICAL_REEL_ORDER,
)

# Original Reel-A physical-stop weights from the existing 72-stop model.
A_VIRTUAL_STOP_COUNTS: tuple[int, ...] = (
    3, 1, 5, 3, 7, 2, 5, 1, 5, 3, 4,
    1, 2, 1, 8, 3, 5, 1, 5, 2, 3, 2,
)

# Calibrated Reel-B physical-stop weights. Every physical stop keeps at least
# one virtual stop. These weights are redistributed for the corrected B strip:
# stop 9 is 1BAR-UP and stop 16 is 1BAR-UP, with stop 17 nudging to stop 16.
# After all five nudges, Reel B retains the calibrated final symbol counts:
# blank 48, cherry 1, 1BAR 6, 2BAR 9, 3BAR 4, seven 2, DD 2.
# With A-B-A and the current paytable this produces a theoretical RTP of
# 92.5754458% and a hit frequency of 14.9305556%.
B_VIRTUAL_STOP_COUNTS: tuple[int, ...] = (
    1, 8, 3, 8, 1, 1, 1, 1, 1, 8, 2,
    1, 1, 8, 2, 2, 1, 8, 2, 8, 2, 2,
)

REEL_VIRTUAL_STOP_COUNTS: tuple[tuple[int, ...], ...] = (
    A_VIRTUAL_STOP_COUNTS,
    B_VIRTUAL_STOP_COUNTS,
    A_VIRTUAL_STOP_COUNTS,
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

# Backward-friendly aliases refer to Reel 1 / strip A.
PHYSICAL_REEL_ORDER = A_PHYSICAL_REEL_ORDER
VIRTUAL_STOP_COUNTS = A_VIRTUAL_STOP_COUNTS
VIRTUAL_STOP_RANGES = REEL_VIRTUAL_STOP_RANGES[0]
VIRTUAL_STOP_TO_PHYSICAL = REEL_VIRTUAL_STOP_TO_PHYSICAL[0]

# One-based physical-stop nudges.  The Reel-B map follows the UP/DWN markers on
# the published 85895500 strip.  The selected 72-stop result remains recorded;
# the adjacent physical move happens only after the normal spin has stopped.
A_POST_STOP_NUDGE_TARGETS: dict[int, int] = {
    5: 4,
    13: 12,
    15: 16,
    19: 20,
}
B_POST_STOP_NUDGE_TARGETS: dict[int, int] = {
    6: 5,
    8: 9,
    12: 13,
    16: 17,
    22: 21,
}
REEL_POST_STOP_NUDGE_TARGETS: tuple[dict[int, int], ...] = (
    A_POST_STOP_NUDGE_TARGETS,
    B_POST_STOP_NUDGE_TARGETS,
    A_POST_STOP_NUDGE_TARGETS,
)
POST_STOP_NUDGE_TARGETS = A_POST_STOP_NUDGE_TARGETS

# Diamond-backed BAR artwork by one-based physical stop.  Reel B contains five
# nudge-labelled BAR-family symbols in the published strip.
A_DIAMOND_BACKED_BAR_STOPS: dict[int, str] = {
    4: "down",
    12: "down",
    16: "up",
    20: "up",
}
B_DIAMOND_BACKED_BAR_STOPS: dict[int, str] = {
    5: "down",
    9: "up",
    13: "up",
    16: "down",
    21: "down",
}
REEL_DIAMOND_BACKED_BAR_STOPS: tuple[dict[int, str], ...] = (
    A_DIAMOND_BACKED_BAR_STOPS,
    B_DIAMOND_BACKED_BAR_STOPS,
    A_DIAMOND_BACKED_BAR_STOPS,
)
DIAMOND_BACKED_BAR_STOPS = A_DIAMOND_BACKED_BAR_STOPS

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

# Initial center symbols: Reel 1 A-stop 4, Reel 2 B-stop 13, Reel 3 A-stop 20.
INITIAL_PHYSICAL_STOPS: tuple[int, int, int] = (4, 13, 20)


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


def _final_symbol_counts_for_reel(reel_index: int) -> dict[str, int]:
    """Count final displayed symbols across one reel's 72 virtual outcomes."""
    counts = {symbol: 0 for symbol in (HIDDEN_SPACE, CHERRY, BAR, DOUBLE_BAR, TRIPLE_BAR, SEVEN, DOUBLE_DIAMOND)}
    strip = FIXED_PHYSICAL_REELS[reel_index]
    for physical_index in REEL_VIRTUAL_STOP_TO_PHYSICAL[reel_index]:
        final_index = resolve_post_stop_physical_index(physical_index, reel_index)
        counts[strip[final_index]] += 1
    return counts


def calculate_theoretical_statistics() -> dict[str, object]:
    """Enumerate weighted final center-line outcomes and return exact RTP/hit rate."""
    reel_counts = tuple(_final_symbol_counts_for_reel(index) for index in range(3))
    total_combinations = TOTAL_VIRTUAL_STOPS ** 3
    total_award_credits = 0
    winning_combinations = 0

    for symbol_1, count_1 in reel_counts[0].items():
        for symbol_2, count_2 in reel_counts[1].items():
            for symbol_3, count_3 in reel_counts[2].items():
                combinations = count_1 * count_2 * count_3
                result = evaluate_payline((symbol_1, symbol_2, symbol_3))
                total_award_credits += combinations * result.award_credits
                if result.is_win:
                    winning_combinations += combinations

    return {
        "total_combinations": total_combinations,
        "total_award_credits": total_award_credits,
        "winning_combinations": winning_combinations,
        "rtp": total_award_credits / total_combinations,
        "rtp_percent": 100.0 * total_award_credits / total_combinations,
        "hit_rate": winning_combinations / total_combinations,
        "hit_rate_percent": 100.0 * winning_combinations / total_combinations,
        "final_symbol_counts": reel_counts,
    }


def calculate_virtual_stop_audit() -> dict[str, object]:
    """Return every A-B-A physical/virtual mapping plus exact theoretical math."""
    reels: list[dict[str, object]] = []
    for reel_index, (strip, ranges, counts) in enumerate(
        zip(
            FIXED_PHYSICAL_REELS,
            REEL_VIRTUAL_STOP_RANGES,
            REEL_VIRTUAL_STOP_COUNTS,
        )
    ):
        rows: list[dict[str, object]] = []
        nudge_map = REEL_POST_STOP_NUDGE_TARGETS[reel_index]
        diamond_map = REEL_DIAMOND_BACKED_BAR_STOPS[reel_index]
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
                    "nudge_target": nudge_map.get(physical_number),
                    "diamond_orientation": diamond_map.get(physical_number),
                }
            )
        reels.append(
            {
                "reel": reel_index + 1,
                "strip_type": "B" if reel_index == 1 else "A",
                "physical_stops": rows,
                "final_symbol_counts": _final_symbol_counts_for_reel(reel_index),
            }
        )

    return {
        "version": VERSION,
        "model": "three independent 72-stop virtual reels -> A-B-A physical strips -> per-reel adjacent nudge",
        "physical_stop_count_per_reel": 22,
        "virtual_stop_count_per_reel": TOTAL_VIRTUAL_STOPS,
        "reels": reels,
        "theoretical_statistics": calculate_theoretical_statistics(),
    }


# ---------------------------------------------------------------------------
# Account persistence compatibility
# ---------------------------------------------------------------------------


def get_data_file_path() -> str:
    """Preserve the Cash Machine V20 saving_data.json location convention."""
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "../saving_data.json"
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


class DoubleDiamondSlotMachine:
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

    BASE_BET = 5.0
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

        # Every reel independently shuffles 1..72 and draws its own secret number.
        self.rng = random.SystemRandom()

        self.reel_sequences: list[tuple[str, ...]] = [
            tuple(reel) for reel in FIXED_PHYSICAL_REELS
        ]
        for reel in self.reel_sequences:
            _validate_physical_strip(reel)

        # Start all three reels on photographed diamond-backed BAR-family stops.
        # INITIAL_PHYSICAL_STOPS is one-based; reel positions are zero-based.
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

        # 0 = neutral, 1 = highlight the one-Double/X2 panel,
        # 2 = highlight the two-Double/X4 panel.
        self.diamond_rule_highlight = 0

        self.center_symbols = [
            self._symbol_from_position(index) for index in range(3)
        ]

        self.balance_var = tk.StringVar()
        self.bet_var = tk.StringVar()
        self.last_win_var = tk.StringVar()
        self.multiplier_var = tk.StringVar()
        self.result_var = tk.StringVar(value="按下“开始抽奖”")
        self.status_var = tk.StringVar(
            value="只计算中央中奖线 · 每轴独立打乱 1–72 临时数字"
        )
        self.motion_var = tk.StringVar(value="静止")

        self.multiplier_quick_buttons: list[ModernButton] = []
        self.reel_canvases: list[tk.Canvas] = []
        self.paytable_canvas: Optional[tk.Canvas] = None
        self.diamond_rule_canvas: Optional[tk.Canvas] = None

        self.create_widgets()
        self.update_display()

    # ------------------------------------------------------------------
    # Root and layout
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("Double Diamond 双钻石三轴老虎机")
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
        self._draw_double_diamond_icon(icon, 34, 26, 12.5, compact=False)

        tk.Label(
            header,
            text="DOUBLE DIAMOND 双倍钻石",
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT, 18, "bold"),
            anchor=tk.W,
        ).place(x=88, y=10, width=376, height=27)

        tk.Label(
            header,
            text="三轴固定滚轮",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 10, "bold"),
            anchor=tk.W,
        ).place(x=88, y=39, width=486, height=20)

        balance_box = tk.Frame(
            header,
            width=206,
            height=46,
            bg=Theme.PANEL_ALT,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        balance_box.place(
            x=self.SHELL_WIDTH - 220, y=12, width=206, height=46
        )

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
        self.game_canvas.place(
            x=1, y=70, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT
        )

        reel_total = self.REEL_WIDTH * 3 + self.REEL_GAP * 2
        reel_start_x = int(round((self.CANVAS_WIDTH - reel_total) / 2))
        for reel_index in range(3):
            x = 1 + reel_start_x + reel_index * (
                self.REEL_WIDTH + self.REEL_GAP
            )
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
            reel_canvas.place(
                x=x, y=y, width=self.REEL_WIDTH, height=self.REEL_HEIGHT
            )
            self.reel_canvases.append(reel_canvas)

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

            payout = self.current_bet * float(base_multiplier)

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
    def current_bet(self) -> float:
        return self.BASE_BET * self.multiplier

    def set_multiplier(self, value: int) -> None:
        if self.spinning:
            return
        self.multiplier = max(1, min(self.MAX_MULTIPLIER, int(value)))
        self.winning_reels.clear()
        self.light_mode = "idle"
        self.update_display()

    def change_multiplier(self, delta: int) -> None:
        self.set_multiplier(self.multiplier + int(delta))

    def _set_controls_enabled(self, enabled: bool) -> None:
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
        if self.spinning or self.win_animation_after_id is not None:
            return

        if self.balance < self.current_bet:
            messagebox.showwarning(
                "余额不足",
                f"本局需要 ${self.current_bet:,.2f}。",
                parent=self.root,
            )
            return

        # Each reel independently shuffles temporary numbers 1..72, draws one
        # secret number, resolves the original virtual stop, and selects the exact
        # configured physical stop.  No payout or win state is chosen here.
        self.round_reel_selections = self._select_round_reel_stops()
        self.selected_stop_indices = [
            selection.physical_stop_index
            for selection in self.round_reel_selections
        ]
        self.final_stop_indices = []
        for reel_index, stop_index in enumerate(self.selected_stop_indices):
            final_index = resolve_post_stop_physical_index(stop_index, reel_index)
            if (
                final_index != stop_index
                and physical_stop_has_diamond_bar(final_index, reel_index)
            ):
                self.final_stop_indices.append(final_index)
            else:
                self.final_stop_indices.append(stop_index)
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
            self.reel_spin_durations[index] = self.rng.uniform(
                *self.SPIN_DURATIONS[index]
            )
            self.reel_display_speeds[index] = 0.0
            self.reel_states[index] = "accelerating"

        self.spinning = True
        self.result_var.set("滚轮转动中...")
        self.status_var.set("滚轮转动中，祝您好运！")
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
        """Verify the primary stops, then nudge or settle the displayed result."""
        self.after_id = None

        # The normal spin must first land on the exact 72-stop selections.
        primary_indices = [
            int(round(self.reel_positions[index]))
            % len(self.reel_sequences[index])
            for index in range(3)
        ]
        if primary_indices != self.selected_stop_indices:
            raise RuntimeError(
                "Reel animation ended on different stops than those selected at START: "
                f"selected={self.selected_stop_indices}, actual={primary_indices}"
            )

        primary_symbols = [
            self._symbol_from_position(index, 0) for index in range(3)
        ]
        if tuple(primary_symbols) != tuple(self.selected_center_symbols):
            raise RuntimeError(
                "Displayed symbols differ from the exact selected physical stops: "
                f"selected={self.selected_center_symbols}, "
                f"displayed={primary_symbols}"
            )

        self.final_stop_indices = []
        for reel_index, stop_index in enumerate(self.selected_stop_indices):
            final_index = resolve_post_stop_physical_index(stop_index, reel_index)
            if (
                final_index != stop_index
                and physical_stop_has_diamond_bar(final_index, reel_index)
            ):
                self.final_stop_indices.append(final_index)
            else:
                self.final_stop_indices.append(stop_index)
        if self.final_stop_indices != self.selected_stop_indices:
            self._start_post_stop_nudge()
            return

        self.spinning = False
        self._settle_final_display()

    def _start_post_stop_nudge(self) -> None:
        """Move every configured reel one adjacent detent in exactly 0.4 seconds."""
        self.nudging = True
        self.nudge_started = time.monotonic()

        for reel_index in range(3):
            start = float(int(round(self.reel_positions[reel_index])))
            source_index = self.selected_stop_indices[reel_index]
            target_index = self.final_stop_indices[reel_index]
            delta = target_index - source_index
            if delta not in {-1, 0, 1}:
                raise RuntimeError(
                    "Post-stop nudge must move at most one adjacent physical stop"
                )

            self.nudge_start_positions[reel_index] = start
            self.nudge_target_positions[reel_index] = start + float(delta)
            self.reel_display_speeds[reel_index] = 0.0
            self.reel_states[reel_index] = (
                "nudging" if delta != 0 else "stopped"
            )

        self.result_var.set("滚轮已停定，执行快速移位...")
        self.status_var.set("命中带钻石的特殊停点：0.4 秒移动到相邻 BAR")
        self.motion_var.set("快速移位")
        self.draw_scene()
        self._nudge_frame()

    def _nudge_frame(self) -> None:
        if not self.spinning or not self.nudging:
            return

        now = time.monotonic()
        duration = max(0.001, float(self.POST_STOP_NUDGE_DURATION))
        raw_u = (now - self.nudge_started) / duration
        u = max(0.0, min(1.0, raw_u))
        eased = self._minimum_jerk(u)

        for reel_index in range(3):
            start = self.nudge_start_positions[reel_index]
            target = self.nudge_target_positions[reel_index]
            if target == start:
                self.reel_positions[reel_index] = start
                self.reel_display_speeds[reel_index] = 0.0
                self.reel_states[reel_index] = "stopped"
                continue

            old_position = self.reel_positions[reel_index]
            new_position = start + (target - start) * eased
            self.reel_positions[reel_index] = new_position
            elapsed = max(0.001, now - self.last_frame_time)
            self.reel_display_speeds[reel_index] = (
                abs(new_position - old_position) / elapsed
            )
            self.reel_states[reel_index] = "nudging"

        self.last_frame_time = now
        self.draw_scene()

        if raw_u >= 1.0:
            for reel_index in range(3):
                self.reel_positions[reel_index] = float(
                    int(round(self.nudge_target_positions[reel_index]))
                )
                self.reel_display_speeds[reel_index] = 0.0
                self.reel_states[reel_index] = "stopped"
            self.nudging = False
            self.spinning = False
            self.after_id = None
            self._settle_final_display()
            return

        self.after_id = self.root.after(16, self._nudge_frame)

    def _settle_final_display(self) -> None:
        """Validate and evaluate the center line after all motion is complete."""
        self.center_symbols = [
            self._symbol_from_position(index, 0) for index in range(3)
        ]
        actual_indices = [
            int(round(self.reel_positions[index]))
            % len(self.reel_sequences[index])
            for index in range(3)
        ]
        if actual_indices != self.final_stop_indices:
            raise RuntimeError(
                "Post-stop result ended on different physical stops: "
                f"expected={self.final_stop_indices}, actual={actual_indices}"
            )

        expected_symbols = tuple(
            self.reel_sequences[index][self.final_stop_indices[index]]
            for index in range(3)
        )
        if tuple(self.center_symbols) != expected_symbols:
            raise RuntimeError(
                "Displayed symbols differ from the final physical stops: "
                f"expected={expected_symbols}, displayed={self.center_symbols}"
            )

        # Payout evaluation happens only now, from the final displayed symbols.
        result = evaluate_payline(self.center_symbols)
        self.last_pay_result = result
        self.winning_reels = set(result.winning_reels)

        if result.is_win:
            self._settle_win(result)
        else:
            self._settle_loss()

    def _settle_win(self, result: PayResult) -> None:
        payout = self.current_bet * float(result.award_credits)
        base_payout = self.current_bet * float(result.base_credits)
        self.last_win = payout
        self.balance += payout
        self.light_mode = "win"
        self.winning_paytable_key = result.paytable_key
        self.paytable_flash_on = True
        self.diamond_rule_highlight = (
            result.diamond_count if result.diamond_count in {1, 2} else 0
        )

        if result.diamond_count == 1:
            self.last_win_expression = (
                f"${base_payout:,.0f} * 2 = ${payout:,.0f}"
            )
        elif result.diamond_count == 2:
            self.last_win_expression = (
                f"${base_payout:,.0f} * 2 * 2 = ${payout:,.0f}"
            )
        else:
            self.last_win_expression = ""

        self.result_var.set(f"中奖：{result.description}")
        if self.last_win_expression:
            self.status_var.set(self.last_win_expression)
        else:
            self.status_var.set(
                f"下注 ${self.current_bet:,.2f} × {result.award_credits:,} "
                f"= ${payout:,.2f}"
            )
        self.motion_var.set("中奖")
        update_balance_in_json(self.username, self.balance)
        self.update_display()

        cherry_key = result.paytable_key in {
            "ONE_CHERRY", "TWO_CHERRIES", "THREE_CHERRIES"
        }
        should_impact = (
            result.diamond_count in {1, 2}
            and not cherry_key
            and result.paytable_key != "THREE_DOUBLE_DIAMOND"
        )
        if should_impact:
            self._start_paytable_impact(result.diamond_count)
        else:
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
        self.result_var.set(
            f"未中奖 送您好运！"
        )
        self.status_var.set("本局结束")
        self.motion_var.set("结束")
        update_balance_in_json(self.username, self.balance)
        self._set_controls_enabled(True)
        self.update_display()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

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
                f"本局下注：${self.BASE_BET:,.0f} × {self.multiplier} "
                f"= ${self.current_bet:,.0f}"
            ),
            fill="#F1E8F8",
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.W,
        )

    # ------------------------------------------------------------------
    # Display and closing
    # ------------------------------------------------------------------

    def update_display(self) -> None:
        if not hasattr(self, "_default_multiplier_initialized"):
            self.multiplier = self.MAX_MULTIPLIER
            self._default_multiplier_initialized = True
    
        self.balance_var.set(f"${self.balance:,.2f}")
        self.bet_var.set(f"${self.current_bet:,.2f}")
        self.last_win_var.set(
            f"${self.last_win:,.2f}"
        )
        self.multiplier_var.set(
            f"{self.multiplier}×   ·   本局 ${self.current_bet:,.0f}"
        )
        self.spin_button.configure(text=f"开始抽奖 · ${self.current_bet:,.0f}")

        self._draw_paytable()
        self._draw_diamond_rule_panel()
        if not self.spinning:
            self._set_controls_enabled(True)
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

        self.spinning = False
        self.nudging = False
        update_balance_in_json(self.username, self.balance)

        finish = getattr(self.root, "finish", None)
        if callable(finish):
            finish(self.balance)
        else:
            self.root.destroy()


# Backward-friendly alias for hosts that imported NumberSlotMachine from V20.
NumberSlotMachine = DoubleDiamondSlotMachine


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
            title="Double Diamond 双倍钻石老虎机",
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        page.set_requested_size(1150, 750)
        game = DoubleDiamondSlotMachine(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = DoubleDiamondSlotMachine(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


def _print_audit() -> None:
    print(json.dumps(calculate_virtual_stop_audit(), ensure_ascii=False, indent=2))


def _run_self_tests() -> None:
    tests = {
        (DOUBLE_DIAMOND, DOUBLE_DIAMOND, DOUBLE_DIAMOND): 1000,
        (SEVEN, SEVEN, SEVEN): 80,
        (DOUBLE_DIAMOND, SEVEN, SEVEN): 160,
        (DOUBLE_DIAMOND, DOUBLE_DIAMOND, SEVEN): 320,
        (TRIPLE_BAR, TRIPLE_BAR, TRIPLE_BAR): 40,
        (DOUBLE_DIAMOND, TRIPLE_BAR, TRIPLE_BAR): 80,
        (BAR, DOUBLE_BAR, TRIPLE_BAR): 5,
        (DOUBLE_DIAMOND, BAR, DOUBLE_BAR): 10,
        (CHERRY, HIDDEN_SPACE, HIDDEN_SPACE): 2,
        (CHERRY, CHERRY, HIDDEN_SPACE): 5,
        (CHERRY, CHERRY, CHERRY): 10,
        (CHERRY, DOUBLE_DIAMOND, HIDDEN_SPACE): 4,
        (CHERRY, HIDDEN_SPACE, DOUBLE_DIAMOND): 4,
        (CHERRY, DOUBLE_DIAMOND, DOUBLE_DIAMOND): 8,
        (CHERRY, CHERRY, DOUBLE_DIAMOND): 10,
        (DOUBLE_DIAMOND, HIDDEN_SPACE, HIDDEN_SPACE): 0,
        (DOUBLE_DIAMOND, DOUBLE_DIAMOND, HIDDEN_SPACE): 0,
        (SEVEN, SEVEN, HIDDEN_SPACE): 0,
    }
    for line, expected in tests.items():
        actual = evaluate_payline(line).award_credits
        if actual != expected:
            raise AssertionError(
                f"evaluate_payline({line}) returned {actual}; expected {expected}"
            )
    expected_a_order = (
        HIDDEN_SPACE, SEVEN, HIDDEN_SPACE, BAR, HIDDEN_SPACE, CHERRY,
        HIDDEN_SPACE, DOUBLE_DIAMOND, HIDDEN_SPACE, BAR, HIDDEN_SPACE,
        TRIPLE_BAR, HIDDEN_SPACE, SEVEN, HIDDEN_SPACE, BAR, HIDDEN_SPACE,
        DOUBLE_DIAMOND, HIDDEN_SPACE, DOUBLE_BAR, HIDDEN_SPACE, BAR,
    )
    expected_b_order = (
        CHERRY, HIDDEN_SPACE, DOUBLE_BAR, HIDDEN_SPACE, TRIPLE_BAR,
        HIDDEN_SPACE, BAR, HIDDEN_SPACE, BAR, HIDDEN_SPACE,
        SEVEN, HIDDEN_SPACE, TRIPLE_BAR, HIDDEN_SPACE, DOUBLE_BAR,
        HIDDEN_SPACE, BAR, HIDDEN_SPACE, DOUBLE_DIAMOND, HIDDEN_SPACE,
        DOUBLE_BAR, HIDDEN_SPACE,
    )
    if FIXED_PHYSICAL_REELS != (expected_a_order, expected_b_order, expected_a_order):
        raise AssertionError("The configured A-B-A physical strip order is incorrect")

    expected_a_counts = (
        3, 1, 5, 3, 7, 2, 5, 1, 5, 3, 4,
        1, 2, 1, 8, 3, 5, 1, 5, 2, 3, 2,
    )
    expected_b_counts = (
        1, 8, 3, 8, 1, 1, 1, 1, 1, 8, 2,
        1, 1, 8, 2, 2, 1, 8, 2, 8, 2, 2,
    )
    if REEL_VIRTUAL_STOP_COUNTS != (
        expected_a_counts, expected_b_counts, expected_a_counts
    ):
        raise AssertionError("The configured A-B-A virtual-stop weights are incorrect")
    for reel_index, mapping in enumerate(REEL_VIRTUAL_STOP_TO_PHYSICAL):
        if len(mapping) != TOTAL_VIRTUAL_STOPS:
            raise AssertionError(f"Reel {reel_index + 1} must map exactly 72 stops")

    if INITIAL_PHYSICAL_STOPS != (4, 13, 20):
        raise AssertionError("The initial A-B-A physical stops are incorrect")
    for reel_index, stop_number in enumerate(INITIAL_PHYSICAL_STOPS):
        if stop_number not in REEL_DIAMOND_BACKED_BAR_STOPS[reel_index]:
            raise AssertionError(
                f"Initial Reel {reel_index + 1} stop must be diamond-backed"
            )

    expected_nudges = (
        {5: 4, 13: 12, 15: 16, 19: 20},
        {6: 5, 8: 9, 12: 13, 16: 15, 22: 21},
        {5: 4, 13: 12, 15: 16, 19: 20},
    )
    if REEL_POST_STOP_NUDGE_TARGETS != expected_nudges:
        raise AssertionError("The configured A-B-A nudge maps are incorrect")
    for reel_index, nudge_map in enumerate(expected_nudges):
        for source_number in range(1, 23):
            expected_number = nudge_map.get(source_number, source_number)
            actual_number = (
                resolve_post_stop_physical_index(source_number - 1, reel_index) + 1
            )
            if actual_number != expected_number:
                raise AssertionError(
                    f"Reel {reel_index + 1} stop {source_number} resolved to "
                    f"{actual_number}; expected {expected_number}"
                )

    deterministic_rng = random.Random(20260728)
    for reel_index in range(3):
        for _ in range(200):
            selection = select_reel_stop(deterministic_rng, reel_index)
            temporary_numbers = selection.temporary_numbers_by_virtual_stop
            if sorted(temporary_numbers) != list(range(1, 73)):
                raise AssertionError("Temporary numbers must be a unique 1..72 permutation")
            if temporary_numbers[selection.winning_virtual_stop - 1] != selection.secret_number:
                raise AssertionError("Secret number did not resolve to the winning virtual stop")
            expected_physical = REEL_VIRTUAL_STOP_TO_PHYSICAL[reel_index][
                selection.winning_virtual_stop - 1
            ]
            if selection.physical_stop_index != expected_physical:
                raise AssertionError("Virtual stop resolved to the wrong physical stop")
            if selection.symbol != FIXED_PHYSICAL_REELS[reel_index][expected_physical]:
                raise AssertionError("Selected symbol does not match the physical stop")

    stats = calculate_theoretical_statistics()
    rtp = float(stats["rtp"])
    hit_rate = float(stats["hit_rate"])
    if not 0.92 <= rtp <= 0.94:
        raise AssertionError(f"Theoretical RTP {rtp:.9%} is outside 92%-94%")
    if not 0.13 <= hit_rate <= 0.16:
        raise AssertionError(
            f"Theoretical hit rate {hit_rate:.9%} is outside 13%-16%"
        )
    expected_final_counts = (
        {HIDDEN_SPACE: 30, CHERRY: 2, BAR: 26, DOUBLE_BAR: 7, TRIPLE_BAR: 3, SEVEN: 2, DOUBLE_DIAMOND: 2},
        {HIDDEN_SPACE: 48, CHERRY: 1, BAR: 6, DOUBLE_BAR: 9, TRIPLE_BAR: 4, SEVEN: 2, DOUBLE_DIAMOND: 2},
        {HIDDEN_SPACE: 30, CHERRY: 2, BAR: 26, DOUBLE_BAR: 7, TRIPLE_BAR: 3, SEVEN: 2, DOUBLE_DIAMOND: 2},
    )
    if tuple(stats["final_symbol_counts"]) != expected_final_counts:
        raise AssertionError("Final A-B-A symbol counts are incorrect")

    print(
        f"{len(tests)} payline tests passed; A-B-A strips, independent 72-stop "
        f"maps, per-reel nudges, RTP {stats['rtp_percent']:.6f}%, and "
        f"hit rate {stats['hit_rate_percent']:.6f}% passed."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Print the fixed 22-stop / 72-virtual-stop configuration and exit.",
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