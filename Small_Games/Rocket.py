"""Rocket HMI — ChickenCrossing visual-system edition.

The original crash-game rules are preserved: place a bet, optionally set an
automatic cash-out multiplier, then cash out before the hidden boom multiplier
is reached.  The UI is rebuilt around the warm fixed-size ChickenCrossing HMI
and supports the project's single-Tk EmbeddedGamePage mode.
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


import bisect
import json
import math
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


VERSION = "Rocket-ChickenStyle-R4-CloudMilestones"


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

    SKY = "#AFCAD4"
    SKY_DEEP = "#8FB2C1"
    CLOUD = "#E8E5DE"
    GROUND = "#879B78"
    GROUND_DARK = "#667C5B"
    PAD = "#9B9185"
    PAD_DARK = "#6E675F"
    ROCKET_BODY = "#E4E0D8"
    ROCKET_EDGE = "#736E68"
    ROCKET_NOSE = "#B85D4F"
    ROCKET_WINDOW = "#82B9C8"
    FLAME = "#D98436"
    FLAME_LIGHT = "#E9B452"
    TRAIL = "#D8E0D7"
    EXPLOSION = "#D57A45"
    EXPLOSION_LIGHT = "#E7B74A"

    # Solar-journey scene palette.  These remain muted so the game still
    # belongs to the ChickenCrossing warm HMI family.
    ATMOSPHERE_TOP = "#739AA9"
    ATMOSPHERE_LOW = "#AFCAD4"
    SPACE = "#26343E"
    SPACE_DEEP = "#18232B"
    STAR = "#E7E1D8"
    PLANET_LINE = "#AFA79D"
    MOON = "#C8C3BB"
    MARS = "#B96B55"
    JUPITER = "#C49B72"
    SATURN = "#D2B67A"
    URANUS = "#8FC4C9"
    NEPTUNE = "#668BA8"
    PLUTO = "#B9A99B"

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


# ---------------------------------------------------------------------------
# Persistence
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
    """Physical betting chip matching the Chicken/Thimbles HMI."""

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
        self.create_oval(
            5, 3 + offset_y, self.control_width - 5, self.control_height - 5 + offset_y,
            fill=outer if not disabled else "#9A958D", outline=outline,
            width=outline_width,
        )
        self.create_oval(
            9, 7 + offset_y, self.control_width - 9, self.control_height - 9 + offset_y,
            fill=self.chip_color if not disabled else "#B2ADA5",
            outline=inner if not disabled else "#8E8981", width=2,
        )
        cx, cy = self.control_width / 2, self.control_height / 2 - 1 + offset_y
        r1, r2 = 18, 22
        for angle in (0, 90, 180, 270):
            rad = math.radians(angle)
            x1, y1 = cx + math.cos(rad) * r1, cy + math.sin(rad) * r1
            x2, y2 = cx + math.cos(rad) * r2, cy + math.sin(rad) * r2
            self.create_line(x1, y1, x2, y2, fill="#F4F1EA", width=4)
        self.create_text(
            cx, cy,
            text=self.label,
            fill=self.text_color if not disabled else Theme.TEXT_DIM,
            font=(Theme.FONT, 11, "bold"),
        )

    def _activate(self) -> None:
        if self._state == tk.DISABLED:
            return
        self.command(self.amount)
        self._flash = True
        if self._flash_job is not None:
            try:
                self.after_cancel(self._flash_job)
            except tk.TclError:
                pass
        self._flash_job = self.after(130, self._clear_flash)
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
            self._activate()
        else:
            self.draw()

    def _keyboard_activate(self, _event) -> str:
        self._activate()
        return "break"

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


class RocketGame:
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

    ACTION_BUTTON_HEIGHT = 36
    DESTINATION_MULTIPLIER = 500.0
    FLIGHT_TICK_MS = 45
    SPEED_SCALE = 0.25  # R2 的 25% 速度：整体减慢 3/4
    RTP = 0.96
    WORLD_SCALE = 1750.0

    # Milestone windows requested for the solar-system journey.
    # Neptune interprets the user's "200X-22X" as 200X-220X, matching
    # the surrounding milestone pattern.
    MILESTONES = (
        ("大气层", 2.0, 2.5),
        ("太空", 2.5, 3.0),
        ("月球", 5.0, 5.5),
        ("火星", 10.0, 11.0),
        ("木星", 20.0, 22.0),
        ("土星", 50.0, 55.0),
        ("天王星", 100.0, 110.0),
        ("海王星", 200.0, 220.0),
        ("冥王星", 500.0, 500.0),
    )

    # Weighted-distribution cache.  The original algorithm used weights
    # proportional to 1 / multiplier**1.5 on this exact stepped grid.
    _probability_ready = False
    _small_points: list[float] = []
    _small_weights: list[float] = []
    _tail_block_cumulative: list[float] = []
    _small_total = 0.0
    _tail_total = 0.0
    _tail_start = 10.1
    _tail_count = 999_990
    _tail_block_size = 1000

    def __init__(self, root, initial_balance: float, username: str):
        self.root = root
        self._configure_root()

        self.balance = float(initial_balance)
        self.username = username
        self.current_bet = 0.0
        self.bet_amount = 0.0
        self.last_win = 0.0

        self.game_active = False
        self.game_running = False
        self.current_multiplier = 1.0
        self.boom_multiplier = 0.0
        self.target_multiplier = 1_000_000.0
        self.last_result = ""

        self.phase = "idle"  # idle, countdown, flying, result
        self.countdown_value = 0
        self._countdown_job: Optional[str] = None
        self._flight_job: Optional[str] = None
        self._result_job: Optional[str] = None
        self._time_to_increase = self.FLIGHT_TICK_MS
        self._multiplier_exact = 1.0
        self.flight_distance = 0.0
        self._trail_points: list[tuple[float, float]] = []

        self.chip_buttons: list[ChipButton] = []

        self.create_widgets()
        self.update_display()
        self.root.after(100, self.draw_scene)

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("火箭升空")
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
            font=(Theme.FONT, 10, "bold"), anchor=tk.CENTER,
        ).place(x=4, y=24, width=96, height=20)

    def create_widgets(self) -> None:
        self.balance_var = tk.StringVar(value=f"${self.balance:.2f}")
        self.bet_var = tk.StringVar(value="$0.00")
        self.last_win_var = tk.StringVar(value="$0.00")
        self.multiplier_var = tk.StringVar(value="1.00×")
        self.potential_var = tk.StringVar(value="$0.00")
        self.auto_target_var = tk.StringVar(value="关闭")
        self.status_var = tk.StringVar(value="设置下注金额后开始飞行。")
        self.badge_var = tk.StringVar(value="待机")
        self.canvas_multiplier_var = tk.StringVar(value="1.00×")
        self.auto_cash_var = tk.StringVar(value="")

        shell = tk.Frame(
            self.root, width=self.SHELL_WIDTH, height=self.SHELL_HEIGHT,
            bg=Theme.APP_BG,
        )
        shell.pack(padx=20, pady=18)
        shell.pack_propagate(False)

        self._build_header(shell)
        body = tk.Frame(
            shell, width=self.SHELL_WIDTH, height=self.BODY_HEIGHT, bg=Theme.APP_BG,
        )
        body.place(x=0, y=self.BODY_TOP, width=self.SHELL_WIDTH, height=self.BODY_HEIGHT)
        body.pack_propagate(False)
        self._build_game_panel(body)
        self._build_control_panel(body)

    def _build_header(self, master) -> None:
        header = tk.Frame(
            master, width=self.SHELL_WIDTH, height=self.HEADER_HEIGHT, bg=Theme.APP_BG,
        )
        header.place(x=0, y=0, width=self.SHELL_WIDTH, height=self.HEADER_HEIGHT)

        tk.Label(
            header, text="🚀", bg=Theme.APP_BG, fg=Theme.TEXT,
            font=(Theme.FONT_EMOJI, 30), anchor=tk.CENTER,
        ).place(x=0, y=5, width=42, height=46)
        tk.Label(
            header, text="ROCKET", bg=Theme.APP_BG, fg=Theme.TEXT,
            font=(Theme.FONT, 20, "bold"), anchor=tk.W,
        ).place(x=52, y=4, width=430, height=31)
        tk.Label(
            header, text="火箭升空", bg=Theme.APP_BG, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 10), anchor=tk.W,
        ).place(x=52, y=37, width=520, height=22)

        balance_box = tk.Frame(
            header, width=270, height=54, bg=Theme.PANEL,
            highlightthickness=1, highlightbackground=Theme.BORDER,
        )
        balance_box.place(x=840, y=8, width=270, height=54)
        self.balance_display_var = tk.StringVar()

        def sync_balance(*_args) -> None:
            self.balance_display_var.set(f"账户余额: {self.balance_var.get()}")

        self.balance_var.trace_add("write", sync_balance)
        sync_balance()
        tk.Label(
            balance_box, textvariable=self.balance_display_var,
            bg=Theme.PANEL, fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 13, "bold"), anchor=tk.E,
        ).place(x=10, y=8, width=245, height=38)

    def _build_game_panel(self, master) -> None:
        panel = self._card(master, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT, padding=0)
        panel.place(x=0, y=0, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT)
        content = panel.content  # type: ignore[attr-defined]

        top = tk.Frame(content, width=self.CANVAS_WIDTH, height=74, bg=Theme.PANEL)
        top.place(x=0, y=0, width=self.CANVAS_WIDTH, height=74)
        tk.Label(
            top, textvariable=self.status_var, bg=Theme.PANEL, fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 17, "bold"), anchor=tk.W,
        ).place(x=18, y=17, width=550, height=38)
        self.badge_label = tk.Label(
            top, textvariable=self.badge_var, bg=Theme.ACCENT_SOFT, fg=Theme.ACCENT,
            font=(Theme.FONT_CJK, 9, "bold"), anchor=tk.CENTER,
        )
        self.badge_label.place(x=574, y=19, width=152, height=32)

        self.rocket_canvas = tk.Canvas(
            content, width=self.CANVAS_WIDTH, height=554,
            bg=Theme.SKY, bd=0, highlightthickness=0,
        )
        self.rocket_canvas.place(x=0, y=74, width=self.CANVAS_WIDTH, height=554)
        self.rocket_canvas.bind("<Configure>", lambda _event: self.draw_scene())

    def _build_control_panel(self, master) -> None:
        sidebar = tk.Frame(master, width=self.SIDEBAR_WIDTH, height=self.BODY_HEIGHT, bg=Theme.APP_BG)
        sidebar.place(
            x=self.GAME_PANEL_WIDTH + self.PANEL_GAP, y=0,
            width=self.SIDEBAR_WIDTH, height=self.BODY_HEIGHT,
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
        for index, (label, amount, chip_color, text_color) in enumerate(CHIP_CONFIGS):
            button = ChipButton(
                bet_content,
                label=label,
                amount=amount,
                chip_color=chip_color,
                text_color=text_color,
                command=self.add_chip,
                width=57,
                height=50,
            )
            button.place(x=index * 66, y=42, width=57, height=50)
            self.chip_buttons.append(button)

        auto_card = self._card(sidebar, width=348, height=106, padding=12)
        auto_card.place(x=0, y=208, width=348, height=106)
        auto_content = auto_card.content  # type: ignore[attr-defined]
        self._section_title(auto_content, "自动兑现", "留空表示关闭；最低 1.01×", width=322)
        entry_shell = tk.Frame(
            auto_content, bg=Theme.PANEL_ALT,
            highlightthickness=1, highlightbackground=Theme.BORDER_SOFT,
        )
        entry_shell.place(x=0, y=45, width=322, height=34)
        self.auto_cash_entry = tk.Entry(
            entry_shell,
            textvariable=self.auto_cash_var,
            bg=Theme.PANEL_ALT,
            fg=Theme.TEXT,
            disabledbackground=Theme.PANEL_HOVER,
            disabledforeground=Theme.TEXT_DIM,
            insertbackground=Theme.TEXT,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            font=(Theme.FONT, 12, "bold"),
            justify=tk.CENTER,
        )
        self.auto_cash_entry.place(x=8, y=3, width=280, height=27)
        tk.Label(
            entry_shell, text="×", bg=Theme.PANEL_ALT, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT, 12, "bold"), anchor=tk.CENTER,
        ).place(x=290, y=3, width=24, height=27)

        action_card = self._card(sidebar, width=348, height=184, padding=12)
        action_card.place(x=0, y=324, width=348, height=184)
        action_content = action_card.content  # type: ignore[attr-defined]

        stats = tk.Frame(action_content, width=322, height=52, bg=Theme.PANEL)
        stats.place(x=0, y=0, width=322, height=52)
        self._mini_stat(stats, 0, "当前倍数", self.multiplier_var, Theme.CYAN)
        self._mini_stat(stats, 109, "可兑现", self.potential_var, Theme.GREEN)
        self._mini_stat(stats, 218, "自动目标", self.auto_target_var, Theme.AMBER)

        self.button_frame = tk.Frame(action_content, width=322, height=106, bg=Theme.PANEL)
        self.button_frame.place(x=0, y=58, width=322, height=106)

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

        self.cash_out_button = ModernButton(
            self.button_frame,
            text="立即兑现",
            command=self.cash_out,
            background=Theme.ACCENT,
            hover_background=Theme.ACCENT_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.cash_out_button.place_forget()

        rules_card = self._card(sidebar, width=348, height=112, padding=12)
        rules_card.place(x=0, y=518, width=348, height=112)
        rules_content = rules_card.content  # type: ignore[attr-defined]
        tk.Label(
            rules_content,
            text=(
                "本局隐藏爆点在起飞前已经确定。\n"
                "场景随飞行距离连续滚动；爆炸前可手动或自动兑现。\n"
                "若隐藏结果达到 500×。"
            ),
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9),
            justify=tk.LEFT,
            anchor=tk.W,
            wraplength=320,
        ).place(x=0, y=0, width=322, height=86)

    # ------------------------------------------------------------------
    # Scene rendering
    # ------------------------------------------------------------------

    def _canvas_size(self) -> tuple[int, int]:
        width = max(100, self.rocket_canvas.winfo_width())
        height = max(100, self.rocket_canvas.winfo_height())
        return width, height

    def _draw_cloud(self, x: float, y: float, scale: float = 1.0, fill: Optional[str] = None) -> None:
        c = self.rocket_canvas
        cloud_fill = fill or Theme.CLOUD
        c.create_oval(x, y + 10 * scale, x + 56 * scale, y + 38 * scale, fill=cloud_fill, outline="")
        c.create_oval(x + 22 * scale, y, x + 72 * scale, y + 38 * scale, fill=cloud_fill, outline="")
        c.create_oval(x + 48 * scale, y + 10 * scale, x + 100 * scale, y + 38 * scale, fill=cloud_fill, outline="")

    def _draw_rocket_vector(self, x: float, y: float, scale: float = 1.0, flying: bool = False) -> None:
        c = self.rocket_canvas
        s = scale
        body_w = 42 * s
        body_h = 84 * s
        left = x - body_w / 2
        top = y - body_h / 2
        right = x + body_w / 2
        bottom = y + body_h / 2

        if flying:
            c.create_polygon(
                x - 13 * s, bottom - 2 * s,
                x + 13 * s, bottom - 2 * s,
                x + 2 * s, bottom + 48 * s,
                x - 2 * s, bottom + 48 * s,
                fill=Theme.TRAIL, outline="",
            )
            c.create_polygon(
                x - 9 * s, bottom,
                x + 9 * s, bottom,
                x + 2 * s, bottom + 31 * s,
                x - 2 * s, bottom + 31 * s,
                fill=Theme.FLAME_LIGHT, outline="",
            )
            c.create_polygon(
                x - 5 * s, bottom,
                x + 5 * s, bottom,
                x, bottom + 22 * s,
                fill=Theme.FLAME, outline="",
            )

        c.create_polygon(
            left, bottom - 28 * s,
            left - 18 * s, bottom + 10 * s,
            left + 3 * s, bottom - 2 * s,
            fill=Theme.ROCKET_NOSE, outline=Theme.ROCKET_EDGE, width=2,
        )
        c.create_polygon(
            right, bottom - 28 * s,
            right + 18 * s, bottom + 10 * s,
            right - 3 * s, bottom - 2 * s,
            fill=Theme.ROCKET_NOSE, outline=Theme.ROCKET_EDGE, width=2,
        )
        c.create_rectangle(
            left, top + 22 * s, right, bottom,
            fill=Theme.ROCKET_BODY, outline=Theme.ROCKET_EDGE, width=2,
        )
        c.create_polygon(
            left, top + 24 * s,
            right, top + 24 * s,
            x, top - 8 * s,
            fill=Theme.ROCKET_NOSE, outline=Theme.ROCKET_EDGE, width=2,
        )
        c.create_oval(
            x - 11 * s, top + 34 * s,
            x + 11 * s, top + 56 * s,
            fill=Theme.ROCKET_WINDOW, outline=Theme.ACCENT, width=2,
        )
        c.create_line(
            left + 7 * s, top + 66 * s, right - 7 * s, top + 66 * s,
            fill=Theme.BORDER, width=2,
        )

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, value))

    @classmethod
    def _smoothstep(cls, edge0: float, edge1: float, value: float) -> float:
        if edge1 <= edge0:
            return 1.0 if value >= edge1 else 0.0
        t = cls._clamp((value - edge0) / (edge1 - edge0))
        return t * t * (3.0 - 2.0 * t)

    @staticmethod
    def _blend_color(color_a: str, color_b: str, amount: float) -> str:
        amount = max(0.0, min(1.0, amount))
        a = tuple(int(color_a[i:i + 2], 16) for i in (1, 3, 5))
        b = tuple(int(color_b[i:i + 2], 16) for i in (1, 3, 5))
        rgb = tuple(round(av + (bv - av) * amount) for av, bv in zip(a, b))
        return "#{:02X}{:02X}{:02X}".format(*rgb)

    def _multiplier_to_progress(self, multiplier: float) -> float:
        """Map 1×..500× to continuous flight distance on a logarithmic route."""
        m = max(1.0, min(self.DESTINATION_MULTIPLIER, float(multiplier)))
        return self._clamp(math.log(m) / math.log(self.DESTINATION_MULTIPLIER))

    @classmethod
    def _base_flight_step(cls, multiplier: float) -> float:
        if multiplier < 2.0:
            return 0.02
        if multiplier < 5.0:
            return 0.05
        if multiplier < 10.0:
            return 0.10
        if multiplier < 20.0:
            return 0.20
        if multiplier < 50.0:
            return 0.50
        if multiplier < 100.0:
            return 1.00
        if multiplier < 200.0:
            return 2.00
        return 5.00

    @classmethod
    def _flight_step(cls, multiplier: float) -> float:
        """R3 runs at exactly 25% of the R2 multiplier speed."""
        return cls._base_flight_step(multiplier) * cls.SPEED_SCALE

    def _stage_for_multiplier(self, multiplier: float) -> str:
        m = float(multiplier)
        if m >= 500.0:
            return "抵达冥王星"
        if 200.0 <= m <= 220.0:
            return "经过海王星"
        if 100.0 <= m <= 110.0:
            return "经过天王星"
        if 50.0 <= m <= 55.0:
            return "经过土星"
        if 20.0 <= m <= 22.0:
            return "经过木星"
        if 10.0 <= m <= 11.0:
            return "经过火星"
        if 5.0 <= m <= 5.5:
            return "经过月球"
        if 2.5 <= m <= 3.0:
            return "进入太空"
        if 2.0 <= m < 2.5:
            return "穿越大气层"
        if m < 2.0:
            return "垂直升空"
        return "深空航行"

    def _rocket_y_for_distance(self, h: int, distance: float) -> float:
        """Rocket rises from the pad, then stays in a forward cruise window."""
        start_y = h - 132
        atmosphere_p = self._multiplier_to_progress(2.6)
        launch_mix = self._smoothstep(0.0, atmosphere_p, distance)
        cruise_y = h * 0.47
        y = start_y + (cruise_y - start_y) * launch_mix
        deep_mix = self._smoothstep(self._multiplier_to_progress(3.0), 1.0, distance)
        return y - 38.0 * deep_mix

    def _draw_star_field(self, w: int, h: int, intensity: float, scroll: float, background: str) -> None:
        c = self.rocket_canvas
        intensity = self._clamp(intensity)
        count = int(72 * intensity)
        if count <= 0:
            return
        for i in range(count):
            x = 18 + ((i * 97 + 41) % max(80, w - 36))
            base_y = 10 + ((i * 53 + 17) % max(80, h - 20))
            speed = 0.35 + (i % 5) * 0.09
            y = (base_y + scroll * speed) % (h + 30) - 15
            strength = intensity * (0.58 + (i % 4) * 0.12)
            fill = self._blend_color(background, Theme.STAR, min(1.0, strength))
            r = 1 if i % 5 else 2
            c.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline="")

    def _draw_planet(
        self,
        name: str,
        x: float,
        y: float,
        radius: float,
        fill: str,
        *,
        proximity: float = 0.0,
    ) -> None:
        c = self.rocket_canvas
        proximity = self._clamp(proximity)
        active = proximity > 0.55
        outline = Theme.AMBER if active else Theme.PLANET_LINE
        width = 4 if active else 2

        if name == "土星":
            c.create_oval(
                x - radius * 1.75, y - radius * 0.55,
                x + radius * 1.75, y + radius * 0.55,
                outline=outline, width=3,
            )
        c.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill=fill, outline=outline, width=width,
        )
        if name == "木星":
            for offset in (-0.38, 0.0, 0.36):
                yy = y + radius * offset
                c.create_line(x - radius * 0.82, yy, x + radius * 0.82, yy, fill="#A5795F", width=3)
        elif name == "火星":
            c.create_oval(x - radius * .35, y - radius * .2, x - radius * .05, y + radius * .1, fill="#8F5548", outline="")
        elif name == "月球":
            c.create_oval(x - radius * .45, y - radius * .25, x - radius * .15, y + radius * .05, fill="#AAA59E", outline="")
            c.create_oval(x + radius * .12, y + radius * .08, x + radius * .42, y + radius * .38, fill="#AAA59E", outline="")
        elif name == "冥王星":
            c.create_oval(x - radius * .18, y - radius * .18, x + radius * .18, y + radius * .18, fill="#8D7769", outline="")
        c.create_text(
            x,
            y + radius + 14,
            text=name,
            fill="#FFFFFF",
            font=(Theme.FONT_CJK, 12, "bold"),
            anchor=tk.N,
        )

    def _draw_milestone_cloud(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        fill: str,
        text: str,
        text_fill: str,
    ) -> None:
        """Draw one soft cloud-shaped milestone badge."""
        c = self.rocket_canvas

        left = x
        top = y - height / 2
        right = x + width
        bottom = y + height / 2

        # 云朵主体
        c.create_oval(
            left + 4,
            top + height * 0.28,
            left + height * 0.78,
            bottom,
            fill=fill,
            outline="",
        )

        c.create_oval(
            left + width * 0.20,
            top + 1,
            left + width * 0.48,
            bottom - 1,
            fill=fill,
            outline="",
        )

        c.create_oval(
            left + width * 0.40,
            top + height * 0.12,
            left + width * 0.70,
            bottom,
            fill=fill,
            outline="",
        )

        c.create_oval(
            right - height * 0.86,
            top + height * 0.31,
            right - 2,
            bottom,
            fill=fill,
            outline="",
        )

        c.create_rectangle(
            left + height * 0.42,
            top + height * 0.48,
            right - height * 0.42,
            bottom,
            fill=fill,
            outline="",
        )

        # --------------------------------------------------
        # 文字往云朵下方移动 20px
        # --------------------------------------------------
        c.create_text(
            left + width / 2,
            y + 8,
            text=text,
            fill=text_fill,
            font=(Theme.FONT_CJK, 16, "bold"),
            anchor=tk.CENTER,
        )

    def _draw_route_markers(
        self,
        w: int,
        h: int,
        distance: float,
        top_color: str,
        bottom_color: str,
    ) -> None:
        """Render the left MILESTONES as 30%-transparent cloud badges."""
        markers = (
            (500.0, "500× 冥王星"),
            (200.0, "200× 海王星"),
            (100.0, "100× 天王星"),
            (50.0, "50× 土星"),
            (20.0, "20× 木星"),
            (10.0, "10× 火星"),
            (5.0, "5× 月球"),
            (2.5, "2.5× 太空"),
            (2.0, "2× 大气层"),
        )

        # Fixed, evenly spaced cloud positions keep 16px labels from
        # colliding.  The actual scenery/planet positions still use the true
        # logarithmic flight-distance coordinates elsewhere in draw_scene().
        cloud_x = 14
        cloud_width = 184
        cloud_height = 40
        top_center = 52
        bottom_center = h - 34
        spacing = (bottom_center - top_center) / max(1, len(markers) - 1)

        current_multiplier = max(1.0, self.current_multiplier)

        for index, (multiplier, label) in enumerate(markers):
            y = top_center + index * spacing
            progress = self._multiplier_to_progress(multiplier)
            passed = distance >= progress

            # Approximate a true 30% alpha cloud by blending the cloud colour
            # into the continuously changing local sky colour.
            y_mix = self._clamp(y / max(1.0, float(h)))
            local_sky = self._blend_color(top_color, bottom_color, y_mix)
            cloud_fill = self._blend_color(local_sky, Theme.CLOUD, 0.30)

            # The currently crossed milestone receives amber text; previous
            # milestones remain clearly readable without becoming dominant.
            if multiplier <= current_multiplier:
                text_fill = Theme.AMBER if abs(current_multiplier - multiplier) <= max(0.06, multiplier * 0.03) else Theme.TEXT
            else:
                text_fill = Theme.TEXT_MUTED

            self._draw_milestone_cloud(
                cloud_x, y, cloud_width, cloud_height,
                fill=cloud_fill,
                text=label,
                text_fill=text_fill,
            )

    def _draw_atmosphere_band(self, w: int, rocket_y: float, distance: float) -> None:
        """A moving band gives the 2× atmosphere transition physical depth."""
        c = self.rocket_canvas
        atmosphere_p = self._multiplier_to_progress(2.0)
        band_y = rocket_y - (atmosphere_p - distance) * self.WORLD_SCALE
        if -90 <= band_y <= c.winfo_height() + 90:
            for offset, width, shade in ((-28, 2, "#D9E5E7"), (-10, 3, "#C9DBDF"), (12, 2, "#B9D0D6"), (30, 1, "#A9C4CC")):
                c.create_line(0, band_y + offset, w, band_y + offset, fill=shade, width=width)

    def draw_scene(self) -> None:
        if not hasattr(self, "rocket_canvas") or not self.rocket_canvas.winfo_exists():
            return
        c = self.rocket_canvas
        w, h = self._canvas_size()
        c.delete("all")

        multiplier = max(1.0, self.current_multiplier)
        distance = self.flight_distance if self.phase in {"flying", "result"} else self._multiplier_to_progress(multiplier)
        distance = self._clamp(distance)
        stage = self._stage_for_multiplier(multiplier)

        # Continuous sky -> atmosphere -> space blend.  No threshold swaps the whole scene.
        fade_start = self._multiplier_to_progress(1.25)
        fade_end = self._multiplier_to_progress(3.1)
        space_mix = self._smoothstep(fade_start, fade_end, distance)
        top_color = self._blend_color(Theme.ATMOSPHERE_TOP, Theme.SPACE_DEEP, space_mix)
        bottom_color = self._blend_color(Theme.ATMOSPHERE_LOW, Theme.SPACE, space_mix)

        bands = 18
        for i in range(bands):
            t = i / max(1, bands - 1)
            band_color = self._blend_color(top_color, bottom_color, t)
            y0 = round(i * h / bands)
            y1 = round((i + 1) * h / bands) + 1
            c.create_rectangle(0, y0, w, y1, fill=band_color, outline="")

        star_intensity = self._smoothstep(
            self._multiplier_to_progress(1.7),
            self._multiplier_to_progress(3.2),
            distance,
        )
        self._draw_star_field(w, h, star_intensity, distance * 1550.0, bottom_color)

        rocket_y = self._rocket_y_for_distance(h, distance)
        rocket_x = w * 0.50

        # Earth and clouds physically scroll downward as the rocket travels upward.
        ground_base = h - 74
        ground_scroll = distance * 1050.0
        ground_y = ground_base + ground_scroll
        if ground_y < h + 120:
            c.create_rectangle(0, ground_y, w, h + 120, fill=Theme.GROUND, outline="")
            c.create_rectangle(0, ground_y + 42, w, h + 120, fill=Theme.GROUND_DARK, outline="")
            c.create_rectangle(280, ground_y + 28, 465, ground_y + 42, fill=Theme.PAD, outline=Theme.PAD_DARK, width=2)

        cloud_fade = 1.0 - self._smoothstep(
            self._multiplier_to_progress(1.55),
            self._multiplier_to_progress(2.9),
            distance,
        )
        cloud_fill = self._blend_color(bottom_color, Theme.CLOUD, cloud_fade)
        for x, base_y, scale, speed in (
            (105, 110, 0.78, 0.74),
            (w - 205, 178, 0.64, 0.92),
            (310, 34, 0.52, 1.10),
        ):
            y = base_y + distance * 820.0 * speed
            if y < h + 55 and cloud_fade > 0.04:
                self._draw_cloud(x, y, scale, cloud_fill)

        self._draw_atmosphere_band(w, rocket_y, distance)

        # Solar-system objects exist in one continuous world coordinate system.
        planet_specs = (
            (5.25, "月球", 575, 27, Theme.MOON),
            (10.5, "火星", 205, 31, Theme.MARS),
            (21.0, "木星", 570, 45, Theme.JUPITER),
            (52.5, "土星", 195, 39, Theme.SATURN),
            (105.0, "天王星", 565, 34, Theme.URANUS),
            (210.0, "海王星", 205, 35, Theme.NEPTUNE),
            (500.0, "冥王星", 555, 27, Theme.PLUTO),
        )
        if star_intensity > 0.10 or distance >= self._multiplier_to_progress(3.0):
            for midpoint, name, px, base_radius, fill in planet_specs:
                planet_distance = self._multiplier_to_progress(midpoint)
                py = rocket_y - (planet_distance - distance) * self.WORLD_SCALE
                if -110 <= py <= h + 110:
                    proximity = 1.0 - min(1.0, abs(py - rocket_y) / 280.0)
                    radius = base_radius * (0.88 + 0.18 * proximity)
                    self._draw_planet(name, px, py, radius, fill, proximity=proximity)

        # Top-right status board remains fixed HMI chrome while scenery scrolls beneath it.
        board_fill = self._blend_color("#DCE3DD", "#D5D9D4", space_mix)
        c.create_rectangle(450, 22, w - 24, 126, fill=board_fill, outline=Theme.BORDER_SOFT, width=1)
        c.create_text(468, 38, text="当前倍数", fill=Theme.TEXT_MUTED, font=(Theme.FONT_CJK, 10, "bold"), anchor=tk.NW)
        c.create_text(
            w - 42, 50, text=self.canvas_multiplier_var.get(),
            fill=Theme.ACCENT if self.phase != "result" else (Theme.GREEN if self.last_win > 0 else Theme.RED),
            font=(Theme.FONT, 32, "bold"), anchor=tk.NE,
        )

        self._draw_route_markers(w, h, distance, top_color, bottom_color)

        if self.phase == "countdown":
            c.create_text(
                w / 2, h / 2 - 20,
                text=str(self.countdown_value) if self.countdown_value > 0 else "GO",
                fill=Theme.ACCENT if self.countdown_value > 0 else Theme.GREEN,
                font=(Theme.FONT, 54, "bold"),
            )
            c.create_text(w / 2, h / 2 + 42, text="垂直发射准备", fill=Theme.TEXT_MUTED, font=(Theme.FONT_CJK, 14, "bold"))
            self._draw_rocket_vector(rocket_x, h - 132, 1.55, flying=False)
            return

        if self.phase == "flying":
            self._trail_points.append((rocket_x, rocket_y + 70))
            self._trail_points = self._trail_points[-42:]
            if len(self._trail_points) >= 2:
                flat = [coord for point in self._trail_points for coord in point]
                c.create_line(*flat, fill=Theme.TRAIL, width=11, smooth=True)
                c.create_line(*flat, fill=Theme.ACCENT_SOFT, width=4, smooth=True)

            if self.target_multiplier < 1_000_000 and self.target_multiplier <= self.DESTINATION_MULTIPLIER:
                target_distance = self._multiplier_to_progress(self.target_multiplier)
                target_y = rocket_y - (target_distance - distance) * self.WORLD_SCALE
                if 20 <= target_y <= h - 20:
                    c.create_line(118, target_y, w - 72, target_y, fill=Theme.AMBER, width=2, dash=(7, 5))
                    c.create_text(
                        w - 78, target_y - 10,
                        text=f"自动兑现 {self.target_multiplier:.2f}×",
                        fill=Theme.AMBER, font=(Theme.FONT_CJK, 9, "bold"), anchor=tk.E,
                    )

            self._draw_rocket_vector(rocket_x, rocket_y, 1.62, flying=True)
            return

        if self.phase == "result" and self.last_result:
            if self.last_win <= 0:
                cx, cy = rocket_x, rocket_y
                for i in range(18):
                    angle = (2 * math.pi / 18) * i
                    radius = 34 + (i % 4) * 9
                    px = cx + math.cos(angle) * radius
                    py = cy + math.sin(angle) * radius
                    size = 18 + (i % 3) * 7
                    c.create_oval(
                        px - size, py - size, px + size, py + size,
                        fill=Theme.EXPLOSION_LIGHT if i % 2 else Theme.EXPLOSION, outline="",
                    )
                c.create_text(cx, cy, text="!", fill="#FFFFFF", font=(Theme.FONT, 40, "bold"))
            else:
                self._draw_rocket_vector(rocket_x, rocket_y, 1.58, flying=False)

            c.create_rectangle(128, h - 168, w - 128, h - 80, fill=Theme.PANEL, outline=Theme.BORDER, width=1)
            c.create_text(
                w / 2, h - 124, text=self.last_result,
                fill=Theme.GREEN if self.last_win > 0 else Theme.RED,
                font=(Theme.FONT_CJK, 14, "bold"), justify=tk.CENTER,
            )
            return

        self._trail_points.clear()
        self._draw_rocket_vector(rocket_x, h - 132, 1.55, flying=False)
        c.create_text(
            rocket_x, h - 235, text="火箭准备垂直升空",
            fill=Theme.TEXT, font=(Theme.FONT_CJK, 19, "bold"), anchor=tk.CENTER,
        )

    # ------------------------------------------------------------------
    # Probability model
    # ------------------------------------------------------------------

    @classmethod
    def generate_boom_multiplier(cls) -> float:
        """Lock the hidden round outcome before launch using a 96% crash curve.

        For any target multiplier X below the 500× cap:
            P(reach X) ~= RTP / X

        Values whose sampled crash point reaches or exceeds 500× are converted to
        the Pluto destination outcome.  Therefore P(reach 500×) ~= 0.96 / 500,
        about 0.192% (roughly 1 in 521 rounds), rather than the old 1% jackpot.
        """
        roll = max(random.random(), 1e-12)
        raw_multiplier = cls.RTP / roll

        if raw_multiplier >= cls.DESTINATION_MULTIPLIER:
            return cls.DESTINATION_MULTIPLIER

        # Floor rather than round so the displayed crash point never promises a
        # survival probability higher than the sampled continuous curve.
        crash = math.floor(raw_multiplier * 100.0) / 100.0
        return max(1.0, min(cls.DESTINATION_MULTIPLIER - 0.01, crash))

    # Compatibility helpers retained for callers/tests that used the old API.
    def generate_probability_table(self, max_multiplier, C=100, k=1.5):
        probability_table = []
        multiplier = 1.01
        while multiplier <= max_multiplier:
            prob = C / (multiplier ** k)
            probability_table.append((round(multiplier, 2), prob))
            multiplier += 0.01 if multiplier < 2 else 0.1 if multiplier < 10 else 1
        total_prob = sum(prob for _, prob in probability_table)
        return [(m, (p / total_prob) * 100) for m, p in probability_table]

    # ------------------------------------------------------------------
    # Betting / state
    # ------------------------------------------------------------------

    def add_chip(self, amount: str) -> None:
        if self.game_active:
            return
        try:
            amount_val = float(amount)
        except ValueError:
            return
        new_bet = self.current_bet + amount_val
        if new_bet <= self.balance:
            self.current_bet = new_bet
            self.update_display()

    def reset_bet(self) -> None:
        if self.game_active:
            return
        self.current_bet = 0.0
        self.update_display()

    def _parse_auto_target(self) -> Optional[float]:
        raw = self.auto_cash_var.get().strip()
        if not raw:
            return 1_000_000.0
        try:
            value = float(raw)
        except ValueError:
            messagebox.showwarning("错误", "请输入有效的自动兑现倍数", parent=self.root)
            return None
        if value < 1.01:
            messagebox.showwarning("错误", "自动兑现倍数必须大于或等于 1.01", parent=self.root)
            return None
        if value > self.DESTINATION_MULTIPLIER:
            messagebox.showwarning("错误", "自动兑现最高为 500×；500× 即抵达冥王星并结束游戏。", parent=self.root)
            return None
        return value

    def start_game(self) -> None:
        if self.game_active or self.phase in {"countdown", "flying"}:
            return
        if self.current_bet <= 0:
            messagebox.showwarning("错误", "请先下注", parent=self.root)
            return
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注", parent=self.root)
            return

        target = self._parse_auto_target()
        if target is None:
            return
        self.target_multiplier = target

        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        update_balance_in_json(self.username, self.balance)

        self.boom_multiplier = self.generate_boom_multiplier()
        self._multiplier_exact = 1.0
        self.current_multiplier = 1.0
        self.flight_distance = 0.0
        self.game_active = True
        self.game_running = True
        self.last_result = ""
        self.phase = "countdown"
        self.countdown_value = 3
        self._time_to_increase = self.FLIGHT_TICK_MS
        self._trail_points.clear()

        self._set_round_controls(True)
        self.update_display()
        self.draw_scene()
        self._schedule_countdown_step()

    def _schedule_countdown_step(self) -> None:
        self._cancel_job("_countdown_job")
        self._countdown_job = self.root.after(1000, self._countdown_step)

    def _countdown_step(self) -> None:
        self._countdown_job = None
        if not self.game_active or self.phase != "countdown":
            return
        self.countdown_value -= 1
        if self.countdown_value > 0:
            self.draw_scene()
            self._schedule_countdown_step()
            return
        if self.countdown_value == 0:
            self.draw_scene()
            self._countdown_job = self.root.after(700, self._begin_flight)

    def _begin_flight(self) -> None:
        self._countdown_job = None
        if not self.game_active:
            return
        self.phase = "flying"
        self.cash_out_button.configure(state=tk.NORMAL)
        self._multiplier_exact = 1.0
        self.current_multiplier = 1.00
        self.flight_distance = 0.0
        self.status_var.set("火箭垂直升空")
        self.badge_var.set("垂直升空")
        self._refresh_badge(Theme.ACCENT_SOFT, Theme.ACCENT)
        self.update_display()
        self.draw_scene()
        self._schedule_flight_tick()

    def _schedule_flight_tick(self) -> None:
        self._cancel_job("_flight_job")
        self._flight_job = self.root.after(self.FLIGHT_TICK_MS, self._flight_tick)

    def _flight_tick(self) -> None:
        self._flight_job = None
        if not self.game_running or not self.game_active or self.phase != "flying":
            return

        step = self._flight_step(self._multiplier_exact)
        next_exact = min(self.DESTINATION_MULTIPLIER, self._multiplier_exact + step)

        # Both thresholds are locked before launch.  Compare against the internal
        # high-precision multiplier so slowing the animation never changes odds.
        if (
            self.target_multiplier < self.boom_multiplier
            and self.target_multiplier <= next_exact
        ):
            self._multiplier_exact = self.target_multiplier
            self.current_multiplier = round(self.target_multiplier, 2)
            self.flight_distance = self._multiplier_to_progress(self._multiplier_exact)
            self.update_display()
            self.draw_scene()
            self.auto_cash_out()
            return

        if (
            self.boom_multiplier < self.DESTINATION_MULTIPLIER
            and self.boom_multiplier <= next_exact
        ):
            self._multiplier_exact = self.boom_multiplier
            self.current_multiplier = self.boom_multiplier
            self.flight_distance = self._multiplier_to_progress(self._multiplier_exact)
            self.update_display()
            self.draw_scene()
            self.explode()
            return

        self._multiplier_exact = next_exact
        self.current_multiplier = round(next_exact, 2)
        self.flight_distance = self._multiplier_to_progress(next_exact)

        stage = self._stage_for_multiplier(self.current_multiplier)
        self.status_var.set(f"{stage} · 在爆炸前兑现。")
        self.badge_var.set(stage)
        self._refresh_badge(Theme.ACCENT_SOFT, Theme.ACCENT)
        self.update_display()
        self.draw_scene()

        if next_exact >= self.DESTINATION_MULTIPLIER:
            self.reach_destination()
            return

        self._schedule_flight_tick()

    def cash_out(self) -> None:
        if not self.game_active or self.phase != "flying":
            return
        self.game_running = False
        self.manual_cash_out()

    def manual_cash_out(self) -> None:
        if not self.game_active:
            return
        win_amount = self.bet_amount * self.current_multiplier
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        self.game_running = False
        update_balance_in_json(self.username, self.balance)

        self.last_result = (
            f"手动兑现成功 · {self.current_multiplier:.2f}×\n"
            f"返还 ${win_amount:,.2f}"
        )
        self._finish_round(success=True)

    def auto_cash_out(self) -> None:
        if not self.game_active:
            return
        # Preserve the original settlement rule: target multiplier is used exactly.
        win_amount = self.bet_amount * self.target_multiplier
        self.balance += win_amount
        self.last_win = win_amount
        self.current_multiplier = max(self.current_multiplier, self.target_multiplier)
        self.game_active = False
        self.game_running = False
        update_balance_in_json(self.username, self.balance)

        self.last_result = (
            f"自动兑现成功 · {self.target_multiplier:.2f}×\n"
            f"返还 ${win_amount:,.2f}"
        )
        self._finish_round(success=True)

    def reach_destination(self) -> None:
        """Finish a 500× round successfully at Pluto."""
        if not self.game_active:
            return
        self._multiplier_exact = self.DESTINATION_MULTIPLIER
        self.current_multiplier = self.DESTINATION_MULTIPLIER
        self.flight_distance = 1.0
        win_amount = self.bet_amount * self.DESTINATION_MULTIPLIER
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        self.game_running = False
        update_balance_in_json(self.username, self.balance)
        self.last_result = (
            f"成功抵达冥王星 · {self.DESTINATION_MULTIPLIER:.2f}×\n"
            f"返还 ${win_amount:,.2f}"
        )
        self._finish_round(success=True)

    def explode(self) -> None:
        if not self.game_active:
            return
        self._multiplier_exact = self.boom_multiplier
        self.current_multiplier = self.boom_multiplier
        self.flight_distance = self._multiplier_to_progress(self.boom_multiplier)
        self.game_active = False
        self.game_running = False
        self.last_win = 0.0
        self.last_result = f"爆炸于 {self.boom_multiplier:.2f}×\n本局下注未返还"
        update_balance_in_json(self.username, self.balance)
        self._finish_round(success=False)

    def _finish_round(self, *, success: bool) -> None:
        self._cancel_job("_flight_job")
        self._cancel_job("_countdown_job")
        self.phase = "result"
        if success:
            destination = (
                self.current_multiplier >= self.DESTINATION_MULTIPLIER
                and self.boom_multiplier >= self.DESTINATION_MULTIPLIER
            )
            if destination:
                self.status_var.set("成功抵达冥王星 · 500× 航程完成。")
                self.badge_var.set("抵达终点")
                self._refresh_badge("#D8CC9E", Theme.AMBER)
            else:
                self.status_var.set("兑现成功 · 本局资金已结算。")
                self.badge_var.set("已兑现")
                self._refresh_badge("#C8D9C8", Theme.GREEN)
        else:
            self.status_var.set("火箭爆炸 · 本局下注归零。")
            self.badge_var.set("已爆炸")
            self._refresh_badge("#E3C0BB", Theme.RED)
        self._set_round_controls(False)
        self.update_display()
        self.draw_scene()
        self._result_job = self.root.after(2600, self.end_game)

    def end_game(self) -> None:
        self._result_job = None
        self.phase = "idle"
        self._multiplier_exact = 1.0
        self.current_multiplier = 1.0
        self.flight_distance = 0.0
        self.target_multiplier = 1_000_000.0
        self.boom_multiplier = 0.0
        self.game_active = False
        self.game_running = False
        self.last_result = ""
        self.status_var.set("设置下注金额后开始飞行。")
        self.badge_var.set("待机")
        self._refresh_badge(Theme.ACCENT_SOFT, Theme.ACCENT)
        self._set_round_controls(False)
        self.update_display()
        self.draw_scene()

    def _set_round_controls(self, active: bool) -> None:
        state = tk.DISABLED if active else tk.NORMAL
        for button in self.chip_buttons:
            button.configure(state=state)
        self.auto_cash_entry.configure(state=state)
        self.start_button.configure(state=state)

        if active:
            self.reset_bet_button.place_forget()
            self.cash_out_button.configure(
                state=tk.DISABLED if self.phase == "countdown" else tk.NORMAL
            )
            self.cash_out_button.place(x=0, y=42, width=322, height=self.ACTION_BUTTON_HEIGHT)
        else:
            self.cash_out_button.place_forget()
            self.reset_bet_button.place(x=0, y=0, width=322, height=self.ACTION_BUTTON_HEIGHT)
            self.start_button.place(x=0, y=42, width=322, height=self.ACTION_BUTTON_HEIGHT)

    def _refresh_badge(self, background: str, foreground: str) -> None:
        if hasattr(self, "badge_label"):
            self.badge_label.configure(bg=background, fg=foreground)

    def update_display(self) -> None:
        self.balance_var.set(f"${self.balance:,.2f}")
        self.bet_var.set(f"${self.current_bet:,.2f}")
        self.last_win_var.set(f"${self.last_win:,.2f}")
        self.multiplier_var.set(f"{self.current_multiplier:.2f}×")
        self.canvas_multiplier_var.set(f"{self.current_multiplier:.2f}×")

        live_bet = self.bet_amount if self.game_active or self.phase == "result" else self.current_bet
        potential = live_bet * self.current_multiplier if live_bet > 0 else 0.0
        self.potential_var.set(f"${potential:,.2f}")

        if self.target_multiplier >= 1_000_000:
            raw = self.auto_cash_var.get().strip()
            if not self.game_active and raw:
                try:
                    parsed = float(raw)
                    self.auto_target_var.set(f"{parsed:.2f}×" if parsed >= 1.01 else "无效")
                except ValueError:
                    self.auto_target_var.set("无效")
            else:
                self.auto_target_var.set("关闭")
        else:
            self.auto_target_var.set(f"{self.target_multiplier:.2f}×")

    def _cancel_job(self, attr_name: str) -> None:
        job = getattr(self, attr_name, None)
        if job is not None:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
            setattr(self, attr_name, None)

    def on_closing(self) -> None:
        for attr in ("_countdown_job", "_flight_job", "_result_job"):
            self._cancel_job(attr)
        self.game_active = False
        self.game_running = False
        update_balance_in_json(self.username, self.balance)
        finish = getattr(self.root, "finish", None)
        if callable(finish):
            finish(self.balance)
        else:
            try:
                self.root.destroy()
            except tk.TclError:
                pass


# ---------------------------------------------------------------------------
# Entry point — standalone + EmbeddedGamePage
# ---------------------------------------------------------------------------


def main(
    initial_balance: float = 1000.0,
    username: str = "Guest",
    *,
    parent=None,
    balance: Optional[float] = None,
    user: Optional[str] = None,
    on_back: Optional[Callable[[float], None]] = None,
    on_balance_change: Optional[Callable[[float], None]] = None,
):
    effective_balance = float(balance if balance is not None else initial_balance)
    effective_user = str(user if user is not None else username)

    if parent is not None:
        page = EmbeddedGamePage(
            parent,
            title="火箭升空",
            username=effective_user,
            balance=effective_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        game = RocketGame(page.host, effective_balance, effective_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = RocketGame(root, effective_balance, effective_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    main(10000.0, "test_user")