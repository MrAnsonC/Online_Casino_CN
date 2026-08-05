"""Cash Machine-style Number Slot Machine — fixed-prize / fixed-reel V20.

Player-facing rules:
- Every paid round uses all 3 reels.
- Base wager is $5; multiplier is 1× through 20×.
- Winning amount = displayed number × current multiplier.
- Only the center payline is evaluated. '*' and physical Blank contribute no digits.
- Legal center symbols:
    Reel 1: 1 / 2 / 5 / 10 / * / Blank
    Reel 2: 0 / 5 / * / Blank
    Reel 3: 0 / 5 / 00 / * / Blank

V20 mathematics (same fixed probability table as V18):
- Final hit rate: 45.000000%.
- Long-run RTP: 98.000000%.
- House edge: 2.000000%.
- Every legal positive displayed award has its own fixed probability.
- START first samples the final award, then randomly chooses one legal center
  composition that equals that award. A loss is likewise fixed at START.
- Zero Respins / Red Respins are presentation routes for the already-fixed result;
  they cannot change the final selected award.

V20 mechanical presentation:
- R1/R2/R3 now use immutable cyclic physical reel strips. The strips are not
  regenerated or rewritten when START is pressed.
- Every printed stop is followed by one invisible physical Blank detent.
- The outcome engine selects an existing future stop on each fixed reel that gives
  the required winning or losing center result. The animation only travels to that
  already-existing stop.
- Losing rounds may still use legal Zero-Respin routes and near-miss presentation.

The public interface intentionally does not display theoretical RTP, hit rate,
locked outcomes, or other internal math/debug information.
"""

from __future__ import annotations

import itertools
import json
import math
import os
import random
import sys
import time
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional, Sequence

try:
    from .slot_machine import EmbeddedGamePage
except ImportError:
    try:
        from Slot_Machine.slot_machine import EmbeddedGamePage
    except ImportError:
        EmbeddedGamePage = None


VERSION = "SlotMachine-CashMachine-V20"
STAR = "*"                       # visible printed symbol / non-numeric stop
HIDDEN_SPACE = "<HIDDEN_SPACE>"  # real physical detent, intentionally not drawn
ROW_OFFSETS = (-1, 0, 1)  # top, center, bottom physical detents
ROW_NAMES = {-1: "上格", 0: "中线", 1: "下格"}


def _interleave_hidden_spaces(symbols: Sequence[str]) -> tuple[str, ...]:
    """Insert one invisible physical detent after EVERY visible number/symbol.

    Example logical strip::
        1, *, 5, *, 10

    becomes the physical strip::
        1, <space>, *, <space>, 5, <space>, *, <space>, 10, <space>

    Both visible tokens and hidden spaces are real full reel stops and every stop
    seats exactly at the center payline.
    """
    strip: list[str] = []
    for symbol in symbols:
        strip.extend((str(symbol), HIDDEN_SPACE))
    return tuple(strip)


class Theme:
    APP_BG = "#C8C1B7"
    PANEL = "#E7E1D8"
    PANEL_ALT = "#DCD5CB"
    PANEL_HOVER = "#D1C9BE"
    # Default machine body: warm cream yellow.
    CANVAS_BG = "#F4E8B8"
    BORDER = "#9A9185"
    BORDER_SOFT = "#B9B0A5"

    TEXT = "#252A2E"
    TEXT_MUTED = "#596169"
    TEXT_DIM = "#777E83"

    ACCENT = "#345E73"
    ACCENT_HOVER = "#294A5A"
    ACCENT_SOFT = "#B8CAD2"
    CYAN = "#276E78"
    GREEN = "#4E7355"
    GREEN_HOVER = "#3D5C43"
    RED = "#A84D4D"
    RED_HOVER = "#873D3D"
    AMBER = "#A36B22"

    REEL_WELL = "#434A51"
    REEL_FACE = "#F1EDE5"
    REEL_TEXT = "#252A2E"
    REEL_FADE = "#8E969C"
    REEL_EDGE = "#8E877E"
    PAYLINE = "#D2B24D"
    HELD = "#5C7A61"
    WIN = "#A36B22"

    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )


def get_data_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../saving_data.json")


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


def _token_to_text(symbol: str) -> str:
    # Both the visible '*' symbol and the invisible physical space contribute
    # no digits to Win What You See. Numeric stops concatenate left-to-right.
    return "" if symbol in {STAR, HIDDEN_SPACE} else str(symbol)


def evaluate_visible_matrix(
    windows: Sequence[Sequence[str]],
    active_reels: int,
    *,
    visible_window_pays: bool = True,
) -> tuple[int, dict[int, tuple[int, str]]]:
    """Return (highest_credit_prize, winning_positions).

    ``windows`` is one 3-symbol tuple per reel in TOP/CENTER/BOTTOM order.
    The leftmost active reel must contribute a number, matching the game's
    left-to-right construction. Blanks contribute no digits.

    In video-like visible-window mode all visible rows are candidates and the
    highest concatenated prize is selected. In strict mode only the center row
    is considered.
    """
    active_reels = max(0, min(int(active_reels), len(windows)))
    if active_reels <= 0:
        return 0, {}

    row_candidates = (-1, 0, 1) if visible_window_pays else (0,)
    choices: list[list[tuple[int, str]]] = []

    for reel_index in range(active_reels):
        reel_window = windows[reel_index]
        if len(reel_window) != 3:
            raise ValueError("Each reel window must contain top/center/bottom symbols")

        options: list[tuple[int, str]] = []
        for row_offset in row_candidates:
            symbol = str(reel_window[row_offset + 1])
            options.append((row_offset, symbol))
        choices.append(options)

    best_value = 0
    best_positions: dict[int, tuple[int, str]] = {}
    best_tiebreak: tuple[int, ...] | None = None

    for combo in itertools.product(*choices):
        # Non-numeric center stops are skipped. The amount does NOT require
        # Reel 1 to contain a number: e.g. hidden | 5 | hidden = 5 credits.
        text = "".join(_token_to_text(symbol) for _row, symbol in combo)
        if not text:
            continue
        try:
            value = int(text)
        except ValueError:
            continue

        # Prefer center-row symbols when two combinations pay the same amount,
        # then prefer the combination closer to the payline overall.
        tiebreak = tuple(abs(row) for row, _symbol in combo)
        if value > best_value or (
            value == best_value
            and (best_tiebreak is None or tiebreak < best_tiebreak)
        ):
            best_value = value
            best_tiebreak = tiebreak
            best_positions = {
                reel_index: (row, symbol)
                for reel_index, (row, symbol) in enumerate(combo)
                if symbol not in {STAR, HIDDEN_SPACE}
            }

    return best_value, best_positions


def _center_award(symbols: Sequence[str]) -> int:
    text = "".join(_token_to_text(str(symbol)) for symbol in symbols)
    return int(text) if text else 0


def enumerate_legal_center_prizes(
    allowed_center_symbols: Sequence[Sequence[str]],
) -> dict[int, list[tuple[str, str, str]]]:
    """Enumerate every legal center combination, grouped by displayed award."""
    grouped: dict[int, list[tuple[str, str, str]]] = {}
    for combo in itertools.product(*allowed_center_symbols):
        normalized = tuple(map(str, combo))
        value = _center_award(normalized)
        grouped.setdefault(value, []).append(normalized)  # type: ignore[arg-type]
    return grouped


def calculate_prize_table_audit(
    prize_probabilities: dict[int, float],
    *,
    base_bet: float = 5.0,
) -> dict[str, float]:
    """Exact audit for V17's fixed FINAL-award probability table."""
    hit_rate = sum(float(probability) for probability in prize_probabilities.values())
    expected_award = sum(
        float(award) * float(probability)
        for award, probability in prize_probabilities.items()
    )
    return {
        "hit_rate": hit_rate,
        "loss_rate": 1.0 - hit_rate,
        "rounds_per_hit": (1.0 / hit_rate) if hit_rate > 0.0 else math.inf,
        "expected_award": expected_award,
        "rtp": expected_award / float(base_bet),
        "house_edge": 1.0 - expected_award / float(base_bet),
    }


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
            font=(Theme.FONT, 15, "bold"),
            anchor=tk.W,
        ).place(x=12, y=29, width=width - 24, height=28)


class NumberSlotMachine:
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
    MAX_MULTIPLIER = 20
    VISIBLE_WINDOW_PAYS = False
    MAX_TOTAL_SPINS = 3

    # V18 fixed FINAL-award probabilities.
    #
    # Exact internal audit (not shown in the player UI):
    #   Hit rate   = 45.000000%
    #   RTP        = 98.000000%
    #   House edge =  2.000000%
    #   E[award]   = 4.900000 credits per $5 base wager
    #
    # Every legal positive Win-What-You-See award remains possible.
    PRIZE_PROBABILITIES = {
        1: 0.12602417259719087,
        2: 0.10880162274367994,
        5: 0.07460468539027709,
        10: 0.0458109915720592,
        15: 0.0313444352319357,
        20: 0.022965272049721673,
        25: 0.01763975310727892,
        50: 0.006955482850319101,
        55: 0.006049261847297478,
        100: 0.002385238076785976,
        105: 0.0022020073506828558,
        150: 0.0012056948961279641,
        155: 0.001138896429100904,
        200: 0.0007240310194835967,
        205: 0.0006922706155514229,
        250: 0.0004794745374623188,
        255: 0.00046189962199169414,
        500: 0.00011823919260519184,
        505: 0.0001156933918999326,
        550: 9.575701918579607e-05,
        555: 9.383159538350403e-05,
        1000: 2.1892548042923315e-05,
        1005: 2.159489364319945e-05,
        1050: 1.9125760329295886e-05,
        1055: 1.8873074698678497e-05,
        1500: 6.4939878191824864e-06,
        2000: 2.3403347640843977e-06,
        2500: 9.387502721214283e-07,
        5000: 1.969655088970406e-08,
        5500: 9.77548900404077e-09,
        10000: 2.7576463924093827e-11,
        10500: 1.4793067005986708e-11,
    }
    LOSS_PROBABILITY = 0.55
    EXPECTED_RTP = 0.98
    EXPECTED_HIT_RATE = 0.45
    EXPECTED_ROUNDS_PER_HIT = 2.2222222222222223

    # Immutable printed reel faces. One physical Hidden Blank is inserted after
    # every printed face by _interleave_hidden_spaces(). These cyclic strips are
    # never regenerated or rewritten at START.
    FIXED_PRINTED_REELS = (
        (
            "1", STAR, "2", STAR, "5", STAR, "1", STAR,
            "10", STAR, "2", STAR, "1", STAR, "5", STAR,
            "2", STAR, "1", STAR, "10", STAR, "5", STAR,
        ),
        (
            "0", STAR, "5", STAR, "0", STAR, "0", STAR,
            "5", STAR, "0", STAR, "5", STAR, "0", STAR,
            "0", STAR, "5", STAR, "0", STAR, "5", STAR,
        ),
        (
            "0", STAR, "5", STAR, "00", STAR, "0", STAR,
            "5", STAR, "0", STAR, "00", STAR, "5", STAR,
            "0", STAR, "5", STAR, "00", STAR, "0", STAR,
        ),
    )

    ALLOWED_CENTER_SYMBOLS = (
        ("1", "2", "5", "10", STAR, HIDDEN_SPACE),
        ("0", "5", STAR, HIDDEN_SPACE),
        ("0", "5", "00", STAR, HIDDEN_SPACE),
    )

    # Red Respin is only ONE possible presentation route for the already-locked
    # result. Any numeric R1 (1 / 2 / 5 / 10) may be used as the held trigger,
    # with R2/R3 initially landing on non-prize stops. It is never mandatory.
    RED_RESPIN_PRESENTATION_CHANCE = 0.45

    # Feature routing changes only HOW the already-fixed result is revealed.
    WIN_ZERO_RESPIN_PRESENTATION_CHANCE = 0.68
    WIN_DOUBLE_ZERO_RESPIN_SHARE = 0.58
    LOSS_FEATURE_SHOWCASE_CHANCE = 0.36
    LOSS_DOUBLE_RESPIN_SHARE = 0.38
    NATURAL_LOSS_NEAR_MISS_CHANCE = 1.00

    # Fixed-reel target search / animation.
    MIN_TRAVEL_STOPS = (118, 156, 194)
    MAX_TRAVEL_STOPS = (148, 186, 224)
    SPIN_DURATIONS = ((3.15, 3.55), (3.55, 3.95), (3.95, 4.35))

    # Flowing paytable: exactly four rows are visible at once.
    PAYTABLE_VISIBLE_ROWS = 4
    PAYTABLE_ROW_HEIGHT = 48
    PAYTABLE_FRAME_MS = 35
    PAYTABLE_SCROLL_PIXELS = 0.85

    BASE_ACCEL = (46.0, 54.0, 62.0)
    TARGET_SPEED_RANGES = (
        (22.0, 25.5),
        (28.5, 32.0),
        (33.0, 36.5),
    )
    BASE_DRAG = (0.58, 0.52, 0.47)
    ALIGN_THRESHOLD = 1.45

    REEL_WIDTH = 146
    REEL_HEIGHT = 197
    REEL_GAP = 22
    REEL_TOP_Y = 72
    REEL_SPACING = 40

    def __init__(self, root, initial_balance: float, username: str):
        self.root = root
        self._configure_root()

        self.balance = float(initial_balance)
        self.username = username
        self.multiplier = 1
        self.last_win = 0.0
        self.last_award_credits = 0
        self.prize_map = enumerate_legal_center_prizes(self.ALLOWED_CENTER_SYMBOLS)

        legal_positive_values = set(self.prize_map) - {0}
        table_values = set(self.PRIZE_PROBABILITIES)
        if table_values != legal_positive_values:
            missing = sorted(legal_positive_values - table_values)
            extra = sorted(table_values - legal_positive_values)
            raise RuntimeError(
                f"V19 prize table coverage mismatch; missing={missing}, extra={extra}"
            )

        if any(
            float(probability) <= 0.0
            for probability in self.PRIZE_PROBABILITIES.values()
        ):
            raise ValueError("Every legal winning value must have positive probability")

        if abs(
            sum(self.PRIZE_PROBABILITIES.values()) + self.LOSS_PROBABILITY - 1.0
        ) > 1e-12:
            raise ValueError("V19 win + loss probabilities must sum to 1.0")

        self.math_audit = calculate_prize_table_audit(
            self.PRIZE_PROBABILITIES,
            base_bet=self.BASE_BET,
        )
        self.theoretical_rtp = self.math_audit["rtp"]
        self.theoretical_hit_rate = self.math_audit["hit_rate"]
        self.theoretical_rounds_per_hit = self.math_audit["rounds_per_hit"]

        if abs(self.theoretical_rtp - self.EXPECTED_RTP) > 1e-12:
            raise RuntimeError(
                f"RTP audit failed: got {self.theoretical_rtp:.12%}, "
                f"expected {self.EXPECTED_RTP:.12%}"
            )
        if abs(self.theoretical_hit_rate - self.EXPECTED_HIT_RATE) > 1e-12:
            raise RuntimeError(
                f"Hit-rate audit failed: got {self.theoretical_hit_rate:.12%}, "
                f"expected {self.EXPECTED_HIT_RATE:.12%}"
            )
        if abs(
            self.theoretical_rounds_per_hit - self.EXPECTED_ROUNDS_PER_HIT
        ) > 1e-10:
            raise RuntimeError(
                f"Rounds-per-hit audit failed: "
                f"{self.theoretical_rounds_per_hit:.12f}"
            )

        self.locked_round_award = 0
        self.reel_sequences = [
            list(_interleave_hidden_spaces(self.FIXED_PRINTED_REELS[index]))
            for index in range(3)
        ]
        self.pending_target_symbols: list[Optional[str]] = [None, None, None]
        self.reel_start_positions = [0.0, 0.0, 0.0]
        self.reel_target_positions = [0.0, 0.0, 0.0]
        self.reel_spin_started = [0.0, 0.0, 0.0]
        self.reel_spin_durations = [0.0, 0.0, 0.0]

        self.spinning = False
        self.after_id: Optional[str] = None
        self.last_frame_time = 0.0

        self.in_zero_respin = False
        self.round_spin_count = 0
        self.held_reels: set[int] = set()
        self.current_spin_reels: set[int] = set()
        self.last_cycle_was_respin = False
        self.round_plan: list[dict] = []
        self.round_plan_index = 0
        self.current_feature_kind = "base"

        self.reel_positions = [6.0, 8.0, 10.0]
        self.reel_velocities = [0.0, 0.0, 0.0]
        self.reel_directions = [1, 1, 1]
        self.reel_display_speeds = [0.0, 0.0, 0.0]
        self.reel_states = ["idle", "idle", "idle"]
        self.reel_accels = list(self.BASE_ACCEL)
        self.reel_target_speeds = [sum(bounds) / 2.0 for bounds in self.TARGET_SPEED_RANGES]
        self.reel_drags = list(self.BASE_DRAG)
        self.reel_align_targets: list[Optional[int]] = [None, None, None]
        self.reel_canvases: list[tk.Canvas] = []
        self.reel_canvas_places: list[tuple[int, int, int, int]] = []

        self.center_symbols = [
            str(self.reel_sequences[i][int(round(self.reel_positions[i])) % len(self.reel_sequences[i])])
            for i in range(3)
        ]
        self.winning_positions: dict[int, tuple[int, str]] = {}
        self.light_mode = "idle"

        self.balance_var = tk.StringVar()
        self.bet_var = tk.StringVar()
        self.last_win_var = tk.StringVar()
        self.multiplier_var = tk.StringVar()
        self.result_var = tk.StringVar(value="按下“开始抽奖”")
        self.status_var = tk.StringVar(value="数字从左到右组合；* 与空白不计入数值")
        self.motion_var = tk.StringVar(value="静止")
        self.feature_var = tk.StringVar(value="免费重转：待机")
        self.active_reels_var = tk.StringVar()

        self.paytable_awards = sorted(self.PRIZE_PROBABILITIES.keys(), reverse=True)
        self.paytable_first_index = 0
        self.paytable_scroll_offset = 0.0
        self.paytable_after_id: Optional[str] = None
        self.paytable_canvas: Optional[tk.Canvas] = None

        self.multiplier_quick_buttons: list[ModernButton] = []

        self.create_widgets()
        self.update_display()
        self._start_paytable_animation()

    # ------------------------------------------------------------------
    # Root / layout
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("现金机器数字老虎机")
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
        body.place(x=0, y=self.BODY_TOP, width=self.SHELL_WIDTH, height=self.BODY_HEIGHT)

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

        icon = tk.Canvas(header, width=48, height=48, bg=Theme.PANEL, bd=0, highlightthickness=0)
        icon.place(x=14, y=11)
        icon.create_oval(2, 2, 46, 46, fill=Theme.ACCENT_SOFT, outline=Theme.ACCENT, width=2)
        icon.create_text(24, 24, text="00", fill=Theme.ACCENT, font=(Theme.FONT, 14, "bold"))

        tk.Label(
            header,
            text="现金机器",
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT, 18, "bold"),
            anchor=tk.W,
        ).place(x=74, y=10, width=340, height=27)

        tk.Label(
            header,
            text="三轴机械数字抽奖 · 每注 $5 · 抽中0/00免费重抽",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT, 10, "bold"),
            anchor=tk.W,
        ).place(x=74, y=39, width=430, height=20)

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
        panel = self._card(master, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT, padding=0)
        panel.place(x=0, y=0, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT)

        top = tk.Frame(panel, width=self.CANVAS_WIDTH, height=70, bg=Theme.PANEL)
        top.place(x=0, y=0, width=self.CANVAS_WIDTH, height=70)

        tk.Label(
            top,
            textvariable=self.result_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 15, "bold"),
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
            self.reel_canvas_places.append((x, y, self.REEL_WIDTH, self.REEL_HEIGHT))

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
            sidebar, "本局下注", self.bet_var, Theme.CYAN,
            width=169, height=68,
        ).place(x=0, y=0, width=169, height=68)
        MetricTile(
            sidebar, "上局返还", self.last_win_var, Theme.GREEN,
            width=169, height=68,
        ).place(x=179, y=0, width=169, height=68)

        info = self._card(sidebar, width=348, height=372, padding=9)
        info.place(x=0, y=74, width=348, height=372)
        self._section_title(info.content, "中奖赔付表").place(
            x=0, y=0, width=150, height=18
        )

        # Static Chinese column headers; the four data rows below flow upward.
        tk.Label(
            info.content, text="抽中数字", bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9, "bold"), anchor=tk.CENTER,
        ).place(x=0, y=25, width=94, height=24)
        tk.Label(
            info.content, text="下注倍数", bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9, "bold"), anchor=tk.CENTER,
        ).place(x=102, y=25, width=86, height=24)
        tk.Label(
            info.content, text="最终赢", bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9, "bold"), anchor=tk.CENTER,
        ).place(x=196, y=25, width=126, height=24)

        self.paytable_canvas = tk.Canvas(
            info.content,
            width=322,
            height=self.PAYTABLE_VISIBLE_ROWS * self.PAYTABLE_ROW_HEIGHT,
            bg=Theme.PANEL_ALT,
            bd=0,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        self.paytable_canvas.place(
            x=0, y=53, width=322,
            height=self.PAYTABLE_VISIBLE_ROWS * self.PAYTABLE_ROW_HEIGHT,
        )

        tk.Label(
            info.content,
            text="最终赢取 = 抽中数字 × 当前下注倍数",
            bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8), anchor=tk.W,
        ).place(x=0, y=252, width=322, height=20)

        tk.Label(
            info.content,
            textvariable=self.feature_var,
            bg=Theme.ACCENT_SOFT,
            fg=Theme.ACCENT,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.W,
            padx=8,
        ).place(x=0, y=282, width=322, height=62)

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

    # ------------------------------------------------------------------
    # 流动中奖赔付表
    # ------------------------------------------------------------------

    def _draw_paytable(self) -> None:
        canvas = self.paytable_canvas
        if canvas is None:
            return
        canvas.delete("all")
        row_h = self.PAYTABLE_ROW_HEIGHT
        height = self.PAYTABLE_VISIBLE_ROWS * row_h
        offset = self.paytable_scroll_offset
        count = len(self.paytable_awards)

        # Draw one extra row above and below so scrolling remains continuous.
        for slot in range(-1, self.PAYTABLE_VISIBLE_ROWS + 2):
            index = (self.paytable_first_index + slot) % count
            award = self.paytable_awards[index]
            top = slot * row_h - offset
            bottom = top + row_h
            if bottom < 0 or top > height:
                continue

            if index % 2 == 0:
                canvas.create_rectangle(
                    0, top, 322, bottom, fill=Theme.PANEL, outline=""
                )
            canvas.create_line(
                0, bottom, 322, bottom, fill=Theme.BORDER_SOFT, width=1
            )
            canvas.create_text(
                47, top + row_h / 2, text=f"{award:,}",
                fill=Theme.TEXT, font=(Theme.FONT, 11, "bold")
            )
            canvas.create_text(
                145, top + row_h / 2, text=f"{self.multiplier}×",
                fill=Theme.ACCENT, font=(Theme.FONT, 11, "bold")
            )
            canvas.create_text(
                259, top + row_h / 2,
                text=f"${award * self.multiplier:,.0f}",
                fill=Theme.GREEN, font=(Theme.FONT, 11, "bold")
            )

    def _start_paytable_animation(self) -> None:
        if self.paytable_after_id is not None:
            return
        self._draw_paytable()
        self.paytable_after_id = self.root.after(
            self.PAYTABLE_FRAME_MS, self._animate_paytable
        )

    def _animate_paytable(self) -> None:
        self.paytable_after_id = None
        if self.paytable_canvas is None:
            return
        self.paytable_scroll_offset += self.PAYTABLE_SCROLL_PIXELS
        if self.paytable_scroll_offset >= self.PAYTABLE_ROW_HEIGHT:
            self.paytable_scroll_offset -= self.PAYTABLE_ROW_HEIGHT
            self.paytable_first_index = (
                self.paytable_first_index + 1
            ) % len(self.paytable_awards)
        self._draw_paytable()
        try:
            self.paytable_after_id = self.root.after(
                self.PAYTABLE_FRAME_MS, self._animate_paytable
            )
        except tk.TclError:
            self.paytable_after_id = None

    # ------------------------------------------------------------------
    # Betting / feature helpers
    # ------------------------------------------------------------------

    @property
    def current_bet(self) -> float:
        return self.BASE_BET * self.multiplier

    @property
    def active_reel_count(self) -> int:
        return 3

    @property
    def max_total_spins_for_round(self) -> int:
        return self.MAX_TOTAL_SPINS

    def set_multiplier(self, value: int) -> None:
        if self.spinning or self.in_zero_respin:
            return
        self.multiplier = max(1, min(self.MAX_MULTIPLIER, int(value)))
        self.winning_positions = {}
        self.update_display()
        self._draw_paytable()

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

    def _near_miss_matches_fixed_strip(
        self,
        reel_index: int,
        target_index: int,
        target_symbol: str,
        near_miss_symbol: Optional[str],
    ) -> bool:
        if not near_miss_symbol or near_miss_symbol == HIDDEN_SPACE:
            return True
        sequence = self.reel_sequences[reel_index]
        # Hidden-center stops show the adjacent printed face at ±1. Printed-center
        # stops have hidden detents at ±1, so the next visible face is ±2.
        step = 1 if target_symbol == HIDDEN_SPACE else 2
        return any(
            str(sequence[(target_index + side * step) % len(sequence)])
            == str(near_miss_symbol)
            for side in (-1, 1)
        )

    def _find_fixed_target_index(
        self,
        reel_index: int,
        target_symbol: str,
        *,
        near_miss_symbol: Optional[str] = None,
    ) -> int:
        """Choose an already-existing future stop on the immutable reel strip."""
        sequence = self.reel_sequences[reel_index]
        start_index = int(round(self.reel_positions[reel_index]))
        direction = 1 if self.reel_directions[reel_index] >= 0 else -1
        min_travel = self.MIN_TRAVEL_STOPS[reel_index]
        max_travel = self.MAX_TRAVEL_STOPS[reel_index]
        period = len(sequence)

        def collect(require_near: bool, extra_periods: int) -> list[int]:
            upper = max_travel + period * extra_periods
            found: list[int] = []
            for distance in range(min_travel, upper + 1):
                candidate = start_index + direction * distance
                if str(sequence[candidate % period]) != str(target_symbol):
                    continue
                if require_near and not self._near_miss_matches_fixed_strip(
                    reel_index, candidate, target_symbol, near_miss_symbol
                ):
                    continue
                found.append(candidate)
                if len(found) >= 8:
                    break
            return found

        candidates = collect(bool(near_miss_symbol), 8)
        if not candidates:
            candidates = collect(False, 8)
        if not candidates:
            raise RuntimeError(
                f"固定滚轮 R{reel_index + 1} 找不到目标符号 {target_symbol!r}"
            )
        return random.choice(candidates)

    def _rebase_and_prepare_target(
        self,
        reel_index: int,
        target_symbol: str,
        *,
        near_miss_symbol: Optional[str] = None,
    ) -> None:
        """Select a target on the fixed strip; never rewrite any reel face."""
        start_index = int(round(self.reel_positions[reel_index]))
        target_index = self._find_fixed_target_index(
            reel_index,
            str(target_symbol),
            near_miss_symbol=near_miss_symbol,
        )

        self.pending_target_symbols[reel_index] = str(target_symbol)
        self.reel_positions[reel_index] = float(start_index)
        self.reel_start_positions[reel_index] = float(start_index)
        self.reel_target_positions[reel_index] = float(target_index)
        self.reel_spin_started[reel_index] = time.monotonic()
        self.reel_spin_durations[reel_index] = random.uniform(
            *self.SPIN_DURATIONS[reel_index]
        )

    @staticmethod
    def _minimum_jerk(u: float) -> float:
        # 0→1 S-curve with zero velocity and acceleration at both endpoints.
        u = max(0.0, min(1.0, float(u)))
        return 10.0 * u**3 - 15.0 * u**4 + 6.0 * u**5

    # ------------------------------------------------------------------
    # Pre-planned round RNG
    # ------------------------------------------------------------------

    def _sample_prize_outcome(self) -> int:
        """Draw the FINAL award at START from V18's fixed prize table."""
        awards = [0, *self.PRIZE_PROBABILITIES.keys()]
        weights = [
            self.LOSS_PROBABILITY,
            *self.PRIZE_PROBABILITIES.values(),
        ]
        return int(random.choices(awards, weights=weights, k=1)[0])

    @staticmethod
    def _is_non_prize(symbol: str) -> bool:
        return str(symbol) in {STAR, HIDDEN_SPACE}

    @classmethod
    def _is_numeric_stop(cls, symbol: str) -> bool:
        """Return True only for a visible numeric reel stop."""
        token = str(symbol)
        return token not in {STAR, HIDDEN_SPACE} and token.isdigit()

    @classmethod
    def _is_red_respin_trigger_combo(cls, symbols: Sequence[str]) -> bool:
        """Red Respin trigger: R1 numeric while R2 and R3 are non-prize stops."""
        return (
            len(symbols) >= 3
            and cls._is_numeric_stop(str(symbols[0]))
            and cls._is_non_prize(str(symbols[1]))
            and cls._is_non_prize(str(symbols[2]))
        )

    @staticmethod
    def _random_non_prize() -> str:
        return STAR if random.random() < 0.5 else HIDDEN_SPACE

    def _make_step(
        self,
        kind: str,
        spin_reels: Sequence[int],
        targets: dict[int, str],
        held_before: Optional[dict[int, str]] = None,
        near_miss: Optional[dict[int, str]] = None,
    ) -> dict:
        return {
            "kind": str(kind),
            "spin_reels": tuple(int(i) for i in spin_reels),
            "targets": {int(i): str(s) for i, s in targets.items()},
            "held_before": {
                int(i): str(s) for i, s in (held_before or {}).items()
            },
            "near_miss": {
                int(i): str(s) for i, s in (near_miss or {}).items()
            },
        }

    def _random_combo_for_award(self, award: int) -> tuple[str, str, str]:
        """Uniformly choose one legal center composition for the locked award."""
        combos = self.prize_map.get(int(award), [])
        if not combos:
            raise RuntimeError(f"No legal center combination for award {award}")
        return random.choice(combos)

    def _build_direct_win_plan(
        self,
        final_combo: tuple[str, str, str],
    ) -> list[dict]:
        return [
            self._make_step(
                "base",
                (0, 1, 2),
                {index: symbol for index, symbol in enumerate(final_combo)},
            )
        ]

    def _build_zero_win_plan(
        self,
        final_combo: tuple[str, str, str],
    ) -> list[dict]:
        """Reveal an already-fixed winning combination through legal Zero Respins."""
        zero_indices = [
            index
            for index in (1, 2)
            if final_combo[index] in {"0", "00"}
        ]
        if not zero_indices:
            return self._build_direct_win_plan(final_combo)

        # Both R2 and R3 are zero-type final stops:
        # reveal one zero first, then the other, then R1.
        # Example: *|0|* -> *|0|00 -> 1|0|00 = 1000.
        if (
            len(zero_indices) == 2
            and random.random() < self.WIN_DOUBLE_ZERO_RESPIN_SHARE
        ):
            first, second = (
                (1, 2) if random.random() < 0.5 else (2, 1)
            )

            base = [
                self._random_non_prize(),
                self._random_non_prize(),
                self._random_non_prize(),
            ]
            base[first] = final_combo[first]

            step1 = self._make_step(
                "base",
                (0, 1, 2),
                {index: symbol for index, symbol in enumerate(base)},
            )

            held1 = {first: final_combo[first]}
            moving1 = tuple(index for index in range(3) if index != first)
            targets1 = {
                index: self._random_non_prize()
                for index in moving1
            }
            targets1[second] = final_combo[second]
            targets1[0] = self._random_non_prize()

            step2 = self._make_step(
                "zero",
                moving1,
                targets1,
                held_before=held1,
            )

            held2 = {
                first: final_combo[first],
                second: final_combo[second],
            }
            step3 = self._make_step(
                "zero",
                (0,),
                {0: final_combo[0]},
                held_before=held2,
            )
            return [step1, step2, step3]

        # One Zero Respin: hold one zero-type reel on a losing base stop and then
        # reveal every remaining part of the locked winning combination.
        hold_index = random.choice(zero_indices)
        base = [
            self._random_non_prize(),
            self._random_non_prize(),
            self._random_non_prize(),
        ]
        base[hold_index] = final_combo[hold_index]

        step1 = self._make_step(
            "base",
            (0, 1, 2),
            {index: symbol for index, symbol in enumerate(base)},
        )

        held = {hold_index: final_combo[hold_index]}
        moving = tuple(index for index in range(3) if index != hold_index)

        step2 = self._make_step(
            "zero",
            moving,
            {index: final_combo[index] for index in moving},
            held_before=held,
        )
        return [step1, step2]

    def _build_red_win_plan(
        self,
        final_combo: tuple[str, str, str],
    ) -> list[dict]:
        """Reveal an already-fixed award through the generalized Red Respin.

        The first stop must visibly satisfy the feature trigger: R1 is numeric,
        while R2 and R3 are '*' or a physical blank.  R1 is then held and only
        R2/R3 are red-respun to the already-locked final combination.  The final
        award may be larger than, or equal to, the temporary R1-only value.
        """
        if not self._is_numeric_stop(final_combo[0]):
            return self._build_direct_win_plan(final_combo)

        held_r1 = str(final_combo[0])
        base = [held_r1, self._random_non_prize(), self._random_non_prize()]
        if not self._is_red_respin_trigger_combo(base):
            raise RuntimeError(f"Invalid Red Respin trigger stop: {base}")

        step1 = self._make_step(
            "base",
            (0, 1, 2),
            {index: symbol for index, symbol in enumerate(base)},
        )
        step2 = self._make_step(
            "red",
            (1, 2),
            {1: final_combo[1], 2: final_combo[2]},
            held_before={0: held_r1},
        )
        return [step1, step2]

    def _build_winning_round_plan(
        self,
        award: int,
        final_combo: tuple[str, str, str],
        *,
        route: str = "auto",
    ) -> list[dict]:
        """Build one presentation route for an already-locked FINAL award.

        ``route`` may be ``direct``, ``zero`` or ``red``.  The route only controls
        how the result is revealed; it never changes the final award selected at
        START.
        """
        if _center_award(final_combo) != int(award):
            raise RuntimeError("Winning combo does not match locked award")

        if route == "red":
            if not self._is_numeric_stop(final_combo[0]):
                raise RuntimeError("Red Respin final combo must keep a numeric R1")
            return self._build_red_win_plan(final_combo)

        if route == "zero":
            contains_zero = any(
                final_combo[index] in {"0", "00"}
                for index in (1, 2)
            )
            if not contains_zero:
                raise RuntimeError("Zero Respin final combo must contain 0/00 on R2/R3")
            return self._build_zero_win_plan(final_combo)

        if route == "direct":
            return self._build_direct_win_plan(final_combo)

        # Backward-compatible automatic routing. Red is optional, never forced.
        if (
            self._is_numeric_stop(final_combo[0])
            and random.random() < self.RED_RESPIN_PRESENTATION_CHANCE
        ):
            return self._build_red_win_plan(final_combo)

        contains_zero = any(
            final_combo[index] in {"0", "00"}
            for index in (1, 2)
        )
        if (
            contains_zero
            and random.random() < self.WIN_ZERO_RESPIN_PRESENTATION_CHANCE
        ):
            return self._build_zero_win_plan(final_combo)

        return self._build_direct_win_plan(final_combo)

    def _choose_winning_route_and_combo(
        self,
        award: int,
    ) -> tuple[str, tuple[str, str, str]]:
        """Choose a legal reveal route, then a combo compatible with it.

        This is intentionally route-aware.  For example, a locked award of 100
        can choose Red Respin first and then select a legal numeric-R1 composition
        such as 1|0|0, 1|*|00 or 1|Blank|00.  Alternatively the same award may
        use Zero Respin or simply stop directly.
        """
        combos = list(self.prize_map.get(int(award), []))
        if not combos:
            raise RuntimeError(f"No legal center combination for award {award}")

        red_combos = [combo for combo in combos if self._is_numeric_stop(combo[0])]
        zero_combos = [
            combo
            for combo in combos
            if combo[1] in {"0", "00"} or combo[2] in {"0", "00"}
        ]

        # Red Respin is one optional route, not an automatic consequence of the
        # first-stop symbols.  If it is not selected, Zero Respin still has its
        # normal chance whenever a compatible final composition exists.
        if red_combos and random.random() < self.RED_RESPIN_PRESENTATION_CHANCE:
            return "red", random.choice(red_combos)

        if (
            zero_combos
            and random.random() < self.WIN_ZERO_RESPIN_PRESENTATION_CHANCE
        ):
            return "zero", random.choice(zero_combos)

        return "direct", random.choice(combos)

    def _build_losing_round_plan(self) -> list[dict]:
        """Build a locked zero-award round, optionally using legal Zero Respins."""
        if random.random() >= self.LOSS_FEATURE_SHOWCASE_CHANCE:
            # IMPORTANT: an immediate final loss must NOT contain 0/00, because a
            # losing center 0/00 is required to enter Zero Respin.
            zero_free_losses = [
                combo
                for combo in self.prize_map[0]
                if combo[1] not in {"0", "00"}
                and combo[2] not in {"0", "00"}
            ]
            final_combo = random.choice(zero_free_losses)
            step = self._make_step(
                "base",
                (0, 1, 2),
                {index: symbol for index, symbol in enumerate(final_combo)},
            )
            step["near_miss"] = self._near_miss_for_final_loss(step)
            return [step]

        double = random.random() < self.LOSS_DOUBLE_RESPIN_SHARE

        if double:
            first = 1 if random.random() < 0.5 else 2
            second = 2 if first == 1 else 1
            first_zero = "0" if first == 1 else random.choice(("0", "00"))
            second_zero = "0" if second == 1 else random.choice(("0", "00"))

            base = [
                self._random_non_prize(),
                self._random_non_prize(),
                self._random_non_prize(),
            ]
            base[first] = first_zero

            step1 = self._make_step(
                "base",
                (0, 1, 2),
                {index: symbol for index, symbol in enumerate(base)},
            )

            held1 = {first: first_zero}
            moving1 = tuple(index for index in range(3) if index != first)
            targets1 = {
                index: self._random_non_prize()
                for index in moving1
            }
            targets1[second] = second_zero
            targets1[0] = self._random_non_prize()

            step2 = self._make_step(
                "zero",
                moving1,
                targets1,
                held_before=held1,
            )

            held2 = {first: first_zero, second: second_zero}
            step3 = self._make_step(
                "zero",
                (0,),
                {0: self._random_non_prize()},
                held_before=held2,
            )
            step3["near_miss"] = self._near_miss_for_final_loss(step3)
            return [step1, step2, step3]

        # One-stage losing Zero Respin.
        hold_index = 1 if random.random() < 0.58 else 2
        hold_symbol = "0" if hold_index == 1 else random.choice(("0", "00"))

        base = [
            self._random_non_prize(),
            self._random_non_prize(),
            self._random_non_prize(),
        ]
        base[hold_index] = hold_symbol

        step1 = self._make_step(
            "base",
            (0, 1, 2),
            {index: symbol for index, symbol in enumerate(base)},
        )

        held = {hold_index: hold_symbol}
        moving = tuple(index for index in range(3) if index != hold_index)

        step2 = self._make_step(
            "zero",
            moving,
            {index: self._random_non_prize() for index in moving},
            held_before=held,
        )
        step2["near_miss"] = self._near_miss_for_final_loss(step2)
        return [step1, step2]

    def _near_miss_for_final_loss(self, final_step: dict) -> dict[int, str]:
        """Choose an off-payline number that would have completed a value.

        It is planted adjacent to a non-prize center stop, never on the payline.
        """
        held = final_step.get("held_before", {})
        targets = final_step.get("targets", {})
        center = [self.center_symbols[index] for index in range(3)]
        for index, symbol in held.items():
            center[int(index)] = str(symbol)
        for index, symbol in targets.items():
            center[int(index)] = str(symbol)

        candidates: list[tuple[int, str]] = []
        if self._is_non_prize(center[0]):
            candidates.extend([(0, "10"), (0, "5"), (0, "2")])
        if self._is_non_prize(center[1]):
            candidates.append((1, "5"))
        if self._is_non_prize(center[2]):
            candidates.extend([(2, "00"), (2, "5"), (2, "0")])
        if not candidates:
            return {}
        reel_index, symbol = random.choice(candidates)
        return {reel_index: symbol}

    def _plan_final_symbols(self, plan: Sequence[dict]) -> list[str]:
        result = list(self.center_symbols)
        for step in plan:
            for index, symbol in step.get("held_before", {}).items():
                result[int(index)] = str(symbol)
            for index, symbol in step.get("targets", {}).items():
                result[int(index)] = str(symbol)
        return result

    def _build_round_plan(self) -> list[dict]:
        """Draw FINAL award + combination at START, then lock the full reveal path."""
        award = self._sample_prize_outcome()
        self.locked_round_award = int(award)

        if award > 0:
            route, final_combo = self._choose_winning_route_and_combo(award)
            plan = self._build_winning_round_plan(
                award,
                final_combo,
                route=route,
            )
        else:
            plan = self._build_losing_round_plan()

        final_symbols = self._plan_final_symbols(plan)
        final_award = _center_award(final_symbols)

        if final_award != self.locked_round_award:
            raise RuntimeError(
                f"Locked award {self.locked_round_award} but plan ends at "
                f"{final_award}: {final_symbols}"
            )
        return plan

    def _start_current_plan_step(self) -> None:
        if not self.round_plan or self.round_plan_index >= len(self.round_plan):
            self._finish_losing_round("本局结束")
            return

        step = self.round_plan[self.round_plan_index]
        kind = str(step["kind"])
        self.current_feature_kind = kind
        held_before = {
            int(index): str(symbol)
            for index, symbol in step.get("held_before", {}).items()
        }
        self.held_reels = set(held_before)
        reel_indices = set(int(index) for index in step["spin_reels"])
        direction = -1 if kind in {"zero", "red"} else 1
        self._begin_spin_cycle(
            reel_indices,
            direction=direction,
            is_respin=kind in {"zero", "red"},
            feature_kind=kind,
            target_symbols=step.get("targets", {}),
            near_miss=step.get("near_miss", {}),
        )

    # ------------------------------------------------------------------
    # Physical reel model
    # ------------------------------------------------------------------

    def start_spin(self) -> None:
        if self.spinning or self.in_zero_respin:
            return

        if self.balance < self.current_bet:
            messagebox.showwarning(
                "余额不足",
                f"本局需要 ${self.current_bet:,.2f}。",
                parent=self.root,
            )
            return

        # The entire base/feature outcome sequence is fixed here, before motion.
        self.round_plan = self._build_round_plan()
        self.round_plan_index = 0

        self.balance -= self.current_bet
        self.last_win = 0.0
        self.last_award_credits = 0
        self.winning_positions = {}
        self.light_mode = "idle"
        self.held_reels.clear()
        self.in_zero_respin = False
        self.round_spin_count = 0
        update_balance_in_json(self.username, self.balance)

        self._set_controls_enabled(False)
        self._start_current_plan_step()
        self.update_display()

    def _begin_spin_cycle(
        self,
        reel_indices: set[int],
        *,
        direction: int,
        is_respin: bool,
        feature_kind: str,
        target_symbols: dict[int, str],
        near_miss: Optional[dict[int, str]] = None,
    ) -> None:
        if not reel_indices:
            self._finish_losing_round("没有可重转滚轮")
            return

        self.round_spin_count += 1
        self.last_cycle_was_respin = bool(is_respin)
        self.current_spin_reels = set(reel_indices)
        self.winning_positions = {}
        if feature_kind == "zero":
            self.light_mode = "zero_respin"
        elif feature_kind == "red":
            self.light_mode = "red_respin"
        else:
            self.light_mode = "idle"
        near_miss = near_miss or {}

        for index in range(3):
            self.reel_velocities[index] = 0.0
            self.reel_display_speeds[index] = 0.0
            self.reel_align_targets[index] = None

            if index >= self.active_reel_count:
                self.reel_states[index] = "inactive"
                self.reel_directions[index] = 1
                continue

            if index in self.held_reels:
                self.reel_states[index] = "held"
                self.reel_directions[index] = 1
                continue

            if index in reel_indices:
                self.reel_directions[index] = 1 if direction >= 0 else -1
                target = str(target_symbols[index])
                self._rebase_and_prepare_target(
                    index,
                    target,
                    near_miss_symbol=near_miss.get(index),
                )
                self.reel_states[index] = "accelerating"
                continue

            self.reel_states[index] = "stopped"
            self.reel_directions[index] = 1

        self.reel_accels = [base * random.uniform(0.96, 1.06) for base in self.BASE_ACCEL]
        self.reel_target_speeds = [
            random.uniform(low, high) for low, high in self.TARGET_SPEED_RANGES
        ]
        self.reel_drags = [base * random.uniform(0.96, 1.05) for base in self.BASE_DRAG]

        self.spinning = True
        self.last_frame_time = time.monotonic()

        if feature_kind == "zero":
            held_text = ", ".join(f"R{i + 1}" for i in sorted(self.held_reels)) or "无"
            self.in_zero_respin = True
            self.result_var.set("零点免费重转 · 免费重转")
            self.status_var.set(f"锁定 {held_text}；其余滚轮反向旋转")
            self.motion_var.set(f"重转 {self.round_spin_count}/{self.max_total_spins_for_round}")
            self.feature_var.set(f"零点免费重转 · 锁定：{held_text}")
        elif feature_kind == "red":
            held_text = ", ".join(f"R{i + 1}" for i in sorted(self.held_reels)) or "R1"
            self.in_zero_respin = True
            self.result_var.set("红色免费重转 · R1数字触发")
            self.status_var.set(f"{held_text} 保持；R2/R3 免费重转一次")
            self.motion_var.set(f"重转 {self.round_spin_count}/{self.max_total_spins_for_round}")
            self.feature_var.set(f"红色免费重转 · 锁定：{held_text}")
        else:
            self.in_zero_respin = False
            self.result_var.set("滚轮转动中...")
            self.status_var.set("祝你好运")
            self.motion_var.set("滚动中")
            self.feature_var.set("免费重转：等待触发")

        self._physics_frame()

    def _physics_frame(self) -> None:
        if not self.spinning:
            return

        now = time.monotonic()
        dt = max(0.001, min(0.045, now - self.last_frame_time))
        self.last_frame_time = now

        for index in range(3):
            state = self.reel_states[index]
            position_before = self.reel_positions[index]

            if state in {"accelerating", "cruising", "decelerating"}:
                duration = max(0.001, self.reel_spin_durations[index])
                raw_u = (now - self.reel_spin_started[index]) / duration
                u = max(0.0, min(1.0, raw_u))

                # One analytic trajectory is used from the first frame through the
                # exact final detent.  There is no late align phase and no snap.
                eased = self._minimum_jerk(u)
                start = self.reel_start_positions[index]
                target = self.reel_target_positions[index]
                self.reel_positions[index] = start + (target - start) * eased

                actual_velocity = (self.reel_positions[index] - position_before) / dt
                self.reel_velocities[index] = actual_velocity
                self.reel_display_speeds[index] = abs(actual_velocity)

                if raw_u >= 1.0:
                    # minimum-jerk(1) is exactly 1, so this is merely a state change;
                    # position is already the final integer detent on this same frame.
                    self.reel_velocities[index] = 0.0
                    self.reel_display_speeds[index] = 0.0
                    self.reel_states[index] = "stopped"
                elif u < 0.30:
                    self.reel_states[index] = "accelerating"
                elif u < 0.62:
                    self.reel_states[index] = "cruising"
                else:
                    self.reel_states[index] = "decelerating"

            elif state in {"stopped", "held", "inactive", "idle"}:
                self.reel_velocities[index] = 0.0
                self.reel_display_speeds[index] = 0.0

        self.draw_scene()

        moving = any(
            self.reel_states[index] in {"accelerating", "cruising", "decelerating"}
            for index in self.current_spin_reels
        )
        if not moving:
            self._finish_spin_cycle()
            return

        self.after_id = self.root.after(16, self._physics_frame)

    # ------------------------------------------------------------------
    # Result evaluation / Zero Respin
    # ------------------------------------------------------------------

    def _symbol_from_position(self, reel_index: int, row_offset: int = 0) -> str:
        sequence = self.reel_sequences[reel_index]
        center_index = int(round(self.reel_positions[reel_index]))
        index = (center_index + int(row_offset)) % len(sequence)
        return str(sequence[index])

    def _window_for_reel(self, reel_index: int) -> tuple[str, str, str]:
        return tuple(
            self._symbol_from_position(reel_index, row_offset)
            for row_offset in ROW_OFFSETS
        )  # type: ignore[return-value]

    def _all_windows(self) -> list[tuple[str, str, str]]:
        return [self._window_for_reel(index) for index in range(3)]

    def _finish_spin_cycle(self) -> None:
        self.spinning = False
        self.after_id = None
        self.current_spin_reels = set(self.current_spin_reels)

        windows = self._all_windows()
        self.center_symbols = [window[1] for window in windows]

        award_credits, winning_positions = evaluate_visible_matrix(
            windows,
            self.active_reel_count,
            visible_window_pays=self.VISIBLE_WINDOW_PAYS,
        )
        self.winning_positions = winning_positions
        self.motion_var.set("已停止")
        self.draw_scene()

        # The complete round sequence was fixed at START. If another planned step
        # exists, execute it regardless of whether this intermediate stop displays
        # a temporary value (Red Respin pays only the respin value).
        if self.round_plan_index + 1 < len(self.round_plan):
            next_step = self.round_plan[self.round_plan_index + 1]
            next_kind = str(next_step["kind"])
            held = next_step.get("held_before", {})
            held_text = ", ".join(
                f"R{int(index) + 1}={symbol}"
                for index, symbol in sorted(held.items())
            ) or "无"

            if next_kind == "red":
                self.light_mode = "red_respin"
                self.result_var.set("红色免费重转 · 触发")
                self.status_var.set("R1 为数字且 R2/R3 非数字；锁定 R1，R2/R3 免费重转")
                self.feature_var.set(f"红色免费重转 · 锁定：{held_text}")
            else:
                self.light_mode = "zero_respin"
                self.result_var.set("零点免费重转 · 触发")
                self.status_var.set(f"{held_text} 已锁定；其余滚轮免费重转")
                self.feature_var.set(f"零点免费重转 · 锁定：{held_text}")
            self.draw_scene()

            self.round_plan_index += 1
            self.after_id = self.root.after(650, self._start_current_plan_step)
            return

        # Final step: only now is the round settled. V19 verifies that the
        # mechanical result is exactly the award locked at START.
        self.in_zero_respin = False
        if int(award_credits) != int(self.locked_round_award):
            raise RuntimeError(
                f"Mechanical result {award_credits} != locked V19 award "
                f"{self.locked_round_award}"
            )
        if award_credits > 0:
            self._settle_win(award_credits, winning_positions)
            return

        reason = "Respin 结束" if len(self.round_plan) > 1 else "本局未中奖"
        self._finish_losing_round(reason)

    def _format_winning_tokens(
        self,
        winning_positions: dict[int, tuple[int, str]],
    ) -> str:
        display_symbols = []

        for reel_index in range(self.active_reel_count):
            picked = winning_positions.get(reel_index)

            if picked is None:
                # 没有参与奖值的轴，仍显示真实中线符号
                symbol = self.center_symbols[reel_index]
            else:
                row_offset, symbol = picked

                # 正常情况下 Win What You See 应该使用中线。
                # 如未来保留其他行逻辑，则仍显示该中奖符号。
                if row_offset != 0:
                    symbol = str(symbol)

            display_symbols.append(symbol)

        return self._format_center_result(display_symbols)
    
    def _format_center_symbol(self, symbol: str) -> str:
        """把内部转盘符号转换成玩家看到的显示符号。"""
        if symbol == HIDDEN_SPACE:
            return "~"
        if symbol == STAR:
            return "◆"
        return str(symbol)

    def _format_center_result(self, symbols) -> str:
        """把三轴中线显示成三个独立的老虎机窗口。"""
        cells = [
            f"[ {self._format_center_symbol(symbol):^2} ]"
            for symbol in symbols
        ]
        return "  ".join(cells)

    def _settle_win(
        self,
        award_credits: int,
        winning_positions: dict[int, tuple[int, str]],
    ) -> None:
        self.in_zero_respin = False
        self.light_mode = "win"
        self.last_award_credits = int(award_credits)
        total_return = float(award_credits) * self.multiplier
        self.last_win = total_return
        self.balance += total_return

        combo_text = self._format_winning_tokens(winning_positions)
        self.result_var.set(f"本局的中奖组合是： {combo_text}")
        self.status_var.set("恭喜您！中奖啦！")
        self.motion_var.set("中奖")
        if total_return != 0:
            self.feature_var.set(f"中奖组合【{award_credits:,}】 * 倍数【{self.multiplier}】= 返还【${total_return:,.0f}】")
        else:
            self.feature_var.set("免费重转：本局已结束")

        update_balance_in_json(self.username, self.balance)
        self.held_reels.clear()
        self.current_spin_reels.clear()
        self.round_plan = []
        self.round_plan_index = 0
        self._set_controls_enabled(True)
        self.update_display()

    def _finish_losing_round(self, reason: str) -> None:
        self.in_zero_respin = False
        self.light_mode = "idle"
        self.last_award_credits = 0
        self.last_win = 0.0
        self.winning_positions = {}
        centers = self._format_center_result(
            self.center_symbols[:self.active_reel_count]
        )
        self.result_var.set(f"本局的中奖组合是： {centers} · 未中奖")
        self.status_var.set(reason)
        self.motion_var.set("结束")
        self.feature_var.set("免费重转：待机")

        self.held_reels.clear()
        self.current_spin_reels.clear()
        self.round_plan = []
        self.round_plan_index = 0
        update_balance_in_json(self.username, self.balance)
        self._set_controls_enabled(True)
        self.update_display()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw_scene(self) -> None:
        c = self.game_canvas
        c.delete("all")

        w = self.CANVAS_WIDTH
        h = self.CANVAS_HEIGHT

        if self.light_mode == "zero_respin":
            # Zero / 00 free respin: light green.
            canvas_bg = "#DDEEDC"
            cabinet_fill = "#EAF5E8"
            cabinet_outline = "#79A978"
            well_outline = "#70A56F"
            reel_face = "#F2FAF0"
            lamp_fill = "#9BCB98"
            lamp_outline = "#C5E5C2"
            glow_text = Theme.GREEN
        elif self.light_mode == "red_respin":
            # Red free respin: light red / blush.
            canvas_bg = "#F3DCDC"
            cabinet_fill = "#F8E8E8"
            cabinet_outline = "#C87B7B"
            well_outline = "#C96C6C"
            reel_face = "#FFF3F3"
            lamp_fill = "#E89B9B"
            lamp_outline = "#F4C5C5"
            glow_text = Theme.RED
        elif self.light_mode == "win":
            canvas_bg = "#C7D8C7"
            cabinet_fill = "#E1EFE1"
            cabinet_outline = "#3E8F4F"
            well_outline = "#45A85A"
            reel_face = "#EEF8EE"
            lamp_fill = "#35A44A"
            lamp_outline = "#8AE19A"
            glow_text = Theme.GREEN
        else:
            # Idle / normal spin: cream yellow.
            canvas_bg = Theme.CANVAS_BG
            cabinet_fill = "#F7EDC9"
            cabinet_outline = "#BCA45F"
            well_outline = "#B49A55"
            reel_face = "#FFF9E8"
            lamp_fill = "#E5CB7B"
            lamp_outline = "#C8AD63"
            glow_text = Theme.AMBER

        c.create_rectangle(0, 0, w, h, fill=canvas_bg, outline="")

        c.create_rectangle(
            68, 28, w - 68, 360,
            fill=cabinet_fill,
            outline=cabinet_outline,
            width=3 if self.light_mode != "idle" else 2,
        )
        c.create_rectangle(
            92, 56, w - 92, 286,
            fill=Theme.REEL_WELL,
            outline=well_outline,
            width=4 if self.light_mode != "idle" else 3,
        )

        lamp_y_positions = (42, 336)
        for lamp_y in lamp_y_positions:
            for lamp_x in range(112, w - 112, 46):
                c.create_oval(
                    lamp_x - 9, lamp_y - 9, lamp_x + 9, lamp_y + 9,
                    fill=lamp_fill,
                    outline=lamp_outline,
                    width=2,
                )

        reel_w = self.REEL_WIDTH
        gap = self.REEL_GAP
        total = reel_w * 3 + gap * 2
        start_x = (w - total) / 2
        top_y = self.REEL_TOP_Y
        bottom_y = top_y + self.REEL_HEIGHT
        center_y = (top_y + bottom_y) / 2
        spacing = self.REEL_SPACING

        for reel_index, reel_canvas in enumerate(self.reel_canvases):
            x1 = start_x + reel_index * (reel_w + gap)
            x2 = x1 + reel_w
            active = reel_index < self.active_reel_count
            held = reel_index in self.held_reels

            base_edge = Theme.HELD if held else (Theme.REEL_EDGE if active else Theme.BORDER_SOFT)
            edge = base_edge
            if active and self.light_mode == "zero_respin":
                edge = "#70A56F" if not held else Theme.HELD
            elif active and self.light_mode == "red_respin":
                edge = "#B85F5F" if held else "#C96C6C"
            elif active and self.light_mode == "win":
                edge = "#45A85A"
            c.create_rectangle(
                x1, top_y, x2, bottom_y,
                fill=reel_face,
                outline=edge,
                width=5 if (held or self.light_mode != "idle") else 3,
            )
            c.create_text(
                (x1 + x2) / 2,
                bottom_y + 18,
                text=(
                    f"REEL {reel_index + 1}"
                    if active else
                    f"REEL {reel_index + 1} · OFF"
                ),
                fill=Theme.TEXT_MUTED,
                font=(Theme.FONT, 8, "bold"),
            )

            reel_canvas.delete("all")
            reel_canvas.configure(
                bg=reel_face,
                highlightbackground=edge,
            )

            if not active:
                reel_canvas.create_text(
                    self.REEL_WIDTH / 2,
                    self.REEL_HEIGHT / 2,
                    text="OFF",
                    fill=Theme.TEXT_DIM,
                    font=(Theme.FONT, 22, "bold"),
                )
                continue

            sequence = self.reel_sequences[reel_index]
            position = self.reel_positions[reel_index]
            local_center_y = self.REEL_HEIGHT / 2
            base_index = math.floor(position)
            center_index = int(round(position))

            for strip_index in range(base_index - 4, base_index + 5):
                symbol = str(sequence[strip_index % len(sequence)])
                y = local_center_y + (strip_index - position) * spacing
                distance = abs(y - local_center_y)
                logical_row = strip_index - center_index
                row_offset = logical_row if logical_row in ROW_OFFSETS else None

                if symbol == HIDDEN_SPACE:
                    # Real full-size physical detent, intentionally invisible.
                    # It can stop exactly on the center line; adjacent printed
                    # tokens then appear one full physical slot above and below.
                    continue
                elif symbol == STAR:
                    display_symbol = "*"
                    font_size = 30 if distance < 18 else (22 if distance < 78 else 16)
                    fill = Theme.REEL_TEXT if distance < 18 else ("#5B6268" if distance < 78 else Theme.REEL_FADE)
                elif distance < 18:
                    display_symbol = symbol
                    font_size = 36 if len(symbol) <= 2 else 32
                    fill = Theme.REEL_TEXT
                elif distance < 78:
                    display_symbol = symbol
                    font_size = 25 if len(symbol) <= 2 else 22
                    fill = "#5B6268"
                else:
                    display_symbol = symbol
                    font_size = 18
                    fill = Theme.REEL_FADE

                # Highlight the chosen paying visible symbol, even if it is on
                # the top/bottom row instead of the center payline.
                win = self.winning_positions.get(reel_index)
                if win is not None and row_offset is not None:
                    win_row, win_symbol = win
                    if row_offset == win_row and symbol == win_symbol:
                        reel_canvas.create_rectangle(
                            12, y - 27, self.REEL_WIDTH - 12, y + 27,
                            outline="#3AAA55" if self.light_mode == "win" else Theme.WIN,
                            width=4,
                        )
                        fill = "#2E7D32" if self.light_mode == "win" else Theme.WIN

                # Zero / 00 Respin：已经锁定在中线的 0 / 00
                # 使用黄色方框提示，不再显示 HOLD / LOCK 字样。
                if (
                    held
                    and self.light_mode == "zero_respin"
                    and row_offset == 0
                    and symbol in {"0", "00"}
                ):
                    reel_canvas.create_rectangle(
                        12,
                        y - 27,
                        self.REEL_WIDTH - 12,
                        y + 27,
                        outline="#FFD24A",
                        width=4,
                    )
                    fill = "#D89B00"

                reel_canvas.create_text(
                    self.REEL_WIDTH / 2,
                    y,
                    text=display_symbol,
                    fill=fill,
                    font=(Theme.FONT, font_size, "bold"),
                )

            # Center payline remains the Zero/00 HOLD trigger line.
            reel_canvas.create_line(
                0, local_center_y, self.REEL_WIDTH, local_center_y,
                fill=Theme.PAYLINE, width=4,
            )
            reel_canvas.create_line(
                0, local_center_y - 5, self.REEL_WIDTH, local_center_y - 5,
                fill="#E8D38B", width=1,
            )

        c.create_line(98, center_y, w - 98, center_y, fill=Theme.PAYLINE, width=4)
        c.create_line(98, center_y - 5, w - 98, center_y - 5, fill="#E8D38B", width=1)
        c.create_text(
            104,
            center_y - 14,
            text="CENTER PAYLINE / ZERO HOLD",
            fill=glow_text,
            font=(Theme.FONT, 7, "bold"),
            anchor=tk.W,
        )

        # Reel motion cards.
        card_y = 392
        card_w = 181
        card_gap = 18
        total_cards = card_w * 3 + card_gap * 2
        card_start = (w - total_cards) / 2

        state_labels = {
            "idle": "待机",
            "accelerating": "加速",
            "cruising": "匀速",
            "decelerating": "减速",
            "aligning": "对齐",
            "stopped": "停止",
            "held": "HOLD",
            "inactive": "未启用",
        }

        for index in range(3):
            x1 = card_start + index * (card_w + card_gap)
            x2 = x1 + card_w
            state = self.reel_states[index]
            state_label = state_labels.get(state, state)
            direction_text = "←" if self.reel_directions[index] < 0 else "→"
            if state in {"held", "inactive", "idle", "stopped"}:
                direction_text = "·"

            c.create_rectangle(
                x1, card_y, x2, card_y + 79,
                fill=Theme.PANEL_ALT,
                outline=Theme.BORDER_SOFT,
                width=1,
            )
            c.create_text(
                x1 + 12, card_y + 18,
                text=f"滚轮 {index + 1}",
                fill=Theme.TEXT_MUTED,
                font=(Theme.FONT_CJK, 8, "bold"),
                anchor=tk.W,
            )
            c.create_text(
                x1 + 12, card_y + 43,
                text=f"{state_label} {direction_text}",
                fill=Theme.HELD if state == "held" else Theme.ACCENT,
                font=(Theme.FONT_CJK, 11, "bold"),
                anchor=tk.W,
            )
            c.create_text(
                x2 - 12, card_y + 43,
                text=f"{self.reel_display_speeds[index]:.1f}",
                fill=Theme.TEXT,
                font=(Theme.FONT, 11, "bold"),
                anchor=tk.E,
            )
            c.create_text(
                x2 - 12, card_y + 62,
                text="格/秒",
                fill=Theme.TEXT_DIM,
                font=(Theme.FONT_CJK, 7),
                anchor=tk.E,
            )

        c.create_text(
            52, 507,
            text=(
                f"本局下注：$5 × {self.multiplier} = ${self.current_bet:,.0f}"
            ),
            fill=Theme.TEXT,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.W,
        )

    # ------------------------------------------------------------------
    # Display / closing
    # ------------------------------------------------------------------

    def update_display(self) -> None:
        # Match the Blackjack Slot Machine account/bet presentation.
        self.balance_var.set(f"${self.balance:,.2f}")
        self.bet_var.set(f"${self.current_bet:,.2f}")
        self.last_win_var.set(f"${self.last_win:,.2f}")
        self.multiplier_var.set(
            f"{self.multiplier}×   ·   本局 ${self.current_bet:,.0f}"
        )
        self.active_reels_var.set("固定 3 轴 · 严格中线判定")
        self.spin_button.configure(text=f"开始抽奖 · ${self.current_bet:,.0f}")

        if not self.spinning and not self.in_zero_respin:
            self._set_controls_enabled(True)
        self.draw_scene()

    def on_closing(self) -> None:
        if self.paytable_after_id is not None:
            try:
                self.root.after_cancel(self.paytable_after_id)
            except tk.TclError:
                pass
            self.paytable_after_id = None

        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None

        self.spinning = False
        self.in_zero_respin = False
        update_balance_in_json(self.username, self.balance)

        finish = getattr(self.root, "finish", None)
        if callable(finish):
            finish(self.balance)
        else:
            self.root.destroy()


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
            title="现金机器数字老虎机",
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        page.set_requested_size(1150, 750)
        game = NumberSlotMachine(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = NumberSlotMachine(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    final_balance = main(10000.0, "demo_player")
    print(f"Final balance: {final_balance:.2f}")