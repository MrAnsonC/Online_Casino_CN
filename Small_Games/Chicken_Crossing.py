"""Chicken Crossing HMI R6 — fixed danger pool and live-risk edition.

The visual layout remains the warm fixed-size HMI from R5.  Gameplay now uses
a 25-element danger pool without replacement, a live next-step risk display,
and the reduced 7% single-item system with temporary +1x and Speed +1 only.
"""

from __future__ import annotations

import json
import os
import random
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

try:
    from .small_games import EmbeddedGamePage
except ImportError:  # Allow the module to run directly inside the original project.
    from small_games import EmbeddedGamePage


# ---------------------------------------------------------------------------
# Theme and immutable game configuration
# ---------------------------------------------------------------------------

class Theme:
    """Centralised visual tokens for a warm, refined, low-glare HMI."""

    # Warm mineral surfaces: neither paper-white nor visually oppressive black.
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

    # Cartoon-road palette.
    SKY = "#AFCAD4"
    GRASS = "#79A66A"
    GRASS_DARK = "#5D8A52"
    SOIL = "#B58B5D"
    SIDEWALK = "#D7C9AF"
    CURB_LIGHT = "#F0E5CF"
    CURB_DARK = "#D06A5F"
    ROAD = "#4B5058"
    ROAD_EDGE = "#343940"
    ROAD_PATCH = "#5A6068"
    ROAD_LINE = "#F4D35E"
    ROAD_WHITE = "#F2F0E9"

    COMPLETED = "#A9C4A5"
    COMPLETED_BORDER = "#4D7D52"
    ACTIVE = "#B7CCD5"
    ACTIVE_BORDER = "#345E73"
    UPCOMING = "#D6D0C7"
    UPCOMING_BORDER = "#AAA196"

    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )
    FONT_EMOJI = "Segoe UI Emoji"


DIFFICULTY_SETTINGS = {
    "1": {
        "death_rate": 1 / 25,
        "multipliers": [
            1.00, 1.01, 1.04, 1.09, 1.14, 1.20, 1.26, 1.33, 1.41, 1.50,
            1.60, 1.71, 1.85, 2.00, 2.18, 2.40, 2.67, 3.00, 3.43, 4.00,
            4.80, 6.00, 8.00, 12.00, 24.00,
        ],
    },
    "2": {
        "death_rate": 3 / 25,
        "multipliers": [
            1, 1.09, 1.25, 1.43, 1.66, 1.94, 2.28, 2.71, 3.25, 3.94,
            4.85, 6.07, 7.72, 10.04, 13.28, 18.40, 26.29, 39.43, 63.09,
            110.40, 220.80, 552.00, 2208.00,
        ],
    },
    "3": {
        "death_rate": 5 / 25,
        "multipliers": [
            1, 1.20, 1.52, 1.94, 2.51, 3.29, 4.39, 5.95, 8.24, 11.68,
            16.98, 25.48, 39.63, 64.40, 110.40, 202.40, 404.80, 910.80,
            2428.00, 8500.00, 51004.80,
        ],
    },
    "4": {
        "death_rate": 10 / 25,
        "multipliers": [
            1, 1.60, 2.74, 4.85, 8.90, 16.98, 33.67, 71.71, 161.35,
            391.86, 1044.96, 3134.87, 10972.06, 47545.60, 285273.60,
            3138009.60,
        ],
    },
}

DIFFICULTIES = (
    ("简单", "1", "4% 风险"),
    ("中等", "2", "12% 风险"),
    ("困难", "3", "20% 风险"),
    ("地狱", "4", "40% 风险"),
)

# label, amount, chip colour, label colour
CHIP_CONFIGS = (
    ("$10", "10", "#ffa500", "black"),
    ("$25", "25", "#00ff00", "black"),
    ("$100", "100", "#000000", "white"),
    ("$500", "500", "#FF7DDA", "black"),
    ("$1K", "1000", "#ffffff", "black"),
    ("$2.5K", "2500", "#ff0000", "white"),
)

# Fixed danger pool.  The multiplier tables are based on a 25-element pool.
TOTAL_POOL_CELLS = 25
DANGER_COUNTS = {
    "1": 1,
    "2": 3,
    "3": 5,
    "4": 10,
}

# Per round: 93% no item, 7% exactly one item.
ITEM_ROUND_RATE = 0.07

# Item identifiers, display labels and icons.
ITEM_DEFINITIONS = {
    "bonus_1": {"name": "临时+1倍率", "icon": "+1×", "color": "#8D5AA8"},
    "speed_1": {"name": "加速+1", "icon": "➕1", "color": "#E5A93D"},
}

# Easy/medium: 80% temporary +1x, 20% speed+1.
# Hard/hell:   90% temporary +1x, 10% speed+1.
ITEM_WEIGHTS_BY_DIFFICULTY = {
    "1": {"bonus_1": 80, "speed_1": 20},
    "2": {"bonus_1": 80, "speed_1": 20},
    "3": {"bonus_1": 90, "speed_1": 10},
    "4": {"bonus_1": 90, "speed_1": 10},
}


# ---------------------------------------------------------------------------
# Persistence helpers — same data format and update behaviour as before
# ---------------------------------------------------------------------------


def get_data_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../saving_data.json")


def save_user_data(users) -> None:
    file_path = get_data_file_path()
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(users, file, ensure_ascii=False, indent=4)


def load_user_data():
    file_path = get_data_file_path()
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def update_balance_in_json(username: str, new_balance: float) -> None:
    users = load_user_data()
    for user in users:
        if user["user_name"] == username:
            user["cash"] = f"{new_balance:.2f}"
            break
    save_user_data(users)


# ---------------------------------------------------------------------------
# Reusable UI controls
# ---------------------------------------------------------------------------


class ModernButton(tk.Button):
    """Flat button with consistent hover and disabled behaviour."""

    def __init__(
        self,
        master,
        *,
        text: str,
        command: Optional[Callable[[], None]] = None,
        background: str = Theme.PANEL_HOVER,
        hover_background: str = Theme.BORDER,
        foreground: str = Theme.TEXT,
        font_size: int = 10,
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
    """Fixed-size poker chip with tactile press, hover and click feedback."""

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
        self._flash = False
        self._flash_job = None

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Key-space>", self._on_keyboard_activate)
        self.bind("<Return>", self._on_keyboard_activate)
        self.draw()

    @staticmethod
    def _shade(hex_color: str, factor: float) -> str:
        if not hex_color.startswith("#") or len(hex_color) != 7:
            return "#4A4A4A"
        rgb = [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]
        rgb = [max(0, min(255, round(channel * factor))) for channel in rgb]
        return "#%02x%02x%02x" % tuple(rgb)

    def draw(self) -> None:
        self.delete("all")
        offset_y = 3 if self._pressed else 0
        disabled = self._state == tk.DISABLED
        outer = self._shade(self.chip_color, 0.68)
        inner = self._shade(self.chip_color, 0.86)
        outline = Theme.ACCENT if self._flash else (Theme.TEXT if self._hovered else outer)
        outline_width = 3 if (self._flash or self._hovered) else 2

        # Ground shadow and stacked-chip edge create a physical press response.
        self.create_oval(5, 7, self.control_width - 4, self.control_height - 1,
                         fill="#8E877E", outline="")
        self.create_oval(4, 3 + offset_y, self.control_width - 5,
                         self.control_height - 5 + offset_y,
                         fill=outer, outline=outline, width=outline_width)
        self.create_oval(8, 7 + offset_y, self.control_width - 9,
                         self.control_height - 9 + offset_y,
                         fill=self.chip_color, outline=inner, width=2)
        self.create_oval(13, 12 + offset_y, self.control_width - 14,
                         self.control_height - 14 + offset_y,
                         fill=self.chip_color, outline=outer, width=1)

        # Casino-style edge inserts.
        cx = self.control_width / 2
        cy = (self.control_height - 2) / 2 + offset_y
        insert_color = self.text_color
        inserts = (
            (cx - 3, 4 + offset_y, cx + 3, 10 + offset_y),
            (cx - 3, self.control_height - 12 + offset_y, cx + 3,
             self.control_height - 6 + offset_y),
            (5, cy - 3, 11, cy + 3),
            (self.control_width - 12, cy - 3, self.control_width - 6, cy + 3),
        )
        for x1, y1, x2, y2 in inserts:
            self.create_rectangle(x1, y1, x2, y2, fill=insert_color, outline="")

        self.create_text(
            cx,
            cy,
            text=self.label,
            fill=self.text_color,
            font=(Theme.FONT, 8 if len(self.label) <= 4 else 7, "bold"),
        )

        if disabled:
            # A stippled cover keeps the chip visible while clearly locking it.
            # Tk does not support per-widget alpha, so stipple is used as the
            # transparent-cover equivalent without replacing the chip artwork.
            self.create_oval(4, 3 + offset_y, self.control_width - 5,
                             self.control_height - 5 + offset_y,
                             fill="#C9C2B8", outline=Theme.BORDER_SOFT,
                             width=1, stipple="gray50")
            self.create_line(13, 13 + offset_y,
                             self.control_width - 14, self.control_height - 14 + offset_y,
                             fill="#F3EEE6", width=2, stipple="gray50")

    def _on_enter(self, _event) -> None:
        if self._state != tk.DISABLED:
            self._hovered = True
            self.draw()

    def _on_leave(self, _event) -> None:
        self._hovered = False
        if self._pressed:
            self._pressed = False
        self.draw()

    def _on_press(self, _event) -> None:
        if self._state == tk.DISABLED:
            return
        self.focus_set()
        self._pressed = True
        self.draw()

    def _on_release(self, event) -> None:
        if self._state == tk.DISABLED:
            return
        was_pressed = self._pressed
        self._pressed = False
        inside = 0 <= event.x < self.control_width and 0 <= event.y < self.control_height
        if was_pressed and inside:
            self._activate()
        else:
            self.draw()

    def _on_keyboard_activate(self, _event) -> str:
        if self._state != tk.DISABLED:
            self._activate()
        return "break"

    def _activate(self) -> None:
        self._flash = True
        self.draw()
        self.command(self.amount)
        if self._flash_job is not None:
            try:
                self.after_cancel(self._flash_job)
            except tk.TclError:
                pass
        self._flash_job = self.after(150, self._clear_flash)

    def _clear_flash(self) -> None:
        self._flash = False
        self._flash_job = None
        self.draw()

    def configure(self, cnf=None, **kwargs):
        state = kwargs.pop("state", None)
        if state is not None:
            self._state = state
            if state == tk.DISABLED:
                self._hovered = False
                self._pressed = False
                self._flash = False
                if self._flash_job is not None:
                    try:
                        self.after_cancel(self._flash_job)
                    except tk.TclError:
                        pass
                    self._flash_job = None
            super().configure(cursor="" if state == tk.DISABLED else "hand2")
            self.draw()
        if cnf is not None or kwargs:
            return super().configure(cnf, **kwargs)
        return None

    config = configure


class MetricTile(tk.Frame):
    """Fixed-size label/value block used in the summary strip."""

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


class ChickenCrossingGame:
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
    ACTION_BUTTON_WIDTH = 322
    ACTION_BUTTON_HEIGHT = 38

    BOARD_CELL_WIDTH = 124
    BOARD_CELL_HEIGHT = 470
    BOARD_START_X = 42
    BOARD_START_Y = 24
    ROAD_TOP_OFFSET = 116
    ROAD_BOTTOM_OFFSET = 390
    CHICKEN_Y_OFFSET = 252

    def __init__(self, root, initial_balance, username):
        self.root = root
        self._configure_root()

        # Game state — deliberately kept equivalent to the original version.
        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0
        self.difficulty = "1"
        self.current_stage = 0
        self.game_active = False
        self.last_win = 0.0
        self.current_bet = 0.0
        self.animation_in_progress = False
        self.car_animation_step = 0
        self.collision_triggered = False
        self.collision_camera_position = None
        self.chicken_animation_id = None
        self.chicken_animation_steps = []
        self.difficulty_settings = DIFFICULTY_SETTINGS

        # Per-round item and effect state.
        self.round_items = {}  # 0-based stage index -> item identifier
        self.collected_item_stages = set()
        self.safe_bonus_steps_remaining = 0
        self.effect_in_progress = False
        self.round_original_bet = 0.0
        self.temporary_multiplier_bonus = 0.0
        self.notice_message = ""
        self.notice_clear_job = None

        # Fixed danger-pool state.  A normal safe step removes one safe element;
        # a speed step also removes one guaranteed-safe element.
        self.remaining_cells = TOTAL_POOL_CELLS
        self.remaining_dangers = DANGER_COUNTS[self.difficulty]

        # Widget references used by both the view and existing game flow.
        self.chip_buttons = []
        self.difficulty_buttons = []

        self.create_widgets()
        self.update_display()

    # ------------------------------------------------------------------
    # Window and theme setup
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title(f"小鸡过马路")
            self.root.geometry("1150x750+50+10")
            self.root.resizable(False, False)
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        else:
            # Embedded mode still receives a fixed logical viewport.
            self.root.configure(width=self.WINDOW_WIDTH, height=self.WINDOW_HEIGHT)
            try:
                self.root.pack_propagate(False)
                self.root.grid_propagate(False)
            except tk.TclError:
                pass

        self.root.configure(bg=Theme.APP_BG)

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Modern.Horizontal.TScrollbar",
            background=Theme.BORDER,
            troughcolor=Theme.PANEL_ALT,
            bordercolor=Theme.BORDER_SOFT,
            arrowcolor=Theme.TEXT_MUTED,
            lightcolor=Theme.BORDER,
            darkcolor=Theme.BORDER,
        )

    @staticmethod
    def _card(master, *, width: int, height: int, padding: int = 12) -> tk.Frame:
        """Create a card whose outer and inner dimensions never propagate."""
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

        inner_width = max(1, width - 2 * (padding + 1))
        inner_height = max(1, height - 2 * (padding + 1))
        inner = tk.Frame(
            outer,
            width=inner_width,
            height=inner_height,
            bg=Theme.PANEL,
        )
        inner.place(x=padding + 1, y=padding + 1, width=inner_width, height=inner_height)
        inner.pack_propagate(False)
        inner.grid_propagate(False)
        outer.content = inner  # type: ignore[attr-defined]
        return outer

    @staticmethod
    def _section_title(
        master,
        title: str,
        subtitle: str = "",
        *,
        width: int,
        x: int = 0,
        y: int = 0,
    ) -> None:
        tk.Label(
            master,
            text=title,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 16, "bold"),
            anchor=tk.W,
        ).place(x=x, y=y, width=width, height=22)
        if subtitle:
            tk.Label(
                master,
                text=subtitle,
                bg=Theme.PANEL,
                fg=Theme.TEXT_MUTED,
                font=(Theme.FONT_CJK, 8),
                anchor=tk.W,
            ).place(x=x, y=y + 22, width=width, height=17)

    # ------------------------------------------------------------------
    # UI construction: every region has an explicit pixel size.
    # ------------------------------------------------------------------

    def create_widgets(self):
        self.balance_var = tk.StringVar(value=f"${self.balance:.2f}")
        self.bet_var = tk.StringVar(value="$0.00")
        self.last_win_var = tk.StringVar(value="$0.00")
        self.stage_var = tk.StringVar(value="待开始")
        self.potential_var = tk.StringVar(value="$0.00")
        self.risk_var = tk.StringVar(value="4% / 次")
        self.info_var = tk.StringVar(value="选择下注金额与难度，然后开始挑战。")

        shell = tk.Frame(
            self.root,
            width=self.SHELL_WIDTH,
            height=self.SHELL_HEIGHT,
            bg=Theme.APP_BG,
        )
        shell.pack(padx=20, pady=18)
        shell.pack_propagate(False)
        shell.grid_propagate(False)

        self._build_header(shell)

        body = tk.Frame(
            shell,
            width=self.SHELL_WIDTH,
            height=self.BODY_HEIGHT,
            bg=Theme.APP_BG,
        )
        body.place(x=0, y=self.BODY_TOP, width=self.SHELL_WIDTH, height=self.BODY_HEIGHT)
        body.pack_propagate(False)
        body.grid_propagate(False)

        self._build_game_panel(body)
        self._build_control_panel(body)

    def _build_header(self, master) -> None:
        header = tk.Frame(
            master,
            width=self.SHELL_WIDTH,
            height=self.HEADER_HEIGHT,
            bg=Theme.APP_BG,
        )
        header.place(x=0, y=0, width=self.SHELL_WIDTH, height=self.HEADER_HEIGHT)
        header.pack_propagate(False)
        header.grid_propagate(False)

        tk.Label(
            header,
            text="🐥",
            bg=Theme.APP_BG,
            fg=Theme.AMBER,
            font=(Theme.FONT_EMOJI, 27),
            anchor=tk.CENTER,
        ).place(x=0, y=7, width=42, height=44)
        tk.Label(
            header,
            text="CHICKEN CROSSING",
            bg=Theme.APP_BG,
            fg=Theme.TEXT,
            font=(Theme.FONT, 20, "bold"),
            anchor=tk.W,
        ).place(x=52, y=4, width=430, height=31)
        tk.Label(
            header,
            text="小鸡过马路",
            bg=Theme.APP_BG,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 10),
            anchor=tk.W,
        ).place(x=52, y=37, width=520, height=22)

        balance_box = tk.Frame(
            header,
            width=230,
            height=54,
            bg=Theme.PANEL,
            highlightthickness=1,
            highlightbackground=Theme.BORDER,
        )
        balance_box.place(x=880, y=8, width=270, height=54)
        balance_box.pack_propagate(False)

        # 将标题和余额合并为一个动态文本变量
        self.balance_display_var = tk.StringVar(
            value=f"账户余额: {self.balance_var.get()}"
        )

        def update_balance_display(*_):
            self.balance_display_var.set(
                f"账户余额: {self.balance_var.get()}"
            )

        self.balance_var.trace_add("write", update_balance_display)

        tk.Label(
            balance_box,
            textvariable=self.balance_display_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 13, "bold"),
            anchor=tk.E,
        ).place(x=0, y=8, width=160, height=40)

    def _build_game_panel(self, master) -> None:
        panel = self._card(
            master,
            width=self.GAME_PANEL_WIDTH,
            height=self.BODY_HEIGHT,
            padding=0,
        )
        panel.place(x=0, y=0, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT)
        content = panel.content  # type: ignore[attr-defined]

        top = tk.Frame(content, width=self.CANVAS_WIDTH, height=74, bg=Theme.PANEL)
        top.place(x=0, y=0, width=self.CANVAS_WIDTH, height=74)
        top.pack_propagate(False)

        self.info_label = tk.Label(
            top,
            textvariable=self.info_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 18, "bold"),
            anchor=tk.W,
        )
        self.info_label.place(x=18, y=18, width=565, height=36)
        tk.Label(
            top,
            text="实时道路",
            bg=Theme.ACCENT_SOFT,
            fg=Theme.ACCENT,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.CENTER,
        ).place(x=618, y=19, width=108, height=32)

        canvas_wrap = tk.Frame(
            content,
            width=self.CANVAS_WIDTH,
            height=554,
            bg=Theme.CANVAS_BG,
        )
        canvas_wrap.place(x=0, y=74, width=self.CANVAS_WIDTH, height=554)
        canvas_wrap.pack_propagate(False)
        canvas_wrap.grid_propagate(False)

        self.game_canvas = tk.Canvas(
            canvas_wrap,
            width=self.CANVAS_WIDTH,
            height=self.CANVAS_HEIGHT,
            bg=Theme.CANVAS_BG,
            bd=0,
            highlightthickness=0,
        )
        self.game_canvas.place(x=0, y=0, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT)
        self.game_canvas.bind("<Configure>", self._on_canvas_resize)
        self.game_canvas.bind("<Button-1>", self._on_canvas_click)

        h_scrollbar = ttk.Scrollbar(
            canvas_wrap,
            orient=tk.HORIZONTAL,
            style="Modern.Horizontal.TScrollbar",
            command=self.game_canvas.xview,
        )
        h_scrollbar.place(x=0, y=self.CANVAS_HEIGHT, width=self.CANVAS_WIDTH, height=18)
        self.game_canvas.configure(xscrollcommand=h_scrollbar.set)

    def _build_control_panel(self, master) -> None:
        sidebar_x = self.GAME_PANEL_WIDTH + self.PANEL_GAP
        sidebar = tk.Frame(
            master,
            width=self.SIDEBAR_WIDTH,
            height=self.BODY_HEIGHT,
            bg=Theme.APP_BG,
        )
        sidebar.place(
            x=sidebar_x,
            y=0,
            width=self.SIDEBAR_WIDTH,
            height=self.BODY_HEIGHT,
        )
        sidebar.pack_propagate(False)
        sidebar.grid_propagate(False)

        # 0..67: fixed summary metrics.
        MetricTile(
            sidebar,
            "当前下注",
            self.bet_var,
            Theme.CYAN,
            width=169,
            height=68,
        ).place(x=0, y=0, width=169, height=68)
        MetricTile(
            sidebar,
            "上局获胜",
            self.last_win_var,
            Theme.GREEN,
            width=169,
            height=68,
        ).place(x=179, y=0, width=169, height=68)

        # 78..197: compact fixed bet card (the clear button now lives below).
        bet_card = self._card(sidebar, width=348, height=120, padding=12)
        bet_card.place(x=0, y=78, width=348, height=120)
        bet_content = bet_card.content  # type: ignore[attr-defined]
        self._section_title(
            bet_content,
            "下注金额",
            width=322,
        )

        chip_width = 49
        chip_gap = 5
        for index, (label, amount, chip_color, text_color) in enumerate(CHIP_CONFIGS):
            button = ChipButton(
                bet_content,
                label=label,
                amount=amount,
                chip_color=chip_color,
                text_color=text_color,
                command=self.add_chip,
                width=chip_width,
                height=50,
            )
            button.place(x=index * (chip_width + chip_gap), y=42, width=chip_width, height=50)
            self.chip_buttons.append(button)

        # 208..351: fixed difficulty card.
        difficulty_card = self._card(sidebar, width=348, height=144, padding=12)
        difficulty_card.place(x=0, y=208, width=348, height=144)
        difficulty_content = difficulty_card.content  # type: ignore[attr-defined]
        self._section_title(
            difficulty_content,
            "难度模式",
            width=322,
        )

        for index, (name, value, risk) in enumerate(DIFFICULTIES):
            button = ModernButton(
                difficulty_content,
                text=f"{name}  ·  {risk}",
                command=lambda level=value: self.set_difficulty(level),
                background=Theme.PANEL_HOVER,
                hover_background=Theme.BORDER_SOFT,
                foreground=Theme.TEXT,
                font_size=12,
                justify=tk.CENTER,
            )
            x = 0 if index % 2 == 0 else 167
            y = 44 if index < 2 else 82
            button.place(x=x, y=y, width=155, height=32)
            self.difficulty_buttons.append(button)

        # 362..525: fixed status/action card.
        action_card = self._card(sidebar, width=348, height=164, padding=12)
        action_card.place(x=0, y=362, width=348, height=164)
        action_content = action_card.content  # type: ignore[attr-defined]

        stats = tk.Frame(action_content, width=322, height=52, bg=Theme.PANEL)
        stats.place(x=0, y=0, width=322, height=52)
        stats.pack_propagate(False)
        self._mini_stat(stats, 0, "阶段", self.stage_var, Theme.TEXT)
        self._mini_stat(stats, 109, "潜在奖励", self.potential_var, Theme.CYAN)
        self._mini_stat(stats, 218, "实时风险", self.risk_var, Theme.RED)

        self.button_frame = tk.Frame(
            action_content,
            width=self.ACTION_BUTTON_WIDTH,
            height=80,
            bg=Theme.PANEL,
        )
        self.button_frame.place(x=0, y=58, width=self.ACTION_BUTTON_WIDTH, height=80)
        self.button_frame.pack_propagate(False)

        self.reset_bet_button = ModernButton(
            self.button_frame,
            text="清空全部筹码",
            command=self.reset_bet,
            background=Theme.RED,
            hover_background=Theme.RED_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.reset_bet_button.place(
            x=0, y=0, width=self.ACTION_BUTTON_WIDTH, height=self.ACTION_BUTTON_HEIGHT
        )

        self.start_button = ModernButton(
            self.button_frame,
            text="开始游戏",
            command=self.start_game,
            background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.start_button.place(
            x=0,
            y=42,
            width=self.ACTION_BUTTON_WIDTH,
            height=self.ACTION_BUTTON_HEIGHT,
        )

        self.advance_button = ModernButton(
            self.button_frame,
            text="前进一步  →",
            command=self.advance,
            background=Theme.ACCENT,
            hover_background=Theme.ACCENT_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.advance_button.place_forget()

        self.cash_out_button = ModernButton(
            self.button_frame,
            text="兑现奖金",
            command=self.cash_out,
            background=Theme.RED,
            hover_background=Theme.RED_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.cash_out_button.place_forget()

        # 536..595: compact fixed footer card.
        rules_card = self._card(sidebar, width=348, height=150, padding=12)
        rules_card.place(x=0, y=536, width=348, height=140)
        rules_content = rules_card.content  # type: ignore[attr-defined]
        tk.Label(
            rules_content,
            text="成功后可继续前进或立即兑现\n失败将损失本局下注。",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 18),
            justify=tk.LEFT,
            anchor=tk.W,
            wraplength=318,
        ).place(x=0, y=0, width=322, height=70)

        self._refresh_difficulty_styles()

    def _mini_stat(
        self,
        master,
        x: int,
        label: str,
        variable: tk.StringVar,
        color: str,
    ) -> None:
        box = tk.Frame(
            master,
            width=104,
            height=52,
            bg=Theme.PANEL_ALT,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        box.place(x=x, y=0, width=104, height=52)
        box.pack_propagate(False)
        tk.Label(
            box,
            text=label,
            bg=Theme.PANEL_ALT,
            fg=Theme.TEXT_DIM,
            font=(Theme.FONT_CJK, 8),
            anchor=tk.CENTER,
        ).place(x=4, y=5, width=96, height=16)
        tk.Label(
            box,
            textvariable=variable,
            bg=Theme.PANEL_ALT,
            fg=color,
            font=(Theme.FONT, 9, "bold"),
            anchor=tk.CENTER,
        ).place(x=4, y=24, width=96, height=20)

    def _on_canvas_resize(self, _event) -> None:
        # Configure fires once during construction; dimensions remain fixed afterwards.
        if not self.game_active and not self.animation_in_progress:
            self.draw_game()

    def _on_canvas_click(self, event) -> None:
        """Advance when the player clicks the immediately following road cell."""
        if (
            not self.game_active
            or self.animation_in_progress
            or self.chicken_animation_steps
            or str(self.advance_button.cget("state")) == tk.DISABLED
        ):
            return

        multipliers = self.difficulty_settings[self.difficulty]["multipliers"]
        next_stage = self.current_stage + 1
        if next_stage >= len(multipliers):
            return

        canvas_x = self.game_canvas.canvasx(event.x)
        canvas_y = self.game_canvas.canvasy(event.y)
        x1 = self.BOARD_START_X + next_stage * self.BOARD_CELL_WIDTH
        x2 = x1 + self.BOARD_CELL_WIDTH
        y1 = self.BOARD_START_Y
        y2 = self.BOARD_START_Y + self.ROAD_BOTTOM_OFFSET + 20

        if x1 <= canvas_x < x2 and y1 <= canvas_y <= y2:
            self.advance()

    # ------------------------------------------------------------------
    # UI state and player inputs
    # ------------------------------------------------------------------

    def add_chip(self, amount):
        try:
            amount_val = float(amount)
            new_bet = self.current_bet + amount_val
            if new_bet <= self.balance:
                self.current_bet = new_bet
                self.bet_var.set(f"${self.current_bet:.2f}")
        except ValueError:
            pass

    def reset_bet(self):
        if self.game_active:
            return
        self.current_bet = 0.0
        self.bet_var.set("$0.00")

    def _set_notice(self, message: str, duration_ms: Optional[int] = None) -> None:
        """Show a temporary high-priority status message without resizing widgets."""
        self.notice_message = message
        if self.notice_clear_job is not None:
            try:
                self.root.after_cancel(self.notice_clear_job)
            except tk.TclError:
                pass
            self.notice_clear_job = None
        if duration_ms is not None:
            self.notice_clear_job = self.root.after(duration_ms, self._clear_notice)
        self.update_display()

    def _clear_notice(self) -> None:
        self.notice_message = ""
        self.notice_clear_job = None
        self.update_display()

    def _reset_risk_pool(self) -> None:
        """Reset the 25-element fixed danger pool for a new round."""
        self.remaining_cells = TOTAL_POOL_CELLS
        self.remaining_dangers = DANGER_COUNTS[self.difficulty]

    def _get_current_death_rate(self) -> float:
        """Return the live conditional risk for the next ordinary move."""
        if self.remaining_cells <= 0 or self.remaining_dangers <= 0:
            return 0.0
        return max(0.0, min(1.0, self.remaining_dangers / self.remaining_cells))

    def _consume_safe_pool_element(self) -> bool:
        """Remove one guaranteed-safe element from the remaining pool."""
        safe_remaining = self.remaining_cells - self.remaining_dangers
        if self.remaining_cells <= 0 or safe_remaining <= 0:
            return False
        self.remaining_cells -= 1
        return True

    def _generate_round_items(self) -> None:
        """Generate no item 93% of rounds; otherwise one STEP 04-15 item."""
        self.round_items = {}
        self.collected_item_stages.clear()

        if random.random() >= ITEM_ROUND_RATE:
            return

        multipliers = self.difficulty_settings[self.difficulty]["multipliers"]
        eligible_stages = [
            stage_index
            for stage_index in range(3, 15)  # STEP 04 through STEP 15 inclusive
            if stage_index < len(multipliers) - 1
        ]
        if not eligible_stages:
            return

        stage = random.choice(eligible_stages)
        type_weights = ITEM_WEIGHTS_BY_DIFFICULTY[self.difficulty]
        item_ids = tuple(type_weights.keys())
        weights = tuple(type_weights.values())
        self.round_items[stage] = random.choices(item_ids, weights=weights, k=1)[0]

    def _handle_safe_arrival(self) -> None:
        """Activate an item only after the chicken has safely reached its cell."""
        if not self.game_active:
            return

        item_id = self.round_items.get(self.current_stage)
        if item_id is not None and self.current_stage not in self.collected_item_stages:
            self.collected_item_stages.add(self.current_stage)
            self._activate_item(item_id)
            return

        self._continue_after_item_effect()

    def _activate_item(self, item_id: str) -> None:
        definition = ITEM_DEFINITIONS[item_id]
        self.effect_in_progress = True

        if item_id == "speed_1":
            self.safe_bonus_steps_remaining = 1
            self._set_notice(
                f"获得道具：{definition['name']}，免费安全前进 1 步"
            )
            self.root.after(500, self._continue_after_item_effect)
            return

        if item_id == "bonus_1":
            self.temporary_multiplier_bonus = 1.0
            base_multiplier = self.difficulty_settings[self.difficulty]["multipliers"][
                self.current_stage
            ]
            self._set_notice(
                f"获得道具：{definition['name']}，本格立即兑现为 "
                f"×{base_multiplier + self.temporary_multiplier_bonus:.2f}",
                duration_ms=None,
            )
            self.root.after(500, self._continue_after_item_effect)
            return

        self._continue_after_item_effect()

    def _continue_after_item_effect(self) -> None:
        if not self.game_active:
            return
        if self.safe_bonus_steps_remaining > 0:
            self._continue_safe_bonus_move()
        else:
            self._finish_safe_turn()

    def _continue_safe_bonus_move(self) -> None:
        """Advance one guaranteed-safe step and consume one safe pool element."""
        if not self.game_active:
            return

        multipliers = self.difficulty_settings[self.difficulty]["multipliers"]
        if self.current_stage >= len(multipliers) - 1:
            self.safe_bonus_steps_remaining = 0
            self.complete_game()
            return

        # A speed item represents a guaranteed safe draw from the fixed pool.
        if self.remaining_cells - self.remaining_dangers <= 0:
            self.safe_bonus_steps_remaining = 0
            self.complete_game()
            return

        self.safe_bonus_steps_remaining -= 1
        from_stage = self.current_stage
        to_stage = self.current_stage + 1
        self.play_chicken_animation(
            from_stage,
            to_stage,
            death_rate=0.0,
            safe_move=True,
        )

    def _finish_safe_turn(self) -> None:
        if not self.game_active:
            return

        multipliers = self.difficulty_settings[self.difficulty]["multipliers"]
        self.effect_in_progress = False
        if self.temporary_multiplier_bonus <= 0:
            self.notice_message = ""
        if self.current_stage >= len(multipliers) - 1:
            self.root.after(350, self.complete_game)
        else:
            self.root.after(350, lambda: self.advance_button.config(state=tk.NORMAL))
            self.update_display()

    def set_difficulty(self, difficulty):
        self.difficulty = difficulty
        self._refresh_difficulty_styles()
        self.update_display()

    def _refresh_difficulty_styles(self) -> None:
        for index, (_name, value, _risk) in enumerate(DIFFICULTIES):
            button = self.difficulty_buttons[index]
            if value == self.difficulty:
                button.set_colors(Theme.ACCENT, Theme.ACCENT_HOVER, "#FFFFFF")
            else:
                button.set_colors(Theme.PANEL_HOVER, Theme.BORDER, Theme.TEXT)

    def update_display(self):
        self.balance_var.set(f"${self.balance:.2f}")
        self.last_win_var.set(f"${self.last_win:.2f}")
        self.bet_var.set(
            f"${self.bet_amount:.2f}" if self.game_active else f"${self.current_bet:.2f}"
        )

        settings = self.difficulty_settings[self.difficulty]
        multipliers = settings["multipliers"]
        if self.collision_triggered:
            live_risk = 1.0
        elif (
            self.game_active
            and self.current_stage >= len(multipliers) - 1
        ):
            # 已经安全抵达最后一格，不再存在下一步风险
            live_risk = 0.0
        else:
            if self.game_active:
                live_risk = self._get_current_death_rate()
            else:
                live_risk = (
                    DANGER_COUNTS[self.difficulty]
                    / TOTAL_POOL_CELLS
                )

        self.risk_var.set(f"{live_risk * 100:.1f}%")

        if self.game_active:
            if self.current_stage < len(multipliers):
                base_multiplier = multipliers[self.current_stage]
                cashout_multiplier = base_multiplier + self.temporary_multiplier_bonus
                potential_win = self.bet_amount * cashout_multiplier
                self.stage_var.set(f"{self.current_stage + 1}/{len(multipliers)}")
                self.potential_var.set(f"${potential_win:.2f}")
                bonus_text = (
                    f"  ·  临时 ×{cashout_multiplier:.2f}"
                    if self.temporary_multiplier_bonus > 0
                    else ""
                )
                regular_message = (
                    f"阶段 {self.current_stage + 1}/{len(multipliers)}  ·  "
                    f"实时风险 {live_risk * 100:.1f}%{bonus_text}"
                )
                self.info_var.set(self.notice_message or regular_message)
            else:
                self.stage_var.set("完成")
                self.potential_var.set("MAX")
                self.info_var.set(self.notice_message or "游戏完成！")
        else:
            self.stage_var.set("待开始")
            self.potential_var.set("$0.00")
            self.info_var.set("选择下注金额与难度，然后开始挑战。")

        self.draw_game()

    # ------------------------------------------------------------------
    # Board rendering
    # ------------------------------------------------------------------

    def ensure_chicken_visible(self):
        if not self.game_active:
            return

        # --------------------------------------------------
        # 撞车动画期间：冻结当前道路滚动位置
        # --------------------------------------------------
        if (
            self.collision_triggered
            and self.collision_camera_position is not None
        ):
            self.game_canvas.xview_moveto(
                self.collision_camera_position
            )
            return

        multipliers = self.difficulty_settings[self.difficulty]["multipliers"]

        cell_width = self.BOARD_CELL_WIDTH
        start_x = self.BOARD_START_X

        canvas_width = self.game_canvas.winfo_width()
        if canvas_width <= 1:
            return

        total_width = (
            len(multipliers) * cell_width
            + start_x * 2
        )

        # 当前小鸡世界坐标
        if self.chicken_animation_steps:
            _, from_stage, to_stage, progress = self.chicken_animation_steps[0]

            from_x = (
                start_x
                + from_stage * cell_width
                + cell_width / 2
            )

            to_x = (
                start_x
                + to_stage * cell_width
                + cell_width / 2
            )

            chicken_x = (
                from_x
                + (to_x - from_x) * progress
            )
        else:
            chicken_x = (
                start_x
                + self.current_stage * cell_width
                + cell_width / 2
            )

        # --------------------------------------------------
        # 希望小鸡保持在画面宽度约 35% 的位置
        # --------------------------------------------------

        target_screen_ratio = 0.35

        target_left = (
            chicken_x
            - canvas_width * target_screen_ratio
        )

        max_left = max(
            0,
            total_width - canvas_width
        )

        target_left = max(
            0,
            min(target_left, max_left)
        )

        # --------------------------------------------------
        # 获取当前视口左侧像素位置
        # --------------------------------------------------

        current_fraction = self.game_canvas.xview()[0]

        current_left = (
            current_fraction * total_width
        )

        # --------------------------------------------------
        # 平滑靠近目标
        # --------------------------------------------------

        smoothing = 0.18

        new_left = (
            current_left
            + (target_left - current_left) * smoothing
        )

        # 很接近时直接贴合，避免微小抖动
        if abs(target_left - new_left) < 1:
            new_left = target_left

        new_fraction = (
            new_left / total_width
            if total_width > 0
            else 0
        )

        self.game_canvas.xview_moveto(
            max(0, min(1, new_fraction))
        )

    def draw_game(self):
        self.game_canvas.delete("all")

        if not self.game_active:
            self._draw_welcome_screen()
            return

        self.draw_classic_ui()
        bbox = self.game_canvas.bbox("all")
        if bbox:
            self.game_canvas.configure(scrollregion=bbox)
        self.ensure_chicken_visible()

    def _draw_welcome_screen(self) -> None:
        width = max(self.game_canvas.winfo_width(), 640)
        height = max(self.game_canvas.winfo_height(), 460)
        self.game_canvas.configure(scrollregion=(0, 0, width, height))

        # Cartoon landscape preview rather than a blank paper-like canvas.
        self.game_canvas.create_rectangle(0, 0, width, 112, fill=Theme.SKY, outline="")
        self.game_canvas.create_rectangle(0, 112, width, 164, fill=Theme.GRASS, outline="")
        self.game_canvas.create_rectangle(0, 164, width, 184, fill=Theme.SIDEWALK, outline="")
        self.game_canvas.create_rectangle(0, 184, width, 410, fill=Theme.ROAD, outline="")
        self.game_canvas.create_rectangle(0, 410, width, 430, fill=Theme.SIDEWALK, outline="")
        self.game_canvas.create_rectangle(0, 430, width, height, fill=Theme.GRASS_DARK, outline="")

        # Clouds, grass tufts, curb, lane markings and asphalt patches.
        for cloud_x in (95, 320, 590):
            self.game_canvas.create_oval(cloud_x, 30, cloud_x + 64, 65,
                                         fill="#DCE8E9", outline="")
            self.game_canvas.create_oval(cloud_x + 28, 17, cloud_x + 84, 63,
                                         fill="#DCE8E9", outline="")
        for x in range(0, width + 40, 40):
            curb_color = Theme.CURB_LIGHT if (x // 40) % 2 == 0 else Theme.CURB_DARK
            self.game_canvas.create_rectangle(x, 176, x + 40, 184,
                                               fill=curb_color, outline="")
            self.game_canvas.create_rectangle(x, 410, x + 40, 418,
                                               fill=curb_color, outline="")
        for x in range(-20, width + 80, 92):
            self.game_canvas.create_rectangle(x, 251, x + 52, 259,
                                               fill=Theme.ROAD_WHITE, outline="")
            self.game_canvas.create_rectangle(x + 38, 333, x + 90, 341,
                                               fill=Theme.ROAD_WHITE, outline="")
        self.game_canvas.create_line(0, 296, width, 296,
                                     fill=Theme.ROAD_LINE, width=4)
        for x, y in ((85, 210), (520, 222), (650, 370), (230, 380)):
            self.game_canvas.create_oval(x, y, x + 70, y + 20,
                                         fill=Theme.ROAD_PATCH, outline="")

        center_x = width / 2
        self._rounded_rectangle(
            center_x - 235,
            62,
            center_x + 235,
            172,
            radius=18,
            fill=Theme.PANEL,
            outline=Theme.BORDER,
            width=2,
        )
        self.game_canvas.create_text(
            center_x - 174,
            115,
            text="🐥",
            font=(Theme.FONT_EMOJI, 42),
        )
        self.game_canvas.create_text(
            center_x + 10,
            98,
            text="准备穿越卡通公路",
            fill=Theme.TEXT,
            font=(Theme.FONT_CJK, 20, "bold"),
        )
        self.game_canvas.create_text(
            center_x + 10,
            132,
            text="选择筹码与难度，开始你的第一步",
            fill=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 10),
        )
        self.game_canvas.create_text(
            center_x,
            468,
            text="RISK  ×  REWARD",
            fill="#E8E0C9",
            font=(Theme.FONT, 10, "bold"),
        )

    def draw_classic_ui(self):
        """Draw a tall, detailed three-lane cartoon road with fixed geometry."""
        multipliers = self.difficulty_settings[self.difficulty]["multipliers"]
        cell_width = self.BOARD_CELL_WIDTH
        cell_height = self.BOARD_CELL_HEIGHT
        start_x = self.BOARD_START_X
        start_y = self.BOARD_START_Y
        road_top = start_y + self.ROAD_TOP_OFFSET
        road_bottom = start_y + self.ROAD_BOTTOM_OFFSET
        road_height = road_bottom - road_top
        total_width = len(multipliers) * cell_width
        road_left = start_x - 18
        road_right = start_x + total_width + 18

        # Continue the welcome-screen landscape inside the active game view.
        self.game_canvas.create_rectangle(
            road_left, 0, road_right, road_top - 20,
            fill=Theme.SKY, outline=""
        )
        for cloud_x in range(int(road_left) + 70, int(road_right), 250):
            self.game_canvas.create_oval(
                cloud_x, 31, cloud_x + 64, 66,
                fill="#DCE8E9", outline=""
            )
            self.game_canvas.create_oval(
                cloud_x + 28, 18, cloud_x + 84, 64,
                fill="#DCE8E9", outline=""
            )
        for hill_x in range(int(road_left) - 30, int(road_right), 210):
            self.game_canvas.create_oval(
                hill_x, 82, hill_x + 250, 150,
                fill=Theme.GRASS_DARK, outline=""
            )
        self.game_canvas.create_rectangle(
            road_left, start_y + 94, road_right, road_top - 20,
            fill=Theme.GRASS, outline=""
        )
        self.game_canvas.create_rectangle(
            road_left, road_top - 20, road_right, road_top,
            fill=Theme.SIDEWALK, outline=""
        )
        self.game_canvas.create_rectangle(
            road_left, road_bottom, road_right, road_bottom + 20,
            fill=Theme.SIDEWALK, outline=""
        )
        self.game_canvas.create_rectangle(
            road_left, road_bottom + 20, road_right, road_bottom + 48,
            fill=Theme.GRASS_DARK, outline=""
        )

        # Alternating cartoon curb blocks.
        curb_block = 42
        for x in range(int(road_left), int(road_right) + curb_block, curb_block):
            color = Theme.CURB_LIGHT if ((x - int(road_left)) // curb_block) % 2 == 0 else Theme.CURB_DARK
            self.game_canvas.create_rectangle(
                x, road_top - 8, x + curb_block, road_top,
                fill=color, outline=""
            )
            self.game_canvas.create_rectangle(
                x, road_bottom, x + curb_block, road_bottom + 8,
                fill=color, outline=""
            )

        # Main asphalt body with a strong dark edge.
        self._rounded_rectangle(
            road_left,
            road_top,
            road_right,
            road_bottom,
            radius=18,
            fill=Theme.ROAD,
            outline=Theme.ROAD_EDGE,
            width=3,
        )

        # Asphalt patches and small aggregate marks add cartoon texture.
        for idx in range(len(multipliers)):
            center_x = start_x + idx * cell_width + cell_width / 2
            if idx % 3 == 0:
                self.game_canvas.create_oval(
                    center_x - 43, road_top + 36,
                    center_x + 20, road_top + 55,
                    fill=Theme.ROAD_PATCH, outline=""
                )
            if idx % 4 == 1:
                self.game_canvas.create_oval(
                    center_x - 10, road_bottom - 62,
                    center_x + 47, road_bottom - 44,
                    fill=Theme.ROAD_PATCH, outline=""
                )
            self.game_canvas.create_oval(
                center_x - 31, road_top + 92,
                center_x - 27, road_top + 96,
                fill="#3C4148", outline=""
            )
            self.game_canvas.create_oval(
                center_x + 25, road_bottom - 92,
                center_x + 29, road_bottom - 88,
                fill="#676D74", outline=""
            )

        # Three lanes: white broken separators plus a double yellow centre line.
        lane_y_1 = road_top + road_height / 3
        lane_y_2 = road_top + road_height * 2 / 3
        for x in range(int(road_left) + 22, int(road_right), 84):
            self.game_canvas.create_rectangle(
                x, lane_y_1 - 3, x + 46, lane_y_1 + 3,
                fill=Theme.ROAD_WHITE, outline=""
            )
            self.game_canvas.create_rectangle(
                x + 30, lane_y_2 - 3, x + 76, lane_y_2 + 3,
                fill=Theme.ROAD_WHITE, outline=""
            )
        self.game_canvas.create_line(
            road_left + 10, (road_top + road_bottom) / 2 - 5,
            road_right - 10, (road_top + road_bottom) / 2 - 5,
            fill=Theme.ROAD_LINE, width=3
        )
        self.game_canvas.create_line(
            road_left + 10, (road_top + road_bottom) / 2 + 5,
            road_right - 10, (road_top + road_bottom) / 2 + 5,
            fill=Theme.ROAD_LINE, width=3
        )

        for idx, multiplier in enumerate(multipliers):
            cell_left = start_x + idx * cell_width
            cell_right = start_x + (idx + 1) * cell_width
            x1 = cell_left + 7
            x2 = cell_right - 7
            center_x = cell_left + cell_width / 2

            # Keep every numbered lower road cell visibly green, matching the
            # initial landscape instead of exposing the canvas background.
            self.game_canvas.create_rectangle(
                cell_left,
                road_bottom + 20,
                cell_right,
                road_bottom + 48,
                fill=Theme.GRASS_DARK,
                outline=Theme.GRASS,
                width=1,
            )

            if idx < self.current_stage:
                fill = Theme.COMPLETED
                outline = Theme.COMPLETED_BORDER
                status = "安全"
                status_color = Theme.COMPLETED_BORDER
            elif idx == self.current_stage:
                fill = Theme.ACTIVE
                outline = Theme.ACTIVE_BORDER
                status = "目前"
                status_color = Theme.ACCENT
            else:
                fill = Theme.UPCOMING
                outline = Theme.UPCOMING_BORDER
                status = "下一个"
                status_color = Theme.TEXT_DIM

            self._rounded_rectangle(
                x1,
                start_y,
                x2,
                start_y + 88,
                radius=13,
                fill=fill,
                outline=outline,
                width=2 if idx == self.current_stage else 1,
            )
            self.game_canvas.create_text(
                center_x,
                start_y + 19,
                text=f"STEP {idx + 1:02d}",
                fill=status_color,
                font=(Theme.FONT, 8, "bold"),
            )
            self.game_canvas.create_text(
                center_x,
                start_y + 47,
                text=f"×{multiplier:.2f}",
                fill=Theme.AMBER if idx == self.current_stage else Theme.TEXT,
                font=(Theme.FONT, 14, "bold"),
            )
            self.game_canvas.create_text(
                center_x,
                start_y + 72,
                text=status,
                fill=status_color,
                font=(Theme.FONT, 7, "bold"),
            )

            # Wide zebra-crossing marker for every risk step.
            stripe_width = 10
            for stripe_index in range(7):
                stripe_y = road_top + 20 + stripe_index * 35
                stripe_fill = "#D9D8D3" if idx != self.current_stage else "#F8F4E9"
                self.game_canvas.create_rectangle(
                    center_x - stripe_width,
                    stripe_y,
                    center_x + stripe_width,
                    min(stripe_y + 21, road_bottom - 14),
                    fill=stripe_fill,
                    outline="",
                )
            self.game_canvas.create_line(
                center_x - 14, road_top + 12,
                center_x - 14, road_bottom - 12,
                fill=outline, width=2 if idx == self.current_stage else 1
            )
            self.game_canvas.create_line(
                center_x + 14, road_top + 12,
                center_x + 14, road_bottom - 12,
                fill=outline, width=2 if idx == self.current_stage else 1
            )

            item_id = self.round_items.get(idx)
            if item_id is not None and idx not in self.collected_item_stages:
                self._draw_item_marker(center_x, road_top + 43, item_id)

            if idx == self.current_stage and not self.chicken_animation_steps:
                self.game_canvas.create_oval(
                    center_x - 28,
                    start_y + self.CHICKEN_Y_OFFSET - 28,
                    center_x + 28,
                    start_y + self.CHICKEN_Y_OFFSET + 28,
                    fill="#F2D48A",
                    outline=Theme.ACTIVE_BORDER,
                    width=3,
                )
                self.game_canvas.create_text(
                    center_x,
                    start_y + self.CHICKEN_Y_OFFSET,
                    text="🐥",
                    font=(Theme.FONT_EMOJI, 25),
                )

            self.game_canvas.create_text(
                center_x,
                road_bottom + 34,
                text=f"{idx + 1:02d}",
                fill="#E6E0D4",
                font=(Theme.FONT, 8, "bold"),
            )

        if self.animation_in_progress and self.car_animation_step > 0:
            self.draw_car_animation(start_x, start_y, cell_width, cell_height)

        if self.chicken_animation_steps:
            self.draw_chicken_animation(start_x, start_y, cell_width, cell_height)

        self.game_canvas.create_text(
            start_x,
            start_y + cell_height - 4,
            text="START",
            anchor=tk.W,
            fill="#E9E2D5",
            font=(Theme.FONT, 8, "bold"),
        )
        self.game_canvas.create_text(
            start_x + total_width,
            start_y + cell_height - 4,
            text="MAX PAYOUT",
            anchor=tk.E,
            fill="#E9E2D5",
            font=(Theme.FONT, 8, "bold"),
        )

    def _draw_item_marker(self, x: float, y: float, item_id: str) -> None:
        definition = ITEM_DEFINITIONS[item_id]
        color = definition["color"]
        self.game_canvas.create_oval(
            x - 22, y - 22, x + 22, y + 22,
            fill="#F4E8C8", outline=color, width=3,
        )
        self.game_canvas.create_oval(
            x - 16, y - 16, x + 16, y + 16,
            fill=color, outline="#F7F1E5", width=2,
        )
        self.game_canvas.create_text(
            x,
            y - 1,
            text=definition["icon"],
            fill="#FFFFFF",
            font=(Theme.FONT_EMOJI, 10, "bold"),
        )

    def draw_chicken_animation(self, start_x, start_y, cell_width, cell_height):
        if not self.chicken_animation_steps:
            return

        _step_idx, from_stage, to_stage, progress = self.chicken_animation_steps[0]
        from_x = start_x + from_stage * cell_width + cell_width / 2
        to_x = start_x + to_stage * cell_width + cell_width / 2
        y = start_y + self.CHICKEN_Y_OFFSET
        current_x = from_x + (to_x - from_x) * progress

        self.game_canvas.create_oval(
            current_x - 25,
            y - 25,
            current_x + 25,
            y + 25,
            fill="#F2D48A",
            outline=Theme.ACTIVE_BORDER,
            width=2,
        )
        self.game_canvas.create_text(
            current_x,
            y,
            text="🐥",
            font=(Theme.FONT_EMOJI, 23),
        )

        if len(self.chicken_animation_steps) > 1:
            ghost_colors = ("#D8B96D", "#BCA86F", "#9B9275", "#7C7B75")
            for index in range(1, min(5, len(self.chicken_animation_steps))):
                _, _, _, previous_progress = self.chicken_animation_steps[index]
                previous_x = from_x + (to_x - from_x) * previous_progress
                self.game_canvas.create_text(
                    previous_x,
                    y,
                    text="🐥",
                    font=(Theme.FONT_EMOJI, 18),
                    fill=ghost_colors[index - 1],
                )

    def get_transparent_color(self, color, alpha):
        # Kept for API compatibility with the previous drawing implementation.
        if alpha > 0.7:
            return color
        if alpha > 0.4:
            return "#A8B3C0"
        return "#C7D0DA"

    def draw_car_animation(self, start_x, start_y, cell_width, cell_height):
        car_x = start_x + self.current_stage * cell_width + cell_width / 2
        car_y = start_y + self.CHICKEN_Y_OFFSET
        road_top = start_y + self.ROAD_TOP_OFFSET

        car_positions = (
            road_top + 18,
            road_top + 68,
            road_top + 118,
            road_top + 168,
        )
        if 1 <= self.car_animation_step <= 3:
            self.draw_car_model(car_x, car_positions[self.car_animation_step - 1], 1.18)
        elif self.car_animation_step == 4:
            self.draw_car_model(car_x, car_y, 1.18)
            self.game_canvas.create_text(
                car_x,
                car_y - 45,
                text="IMPACT",
                font=(Theme.FONT, 10, "bold"),
                fill="#FFD4CF",
            )
            self.game_canvas.create_text(
                car_x,
                car_y,
                text="💥",
                font=(Theme.FONT_EMOJI, 29),
            )
        elif self.car_animation_step >= 5:
            self.game_canvas.create_oval(
                car_x - 29,
                car_y - 29,
                car_x + 29,
                car_y + 29,
                fill="#6B3E42",
                outline="#F1B0A9",
                width=3,
            )
            self.game_canvas.create_text(
                car_x,
                car_y,
                text="💀",
                font=(Theme.FONT_EMOJI, 25),
            )

    def draw_car_model(self, x, y, scale=1.0):
        car_width = 46 * scale
        car_height = 20 * scale
        wheel_radius = 7 * scale

        self._rounded_rectangle(
            x - car_width / 2,
            y - car_height / 2,
            x + car_width / 2,
            y + car_height / 2,
            radius=7,
            fill=Theme.RED,
            outline="#F3B2AA",
            width=2,
        )
        self._rounded_rectangle(
            x - car_width / 3,
            y - car_height / 2 - 11 * scale,
            x + car_width / 3,
            y - car_height / 2 + 1,
            radius=5,
            fill="#C95E55",
            outline="#F3B2AA",
            width=1,
        )
        self.game_canvas.create_rectangle(
            x - car_width / 5,
            y - car_height / 2 - 8 * scale,
            x + car_width / 5,
            y - car_height / 2 - 2 * scale,
            fill="#BCE2EB",
            outline="",
        )
        for wheel_x in (x - car_width / 3, x + car_width / 3):
            self.game_canvas.create_oval(
                wheel_x - wheel_radius,
                y + car_height / 2 - wheel_radius / 2,
                wheel_x + wheel_radius,
                y + car_height / 2 + wheel_radius / 2,
                fill="#24282D",
                outline=Theme.TEXT_DIM,
            )

    def _rounded_rectangle(self, x1, y1, x2, y2, radius=12, **kwargs):
        radius = min(radius, abs(x2 - x1) / 2, abs(y2 - y1) / 2)
        points = (
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        )
        return self.game_canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

    # ------------------------------------------------------------------
    # Game mechanics — same flow and formulas as the original
    # ------------------------------------------------------------------

    def start_game(self):
        if self.current_bet <= 0:
            messagebox.showwarning("错误", "请先下注")
            return
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注")
            return

        self.round_original_bet = self.current_bet
        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        self.current_stage = 0
        self.game_active = True
        self.animation_in_progress = False
        self.effect_in_progress = False
        self.car_animation_step = 0
        self.collision_triggered = False
        self.collision_camera_position = None
        self.safe_bonus_steps_remaining = 0
        self.temporary_multiplier_bonus = 0.0
        self.notice_message = ""
        self._reset_risk_pool()
        if self.notice_clear_job is not None:
            try:
                self.root.after_cancel(self.notice_clear_job)
            except tk.TclError:
                pass
            self.notice_clear_job = None
        self._generate_round_items()

        update_balance_in_json(self.username, self.balance)

        self.start_button.config(state=tk.DISABLED)
        self.start_button.place_forget()
        self.reset_bet_button.place_forget()
        self.advance_button.place(
            x=0, y=0, width=self.ACTION_BUTTON_WIDTH, height=self.ACTION_BUTTON_HEIGHT
        )
        self.advance_button.config(state=tk.NORMAL)
        self.cash_out_button.place(
            x=0, y=42, width=self.ACTION_BUTTON_WIDTH, height=self.ACTION_BUTTON_HEIGHT
        )
        self.cash_out_button.config(state=tk.NORMAL)

        for button in self.chip_buttons:
            button.configure(state=tk.DISABLED)
        for button in self.difficulty_buttons:
            button.configure(state=tk.DISABLED)

        self.game_canvas.xview_moveto(0)
        self.update_display()

    def advance(self):
        if (
            not self.game_active
            or self.animation_in_progress
            or self.effect_in_progress
            or self.chicken_animation_steps
        ):
            return

        multipliers = self.difficulty_settings[self.difficulty]["multipliers"]
        if self.current_stage >= len(multipliers) - 1:
            self.complete_game()
            return

        # The +1x item is valid only on the cell where it was collected.
        if self.temporary_multiplier_bonus > 0:
            self.temporary_multiplier_bonus = 0.0
            self.notice_message = ""

        self.advance_button.config(state=tk.DISABLED)
        death_rate = self._get_current_death_rate()
        from_stage = self.current_stage
        to_stage = self.current_stage + 1
        self.update_display()
        self.play_chicken_animation(from_stage, to_stage, death_rate, safe_move=False)

    def play_chicken_animation(
        self,
        from_stage,
        to_stage,
        death_rate,
        safe_move: bool = False,
    ):
        if self.chicken_animation_id:
            try:
                self.root.after_cancel(self.chicken_animation_id)
            except tk.TclError:
                pass

        duration = 300
        steps = 10
        step_delay = duration // steps
        self.chicken_animation_steps = []

        for step in range(steps):
            progress = step / (steps - 1)
            self.chicken_animation_steps.append((step, from_stage, to_stage, progress))

        self.update_display()

        if len(self.chicken_animation_steps) > 1:
            self.chicken_animation_id = self.root.after(
                step_delay,
                lambda: self.continue_chicken_animation(
                    from_stage, to_stage, death_rate, safe_move
                ),
            )
        else:
            self.finish_chicken_animation(
                from_stage, to_stage, death_rate, safe_move
            )

    def continue_chicken_animation(
        self,
        from_stage,
        to_stage,
        death_rate,
        safe_move: bool = False,
    ):
        if len(self.chicken_animation_steps) > 1:
            self.chicken_animation_steps.pop(0)
            self.update_display()

            duration = 300
            steps = 10
            step_delay = duration // steps
            self.chicken_animation_id = self.root.after(
                step_delay,
                lambda: self.continue_chicken_animation(
                    from_stage, to_stage, death_rate, safe_move
                ),
            )
        else:
            self.finish_chicken_animation(
                from_stage, to_stage, death_rate, safe_move
            )

    def finish_chicken_animation(
        self,
        from_stage,
        to_stage,
        death_rate,
        safe_move: bool = False,
    ):
        self.chicken_animation_id = None
        self.chicken_animation_steps = []
        self.current_stage = to_stage

        if safe_move:
            # Guaranteed safe draw: remove one safe element, leave danger count intact.
            if not self._consume_safe_pool_element():
                self.safe_bonus_steps_remaining = 0
                self.complete_game()
                return
            self.update_display()
            self._handle_safe_arrival()
            return

        failed = random.random() < death_rate

        if self.remaining_cells > 0:
            self.remaining_cells -= 1

        if failed:
            self.collision_triggered = True

            # 保存撞车发生瞬间的道路视口位置
            self.collision_camera_position = self.game_canvas.xview()[0]

            self.last_win = 0.0
            self.effect_in_progress = True
            self.animation_in_progress = True
            self.car_animation_step = 0
            self.notice_message = "危险命中！"

            self.update_display()
            self.root.after(500, self.play_car_animation)

        else:
            self.collision_triggered = False
            self.update_display()
            self._handle_safe_arrival()

    def play_car_animation(self):
        if self.car_animation_step < 6:
            self.car_animation_step += 1
            self.update_display()
            self.root.after(500, self.play_car_animation)
        else:
            self.animation_in_progress = False
            self.effect_in_progress = False
            self.game_active = False
            self.game_canvas.xview_moveto(0)
            self.end_game()

    def cash_out(self):
        if (
            not self.game_active
            or self.current_stage == 0
            or self.animation_in_progress
            or self.effect_in_progress
            or self.chicken_animation_steps
            or self.safe_bonus_steps_remaining > 0
        ):
            return

        multipliers = self.difficulty_settings[self.difficulty]["multipliers"]
        base_multiplier = multipliers[min(self.current_stage, len(multipliers) - 1)]
        win_multiplier = base_multiplier + self.temporary_multiplier_bonus
        win_amount = self.bet_amount * win_multiplier
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        self.effect_in_progress = False
        self.temporary_multiplier_bonus = 0.0
        self.notice_message = ""

        update_balance_in_json(self.username, self.balance)
        self.show_fireworks()
        self.root.after(2000, self.end_game)

    def complete_game(self):
        if not self.game_active:
            return
        multipliers = self.difficulty_settings[self.difficulty]["multipliers"]
        win_multiplier = multipliers[-1]
        win_amount = self.bet_amount * win_multiplier
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        self.effect_in_progress = False
        self.temporary_multiplier_bonus = 0.0
        self.notice_message = ""

        update_balance_in_json(self.username, self.balance)
        self.show_fireworks()
        self.root.after(2000, self.end_game)

    def show_fireworks(self):
        colors = (Theme.RED, Theme.GREEN, Theme.CYAN, Theme.AMBER, Theme.ACCENT_HOVER)

        scroll_left, scroll_right = self.game_canvas.xview()
        bbox = self.game_canvas.bbox("all")
        if bbox is None:
            return

        total_width = max(1, bbox[2] - bbox[0])
        view_left = scroll_left * total_width
        view_right = scroll_right * total_width
        canvas_height = max(120, self.game_canvas.winfo_height())

        for _ in range(15):
            x = random.randint(int(view_left), max(int(view_left), int(view_right)))
            y = random.randint(50, max(50, canvas_height - 50))
            color = random.choice(colors)
            firework = self.game_canvas.create_oval(
                x - 2, y - 2, x + 2, y + 2, fill=color, outline=color
            )

            def explode_firework(fw, cx, cy, step, firework_color=color):
                if step < 20:
                    radius = step * 5
                    self.game_canvas.delete(fw)
                    new_fw = self.game_canvas.create_oval(
                        cx - radius,
                        cy - radius,
                        cx + radius,
                        cy + radius,
                        outline=firework_color,
                        width=2,
                    )
                    self.root.after(
                        50,
                        lambda: explode_firework(
                            new_fw, cx, cy, step + 1, firework_color
                        ),
                    )
                else:
                    self.game_canvas.delete(fw)

            self.root.after(
                random.randint(0, 1000),
                lambda fw=firework, cx=x, cy=y: explode_firework(fw, cx, cy, 0),
            )

        self.root.after(2500, lambda: self.game_canvas.xview_moveto(0))

    def end_game(self):
        self.animation_in_progress = False
        self.collision_triggered = False
        self.collision_camera_position = None
        self.effect_in_progress = False
        self.chicken_animation_steps = []
        self.safe_bonus_steps_remaining = 0
        self.temporary_multiplier_bonus = 0.0
        self.notice_message = ""
        self.remaining_cells = TOTAL_POOL_CELLS
        self.remaining_dangers = DANGER_COUNTS[self.difficulty]
        self.start_button.config(state=tk.NORMAL)
        self.start_button.place(
            x=0, y=42, width=self.ACTION_BUTTON_WIDTH, height=self.ACTION_BUTTON_HEIGHT
        )
        self.advance_button.place_forget()
        self.advance_button.config(state=tk.NORMAL)
        self.cash_out_button.place_forget()
        self.cash_out_button.config(state=tk.NORMAL)
        self.reset_bet_button.place(
            x=0, y=0, width=self.ACTION_BUTTON_WIDTH, height=self.ACTION_BUTTON_HEIGHT
        )

        for button in self.chip_buttons:
            button.configure(state=tk.NORMAL)
        for button in self.difficulty_buttons:
            button.configure(state=tk.NORMAL)

        self.update_display()

    def on_closing(self):
        update_balance_in_json(self.username, self.balance)
        finish = getattr(self.root, "finish", None)
        if callable(finish):
            finish(self.balance)
        else:
            self.root.destroy()


# ---------------------------------------------------------------------------
# Public entry point — kept compatible with the original project
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
        page = EmbeddedGamePage(
            parent,
            title="小鸡过马路游戏",
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        game = ChickenCrossingGame(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = ChickenCrossingGame(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    final_balance = main(10000.0, "test_user")
    print(f"Final balance: {final_balance}")