import json
import os
import random
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Dict, Optional, Set, Tuple


# =========================================================
# Banknote_Detection_gui 统一视觉标准
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
ACTION_GREEN = "#4CAF50"
ACTION_BLUE = "#4B8BBE"
SILVER_PALETTE = ("#D7D9D8", "#C8CCCA", "#B8BDBB", "#A9AEAC", "#D0D3D2")


PRIZE_PROBABILITIES = {
    0: 60000,
    5: 22000,
    10: 10000,
    20: 5000,
    25: 2000,
    40: 700,
    50: 200,
    100: 100,
    1000: 10,
    2000: 5,
    20000: 3,
    50000: 1,
}
YOUR_PRIZE_OPTIONS = [5, 10, 25, 50, 100, 1000, 2000, 20000, 50000]


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


def generate_prize() -> int:
    return random.choices(
        list(PRIZE_PROBABILITIES),
        weights=PRIZE_PROBABILITIES.values(),
        k=1,
    )[0]


def generate_numbers() -> Tuple[list, list, list, int]:
    lucky_numbers = random.sample(range(1, 41), 6)
    prize_amount = generate_prize()

    if prize_amount == 0:
        your_numbers = random.sample(
            [number for number in range(1, 41) if number not in lucky_numbers],
            10,
        )
        your_prizes = random.choices(YOUR_PRIZE_OPTIONS, k=10)
    else:
        winning_number = random.choice(lucky_numbers)
        non_winning = random.sample(
            [number for number in range(1, 41) if number not in lucky_numbers],
            9,
        )
        combined = list(
            zip(
                non_winning + [winning_number],
                random.choices(YOUR_PRIZE_OPTIONS, k=9) + [prize_amount],
            )
        )
        random.shuffle(combined)
        your_numbers, your_prizes = zip(*combined)

    return lucky_numbers, list(your_numbers), list(your_prizes), prize_amount


def format_prize(value: float) -> str:
    return f"{value:,.0f}" if value >= 100 else f"{value:,.2f}"


class CashChallengeGame(tk.Frame):
    """固定 10 格、支持真实鼠标刮除效果的 100X 现金大挑战。"""

    TICKET_COST = 5.0
    TOTAL_CELLS = 10

    # 每格刮除达到其中一个阈值时，自动清除余下涂层并完成该格。
    REVEAL_THRESHOLD = 0.74
    RESULT_TEXT_REVEAL_THRESHOLD = 0.68
    BRUSH_RADIUS = 18
    COATING_TILE = 7

    # 下方 10 个数字格使用固定坐标，永远保持 2 行 x 5 列。
    SCRATCH_CANVAS_WIDTH = 516
    SCRATCH_CANVAS_HEIGHT = 150
    CELL_START_X = 8
    CELL_START_Y = 8
    CELL_WIDTH = 92
    CELL_HEIGHT = 62
    CELL_GAP_X = 8
    CELL_GAP_Y = 10

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

        self.lucky_numbers = []
        self.hidden_values: Dict[int, Tuple[int, float, float]] = {}
        self.revealed: Set[int] = set()
        self.ticket_active = False
        self.ticket_serial = "------------"
        self.auto_reveal_job = None
        self._closing = False
        self._last_scratch_xy: Optional[Tuple[int, int]] = None

        self.cell_rects: Dict[int, Tuple[int, int, int, int]] = {}
        self.scratch_cells: Dict[int, Dict[str, object]] = {}

        self.balance_var = tk.StringVar()
        self.stage_var = tk.StringVar(value="待购票")
        self.serial_var = tk.StringVar(value="票号: ------------")
        self.lucky_result_var = tk.StringVar(value="幸运号码: 未生成")
        self.match_result_var = tk.StringVar(value="匹配结果: 未揭晓")
        self.progress_var = tk.StringVar(value="0%")
        self.status_var = tk.StringVar(
            value="购买票券后，按住鼠标拖动刮开 10 个固定数字格。"
        )
        self.last_win_var = tk.StringVar(value="本局赢得: $0.00")

        self._build_ui()
        self._refresh_balance()
        self._reset_ticket_view()

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
        )
        self.table_canvas.pack(fill=tk.BOTH, expand=True)
        self.table_canvas.create_rectangle(
            3, 3, 717, 707, fill=ROOT_BG, outline=GOLD, width=5
        )
        self.table_canvas.create_text(
            360,
            42,
            text="100X 现 金 大 挑 战",
            font=("Microsoft YaHei UI", 25, "bold"),
            fill="#FFD700",
        )
        self.table_canvas.create_text(
            360,
            76,
            text="CASH CHALLENGE · SCRATCH TICKET",
            font=("Arial", 11, "bold"),
            fill=TEXT,
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

        self.ticket_frame = tk.Frame(
            self.table_canvas,
            bg=PANEL_BG,
            width=566,
            height=492,
            bd=4,
            relief=tk.SOLID,
        )
        self.ticket_frame.pack_propagate(False)
        self.table_canvas.create_rectangle(
            67, 105, 653, 617, fill="#102F27", outline="#0C211C", width=2
        )
        self.table_canvas.create_window(
            77, 115, anchor="nw", width=566, height=492, window=self.ticket_frame
        )
        self._build_ticket_board()

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
            text=f"票价: ${self.TICKET_COST:.2f}    最高奖金: $50,000",
            font=("Arial", 11),
            bg=PANEL_BG,
            fg="black",
        ).pack(anchor="w", pady=(4, 0))
        tk.Label(
            ticket_body,
            textvariable=self.lucky_result_var,
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=PANEL_BG,
            fg=ACCENT_FG,
            wraplength=340,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(5, 0))
        self.match_result_label = tk.Label(
            ticket_body,
            textvariable=self.match_result_var,
            font=("Microsoft YaHei UI", 11, "bold"),
            bg=PANEL_BG,
            fg=ACCENT_FG,
        )
        self.match_result_label.pack(anchor="w", pady=(3, 0))

        progress_body = self._panel_card(right_panel, "刮卡进度")
        self.progress_canvas = self._progress_row(
            progress_body, "已刮号码", self.progress_var
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
        button_row.grid_columnconfigure(0, weight=1, uniform="actions")
        button_row.grid_columnconfigure(1, weight=1, uniform="actions")
        self.buy_button = self._action_button(
            button_row, "购买票券（-5 元）", self.buy_ticket, ACTION_GREEN
        )
        self.buy_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.reveal_all_button = self._action_button(
            button_row, "刮开全部", self.reveal_all_numbers, ACTION_BLUE
        )
        self.reveal_all_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        self.reveal_all_button.config(state=tk.DISABLED)
        tk.Label(
            action_body,
            textvariable=self.last_win_var,
            font=("Arial", 12),
            bg=PANEL_BG,
            fg="black",
        ).pack(anchor="w", pady=(8, 0))

        rules_body = self._panel_card(right_panel, "玩法说明")
        tk.Label(
            rules_body,
            text=(
                "1. 购买后立即显示 6 个幸运号码。\n"
                "2. 按住鼠标，在 10 个固定银色格子上拖动刮开。\n"
                "3. 号码匹配幸运号码，即赢得该格奖金。"
            ),
            font=("Microsoft YaHei UI", 10),
            bg=PANEL_BG,
            fg=TITLE_FG,
            justify=tk.LEFT,
            wraplength=340,
        ).pack(anchor="w")

    def _build_ticket_board(self) -> None:
        header = tk.Frame(self.ticket_frame, bg=HEADER_BG, height=65)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header,
            text="100X",
            font=("Georgia", 24, "bold"),
            bg=HEADER_BG,
            fg=TITLE_FG,
        ).pack(side=tk.LEFT, padx=18)
        tk.Label(
            header,
            text="现金大挑战",
            font=("Microsoft YaHei UI", 22, "bold"),
            bg=HEADER_BG,
            fg=TITLE_FG,
        ).pack(side=tk.LEFT, expand=True)
        tk.Label(
            header,
            text="$5",
            font=("Arial", 23, "bold"),
            bg=HEADER_BG,
            fg=TITLE_FG,
        ).pack(side=tk.RIGHT, padx=18)

        tk.Label(
            self.ticket_frame,
            text="匹配幸运号码，赢得该号码下方奖金",
            font=("Microsoft YaHei UI", 11, "bold"),
            bg=PANEL_BG,
            fg=ACCENT_FG,
        ).pack(pady=(13, 8))

        lucky_box = tk.Frame(self.ticket_frame, bg="#FFFDF4", bd=2, relief=tk.SOLID)
        lucky_box.pack(fill=tk.X, padx=24)
        tk.Label(
            lucky_box,
            text="幸运号码",
            font=("Microsoft YaHei UI", 11, "bold"),
            bg="#FFFDF4",
            fg=TITLE_FG,
        ).pack(side=tk.LEFT, padx=(12, 16), pady=10)
        self.lucky_numbers_label = tk.Label(
            lucky_box,
            text="??   ??   ??   ??   ??   ??",
            font=("Consolas", 17, "bold"),
            bg="#FFFDF4",
            fg=ACCENT_FG,
        )
        self.lucky_numbers_label.pack(side=tk.LEFT, pady=10)

        tk.Label(
            self.ticket_frame,
            text="你的号码 / 奖金",
            font=("Microsoft YaHei UI", 12, "bold"),
            bg=PANEL_BG,
            fg=TITLE_FG,
        ).pack(pady=(12, 2))

        # 10 个号码格不再使用 Button，而是使用固定坐标 Canvas。
        self.scratch_canvas = tk.Canvas(
            self.ticket_frame,
            width=self.SCRATCH_CANVAS_WIDTH,
            height=self.SCRATCH_CANVAS_HEIGHT,
            bg=PANEL_BG,
            highlightthickness=0,
            cursor="crosshair",
        )
        self.scratch_canvas.pack()
        self.scratch_canvas.bind("<Button-1>", self._start_scratch)
        self.scratch_canvas.bind("<B1-Motion>", self._scratch_motion)
        self.scratch_canvas.bind("<ButtonRelease-1>", self._stop_scratch)
        self.scratch_canvas.bind("<Leave>", self._stop_scratch)

        self.cell_rects.clear()
        for index in range(self.TOTAL_CELLS):
            row, column = divmod(index, 5)
            x1 = self.CELL_START_X + column * (self.CELL_WIDTH + self.CELL_GAP_X)
            y1 = self.CELL_START_Y + row * (self.CELL_HEIGHT + self.CELL_GAP_Y)
            self.cell_rects[index] = (
                x1,
                y1,
                x1 + self.CELL_WIDTH,
                y1 + self.CELL_HEIGHT,
            )

        tk.Label(
            self.ticket_frame,
            text="最高奖金 $50,000 · 每票 $5.00",
            font=("Arial", 11, "bold"),
            bg=PANEL_BG,
            fg=TITLE_FG,
        ).pack(side=tk.BOTTOM, pady=8)

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

    @staticmethod
    def _action_button(master: tk.Misc, text: str, command, color: str) -> tk.Button:
        return tk.Button(
            master,
            text=text,
            command=command,
            font=("Microsoft YaHei UI", 11, "bold"),
            bg=color,
            fg="white",
            activebackground="#66BB6A" if color == ACTION_GREEN else "#6AA0CA",
            activeforeground="white",
            relief=tk.RAISED,
            bd=2,
            cursor="hand2",
            padx=8,
            pady=9,
        )

    # =====================================================
    # 固定号码格绘制
    # =====================================================
    def _reset_ticket_view(self) -> None:
        self.lucky_numbers_label.config(text="??   ??   ??   ??   ??   ??")
        self.scratch_canvas.delete("all")
        self.scratch_cells.clear()
        self._last_scratch_xy = None

        for index in range(self.TOTAL_CELLS):
            x1, y1, x2, y2 = self.cell_rects[index]
            self.scratch_canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill="#C8CCCA",
                outline="#7A6737",
                width=2,
            )
            self.scratch_canvas.create_text(
                (x1 + x2) // 2,
                (y1 + y2) // 2,
                text="刮开\n????",
                font=("Microsoft YaHei UI", 10, "bold"),
                fill="#5D6361",
                justify=tk.CENTER,
            )

        self._set_progress(0.0)

    def _draw_live_number_grid(self) -> None:
        self.scratch_canvas.delete("all")
        self.scratch_cells.clear()
        self._last_scratch_xy = None

        for index in range(self.TOTAL_CELLS):
            x1, y1, x2, y2 = self.cell_rects[index]
            number, display_prize, _actual_win = self.hidden_values[index]

            self.scratch_canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill="#FFFDF4",
                outline="#7A6737",
                width=2,
                tags=(f"cell_base_{index}",),
            )
            number_item = self.scratch_canvas.create_text(
                (x1 + x2) // 2,
                y1 + 20,
                text=f"{number:02d}",
                font=("Consolas", 16, "bold"),
                fill=TITLE_FG,
                tags=(f"result_{index}",),
            )
            prize_item = self.scratch_canvas.create_text(
                (x1 + x2) // 2,
                y1 + 46,
                text=f"${format_prize(display_prize)}",
                font=("Arial", 9, "bold"),
                fill=ACCENT_FG,
                tags=(f"result_{index}",),
            )

            result_bbox = self.scratch_canvas.bbox(number_item, prize_item)
            if result_bbox is not None:
                result_bbox = (
                    max(x1, result_bbox[0] - 4),
                    max(y1, result_bbox[1] - 4),
                    min(x2, result_bbox[2] + 4),
                    min(y2, result_bbox[3] + 4),
                )

            self.scratch_cells[index] = {
                "rect": self.cell_rects[index],
                "items": set(),
                "total": 0,
                "result_bbox": result_bbox,
                "result_cover_items": set(),
                "result_cover_total": 0,
            }
            self._create_cell_coating(index)

    def _create_cell_coating(self, index: int) -> None:
        area_data = self.scratch_cells[index]
        x1, y1, x2, y2 = area_data["rect"]  # type: ignore[misc]
        items: Set[int] = set()
        tile = self.COATING_TILE

        for row, y in enumerate(range(y1, y2, tile)):
            for column, x in enumerate(range(x1, x2, tile)):
                shade = random.choice(SILVER_PALETTE)
                item = self.scratch_canvas.create_rectangle(
                    x,
                    y,
                    min(x + tile + 1, x2),
                    min(y + tile + 1, y2),
                    fill=shade,
                    outline=shade,
                    tags=(f"coat_{index}",),
                )
                items.add(item)

                if (row + column) % 7 == 0:
                    self.scratch_canvas.create_line(
                        x + 1,
                        min(y + tile - 1, y2),
                        min(x + tile - 1, x2),
                        y + 1,
                        fill="#ECEEEE",
                        width=1,
                        tags=(f"coat_{index}", f"shine_{index}"),
                    )

        area_data["items"] = items
        area_data["total"] = len(items)

        result_bbox = area_data.get("result_bbox")
        if isinstance(result_bbox, tuple) and len(result_bbox) == 4:
            covered = set(self.scratch_canvas.find_overlapping(*result_bbox)) & items
        else:
            covered = set()
        area_data["result_cover_items"] = covered
        area_data["result_cover_total"] = len(covered)

        self.scratch_canvas.create_text(
            (x1 + x2) // 2,
            (y1 + y2) // 2,
            text="刮 开",
            font=("Microsoft YaHei UI", 11, "bold"),
            fill="#4F5553",
            tags=(f"coat_{index}", f"coat_text_{index}"),
        )

    # =====================================================
    # 游戏流程
    # =====================================================
    def buy_ticket(self) -> None:
        if self.ticket_active:
            return
        if self.balance < self.TICKET_COST:
            messagebox.showerror("余额不足", "余额不足以购买现金挑战卡。", parent=self)
            return

        self.balance -= self.TICKET_COST
        lucky, your_numbers, your_prizes, prize_amount = generate_numbers()
        self.lucky_numbers = lucky
        self.hidden_values.clear()
        self.revealed.clear()

        for index in range(self.TOTAL_CELLS):
            actual_win = prize_amount if your_numbers[index] in lucky else 0
            self.hidden_values[index] = (
                your_numbers[index],
                your_prizes[index],
                actual_win,
            )

        self.ticket_serial = "".join(str(random.randrange(10)) for _ in range(12))
        self.ticket_active = True
        self.serial_var.set(f"票号: {self.ticket_serial}")

        # 按下“购买 / 再买”后，幸运号码仍然立即显示，不覆盖、不刮除。
        self.lucky_numbers_label.config(
            text="   ".join(f"{number:02d}" for number in lucky)
        )
        self.lucky_result_var.set(
            "幸运号码: " + "  ".join(f"{number:02d}" for number in lucky)
        )

        self.match_result_var.set("匹配结果: 刮开后揭晓")
        self.match_result_label.config(fg=ACCENT_FG)
        self.last_win_var.set("本局赢得: $0.00")
        self.stage_var.set("刮号码")
        self.status_var.set("按住鼠标左键，在下方 10 个固定银色格子上拖动刮开。")
        self.buy_button.config(state=tk.DISABLED, text="票券进行中")
        self.reveal_all_button.config(state=tk.NORMAL)

        self._draw_live_number_grid()
        self._set_progress(0.0)
        self._refresh_balance()
        self._sync_balance()

    def reveal_single_number(self, index: int) -> None:
        """完成指定号码格；可由手动刮除阈值或“刮开全部”调用。"""
        if (
            not self.ticket_active
            or index not in self.hidden_values
            or index in self.revealed
        ):
            return

        self.revealed.add(index)
        self._clear_cell_coating(index)

        number, _display_prize, actual_win = self.hidden_values[index]
        winning = actual_win > 0

        self.scratch_canvas.itemconfig(
            f"cell_base_{index}",
            fill=SUCCESS if winning else "#FFFDF4",
            outline="#1F6A43" if winning else "#7A6737",
            width=3 if winning else 2,
        )
        self.scratch_canvas.itemconfig(
            f"result_{index}",
            fill="white" if winning else TITLE_FG,
        )

        self._set_progress(len(self.revealed) / self.TOTAL_CELLS)

        if winning:
            self.match_result_var.set(
                f"匹配结果: 号码 {number:02d}，奖金 ${actual_win:,.2f}"
            )
            self.match_result_label.config(fg=SUCCESS)
            self.status_var.set("已发现中奖号码；请继续刮完整张票券。")

        if len(self.revealed) == self.TOTAL_CELLS:
            self._finish_card()

    def reveal_all_numbers(self) -> None:
        if not self.ticket_active:
            return
        self.reveal_all_button.config(state=tk.DISABLED)
        self._reveal_step(0)

    def _reveal_step(self, index: int) -> None:
        while index < self.TOTAL_CELLS:
            if index not in self.revealed:
                self.reveal_single_number(index)
                self.auto_reveal_job = self.after(220, self._reveal_step, index + 1)
                return
            index += 1
        self.auto_reveal_job = None

    def _finish_card(self) -> None:
        total_win = sum(value[2] for value in self.hidden_values.values())

        if total_win > 0:
            self.balance += total_win
            self.last_win_var.set(f"本局赢得: ${total_win:,.2f}")
            self.match_result_var.set(f"匹配结果: 中奖 ${total_win:,.2f}")
            self.match_result_label.config(fg=SUCCESS)
            self.status_var.set(f"恭喜！本张票券赢得 ${total_win:,.2f}。")
        else:
            self.match_result_var.set("匹配结果: 未中奖")
            self.match_result_label.config(fg=DANGER)
            self.status_var.set("本张未中奖，祝你下一张好运。")

        self.ticket_active = False
        self._last_scratch_xy = None
        self.stage_var.set("已结算")
        self.buy_button.config(state=tk.NORMAL, text="再买一张（-5 元）")
        self.reveal_all_button.config(state=tk.DISABLED)
        self._refresh_balance()
        self._sync_balance()

    # =====================================================
    # 鼠标刮除
    # =====================================================
    def _start_scratch(self, event: tk.Event) -> None:
        if not self.ticket_active:
            return
        self._last_scratch_xy = (event.x, event.y)
        self._scratch_at(event.x, event.y)

    def _scratch_motion(self, event: tk.Event) -> None:
        if not self.ticket_active:
            self._last_scratch_xy = None
            return

        if self._last_scratch_xy is None:
            self._last_scratch_xy = (event.x, event.y)
            self._scratch_at(event.x, event.y)
            return

        old_x, old_y = self._last_scratch_xy
        dx = event.x - old_x
        dy = event.y - old_y
        distance = max(abs(dx), abs(dy))
        steps = max(1, distance // 5)

        for step in range(1, steps + 1):
            x = int(old_x + dx * step / steps)
            y = int(old_y + dy * step / steps)
            self._scratch_at(x, y)

        self._last_scratch_xy = (event.x, event.y)

    def _stop_scratch(self, _event: tk.Event) -> None:
        self._last_scratch_xy = None

    def _cell_at(self, x: int, y: int) -> Optional[int]:
        for index, rect in self.cell_rects.items():
            x1, y1, x2, y2 = rect
            if x1 <= x <= x2 and y1 <= y <= y2:
                return index
        return None

    def _scratch_at(self, x: int, y: int) -> None:
        if not self.ticket_active:
            return

        index = self._cell_at(x, y)
        if index is None or index in self.revealed:
            return

        area_data = self.scratch_cells.get(index)
        if area_data is None:
            return

        radius = self.BRUSH_RADIUS
        overlapping = self.scratch_canvas.find_overlapping(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
        )
        coating_items: Set[int] = area_data["items"]  # type: ignore[assignment]
        removed = False

        for item in overlapping:
            tags = self.scratch_canvas.gettags(item)
            if item in coating_items:
                self.scratch_canvas.delete(item)
                coating_items.discard(item)
                removed = True
            elif f"coat_{index}" in tags:
                # 反光线和“刮开”文字不计入百分比，但会随刮痕删除。
                self.scratch_canvas.delete(item)

        if not removed:
            return

        self._emit_dust(x, y)

        total = int(area_data["total"])
        ratio = 1.0 - (len(coating_items) / total if total else 0.0)

        result_cover_items: Set[int] = area_data["result_cover_items"]  # type: ignore[assignment]
        result_cover_total = int(area_data["result_cover_total"])
        result_remaining = len(coating_items & result_cover_items)
        result_ratio = 1.0 - (
            result_remaining / result_cover_total if result_cover_total else 0.0
        )

        if (
            ratio >= self.REVEAL_THRESHOLD
            or result_ratio >= self.RESULT_TEXT_REVEAL_THRESHOLD
        ):
            self.reveal_single_number(index)

    def _emit_dust(self, x: int, y: int) -> None:
        dust_ids = []
        for _ in range(3):
            dx = random.randint(-13, 13)
            dy = random.randint(-13, 13)
            size = random.randint(2, 3)
            dust_ids.append(
                self.scratch_canvas.create_oval(
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
                    self.scratch_canvas.delete(item)
            except tk.TclError:
                pass

        self.after(140, remove_dust)

    def _clear_cell_coating(self, index: int) -> None:
        self.scratch_canvas.delete(f"coat_{index}")
        area_data = self.scratch_cells.get(index)
        if area_data is None:
            return

        coating_items: Set[int] = area_data["items"]  # type: ignore[assignment]
        coating_items.clear()
        result_cover_items: Set[int] = area_data["result_cover_items"]  # type: ignore[assignment]
        result_cover_items.clear()

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
        return CashChallengeGame(
            parent,
            actual_balance,
            actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("100X 现金大挑战")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = CashChallengeGame(root, actual_balance, actual_user)
    page.pack(fill="both", expand=True)
    page.on_back = lambda _balance: root.destroy()
    root.protocol("WM_DELETE_WINDOW", page.on_close)
    root.mainloop()
    return page.balance


if __name__ == "__main__":
    main()