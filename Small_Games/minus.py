"""Mines HMI — ChickenCrossing visual-system edition.

The game rules and multiplier tables are retained from the original ``minus.py``.
The view layer is rebuilt to use the same fixed warm HMI language as
``ChickenCrossing_tk.py`` and supports the project's single-Tk embedded mode.
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
except ImportError:  # Allow direct execution inside the original project.
    from small_games import EmbeddedGamePage


VERSION = "Mines-ChickenStyle-R1"


# ---------------------------------------------------------------------------
# Theme — deliberately aligned with ChickenCrossing_tk.py
# ---------------------------------------------------------------------------


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

    SAFE = "#A9C4A5"
    SAFE_BORDER = "#4D7D52"
    HIDDEN = "#D6D0C7"
    HIDDEN_HOVER = "#C8C0B5"
    HIDDEN_BORDER = "#AAA196"
    MINE = "#C56C63"
    MINE_BORDER = "#8E4742"
    BOARD_WELL = "#B7C8B7"

    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )
    FONT_EMOJI = "Segoe UI Emoji"


# Original multiplier tables — unchanged.
odds_dict = {
    1: [
        1, 1, 1.04, 1.09, 1.14, 1.20, 1.26, 1.33, 1.41, 1.50, 1.60,
        1.71, 1.85, 2.00, 2.18, 2.40, 2.67, 3.00, 3.43, 4.00, 4.80,
        6.00, 8.00, 12.00, 24.00,
    ],
    3: [
        1, 1.09, 1.25, 1.43, 1.66, 1.94, 2.28, 2.71, 3.25, 3.94,
        4.85, 6.07, 7.72, 10.04, 13.38, 18.40, 26.29, 39.43, 63.09,
        110.40, 220.80, 552.00, 2208.00,
    ],
    5: [
        1, 1.20, 1.52, 1.94, 2.51, 3.29, 4.39, 5.95, 8.24, 11.68,
        16.98, 25.48, 39.63, 64.40, 110.40, 202.40, 404.80, 910.80,
        2428.80, 8500.80, 51004.80,
    ],
    10: [
        1, 1.60, 2.74, 4.85, 8.90, 16.98, 33.97, 71.71, 161.35,
        391.86, 1044.96, 3134.87, 10972.06, 47545.60, 285273.60,
        3138009.60,
    ],
}


DIFFICULTIES = (
    ("简单", 1, "1 雷 · 4%"),
    ("中等", 3, "3 雷 · 12%"),
    ("困难", 5, "5 雷 · 20%"),
    ("地狱", 10, "10 雷 · 40%"),
)

# Keep the original betting denominations, but render them as Chicken-style chips.
CHIP_CONFIGS = (
    ("$5", "5", "#D75A54", "white"),
    ("$25", "25", "#67B56A", "black"),
    ("$100", "100", "#292929", "white"),
    ("$500", "500", "#D47AB7", "black"),
    ("$1K", "1000", "#F4F1EA", "black"),
)


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


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
    path = get_data_file_path()
    with open(path, "w", encoding="utf-8") as file:
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
        # The UI should remain playable if a standalone test directory is read-only.
        pass


# ---------------------------------------------------------------------------
# Shared controls — same visual grammar as ChickenCrossing
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
            font=(Theme.FONT, 8 if len(self.label) <= 4 else 7, "bold"),
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


class MineCell(tk.Canvas):
    """Warm HMI mine-grid cell with hover, press and reveal states."""

    def __init__(
        self,
        master,
        *,
        row: int,
        col: int,
        command: Callable[[int, int], None],
        size: int = 92,
    ) -> None:
        super().__init__(
            master,
            width=size,
            height=size,
            bg=Theme.BOARD_WELL,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.row = row
        self.col = col
        self.command = command
        self.size = size
        self.is_revealed = False
        self.value: Optional[str] = None
        self._hovered = False
        self._pressed = False
        self._enabled = True
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.draw()

    def draw(self) -> None:
        self.delete("all")
        s = self.size
        inset = 4 + (2 if self._pressed and not self.is_revealed else 0)
        if self.is_revealed and self.value == "mine":
            fill, outline, text = Theme.MINE, Theme.MINE_BORDER, "💣"
            text_color = "#FFFFFF"
        elif self.is_revealed:
            fill, outline, text = Theme.SAFE, Theme.SAFE_BORDER, "💎"
            text_color = "#FFFFFF"
        else:
            fill = Theme.HIDDEN_HOVER if self._hovered and self._enabled else Theme.HIDDEN
            outline = Theme.ACCENT if self._hovered and self._enabled else Theme.HIDDEN_BORDER
            text = "?"
            text_color = Theme.TEXT_MUTED

        # Subtle physical shadow and inset face.
        self.create_rectangle(7, 8, s - 3, s - 2, fill="#9F998F", outline="")
        self.create_rectangle(
            inset,
            inset,
            s - inset,
            s - inset,
            fill=fill,
            outline=outline,
            width=3 if self._hovered and not self.is_revealed else 2,
        )
        if not self.is_revealed:
            self.create_line(inset + 8, inset + 8, s - inset - 8, inset + 8,
                             fill="#EFEAE3", width=2)
            self.create_line(inset + 8, inset + 8, inset + 8, s - inset - 8,
                             fill="#EFEAE3", width=2)
        self.create_text(
            s / 2,
            s / 2 + (2 if self._pressed else 0),
            text=text,
            fill=text_color,
            font=(Theme.FONT_EMOJI if self.is_revealed else Theme.FONT, 25, "bold"),
        )

        if not self._enabled and not self.is_revealed:
            self.create_rectangle(
                inset,
                inset,
                s - inset,
                s - inset,
                fill="#CBC4BB",
                outline=Theme.BORDER_SOFT,
                stipple="gray50",
            )

    def reset(self, enabled: bool = False) -> None:
        self.is_revealed = False
        self.value = None
        self._enabled = enabled
        self._hovered = self._pressed = False
        self.configure(cursor="hand2" if enabled else "")
        self.draw()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled and not self.is_revealed else "")
        self.draw()

    def reveal(self, value: str) -> None:
        self.is_revealed = True
        self.value = value
        self._enabled = False
        self._hovered = self._pressed = False
        self.configure(cursor="")
        self.draw()

    def _on_enter(self, _event) -> None:
        if self._enabled and not self.is_revealed:
            self._hovered = True
            self.draw()

    def _on_leave(self, _event) -> None:
        self._hovered = False
        self._pressed = False
        self.draw()

    def _on_press(self, _event) -> None:
        if self._enabled and not self.is_revealed:
            self._pressed = True
            self.draw()

    def _on_release(self, event) -> None:
        if not self._enabled or self.is_revealed:
            return
        pressed = self._pressed
        self._pressed = False
        inside = 0 <= event.x < self.size and 0 <= event.y < self.size
        if pressed and inside:
            self.command(self.row, self.col)
        else:
            self.draw()


# ---------------------------------------------------------------------------
# Main game
# ---------------------------------------------------------------------------


class MinesGame:
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
    ACTION_BUTTON_WIDTH = 322
    ACTION_BUTTON_HEIGHT = 38

    BOARD_SIZE = 5
    CELL_SIZE = 92
    CELL_GAP = 9
    BOARD_PIXEL = BOARD_SIZE * CELL_SIZE + (BOARD_SIZE - 1) * CELL_GAP

    def __init__(self, root, initial_balance, username):
        self.root = root
        self._configure_root()

        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0.0
        self.mines_count = 1
        self.board: list[list[str]] = []
        self.revealed_cells: set[tuple[int, int]] = set()
        self.game_active = False
        self.last_win = 0.0
        self.current_bet = 0.0
        self.current_odds = 1.0
        self.next_odds = 1.0
        self.cell_buttons: list[list[MineCell]] = []
        self.chip_buttons: list[ChipButton] = []
        self.difficulty_buttons: list[ModernButton] = []
        self.last_result_text = ""

        self.create_widgets()
        self.update_display()

    # ------------------------------------------------------------------
    # Fixed ChickenCrossing window and cards
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("扫雷游戏")
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

    def create_widgets(self) -> None:
        self.balance_var = tk.StringVar(value=f"${self.balance:.2f}")
        self.bet_var = tk.StringVar(value="$0.00")
        self.last_win_var = tk.StringVar(value="$0.00")
        self.safe_count_var = tk.StringVar(value="0 / 24")
        self.current_odds_var = tk.StringVar(value="×1.00")
        self.next_odds_var = tk.StringVar(value="×1.00")
        self.info_var = tk.StringVar(value="选择下注金额与雷数，然后开始游戏。")
        self.board_badge_var = tk.StringVar(value="5 × 5 · 1 雷")

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
            text="💣",
            bg=Theme.APP_BG,
            fg=Theme.AMBER,
            font=(Theme.FONT_EMOJI, 27),
            anchor=tk.CENTER,
        ).place(x=0, y=7, width=42, height=44)
        tk.Label(
            header,
            text="MINES",
            bg=Theme.APP_BG,
            fg=Theme.TEXT,
            font=(Theme.FONT, 20, "bold"),
            anchor=tk.W,
        ).place(x=52, y=4, width=430, height=31)
        tk.Label(
            header,
            text="扫雷游戏",
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

        def update_balance_display(*_args):
            self.balance_display_var.set(f"账户余额: {self.balance_var.get()}")

        self.balance_var.trace_add("write", update_balance_display)
        tk.Label(
            balance_box,
            textvariable=self.balance_display_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 13, "bold"),
            anchor=tk.E,
        ).place(x=10, y=8, width=245, height=38)

    def _build_game_panel(self, master) -> None:
        panel = self._card(master, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT, padding=0)
        panel.place(x=0, y=0, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT)
        content = panel.content  # type: ignore[attr-defined]

        top = tk.Frame(content, width=self.CANVAS_WIDTH, height=74, bg=Theme.PANEL)
        top.place(x=0, y=0, width=self.CANVAS_WIDTH, height=74)
        top.pack_propagate(False)
        tk.Label(
            top,
            textvariable=self.info_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 18, "bold"),
            anchor=tk.W,
        ).place(x=18, y=18, width=565, height=36)
        tk.Label(
            top,
            textvariable=self.board_badge_var,
            bg=Theme.ACCENT_SOFT,
            fg=Theme.ACCENT,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.CENTER,
        ).place(x=608, y=19, width=118, height=32)

        board_well = tk.Frame(
            content,
            width=self.CANVAS_WIDTH,
            height=554,
            bg=Theme.CANVAS_BG,
        )
        board_well.place(x=0, y=74, width=self.CANVAS_WIDTH, height=554)
        board_well.pack_propagate(False)

        # Two quiet info strips make the game area feel like the Chicken HMI rather
        # than an isolated 5x5 widget floating in a panel.=
        board_frame = tk.Frame(
            board_well,
            width=self.BOARD_PIXEL + 34,
            height=self.BOARD_PIXEL + 34,
            bg=Theme.BOARD_WELL,
            highlightthickness=1,
            highlightbackground=Theme.BORDER,
        )
        board_x = (self.CANVAS_WIDTH - (self.BOARD_PIXEL + 34)) // 2
        board_frame.place(
            x=board_x,
            y=14,
            width=self.BOARD_PIXEL + 34,
            height=self.BOARD_PIXEL + 34,
        )
        board_frame.pack_propagate(False)

        self.board_frame = tk.Frame(
            board_frame,
            width=self.BOARD_PIXEL,
            height=self.BOARD_PIXEL,
            bg=Theme.BOARD_WELL,
        )
        self.board_frame.place(x=17, y=17, width=self.BOARD_PIXEL, height=self.BOARD_PIXEL)
        self.board_frame.pack_propagate(False)
        self.board_frame.grid_propagate(False)
        self.create_game_board()

    def _build_control_panel(self, master) -> None:
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
        chip_width = 57
        chip_gap = 9
        start_x = 0
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
            button.place(x=start_x + index * (chip_width + chip_gap), y=42, width=chip_width, height=50)
            self.chip_buttons.append(button)

        difficulty_card = self._card(sidebar, width=348, height=144, padding=12)
        difficulty_card.place(x=0, y=208, width=348, height=144)
        difficulty_content = difficulty_card.content  # type: ignore[attr-defined]
        self._section_title(difficulty_content, "地雷数量", "雷越多，倍率提升越快", width=322)
        for index, (name, value, risk) in enumerate(DIFFICULTIES):
            button = ModernButton(
                difficulty_content,
                text=f"{name}  ·  {risk}",
                command=lambda mines=value: self.set_difficulty(mines),
                background=Theme.PANEL_HOVER,
                hover_background=Theme.BORDER_SOFT,
                foreground=Theme.TEXT,
                font_size=11,
            )
            x = 0 if index % 2 == 0 else 167
            y = 44 if index < 2 else 82
            button.place(x=x, y=y, width=155, height=32)
            self.difficulty_buttons.append(button)

        action_card = self._card(sidebar, width=348, height=164, padding=12)
        action_card.place(x=0, y=362, width=348, height=164)
        action_content = action_card.content  # type: ignore[attr-defined]

        stats = tk.Frame(action_content, width=322, height=52, bg=Theme.PANEL)
        stats.place(x=0, y=0, width=322, height=52)
        self._mini_stat(stats, 0, "安全格", self.safe_count_var, Theme.TEXT)
        self._mini_stat(stats, 109, "当前赔率", self.current_odds_var, Theme.CYAN)
        self._mini_stat(stats, 218, "下格赔率", self.next_odds_var, Theme.RED)

        self.button_frame = tk.Frame(action_content, width=322, height=80, bg=Theme.PANEL)
        self.button_frame.place(x=0, y=58, width=322, height=80)
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
        self.reset_bet_button.place(x=0, y=0, width=322, height=self.ACTION_BUTTON_HEIGHT)

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
        self.start_button.place(x=0, y=42, width=322, height=self.ACTION_BUTTON_HEIGHT)

        self.random_button = ModernButton(
            self.button_frame,
            text="随机打开一格",
            command=self.random_reveal,
            background=Theme.ACCENT,
            hover_background=Theme.ACCENT_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.random_button.place_forget()

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

        rules_card = self._card(sidebar, width=348, height=94, padding=12)
        rules_card.place(x=0, y=536, width=348, height=94)
        rules_content = rules_card.content  # type: ignore[attr-defined]
        tk.Label(
            rules_content,
            text="找到宝石后倍率递增，可随时兑现。\n踩中地雷将损失本局全部下注。",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 11),
            justify=tk.LEFT,
            anchor=tk.W,
            wraplength=318,
        ).place(x=0, y=0, width=322, height=66)

        self._refresh_difficulty_styles()

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

    # ------------------------------------------------------------------
    # Board and UI state
    # ------------------------------------------------------------------

    def create_game_board(self) -> None:
        for widget in self.board_frame.winfo_children():
            widget.destroy()
        self.cell_buttons = []
        for row in range(self.BOARD_SIZE):
            row_buttons: list[MineCell] = []
            for col in range(self.BOARD_SIZE):
                button = MineCell(
                    self.board_frame,
                    row=row,
                    col=col,
                    command=self.select_cell,
                    size=self.CELL_SIZE,
                )
                x = col * (self.CELL_SIZE + self.CELL_GAP)
                y = row * (self.CELL_SIZE + self.CELL_GAP)
                button.place(x=x, y=y, width=self.CELL_SIZE, height=self.CELL_SIZE)
                button.reset(enabled=self.game_active)
                row_buttons.append(button)
            self.cell_buttons.append(row_buttons)

    def _refresh_difficulty_styles(self) -> None:
        for button, (_name, value, _risk) in zip(self.difficulty_buttons, DIFFICULTIES):
            if value == self.mines_count:
                button.set_colors(Theme.ACCENT, Theme.ACCENT_HOVER, "#FFFFFF")
            else:
                button.set_colors(Theme.PANEL_HOVER, Theme.BORDER_SOFT, Theme.TEXT)

    def _set_board_enabled(self, enabled: bool) -> None:
        for row in self.cell_buttons:
            for button in row:
                if not button.is_revealed:
                    button.set_enabled(enabled)

    def _next_multiplier(self) -> Optional[float]:
        next_index = len(self.revealed_cells) + 1
        table = odds_dict[self.mines_count]
        return table[next_index] if next_index < len(table) else None

    def update_display(self) -> None:
        self.balance_var.set(f"${self.balance:.2f}")
        self.bet_var.set(f"${self.current_bet:.2f}")
        self.last_win_var.set(f"${self.last_win:.2f}")
        safe_total = 25 - self.mines_count
        safe_open = len(self.revealed_cells)
        self.safe_count_var.set(f"{safe_open} / {safe_total}")
        self.current_odds_var.set(f"×{self.current_odds:.2f}")
        next_multiplier = self._next_multiplier() if self.game_active else None
        self.next_odds_var.set(f"×{next_multiplier:.2f}" if next_multiplier is not None else "--")
        self.board_badge_var.set(f"5 × 5 · {self.mines_count} 雷")

        live_bet = self.bet_amount if self.game_active else self.current_bet
        potential = live_bet * self.current_odds if live_bet > 0 else 0.0

        if self.game_active:
            self.info_var.set(f"已安全打开 {safe_open} 格 · 继续挑战或立即兑现。")
            self.cash_out_button.configure(text=f"兑现  ${potential:.2f}")
        elif self.last_result_text:
            self.info_var.set(self.last_result_text)
        else:
            self.info_var.set("选择下注金额与雷数，然后开始游戏。")

    # ------------------------------------------------------------------
    # Betting and difficulty
    # ------------------------------------------------------------------

    def add_chip(self, amount: str) -> None:
        if self.game_active:
            return
        try:
            amount_val = float(amount)
        except ValueError:
            return
        if self.current_bet + amount_val <= self.balance:
            self.current_bet += amount_val
            self.last_result_text = ""
            self.update_display()

    def reset_bet(self) -> None:
        if self.game_active:
            return
        self.current_bet = 0.0
        self.last_result_text = ""
        self.update_display()

    def set_difficulty(self, mines_count: int) -> None:
        if self.game_active:
            return
        self.mines_count = int(mines_count)
        self.current_odds = 1.0
        self.last_result_text = ""
        self._refresh_difficulty_styles()
        self.update_display()

    # ------------------------------------------------------------------
    # Game flow — rules preserved from the original minus.py
    # ------------------------------------------------------------------

    def generate_board(self) -> None:
        positions = set(random.sample(range(25), self.mines_count))
        self.board = [["safe" for _ in range(5)] for _ in range(5)]
        for pos in positions:
            self.board[pos // 5][pos % 5] = "mine"
        self.revealed_cells = set()
        self.game_active = True
        self.current_odds = 1.0
        self.create_game_board()
        self._set_board_enabled(True)
        self.update_display()

    def start_game(self) -> None:
        if self.current_bet <= 0:
            messagebox.showinfo("提示", "请先设置下注金额！")
            return
        if self.current_bet > self.balance:
            messagebox.showinfo("错误", "下注金额不能超过余额！")
            return

        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        self.last_win = 0.0
        self.last_result_text = ""
        self.generate_board()
        update_balance_in_json(self.username, self.balance)

        self.reset_bet_button.place_forget()
        self.start_button.place_forget()
        self.random_button.place(x=0, y=0, width=322, height=self.ACTION_BUTTON_HEIGHT)
        self.cash_out_button.place(x=0, y=42, width=322, height=self.ACTION_BUTTON_HEIGHT)

        for button in self.chip_buttons:
            button.configure(state=tk.DISABLED)
        for button in self.difficulty_buttons:
            button.configure(state=tk.DISABLED)
        self.update_display()

    def random_reveal(self) -> None:
        if not self.game_active:
            return
        unrevealed = [
            (row, col)
            for row in range(5)
            for col in range(5)
            if not self.cell_buttons[row][col].is_revealed
        ]
        if unrevealed:
            self.select_cell(*random.choice(unrevealed))

    def select_cell(self, row: int, col: int) -> None:
        if not self.game_active or self.cell_buttons[row][col].is_revealed:
            return

        cell_value = self.board[row][col]
        if cell_value == "mine":
            self.cell_buttons[row][col].reveal("mine")
            self.game_active = False
            self.last_win = 0.0
            self.last_result_text = "踩中地雷 · 本局下注已损失。"
            self.reveal_all_cells()
            self.end_game()
            messagebox.showinfo("游戏结束", "你踩到了地雷！游戏结束。")
            return

        # Safe cell: only safe reveals contribute to the payout index, matching
        # the original successful-step progression.
        self.revealed_cells.add((row, col))
        self.cell_buttons[row][col].reveal("safe")
        odds_index = len(self.revealed_cells)
        table = odds_dict[self.mines_count]
        if odds_index < len(table):
            self.current_odds = table[odds_index]
        self.update_display()

        if len(self.revealed_cells) == 25 - self.mines_count:
            self.complete_game()

    def reveal_all_cells(self) -> None:
        for row in range(5):
            for col in range(5):
                if not self.cell_buttons[row][col].is_revealed:
                    self.cell_buttons[row][col].reveal(self.board[row][col])

    def cash_out(self) -> None:
        if not self.game_active:
            return
        win_amount = self.bet_amount * self.current_odds
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        self.last_result_text = f"兑现成功 · 本局返还 ${win_amount:.2f}。"
        update_balance_in_json(self.username, self.balance)
        self.reveal_all_cells()
        self.end_game()
        messagebox.showinfo("兑现成功", f"你成功兑现了 ${win_amount:.2f}！")

    def complete_game(self) -> None:
        win_amount = self.bet_amount * self.current_odds
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        self.last_result_text = f"全部安全格已开启 · 本局返还 ${win_amount:.2f}。"
        update_balance_in_json(self.username, self.balance)
        self.reveal_all_cells()
        self.end_game()
        messagebox.showinfo("游戏胜利", f"恭喜！你发现了所有宝石，赢得 ${win_amount:.2f}！")

    def end_game(self) -> None:
        self._set_board_enabled(False)
        self.random_button.place_forget()
        self.cash_out_button.place_forget()
        self.reset_bet_button.place(x=0, y=0, width=322, height=self.ACTION_BUTTON_HEIGHT)
        self.start_button.place(x=0, y=42, width=322, height=self.ACTION_BUTTON_HEIGHT)
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


# ---------------------------------------------------------------------------
# Public entry point — compatible with small_games.py single-Tk embedding
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
            title="扫雷游戏",
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        game = MinesGame(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = MinesGame(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    final_balance = main(10000.0, "test_user")
    print(f"Final balance: {final_balance}")