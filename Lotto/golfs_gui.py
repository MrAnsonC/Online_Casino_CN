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
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Dict, Optional, Set, Tuple


# =========================================================
# 与 Banknote_Detection_gui 一致的视觉规范
# =========================================================
ROOT_BG = "#1B3D31"
TABLE_INNER = "#2A4A3C"
TEXT = "#FFFFFF"
GOLD = "#D4AF37"
PANEL_BG = "#F2E6C9"
HEADER_BG = "#D8B46A"
TITLE_FG = "#2A1B08"
ACCENT_FG = "#A88100"
SUCCESS = "#2E8B57"
DANGER = "#C0392B"
SILVER_PALETTE = ("#D7D9D8", "#C8CCCA", "#B8BDBB", "#A9AEAC", "#D0D3D2")


# =========================================================
# 用户余额文件操作
# =========================================================
def get_data_file_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "A_Tools/Account/saving_data.json",
    )


def load_user_data() -> list:
    try:
        with open(get_data_file_path(), "r", encoding="utf-8") as file:
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
            user["cash"] = f"{float(new_balance):.2f}"
            save_user_data(users)
            return


# =========================================================
# 游戏数据与中奖逻辑
# =========================================================
EMOJI_LIST = ["🏦", "💵", "💲", "🧧", "💰", "💎", "🪙"]

# 奖金只由连线位置决定，与格子中的 emoji 种类无关。
# 位置编号：
# 1 2 3
# 4 5 6
# 7 8 9
WIN_LINES = (
    ("123", (0, 1, 2), 1),
    ("456", (3, 4, 5), 5),
    ("789", (6, 7, 8), 20),
    ("147", (0, 3, 6), 2),
    ("258", (1, 4, 7), 40),
    ("369", (2, 5, 8), 100),
    ("159", (0, 4, 8), 10000),
)
LINE_BY_PRIZE = {prize: (name, indices, prize) for name, indices, prize in WIN_LINES}

# 保留原程序的中奖权重；键是本张票预设的中奖金额，0 表示不中奖。
OUTCOME_WEIGHTS = {
    0: 451603,
    1: 258059,
    2: 129030,
    5: 96772,
    20: 32257,
    40: 32257,
    100: 15,
    10000: 3.0464990000000003,
}


def check_for_wins(card: list) -> list:
    """返回所有有效中奖线；不检查 357 反斜线。"""
    if len(card) != 3 or any(len(row) != 3 for row in card):
        return []

    flat_card = [symbol for row in card for symbol in row]
    wins = []
    for line_name, indices, prize in WIN_LINES:
        symbols = [flat_card[index] for index in indices]
        if symbols[0] == symbols[1] == symbols[2]:
            wins.append((line_name, prize, symbols[0]))
    return wins


def check_for_win(card: list) -> int:
    """兼容旧调用：返回全部有效中奖线的奖金总额。"""
    return sum(prize for _line_name, prize, _symbol in check_for_wins(card))


def generate_scratch_card(forced_prize: Optional[int] = None) -> list:
    """生成纯 emoji 九宫格，并确保只出现预设的有效中奖线。"""
    if forced_prize is None:
        selected_prize = random.choices(
            list(OUTCOME_WEIGHTS), weights=OUTCOME_WEIGHTS.values(), k=1
        )[0]
    else:
        if forced_prize not in OUTCOME_WEIGHTS:
            raise ValueError(f"不支持的中奖金额: {forced_prize}")
        selected_prize = forced_prize

    target_line = LINE_BY_PRIZE.get(selected_prize)

    # 中奖线最多固定 3 个格子，其余格子随机；若意外形成其他有效连线便重生成。
    for _attempt in range(10000):
        flat_card = [random.choice(EMOJI_LIST) for _ in range(9)]
        if target_line is not None:
            _line_name, indices, _prize = target_line
            winning_symbol = random.choice(EMOJI_LIST)
            for index in indices:
                flat_card[index] = winning_symbol

        card = [flat_card[index : index + 3] for index in range(0, 9, 3)]
        wins = check_for_wins(card)
        if selected_prize == 0 and not wins:
            return card
        if selected_prize > 0 and len(wins) == 1 and wins[0][1] == selected_prize:
            return card

    # 理论上几乎不会走到这里；提供一个明确错误，避免派彩与票面不一致。
    raise RuntimeError("无法生成符合指定连线规则的九宫格")


class PassThreeLevelsGame(tk.Frame):
    """按验钞刮刮乐视觉规范重制的“过三关”九宫格刮刮乐。"""

    TICKET_COST = 1.0
    REVEAL_THRESHOLD = 0.72
    BRUSH_RADIUS = 24
    CELL_WIDTH = 132
    CELL_HEIGHT = 82
    CELL_GAP = 10
    GRID_X = 107
    GRID_Y = 235

    def __init__(
        self,
        parent: tk.Misc,
        initial_balance: float,
        username: str,
        on_back: Optional[Callable[[float], None]] = None,
        on_balance_change: Optional[Callable[[float], None]] = None,
    ):
        super().__init__(parent, bg=ROOT_BG)
        self.balance = float(initial_balance)
        self.username = username
        self.on_back = on_back
        self.on_balance_change = on_balance_change

        self.card: Optional[list] = None
        self.ticket_active = False
        self.prize_paid = False
        self.revealed: Set[int] = set()
        self.scratch_areas: Dict[int, Dict[str, object]] = {}
        self.auto_reveal_job: Optional[str] = None
        self._last_scratch_xy: Optional[Tuple[int, int]] = None
        self._closing = False

        self.balance_var = tk.StringVar()
        self.stage_var = tk.StringVar(value="待购票")
        self.status_var = tk.StringVar(value="购买票券后，按住鼠标拖动刮开九宫格。")
        self.serial_var = tk.StringVar(value="票号: ------------")
        self.progress_var = tk.StringVar(value="0%")
        self.opened_var = tk.StringVar(value="已刮开: 0 / 9")
        self.last_win_var = tk.StringVar(value="本局赢得: $0.00")

        self._build_ui()
        self._refresh_balance()
        self._draw_empty_ticket()

    # =====================================================
    # UI
    # =====================================================
    def _build_ui(self) -> None:
        main_frame = tk.Frame(self, bg=ROOT_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left_frame = tk.Frame(main_frame, bg=ROOT_BG)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.table_canvas = tk.Canvas(
            left_frame,
            width=720,
            height=710,
            bg=ROOT_BG,
            highlightthickness=0,
            cursor="crosshair",
        )
        self.table_canvas.pack(fill=tk.BOTH, expand=True)
        self.table_canvas.create_rectangle(
            3, 3, 717, 707, fill=ROOT_BG, outline=GOLD, width=5, tags="table"
        )
        self.table_canvas.create_text(
            360,
            42,
            text="过 三 关 刮 刮 乐",
            font=("Microsoft YaHei UI", 25, "bold"),
            fill="#FFD700",
            tags="table",
        )
        self.table_canvas.create_text(
            360,
            76,
            text="PASS THREE LEVELS · SCRATCH TICKET",
            font=("Arial", 11, "bold"),
            fill=TEXT,
            tags="table",
        )

        back_button = tk.Button(
            self.table_canvas,
            text="← 返回刮刮乐",
            command=self.on_close,
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=TABLE_INNER,
            fg=TEXT,
            activebackground=HEADER_BG,
            activeforeground=TITLE_FG,
            relief=tk.RAISED,
            bd=2,
            cursor="hand2",
            padx=12,
            pady=7,
        )
        self.table_canvas.create_window(20, 20, anchor="nw", window=back_button)

        self.table_canvas.bind("<Button-1>", self._start_scratch)
        self.table_canvas.bind("<B1-Motion>", self._scratch_motion)
        self.table_canvas.bind("<ButtonRelease-1>", self._stop_scratch)

        right_panel = tk.Frame(main_frame, bg=ROOT_BG, width=390)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right_panel.pack_propagate(False)

        info_body = self._panel_card(right_panel, "玩家信息")
        tk.Label(
            info_body,
            textvariable=self.balance_var,
            font=("Arial", 16, "bold"),
            bg=PANEL_BG,
            fg="black",
        ).pack(side=tk.LEFT)
        tk.Label(
            info_body,
            textvariable=self.stage_var,
            font=("Microsoft YaHei UI", 15, "bold"),
            bg=PANEL_BG,
            fg=ACCENT_FG,
        ).pack(side=tk.RIGHT)

        ticket_body = self._panel_card(right_panel, "当前票券")
        tk.Label(
            ticket_body,
            textvariable=self.serial_var,
            font=("Consolas", 11, "bold"),
            bg=PANEL_BG,
            fg=TITLE_FG,
        ).pack(anchor="w")
        tk.Label(
            ticket_body,
            text=f"票价: ${self.TICKET_COST:.2f}",
            font=("Arial", 12),
            bg=PANEL_BG,
            fg="black",
        ).pack(anchor="w", pady=(4, 0))
        tk.Label(
            ticket_body,
            text="目标: 指定横线、竖线或 159 斜线三个图案相同",
            font=("Microsoft YaHei UI", 11, "bold"),
            bg=PANEL_BG,
            fg=ACCENT_FG,
        ).pack(anchor="w", pady=(5, 0))
        tk.Label(
            ticket_body,
            textvariable=self.opened_var,
            font=("Microsoft YaHei UI", 11, "bold"),
            bg=PANEL_BG,
            fg=TITLE_FG,
        ).pack(anchor="w", pady=(3, 0))

        progress_body = self._panel_card(right_panel, "刮卡进度")
        self.progress_canvas = self._progress_row(
            progress_body, "整张票券", self.progress_var
        )

        action_body = self._panel_card(right_panel, "操作")
        tk.Label(
            action_body,
            textvariable=self.status_var,
            font=("Microsoft YaHei UI", 11, "bold"),
            bg=PANEL_BG,
            fg=TITLE_FG,
            justify=tk.LEFT,
            wraplength=335,
            height=3,
        ).pack(fill=tk.X, pady=(0, 6))

        button_row = tk.Frame(action_body, bg=PANEL_BG)
        button_row.pack(fill=tk.X)
        button_row.grid_columnconfigure(0, weight=1, uniform="action_buttons")
        button_row.grid_columnconfigure(1, weight=1, uniform="action_buttons")
        self.buy_button = tk.Button(
            button_row,
            text="购买票券（-1 元）",
            command=self.buy_ticket,
            font=("Microsoft YaHei UI", 11, "bold"),
            bg="#4CAF50",
            fg="white",
            activebackground="#66BB6A",
            activeforeground="white",
            relief=tk.RAISED,
            bd=2,
            cursor="hand2",
            padx=8,
            pady=9,
        )
        self.buy_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.reveal_all_button = tk.Button(
            button_row,
            text="刮开全部",
            command=self.reveal_all,
            font=("Microsoft YaHei UI", 11, "bold"),
            bg="#4B8BBE",
            fg="white",
            activebackground="#6AA0CA",
            activeforeground="white",
            relief=tk.RAISED,
            bd=2,
            cursor="hand2",
            padx=8,
            pady=9,
            state=tk.DISABLED,
        )
        self.reveal_all_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        tk.Label(
            action_body,
            textvariable=self.last_win_var,
            font=("Arial", 12),
            bg=PANEL_BG,
            fg="black",
        ).pack(anchor="w", pady=(8, 0))

        rules_body = self._panel_card(right_panel, "玩法说明")
        rules = (
            "1. 刮开全部九个格子。\n"
            "2. 仅票面标示的三横、三竖和 159 斜线有效。\n"
            "3. 同一有效线上三个图案相同即中奖；奖金由连线位置决定。"
        )
        tk.Label(
            rules_body,
            text=rules,
            font=("Microsoft YaHei UI", 10),
            bg=PANEL_BG,
            fg=TITLE_FG,
            justify=tk.LEFT,
            wraplength=340,
        ).pack(anchor="w")

    def _panel_card(self, master: tk.Misc, title: str) -> tk.Frame:
        card = tk.Frame(master, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        card.pack(fill=tk.X, pady=3)
        header = tk.Frame(card, bg=HEADER_BG)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text=title,
            font=("Microsoft YaHei UI", 12, "bold"),
            bg=HEADER_BG,
            fg=TITLE_FG,
        ).pack(pady=4)
        body = tk.Frame(card, bg=PANEL_BG)
        body.pack(fill=tk.X, padx=10, pady=8)
        return body

    def _progress_row(
        self, master: tk.Misc, label_text: str, value_var: tk.StringVar
    ) -> tk.Canvas:
        row = tk.Frame(master, bg=PANEL_BG)
        row.pack(fill=tk.X, pady=4)
        tk.Label(
            row,
            text=label_text,
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=PANEL_BG,
            fg=TITLE_FG,
            width=9,
            anchor="w",
        ).pack(side=tk.LEFT)
        bar = tk.Canvas(
            row,
            width=210,
            height=16,
            bg="#DDD4BF",
            highlightthickness=1,
            highlightbackground="#7D6A3D",
        )
        bar.pack(side=tk.LEFT, padx=5)
        bar.create_rectangle(0, 0, 0, 16, fill=GOLD, outline="", tags="fill")
        tk.Label(
            row,
            textvariable=value_var,
            font=("Arial", 10, "bold"),
            bg=PANEL_BG,
            fg=ACCENT_FG,
            width=4,
            anchor="e",
        ).pack(side=tk.RIGHT)
        return bar

    # =====================================================
    # 票券绘制
    # =====================================================
    def _draw_empty_ticket(self) -> None:
        self.table_canvas.delete("ticket")
        self._draw_ticket_base()
        self.table_canvas.create_text(
            360,
            345,
            text="请先在右侧购买票券",
            font=("Microsoft YaHei UI", 22, "bold"),
            fill=TITLE_FG,
            tags="ticket",
        )
        self.table_canvas.create_text(
            360,
            395,
            text="购买后按住鼠标，在九个银色区域来回刮动",
            font=("Microsoft YaHei UI", 12),
            fill="#6D5B33",
            tags="ticket",
        )

    def _draw_ticket_base(self) -> None:
        c = self.table_canvas
        c.create_rectangle(
            67, 105, 653, 622, fill="#102F27", outline="#0C211C", width=2, tags="ticket"
        )
        c.create_rectangle(
            77, 115, 643, 612, fill=PANEL_BG, outline=GOLD, width=4, tags="ticket"
        )
        c.create_rectangle(
            77, 115, 643, 180, fill=HEADER_BG, outline=GOLD, width=2, tags="ticket"
        )
        c.create_text(
            106,
            147,
            text="P3",
            font=("Georgia", 24, "bold"),
            fill=TITLE_FG,
            tags="ticket",
        )
        c.create_text(
            360,
            143,
            text="过三关刮刮乐",
            font=("Microsoft YaHei UI", 24, "bold"),
            fill=TITLE_FG,
            tags="ticket",
        )
        c.create_text(
            360,
            168,
            text="MATCH THREE SYMBOLS IN A LINE",
            font=("Arial", 9, "bold"),
            fill="#6D4D19",
            tags="ticket",
        )
        c.create_text(
            605,
            145,
            text="$1",
            font=("Arial", 23, "bold"),
            fill=TITLE_FG,
            tags="ticket",
        )
        for y in (205, 218, 596):
            c.create_line(97, y, 623, y, fill="#D8C99F", dash=(4, 4), tags="ticket")

    def _draw_live_ticket(self) -> None:
        self.table_canvas.delete("ticket")
        self._draw_ticket_base()
        c = self.table_canvas
        c.create_text(
            100,
            205,
            text=f"SERIAL  {self.serial_var.get().replace('票号: ', '')}",
            font=("Consolas", 11, "bold"),
            fill=TITLE_FG,
            anchor="w",
            tags="ticket",
        )
        c.create_text(
            620,
            205,
            text="刮开全部 · 连成一线",
            font=("Microsoft YaHei UI", 10, "bold"),
            fill=ACCENT_FG,
            anchor="e",
            tags="ticket",
        )

        self.scratch_areas.clear()
        if self.card is None:
            return

        for row in range(3):
            for col in range(3):
                index = row * 3 + col
                x1 = self.GRID_X + col * (self.CELL_WIDTH + self.CELL_GAP)
                y1 = self.GRID_Y + row * (self.CELL_HEIGHT + self.CELL_GAP)
                x2 = x1 + self.CELL_WIDTH
                y2 = y1 + self.CELL_HEIGHT
                rect = (x1, y1, x2, y2)
                symbol = self.card[row][col]
                c.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill="#FFFDF4",
                    outline="#7A6737",
                    width=3,
                    tags="ticket",
                )

                # 图案只需位于格子内，不绑定固定的绝对 x/y 坐标。
                symbol_x = random.randint(x1 + 34, x2 - 34)
                symbol_y = random.randint(y1 + 28, y2 - 28)
                c.create_text(
                    symbol_x,
                    symbol_y,
                    text=symbol,
                    font=("Segoe UI Emoji", 31),
                    fill=TITLE_FG,
                    tags=("ticket", f"result_{index}"),
                )
                self.scratch_areas[index] = {
                    "rect": rect,
                    "items": set(),
                    "total": 0,
                }
                self._create_coating(index)

        self._draw_prize_guides()
        c.create_text(
            360,
            580,
            text="三个相同图案连成票面指定线路即可中奖",
            font=("Microsoft YaHei UI", 10, "bold"),
            fill="#6D5B33",
            tags="ticket",
        )

    def _draw_prize_guides(self) -> None:
        """在三行右侧、三列下方和 159 斜线末端显示固定奖金。"""
        c = self.table_canvas
        grid_right = self.GRID_X + 3 * self.CELL_WIDTH + 2 * self.CELL_GAP
        grid_bottom = self.GRID_Y + 3 * self.CELL_HEIGHT + 2 * self.CELL_GAP
        row_centers = [
            self.GRID_Y + row * (self.CELL_HEIGHT + self.CELL_GAP) + self.CELL_HEIGHT // 2
            for row in range(3)
        ]
        column_centers = [
            self.GRID_X + col * (self.CELL_WIDTH + self.CELL_GAP) + self.CELL_WIDTH // 2
            for col in range(3)
        ]

        # 三条横线的奖金显示在每行右侧。
        for y, prize in zip(row_centers, (1, 5, 20)):
            c.create_line(
                grid_right + 4,
                y,
                grid_right + 23,
                y,
                fill=ACCENT_FG,
                width=2,
                arrow=tk.LAST,
                tags="ticket",
            )
            c.create_text(
                grid_right + 29,
                y,
                text=f"${prize:,.2f}",
                font=("Arial", 10, "bold"),
                fill=TITLE_FG,
                anchor="w",
                tags="ticket",
            )

        # 三条竖线的奖金显示在每列下方。
        for x, prize in zip(column_centers, (2, 40, 100)):
            c.create_line(
                x,
                grid_bottom + 3,
                x,
                grid_bottom + 18,
                fill=ACCENT_FG,
                width=2,
                arrow=tk.LAST,
                tags="ticket",
            )
            c.create_text(
                x,
                grid_bottom + 34,
                text=f"${prize:,.2f}",
                font=("Arial", 10, "bold"),
                fill=TITLE_FG,
                anchor="n",
                tags="ticket",
            )

        # 仅左上到右下的 159 斜线有效；357 反斜线不设奖金。
        c.create_line(
            grid_right + 3,
            grid_bottom + 3,
            grid_right + 28,
            grid_bottom + 28,
            fill=ACCENT_FG,
            width=2,
            arrow=tk.LAST,
            tags="ticket",
        )
        c.create_text(
            grid_right + 34,
            grid_bottom + 34,
            text="$10,000.00",
            font=("Arial", 10, "bold"),
            fill=TITLE_FG,
            anchor="w",
            tags="ticket",
        )

    def _create_coating(self, index: int) -> None:
        area_data = self.scratch_areas[index]
        x1, y1, x2, y2 = area_data["rect"]  # type: ignore[misc]
        items: Set[int] = set()
        tile = 9
        for row, y in enumerate(range(y1, y2, tile)):
            for col, x in enumerate(range(x1, x2, tile)):
                shade = random.choice(SILVER_PALETTE)
                item = self.table_canvas.create_rectangle(
                    x,
                    y,
                    min(x + tile + 1, x2),
                    min(y + tile + 1, y2),
                    fill=shade,
                    outline=shade,
                    tags=("ticket", f"coat_{index}"),
                )
                items.add(item)
                if (row + col) % 7 == 0:
                    self.table_canvas.create_line(
                        x + 1,
                        y + tile - 1,
                        min(x + tile - 1, x2),
                        y + 1,
                        fill="#ECEEEE",
                        width=1,
                        tags=("ticket", f"coat_{index}", f"shine_{index}"),
                    )
        area_data["items"] = items
        area_data["total"] = len(items)
        self.table_canvas.create_text(
            (x1 + x2) // 2,
            (y1 + y2) // 2,
            text="刮 开",
            font=("Microsoft YaHei UI", 13, "bold"),
            fill="#4F5553",
            tags=("ticket", f"coat_{index}"),
        )

    # =====================================================
    # 游戏流程
    # =====================================================
    def buy_ticket(self) -> None:
        if self.ticket_active:
            return
        if self.balance < self.TICKET_COST:
            messagebox.showerror("余额不足", "余额不足以购买过三关票券。", parent=self)
            return

        self.balance -= self.TICKET_COST
        self.card = generate_scratch_card()
        serial = "".join(str(random.randrange(10)) for _ in range(12))
        self.serial_var.set(f"票号: {serial}")
        self.ticket_active = True
        self.prize_paid = False
        self.revealed.clear()
        self._last_scratch_xy = None

        self.stage_var.set("刮卡中")
        self.status_var.set("请刮开九个银色格子；全部刮开后自动结算。")
        self.opened_var.set("已刮开: 0 / 9")
        self.last_win_var.set("本局赢得: $0.00")
        self.buy_button.config(state=tk.DISABLED, text="票券进行中")
        self.reveal_all_button.config(state=tk.NORMAL)
        self._set_progress(0.0)
        self._draw_live_ticket()
        self._refresh_balance()
        self._sync_balance()

    def reveal_all(self) -> None:
        if not self.ticket_active:
            return
        self.reveal_all_button.config(state=tk.DISABLED)
        self._auto_reveal_next(0)

    def _auto_reveal_next(self, index: int) -> None:
        while index < 9:
            if index not in self.revealed:
                self._complete_cell(index)
                if self.ticket_active:
                    self.auto_reveal_job = self.after(120, self._auto_reveal_next, index + 1)
                return
            index += 1
        self.auto_reveal_job = None

    def _complete_cell(self, index: int) -> None:
        if index in self.revealed or index not in self.scratch_areas:
            return
        self._clear_coating(index)
        self.revealed.add(index)

        # 与 Golf 刮刮乐一致：中奖线上的三个图案全部刮开后，
        # 立即把三个格子的外框标示为绿色。
        self._highlight_revealed_wins()

        ratio = len(self.revealed) / 9
        self._set_progress(ratio)
        self.opened_var.set(f"已刮开: {len(self.revealed)} / 9")
        if len(self.revealed) == 9:
            self._finish_ticket()

    def _highlight_revealed_wins(self) -> None:
        """为已经完全刮开的有效中奖线绘制绿色格子外框。"""
        self.table_canvas.delete("winner_highlight")
        if self.card is None:
            return

        winning_line_names = {
            line_name for line_name, _prize, _symbol in check_for_wins(self.card)
        }
        for line_name, indices, _prize in WIN_LINES:
            if line_name not in winning_line_names:
                continue
            if not set(indices).issubset(self.revealed):
                continue

            for index in indices:
                area_data = self.scratch_areas.get(index)
                if area_data is None:
                    continue
                x1, y1, x2, y2 = area_data["rect"]  # type: ignore[misc]
                self.table_canvas.create_rectangle(
                    x1 + 2,
                    y1 + 2,
                    x2 - 2,
                    y2 - 2,
                    outline=SUCCESS,
                    width=5,
                    tags=("ticket", "winner_highlight"),
                )

    def _finish_ticket(self) -> None:
        if not self.ticket_active or self.card is None:
            return

        wins = check_for_wins(self.card)
        self._highlight_revealed_wins()
        total_prize = sum(prize for _line_name, prize, _symbol in wins)
        if total_prize > 0 and not self.prize_paid:
            self.balance += total_prize
            self.prize_paid = True
            line_details = "、".join(
                f"{line_name}=${prize:,.2f}" for line_name, prize, _symbol in wins
            )
            self.last_win_var.set(f"本局赢得: ${total_prize:,.2f}")
            self.status_var.set(f"已派彩 恭喜！")
        else:
            self.last_win_var.set("本局赢得: $0.00")
            self.status_var.set("本张未中奖，再试一次吧。")

        self.ticket_active = False
        self.stage_var.set("已结算")
        self.buy_button.config(state=tk.NORMAL, text="再买一张（-1 元）")
        self.reveal_all_button.config(state=tk.DISABLED)
        self._refresh_balance()
        self._sync_balance()

    # =====================================================
    # 鼠标刮除
    # =====================================================
    def _start_scratch(self, event: tk.Event) -> None:
        self._last_scratch_xy = (event.x, event.y)
        self._scratch_at(event.x, event.y)

    def _scratch_motion(self, event: tk.Event) -> None:
        if self._last_scratch_xy is None:
            self._last_scratch_xy = (event.x, event.y)
            self._scratch_at(event.x, event.y)
            return

        old_x, old_y = self._last_scratch_xy
        dx = event.x - old_x
        dy = event.y - old_y
        distance = max(abs(dx), abs(dy))
        steps = max(1, distance // 8)
        for step in range(1, steps + 1):
            x = int(old_x + dx * step / steps)
            y = int(old_y + dy * step / steps)
            self._scratch_at(x, y)
        self._last_scratch_xy = (event.x, event.y)

    def _stop_scratch(self, _event: tk.Event) -> None:
        self._last_scratch_xy = None

    def _scratch_at(self, x: int, y: int) -> None:
        if not self.ticket_active:
            return
        index = self._cell_at(x, y)
        if index is None or index in self.revealed:
            return

        area_data = self.scratch_areas[index]
        coating_items: Set[int] = area_data["items"]  # type: ignore[assignment]
        radius = self.BRUSH_RADIUS
        overlapping = self.table_canvas.find_overlapping(
            x - radius, y - radius, x + radius, y + radius
        )
        removed = False
        for item in overlapping:
            tags = self.table_canvas.gettags(item)
            if item in coating_items:
                self.table_canvas.delete(item)
                coating_items.discard(item)
                removed = True
            elif f"coat_{index}" in tags:
                self.table_canvas.delete(item)

        if not removed:
            return

        self._emit_dust(x, y)
        total = int(area_data["total"])
        ratio = 1.0 - (len(coating_items) / total if total else 0.0)
        if ratio >= self.REVEAL_THRESHOLD:
            self._complete_cell(index)

    def _cell_at(self, x: int, y: int) -> Optional[int]:
        for index, area_data in self.scratch_areas.items():
            x1, y1, x2, y2 = area_data["rect"]  # type: ignore[misc]
            if x1 <= x <= x2 and y1 <= y <= y2:
                return index
        return None

    def _emit_dust(self, x: int, y: int) -> None:
        dust_ids = []
        for _ in range(3):
            dx = random.randint(-18, 18)
            dy = random.randint(-18, 18)
            size = random.randint(2, 4)
            dust_ids.append(
                self.table_canvas.create_oval(
                    x + dx,
                    y + dy,
                    x + dx + size,
                    y + dy + size,
                    fill=random.choice(SILVER_PALETTE),
                    outline="",
                    tags="dust",
                )
            )

        def remove_dust(ids=dust_ids) -> None:
            try:
                for item in ids:
                    self.table_canvas.delete(item)
            except tk.TclError:
                pass

        self.after(140, remove_dust)

    def _clear_coating(self, index: int) -> None:
        self.table_canvas.delete(f"coat_{index}")
        area_data = self.scratch_areas[index]
        coating_items: Set[int] = area_data["items"]  # type: ignore[assignment]
        coating_items.clear()

    # =====================================================
    # 状态辅助
    # =====================================================
    def _set_progress(self, ratio: float) -> None:
        ratio = max(0.0, min(1.0, ratio))
        self.progress_canvas.coords("fill", 0, 0, int(210 * ratio), 16)
        self.progress_var.set(f"{int(round(ratio * 100)):d}%")

    def _refresh_balance(self) -> None:
        self.balance_var.set(f"余额: ${self.balance:,.2f}")

    def _sync_balance(self) -> None:
        if self.username not in ("demo_player", "Guest"):
            update_balance_in_json(self.username, self.balance)
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))

    def on_close(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self.auto_reveal_job is not None:
            try:
                self.after_cancel(self.auto_reveal_job)
            except tk.TclError:
                pass
            self.auto_reveal_job = None
        self._sync_balance()
        if callable(self.on_back):
            self.on_back(float(self.balance))


def main(
    initial_balance: float = 100,
    username: str = "demo_player",
    *,
    parent: Optional[tk.Misc] = None,
    balance: Optional[float] = None,
    user: Optional[str] = None,
    on_back: Optional[Callable[[float], None]] = None,
    on_balance_change: Optional[Callable[[float], None]] = None,
):
    """创建可嵌入页面；只有未传 parent 时才创建独立 Tk 窗口。"""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return PassThreeLevelsGame(
            parent,
            actual_balance,
            actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("过三关刮刮乐")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = PassThreeLevelsGame(root, actual_balance, actual_user)
    page.pack(fill="both", expand=True)
    page.on_back = lambda _balance: root.destroy()
    root.protocol("WM_DELETE_WINDOW", page.on_close)
    root.mainloop()
    return page.balance


if __name__ == "__main__":
    main()