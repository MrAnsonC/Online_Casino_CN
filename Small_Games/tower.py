"""Tower HMI — ChickenCrossing visual-system edition.

The original 8-floor Tower rules, skull/gem distributions and payout tables are
preserved.  The view layer is rebuilt to match ChickenCrossing_tk.py's fixed
warm HMI and supports the project's single-Tk EmbeddedGamePage mode.
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
from tkinter import messagebox, ttk
from typing import Callable, Optional

try:
    from .small_games import EmbeddedGamePage
except ImportError:
    from small_games import EmbeddedGamePage

VERSION = "Tower-ChickenStyle-R2"


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

    COMPLETED = "#A9C4A5"
    COMPLETED_BORDER = "#4D7D52"
    ACTIVE = "#B7CCD5"
    ACTIVE_BORDER = "#345E73"
    UPCOMING = "#D6D0C7"
    UPCOMING_BORDER = "#AAA196"
    SKULL = "#C56C63"
    SKULL_BORDER = "#8E4742"
    TOWER_WELL = "#AFC4B1"
    GEM = "#00B6F8"
    GEM_BORDER = "#5B8EA6"
    GEM_TEXT = "#1F5F78"

    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )
    FONT_EMOJI = "Segoe UI Emoji"


ODDS = {
    "1": [1.28, 1.64, 2.10, 2.68, 3.44, 4.40, 5.63, 7.21],
    "2": [1.44, 2.07, 2.99, 4.30, 6.19, 8.92, 12.84, 18.49],
    "3": [1.92, 3.69, 7.08, 13.59, 26.09, 50.10, 96.19, 184.68],
    "4": [2.88, 8.29, 23.89, 68.80, 198.14, 570.63, 1643.42, 4733.04],
    "5": [3.84, 14.75, 56.62, 217.43, 834.94, 3206.18, 12311.72, 47276.99],
}

SKULL_DISTRIBUTION = {
    "1": (1, 3),
    "2": (1, 2),
    "3": (1, 1),
    "4": (2, 1),
    "5": (3, 1),
}

DIFFICULTIES = (
    ("入门", "1", "1 骷髅 · 3 宝石"),
    ("简单", "2", "1 骷髅 · 2 宝石"),
    ("中等", "3", "1 骷髅 · 1 宝石"),
    ("困难", "4", "2 骷髅 · 1 宝石"),
    ("地狱", "5", "3 骷髅 · 1 宝石"),
)

CHIP_CONFIGS = (
    ("$5", "5", "#D75A54", "white"),
    ("$25", "25", "#67B56A", "black"),
    ("$100", "100", "#292929", "white"),
    ("$500", "500", "#D47AB7", "black"),
    ("$1K", "1000", "#F4F1EA", "black"),
)


def get_data_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../A_Tools/Account/saving_data.json")


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
    """Chicken-style physical betting chip."""

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
            font=(Theme.FONT, 12, "bold"),
        )

        if disabled:
            self.create_oval(
                7,
                3 + offset_y,
                self.control_width - 8,
                self.control_height - 5 + offset_y,
                fill="#C9C2B8",
                outline=Theme.BORDER_SOFT,
                stipple="gray50",
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
            self.focus_set()
            self._pressed = True
            self.draw()

    def _on_release(self, event) -> None:
        if self._state == tk.DISABLED:
            return
        pressed = self._pressed
        self._pressed = False
        inside = 0 <= event.x < self.control_width and 0 <= event.y < self.control_height
        if pressed and inside:
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
                self._hovered = self._pressed = self._flash = False
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



class TowerCell(tk.Canvas):
    """Physical tower tile with Chicken-style hover/press/reveal states."""

    def __init__(
        self,
        master,
        *,
        row: int,
        col: int,
        command: Callable[[int, int], None],
        size: int = 52,
    ) -> None:
        super().__init__(
            master,
            width=size,
            height=size,
            bg=Theme.TOWER_WELL,
            bd=0,
            highlightthickness=0,
            cursor="",
        )
        self.row = row
        self.col = col
        self.command = command
        self.size = size
        self.mode = "upcoming"  # upcoming, active, gem, skull, hidden_end
        self.value: Optional[str] = None
        self._enabled = False
        self._hovered = False
        self._pressed = False
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.draw()

    def set_state(self, mode: str, value: Optional[str] = None, enabled: bool = False) -> None:
        self.mode = mode
        self.value = value
        self._enabled = enabled
        self._hovered = False
        self._pressed = False
        self.configure(cursor="hand2" if enabled else "")
        self.draw()

    def draw(self) -> None:
        self.delete("all")
        s = self.size
        shift = 2 if self._pressed and self._enabled else 0

        if self.mode == "gem":
            fill, outline, text, fg = Theme.GEM, Theme.GEM_BORDER, "💎", Theme.GEM_TEXT
        elif self.mode == "skull":
            fill, outline, text, fg = Theme.SKULL, Theme.SKULL_BORDER, "☠", "#FFFFFF"
        elif self.mode == "active":
            fill = Theme.ACCENT_SOFT if not self._hovered else "#A9C2CE"
            outline = Theme.ACCENT if self._hovered else Theme.ACTIVE_BORDER
            text, fg = "?", Theme.ACCENT
        elif self.mode == "hidden_end":
            if self.value == "skull":
                fill, outline, text, fg = "#D8AAA5", Theme.SKULL_BORDER, "☠", Theme.SKULL_BORDER
            else:
                fill, outline, text, fg = "#D8EAF1", Theme.GEM_BORDER, "💎", Theme.GEM_TEXT
        else:
            fill, outline, text, fg = Theme.UPCOMING, Theme.UPCOMING_BORDER, "·", Theme.TEXT_DIM

        self.create_rectangle(6, 7, s - 2, s - 1, fill="#938D84", outline="")
        self.create_rectangle(
            3 + shift,
            3 + shift,
            s - 5 + shift,
            s - 5 + shift,
            fill=fill,
            outline=outline,
            width=3 if self._hovered and self._enabled else 2,
        )
        if self.mode in {"active", "upcoming"}:
            self.create_line(10 + shift, 10 + shift, s - 12 + shift, 10 + shift,
                             fill="#F2ECE4", width=2)
        self.create_text(
            s / 2 + shift,
            s / 2 + shift,
            text=text,
            fill=fg,
            font=(Theme.FONT_EMOJI if self.mode in {"gem", "skull", "hidden_end"} else Theme.FONT,
                  19 if self.mode != "upcoming" else 16,
                  "bold"),
        )

    def _on_enter(self, _event) -> None:
        if self._enabled:
            self._hovered = True
            self.draw()

    def _on_leave(self, _event) -> None:
        self._hovered = False
        self._pressed = False
        self.draw()

    def _on_press(self, _event) -> None:
        if self._enabled:
            self._pressed = True
            self.draw()

    def _on_release(self, event) -> None:
        if not self._enabled:
            return
        pressed = self._pressed
        self._pressed = False
        inside = 0 <= event.x < self.size and 0 <= event.y < self.size
        if pressed and inside:
            self.command(self.row, self.col)
        else:
            self.draw()


class TowerGame:
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
    ACTION_BUTTON_HEIGHT = 34

    CELL_SIZE = 52
    CELL_GAP = 10
    ROW_STEP = 59

    def __init__(self, root, initial_balance, username):
        self.root = root
        self._configure_root()

        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0.0
        self.difficulty = "1"
        self.board: list[list[str]] = []
        self.revealed_rows: list[tuple[int, int]] = []
        self.current_round = 0
        self.game_active = False
        self.last_win = 0.0
        self.current_bet = 0.0
        self.exploded_cell: Optional[tuple[int, int]] = None
        self.last_result_text = ""

        self.chip_buttons: list[ChipButton] = []
        self.difficulty_buttons: list[ModernButton] = []
        self.tower_cells: list[list[TowerCell]] = []

        self.create_widgets()
        self.generate_board(active=False)
        self.update_display()

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("上塔游戏")
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
            master, text=title, bg=Theme.PANEL, fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 16, "bold"), anchor=tk.W,
        ).place(x=0, y=0, width=width, height=22)
        if subtitle:
            tk.Label(
                master, text=subtitle, bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
                font=(Theme.FONT_CJK, 8), anchor=tk.W,
            ).place(x=0, y=22, width=width, height=17)

    def _mini_stat(self, master, x: int, label: str, variable: tk.StringVar, color: str) -> None:
        box = tk.Frame(
            master, width=104, height=52, bg=Theme.PANEL_ALT,
            highlightthickness=1, highlightbackground=Theme.BORDER_SOFT,
        )
        box.place(x=x, y=0, width=104, height=52)
        tk.Label(
            box, text=label, bg=Theme.PANEL_ALT, fg=Theme.TEXT_DIM,
            font=(Theme.FONT_CJK, 8), anchor=tk.CENTER,
        ).place(x=4, y=5, width=96, height=16)
        tk.Label(
            box, textvariable=variable, bg=Theme.PANEL_ALT, fg=color,
            font=(Theme.FONT, 9, "bold"), anchor=tk.CENTER,
        ).place(x=4, y=24, width=96, height=20)

    def create_widgets(self) -> None:
        self.balance_var = tk.StringVar(value=f"${self.balance:.2f}")
        self.bet_var = tk.StringVar(value="$0.00")
        self.last_win_var = tk.StringVar(value="$0.00")
        self.floor_var = tk.StringVar(value="0 / 8")
        self.current_odds_var = tk.StringVar(value="--")
        self.next_odds_var = tk.StringVar(value=f"×{ODDS[self.difficulty][0]:.2f}")
        self.info_var = tk.StringVar(value="选择下注金额与难度，然后开始攀塔。")
        self.badge_var = tk.StringVar(value="入门 · 1 骷髅 / 3 宝石")
        self.potential_var = tk.StringVar(value="通过一层后即可兑现")

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
            header, text="♜", bg=Theme.APP_BG, fg=Theme.AMBER,
            font=(Theme.FONT, 30, "bold"), anchor=tk.CENTER,
        ).place(x=0, y=5, width=42, height=46)
        tk.Label(
            header, text="TOWER", bg=Theme.APP_BG, fg=Theme.TEXT,
            font=(Theme.FONT, 20, "bold"), anchor=tk.W,
        ).place(x=52, y=4, width=430, height=31)
        tk.Label(
            header, text="上塔游戏", bg=Theme.APP_BG, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 10), anchor=tk.W,
        ).place(x=52, y=37, width=520, height=22)

        balance_box = tk.Frame(
            header, width=270, height=54, bg=Theme.PANEL,
            highlightthickness=1, highlightbackground=Theme.BORDER,
        )
        balance_box.place(x=840, y=8, width=270, height=54)
        self.balance_display_var = tk.StringVar()
        def sync_balance(*_args):
            self.balance_display_var.set(f"账户余额: {self.balance_var.get()}")
        self.balance_var.trace_add("write", sync_balance)
        sync_balance()
        tk.Label(
            balance_box, textvariable=self.balance_display_var, bg=Theme.PANEL, fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 13, "bold"), anchor=tk.E,
        ).place(x=10, y=8, width=245, height=38)

    def _build_game_panel(self, master) -> None:
        panel = self._card(master, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT, padding=0)
        panel.place(x=0, y=0, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT)
        content = panel.content  # type: ignore[attr-defined]

        top = tk.Frame(content, width=self.CANVAS_WIDTH, height=74, bg=Theme.PANEL)
        top.place(x=0, y=0, width=self.CANVAS_WIDTH, height=74)
        tk.Label(
            top, textvariable=self.info_var, bg=Theme.PANEL, fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 17, "bold"), anchor=tk.W,
        ).place(x=18, y=17, width=550, height=38)
        tk.Label(
            top, textvariable=self.badge_var, bg=Theme.ACCENT_SOFT, fg=Theme.ACCENT,
            font=(Theme.FONT_CJK, 8, "bold"), anchor=tk.CENTER,
        ).place(x=574, y=19, width=152, height=32)

        self.tower_well = tk.Frame(content, width=self.CANVAS_WIDTH, height=554, bg=Theme.CANVAS_BG)
        self.tower_well.place(x=0, y=74, width=self.CANVAS_WIDTH, height=554)
        self.tower_well.pack_propagate(False)

        tk.Label(
            self.tower_well, text="从第 1 层开始向上攀登 · 当前层高亮后选择一个格子",
            bg=Theme.CANVAS_BG, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 10), anchor=tk.CENTER,
        ).place(x=0, y=8, width=self.CANVAS_WIDTH, height=24)

        # Central tower plate.
        self.tower_plate = tk.Frame(
            self.tower_well, width=570, height=482, bg=Theme.TOWER_WELL,
            highlightthickness=1, highlightbackground=Theme.BORDER,
        )
        self.tower_plate.place(x=88, y=37, width=570, height=482)
        self.tower_plate.pack_propagate(False)

        # Vertical guide makes the stacked floors read as a single tower.
        tk.Frame(self.tower_plate, bg="#8DA28F").place(x=283, y=18, width=4, height=444)

        self.row_hosts: list[tk.Frame] = []
        self.floor_labels: list[tk.Label] = []
        self.odds_labels: list[tk.Label] = []
        for row in range(8):
            y = 14 + (7 - row) * self.ROW_STEP
            floor_label = tk.Label(
                self.tower_plate, text=f"第{row + 1}层", bg=Theme.TOWER_WELL,
                fg=Theme.TEXT_MUTED, font=(Theme.FONT_CJK, 10, "bold"), anchor=tk.E,
            )
            floor_label.place(x=25, y=y + 14, width=70, height=22)
            odds_label = tk.Label(
                self.tower_plate, text=f"×{ODDS[self.difficulty][row]:.2f}",
                bg=Theme.TOWER_WELL, fg=Theme.AMBER,
                font=(Theme.FONT, 10, "bold"), anchor=tk.W,
            )
            odds_label.place(x=473, y=y + 14, width=80, height=22)
            host = tk.Frame(self.tower_plate, bg=Theme.TOWER_WELL, width=330, height=self.CELL_SIZE)
            host.place(x=120, y=y, width=330, height=self.CELL_SIZE)
            host.pack_propagate(False)
            self.row_hosts.append(host)
            self.floor_labels.append(floor_label)
            self.odds_labels.append(odds_label)

        self.potential_strip = tk.Label(
            self.tower_well, textvariable=self.potential_var,
            bg=Theme.ACCENT_SOFT, fg=Theme.ACCENT,
            font=(Theme.FONT_CJK, 10, "bold"), anchor=tk.CENTER,
        )
        self.potential_strip.place(x=217, y=524, width=312, height=26)

    def _build_control_panel(self, master) -> None:
        sidebar = tk.Frame(master, width=self.SIDEBAR_WIDTH, height=self.BODY_HEIGHT, bg=Theme.APP_BG)
        sidebar.place(x=self.GAME_PANEL_WIDTH + self.PANEL_GAP, y=0,
                      width=self.SIDEBAR_WIDTH, height=self.BODY_HEIGHT)
        sidebar.pack_propagate(False)

        MetricTile(sidebar, "当前下注", self.bet_var, Theme.CYAN, width=169, height=68).place(
            x=0, y=0, width=169, height=68
        )
        MetricTile(sidebar, "上局获胜", self.last_win_var, Theme.GREEN, width=169, height=68).place(
            x=179, y=0, width=169, height=68
        )

        bet_card = self._card(sidebar, width=348, height=120, padding=12)
        bet_card.place(x=0, y=78, width=348, height=120)
        bet_content = bet_card.content  # type: ignore[attr-defined]
        self._section_title(bet_content, "下注金额", "点击筹码可累加下注", width=322)
        for index, (label, amount, chip_color, text_color) in enumerate(CHIP_CONFIGS):
            button = ChipButton(
                bet_content, label=label, amount=amount, chip_color=chip_color,
                text_color=text_color, command=self.add_chip, width=57, height=50,
            )
            button.place(x=index * 66, y=42, width=57, height=50)
            self.chip_buttons.append(button)

        difficulty_card = self._card(sidebar, width=348, height=170, padding=12)
        difficulty_card.place(x=0, y=208, width=348, height=170)
        difficulty_content = difficulty_card.content  # type: ignore[attr-defined]
        self._section_title(difficulty_content, "难度", "每层宝石越少，赔率越高", width=322)
        for index, (name, value, detail) in enumerate(DIFFICULTIES):
            button = ModernButton(
                difficulty_content,
                text=name,
                command=lambda v=value: self.set_difficulty(v),
                background=Theme.PANEL_HOVER,
                hover_background=Theme.BORDER_SOFT,
                foreground=Theme.TEXT,
                font_size=12,
            )
            if index < 4:
                x = 0 if index % 2 == 0 else 164
                y = 42 if index < 2 else 76
                button.place(x=x, y=y, width=158, height=30)
            else:
                button.place(x=0, y=110, width=322, height=30)
            self.difficulty_buttons.append(button)

        action_card = self._card(sidebar, width=348, height=150, padding=12)
        action_card.place(x=0, y=388, width=348, height=150)
        action_content = action_card.content  # type: ignore[attr-defined]
        stats = tk.Frame(action_content, width=322, height=52, bg=Theme.PANEL)
        stats.place(x=0, y=0, width=322, height=52)
        self._mini_stat(stats, 0, "已通过", self.floor_var, Theme.TEXT)
        self._mini_stat(stats, 109, "当前赔率", self.current_odds_var, Theme.CYAN)
        self._mini_stat(stats, 218, "下层赔率", self.next_odds_var, Theme.RED)

        self.button_frame = tk.Frame(action_content, width=322, height=66, bg=Theme.PANEL)
        self.button_frame.place(x=0, y=58, width=322, height=66)
        self.reset_bet_button = ModernButton(
            self.button_frame, text="清空全部筹码", command=self.reset_bet,
            background=Theme.RED, hover_background=Theme.RED_HOVER,
            foreground="#FFFFFF", font_size=12, bold=True,
        )
        self.reset_bet_button.place(x=0, y=0, width=322, height=self.ACTION_BUTTON_HEIGHT)
        self.start_button = ModernButton(
            self.button_frame, text="开始游戏", command=self.start_game,
            background=Theme.GREEN, hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF", font_size=12, bold=True,
        )
        self.start_button.place(x=0, y=38, width=322, height=self.ACTION_BUTTON_HEIGHT)
        self.random_open_button = ModernButton(
            self.button_frame, text="随机打开", command=self.random_reveal,
            background=Theme.CYAN, hover_background=Theme.ACCENT_HOVER,
            foreground="#FFFFFF", font_size=12, bold=True,
        )
        self.random_open_button.place_forget()

        self.cash_out_button = ModernButton(
            self.button_frame, text="兑现奖金", command=self.cash_out,
            background=Theme.ACCENT, hover_background=Theme.ACCENT_HOVER,
            foreground="#FFFFFF", font_size=12, bold=True,
        )
        self.cash_out_button.place_forget()

        rules_card = self._card(sidebar, width=348, height=82, padding=12)
        rules_card.place(x=0, y=548, width=348, height=82)
        rules_content = rules_card.content  # type: ignore[attr-defined]
        tk.Label(
            rules_content,
            text="每层只选一个格子：宝石继续，骷髅全输。\n通过一层后可随时兑现；8 层全通关获得最高赔率。",
            bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9), justify=tk.LEFT, anchor=tk.W, wraplength=320,
        ).place(x=0, y=0, width=322, height=56)

        self._refresh_difficulty_styles()

    # ------------------------------------------------------------------
    # Board rendering/state
    # ------------------------------------------------------------------

    def _build_tower_cells(self) -> None:
        for host in self.row_hosts:
            for widget in host.winfo_children():
                widget.destroy()
        self.tower_cells = []
        for row, values in enumerate(self.board):
            host = self.row_hosts[row]
            count = len(values)
            total_w = count * self.CELL_SIZE + (count - 1) * self.CELL_GAP
            start_x = (330 - total_w) // 2
            row_cells: list[TowerCell] = []
            for col in range(count):
                cell = TowerCell(
                    host, row=row, col=col, command=self.select_cell, size=self.CELL_SIZE
                )
                cell.place(x=start_x + col * (self.CELL_SIZE + self.CELL_GAP),
                           y=0, width=self.CELL_SIZE, height=self.CELL_SIZE)
                row_cells.append(cell)
            self.tower_cells.append(row_cells)
        self._refresh_tower_cells()

    def _refresh_tower_cells(self) -> None:
        revealed = set(self.revealed_rows)
        for row, cells in enumerate(self.tower_cells):
            for col, cell in enumerate(cells):
                value = self.board[row][col] if self.board else "gem"
                if (row, col) in revealed:
                    cell.set_state("gem" if value == "gem" else "skull")
                elif self.game_active:
                    if row == self.current_round:
                        cell.set_state("active", enabled=True)
                    else:
                        cell.set_state("upcoming")
                elif self.last_result_text and self.board:
                    cell.set_state("hidden_end", value=value)
                else:
                    cell.set_state("upcoming")

        for row in range(8):
            active = self.game_active and row == self.current_round
            completed = row < self.current_round and any(r == row for r, _ in self.revealed_rows)
            self.floor_labels[row].configure(
                fg=Theme.ACCENT if active else (Theme.GREEN if completed else Theme.TEXT_MUTED)
            )
            self.odds_labels[row].configure(
                fg=Theme.ACCENT if active else (Theme.GREEN if completed else Theme.AMBER)
            )

    def _refresh_difficulty_styles(self) -> None:
        for button, (_name, value, _detail) in zip(self.difficulty_buttons, DIFFICULTIES):
            if value == self.difficulty:
                button.set_colors(Theme.ACCENT, Theme.ACCENT_HOVER, "#FFFFFF")
            else:
                button.set_colors(Theme.PANEL_HOVER, Theme.BORDER_SOFT, Theme.TEXT)

    def _difficulty_detail(self) -> tuple[str, str]:
        for name, value, detail in DIFFICULTIES:
            if value == self.difficulty:
                return name, detail
        return "入门", "1 骷髅 · 3 宝石"

    def update_display(self) -> None:
        self.balance_var.set(f"${self.balance:.2f}")
        self.bet_var.set(f"${self.current_bet:.2f}")
        self.last_win_var.set(f"${self.last_win:.2f}")
        self.floor_var.set(f"{self.current_round} / 8")
        if self.current_round > 0:
            current = ODDS[self.difficulty][self.current_round - 1]
            self.current_odds_var.set(f"×{current:.2f}")
        else:
            self.current_odds_var.set("--")
        if self.current_round < 8:
            self.next_odds_var.set(f"×{ODDS[self.difficulty][self.current_round]:.2f}")
        else:
            self.next_odds_var.set("MAX")

        name, detail = self._difficulty_detail()
        self.badge_var.set(f"{name} · {detail}")
        for row, label in enumerate(self.odds_labels):
            label.configure(text=f"×{ODDS[self.difficulty][row]:.2f}")

        if self.game_active:
            self.random_open_button.configure(state=tk.NORMAL, text="随机打开")
            if self.current_round == 0:
                self.info_var.set("第 1 层已解锁 · 选择一个格子开始攀塔。")
                self.potential_var.set("通过一层后即可兑现")
                self.cash_out_button.configure(state=tk.DISABLED, text="通过一层后可兑现")
            else:
                current_multiplier = ODDS[self.difficulty][self.current_round - 1]
                cash_value = self.bet_amount * current_multiplier
                self.info_var.set(f"已通过 {self.current_round} 层 · 继续攀登或立即兑现。")
                self.potential_var.set(f"当前可兑现  ${cash_value:.2f}")
                self.cash_out_button.configure(state=tk.NORMAL, text=f"兑现  ${cash_value:.2f}")
        elif self.last_result_text:
            self.info_var.set(self.last_result_text)
            self.potential_var.set("选择新下注后可再次挑战")
        else:
            self.info_var.set("选择下注金额与难度，然后开始攀塔。")
            self.potential_var.set("通过一层后即可兑现")
        self._refresh_tower_cells()

    # ------------------------------------------------------------------
    # Betting / difficulty
    # ------------------------------------------------------------------

    def add_chip(self, amount: str) -> None:
        if self.game_active:
            return
        try:
            value = float(amount)
        except ValueError:
            return
        if self.current_bet + value <= self.balance:
            self.current_bet += value
            self.last_result_text = ""
            self.update_display()

    def reset_bet(self) -> None:
        if self.game_active:
            return
        self.current_bet = 0.0
        self.last_result_text = ""
        self.update_display()

    def set_difficulty(self, difficulty: str) -> None:
        if self.game_active:
            return
        self.difficulty = str(difficulty)
        self.last_result_text = ""
        self.generate_board(active=False)
        self._refresh_difficulty_styles()
        self.update_display()

    # ------------------------------------------------------------------
    # Game flow — original rules retained
    # ------------------------------------------------------------------

    def generate_board(self, *, active: bool) -> None:
        skull_count, gem_count = SKULL_DISTRIBUTION[self.difficulty]
        board: list[list[str]] = []
        for _ in range(8):
            row = ["gem"] * gem_count + ["skull"] * skull_count
            random.shuffle(row)
            board.append(row)
        self.board = board
        self.revealed_rows = []
        self.current_round = 0
        self.game_active = active
        self.exploded_cell = None
        self._build_tower_cells()

    def start_game(self) -> None:
        if self.current_bet <= 0:
            messagebox.showwarning("提示", "请先下注。")
            return
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注。")
            return

        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        self.last_win = 0.0
        self.last_result_text = ""
        self.generate_board(active=True)
        update_balance_in_json(self.username, self.balance)

        self.reset_bet_button.place_forget()
        self.start_button.place_forget()
        self.random_open_button.place(x=0, y=0, width=322, height=self.ACTION_BUTTON_HEIGHT)
        self.cash_out_button.place(x=0, y=38, width=322, height=self.ACTION_BUTTON_HEIGHT)
        for button in self.chip_buttons:
            button.configure(state=tk.DISABLED)
        for button in self.difficulty_buttons:
            button.configure(state=tk.DISABLED)
        self.update_display()

    def select_cell(self, row: int, col: int) -> None:
        if not self.game_active or row != self.current_round:
            return
        value = self.board[row][col]
        self.revealed_rows.append((row, col))
        if value == "skull":
            self.exploded_cell = (row, col)
            self.game_active = False
            self.last_win = 0.0
            self.last_result_text = f"第 {row + 1} 层踩中骷髅 · 本局下注已损失。"
            self._refresh_tower_cells()
            self.end_game()
            return

        self.current_round += 1
        if self.current_round >= 8:
            self.complete_game()
        else:
            self.update_display()

    def random_reveal(self) -> None:
        """随机打开当前层的一个可选格子。"""
        if not self.game_active or self.current_round >= 8:
            return
        current_row = self.current_round
        if not self.board or current_row >= len(self.board):
            return
        col = random.randrange(len(self.board[current_row]))
        self.select_cell(current_row, col)

    def cash_out(self) -> None:
        if not self.game_active or self.current_round == 0:
            return
        multiplier = ODDS[self.difficulty][self.current_round - 1]
        win_amount = self.bet_amount * multiplier
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        self.last_result_text = (
            f"兑现成功 · 已通过 {self.current_round} 层。"
        )
        update_balance_in_json(self.username, self.balance)
        self.end_game()

    def complete_game(self) -> None:
        multiplier = ODDS[self.difficulty][7]
        win_amount = self.bet_amount * multiplier
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        self.last_result_text = f"登顶成功 · 8 层全部通过。"
        update_balance_in_json(self.username, self.balance)
        self.end_game()

    def end_game(self) -> None:
        self.random_open_button.place_forget()
        self.cash_out_button.place_forget()
        self.reset_bet_button.place(x=0, y=0, width=322, height=self.ACTION_BUTTON_HEIGHT)
        self.start_button.place(x=0, y=38, width=322, height=self.ACTION_BUTTON_HEIGHT)
        for button in self.chip_buttons:
            button.configure(state=tk.NORMAL)
        for button in self.difficulty_buttons:
            button.configure(state=tk.NORMAL)
        self._refresh_difficulty_styles()
        self.update_display()

    def on_closing(self) -> None:
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
            title="上塔游戏",
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        game = TowerGame(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = TowerGame(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    final_balance = main(10000.0, "test_user")
    print(f"Final balance: {final_balance}")