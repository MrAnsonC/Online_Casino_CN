"""打地鼠 HMI — fixed-size UI with seven whack-a-mole holes.

The warm HMI layout is preserved while the gameplay is now a seven-hole
whack-a-mole betting game with difficulty-based mole counts and odds.
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


import base64
import io
import json
import os
import random
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

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
    "1": {"name": "天堂", "moles": 6, "odds": 0.10},
    "2": {"name": "简单", "moles": 5, "odds": 0.33},
    "3": {"name": "普通", "moles": 4, "odds": 0.65},
    "4": {"name": "中等", "moles": 3, "odds": 1.21},
    "5": {"name": "困难", "moles": 2, "odds": 2.35},
    "6": {"name": "地狱", "moles": 1, "odds": 5.65},
}

DIFFICULTIES = (
    ("天堂", "1", "6 鼠 · 0.10:1"),
    ("简单", "2", "5 鼠 · 0.33:1"),
    ("普通", "3", "4 鼠 · 0.65:1"),
    ("中等", "4", "3 鼠 · 1.21:1"),
    ("困难", "5", "2 鼠 · 2.35:1"),
    ("地狱", "6", "1 鼠 · 5.65:1"),
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


HAMMER_ICON_PNG_B64 = "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"


# ---------------------------------------------------------------------------
# Persistence helpers — same data format and update behaviour as before
# ---------------------------------------------------------------------------


def get_data_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../A_Tools/Account/saving_data.json")


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
    CANVAS_HEIGHT = 554
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

        # Whack-a-mole state. Seven holes are fixed; each round randomly selects
        # a group of active mole holes according to the chosen difficulty.
        self.total_holes = 7
        self.active_mole_holes = set()
        self.round_principal = 0.0
        self.successful_hits = 0
        self.selected_hole = None
        self.hammer_progress = 0.0
        self.mole_progress = 0.0
        self.hit_result = None
        self.turn_animation_job = None
        self.result_effect_active = False
        self.result_effect_phase = 0
        self.result_effect_job = None
        self.resolved_hole = None
        self.hammer_sprite_source = None
        self.hammer_sprite_cache = {}
        self.notice_message = "选择下注金额与难度，然后开始游戏"

        # Widget references used by both the view and existing game flow.
        self.chip_buttons = []
        self.difficulty_buttons = []

        self._load_hammer_sprite()
        self.create_widgets()
        self.update_display()

    # ------------------------------------------------------------------
    # Window and theme setup
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("打地鼠")
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
        self.risk_var = tk.StringVar(value="0.10:1")
        self.info_var = tk.StringVar(value="选择下注金额与难度，然后开始游戏")

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
            text="🔨",
            bg=Theme.APP_BG,
            fg=Theme.AMBER,
            font=(Theme.FONT_EMOJI, 27),
            anchor=tk.CENTER,
        ).place(x=0, y=7, width=42, height=44)
        tk.Label(
            header,
            text="WHACK-A-MOLE",
            bg=Theme.APP_BG,
            fg=Theme.TEXT,
            font=(Theme.FONT, 20, "bold"),
            anchor=tk.W,
        ).place(x=52, y=4, width=430, height=31)
        tk.Label(
            header,
            text="打地鼠",
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
        self.info_label.place(x=18, y=18, width=590, height=36)
        tk.Label(
            top,
            text="7 个鼠洞",
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
            y = 36 + (index // 2) * 28
            button.place(x=x, y=y, width=155, height=26)
            self.difficulty_buttons.append(button)

        # 362..525: fixed status/action card.
        action_card = self._card(sidebar, width=348, height=164, padding=12)
        action_card.place(x=0, y=362, width=348, height=164)
        action_content = action_card.content  # type: ignore[attr-defined]

        stats = tk.Frame(action_content, width=322, height=52, bg=Theme.PANEL)
        stats.place(x=0, y=0, width=322, height=52)
        stats.pack_propagate(False)
        self._mini_stat(stats, 0, "命中次数", self.stage_var, Theme.TEXT)
        self._mini_stat(stats, 109, "当前本金", self.potential_var, Theme.CYAN)
        self._mini_stat(stats, 218, "当前赔率", self.risk_var, Theme.RED)

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
            text="打下锤子  ↓",
            command=self.advance,
            background=Theme.ACCENT,
            hover_background=Theme.ACCENT_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.advance_button.place_forget()

        self.random_strike_button = ModernButton(
            self.button_frame,
            text="随机打下",
            command=self.random_strike,
            background=Theme.ACCENT,
            hover_background=Theme.ACCENT_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.random_strike_button.place_forget()

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
            text="命中后可继续挑战或立即兑现\n可累积获胜赔率直到兑现。",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 13),
            justify=tk.LEFT,
            anchor=tk.W,
            wraplength=318,
        ).place(x=0, y=4, width=322, height=58)

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
        """Strike the clicked one of seven fixed mole holes."""
        if not self.game_active or self.animation_in_progress or self.result_effect_active:
            return
        canvas_x = self.game_canvas.canvasx(event.x)
        canvas_y = self.game_canvas.canvasy(event.y)
        hole = self._hole_at(canvas_x, canvas_y)
        if hole is not None:
            self.strike_hole(hole)

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

    def _format_progress_notice(self) -> str:
        return f"已打中{self.successful_hits}次，兑现金额: ${self.round_principal:.2f}"

    def set_difficulty(self, difficulty):
        if self.game_active:
            return
        self.difficulty = difficulty
        self._refresh_difficulty_styles()
        self.update_display()

    def _refresh_difficulty_styles(self) -> None:
        for index, (_name, value, _detail) in enumerate(DIFFICULTIES):
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
        self.risk_var.set(f"{settings['odds']:.2f}:1")

        if self.game_active:
            self.stage_var.set(f"命中 {self.successful_hits}")
            self.potential_var.set(f"${self.round_principal:.2f}")
        else:
            self.stage_var.set("待开始")
            self.potential_var.set("$0.00")

        self.info_var.set(self.notice_message or "选择下注金额与难度，然后开始游戏")
        self.draw_game()

    # ------------------------------------------------------------------
    # Board rendering
    # ------------------------------------------------------------------

    def ensure_chicken_visible(self):
        # The whack-a-mole board is fixed-width and never scrolls horizontally.
        self.game_canvas.xview_moveto(0)

    def draw_game(self):
        self.game_canvas.delete("all")
        self.game_canvas.configure(scrollregion=(0, 0, self.CANVAS_WIDTH, self.CANVAS_HEIGHT))
        self._draw_mole_board(show_ready=not self.game_active)

    def _hole_geometry(self):
        """Return fixed centres for seven holes in a 4+3 layout."""
        top_y, bottom_y = 220, 390
        top_x = (105, 285, 465, 645)
        bottom_x = (195, 375, 555)
        return [(x, top_y) for x in top_x] + [(x, bottom_y) for x in bottom_x]

    def _hole_at(self, x, y):
        for index, (cx, cy) in enumerate(self._hole_geometry()):
            dx = (x - cx) / 65.0
            dy = (y - cy) / 34.0
            if dx * dx + dy * dy <= 1.0:
                return index
        return None

    def _load_hammer_sprite(self):
        """Load the exact uploaded hammer line-art embedded in this file."""
        self.hammer_sprite_source = None
        self.hammer_sprite_cache = {}
        if Image is None or ImageTk is None:
            return
        try:
            raw = base64.b64decode(HAMMER_ICON_PNG_B64)
            self.hammer_sprite_source = Image.open(io.BytesIO(raw)).convert("RGBA")
        except Exception:
            self.hammer_sprite_source = None

    def _get_hammer_sprite(self, width, height):
        """Return a cached Tk image of the embedded hammer at the requested size."""
        if self.hammer_sprite_source is None or Image is None or ImageTk is None:
            return None
        key = (int(width), int(height))
        sprite = self.hammer_sprite_cache.get(key)
        if sprite is None:
            resized = self.hammer_sprite_source.resize(key, Image.LANCZOS)
            sprite = ImageTk.PhotoImage(resized)
            self.hammer_sprite_cache[key] = sprite
        return sprite

    def _draw_farm_background(self, w, h):
        self.game_canvas.create_rectangle(0, 0, w, h, fill="#C9E8F0", outline="")
        self.game_canvas.create_oval(w - 145, 18, w - 75, 88, fill="#F6D56B", outline="")
        for cx, cy in ((110, 44), (238, 58), (520, 42)):
            self.game_canvas.create_oval(cx - 34, cy - 16, cx + 4, cy + 14, fill="#F7FBFD", outline="")
            self.game_canvas.create_oval(cx - 4, cy - 22, cx + 34, cy + 14, fill="#F7FBFD", outline="")
            self.game_canvas.create_oval(cx + 18, cy - 14, cx + 56, cy + 14, fill="#F7FBFD", outline="")

        self.game_canvas.create_polygon(0, 118, 90, 98, 180, 116, 280, 94, 390, 114, 500, 93, 620, 115, w, 104, w, 168, 0, 168,
                                        fill="#9BC37C", outline="")
        self.game_canvas.create_polygon(0, 168, w, 168, w, 232, 0, 216, fill="#DAB96A", outline="")
        self.game_canvas.create_polygon(0, 204, w, 220, w, h, 0, h, fill=Theme.GRASS, outline="")
        for x in range(-20, w + 40, 48):
            self.game_canvas.create_line(x, 172, x + 26, 218, fill="#C89E4F", width=2)

        fence_y = 157
        self.game_canvas.create_line(0, fence_y, w, fence_y, fill="#B0814B", width=4)
        for x in range(28, w, 54):
            self.game_canvas.create_line(x, fence_y - 16, x, fence_y + 18, fill="#B0814B", width=5)

        barn_x, barn_y = 558, 108
        self.game_canvas.create_rectangle(barn_x, barn_y, barn_x + 92, barn_y + 62, fill="#C75F50", outline="#93433A", width=2)
        self.game_canvas.create_polygon(barn_x - 8, barn_y, barn_x + 46, barn_y - 30, barn_x + 100, barn_y,
                                        fill="#894B44", outline="#6A3732", width=2)
        self.game_canvas.create_rectangle(barn_x + 34, barn_y + 28, barn_x + 58, barn_y + 62, fill="#F2E8D6", outline="#A78D6C")

    def _draw_mole(self, cx, cy, rise, *, dizzy=False, phase=0):
        wobble = 0
        if dizzy:
            wobble = (-1) ** phase * min(8, 2 + phase)
        body_y = cy + 26 - 76 * rise
        cx = cx + wobble
        fur_main = "#8C5D3C"
        fur_shadow = "#6E472E"
        belly = "#C98D67"
        ear_inner = "#E2B297"

        self.game_canvas.create_oval(cx - 40, body_y + 18, cx + 40, body_y + 56,
                                     fill="#5A3928", outline="")
        self.game_canvas.create_oval(cx - 32, body_y - 30, cx - 10, body_y - 6,
                                     fill=fur_main, outline=fur_shadow, width=2)
        self.game_canvas.create_oval(cx + 10, body_y - 30, cx + 32, body_y - 6,
                                     fill=fur_main, outline=fur_shadow, width=2)
        self.game_canvas.create_oval(cx - 25, body_y - 23, cx - 14, body_y - 11,
                                     fill=ear_inner, outline="")
        self.game_canvas.create_oval(cx + 14, body_y - 23, cx + 25, body_y - 11,
                                     fill=ear_inner, outline="")
        self.game_canvas.create_oval(cx - 39, body_y - 18, cx + 39, body_y + 48,
                                     fill=fur_main, outline=fur_shadow, width=2)
        self.game_canvas.create_oval(cx - 27, body_y + 4, cx + 27, body_y + 40,
                                     fill=belly, outline="")

        if dizzy:
            for ex in (-17, 17):
                r = 7
                self.game_canvas.create_arc(cx + ex - r, body_y - 8 - r, cx + ex + r, body_y - 8 + r,
                                            start=phase * 30, extent=270, style=tk.ARC,
                                            outline="#111", width=2)
                self.game_canvas.create_arc(cx + ex - (r - 3), body_y - 8 - (r - 3), cx + ex + (r - 3), body_y - 8 + (r - 3),
                                            start=40 + phase * 30, extent=220, style=tk.ARC,
                                            outline="#111", width=2)
        else:
            self.game_canvas.create_oval(cx - 24, body_y - 6, cx - 12, body_y + 6, fill="#111", outline="")
            self.game_canvas.create_oval(cx + 12, body_y - 6, cx + 24, body_y + 6, fill="#111", outline="")
            self.game_canvas.create_oval(cx - 19, body_y - 2, cx - 16, body_y + 1, fill="#F2F2F2", outline="")
            self.game_canvas.create_oval(cx + 17, body_y - 2, cx + 20, body_y + 1, fill="#F2F2F2", outline="")

        self.game_canvas.create_line(cx - 26, body_y - 12, cx - 10, body_y - 16, fill=fur_shadow, width=2)
        self.game_canvas.create_line(cx + 10, body_y - 16, cx + 26, body_y - 12, fill=fur_shadow, width=2)
        self.game_canvas.create_oval(cx - 10, body_y + 6, cx + 10, body_y + 20,
                                     fill="#E8B18D", outline="#C98D67")
        self.game_canvas.create_line(cx, body_y + 19, cx, body_y + 27, fill=fur_shadow, width=2)
        self.game_canvas.create_arc(cx - 14, body_y + 19, cx + 1, body_y + 31,
                                    start=200, extent=110, style=tk.ARC, outline=fur_shadow, width=2)
        self.game_canvas.create_arc(cx - 1, body_y + 19, cx + 14, body_y + 31,
                                    start=230, extent=110, style=tk.ARC, outline=fur_shadow, width=2)
        self.game_canvas.create_rectangle(cx - 6, body_y + 24, cx - 1, body_y + 31,
                                          fill="#F6F0E8", outline="")
        self.game_canvas.create_rectangle(cx + 1, body_y + 24, cx + 6, body_y + 31,
                                          fill="#F6F0E8", outline="")
        self.game_canvas.create_oval(cx - 23, body_y + 34, cx - 5, body_y + 48,
                                     fill=fur_shadow, outline="")
        self.game_canvas.create_oval(cx + 5, body_y + 34, cx + 23, body_y + 48,
                                     fill=fur_shadow, outline="")
        for dx in (18, 24, 30):
            self.game_canvas.create_line(cx - 9, body_y + 16, cx - dx, body_y + 12 - (dx - 18) / 6,
                                         fill="#EEE7DC", width=1.5)
            self.game_canvas.create_line(cx + 9, body_y + 16, cx + dx, body_y + 12 - (dx - 18) / 6,
                                         fill="#EEE7DC", width=1.5)

        if dizzy:
            for idx, (sx, sy) in enumerate(((cx - 30, body_y - 36), (cx, body_y - 48), (cx + 31, body_y - 34))):
                offset = 4 if (phase + idx) % 2 == 0 else -4
                self.game_canvas.create_text(sx, sy + offset, text="✦", fill="#F0C44D",
                                             font=(Theme.FONT, 12, "bold"))
            self.game_canvas.create_text(cx, body_y - 62, text="命中", fill=Theme.RED,
                                         font=(Theme.FONT_CJK, 11, "bold"))

    def _draw_hammer(self, cx, cy, progress):
        sprite = self._get_hammer_sprite(92, 90)
        if sprite is not None:
            draw_x = cx + 16 - 10 * progress
            draw_y = cy - 98 + 105 * progress
            self.game_canvas.create_image(draw_x, draw_y, image=sprite)
        else:
            # Fallback line drawing if Pillow is unavailable.
            base_x = cx + 26 - 10 * progress
            base_y = cy - 92 + 96 * progress
            amber = "#B97A1E"
            self.game_canvas.create_line(base_x + 46, base_y - 66, base_x - 6, base_y - 14,
                                         fill=amber, width=11, capstyle=tk.ROUND)
            self.game_canvas.create_line(base_x + 46, base_y - 66, base_x - 6, base_y - 14,
                                         fill=Theme.PANEL, width=5, capstyle=tk.ROUND)
            self.game_canvas.create_line(base_x + 14, base_y - 36, base_x - 8, base_y - 58, base_x - 21, base_y - 46,
                                         fill=amber, width=5, joinstyle=tk.ROUND, capstyle=tk.ROUND)
            self.game_canvas.create_line(base_x - 2, base_y - 24, base_x - 26, base_y - 48,
                                         fill=amber, width=5, capstyle=tk.ROUND)
            self.game_canvas.create_line(base_x + 14, base_y - 36, base_x + 26, base_y - 48, base_x + 8, base_y - 66,
                                         fill=amber, width=5, joinstyle=tk.ROUND, capstyle=tk.ROUND)
            self.game_canvas.create_line(base_x + 18, base_y - 18, base_x - 10, base_y - 46,
                                         fill=amber, width=5, capstyle=tk.ROUND)
        if progress > 0.84:
            self.game_canvas.create_text(cx, cy - 88, text="BAM!", fill=Theme.RED,
                                         font=(Theme.FONT, 16, "bold"))

    def _draw_mole_board(self, show_ready=False):
        w, h = self.CANVAS_WIDTH, self.CANVAS_HEIGHT
        self._draw_farm_background(w, h)

        title = "准备打地鼠" if show_ready else "请选择一个鼠洞"
        subtitle = "先选择筹码与难度，再开始" if show_ready else "锤子落下时，老鼠会从本轮随机洞内升起"
        self.game_canvas.create_text(w / 2, 40, text=title, fill=Theme.TEXT,
                                     font=(Theme.FONT_CJK, 20, "bold"))
        self.game_canvas.create_text(w / 2, 67, text=subtitle, fill=Theme.TEXT_MUTED,
                                     font=(Theme.FONT_CJK, 10))

        active = self.active_mole_holes if self.game_active else set()
        for cx, cy in self._hole_geometry():
            self.game_canvas.create_oval(cx - 90, cy - 34, cx + 90, cy + 44,
                                         fill="#C89459", outline="")
            self.game_canvas.create_oval(cx - 70, cy - 24, cx + 70, cy + 30,
                                         fill="#56392B", outline="#362219", width=2)
            self.game_canvas.create_arc(cx - 80, cy - 8, cx + 80, cy + 44,
                                        start=0, extent=180, style=tk.ARC,
                                        outline="#DDB583", width=2)

        if self.animation_in_progress:
            for i, (cx, cy) in enumerate(self._hole_geometry()):
                if i in active:
                    rise = max(0.0, min(1.0, self.mole_progress))
                    self._draw_mole(cx, cy, rise)

        if self.result_effect_active and self.resolved_hole is not None:
            cx, cy = self._hole_geometry()[self.resolved_hole]
            self._draw_mole(cx, cy, 1.0, dizzy=True, phase=self.result_effect_phase)

        if self.animation_in_progress and self.selected_hole is not None:
            cx, cy = self._hole_geometry()[self.selected_hole]
            self._draw_hammer(cx, cy, max(0.0, min(1.0, self.hammer_progress)))

    # ------------------------------------------------------------------
    # Game mechanics — same flow and formulas as the original
    # ------------------------------------------------------------------

    def _roll_mole_group(self):
        count = self.difficulty_settings[self.difficulty]["moles"]
        self.active_mole_holes = set(random.sample(range(self.total_holes), count))

    def start_game(self):
        if self.current_bet <= 0:
            messagebox.showwarning("错误", "请先下注")
            return
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注")
            return

        self.bet_amount = self.current_bet
        self.round_principal = self.bet_amount
        self.balance -= self.bet_amount
        self.successful_hits = 0
        self.current_stage = 0
        self.game_active = True
        self.animation_in_progress = False
        self.hit_result = None
        self.selected_hole = None
        self.notice_message = "选择下注金额与难度，然后开始游戏"
        self._roll_mole_group()
        update_balance_in_json(self.username, self.balance)

        self.start_button.config(state=tk.DISABLED)
        self.start_button.place_forget()
        self.reset_bet_button.place_forget()
        self.advance_button.place_forget()
        self.random_strike_button.place(
            x=0, y=0, width=self.ACTION_BUTTON_WIDTH, height=self.ACTION_BUTTON_HEIGHT
        )
        self.random_strike_button.config(state=tk.NORMAL)
        self.cash_out_button.place(
            x=0, y=42, width=self.ACTION_BUTTON_WIDTH, height=self.ACTION_BUTTON_HEIGHT
        )
        self.cash_out_button.config(state=tk.DISABLED)
        for button in self.chip_buttons:
            button.configure(state=tk.DISABLED)
        for button in self.difficulty_buttons:
            button.configure(state=tk.DISABLED)
        self.update_display()

    def random_strike(self):
        if not self.game_active or self.animation_in_progress or self.result_effect_active:
            return
        self.strike_hole(random.randrange(self.total_holes))

    def advance(self):
        """Keyboard/button-compatible legacy entry point; board click or random strike is used."""
        return

    def strike_hole(self, hole_index):
        if not self.game_active or self.animation_in_progress or self.result_effect_active:
            return
        if not 0 <= hole_index < self.total_holes:
            return
        self.selected_hole = hole_index
        self.resolved_hole = hole_index
        self.hit_result = None
        self.animation_in_progress = True
        self.result_effect_active = False
        self.result_effect_phase = 0
        self.hammer_progress = 0.0
        self.mole_progress = 0.0
        self.random_strike_button.config(state=tk.DISABLED)
        self.cash_out_button.config(state=tk.DISABLED)
        self._animate_strike(0)

    def _animate_strike(self, frame):
        frames = 10
        if frame < frames:
            progress = frame / (frames - 1)
            self.hammer_progress = progress
            # Moles rise slightly ahead of hammer impact, then stay visible for resolution.
            self.mole_progress = min(1.0, progress * 1.35)
            self.update_display()
            self.turn_animation_job = self.root.after(45, lambda: self._animate_strike(frame + 1))
            return

        hit = self.selected_hole in self.active_mole_holes
        self.hit_result = hit
        self.animation_in_progress = False
        self.turn_animation_job = None

        if hit:
            odds = self.difficulty_settings[self.difficulty]["odds"]
            self.round_principal *= (1.0 + odds)
            self.successful_hits += 1
            self.current_stage = self.successful_hits
            self.notice_message = self._format_progress_notice()
            self.result_effect_active = True
            self.result_effect_phase = 0
            self.update_display()
            self._animate_hit_effect(0)
        else:
            self.round_principal = 0.0
            self.last_win = 0.0
            self.notice_message = "打偏了，送您好运！"
            self.update_display()
            self.root.after(700, self._finish_loss)

    def _animate_hit_effect(self, frame):
        total_frames = 8
        if frame < total_frames:
            self.result_effect_active = True
            self.result_effect_phase = frame
            self.update_display()
            self.result_effect_job = self.root.after(90, lambda: self._animate_hit_effect(frame + 1))
            return

        self.result_effect_active = False
        self.result_effect_job = None
        self.result_effect_phase = 0
        self._roll_mole_group()
        self.random_strike_button.config(state=tk.NORMAL)
        self.cash_out_button.config(state=tk.NORMAL)
        self.update_display()

    def _finish_loss(self):
        self.game_active = False
        self.active_mole_holes = set()
        self.update_display()
        self.end_game(reset_notice=False)

    def cash_out(self):
        if not self.game_active or self.animation_in_progress or self.result_effect_active or self.successful_hits <= 0:
            return
        win_amount = self.round_principal
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        self.active_mole_holes = set()
        self.notice_message = f"已兑现${win_amount:.2f}，恭喜获胜！"
        update_balance_in_json(self.username, self.balance)
        self.update_display()
        self.show_fireworks()
        self.root.after(1200, lambda: self.end_game(reset_notice=False))

    def complete_game(self):
        # Kept for compatibility with the original host; this game has no fixed final stage.
        if self.game_active and self.successful_hits > 0:
            self.cash_out()

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

    def end_game(self, *, reset_notice=True):
        self.animation_in_progress = False
        self.hit_result = None
        self.selected_hole = None
        self.hammer_progress = 0.0
        self.mole_progress = 0.0
        self.active_mole_holes = set()
        self.resolved_hole = None
        self.result_effect_active = False
        self.result_effect_phase = 0
        if self.turn_animation_job is not None:
            try:
                self.root.after_cancel(self.turn_animation_job)
            except tk.TclError:
                pass
            self.turn_animation_job = None
        if self.result_effect_job is not None:
            try:
                self.root.after_cancel(self.result_effect_job)
            except tk.TclError:
                pass
            self.result_effect_job = None
        if reset_notice:
            self.notice_message = "选择下注金额与难度，然后开始游戏"
        self.round_principal = 0.0
        self.successful_hits = 0
        self.start_button.config(state=tk.NORMAL)
        self.start_button.place(
            x=0, y=42, width=self.ACTION_BUTTON_WIDTH, height=self.ACTION_BUTTON_HEIGHT
        )
        self.advance_button.place_forget()
        self.random_strike_button.place_forget()
        self.random_strike_button.config(state=tk.NORMAL)
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
            title="打地鼠",
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