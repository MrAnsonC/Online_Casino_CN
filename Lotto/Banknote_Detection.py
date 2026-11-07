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
# Caribbean Stud Poker 风格配色
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
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, "A_Tools/Account/saving_data.json")


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


class BanknoteDetectionGame(tk.Frame):
    """带真实鼠标刮除效果的验钞刮刮乐。"""

    TICKET_COST = 1.0
    REVEAL_THRESHOLD = 0.77
    RESULT_TEXT_REVEAL_THRESHOLD = 0.70
    BRUSH_RADIUS = 25
    VALUE_RECT = (115, 302, 340, 425)
    AUTH_RECT = (380, 302, 605, 425)

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

        self.total_value: Optional[float] = None
        self.real_or_fake: Optional[str] = None
        self.ticket_serial = "------------"
        self.active_area: Optional[str] = None
        self.ticket_active = False
        self.value_revealed = False
        self.authenticity_revealed = False
        self.prize_paid = False
        self._closing = False
        self._last_scratch_xy: Optional[Tuple[int, int]] = None

        self.scratch_areas: Dict[str, Dict[str, object]] = {
            "value": {
                "items": set(),
                "total": 0,
                "rect": self.VALUE_RECT,
                "result_bbox": None,
                "result_cover_items": set(),
                "result_cover_total": 0,
            },
            "auth": {
                "items": set(),
                "total": 0,
                "rect": self.AUTH_RECT,
                "result_bbox": None,
                "result_cover_items": set(),
                "result_cover_total": 0,
            },
        }

        self.balance_var = tk.StringVar()
        self.stage_var = tk.StringVar(value="待购票")
        self.status_var = tk.StringVar(value="购买票券后，按住鼠标拖动刮开银色涂层。")
        self.serial_var = tk.StringVar(value="票号: ------------")
        self.value_result_var = tk.StringVar(value="钞票总值: 未揭晓")
        self.auth_result_var = tk.StringVar(value="验钞结果: 未揭晓")
        self.last_win_var = tk.StringVar(value="本局赢得: $0.00")
        self.value_progress_var = tk.StringVar(value="0%")
        self.auth_progress_var = tk.StringVar(value="0%")

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
            text="验 钞 刮 刮 乐",
            font=("Microsoft YaHei UI", 25, "bold"),
            fill="#FFD700",
            tags="table",
        )
        self.table_canvas.create_text(
            360,
            76,
            text="BANKNOTE DETECTION · SCRATCH TICKET",
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

        # 玩家信息
        info_body = self._panel_card(right_panel, "玩家信息")
        self.balance_label = tk.Label(
            info_body,
            textvariable=self.balance_var,
            font=("Arial", 16, "bold"),
            bg=PANEL_BG,
            fg="black",
        )
        self.balance_label.pack(side=tk.LEFT)
        tk.Label(
            info_body,
            textvariable=self.stage_var,
            font=("Microsoft YaHei UI", 15, "bold"),
            bg=PANEL_BG,
            fg=ACCENT_FG,
        ).pack(side=tk.RIGHT)

        # 当前票券
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
        self.value_result_label = tk.Label(
            ticket_body,
            textvariable=self.value_result_var,
            font=("Microsoft YaHei UI", 12, "bold"),
            bg=PANEL_BG,
            fg=ACCENT_FG,
        )
        self.value_result_label.pack(anchor="w", pady=(5, 0))
        self.auth_result_label = tk.Label(
            ticket_body,
            textvariable=self.auth_result_var,
            font=("Microsoft YaHei UI", 12, "bold"),
            bg=PANEL_BG,
            fg=ACCENT_FG,
        )
        self.auth_result_label.pack(anchor="w", pady=(3, 0))

        # 刮卡进度
        progress_body = self._panel_card(right_panel, "刮卡进度")
        self.value_progress_canvas = self._progress_row(
            progress_body, "钞票总值", self.value_progress_var
        )
        self.auth_progress_canvas = self._progress_row(
            progress_body, "验钞结果", self.auth_progress_var
        )

        # 操作
        action_body = self._panel_card(right_panel, "操作")
        self.status_label = tk.Label(
            action_body,
            textvariable=self.status_var,
            font=("Microsoft YaHei UI", 11, "bold"),
            bg=PANEL_BG,
            fg=TITLE_FG,
            justify=tk.LEFT,
            wraplength=335,
            height=3,
        )
        self.status_label.pack(fill=tk.X, pady=(0, 6))

        button_row = tk.Frame(action_body, bg=PANEL_BG)
        button_row.pack(fill=tk.X)
        button_row.grid_columnconfigure(0, weight=1, uniform="action_buttons")
        button_row.grid_columnconfigure(1, weight=1, uniform="action_buttons")
        self.buy_button = tk.Button(
            button_row,
            text="购买票券（-1 元）",
            command=self.draw_ticket,
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

        self.reveal_button = tk.Button(
            button_row,
            text="刮开当前区",
            command=self.reveal_current_area,
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
        self.reveal_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        tk.Label(
            action_body,
            textvariable=self.last_win_var,
            font=("Arial", 12),
            bg=PANEL_BG,
            fg="black",
        ).pack(anchor="w", pady=(8, 0))

        # 玩法说明
        rules_body = self._panel_card(right_panel, "玩法说明")
        rules = (
            "1. 先刮左侧金额，再刮右侧真伪。\n"
            "2. 真钞按显示金额派彩；假钞不派彩。\n"
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
            352,
            text="请先在右侧购买票券",
            font=("Microsoft YaHei UI", 22, "bold"),
            fill=TITLE_FG,
            tags="ticket",
        )
        self.table_canvas.create_text(
            360,
            400,
            text="购买后按住鼠标，在银色区域来回刮动",
            font=("Microsoft YaHei UI", 12),
            fill="#6D5B33",
            tags="ticket",
        )

    def _draw_ticket_base(self) -> None:
        c = self.table_canvas
        c.create_rectangle(
            67, 105, 653, 612, fill="#102F27", outline="#0C211C", width=2, tags="ticket"
        )
        c.create_rectangle(
            77, 115, 643, 602, fill=PANEL_BG, outline=GOLD, width=4, tags="ticket"
        )
        c.create_rectangle(
            77, 115, 643, 180, fill=HEADER_BG, outline=GOLD, width=2, tags="ticket"
        )
        c.create_text(
            105,
            147,
            text="BN",
            font=("Georgia", 25, "bold"),
            fill=TITLE_FG,
            tags="ticket",
        )
        c.create_text(
            360,
            143,
            text="验钞刮刮乐",
            font=("Microsoft YaHei UI", 24, "bold"),
            fill=TITLE_FG,
            tags="ticket",
        )
        c.create_text(
            360,
            168,
            text="BANKNOTE AUTHENTICITY TICKET",
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

        # 简单钞票纹样，增加票券感
        for radius in range(28, 125, 16):
            c.create_oval(
                360 - radius * 1.6,
                360 - radius * 0.55,
                360 + radius * 1.6,
                360 + radius * 0.55,
                outline="#D6C79E",
                width=1,
                tags="ticket",
            )
        for y in (205, 222, 239, 474, 491, 508):
            c.create_line(97, y, 623, y, fill="#D8C99F", dash=(4, 4), tags="ticket")

    def _draw_live_ticket(self) -> None:
        self.table_canvas.delete("ticket")
        self._draw_ticket_base()
        c = self.table_canvas

        c.create_text(
            100,
            210,
            text=f"SERIAL  {self.ticket_serial}",
            font=("Consolas", 12, "bold"),
            fill=TITLE_FG,
            anchor="w",
            tags="ticket",
        )
        c.create_text(
            620,
            210,
            text="先金额 · 后验钞",
            font=("Microsoft YaHei UI", 11, "bold"),
            fill=ACCENT_FG,
            anchor="e",
            tags="ticket",
        )
        c.create_text(
            227,
            270,
            text="① 钞票总值",
            font=("Microsoft YaHei UI", 15, "bold"),
            fill=TITLE_FG,
            tags="ticket",
        )
        c.create_text(
            492,
            270,
            text="② 验钞结果",
            font=("Microsoft YaHei UI", 15, "bold"),
            fill=TITLE_FG,
            tags="ticket",
        )

        value_color = {
            10: "#8758B5",
            20: "#2E5AAC",
            50: "#2F7D32",
            100: "#C04A2B",
            500: "#8B4B10",
            1000: "#8C7A00",
        }.get(self.total_value, TITLE_FG)

        self._draw_result_window(
            "value",
            self.VALUE_RECT,
            result=f"￥{float(self.total_value):,.2f}",
            result_color=value_color,
        )
        self._draw_result_window(
            "auth",
            self.AUTH_RECT,
            result=str(self.real_or_fake),
            result_color=SUCCESS if self.real_or_fake == "真" else DANGER,
        )

        self._create_coating("value")
        self._create_coating("auth")
        c.create_rectangle(
            self.AUTH_RECT[0],
            self.AUTH_RECT[1],
            self.AUTH_RECT[2],
            self.AUTH_RECT[3],
            fill="#173F35",
            stipple="gray50",
            outline="#0D2821",
            width=2,
            tags=("ticket", "auth_lock"),
        )
        c.create_text(
            (self.AUTH_RECT[0] + self.AUTH_RECT[2]) // 2,
            (self.AUTH_RECT[1] + self.AUTH_RECT[3]) // 2,
            text="🔒 先刮开金额",
            font=("Microsoft YaHei UI", 14, "bold"),
            fill=TEXT,
            tags=("ticket", "auth_lock"),
        )

        c.create_text(
            360,
            465,
            text="按住鼠标左键，在银色涂层上来回拖动",
            font=("Microsoft YaHei UI", 12, "bold"),
            fill=TITLE_FG,
            tags="ticket",
        )
        c.create_text(
            102,
            548,
            text="中奖规则",
            font=("Microsoft YaHei UI", 12, "bold"),
            fill=ACCENT_FG,
            anchor="w",
            tags="ticket",
        )
        c.create_text(
            102,
            574,
            text="真钞：赢得票面金额    ·    假钞：无派彩    ·    每票 $1.00",
            font=("Microsoft YaHei UI", 11),
            fill=TITLE_FG,
            anchor="w",
            tags="ticket",
        )

    def _draw_result_window(
        self,
        area: str,
        rect: Tuple[int, int, int, int],
        result: str,
        result_color: str,
    ) -> None:
        x1, y1, x2, y2 = rect
        c = self.table_canvas
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

        # 先在中心创建，以实际文字边界计算安全随机范围，确保文字不会越出格子。
        result_item = c.create_text(
            (x1 + x2) // 2,
            (y1 + y2) // 2,
            text=result,
            font=("Microsoft YaHei UI", 28, "bold"),
            fill=result_color,
            tags=("ticket", f"result_{area}"),
        )
        bbox = c.bbox(result_item)
        if bbox is None:
            self.scratch_areas[area]["result_bbox"] = None
            return

        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        margin = 12
        min_x = x1 + margin + text_width // 2
        max_x = x2 - margin - text_width // 2
        min_y = y1 + margin + text_height // 2
        max_y = y2 - margin - text_height // 2

        result_x = random.randint(min_x, max_x) if min_x <= max_x else (x1 + x2) // 2
        result_y = random.randint(min_y, max_y) if min_y <= max_y else (y1 + y2) // 2
        c.coords(result_item, result_x, result_y)

        # 稍微扩张文字触发区域，避免只剩抗锯齿边缘时仍不触发自动揭示。
        final_bbox = c.bbox(result_item)
        if final_bbox is not None:
            padding = 3
            self.scratch_areas[area]["result_bbox"] = (
                final_bbox[0] - padding,
                final_bbox[1] - padding,
                final_bbox[2] + padding,
                final_bbox[3] + padding,
            )

    def _create_coating(self, area: str) -> None:
        area_data = self.scratch_areas[area]
        rect = area_data["rect"]
        x1, y1, x2, y2 = rect  # type: ignore[misc]
        items: Set[int] = set()
        tile = 10
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
                    tags=("ticket", f"coat_{area}"),
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
                        tags=("ticket", f"coat_{area}", f"shine_{area}"),
                    )
        area_data["items"] = items
        area_data["total"] = len(items)

        result_bbox = area_data.get("result_bbox")
        if isinstance(result_bbox, tuple) and len(result_bbox) == 4:
            covered = set(self.table_canvas.find_overlapping(*result_bbox)) & items
        else:
            covered = set()
        area_data["result_cover_items"] = covered
        area_data["result_cover_total"] = len(covered)

        self.table_canvas.create_text(
            (x1 + x2) // 2,
            (y1 + y2) // 2,
            text="刮 开 此 处",
            font=("Microsoft YaHei UI", 15, "bold"),
            fill="#4F5553",
            tags=("ticket", f"coat_{area}", f"coat_text_{area}"),
        )

    # =====================================================
    # 游戏流程
    # =====================================================
    def draw_ticket(self) -> None:
        if self.ticket_active:
            return
        if self.balance < self.TICKET_COST:
            messagebox.showerror("余额不足", "余额不足以购买验钞卡。", parent=self)
            return

        self.balance -= self.TICKET_COST
        self.real_or_fake = random.choices(["真", "假"], weights=[40, 60])[0]
        if self.real_or_fake == "真":
            probabilities = [29.4, 24.5, 17.2, 12.3, 7.4, 3.7, 1.7, 0.7, 0.5, 0.2]
        else:
            probabilities = [10, 15, 15, 10, 10, 10, 10, 10, 5, 5]
        self.total_value = random.choices(
            [0.5, 1, 2, 5, 10, 20, 50, 100, 500, 1000],
            weights=probabilities,
        )[0]
        self.ticket_serial = "".join(str(random.randrange(10)) for _ in range(12))

        self.ticket_active = True
        self.active_area = "value"
        self.value_revealed = False
        self.authenticity_revealed = False
        self.prize_paid = False
        self._last_scratch_xy = None

        self.serial_var.set(f"票号: {self.ticket_serial}")
        self.value_result_var.set("钞票总值: 未揭晓")
        self.auth_result_var.set("验钞结果: 未揭晓")
        self.value_result_label.config(fg=ACCENT_FG)
        self.auth_result_label.config(fg=ACCENT_FG)
        self.last_win_var.set("本局赢得: $0.00")
        self.stage_var.set("刮金额")
        self.status_var.set("请先刮开左侧“钞票总值”银色区域。")
        self.buy_button.config(state=tk.DISABLED, text="票券进行中")
        self.reveal_button.config(state=tk.NORMAL)
        self._set_progress("value", 0.0)
        self._set_progress("auth", 0.0)
        self._draw_live_ticket()
        self._refresh_balance()
        self._sync_balance()

    def reveal_current_area(self) -> None:
        if not self.ticket_active or self.active_area not in ("value", "auth"):
            return
        area = self.active_area
        self._clear_coating(area)
        self._complete_area(area)

    def _complete_area(self, area: str) -> None:
        if area == "value":
            if self.value_revealed:
                return
            self.value_revealed = True
            self._clear_coating("value")
            self._set_progress("value", 1.0)
            self.value_result_var.set(f"钞票总值: ${float(self.total_value):,.2f}")
            self.table_canvas.delete("auth_lock")
            self.active_area = "auth"
            self.stage_var.set("验真伪")
            self.status_var.set("金额已揭晓。现在刮开右侧“验钞结果”。")
            return

        if self.authenticity_revealed:
            return
        self.authenticity_revealed = True
        self._clear_coating("auth")
        self._set_progress("auth", 1.0)
        self.auth_result_var.set(f"验钞结果: {self.real_or_fake}钞")

        if self.real_or_fake == "真" and not self.prize_paid:
            winnings = float(self.total_value)
            self.balance += winnings
            self.prize_paid = True
            self.last_win_var.set(f"本局赢得: ${winnings:,.2f}")
            self.auth_result_label.config(fg=SUCCESS)
            self.status_var.set(f"真钞！已派彩 ${winnings:,.2f}。")
        else:
            self.last_win_var.set("本局赢得: $0.00")
            self.auth_result_label.config(fg=DANGER)
            self.status_var.set("很遗憾，这是一张假钞，本局无派彩。")

        self.ticket_active = False
        self.active_area = None
        self.stage_var.set("已结算")
        self.buy_button.config(state=tk.NORMAL, text="再买一张（-1 元）")
        self.reveal_button.config(state=tk.DISABLED)
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
        area = self.active_area
        if not self.ticket_active or area not in ("value", "auth"):
            return

        area_data = self.scratch_areas[area]
        x1, y1, x2, y2 = area_data["rect"]  # type: ignore[misc]
        if not (x1 <= x <= x2 and y1 <= y <= y2):
            return

        radius = self.BRUSH_RADIUS
        overlapping = self.table_canvas.find_overlapping(
            x - radius, y - radius, x + radius, y + radius
        )
        coating_items: Set[int] = area_data["items"]  # type: ignore[assignment]
        removed = False
        for item in overlapping:
            tags = self.table_canvas.gettags(item)
            if item in coating_items:
                self.table_canvas.delete(item)
                coating_items.discard(item)
                removed = True
            elif f"coat_{area}" in tags:
                # 文字和反光线不计入百分比，但也随刮痕移除。
                self.table_canvas.delete(item)

        if not removed:
            return

        self._emit_dust(x, y)
        total = int(area_data["total"])
        ratio = 1.0 - (len(coating_items) / total if total else 0.0)
        self._set_progress(area, ratio)

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
            self._complete_area(area)

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

    def _clear_coating(self, area: str) -> None:
        self.table_canvas.delete(f"coat_{area}")
        area_data = self.scratch_areas[area]
        coating_items: Set[int] = area_data["items"]  # type: ignore[assignment]
        coating_items.clear()
        result_cover_items: Set[int] = area_data["result_cover_items"]  # type: ignore[assignment]
        result_cover_items.clear()

    # =====================================================
    # 状态辅助
    # =====================================================
    def _set_progress(self, area: str, ratio: float) -> None:
        ratio = max(0.0, min(1.0, ratio))
        canvas = self.value_progress_canvas if area == "value" else self.auth_progress_canvas
        var = self.value_progress_var if area == "value" else self.auth_progress_var
        canvas.coords("fill", 0, 0, int(210 * ratio), 16)
        var.set(f"{int(round(ratio * 100)):d}%")

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
        return BanknoteDetectionGame(
            parent,
            actual_balance,
            actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("验钞刮刮乐")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = BanknoteDetectionGame(root, actual_balance, actual_user)
    page.pack(fill="both", expand=True)
    page.on_back = lambda _balance: root.destroy()
    root.protocol("WM_DELETE_WINDOW", page.on_close)
    root.mainloop()
    return page.balance


if __name__ == "__main__":
    main()