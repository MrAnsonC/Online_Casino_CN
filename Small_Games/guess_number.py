"""Guess Number — ChickenCrossing-style warm fixed HMI.

Original gameplay retained:
- One target number is sampled uniformly from 1..100 when a round starts.
- The stake is deducted once at round start.
- Before each round the player selects 5, 6, or 7 guesses.
- A wrong guess narrows the valid range; it does not charge another stake.
- Five-chance original total-return multipliers are retained exactly.
- Six/seven-chance modes use lower chance-dependent payout tables.
- The active stake remains selected after a round, matching the original flow.

The visual layer follows ChickenCrossing_tk.py's fixed 1150x750 warm HMI and
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
import os
import random
import sys
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


VERSION = "GuessNumber-ChickenStyle-R2"


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

    RANGE_ACTIVE = "#AEC6AF"
    RANGE_OUT = "#C9B6B1"
    RANGE_MARK = "#D5B85D"
    RANGE_BG = "#D5D0C7"
    ATTEMPT_DONE = "#C8D4C4"
    ATTEMPT_ACTIVE = "#BCD0D9"
    ATTEMPT_FUTURE = "#D8D2C9"

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

ODDS_TABLES = {
    5: (196.00, 48.10, 14.24, 3.80, 1.85),
    6: (163.33, 40.08, 11.87, 3.17, 1.54, 1.25),
    7: (140.00, 34.36, 10.17, 2.71, 1.32, 1.15, 1.05),
}


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
            master, width=width, height=height,
            bg=Theme.PANEL, bd=0, highlightthickness=0,
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

        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.draw()

    @staticmethod
    def _shade(hex_color: str, factor: float) -> str:
        rgb = [int(hex_color[i:i+2], 16) for i in (1, 3, 5)]
        rgb = [max(0, min(255, round(v * factor))) for v in rgb]
        return "#%02x%02x%02x" % tuple(rgb)

    def draw(self) -> None:
        self.delete("all")
        offset = 3 if self._pressed else 0
        outer = self._shade(self.chip_color, 0.68)
        inner = self._shade(self.chip_color, 0.86)
        outline = Theme.TEXT if self._hovered else outer
        width = 3 if self._hovered else 2

        self.create_oval(6, 7, self.control_width - 5, self.control_height - 1,
                         fill="#8E877E", outline="")
        self.create_oval(5, 3 + offset, self.control_width - 6,
                         self.control_height - 5 + offset,
                         fill=outer, outline=outline, width=width)
        self.create_oval(9, 7 + offset, self.control_width - 10,
                         self.control_height - 9 + offset,
                         fill=self.chip_color, outline=inner, width=2)
        self.create_text(
            self.control_width / 2,
            (self.control_height - 2) / 2 + offset,
            text=self.label,
            fill=self.text_color,
            font=(Theme.FONT, 10 if len(self.label) <= 4 else 9, "bold"),
        )

        if self._state == tk.DISABLED:
            self.create_oval(
                5, 3 + offset, self.control_width - 6,
                self.control_height - 5 + offset,
                fill="#C9C2B8", outline=Theme.BORDER_SOFT,
                width=1, stipple="gray50",
            )

    def _enter(self, _event) -> None:
        if self._state != tk.DISABLED:
            self._hovered = True
            self.draw()

    def _leave(self, _event) -> None:
        self._hovered = False
        self._pressed = False
        self.draw()

    def _press(self, _event) -> None:
        if self._state != tk.DISABLED:
            self._pressed = True
            self.draw()

    def _release(self, event) -> None:
        if self._state == tk.DISABLED:
            return
        pressed = self._pressed
        self._pressed = False
        if pressed and 0 <= event.x < self.control_width and 0 <= event.y < self.control_height:
            self.command(self.amount)
        self.draw()

    def set_enabled(self, enabled: bool) -> None:
        self._state = tk.NORMAL if enabled else tk.DISABLED
        self.configure(cursor="hand2" if enabled else "")
        if not enabled:
            self._hovered = False
            self._pressed = False
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
            master, width=width, height=height,
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


class GuessNumberGame:
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

    def __init__(self, root, initial_balance: float, username: str):
        self.root = root
        self._configure_root()

        self.balance = float(initial_balance)
        self.username = username
        self.current_bet = 0.0
        self.target_number = 0
        self.min_guess = 1
        self.max_guess = 100
        self.attempt = 0
        self.max_attempts = 5
        self.reveal_target = False
        self.game_active = False
        self.last_win = 0.0
        self.history: list[int] = []
        self.last_result_text = "选择下注金额后开始游戏"

        self.balance_var = tk.StringVar()
        self.bet_var = tk.StringVar()
        self.last_win_var = tk.StringVar()
        self.range_var = tk.StringVar()
        self.attempt_var = tk.StringVar()
        self.odds_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.guess_var = tk.StringVar()
        self.chance_var = tk.StringVar(value="5 次机会")

        self.chip_buttons: list[ChipButton] = []
        self.chance_buttons: dict[int, ModernButton] = {}
        self.odds_table_labels: list[tk.Label] = []

        self.create_widgets()
        self.update_display()

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("猜数字游戏")
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
            master, width=width, height=height,
            bg=Theme.PANEL, highlightthickness=1,
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
        icon.create_text(24, 24, text="?", fill=Theme.ACCENT, font=(Theme.FONT, 21, "bold"))

        tk.Label(
            header, text="GUESS NUMBER",
            bg=Theme.PANEL, fg=Theme.TEXT,
            font=(Theme.FONT, 18, "bold"), anchor=tk.W,
        ).place(x=74, y=10, width=340, height=27)
        tk.Label(
            header, text="猜数字 · 5 / 6 / 7 次机会",
            bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 11, "bold"), anchor=tk.W,
        ).place(x=74, y=39, width=280, height=20)

        balance_box = tk.Frame(
            header, width=206, height=46,
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
            panel, textvariable=self.attempt_var,
            bg=Theme.PANEL, fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 15, "bold"), anchor=tk.W,
        ).place(x=16, y=10, width=240, height=28)

        tk.Label(
            panel, textvariable=self.odds_var,
            bg=Theme.ACCENT_SOFT, fg=Theme.ACCENT,
            font=(Theme.FONT, 12, "bold"), anchor=tk.CENTER,
        ).place(x=590, y=10, width=140, height=28)

        self.game_canvas = tk.Canvas(
            panel, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT,
            bg=Theme.CANVAS_BG, bd=0, highlightthickness=0,
        )
        self.game_canvas.place(x=1, y=46, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT)

        # Real Entry/Button widgets sit inside the left panel while the Canvas
        # supplies the instrumentation/background.
        self.guess_entry = tk.Entry(
            panel,
            textvariable=self.guess_var,
            font=(Theme.FONT, 24, "bold"),
            justify=tk.CENTER,
            bg="#F4F0E8",
            fg=Theme.TEXT,
            insertbackground=Theme.TEXT,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=2,
            highlightbackground=Theme.BORDER,
            highlightcolor=Theme.ACCENT,
        )
        self.guess_entry.place(x=226, y=294, width=190, height=58)
        self.guess_entry.bind("<Return>", lambda _event: self.make_guess())

        self.submit_button = ModernButton(
            panel, text="提交猜测",
            command=self.make_guess,
            background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.submit_button.place(x=428, y=294, width=150, height=58)

        self.draw_game_screen()

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

        chance = self._card(sidebar, width=348, height=82)
        chance.place(x=0, y=189, width=348, height=82)
        self._section_title(chance.inner, "选择机会次数").place(x=0, y=0, width=130, height=20)

        for index, count in enumerate((5, 6, 7)):
            btn = ModernButton(
                chance.inner,
                text=f"{count} 次",
                command=lambda value=count: self.set_max_attempts(value),
                background=Theme.PANEL_ALT,
                hover_background=Theme.PANEL_HOVER,
                foreground=Theme.TEXT,
                font_size=10,
                bold=True,
            )
            btn.place(x=index * 107, y=28, width=100, height=32)
            self.chance_buttons[count] = btn

        odds = self._card(sidebar, width=348, height=98)
        odds.place(x=0, y=281, width=348, height=94)
        self._section_title(odds.inner, "机会赔率").place(x=0, y=0, width=100, height=20)

        self.odds_table_frame = tk.Frame(
            odds.inner,
            bg=Theme.PANEL,
            bd=2,
            relief=tk.SOLID,
        )
        self.odds_table_frame.place(x=0, y=26, width=322, height=48)

        actions = self._card(sidebar, width=348, height=92)
        actions.place(x=0, y=385, width=348, height=92)

        self.reset_bet_button = ModernButton(
            actions.inner, text="清空下注",
            command=self.reset_bet,
            background=Theme.RED,
            hover_background=Theme.RED_HOVER,
            foreground="#FFFFFF",
            font_size=11,
            bold=True,
        )
        self.reset_bet_button.place(x=0, y=0, width=322, height=34)

        self.start_button = ModernButton(
            actions.inner, text="开始游戏",
            command=self.start_game,
            background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.start_button.place(x=0, y=42, width=322, height=34)

        status = self._card(sidebar, width=348, height=66, padding=9)
        status.place(x=0, y=487, width=348, height=66)
        tk.Label(
            status.inner, text="状态",
            bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9), anchor=tk.W,
        ).place(x=0, y=0, width=60, height=18)
        tk.Label(
            status.inner, textvariable=self.status_var,
            bg=Theme.PANEL, fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 9, "bold"), anchor=tk.W,
            justify=tk.LEFT, wraplength=322,
        ).place(x=0, y=20, width=322, height=26)

        rules = self._card(sidebar, width=348, height=67, padding=9)
        rules.place(x=0, y=563, width=348, height=67)
        tk.Label(
            rules.inner,
            text="规则：1–100 随机答案；开局前可选 5/6/7 次机会。猜错缩小范围，越早猜中倍率越高。",
            bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8),
            anchor=tk.W, justify=tk.LEFT, wraplength=322,
        ).place(x=0, y=0, width=322, height=49)

    @property
    def active_odds(self) -> tuple[float, ...]:
        return ODDS_TABLES[self.max_attempts]

    def set_max_attempts(self, count: int) -> None:
        if self.game_active or count not in ODDS_TABLES:
            return
        self.max_attempts = int(count)
        self.reveal_target = False
        self.attempt = 0
        self.history = []
        self.last_result_text = f"已选择 {count} 次机会"
        self.update_display()

    def _refresh_chance_buttons(self) -> None:
        for count, button in self.chance_buttons.items():
            selected = count == self.max_attempts
            if self.game_active:
                button.configure(
                    state=tk.DISABLED,
                    bg=Theme.ACCENT if selected else Theme.PANEL_ALT,
                    fg="#FFFFFF" if selected else Theme.TEXT,
                    activebackground=Theme.ACCENT if selected else Theme.PANEL_ALT,
                )
            else:
                button.configure(
                    state=tk.DISABLED if selected else tk.NORMAL,
                    bg=Theme.ACCENT if selected else Theme.PANEL_ALT,
                    fg="#FFFFFF" if selected else Theme.TEXT,
                    activebackground=Theme.ACCENT_HOVER if selected else Theme.PANEL_HOVER,
                    activeforeground="#FFFFFF" if selected else Theme.TEXT,
                )

    def rebuild_odds_table(self) -> None:
        # 删除旧表格内容
        for widget in self.odds_table_frame.winfo_children():
            widget.destroy()

        # 重点：
        # grid 的 columnconfigure 不会随着 widget.destroy() 自动消失。
        # 因此每次重建前，先把最多 7 列全部恢复成无宽度状态。
        for col in range(7):
            self.odds_table_frame.columnconfigure(
                col,
                weight=0,
                minsize=0,
                uniform="",
            )

        odds = self.active_odds
        count = len(odds)

        # 根据列数微调字号
        if count == 5:
            title_font = 9
            odds_font = 10
        elif count == 6:
            title_font = 8
            odds_font = 9
        else:  # 7
            title_font = 8
            odds_font = 8

        for col in range(count):
            title = tk.Label(
                self.odds_table_frame,
                text=f"第{col + 1}次",
                font=(Theme.FONT_CJK, title_font, "bold"),
                bg=Theme.PANEL_ALT,
                fg=Theme.TEXT,
                borderwidth=1,
                relief=tk.SOLID,
                padx=1,
                pady=2,
            )
            title.grid(
                row=0,
                column=col,
                sticky="nsew",
                padx=0,
                pady=0,
            )

            value = tk.Label(
                self.odds_table_frame,
                text=f"{odds[col]:.2f}×",
                font=(Theme.FONT, odds_font, "bold"),
                bg=(
                    Theme.ACCENT_SOFT
                    if self.game_active and col == self.attempt
                    else Theme.PANEL
                ),
                fg=Theme.ACCENT,
                borderwidth=1,
                relief=tk.SOLID,
                padx=1,
                pady=2,
            )
            value.grid(
                row=1,
                column=col,
                sticky="nsew",
                padx=0,
                pady=0,
            )

            # 只让当前模式真正存在的列平均分配宽度
            self.odds_table_frame.columnconfigure(
                col,
                weight=1,
                minsize=0,
                uniform="odds",
            )

        self.odds_table_frame.rowconfigure(0, weight=1)
        self.odds_table_frame.rowconfigure(1, weight=1)

    # ------------------------------------------------------------------
    # Betting and game flow
    # ------------------------------------------------------------------

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
            self.status_var.set("下注已更新")
            self.update_display()
        else:
            messagebox.showwarning("余额不足", "账户余额不足以加入这个筹码。", parent=self.root)

    def reset_bet(self) -> None:
        if self.game_active:
            return
        self.current_bet = 0.0
        self.status_var.set("下注已清空")
        self.update_display()

    def start_game(self) -> None:
        if self.game_active:
            return
        if self.current_bet <= 0:
            messagebox.showwarning("尚未下注", "请先选择下注金额。", parent=self.root)
            return
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "账户余额不足。", parent=self.root)
            return

        self.balance -= self.current_bet
        update_balance_in_json(self.username, self.balance)

        self.target_number = random.randint(1, 100)
        self.min_guess = 1
        self.max_guess = 100
        self.attempt = 0
        self.reveal_target = False
        self.game_active = True
        self.history = []
        self.guess_var.set("")
        self.last_result_text = "游戏开始 · 输入 1–100 之间的数字"

        self._set_game_controls(True)
        self.update_display()
        self.guess_entry.focus_set()

    def make_guess(self) -> None:
        if not self.game_active:
            return

        try:
            guess = int(self.guess_var.get())
        except ValueError:
            messagebox.showerror("输入错误", "请输入有效的整数。", parent=self.root)
            return

        if guess < self.min_guess or guess > self.max_guess:
            messagebox.showerror(
                "超出范围",
                f"请输入 {self.min_guess}–{self.max_guess} 之间的数字。",
                parent=self.root,
            )
            return

        self.history.append(guess)

        if guess == self.target_number:
            self.win_game()
            return

        if guess < self.target_number:
            self.min_guess = guess + 1
            hint = f"{guess} 太小"
        else:
            self.max_guess = guess - 1
            hint = f"{guess} 太大"

        self.attempt += 1

        if self.attempt >= self.max_attempts:
            self.lose_game()
            return

        self.guess_var.set("")
        self.last_result_text = f"{hint} · 新范围 {self.min_guess}–{self.max_guess}"
        self.update_display()
        self.guess_entry.focus_set()

    def win_game(self) -> None:
        win_amount = self.current_bet * self.active_odds[self.attempt]
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        self.reveal_target = True
        update_balance_in_json(self.username, self.balance)

        self.last_result_text = (
            f"猜中 {self.target_number} · 第 {self.attempt + 1} 次 · "
            f"返还 ${win_amount:,.2f}"
        )
        self._set_game_controls(False)
        self.update_display()

    def lose_game(self) -> None:
        self.last_win = 0.0
        self.game_active = False
        self.reveal_target = True
        self.last_result_text = (
            f"{self.max_attempts} 次机会已用完 · 正确答案 {self.target_number}"
        )
        self._set_game_controls(False)
        self.update_display()

    def _set_game_controls(self, active: bool) -> None:
        # active=True means a round is in progress.
        enabled = not active
        for chip in self.chip_buttons:
            chip.set_enabled(enabled)

        self.reset_bet_button.configure(state=tk.NORMAL if enabled else tk.DISABLED)
        self.start_button.configure(state=tk.NORMAL if enabled else tk.DISABLED)
        self._refresh_chance_buttons()

        entry_state = tk.NORMAL if active else tk.DISABLED
        self.guess_entry.configure(state=entry_state)
        self.submit_button.configure(state=entry_state)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    @staticmethod
    def _range_to_x(value: int, x1: float, x2: float) -> float:
        return x1 + (max(1, min(100, value)) - 1) / 99 * (x2 - x1)

    def draw_game_screen(self) -> None:
        c = self.game_canvas
        c.delete("all")
        w = self.CANVAS_WIDTH
        h = self.CANVAS_HEIGHT

        c.create_rectangle(0, 0, w, h, fill=Theme.CANVAS_BG, outline="")

        # Current valid range card.
        c.create_rectangle(
            35, 25, w - 35, 122,
            fill=Theme.PANEL_ALT, outline=Theme.BORDER_SOFT, width=1,
        )
        c.create_text(
            53, 46, text="当前有效范围",
            fill=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9, "bold"), anchor=tk.W,
        )

        range_text = (
            f"{self.min_guess}  —  {self.max_guess}"
            if self.game_active else "1  —  100"
        )
        c.create_text(
            53, 82, text=range_text,
            fill=Theme.ACCENT,
            font=(Theme.FONT, 26, "bold"), anchor=tk.W,
        )

        remaining = max(0, self.max_attempts - self.attempt)
        c.create_text(
            w - 53, 46, text="剩余机会",
            fill=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9, "bold"), anchor=tk.E,
        )
        c.create_text(
            w - 53, 82,
            text=str(remaining if self.game_active else self.max_attempts),
            fill=Theme.AMBER,
            font=(Theme.FONT, 27, "bold"), anchor=tk.E,
        )

        # The final winning number is revealed only after every selected
        # opportunity has been consumed without a successful guess.
        if self.reveal_target:
            c.create_text(
                w / 2, 46, text="最终中奖号码",
                fill=Theme.TEXT_MUTED,
                font=(Theme.FONT_CJK, 9, "bold"), anchor=tk.CENTER,
            )
            c.create_text(
                w / 2, 82,
                text=str(self.target_number),
                fill=Theme.RED,
                font=(Theme.FONT, 27, "bold"), anchor=tk.CENTER,
            )

        # Range instrument.
        bar_x1, bar_x2 = 62, w - 62
        bar_y1, bar_y2 = 165, 218

        c.create_rectangle(
            bar_x1, bar_y1, bar_x2, bar_y2,
            fill=Theme.RANGE_OUT, outline=Theme.BORDER, width=1,
        )

        if self.game_active:
            active_x1 = self._range_to_x(self.min_guess, bar_x1, bar_x2)
            active_x2 = self._range_to_x(self.max_guess, bar_x1, bar_x2)
        else:
            active_x1, active_x2 = bar_x1, bar_x2

        c.create_rectangle(
            active_x1, bar_y1, active_x2, bar_y2,
            fill=Theme.RANGE_ACTIVE, outline="",
        )

        # Scale.
        for number in (1, 25, 50, 75, 100):
            x = self._range_to_x(number, bar_x1, bar_x2)
            c.create_line(x, bar_y2 + 6, x, bar_y2 + 12, fill=Theme.TEXT_DIM, width=1)
            c.create_text(
                x, bar_y2 + 25,
                text=str(number), fill=Theme.TEXT_MUTED,
                font=(Theme.FONT, 8, "bold"),
            )

        # Previous guesses as markers.
        for index, guess in enumerate(self.history):
            x = self._range_to_x(guess, bar_x1, bar_x2)
            c.create_line(
                x, bar_y1 - 12, x, bar_y2 + 2,
                fill=Theme.RANGE_MARK, width=3,
            )
            c.create_text(
                x, bar_y1 - 22,
                text=str(guess), fill=Theme.AMBER,
                font=(Theme.FONT, 8, "bold"),
            )

        c.create_text(
            w / 2, 263,
            text=(
                "输入当前范围内的整数"
                if self.game_active
                else "开始游戏后输入你的猜测"
            ),
            fill=Theme.TEXT,
            font=(Theme.FONT_CJK, 12, "bold"),
        )

        # Entry and submit widget area backdrop.
        c.create_rectangle(
            208, 240, 596, 324,
            fill=Theme.PANEL, outline=Theme.BORDER_SOFT, width=1,
        )

        # Attempt timeline adapts to 5 / 6 / 7 selected opportunities.
        timeline_y = 380
        left = 54
        total_w = w - 108
        gap = 7
        count = self.max_attempts
        cell_w = (total_w - gap * (count - 1)) / count
        odds = self.active_odds

        for index in range(count):
            x1 = left + index * (cell_w + gap)
            x2 = x1 + cell_w

            if index < len(self.history):
                fill = Theme.ATTEMPT_DONE
                border = Theme.GREEN
            elif self.game_active and index == self.attempt:
                fill = Theme.ATTEMPT_ACTIVE
                border = Theme.ACCENT
            else:
                fill = Theme.ATTEMPT_FUTURE
                border = Theme.BORDER_SOFT

            c.create_rectangle(
                x1, timeline_y, x2, timeline_y + 78,
                fill=fill, outline=border,
                width=2 if index == self.attempt and self.game_active else 1,
            )
            c.create_text(
                (x1 + x2) / 2, timeline_y + 17,
                text=f"第{index + 1}次",
                fill=Theme.TEXT_MUTED,
                font=(Theme.FONT_CJK, 7 if count >= 7 else 8, "bold"),
            )
            c.create_text(
                (x1 + x2) / 2, timeline_y + 42,
                text=f"{odds[index]:.2f}×",
                fill=Theme.ACCENT,
                font=(Theme.FONT, 9 if count >= 7 else 11, "bold"),
            )

            guess_text = str(self.history[index]) if index < len(self.history) else "--"
            c.create_text(
                (x1 + x2) / 2, timeline_y + 62,
                text=guess_text,
                fill=Theme.TEXT if guess_text != "--" else Theme.TEXT_DIM,
                font=(Theme.FONT, 9, "bold"),
            )

        c.create_text(
            53, 500,
            text=self.last_result_text,
            fill=Theme.TEXT if self.game_active else (
                Theme.GREEN if self.last_win > 0 else Theme.TEXT_MUTED
            ),
            font=(Theme.FONT_CJK, 10, "bold"),
            anchor=tk.W,
        )

    def draw_odds(self) -> None:
        self.rebuild_odds_table()


    def update_display(self) -> None:
        self.balance_var.set(f"${self.balance:,.2f}")
        self.bet_var.set(f"${self.current_bet:,.2f}")
        self.last_win_var.set(f"${self.last_win:,.2f}")

        if self.game_active:
            self.range_var.set(f"{self.min_guess}–{self.max_guess}")
            self.attempt_var.set(f"第 {self.attempt + 1} 次猜测")
            self.odds_var.set(f"{self.active_odds[self.attempt]:.2f}×")
        else:
            self.range_var.set("1–100")
            self.attempt_var.set("等待开始")
            self.odds_var.set(f"{self.max_attempts} 次机会")

        self.chance_var.set(f"{self.max_attempts} 次机会")
        self.status_var.set(self.last_result_text)
        self._refresh_chance_buttons()
        self.draw_game_screen()
        self.draw_odds()

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
                "EmbeddedGamePage is unavailable. Place guess_number.py inside "
                "the Small_Games package or make small_games.py importable."
            )
        page = EmbeddedGamePage(
            parent,
            title="猜数字游戏",
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        page.set_requested_size(1150, 750)
        game = GuessNumberGame(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = GuessNumberGame(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    final_balance = main(1000.0, "test_user")
    print(f"Final balance: {final_balance:.2f}")