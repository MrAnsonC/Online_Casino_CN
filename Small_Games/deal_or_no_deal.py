"""Deal or No Deal — ChickenCrossing-style warm HMI edition.

The game logic remains compatible with the original project, while the visual
system follows ChickenCrossing_tk.py: fixed 1150x750 viewport, warm mineral
palette, 1110x714 shell, 70px header, 748/348 game/sidebar split, metric tiles,
flat modern buttons, fixed cards, and the EmbeddedGamePage entry point.
"""

from __future__ import annotations

import json
import os
import random
import statistics
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import Callable, Optional

try:
    from .small_games import EmbeddedGamePage
except ImportError:  # Allow direct execution from the Small_Games folder.
    from small_games import EmbeddedGamePage


# ---------------------------------------------------------------------------
# Theme — intentionally aligned with ChickenCrossing_tk.py
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

    # Deal-or-No-Deal-specific warm accents, kept inside the same visual family.
    CASE = "#A97745"
    CASE_DARK = "#705033"
    CASE_LIGHT = "#C99A66"
    SELECTED = "#B7CCD5"
    SELECTED_BORDER = "#345E73"
    OPENED = "#D4CEC5"
    PRIZE_LIVE = "#EEE7DC"
    PRIZE_GONE = "#CCC5BB"
    BANKER = "#8D6732"

    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )
    FONT_EMOJI = "Segoe UI Emoji"


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def get_data_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../saving_data.json")


def save_user_data(users) -> None:
    with open(get_data_file_path(), "w", encoding="utf-8") as file:
        json.dump(users, file, ensure_ascii=False, indent=4)


def load_user_data():
    try:
        with open(get_data_file_path(), "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def update_balance_in_json(username: str, new_balance: float) -> None:
    users = load_user_data()
    found = False
    for user in users:
        if user.get("user_name") == username:
            user["cash"] = f"{new_balance:.2f}"
            found = True
            break
    if not found and username:
        users.append({"user_name": username, "cash": f"{new_balance:.2f}"})
    save_user_data(users)


# ---------------------------------------------------------------------------
# Reusable controls — same design grammar as ChickenCrossing_tk.py
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
    """ChickenCrossing-style tactile chip. Clicking directly adds the chip."""

    def __init__(
        self,
        master,
        *,
        label: str,
        amount: float,
        chip_color: str,
        text_color: str,
        command: Callable[[float], None],
        width: int = 58,
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
        self.amount = float(amount)
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

        self.create_oval(7, 7, self.control_width - 6, self.control_height - 1,
                         fill="#8E877E", outline="")
        self.create_oval(6, 3 + offset_y, self.control_width - 7,
                         self.control_height - 5 + offset_y,
                         fill=outer, outline=outline, width=outline_width)
        self.create_oval(10, 7 + offset_y, self.control_width - 11,
                         self.control_height - 9 + offset_y,
                         fill=self.chip_color, outline=inner, width=2)
        self.create_oval(15, 12 + offset_y, self.control_width - 16,
                         self.control_height - 14 + offset_y,
                         fill=self.chip_color, outline=outer, width=1)

        cx = self.control_width / 2
        cy = (self.control_height - 2) / 2 + offset_y
        for x1, y1, x2, y2 in (
            (cx - 3, 4 + offset_y, cx + 3, 10 + offset_y),
            (cx - 3, self.control_height - 12 + offset_y, cx + 3,
             self.control_height - 6 + offset_y),
            (7, cy - 3, 13, cy + 3),
            (self.control_width - 14, cy - 3, self.control_width - 8, cy + 3),
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
            self.create_oval(6, 3 + offset_y, self.control_width - 7,
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
        ).place(x=12, y=8, width=145, height=17)
        tk.Label(
            self,
            textvariable=variable,
            bg=Theme.PANEL_ALT,
            fg=accent,
            font=(Theme.FONT, 14, "bold"),
            anchor=tk.W,
        ).place(x=12, y=28, width=145, height=28)


class CaseButton(tk.Canvas):
    """Compact suitcase card that fits the ChickenCrossing fixed game panel."""

    WIDTH = 57
    HEIGHT = 94

    def __init__(self, master, idx: int, command=None, **kwargs):
        super().__init__(
            master,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg=Theme.PANEL,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            **kwargs,
        )
        self.idx = idx
        self.command = command
        self.is_open = False
        self.is_selected = False
        self.enabled = True
        self.amount_text = ""
        self._hovered = False
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.draw_closed()

    def draw_closed(self, is_selected: Optional[bool] = None) -> None:
        if is_selected is not None:
            self.is_selected = is_selected
        self.delete("all")

        card_fill = Theme.SELECTED if self.is_selected else Theme.PANEL_ALT
        card_border = Theme.SELECTED_BORDER if self.is_selected else (
            Theme.BORDER if self._hovered and self.enabled else Theme.BORDER_SOFT
        )
        border_width = 2 if self.is_selected or self._hovered else 1
        self.create_rectangle(1, 1, self.WIDTH - 2, self.HEIGHT - 2,
                              fill=card_fill, outline=card_border, width=border_width)

        # Suitcase handle and body.
        self.create_arc(19, 14, 38, 34, start=0, extent=180,
                        style=tk.ARC, outline=Theme.CASE_DARK, width=3)
        self.create_rectangle(8, 25, 49, 66,
                              fill=Theme.CASE if self.enabled else Theme.OPENED,
                              outline=Theme.CASE_DARK if self.enabled else Theme.BORDER,
                              width=2)
        self.create_rectangle(8, 34, 49, 39,
                              fill=Theme.CASE_LIGHT if self.enabled else Theme.PRIZE_GONE,
                              outline="")
        self.create_rectangle(26, 43, 31, 52,
                              fill=Theme.AMBER if self.enabled else Theme.TEXT_DIM,
                              outline=Theme.CASE_DARK, width=1)
        self.create_text(28.5, 55, text="?", fill="#FFF8EB",
                         font=(Theme.FONT, 11, "bold"))

        self.create_text(
            self.WIDTH / 2,
            80,
            text=f"CASE {self.idx + 1:02d}",
            fill=Theme.ACCENT if self.is_selected else Theme.TEXT_MUTED,
            font=(Theme.FONT, 7, "bold"),
        )
        if self.is_selected:
            self.create_text(self.WIDTH / 2, 9, text="你的箱子",
                             fill=Theme.ACCENT, font=(Theme.FONT_CJK, 7, "bold"))

    def draw_open(self, color: Optional[str] = None) -> None:
        self.delete("all")
        fill = color or Theme.OPENED
        border = Theme.ACCENT if color == "white" else Theme.BORDER_SOFT
        self.create_rectangle(1, 1, self.WIDTH - 2, self.HEIGHT - 2,
                              fill=Theme.PANEL_ALT, outline=border, width=2)
        self.create_rectangle(8, 26, 49, 66, fill=fill,
                              outline=Theme.BORDER, width=2)
        self.create_line(10, 24, 47, 12, fill=Theme.CASE_DARK, width=3)
        self.create_line(47, 12, 49, 25, fill=Theme.CASE_DARK, width=3)
        font_size = 8 if len(self.amount_text) <= 7 else 7
        self.create_text(28.5, 47, text=self.amount_text,
                         fill=Theme.TEXT, font=(Theme.FONT, font_size, "bold"),
                         width=38)
        self.create_text(self.WIDTH / 2, 80, text=f"CASE {self.idx + 1:02d}",
                         fill=Theme.TEXT_DIM, font=(Theme.FONT, 7, "bold"))

    def set_open(self, amount: str, custom_color: Optional[str] = None) -> None:
        self.is_open = True
        self.enabled = False
        self.amount_text = amount
        self.draw_open(custom_color)
        self.configure(cursor="")

    def set_closed(self) -> None:
        self.is_open = False
        self.is_selected = False
        self.enabled = True
        self.amount_text = ""
        self.configure(cursor="hand2")
        self.draw_closed(False)

    def set_selected(self, selected: bool = True) -> None:
        self.is_selected = selected
        if not self.is_open:
            self.draw_closed(selected)

    def enable(self) -> None:
        if not self.is_open:
            self.enabled = True
            self.configure(cursor="hand2")
            self.draw_closed()

    def disable(self) -> None:
        self.enabled = False
        self.configure(cursor="")
        if not self.is_open:
            self.draw_closed()

    def _on_enter(self, _event) -> None:
        if self.enabled and not self.is_open:
            self._hovered = True
            self.draw_closed()

    def _on_leave(self, _event) -> None:
        if self._hovered:
            self._hovered = False
            if not self.is_open:
                self.draw_closed()

    def _on_click(self, _event) -> None:
        if self.is_open or not self.enabled:
            return
        if self.command:
            self.command(self.idx)


# ---------------------------------------------------------------------------
# Game configuration
# ---------------------------------------------------------------------------


BASE_VALUES = [
    0.01, 0.1, 0.5, 1, 2, 5, 10, 15,
    20, 25, 35, 50, 60, 75, 100, 125,
    150, 175, 200, 250, 300, 350, 400, 500,
    650, 800, 1000, 1500,
    2500, 5000, 10000, 12000,
]

CHIP_CONFIGS = (
    ("$1K", 1000, "#D96055", "white"),
    ("$5K", 5000, "#67A76F", "black"),
    ("$10K", 10000, "#31363A", "white"),
    ("$25K", 25000, "#C98BB3", "black"),
    ("$100K", 100000, "#F3EEE6", "black"),
)


# ---------------------------------------------------------------------------
# Main game
# ---------------------------------------------------------------------------


class DealOrNoDealGame:
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
    ACTION_BUTTON_WIDTH = 322
    ACTION_BUTTON_HEIGHT = 38

    def __init__(self, root, initial_balance, username):
        self.root = root
        self._configure_root()

        self.username = username
        self.balance = float(initial_balance)
        self.bet_amount = 0.0
        self.n = 1.0
        self.box_values = []
        self.player_box_index = -1
        self.player_box_value = 0.0
        self.opened_indices = set()
        self.rounds = [7, 6, 5, 4, 3, 2, 1, 1, 1]
        self.current_round = 0
        self.to_open_this_round = 0
        self.game_active = False
        self.waiting_for_decision = False
        self.lost_quote_right = False
        self.last_win = 0.0
        self.current_offer = 0.0

        self.offer_history = []
        self.selected_chip = None
        self.chip_buttons = []
        self.box_buttons = []
        self.remaining_labels = []
        self.sorted_amounts = []
        self.history_labels = []

        self.create_widgets()
        self.update_balance_display()
        self.update_bet_display()
        self.update_remaining_panel()
        self.update_ui_state()

    # ------------------------------------------------------------------
    # Root and shared layout helpers
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("成交与否")
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

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def create_widgets(self) -> None:
        self.balance_var = tk.StringVar(value=f"${self.balance:.2f}")
        self.bet_var = tk.StringVar(value="$0.00")
        self.last_win_var = tk.StringVar(value="$0.00")
        self.round_stat_var = tk.StringVar(value="待开始")
        self.remaining_stat_var = tk.StringVar(value="—")
        self.offer_stat_var = tk.StringVar(value="—")
        self.round_info_var = tk.StringVar(value="未开始游戏")
        self.need_open_var = tk.StringVar(value="选择下注金额，然后选择一个箱子。")
        self.info_var = tk.StringVar(value="选择下注金额，再选一个箱子作为你的箱子。")
        self.bet_info_var = self.bet_var

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
        body = tk.Frame(shell, width=self.SHELL_WIDTH, height=self.BODY_HEIGHT, bg=Theme.APP_BG)
        body.place(x=0, y=self.BODY_TOP, width=self.SHELL_WIDTH, height=self.BODY_HEIGHT)
        body.pack_propagate(False)
        body.grid_propagate(False)
        self._build_game_panel(body)
        self._build_control_panel(body)

    def _build_header(self, master) -> None:
        header = tk.Frame(master, width=self.SHELL_WIDTH, height=self.HEADER_HEIGHT, bg=Theme.APP_BG)
        header.place(x=0, y=0, width=self.SHELL_WIDTH, height=self.HEADER_HEIGHT)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="💼",
            bg=Theme.APP_BG,
            fg=Theme.AMBER,
            font=(Theme.FONT_EMOJI, 27),
            anchor=tk.CENTER,
        ).place(x=0, y=7, width=42, height=44)
        tk.Label(
            header,
            text="DEAL OR NO DEAL",
            bg=Theme.APP_BG,
            fg=Theme.TEXT,
            font=(Theme.FONT, 20, "bold"),
            anchor=tk.W,
        ).place(x=52, y=4, width=430, height=31)
        tk.Label(
            header,
            text="成交与否",
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

        def _sync_balance_text(*_):
            self.balance_display_var.set(f"账户余额: {self.balance_var.get()}")

        self.balance_var.trace_add("write", _sync_balance_text)
        tk.Label(
            balance_box,
            textvariable=self.balance_display_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 13, "bold"),
            anchor=tk.E,
        ).place(x=12, y=8, width=246, height=40)

    def _build_game_panel(self, master) -> None:
        panel = self._card(master, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT, padding=0)
        panel.place(x=0, y=0, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT)
        content = panel.content  # type: ignore[attr-defined]

        top = tk.Frame(content, width=746, height=74, bg=Theme.PANEL)
        top.place(x=0, y=0, width=746, height=74)
        top.pack_propagate(False)
        self.info_label = tk.Label(
            top,
            textvariable=self.info_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 18, "bold"),
            anchor=tk.W,
        )
        self.info_label.place(x=18, y=18, width=545, height=36)
        self.phase_badge_var = tk.StringVar(value="选择阶段")
        tk.Label(
            top,
            textvariable=self.phase_badge_var,
            bg=Theme.ACCENT_SOFT,
            fg=Theme.ACCENT,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.CENTER,
        ).place(x=608, y=19, width=120, height=32)

        playfield = tk.Frame(content, width=746, height=554, bg=Theme.CANVAS_BG)
        playfield.place(x=0, y=74, width=746, height=554)
        playfield.pack_propagate(False)

        cases_panel = tk.Frame(playfield, width=520, height=554, bg=Theme.CANVAS_BG)
        cases_panel.place(x=0, y=0, width=520, height=554)
        cases_panel.pack_propagate(False)

        tk.Label(
            cases_panel,
            text="32 个箱子",
            bg=Theme.CANVAS_BG,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 10, "bold"),
            anchor=tk.W,
        ).place(x=22, y=16, width=180, height=22)
        self.player_case_var = tk.StringVar(value="你的箱子：未选择")
        tk.Label(
            cases_panel,
            textvariable=self.player_case_var,
            bg=Theme.CANVAS_BG,
            fg=Theme.ACCENT,
            font=(Theme.FONT_CJK, 10, "bold"),
            anchor=tk.E,
        ).place(x=250, y=16, width=245, height=22)

        cases_grid = tk.Frame(cases_panel, width=492, height=438, bg=Theme.CANVAS_BG)
        cases_grid.place(x=14, y=51, width=492, height=438)
        cases_grid.pack_propagate(False)
        self.create_boxes(cases_grid)

        hint = tk.Frame(
            cases_panel,
            width=482,
            height=43,
            bg=Theme.PANEL,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        hint.place(x=19, y=498, width=482, height=43)
        tk.Label(
            hint,
            text="箱子打开后会从右侧奖金表划除；你的箱子会一直保留到最后。",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9),
            anchor=tk.CENTER,
        ).place(x=8, y=5, width=466, height=31)

        prize_panel = tk.Frame(
            playfield,
            width=226,
            height=554,
            bg=Theme.PANEL,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        prize_panel.place(x=520, y=0, width=226, height=554)
        prize_panel.pack_propagate(False)
        tk.Label(
            prize_panel,
            text="剩余奖金",
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 15, "bold"),
            anchor=tk.W,
        ).place(x=14, y=12, width=140, height=24)
        tk.Label(
            prize_panel,
            text="LIVE VALUES",
            bg=Theme.ACCENT_SOFT,
            fg=Theme.ACCENT,
            font=(Theme.FONT, 8, "bold"),
            anchor=tk.CENTER,
        ).place(x=135, y=12, width=76, height=24)
        prizes = tk.Frame(prize_panel, width=204, height=494, bg=Theme.PANEL)
        prizes.place(x=10, y=49, width=204, height=494)
        prizes.pack_propagate(False)
        self.create_remaining_panel(prizes)

    def _build_control_panel(self, master) -> None:
        sidebar_x = self.GAME_PANEL_WIDTH + self.PANEL_GAP
        sidebar = tk.Frame(master, width=self.SIDEBAR_WIDTH, height=self.BODY_HEIGHT, bg=Theme.APP_BG)
        sidebar.place(x=sidebar_x, y=0, width=self.SIDEBAR_WIDTH, height=self.BODY_HEIGHT)
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
        self._section_title(bet_content, "下注金额", "点击筹码直接加入本局下注", width=322)
        chip_width = 58
        chip_gap = 8
        for index, (label, amount, chip_color, text_color) in enumerate(CHIP_CONFIGS):
            button = ChipButton(
                bet_content,
                label=label,
                amount=amount,
                chip_color=chip_color,
                text_color=text_color,
                command=self.add_chip_to_bet,
                width=chip_width,
                height=50,
            )
            button.place(x=index * (chip_width + chip_gap), y=42, width=chip_width, height=50)
            self.chip_buttons.append(button)

        action_card = self._card(sidebar, width=348, height=220, padding=12)
        action_card.place(x=0, y=208, width=348, height=220)
        action_content = action_card.content  # type: ignore[attr-defined]

        stats = tk.Frame(action_content, width=322, height=52, bg=Theme.PANEL)
        stats.place(x=0, y=0, width=322, height=52)
        self._mini_stat(stats, 0, "轮次", self.round_stat_var, Theme.TEXT)
        self._mini_stat(stats, 109, "还需开箱", self.remaining_stat_var, Theme.CYAN)
        self._mini_stat(stats, 218, "银行报价", self.offer_stat_var, Theme.AMBER)

        tk.Label(
            action_content,
            textvariable=self.need_open_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9),
            anchor=tk.W,
        ).place(x=0, y=58, width=322, height=24)

        self.action_frame = tk.Frame(action_content, width=322, height=110, bg=Theme.PANEL)
        self.action_frame.place(x=0, y=86, width=322, height=110)
        self.action_frame.pack_propagate(False)
        self._create_action_controls()
        self.show_start_buttons()

        history_card = self._card(sidebar, width=348, height=192, padding=12)
        history_card.place(x=0, y=438, width=348, height=192)
        history_content = history_card.content  # type: ignore[attr-defined]
        self._section_title(history_content, "历史报价", "银行家每轮报价记录", width=322)
        history_host = tk.Frame(history_content, width=322, height=126, bg=Theme.PANEL)
        history_host.place(x=0, y=42, width=322, height=126)
        history_host.pack_propagate(False)
        self.create_history_panel(history_host)

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
        tk.Label(box, text=label, bg=Theme.PANEL_ALT, fg=Theme.TEXT_DIM,
                 font=(Theme.FONT_CJK, 8), anchor=tk.CENTER).place(x=4, y=5, width=96, height=16)
        tk.Label(box, textvariable=variable, bg=Theme.PANEL_ALT, fg=color,
                 font=(Theme.FONT, 9, "bold"), anchor=tk.CENTER).place(x=4, y=24, width=96, height=20)

    def _create_action_controls(self) -> None:
        # Start mode controls.
        self.start_frame = tk.Frame(self.action_frame, width=322, height=110, bg=Theme.PANEL)
        self.start_frame.place(x=0, y=0, width=322, height=110)
        self.reset_bets_button = ModernButton(
            self.start_frame,
            text="清空全部筹码",
            command=self.reset_bet_button,
            background=Theme.RED,
            hover_background=Theme.RED_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.reset_bets_button.place(x=0, y=0, width=322, height=38)
        self.start_button = ModernButton(
            self.start_frame,
            text="开始游戏",
            command=self.start_game,
            background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
            state=tk.DISABLED,
        )
        self.start_button.place(x=0, y=43, width=322, height=38)

        # Banker decision controls.
        self.decision_frame = tk.Frame(self.action_frame, width=322, height=110, bg=Theme.PANEL)
        self.offer_label = tk.Label(
            self.decision_frame,
            text="",
            bg=Theme.PANEL,
            fg=Theme.AMBER,
            font=(Theme.FONT_CJK, 12, "bold"),
            anchor=tk.W,
        )
        self.offer_label.place(x=0, y=0, width=322, height=28)
        self.continue_btn = ModernButton(
            self.decision_frame,
            text="继续",
            command=self.continue_game,
            background=Theme.ACCENT,
            hover_background=Theme.ACCENT_HOVER,
            foreground="#FFFFFF",
            font_size=10,
            bold=True,
        )
        self.continue_btn.place(x=0, y=35, width=102, height=38)
        self.accept_btn = ModernButton(
            self.decision_frame,
            text="成交",
            command=self.accept_offer,
            background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF",
            font_size=10,
            bold=True,
        )
        self.accept_btn.place(x=110, y=35, width=102, height=38)
        self.offer_btn = ModernButton(
            self.decision_frame,
            text="反报价",
            command=self.counter_offer,
            background=Theme.AMBER,
            hover_background="#85571B",
            foreground="#FFFFFF",
            font_size=10,
            bold=True,
        )
        self.offer_btn.place(x=220, y=35, width=102, height=38)

        # End-of-game control.
        self.newgame_frame = tk.Frame(self.action_frame, width=322, height=110, bg=Theme.PANEL)
        self.newgame_btn = ModernButton(
            self.newgame_frame,
            text="再来一局",
            command=self.reset_for_newgame,
            background=Theme.ACCENT,
            hover_background=Theme.ACCENT_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.newgame_btn.place(x=0, y=17, width=322, height=42)

    # ------------------------------------------------------------------
    # Main-panel controls
    # ------------------------------------------------------------------

    def create_boxes(self, parent) -> None:
        self.box_buttons = []
        # 8 x 4 grid = 32 cases; compact and symmetric inside the 748px panel.
        for idx in range(32):
            row, col = divmod(idx, 8)
            case = CaseButton(parent, idx, command=self.on_box_click)
            x = 3 + col * 61
            y = 8 + row * 106
            case.place(x=x, y=y, width=57, height=94)
            self.box_buttons.append(case)

    def create_remaining_panel(self, parent) -> None:
        self.remaining_labels = []
        for i in range(32):
            row = i % 16
            col = i // 16
            label = tk.Label(
                parent,
                text="—",
                bg=Theme.PRIZE_LIVE,
                fg=Theme.TEXT,
                font=(Theme.FONT, 8, "bold"),
                anchor=tk.CENTER,
                highlightthickness=1,
                highlightbackground=Theme.BORDER_SOFT,
            )
            label.place(x=col * 102, y=row * 30, width=98, height=26)
            self.remaining_labels.append(label)

    def update_remaining_panel(self) -> None:
        # Before a round is started, show the unscaled base ladder as a guide.
        values = sorted(self.box_values) if self.box_values else BASE_VALUES
        self.sorted_amounts = list(values)
        opened_amounts = {self.box_values[i] for i in self.opened_indices} if self.box_values else set()

        for i, amount in enumerate(values):
            label = self.remaining_labels[i]
            label.configure(text=self.format_money(amount))
            if amount in opened_amounts:
                label.configure(bg=Theme.PRIZE_GONE, fg=Theme.TEXT_DIM)
            else:
                high = i >= 24
                label.configure(
                    bg=Theme.PRIZE_LIVE if not high else Theme.ACCENT_SOFT,
                    fg=Theme.TEXT if not high else Theme.ACCENT,
                )

    # ------------------------------------------------------------------
    # Betting and history
    # ------------------------------------------------------------------

    def update_bet_display(self) -> None:
        self.bet_var.set(self.format_money(self.bet_amount))

    def select_chip(self, chip_value):
        # Compatibility with older callers: selecting a chip now directly adds it,
        # mirroring ChickenCrossing's chip interaction.
        self.selected_chip = float(chip_value)

    def get_chip_value(self):
        return self.selected_chip if self.selected_chip else 0.0

    def add_chip_to_bet(self, chip_value: Optional[float] = None) -> None:
        if self.game_active or self.waiting_for_decision:
            return
        amount = float(chip_value if chip_value is not None else self.get_chip_value())
        if amount <= 0:
            return
        self.selected_chip = amount
        new_bet = self.bet_amount + amount
        if new_bet > self.balance:
            messagebox.showerror("余额不足", "下注总额超过余额", parent=self.root)
            return
        if new_bet > 1_000_000:
            messagebox.showerror("下注超限", "下注总额不能超过 1,000,000", parent=self.root)
            return
        self.bet_amount = new_bet
        self.update_bet_display()
        if self.player_box_index < 0:
            self.info_var.set("下注已就绪。请选择一个箱子作为你的箱子。")
            self.need_open_var.set("下一步：从左侧选择你的箱子。")
        else:
            self.info_var.set("下注与箱子已确认，可以开始游戏。")
            self.need_open_var.set("点击“开始游戏”进入第一轮。")
        self.update_ui_state()

    def reset_bet(self) -> None:
        if self.game_active or self.waiting_for_decision:
            return
        self.bet_amount = 0.0
        self.update_bet_display()
        self.info_var.set("选择下注金额，再选一个箱子作为你的箱子。")
        self.need_open_var.set("选择下注金额，然后选择一个箱子。")
        self.update_ui_state()

    def reset_bet_button(self) -> None:
        self.reset_bet()

    def create_history_panel(self, parent) -> None:
        self.history_labels = []
        titles = ["首次", "二次", "三次", "四次", "五次", "六次", "七次", "八次"]
        for i, title in enumerate(titles):
            col = i // 4
            row = i % 4
            item = tk.Frame(
                parent,
                width=156,
                height=28,
                bg=Theme.PANEL_ALT,
                highlightthickness=1,
                highlightbackground=Theme.BORDER_SOFT,
            )
            item.place(x=col * 166, y=row * 31, width=156, height=28)
            tk.Label(item, text=title, bg=Theme.PANEL_ALT, fg=Theme.TEXT_DIM,
                     font=(Theme.FONT_CJK, 8), anchor=tk.W).place(x=7, y=4, width=42, height=19)
            value = tk.Label(item, text="$ ------", bg=Theme.PANEL_ALT, fg=Theme.AMBER,
                             font=(Theme.FONT, 8, "bold"), anchor=tk.E)
            value.place(x=48, y=4, width=101, height=19)
            self.history_labels.append(value)

    def update_history_display(self) -> None:
        for label in self.history_labels:
            label.configure(text="$ ------")
        for i, offer_text in enumerate(self.offer_history[: len(self.history_labels)]):
            self.history_labels[i].configure(text=offer_text)

    def add_offer_to_history(self, offer_amount) -> None:
        self.offer_history.append(self.format_money(offer_amount))
        self.update_history_display()

    def clear_history(self) -> None:
        self.offer_history.clear()
        self.update_history_display()

    # ------------------------------------------------------------------
    # Action mode switching
    # ------------------------------------------------------------------

    def show_start_buttons(self) -> None:
        self.decision_frame.place_forget()
        self.newgame_frame.place_forget()
        self.start_frame.place(x=0, y=0, width=322, height=110)
        self.update_ui_state()

    def show_decision_buttons(self) -> None:
        self.start_frame.place_forget()
        self.newgame_frame.place_forget()
        self.decision_frame.place(x=0, y=0, width=322, height=110)
        self.accept_btn.configure(state=tk.DISABLED)

    def show_newgame_button(self) -> None:
        self.start_frame.place_forget()
        self.decision_frame.place_forget()
        self.newgame_frame.place(x=0, y=0, width=322, height=110)

    def update_ui_state(self) -> None:
        if not hasattr(self, "start_button"):
            return
        can_start = (
            not self.game_active
            and not self.waiting_for_decision
            and self.bet_amount > 0
            and self.player_box_index >= 0
        )
        self.start_button.configure(state=tk.NORMAL if can_start else tk.DISABLED)
        self.reset_bets_button.configure(
            state=tk.NORMAL if not self.game_active and not self.waiting_for_decision else tk.DISABLED
        )

    # ------------------------------------------------------------------
    # Case interaction and game flow
    # ------------------------------------------------------------------

    def on_box_click(self, idx) -> None:
        if self.game_active and not self.waiting_for_decision:
            self.open_box(idx)
        elif not self.game_active and not self.waiting_for_decision:
            self.select_box(idx)

    def select_box(self, idx) -> None:
        for case in self.box_buttons:
            case.set_selected(False)
        self.box_buttons[idx].set_selected(True)
        self.player_box_index = idx
        self.player_case_var.set(f"你的箱子：CASE {idx + 1:02d}")
        if self.bet_amount > 0:
            self.info_var.set("下注与箱子已确认，可以开始游戏。")
            self.need_open_var.set("点击“开始游戏”进入第一轮。")
        else:
            self.info_var.set("箱子已保留。请在右侧加入下注筹码。")
            self.need_open_var.set("下一步：点击右侧筹码加入下注。")
        self.update_ui_state()

    def open_box(self, idx) -> None:
        if idx == self.player_box_index or idx in self.opened_indices:
            return
        if self.to_open_this_round <= 0:
            messagebox.showinfo("提示", "本轮开箱数量已满，请等待银行家报价。", parent=self.root)
            return

        self.opened_indices.add(idx)
        self.to_open_this_round -= 1
        value = self.box_values[idx]
        self.box_buttons[idx].set_open(self.format_money(value))
        self.update_remaining_panel()
        self.remaining_stat_var.set(str(self.to_open_this_round))
        self.need_open_var.set(f"本轮还需打开 {self.to_open_this_round} 个箱子。")
        self.info_var.set(f"CASE {idx + 1:02d}：{self.format_money(value)} 已离场。")

        if self.to_open_this_round == 0:
            self.enter_offer_phase()

    def start_game(self) -> None:
        if self.bet_amount <= 0:
            messagebox.showinfo("提示", "请先下注。", parent=self.root)
            return
        if self.bet_amount > self.balance:
            messagebox.showinfo("错误", "下注超过余额。", parent=self.root)
            return
        if self.player_box_index == -1:
            messagebox.showinfo("提示", "请先点击一个箱子作为你的箱子。", parent=self.root)
            return

        self.balance -= self.bet_amount
        update_balance_in_json(self.username, self.balance)
        self.update_balance_display()
        self.clear_history()

        self.n = self.bet_amount / 1000
        self.box_values = [round(value * self.n, 2) for value in BASE_VALUES]
        random.shuffle(self.box_values)
        self.player_box_value = self.box_values[self.player_box_index]

        self.opened_indices = set()
        self.current_round = 0
        self.to_open_this_round = self.rounds[0]
        self.game_active = True
        self.waiting_for_decision = False
        self.lost_quote_right = False
        self.current_offer = 0.0

        self.round_stat_var.set("1 / 9")
        self.remaining_stat_var.set(str(self.to_open_this_round))
        self.offer_stat_var.set("—")
        self.phase_badge_var.set("开箱阶段")
        self.round_info_var.set(f"第 1 轮 · 打开 {self.rounds[0]} 个箱子")
        self.need_open_var.set(f"本轮还需打开 {self.to_open_this_round} 个箱子。")
        self.info_var.set("第一轮开始：避开你的箱子，打开场上的箱子。")
        self.show_decision_buttons()
        self.decision_frame.place_forget()  # Decisions appear only after enough cases are opened.

        for button in self.chip_buttons:
            button.configure(state=tk.DISABLED)
        self.reset_bets_button.configure(state=tk.DISABLED)

        for i, case in enumerate(self.box_buttons):
            case.set_closed()
            if i == self.player_box_index:
                case.set_selected(True)
                case.disable()
            else:
                case.enable()

        self.update_remaining_panel()

    def enter_offer_phase(self) -> None:
        self.game_active = False
        self.waiting_for_decision = True

        remaining_indices = [i for i in range(len(self.box_values)) if i not in self.opened_indices]
        remaining_values = [self.box_values[i] for i in remaining_indices]
        offer = self.calculate_banker_offer(self.current_round, remaining_values)
        self.current_offer = offer
        self.add_offer_to_history(offer)

        self.offer_stat_var.set(self.format_money(offer))
        self.offer_label.configure(text=f"银行家报价  {self.format_money(offer)}")
        self.phase_badge_var.set("银行报价")
        self.info_var.set("银行家已给出报价：成交，还是继续开箱？")
        self.need_open_var.set("选择继续、成交，或尝试一次反报价。")
        self.show_decision_buttons()
        self.accept_btn.configure(state=tk.NORMAL)
        self.offer_btn.configure(state=tk.DISABLED if self.lost_quote_right else tk.NORMAL)

    def calculate_banker_offer(self, round_idx, remaining_values):
        if not remaining_values:
            return 0.0
        ev = sum(remaining_values) / len(remaining_values)
        if ev <= 0:
            return 0.0

        progress = round_idx / max(1, len(self.rounds) - 1)
        remaining_ratio = len(remaining_values) / len(self.box_values)
        std = statistics.pstdev(remaining_values) if len(remaining_values) > 1 else 0.0
        std_ratio = std / ev if ev > 0 else 0.0
        top_value = max(remaining_values)
        top_ratio = top_value / max(BASE_VALUES)
        high_count = sum(1 for value in remaining_values if value >= ev * 2)
        low_count = sum(1 for value in remaining_values if value <= ev * 0.20)

        factor = 0.16 + 0.74 * (progress ** 1.35)
        factor *= 0.95 + 0.08 * (1.0 - remaining_ratio)
        factor *= 1.0 - min(0.16, 0.06 * std_ratio)
        factor += min(0.05, 0.01 * high_count)
        factor -= min(0.03, 0.004 * low_count)
        if top_ratio <= 0.20:
            factor += 0.03
        elif top_ratio <= 0.40:
            factor += 0.015

        jitter = random.uniform(0.985, 1.015)
        offer = ev * factor * jitter
        offer = min(offer, ev * 0.97)
        return round(max(0.0, offer), 2)

    def _advance_to_next_round(self):
        self.waiting_for_decision = False
        self.decision_frame.place_forget()
        self.current_round += 1

        if self.current_round >= len(self.rounds):
            self.final_two_boxes_choice()
            return False

        self.to_open_this_round = self.rounds[self.current_round]
        self.game_active = True
        self.round_stat_var.set(f"{self.current_round + 1} / {len(self.rounds)}")
        self.remaining_stat_var.set(str(self.to_open_this_round))
        self.offer_stat_var.set("—")
        self.phase_badge_var.set("开箱阶段")
        self.round_info_var.set(
            f"第 {self.current_round + 1} 轮 · 打开 {self.rounds[self.current_round]} 个箱子"
        )
        self.need_open_var.set(f"本轮还需打开 {self.to_open_this_round} 个箱子。")
        self.info_var.set("继续开箱。你的箱子仍然安全保留。")

        for i, case in enumerate(self.box_buttons):
            if i == self.player_box_index:
                case.disable()
            elif i not in self.opened_indices:
                case.enable()
            else:
                case.disable()

        self.accept_btn.configure(state=tk.DISABLED)
        self.offer_btn.configure(state=tk.DISABLED if self.lost_quote_right else tk.NORMAL)
        return True

    def continue_game(self) -> None:
        if self.waiting_for_decision:
            self._advance_to_next_round()

    def accept_offer(self) -> None:
        if not self.waiting_for_decision:
            return
        win_amount = self.current_offer
        self.balance += win_amount
        self.last_win = win_amount
        update_balance_in_json(self.username, self.balance)
        self.update_balance_display()
        self.last_win_var.set(self.format_money(self.last_win))
        self.reveal_all_boxes()
        messagebox.showinfo(
            "游戏结束",
            f"你接受了银行家报价 {self.format_money(win_amount)}，赢得奖金！",
            parent=self.root,
        )
        self.end_game()

    def counter_offer(self) -> None:
        if not self.waiting_for_decision or self.lost_quote_right:
            return
        player_offer = simpledialog.askfloat(
            "反报价",
            "请输入你的报价金额：",
            minvalue=0,
            maxvalue=1e9,
            parent=self.root,
        )
        if player_offer is None:
            return

        remaining_indices = [i for i in range(len(self.box_values)) if i not in self.opened_indices]
        remaining_values = [self.box_values[i] for i in remaining_indices]
        ev = sum(remaining_values) / len(remaining_values) if remaining_values else 0.0
        progress = self.current_round / max(1, len(self.rounds) - 1)
        accept_limit = max(
            self.current_offer * (1.10 + 0.08 * progress),
            ev * (0.22 + 0.42 * progress),
        )

        if player_offer <= accept_limit:
            self.balance += player_offer
            self.last_win = player_offer
            update_balance_in_json(self.username, self.balance)
            self.update_balance_display()
            self.last_win_var.set(self.format_money(self.last_win))
            self.reveal_all_boxes()
            messagebox.showinfo(
                "报价成功",
                f"银行家接受了你的报价 {self.format_money(player_offer)}，游戏结束！",
                parent=self.root,
            )
            self.end_game()
        else:
            self.lost_quote_right = True
            messagebox.showwarning(
                "报价被拒",
                "银行家拒绝了你的报价。你将失去本局反报价权，并自动进入下一轮。",
                parent=self.root,
            )
            self._advance_to_next_round()

    # ------------------------------------------------------------------
    # Final two-case choice — restyled to the same HMI family
    # ------------------------------------------------------------------

    def final_two_boxes_choice(self) -> None:
        all_indices = set(range(len(self.box_values)))
        unopened = list(all_indices - self.opened_indices)
        if self.player_box_index not in unopened:
            unopened.append(self.player_box_index)
        unopened = list(dict.fromkeys(unopened))
        if len(unopened) < 2:
            # Defensive fallback; should not occur with the normal round schedule.
            remaining = [i for i in range(len(self.box_values)) if i != self.player_box_index]
            unopened.extend(remaining[: 2 - len(unopened)])

        player_idx = self.player_box_index
        other_idx = next(i for i in unopened if i != player_idx)
        player_value = self.box_values[player_idx]
        other_value = self.box_values[other_idx]

        top = self.root.winfo_toplevel()
        choice_win = tk.Toplevel(top)
        choice_win.title("最终抉择")
        choice_win.geometry("650x390")
        choice_win.resizable(False, False)
        choice_win.configure(bg=Theme.APP_BG)
        choice_win.transient(top)
        choice_win.grab_set()

        top.update_idletasks()
        x = top.winfo_rootx() + max(0, (top.winfo_width() - 650) // 2)
        y = top.winfo_rooty() + max(0, (top.winfo_height() - 390) // 2)
        choice_win.geometry(f"650x390+{x}+{y}")

        tk.Label(choice_win, text="FINAL CHOICE", bg=Theme.APP_BG, fg=Theme.TEXT,
                 font=(Theme.FONT, 18, "bold"), anchor=tk.CENTER).place(x=20, y=18, width=610, height=30)
        tk.Label(choice_win, text="最终二选一：保留你的箱子，或交换场上最后一个箱子。",
                 bg=Theme.APP_BG, fg=Theme.TEXT_MUTED,
                 font=(Theme.FONT_CJK, 10), anchor=tk.CENTER).place(x=20, y=50, width=610, height=24)

        cards = []
        chosen = [None]
        selected_amount = [0.0]
        choice_label = tk.StringVar(value="请选择一个箱子")

        def make_choice_card(x_pos: int, title: str, case_idx: int):
            frame = tk.Frame(choice_win, bg=Theme.PANEL, highlightthickness=1,
                             highlightbackground=Theme.BORDER_SOFT)
            frame.place(x=x_pos, y=92, width=280, height=180)
            tk.Label(frame, text=title, bg=Theme.PANEL, fg=Theme.TEXT,
                     font=(Theme.FONT_CJK, 13, "bold")).place(x=12, y=12, width=256, height=25)
            tk.Label(frame, text=f"CASE {case_idx + 1:02d}", bg=Theme.PANEL,
                     fg=Theme.TEXT_MUTED, font=(Theme.FONT, 10, "bold")).place(x=12, y=41, width=256, height=22)
            canvas = tk.Canvas(frame, width=112, height=84, bg=Theme.PANEL,
                               bd=0, highlightthickness=0, cursor="hand2")
            canvas.place(x=84, y=72, width=112, height=84)
            self._draw_final_case(canvas, None, selected=False)
            cards.append((frame, canvas, case_idx))
            return canvas

        left_canvas = make_choice_card(35, "保留你的箱子", player_idx)
        right_canvas = make_choice_card(335, "交换最后箱子", other_idx)

        tk.Label(choice_win, textvariable=choice_label, bg=Theme.APP_BG, fg=Theme.ACCENT,
                 font=(Theme.FONT_CJK, 10, "bold")).place(x=35, y=282, width=580, height=24)

        confirm_btn = ModernButton(
            choice_win,
            text="确认最终选择",
            command=lambda: on_confirm(),
            background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
            state=tk.DISABLED,
        )
        confirm_btn.place(x=164, y=320, width=322, height=42)

        auto_click_id = [None]

        def enable_confirm():
            confirm_btn.configure(state=tk.NORMAL)
            auto_click_id[0] = choice_win.after(30000, lambda: confirm_btn.invoke())

        def disable_auto_click():
            if auto_click_id[0]:
                try:
                    choice_win.after_cancel(auto_click_id[0])
                except tk.TclError:
                    pass
                auto_click_id[0] = None

        def choose_box(kind: str):
            if chosen[0] is not None:
                return
            chosen[0] = kind
            if kind == "player":
                selected_amount[0] = player_value
                self._draw_final_case(left_canvas, player_value, selected=True)
                self._draw_final_case(right_canvas, other_value, selected=False)
                choice_label.set(f"已选择保留 CASE {player_idx + 1:02d}，3 秒后可确认")
            else:
                selected_amount[0] = other_value
                self._draw_final_case(left_canvas, player_value, selected=False)
                self._draw_final_case(right_canvas, other_value, selected=True)
                choice_label.set(f"已选择交换到 CASE {other_idx + 1:02d}，3 秒后可确认")
            left_canvas.configure(cursor="")
            right_canvas.configure(cursor="")
            left_canvas.unbind("<Button-1>")
            right_canvas.unbind("<Button-1>")
            choice_win.after(3000, enable_confirm)

        def on_confirm():
            if chosen[0] is None:
                return
            disable_auto_click()
            win_amount = selected_amount[0]
            if chosen[0] == "player":
                chosen_idx, unchosen_idx = player_idx, other_idx
            else:
                chosen_idx, unchosen_idx = other_idx, player_idx

            choice_win.destroy()
            self.balance += win_amount
            self.last_win = win_amount
            update_balance_in_json(self.username, self.balance)
            self.update_balance_display()
            self.last_win_var.set(self.format_money(self.last_win))
            self.box_buttons[chosen_idx].set_open(
                self.format_money(self.box_values[chosen_idx]), custom_color="white"
            )
            self.box_buttons[unchosen_idx].set_open(
                self.format_money(self.box_values[unchosen_idx]), custom_color=Theme.ACCENT_SOFT
            )
            self.end_game()

        left_canvas.bind("<Button-1>", lambda _event: choose_box("player"))
        right_canvas.bind("<Button-1>", lambda _event: choose_box("other"))

        def on_close():
            if chosen[0] is None:
                messagebox.showwarning("尚未选择", "请选择一个箱子以继续游戏。", parent=choice_win)
            else:
                disable_auto_click()
                choice_win.destroy()

        choice_win.protocol("WM_DELETE_WINDOW", on_close)
        top.wait_window(choice_win)

    @staticmethod
    def _draw_final_case(canvas: tk.Canvas, amount: Optional[float], *, selected: bool) -> None:
        canvas.delete("all")
        border = Theme.ACCENT if selected else Theme.BORDER_SOFT
        fill = Theme.SELECTED if selected else Theme.PANEL_ALT
        canvas.create_rectangle(2, 2, 109, 81, fill=fill, outline=border, width=2)
        if amount is None:
            canvas.create_arc(41, 10, 71, 38, start=0, extent=180, style=tk.ARC,
                              outline=Theme.CASE_DARK, width=4)
            canvas.create_rectangle(24, 27, 88, 67, fill=Theme.CASE,
                                    outline=Theme.CASE_DARK, width=2)
            canvas.create_text(56, 48, text="?", fill="#FFF8EB",
                               font=(Theme.FONT, 18, "bold"))
        else:
            canvas.create_rectangle(21, 23, 91, 68, fill=Theme.PANEL,
                                    outline=Theme.BORDER, width=2)
            text = f"${amount:,.2f}" if not float(amount).is_integer() else f"${int(amount):,}"
            canvas.create_text(56, 46, text=text, fill=Theme.TEXT,
                               font=(Theme.FONT, 10, "bold"), width=64)

    # ------------------------------------------------------------------
    # End/reset/display helpers
    # ------------------------------------------------------------------

    def format_money(self, value) -> str:
        value = float(value)
        if value.is_integer():
            return f"${int(value):,}"
        return f"${value:,.2f}"

    def reveal_all_boxes(self) -> None:
        if not self.box_values:
            return
        for i, case in enumerate(self.box_buttons):
            value = self.box_values[i]
            if i == self.player_box_index:
                case.set_open(self.format_money(value), custom_color="white")
            else:
                case.set_open(self.format_money(value))

    def end_game(self) -> None:
        self.game_active = False
        self.waiting_for_decision = False
        self.phase_badge_var.set("本局结束")
        self.round_stat_var.set("完成")
        self.remaining_stat_var.set("—")
        self.offer_stat_var.set("—")
        self.info_var.set(f"本局结束。赢得 {self.format_money(self.last_win)}。")
        self.need_open_var.set("点击“再来一局”重新开始。")
        self.show_newgame_button()
        for button in self.chip_buttons:
            button.configure(state=tk.NORMAL)
        update_balance_in_json(self.username, self.balance)

    def reset_for_newgame(self) -> None:
        self.bet_amount = 0.0
        self.player_box_index = -1
        self.player_box_value = 0.0
        self.box_values = []
        self.opened_indices.clear()
        self.current_round = 0
        self.to_open_this_round = 0
        self.game_active = False
        self.waiting_for_decision = False
        self.lost_quote_right = False
        self.current_offer = 0.0

        self.update_bet_display()
        self.round_stat_var.set("待开始")
        self.remaining_stat_var.set("—")
        self.offer_stat_var.set("—")
        self.round_info_var.set("未开始游戏")
        self.need_open_var.set("选择下注金额，然后选择一个箱子。")
        self.info_var.set("选择下注金额，再选一个箱子作为你的箱子。")
        self.phase_badge_var.set("选择阶段")
        self.player_case_var.set("你的箱子：未选择")
        self.clear_history()

        for button in self.chip_buttons:
            button.configure(state=tk.NORMAL)
        for case in self.box_buttons:
            case.set_closed()
            case.enable()
        self.update_remaining_panel()
        self.show_start_buttons()
        self.update_balance_display()

    def update_balance_display(self) -> None:
        self.balance_var.set(f"${self.balance:.2f}")

    def on_closing(self) -> None:
        update_balance_in_json(self.username, self.balance)
        finish = getattr(self.root, "finish", None)
        if callable(finish):
            finish(self.balance)
        else:
            self.root.destroy()


# ---------------------------------------------------------------------------
# Public entry point — same interface as ChickenCrossing_tk.py
# ---------------------------------------------------------------------------


def main(
    initial_balance=10000.0,
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
            title="成交与否",
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        game = DealOrNoDealGame(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = DealOrNoDealGame(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    final_balance = main(10000.0, "test_user")
    print(f"Final balance: {final_balance}")