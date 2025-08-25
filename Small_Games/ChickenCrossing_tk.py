import tkinter as tk
from tkinter import ttk, messagebox
import random
import json
import os
import time
import math

def get_data_file_path():
    # 用于获取保存数据的文件路径
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')

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

class CircleButton(tk.Canvas):
    """自定义圆形按钮"""
    def __init__(self, master, text, bg_color, fg_color, command=None, radius=30, *args, **kwargs):
        super().__init__(master, width=radius*2, height=radius*2, 
                         highlightthickness=0, bg="#16213e", *args, **kwargs)  # 背景色与父容器一致
        self.radius = radius
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.text = text
        self.command = command
        
        # 绘制圆形按钮
        self.create_oval(0, 0, radius*2, radius*2, fill=bg_color, outline="#16213e", width=2)  # 外框使用背景色
        self.create_text(radius, radius, text=text, fill=fg_color, 
                        font=("Arial", 18, "bold"))
        
        # 绑定点击事件
        self.bind("<Button-1>", self.on_click)
    
    def on_click(self, event):
        if self.command:
            self.command()

class ChickenCrossingGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("小鸡过马路游戏")
        self.root.geometry("1000x700+50+10")
        self.root.resizable(0,0)
        self.root.configure(bg="#1a1a2e")
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 游戏数据
        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0
        self.difficulty = "1"
        self.current_stage = 0
        self.game_active = False
        self.last_win = 0.0
        self.chip_buttons = []  # 存储筹码按钮的引用
        self.current_bet = 0.0  # 当前下注金额
        self.animation_in_progress = False
        self.car_animation_step = 0
        self.chicken_animation_id = None  # 存储小鸡动画ID
        self.chicken_animation_steps = []  # 存储小鸡动画步骤
        
        # 各难度对应死亡几率和赔率
        self.difficulty_settings = {
            '1': {'death_rate': 1/25, 'multipliers': [1, 1.04, 1.09, 1.14, 1.20, 1.26, 1.33, 1.41, 1.50, 1.60, 1.71, 1.85, 2, 2.18, 2.40, 2.67, 3.00, 3.43, 4.00, 4.80, 6.00, 8.00, 12.00, 24.00]},
            '2': {'death_rate': 3/25, 'multipliers': [1, 1.09, 1.25, 1.43, 1.66, 1.94, 2.28, 2.71, 3.25, 3.94, 4.85, 6.07, 7.72, 10.04, 13.28, 18.40, 26.29, 39.43, 63.09, 110.40, 220.80, 552.00, 2208.00]},
            '3': {'death_rate': 5/25, 'multipliers': [1, 1.20, 1.52, 1.94, 2.51, 3.29, 4.39, 5.95, 8.24, 11.68, 16.98, 25.48, 39.63, 64.40, 110.40, 202.40, 404.80, 910.80, 2428.00, 8500.00, 51004.80]},
            '4': {'death_rate': 10/25, 'multipliers': [1, 1.60, 2.74, 4.85, 8.90, 16.98, 33.67, 71.71, 161.35, 391.86, 1044.96, 3134.87, 10972.06, 47545.60, 285273.60, 3138009.60]}
        }
        
        # 创建UI
        self.create_widgets()
        self.update_display()
    
    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 左侧 - 游戏显示
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # 标题和游戏信息框架（固定在顶部，不随滚动条移动）
        title_info_frame = tk.Frame(left_frame, bg="#16213e")
        title_info_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(title_info_frame, text="小鸡过马路", font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#e94560").pack(pady=(10, 5))
        
        # 游戏信息标签
        self.info_label = tk.Label(title_info_frame, text="选择下注金额和难度后点击开始游戏", 
                                  font=("Arial", 14), bg="#16213e", fg="#bdc3c7")
        self.info_label.pack(pady=(0, 10))
        
        # 创建滚动框架
        scroll_frame = tk.Frame(left_frame, bg="#16213e")
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # 创建画布和滚动条
        self.canvas_frame = tk.Frame(scroll_frame, bg="#0f3460")
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.game_canvas = tk.Canvas(self.canvas_frame, bg="#0f3460", bd=0, highlightthickness=0)
        
        # 添加水平滚动条
        h_scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL, command=self.game_canvas.xview)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.game_canvas.configure(xscrollcommand=h_scrollbar.set)
        self.game_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
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
            ("$25", '#00ff00', 'black'),    # 绿色背景，黑色文字
            ("$100", '#000000', 'white'),   # 黑色背景，白色文字
            ("$500", "#FF7DDA", 'black'),   # 粉色背景，黑色文字
            ("$1K", '#ffffff', 'black')     # 白色背景，黑色文字
        ]
        
        self.chip_buttons = []  # 存储所有筹码按钮
        for text, bg_color, fg_color in chips:
            btn = CircleButton(
                chips_frame, text=text, bg_color=bg_color, fg_color=fg_color,
                command=lambda t=text: self.add_chip(t[1:])  # 去掉$符号
            )
            btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.chip_buttons.append(btn)
        
        # 难度选择
        difficulty_frame = tk.Frame(right_frame, bg="#16213e")
        difficulty_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(difficulty_frame, text="难度:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.difficulty_var = tk.StringVar()
        self.difficulty_var.set("1")
        
        difficulties = [
            ("简单", "1"),
            ("中等", "2"),
            ("困难", "3"),
            ("地狱", "4")
        ]
        
        self.difficulty_buttons = []  # 存储所有难度按钮
        for text, value in difficulties:
            btn = tk.Button(
                difficulty_frame, text=text, font=("Arial", 10),
                bg="#4e9de0" if value == "1" else "#2d4059", fg="white", 
                width=6, height=1, relief=tk.RAISED,
                command=lambda v=value: self.set_difficulty(v)
            )
            btn.pack(side=tk.LEFT, padx=2, pady=2)
            self.difficulty_buttons.append(btn)
        
        # 游戏按钮
        button_frame = tk.Frame(right_frame, bg="#16213e")
        button_frame.pack(fill=tk.X, padx=10, pady=20)
        
        self.start_button = tk.Button(
            button_frame, text="开始游戏", font=("Arial", 12, "bold"),
            bg="#27ae60", fg="white", width=12, command=self.start_game
        )
        self.start_button.pack(pady=5)
        
        self.advance_button = tk.Button(
            button_frame, text="前进", font=("Arial", 12),
            bg="#3498db", fg="white", width=12, command=self.advance
        )
        self.advance_button.pack(pady=5)
        self.advance_button.pack_forget()  # 初始隐藏前进按钮
        
        self.cash_out_button = tk.Button(
            button_frame, text="兑现奖金", font=("Arial", 12),
            bg="#e74c3c", fg="white", width=12, command=self.cash_out
        )
        self.cash_out_button.pack(pady=5)
        self.cash_out_button.pack_forget()  # 初始隐藏兑现按钮
        
        self.reset_bet_button = tk.Button(
            button_frame, text="重设下注金额", font=("Arial", 12),
            bg="#3498db", fg="white", width=12, command=self.reset_bet
        )
        self.reset_bet_button.pack(pady=5)
                
        # 游戏信息
        info_frame = tk.Frame(right_frame, bg="#16213e")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Label(info_frame, text="游戏规则:", font=("Arial", 12, "bold"), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, pady=(0, 5))
        
        rules = [
            "1. 选择下注金额和难度",
            "2. 点击开始游戏按钮",
            "3. 选择前进或兑现奖金",
            "4. 每前进一关，奖金倍数增加",
            "5. 但遇到车祸的风险也增加",
            "6. 随时可以兑现奖金结束游戏"
        ]
        
        for rule in rules:
            tk.Label(info_frame, text=rule, font=("Arial", 10), 
                    bg="#16213e", fg="#bdc3c7", justify=tk.LEFT).pack(anchor=tk.W, pady=2)
            
        # 下注金额和上局获胜金额显示
        bet_win_frame = tk.Frame(right_frame, bg="#16213e")
        bet_win_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # 下注金额
        bet_frame = tk.Frame(bet_win_frame, bg="#16213e")
        bet_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        tk.Label(bet_frame, text="下注金额:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.bet_var = tk.StringVar()
        self.bet_var.set("$0.00")  # 初始显示格式
        tk.Label(bet_frame, textvariable=self.bet_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
        
        # 上局获胜金额
        win_frame = tk.Frame(bet_win_frame, bg="#16213e")
        win_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))
        
        tk.Label(win_frame, text="上局获胜金额:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.last_win_var = tk.StringVar()
        self.last_win_var.set("$0.00")  # 初始显示格式
        tk.Label(win_frame, textvariable=self.last_win_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
    
    def add_chip(self, amount):
        try:
            amount_val = float(amount)
            new_bet = self.current_bet + amount_val
            if new_bet <= self.balance:
                self.current_bet = new_bet
                self.bet_var.set(f"${self.current_bet:.2f}")  # 格式化为两位小数
        except ValueError:
            pass
    
    def reset_bet(self):
        self.current_bet = 0.0
        self.bet_var.set("$0.00")  # 格式化为两位小数
    
    def set_difficulty(self, difficulty):
        self.difficulty = difficulty
        # 更新按钮样式
        for i, (text, value) in enumerate([("简单", "1"), ("中等", "2"), ("困难", "3"), ("地狱", "4")]):
            if value == difficulty:
                self.difficulty_buttons[i].configure(bg="#4e9de0")
            else:
                self.difficulty_buttons[i].configure(bg="#2d4059")
        
        self.update_display()
    
    def update_display(self):
        self.balance_var.set(f"${self.balance:.2f}")
        self.last_win_var.set(f"${self.last_win:.2f}")  # 格式化为两位小数
        
        # 更新游戏信息标签
        if self.game_active:
            settings = self.difficulty_settings[self.difficulty]
            multipliers = settings['multipliers']
            
            if self.current_stage < len(multipliers):
                potential_win = self.bet_amount * multipliers[self.current_stage]
                self.info_label.config(text=f"当前阶段: {self.current_stage+1}/{len(multipliers)}\n潜在奖励: ${potential_win:.2f}")
            else:
                self.info_label.config(text="游戏完成!")
        else:
            self.info_label.config(text="选择下注金额和难度后点击开始游戏")
        
        self.draw_game()
    
    def ensure_chicken_visible(self):
        """确保小鸡在视野范围内，必要时滚动画面"""
        if not self.game_active:
            return
            
        settings = self.difficulty_settings[self.difficulty]
        multipliers = settings['multipliers']
        
        # 计算小鸡位置
        cell_width = 100
        start_x = 50
        
        # 获取画布宽度
        canvas_width = self.game_canvas.winfo_width()
        if canvas_width <= 1:  # 如果画布尚未渲染
            return
            
        # 计算总宽度
        total_width = len(multipliers) * cell_width + start_x * 2
        
        # 计算小鸡的x坐标
        if self.chicken_animation_steps:
            # 动画中的小鸡位置
            step_idx, from_stage, to_stage, progress = self.chicken_animation_steps[0]
            from_x = start_x + from_stage * cell_width + cell_width/2
            to_x = start_x + to_stage * cell_width + cell_width/2
            chicken_x = from_x + (to_x - from_x) * progress
        else:
            # 静止的小鸡位置
            chicken_x = start_x + self.current_stage * cell_width + cell_width/2
        
        # 获取当前滚动位置
        scroll_left, scroll_right = self.game_canvas.xview()
        view_left = scroll_left * total_width
        view_right = scroll_right * total_width
        
        # 检查小鸡是否在视野范围内（左侧留50px余量）
        if chicken_x < view_left + 50 or chicken_x > view_right - 50:
            # 计算新的滚动位置，使小鸡在视野中偏左50px位置
            scroll_pos = (chicken_x - 50) / total_width
            scroll_pos = max(0, min(1, scroll_pos))  # 确保在0-1范围内
            
            # 设置滚动位置
            self.game_canvas.xview_moveto(scroll_pos)
    
    def draw_game(self):
        self.game_canvas.delete("all")
        
        if not self.game_active:
            # 显示欢迎信息
            self.game_canvas.create_text(300, 250, text="小鸡过马路", 
                                         font=("Arial", 28, "bold"), fill="#e94560")
            return
        
        # 绘制游戏界面
        settings = self.difficulty_settings[self.difficulty]
        multipliers = settings['multipliers']
        
        # 绘制经典UI界面
        self.draw_classic_ui()
        
        # 更新滚动区域
        self.game_canvas.configure(scrollregion=self.game_canvas.bbox("all"))
        
        # 确保小鸡在视野范围内
        self.ensure_chicken_visible()
    
    def draw_classic_ui(self):
        """绘制经典的原版UI界面，但使用Tkinter的图形元素和颜色"""
        settings = self.difficulty_settings[self.difficulty]
        multipliers = settings['multipliers']
        
        # 绘制UI框架
        cell_width = 100
        cell_height = 60
        start_x = 50
        start_y = 50  # 从较低位置开始，因为信息现在显示在标题下方
        
        # 绘制行标签
        labels = ["S", "T", "A", "R", "T"]
        label_colors = ["#3498db", "#2ecc71", "#f1c40f", "#e74c3c", "#9b59b6"]
        for i, (label, color) in enumerate(zip(labels, label_colors)):
            self.game_canvas.create_text(start_x - 20, start_y + i * cell_height + cell_height/2, 
                                       text=label, font=("Arial", 14, "bold"), fill=color)
        
        # 绘制所有阶段
        for idx in range(len(multipliers)):
            col_x = start_x + idx * cell_width + cell_width/2
            
            # 绘制单元格背景
            cell_color = "#2d4059"  # 默认单元格颜色
            if idx == self.current_stage:
                cell_color = "#4e9de0"  # 当前阶段高亮
            elif idx < self.current_stage:
                cell_color = "#27ae60"  # 已完成的阶段
            
            # 绘制单元格背景
            self.game_canvas.create_rectangle(
                start_x + idx * cell_width, start_y,
                start_x + (idx + 1) * cell_width, start_y + 5 * cell_height,
                fill=cell_color, outline="#34495e", width=2
            )
            
            # 绘制倍数
            multiplier_text = f"X{multipliers[idx]:.2f}"
            multiplier_color = "#f1f1f1"
            if idx == self.current_stage:
                multiplier_color = "#ffd369"  # 当前阶段倍数高亮
            
            self.game_canvas.create_text(col_x, start_y + cell_height + cell_height/2, 
                                       text=multiplier_text, font=("Arial", 12, "bold"), fill=multiplier_color)
            
            # 绘制小鸡位置
            if idx == self.current_stage and not self.chicken_animation_steps:
                # 绘制小鸡
                self.game_canvas.create_text(col_x, start_y + 2 * cell_height + cell_height/2, 
                                           text="🐥", font=("Arial", 20))
            
            # 绘制分隔线
            if idx > 0:
                x = start_x + idx * cell_width
                self.game_canvas.create_line(x, start_y, x, start_y + 5 * cell_height, 
                                           fill="#34495e", width=2)
        
        # 绘制水平分隔线
        for i in range(6):  # 5行需要6条水平线
            y = start_y + i * cell_height
            self.game_canvas.create_line(start_x, y, start_x + len(multipliers) * cell_width, y, 
                                       fill="#34495e", width=2)
        
        # 绘制汽车动画（如果正在进行）
        if self.animation_in_progress and self.car_animation_step > 0:
            self.draw_car_animation(start_x, start_y, cell_width, cell_height)
        
        # 绘制小鸡动画（如果正在进行）
        if self.chicken_animation_steps:
            self.draw_chicken_animation(start_x, start_y, cell_width, cell_height)
    
    def draw_chicken_animation(self, start_x, start_y, cell_width, cell_height):
        """绘制小鸡移动动画"""
        if not self.chicken_animation_steps:
            return
            
        step_idx, from_stage, to_stage, progress = self.chicken_animation_steps[0]
        
        # 计算小鸡位置
        from_x = start_x + from_stage * cell_width + cell_width/2
        to_x = start_x + to_stage * cell_width + cell_width/2
        y = start_y + 2 * cell_height + cell_height/2
        
        # 计算当前动画位置
        current_x = from_x + (to_x - from_x) * progress
        
        # 绘制小鸡
        self.game_canvas.create_text(current_x, y, text="🐥", font=("Arial", 20))
        
        # 绘制残影
        if len(self.chicken_animation_steps) > 1:
            for i in range(1, min(5, len(self.chicken_animation_steps))):  # 最多显示4个残影
                _, _, _, prev_progress = self.chicken_animation_steps[i]
                prev_x = from_x + (to_x - from_x) * prev_progress
                alpha = 0.7 - (i * 0.15)  # 透明度递减
                self.game_canvas.create_text(prev_x, y, text="🐥", font=("Arial", 20), 
                                           fill=self.get_transparent_color("#000000", alpha))
    
    def get_transparent_color(self, color, alpha):
        """获取带有透明度的颜色（通过混合背景色实现）"""
        # 这里简化处理，实际效果可能有限
        bg_color = "#0f3460"
        if alpha > 0.7:
            return color
        elif alpha > 0.4:
            return "#555555"
        else:
            return "#888888"
    
    def draw_car_animation(self, start_x, start_y, cell_width, cell_height):
        """绘制汽车动画，使用汽车模型"""
        settings = self.difficulty_settings[self.difficulty]
        multipliers = settings['multipliers']
        
        # 计算汽车位置
        car_x = start_x + self.current_stage * cell_width + cell_width/2
        car_y = start_y + 2 * cell_height + cell_height/2
        
        # 根据动画步骤绘制汽车
        if self.car_animation_step == 1:
            # 汽车从上方出现
            self.draw_car_model(car_x, start_y - 30, 1.0)
        elif self.car_animation_step == 2:
            # 汽车继续下移
            self.draw_car_model(car_x, start_y + cell_height/2, 1.0)
        elif self.car_animation_step == 3:
            # 汽车接近小鸡
            self.draw_car_model(car_x, start_y + cell_height, 1.0)
        elif self.car_animation_step == 4:
            # 汽车撞到小鸡
            self.draw_car_model(car_x, car_y, 1.0)
            self.game_canvas.create_text(car_x, car_y, text="💥", font=("Arial", 24), fill="#ff0000")
        elif self.car_animation_step >= 5:
            # 显示骷髅
            self.game_canvas.create_text(car_x, car_y, text="💀", font=("Arial", 24), fill="#ffffff")
    
    def draw_car_model(self, x, y, scale=1.0):
        """绘制汽车模型"""
        # 汽车主体
        car_width = 40 * scale
        car_height = 20 * scale
        wheel_radius = 8 * scale
        
        # 汽车主体
        self.game_canvas.create_rectangle(
            x - car_width/2, y - car_height/2,
            x + car_width/2, y + car_height/2,
            fill="#e74c3c", outline="#c0392b", width=2
        )
        
        # 汽车顶部
        self.game_canvas.create_rectangle(
            x - car_width/3, y - car_height/2 - 10 * scale,
            x + car_width/3, y - car_height/2,
            fill="#e74c3c", outline="#c0392b", width=2
        )
        
        # 车窗
        self.game_canvas.create_rectangle(
            x - car_width/4, y - car_height/2 - 8 * scale,
            x + car_width/4, y - car_height/2 - 2 * scale,
            fill="#3498db", outline="#2980b9", width=1
        )
        
        # 车轮
        self.game_canvas.create_oval(
            x - car_width/3 - wheel_radius, y + car_height/2 - wheel_radius/2,
            x - car_width/3 + wheel_radius, y + car_height/2 + wheel_radius/2,
            fill="#2c3e50", outline="#2c3e50"
        )
        
        self.game_canvas.create_oval(
            x + car_width/3 - wheel_radius, y + car_height/2 - wheel_radius/2,
            x + car_width/3 + wheel_radius, y + car_height/2 + wheel_radius/2,
            fill="#2c3e50", outline="#2c3e50"
        )
    
    def start_game(self):
        if self.current_bet <= 0:
            messagebox.showwarning("错误", "请先下注")
            return
        # 检查余额是否足够
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注")
            return
        
        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        self.current_stage = 0
        self.game_active = True
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 更新UI状态
        self.start_button.config(state=tk.DISABLED)
        self.reset_bet_button.pack_forget()  # 隐藏重设按钮
        self.advance_button.pack(pady=5)  # 显示前进按钮
        self.advance_button.config(state=tk.NORMAL)  # 确保按钮状态正常
        self.cash_out_button.pack(pady=5)  # 显示兑现按钮
        
        # 禁用筹码按钮
        for btn in self.chip_buttons:
            btn.configure(state=tk.DISABLED)
        
        # 禁用难度按钮
        for btn in self.difficulty_buttons:
            btn.configure(state=tk.DISABLED)
        
        # 滚动到最左边
        self.game_canvas.xview_moveto(0)
        
        self.update_display()
    
    def advance(self):
        if not self.game_active or self.animation_in_progress:
            return
        
        # 禁用前进按钮
        self.advance_button.config(state=tk.DISABLED)
        
        settings = self.difficulty_settings[self.difficulty]
        death_rate = settings['death_rate']
        multipliers = settings['multipliers']
        
        # 检查是否已经到达最后阶段
        if self.current_stage >= len(multipliers) - 1:
            self.complete_game()
            return
        
        # 记录当前阶段
        from_stage = self.current_stage
        to_stage = self.current_stage + 1
        
        # 开始小鸡移动动画
        self.play_chicken_animation(from_stage, to_stage, death_rate)
    
    def play_chicken_animation(self, from_stage, to_stage, death_rate):
        """播放小鸡移动动画"""
        if self.chicken_animation_id:
            self.root.after_cancel(self.chicken_animation_id)
        
        # 设置动画参数
        duration = 300  # 动画持续时间（毫秒）
        steps = 10      # 动画步数
        step_delay = duration // steps
        
        # 清空动画步骤
        self.chicken_animation_steps = []
        
        # 添加动画步骤
        for step in range(steps):
            progress = step / (steps - 1)  # 0.0 到 1.0
            self.chicken_animation_steps.append((step, from_stage, to_stage, progress))
        
        # 更新显示
        self.update_display()
        
        # 设置动画回调
        if len(self.chicken_animation_steps) > 1:
            self.chicken_animation_id = self.root.after(step_delay, 
                                                       lambda: self.continue_chicken_animation(from_stage, to_stage, death_rate))
        else:
            self.finish_chicken_animation(from_stage, to_stage, death_rate)
    
    def continue_chicken_animation(self, from_stage, to_stage, death_rate):
        """继续小鸡移动动画"""
        if len(self.chicken_animation_steps) > 1:
            # 移除已完成的一步
            self.chicken_animation_steps.pop(0)
            
            # 更新显示
            self.update_display()
            
            # 设置下一步动画
            duration = 300  # 动画持续时间（毫秒）
            steps = 10      # 动画步数
            step_delay = duration // steps
            
            self.chicken_animation_id = self.root.after(step_delay, 
                                                       lambda: self.continue_chicken_animation(from_stage, to_stage, death_rate))
        else:
            self.finish_chicken_animation(from_stage, to_stage, death_rate)
    
    def finish_chicken_animation(self, from_stage, to_stage, death_rate):
        """完成小鸡移动动画"""
        # 清空动画步骤
        self.chicken_animation_steps = []
        
        # 小鸡向前移动一步
        self.current_stage = to_stage
        self.update_display()
        
        # 检查是否遇到车祸
        if random.random() < death_rate:
            # 遇到车祸，播放汽车动画
            self.animation_in_progress = True
            self.car_animation_step = 0
            self.root.after(500, self.play_car_animation)  # 等待0.5秒后播放汽车动画
            self.last_win = 0.0
        else:
            # 没有遇到车祸，检查是否完成所有阶段
            settings = self.difficulty_settings[self.difficulty]
            multipliers = settings['multipliers']
            
            if self.current_stage >= len(multipliers) - 1:
                self.root.after(500, self.complete_game)  # 等待0.5秒后完成游戏
            else:
                # 等待0.5秒后重新启用前进按钮
                self.root.after(500, lambda: self.advance_button.config(state=tk.NORMAL))
    
    def play_car_animation(self):
        """播放汽车动画"""
        if self.car_animation_step < 6:
            self.car_animation_step += 1
            self.update_display()
            self.root.after(500, self.play_car_animation)  # 每500ms更新一次动画
        else:
            self.animation_in_progress = False
            self.game_active = False
            
            # 车祸后滚动到最左边
            self.game_canvas.xview_moveto(0)
            
            # 结束游戏
            self.end_game()
    
    def cash_out(self):
        if not self.game_active or self.current_stage == 0 or self.animation_in_progress:
            return
        
        # 计算赢得的金额
        settings = self.difficulty_settings[self.difficulty]
        multipliers = settings['multipliers']
        win_multiplier = multipliers[self.current_stage - 1] if self.current_stage > 0 else 1.0
        win_amount = self.bet_amount * win_multiplier
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 显示庆祝动画
        self.show_fireworks()
        
        # 结束游戏
        self.root.after(2000, self.end_game)  # 2秒后结束游戏
    
    def complete_game(self):
        # 计算赢得的金额
        settings = self.difficulty_settings[self.difficulty]
        multipliers = settings['multipliers']
        win_multiplier = multipliers[-1]
        win_amount = self.bet_amount * win_multiplier
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 显示庆祝动画
        self.show_fireworks()
        
        # 结束游戏
        self.root.after(2000, self.end_game)  # 2秒后结束游戏
    
    def show_fireworks(self):
        """显示烟花庆祝动画 - 在当前视图范围内"""
        colors = ["#ff0000", "#00ff00", "#0000ff", "#ffff00", "#ff00ff", "#00ffff"]
        
        # 获取当前视图范围
        scroll_left, scroll_right = self.game_canvas.xview()
        bbox = self.game_canvas.bbox("all")
        if bbox is None:
            return
            
        total_width = bbox[2] - bbox[0]
        view_left = scroll_left * total_width
        view_right = scroll_right * total_width
        canvas_height = self.game_canvas.winfo_height()
        
        for _ in range(15):  # 增加烟花数量
            # 在当前视图范围内随机生成烟花位置
            x = random.randint(int(view_left), int(view_right))
            y = random.randint(50, canvas_height - 50)  # 避免太靠近边缘
            color = random.choice(colors)
            
            # 创建烟花
            firework = self.game_canvas.create_oval(x-2, y-2, x+2, y+2, fill=color, outline=color)
            
            # 烟花爆炸效果
            def explode_firework(fw, cx, cy, step):
                if step < 20:
                    radius = step * 5
                    self.game_canvas.delete(fw)
                    new_fw = self.game_canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius, 
                                                         outline=color, width=2)
                    self.root.after(50, lambda: explode_firework(new_fw, cx, cy, step + 1))
                else:
                    self.game_canvas.delete(fw)
            
            self.root.after(random.randint(0, 1000), lambda: explode_firework(firework, x, y, 0))
        
        # 烟花结束后滚动到最左边
        self.root.after(2500, lambda: self.game_canvas.xview_moveto(0))
    
    def end_game(self):
        # 更新UI状态
        self.start_button.config(state=tk.NORMAL)
        self.advance_button.pack_forget()  # 隐藏前进按钮
        self.advance_button.config(state=tk.NORMAL)  # 确保按钮状态正常
        self.cash_out_button.pack_forget()  # 隐藏兑现按钮
        self.reset_bet_button.pack(pady=5)  # 显示重设按钮
        
        # 启用筹码按钮
        for btn in self.chip_buttons:
            btn.configure(state=tk.NORMAL)
        
        # 启用难度按钮
        for btn in self.difficulty_buttons:
            btn.configure(state=tk.NORMAL)
        
        # 更新显示
        self.update_display()
    
    def on_closing(self):
        """窗口关闭事件处理"""
        # 更新余额到JSON
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()

def main(initial_balance, username):
    """供small_games.py调用的主函数"""
    root = tk.Tk()
    game = ChickenCrossingGame(root, initial_balance, username)
    root.mainloop()
    # 返回更新后的余额
    return game.balance

if __name__ == "__main__":
    # 单独运行时的测试代码
    root = tk.Tk()
    # 使用测试余额和用户名
    game = ChickenCrossingGame(root, 1000.0, "test_user")
    root.mainloop()