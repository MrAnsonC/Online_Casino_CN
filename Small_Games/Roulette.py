import tkinter as tk
from tkinter import ttk, messagebox
import random
import math
import os
import json
from PIL import Image, ImageTk, ImageDraw, ImageFont
import winsound  # 用于添加音效

# 轮盘赌游戏逻辑 - 支持标准下注类型
class RouletteGame:
    def __init__(self):
        self.reset_game()
        
    def reset_game(self):
        self.bets = {}  # 存储所有下注: {位置: (金额, 下注类型)}
        self.total_bet = 0
        self.winning_number = None
        self.win_amount = 0
        self.winning_bets = []
        
    def place_bet(self, bet_type, amount, position=None):
        """下注到指定位置"""
        key = position if position else bet_type
        
        if key not in self.bets:
            self.bets[key] = (0, bet_type)
        current_amount, _ = self.bets[key]
        self.bets[key] = (current_amount + amount, bet_type)
        self.total_bet += amount
        
    def spin(self):
        """旋转轮盘并确定获胜号码"""
        self.winning_number = random.randint(0, 36)
        self.winning_bets = []
        self.win_amount = 0
        
        # 确定哪些下注获胜
        for key, (amount, bet_type) in self.bets.items():
            if self.is_winning_bet(bet_type, key, self.winning_number):
                odds = self.get_odds(bet_type)
                self.win_amount += amount * (odds + 1)
                self.winning_bets.append((key, bet_type, amount, odds))
        
        return self.winning_number, self.win_amount, self.winning_bets
    
    def is_winning_bet(self, bet_type, key, number):
        """检查下注是否获胜"""
        # 单个数字
        if bet_type == "straight":
            return int(key) == number
        
        # First Five (0, 00, 1, 2, 3)
        elif bet_type == "first_five":
            return number in [0, 37, 1, 2, 3]  # 37代表00
        
        # Split (两个相邻数字)
        elif bet_type == "split":
            num1, num2 = map(int, key.split(','))
            return number in [num1, num2]
        
        # Street (一行三个数字)
        elif bet_type == "street":
            start_num = int(key)
            return start_num <= number <= start_num + 2
        
        # Corner (四个数字)
        elif bet_type == "corner":
            nums = list(map(int, key.split(',')))
            return number in nums
        
        # Six-line (两行六个数字)
        elif bet_type == "six_line":
            start_num = int(key)
            return start_num <= number <= start_num + 5
        
        # Even Chance (红/黑, 单/双, 1-18/19-36)
        elif bet_type == "even_chance":
            if key == "red":
                return number in self.red_numbers
            elif key == "black":
                return number in self.black_numbers
            elif key == "odd":
                return number % 2 == 1 and number != 0 and number != 37
            elif key == "even":
                return number % 2 == 0 and number != 0 and number != 37
            elif key == "1-18":
                return 1 <= number <= 18
            elif key == "19-36":
                return 19 <= number <= 36
        
        # Dozen (1-12, 13-24, 25-36)
        elif bet_type == "dozen":
            if key == "1st_12":
                return 1 <= number <= 12
            elif key == "2nd_12":
                return 13 <= number <= 24
            elif key == "3rd_12":
                return 25 <= number <= 36
        
        # Column (列下注)
        elif bet_type == "column":
            if key == "1st_col":
                return number % 3 == 1 and number != 0 and number != 37
            elif key == "2nd_col":
                return number % 3 == 2 and number != 0 and number != 37
            elif key == "3rd_col":
                return number % 3 == 0 and number != 0 and number != 37
        
        return False
    
    def get_odds(self, bet_type):
        """获取不同下注类型的赔率"""
        odds_map = {
            "straight": 35,     # 35:1
            "first_five": 6,    # 6:1
            "split": 17,        # 17:1
            "street": 11,        # 11:1
            "corner": 8,         # 8:1
            "six_line": 5,       # 5:1
            "even_chance": 1,   # 1:1
            "dozen": 2,         # 2:1
            "column": 2          # 2:1
        }
        return odds_map.get(bet_type, 1)
    
    # 轮盘数字颜色定义 (美式轮盘)
    red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
    black_numbers = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]

class RouletteGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("Casino Roulette")
        self.geometry("1200x800+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')  # 赌场绿色背景
        
        self.username = username
        self.balance = initial_balance
        self.game = RouletteGame()
        self.selected_chip = 5  # 默认选择5元筹码
        self.selected_bet_type = "straight"  # 默认下注类型
        self.chip_buttons = []  # 筹码按钮列表
        self.bet_type_buttons = []  # 下注类型按钮列表
        self.last_win = 0
        self.bet_labels = {}  # 存储下注标签
        self.bet_markers = []  # 存储下注标记
        
        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        # 保存余额（如果是登录用户）
        if self.username != 'Guest':
            self.update_balance_in_json()
        self.destroy()
        
    def update_balance_in_json(self):
        # 加载用户数据
        users = []
        try:
            with open('saving_data.json', 'r') as f:
                users = json.load(f)
        except:
            pass
        
        # 更新当前用户余额
        for user in users:
            if user['user_name'] == self.username:
                user['cash'] = f"{self.balance:.2f}"
                break
                
        # 保存用户数据
        with open('saving_data.json', 'w') as f:
            json.dump(users, f, indent=4)

    def _load_assets(self):
        # 创建筹码图像
        self.chip_images = {}
        chip_values = [5, 10, 25, 50, 100, 500]
        chip_colors = ['#FF0000', '#FFA500', '#00FF00', '#FFFFFF', '#0000FF', '#FF00FF']
        
        for value, color in zip(chip_values, chip_colors):
            # 创建圆形筹码图像
            img = Image.new('RGBA', (60, 60), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # 绘制筹码主体
            draw.ellipse((5, 5, 55, 55), fill=color)
            
            # 绘制白色边框
            draw.ellipse((0, 0, 59, 59), outline='white', width=3)
            
            # 添加筹码值文本
            try:
                font = ImageFont.truetype("arial.ttf", 16)
            except:
                font = ImageFont.load_default()
                
            text = f"${value}"
            # 使用 textbbox 替代已弃用的 textsize
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            draw.text((30 - w/2, 30 - h/2), text, fill='white' if color in ['#0000FF', '#000000'] else 'black', font=font)
            
            self.chip_images[value] = ImageTk.PhotoImage(img)
        
        # 创建轮盘图像
        self.wheel_image = self.create_roulette_wheel()
        
        # 小球图像
        self.ball_image = self.create_ball_image()
        
        # 创建下注标记图像
        self.bet_marker_img = self.create_bet_marker()

    def create_roulette_wheel(self):
        """创建轮盘图像"""
        size = 300
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 绘制轮盘外圈
        draw.ellipse((10, 10, size-10, size-10), fill='#2a4a3c', outline='#FFD700', width=3)
        
        # 绘制内圈
        draw.ellipse((40, 40, size-40, size-40), fill='#1e1e1e', outline='#FFD700', width=2)
        
        # 绘制数字槽
        num_slots = 38  # 0, 00, 1-36
        slot_width = 360 / num_slots
        
        for i in range(num_slots):
            angle = i * slot_width - 90  # 从顶部开始
            
            # 计算槽位位置
            start_angle = angle
            end_angle = angle + slot_width
            
            # 槽位颜色 (红、黑、绿)
            if i == 0:  # 0
                color = '#008000'  # 绿色
            elif i == 1:  # 00
                color = '#008000'  # 绿色
            else:
                num = i - 1  # 实际数字
                color = '#FF0000' if num in self.game.red_numbers else '#000000'
            
            # 绘制槽位
            draw.pieslice((20, 20, size-20, size-20), start_angle, end_angle, fill=color, outline='#FFD700')
            
            # 添加数字
            num_text = "0" if i == 0 else "00" if i == 1 else str(num)
            rad = math.radians(angle + slot_width/2)
            text_x = size/2 + (size/2 - 40) * math.cos(rad)
            text_y = size/2 + (size/2 - 40) * math.sin(rad)
            
            try:
                font = ImageFont.truetype("arial.ttf", 12)
            except:
                font = ImageFont.load_default()
                
            # 使用 textbbox 替代已弃用的 textsize
            bbox = draw.textbbox((0, 0), num_text, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            draw.text((text_x - w/2, text_y - h/2), num_text, 
                     fill='white' if color == '#000000' else 'black', 
                     font=font)
        
        return ImageTk.PhotoImage(img)
    
    def create_ball_image(self):
        """创建小球图像"""
        img = Image.new('RGBA', (20, 20), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 绘制小球
        draw.ellipse((0, 0, 19, 19), fill='#FFFFFF')
        draw.ellipse((5, 5, 14, 14), fill='#FF0000')
        
        # 添加高光
        draw.ellipse((3, 3, 8, 8), fill='#FFFFFF')
        
        return ImageTk.PhotoImage(img)
    
    def create_bet_marker(self):
        """创建下注标记图像"""
        img = Image.new('RGBA', (30, 30), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 绘制透明圆形标记
        draw.ellipse((0, 0, 29, 29), fill=(255, 255, 0, 150))  # 半透明黄色
        
        return ImageTk.PhotoImage(img)

    def _create_widgets(self):
        # 主框架 - 上下布局
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 顶部轮盘区域
        wheel_frame = tk.Frame(main_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        wheel_frame.pack(fill=tk.X, pady=5)
        
        wheel_label = tk.Label(wheel_frame, text="轮盘", font=('Arial', 16), bg='#2a4a3c', fg='#FFD700')
        wheel_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        
        self.wheel_canvas = tk.Canvas(wheel_frame, width=310, height=310, bg='#2a4a3c', highlightthickness=0)
        self.wheel_canvas.pack(padx=10, pady=10)
        self.wheel_canvas.create_image(155, 155, image=self.wheel_image)
        
        # 小球位置（初始在顶部）
        self.ball_id = self.wheel_canvas.create_image(155, 25, image=self.ball_image)
        
        # 下注区域
        betting_frame = tk.Frame(main_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        betting_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        betting_label = tk.Label(betting_frame, text="下注区域", font=('Arial', 16), bg='#2a4a3c', fg='#FFD700')
        betting_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        
        # 创建下注表格
        self.create_betting_table(betting_frame)
        
        # 右侧控制面板
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=300)
        control_frame.pack(fill=tk.Y, side=tk.RIGHT, padx=5)
        
        # 顶部信息栏
        info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=5)
        
        self.balance_label = tk.Label(
            info_frame, 
            text=f"余额: ${self.balance:.2f}",
            font=('Arial', 18),
            bg='#2a4a3c',
            fg='white'
        )
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        # 下注类型选择
        bet_type_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_type_frame.pack(fill=tk.X, pady=5)
        
        bet_type_label = tk.Label(bet_type_frame, text="下注类型:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        bet_type_label.pack(anchor='w', padx=10, pady=5)
        
        # 下注类型按钮
        bet_types = [
            ("直注(35:1)", "straight"),
            ("分注(17:1)", "split"),
            ("街注(11:1)", "street"),
            ("角注(8:1)", "corner"),
            ("线注(5:1)", "six_line"),
            ("首五注(6:1)", "first_five"),
            ("均注(1:1)", "even_chance"),
            ("打注(2:1)", "dozen"),
            ("列注(2:1)", "column")
        ]
        
        self.bet_type_buttons = []
        for text, b_type in bet_types:
            # 创建按钮时存储下注类型
            btn = tk.Button(
                bet_type_frame,
                text=text,
                font=('Arial', 10),
                bg='#4A4A4A',
                fg='white',
                relief='flat'
            )
            # 添加下注类型作为按钮属性
            btn.bet_type = b_type
            btn.config(command=lambda bt=b_type: self.select_bet_type(bt))
            btn.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)
            self.bet_type_buttons.append(btn)
        
        # 默认选中直注
        self.select_bet_type("straight")
        
        # 筹码区域
        chips_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        chips_frame.pack(fill=tk.X, pady=5)
        
        chips_label = tk.Label(chips_frame, text="筹码:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        chips_label.pack(anchor='w', padx=10, pady=5)
        
        # 单行放置6个筹码
        chip_row = tk.Frame(chips_frame, bg='#2a4a3c')
        chip_row.pack(fill=tk.X, pady=5, padx=5)
        
        chip_values = [5, 10, 25, 50, 100, 500]
        
        self.chip_buttons = []
        for value in chip_values:
            btn = tk.Button(
                chip_row, 
                image=self.chip_images[value],
                command=lambda v=value: self.select_chip(v),
                bg='#2a4a3c',
                relief='flat',
                borderwidth=0
            )
            btn.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(btn)
        
        # 默认选中$5筹码
        self.select_chip(5)
        
        # 下注信息区域
        bet_info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_info_frame.pack(fill=tk.X, pady=5)
        
        self.current_bet_label = tk.Label(
            bet_info_frame, 
            text="本局下注: $0.00",
            font=('Arial', 14),
            bg='#2a4a3c',
            fg='white'
        )
        self.current_bet_label.pack(pady=5, padx=10, anchor='w')
        
        self.last_win_label = tk.Label(
            bet_info_frame, 
            text="上局获胜: $0.00",
            font=('Arial', 14),
            bg='#2a4a3c',
            fg='#FFD700'
        )
        self.last_win_label.pack(pady=5, padx=10, anchor='w')
        
        # 游戏操作按钮
        action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        action_frame.pack(fill=tk.X, pady=5)
        
        spin_btn = tk.Button(
            action_frame, 
            text="旋转轮盘",
            command=self.spin_roulette,
            font=('Arial', 16, 'bold'),
            bg='#4CAF50',
            fg='white',
            padx=10,
            pady=10
        )
        spin_btn.pack(fill=tk.X, pady=5)
        
        clear_btn = tk.Button(
            action_frame, 
            text="清除下注",
            command=self.clear_bets,
            font=('Arial', 14),
            bg='#F44336',
            fg='white'
        )
        clear_btn.pack(fill=tk.X, pady=5)
        
        # 状态信息
        self.status_label = tk.Label(
            control_frame, 
            text="请选择筹码和下注类型，然后点击下注区域",
            font=('Arial', 12, 'bold'),
            bg='#2a4a3c',
            fg='#FFD700'
        )
        self.status_label.pack(pady=10, fill=tk.X)
        
        # 获胜信息
        self.win_info_label = tk.Label(
            control_frame, 
            text="",
            font=('Arial', 12),
            bg='#2a4a3c',
            fg='white',
            wraplength=280
        )
        self.win_info_label.pack(pady=5, fill=tk.X)

    def create_betting_table(self, parent):
        """创建经典轮盘赌桌布局"""
        # 主框架
        table_frame = tk.Frame(parent, bg='#2a4a3c')
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 顶部 - 0和00
        top_frame = tk.Frame(table_frame, bg='#2a4a3c')
        top_frame.pack(fill=tk.X, pady=(0, 5))
        
        # 0
        self.create_bet_button(top_frame, "0", 0, 0, "green", bet_type="straight")
        # 00
        self.create_bet_button(top_frame, "00", 0, 1, "green", bet_type="straight")
        
        # 第一行数字 (1, 2, 3) - 添加分注线
        row1_frame = tk.Frame(table_frame, bg='#2a4a3c')
        row1_frame.pack(fill=tk.X, pady=(0, 5))
        
        # 添加分注线 (0-1, 0-2, 00-2, 00-3, 1-2, 2-3)
        self.create_split_button(row1_frame, "0,1", 0, 0, "split")
        self.create_split_button(row1_frame, "0,2", 0, 1, "split")
        self.create_split_button(row1_frame, "00,2", 0, 2, "split")
        self.create_split_button(row1_frame, "00,3", 0, 3, "split")
        self.create_split_button(row1_frame, "1,2", 0, 4, "split")
        self.create_split_button(row1_frame, "2,3", 0, 5, "split")
        
        # 数字1,2,3
        self.create_bet_button(row1_frame, "1", 0, 6, "red", bet_type="straight")
        self.create_bet_button(row1_frame, "2", 0, 7, "black", bet_type="straight")
        self.create_bet_button(row1_frame, "3", 0, 8, "red", bet_type="straight")
        
        # 添加角注点 (0,1,2,3)
        self.create_corner_button(row1_frame, "0,1,2,3", 0, 9, "corner")
        
        # 数字表格 (3列x12行)
        num_frame = tk.Frame(table_frame, bg='#2a4a3c')
        num_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建数字按钮和分注线
        for row in range(12):
            row_frame = tk.Frame(num_frame, bg='#2a4a3c')
            row_frame.pack(fill=tk.X, pady=2)
            
            # 分注线 (垂直)
            for col in range(3):
                num = 3 * row + col + 1
                color = "red" if num in self.game.red_numbers else "black"
                
                # 添加分注线 (水平)
                if row > 0:
                    num_above = num - 3
                    self.create_split_button(row_frame, f"{num_above},{num}", 0, col*2, "split")
                
                # 添加分注线 (垂直)
                if col < 2:
                    next_num = num + 1
                    self.create_split_button(row_frame, f"{num},{next_num}", 0, col*2+1, "split")
                
                # 添加角注点
                if col < 2 and row < 11:
                    corner_nums = [num, num+1, num+3, num+4]
                    self.create_corner_button(row_frame, ",".join(map(str, corner_nums)), 0, col*2+1, "corner")
                
                # 添加数字
                self.create_bet_button(row_frame, str(num), 0, col*2, color, bet_type="straight")
        
        # 底部 - 外部下注区域
        bottom_frame = tk.Frame(table_frame, bg='#2a4a3c')
        bottom_frame.pack(fill=tk.X, pady=(5, 0))
        
        # 第一打 (1-12)
        self.create_bet_button(bottom_frame, "1st_12", 0, 0, "blue", columnspan=4, bet_type="dozen")
        # 第二打 (13-24)
        self.create_bet_button(bottom_frame, "2nd_12", 0, 1, "blue", columnspan=4, bet_type="dozen")
        # 第三打 (25-36)
        self.create_bet_button(bottom_frame, "3rd_12", 0, 2, "blue", columnspan=4, bet_type="dozen")
        
        # 空位
        tk.Frame(bottom_frame, width=10, bg='#2a4a3c').grid(row=0, column=3)
        
        # 1-18
        self.create_bet_button(bottom_frame, "1-18", 0, 4, "blue", bet_type="even_chance")
        # 红
        self.create_bet_button(bottom_frame, "red", 0, 5, "red", bet_type="even_chance")
        # 黑
        self.create_bet_button(bottom_frame, "black", 0, 6, "black", bet_type="even_chance")
        # 奇
        self.create_bet_button(bottom_frame, "odd", 0, 7, "blue", bet_type="even_chance")
        # 偶
        self.create_bet_button(bottom_frame, "even", 0, 8, "blue", bet_type="even_chance")
        # 19-36
        self.create_bet_button(bottom_frame, "19-36", 0, 9, "blue", bet_type="even_chance")
        
        # 第二行 - 列下注
        bottom_frame2 = tk.Frame(table_frame, bg='#2a4a3c')
        bottom_frame2.pack(fill=tk.X, pady=(5, 0))
        
        # 第一列
        self.create_bet_button(bottom_frame2, "1st_col", 0, 0, "blue", columnspan=4, bet_type="column")
        # 第二列
        self.create_bet_button(bottom_frame2, "2nd_col", 0, 1, "blue", columnspan=4, bet_type="column")
        # 第三列
        self.create_bet_button(bottom_frame2, "3rd_col", 0, 2, "blue", columnspan=4, bet_type="column")
        
        # First Five
        self.create_bet_button(bottom_frame2, "First Five", 0, 3, "green", columnspan=4, bet_type="first_five")

    def create_bet_button(self, parent, text, row, column, color, rowspan=1, columnspan=1, bet_type=None):
        """创建下注按钮"""
        if bet_type is None:
            bet_type = self.selected_bet_type
            
        bg_color = {
            "red": "#FF6B6B",
            "black": "#4A4A4A",
            "green": "#4CAF50",
            "blue": "#2196F3"
        }.get(color, "#2196F3")
        
        btn = tk.Button(
            parent,
            text=text,
            font=('Arial', 10, 'bold'),
            bg=bg_color,
            fg='white',
            relief='flat',
            command=lambda: self.place_bet(bet_type, text)
        )
        btn.grid(
            row=row, 
            column=column, 
            padx=2, 
            pady=2, 
            sticky='nsew',
            rowspan=rowspan,
            columnspan=columnspan
        )
        
        # 配置行列权重
        parent.grid_rowconfigure(row, weight=1)
        parent.grid_columnconfigure(column, weight=1)
        
        return btn

    def create_split_button(self, parent, text, row, column, bet_type):
        """创建分注线按钮"""
        btn = tk.Button(
            parent,
            text="",
            font=('Arial', 1),
            bg='#2a4a3c',
            fg='white',
            relief='flat',
            command=lambda: self.place_bet(bet_type, text)
        )
        btn.grid(
            row=row, 
            column=column, 
            padx=0, 
            pady=0, 
            sticky='nsew',
            ipadx=5,
            ipady=5
        )
        # 添加分注线
        canvas = tk.Canvas(btn, bg='#2a4a3c', highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.create_line(0, 0, 20, 20, fill="yellow", width=2)
        return btn

    def create_corner_button(self, parent, text, row, column, bet_type):
        """创建角注点按钮"""
        btn = tk.Button(
            parent,
            text="",
            font=('Arial', 1),
            bg='#2a4a3c',
            fg='white',
            relief='flat',
            command=lambda: self.place_bet(bet_type, text)
        )
        btn.grid(
            row=row, 
            column=column, 
            padx=0, 
            pady=0, 
            sticky='nsew',
            ipadx=5,
            ipady=5
        )
        # 添加角注点
        canvas = tk.Canvas(btn, bg='#2a4a3c', highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.create_oval(8, 8, 12, 12, fill="yellow", outline="yellow")
        return btn

    def select_chip(self, value):
        """选择筹码"""
        self.selected_chip = value
        
        # 高亮选中的筹码
        for btn in self.chip_buttons:
            if btn['image'] == self.chip_images[value]:
                btn.config(relief='sunken', borderwidth=2)
            else:
                btn.config(relief='flat', borderwidth=0)
    
    def select_bet_type(self, bet_type):
        """选择下注类型"""
        self.selected_bet_type = bet_type
        
        # 高亮选中的下注类型
        for btn in self.bet_type_buttons:
            if btn.bet_type == bet_type:
                btn.config(bg='#FFD700', fg='black')
            else:
                btn.config(bg='#4A4A4A', fg='white')
    
    def place_bet(self, bet_type, position):
        """在指定位置下注"""
        if self.balance < self.selected_chip:
            messagebox.showerror("错误", "余额不足")
            return
            
        # 下注
        self.game.place_bet(bet_type, self.selected_chip, position)
        self.balance -= self.selected_chip
        self.update_balance()
        
        # 更新显示
        self.current_bet_label.config(text=f"本局下注: ${self.game.total_bet:.2f}")
        self.status_label.config(text=f"已下注 ${self.selected_chip} ({bet_type}) 到 {position}")
        
        # 添加下注标记
        self.add_bet_marker(position)
        
        # 播放下注音效
        try:
            winsound.PlaySound("chip.wav", winsound.SND_ASYNC)
        except:
            pass
    
    def add_bet_marker(self, position):
        """添加下注标记到赌桌"""
        # 在实际游戏中，这里需要根据位置添加图形标记
        # 本实现中我们简单显示一个文本标记
        marker = tk.Label(
            self, 
            text=f"${self.selected_chip}",
            font=('Arial', 8, 'bold'),
            bg='yellow',
            fg='black',
            bd=1,
            relief=tk.RAISED
        )
        marker.place(x=random.randint(100, 1000), y=random.randint(300, 600))
        self.bet_markers.append(marker)
    
    def spin_roulette(self):
        """旋转轮盘"""
        if self.game.total_bet == 0:
            messagebox.showinfo("提示", "请先下注")
            return
            
        # 旋转轮盘动画
        self.animate_spin()
        
        # 播放旋转音效
        try:
            winsound.PlaySound("wheel_spin.wav", winsound.SND_ASYNC)
        except:
            pass
    
    def animate_spin(self, step=0, total_steps=50, final_angle=None):
        """轮盘旋转动画"""
        if step == 0:
            # 第一次调用，计算最终角度
            self.winning_number = random.randint(0, 37)  # 37代表00
            slot_angle = 360 / 38  # 38个槽位
            self.final_angle = (self.winning_number * slot_angle) % 360
            # 添加随机旋转圈数（5-10圈）
            self.final_angle += random.randint(5, 10) * 360
        
        if step < total_steps:
            # 缓动函数 - 先快后慢
            progress = step / total_steps
            # 二次缓出
            eased_progress = 1 - (1 - progress) ** 2
            current_angle = eased_progress * self.final_angle
            
            # 更新轮盘位置
            self.wheel_canvas.delete("wheel")
            self.wheel_canvas.create_image(155, 155, image=self.wheel_image, tags="wheel")
            
            # 更新小球位置
            rad = math.radians(current_angle)
            ball_x = 155 + 130 * math.cos(rad)
            ball_y = 155 + 130 * math.sin(rad)
            self.wheel_canvas.coords(self.ball_id, ball_x, ball_y)
            
            # 继续动画
            self.after(30, lambda: self.animate_spin(step+1, total_steps, self.final_angle))
        else:
            # 动画结束，结算
            winning_number, win_amount, winning_bets = self.game.spin()
            
            # 更新余额
            self.balance += win_amount
            self.update_balance()
            
            # 显示结果
            display_num = "00" if winning_number == 37 else str(winning_number)
            self.status_label.config(text=f"获胜号码: {display_num}")
            
            # 显示获胜详情
            win_text = f"赢得 ${win_amount:.2f}!\n"
            if winning_bets:
                win_text += "获胜下注:\n"
                for key, bet_type, amount, odds in winning_bets:
                    win_text += f"- {key} ({bet_type}): ${amount} × {odds+1} = ${amount*(odds+1):.2f}\n"
            else:
                win_text += "没有获胜下注"
                
            self.win_info_label.config(text=win_text)
            
            # 更新上局获胜金额
            self.last_win = win_amount
            self.last_win_label.config(text=f"上局获胜: ${win_amount:.2f}")
            
            # 播放结果音效
            try:
                if win_amount > 0:
                    winsound.PlaySound("win.wav", winsound.SND_ASYNC)
                else:
                    winsound.PlaySound("lose.wav", winsound.SND_ASYNC)
            except:
                pass
            
            # 重置下注（不清除下注显示，让玩家看到结果）
            self.after(5000, self.reset_for_new_game)
    
    def reset_for_new_game(self):
        """准备新游戏"""
        self.game.reset_game()
        self.current_bet_label.config(text="本局下注: $0.00")
        self.status_label.config(text="请选择筹码和下注类型，然后点击下注区域")
        self.win_info_label.config(text="")
        
        # 清除下注标记
        for marker in self.bet_markers:
            marker.destroy()
        self.bet_markers = []
        
        # 重置小球位置到顶部
        self.wheel_canvas.coords(self.ball_id, 155, 25)
    
    def clear_bets(self):
        """清除所有下注"""
        # 退还下注金额
        self.balance += self.game.total_bet
        self.update_balance()
        
        # 重置游戏
        self.game.reset_game()
        self.current_bet_label.config(text="本局下注: $0.00")
        self.status_label.config(text="已清除所有下注")
        
        # 清除下注标记
        for marker in self.bet_markers:
            marker.destroy()
        self.bet_markers = []
    
    def update_balance(self):
        """更新余额显示"""
        self.balance_label.config(text=f"余额: ${self.balance:.2f}")

def main(initial_balance=1000, username="Guest"):
    app = RouletteGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    # 独立运行时的示例调用
    final_balance = main()
    print(f"最终余额: {final_balance}")