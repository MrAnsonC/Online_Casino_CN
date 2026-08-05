"""Plinko — ChickenCrossing-style warm fixed HMI.

Gameplay retained from the original plinko.py:
- 8 peg rows / 9 payout slots.
- Easy / medium / hard payout tables are unchanged.
- Every launched ball costs the current stake once.
- Multiple balls may be launched while balls are already falling.
- Each ball's final slot is fixed before animation by 8 independent 50/50
  left/right decisions; the visible motion is then naturally guided there.
- Balance is credited when each ball reaches its final slot.

Additional persistence:
- Final landing slots are stored in ../A_Logs/Plinko.json.
- Data is separated into easy / medium / hard.
- Each mode keeps only its latest 20 raw landing slots in the requested
  [{"game_01": ..., ..., "game_20": ...}] structure.
- The on-screen history shows the latest 8 results converted to the
  corresponding payout multiplier for the active risk mode.

The UI follows ChickenCrossing_tk.py's fixed 1150x750 warm HMI and supports
the project's EmbeddedGamePage single-Tk mode.
"""

from __future__ import annotations

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


VERSION = "Plinko-ChickenStyle-R5-EventDrivenRigidBody"


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

    BOARD = "#AFC4B1"
    BOARD_DARK = "#839E86"
    BOARD_EDGE = "#718C75"
    PEG = "#EEE8DE"
    PEG_BORDER = "#8C857B"
    SLOT = "#D5CEC3"
    SLOT_EDGE = "#9C9388"
    SLOT_GOOD = "#A9C4A5"
    SLOT_NEUTRAL = "#D8C994"
    SLOT_BAD = "#D1A09B"
    BALL_OUTLINE = "#F7F3EC"

    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )
    FONT_EMOJI = "Segoe UI Emoji"


CHIP_CONFIGS = (
    ("$1", "1", "#D75A54", "white"),
    ("$5", "5", "#67B56A", "black"),
    ("$10", "10", "#292929", "white"),
    ("$25", "25", "#D47AB7", "black"),
    ("$100", "100", "#F4F1EA", "black"),
)

RISK_CONFIGS = (
    ("简单", "1", "easy"),
    ("中等", "2", "medium"),
    ("困难", "3", "hard"),
)

PAYOUTS = {
    "1": [5.6, 2.1, 1.1, 1.0, 0.5, 1.0, 1.1, 2.1, 5.6],
    "2": [13.0, 3.0, 1.3, 0.7, 0.4, 0.7, 1.3, 3.0, 13.0],
    "3": [29.0, 4.0, 1.5, 0.3, 0.2, 0.3, 1.5, 4.0, 29.0],
}

RISK_KEY = {"1": "easy", "2": "medium", "3": "hard"}
RISK_LABEL = {"1": "简单", "2": "中等", "3": "困难"}


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def get_data_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../saving_data.json")


def get_plinko_log_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "../A_Logs/Plinko.json",
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


def _empty_landing_log() -> dict:
    return {
        "easy": [{}],
        "medium": [{}],
        "hard": [{}],
    }


def _extract_mode_values(data: dict, mode: str) -> list[int]:
    """Return stored landing values in chronological order."""
    try:
        block = data.get(mode, [])
        if not isinstance(block, list) or not block or not isinstance(block[0], dict):
            return []
        record = block[0]
        pairs = []
        for key, value in record.items():
            if not isinstance(key, str) or not key.startswith("game_"):
                continue
            try:
                index = int(key.split("_", 1)[1])
                landing = int(value)
            except (ValueError, TypeError):
                continue
            if 1 <= landing <= 9:
                pairs.append((index, landing))
        pairs.sort(key=lambda pair: pair[0])
        return [landing for _, landing in pairs][-20:]
    except Exception:
        return []


def load_landing_log() -> dict:
    base = _empty_landing_log()
    try:
        with open(get_plinko_log_path(), "r", encoding="utf-8") as file:
            raw = json.load(file)
        if not isinstance(raw, dict):
            return base
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return base

    for mode in ("easy", "medium", "hard"):
        values = _extract_mode_values(raw, mode)
        base[mode] = [{
            f"game_{index:02d}": value
            for index, value in enumerate(values, start=1)
        }]
    return base


def record_landing(mode: str, slot: int) -> None:
    """Append one landing slot and keep the newest 20 for the selected mode."""
    if mode not in ("easy", "medium", "hard"):
        return
    slot = int(slot)
    if not 1 <= slot <= 9:
        return

    data = load_landing_log()
    values = _extract_mode_values(data, mode)
    values.append(slot)
    values = values[-20:]

    data[mode] = [{
        f"game_{index:02d}": value
        for index, value in enumerate(values, start=1)
    }]

    # Normalize the untouched modes too, so the file always has all 3 groups.
    for other in ("easy", "medium", "hard"):
        if other == mode:
            continue
        other_values = _extract_mode_values(data, other)
        data[other] = [{
            f"game_{index:02d}": value
            for index, value in enumerate(other_values, start=1)
        }]

    path = get_plinko_log_path()
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Reusable Chicken-style controls
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

        self.create_oval(6, 7, self.control_width - 5, self.control_height - 1,
                         fill="#8E877E", outline="")
        self.create_oval(5, 3 + offset_y, self.control_width - 6,
                         self.control_height - 5 + offset_y,
                         fill=outer, outline=outline, width=outline_width)
        self.create_oval(9, 7 + offset_y, self.control_width - 10,
                         self.control_height - 9 + offset_y,
                         fill=self.chip_color, outline=inner, width=2)
        self.create_oval(14, 12 + offset_y, self.control_width - 15,
                         self.control_height - 14 + offset_y,
                         fill=self.chip_color, outline=outer, width=1)

        cx = self.control_width / 2
        cy = (self.control_height - 2) / 2 + offset_y
        inserts = (
            (cx - 3, 4 + offset_y, cx + 3, 10 + offset_y),
            (cx - 3, self.control_height - 12 + offset_y, cx + 3,
             self.control_height - 6 + offset_y),
            (6, cy - 3, 12, cy + 3),
            (self.control_width - 13, cy - 3, self.control_width - 7, cy + 3),
        )
        for x1, y1, x2, y2 in inserts:
            self.create_rectangle(x1, y1, x2, y2, fill=self.text_color, outline="")

        self.create_text(
            cx, cy, text=self.label, fill=self.text_color,
            font=(Theme.FONT, 10 if len(self.label) <= 4 else 9, "bold")
        )
        if disabled:
            self.create_oval(
                5, 3 + offset_y, self.control_width - 6,
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


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class PlinkoGame:
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

    BOARD_WIDTH = 716
    BOARD_HEIGHT = 478

    def __init__(self, root, initial_balance: float, username: str):
        self.root = root
        self._configure_root()

        self.balance = float(initial_balance)
        self.username = username
        self.risk_level = "1"
        self.current_bet = 0.0
        self.last_win = 0.0
        self.balls: list[dict] = []
        self.pegs: list[tuple[float, float]] = []
        self.peg_rows: list[list[tuple[float, float]]] = []
        self.animation_running = False
        self.active_balls = 0
        self.last_result_text = "等待发射"

        # Continuous event-driven rigid-body tuning (pixel / second units).
        # Between impacts the ball follows x = x0 + vx*t and
        # y = y0 + vy*t + 1/2*g*t^2 exactly.  Result control is applied only as
        # an instantaneous collision impulse while the ball touches a peg.
        self.gravity = 980.0
        self.ball_radius = 8.0
        self.peg_radius = 5.0
        self.frame_interval_ms = 16
        self.max_frame_dt = 0.040
        self._last_frame_time = time.monotonic()

        self.chip_buttons: list[ChipButton] = []
        self.risk_buttons: list[ModernButton] = []

        self.balance_var = tk.StringVar()
        self.bet_var = tk.StringVar()
        self.last_win_var = tk.StringVar()
        self.active_var = tk.StringVar()
        self.mode_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.history_var = tk.StringVar()

        self.create_widgets()
        self.update_display()

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("Plinko")
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
            master,
            text=text,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 11, "bold"),
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
        icon.create_oval(16, 10, 32, 26, fill=Theme.AMBER, outline=Theme.TEXT, width=1)
        icon.create_line(24, 27, 24, 39, fill=Theme.ACCENT, width=2)
        icon.create_line(17, 38, 31, 38, fill=Theme.ACCENT, width=2)

        tk.Label(
            header,
            text="PLINKO",
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT, 18, "bold"),
            anchor=tk.W,
        ).place(x=74, y=10, width=300, height=27)
        tk.Label(
            header,
            text="弹珠落点",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 11, "bold"),
            anchor=tk.W,
        ).place(x=74, y=39, width=240, height=20)

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

        tk.Label(
            panel, text="落球板",
            bg=Theme.PANEL, fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 12, "bold"), anchor=tk.W,
        ).place(x=16, y=10, width=100, height=24)

        self.mode_badge = tk.Label(
            panel, textvariable=self.mode_var,
            bg=Theme.ACCENT_SOFT, fg=Theme.ACCENT,
            font=(Theme.FONT_CJK, 10, "bold"), anchor=tk.CENTER,
        )
        self.mode_badge.place(x=590, y=10, width=140, height=24)

        self.board_canvas = tk.Canvas(
            panel,
            width=self.BOARD_WIDTH,
            height=self.BOARD_HEIGHT,
            bg=Theme.CANVAS_BG,
            bd=0,
            highlightthickness=0,
        )
        self.board_canvas.place(x=16, y=43, width=self.BOARD_WIDTH, height=self.BOARD_HEIGHT)

        history_box = tk.Frame(
            panel,
            bg=Theme.PANEL_ALT,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        history_box.place(x=16, y=533, width=716, height=80)
        tk.Label(
            history_box,
            text="当前模式最新 8 局落点倍率",
            bg=Theme.PANEL_ALT,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.W,
        ).place(x=10, y=5, width=180, height=18)

        self.history_canvas = tk.Canvas(
            history_box, width=694, height=47,
            bg=Theme.PANEL_ALT, bd=0, highlightthickness=0,
        )
        self.history_canvas.place(x=10, y=27, width=694, height=47)

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
            sidebar, "当前下注", self.bet_var, Theme.CYAN,
            width=169, height=68,
        ).place(x=0, y=0, width=169, height=68)
        MetricTile(
            sidebar, "上局返还", self.last_win_var, Theme.GREEN,
            width=169, height=68,
        ).place(x=179, y=0, width=169, height=68)

        chips = self._card(sidebar, width=348, height=101)
        chips.place(x=0, y=78, width=348, height=101)
        self._section_title(chips.inner, "下注筹码").place(x=0, y=0, width=120, height=20)
        for index, (label, amount, chip_color, text_color) in enumerate(CHIP_CONFIGS):
            chip = ChipButton(
                chips.inner,
                label=label,
                amount=amount,
                chip_color=chip_color,
                text_color=text_color,
                command=self.add_chip,
                width=57,
                height=50,
            )
            chip.place(x=index * 62, y=24, width=57, height=50)
            self.chip_buttons.append(chip)

        risk = self._card(sidebar, width=348, height=82)
        risk.place(x=0, y=189, width=348, height=82)
        self._section_title(risk.inner, "风险模式").place(x=0, y=0, width=120, height=20)
        for index, (label, value, _mode) in enumerate(RISK_CONFIGS):
            btn = ModernButton(
                risk.inner,
                text=label,
                command=lambda v=value: self.set_risk(v),
                background=Theme.PANEL_ALT,
                hover_background=Theme.PANEL_HOVER,
                foreground=Theme.TEXT,
                font_size=11,
                bold=True,
            )
            btn.place(x=index * 107, y=28, width=100, height=32)
            self.risk_buttons.append(btn)

        payout = self._card(sidebar, width=348, height=103)
        payout.place(x=0, y=281, width=348, height=103)
        self._section_title(payout.inner, "当前 9 槽赔率").place(x=0, y=0, width=150, height=20)
        self.payout_canvas = tk.Canvas(
            payout.inner, width=322, height=55,
            bg=Theme.PANEL, bd=0, highlightthickness=0,
        )
        self.payout_canvas.place(x=0, y=26, width=322, height=55)

        actions = self._card(sidebar, width=348, height=92)
        actions.place(x=0, y=394, width=348, height=92)
        self.reset_bet_button = ModernButton(
            actions.inner,
            text="清空全部筹码",
            command=self.reset_bet,
            background=Theme.RED,
            hover_background=Theme.RED_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.reset_bet_button.place(x=0, y=0, width=322, height=34)

        self.launch_button = ModernButton(
            actions.inner,
            text="发射弹珠",
            command=self.launch_ball,
            background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.launch_button.place(x=0, y=42, width=322, height=34)

        state = self._card(sidebar, width=348, height=60, padding=9)
        state.place(x=0, y=496, width=348, height=60)
        tk.Label(
            state.inner,
            text="活动弹珠",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9),
            anchor=tk.W,
        ).place(x=0, y=0, width=86, height=18)
        tk.Label(
            state.inner,
            textvariable=self.active_var,
            bg=Theme.PANEL,
            fg=Theme.ACCENT,
            font=(Theme.FONT, 11, "bold"),
            anchor=tk.W,
        ).place(x=0, y=20, width=86, height=20)

        tk.Label(
            state.inner,
            text="最近结果",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9),
            anchor=tk.E,
        ).place(x=92, y=0, width=230, height=18)
        tk.Label(
            state.inner,
            textvariable=self.status_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 10, "bold"),
            anchor=tk.E,
        ).place(x=92, y=20, width=230, height=20)

        rules = self._card(sidebar, width=348, height=64, padding=9)
        rules.place(x=0, y=566, width=348, height=64)
        tk.Label(
            rules.inner,
            text="规则：每次点击发射一颗；可连续多球。每颗球会沿 8 层随机路径下落，最终按 1–9 槽赔率返还。",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8),
            justify=tk.LEFT,
            anchor=tk.W,
            wraplength=322,
        ).place(x=0, y=0, width=322, height=44)

    # ------------------------------------------------------------------
    # UI state
    # ------------------------------------------------------------------

    def add_chip(self, amount: str) -> None:
        if self.active_balls > 0:
            return
        try:
            value = float(amount)
        except (TypeError, ValueError):
            return
        new_bet = self.current_bet + value
        if new_bet <= self.balance:
            self.current_bet = new_bet
            self.update_display()
        else:
            messagebox.showwarning("余额不足", "账户余额不足以加入这个筹码。", parent=self.root)

    def reset_bet(self) -> None:
        if self.active_balls > 0:
            return
        self.current_bet = 0.0
        self.update_display()

    def set_risk(self, risk: str) -> None:
        if self.active_balls > 0 or risk not in PAYOUTS:
            return
        self.risk_level = risk
        self.update_display()

    def update_display(self) -> None:
        self.balance_var.set(f"${self.balance:,.2f}")
        self.bet_var.set(f"${self.current_bet:,.2f}")
        self.last_win_var.set(f"${self.last_win:,.2f}")
        self.active_var.set(str(self.active_balls))
        self.mode_var.set(f"{RISK_LABEL[self.risk_level]}模式")
        self.status_var.set(self.last_result_text)

        locked = self.active_balls > 0
        state = tk.DISABLED if locked else tk.NORMAL
        for chip in self.chip_buttons:
            chip.configure(state=state)
        self.reset_bet_button.configure(state=state)

        for index, button in enumerate(self.risk_buttons):
            button.configure(state=state)
            selected = RISK_CONFIGS[index][1] == self.risk_level
            button.set_colors(
                Theme.ACCENT if selected else Theme.PANEL_ALT,
                Theme.ACCENT_HOVER if selected else Theme.PANEL_HOVER,
                "#FFFFFF" if selected else Theme.TEXT,
            )

        launch_enabled = self.current_bet > 0 and self.current_bet <= self.balance
        self.launch_button.configure(state=tk.NORMAL if launch_enabled else tk.DISABLED)

        self.draw_board()
        self.draw_payout_strip()
        self.draw_landing_history()

    def draw_payout_strip(self) -> None:
        c = self.payout_canvas
        c.delete("all")
        w = 322
        cell_w = w / 9
        values = PAYOUTS[self.risk_level]
        for i, payout in enumerate(values):
            x1 = round(i * cell_w)
            x2 = round((i + 1) * cell_w)
            if payout > 1:
                fill = Theme.SLOT_GOOD
                fg = Theme.GREEN
            elif payout < 1:
                fill = Theme.SLOT_BAD
                fg = Theme.RED
            else:
                fill = Theme.SLOT_NEUTRAL
                fg = Theme.AMBER
            c.create_rectangle(x1, 1, x2, 54, fill=fill, outline=Theme.BORDER, width=1)
            text = f"{int(payout)}×" if float(payout).is_integer() else f"{payout:.1f}×"
            c.create_text(
                (x1 + x2) / 2, 18, text=str(i + 1),
                fill=Theme.TEXT_MUTED, font=(Theme.FONT, 8, "bold")
            )
            c.create_text(
                (x1 + x2) / 2, 38, text=text,
                fill=fg, font=(Theme.FONT, 8, "bold")
            )

    def draw_landing_history(self) -> None:
        """Show the latest 8 landings as payout multipliers.

        Plinko.json continues to store the raw final slot number (1-9).
        The display converts each slot to the payout multiplier belonging
        to the currently selected risk mode.
        """
        c = self.history_canvas
        c.delete("all")

        mode = RISK_KEY[self.risk_level]
        slot_values = _extract_mode_values(load_landing_log(), mode)[-8:]
        payout_values = PAYOUTS[self.risk_level]

        width = 694
        gap = 5
        cell_width = (width - gap * 7) / 8
        cell_height = 42

        for index in range(8):
            x1 = round(index * (cell_width + gap))
            x2 = round(x1 + cell_width)
            y1 = 2
            y2 = y1 + cell_height

            if index < len(slot_values):
                slot = int(slot_values[index])
                payout = float(payout_values[slot - 1])

                if payout > 1.0:
                    fill = Theme.SLOT_GOOD
                    fg = Theme.GREEN
                elif payout < 1.0:
                    fill = Theme.SLOT_BAD
                    fg = Theme.RED
                else:
                    fill = Theme.SLOT_NEUTRAL
                    fg = Theme.AMBER

                payout_text = (
                    f"{int(payout)}×"
                    if payout.is_integer()
                    else f"{payout:.1f}×"
                )

                c.create_rectangle(
                    x1, y1, x2, y2,
                    fill=fill,
                    outline=Theme.BORDER_SOFT,
                    width=1,
                )
                c.create_text(
                    (x1 + x2) / 2,
                    14,
                    text=f"{index + 1:02d}",
                    fill=Theme.TEXT_MUTED,
                    font=(Theme.FONT, 7, "bold"),
                )
                c.create_text(
                    (x1 + x2) / 2,
                    29,
                    text=payout_text,
                    fill=fg,
                    font=(Theme.FONT, 12, "bold"),
                )
            else:
                c.create_rectangle(
                    x1, y1, x2, y2,
                    fill=Theme.PANEL,
                    outline=Theme.BORDER_SOFT,
                    width=1,
                )
                c.create_text(
                    (x1 + x2) / 2,
                    14,
                    text=f"{index + 1:02d}",
                    fill=Theme.TEXT_DIM,
                    font=(Theme.FONT, 7, "bold"),
                )
                c.create_text(
                    (x1 + x2) / 2,
                    29,
                    text="--",
                    fill=Theme.TEXT_DIM,
                    font=(Theme.FONT, 12, "bold"),
                )

    # ------------------------------------------------------------------
    # Board rendering
    # ------------------------------------------------------------------

    def _board_geometry(self, width: int, height: int) -> dict:
        top_y = 44
        bottom_y = height - 96
        top_width = 46
        bottom_width = width - 126
        start_x = (width - bottom_width) / 2
        slot_width = bottom_width / 9
        return {
            "top_y": top_y,
            "bottom_y": bottom_y,
            "top_width": top_width,
            "bottom_width": bottom_width,
            "start_x": start_x,
            "slot_width": slot_width,
        }

    def draw_board(self) -> None:
        c = self.board_canvas
        c.delete("all")
        width = self.BOARD_WIDTH
        height = self.BOARD_HEIGHT
        geo = self._board_geometry(width, height)
        top_y = geo["top_y"]
        bottom_y = geo["bottom_y"]
        top_width = geo["top_width"]
        bottom_width = geo["bottom_width"]

        # Warm board well and subtle horizontal bands.
        c.create_rectangle(0, 0, width, height, fill=Theme.BOARD, outline="")
        for y in range(34, height, 48):
            c.create_line(0, y, width, y, fill=Theme.BOARD_DARK, width=1, stipple="gray50")

        left_top = width / 2 - top_width / 2
        right_top = width / 2 + top_width / 2
        left_bottom = width / 2 - bottom_width / 2
        right_bottom = width / 2 + bottom_width / 2

        c.create_polygon(
            left_top, top_y,
            right_top, top_y,
            right_bottom, bottom_y,
            left_bottom, bottom_y,
            fill=Theme.CANVAS_BG,
            outline=Theme.BOARD_EDGE,
            width=2,
        )

        # Launch throat.
        c.create_rectangle(
            width / 2 - 28, 11, width / 2 + 28, top_y + 7,
            fill=Theme.PANEL_ALT, outline=Theme.BORDER, width=2,
        )
        c.create_text(
            width / 2, 27, text="DROP",
            fill=Theme.ACCENT, font=(Theme.FONT, 9, "bold"),
        )

        self._draw_pegs(width, height, geo)
        self._draw_slots(width, height, geo)

        # Dynamic balls are tagged separately so animation frames do not have
        # to rebuild the board, pegs and slots.
        self._draw_ball_layer(clear_existing=False)

        # Current stake tag.
        c.create_rectangle(
            14, 12, 160, 64,
            fill=Theme.PANEL_ALT, outline=Theme.BORDER_SOFT, width=1,
        )
        c.create_text(
            25, 26, text="每颗弹珠",
            fill=Theme.TEXT_MUTED, font=(Theme.FONT_CJK, 8, "bold"),
            anchor=tk.W,
        )
        c.create_text(
            25, 48, text=f"${self.current_bet:,.2f}",
            fill=Theme.CYAN, font=(Theme.FONT, 14, "bold"),
            anchor=tk.W,
        )

    def _draw_ball_layer(self, *, clear_existing: bool = True) -> None:
        """Redraw only the moving balls.

        A long painted trail makes a physically correct trajectory look like a
        scripted spline, so the rigid-body version deliberately draws only the
        current ball position.
        """
        c = self.board_canvas
        if clear_existing:
            c.delete("ball_dynamic")

        for ball in self.balls:
            if ball.get("finished"):
                continue
            x = float(ball.get("x", 0.0))
            y = float(ball.get("y", 0.0))
            c.create_oval(
                x - self.ball_radius, y - self.ball_radius,
                x + self.ball_radius, y + self.ball_radius,
                fill=ball["color"],
                outline=Theme.BALL_OUTLINE,
                width=2,
                tags=("ball_dynamic",),
            )

    def _peg_layout(self, width: int, geo: dict) -> list[list[tuple[float, float]]]:
        """Return the exact triangular peg lattice used by drawing and physics."""
        top_y = geo["top_y"] + 30
        bottom_y = geo["bottom_y"] - 42
        top_width = 64
        bottom_width = geo["bottom_width"] - 70
        rows: list[list[tuple[float, float]]] = []

        for row in range(8):
            progress = row / 7.0
            current_width = top_width + (bottom_width - top_width) * progress
            y = top_y + (bottom_y - top_y) * progress
            peg_count = row + 1
            spacing = current_width / (peg_count + 1)
            rows.append([
                (width / 2 - current_width / 2 + spacing * (index + 1), y)
                for index in range(peg_count)
            ])
        return rows

    def _draw_pegs(self, width: int, height: int, geo: dict) -> None:
        c = self.board_canvas
        self.peg_rows = self._peg_layout(width, geo)
        self.pegs = [peg for row in self.peg_rows for peg in row]

        for row in self.peg_rows:
            for x, y in row:
                c.create_oval(
                    x - self.peg_radius, y - self.peg_radius,
                    x + self.peg_radius, y + self.peg_radius,
                    fill=Theme.PEG,
                    outline=Theme.PEG_BORDER,
                    width=1,
                )

    def _draw_slots(self, width: int, height: int, geo: dict) -> None:
        c = self.board_canvas
        start_x = geo["start_x"]
        slot_width = geo["slot_width"]
        start_y = geo["bottom_y"] + 8
        slot_height = 50
        values = PAYOUTS[self.risk_level]

        for i, payout in enumerate(values):
            x1 = start_x + i * slot_width
            x2 = start_x + (i + 1) * slot_width
            if payout > 1:
                fill = Theme.SLOT_GOOD
                fg = Theme.GREEN
            elif payout < 1:
                fill = Theme.SLOT_BAD
                fg = Theme.RED
            else:
                fill = Theme.SLOT_NEUTRAL
                fg = Theme.AMBER

            c.create_rectangle(
                x1, start_y, x2, start_y + slot_height,
                fill=fill, outline=Theme.SLOT_EDGE, width=1,
            )
            payout_text = f"{int(payout)}×" if float(payout).is_integer() else f"{payout:.1f}×"
            c.create_text(
                (x1 + x2) / 2, start_y + 17,
                text=payout_text,
                fill=fg,
                font=(Theme.FONT, 10, "bold"),
            )
            c.create_text(
                (x1 + x2) / 2, start_y + 36,
                text=f"槽 {i + 1}",
                fill=Theme.TEXT_MUTED,
                font=(Theme.FONT_CJK, 7, "bold"),
            )

    # ------------------------------------------------------------------
    # Gameplay / physics
    # ------------------------------------------------------------------

    def launch_ball(self) -> None:
        if self.current_bet <= 0:
            messagebox.showwarning("尚未下注", "请先选择下注筹码。", parent=self.root)
            return
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "账户余额不足以发射这颗弹珠。", parent=self.root)
            return

        stake = float(self.current_bet)
        risk = self.risk_level

        self.balance -= stake
        update_balance_in_json(self.username, self.balance)

        self._add_ball(stake=stake, risk=risk)
        if not self.animation_running:
            self.animation_running = True
            self._last_frame_time = time.monotonic()
            self.root.after(self.frame_interval_ms, self.animate_balls)
        self.update_display()

    @staticmethod
    def _choose_target_route() -> tuple[list[int], int]:
        """Lock eight fair left/right peg decisions before animation starts."""
        route = [1 if random.random() < 0.5 else -1 for _ in range(8)]
        target_slot = 1 + sum(1 for direction in route if direction > 0)
        return route, target_slot

    def _build_contact_plan(
        self,
        route: list[int],
        geo: dict,
    ) -> tuple[list[tuple[float, float]], tuple[float, float]]:
        """Create physically valid contact points on the selected side of pegs.

        For a right deflection the ball touches the upper-right surface of the
        peg; for a left deflection it touches the upper-left surface.  The
        previous version used the opposite side, which visually made the ball
        pass through a peg before changing direction.
        """
        if not self.peg_rows:
            self.peg_rows = self._peg_layout(self.BOARD_WIDTH, geo)
            self.pegs = [peg for row in self.peg_rows for peg in row]

        separation = self.ball_radius + self.peg_radius + 0.20
        contacts: list[tuple[float, float]] = []
        rights_before = 0

        for row_index, direction in enumerate(route):
            peg_x, peg_y = self.peg_rows[row_index][rights_before]

            # Varying the normal angle changes both the impact soundless "kick"
            # and the following arc without ever moving the contact off the peg.
            angle = math.radians(random.uniform(35.0, 43.5))
            normal_x = direction * math.sin(angle)
            normal_y = -math.cos(angle)
            contacts.append((
                peg_x + normal_x * separation,
                peg_y + normal_y * separation,
            ))

            if direction > 0:
                rights_before += 1

        target_slot = rights_before + 1
        slot_centre = geo["start_x"] + (target_slot - 0.5) * geo["slot_width"]
        landing_margin = geo["slot_width"] * 0.13
        final_point = (
            slot_centre + random.uniform(-landing_margin, landing_margin),
            geo["bottom_y"] + 2.0,
        )
        return contacts, final_point

    def _set_flight_event(
        self,
        ball: dict,
        target: tuple[float, float],
        *,
        event_kind: str,
        launch_segment: bool = False,
    ) -> None:
        """Set one genuine free-flight segment ending at a collision event."""
        x0 = float(ball["x"])
        y0 = float(ball["y"])
        x1, y1 = target
        dx = x1 - x0
        dy = y1 - y0
        gravity = float(ball["gravity"])

        if launch_segment:
            # The ball exits the throat with downward velocity and reaches the
            # first peg without any invisible horizontal attraction.
            duration = random.uniform(0.175, 0.205)
            vx = dx / duration
            vy = (dy - 0.5 * gravity * duration * duration) / duration
        else:
            # Convert incoming impact energy into a small upward rebound.  The
            # next collision time follows from the vertical kinematic equation;
            # horizontal speed is then the exact speed required to reach the
            # next visible peg surface.
            incoming_speed = math.hypot(float(ball["vx"]), float(ball["vy"]))
            rebound_speed = max(
                54.0,
                min(98.0, incoming_speed * random.uniform(0.21, 0.285)),
            )
            vy = -rebound_speed
            discriminant = max(0.0, vy * vy + 2.0 * gravity * max(0.1, dy))
            duration = (-vy + math.sqrt(discriminant)) / gravity
            duration = max(0.22, duration)
            vx = dx / duration

        ball["vx"] = vx
        ball["vy"] = vy
        ball["event_x"] = float(x1)
        ball["event_y"] = float(y1)
        ball["event_kind"] = event_kind
        ball["time_to_event"] = float(duration)

    def _add_ball(self, *, stake: float, risk: str) -> None:
        geo = self._board_geometry(self.BOARD_WIDTH, self.BOARD_HEIGHT)
        colors = ("#B75B55", "#4D7893", "#5E875F", "#C19643", "#9B648B")

        route, target_slot = self._choose_target_route()
        contacts, final_point = self._build_contact_plan(route, geo)

        # A very small launch-side offset is enough to make the first impact
        # readable while the throat still appears centred.
        start_x = self.BOARD_WIDTH / 2 + route[0] * random.uniform(0.7, 1.7)
        start_y = geo["top_y"] - 4.0

        ball = {
            "x": start_x,
            "y": start_y,
            "vx": 0.0,
            "vy": 0.0,
            "gravity": random.uniform(955.0, 1010.0),
            "color": random.choice(colors),
            "finished": False,
            "slot": None,
            "target_slot": target_slot,
            "route": route,
            "contacts": contacts,
            "final_point": final_point,
            "next_contact": 0,
            "event_kind": "peg",
            "time_to_event": 0.0,
            "stake": stake,
            "risk": risk,
            "start_time": time.monotonic(),
        }
        self._set_flight_event(
            ball,
            contacts[0],
            event_kind="peg",
            launch_segment=True,
        )
        self.balls.append(ball)
        self.active_balls += 1

    def _handle_peg_impact(self, ball: dict) -> None:
        """Apply the route-control impulse only while touching a visible peg."""
        row_index = int(ball["next_contact"])
        ball["x"] = float(ball["event_x"])
        ball["y"] = float(ball["event_y"])
        ball["next_contact"] = row_index + 1

        if row_index + 1 < len(ball["contacts"]):
            target = ball["contacts"][row_index + 1]
            self._set_flight_event(ball, target, event_kind="peg")
        else:
            self._set_flight_event(
                ball,
                ball["final_point"],
                event_kind="landing",
            )

    def _advance_ball(self, ball: dict, frame_dt: float) -> None:
        """Advance a ball analytically, splitting the frame at impacts."""
        remaining = max(0.0, float(frame_dt))
        gravity = float(ball["gravity"])

        while remaining > 1e-7 and not ball.get("finished"):
            event_time = max(0.0, float(ball["time_to_event"]))
            step = min(remaining, event_time)

            ball["x"] += ball["vx"] * step
            ball["y"] += ball["vy"] * step + 0.5 * gravity * step * step
            ball["vy"] += gravity * step
            ball["time_to_event"] = event_time - step
            remaining -= step

            if ball["time_to_event"] <= 1e-7:
                # Snap only the sub-pixel integration error at the exact moment
                # of contact. This is not a visible route correction.
                ball["x"] = float(ball["event_x"])
                ball["y"] = float(ball["event_y"])

                if ball["event_kind"] == "peg":
                    self._handle_peg_impact(ball)
                else:
                    ball["slot"] = int(ball["target_slot"])
                    ball["finished"] = True

    def animate_balls(self) -> None:
        if not self.balls:
            self.animation_running = False
            self.active_balls = 0
            self.update_display()
            return

        now = time.monotonic()
        frame_dt = min(self.max_frame_dt, max(0.001, now - self._last_frame_time))
        self._last_frame_time = now

        finished_indices: list[int] = []
        active_count = 0

        for index, ball in enumerate(self.balls):
            if ball.get("finished"):
                finished_indices.append(index)
                continue
            self._advance_ball(ball, frame_dt)
            if ball.get("finished"):
                finished_indices.append(index)
            else:
                active_count += 1

        self.active_balls = active_count
        if finished_indices:
            self._process_finished_balls(finished_indices)
            self.update_display()
        else:
            self.active_var.set(str(self.active_balls))
            self._draw_ball_layer()

        if self.balls:
            self.root.after(self.frame_interval_ms, self.animate_balls)
        else:
            self.animation_running = False
            self.active_balls = 0
            self.update_display()

    def _process_finished_balls(self, indices: list[int]) -> None:
        valid = sorted(
            {i for i in indices if 0 <= i < len(self.balls)},
            key=lambda i: self.balls[i]["start_time"],
        )

        for index in valid:
            ball = self.balls[index]
            slot = int(ball["slot"])
            slot_index = slot - 1
            risk = ball["risk"]
            stake = float(ball["stake"])
            payout = float(PAYOUTS[risk][slot_index])
            winnings = stake * payout

            self.balance += winnings
            self.last_win = winnings
            update_balance_in_json(self.username, self.balance)

            mode = RISK_KEY[risk]
            record_landing(mode, slot)

            payout_text = f"{int(payout)}×" if payout.is_integer() else f"{payout:.1f}×"
            self.last_result_text = f"槽 {slot} · {payout_text} · ${winnings:,.2f}"
            self._show_ball_result(slot, payout_text, winnings)

        for index in sorted(valid, reverse=True):
            self.balls.pop(index)

        self.active_balls = sum(1 for ball in self.balls if not ball.get("finished"))

    def _show_ball_result(self, slot: int, payout_text: str, winnings: float) -> None:
        c = self.board_canvas
        geo = self._board_geometry(self.BOARD_WIDTH, self.BOARD_HEIGHT)
        x = geo["start_x"] + (slot - 0.5) * geo["slot_width"]
        y = geo["bottom_y"] - 15
        result_id = c.create_text(
            x, y,
            text=f"{payout_text}\n${winnings:,.2f}",
            fill=Theme.AMBER,
            font=(Theme.FONT, 10, "bold"),
            justify=tk.CENTER,
        )
        try:
            self.root.after(1800, lambda item=result_id: c.delete(item))
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Closing / embedding
    # ------------------------------------------------------------------

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
        if EmbeddedGamePage is None:
            raise RuntimeError(
                "EmbeddedGamePage is unavailable. Place plinko.py inside the Small_Games package "
                "or make small_games.py importable before using embedded mode."
            )
        page = EmbeddedGamePage(
            parent,
            title="Plinko",
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        page.set_requested_size(1150, 750)
        game = PlinkoGame(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = PlinkoGame(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    final_balance = main(10000.0, "test_user")
    print(f"Final balance: {final_balance:.2f}")