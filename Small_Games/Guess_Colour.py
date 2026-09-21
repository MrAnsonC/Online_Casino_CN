"""Guess Color — ChickenCrossing-style warm fixed-size HMI.

The game rules remain the same as the original Guess_color.py:
- 24 playable cells: 8 red, 8 blue, 8 green, with a non-playable centre cell.
- Reveal 12 cells.
- A 3/4/5 colour split loses.
- A 4/4/4 split pays 0.5:1 profit (1.5x total return).
- Any other split pays 1:1 profit (2.0x total return).

The UI is rebuilt to match ChickenCrossing_tk.py's fixed 1150x750 layout,
warm mineral palette, card hierarchy, metric tiles, chip controls and embedded
single-window integration.
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
import os
import random
import sys
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional

try:
    from .small_games import EmbeddedGamePage
except ImportError:  # Allow direct execution inside the original project.
    from small_games import EmbeddedGamePage


# ---------------------------------------------------------------------------
# Theme and immutable game configuration
# ---------------------------------------------------------------------------


class Theme:
    """Visual tokens intentionally aligned with ChickenCrossing_tk.py."""

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
    HALF = "#64A100"
    CYAN = "#276E78"
    GREEN = "#4E7355"
    GREEN_HOVER = "#3D5C43"
    RED = "#A84D4D"
    RED_HOVER = "#873D3D"
    AMBER = "#A36B22"

    # Guess-color semantic tones, softened to sit inside the warm HMI.
    COLOR_RED = "#B95C58"
    COLOR_RED_DARK = "#87413E"
    COLOR_BLUE = "#4E7892"
    COLOR_BLUE_DARK = "#365A70"
    COLOR_GREEN = "#5F865F"
    COLOR_GREEN_DARK = "#416442"

    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )
    FONT_EMOJI = "Segoe UI Emoji"


# label, amount, chip colour, label colour
CHIP_CONFIGS = (
    ("$5", "5", "#D74A45", "white"),
    ("$25", "25", "#65A65A", "black"),
    ("$100", "100", "#202225", "white"),
    ("$500", "500", "#D78AC5", "black"),
    ("$1K", "1000", "#F7F4EE", "black"),
)

COLOR_KEYS = ("🔴", "🔵", "🟢")
COLOR_LABELS = {"🔴": "红", "🔵": "蓝", "🟢": "绿"}
COLOR_FILLS = {
    "🔴": Theme.COLOR_RED,
    "🔵": Theme.COLOR_BLUE,
    "🟢": Theme.COLOR_GREEN,
}
COLOR_DARK = {
    "🔴": Theme.COLOR_RED_DARK,
    "🔵": Theme.COLOR_BLUE_DARK,
    "🟢": Theme.COLOR_GREEN_DARK,
}


# ---------------------------------------------------------------------------
# Persistence helpers — same A_Tools/Account/saving_data.json contract as the original
# ---------------------------------------------------------------------------


def get_data_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../A_Tools/Account/saving_data.json")


def save_user_data(users) -> None:
    with open(get_data_file_path(), "w", encoding="utf-8") as file:
        json.dump(users, file, ensure_ascii=False, indent=4)


def load_user_data():
    with open(get_data_file_path(), "r", encoding="utf-8") as file:
        return json.load(file)


def update_balance_in_json(username: str, new_balance: float) -> None:
    users = load_user_data()
    for user in users:
        if user.get("user_name") == username:
            user["cash"] = f"{new_balance:.2f}"
            break
    save_user_data(users)


# ---------------------------------------------------------------------------
# Reusable UI controls copied in format from ChickenCrossing_tk.py
# ---------------------------------------------------------------------------


class ModernButton(tk.Button):
    """Flat button with ChickenCrossing-style hover/disabled behaviour."""

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
    """Compact physical poker chip, matching ChickenCrossing's control language."""

    def __init__(
        self,
        master,
        *,
        label: str,
        amount: str,
        chip_color: str,
        text_color: str,
        command: Callable[[str], None],
        width: int = 54,
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
            cx,
            cy,
            text=self.label,
            fill=self.text_color,
            font=(Theme.FONT, 8 if len(self.label) <= 4 else 7, "bold"),
        )

        if disabled:
            self.create_oval(4, 3 + offset_y, self.control_width - 5,
                             self.control_height - 5 + offset_y,
                             fill="#C9C2B8", outline=Theme.BORDER_SOFT,
                             width=1, stipple="gray50")

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
            super().configure(cursor="" if state == tk.DISABLED else "hand2")
            self.draw()
        if cnf is not None or kwargs:
            return super().configure(cnf, **kwargs)
        return None

    config = configure


class MetricTile(tk.Frame):
    """Fixed-size label/value block used in ChickenCrossing's summary strip."""

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
        tk.Frame(self, width=4, height=height, bg=accent).place(x=0, y=0, width=4, height=height)
        tk.Label(
            self,
            text=label,
            bg=Theme.PANEL_ALT,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9),
            anchor=tk.W,
        ).place(x=14, y=9, width=145, height=18)
        tk.Label(
            self,
            textvariable=variable,
            bg=Theme.PANEL_ALT,
            fg=accent,
            font=(Theme.FONT, 16, "bold"),
            anchor=tk.W,
        ).place(x=14, y=29, width=145, height=28)


class ColorCellButton(tk.Canvas):
    """Warm HMI board tile with explicit unrevealed/revealed/centre states."""

    def __init__(
        self,
        master,
        *,
        row: int,
        col: int,
        command: Optional[Callable[[], None]],
        centre: bool = False,
        width: int = 104,
        height: int = 84,
    ) -> None:
        super().__init__(
            master,
            width=width,
            height=height,
            bg=Theme.CANVAS_BG,
            bd=0,
            highlightthickness=0,
            cursor="" if centre else "hand2",
        )
        self.row = row
        self.col = col
        self.command = command
        self.centre = centre
        self.control_width = width
        self.control_height = height
        self.is_revealed = centre
        self.value = ""
        self.remaining_count = 12
        self._hovered = False
        self._pressed = False

        if not centre:
            self.bind("<Enter>", self._on_enter)
            self.bind("<Leave>", self._on_leave)
            self.bind("<ButtonPress-1>", self._on_press)
            self.bind("<ButtonRelease-1>", self._on_release)
        self.draw()

    def draw(self) -> None:
        self.delete("all")
        if self.centre:
            self.create_rectangle(
                4, 4, self.control_width - 4, self.control_height - 4,
                fill=Theme.ACCENT_SOFT,
                outline=Theme.ACCENT,
                width=2,
            )
            self.create_text(
                self.control_width / 2,
                27,
                text=str(self.remaining_count),
                fill=Theme.ACCENT,
                font=(Theme.FONT, 21, "bold"),
            )
            self.create_text(
                self.control_width / 2,
                55,
                text="剩余需开启",
                fill=Theme.TEXT_MUTED,
                font=(Theme.FONT_CJK, 9, "bold"),
            )
            return

        if self.is_revealed:
            fill = COLOR_FILLS[self.value]
            dark = COLOR_DARK[self.value]
            self.create_rectangle(
                4, 4, self.control_width - 4, self.control_height - 4,
                fill=fill,
                outline=dark,
                width=2,
            )
            self.create_oval(
                33, 14, self.control_width - 33, 48,
                fill="#F7F3EC",
                outline=dark,
                width=2,
            )
            self.create_text(
                self.control_width / 2,
                31,
                text=COLOR_LABELS[self.value],
                fill=dark,
                font=(Theme.FONT_CJK, 14, "bold"),
            )
            self.create_text(
                self.control_width / 2,
                63,
                text=f"{self.row * 5 + self.col + 1:02d}",
                fill="#F7F3EC",
                font=(Theme.FONT, 9, "bold"),
            )
            return

        y = 6 if self._pressed else 4
        fill = Theme.PANEL_HOVER if self._hovered else Theme.PANEL_ALT
        outline = Theme.ACCENT if self._hovered else Theme.BORDER
        self.create_rectangle(
            5, y + 3, self.control_width - 3, self.control_height - 2,
            fill="#A49C91",
            outline="",
        )
        self.create_rectangle(
            3, y, self.control_width - 5, self.control_height - 6,
            fill=fill,
            outline=outline,
            width=2,
        )
        self.create_text(
            self.control_width / 2,
            31 + (2 if self._pressed else 0),
            text="?",
            fill=Theme.TEXT,
            font=(Theme.FONT, 22, "bold"),
        )
        self.create_text(
            self.control_width / 2,
            59 + (2 if self._pressed else 0),
            text=f"{self.row * 5 + self.col + 1:02d}",
            fill=Theme.TEXT_MUTED,
            font=(Theme.FONT, 8, "bold"),
        )

    def _on_enter(self, _event) -> None:
        if not self.is_revealed:
            self._hovered = True
            self.draw()

    def _on_leave(self, _event) -> None:
        self._hovered = False
        self._pressed = False
        self.draw()

    def _on_press(self, _event) -> None:
        if not self.is_revealed:
            self._pressed = True
            self.draw()

    def _on_release(self, event) -> None:
        if self.is_revealed:
            return
        was_pressed = self._pressed
        self._pressed = False
        inside = 0 <= event.x < self.control_width and 0 <= event.y < self.control_height
        if was_pressed and inside and callable(self.command):
            self.command()
        self.draw()

    def set_remaining_count(self, count: int) -> None:
        if not self.centre:
            return
        self.remaining_count = max(0, int(count))
        self.draw()

    def reveal(self, value: str) -> None:
        self.value = value
        self.is_revealed = True
        self._hovered = False
        self._pressed = False
        self.configure(cursor="")
        self.draw()


# ---------------------------------------------------------------------------
# Main game
# ---------------------------------------------------------------------------


class ColorGame:
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
    GAME_INNER_WIDTH = 746
    ACTION_BUTTON_WIDTH = 322

    CELL_WIDTH = 104
    CELL_HEIGHT = 84
    CELL_GAP = 12
    BOARD_WIDTH = CELL_WIDTH * 5 + CELL_GAP * 4
    BOARD_HEIGHT = CELL_HEIGHT * 5 + CELL_GAP * 4

    def __init__(self, root, initial_balance, username):
        self.root = root
        self._configure_root()

        # Original gameplay state.
        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0.0
        self.board = []
        self.revealed_cells = set()
        self.game_active = False
        self.last_win = 0.0
        self.current_bet = 0.0
        self.current_odds = 1.0
        self.cell_buttons = []
        self.color_counts = {"🔴": 0, "🔵": 0, "🟢": 0}
        self.chip_buttons = []

        self.create_widgets()
        self.update_display()

    # ------------------------------------------------------------------
    # Window / common card helpers
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("抽颜色游戏")
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

    @staticmethod
    def _mini_stat(master, x: int, label: str, variable: tk.StringVar, accent: str) -> None:
        tk.Label(
            master,
            text=label,
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8),
            anchor=tk.W,
        ).place(x=x, y=0, width=98, height=16)
        tk.Label(
            master,
            textvariable=variable,
            bg=Theme.PANEL,
            fg=accent,
            font=(Theme.FONT, 13, "bold"),
            anchor=tk.W,
        ).place(x=x, y=17, width=98, height=24)

    # ------------------------------------------------------------------
    # UI construction — same fixed shell proportions as ChickenCrossing
    # ------------------------------------------------------------------

    def create_widgets(self) -> None:
        self.balance_var = tk.StringVar(value=f"${self.balance:.2f}")
        self.bet_var = tk.StringVar(value="$0.00")
        self.last_win_var = tk.StringVar(value="$0.00")
        self.progress_var = tk.StringVar(value="0 / 12")
        self.return_var = tk.StringVar(value="其他组合")
        self.halfreturn_var = tk.StringVar(value="4·4·4")
        self.status_var = tk.StringVar(value="选择下注金额，然后开始抽色。")
        self.info_var = tk.StringVar(value="抽出 12 格：避开 3-4-5，4-4-4 为半额盈利。")
        self.red_count_var = tk.StringVar(value="0")
        self.blue_count_var = tk.StringVar(value="0")
        self.green_count_var = tk.StringVar(value="0")
        self.danger_var = tk.StringVar(value="3·4·5")

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

        tk.Label(
            header,
            text="●",
            bg=Theme.APP_BG,
            fg=Theme.COLOR_RED,
            font=(Theme.FONT, 28, "bold"),
            anchor=tk.CENTER,
        ).place(x=0, y=7, width=42, height=44)
        tk.Label(
            header,
            text="GUESS COLOR",
            bg=Theme.APP_BG,
            fg=Theme.TEXT,
            font=(Theme.FONT, 20, "bold"),
            anchor=tk.W,
        ).place(x=52, y=4, width=430, height=31)
        tk.Label(
            header,
            text="抽颜色游戏",
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
        balance_box.pack_propagate(False)

        self.balance_display_var = tk.StringVar(value=f"账户余额: {self.balance_var.get()}")

        def update_balance_display(*_args) -> None:
            self.balance_display_var.set(f"账户余额: {self.balance_var.get()}")

        self.balance_var.trace_add("write", update_balance_display)
        tk.Label(
            balance_box,
            textvariable=self.balance_display_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 13, "bold"),
            anchor=tk.E,
        ).place(x=14, y=7, width=242, height=40)

    def _build_game_panel(self, master) -> None:
        panel = self._card(master, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT, padding=0)
        panel.place(x=0, y=0, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT)
        content = panel.content  # type: ignore[attr-defined]

        top = tk.Frame(content, width=self.GAME_INNER_WIDTH, height=74, bg=Theme.PANEL)
        top.place(x=0, y=0, width=self.GAME_INNER_WIDTH, height=74)
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
            text="颜色矩阵",
            bg=Theme.ACCENT_SOFT,
            fg=Theme.ACCENT,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.CENTER,
        ).place(x=618, y=19, width=108, height=32)

        self.board_frame = tk.Frame(
            content,
            width=self.GAME_INNER_WIDTH,
            height=554,
            bg=Theme.CANVAS_BG,
        )
        self.board_frame.place(x=0, y=74, width=self.GAME_INNER_WIDTH, height=554)
        self.board_frame.pack_propagate(False)
        self.board_frame.grid_propagate(False)

        # Quiet background guide, using the same warm canvas idea as ChickenCrossing.
        guide = tk.Canvas(
            self.board_frame,
            width=self.GAME_INNER_WIDTH,
            height=554,
            bg=Theme.CANVAS_BG,
            bd=0,
            highlightthickness=0,
        )
        guide.place(x=0, y=0, width=self.GAME_INNER_WIDTH, height=554)
        guide.create_rectangle(52, 30, 694, 524, fill="#C8D7C7", outline=Theme.BORDER_SOFT, width=1)
        guide.create_text(
            74,
            52,
            text="24 个隐藏色块 · 红 / 蓝 / 绿各 8 个",
            anchor=tk.W,
            fill=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9, "bold"),
        )
        guide.create_text(
            672,
            52,
            text="目标：抽 12 格",
            anchor=tk.E,
            fill=Theme.ACCENT,
            font=(Theme.FONT_CJK, 9, "bold"),
        )

        self.board_surface = tk.Frame(
            self.board_frame,
            width=self.BOARD_WIDTH,
            height=self.BOARD_HEIGHT,
            bg="#C8D7C7",
        )
        board_x = (self.GAME_INNER_WIDTH - self.BOARD_WIDTH) // 2
        board_y = 76
        self.board_surface.place(
            x=board_x,
            y=board_y,
            width=self.BOARD_WIDTH,
            height=self.BOARD_HEIGHT,
        )
        self.board_surface.pack_propagate(False)
        self.board_surface.grid_propagate(False)
        self.create_game_board()

    def _build_control_panel(self, master) -> None:
        sidebar_x = self.GAME_PANEL_WIDTH + self.PANEL_GAP
        sidebar = tk.Frame(
            master,
            width=self.SIDEBAR_WIDTH,
            height=self.BODY_HEIGHT,
            bg=Theme.APP_BG,
        )
        sidebar.place(x=sidebar_x, y=0, width=self.SIDEBAR_WIDTH, height=self.BODY_HEIGHT)
        sidebar.pack_propagate(False)
        sidebar.grid_propagate(False)

        MetricTile(sidebar, "当前下注", self.bet_var, Theme.CYAN, width=169, height=68).place(
            x=0, y=0, width=169, height=68
        )
        MetricTile(sidebar, "上局获胜", self.last_win_var, Theme.GREEN, width=169, height=68).place(
            x=179, y=0, width=169, height=68
        )

        # Bet card: 78..197
        bet_card = self._card(sidebar, width=348, height=120, padding=12)
        bet_card.place(x=0, y=78, width=348, height=120)
        bet_content = bet_card.content  # type: ignore[attr-defined]
        self._section_title(bet_content, "下注金额", "点击筹码可累加下注", width=322)
        chip_width = 54
        chip_gap = 12
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

        # Colour count card: 208..307
        count_card = self._card(sidebar, width=348, height=100, padding=12)
        count_card.place(x=0, y=208, width=348, height=100)
        count_content = count_card.content  # type: ignore[attr-defined]
        self._section_title(
            count_content,
            "已揭示颜色统计",
            "红 / 蓝 / 绿 · 当前已开启数量",
            width=322,
        )
        self._build_color_counter(count_content, 0, "红色已开", self.red_count_var, Theme.COLOR_RED)
        self._build_color_counter(count_content, 109, "蓝色已开", self.blue_count_var, Theme.COLOR_BLUE)
        self._build_color_counter(count_content, 218, "绿色已开", self.green_count_var, Theme.COLOR_GREEN)

        # Action card: 318..497
        action_card = self._card(sidebar, width=348, height=180, padding=12)
        action_card.place(x=0, y=318, width=348, height=180)
        action_content = action_card.content  # type: ignore[attr-defined]

        stats = tk.Frame(action_content, width=322, height=44, bg=Theme.PANEL)
        stats.place(x=0, y=0, width=322, height=44)
        self._mini_stat(stats, 0, "已抽进度", self.progress_var, Theme.TEXT)
        self._mini_stat(stats, 88, "危险组合", self.danger_var, Theme.RED)
        self._mini_stat(stats, 150, "半额赔率", self.halfreturn_var, Theme.HALF)
        self._mini_stat(stats, 218, "完整赔率", self.return_var, Theme.CYAN)

        self.status_label = tk.Label(
            action_content,
            textvariable=self.status_var,
            bg=Theme.PANEL_ALT,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.W,
            padx=10,
        )
        self.status_label.place(x=0, y=50, width=322, height=32)

        self.reset_bet_button = ModernButton(
            action_content,
            text="清空全部筹码",
            command=self.reset_bet,
            background=Theme.RED,
            hover_background=Theme.RED_HOVER,
            foreground="white",
            font_size=11,
            bold=True,
        )
        self.reset_bet_button.place(x=0, y=92, width=155, height=38)

        self.game_button = ModernButton(
            action_content,
            text="开始游戏",
            command=self.start_game,
            background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER,
            foreground="white",
            font_size=11,
            bold=True,
        )
        self.game_button.place(x=167, y=92, width=155, height=38)

        # Rules card: 508..629
        rules_card = self._card(sidebar, width=348, height=122, padding=12)
        rules_card.place(x=0, y=508, width=348, height=122)
        rules_content = rules_card.content  # type: ignore[attr-defined]
        self._section_title(rules_content, "规则", width=322)
        rules_text = (
            "24 格：红 / 蓝 / 绿各 8 个，中心显示剩余开启数。\n"
            "3 / 4 / 5：输；4 / 4 / 4：盈利 0.5:1（返 1.5×）；\n"
            "其他组合：盈利 1:1（返 2×）。"
        )
        tk.Label(
            rules_content,
            text=rules_text,
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8),
            justify=tk.LEFT,
            anchor=tk.NW,
        ).place(x=0, y=30, width=322, height=63)

    def _build_color_counter(
        self,
        master,
        x: int,
        label: str,
        variable: tk.StringVar,
        accent: str,
    ) -> None:
        box = tk.Frame(master, width=104, height=35, bg=Theme.PANEL_ALT)
        box.place(x=x, y=39, width=104, height=35)
        box.pack_propagate(False)
        tk.Frame(box, width=5, height=35, bg=accent).place(x=0, y=0, width=5, height=35)
        tk.Label(
            box,
            text=label,
            bg=Theme.PANEL_ALT,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 7, "bold"),
            anchor=tk.W,
        ).place(x=13, y=7, width=50, height=18)
        tk.Label(
            box,
            textvariable=variable,
            bg=Theme.PANEL_ALT,
            fg=accent,
            font=(Theme.FONT, 15, "bold"),
            anchor=tk.E,
        ).place(x=62, y=3, width=20, height=28)
        tk.Label(
            box,
            text="格",
            bg=Theme.PANEL_ALT,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8, "bold"),
            anchor=tk.W,
        ).place(x=84, y=8, width=17, height=18)

    # ------------------------------------------------------------------
    # Board and original gameplay
    # ------------------------------------------------------------------

    def create_game_board(self) -> None:
        for widget in self.board_surface.winfo_children():
            widget.destroy()

        self.cell_buttons = []
        self.center_button = None
        for row in range(5):
            row_buttons = []
            for col in range(5):
                centre = row == 2 and col == 2
                button = ColorCellButton(
                    self.board_surface,
                    row=row,
                    col=col,
                    centre=centre,
                    command=None if centre else (lambda r=row, c=col: self.select_cell(r, c)),
                    width=self.CELL_WIDTH,
                    height=self.CELL_HEIGHT,
                )
                x = col * (self.CELL_WIDTH + self.CELL_GAP)
                y = row * (self.CELL_HEIGHT + self.CELL_GAP)
                button.place(x=x, y=y, width=self.CELL_WIDTH, height=self.CELL_HEIGHT)
                if centre:
                    self.center_button = button
                row_buttons.append(button)
            self.cell_buttons.append(row_buttons)

    def add_chip(self, amount: str) -> None:
        if self.game_active:
            return
        try:
            amount_val = float(amount)
        except (TypeError, ValueError):
            return
        new_bet = self.current_bet + amount_val
        if new_bet <= self.balance:
            self.current_bet = new_bet
            self.bet_var.set(f"${self.current_bet:.2f}")
            self.status_var.set(f"下注已设为 ${self.current_bet:.2f}，可继续加注或开始。")
        else:
            self.status_var.set("筹码无法加入：下注金额不能超过当前余额。")

    def reset_bet(self) -> None:
        if self.game_active:
            return
        self.current_bet = 0.0
        self.bet_var.set("$0.00")
        self.status_var.set("下注已清空，请重新选择筹码。")

    def update_display(self) -> None:
        self.balance_var.set(f"${self.balance:.2f}")
        self.bet_var.set(f"${self.current_bet:.2f}")
        self.last_win_var.set(f"${self.last_win:.2f}")
        opened = len(self.revealed_cells)
        self.progress_var.set(f"{opened} / 12")
        centre = getattr(self, "center_button", None)
        if centre is not None:
            centre.set_remaining_count(12 - opened)
        self.update_color_chips()

    def update_color_chips(self) -> None:
        self.red_count_var.set(str(self.color_counts["🔴"]))
        self.blue_count_var.set(str(self.color_counts["🔵"]))
        self.green_count_var.set(str(self.color_counts["🟢"]))

    def generate_board(self) -> None:
        colors = ["🔴"] * 8 + ["🔵"] * 8 + ["🟢"] * 8
        random.shuffle(colors)
        self.board = [["" for _ in range(5)] for _ in range(5)]
        color_index = 0
        for row in range(5):
            for col in range(5):
                if row == 2 and col == 2:
                    continue
                self.board[row][col] = colors[color_index]
                color_index += 1

        self.revealed_cells = set()
        self.game_active = True
        self.color_counts = {"🔴": 0, "🔵": 0, "🟢": 0}
        self.create_game_board()
        self.update_display()

    def start_game(self) -> None:
        if self.current_bet <= 0:
            messagebox.showinfo("提示", "请先设置下注金额！")
            return
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注")
            return

        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        self.last_win = 0.0
        self.generate_board()
        update_balance_in_json(self.username, self.balance)

        self.game_button.config(text="游戏进行中", state=tk.DISABLED)
        self.reset_bet_button.config(
            text="随机抽取",
            command=self.random_reveal,
            state=tk.NORMAL,
        )
        self.reset_bet_button.set_colors(Theme.ACCENT, Theme.ACCENT_HOVER, "white")
        for button in self.chip_buttons:
            button.configure(state=tk.DISABLED)

        self.info_var.set("请选择隐藏色块；抽满 12 格后自动结算。")
        self.status_var.set("游戏进行中：点击棋盘色块，或使用“随机抽取”。")
        self.update_display()

    def random_reveal(self) -> None:
        if not self.game_active:
            return
        unrevealed = []
        for row in range(5):
            for col in range(5):
                if (row != 2 or col != 2) and not self.cell_buttons[row][col].is_revealed:
                    unrevealed.append((row, col))
        if unrevealed:
            row, col = random.choice(unrevealed)
            self.select_cell(row, col)

    def select_cell(self, row: int, col: int) -> None:
        if not self.game_active:
            return
        button = self.cell_buttons[row][col]
        if button.is_revealed:
            return

        self.revealed_cells.add((row, col))
        cell_value = self.board[row][col]
        self.color_counts[cell_value] += 1
        button.reveal(cell_value)
        self.update_display()

        red = self.color_counts["🔴"]
        blue = self.color_counts["🔵"]
        green = self.color_counts["🟢"]
        self.status_var.set(
            f"已抽 {len(self.revealed_cells)}/12 · 红 {red} · 蓝 {blue} · 绿 {green}"
        )

        if len(self.revealed_cells) == 12:
            self.check_game_result()

    @staticmethod
    def calculate_settlement(counts, bet_amount: float):
        """Return (profit, total_return, result_name, odds_text, is_loss).

        Payout rules requested by the user:
        - 3/4/5: lose the entire stake.
        - 4/4/4: 0.5:1 profit, so a $10 stake returns $15 total.
        - every other 12-cell split: 1:1 profit, so a $10 stake returns $20 total.
        """
        ordered = sorted(int(value) for value in counts)
        bet = float(bet_amount)
        if ordered == [3, 4, 5]:
            return 0.0, 0.0, "3-4-5 危险组合", "全输", True
        if ordered == [4, 4, 4]:
            profit = bet * 0.5
            return profit, bet + profit, "4-4-4 平衡组合", "盈利 0.5:1", False
        profit = bet
        return profit, bet + profit, "普通安全组合", "盈利 1:1", False

    def check_game_result(self) -> None:
        counts = sorted(self.color_counts.values())
        self.game_active = False

        profit, total_return, result_name, odds_text, is_loss = self.calculate_settlement(
            counts, self.bet_amount
        )

        if is_loss:
            self.last_win = 0.0
            self.info_var.set("结果：3-4-5 ，本局全输。")
            self.status_var.set("本局结束 · 3 / 4 / 5：返还 $0.00。")
            update_balance_in_json(self.username, self.balance)
            self.end_game()
            return

        self.balance += total_return
        self.last_win = total_return
        update_balance_in_json(self.username, self.balance)
        self.info_var.set(
            f"结果：{result_name}。"
        )
        self.status_var.set( 
            f"本局获胜 · {odds_text}"
        )
        self.end_game()

    def reveal_all_cells(self) -> None:
        """Compatibility helper retained from the original implementation."""
        if not self.board:
            return
        for row in range(5):
            for col in range(5):
                if row == 2 and col == 2:
                    continue
                if not self.cell_buttons[row][col].is_revealed:
                    self.cell_buttons[row][col].reveal(self.board[row][col])

    def end_game(self) -> None:
        self.game_button.config(text="开始游戏", state=tk.NORMAL, command=self.start_game)
        self.reset_bet_button.config(
            text="清空全部筹码",
            command=self.reset_bet,
            state=tk.NORMAL,
        )
        self.reset_bet_button.set_colors(Theme.RED, Theme.RED_HOVER, "white")
        for button in self.chip_buttons:
            button.configure(state=tk.NORMAL)
        self.update_display()

    def on_closing(self) -> None:
        update_balance_in_json(self.username, self.balance)
        finish = getattr(self.root, "finish", None)
        if callable(finish):
            finish(self.balance)
        else:
            self.root.destroy()


# ---------------------------------------------------------------------------
# Public entry point — same embedded API contract as ChickenCrossing_tk.py
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
            title="抽颜色游戏",
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        page.set_requested_size(1150, 750)
        game = ColorGame(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = ColorGame(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    final_balance = main(10000.0, "test_user")
    print(f"Final balance: {final_balance}")