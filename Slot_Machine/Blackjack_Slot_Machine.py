"""Daval Reel "21" Blackjack — five-reel mechanical slot recreation.

This version is built from the existing ChickenCrossing-style slot framework:
- Bet = $5 × 1..10 units ($5..$50 per game).
- Five physical cyclic reels, each with 11 equally likely stops.
- Reel order on screen: DEAL 1, DEAL 2, HOUSE, DRAW 3, DRAW 4.
- HOUSE / DRAW 3 / DRAW 4 use animated mechanical shutters that physically slide.
- After the reels stop, the player may reveal DRAW 3, then optionally DRAW 4,
  or reveal HOUSE to stand. Revealing HOUSE permanently locks unopened draw reels.
- Player must stay at 21 or below. Matching HOUSE is a push and returns the wager.
- HOUSE reel also carries the payout multiplier.
- Modern casino paytable: optimal-play theoretical RTP is about 90.595%.
- Special BLACK JACK: Blank + 10 + (1 or 11) on DRAW 3,
  with HOUSE "BEAT 21 / PAYS 80".

The 11-stop reel inventories are based on the documented Daval Reel "21"
trade stimulator (circa 1936).
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
from typing import Callable, Optional, Union

try:
    from .slot_machine import EmbeddedGamePage
except ImportError:
    try:
        from Slot_Machine.slot_machine import EmbeddedGamePage
    except ImportError:
        EmbeddedGamePage = None


VERSION = "Reel21-Blackjack-R4"


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

    REEL_WELL = "#343A3F"
    REEL_FACE = "#F4E9D0"
    REEL_TEXT = "#22201D"
    REEL_FADE = "#8A8176"
    REEL_EDGE = "#7B736A"
    PAYLINE = "#C9A632"

    SHUTTER = "#4D5256"
    SHUTTER_DARK = "#353A3E"
    SHUTTER_EDGE = "#23272A"
    BRASS = "#B58A35"
    BRASS_LIGHT = "#D9B75A"

    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )


# ----------------------------------------------------------------------
# Historical 11-stop reel strips.
# Display order is 1, 2, HOUSE (historical Reel 5), 3, 4.
# ----------------------------------------------------------------------

CardStop = Union[int, str]
HouseStop = tuple[int, int]

REEL_1: tuple[CardStop, ...] = (
    5, "blank", 6, 5, 7, 6, 5, 6, 5, 7, 6,
)

REEL_2: tuple[CardStop, ...] = (
    7, 8, 9, 7, 8, 10, 7, 8, 9, 7, 8,
)

REEL_3: tuple[CardStop, ...] = (
    2, 10, 3, 2, 10, "ace", 2, 10, 3, 2, 10,
)

REEL_4: tuple[CardStop, ...] = (
    10, 2, "ace", 9, 10, 3, 2, 9, 10, 8, 9,
)

# Modernized integer paytable while preserving the historical HOUSE conditions.
# Payouts for BEAT 19 and above all end in 5 or 0.
HOUSE_REEL: tuple[HouseStop, ...] = (
    (20, 25),
    (19, 20),
    (19, 20),
    (21, 80),
    (20, 25),
    (18, 8),
    (15, 3),
    (17, 8),
    (20, 40),
    (19, 20),
    (16, 3),
)

REEL_SEQUENCES = (REEL_1, REEL_2, HOUSE_REEL, REEL_3, REEL_4)
REEL_LABELS = ("抽牌 1", "抽牌 2", "庄家", "抽牌 3", "抽牌 4")
THEORETICAL_RTP = 0.9059490471962306
THEORETICAL_HOUSE_EDGE = 1.0 - THEORETICAL_RTP


def get_data_file_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "../saving_data.json",
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


def blackjack_total(values: list[CardStop]) -> tuple[int, bool]:
    """Return the best <=21 total when possible and whether an Ace is soft."""
    total = 0
    aces = 0
    for value in values:
        if value == "blank":
            continue
        if value == "ace":
            total += 11
            aces += 1
        else:
            total += int(value)

    while total > 21 and aces:
        total -= 10
        aces -= 1

    return total, aces > 0


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


class Reel21Blackjack:
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

    REEL_WIDTH = 108
    REEL_HEIGHT = 196
    REEL_GAP = 10
    REEL_TOP_Y = 70
    REEL_SPACING = 62

    BASE_ACCEL = (44.0, 49.0, 54.0, 59.0, 64.0)
    TARGET_SPEED_RANGES = (
        (21.0, 24.0),
        (23.0, 26.0),
        (25.0, 28.0),
        (27.0, 30.0),
        (29.0, 32.0),
    )
    BASE_DRAG = (0.63, 0.59, 0.56, 0.53, 0.50)
    ALIGN_THRESHOLD = 1.35

    def __init__(self, root, initial_balance: float, username: str):
        self.root = root
        self._configure_root()

        self.balance = float(initial_balance)
        self.username = username
        self.multiplier = 1
        self.last_win = 0.0

        self.spinning = False
        self.shutter_animating = False
        self.round_active = False
        self.round_complete = True
        self.after_id: Optional[str] = None
        self.last_frame_time = 0.0

        self.reel_positions = [0.0] * 5
        self.reel_velocities = [0.0] * 5
        self.reel_display_speeds = [0.0] * 5
        self.reel_states = ["idle"] * 5
        self.reel_accels = list(self.BASE_ACCEL)
        self.reel_target_speeds = [
            sum(bounds) / 2.0 for bounds in self.TARGET_SPEED_RANGES
        ]
        self.reel_drags = list(self.BASE_DRAG)
        self.reel_align_targets: list[Optional[int]] = [None] * 5
        self.reel_canvases: list[tk.Canvas] = []
        self.reel_canvas_places: list[tuple[int, int, int, int]] = []

        self.final_stops: list[Union[CardStop, HouseStop]] = [
            REEL_1[0], REEL_2[0], HOUSE_REEL[0], REEL_3[0], REEL_4[0]
        ]

        # Shutter progress: 0.0 = fully open (shutter below window),
        # 1.0 = fully closed (window completely covered).
        # On first load HOUSE / DRAW 3 / DRAW 4 are all OPEN.
        self.shutter_progress = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.shutter_animating = False
        self.shutter_anim_start = 0.0
        self.shutter_anim_duration = 0.0
        self.shutter_anim_indices: tuple[int, ...] = ()
        self.shutter_anim_from: dict[int, float] = {}
        self.shutter_anim_to: dict[int, float] = {}
        self.shutter_anim_callback: Optional[Callable[[], None]] = None

        self.revealed = [True, True, True, True, True]
        self.draw3_open = False
        self.draw4_open = False
        self.house_open = False

        self.mechanical_button_rects: dict[int, tuple[float, float, float, float]] = {}
        self.highlighted_house_stop: Optional[HouseStop] = None
        self.payout_highlight_outcome: Optional[str] = None  # "win" / "lose"

        self.balance_var = tk.StringVar()
        self.bet_var = tk.StringVar()
        self.last_win_var = tk.StringVar()
        self.multiplier_var = tk.StringVar()

        self.result_var = tk.StringVar(value="按下发牌开始游戏")
        self.status_var = tk.StringVar(value="Reel 21 · 机械五轴待机")
        self.motion_var = tk.StringVar(value="静止")
        self.hand_var = tk.StringVar(value="玩家: 尚未发牌")
        self.house_var = tk.StringVar(value="庄家: 尚未发牌")
        self.action_var = tk.StringVar(value="发牌后选择 抽牌 或 庄家")

        self.create_widgets()
        self.update_display()

    # ------------------------------------------------------------------
    # Root / layout
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("Reel 21 Blackjack")
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

        icon = tk.Canvas(
            header, width=48, height=48,
            bg=Theme.PANEL, bd=0, highlightthickness=0,
        )
        icon.place(x=14, y=11)
        icon.create_oval(
            2, 2, 46, 46,
            fill="#B69343", outline="#6D542A", width=2,
        )
        icon.create_text(
            24, 20, text="21",
            fill="#252A2E", font=(Theme.FONT, 14, "bold"),
        )
        icon.create_text(
            24, 34, text="REEL",
            fill="#252A2E", font=(Theme.FONT, 6, "bold"),
        )

        tk.Label(
            header,
            text='REEL "21" BLACKJACK',
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT, 18, "bold"),
            anchor=tk.W,
        ).place(x=74, y=10, width=400, height=27)

        tk.Label(
            header,
            text="经典五轴机械黑杰克 · 每注 $5",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 11, "bold"),
            anchor=tk.W,
        ).place(x=74, y=39, width=450, height=20)

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
        panel = self._card(
            master,
            width=self.GAME_PANEL_WIDTH,
            height=self.BODY_HEIGHT,
            padding=0,
        )
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
        ).place(x=18, y=40, width=540, height=18)

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
        self.game_canvas.bind("<Button-1>", self._on_machine_canvas_click)

        reel_total = self.REEL_WIDTH * 5 + self.REEL_GAP * 4
        reel_start_x = int(round((self.CANVAS_WIDTH - reel_total) / 2))

        for reel_index in range(5):
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
            reel_canvas.bind(
                "<Button-1>",
                lambda event, idx=reel_index: self._on_reel_window_click(idx),
            )
            self.reel_canvases.append(reel_canvas)
            self.reel_canvas_places.append(
                (x, y, self.REEL_WIDTH, self.REEL_HEIGHT)
            )

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

        hand = self._card(sidebar, width=348, height=88, padding=9)
        hand.place(x=0, y=74, width=348, height=88)
        self._section_title(hand.content, "手牌信息").place(
            x=0, y=0, width=100, height=18
        )
        tk.Label(
            hand.content,
            textvariable=self.hand_var,
            bg=Theme.PANEL,
            fg=Theme.ACCENT,
            font=(Theme.FONT_CJK, 13, "bold"),
            anchor=tk.W,
        ).place(x=0, y=20, width=322, height=23)
        tk.Label(
            hand.content,
            textvariable=self.house_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 13, "bold"),
            anchor=tk.W,
        ).place(x=0, y=45, width=322, height=16)

        payout = self._card(sidebar, width=348, height=278, padding=9)
        payout.place(x=0, y=168, width=348, height=278)
        self._section_title(payout.content, "赔付表 · 平局退注").place(
            x=0, y=0, width=180, height=18
        )

        self.payout_canvas = tk.Canvas(
            payout.content,
            width=322,
            height=236,
            bg=Theme.PANEL,
            bd=0,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        self.payout_canvas.place(x=0, y=24, width=322, height=236)

        multiplier_card = self._card(sidebar, width=348, height=100, padding=9)
        multiplier_card.place(x=0, y=452, width=348, height=100)
        self._section_title(multiplier_card.content, "选择下注倍数").place(
            x=0, y=0, width=130, height=18
        )

        self.minus_button = ModernButton(
            multiplier_card.content,
            text="−",
            command=lambda: self.change_multiplier(-1),
            background=Theme.PANEL_ALT,
            hover_background=Theme.PANEL_HOVER,
            foreground=Theme.TEXT,
            font_size=15,
            bold=True,
        )
        self.minus_button.place(x=0, y=22, width=58, height=30)

        tk.Label(
            multiplier_card.content,
            textvariable=self.multiplier_var,
            bg=Theme.ACCENT_SOFT,
            fg=Theme.ACCENT,
            font=(Theme.FONT, 13, "bold"),
            anchor=tk.CENTER,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        ).place(x=68, y=22, width=186, height=30)

        self.plus_button = ModernButton(
            multiplier_card.content,
            text="+",
            command=lambda: self.change_multiplier(1),
            background=Theme.PANEL_ALT,
            hover_background=Theme.PANEL_HOVER,
            foreground=Theme.TEXT,
            font_size=15,
            bold=True,
        )
        self.plus_button.place(x=264, y=22, width=58, height=30)

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
            button.place(x=index * 81, y=59, width=76, height=23)
            self.multiplier_quick_buttons.append(button)

        actions = self._card(sidebar, width=348, height=72, padding=9)
        actions.place(x=0, y=558, width=348, height=72)

        self.spin_button = ModernButton(
            actions.content,
            text="开始抽奖",
            command=self.start_spin,
            background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF",
            font_size=16,
            bold=True,
        )
        self.spin_button.place(x=0, y=0, width=326, height=45)

        self._draw_payout_table()

    # ------------------------------------------------------------------
    # Betting / controls
    # ------------------------------------------------------------------

    @property
    def current_bet(self) -> float:
        return self.BASE_BET * self.multiplier

    def set_multiplier(self, value: int) -> None:
        if self.spinning or self.round_active:
            return
        self.multiplier = max(1, min(self.MAX_MULTIPLIER, int(value)))
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

    def _set_action_buttons(self, enabled: bool) -> None:
        # No right-side game-operation buttons in V2.
        self.draw_scene()

    def _draw_payout_table(self) -> None:
        canvas = getattr(self, "payout_canvas", None)
        if canvas is None:
            return

        canvas.delete("all")
        width = 322
        row_h = 29

        # Highest payout at the top, lowest at the bottom.
        rows = (
            ((21, 80), "BLACKJACK · 击败 21", 80),
            ((20, 40), "击败 20", 40),
            ((20, 25), "击败 20", 25),
            ((19, 20), "击败 19", 20),
            ((18, 8), "击败 18", 8),
            ((17, 8), "击败 17", 8),
            ((16, 3), "击败 16", 3),
            ((15, 3), "击败 15", 3),
        )

        for row, (stop_key, label, units) in enumerate(rows):
            y1 = row * row_h
            y2 = y1 + row_h
            cy = (y1 + y2) / 2

            highlighted = self.highlighted_house_stop == stop_key

            if highlighted and self.payout_highlight_outcome == "win":
                bg = "#D4B55E"
            elif highlighted and self.payout_highlight_outcome in ("lose", "push"):
                bg = "#C9E7F2"
            else:
                bg = Theme.PANEL_ALT if row % 2 == 0 else Theme.PANEL

            canvas.create_rectangle(
                0, y1, width, y2,
                fill=bg,
                outline=Theme.BORDER_SOFT,
                width=1,
            )
            canvas.create_text(
                10, cy,
                text=label,
                fill=Theme.TEXT,
                font=(Theme.FONT_CJK, 11, "bold"),
                anchor=tk.W,
            )

            payout = int(units * self.current_bet)
            canvas.create_text(
                width - 10, cy,
                text=f"${payout:,}",
                fill=Theme.TEXT if highlighted else Theme.AMBER,
                font=(Theme.FONT, 12, "bold"),
                anchor=tk.E,
            )

    def _mechanical_action_available(self, reel_index: int) -> bool:
        if (
            self.spinning
            or self.shutter_animating
            or not self.round_active
            or self.house_open
        ):
            return False

        total, _soft = self._current_hand_total()

        if reel_index == 2:
            return True
        if reel_index == 3:
            return not self.draw3_open and total < 21
        if reel_index == 4:
            return self.draw3_open and not self.draw4_open and total < 21
        return False

    def _activate_mechanical_action(self, reel_index: int) -> None:
        if not self._mechanical_action_available(reel_index):
            return

        if reel_index == 2:
            self.reveal_house()
        elif reel_index == 3:
            self.reveal_draw3()
        elif reel_index == 4:
            self.reveal_draw4()

    def _on_reel_window_click(self, reel_index: int) -> None:
        if reel_index in (2, 3, 4):
            self._activate_mechanical_action(reel_index)

    def _on_machine_canvas_click(self, event) -> None:
        for reel_index, rect in self.mechanical_button_rects.items():
            x1, y1, x2, y2 = rect
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self._activate_mechanical_action(reel_index)
                return

    # ------------------------------------------------------------------
    # Mechanical five-reel spin
    # ------------------------------------------------------------------

    def start_spin(self) -> None:
        if self.spinning or self.round_active or self.shutter_animating:
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
        self.highlighted_house_stop = None
        self.payout_highlight_outcome = None
        update_balance_in_json(self.username, self.balance)

        self.draw3_open = False
        self.draw4_open = False
        self.house_open = False
        self.round_active = True
        self.round_complete = False
        self.revealed = [True, True, False, False, False]

        self.result_var.set("机械挡板关闭中")
        self.status_var.set("庄家 / 抽牌 3 / 抽牌 4 正在升起遮挡")
        self.motion_var.set("挡板 ↑")
        self.hand_var.set("玩家: 准备发牌…")
        self.house_var.set("庄家: 准备发牌…")
        self.action_var.set("等待挡板关闭")

        self.spin_button.configure(state=tk.DISABLED)
        self._set_bet_controls_enabled(False)

        self._animate_shutters(
            indices=(2, 3, 4),
            target=1.0,
            duration=1.0,
            callback=self._begin_physical_spin,
        )
        self.update_display()

    def _begin_physical_spin(self) -> None:
        if not self.round_active:
            return

        self.reel_velocities = [0.0] * 5
        self.reel_display_speeds = [0.0] * 5
        self.reel_states = ["accelerating"] * 5
        self.reel_align_targets = [None] * 5

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
        self.result_var.set("滚动中.......")
        self.status_var.set("前两轴公开； 庄家 / 抽牌 3 / 抽牌 4 保持遮蔽")
        self.motion_var.set("滚动中")
        self.action_var.set("等待滚轮停止")
        self._physics_frame()

    def _animate_shutters(
        self,
        *,
        indices: tuple[int, ...],
        target: float,
        duration: float,
        callback: Optional[Callable[[], None]] = None,
    ) -> None:
        if self.shutter_animating:
            return

        self.shutter_animating = True
        self.shutter_anim_start = time.monotonic()
        self.shutter_anim_duration = max(0.05, float(duration))
        self.shutter_anim_indices = tuple(indices)
        self.shutter_anim_from = {
            index: float(self.shutter_progress[index])
            for index in indices
        }
        self.shutter_anim_to = {
            index: max(0.0, min(1.0, float(target)))
            for index in indices
        }
        self.shutter_anim_callback = callback
        self._shutter_animation_frame()

    def _shutter_animation_frame(self) -> None:
        if not self.shutter_animating:
            return

        elapsed = time.monotonic() - self.shutter_anim_start
        t = min(1.0, elapsed / self.shutter_anim_duration)
        eased = t * t * (3.0 - 2.0 * t)

        for index in self.shutter_anim_indices:
            start = self.shutter_anim_from[index]
            end = self.shutter_anim_to[index]
            self.shutter_progress[index] = start + (end - start) * eased

        self.draw_scene()

        if t >= 1.0:
            for index in self.shutter_anim_indices:
                self.shutter_progress[index] = self.shutter_anim_to[index]

            callback = self.shutter_anim_callback
            self.shutter_animating = False
            self.shutter_anim_indices = ()
            self.shutter_anim_from = {}
            self.shutter_anim_to = {}
            self.shutter_anim_callback = None
            self.after_id = None
            self.draw_scene()

            if callable(callback):
                callback()
            return

        self.after_id = self.root.after(16, self._shutter_animation_frame)

    def _physics_frame(self) -> None:
        if not self.spinning:
            return

        now = time.monotonic()
        dt = max(0.001, min(0.045, now - self.last_frame_time))
        self.last_frame_time = now

        all_stopped = True

        for index in range(5):
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
                velocity *= math.exp(-self.reel_drags[index] * dt)
                self.reel_positions[index] += velocity * dt

                if abs(velocity) <= self.ALIGN_THRESHOLD:
                    position = self.reel_positions[index]
                    fraction = position - math.floor(position)
                    target = (
                        math.floor(position)
                        if fraction < 0.5
                        else math.ceil(position)
                    )
                    self.reel_align_targets[index] = int(target)
                    self.reel_states[index] = "aligning"

            elif state == "aligning":
                all_stopped = False
                target = self.reel_align_targets[index]
                if target is None:
                    target = round(self.reel_positions[index])
                    self.reel_align_targets[index] = int(target)

                error = float(target) - self.reel_positions[index]
                self.reel_positions[index] += error * min(1.0, dt * 4.6)
                velocity *= math.exp(-4.9 * dt)

                if abs(error) < 0.0025:
                    self.reel_positions[index] = float(target)
                    velocity = 0.0
                    self.reel_states[index] = "stopped"

            elif state == "stopped":
                velocity = 0.0

            self.reel_velocities[index] = velocity

            actual_speed = abs(self.reel_positions[index] - position_before) / dt
            if self.reel_states[index] == "stopped":
                actual_speed = 0.0
            self.reel_display_speeds[index] = actual_speed

        self.draw_scene()

        if all_stopped:
            self._finish_deal()
            return

        self.after_id = self.root.after(16, self._physics_frame)

    def _stop_from_position(self, reel_index: int):
        sequence = REEL_SEQUENCES[reel_index]
        index = int(round(self.reel_positions[reel_index])) % len(sequence)
        return sequence[index]

    def _finish_deal(self) -> None:
        self.spinning = False
        self.after_id = None
        self.final_stops = [
            self._stop_from_position(index)
            for index in range(5)
        ]

        self.motion_var.set("已对齐")
        total, soft = self._current_hand_total()
        self.result_var.set(f"起手点数：{total}")
        self.status_var.set("按 抽牌 3 / 庄家 窗口或下方「打开」按钮")
        self.action_var.set("抽牌 3 可打开 · 或按 庄家 窗口游戏结算")
        self._refresh_hand_display()

        self._set_action_buttons(True)
        self.draw_scene()
        self.update_display()

    # ------------------------------------------------------------------
    # Player decisions / settlement
    # ------------------------------------------------------------------

    def _visible_card_values(self) -> list[CardStop]:
        values: list[CardStop] = [
            self.final_stops[0],
            self.final_stops[1],
        ]
        if self.draw3_open:
            values.append(self.final_stops[3])
        if self.draw4_open:
            values.append(self.final_stops[4])
        return values

    def _current_hand_total(self) -> tuple[int, bool]:
        return blackjack_total(self._visible_card_values())

    @staticmethod
    def _card_display(value: CardStop) -> str:
        if value == "blank":
            return "空白"
        if value == "ace":
            return "1 OR 11"
        return str(value)

    def _refresh_hand_display(self) -> None:
        values = self._visible_card_values()
        total, soft = blackjack_total(values)
        shown = " + ".join(self._card_display(value) for value in values)
        suffix = "（软）" if soft else ""
        self.hand_var.set(f"玩家: {shown} = {total}{suffix}")

        if self.house_open:
            beat, pay = self.final_stops[2]
            self.house_var.set(f"庄家: 击败 {beat} · 赔付 {pay} 倍")
        else:
            self.house_var.set("庄家: 隐藏")

    def reveal_draw3(self) -> None:
        if not self._mechanical_action_available(3):
            return

        self.draw3_open = True
        self.revealed[3] = True
        self.status_var.set("抽牌 3 挡板正在下降")
        self.motion_var.set("挡板 ↓")

        self._animate_shutters(
            indices=(3,),
            target=0.0,
            duration=0.85,
            callback=self._after_draw3_open,
        )

    def _after_draw3_open(self) -> None:
        self.motion_var.set("已打开")
        self._refresh_hand_display()

        total, _soft = self._current_hand_total()
        if total > 21:
            self.result_var.set(f"爆牌 · {total}")
            self.status_var.set("超过 21，本局失败 · 庄家窗口自动揭晓")
            self.action_var.set("爆牌后自动打开庄家窗口")
            self.reveal_house(force_loss=True)
            return

        if total == 21:
            self.result_var.set("21！")
            self.status_var.set("您已经21点了；请打开 庄家 窗口或下方「打开」按钮")
            self.action_var.set("点数 21 · 游戏结算")
        else:
            self.result_var.set(f"当前点数：{total}")
            self.status_var.set("按 抽牌 4 / 庄家 窗口或下方「打开」按钮")
            self.action_var.set("抽牌 4 可打开 · 或按 庄家 窗口游戏结算")

        self.draw_scene()

    def reveal_draw4(self) -> None:
        if not self._mechanical_action_available(4):
            return

        self.draw4_open = True
        self.revealed[4] = True
        self.status_var.set("抽牌 4 挡板正在下降")
        self.motion_var.set("挡板 ↓")

        self._animate_shutters(
            indices=(4,),
            target=0.0,
            duration=0.85,
            callback=self._after_draw4_open,
        )

    def _after_draw4_open(self) -> None:
        self.motion_var.set("已打开")
        self._refresh_hand_display()

        total, _soft = self._current_hand_total()
        if total > 21:
            self.result_var.set(f"BUST · {total}")
            self.status_var.set("玩家超过21点，本局失败 · 庄家窗口自动揭晓")
            self.action_var.set("爆牌后自动打开庄家")
            self.reveal_house(force_loss=True)
            return

        self.result_var.set(f"最终手牌：{total}")
        self.status_var.set("抽牌已用完；请打开 庄家 窗口")
        self.action_var.set("游戏已结算")
        self.draw_scene()

    def reveal_house(self, force_loss: bool = False) -> None:
        if (
            not self.round_active
            or self.spinning
            or self.house_open
            or self.shutter_animating
        ):
            return

        self.house_open = True
        self.revealed[2] = True
        self.status_var.set("HOUSE 挡板正在下降")
        self.motion_var.set("挡板 ↓")
        self.action_var.set("HOUSE 已启动；未开的 DRAW 已锁定")

        self._animate_shutters(
            indices=(2,),
            target=0.0,
            duration=0.85,
            callback=lambda: self._after_house_open(force_loss),
        )

    def _after_house_open(self, force_loss: bool) -> None:
        self.motion_var.set("已打开")
        self._refresh_hand_display()
        self.draw_scene()
        self._settle_round(force_loss=force_loss)

    def _is_special_blackjack(self) -> bool:
        return (
            self.draw3_open
            and not self.draw4_open
            and self.final_stops[0] == "blank"
            and self.final_stops[1] == 10
            and self.final_stops[3] == "ace"
            and self.final_stops[2][0] == 21
        )

    def _settle_round(self, *, force_loss: bool = False) -> None:
        total, _soft = self._current_hand_total()
        beat, pay_units = self.final_stops[2]

        won = False
        push = False
        special = False

        if not force_loss and total <= 21:
            if self._is_special_blackjack():
                won = True
                special = True
            elif total > beat:
                won = True
            elif total == beat:
                push = True

        if won:
            payout = int(pay_units * self.current_bet)
        elif push:
            payout = int(self.current_bet)
        else:
            payout = 0

        self.last_win = float(payout)
        self.highlighted_house_stop = (beat, pay_units)
        self.payout_highlight_outcome = (
            "win" if won else "push" if push else "lose"
        )

        if won:
            self.balance += float(payout)
            if special:
                self.result_var.set(f"BLACKJACK！返还 ${payout:,}")
                self.status_var.set("空白 + 10 + 1/11 · 击败 21")
            else:
                self.result_var.set(f"{total} 击败 {beat} · 返还 ${payout:,}")
                self.status_var.set("您赢了！")

        elif push:
            self.balance += float(payout)
            self.result_var.set(f"{total} = {beat} · 平局")
            self.status_var.set(f"退回本局下注 ${payout:,}")

        else:
            if total > 21:
                self.result_var.set(f"{total}点爆牌 · 未中奖")
                self.status_var.set("送您好运！")
            else:
                self.result_var.set("您未能击败庄家")
                self.status_var.set("送您好运！")

        self.round_active = False
        self.round_complete = True
        self.action_var.set("本局结束 · 可调整下注后开始下一局")
        self.motion_var.set("完成")

        update_balance_in_json(self.username, self.balance)

        self.spin_button.configure(state=tk.NORMAL)
        self._set_bet_controls_enabled(True)
        self._set_action_buttons(False)
        self.update_display()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw_scene(self) -> None:
        self._draw_machine()

    def _draw_card_stop(
        self,
        canvas: tk.Canvas,
        value: CardStop,
        x: float,
        y: float,
        *,
        scale: float,
    ) -> None:
        if value == "blank":
            # Historical-style seven-line BLANK instruction stop:
            # 1 BLANK
            # 2 divider
            # 3 START
            # 4 COUNT
            # 5 TO
            # 6 RIGHT
            # 7 right-pointing arrow
            ink = Theme.REEL_TEXT
            muted = "#746A5D"

            top = y - 27 * scale
            line_gap = 8.0 * scale

            canvas.create_text(
                x, top,
                text="BLANK",
                fill=ink,
                font=(Theme.FONT, max(5, int(8 * scale)), "bold"),
            )

            divider_y = top + line_gap
            canvas.create_line(
                x - 30 * scale,
                divider_y,
                x + 30 * scale,
                divider_y,
                fill=muted,
                width=max(1, int(1.5 * scale)),
            )

            words = ("START", "COUNT", "TO", "RIGHT")
            for idx, word in enumerate(words, start=2):
                canvas.create_text(
                    x,
                    top + idx * line_gap,
                    text=word,
                    fill=ink,
                    font=(Theme.FONT, max(4, int(6.5 * scale)), "bold"),
                )

            arrow_y = top + 6 * line_gap
            canvas.create_line(
                x - 22 * scale,
                arrow_y,
                x + 17 * scale,
                arrow_y,
                fill=ink,
                width=max(1, int(2 * scale)),
                arrow=tk.LAST,
                arrowshape=(
                    max(4, int(7 * scale)),
                    max(5, int(9 * scale)),
                    max(2, int(3 * scale)),
                ),
            )
            return

        if value == "ace":
            # Original two-line marking: "1 OR" / "11".
            canvas.create_text(
                x + 1.5 * scale,
                y - 10 * scale + 1.5 * scale,
                text="1 OR",
                fill="#B7A88D",
                font=(Theme.FONT, max(7, int(16 * scale)), "bold"),
            )
            canvas.create_text(
                x,
                y - 10 * scale,
                text="1 OR",
                fill=Theme.REEL_TEXT,
                font=(Theme.FONT, max(7, int(16 * scale)), "bold"),
            )
            canvas.create_text(
                x + 1.5 * scale,
                y + 12 * scale + 1.5 * scale,
                text="11",
                fill="#B7A88D",
                font=(Theme.FONT, max(8, int(21 * scale)), "bold"),
            )
            canvas.create_text(
                x,
                y + 12 * scale,
                text="11",
                fill=Theme.REEL_TEXT,
                font=(Theme.FONT, max(8, int(21 * scale)), "bold"),
            )
            return

        text = str(value)
        is_ten = text == "10"
        size = int((30 if is_ten else 34) * scale)

        canvas.create_text(
            x + 2 * scale,
            y + 2 * scale,
            text=text,
            fill="#B7A88D",
            font=(Theme.FONT, max(8, size), "bold"),
        )
        canvas.create_text(
            x,
            y,
            text=text,
            fill=Theme.REEL_TEXT,
            font=(Theme.FONT, max(8, size), "bold"),
        )

    def _draw_house_stop(
        self,
        canvas: tk.Canvas,
        stop: HouseStop,
        x: float,
        y: float,
        *,
        scale: float,
    ) -> None:
        beat, pay = stop

        canvas.create_rectangle(
            x - 43 * scale,
            y - 26 * scale,
            x + 43 * scale,
            y + 27 * scale,
            fill="#EFE0BD",
            outline="#8B744B",
            width=max(1, int(2 * scale)),
        )

        canvas.create_text(
            x,
            y - 8 * scale,
            text=f"BEAT {beat}",
            fill="#2A2520",
            font=(Theme.FONT, max(6, int(12 * scale)), "bold"),
        )
        canvas.create_text(
            x,
            y + 10 * scale,
            text=f"PAYS {pay}",
            fill="#9A342D",
            font=(Theme.FONT, max(6, int(11 * scale)), "bold"),
        )

    def _draw_shutter(
        self,
        canvas: tk.Canvas,
        reel_index: int,
    ) -> None:
        progress = max(0.0, min(1.0, self.shutter_progress[reel_index]))
        if progress <= 0.001:
            return

        w = self.REEL_WIDTH
        h = self.REEL_HEIGHT
        top = h * (1.0 - progress)
        bottom = top + h

        canvas.create_rectangle(
            0, top, w, bottom,
            fill=Theme.SHUTTER,
            outline=Theme.SHUTTER_EDGE,
            width=3,
        )

        rib_y = top + 8
        while rib_y < bottom:
            canvas.create_line(
                4, rib_y, w - 4, rib_y,
                fill=Theme.SHUTTER_DARK,
                width=2,
            )
            canvas.create_line(
                4, rib_y + 2, w - 4, rib_y + 2,
                fill="#646A6E",
                width=1,
            )
            rib_y += 12

        label = {
            2: "庄家",
            3: "抽牌 3",
            4: "抽牌 4",
        }.get(reel_index, "LOCKED")

        plate_cy = top + h / 2
        canvas.create_rectangle(
            13, plate_cy - 22,
            w - 13, plate_cy + 22,
            fill=Theme.BRASS,
            outline="#6F5522",
            width=2,
        )
        canvas.create_rectangle(
            17, plate_cy - 18,
            w - 17, plate_cy + 18,
            outline=Theme.BRASS_LIGHT,
            width=1,
        )
        canvas.create_text(
            w / 2, plate_cy,
            text=label,
            fill="#25221D",
            font=(Theme.FONT, 11, "bold"),
        )

        if self.house_open and reel_index in (3, 4):
            unopened = (
                (reel_index == 3 and not self.draw3_open)
                or (reel_index == 4 and not self.draw4_open)
            )
            if unopened:
                canvas.create_text(
                    w / 2,
                    plate_cy + 34,
                    text="LOCKED",
                    fill="#E7D6B0",
                    font=(Theme.FONT, 7, "bold"),
                )

    def _draw_machine(self) -> None:
        c = self.game_canvas
        c.delete("all")

        w = self.CANVAS_WIDTH
        h = self.CANVAS_HEIGHT

        c.create_rectangle(0, 0, w, h, fill=Theme.CANVAS_BG, outline="")

        c.create_rectangle(
            46, 24, w - 46, 370,
            fill=Theme.PANEL_ALT,
            outline=Theme.BORDER,
            width=2,
        )
        c.create_rectangle(
            63, 50, w - 63, 292,
            fill=Theme.REEL_WELL,
            outline=Theme.REEL_EDGE,
            width=3,
        )

        reel_total = self.REEL_WIDTH * 5 + self.REEL_GAP * 4
        start_x = (w - reel_total) / 2
        top_y = self.REEL_TOP_Y
        bottom_y = top_y + self.REEL_HEIGHT
        center_y = (top_y + bottom_y) / 2

        for reel_index, reel_canvas in enumerate(self.reel_canvases):
            x1 = start_x + reel_index * (self.REEL_WIDTH + self.REEL_GAP)
            x2 = x1 + self.REEL_WIDTH
            sequence = REEL_SEQUENCES[reel_index]
            position = self.reel_positions[reel_index]

            c.create_rectangle(
                x1, top_y, x2, bottom_y,
                fill=Theme.REEL_FACE,
                outline=Theme.REEL_EDGE,
                width=3,
            )

            label_color = Theme.AMBER if reel_index == 2 else Theme.TEXT_MUTED
            c.create_text(
                (x1 + x2) / 2,
                bottom_y + 18,
                text=REEL_LABELS[reel_index],
                fill=label_color,
                font=(Theme.FONT, 8, "bold"),
            )

            reel_canvas.delete("all")
            reel_canvas.configure(bg=Theme.REEL_FACE)
            local_center_y = self.REEL_HEIGHT / 2
            base_index = math.floor(position)

            for strip_index in range(base_index - 4, base_index + 5):
                stop = sequence[strip_index % len(sequence)]
                y = local_center_y + (
                    strip_index - position
                ) * self.REEL_SPACING
                distance = abs(y - local_center_y)

                if distance < 18:
                    scale = 1.0
                elif distance < 78:
                    scale = 0.68
                else:
                    scale = 0.45

                if reel_index == 2:
                    self._draw_house_stop(
                        reel_canvas,
                        stop,
                        self.REEL_WIDTH / 2,
                        y,
                        scale=scale,
                    )
                else:
                    self._draw_card_stop(
                        reel_canvas,
                        stop,
                        self.REEL_WIDTH / 2,
                        y,
                        scale=scale,
                    )

            reel_canvas.create_line(
                0, local_center_y,
                self.REEL_WIDTH, local_center_y,
                fill=Theme.PAYLINE, width=3,
            )

            if reel_index >= 2:
                self._draw_shutter(reel_canvas, reel_index)

        # Mechanical "打开" buttons below HOUSE / DRAW 3 / DRAW 4.
        self.mechanical_button_rects = {}
        button_y1 = bottom_y + 36
        button_y2 = button_y1 + 28

        for reel_index in (2, 3, 4):
            x1 = start_x + reel_index * (self.REEL_WIDTH + self.REEL_GAP)
            x2 = x1 + self.REEL_WIDTH
            bx1 = x1 + 12
            bx2 = x2 - 12
            self.mechanical_button_rects[reel_index] = (
                bx1, button_y1, bx2, button_y2
            )

            enabled = self._mechanical_action_available(reel_index)
            if enabled:
                fill = Theme.BRASS
                edge = "#6F5522"
                text_fill = "#25221D"
            else:
                fill = "#9C968B"
                edge = "#777169"
                text_fill = "#514D48"

            c.create_rectangle(
                bx1 + 2, button_y1 + 3,
                bx2 + 2, button_y2 + 3,
                fill="#777068", outline="",
            )
            c.create_rectangle(
                bx1, button_y1,
                bx2, button_y2,
                fill=fill, outline=edge, width=2,
            )
            c.create_rectangle(
                bx1 + 4, button_y1 + 4,
                bx2 - 4, button_y2 - 4,
                outline=Theme.BRASS_LIGHT if enabled else "#B4ADA3",
                width=1,
            )
            c.create_text(
                (bx1 + bx2) / 2,
                (button_y1 + button_y2) / 2,
                text="打开",
                fill=text_fill,
                font=(Theme.FONT_CJK, 10, "bold"),
            )

        # Payline segments between the five windows.
        c.create_line(
            68, center_y, w - 68, center_y,
            fill=Theme.PAYLINE,
            width=3,
        )

        # Instruction / state panel.
        c.create_rectangle(
            86, 394, w - 86, 488,
            fill=Theme.PANEL_ALT,
            outline=Theme.BORDER_SOFT,
            width=1,
        )

        c.create_text(
            106, 415,
            text="PLAY",
            fill=Theme.TEXT_MUTED,
            font=(Theme.FONT, 8, "bold"),
            anchor=tk.W,
        )
        c.create_text(
            106, 440,
            text=(
                "直接按 庄家 / 抽牌 窗口，或按下方机械「打开」按钮"
            ),
            fill=Theme.TEXT,
            font=(Theme.FONT, 12, "bold"),
            anchor=tk.W,
        )
        c.create_text(
            106, 465,
            text=(
                "目标：不超过 21，并严格高于 庄家 的「击败」数字。"
            ),
            fill=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.W,
        )

        c.create_text(
            52, 516,
            text=f"本局下注：$5 × {self.multiplier} = ${self.current_bet:,.0f}",
            fill=Theme.TEXT,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.W,
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

        self._draw_payout_table()

        if self.shutter_animating:
            spin_text = "机械挡板动作中"
        elif self.round_active:
            spin_text = "本局进行中"
        else:
            spin_text = f"开始抽奖 · ${self.current_bet:,.0f}"

        self.spin_button.configure(text=spin_text)

        if not self.spinning and not self.round_active:
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
        self.shutter_animating = False
        self.round_active = False
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
            title='Reel "21" Blackjack',
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        page.set_requested_size(1150, 750)
        game = Reel21Blackjack(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = Reel21Blackjack(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    final_balance = main(10000.0, "demo_player")
    print(f"Final balance: {final_balance:.2f}")