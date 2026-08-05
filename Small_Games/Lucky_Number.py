"""Lucky Number — ChickenCrossing-style warm fixed HMI.

Original game rules retained:
- Result is uniformly random from 1..100.
- ABOVE wins when result > target.
- BELOW wins when result < target.
- Exact target match returns 2x the current dynamic payout.
- Dynamic payout uses the original fair-odds formula with a 1% house edge.
- ABOVE target range: 3..99.
- BELOW target range: 1..97.
- Ones digit animates first, then tens digit, using the original timing.
- Latest results continue to persist in ../A_Logs/small_g_dice.json.

The visual layer follows ChickenCrossing_tk.py's fixed 1150x750 warm HMI and
supports the project's EmbeddedGamePage single-Tk mode.
"""

from __future__ import annotations

import json
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


VERSION = "LuckyNum-ChickenStyle-R1"


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

    WIN_ZONE = "#89A989"
    LOSE_ZONE = "#C99C96"
    TARGET = "#D4B55E"
    DISPLAY_BG = "#3F464D"
    DISPLAY_EDGE = "#69727A"
    DIGIT_BG = "#565E66"
    DIGIT_TEXT = "#F5F1E8"

    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )
    FONT_EMOJI = "Segoe UI Emoji"


CHIP_CONFIGS = (
    ("$5", "5", "#D75A54", "white"),
    ("$25", "25", "#67B56A", "black"),
    ("$100", "100", "#292929", "white"),
    ("$500", "500", "#D47AB7", "black"),
    ("$1K", "1000", "#F4F1EA", "black"),
)


def get_data_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../saving_data.json")


def get_log_file_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "../A_Logs/small_g_dice.json",
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


def _default_logs() -> dict:
    return {f"{index:02d}": 0 for index in range(1, 9)}


def load_game_log() -> dict:
    try:
        with open(get_log_file_path(), "r", encoding="utf-8") as file:
            raw = json.load(file)
        if not isinstance(raw, dict):
            return _default_logs()
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return _default_logs()

    result = _default_logs()
    for key in result:
        try:
            value = int(raw.get(key, 0))
        except (TypeError, ValueError):
            value = 0
        result[key] = value if 0 <= value <= 100 else 0
    return result


def save_game_log(result: int) -> dict:
    logs = load_game_log()
    for index in range(8, 1, -1):
        logs[f"{index:02d}"] = logs[f"{index - 1:02d}"]
    logs["01"] = int(result)

    path = get_log_file_path()
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(logs, file, ensure_ascii=False, indent=4)
    except OSError:
        pass
    return logs


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

    def set_enabled(self, enabled: bool) -> None:
        self._state = tk.NORMAL if enabled else tk.DISABLED
        if not enabled:
            self._hovered = False
            self._pressed = False
            self._flash = False
        super().configure(cursor="hand2" if enabled else "")
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


class DiceGame:
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
    CANVAS_HEIGHT = 430

    def __init__(self, root, initial_balance: float, username: str):
        self.root = root
        self._configure_root()

        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0.0
        self.current_bet = 0.0
        self.target_number = 50
        self.bet_type = "above"
        self.game_active = False
        self.last_win = 0.0

        self.animation_running = False
        self.ones_digit = "-"
        self.tens_digit = "-"
        self.final_result = 0
        self.last_ones_digit = -1
        self.last_tens_digit = -1
        self.ones_animation_count = 0
        self.tens_animation_count = 0
        self.ones_animation_started = 0.0
        self.tens_animation_started = 0.0
        self.after_jobs: set[str] = set()

        self.game_logs = load_game_log()

        self.balance_var = tk.StringVar()
        self.bet_var = tk.StringVar()
        self.last_win_var = tk.StringVar()
        self.odds_var = tk.StringVar()
        self.win_var = tk.StringVar()
        self.target_var = tk.StringVar()
        self.direction_var = tk.StringVar()
        self.result_var = tk.StringVar(value="请下注并开始游戏")
        self.range_var = tk.StringVar()

        self.chip_buttons: list[ChipButton] = []

        self.create_widgets()
        self.update_display()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("幸运数字")
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
            font=(Theme.FONT_CJK, 10, "bold"),
            anchor=tk.W,
        )

    def _schedule(self, delay: int, callback: Callable[[], None]) -> str:
        job_id = ""

        def wrapped() -> None:
            self.after_jobs.discard(job_id)
            callback()

        job_id = self.root.after(delay, wrapped)
        self.after_jobs.add(job_id)
        return job_id

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

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

        icon = tk.Canvas(
            header, width=48, height=48,
            bg=Theme.PANEL, bd=0, highlightthickness=0,
        )
        icon.place(x=14, y=11)
        icon.create_oval(2, 2, 46, 46, fill=Theme.ACCENT_SOFT, outline=Theme.ACCENT, width=2)
        icon.create_text(
            24, 24, text="77",
            fill=Theme.ACCENT, font=(Theme.FONT, 13, "bold"),
        )

        tk.Label(
            header,
            text="LUCKY NUMBER",
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT, 18, "bold"),
            anchor=tk.W,
        ).place(x=74, y=10, width=340, height=27)
        tk.Label(
            header,
            text="幸运数字",
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

        top = tk.Frame(panel, width=self.CANVAS_WIDTH, height=74, bg=Theme.PANEL)
        top.place(x=0, y=0, width=self.CANVAS_WIDTH, height=74)

        tk.Label(
            top,
            textvariable=self.range_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 18, "bold"),
            anchor=tk.W,
        ).place(x=18, y=13, width=450, height=29)

        tk.Label(
            top,
            textvariable=self.result_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.W,
        ).place(x=18, y=44, width=535, height=20)

        tk.Label(
            top,
            textvariable=self.odds_var,
            bg=Theme.ACCENT_SOFT,
            fg=Theme.ACCENT,
            font=(Theme.FONT, 12, "bold"),
            anchor=tk.CENTER,
        ).place(x=590, y=19, width=136, height=32)

        self.game_canvas = tk.Canvas(
            panel,
            width=self.CANVAS_WIDTH,
            height=self.CANVAS_HEIGHT,
            bg=Theme.CANVAS_BG,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.game_canvas.place(x=0, y=74, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT)
        self.game_canvas.bind("<Button-1>", self._on_bar_pointer)
        self.game_canvas.bind("<B1-Motion>", self._on_bar_pointer)

        history = tk.Frame(
            panel,
            bg=Theme.PANEL_ALT,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        history.place(x=15, y=516, width=716, height=97)

        tk.Label(
            history,
            text="最近 8 局结果",
            bg=Theme.PANEL_ALT,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.W,
        ).place(x=10, y=5, width=140, height=18)

        self.history_canvas = tk.Canvas(
            history,
            width=694,
            height=61,
            bg=Theme.PANEL_ALT,
            bd=0,
            highlightthickness=0,
        )
        self.history_canvas.place(x=10, y=29, width=694, height=61)

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
            sidebar, "上局获胜", self.last_win_var, Theme.GREEN,
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

        direction = self._card(sidebar, width=348, height=82)
        direction.place(x=0, y=189, width=348, height=82)
        self._section_title(direction.inner, "选择方向").place(x=0, y=0, width=120, height=20)

        self.below_button = ModernButton(
            direction.inner,
            text="低于目标",
            command=self.select_below,
            background=Theme.PANEL_ALT,
            hover_background=Theme.PANEL_HOVER,
            foreground=Theme.TEXT,
            font_size=11,
            bold=True,
        )
        self.below_button.place(x=0, y=28, width=155, height=32)

        self.above_button = ModernButton(
            direction.inner,
            text="高于目标",
            command=self.select_above,
            background=Theme.ACCENT,
            hover_background=Theme.ACCENT_HOVER,
            foreground="#FFFFFF",
            font_size=11,
            bold=True,
        )
        self.above_button.place(x=167, y=28, width=155, height=32)

        target = self._card(sidebar, width=348, height=92)
        target.place(x=0, y=281, width=348, height=92)
        self._section_title(target.inner, "目标数字").place(x=0, y=0, width=100, height=20)

        self.minus_button = ModernButton(
            target.inner,
            text="−",
            command=lambda: self.nudge_target(-1),
            background=Theme.PANEL_ALT,
            hover_background=Theme.PANEL_HOVER,
            foreground=Theme.TEXT,
            font_size=16,
            bold=True,
        )
        self.minus_button.place(x=0, y=27, width=62, height=39)

        tk.Label(
            target.inner,
            textvariable=self.target_var,
            bg=Theme.PANEL_ALT,
            fg=Theme.ACCENT,
            font=(Theme.FONT, 20, "bold"),
            anchor=tk.CENTER,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        ).place(x=74, y=27, width=174, height=39)

        self.plus_button = ModernButton(
            target.inner,
            text="+",
            command=lambda: self.nudge_target(1),
            background=Theme.PANEL_ALT,
            hover_background=Theme.PANEL_HOVER,
            foreground=Theme.TEXT,
            font_size=16,
            bold=True,
        )
        self.plus_button.place(x=260, y=27, width=62, height=39)

        estimate = self._card(sidebar, width=348, height=68)
        estimate.place(x=0, y=383, width=348, height=68)

        tk.Label(
            estimate.inner,
            text="当前赔率",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9),
            anchor=tk.W,
        ).place(x=0, y=0, width=90, height=18)
        tk.Label(
            estimate.inner,
            textvariable=self.odds_var,
            bg=Theme.PANEL,
            fg=Theme.AMBER,
            font=(Theme.FONT, 13, "bold"),
            anchor=tk.W,
        ).place(x=0, y=20, width=100, height=24)

        tk.Label(
            estimate.inner,
            text="预计返还",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9),
            anchor=tk.E,
        ).place(x=110, y=0, width=212, height=18)
        tk.Label(
            estimate.inner,
            textvariable=self.win_var,
            bg=Theme.PANEL,
            fg=Theme.CYAN,
            font=(Theme.FONT, 13, "bold"),
            anchor=tk.E,
        ).place(x=110, y=20, width=212, height=24)

        actions = self._card(sidebar, width=348, height=92)
        actions.place(x=0, y=461, width=348, height=92)

        self.reset_bet_button = ModernButton(
            actions.inner,
            text="清空下注",
            command=self.reset_bet,
            background=Theme.RED,
            hover_background=Theme.RED_HOVER,
            foreground="#FFFFFF",
            font_size=11,
            bold=True,
        )
        self.reset_bet_button.place(x=0, y=0, width=322, height=34)

        self.start_button = ModernButton(
            actions.inner,
            text="开始游戏",
            command=self.start_game,
            background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.start_button.place(x=0, y=42, width=322, height=34)

        rules = self._card(sidebar, width=348, height=67, padding=9)
        rules.place(x=0, y=563, width=348, height=67)

        tk.Label(
            rules.inner,
            text="规则：结果为 1–100。高于/低于目标即中奖；若刚好等于目标，按当前赔率的 2 倍返还。",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8),
            justify=tk.LEFT,
            anchor=tk.W,
            wraplength=322,
        ).place(x=0, y=0, width=322, height=49)

    # ------------------------------------------------------------------
    # Game rules
    # ------------------------------------------------------------------

    def calculate_payout(self, target: int, bet_type: str) -> float:
        if bet_type == "above":
            probability = (100 - target) / 100
        else:
            probability = (target - 1) / 100

        if probability == 0:
            probability = 0.01

        fair_odds = 1.0 / probability
        house_edge = 0.01
        payout = fair_odds * (1 - house_edge)
        payout = max(1.01, min(99.0, payout))
        return round(payout, 2)

    def _target_bounds(self) -> tuple[int, int]:
        return (3, 99) if self.bet_type == "above" else (1, 97)

    def select_above(self) -> None:
        if self.game_active:
            return
        self.bet_type = "above"
        if self.target_number < 3:
            self.target_number = 3
        self.update_display()

    def select_below(self) -> None:
        if self.game_active:
            return
        self.bet_type = "below"
        if self.target_number > 97:
            self.target_number = 97
        self.update_display()

    def nudge_target(self, delta: int) -> None:
        if self.game_active:
            return
        low, high = self._target_bounds()
        new_target = max(low, min(high, self.target_number + int(delta)))
        if new_target != self.target_number:
            self.target_number = new_target
            self.update_display()

    def _on_bar_pointer(self, event) -> None:
        if self.game_active:
            return

        x1, x2 = 52, self.CANVAS_WIDTH - 52
        y1, y2 = 332, 390
        if not (x1 - 15 <= event.x <= x2 + 15 and y1 - 15 <= event.y <= y2 + 15):
            return

        ratio = (event.x - x1) / max(1, x2 - x1)
        target = int(round(1 + max(0.0, min(1.0, ratio)) * 98))
        low, high = self._target_bounds()
        target = max(low, min(high, target))

        if target != self.target_number:
            self.target_number = target
            self.update_display()

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
            self.update_display()
        else:
            messagebox.showwarning("余额不足", "账户余额不足以加入这个筹码。", parent=self.root)

    def reset_bet(self) -> None:
        if self.game_active:
            return
        self.current_bet = 0.0
        self.update_display()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw_game(self) -> None:
        c = self.game_canvas
        c.delete("all")
        w = self.CANVAS_WIDTH
        h = self.CANVAS_HEIGHT

        # Warm instrument well.
        c.create_rectangle(0, 0, w, h, fill=Theme.CANVAS_BG, outline="")

        # Top status strip.
        c.create_rectangle(
            34, 24, w - 34, 90,
            fill=Theme.PANEL_ALT, outline=Theme.BORDER_SOFT, width=1,
        )
        c.create_text(
            52, 44,
            text="当前判定",
            anchor=tk.W,
            fill=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9, "bold"),
        )
        condition = (
            f"结果 < {self.target_number}"
            if self.bet_type == "below"
            else f"结果 > {self.target_number}"
        )
        c.create_text(
            52, 68,
            text=condition,
            anchor=tk.W,
            fill=Theme.ACCENT,
            font=(Theme.FONT_CJK, 16, "bold"),
        )

        c.create_text(
            w - 52, 44,
            text="完美命中",
            anchor=tk.E,
            fill=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9, "bold"),
        )
        c.create_text(
            w - 52, 68,
            text=f"= {self.target_number} · {self.calculate_payout(self.target_number, self.bet_type) * 2:.2f}×",
            anchor=tk.E,
            fill=Theme.AMBER,
            font=(Theme.FONT, 14, "bold"),
        )

        # Large digital number module.
        display_x1, display_y1 = 178, 118
        display_x2, display_y2 = w - 178, 297
        c.create_rectangle(
            display_x1, display_y1, display_x2, display_y2,
            fill=Theme.DISPLAY_BG, outline=Theme.DISPLAY_EDGE, width=2,
        )

        c.create_text(
            w / 2, 139,
            text="RANDOM 01–100",
            fill="#C9D0D4",
            font=(Theme.FONT, 9, "bold"),
        )

        # Tens/ones drums. For 100, the final tens value is intentionally "10",
        # matching the original representation.
        left_x1, left_y1, left_x2, left_y2 = 237, 166, 351, 264
        right_x1, right_y1, right_x2, right_y2 = 395, 166, 509, 264

        for x1, y1, x2, y2 in (
            (left_x1, left_y1, left_x2, left_y2),
            (right_x1, right_y1, right_x2, right_y2),
        ):
            c.create_rectangle(
                x1, y1, x2, y2,
                fill=Theme.DIGIT_BG, outline="#818A92", width=2,
            )
            c.create_line(x1 + 8, (y1 + y2) / 2, x2 - 8, (y1 + y2) / 2,
                          fill="#454C53", width=1)

        c.create_text(
            (left_x1 + left_x2) / 2, 157,
            text="十位", fill="#C9D0D4",
            font=(Theme.FONT_CJK, 8, "bold"),
        )
        c.create_text(
            (right_x1 + right_x2) / 2, 157,
            text="个位", fill="#C9D0D4",
            font=(Theme.FONT_CJK, 8, "bold"),
        )

        c.create_text(
            (left_x1 + left_x2) / 2,
            (left_y1 + left_y2) / 2,
            text=str(self.tens_digit),
            fill=Theme.DIGIT_TEXT,
            font=(Theme.FONT, 38, "bold"),
        )
        c.create_text(
            (right_x1 + right_x2) / 2,
            (right_y1 + right_y2) / 2,
            text=str(self.ones_digit),
            fill=Theme.DIGIT_TEXT,
            font=(Theme.FONT, 38, "bold"),
        )

        # Probability / target bar.
        bar_x1, bar_x2 = 52, w - 52
        bar_y1, bar_y2 = 332, 390
        target_ratio = (self.target_number - 1) / 98
        target_x = bar_x1 + (bar_x2 - bar_x1) * target_ratio

        if self.bet_type == "below":
            left_fill, right_fill = Theme.WIN_ZONE, Theme.LOSE_ZONE
        else:
            left_fill, right_fill = Theme.LOSE_ZONE, Theme.WIN_ZONE

        c.create_rectangle(
            bar_x1, bar_y1, target_x, bar_y2,
            fill=left_fill, outline="",
        )
        c.create_rectangle(
            target_x, bar_y1, bar_x2, bar_y2,
            fill=right_fill, outline="",
        )
        c.create_rectangle(
            target_x - 13, bar_y1 - 5,
            target_x + 13, bar_y2 + 5,
            fill=Theme.TARGET, outline=Theme.AMBER, width=2,
        )
        c.create_text(
            target_x, (bar_y1 + bar_y2) / 2,
            text=str(self.target_number),
            fill=Theme.TEXT,
            font=(Theme.FONT, 11, "bold"),
        )

        # Scale labels.
        for number in (1, 25, 50, 75, 99):
            ratio = (number - 1) / 98
            x = bar_x1 + (bar_x2 - bar_x1) * ratio
            c.create_line(x, bar_y2 + 6, x, bar_y2 + 11, fill=Theme.TEXT_DIM, width=1)
            c.create_text(
                x, bar_y2 + 23,
                text=str(number),
                fill=Theme.TEXT_MUTED,
                font=(Theme.FONT, 8, "bold"),
            )

        c.create_text(
            bar_x1, 316,
            text="拖动此区域选择目标数字",
            anchor=tk.W,
            fill=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8, "bold"),
        )

    def draw_history(self) -> None:
        c = self.history_canvas
        c.delete("all")
        width = 694
        gap = 7
        cell_width = (width - gap * 7) / 8

        for index in range(8):
            key = f"{index + 1:02d}"
            value = int(self.game_logs.get(key, 0))

            x1 = round(index * (cell_width + gap))
            x2 = round(x1 + cell_width)
            y1, y2 = 2, 58

            if value <= 0:
                fill = Theme.PANEL
                value_text = "--"
                fg = Theme.TEXT_DIM
            else:
                if value == self.target_number:
                    fill = "#E1D29A"
                    fg = Theme.AMBER
                else:
                    won = (
                        value < self.target_number
                        if self.bet_type == "below"
                        else value > self.target_number
                    )
                    fill = "#C5D4C2" if won else "#D8C1BD"
                    fg = Theme.GREEN if won else Theme.RED
                value_text = str(value)

            c.create_rectangle(
                x1, y1, x2, y2,
                fill=fill, outline=Theme.BORDER_SOFT, width=1,
            )
            c.create_text(
                (x1 + x2) / 2, 15,
                text=f"{index + 1:02d}",
                fill=Theme.TEXT_MUTED,
                font=(Theme.FONT, 7, "bold"),
            )
            c.create_text(
                (x1 + x2) / 2, 38,
                text=value_text,
                fill=fg,
                font=(Theme.FONT, 15, "bold"),
            )

    # ------------------------------------------------------------------
    # Animation / settlement
    # ------------------------------------------------------------------

    def _set_controls_enabled(self, enabled: bool) -> None:
        for chip in self.chip_buttons:
            chip.set_enabled(enabled)

        state = tk.NORMAL if enabled else tk.DISABLED
        self.reset_bet_button.configure(state=state)
        self.minus_button.configure(state=state)
        self.plus_button.configure(state=state)

        if enabled:
            self._refresh_direction_buttons()
        else:
            self.below_button.configure(state=tk.DISABLED)
            self.above_button.configure(state=tk.DISABLED)

    def _refresh_direction_buttons(self) -> None:
        # During animation both direction buttons must remain locked even when
        # update_display() redraws the HMI.
        if self.game_active:
            self.below_button.configure(state=tk.DISABLED)
            self.above_button.configure(state=tk.DISABLED)
            return

        if self.bet_type == "above":
            self.above_button.configure(state=tk.DISABLED)
            self.above_button.set_colors(Theme.ACCENT, Theme.ACCENT_HOVER, "#FFFFFF")
            self.below_button.configure(state=tk.NORMAL)
            self.below_button.set_colors(Theme.PANEL_ALT, Theme.PANEL_HOVER, Theme.TEXT)
        else:
            self.below_button.configure(state=tk.DISABLED)
            self.below_button.set_colors(Theme.ACCENT, Theme.ACCENT_HOVER, "#FFFFFF")
            self.above_button.configure(state=tk.NORMAL)
            self.above_button.set_colors(Theme.PANEL_ALT, Theme.PANEL_HOVER, Theme.TEXT)

    def start_game(self) -> None:
        if self.game_active or self.animation_running:
            return
        if self.current_bet <= 0:
            self.result_var.set("请先选择下注筹码")
            return
        if self.current_bet > self.balance:
            self.result_var.set("余额不足")
            return

        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        self.game_active = True
        self._set_controls_enabled(False)
        self.start_button.configure(state=tk.DISABLED)
        update_balance_in_json(self.username, self.balance)

        self.roll_dice()
        self.update_display()

    def roll_dice(self) -> None:
        self.animation_running = True
        self.ones_digit = "-"
        self.tens_digit = "-"
        self.final_result = random.randint(1, 100)
        self.last_ones_digit = -1
        self.last_tens_digit = -1
        self.ones_animation_count = 0
        self.tens_animation_count = 0
        self.ones_animation_started = time.monotonic()
        self.tens_animation_started = 0.0

        if self.final_result == 100:
            final_tens = 10
            final_ones = 0
        else:
            final_tens = self.final_result // 10
            final_ones = self.final_result % 10

        self.result_var.set("个位滚动中…")
        self.animate_ones_digit(final_ones, final_tens)

    @staticmethod
    def get_different_digit(last_digit: int) -> int:
        candidates = [digit for digit in range(10) if digit != last_digit]
        return random.choice(candidates)

    def animate_ones_digit(self, final_ones: int, final_tens: int) -> None:
        if not self.animation_running:
            return

        elapsed = time.monotonic() - self.ones_animation_started
        if elapsed < 1.5:
            self.ones_digit = self.get_different_digit(self.last_ones_digit)
            self.last_ones_digit = self.ones_digit
            self.tens_digit = "-"
            self.ones_animation_count += 1
            self.draw_game()
            self._schedule(16, lambda: self.animate_ones_digit(final_ones, final_tens))
            return

        self.ones_digit = final_ones
        self.draw_game()
        self.result_var.set("个位锁定 · 等待十位")
        self._schedule(500, lambda: self._begin_tens_animation(final_tens))

    def _begin_tens_animation(self, final_tens: int) -> None:
        if not self.animation_running:
            return
        self.tens_animation_started = time.monotonic()
        self.animate_tens_digit(final_tens)

    def animate_tens_digit(self, final_tens: int) -> None:
        if not self.animation_running:
            return

        elapsed = time.monotonic() - self.tens_animation_started
        if elapsed < 1.5:
            self.tens_digit = self.get_different_digit(self.last_tens_digit)
            self.last_tens_digit = self.tens_digit
            self.tens_animation_count += 1
            self.draw_game()
            self._schedule(16, lambda: self.animate_tens_digit(final_tens))
            return

        self.tens_digit = final_tens
        self.draw_game()
        self.result_var.set("十位锁定 · 正在结算")
        self._schedule(500, self.finish_roll)

    def finish_roll(self) -> None:
        if not self.game_active:
            return

        self.animation_running = False
        payout = self.calculate_payout(self.target_number, self.bet_type)

        win = False
        exact_match = False

        if self.bet_type == "above":
            if self.final_result > self.target_number:
                win = True
            elif self.final_result == self.target_number:
                exact_match = True
        else:
            if self.final_result < self.target_number:
                win = True
            elif self.final_result == self.target_number:
                exact_match = True

        if exact_match:
            win_amount = self.bet_amount * payout * 2
            self.balance += win_amount
            self.last_win = win_amount
            self.result_var.set(f"完美命中 · 结果 {self.final_result} · 返还 ${win_amount:,.2f}")
        elif win:
            win_amount = self.bet_amount * payout
            self.balance += win_amount
            self.last_win = win_amount
            self.result_var.set(f"中奖 · 结果 {self.final_result} · 返还 ${win_amount:,.2f}")
        else:
            self.last_win = 0.0
            self.result_var.set(f"未中奖 · 结果 {self.final_result}")

        self.game_logs = save_game_log(self.final_result)
        update_balance_in_json(self.username, self.balance)

        self.game_active = False
        self._set_controls_enabled(True)
        self.start_button.configure(state=tk.NORMAL)
        self.update_display()

    # ------------------------------------------------------------------
    # Display / closing
    # ------------------------------------------------------------------

    def update_display(self) -> None:
        payout = self.calculate_payout(self.target_number, self.bet_type)
        potential = self.current_bet * payout

        self.balance_var.set(f"${self.balance:,.2f}")
        self.bet_var.set(f"${self.current_bet:,.2f}")
        self.last_win_var.set(f"${self.last_win:,.2f}")
        self.odds_var.set(f"{payout:.2f}×")
        self.win_var.set(f"${potential:,.2f}")
        self.target_var.set(str(self.target_number))
        self.direction_var.set("高于" if self.bet_type == "above" else "低于")

        if self.bet_type == "above":
            self.range_var.set(f"高于 {self.target_number} 即中奖")
        else:
            self.range_var.set(f"低于 {self.target_number} 即中奖")

        self._refresh_direction_buttons()
        self.draw_game()
        self.draw_history()

    def on_closing(self) -> None:
        self.animation_running = False
        self.game_active = False

        for job_id in list(self.after_jobs):
            try:
                self.root.after_cancel(job_id)
            except tk.TclError:
                pass
        self.after_jobs.clear()

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
                "EmbeddedGamePage is unavailable. Place lucky_num.py inside the "
                "Small_Games package or make small_games.py importable."
            )
        page = EmbeddedGamePage(
            parent,
            title="幸运数字",
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        page.set_requested_size(1150, 750)
        game = DiceGame(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = DiceGame(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    final_balance = main(10000.0, "test_user")
    print(f"Final balance: {final_balance:.2f}")