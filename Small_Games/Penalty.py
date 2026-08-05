"""Penalty Shootout — ChickenCrossing risk-pool continuous-cashout edition.

R4 economy / flow:
- No timing/power meter. The player only chooses a target inside the goal.
- IN / OUT is decided before animation by a Chicken-style fixed danger pool
  without replacement of successful safe cells.
- Each difficulty has exactly 10 safe cells so all modes can reach stage 10:
  Easy 1/11, Medium 2/12, Hard 3/13 initial danger.
- One stake starts a 10-stage run. After every successful goal the goalkeeper
  automatically recovers to the centre; the player may immediately shoot again
  by clicking the goal, or cash out. A later save loses the whole active run.
- Cash-out multipliers are derived so every stage has ~96% RTP:
      multiplier(stage) = 0.96 / cumulative_survival_probability(stage)
- Goalkeeper and shot animation only PRESENT the predetermined outcome; Canvas
  collision, timing bars and animation pose never change the economic result.

R4 redesigns goalkeeper proportions, multi-phase save/recovery animation, and
removes the per-stage continue button: the goal itself continues the run.

The HMI follows the project's fixed 1150x750 ChickenCrossing visual system and
supports EmbeddedGamePage single-Tk embedding.
"""

from __future__ import annotations

import json
import math
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


VERSION = "Penalty-ChickenStyle-R4"
RTP = 0.96
TOTAL_STAGES = 10


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
    GOLD = "#D4B55E"

    SKY = "#AFCAD4"
    CROWD_DARK = "#525B62"
    CROWD = "#69747B"
    PITCH = "#73916F"
    PITCH_ALT = "#7F9B7A"
    PITCH_LINE = "#E9E8DE"
    GOAL_POST = "#F3F1E9"
    NET = "#C9D2CC"
    NET_SHADOW = "#96A49C"

    KEEPER_JERSEY = "#D48738"
    KEEPER_JERSEY_DARK = "#A85F25"
    KEEPER_JERSEY_LIGHT = "#E7A760"
    KEEPER_SHORTS = "#343D43"
    KEEPER_SOCK = "#D48738"
    KEEPER_SKIN = "#C99468"
    KEEPER_GLOVE = "#F0E7CC"
    KEEPER_GLOVE_EDGE = "#8D7D5B"
    KEEPER_BOOT = "#272C30"

    BALL = "#F2F0E9"
    BALL_PATCH = "#30353A"
    AIM = "#D4B55E"
    AIM_INNER = "#F4E1A4"

    STAGE_DONE = "#AAC4A5"
    STAGE_DONE_EDGE = "#4D7D52"
    STAGE_ACTIVE = "#B7CCD5"
    STAGE_ACTIVE_EDGE = "#345E73"
    STAGE_FUTURE = "#D6D0C7"
    STAGE_FUTURE_EDGE = "#AAA196"

    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )


CHIP_CONFIGS = (
    ("$5", 5.0, "#D75A54", "#FFFFFF"),
    ("$25", 25.0, "#67B56A", "#000000"),
    ("$100", 100.0, "#292929", "#FFFFFF"),
    ("$500", 500.0, "#D47AB7", "#000000"),
    ("$1K", 1000.0, "#F4F1EA", "#000000"),
)

DIFFICULTIES = (
    ("简单", "easy", 1, 11),
    ("中等", "medium", 2, 12),
    ("困难", "hard", 3, 13),
)


def build_multiplier_table(pool_cells: int, danger_count: int) -> tuple[float, ...]:
    """Build a 10-stage ~96% RTP cash-out ladder.

    A successful stage removes one safe cell only.  Each R3 difficulty is
    configured with exactly ten safe cells, so stage 10 is always reachable
    while the live danger probability rises sharply after every goal.
    """
    if pool_cells - danger_count < TOTAL_STAGES:
        raise ValueError("difficulty must contain at least 10 safe cells")

    survival = 1.0
    result: list[float] = []
    for step in range(TOTAL_STAGES):
        safe_cells = pool_cells - danger_count - step
        total_cells = pool_cells - step
        survival *= safe_cells / total_cells
        result.append(round(RTP / survival, 2))
    return tuple(result)


DIFFICULTY_SETTINGS = {
    "easy": {
        "name": "简单",
        "danger_count": 1,
        "pool_cells": 11,
        "multipliers": build_multiplier_table(11, 1),
    },
    "medium": {
        "name": "中等",
        "danger_count": 2,
        "pool_cells": 12,
        "multipliers": build_multiplier_table(12, 2),
    },
    "hard": {
        "name": "困难",
        "danger_count": 3,
        "pool_cells": 13,
        "multipliers": build_multiplier_table(13, 3),
    },
}


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def get_data_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../saving_data.json")


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


# ---------------------------------------------------------------------------
# Reusable controls
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
        font_size: int = 11,
        bold: bool = True,
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

    def set_colors(self, bg: str, hover: str, fg: str = "#FFFFFF") -> None:
        self.normal_background = bg
        self.hover_background = hover
        self.normal_foreground = fg
        super().configure(
            bg=bg,
            fg=fg,
            activebackground=hover,
            activeforeground=fg,
        )


class ChipButton(tk.Canvas):
    def __init__(
        self,
        master,
        *,
        label: str,
        amount: float,
        color: str,
        text_color: str,
        command: Callable[[float], None],
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
        self.amount = float(amount)
        self.color = color
        self.text_color = text_color
        self.command = command
        self.w = width
        self.h = height
        self.enabled = True
        self.hovered = False
        self.pressed = False
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.draw()

    @staticmethod
    def _shade(color: str, factor: float) -> str:
        rgb = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
        rgb = [max(0, min(255, round(v * factor))) for v in rgb]
        return "#%02x%02x%02x" % tuple(rgb)

    def draw(self) -> None:
        self.delete("all")
        dy = 2 if self.pressed else 0
        outer = self._shade(self.color, 0.68)
        self.create_oval(6, 7, self.w - 5, self.h - 1, fill="#8E877E", outline="")
        self.create_oval(
            5, 3 + dy, self.w - 6, self.h - 5 + dy,
            fill=outer,
            outline=Theme.TEXT if self.hovered and self.enabled else outer,
            width=3 if self.hovered and self.enabled else 2,
        )
        self.create_oval(
            9, 7 + dy, self.w - 10, self.h - 9 + dy,
            fill=self.color,
            outline=self._shade(self.color, 0.84),
            width=2,
        )
        self.create_text(
            self.w / 2,
            self.h / 2 + dy - 1,
            text=self.label,
            fill=self.text_color,
            font=(Theme.FONT, 9, "bold"),
        )
        if not self.enabled:
            self.create_oval(
                5, 3 + dy, self.w - 6, self.h - 5 + dy,
                fill="#C9C2B8",
                outline=Theme.BORDER_SOFT,
                stipple="gray50",
            )

    def _enter(self, _event) -> None:
        if self.enabled:
            self.hovered = True
            self.draw()

    def _leave(self, _event) -> None:
        self.hovered = False
        self.pressed = False
        self.draw()

    def _press(self, _event) -> None:
        if self.enabled:
            self.pressed = True
            self.draw()

    def _release(self, event) -> None:
        if not self.enabled:
            return
        pressed = self.pressed
        self.pressed = False
        inside = 0 <= event.x < self.w and 0 <= event.y < self.h
        if pressed and inside:
            self.command(self.amount)
        self.draw()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        self.configure(cursor="hand2" if self.enabled else "")
        if not self.enabled:
            self.hovered = False
            self.pressed = False
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


# ---------------------------------------------------------------------------
# Main game
# ---------------------------------------------------------------------------


class PenaltyGame:
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

    GOAL_LEFT = 116
    GOAL_RIGHT = 630
    GOAL_TOP = 104
    GOAL_BOTTOM = 286
    BALL_START = (373.0, 478.0)

    def __init__(self, root, initial_balance: float, username: str):
        self.root = root
        self._configure_root()

        self.balance = float(initial_balance)
        self.username = username
        self.current_bet = 0.0
        self.bet_amount = 0.0
        self.last_win = 0.0

        self.difficulty = "easy"
        self.current_stage = 0
        self.game_active = False
        self.shot_in_progress = False
        self.awaiting_decision = False
        self.shot_ready = False

        self.remaining_cells = DIFFICULTY_SETTINGS[self.difficulty]["pool_cells"]
        self.remaining_dangers = DIFFICULTY_SETTINGS[self.difficulty]["danger_count"]

        self.aim_x = (self.GOAL_LEFT + self.GOAL_RIGHT) / 2
        self.aim_y = (self.GOAL_TOP + self.GOAL_BOTTOM) / 2
        self.ball_pos = self.BALL_START
        self.ball_radius = 21.0
        self.keeper_pose = self._neutral_keeper_pose()
        self.result_overlay = ""
        self.result_color = Theme.TEXT
        self.last_shot_saved: Optional[bool] = None
        self.after_id: Optional[str] = None
        self.shot_history: list[str] = []

        self.balance_var = tk.StringVar()
        self.bet_var = tk.StringVar()
        self.potential_var = tk.StringVar()
        self.stage_var = tk.StringVar()
        self.risk_var = tk.StringVar()
        self.info_var = tk.StringVar(value="选择下注与难度，然后开始高风险 10 关挑战")

        self.chip_buttons: list[ChipButton] = []
        self.difficulty_buttons: dict[str, ModernButton] = {}

        self.create_widgets()
        self.update_display()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("点球连胜")
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
        icon.create_oval(12, 12, 36, 36, fill=Theme.BALL, outline=Theme.TEXT, width=1)
        icon.create_polygon(24, 16, 30, 21, 28, 29, 20, 29, 18, 21,
                            fill=Theme.BALL_PATCH, outline="")

        tk.Label(
            header,
            text="PENALTY STREAK",
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT, 18, "bold"),
            anchor=tk.W,
        ).place(x=74, y=10, width=350, height=27)
        tk.Label(
            header,
            text="点球连胜 · 10 关连续兑现 · RTP 96%",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 11, "bold"),
            anchor=tk.W,
        ).place(x=74, y=39, width=440, height=20)

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

        top = tk.Frame(panel, width=self.CANVAS_WIDTH, height=74, bg=Theme.PANEL)
        top.place(x=0, y=0, width=self.CANVAS_WIDTH, height=74)
        tk.Label(
            top,
            textvariable=self.info_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 17, "bold"),
            anchor=tk.W,
        ).place(x=18, y=11, width=535, height=29)
        tk.Label(
            top,
            text="点击球门选择射门位置",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.W,
        ).place(x=18, y=43, width=350, height=18)
        tk.Label(
            top,
            textvariable=self.risk_var,
            bg=Theme.ACCENT_SOFT,
            fg=Theme.ACCENT,
            font=(Theme.FONT_CJK, 9, "bold"),
            anchor=tk.CENTER,
        ).place(x=580, y=18, width=146, height=31)

        self.game_canvas = tk.Canvas(
            panel,
            width=self.CANVAS_WIDTH,
            height=self.CANVAS_HEIGHT,
            bg=Theme.CANVAS_BG,
            bd=0,
            highlightthickness=0,
            cursor="arrow",
        )
        self.game_canvas.place(x=1, y=74, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT)
        self.game_canvas.bind("<Motion>", self._on_canvas_motion)
        self.game_canvas.bind("<Leave>", self._on_canvas_leave)
        self.game_canvas.bind("<Button-1>", self._on_goal_click)

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
            sidebar, "当前可兑现", self.potential_var, Theme.GREEN,
            width=169, height=68,
        ).place(x=179, y=0, width=169, height=68)

        bet_card = self._card(sidebar, width=348, height=100, padding=9)
        bet_card.place(x=0, y=78, width=348, height=100)
        self._section_title(bet_card.content, "下注金额").place(x=0, y=0, width=110, height=20)
        for index, (label, amount, color, text_color) in enumerate(CHIP_CONFIGS):
            chip = ChipButton(
                bet_card.content,
                label=label,
                amount=amount,
                color=color,
                text_color=text_color,
                command=self.add_chip,
                width=57,
                height=50,
            )
            chip.place(x=index * 62, y=24, width=57, height=50)
            self.chip_buttons.append(chip)

        difficulty_card = self._card(sidebar, width=348, height=88, padding=9)
        difficulty_card.place(x=0, y=188, width=348, height=88)
        self._section_title(difficulty_card.content, "难度").place(x=0, y=0, width=80, height=20)
        for index, (name, key, dangers, pool_cells) in enumerate(DIFFICULTIES):
            button = ModernButton(
                difficulty_card.content,
                text=f"{name} · {dangers}/{pool_cells}",
                command=lambda value=key: self.set_difficulty(value),
                background=Theme.PANEL_ALT,
                hover_background=Theme.PANEL_HOVER,
                foreground=Theme.TEXT,
                font_size=9,
                bold=True,
            )
            button.place(x=index * 107, y=28, width=100, height=34)
            self.difficulty_buttons[key] = button

        ladder_card = self._card(sidebar, width=348, height=204, padding=9)
        ladder_card.place(x=0, y=286, width=348, height=204)
        self._section_title(ladder_card.content, "10 关兑现倍率").place(x=0, y=0, width=130, height=20)
        tk.Label(
            ladder_card.content,
            text="每一关兑现 RTP 约 96% · 后段倍率快速上升",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8),
            anchor=tk.E,
        ).place(x=130, y=1, width=192, height=18)
        self.ladder_canvas = tk.Canvas(
            ladder_card.content,
            width=322,
            height=154,
            bg=Theme.PANEL,
            bd=0,
            highlightthickness=0,
        )
        self.ladder_canvas.place(x=0, y=28, width=322, height=154)

        action_card = self._card(sidebar, width=348, height=130, padding=9)
        action_card.place(x=0, y=500, width=348, height=130)

        stats = tk.Frame(action_card.content, bg=Theme.PANEL)
        stats.place(x=0, y=0, width=322, height=36)
        tk.Label(
            stats, text="阶段", bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8), anchor=tk.W,
        ).place(x=0, y=0, width=45, height=16)
        tk.Label(
            stats, textvariable=self.stage_var, bg=Theme.PANEL, fg=Theme.ACCENT,
            font=(Theme.FONT, 10, "bold"), anchor=tk.W,
        ).place(x=0, y=16, width=90, height=18)
        tk.Label(
            stats, text="下一球风险", bg=Theme.PANEL, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8), anchor=tk.E,
        ).place(x=150, y=0, width=172, height=16)
        tk.Label(
            stats, textvariable=self.risk_var, bg=Theme.PANEL, fg=Theme.RED,
            font=(Theme.FONT, 10, "bold"), anchor=tk.E,
        ).place(x=150, y=16, width=172, height=18)

        self.reset_button = ModernButton(
            action_card.content,
            text="清空下注",
            command=self.reset_bet,
            background=Theme.RED,
            hover_background=Theme.RED_HOVER,
            foreground="#FFFFFF",
            font_size=10,
        )
        # Pregame actions deliberately split the full width 50 / 50.
        self.reset_button.place(x=0, y=44, width=156, height=32)

        self.start_button = ModernButton(
            action_card.content,
            text="开始游戏",
            command=self.start_game,
            background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF",
            font_size=11,
        )
        self.start_button.place(x=166, y=44, width=156, height=32)

        self.cashout_button = ModernButton(
            action_card.content,
            text="兑现",
            command=self.cash_out,
            background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF",
            font_size=11,
        )

        tk.Label(
            action_card.content,
            text="进球后门将自动回中；直接再次点击球门继续，或按兑现结束本局。",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8),
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=322,
        ).place(x=0, y=84, width=322, height=28)

    # ------------------------------------------------------------------
    # Difficulty / economy
    # ------------------------------------------------------------------

    @property
    def multipliers(self) -> tuple[float, ...]:
        return DIFFICULTY_SETTINGS[self.difficulty]["multipliers"]

    def set_difficulty(self, difficulty: str) -> None:
        if self.game_active or self.shot_in_progress:
            return
        if difficulty not in DIFFICULTY_SETTINGS:
            return
        self.difficulty = difficulty
        self.remaining_dangers = DIFFICULTY_SETTINGS[difficulty]["danger_count"]
        self.remaining_cells = DIFFICULTY_SETTINGS[difficulty]["pool_cells"]
        self._refresh_difficulty_buttons()
        self.update_display()

    def _refresh_difficulty_buttons(self) -> None:
        for key, button in self.difficulty_buttons.items():
            selected = key == self.difficulty
            if self.game_active:
                button.configure(state=tk.DISABLED)
            else:
                button.configure(state=tk.DISABLED if selected else tk.NORMAL)
            button.set_colors(
                Theme.ACCENT if selected else Theme.PANEL_ALT,
                Theme.ACCENT_HOVER if selected else Theme.PANEL_HOVER,
                "#FFFFFF" if selected else Theme.TEXT,
            )

    def add_chip(self, amount: float) -> None:
        if self.game_active or self.shot_in_progress:
            return
        amount = float(amount)
        if self.current_bet + amount <= self.balance:
            self.current_bet += amount
            self.last_win = 0.0
            self.update_display()
        else:
            messagebox.showwarning("余额不足", "下注金额不能超过账户余额。", parent=self.root)

    def reset_bet(self) -> None:
        if self.game_active or self.shot_in_progress:
            return
        self.current_bet = 0.0
        self.last_win = 0.0
        self.update_display()

    def _live_failure_rate(self) -> float:
        if self.remaining_cells <= 0:
            return 1.0
        return self.remaining_dangers / self.remaining_cells

    def _draw_risk_failure(self) -> bool:
        """ChickenCrossing-style fixed-pool draw.

        Risk is evaluated from the remaining danger/total counts. A successful
        draw consumes one safe cell, so the danger count stays unchanged while
        the denominator shrinks. A failed draw ends the run immediately.
        """
        failure_rate = self._live_failure_rate()
        failed = random.random() < failure_rate
        if self.remaining_cells > 0:
            self.remaining_cells -= 1
        return failed

    # ------------------------------------------------------------------
    # Game flow
    # ------------------------------------------------------------------

    def start_game(self) -> None:
        if self.game_active or self.shot_in_progress:
            return
        if self.current_bet <= 0:
            messagebox.showwarning("尚未下注", "请先选择下注金额。", parent=self.root)
            return
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "账户余额不足。", parent=self.root)
            return

        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        self.last_win = 0.0
        self.current_stage = 0
        self.game_active = True
        self.awaiting_decision = False
        self.shot_ready = True
        self.result_overlay = ""
        self.last_shot_saved = None
        self.shot_history = []
        self.remaining_cells = DIFFICULTY_SETTINGS[self.difficulty]["pool_cells"]
        self.remaining_dangers = DIFFICULTY_SETTINGS[self.difficulty]["danger_count"]
        self._reset_field()
        self._set_pre_game_controls(False)
        update_balance_in_json(self.username, self.balance)
        self.info_var.set("第 1 关 · 点击球门任意位置射门")
        self.update_display()


    def cash_out(self) -> None:
        if not self.game_active or self.current_stage <= 0 or self.shot_in_progress:
            return
        multiplier = self.multipliers[self.current_stage - 1]
        amount = self.bet_amount * multiplier
        self.balance += amount
        self.last_win = amount
        self.result_overlay = f"CASH OUT  ×{multiplier:.2f}"
        self.result_color = Theme.GOLD
        self.info_var.set(f"兑现成功 · 返还 ${amount:,.2f}")
        update_balance_in_json(self.username, self.balance)
        self._finish_run()

    def _finish_run(self) -> None:
        self.game_active = False
        self.awaiting_decision = False
        self.shot_ready = False
        self.shot_in_progress = False
        self._reset_field()
        self._set_pre_game_controls(True)
        self.update_display()

    def _on_canvas_motion(self, event) -> None:
        if not self.game_active or not self.shot_ready or self.shot_in_progress:
            return
        if self._inside_goal(event.x, event.y):
            self.aim_x = float(event.x)
            self.aim_y = float(event.y)
            self.game_canvas.configure(cursor="crosshair")
            self.draw_scene()
        else:
            self.game_canvas.configure(cursor="arrow")

    def _on_canvas_leave(self, _event) -> None:
        self.game_canvas.configure(cursor="arrow")

    def _on_goal_click(self, event) -> None:
        if not self.game_active or not self.shot_ready or self.shot_in_progress:
            return
        if not self._inside_goal(event.x, event.y):
            return
        self.aim_x = float(event.x)
        self.aim_y = float(event.y)
        self._commit_shot((self.aim_x, self.aim_y))

    def _inside_goal(self, x: float, y: float) -> bool:
        return self.GOAL_LEFT <= x <= self.GOAL_RIGHT and self.GOAL_TOP <= y <= self.GOAL_BOTTOM

    def _commit_shot(self, target: tuple[float, float]) -> None:
        self.shot_ready = False
        self.shot_in_progress = True
        failed = self._draw_risk_failure()

        # The economic result is fixed here. Animation below is presentation only.
        if failed:
            keeper_target = target
        else:
            keeper_target = self._choose_wrong_keeper_target(target)

        self._animate_shot(target, keeper_target, saved=failed)

    def _choose_wrong_keeper_target(self, shot_target: tuple[float, float]) -> tuple[float, float]:
        zones = [
            (165, 135), (373, 135), (581, 135),
            (165, 195), (373, 195), (581, 195),
            (165, 258), (373, 258), (581, 258),
        ]
        sx, sy = shot_target
        candidates = [
            p for p in zones
            if math.hypot(p[0] - sx, p[1] - sy) > 150
        ]
        return random.choice(candidates or zones)

    @staticmethod
    def _mix_pose(a: dict[str, float], b: dict[str, float], t: float) -> dict[str, float]:
        t = max(0.0, min(1.0, t))
        return {key: a[key] + (b[key] - a[key]) * t for key in a}

    @staticmethod
    def _ease_out_cubic(t: float) -> float:
        t = max(0.0, min(1.0, t))
        return 1.0 - (1.0 - t) ** 3

    @staticmethod
    def _ease_in_out_cubic(t: float) -> float:
        t = max(0.0, min(1.0, t))
        if t < 0.5:
            return 4.0 * t * t * t
        return 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0

    def _animate_shot(
        self,
        target: tuple[float, float],
        keeper_target: tuple[float, float],
        *,
        saved: bool,
    ) -> None:
        # R4 uses a three-phase keeper save: preload -> launch -> full extension.
        # This removes the old linear puppet-like interpolation.
        frames = 36
        frame_ms = 22
        start_ball = self.BALL_START
        neutral = self._neutral_keeper_pose()
        preload = self._keeper_preload_pose(keeper_target)
        final_pose = self._keeper_target_pose(keeper_target)

        curve = (target[0] - start_ball[0]) * -0.065

        def keeper_pose_at(t: float) -> dict[str, float]:
            if t < 0.18:
                q = self._ease_in_out_cubic(t / 0.18)
                return self._mix_pose(neutral, preload, q)
            if t < 0.78:
                q = self._ease_out_cubic((t - 0.18) / 0.60)
                return self._mix_pose(preload, final_pose, q)
            # Slight settling at full reach instead of snapping to a hard pose.
            hold = dict(final_pose)
            hold["compression"] = min(1.0, final_pose["compression"] + 0.08)
            q = self._ease_in_out_cubic((t - 0.78) / 0.22)
            return self._mix_pose(final_pose, hold, q)

        def step(frame: int = 0) -> None:
            if frame > frames:
                self._finish_shot_animation(target, keeper_target, saved)
                return

            t = frame / frames
            ball_t = 1.0 - (1.0 - t) ** 2.45

            mx = (start_ball[0] + target[0]) / 2 + curve
            my = (start_ball[1] + target[1]) / 2 - 43
            inv = 1.0 - ball_t
            bx = inv * inv * start_ball[0] + 2 * inv * ball_t * mx + ball_t * ball_t * target[0]
            by = inv * inv * start_ball[1] + 2 * inv * ball_t * my + ball_t * ball_t * target[1]
            self.ball_pos = (bx, by)
            self.ball_radius = 21.0 - 9.5 * ball_t

            self.keeper_pose = keeper_pose_at(min(1.0, t / 0.93))
            self.draw_scene()
            self.after_id = self.root.after(frame_ms, lambda: step(frame + 1))

        step()

    def _animate_keeper_return(self, *, resume_run: bool = True) -> None:
        """Recover naturally to the centre after a save attempt."""
        start_pose = dict(self.keeper_pose)
        neutral = self._neutral_keeper_pose()
        frames = 22
        frame_ms = 20

        def step(frame: int = 0) -> None:
            if frame > frames:
                self.after_id = None
                self.keeper_pose = neutral
                self.ball_pos = self.BALL_START
                self.ball_radius = 21.0
                self.shot_in_progress = False
                self.awaiting_decision = False
                if resume_run:
                    self.shot_ready = True
                    self.result_overlay = ""
                    potential = self.bet_amount * self.multipliers[self.current_stage - 1]
                    self.info_var.set(
                        f"第 {self.current_stage} 关已进球 · 点击球门继续，或兑现 ${potential:,.2f}"
                    )
                else:
                    self.shot_ready = False
                    self.game_active = False
                    self._set_pre_game_controls(True)
                self.update_display()
                return

            t = self._ease_in_out_cubic(frame / frames)
            self.keeper_pose = self._mix_pose(start_pose, neutral, t)
            # Ball visually returns to the spot during the final half of recovery.
            if t > 0.45:
                q = (t - 0.45) / 0.55
                self.ball_pos = (
                    self.ball_pos[0] + (self.BALL_START[0] - self.ball_pos[0]) * q * 0.18,
                    self.ball_pos[1] + (self.BALL_START[1] - self.ball_pos[1]) * q * 0.18,
                )
                self.ball_radius += (21.0 - self.ball_radius) * q * 0.18
            self.draw_scene()
            self.after_id = self.root.after(frame_ms, lambda: step(frame + 1))

        step()

    def _finish_shot_animation(
        self,
        target: tuple[float, float],
        keeper_target: tuple[float, float],
        saved: bool,
    ) -> None:
        self.after_id = None

        if saved:
            self.last_shot_saved = True
            self.result_overlay = "SAVED"
            self.result_color = Theme.RED
            self.shot_history.append("S")
            self.last_win = 0.0
            self.info_var.set(f"第 {self.current_stage + 1} 关被扑出 · 本局归零")
            update_balance_in_json(self.username, self.balance)
            self.update_display()
            # Hold the completed save for a beat, then let the keeper recover
            # naturally instead of snapping back to the centre.
            self.after_id = self.root.after(520, lambda: self._animate_keeper_return(resume_run=False))
            return

        self.last_shot_saved = False
        self.current_stage += 1
        multiplier = self.multipliers[self.current_stage - 1]
        potential = self.bet_amount * multiplier
        self.result_overlay = "GOAL"
        self.result_color = Theme.GREEN
        self.shot_history.append("G")

        if self.current_stage >= TOTAL_STAGES:
            self.shot_in_progress = False
            self.balance += potential
            self.last_win = potential
            self.info_var.set(f"第 10 关完成 · 自动兑现 ${potential:,.2f}")
            update_balance_in_json(self.username, self.balance)
            self._finish_run()
            return

        # No 'continue' confirmation.  The keeper recovers automatically, then
        # the goal becomes clickable for the next stage while cash-out stays available.
        self.awaiting_decision = False
        self.info_var.set(f"第 {self.current_stage} 关进球 · 门将回位中…")
        self.update_display()
        self.after_id = self.root.after(360, self._animate_keeper_return)

    # ------------------------------------------------------------------
    # Keeper geometry / drawing
    # ------------------------------------------------------------------

    def _neutral_keeper_pose(self) -> dict[str, float]:
        return {
            "cx": 373.0,
            "cy": 252.0,
            "angle": 0.0,
            "air": 0.0,
            "reach": 0.18,
            "crouch": 0.16,
            "spread": 0.28,
            "compression": 0.0,
            "side": 0.0,
            "high": 0.0,
        }

    def _keeper_preload_pose(self, target: tuple[float, float]) -> dict[str, float]:
        tx, ty = target
        side = max(-1.0, min(1.0, (tx - 373.0) / 215.0))
        high = max(-1.0, min(1.0, (190.0 - ty) / 92.0))
        return {
            "cx": 373.0 - side * 8.0,
            "cy": 254.0 + max(0.0, -high) * 5.0,
            "angle": side * 0.06,
            "air": 0.0,
            "reach": 0.28,
            "crouch": 0.38 + max(0.0, -high) * 0.16,
            "spread": 0.40,
            "compression": 0.38,
            "side": side,
            "high": high,
        }

    def _keeper_target_pose(self, target: tuple[float, float]) -> dict[str, float]:
        tx, ty = target
        side = max(-1.0, min(1.0, (tx - 373.0) / 215.0))
        high = max(-1.0, min(1.0, (190.0 - ty) / 92.0))
        abs_side = abs(side)
        high_pos = max(0.0, high)
        low = max(0.0, -high)

        # Realistic save categories emerge continuously from target position:
        # central = set/block, high lateral = airborne dive, low lateral = skid save.
        return {
            "cx": 373.0 + side * (132.0 + 24.0 * high_pos),
            "cy": 250.0 - high_pos * (47.0 + 18.0 * abs_side) + low * 24.0,
            "angle": side * (0.18 + 0.88 * abs_side) * (1.0 - 0.18 * low),
            "air": min(1.0, high_pos * 0.90 + abs_side * 0.36),
            "reach": min(1.0, 0.48 + abs_side * 0.50 + high_pos * 0.18),
            "crouch": min(1.0, 0.14 + low * 0.78 + (1.0 - abs_side) * 0.10),
            "spread": min(1.0, 0.34 + low * 0.55 + abs_side * 0.25),
            "compression": 0.08,
            "side": side,
            "high": high,
        }

    @staticmethod
    def _basis_point(
        origin: tuple[float, float],
        right: tuple[float, float],
        up: tuple[float, float],
        x: float,
        y: float,
    ) -> tuple[float, float]:
        return (
            origin[0] + right[0] * x + up[0] * y,
            origin[1] + right[1] * x + up[1] * y,
        )

    def _draw_keeper(self) -> None:
        """Draw a proportioned articulated goalkeeper rather than a rotating puppet."""
        c = self.game_canvas
        p = self.keeper_pose
        cx, cy = p["cx"], p["cy"]
        angle = p["angle"] * math.radians(54)
        air = p["air"]
        reach = p["reach"]
        crouch = p["crouch"]
        spread = p["spread"]
        side = p["side"]
        high = p["high"]

        right = (math.cos(angle), math.sin(angle))
        up = (math.sin(angle), -math.cos(angle))
        origin = (cx, cy)

        # Body proportions are intentionally more human: larger torso/head relation,
        # narrower waist, longer limbs and asymmetric push-off/trailing legs.
        pelvis = self._basis_point(origin, right, up, 0, 0)
        chest = self._basis_point(origin, right, up, 0, 42 - crouch * 12)
        neck = self._basis_point(chest, right, up, 0, 18)
        head = self._basis_point(neck, right, up, side * 2, 13)

        shadow_y = 297
        shadow_half = 35 + abs(side) * 55
        shadow_h = max(3.0, 10.0 - air * 5.5)
        c.create_oval(
            cx - shadow_half, shadow_y - shadow_h,
            cx + shadow_half, shadow_y + shadow_h,
            fill="#39413E", outline="", stipple="gray50", tags="keeper",
        )

        # Legs first so torso/arms layer naturally above them.
        hip_l = self._basis_point(pelvis, right, up, -13, 1)
        hip_r = self._basis_point(pelvis, right, up, 13, 1)
        dive_sign = 1.0 if side >= 0 else -1.0
        low = max(0.0, -high)

        for idx, (hip_pt, sign) in enumerate(((hip_l, -1.0), (hip_r, 1.0))):
            leading = (sign == dive_sign)
            if abs(side) < 0.12:
                leading = sign > 0

            lateral = sign * (17 + spread * 23)
            if abs(side) > 0.15:
                lateral += -side * (8 if leading else 24)
            knee = (
                hip_pt[0] + right[0] * lateral + up[0] * (-26 + low * 8),
                hip_pt[1] + right[1] * lateral + up[1] * (-26 + low * 8),
            )
            extension = 31 + (10 if not leading and abs(side) > 0.2 else 0) + low * 8
            foot = (
                knee[0] + right[0] * (sign * (10 + spread * 12) - side * 13) + up[0] * (-extension),
                knee[1] + right[1] * (sign * (10 + spread * 12) - side * 13) + up[1] * (-extension),
            )

            c.create_line(*hip_pt, *knee, fill=Theme.KEEPER_SHORTS, width=12,
                          capstyle=tk.ROUND, tags="keeper")
            c.create_line(*knee, *foot, fill=Theme.KEEPER_SOCK, width=9,
                          capstyle=tk.ROUND, tags="keeper")
            boot_tip = (foot[0] + right[0] * sign * 8, foot[1] + right[1] * sign * 8)
            c.create_line(*foot, *boot_tip, fill=Theme.KEEPER_BOOT, width=8,
                          capstyle=tk.ROUND, tags="keeper")

        # Shorts / torso.
        shorts = [
            self._basis_point(pelvis, right, up, -16, 4),
            self._basis_point(pelvis, right, up, 16, 4),
            self._basis_point(pelvis, right, up, 13, -14),
            self._basis_point(pelvis, right, up, -13, -14),
        ]
        c.create_polygon(*sum(([x, y] for x, y in shorts), []),
                         fill=Theme.KEEPER_SHORTS, outline="#20292E", width=1, tags="keeper")

        torso = [
            self._basis_point(chest, right, up, -21, 2),
            self._basis_point(chest, right, up, 21, 2),
            self._basis_point(pelvis, right, up, 15, 3),
            self._basis_point(pelvis, right, up, -15, 3),
        ]
        c.create_polygon(*sum(([x, y] for x, y in torso), []),
                         fill=Theme.KEEPER_JERSEY, outline=Theme.KEEPER_JERSEY_DARK,
                         width=2, tags="keeper")

        # Jersey shoulder panel and number give the figure a sports-game silhouette.
        shoulder_a = self._basis_point(chest, right, up, -19, -1)
        shoulder_b = self._basis_point(chest, right, up, 19, -1)
        c.create_line(*shoulder_a, *shoulder_b, fill=Theme.KEEPER_JERSEY_LIGHT,
                      width=5, tags="keeper")
        number_pos = self._basis_point(chest, right, up, 0, -12)
        c.create_text(number_pos[0], number_pos[1], text="1", fill="#F4E8CF",
                      font=(Theme.FONT, 9, "bold"), angle=-math.degrees(angle), tags="keeper")

        # Arms.  In side dives both hands travel toward the ball but retain elbow bend.
        sh_l = self._basis_point(chest, right, up, -22, 0)
        sh_r = self._basis_point(chest, right, up, 22, 0)
        high_world = max(-1.0, min(1.0, high))
        side_abs = abs(side)

        if side_abs < 0.18:
            # Central block: symmetric hands, high shots overhead / low shots down.
            hand_l = (sh_l[0] - 18, sh_l[1] - 24 - high_world * 28 + low * 28)
            hand_r = (sh_r[0] + 18, sh_r[1] - 24 - high_world * 28 + low * 28)
        else:
            reach_len = 47 + reach * 32
            vertical = -18 - max(0.0, high_world) * 33 + low * 22
            lead_sh = sh_r if side > 0 else sh_l
            trail_sh = sh_l if side > 0 else sh_r
            lead_hand = (lead_sh[0] + dive_sign * reach_len, lead_sh[1] + vertical)
            trail_hand = (trail_sh[0] + dive_sign * (reach_len - 15), trail_sh[1] + vertical + 8)
            if side > 0:
                hand_r, hand_l = lead_hand, trail_hand
            else:
                hand_l, hand_r = lead_hand, trail_hand

        for shoulder_pt, hand in ((sh_l, hand_l), (sh_r, hand_r)):
            elbow = (
                shoulder_pt[0] * 0.46 + hand[0] * 0.54 - up[0] * 5,
                shoulder_pt[1] * 0.46 + hand[1] * 0.54 - up[1] * 5,
            )
            c.create_line(*shoulder_pt, *elbow, fill=Theme.KEEPER_JERSEY,
                          width=10, capstyle=tk.ROUND, tags="keeper")
            c.create_line(*elbow, *hand, fill=Theme.KEEPER_JERSEY_LIGHT,
                          width=8, capstyle=tk.ROUND, tags="keeper")
            # Glove palm + cuff.
            cuff = ((elbow[0] + hand[0]) / 2 * 0.15 + hand[0] * 0.85,
                    (elbow[1] + hand[1]) / 2 * 0.15 + hand[1] * 0.85)
            c.create_line(*cuff, *hand, fill=Theme.KEEPER_GLOVE_EDGE, width=10,
                          capstyle=tk.ROUND, tags="keeper")
            c.create_oval(hand[0] - 8, hand[1] - 8, hand[0] + 8, hand[1] + 8,
                          fill=Theme.KEEPER_GLOVE, outline=Theme.KEEPER_GLOVE_EDGE,
                          width=2, tags="keeper")

        # Neck/head last.
        c.create_line(*neck, *head, fill=Theme.KEEPER_SKIN, width=7,
                      capstyle=tk.ROUND, tags="keeper")
        c.create_oval(head[0] - 12, head[1] - 13, head[0] + 12, head[1] + 13,
                      fill=Theme.KEEPER_SKIN, outline="#73513D", width=1, tags="keeper")
        c.create_arc(head[0] - 12, head[1] - 14, head[0] + 12, head[1] + 5,
                     start=0, extent=180, style=tk.PIESLICE,
                     fill="#352F2A", outline="#352F2A", tags="keeper")


    # ------------------------------------------------------------------
    # Scene drawing
    # ------------------------------------------------------------------

    def _reset_field(self) -> None:
        self.ball_pos = self.BALL_START
        self.ball_radius = 21.0
        self.keeper_pose = self._neutral_keeper_pose()
        self.aim_x = (self.GOAL_LEFT + self.GOAL_RIGHT) / 2
        self.aim_y = (self.GOAL_TOP + self.GOAL_BOTTOM) / 2
        self.draw_scene()

    def _draw_goal(self) -> None:
        c = self.game_canvas
        left, right = self.GOAL_LEFT, self.GOAL_RIGHT
        top, bottom = self.GOAL_TOP, self.GOAL_BOTTOM
        back_left, back_right = left + 25, right - 25
        back_top = top + 22

        # Back net plane.
        c.create_polygon(
            back_left, back_top,
            back_right, back_top,
            right, bottom,
            left, bottom,
            fill="#80958A",
            outline="",
            stipple="gray50",
            tags="goal",
        )

        # Net grid in perspective.
        for i in range(1, 11):
            t = i / 11
            x_top = back_left + (back_right - back_left) * t
            x_bottom = left + (right - left) * t
            c.create_line(x_top, back_top, x_bottom, bottom, fill=Theme.NET, width=1, tags="goal")
        for i in range(1, 6):
            t = i / 6
            y = back_top + (bottom - back_top) * t
            inset = 25 * (1 - t)
            c.create_line(left + inset, y, right - inset, y, fill=Theme.NET, width=1, tags="goal")

        # Thick frame.
        c.create_line(left, bottom, left, top, right, top, right, bottom,
                      fill=Theme.GOAL_POST, width=8, joinstyle=tk.ROUND, tags="goal")
        c.create_line(left + 7, bottom, right - 7, bottom, fill=Theme.GOAL_POST, width=5, tags="goal")

    def _draw_ball(self) -> None:
        c = self.game_canvas
        x, y = self.ball_pos
        r = self.ball_radius
        c.create_oval(x - r, y - r, x + r, y + r,
                      fill=Theme.BALL, outline="#33383C", width=2, tags="ball")
        c.create_polygon(
            x, y - r * 0.46,
            x + r * 0.42, y - r * 0.12,
            x + r * 0.26, y + r * 0.38,
            x - r * 0.26, y + r * 0.38,
            x - r * 0.42, y - r * 0.12,
            fill=Theme.BALL_PATCH,
            outline="",
            tags="ball",
        )
        for angle in range(0, 360, 72):
            rad = math.radians(angle)
            px = x + math.cos(rad) * r * 0.72
            py = y + math.sin(rad) * r * 0.72
            c.create_oval(px - r * 0.12, py - r * 0.12, px + r * 0.12, py + r * 0.12,
                          fill=Theme.BALL_PATCH, outline="", tags="ball")

    def _draw_stage_strip(self) -> None:
        c = self.game_canvas
        left = 61
        y = 18
        gap = 5
        total_width = self.CANVAS_WIDTH - left * 2
        cell_w = (total_width - gap * 9) / 10
        for index in range(10):
            x1 = left + index * (cell_w + gap)
            x2 = x1 + cell_w
            if index < self.current_stage:
                fill = Theme.STAGE_DONE
                edge = Theme.STAGE_DONE_EDGE
                fg = Theme.STAGE_DONE_EDGE
            elif index == self.current_stage and self.game_active:
                fill = Theme.STAGE_ACTIVE
                edge = Theme.STAGE_ACTIVE_EDGE
                fg = Theme.ACCENT
            else:
                fill = Theme.STAGE_FUTURE
                edge = Theme.STAGE_FUTURE_EDGE
                fg = Theme.TEXT_DIM
            c.create_rectangle(x1, y, x2, y + 38, fill=fill, outline=edge,
                               width=2 if index == self.current_stage and self.game_active else 1,
                               tags="stage")
            c.create_text((x1 + x2) / 2, y + 11, text=f"{index + 1}",
                          fill=fg, font=(Theme.FONT, 7, "bold"), tags="stage")
            c.create_text((x1 + x2) / 2, y + 27, text=f"×{self.multipliers[index]:.2f}",
                          fill=Theme.TEXT if index != self.current_stage else Theme.AMBER,
                          font=(Theme.FONT, 7, "bold"), tags="stage")

    def draw_scene(self) -> None:
        c = self.game_canvas
        c.delete("all")
        w = self.CANVAS_WIDTH
        h = self.CANVAS_HEIGHT

        # Broadcast-style stadium background.
        c.create_rectangle(0, 0, w, 86, fill=Theme.SKY, outline="")
        c.create_rectangle(0, 56, w, 116, fill=Theme.CROWD_DARK, outline="")
        for x in range(8, w, 18):
            crowd_fill = Theme.CROWD if (x // 18) % 2 == 0 else "#7C6F67"
            c.create_oval(x, 69 + (x % 3) * 3, x + 8, 77 + (x % 3) * 3,
                          fill=crowd_fill, outline="")

        # Perspective pitch.
        c.create_polygon(0, 116, w, 116, w, h, 0, h, fill=Theme.PITCH, outline="")
        c.create_polygon(0, 116, w / 2, 116, w / 2, h, 0, h,
                         fill=Theme.PITCH_ALT, outline="")
        c.create_polygon(w / 2, 116, w, 116, w, h, w / 2, h,
                         fill=Theme.PITCH, outline="")

        # Penalty area perspective lines.
        c.create_line(92, 302, 654, 302, fill=Theme.PITCH_LINE, width=2)
        c.create_line(92, 302, 22, h, fill=Theme.PITCH_LINE, width=2)
        c.create_line(654, 302, 724, h, fill=Theme.PITCH_LINE, width=2)
        c.create_arc(275, 300, 471, 390, start=190, extent=160,
                     outline=Theme.PITCH_LINE, width=2, style=tk.ARC)

        self._draw_stage_strip()
        self._draw_goal()
        self._draw_keeper()
        self._draw_ball()

        # Aim ring exists only when the player is allowed to choose a shot.
        if self.game_active and self.shot_ready and not self.shot_in_progress:
            r = 20
            c.create_oval(
                self.aim_x - r, self.aim_y - r,
                self.aim_x + r, self.aim_y + r,
                outline=Theme.AIM,
                width=3,
                dash=(5, 3),
                tags="aim",
            )
            c.create_oval(
                self.aim_x - 5, self.aim_y - 5,
                self.aim_x + 5, self.aim_y + 5,
                fill=Theme.AIM_INNER,
                outline=Theme.AMBER,
                width=1,
                tags="aim",
            )

        if self.result_overlay:
            c.create_text(
                w / 2,
                344,
                text=self.result_overlay,
                fill=self.result_color,
                font=(Theme.FONT, 27, "bold"),
            )

        # Recent sequence is compact and unobtrusive.
        c.create_text(32, 505, text="本局", fill=Theme.TEXT_MUTED,
                      font=(Theme.FONT_CJK, 8, "bold"), anchor=tk.W)
        for index in range(10):
            x = 82 + index * 46
            value = self.shot_history[index] if index < len(self.shot_history) else "·"
            if value == "G":
                fill = Theme.GREEN
            elif value == "S":
                fill = Theme.RED
            else:
                fill = Theme.TEXT_DIM
            c.create_text(x, 505, text=value, fill=fill,
                          font=(Theme.FONT, 10, "bold"))

    def draw_ladder(self) -> None:
        c = self.ladder_canvas
        c.delete("all")
        multipliers = self.multipliers
        cols = 5
        gap = 5
        cell_w = (322 - gap * 4) / 5
        cell_h = 70
        for index, multiplier in enumerate(multipliers):
            row = index // cols
            col = index % cols
            x1 = col * (cell_w + gap)
            y1 = row * 76
            x2 = x1 + cell_w
            y2 = y1 + cell_h
            if index < self.current_stage:
                fill = Theme.STAGE_DONE
                edge = Theme.STAGE_DONE_EDGE
            elif index == self.current_stage and self.game_active:
                fill = Theme.STAGE_ACTIVE
                edge = Theme.STAGE_ACTIVE_EDGE
            else:
                fill = Theme.PANEL_ALT
                edge = Theme.BORDER_SOFT
            c.create_rectangle(x1, y1, x2, y2, fill=fill, outline=edge,
                               width=2 if index == self.current_stage and self.game_active else 1)
            c.create_text((x1 + x2) / 2, y1 + 17, text=f"第{index + 1}关",
                          fill=Theme.TEXT_MUTED, font=(Theme.FONT_CJK, 7, "bold"))
            c.create_text((x1 + x2) / 2, y1 + 42, text=f"{multiplier:.2f}×",
                          fill=Theme.ACCENT, font=(Theme.FONT, 9, "bold"))
            if index < self.current_stage:
                c.create_text((x1 + x2) / 2, y1 + 59, text="IN",
                              fill=Theme.GREEN, font=(Theme.FONT, 7, "bold"))

    # ------------------------------------------------------------------
    # UI state
    # ------------------------------------------------------------------

    def _set_pre_game_controls(self, enabled: bool) -> None:
        for chip in self.chip_buttons:
            chip.set_enabled(enabled)
        self.reset_button.configure(state=tk.NORMAL if enabled else tk.DISABLED)
        self.start_button.configure(state=tk.NORMAL if enabled else tk.DISABLED)
        self._refresh_difficulty_buttons()

    def _sync_action_buttons(self) -> None:
        self.reset_button.place_forget()
        self.start_button.place_forget()
        self.cashout_button.place_forget()

        if not self.game_active:
            # Exactly half / half across the 322 px action width.
            self.reset_button.place(x=0, y=44, width=156, height=32)
            self.start_button.place(x=166, y=44, width=156, height=32)
            self.reset_button.configure(state=tk.NORMAL)
            self.start_button.configure(state=tk.NORMAL)
            return

        # During an active run the goal itself is the 'continue' control.
        # Cash-out becomes available after at least one successful stage.
        if self.current_stage > 0:
            amount = self.bet_amount * self.multipliers[self.current_stage - 1]
            self.cashout_button.configure(
                text=f"兑现 ${amount:,.2f}",
                state=tk.DISABLED if self.shot_in_progress else tk.NORMAL,
            )
            self.cashout_button.place(x=0, y=44, width=322, height=32)

    def update_display(self) -> None:
        self.balance_var.set(f"${self.balance:,.2f}")
        self.bet_var.set(f"${self.current_bet:,.2f}")

        if self.game_active and self.current_stage > 0:
            potential = self.bet_amount * self.multipliers[self.current_stage - 1]
            self.potential_var.set(f"${potential:,.2f}")
        else:
            self.potential_var.set("$0.00")

        self.stage_var.set(f"{self.current_stage} / {TOTAL_STAGES}")
        if self.game_active and self.current_stage < TOTAL_STAGES:
            self.risk_var.set(f"{self._live_failure_rate() * 100:.2f}%")
        else:
            setting = DIFFICULTY_SETTINGS[self.difficulty]
            initial = setting["danger_count"] / setting["pool_cells"]
            self.risk_var.set(f"{initial * 100:.2f}%")

        self._refresh_difficulty_buttons()
        self._sync_action_buttons()
        self.draw_ladder()
        self.draw_scene()

    def on_closing(self) -> None:
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None
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
                "EmbeddedGamePage is unavailable. Place Penalty.py inside the "
                "Small_Games package or make small_games.py importable."
            )
        page = EmbeddedGamePage(
            parent,
            title="点球连胜",
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        page.set_requested_size(1150, 750)
        game = PenaltyGame(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = PenaltyGame(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    final_balance = main(10000.0, "demo_player")
    print(f"Final balance: {final_balance:.2f}")