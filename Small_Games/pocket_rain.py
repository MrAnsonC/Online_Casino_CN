"""Red Packet Rain HMI — ChickenCrossing visual-system edition.

Gameplay is retained from the original ``pocket_rain.py``: each clicked packet
costs one configured stake, immediately returns stake × the packet multiplier,
and the three difficulty distributions keep the original RTP/range settings.
The view layer is rebuilt to match the warm, fixed-size ChickenCrossing HMI and
supports the project's single-Tk ``EmbeddedGamePage`` mode.
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
except ImportError:  # Allow direct execution from the original project folder.
    from small_games import EmbeddedGamePage


VERSION = "PocketRain-ChickenStyle-R2"


class Theme:
    """Visual tokens aligned with ChickenCrossing_tk.py."""

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

    PACKET_RED = "#B64C43"
    PACKET_RED_DARK = "#873D3D"
    PACKET_GOLD = "#D9B65B"
    PACKET_GOLD_DARK = "#9C7A2B"
    PACKET_DISABLED = "#7B7670"
    RAIN_BG = "#BBC9B9"
    RAIN_BAND = "#AFC1B0"
    DANGER_BG = "#D8C9BD"

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

DIFFICULTIES = (
    ("简单", "1", "倍数 0.7–5.0×"),
    ("中等", "2", "倍数 0.5–10.0×"),
    ("地狱", "3", "倍数 0.3–15.0×"),
)

DIFFICULTY_PARAMS = {
    "1": {"rtp": 0.95, "min_mul": 0.7, "max_mul": 5.0},
    "2": {"rtp": 0.93, "min_mul": 0.5, "max_mul": 10.0},
    "3": {"rtp": 0.91, "min_mul": 0.3, "max_mul": 15.0},
}


# ---------------------------------------------------------------------------
# Persistence helpers
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
# Chicken-style reusable controls
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
        font_size: int = 10,
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
    """Physical betting chip matching ChickenCrossing's control language."""

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
            font=(Theme.FONT, 8 if len(self.label) <= 4 else 7, "bold"),
        )

        if disabled:
            self.create_oval(
                7, 3 + offset_y, self.control_width - 8,
                self.control_height - 5 + offset_y,
                fill="#C9C2B8", outline=Theme.BORDER_SOFT, stipple="gray50",
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
        pressed = self._pressed
        self._pressed = False
        inside = 0 <= event.x < self.control_width and 0 <= event.y < self.control_height
        if pressed and inside:
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
# Main game
# ---------------------------------------------------------------------------


class RedPacketRainGame:
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
    CANVAS_HEIGHT = 554
    ACTION_BUTTON_WIDTH = 322
    ACTION_BUTTON_HEIGHT = 38

    def __init__(self, root, initial_balance, username):
        self.root = root
        self._configure_root()

        self.balance = float(initial_balance)
        self.username = username
        self.bet_per_draw = 0.0
        self.difficulty = "1"
        self.game_active = False
        self.stop_generate = False
        self.redpackets: list[dict] = []
        self.generate_after_id = None
        self.move_after_id = None
        self.packet_serial = 0

        # Original round statistics.
        self.round_total_win = 0.0
        self.round_open_count = 0
        self.last_packet_return = 0.0
        self.round_max_multiplier = 0.0

        # Original distribution settings — unchanged.
        self.difficulty_params = DIFFICULTY_PARAMS
        self.difficulty_k: dict[str, float] = {}
        for diff, params in self.difficulty_params.items():
            min_mul = params["min_mul"]
            max_mul = params["max_mul"]
            rtp = params["rtp"]
            if rtp <= min_mul:
                k = 0.0
            else:
                k = (max_mul - min_mul) / (rtp - min_mul) - 1
            self.difficulty_k[diff] = max(k, 0.01)

        self.fall_speed = 3
        self.chip_buttons: list[ChipButton] = []
        self.difficulty_buttons: list[ModernButton] = []

        self.create_widgets()
        self.update_display()
        self._draw_canvas_background()

    # ------------------------------------------------------------------
    # Fixed ChickenCrossing shell
    # ------------------------------------------------------------------

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("红包雨游戏")
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

    def create_widgets(self) -> None:
        self.balance_var = tk.StringVar(value=f"${self.balance:.2f}")
        self.bet_var = tk.StringVar(value="$0.00")
        self.round_return_var = tk.StringVar(value="$0.00")
        self.open_count_var = tk.StringVar(value="0")
        self.last_packet_var = tk.StringVar(value="$0.00")
        self.max_multiplier_var = tk.StringVar(value="0.0×")
        self.info_var = tk.StringVar(value="设置单次下注与难度，然后开始红包雨。")
        self.mode_badge_var = tk.StringVar(value="简单 · 0.7–5.0×")
        self.status_var = tk.StringVar(value="等待开始")

        shell = tk.Frame(
            self.root, width=self.SHELL_WIDTH, height=self.SHELL_HEIGHT, bg=Theme.APP_BG,
        )
        shell.pack(padx=20, pady=18)
        shell.pack_propagate(False)
        shell.grid_propagate(False)

        self._build_header(shell)
        body = tk.Frame(
            shell, width=self.SHELL_WIDTH, height=self.BODY_HEIGHT, bg=Theme.APP_BG,
        )
        body.place(x=0, y=self.BODY_TOP, width=self.SHELL_WIDTH, height=self.BODY_HEIGHT)
        body.pack_propagate(False)
        body.grid_propagate(False)
        self._build_game_panel(body)
        self._build_control_panel(body)

    def _build_header(self, master) -> None:
        header = tk.Frame(
            master, width=self.SHELL_WIDTH, height=self.HEADER_HEIGHT, bg=Theme.APP_BG,
        )
        header.place(x=0, y=0, width=self.SHELL_WIDTH, height=self.HEADER_HEIGHT)
        header.pack_propagate(False)

        tk.Label(
            header, text="🧧", bg=Theme.APP_BG, fg=Theme.RED,
            font=(Theme.FONT_EMOJI, 27), anchor=tk.CENTER,
        ).place(x=0, y=7, width=42, height=44)
        tk.Label(
            header, text="RED PACKET RAIN", bg=Theme.APP_BG, fg=Theme.TEXT,
            font=(Theme.FONT, 20, "bold"), anchor=tk.W,
        ).place(x=52, y=4, width=470, height=31)
        tk.Label(
            header, text="红包雨游戏", bg=Theme.APP_BG, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 10), anchor=tk.W,
        ).place(x=52, y=37, width=520, height=22)

        balance_box = tk.Frame(
            header, width=270, height=54, bg=Theme.PANEL,
            highlightthickness=1, highlightbackground=Theme.BORDER,
        )
        balance_box.place(x=840, y=8, width=270, height=54)
        balance_box.pack_propagate(False)
        self.balance_display_var = tk.StringVar(value=f"账户余额: {self.balance_var.get()}")

        def update_balance_display(*_args):
            self.balance_display_var.set(f"账户余额: {self.balance_var.get()}")

        self.balance_var.trace_add("write", update_balance_display)
        tk.Label(
            balance_box, textvariable=self.balance_display_var, bg=Theme.PANEL,
            fg=Theme.TEXT, font=(Theme.FONT_CJK, 13, "bold"), anchor=tk.E,
        ).place(x=10, y=8, width=245, height=38)

    def _build_game_panel(self, master) -> None:
        panel = self._card(master, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT, padding=0)
        panel.place(x=0, y=0, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT)
        content = panel.content  # type: ignore[attr-defined]

        top = tk.Frame(content, width=self.CANVAS_WIDTH, height=74, bg=Theme.PANEL)
        top.place(x=0, y=0, width=self.CANVAS_WIDTH, height=74)
        top.pack_propagate(False)
        tk.Label(
            top, textvariable=self.info_var, bg=Theme.PANEL, fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 18, "bold"), anchor=tk.W,
        ).place(x=18, y=18, width=565, height=36)
        tk.Label(
            top, textvariable=self.mode_badge_var, bg=Theme.ACCENT_SOFT, fg=Theme.ACCENT,
            font=(Theme.FONT_CJK, 9, "bold"), anchor=tk.CENTER,
        ).place(x=598, y=19, width=128, height=32)

        self.canvas = tk.Canvas(
            content, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT,
            bg=Theme.RAIN_BG, bd=0, highlightthickness=0,
        )
        self.canvas.place(x=0, y=74, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

    def _build_control_panel(self, master) -> None:
        sidebar = tk.Frame(
            master, width=self.SIDEBAR_WIDTH, height=self.BODY_HEIGHT, bg=Theme.APP_BG,
        )
        sidebar.place(
            x=self.GAME_PANEL_WIDTH + self.PANEL_GAP, y=0,
            width=self.SIDEBAR_WIDTH, height=self.BODY_HEIGHT,
        )
        sidebar.pack_propagate(False)

        MetricTile(sidebar, "单次下注", self.bet_var, Theme.CYAN, width=169, height=68).place(
            x=0, y=0, width=169, height=68
        )
        MetricTile(sidebar, "本轮返还", self.round_return_var, Theme.GREEN, width=169, height=68).place(
            x=179, y=0, width=169, height=68
        )

        bet_card = self._card(sidebar, width=348, height=120, padding=12)
        bet_card.place(x=0, y=78, width=348, height=120)
        bet_content = bet_card.content  # type: ignore[attr-defined]
        self._section_title(bet_content, "单次下注", "每打开一个红包扣除一次该金额", width=322)
        for index, (label, amount, chip_color, text_color) in enumerate(CHIP_CONFIGS):
            button = ChipButton(
                bet_content, label=label, amount=amount, chip_color=chip_color,
                text_color=text_color, command=self.add_chip, width=57, height=50,
            )
            button.place(x=index * 66, y=42, width=57, height=50)
            self.chip_buttons.append(button)

        difficulty_card = self._card(sidebar, width=348, height=144, padding=12)
        difficulty_card.place(x=0, y=208, width=348, height=144)
        difficulty_content = difficulty_card.content  # type: ignore[attr-defined]
        self._section_title(difficulty_content, "难度", "难度越高，倍数范围越大", width=322)
        for index, (name, value, detail) in enumerate(DIFFICULTIES):
            button = ModernButton(
                difficulty_content,
                text=f"{name}  ·  {detail}",
                command=lambda v=value: self.set_difficulty(v),
                background=Theme.PANEL_HOVER,
                hover_background=Theme.BORDER_SOFT,
                foreground=Theme.TEXT,
                font_size=10,
            )
            button.place(x=0, y=42 + index * 25, width=322, height=22)
            self.difficulty_buttons.append(button)

        action_card = self._card(sidebar, width=348, height=164, padding=12)
        action_card.place(x=0, y=362, width=348, height=164)
        action_content = action_card.content  # type: ignore[attr-defined]

        stats = tk.Frame(action_content, width=322, height=52, bg=Theme.PANEL)
        stats.place(x=0, y=0, width=322, height=52)
        self._mini_stat(stats, 0, "已打开", self.open_count_var, Theme.TEXT)
        self._mini_stat(stats, 109, "最近返还", self.last_packet_var, Theme.GREEN)
        self._mini_stat(stats, 218, "本轮最高倍数", self.max_multiplier_var, Theme.AMBER)

        self.status_strip = tk.Label(
            action_content, textvariable=self.status_var, bg=Theme.ACCENT_SOFT,
            fg=Theme.ACCENT, font=(Theme.FONT_CJK, 9, "bold"), anchor=tk.CENTER,
        )
        self.status_strip.place(x=0, y=58, width=322, height=25)

        self.button_frame = tk.Frame(action_content, width=322, height=42, bg=Theme.PANEL)
        self.button_frame.place(x=0, y=88, width=322, height=42)
        self.button_frame.pack_propagate(False)

        self.reset_bet_button = ModernButton(
            self.button_frame, text="清空全部筹码", command=self.reset_bet,
            background=Theme.RED, hover_background=Theme.RED_HOVER,
            foreground="#FFFFFF", font_size=12, bold=True,
        )
        self.reset_bet_button.place(x=0, y=0, width=157, height=self.ACTION_BUTTON_HEIGHT)

        self.start_button = ModernButton(
            self.button_frame, text="开始红包雨", command=self.start_game,
            background=Theme.GREEN, hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF", font_size=12, bold=True,
        )
        self.start_button.place(x=165, y=0, width=157, height=self.ACTION_BUTTON_HEIGHT)

        self.stop_button = ModernButton(
            self.button_frame, text="停止红包雨", command=self.stop_game,
            background=Theme.RED, hover_background=Theme.RED_HOVER,
            foreground="#FFFFFF", font_size=12, bold=True,
        )
        self.stop_button.place_forget()

        rules_card = self._card(sidebar, width=348, height=94, padding=12)
        rules_card.place(x=0, y=536, width=348, height=94)
        rules_content = rules_card.content  # type: ignore[attr-defined]
        tk.Label(
            rules_content,
            text="点击仍在有效区域内的红包：每次扣除单次下注，\n立即返还 下注 × 红包倍数；触底后只能查看倍数。",
            bg=Theme.PANEL, fg=Theme.TEXT_MUTED, font=(Theme.FONT_CJK, 10),
            justify=tk.LEFT, anchor=tk.W, wraplength=318,
        ).place(x=0, y=0, width=322, height=66)

        self._refresh_difficulty_styles()

    def _mini_stat(self, master, x: int, label: str, variable: tk.StringVar, color: str) -> None:
        box = tk.Frame(
            master, width=104, height=52, bg=Theme.PANEL_ALT,
            highlightthickness=1, highlightbackground=Theme.BORDER_SOFT,
        )
        box.place(x=x, y=0, width=104, height=52)
        box.pack_propagate(False)
        tk.Label(
            box, text=label, bg=Theme.PANEL_ALT, fg=Theme.TEXT_DIM,
            font=(Theme.FONT_CJK, 8), anchor=tk.CENTER,
        ).place(x=4, y=5, width=96, height=16)
        tk.Label(
            box, textvariable=variable, bg=Theme.PANEL_ALT, fg=color,
            font=(Theme.FONT, 9, "bold"), anchor=tk.CENTER,
        ).place(x=4, y=24, width=96, height=20)

    # ------------------------------------------------------------------
    # Canvas visuals
    # ------------------------------------------------------------------

    def _draw_canvas_background(self) -> None:
        if not hasattr(self, "canvas") or not self.canvas.winfo_exists():
            return
        self.canvas.delete("background")
        w = self.CANVAS_WIDTH
        h = self.CANVAS_HEIGHT

        self.canvas.create_rectangle(0, 0, w, h, fill=Theme.RAIN_BG, outline="", tags="background")
        # Calm vertical lanes give the falling objects spatial rhythm.
        for x in range(0, w, 124):
            self.canvas.create_rectangle(
                x, 0, min(x + 62, w), h - 44,
                fill=Theme.RAIN_BAND, outline="", tags="background",
            )
        # Small hanging marks at the top, decorative only.
        for x in range(32, w, 74):
            self.canvas.create_line(x, 0, x, 14, fill=Theme.BORDER_SOFT, width=2, tags="background")
            self.canvas.create_oval(x - 3, 14, x + 3, 20, fill=Theme.PACKET_GOLD,
                                    outline="", tags="background")

        bottom_y = h - 44
        self.canvas.create_rectangle(
            0, bottom_y, w, h, fill=Theme.DANGER_BG, outline="", tags="background"
        )
        self.canvas.create_line(
            0, bottom_y, w, bottom_y, fill=Theme.RED, width=3, dash=(8, 5), tags="background"
        )
        self.canvas.create_text(
            w / 2, bottom_y + 22,
            text="不可点击区域 · 红包到达此线后只显示倍数",
            fill=Theme.TEXT_MUTED, font=(Theme.FONT_CJK, 10, "bold"), tags="background"
        )
        self.canvas.tag_lower("background")

    def _create_packet_visual(self, x: int, y: int, tag: str) -> tuple[int, int, int]:
        r_width = 60
        r_height = 80
        # Shadow.
        self.canvas.create_rectangle(
            x + 4, y + 5, x + r_width + 4, y + r_height + 5,
            fill="#8E877E", outline="", tags=(tag, "packet"),
        )
        body_id = self.canvas.create_rectangle(
            x, y, x + r_width, y + r_height,
            fill=Theme.PACKET_RED, outline=Theme.PACKET_RED_DARK, width=2,
            tags=(tag, "packet"),
        )
        self.canvas.create_rectangle(
            x + 5, y + 6, x + r_width - 5, y + 24,
            fill="#C85D52", outline="", tags=(tag, "packet"),
        )
        self.canvas.create_line(
            x + 7, y + 29, x + r_width - 7, y + 29,
            fill=Theme.PACKET_GOLD, width=2, tags=(tag, "packet"),
        )
        # Dedicated result badge.  It becomes a high-contrast light panel after
        # the packet is opened, so the multiplier remains readable while falling.
        badge_id = self.canvas.create_rectangle(
            x + 6, y + 35, x + r_width - 6, y + 64,
            fill=Theme.PACKET_GOLD, outline=Theme.PACKET_GOLD_DARK, width=1,
            tags=(tag, "packet"),
        )
        text_id = self.canvas.create_text(
            x + r_width // 2, y + 49,
            text="?", font=(Theme.FONT, 15, "bold"), fill=Theme.PACKET_RED_DARK,
            tags=(tag, "packet"),
        )
        return body_id, badge_id, text_id

    # ------------------------------------------------------------------
    # Betting / difficulty / display
    # ------------------------------------------------------------------

    def add_chip(self, amount: str) -> None:
        if self.game_active:
            return
        try:
            amount_val = float(amount)
        except ValueError:
            return
        new_bet = self.bet_per_draw + amount_val
        if new_bet <= self.balance:
            self.bet_per_draw = new_bet
            self.update_display()
        else:
            messagebox.showwarning("余额不足", "单次下注金额不能超过当前余额")

    def reset_bet(self) -> None:
        if self.game_active:
            return
        self.bet_per_draw = 0.0
        self.update_display()

    def set_difficulty(self, difficulty: str) -> None:
        if self.game_active:
            return
        self.difficulty = difficulty
        self._refresh_difficulty_styles()
        self.update_display()

    def _refresh_difficulty_styles(self) -> None:
        for button, (_name, value, _detail) in zip(self.difficulty_buttons, DIFFICULTIES):
            if value == self.difficulty:
                button.set_colors(Theme.ACCENT, Theme.ACCENT_HOVER, "#FFFFFF")
            else:
                button.set_colors(Theme.PANEL_HOVER, Theme.BORDER_SOFT, Theme.TEXT)

    def update_status(self) -> None:
        if self.game_active:
            self.status_var.set("红包雨进行中 · 点击有效红包")
            self.info_var.set("红包雨进行中 · 点击仍在红线以上的红包。")
        elif self.bet_per_draw <= 0:
            self.status_var.set("请选择单次下注")
            self.info_var.set("选择单次下注与难度，然后开始红包雨。")
        else:
            diff_name = {"1": "简单", "2": "中等", "3": "地狱"}[self.difficulty]
            self.status_var.set(f"已就绪 · {diff_name}模式")
            self.info_var.set(f"单次 ${self.bet_per_draw:.2f} · {diff_name}模式 · 点击开始。")

    def update_display(self) -> None:
        self.balance_var.set(f"${self.balance:.2f}")
        self.bet_var.set(f"${self.bet_per_draw:.2f}")
        self.round_return_var.set(f"${self.round_total_win:.2f}")
        self.open_count_var.set(str(self.round_open_count))
        self.last_packet_var.set(f"${self.last_packet_return:.2f}")
        self.max_multiplier_var.set(f"{self.round_max_multiplier:.1f}×")
        params = self.difficulty_params[self.difficulty]
        diff_name = {"1": "简单", "2": "中等", "3": "地狱"}[self.difficulty]
        self.mode_badge_var.set(
            f"{diff_name} · {params['min_mul']:.1f}–{params['max_mul']:.1f}×"
        )
        self.update_status()

    # ------------------------------------------------------------------
    # Original game flow, with canvas-only visual changes
    # ------------------------------------------------------------------

    def on_canvas_click(self, event) -> None:
        if not self.game_active:
            return
        items = self.canvas.find_overlapping(event.x, event.y, event.x, event.y)
        if not items:
            return
        for item_id in reversed(items):
            tags = self.canvas.gettags(item_id)
            packet_tag = next((tag for tag in tags if tag.startswith("rp_")), None)
            if packet_tag is None:
                continue
            for rp in self.redpackets:
                if rp["tag"] == packet_tag:
                    self.open_redpacket(rp)
                    return

    def generate_multiplier(self) -> float:
        """Original continuous multiplier distribution."""
        params = self.difficulty_params[self.difficulty]
        min_mul = params["min_mul"]
        max_mul = params["max_mul"]
        k = self.difficulty_k[self.difficulty]
        u = random.random()
        multiplier = min_mul + (max_mul - min_mul) * (u ** k)
        return round(multiplier, 1)

    def open_redpacket(self, rp: dict) -> None:
        if not self.game_active or rp["opened"]:
            return
        if not rp["can_click"]:
            self.show_multiplier_on_redpacket(rp)
            return
        if self.balance < self.bet_per_draw:
            messagebox.showwarning("余额不足", "余额不足以继续打开红包，游戏将停止")
            self.stop_game()
            return

        # Original accounting: one stake per opened packet, immediate return.
        self.balance -= self.bet_per_draw
        win_amount = self.bet_per_draw * rp["multiplier"]
        self.balance += win_amount
        self.round_total_win += win_amount
        self.round_open_count += 1
        self.last_packet_return = win_amount
        self.round_max_multiplier = max(self.round_max_multiplier, rp["multiplier"])

        rp["opened"] = True
        rp["can_click"] = False
        self.canvas.itemconfig(
            rp["badge_id"], fill="#F6E7B0", outline="#5B4632", width=2
        )
        self.canvas.itemconfig(
            rp["text_id"],
            text=f"{rp['multiplier']:.1f}×",
            fill="#202428",
            font=(Theme.FONT, 15, "bold"),
        )
        self.canvas.itemconfig(
            rp["body_id"], fill=Theme.PACKET_RED_DARK, outline=Theme.PACKET_GOLD_DARK
        )
        self.status_var.set(f"最近红包返还 ${win_amount:.2f} · {rp['multiplier']:.1f}×")
        self.info_var.set(f"已打开 {self.round_open_count} 个红包 · 最近返还 ${win_amount:.2f}。")
        self.update_display()
        # update_display sets the general running status; restore the richer packet result.
        self.status_var.set(f"最近红包返还 ${win_amount:.2f} · {rp['multiplier']:.1f}×")
        self.info_var.set(f"已打开 {self.round_open_count} 个红包 · 最近返还 ${win_amount:.2f}。")
        update_balance_in_json(self.username, self.balance)

    def show_multiplier_on_redpacket(self, rp: dict) -> None:
        if rp["opened"]:
            return
        rp["opened"] = True
        rp["can_click"] = False
        self.canvas.itemconfig(
            rp["badge_id"], fill="#EEE9E1", outline=Theme.BORDER, width=2
        )
        self.canvas.itemconfig(
            rp["text_id"],
            text=f"{rp['multiplier']:.1f}×",
            fill="#252A2E",
            font=(Theme.FONT, 15, "bold"),
        )
        self.canvas.itemconfig(
            rp["body_id"], fill=Theme.PACKET_DISABLED, outline=Theme.BORDER
        )

    def generate_redpacket(self) -> None:
        if not self.game_active or self.stop_generate:
            return
        if not self.canvas.winfo_exists():
            return

        width = max(self.CANVAS_WIDTH, self.canvas.winfo_width())
        r_width = 60
        r_height = 80
        x = random.randint(20, width - r_width - 20)
        y = 5
        multiplier = self.generate_multiplier()

        self.packet_serial += 1
        tag = f"rp_{self.packet_serial}"
        body_id, badge_id, text_id = self._create_packet_visual(x, y, tag)
        rp_data = {
            "body_id": body_id,
            "badge_id": badge_id,
            "text_id": text_id,
            "tag": tag,
            "multiplier": multiplier,
            "opened": False,
            "y": y,
            "height": r_height,
            "can_click": True,
            "x": x,
            "width": r_width,
        }
        self.redpackets.append(rp_data)

        delay = random.randint(450, 1200)
        self.generate_after_id = self.root.after(delay, self.generate_redpacket)

    def move_redpackets(self) -> None:
        if not self.game_active or not self.canvas.winfo_exists():
            return

        canvas_height = self.CANVAS_HEIGHT
        bottom_limit = canvas_height - 44
        to_remove: list[dict] = []

        for rp in list(self.redpackets):
            new_y = rp["y"] + self.fall_speed
            if (
                new_y + rp["height"] >= bottom_limit
                and rp["can_click"]
                and not rp["opened"]
            ):
                rp["can_click"] = False
                self.show_multiplier_on_redpacket(rp)

            self.canvas.move(rp["tag"], 0, self.fall_speed)
            rp["y"] = new_y
            if rp["y"] > canvas_height:
                to_remove.append(rp)

        for rp in to_remove:
            self.canvas.delete(rp["tag"])
            try:
                self.redpackets.remove(rp)
            except ValueError:
                pass

        self.move_after_id = self.root.after(10, self.move_redpackets)

    def start_game(self) -> None:
        if self.game_active:
            return
        if self.bet_per_draw <= 0:
            messagebox.showwarning("提示", "请先设置单次下注金额")
            return
        if self.balance < self.bet_per_draw:
            messagebox.showwarning("余额不足", "余额不足以进行单次下注")
            return

        self._cancel_jobs()
        self.canvas.delete("all")
        self._draw_canvas_background()
        self.redpackets.clear()
        self.round_total_win = 0.0
        self.round_open_count = 0
        self.last_packet_return = 0.0
        self.round_max_multiplier = 0.0
        self.game_active = True
        self.stop_generate = False

        for button in self.chip_buttons:
            button.configure(state=tk.DISABLED)
        for button in self.difficulty_buttons:
            button.configure(state=tk.DISABLED)
        self.reset_bet_button.place_forget()
        self.start_button.place_forget()
        self.stop_button.place(x=0, y=0, width=322, height=self.ACTION_BUTTON_HEIGHT)

        self.update_display()
        self.generate_redpacket()
        self.move_redpackets()

    def stop_game(self) -> None:
        if not self.game_active:
            return

        self.game_active = False
        self.stop_generate = True
        self._cancel_jobs()
        for rp in self.redpackets:
            if not rp["opened"]:
                self.show_multiplier_on_redpacket(rp)

        self.stop_button.place_forget()
        self.reset_bet_button.place(x=0, y=0, width=157, height=self.ACTION_BUTTON_HEIGHT)
        self.start_button.place(x=165, y=0, width=157, height=self.ACTION_BUTTON_HEIGHT)
        for button in self.chip_buttons:
            button.configure(state=tk.NORMAL)
        for button in self.difficulty_buttons:
            button.configure(state=tk.NORMAL)
        self._refresh_difficulty_styles()

        self.status_var.set("本轮已停止 · 所有剩余红包已揭示")
        self.info_var.set(
            f"本轮结束 · 打开 {self.round_open_count} 个 · 总返还 ${self.round_total_win:.2f}。"
        )
        self.update_display()
        self.status_var.set("本轮已停止 · 所有剩余红包已揭示")
        self.info_var.set(
            f"本轮结束 · 打开 {self.round_open_count} 个 · 总返还 ${self.round_total_win:.2f}。"
        )
        update_balance_in_json(self.username, self.balance)

    def _cancel_jobs(self) -> None:
        if self.generate_after_id is not None:
            try:
                self.root.after_cancel(self.generate_after_id)
            except tk.TclError:
                pass
            self.generate_after_id = None
        if self.move_after_id is not None:
            try:
                self.root.after_cancel(self.move_after_id)
            except tk.TclError:
                pass
            self.move_after_id = None

    def on_closing(self) -> None:
        self.game_active = False
        self.stop_generate = True
        self._cancel_jobs()
        update_balance_in_json(self.username, self.balance)
        finish = getattr(self.root, "finish", None)
        if callable(finish):
            finish(self.balance)
        else:
            self.root.destroy()


# ---------------------------------------------------------------------------
# Public entry point — supports the same single-Tk embedded API as Chicken
# ---------------------------------------------------------------------------


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
            title="红包雨游戏",
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        game = RedPacketRainGame(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = RedPacketRainGame(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    final_balance = main(10000.0, "test_user")
    print(f"Final balance: {final_balance:.2f}")