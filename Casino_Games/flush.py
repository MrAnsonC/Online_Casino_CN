import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
import math
import hashlib
import time
import secrets
import subprocess, sys
import struct

# 扑克牌花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}

# 高牌同花赔付表
FLUSH_BONUS_PAYOUT = {
    7: 300,  # 7张同花 300:1
    6: 100,  # 6张同花 100:1
    5: 10,   # 5张同花 10:1
    4: 1,    # 4张同花 1:1,
}

STRAIGHT_FLUSH_BONUS_PAYOUT = {
    7: 8000,  # 7张同花顺 8000:1
    6: 1000,  # 6张同花顺 1000:1
    5: 100,   # 5张同花顺 100:1
    4: 60,    # 4张同花顺 60:1
    3: 7,     # 3张同花顺 7:1,
}

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
        self.value = RANK_VALUES[rank]
    def __repr__(self):
        return f"{self.rank}{self.suit}"

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
                [sys.executable, shuffle_script, "false", "1"],
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

def evaluate_seven_card_hand(cards):
    """评估七张牌的手牌，返回最大同花的花色、长度和高牌"""
    # 按花色分组
    suits = {}
    for card in cards:
        suits.setdefault(card.suit, []).append(card)
    
    # 找出最大同花
    max_flush = []
    flush_suit = ''
    for suit, cards_in_suit in suits.items():
        if len(cards_in_suit) > len(max_flush):
            max_flush = sorted(cards_in_suit, key=lambda c: c.value, reverse=True)
            flush_suit = suit
        elif len(cards_in_suit) == len(max_flush) and cards_in_suit:
            # 如果同花长度相同，比较高牌
            current_high = max_flush[0].value if max_flush else 0
            new_high = max(card.value for card in cards_in_suit)
            if new_high > current_high:
                max_flush = sorted(cards_in_suit, key=lambda c: c.value, reverse=True)
                flush_suit = suit
    
    flush_length = len(max_flush)
    high_card = max_flush[0].value if max_flush else 0
    
    # 检查同花顺
    straight_flush_length = 0
    if flush_length >= 3:
        values = sorted([c.value for c in max_flush])
        # 检查连续
        consecutive_count = 1
        max_consecutive = 1
        for i in range(1, len(values)):
            if values[i] == values[i-1] + 1:
                consecutive_count += 1
                if consecutive_count > max_consecutive:
                    max_consecutive = consecutive_count
            else:
                consecutive_count = 1
        
        # 特殊处理A-2-3-4-5
        if 14 in values and 2 in values and 3 in values and 4 in values and 5 in values:
            max_consecutive = max(max_consecutive, 5)
        
        straight_flush_length = max_consecutive
    
    # 获取花色名称
    suit_names = {'♠': "黑桃", '♥': "红心", '♦': "方片", '♣': "梅花"}
    suit_name = suit_names.get(flush_suit, '')
    
    return suit_name, flush_length, high_card, straight_flush_length, max_flush

def compare_hands(hand1, hand2):
    """比较两手牌，返回1表示hand1赢，0表示平局，-1表示hand2赢"""
    _, flush_len1, high_card1, _, _ = evaluate_seven_card_hand(hand1)
    _, flush_len2, high_card2, _, _ = evaluate_seven_card_hand(hand2)
    
    # 先比较同花长度
    if flush_len1 > flush_len2:
        return 1
    elif flush_len1 < flush_len2:
        return -1
    else:
        # 同花长度相同，比较高牌
        if high_card1 > high_card2:
            return 1
        elif high_card1 < high_card2:
            return -1
        else:
            # 高牌相同，比较次高牌（递归比较）
            _, _, _, _, flush_cards1 = evaluate_seven_card_hand(hand1)
            _, _, _, _, flush_cards2 = evaluate_seven_card_hand(hand2)
            
            # 比较同花中的所有牌
            for i in range(min(len(flush_cards1), len(flush_cards2))):
                if flush_cards1[i].value > flush_cards2[i].value:
                    return 1
                elif flush_cards1[i].value < flush_cards2[i].value:
                    return -1
            return 0

class HighCardFlushGame:
    def __init__(self):
        self.reset_game()
        # 添加牌序记录
        self.card_sequence = []  # 记录整副牌的序列
        self.cut_position = 0    # 切牌位置
        self.cut_method = 0      # 切牌方法
    
    def reset_game(self):
        self.deck = Deck()
        self.player_hand = []
        self.dealer_hand = []
        self.ante = 0
        self.flush_bonus = 0
        self.straight_flush_bonus = 0
        self.play_bet = 0
        self.stage = "pre_flop"  # pre_flop, decision, showdown
        self.folded = False
        self.cards_revealed = {
            "player": [False, False, False, False, False, False, False],
            "dealer": [False, False, False, False, False, False, False]
        }
        # 记录牌序和切牌位置
        self.card_sequence = self.deck.full_deck.copy()
        self.cut_position = self.deck.start_pos
    
    def deal_initial(self):
        """发初始牌：玩家7张，庄家7张"""
        self.player_hand = self.deck.deal(7)
        self.dealer_hand = self.deck.deal(7)
    
    def dealer_qualifies(self):
        """庄家是否合格（至少3张同花且高牌不小于9）"""
        _, flush_len, high_card, _, _ = evaluate_seven_card_hand(self.dealer_hand)
        return flush_len >= 3 and high_card >= 9

class HighCardFlushGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("高牌同花")
        self.geometry("1350x730+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')
        
        self.username = username
        self.balance = initial_balance
        self.game = HighCardFlushGame()
        self.card_images = {}
        self.animation_queue = []
        self.animation_in_progress = False
        self.card_positions = {}
        self.active_card_labels = []  # 跟踪所有活动中的卡片标签
        self.selected_chip = None  # 当前选中的筹码
        self.chip_buttons = []  # 筹码按钮列表
        self.last_win = 0
        self.auto_reset_timer = None
        self.buttons_disabled = False  # 跟踪按钮是否被禁用
        self.win_details = {
            "ante": 0,
            "play": 0,
            "flush_bonus": 0,
            "straight_flush_bonus": 0,
        }
        self.bet_widgets = {}  # 存储下注显示控件
        self.flush_cards = {"player": [], "dealer": []}  # 存储同花牌标签
        self.highlight_animations = {"player": None, "dealer": None}  # 存储同花牌动画ID

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
        card_size = (100, 150)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 使用实例变量来跟踪当前使用的扑克牌文件夹
        if not hasattr(self, 'current_poker_folder'):
            # 第一次加载时随机选择
            self.current_poker_folder = random.choice(['Poker1', 'Poker2'])
        else:
            # 交替使用 Poker1 和 Poker2
            self.current_poker_folder = 'Poker2' if self.current_poker_folder == 'Poker1' else 'Poker1'
        
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', self.current_poker_folder)
        
        # 花色映射：将符号映射为英文名称
        suit_mapping = {
            '♠': 'Spade',
            '♥': 'Heart',
            '♦': 'Diamond',
            '♣': 'Club'
        }

        self.original_images = {}
        
        # 加载背面图片
        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_img_orig = Image.open(back_path)  # 原始尺寸
            self.original_images["back"] = back_img_orig  # 保存原始图像
            back_img = back_img_orig.resize(card_size)  # 缩放
            self.back_image = ImageTk.PhotoImage(back_img)
        except Exception as e:
            print(f"Error loading back image: {e}")
            # 创建黑色背景
            img_orig = Image.new('RGB', card_size, 'black')
            self.original_images["back"] = img_orig
            self.back_image = ImageTk.PhotoImage(img_orig)
        
        # 加载扑克牌图片
        for suit in SUITS:
            for rank in RANKS:
                # 获取映射后的文件名
                suit_name = suit_mapping.get(suit, suit)
                if suit == 'JOKER':
                    filename = f"JOKER-A.png"  # 鬼牌文件名
                else:
                    filename = f"{suit_name}{rank}.png"
                path = os.path.join(card_dir, filename)
                
                try:
                    if os.path.exists(path):
                        img = Image.open(path)
                        # 保存原始图像
                        self.original_images[(suit, rank)] = img
                        # 创建缩放后的图像用于显示
                        img_resized = img.resize(card_size)
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_resized)
                    else:
                        # 创建占位图片
                        img_orig = Image.new('RGB', card_size, 'blue')
                        draw = ImageDraw.Draw(img_orig)
                        # 绘制卡片文本
                        if suit == 'JOKER':
                            text = "JOKER"
                        else:
                            text = f"{rank}{suit}"
                        try:
                            font = ImageFont.truetype("arial.ttf", 20)
                        except:
                            font = ImageFont.load_default()
                        text_width, text_height = draw.textsize(text, font=font)
                        x = (card_size[0] - text_width) / 2
                        y = (card_size[1] - text_height) / 2
                        draw.text((x, y), text, fill="white", font=font)
                        
                        # 保存原始图像
                        self.original_images[(suit, rank)] = img_orig
                        # 创建缩放后的图像用于显示
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
                except Exception as e:
                    print(f"Error loading card image {path}: {e}")
                    # 创建占位图片
                    img_orig = Image.new('RGB', card_size, 'red')
                    draw = ImageDraw.Draw(img_orig)
                    text = "Error"
                    try:
                        font = ImageFont.truetype("arial.ttf", 20)
                    except:
                        font = ImageFont.load_default()
                    text_width, text_height = draw.textsize(text, font=font)
                    x = (card_size[0] - text_width) / 2
                    y = (card_size[1] - text_height) / 2
                    draw.text((x, y), text, fill="white", font=font)
                    
                    # 保存原始图像
                    self.original_images[(suit, rank)] = img_orig
                    # 创建缩放后的图像用于显示
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)

    def add_chip_to_bet(self, bet_type):
        """添加筹码到下注区域"""
        if not self.selected_chip:
            return
            
        # 获取筹码金额
        chip_value = float(self.selected_chip.replace('$', '').replace('K', '000'))
        
        # 更新对应的下注变量
        if bet_type == "ante":
            current = float(self.ante_var.get())
            self.ante_var.set(str(int(current + chip_value)))
        elif bet_type == "flush_bonus":
            current = float(self.flush_bonus_var.get())
            self.flush_bonus_var.set(str(int(current + chip_value)))
        elif bet_type == "straight_flush_bonus":
            current = float(self.straight_flush_bonus_var.get())
            self.straight_flush_bonus_var.set(str(int(current + chip_value)))
    
    def toggle_play_bet(self, event):
        """切换Play下注状态 - 已移除功能"""
        # 不再允许切换Play下注状态
        pass
    
    def _create_widgets(self):
        # 主框架 - 左右布局
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧牌桌区域 - 使用Canvas提供更好的控制
        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0, width=900, height=650)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 牌桌背景
        table_bg = table_canvas.create_rectangle(0, 0, 900, 650, fill='#35654d', outline='')
        
        # 庄家区域 - 固定高度250
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=50, y=50, width=800, height=270)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 22), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 在庄家和玩家区域之间添加提示文字
        self.ante_info_label = tk.Label(
            table_canvas, 
            text="庄家需至少3张同花\n同时其中一张牌的点数等于大于9才及格", 
            font=('Arial', 28), 
            bg='#35654d', 
            fg='#FFD700'
        )
        self.ante_info_label.place(x=450, y=370, anchor='center')
        
        # 玩家区域 - 固定高度250
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=50, y=420, width=800, height=270)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 22), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 右侧控制面板
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=300, padx=10, pady=10)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 顶部信息栏
        info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=10)
        
        self.balance_label = tk.Label(
            info_frame, 
            text=f"余额: ${self.balance:.2f}",
            font=('Arial', 18),
            bg='#2a4a3c',
            fg='white'
        )
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        self.stage_label = tk.Label(
            info_frame, 
            text="阶段: 下注",
            font=('Arial', 18, 'bold'),
            bg='#2a4a3c',
            fg='#FFD700'
        )
        self.stage_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        # 筹码区域
        chips_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        chips_frame.pack(fill=tk.X, pady=10)
        
        chips_label = tk.Label(chips_frame, text="筹码:", font=('Arial', 18), bg='#2a4a3c', fg='white')
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
        
        # 下注区域 - 重新设计布局
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=10)
        
        # Bonus部分框架
        bonus_frame = tk.LabelFrame(bet_frame, text="边注", font=('Arial', 18, 'bold'), 
                                  bg='#2a4a3c', fg='#FFD700', padx=10, pady=5)
        bonus_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 创建一行放置同花和同花顺
        bonus_row = tk.Frame(bonus_frame, bg='#2a4a3c')
        bonus_row.pack(fill=tk.X, padx=5, pady=5)
        
        # 同花边注
        flush_bonus_frame = tk.Frame(bonus_row, bg='#2a4a3c')
        flush_bonus_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        flush_bonus_label = tk.Label(flush_bonus_frame, text="同花:", font=('Arial', 18), bg='#2a4a3c', fg='white')
        flush_bonus_label.pack(side=tk.LEFT)
        
        self.flush_bonus_var = tk.StringVar(value="0")
        self.flush_bonus_display = tk.Label(flush_bonus_frame, textvariable=self.flush_bonus_var, font=('Arial', 18), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.flush_bonus_display.pack(side=tk.LEFT, padx=5)
        self.flush_bonus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("flush_bonus"))
        self.bet_widgets["flush_bonus"] = self.flush_bonus_display
        
        # 同花顺边注
        straight_flush_bonus_frame = tk.Frame(bonus_row, bg='#2a4a3c')
        straight_flush_bonus_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        straight_flush_bonus_label = tk.Label(straight_flush_bonus_frame, text="同花顺:", font=('Arial', 18), bg='#2a4a3c', fg='white')
        straight_flush_bonus_label.pack(side=tk.LEFT)
        
        self.straight_flush_bonus_var = tk.StringVar(value="0")
        self.straight_flush_bonus_display = tk.Label(straight_flush_bonus_frame, textvariable=self.straight_flush_bonus_var, font=('Arial', 18), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.straight_flush_bonus_display.pack(side=tk.LEFT, padx=5)
        self.straight_flush_bonus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("straight_flush_bonus"))
        self.bet_widgets["straight_flush_bonus"] = self.straight_flush_bonus_display
        
        # Basic部分框架
        basic_frame = tk.LabelFrame(bet_frame, text="基本", font=('Arial', 18, 'bold'), 
                                  bg='#2a4a3c', fg='#FFD700', padx=10, pady=5)
        basic_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 创建一行放置Ante和Play
        basic_row = tk.Frame(basic_frame, bg='#2a4a3c')
        basic_row.pack(fill=tk.X, padx=5, pady=5)
        
        # Ante 部分
        ante_frame = tk.Frame(basic_row, bg='#2a4a3c')
        ante_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        ante_label = tk.Label(ante_frame, text="底注:", font=('Arial', 18), bg='#2a4a3c', fg='white')
        ante_label.pack(side=tk.LEFT)
        
        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(ante_frame, textvariable=self.ante_var, font=('Arial', 18), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.bet_widgets["ante"] = self.ante_display
        
        # Play 部分
        play_frame = tk.Frame(basic_row, bg='#2a4a3c')
        play_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.play_label = tk.Label(play_frame, text="  加注:", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.play_label.pack(side=tk.LEFT)
        
        self.play_var = tk.StringVar(value="0")
        self.play_display = tk.Label(play_frame, textvariable=self.play_var, font=('Arial', 18), 
                                bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.play_display.pack(side=tk.LEFT, padx=5)
        # Play Bet 点击事件 - 已移除功能
        self.play_display.bind("<Button-1>", self.toggle_play_bet)
        self.bet_widgets["play"] = self.play_display
        
        # 添加提示文字
        tip_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        tip_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        tip_label = tk.Label(
            tip_frame, 
            text="庄家不及格 底注赢 加注退还", 
            font=('Arial', 18, 'bold'), 
            bg='#2a4a3c', 
            fg='#FFD700'
        )
        tip_label.pack(side=tk.LEFT)
        
        # 游戏操作按钮框架 - 用于放置所有操作按钮
        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        self.action_frame.pack(fill=tk.X, pady=10)

        # 创建一个框架来容纳重置按钮和开始游戏按钮
        self.start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        self.start_button_frame.pack(pady=5)

        # 添加"重置金额"按钮
        self.reset_bets_button = tk.Button(
            self.start_button_frame, text="重置金额", 
            command=self.reset_bets, font=('Arial', 14),
            bg='#F44336', fg='white', width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))

        # 开始游戏按钮
        self.start_button = tk.Button(
            self.start_button_frame, text="开始游戏", 
            command=self.start_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT)
        
        # 决策按钮框架 (初始隐藏)
        self.decision_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        
        # 状态信息
        self.status_label = tk.Label(
            control_frame, text="设置下注金额并开始游戏", 
            font=('Arial', 18), bg='#2a4a3c', fg='white'
        )
        self.status_label.pack(pady=0, fill=tk.X)  # 减少空隙
        
        # 本局下注和上局获胜金额显示
        bet_info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_info_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(0,0))  # 减少空隙
        
        # 本局下注金额
        self.current_bet_label = tk.Label(
            bet_info_frame, text="本局下注: $0.00", 
            font=('Arial', 18), bg='#2a4a3c', fg='white'
        )
        self.current_bet_label.pack(pady=0, padx=10, anchor='w')
        
        # 上局获胜金额
        self.last_win_label = tk.Label(
            bet_info_frame, text="上局获胜: $0.00", 
            font=('Arial', 18), bg='#2a4a3c', fg='#FFD700'
        )
        self.last_win_label.pack(pady=0, padx=10, anchor='w', side=tk.LEFT)
        
        # 添加游戏规则按钮到上局获胜的右下角
        rules_btn = tk.Button(
            bet_info_frame, text="ℹ️", 
            command=self.show_game_instructions, 
            font=('Arial', 18), bg='#4B8BBE', fg='white', width=2, height=1
        )
        rules_btn.pack(side=tk.RIGHT, padx=10, pady=5)
    
    def show_game_instructions(self):
        """显示游戏规则说明"""
        # 创建自定义弹窗
        win = tk.Toplevel(self)
        win.title("高牌同花游戏规则")
        win.geometry("800x650")
        win.resizable(0,0)
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
        高牌同花 游戏规则

        1. 游戏开始前下注:
           - 底注: 基础下注（必须）
           - 同花边注: 可选下注（根据同花张数赔付）
           - 同花顺边注: 可选下注（根据同花顺张数赔付）

        2. 游戏流程:
           a. 下注阶段:
               - 玩家下注底注
               - 可选择下注同花边注和同花顺边注
               - 点击"开始游戏"按钮开始

           b. 发牌:
               - 玩家和庄家各发七张牌
               - 玩家牌面朝上，庄家牌面朝下（不显示任何牌）

           c. 决策阶段:
               - 玩家查看自己的七张牌后选择:
                 * 弃牌: 输掉底注下注
                 * 下注1倍: 下注金额等于底注
                 * 下注2倍: 下注金额等于底注的2倍（仅当有5张或以上同花）
                 * 下注3倍: 下注金额等于底注的3倍（仅当有6张或以上同花）

           d. 摊牌:
               - 庄家开牌
               - 庄家必须至少3张同花且高牌≥9才合格
               - 结算所有下注

        3. 结算规则:
           - 底注和加注:
             * 如果庄家不合格:
                 - 底注支付1:1
                 - 加注: 退还
             * 如果庄家合格:
                 - 比较玩家和庄家的牌:
                   - 玩家赢: 底注和加注支付1:1
                   - 平局: 底注和加注都退还
                   - 玩家输: 输掉底注和加注
                   
           - 边注:
             * 同花边注: 根据玩家最大同花张数赔付
             * 同花顺边注: 根据玩家最大同花顺张数赔付
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
        
        # 同花边注赔付表
        tk.Label(
            content_frame, 
            text="同花边注赔付表",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')
        
        flush_frame = tk.Frame(content_frame, bg='#F0F0F0')
        flush_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ["同花长度", "赔率"]
        flush_data = [
            ("7张同花", "300:1"),
            ("6张同花", "100:1"),
            ("5张同花", "10:1"),
            ("4张同花", "1:1"),
        ]

        # 表头
        for col, h in enumerate(headers):
            tk.Label(
                flush_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(flush_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    flush_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配每列宽度，让 sticky='nsew' 生效
        for c in range(len(headers)):
            flush_frame.columnconfigure(c, weight=1)
        
        # 同花顺边注赔付表
        tk.Label(
            content_frame, 
            text="同花顺边注赔付表",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')
        
        straight_flush_frame = tk.Frame(content_frame, bg='#F0F0F0')
        straight_flush_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ["同花顺长度", "赔率"]
        straight_flush_data = [
            ("7张同花顺", "8000:1"),
            ("6张同花顺", "1000:1"),
            ("5张同花顺", "100:1"),
            ("4张同花顺", "60:1"),
            ("3张同花顺", "7:1"),
        ]

        # 表头
        for col, h in enumerate(headers):
            tk.Label(
                straight_flush_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(straight_flush_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    straight_flush_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配每列宽度
        for c in range(len(headers)):
            straight_flush_frame.columnconfigure(c, weight=1)
            
        # 注释
        notes = """
        注: 
        * 庄家必须至少3张同花且高牌≥9才合格
        * 加注金额等于底注下注金额的倍数
        * 边注奖励根据玩家手牌支付（无论庄家是否合格）
        """
        
        notes_label = tk.Label(
            content_frame, 
            text=notes,
            font=('微软雅黑', 10),
            bg='#F0F0F0',
            justify=tk.LEFT,
            padx=10,
            pady=10
        )
        notes_label.pack(fill=tk.X, padx=10, pady=5)
        
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
    
    def update_hand_labels(self):
        """更新玩家和庄家的手牌标签显示牌型"""
        # 计算玩家当前牌型
        if self.game.player_hand:
            suit_name, flush_len, _, _, _ = evaluate_seven_card_hand(self.game.player_hand)
            self.player_label.config(text=f"玩家 - {suit_name}{flush_len}张")
        
        # 计算庄家当前牌型（只有在摊牌时）
        if self.game.stage == "showdown" or self.game.folded:
            if self.game.dealer_hand:
                suit_name, flush_len, _, _, _ = evaluate_seven_card_hand(self.game.dealer_hand)
                self.dealer_label.config(text=f"庄家 - {suit_name}{flush_len}张")
    
    def disable_action_buttons(self):
        """禁用所有操作按钮"""
        self.buttons_disabled = True
        for widget in self.action_frame.winfo_children():
            # 只对按钮控件禁用
            if isinstance(widget, tk.Button):
                widget.config(state=tk.DISABLED)
        
    def enable_action_buttons(self):
        """启用所有操作按钮"""
        self.buttons_disabled = False
        for widget in self.action_frame.winfo_children():
            # 只对按钮控件启用
            if isinstance(widget, tk.Button):
                widget.config(state=tk.NORMAL)
    
    def start_game(self):
        try:
            self.ante = int(self.ante_var.get())
            self.flush_bonus = int(self.flush_bonus_var.get())
            self.straight_flush_bonus = int(self.straight_flush_bonus_var.get())
            
            # 检查Ante至少5块
            if self.ante < 5:
                messagebox.showerror("错误", "底注至少需要5块")
                return
                
            # 计算总下注
            total_bet = self.ante + self.flush_bonus + self.straight_flush_bonus
                
            if self.balance < total_bet:
                messagebox.showwarning("警告", "余额不足")
                return
                
            self.balance -= total_bet
            self.update_balance()
            
            # 更新本局下注显示
            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            
            self.game.reset_game()
            self.game.deal_initial()
            self.game.ante = self.ante
            self.game.flush_bonus = self.flush_bonus
            self.game.straight_flush_bonus = self.straight_flush_bonus
            
            # 清除所有卡片
            for widget in self.dealer_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.player_cards_frame.winfo_children():
                widget.destroy()
            
            # 重置动画状态
            self.animation_queue = []
            self.animation_in_progress = False
            self.active_card_labels = []
            
            # 初始化卡片位置
            self.card_positions = {}
            
            # 玩家牌 - 放置在中中心位置
            # 计算每张牌的起始x位置，使得7张牌左对齐显示
            card_width = 106   # 每张牌占据的宽度（包括间隙）
            start_x = 10  # 从左侧50px开始

            for i in range(7):
                card_id = f"player_{i}"
                self.card_positions[card_id] = {
                    "current": (0, 50), 
                    "target": (start_x + i * card_width, 0)
                }
                self.animation_queue.append(card_id)
            
            # 庄家牌 - 同样左对齐
            for i in range(7):
                card_id = f"dealer_{i}"
                self.card_positions[card_id] = {
                    "current": (0, 50), 
                    "target": (start_x + i * card_width, 0)
                }
                self.animation_queue.append(card_id)

            # 隐藏开始按钮，显示决策按钮
            self.start_button_frame.pack_forget()
            
            # 创建决策按钮框架
            self.decision_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
            self.decision_frame.pack(pady=2)
            
            # 创建决策按钮 (初始禁用) —— 四个按钮同一行
            row_frame = tk.Frame(self.decision_frame, bg='#2a4a3c')
            row_frame.pack(pady=3)

            self.fold_button = tk.Button(
                row_frame, text="弃牌",
                command=self.fold_action,
                state=tk.DISABLED,
                font=('Arial', 14), bg='#F44336', fg='white', width=7
            )
            self.fold_button.pack(side=tk.LEFT, padx=5)

            self.bet1x_button = tk.Button(
                row_frame, text="下注1倍",
                command=lambda: self.play_action(1),
                state=tk.DISABLED,
                font=('Arial', 14), bg='#4CAF50', fg='white', width=7
            )
            self.bet1x_button.pack(side=tk.LEFT, padx=5)

            self.bet2x_button = tk.Button(
                row_frame, text="下注2倍",
                command=lambda: self.play_action(2),
                state=tk.DISABLED,
                font=('Arial', 14), bg='#2196F3', fg='white', width=7
            )
            self.bet2x_button.pack(side=tk.LEFT, padx=5)

            self.bet3x_button = tk.Button(
                row_frame, text="下注3倍",
                command=lambda: self.play_action(3),
                state=tk.DISABLED,
                font=('Arial', 14), bg='#FF9800', fg='white', width=7
            )
            self.bet3x_button.pack(side=tk.LEFT, padx=5)

            # 禁用下注区域
            self.ante_display.unbind("<Button-1>")
            self.flush_bonus_display.unbind("<Button-1>")
            self.straight_flush_bonus_display.unbind("<Button-1>")
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")
            
            # 开始动画
            self.animate_deal()
            
        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")
    
    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            # 发牌动画完成后翻开玩家牌
            self.after(500, self.reveal_player_cards)
            return
            
        self.animation_in_progress = True
        card_id = self.animation_queue.pop(0)
        
        # 创建卡片标签
        if card_id.startswith("player"):
            frame = self.player_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.player_hand[idx] if idx < len(self.game.player_hand) else None
        elif card_id.startswith("dealer"):
            frame = self.dealer_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.dealer_hand[idx] if idx < len(self.game.dealer_hand) else None
        
        # 创建卡片标签
        card_label = tk.Label(frame, image=self.back_image, bg='#2a4a3c')
        card_label.place(
            x=self.card_positions[card_id]["current"][0],
            y=self.card_positions[card_id]["current"][1]
        )
        
        # 存储卡片信息
        card_label.card_id = card_id
        card_label.card = card
        card_label.is_face_up = False
        card_label.is_moving = True
        card_label.target_pos = self.card_positions[card_id]["target"]
        
        # 添加到活动卡片列表
        self.active_card_labels.append(card_label)
        
        # 开始移动动画
        self.animate_card_move(card_label)
    
    def animate_card_move(self, card_label):
        # 检查卡片是否仍然存在
        if not hasattr(card_label, "target_pos") or card_label not in self.active_card_labels:
            return
            
        try:
            current_x, current_y = card_label.winfo_x(), card_label.winfo_y()
            target_x, target_y = card_label.target_pos
            
            # 计算移动方向向量
            dx = target_x - current_x
            dy = target_y - current_y
            distance = math.sqrt(dx**2 + dy**2)
            
            # 如果已经到达目标位置
            if distance < 5:
                card_label.place(x=target_x, y=target_y)
                card_label.is_moving = False
                
                # 如果是回收动画且到达左上角，销毁卡片
                if card_label.target_pos == (50, 50):
                    if card_label in self.active_card_labels:
                        self.active_card_labels.remove(card_label)
                    card_label.destroy()
                    
                self.after(100, self.animate_deal)  # 处理下一张牌
                return
            
            # 计算移动步长
            step_x = dx * 0.2
            step_y = dy * 0.2
            
            # 更新位置
            new_x = current_x + step_x
            new_y = current_y + step_y
            card_label.place(x=new_x, y=new_y)
            
            # 继续动画
            self.after(20, lambda: self.animate_card_move(card_label))
            
        except tk.TclError:
            # 卡片已被销毁，停止动画
            if card_label in self.active_card_labels:
                self.active_card_labels.remove(card_label)
            return
    
    def reveal_player_cards(self):
        """翻开玩家牌（带动画）"""
        if self.animation_in_progress:
            return
        
        for i, card_label in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                # 标记玩家牌已翻开
                self.game.cards_revealed["player"][i] = True
        
        # 更新玩家牌型
        self.update_hand_labels()
        
        # 根据同花长度启用相应的下注按钮
        suit_name, flush_len, _, _, _ = evaluate_seven_card_hand(self.game.player_hand)
        
        # 总是启用弃牌和下注1倍按钮
        self.fold_button.config(state=tk.NORMAL)
        self.bet1x_button.config(state=tk.NORMAL)
        
        # 根据同花长度启用其他按钮
        if flush_len >= 5:
            self.bet2x_button.config(state=tk.NORMAL)
        if flush_len >= 6:
            self.bet3x_button.config(state=tk.NORMAL)
        
        # 2秒后下移玩家同花牌
        self.after(2000, lambda: self.highlight_flush_cards("player"))
    
    def flip_card_animation(self, card_label):
        """卡片翻转动画"""
        # 获取卡片正面图像
        card = card_label.card
        front_img = self.card_images.get((card.suit, card.rank), self.back_image)
        
        # 创建动画序列
        self.animate_flip(card_label, front_img, 0)
    
    def animate_flip(self, card_label, front_img, step):
        """执行翻转动画，保持上下高度，水平居中缩放，修复只显示中间一半的问题"""
        steps = 10
        orig_w, orig_h = 96, 144
        if step > steps:
            card_label.is_face_up = True
            self.animation_in_progress = False
            return

        # 计算当前宽度
        if step <= steps // 2:
            w = orig_w * (1 - step / (steps/2))
            img = self.back_image
        else:
            w = orig_w * ((step - steps/2) / (steps/2))
            img = front_img

        w = max(1, int(w))
        # 计算水平偏移，让缩放后图片居中
        tx, ty = card_label.target_pos
        offset = (orig_w - w) // 2

        # 更新图片与位置，并保持原始高度不变
        card_label.config(image=img)
        card_label.place(x=tx + offset, y=ty, width=w, height=orig_h)

        # 下一帧
        self.after(50, lambda: self.animate_flip(card_label, front_img, step+1))

    def play_action(self, bet_multiplier):
        """玩家选择下注"""
        self.fold_button.config(state=tk.DISABLED)
        self.bet1x_button.config(state=tk.DISABLED)
        self.bet2x_button.config(state=tk.DISABLED)
        self.bet3x_button.config(state=tk.DISABLED)

        # 计算下注金额
        play_bet = self.ante * bet_multiplier
        if play_bet > self.balance:
            messagebox.showerror("错误", "余额不足")
            return
            
        # 扣除下注金额
        self.balance -= play_bet
        self.update_balance()
        self.game.play_bet = play_bet
        
        # 更新Play Bet显示
        self.play_var.set(str(play_bet))
        
        # 更新本局下注显示
        total_bet = self.ante + self.flush_bonus + self.straight_flush_bonus + play_bet
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        
        # 结算边注
        flush_win = self.calculate_flush_bonus()
        straight_flush_win = self.calculate_straight_flush_bonus()
        
        # 记录边注赢得的金额
        self.win_details["flush_bonus"] = flush_win
        self.win_details["straight_flush_bonus"] = straight_flush_win
        
        # 进入摊牌阶段
        self.game.stage = "showdown"
        self.stage_label.config(text="阶段: 摊牌")
        self.status_label.config(text="摊牌中...")
        self.after(1000, self.show_showdown)
    
    def fold_action(self):
        self.fold_button.config(state=tk.DISABLED)
        self.bet1x_button.config(state=tk.DISABLED)
        self.bet2x_button.config(state=tk.DISABLED)
        self.bet3x_button.config(state=tk.DISABLED)

        self.game.folded = True
        self.status_label.config(text="您已弃牌 ~ 游戏结束")

        # 保存下注金额用于结算
        ante_bet = int(self.ante_var.get())
        
        # 重置显示金额为0
        self.ante_var.set("0")
        self.play_var.set("0")
        
        # 翻开庄家牌
        self.reveal_dealer_cards()
        
        # 更新庄家牌型
        self.update_hand_labels()
        
        # 计算边注
        flush_win = self.calculate_flush_bonus()
        straight_flush_win = self.calculate_straight_flush_bonus()
        
        # 更新余额
        total_win = flush_win + straight_flush_win
        if total_win > 0:
            self.balance += total_win
            self.update_balance()
        
        # 设置背景色
        self.ante_display.config(bg='white')  # 输
        
        # 计算总赢得金额
        self.last_win = total_win
        
        # 更新上局赢得金额显示
        self.last_win_label.config(text=f"上局获胜: ${total_win:.2f}")
        
        # 构建主消息
        result_text = "本局您选择弃牌"

        self.status_label.config(text=result_text, fg='white')
        
        # 添加重新开始按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()
            
        restart_btn = tk.Button(
            self.action_frame, text="再来一局", 
            command=self.reset_game, 
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
        )
        restart_btn.pack(pady=5)
        restart_btn.bind("<Button-3>", self.show_card_sequence)
        
        # 设置30秒后自动重置
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
    
    def reveal_dealer_cards(self):
        """翻开庄家牌（带动画）"""
        if self.animation_in_progress:
            return
        
        for i, card_label in enumerate(self.dealer_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                # 标记庄家牌已翻开
                self.game.cards_revealed["dealer"][i] = True
        
        # 更新庄家牌型
        self.update_hand_labels()
        
        # 2秒后下移庄家同花牌
        self.after(2000, lambda: self.highlight_flush_cards("dealer"))
    
    def highlight_flush_cards(self, hand_type):
        """高亮显示同花牌并下移20px（带动画）"""
        frame = self.player_cards_frame if hand_type == "player" else self.dealer_cards_frame
        hand = self.game.player_hand if hand_type == "player" else self.game.dealer_hand
        
        # 获取最大同花
        _, _, _, _, flush_cards = evaluate_seven_card_hand(hand)
        
        # 存储同花牌标签
        self.flush_cards[hand_type] = []
        
        # 找到同花牌对应的标签并下移
        for card in flush_cards:
            for card_label in frame.winfo_children():
                if hasattr(card_label, "card") and card_label.card == card:
                    # 初始化目标位置
                    card_label.target_y = card_label.winfo_y() + 20
                    self.flush_cards[hand_type].append(card_label)
                    break
        
        # 启动动画
        self.animate_highlight_cards(hand_type, 0)
    
    def animate_highlight_cards(self, hand_type, step):
        """执行同花牌高亮动画"""
        if step >= 5:  # 10步完成20px移动
            return
            
        for card_label in self.flush_cards[hand_type]:
            if card_label.winfo_exists():  # 确保标签仍然存在
                current_y = card_label.winfo_y()
                new_y = current_y + 4  # 每步移动2px
                card_label.place(y=new_y)
        
        # 继续动画
        self.highlight_animations[hand_type] = self.after(100, lambda: self.animate_highlight_cards(hand_type, step+1))
    
    def reset_highlighted_cards(self):
        """重置高亮牌的位置（上移20px，带动画）"""
        for hand_type in ["player", "dealer"]:
            # 取消可能存在的动画
            if self.highlight_animations[hand_type]:
                self.after_cancel(self.highlight_animations[hand_type])
                self.highlight_animations[hand_type] = None
            
            # 启动复位动画
            self.animate_reset_cards(hand_type, 0)
    
    def animate_reset_cards(self, hand_type, step):
        """执行同花牌复位动画"""
        if step >= 5:  # 10步完成20px移动
            return
            
        for card_label in self.flush_cards[hand_type]:
            if card_label.winfo_exists():  # 确保标签仍然存在
                current_y = card_label.winfo_y()
                new_y = current_y - 4  # 每步移动2px
                card_label.place(y=new_y)
        
        # 继续动画
        self.after(100, lambda: self.animate_reset_cards(hand_type, step+1))
    
    def show_showdown(self):
        # 翻开庄家牌
        self.reveal_dealer_cards()
        
        # 结算
        winnings, details = self.calculate_winnings()
        self.last_win = winnings
        
        # 更新余额
        self.balance += winnings
        self.update_balance()
        
        # 更新下注显示金额
        self.ante_var.set(str(int(details["ante"])))
        self.play_var.set(str(int(details["play"])))
        
        # 设置背景色：赢为金色，平局为浅蓝色，输为白色
        for bet_type in ["ante", "play"]:
            widget = self.bet_widgets.get(bet_type)
            if not widget:
                continue

            # 对应的下注金额
            if bet_type == "ante":
                bet_amount = self.game.ante
            else:  # "play"
                bet_amount = self.game.play_bet
                
            win_amount = details[bet_type]

            # 赢（任何注项赢都染金色）
            if win_amount > bet_amount:  # 赢
                widget.config(bg='gold')
            # 平局并且确实有下注（注金>0）
            elif win_amount == bet_amount and bet_amount > 0:
                widget.config(bg='light blue')
            # 其他情况（输了，或根本没下注）保持白色
            else:
                widget.config(bg='white')
        
        # 构建主消息
        dealer_qualifies = self.game.dealer_qualifies()
        comparison = compare_hands(self.game.player_hand, self.game.dealer_hand)
        
        if not dealer_qualifies:
            base_text = "庄家不合格，退还Play"
        else:
            if comparison > 0:  # 玩家赢
                base_text = "本局您赢了"
            elif comparison < 0:  # 玩家输
                base_text = "本局您输了"
            else:  # 平局
                base_text = "本局Push"
        
        # 组合消息
        result_text = base_text

        self.status_label.config(text=result_text, fg='white')
        
        # 更新上局赢得金额
        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")
        
        # 添加重新开始按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()
            
        restart_btn = tk.Button(
            self.action_frame, text="再来一局", 
            command=self.reset_game, 
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
        )
        restart_btn.pack(pady=5)
        restart_btn.bind("<Button-3>", self.show_card_sequence)
        
        # 设置30秒后自动重置
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
    
    def calculate_winnings(self):
        """计算赢得的金额"""
        winnings = 0
        details = {
            "ante": 0,
            "play": 0,
            "flush_bonus": self.win_details["flush_bonus"],
            "straight_flush_bonus": self.win_details["straight_flush_bonus"],
        }
        
        # 结算边注
        winnings += details["flush_bonus"] + details["straight_flush_bonus"]
        
        # 1. 结算Ante和Play
        dealer_qualifies = self.game.dealer_qualifies()
        comparison = compare_hands(self.game.player_hand, self.game.dealer_hand)
        
        ante_result = 0
        play_result = 0
        
        if not dealer_qualifies:
            # 庄家不合格：Ante支付1:1（即赢Ante下注额），Play退还
            ante_result = self.game.ante * 2   # 赢1倍，加上本金共2倍
            play_result = self.game.play_bet   # 退还Play下注额（即1倍，因为已经扣除，所以加回1倍即可）
        else:
            if comparison > 0:  # 玩家赢
                ante_result = self.game.ante * 2
                play_result = self.game.play_bet * 2
            elif comparison == 0:  # 平局
                ante_result = self.game.ante
                play_result = self.game.play_bet
            else:  # 玩家输
                ante_result = 0
                play_result = 0
        
        winnings += ante_result + play_result
        details["ante"] = ante_result
        details["play"] = play_result
        
        return winnings, details
    
    def calculate_flush_bonus(self):
        """计算同花边注奖金"""
        if self.game.flush_bonus <= 0:
            # 没有下注，不需要处理
            return 0
            
        _, flush_len, _, _, _ = evaluate_seven_card_hand(self.game.player_hand)
        
        if flush_len >= 4:
            payout = FLUSH_BONUS_PAYOUT.get(flush_len, 0)
            win_amount = self.game.flush_bonus * (1 + payout)
            
            # 更新显示：本金+净赢金额
            total_win = win_amount
            self.flush_bonus_var.set(str(total_win))
            
            # 设置背景色为金色
            self.flush_bonus_display.config(bg='gold')
            return win_amount
        else:
            # 未中奖，将金额重置为0
            self.flush_bonus_var.set("0")
            # 设置背景色为白色
            self.flush_bonus_display.config(bg='white')
            return 0
    
    def calculate_straight_flush_bonus(self):
        """计算同花顺边注奖金"""
        if self.game.straight_flush_bonus <= 0:
            # 没有下注，不需要处理
            return 0
            
        _, _, _, straight_flush_len, _, = evaluate_seven_card_hand(self.game.player_hand)
        
        if straight_flush_len >= 3:
            payout = STRAIGHT_FLUSH_BONUS_PAYOUT.get(straight_flush_len, 0)
            win_amount = self.game.straight_flush_bonus * (1 + payout)
            
            # 更新显示：本金+净赢金额
            total_win = win_amount
            self.straight_flush_bonus_var.set(str(total_win))
            
            # 设置背景色为金色
            self.straight_flush_bonus_display.config(bg='gold')
            return win_amount
        else:
            # 未中奖，将金额重置为0
            self.straight_flush_bonus_var.set("0")
            # 设置背景色为白色
            self.straight_flush_bonus_display.config(bg='white')
            return 0
    
    def animate_collect_cards(self, auto_reset):
        """执行收牌动画：先翻转所有牌为背面，然后向中心牌堆位置收起"""
        # 禁用所有按钮
        self.disable_action_buttons()
        
        # 设置动画完成后执行真正的重置
        self.animate_move_cards_out(auto_reset)

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
                # 移除此卡片
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
        # 重新加载资源（切换扑克牌图片）
        self._load_assets()

        # 取消自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        
        # 重置高亮牌的位置
        self.reset_highlighted_cards()
        
        # 如果当前有牌在桌上，先执行收牌动画
        if self.active_card_labels:
            self.disable_action_buttons()  # 禁用按钮
            # 先执行同花牌复位动画
            self.after(1000, lambda: self.animate_collect_cards(auto_reset))
            return

        # 否则直接重置
        self._do_reset(auto_reset)
    
    def reset_bets(self):
        """重置下注金额为0"""
        self.ante_var.set("0")
        self.play_var.set("0")
        self.flush_bonus_var.set("0")
        self.straight_flush_bonus_var.set("0")
        
        # 更新显示
        self.status_label.config(text="已重置所有下注金额")
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 短暂高亮显示重置效果
        self.ante_display.config(bg='#FFCDD2')  # 浅红色
        self.play_display.config(bg='#FFCDD2')  # 浅红色
        self.flush_bonus_display.config(bg='#FFCDD2')  # 浅红色
        self.straight_flush_bonus_display.config(bg='#FFCDD2')  # 浅红色
        self.after(500, lambda: self.ante_display.config(bg='white'))
        self.after(500, lambda: self.play_display.config(bg='white'))
        self.after(500, lambda: self.flush_bonus_display.config(bg='white'))
        self.after(500, lambda: self.straight_flush_bonus_display.config(bg='white'))
    
    def _do_reset(self, auto_reset=False):
        """真正的重置游戏界面"""
        # 重置游戏状态
        self.game.reset_game()
        self.stage_label.config(text="阶段: 下注")
        self.status_label.config(text="设置下注金额并开始游戏")
        
        # 重置标签显示
        self.player_label.config(text="玩家")
        self.dealer_label.config(text="庄家")
        
        # 重置下注金额为0
        self.ante_var.set("0")
        self.play_var.set("0")
        self.flush_bonus_var.set("0")
        self.straight_flush_bonus_var.set("0")
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 清空活动卡片列表（在收牌动画后已清空）
        self.active_card_labels = []
        
        # 恢复下注区域
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.play_display.bind("<Button-1>", self.toggle_play_bet)
        self.flush_bonus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("flush_bonus"))
        self.straight_flush_bonus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("straight_flush_bonus"))
        for chip in self.chip_buttons:
            # 使用存储的文本重新绑定事件
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
        
        # 恢复操作按钮区域
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        
        # 重新显示开始按钮框架
        self.start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        self.start_button_frame.pack(pady=5)

        # 添加"重置金额"按钮
        self.reset_bets_button = tk.Button(
            self.start_button_frame, text="重置金额", 
            command=self.reset_bets, font=('Arial', 14),
            bg='#F44336', fg='white', width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))

        # 开始游戏按钮
        self.start_button = tk.Button(
            self.start_button_frame, text="开始游戏", 
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

    def show_card_sequence(self, event):
        """显示本局牌序窗口 - 右键点击时取消30秒计时"""
        # 取消30秒自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None

        win = tk.Toplevel(self)
        win.title("本局牌序")
        win.geometry("660x600")  # 固定窗口大小
        win.resizable(0, 0)
        win.configure(bg='#f0f0f0')

        # 显示切牌位置
        cut_pos = self.game.cut_position  # 0-based index

        # 显示切牌位置和洗牌方式
        cut_label = tk.Label(
            win,
            text=f"本局切牌位置: {cut_pos + 1}",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0'
        )
        cut_label.pack(pady=(10, 0))  # 减少上边距

        # 创建主框架和滚动条
        main_frame = tk.Frame(win, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main_frame, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)

        # 创建内部框架放置所有内容
        content_frame = tk.Frame(canvas, bg='#f0f0f0')
        canvas.create_window((0, 0), window=content_frame, anchor='nw')

        # 卡片显示框架
        card_frame = tk.Frame(content_frame, bg='#f0f0f0')
        card_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 生成小图
        small_size = (60, 90)
        small_images = {}
        for i, card in enumerate(self.game.card_sequence):
            key = (card.suit, card.rank)
            if key in self.original_images:
                img = self.original_images[key].resize(small_size, Image.LANCZOS)
                small_images[i] = ImageTk.PhotoImage(img)
            else:
                back = self.original_images.get("back")
                if back:
                    img = back.resize(small_size, Image.LANCZOS)
                    small_images[i] = ImageTk.PhotoImage(img)

        total = len(self.game.card_sequence)  # 应该是52
        # 按行显示，每行8张，最后一行可能不足
        for row in range(7):
            row_frame = tk.Frame(card_frame, bg='#f0f0f0')
            row_frame.pack(fill=tk.X, pady=5)
            cards_in_row = 8 if row < 6 else (total - row * 8)

            for col in range(cards_in_row):
                idx = row * 8 + col
                if idx >= total:
                    break

                # 计算距离并取模，以实现"第52张后变第1张"
                dist = (idx - cut_pos) % total
                if 0 <= dist < 7:
                    bg_color = 'light blue'
                elif 7 <= dist < 14:
                    bg_color = 'light pink'
                else:
                    bg_color = '#f0f0f0'

                # 卡片容器
                container = tk.Frame(row_frame, bg=bg_color, borderwidth=1, relief='solid')
                container.grid(row=0, column=col, padx=5, pady=5)

                # 图像或文字
                if idx in small_images:
                    lbl = tk.Label(container, image=small_images[idx], bg=bg_color)
                    lbl.image = small_images[idx]
                else:
                    c = self.game.card_sequence[idx]
                    lbl = tk.Label(container, text=f"{c.rank}{c.suit}", bg=bg_color, width=6, height=3)
                lbl.pack()

                # 序号
                pos = tk.Label(container, text=str(idx + 1), bg=bg_color, font=('Arial', 9))
                pos.pack()

        # 更新滚动区域并绑定滚轮
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

def main(initial_balance=1000, username="Guest"):
    app = HighCardFlushGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    # 独立运行时的示例调用
    final_balance = main()
    print(f"Final balance: {final_balance}")