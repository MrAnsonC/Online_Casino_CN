"""Thimbles HMI — ChickenCrossing visual-system edition.

The original three-cup gameplay is retained: choose one or two balls, place a
bet, watch the cups reveal the balls, shuffle, choose a cup, and settle using
the original 2.88x / 1.44x payout multipliers.  The UI is rebuilt to match the
warm fixed-size ChickenCrossing HMI and supports the single-Tk EmbeddedGamePage
mode used by small_games.py.
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

try:
    from .small_games import EmbeddedGamePage
except ImportError:
    from small_games import EmbeddedGamePage

VERSION = "Thimbles-ChickenStyle-R3-FinalLoweringBallOcclusion"


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

    TABLE = "#AFC4B1"
    TABLE_EDGE = "#6F8D71"
    # Japanese yunomi / porcelain palette.
    CUP = "#F3EFE4"
    CUP_SIDE = "#DDD6C8"
    CUP_RIM = "#355D78"
    CUP_PATTERN = "#4E7892"
    CUP_PATTERN_SOFT = "#C7DCE6"
    CUP_SEAL = "#B65C50"
    CUP_SELECTED = "#D9ECF4"
    CUP_SELECTED_EDGE = "#4D839D"
    BALL = "#E4B84A"
    BALL_EDGE = "#8C6A22"

    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )
    FONT_EMOJI = "Segoe UI Emoji"


ODDS = {1: 2.88, 2: 1.44}
BALL_MODES = (
    ("1 个球", 1, "猜中 1 个藏球杯 · 返还 2.88×"),
    ("2 个球", 2, "3 杯中有 2 杯藏球 · 返还 1.44×"),
)
CHIP_CONFIGS = (
    ("$5", "5", "#D75A54", "white"),
    ("$25", "25", "#67B56A", "black"),
    ("$100", "100", "#292929", "white"),
    ("$500", "500", "#D47AB7", "black"),
    ("$1K", "1000", "#F4F1EA", "black"),
)


def get_data_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../saving_data.json")


def load_user_data() -> list:
    path = get_data_file_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_user_data(users: list) -> None:
    with open(get_data_file_path(), "w", encoding="utf-8") as file:
        json.dump(users, file, ensure_ascii=False, indent=4)


def update_balance_in_json(username: str, new_balance: float) -> None:
    users = load_user_data()
    for user in users:
        if user.get("user_name") == username:
            user["cash"] = f"{new_balance:.2f}"
            break
    else:
        users.append({"user_name": username, "cash": f"{new_balance:.2f}"})
    try:
        save_user_data(users)
    except OSError:
        pass


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
    """Chicken-style physical poker chip."""

    def __init__(
        self,
        master,
        *,
        label: str,
        amount: str,
        chip_color: str,
        text_color: str,
        command: Callable[[str], None],
        width: int = 57,
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
        self.bind("<Key-space>", self._keyboard_activate)
        self.bind("<Return>", self._keyboard_activate)
        self.draw()

    @staticmethod
    def _shade(hex_color: str, factor: float) -> str:
        if not hex_color.startswith("#") or len(hex_color) != 7:
            return "#4A4A4A"
        rgb = [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]
        rgb = [max(0, min(255, round(c * factor))) for c in rgb]
        return "#%02x%02x%02x" % tuple(rgb)

    def draw(self) -> None:
        self.delete("all")
        offset_y = 3 if self._pressed else 0
        disabled = self._state == tk.DISABLED
        outer = self._shade(self.chip_color, 0.68)
        inner = self._shade(self.chip_color, 0.86)
        outline = Theme.ACCENT if self._flash else (Theme.TEXT if self._hovered else outer)
        outline_width = 3 if (self._flash or self._hovered) else 2

        self.create_oval(8, 7, self.control_width - 7, self.control_height - 1,
                         fill="#8E877E", outline="")
        self.create_oval(7, 3 + offset_y, self.control_width - 8,
                         self.control_height - 5 + offset_y,
                         fill=outer, outline=outline, width=outline_width)
        self.create_oval(11, 7 + offset_y, self.control_width - 12,
                         self.control_height - 9 + offset_y,
                         fill=self.chip_color, outline=inner, width=2)

        cx = self.control_width / 2
        cy = (self.control_height - 2) / 2 + offset_y
        for x1, y1, x2, y2 in (
            (cx - 3, 4 + offset_y, cx + 3, 10 + offset_y),
            (cx - 3, self.control_height - 12 + offset_y, cx + 3,
             self.control_height - 6 + offset_y),
            (8, cy - 3, 14, cy + 3),
            (self.control_width - 15, cy - 3, self.control_width - 9, cy + 3),
        ):
            self.create_rectangle(x1, y1, x2, y2, fill=self.text_color, outline="")

        self.create_text(
            cx,
            cy,
            text=self.label,
            fill=self.text_color,
            font=(Theme.FONT, 9 if len(self.label) <= 4 else 8, "bold"),
        )

        if disabled:
            self.create_oval(
                7, 3 + offset_y, self.control_width - 8, self.control_height - 5 + offset_y,
                fill="#C9C2B8", outline=Theme.BORDER_SOFT, width=1, stipple="gray50",
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

    def _keyboard_activate(self, _event) -> str:
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
            super().configure(cursor="" if state == tk.DISABLED else "hand2")
            self.draw()
        if cnf is not None or kwargs:
            return super().configure(cnf, **kwargs)
        return None

    config = configure


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


class ThimblesGame:
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
    CANVAS_HEIGHT = 556
    ACTION_BUTTON_HEIGHT = 38

    CUP_BASE_Y = 430
    CUP_LIFT_Y = 292
    CUP_WIDTH = 128
    CUP_HEIGHT = 166
    BALL_Y = 410
    CUP_XS = (155, 373, 591)

    def __init__(self, root, initial_balance, username):
        self.root = root
        self._configure_root()

        self.balance = float(initial_balance)
        self.username = username
        self.current_bet = 0.0
        self.bet_amount = 0.0
        self.ball_count = 1
        self.ball_position: list[int] = []
        self.selected_cup = -1
        self.last_win = 0.0
        self.game_state = "idle"

        # cup_positions stores slot coordinates (0..2), not pixels.
        self.cup_positions = [0.0, 1.0, 2.0]
        self.cup_targets = [0.0, 1.0, 2.0]
        self.cup_y_positions = [float(self.CUP_BASE_Y)] * 3
        self.selected_highlight: Optional[int] = None

        self._after_jobs: set[str] = set()
        self._motion_start: Optional[float] = None
        self._motion_duration = 0.0
        self._motion_from: list[float] = []
        self._motion_to: list[float] = []
        self._motion_callback: Optional[Callable[[], None]] = None

        self.chip_buttons: list[ChipButton] = []
        self.ball_mode_buttons: list[ModernButton] = []

        self.create_widgets()
        self.update_display()

    # ------------------------------------------------------------------
    # UI shell
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("三杯球游戏")
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
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

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
        inner_width = max(1, width - 2 * (padding + 1))
        inner_height = max(1, height - 2 * (padding + 1))
        inner = tk.Frame(outer, width=inner_width, height=inner_height, bg=Theme.PANEL)
        inner.place(x=padding + 1, y=padding + 1, width=inner_width, height=inner_height)
        inner.pack_propagate(False)
        inner.grid_propagate(False)
        outer.content = inner  # type: ignore[attr-defined]
        return outer

    @staticmethod
    def _section_title(master, title: str, subtitle: str = "", *, width: int) -> None:
        tk.Label(
            master,
            text=title,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 16, "bold"),
            anchor=tk.W,
        ).place(x=0, y=0, width=width, height=22)
        if subtitle:
            tk.Label(
                master,
                text=subtitle,
                bg=Theme.PANEL,
                fg=Theme.TEXT_MUTED,
                font=(Theme.FONT_CJK, 8),
                anchor=tk.W,
            ).place(x=0, y=22, width=width, height=17)

    def _mini_stat(self, master, x: int, label: str, variable: tk.StringVar, color: str) -> None:
        box = tk.Frame(
            master,
            width=104,
            height=52,
            bg=Theme.PANEL_ALT,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        box.place(x=x, y=0, width=104, height=52)
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

    def create_widgets(self) -> None:
        self.balance_var = tk.StringVar(value=f"${self.balance:.2f}")
        self.bet_var = tk.StringVar(value="$0.00")
        self.last_win_var = tk.StringVar(value="$0.00")
        self.mode_var = tk.StringVar(value="1 个球")
        self.odds_var = tk.StringVar(value="×2.88")
        self.stage_var = tk.StringVar(value="待开始")
        self.info_var = tk.StringVar(value="选择下注金额和球数，然后开始三杯挑战。")
        self.badge_var = tk.StringVar(value="1 个球 · 返还 2.88×")

        shell = tk.Frame(self.root, width=self.SHELL_WIDTH, height=self.SHELL_HEIGHT, bg=Theme.APP_BG)
        shell.pack(padx=20, pady=18)
        shell.pack_propagate(False)
        shell.grid_propagate(False)

        self._build_header(shell)

        body = tk.Frame(shell, width=self.SHELL_WIDTH, height=self.BODY_HEIGHT, bg=Theme.APP_BG)
        body.place(x=0, y=self.BODY_TOP, width=self.SHELL_WIDTH, height=self.BODY_HEIGHT)
        body.pack_propagate(False)
        body.grid_propagate(False)
        self._build_game_panel(body)
        self._build_control_panel(body)

    def _build_header(self, master) -> None:
        header = tk.Frame(master, width=self.SHELL_WIDTH, height=self.HEADER_HEIGHT, bg=Theme.APP_BG)
        header.place(x=0, y=0, width=self.SHELL_WIDTH, height=self.HEADER_HEIGHT)

        tk.Label(
            header,
            text="●",
            bg=Theme.APP_BG,
            fg=Theme.AMBER,
            font=(Theme.FONT, 25, "bold"),
            anchor=tk.CENTER,
        ).place(x=0, y=7, width=42, height=44)
        tk.Label(
            header,
            text="THIMBLES",
            bg=Theme.APP_BG,
            fg=Theme.TEXT,
            font=(Theme.FONT, 20, "bold"),
            anchor=tk.W,
        ).place(x=52, y=4, width=430, height=31)
        tk.Label(
            header,
            text="三杯球游戏",
            bg=Theme.APP_BG,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 10),
            anchor=tk.W,
        ).place(x=52, y=37, width=520, height=22)

        balance_box = tk.Frame(
            header,
            width=270,
            height=54,
            bg=Theme.PANEL,
            highlightthickness=1,
            highlightbackground=Theme.BORDER,
        )
        balance_box.place(x=840, y=8, width=270, height=54)
        self.balance_display_var = tk.StringVar(value=f"账户余额: {self.balance_var.get()}")

        def sync_balance(*_args) -> None:
            self.balance_display_var.set(f"账户余额: {self.balance_var.get()}")

        self.balance_var.trace_add("write", sync_balance)
        tk.Label(
            balance_box,
            textvariable=self.balance_display_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 13, "bold"),
            anchor=tk.E,
        ).place(x=12, y=8, width=246, height=38)

    def _build_game_panel(self, master) -> None:
        panel = self._card(master, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT, padding=0)
        panel.place(x=0, y=0, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT)
        content = panel.content  # type: ignore[attr-defined]

        top = tk.Frame(content, width=self.CANVAS_WIDTH, height=74, bg=Theme.PANEL)
        top.place(x=0, y=0, width=self.CANVAS_WIDTH, height=74)
        tk.Label(
            top,
            textvariable=self.info_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 17, "bold"),
            anchor=tk.W,
        ).place(x=18, y=18, width=540, height=36)
        tk.Label(
            top,
            textvariable=self.badge_var,
            bg=Theme.ACCENT_SOFT,
            fg=Theme.ACCENT,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.CENTER,
        ).place(x=572, y=19, width=154, height=32)

        canvas_wrap = tk.Frame(content, width=self.CANVAS_WIDTH, height=556, bg=Theme.CANVAS_BG)
        canvas_wrap.place(x=0, y=74, width=self.CANVAS_WIDTH, height=556)
        self.game_canvas = tk.Canvas(
            canvas_wrap,
            width=self.CANVAS_WIDTH,
            height=self.CANVAS_HEIGHT,
            bg=Theme.CANVAS_BG,
            bd=0,
            highlightthickness=0,
        )
        self.game_canvas.place(x=0, y=0, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT)
        self.game_canvas.bind("<Button-1>", self._on_canvas_click)
        self.game_canvas.bind("<Motion>", self._on_canvas_motion)
        self.game_canvas.bind("<Leave>", lambda _e: self._hover_cup(None))

    def _build_control_panel(self, master) -> None:
        sidebar_x = self.GAME_PANEL_WIDTH + self.PANEL_GAP
        sidebar = tk.Frame(master, width=self.SIDEBAR_WIDTH, height=self.BODY_HEIGHT, bg=Theme.APP_BG)
        sidebar.place(x=sidebar_x, y=0, width=self.SIDEBAR_WIDTH, height=self.BODY_HEIGHT)

        MetricTile(sidebar, "当前下注", self.bet_var, Theme.CYAN, width=169, height=68).place(
            x=0, y=0, width=169, height=68
        )
        MetricTile(sidebar, "上局获胜", self.last_win_var, Theme.GREEN, width=169, height=68).place(
            x=179, y=0, width=169, height=68
        )

        bet_card = self._card(sidebar, width=348, height=120, padding=12)
        bet_card.place(x=0, y=78, width=348, height=120)
        bet_content = bet_card.content  # type: ignore[attr-defined]
        self._section_title(bet_content, "下注金额", "选择筹码累计本局下注", width=322)
        chip_width = 57
        chip_gap = 9
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

        mode_card = self._card(sidebar, width=348, height=116, padding=12)
        mode_card.place(x=0, y=208, width=348, height=116)
        mode_content = mode_card.content  # type: ignore[attr-defined]
        self._section_title(mode_content, "藏球模式", "球越少，猜中赔率越高", width=322)
        for index, (name, value, detail) in enumerate(BALL_MODES):
            button = ModernButton(
                mode_content,
                text=f"{name}  ·  ×{ODDS[value]:.2f}",
                command=lambda v=value: self.set_ball_count(v),
                background=Theme.PANEL_HOVER,
                hover_background=Theme.BORDER_SOFT,
                foreground=Theme.TEXT,
                font_size=12,
                bold=True,
            )
            button.place(x=index * 164, y=48, width=154, height=38)
            self.ball_mode_buttons.append(button)

        action_card = self._card(sidebar, width=348, height=176, padding=12)
        action_card.place(x=0, y=334, width=348, height=176)
        action_content = action_card.content  # type: ignore[attr-defined]

        stats = tk.Frame(action_content, width=322, height=52, bg=Theme.PANEL)
        stats.place(x=0, y=0, width=322, height=52)
        self._mini_stat(stats, 0, "球数", self.mode_var, Theme.TEXT)
        self._mini_stat(stats, 109, "赔率", self.odds_var, Theme.CYAN)
        self._mini_stat(stats, 218, "阶段", self.stage_var, Theme.ACCENT)

        button_frame = tk.Frame(action_content, width=322, height=90, bg=Theme.PANEL)
        button_frame.place(x=0, y=60, width=322, height=90)
        self.reset_bet_button = ModernButton(
            button_frame,
            text="清空全部筹码",
            command=self.reset_bet,
            background=Theme.RED,
            hover_background=Theme.RED_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.reset_bet_button.place(x=0, y=0, width=322, height=self.ACTION_BUTTON_HEIGHT)
        self.start_button = ModernButton(
            button_frame,
            text="开始游戏",
            command=self.start_game,
            background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.start_button.place(x=0, y=44, width=322, height=self.ACTION_BUTTON_HEIGHT)

        footer = self._card(sidebar, width=348, height=110, padding=12)
        footer.place(x=0, y=520, width=348, height=110)
        footer_content = footer.content  # type: ignore[attr-defined]
        tk.Label(
            footer_content,
            text="玩法说明",
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 13, "bold"),
            anchor=tk.W,
        ).place(x=0, y=0, width=322, height=22)
        tk.Label(
            footer_content,
            text="先记住球的位置，再观察杯子洗牌。洗牌结束后点击任意杯子；猜中即按所选模式赔率返还。",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9),
            justify=tk.LEFT,
            anchor=tk.NW,
            wraplength=318,
        ).place(x=0, y=30, width=322, height=54)

        self._refresh_mode_styles()

    # ------------------------------------------------------------------
    # State / display
    # ------------------------------------------------------------------

    def _stage_text(self) -> str:
        return {
            "idle": "待开始",
            "showing_balls": "记忆球位",
            "lowering": "落杯",
            "shuffling": "洗杯中",
            "waiting_selection": "请选择",
            "revealing": "揭晓中",
            "showing_all": "结算",
        }.get(self.game_state, self.game_state)

    def _status_text(self) -> str:
        if self.game_state == "idle":
            return "选择下注金额和球数，然后开始三杯挑战。"
        if self.game_state == "showing_balls":
            return "记住球的位置，然后观察杯子的移动。"
        if self.game_state == "lowering":
            return "杯子正在落下，请继续记住位置。"
        if self.game_state == "shuffling":
            return "杯子正在洗牌 · 眼睛不要离开。"
        if self.game_state == "waiting_selection":
            return "洗牌完成 · 点击你认为藏有球的杯子。"
        if self.game_state == "revealing":
            return "正在揭晓你选择的杯子……"
        if self.game_state == "showing_all":
            if self.selected_cup in self.ball_position:
                return f"猜中了 · 本局返还 ${self.last_win:.2f}"
            return "没有猜中 · 本局未获得返还。"
        return "三杯挑战"

    def update_display(self) -> None:
        self.balance_var.set(f"${self.balance:.2f}")
        self.bet_var.set(f"${self.current_bet:.2f}")
        self.last_win_var.set(f"${self.last_win:.2f}")
        self.mode_var.set(f"{self.ball_count} 个球")
        self.odds_var.set(f"×{ODDS[self.ball_count]:.2f}")
        self.stage_var.set(self._stage_text())
        self.info_var.set(self._status_text())
        self.badge_var.set(f"{self.ball_count} 个球 · 返还 {ODDS[self.ball_count]:.2f}×")
        self._refresh_mode_styles()
        self.draw_game()

    def _refresh_mode_styles(self) -> None:
        for index, button in enumerate(self.ball_mode_buttons):
            value = BALL_MODES[index][1]
            if value == self.ball_count:
                button.set_colors(Theme.ACCENT, Theme.ACCENT_HOVER, "#FFFFFF")
            else:
                button.set_colors(Theme.PANEL_HOVER, Theme.BORDER_SOFT, Theme.TEXT)

    # ------------------------------------------------------------------
    # Canvas artwork
    # ------------------------------------------------------------------

    def _cup_pixel_x(self, cup_id: int) -> float:
        slot_pos = self.cup_positions[cup_id]
        return self.CUP_XS[0] + slot_pos * (self.CUP_XS[1] - self.CUP_XS[0])

    def draw_game(self) -> None:
        c = self.game_canvas
        c.delete("all")

        # Soft playfield and tabletop, using ChickenCrossing's warm mineral palette.
        c.create_rectangle(0, 0, self.CANVAS_WIDTH, self.CANVAS_HEIGHT, fill=Theme.CANVAS_BG, outline="")
        c.create_text(
            28, 26,
            text="观察 · 记忆 · 选择",
            fill=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 10, "bold"),
            anchor=tk.W,
        )
        c.create_rectangle(28, 110, 718, 505, fill=Theme.TABLE, outline=Theme.TABLE_EDGE, width=2)
        # Keep a generous tabletop surface so the cups sit fully on the table,
        # rather than hanging over its front edge.
        c.create_rectangle(28, 466, 718, 505, fill="#91AA91", outline="")
        c.create_line(48, 466, 698, 466, fill=Theme.TABLE_EDGE, width=2)

        # Position markers remain fixed even while cup identities shuffle.
        for idx, x in enumerate(self.CUP_XS, start=1):
            c.create_oval(x - 54, 444, x + 54, 462, fill="#9EB39D", outline="#7D987D")
            c.create_text(x, 484, text=f"位置 {idx}", fill=Theme.TEXT_DIM,
                          font=(Theme.FONT_CJK, 9, "bold"))

        # IMPORTANT: balls are always drawn first (lowest game-object layer).
        # They are never state-hidden while a cup is lowering.  Instead, the cup
        # artwork physically occludes the ball as it comes down; once the cup is
        # fully seated at CUP_BASE_Y the ball is completely covered.
        for cup_id in range(3):
            if cup_id not in self.ball_position:
                continue
            x = self._cup_pixel_x(cup_id)
            self._draw_ball(x, self.BALL_Y)

        for cup_id in range(3):
            x = self._cup_pixel_x(cup_id)
            y = self.cup_y_positions[cup_id]
            is_open = self._cup_should_be_open(cup_id)
            selected = cup_id == self.selected_highlight
            self._draw_cup(cup_id, x, y, is_open=is_open, selected=selected)

        if self.game_state == "waiting_selection":
            c.create_text(
                self.CANVAS_WIDTH / 2,
                76,
                text="点击任意一个杯子",
                fill=Theme.ACCENT,
                font=(Theme.FONT_CJK, 16, "bold"),
            )
        elif self.game_state == "shuffling":
            c.create_text(
                self.CANVAS_WIDTH / 2,
                76,
                text="洗杯进行中",
                fill=Theme.AMBER,
                font=(Theme.FONT_CJK, 16, "bold"),
            )

    def _cup_should_be_open(self, cup_id: int) -> bool:
        if self.game_state == "showing_balls":
            return True
        if self.game_state == "revealing" and cup_id == self.selected_cup:
            return True
        if self.game_state == "showing_all":
            return True
        return False

    def _draw_ball(self, x: float, y: float) -> None:
        c = self.game_canvas
        # Slightly smaller than R1 so an upside-down yunomi can genuinely cover
        # the whole ball when its rim is resting on the tabletop.
        r = 20
        c.create_oval(x - r, y - r, x + r, y + r,
                      fill=Theme.BALL, outline=Theme.BALL_EDGE, width=2)
        c.create_oval(x - 9, y - 11, x - 2, y - 4, fill="#FFF7D6", outline="")
        c.create_arc(x - 14, y - 13, x + 14, y + 15, start=205, extent=120,
                     style=tk.ARC, outline=Theme.BALL_EDGE, width=2)
        c.create_text(x, y + 1, text="●", fill="#73551C", font=(Theme.FONT, 9, "bold"))

    def _draw_cup(self, cup_id: int, x: float, y: float, *, is_open: bool, selected: bool) -> None:
        """Draw an upside-down Japanese yunomi-style porcelain cup.

        ``y`` is the tabletop contact line of the cup.  At CUP_BASE_Y the
        complete rim and shadow sit above the table's front edge, so the cup
        no longer appears to float or hang off the desk.
        """
        c = self.game_canvas
        w = self.CUP_WIDTH
        h = self.CUP_HEIGHT
        top_y = y - h

        glaze = Theme.CUP_SELECTED if selected else Theme.CUP
        glaze_side = "#C9E2ED" if selected else Theme.CUP_SIDE
        edge = Theme.CUP_SELECTED_EDGE if selected else Theme.CUP_RIM
        pattern = Theme.CUP_SELECTED_EDGE if selected else Theme.CUP_PATTERN

        # Contact shadow first.  The ball was drawn before this entire cup, so
        # cup + shadow always remain above it in the canvas stack.
        c.create_oval(
            x - w * 0.50, y - 7, x + w * 0.50, y + 14,
            fill="#7D887E", outline="",
        )

        # Upside-down yunomi body: narrower ceramic foot at the top and a broad
        # drinking rim at the bottom.  This silhouette fully encloses the ball
        # once y reaches CUP_BASE_Y.
        c.create_polygon(
            x - w * 0.34, top_y + 24,
            x + w * 0.34, top_y + 24,
            x + w * 0.47, y - 13,
            x - w * 0.47, y - 13,
            fill=glaze,
            outline=edge,
            width=2,
        )

        # Small raised foot ring, typical of Japanese ceramic tea cups.
        c.create_oval(
            x - w * 0.30, top_y + 8, x + w * 0.30, top_y + 32,
            fill="#E7E0D4" if not selected else "#D5E8F0",
            outline=edge,
            width=2,
        )
        c.create_oval(
            x - w * 0.20, top_y + 13, x + w * 0.20, top_y + 26,
            fill="#F6F2E9" if not selected else "#E7F4F8",
            outline=Theme.BORDER_SOFT,
            width=1,
        )

        # Indigo sometsuke-style band.
        band_top = top_y + 68
        band_bottom = top_y + 105
        c.create_rectangle(
            x - w * 0.39, band_top, x + w * 0.39, band_bottom,
            fill=Theme.CUP_PATTERN_SOFT if not selected else "#C2DFEB",
            outline="",
        )
        c.create_line(x - w * 0.40, band_top, x + w * 0.40, band_top, fill=pattern, width=2)
        c.create_line(x - w * 0.42, band_bottom, x + w * 0.42, band_bottom, fill=pattern, width=2)

        # Simplified seigaiha (青海波) waves.
        wave_y = band_top + 22
        for offset in (-34, 0, 34):
            c.create_arc(
                x + offset - 22, wave_y - 15, x + offset + 22, wave_y + 17,
                start=0, extent=180, style=tk.ARC, outline=pattern, width=2,
            )
            c.create_arc(
                x + offset - 15, wave_y - 9, x + offset + 15, wave_y + 13,
                start=0, extent=180, style=tk.ARC, outline=pattern, width=1,
            )

        # Small red kiln/seal mark.
        c.create_rectangle(
            x + w * 0.25, top_y + 118, x + w * 0.36, top_y + 132,
            fill=Theme.CUP_SEAL, outline="",
        )
        c.create_text(
            x + w * 0.305, top_y + 125, text="和", fill="#FFF8ED",
            font=(Theme.FONT_CJK, 6, "bold"),
        )

        # Bottom/open rim.  Together with the body it closes every visible gap
        # around the ball at the seated position.
        c.create_oval(
            x - w * 0.49, y - 19, x + w * 0.49, y + 7,
            fill=glaze_side, outline=edge, width=3,
        )
        c.create_arc(
            x - w * 0.43, y - 14, x + w * 0.43, y + 2,
            start=0, extent=180, style=tk.ARC, outline="#F8F4EA", width=2,
        )

        # A soft highlight keeps the porcelain dimensional without becoming
        # glossy or inconsistent with ChickenCrossing's low-glare HMI.
        c.create_line(
            x - w * 0.28, top_y + 40, x - w * 0.37, y - 33,
            fill="#FFFFFF", width=2,
        )

        if selected:
            c.create_text(
                x, top_y - 14, text="已选择", fill=Theme.ACCENT,
                font=(Theme.FONT_CJK, 10, "bold"),
            )

    def _cup_at_point(self, x: float, y: float) -> Optional[int]:
        if self.game_state != "waiting_selection":
            return None
        for cup_id in range(3):
            cx = self._cup_pixel_x(cup_id)
            cy = self.cup_y_positions[cup_id]
            if cx - 72 <= x <= cx + 72 and cy - self.CUP_HEIGHT - 12 <= y <= cy + 20:
                return cup_id
        return None

    def _on_canvas_click(self, event) -> None:
        cup_id = self._cup_at_point(event.x, event.y)
        if cup_id is not None:
            self.select_cup(cup_id)

    def _on_canvas_motion(self, event) -> None:
        if self.game_state != "waiting_selection":
            return
        self._hover_cup(self._cup_at_point(event.x, event.y))

    def _hover_cup(self, cup_id: Optional[int]) -> None:
        if self.game_state != "waiting_selection":
            return
        if self.selected_highlight == cup_id:
            return
        self.selected_highlight = cup_id
        self.game_canvas.configure(cursor="hand2" if cup_id is not None else "")
        self.draw_game()

    # ------------------------------------------------------------------
    # Betting and controls
    # ------------------------------------------------------------------

    def add_chip(self, amount: str) -> None:
        if self.game_state != "idle":
            return
        try:
            value = float(amount)
        except (TypeError, ValueError):
            return
        if value <= 0:
            return
        if self.current_bet + value <= self.balance:
            self.current_bet += value
            self.update_display()

    def reset_bet(self) -> None:
        if self.game_state != "idle":
            return
        self.current_bet = 0.0
        self.update_display()

    def set_ball_count(self, value: int) -> None:
        if self.game_state != "idle" or value not in (1, 2):
            return
        self.ball_count = value
        self.update_display()

    def _set_controls_locked(self, locked: bool) -> None:
        state = tk.DISABLED if locked else tk.NORMAL
        self.start_button.configure(state=state)
        self.reset_bet_button.configure(state=state)
        for button in self.chip_buttons:
            button.configure(state=state)
        for button in self.ball_mode_buttons:
            button.configure(state=state)

    # ------------------------------------------------------------------
    # Game lifecycle
    # ------------------------------------------------------------------

    def start_game(self) -> None:
        if self.game_state != "idle":
            return
        if self.current_bet <= 0:
            messagebox.showwarning("提示", "请先选择下注金额。")
            return
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "账户余额不足以进行本次下注。")
            return

        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        update_balance_in_json(self.username, self.balance)
        self.selected_cup = -1
        self.selected_highlight = None
        self.cup_positions = [0.0, 1.0, 2.0]
        self.cup_targets = [0.0, 1.0, 2.0]
        self.cup_y_positions = [float(self.CUP_BASE_Y)] * 3
        self.ball_position = (
            [random.randint(0, 2)] if self.ball_count == 1
            else random.sample([0, 1, 2], 2)
        )
        self.game_state = "showing_balls"
        self._set_controls_locked(True)
        self.update_display()

        # Lift all cups to expose the balls, pause, then lower them again.
        self._animate_cups_y(
            [float(self.CUP_LIFT_Y)] * 3,
            duration=0.75,
            callback=lambda: self._after(1100, self._begin_lowering),
        )

    def _begin_lowering(self) -> None:
        self.game_state = "lowering"
        self.update_display()
        self._animate_cups_y(
            [float(self.CUP_BASE_Y)] * 3,
            duration=0.75,
            callback=self.start_smooth_shuffling,
        )

    def start_smooth_shuffling(self) -> None:
        self.game_state = "shuffling"
        self.shuffle_start_time = time.time()
        self.shuffle_duration = 10.0
        self.last_swap_time = time.time()
        self.last_frame_time = time.time()
        self.cup_targets = list(self.cup_positions)
        self.update_display()
        self._shuffle_frame()

    def _shuffle_frame(self) -> None:
        if self.game_state != "shuffling":
            return
        now = time.time()
        elapsed = now - self.shuffle_start_time
        frame_time = min(0.05, max(0.001, now - self.last_frame_time))
        self.last_frame_time = now

        if elapsed < 1.0:
            speed = 2.8
        elif elapsed < 2.75:
            p = (elapsed - 1.0) / 1.75
            speed = 2.8 + (7.0 - 2.8) * p
        elif elapsed < 7.75:
            speed = 7.0
        elif elapsed < 9.5:
            p = (elapsed - 7.75) / 1.75
            speed = 7.0 - (7.0 - 2.8) * p
        else:
            speed = 2.8

        if elapsed < self.shuffle_duration:
            swap_interval = max(0.10, 0.42 / max(1.0, speed / 2.8))
            if now - self.last_swap_time >= swap_interval:
                i, j = random.sample([0, 1, 2], 2)
                self.cup_targets[i], self.cup_targets[j] = self.cup_targets[j], self.cup_targets[i]
                self.last_swap_time = now

        all_arrived = True
        for cup_id in range(3):
            current = self.cup_positions[cup_id]
            target = self.cup_targets[cup_id]
            diff = target - current
            if abs(diff) > 0.006:
                step = math.copysign(min(abs(diff), speed * frame_time), diff)
                self.cup_positions[cup_id] += step
                all_arrived = False
            else:
                self.cup_positions[cup_id] = target
            self.cup_y_positions[cup_id] = self.CUP_BASE_Y + 6 * math.sin(now * 6 + cup_id * 2.1)

        if elapsed >= self.shuffle_duration and all_arrived:
            self.cup_y_positions = [float(self.CUP_BASE_Y)] * 3
            self.game_state = "waiting_selection"
            self.update_display()
            return

        self.draw_game()
        self._after(16, self._shuffle_frame)

    def select_cup(self, cup_idx: int) -> None:
        if self.game_state != "waiting_selection" or cup_idx not in (0, 1, 2):
            return
        self.selected_cup = cup_idx

        # R3: once the chosen cup starts opening, remove the hover/selection
        # banner immediately.  The cup itself can still be identified by the
        # reveal motion, but the "已选择" text must not remain floating above it.
        self.selected_highlight = None
        self.game_state = "revealing"
        self.update_display()

        targets = list(self.cup_y_positions)
        targets[cup_idx] = float(self.CUP_LIFT_Y)
        self._animate_cups_y(
            targets,
            duration=0.75,
            callback=lambda: self._after(1100, self._show_all_cups),
        )

    def _show_all_cups(self) -> None:
        self.game_state = "showing_all"
        self.calculate_win()
        self.update_display()
        self._animate_cups_y(
            [float(self.CUP_LIFT_Y)] * 3,
            duration=0.7,
            callback=lambda: self._after(2200, self._reset_after_round),
        )

    def calculate_win(self) -> None:
        if self.selected_cup in self.ball_position:
            win_amount = self.bet_amount * ODDS[self.ball_count]
            self.balance += win_amount
            self.last_win = win_amount
        else:
            self.last_win = 0.0
        update_balance_in_json(self.username, self.balance)

    def _reset_after_round(self) -> None:
        self.selected_cup = -1
        self.selected_highlight = None

        # R3: keep both ball_position and the current shuffled cup_positions
        # alive while the cups come back down.  draw_game() always paints balls
        # first, then cups above them, so the balls remain visible during the
        # descent and disappear only when the cup body physically covers them.
        # Do NOT clear/reset these here, otherwise the final lowering animation
        # either loses the balls completely or makes them jump to another slot.
        self.cup_targets = list(self.cup_positions)
        self.cup_y_positions = [float(self.CUP_LIFT_Y)] * 3
        self.game_state = "lowering"
        self.update_display()
        self._animate_cups_y(
            [float(self.CUP_BASE_Y)] * 3,
            duration=0.65,
            callback=self.finish_game,
        )

    def finish_game(self) -> None:
        # The cups are now fully seated on the table, so it is finally safe to
        # remove the hidden balls from the next idle redraw.
        self.ball_position = []
        self.game_state = "idle"
        self.cup_y_positions = [float(self.CUP_BASE_Y)] * 3
        self._set_controls_locked(False)
        self.update_display()

    # ------------------------------------------------------------------
    # Animation helpers
    # ------------------------------------------------------------------

    def _animate_cups_y(
        self,
        target_values: list[float],
        *,
        duration: float,
        callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self._motion_start = time.time()
        self._motion_duration = max(0.01, duration)
        self._motion_from = list(self.cup_y_positions)
        self._motion_to = list(target_values)
        self._motion_callback = callback
        self._motion_frame()

    def _motion_frame(self) -> None:
        if self._motion_start is None:
            return
        p = min(1.0, (time.time() - self._motion_start) / self._motion_duration)
        # ease in/out
        eased = p * p * (3.0 - 2.0 * p)
        self.cup_y_positions = [
            start + (end - start) * eased
            for start, end in zip(self._motion_from, self._motion_to)
        ]
        self.draw_game()
        if p < 1.0:
            self._after(16, self._motion_frame)
            return
        callback = self._motion_callback
        self._motion_start = None
        self._motion_callback = None
        if callback is not None:
            callback()

    def _after(self, ms: int, callback: Callable[[], None]) -> Optional[str]:
        holder: dict[str, str] = {}

        def wrapped() -> None:
            job = holder.get("id")
            if job is not None:
                self._after_jobs.discard(job)
            callback()

        try:
            job = self.root.after(ms, wrapped)
        except tk.TclError:
            return None
        holder["id"] = job
        self._after_jobs.add(job)
        return job

    def _cancel_jobs(self) -> None:
        for job in list(self._after_jobs):
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        self._after_jobs.clear()

    def on_closing(self) -> None:
        self._cancel_jobs()
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
        page = EmbeddedGamePage(
            parent,
            title="三杯球游戏",
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        game = ThimblesGame(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = ThimblesGame(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    final_balance = main(10000.0, "test_user")
    print(f"Final balance: {final_balance}")