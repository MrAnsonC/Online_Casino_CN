import tkinter as tk
from tkinter import ttk, messagebox
import random
import json
import os
import time
import math
from PIL import Image, ImageTk, ImageDraw

def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')

def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_user_data():
    file_path = get_data_file_path()
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)
    
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
        
        self.create_oval(0, 0, radius*2, radius*2, fill=bg_color, outline="#16213e", width=2)
        self.create_text(radius, radius, text=text, fill=fg_color, 
                        font=("Arial", 18, "bold"))
        
        self.bind("<Button-1>", self.on_click)
    
    def on_click(self, event):
        if self.command:
            self.command()

class GoalkeeperGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("守门员游戏")
        self.root.geometry("1000x700+50+10")
        self.root.configure(bg="#1a1a2e")
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0
        self.current_bet = 0.0
        self.last_win = 0.0
        self.game_active = False
        self.role = None  # 'goalkeeper' or 'player'
        
        # 赔率表 - 根据数学期望优化过
        self.odds = {
            'goalkeeper': {
                'post': 1.5,   # 撞柱赔率 1.5:1
                'miss': 1.1,    # Miss赔率 1.1:1
            },
            'player': {
                'goal': 1.8,    # 进球赔率 1.8:1
                'critical_post': 8.0  # 暴击撞柱赔率 8:1
            }
        }
        
        self.create_widgets()
        self.update_display()
    
    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 初始化位置矩形和标签列表
        self.position_rects = []
        self.position_labels = []
        
        # 左侧 - 足球龙门显示
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(left_frame, text="足球龙门游戏", font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#e94560").pack(pady=10)
        
        self.game_canvas = tk.Canvas(left_frame, bg="#0f3460", bd=0, highlightthickness=0)
        self.game_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 修复：先初始化骰子标签列表
        self.dice_labels = []
        # 守门员左骰子
        lbl_gk_left = tk.Label(self.game_canvas, bg='#0f3460', borderwidth=0)
        self.dice_labels.append(lbl_gk_left)
        
        # 守门员右骰子
        lbl_gk_right = tk.Label(self.game_canvas, bg='#0f3460', borderwidth=0)
        self.dice_labels.append(lbl_gk_right)
        
        # 球员骰子
        lbl_player = tk.Label(self.game_canvas, bg='#0f3460', borderwidth=0)
        self.dice_labels.append(lbl_player)
        
        # 绘制足球龙门框架 (现在dice_labels已初始化)
        self.draw_goal_frame()
        
        # 结果标签
        self.result_var = tk.StringVar()
        self.result_var.set("选择角色和下注金额后开始游戏")
        self.result_label = tk.Label(self.game_canvas, textvariable=self.result_var, 
                                   font=("Arial", 16, "bold"), fg="white", bg="#0f3460")
        self.result_label.place(relx=0.5, rely=0.95, anchor=tk.CENTER)
        
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
        
        # 角色选择
        role_frame = tk.Frame(right_frame, bg="#16213e")
        role_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(role_frame, text="选择角色:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.role_var = tk.StringVar()
        self.role_var.set(None)
        
        goalkeeper_btn = tk.Radiobutton(
            role_frame, text="守门员", font=("Arial", 12),
            variable=self.role_var, value="goalkeeper", 
            bg="#16213e", fg="white", selectcolor="#1a1a2e",
            command=lambda: self.set_role("goalkeeper")
        )
        goalkeeper_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        player_btn = tk.Radiobutton(
            role_frame, text="球员", font=("Arial", 12),
            variable=self.role_var, value="player", 
            bg="#16213e", fg="white", selectcolor="#1a1a2e",
            command=lambda: self.set_role("player")
        )
        player_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
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
            "1. 选择角色: 守门员或球员",
            "2. 选择下注金额",
            "3. 点击开始游戏按钮",
            "4. 系统自动摇骰子",
            "5. 根据结果计算奖金:",
            "   - 守门员: 撞柱(1.5:1), Miss(1.1:1)",
            "   - 球员: Goal!(1.8:1), 暴击撞柱(8:1)",
            "6. 其他情况: 没有奖金"
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
        
        # 初始化骰子图片
        self.dice_images = []
        for i in range(1, 7):
            img = Image.new('RGB', (80, 80), '#e8d6b3')
            self.draw_dice(img, i)
            self.dice_images.append(ImageTk.PhotoImage(img))
        
        # 初始化足球图片
        self.football_img = self.create_football_image()
    
    def draw_goal_frame(self):
        # 清除画布
        self.game_canvas.delete("all")
        
        # 设置龙门参数
        self.goal_width = 500
        self.goal_height = 300
        self.goal_x = (800 - self.goal_width) // 2
        self.goal_y = 50
        post_width = 10
        
        # 保存门柱位置坐标
        self.left_post_x = self.goal_x
        self.right_post_x = self.goal_x + self.goal_width - post_width
        self.goal_top_y = self.goal_y
        
        # 绘制龙门框架
        self.game_canvas.create_rectangle(self.goal_x, self.goal_y, self.goal_x + self.goal_width, self.goal_y + self.goal_height, 
                                         outline="#FFFFFF", width=3, fill="#0f3460")
        
        # 绘制球网
        net_spacing = 20
        for i in range(0, self.goal_width, net_spacing):
            self.game_canvas.create_line(self.goal_x + i, self.goal_y, self.goal_x + i, self.goal_y + self.goal_height, 
                                       fill="#AAAAAA", dash=(2, 2))
        for i in range(0, self.goal_height, net_spacing):
            self.game_canvas.create_line(self.goal_x, self.goal_y + i, self.goal_x + self.goal_width, self.goal_y + i, 
                                       fill="#AAAAAA", dash=(2, 2))
        
        # 绘制门柱
        post_width = 10
        self.game_canvas.create_rectangle(self.goal_x, self.goal_y, self.goal_x + post_width, self.goal_y + self.goal_height, 
                                         fill="#CCCCCC", outline="#FFFFFF")
        self.game_canvas.create_rectangle(self.goal_x + self.goal_width - post_width, self.goal_y, 
                                         self.goal_x + self.goal_width, self.goal_y + self.goal_height, 
                                         fill="#CCCCCC", outline="#FFFFFF")
        self.game_canvas.create_rectangle(self.goal_x, self.goal_y, self.goal_x + self.goal_width, self.goal_y + post_width, 
                                         fill="#CCCCCC", outline="#FFFFFF")
        
        # 绘制6个位置
        position_width = self.goal_width // 6
        for i in range(6):
            x1 = self.goal_x + i * position_width
            x2 = x1 + position_width
            y1 = self.goal_y + self.goal_height
            y2 = y1 + 30
            
            # 位置矩形
            rect = self.game_canvas.create_rectangle(x1, y1, x2, y2, 
                                                   outline="#FFFFFF", fill="#2d4059", width=2)
            self.position_rects.append(rect)
            
            # 位置标签
            label = self.game_canvas.create_text((x1 + x2) // 2, (y1 + y2) // 2, 
                                               text=str(i+1), font=("Arial", 12, "bold"), 
                                               fill="#FFFFFF")
            self.position_labels.append(label)
        
        # 更新骰子位置
        self.update_dice_positions()
    
    def update_dice_positions(self):
        if hasattr(self, 'goal_top_y') and hasattr(self, 'left_post_x') and hasattr(self, 'right_post_x'):
            # 守门员左骰子位置：左门柱上方
            self.dice_labels[0].place(x=self.left_post_x - 40, y=self.goal_top_y - 40, anchor=tk.CENTER)
            # 守门员右骰子位置：右门柱上方
            self.dice_labels[1].place(x=self.right_post_x + 40, y=self.goal_top_y - 40, anchor=tk.CENTER)
            # 球员骰子位置：球门中间下方（距离球门底部一定距离）
            center_x = (self.left_post_x + self.right_post_x) // 2
            bottom_y = self.goal_top_y + self.goal_height + 60
            self.dice_labels[2].place(x=center_x, y=bottom_y, anchor=tk.CENTER)
    
    def highlight_goal_range(self, start, end):
        # 清除之前的高亮
        for rect in self.position_rects:
            self.game_canvas.itemconfig(rect, fill="#2d4059")
        
        # 高亮选中的范围
        for i in range(start-1, end):
            if 0 <= i < len(self.position_rects):
                self.game_canvas.itemconfig(self.position_rects[i], fill="#27ae60")
    
    def create_football_image(self):
        img = Image.new('RGBA', (40, 40), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 绘制足球
        draw.ellipse((0, 0, 39, 39), fill="#FFFFFF", outline="#000000", width=2)
        
        # 绘制足球花纹
        draw.line((10, 20, 30, 20), fill="#000000", width=2)
        draw.line((20, 10, 20, 30), fill="#000000", width=2)
        draw.ellipse((15, 15, 25, 25), fill="#000000")
        
        return ImageTk.PhotoImage(img)
    
    def draw_dice(self, img, num):
        draw = ImageDraw.Draw(img)
        size = img.size[0]
        dot_size = max(2, size // 10)
        draw.rectangle([0, 0, size-1, size-1], outline='#333', width=1)
        dot_color = '#333'
        dot_positions = {
            1: [(size//2, size//2)],
            2: [(size//4, size//4), (3*size//4, 3*size//4)],
            3: [(size//4, size//4), (size//2, size//2), (3*size//4, 3*size//4)],
            4: [(size//4, size//4), (3*size//4, size//4), (size//4, 3*size//4), (3*size//4, 3*size//4)],
            5: [(size//4, size//4), (3*size//4, size//4), (size//2, size//2), (size//4, 3*size//4), (3*size//4, 3*size//4)],
            6: [(size//4, size//4), (3*size//4, size//4), (size//4, size//2), (3*size//4, size//2), (size//4, 3*size//4), (3*size//4, 3*size//4)]
        }
        for pos in dot_positions[num]:
            draw.ellipse([pos[0]-dot_size, pos[1]-dot_size, pos[0]+dot_size, pos[1]+dot_size], fill=dot_color)
    
    def set_role(self, role):
        self.role = role
        self.result_var.set(f"已选择: {'守门员' if role == 'goalkeeper' else '球员'}")
    
    def add_chip(self, amount):
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
    
    def update_display(self):
        self.balance_var.set(f"${self.balance:.2f}")
        self.last_win_var.set(f"${self.last_win:.2f}")
    
    def start_game(self):
        if self.role is None:
            messagebox.showwarning("错误", "请先选择角色")
            return
        if self.current_bet <= 0:
            messagebox.showwarning("错误", "请先下注")
            return
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注")
            return
        
        # 禁用按钮
        self.start_button.config(state=tk.DISABLED)
        self.reset_bet_button.config(state=tk.DISABLED)
        for btn in self.chip_buttons:
            btn.configure(state=tk.DISABLED)
        
        # 保存下注金额
        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        self.update_display()
        
        # 生成骰子结果
        self.gk_dice = [random.randint(1, 6), random.randint(1, 6)]
        self.gk_dice.sort()  # 排序，小的在前
        
        self.player_dice = [random.randint(1, 6)]
        
        # 显示骰子
        for lbl in self.dice_labels:
            lbl.place()  # 确保骰子显示
        
        # 开始骰子动画
        self.animate_dice(0, phase=1)
    
    def animate_dice(self, frame, phase):
        # 第一阶段：守门员骰子动画
        if phase == 1:
            for i in range(2):
                dice_img = random.randint(0, 5)
                self.dice_labels[i].config(image=self.dice_images[dice_img])
                self.dice_labels[i].image = self.dice_images[dice_img]
            
            # 隐藏球员骰子
            self.dice_labels[2].config(image='')
            
            if frame < 10:  # 动画持续10帧
                self.root.after(100, lambda: self.animate_dice(frame + 1, phase))
            else:
                # 显示守门员骰子结果
                self.dice_labels[0].config(image=self.dice_images[self.gk_dice[0] - 1])
                self.dice_labels[0].image = self.dice_images[self.gk_dice[0] - 1]
                self.dice_labels[1].config(image=self.dice_images[self.gk_dice[1] - 1])
                self.dice_labels[1].image = self.dice_images[self.gk_dice[1] - 1]
                
                # 高亮龙门范围
                self.highlight_goal_range(self.gk_dice[0], self.gk_dice[1])
                self.result_var.set(f"守门员防守范围: {self.gk_dice[0]}到{self.gk_dice[1]}")
                
                # 2秒后进入第二阶段
                self.root.after(2000, lambda: self.animate_dice(0, phase=2))
        
        # 第二阶段：球员骰子动画
        elif phase == 2:
            # 显示球员骰子
            dice_img = random.randint(0, 5)
            self.dice_labels[2].config(image=self.dice_images[dice_img])
            self.dice_labels[2].image = self.dice_images[dice_img]
            
            if frame < 8:  # 动画持续8帧
                self.root.after(100, lambda: self.animate_dice(frame + 1, phase))
            else:
                # 显示最终骰子结果
                self.dice_labels[2].config(image=self.dice_images[self.player_dice[0] - 1])
                self.dice_labels[2].image = self.dice_images[self.player_dice[0] - 1]
                
                # 开始发射足球动画
                self.animate_football()
    
    def animate_football(self):
        # 移除之前的足球
        if hasattr(self, 'football_item'):
            self.game_canvas.delete(self.football_item)
        
        # 获取球员骰子位置（起点）
        x0 = self.dice_labels[2].winfo_x()
        y0 = self.dice_labels[2].winfo_y()
        width = self.dice_labels[2].winfo_width()
        height = self.dice_labels[2].winfo_height()
        start_x = x0 + width // 2
        start_y = y0 + height // 2
        
        # 计算足球在球门中的位置（终点）
        goal_x = self.goal_x
        goal_width = self.goal_width
        position_width = goal_width // 6
        # 球员骰子点数对应的位置
        pos = self.player_dice[0]
        # 目标位置的x坐标：球门左边开始，第pos个位置的中间
        target_x = goal_x + (pos - 0.5) * position_width
        target_y = self.goal_y + self.goal_height // 2  # 球门中间高度
        
        # 在起点创建足球
        self.football_item = self.game_canvas.create_image(start_x, start_y, image=self.football_img)
        
        # 计算移动的步长
        steps = 30
        dx = (target_x - start_x) / steps
        dy = (target_y - start_y) / steps
        
        # 开始动画
        self.animate_football_step(0, steps, dx, dy, target_x, target_y)

    def animate_football_step(self, step, total_steps, dx, dy, target_x, target_y):
        if step < total_steps:
            self.game_canvas.move(self.football_item, dx, dy)
            self.root.after(20, lambda: self.animate_football_step(step+1, total_steps, dx, dy, target_x, target_y))
        else:
            # 确保足球在目标位置
            self.game_canvas.coords(self.football_item, target_x, target_y)
            # 动画结束后判断结果
            self.determine_result()
    
    def determine_result(self):
        gk1, gk2 = self.gk_dice
        player_dice = self.player_dice[0]
        
        result_text = ""
        win_amount = 0.0
        
        if self.role == 'goalkeeper':
            # 守门员角色
            if gk1 == gk2 == player_dice:
                # 暴击撞柱 - 守门员输
                result_text = "暴击撞柱! (输)"
                win_amount = 0
            elif player_dice == gk1 or player_dice == gk2:
                # 撞柱
                result_text = f"撞柱! 赢 {self.odds['goalkeeper']['post']:.2f}倍"
                win_amount = self.bet_amount * self.odds['goalkeeper']['post']
            elif gk1 < player_dice < gk2:
                # Goal - 守门员输
                result_text = "Goal! (输)"
                win_amount = 0
            else:
                # Miss
                result_text = f"Miss! 赢 {self.odds['goalkeeper']['miss']:.1f}倍"
                win_amount = self.bet_amount * self.odds['goalkeeper']['miss']
        else:
            # 球员角色
            if gk1 == gk2 == player_dice:
                # 暴击撞柱
                result_text = f"暴击撞柱! 赢 {self.odds['player']['critical_post']:.0f}倍"
                win_amount = self.bet_amount * self.odds['player']['critical_post']
            elif gk1 < player_dice < gk2:
                # Goal
                result_text = f"Goal! 赢 {self.odds['player']['goal']:.1f}倍"
                win_amount = self.bet_amount * self.odds['player']['goal']
            elif player_dice == gk1 or player_dice == gk2:
                # 撞柱 - 球员输
                result_text = "撞柱! (输)"
                win_amount = 0
            else:
                # Miss - 球员输
                result_text = "Miss! (输)"
                win_amount = 0
        
        # 更新余额
        self.balance += win_amount
        self.last_win = win_amount
        self.update_display()
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 显示结果
        self.result_var.set(result_text)
        
        # 重新启用按钮
        self.start_button.config(state=tk.NORMAL)
        self.reset_bet_button.config(state=tk.NORMAL)
        for btn in self.chip_buttons:
            btn.configure(state=tk.NORMAL)
        
        # 延迟2秒后隐藏骰子
        self.root.after(2000, self.hide_dice)
    
    def hide_dice(self):
        for lbl in self.dice_labels:
            lbl.place_forget()  # 隐藏标签
    
    def on_closing(self):
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()

def main(initial_balance, username):
    root = tk.Tk()
    game = GoalkeeperGame(root, initial_balance, username)
    root.mainloop()
    return game.balance

if __name__ == "__main__":
    root = tk.Tk()
    game = GoalkeeperGame(root, 1000.0, "test_user")
    root.mainloop()