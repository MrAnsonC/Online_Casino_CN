import tkinter as tk
from tkinter import ttk, messagebox
import random
import json
import os
import time
import math
from datetime import datetime

def get_data_file_path():
    # 用于获取保存数据的文件路径
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')

# 获取历史记录文件路径
def get_history_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../A_Logs/stock_market.json')

# 保存用户数据
def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

# 读取用户数据
def load_user_data():
    file_path = get_data_file_path()
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)
    
def update_balance_in_json(username, new_balance):
    users = load_user_data()  # 先加载现有用户数据
    for user in users:
        if user['user_name'] == username:  # 查找当前用户
            user['cash'] = f"{new_balance:.2f}"  # 更新余额
            break
    save_user_data(users)  # 保存更新后的数据

# 保存历史记录到文件
def save_history_to_file(history_dict):
    file_path = get_history_file_path()
    # 确保目录存在
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(history_dict, f, ensure_ascii=False, indent=4)

# 加载历史记录从文件
def load_history_from_file():
    file_path = get_history_file_path()
    # 如果文件不存在，返回默认的空历史记录
    if not os.path.exists(file_path):
        # 创建默认的20条历史记录，全部为0
        default_history = {f"{i:02d}": 0 for i in range(1, 21)}
        save_history_to_file(default_history)
        return default_history
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            history = json.load(f)
            # 确保历史记录有20条
            if len(history) < 20:
                for i in range(len(history) + 1, 21):
                    history[f"{i:02d}"] = 0
            return history
    except (json.JSONDecodeError, FileNotFoundError):
        # 如果文件损坏或读取失败，返回默认历史记录
        default_history = {f"{i:02d}": 0 for i in range(1, 21)}
        save_history_to_file(default_history)
        return default_history

# 更新历史记录：添加新结果，移动旧记录
def update_history_in_file(new_percent):
    # 加载当前历史记录
    history = load_history_from_file()
    
    # 移动历史记录：01->02, 02->03, ..., 19->20
    for i in range(19, 0, -1):
        old_key = f"{i:02d}"
        new_key = f"{i+1:02d}"
        if old_key in history:
            history[new_key] = history[old_key]
    
    # 添加新记录到01位置（整数形式，不带小数）
    history["01"] = int(round(new_percent))
    
    # 保存更新后的历史记录
    save_history_to_file(history)
    return history

# 股票价格变动概率分布
price_changes = {
    1: 0.34,   # 1% 变动
    2: 0.23,   # 2% 变动
    3: 0.13,   # 3% 变动
    4: 0.08,   # 4% 变动
    5: 0.07,   # 5% 变动
    6: 0.06,   # 6% 变动
    7: 0.06,   # 7% 变动
    8: 0.05,   # 8% 变动
    9: 0.04,   # 9% 变动
    10: 0.03   # 10% 变动
}

class CircleButton(tk.Canvas):
    """自定义圆形按钮"""
    def __init__(self, master, text, bg_color, fg_color, command=None, radius=30, 
                 border_color="#16213e", border_width=2, *args, **kwargs):
        super().__init__(master, width=radius*2, height=radius*2, 
                         highlightthickness=0, bg="#16213e", *args, **kwargs)  # 背景色与父容器一致
        self.radius = radius
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.text = text
        self.command = command
        self.border_color = border_color
        self.border_width = border_width
        self.border_id = None  # 边框对象ID
        
        # 绘制圆形按钮
        self.create_oval(0, 0, radius*2, radius*2, fill=bg_color, outline="#16213e", width=2)
        # 修改字体大小为18
        self.create_text(radius, radius, text=text, fill=fg_color, 
                        font=("Arial", 18, "bold"))  # 字体大小从10改为18
        
        # 添加边框
        self.add_border()
        
        # 绑定点击事件
        self.bind("<Button-1>", self.on_click)
    
    def add_border(self):
        """添加边框"""
        # 创建一个稍大的圆形作为边框
        border_padding = 1  # 边框内边距，让边框更靠近圆形
        self.border_id = self.create_oval(
            self.border_width - border_padding, 
            self.border_width - border_padding, 
            self.radius*2 - self.border_width + border_padding, 
            self.radius*2 - self.border_width + border_padding,
            outline=self.border_color, 
            width=self.border_width
        )
    
    def change_border_color(self, new_color):
        """修改边框颜色"""
        self.border_color = new_color
        self.itemconfig(self.border_id, outline=new_color)
    
    def on_click(self, event):
        if self.command:
            self.command()

class StockChart(tk.Canvas):
    """股票图表"""
    def __init__(self, master, width=500, height=200, *args, **kwargs):
        super().__init__(master, width=width, height=height, 
                        bg="#0f3460", highlightthickness=0, *args, **kwargs)
        self.width = width
        self.height = height
        self.points = []  # 存储价格点 (x, y)
        self.base_price = 100  # 起始价格
        self.current_price = 100  # 当前价格
        self.max_points = 230  # 最多显示200个点（10秒/0.05秒）
            
    def update_chart(self, new_price_percent):
        """
        更新图表数据并重绘。
        new_price_percent: 相对于 base_price 的百分比变化（例如 -5 表示 -5%）
        横向刻度线只绘制到 x_pos_200（200 点参考线的位置）。
        右侧刻度数字固定放在 x=210（或在画布宽度允许范围内的最大值），并左对齐。
        """
        # 更新当前价格（基于百分比）
        self.current_price = self.base_price * (1 + new_price_percent / 100.0)

        # 限制价格范围，避免显示异常值
        if self.current_price > self.base_price * 2:
            self.current_price = self.base_price * 2
        elif self.current_price < 0:
            self.current_price = 0

        # 画布内边距
        top_margin = 8
        bottom_margin = 8
        effective_height = max(self.height - top_margin - bottom_margin, 1)

        # 将 new_price_percent（范围 -100 .. +100）归一化到 [0..1]，0->底部(-100)，1->顶部(+100)
        pct = max(min(new_price_percent, 100.0), -100.0)
        normalized_from_bottom = (pct + 100.0) / 200.0

        # 计算 y（像素）
        y = top_margin + (1.0 - normalized_from_bottom) * effective_height

        # x 计算（横向滚动逻辑保持不变）
        if len(self.points) < self.max_points:
            x = len(self.points) * (self.width / self.max_points)
        else:
            step = (self.width / self.max_points)
            self.points = [(x - step, y) for x, y in self.points[1:]]
            x = self.width

        # 添加新点
        self.points.append((x, y))

        # 清空画布并重绘
        self.delete("all")

        # 计算 200 点参考线的横向位置（用于限制横向刻度线长度）
        try:
            if self.max_points and self.max_points >= 200:
                x_pos_200 = (self.width / float(self.max_points)) * 200.0
                x_pos_200 = max(0.0, min(self.width, x_pos_200))
            else:
                x_pos_200 = self.width
        except Exception:
            x_pos_200 = self.width

        # --- 绘制横向刻度线（只绘制到 x_pos_200）和右侧刻度数字（放在 x=210 左对齐） ---
        # 文字的固定 x 位置，尽量保留在 210 左对齐；若画布不足宽则退到 self.width - 30
        label_x_fixed = 515
        if label_x_fixed > self.width - 30:
            label_x_fixed = max(10, self.width - 30)  # 避免越界

        for j in range(5):
            # j=0 -> -100 (最底); j=4 -> 100 (最顶)
            label_value = -100 + j * 50
            y_pos = top_margin + (1.0 - ((label_value + 100) / 200.0)) * effective_height
            y_pos = max(top_margin, min(self.height - bottom_margin, y_pos))

            if label_value in (100, -100):
                line_color = "#FF0000"
            elif label_value in (50, -50):
                line_color = "#ffd369"
            else:
                line_color = "#2d4059"

            # 横线：从左侧到 x_pos_200（不再延伸整列）
            self.create_line(0, y_pos, x_pos_200, y_pos, fill=line_color, width=1)

            # 右侧刻度文字 — 固定在 label_x_fixed，并左对齐（anchor='w'）
            # 使用左对齐：文字从 label_x_fixed 开始向右画
            self.create_text(
                label_x_fixed, y_pos,
                text=str(label_value),
                fill="#bdc3c7",
                font=("Arial", 12),
                anchor='w'  # 左对齐
            )

        # 绘制折线（涨为绿色，跌为红色）
        if len(self.points) > 1:
            for i in range(1, len(self.points)):
                x1, y1 = self.points[i - 1]
                x2, y2 = self.points[i]
                color = "#e74c3c" if y2 <= y1 else "#27ae60"
                self.create_line(x1, y1, x2, y2, fill=color, width=2)

        # 绘制当前点标记
        last_x, last_y = self.points[-1]
        self.create_oval(
            last_x - 3, last_y - 3,
            last_x + 3, last_y + 3,
            fill="#4cc9f0", outline="#4cc9f0"
        )

        # 中心虚线（基线）——与 0% 对齐，长度同样限制到 x_pos_200
        zero_normalized = (0.0 + 100.0) / 200.0
        y_center = top_margin + (1.0 - zero_normalized) * effective_height
        self.create_line(0, y_center, x_pos_200, y_center, fill="#ffffff", width=1, dash=(2, 2))

        # 200 点参考线（竖线）
        try:
            if self.max_points and self.max_points >= 200:
                if 0 <= x_pos_200 <= self.width:
                    self.create_line(x_pos_200, 0, x_pos_200, self.height, fill="#000000", width=3)
        except Exception:
            pass

        percent_change = ((self.current_price - self.base_price) / self.base_price) * 100.0
        return percent_change

class HistoryBar(tk.Canvas):
    """历史记录条"""
    def __init__(self, master, width=400, height=250, *args, **kwargs):
        super().__init__(master, width=width, height=height, bg="#0f3460", highlightthickness=0, *args, **kwargs)
        self.width = width
        self.height = height
        self.history = []  # 存储历史记录（正数表示上涨，负数表示下跌）
        self.max_history = 20

    def add_result(self, result_percent):
        """添加新的历史记录并重绘"""
        self.history.append(result_percent)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        self.draw_history()
    
    def set_history(self, history_list):
        """直接设置历史记录列表"""
        self.history = history_list[-self.max_history:]  # 只保留最多max_history条
        self.draw_history()

    def draw_history(self):
        """绘制历史记录（美化版）"""
        self.delete("all")

        # 绘制背景（保留画布背景）
        max_slots = self.max_history
        hist = self.history[-max_slots:]
        n = len(hist)

        # 获取画布实际尺寸（优先使用运行时真实尺寸，回退到配置值）
        try:
            actual_width = self.winfo_width()
            if actual_width <= 1:
                actual_width = int(self.cget("width"))
        except Exception:
            actual_width = getattr(self, "width", 400)

        try:
            actual_height = self.winfo_height()
            if actual_height <= 1:
                actual_height = int(self.cget("height"))
        except Exception:
            actual_height = getattr(self, "height", 250)

        # 槽间距与槽宽（固定 max_slots 个槽位，右对齐显示最近 N 条）
        gap = 6
        # 防止负值和极小宽度
        slot_width = max(18, (actual_width - (max_slots + 1) * gap) / max_slots) if actual_width > 0 else 18
        slot_width = float(slot_width)

        # 计算起始 x，使全部 slots 右对齐（保证固定 max_slots 个槽位）
        total_width_used = max_slots * slot_width + (max_slots + 1) * gap
        start_x = max(0, actual_width - total_width_used)

        baseline = actual_height / 2.0
        max_visual_percent = 50.0  # 用于高度归一化（50% -> 最大高度）

        # 每个槽位的绘制
        for slot_index in range(max_slots):
            x1 = start_x + gap + slot_index * (slot_width + gap)
            x2 = x1 + slot_width

            # 对应数据索引（右对齐）
            data_offset = max_slots - n
            if slot_index < data_offset:
                # 空槽：暗色小卡片
                y_top = 6
                y_bottom = max(6, actual_height - 6)
                self.create_rectangle(x1, y_top, x2, y_bottom, fill="#081826", outline="#0f2740", width=1)
            else:
                val = hist[slot_index - data_offset]
                # 归一化高度
                height_ratio = min(abs(val) / max_visual_percent, 1.0)
                bar_half_height = max(2.0, (actual_height / 2.0 - 16.0) * height_ratio)  # 留边距，避免为0

                if val > 0:
                    y1 = baseline - bar_half_height
                    y2 = baseline
                    color = "#e74c3c"  # 上涨（红）
                    txt_color = "#ffffff"
                elif val < 0:
                    y1 = baseline
                    y2 = baseline + bar_half_height
                    color = "#27ae60"  # 下跌（绿）
                    txt_color = "#ffffff"
                else:
                    # 平手显示为中性小条（黄色）
                    y1 = baseline - 20
                    y2 = baseline + 20
                    color = "#ffd369"
                    txt_color = "#000000"

                # 画条形
                self.create_rectangle(x1, y1, x2, y2, fill=color, outline="#0b1114", width=1)

                # 百分比文本：**不带符号**（始终显示绝对值，如 "56%"）
                percent_text = f"{abs(val):.0f}"
                text_font = ("Arial", 9, "bold")

                text_x = (x1 + x2) / 2.0
                if val > 0:
                    text_y = y1 - 8
                elif val < 0:
                    text_y = y2 + 8
                else:
                    text_y = baseline
                self.create_text(text_x, text_y, text=percent_text, fill=txt_color, font=text_font)

        # 绘制基准线（中线），只绘制到可视槽位区域
        self.create_line(start_x, baseline, start_x + total_width_used, baseline, fill="#13202a", width=1)

class StockMarketGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("股市风云")
        self.root.geometry("1070x650+50+10")
        self.root.resizable(0,0)
        self.root.configure(bg="#1a1a2e")
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 游戏数据
        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount_up = 0.0  # 上涨区下注金额
        self.bet_amount_down = 0.0  # 下跌区下注金额
        self.game_active = False  # 游戏是否进行中
        self.timer_active = False  # 倒计时是否进行中
        self.last_win = 0.0
        self.current_price_percent = 0.0  # 当前价格变化百分比
        self.cumulative_net_since_cashout = 0.0
        self.starting_price = 100  # 起始价格
        self.result_history = []  # 历史记录
        self.bet_direction = None  # 下注方向：'up' 或 'down'
        self.chip_buttons = []  # 存储筹码按钮的引用
        self.timer_id = None  # 定时器ID
        self.selected_chip = 5.0  # 默认选中的筹码金额为5
        self.original_bet_up = 0.0  # 上涨区原始下注金额
        self.original_bet_down = 0.0  # 下跌区原始下注金额
        self.current_selected_chip_button = None  # 当前选中的筹码按钮
        
        # 加载历史记录
        self.load_history_data()
        
        # 创建UI
        self.create_widgets()
        self.update_display()
        self.start_countdown()  # 首次加载开始倒计时
            
    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 左侧区域
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # 标题
        tk.Label(
            left_frame,
            text="股市风云",
            font=("Arial", 20, "bold"),
            bg="#16213e",
            fg="#e94560"
        ).pack(pady=(10, 4))

        # 当前百分比显示（在标题和图表之间）
        self.percent_var = tk.StringVar(value="当前: 0%")
        self.percent_label = tk.Label(
            left_frame,
            textvariable=self.percent_var,
            font=("Arial", 16, "bold"),
            bg="#16213e",
            fg="#ffd369"
        )
        self.percent_label.pack(pady=(0, 6))

        # 图表框架
        chart_frame_height = 250
        chart_frame = tk.Frame(left_frame, bg="#0f3460", height=chart_frame_height)
        chart_frame.pack(fill=tk.X, padx=10, pady=(5, 5))
        chart_frame.pack_propagate(False)

        # 股票图表
        self.stock_chart = StockChart(chart_frame, width=580, height=200)

        # 将画布锚定在容器顶部，避免纵向 expand 导致空白
        self.stock_chart.pack(anchor='n', pady=(20, 10))

        # 买涨 / 买跌按钮区域（下面内容保持原样）
        bet_direction_frame = tk.Frame(left_frame, bg="#16213e")
        bet_direction_frame.pack(fill=tk.X, padx=10, pady=5)

        center_frame = tk.Frame(bet_direction_frame, bg="#16213e")
        center_frame.pack(expand=True)

        buttons_frame = tk.Frame(center_frame, bg="#16213e")
        buttons_frame.pack()

        self.up_button_text_var = tk.StringVar(value="买涨 ↑\n$0.00")
        self.up_button = tk.Button(
            buttons_frame, textvariable=self.up_button_text_var,
            font=("Arial", 12, "bold"),
            bg="#e74c3c", fg="white",
            width=15, height=2,
            command=lambda: self.add_bet('up')
        )
        self.up_button.pack(side=tk.LEFT, padx=10)

        self.down_button_text_var = tk.StringVar(value="买跌 ↓\n$0.00")
        self.down_button = tk.Button(
            buttons_frame, textvariable=self.down_button_text_var,
            font=("Arial", 12, "bold"),
            bg="#27ae60", fg="white",
            width=15, height=2,
            command=lambda: self.add_bet('down')
        )
        self.down_button.pack(side=tk.LEFT, padx=10)

        # 兑现按钮（放在方向按钮下方）
        cashout_frame = tk.Frame(left_frame, bg="#16213e")
        cashout_frame.pack(fill=tk.X, padx=10, pady=5)

        self.cashout_button = tk.Button(
            cashout_frame, text="兑现", font=("Arial", 12, "bold"),
            bg="#3498db", fg="white", width=15, height=1, command=self.cashout
        )
        self.cashout_button.pack()

        # 历史记录（高度调整为 60）
        history_frame = tk.Frame(left_frame, bg="#0f3460")
        history_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        tk.Label(history_frame, text="过去20局历史记录:", font=("Arial", 10),
                bg="#0f3460", fg="#f1f1f1").pack(anchor=tk.W, pady=(5, 2))

        # 这里把高度设为 60（比原来 +30px）
        self.history_bar = HistoryBar(history_frame, width=600, height=80)
        self.history_bar.pack(fill=tk.X, pady=(0, 5))

        # 右侧 - 控制面板（保留原样）
        right_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        # 余额显示
        balance_frame = tk.Frame(right_frame, bg="#16213e")
        balance_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(balance_frame, text="余额:", font=("Arial", 14),
                bg="#16213e", fg="#f1f1f1").pack(side=tk.LEFT)

        self.balance_var = tk.StringVar()
        self.balance_var.set(f"${self.balance:.2f}")
        tk.Label(balance_frame, textvariable=self.balance_var, font=("Arial", 14, "bold"),
                bg="#16213e", fg="#ffd369").pack(side=tk.LEFT, padx=(5, 0))

        # 筹码按钮（修改：添加边框）
        chips_frame = tk.Frame(right_frame, bg="#16213e")
        chips_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        chips = [
            ("$5", '#ff0000', 'white'),
            ("$25", '#00ff00', 'black'),
            ("$100", '#000000', 'white'),
            ("$500", "#FF7DDA", 'black'),
            ("$1K", '#ffffff', 'black')
        ]

        self.chip_buttons = []
        for i, (text, bg_color, fg_color) in enumerate(chips):
            # 预设$5筹码边框为金色，其他为白色
            if i == 0:  # $5筹码
                border_color = "#ffd369"  # 金色边框
            else:
                border_color = "#16213e"  # 白色边框
                
            btn = CircleButton(
                chips_frame, text=text, bg_color=bg_color, fg_color=fg_color,
                command=lambda t=text: self.select_chip(t),
                border_color=border_color,  # 设置边框颜色
                border_width=3  # 边框宽度
            )
            btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.chip_buttons.append(btn)
            
            # 记录$5筹码为当前选中的按钮
            if i == 0:
                self.current_selected_chip_button = btn

        # 游戏信息（保留原样）
        info_frame = tk.Frame(right_frame, bg="#16213e")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(info_frame, text="游戏规则:", font=("Arial", 18, "bold"),
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, pady=(0, 5))

        rules = [
            "1. 选择下注金额和方向(买涨 或 买跌)",
            "2. 倒计时结束后游戏自动开始",
            "3. 股票随机涨跌，结果完全随机",
            "4. 游戏结束后自动结算",
            "5. 点击'兑现'按钮获取收益",
            "6. 获胜时，系统会在收益中抽取5%手续费",
            "7. 下注<5元时，自动兑现",
        ]

        for rule in rules:
            tk.Label(info_frame, text=rule, font=("Arial", 14),
                    bg="#16213e", fg="#bdc3c7", justify=tk.LEFT).pack(anchor=tk.W, pady=2)

        # 上局结果与本局/累计 盈亏显示 — 合并为单行 "上局结果：{status}"
        win_frame = tk.Frame(right_frame, bg="#16213e")
        win_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # 新增：本局/累计 盈亏显示（默认空）
        self.result_win_or_loss_var = tk.StringVar()
        self.result_win_or_loss_var.set("")
        self.result_win_or_loss_label = tk.Label(win_frame, textvariable=self.result_win_or_loss_var,
                                                font=("Arial", 11, "bold"), bg="#16213e", fg="#ffd369")
        self.result_win_or_loss_label.pack(anchor=tk.W, pady=(2, 0))

        # 合并（初始显示为 未开始）
        self.last_result_var = tk.StringVar()
        self.last_result_var.set("结果：未开始")
        # 这是合并后唯一的"上局结果"标签（颜色会在 finish_game 中按涨跌调整）
        self.last_result_label = tk.Label(win_frame, textvariable=self.last_result_var,
                                        font=("Arial", 18, "bold"), bg="#16213e", fg="#4cc9f0")
        self.last_result_label.pack(anchor=tk.W, pady=(5, 0))

        # 倒计时显示（合并为一行）
        timer_frame = tk.Frame(right_frame, bg="#16213e")
        timer_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # 创建合并的 timer 字符串变量，初始显示（若 self.countdown 未定义则显示默认）
        self.timer_var = tk.StringVar()
        # 如果已有 countdown（如首次 start_countdown 之前），展示默认 12 秒样式，否则显示未开始
        init_seconds = getattr(self, 'countdown', 12)
        self.timer_var.set(f"下一局倒计时: {init_seconds}秒")
        tk.Label(timer_frame, textvariable=self.timer_var, font=("Arial", 20, "bold"),
                bg="#16213e", fg="#ffd369").pack(anchor=tk.W, pady=(5, 0))

        # 状态信息
        self.status_var = tk.StringVar()
        self.status_var.set("请选择下注金额和方向")
        status_label = tk.Label(right_frame, textvariable=self.status_var,
                            font=("Arial", 14), bg="#16213e", fg="#ffd369")
        status_label.pack(fill=tk.X, padx=10, pady=(0, 10))
    
    def load_history_data(self):
        """加载历史记录数据"""
        history_dict = load_history_from_file()
        
        # 将历史记录转换为列表，按顺序从01到20（01为最新，20为最旧）
        # 我们需要反转顺序，因为历史记录条从左到右显示最旧到最新
        history_list = []
        for i in range(20, 0, -1):
            key = f"{i:02d}"
            if key in history_dict:
                history_list.append(history_dict[key])
        
        # 存储到游戏历史记录中
        self.result_history = history_list
    
    def select_chip(self, amount_text):
        """选择筹码金额"""
        try:
            # 处理特殊格式（如$1K）
            if amount_text == "$1K":
                amount_val = 1000.0
            else:
                # 去掉$符号并转换为浮点数
                amount_val = float(amount_text[1:])
            
            self.selected_chip = amount_val
            
            # 将所有筹码边框改为白色
            for btn in self.chip_buttons:
                btn.change_border_color("#16213e")
            
            # 找到被点击的筹码按钮并将其边框改为金色
            for btn in self.chip_buttons:
                # 获取按钮上的文本
                btn_text = btn.text
                if btn_text == amount_text:
                    btn.change_border_color("#ffd369")  # 金色边框
                    self.current_selected_chip_button = btn
                    break
                
        except ValueError:
            pass
    
    def add_bet(self, direction):
        """添加下注（允许在倒计时期间下注，但游戏进行中禁止下注）"""
        # 仅当游戏正在运行时禁止下注
        if self.game_active:
            return

        # 检查余额是否足够
        if self.selected_chip > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注")
            return

        # 设置下注方向（记录最后一次选择的方向）
        self.bet_direction = direction

        # 根据下注方向添加到相应的区域并扣款
        if direction == 'up':
            self.bet_amount_up += self.selected_chip
            self.balance -= self.selected_chip
            # 按钮视觉反馈：按下一侧，下侧为非按下样式
            self.up_button.configure(bg="#c0392b", relief=tk.SUNKEN)
            self.down_button.configure(bg="#27ae60", relief=tk.RAISED)
        else:
            self.bet_amount_down += self.selected_chip
            self.balance -= self.selected_chip
            self.down_button.configure(bg="#229954", relief=tk.SUNKEN)
            self.up_button.configure(bg="#e74c3c", relief=tk.RAISED)

        # 更新显示（余额、按钮文本、状态）
        self.update_display()
        self.update_direction_buttons_text()
        self.update_status()
        
    def update_direction_buttons_text(self):
        """更新方向按钮的文本显示

        - 游戏进行中（game_active=True）：显示"当前价值"（基于 original_bet_* 与 current_price_percent）
        - 游戏未进行时：显示已下注金额（bet_amount_*）
        """
        # 游戏进行中：显示即时计算的价值（并防止负值显示）
        if self.game_active:
            # 上涨区（当前价值 = original_bet_up * (1 + 当前百分比/100)）
            if self.original_bet_up > 0:
                current_value_up = self.original_bet_up * (1 + self.current_price_percent / 100)
                if current_value_up < 0:
                    current_value_up = 0.0
                self.up_button_text_var.set(f"买涨 ↑\n${current_value_up:.2f}")
            else:
                self.up_button_text_var.set("买涨 ↑\n$0.00")

            # 下跌区（当前价值 = original_bet_down * (1 - 当前百分比/100)）
            if self.original_bet_down > 0:
                current_value_down = self.original_bet_down * (1 - self.current_price_percent / 100)
                if current_value_down < 0:
                    current_value_down = 0.0
                self.down_button_text_var.set(f"买跌 ↓\n${current_value_down:.2f}")
            else:
                self.down_button_text_var.set("买跌 ↓\n$0.00")
        else:
            # 非游戏中：显示实际已下注金额
            self.up_button_text_var.set(f"买涨 ↑\n${self.bet_amount_up:.2f}")
            self.down_button_text_var.set(f"买跌 ↓\n${self.bet_amount_down:.2f}")
    
    def cashout(self):
        """
        兑现当前下注区的全部金额：
        - 将 bet_amount_up + bet_amount_down 加回 balance
        - 清空下注区（并重置 original_bet_*）
        - 更新显示和状态
        - 显示自上次兑现以来的累计盈亏（然后重置累计）
        """
        total = float(self.bet_amount_up) + float(self.bet_amount_down)
        if total <= 0:
            # 无下注，无需操作，但仍显示累计盈亏（如果有）
            if hasattr(self, 'cumulative_net_since_cashout') and self.cumulative_net_since_cashout != 0.0:
                cum = self.cumulative_net_since_cashout
                if cum > 0:
                    self.result_win_or_loss_var.set(f"总共盈利了 ${cum:.2f}")
                    self.result_win_or_loss_label.configure(fg="#27ae60")
                elif cum < 0:
                    self.result_win_or_loss_var.set(f"总共亏损了 ${abs(cum):.2f}")
                    self.result_win_or_loss_label.configure(fg="#e74c3c")
                else:
                    self.result_win_or_loss_var.set("平手")
                    self.result_win_or_loss_label.configure(fg="#ffd369")
                # 重置累计（已兑现）
                self.cumulative_net_since_cashout = 0.0
            return

        # 将下注区金额返还到余额
        self.balance = float(self.balance) + total

        # 清空下注区与原始下注记录（以免与下一轮冲突）
        self.bet_amount_up = 0.0
        self.bet_amount_down = 0.0
        self.original_bet_up = 0.0
        self.original_bet_down = 0.0

        # 显示自上次兑现以来的累计盈亏，然后重置累计
        if not hasattr(self, 'cumulative_net_since_cashout'):
            self.cumulative_net_since_cashout = 0.0

        cum = self.cumulative_net_since_cashout
        if cum > 0:
            self.result_win_or_loss_var.set(f"总共盈利了 ${cum:.2f}")
            self.result_win_or_loss_label.configure(fg="#27ae60")
        elif cum < 0:
            self.result_win_or_loss_var.set(f"总共亏损了 ${abs(cum):.2f}")
            self.result_win_or_loss_label.configure(fg="#e74c3c")
        else:
            self.result_win_or_loss_var.set("平手")
            self.result_win_or_loss_label.configure(fg="#ffd369")

        # 重置累计（已兑现）
        self.cumulative_net_since_cashout = 0.0

        # 更新界面与按钮文本
        try:
            self.update_direction_buttons_text()
        except Exception:
            pass
        try:
            self.update_display()
        except Exception:
            pass
        try:
            self.update_status()
        except Exception:
            pass
    
    def auto_cashout_small_bets(self):
        """自动兑现小于5元的下注"""
        total_cashed = 0.0

        if self.bet_amount_up < 5 and self.bet_amount_up > 0:
            self.balance += self.bet_amount_up
            total_cashed += self.bet_amount_up
            self.bet_amount_up = 0.0
            self.original_bet_up = 0.0

        if self.bet_amount_down < 5 and self.bet_amount_down > 0:
            self.balance += self.bet_amount_down
            total_cashed += self.bet_amount_down
            self.bet_amount_down = 0.0
            self.original_bet_down = 0.0

        if total_cashed > 0:
            # 如果两个区域都小于5元，重置按钮样式
            if self.bet_amount_up == 0 and self.bet_amount_down == 0:
                self.up_button.configure(bg="#e74c3c", relief=tk.RAISED)
                self.down_button.configure(bg="#27ae60", relief=tk.RAISED)
                self.bet_direction = None

            # 在自动兑现时，显示自上次兑现以来的累计盈亏（若有）
            if not hasattr(self, 'cumulative_net_since_cashout'):
                self.cumulative_net_since_cashout = 0.0

            cum = self.cumulative_net_since_cashout
            if cum > 0:
                self.result_win_or_loss_var.set(f"总共盈利了 ${cum:.2f}")
                self.result_win_or_loss_label.configure(fg="#27ae60")
            elif cum < 0:
                self.result_win_or_loss_var.set(f"总共亏损了 ${abs(cum):.2f}")
                self.result_win_or_loss_label.configure(fg="#e74c3c")
            else:
                # 若没有累计盈亏则清空或显示平手
                self.result_win_or_loss_var.set("平手")
                self.result_win_or_loss_label.configure(fg="#ffd369")

            # 重置累计（自动兑现等同于兑现动作）
            self.cumulative_net_since_cashout = 0.0

            self.update_display()
            self.update_direction_buttons_text()
    
    def update_status(self):
        self.status_var.set("请选择下注金额和方向")
    
    def update_display(self):
        """更新显示"""
        self.balance_var.set(f"${self.balance:.2f}")
    
    def start_countdown(self, countdown=12):
        """开始倒计时"""
        self.timer_active = True
        self.countdown = countdown
        
        # 启用方向按钮
        self.up_button.configure(state=tk.NORMAL)
        self.down_button.configure(state=tk.NORMAL)
        self.cashout_button.configure(state=tk.NORMAL)
        
        # 启用筹码按钮
        for btn in self.chip_buttons:
            btn.configure(state=tk.NORMAL)
        
        # 自动兑现小于5元的注
        self.auto_cashout_small_bets()
        
        # 初始化时加载历史记录到历史记录条
        if hasattr(self, 'result_history') and self.result_history:
            self.history_bar.set_history(self.result_history)
        
        self.update_timer()
    
    def update_timer(self):
        """更新倒计时"""
        if self.countdown > 0:
            self.timer_var.set(f"下一局倒计时: {self.countdown}秒")
            self.countdown -= 1
            self.timer_id = self.root.after(1000, self.update_timer)
        else:
            self.timer_var.set("下一局倒计时: 游戏中")
            self.timer_active = False
            self.start_game_auto()
    
    def start_game_auto(self):
        """自动开始游戏"""
        # 无论是否有下注，都开始游戏
        self.start_game()
    
    def start_game(self):
        """开始游戏"""
        if self.game_active:
            return
        
        # 保存原始下注金额
        self.original_bet_up = self.bet_amount_up
        self.original_bet_down = self.bet_amount_down
        
        # 设置游戏状态
        self.game_active = True
        
        # 禁用所有按钮
        self.up_button.configure(state=tk.DISABLED)
        self.down_button.configure(state=tk.DISABLED)
        self.cashout_button.configure(state=tk.DISABLED)
        for btn in self.chip_buttons:
            btn.configure(state=tk.DISABLED)
        
        # 重置图表
        self.stock_chart.points = []
        self.stock_chart.current_price = self.stock_chart.base_price
        self.current_price_percent = 0.0
        
        # 开始游戏循环 - 每0.05秒更新一次
        self.game_duration = 10  # 10秒
        self.update_interval = 0.05  # 0.05秒更新一次
        self.updates_per_second = int(1 / self.update_interval)
        self.total_updates = int(self.game_duration / self.update_interval)
        self.current_update = 0
        
        self.run_game_update()
        
    def run_game_update(self):
        """运行游戏更新"""
        if self.current_update >= self.total_updates:
            self.finish_game()
            return

        # 生成随机涨跌
        direction = random.choice(['up', 'down'])  # 50%上涨，50%下跌

        # 根据概率分布选择涨跌幅度
        rand_val = random.random()
        cumulative_prob = 0
        change_percent = 1  # 默认1%

        for percent, prob in price_changes.items():
            cumulative_prob += prob
            if rand_val <= cumulative_prob:
                change_percent = percent
                break

        # 应用涨跌方向
        if direction == 'down':
            change_percent = -change_percent

        # 计算新价格百分比
        new_price_percent = self.current_price_percent + change_percent

        # 限制在-100%到+100%之间
        if new_price_percent > 100:
            new_price_percent = 100
        elif new_price_percent < -100:
            new_price_percent = -100

        self.current_price_percent = new_price_percent

        #  关键修改在这里（原来只有一行）
        percent_change = self.stock_chart.update_chart(new_price_percent)
        self.percent_var.set(f"当前: {percent_change:.0f}%")

        # 更新按钮文本（显示当前价值）
        self.update_direction_buttons_text()

        # 更新状态
        color = "#e74c3c" if change_percent > 0 else "#27ae60"
        direction_symbol = "↑" if change_percent > 0 else "↓"
        self.status_var.set(f"更新中... {direction_symbol}{abs(change_percent):.0f}%")

        # 继续下一次更新
        self.current_update += 1
        self.root.after(int(self.update_interval * 1000), self.run_game_update)
            
    def finish_game(self):
        """结束游戏并结算——将上局结果前缀"结果："设置为黑色，涨/跌部分单独用颜色显示。"""
        final_percent = self.current_price_percent

        # 保存历史记录到文件
        update_history_in_file(final_percent)
        
        # 重新加载历史记录
        self.load_history_data()
        
        # 更新历史记录条
        self.history_bar.set_history(self.result_history)

        # 结算（保持你现有的结算逻辑）
        total_win = 0.0
        total_loss = 0.0

        if getattr(self, 'original_bet_up', 0) > 0:
            if final_percent > 0:  # 上涨，买涨赢
                winnings = self.original_bet_up * (final_percent / 100) * 0.95
                total_win += winnings
                self.bet_amount_up = self.original_bet_up + winnings
            else:  # 买涨输
                loss = self.original_bet_up * (abs(final_percent) / 100)
                total_loss += loss
                self.bet_amount_up = max(0.0, self.original_bet_up - loss)

        if getattr(self, 'original_bet_down', 0) > 0:
            if final_percent < 0:  # 下跌，买跌赢
                winnings = self.original_bet_down * (abs(final_percent) / 100) * 0.95
                total_win += winnings
                self.bet_amount_down = self.original_bet_down + winnings
            else:  # 买跌输
                loss = self.original_bet_down * (final_percent / 100)
                total_loss += loss
                self.bet_amount_down = max(0.0, self.original_bet_down - loss)

        net_win = total_win - total_loss
        self.last_win = net_win

        # 累计自上次"兑现"以来的净额
        if not hasattr(self, 'cumulative_net_since_cashout'):
            self.cumulative_net_since_cashout = 0.0
        self.cumulative_net_since_cashout += net_win

        # 构建结果文本与颜色（百分比不带小数）
        if final_percent > 0:
            status_text = f"上涨{final_percent:.0f}%"
            market_color = "#e74c3c"  # 红色表示上涨
        elif final_percent < 0:
            status_text = f"下跌{abs(final_percent):.0f}%"
            market_color = "#27ae60"  # 绿色表示下跌
        else:
            status_text = "持平 0%"
            market_color = "#ffd369"

        # --------- 关键：以两段 Label 显示（前缀黑色，状态有颜色） ----------
        # 若已有分离的 prefix/status label，直接更新颜色与文本
        if hasattr(self, 'last_result_status_label') and hasattr(self, 'last_result_prefix_label'):
            try:
                self.last_result_prefix_label.configure(text="结果：", fg="#4cc9f0")
                self.last_result_status_label.configure(text=status_text, fg=market_color)
            except Exception:
                # 兜底回退到 single label
                try:
                    if hasattr(self, 'last_result_label'):
                        self.last_result_label.configure(text=f"结果：{status_text}", fg=market_color)
                    else:
                        self.last_result_label = tk.Label(self.root, text=f"结果：{status_text}", font=("Arial", 18, "bold"))
                        self.last_result_label.pack(anchor=tk.W, pady=(5, 0))
                except Exception:
                    pass
        # 如果界面只有一个旧的 last_result_label，则把它替换为两段显示
        elif hasattr(self, 'last_result_label'):
            try:
                parent = self.last_result_label.master
                parent_bg = parent.cget('bg') if hasattr(parent, 'cget') else None
                # 销毁旧标签
                self.last_result_label.destroy()
                # 在同一父容器中创建容器帧和两个标签
                container = tk.Frame(parent, bg=parent_bg) if parent_bg is not None else tk.Frame(parent)
                container.pack(anchor=tk.W, pady=(5, 0))
                self.last_result_prefix_label = tk.Label(container, text="结果：", font=("Arial", 18, "bold"),
                                                        bg=parent_bg, fg="#4cc9f0") if parent_bg is not None else tk.Label(container, text="结果：", font=("Arial", 14, "#4cc9f0"), fg="black")
                self.last_result_prefix_label.pack(side=tk.LEFT)
                self.last_result_status_label = tk.Label(container, text=status_text, font=("Arial", 18, "bold"),
                                                        bg=parent_bg, fg=market_color) if parent_bg is not None else tk.Label(container, text=status_text, font=("Arial", 14, "bold"), fg=market_color)
                self.last_result_status_label.pack(side=tk.LEFT)
            except Exception:
                # 兜底：回到单一标签显示
                try:
                    self.last_result_label = tk.Label(parent, text=f"结果：{status_text}", font=("Arial", 18, "bold"), fg=market_color)
                    self.last_result_label.pack(anchor=tk.W, pady=(5, 0))
                except Exception:
                    pass
        # 如果既没有分离标签也没有旧标签，尝试创建新的分离标签在可用的 right_frame 或 root 上
        else:
            try:
                target_parent = getattr(self, 'win_frame', None) or getattr(self, 'right_frame', None) or self.root
                parent_bg = target_parent.cget('bg') if hasattr(target_parent, 'cget') else None
                container = tk.Frame(target_parent, bg=parent_bg) if parent_bg is not None else tk.Frame(target_parent)
                container.pack(anchor=tk.W, pady=(5, 0))
                self.last_result_prefix_label = tk.Label(container, text="结果：", font=("Arial", 18, "bold"),
                                                        bg=parent_bg, fg="#4cc9f0") if parent_bg is not None else tk.Label(container, text="结果：", font=("Arial", 18, "bold"), fg="black")
                self.last_result_prefix_label.pack(side=tk.LEFT)
                self.last_result_status_label = tk.Label(container, text=status_text, font=("Arial", 18, "bold"),
                                                        bg=parent_bg, fg=market_color) if parent_bg is not None else tk.Label(container, text=status_text, font=("Arial", 18, "bold"), fg=market_color)
                self.last_result_status_label.pack(side=tk.LEFT)
            except Exception:
                # 最后兜底：单一标签（不分色）
                try:
                    self.last_result_label = tk.Label(self.root, text=f"结果：{status_text}", font=("Arial", 18, "bold"))
                    self.last_result_label.pack(anchor=tk.W, pady=(5, 0))
                except Exception:
                    pass

        # --------- 本局盈亏显示（仅当有下注时显示） ----------
        if (getattr(self, 'original_bet_up', 0) > 0) or (getattr(self, 'original_bet_down', 0) > 0):
            if net_win > 0:
                self.result_win_or_loss_var.set(f"本局盈利了 ${net_win:.2f}")
                try:
                    self.result_win_or_loss_label.configure(fg="#27ae60")
                except Exception:
                    pass
            elif net_win < 0:
                self.result_win_or_loss_var.set(f"本局亏损了 ${abs(net_win):.2f}")
                try:
                    self.result_win_or_loss_label.configure(fg="#e74c3c")
                except Exception:
                    pass
            else:
                self.result_win_or_loss_var.set("平手")
                try:
                    self.result_win_or_loss_label.configure(fg="#ffd369")
                except Exception:
                    pass
        else:
            # 本局没有下注则不显示
            try:
                self.result_win_or_loss_var.set("")
            except Exception:
                pass

        # 自动兑现小注（如果实现）
        if hasattr(self, 'auto_cashout_small_bets'):
            try:
                self.auto_cashout_small_bets()
            except Exception:
                pass

        # 标记游戏结束并刷新显示
        self.game_active = False
        try:
            self.update_direction_buttons_text()
        except Exception:
            pass
        try:
            self.update_display()
        except Exception:
            pass

        # 更新状态栏文本
        try:
            self.status_var.set("游戏结束")
        except Exception:
            pass

        # 启动下一局倒计时（延迟 2 秒后开始）
        try:
            self.root.after(2000, lambda: self.start_countdown(12))
        except Exception:
            pass
    
    def on_closing(self):
        """窗口关闭事件处理"""
        # 取消定时器
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
        
        # 更新余额到JSON
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()

def main(initial_balance, username):
    """供small_games.py调用的主函数"""
    root = tk.Tk()
    game = StockMarketGame(root, initial_balance, username)
    root.mainloop()
    # 返回更新后的余额
    return game.balance

if __name__ == "__main__":
    # 单独运行时的测试代码
    root = tk.Tk()
    # 使用测试余额和用户名
    game = StockMarketGame(root, 1000.0, "test_user")
    root.mainloop()