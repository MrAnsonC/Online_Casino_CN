import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
import math
import secrets
import subprocess, sys

# 扑克牌花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

def get_data_file_path():
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'saving_data.json')

def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_user_data():
    file_path = get_data_file_path()
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:.2f}"
            break
    save_user_data(users)

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
    def __repr__(self):
        return f"{self.rank}{self.suit}"
    def is_red(self):
        return self.suit in ['♥', '♦']

class Deck:
    def __init__(self):
        # 获取当前脚本所在目录的上一级目录
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 新的Card文件夹路径
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
        shuffle_script = os.path.join(card_dir, 'shuffle.py')
        
        # 保证 Python 输出为 UTF-8
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        try:
            # 调用外部 shuffle.py，超时 30 秒
            result = subprocess.run(
                [sys.executable, shuffle_script],
                capture_output=True,
                text=True,
                encoding='utf-8',
                env=env,
                check=True,
                timeout=30
            )
            shuffle_data = json.loads(result.stdout)
            
            if "deck" not in shuffle_data or "cut_position" not in shuffle_data:
                raise ValueError("Invalid shuffle data format")
            
            # 用本模块的 Card 类实例化
            self.full_deck = [
                Card(d["suit"], d["rank"])
                for d in shuffle_data["deck"]
            ]
            self.cut_position = shuffle_data["cut_position"]
        
        except (subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
                json.JSONDecodeError,
                ValueError,
                KeyError) as e:
            print(f"Error calling shuffle.py: {e}. Using fallback shuffle.")
            # fallback：标准顺序+安全乱序
            self.full_deck = [Card(s, r) for s in SUITS for r in RANKS]
            self._secure_shuffle()
            self.cut_position = secrets.randbelow(52)
        
        # 通用的洗牌后索引 & 发牌序列逻辑
        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + i) % 52 for i in range(52)]
        self.pointer = 0
        self.card_sequence = [self.full_deck[i] for i in self.indexes]
    
    def _secure_shuffle(self):
        """Fisher–Yates 洗牌，用 secrets 保证随机性"""
        for i in range(len(self.full_deck) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            self.full_deck[i], self.full_deck[j] = self.full_deck[j], self.full_deck[i]

    def deal(self, n=1):
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt

class FaroGame:
    def __init__(self):
        self.reset_game()
    
    def reset_game(self):
        self.deck = Deck()
        self.player_card = None
        self.in_pile = []
        self.out_pile = []
        self.matched_card = None
        self.stage = "pre_bet"  # pre_bet, flipping, showdown
        self.in_bet_amount = 0
        self.out_bet_amount = 0
        self.red_bet_amount = 0
        self.black_bet_amount = 0
        self.high_bet_amount = 0
        self.low_bet_amount = 0
        self.cards_revealed = False
        self.pointer = 0
        self.pile_counter = 1  # 1 for IN, 2 for OUT
        self.flip_count = 0  # 记录翻牌次数

    def player_draw(self):
        """玩家抽一张牌"""
        if self.deck.pointer < 52:
            self.player_card = self.deck.deal(1)[0]
            return True
        return False
    
    def dealer_flip(self):
        """庄家翻一张牌"""
        if self.deck.pointer < 52:
            card = self.deck.deal(1)[0]
            self.flip_count += 1
            
            # 交替放入IN和OUT牌堆
            if self.pile_counter == 1:
                self.in_pile.append(card)
                pile = "IN"
                self.pile_counter = 2
            else:
                self.out_pile.append(card)
                pile = "OUT"
                self.pile_counter = 1
            
            # 检查是否匹配玩家牌
            if card.rank == self.player_card.rank:
                self.matched_card = card
                self.matched_pile = pile
            
            return card, pile
        return None, None

class FaroGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("Faro 游戏")
        self.geometry("1050x680+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')
        
        self.username = username
        self.balance = initial_balance
        self.game = FaroGame()
        self.card_images = {}
        self.original_images = {}  # 用于存储原始卡片图像
        self.animation_queue = []
        self.animation_in_progress = False
        self.card_positions = {}
        self.active_card_labels = []  # 追踪所有活动中的卡片标签
        self.selected_chip = None  # 当前选中的筹码
        self.chip_buttons = []  # 筹码按钮列表
        self.last_win = 0
        self.auto_reset_timer = None
        self.buttons_disabled = False  # 跟踪按钮是否被禁用
        self.win_details = {}
        self.bet_widgets = {}  # 存储下注显示控件
        self.bet_choice_var = tk.StringVar(value="IN")  # 默认选择IN

        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def on_close(self):
        # 取消自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
        self.destroy()
        self.quit()
        
    def _load_assets(self):
        card_size = (100, 140)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
        
        # 花色映射：将符号映射为英文名称
        suit_mapping = {
            '♠': 'Spade',
            '♥': 'Heart',
            '♦': 'Diamond',
            '♣': 'Club'
        }
        
        # 加载背面图片
        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_img = Image.open(back_path).resize(card_size)
            self.back_image = ImageTk.PhotoImage(back_img)
            self.original_images["back"] = Image.open(back_path)  # 保存原始图像
        except Exception as e:
            print(f"Error loading back image: {e}")
            # 如果没有背景图，创建一个黑色背景
            img = Image.new('RGB', card_size, 'black')
            self.back_image = ImageTk.PhotoImage(img)
            self.original_images["back"] = img  # 保存原始图像
        
        # 加载扑克牌图片
        for suit in SUITS:
            for rank in RANKS:
                # 获取映射后的文件名
                suit_name = suit_mapping.get(suit, suit)
                
                # 尝试可能的文件名组合
                possible_filenames = [
                    f"{suit_name}{rank}.png",       # 如 "SpadeA.png"
                ]
                
                img_found = False
                for filename in possible_filenames:
                    path = os.path.join(card_dir, filename)
                    if os.path.exists(path):
                        try:
                            img = Image.open(path).resize(card_size)
                            self.card_images[(suit, rank)] = ImageTk.PhotoImage(img)
                            self.original_images[(suit, rank)] = Image.open(path)  # 保存原始图像
                            img_found = True
                            break
                        except Exception as e:
                            print(f"Error loading {path}: {e}")
                
                # 如果没有找到图片，创建一个占位图片
                if not img_found:
                    print(f"Card image not found for {suit}{rank}")
                    img = Image.new('RGB', card_size, 'blue')
                    draw = ImageDraw.Draw(img)
                    # 在图片上绘制花色和点数
                    try:
                        font = ImageFont.truetype("arial.ttf", 24)
                        text = f"{suit}{rank}"
                        draw.text((10, 10), text, font=font, fill="white")
                    except:
                        # 如果字体加载失败，使用简单文本
                        draw.text((10, 10), f"{suit}{rank}", fill="white")
                    
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img)
                    self.original_images[(suit, rank)] = img  # 保存原始图像

    def add_chip_to_bet(self, bet_type):
        """添加筹码到下注区域"""
        if not self.selected_chip:
            return
            
        # 获取筹码金额
        chip_value = float(self.selected_chip.replace('$', '').replace('K', '000'))
        
        # 更新对应的下注变量
        if bet_type == "IN":
            current = float(self.in_bet_var.get())
            self.in_bet_var.set(str(int(current + chip_value)))
        elif bet_type == "OUT":
            current = float(self.out_bet_var.get())
            self.out_bet_var.set(str(int(current + chip_value)))
        elif bet_type == "RED":
            current = float(self.red_bet_var.get())
            self.red_bet_var.set(str(int(current + chip_value)))
        elif bet_type == "BLACK":
            current = float(self.black_bet_var.get())
            self.black_bet_var.set(str(int(current + chip_value)))
        elif bet_type == "HIGH":
            current = float(self.high_bet_var.get())
            self.high_bet_var.set(str(int(current + chip_value)))
        elif bet_type == "LOW":
            current = float(self.low_bet_var.get())
            self.low_bet_var.set(str(int(current + chip_value)))
    
    def _create_widgets(self):
        # 先初始化变量
        self.in_bet_var  = tk.StringVar(value="0")
        self.out_bet_var = tk.StringVar(value="0")
        self.red_bet_var = tk.StringVar(value="0")
        self.black_bet_var = tk.StringVar(value="0")
        self.high_bet_var = tk.StringVar(value="0")
        self.low_bet_var = tk.StringVar(value="0")

        # 主框架 - 左右布局
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧牌桌区域 - 使用Canvas提供更好的控制
        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 牌桌背景
        table_bg = table_canvas.create_rectangle(0, 0, 800, 600, fill='#35654d', outline='')
        
        # 玩家区域
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=10, y=50, width=175, height=250)
        self.player_label = tk.Label(player_frame, text="目标牌", font=('Arial', 14), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_card_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_card_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # IN/OUT牌堆区域 - 固定高度和宽度
        piles_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        piles_frame.place(x=200, y=50, width=400, height=600)
        
        # IN牌堆标题
        in_title_frame = tk.Frame(piles_frame, bg='#2a4a3c')
        in_title_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(in_title_frame, text="IN", font=('Arial', 16, 'bold'), 
                bg='#2a4a3c', fg='#FF5555').pack(side=tk.LEFT)
        
        # IN牌堆容器 - 固定高度
        in_container = tk.Frame(piles_frame, bg='#2a4a3c', height=260)
        in_container.pack(fill=tk.X, padx=10, pady=5)
        
        # IN牌堆卡片区 - 使用Canvas以便控制位置
        in_canvas = tk.Canvas(in_container, bg='#2a4a3c', height=260, highlightthickness=0)
        in_canvas.pack(fill=tk.X)
        self.in_cards_frame = tk.Frame(in_canvas, bg='#2a4a3c')
        self.in_cards_frame.place(x=0, y=0, relwidth=1, height=260)
        
        # OUT牌堆标题
        out_title_frame = tk.Frame(piles_frame, bg='#2a4a3c')
        out_title_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(out_title_frame, text="OUT", font=('Arial', 16, 'bold'), 
                bg='#2a4a3c', fg='#5555FF').pack(side=tk.LEFT)
        
        # OUT牌堆容器 - 固定高度
        out_container = tk.Frame(piles_frame, bg='#2a4a3c', height=260)
        out_container.pack(fill=tk.X, padx=10, pady=5)
        
        # OUT牌堆卡片区 - 使用Canvas以便控制位置
        out_canvas = tk.Canvas(out_container, bg='#2a4a3c', height=260, highlightthickness=0)
        out_canvas.pack(fill=tk.X)
        self.out_cards_frame = tk.Frame(out_canvas, bg='#2a4a3c')
        self.out_cards_frame.place(x=0, y=0, relwidth=1, height=260)
        
        # 右侧控制面板
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=300, padx=10, pady=10)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 顶部信息栏
        info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=10)
        
        self.balance_label = tk.Label(
            info_frame, 
            text=f"余额: ${self.balance:.2f}",
            font=('Arial', 14),
            bg='#2a4a3c',
            fg='white'
        )
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        self.stage_label = tk.Label(
            info_frame, 
            text="阶段: 下注",
            font=('Arial', 14, 'bold'),
            bg='#2a4a3c',
            fg='#FFD700'
        )
        self.stage_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        # 筹码区域
        chips_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        chips_frame.pack(fill=tk.X, pady=10)
        
        chips_label = tk.Label(chips_frame, text="筹码:", font=('Arial', 12), bg='#2a4a3c', fg='white')
        chips_label.pack(anchor='w', padx=10, pady=5)
        
        # 单行放置5个筹码 - 增加50%大小
        chip_row = tk.Frame(chips_frame, bg='#2a4a3c')
        chip_row.pack(fill=tk.X, pady=5, padx=5)
        
        chip_configs = [
            ("$5", '#ff0000', 'white'),     # 红色背景，白色文字
            ('$10', '#ffa500', 'black'),   # 橙色背景，黑色文字
            ("$25", '#00ff00', 'black'),    # 绿色背景，黑色文字
            ("$50", '#ffffff', 'black'),    # 白色背景，黑色文字
            ("$100", '#000000', 'white'),   # 黑色背景，白色文字
        ]
        
        self.chip_buttons = []
        self.chip_texts = {}  # 存储每个筹码按钮的文本
        for text, bg_color, fg_color in chip_configs:
            # 使用Canvas创建圆形筹码 - 增加50%大小 (60x60)
            chip_canvas = tk.Canvas(chip_row, width=60, height=60, bg='#2a4a3c', highlightthickness=0)
            chip_canvas.create_oval(2, 2, 58, 58, fill=bg_color, outline='black')
            text_id = chip_canvas.create_text(30, 30, text=text, fill=fg_color, font=('Arial', 16, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text  # 存储文本
        
        # 默认选中$5筹码
        self.select_chip("$5")
        
        # 下注区域 - 现在有多个下注区域：IN, OUT, 黑/红, 大/小
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=10)
        
        # 第一行：IN 和 OUT
        bet_line1 = tk.Frame(bet_frame, bg='#2a4a3c')
        bet_line1.pack(fill=tk.X, padx=20, pady=5)

        # IN 下注
        tk.Label(bet_line1, text="IN:", font=('Arial',12), bg='#2a4a3c', fg='white').pack(side=tk.LEFT)
        self.in_bet_display = tk.Label(bet_line1, textvariable=self.in_bet_var, font=('Arial',12),
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.in_bet_display.pack(side=tk.LEFT, padx=(5,20))
        self.in_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("IN"))
        self.bet_widgets["IN"] = self.in_bet_display

        # OUT 下注
        tk.Label(bet_line1, text="OUT:", font=('Arial',12), bg='#2a4a3c', fg='white').pack(side=tk.LEFT)
        self.out_bet_display = tk.Label(bet_line1, textvariable=self.out_bet_var, font=('Arial',12),
                                        bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.out_bet_display.pack(side=tk.LEFT, padx=5)
        self.out_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("OUT"))
        self.bet_widgets["OUT"] = self.out_bet_display
        
        # 第二行：黑/红下注
        bet_line2 = tk.Frame(bet_frame, bg='#2a4a3c')
        bet_line2.pack(fill=tk.X, padx=20, pady=5)
        
        # 红下注
        tk.Label(bet_line2, text="红:", font=('Arial',12), bg='#2a4a3c', fg="#ffffff").pack(side=tk.LEFT)
        self.red_bet_display = tk.Label(bet_line2, textvariable=self.red_bet_var, font=('Arial',12),
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.red_bet_display.pack(side=tk.LEFT, padx=(5,20))
        self.red_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("RED"))
        self.bet_widgets["RED"] = self.red_bet_display
        
        # 黑下注
        tk.Label(bet_line2, text="   黑:", font=('Arial',12), bg='#2a4a3c', fg="#ffffff").pack(side=tk.LEFT)
        self.black_bet_display = tk.Label(bet_line2, textvariable=self.black_bet_var, font=('Arial',12),
                                        bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.black_bet_display.pack(side=tk.LEFT, padx=5)
        self.black_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("BLACK"))
        self.bet_widgets["BLACK"] = self.black_bet_display
        
        # 第三行：大/小下注
        bet_line3 = tk.Frame(bet_frame, bg='#2a4a3c')
        bet_line3.pack(fill=tk.X, padx=20, pady=(5,10))
        
        # 大下注
        tk.Label(bet_line3, text="大:", font=('Arial',12), bg='#2a4a3c', fg="#ffffff").pack(side=tk.LEFT)
        self.high_bet_display = tk.Label(bet_line3, textvariable=self.high_bet_var, font=('Arial',12),
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.high_bet_display.pack(side=tk.LEFT, padx=(5,20))
        self.high_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("HIGH"))
        self.bet_widgets["HIGH"] = self.high_bet_display
        
        # 小下注
        tk.Label(bet_line3, text="   小:", font=('Arial',12), bg='#2a4a3c', fg="#ffffff").pack(side=tk.LEFT)
        self.low_bet_display = tk.Label(bet_line3, textvariable=self.low_bet_var, font=('Arial',12),
                                        bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.low_bet_display.pack(side=tk.LEFT, padx=5)
        self.low_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("LOW"))
        self.bet_widgets["LOW"] = self.low_bet_display
        
        # 游戏操作按钮框架 - 用于放置所有操作按钮
        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        self.action_frame.pack(fill=tk.X, pady=10)

        # 创建一个框架来容纳重置按钮和开始游戏按钮
        start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_button_frame.pack(pady=10)

        # 添加"重设金额"按钮
        self.reset_bets_button = tk.Button(
            start_button_frame, text="重设金额", 
            command=self.reset_bets, font=('Arial', 14),
            bg='#F44336', fg='white', width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 开始游戏按钮
        self.start_button = tk.Button(
            start_button_frame, text="开始游戏", 
            command=self.start_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT)
        
        # 状态信息
        self.status_label = tk.Label(
            control_frame, text="设置下注金额并开始游戏", 
            font=('Arial', 12), bg="#2a4a3c", fg='white'
        )
        self.status_label.pack(pady=5, fill=tk.X)
        
        # 本局下注和上局获胜金额显示
        bet_info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_info_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 本局下注金额 - 只显示总金额
        self.current_bet_label = tk.Label(
            bet_info_frame, text="本局下注: $0.00", 
            font=('Arial', 12), bg='#2a4a3c', fg='white'
        )
        self.current_bet_label.pack(pady=5, padx=10, anchor='w')
        
        # 上局获胜金额
        self.last_win_label = tk.Label(
            bet_info_frame, text="上局获胜: $0.00", 
            font=('Arial', 12), bg='#2a4a3c', fg='#FFD700'
        )
        self.last_win_label.pack(pady=5, padx=10, anchor='w', side=tk.LEFT)
        
        # 添加游戏规则按钮到上局获胜的右下角
        rules_btn = tk.Button(
            bet_info_frame, text="ℹ️", 
            command=self.show_game_instructions, 
            font=('Arial', 8), bg='#4B8BBE', fg='white', width=2, height=1
        )
        rules_btn.pack(side=tk.RIGHT, padx=10, pady=5)
    
    def show_game_instructions(self):
        """显示游戏规则说明"""
        # 创建自定义弹窗
        win = tk.Toplevel(self)
        win.title("Faro 游戏规则")
        win.geometry("800x500")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')
        
        # 创建主框架
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建画布用于滚动
        canvas = tk.Canvas(main_frame, bg='#F0F0F0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        
        # 创建内部框架放置所有内容
        content_frame = tk.Frame(canvas, bg='#F0F0F0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')
        
        # 游戏规则文本
        rules_text = """
        Faro(变种) 游戏规则

        核心创新：
        - 先抽取目标牌
        - 庄家翻牌直到匹配目标牌点数
        - 胜负取决于匹配牌出现的牌堆/颜色/顺序位置

        1. 游戏开始前下注:
           - 选择下注区域: 
                * IN 或 OUT: 匹配牌落在IN或OUT牌堆
                * 红或黑: 匹配牌的颜色
                * 大或小: 匹配牌出现的位置
           - 设置下注金额
           - 点击"开始游戏"按钮开始

        2. 游戏流程:
           a. 抽第一张牌
           b. 庄家轮流翻牌:
              - 第一张牌放入 IN 牌堆
              - 第二张牌放入 OUT 牌堆
              - 第三张牌放入 IN 牌堆
              - 第四张牌放入 OUT 牌堆
              - 以此类推...
           c. 当翻到与玩家牌点数相同的牌时停止
           d. 如果匹配牌落在您下注的区域 (IN, OUT, 红, 黑, 大, 小), 您赢

        3. 结算规则:
           - IN/OUT: 1:1 赔率
           - 红/黑: 1:1 赔率
           - 大/小: 
               * 小: 匹配牌在翻牌位置1-17之间
               * 大: 匹配牌在翻牌位置18-49之间
               * 赔率: 1:1
        """
        
        rules_label = tk.Label(
            content_frame, 
            text=rules_text,
            font=('微软雅黑', 11),
            bg='#F0F0F0',
            justify=tk.LEFT,
            padx=10,
            pady=10
        )
        rules_label.pack(fill=tk.X, padx=10, pady=5)
        
        # 更新滚动区域
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        
        # 添加关闭按钮
        close_btn = ttk.Button(
            win,
            text="关闭",
            command=win.destroy
        )
        close_btn.pack(pady=10)
        
        # 绑定鼠标滚轮滚动
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
    
    def select_chip(self, chip_text):
        """选择筹码，并更新筹码的高亮状态"""
        self.selected_chip = chip_text
        # 1. 重置所有筹码的边框
        for chip in self.chip_buttons:
            # 删除之前的高亮
            chip.delete("highlight")
            # 找到 oval 的 id，重画默认黑色边框
            for item_id in chip.find_all():
                if chip.type(item_id) == 'oval':
                    x1, y1, x2, y2 = chip.coords(item_id)
                    chip.create_oval(x1, y1, x2, y2, outline='black', width=2)
                    break

        # 2. 给选中的筹码加金色高亮
        for chip in self.chip_buttons:
            text_id = None
            oval_id = None
            # 先分别找到 text 和 oval 的 id
            for item_id in chip.find_all():
                t = chip.type(item_id)
                if t == 'text':
                    text_id = item_id
                elif t == 'oval':
                    oval_id = item_id
            # 如果找到了文字项，并且内容匹配
            if text_id and chip.itemcget(text_id, 'text') == chip_text:
                # 拿到对应的 oval 坐标
                x1, y1, x2, y2 = chip.coords(oval_id)
                chip.create_oval(x1, y1, x2, y2, outline='gold', width=3, tags="highlight")
                break
    
    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)
    
    def disable_action_buttons(self):
        """禁用所有操作按钮"""
        self.buttons_disabled = True
        for widget in self.action_frame.winfo_children():
            widget.config(state=tk.DISABLED)
    
    def enable_action_buttons(self):
        """启用所有操作按钮"""
        self.buttons_disabled = False
        for widget in self.action_frame.winfo_children():
            widget.config(state=tk.NORMAL)
    
    def start_game(self):
        try:
            in_bet = int(self.in_bet_var.get())
            out_bet = int(self.out_bet_var.get())
            red_bet = int(self.red_bet_var.get())
            black_bet = int(self.black_bet_var.get())
            high_bet = int(self.high_bet_var.get())
            low_bet = int(self.low_bet_var.get())
            total_bet = in_bet + out_bet + red_bet + black_bet + high_bet + low_bet
            
            # 检查下注金额
            if total_bet < 5:
                messagebox.showerror("错误", "下注金额至少需要5块")
                return
                
            if self.balance < total_bet:
                messagebox.showerror("错误", "余额不足")
                return
                
            self.balance -= total_bet
            self.update_balance()
            
            # 更新本局下注显示 - 只显示总金额
            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            
            self.game.reset_game()
            self.game.in_bet_amount = in_bet
            self.game.out_bet_amount = out_bet
            self.game.red_bet_amount = red_bet
            self.game.black_bet_amount = black_bet
            self.game.high_bet_amount = high_bet
            self.game.low_bet_amount = low_bet
            
            # 清除所有卡片
            for widget in self.player_card_frame.winfo_children():
                widget.destroy()
            for widget in self.in_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.out_cards_frame.winfo_children():
                widget.destroy()
            
            # 玩家抽牌
            if not self.game.player_draw():
                messagebox.showerror("错误", "牌堆已空，无法抽牌")
                return
                
            # 显示玩家的牌（正面） - 游戏开始就翻开
            self.show_player_card()
            
            # 更新游戏状态
            self.stage_label.config(text="阶段: 翻牌中")
            self.status_label.config(text="庄家正在翻牌...")
            
            # 禁用下注区域
            self.in_bet_display.unbind("<Button-1>")
            self.out_bet_display.unbind("<Button-1>")
            self.red_bet_display.unbind("<Button-1>")
            self.black_bet_display.unbind("<Button-1>")
            self.high_bet_display.unbind("<Button-1>")
            self.low_bet_display.unbind("<Button-1>")
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")
            
            # 禁用开始按钮和重置按钮
            self.start_button.config(state=tk.DISABLED)
            self.reset_bets_button.config(state=tk.DISABLED)
            
            # 开始自动翻牌
            self.auto_flip_until_match()
            
        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")

    def show_player_card(self):
        """显示玩家的牌（正面）"""
        card = self.game.player_card
        front_img = self.card_images.get((card.suit, card.rank), self.back_image)
        
        card_label = tk.Label(self.player_card_frame, image=front_img, bg='#2a4a3c')
        card_label.pack(pady=20)
        card_label.card = card
        card_label.is_face_up = True
        # 将玩家牌加入活动列表，以便收牌动画
        self.active_card_labels.append(card_label)
    
    def flip_card_animation(self, card_label):
        """卡片翻转动画"""
        # 获取卡片正面图像
        card = card_label.card
        front_img = self.card_images.get((card.suit, card.rank), self.back_image)
        
        # 创建动画序列
        self.animate_flip(card_label, front_img, 0)
    
    def animate_flip(self, card_label, front_img, step):
        """执行翻转动画"""
        steps = 10  # 动画总步数
        
        if step > steps:
            # 动画结束
            card_label.is_face_up = True
            return
        
        # 简化翻转动画 - 直接切换图片
        if step == 5:
            card_label.config(image=front_img)
        
        step += 1
        card_label.after(50, lambda: self.animate_flip(card_label, front_img, step))
    
    def show_flipped_card(self, card, pile):
        """显示刚翻开的牌"""
        frame = self.in_cards_frame if pile == "IN" else self.out_cards_frame
        
        # 创建卡片标签
        card_label = tk.Label(frame, image=self.back_image, bg='#2a4a3c')
        card_label.card = card
        self.active_card_labels.append(card_label)  # 添加到活动列表
        
        # 计算位置 - 根据牌堆中的牌数（从0开始计数）
        card_count = len(frame.winfo_children()) - 1
        
        # 每9张牌换行，卡片索引从1开始计数
        row = (card_count) // 9  # 计算行数（0-indexed）
        col = (card_count) % 9   # 计算列数（0-indexed）
        
        # 设置位置 - 所有行都从0开始
        card_label.place(x=col * 25, y=row * 50)
        
        # 翻牌动画
        self.flip_card_animation(card_label)
    
    def auto_flip_until_match(self):
        card, pile = self.game.dealer_flip()
        
        if card is None:
            messagebox.showinfo("游戏结束", "牌堆已空，未找到匹配牌")
            self.end_game(False)
            return
            
        # 显示翻开的牌
        self.show_flipped_card(card, pile)
        self.status_label.config(text=f"庄家翻牌: {card.rank}{card.suit} -> {pile} (第{self.game.flip_count}张)")
        
        # 检查是否匹配
        if self.game.matched_card:
            # 匹配牌出现，显示结果
            self.after(1500, self.show_result)
        else:
            # 继续翻牌
            self.after(500, self.auto_flip_until_match)
    
    def show_result(self):
        """显示游戏结果"""
        # 高亮匹配的牌
        for frame in [self.in_cards_frame, self.out_cards_frame]:
            for card_label in frame.winfo_children():
                if hasattr(card_label, "card") and card_label.card.rank == self.game.player_card.rank:
                    card_label.config(bg='gold')
                    card_label.config(relief="solid", bd=2, highlightbackground="yellow", highlightthickness=2)
        
        # 判断输赢
        in_win = (self.game.matched_pile == "IN")
        out_win = (self.game.matched_pile == "OUT")
        red_win = self.game.matched_card.is_red()
        black_win = not red_win
        
        # 大小判定：前17张为小，18-51为大
        low_win = self.game.flip_count <= 17
        high_win = not low_win
        
        self.end_game(in_win, out_win, red_win, black_win, low_win, high_win)
    
    def end_game(self, in_win, out_win, red_win, black_win, low_win, high_win):
        """结束游戏并结算"""
        # 计算赢得的金额
        winnings = 0
        round_winnings = 0  # 本局获胜金额（获胜本金+盈利）
        
        # IN/OUT下注结算
        if in_win:
            in_total = self.game.in_bet_amount * 2
            winnings += in_total
            round_winnings += in_total
            # 更新IN下注显示
            self.in_bet_var.set(str(in_total))
            self.in_bet_display.config(bg='gold')
        else:
            winnings -= self.game.in_bet_amount
            self.in_bet_var.set('0')
        
        if out_win:
            out_total = self.game.out_bet_amount * 2
            winnings += out_total
            round_winnings += out_total
            # 更新OUT下注显示
            self.out_bet_var.set(str(out_total))
            self.out_bet_display.config(bg='gold')
        else:
            winnings -= self.game.out_bet_amount
            self.out_bet_var.set('0')
        
        # 红黑下注结算
        if red_win:
            red_total = self.game.red_bet_amount * 2
            winnings += red_total
            round_winnings += red_total
            # 更新红下注显示
            self.red_bet_var.set(str(red_total))
            self.red_bet_display.config(bg='gold')
        else:
            winnings -= self.game.red_bet_amount
            self.red_bet_var.set('0')
        
        if black_win:
            black_total = self.game.black_bet_amount * 2
            winnings += black_total
            round_winnings += black_total
            # 更新黑下注显示
            self.black_bet_var.set(str(black_total))
            self.black_bet_display.config(bg='gold')
        else:
            winnings -= self.game.black_bet_amount
            self.black_bet_var.set('0')
        
        # 大小下注结算
        if low_win:
            low_total = self.game.low_bet_amount * 2
            winnings += low_total
            round_winnings += low_total
            # 更新小下注显示
            self.low_bet_var.set(str(low_total))
            self.low_bet_display.config(bg='gold')
        else:
            winnings -= self.game.low_bet_amount
            self.low_bet_var.set('0')
        
        if high_win:
            high_total = self.game.high_bet_amount * 2
            winnings += high_total
            round_winnings += high_total
            # 更新大下注显示
            self.high_bet_var.set(str(high_total))
            self.high_bet_display.config(bg='gold')
        else:
            winnings -= self.game.high_bet_amount
            self.high_bet_var.set('0')
        
        # 构建结果文本
        result_text = (
            f"本局点数是{self.game.player_card.rank}, "
            f"第{self.game.flip_count}张抽到, "
            f"{self.game.matched_pile}, "
            f"{'红' if self.game.matched_card.is_red() else '黑'}"
        )
        
        # 更新余额
        self.balance += winnings
        self.update_balance()
        
        # 更新状态标签
        self.status_label.config(text=result_text)
        
        # 更新本局获胜金额
        self.last_win_label.config(text=f"本局获胜: ${round_winnings:.2f}")
        
        # 添加重新开始按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()
            
        restart_btn = tk.Button(
            self.action_frame, text="再来一局", 
            command=self.reset_game, 
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
        )
        restart_btn.pack(pady=10)
        
        # 设置30秒后自动重置
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
    
    def animate_collect_cards(self, auto_reset):
        """执行收牌动画：先翻转所有牌为背面，然后向右收起"""
        # 禁用所有按钮
        self.disable_action_buttons()
        
        # 第一步：翻转所有牌为背面
        self.flip_all_to_back()
        
        # 第二步：设置动画完成后执行真正的重置
        self.after(1000, lambda: self.animate_move_cards_out(auto_reset))

    def flip_all_to_back(self):
        """将所有牌翻转为背面"""
        self.flipping_cards = []  # 存储正在翻转的卡片
        
        # 收集所有需要翻转的卡片（包括玩家牌）
        for card_label in self.active_card_labels:
            if card_label.is_face_up:
                self.flipping_cards.append(card_label)
        
        # 如果没有需要翻转的卡片，直接返回
        if not self.flipping_cards:
            self.after(500, lambda: self.animate_move_cards_out(False))
            return
            
        # 开始翻转动画
        self.animate_flip_to_back_step(0)

    def animate_flip_to_back_step(self, step):
        """执行翻转动画的每一步"""
        if step >= 10:  # 假设10步完成
            # 翻转完成，将所有正在翻转的卡片设为背面
            for card_label in self.flipping_cards:
                card_label.config(image=self.back_image)
                card_label.is_face_up = False
                
            # 开始移动动画
            self.after(500, lambda: self.animate_move_cards_out(False))
            return

        # 模拟翻转效果：先缩小宽度，再放大（但背面）
        width = 100 - (step * 10) if step < 5 else (step - 5) * 10
        if width <= 0:
            width = 1

        for card_label in self.flipping_cards:
            card_label.place(width=width)

        step += 1
        self.after(50, lambda: self.animate_flip_to_back_step(step))

    def animate_move_cards_out(self, auto_reset):
        """将所有牌向右移出屏幕"""
        if not self.active_card_labels:
            # 没有牌，直接重置
            self._do_reset(auto_reset)
            return

        # 设置所有牌的目标位置为屏幕右侧外
        for card_label in self.active_card_labels:
            card_label.target_pos = (1200, card_label.winfo_y())  # 目标x为窗口右侧外

        # 开始移动
        self.animate_card_out_step(auto_reset)

    def animate_card_out_step(self, auto_reset):
        """移动卡片出屏幕的每一步"""
        all_done = True
        for card_label in self.active_card_labels[:]:  # 遍历副本，因为可能删除
            if not hasattr(card_label, 'target_pos'):
                continue

            current_x = card_label.winfo_x()
            target_x, target_y = card_label.target_pos

            # 计算新位置
            dx = target_x - current_x
            if abs(dx) < 5:
                card_label.place(x=target_x, y=target_y)
                # 移除该卡片
                card_label.destroy()
                if card_label in self.active_card_labels:
                    self.active_card_labels.remove(card_label)
                continue

            new_x = current_x + dx * 0.2
            card_label.place(x=new_x)
            all_done = False

        if not all_done:
            self.after(20, lambda: self.animate_card_out_step(auto_reset))
        else:
            # 所有动画完成，重置游戏
            self._do_reset(auto_reset)

    def reset_game(self, auto_reset=False):
        # 取消自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        
        # 如果当前有牌在桌上，先执行收牌动画
        if self.active_card_labels:
            self.disable_action_buttons()  # 禁用按钮
            self.animate_collect_cards(auto_reset)  # 开始收牌动画，动画完成后会调用真正的重置
            return

        # 否则直接重置
        self._do_reset(auto_reset)
    
    def reset_bets(self):
        """重置下注金额为0"""
        self.in_bet_var.set("0")
        self.out_bet_var.set("0")
        self.red_bet_var.set("0")
        self.black_bet_var.set("0")
        self.high_bet_var.set("0")
        self.low_bet_var.set("0")
        
        # 更新显示
        self.status_label.config(text="已重置下注金额")
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 短暂高亮显示重置效果
        self.in_bet_display.config(bg='#FFCDD2')  # 浅红色
        self.out_bet_display.config(bg='#FFCDD2')  # 浅红色
        self.red_bet_display.config(bg='#FFCDD2')  # 浅红色
        self.black_bet_display.config(bg='#FFCDD2')  # 浅红色
        self.high_bet_display.config(bg='#FFCDD2')  # 浅红色
        self.low_bet_display.config(bg='#FFCDD2')  # 浅红色
        self.after(500, lambda: [w.config(bg='white') for w in self.bet_widgets.values()])
    
    def _do_reset(self, auto_reset=False):
        """真正的重置游戏界面"""
        # 重置游戏状态
        self.game.reset_game()
        self.stage_label.config(text="阶段: 下注")
        self.status_label.config(text="设置下注金额并开始游戏")
        
        # 重置下注金额为0
        self.in_bet_var.set("0")
        self.out_bet_var.set("0")
        self.red_bet_var.set("0")
        self.black_bet_var.set("0")
        self.high_bet_var.set("0")
        self.low_bet_var.set("0")
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 清空活动卡片列表（在收牌动画后已经清空，这里确保一下）
        self.active_card_labels = []
        
        # 恢复下注区域
        self.in_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("IN"))
        self.out_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("OUT"))
        self.red_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("RED"))
        self.black_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("BLACK"))
        self.high_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("HIGH"))
        self.low_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("LOW"))
        for chip in self.chip_buttons:
            # 使用存储的文本重新绑定事件
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
        
        # 恢复操作按钮区域
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        
        start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_button_frame.pack(pady=10)

        # 添加"重设金额"按钮
        self.reset_bets_button = tk.Button(
            start_button_frame, text="重设金额", 
            command=self.reset_bets, font=('Arial', 14),
            bg='#F44336', fg='white', width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))  # 右侧留出10像素间距

        # 开始游戏按钮
        self.start_button = tk.Button(
            start_button_frame, text="开始游戏", 
            command=self.start_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT)
        
        # 重置本局下注显示
        self.current_bet_label.config(text="本局下注: $0.00")
        
        # 如果是自动重置，显示消息
        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))

def main(initial_balance=1000, username="Guest"):
    app = FaroGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    # 独立运行时的示例调用
    final_balance = main()
    print(f"Final balance: {final_balance}")