"""
Spin Poker — physical-reel 9-line Jacks or Better R9 FINAL

Key mechanics:
- 5 continuous physical card reels, each with a 300-card strip generated exactly
  when the player presses START / DEAL.
- Reel outcome is NOT preselected. Each reel accelerates to a mechanical target
  speed, coasts under drag, then seats to the nearest card index. The visible
  cards therefore come from the actual distance travelled along the 300-card strip.
- DEAL spins all five reels and leaves the middle row as the five-card 保留 hand.
- DRAW regenerates all five 300-card strips. Each unheld reel starts at its current
  discarded card, then moves forward on the new strip. Held cards are excluded from
  all newly generated unheld strips; held columns remain locked and copied to all rows.
- Active paylines are selectable only as 3 / 6 / 9 and are drawn above
  the card art while idle/保留. During physical spinning all payline overlays are
  hidden. At settlement only winning lines are shown in their representative colours.
- Credits per line are 5..50 in steps of 5, with quick multiplier buttons
  1× / 2× / 5× / 10× mapping to 5 / 10 / 25 / 50 credits.
- R9 FINAL payline rendering uses edge-facing straight polylines. Reel 1 and Reel 5
  use side-facing points whose Y coordinates are parallel with their left/right line
  badges. Reels 2..4 normally use exact card centres; when a same-row run touches an
  outer reel, that run inherits the outer Y so the repeated-row segment stays perfectly
  horizontal, matching the original Spin Poker cabinet geometry more closely.

Card assets:
    ../A_Tools/Card/Poker1/Background.png
    ../A_Tools/Card/Poker1/{suit}{rank}.png
"""

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


import json
import math
import os
import random
import sys
import time
import tkinter as tk
from collections import Counter
from tkinter import messagebox
from typing import Callable, Optional

try:
    from PIL import Image, ImageTk
except ImportError:  # Pillow is optional; Tk fallback is implemented below.
    Image = None
    ImageTk = None

try:
    from .slot_machine import EmbeddedGamePage
except ImportError:
    try:
        from Slot_Machine.slot_machine import EmbeddedGamePage
    except ImportError:
        EmbeddedGamePage = None


VERSION = "SpinPoker-Physical-R9-BJSHUTTER-V9-20260727"
BUILD_TAG = "R9-BJSHUTTER-V9"

SUITS = ["Club", "Diamond", "Heart", "Spade"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
RANK_VALUE = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
    "A": 14,
}
SUIT_GLYPH = {
    "Club": "♣",
    "Diamond": "♦",
    "Heart": "♥",
    "Spade": "♠",
}

# Card is stored as (suit, rank), matching the user's asset filename order.
Card = tuple[str, str]


class Theme:
    APP_BG = "#C8C1B7"
    PANEL = "#E7E1D8"
    PANEL_ALT = "#DCD5CB"
    PANEL_HOVER = "#D1C9BE"
    CANVAS_BG = "#BFD0C1"
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
    AMBER = "#A36B22"
    GOLD = "#D2B24D"
    GOLD_SOFT = "#E4D39C"

    CARD_FACE = "#F7F4EC"
    CARD_EDGE = "#7E776E"
    CARD_BACK = "#7D8E95"

    # Blackjack_Slot_Machine mechanical shutter material.  HOLD Top/Bottom
    # shutters use this exact palette and ribbed/brass construction.
    SHUTTER = "#4D5256"
    SHUTTER_DARK = "#353A3E"
    SHUTTER_EDGE = "#23272A"
    SHUTTER_RIB_LIGHT = "#646A6E"
    BRASS = "#B58A35"
    BRASS_LIGHT = "#D9B75A"
    BRASS_EDGE = "#6F5522"

    HEART_DIAMOND = "#A84D4D"
    CLUB_SPADE = "#252A2E"

    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )


# Spin Poker R9 payline numbering / geometry, retaining the requested R5 row order.
# Row index: 0=TOP (Line 2), 1=DEAL/MIDDLE (Line 1), 2=BOTTOM (Line 3).
# Each tuple contains the row used in columns 1..5.
PAYLINES: tuple[tuple[int, int, int, int, int], ...] = (
    (1, 1, 1, 1, 1),  # Line 1 Red:    middle horizontal
    (0, 0, 0, 0, 0),  # Line 2 Blue:   top horizontal
    (2, 2, 2, 2, 2),  # Line 3 Navy:   bottom horizontal
    (0, 1, 2, 1, 0),  # Line 4 Peach:  TOP, MID, BOTTOM, MID, TOP (V)
    (2, 1, 0, 1, 2),  # Line 5 Pink:   BOTTOM, MID, TOP, MID, BOTTOM (inverted V)
    (0, 0, 1, 2, 2),  # Line 6 Orange: TOP, TOP, MID, BOTTOM, BOTTOM
    (2, 2, 1, 0, 0),  # Line 7 Violet: BOTTOM, BOTTOM, MID, TOP, TOP
    (1, 0, 1, 2, 1),  # Line 8 Green:  MID, TOP, MID, BOTTOM, MID
    (1, 2, 1, 0, 1),  # Line 9 Yellow: MID, BOTTOM, MID, TOP, MID
)

PAYLINE_NAMES = (
    "Red middle line",
    "Blue top line",
    "Navy bottom line",
    "Peach V line",
    "Pink upside-down V line",
    "Orange stepped line",
    "Violet stepped line",
    "Green zig-zag line",
    "Yellow zig-zag line",
)


# 9/6 Jacks or Better: payout per credit, except the Royal Flush max-credit
# bonus handled in payout_credits().
JOB_BASE_PAYOUT = {
    "royal_flush": 250,
    "straight_flush": 50,
    "four_kind": 25,
    "full_house": 9,
    "flush": 6,
    "straight": 4,
    "three_kind": 3,
    "two_pair": 2,
    "jacks_or_better": 1,
    "none": 0,
}

HAND_LABELS = {
    "royal_flush": "皇家同花顺",
    "straight_flush": "同花顺",
    "four_kind": "四条",
    "full_house": "葫芦",
    "flush": "同花",
    "straight": "顺子",
    "three_kind": "三条",
    "two_pair": "两对",
    "jacks_or_better": "J或更高对子",
    "none": "未中奖",
}


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def get_data_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../A_Tools/Account/saving_data.json")


def get_card_asset_dir() -> str:
    return os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "../A_Tools/Card/Poker1")
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
# Poker rules
# ---------------------------------------------------------------------------


def make_deck() -> list[Card]:
    return [(suit, rank) for suit in SUITS for rank in RANKS]


def evaluate_hand(cards: list[Card]) -> str:
    """Classify one 5-card hand using 9/6 Jacks or Better rules."""
    if len(cards) != 5:
        return "none"

    suits = [card[0] for card in cards]
    ranks = [card[1] for card in cards]
    values = sorted(RANK_VALUE[rank] for rank in ranks)
    counts = Counter(values)
    count_values = sorted(counts.values(), reverse=True)

    is_flush = len(set(suits)) == 1
    unique = sorted(set(values))
    is_wheel = unique == [2, 3, 4, 5, 14]
    is_normal_straight = len(unique) == 5 and unique[-1] - unique[0] == 4
    is_straight = is_wheel or is_normal_straight

    if is_flush and set(values) == {10, 11, 12, 13, 14}:
        return "royal_flush"
    if is_flush and is_straight:
        return "straight_flush"
    if count_values == [4, 1]:
        return "four_kind"
    if count_values == [3, 2]:
        return "full_house"
    if is_flush:
        return "flush"
    if is_straight:
        return "straight"
    if count_values == [3, 1, 1]:
        return "three_kind"
    if count_values == [2, 2, 1]:
        return "two_pair"
    if count_values == [2, 1, 1, 1]:
        pair_value = next(value for value, count in counts.items() if count == 2)
        if pair_value >= 11 or pair_value == 14:
            return "jacks_or_better"
    return "none"


def payout_credits(hand_key: str, credits_per_line: int) -> int:
    """Return total credits won for one payline. Credits are 5..50.

    Because this cabinet only allows 5 or more credits per line, Royal Flush
    uses the conventional max-coin 800-for-1 rate for every selected credit.
    Other Jacks-or-Better hands remain linear at their normal per-credit rate.
    """
    credits = max(5, min(100, int(credits_per_line)))
    if hand_key == "royal_flush":
        return 800 * credits
    return int(JOB_BASE_PAYOUT.get(hand_key, 0) * credits)



# ---------------------------------------------------------------------------
# Reusable Tk widgets
# ---------------------------------------------------------------------------


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



# ---------------------------------------------------------------------------
# Main game
# ---------------------------------------------------------------------------


class NumberSlotMachine:
    """Compatibility name retained so existing project imports still work."""

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

    CREDIT_VALUE = 1.0
    LINE_CHOICES = (3, 6, 9)
    MIN_CREDITS_PER_LINE = 5
    MAX_CREDITS_PER_LINE = 100
    CREDIT_STEP = 5
    CREDIT_QUICK_MULTIPLIERS = (1, 5, 10, 20)

    REEL_COUNT = 5
    REEL_STRIP_LENGTH = 300

    CARD_W = 94
    CARD_H = 124
    CARD_GAP_X = 12
    CARD_GAP_Y = 10
    CARD_PITCH = CARD_H + CARD_GAP_Y
    GRID_TOP = 18

    # R7 physical model.  The five reels deliberately have visibly different
    # mechanical characteristics.  Acceleration is generated left-to-right
    # with an adjacent gap of 28..38 symbols/s^2 (inside the requested 25..40
    # separation band), while target speed rises and drag falls across reels.
    # This makes R1 settle much earlier than R5 without preselecting outcomes.
    ACCEL_START_RANGE = (42.0, 50.0)
    ACCEL_GAP_RANGE = (28.0, 38.0)
    TARGET_SPEED_RANGES = (
        (17.0, 20.0),
        (32.0, 35.0),
        (47.0, 50.0),
        (62.0, 65.0),
        (77.0, 80.0),
    )
    BASE_DRAG = (0.94, 0.79, 0.66, 0.54, 0.44)
    ALIGN_THRES保留 = 1.35
    FRAME_INTERVAL_MS = 12
    MAX_PHYSICS_STEP = 1.0 / 120.0

    # HOLD Top/Bottom reveal animation.  This deliberately uses the same
    # timing curve as Blackjack_Slot_Machine's descending shutter:
    # 16 ms frames + smoothstep t^2(3-2t), 0.85 s travel.
    # In Poker the two covers move outward from the DEAL row:
    # TOP slides upward, BOTTOM slides downward.
    HOLD_SLIDE_DURATION = 0.85
    HOLD_SLIDE_FRAME_MS = 16

    # Sequential no-repeat rule. When an earlier reel stops, its settled
    # 1-card (DEAL) or 3-card (DRAW) visible result becomes forbidden on every
    # later moving reel. V4 has two hard guarantees:
    #   1) every matching copy that is OFF SCREEN is replaced immediately;
    #   2) a matching copy that is already visible is never rewritten in front
    #      of the player. It may roll out naturally, then is replaced as soon as
    #      it is fully off screen.
    # Before every physical position advance, the next entering strip slot is
    # sanitized, so a newly appearing card can never match any stopped card.

    # Permanent representative colour for each R9 payline.
    # The colour order follows the user's requested machine legend exactly.
    LINE_COLORS = (
        "#E43131",  # 1 Red
        "#315DD8",  # 2 Blue
        "#263D8F",  # 3 Navy
        "#000000",  # 4 Black
        "#F05A9D",  # 5 Pink
        "#1B5F00",  # 6 Dark Green
        "#8A55C5",  # 7 Violet
        "#20A93A",  # 8 Green
        "#00A892",  # 9 Yellow
    )

    # Line-number diamonds are vertically staggered on both sides to match
    # the original Spin Poker cabinet shown in the reference image.
    # Top -> bottom:
    #   left  = 4, 2, 6, 9, 1, 8, 7, 3, 5
    #   right = 4, 2, 7, 8, 1, 9, 6, 3, 5
    LINE_LEFT_ORDER = (4, 2, 6, 9, 1, 8, 7, 3, 5)
    LINE_RIGHT_ORDER = (4, 2, 7, 8, 1, 9, 6, 3, 5)

    # R9 FINAL payline geometry:
    # - Reel 1 / Reel 5 use the side-facing edge of the card, not the centre X.
    # - Their Y coordinates match the left/right line-number badge, so entry and
    #   exit segments are perfectly horizontal.
    # - Reels 2..4 normally use the exact card centre.
    # - Exception: if a same-row run connects to Reel 1 or Reel 5, the interior
    #   point(s) in that run inherit the outer Y.  Thus Line 6/7 have clean
    #   horizontal first-two / last-two-card sections, while V and zig-zag lines
    #   still pass through the true centres of Reels 2..4.
    EDGE_POINT_X_INSET = 7.0

    def __init__(self, root, initial_balance: float, username: str):
        self.root = root
        self._configure_root()

        self.balance = float(initial_balance)
        self.username = username
        self.active_lines = 9
        self.credits_per_line = 5
        self.last_win = 0.0

        # idle -> deal_spinning -> 保留 -> draw_spinning -> result
        self.phase = "idle"
        self.spin_mode = ""
        self.after_id: Optional[str] = None
        self.last_frame_time = 0.0

        self.initial_hand: list[Card] = []
        self.held = [False] * self.REEL_COUNT

        # Per-column HOLD reveal progress:
        # 0.0 = TOP/BOTTOM Blackjack-texture shutters fully closed
        # 1.0 = shutters fully moved outward, held card fully revealed.
        # Each active column keeps its own Blackjack-style smoothstep animation
        # so the player can lock/unlock different columns without blocking input.
        self.hold_slide_progress = [0.0] * self.REEL_COUNT
        self.hold_slide_animations: dict[int, tuple[float, float, float]] = {}
        self.hold_slide_after_id: Optional[str] = None
        self.hold_slide_callback: Optional[Callable[[], None]] = None
        self.shutter_transitioning = False

        # First-load showcase: Line 1 (DEAL/middle) is a preset Spade Royal Flush.
        # TOP/BOTTOM start physically covered by Blackjack-texture shutters.
        self.demo_hand: list[Card] = [
            ("Spade", "10"),
            ("Spade", "J"),
            ("Spade", "Q"),
            ("Spade", "K"),
            ("Spade", "A"),
        ]
        # Cards visible on the DEAL row at the instant START is pressed.
        # The next 300-card strips begin on these exact cards so switching from
        # the stationary scene to the clipped physical reel view is continuous
        # instead of flashing/jumping to a different index-0 card.
        self.deal_start_cards: list[Card] = list(self.demo_hand)
        self.matrix: list[list[Optional[Card]]] = [[None] * self.REEL_COUNT for _ in range(3)]
        self.matrix[1] = list(self.demo_hand)
        self.line_results: list[dict] = []
        self.hold_button_rects: dict[int, tuple[float, float, float, float]] = {}

        # Five physical reels. Each reel gets exactly 300 cards at each DEAL / DRAW generation.
        self.reel_strips: list[list[Card]] = [[] for _ in range(self.REEL_COUNT)]
        self.reel_positions = [0.0] * self.REEL_COUNT
        self.reel_velocities = [0.0] * self.REEL_COUNT
        self.reel_display_speeds = [0.0] * self.REEL_COUNT
        self.reel_states = ["idle"] * self.REEL_COUNT
        self.reel_accels = [0.0] * self.REEL_COUNT
        self.reel_target_speeds = [
            sum(bounds) / 2.0 for bounds in self.TARGET_SPEED_RANGES
        ]
        self.reel_drags = list(self.BASE_DRAG)
        self.reel_align_targets: list[Optional[int]] = [None] * self.REEL_COUNT
        self.reel_spin_mask = [False] * self.REEL_COUNT

        # R7 strip integrity / deferred sequential-ban state.  Each reel owns a set
        # of cards that may no longer appear on that physical strip.  When a
        # moving reel stops, its centre card is immediately banned and replaced
        # in every later moving reel without changing strip length or indices.
        self.reel_banned_cards: list[set[Card]] = [set() for _ in range(self.REEL_COUNT)]
        # Strip slots containing a newly banned card that were actually visible
        # at the exact ban moment.  Those slots are never rewritten while any
        # part of that card remains in an exposed window; as soon as the card
        # has rolled fully out, the slot is sanitized like every other copy.
        self.reel_visible_ban_protected: list[set[int]] = [
            set() for _ in range(self.REEL_COUNT)
        ]
        self.reel_stop_processed = [False] * self.REEL_COUNT
        self.reel_stopped_cards: list[Optional[Card]] = [None] * self.REEL_COUNT
        # DRAW settles three visible cards per moving reel.  Keep the complete
        # stopped window so every exact card visible on an earlier reel can be
        # excluded from all later moving reels.  DEAL only exposes the centre
        # card, so its stopped window contains one card.
        self.reel_stopped_visible_cards: list[tuple[Card, ...]] = [
            tuple() for _ in range(self.REEL_COUNT)
        ]

        # Real clipped child canvases used only while the physical strips move.
        self.reel_canvases: list[tk.Canvas] = []
        self.reel_canvas_places: list[tuple[int, int, int, int]] = []

        self.card_images: dict[Card, object] = {}
        self.card_back_image: Optional[object] = None
        self.asset_dir = get_card_asset_dir()
        self.asset_status = ""
        self._load_card_images()

        self.balance_var = tk.StringVar()
        self.bet_var = tk.StringVar()
        self.last_win_var = tk.StringVar()
        self.lines_var = tk.StringVar()
        self.credits_var = tk.StringVar()
        self.result_var = tk.StringVar(value="皇家同花顺 · 黑桃 10-J-Q-K-A")
        self.status_var = tk.StringVar(value="TOP / BOTTOM 已由 机械挡板关闭 · 按下 开始")
        self.phase_var = tk.StringVar(value="待机")
        self.asset_var = tk.StringVar(value=self.asset_status)

        self.pay_vars: dict[str, tk.StringVar] = {
            key: tk.StringVar() for key in JOB_BASE_PAYOUT if key != "none"
        }
        self.pay_line_count_vars: dict[str, tk.StringVar] = {
            key: tk.StringVar(value="-") for key in JOB_BASE_PAYOUT if key != "none"
        }
        self.pay_total_vars: dict[str, tk.StringVar] = {
            key: tk.StringVar(value="-") for key in JOB_BASE_PAYOUT if key != "none"
        }
        self.payout_row_widgets: dict[
            str, tuple[tk.Label, tk.Label, tk.Label, tk.Label, str]
        ] = {}
        self.line_buttons: dict[int, ModernButton] = {}
        self.credit_quick_buttons: dict[int, ModernButton] = {}

        self.create_widgets()
        self.update_display()

    # ------------------------------------------------------------------
    # Root / layout
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("旋转扑克")
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
        icon.create_text(24, 18, text="A♠", fill=Theme.ACCENT, font=(Theme.FONT, 10, "bold"))
        icon.create_text(24, 31, text="9L", fill=Theme.ACCENT, font=(Theme.FONT, 8, "bold"))

        tk.Label(
            header,
            text="旋转扑克",
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT, 18, "bold"),
            anchor=tk.W,
        ).place(x=74, y=10, width=450, height=27)

        tk.Label(
            header,
            text="老虎机版视频扑克",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.W,
        ).place(x=74, y=39, width=560, height=20)

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
        ).place(x=18, y=9, width=540, height=28)

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
            textvariable=self.phase_var,
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
            cursor="hand2",
        )
        self.game_canvas.place(x=1, y=70, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT)
        self.game_canvas.bind("<Button-1>", self._on_canvas_click)

        # One true clipping viewport per physical column.  Because paylines are
        # hidden while spinning, these child Canvases can sit above the cabinet
        # without fighting the payline z-order.
        start_x, start_y = self._grid_geometry()
        viewport_h = self.CARD_H * 3 + self.CARD_GAP_Y * 2
        for col in range(self.REEL_COUNT):
            x = int(round(1 + start_x + col * (self.CARD_W + self.CARD_GAP_X)))
            y = int(round(70 + start_y))
            reel_canvas = tk.Canvas(
                panel, width=self.CARD_W, height=viewport_h,
                bg="#454C52", bd=0, highlightthickness=0,
            )
            self.reel_canvases.append(reel_canvas)
            self.reel_canvas_places.append((x, y, self.CARD_W, viewport_h))
            reel_canvas.place_forget()

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
            sidebar, "本局总下注", self.bet_var, Theme.CYAN,
            width=169, height=68,
        ).place(x=0, y=0, width=169, height=68)

        MetricTile(
            sidebar, "上局返还", self.last_win_var, Theme.GREEN,
            width=169, height=68,
        ).place(x=179, y=0, width=169, height=68)

        # R9 retains the R8 larger, left-aligned paytable. Every cell is at least 12pt.
        payout = self._card(sidebar, width=348, height=292, padding=9)
        payout.place(x=0, y=78, width=348, height=292)
        self._section_title(payout.content, "J对子或更好").place(
            x=0, y=0, width=260, height=20
        )

        table = tk.Frame(payout.content, bg=Theme.BORDER_SOFT, bd=1, relief=tk.SOLID)
        table.place(x=0, y=27, width=322, height=245)

        rows = (
            ("royal_flush", "皇家同花顺"),
            ("straight_flush", "同花顺"),
            ("four_kind", "四条"),
            ("full_house", "葫芦"),
            ("flush", "同花"),
            ("straight", "顺子"),
            ("three_kind", "三条"),
            ("two_pair", "两对"),
            ("jacks_or_better", "J或更高对子"),
        )

        headers = ("牌型", "每线", "行", "合计")
        for col, text in enumerate(headers):
            tk.Label(
                table, text=text, bg=Theme.PANEL_HOVER, fg=Theme.TEXT_MUTED,
                font=(Theme.FONT_CJK, 12, "bold"), anchor=tk.W, padx=3,
            ).grid(row=0, column=col, sticky="nsew")

        for row, (key, label) in enumerate(rows, start=1):
            bg = Theme.PANEL_ALT if (row - 1) % 2 == 0 else Theme.PANEL
            name_label = tk.Label(
                table, text=label, bg=bg, fg=Theme.TEXT,
                font=(Theme.FONT_CJK, 12, "bold"), anchor=tk.W, padx=3,
            )
            name_label.grid(row=row, column=0, sticky="nsew")
            value_label = tk.Label(
                table, textvariable=self.pay_vars[key], bg=bg, fg=Theme.AMBER,
                font=(Theme.FONT, 12, "bold"), anchor=tk.W, padx=3,
            )
            value_label.grid(row=row, column=1, sticky="nsew")
            count_label = tk.Label(
                table, textvariable=self.pay_line_count_vars[key], bg=bg, fg=Theme.CYAN,
                font=(Theme.FONT_CJK, 12, "bold"), anchor=tk.W, padx=3,
            )
            count_label.grid(row=row, column=2, sticky="nsew")
            total_label = tk.Label(
                table, textvariable=self.pay_total_vars[key], bg=bg, fg=Theme.GREEN,
                font=(Theme.FONT, 12, "bold"), anchor=tk.W, padx=3,
            )
            total_label.grid(row=row, column=3, sticky="nsew")
            self.payout_row_widgets[key] = (
                name_label, value_label, count_label, total_label, bg
            )

        table.rowconfigure(0, minsize=24)
        for row in range(1, len(rows) + 1):
            table.rowconfigure(row, weight=1, minsize=23)
        table.columnconfigure(0, weight=12, minsize=112)
        table.columnconfigure(1, weight=7, minsize=64)
        table.columnconfigure(2, weight=4, minsize=39)
        table.columnconfigure(3, weight=8, minsize=82)

        line_card = self._card(sidebar, width=348, height=68, padding=9)
        line_card.place(x=0, y=378, width=348, height=68)
        self._section_title(line_card.content, "激活赔付线").place(
            x=0, y=0, width=190, height=20
        )

        for index, line_count in enumerate(self.LINE_CHOICES):
            button = ModernButton(
                line_card.content,
                text=f"{line_count}条线",
                command=lambda value=line_count: self.set_lines(value),
                background=Theme.PANEL_ALT,
                hover_background=Theme.PANEL_HOVER,
                foreground=Theme.TEXT,
                font_size=9,
                bold=True,
            )
            button.place(x=index * 108, y=23, width=102, height=27)
            self.line_buttons[line_count] = button

        # R9 retains the original number-slot style credit control: +/- step
        # plus a dedicated quick-multiplier row.  Base is 5 credits, therefore
        # 1×/2×/5×/10× map to 5/10/25/50 credits per line.
        credit_card = self._card(sidebar, width=348, height=106, padding=9)
        credit_card.place(x=0, y=454, width=348, height=106)
        self._section_title(credit_card.content, "每线线， 5–100 CREDITS").place(
            x=0, y=0, width=170, height=20
        )

        self.credit_minus = ModernButton(
            credit_card.content,
            text="− 5",
            command=lambda: self.change_credits(-self.CREDIT_STEP),
            background=Theme.PANEL_ALT,
            hover_background=Theme.PANEL_HOVER,
            font_size=10,
            bold=True,
        )
        self.credit_minus.place(x=0, y=24, width=54, height=30)

        tk.Label(
            credit_card.content,
            textvariable=self.credits_var,
            bg=Theme.ACCENT_SOFT,
            fg=Theme.ACCENT,
            font=(Theme.FONT, 13, "bold"),
            anchor=tk.CENTER,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        ).place(x=64, y=24, width=194, height=30)

        self.credit_plus = ModernButton(
            credit_card.content,
            text="+ 5",
            command=lambda: self.change_credits(self.CREDIT_STEP),
            background=Theme.PANEL_ALT,
            hover_background=Theme.PANEL_HOVER,
            font_size=10,
            bold=True,
        )
        self.credit_plus.place(x=268, y=24, width=54, height=30)

        for index, multiplier in enumerate(self.CREDIT_QUICK_MULTIPLIERS):
            button = ModernButton(
                credit_card.content,
                text=f"{multiplier}×",
                command=lambda value=multiplier: self.set_credit_multiplier(value),
                background=Theme.PANEL_ALT,
                hover_background=Theme.PANEL_HOVER,
                foreground=Theme.TEXT,
                font_size=9,
                bold=True,
            )
            button.place(x=index * 82, y=62, width=76, height=26)
            self.credit_quick_buttons[multiplier] = button

        actions = self._card(sidebar, width=348, height=62, padding=9)
        actions.place(x=0, y=568, width=348, height=62)

        self.primary_button = ModernButton(
            actions.content,
            text="开始 / DEAL",
            command=self.primary_action,
            background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.primary_button.place(x=0, y=0, width=322, height=44)

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    def _load_card_images(self) -> None:
        target_w = self.CARD_W - 6
        target_h = self.CARD_H - 6
        loaded = 0

        if not os.path.isdir(self.asset_dir):
            self.asset_status = "牌图目录未找到：运行时将使用内置文字牌面"
            return

        back_path = os.path.join(self.asset_dir, "Background.png")
        self.card_back_image = self._load_one_image(back_path, target_w, target_h)

        for suit in SUITS:
            for rank in RANKS:
                path = os.path.join(self.asset_dir, f"{suit}{rank}.png")
                image = self._load_one_image(path, target_w, target_h)
                if image is not None:
                    self.card_images[(suit, rank)] = image
                    loaded += 1

        if loaded == 52 and self.card_back_image is not None:
            self.asset_status = "扑克牌素材：53/53 已加载"
        else:
            back_count = 1 if self.card_back_image is not None else 0
            self.asset_status = f"扑克牌素材：{loaded + back_count}/53 已加载；缺图自动使用文字牌面"

    def _load_one_image(self, path: str, target_w: int, target_h: int):
        if not os.path.isfile(path):
            return None

        if Image is not None and ImageTk is not None:
            try:
                image = Image.open(path).convert("RGBA")
                resampling = getattr(Image, "Resampling", Image).LANCZOS
                image.thumbnail((target_w, target_h), resampling)
                return ImageTk.PhotoImage(image, master=self.root)
            except (OSError, ValueError, tk.TclError):
                pass

        try:
            image = tk.PhotoImage(file=path, master=self.root)
            factor = max(
                1,
                int(math.ceil(image.width() / max(1, target_w))),
                int(math.ceil(image.height() / max(1, target_h))),
            )
            return image.subsample(factor, factor) if factor > 1 else image
        except tk.TclError:
            return None

    # ------------------------------------------------------------------
    # Betting controls
    # ------------------------------------------------------------------

    @property
    def current_bet(self) -> float:
        return self.active_lines * self.credits_per_line * self.CREDIT_VALUE

    def _betting_is_editable(self) -> bool:
        return self.phase in {"idle", "result"}

    def set_lines(self, value: int) -> None:
        if not self._betting_is_editable():
            return
        if int(value) not in self.LINE_CHOICES:
            return
        self.active_lines = int(value)
        self._clear_payout_highlights()
        self.update_display()  # redraws paylines immediately above the cards

    def set_credits(self, value: int) -> None:
        if not self._betting_is_editable():
            return
        value = max(self.MIN_CREDITS_PER_LINE, min(self.MAX_CREDITS_PER_LINE, int(value)))
        value = int(round(value / self.CREDIT_STEP) * self.CREDIT_STEP)
        if value == self.credits_per_line:
            return
        self.credits_per_line = value
        self._clear_payout_highlights()
        self.update_display()

    def change_credits(self, delta: int) -> None:
        self.set_credits(self.credits_per_line + int(delta))

    def set_credit_multiplier(self, multiplier: int) -> None:
        if int(multiplier) not in self.CREDIT_QUICK_MULTIPLIERS:
            return
        self.set_credits(self.MIN_CREDITS_PER_LINE * int(multiplier))

    def _set_bet_controls_enabled(self, enabled: bool) -> None:
        for line_count, button in self.line_buttons.items():
            button.configure(state=tk.NORMAL if enabled else tk.DISABLED)
            if enabled and line_count == self.active_lines:
                button.normal_background = Theme.ACCENT_SOFT
                button.configure(bg=Theme.ACCENT_SOFT, fg=Theme.ACCENT)
            else:
                button.normal_background = Theme.PANEL_ALT
                button.configure(bg=Theme.PANEL_ALT, fg=Theme.TEXT)

        if not enabled:
            self.credit_minus.configure(state=tk.DISABLED)
            self.credit_plus.configure(state=tk.DISABLED)
            for button in self.credit_quick_buttons.values():
                button.configure(state=tk.DISABLED)
            return

        self.credit_minus.configure(
            state=tk.NORMAL if self.credits_per_line > self.MIN_CREDITS_PER_LINE else tk.DISABLED
        )
        self.credit_plus.configure(
            state=tk.NORMAL if self.credits_per_line < self.MAX_CREDITS_PER_LINE else tk.DISABLED
        )

        for multiplier, button in self.credit_quick_buttons.items():
            target = self.MIN_CREDITS_PER_LINE * multiplier
            button.configure(state=tk.NORMAL)
            if self.credits_per_line == target:
                button.normal_background = Theme.ACCENT_SOFT
                button.configure(bg=Theme.ACCENT_SOFT, fg=Theme.ACCENT)
            else:
                button.normal_background = Theme.PANEL_ALT
                button.configure(bg=Theme.PANEL_ALT, fg=Theme.TEXT)

    # ------------------------------------------------------------------
    # Continuous reel generation / gameplay
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_has_unique_visible_triplets(strip: list[Card]) -> bool:
        """Every cyclic TOP/MIDDLE/BOTTOM window must contain three distinct cards."""
        if len(strip) < 3:
            return False
        size = len(strip)
        for index in range(size):
            window = {
                strip[(index - 1) % size],
                strip[index % size],
                strip[(index + 1) % size],
            }
            if len(window) != 3:
                return False
        return True

    @classmethod
    def _make_300_card_strip(
        cls,
        *,
        first_card: Optional[Card] = None,
        excluded_cards: Optional[set[Card]] = None,
    ) -> list[Card]:
        """Create one exact 300-card cyclic physical strip.

        R7 invariants:
        - ``first_card`` is physically index 0 when supplied.
        - excluded cards never appear anywhere on the strip.
        - every three consecutive cyclic positions are different exact cards,
          so TOP / DEAL / BOTTOM can never show the same suit+rank twice.
        """
        excluded = set(excluded_cards or set())
        if first_card is not None and first_card in excluded:
            raise ValueError("first_card cannot also be excluded")

        allowed = [card for card in make_deck() if card not in excluded]
        if len(allowed) < 3:
            raise RuntimeError("Not enough cards remain to construct a physical reel strip.")

        # Boundary rejection is cheap (52-card alphabet) and lets us preserve
        # the cyclic three-card uniqueness rule at index 299 -> 0 as well.
        for _attempt in range(200):
            strip: list[Card] = []
            if first_card is not None:
                strip.append(first_card)

            while len(strip) < cls.REEL_STRIP_LENGTH:
                blocked = set(strip[-2:])
                candidates = [card for card in allowed if card not in blocked]
                if not candidates:
                    break
                strip.append(random.choice(candidates))

            if len(strip) != cls.REEL_STRIP_LENGTH:
                continue
            if cls._strip_has_unique_visible_triplets(strip):
                return strip

        raise RuntimeError("Unable to build a 300-card strip with unique visible triplets.")

    def _generate_deal_reel_strips(
        self, first_cards: Optional[list[Card]] = None
    ) -> None:
        """Generate all 5×300 DEAL strips without a visual first-frame jump.

        ``first_cards`` are the five cards already visible on the DEAL row when
        START / START NEXT ROUND is pressed.  Each becomes strip[0] for its reel.
        This does not preselect the settled outcome; it only makes the physical
        reel begin from the exact card the player was already looking at.
        """
        self.reel_banned_cards = [set() for _ in range(self.REEL_COUNT)]
        self.reel_visible_ban_protected = [set() for _ in range(self.REEL_COUNT)]

        if first_cards is None or len(first_cards) != self.REEL_COUNT:
            first_cards = [None] * self.REEL_COUNT

        self.reel_strips = [
            self._make_300_card_strip(first_card=first_cards[col])
            for col in range(self.REEL_COUNT)
        ]
        # Index zero is the physical beginning of each newly generated strip.
        self.reel_positions = [0.0] * self.REEL_COUNT

    def _generate_draw_reel_strips(self) -> None:
        """Regenerate all 5×300 strips when DRAW / SPIN is pressed.

        For every unheld reel, strip[0] is exactly the card currently being
        discarded from the DEAL row.  All held exact cards are excluded from
        every unheld strip so they cannot reappear as new TOP/MIDDLE/BOTTOM cards.
        Held reels also receive a fresh 300-card strip for the 5×300 invariant,
        but remain mechanically locked and continue to display their held card.
        """
        held_cards = {
            self.initial_hand[index]
            for index, is_held in enumerate(self.held)
            if is_held
        }

        new_strips: list[list[Card]] = []
        banned: list[set[Card]] = []
        for col in range(self.REEL_COUNT):
            current_card = self.initial_hand[col]
            if self.held[col]:
                # This strip is not spun; retaining its own held card at index 0
                # makes the regenerated strip state explicit and inspectable.
                exclusions = set(held_cards) - {current_card}
                first_card = current_card
            else:
                exclusions = set(held_cards)
                first_card = current_card

            new_strips.append(
                self._make_300_card_strip(
                    first_card=first_card,
                    excluded_cards=exclusions,
                )
            )
            banned.append(exclusions)

        self.reel_strips = new_strips
        self.reel_banned_cards = banned
        self.reel_visible_ban_protected = [set() for _ in range(self.REEL_COUNT)]
        self.reel_positions = [0.0] * self.REEL_COUNT

    def _safe_replacement_for_strip(self, reel_index: int, position: int) -> Card:
        """Choose a replacement that preserves the cyclic 3-visible-card rule."""
        strip = self.reel_strips[reel_index]
        size = len(strip)
        banned = self.reel_banned_cards[reel_index]
        neighbour_cards = {
            strip[(position + delta) % size]
            for delta in (-2, -1, 1, 2)
        }
        candidates = [
            card for card in make_deck()
            if card not in banned and card not in neighbour_cards
        ]
        if not candidates:
            raise RuntimeError("No legal card available while removing a stopped card.")
        return random.choice(candidates)

    def _exposed_reel_windows(self) -> tuple[tuple[float, float], ...]:
        """Return the vertical intervals in which the moving strip is visible.

        DEAL covers TOP and BOTTOM with card backs, so only the middle physical
        window counts as player-visible.  DRAW exposes all three windows.
        """
        if self.spin_mode == "deal":
            top = float(self.CARD_PITCH)
            return ((top, top + float(self.CARD_H)),)

        return tuple(
            (
                float(row * self.CARD_PITCH),
                float(row * self.CARD_PITCH + self.CARD_H),
            )
            for row in range(3)
        )

    def _visible_strip_slots_at_position(
        self, reel_index: int, position: float
    ) -> set[int]:
        """Return exact strip slots with any pixels visible at ``position``.

        DRAW normally exposes four physical cards while the reel is between
        integer positions (three windows plus the entering/leaving partial
        card). DEAL only exposes the middle window because TOP/BOTTOM are
        covered by card backs, so only cards actually visible through that
        middle window are protected from mutation.
        """
        strip = self.reel_strips[reel_index]
        if not strip:
            return set()

        size = len(strip)
        base_index = math.floor(position)
        local_middle_center = self.CARD_H / 2 + self.CARD_PITCH
        windows = self._exposed_reel_windows()
        visible: set[int] = set()

        # +/-4 is wider than the real three-window viewport and therefore also
        # covers the partial fourth card at fractional strip positions.
        for absolute_index in range(base_index - 4, base_index + 5):
            y_center = (
                local_middle_center
                + (absolute_index - position) * self.CARD_PITCH
            )
            y1 = y_center - self.CARD_H / 2
            y2 = y_center + self.CARD_H / 2

            if any(
                y2 > window_top and y1 < window_bottom
                for window_top, window_bottom in windows
            ):
                visible.add(absolute_index % size)

        return visible

    def _currently_visible_strip_slots(self, reel_index: int) -> set[int]:
        """Return the player's currently visible physical strip slots."""
        return self._visible_strip_slots_at_position(
            reel_index, self.reel_positions[reel_index]
        )

    def _replace_banned_slot_if_hidden(
        self, reel_index: int, slot: int, visible_slots: set[int]
    ) -> bool:
        """Replace one banned slot only when it is not currently visible."""
        strip = self.reel_strips[reel_index]
        banned = self.reel_banned_cards[reel_index]
        slot %= len(strip)
        if slot in visible_slots or strip[slot] not in banned:
            return False
        strip[slot] = self._safe_replacement_for_strip(reel_index, slot)
        return True

    def _sweep_hidden_banned_cards(
        self, reel_index: int, visible_slots: Optional[set[int]] = None
    ) -> None:
        """Immediately remove every forbidden card that the player cannot see.

        This is intentionally a whole-strip sweep. A newly stopped card must
        disappear from every hidden location on every later moving reel at once,
        rather than waiting until that location approaches the viewport.
        """
        if not self.reel_spin_mask[reel_index]:
            return
        strip = self.reel_strips[reel_index]
        banned = self.reel_banned_cards[reel_index]
        if not strip or not banned:
            return

        if visible_slots is None:
            visible_slots = self._currently_visible_strip_slots(reel_index)

        for slot in range(len(strip)):
            self._replace_banned_slot_if_hidden(
                reel_index, slot, visible_slots
            )

        if len(strip) != self.REEL_STRIP_LENGTH:
            raise RuntimeError(
                "Physical strip length changed during no-repeat cleanup."
            )
        if not self._strip_has_unique_visible_triplets(strip):
            raise RuntimeError(
                "No-repeat cleanup broke visible-triplet uniqueness."
            )

    def _ban_cards_from_reel(self, reel_index: int, cards: set[Card]) -> None:
        """Apply stopped-card bans without ever changing an on-screen card.

        At the exact stop moment, matching cards already visible on this later
        reel are remembered as protected physical slots. Every matching hidden
        copy is removed immediately from the full 300-card strip.
        """
        if not cards or not self.reel_spin_mask[reel_index]:
            return

        strip = self.reel_strips[reel_index]
        if not strip:
            return

        self.reel_banned_cards[reel_index].update(cards)
        banned = self.reel_banned_cards[reel_index]
        visible_now = self._currently_visible_strip_slots(reel_index)
        protected = self.reel_visible_ban_protected[reel_index]

        # Preserve only banned cards that are genuinely already on screen.
        # Existing protected slots stay protected while still visible.
        protected.intersection_update(visible_now)
        protected.update(
            slot for slot in visible_now if strip[slot] in banned
        )

        # Everything not on screen disappears from the strip immediately.
        self._sweep_hidden_banned_cards(reel_index, visible_now)

    def _ban_card_from_reel(self, reel_index: int, card: Card) -> None:
        """Compatibility wrapper for callers that ban one exact card."""
        self._ban_cards_from_reel(reel_index, {card})

    def _sanitize_incoming_banned_cards(
        self, reel_index: int, next_position: float
    ) -> None:
        """Sanitize cards BEFORE they become newly visible.

        This is the entry gate that removes the remaining cheating-looking
        failure mode: a forbidden card is never allowed to appear for one frame
        and then jump to another identity. If a slot is not visible now but will
        be visible at ``next_position``, it is checked and replaced before the
        reel position changes.
        """
        banned = self.reel_banned_cards[reel_index]
        if not banned or not self.reel_spin_mask[reel_index]:
            return

        strip = self.reel_strips[reel_index]
        current_visible = self._currently_visible_strip_slots(reel_index)
        next_visible = self._visible_strip_slots_at_position(
            reel_index, next_position
        )
        incoming = next_visible - current_visible

        changed = False
        for slot in incoming:
            if strip[slot] in banned:
                strip[slot] = self._safe_replacement_for_strip(
                    reel_index, slot
                )
                changed = True

        if changed and not self._strip_has_unique_visible_triplets(strip):
            raise RuntimeError(
                "Incoming-card sanitation broke visible-triplet uniqueness."
            )

    def _release_expired_visible_bans(self, reel_index: int) -> None:
        """Replace protected banned cards immediately after they leave view."""
        banned = self.reel_banned_cards[reel_index]
        if not banned:
            return

        strip = self.reel_strips[reel_index]
        visible_now = self._currently_visible_strip_slots(reel_index)
        protected = self.reel_visible_ban_protected[reel_index]

        expired = [slot for slot in protected if slot not in visible_now]
        changed = False
        for slot in expired:
            protected.discard(slot)
            if strip[slot] in banned:
                strip[slot] = self._safe_replacement_for_strip(
                    reel_index, slot
                )
                changed = True

        if changed and not self._strip_has_unique_visible_triplets(strip):
            raise RuntimeError(
                "Protected-card release broke visible-triplet uniqueness."
            )

    def _set_reel_position_guarded(
        self, reel_index: int, next_position: float
    ) -> None:
        """Advance a reel only after guaranteeing legal newly entering cards."""
        self._sanitize_incoming_banned_cards(reel_index, next_position)
        self.reel_positions[reel_index] = next_position
        self._release_expired_visible_bans(reel_index)

    def _sanitize_banned_cards_ahead(self, reel_index: int) -> None:
        """Defensive frame-end invariant check and hidden-card cleanup.

        Normal sanitation happens at the stop event and before each position
        advance. This final pass is deliberately conservative: it never touches
        any currently visible slot.
        """
        if not self.reel_spin_mask[reel_index]:
            return
        banned = self.reel_banned_cards[reel_index]
        if not banned:
            return

        self._release_expired_visible_bans(reel_index)
        visible_now = self._currently_visible_strip_slots(reel_index)
        protected = self.reel_visible_ban_protected[reel_index]
        strip = self.reel_strips[reel_index]

        # Any banned card that is currently visible must be one of the original
        # protected cards. Never rewrite it now; let it roll out naturally.
        # Hidden copies were removed at ban time, while the pre-entry gate checks
        # every newly entering slot before it can be rendered. Avoiding another
        # full 300-card sweep every frame keeps high-speed reels smooth.
        for slot in visible_now:
            if strip[slot] in banned:
                protected.add(slot)

    def _alignment_target_is_allowed(self, reel_index: int, target: int) -> bool:
        """Never settle onto any card already fixed on an earlier reel."""
        banned = self.reel_banned_cards[reel_index]
        offsets = (-1, 0, 1) if self.spin_mode == "draw" else (0,)
        return all(
            self._strip_card(reel_index, target + offset) not in banned
            for offset in offsets
        )


    def _on_reel_stopped(self, reel_index: int) -> None:
        """Propagate the cumulative stopped-card set to every later reel.

        DEAL contributes one exact card per stopped reel. DRAW contributes the
        settled TOP/MIDDLE/BOTTOM cards. R2 therefore bans the union of R1+R2
        from R3-R5, R3 bans R1+R2+R3 from R4-R5, and so on.
        """
        if self.reel_stop_processed[reel_index]:
            return
        self.reel_stop_processed[reel_index] = True

        center_index = int(round(self.reel_positions[reel_index]))
        stopped_card = self._strip_card(reel_index, center_index)
        self.reel_stopped_cards[reel_index] = stopped_card

        if self.spin_mode == "draw":
            visible_cards = tuple(
                self._strip_card(reel_index, center_index + offset)
                for offset in (-1, 0, 1)
            )
        else:
            visible_cards = (stopped_card,)

        self.reel_stopped_visible_cards[reel_index] = visible_cards

        cumulative_banned: set[Card] = set()
        for earlier in range(reel_index + 1):
            if self.reel_stop_processed[earlier]:
                cumulative_banned.update(
                    self.reel_stopped_visible_cards[earlier]
                )

        # Re-apply the COMPLETE cumulative set to every later moving reel.
        # This makes the intended R1 -> R2 -> ... rule explicit and also repairs
        # any stale hidden occurrence defensively.
        for later in range(reel_index + 1, self.REEL_COUNT):
            if self.reel_spin_mask[later]:
                self._ban_cards_from_reel(later, cumulative_banned)


    def primary_action(self) -> None:
        if self.phase in {"idle", "result"}:
            self.start_deal()
        elif self.phase == "保留":
            self.start_draw()

    def start_deal(self) -> None:
        if self.phase not in {"idle", "result"} or self.shutter_transitioning:
            return

        if self.balance < self.current_bet:
            messagebox.showwarning(
                "余额不足",
                f"本局需要 ${self.current_bet:,.2f}。",
                parent=self.root,
            )
            return

        # V9 keeps the first physical DEAL frame continuous with the stationary
        # DEAL row. Capture the five visible cards BEFORE any state is cleared.
        starting_from_result = self.phase == "result"
        if starting_from_result:
            self.deal_start_cards = [
                self.matrix[1][col]
                if self.matrix[1][col] is not None
                else (self.initial_hand[col] if len(self.initial_hand) == self.REEL_COUNT else self.demo_hand[col])
                for col in range(self.REEL_COUNT)
            ]
        else:
            self.deal_start_cards = list(self.demo_hand)

        self.balance -= self.current_bet
        self.last_win = 0.0
        update_balance_in_json(self.username, self.balance)

        self._cancel_hold_slide_animation()
        self.held = [False] * self.REEL_COUNT
        self.line_results = []
        self._clear_payout_highlights()

        self.shutter_transitioning = True
        self.primary_button.configure(state=tk.DISABLED)
        self._set_bet_controls_enabled(False)

        if starting_from_result:
            # Progress 1 -> 0 makes the TOP shutter descend into its window and
            # the BOTTOM shutter rise into its window.  Because the shutter is
            # clipped per card cell, neither panel can enter the middle DEAL row.
            self.result_var.set("下一局 · 机械挡板关闭中…")
            self.status_var.set("TOP ↓ / BOTTOM ↑ · Blackjack 同款缓动")
            self.phase_var.set("挡板关闭")
            self._animate_shutters_to(
                columns=tuple(range(self.REEL_COUNT)),
                target=0.0,
                callback=self._begin_deal_with_shutters_closed,
            )
            return

        # First START: the initial scene is already fully covered.  Keep it
        # closed, commit one frame, then begin the physical DEAL behind it.
        self.hold_slide_progress = [0.0] * self.REEL_COUNT
        self.hold_slide_animations.clear()
        self.hold_slide_callback = None
        self.result_var.set("机械挡板已关闭 · 准备发牌")
        self.status_var.set("TOP / BOTTOM 已由 挡板完全遮住")
        self.phase_var.set("挡板关闭")
        self.draw_scene()

        self.after_id = self.root.after(1, self._begin_deal_with_shutters_closed)

    def _begin_deal_with_shutters_closed(self) -> None:
        self.after_id = None
        # Always finish exactly at the mechanically closed endpoint before the
        # first reel frame, avoiding any sub-pixel gap after the easing curve.
        self.hold_slide_progress = [0.0] * self.REEL_COUNT
        self.hold_slide_animations.clear()
        self.hold_slide_callback = None
        self.shutter_transitioning = False

        # All five continuous 300-card reels are finalized immediately before
        # the first physics frame.  No Background/card-back blocker is used.
        self._generate_deal_reel_strips(first_cards=self.deal_start_cards)
        self.initial_hand = []
        self.matrix = [[None] * self.REEL_COUNT for _ in range(3)]
        self.line_results = []

        self.result_var.set("首轮转动进行中...")
        self.status_var.set("DEAL：TOP / BOTTOM 保持关闭，仅中间 DEAL 行可见")
        self.phase_var.set("DEAL SPIN")
        self._start_physical_spin(mode="deal", spin_mask=[True] * self.REEL_COUNT)

    def _cancel_hold_slide_animation(self) -> None:
        if self.hold_slide_after_id is not None:
            try:
                self.root.after_cancel(self.hold_slide_after_id)
            except tk.TclError:
                pass
            self.hold_slide_after_id = None
        self.hold_slide_animations.clear()
        self.hold_slide_callback = None

    def _start_hold_slide_animation(self, column: int, target: float) -> None:
        """Animate one HOLD column with Blackjack's shutter easing curve."""
        now = time.monotonic()
        start = max(0.0, min(1.0, float(self.hold_slide_progress[column])))
        end = max(0.0, min(1.0, float(target)))

        if abs(start - end) <= 1e-6:
            self.hold_slide_progress[column] = end
            self.hold_slide_animations.pop(column, None)
            self.draw_scene()
            return

        # Store (start_time, start_progress, end_progress).  Multiple columns can
        # animate at once while sharing one 16 ms Tk timer.
        self.hold_slide_animations[column] = (now, start, end)
        if self.hold_slide_after_id is None:
            self._hold_slide_animation_frame()
        else:
            self.draw_scene()

    def _animate_shutters_to(
        self,
        *,
        columns: tuple[int, ...],
        target: float,
        callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """Move selected TOP/BOTTOM shutter pairs with Blackjack easing."""
        valid = tuple(col for col in columns if 0 <= col < self.REEL_COUNT)
        self.hold_slide_callback = callback
        if not valid:
            cb = self.hold_slide_callback
            self.hold_slide_callback = None
            if cb is not None:
                cb()
            return

        pending = False
        now = time.monotonic()
        end = max(0.0, min(1.0, float(target)))
        for col in valid:
            start = max(0.0, min(1.0, float(self.hold_slide_progress[col])))
            if abs(start - end) <= 1e-6:
                self.hold_slide_progress[col] = end
                continue
            self.hold_slide_animations[col] = (now, start, end)
            pending = True

        if pending:
            if self.hold_slide_after_id is None:
                self._hold_slide_animation_frame()
            else:
                self.draw_scene()
        else:
            self.draw_scene()
            cb = self.hold_slide_callback
            self.hold_slide_callback = None
            if cb is not None:
                cb()

    def _hold_slide_animation_frame(self) -> None:
        if not self.hold_slide_animations:
            self.hold_slide_after_id = None
            return

        now = time.monotonic()
        finished: list[int] = []

        for column, (start_time, start, end) in list(self.hold_slide_animations.items()):
            elapsed = now - start_time
            t = min(1.0, elapsed / max(0.05, float(self.HOLD_SLIDE_DURATION)))
            # Exact curve copied from Blackjack_Slot_Machine:
            # eased = t * t * (3.0 - 2.0 * t)
            eased = t * t * (3.0 - 2.0 * t)
            self.hold_slide_progress[column] = start + (end - start) * eased
            if t >= 1.0:
                self.hold_slide_progress[column] = end
                finished.append(column)

        for column in finished:
            self.hold_slide_animations.pop(column, None)

        self.draw_scene()

        if self.hold_slide_animations:
            self.hold_slide_after_id = self.root.after(
                self.HOLD_SLIDE_FRAME_MS,
                self._hold_slide_animation_frame,
            )
        else:
            self.hold_slide_after_id = None
            callback = self.hold_slide_callback
            self.hold_slide_callback = None
            if callback is not None:
                callback()

    def _finish_hold_slide_animations(self) -> None:
        """Snap any in-flight HOLD covers to their current held/unheld state."""
        self._cancel_hold_slide_animation()
        self.hold_slide_progress = [
            1.0 if held else 0.0
            for held in self.held
        ]

    def toggle_保留(self, column: int) -> None:
        if (
            self.phase != "保留"
            or self.shutter_transitioning
            or not 0 <= column < self.REEL_COUNT
        ):
            return

        self.held[column] = not self.held[column]
        target = 1.0 if self.held[column] else 0.0
        self._start_hold_slide_animation(column, target)

        held_count = sum(self.held)
        direction = "TOP ↑ / BOTTOM ↓" if self.held[column] else "TOP ↓ / BOTTOM ↑"
        self.status_var.set(f"已保留 {held_count} 张 · 第 {column + 1} 列 {direction}")

    def start_draw(self) -> None:
        if self.phase != "保留" or self.shutter_transitioning:
            return

        # Before DRAW, every still-closed (unheld) TOP/BOTTOM pair opens with
        # the exact Blackjack shutter motion.  Held columns are already open.
        self.line_results = []
        self.shutter_transitioning = True
        self.result_var.set("未保留列挡板开启中…")
        self.status_var.set("TOP ↑ / BOTTOM ↓ · 开启后开始 DRAW")
        self.phase_var.set("挡板开启")
        self.primary_button.configure(state=tk.DISABLED)
        self._set_bet_controls_enabled(False)

        columns_to_open = tuple(
            col for col in range(self.REEL_COUNT)
            if self.hold_slide_progress[col] < 0.999
        )
        self._animate_shutters_to(
            columns=columns_to_open,
            target=1.0,
            callback=self._begin_draw_after_shutters,
        )

    def _begin_draw_after_shutters(self) -> None:
        self.shutter_transitioning = False

        # DRAW regenerates a completely new 5×300 physical-strip set.
        self._generate_draw_reel_strips()
        spin_mask = [not held for held in self.held]
        if not any(spin_mask):
            for col, card in enumerate(self.initial_hand):
                for row in range(3):
                    self.matrix[row][col] = card
            self.hold_slide_progress = [1.0] * self.REEL_COUNT
            self._finish_draw_result()
            return

        self.result_var.set("第二轮转动进行中...")
        self.status_var.set("DRAW：未保留列滚动；保留列机械锁定")
        self.phase_var.set("DRAW SPIN")
        self._start_physical_spin(mode="draw", spin_mask=spin_mask)

    def _start_physical_spin(self, *, mode: str, spin_mask: list[bool]) -> None:
        self.spin_mode = mode
        self.phase = "deal_spinning" if mode == "deal" else "draw_spinning"
        self.reel_spin_mask = list(spin_mask)
        self.reel_velocities = [0.0] * self.REEL_COUNT
        self.reel_display_speeds = [0.0] * self.REEL_COUNT
        self.reel_align_targets = [None] * self.REEL_COUNT
        self.reel_stop_processed = [not flag for flag in self.reel_spin_mask]
        self.reel_stopped_cards = [None] * self.REEL_COUNT
        self.reel_stopped_visible_cards = [tuple() for _ in range(self.REEL_COUNT)]
        self.reel_visible_ban_protected = [set() for _ in range(self.REEL_COUNT)]

        first_accel = random.uniform(*self.ACCEL_START_RANGE)
        self.reel_accels = [first_accel]
        for _ in range(1, self.REEL_COUNT):
            self.reel_accels.append(
                self.reel_accels[-1] + random.uniform(*self.ACCEL_GAP_RANGE)
            )
        self.reel_target_speeds = [
            random.uniform(low, high) for low, high in self.TARGET_SPEED_RANGES
        ]
        self.reel_drags = [
            base * random.uniform(0.96, 1.05) for base in self.BASE_DRAG
        ]

        self.reel_states = [
            "accelerating" if self.reel_spin_mask[i] else "locked"
            for i in range(self.REEL_COUNT)
        ]

        self.primary_button.configure(state=tk.DISABLED)
        self._set_bet_controls_enabled(False)
        # Refresh paytable and map the physical reel canvases at exact position 0.
        # Do NOT start the physics timer in this same event callback.  Tk may not
        # paint newly placed child canvases until control returns to the event loop;
        # if integration starts immediately, the first frame the player actually
        # sees can already be displaced and looks like the first card "jumps".
        self.update_display()
        self.after_id = self.root.after_idle(self._commit_spin_entry_frame)

    def _commit_spin_entry_frame(self) -> None:
        """Commit one truly visible zero-position reel frame before motion.

        This extra event-loop boundary is used for both START and START NEXT
        ROUND.  The stationary DEAL card and reel strip[0] are identical, and
        physics time begins only after the zero frame has been mapped/painted.
        """
        self.after_id = None
        if self.phase not in {"deal_spinning", "draw_spinning"}:
            return

        # Reassert exact zero position for DEAL entry.  DRAW also starts at zero
        # by construction, so this is harmless and keeps both paths deterministic.
        if self.spin_mode == "deal":
            self.reel_positions = [0.0] * self.REEL_COUNT

        self.draw_scene()
        self.last_frame_time = time.monotonic()
        self.after_id = self.root.after(
            self.FRAME_INTERVAL_MS,
            self._physics_frame,
        )

    def _earlier_active_reel_is_moving(self, reel_index: int) -> bool:
        """Guarantee left-to-right seating for sequential bans in DEAL and DRAW."""
        for earlier in range(reel_index):
            if not self.reel_spin_mask[earlier]:
                continue
            if self.reel_states[earlier] != "stopped":
                return True
        return False

    def _physics_frame(self) -> None:
        """Advance all moving reels using small physics substeps.

        Tkinter timer intervals are not perfectly uniform.  R7 therefore
        separates rendering cadence from physics integration: each visual
        frame may contain several <= 1/120 s physics steps.  This preserves
        the original accelerate -> drag -> nearest-index seating model while
        making the visible card motion much less jumpy when a frame arrives
        late.
        """
        if self.phase not in {"deal_spinning", "draw_spinning"}:
            return

        now = time.monotonic()
        frame_dt = max(0.001, min(0.060, now - self.last_frame_time))
        self.last_frame_time = now

        position_before_frame = list(self.reel_positions)
        remaining = frame_dt

        while remaining > 1e-9:
            dt = min(self.MAX_PHYSICS_STEP, remaining)
            remaining -= dt

            for index in range(self.REEL_COUNT):
                if not self.reel_spin_mask[index]:
                    self.reel_states[index] = "locked"
                    self.reel_velocities[index] = 0.0
                    continue

                state = self.reel_states[index]
                velocity = self.reel_velocities[index]

                if state == "accelerating":
                    velocity += self.reel_accels[index] * dt
                    target_speed = self.reel_target_speeds[index]
                    if velocity >= target_speed:
                        velocity = target_speed
                        self.reel_states[index] = "decelerating"
                    self._set_reel_position_guarded(
                        index, self.reel_positions[index] + velocity * dt
                    )

                elif state == "decelerating":
                    velocity *= math.exp(-self.reel_drags[index] * dt)
                    self._set_reel_position_guarded(
                        index, self.reel_positions[index] + velocity * dt
                    )

                    if abs(velocity) <= self.ALIGN_THRES保留:
                        if self._earlier_active_reel_is_moving(index):
                            # A later reel may mechanically reach low speed first,
                            # but it keeps creeping until every active reel to its
                            # left has seated. This makes the R1→R2→... removal
                            # sequence deterministic without preselecting outcomes.
                            velocity = max(abs(velocity), self.ALIGN_THRES保留 * 0.72)
                            self._set_reel_position_guarded(
                                index,
                                self.reel_positions[index] + velocity * dt,
                            )
                        else:
                            position = self.reel_positions[index]
                            fraction = position - math.floor(position)
                            target = math.floor(position) if fraction < 0.5 else math.ceil(position)
                            if self._alignment_target_is_allowed(index, int(target)):
                                self.reel_align_targets[index] = int(target)
                                self.reel_states[index] = "aligning"
                            else:
                                # A duplicate that was already visible when the
                                # earlier reel stopped may finish rolling out, but
                                # the reel cannot seat until all three final visible
                                # cards (TOP/MIDDLE/BOTTOM) are free of banned cards.
                                velocity = max(
                                    abs(velocity), self.ALIGN_THRES保留 * 0.86
                                )

                elif state == "aligning":
                    target = self.reel_align_targets[index]
                    if target is None:
                        target = round(self.reel_positions[index])
                        self.reel_align_targets[index] = int(target)

                    error = float(target) - self.reel_positions[index]
                    self._set_reel_position_guarded(
                        index,
                        self.reel_positions[index]
                        + error * min(1.0, dt * 4.8),
                    )
                    velocity *= math.exp(-5.2 * dt)

                    if abs(error) < 0.0025:
                        self._set_reel_position_guarded(index, float(target))
                        velocity = 0.0
                        self.reel_states[index] = "stopped"
                        self._on_reel_stopped(index)

                elif state == "stopped":
                    velocity = 0.0

                self.reel_velocities[index] = velocity

        # V4 frame-end cleanup only releases protected copies that have fully
        # rolled out. Newly entering cards were already sanitized before motion.
        for index in range(self.REEL_COUNT):
            if self.reel_spin_mask[index] and self.reel_states[index] != "stopped":
                self._sanitize_banned_cards_ahead(index)

        for index in range(self.REEL_COUNT):
            if self.reel_states[index] in {"stopped", "locked"}:
                self.reel_display_speeds[index] = 0.0
            else:
                self.reel_display_speeds[index] = (
                    abs(self.reel_positions[index] - position_before_frame[index]) / frame_dt
                )

        moving = sum(
            1
            for i in range(self.REEL_COUNT)
            if self.reel_states[i] in {"accelerating", "decelerating", "aligning"}
        )
        if moving:
            avg_speed = sum(self.reel_display_speeds) / max(1, moving)
            self.phase_var.set(f"滚动 {moving} 列")
            self.status_var.set(f"平均 {avg_speed:.1f} 格/秒")

        self.draw_scene()

        if moving == 0:
            self._finish_physical_spin()
            return

        self.after_id = self.root.after(self.FRAME_INTERVAL_MS, self._physics_frame)

    def _strip_card(self, reel_index: int, absolute_index: int) -> Card:
        strip = self.reel_strips[reel_index]
        if not strip:
            # Defensive fallback; normal gameplay always generates strips first.
            strip = self._make_300_card_strip()
            self.reel_strips[reel_index] = strip
        return strip[int(absolute_index) % len(strip)]

    def _center_card_for_reel(self, reel_index: int) -> Card:
        return self._strip_card(reel_index, int(round(self.reel_positions[reel_index])))

    def _finish_physical_spin(self) -> None:
        self.after_id = None
        mode = self.spin_mode

        if mode == "deal":
            self.initial_hand = [
                self._center_card_for_reel(col) for col in range(self.REEL_COUNT)
            ]
            self.matrix = [[None] * self.REEL_COUNT for _ in range(3)]
            self.matrix[1] = list(self.initial_hand)
            self.phase = "保留"
            self.spin_mode = ""
            self.shutter_transitioning = True
            self.result_var.set("首轮停止 · 机械挡板关闭中…")
            self.status_var.set("TOP ↓ / BOTTOM ↑ · 关闭后使用下方「保留」按钮")
            self.phase_var.set("挡板关闭")
            self.primary_button.configure(text="继续", state=tk.DISABLED)
            self._set_bet_controls_enabled(False)
            self._animate_shutters_to(
                columns=tuple(range(self.REEL_COUNT)),
                target=0.0,
                callback=self._finish_deal_hold_ready,
            )
            return

        if mode == "draw":
            for col in range(self.REEL_COUNT):
                if self.held[col]:
                    card = self.initial_hand[col]
                    for row in range(3):
                        self.matrix[row][col] = card
                else:
                    center_index = int(round(self.reel_positions[col]))
                    self.matrix[0][col] = self._strip_card(col, center_index - 1)
                    self.matrix[1][col] = self._strip_card(col, center_index)
                    self.matrix[2][col] = self._strip_card(col, center_index + 1)

            self.hold_slide_progress = [1.0] * self.REEL_COUNT
            self.spin_mode = ""
            self._finish_draw_result()

    def _finish_deal_hold_ready(self) -> None:
        self.shutter_transitioning = False
        self.result_var.set("首次转动完成 · 选择保留手牌")
        self.status_var.set("每列下方均有「保留」按钮；选好后按 继续")
        self.phase_var.set("保留")
        self.primary_button.configure(text="继续", state=tk.NORMAL)
        self._set_bet_controls_enabled(False)
        self.draw_scene()

    def _finish_draw_result(self) -> None:
        self.phase = "result"
        self.line_results = []
        total_credits = 0

        for line_index in range(self.active_lines):
            pattern = PAYLINES[line_index]
            cards: list[Card] = []
            for col, row in enumerate(pattern):
                card = self.matrix[row][col]
                if card is None:
                    raise RuntimeError("Spin Poker matrix contains an empty card at settlement.")
                cards.append(card)

            hand_key = evaluate_hand(cards)
            credits = payout_credits(hand_key, self.credits_per_line)
            dollars = credits * self.CREDIT_VALUE
            total_credits += credits
            self.line_results.append(
                {
                    "line": line_index + 1,
                    "pattern": pattern,
                    "cards": cards,
                    "hand_key": hand_key,
                    "label": HAND_LABELS[hand_key],
                    "credits": credits,
                    "dollars": dollars,
                }
            )

        total_return = total_credits * self.CREDIT_VALUE
        self.last_win = float(total_return)
        self.balance += total_return
        update_balance_in_json(self.username, self.balance)

        winning = [result for result in self.line_results if result["credits"] > 0]
        if winning:
            self._highlight_payout_rows({result["hand_key"] for result in winning})
            self.result_var.set(f"共 {len(winning)} 条线中奖 · 返还 ${total_return:,.2f}")
            best = max(winning, key=lambda item: item["credits"])
            self.status_var.set(
                f"按下 开始下一局 开始新的一局"
            )
        else:
            self.result_var.set("本局未中奖")
            self.status_var.set("没有形成 J或更高对子 的中奖牌型；按下 开始下一局 开始新的一局")

        self.phase_var.set("结算完成")
        self.primary_button.configure(text="开始下一局", state=tk.NORMAL)
        self._set_bet_controls_enabled(True)
        self.update_display()

    # ------------------------------------------------------------------
    # Canvas interaction / geometry
    # ------------------------------------------------------------------

    def _grid_geometry(self) -> tuple[float, float]:
        total_w = self.CARD_W * self.REEL_COUNT + self.CARD_GAP_X * (self.REEL_COUNT - 1)
        start_x = (self.CANVAS_WIDTH - total_w) / 2
        return start_x, float(self.GRID_TOP)

    def _card_rect(self, row: int, col: int) -> tuple[float, float, float, float]:
        start_x, start_y = self._grid_geometry()
        x1 = start_x + col * (self.CARD_W + self.CARD_GAP_X)
        y1 = start_y + row * self.CARD_PITCH
        return x1, y1, x1 + self.CARD_W, y1 + self.CARD_H

    def _card_center(self, row: int, col: int) -> tuple[float, float]:
        x1, y1, x2, y2 = self._card_rect(row, col)
        return (x1 + x2) / 2, (y1 + y2) / 2

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _payline_card_points(
        self,
        pattern: tuple[int, int, int, int, int],
        *,
        left_anchor_y: float,
        right_anchor_y: float,
    ) -> list[tuple[float, float]]:
        """Return the five R9 FINAL card points for one payline.

        Geometry rules:
        1. Reel 1 uses the left-facing edge and the left badge Y.
        2. Reel 5 uses the right-facing edge and the right badge Y.
        3. Reels 2..4 use exact centres by default.
        4. A consecutive same-row run that touches Reel 1 or Reel 5 inherits
           that edge Y.  This keeps repeated-row sections horizontal without
           distorting isolated centre points.

        This is intentionally computed per complete line instead of per card;
        whether Reel 2/3/4 should leave its centre depends on its neighbours.
        """
        points = [list(self._card_center(row, col)) for col, row in enumerate(pattern)]

        margin_y = 8.0
        edge_inset = float(self.EDGE_POINT_X_INSET)

        # Side-facing first-card point, horizontally parallel with the left badge.
        x1, y1, x2, y2 = self._card_rect(pattern[0], 0)
        points[0][0] = x1 + edge_inset
        points[0][1] = self._clamp(float(left_anchor_y), y1 + margin_y, y2 - margin_y)

        # Side-facing fifth-card point, horizontally parallel with the right badge.
        x1, y1, x2, y2 = self._card_rect(pattern[-1], self.REEL_COUNT - 1)
        points[-1][0] = x2 - edge_inset
        points[-1][1] = self._clamp(float(right_anchor_y), y1 + margin_y, y2 - margin_y)

        # Find contiguous runs of the same row.  Only runs touching an OUTER reel
        # are flattened to the outer edge Y.  Interior-only runs retain exact
        # centres, satisfying the R2-R4-centre rule.
        run_start = 0
        while run_start < self.REEL_COUNT:
            run_end = run_start
            while (
                run_end + 1 < self.REEL_COUNT
                and pattern[run_end + 1] == pattern[run_start]
            ):
                run_end += 1

            if run_end > run_start:
                touches_left = run_start == 0
                touches_right = run_end == self.REEL_COUNT - 1

                if touches_left and touches_right:
                    # Horizontal lines 1/2/3 normally have identical badge Y on
                    # both sides.  Use their mean defensively if a future layout
                    # shifts one side by a pixel.
                    run_y = (points[0][1] + points[-1][1]) / 2.0
                    for col in range(run_start, run_end + 1):
                        points[col][1] = run_y
                elif touches_left:
                    run_y = points[0][1]
                    for col in range(run_start + 1, run_end + 1):
                        points[col][1] = run_y
                elif touches_right:
                    run_y = points[-1][1]
                    for col in range(run_start, run_end):
                        points[col][1] = run_y

            run_start = run_end + 1

        return [(float(x), float(y)) for x, y in points]

    def _on_canvas_click(self, event) -> None:
        if self.phase != "保留" or self.shutter_transitioning:
            return

        for col, rect in self.hold_button_rects.items():
            x1, y1, x2, y2 = rect
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.toggle_保留(col)
                return

        # Retain direct middle-card click as a secondary convenience.
        for col in range(self.REEL_COUNT):
            x1, y1, x2, y2 = self._card_rect(1, col)
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.toggle_保留(col)
                return

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _set_reel_canvases_visible(self, visible: bool) -> None:
        for reel_canvas, (x, y, width, height) in zip(
            self.reel_canvases, self.reel_canvas_places
        ):
            if visible:
                reel_canvas.place(x=x, y=y, width=width, height=height)
                reel_canvas.tk.call("raise", reel_canvas._w)
            else:
                reel_canvas.place_forget()

    def draw_scene(self) -> None:
        if not hasattr(self, "game_canvas"):
            return

        c = self.game_canvas
        c.delete("all")
        c.create_rectangle(
            0, 0, self.CANVAS_WIDTH, self.CANVAS_HEIGHT,
            fill=Theme.CANVAS_BG, outline=""
        )
        c.create_rectangle(
            44, 6, self.CANVAS_WIDTH - 44, 448,
            fill=Theme.PANEL_ALT, outline=Theme.BORDER, width=2,
        )

        spinning = self.phase in {"deal_spinning", "draw_spinning"}
        if spinning:
            self._draw_physical_reels()
            self._set_reel_canvases_visible(True)
        else:
            self._set_reel_canvases_visible(False)
            for row in range(3):
                for col in range(self.REEL_COUNT):
                    self._draw_grid_cell(row, col)

        # TOP/BOTTOM obstruction is ALWAYS the Blackjack mechanical shutter.
        # Never use Background.png/card backs as a blocking layer.
        if not spinning:
            self._draw_hold_slide_covers()

        if self.phase == "保留":
            self._draw_保留_decorations()

        self._draw_row_labels()
        self._draw_hold_buttons()
        self._draw_footer()
        self._draw_all_active_paylines_top_layer()

    def _draw_physical_reels(self) -> None:
        """Draw physical strips in five real clipped viewports.

        DEAL/DRAW always render real strip cards in all three windows.
        Whenever TOP/BOTTOM must be hidden, the Blackjack mechanical shutter
        is the only blocking surface; Background.png is never used as a cover.
        """
        c = self.game_canvas
        start_x, start_y = self._grid_geometry()
        viewport_h = self.CARD_H * 3 + self.CARD_GAP_Y * 2
        local_middle_center = self.CARD_H / 2 + self.CARD_PITCH

        for col, reel_canvas in enumerate(self.reel_canvases):
            x1 = start_x + col * (self.CARD_W + self.CARD_GAP_X)
            x2 = x1 + self.CARD_W
            c.create_rectangle(
                x1 - 3, start_y - 3, x2 + 3, start_y + viewport_h + 3,
                fill="#454C52", outline=Theme.CARD_EDGE, width=2,
            )

            reel_canvas.delete("all")
            reel_canvas.configure(bg="#454C52")

            if self.phase == "draw_spinning" and self.held[col]:
                card = self.initial_hand[col]
                for row in range(3):
                    y1 = row * self.CARD_PITCH
                    self._draw_card_on_canvas(
                        reel_canvas, 0, y1, self.CARD_W, y1 + self.CARD_H,
                        card, face_down=False,
                    )
                # Keep the DEAL-row HOLD wording visible after Continue is pressed.
                middle_y1 = float(self.CARD_PITCH)
                self._draw_deal_hold_badge(
                    reel_canvas,
                    0.0, middle_y1, float(self.CARD_W), middle_y1 + self.CARD_H,
                )
            else:
                position = self.reel_positions[col]
                base_index = math.floor(position)
                for strip_index in range(base_index - 3, base_index + 4):
                    y_center = local_middle_center + (strip_index - position) * self.CARD_PITCH
                    y1 = y_center - self.CARD_H / 2
                    y2 = y_center + self.CARD_H / 2
                    if y2 < -self.CARD_H or y1 > viewport_h + self.CARD_H:
                        continue
                    self._draw_card_on_canvas(
                        reel_canvas, 0, y1, self.CARD_W, y2,
                        self._strip_card(col, strip_index), face_down=False,
                    )

            # During physical motion, TOP/BOTTOM obstruction (if any) remains
            # the same Blackjack steel shutter, drawn inside this clipped reel
            # canvas.  No Background.png/card-back blocker is ever substituted.
            progress = max(0.0, min(1.0, float(self.hold_slide_progress[col])))
            top_y1 = 0.0
            top_y2 = float(self.CARD_H)
            self._draw_blackjack_hold_shutter(
                x1=0.0, y1=top_y1, x2=float(self.CARD_W), y2=top_y2,
                panel_y=top_y1 - self.CARD_H * progress,
                label="", canvas=reel_canvas,
            )
            bottom_y1 = float(2 * self.CARD_PITCH)
            bottom_y2 = bottom_y1 + self.CARD_H
            self._draw_blackjack_hold_shutter(
                x1=0.0, y1=bottom_y1, x2=float(self.CARD_W), y2=bottom_y2,
                panel_y=bottom_y1 + self.CARD_H * progress,
                label="", canvas=reel_canvas,
            )

            # The metal separators sit in front of the continuous strip and
            # hide it while passing between windows.
            for gap_y in (self.CARD_H, self.CARD_PITCH + self.CARD_H):
                reel_canvas.create_rectangle(
                    0, gap_y, self.CARD_W, gap_y + self.CARD_GAP_Y,
                    fill="#454C52", outline="",
                )

            for row in range(3):
                y1 = row * self.CARD_PITCH
                reel_canvas.create_rectangle(
                    0, y1, self.CARD_W - 1, y1 + self.CARD_H - 1,
                    outline=Theme.CARD_EDGE, width=2,
                )

    def _draw_grid_cell(self, row: int, col: int) -> None:
        x1, y1, x2, y2 = self._card_rect(row, col)
        card: Optional[Card] = None
        face_down = False

        if self.phase == "idle":
            # First-load showcase.  TOP/BOTTOM are physically hidden by shutters,
            # while the DEAL row visibly presents the preset Spade Royal Flush.
            card = self.demo_hand[col]
        elif self.phase == "保留":
            # All three cards are stationary underneath the mechanical HOLD
            # shutters.  TOP/BOTTOM visibility is controlled entirely by the
            # clipped Blackjack-texture shutter layer drawn afterward.
            # Keeping the real card underneath at every animation frame avoids
            # holes/flicker and guarantees there is never a card-back/shutter
            # interpenetration transition.
            card = self.initial_hand[col]
        elif self.phase == "result":
            card = self.matrix[row][col]
            face_down = False
        else:
            face_down = False

        self._draw_card(x1, y1, x2, y2, card, face_down=face_down)

    def _draw_blackjack_hold_shutter(
        self,
        *,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        panel_y: float,
        label: str = "",
        canvas: Optional[tk.Canvas] = None,
    ) -> None:
        """Draw one rigid Blackjack-style shutter, manually clipped to a cell.

        Tk's main Canvas has no clip-path.  Instead of drawing a full panel and
        masking it afterward (which can visually punch through adjacent rows),
        every primitive is intersected with [y1, y2] before it is emitted.
        The shutter therefore never enters the DEAL row or the cabinet gaps.
        """
        c = canvas if canvas is not None else self.game_canvas
        panel_h = y2 - y1
        panel_bottom = panel_y + panel_h

        visible_top = max(y1, panel_y)
        visible_bottom = min(y2, panel_bottom)
        if visible_bottom <= visible_top + 0.01:
            return

        # Main steel face — same palette as Blackjack_Slot_Machine._draw_shutter.
        c.create_rectangle(
            x1, visible_top, x2, visible_bottom,
            fill=Theme.SHUTTER,
            outline="",
        )

        # Preserve the rigid panel's rib positions while clipping each rib to
        # this row's window.  Nothing is redrawn relative to the visible slice.
        rib_y = panel_y + 8.0
        while rib_y < panel_bottom:
            if y1 <= rib_y <= y2:
                c.create_line(
                    x1 + 4, rib_y, x2 - 4, rib_y,
                    fill=Theme.SHUTTER_DARK,
                    width=2,
                )
            light_y = rib_y + 2.0
            if y1 <= light_y <= y2:
                c.create_line(
                    x1 + 4, light_y, x2 - 4, light_y,
                    fill=Theme.SHUTTER_RIB_LIGHT,
                    width=1,
                )
            rib_y += 12.0

        # Draw only the actual rigid-panel edges that are currently inside the
        # clip window.  The clip boundary itself never becomes a fake panel edge.
        c.create_line(x1, visible_top, x1, visible_bottom,
                      fill=Theme.SHUTTER_EDGE, width=3)
        c.create_line(x2, visible_top, x2, visible_bottom,
                      fill=Theme.SHUTTER_EDGE, width=3)
        if y1 <= panel_y <= y2:
            c.create_line(x1, panel_y, x2, panel_y,
                          fill=Theme.SHUTTER_EDGE, width=3)
        if y1 <= panel_bottom <= y2:
            c.create_line(x1, panel_bottom, x2, panel_bottom,
                          fill=Theme.SHUTTER_EDGE, width=3)

        # Blackjack brass plate.  The plate is also geometrically clipped, so a
        # partially exiting plate cannot overlap the middle card or cabinet gap.
        plate_cy = panel_y + panel_h / 2.0
        outer_top = plate_cy - 22.0
        outer_bottom = plate_cy + 22.0
        # Tk text itself cannot be clipped.  Render it only while the full brass
        # label region is safely inside the card window; this prevents glyphs
        # from ever bleeding into an adjacent row during travel.
        if label and outer_top >= y1 and outer_bottom <= y2:
            c.create_text(
                (x1 + x2) / 2.0,
                plate_cy,
                text=label,
                fill="#25221D",
                font=(Theme.FONT_CJK, 11, "bold"),
            )

    def _draw_hold_slide_covers(self) -> None:
        """Draw Blackjack-texture HOLD shutters with hard per-cell clipping.

        progress 0 -> TOP/BOTTOM shutters fully cover their own card windows.
        progress 1 -> TOP rigid shutter has travelled upward out of TOP; BOTTOM
                      rigid shutter has travelled downward out of BOTTOM.

        Crucially, no object is ever painted outside its own TOP/BOTTOM card
        rectangle.  This is true clipping-by-construction, not a later mask, so
        there is no possible穿模 into the DEAL row or the separator gaps.
        """
        for col in range(self.REEL_COUNT):
            progress = max(0.0, min(1.0, float(self.hold_slide_progress[col])))

            # TOP: rigid panel translates upward by exactly one card height.
            x1, y1, x2, y2 = self._card_rect(0, col)
            top_panel_y = y1 - self.CARD_H * progress
            self._draw_blackjack_hold_shutter(
                x1=x1, y1=y1, x2=x2, y2=y2,
                panel_y=top_panel_y,
                label="",
            )

            # BOTTOM: rigid panel translates downward by exactly one card height.
            x1, y1, x2, y2 = self._card_rect(2, col)
            bottom_panel_y = y1 + self.CARD_H * progress
            self._draw_blackjack_hold_shutter(
                x1=x1, y1=y1, x2=x2, y2=y2,
                panel_y=bottom_panel_y,
                label="",
            )

    def _draw_hold_buttons(self) -> None:
        """Blackjack-style brass HOLD button below every reel column."""
        c = self.game_canvas
        self.hold_button_rects = {}
        _start_x, start_y = self._grid_geometry()
        grid_bottom = start_y + self.CARD_H * 3 + self.CARD_GAP_Y * 2
        button_y1 = grid_bottom + 7
        button_y2 = button_y1 + 27

        for col in range(self.REEL_COUNT):
            x1, _y1, x2, _y2 = self._card_rect(2, col)
            bx1 = x1 + 10
            bx2 = x2 - 10
            self.hold_button_rects[col] = (bx1, button_y1, bx2, button_y2)

            enabled = self.phase == "保留" and not self.shutter_transitioning
            selected = self.held[col] if self.phase == "保留" else False
            if enabled and selected:
                fill = Theme.BRASS_LIGHT
                edge = Theme.BRASS_EDGE
                text_fill = "#25221D"
            elif enabled:
                fill = Theme.BRASS
                edge = Theme.BRASS_EDGE
                text_fill = "#25221D"
            else:
                fill = "#9C968B"
                edge = "#777169"
                text_fill = "#514D48"

            # Same three-layer mechanical button treatment as Blackjack.
            c.create_rectangle(
                bx1 + 2, button_y1 + 3, bx2 + 2, button_y2 + 3,
                fill="#777068", outline="",
            )
            c.create_rectangle(
                bx1, button_y1, bx2, button_y2,
                fill=fill, outline=edge, width=2,
            )
            c.create_rectangle(
                bx1 + 4, button_y1 + 4, bx2 - 4, button_y2 - 4,
                outline=Theme.BRASS_LIGHT if enabled else "#B4ADA3",
                width=1,
            )
            c.create_text(
                (bx1 + bx2) / 2, (button_y1 + button_y2) / 2,
                text="保留", fill=text_fill,
                font=(Theme.FONT_CJK, 9, "bold"),
            )

    def _draw_deal_hold_badge(
        self,
        canvas: tk.Canvas,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
    ) -> None:
        """Draw the HOLD wording on the DEAL/middle card.

        This helper is shared by the stationary HOLD view and the raised child
        reel canvas used during DRAW.  Therefore pressing Continue no longer
        makes the DEAL-row "保留" badge disappear on locked columns.
        """
        canvas.create_rectangle(
            x1 + 18, y2 - 23, x2 - 18, y2 - 5,
            fill=Theme.GOLD_SOFT, outline=Theme.GOLD, width=1,
        )
        canvas.create_text(
            (x1 + x2) / 2, y2 - 14,
            text="保留", fill=Theme.TEXT,
            font=(Theme.FONT, 8, "bold"),
        )

    def _draw_保留_decorations(self) -> None:
        for col, is_held in enumerate(self.held):
            if not is_held:
                continue
            for row in range(3):
                x1, y1, x2, y2 = self._card_rect(row, col)
                self.game_canvas.create_rectangle(
                    x1 + 1, y1 + 1, x2 - 1, y2 - 1,
                    outline=Theme.GOLD,
                    width=4 if row == 1 else 2,
                )
            x1, y1, x2, y2 = self._card_rect(1, col)
            self._draw_deal_hold_badge(self.game_canvas, x1, y1, x2, y2)

    def _draw_card(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        card: Optional[Card],
        *,
        face_down: bool,
    ) -> None:
        self._draw_card_on_canvas(
            self.game_canvas, x1, y1, x2, y2, card, face_down=face_down
        )

    def _draw_card_on_canvas(
        self,
        canvas: tk.Canvas,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        card: Optional[Card],
        *,
        face_down: bool,
    ) -> None:
        canvas.create_rectangle(
            x1, y1, x2, y2,
            fill=Theme.CARD_FACE if not face_down else Theme.CARD_BACK,
            outline=Theme.CARD_EDGE, width=2,
        )
        if face_down:
            if self.card_back_image is not None:
                canvas.create_image((x1 + x2) / 2, (y1 + y2) / 2, image=self.card_back_image)
            else:
                inset = 8
                canvas.create_rectangle(
                    x1 + inset, y1 + inset, x2 - inset, y2 - inset,
                    outline=Theme.GOLD_SOFT, width=2,
                )
                canvas.create_text(
                    (x1 + x2) / 2, (y1 + y2) / 2,
                    text="SPIN\nPOKER", fill="#F4EFE6",
                    font=(Theme.FONT, 11, "bold"), justify=tk.CENTER,
                )
            return
        if card is None:
            return
        image = self.card_images.get(card)
        if image is not None:
            canvas.create_image((x1 + x2) / 2, (y1 + y2) / 2, image=image)
            return
        suit, rank = card
        glyph = SUIT_GLYPH[suit]
        color = Theme.HEART_DIAMOND if suit in {"Heart", "Diamond"} else Theme.CLUB_SPADE
        canvas.create_text(
            x1 + 9, y1 + 7, text=f"{rank}{glyph}", fill=color,
            font=(Theme.FONT, 10, "bold"), anchor=tk.NW,
        )
        canvas.create_text(
            (x1 + x2) / 2, (y1 + y2) / 2 + 2,
            text=glyph, fill=color, font=(Theme.FONT, 30, "bold"),
        )
        canvas.create_text(
            x2 - 9, y2 - 7, text=f"{rank}{glyph}", fill=color,
            font=(Theme.FONT, 10, "bold"), anchor=tk.SE,
        )

    def _draw_row_labels(self) -> None:
        c = self.game_canvas
        start_x, _ = self._grid_geometry()
        label_x = start_x - 18
        for row, text in enumerate(("TOP", "DEAL", "BOTTOM")):
            _, cy = self._card_center(row, 0)
            c.create_text(
                label_x, cy, text=text, fill=Theme.TEXT_MUTED,
                font=(Theme.FONT, 7, "bold"), angle=90,
            )

    def _winning_line_numbers(self) -> set[int]:
        if self.phase != "result":
            return set()
        return {
            int(result["line"])
            for result in self.line_results
            if result.get("credits", 0) > 0
        }

    def _line_side_anchor(self, line_number: int, side: str) -> tuple[float, float]:
        start_x, start_y = self._grid_geometry()
        grid_right = (
            start_x + self.REEL_COUNT * self.CARD_W
            + (self.REEL_COUNT - 1) * self.CARD_GAP_X
        )
        order = self.LINE_LEFT_ORDER if side == "left" else self.LINE_RIGHT_ORDER
        slot = order.index(line_number)
        top_y = start_y + 13
        bottom_y = start_y + (self.CARD_H * 3 + self.CARD_GAP_Y * 2) - 13
        y = top_y + slot * (bottom_y - top_y) / (len(order) - 1)
        x = start_x - 47 if side == "left" else grid_right + 47
        return x, y

    def _draw_all_active_paylines_top_layer(self) -> None:
        # R9: no line overlays during physical motion OR while the player is
        # choosing 保留.  This keeps card selection completely unobstructed.
        if self.phase in {"deal_spinning", "draw_spinning", "保留"}:
            return

        if self.phase == "result":
            # Settlement: only actual winning lines remain, and every winner
            # uses its own permanent representative colour.
            for line_number in sorted(self._winning_line_numbers()):
                if line_number <= self.active_lines:
                    self._draw_payline(
                        PAYLINES[line_number - 1], line_number, is_winner=True
                    )
            return

        # First-load idle showcase: the preset Spade Royal Flush is Line 1.
        if self.phase == "idle":
            self._draw_payline(PAYLINES[0], 1, is_winner=True)
            return

        for line_number in range(1, self.active_lines + 1):
            self._draw_payline(
                PAYLINES[line_number - 1], line_number, is_winner=False
            )

    def _draw_line_badge(
        self, x: float, y: float, line_number: int, color: str, *, winner: bool
    ) -> None:
        radius = 11 if winner else 9
        self.game_canvas.create_polygon(
            x, y - radius, x + radius, y, x, y + radius, x - radius, y,
            fill=color, outline="#30343A", width=2,
        )
        self.game_canvas.create_text(
            x, y, text=str(line_number), fill="#FFFFFF",
            font=(Theme.FONT, 8 if winner else 7, "bold"),
        )

    def _draw_payline(
        self,
        pattern: tuple[int, int, int, int, int],
        line_number: int,
        *,
        is_winner: bool,
    ) -> None:
        """Draw one R9 FINAL payline using edge-parallel straight geometry."""
        color = self.LINE_COLORS[line_number - 1]
        left_anchor = self._line_side_anchor(line_number, "left")
        right_anchor = self._line_side_anchor(line_number, "right")

        card_points = self._payline_card_points(
            pattern,
            left_anchor_y=left_anchor[1],
            right_anchor_y=right_anchor[1],
        )
        points: list[float] = [left_anchor[0], left_anchor[1]]
        for x, y in card_points:
            points.extend((x, y))
        points.extend((right_anchor[0], right_anchor[1]))

        # R9 FINAL: every segment is straight.  The first/last card points use
        # side-facing edges, same-row runs touching an edge stay horizontal, and
        # isolated Reel 2..4 points remain exact centres.
        color_width = 5 if is_winner else 3
        underlay_width = color_width + 3
        self.game_canvas.create_line(
            *points, fill="#F4F0E8", width=underlay_width,
            smooth=False, joinstyle="miter", capstyle="butt",
        )
        self.game_canvas.create_line(
            *points, fill=color, width=color_width,
            smooth=False, joinstyle="miter", capstyle="butt",
        )

        self._draw_line_badge(
            left_anchor[0], left_anchor[1], line_number, color, winner=is_winner
        )
        self._draw_line_badge(
            right_anchor[0], right_anchor[1], line_number, color, winner=is_winner
        )

    def _draw_footer(self) -> None:
        c = self.game_canvas
        y = 458
        c.create_text(
            52, y,
            text=(
                f"{self.active_lines}条线 × 每线 {self.credits_per_line} CREDITS = ${self.current_bet:,.2f}"
            ),
            fill=Theme.TEXT,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.W,
        )

        if self.phase in {"deal_spinning", "draw_spinning"}:
            states = {
                "accelerating": "加速",
                "decelerating": "惯性",
                "aligning": "对齐",
                "stopped": "停止",
                "locked": "保留",
            }
            status = "  ".join(
                f"R{i+1}:{states.get(self.reel_states[i], self.reel_states[i])}"
                for i in range(self.REEL_COUNT)
            )
            c.create_text(
                52, y + 29, text=status, fill=Theme.ACCENT,
                font=(Theme.FONT_CJK, 8, "bold"), anchor=tk.W,
            )
            c.create_text(
                52, y + 53,
                text="",
                fill=Theme.TEXT_MUTED, font=(Theme.FONT_CJK, 8), anchor=tk.W,
            )
            return

        if self.phase == "保留":
            held_cols = [str(index + 1) for index, held in enumerate(self.held) if held]
            c.create_text(
                52, y + 28,
                text="保留列：" + (", ".join(held_cols) if held_cols else "无"),
                fill=Theme.ACCENT, font=(Theme.FONT_CJK, 9, "bold"), anchor=tk.W,
            )
            c.create_text(
                52, y + 52,
                text="",
                fill=Theme.TEXT_MUTED, font=(Theme.FONT_CJK, 8), anchor=tk.W,
            )
            return

        if self.phase == "result":
            winning = [item for item in self.line_results if item["credits"] > 0]

            if winning:
                # 找出最高牌型。
                # 假设 line_results 中牌型强弱已经通过 credits / payout 正确体现，
                # 这里直接取本局单线返还最高的中奖结果。
                best = max(winning, key=lambda item: item["credits"])

                summary = (
                    f"本局共有 {len(winning)} 条中奖线"
                    f" · 最高牌型是 {best['label']}"
                )
            else:
                summary = "本局没有中奖线"
            c.create_text(
                52, y + 28, text=summary,
                fill=Theme.ACCENT if winning else Theme.TEXT_MUTED,
                font=(Theme.FONT_CJK, 8, "bold"), anchor=tk.W,
            )
            c.create_text(
                52, y + 52,
                text="",
                fill=Theme.TEXT_MUTED, font=(Theme.FONT_CJK, 8), anchor=tk.W,
            )
            return

        c.create_text(
            52, y + 30,
            text="待机预览 3 / 6 / 9 条彩色直线。",
            fill=Theme.TEXT_MUTED, font=(Theme.FONT_CJK, 8), anchor=tk.W,
        )

    # ------------------------------------------------------------------
    # Payout UI / display
    # ------------------------------------------------------------------

    def _clear_payout_highlights(self) -> None:
        for _key, widgets in self.payout_row_widgets.items():
            name_label, value_label, count_label, total_label, original_bg = widgets
            name_label.configure(bg=original_bg, fg=Theme.TEXT)
            value_label.configure(bg=original_bg, fg=Theme.AMBER)
            count_label.configure(bg=original_bg, fg=Theme.CYAN)
            total_label.configure(bg=original_bg, fg=Theme.GREEN)

    def _highlight_payout_rows(self, hand_keys: set[str]) -> None:
        self._clear_payout_highlights()
        for key in hand_keys:
            widgets = self.payout_row_widgets.get(key)
            if widgets is None:
                continue
            name_label, value_label, count_label, total_label, _ = widgets
            for widget in (name_label, value_label, count_label, total_label):
                widget.configure(bg=Theme.GOLD_SOFT)
            name_label.configure(fg=Theme.TEXT)
            value_label.configure(fg=Theme.TEXT)
            count_label.configure(fg=Theme.TEXT)
            total_label.configure(fg=Theme.TEXT)

    def update_display(self) -> None:
        self.balance_var.set(f"${self.balance:,.2f}")
        self.bet_var.set(f"${self.current_bet:,.2f}")
        self.last_win_var.set(f"${self.last_win:,.2f}")
        self.lines_var.set(f"{self.active_lines} lines")
        self.credits_var.set(f"{self.credits_per_line} CREDITS")

        hand_line_counts = {key: 0 for key in self.pay_vars}
        hand_totals = {key: 0.0 for key in self.pay_vars}
        if self.phase == "result":
            for result in self.line_results:
                if result.get("credits", 0) <= 0:
                    continue
                key = str(result["hand_key"])
                if key in hand_line_counts:
                    hand_line_counts[key] += 1
                    hand_totals[key] += float(result["dollars"])

        for key, variable in self.pay_vars.items():
            credits = payout_credits(key, self.credits_per_line)
            amount = credits * self.CREDIT_VALUE
            variable.set(f"${amount:,.0f}")
            if self.phase == "result":
                self.pay_line_count_vars[key].set(f"{hand_line_counts[key]}")
                self.pay_total_vars[key].set(f"${hand_totals[key]:,.0f}")
            else:
                self.pay_line_count_vars[key].set("-")
                self.pay_total_vars[key].set("-")

        if self.phase in {"idle", "result"}:
            self.primary_button.configure(
                text=("开始" if self.phase == "idle" else "开始下一局")
                + f" · ${self.current_bet:,.0f}",
                state=tk.NORMAL,
            )
            self._set_bet_controls_enabled(True)
        elif self.phase == "保留":
            self.primary_button.configure(
                text="继续 · 开启未保留挡板",
                state=tk.DISABLED if self.shutter_transitioning else tk.NORMAL,
            )
            self._set_bet_controls_enabled(False)
        else:
            self.primary_button.configure(text="滚动中…", state=tk.DISABLED)
            self._set_bet_controls_enabled(False)

        self.draw_scene()

    # ------------------------------------------------------------------
    # Closing
    # ------------------------------------------------------------------

    def on_closing(self) -> None:
        self.shutter_transitioning = False
        self._cancel_hold_slide_animation()

        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None

        update_balance_in_json(self.username, self.balance)
        finish = getattr(self.root, "finish", None)
        if callable(finish):
            finish(self.balance)
        else:
            self.root.destroy()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


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
                "EmbeddedGamePage is unavailable. Place this file inside "
                "the Small_Games package or make small_games.py importable."
            )
        page = EmbeddedGamePage(
            parent,
            title="Spin Poker R9",
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