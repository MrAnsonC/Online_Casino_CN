import json
import math
import os
import uuid
import time
import tkinter as tk
from tkinter import messagebox, ttk

try:
    from PIL import ImageColor
except Exception:
    ImageColor = None


# =========================================================
# Constants for scaling the betting board (shrink to 75%)
# =========================================================
ORIGINAL_SCALE = 2.0
BOARD_SCALE = 1.5                     # 75% of original scale (since 1.5 / 2 = 0.75)
BOARD_W = 660
BOARD_H = 340

# =========================================================
# Paths / persistence
# =========================================================

def uuid_uniform(a: float, b: float) -> float:
    """使用 uuid4 的随机位生成 [a, b) 范围内的浮点数"""
    # uuid4 返回 128 位随机整数，取高 64 位足够了
    rand_int = uuid.uuid4().int >> 64   # 取高 64 位
    # 映射到 [0, 1) 区间
    rand_float = rand_int / (1 << 64)
    return a + (b - a) * rand_float

def project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def user_data_path() -> str:
    return os.path.join(project_root(), "saving_data.json")


def roulette_log_path() -> str:
    log_dir = os.path.join(project_root(), "A_Logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Roulette_Europe.json")      # changed to European


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
        if user.get("user_name") == username:
            user["cash"] = f"{float(new_balance):.2f}"
            found = True
            break
    if not found:
        users.append({"user_name": username, "cash": f"{float(new_balance):.2f}"})
    save_user_data(users)


# =========================================================
# Roulette rules / constants – European single zero
# =========================================================

ROULETTE_SEQUENCE = [
    "0", "32", "15", "19", "4", "21", "2", "25", "17", "34",
    "6", "27", "13", "36", "11", "30", "8", "23", "10", "5",
    "24", "16", "33", "1", "20", "14", "31", "9", "22", "18",
    "29", "7", "28", "12", "35", "3", "26",
]
assert len(ROULETTE_SEQUENCE) == 37, f"Wheel sequence must have 37 items, got {len(ROULETTE_SEQUENCE)}"

RED_NUMBERS = {
    1, 3, 5, 7, 9, 12, 14, 16, 18,
    19, 21, 23, 25, 27, 30, 32, 34, 36,
}

NUMBERS_1_TO_36 = [str(i) for i in range(1, 37)]

BET_ODDS = {
    "straight": 35,
    "split": 17,
    "street": 11,
    "corner": 8,
    "six_line": 5,
    "dozen": 2,
    "column": 2,
    "color": 1,
    "odd_even": 1,
    "high_low": 1,
    # "five_number" removed
}

OUTCOME_COLORS = {
    "0": "#188a8e",    # green
}

OUTCOME_TEXT_COLORS = {
    "0": "#ffffff",
}

for n in range(1, 37):
    s = str(n)
    if n in RED_NUMBERS:
        OUTCOME_COLORS[s] = "#ff2a23"
    else:
        OUTCOME_COLORS[s] = "#050505"
    OUTCOME_TEXT_COLORS[s] = "#ffffff"

COLOR_GROUPS = {
    "Red": {"results": {str(n) for n in RED_NUMBERS}},
    "Black": {"results": {str(n) for n in range(1, 37)} - {str(n) for n in RED_NUMBERS}},
    "Green": {"results": {"0"}},
}

ROULETTE_BET_TYPES = {
    "straight",
    "split",
    "street",
    "corner",
    "six_line",
    "dozen",
    "column",
    "color",
    "odd_even",
    "high_low",
    # "five_number" removed
}


# =========================================================
# History store
# =========================================================

class RouletteHistory:
    ORDERED_TOP_KEYS = ["Total", "Red", "Black", "Green", "Record1", "Record2"]

    RECORD1_KEY = "Record1"
    RECORD2_KEY = "Record2"
    LEGACY_RECORD_KEY = "Record"

    RECORD1_MAX = 54
    RECORD2_MAX = 2000

    def __init__(self, path: str):
        self.path = path
        self.data = self._load_or_create()
        self._reorder_and_save()

    def _default_payload(self):
        return {
            "Total": 0,
            "Red": 0,
            "Black": 0,
            "Green": 0,
            "Record1": {},
            "Record2": {},
        }

    def _clean_record(self, record_obj):
        """
        只保留符合 xx_Data 格式的资料，并把值统一成：
        {"result": "...", "color": "..."}
        """
        if not isinstance(record_obj, dict):
            return {}

        cleaned = {}
        for key, entry in record_obj.items():
            if not isinstance(key, str) or not key.endswith("_Data"):
                continue

            if isinstance(entry, dict):
                cleaned[key] = {
                    "result": str(entry.get("result", "")),
                    "color": str(entry.get("color", "")),
                }
            else:
                cleaned[key] = {"result": "", "color": ""}
        return cleaned

    def _load_or_create(self):
        ensure_json_file(self.path, self._default_payload())
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return self._default_payload()
        except Exception:
            return self._default_payload()

        payload = self._default_payload()
        for key in ("Total", "Red", "Black", "Green"):
            try:
                payload[key] = int(data.get(key, 0))
            except Exception:
                payload[key] = 0

        # 兼容旧版：旧的 Record 自动并入 Record1
        legacy_record1 = data.get(self.RECORD1_KEY)
        if not isinstance(legacy_record1, dict):
            legacy_record1 = data.get(self.LEGACY_RECORD_KEY, {})
        payload[self.RECORD1_KEY] = self._clean_record(legacy_record1)
        payload[self.RECORD2_KEY] = self._clean_record(data.get(self.RECORD2_KEY, {}))
        return payload

    def _reorder_and_save(self):
        new_data = {}
        for key in self.ORDERED_TOP_KEYS:
            if key in self.data:
                new_data[key] = self.data[key]
        for key, value in self.data.items():
            if key not in new_data:
                new_data[key] = value
        self.data = new_data
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    def _record_to_ordered_list(self, record_name: str, limit: int):
        record = self.data.get(record_name, {})
        ordered = []

        for i in range(1, limit + 1):
            key = f"{i:02d}_Data"
            entry = record.get(key)
            if isinstance(entry, dict):
                ordered.append({
                    "result": str(entry.get("result", "")),
                    "color": str(entry.get("color", "")),
                })
            else:
                ordered.append({"result": "", "color": ""})
        return ordered

    def _ordered_list_to_record(self, entries):
        new_record = {}
        for idx, entry in enumerate(entries, start=1):
            new_record[f"{idx:02d}_Data"] = {
                "result": str(entry.get("result", "")),
                "color": str(entry.get("color", "")),
            }
        return new_record

    def recent_results(self, limit: int = 54, record_name: str = "Record1"):
        record_key = record_name
        if record_key not in self.data:
            record_key = self.LEGACY_RECORD_KEY if self.LEGACY_RECORD_KEY in self.data else self.RECORD1_KEY

        return self._record_to_ordered_list(record_key, limit)

    def recent_results2(self, limit: int = 500):
        return self._record_to_ordered_list(self.RECORD2_KEY, limit)

    def _append_result_to_record1(self, result: str, color: str):
        # 获取当前 Record1 的所有条目（长度为 54，空位为 {"result":"","color":""}）
        existing = self._record_to_ordered_list(self.RECORD1_KEY, self.RECORD1_MAX)

        # 统计实际非空记录的数量
        actual_count = sum(1 for entry in existing if entry["result"])

        # 只有当已经达到 54 条记录，需要添加第 55 条时，才删除最后 6 条（49_Data ~ 54_Data）
        if actual_count >= self.RECORD1_MAX:
            # 保留前 48 条，丢弃索引 48~53（即 49_Data ~ 54_Data）
            existing = existing[:48]

        # 将新结果插入头部，然后拼接上所有非空旧记录（已过滤空位）
        new_entries = [{"result": result, "color": color}] + [e for e in existing if e["result"]]

        # 确保总数不超过 RECORD1_MAX（54）
        new_entries = new_entries[:self.RECORD1_MAX]

        # 写回 data
        self.data[self.RECORD1_KEY] = self._ordered_list_to_record(new_entries)

    def _append_result_to_record2(self, result: str, color: str):
        existing = self._record_to_ordered_list(self.RECORD2_KEY, self.RECORD2_MAX)
        new_entries = [{"result": result, "color": color}] + [e for e in existing if e["result"]]
        new_entries = new_entries[:self.RECORD2_MAX]
        self.data[self.RECORD2_KEY] = self._ordered_list_to_record(new_entries)

    def add_result(self, result: str):
        color = roulette_color(result)
        self.data = self._load_or_create()

        self._append_result_to_record1(result, color)
        self._append_result_to_record2(result, color)

        self.data["Total"] = int(self.data.get("Total", 0)) + 1
        if color == "Red":
            self.data["Red"] = int(self.data.get("Red", 0)) + 1
        elif color == "Black":
            self.data["Black"] = int(self.data.get("Black", 0)) + 1
        else:
            self.data["Green"] = int(self.data.get("Green", 0)) + 1

        self._reorder_and_save()

    def counts(self):
        return {
            "Red": int(self.data.get("Red", 0)),
            "Black": int(self.data.get("Black", 0)),
            "Green": int(self.data.get("Green", 0)),
        }

    def total(self):
        return int(self.data.get("Total", 0))


# =========================================================
# Board geometry / drawing (scaled)
# =========================================================

ROOT_BG = "#1B3D31"
CYAN = "#007502"
TEXT = "#ffffff"
RED = "#ff2a23"
BLACK = "#050505"
DARK_BLUE = "#173f66"
TEAL = "#188a8e"

def draw_center_text(canvas, x1, y1, x2, y2, text, font=("Arial", 12, "bold"), angle=0, fill=TEXT):
    canvas.create_text(
        (x1 + x2) / 2,
        (y1 + y2) / 2,
        text=text,
        fill=fill,
        font=font,
        angle=angle
    )


def draw_cell(canvas, x1, y1, x2, y2, fill, text=None, text_font=("Arial", 12, "bold"),
              text_angle=0, text_fill=TEXT, outline=CYAN, width=2):
    canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=width)
    if text is not None:
        draw_center_text(canvas, x1, y1, x2, y2, text, font=text_font, angle=text_angle, fill=text_fill)


def get_board_layout(scale=BOARD_SCALE):
    x0 = 12 * scale
    y0 = 17 * scale
    num_w = 29 * scale
    num_h = 38 * scale
    zero_w = num_w 
    zero_h = (3 * num_h) // 2          # 1.5 * num_h (for half-height cells)
    # For European: zero area will be 2 * zero_h high (3 * num_h)
    dozen_h = 39 * scale
    outer_h = 38 * scale
    col_w = 14 * scale + 20

    zero_x1 = x0
    zero_x2 = zero_x1 + zero_w
    grid_x1 = zero_x2
    grid_x2 = grid_x1 + 12 * num_w
    col_x1 = grid_x2
    col_x2 = col_x1 + col_w

    rows = [
        [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36],
        [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35],
        [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34],
    ]
    return {
        "x0": x0,
        "y0": y0,
        "num_w": num_w,
        "num_h": num_h,
        "zero_w": zero_w,
        "zero_h": zero_h,
        "dozen_h": dozen_h,
        "outer_h": outer_h,
        "col_w": col_w,
        "zero_x1": zero_x1,
        "zero_x2": zero_x2,
        "grid_x1": grid_x1,
        "grid_x2": grid_x2,
        "col_x1": col_x1,
        "col_x2": col_x2,
        "rows": rows,
    }


def draw_roulette_static(canvas, scale=BOARD_SCALE):
    canvas.delete("all")
    canvas.configure(bg=ROOT_BG)

    layout = get_board_layout(scale)
    x0 = layout["x0"]
    y0 = layout["y0"]
    num_w = layout["num_w"]
    num_h = layout["num_h"]
    zero_w = layout["zero_w"]
    zero_h = layout["zero_h"]
    dozen_h = layout["dozen_h"]
    outer_h = layout["outer_h"]
    col_w = layout["col_w"]
    zero_x1 = layout["zero_x1"]
    zero_x2 = layout["zero_x2"]
    grid_x1 = layout["grid_x1"]
    col_x1 = layout["col_x1"]
    col_x2 = layout["col_x2"]
    rows = layout["rows"]

    dozen_y1 = y0 + 3 * num_h
    dozen_y2 = dozen_y1 + dozen_h
    outer_y1 = dozen_y2
    outer_y2 = outer_y1 + outer_h

    # European single zero
    zero_height = 2 * zero_h
    canvas.create_rectangle(
        int(zero_x1), int(y0),
        int(zero_x2), int(y0 + zero_height),
        fill=TEAL,
        outline=CYAN,
        width=1
    )
    canvas.create_text(
        int(zero_x1 + zero_w / 2),
        int(y0 + zero_height / 2),
        text="0",
        fill=TEXT,
        font=("Arial", int(16 * scale // 2), "bold"),
        angle=90
    )

    for r in range(3):
        y1 = y0 + r * num_h
        y2 = y1 + num_h
        for c in range(12):
            x1 = grid_x1 + c * num_w
            x2 = x1 + num_w
            n = rows[r][c]
            fill = RED if n in RED_NUMBERS else BLACK
            canvas.create_rectangle(
                int(x1), int(y1), int(x2), int(y2),
                fill=fill, outline=CYAN, width=2
            )
            canvas.create_text(
                int((x1 + x2) / 2),
                int((y1 + y2) / 2),
                text=str(n),
                fill=TEXT,
                font=("Arial", int(13 * scale // 2), "bold"),
                angle=90
            )

    for r in range(3):
        y1 = y0 + r * num_h
        y2 = y1 + num_h
        draw_cell(
            canvas,
            int(col_x1), int(y1), int(col_x2), int(y2),
            fill=DARK_BLUE,
            text="2:1",
            text_font=("Arial", 11, "bold"),
            text_angle=90,
            outline=CYAN
        )

    dozen_w = 4 * num_w
    draw_cell(
        canvas,
        int(grid_x1), int(dozen_y1), int(grid_x1 + dozen_w), int(dozen_y2),
        fill=DARK_BLUE, text="1st 12",
        text_font=("Arial", int(14 * scale // 2), "bold")
    )
    draw_cell(
        canvas,
        int(grid_x1 + dozen_w), int(dozen_y1), int(grid_x1 + 2 * dozen_w), int(dozen_y2),
        fill=DARK_BLUE, text="2nd 12",
        text_font=("Arial", int(14 * scale // 2), "bold")
    )
    draw_cell(
        canvas,
        int(grid_x1 + 2 * dozen_w), int(dozen_y1), int(grid_x1 + 3 * dozen_w), int(dozen_y2),
        fill=DARK_BLUE, text="3rd 12",
        text_font=("Arial", int(14 * scale // 2), "bold")
    )

    outer_y1 = dozen_y2
    outer_y2 = outer_y1 + outer_h

    seg_w = dozen_w // 2
    x = grid_x1
    draw_cell(canvas, int(x), int(outer_y1), int(x + seg_w), int(outer_y2),
              fill=DARK_BLUE, text="1 to 18", text_font=("Arial", int(14 * scale // 2), "bold"))
    x += seg_w
    draw_cell(canvas, int(x), int(outer_y1), int(x + seg_w), int(outer_y2),
              fill=DARK_BLUE, text="EVEN", text_font=("Arial", int(14 * scale // 2), "bold"))
    x += seg_w
    draw_cell(canvas, int(x), int(outer_y1), int(x + seg_w), int(outer_y2),
              fill=RED, text="RED", text_font=("Arial", int(14 * scale // 2), "bold"))
    x += seg_w
    draw_cell(canvas, int(x), int(outer_y1), int(x + seg_w), int(outer_y2),
              fill=BLACK, text="BLACK", text_font=("Arial", int(14 * scale // 2), "bold"))
    x += seg_w
    draw_cell(canvas, int(x), int(outer_y1), int(x + seg_w), int(outer_y2),
              fill=DARK_BLUE, text="ODD", text_font=("Arial", int(14 * scale // 2), "bold"))
    x += seg_w
    draw_cell(canvas, int(x), int(outer_y1), int(x + seg_w), int(outer_y2),
              fill=DARK_BLUE, text="19 to 36", text_font=("Arial", int(14 * scale // 2), "bold"))

    # Street bet lines: 12 个横线下注位
    street_y = int(round(dozen_y1))
    for col in range(12):
        x1 = int(round(grid_x1 + col * num_w))
        x2 = int(round(x1 + num_w))
        canvas.create_line(
            x1 + 2, street_y, x2 - 2, street_y,
            fill="#33624b",
            width=4,
            capstyle=tk.ROUND
        )


def roulette_color(result: str) -> str:
    if result == "0":
        return "Green"
    try:
        n = int(result)
    except Exception:
        return "Green"
    return "Red" if n in RED_NUMBERS else "Black"


# =========================================================
# Roulette board interaction (geometry with scaling)
# =========================================================


class RouletteBoardGeometry:
    def __init__(self, scale=BOARD_SCALE):
        self.scale = scale
        layout = get_board_layout(scale)

        self.x0 = layout["x0"]
        self.y0 = layout["y0"]
        self.num_w = layout["num_w"]
        self.num_h = layout["num_h"]
        self.zero_w = layout["zero_w"]
        self.zero_h = layout["zero_h"]
        self.dozen_h = layout["dozen_h"]
        self.outer_h = layout["outer_h"]
        self.col_w = layout["col_w"]

        self.zero_x1 = layout["zero_x1"]
        self.zero_x2 = layout["zero_x2"]
        self.grid_x1 = layout["grid_x1"]
        self.grid_x2 = layout["grid_x2"]
        self.col_x1 = layout["col_x1"]
        self.col_x2 = layout["col_x2"]

        self.grid_y1 = self.y0
        self.grid_y2 = self.y0 + 3 * self.num_h

        self.dozen_y1 = self.grid_y2
        self.dozen_y2 = self.dozen_y1 + self.dozen_h
        self.outer_y1 = self.dozen_y2
        self.outer_y2 = self.outer_y1 + self.outer_h

        self.rows = layout["rows"]
        self.number_to_rc = {}
        for r in range(3):
            for c in range(12):
                self.number_to_rc[self.rows[r][c]] = (r, c)

    def cell_bounds(self, row: int, col: int):
        x1 = self.grid_x1 + col * self.num_w
        y1 = self.grid_y1 + row * self.num_h
        return x1, y1, x1 + self.num_w, y1 + self.num_h

    def center_of_cell(self, row: int, col: int):
        x1, y1, x2, y2 = self.cell_bounds(row, col)
        return (x1 + x2) / 2, (y1 + y2) / 2

    def get_number(self, row: int, col: int) -> str:
        return str(self.rows[row][col])

    def column_numbers(self, col: int):
        return [str(self.rows[r][col]) for r in range(3)]

    def doze_numbers(self, idx: int):
        start = idx * 12 + 1
        return [str(n) for n in range(start, start + 12)]

    def column_bet_numbers(self, idx: int):
        col_map = {0: 0, 1: 1, 2: 2}
        c = col_map[idx]
        return self.column_numbers(c)

    def color_bet_numbers(self, bet: str):
        if bet == "Red":
            return [str(n) for n in sorted(RED_NUMBERS)]
        if bet == "Black":
            return [str(n) for n in range(1, 37) if n not in RED_NUMBERS]
        return []

    def odd_even_numbers(self, bet: str):
        if bet == "Odd":
            return [str(n) for n in range(1, 37) if n % 2 == 1]
        if bet == "Even":
            return [str(n) for n in range(1, 37) if n % 2 == 0]
        return []

    def high_low_numbers(self, bet: str):
        if bet == "1-18":
            return [str(n) for n in range(1, 19)]
        if bet == "19-36":
            return [str(n) for n in range(19, 37)]
        return []


class RouletteGameGUI(tk.Tk):
    BETTING_SECONDS = 30  #时间
    TIMER_TICK_MS = 250

    def __init__(self, initial_balance=1_000_000, username="Guest"):
        super().__init__()
        self.title("欧式轮盘")        # changed title
        self.geometry("1230x770+20+10")
        self.resizable(False, False)
        self.configure(bg=ROOT_BG)

        self.username = username
        self.balance = float(load_balance(username, float(initial_balance)))
        self.history = RouletteHistory(roulette_log_path())

        self.geometry_model = RouletteBoardGeometry(scale=BOARD_SCALE)
        self.marker_results = []
        self.marker_rows = 6
        self.marker_cols = 9

        self.selected_bet_amount = 25
        self.selected_chip_color = "#ffffff"
        self.selected_chip = None
        self.chip_buttons = []

        self.round_state = "betting"
        self.betting_deadline = None
        self._countdown_job = None
        self._spin_job = None

        self.last_bets = {}
        self.last_bet_colors = {}
        self.timer_paused = False
        self.paused_remaining = 0

        self.current_wheel_offset = 0.0
        self.wheel_velocity = 0.0
        self.wheel_acceleration = 0.0
        self._last_physics_time = None
        self.is_spinning = False

        self.pointer_angle = 0.0
        self.pointer_velocity = 0.0
        self.pointer_acceleration = 0.0
        self.is_pointer_spinning = False

        # 用于存储最后一局的开奖物理数据
        self.last_spin_data = None
        # 结果弹窗防重复
        self.detail_window = None

        self.current_round_result = None
        self.current_round_index = None
        self.center_display_result = None
        self.wheel_timer_id = None

        self.current_bets = {}
        self.current_bet_colors = {}
        self.bet_spots = self._build_bet_spots()
        self.placed_chip_items = {}
        self.result_chip_display = {}
        self._result_flash_job = None
        self._result_flash_state = False
        self._result_flash_spot_ids = set()

        self.distribution_display_count = 50   # 默认分析最近50局
        self.distribution_frame = None         # 分布面板主框架
        self.distribution_labels = {}          # 存储各统计标签的引用

        self._build_ui()
        self._sync_marker_from_history()
        self._start_new_round()

        self.focus_force()                         # 确保窗口获得焦点
        self.bind("<Return>", lambda event: self.start_game())
        self.bind("<KP_Enter>", lambda event: self.start_game())

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):
        main = tk.Frame(self, bg=ROOT_BG)
        main.pack(fill=tk.BOTH, expand=True)

        # 左右整体重新分配宽度，给右侧统计区留更多空间
        left_frame = tk.Frame(main, bg=ROOT_BG, width=650)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=0)
        left_frame.pack_propagate(False)

        right_frame = tk.Frame(main, bg=ROOT_BG, width=560)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 8), pady=0)
        right_frame.pack_propagate(False)

        self._build_left_side(left_frame)
        self._build_right_side(right_frame)

    def _build_left_side(self, parent):
        top_frame = tk.Frame(parent, bg=ROOT_BG)
        top_frame.pack(fill=tk.X, padx=8, pady=0)

        self.wheel_canvas = tk.Canvas(
            top_frame,
            width=910,
            height=450,
            bg=ROOT_BG,
            highlightthickness=0,
            bd=0
        )
        self.wheel_canvas.pack(fill=tk.X)

        betting_area = tk.Frame(parent, bg=ROOT_BG)
        betting_area.pack(fill=tk.BOTH, expand=True, padx=8, pady=0)

        betting_left = tk.Frame(betting_area, bg=ROOT_BG)
        betting_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._populate_betting_area(betting_left)

    def _populate_betting_area(self, parent):
        self.board_canvas = tk.Canvas(
            parent,
            width=BOARD_W,
            height=BOARD_H,
            highlightthickness=0,
            bd=0,
            bg=ROOT_BG
        )
        self.board_canvas.pack(anchor='n')
        draw_roulette_static(self.board_canvas, scale=BOARD_SCALE)

        # 添加帮助按钮
        self._add_help_button_on_board()

        self.board_canvas.bind("<Button-1>", self.on_board_click)
        self.board_canvas.bind("<Button-3>", self.on_board_right_click)

    def _add_help_button_on_board(self):
        """在棋盘上0格子下方、1-18格子左侧添加一个帮助按钮，鼠标悬停时显示手型光标"""
        if not hasattr(self, "board_canvas"):
            return

        g = self.geometry_model
        zero_bottom_y = g.y0 + 2 * g.zero_h
        outer_y1 = g.outer_y1
        btn_y1 = zero_bottom_y + 5
        btn_y2 = outer_y1 - 5
        if btn_y2 - btn_y1 < 20:
            btn_y1 = zero_bottom_y - 20
            btn_y2 = zero_bottom_y - 2

        btn_width = (g.zero_x2 - g.zero_x1) - 8
        btn_x1 = g.zero_x1 + 4
        btn_x2 = btn_x1 + btn_width

        cx = (btn_x1 + btn_x2) / 2
        cy = (btn_y1 + btn_y2) / 2
        radius = min((btn_x2 - btn_x1) / 2, (btn_y2 - btn_y1) / 2) * 0.7

        # 删除旧的按钮（避免重复）
        self.board_canvas.delete("help_button")

        # 绘制按钮圆底
        self.board_canvas.create_oval(
            cx - radius, cy - radius,
            cx + radius, cy + radius,
            fill="#F5E6B8",
            outline="#D4AF37",
            width=2,
            tags="help_button"
        )
        # 绘制问号
        self.board_canvas.create_text(
            cx, cy,
            text="?",
            font=("Arial", int(radius * 1.2), "bold"),
            fill="#2A1B08",
            tags="help_button"
        )

        # 绑定鼠标进入/离开事件，实现手型光标
        self.board_canvas.tag_bind("help_button", "<Enter>", self._on_help_enter)
        self.board_canvas.tag_bind("help_button", "<Leave>", self._on_help_leave)

        # 绑定点击事件
        self.board_canvas.tag_bind("help_button", "<Button-1>", lambda e: self.show_game_instructions())

    def _on_help_enter(self, event):
        """鼠标进入帮助按钮区域时，将画布光标改为手型"""
        if hasattr(self, "board_canvas"):
            self.board_canvas.config(cursor="hand2")

    def _on_help_leave(self, event):
        """鼠标离开帮助按钮区域时，恢复默认光标"""
        if hasattr(self, "board_canvas"):
            self.board_canvas.config(cursor="")

    def _store_current_bets_as_last(self):
        """将当前下注数据存储为“上一局下注”，只有非空时才存储"""
        if self.current_bets:
            self.last_bets = self.current_bets.copy()
            self.last_bet_colors = self.current_bet_colors.copy()
            # 更新按钮状态
        else:
            # 如果当前没有下注，清空之前存储的数据，使按钮不可用
            pass
        self._update_repeat_button_state()

    def _update_repeat_button_state(self):
        """
        根据存储的上一局数据和当前余额，更新重复下注按钮的可用性。
        注意：如果当前不在投注阶段，按钮应保持禁用（由 _set_control_buttons_state 控制）。
        """
        if self.round_state != "betting":
            return  # 非投注阶段，按钮已被禁用，无需额外处理
        if not self.last_bets:
            self.repeat_last_btn.config(state=tk.DISABLED)
            return
        total_last = sum(self.last_bets.values())
        if total_last > self.balance:
            self.repeat_last_btn.config(state=tk.DISABLED)
        else:
            self.repeat_last_btn.config(state=tk.NORMAL)

    def _repeat_last_bet(self):
        """重复上一局的下注（复制到当前局）"""
        if self.round_state != "betting":
            messagebox.showwarning("提示", "只能在投注阶段重复上局下注")
            return
        if not self.last_bets:
            messagebox.showwarning("提示", "没有上一局下注记录")
            return
        total_last = sum(self.last_bets.values())
        if total_last > self.balance:
            messagebox.showwarning("余额不足", f"重复上局下注需要 ${total_last:,.0f}，余额不足")
            return

        # 清除当前下注
        self.clear_bets()
        # 复制上局下注
        for spot_id, amount in self.last_bets.items():
            spot = self._find_spot_by_id(spot_id)
            if not spot:
                continue
            limit = self._bet_limit_for_spot(spot)
            existing = self.current_bets.get(spot_id, 0)
            remaining_limit = limit - existing
            actual_amount = min(amount, remaining_limit)
            if actual_amount <= 0:
                continue
            if self.balance < actual_amount:
                # 余额不足时终止后续复制
                break
            self.balance -= actual_amount
            self.current_bets[spot_id] = existing + actual_amount
            self.current_bet_colors[spot_id] = self._chip_fill_color_for_amount(self.current_bets[spot_id])

        self._refresh_balance_display()
        self._refresh_bet_totals()
        self._repaint_all_chips()

        total_bet = sum(self.current_bets.values())
        self.current_chip_label.config(text=f"本局下注金额: ${total_bet:,}")

    def _toggle_pause_timer(self):
        """暂停/继续倒计时"""
        if self.round_state != "betting":
            return

        if not self.timer_paused:
            # 暂停倒计时
            if self._countdown_job is not None:
                try:
                    self.after_cancel(self._countdown_job)
                except Exception:
                    pass
                self._countdown_job = None
            # 计算剩余时间
            self.paused_remaining = max(0, self.betting_deadline - time.time())
            self.timer_paused = True
            self.pause_timer_btn.config(text="开始倒计时", bg="#4A90E2")
            # 显示暂停剩余时间
            if hasattr(self, "wheel_timer_id") and self.wheel_timer_id:
                try:
                    self.wheel_canvas.itemconfig(self.wheel_timer_id, text=f"{int(self.paused_remaining)}s (暂停)")
                except Exception:
                    pass
        else:
            # 继续倒计时
            if self.paused_remaining <= 0:
                # 如果剩余时间为0，直接结束下注
                self._lock_bets_and_spin()
                return
            # 重新设置截止时间
            self.betting_deadline = time.time() + self.paused_remaining
            self.timer_paused = False
            self.pause_timer_btn.config(text="暂停倒计时", bg="#F5A623")
            # 重新启动倒计时更新
            self._update_countdown()

    def _populate_chips(self, parent):
        panel_bg = "#F2E6C9"
        header_bg = "#D8B46A"

        panel = tk.Frame(parent, bg=ROOT_BG, width=240, height=449)
        panel.pack(fill=tk.Y, expand=False, pady=(0, 5))
        panel.pack_propagate(False)

        card = tk.Frame(panel, bg=panel_bg, bd=1, relief=tk.SOLID, highlightthickness=0)
        card.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            card,
            text="筹码",
            font=("Arial", 15, "bold"),
            bg=header_bg,
            fg="#2A1B08",
            pady=8
        ).pack(fill=tk.X)

        chips_frame = tk.Frame(card, bg=panel_bg)
        chips_frame.pack(pady=16, padx=6)

        chips = [
            ("1", "#ffffff"),
            ("5", "#9e9e9e"),
            ("10", "#0000ff"),
            ("25", "#00ff00"),
            ("100", "#A8ECFF"),
            ("500", "#FF7DDA"),
        ]

        for i in range(0, len(chips), 3):
            row_frame = tk.Frame(chips_frame, bg=panel_bg)
            row_frame.pack(pady=5)
            for text, bg_color in chips[i:i + 3]:
                canvas = self._create_chip_button(row_frame, text, bg_color)
                canvas.pack(side=tk.LEFT, padx=5)

        self.current_chip_label = tk.Label(
            card,
            text="筹码: $25",
            font=("Arial", 14, "bold"),
            bg=panel_bg,
            fg="black"
        )
        self.current_chip_label.pack(pady=(3, 2))

        self.balance_label_side = tk.Label(
            card,
            text=f"余额: ${self.balance:,.2f}",
            font=("Arial", 13, "bold"),
            bg=panel_bg,
            fg="black"
        )
        self.balance_label_side.pack(pady=(0, 10))

        self._set_default_chip()

        btn_frame = tk.Frame(card, bg=panel_bg)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 6))

        # 清除下注按钮
        self.reset_button = tk.Button(
            btn_frame,
            text="清除下注",
            command=self.clear_bets,
            bg="#C94A4A",
            fg="white",
            activebackground="#B73C3C",
            activeforeground="white",
            font=("微软雅黑", 14, "bold"),
            relief=tk.RAISED,      # 3D凸起效果
            bd=3,
            cursor="hand2"
        )
        self.reset_button.pack(side=tk.TOP, fill=tk.X, pady=4)

        # 两个按钮水平排列
        button_row = tk.Frame(btn_frame, bg=panel_bg)
        button_row.pack(fill=tk.X, pady=4)

        # 重复上局下注按钮
        self.repeat_last_btn = tk.Button(
            button_row,
            text="重复上局下注",
            command=self._repeat_last_bet,
            bg="#4A90E2",
            fg="white",
            activebackground="#3A7BC8",
            activeforeground="white",
            font=("微软雅黑", 12, "bold"),
            relief=tk.RAISED,
            bd=3,
            state=tk.DISABLED
        )
        self.repeat_last_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        # 暂停/开始倒计时按钮
        self.pause_timer_btn = tk.Button(
            button_row,
            text="暂停倒计时",
            command=self._toggle_pause_timer,
            bg="#F5A623",
            fg="white",
            activebackground="#E09512",
            activeforeground="white",
            font=("微软雅黑", 12, "bold"),
            relief=tk.RAISED,
            bd=3,
            cursor="hand2"
        )
        self.pause_timer_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(2, 0))

        # 开始游戏按钮
        self.deal_button = tk.Button(
            btn_frame,
            text="开始游戏 (Enter)",
            command=self.start_game,
            bg="#D8B46A",
            fg="#2A1B08",
            activebackground="#C8A455",
            activeforeground="#2A1B08",
            font=("微软雅黑", 14, "bold"),
            relief=tk.RAISED,
            bd=3,
            cursor="hand2"
        )
        self.deal_button.pack(side=tk.TOP, fill=tk.X, pady=4)

    def _create_chip_button(self, parent, text, bg_color):
        size = 60
        canvas = tk.Canvas(
            parent,
            width=size,
            height=size,
            highlightthickness=0,
            bd=0,
            bg="#F2E6C9"
        )
        chip_id = canvas.create_oval(2, 2, size - 2, size - 2, fill=bg_color, outline="", width=0)

        try:
            if ImageColor is not None:
                rgb = ImageColor.getrgb(bg_color)
                luminance = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
                text_color = "white" if luminance < 140 else "black"
            else:
                text_color = "black"
        except Exception:
            text_color = "black"

        canvas.create_text(size / 2, size / 2, text=text, fill=text_color, font=("Arial", 16, "bold"))
        canvas.bind("<Button-1>", lambda e, t=text, c=canvas, cid=chip_id, bg=bg_color: self._set_bet_amount(t, c, cid, bg))
        self.chip_buttons.append({"canvas": canvas, "chip_id": chip_id, "text": text, "bg_color": bg_color})
        return canvas


    def _set_bet_amount(self, chip_text, clicked_canvas, clicked_chip_id, bg_color=None):
        for chip in self.chip_buttons:
            chip["canvas"].itemconfig(chip["chip_id"], outline="", width=0)
            chip["canvas"].delete("glow")
        clicked_canvas.itemconfig(clicked_chip_id, outline="yellow", width=4)
        self.selected_chip = next((c for c in self.chip_buttons if c["canvas"] == clicked_canvas), None)
        if bg_color is None and self.selected_chip:
            bg_color = self.selected_chip.get("bg_color", "#ffffff")
        self.selected_chip_color = bg_color or "#ffffff"

        # chip_text is like "1","5","10","25","100","500"
        amount = int(chip_text)
        self.selected_bet_amount = amount
        self.current_chip_label.config(text=f"筹码: ${amount:,}")

    def _set_default_chip(self):
        # default to chip "25"
        for chip in self.chip_buttons:
            if chip["text"] == "25":
                chip["canvas"].itemconfig(chip["chip_id"], outline="yellow", width=4)
                self.selected_chip = chip
                self.selected_chip_color = chip.get("bg_color", "#ffffff")
                self.selected_bet_amount = 25
                self.current_chip_label.config(text="筹码: $25")
                break

    # =====================================================
    # Right side: marker road + history proportion
    # =====================================================
    def _build_right_side(self, parent):
        root = tk.Frame(parent, bg=ROOT_BG)
        root.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=0, minsize=240)
        root.grid_columnconfigure(1, weight=1, minsize=300)

        chip_frame = tk.Frame(root, bg=ROOT_BG, width=240)
        chip_frame.grid(row=0, column=0, sticky="ns", padx=0, pady=0)
        chip_frame.grid_propagate(False)

        # 饼图放在筹码区上方
        self._create_pie_chart(chip_frame)

        # 筹码区（包含“筹码”面板和按钮）
        self._populate_chips(chip_frame)

        stats_frame = tk.Frame(root, bg=ROOT_BG)
        stats_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

        self._create_marker_road(stats_frame)
        self._create_distribution_panel(stats_frame)
        self._create_hot_cold_panel(stats_frame)

    def _create_marker_road(self, parent):
        card_bg = "#F2E6C9"
        header_bg = "#D8B46A"
        title_fg = "#2A1B08"

        outer = tk.Frame(parent, bg=ROOT_BG)
        outer.pack(fill=tk.X, pady=(8, 0))

        card = tk.Frame(outer, bg=card_bg, bd=1, relief=tk.SOLID, highlightthickness=0)
        card.pack(fill=tk.X)

        title_bar = tk.Frame(card, bg=header_bg)
        title_bar.pack(fill=tk.X)

        tk.Label(
            title_bar,
            text="标记路",
            font=("Arial", 15, "bold"),
            bg=header_bg,
            fg=title_fg,
            pady=5
        ).pack()

        content = tk.Frame(card, bg=card_bg)
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=(8, 10))

        self.marker_canvas = tk.Canvas(
            content,
            bg=card_bg,
            highlightthickness=0,
            bd=0
        )
        self.marker_canvas.pack(fill=tk.BOTH, expand=True)

        self._draw_marker_grid()
        self._update_marker_road()


    def _update_distribution(self):
        """从 Record2 读取最近 N 条结果，更新：
        1) 小/0/大
        2) 单/0/双
        3) 红/绿/黑   （新增）
        """
        if not hasattr(self, 'history'):
            return

        all_results = self.history.recent_results2(limit=2000)
        if not all_results:
            return

        n = min(self.distribution_display_count, len(all_results))
        recent = all_results[:n] if n > 0 else []

        # 统计第一组（小/0/大）
        small_cnt = big_cnt = zero_cnt = 0
        # 第二组（单/0/双）
        odd_cnt = even_cnt = 0   # zero_cnt 共用
        # 第三组（红/绿/黑）
        red_cnt = green_cnt = black_cnt = 0

        for entry in recent:
            result = entry.get("result", "")
            if result == "0":
                zero_cnt += 1
                green_cnt += 1      # 绿色（0）
            else:
                try:
                    num = int(result)
                    # 第一组
                    if 1 <= num <= 18:
                        small_cnt += 1
                    elif 19 <= num <= 36:
                        big_cnt += 1
                    # 第二组
                    if num % 2 == 1:
                        odd_cnt += 1
                    else:
                        even_cnt += 1
                    # 第三组：红/黑
                    if num in RED_NUMBERS:
                        red_cnt += 1
                    else:
                        black_cnt += 1
                except ValueError:
                    pass

        total = n
        if total == 0:
            return

        # 计算百分比
        small_pct = (small_cnt / total) * 100
        big_pct   = (big_cnt / total) * 100
        zero_pct  = (zero_cnt / total) * 100
        odd_pct   = (odd_cnt / total) * 100
        even_pct  = (even_cnt / total) * 100
        red_pct   = (red_cnt / total) * 100
        green_pct = (green_cnt / total) * 100
        black_pct = (black_cnt / total) * 100

        total_width = 235      # 进度条总宽度
        height = 30
        min_zero_width = 30    # 0 最小宽度

        # ========== 第一组：小 / 0 / 大 ==========
        small_w = int(total_width * small_pct / 100)
        zero_w  = int(total_width * zero_pct / 100)
        big_w   = total_width - small_w - zero_w

        if zero_cnt > 0 and zero_w < min_zero_width:
            needed = min_zero_width - zero_w
            if big_w >= needed // 2 and small_w >= needed - needed // 2:
                big_w -= needed // 2
                small_w -= needed - (needed // 2)
            elif big_w >= needed:
                big_w -= needed
            elif small_w >= needed:
                small_w -= needed
            else:
                total_available = big_w + small_w
                if total_available > 0:
                    big_w -= int(needed * big_w / total_available)
                    small_w -= needed - int(needed * big_w / total_available)
            zero_w = min_zero_width

        small_w = max(small_w, 8 if small_cnt > 0 else 0)
        big_w   = max(big_w,   8 if big_cnt   > 0 else 0)
        if small_w + zero_w + big_w != total_width:
            diff = total_width - (small_w + zero_w + big_w)
            if diff != 0:
                if big_cnt > 0:
                    big_w += diff
                elif small_cnt > 0:
                    small_w += diff
                else:
                    zero_w += diff

        self.small_progress.place(x=0, y=0, width=small_w, height=height)
        self.zero_progress1.place(x=small_w, y=0, width=zero_w, height=height)
        self.big_progress.place(x=small_w + zero_w, y=0, width=big_w, height=height)

        if self.distribution_display_count in [50, 100]:
            sp_display = f"{int(round(small_pct))}" if small_pct > 0 else "0"
            zp_display = f"{int(round(zero_pct))}" if zero_pct > 0 else "0"
            bp_display = f"{int(round(big_pct))}" if big_pct > 0 else "0"
        else:
            sp_display = f"{small_pct:.1f}"
            zp_display = f"{zero_pct:.1f}"
            bp_display = f"{big_pct:.1f}"
        self.small_progress.config(text=f"{sp_display}%")
        self.zero_progress1.config(text=f"{zp_display}%")
        self.big_progress.config(text=f"{bp_display}%")

        # ========== 第二组：单 / 0 / 双 ==========
        odd_w = int(total_width * odd_pct / 100)
        zero_w2 = int(total_width * zero_pct / 100)
        even_w = total_width - odd_w - zero_w2

        if zero_cnt > 0 and zero_w2 < min_zero_width:
            needed = min_zero_width - zero_w2
            if even_w >= needed // 2 and odd_w >= needed - needed // 2:
                even_w -= needed // 2
                odd_w -= needed - (needed // 2)
            elif even_w >= needed:
                even_w -= needed
            elif odd_w >= needed:
                odd_w -= needed
            else:
                total_available = even_w + odd_w
                if total_available > 0:
                    even_w -= int(needed * even_w / total_available)
                    odd_w -= needed - int(needed * even_w / total_available)
            zero_w2 = min_zero_width

        odd_w = max(odd_w, 8 if odd_cnt > 0 else 0)
        even_w = max(even_w, 8 if even_cnt > 0 else 0)
        if odd_w + zero_w2 + even_w != total_width:
            diff = total_width - (odd_w + zero_w2 + even_w)
            if diff != 0:
                if even_cnt > 0:
                    even_w += diff
                elif odd_cnt > 0:
                    odd_w += diff
                else:
                    zero_w2 += diff

        self.odd_progress.place(x=0, y=0, width=odd_w, height=height)
        self.zero_progress2.place(x=odd_w, y=0, width=zero_w2, height=height)
        self.even_progress.place(x=odd_w + zero_w2, y=0, width=even_w, height=height)

        if self.distribution_display_count in [50, 100]:
            op_display = f"{int(round(odd_pct))}" if odd_pct > 0 else "0"
            zp2_display = f"{int(round(zero_pct))}" if zero_pct > 0 else "0"
            ep_display = f"{int(round(even_pct))}" if even_pct > 0 else "0"
        else:
            op_display = f"{odd_pct:.1f}"
            zp2_display = f"{zero_pct:.1f}"
            ep_display = f"{even_pct:.1f}"
        self.odd_progress.config(text=f"{op_display}%")
        self.zero_progress2.config(text=f"{zp2_display}%")
        self.even_progress.config(text=f"{ep_display}%")

        # ========== 第三组（新增）：红 / 绿(0) / 黑 ==========
        red_w   = int(total_width * red_pct / 100)
        green_w = int(total_width * green_pct / 100)
        black_w = total_width - red_w - green_w

        min_green_width = 30   # 绿色区域最小宽度
        if green_cnt > 0 and green_w < min_green_width:
            needed = min_green_width - green_w
            if black_w >= needed // 2 and red_w >= needed - needed // 2:
                black_w -= needed // 2
                red_w -= needed - (needed // 2)
            elif black_w >= needed:
                black_w -= needed
            elif red_w >= needed:
                red_w -= needed
            else:
                total_available = black_w + red_w
                if total_available > 0:
                    black_w -= int(needed * black_w / total_available)
                    red_w -= needed - int(needed * black_w / total_available)
            green_w = min_green_width

        red_w   = max(red_w,   8 if red_cnt   > 0 else 0)
        black_w = max(black_w, 8 if black_cnt > 0 else 0)
        if red_w + green_w + black_w != total_width:
            diff = total_width - (red_w + green_w + black_w)
            if diff != 0:
                if black_cnt > 0:
                    black_w += diff
                elif red_cnt > 0:
                    red_w += diff
                else:
                    green_w += diff

        self.red_progress.place(x=0, y=0, width=red_w, height=height)
        self.green_progress.place(x=red_w, y=0, width=green_w, height=height)
        self.black_progress.place(x=red_w + green_w, y=0, width=black_w, height=height)

        if self.distribution_display_count in [50, 100]:
            rp_display = f"{int(round(red_pct))}" if red_pct > 0 else "0"
            gp_display = f"{int(round(green_pct))}" if green_pct > 0 else "0"
            bp_display = f"{int(round(black_pct))}" if black_pct > 0 else "0"
        else:
            rp_display = f"{red_pct:.1f}"
            gp_display = f"{green_pct:.1f}"
            bp_display = f"{black_pct:.1f}"
        self.red_progress.config(text=f"{rp_display}%")
        self.green_progress.config(text=f"{gp_display}%")
        self.black_progress.config(text=f"{bp_display}%")


    def _create_distribution_panel(self, parent):
        card_bg = "#F2E6C9"
        header_bg = "#D8B46A"
        title_fg = "#2A1B08"

        outer = tk.Frame(parent, bg=ROOT_BG)
        outer.pack(fill=tk.X, pady=(0, 0))

        card = tk.Frame(outer, bg=card_bg, bd=1, relief=tk.SOLID, highlightthickness=0)
        card.pack(fill=tk.X)

        header = tk.Frame(card, bg=header_bg)
        header.pack(fill=tk.X)

        self.dist_title_btn = tk.Button(
            header,
            text=f"最新{self.distribution_display_count}局的获胜分布",
            font=("Arial", 13, "bold"),
            bg=header_bg,
            fg=title_fg,
            activebackground=header_bg,
            activeforeground=title_fg,
            relief=tk.FLAT,
            bd=0,
            command=self._toggle_distribution_count
        )
        self.dist_title_btn.pack(anchor=tk.CENTER, padx=10, pady=6)

        body = tk.Frame(card, bg=card_bg)
        body.pack(fill=tk.X, padx=10, pady=(8, 10))

        # 第一组：小 / 0 / 大
        group1_frame = tk.Frame(body, bg=card_bg)
        group1_frame.pack(fill=tk.X, pady=(0, 6))

        tk.Label(group1_frame, text="小", font=("Arial", 10, "bold"),
                bg=card_bg, fg="black", width=2, anchor="w").pack(side=tk.LEFT)

        progress_container1 = tk.Frame(group1_frame, bg=card_bg, height=30)
        progress_container1.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        self.small_progress = tk.Label(progress_container1, text="0.0%", bg="#5F9F4F",
                                    fg="white", anchor="center", font=("Arial", 10, "bold"))
        self.zero_progress1 = tk.Label(progress_container1, text="0.0%", bg=TEAL,
                                    fg="white", anchor="center", font=("Arial", 10, "bold"))
        self.big_progress = tk.Label(progress_container1, text="0.0%", bg="#AF4900",
                                    fg="white", anchor="center", font=("Arial", 10, "bold"))

        tk.Label(group1_frame, text="大", font=("Arial", 10, "bold"),
                bg=card_bg, fg="black", width=2, anchor="e").pack(side=tk.RIGHT)

        # 第二组：单 / 0 / 双
        group2_frame = tk.Frame(body, bg=card_bg)
        group2_frame.pack(fill=tk.X, pady=(0, 6))

        tk.Label(group2_frame, text="单", font=("Arial", 10, "bold"),
                bg=card_bg, fg="black", width=2, anchor="w").pack(side=tk.LEFT)

        progress_container2 = tk.Frame(group2_frame, bg=card_bg, height=30)
        progress_container2.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        self.odd_progress = tk.Label(progress_container2, text="0.0%", bg="#91FF00",
                                    fg="black", anchor="center", font=("Arial", 10, "bold"))
        self.zero_progress2 = tk.Label(progress_container2, text="0.0%", bg=TEAL,
                                    fg="white", anchor="center", font=("Arial", 10, "bold"))
        self.even_progress = tk.Label(progress_container2, text="0.0%", bg="#FF6B93",
                                    fg="white", anchor="center", font=("Arial", 10, "bold"))

        tk.Label(group2_frame, text="双", font=("Arial", 10, "bold"),
                bg=card_bg, fg="black", width=2, anchor="e").pack(side=tk.RIGHT)

        # 第三组：红 / 绿 / 黑
        group3_frame = tk.Frame(body, bg=card_bg)
        group3_frame.pack(fill=tk.X, pady=(0, 2))

        tk.Label(group3_frame, text="红", font=("Arial", 10, "bold"),
                bg=card_bg, fg="black", width=2, anchor="w").pack(side=tk.LEFT)

        progress_container3 = tk.Frame(group3_frame, bg=card_bg, height=30)
        progress_container3.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        self.red_progress = tk.Label(progress_container3, text="0.0%", bg=RED,
                                    fg="white", anchor="center", font=("Arial", 10, "bold"))
        self.green_progress = tk.Label(progress_container3, text="0.0%", bg=TEAL,
                                    fg="white", anchor="center", font=("Arial", 10, "bold"))
        self.black_progress = tk.Label(progress_container3, text="0.0%", bg=BLACK,
                                    fg="white", anchor="center", font=("Arial", 10, "bold"))

        tk.Label(group3_frame, text="黑", font=("Arial", 10, "bold"),
                bg=card_bg, fg="black", width=2, anchor="e").pack(side=tk.RIGHT)

        self._update_distribution()


    def _toggle_distribution_count(self):
        """循环切换分析局数：50 -> 100 -> 250 -> 500 -> 50"""
        options = [50, 100, 250, 500, 1000, 1500, 2000]
        current_index = options.index(self.distribution_display_count)
        next_index = (current_index + 1) % len(options)
        self.distribution_display_count = options[next_index]
        self.dist_title_btn.config(text=f"最新{self.distribution_display_count}局的获胜分布")
        self._update_distribution()

    def _create_pie_chart(self, parent):
        """创建可切换的饼图：居中显示，下方动态显示颜色+说明+次数"""
        card_bg = "#F2E6C9"
        header_bg = "#D8B46A"
        title_fg = "#2A1B08"

        outer = tk.Frame(parent, bg=ROOT_BG)
        outer.pack(fill=tk.X, pady=(8, 0))

        card = tk.Frame(outer, bg=card_bg, bd=1, relief=tk.SOLID, highlightthickness=0)
        card.pack(fill=tk.X)

        # 标题栏 - 与其他卡片保持一致
        title_bar = tk.Frame(card, bg=header_bg)
        title_bar.pack(fill=tk.X)

        self.pie_mode = "sector"  # "sector" 或 "row"
        self.pie_title_btn = tk.Button(
            title_bar,
            text="最新50局的区间分布",
            font=("Arial", 13, "bold"),          # 字体统一为 13
            bg=header_bg,
            fg=title_fg,
            activebackground=header_bg,
            activeforeground=title_fg,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=self._toggle_pie_chart_type
        )
        self.pie_title_btn.pack(anchor=tk.CENTER, padx=10, pady=6)

        # 主体内容区
        body = tk.Frame(card, bg=card_bg)
        body.pack(fill=tk.X, padx=6)

        # 饼图容器 - 居中显示
        pie_container = tk.Frame(body, bg=card_bg)
        pie_container.pack(expand=True, fill=tk.BOTH)
        # 让饼图画布在容器中居中
        self.pie_canvas = tk.Canvas(
            pie_container,
            width=150,
            height=150,
            bg=card_bg,
            highlightthickness=0,
            bd=0
        )
        self.pie_canvas.pack(anchor=tk.CENTER)

        # 饼图下方统计容器（颜色+说明+次数）
        self.pie_stats_frame = tk.Frame(card, bg=card_bg)
        self.pie_stats_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # 预定义颜色
        self.pie_colors = {
            "sector1": "#5F9F4F",   # 1-12
            "sector2": "#AF4900",   # 13-24
            "sector3": "#4A90E2",   # 25-36
            "zero": TEAL,           # 0
            "row1": RED,            # 行1
            "row2": BLACK,          # 行2
            "row3": "#8B4513",      # 行3
        }

    def _rebuild_pie_legend(self, parent):
        """重建图例：仅显示名称和色块，不显示百分比（根据当前模式动态生成，但实际内容在_update中动态增减）"""
        # 清除原有
        for widget in parent.winfo_children():
            widget.destroy()
        self.legend_widgets = {}  # 存储每个分类对应的图例行（用于隐藏/显示）
        pass

    def _toggle_pie_chart_type(self):
        """切换饼图模式（Sector 或 Row）并更新界面"""
        if self.pie_mode == "sector":
            self.pie_mode = "row"
            self.pie_title_btn.config(text="最新50局的每行分布")
        else:
            self.pie_mode = "sector"
            self.pie_title_btn.config(text="最新50局的区间分布")

        self._update_pie_chart()

    def _get_sector_data_from_recent(self, limit=50):
        """从 Record2 中获取最近 limit 条结果，统计各区间（1-12,13-24,25-36,0）出现的次数"""
        all_results = self.history.recent_results2(limit=2000)
        recent = [entry.get("result", "") for entry in all_results if entry.get("result", "")][:limit]
        counts = {"1-12": 0, "13-24": 0, "25-36": 0, "0": 0}
        for res in recent:
            if res == "0":
                counts["0"] += 1
            else:
                try:
                    num = int(res)
                    if 1 <= num <= 12:
                        counts["1-12"] += 1
                    elif 13 <= num <= 24:
                        counts["13-24"] += 1
                    elif 25 <= num <= 36:
                        counts["25-36"] += 1
                except ValueError:
                    pass
        return counts, len(recent)

    def _get_row_data_from_recent(self, limit=50):
        """统计最近 limit 条结果中属于 Row1/Row2/Row3/0 的次数"""
        row1_set = {1,4,7,10,13,16,19,22,25,28,31,34}
        row2_set = {2,5,8,11,14,17,20,23,26,29,32,35}
        row3_set = {3,6,9,12,15,18,21,24,27,30,33,36}

        all_results = self.history.recent_results2(limit=2000)
        recent = [entry.get("result", "") for entry in all_results if entry.get("result", "")][:limit]
        counts = {"row1": 0, "row2": 0, "row3": 0, "0": 0}
        for res in recent:
            if res == "0":
                counts["0"] += 1
            else:
                try:
                    num = int(res)
                    if num in row1_set:
                        counts["row1"] += 1
                    elif num in row2_set:
                        counts["row2"] += 1
                    elif num in row3_set:
                        counts["row3"] += 1
                except ValueError:
                    pass
        return counts, len(recent)

    def _create_hot_cold_panel(self, parent):
        """最热/最冷数字卡片化，支持循环切换统计局数（500/1000/1500/2000）"""
        card_bg = "#F2E6C9"
        header_bg = "#D8B46A"
        title_fg = "#2A1B08"

        outer = tk.Frame(parent, bg=ROOT_BG)
        outer.pack(fill=tk.X, pady=(0, 0))

        card = tk.Frame(outer, bg=card_bg, bd=1, relief=tk.SOLID, highlightthickness=0)
        card.pack(fill=tk.X)

        # 标题栏（可点击切换）
        header = tk.Frame(card, bg=header_bg)
        header.pack(fill=tk.X)

        self.hot_cold_limit = 500   # 默认500局
        self.hot_cold_title_btn = tk.Button(
            header,
            text=f"最新{self.hot_cold_limit}局的最热/最冷数字",
            font=("Arial", 13, "bold"),
            bg=header_bg,
            fg=title_fg,
            activebackground=header_bg,
            activeforeground=title_fg,
            relief=tk.FLAT,
            bd=0,
            command=self._toggle_hot_cold_count
        )
        self.hot_cold_title_btn.pack(anchor=tk.CENTER, padx=10, pady=6)   # 居中显示

        content_frame = tk.Frame(card, bg=card_bg)
        content_frame.pack(fill=tk.X, pady=(8, 10))

        def create_table(parent, title, title_color, body_bg):
            outer_card = tk.Frame(parent, bg=body_bg, bd=1, relief=tk.SOLID, highlightthickness=0)
            outer_card.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=4)

            tk.Label(
                outer_card,
                text=title,
                font=("微软雅黑", 12, "bold"),
                fg=title_color,
                bg=body_bg
            ).pack(pady=(5, 3))

            rows = []
            for _ in range(6):
                row_frame = tk.Frame(outer_card, bg=body_bg, height=42)
                row_frame.pack(fill=tk.X, padx=6, pady=0)
                row_frame.pack_propagate(False)

                canvas = tk.Canvas(
                    row_frame,
                    width=36,
                    height=36,
                    bg=body_bg,
                    highlightthickness=0,
                    bd=0
                )
                canvas.pack(side=tk.LEFT, padx=(2, 0))

                count_label = tk.Label(
                    row_frame,
                    text="",
                    font=("Arial", 18, "bold"),
                    bg=body_bg,
                    fg="#333333",
                    width=4,
                    relief=tk.FLAT
                )
                count_label.pack(side=tk.RIGHT, padx=(0, 4))

                rows.append((canvas, count_label))

            return rows

        self.hot_canvases = create_table(
            content_frame,
            "🔥 最热数字",
            "#E67E22",
            "#FFF7EE"
        )

        self.cold_canvases = create_table(
            content_frame,
            "❄ 最冷数字",
            "#3498DB",
            "#EEF7FF"
        )

        self._update_hot_cold_display()

    def _toggle_hot_cold_count(self):
        """循环切换统计局数：500 -> 1000 -> 1500 -> 2000 -> 500"""
        options = [500, 1000, 1500, 2000]
        current_index = options.index(self.hot_cold_limit)
        next_index = (current_index + 1) % len(options)
        self.hot_cold_limit = options[next_index]
        self.hot_cold_title_btn.config(text=f"最新{self.hot_cold_limit}局的最热/最冷数字")
        self._update_hot_cold_display()

    def _update_hot_cold_display(self):
        """根据 self.hot_cold_limit 从历史中取最近 N 条结果，更新热冷数字"""
        if not hasattr(self, 'history'):
            return

        # 获取足够多的历史（从 Record2 中取，最多 2000 条）
        all_results = self.history.recent_results2(limit=2000)
        # 只取最近 self.hot_cold_limit 条
        results = [
            entry.get("result", "")
            for entry in all_results
            if entry.get("result", "")
        ][:self.hot_cold_limit]

        # 统计
        all_numbers = [str(i) for i in range(1, 37)] + ["0"]
        counts = {num: 0 for num in all_numbers}
        for res in results:
            if res in counts:
                counts[res] += 1

        # 最热（按次数降序，同次数按数字升序）
        hot_items = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:6]
        # 最冷（按次数升序，同次数按数字升序）取前6再反转
        cold_items = sorted(counts.items(), key=lambda x: (x[1], x[0]))[:6][::-1]

        def draw_ball(canvas, number, color):
            canvas.delete("all")
            canvas.create_oval(3, 4, 33, 34, fill="#999999", outline="")
            canvas.create_oval(2, 2, 32, 32, fill=color, outline="#111111", width=1)
            canvas.create_text(17, 17, text=number, fill="white", font=("Arial", 12, "bold"))

        def update_group(items, widgets, row_bg):
            for i, (num, cnt) in enumerate(items):
                canvas, count_lbl = widgets[i]
                color_name = roulette_color(num)
                if color_name == "Red":
                    ball_color = RED
                elif color_name == "Black":
                    ball_color = BLACK
                else:
                    ball_color = TEAL
                draw_ball(canvas, num, ball_color)
                count_lbl.config(text=str(cnt), bg=row_bg, fg="#222222")
            # 清空多余行
            for i in range(len(items), len(widgets)):
                canvas, count_lbl = widgets[i]
                canvas.delete("all")
                count_lbl.config(text="", bg=canvas["bg"])

        update_group(hot_items, self.hot_canvases, "#FFF7EE")
        update_group(cold_items, self.cold_canvases, "#EEF7FF")

    def _update_pie_chart(self):
        """根据当前模式，动态绘制饼图（仅绘制计数>0的扇形），下方显示颜色+说明+次数，0始终在最上方且永远显示（即使0次）"""
        if not hasattr(self, "pie_canvas"):
            return

        limit = 50
        if self.pie_mode == "sector":
            counts, total = self._get_sector_data_from_recent(limit)
            all_keys = ["1-12", "13-24", "25-36", "0"]
            display_names = {"1-12": "1-12", "13-24": "13-24", "25-36": "25-36", "0": "数字0"}
            color_keys = {"1-12": "sector1", "13-24": "sector2", "25-36": "sector3", "0": "zero"}
        else:
            counts, total = self._get_row_data_from_recent(limit)
            all_keys = ["row1", "row2", "row3", "0"]
            display_names = {"row1": "直行1(1/4/7...)", "row2": "直行2(2/5/8...)", "row3": "直行3(3/6/9...)", "0": "数字0"}
            color_keys = {"row1": "row1", "row2": "row2", "row3": "row3", "0": "zero"}

        if total == 0:
            total = 1

        # 构建用于饼图扇形的有效数据（计数>0）
        valid_for_pie = [(key, counts[key]) for key in all_keys if counts[key] > 0]

        # 构建用于统计显示的数据：包含所有计数>0的分类 + 始终包含0（即使计数为0）
        zero_count = counts.get("0", 0)
        other_items = [(key, counts[key]) for key in all_keys if key != "0" and counts[key] > 0]
        # 始终把0放在最前面（即使计数为0）
        valid_for_stats = [("0", zero_count)] + other_items

        # 如果没有扇形数据（只有0且0次），则清空饼图
        if not valid_for_pie:
            self.pie_canvas.delete("all")
        else:
            # 绘制饼图扇形
            self.pie_canvas.delete("all")
            cx, cy = 75, 75
            radius = 65
            start_angle = 0
            values = [cnt for _, cnt in valid_for_pie]
            angles = [360 * (v / total) for v in values]

            for (key, _), angle in zip(valid_for_pie, angles):
                color = self.pie_colors[color_keys[key]]
                self.pie_canvas.create_arc(
                    cx - radius, cy - radius,
                    cx + radius, cy + radius,
                    start=start_angle,
                    extent=angle,
                    fill=color,
                    outline="white",
                    width=1.5
                )
                # 添加扇区中央文字（短名称）
                mid_angle = start_angle + angle / 2
                rad = math.radians(mid_angle)
                text_r = radius * 0.65
                tx = cx + text_r * math.cos(rad)
                ty = cy - text_r * math.sin(rad)
                if key == "0":
                    label = "0"
                elif key.startswith("row"):
                    label = key[-1]
                else:
                    label = key
                text_color = "black" if label == "0" else "white"
                self.pie_canvas.create_text(tx, ty, text=label, fill=text_color, font=("Arial", 9, "bold"))
                start_angle += angle

        # 更新下方统计信息：颜色 + 说明 + 次数（0永远显示）
        for widget in self.pie_stats_frame.winfo_children():
            widget.destroy()

        for key, cnt in valid_for_stats:
            row_frame = tk.Frame(self.pie_stats_frame, bg=self.pie_stats_frame["bg"])
            row_frame.pack(fill=tk.X, pady=2)

            color_block = tk.Canvas(row_frame, width=16, height=16, bg=self.pie_stats_frame["bg"],
                                    highlightthickness=0, bd=0)
            color_block.pack(side=tk.LEFT, padx=(0, 6))
            # 即使次数为0，也显示色块（颜色正常）
            color_block.create_oval(2, 2, 14, 14, fill=self.pie_colors[color_keys[key]], outline="")

            lbl_text = tk.Label(row_frame, text=f"{display_names[key]}: {cnt}次",
                                bg=self.pie_stats_frame["bg"], fg="#1A1A1A",
                                font=("Arial", 10, "bold"), anchor="w")
            lbl_text.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _get_legend_frame(self):
        """辅助方法：获取饼图右侧的图例框架"""
        body = self.pie_canvas.master
        for child in body.winfo_children():
            if isinstance(child, tk.Frame) and child != self.pie_canvas:
                return child
        return None

    def _draw_marker_grid(self):
        self.marker_canvas.delete("all")

        rows = self.marker_rows
        cols = self.marker_cols
        cell_size = 30

        width = cols * cell_size + 2
        height = rows * cell_size + 2

        self.marker_canvas.config(
            width=width,
            height=height,
            scrollregion=(0, 0, width, height)
        )

        for col in range(cols):
            for row in range(rows):
                x1 = col * cell_size
                y1 = row * cell_size
                x2 = x1 + cell_size
                y2 = y1 + cell_size

                self.marker_canvas.create_rectangle(
                    x1, y1, x2, y2,
                    outline="#7B6441",
                    fill="#F7ECD3",
                    width=1
                )

    def _update_marker_road(self):
        self._draw_marker_grid()
        rows, cols = self.marker_rows, self.marker_cols
        cell_size = 30
        max_display = rows * cols
        start_idx = max(0, len(self.marker_results) - max_display)
        results_to_show = self.marker_results[start_idx:]

        for idx, entry in enumerate(results_to_show):
            if idx >= max_display:
                break
            result = entry["result"]
            color = roulette_color(result)
            if color == "Red":
                fill = RED
                text_fill = "white"
            elif color == "Black":
                fill = BLACK
                text_fill = "white"
            else:
                fill = TEAL
                text_fill = "white"

            col = idx // rows
            row = idx % rows
            x1 = col * cell_size
            y1 = row * cell_size
            x2 = x1 + cell_size
            y2 = y1 + cell_size
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            radius = cell_size * 0.40

            self.marker_canvas.create_oval(
                cx - radius, cy - radius,
                cx + radius, cy + radius,
                fill=fill,
                outline="#000000",
                width=2,
                tags="dot"
            )
            font = ("Segoe UI Emoji", 11, "bold") if result == "00" else ("Arial", 11, "bold")
            self.marker_canvas.create_text(
                cx, cy,
                text=result,
                fill=text_fill,
                font=font,
                tags="dot"
            )

    def _sync_marker_from_history(self):
        raw_hist = self.history.recent_results(limit=54)
        reversed_hist = [entry for entry in reversed(raw_hist) if entry["result"]]
        self.marker_results = reversed_hist
        self._update_marker_road()
        self._update_pie_chart()
        self._update_distribution() 
        self._update_hot_cold_display()

    def add_marker_result(self, result):
        self._sync_marker_from_history()
        self._update_pie_chart()
        self._update_distribution() 
        self._update_hot_cold_display()

    # =====================================================
    # Wheel drawing (unchanged)
    # =====================================================
    def _draw_wheel(self):
        # 强制处理 pending 的布局事件，确保能获取到正确的画布尺寸
        self.update_idletasks()

        canvas_w = max(int(self.wheel_canvas.winfo_width()), 1)
        canvas_h = max(int(self.wheel_canvas.winfo_height()), 1)

        # 如果画布尺寸过小（通常窗口尚未完全映射），延迟重试
        if canvas_w <= 10 or canvas_h <= 10:
            self.after(50, self._draw_wheel)
            return

        self.wheel_canvas.delete("all")

        # ===== 背景：赌场风格深色舞台 + 轻微渐层感 =====
        self.wheel_canvas.create_rectangle(
            0, 0, canvas_w, canvas_h,
            fill="#1B3D31",
            outline="",
            tags=("wheel_bg",)
        )

        # 轻微装饰光圈
        cx = canvas_w / 2
        cy = canvas_h / 2 - 2

        for r, fill, width in [
            (220, "#173F66", 2),
            (205, "#0E241E", 2),
        ]:
            self.wheel_canvas.create_oval(
                cx - r, cy - r,
                cx + r, cy + r,
                fill="",
                outline=fill,
                width=width,
                tags=("wheel_bg",)
            )

        # 轮盘本体参数
        outer_r = 174
        inner_r = 70

        # 外围金属底座
        self.wheel_canvas.create_oval(
            cx - outer_r - 28, cy - outer_r - 28,
            cx + outer_r + 28, cy + outer_r + 28,
            fill="#2D2214",
            outline="#D4AF37",
            width=6,
            tags=("wheel",)
        )
        self.wheel_canvas.create_oval(
            cx - outer_r - 18, cy - outer_r - 18,
            cx + outer_r + 18, cy + outer_r + 18,
            fill="",
            outline="#8B6B24",
            width=2,
            tags=("wheel",)
        )

        # 轮盘转盘阴影层
        self.wheel_canvas.create_oval(
            cx - outer_r - 8, cy - outer_r - 8,
            cx + outer_r + 8, cy + outer_r + 8,
            fill="#1A1A1A",
            outline="",
            tags=("wheel",)
        )

        # 轮盘扇区
        self._draw_wheel_segments(cx, cy, outer_r, inner_r, self.current_wheel_offset)

        # 轮盘外圈细金边
        self.wheel_canvas.create_oval(
            cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r,
            outline="#E6C15A",
            width=3,
            tags=("wheel",)
        )
        self.wheel_canvas.create_oval(
            cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r,
            outline="#E6C15A",
            width=2,
            tags=("wheel",)
        )

        # 外圈刻痕 / 螺钉感装饰
        for i in range(37):
            ang = math.radians(i * (360.0 / 37.0))
            r1 = outer_r + 6
            r2 = outer_r + 14
            x1 = cx + r1 * math.sin(ang)
            y1 = cy - r1 * math.cos(ang)
            x2 = cx + r2 * math.sin(ang)
            y2 = cy - r2 * math.cos(ang)
            self.wheel_canvas.create_line(
                x1, y1, x2, y2,
                fill="#C9A24A",
                width=2,
                tags=("wheel",)
            )

        # 中心金属盘
        self.wheel_canvas.create_oval(
            cx - inner_r - 15, cy - inner_r - 15,
            cx + inner_r + 15, cy + inner_r + 15,
            fill="#6B4D1B",
            outline="#E6C15A",
            width=3,
            tags=("wheel",)
        )
        self.wheel_canvas.create_oval(
            cx - inner_r - 7, cy - inner_r - 7,
            cx + inner_r + 7, cy + inner_r + 7,
            fill="#F3E8C9",
            outline="#1A1A1A",
            width=2,
            tags=("wheel",)
        )

        # 中心显示
        if self.center_display_result is not None:
            result = self.center_display_result
            bg_color = OUTCOME_COLORS.get(result, "#FFFFFF")
            inner_bg_r = inner_r - 10
            self.wheel_canvas.create_oval(
                cx - inner_bg_r, cy - inner_bg_r,
                cx + inner_bg_r, cy + inner_bg_r,
                fill=bg_color,
                outline="#111111",
                width=2,
                tags=("wheel",)
            )
            font_size = 34 if len(result) == 2 else 36
            font = ("Segoe UI Emoji", font_size, "bold") if result == "00" else ("Arial", font_size, "bold")
            self.wheel_canvas.create_text(
                cx, cy,
                text=result,
                fill=OUTCOME_TEXT_COLORS.get(result, "white"),
                font=font,
                tags=("wheel",)
            )
        else:
            self.wheel_canvas.create_text(
                cx, cy - 10,
                text="欧式轮盘",
                font=("Arial", 24, "bold"),
                fill="#2A1B08",
                tags=("wheel",)
            )

            if self.round_state == "betting" and self.betting_deadline is not None:
                remaining = max(0, int(math.ceil(self.betting_deadline - time.time())))
                timer_text = f"{remaining:02d}s"
            elif self.round_state == "spinning":
                timer_text = "开奖中"
            else:
                timer_text = "等待开奖"

            self.wheel_timer_id = self.wheel_canvas.create_text(
                cx, cy + 28,
                text=timer_text,
                font=("Arial", 16, "bold"),
                fill="#2A1B08",
                tags=("timer",)
            )

        # 逆时针绕轮盘旋转的指针
        self._draw_orbiting_pointer(cx, cy, outer_r)

    def _draw_wheel_segments(self, cx, cy, outer_r, inner_r, offset_deg):
        self.wheel_canvas.delete("wheel_segments")

        n = len(ROULETTE_SEQUENCE)
        step = 360.0 / n

        # 先画一层底色，避免扇区之间露出空隙
        self.wheel_canvas.create_oval(
            cx - outer_r, cy - outer_r,
            cx + outer_r, cy + outer_r,
            fill="#1A1A1A",
            outline="",
            tags=("wheel_segments",)
        )

        for i, symbol in enumerate(ROULETTE_SEQUENCE):
            start = (offset_deg + i * step) % 360.0
            end = start + step

            # 扇形多边形：中心点 + 外圈两点
            points = [cx, cy]
            for ang in (start, end):
                rad = math.radians(ang)
                x = cx + outer_r * math.sin(rad)
                y = cy - outer_r * math.cos(rad)
                points.extend([x, y])

            fill_color = OUTCOME_COLORS[symbol]
            outline_color = "#2A2A2A"

            self.wheel_canvas.create_polygon(
                points,
                fill=fill_color,
                outline=outline_color,
                width=1,
                smooth=False,
                tags=("wheel_segments",)
            )

            # 扇区高光线，增加层次感
            rad1 = math.radians(start)
            x1 = cx + inner_r * math.sin(rad1)
            y1 = cy - inner_r * math.cos(rad1)
            x2 = cx + outer_r * math.sin(rad1)
            y2 = cy - outer_r * math.cos(rad1)
            self.wheel_canvas.create_line(
                x1, y1, x2, y2,
                fill="#F6F1D0",
                width=1,
                tags=("wheel_segments",)
            )

            # 号码文字
            mid = (start + end) / 2.0
            rad = math.radians(mid)
            text_r = outer_r * 0.83
            tx = cx + text_r * math.sin(rad)
            ty = cy - text_r * math.cos(rad)

            is_zero = symbol in {"0", "00"}
            text_font = ("Segoe UI Emoji", 11, "bold") if symbol == "00" else ("Arial", 11, "bold")
            text_fill = OUTCOME_TEXT_COLORS[symbol]

            # 轻微文字阴影
            self.wheel_canvas.create_text(
                tx + 1, ty + 1,
                text=symbol,
                font=text_font,
                fill="#000000",
                tags=("wheel_segments",)
            )
            self.wheel_canvas.create_text(
                tx, ty,
                text=symbol,
                font=text_font,
                fill=text_fill,
                tags=("wheel_segments",)
            )

        # 最内圈边界
        self.wheel_canvas.create_oval(
            cx - inner_r, cy - inner_r,
            cx + inner_r, cy + inner_r,
            outline="#F3E8C9",
            width=2,
            tags=("wheel_segments",)
        )

        # 外圈边界
        self.wheel_canvas.create_oval(
            cx - outer_r, cy - outer_r,
            cx + outer_r, cy + outer_r,
            outline="#F3E8C9",
            width=2,
            tags=("wheel_segments",)
        )

        # 让轮盘层在最上面
        self.wheel_canvas.tag_raise("wheel_segments")

    # =====================================================
    # Bet spots / hit testing / chips (chip radius enlarged by 20%)
    # =====================================================

    def _build_bet_spots(self):
        g = self.geometry_model
        spots = []

        def add_spot(spot_id, spot_type, label, numbers, payout, bounds, center, kind="point", extra=None):
            payload = {
                "id": spot_id,
                "type": spot_type,
                "label": label,
                "numbers": set(numbers),
                "payout": payout,
                "kind": kind,
                "bounds": bounds,
                "center": center,
            }
            if extra:
                payload.update(extra)
            spots.append(payload)

        # European single zero – merged straight spot
        zero_height = 2 * g.zero_h   # total height = 3 * num_h
        add_spot(
            "straight_0",
            "straight",
            "0",
            {"0"},
            BET_ODDS["straight"],
            (g.zero_x1, g.grid_y1, g.zero_x2, g.grid_y1 + zero_height),
            ((g.zero_x1 + g.zero_x2) / 2, g.grid_y1 + zero_height / 2),
            kind="cell",
        )

        for row in range(3):
            for col in range(12):
                num = str(g.rows[row][col])
                x1, y1, x2, y2 = g.cell_bounds(row, col)
                add_spot(
                    f"straight_{num}",
                    "straight",
                    num,
                    {num},
                    BET_ODDS["straight"],
                    (x1, y1, x2, y2),
                    ((x1 + x2) / 2, (y1 + y2) / 2),
                    kind="cell",
                    extra={"row": row, "col": col},
                )

        # Dozens
        dozen_w = 4 * g.num_w
        for idx, label in enumerate(["1st 12", "2nd 12", "3rd 12"]):
            x1 = g.grid_x1 + idx * dozen_w
            x2 = x1 + dozen_w
            add_spot(
                f"dozen_{idx + 1}",
                "dozen",
                label,
                g.doze_numbers(idx),
                BET_ODDS["dozen"],
                (x1, g.dozen_y1, x2, g.dozen_y2),
                ((x1 + x2) / 2, (g.dozen_y1 + g.dozen_y2) / 2),
                kind="rectangle",
            )

        # Column bets
        column_labels = ["3rd Column", "2nd Column", "1st Column"]
        column_sets = [
            [str(n) for n in range(3, 37, 3)],
            [str(n) for n in range(2, 36, 3)],
            [str(n) for n in range(1, 35, 3)],
        ]
        for row in range(3):
            y1 = g.grid_y1 + row * g.num_h
            y2 = y1 + g.num_h
            add_spot(
                f"column_{row}",
                "column",
                column_labels[row],
                column_sets[row],
                BET_ODDS["column"],
                (g.col_x1, y1, g.col_x2, y2),
                ((g.col_x1 + g.col_x2) / 2, (y1 + y2) / 2),
                kind="rectangle",
            )

        # Outside bets
        seg_w = (4 * g.num_w) // 2
        outer_labels = [
            ("1-18", set(str(n) for n in range(1, 19))),
            ("Even", set(str(n) for n in range(1, 37) if n % 2 == 0)),
            ("Red", set(str(n) for n in RED_NUMBERS)),
            ("Black", set(str(n) for n in range(1, 37) if n not in RED_NUMBERS)),
            ("Odd", set(str(n) for n in range(1, 37) if n % 2 == 1)),
            ("19-36", set(str(n) for n in range(19, 37))),
        ]
        for idx, (label, numbers) in enumerate(outer_labels):
            x1 = g.grid_x1 + idx * seg_w
            x2 = x1 + seg_w
            spot_type = "color" if label in {"Red", "Black"} else ("odd_even" if label in {"Odd", "Even"} else "high_low")
            payout = BET_ODDS["color"] if label in {"Red", "Black"} else BET_ODDS["odd_even"]
            add_spot(
                f"outside_{idx}",
                spot_type,
                label,
                numbers,
                payout,
                (x1, g.outer_y1, x2, g.outer_y2),
                ((x1 + x2) / 2, (g.outer_y1 + g.outer_y2) / 2),
                kind="rectangle",
            )

        # Five-number bet removed

        # Special zero-area split / intersection bets (European style)
        # split 0-1
        add_spot(
            "split_0_1",
            "split",
            "0-1",
            {"0", "1"},
            BET_ODDS["split"],
            (g.zero_x2 - 9, g.grid_y1 + 2 * g.num_h + 8, g.zero_x2 + 9, g.grid_y1 + 3 * g.num_h - 8),
            (g.zero_x2, g.grid_y1 + 2.5 * g.num_h),
            kind="line",
        )
        # split 0-2
        add_spot(
            "split_0_2",
            "split",
            "0-2",
            {"0", "2"},
            BET_ODDS["split"],
            (g.zero_x2 - 9, g.grid_y1 + g.num_h + 8, g.zero_x2 + 9, g.grid_y1 + 2 * g.num_h - 8),
            (g.zero_x2, g.grid_y1 + 1.5 * g.num_h),
            kind="line",
        )
        # split 0-3
        add_spot(
            "split_0_3",
            "split",
            "0-3",
            {"0", "3"},
            BET_ODDS["split"],
            (g.zero_x2 - 9, g.grid_y1 + 8, g.zero_x2 + 9, g.grid_y1 + g.num_h - 8),
            (g.zero_x2, g.grid_y1 + g.num_h / 2),
            kind="line",
        )
        # street 0-1-2
        add_spot(
            "triple_0_1_2",
            "street",
            "0-1-2",
            {"0", "1", "2"},
            BET_ODDS["street"],
            (g.zero_x2 - 10, g.grid_y1 + 2 * g.num_h - 10, g.zero_x2 + 10, g.grid_y1 + 2 * g.num_h + 10),
            (g.zero_x2, g.grid_y1 + 2 * g.num_h),
            kind="point",
        )
        # street 0-2-3 (optional, often not available, but we keep for completeness)
        add_spot(
            "triple_0_2_3",
            "street",
            "0-2-3",
            {"0", "2", "3"},
            BET_ODDS["street"],
            (g.zero_x2 - 10, g.grid_y1 + g.num_h - 10, g.zero_x2 + 10, g.grid_y1 + g.num_h + 10),
            (g.zero_x2, g.grid_y1 + g.num_h),
            kind="point",
        )

        # Split spots: vertical and horizontal
        for row in range(3):
            for col in range(11):
                n1 = str(g.rows[row][col])
                n2 = str(g.rows[row][col + 1])
                x1, y1, x2, y2 = g.cell_bounds(row, col)
                _, _, nx2, _ = g.cell_bounds(row, col + 1)
                cx = x2
                cy = (y1 + y2) / 2
                add_spot(
                    f"split_v_{row}_{col}",
                    "split",
                    f"{n1}-{n2}",
                    {n1, n2},
                    BET_ODDS["split"],
                    (cx - 8, y1 + 6, cx + 8, y2 - 6),
                    (cx, cy),
                    kind="line",
                    extra={"orientation": "v"},
                )

        for col in range(12):
            for row in range(2):
                n1 = str(g.rows[row][col])
                n2 = str(g.rows[row + 1][col])
                x1, y1, x2, y2 = g.cell_bounds(row, col)
                cx = (x1 + x2) / 2
                cy = y2
                add_spot(
                    f"split_h_{row}_{col}",
                    "split",
                    f"{n1}-{n2}",
                    {n1, n2},
                    BET_ODDS["split"],
                    (x1 + 6, cy - 8, x2 - 6, cy + 8),
                    (cx, cy),
                    kind="line",
                    extra={"orientation": "h"},
                )

        # Corner spots: give them a larger square around the intersection
        for row in range(2):
            for col in range(11):
                nums = {
                    str(g.rows[row][col]),
                    str(g.rows[row][col + 1]),
                    str(g.rows[row + 1][col]),
                    str(g.rows[row + 1][col + 1]),
                }
                x1, y1, x2, y2 = g.cell_bounds(row, col)
                ix = x2
                iy = y2
                add_spot(
                    f"corner_{row}_{col}",
                    "corner",
                    ",".join(sorted(nums, key=lambda s: (len(s), s))),
                    nums,
                    BET_ODDS["corner"],
                    (ix - 10, iy - 10, ix + 10, iy + 10),
                    (ix, iy),
                    kind="point",
                )

        # Street spots: horizontal line under each column, between grid and dozens
        street_y = g.dozen_y1
        for col in range(12):
            numbers = {str(g.rows[r][col]) for r in range(3)}
            x1, y1, x2, y2 = g.cell_bounds(0, col)
            add_spot(
                f"street_{col}",
                "street",
                "-".join(sorted(numbers, key=lambda s: int(s))),
                numbers,
                BET_ODDS["street"],
                (x1 + 4, street_y - 8, x2 - 4, street_y + 8),
                ((x1 + x2) / 2, street_y),
                kind="line",
                extra={"col": col},
            )

        # Six line spots: intersection between two streets and the dozen line
        for col in range(11):
            numbers = {str(g.rows[r][col]) for r in range(3)} | {str(g.rows[r][col + 1]) for r in range(3)}
            x1, y1, x2, y2 = g.cell_bounds(0, col)
            nx1, ny1, nx2, ny2 = g.cell_bounds(2, col + 1)
            bx = x2
            add_spot(
                f"six_line_{col}_{col+1}",
                "six_line",
                f"{col+1}/{col+2}",
                numbers,
                BET_ODDS["six_line"],
                (bx - 10, g.dozen_y1 - 10, bx + 10, g.dozen_y1 + 10),
                (bx, g.dozen_y1),
                kind="point",
            )

        return spots

    def _spot_numbers(self, spot):
        return set(spot.get("numbers", set()))

    def _chip_fill_color_for_amount(self, amount: int) -> str:
        try:
            amt = int(amount)
        except Exception:
            amt = 0

        if amt <= 4:
            return "#ffffff"
        if amt <= 9:
            return "#9e9e9e"
        if amt <= 24:
            return "#0000ff"
        if amt <= 99:
            return "#00ff00"
        if amt <= 499:
            return "#A8ECFF"
        return "#FF7DDA"

    def _bet_limit_for_spot(self, spot):
        inside_types = {"straight", "split", "street", "corner", "six_line"}  # five_number removed
        if spot.get("type") in inside_types:
            return 200
        return 500
    
    def _format_win_amount(self, value):
        value = int(value)

        if value < 1000:
            return str(value)

        k = value / 1000

        if value % 1000 == 0:
            return f"{int(k)}K"

        if value % 100 == 0:
            return f"{k:.1f}K"

        return f"{k:.1f}K+"


    def _result_chip_style(self, amount):
        amount = int(amount)

        if 1 <= amount <= 4:
            return "#ffffff", "black"
        if 5 <= amount <= 9:
            return "#9e9e9e", "black"
        if 10 <= amount <= 24:
            return "#0000ff", "white"
        if 25 <= amount <= 99:
            return "#00ff00", "black"
        if 100 <= amount <= 499:
            return "#A8ECFF", "black"
        if 500 <= amount <= 999:
            return "#FF7DDA", "black"
        return "#9400b6", "white"

    def _find_spot_by_id(self, spot_id: str):
        for spot in self.bet_spots:
            if spot["id"] == spot_id:
                return spot
        return None

    def _spot_by_point(self, x: float, y: float):
        def inside(bounds):
            x1, y1, x2, y2 = bounds
            return x1 <= x <= x2 and y1 <= y <= y2

        # 优先匹配更精确的非直注区域
        priority = {
            "street": 0,
            "six_line": 1,
            "corner": 2,
            "split": 3,
            "dozen": 4,
            "column": 5,
            "color": 6,
            "odd_even": 7,
            "high_low": 8,
        }

        matches = []
        for idx, spot in enumerate(self.bet_spots):
            bounds = spot.get("bounds")
            if not bounds or not inside(bounds):
                continue

            x1, y1, x2, y2 = bounds
            area = max(0.0, float(x2 - x1)) * max(0.0, float(y2 - y1))
            spot_type = spot.get("type", "")
            matches.append((priority.get(spot_type, 99), area, idx, spot))

        if not matches:
            return None

        matches.sort(key=lambda item: (item[0], item[1], item[2]))
        return matches[0][3]

    def _spot_display_label(self, spot):
        if spot["type"] == "straight":
            return spot["label"]
        return spot["label"]

    def _spot_text_color(self, fill_color):
        try:
            if ImageColor is not None:
                rgb = ImageColor.getrgb(fill_color)
                luminance = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
                return "white" if luminance < 140 else "black"
        except Exception:
            pass
        return "black"

    def _chip_radius_for_spot(self, spot):
        """
        内围投注统一筹码大小
        外围投注统一筹码大小
        """

        # 内围投注
        if spot["type"] in (
            "straight",
            "split",
            "corner",
            "street",
            "six_line",
        ):
            return 10

        # 外围投注
        if spot["type"] in (
            "dozen",
            "column",
            "color",
            "odd_even",
            "high_low",
        ):
            return 14

        return 14

    def _draw_placed_chips(self):
        if not hasattr(self, "board_canvas"):
            return

        self.board_canvas.delete("chips")
        for spot_id, amount in self.current_bets.items():
            if amount <= 0:
                continue
            spot = self._find_spot_by_id(spot_id)
            if not spot:
                continue
            fill = self.current_bet_colors.get(spot_id, self._chip_fill_color_for_amount(amount))
            self._draw_chip_on_spot(spot, amount, fill)

    def _draw_chip_on_spot(self, spot, amount, fill=None):
        cx, cy = spot["center"]
        radius = self._chip_radius_for_spot(spot)

        spot_id = spot["id"]
        base_fill = fill or self._chip_fill_color_for_amount(amount)
        base_text_color = self._spot_text_color(base_fill)
        display_amount = int(amount)
        display_fill = base_fill
        display_text_color = base_text_color

        # 开奖后的中奖筹码：原色/派奖色 轮流显示
        if self.round_state == "result" and spot_id in self.result_chip_display:
            info = self.result_chip_display[spot_id]
            if self._result_flash_state:
                display_amount = int(info["win_amount"])
                display_fill = info["win_fill"]
                display_text_color = info["win_text_color"]
            else:
                display_amount = int(info["original_amount"])
                display_fill = info["original_fill"]
                display_text_color = info["original_text_color"]

        if spot["type"] in ("straight", "split", "corner", "street"):
            offset_list = [(0, 0), (10, 0), (-10, 0), (0, 10), (0, -10)]
        elif spot["type"] == "six_line":
            offset_list = [(0, 0), (10, 0), (-10, 0)]
        else:
            offset_list = [(0, 0)]

        existing_count = sum(
            1 for key in self.placed_chip_items
            if key.startswith(spot_id + "_")
        )
        ox, oy = offset_list[min(existing_count, len(offset_list) - 1)]

        center_x = int(round(cx + ox))
        center_y = int(round(cy + oy))

        cid = self.board_canvas.create_oval(
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
            fill=display_fill,
            outline="#d4af37",
            width=2,
            tags=("chips",)
        )

        txt = self.board_canvas.create_text(
            center_x,
            center_y,
            text=self._format_win_amount(display_amount),
            fill=display_text_color,
            font=("Arial", 7, "bold"),
            tags=("chips",)
        )

        self.placed_chip_items[f"{spot_id}_{existing_count}"] = (cid, txt)

    def _remove_chip_items(self, spot_id):
        keys = [k for k in self.placed_chip_items if k.startswith(spot_id + "_")]
        for key in keys:
            items = self.placed_chip_items.pop(key, None)
            if items:
                for item in items:
                    try:
                        self.board_canvas.delete(item)
                    except Exception:
                        pass

    def _repaint_all_chips(self):
        if not hasattr(self, "board_canvas"):
            return
        self.board_canvas.delete("chips")
        self.placed_chip_items = {}
        for spot_id, amount in self.current_bets.items():
            if amount > 0:
                spot = self._find_spot_by_id(spot_id)
                if spot:
                    fill = self.current_bet_colors.get(spot_id, self._chip_fill_color_for_amount(amount))
                    self._draw_chip_on_spot(spot, amount, fill)

    # =====================================================
    # Board click handling
    # =====================================================

    def on_board_click(self, event):
        if self.round_state != "betting":
            return
        spot = self._spot_by_point(event.x, event.y)
        if not spot:
            return
        self.place_bet(spot["id"])

    def on_board_right_click(self, event):
        if self.round_state != "betting":
            return
        spot = self._spot_by_point(event.x, event.y)
        if not spot:
            return
        self.clear_single_bet(spot["id"])

    # =====================================================
    # Betting / settlement
    # =====================================================
    def place_bet(self, spot_id: str):
        if self.round_state != "betting":
            return
        spot = self._find_spot_by_id(spot_id)
        if not spot:
            return

        amount = int(self.selected_bet_amount)
        if amount <= 0:
            return

        limit = self._bet_limit_for_spot(spot)
        existing = self.current_bets.get(spot_id, 0)
        remaining_limit = limit - existing
        if remaining_limit <= 0:
            messagebox.showwarning("投注上限", f"{spot['label']} 已达到最高限红 ${limit:,}")
            return

        actual_amount = min(amount, remaining_limit)
        if self.balance < actual_amount:
            messagebox.showwarning("余额不足", f"余额不足，无法下注 ${actual_amount:,.0f}。")
            return

        self.balance -= actual_amount
        self.current_bets[spot_id] = existing + actual_amount
        self.current_bet_colors[spot_id] = self._chip_fill_color_for_amount(self.current_bets[spot_id])

        self._refresh_balance_display()
        self._refresh_bet_totals()
        self._repaint_all_chips()

        total_bet = sum(self.current_bets.values())
        self.current_chip_label.config(text=f"本局下注金额: ${total_bet:,}")

    def clear_bets(self):
        if self.round_state != "betting":
            return
        refund = sum(self.current_bets.values())
        if refund > 0:
            self.balance += refund
        self.current_bets = {}
        self.current_bet_colors = {}
        self._refresh_balance_display()
        self._refresh_bet_totals()
        self._repaint_all_chips()

        self.current_chip_label.config(
            text=f"上局获胜金额: ${int(getattr(self, 'last_win_amount', 0)):,}"
        )

    def clear_single_bet(self, spot_id: str):
        if self.round_state != "betting":
            return
        amount = self.current_bets.get(spot_id, 0)
        if amount > 0:
            self.balance += amount
            self.current_bets.pop(spot_id, None)
            self.current_bet_colors.pop(spot_id, None)
            self._refresh_balance_display()
            self._refresh_bet_totals()
            self._repaint_all_chips()

    def _refresh_bet_totals(self):
        total_bet = sum(self.current_bets.values())
        if hasattr(self, "current_bet_label"):
            self.current_bet_label.config(text=f"${total_bet:,}")

    def _settle_bets(self, result: str) -> float:
        total_payout = 0.0

        for spot_id, amount in list(self.current_bets.items()):
            spot = self._find_spot_by_id(spot_id)
            if not spot or amount <= 0:
                continue

            if result in spot["numbers"]:
                multiplier = spot["payout"] + 1
                win_amount = amount * multiplier
                total_payout += win_amount
                self.balance += win_amount

        if self.username != "Guest":
            update_balance_in_json(self.username, self.balance)

        self.last_win_amount = int(total_payout)

        self.current_chip_label.config(
            text=f"本局获胜金额: ${self.last_win_amount:,}"
        )
        return total_payout

    # =====================================================
    # Game flow
    # =====================================================
    def _start_new_round(self):
        self._stop_result_flash()
        self.last_spin_data = None

        # 重置暂停相关标志
        self.timer_paused = False
        self.paused_remaining = 0
        if hasattr(self, "pause_timer_btn"):
            self.pause_timer_btn.config(text="暂停倒计时", bg="#F5A623")

        self.result_chip_display = {}
        self.current_bets = {}
        self.current_bet_colors = {}
        self.center_display_result = None

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

        # 重置指针状态：下一局从顶部重新开始
        self.pointer_velocity = 0.0
        self.pointer_acceleration = 0.0
        self.is_pointer_spinning = False

        self._enable_amount_buttons()
        self._set_control_buttons_state(tk.NORMAL)
        self._set_bet_buttons_state(tk.NORMAL)

        self._refresh_bet_totals()

        self._draw_wheel()
        self._repaint_all_chips()

        self.betting_deadline = time.time() + self.BETTING_SECONDS
        self._update_countdown()

        # 重新添加帮助按钮（因为上面delete了all）
        self._add_help_button_on_board()

    def _update_countdown(self):
        if self.timer_paused:
            # 暂停时不更新倒计时，也不自动结束
            return

        remaining = int(math.ceil(self.betting_deadline - time.time()))
        if remaining < 0:
            remaining = 0

        if hasattr(self, "wheel_timer_id") and self.wheel_timer_id:
            try:
                self.wheel_canvas.itemconfig(self.wheel_timer_id, text=f"{remaining:02d}s")
            except Exception:
                pass

        if remaining <= 0:
            self._countdown_job = None
            self._lock_bets_and_spin()
            return

        self._countdown_job = self.after(self.TIMER_TICK_MS, self._update_countdown)

    def _lock_bets_and_spin(self):
        if self.detail_window and self.detail_window.winfo_exists():
            self.detail_window.destroy()
            self.detail_window = None
        # 存储当前下注数据作为上一局记录（若无下注则保留旧记录）
        self._store_current_bets_as_last()

        # 重置暂停相关状态
        self.timer_paused = False
        self.paused_remaining = 0
        self.pause_timer_btn.config(text="暂停倒计时", bg="#F5A623")

        self.round_state = "spinning"
        self._set_bet_buttons_state(tk.DISABLED)
        self._disable_amount_buttons()
        self._set_control_buttons_state(tk.DISABLED)   # 禁用所有游戏按钮
        self._start_physical_spin()

    def _start_physical_spin(self):
        # 轮盘：保持原本顺时针旋转
        self.wheel_velocity = uuid_uniform(450, 750)
        self.wheel_acceleration = -uuid_uniform(70, 125)

        # 指针：改为逆时针绕着轮盘旋转，速度/减速度同样随机
        self.pointer_angle = 0.0 if not hasattr(self, "pointer_angle") else self.pointer_angle % 360.0
        self.pointer_velocity = uuid_uniform(675, 1075)
        self.pointer_acceleration = -uuid_uniform(115, 180)

        self.is_spinning = True
        self.is_pointer_spinning = True
        self._last_physics_time = time.time()
        self._physics_update()

    def _physics_update(self):
        now = time.time()
        dt = min(0.04, now - self._last_physics_time)
        self._last_physics_time = now

        # 轮盘：顺时针
        self.wheel_velocity = max(0.0, self.wheel_velocity + self.wheel_acceleration * dt)
        self.current_wheel_offset = (self.current_wheel_offset + self.wheel_velocity * dt) % 360.0

        # 指针：逆时针绕轮盘转
        self.pointer_velocity = max(0.0, self.pointer_velocity + self.pointer_acceleration * dt)
        self.pointer_angle = (self.pointer_angle - self.pointer_velocity * dt) % 360.0

        self._draw_wheel()

        # 两者都停下后再结算
        if self.wheel_velocity <= 0 and self.pointer_velocity <= 0:
            self._finish_physical_spin()
            return

        self._spin_job = self.after(max(16, int(dt * 1000)), self._physics_update)

    def _finish_physical_spin(self):
        self.is_spinning = False
        self.is_pointer_spinning = False
        self.wheel_velocity = 0.0
        self.pointer_velocity = 0.0
        self.current_wheel_offset %= 360.0
        self.pointer_angle %= 360.0

        if self._spin_job is not None:
            try:
                self.after_cancel(self._spin_job)
            except Exception:
                pass
            self._spin_job = None

        self._draw_wheel()

        # 中奖结果 = 轮盘当前角度 与 指针当前角度 的相对位置
        step = 360.0 / len(ROULETTE_SEQUENCE)
        raw_index = ((self.pointer_angle - self.current_wheel_offset) / step - 0.5) % len(ROULETTE_SEQUENCE)
        self.current_round_index = int(round(raw_index)) % len(ROULETTE_SEQUENCE)
        self.current_round_result = ROULETTE_SEQUENCE[self.current_round_index]

        self._finish_round(self.current_round_result)
    
    def _draw_orbiting_pointer(self, cx, cy, outer_r):
        """
        绕着轮盘旋转的指针：
        - 白金色金属风格
        - 三角指针始终朝向轮盘中心
        - 带一点赌场灯光感
        """
        angle = getattr(self, "pointer_angle", 0.0) % 360.0
        rad = math.radians(angle)

        # 指针所在点相对轮盘中心的外向单位向量
        ux = math.sin(rad)
        uy = -math.cos(rad)

        # 切线方向
        tx = math.cos(rad)
        ty = math.sin(rad)

        orbit_r = outer_r + 2
        pcx = cx + ux * orbit_r
        pcy = cy + uy * orbit_r

        # 指针几何
        tip_len = 18
        base_len = 19
        half_width = 15

        tip_x = pcx - ux * tip_len
        tip_y = pcy - uy * tip_len

        base_center_x = pcx + ux * base_len
        base_center_y = pcy + uy * base_len

        left_x = base_center_x + tx * half_width
        left_y = base_center_y + ty * half_width

        right_x = base_center_x - tx * half_width
        right_y = base_center_y - ty * half_width

        # 指针阴影
        shadow_dx = 3
        shadow_dy = 3
        self.wheel_canvas.create_polygon(
            left_x + shadow_dx, left_y + shadow_dy,
            right_x + shadow_dx, right_y + shadow_dy,
            tip_x + shadow_dx, tip_y + shadow_dy,
            fill="#000000",
            outline="",
            tags=("pointer_shadow",)
        )

        # 指针主体
        self.wheel_canvas.create_polygon(
            left_x, left_y,
            right_x, right_y,
            tip_x, tip_y,
            fill="#F8F4E8",
            outline="#B08B2D",
            width=2,
            tags=("pointer",)
        )

        # 指针中线高光
        mid_x = (left_x + right_x) / 2
        mid_y = (left_y + right_y) / 2
        self.wheel_canvas.create_line(
            mid_x, mid_y,
            tip_x, tip_y,
            fill="#FFFFFF",
            width=1,
            tags=("pointer",)
        )

        self.wheel_canvas.tag_raise("pointer_shadow")
        self.wheel_canvas.tag_raise("pointer")

    def _get_winning_spot_ids(self, result: str):
        """
        Only straight up bets and outside bets flash.
        不闪的类型：
        split / corner / street / six_line
        """
        flashing_types = {
            "straight",
            "dozen",
            "column",
            "color",
            "odd_even",
            "high_low",
        }

        winning = set()
        for spot in self.bet_spots:
            if spot.get("type") not in flashing_types:
                continue
            if result in spot.get("numbers", set()):
                winning.add(spot["id"])
        return winning

    def _stop_result_flash(self):
        if self._result_flash_job is not None:
            try:
                self.after_cancel(self._result_flash_job)
            except Exception:
                pass
            self._result_flash_job = None
        self._result_flash_state = False
        self._result_flash_spot_ids = set()

    def _redraw_board_for_result_flash(self, flash_on=False):
        if not hasattr(self, "board_canvas"):
            return

        self.board_canvas.delete("all")
        draw_roulette_static(self.board_canvas, scale=BOARD_SCALE)

        if flash_on and self._result_flash_spot_ids:
            for spot_id in self._result_flash_spot_ids:
                spot = self._find_spot_by_id(spot_id)
                if not spot:
                    continue
                x1, y1, x2, y2 = spot["bounds"]
                self.board_canvas.create_rectangle(
                    int(x1), int(y1), int(x2), int(y2),
                    fill="#ffffff",
                    outline="#000000",
                    width=2,
                    tags=("result_flash",)
                )
                self._draw_flash_label(spot, fill="#000000")

        self._repaint_all_chips()

    def _result_flash_tick(self):
        if self.round_state != "result":
            self._stop_result_flash()
            return

        self._result_flash_state = not self._result_flash_state
        self._redraw_board_for_result_flash(flash_on=self._result_flash_state)
        self._result_flash_job = self.after(1000, self._result_flash_tick)

    def _is_flashable_spot(self, spot):
        return spot and spot.get("type") in {
            "straight",      # 单个数字注
            "dozen",         # 外围投注
            "column",
            "color",
            "odd_even",
            "high_low",
        }


    def _get_flashable_winning_spot_ids(self, result: str):
        flash_ids = set()
        for spot_id, amount in self.current_bets.items():
            if amount <= 0:
                continue
            spot = self._find_spot_by_id(spot_id)
            if not spot:
                continue
            if result in spot["numbers"] and self._is_flashable_spot(spot):
                flash_ids.add(spot_id)
        return flash_ids


    def _stop_result_flash(self):
        if self._result_flash_job is not None:
            try:
                self.after_cancel(self._result_flash_job)
            except Exception:
                pass
            self._result_flash_job = None
        self._result_flash_state = False
        self._result_flash_spot_ids = set()

    def _draw_flash_label(self, spot, fill="#ffffff"):
        """
        白色闪烁层上的文字，按原始桌面显示内容重画。
        """
        x1, y1, x2, y2 = spot["bounds"]
        cx, cy = spot["center"]
        t = spot["type"]

        if t == "straight":
            text = spot["label"]  # 0 / 1-36
            font = ("Arial", 11, "bold")
            angle = 90

        elif t == "column":
            text = "2:1"
            font = ("Arial", 11, "bold")
            angle = 90

        elif t == "dozen":
            text = spot["label"]  # 1st 12 / 2nd 12 / 3rd 12
            font = ("Arial", 11, "bold")
            angle = 0

        elif t in {"color", "odd_even"}:
            text = str(spot["label"]).upper()
            font = ("Arial", 11, "bold")
            angle = 0

        elif t == "high_low":
            # 统一显示桌面文字
            if spot["label"] in {"1-18", "1 to 18"}:
                text = "1 to 18"
            else:
                text = "19 to 36"
            font = ("Arial", 11, "bold")
            angle = 0

        else:
            return

        self.board_canvas.create_text(
            cx, cy,
            text=text,
            fill=fill,
            font=font,
            angle=angle,
            tags=("result_flash",)
        )

    def _redraw_board_for_result_flash(self, flash_on=False):
        if not hasattr(self, "board_canvas"):
            return

        self.board_canvas.delete("all")
        draw_roulette_static(self.board_canvas, scale=BOARD_SCALE)

        if flash_on and self._result_flash_spot_ids:
            for spot_id in self._result_flash_spot_ids:
                spot = self._find_spot_by_id(spot_id)
                if not spot:
                    continue

                x1, y1, x2, y2 = spot["bounds"]

                self.board_canvas.create_rectangle(
                    int(x1), int(y1), int(x2), int(y2),
                    fill="#ffffff",
                    outline="#000000",
                    width=2,
                    tags=("result_flash",)
                )
                self._draw_flash_label(spot, fill="#000000")

        self._repaint_all_chips()

    def _finish_round(self, result):
        payout = self._settle_bets(result)

        self.history.add_result(result)
        self.add_marker_result(result)
        self._refresh_balance_display()

        winning_spots = self._get_winning_spot_ids(result)

        # 只保留中奖筹码；没中的全部删掉
        winning_bets = {}
        winning_colors = {}
        self.result_chip_display = {}

        for spot_id, amount in self.current_bets.items():
            spot = self._find_spot_by_id(spot_id)
            if not spot or amount <= 0:
                continue

            if result in spot["numbers"]:
                win_amount = int(amount * (spot["payout"] + 1))
                win_fill, win_text_color = self._result_chip_style(win_amount)

                winning_bets[spot_id] = int(amount)
                winning_colors[spot_id] = self._chip_fill_color_for_amount(amount)

                self.result_chip_display[spot_id] = {
                    "original_amount": int(amount),
                    "original_fill": self._chip_fill_color_for_amount(amount),
                    "original_text_color": self._spot_text_color(self._chip_fill_color_for_amount(amount)),
                    "win_amount": win_amount,
                    "win_fill": win_fill,
                    "win_text_color": win_text_color,
                }

        self.current_bets = winning_bets
        self.current_bet_colors = winning_colors
        self._refresh_bet_totals()

        self.round_state = "result"
        self.center_display_result = result

        # 立即绘制轮盘显示中奖结果（背景色+数字）
        self._draw_wheel()

        self._stop_result_flash()
        self._result_flash_spot_ids = winning_spots
        self._result_flash_state = True

        # 先显示“原色”，下一秒切到白色，再循环
        self._redraw_board_for_result_flash(flash_on=True)
        self._result_flash_job = self.after(1000, self._result_flash_tick)

        self.last_spin_data = {
            "result": result,
            "pointer_angle": self.pointer_angle,               # 指针最终角度（0~360）
            "wheel_offset": self.current_wheel_offset,         # 轮盘最终偏移角度
            "result_index": self.current_round_index,          # 在 ROULETTE_SEQUENCE 中的索引
        }
        # 绑定中心点击事件（如果尚未绑定）
        if not hasattr(self, "_center_click_bound"):
            self.wheel_canvas.bind("<Button-1>", self._on_wheel_click)
            self._center_click_bound = True

        self.after(6000, self._start_new_round)

    def _on_wheel_click(self, event):
        """点击轮盘画布时，判断是否点中中心区域，且处于结果展示阶段"""
        if self.round_state != "result":
            return
        if not self.last_spin_data:
            return

        # 获取画布上轮盘中心坐标
        cx = self.wheel_canvas.winfo_width() / 2
        cy = self.wheel_canvas.winfo_height() / 2 - 8   # 与 _draw_wheel 中的 cy 一致
        dx = event.x - cx
        dy = event.y - cy
        # 内圆半径大约 70（从 _draw_wheel 中 inner_r = 70）
        inner_r = 70
        if (dx * dx + dy * dy) <= inner_r * inner_r:
            self._show_result_details()

    def _show_result_details(self):
        """弹出新窗口，显示本局的技术数据"""
        if self.detail_window is not None and self.detail_window.winfo_exists():
            self.detail_window.lift()
            return

        data = self.last_spin_data
        result = data["result"]
        pointer = data["pointer_angle"]
        offset = data["wheel_offset"]
        idx = data["result_index"]

        step = 360.0 / 37   # 每个扇区角度跨度
        # 扇区边界算法：假设轮盘上第 i 个扇区起始边界（相对于轮盘自身0点）为 i * step
        # 绝对坐标下的起始边界 = (i * step + offset) % 360
        def sector_range(i):
            start = (i * step + offset) % 360
            end = (start + step) % 360
            return start, end

        cur_start, cur_end = sector_range(idx)
        prev_idx = (idx - 1) % 37
        prev_start, prev_end = sector_range(prev_idx)
        next_idx = (idx + 1) % 37
        next_start, next_end = sector_range(next_idx)

        # 构建弹窗
        self.detail_window = tk.Toplevel(self)
        self.detail_window.title("开奖详情")
        self.detail_window.geometry("500x420")
        self.detail_window.resizable(False, False)

        text = f"""
    【本局开奖结果】: {result}

    【指针最终角度】: {pointer:.4f}°

    【上一个数字】: {ROULETTE_SEQUENCE[prev_idx]}
        角度范围: {prev_start:.4f}° ～ {prev_end:.4f}°

    【中奖数字扇区】: {result}
        角度范围: {cur_start:.4f}° ～ {cur_end:.4f}°

    【下一个数字】: {ROULETTE_SEQUENCE[next_idx]}
        角度范围: {next_start:.4f}° ～ {next_end:.4f}°

    说明:
    - 角度以正上方为 0°，顺时针增加。
    - 指针角度是它的绝对方向
    - 扇区范围是轮盘上该数字占据的绝对角度区间。
    - 若结果落在指针指向的扇区内，即为中奖。
        """

        frm = tk.Frame(self.detail_window)
        frm.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        txt = tk.Text(frm, font=("Consolas", 12), wrap=tk.WORD)
        txt.insert(tk.END, text)
        txt.config(state=tk.DISABLED)
        txt.pack(fill=tk.BOTH, expand=True)
        tk.Button(self.detail_window, text="关闭", command=self.detail_window.destroy, font=("Arial", 10)).pack(pady=8)

        # 窗口关闭时清空引用
        self.detail_window.protocol("WM_DELETE_WINDOW", self._close_detail_window)

    def _close_detail_window(self):
        if self.detail_window:
            self.detail_window.destroy()
            self.detail_window = None
    # =====================================================
    # Misc / controls
    # =====================================================

    def _set_bet_buttons_state(self, state):
        pass

    def _enable_amount_buttons(self):
        for chip in self.chip_buttons:
            chip["canvas"].config(state=tk.NORMAL)
            chip["canvas"].bind("<Button-1>", lambda e, t=chip["text"], c=chip["canvas"], cid=chip["chip_id"], bg=chip.get("bg_color", "#ffffff"): self._set_bet_amount(t, c, cid, bg))

    def _disable_amount_buttons(self):
        for chip in self.chip_buttons:
            chip["canvas"].config(state=tk.DISABLED)
            chip["canvas"].unbind("<Button-1>")

    def _set_control_buttons_state(self, state):
        """
        控制游戏相关按钮的状态（清除下注、重复上局下注、暂停倒计时、开始游戏）
        state: tk.NORMAL 或 tk.DISABLED
        """
        self.deal_button.config(state=state)
        self.reset_button.config(state=state)
        self.repeat_last_btn.config(state=state)
        self.pause_timer_btn.config(state=state)
        
        # 如果是在投注阶段启用按钮，重复按钮还需要根据余额和上一局数据单独控制
        if state == tk.NORMAL:
            self._update_repeat_button_state()

    def _refresh_balance_display(self):
        self.balance_label_side.config(text=f"余额: ${self.balance:,.2f}")
        if self.username != "Guest":
            update_balance_in_json(self.username, self.balance)
        self._update_repeat_button_state()   # 余额变化时更新重复按钮状态

    def on_close(self):
        try:
            if self.username != "Guest":
                update_balance_in_json(self.username, self.balance)
        except Exception:
            pass
        self.destroy()

    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("欧式轮盘 玩法说明")
        win.geometry("720x560")
        win.resizable(False, False)
        text = (
            "欧式轮盘 玩法说明\n\n"
            "1. 每局下注时间为 30 秒。\n"
            "2. 时间结束后，所有下注会锁定，轮盘开始旋转。\n"
            "3. 轮盘停止时，最上方指针指向的格子为中奖结果。\n\n"
            "4. 单注类型和赔率（净赢）：\n"
            "   - 直注 Straight Up：35:1\n"
            "   - 分注 Split：17:1\n"
            "   - 街注 Street：11:1\n"
            "   - 角注 Corner：8:1\n"
            "   - 六线注 Six Line：5:1\n"
            "   - 打一打 / Dozen：2:1\n"
            "   - 选号列 / Column：2:1\n"
            "   - 红 / 黑：1:1\n"
            "   - 单 / 双：1:1\n"
            "   - 大 / 小（1-18 / 19-36）：1:1\n\n"
            "5. 下注在桌面上的位置后，筹码会直接显示在对应下注区域。\n"
            "6. 标记路会显示每次开奖结果的颜色与号码。\n"
        )
        frm = tk.Frame(win)
        frm.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        txt = tk.Text(frm, font=("Arial", 13), wrap=tk.WORD)
        txt.insert(tk.END, text)
        txt.config(state=tk.DISABLED)
        txt.pack(fill=tk.BOTH, expand=True)
        tk.Button(win, text="关闭", command=win.destroy, font=("Arial", 12, "bold"), width=10).pack(pady=10)

    def start_game(self):
        """强制开始游戏：下注阶段立即旋转，结果阶段跳转到新的一局"""
        if self.round_state == "betting":
            # 取消倒计时，立即开始旋转
            if self._countdown_job is not None:
                try:
                    self.after_cancel(self._countdown_job)
                except Exception:
                    pass
                self._countdown_job = None
            self._lock_bets_and_spin()

def main(initial_balance=1_000_000, username="Guest"):
    app = RouletteGameGUI(initial_balance=initial_balance, username=username)
    app.mainloop()
    return app.balance


if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")