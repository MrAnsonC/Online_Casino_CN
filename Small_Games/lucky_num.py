import tkinter as tk
from tkinter import ttk
import random
import json
import os
import time
import math
from PIL import Image, ImageTk
import sys

def get_data_file_path():
    # 用于获取保存数据的文件路径
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')

def get_log_file_path():
    # 用于获取游戏记录的文件路径
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../A_Logs/small_g_dice.json')

# 保存用户数据
def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

# 读取用户数据
def load_user_data():
    file_path = get_data_file_path()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def update_balance_in_json(username, new_balance):
    users = load_user_data()  # 先加载现有用户数据
    for user in users:
        if user['user_name'] == username:  # 查找当前用户
            user['cash'] = f"{new_balance:.2f}"  # 更新余额
            break
    save_user_data(users)  # 保存更新后的数据 

# 保存游戏记录
def save_game_log(result):
    file_path = get_log_file_path()
    
    # 确保目录存在
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    try:
        # 尝试读取现有记录
        with open(file_path, 'r', encoding='utf-8') as f:
            logs = json.load(f)
    except:
        # 如果文件不存在或格式错误，创建默认记录
        logs = {
            "01": 0,
            "02": 0,
            "03": 0,
            "04": 0,
            "05": 0,
            "06": 0,
            "07": 0,
            "08": 0
        }
    
    # 更新记录：01的数据移动到02，02的移动到03...05的数据会被移除
    logs["08"] = logs["07"]
    logs["07"] = logs["06"]
    logs["06"] = logs["05"]
    logs["05"] = logs["04"]
    logs["04"] = logs["03"]
    logs["03"] = logs["02"]
    logs["02"] = logs["01"]
    logs["01"] = result
    
    # 保存更新后的记录
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(logs, f, ensure_ascii=False, indent=4)
    
    return logs

# 读取游戏记录
def load_game_log():
    file_path = get_log_file_path()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        # 如果文件不存在，返回默认记录
        return {
            "01": 0,
            "02": 0,
            "03": 0,
            "04": 0,
            "05": 0,
            "06": 0,
            "07": 0,
            "08": 0
        }

class CircleButton(tk.Canvas):
    def __init__(self, parent, text, bg_color, fg_color, command=None, diameter=60):
        tk.Canvas.__init__(self, parent, width=diameter, height=diameter, 
                          bg=parent['bg'], highlightthickness=0)
        self.command = command
        self.bg_color = bg_color
        self.fg_color = fg_color
        
        # 绘制圆形按钮
        self.create_oval(2, 2, diameter-2, diameter-2, fill=bg_color, outline="white", width=2)
        self.create_text(diameter/2, diameter/2, text=text, fill=fg_color, 
                        font=("Arial", 18, "bold"))
        
        # 绑定点击事件
        self.bind("<Button-1>", self.on_click)
        
    def on_click(self, event):
        if self.command:
            self.command()

class DiceGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("幸运数字")
        self.root.geometry("1003x670+50+10")
        self.root.resizable(0,0)
        self.root.configure(bg="#1a1a2e")
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 游戏数据
        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0
        self.current_bet = 0.0
        self.target_number = 50
        self.bet_type = "above"  # "above" or "below"
        self.game_active = False
        self.last_win = 0.0
        
        # 动画相关变量
        self.animation_running = False
        self.ones_digit = "-"
        self.tens_digit = "-"
        self.final_result = 0
        self.last_ones_digit = -1
        self.last_tens_digit = -1
        
        # 游戏记录
        self.game_logs = load_game_log()
        
        # 创建UI
        self.create_widgets()
        self.update_display()
    
    def calculate_payout(self, target, bet_type):
        """计算赔率 - 基于目标数字和投注类型"""
        if bet_type == "above":
            # 高于目标数字的概率 = (100 - target) / 100
            probability = (100 - target) / 100
        else:  # below
            # 低于目标数字的概率 = (target - 1) / 100
            probability = (target - 1) / 100
        
        # 防止除零错误
        if probability == 0:
            probability = 0.01
        
        # 计算公平赔率并添加庄家优势
        fair_odds = 1.0 / probability
        house_edge = 0.01  # 1% 庄家优势
        payout = fair_odds * (1 - house_edge)
        
        # 确保赔率在范围内 (1.01 到 99.0)
        payout = max(1.01, min(99.0, payout))
        
        return round(payout, 2)
    
    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 左侧 - 骰子显示和结果区域
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # 初始游戏说明 - 修改背景颜色与游戏画面框架相同
        self.instructions_frame = tk.Frame(left_frame, bg="#16213e")
        self.instructions_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        tk.Label(self.instructions_frame, text="幸运数字", font=("Arial", 24, "bold"), 
                bg="#16213e", fg="#e94560").pack(pady=20)
        
        instructions = """
游戏规则：
1. 首先下注
2. 选择目标数字范围
3. 选择高于或低于目标数字
4. 点击开始游戏，等待结果

赔率说明：
- 根据您选择的目标数字和投注类型，赔率会动态变化
- 如果结果刚好等于目标数字，赔率乘以2
- 赔率范围从1.01到99.0

目标数字范围：
- 低于目标：1-97
- 高于目标：3-99

点击"开始游戏"后，将显示游戏界面
        """
        tk.Label(self.instructions_frame, text=instructions, font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1", justify=tk.LEFT).pack(pady=20)
        
        # 目标数字选择和颜色条 - 始终显示在说明下方
        self.target_frame = tk.Frame(left_frame, bg="#16213e")
        self.target_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(self.target_frame, text="目标数字:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        # 颜色条和按钮框架
        color_button_frame = tk.Frame(self.target_frame, bg="#16213e")
        color_button_frame.pack(fill=tk.X, pady=5)
        
        # 左侧按钮 - 低于目标
        self.below_button = tk.Button(
            color_button_frame, text="低于目标", font=("Arial", 10, "bold"),
            bg="#e94560", fg="white", width=10, command=self.select_below
        )
        self.below_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 颜色条 - 现在也作为目标数字选择器
        self.color_bar_frame = tk.Frame(color_button_frame, bg="#16213e", height=30)
        self.color_bar_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 右侧按钮 - 高于目标
        self.above_button = tk.Button(
            color_button_frame, text="高于目标", font=("Arial", 10, "bold"),
            bg="#27ae60", fg="white", width=10, command=self.select_above
        )
        self.above_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        # 结果标签 - 始终显示
        self.result_var = tk.StringVar()
        self.result_var.set("请下注并开始游戏")
        self.result_label = tk.Label(left_frame, textvariable=self.result_var, 
                              font=("Arial", 16, "bold"), bg="#16213e", fg="#4cc9f0")
        self.result_label.pack(pady=10)
        
        # 游戏画面框架（初始隐藏）
        self.game_frame = tk.Frame(left_frame, bg="#16213e")
        
        # 骰子显示区域 - 放在游戏画面的顶部
        self.dice_frame = tk.Frame(self.game_frame, bg="#0f3460", bd=0)
        self.dice_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 骰子画布
        self.dice_canvas = tk.Canvas(self.dice_frame, bg="#0f3460", highlightthickness=0, width=400, height=300)
        self.dice_canvas.pack(fill=tk.BOTH, expand=True)
        
        # 历史记录区域 - 放在骰子显示区域下方
        self.history_frame = tk.Frame(self.game_frame, bg="#16213e")
        self.history_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # 历史记录标题
        tk.Label(self.history_frame, text="最近7局游戏记录", font=("Arial", 14, "bold"), 
                bg="#16213e", fg="#ffd369").pack(anchor=tk.W, pady=(0, 10))
        
        # 历史记录显示
        self.history_canvas = tk.Frame(self.history_frame, bg="#16213e")
        self.history_canvas.pack(fill=tk.X)
        
        # 初始化历史记录显示
        self.update_history_display()
        
        # 右侧 - 控制面板
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
        
        # 筹码按钮
        chips_frame = tk.Frame(right_frame, bg="#16213e")
        chips_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        chips = [
            ("$5", '#ff0000', 'white'),    # 红色背景，白色文字
            ("$25", '#00ff00', 'black'),   # 绿色背景，黑色文字
            ("$100", '#000000', 'white'),  # 黑色背景，白色文字
            ("$500", "#FF7DDA", 'black'),  # 粉色背景，黑色文字
            ("$1K", '#ffffff', 'black')    # 白色背景，黑色文字
        ]
        
        self.chip_buttons = []  # 存储所有筹码按钮
        for text, bg_color, fg_color in chips:
            btn = CircleButton(
                chips_frame, text=text, bg_color=bg_color, fg_color=fg_color,
                command=lambda t=text: self.add_chip(t[1:])  # 去掉$符号
            )
            btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.chip_buttons.append(btn)
        
        # 下注金额和赔率显示 - 放在同一行
        bet_odds_frame = tk.Frame(right_frame, bg="#16213e")
        bet_odds_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 下注金额
        bet_frame = tk.Frame(bet_odds_frame, bg="#16213e")
        bet_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Label(bet_frame, text="下注金额:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.bet_var = tk.StringVar()
        self.bet_var.set("$0.00")
        tk.Label(bet_frame, textvariable=self.bet_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
        
        # 赔率显示 - 固定在右边控制面板的中间位置
        odds_frame = tk.Frame(right_frame, bg="#16213e")
        odds_frame.pack(fill=tk.X, padx=10, pady=20)
        
        tk.Label(odds_frame, text="当前赔率:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.odds_var = tk.StringVar()
        self.odds_var.set("1.00x")
        tk.Label(odds_frame, textvariable=self.odds_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#ffd369").pack(anchor=tk.W, pady=(5, 0))
        
        # 预计获胜金额 - 放在下一行
        win_frame = tk.Frame(right_frame, bg="#16213e")
        win_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(win_frame, text="预计获胜金额:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.win_var = tk.StringVar()
        self.win_var.set("$0.00")
        tk.Label(win_frame, textvariable=self.win_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
        
        # 游戏按钮
        button_frame = tk.Frame(right_frame, bg="#16213e")
        button_frame.pack(fill=tk.X, padx=10, pady=20)
        
        self.start_button = tk.Button(
            button_frame, text="开始游戏", font=("Arial", 12, "bold"),
            bg="#27ae60", fg="white", width=12, command=self.start_game
        )
        self.start_button.pack(pady=5)
        
        self.reset_bet_button = tk.Button(
            button_frame, text="重设下注金额", font=("Arial", 12),
            bg="#3498db", fg="white", width=12, command=self.reset_bet
        )
        self.reset_bet_button.pack(pady=5)
        
        # 上局获胜金额 - 放在右边控制面板的左下方
        last_win_frame = tk.Frame(right_frame, bg="#16213e")
        last_win_frame.pack(fill=tk.X, padx=10, pady=(20, 10), side=tk.BOTTOM)
        
        tk.Label(last_win_frame, text="上局获胜金额:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.last_win_var = tk.StringVar()
        self.last_win_var.set("$0.00")
        tk.Label(last_win_frame, textvariable=self.last_win_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
        
        # 更新赔率和赢利显示
        self.update_odds()
        self.update_color_bar()
        self.update_button_states()
    
    def update_history_display(self):
        # 清除历史记录显示
        for widget in self.history_canvas.winfo_children():
            widget.destroy()
        
        # 显示历史记录
        for i in range(1, 8):
            key = f"{i:02d}"
            result = self.game_logs.get(key, 0)
            
            # 创建历史记录项框架
            history_item = tk.Frame(self.history_canvas, bg="#16213e")
            history_item.pack(side=tk.LEFT, padx=10, pady=5)
            
            # 显示记录编号
            tk.Label(history_item, text=f"第{key}局:", font=("Arial", 10), 
                    bg="#16213e", fg="#f1f1f1").pack()
            
            # 显示记录结果
            result_color = "#4cc9f0" if result >= 0 else "#f1f1f1"
            result_text = str(result) if result >= 0 else "无记录"
            tk.Label(history_item, text=result_text, font=("Arial", 14, "bold"), 
                    bg="#16213e", fg=result_color).pack()
    
    def select_above(self):
        self.bet_type = "above"
        # 如果当前数字不在3-99范围内，调整为3
        if self.target_number < 3:
            self.target_number = 3
        self.update_bet_type()
    
    def select_below(self):
        self.bet_type = "below"
        # 如果当前数字不在1-97范围内，调整为97
        if self.target_number > 97:
            self.target_number = 97
        self.update_bet_type()
    
    def update_button_states(self):
        if self.bet_type == "above":
            self.above_button.config(bg="#4cc9f0", state=tk.DISABLED)
            self.below_button.config(bg="#e94560", state=tk.NORMAL)
        else:
            self.above_button.config(bg="#27ae60", state=tk.NORMAL)
            self.below_button.config(bg="#4cc9f0", state=tk.DISABLED)
    
    def update_color_bar(self):
        # 清除颜色条
        for widget in self.color_bar_frame.winfo_children():
            widget.destroy()
        
        # 创建颜色条
        width = 335
        height = 30
        
        # 创建画布
        self.color_canvas = tk.Canvas(self.color_bar_frame, width=width, height=height, 
                                     bg="#FFFBFB", highlightthickness=0)
        self.color_canvas.pack(fill=tk.BOTH, expand=True)
        
        # 绑定鼠标拖动事件
        self.color_canvas.bind("<B1-Motion>", self.on_color_bar_drag)
        
        # 根据下注类型绘制颜色条
        if self.bet_type == "below":
            # 低于目标：0-目标数字为绿色，目标数字-100为红色
            green_width = int(width * (self.target_number / 99))
            self.color_canvas.create_rectangle(0, 0, green_width, height, fill="#27ae60", outline="")
            self.color_canvas.create_rectangle(green_width, 0, width, height, fill="#e94560", outline="")
        else:
            # 高于目标：0-目标数字为红色，目标数字-100为绿色
            red_width = int(width * (self.target_number / 99))
            self.color_canvas.create_rectangle(0, 0, red_width, height, fill="#e94560", outline="")
            self.color_canvas.create_rectangle(red_width, 0, width, height, fill="#27ae60", outline="")
        
        # 添加目标线
        target_x = int(width * (self.target_number / 99))
        self.color_canvas.create_line(target_x, 0, target_x, height, fill="#ffd369", width=20)
        
        # 显示目标数字
        self.color_canvas.create_text(target_x, 15, text=str(self.target_number), 
                                     fill="#000000", font=("Arial", 12, "bold"))
    
    def on_color_bar_drag(self, event):
        self.set_target_from_color_bar(event.x)
    
    def set_target_from_color_bar(self, x):
        width = self.color_canvas.winfo_width()
        if width == 1:  # 如果画布还没有被渲染，使用默认宽度
            width = 335
        
        # 计算目标数字 - 增加宽度参数使边缘数字更容易选择
        new_target = max(1, min(99, int((x / width) * 99)))
        
        # 根据下注类型限制范围
        if self.bet_type == "above" and new_target < 3:
            new_target = 3
        elif self.bet_type == "below" and new_target > 97:
            new_target = 97
        
        if new_target != self.target_number:
            self.target_number = new_target
            self.update_odds()
            self.update_color_bar()
    
    def add_chip(self, amount):
        try:
            # 处理"1K"的情况
            if amount == "1K":
                amount_val = 1000.0
            else:
                amount_val = float(amount)
                
            new_bet = self.current_bet + amount_val
            if new_bet <= self.balance:
                self.current_bet = new_bet
                self.bet_var.set(f"${self.current_bet:.2f}")
                self.update_win_amount()
        except ValueError:
            pass
    
    def reset_bet(self):
        self.current_bet = 0.0
        self.bet_var.set("$0.00")
        self.update_win_amount()
    
    def update_bet_type(self):
        self.update_odds()
        self.update_color_bar()
        self.update_button_states()
    
    def update_odds(self):
        # 计算当前赔率
        payout = self.calculate_payout(self.target_number, self.bet_type)
        self.odds_var.set(f"{payout:.2f}x")
        
        # 更新潜在赢利
        self.update_win_amount()
    
    def update_win_amount(self):
        payout = self.calculate_payout(self.target_number, self.bet_type)
        win_amount = self.current_bet * payout
        self.win_var.set(f"${win_amount:.2f}")
    
    def update_display(self):
        self.balance_var.set(f"${self.balance:.2f}")
        self.last_win_var.set(f"${self.last_win:.2f}")
        self.draw_dice()
    
    def draw_dice(self):
        self.dice_canvas.delete("all")
        
        # 绘制骰子背景
        width = self.dice_canvas.winfo_width()
        height = self.dice_canvas.winfo_height()
        
        # 绘制目标区域
        target_x = width // 2
        target_y = height // 2 - 50
        
        # 绘制目标文本
        if self.bet_type == "below":
            target_text = f"目标: 0-{self.target_number}"
        else:
            target_text = f"目标: {self.target_number}-99"
            
        self.dice_canvas.create_text(target_x, target_y - 20, 
                                    text=target_text, 
                                    font=("Arial", 30, "bold"), 
                                    fill="#ffd369")
        
        # 绘制数字显示区域
        result_x = width // 2
        result_y = height // 2 + 50
        
        # 绘制数字背景
        self.dice_canvas.create_rectangle(result_x-80, result_y-40, result_x+80, result_y+40, 
                                         fill="#2d4059", outline="#4cc9f0", width=2)
        
        # 绘制数字分隔线
        self.dice_canvas.create_line(result_x, result_y-40, result_x, result_y+40, 
                                    fill="#4cc9f0", width=2)
        
        # 绘制十位数
        tens_x = result_x - 40
        self.dice_canvas.create_text(tens_x, result_y, text=str(self.tens_digit), 
                                    font=("Arial", 36, "bold"), fill="#ffffff")
        
        # 绘制个位数
        ones_x = result_x + 40
        self.dice_canvas.create_text(ones_x, result_y, text=str(self.ones_digit), 
                                    font=("Arial", 36, "bold"), fill="#ffffff")
        
        # 绘制标签
        self.dice_canvas.create_text(tens_x, result_y - 60, text="十位", 
                                    font=("Arial", 12), fill="#ffd369")
        self.dice_canvas.create_text(ones_x, result_y - 60, text="个位", 
                                    font=("Arial", 12), fill="#ffd369")
    
    def disable_controls(self):
        """禁用游戏控制控件"""
        self.color_canvas.unbind("<B1-Motion>")  # 解除颜色条拖动事件
        self.below_button.config(state=tk.DISABLED)
        self.above_button.config(state=tk.DISABLED)
        for btn in self.chip_buttons:
            btn.configure(state=tk.DISABLED)
        self.reset_bet_button.config(state=tk.DISABLED)
    
    def enable_controls(self):
        """启用游戏控制控件"""
        self.color_canvas.bind("<B1-Motion>", self.on_color_bar_drag)  # 重新绑定颜色条拖动事件
        self.update_button_states()  # 这会根据当前bet_type设置按钮状态
        for btn in self.chip_buttons:
            btn.configure(state=tk.NORMAL)
        self.reset_bet_button.config(state=tk.NORMAL)
    
    def start_game(self):
        if self.current_bet <= 0:
            self.result_var.set("请先下注！")
            return
        if self.current_bet > self.balance:
            self.result_var.set("余额不足！")
            return
        
        # 隐藏说明，显示游戏画面
        self.instructions_frame.pack_forget()
        self.game_frame.pack(fill=tk.BOTH, expand=True, before=self.target_frame)
        
        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        self.game_active = True
        
        # 禁用游戏控制控件
        self.disable_controls()
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 更新UI状态
        self.start_button.config(state=tk.DISABLED)
        
        # 开始掷骰子动画
        self.roll_dice()
    
    def roll_dice(self):
        # 重置动画状态
        self.animation_running = True
        self.ones_digit = "-"
        self.tens_digit = "-"
        self.final_result = 0
        self.last_ones_digit = -1
        self.last_tens_digit = -1
        
        # 生成最终结果 (1-100)
        self.final_result = random.randint(1, 100)
        
        # 分解为十位和个位 - 修复十位数范围问题
        if self.final_result == 100:
            final_tens = 10  # 100的十位数是10
            final_ones = 0   # 100的个位数是0
        else:
            final_tens = self.final_result // 10
            final_ones = self.final_result % 10
        
        self.result_var.set("掷骰子中...")
        
        # 开始个位数字动画
        self.animate_ones_digit(final_ones, final_tens)
    
    def get_different_digit(self, current_digit, last_digit, is_tens=False):
        """获取一个与上一个数字不同的随机数字"""
        new_digit = current_digit
        while new_digit == last_digit:
            new_digit = random.randint(0, 9)
        return new_digit
    
    def animate_ones_digit(self, final_ones, final_tens):
        if not self.animation_running:
            return
            
        # 更新个位数字，确保与上一个数字不同
        self.ones_digit = self.get_different_digit(self.ones_digit, self.last_ones_digit)
        self.last_ones_digit = self.ones_digit
        # 十位数保持为"-"
        self.tens_digit = "-"
        self.draw_dice()
        
        # 继续动画或停止
        if hasattr(self, 'ones_animation_count'):
            self.ones_animation_count += 1
        else:
            self.ones_animation_count = 1
            
        if self.ones_animation_count < 150:  # 1.5秒，每10ms更新一次
            self.root.after(10, lambda: self.animate_ones_digit(final_ones, final_tens))
        else:
            # 停止个位数字动画，设置最终个位数字
            self.ones_digit = final_ones
            self.draw_dice()
            
            # 重置十位数动画计数
            if hasattr(self, 'tens_animation_count'):
                del self.tens_animation_count
            
            # 开始十位数字动画
            self.root.after(500, lambda: self.animate_tens_digit(final_tens))
    
    def animate_tens_digit(self, final_tens):
        if not self.animation_running:
            return
            
        # 更新十位数字，确保与上一个数字不同
        self.tens_digit = self.get_different_digit(self.tens_digit, self.last_tens_digit, is_tens=True)
        self.last_tens_digit = self.tens_digit
        self.draw_dice()
        
        # 继续动画或停止
        if hasattr(self, 'tens_animation_count'):
            self.tens_animation_count += 1
        else:
            self.tens_animation_count = 1
            
        if self.tens_animation_count < 150:  # 1.5秒，每10ms更新一次
            self.root.after(10, lambda: self.animate_tens_digit(final_tens))
        else:
            # 停止十位数字动画，设置最终十位数字
            self.tens_digit = final_tens
            self.draw_dice()
            
            # 完成掷骰子
            self.root.after(500, self.finish_roll)
    
    def finish_roll(self):
        # 重置动画计数
        if hasattr(self, 'ones_animation_count'):
            del self.ones_animation_count
        if hasattr(self, 'tens_animation_count'):
            del self.tens_animation_count
            
        self.animation_running = False
        
        # 确定结果
        win = False
        exact_match = False
        
        if self.bet_type == "above":
            if self.final_result > self.target_number:
                win = True
            elif self.final_result == self.target_number:
                exact_match = True
        else:  # below
            if self.final_result < self.target_number:
                win = True
            elif self.final_result == self.target_number:
                exact_match = True
        
        # 计算赢利
        payout = self.calculate_payout(self.target_number, self.bet_type)
        
        if exact_match:
            # 刚好等于目标数字，赔率乘以2
            win_amount = self.bet_amount * payout * 2
            self.balance += win_amount
            self.last_win = win_amount
            self.result_var.set(f"完美命中！你赢了 ${win_amount:.2f}")
        elif win:
            win_amount = self.bet_amount * payout
            self.balance += win_amount
            self.last_win = win_amount
            self.result_var.set(f"恭喜！你赢了 ${win_amount:.2f}")
        else:
            self.last_win = 0.0
            self.result_var.set(f"很遗憾，没有赢。")
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 更新游戏记录
        self.game_logs = save_game_log(self.final_result)
        self.update_history_display()
        
        # 更新UI状态
        self.start_button.config(state=tk.NORMAL)
        
        # 启用游戏控制控件
        self.enable_controls()
        
        # 更新显示
        self.update_display()
    
    def on_closing(self):
        """窗口关闭事件处理"""
        # 停止任何正在运行的动画
        self.animation_running = False
        
        # 更新余额到JSON
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()

def main(initial_balance, username):
    """供small_games.py调用的主函数"""
    root = tk.Tk()
    game = DiceGame(root, initial_balance, username)
    root.mainloop()
    # 返回更新后的余额
    return game.balance

if __name__ == "__main__":
    # 单独运行时的测试代码
    root = tk.Tk()
    # 使用测试余额和用户名
    game = DiceGame(root, 1000.0, "test_user")
    root.mainloop()