import json
import os
import random
import tkinter as tk
from collections import Counter
from tkinter import messagebox
from typing import Callable, Dict, List, Optional, Set, Tuple


# =========================================================
# 与 Banknote_Detection_gui 一致的视觉规范
# =========================================================
ROOT_BG = "#1B3D31"
TABLE_INNER = "#2A4A3C"
TEXT = "#FFFFFF"
GOLD = "#D4AF37"
WIN_GOLD = "#F2C94C"
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
        "saving_data.json",
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
WEIGHTS = {
    0: 480,
    5: 230,
    10: 230,
    20: 70,
    25: 60,
    40: 28,
    50: 17,
    100: 15,
    1000: 7,
    50000: 3,
}
MONEY_EMOJIS = ["🏦", "💲", "🧧", "💰", "💵", "🪙"]
OBJECT_EMOJIS = ["👛", "🤑", "💳", "🫰", "💎", "📒"]
EXTRA_CELL_WIN_PROBABILITY = 0.02
EXTRA_CELL_PRIZE = 100


def draw_amount() -> int:
    return random.choices(list(WEIGHTS), weights=WEIGHTS.values(), k=1)[0]


def draw_row(amount: int) -> Optional[int]:
    if amount == 0:
        return None
    return random.randint(1, 10)


def handle_fixed_emoji_row() -> list:
    """生成恰好包含三个相同图案的中奖行。"""
    fixed = random.choice(OBJECT_EMOJIS)
    remaining = [emoji for emoji in OBJECT_EMOJIS if emoji != fixed]
    other = random.choice(remaining)
    row = [fixed, fixed, fixed, other, random.choice(remaining)]
    random.shuffle(row)
    return row


def generate_emoji_row(row_index: int) -> list:
    """生成不可能出现三个相同图案的普通行。"""
    source = MONEY_EMOJIS if row_index % 2 else OBJECT_EMOJIS
    counts = {emoji: 0 for emoji in source}
    row = []
    while len(row) < 5:
        chosen = random.choice(source)
        if counts[chosen] < 2:
            row.append(chosen)
            counts[chosen] += 1
    return row


def handle_row_zero() -> list:
    """额外玩法：左右两格分别以 2% 概率独立出现 💵。"""
    return [
        "💵"
        if random.random() < EXTRA_CELL_WIN_PROBABILITY
        else random.choice(OBJECT_EMOJIS)
        for _ in range(2)
    ]


def format_amount(amount: int) -> str:
    return f"{amount:,.2f}" if amount < 100 else f"{amount:,}"


def generate_emoji_rows(winning_row: Optional[int], amount: int) -> list:
    rows = [handle_row_zero()]
    non_zero_prizes = [prize for prize in WEIGHTS if prize]

    for row_index in range(1, 11):
        if row_index == winning_row:
            row = handle_fixed_emoji_row()
            row.append(format_amount(amount))
        else:
            row = generate_emoji_row(row_index)
            row.append(format_amount(random.choice(non_zero_prizes)))
        rows.append(row)

    return rows


CellKey = Tuple[int, int]


class StackedScratchGame(tk.Frame):
    """11 行叠叠乐：每个图案和奖金都是独立刮开格。"""

    TICKET_COST = 5.0
    REVEAL_THRESHOLD = 0.72
    BRUSH_RADIUS = 20

    # 票面尺寸在原版本基础上放大，但主 Tk 窗口仍保持 1150x750。
    CANVAS_WIDTH = 760
    CANVAS_HEIGHT = 724

    TICKET_OUTER = (44, 98, 706, 655)
    TICKET_INNER = (54, 108, 696, 645)

    ROW_X1 = 158
    ROW_X2 = 640
    ROW_Y = 212
    ROW_HEIGHT = 31
    ROW_GAP = 3

    EMOJI_CELL_WIDTH = 68
    CELL_GAP = 4
    PRIZE_CELL_WIDTH = 172

    ROW_ZERO_SIDE_WIDTH = 120
    ROW_ZERO_CENTER_X1 = 236
    ROW_ZERO_CENTER_X2 = 512

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

        self.amount = 0
        self.extra_prize = 0
        self.winning_row: Optional[int] = None
        self.rows: list = []
        self.ticket_active = False
        self.prize_paid = False

        # revealed_cells 保存已经完成刮开的独立格子，而不是整行编号。
        self.revealed_cells: Set[CellKey] = set()
        self.winning_rows: Set[int] = set()
        self.scratch_areas: Dict[CellKey, Dict[str, object]] = {}
        self.row_visuals: Dict[int, Dict[str, object]] = {}
        self.row_cell_keys: Dict[int, List[CellKey]] = {}
        self.cell_order: List[CellKey] = []

        self.auto_reveal_job: Optional[str] = None
        self._last_scratch_xy: Optional[Tuple[int, int]] = None
        self._closing = False

        self.balance_var = tk.StringVar()
        self.stage_var = tk.StringVar(value="待购票")
        self.status_var = tk.StringVar(value="购买票券后，按住鼠标逐格刮开银色涂层。")
        self.serial_var = tk.StringVar(value="票号: ------------")
        self.progress_var = tk.StringVar(value="0%")
        self.opened_var = tk.StringVar(value="已刮开: 0 / 62 格")
        self.result_var = tk.StringVar(value="票券结果: 未揭晓")
        self.last_win_var = tk.StringVar(value="本局赢得: $0.00")

        self._build_ui()
        self._refresh_balance()
        self._draw_empty_ticket()

    # =====================================================
    # UI
    # =====================================================
    def _build_ui(self) -> None:
        main_frame = tk.Frame(self, bg=ROOT_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        left_frame = tk.Frame(main_frame, bg=ROOT_BG)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.table_canvas = tk.Canvas(
            left_frame,
            width=self.CANVAS_WIDTH,
            height=self.CANVAS_HEIGHT,
            bg=ROOT_BG,
            highlightthickness=0,
            cursor="crosshair",
        )
        self.table_canvas.pack(fill=tk.BOTH, expand=True)
        self.table_canvas.create_rectangle(
            3,
            3,
            self.CANVAS_WIDTH - 3,
            self.CANVAS_HEIGHT - 3,
            fill=ROOT_BG,
            outline=GOLD,
            width=5,
            tags="table",
        )
        self.table_canvas.create_text(
            self.CANVAS_WIDTH // 2,
            40,
            text="叠 叠 乐",
            font=("Microsoft YaHei UI", 26, "bold"),
            fill="#FFD700",
            tags="table",
        )
        self.table_canvas.create_text(
            self.CANVAS_WIDTH // 2,
            74,
            text="STACKED SYMBOLS · SCRATCH TICKET",
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
        self.table_canvas.create_window(18, 18, anchor="nw", window=back_button)

        self.table_canvas.bind("<Button-1>", self._start_scratch)
        self.table_canvas.bind("<B1-Motion>", self._scratch_motion)
        self.table_canvas.bind("<ButtonRelease-1>", self._stop_scratch)

        # 缩窄右侧信息栏，为左侧游戏票面留出更多空间；总窗口尺寸不变。
        right_panel = tk.Frame(main_frame, bg=ROOT_BG, width=360)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        right_panel.pack_propagate(False)

        info_body = self._panel_card(right_panel, "玩家信息")
        tk.Label(
            info_body,
            textvariable=self.balance_var,
            font=("Arial", 15, "bold"),
            bg=PANEL_BG,
            fg="black",
        ).pack(side=tk.LEFT)
        tk.Label(
            info_body,
            textvariable=self.stage_var,
            font=("Microsoft YaHei UI", 14, "bold"),
            bg=PANEL_BG,
            fg=ACCENT_FG,
        ).pack(side=tk.RIGHT)

        ticket_body = self._panel_card(right_panel, "当前票券")
        tk.Label(
            ticket_body,
            textvariable=self.serial_var,
            font=("Consolas", 10, "bold"),
            bg=PANEL_BG,
            fg=TITLE_FG,
        ).pack(anchor="w")
        tk.Label(
            ticket_body,
            text=f"票价: ${self.TICKET_COST:.2f}    最高奖金: $50,000",
            font=("Arial", 10),
            bg=PANEL_BG,
            fg="black",
        ).pack(anchor="w", pady=(4, 0))
        self.result_label = tk.Label(
            ticket_body,
            textvariable=self.result_var,
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=PANEL_BG,
            fg=ACCENT_FG,
        )
        self.result_label.pack(anchor="w", pady=(5, 0))
        tk.Label(
            ticket_body,
            textvariable=self.opened_var,
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=PANEL_BG,
            fg=TITLE_FG,
        ).pack(anchor="w", pady=(3, 0))

        progress_body = self._panel_card(right_panel, "刮卡进度")
        self.progress_canvas = self._progress_row(
            progress_body, "独立格子", self.progress_var
        )

        action_body = self._panel_card(right_panel, "操作")
        tk.Label(
            action_body,
            textvariable=self.status_var,
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=PANEL_BG,
            fg=TITLE_FG,
            justify=tk.LEFT,
            wraplength=310,
            height=3,
        ).pack(fill=tk.X, pady=(0, 6))

        button_row = tk.Frame(action_body, bg=PANEL_BG)
        button_row.pack(fill=tk.X)
        button_row.grid_columnconfigure(0, weight=1, uniform="action_buttons")
        button_row.grid_columnconfigure(1, weight=1, uniform="action_buttons")

        self.buy_button = tk.Button(
            button_row,
            text="购买票券（-5 元）",
            command=self.buy_ticket,
            font=("Microsoft YaHei UI", 10, "bold"),
            bg="#4CAF50",
            fg="white",
            activebackground="#66BB6A",
            activeforeground="white",
            relief=tk.RAISED,
            bd=2,
            cursor="hand2",
            padx=6,
            pady=8,
        )
        self.buy_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.reveal_all_button = tk.Button(
            button_row,
            text="刮开全部",
            command=self.reveal_all,
            font=("Microsoft YaHei UI", 10, "bold"),
            bg="#4B8BBE",
            fg="white",
            activebackground="#6AA0CA",
            activeforeground="white",
            relief=tk.RAISED,
            bd=2,
            cursor="hand2",
            padx=6,
            pady=8,
            state=tk.DISABLED,
        )
        self.reveal_all_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        tk.Label(
            action_body,
            textvariable=self.last_win_var,
            font=("Arial", 11),
            bg=PANEL_BG,
            fg="black",
        ).pack(anchor="w", pady=(7, 0))

        rules_body = self._panel_card(right_panel, "玩法说明")
        rules = (
            "1. 第 1-10 行每个图案和奖金均为独立。\n"
            "2. 刮出三个相同图案时，该行变金色，其余行自动揭开。\n"
            "3. 额外玩法每格独立，出现 💵，就赢 $100。"
        )
        tk.Label(
            rules_body,
            text=rules,
            font=("Microsoft YaHei UI", 9),
            bg=PANEL_BG,
            fg=TITLE_FG,
            justify=tk.LEFT,
            wraplength=315,
        ).pack(anchor="w")

    def _panel_card(self, master: tk.Misc, title: str) -> tk.Frame:
        card = tk.Frame(master, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        card.pack(fill=tk.X, pady=3)
        header = tk.Frame(card, bg=HEADER_BG)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text=title,
            font=("Microsoft YaHei UI", 11, "bold"),
            bg=HEADER_BG,
            fg=TITLE_FG,
        ).pack(pady=3)
        body = tk.Frame(card, bg=PANEL_BG)
        body.pack(fill=tk.X, padx=9, pady=7)
        return body

    def _progress_row(
        self, master: tk.Misc, label_text: str, value_var: tk.StringVar
    ) -> tk.Canvas:
        row = tk.Frame(master, bg=PANEL_BG)
        row.pack(fill=tk.X, pady=3)
        tk.Label(
            row,
            text=label_text,
            font=("Microsoft YaHei UI", 9, "bold"),
            bg=PANEL_BG,
            fg=TITLE_FG,
            width=8,
            anchor="w",
        ).pack(side=tk.LEFT)
        bar = tk.Canvas(
            row,
            width=185,
            height=16,
            bg="#DDD4BF",
            highlightthickness=1,
            highlightbackground="#7D6A3D",
        )
        bar.pack(side=tk.LEFT, padx=4)
        bar.create_rectangle(0, 0, 0, 16, fill=GOLD, outline="", tags="fill")
        tk.Label(
            row,
            textvariable=value_var,
            font=("Arial", 9, "bold"),
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
            self.CANVAS_WIDTH // 2,
            350,
            text="请先在右侧购买票券",
            font=("Microsoft YaHei UI", 23, "bold"),
            fill=TITLE_FG,
            tags="ticket",
        )
        self.table_canvas.create_text(
            self.CANVAS_WIDTH // 2,
            402,
            text="购买后按住鼠标，逐格刮开银色区域",
            font=("Microsoft YaHei UI", 13),
            fill="#6D5B33",
            tags="ticket",
        )

    def _draw_ticket_base(self) -> None:
        c = self.table_canvas
        ox1, oy1, ox2, oy2 = self.TICKET_OUTER
        ix1, iy1, ix2, iy2 = self.TICKET_INNER

        c.create_rectangle(
            ox1,
            oy1,
            ox2,
            oy2,
            fill="#102F27",
            outline="#0C211C",
            width=2,
            tags="ticket",
        )
        c.create_rectangle(
            ix1,
            iy1,
            ix2,
            iy2,
            fill=PANEL_BG,
            outline=GOLD,
            width=4,
            tags="ticket",
        )
        c.create_rectangle(
            ix1,
            iy1,
            ix2,
            175,
            fill=HEADER_BG,
            outline=GOLD,
            width=2,
            tags="ticket",
        )
        c.create_text(
            89,
            141,
            text="SS",
            font=("Georgia", 25, "bold"),
            fill=TITLE_FG,
            tags="ticket",
        )
        c.create_text(
            375,
            138,
            text="叠叠乐",
            font=("Microsoft YaHei UI", 25, "bold"),
            fill=TITLE_FG,
            tags="ticket",
        )
        c.create_text(
            375,
            163,
            text="SCRATCH THREE MATCHING SYMBOLS",
            font=("Arial", 9, "bold"),
            fill="#6D4D19",
            tags="ticket",
        )
        c.create_text(
            659,
            141,
            text="$5",
            font=("Arial", 24, "bold"),
            fill=TITLE_FG,
            tags="ticket",
        )
        for y in (199, 621):
            c.create_line(74, y, 676, y, fill="#D8C99F", dash=(4, 4), tags="ticket")

    def _draw_live_ticket(self) -> None:
        self.table_canvas.delete("ticket")
        self._draw_ticket_base()
        c = self.table_canvas

        c.create_text(
            76,
            193,
            text=f"SERIAL  {self.serial_var.get().replace('票号: ', '')}",
            font=("Consolas", 10, "bold"),
            fill=TITLE_FG,
            anchor="w",
            tags="ticket",
        )
        c.create_text(
            674,
            193,
            text="每格独立刮开 · 三同图案赢行奖",
            font=("Microsoft YaHei UI", 9, "bold"),
            fill=ACCENT_FG,
            anchor="e",
            tags="ticket",
        )

        self.scratch_areas.clear()
        self.row_visuals.clear()
        self.row_cell_keys.clear()
        self.cell_order.clear()

        for row_index in range(11):
            self._draw_row(row_index)

        c.create_text(
            375,
            633,
            text="按住鼠标左键逐格刮开；全部格子完成后自动结算",
            font=("Microsoft YaHei UI", 10, "bold"),
            fill="#6D5B33",
            tags="ticket",
        )

    def _draw_row(self, row_index: int) -> None:
        c = self.table_canvas
        y1 = self.ROW_Y + row_index * (self.ROW_HEIGHT + self.ROW_GAP)
        y2 = y1 + self.ROW_HEIGHT

        strip = c.create_rectangle(
            63,
            y1,
            649,
            y2,
            fill="#F8EFCF" if row_index == 0 else "#EEE4C9",
            outline="#B6A778",
            width=1,
            tags=("ticket", f"row_strip_{row_index}"),
        )

        label = "额外玩法" if row_index == 0 else f"第 {row_index:02d} 行"
        label_item = c.create_text(
            self.ROW_X1 - 22,
            (y1 + y2) // 2,
            text=label,
            font=("Microsoft YaHei UI", 9, "bold"),
            fill=ACCENT_FG if row_index == 0 else TITLE_FG,
            anchor="e",
            tags=("ticket", f"row_label_{row_index}"),
        )

        self.row_visuals[row_index] = {
            "strip": strip,
            "label": label_item,
            "cell_bgs": [],
            "cell_texts": [],
            "center_bg": None,
            "center_text": None,
        }
        self.row_cell_keys[row_index] = []

        if row_index == 0:
            self._draw_row_zero(y1, y2)
        else:
            self._draw_normal_row(row_index, y1, y2)

    def _draw_row_zero(self, y1: int, y2: int) -> None:
        # 左右刮刮格使用完全相同的宽度
        side_width = self.ROW_ZERO_SIDE_WIDTH
        center_gap = 8

        # 左侧刮刮格
        left_x1 = self.ROW_X1
        left_x2 = left_x1 + side_width

        # 右侧刮刮格
        right_x2 = self.ROW_X2
        right_x1 = right_x2 - side_width

        left_rect = (
            left_x1,
            y1,
            left_x2,
            y2,
        )

        right_rect = (
            right_x1,
            y1,
            right_x2,
            y2,
        )

        # 中间说明区域根据左右格的位置自动计算
        center_rect = (
            left_x2 + center_gap,
            y1,
            right_x1 - center_gap,
            y2,
        )

        for cell_index, rect in enumerate((left_rect, right_rect)):
            self._create_result_cell(
                row_index=0,
                cell_index=cell_index,
                rect=rect,
                value=self.rows[0][cell_index],
                is_prize=False,
            )

        center_bg = self.table_canvas.create_rectangle(
            *center_rect,
            fill="#FFF8DD",
            outline="#7A6737",
            width=1,
            tags=("ticket", "row_zero_center"),
        )

        center_text = self.table_canvas.create_text(
            (center_rect[0] + center_rect[2]) // 2,
            (center_rect[1] + center_rect[3]) // 2,
            text="开中💵立刻赢$100",
            font=("Microsoft YaHei UI", 12, "bold"),
            fill=ACCENT_FG,
            tags=("ticket", "row_zero_center"),
        )

        self.row_visuals[0]["center_bg"] = center_bg
        self.row_visuals[0]["center_text"] = center_text

    def _draw_normal_row(self, row_index: int, y1: int, y2: int) -> None:
        current_x = self.ROW_X1

        for cell_index in range(5):
            rect = (current_x, y1, current_x + self.EMOJI_CELL_WIDTH, y2)
            self._create_result_cell(
                row_index=row_index,
                cell_index=cell_index,
                rect=rect,
                value=self.rows[row_index][cell_index],
                is_prize=False,
            )
            current_x += self.EMOJI_CELL_WIDTH + self.CELL_GAP

        prize_rect = (current_x, y1, self.ROW_X2, y2)
        self._create_result_cell(
            row_index=row_index,
            cell_index=5,
            rect=prize_rect,
            value=f"奖金  ${self.rows[row_index][5]}",
            is_prize=True,
        )

    def _create_result_cell(
        self,
        row_index: int,
        cell_index: int,
        rect: Tuple[int, int, int, int],
        value: str,
        is_prize: bool,
    ) -> None:
        key = (row_index, cell_index)
        x1, y1, x2, y2 = rect

        bg_item = self.table_canvas.create_rectangle(
            *rect,
            fill="#FFFDF4",
            outline="#7A6737",
            width=1,
            tags=("ticket", f"cell_bg_{row_index}_{cell_index}"),
        )
        text_item = self.table_canvas.create_text(
            (x1 + x2) // 2,
            (y1 + y2) // 2,
            text=value,
            font=(
                "Microsoft YaHei UI" if is_prize else "Segoe UI Emoji",
                10 if is_prize else 15,
                "bold",
            ),
            fill=TITLE_FG,
            tags=("ticket", f"result_{row_index}_{cell_index}"),
        )

        self.row_visuals[row_index]["cell_bgs"].append(bg_item)  # type: ignore[union-attr]
        self.row_visuals[row_index]["cell_texts"].append(text_item)  # type: ignore[union-attr]
        self.row_cell_keys[row_index].append(key)
        self.cell_order.append(key)

        self.scratch_areas[key] = {
            "rect": rect,
            "items": set(),
            "total": 0,
            "bg": bg_item,
            "text": text_item,
        }
        self._create_coating(key, is_prize=is_prize)

    def _create_coating(self, key: CellKey, is_prize: bool) -> None:
        area_data = self.scratch_areas[key]
        x1, y1, x2, y2 = area_data["rect"]  # type: ignore[misc]
        row_index, cell_index = key
        coat_tag = self._coat_tag(key)
        items: Set[int] = set()
        tile = 8

        for tile_row, y in enumerate(range(y1 + 1, y2, tile)):
            for tile_col, x in enumerate(range(x1 + 1, x2, tile)):
                shade = random.choice(SILVER_PALETTE)
                item = self.table_canvas.create_rectangle(
                    x,
                    y,
                    min(x + tile + 1, x2 - 1),
                    min(y + tile + 1, y2 - 1),
                    fill=shade,
                    outline=shade,
                    tags=("ticket", coat_tag),
                )
                items.add(item)
                if (tile_row + tile_col) % 8 == 0:
                    self.table_canvas.create_line(
                        x + 1,
                        min(y + tile - 1, y2 - 1),
                        min(x + tile - 1, x2 - 1),
                        y + 1,
                        fill="#ECEEEE",
                        width=1,
                        tags=("ticket", coat_tag),
                    )

        area_data["items"] = items
        area_data["total"] = len(items)

        coat_text = "刮奖金" if is_prize else "刮"
        self.table_canvas.create_text(
            (x1 + x2) // 2,
            (y1 + y2) // 2,
            text=coat_text,
            font=("Microsoft YaHei UI", 9, "bold"),
            fill="#4F5553",
            tags=("ticket", coat_tag),
        )

    # =====================================================
    # 游戏流程
    # =====================================================
    def buy_ticket(self) -> None:
        if self.ticket_active:
            return
        if self.balance < self.TICKET_COST:
            messagebox.showerror("余额不足", "余额不足以购买叠叠乐票券。", parent=self)
            return

        self.balance -= self.TICKET_COST
        self.amount = draw_amount()
        self.winning_row = draw_row(self.amount)
        self.rows = generate_emoji_rows(self.winning_row, self.amount)
        self.extra_prize = self.rows[0].count("💵") * EXTRA_CELL_PRIZE

        serial = "".join(str(random.randrange(10)) for _ in range(12))
        self.serial_var.set(f"票号: {serial}")
        self.ticket_active = True
        self.prize_paid = False
        self.revealed_cells.clear()
        self.winning_rows.clear()
        self._last_scratch_xy = None

        self.stage_var.set("刮卡中")
        self.status_var.set("每个图案和奖金都是独立格，可按任意顺序刮开。")
        self.result_var.set("票券结果: 未揭晓")
        self.result_label.config(fg=ACCENT_FG)
        self.last_win_var.set("本局赢得: $0.00")
        self.buy_button.config(state=tk.DISABLED, text="票券进行中")
        self.reveal_all_button.config(state=tk.NORMAL)
        self._set_progress(0.0)
        self._draw_live_ticket()
        self._update_opened_text()
        self._refresh_balance()
        self._sync_balance()

    def reveal_all(self) -> None:
        if not self.ticket_active:
            return
        self.reveal_all_button.config(state=tk.DISABLED)
        self._auto_reveal_next(0)

    def _auto_reveal_next(self, position: int) -> None:
        while position < len(self.cell_order):
            key = self.cell_order[position]
            if key not in self.revealed_cells:
                self._complete_cell(key)
                if self.ticket_active:
                    self.auto_reveal_job = self.after(
                        65, self._auto_reveal_next, position + 1
                    )
                return
            position += 1
        self.auto_reveal_job = None

    def _complete_cell(self, key: CellKey) -> None:
        if key in self.revealed_cells or key not in self.scratch_areas:
            return

        self._clear_coating(key)
        self.revealed_cells.add(key)
        row_index, _ = key

        # 每刮开一个图案格，就立即检查当前已揭示图案是否达到三个相同。
        self._check_row_win(row_index)
        self._refresh_game_progress()

        if len(self.revealed_cells) == len(self.cell_order):
            self._finish_ticket()

    def _check_row_win(self, row_index: int) -> None:
        if row_index == 0:
            revealed_money_cells = sum(
                1
                for key in self.row_cell_keys[0]
                if key in self.revealed_cells and self.rows[0][key[1]] == "💵"
            )
            if revealed_money_cells:
                if row_index not in self.winning_rows:
                    self._activate_winning_row(0)
                else:
                    won = revealed_money_cells * EXTRA_CELL_PRIZE
                    self.status_var.set(
                        f"额外玩法已刮中 {revealed_money_cells} 个 💵，"
                        f"目前赢得 ${won:,.2f}。"
                    )
            return

        if row_index in self.winning_rows:
            return

        revealed_symbols = []
        for cell_index in range(5):
            key = (row_index, cell_index)
            if key in self.revealed_cells:
                revealed_symbols.append(self.rows[row_index][cell_index])

        counts = Counter(revealed_symbols)
        if any(count >= 3 for count in counts.values()):
            self._activate_winning_row(row_index)

    def _activate_winning_row(self, row_index: int) -> None:
        """中奖行变金色；普通中奖行触发其余普通行自动揭开。"""
        if row_index in self.winning_rows:
            return

        self.winning_rows.add(row_index)
        visuals = self.row_visuals[row_index]

        self.table_canvas.itemconfigure(
            int(visuals["strip"]), fill=WIN_GOLD, outline=GOLD, width=2
        )
        self.table_canvas.itemconfigure(
            int(visuals["label"]), fill=TITLE_FG
        )

        for bg_item in visuals["cell_bgs"]:  # type: ignore[union-attr]
            self.table_canvas.itemconfigure(
                int(bg_item), fill=WIN_GOLD, outline="#8C6500", width=2
            )

        center_bg = visuals.get("center_bg")
        center_text = visuals.get("center_text")
        if center_bg is not None:
            self.table_canvas.itemconfigure(
                int(center_bg), fill=WIN_GOLD, outline="#8C6500", width=2
            )
        if center_text is not None:
            self.table_canvas.itemconfigure(int(center_text), fill=TITLE_FG)

        # 未刮开的中奖行格子保留可刮状态，但银层同步改为金色。
        for key in self.row_cell_keys[row_index]:
            if key not in self.revealed_cells:
                self._goldenize_coating(key)

        if row_index == 0:
            revealed_money_cells = sum(
                1
                for key in self.row_cell_keys[0]
                if key in self.revealed_cells and self.rows[0][key[1]] == "💵"
            )
            won = revealed_money_cells * EXTRA_CELL_PRIZE
            self.status_var.set(
                f"额外玩法刮中 💵，该行已变成金色！目前赢得 ${won:,.2f}。"
            )
            return

        self._reveal_other_normal_rows(row_index)
        self.status_var.set(
            f"第 {row_index:02d} 行刮出第三个相同图案！"
        )

    def _goldenize_coating(self, key: CellKey) -> None:
        """把尚未刮开的银层改成金色，同时保留可刮功能。"""
        coat_tag = self._coat_tag(key)
        for item in self.table_canvas.find_withtag(coat_tag):
            item_type = self.table_canvas.type(item)
            if item_type == "rectangle":
                self.table_canvas.itemconfigure(
                    item, fill=WIN_GOLD, outline=WIN_GOLD
                )
            elif item_type == "line":
                self.table_canvas.itemconfigure(item, fill="#FFE78A")
            elif item_type == "text":
                self.table_canvas.itemconfigure(item, fill=TITLE_FG)

    def _reveal_other_normal_rows(self, winning_row: int) -> None:
        """揭开除中奖行和额外玩法行以外的所有普通格子。"""
        for key in self.cell_order:
            row_index, _ = key
            if row_index in (0, winning_row) or key in self.revealed_cells:
                continue
            self._clear_coating(key)
            self.revealed_cells.add(key)

    def _finish_ticket(self) -> None:
        if not self.ticket_active:
            return

        total_prize = self.amount + self.extra_prize

        if total_prize > 0 and not self.prize_paid:
            self.balance += total_prize
            self.prize_paid = True
            self.result_var.set(f"票券结果: 中奖 ${total_prize:,.2f}")
            self.result_label.config(fg=SUCCESS)
            self.last_win_var.set(f"本局赢得: ${total_prize:,.2f}")

            self.status_var.set(
                f"恭喜！本张已派彩 ${total_prize:,.2f}。"
            )
        else:
            self.result_var.set("票券结果: 未中奖")
            self.result_label.config(fg=DANGER)
            self.last_win_var.set("本局赢得: $0.00")
            self.status_var.set("本张没有中奖，再试一次吧。")

        self.ticket_active = False
        self.stage_var.set("已结算")
        self.buy_button.config(state=tk.NORMAL, text="再买一张（-5 元）")
        self.reveal_all_button.config(state=tk.DISABLED)
        self.auto_reveal_job = None
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
        steps = max(1, distance // 7)

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

        key = self._cell_at(x, y)
        if key is None or key in self.revealed_cells:
            return

        area_data = self.scratch_areas[key]
        coating_items: Set[int] = area_data["items"]  # type: ignore[assignment]
        radius = self.BRUSH_RADIUS
        overlapping = self.table_canvas.find_overlapping(
            x - radius, y - radius, x + radius, y + radius
        )

        removed = False
        coat_tag = self._coat_tag(key)
        for item in overlapping:
            tags = self.table_canvas.gettags(item)
            if item in coating_items:
                self.table_canvas.delete(item)
                coating_items.discard(item)
                removed = True
            elif coat_tag in tags:
                self.table_canvas.delete(item)

        if not removed:
            return

        self._emit_dust(x, y)
        total = int(area_data["total"])
        ratio = 1.0 - (len(coating_items) / total if total else 0.0)
        if ratio >= self.REVEAL_THRESHOLD:
            self._complete_cell(key)

    def _cell_at(self, x: int, y: int) -> Optional[CellKey]:
        for key, area_data in self.scratch_areas.items():
            x1, y1, x2, y2 = area_data["rect"]  # type: ignore[misc]
            if x1 <= x <= x2 and y1 <= y <= y2:
                return key
        return None

    def _emit_dust(self, x: int, y: int) -> None:
        dust_ids = []
        for _ in range(3):
            dx = random.randint(-15, 15)
            dy = random.randint(-12, 12)
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

    def _coat_tag(self, key: CellKey) -> str:
        return f"coat_{key[0]}_{key[1]}"

    def _clear_coating(self, key: CellKey) -> None:
        if key not in self.scratch_areas:
            return
        self.table_canvas.delete(self._coat_tag(key))
        coating_items: Set[int] = self.scratch_areas[key]["items"]  # type: ignore[assignment]
        coating_items.clear()

    # =====================================================
    # 状态辅助
    # =====================================================
    def _refresh_game_progress(self) -> None:
        total = len(self.cell_order)
        opened = len(self.revealed_cells)
        ratio = opened / total if total else 0.0
        self._set_progress(ratio)
        self._update_opened_text()

    def _update_opened_text(self) -> None:
        total = len(self.cell_order) if self.cell_order else 62
        self.opened_var.set(f"已刮开: {len(self.revealed_cells)} / {total} 格")

    def _set_progress(self, ratio: float) -> None:
        ratio = max(0.0, min(1.0, ratio))
        self.progress_canvas.coords("fill", 0, 0, int(185 * ratio), 16)
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
        return StackedScratchGame(
            parent,
            actual_balance,
            actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("叠叠乐")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = StackedScratchGame(root, actual_balance, actual_user)
    page.pack(fill="both", expand=True)
    page.on_back = lambda _balance: root.destroy()
    root.protocol("WM_DELETE_WINDOW", page.on_close)
    root.mainloop()
    return page.balance


if __name__ == "__main__":
    main()