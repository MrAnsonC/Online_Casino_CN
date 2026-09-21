"""21 Bell Slot Machine — ChickenCrossing-style physical-reel edition.

Gameplay:
- Bet = $5 × 1..10 units, so each spin costs $5..$50.
- Three traditional cyclic reels, each with 20 equally likely physical stops.
- Reel strips reproduce the classic 21 Bell configuration documented by Wizard of Odds.
- Compound stops such as "7 + ORANGE" count as either printed symbol for paytable matching.
- Existing physical animation is retained: acceleration, drag, and final mechanical alignment.
- One center payline uses the traditional 21 Bell paytable.
- V3 renders upgraded vintage mechanical-slot artwork on both reels and paytable.
- Payout = traditional pay units × $5 denomination × selected multiplier.
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


VERSION = "21Bell-ChickenStyle-R3"


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


SYMBOL_LABELS = {
    "7": "7", "bar": "BAR", "melon": "MELON", "bell": "BELL",
    "plum": "PLUM", "orange": "ORANGE", "cherry": "CHERRY", "lemon": "LEMON",
}

REEL_STRIPS = (
    (("orange",),("melon",),("plum",),("cherry",),("plum",),("orange",),("7",),("bell","bar"),("orange",),("cherry",),("bar",),("plum",),("orange",),("plum",),("melon",),("plum",),("orange",),("plum",),("bar",),("plum",)),
    (("cherry",),("plum",),("cherry",),("7","orange"),("cherry",),("bell",),("plum","bar"),("bell",),("cherry",),("orange",),("bell",),("melon","orange"),("plum",),("bell",),("cherry",),("bar",),("orange",),("cherry",),("bell",),("melon","orange")),
    (("bell",),("orange",),("plum",),("bell",),("orange",),("lemon",),("bell",),("melon","orange"),("bell",),("plum",),("lemon",),("bell",),("plum",),("bell",),("7","bar"),("lemon",),("bell",),("melon","orange"),("bell",),("lemon",)),
)

def stop_text(stop: tuple[str, ...]) -> str:
    return "+".join(SYMBOL_LABELS[s] for s in stop)

PAYTABLE_ROWS = (
    ("three_sevens",       ("7", "7", "7"),                  200),
    ("three_bars",         ("bar", "bar", "bar"),            100),
    ("three_melons",       ("melon", "melon", "melon"),      100),
    ("melon_melon_bar",    ("melon", "melon", "bar"),        100),
    ("three_bells",        ("bell", "bell", "bell"),          18),
    ("bell_bell_bar",      ("bell", "bell", "bar"),           18),
    ("three_plums",        ("plum", "plum", "plum"),          14),
    ("plum_plum_bar",      ("plum", "plum", "bar"),           14),
    ("three_oranges",      ("orange", "orange", "orange"),    10),
    ("orange_orange_bar",  ("orange", "orange", "bar"),       10),
    ("two_cherries",       ("cherry", "cherry", "any"),       5),
    ("one_cherry",         ("cherry", "any", "any"),           2),
)

def classify_21_bell(r1: tuple[str,...], r2: tuple[str,...], r3: tuple[str,...]) -> tuple[str,int]:
    s1,s2,s3=set(r1),set(r2),set(r3)
    rules=(
        ("three_sevens",200,"7" in s1 and "7" in s2 and "7" in s3),
        ("three_bars",100,"bar" in s1 and "bar" in s2 and "bar" in s3),
        ("three_melons",100,"melon" in s1 and "melon" in s2 and "melon" in s3),
        ("melon_melon_bar",100,"melon" in s1 and "melon" in s2 and "bar" in s3),
        ("three_bells",18,"bell" in s1 and "bell" in s2 and "bell" in s3),
        ("bell_bell_bar",18,"bell" in s1 and "bell" in s2 and "bar" in s3),
        ("three_plums",14,"plum" in s1 and "plum" in s2 and "plum" in s3),
        ("plum_plum_bar",14,"plum" in s1 and "plum" in s2 and "bar" in s3),
        ("three_oranges",10,"orange" in s1 and "orange" in s2 and "orange" in s3),
        ("orange_orange_bar",10,"orange" in s1 and "orange" in s2 and "bar" in s3),
        ("two_cherries",5,"cherry" in s1 and "cherry" in s2),
        ("one_cherry",2,"cherry" in s1),
    )
    for key,units,ok in rules:
        if ok: return key,units
    return "none",0


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

    REEL_SEQUENCES = REEL_STRIPS

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

        self.reel_positions = [0.0, 0.0, 0.0]
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
        self.final_result = [REEL_STRIPS[0][0], REEL_STRIPS[1][0], REEL_STRIPS[2][0]]

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
        self.status_var = tk.StringVar(value="21 Bell 传统物理滚轮待机")
        self.motion_var = tk.StringVar(value="静止")


        self.highlighted_payout_class: Optional[str] = None

        self.create_widgets()
        self.update_display()

    # ------------------------------------------------------------------
    # Root / layout
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("21 Bell 老虎機")
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
            text="21 BELL",
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT, 18, "bold"),
            anchor=tk.W,
        ).place(x=74, y=10, width=340, height=27)

        tk.Label(
            header,
            text="经典老虎机 · 每注5块",
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

        # V2: all 12 traditional 21 Bell wins are shown individually,
        # with the same classic vector symbols used on the physical reels.
        payout = self._card(sidebar, width=348, height=382, padding=9)
        payout.place(x=0, y=73, width=348, height=382)
        self._section_title(payout.content, "赔付表 · 当前下注").place(
            x=0, y=0, width=200, height=20
        )

        self.payout_canvas = tk.Canvas(
            payout.content,
            width=322,
            height=336,
            bg=Theme.PANEL,
            bd=0,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        self.payout_canvas.place(x=0, y=27, width=322, height=336)

        multiplier_card = self._card(sidebar, width=348, height=104, padding=9)
        multiplier_card.place(x=0, y=460, width=348, height=104)
        self._section_title(multiplier_card.content, "选择下注倍数").place(
            x=0, y=0, width=130, height=20
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
        self.minus_button.place(x=0, y=24, width=58, height=32)

        tk.Label(
            multiplier_card.content,
            textvariable=self.multiplier_var,
            bg=Theme.ACCENT_SOFT,
            fg=Theme.ACCENT,
            font=(Theme.FONT, 13, "bold"),
            anchor=tk.CENTER,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        ).place(x=68, y=24, width=186, height=32)

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
        self.plus_button.place(x=264, y=24, width=58, height=32)

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
            button.place(x=index * 81, y=62, width=76, height=24)
            self.multiplier_quick_buttons.append(button)

        actions = self._card(sidebar, width=348, height=65, padding=9)
        actions.place(x=0, y=569, width=348, height=60)

        self.spin_button = ModernButton(
            actions.content,
            text="开始抽奖",
            command=self.start_spin,
            background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF",
            font_size=18,
            bold=True,
        )
        self.spin_button.place(x=0, y=0, width=322, height=40)

        self._draw_payout_table()

    # ------------------------------------------------------------------
    # Multiplier / payout UI
    # ------------------------------------------------------------------

    @property
    def current_bet(self) -> float:
        return self.BASE_BET * self.multiplier

    def _clear_payout_highlight(self) -> None:
        self.highlighted_payout_class = None
        self._draw_payout_table()

    def _highlight_payout_row(self, result_class: str) -> None:
        self.highlighted_payout_class = result_class
        self._draw_payout_table()

    def _draw_payout_table(self) -> None:
        canvas = getattr(self, "payout_canvas", None)
        if canvas is None:
            return

        canvas.delete("all")
        width = 322
        row_h = 28
        denom = int(self.BASE_BET)

        for row_index, (result_key, symbols, units) in enumerate(PAYTABLE_ROWS):
            y1 = row_index * row_h
            y2 = y1 + row_h
            cy = y1 + row_h / 2

            if result_key == self.highlighted_payout_class:
                bg = "#D4B55E"
            else:
                bg = Theme.PANEL_ALT if row_index % 2 == 0 else Theme.PANEL

            canvas.create_rectangle(
                0, y1, width, y2,
                fill=bg,
                outline=Theme.BORDER_SOFT,
                width=1,
            )

            # Three classic symbols per winning combination.
            for col, symbol in enumerate(symbols):
                self._draw_classic_symbol(
                    canvas,
                    symbol,
                    22 + col * 34,
                    cy,
                    scale=0.43,
                )

            payout = units * denom * self.multiplier
            canvas.create_text(
                width - 10,
                cy,
                text=f"${payout:,}",
                fill=Theme.TEXT if result_key == self.highlighted_payout_class else Theme.AMBER,
                font=(Theme.FONT, 12, "bold"),
                anchor=tk.E,
            )

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

    def _symbol_from_position(self, reel_index: int) -> tuple[str, ...]:
        sequence = self.REEL_SEQUENCES[reel_index]
        index = int(round(self.reel_positions[reel_index])) % len(sequence)
        return tuple(sequence[index])

    def _finish_physical_spin(self) -> None:
        self.spinning = False
        self.after_id = None
        self.final_result = [self._symbol_from_position(i) for i in range(3)]
        result_class, pay_units = classify_21_bell(*self.final_result)
        self.motion_var.set("已对齐")
        self.draw_scene()
        payout = int(pay_units * self.BASE_BET * self.multiplier)
        self._settle_regular(result_class, payout)

    # ------------------------------------------------------------------
    # Settlement
    # ------------------------------------------------------------------

    def _settle_regular(self, result_class: str, payout: int) -> None:
        labels = {
            "three_sevens":"三个 7", "three_bars":"三个 BAR",
            "three_melons":"三个 MELON", "melon_melon_bar":"MELON · MELON · BAR",
            "three_bells":"三个 BELL", "bell_bell_bar":"BELL · BELL · BAR",
            "three_plums":"三个 PLUM", "plum_plum_bar":"PLUM · PLUM · BAR",
            "three_oranges":"三个 ORANGE", "orange_orange_bar":"ORANGE · ORANGE · BAR",
            "two_cherries":"CHERRY · CHERRY · ANY", "one_cherry":"CHERRY · ANY · ANY",
            "none":"未中奖",
        }
        shown = " | ".join(stop_text(stop) for stop in self.final_result)
        self.last_win = float(payout)
        if payout > 0:
            self.balance += float(payout)
            self._highlight_payout_row(result_class)
            self.result_var.set(f"您赢了${payout:,}！")
        else:
            self.result_var.set(f"未中奖，送您好运！")
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

    def _draw_classic_symbol(
        self,
        canvas: tk.Canvas,
        symbol: str,
        x: float,
        y: float,
        *,
        scale: float = 1.0,
    ) -> None:
        """Draw a polished vintage mechanical-slot symbol using Tk Canvas vectors."""
        s = max(0.18, float(scale))

        def X(v: float) -> float:
            return x + v * s

        def Y(v: float) -> float:
            return y + v * s

        def W(v: float) -> int:
            return max(1, int(round(v * s)))

        # Shared vintage reel palette.
        ink = "#2A2520"
        cream = "#F4E7C7"
        cream_hi = "#FFF5DC"
        red = "#C92A2A"
        red_dark = "#7A1717"
        gold = "#E3B73D"
        gold_dark = "#806116"
        green = "#4F8A3B"
        green_dark = "#2D5C28"

        def shadow_oval(x1, y1, x2, y2, amount=2.5):
            canvas.create_oval(
                X(x1 + amount), Y(y1 + amount),
                X(x2 + amount), Y(y2 + amount),
                fill="#8F877B", outline=""
            )

        def glossy_highlight(x1, y1, x2, y2, color="#FFF6D9"):
            canvas.create_arc(
                X(x1), Y(y1), X(x2), Y(y2),
                start=35, extent=115, style=tk.ARC,
                outline=color, width=W(2),
            )

        if symbol == "any":
            # Classic blank/any marker: neutral ivory disk with a small star.
            shadow_oval(-19, -19, 19, 19, 2.0)
            canvas.create_oval(
                X(-20), Y(-20), X(20), Y(20),
                fill=cream_hi, outline=ink, width=W(2),
            )
            pts = []
            for i in range(10):
                ang = math.radians(-90 + i * 36)
                r = 10 if i % 2 == 0 else 4.5
                pts.extend((x + math.cos(ang) * r * s, y + math.sin(ang) * r * s))
            canvas.create_polygon(
                *pts, fill=gold, outline=gold_dark, width=W(1)
            )
            return

        if symbol == "7":
            # Chunky red 7 with cream pinstripe and black offset shadow.
            canvas.create_polygon(
                X(-23), Y(-22), X(24), Y(-22),
                X(17), Y(-10), X(6), Y(20),
                X(-11), Y(20), X(2), Y(-7),
                X(-23), Y(-7),
                fill=ink, outline=ink,
            )
            canvas.create_polygon(
                X(-20), Y(-19), X(20), Y(-19),
                X(14), Y(-10), X(3), Y(17),
                X(-7), Y(17), X(6), Y(-10),
                X(-20), Y(-10),
                fill=red, outline=cream, width=W(2),
            )
            canvas.create_line(
                X(-15), Y(-15), X(13), Y(-15),
                fill="#F6A3A0", width=W(2),
            )
            canvas.create_line(
                X(8), Y(-8), X(-1), Y(13),
                fill="#8D1D1D", width=W(2),
            )
            return

        if symbol == "bar":
            # Old embossed BAR plaque.
            canvas.create_rectangle(
                X(-25), Y(-15), X(25), Y(15),
                fill=ink, outline="#11100F", width=W(2),
            )
            canvas.create_rectangle(
                X(-22), Y(-12), X(22), Y(12),
                fill="#3C3732", outline=cream, width=W(1),
            )
            canvas.create_rectangle(
                X(-18), Y(-8), X(18), Y(8),
                fill="#201D1A", outline="#7A7167", width=W(1),
            )
            canvas.create_text(
                x + 1.5 * s, y + 1.5 * s,
                text="BAR",
                fill="#7D756C",
                font=(Theme.FONT, max(7, int(15 * s)), "bold"),
            )
            canvas.create_text(
                x, y,
                text="BAR",
                fill=cream_hi,
                font=(Theme.FONT, max(7, int(15 * s)), "bold"),
            )
            return

        if symbol == "bell":
            # Liberty-bell-style icon with a broad skirt and cast-metal shading.
            canvas.create_oval(
                X(-7), Y(-27), X(7), Y(-20),
                fill=gold_dark, outline=ink, width=W(1),
            )
            canvas.create_polygon(
                X(-6), Y(-22), X(6), Y(-22),
                X(10), Y(-17), X(12), Y(-13),
                X(16), Y(-7), X(17), Y(2),
                X(21), Y(10), X(-21), Y(10),
                X(-17), Y(2), X(-16), Y(-7),
                X(-12), Y(-13), X(-10), Y(-17),
                fill=gold, outline=ink, width=W(2),
                smooth=True,
            )
            canvas.create_arc(
                X(-14), Y(-18), X(14), Y(8),
                start=78, extent=118, style=tk.ARC,
                outline="#F8DB76", width=W(3),
            )
            canvas.create_line(
                X(-18), Y(6), X(18), Y(6),
                fill=gold_dark, width=W(2),
            )
            canvas.create_oval(
                X(-22), Y(6), X(22), Y(14),
                fill="#EBC64E", outline=ink, width=W(2),
            )
            canvas.create_oval(
                X(-5), Y(11), X(5), Y(21),
                fill="#9D6E12", outline=ink, width=W(1),
            )
            return

        if symbol == "cherry":
            # Twin glossy cherries, long curved stems, and one large leaf.
            canvas.create_line(
                X(-11), Y(-4), X(-3), Y(-20), X(6), Y(-24),
                fill=green_dark, width=W(3), smooth=True,
            )
            canvas.create_line(
                X(11), Y(-3), X(4), Y(-18), X(6), Y(-24),
                fill=green_dark, width=W(3), smooth=True,
            )
            canvas.create_polygon(
                X(5), Y(-24), X(21), Y(-28), X(16), Y(-14), X(7), Y(-16),
                fill=green, outline=green_dark, width=W(1), smooth=True,
            )

            shadow_oval(-22, -3, -1, 18, 2.0)
            shadow_oval(2, -1, 23, 20, 2.0)
            canvas.create_oval(
                X(-23), Y(-4), X(-1), Y(18),
                fill=red_dark, outline=ink, width=W(2),
            )
            canvas.create_oval(
                X(-20), Y(-2), X(0), Y(18),
                fill=red, outline="#A01919", width=W(1),
            )
            canvas.create_oval(
                X(1), Y(-2), X(23), Y(20),
                fill=red_dark, outline=ink, width=W(2),
            )
            canvas.create_oval(
                X(4), Y(0), X(24), Y(20),
                fill="#D93434", outline="#A01919", width=W(1),
            )
            canvas.create_oval(
                X(-15), Y(1), X(-9), Y(7),
                fill="#FFC1B1", outline="",
            )
            canvas.create_oval(
                X(9), Y(2), X(14), Y(7),
                fill="#FFC5B5", outline="",
            )
            return

        if symbol == "orange":
            shadow_oval(-21, -20, 21, 21, 2.5)
            canvas.create_oval(
                X(-22), Y(-21), X(22), Y(22),
                fill="#DC761A", outline=ink, width=W(2),
            )
            canvas.create_oval(
                X(-18), Y(-17), X(18), Y(19),
                fill="#F09622", outline="#B55D10", width=W(1),
            )
            glossy_highlight(-15, -14, 10, 10, "#FFD58A")
            canvas.create_line(
                X(1), Y(-19), X(7), Y(-27),
                fill=green_dark, width=W(2),
            )
            canvas.create_polygon(
                X(4), Y(-25), X(20), Y(-29), X(15), Y(-16), X(7), Y(-17),
                fill=green, outline=green_dark, width=W(1),
            )
            # Tiny peel pores for a printed vintage look.
            for px, py in ((-9, 7), (8, 9), (11, -5), (-4, -10)):
                canvas.create_oval(
                    X(px - 1.0), Y(py - 1.0), X(px + 1.0), Y(py + 1.0),
                    fill="#C86916", outline="",
                )
            return

        if symbol == "lemon":
            # Pointed oval lemon, thick outline and simple peel texture.
            canvas.create_polygon(
                X(-25), Y(0), X(-18), Y(-6),
                X(-12), Y(-14), X(0), Y(-17),
                X(12), Y(-14), X(18), Y(-6),
                X(25), Y(0), X(18), Y(6),
                X(12), Y(14), X(0), Y(17),
                X(-12), Y(14), X(-18), Y(6),
                fill="#E7C72B", outline=ink, width=W(2),
                smooth=True,
            )
            canvas.create_polygon(
                X(-18), Y(0), X(-12), Y(-8),
                X(0), Y(-12), X(12), Y(-8),
                X(18), Y(0), X(12), Y(8),
                X(0), Y(12), X(-12), Y(8),
                fill="#F2DC45", outline="",
                smooth=True,
            )
            glossy_highlight(-12, -10, 12, 9, "#FFF6A8")
            canvas.create_polygon(
                X(6), Y(-17), X(20), Y(-22), X(15), Y(-10), X(7), Y(-10),
                fill=green, outline=green_dark, width=W(1),
            )
            return

        if symbol == "plum":
            shadow_oval(-20, -18, 20, 22, 2.5)
            canvas.create_oval(
                X(-21), Y(-19), X(21), Y(22),
                fill="#4E3F8F", outline=ink, width=W(2),
            )
            canvas.create_oval(
                X(-17), Y(-15), X(17), Y(18),
                fill="#7059A8", outline="#4D397B", width=W(1),
            )
            glossy_highlight(-14, -12, 10, 12, "#C3B5E5")
            canvas.create_line(
                X(1), Y(-17), X(7), Y(-26),
                fill="#5F5225", width=W(2),
            )
            canvas.create_polygon(
                X(5), Y(-25), X(19), Y(-27), X(14), Y(-15), X(7), Y(-16),
                fill=green, outline=green_dark, width=W(1),
            )
            return

        if symbol == "melon":
            # Classic whole melon/watermelon: green body, cream ribs and stem.
            shadow_oval(-23, -18, 23, 18, 2.5)
            canvas.create_oval(
                X(-24), Y(-19), X(24), Y(19),
                fill="#3C7F37", outline=ink, width=W(2),
            )
            canvas.create_oval(
                X(-20), Y(-15), X(20), Y(15),
                fill="#65A84A", outline="#3B7434", width=W(1),
            )
            for off in (-12, -4, 4, 12):
                canvas.create_arc(
                    X(off - 9), Y(-15), X(off + 9), Y(15),
                    start=80, extent=200, style=tk.ARC,
                    outline="#D9D37A", width=W(2),
                )
            canvas.create_line(
                X(0), Y(-17), X(5), Y(-25),
                fill=green_dark, width=W(2),
            )
            canvas.create_polygon(
                X(3), Y(-24), X(14), Y(-27), X(10), Y(-18),
                fill=green, outline=green_dark, width=W(1),
            )
            return

        # Safe fallback.
        canvas.create_text(
            x, y,
            text=str(symbol).upper(),
            fill=Theme.TEXT,
            font=(Theme.FONT, max(7, int(12 * s)), "bold"),
        )

    def _draw_reel_stop(
        self,
        canvas: tk.Canvas,
        stop: tuple[str, ...],
        center_x: float,
        center_y: float,
        *,
        scale: float,
    ) -> None:
        """Draw one physical stop; compound stops show both printed symbols."""
        if len(stop) == 1:
            self._draw_classic_symbol(
                canvas, stop[0], center_x, center_y, scale=scale
            )
            return

        # Compound 21 Bell stops are two real printed symbols in one stop.
        child_scale = scale * 0.64
        spread = 27 * scale
        self._draw_classic_symbol(
            canvas, stop[0], center_x - spread, center_y, scale=child_scale
        )
        self._draw_classic_symbol(
            canvas, stop[1], center_x + spread, center_y, scale=child_scale
        )

    def draw_scene(self) -> None:
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
                stop = tuple(sequence[strip_index % len(sequence)])
                y = local_center_y + (strip_index - position) * spacing
                distance = abs(y - local_center_y)

                if distance < 18:
                    icon_scale = 1.02
                elif distance < 78:
                    icon_scale = 0.72
                else:
                    icon_scale = 0.50

                self._draw_reel_stop(
                    reel_canvas,
                    stop,
                    self.REEL_WIDTH / 2,
                    y,
                    scale=icon_scale,
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
            title="21 Bell 老虎機",
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