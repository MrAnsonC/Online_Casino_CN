import tkinter as tk
from tkinter import ttk, messagebox
import random
import json
import os
import time
import math

def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')

def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_user_data():
    file_path = get_data_file_path()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:.2f}"
            break
    save_user_data(users)

class CircleButton(tk.Canvas):
    def __init__(self, master, text, bg_color, fg_color, command=None, radius=30, *args, **kwargs):
        super().__init__(master, width=radius*2, height=radius*2, 
                         highlightthickness=0, bg="#16213e", *args, **kwargs)
        self.radius = radius
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.text = text
        self.command = command
        self.enabled = True  # 添加启用状态标志
        
        self.create_oval(0, 0, radius*2, radius*2, fill=bg_color, outline="#16213e", width=2)
        self.create_text(radius, radius, text=text, fill=fg_color, 
                        font=("Arial", 18, "bold"))
        
        self.bind("<Button-1>", self.on_click)
    
    def on_click(self, event):
        # 只在启用状态下响应点击
        if self.enabled and self.command:
            self.command()
    
    def configure(self, state=None, **kwargs):
        """重写configure方法以支持状态改变"""
        if state is not None:
            self.enabled = (state == tk.NORMAL)
        super().configure(**kwargs)

class ThimblesGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("三杯球游戏")
        self.root.geometry("1000x700+50+10")
        self.root.resizable(0,0)
        self.root.configure(bg="#1a1a2e")
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 游戏数据
        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0
        self.ball_count = 1  # 1或2个球
        self.cup_positions = [0, 1, 2]  # 杯子的位置
        self.ball_position = []  # 球的位置
        self.selected_cup = -1  # 玩家选择的杯子
        self.game_active = False
        self.animation_active = False
        self.last_win = 0.0
        self.chip_buttons = []
        self.current_bet = 0.0
        self.animation_id = None  # 用于存储动画ID
        self.game_state = "idle"  # idle, showing_balls, shuffling, waiting_selection, revealing, showing_all
        self.cup_y_positions = [400, 400, 400]  # 每个杯子的Y轴位置
        self.ball_fixed_positions = {}  # 存储球的固定位置
        self.cup_colors = ["#2d4059", "#2d4059", "#2d4059"]  # 杯子颜色
        
        # 杯子的图形对象
        self.cup_items = {0: [], 1: [], 2: []}
        
        # 赔率
        self.odds = {
            1: 2.88,  # 1个球的赔率
            2: 1.44   # 2个球的赔率
        }
        
        # 创建UI
        self.create_widgets()
        self.update_display()
    
    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 左侧 - 游戏区域
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(left_frame, text="三杯球游戏", font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#e94560").pack(pady=10)
        
        self.game_canvas = tk.Canvas(left_frame, bg="#0f3460", bd=0, highlightthickness=0)
        self.game_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
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
            ("$5", '#ff0000', 'white'),
            ("$25", '#00ff00', 'black'),
            ("$100", '#000000', 'white'),
            ("$500", "#FF7DDA", 'black'),
            ("$1K", '#ffffff', 'black')
        ]
        
        self.chip_buttons = []
        for text, bg_color, fg_color in chips:
            btn = CircleButton(
                chips_frame, text=text, bg_color=bg_color, fg_color=fg_color,
                command=lambda t=text: self.add_chip(t[1:])
            )
            btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.chip_buttons.append(btn)
        
        # 球数量选择
        ball_frame = tk.Frame(right_frame, bg="#16213e")
        ball_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(ball_frame, text="球的数量:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.ball_var = tk.IntVar()
        self.ball_var.set(1)
        
        self.ball_buttons = []
        for text, value in [("1个球", 1), ("2个球", 2)]:
            btn = tk.Radiobutton(
                ball_frame, text=text, variable=self.ball_var, value=value,
                font=("Arial", 10), bg="#16213e", fg="#f1f1f1", selectcolor="#2d4059",
                command=self.set_ball_count
            )
            btn.pack(side=tk.LEFT, padx=5)
            self.ball_buttons.append(btn)
        
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
                
        # 游戏信息
        info_frame = tk.Frame(right_frame, bg="#16213e")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Label(info_frame, text="游戏规则:", font=("Arial", 12, "bold"), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, pady=(0, 5))
        
        rules = [
            "1. 选择下注金额和球的数量",
            "2. 点击开始游戏按钮",
            "3. 观看杯子移动动画",
            "4. 动画结束后选择一个杯子",
            "5. 如果选择的杯子中有球，赢得下注金额×赔率",
            "6. 1个球赔率:2.88, 2个球赔率:1.44"
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
        self.bet_var.set("$0.00")
        tk.Label(bet_frame, textvariable=self.bet_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
        
        # 上局获胜金额
        win_frame = tk.Frame(bet_win_frame, bg="#16213e")
        win_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))
        
        tk.Label(win_frame, text="上局获胜金额:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.last_win_var = tk.StringVar()
        self.last_win_var.set("$0.00")
        tk.Label(win_frame, textvariable=self.last_win_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
    
    def add_chip(self, amount):
        # 只有在游戏空闲状态下才能添加筹码
        if self.game_state != "idle":
            return
            
        try:
            amount_val = float(amount)
            new_bet = self.current_bet + amount_val
            if new_bet <= self.balance:
                self.current_bet = new_bet
                self.bet_var.set(f"${self.current_bet:.2f}")
        except ValueError:
            pass
    
    def reset_bet(self):
        self.current_bet = 0.0
        self.bet_var.set("$0.00")
    
    def set_ball_count(self):
        self.ball_count = self.ball_var.get()
    
    def update_display(self):
        self.balance_var.set(f"${self.balance:.2f}")
        self.last_win_var.set(f"${self.last_win:.2f}")
        self.draw_game()
    
    def draw_japanese_teacup(self, x, y, cup_id, is_open=False):
        """绘制3D日本茶杯（无柄）"""
        cup_height = 150
        cup_width = 100
        
        # 使用存储的杯子颜色
        cup_color = self.cup_colors[cup_id]
        
        items = []
        
        if not is_open:
            # 绘制杯身（3D圆柱效果）
            # 杯底
            items.append(self.game_canvas.create_oval(
                x - cup_width//2, y - 10,
                x + cup_width//2, y + 10,
                fill=cup_color, outline="#1a1a2e", width=2
            ))
            
            # 杯身主体
            items.append(self.game_canvas.create_rectangle(
                x - cup_width//2, y - cup_height + 20,
                x + cup_width//2, y,
                fill=cup_color, outline="#1a1a2e", width=2
            ))
            
            # 杯口
            items.append(self.game_canvas.create_oval(
                x - cup_width//2, y - cup_height + 10,
                x + cup_width//2, y - cup_height + 30,
                fill=cup_color, outline="#1a1a2e", width=2
            ))
            
            # 添加纹理和细节
            items.append(self.game_canvas.create_line(
                x - cup_width//3, y - cup_height + 50,
                x - cup_width//3, y - 30,
                fill="#3a506b", width=2
            ))
            items.append(self.game_canvas.create_line(
                x + cup_width//3, y - cup_height + 50,
                x + cup_width//3, y - 30,
                fill="#3a506b", width=2
            ))
        else:
            # 打开状态的杯子 - 向上移动
            open_y = y - 100  # 抬起100px
            
            # 绘制杯身（正放）
            items.append(self.game_canvas.create_rectangle(
                x - cup_width//2, open_y,
                x + cup_width//2, open_y + cup_height - 20,
                fill=cup_color, outline="#1a1a2e", width=2
            ))
            
            items.append(self.game_canvas.create_oval(
                x - cup_width//2, open_y + cup_height - 40,
                x + cup_width//2, open_y + cup_height - 10,
                fill=cup_color, outline="#1a1a2e", width=2
            ))
            
            # 杯口（顶部）
            items.append(self.game_canvas.create_oval(
                x - cup_width//2, open_y - 10,
                x + cup_width//2, open_y + 10,
                fill=cup_color, outline="#1a1a2e", width=2
            ))
            
            # 添加纹理和细节
            items.append(self.game_canvas.create_line(
                x - cup_width//3, open_y + 30,
                x - cup_width//3, open_y + cup_height - 50,
                fill="#3a506b", width=2
            ))
            items.append(self.game_canvas.create_line(
                x + cup_width//3, open_y + 30,
                x + cup_width//3, open_y + cup_height - 50,
                fill="#3a506b", width=2
            ))
        
        return items
    
    def draw_game(self):
        # 清除画布
        self.game_canvas.delete("all")
        self.cup_items = {0: [], 1: [], 2: []}
        
        # 杯子大小和位置
        cup_height = 150
        ball_radius = 25
        start_x = 100
        start_y = 400
        spacing = 175
        
        # 状态消息文本
        status_text = ""
        if self.game_state == "idle":
            status_text = "选择下注金额和球的数量后点击开始游戏"
        elif self.game_state == "showing_balls":
            status_text = "请记住球的位置 并小心观察杯子的转动"
        elif self.game_state == "shuffling":
            status_text = "杯子正在转动中 请稍后........"
        elif self.game_state == "waiting_selection":
            status_text = "杯子转完成啦！ 请选择........"
        elif self.game_state == "revealing":
            status_text = "杯子正在打开！ 请稍后........"
        elif self.game_state == "showing_all":
            # 检查玩家是否猜中
            if self.selected_cup in self.ball_position:
                # 计算赢得的金额
                win_multiplier = self.odds[self.ball_count]
                win_amount = self.bet_amount * win_multiplier
                status_text = f"恭喜你猜中啦！ 你赢了${win_amount:.2f}！"
            else:
                status_text = "很抱歉你输了！ 送你好运气...."
        
        # 显示状态消息
        if status_text:
            self.game_canvas.create_text(275, 50, text=status_text, 
                                       font=("Arial", 14), fill="#bdc3c7")
        
        # 绘制球（如果可见） - 先绘制球
        ball_items = []
        for i in range(3):
            x = start_x + self.cup_positions[i] * spacing
            
            # 在展示球状态或揭示状态时显示球
            if (self.game_state == "showing_balls" and i in self.ball_position) or \
               (self.game_state == "revealing" and self.selected_cup == i and i in self.ball_position) or \
               (self.game_state == "showing_all" and i in self.ball_position):
                # 球的位置固定在桌面上（390px）
                ball_y = 390
                ball_id = self.draw_ball(x, ball_y, ball_radius)
                ball_items.append((ball_id, x, ball_y))
        
        # 绘制三个杯子
        for i in range(3):
            x = start_x + self.cup_positions[i] * spacing
            y = self.cup_y_positions[i]
            
            # 绘制日本茶杯
            is_open = (self.game_state == "showing_balls") or \
                     (self.game_state == "revealing" and self.selected_cup == i) or \
                     (self.game_state == "showing_all")
            cup_id = self.draw_japanese_teacup(x, y, i, is_open)
            self.cup_items[i] = cup_id
            
            # 添加可点击区域（在等待选择状态）
            if self.game_state == "waiting_selection":
                tag_name = f"cup_{i}"
                cup_area = self.game_canvas.create_rectangle(
                    x - 60, y - cup_height,
                    x + 60, y,
                    fill="", outline="", tags=tag_name
                )
                self.cup_items[i].append(cup_area)
                self.game_canvas.tag_bind(tag_name, "<Button-1>", 
                                        lambda e, idx=i: self.select_cup(idx))
        
        # 确保球在杯子下方
        for ball_id_list, x, y in ball_items:
            for ball_id in ball_id_list:
                self.game_canvas.lower(ball_id)
    
    def draw_ball(self, x, y, radius):
        # 绘制球体
        ball = self.game_canvas.create_oval(x-radius, y-radius,
                                         x+radius, y+radius,
                                         fill="#ffd369", outline="#e94560", width=2)
        
        # 绘制球的高光
        highlight_radius = radius * 0.3
        highlight = self.game_canvas.create_oval(x-radius*0.5, y-radius*0.7,
                                               x-radius*0.5+highlight_radius, y-radius*0.7+highlight_radius,
                                               fill="white", outline="")
        
        # 绘制足球图案 - 简化图案使其更清晰
        # 中心十字
        self.game_canvas.create_line(x-radius, y, x+radius, y, fill="black", width=1)
        self.game_canvas.create_line(x, y-radius, x, y+radius, fill="black", width=1)
        
        # 对角线
        self.game_canvas.create_line(x-radius*0.7, y-radius*0.7, x+radius*0.7, y+radius*0.7, fill="black", width=1)
        self.game_canvas.create_line(x-radius*0.7, y+radius*0.7, x+radius*0.7, y-radius*0.7, fill="black", width=1)
        
        return [ball, highlight]
    
    def start_game(self):
        if self.current_bet <= 0:
            messagebox.showwarning("错误", "请先下注")
            return
            
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注")
            return
        
        # 修改点1：在游戏开始时立即扣除下注金额
        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        self.game_state = "showing_balls"
        self.selected_cup = -1
        
        # 重置杯子颜色
        self.cup_colors = ["#2d4059", "#2d4059", "#2d4059"]
        
        # 重置所有杯子的Y位置
        self.cup_y_positions = [400, 400, 400]
        
        # 更新显示
        self.update_display()
        
        # 禁用所有按钮
        self.disable_all_buttons()

        # 随机放置球
        if self.ball_count == 1:
            self.ball_position = [random.randint(0, 2)]
        else:  # 2个球
            self.ball_position = random.sample([0, 1, 2], 2)
        
        # 初始杯子位置
        self.cup_positions = [0, 1, 2]
        
        # 立即绘制初始状态
        self.draw_game()
        self.root.update()
        
        # 升起所有杯子100px（到300px）并显示球
        self.lift_all_cups(300, 1.0, self.start_shuffling)
    
    def disable_all_buttons(self):
        """禁用所有按钮"""
        self.start_button.config(state=tk.DISABLED)
        self.reset_bet_button.config(state=tk.DISABLED)
        for btn in self.chip_buttons:
            btn.configure(state=tk.DISABLED)
        for btn in self.ball_buttons:
            btn.configure(state=tk.DISABLED)
    
    def enable_all_buttons(self):
        """启用所有按钮"""
        self.start_button.config(state=tk.NORMAL)
        self.reset_bet_button.config(state=tk.NORMAL)
        for btn in self.chip_buttons:
            btn.configure(state=tk.NORMAL)
        for btn in self.ball_buttons:
            btn.configure(state=tk.NORMAL)
    
    def lift_all_cups(self, target_y, duration, callback=None):
        """升起所有杯子到指定高度"""
        self.animation_start_time = time.time()
        self.animation_duration = duration
        self.animation_target_y = target_y
        self.animation_callback = callback
        
        # 确保杯子位置正确
        for i in range(3):
            self.cup_y_positions[i] = 400
        
        # 立即绘制初始状态
        self.draw_game()
        self.root.update()
        
        self.animate_lift_all_cups()
    
    def animate_lift_all_cups(self):
        """动画：升起所有杯子"""
        elapsed = time.time() - self.animation_start_time
        progress = min(1.0, elapsed / self.animation_duration)
        
        # 使用缓动函数计算当前高度
        for i in range(3):
            start_y = 400
            distance = start_y - self.animation_target_y
            current_y = start_y - distance * progress
            self.cup_y_positions[i] = current_y
        
        self.draw_game()
        
        if progress < 1.0:
            self.root.after(16, self.animate_lift_all_cups)
        else:
            if self.animation_callback:
                self.root.after(2000, self.animation_callback)  # 等待2秒
    
    def lower_all_cups(self, target_y, duration, callback=None):
        """降下所有杯子到指定高度"""
        self.animation_start_time = time.time()
        self.animation_duration = duration
        self.animation_target_y = target_y
        self.animation_callback = callback
        
        # 确保杯子位置正确
        for i in range(3):
            self.cup_y_positions[i] = 300
        
        # 立即绘制初始状态
        self.draw_game()
        self.root.update()
        
        self.animate_lower_all_cups()
    
    def animate_lower_all_cups(self):
        """动画：降下所有杯子"""
        elapsed = time.time() - self.animation_start_time
        progress = min(1.0, elapsed / self.animation_duration)
        
        # 使用缓动函数计算当前高度
        for i in range(3):
            start_y = self.cup_y_positions[i]
            distance = self.animation_target_y - start_y
            current_y = start_y + distance * progress
            self.cup_y_positions[i] = current_y
        
        self.draw_game()
        
        if progress < 1.0:
            self.root.after(16, self.animate_lower_all_cups)
        else:
            if self.animation_callback:
                self.animation_callback()
    
    def start_shuffling(self):
        """开始洗牌流程"""
        # 降下所有杯子回到400px
        self.lower_all_cups(400, 1.0, self.start_smooth_shuffling)
    
    def start_smooth_shuffling(self):
        """开始平滑的杯子移动动画"""
        self.game_state = "shuffling"
        self.shuffle_start_time = time.time()
        self.shuffle_duration = 10.0  # 10秒总时间
        self.animation_complete = False  # 动画完成标志
        self.last_swap_time = time.time()  # 上次交换时间
        
        # 速度控制参数
        self.current_speed = 12.0  # 初始速度
        
        # 初始位置
        self.cup_targets = {
            0: self.cup_positions[0],
            1: self.cup_positions[1],
            2: self.cup_positions[2]
        }
        
        # 开始动画循环
        self.last_frame_time = time.time()
        self.animate_smooth_shuffling()
    
    def animate_smooth_shuffling(self):
        """平滑的杯子移动动画循环"""
        current_time = time.time()
        elapsed = current_time - self.shuffle_start_time
        
        # 计算帧时间
        frame_time = current_time - self.last_frame_time
        self.last_frame_time = current_time
        
        # 检查是否超过10秒
        if elapsed >= self.shuffle_duration and not self.animation_complete:
            # 设置动画完成标志
            self.animation_complete = True
        
        # 更新速度阶段 - 按照要求调整
        if elapsed < 1.0:  # 0-1秒: 初始速度
            self.current_speed = 12.0
        elif elapsed < 2.75:  # 1-2.75秒: 加速
            progress = (elapsed - 1.0) / 1.75
            self.current_speed = 12.0 + (30.0 - 12.0) * progress
        elif elapsed < 7.75:  # 2.75-7.75秒: 高速
            self.current_speed = 30.0
        elif elapsed < 9.5:  # 7.75-9.5秒: 减速
            progress = (elapsed - 7.75) / 1.75
            self.current_speed = 30.0 - (30.0 - 12.0) * progress
        else:  # 9.5-10秒: 恢复初始速度
            self.current_speed = 12.0
        
        # 随机选择两个杯子交换位置
        if not self.animation_complete and current_time - self.last_swap_time > 0.5 / (self.current_speed / 8.0) and random.random() < 0.5:
            idx1, idx2 = random.sample([0, 1, 2], 2)
            self.cup_targets[idx1], self.cup_targets[idx2] = self.cup_targets[idx2], self.cup_targets[idx1]
            self.last_swap_time = current_time
        
        # 平滑移动所有杯子到目标位置
        all_arrived = True
        for cup_id in [0, 1, 2]:
            current_pos = self.cup_positions[cup_id]
            target_pos = self.cup_targets[cup_id]
            
            # 计算移动方向
            direction = 1 if target_pos > current_pos else -1
            
            # 计算移动速度（使用当前速度）
            distance = abs(target_pos - current_pos)
            move_speed = min(self.current_speed * frame_time, distance) * direction
            
            # 移动杯子
            if abs(target_pos - current_pos) > 0.01:
                self.cup_positions[cup_id] += move_speed
                all_arrived = False
        
        # 添加轻微的上下浮动效果（仅在洗牌过程中）
        if not self.animation_complete:
            for i in range(3):
                self.cup_y_positions[i] = 400 + 10 * math.sin(time.time() * 5 + i * 2)
        
        # 重绘画布
        self.draw_game()
        
        # 检查是否所有杯子都到达目标位置
        if self.animation_complete and all_arrived:
            self.game_state = "waiting_selection"
            # 重置杯子位置（停止浮动）
            for i in range(3):
                self.cup_y_positions[i] = 400
            self.draw_game()
            return
        
        # 继续动画
        self.root.after(10, self.animate_smooth_shuffling)
    
    def select_cup(self, cup_idx):
        if self.game_state != "waiting_selection":
            return
            
        self.selected_cup = cup_idx
        self.game_state = "revealing"
        
        # 将选中的杯子颜色改为浅蓝色
        self.cup_colors[cup_idx] = "#4e9de0"
        
        # 确保杯子位置正确
        self.cup_y_positions[cup_idx] = 400
        self.draw_game()
        self.root.update()
        
        # 开始升起选中的杯子
        self.lift_selected_cup(cup_idx, 300, 1.0, self.show_remaining_cups)
    
    def lift_selected_cup(self, cup_idx, target_y, duration, callback=None):
        """升起选中的杯子"""
        self.selected_cup_idx = cup_idx
        self.animation_start_time = time.time()
        self.animation_duration = duration
        self.animation_target_y = target_y
        self.animation_callback = callback
        
        # 确保杯子位置正确
        self.cup_y_positions[cup_idx] = 400
        self.draw_game()
        self.root.update()
        
        self.animate_lift_selected_cup()
    
    def animate_lift_selected_cup(self):
        """动画：升起选中的杯子"""
        elapsed = time.time() - self.animation_start_time
        progress = min(1.0, elapsed / self.animation_duration)
        
        # 使用缓动函数计算当前高度
        start_y = 400
        distance = start_y - self.animation_target_y
        current_y = start_y - distance * progress
        
        self.cup_y_positions[self.selected_cup_idx] = current_y
        self.draw_game()
        
        if progress < 1.0:
            self.root.after(16, self.animate_lift_selected_cup)
        else:
            if self.animation_callback:
                self.root.after(2000, self.animation_callback)  # 等待2秒
    
    def show_remaining_cups(self):
        """显示剩余的杯子"""
        self.game_state = "showing_all"
        
        # 确保杯子位置正确
        for i in range(3):
            if i != self.selected_cup:
                self.cup_y_positions[i] = 400
        
        self.draw_game()
        self.root.update()
        
        # 修改点2：在杯子完全打开时结算游戏
        self.calculate_win()
        
        self.lift_remaining_cups(300, 1.0, self.reset_game)
    
    def lift_remaining_cups(self, target_y, duration, callback=None):
        """升起剩余的杯子"""
        self.remaining_cups = [i for i in range(3) if i != self.selected_cup]
        self.animation_start_time = time.time()
        self.animation_duration = duration
        self.animation_target_y = target_y
        self.animation_callback = callback
        
        # 确保杯子位置正确
        for i in self.remaining_cups:
            self.cup_y_positions[i] = 400
        
        self.draw_game()
        self.root.update()
        
        self.animate_lift_remaining_cups()
    
    def animate_lift_remaining_cups(self):
        """动画：升起剩余的杯子"""
        elapsed = time.time() - self.animation_start_time
        progress = min(1.0, elapsed / self.animation_duration)
        
        # 使用缓动函数计算当前高度
        for i in self.remaining_cups:
            start_y = 400
            distance = start_y - self.animation_target_y
            current_y = start_y - distance * progress
            self.cup_y_positions[i] = current_y
        
        self.draw_game()
        
        if progress < 1.0:
            self.root.after(16, self.animate_lift_remaining_cups)
        else:
            if self.animation_callback:
                self.root.after(4000, self.animation_callback)  # 等待4秒
    
    def calculate_win(self):
        """在杯子完全打开时结算游戏"""
        win = False
        if self.selected_cup in self.ball_position:
            # 计算赢得的金额
            win_multiplier = self.odds[self.ball_count]
            win_amount = self.bet_amount * win_multiplier
            self.balance += win_amount
            self.last_win = win_amount
            win = True
        else:
            self.last_win = 0.0
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 更新显示
        self.update_display()
    
    def reset_game(self):
        """重置游戏状态"""
        # 确保杯子位置正确
        for i in range(3):
            self.cup_y_positions[i] = 300
        
        # 重置杯子颜色为正常颜色（深蓝色）
        self.cup_colors = ["#2d4059", "#2d4059", "#2d4059"]
        
        self.draw_game()
        self.root.update()
        
        # 降下所有杯子回到400px
        self.lower_all_cups(400, 1.0, self.finish_game)
    
    def finish_game(self):
        """结束游戏并启用按钮"""
        # 重置游戏状态
        self.game_state = "idle"
        
        # 启用所有按钮
        self.enable_all_buttons()
    
    def on_closing(self):
        # 停止任何进行中的动画
        if self.animation_id:
            self.root.after_cancel(self.animation_id)
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()

def main(initial_balance, username):
    root = tk.Tk()
    game = ThimblesGame(root, initial_balance, username)
    root.mainloop()
    return game.balance

if __name__ == "__main__":
    root = tk.Tk()
    game = ThimblesGame(root, 1000.0, "test_user")
    root.mainloop()