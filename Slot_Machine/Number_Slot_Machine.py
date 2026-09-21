"""Number Slot Machine — ChickenCrossing-style physical-reel R2.

R2 gameplay:
- Bet = $5 × an integer multiplier selected before the spin.
- Three traditional cyclic reels:
    left/right: 1-2-3-4-5-6-7-8-9-1...
    middle:     0-1-2-3-4-5-6-7-8-9-0...
- Reels have no time-based stop condition. Each reel accelerates until its own
  mechanical target speed, then loses speed through drag. Near rest, its fractional
  position eases to the nearest payline index (upward/downward by remaining fraction).
- Each reel is rendered inside its own clipped Canvas, so symbols cannot escape
  through the top/bottom of the physical reel window.
- Total-return payouts (stake included):
    any pair                    = $6 × multiplier
    any triple                  = $100 × multiplier
    ascending straight         = $40 × multiplier
    descending straight        = $40 × multiplier
    middle 0, side values differ = $10 × multiplier
- If middle=0 and left=right, "0时间" starts:
    10 suitcase values are integers from 20..50 with exact average 35.
    Base pool: [20,23,27,30,34,36,40,43,47,50].
    The cases are first opened, then closed and physically rotate continuously
    along a closed track for 10 seconds; individual case numbers are never shown.
    The player chooses one case; its value × multiplier is the total return.

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
import math
import os
import random
import sys
import time
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional

try:
    from .slot_machine import EmbeddedGamePage
except ImportError:
    try:
        from Slot_Machine.slot_machine import EmbeddedGamePage
    except ImportError:
        EmbeddedGamePage = None


VERSION = "SlotMachine-ChickenStyle-R5"


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

    REEL_WELL = "#434A51"
    REEL_FACE = "#F1EDE5"
    REEL_TEXT = "#252A2E"
    REEL_FADE = "#8E969C"
    REEL_EDGE = "#8E877E"
    PAYLINE = "#D2B24D"

    CASE = "#B28A58"
    CASE_EDGE = "#725436"
    CASE_HANDLE = "#5E4630"
    CASE_OPEN = "#E2CB91"
    CASE_SELECTED = "#B8CFB6"
    CASE_HOVER = "#C7A97A"

    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )


BONUS_BASE_VALUES = [20, 23, 27, 30, 34, 36, 40, 43, 47, 50]


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


def classify_result(d1: int, d2: int, d3: int) -> str:
    """Return the R2 payout class in precedence order."""
    if d2 == 0 and d1 == d3:
        return "zero_time_zero"
    if d1 == d2 == d3:
        return "triple"
    if d2 == d1 + 1 and d3 == d2 + 1:
        return "straight"
    if d2 == d1 - 1 and d3 == d2 - 1:
        return "reverse"
    if d1 == d2 or d2 == d3 or d1 == d3:
        return "pair"
    if d2 == 0:
        return "middle_zero"
    return "none"


def payout_for_class(result_class: str, multiplier: int) -> int:
    multiplier = int(multiplier)
    base = {
        "pair": 6,
        "triple": 100,
        "straight": 40,
        "reverse": 40,
        "middle_zero": 10,
        "none": 0,
    }.get(result_class, 0)
    return int(base * multiplier)


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
        self.bind("<Enter>", self._enter, add="+")
        self.bind("<Leave>", self._leave, add="+")

    def _enter(self, _event) -> None:
        if str(self.cget("state")) != tk.DISABLED:
            super().configure(bg=self.hover_background)

    def _leave(self, _event) -> None:
        super().configure(bg=self.normal_background)


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


class NumberSlotMachine:
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

    BASE_BET = 5.0
    MAX_MULTIPLIER = 20

    REEL_SEQUENCES = (
        tuple(range(1, 10)),
        tuple(range(0, 10)),
        tuple(range(1, 10)),
    )

    # Intentionally different mechanical characteristics.  R3 uses a much
    # stronger launch and NO elapsed-time transition.  A reel accelerates until
    # it physically reaches its target speed, then drag alone slows it down.
    BASE_ACCEL = (46.0, 54.0, 62.0)        # symbols / s²
    TARGET_SPEED_RANGES = (
        (22.0, 25.5),
        (28.5, 32.0),
        (33.0, 36.5),
    )                                       # symbols / s, re-randomized every spin
    BASE_DRAG = (0.58, 0.52, 0.47)         # exponential speed loss / s
    ALIGN_THRESHOLD = 1.45                  # symbols / s

    REEL_WIDTH = 146
    REEL_HEIGHT = 197
    REEL_GAP = 22
    REEL_TOP_Y = 72
    REEL_SPACING = 62

    def __init__(self, root, initial_balance: float, username: str):
        self.root = root
        self._configure_root()

        self.balance = float(initial_balance)
        self.username = username
        self.multiplier = 1
        self.last_win = 0.0

        self.spinning = False
        self.in_bonus = False
        self.bonus_phase = "idle"
        self.after_id: Optional[str] = None
        self.last_frame_time = 0.0

        self.reel_positions = [6.0, 0.0, 6.0]
        self.reel_velocities = [0.0, 0.0, 0.0]
        # Displayed speed is measured from the actual position travelled each
        # physics frame, rather than inferred from the internal velocity state.
        self.reel_display_speeds = [0.0, 0.0, 0.0]
        self.reel_states = ["idle", "idle", "idle"]
        self.reel_accels = list(self.BASE_ACCEL)
        self.reel_target_speeds = [sum(bounds) / 2.0 for bounds in self.TARGET_SPEED_RANGES]
        self.reel_drags = list(self.BASE_DRAG)
        self.reel_align_targets: list[Optional[int]] = [None, None, None]
        self.reel_canvases: list[tk.Canvas] = []
        self.reel_canvas_places: list[tuple[int, int, int, int]] = []
        self.final_result = [7, 0, 7]

        self.bonus_values = list(BONUS_BASE_VALUES)
        self.bonus_order = list(range(10))
        self.bonus_rects: list[tuple[float, float, float, float]] = []
        self.bonus_hover: Optional[int] = None
        self.bonus_shuffle_started = 0.0
        self.bonus_last_frame_time = 0.0
        self.bonus_rotation_offset = 0.0
        self.bonus_rotation_velocity = 0.0
        self.bonus_rotation_target_speed = 0.0
        self.bonus_rotation_accel = 0.0
        self.bonus_selected_position: Optional[int] = None
        self.pending_result = [0, 0, 0]

        self.balance_var = tk.StringVar()
        self.bet_var = tk.StringVar()
        self.last_win_var = tk.StringVar()
        self.multiplier_var = tk.StringVar()
        self.result_var = tk.StringVar(value="按下开始抽奖")
        self.status_var = tk.StringVar(value="传统物理滚轮待机")
        self.motion_var = tk.StringVar(value="静止")

        self.pair_var = tk.StringVar()
        self.triple_var = tk.StringVar()
        self.straight_reverse_var = tk.StringVar()
        self.middle_zero_var = tk.StringVar()
        self.bonus_range_var = tk.StringVar()

        self.payout_row_widgets: dict[str, tuple[tk.Label, tk.Label, str]] = {}
        self.highlighted_payout_class: Optional[str] = None

        self.create_widgets()
        self.update_display()

    # ------------------------------------------------------------------
    # Root / layout
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("数字老虎机")
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
            x=padding,
            y=padding,
            width=max(1, width - padding * 2),
            height=max(1, height - padding * 2),
        )
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
        icon.create_text(24, 24, text="777", fill=Theme.ACCENT, font=(Theme.FONT, 9, "bold"))

        tk.Label(
            header,
            text="NUMBER SLOT",
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT, 18, "bold"),
            anchor=tk.W,
        ).place(x=74, y=10, width=340, height=27)

        tk.Label(
            header,
            text="数字老虎机 · $5",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 11, "bold"),
            anchor=tk.W,
        ).place(x=74, y=39, width=430, height=20)

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
            balance_box,
            text="账户余额",
            bg=Theme.PANEL_ALT,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9),
            anchor=tk.W,
        ).place(x=12, y=4, width=90, height=17)

        tk.Label(
            balance_box,
            textvariable=self.balance_var,
            bg=Theme.PANEL_ALT,
            fg=Theme.ACCENT,
            font=(Theme.FONT, 15, "bold"),
            anchor=tk.E,
        ).place(x=12, y=20, width=182, height=22)

    def _build_game_panel(self, master: tk.Frame) -> None:
        panel = self._card(master, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT, padding=0)
        panel.place(x=0, y=0, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT)

        top = tk.Frame(panel, width=self.CANVAS_WIDTH, height=70, bg=Theme.PANEL)
        top.place(x=0, y=0, width=self.CANVAS_WIDTH, height=70)

        tk.Label(
            top,
            textvariable=self.result_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 16, "bold"),
            anchor=tk.W,
        ).place(x=18, y=9, width=520, height=28)

        tk.Label(
            top,
            textvariable=self.status_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.W,
        ).place(x=18, y=40, width=530, height=18)

        tk.Label(
            top,
            textvariable=self.motion_var,
            bg=Theme.ACCENT_SOFT,
            fg=Theme.ACCENT,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.CENTER,
        ).place(x=584, y=18, width=142, height=30)

        self.game_canvas = tk.Canvas(
            panel,
            width=self.CANVAS_WIDTH,
            height=self.CANVAS_HEIGHT,
            bg=Theme.CANVAS_BG,
            bd=0,
            highlightthickness=0,
        )
        self.game_canvas.place(x=1, y=70, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT)
        self.game_canvas.bind("<Motion>", self._on_canvas_motion)
        self.game_canvas.bind("<Leave>", self._on_canvas_leave)
        self.game_canvas.bind("<Button-1>", self._on_canvas_click)

        # Three independent child Canvases provide real clipping.  Unlike the
        # R2 masking trick, symbols physically cannot draw outside these windows.
        reel_total = self.REEL_WIDTH * 3 + self.REEL_GAP * 2
        reel_start_x = int(round((self.CANVAS_WIDTH - reel_total) / 2))
        for reel_index in range(3):
            x = 1 + reel_start_x + reel_index * (self.REEL_WIDTH + self.REEL_GAP)
            y = 70 + self.REEL_TOP_Y
            reel_canvas = tk.Canvas(
                panel,
                width=self.REEL_WIDTH,
                height=self.REEL_HEIGHT,
                bg=Theme.REEL_FACE,
                bd=0,
                highlightthickness=3,
                highlightbackground=Theme.REEL_EDGE,
            )
            reel_canvas.place(
                x=x, y=y,
                width=self.REEL_WIDTH,
                height=self.REEL_HEIGHT,
            )
            self.reel_canvases.append(reel_canvas)
            self.reel_canvas_places.append((x, y, self.REEL_WIDTH, self.REEL_HEIGHT))

        self.draw_scene()

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
            sidebar, "本局下注", self.bet_var, Theme.CYAN,
            width=169, height=68,
        ).place(x=0, y=0, width=169, height=68)

        MetricTile(
            sidebar, "上局返还", self.last_win_var, Theme.GREEN,
            width=169, height=68,
        ).place(x=179, y=0, width=169, height=68)

        payout = self._card(sidebar, width=348, height=220, padding=9)
        payout.place(x=0, y=78, width=348, height=220)
        self._section_title(payout.content, "返还表").place(x=0, y=0, width=150, height=20)

        table = tk.Frame(
            payout.content,
            bg=Theme.BORDER_SOFT,
            bd=1,
            relief=tk.SOLID,
        )
        table.place(x=0, y=28, width=322, height=172)

        rows = (
            ("pair", "任意2个一样", self.pair_var),
            ("middle_zero", "中轮 0 / 两侧不一", self.middle_zero_var),
            ("zero_time_zero", "中轮 0 / 两侧一样", self.bonus_range_var),
            ("straight_reverse", "顺子 / 倒顺", self.straight_reverse_var),
            ("triple", "任意3个一样", self.triple_var),
        )

        for row, (result_key, label, variable) in enumerate(rows):
            bg = Theme.PANEL_ALT if row % 2 == 0 else Theme.PANEL
            name_label = tk.Label(
                table,
                text=label,
                bg=bg,
                fg=Theme.TEXT,
                font=(Theme.FONT_CJK, 8, "bold"),
                anchor=tk.W,
                padx=7,
            )
            name_label.grid(row=row, column=0, sticky="nsew")

            value_label = tk.Label(
                table,
                textvariable=variable,
                bg=bg,
                fg=Theme.AMBER,
                font=(Theme.FONT, 9, "bold"),
                anchor=tk.E,
                padx=7,
            )
            value_label.grid(row=row, column=1, sticky="nsew")
            self.payout_row_widgets[result_key] = (name_label, value_label, bg)

        for row in range(len(rows)):
            table.rowconfigure(row, weight=1)
        table.columnconfigure(0, weight=3)
        table.columnconfigure(1, weight=2)

        multiplier_card = self._card(sidebar, width=348, height=122, padding=9)
        multiplier_card.place(x=0, y=308, width=348, height=122)
        self._section_title(multiplier_card.content, "选择下注倍数").place(x=0, y=0, width=130, height=20)

        self.minus_button = ModernButton(
            multiplier_card.content,
            text="−",
            command=lambda: self.change_multiplier(-1),
            background=Theme.PANEL_ALT,
            hover_background=Theme.PANEL_HOVER,
            foreground=Theme.TEXT,
            font_size=16,
            bold=True,
        )
        self.minus_button.place(x=0, y=27, width=58, height=36)

        tk.Label(
            multiplier_card.content,
            textvariable=self.multiplier_var,
            bg=Theme.ACCENT_SOFT,
            fg=Theme.ACCENT,
            font=(Theme.FONT, 16, "bold"),
            anchor=tk.CENTER,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        ).place(x=68, y=27, width=186, height=36)

        self.plus_button = ModernButton(
            multiplier_card.content,
            text="+",
            command=lambda: self.change_multiplier(1),
            background=Theme.PANEL_ALT,
            hover_background=Theme.PANEL_HOVER,
            foreground=Theme.TEXT,
            font_size=16,
            bold=True,
        )
        self.plus_button.place(x=264, y=27, width=58, height=36)

        self.multiplier_quick_buttons = []
        for index, mult in enumerate((1, 5, 10, 20)):
            button = ModernButton(
                multiplier_card.content,
                text=f"{mult}×",
                command=lambda value=mult: self.set_multiplier(value),
                background=Theme.PANEL_ALT,
                hover_background=Theme.PANEL_HOVER,
                foreground=Theme.TEXT,
                font_size=9,
                bold=True,
            )
            button.place(x=index * 81, y=72, width=76, height=27)
            self.multiplier_quick_buttons.append(button)

        actions = self._card(sidebar, width=348, height=91, padding=9)
        actions.place(x=0, y=440, width=348, height=91)

        self.spin_button = ModernButton(
            actions.content,
            text="开始抽奖",
            command=self.start_spin,
            background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.spin_button.place(x=0, y=0, width=322, height=36)

        tk.Label(
            actions.content,
            text="下注倍数 1–20×（每局最多 $100）；\n滚轮由机械速度衰减并自动对齐中线。",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8),
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=322,
        ).place(x=0, y=43, width=322, height=30)

        rules = self._card(sidebar, width=348, height=89, padding=9)
        rules.place(x=0, y=541, width=348, height=89)
        self._section_title(rules.content, "0时间").place(x=0, y=0, width=80, height=20)

        tk.Label(
            rules.content,
            text=(
                "条件：中轮为 0 且左右相同。\n"
                "基础奖 20–50，再乘下注倍数。"
            ),
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8),
            justify=tk.LEFT,
            anchor=tk.NW,
            wraplength=322,
        ).place(x=0, y=25, width=322, height=49)

    # ------------------------------------------------------------------
    # Multiplier / payout UI
    # ------------------------------------------------------------------

    @property
    def current_bet(self) -> float:
        return self.BASE_BET * self.multiplier

    def _clear_payout_highlight(self) -> None:
        self.highlighted_payout_class = None
        for _key, (name_label, value_label, original_bg) in self.payout_row_widgets.items():
            name_label.configure(bg=original_bg, fg=Theme.TEXT)
            value_label.configure(bg=original_bg, fg=Theme.AMBER)

    def _highlight_payout_row(self, result_class: str) -> None:
        self._clear_payout_highlight()
        # Straight and reverse-straight share one visual row in the payout table.
        visual_key = "straight_reverse" if result_class in {"straight", "reverse"} else result_class
        widgets = self.payout_row_widgets.get(visual_key)
        if widgets is None:
            return
        self.highlighted_payout_class = result_class
        name_label, value_label, _original_bg = widgets
        gold = "#D4B55E"
        name_label.configure(bg=gold, fg=Theme.TEXT)
        value_label.configure(bg=gold, fg=Theme.TEXT)

    def set_multiplier(self, value: int) -> None:
        if self.spinning or self.in_bonus:
            return
        value = max(1, min(self.MAX_MULTIPLIER, int(value)))
        if value == self.multiplier:
            return
        self.multiplier = value
        # A multiplier change starts a new betting configuration, so any
        # previous winning-row highlight returns to its original colour.
        self._clear_payout_highlight()
        self.update_display()

    def change_multiplier(self, delta: int) -> None:
        self.set_multiplier(self.multiplier + int(delta))

    def _set_bet_controls_enabled(self, enabled: bool) -> None:
        if not enabled:
            self.minus_button.configure(state=tk.DISABLED)
            self.plus_button.configure(state=tk.DISABLED)
            for button in self.multiplier_quick_buttons:
                button.configure(state=tk.DISABLED)
            return

        self.minus_button.configure(
            state=tk.NORMAL if self.multiplier > 1 else tk.DISABLED
        )
        self.plus_button.configure(
            state=tk.NORMAL if self.multiplier < self.MAX_MULTIPLIER else tk.DISABLED
        )
        for button in self.multiplier_quick_buttons:
            button.configure(state=tk.NORMAL)

    # ------------------------------------------------------------------
    # Physical reel model
    # ------------------------------------------------------------------

    def start_spin(self) -> None:
        if self.spinning or self.in_bonus:
            return

        if self.balance < self.current_bet:
            messagebox.showwarning(
                "余额不足",
                f"本局需要 ${self.current_bet:,.2f}。",
                parent=self.root,
            )
            return

        self.balance -= self.current_bet
        self.last_win = 0.0
        self._clear_payout_highlight()
        update_balance_in_json(self.username, self.balance)

        # Keep the previous aligned positions as the mechanical starting point.
        self.reel_velocities = [0.0, 0.0, 0.0]
        self.reel_display_speeds = [0.0, 0.0, 0.0]
        self.reel_states = ["accelerating", "accelerating", "accelerating"]
        self.reel_align_targets = [None, None, None]

        # Per-spin tolerance makes the final symbol emerge from the travelled
        # distance.  There is no stop time and no acceleration timer.
        self.reel_accels = [
            base * random.uniform(0.96, 1.06)
            for base in self.BASE_ACCEL
        ]
        self.reel_target_speeds = [
            random.uniform(low, high)
            for low, high in self.TARGET_SPEED_RANGES
        ]
        self.reel_drags = [
            base * random.uniform(0.96, 1.05)
            for base in self.BASE_DRAG
        ]

        self.spinning = True
        self.last_frame_time = time.monotonic()
        self.result_var.set("物理滚轮启动")
        self.status_var.set("加速 → 惯性衰减 → 中线对齐")
        self.spin_button.configure(state=tk.DISABLED)
        self._set_bet_controls_enabled(False)

        self._physics_frame()
        self.update_display()

    def _physics_frame(self) -> None:
        if not self.spinning:
            return

        now = time.monotonic()
        dt = max(0.001, min(0.045, now - self.last_frame_time))
        self.last_frame_time = now

        all_stopped = True
        speeds = []

        for index in range(3):
            state = self.reel_states[index]
            velocity = self.reel_velocities[index]
            position_before = self.reel_positions[index]

            if state == "accelerating":
                all_stopped = False
                velocity += self.reel_accels[index] * dt
                target_speed = self.reel_target_speeds[index]
                if velocity >= target_speed:
                    velocity = target_speed
                    self.reel_states[index] = "decelerating"
                self.reel_positions[index] += velocity * dt

            elif state == "decelerating":
                all_stopped = False

                # Exponential drag: no stop timestamp is involved.
                velocity *= math.exp(-self.reel_drags[index] * dt)
                self.reel_positions[index] += velocity * dt

                if abs(velocity) <= self.ALIGN_THRESHOLD:
                    position = self.reel_positions[index]
                    fraction = position - math.floor(position)

                    # Nearest-index alignment. fraction < .5 eases downward
                    # to floor(position), fraction >= .5 eases upward to ceil.
                    target = math.floor(position) if fraction < 0.5 else math.ceil(position)
                    self.reel_align_targets[index] = int(target)
                    self.reel_states[index] = "aligning"

            elif state == "aligning":
                all_stopped = False
                target = self.reel_align_targets[index]
                if target is None:
                    target = round(self.reel_positions[index])
                    self.reel_align_targets[index] = int(target)

                error = float(target) - self.reel_positions[index]

                # Smooth final seating into the payline.  Direction is chosen
                # by the sign of the remaining fractional error.
                self.reel_positions[index] += error * min(1.0, dt * 4.4)
                velocity *= math.exp(-4.8 * dt)

                if abs(error) < 0.0025:
                    self.reel_positions[index] = float(target)
                    velocity = 0.0
                    self.reel_states[index] = "stopped"

            elif state == "stopped":
                velocity = 0.0

            self.reel_velocities[index] = velocity
            # Real-time displayed speed = actual symbols travelled / actual frame time.
            actual_speed = abs(self.reel_positions[index] - position_before) / dt
            if self.reel_states[index] == "stopped":
                actual_speed = 0.0
            self.reel_display_speeds[index] = actual_speed
            speeds.append(actual_speed)

        self.motion_var.set(
            "滚动中"
        )
        self.draw_scene()

        if all_stopped:
            self._finish_physical_spin()
            return

        self.after_id = self.root.after(16, self._physics_frame)

    def _symbol_from_position(self, reel_index: int) -> int:
        sequence = self.REEL_SEQUENCES[reel_index]
        index = int(round(self.reel_positions[reel_index])) % len(sequence)
        return int(sequence[index])

    def _finish_physical_spin(self) -> None:
        self.spinning = False
        self.after_id = None
        self.final_result = [
            self._symbol_from_position(0),
            self._symbol_from_position(1),
            self._symbol_from_position(2),
        ]

        d1, d2, d3 = self.final_result
        result_class = classify_result(d1, d2, d3)
        self.motion_var.set("已对齐")
        self.draw_scene()

        if result_class == "zero_time_zero":
            self._start_zero_time_zero()
            return

        payout = payout_for_class(result_class, self.multiplier)
        self._settle_regular(result_class, payout)

    # ------------------------------------------------------------------
    # 0时间
    # ------------------------------------------------------------------

    def _start_zero_time_zero(self) -> None:
        self.in_bonus = True
        self.bonus_phase = "reveal"
        self.pending_result = list(self.final_result)
        self.bonus_values = list(BONUS_BASE_VALUES)
        random.shuffle(self.bonus_values)
        self.bonus_order = list(range(10))
        self.bonus_selected_position = None
        self.bonus_hover = None
        self.bonus_rotation_offset = 0.0
        self.bonus_rotation_velocity = 0.0
        self.bonus_rotation_target_speed = random.uniform(4.6, 6.4)
        self.bonus_rotation_accel = random.uniform(8.5, 11.5)

        self.result_var.set("0时间")
        self.status_var.set("先公开 10 个行李箱奖励")
        self.motion_var.set("奖励公开")
        self.spin_button.configure(state=tk.DISABLED)
        self._set_bet_controls_enabled(False)
        self.draw_scene()

        # Briefly show all contents before the shuffle begins.
        self.after_id = self.root.after(1500, self._begin_bonus_shuffle)

    def _begin_bonus_shuffle(self) -> None:
        if not self.in_bonus:
            return
        self.bonus_phase = "shuffle"
        self.bonus_shuffle_started = time.monotonic()
        self.bonus_last_frame_time = self.bonus_shuffle_started
        self.status_var.set("行李箱已关闭 · 沿闭合轨道物理转动中")
        self.motion_var.set("10.0 秒")
        self.draw_scene()
        self._bonus_shuffle_frame()

    def _bonus_shuffle_frame(self) -> None:
        if not self.in_bonus or self.bonus_phase != "shuffle":
            return

        now = time.monotonic()
        elapsed = now - self.bonus_shuffle_started
        dt = max(0.001, min(0.045, now - self.bonus_last_frame_time))
        self.bonus_last_frame_time = now
        remaining = max(0.0, 10.0 - elapsed)
        self.motion_var.set(f"{remaining:0.1f} 秒")

        if elapsed >= 10.0:
            # Convert the continuous travelled distance into the final physical
            # slot positions, then reset the drawing offset to the aligned grid.
            shift = int(round(self.bonus_rotation_offset)) % 10
            if shift:
                final_order = [0] * 10
                for original_position, case_id in enumerate(self.bonus_order):
                    final_order[(original_position + shift) % 10] = case_id
                self.bonus_order = final_order

            self.bonus_rotation_offset = 0.0
            self.bonus_rotation_velocity = 0.0
            self.bonus_phase = "choose"
            self.bonus_hover = None
            self.status_var.set("转动完成 · 请选择 1 个行李箱")
            self.motion_var.set("请选择")
            self.after_id = None
            self.draw_scene()
            return

        # Physical continuous rotation on a closed 10-position track.  The
        # boxes accelerate under drive, coast near their mechanical target,
        # then progressively lose speed near the end.  No case teleports or
        # instantaneously swaps places during the animation.
        if remaining <= 0.8:
            # Final mechanical seating happens inside the original 10-second
            # shuffle window, so the cases visibly settle onto real slots
            # instead of jumping to an aligned position at the end.
            target_slot = round(self.bonus_rotation_offset)
            error = float(target_slot) - self.bonus_rotation_offset
            self.bonus_rotation_offset += error * min(1.0, dt * 7.5)
            self.bonus_rotation_velocity *= math.exp(-7.0 * dt)
        else:
            if elapsed < 7.4:
                self.bonus_rotation_velocity = min(
                    self.bonus_rotation_target_speed,
                    self.bonus_rotation_velocity + self.bonus_rotation_accel * dt,
                )
            else:
                # Smooth braking before the final seating phase.
                brake_fraction = max(0.0, min(1.0, remaining / 2.6))
                desired_speed = self.bonus_rotation_target_speed * (brake_fraction ** 1.7)
                response = min(1.0, dt * 5.5)
                self.bonus_rotation_velocity += (
                    desired_speed - self.bonus_rotation_velocity
                ) * response

            self.bonus_rotation_offset = (
                self.bonus_rotation_offset + self.bonus_rotation_velocity * dt
            ) % 10.0

        self.draw_scene()
        self.after_id = self.root.after(16, self._bonus_shuffle_frame)

    def _bonus_position_at(self, x: float, y: float) -> Optional[int]:
        if self.bonus_phase != "choose":
            return None
        for position, rect in enumerate(self.bonus_rects):
            x1, y1, x2, y2 = rect
            if x1 <= x <= x2 and y1 <= y <= y2:
                return position
        return None

    def _on_canvas_motion(self, event) -> None:
        if not self.in_bonus or self.bonus_phase != "choose":
            return
        hovered = self._bonus_position_at(event.x, event.y)
        if hovered != self.bonus_hover:
            self.bonus_hover = hovered
            self.draw_scene()

    def _on_canvas_leave(self, _event) -> None:
        if self.bonus_hover is not None:
            self.bonus_hover = None
            self.draw_scene()

    def _on_canvas_click(self, event) -> None:
        if not self.in_bonus or self.bonus_phase != "choose":
            return
        position = self._bonus_position_at(event.x, event.y)
        if position is None:
            return
        self.choose_bonus_case(position)

    def choose_bonus_case(self, position: int) -> None:
        if not self.in_bonus or self.bonus_phase != "choose":
            return
        if not (0 <= position < 10):
            return

        self.bonus_selected_position = position
        case_id = self.bonus_order[position]
        base_value = int(self.bonus_values[case_id])
        total_return = int(base_value * self.multiplier)

        self.bonus_phase = "selected"
        self.bonus_hover = None
        self.status_var.set(
            f"所选行李箱：基础 ${base_value} × {self.multiplier} = ${total_return}"
        )
        self.motion_var.set("已打开")
        self.draw_scene()

        self.after_id = self.root.after(
            1300,
            lambda: self._finish_bonus(total_return),
        )

    def _finish_bonus(self, total_return: int) -> None:
        self.after_id = None
        self.in_bonus = False
        self.bonus_phase = "idle"
        self.last_win = float(total_return)
        self.balance += float(total_return)
        self._highlight_payout_row("zero_time_zero")

        d1, d2, d3 = self.pending_result
        self.result_var.set(f"{d1} - {d2} - {d3} · 0时间 返还 ${total_return}")
        self.status_var.set("奖励已计入余额")
        self.motion_var.set("完成")

        update_balance_in_json(self.username, self.balance)
        self.spin_button.configure(state=tk.NORMAL)
        self._set_bet_controls_enabled(True)
        self.update_display()

    # ------------------------------------------------------------------
    # Settlement
    # ------------------------------------------------------------------

    def _settle_regular(self, result_class: str, payout: int) -> None:
        labels = {
            "triple": "3 个一样",
            "straight": "顺子",
            "reverse": "倒顺",
            "pair": "2 个一样",
            "middle_zero": "中轮 0",
            "none": "未中奖",
        }
        d1, d2, d3 = self.final_result

        self.last_win = float(payout)
        if payout > 0:
            self.balance += float(payout)
            self._highlight_payout_row(result_class)
            self.result_var.set(f"{d1} - {d2} - {d3} · 返还 ${payout}")
            self.status_var.set(labels[result_class])
        else:
            self.result_var.set(f"{d1} - {d2} - {d3} · 未中奖")
            self.status_var.set("本局返还 $0")

        update_balance_in_json(self.username, self.balance)
        self.spin_button.configure(state=tk.NORMAL)
        self._set_bet_controls_enabled(True)
        self.update_display()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _set_reel_canvases_visible(self, visible: bool) -> None:
        for reel_canvas, (x, y, width, height) in zip(
            self.reel_canvases, self.reel_canvas_places
        ):
            if visible:
                reel_canvas.place(x=x, y=y, width=width, height=height)
            else:
                reel_canvas.place_forget()

    def draw_scene(self) -> None:
        if self.in_bonus:
            self._set_reel_canvases_visible(False)
            self._draw_zero_time_zero()
        else:
            self._draw_machine()
            self._set_reel_canvases_visible(True)

    def _draw_machine(self) -> None:
        c = self.game_canvas
        c.delete("all")
        self.bonus_rects = []

        w = self.CANVAS_WIDTH
        h = self.CANVAS_HEIGHT
        c.create_rectangle(0, 0, w, h, fill=Theme.CANVAS_BG, outline="")

        c.create_rectangle(
            68, 28, w - 68, 360,
            fill=Theme.PANEL_ALT,
            outline=Theme.BORDER,
            width=2,
        )
        c.create_rectangle(
            92, 56, w - 92, 286,
            fill=Theme.REEL_WELL,
            outline=Theme.REEL_EDGE,
            width=3,
        )

        reel_w = self.REEL_WIDTH
        gap = self.REEL_GAP
        total = reel_w * 3 + gap * 2
        start_x = (w - total) / 2
        top_y = self.REEL_TOP_Y
        bottom_y = top_y + self.REEL_HEIGHT
        center_y = (top_y + bottom_y) / 2
        spacing = self.REEL_SPACING

        # Main Canvas draws the cabinet/well.  The moving symbol strips are
        # rendered inside three child Canvases, which provide real clipping.
        for reel_index, reel_canvas in enumerate(self.reel_canvases):
            x1 = start_x + reel_index * (reel_w + gap)
            x2 = x1 + reel_w
            sequence = self.REEL_SEQUENCES[reel_index]
            position = self.reel_positions[reel_index]

            # Keep an exact window footprint in the cabinet behind the child.
            c.create_rectangle(
                x1, top_y, x2, bottom_y,
                fill=Theme.REEL_FACE, outline=Theme.REEL_EDGE, width=3,
            )
            c.create_text(
                (x1 + x2) / 2,
                bottom_y + 18,
                text=f"REEL {reel_index + 1}",
                fill=Theme.TEXT_MUTED,
                font=(Theme.FONT, 8, "bold"),
            )

            reel_canvas.delete("all")
            reel_canvas.configure(bg=Theme.REEL_FACE)
            local_center_y = self.REEL_HEIGHT / 2
            base_index = math.floor(position)

            for strip_index in range(base_index - 4, base_index + 5):
                symbol = sequence[strip_index % len(sequence)]
                y = local_center_y + (strip_index - position) * spacing
                distance = abs(y - local_center_y)

                if distance < 18:
                    font_size = 36
                    fill = Theme.REEL_TEXT
                elif distance < 78:
                    font_size = 25
                    fill = "#5B6268"
                else:
                    font_size = 18
                    fill = Theme.REEL_FADE

                reel_canvas.create_text(
                    self.REEL_WIDTH / 2,
                    y,
                    text=str(symbol),
                    fill=fill,
                    font=(Theme.FONT, font_size, "bold"),
                )

            # Payline lives inside the clipped reel too, while the main canvas
            # draws matching segments through the gaps.
            reel_canvas.create_line(
                0, local_center_y, self.REEL_WIDTH, local_center_y,
                fill=Theme.PAYLINE, width=4,
            )
            reel_canvas.create_line(
                0, local_center_y - 5, self.REEL_WIDTH, local_center_y - 5,
                fill="#E8D38B", width=1,
            )

        # Payline is drawn after the symbols so the mechanical centre is obvious.
        c.create_line(
            98, center_y, w - 98, center_y,
            fill=Theme.PAYLINE,
            width=4,
        )
        c.create_line(
            98, center_y - 5, w - 98, center_y - 5,
            fill="#E8D38B",
            width=1,
        )

        # Reel physics status cards.
        card_y = 392
        card_w = 181
        card_gap = 18
        total_cards = card_w * 3 + card_gap * 2
        start = (w - total_cards) / 2

        for index in range(3):
            x1 = start + index * (card_w + card_gap)
            x2 = x1 + card_w
            state = self.reel_states[index]
            state_label = {
                "idle": "待机",
                "accelerating": "加速",
                "decelerating": "减速",
                "aligning": "对齐",
                "stopped": "停止",
            }.get(state, state)

            c.create_rectangle(
                x1, card_y, x2, card_y + 79,
                fill=Theme.PANEL_ALT,
                outline=Theme.BORDER_SOFT,
                width=1,
            )
            c.create_text(
                x1 + 12, card_y + 18,
                text=f"滚轮 {index + 1}",
                fill=Theme.TEXT_MUTED,
                font=(Theme.FONT_CJK, 8, "bold"),
                anchor=tk.W,
            )
            c.create_text(
                x1 + 12, card_y + 43,
                text=state_label,
                fill=Theme.ACCENT,
                font=(Theme.FONT_CJK, 11, "bold"),
                anchor=tk.W,
            )
            c.create_text(
                x2 - 12, card_y + 43,
                text=f"{self.reel_display_speeds[index]:.1f}",
                fill=Theme.TEXT,
                font=(Theme.FONT, 11, "bold"),
                anchor=tk.E,
            )
            c.create_text(
                x2 - 12, card_y + 62,
                text="格/秒",
                fill=Theme.TEXT_DIM,
                font=(Theme.FONT_CJK, 7),
                anchor=tk.E,
            )

        c.create_text(
            52, 507,
            text=(
                f"本局下注：$5 × {self.multiplier} = ${self.current_bet:,.0f}"
                "    ·    中轮 0 且左右相同会进入「0时间」"
            ),
            fill=Theme.TEXT,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.W,
        )

    def _bonus_case_slots(self) -> list[tuple[float, float]]:
        """Return the 10 closed-track suitcase top-left anchor positions."""
        cols = 5
        case_w = 112
        case_h = 116
        gap_x = 18
        gap_y = 30
        total_w = cols * case_w + (cols - 1) * gap_x
        start_x = (self.CANVAS_WIDTH - total_w) / 2
        start_y = 137

        top = [
            (start_x + col * (case_w + gap_x), start_y)
            for col in range(cols)
        ]
        bottom_y = start_y + case_h + gap_y
        bottom = [
            (start_x + col * (case_w + gap_x), bottom_y)
            for col in reversed(range(cols))
        ]
        return top + bottom

    def _bonus_track_point(self, track_position: float) -> tuple[float, float]:
        """Interpolate continuously between neighbouring physical slots."""
        anchors = self._bonus_case_slots()
        wrapped = track_position % 10.0
        base = int(math.floor(wrapped))
        fraction = wrapped - base
        x1, y1 = anchors[base]
        x2, y2 = anchors[(base + 1) % 10]

        # Smoothstep keeps motion continuous while softening each corner of the
        # closed path without changing the box identity or reward.
        eased = fraction * fraction * (3.0 - 2.0 * fraction)
        return (
            x1 + (x2 - x1) * eased,
            y1 + (y2 - y1) * eased,
        )

    def _draw_zero_time_zero(self) -> None:
        c = self.game_canvas
        c.delete("all")
        self.bonus_rects = []

        w = self.CANVAS_WIDTH
        h = self.CANVAS_HEIGHT
        c.create_rectangle(0, 0, w, h, fill=Theme.CANVAS_BG, outline="")

        c.create_rectangle(
            42, 24, w - 42, h - 24,
            fill=Theme.PANEL_ALT,
            outline=Theme.BORDER,
            width=2,
        )

        c.create_text(
            w / 2, 58,
            text="0时间",
            fill=Theme.TEXT,
            font=(Theme.FONT_CJK, 24, "bold"),
        )

        subtitle = {
            "reveal": "10 个行李箱先公开里面的奖励",
            "shuffle": "行李箱关闭并沿闭合轨道物理转动 10 秒",
            "choose": "打乱完成 · 请选择 1 个行李箱",
            "selected": "已打开所选行李箱",
        }.get(self.bonus_phase, "")

        c.create_text(
            w / 2, 91,
            text=subtitle,
            fill=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 10, "bold"),
        )

        case_w = 112
        case_h = 116
        anchors = self._bonus_case_slots()

        for position in range(10):
            if self.bonus_phase == "shuffle":
                x1, y1 = self._bonus_track_point(position + self.bonus_rotation_offset)
            else:
                x1, y1 = anchors[position]

            x2 = x1 + case_w
            y2 = y1 + case_h

            # Click rectangles are only meaningful after the physical rotation
            # has stopped and the cases are aligned to their fixed slots.
            if self.bonus_phase == "shuffle":
                self.bonus_rects.append((0.0, 0.0, 0.0, 0.0))
            else:
                self.bonus_rects.append((x1, y1, x2, y2))

            case_id = self.bonus_order[position]
            value = self.bonus_values[case_id]

            reveal_value = self.bonus_phase == "reveal"
            selected = self.bonus_phase == "selected" and self.bonus_selected_position == position
            hovered = self.bonus_phase == "choose" and self.bonus_hover == position

            if selected:
                fill = Theme.CASE_SELECTED
                outline = Theme.GREEN
            elif reveal_value:
                fill = Theme.CASE_OPEN
                outline = Theme.AMBER
            elif hovered:
                fill = Theme.CASE_HOVER
                outline = Theme.ACCENT
            else:
                fill = Theme.CASE
                outline = Theme.CASE_EDGE

            # Handle.
            c.create_rectangle(
                x1 + 38, y1 - 9,
                x1 + 74, y1 + 9,
                fill=Theme.CASE_HANDLE,
                outline=Theme.CASE_EDGE,
                width=2,
            )
            c.create_rectangle(
                x1, y1, x2, y2,
                fill=fill,
                outline=outline,
                width=3 if (hovered or selected) else 2,
            )
            c.create_line(
                x1 + 8, y1 + 34,
                x2 - 8, y1 + 34,
                fill=Theme.CASE_EDGE,
                width=2,
            )
            c.create_rectangle(
                (x1 + x2) / 2 - 8, y1 + 28,
                (x1 + x2) / 2 + 8, y1 + 44,
                fill="#D9C089",
                outline=Theme.CASE_EDGE,
                width=1,
            )

            if reveal_value or selected:
                displayed = f"${value * self.multiplier}"
                c.create_text(
                    (x1 + x2) / 2,
                    y1 + 76,
                    text=displayed,
                    fill=Theme.TEXT,
                    font=(Theme.FONT, 15, "bold"),
                )
                c.create_text(
                    (x1 + x2) / 2,
                    y1 + 97,
                    text=f"基础 {value}",
                    fill=Theme.TEXT_MUTED,
                    font=(Theme.FONT_CJK, 7),
                )
            else:
                c.create_text(
                    (x1 + x2) / 2,
                    y1 + 78,
                    text="?",
                    fill="#F6EEE0",
                    font=(Theme.FONT, 25, "bold"),
                )

        if self.bonus_phase == "reveal":
            footer = "公开后会自动关闭并开始打乱"
        elif self.bonus_phase == "shuffle":
            footer = "箱子内容保持不变；箱体沿轨道连续转动，不瞬移交换"
        elif self.bonus_phase == "choose":
            footer = "点击一个箱子打开；只能选择一次"
        else:
            footer = "所选奖励将直接作为本局总返还（已含本金）"

        c.create_text(
            w / 2, 475,
            text=footer,
            fill=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9, "bold"),
        )

        c.create_text(
            w / 2, 505,
            text=f"10 个基础值平均 = $35 · 当前下注倍数 {self.multiplier}×",
            fill=Theme.ACCENT,
            font=(Theme.FONT_CJK, 9, "bold"),
        )

    # ------------------------------------------------------------------
    # Display / closing
    # ------------------------------------------------------------------

    def update_display(self) -> None:
        self.balance_var.set(f"${self.balance:,.2f}")
        self.bet_var.set(f"${self.current_bet:,.2f}")
        self.last_win_var.set(f"${self.last_win:,.2f}")
        self.multiplier_var.set(
            f"{self.multiplier}×   ·   本局 ${self.current_bet:,.0f}"
        )

        m = self.multiplier
        self.pair_var.set(f"${6 * m:,}")
        self.triple_var.set(f"${100 * m:,}")
        self.straight_reverse_var.set(f"${40 * m:,}")
        self.middle_zero_var.set(f"${10 * m:,}")
        self.bonus_range_var.set(f"${20 * m:,}–${50 * m:,}")

        self.spin_button.configure(
            text=f"开始抽奖 · ${self.current_bet:,.0f}"
        )
        if not self.spinning and not self.in_bonus:
            self._set_bet_controls_enabled(True)
        self.draw_scene()

    def on_closing(self) -> None:
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None

        self.spinning = False
        self.in_bonus = False
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
                "EmbeddedGamePage is unavailable. Place slot_machine.py inside "
                "the Small_Games package or make small_games.py importable."
            )
        page = EmbeddedGamePage(
            parent,
            title="数字老虎机",
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        page.set_requested_size(1150, 750)
        game = NumberSlotMachine(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = NumberSlotMachine(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    final_balance = main(10000.0, "demo_player")
    print(f"Final balance: {final_balance:.2f}")