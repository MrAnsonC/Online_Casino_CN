"""Stock Market — ChickenCrossing-style warm fixed HMI.

Gameplay retained from the original stock_market.py:
- 12-second betting countdown, then a 10-second market round starts automatically.
- Bets can be added to both UP and DOWN while the round is idle/counting down.
- Market updates every 0.05s using the original direction/magnitude random logic.
- Position value is settled from the final cumulative percentage; winning profit
  carries the original 5% fee (0.95 factor).
- Positions remain invested between rounds until Cash Out; positions under $5
  are automatically cashed out.
- 20-round history is persisted in A_Logs/stock_market.json.

The UI is rebuilt to match ChickenCrossing_tk.py: 1150x750 fixed viewport,
warm mineral palette, 1110x714 shell, 748/348 split, metric tiles, tactile
chips and EmbeddedGamePage support.
"""

from __future__ import annotations

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


VERSION = "StockMarket-ChickenStyle-R2"


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

    CHART_BG = "#D9E1D8"
    CHART_GRID = "#AEB9AF"
    CHART_ZERO = "#69766C"
    CHART_UP = "#A84D4D"      # retain original CN market convention: red = up
    CHART_DOWN = "#4E7355"    # green = down
    CHART_POINT = "#345E73"
    HISTORY_EMPTY = "#CCC6BD"

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

# Intentionally retained exactly from the original game.
price_changes = {
    1: 0.34,
    2: 0.23,
    3: 0.13,
    4: 0.08,
    5: 0.07,
    6: 0.06,
    7: 0.06,
    8: 0.05,
    9: 0.04,
    10: 0.03,
}


def get_data_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../saving_data.json")


def get_history_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../A_Logs/Json/stock_market.json")


def load_user_data() -> list:
    try:
        with open(get_data_file_path(), "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return []


def save_user_data(users: list) -> None:
    try:
        with open(get_data_file_path(), "w", encoding="utf-8") as file:
            json.dump(users, file, ensure_ascii=False, indent=4)
    except OSError:
        pass


def update_balance_in_json(username: str, new_balance: float) -> None:
    users = load_user_data()
    for user in users:
        if user.get("user_name") == username:
            user["cash"] = f"{float(new_balance):.2f}"
            break
    if users:
        save_user_data(users)


def save_history_to_file(history_dict: dict) -> None:
    path = get_history_file_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(history_dict, file, ensure_ascii=False, indent=4)
    except OSError:
        pass


def load_history_from_file() -> dict:
    default = {f"{i:02d}": 0 for i in range(1, 21)}
    path = get_history_file_path()
    if not os.path.exists(path):
        save_history_to_file(default)
        return default
    try:
        with open(path, "r", encoding="utf-8") as file:
            history = json.load(file)
        if not isinstance(history, dict):
            raise ValueError
        for i in range(1, 21):
            history.setdefault(f"{i:02d}", 0)
        return history
    except (OSError, json.JSONDecodeError, ValueError):
        save_history_to_file(default)
        return default


def update_history_in_file(new_percent: float) -> dict:
    history = load_history_from_file()
    for i in range(19, 0, -1):
        history[f"{i + 1:02d}"] = history.get(f"{i:02d}", 0)
    history["01"] = int(round(new_percent))
    save_history_to_file(history)
    return history


class ModernButton(tk.Button):
    def __init__(
        self,
        master,
        *,
        text: str = "",
        textvariable: Optional[tk.StringVar] = None,
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
            textvariable=textvariable,
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

    def set_colors(self, background: str, hover: str, foreground: str = "#FFFFFF") -> None:
        self.normal_background = background
        self.hover_background = hover
        self.normal_foreground = foreground
        super().configure(
            bg=background,
            fg=foreground,
            activebackground=hover,
            activeforeground=foreground,
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
            master, width=width, height=height, bg=Theme.PANEL,
            bd=0, highlightthickness=0, cursor="hand2",
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
        self._selected = False
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.draw()

    @staticmethod
    def _shade(color: str, factor: float) -> str:
        if not color.startswith("#") or len(color) != 7:
            return "#555555"
        rgb = [int(color[i:i+2], 16) for i in (1, 3, 5)]
        rgb = [max(0, min(255, round(v * factor))) for v in rgb]
        return "#%02x%02x%02x" % tuple(rgb)

    def draw(self) -> None:
        self.delete("all")
        off = 3 if self._pressed else 0
        outer = self._shade(self.chip_color, 0.68)
        inner = self._shade(self.chip_color, 0.86)
        outline = Theme.AMBER if self._selected else (Theme.TEXT if self._hovered else outer)
        width = 4 if self._selected else (3 if self._hovered else 2)

        self.create_oval(6, 7, self.control_width - 5, self.control_height - 1,
                         fill="#8E877E", outline="")
        self.create_oval(5, 3 + off, self.control_width - 6, self.control_height - 5 + off,
                         fill=outer, outline=outline, width=width)
        self.create_oval(9, 7 + off, self.control_width - 10, self.control_height - 9 + off,
                         fill=self.chip_color, outline=inner, width=2)
        self.create_oval(14, 12 + off, self.control_width - 15, self.control_height - 14 + off,
                         fill=self.chip_color, outline=outer, width=1)
        cx = self.control_width / 2
        cy = (self.control_height - 2) / 2 + off
        for x1, y1, x2, y2 in (
            (cx - 3, 4 + off, cx + 3, 10 + off),
            (cx - 3, self.control_height - 12 + off, cx + 3, self.control_height - 6 + off),
            (6, cy - 3, 12, cy + 3),
            (self.control_width - 13, cy - 3, self.control_width - 7, cy + 3),
        ):
            self.create_rectangle(x1, y1, x2, y2, fill=self.text_color, outline="")
        self.create_text(cx, cy, text=self.label, fill=self.text_color,
                         font=(Theme.FONT, 10 if len(self.label) <= 4 else 9, "bold"))
        if self._state == tk.DISABLED:
            self.create_oval(5, 3 + off, self.control_width - 6, self.control_height - 5 + off,
                             fill="#C9C2B8", outline=Theme.BORDER_SOFT,
                             width=1, stipple="gray50")

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.draw()

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
            self._pressed = True
            self.draw()

    def _on_release(self, event) -> None:
        if self._state == tk.DISABLED:
            return
        pressed = self._pressed
        self._pressed = False
        inside = 0 <= event.x < self.control_width and 0 <= event.y < self.control_height
        if pressed and inside:
            self.command(self.amount)
        self.draw()

    def configure(self, cnf=None, **kwargs):
        state = kwargs.pop("state", None)
        if state is not None:
            self._state = state
            self._hovered = False
            self._pressed = False
            super().configure(cursor="" if state == tk.DISABLED else "hand2")
            self.draw()
        if cnf is not None or kwargs:
            return super().configure(cnf, **kwargs)
        return None

    config = configure


class MetricTile(tk.Frame):
    def __init__(self, master, label: str, variable: tk.StringVar, accent: str, *, width: int, height: int):
        super().__init__(
            master, width=width, height=height, bg=Theme.PANEL_ALT,
            highlightthickness=1, highlightbackground=Theme.BORDER_SOFT,
        )
        self.pack_propagate(False)
        tk.Label(self, text=label, bg=Theme.PANEL_ALT, fg=Theme.TEXT_MUTED,
                 font=(Theme.FONT_CJK, 9), anchor=tk.W).place(x=12, y=8, width=width-24, height=18)
        tk.Label(self, textvariable=variable, bg=Theme.PANEL_ALT, fg=accent,
                 font=(Theme.FONT, 15, "bold"), anchor=tk.W).place(x=12, y=29, width=width-24, height=28)


class StockChart(tk.Canvas):
    """Warm market chart; price mechanics remain external and unchanged."""

    def __init__(self, master, width=746, height=380, **kwargs):
        super().__init__(master, width=width, height=height, bg=Theme.CHART_BG,
                         bd=0, highlightthickness=0, **kwargs)
        self.chart_width = width
        self.chart_height = height
        self.points: list[float] = []
        self.base_price = 100.0
        self.current_price = 100.0
        # 0s initial point + 200 updates at 0.05s = exactly 10.00 seconds.
        self.max_points = 201
        self.draw_chart()

    def reset(self) -> None:
        # Include the t=0 starting point so the 200th 0.05s update lands
        # exactly at the right edge (10.00 seconds).
        self.points = [0.0]
        self.current_price = self.base_price
        self.draw_chart()

    def update_chart(self, new_price_percent: float) -> float:
        self.current_price = self.base_price * (1 + new_price_percent / 100.0)
        self.current_price = min(self.base_price * 2, max(0.0, self.current_price))
        self.points.append(max(-100.0, min(100.0, float(new_price_percent))))
        if len(self.points) > self.max_points:
            self.points = self.points[-self.max_points:]
        self.draw_chart()
        return ((self.current_price - self.base_price) / self.base_price) * 100.0

    def draw_chart(self) -> None:
        self.delete("all")
        w = max(1, int(self.winfo_width() if self.winfo_width() > 1 else self.chart_width))
        h = max(1, int(self.winfo_height() if self.winfo_height() > 1 else self.chart_height))
        left, right, top, bottom = 48, 22, 18, 28
        plot_w = max(1, w - left - right)
        plot_h = max(1, h - top - bottom)

        def y_for(pct: float) -> float:
            return top + (100.0 - max(-100.0, min(100.0, pct))) / 200.0 * plot_h

        for pct in (-100, -50, 0, 50, 100):
            y = y_for(pct)
            color = Theme.CHART_ZERO if pct == 0 else Theme.CHART_GRID
            self.create_line(left, y, left + plot_w, y, fill=color, width=2 if pct == 0 else 1,
                             dash=(5, 5) if pct == 0 else ())
            self.create_text(left - 8, y, text=f"{pct:+d}%" if pct else "0%",
                             fill=Theme.TEXT_MUTED, font=(Theme.FONT, 9, "bold"), anchor=tk.E)

        # Horizontal time axis: 10 equal cells = exactly 10 seconds.
        # Each vertical grid line is one real second, from 0s through 10s.
        for second in range(0, 11):
            x = left + plot_w * second / 10
            self.create_line(
                x, top, x, top + plot_h,
                fill=Theme.CHART_GRID, width=1, stipple="gray50"
            )
            self.create_text(
                x, top + plot_h + 15,
                text=str(second),
                fill=Theme.TEXT_MUTED,
                font=(Theme.FONT, 8, "bold"),
                anchor=tk.CENTER,
            )
        self.create_text(
            w - 3, top + plot_h + 15,
            text="秒", fill=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8, "bold"), anchor=tk.E,
        )

        if not self.points:
            self.create_text(left + plot_w/2, top + plot_h/2,
                             text="等待下一局行情", fill=Theme.TEXT_MUTED,
                             font=(Theme.FONT_CJK, 14, "bold"))
            return

        n = len(self.points)
        coords = []
        for i, pct in enumerate(self.points):
            x = left if self.max_points <= 1 else left + plot_w * i / max(1, self.max_points - 1)
            coords.extend((x, y_for(pct)))

        # Segment colours keep the original China-market red-up / green-down convention.
        for i in range(1, n):
            x1, y1 = coords[(i-1)*2:(i-1)*2+2]
            x2, y2 = coords[i*2:i*2+2]
            color = Theme.CHART_UP if self.points[i] >= self.points[i-1] else Theme.CHART_DOWN
            self.create_line(x1, y1, x2, y2, fill=color, width=3)

        x, y = coords[-2], coords[-1]
        self.create_oval(x-5, y-5, x+5, y+5, fill=Theme.CHART_POINT, outline="#FFFFFF", width=2)
        self.create_text(left + plot_w - 4, top + 8,
                         text=f"PRICE  {self.current_price:.2f}", fill=Theme.ACCENT,
                         font=(Theme.FONT, 10, "bold"), anchor=tk.NE)


class HistoryBar(tk.Canvas):
    def __init__(self, master, width=746, height=118, **kwargs):
        super().__init__(master, width=width, height=height, bg=Theme.PANEL_ALT,
                         bd=0, highlightthickness=0, **kwargs)
        self.history: list[float] = []
        self.max_history = 20

    def set_history(self, history_list) -> None:
        self.history = list(history_list)[-self.max_history:]
        self.draw_history()

    def draw_history(self) -> None:
        self.delete("all")
        w = max(1, int(self.winfo_width() if self.winfo_width() > 1 else self.cget("width")))
        h = max(1, int(self.winfo_height() if self.winfo_height() > 1 else self.cget("height")))
        baseline = h / 2
        gap = 4
        slot_w = (w - gap * (self.max_history + 1)) / self.max_history
        hist = self.history[-self.max_history:]
        data_offset = self.max_history - len(hist)
        for i in range(self.max_history):
            x1 = gap + i * (slot_w + gap)
            x2 = x1 + slot_w
            if i < data_offset:
                self.create_rectangle(x1, 8, x2, h-8, fill=Theme.HISTORY_EMPTY,
                                      outline=Theme.BORDER_SOFT, width=1)
                continue
            val = float(hist[i - data_offset])
            ratio = min(abs(val) / 50.0, 1.0)
            half = max(3.0, (h/2 - 18) * ratio)
            if val > 0:
                y1, y2, fill = baseline-half, baseline, Theme.CHART_UP
                text_y, anchor = y1-3, tk.S
            elif val < 0:
                y1, y2, fill = baseline, baseline+half, Theme.CHART_DOWN
                text_y, anchor = y2+3, tk.N
            else:
                y1, y2, fill = baseline-4, baseline+4, Theme.AMBER
                text_y, anchor = baseline, tk.CENTER
            self.create_rectangle(x1, y1, x2, y2, fill=fill, outline="")
            if slot_w >= 20:
                self.create_text((x1+x2)/2, text_y, text=f"{abs(val):.0f}",
                                 fill=Theme.TEXT, font=(Theme.FONT, 8, "bold"), anchor=anchor)
        self.create_line(0, baseline, w, baseline, fill=Theme.BORDER, width=1)


class StockMarketGame:
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

    def __init__(self, root, initial_balance, username):
        self.root = root
        self._configure_root()

        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount_up = 0.0
        self.bet_amount_down = 0.0
        self.game_active = False
        self.timer_active = False
        self.last_win = 0.0
        self.current_price_percent = 0.0
        self.cumulative_net_since_cashout = 0.0
        self.starting_price = 100
        self.result_history = []
        self.bet_direction = None
        self.timer_id = None
        self.round_job = None
        self.next_round_job = None
        self.selected_chip = 5.0
        self.original_bet_up = 0.0
        self.original_bet_down = 0.0
        self.countdown = 12
        self.current_update = 0
        self.total_updates = 0
        self.update_interval = 0.05

        self.chip_buttons: list[ChipButton] = []
        self.load_history_data()
        self._create_vars()
        self.create_widgets()
        self.update_display()
        self.start_countdown()

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("股市风云")
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

    def _create_vars(self) -> None:
        self.balance_var = tk.StringVar()
        self.up_position_var = tk.StringVar()
        self.down_position_var = tk.StringVar()
        self.percent_var = tk.StringVar(value="0%")
        self.price_var = tk.StringVar(value="$100 / $100")
        self.timer_var = tk.StringVar(value="开盘时间剩下: 12秒")
        self.selected_chip_var = tk.StringVar(value="$5")
        self.status_var = tk.StringVar(value="请选择筹码并建立买涨/买跌仓位")
        self.last_result_var = tk.StringVar(value="尚未开始")
        self.pnl_var = tk.StringVar(value="累计盈亏 $0.00")
        self.up_button_text_var = tk.StringVar(value="买涨 ↑\n$0.00")
        self.down_button_text_var = tk.StringVar(value="买跌 ↓\n$0.00")

    @staticmethod
    def _card(master, *, width: int, height: int, padding: int = 12) -> tk.Frame:
        card = tk.Frame(master, width=width, height=height, bg=Theme.PANEL,
                        highlightthickness=1, highlightbackground=Theme.BORDER_SOFT)
        card.pack_propagate(False)
        card.grid_propagate(False)
        content = tk.Frame(card, bg=Theme.PANEL)
        content.place(x=padding, y=padding, width=max(1, width-padding*2), height=max(1, height-padding*2))
        card.content = content
        return card

    @staticmethod
    def _section_title(master, text: str) -> tk.Label:
        return tk.Label(master, text=text, bg=Theme.PANEL, fg=Theme.TEXT,
                        font=(Theme.FONT_CJK, 11, "bold"), anchor=tk.W)

    def create_widgets(self) -> None:
        shell = tk.Frame(self.root, width=self.SHELL_WIDTH, height=self.SHELL_HEIGHT, bg=Theme.APP_BG)
        shell.pack(padx=20, pady=18)
        shell.pack_propagate(False)
        self._build_header(shell)
        body = tk.Frame(shell, width=self.SHELL_WIDTH, height=self.BODY_HEIGHT, bg=Theme.APP_BG)
        body.place(x=0, y=self.BODY_TOP, width=self.SHELL_WIDTH, height=self.BODY_HEIGHT)
        self._build_market_panel(body)
        self._build_control_panel(body)

    def _build_header(self, shell: tk.Frame) -> None:
        header = tk.Frame(shell, width=self.SHELL_WIDTH, height=self.HEADER_HEIGHT, bg=Theme.PANEL,
                          highlightthickness=1, highlightbackground=Theme.BORDER_SOFT)
        header.place(x=0, y=0, width=self.SHELL_WIDTH, height=self.HEADER_HEIGHT)
        icon = tk.Canvas(header, width=48, height=48, bg=Theme.PANEL, bd=0, highlightthickness=0)
        icon.place(x=14, y=11)
        icon.create_oval(2, 2, 46, 46, fill=Theme.ACCENT_SOFT, outline=Theme.ACCENT, width=2)
        icon.create_line(12, 34, 20, 27, 27, 30, 37, 15, fill=Theme.ACCENT, width=3, smooth=True)
        icon.create_polygon(34, 15, 39, 14, 38, 20, fill=Theme.ACCENT, outline="")
        tk.Label(header, text="MARKET PULSE", bg=Theme.PANEL, fg=Theme.TEXT,
                 font=(Theme.FONT, 18, "bold"), anchor=tk.W).place(x=74, y=10, width=330, height=27)
        tk.Label(header, text="股市风云", bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
                 font=(Theme.FONT_CJK, 11, "bold"), anchor=tk.W).place(x=74, y=39, width=220, height=20)

        box = tk.Frame(header, width=206, height=46, bg=Theme.PANEL_ALT,
                       highlightthickness=1, highlightbackground=Theme.BORDER_SOFT)
        box.place(x=self.SHELL_WIDTH-220, y=12, width=206, height=46)
        tk.Label(box, text="账户余额", bg=Theme.PANEL_ALT, fg=Theme.TEXT_MUTED,
                 font=(Theme.FONT_CJK, 9), anchor=tk.W).place(x=12, y=4, width=90, height=17)
        tk.Label(box, textvariable=self.balance_var, bg=Theme.PANEL_ALT, fg=Theme.ACCENT,
                 font=(Theme.FONT, 15, "bold"), anchor=tk.E).place(x=12, y=20, width=182, height=22)

    def _build_market_panel(self, master: tk.Frame) -> None:
        panel = self._card(master, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT, padding=0)
        panel.place(x=0, y=0, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT)

        top = tk.Frame(panel, width=self.CANVAS_WIDTH, height=74, bg=Theme.PANEL)
        top.place(x=0, y=0, width=self.CANVAS_WIDTH, height=74)
        tk.Label(top, text="当前市场变化", bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
                 font=(Theme.FONT_CJK, 9), anchor=tk.W).place(x=18, y=9, width=120, height=18)
        self.percent_label = tk.Label(top, textvariable=self.percent_var, bg=Theme.PANEL,
                                      fg=Theme.AMBER, font=(Theme.FONT, 23, "bold"), anchor=tk.W)
        self.percent_label.place(x=18, y=26, width=175, height=34)
        tk.Label(top, text="本金100/当前价格", bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
                 font=(Theme.FONT_CJK, 9), anchor=tk.W).place(x=230, y=9, width=150, height=18)
        tk.Label(top, textvariable=self.price_var, bg=Theme.PANEL, fg=Theme.ACCENT,
                 font=(Theme.FONT, 17, "bold"), anchor=tk.W).place(x=230, y=29, width=155, height=28)
        self.market_badge = tk.Label(top, textvariable=self.timer_var, bg=Theme.ACCENT_SOFT, fg=Theme.ACCENT,
                                     font=(Theme.FONT_CJK, 10, "bold"), anchor=tk.CENTER)
        self.market_badge.place(x=545, y=19, width=181, height=32)

        chart_wrap = tk.Frame(panel, width=self.CANVAS_WIDTH, height=383, bg=Theme.CHART_BG)
        chart_wrap.place(x=0, y=74, width=self.CANVAS_WIDTH, height=383)
        self.stock_chart = StockChart(chart_wrap, width=self.CANVAS_WIDTH, height=383)
        self.stock_chart.place(x=0, y=0, width=self.CANVAS_WIDTH, height=383)

        history_wrap = tk.Frame(panel, width=self.CANVAS_WIDTH, height=173, bg=Theme.PANEL)
        history_wrap.place(x=0, y=457, width=self.CANVAS_WIDTH, height=173)
        tk.Label(history_wrap, text="过去 20 局", bg=Theme.PANEL, fg=Theme.TEXT,
                 font=(Theme.FONT_CJK, 11, "bold"), anchor=tk.W).place(x=16, y=9, width=120, height=22)
        tk.Label(history_wrap, text="红=上涨 · 绿=下跌", bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
                 font=(Theme.FONT_CJK, 9), anchor=tk.E).place(x=540, y=10, width=188, height=20)
        self.history_bar = HistoryBar(history_wrap, width=714, height=124)
        self.history_bar.place(x=16, y=38, width=714, height=124)
        self.history_bar.set_history(self.result_history)

    def _build_control_panel(self, master: tk.Frame) -> None:
        sidebar = tk.Frame(master, width=self.SIDEBAR_WIDTH, height=self.BODY_HEIGHT, bg=Theme.APP_BG)
        sidebar.place(x=self.GAME_PANEL_WIDTH + self.PANEL_GAP, y=0, width=self.SIDEBAR_WIDTH, height=self.BODY_HEIGHT)

        MetricTile(sidebar, "买涨仓位", self.up_position_var, Theme.RED, width=169, height=68).place(x=0, y=0, width=169, height=68)
        MetricTile(sidebar, "买跌仓位", self.down_position_var, Theme.GREEN, width=169, height=68).place(x=179, y=0, width=169, height=68)

        chips = self._card(sidebar, width=348, height=101)
        chips.place(x=0, y=78, width=348, height=101)
        self._section_title(chips.content, "选择筹码").place(x=0, y=0, width=100, height=20)
        tk.Label(chips.content, textvariable=self.selected_chip_var, bg=Theme.PANEL, fg=Theme.AMBER,
                 font=(Theme.FONT, 10, "bold"), anchor=tk.E).place(x=220, y=0, width=102, height=20)
        for i, (label, amount, color, text_color) in enumerate(CHIP_CONFIGS):
            chip = ChipButton(chips.content, label=label, amount=amount, chip_color=color,
                              text_color=text_color, command=self.select_chip)
            chip.place(x=i*62, y=24, width=57, height=50)
            chip.set_selected(i == 0)
            self.chip_buttons.append(chip)

        state = self._card(sidebar, width=348, height=70, padding=9)
        state.place(x=0, y=189, width=348, height=70)

        # --------------------------------------------------
        # 左侧：市场状态
        # --------------------------------------------------
        tk.Label(
            state.content,
            text="市场状态",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 12),
            anchor=tk.W,
        ).place(
            x=0,
            y=3,
            width=150,
            height=18,
        )

        tk.Label(
            state.content,
            textvariable=self.timer_var,
            bg=Theme.PANEL,
            fg=Theme.ACCENT,
            font=(Theme.FONT_CJK, 10, "bold"),
            anchor=tk.W,
        ).place(
            x=0,
            y=27,
            width=205,
            height=24,
        )


        # --------------------------------------------------
        # 右侧：累计盈亏
        # --------------------------------------------------
        self.pnl_label = tk.Label(
            state.content,
            textvariable=self.pnl_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT, 11, "bold"),
            anchor=tk.E,
        )
        self.pnl_label.place(
            x=215,
            y=27,
            width=107,
            height=24,
        )

        actions = self._card(sidebar, width=348, height=144)
        actions.place(x=0, y=265, width=348, height=144)
        self._section_title(actions.content, "建立 / 管理仓位").place(x=0, y=0, width=150, height=20)
        self.up_button = ModernButton(
            actions.content, textvariable=self.up_button_text_var,
            command=lambda: self.add_bet("up"), background=Theme.RED,
            hover_background=Theme.RED_HOVER, foreground="#FFFFFF", font_size=12, bold=True,
        )
        self.up_button.place(x=0, y=27, width=156, height=52)
        self.down_button = ModernButton(
            actions.content, textvariable=self.down_button_text_var,
            command=lambda: self.add_bet("down"), background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER, foreground="#FFFFFF", font_size=12, bold=True,
        )
        self.down_button.place(x=166, y=27, width=156, height=52)
        self.cashout_button = ModernButton(
            actions.content, text="兑现全部仓位", command=self.cashout,
            background=Theme.ACCENT, hover_background=Theme.ACCENT_HOVER,
            foreground="#FFFFFF", font_size=12, bold=True,
        )
        self.cashout_button.place(x=0, y=88, width=322, height=32)

        result = self._card(sidebar, width=348, height=82)
        result.place(x=0, y=419, width=348, height=82)
        self._section_title(result.content, "上局结果").place(x=0, y=0, width=100, height=20)
        self.last_result_label = tk.Label(result.content, textvariable=self.last_result_var, bg=Theme.PANEL,
                                          fg=Theme.TEXT, font=(Theme.FONT_CJK, 12, "bold"), anchor=tk.W)
        self.last_result_label.place(x=0, y=28, width=322, height=24)

        rules = self._card(sidebar, width=348, height=130)
        rules.place(x=0, y=511, width=348, height=130)
        self._section_title(rules.content, "玩法说明").place(x=0, y=0, width=100, height=20)
        tk.Label(
            rules.content,
            text="倒计时可加仓；开局后锁定操作。\n10 秒行情结束后仓位自动重估\n盈利收 5% 费用；低于 $5 自动兑现。\n仓位会跨局保留，点击兑现才返回余额。",
            bg=Theme.PANEL, fg=Theme.TEXT_MUTED, font=(Theme.FONT_CJK, 10),
            justify=tk.LEFT, anchor=tk.NW,
        ).place(x=0, y=20, width=322, height=77)

    def load_history_data(self) -> None:
        history = load_history_from_file()
        self.result_history = [history.get(f"{i:02d}", 0) for i in range(20, 0, -1)]

    def select_chip(self, amount_text: str) -> None:
        if self.game_active:
            return
        try:
            amount = float(amount_text)
        except (TypeError, ValueError):
            return
        self.selected_chip = amount
        label = "$1K" if amount == 1000 else f"${amount:g}"
        self.selected_chip_var.set(f"已选 {label}")
        for chip in self.chip_buttons:
            chip.set_selected(float(chip.amount) == amount)

    def add_bet(self, direction: str) -> None:
        if self.game_active:
            return
        if self.selected_chip > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注。", parent=self.root)
            return
        self.bet_direction = direction
        if direction == "up":
            self.bet_amount_up += self.selected_chip
        else:
            self.bet_amount_down += self.selected_chip
        self.balance -= self.selected_chip
        update_balance_in_json(self.username, self.balance)
        self.update_display()
        self.update_status()

    def update_direction_buttons_text(self) -> None:
        if self.game_active:
            up_val = self.original_bet_up * (1 + self.current_price_percent / 100) if self.original_bet_up > 0 else 0.0
            down_val = self.original_bet_down * (1 - self.current_price_percent / 100) if self.original_bet_down > 0 else 0.0
            self.up_button_text_var.set(f"买涨 ↑\n${max(0.0, up_val):.2f}")
            self.down_button_text_var.set(f"买跌 ↓\n${max(0.0, down_val):.2f}")
        else:
            self.up_button_text_var.set(f"买涨 ↑\n${self.bet_amount_up:.2f}")
            self.down_button_text_var.set(f"买跌 ↓\n${self.bet_amount_down:.2f}")

    def cashout(self) -> None:
        if self.game_active:
            return
        total = float(self.bet_amount_up) + float(self.bet_amount_down)
        if total <= 0:
            if self.cumulative_net_since_cashout != 0.0:
                self._show_cumulative_result()
                self.cumulative_net_since_cashout = 0.0
                self.update_display()
            return
        self.balance += total
        self.bet_amount_up = 0.0
        self.bet_amount_down = 0.0
        self.original_bet_up = 0.0
        self.original_bet_down = 0.0
        self._show_cumulative_result()
        self.cumulative_net_since_cashout = 0.0
        update_balance_in_json(self.username, self.balance)
        self.update_display()
        self.update_status()

    def _show_cumulative_result(self) -> None:
        cum = self.cumulative_net_since_cashout
        if cum > 0:
            self.last_result_var.set(f"累计盈利 ${cum:.2f} · 已兑现")
            self.last_result_label.configure(fg=Theme.GREEN)
        elif cum < 0:
            self.last_result_var.set(f"累计亏损 ${abs(cum):.2f} · 已兑现")
            self.last_result_label.configure(fg=Theme.RED)
        else:
            self.last_result_var.set("累计持平 · 已兑现")
            self.last_result_label.configure(fg=Theme.AMBER)

    def auto_cashout_small_bets(self) -> None:
        total_cashed = 0.0
        if 0 < self.bet_amount_up < 5:
            self.balance += self.bet_amount_up
            total_cashed += self.bet_amount_up
            self.bet_amount_up = 0.0
            self.original_bet_up = 0.0
        if 0 < self.bet_amount_down < 5:
            self.balance += self.bet_amount_down
            total_cashed += self.bet_amount_down
            self.bet_amount_down = 0.0
            self.original_bet_down = 0.0
        if total_cashed > 0:
            self._show_cumulative_result()
            self.cumulative_net_since_cashout = 0.0
            update_balance_in_json(self.username, self.balance)
            self.update_display()

    def update_status(self) -> None:
        if self.game_active:
            return
        if self.bet_amount_up > 0 or self.bet_amount_down > 0:
            self.status_var.set("仓位已建立，可继续加仓或等待开局")
        else:
            self.status_var.set("请选择筹码并建立买涨/买跌仓位")

    def update_display(self) -> None:
        self.balance_var.set(f"${self.balance:,.2f}")
        self.up_position_var.set(f"${self.bet_amount_up:,.2f}")
        self.down_position_var.set(f"${self.bet_amount_down:,.2f}")
        simulated_price = int(round(100.0 * (1 + self.current_price_percent / 100)))
        simulated_price = max(0, min(200, simulated_price))
        self.price_var.set(f"$100 / ${simulated_price}")
        self.percent_var.set(f"{self.current_price_percent:+.0f}%")
        if self.current_price_percent > 0:
            self.percent_label.configure(fg=Theme.RED)
        elif self.current_price_percent < 0:
            self.percent_label.configure(fg=Theme.GREEN)
        else:
            self.percent_label.configure(fg=Theme.AMBER)
        self.pnl_var.set(f"累计盈亏 {self.cumulative_net_since_cashout:+.2f}")
        self.update_direction_buttons_text()

    def _set_controls(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        self.up_button.configure(state=state)
        self.down_button.configure(state=state)
        self.cashout_button.configure(state=state)
        for chip in self.chip_buttons:
            chip.configure(state=state)

    def start_countdown(self, countdown: int = 12) -> None:
        if self.game_active:
            return
        self.timer_active = True
        self.countdown = countdown
        self._set_controls(True)
        self.auto_cashout_small_bets()
        self.history_bar.set_history(self.result_history)
        self.update_status()
        self.update_timer()

    def update_timer(self) -> None:
        if not self.timer_active:
            return
        if self.countdown > 0:
            self.timer_var.set(f"开盘时间剩下: {self.countdown}秒")
            self.countdown -= 1
            self.timer_id = self.root.after(1000, self.update_timer)
        else:
            self.timer_var.set("离收盘时间剩下: 10.0秒")
            self.timer_active = False
            self.timer_id = None
            self.start_game_auto()

    def start_game_auto(self) -> None:
        self.start_game()

    def start_game(self) -> None:
        if self.game_active:
            return
        self.original_bet_up = self.bet_amount_up
        self.original_bet_down = self.bet_amount_down
        self.game_active = True
        self._set_controls(False)
        self.stock_chart.reset()
        self.current_price_percent = 0.0
        self.game_duration = 10
        self.update_interval = 0.05
        self.total_updates = int(self.game_duration / self.update_interval)
        self.current_update = 0
        self.status_var.set("市场开盘 · 仓位已锁定")
        self.timer_var.set(f"离收盘时间剩下: {self.game_duration:.1f}秒")
        self.update_display()
        # Do not consume the first 0.05-second market step immediately.
        # The first update happens after 0.05s; update #200 therefore lands
        # at 10.00s and at the chart's exact right edge.
        self.round_job = self.root.after(
            int(self.update_interval * 1000), self.run_game_update
        )

    def run_game_update(self) -> None:
        if not self.game_active:
            return
        if self.current_update >= self.total_updates:
            self.finish_game()
            return

        direction = random.choice(["up", "down"])
        rand_val = random.random()
        cumulative_prob = 0.0
        change_percent = 1
        for percent, prob in price_changes.items():
            cumulative_prob += prob
            if rand_val <= cumulative_prob:
                change_percent = percent
                break
        if direction == "down":
            change_percent = -change_percent

        self.current_price_percent = max(-100.0, min(100.0, self.current_price_percent + change_percent))
        self.stock_chart.update_chart(self.current_price_percent)
        self.status_var.set(f"市场更新 · {'↑' if change_percent > 0 else '↓'}{abs(change_percent):.0f}%")
        self.current_update += 1
        elapsed = self.current_update * self.update_interval
        remaining = max(0.0, self.game_duration - elapsed)
        self.timer_var.set(f"离收盘时间剩下: {remaining:.1f}秒")
        self.update_display()

        # The 200th 0.05s update is exactly t=10.00s.  At that moment the
        # pointer is on the chart's right edge, so close the market now rather
        # than waiting for an unnecessary 201st timer callback.
        if self.current_update >= self.total_updates:
            self.finish_game()
            return

        self.round_job = self.root.after(
            int(self.update_interval * 1000), self.run_game_update
        )

    def finish_game(self) -> None:
        if not self.game_active:
            return
        final_percent = self.current_price_percent
        update_history_in_file(final_percent)
        self.load_history_data()
        self.history_bar.set_history(self.result_history)

        total_win = 0.0
        total_loss = 0.0
        if self.original_bet_up > 0:
            if final_percent > 0:
                winnings = self.original_bet_up * (final_percent / 100) * 0.95
                total_win += winnings
                self.bet_amount_up = self.original_bet_up + winnings
            else:
                loss = self.original_bet_up * (abs(final_percent) / 100)
                total_loss += loss
                self.bet_amount_up = max(0.0, self.original_bet_up - loss)
        if self.original_bet_down > 0:
            if final_percent < 0:
                winnings = self.original_bet_down * (abs(final_percent) / 100) * 0.95
                total_win += winnings
                self.bet_amount_down = self.original_bet_down + winnings
            else:
                loss = self.original_bet_down * (final_percent / 100)
                total_loss += loss
                self.bet_amount_down = max(0.0, self.original_bet_down - loss)

        net_win = total_win - total_loss
        self.last_win = net_win
        self.cumulative_net_since_cashout += net_win

        if final_percent > 0:
            self.last_result_var.set(f"上涨 {final_percent:.0f}% · 本局 {net_win:+.2f}")
            self.last_result_label.configure(fg=Theme.RED)
        elif final_percent < 0:
            self.last_result_var.set(f"下跌 {abs(final_percent):.0f}% · 本局 {net_win:+.2f}")
            self.last_result_label.configure(fg=Theme.GREEN)
        else:
            self.last_result_var.set(f"持平 0% · 本局 {net_win:+.2f}")
            self.last_result_label.configure(fg=Theme.AMBER)

        self.game_active = False
        self.round_job = None
        self.status_var.set("本局收盘 · 2 秒后进入下一轮倒计时")
        self.timer_var.set("本局已收盘")
        self.auto_cashout_small_bets()
        self.update_display()
        self.next_round_job = self.root.after(2000, lambda: self.start_countdown(12))

    def on_closing(self) -> None:
        for job in (self.timer_id, self.round_job, self.next_round_job):
            if job:
                try:
                    self.root.after_cancel(job)
                except tk.TclError:
                    pass
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
            title="股市风云",
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        page.set_requested_size(1150, 750)
        game = StockMarketGame(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = StockMarketGame(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    final_balance = main(10000.0, "test_user")
    print(f"Final balance: {final_balance:.2f}")