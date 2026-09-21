"""Football Match — ChickenCrossing-style warm fixed HMI.

The original football-pachinko game model is preserved:
- Five rounds per match.
- Each round drops one HOME ball and one AWAY ball simultaneously.
- A team's ball scores only if it physically lands in the centre goal zone.
- Outcomes are NOT predetermined. Gravity, peg collisions, damping, wall
  rebounds, small random perturbations, and the original stuck-ball escape
  determine the result.
- Match-result, exact-total-goals, and over/under bets settle independently.
- Per-selection maximum: $10,000. Total match maximum: $100,000.
- Betting cells use a warm ChickenCrossing card palette with larger market text.
- R5 betting-cell chips are plain solid circles with no decorative pattern.
- Their fill/text colours are selected strictly from the displayed amount range.
- Stake/return chips use truncated 0.1K labels; hidden remainder adds '+'.
- At settlement those chips change to the actual returned amount, and zero-return chips disappear.

The view layer follows ChickenCrossing_tk.py's fixed 1150x750 warm HMI.
R4 widens the betting sidebar by 30px and reduces the field panel by 30px.
supports the project's EmbeddedGamePage single-Tk mode.
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
from tkinter import messagebox
from typing import Callable, Optional

try:
    from .small_games import EmbeddedGamePage
except ImportError:
    try:
        from small_games import EmbeddedGamePage
    except ImportError:
        EmbeddedGamePage = None


VERSION = "FootballMatch-ChickenStyle-R5"


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
    RED_HOVER = "#873D3D"
    AMBER = "#A36B22"

    FIELD = "#82A579"
    FIELD_DARK = "#6F9167"
    FIELD_LINE = "#DDE6D8"
    PEG = "#F0ECE4"
    PEG_BORDER = "#8E877E"
    HOME = "#4D7893"
    HOME_SOFT = "#B9CEDA"
    AWAY = "#B75B55"
    AWAY_SOFT = "#D7B4B0"
    GOAL = "#D6C67E"
    NO_GOAL = "#C9B9AE"
    WIN = "#D9B75B"

    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )
    FONT_EMOJI = "Segoe UI Emoji"


CHIP_CONFIGS = (
    ("$10", "10", "#E3A43A", "black"),
    ("$25", "25", "#67B56A", "black"),
    ("$100", "100", "#292929", "white"),
    ("$500", "500", "#D47AB7", "black"),
    ("$1K", "1000", "#F4F1EA", "black"),
    ("$2.5K", "2500", "#D75A54", "white"),
)

MATCH_ODDS = {"home": 2.60, "draw": 3.15, "away": 2.60}
TOTAL_GOAL_OPTIONS = ("0/1", "2", "3", "4", "5", "6+")
TOTAL_GOAL_ODDS = {
    "0/1": 19.60,
    "2": 7.40,
    "3": 4.55,
    "4": 4.00,
    "5": 4.60,
    "6+": 4.65,
}
OVER_UNDER_OPTIONS = ("under3.5", "over3.5", "under4.5", "over4.5")
OVER_UNDER_ODDS = {
    "under4.5": 1.60,
    "over4.5": 2.15,
    "under3.5": 2.50,
    "over3.5": 1.50,
}
OVER_UNDER_LABELS = {
    "under3.5": "小3.5",
    "over3.5": "大3.5",
    "under4.5": "小4.5",
    "over4.5": "大4.5",
}

PER_BET_MAX = 10_000.0
TOTAL_BET_MAX = 100_000.0


def get_data_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../A_Tools/Account/saving_data.json")


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


def money(value: float) -> str:
    return f"${float(value):,.2f}"


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
        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")

    def _on_enter(self, _event) -> None:
        if str(self.cget("state")) != tk.DISABLED:
            super().configure(bg=self.hover_background)

    def _on_leave(self, _event) -> None:
        super().configure(bg=self.normal_background)

    def set_colors(
        self,
        background: str,
        hover_background: Optional[str] = None,
        foreground: Optional[str] = None,
    ) -> None:
        self.normal_background = background
        self.hover_background = hover_background or background
        if foreground is not None:
            self.normal_foreground = foreground
        super().configure(
            bg=self.normal_background,
            fg=self.normal_foreground,
            activebackground=self.hover_background,
            activeforeground=self.normal_foreground,
        )


class ChipButton(tk.Canvas):
    def __init__(
        self,
        master,
        *,
        label: str,
        amount: str,
        chip_color: str,
        text_color: str,
        command: Callable[[str], None],
        width: int = 49,
        height: int = 50,
    ) -> None:
        super().__init__(
            master,
            width=width,
            height=height,
            bg=Theme.PANEL,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.label = label
        self.amount = amount
        self.chip_color = chip_color
        self.text_color = text_color
        self.command = command
        self.control_width = width
        self.control_height = height
        self._state = tk.NORMAL
        self._hovered = False
        self._pressed = False
        self._selected = False

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.draw()

    @staticmethod
    def _shade(hex_color: str, factor: float) -> str:
        rgb = [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]
        rgb = [max(0, min(255, round(channel * factor))) for channel in rgb]
        return "#%02x%02x%02x" % tuple(rgb)

    def draw(self) -> None:
        self.delete("all")
        offset_y = 3 if self._pressed else 0
        outer = self._shade(self.chip_color, 0.68)
        inner = self._shade(self.chip_color, 0.86)
        outline = Theme.ACCENT if self._selected else (
            Theme.TEXT if self._hovered else outer
        )
        outline_width = 3 if self._selected or self._hovered else 2

        self.create_oval(
            5, 7, self.control_width - 4, self.control_height - 1,
            fill="#8E877E", outline=""
        )
        self.create_oval(
            4, 3 + offset_y, self.control_width - 5,
            self.control_height - 5 + offset_y,
            fill=outer, outline=outline, width=outline_width
        )
        self.create_oval(
            8, 7 + offset_y, self.control_width - 9,
            self.control_height - 9 + offset_y,
            fill=self.chip_color, outline=inner, width=2
        )
        self.create_oval(
            13, 12 + offset_y, self.control_width - 14,
            self.control_height - 14 + offset_y,
            fill=self.chip_color, outline=outer, width=1
        )

        cx = self.control_width / 2
        cy = (self.control_height - 2) / 2 + offset_y
        inserts = (
            (cx - 3, 4 + offset_y, cx + 3, 10 + offset_y),
            (cx - 3, self.control_height - 12 + offset_y, cx + 3,
             self.control_height - 6 + offset_y),
            (5, cy - 3, 11, cy + 3),
            (self.control_width - 12, cy - 3, self.control_width - 6, cy + 3),
        )
        for x1, y1, x2, y2 in inserts:
            self.create_rectangle(x1, y1, x2, y2, fill=self.text_color, outline="")

        self.create_text(
            cx, cy, text=self.label, fill=self.text_color,
            font=(Theme.FONT, 8 if len(self.label) <= 4 else 7, "bold"),
        )

        if self._state == tk.DISABLED:
            self.create_oval(
                4, 3 + offset_y, self.control_width - 5,
                self.control_height - 5 + offset_y,
                fill="#C9C2B8", outline=Theme.BORDER_SOFT,
                width=1, stipple="gray50",
            )

    def _on_enter(self, _event) -> None:
        if self._state != tk.DISABLED:
            self._hovered = True
            self.draw()

    def _on_leave(self, _event) -> None:
        self._hovered = False
        self._pressed = False
        self.draw()

    def _on_press(self, _event) -> None:
        if self._state != tk.DISABLED:
            self._pressed = True
            self.draw()

    def _on_release(self, event) -> None:
        if self._state == tk.DISABLED:
            return
        was_pressed = self._pressed
        self._pressed = False
        inside = 0 <= event.x < self.control_width and 0 <= event.y < self.control_height
        if was_pressed and inside:
            self.command(self.amount)
        self.draw()

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self.draw()

    def set_enabled(self, enabled: bool) -> None:
        self._state = tk.NORMAL if enabled else tk.DISABLED
        self.configure(cursor="hand2" if enabled else "")
        self.draw()


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
        tk.Label(
            self, text=label, bg=Theme.PANEL_ALT, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9), anchor=tk.W,
        ).place(x=12, y=8, width=width - 24, height=18)
        tk.Label(
            self, textvariable=variable, bg=Theme.PANEL_ALT, fg=accent,
            font=(Theme.FONT, 15, "bold"), anchor=tk.W,
        ).place(x=12, y=29, width=width - 24, height=28)


class BetBox(tk.Canvas):
    """Clickable betting cell with a physical stake/return chip in the centre."""

    def __init__(
        self,
        master,
        *,
        key: str,
        label: str,
        odds: float,
        on_add: Callable[[str], None],
        on_reset: Callable[[str], None],
        width: int,
        height: int,
    ) -> None:
        super().__init__(
            master,
            width=width,
            height=height,
            bg=Theme.PANEL,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.key = key
        self.label = label
        self.odds = float(odds)
        self.on_add = on_add
        self.on_reset = on_reset
        self.control_width = width
        self.control_height = height

        # Before settlement this is the player's stake shown on the chip.
        # During settlement it becomes the actual return shown on that chip.
        self.amount = 0.0

        self.enabled = True
        self.hovered = False
        self.result_state = "normal"  # normal / win / lose

        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._left)
        self.bind("<Button-3>", self._right)
        self.draw()

    @staticmethod
    def _shade(hex_color: str, factor: float) -> str:
        rgb = [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]
        rgb = [max(0, min(255, round(channel * factor))) for channel in rgb]
        return "#%02x%02x%02x" % tuple(rgb)

    @staticmethod
    def _compact_money(value: float) -> str:
        """Format money for the chip without overstating the real amount.

        Examples:
            2500   -> $2.5K
            2560   -> $2.5K+
            12300  -> $12.3K
            12345  -> $12.3K+
        """
        value = max(0.0, float(value))

        if value >= 1000.0:
            # Truncate to one decimal K rather than rounding upward.
            tenths_k = math.floor((value / 1000.0) * 10.0 + 1e-9) / 10.0
            represented = tenths_k * 1000.0
            has_hidden_remainder = value - represented >= 0.01

            shown = f"${tenths_k:.1f}K"
            if has_hidden_remainder:
                shown += "+"
            return shown

        if abs(value - round(value)) < 1e-9:
            return f"${value:,.0f}"

        # Settlement can generate decimal returns.
        return f"${value:,.1f}"

    @staticmethod
    def _amount_chip_style(amount: float) -> tuple[str, str]:
        """Return the solid betting-chip fill/text colour for an amount."""
        amount = float(amount)

        if amount >= 10000:
            return "#D3BE00", "#000000"
        if amount >= 2500:
            return "#D75A54", "#FFFFFF"
        if amount >= 1000:
            return "#F4F1EA", "#000000"
        if amount >= 500:
            return "#D47AB7", "#000000"
        if amount >= 100:
            return "#292929", "#FFFFFF"
        if amount >= 25:
            return "#67B56A", "#000000"

        # The game minimum stake is $10, so this covers $10-$24.
        return "#E3A43A", "#000000"

    def _draw_amount_chip(self) -> None:
        if self.amount <= 0:
            return

        # R5 betting chips are deliberately plain: one solid circular fill,
        # one simple outline, and the amount text. No rings, marks, inserts,
        # stripes, segments, or other casino-chip decoration.
        diameter = min(
            max(31, self.control_height - 19),
            max(31, self.control_width - 10),
            40,
        )
        radius = diameter / 2

        cx = self.control_width / 2
        cy = self.control_height - radius - 2

        chip_color, text_color = self._amount_chip_style(self.amount)

        # Small neutral drop shadow is kept outside the chip; the chip itself
        # remains a single uninterrupted solid colour.
        self.create_oval(
            cx - radius + 2,
            cy - radius + 3,
            cx + radius + 2,
            cy + radius + 3,
            fill="#958C80",
            outline="",
        )

        self.create_oval(
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
            fill=chip_color,
            outline=Theme.TEXT if self.hovered and self.enabled else Theme.BORDER,
            width=2,
        )

        amount_text = self._compact_money(self.amount)

        if len(amount_text) <= 4:
            font_size = 10
        elif len(amount_text) <= 6:
            font_size = 9
        elif len(amount_text) <= 8:
            font_size = 8
        else:
            font_size = 7

        self.create_text(
            cx,
            cy,
            text=amount_text,
            fill=text_color,
            font=(Theme.FONT, font_size, "bold"),
        )

    def draw(self) -> None:
        self.delete("all")

        # Warm ChickenCrossing card palette.
        if self.result_state == "win":
            fill = "#E4D8A9"
            outline = "#A36B22"
            header_fill = "#D8C587"
        elif self.result_state == "lose":
            fill = "#E2DDD5"
            outline = Theme.BORDER_SOFT
            header_fill = "#D3CCC2"
        elif self.hovered and self.enabled:
            fill = "#E7E1D8"
            outline = Theme.ACCENT
            header_fill = Theme.ACCENT_SOFT
        elif self.amount > 0:
            fill = "#E7E1D8"
            outline = Theme.ACCENT
            header_fill = "#CAD8DE"
        else:
            fill = Theme.PANEL
            outline = Theme.BORDER_SOFT
            header_fill = Theme.PANEL_ALT

        border_width = 2 if (
            self.result_state == "win"
            or self.amount > 0
            or (self.hovered and self.enabled)
        ) else 1

        self.create_rectangle(
            1,
            1,
            self.control_width - 1,
            self.control_height - 1,
            fill=fill,
            outline=outline,
            width=border_width,
        )

        # A dedicated header strip separates text from the physical chip.
        header_height = 23 if self.control_width < 60 else 21
        self.create_rectangle(
            2,
            2,
            self.control_width - 2,
            header_height,
            fill=header_fill,
            outline="",
        )

        if self.control_width < 60:
            # Six exact-goal cells are narrow, so stack the two text rows.
            self.create_text(
                self.control_width / 2,
                8,
                text=self.label,
                fill=Theme.TEXT,
                font=(Theme.FONT_CJK, 9, "bold"),
                anchor=tk.CENTER,
            )
            self.create_text(
                self.control_width / 2,
                17,
                text=f"{self.odds:.2f}×",
                fill=Theme.ACCENT,
                font=(Theme.FONT, 8, "bold"),
                anchor=tk.CENTER,
            )
        else:
            self.create_text(
                7,
                11,
                text=self.label,
                fill=Theme.TEXT,
                font=(Theme.FONT_CJK, 10, "bold"),
                anchor=tk.W,
            )
            self.create_text(
                self.control_width - 7,
                11,
                text=f"{self.odds:.2f}×",
                fill=Theme.ACCENT,
                font=(Theme.FONT, 9, "bold"),
                anchor=tk.E,
            )

        # The chip itself is the amount display.
        self._draw_amount_chip()

        if not self.enabled:
            self.create_rectangle(
                1,
                1,
                self.control_width - 1,
                self.control_height - 1,
                outline=Theme.BORDER_SOFT,
                width=1,
            )

    def _enter(self, _event) -> None:
        if self.enabled:
            self.hovered = True
            self.draw()

    def _leave(self, _event) -> None:
        self.hovered = False
        self.draw()

    def _left(self, _event) -> None:
        if self.enabled:
            self.on_add(self.key)

    def _right(self, _event) -> None:
        if self.enabled:
            self.on_reset(self.key)

    def set_amount(self, amount: float) -> None:
        self.amount = max(0.0, float(amount))
        self.draw()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        self.configure(cursor="hand2" if enabled else "")
        self.draw()

    def set_result(self, state: str) -> None:
        self.result_state = state
        self.draw()


class FootballPachinko:
    WINDOW_WIDTH = 1150
    WINDOW_HEIGHT = 750
    SHELL_WIDTH = 1110
    SHELL_HEIGHT = 714
    HEADER_HEIGHT = 70
    BODY_TOP = 84
    BODY_HEIGHT = 630
    GAME_PANEL_WIDTH = 718
    SIDEBAR_WIDTH = 378
    PANEL_GAP = 14

    BOARD_WIDTH = 686
    BOARD_HEIGHT = 478
    ROUNDS_TOTAL = 5

    def __init__(self, root, initial_balance: float, username: str):
        self.root = root
        self._configure_root()

        self.username = username
        self.balance = float(initial_balance)

        self.bet_home = 0.0
        self.bet_draw = 0.0
        self.bet_away = 0.0
        self.total_goal_bets = {opt: 0.0 for opt in TOTAL_GOAL_OPTIONS}
        self.over_under_bets = {opt: 0.0 for opt in OVER_UNDER_OPTIONS}

        self.selected_chip = 10.0
        self.last_win = 0.0

        self.match_in_progress = False
        self.settlement_mode = False
        self.home_score = 0
        self.away_score = 0
        self.current_round = 0
        self.balls_in_round = 0
        self.balls: list[dict] = []
        self.pegs: list[tuple[float, float]] = []
        self.active_balls = 0
        self.animation_running = False
        self.after_id = None

        # Original physical tuning.
        self.gravity = 0.5
        self.damping = 0.8
        self.elasticity = 0.8

        self.score_effects: list[dict] = []

        self.balance_var = tk.StringVar()
        self.bet_var = tk.StringVar()
        self.last_win_var = tk.StringVar()
        self.round_var = tk.StringVar(value="第 0 / 5 轮")
        self.status_var = tk.StringVar(value="请选择筹码并点击盘口下注")
        self.score_var = tk.StringVar(value="0  :  0")

        self.chip_buttons: list[ChipButton] = []
        self.bet_boxes: dict[str, BetBox] = {}

        self.create_widgets()
        self.update_display()

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("足球弹珠")
            self.root.geometry("1150x750+50+10")
            self.root.resizable(False, False)
            self.root.protocol("WM_DELETE_WINDOW", self.on_close)
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
            master, width=width, height=height, bg=Theme.PANEL,
            highlightthickness=1, highlightbackground=Theme.BORDER_SOFT,
        )
        outer.pack_propagate(False)
        outer.grid_propagate(False)
        inner = tk.Frame(outer, bg=Theme.PANEL)
        inner.place(
            x=padding, y=padding,
            width=max(1, width - padding * 2),
            height=max(1, height - padding * 2),
        )
        outer.inner = inner
        outer.content = inner
        return outer

    @staticmethod
    def _section_title(master, text: str) -> tk.Label:
        return tk.Label(
            master, text=text, bg=Theme.PANEL, fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 10, "bold"), anchor=tk.W,
        )

    def create_widgets(self) -> None:
        shell = tk.Frame(
            self.root, width=self.SHELL_WIDTH, height=self.SHELL_HEIGHT,
            bg=Theme.APP_BG,
        )
        shell.pack(padx=20, pady=18)
        shell.pack_propagate(False)

        self._build_header(shell)

        body = tk.Frame(
            shell, width=self.SHELL_WIDTH, height=self.BODY_HEIGHT,
            bg=Theme.APP_BG,
        )
        body.place(x=0, y=self.BODY_TOP, width=self.SHELL_WIDTH, height=self.BODY_HEIGHT)

        self._build_game_panel(body)
        self._build_sidebar(body)

    def _build_header(self, shell: tk.Frame) -> None:
        header = tk.Frame(
            shell, width=self.SHELL_WIDTH, height=self.HEADER_HEIGHT,
            bg=Theme.PANEL, highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        header.place(x=0, y=0, width=self.SHELL_WIDTH, height=self.HEADER_HEIGHT)

        icon = tk.Canvas(header, width=48, height=48, bg=Theme.PANEL, bd=0, highlightthickness=0)
        icon.place(x=14, y=11)
        icon.create_oval(2, 2, 46, 46, fill=Theme.ACCENT_SOFT, outline=Theme.ACCENT, width=2)
        icon.create_oval(13, 13, 35, 35, fill="#F2F0E9", outline=Theme.TEXT, width=1)
        icon.create_polygon(24, 17, 29, 21, 27, 27, 21, 27, 19, 21, fill=Theme.TEXT, outline="")

        tk.Label(
            header, text="FOOTBALL MATCH",
            bg=Theme.PANEL, fg=Theme.TEXT,
            font=(Theme.FONT, 18, "bold"), anchor=tk.W,
        ).place(x=74, y=10, width=360, height=27)
        tk.Label(
            header, text="足球弹珠 · 纯物理碰撞",
            bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 11, "bold"), anchor=tk.W,
        ).place(x=74, y=39, width=300, height=20)

        balance_box = tk.Frame(
            header, width=206, height=46, bg=Theme.PANEL_ALT,
            highlightthickness=1, highlightbackground=Theme.BORDER_SOFT,
        )
        balance_box.place(x=self.SHELL_WIDTH - 220, y=12, width=206, height=46)
        tk.Label(
            balance_box, text="账户余额",
            bg=Theme.PANEL_ALT, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9), anchor=tk.W,
        ).place(x=12, y=4, width=90, height=17)
        tk.Label(
            balance_box, textvariable=self.balance_var,
            bg=Theme.PANEL_ALT, fg=Theme.ACCENT,
            font=(Theme.FONT, 15, "bold"), anchor=tk.E,
        ).place(x=12, y=20, width=182, height=22)

    def _build_game_panel(self, master: tk.Frame) -> None:
        panel = self._card(master, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT, padding=0)
        panel.place(x=0, y=0, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT)

        top = tk.Frame(panel, bg=Theme.PANEL)
        top.place(x=0, y=0, width=716, height=74)

        tk.Label(
            top, text="主队",
            bg=Theme.PANEL, fg=Theme.HOME,
            font=(Theme.FONT_CJK, 11, "bold"), anchor=tk.W,
        ).place(x=18, y=8, width=80, height=20)

        tk.Label(
            top, textvariable=self.score_var,
            bg=Theme.PANEL, fg=Theme.TEXT,
            font=(Theme.FONT, 27, "bold"), anchor=tk.CENTER,
        ).place(x=245, y=9, width=226, height=40)

        tk.Label(
            top, text="客队",
            bg=Theme.PANEL, fg=Theme.AWAY,
            font=(Theme.FONT_CJK, 11, "bold"), anchor=tk.E,
        ).place(x=618, y=8, width=80, height=20)

        tk.Label(
            top, textvariable=self.round_var,
            bg=Theme.ACCENT_SOFT, fg=Theme.ACCENT,
            font=(Theme.FONT_CJK, 9, "bold"), anchor=tk.CENTER,
        ).place(x=289, y=50, width=138, height=20)

        canvas_wrap = tk.Frame(panel, bg=Theme.CANVAS_BG)
        canvas_wrap.place(x=15, y=74, width=686, height=478)
        self.board_canvas = tk.Canvas(
            canvas_wrap, width=self.BOARD_WIDTH, height=self.BOARD_HEIGHT,
            bg=Theme.CANVAS_BG, bd=0, highlightthickness=0,
        )
        self.board_canvas.place(x=0, y=0, width=self.BOARD_WIDTH, height=self.BOARD_HEIGHT)

        footer = tk.Frame(
            panel, bg=Theme.PANEL_ALT,
            highlightthickness=1, highlightbackground=Theme.BORDER_SOFT,
        )
        footer.place(x=15, y=564, width=686, height=49)

        tk.Label(
            footer, text="比赛状态",
            bg=Theme.PANEL_ALT, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8), anchor=tk.W,
        ).place(x=10, y=5, width=70, height=16)
        tk.Label(
            footer, textvariable=self.status_var,
            bg=Theme.PANEL_ALT, fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 10, "bold"), anchor=tk.W,
        ).place(x=10, y=22, width=666, height=20)

    def _build_sidebar(self, master: tk.Frame) -> None:
        sidebar = tk.Frame(
            master, width=self.SIDEBAR_WIDTH, height=self.BODY_HEIGHT,
            bg=Theme.APP_BG,
        )
        sidebar.place(
            x=self.GAME_PANEL_WIDTH + self.PANEL_GAP,
            y=0, width=self.SIDEBAR_WIDTH, height=self.BODY_HEIGHT,
        )

        MetricTile(
            sidebar, "本局总下注", self.bet_var, Theme.CYAN,
            width=184, height=68,
        ).place(x=0, y=0, width=184, height=68)
        MetricTile(
            sidebar, "上局返还", self.last_win_var, Theme.GREEN,
            width=184, height=68,
        ).place(x=194, y=0, width=184, height=68)

        chips = self._card(sidebar, width=378, height=101)
        chips.place(x=0, y=76, width=378, height=101)
        self._section_title(chips.inner, "选择筹码").place(x=0, y=0, width=110, height=20)
        tk.Label(
            chips.inner, text="左加注 · 右清空 · 筹码=金额",
            bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 7), anchor=tk.E,
        ).place(x=145, y=1, width=177, height=18)

        for index, (label, amount, chip_color, text_color) in enumerate(CHIP_CONFIGS):
            chip = ChipButton(
                chips.inner,
                label=label, amount=amount,
                chip_color=chip_color, text_color=text_color,
                command=self.select_chip,
                width=49, height=50,
            )
            chip.place(x=index * 59, y=24, width=49, height=50)
            self.chip_buttons.append(chip)

        match_card = self._card(sidebar, width=378, height=88, padding=9)
        match_card.place(x=0, y=185, width=378, height=88)
        self._section_title(match_card.inner, "赛果").place(x=0, y=0, width=80, height=18)
        self._create_bet_row(
            match_card.inner,
            items=(
                ("home", "主胜", MATCH_ODDS["home"]),
                ("draw", "和局", MATCH_ODDS["draw"]),
                ("away", "客胜", MATCH_ODDS["away"]),
            ),
            y=22, cell_width=112, height=47, gap=8,
        )

        goals_card = self._card(sidebar, width=378, height=100, padding=9)
        goals_card.place(x=0, y=281, width=378, height=100)
        self._section_title(goals_card.inner, "总进球").place(x=0, y=0, width=90, height=18)
        self._create_bet_row(
            goals_card.inner,
            items=tuple(
                (f"goal:{opt}", opt, TOTAL_GOAL_ODDS[opt])
                for opt in TOTAL_GOAL_OPTIONS
            ),
            y=22, cell_width=55, height=56, gap=6,
        )

        ou_card = self._card(sidebar, width=378, height=92, padding=9)
        ou_card.place(x=0, y=389, width=378, height=92)
        self._section_title(ou_card.inner, "入球大小").place(x=0, y=0, width=100, height=18)
        self._create_bet_row(
            ou_card.inner,
            items=tuple(
                (f"ou:{key}", OVER_UNDER_LABELS[key], OVER_UNDER_ODDS[key])
                for key in OVER_UNDER_OPTIONS
            ),
            y=22, cell_width=84, height=48, gap=8,
        )

        actions = self._card(sidebar, width=378, height=91, padding=9)
        actions.place(x=0, y=489, width=378, height=91)

        self.reset_button = ModernButton(
            actions.inner, text="清空全部",
            command=self.reset_all_bets,
            background=Theme.RED, hover_background=Theme.RED_HOVER,
            foreground="#FFFFFF", font_size=11, bold=True,
        )
        self.reset_button.place(x=0, y=0, width=175, height=30)

        self.rules_button = ModernButton(
            actions.inner, text="赔率 / 规则",
            command=self.show_rules,
            background=Theme.PANEL_HOVER, hover_background=Theme.BORDER,
            foreground=Theme.TEXT, font_size=11, bold=True,
        )
        self.rules_button.place(x=185, y=0, width=175, height=30)

        self.start_button = ModernButton(
            actions.inner, text="开始比赛",
            command=self.primary_action,
            background=Theme.GREEN, hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF", font_size=12, bold=True,
        )
        self.start_button.place(x=0, y=38, width=360, height=34)

        limits = self._card(sidebar, width=378, height=42, padding=7)
        limits.place(x=0, y=588, width=378, height=42)
        tk.Label(
            limits.inner,
            text="每注 $10–$10,000   ·   总注最高 $100,000",
            bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8, "bold"), anchor=tk.CENTER,
        ).place(x=0, y=2, width=364, height=22)

    def _create_bet_row(
        self,
        master,
        *,
        items: tuple,
        y: int,
        cell_width: int,
        height: int,
        gap: int,
    ) -> None:
        for index, (key, label, odds) in enumerate(items):
            box = BetBox(
                master,
                key=key, label=label, odds=odds,
                on_add=self.add_bet, on_reset=self.reset_single_bet,
                width=cell_width, height=height,
            )
            box.place(
                x=index * (cell_width + gap),
                y=y,
                width=cell_width,
                height=height,
            )
            self.bet_boxes[key] = box

    # ------------------------------------------------------------------
    # Betting
    # ------------------------------------------------------------------

    def select_chip(self, amount: str) -> None:
        if self.match_in_progress or self.settlement_mode:
            return
        self.selected_chip = float(amount)
        for chip in self.chip_buttons:
            chip.set_selected(float(chip.amount) == self.selected_chip)
        self.status_var.set(f"已选择筹码 {money(self.selected_chip)}")

    def _bet_value(self, key: str) -> float:
        if key == "home":
            return self.bet_home
        if key == "draw":
            return self.bet_draw
        if key == "away":
            return self.bet_away
        if key.startswith("goal:"):
            return self.total_goal_bets[key.split(":", 1)[1]]
        if key.startswith("ou:"):
            return self.over_under_bets[key.split(":", 1)[1]]
        return 0.0

    def _set_bet_value(self, key: str, value: float) -> None:
        if key == "home":
            self.bet_home = value
        elif key == "draw":
            self.bet_draw = value
        elif key == "away":
            self.bet_away = value
        elif key.startswith("goal:"):
            self.total_goal_bets[key.split(":", 1)[1]] = value
        elif key.startswith("ou:"):
            self.over_under_bets[key.split(":", 1)[1]] = value

    def add_bet(self, key: str) -> None:
        if self.match_in_progress or self.settlement_mode:
            return

        chip = float(self.selected_chip)
        current = self._bet_value(key)
        new_value = current + chip

        if new_value > PER_BET_MAX:
            messagebox.showerror(
                "下注超限",
                "单个下注项最高 $10,000。",
                parent=self.root,
            )
            return

        total_after = self.calc_total_bet() + chip
        if total_after > TOTAL_BET_MAX:
            messagebox.showerror(
                "总下注超限",
                "每场总下注最高 $100,000。",
                parent=self.root,
            )
            return
        if total_after > self.balance:
            messagebox.showerror(
                "余额不足",
                "下注总额超过账户余额。",
                parent=self.root,
            )
            return

        self._set_bet_value(key, new_value)
        self.bet_boxes[key].set_amount(new_value)
        self.status_var.set("下注已更新；比赛开始后所有盘口会锁定")
        self.update_display()

    def reset_single_bet(self, key: str) -> None:
        if self.match_in_progress or self.settlement_mode:
            return
        self._set_bet_value(key, 0.0)
        self.bet_boxes[key].set_amount(0.0)
        self.update_display()

    def reset_all_bets(self) -> None:
        if self.match_in_progress or self.settlement_mode:
            return
        self.bet_home = self.bet_draw = self.bet_away = 0.0
        for opt in TOTAL_GOAL_OPTIONS:
            self.total_goal_bets[opt] = 0.0
        for key in OVER_UNDER_OPTIONS:
            self.over_under_bets[key] = 0.0
        for box in self.bet_boxes.values():
            box.set_amount(0.0)
            box.set_result("normal")
        self.status_var.set("所有下注已清空")
        self.update_display()

    def calc_total_bet(self) -> float:
        return (
            self.bet_home + self.bet_draw + self.bet_away
            + sum(self.total_goal_bets.values())
            + sum(self.over_under_bets.values())
        )

    def _set_betting_enabled(self, enabled: bool) -> None:
        for chip in self.chip_buttons:
            chip.set_enabled(enabled)
        for box in self.bet_boxes.values():
            box.set_enabled(enabled)
        self.reset_button.configure(state=tk.NORMAL if enabled else tk.DISABLED)

    # ------------------------------------------------------------------
    # Board / pure physics
    # ------------------------------------------------------------------

    def _bottom_bounds(self) -> tuple[float, float, float, float]:
        start_x = 80.0
        end_x = float(self.BOARD_WIDTH - 80)
        total = end_x - start_x
        return (
            start_x,
            start_x + total / 3,
            start_x + total * 2 / 3,
            end_x,
        )

    def _draw_field(self) -> None:
        c = self.board_canvas
        c.delete("all")
        w = self.BOARD_WIDTH
        h = self.BOARD_HEIGHT

        c.create_rectangle(0, 0, w, h, fill=Theme.FIELD, outline="")
        for y in range(0, h, 48):
            fill = Theme.FIELD if (y // 48) % 2 == 0 else Theme.FIELD_DARK
            c.create_rectangle(0, y, w, min(h, y + 48), fill=fill, outline="")

        # Football-pitch linework.
        c.create_rectangle(12, 12, w - 12, h - 12, outline=Theme.FIELD_LINE, width=2)
        c.create_line(w / 2, 12, w / 2, h - 12, fill=Theme.FIELD_LINE, width=1)
        c.create_oval(w / 2 - 48, h / 2 - 48, w / 2 + 48, h / 2 + 48,
                      outline=Theme.FIELD_LINE, width=1)

        top_y = 58
        bottom_y = h - 62
        top_w = 40
        bottom_w = w - 180
        c.create_polygon(
            w / 2 - top_w / 2, top_y,
            w / 2 + top_w / 2, top_y,
            w / 2 + bottom_w / 2, bottom_y,
            w / 2 - bottom_w / 2, bottom_y,
            fill=Theme.CANVAS_BG,
            outline=Theme.BORDER,
            width=2,
        )

        # Launch tunnel.
        c.create_rectangle(
            w / 2 - 42, 18, w / 2 + 42, 59,
            fill=Theme.PANEL_ALT, outline=Theme.BORDER, width=2,
        )
        c.create_text(
            w / 2 - 19, 38, text="●",
            fill=Theme.HOME, font=(Theme.FONT, 14, "bold"),
        )
        c.create_text(
            w / 2 + 19, 38, text="●",
            fill=Theme.AWAY, font=(Theme.FONT, 14, "bold"),
        )

        # Peg pyramid exactly follows the original row-count pattern.
        rows = 11
        pegs_per_row = (1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11)
        self.pegs = []

        for row in range(rows):
            progress = row / (rows - 1)
            cur_w = top_w + (bottom_w - top_w) * progress
            y = top_y + (bottom_y - top_y) * progress
            count = pegs_per_row[row]
            spacing = cur_w / (count + 1)
            for index in range(count):
                x = w / 2 - cur_w / 2 + spacing * (index + 1)
                self.pegs.append((x, y))
                c.create_oval(
                    x - 5, y - 5, x + 5, y + 5,
                    fill=Theme.PEG, outline=Theme.PEG_BORDER, width=1,
                )

        # Bottom scoring zones. The centre is the only goal zone.
        left, b1, b2, right = self._bottom_bounds()
        zone_y = h - 60
        zones = (
            (left, b1, Theme.NO_GOAL, "不入球"),
            (b1, b2, Theme.GOAL, "⚽ 入球区 ⚽"),
            (b2, right, Theme.NO_GOAL, "不入球"),
        )
        for x1, x2, fill, label in zones:
            c.create_rectangle(
                x1, zone_y, x2, h - 17,
                fill=fill, outline=Theme.BORDER, width=1,
            )
            c.create_text(
                (x1 + x2) / 2, zone_y + 21,
                text=label, fill=Theme.TEXT,
                font=(Theme.FONT_CJK, 9, "bold"),
            )

        # Score team markers.
        c.create_rectangle(
            17, 18, 135, 75,
            fill=Theme.HOME_SOFT, outline=Theme.HOME, width=2,
        )
        c.create_text(
            30, 33, text="主队", anchor=tk.W,
            fill=Theme.HOME, font=(Theme.FONT_CJK, 9, "bold"),
        )
        c.create_text(
            119, 52, text=str(self.home_score), anchor=tk.E,
            fill=Theme.HOME, font=(Theme.FONT, 24, "bold"),
        )

        c.create_rectangle(
            w - 135, 18, w - 17, 75,
            fill=Theme.AWAY_SOFT, outline=Theme.AWAY, width=2,
        )
        c.create_text(
            w - 30, 33, text="客队", anchor=tk.E,
            fill=Theme.AWAY, font=(Theme.FONT_CJK, 9, "bold"),
        )
        c.create_text(
            w - 119, 52, text=str(self.away_score), anchor=tk.W,
            fill=Theme.AWAY, font=(Theme.FONT, 24, "bold"),
        )

        now = time.monotonic()
        self.score_effects = [
            effect for effect in self.score_effects
            if now < effect["until"]
        ]
        for effect in self.score_effects:
            c.create_text(
                effect["x"], effect["y"],
                text=effect["text"], fill=effect["color"],
                font=(Theme.FONT_CJK, 11, "bold"),
            )

        for ball in self.balls:
            if ball.get("finished"):
                continue
            self._draw_ball(ball)

    def _draw_ball(self, ball: dict) -> None:
        c = self.board_canvas
        x = ball["x"]
        y = ball["y"]
        color = Theme.HOME if ball["team"] == "home" else Theme.AWAY

        c.create_oval(
            x - 9, y - 9, x + 9, y + 9,
            fill="#F3F0E9", outline=color, width=3,
        )
        c.create_polygon(
            x, y - 5,
            x + 5, y - 1,
            x + 3, y + 5,
            x - 3, y + 5,
            x - 5, y - 1,
            fill=color, outline="",
        )

    def draw_board(self) -> None:
        self._draw_field()

    def launch_round(self) -> None:
        if self.current_round >= self.ROUNDS_TOTAL:
            return

        self.current_round += 1
        self.balls_in_round = 0

        start_x = self.BOARD_WIDTH / 2
        start_y = 60.0
        now = time.monotonic()

        self.balls.extend([
            {
                "x": start_x + random.uniform(-5, 5),
                "y": start_y,
                "vx": random.uniform(-0.5, 0.5),
                "vy": 0.0,
                "finished": False,
                "team": "home",
                "last_move_time": now,
                "last_x": start_x,
                "last_y": start_y,
                "launch_time": now,
            },
            {
                "x": start_x + random.uniform(-5, 5),
                "y": start_y,
                "vx": random.uniform(-0.5, 0.5),
                "vy": 0.0,
                "finished": False,
                "team": "away",
                "last_move_time": now,
                "last_x": start_x,
                "last_y": start_y,
                "launch_time": now,
            },
        ])

        self.active_balls = len(self.balls)
        self.status_var.set(f"第 {self.current_round} 轮：主队与客队弹珠正在下落")
        self.update_display()

    def determine_region(self, x: float) -> str:
        left, b1, b2, right = self._bottom_bounds()
        if x < b1:
            return "left"
        if x < b2:
            return "goal"
        return "right"

    def update_ball_position(self, ball: dict) -> None:
        """Original-style pure physical collision model; no hidden target."""
        if ball["finished"]:
            return

        now = time.monotonic()
        flight_age = now - float(ball.get("launch_time", now))

        # Normal motion uses the original gravity.  For unusually long-lived
        # rebounds, only the downward force is increased; X is never targeted.
        extra_gravity = 0.0
        if flight_age > 1.6:
            extra_gravity = min(0.90, (flight_age - 1.6) * 0.24)

        ball["vy"] += self.gravity + extra_gravity
        if flight_age > 2.0 and ball["vy"] < -1.5:
            ball["vy"] *= 0.62

        new_x = ball["x"] + ball["vx"]
        new_y = ball["y"] + ball["vy"]

        top_y = 60.0
        bottom_y = float(self.BOARD_HEIGHT - 60)
        radius = 8.0

        left, _, _, right = self._bottom_bounds()
        min_x = left + radius
        max_x = right - radius

        progress = (
            max(0.0, min(1.0, (new_y - top_y) / (bottom_y - top_y)))
            if bottom_y > top_y else 0.0
        )
        top_w = 40.0
        bottom_w = float(self.BOARD_WIDTH - 180)
        cur_w = top_w + (bottom_w - top_w) * progress

        center_min_x = self.BOARD_WIDTH / 2 - cur_w / 2 + radius
        center_max_x = self.BOARD_WIDTH / 2 + cur_w / 2 - radius

        min_x = max(min_x, center_min_x)
        max_x = min(max_x, center_max_x)

        if new_x < min_x:
            new_x = min_x
            ball["vx"] = -ball["vx"] * self.damping
        elif new_x > max_x:
            new_x = max_x
            ball["vx"] = -ball["vx"] * self.damping

        # Peg collision.  After an exceptionally long 3.0 s rebound cycle,
        # accept no NEW peg impacts and let gravity finish the current path.
        # Horizontal position and velocity are left untouched: no goal steering.
        allow_peg_collisions = flight_age <= 3.0
        for px, py in self.pegs:
            if not allow_peg_collisions:
                break
            dx = new_x - px
            dy = new_y - py
            dist = math.hypot(dx, dy)

            if dist < radius + 5:
                if dist <= 1e-8:
                    continue

                nx = dx / dist
                ny = dy / dist
                dot = ball["vx"] * nx + ball["vy"] * ny

                ball["vx"] -= 2 * dot * nx
                ball["vy"] -= 2 * dot * ny
                ball["vx"] *= self.damping
                ball["vy"] *= self.damping

                overlap = (radius + 5) - dist
                new_x += nx * overlap * 1.1
                new_y += ny * overlap * 1.1

                # This random nudge is part of the original physical model.
                ball["vx"] += random.uniform(-0.3, 0.3)

        # Original stuck-ball recovery: after 5 s of almost no movement, kick it
        # upward/sideways. This does NOT decide or steer the final result.
        moved = math.hypot(
            new_x - ball["last_x"],
            new_y - ball["last_y"],
        )

        if moved > 0.35:
            ball["last_move_time"] = now
            ball["last_x"] = new_x
            ball["last_y"] = new_y
        elif now - ball["last_move_time"] >= 5.0:
            new_y = max(top_y + radius + 1, new_y - 12)
            new_x += random.uniform(-1.0, 1.0)
            ball["vy"] = -abs(ball["vy"]) * 0.6 - random.uniform(0.8, 1.5)
            ball["vx"] = random.uniform(-1.2, 1.2)
            new_x = max(min_x, min(max_x, new_x))

            ball["last_move_time"] = now
            ball["last_x"] = new_x
            ball["last_y"] = new_y

        ball["x"] = new_x
        ball["y"] = new_y

        if new_y >= bottom_y - radius:
            ball["finished"] = True
            ball["y"] = bottom_y - radius
            region = self.determine_region(new_x)

            if region == "goal":
                if ball["team"] == "home":
                    self.home_score += 1
                    self._add_score_effect(new_x, bottom_y - 28, "主队 +1", Theme.HOME)
                else:
                    self.away_score += 1
                    self._add_score_effect(new_x, bottom_y - 28, "客队 +1", Theme.AWAY)
            else:
                self._add_score_effect(new_x, bottom_y - 28, "不得分", Theme.TEXT_MUTED)

    def _add_score_effect(self, x: float, y: float, text: str, color: str) -> None:
        self.score_effects.append({
            "x": x,
            "y": y,
            "text": text,
            "color": color,
            "until": time.monotonic() + 1.2,
        })

    def animate_balls(self) -> None:
        if not self.match_in_progress and not self.balls:
            self.animation_running = False
            return

        finished_indices: list[int] = []
        for index, ball in enumerate(self.balls):
            if not ball["finished"]:
                self.update_ball_position(ball)
                if ball["finished"]:
                    finished_indices.append(index)

        self.draw_board()

        if finished_indices:
            for index in sorted(finished_indices, reverse=True):
                self.balls.pop(index)

            self.balls_in_round += len(finished_indices)
            self.active_balls = len(self.balls)
            self.update_display()

            if self.balls_in_round >= 2 and self.current_round < self.ROUNDS_TOTAL:
                self.launch_round()
            elif self.current_round >= self.ROUNDS_TOTAL and self.active_balls == 0:
                self.finish_match()
                return

        if any(not ball["finished"] for ball in self.balls):
            self.after_id = self.root.after(30, self.animate_balls)
        else:
            self.animation_running = False

    # ------------------------------------------------------------------
    # Match flow / settlement
    # ------------------------------------------------------------------

    def primary_action(self) -> None:
        if self.settlement_mode:
            self.play_again()
        else:
            self.start_match()

    def start_match(self) -> None:
        if self.match_in_progress:
            return

        total_bet = self.calc_total_bet()
        if total_bet > self.balance:
            messagebox.showerror("余额不足", "下注总额超过账户余额。", parent=self.root)
            return

        if self.animation_running and self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None

        self.balls.clear()
        self.active_balls = 0
        self.score_effects.clear()

        for box in self.bet_boxes.values():
            box.set_result("normal")

        self.balance -= total_bet
        update_balance_in_json(self.username, self.balance)

        self.match_in_progress = True
        self.settlement_mode = False
        self.home_score = 0
        self.away_score = 0
        self.current_round = 0
        self.balls_in_round = 0
        self.balls.clear()
        self.active_balls = 0

        self._set_betting_enabled(False)
        self.start_button.configure(state=tk.DISABLED)
        self.status_var.set("比赛开始 · 结果完全由弹珠物理碰撞产生")
        self.animation_running = True
        self.launch_round()
        self.after_id = self.root.after(30, self.animate_balls)
        self.update_display()

    def _is_total_goal_win(self, option: str, goals: int) -> bool:
        if option == "0/1":
            return goals in (0, 1)
        if option == "6+":
            return goals >= 6
        return goals == int(option)

    def _is_ou_win(self, key: str, goals: int) -> bool:
        if key == "under4.5":
            return goals <= 4
        if key == "over4.5":
            return goals >= 5
        if key == "under3.5":
            return goals <= 3
        if key == "over3.5":
            return goals >= 4
        return False

    def finish_match(self) -> None:
        self.match_in_progress = False
        self.animation_running = False
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None

        if self.home_score > self.away_score:
            result = "home"
            result_text = "主队获胜"
        elif self.home_score < self.away_score:
            result = "away"
            result_text = "客队获胜"
        else:
            result = "draw"
            result_text = "和局"

        win_amount = 0.0

        # ------------------------------------------------------------------
        # Settlement presentation
        # ------------------------------------------------------------------
        # Each betting cell used to keep showing the original stake.
        # R2 replaces that stake chip with this cell's ACTUAL RETURN.
        #
        # return > 0  -> chip remains and its centre changes to return amount
        # return == 0 -> chip is removed from the cell
        # ------------------------------------------------------------------
        match_bets = {
            "home": self.bet_home,
            "draw": self.bet_draw,
            "away": self.bet_away,
        }

        for key, bet in match_bets.items():
            won = key == result
            returned = bet * MATCH_ODDS[key] if won and bet > 0 else 0.0
            win_amount += returned

            box = self.bet_boxes[key]
            box.set_result("win" if won else "lose")
            box.set_amount(returned)

        total_goals = self.home_score + self.away_score

        for option in TOTAL_GOAL_OPTIONS:
            bet = self.total_goal_bets[option]
            won = self._is_total_goal_win(option, total_goals)
            returned = bet * TOTAL_GOAL_ODDS[option] if won and bet > 0 else 0.0
            win_amount += returned

            box = self.bet_boxes[f"goal:{option}"]
            box.set_result("win" if won else "lose")
            box.set_amount(returned)

        for key in OVER_UNDER_OPTIONS:
            bet = self.over_under_bets[key]
            won = self._is_ou_win(key, total_goals)
            returned = bet * OVER_UNDER_ODDS[key] if won and bet > 0 else 0.0
            win_amount += returned

            box = self.bet_boxes[f"ou:{key}"]
            box.set_result("win" if won else "lose")
            box.set_amount(returned)

        self.balance += win_amount
        self.last_win = win_amount
        update_balance_in_json(self.username, self.balance)

        # Preserve the original data flow: once settlement completes, the
        # player's stake variables are cleared. The BetBox objects intentionally
        # keep their settlement return chips until "再来一局" is pressed.
        self.bet_home = self.bet_draw = self.bet_away = 0.0
        for option in TOTAL_GOAL_OPTIONS:
            self.total_goal_bets[option] = 0.0
        for key in OVER_UNDER_OPTIONS:
            self.over_under_bets[key] = 0.0

        self.settlement_mode = True
        self._set_betting_enabled(False)

        self.start_button.configure(
            text="再来一局",
            state=tk.NORMAL,
        )
        self.start_button.set_colors(
            Theme.ACCENT,
            Theme.ACCENT_HOVER,
            "#FFFFFF",
        )

        self.status_var.set(
            f"比赛结束 · {self.home_score}:{self.away_score} · "
            f"{result_text} · 总进球 {total_goals} · 返还 {money(win_amount)}"
        )
        self.update_display()

    def play_again(self) -> None:
        if self.animation_running and self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
        self.after_id = None
        self.animation_running = False
        self.balls.clear()
        self.active_balls = 0
        self.score_effects.clear()

        self.home_score = 0
        self.away_score = 0
        self.current_round = 0
        self.balls_in_round = 0
        self.settlement_mode = False

        for box in self.bet_boxes.values():
            box.set_amount(0.0)
            box.set_result("normal")

        self.start_button.configure(text="开始比赛")
        self.start_button.set_colors(
            Theme.GREEN, Theme.GREEN_HOVER, "#FFFFFF"
        )
        self._set_betting_enabled(True)
        self.status_var.set("请选择筹码并点击盘口下注")
        self.update_display()

    # ------------------------------------------------------------------
    # Display / rules
    # ------------------------------------------------------------------

    def update_display(self) -> None:
        self.balance_var.set(money(self.balance))
        self.bet_var.set(money(self.calc_total_bet()))
        self.last_win_var.set(money(self.last_win))
        self.round_var.set(f"第 {self.current_round} / {self.ROUNDS_TOTAL} 轮")
        self.score_var.set(f"{self.home_score}  :  {self.away_score}")

        # During live betting, chips mirror the current stake variables.
        # During settlement, finish_match() has already replaced those chips
        # with each market's actual return; do not overwrite them with the
        # cleared stake variables.
        if not self.settlement_mode:
            for key, box in self.bet_boxes.items():
                box.set_amount(self._bet_value(key))

        for chip in self.chip_buttons:
            chip.set_selected(float(chip.amount) == self.selected_chip)

        if not self.match_in_progress and not self.settlement_mode:
            self.start_button.configure(state=tk.NORMAL)

        self.draw_board()

    def show_rules(self) -> None:
        top = tk.Toplevel(self.root)
        top.title("足球弹珠 · 赔率与规则")
        top.geometry("700x610+130+70")
        top.resizable(False, False)
        top.configure(bg=Theme.APP_BG)
        top.transient(self.root if isinstance(self.root, (tk.Tk, tk.Toplevel)) else None)

        panel = tk.Frame(
            top, bg=Theme.PANEL,
            highlightthickness=1, highlightbackground=Theme.BORDER_SOFT,
        )
        panel.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        tk.Label(
            panel, text="FOOTBALL MATCH · 赔率与规则",
            bg=Theme.PANEL, fg=Theme.TEXT,
            font=(Theme.FONT, 16, "bold"), anchor=tk.W,
        ).pack(fill=tk.X, padx=18, pady=(16, 4))
        tk.Label(
            panel,
            text=(
                "每场共 5 轮，每轮一颗主队球和一颗客队球。"
                "只有弹珠物理落入底部中央入球区时，该球队才 +1。"
                "所有盘口独立结算。"
            ),
            bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9),
            justify=tk.LEFT, wraplength=620,
        ).pack(fill=tk.X, padx=18, pady=(0, 12))

        sections = [
            (
                "赛果",
                [("主胜", "2.60×"), ("和局", "3.15×"), ("客胜", "2.60×")],
            ),
            (
                "总进球",
                [(opt, f"{TOTAL_GOAL_ODDS[opt]:.2f}×") for opt in TOTAL_GOAL_OPTIONS],
            ),
            (
                "入球大小",
                [
                    ("小3.5（≤3）", "2.50×"),
                    ("大3.5（≥4）", "1.50×"),
                    ("小4.5（≤4）", "1.60×"),
                    ("大4.5（≥5）", "2.15×"),
                ],
            ),
        ]

        for title, rows in sections:
            tk.Label(
                panel, text=title, bg=Theme.PANEL_ALT, fg=Theme.TEXT,
                font=(Theme.FONT_CJK, 11, "bold"), anchor=tk.W,
            ).pack(fill=tk.X, padx=18, pady=(5, 0), ipady=5)

            table = tk.Frame(panel, bg=Theme.BORDER_SOFT)
            table.pack(fill=tk.X, padx=18, pady=(0, 8))
            for row_index, (name, odd) in enumerate(rows):
                tk.Label(
                    table, text=name,
                    bg=Theme.PANEL if row_index % 2 == 0 else Theme.PANEL_ALT,
                    fg=Theme.TEXT, font=(Theme.FONT_CJK, 9),
                    anchor=tk.W,
                ).grid(row=row_index, column=0, sticky="nsew", padx=(1, 0), pady=(1, 0), ipadx=8, ipady=4)
                tk.Label(
                    table, text=odd,
                    bg=Theme.PANEL if row_index % 2 == 0 else Theme.PANEL_ALT,
                    fg=Theme.ACCENT, font=(Theme.FONT, 9, "bold"),
                    anchor=tk.E,
                ).grid(row=row_index, column=1, sticky="nsew", padx=(1, 1), pady=(1, 0), ipadx=8, ipady=4)
            table.columnconfigure(0, weight=1)
            table.columnconfigure(1, weight=1)

        tk.Label(
            panel,
            text=(
                "操作：先选择筹码；左键点击盘口增加筹码，右键清空该盘口。"
                "单项最高 $10,000，全场总下注最高 $100,000。"
            ),
            bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9), justify=tk.LEFT, wraplength=620,
        ).pack(fill=tk.X, padx=18, pady=(8, 10))

        ModernButton(
            panel, text="关闭", command=top.destroy,
            background=Theme.ACCENT, hover_background=Theme.ACCENT_HOVER,
            foreground="#FFFFFF", font_size=11, bold=True,
        ).pack(pady=(0, 14), ipadx=24, ipady=3)

    # ------------------------------------------------------------------
    # Closing / embedded entry point
    # ------------------------------------------------------------------

    def on_close(self) -> None:
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
                "EmbeddedGamePage is unavailable. Place Football_Match.py inside "
                "the Small_Games package or make small_games.py importable."
            )
        page = EmbeddedGamePage(
            parent,
            title="足球弹珠",
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        page.set_requested_size(1150, 750)
        game = FootballPachinko(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = FootballPachinko(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    final_balance = main(10000.0, "test_user")
    print(f"Final balance: {final_balance:.2f}")