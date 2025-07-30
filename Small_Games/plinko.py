import tkinter as tk
from tkinter import ttk, messagebox
import random
import json
import os
import time
import math
from collections import deque

# 获取数据文件的路径
def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')

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
    except FileNotFoundError:
        return []

# 更新余额到JSON文件
def update_balance_in_json(username, new_balance):
    users = load_user_data()
    user_found = False
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:.2f}"
            user_found = True
            break
    
    if not user_found:
        users.append({
            'user_name': username,
            'cash': f"{new_balance:.2f}"
        })
    
    save_user_data(users)

class CircleButton(tk.Canvas):
    """自定义圆形按钮"""
    def __init__(self, master, text, bg_color, fg_color, command=None, radius=30, *args, **kwargs):
        super().__init__(master, width=radius*2, height=radius*2, 
                         highlightthickness=0, bg="#16213e", *args, **kwargs)
        self.radius = radius
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.text = text
        self.command = command
        
        # 绘制圆形按钮
        self.create_oval(0, 0, radius*2, radius*2, fill=bg_color, outline="#16213e", width=2)
        self.create_text(radius, radius, text=text, fill=fg_color, 
                        font=("Arial", 18, "bold"))
        
        # 绑定点击事件
        self.bind("<Button-1>", self.on_click)
    
    def on_click(self, event):
        if self.command:
            self.command()

class PlinkoGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("Plinko 游戏")
        self.root.geometry("1000x800+50+10")
        self.root.resizable(0,0)
        self.root.configure(bg="#1a1a2e")
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 游戏数据
        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0
        self.risk_level = "1"  # 1=低风险, 2=中风险, 3=高风险
        self.game_active = False
        self.chip_buttons = []
        self.current_bet = 0.0
        self.balls = []  # 存储所有弹珠的位置和状态
        self.animation_running = False
        self.history = deque(maxlen=8)  # 存储最近8次结果
        self.last_payouts = []  # 存储最近弹珠的赔率信息
        self.pegs = []  # 存储所有钉子的位置
        self.active_balls = 0  # 当前活动弹珠数量
        
        # 定义赔率 - 使用指定的赔率设置
        self.payouts = {
            "1": [5.6, 2.1, 1.1, 1, 0.5, 1, 1.1, 2.1, 5.6],
            "2": [13, 3, 1.3, 0.7, 0.4, 0.7, 1.3, 3, 13],
            "3": [29, 4, 1.5, 0.3, 0.2, 0.3, 1.5, 4, 29],
        }
        
        # 物理参数
        self.gravity = 0.5
        self.damping = 0.8
        self.elasticity = 0.8
        
        # 添加下注金额显示变量
        self.bet_var = tk.StringVar()
        self.bet_var.set("$0.00")
        
        # 创建UI
        self.create_widgets()
        self.update_display()
        
        # 绑定画布大小变化事件
        self.board_canvas.bind("<Configure>", self.on_canvas_resize)
    
    def on_canvas_resize(self, event):
        """当画布大小改变时重新绘制游戏板"""
        self.update_display()
    
    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 左侧 - 游戏板
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(left_frame, text="Plinko 游戏", font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#e94560").pack(pady=10)
        
        self.board_canvas = tk.Canvas(left_frame, bg="#0f3460", bd=0, highlightthickness=0)
        self.board_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
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
            ("$1", '#ff0000', 'white'),    # 红色
            ("$5", '#00ff00', 'black'),    # 绿色
            ("$10", '#000000', 'white'),   # 黑色
            ("$25", "#FF7DDA", 'black'),   # 粉色
            ("$100", '#ffffff', 'black')   # 白色
        ]
        
        self.chip_buttons = []
        for text, bg_color, fg_color in chips:
            btn = CircleButton(
                chips_frame, text=text, bg_color=bg_color, fg_color=fg_color,
                command=lambda t=text: self.add_chip(t[1:])  # 去掉$符号
            )
            btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.chip_buttons.append(btn)
        
        # 风险选择
        risk_frame = tk.Frame(right_frame, bg="#16213e")
        risk_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(risk_frame, text="风险等级:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.risk_var = tk.StringVar()
        self.risk_var.set("1")  # 默认设置为简单
        
        risks = [
            ("简单", "1"),  # 修改文本为"简单"
            ("中等", "2"),  # 修改文本为"中等"
            ("困难", "3")   # 修改文本为"困难"
        ]
        
        self.risk_buttons = []
        for text, value in risks:
            # 如果是简单风险，设置不同的背景色
            btn_bg = "#4e9de0" if value == "1" else "#2d4059"
            btn = tk.Button(
                risk_frame, text=text, font=("Arial", 10),
                bg=btn_bg, fg="white", 
                width=8, height=1, relief=tk.RAISED,
                command=lambda v=value: self.set_risk(v)
            )
            btn.pack(side=tk.LEFT, padx=2, pady=2)
            self.risk_buttons.append(btn)
        
        # 游戏按钮
        button_frame = tk.Frame(right_frame, bg="#16213e")
        button_frame.pack(fill=tk.X, padx=10, pady=20)
        
        self.start_button = tk.Button(
            button_frame, text="发射弹珠", font=("Arial", 12, "bold"),
            bg="#27ae60", fg="white", width=12, command=self.launch_ball
        )
        self.start_button.pack(pady=5)
        
        # 添加提示文本
        tk.Label(button_frame, text="点击按钮发射弹珠\n每次点击发射一颗", 
                font=("Arial", 9), bg="#16213e", fg="#bdc3c7", justify=tk.LEFT).pack(pady=5)
        
        self.reset_bet_button = tk.Button(
            button_frame, text="重设下注金额", font=("Arial", 12),
            bg="#3498db", fg="white", width=12, command=self.reset_bet
        )
        self.reset_bet_button.pack(pady=5)
        
        # 显示活动弹珠数量
        self.active_label = tk.Label(button_frame, text="活动弹珠: 0", 
                                   font=("Arial", 10), bg="#16213e", fg="#ffd369")
        self.active_label.pack(pady=5)
                
        # 游戏信息
        info_frame = tk.Frame(right_frame, bg="#16213e")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Label(info_frame, text="游戏规则:", font=("Arial", 12, "bold"), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, pady=(0, 5))
        
        rules = [
            "1. 选择下注金额和风险等级",
            "2. 点击发射弹珠按钮",
            "3. 每次点击发射一颗弹珠",
            "4. 可连续点击发射多颗弹珠",
            "5. 观察钢珠下落过程",
            "6. 钢珠落入底部槽位后获得奖金",
            "7. 不同风险等级对应不同赔率",
            "8. 高风险高回报，低风险低回报"
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
    
    def add_chip(self, amount):
        # 如果有活动弹珠，禁用筹码按钮
        if self.active_balls > 0:
            return
            
        try:
            amount_val = float(amount)
            new_bet = self.current_bet + amount_val
            if new_bet <= self.balance:
                self.current_bet = new_bet
                self.bet_var.set(f"${self.current_bet:.2f}")
                # 更新画布上的下注显示
                self.update_display()
        except ValueError:
            pass
    
    def reset_bet(self):
        # 如果有活动弹珠，禁用重置按钮
        if self.active_balls > 0:
            return
            
        self.current_bet = 0.0
        self.bet_var.set("$0.00")
        # 更新画布上的下注显示
        self.update_display()
    
    def set_risk(self, risk):
        # 如果有活动弹珠，禁用风险按钮
        if self.active_balls > 0:
            return
            
        self.risk_level = risk
        # 更新按钮样式
        for i, (text, value) in enumerate([("简单", "1"), ("中等", "2"), ("困难", "3")]):
            if value == risk:
                self.risk_buttons[i].configure(bg="#4e9de0")
            else:
                self.risk_buttons[i].configure(bg="#2d4059")
        
        self.update_display()
    
    def update_display(self):
        self.balance_var.set(f"${self.balance:.2f}")
        self.active_label.config(text=f"活动弹珠: {self.active_balls}")
        self.draw_board()
    
    def draw_board(self):
        self.board_canvas.delete("all")
        width = self.board_canvas.winfo_width()
        height = self.board_canvas.winfo_height()
        
        if width < 10 or height < 10:
            return
        
        # 绘制金字塔形状的游戏板背景
        self.draw_pyramid_shape(width, height)
        
        # 绘制挡板上的钉子
        self.draw_pegs(width, height)
        
        # 绘制底部槽位和赔率
        self.draw_slots(width, height)
        
        # 绘制历史记录
        self.draw_history(width, height)
        
        # 绘制所有弹珠（只绘制活动中的弹珠）
        for ball in self.balls:
            if not ball['finished'] and ball['positions']:
                # 绘制弹珠路径
                for i in range(1, len(ball['positions'])):
                    x1, y1 = ball['positions'][i-1]
                    x2, y2 = ball['positions'][i]
                    self.board_canvas.create_line(x1, y1, x2, y2, 
                                                 fill=ball['color'], width=2, 
                                                 dash=(2, 1) if i < len(ball['positions']) - 1 else ())
                
                # 绘制当前弹珠位置
                last_x, last_y = ball['positions'][-1]
                self.board_canvas.create_oval(last_x-8, last_y-8, last_x+8, last_y+8, 
                                            fill=ball['color'], outline="#ffffff", width=2)
        
        # 在左上角绘制当前下注金额
        self.draw_bet_info()
    
    def draw_bet_info(self):
        """在左上角绘制当前下注金额"""
        # 位置参数
        x = 20
        y = 50
        padding = 10
        box_width = 200
        
        # 绘制标题
        self.board_canvas.create_text(
            x + box_width // 2, y + padding,
            text="下注金额", 
            font=("Arial", 18, "bold"), 
            fill="#ffd369"
        )
        
        # 绘制下注金额
        self.board_canvas.create_text(
            x + box_width // 2, y + padding * 4,
            text=f"${self.current_bet:.2f}", 
            font=("Arial", 24, "bold"), 
            fill="#4cc9f0"
        )
    
    def draw_pyramid_shape(self, width, height):
        """绘制金字塔形状的挡板"""
        # 金字塔顶部
        top_width = 50
        top_y = 100
        
        # 金字塔底部
        bottom_width = width - 200
        bottom_y = height - 250  # 为收集框架留出空间
        
        # 绘制金字塔轮廓
        self.board_canvas.create_line(width//2 - top_width//2, top_y, 
                                     width//2 + top_width//2, top_y, 
                                     fill="#2d4059", width=2)
        
        self.board_canvas.create_line(width//2 - top_width//2, top_y, 
                                     width//2 - bottom_width//2, bottom_y, 
                                     fill="#2d4059", width=2)
        
        self.board_canvas.create_line(width//2 + top_width//2, top_y, 
                                     width//2 + bottom_width//2, bottom_y, 
                                     fill="#2d4059", width=2)
        
        # 填充金字塔内部
        self.board_canvas.create_polygon(
            width//2 - top_width//2, top_y,
            width//2 + top_width//2, top_y,
            width//2 + bottom_width//2, bottom_y,
            width//2 - bottom_width//2, bottom_y,
            fill="#0f3460", outline="#2d4059", width=2
        )
    
    def draw_pegs(self, width, height):
        """绘制挡板上的钉子（金字塔形状分布）"""
        if width < 100 or height < 100:
            return
        
        # 金字塔顶部
        top_width = 50
        top_y = 100
        
        # 金字塔底部
        bottom_width = width - 200
        bottom_y = height - 250  # 为收集框架留出空间
        
        # 总行数：8行（对应9个槽位）
        rows = 8
        peg_radius = 5
        
        # 每行钉子数量（对应槽位布局）
        pegs_per_row = [1, 2, 3, 4, 5, 6, 7, 8]  # 每行钉子数量
        
        # 清空之前的钉子位置
        self.pegs = []
        
        for row in range(rows):
            # 计算当前行的宽度
            progress = row / (rows - 1)
            current_width = top_width + (bottom_width - top_width) * progress
            
            # 计算当前行的y位置
            y = top_y + (bottom_y - top_y) * progress
            
            # 获取当前行钉子数量
            peg_count = pegs_per_row[row]
            
            # 绘制当前行的钉子
            for i in range(peg_count):
                # 计算钉子的x位置（均匀分布）
                spacing = current_width / (peg_count + 1)
                x = width//2 - current_width//2 + spacing * (i + 1)
                
                # 存储钉子位置
                self.pegs.append((x, y))
                
                # 绘制钉子
                self.board_canvas.create_oval(
                    x - peg_radius, 
                    y - peg_radius,
                    x + peg_radius, 
                    y + peg_radius,
                    fill="#ffffff", outline="#aaaaaa"
                )
    
    def draw_slots(self, width, height):
        """绘制底部槽位和赔率（凹形设计）"""
        # 绘制底部槽位（9个槽位）
        slot_count = 9
        slot_width = (width - 200) // slot_count
        start_x = 100
        start_y = height - 240  # 为收集框架留出空间
        
        # 创建凹形槽位 - 中间低，两边高
        slot_heights = [35, 35, 35, 35, 30, 35, 35, 35, 35]  # 凹形高度设计
        
        # 绘制槽位分隔线和背景
        for i in range(slot_count):
            # 计算当前槽位的x位置
            x = start_x + i * slot_width
            
            # 计算当前槽位的高度
            slot_height = slot_heights[i]
            
            # 绘制槽位背景（凹形）
            self.board_canvas.create_rectangle(
                x, start_y, 
                x + slot_width, start_y + slot_height,
                fill="#2d4059", outline="#aaaaaa"
            )
            
            # 绘制赔率标签
            payout = self.payouts[self.risk_level][i] if i < len(self.payouts[self.risk_level]) else 0.0
            
            # 格式化赔率显示
            payout_text = f"{payout:.1f}X" if payout != int(payout) else f"{int(payout)}X"
            self.board_canvas.create_text(
                x + slot_width // 2, start_y + slot_height // 2, 
                text=payout_text, 
                font=("Arial", 10, "bold"), 
                fill="#ffd369"
            )
    
    def draw_history(self, width, height):
        """绘制历史记录表格"""
        # 表格位置：在底部槽位下方
        table_top = height - 150
        table_height = 40
        table_width = width - 100
        cell_width = table_width / 8
        
        # 绘制表格标题（1到8）
        title_y = table_top - 20
        for i in range(8):
            x = 50 + i * cell_width + cell_width/2
            self.board_canvas.create_text(x, title_y, text=str(i+1), 
                                        font=("Arial", 10, "bold"), fill="#f1f1f1")
        
        # 绘制表格背景
        self.board_canvas.create_rectangle(50, table_top, 50+table_width, table_top+table_height, 
                                        fill="#1a3c6c", outline="#0f3460", width=1)
        
        # 绘制单元格分隔线
        for i in range(1, 8):
            x = 50 + i * cell_width
            self.board_canvas.create_line(x, table_top, x, table_top+table_height, 
                                        fill="#0f3460", width=1)
        
        # 填充历史记录
        for i in range(8):
            x = 50 + i * cell_width + cell_width/2
            y = table_top + table_height/2
            
            # 获取历史记录（最新的在最左边）
            if i < len(self.history):
                record = self.history[i]
                # 根据赔率设置颜色
                try:
                    # 去掉X，转换成数字
                    value = float(record.strip('X'))
                    if value > 1:
                        color = "#2ecc71"  # 绿色
                    elif value < 1:
                        color = "#e74c3c"  # 红色
                    else:
                        color = "#f1c40f"  # 黄色
                except:
                    color = "#f1f1f1"
            else:
                record = "~~"
                color = "#bdc3c7"
            
            self.board_canvas.create_text(x, y, text=record, 
                                        font=("Arial", 12, "bold"), 
                                        fill=color)
    
    def launch_ball(self):
        """立即发射一颗弹珠"""
        if self.current_bet <= 0:
            messagebox.showwarning("错误", "请先下注")
            return
            
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注")
            return
        
        # 扣除下注金额
        self.bet_amount = self.current_bet
        self.balance -= self.current_bet
        self.game_active = True
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 添加弹珠
        self.add_ball()
        
        # 如果动画没有运行，开始动画
        if not self.animation_running:
            self.animation_running = True
            self.animate_balls()
    
    def add_ball(self):
        """添加一颗新弹珠"""
        width = self.board_canvas.winfo_width()
        
        # 随机选择弹珠颜色
        colors = ["#ff5252", "#4fc3f7", "#69f0ae", "#ffd740", "#ff4081"]
        color = random.choice(colors)
        
        # 起始位置在顶部中央
        start_x = width // 2
        start_y = 100
        
        # 添加物理参数
        self.balls.append({
            'x': start_x,  # 当前位置x
            'y': start_y,  # 当前位置y
            'vx': 0.0,    # x方向速度
            'vy': 0.0,    # y方向速度
            'positions': [(start_x, start_y)],
            'color': color,
            'finished': False,
            'slot': None,
            'payout': None,
            'start_time': time.time()  # 记录发射时间
        })
        
        # 更新活动弹珠计数
        self.active_balls += 1
        self.update_display()
    
    def animate_balls(self):
        """动画所有弹珠"""
        if not self.balls:
            self.animation_running = False
            return
            
        width = self.board_canvas.winfo_width()
        height = self.board_canvas.winfo_height()
        
        if width < 100 or height < 100:
            # 如果画布太小，继续循环
            self.root.after(30, self.animate_balls)
            return
        
        # 更新所有弹珠位置
        active_balls = 0
        finished_balls = []
        
        for i, ball in enumerate(self.balls):
            if not ball['finished']:
                self.update_ball_position(ball, width, height)
                if not ball['finished']:
                    active_balls += 1
                else:
                    # 标记已完成但尚未处理的弹珠
                    finished_balls.append(i)
        
        # 更新活动弹珠计数
        self.active_balls = active_balls
        self.update_display()
        
        # 处理已完成的弹珠
        if finished_balls:
            self.process_finished_balls(finished_balls)
        
        # 如果有活动弹珠，继续动画
        if active_balls > 0:
            self.root.after(30, self.animate_balls)
        else:
            self.animation_running = False
    
    def process_finished_balls(self, indices):
        """处理已完成的弹珠"""
        total_winnings = 0
        result_text = ""
        
        # 按时间顺序排序（先完成的在前）
        sorted_indices = sorted(indices, key=lambda i: self.balls[i]['start_time'])
        
        for i in sorted_indices:
            if i >= len(self.balls):
                continue
                
            ball = self.balls[i]
            if ball['slot'] is not None:
                slot_index = ball['slot'] - 1  # 槽位索引从0开始
                payout = self.payouts[self.risk_level][slot_index] if slot_index < len(self.payouts[self.risk_level]) else 0.0
                winnings = self.bet_amount * payout
                total_winnings += winnings
                
                # 格式化赔率字符串
                if payout.is_integer():
                    payout_str = f"{int(payout)}X"
                else:
                    payout_str = f"{payout:.1f}X"
                
                # 添加到历史记录（最新在最前面）
                self.history.appendleft(payout_str)
                
                # 立即显示该弹珠的结果
                self.show_ball_result(ball, payout_str, winnings)
                
                # 更新余额
                self.balance += winnings
                
                # 更新JSON余额
                update_balance_in_json(self.username, self.balance)
                
                # 更新显示
                self.update_display()
        
        # 从列表中移除已完成的弹珠
        # 注意：从后往前移除以避免索引变化
        for i in sorted(indices, reverse=True):
            if i < len(self.balls):
                self.balls.pop(i)
    
    def show_ball_result(self, ball, payout_str, winnings):
        """显示单颗弹珠的结果"""
        # 在游戏板上显示结果（短暂显示）
        width = self.board_canvas.winfo_width()
        height = self.board_canvas.winfo_height()
        slot_width = (width - 200) // 9
        start_x = 100
        slot_index = ball['slot'] - 1
        x = start_x + slot_index * slot_width + slot_width // 2
        y = height - 280  # 在槽位上方显示
        
        # 创建结果文本
        result_id = self.board_canvas.create_text(
            x, y,
            text=f"{payout_str} ${winnings:.2f}",
            font=("Arial", 12, "bold"),
            fill="#ffd369"
        )
        
        # 3秒后移除结果文本
        self.root.after(3000, lambda: self.board_canvas.delete(result_id))
    
    def update_ball_position(self, ball, width, height):
        """更新单个弹珠位置（使用物理碰撞模型）"""
        if ball['finished']:
            return
            
        # 应用重力
        ball['vy'] += self.gravity
        
        # 计算新位置
        new_x = ball['x'] + ball['vx']
        new_y = ball['y'] + ball['vy']
        
        # 边界检查（金字塔形状）
        top_y = 100
        bottom_y = height - 250  # 为收集框架留出空间
        
        # 计算金字塔在当前位置的宽度
        progress = (new_y - top_y) / (bottom_y - top_y)
        current_width = 50 + (width - 250) * progress
        
        # 确保弹珠在金字塔范围内
        min_x = width//2 - current_width//2 + 10
        max_x = width//2 + current_width//2 - 10
        
        # 边界碰撞检测
        if new_x < min_x:
            new_x = min_x
            ball['vx'] = -ball['vx'] * self.damping
        elif new_x > max_x:
            new_x = max_x
            ball['vx'] = -ball['vx'] * self.damping
        
        # 钉子碰撞检测
        ball_radius = 8
        peg_radius = 5
        
        for peg in self.pegs:
            px, py = peg
            # 计算弹珠与钉子的距离
            dist = math.sqrt((new_x - px)**2 + (new_y - py)**2)
            
            # 如果发生碰撞
            if dist <= ball_radius + peg_radius:
                # 计算碰撞方向向量
                dx = new_x - px
                dy = new_y - py
                
                if dx == 0 and dy == 0:
                    continue
                
                # 单位化向量
                length = math.sqrt(dx*dx + dy*dy)
                nx = dx / length
                ny = dy / length
                
                # 计算碰撞后的速度
                dot_product = ball['vx'] * nx + ball['vy'] * ny
                ball['vx'] = ball['vx'] - 2 * dot_product * nx
                ball['vy'] = ball['vy'] - 2 * dot_product * ny
                
                # 应用阻尼
                ball['vx'] *= self.damping
                ball['vy'] *= self.damping
                
                # 调整位置防止陷入钉子
                overlap = (ball_radius + peg_radius) - dist
                new_x += nx * overlap * 1.1
                new_y += ny * overlap * 1.1
                
                # 添加随机扰动使运动更自然
                ball['vx'] += random.uniform(-0.5, 0.5)
        
        # 更新位置
        ball['x'] = new_x
        ball['y'] = new_y
        ball['positions'].append((new_x, new_y))
        
        # 检查是否到达底部
        if new_y >= bottom_y:
            ball['finished'] = True
            # 确定落入的槽位（9个槽位）
            slot_width = (width - 200) // 9
            start_x = 100
            slot_index = min(max(0, int((new_x - start_x) // slot_width)), 8)
            ball['slot'] = slot_index + 1  # 槽位从1开始编号
            
            # 获取赔率
            payout = self.payouts[self.risk_level][slot_index] if slot_index < len(self.payouts[self.risk_level]) else 0.0
            ball['payout'] = f"{payout:.1f}X" if payout != int(payout) else f"{int(payout)}X"
            
            # 存储最近赔率
            self.last_payouts.append({
                'slot': ball['slot'],
                'payout': ball['payout'],
                'color': ball['color']
            })
    
    def on_closing(self):
        """窗口关闭事件处理"""
        # 更新余额到JSON
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()

def main(initial_balance, username):
    """供small_games.py调用的主函数"""
    root = tk.Tk()
    game = PlinkoGame(root, initial_balance, username)
    root.mainloop()
    # 返回更新后的余额
    return game.balance

if __name__ == "__main__":
    # 单独运行时的测试代码
    root = tk.Tk()
    # 使用测试余额和用户名
    game = PlinkoGame(root, 1000.0, "test_user")
    root.mainloop()