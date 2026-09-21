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
    from small_games import EmbeddedGamePage


VERSION = "Keno-ChickenStyle-R3-odds-footer-chip-fit"


# ===== 在 Theme 里面新增这两个颜色 =====

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

    WIN = "#A9C4A5"
    MISS = "#D7A6A0"
    SELECTED = "#B7CCD5"
    DEFAULT_CELL = "#DDD7CE"

    # 实时赔率表
    ODDS_PROGRESS = "#B9DDEA"   # 已经过的命中格：浅蓝色
    ODDS_CURRENT = "#D9B75B"    # 当前命中格：金色

    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )
    FONT_EMOJI = "Segoe UI Emoji"

# Original payout tables are intentionally preserved.
odds_easy = {
    1: [0.70, 1.85],
    2: [0, 2, 3.80],
    3: [0, 1.10, 1.38, 26],
    4: [0, 0, 2.2, 7.9, 90],
    5: [0, 0, 1.5, 4.2, 13, 300],
    6: [0, 0, 1.1, 2, 6.2, 100, 700],
    7: [0, 0, 1.1, 1.6, 3.5, 15, 225, 700],
    8: [0, 0, 1.1, 1.5, 2, 5.5, 39, 100, 800],
    9: [0, 0, 1.1, 1.3, 1.7, 2.5, 7.5, 50, 250, 1000],
    10: [0, 0, 1.1, 1.2, 1.3, 1.8, 3.5, 13, 50, 250, 1000],
}

odds_medium = {
    1: [0.4, 2.75],
    2: [0, 1.8, 5.1],
    3: [0, 0, 2.8, 50],
    4: [0, 0, 1.7, 10, 100],
    5: [0, 0, 1.4, 4, 14, 390],
    6: [0, 0, 0, 3, 9, 180, 710],
    7: [0, 0, 0, 2, 7, 30, 400, 800],
    8: [0, 0, 0, 2, 4, 11, 67, 400, 900],
    9: [0, 0, 0, 2, 2.5, 5, 15, 100, 500, 1000],
    10: [0, 0, 0, 1.6, 2, 4, 7, 26, 100, 500, 1000],
}

odds_difficult = {
    1: [0, 3.96],
    2: [0, 0, 17.10],
    3: [0, 0, 0, 81.50],
    4: [0, 0, 0, 10, 259],
    5: [0, 0, 0, 4.50, 48, 450],
    6: [0, 0, 0, 0, 11, 350, 710],
    7: [0, 0, 0, 0, 7, 90, 400, 800],
    8: [0, 0, 0, 0, 5, 20, 270, 600, 900],
    9: [0, 0, 0, 0, 4, 11, 56, 500, 800, 1000],
    10: [0, 0, 0, 0, 3.5, 8, 13, 63, 500, 800, 1000],
}

ODDS_TABLES = {"1": odds_easy, "2": odds_medium, "3": odds_difficult}
DIFFICULTIES = (("简单", "1"), ("中等", "2"), ("地狱", "3"))
CHIP_CONFIGS = (
    ("$5", "5", "#C75252", "white"),
    ("$25", "25", "#72A764", "black"),
    ("$100", "100", "#30343B", "white"),
    ("$500", "500", "#D788B8", "black"),
    ("$1K", "1000", "#F2EFE9", "black"),
)


def get_data_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../A_Tools/Account/saving_data.json")


def load_user_data() -> list:
    try:
        with open(get_data_file_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_user_data(users: list) -> None:
    try:
        with open(get_data_file_path(), "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=4)
    except OSError:
        pass


def update_balance_in_json(username: str, new_balance: float) -> None:
    users = load_user_data()
    for user in users:
        if user.get("user_name") == username:
            user["cash"] = f"{new_balance:.2f}"
            save_user_data(users)
            return


class ModernButton(tk.Button):
    def __init__(self, master, *, text: str, command=None, background=Theme.PANEL_HOVER,
                 hover_background=Theme.BORDER, foreground=Theme.TEXT, font_size=12,
                 bold=False, **kwargs):
        self.normal_background = background
        self.hover_background = hover_background
        self.normal_foreground = foreground
        super().__init__(
            master, text=text, command=command, bg=background, fg=foreground,
            activebackground=hover_background, activeforeground=foreground,
            disabledforeground=Theme.TEXT_DIM,
            font=(Theme.FONT_CJK, font_size, "bold" if bold else "normal"),
            relief=tk.FLAT, bd=0, highlightthickness=0, cursor="hand2", **kwargs
        )
        self.bind("<Enter>", self._enter, add="+")
        self.bind("<Leave>", self._leave, add="+")

    def _enter(self, _event):
        if str(self.cget("state")) != tk.DISABLED:
            super().configure(bg=self.hover_background)

    def _leave(self, _event):
        super().configure(bg=self.normal_background)

    def set_colors(self, background: str, hover_background: Optional[str] = None,
                   foreground: Optional[str] = None):
        self.normal_background = background
        self.hover_background = hover_background or background
        if foreground is not None:
            self.normal_foreground = foreground
        super().configure(bg=self.normal_background, fg=self.normal_foreground,
                          activebackground=self.hover_background,
                          activeforeground=self.normal_foreground)


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
    def __init__(self, master, label: str, variable: tk.StringVar, accent: str,
                 *, width: int, height: int):
        super().__init__(master, width=width, height=height, bg=Theme.PANEL_ALT,
                         highlightthickness=1, highlightbackground=Theme.BORDER_SOFT)
        self.pack_propagate(False)
        tk.Label(self, text=label, bg=Theme.PANEL_ALT, fg=Theme.TEXT_MUTED,
                 font=(Theme.FONT_CJK, 9), anchor=tk.W).place(x=12, y=8, width=width-24, height=18)
        tk.Label(self, textvariable=variable, bg=Theme.PANEL_ALT, fg=accent,
                 font=(Theme.FONT, 15, "bold"), anchor=tk.W).place(x=12, y=29, width=width-24, height=28)


class NumberCell(tk.Canvas):
    WIDTH = 62
    HEIGHT = 61

    def __init__(self, master, number: int, command: Callable[[int], None]):
        super().__init__(master, width=self.WIDTH, height=self.HEIGHT, bg=Theme.CANVAS_BG,
                         bd=0, highlightthickness=0, cursor="hand2")
        self.number = number
        self.command = command
        self.state_name = "default"
        self.enabled = True
        self.hovered = False
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._click)
        self.draw()

    def set_state(self, state_name: str):
        self.state_name = state_name
        self.draw()

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "")
        self.draw()

    def _enter(self, _):
        if self.enabled:
            self.hovered = True; self.draw()
    def _leave(self, _):
        self.hovered = False; self.draw()
    def _click(self, _):
        if self.enabled:
            self.command(self.number)

    def draw(self):
        self.delete("all")
        fills = {
            "default": Theme.DEFAULT_CELL,
            "selected": Theme.SELECTED,
            "match": Theme.WIN,
            "miss": Theme.MISS,
        }
        borders = {
            "default": Theme.BORDER_SOFT,
            "selected": Theme.ACCENT,
            "match": Theme.GREEN,
            "miss": Theme.RED,
        }
        fill = fills.get(self.state_name, Theme.DEFAULT_CELL)
        border = borders.get(self.state_name, Theme.BORDER_SOFT)
        if self.hovered and self.state_name == "default":
            fill = Theme.PANEL_HOVER
            border = Theme.ACCENT
        self.create_rectangle(3, 4, self.WIDTH-3, self.HEIGHT-4,
                              fill="#AAA39A", outline="")
        self.create_rectangle(2, 2, self.WIDTH-4, self.HEIGHT-7,
                              fill=fill, outline=border, width=2)
        label = str(self.number)
        self.create_text(self.WIDTH/2-1, 25, text=label,
                         fill=Theme.TEXT, font=(Theme.FONT, 14, "bold"))
        if self.state_name == "selected":
            self.create_text(self.WIDTH/2-1, 44, text="已选", fill=Theme.ACCENT,
                             font=(Theme.FONT_CJK, 7, "bold"))
        elif self.state_name == "match":
            self.create_text(self.WIDTH/2-1, 44, text="命中", fill=Theme.GREEN,
                             font=(Theme.FONT_CJK, 7, "bold"))
        elif self.state_name == "miss":
            self.create_text(self.WIDTH/2-1, 44, text="开奖", fill=Theme.RED,
                             font=(Theme.FONT_CJK, 7, "bold"))
        if not self.enabled:
            # Locked during the draw, but keep the cell fully opaque.
            # The previous translucent stipple overlay made all 50 buttons look faded.
            self.create_rectangle(2, 2, self.WIDTH-4, self.HEIGHT-7,
                                  fill="", outline=Theme.BORDER, width=2)


class KenoGame:
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

    def __init__(self, root, initial_balance, username):
        self.root = root
        self._configure_root()
        self.balance = float(initial_balance)
        self.username = username
        self.difficulty = "1"
        self.user_numbers: list[int] = []
        self.winning_numbers: list[int] = []
        self.game_active = False
        self.last_win = 0.0
        self.current_bet = 0.0
        self.matches = 0
        self.multiplier = 0.0
        self.draw_index = 0
        self._unlock_job = None
        self.chip_buttons: list[ChipButton] = []
        self.difficulty_buttons: list[ModernButton] = []
        self.number_buttons: list[NumberCell] = []
        self.create_widgets()
        self.update_display()

    def _configure_root(self):
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("基诺游戏")
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
    def _card(master, *, width: int, height: int, padding: int = 12):
        outer = tk.Frame(master, width=width, height=height, bg=Theme.PANEL,
                         highlightthickness=1, highlightbackground=Theme.BORDER_SOFT)
        outer.pack_propagate(False); outer.grid_propagate(False)
        inner_w = max(1, width - 2 * (padding + 1))
        inner_h = max(1, height - 2 * (padding + 1))
        inner = tk.Frame(outer, width=inner_w, height=inner_h, bg=Theme.PANEL)
        inner.place(x=padding+1, y=padding+1, width=inner_w, height=inner_h)
        inner.pack_propagate(False); inner.grid_propagate(False)
        outer.content = inner
        return outer

    def create_widgets(self):
        self.balance_var = tk.StringVar(value=f"${self.balance:.2f}")
        self.bet_var = tk.StringVar(value="$0.00")
        self.last_win_var = tk.StringVar(value="$0.00")
        self.info_var = tk.StringVar(value="选择 1–10 个号码，再设置下注与难度。")
        self.selection_var = tk.StringVar(value="已选择 0 / 10")
        self.selection_count_var = tk.StringVar(value="0 个")
        self.draw_progress_var = tk.StringVar(value="开奖 0 / 10")
        self.matches_var = tk.StringVar(value="命中 0")
        self.multiplier_var = tk.StringVar(value="0.00×")
        self.difficulty_text_var = tk.StringVar(value="简单")

        shell = tk.Frame(self.root, width=self.SHELL_WIDTH, height=self.SHELL_HEIGHT, bg=Theme.APP_BG)
        shell.pack(padx=20, pady=18)
        shell.pack_propagate(False)
        self._build_header(shell)
        body = tk.Frame(shell, width=self.SHELL_WIDTH, height=self.BODY_HEIGHT, bg=Theme.APP_BG)
        body.place(x=0, y=self.BODY_TOP, width=self.SHELL_WIDTH, height=self.BODY_HEIGHT)
        body.pack_propagate(False)
        self._build_game_panel(body)
        self._build_control_panel(body)

    def _build_header(self, master):
        header = tk.Frame(master, width=self.SHELL_WIDTH, height=self.HEADER_HEIGHT, bg=Theme.APP_BG)
        header.place(x=0, y=0, width=self.SHELL_WIDTH, height=self.HEADER_HEIGHT)
        tk.Label(header, text="⑩", bg=Theme.APP_BG, fg=Theme.AMBER,
                 font=(Theme.FONT, 25, "bold"), anchor=tk.CENTER).place(x=0, y=7, width=42, height=44)
        tk.Label(header, text="KENO", bg=Theme.APP_BG, fg=Theme.TEXT,
                 font=(Theme.FONT, 20, "bold"), anchor=tk.W).place(x=52, y=4, width=430, height=31)
        tk.Label(header, text="基诺游戏", bg=Theme.APP_BG, fg=Theme.TEXT_MUTED,
                 font=(Theme.FONT_CJK, 10), anchor=tk.W).place(x=52, y=37, width=520, height=22)
        balance_box = tk.Frame(header, width=270, height=54, bg=Theme.PANEL,
                               highlightthickness=1, highlightbackground=Theme.BORDER)
        balance_box.place(x=840, y=8, width=270, height=54)
        self.balance_display_var = tk.StringVar(value=f"账户余额: {self.balance_var.get()}")
        self.balance_var.trace_add("write", lambda *_: self.balance_display_var.set(f"账户余额: {self.balance_var.get()}"))
        tk.Label(balance_box, textvariable=self.balance_display_var, bg=Theme.PANEL, fg=Theme.TEXT,
                 font=(Theme.FONT_CJK, 13, "bold"), anchor=tk.E).place(x=12, y=7, width=245, height=40)

    def _build_game_panel(self, master):
        panel = self._card(master, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT, padding=0)
        panel.place(x=0, y=0, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT)
        content = panel.content
        top = tk.Frame(content, width=746, height=74, bg=Theme.PANEL)
        top.place(x=0, y=0, width=746, height=74)
        tk.Label(top, textvariable=self.info_var, bg=Theme.PANEL, fg=Theme.TEXT,
                 font=(Theme.FONT_CJK, 17, "bold"), anchor=tk.W).place(x=18, y=12, width=520, height=30)
        tk.Label(top, textvariable=self.selection_var, bg=Theme.ACCENT_SOFT, fg=Theme.ACCENT,
                 font=(Theme.FONT_CJK, 9, "bold"), anchor=tk.CENTER).place(x=575, y=12, width=145, height=26)
        tk.Label(top, textvariable=self.draw_progress_var, bg=Theme.PANEL_ALT, fg=Theme.TEXT_MUTED,
                 font=(Theme.FONT_CJK, 8, "bold"), anchor=tk.CENTER).place(x=575, y=42, width=145, height=22)

        board = tk.Frame(content, width=746, height=554, bg=Theme.CANVAS_BG)
        board.place(x=0, y=74, width=746, height=554)
        tk.Label(board, text="当前50个号码", bg=Theme.CANVAS_BG, fg=Theme.TEXT,
                 font=(Theme.FONT_CJK, 10, "bold"), anchor=tk.W).place(x=28, y=10, width=180, height=22)
        tk.Label(board, text="浅蓝 = 已选　绿色 = 命中　红色 = 开出但未选", bg=Theme.CANVAS_BG,
                 fg=Theme.TEXT_MUTED, font=(Theme.FONT_CJK, 8), anchor=tk.E).place(x=340, y=10, width=378, height=22)

        # Number board starts directly below the section title.
        start_x, start_y = 39, 42
        gap_x, gap_y = 7, 6
        self.number_buttons = []
        for index in range(50):
            num = index + 1
            r, c = divmod(index, 10)
            cell = NumberCell(board, num, self.toggle_number)
            x = start_x + c * (NumberCell.WIDTH + gap_x)
            y = start_y + r * (NumberCell.HEIGHT + gap_y)
            cell.place(x=x, y=y, width=NumberCell.WIDTH, height=NumberCell.HEIGHT)
            self.number_buttons.append(cell)

        # Dedicated live payout table below the 50-number board.
        # It follows the current selection count and difficulty in real time.
        self.odds_table = tk.Frame(board, bg=Theme.PANEL_ALT, highlightthickness=1,
                                   highlightbackground=Theme.BORDER_SOFT)
        self.odds_table.place(x=28, y=410, width=690, height=120)
        self.odds_table_cells: list[tk.Label] = []
        self._refresh_odds_table()

    def _refresh_odds_table(self) -> None:
        if not hasattr(self, "odds_table"):
            return

        # 清除旧内容
        for child in self.odds_table.winfo_children():
            child.destroy()

        count = len(self.user_numbers)
        diff_name = {
            "1": "简单",
            "2": "中等",
            "3": "地狱",
        }[self.difficulty]

        # --------------------------------------------------
        # 标题
        # 全部文字统一 12
        # --------------------------------------------------
        tk.Label(
            self.odds_table,
            text="实时赔率表",
            bg=Theme.PANEL_ALT,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 12, "bold"),
            anchor=tk.W,
        ).place(
            x=12,
            y=5,
            width=170,
            height=30,
        )

        tk.Label(
            self.odds_table,
            text=f"{diff_name} · 已选 {count} 个号码",
            bg=Theme.PANEL_ALT,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 12, "bold"),
            anchor=tk.E,
        ).place(
            x=370,
            y=5,
            width=308,
            height=30,
        )

        # --------------------------------------------------
        # 尚未选择号码
        # --------------------------------------------------
        if count <= 0:
            tk.Label(
                self.odds_table,
                text="选择 1–10 个号码后显示对应赔率",
                bg=Theme.PANEL_ALT,
                fg=Theme.TEXT_DIM,
                font=(Theme.FONT_CJK, 12, "bold"),
                anchor=tk.CENTER,
            ).place(
                x=12,
                y=43,
                width=666,
                height=60,
            )
            return

        row = ODDS_TABLES[self.difficulty].get(count, [])
        columns = len(row)

        # ==================================================
        # 表格尺寸
        #
        # 所有格子完全紧贴：
        # gap = 0
        # padx = 0
        # pady = 0
        #
        # 使用整数边界计算，避免浮点 width 产生 1px 空隙
        # ==================================================
        grid_x = 12
        grid_y = 40

        grid_width = 666
        label_width = 58
        data_width = grid_width - label_width

        row_height = 32

        # --------------------------------------------------
        # 左边固定标题
        # --------------------------------------------------
        tk.Label(
            self.odds_table,
            text="命中",
            bg=Theme.PANEL_HOVER,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 12, "bold"),
            anchor=tk.CENTER,
            bd=0,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        ).place(
            x=grid_x,
            y=grid_y,
            width=label_width,
            height=row_height,
        )

        tk.Label(
            self.odds_table,
            text="赔率",
            bg=Theme.PANEL_HOVER,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 12, "bold"),
            anchor=tk.CENTER,
            bd=0,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        ).place(
            x=grid_x,
            y=grid_y + row_height,
            width=label_width,
            height=row_height,
        )

        # 是否已经开始开奖
        has_result = self.draw_index > 0

        # --------------------------------------------------
        # 每一个赔率格
        # --------------------------------------------------
        for hits, odds in enumerate(row):

            # 使用左右边界计算，确保相邻格子完全贴合
            left_edge = round(hits * data_width / columns)
            right_edge = round((hits + 1) * data_width / columns)

            cell_x = grid_x + label_width + left_edge
            cell_width = right_edge - left_edge

            # ==============================================
            # 格子颜色
            #
            # 假设当前命中 3 个：
            #
            # 0 → 浅蓝
            # 1 → 浅蓝
            # 2 → 浅蓝
            # 3 → 金色
            # 4+ → 普通
            # ==============================================
            if has_result and hits < self.matches:
                cell_bg = Theme.ODDS_PROGRESS
                hit_fg = Theme.TEXT
                odds_fg = Theme.TEXT

            elif has_result and hits == self.matches:
                cell_bg = Theme.ODDS_CURRENT
                hit_fg = Theme.TEXT
                odds_fg = Theme.TEXT

            else:
                cell_bg = Theme.PANEL
                hit_fg = Theme.TEXT

                if odds > 1:
                    odds_fg = Theme.GREEN
                elif odds > 0:
                    odds_fg = Theme.AMBER
                else:
                    odds_fg = Theme.TEXT_DIM

            # --------------------------------------------------
            # 命中数量
            # --------------------------------------------------
            tk.Label(
                self.odds_table,
                text=str(hits),
                bg=cell_bg,
                fg=hit_fg,
                font=(Theme.FONT_CJK, 12, "bold"),
                anchor=tk.CENTER,
                bd=0,
                highlightthickness=1,
                highlightbackground=Theme.BORDER_SOFT,
            ).place(
                x=cell_x,
                y=grid_y,
                width=cell_width,
                height=row_height,
            )

            # --------------------------------------------------
            # 对应赔率
            # --------------------------------------------------
            tk.Label(
                self.odds_table,
                text=f"{odds:g}×",
                bg=cell_bg,
                fg=odds_fg,
                font=(Theme.FONT_CJK, 12, "bold"),
                anchor=tk.CENTER,
                bd=0,
                highlightthickness=1,
                highlightbackground=Theme.BORDER_SOFT,
            ).place(
                x=cell_x,
                y=grid_y + row_height,
                width=cell_width,
                height=row_height,
            )

    def _build_control_panel(self, master):
        sidebar = tk.Frame(master, width=self.SIDEBAR_WIDTH, height=self.BODY_HEIGHT, bg=Theme.APP_BG)
        sidebar.place(x=self.GAME_PANEL_WIDTH + self.PANEL_GAP, y=0,
                      width=self.SIDEBAR_WIDTH, height=self.BODY_HEIGHT)
        MetricTile(sidebar, "当前下注", self.bet_var, Theme.CYAN, width=169, height=68).place(x=0, y=0, width=169, height=68)
        MetricTile(sidebar, "上局获胜", self.last_win_var, Theme.GREEN, width=169, height=68).place(x=179, y=0, width=169, height=68)

        # Extra vertical room prevents the R3-style physical chips from being clipped.
        chip_card = self._card(sidebar, width=348, height=101, padding=10)
        chip_card.place(x=0, y=78, width=348, height=101)
        cc = chip_card.content
        tk.Label(cc, text="下注筹码", bg=Theme.PANEL, fg=Theme.TEXT,
                 font=(Theme.FONT_CJK, 10, "bold"), anchor=tk.W).place(x=0, y=0, width=100, height=20)
        chip_width = 57
        chip_gap = 9
        for i, (label, amount, color, text_color) in enumerate(CHIP_CONFIGS):
            chip = ChipButton(cc, label=label, amount=amount, chip_color=color,
                              text_color=text_color, command=self.add_chip,
                              width=chip_width, height=50)
            chip.place(x=i * (chip_width + chip_gap), y=22, width=chip_width, height=50)
            self.chip_buttons.append(chip)

        diff_card = self._card(sidebar, width=348, height=87, padding=10)
        diff_card.place(x=0, y=189, width=348, height=87)
        dc = diff_card.content
        tk.Label(dc, text="难度模式", bg=Theme.PANEL, fg=Theme.TEXT,
                 font=(Theme.FONT_CJK, 10, "bold"), anchor=tk.W).place(x=0, y=0, width=100, height=20)
        for i, (label, value) in enumerate(DIFFICULTIES):
            btn = ModernButton(dc, text=label, font_size=11, bold=True,
                               command=lambda v=value: self.set_difficulty(v),
                               background=Theme.ACCENT if value == self.difficulty else Theme.PANEL_ALT,
                               hover_background=Theme.ACCENT_HOVER if value == self.difficulty else Theme.PANEL_HOVER,
                               foreground="white" if value == self.difficulty else Theme.TEXT)
            btn.place(x=i*103, y=27, width=94, height=36)
            self.difficulty_buttons.append(btn)

        stat_card = self._card(sidebar, width=348, height=70, padding=10)
        stat_card.place(x=0, y=286, width=348, height=70)
        sc = stat_card.content
        tk.Label(sc, text="本局状态", bg=Theme.PANEL, fg=Theme.TEXT,
                 font=(Theme.FONT_CJK, 10, "bold"), anchor=tk.W).place(x=0, y=0, width=100, height=20)
        tk.Label(sc, text="选择号码数量", bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
                 font=(Theme.FONT_CJK, 8), anchor=tk.W).place(x=0, y=27, width=110, height=20)
        tk.Label(sc, textvariable=self.selection_count_var, bg=Theme.PANEL, fg=Theme.ACCENT,
                 font=(Theme.FONT, 12, "bold"), anchor=tk.E).place(x=118, y=25, width=204, height=22)

        action_card = self._card(sidebar, width=348, height=151, padding=10)
        action_card.place(x=0, y=366, width=348, height=151)
        ac = action_card.content
        self.lucky_button = ModernButton(ac, text="幸运数字", command=self.add_lucky_number,
                                         background=Theme.ACCENT_SOFT, hover_background=Theme.PANEL_HOVER,
                                         foreground=Theme.ACCENT, bold=True)
        self.lucky_button.place(x=0, y=0, width=156, height=36)
        self.clear_button = ModernButton(ac, text="清空选择", command=self.clear_selection,
                                         background=Theme.PANEL_ALT, hover_background=Theme.PANEL_HOVER)
        self.clear_button.place(x=166, y=0, width=156, height=36)
        self.reset_bet_button = ModernButton(ac, text="清空全部筹码", command=self.reset_bet,
                                             background=Theme.PANEL_ALT, hover_background=Theme.PANEL_HOVER)
        self.reset_bet_button.place(x=0, y=46, width=322, height=36)
        self.start_button = ModernButton(ac, text="开始游戏", command=self.start_game,
                                         background=Theme.GREEN, hover_background=Theme.GREEN_HOVER,
                                         foreground="white", bold=True)
        self.start_button.place(x=0, y=92, width=322, height=36)

        rules = self._card(sidebar, width=348, height=79, padding=10)
        rules.place(x=0, y=527, width=348, height=79)
        rc = rules.content
        tk.Label(rc, text="玩法说明", bg=Theme.PANEL, fg=Theme.TEXT,
                 font=(Theme.FONT_CJK, 9, "bold"), anchor=tk.W).place(x=0, y=0, width=80, height=18)
        tk.Label(rc, text="选择 1–10 个号码；系统从 1–50 开出 10 个号码。\n命中数越高，按当前难度赔率表返还奖金。",
                 bg=Theme.PANEL, fg=Theme.TEXT_MUTED, font=(Theme.FONT_CJK, 8),
                 justify=tk.LEFT, anchor=tk.NW).place(x=0, y=22, width=322, height=40)

    def toggle_number(self, number: int):
        if self.game_active:
            return
        if number in self.user_numbers:
            self.user_numbers.remove(number)
        elif len(self.user_numbers) < 10:
            self.user_numbers.append(number)
        self._refresh_number_cells()
        self.update_status()

    def add_chip(self, amount_text: str):
        if self.game_active:
            return
        try:
            amount = float(amount_text)
        except ValueError:
            return
        if self.current_bet + amount <= self.balance:
            self.current_bet += amount
            self.update_display()
            self.update_status()

    def reset_bet(self):
        if self.game_active:
            return
        self.current_bet = 0.0
        self.update_display(); self.update_status()

    def set_difficulty(self, difficulty: str):
        if self.game_active:
            return
        self.difficulty = difficulty
        for btn, (_, value) in zip(self.difficulty_buttons, DIFFICULTIES):
            if value == difficulty:
                btn.set_colors(Theme.ACCENT, Theme.ACCENT_HOVER, "white")
            else:
                btn.set_colors(Theme.PANEL_ALT, Theme.PANEL_HOVER, Theme.TEXT)
        self.difficulty_text_var.set({"1": "简单", "2": "中等", "3": "地狱"}[difficulty])
        self.update_status()

    def add_lucky_number(self):
        if self.game_active or len(self.user_numbers) >= 10:
            return
        available = [n for n in range(1, 51) if n not in self.user_numbers]
        if available:
            self.user_numbers.append(random.choice(available))
            self._refresh_number_cells(); self.update_status()

    def clear_selection(self):
        if self.game_active:
            return
        self.user_numbers.clear()
        self.winning_numbers.clear()
        self.matches = 0; self.multiplier = 0.0; self.draw_index = 0
        self._refresh_number_cells()
        self.update_status(); self.update_display()

    def update_status(self):
        self.selection_var.set(f"已选择 {len(self.user_numbers)} / 10")
        self.selection_count_var.set(f"{len(self.user_numbers)} 个")
        self._refresh_odds_table()
        if self.game_active:
            return
        if self.current_bet <= 0:
            self.info_var.set("请选择下注金额，再选择 1–10 个号码。")
        elif not self.user_numbers:
            self.info_var.set("请选择 1–10 个号码，或使用“幸运数字”。")
        else:
            name = {"1": "简单", "2": "中等", "3": "地狱"}[self.difficulty]
            self.info_var.set(f"已选 {len(self.user_numbers)} 个号码 · {name}模式 · 可以开始开奖。")

    def update_display(self):
        self.balance_var.set(f"${self.balance:.2f}")
        self.bet_var.set(f"${self.current_bet:.2f}")
        self.last_win_var.set(f"${self.last_win:.2f}")
        self.selection_var.set(f"已选择 {len(self.user_numbers)} / 10")
        self.selection_count_var.set(f"{len(self.user_numbers)} 个")
        self.draw_progress_var.set(f"开奖 {self.draw_index} / 10")
        self._refresh_odds_table()
        self.matches_var.set(f"命中 {self.matches}")
        self.multiplier_var.set(f"{self.multiplier:.2f}×")

    def _refresh_number_cells(self):
        winning_set = set(self.winning_numbers[:self.draw_index]) if self.game_active or self.draw_index else set()
        selected_set = set(self.user_numbers)
        for n, cell in enumerate(self.number_buttons, start=1):
            if n in winning_set:
                cell.set_state("match" if n in selected_set else "miss")
            elif n in selected_set:
                cell.set_state("selected")
            else:
                cell.set_state("default")
            cell.set_enabled(not self.game_active)

    def _current_multiplier(self) -> float:
        table = ODDS_TABLES[self.difficulty]
        count = len(self.user_numbers)
        if count not in table:
            return 0.0
        row = table[count]
        return row[self.matches] if self.matches < len(row) else 0.0

    def start_game(self):
        if self.current_bet <= 0:
            messagebox.showwarning("错误", "请先下注")
            return
        if not self.user_numbers:
            messagebox.showwarning("错误", "请至少选择一个数字")
            return
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注")
            return
        self.game_active = True
        self.balance -= self.current_bet
        update_balance_in_json(self.username, self.balance)
        self.matches = 0
        self.multiplier = 0.0
        self.draw_index = 0
        self.winning_numbers = random.sample(range(1, 51), 10)
        self._set_controls_enabled(False)
        self._refresh_number_cells()
        self.info_var.set("正在开奖 · 中奖号码会逐个亮起")
        self.update_display()
        self.root.after(350, self.draw_numbers)

    def draw_numbers(self):
        if not self.game_active:
            return
        if self.draw_index >= 10:
            self.finish_game()
            return
        num = self.winning_numbers[self.draw_index]
        self.draw_index += 1
        if num in self.user_numbers:
            self.matches += 1
        self.multiplier = self._current_multiplier()
        self._refresh_number_cells()
        self.info_var.set(f"第 {self.draw_index} 个中奖号码：{num}")
        self.update_display()
        self.root.after(500, self.draw_numbers)

    def finish_game(self):
        matches = len(set(self.user_numbers) & set(self.winning_numbers))
        self.matches = matches
        self.multiplier = self._current_multiplier()
        winnings = self.current_bet * self.multiplier
        self.balance += winnings
        self.last_win = winnings
        update_balance_in_json(self.username, self.balance)
        self.game_active = False
        self._refresh_number_cells()
        self.info_var.set(f"本局命中 {matches} 个号码")
        self.update_display()
        # Keep result visible briefly, then restore interaction without blocking Tk.
        self._unlock_job = self.root.after(1800, self._unlock_after_round)

    def _unlock_after_round(self):
        self._unlock_job = None
        self._set_controls_enabled(True)
        for cell in self.number_buttons:
            cell.set_enabled(True)
        self.info_var.set("本局结果已保留；可调整号码、下注或难度后继续。")

    def _set_controls_enabled(self, enabled: bool):
        state = tk.NORMAL if enabled else tk.DISABLED
        for widget in [self.start_button, self.lucky_button, self.clear_button, self.reset_bet_button]:
            widget.configure(state=state)
        for chip in self.chip_buttons:
            chip.configure(state=state)
        for btn in self.difficulty_buttons:
            btn.configure(state=state)
        for cell in self.number_buttons:
            cell.set_enabled(enabled)

    def on_closing(self):
        update_balance_in_json(self.username, self.balance)
        finish = getattr(self.root, "finish", None)
        if callable(finish):
            finish(self.balance)
        else:
            self.root.destroy()


def main(initial_balance=1000.0, username="Guest", *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user
    if parent is not None:
        page = EmbeddedGamePage(parent, title="基诺游戏", username=actual_user,
                                balance=actual_balance, on_back=on_back,
                                on_balance_change=on_balance_change)
        game = KenoGame(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page
    root = tk.Tk()
    game = KenoGame(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    main(10000.0, "test_user")