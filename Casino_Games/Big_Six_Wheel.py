import json
import math
import os
import random
import time
import tkinter as tk
from tkinter import messagebox, ttk

try:
    from PIL import Image, ImageTk, ImageColor
except Exception:
    Image = ImageTk = ImageColor = None


# ---------------------------
# Paths / persistence helpers
# ---------------------------

def project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def user_data_path() -> str:
    return os.path.join(project_root(), "saving_data.json")


def big_six_log_path() -> str:
    log_dir = os.path.join(project_root(), "A_Logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Big_Six.json")


def ensure_json_file(path: str, default_obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_obj, f, ensure_ascii=False, indent=4)


def load_user_data():
    path = user_data_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_user_data(users):
    path = user_data_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)


def load_balance(username: str, default_balance: float = 1_000_000.0) -> float:
    if username == "Guest":
        return default_balance

    users = load_user_data()
    for user in users:
        if user.get("user_name") == username:
            try:
                return float(user.get("cash", default_balance))
            except Exception:
                return default_balance
    users.append({"user_name": username, "cash": f"{default_balance:.2f}"})
    save_user_data(users)
    return default_balance


def update_balance_in_json(username: str, new_balance: float):
    if username == "Guest":
        return

    users = load_user_data()
    found = False
    for user in users:
        if user.get("user_name") == username and username != "Guest":
            user["cash"] = f"{float(new_balance):.2f}"
            found = True
            break
    if not found:
        users.append({"user_name": username, "cash": f"{float(new_balance):.2f}"})
    save_user_data(users)


# ---------------------------
# Game constants
# ---------------------------

WHEEL_SEQUENCE = [
    "1", "3", "1", "6", "1", "3", "1", "👑",
    "1", "3", "1", "6", "3", "1", "12", "1",
    "6", "1", "3", "1", "25", "1", "3", "1",
    "6", "1", "3", "1", "12", "1", "6", "1",
    "3", "1", "💵", "3", "1", "3", "1", "3",
    "1", "12", "1", "6", "1", "3", "1", "25",
    "1", "3", "1", "6", "1", "12"
]
assert len(WHEEL_SEQUENCE) == 54, f"Wheel sequence must have 54 items, got {len(WHEEL_SEQUENCE)}"

OUTCOME_MULTIPLIERS = {
    "1": 2,     # bet * (1+1)
    "3": 4,     # bet * (3+1)
    "6": 7,     # bet * (6+1)
    "12": 13,   # bet * (12+1)
    "25": 26,   # bet * (25+1)
    "👑": 51,
    "💵": 51,
}

OUTCOME_COLORS = {
    "1": "#E8E8E8",
    "3": "#A0F0C0",
    "6": "#70B0FF",
    "12": "#FF64F5",
    "25": "#27CC27",
    "👑": "#FBFF02",
    "💵": "#FFA509"
}

OUTCOME_TEXT_COLORS = {
    "1": "black",
    "3": "black",
    "6": "black",
    "12": "black",
    "25": "black",
    "👑": "black",
    "💵": "black",
}

OUTCOME_DISPLAY = ["1", "3", "6", "12", "25", "👑", "💵"]


# ---------------------------
# History store (persistence only) - MODIFIED for key order
# ---------------------------

class BigSixHistory:
    # 期望的 JSON 顶层键顺序：Total -> 各统计结果 -> 54_Record
    ORDERED_TOP_KEYS = ["Total"] + OUTCOME_DISPLAY + ["54_Record"]

    def __init__(self, path: str):
        self.path = path
        self.data = self._load_or_create()
        # 重排已有文件顺序（仅第一次运行时会整理，之后保存也会保持顺序）
        self._reorder_and_save()

    def _default_payload(self):
        # 按照期望的顺序构建默认数据结构
        payload = {}
        payload["Total"] = 0
        for k in OUTCOME_DISPLAY:
            payload[k] = 0
        payload["54_Record"] = {}
        return payload

    def _load_or_create(self):
        ensure_json_file(self.path, self._default_payload())
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return self._default_payload()
        except Exception:
            return self._default_payload()

        # 用默认结构补全缺失字段
        payload = self._default_payload()
        if isinstance(data.get("54_Record"), dict):
            payload["54_Record"] = data["54_Record"]
        if isinstance(data.get("Total"), int):
            payload["Total"] = data["Total"]
        for k in OUTCOME_DISPLAY:
            try:
                payload[k] = int(data.get(k, 0))
            except Exception:
                payload[k] = 0
        return payload

    def _reorder_and_save(self):
        """按照 ORDERED_TOP_KEYS 顺序重排 self.data 并写回文件"""
        new_data = {}
        for key in self.ORDERED_TOP_KEYS:
            if key in self.data:
                new_data[key] = self.data[key]
        # 若存在未知键（理论上没有），追加到末尾
        for key, value in self.data.items():
            if key not in new_data:
                new_data[key] = value
        self.data = new_data
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    def _extract_result(self, entry):
        if isinstance(entry, dict):
            if "result" in entry:
                return str(entry["result"])
            for key in ("result", "outcome", "symbol", "win", "name"):
                if key in entry:
                    return str(entry[key])
        elif isinstance(entry, list) and entry:
            return str(entry[0])
        elif entry is not None:
            return str(entry)
        return ""

    def recent_results(self, limit: int = 54):
        record = self.data.get("54_Record", {})
        ordered = []
        for i in range(1, 55):
            key = f"{i:02d}_Data"
            if key in record:
                res = self._extract_result(record[key])
                if res in OUTCOME_DISPLAY:
                    ordered.append(res)
                else:
                    ordered.append("")
            else:
                ordered.append("")
        return ordered[:limit]

    def add_result(self, result: str, bet_snapshot: dict, payout: float, wheel_index: int):
        self.data = self._load_or_create()
        record = self.data.get("54_Record", {})

        has_full = "54_Data" in record
        if has_full:
            for i in range(49, 55):
                key = f"{i:02d}_Data"
                record.pop(key, None)

        existing_results = []
        for i in range(1, 55):
            key = f"{i:02d}_Data"
            if key in record:
                res = self._extract_result(record[key])
                if res in OUTCOME_DISPLAY:
                    existing_results.append(res)
                else:
                    existing_results.append("")
            else:
                existing_results.append("")

        new_results = [result] + [r for r in existing_results if r != ""]
        new_results = new_results[:54]

        new_record = {}
        for idx, res in enumerate(new_results, start=1):
            new_record[f"{idx:02d}_Data"] = {"result": res}

        self.data["54_Record"] = new_record
        self.data["Total"] = int(self.data.get("Total", 0)) + 1

        if result in OUTCOME_DISPLAY:
            self.data[result] = int(self.data.get(result, 0)) + 1

        # 保存时按顺序写入
        self._reorder_and_save()

    def counts(self):
        return {k: int(self.data.get(k, 0)) for k in OUTCOME_DISPLAY}

    def total(self):
        return int(self.data.get("Total", 0))


# ---------------------------
# Main app
# ---------------------------

class BigSixWheelGUI(tk.Tk):
    BETTING_SECONDS = 0
    TIMER_TICK_MS = 250

    def __init__(self, initial_balance=1_000_000, username="Guest"):
        super().__init__()
        self.title("幸运之轮")
        self.geometry("1350x700+50+10")
        self.resizable(False, False)
        self.configure(bg="#35654d")

        self.username = username
        self.balance = float(load_balance(username, float(initial_balance)))
        self.history = BigSixHistory(big_six_log_path())

        # 标记路相关数据
        self.marker_results = []
        self.stats_counts = {k: 0 for k in OUTCOME_DISPLAY}
        self.marker_rows = 6
        self.marker_cols = 9

        self.bet_buttons = {}
        self.chip_buttons = []
        self.current_bets = {k: 0 for k in OUTCOME_DISPLAY}
        self.selected_bet_amount = 1000
        self.selected_chip = None

        self.round_state = "betting"
        self.betting_deadline = None
        self._countdown_job = None
        self._spin_job = None

        # 物理旋转相关属性
        self.current_wheel_offset = 0.0      # 当前轮盘旋转角度（度）
        self.wheel_velocity = 0.0            # 角速度（度/秒）
        self.wheel_acceleration = 0.0        # 角加速度（度/秒²），负值表示减速
        self._last_physics_time = None
        self.is_spinning = False

        self.current_round_result = None
        self.current_round_index = None
        self.center_display_result = None
        self.wheel_timer_id = None

        self._build_ui()
        self._sync_marker_from_history()
        self._start_new_round()

        self.bind('<Return>', lambda event: self.start_game())
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------- UI build (保持不变) -------------------
    def _build_ui(self):
        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(main, width=300)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right_frame = ttk.Frame(main, width=440)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)

        self._build_left_side(left_frame)
        self._build_right_side(right_frame)

    def _build_left_side(self, parent):
        top_frame = tk.Frame(parent, bg="#35654d")
        top_frame.pack(fill=tk.X, padx=8, pady=(8, 4))

        self.wheel_canvas = tk.Canvas(top_frame, width=900, height=430, bg="#35654d", highlightthickness=0)
        self.wheel_canvas.pack(fill=tk.X)
        self._draw_wheel()

        betting_area = tk.Frame(parent, bg="#D0E7FF", height=200)
        betting_area.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        betting_left = tk.Frame(betting_area, bg="#D0E7FF")
        betting_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        betting_center = tk.Frame(betting_area, bg="#D0E7FF")
        betting_center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        betting_right = tk.Frame(betting_area, bg="#D0E7FF")
        betting_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=2)

        self._populate_betting_left(betting_left)
        self._populate_betting_center(betting_center)
        self._populate_betting_right(betting_right)

    def _populate_betting_left(self, parent):
        title_label = tk.Label(
            parent,
            text="下注区域",
            font=("Arial", 16, "bold"),
            bg="#D0E7FF",
            fg="#000000"
        )
        title_label.pack(side=tk.TOP, fill=tk.X, pady=(5, 0))

        rows = [
            (0, ["👑", "💵"]),
            (1, ["12", "25"]),
            (2, ["1", "3", "6"]),
        ]
        for row_idx, symbols in rows:
            row_frame = tk.Frame(parent, bg="#D0E7FF")
            row_frame.pack(fill=tk.BOTH, expand=True, pady=2)
            for col, symbol in enumerate(symbols):
                row_frame.columnconfigure(col, weight=1)
                btn = tk.Button(
                    row_frame,
                    text=f"{symbol}\n$0",
                    font=("Arial", 14, "bold"),
                    bg=OUTCOME_COLORS[symbol],
                    fg=OUTCOME_TEXT_COLORS[symbol],
                    height=2,
                    width=10,
                    relief=tk.RAISED,
                    bd=3,
                    command=lambda s=symbol: self.place_bet(s),
                )
                btn.bet_symbol = symbol
                btn.original_bg = OUTCOME_COLORS[symbol]
                btn.disabled_bg = "#AAAAAA"
                btn.grid(row=0, column=col, padx=4, pady=1, sticky="nsew")
                btn.bind('<Button-3>', lambda e, s=symbol: self.clear_single_bet(s))
                self.bet_buttons[symbol] = btn

    def _populate_betting_center(self, parent):
        balance_frame = tk.Frame(parent, bg="#D0E7FF")
        balance_frame.pack(fill=tk.X, pady=(5, 0))

        self.balance_label = tk.Label(
            balance_frame,
            text=f"余额: ${self.balance:,.2f}",
            font=("Arial", 16, "bold"),
            bg="#D0E7FF",
            fg="black",
            width=18,
            anchor='w'
        )
        self.balance_label.pack(side=tk.LEFT)

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=3)

        btn_frame = tk.Frame(parent, bg="#D0E7FF")
        btn_frame.pack(fill=tk.X, pady=5)
        self.reset_button = tk.Button(btn_frame, text="清除下注", command=self.clear_bets, bg="#ff4444", fg="white", font=("微软雅黑", 14, "bold"))
        self.reset_button.pack(side=tk.TOP, fill=tk.X, padx=10, pady=2)
        self.deal_button = tk.Button(btn_frame, text="开始游戏 (Enter)", command=self.start_game, bg="gold", fg="black", font=("微软雅黑", 14, "bold"))
        self.deal_button.pack(side=tk.TOP, fill=tk.X, padx=10, pady=2)

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        info_frame = tk.Frame(parent, bg="#D0E7FF")
        info_frame.pack(fill=tk.X, pady=5)

        tk.Label(info_frame, text="当前下注:", font=("微软雅黑", 16), bg="#D0E7FF").grid(row=0, column=0, sticky='w', padx=5)
        self.current_bet_label = tk.Label(info_frame, text="$0", font=("微软雅黑", 16), bg="#D0E7FF", fg="black")
        self.current_bet_label.grid(row=0, column=1, sticky='e', padx=5)

        tk.Label(info_frame, text="上局获胜:", font=("微软雅黑", 16), bg="#D0E7FF").grid(row=1, column=0, sticky='w', padx=5)
        self.last_win_label = tk.Label(info_frame, text="$0", font=("微软雅黑", 16), bg="#D0E7FF", fg="black")
        self.last_win_label.grid(row=1, column=1, sticky='e', padx=5)

        info_frame.columnconfigure(1, weight=1)

    def _populate_betting_right(self, parent):
        chips_frame = tk.Frame(parent, bg="#D0E7FF")
        chips_frame.pack(pady=10)

        chips = [
            ("100", "#000000"),
            ("500", "#FF7DDA"),
            ("1千", "#ab0058"),
            ("5千", "#ff0000"),
            ("1万", "#800080"),
            ("3万", "#ffa500"),
            ("5万", "#006400"),
            ("10万", "#00ff00"),
            ("50万", "#0000ff")
        ]

        for i in range(0, len(chips), 3):
            row_frame = tk.Frame(chips_frame, bg="#D0E7FF")
            row_frame.pack(pady=2)
            for text, bg_color in chips[i:i+3]:
                chip_canvas = self._create_chip_button(row_frame, text, bg_color)
                chip_canvas.pack(side=tk.LEFT, padx=2)

        self.current_chip_label = tk.Label(parent, text="筹码: $1,000", font=("Arial", 14, "bold"), bg="#D0E7FF")
        self.current_chip_label.pack(pady=5)

        self._set_default_chip()

    def _create_chip_button(self, parent, text, bg_color):
        size = 60
        canvas = tk.Canvas(parent, width=size, height=size, highlightthickness=0, bg="#D0E7FF")
        chip_id = canvas.create_oval(2, 2, size-2, size-2, fill=bg_color, outline="", width=0)

        try:
            rgb = ImageColor.getrgb(bg_color)
            luminance = 0.299*rgb[0] + 0.587*rgb[1] + 0.114*rgb[2]
            text_color = "white" if luminance < 140 else "black"
        except:
            text_color = "black"

        canvas.create_text(size/2, size/2, text=text, fill=text_color, font=("Arial", 14, "bold"))
        canvas.bind("<Button-1>", lambda e, t=text, c=canvas, cid=chip_id: self._set_bet_amount(t, c, cid))

        self.chip_buttons.append({"canvas": canvas, "chip_id": chip_id, "text": text})
        return canvas

    def _set_bet_amount(self, chip_text, clicked_canvas, clicked_chip_id):
        for chip in self.chip_buttons:
            chip["canvas"].itemconfig(chip["chip_id"], outline="", width=0)
            chip["canvas"].delete("glow")
        clicked_canvas.itemconfig(clicked_chip_id, outline="yellow", width=4)
        self.selected_chip = next((c for c in self.chip_buttons if c["canvas"] == clicked_canvas), None)

        if "千" in chip_text:
            amount = int(chip_text.replace("千", "")) * 1000
        elif "万" in chip_text:
            amount = int(chip_text.replace("万", "")) * 10000
        else:
            amount = int(chip_text)
        self.selected_bet_amount = amount
        self.current_chip_label.config(text=f"筹码: ${amount:,}")

    def _set_default_chip(self):
        for chip in self.chip_buttons:
            if chip["text"] == "1千":
                chip["canvas"].itemconfig(chip["chip_id"], outline="yellow", width=4)
                self.selected_chip = chip
                self.selected_bet_amount = 1000
                self.current_chip_label.config(text="筹码: $1,000")
                break

    # ---------- 右侧面板：统计 + 标记路 ----------
    def _build_right_side(self, parent):
        self.right_frame = tk.Frame(parent, bg='#D0E7FF')
        self.right_frame.pack(fill=tk.BOTH, expand=True)

        self._create_stats_display(self.right_frame)
        self._create_marker_road(self.right_frame)
        self._create_pie_chart(self.right_frame)

    def _create_stats_display(self, parent):
        self.stats_frame = tk.Frame(parent, bg='#D0E7FF', height=250)
        self.stats_frame.pack(fill=tk.X, pady=(0, 8))
        self.stats_frame.pack_propagate(False)

        title_label = tk.Label(
            self.stats_frame,
            text="统计结果",
            font=('Arial', 16, 'bold'),
            bg='#D0E7FF',
            fg='#000000'
        )
        title_label.pack(pady=(2, 0))

        table_frame = tk.Frame(self.stats_frame, bg='#D0E7FF')
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        headers = ['图标', '数量']
        for i, header in enumerate(headers):
            tk.Label(
                table_frame,
                text=header,
                font=('Arial', 14, 'bold'),
                bg='#4B8BBE',
                fg='white',
                width=16,
                height=1,
                relief=tk.RAISED,
                bd=2
            ).grid(row=0, column=i, padx=1, pady=1, sticky='nsew')

        self.stats_rows = {}
        for row_idx, symbol in enumerate(OUTCOME_DISPLAY, 1):
            icon_frame = tk.Frame(table_frame, bg='#FFFFFF', width=60, height=40)
            icon_frame.grid(row=row_idx, column=0, padx=1, pady=1, sticky='nsew')
            icon_frame.grid_propagate(False)

            icon_canvas = tk.Canvas(
                icon_frame,
                width=26,
                height=26,
                bg='#FFFFFF',
                highlightthickness=0
            )
            icon_canvas.place(relx=0.5, rely=0.5, anchor='center')

            center_x, center_y = 13, 13
            radius = 10
            icon_canvas.create_oval(
                center_x - radius, center_y - radius,
                center_x + radius, center_y + radius,
                fill=OUTCOME_COLORS[symbol],
                outline='#000000',
                width=2
            )
            icon_canvas.create_text(
                center_x, center_y,
                text=symbol,
                fill=OUTCOME_TEXT_COLORS[symbol],
                font=('Arial', 10, 'bold')
            )

            count_label = tk.Label(
                table_frame,
                text="0",
                font=('Arial', 14, 'bold'),
                bg='#FFFFFF',
                fg='#000000',
                width=8,
                height=2,
                relief=tk.RIDGE,
                bd=1
            )
            count_label.grid(row=row_idx, column=1, padx=1, pady=1, sticky='nsew')

            self.stats_rows[symbol] = count_label

        for i in range(3):
            table_frame.columnconfigure(i, weight=1)
        for i in range(len(OUTCOME_DISPLAY) + 1):
            table_frame.rowconfigure(i, weight=1, minsize=25)

        self._update_stats_display()

    def _update_stats_display(self):
        if hasattr(self, 'stats_rows'):
            for symbol, label in self.stats_rows.items():
                label.config(text=str(self.stats_counts.get(symbol, 0)))

    def _create_marker_road(self, parent):
        marker_title = tk.Label(parent, text="标记路", font=('Arial', 14, 'bold'), bg='#D0E7FF')
        marker_title.pack(pady=(10, 2))

        self.marker_canvas = tk.Canvas(parent, bg='#D0E7FF', highlightthickness=0)
        self.marker_canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self._draw_marker_grid()
        self._update_marker_road()

    def _create_pie_chart(self, parent):
        pie_frame = tk.Frame(parent, bg='#D0E7FF')
        pie_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 8), padx=10)

        tk.Label(
            pie_frame,
            text="历史记录占比",
            font=('Arial', 14, 'bold'),
            bg='#D0E7FF',
            fg='#000000'
        ).pack(pady=(0, 8))

        content_frame = tk.Frame(pie_frame, bg='#D0E7FF')
        content_frame.pack(fill=tk.BOTH, expand=True)

        self.pie_canvas = tk.Canvas(
            content_frame,
            width=150,
            height=150,
            bg='#D0E7FF',
            highlightthickness=0
        )
        self.pie_canvas.pack(side=tk.LEFT, padx=5)

        percent_frame = tk.Frame(content_frame, bg='#D0E7FF')
        percent_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        self.percent_labels = {}
        categories = ['1', '3', '6', '12', '25', 'Special']
        for cat in categories:
            lbl = tk.Label(
                percent_frame,
                text=f"{cat}: 0.00%",
                font=('Arial', 11, 'bold'),
                bg='#D0E7FF',
                fg='black',
                anchor='w'
            )
            lbl.pack(fill=tk.X, pady=1)
            self.percent_labels[cat] = lbl

        self._update_pie_chart()

    def _update_pie_chart(self):
        if not hasattr(self, 'pie_canvas'):
            return

        counts = self.history.counts()
        total = self.history.total() or 1

        special_count = counts.get('👑', 0) + counts.get('💵', 0)
        categories = ['1', '3', '6', '12', '25', 'Special']
        values = [counts.get(c, 0) for c in categories[:-1]]
        values.append(special_count)

        colors = {
            '1': OUTCOME_COLORS['1'],
            '3': OUTCOME_COLORS['3'],
            '6': OUTCOME_COLORS['6'],
            '12': OUTCOME_COLORS['12'],
            '25': OUTCOME_COLORS['25'],
            'Special': '#F5A623'
        }

        self.pie_canvas.delete('all')
        cx, cy = 75, 75
        radius = 65

        if sum(values) == 0:
            self.pie_canvas.create_oval(
                cx - radius, cy - radius,
                cx + radius, cy + radius,
                fill='#CCCCCC',
                outline='black',
                width=2
            )
            self.pie_canvas.create_text(
                cx, cy, text="无数据",
                font=('Arial', 12), fill='#666666'
            )
        else:
            start_angle = 0
            for i, cat in enumerate(categories):
                percent = values[i] / total
                if percent == 0:
                    continue
                extent = 360 * percent
                self.pie_canvas.create_arc(
                    cx - radius, cy - radius,
                    cx + radius, cy + radius,
                    start=start_angle,
                    extent=extent,
                    fill=colors[cat],
                    outline='black',
                    width=1.5
                )
                start_angle += extent

            start_angle = 0
            for i, cat in enumerate(categories):
                percent = values[i] / total
                if percent == 0:
                    continue
                extent = 360 * percent
                mid_angle = start_angle + extent / 2
                rad = math.radians(mid_angle)
                text_r = radius * 0.75
                x = cx + text_r * math.cos(rad)
                y = cy - text_r * math.sin(rad)
                label_text = 'S' if cat == 'Special' else cat
                self.pie_canvas.create_text(
                    x, y,
                    text=label_text,
                    fill='black',
                    font=('Arial', 10, 'bold')
                )
                start_angle += extent

        for cat in categories:
            idx = categories.index(cat)
            percent = (values[idx] / total) * 100
            self.percent_labels[cat].config(text=f"{cat}: {percent:.2f}%")

    def _draw_marker_grid(self):
        self.marker_canvas.delete('all')
        rows, cols = self.marker_rows, self.marker_cols
        cell_size = 30
        padding = 0
        width = cols * (cell_size + padding) + padding
        height = rows * (cell_size + padding) + padding
        self.marker_canvas.config(width=width, height=height)

        for col in range(cols):
            for row in range(rows):
                x1 = padding + col * (cell_size + padding)
                y1 = padding + row * (cell_size + padding)
                x2 = x1 + cell_size
                y2 = y1 + cell_size
                self.marker_canvas.create_rectangle(
                    x1, y1, x2, y2,
                    outline='#888888',
                    fill='#D0E7FF'
                )

    def _update_marker_road(self):
        self._draw_marker_grid()
        rows, cols = self.marker_rows, self.marker_cols
        cell_size = 30
        padding = 0

        max_display = rows * cols
        start_idx = max(0, len(self.marker_results) - max_display)
        results_to_show = self.marker_results[start_idx:]

        for idx, result in enumerate(results_to_show):
            if idx >= max_display:
                break
            col = idx // rows
            row = idx % rows
            x1 = padding + col * (cell_size + padding)
            y1 = padding + row * (cell_size + padding)
            x2 = x1 + cell_size
            y2 = y1 + cell_size
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            radius = cell_size * 0.4

            self.marker_canvas.create_oval(
                center_x - radius, center_y - radius,
                center_x + radius, center_y + radius,
                fill=OUTCOME_COLORS.get(result, '#FFFFFF'),
                outline='#000000',
                width=2,
                tags='dot'
            )
            font = ("Segoe UI Emoji", 12, "bold") if result in ("👑", "💵") else ("Arial", 12, "bold")
            self.marker_canvas.create_text(
                center_x, center_y,
                text=result,
                fill=OUTCOME_TEXT_COLORS.get(result, 'black'),
                font=font,
                tags='dot'
            )

    def _sync_marker_from_history(self):
        raw_hist = self.history.recent_results(limit=54)
        reversed_hist = [r for r in reversed(raw_hist) if r != ""]
        self.marker_results = reversed_hist

        self.stats_counts = {k: 0 for k in OUTCOME_DISPLAY}
        for res in self.marker_results:
            if res in self.stats_counts:
                self.stats_counts[res] += 1

        self._update_stats_display()
        self._update_marker_road()

    def add_marker_result(self, result):
        self._sync_marker_from_history()
        self._update_pie_chart()

    # ------------------- 轮盘绘制 -------------------
    def _draw_wheel(self):
        self.wheel_canvas.delete("all")
        w, h = 900, 430
        cx, cy = 450, 215
        outer_r, inner_r = 174, 70

        self._draw_wheel_segments(cx, cy, outer_r, inner_r, self.current_wheel_offset)
        self.wheel_canvas.create_oval(
            cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r,
            fill="#FFFFFF", outline="#222222", width=3, tags=("wheel",)
        )

        if self.center_display_result is not None:
            symbol = self.center_display_result
            bg_color = OUTCOME_COLORS.get(symbol, "#FFFFFF")
            bg_r = inner_r - 10
            self.wheel_canvas.create_oval(
                cx - bg_r, cy - bg_r, cx + bg_r, cy + bg_r,
                fill=bg_color, outline="#000000", width=2, tags=("wheel",)
            )
            font_size = 36
            font = ("Segoe UI Emoji", font_size, "bold") if symbol in ("👑", "💵") else ("Arial", font_size, "bold")
            self.wheel_canvas.create_text(
                cx, cy, text=symbol, font=font,
                fill=OUTCOME_TEXT_COLORS.get(symbol, "black"), tags=("wheel",)
            )
        else:
            self.wheel_canvas.create_text(
                cx, cy - 6, text="幸运之轮", font=("Arial", 22, "bold"),
                fill="#000000", tags=("wheel",)
            )
            if self.round_state == "betting" and self.betting_deadline is not None:
                remaining = max(0, int(math.ceil(self.betting_deadline - time.time())))
                timer_text = f"{remaining}s"
            elif self.round_state == "spinning":
                timer_text = "开奖中..."
            else:
                timer_text = "等待开奖"
            self.wheel_timer_id = self.wheel_canvas.create_text(
                cx, cy + 24, text=timer_text, font=("Arial", 16, "bold"),
                fill="#000000", tags=("timer",)
            )

        self.wheel_canvas.create_polygon(
            cx - 16, 24, cx + 16, 24, cx, 60,
            fill="#FFFFFF", outline="#000000", width=2, tags=("pointer",)
        )
        self.wheel_canvas.tag_raise("pointer")

    def _draw_wheel_segments(self, cx, cy, outer_r, inner_r, offset_deg):
        self.wheel_canvas.delete("wheel")
        n = len(WHEEL_SEQUENCE)
        step = 360.0 / n
        for i, symbol in enumerate(WHEEL_SEQUENCE):
            start = (offset_deg + i * step) % 360.0
            end = start + step

            points = [cx, cy]
            for ang in (start, end):
                rad = math.radians(ang)
                x = cx + outer_r * math.sin(rad)
                y = cy - outer_r * math.cos(rad)
                points.extend([x, y])

            self.wheel_canvas.create_polygon(
                points,
                fill=OUTCOME_COLORS[symbol],
                outline="#444444",
                width=1,
                tags=("wheel",),
            )

            mid = (start + end) / 2.0
            rad = math.radians(mid)
            tx = cx + (outer_r * 0.84) * math.sin(rad)
            ty = cy - (outer_r * 0.84) * math.cos(rad)
            label_font = ("Segoe UI Emoji", 11, "bold") if symbol in ("👑", "💵") else ("Arial", 11, "bold")
            self.wheel_canvas.create_text(
                tx, ty,
                text=symbol,
                font=label_font,
                fill=OUTCOME_TEXT_COLORS[symbol],
                tags=("wheel",),
            )

        self.wheel_canvas.create_oval(
            cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r,
            outline="#222222", width=4, tags=("wheel",),
        )
        self.wheel_canvas.create_oval(
            cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r,
            outline="#222222", width=3, tags=("wheel",),
        )

    def _segment_angle(self):
        return 360.0 / len(WHEEL_SEQUENCE)

    # ------------------- 游戏流程 -------------------
    def _start_new_round(self):
        self.center_display_result = None
        self._draw_wheel()

        if self._countdown_job is not None:
            try:
                self.after_cancel(self._countdown_job)
            except Exception:
                pass
            self._countdown_job = None
        if self._spin_job is not None:
            try:
                self.after_cancel(self._spin_job)
            except Exception:
                pass
            self._spin_job = None

        self.round_state = "betting"
        self.current_round_result = None
        self.current_round_index = None
        self._enable_bet_buttons()
        self._enable_amount_buttons()
        self._set_control_buttons_state(tk.NORMAL)
        self._refresh_bet_button_texts()

        self.betting_deadline = time.time() + self.BETTING_SECONDS
        self._update_countdown()

    def _update_countdown(self):
        remaining = int(math.ceil(self.betting_deadline - time.time()))
        if remaining < 0:
            remaining = 0
        if hasattr(self, 'wheel_timer_id') and self.wheel_timer_id:
            self.wheel_canvas.itemconfig(self.wheel_timer_id, text=f"{remaining:02d}s")
        if remaining <= 0:
            self._countdown_job = None
            self._lock_bets_and_spin()
            return
        self._countdown_job = self.after(self.TIMER_TICK_MS, self._update_countdown)

    def _lock_bets_and_spin(self):
        self.round_state = "spinning"
        self._set_bet_buttons_state(tk.DISABLED)
        self._disable_amount_buttons()
        self._set_control_buttons_state(tk.DISABLED)
        self._start_physical_spin()

    # ------------------- 物理旋转核心 -------------------
    def _start_physical_spin(self):
        """启动物理模拟旋转：随机初速度，随机减速度"""
        self.wheel_velocity = random.uniform(450, 750)
        self.wheel_acceleration = -random.uniform(70, 125)
        self.is_spinning = True
        self._last_physics_time = time.time()
        self._physics_update()

    def _physics_update(self):
        now = time.time()
        dt = min(0.05, now - self._last_physics_time)  # 限制最大步长
        self._last_physics_time = now

        self.wheel_velocity += self.wheel_acceleration * dt
        self.wheel_angle_delta = self.wheel_velocity * dt
        self.current_wheel_offset = (self.current_wheel_offset + self.wheel_angle_delta) % 360.0

        self._draw_wheel()

        if self.wheel_velocity <= 0 and dt > 0:
            self._finish_physical_spin()
            return

        self._spin_job = self.after(int(dt * 1000), self._physics_update)

    def _finish_physical_spin(self):
        self.is_spinning = False
        self.wheel_velocity = 0.0
        self.current_wheel_offset %= 360.0
        self._draw_wheel()

        step = 360.0 / len(WHEEL_SEQUENCE)
        raw_index = ((-self.current_wheel_offset) / step - 0.5) % len(WHEEL_SEQUENCE)
        self.current_round_index = int(round(raw_index)) % len(WHEEL_SEQUENCE)
        self.current_round_result = WHEEL_SEQUENCE[self.current_round_index]

        self._finish_round(self.current_round_result)

    def _finish_round(self, result):
        payout = self._settle_bets(result)

        self.history.add_result(
            result=result,
            bet_snapshot={k: v for k, v in self.current_bets.items() if v},
            payout=payout,
            wheel_index=self.current_round_index + 1,
        )
        self.add_marker_result(result)

        self._refresh_balance_display()
        self._refresh_bet_button_texts()
        self.last_win_label.config(text=f"${int(payout)}")

        self.current_bets = {k: 0 for k in OUTCOME_DISPLAY}
        self.current_bet_label.config(text="$0")
        self.round_state = "result"
        self._disable_amount_buttons()

        self.center_display_result = result
        self._draw_wheel()

        self.after(2500, self._start_new_round)

    # ------------------- 下注相关 -------------------
    def place_bet(self, symbol: str):
        if self.round_state != "betting":
            return
        if symbol not in OUTCOME_DISPLAY:
            return
        amount = self.selected_bet_amount
        if amount <= 0:
            return

        limit = 500_000 if symbol in ("1", "3", "6", "12", "25") else 100_000
        existing = self.current_bets.get(symbol, 0)
        remaining_limit = limit - existing

        if remaining_limit <= 0:
            messagebox.showwarning("投注上限", f"{symbol} 已达到最高限红 ${limit:,}")
            return

        actual_amount = min(amount, remaining_limit)

        if self.balance < actual_amount:
            messagebox.showwarning("余额不足", f"余额不足，无法下注 ${actual_amount:,.0f}。")
            return

        self.balance -= actual_amount
        self.current_bets[symbol] += actual_amount

        self._refresh_balance_display()
        self._refresh_bet_button_texts()
        total_bet = sum(self.current_bets.values())
        self.current_bet_label.config(text=f"${total_bet:,}")

    def clear_bets(self):
        if self.round_state != "betting":
            return
        refund = sum(self.current_bets.values())
        if refund > 0:
            self.balance += refund
        self.current_bets = {k: 0 for k in OUTCOME_DISPLAY}
        self._refresh_balance_display()
        self.current_bet_label.config(text="$0")
        self._refresh_bet_button_texts()

    def clear_single_bet(self, symbol):
        if self.round_state != "betting":
            return
        amount = self.current_bets.get(symbol, 0)
        if amount > 0:
            self.balance += amount
            self.current_bets[symbol] = 0
            self._refresh_balance_display()
            total_bet = sum(self.current_bets.values())
            self.current_bet_label.config(text=f"${total_bet:,}")
            self._refresh_bet_button_texts()

    def _settle_bets(self, result: str) -> float:
        total_payout = 0.0
        for symbol, amount in self.current_bets.items():
            if amount <= 0:
                continue
            if symbol == result:
                multiplier = OUTCOME_MULTIPLIERS.get(symbol, 0)
                win_amount = amount * multiplier
                total_payout += win_amount
                self.balance += win_amount
        if self.username != "Guest":
            update_balance_in_json(self.username, self.balance)
        return total_payout

    def _refresh_bet_button_texts(self):
        for symbol, btn in self.bet_buttons.items():
            btn.config(text=f"{symbol}\n${self.current_bets[symbol]:,}")

    def _set_bet_buttons_state(self, state):
        for btn in self.bet_buttons.values():
            btn.config(state=state)

    def _enable_bet_buttons(self):
        self._set_bet_buttons_state(tk.NORMAL)

    def _disable_amount_buttons(self):
        for chip in self.chip_buttons:
            chip["canvas"].config(state=tk.DISABLED)
            chip["canvas"].unbind("<Button-1>")

    def _enable_amount_buttons(self):
        for chip in self.chip_buttons:
            chip["canvas"].config(state=tk.NORMAL)
            chip["canvas"].bind("<Button-1>", lambda e, t=chip["text"], c=chip["canvas"], cid=chip["chip_id"]: self._set_bet_amount(t, c, cid))

    def _set_control_buttons_state(self, state):
        self.deal_button.config(state=state)
        self.reset_button.config(state=state)

    def _refresh_balance_display(self):
        self.balance_label.config(text=f"余额: ${self.balance:,.2f}")
        if self.username != "Guest":
            update_balance_in_json(self.username, self.balance)

    def on_close(self):
        try:
            if self.username != "Guest":
                update_balance_in_json(self.username, self.balance)
        except Exception:
            pass
        self.destroy()

    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("幸运之轮 玩法说明")
        win.geometry("660x520")
        win.resizable(False, False)
        text = (
            "幸运之轮 玩法说明\n\n"
            "1. 每局下注时间为 20 秒。\n"
            "2. 20 秒结束后，全部下注会被锁定，轮盘开始旋转。\n"
            "3. 轮盘停止时，最上方三角指针指向的格子为中奖结果。\n"
            "4. 下注在数字格子：\n"
            "   - 下注金额 × (格子数字 + 1)\n"
            "   - 例如下注 100 在 '12'，中奖则返还 1300。\n"
            "5. 下注在 👑 或 💵：\n"
            "   - 中奖返还下注金额 × 51。\n"
            "   - 👑 和 💵 是两个不同结果，彼此不通赔。\n"
            "6. 数字格子最高限红 100,000，特殊格子最高限红 500,000。"
        )
        frm = tk.Frame(win)
        frm.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        txt = tk.Text(frm, font=("Arial", 13), wrap=tk.WORD)
        txt.insert(tk.END, text)
        txt.config(state=tk.DISABLED)
        txt.pack(fill=tk.BOTH, expand=True)
        tk.Button(win, text="关闭", command=win.destroy, font=("Arial", 12, "bold"), width=10).pack(pady=10)

    def start_game(self):
        if self.round_state == "betting":
            if self._countdown_job is not None:
                try:
                    self.after_cancel(self._countdown_job)
                except Exception:
                    pass
                self._countdown_job = None
            self._lock_bets_and_spin()


def main(initial_balance=1_000_000, username="Guest"):
    app = BigSixWheelGUI(initial_balance=initial_balance, username=username)
    app.mainloop()
    return app.balance


if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")