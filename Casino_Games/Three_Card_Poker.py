import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
import math

# 扑克牌花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    6: '同花顺', 
    5: '三条', 
    4: '顺子', 
    3: '同花', 
    2: '对子', 
    1: '高牌'
}

# Pair Plus支付表 (已修复)
PAIR_PLUS_PAYOUT = {
    6: 40,  # 同花顺 40:1
    5: 30,  # 三条 30:1
    4: 6,   # 顺子 6:1
    3: 3,   # 同花 3:1
    2: 1    # 对子 1:1
}

# Bonus支付表
BONUS_PAYOUT = {
    "black_royal_flush": "赢得整个Jackpot",
    "royal_flush": "赢得Jackpot的10%",
    "straight_flush": "$500",
    "three_of_a_kind": "$400",
    "straight": "$40"
}

# 6 Card支付表
SIX_CARD_PAYOUT = {
    "6_card_super_royal": 100010,  # 6-Card Super Royal
    "royal_flush": 10010,          # 皇家同花顺
    "straight_flush": 2010,        # 同花顺
    "four_of_a_kind": 510,         # 四条
    "full_house": 210,             # 葫芦
    "flush": 160,                  # 同花
    "straight": 110,               # 顺子
    "three_of_a_kind": 60,         # 三条
    "other": 0                     # 其他
}

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

# Jackpot 文件加载与保存
def load_jackpot():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Jackpot.json')
    default_jackpot = 197301.26
    # 文件不存在时使用默认奖池
    if not os.path.exists(path):
        return True, default_jackpot
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item.get('Games') == '3CP':
                    return False, float(item.get('jackpot', default_jackpot))
    except Exception:
        return True, default_jackpot
    # 未找到 UTH 条目时也使用默认
    return True, default_jackpot

def save_jackpot(jackpot):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Jackpot.json')
    data = []
    # 如果文件存在，读取原有数据
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = []
    
    # 查找是否已有UTH的记录
    found = False
    for item in data:
        if item.get('Games') == '3CP':
            item['jackpot'] = jackpot
            found = True
            break
    
    if not found:
        data.append({"Games": "3CP", "jackpot": jackpot})
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.value = RANK_VALUES[rank]
        
    def __repr__(self):
        return f"{self.rank}{self.suit}"

class Deck:
    def __init__(self):
        self.full_deck = [Card(s, r) for s in SUITS for r in RANKS]
        random.shuffle(self.full_deck)
        self.start_pos = random.randint(4, 46)
        self.indexes = [(self.start_pos + i) % 52 for i in range(52)]
        self.pointer = 0

    def deal(self, n=1):
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt

def evaluate_three_card_hand(cards):
    """评估三张牌的手牌"""
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    
    # 检查同花顺
    if len(set(suits)) == 1:
        # A-2-3 顺子 (最小的顺子)
        if values == [14, 3, 2]:
            return (6, [3])  # 最大牌为3
        # 其他顺子
        if values[0] - values[1] == 1 and values[1] - values[2] == 1:
            return (6, [values[0]])   # 返回最大牌
    
    # 检查三条
    if values[0] == values[1] == values[2]:
        return (5, [values[0]])
    
    # 检查顺子
    if values == [14, 3, 2]:  # A-2-3
        return (4, [3])
    if values[0] - values[1] == 1 and values[1] - values[2] == 1:
        return (4, [values[0]])
    
    # 检查同花
    if len(set(suits)) == 1:
        return (3, values)  # 返回所有点数用于比较
    
    # 检查对子
    if values[0] == values[1]:
        # 对子在前两张，第三张是单张
        return (2, [values[0], values[2]])
    elif values[1] == values[2]:
        # 对子在后两张，第一张是单张
        return (2, [values[1], values[0]])
    
    return (1, values)  # 高牌

def compare_hands(hand1, hand2):
    """比较两手牌，返回1表示hand1赢，0表示平局，-1表示hand2赢"""
    rank1, values1 = evaluate_three_card_hand(hand1)
    rank2, values2 = evaluate_three_card_hand(hand2)
    
    if rank1 > rank2:
        return 1
    elif rank1 < rank2:
        return -1
    else:
        # 相同牌型，比较点数
        # 逐个比较每张牌
        for v1, v2 in zip(values1, values2):
            if v1 > v2:
                return 1
            elif v1 < v2:
                return -1
        return 0

class ThreeCardPokerGame:
    def __init__(self):
        self.reset_game()
        # 初始化Jackpot
        self.jackpot_amount = load_jackpot()[1]
        self.initial_jackpot = self.jackpot_amount  # 保存初始值用于重置
    
    def reset_game(self):
        self.deck = Deck()
        self.player_hand = []
        self.dealer_hand = []
        self.ante = 0
        self.pair_plus = 0
        self.play_bet = 0
        self.jackpot_bet = 0  # 新增Jackpot下注
        self.six_card_bet = 0  # 新增6 Card下注
        self.stage = "pre_flop"  # pre_flop, decision, showdown
        self.folded = False
        self.cards_revealed = {
            "player": [False, False, False],
            "dealer": [False, False, False]
        }
    
    def deal_initial(self):
        """发初始牌：玩家3张，庄家3张"""
        self.player_hand = self.deck.deal(3)
        self.dealer_hand = self.deck.deal(3)
    
    def dealer_qualifies(self):
        """庄家是否合格（至少有一张Q高或更好牌型）"""
        # 首先评估庄家牌型
        hand_rank, _ = evaluate_three_card_hand(self.dealer_hand)
        
        # 规则1：如果牌型不是高牌（即有任何特殊牌型），自动合格
        if hand_rank != 1:  # 1 表示高牌
            return True
        
        # 规则2：如果是高牌，检查是否有Q以上牌（Q, K, A）
        max_value = max(card.value for card in self.dealer_hand)
        # Q=12, K=13, A=14
        return max_value >= 12

class ThreeCardPokerGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("Three Card Poker")
        self.geometry("1050x680")
        self.configure(bg='#35654d')
        
        self.username = username
        self.balance = initial_balance
        self.game = ThreeCardPokerGame()
        self.card_images = {}
        self.animation_queue = []
        self.animation_in_progress = False
        self.card_positions = {}
        self.active_card_labels = []  # 追踪所有活动中的卡片标签
        self.selected_chip = None  # 当前选中的筹码
        self.chip_buttons = []  # 筹码按钮列表
        self.last_win = 0
        self.auto_reset_timer = None
        self.buttons_disabled = False  # 跟踪按钮是否被禁用
        self.last_jackpot_state = 0
        self.last_six_card_state = 0  # 新增：保存上局6 Card状态
        self.win_details = {
            "ante": 0,
            "pair_plus": 0,
            "play": 0,
            "bonus": 0,
            "six_card": 0
        }
        self.bet_widgets = {}  # 存储下注显示控件
        self.jackpot_bet_var = tk.IntVar(value=0)  # Jackpot下注变量
        self.six_card_bet_var = tk.IntVar(value=0)  # 6 Card下注变量

        self.six_card_hand_names = {
            "6_card_super_royal": "6张牌超级皇家同花顺",
            "royal_flush": "皇家同花顺",
            "straight_flush": "同花顺",
            "four_of_a_kind": "四条",
            "full_house": "葫芦",
            "flush": "同花",
            "straight": "顺子",
            "three_of_a_kind": "三条",
            "other": "其他"
        }
        
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
        base_dir = os.path.dirname(os.path.abspath(__file__))
        card_dir = os.path.join(base_dir, 'Card')
        
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
        except Exception as e:
            print(f"Error loading back image: {e}")
            # 如果没有背景图，创建一个黑色背景
            img = Image.new('RGB', card_size, 'black')
            self.back_image = ImageTk.PhotoImage(img)
        
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
        elif bet_type == "pair_plus":
            current = float(self.pair_plus_var.get())
            self.pair_plus_var.set(str(int(current + chip_value)))
    
    def _create_widgets(self):
        # 主框架 - 左右布局
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧牌桌区域 - 使用Canvas提供更好的控制
        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 牌桌背景
        table_bg = table_canvas.create_rectangle(0, 0, 800, 600, fill='#35654d', outline='')
        
        # 庄家区域 - 固定高度200
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=50, y=50, width=500, height=230)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 在庄家和玩家区域之间添加提示文字
        self.ante_info_label = tk.Label(
            table_canvas, 
            text="庄家玩高牌Q或以上", 
            font=('Arial', 20), 
            bg='#35654d', 
            fg='#FFD700'
        )

        # 更新以便获取宽度
        self.ante_info_label.update_idletasks()
        label_width = self.ante_info_label.winfo_width()

        # 获取 canvas 宽度
        table_canvas.update_idletasks()
        canvas_width = table_canvas.winfo_width()

        # 居中放置在庄家和玩家区域之间
        center_x = (canvas_width - label_width) // 2
        self.ante_info_label.place(relx=0.5, y=300, anchor='n')
        
        # 玩家区域 - 固定高度200
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=50, y=350, width=500, height=230)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 18), bg='#2a4a3c', fg='white')
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
        
        # Jackpot显示区域
        jackpot_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        jackpot_frame.pack(fill=tk.X, pady=10)
        
        # 创建一个内部框架用于居中
        jackpot_inner_frame = tk.Frame(jackpot_frame, bg='#2a4a3c')
        jackpot_inner_frame.pack(expand=True, pady=5)  # 使用expand和居中
        
        jackpot_label = tk.Label(jackpot_inner_frame, text="Jackpot:", 
                                font=('Arial', 18), bg='#2a4a3c', fg='gold')
        jackpot_label.pack(side=tk.LEFT, padx=(0, 5))  # 右侧留5像素间距
        
        self.jackpot_var = tk.StringVar()
        self.jackpot_var.set(f"${self.game.jackpot_amount:.2f}")
        self.jackpot_display = tk.Label(jackpot_inner_frame, textvariable=self.jackpot_var, 
                                    font=('Arial', 18, 'bold'), bg='#2a4a3c', fg='gold')
        self.jackpot_display.pack(side=tk.LEFT)
        
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
        
        # 下注区域
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=10)
        
        # Jackpot和6 Card下注区域 - 放在同一行
        bonus_bet_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        bonus_bet_frame.pack(fill=tk.X, padx=20, pady=5)
        
        # Jackpot下注
        self.jackpot_check = tk.Checkbutton(
            bonus_bet_frame, 
            text="Jackpot ($1)", 
            variable=self.jackpot_bet_var,
            font=('Arial', 12), 
            bg='#2a4a3c', 
            fg='white', 
            selectcolor='black'
        )
        self.jackpot_check.pack(side=tk.LEFT)
        
        # 6 Card下注 - 放在Jackpot旁边
        self.six_card_check = tk.Checkbutton(
            bonus_bet_frame, 
            text="6 Card ($10)", 
            variable=self.six_card_bet_var,
            font=('Arial', 12), 
            bg='#2a4a3c', 
            fg='white', 
            selectcolor='black',
            command=self.update_six_card_bet
        )
        self.six_card_check.pack(side=tk.LEFT, padx=(20, 0))  # 左边留20像素间距
        
        # 创建一行放置Ante和Pair Plus
        ante_pair_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        ante_pair_frame.pack(fill=tk.X, padx=20, pady=5)
        
        # Ante 区域（左侧）
        ante_frame = tk.Frame(ante_pair_frame, bg='#2a4a3c')
        ante_frame.pack(side=tk.LEFT, padx=(0, 20))  # 右侧留出间距
        
        ante_label = tk.Label(ante_frame, text="Ante:", font=('Arial', 12), bg='#2a4a3c', fg='white')
        ante_label.pack(side=tk.LEFT)
        
        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(ante_frame, textvariable=self.ante_var, font=('Arial', 12), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.bet_widgets["ante"] = self.ante_display
        
        # Pair Plus 区域（右侧）
        pair_plus_frame = tk.Frame(ante_pair_frame, bg='#2a4a3c')
        pair_plus_frame.pack(side=tk.LEFT)
        
        pair_plus_label = tk.Label(pair_plus_frame, text="Pair Plus:", font=('Arial', 12), bg='#2a4a3c', fg='white')
        pair_plus_label.pack(side=tk.LEFT)
        
        self.pair_plus_var = tk.StringVar(value="0")
        self.pair_plus_display = tk.Label(pair_plus_frame, textvariable=self.pair_plus_var, font=('Arial', 12), 
                                        bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.pair_plus_display.pack(side=tk.LEFT, padx=5)
        self.pair_plus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("pair_plus"))
        self.bet_widgets["pair_plus"] = self.pair_plus_display
        
        # Bet 区域（单独一行）
        self.play_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        self.play_frame.pack(fill=tk.X, padx=20, pady=5)
        
        self.play_label = tk.Label(self.play_frame, text="  Bet:", font=('Arial', 12), bg='#2a4a3c', fg='white')
        self.play_label.pack(side=tk.LEFT)
        
        self.play_var = tk.StringVar(value="0")
        self.play_display = tk.Label(self.play_frame, textvariable=self.play_var, font=('Arial', 12), 
                                   bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.play_display.pack(side=tk.LEFT, padx=5)
        # Play Bet 不能手动添加筹码，只能通过"下注Play"按钮设置
        self.bet_widgets["play"] = self.play_display
        
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
            font=('Arial', 12), bg='#2a4a3c', fg='white'
        )
        self.status_label.pack(pady=5, fill=tk.X)
        
        # 结果展示
        self.result_label = tk.Label(
            control_frame, text="", 
            font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='white', justify='center'
        )
        self.result_label.pack(pady=5, fill=tk.X)
        
        # 本局下注和上局获胜金额显示
        bet_info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_info_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 本局下注金额
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
    
    def update_six_card_bet(self):
        """更新6 Card下注状态"""
        if self.six_card_bet_var.get() == 1:
            # 如果勾选，确保下注金额为10
            self.six_card_bet_var.set(1)
        else:
            self.six_card_bet_var.set(0)
    
    def show_game_instructions(self):
        """显示游戏规则说明"""
        # 创建自定义弹窗
        win = tk.Toplevel(self)
        win.title("三张牌扑克游戏规则")
        win.geometry("800x650")
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
        Three Card Poker 游戏规则

        1. 游戏开始前下注:
           - Ante: 基础下注（必须）
           - Pair Plus: 可选副注（支付表见下方）
           - Jackpot: 可选$1下注（参与Bonus奖励）
           - 6 Card: 可选$10下注（参与6张牌组合奖励）

        2. 游戏流程:
           a. 下注阶段:
               - 玩家下注Ante和可选的Pair Plus
               - 可选择下注$1参与Jackpot奖金
               - 可选择下注$10参与6 Card奖金
               - 点击"开始游戏"按钮开始

           b. 发牌:
               - 玩家和庄家各发三张牌
               - 玩家牌面朝上，庄家牌面朝下

           c. 决策阶段:
               - 玩家查看自己的三张牌后选择:
                 * 弃牌: 输掉Ante下注，但Pair Plus和Bonus可能赢
                 * 下注Bet: 下注金额等于Ante

           d. 摊牌:
               - 庄家开牌
               - 庄家必须有一张Q高或更好才合格
               - 结算所有下注

        3. 结算规则:
           - Pair Plus:
             * 根据玩家的三张牌支付（无论庄家是否合格）
             * 支付表见下方
           
           - Ante和Bet:
             * 如果庄家不合格:
                 - Ante: 支付1:1
                 - Bet: 退还
             * 如果庄家合格:
                 - 比较玩家和庄家的牌:
                   - 玩家赢: Ante和Bet都支付1:1
                   - 平局: Ante和Bet都退还
                   - 玩家输: 输掉Ante和Bet
                   
           - Bonus (需下注Jackpot):
             * 根据玩家手牌支付（无论庄家是否合格）
             * 支付表见下方
             
           - 6 Card (需下注$10):
             * 将玩家和庄家的6张牌组合
             * 选出最好的5张牌组合
             * 根据牌型支付（支付表见下方）
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
        
        # Pair Plus支付表
        tk.Label(
            content_frame, 
            text="Pair Plus 支付表",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')
        
        odds_frame = tk.Frame(content_frame, bg='#F0F0F0')
        odds_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ["牌型", "赔率"]
        odds_data = [
            ("同花顺", "40:1"),
            ("三条", "30:1"),
            ("顺子", "6:1"),
            ("同花", "3:1"),
            ("对子", "1:1")
        ]

        # 表头
        for col, h in enumerate(headers):
            tk.Label(
                odds_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(odds_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    odds_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配每列宽度，让 sticky='nsew' 生效
        for c in range(len(headers)):
            odds_frame.columnconfigure(c, weight=1)
        # 可选：也给行设置权重，支持垂直拉伸
        for r in range(len(odds_data) + 1):
            odds_frame.rowconfigure(r, weight=1)
            
        # Bonus支付表
        tk.Label(
            content_frame, 
            text="Bonus 支付表 (需下注Jackpot)",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')
        
        bonus_frame = tk.Frame(content_frame, bg='#F0F0F0')
        bonus_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ["牌型", "奖励"]
        bonus_data = [
            ("黑桃同花大顺 (QKA♠)", "赢得整个Jackpot"),
            ("同花大顺 (QKA其他花色)", "赢得Jackpot的10%"),
            ("同花顺", "$500"),
            ("三条", "$400"),
            ("顺子", "$40")
        ]

        # 表头
        for col, h in enumerate(headers):
            tk.Label(
                bonus_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(bonus_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    bonus_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配每列宽度
        for c in range(len(headers)):
            bonus_frame.columnconfigure(c, weight=1)
            
        # 6 Card支付表
        tk.Label(
            content_frame, 
            text="6 Card 支付表 (需下注$10)",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')
        
        six_card_frame = tk.Frame(content_frame, bg='#F0F0F0')
        six_card_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ["牌型", "赔率"]
        six_card_data = [
            ("6-Card Super Royal (9–A同花顺)", "10,000:1"),
            ("皇家同花顺 (Royal Flush)", "1,000:1"),
            ("同花顺 (Straight Flush)", "200:1"),
            ("四条 (Four of a Kind)", "50:1"),
            ("葫芦 (Full House)", "20:1"),
            ("同花 (Flush)", "15:1"),
            ("顺子 (Straight)", "10:1"),
            ("三条 (Three of a Kind)", "5:1")
        ]

        # 表头
        for col, h in enumerate(headers):
            tk.Label(
                six_card_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(six_card_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    six_card_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配每列宽度
        for c in range(len(headers)):
            six_card_frame.columnconfigure(c, weight=1)
        
        # 注释
        notes = """
        注: 
        * Pair Plus 下注独立于主游戏结算，只取决于玩家的三张牌
        * 庄家必须至少有一张Q高才合格
        * Bet 金额等于Ante下注金额
        * Bonus奖励需要下注Jackpot($1)才有效
        * 6 Card奖励需要下注$10才有效
        * 黑桃同花大顺赢得整个Jackpot后，Jackpot将重置为初始值
        * 其他花色的同花大顺赢得当前Jackpot的10%
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
            player_eval = evaluate_three_card_hand(self.game.player_hand)
            player_hand_name = HAND_RANK_NAMES[player_eval[0]] if player_eval else ""
            self.player_label.config(text=f"玩家 - {player_hand_name}" if player_hand_name else "玩家")
        
        # 计算庄家当前牌型（只有在摊牌时）
        if self.game.stage == "showdown" or self.game.folded:
            if self.game.dealer_hand:
                dealer_eval = evaluate_three_card_hand(self.game.dealer_hand)
                dealer_hand_name = HAND_RANK_NAMES[dealer_eval[0]] if dealer_eval else ""
                self.dealer_label.config(text=f"庄家 - {dealer_hand_name}" if dealer_hand_name else "庄家")
    
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
            self.ante = int(self.ante_var.get())
            self.pair_plus = int(self.pair_plus_var.get())
            self.jackpot_bet = self.jackpot_bet_var.get()  # 获取Jackpot下注
            self.six_card_bet = self.six_card_bet_var.get() * 10  # 获取6 Card下注 (固定$10)
            self.last_jackpot_state = self.jackpot_bet_var.get()   
            self.last_six_card_state = self.six_card_bet_var.get()  # 保存6 Card状态
            
            # 检查Ante至少5块
            if self.ante < 5 and self.pair_plus < 5:  # 修改这里：改为检查两者总和
                messagebox.showerror("错误", "Ante或Pair Plus至少需要5块")
                return
                
            # 计算总下注
            total_bet = self.ante + self.pair_plus + self.jackpot_bet + self.six_card_bet
                
            if self.balance < total_bet + self.ante:
                messagebox.showwarning("警告", "余额不足以支付Bet")
                return
                
            self.balance -= total_bet
            self.update_balance()
            
            # 更新本局下注显示
            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            
            self.game.reset_game()
            self.game.deal_initial()
            self.game.ante = self.ante
            self.game.pair_plus = self.pair_plus
            self.game.jackpot_bet = self.jackpot_bet  # 保存Jackpot下注
            self.game.six_card_bet = self.six_card_bet  # 保存6 Card下注
            
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
            
            # 添加所有卡片到动画队列
            self.animation_queue = []
            
            # 玩家牌 - 放置在中心位置
            for i in range(3):
                card_id = f"player_{i}"
                self.card_positions[card_id] = {
                    "current": (50, 50), 
                    "target": (i * 120, 0)  # 水平排列
                }
                self.animation_queue.append(card_id)
            
            # 庄家牌 - 放置在中心位置
            for i in range(3):
                card_id = f"dealer_{i}"
                self.card_positions[card_id] = {
                    "current": (50, 50), 
                    "target": (i * 120, 0)  # 水平排列
                }
                self.animation_queue.append(card_id)
            
            # 开始动画
            self.animate_deal()
            
            # 更新游戏状态
            self.stage_label.config(text="阶段: 决策")
            self.status_label.config(text="做出决策: 弃牌或下注Bet")

            # 如果Ante为0，则跳过决策阶段
            if self.ante == 0:  # 添加这个判断
                # 直接进入摊牌阶段
                self.game.stage = "showdown"
                self.stage_label.config(text="阶段: 摊牌")
                self.status_label.config(text="摊牌中...")
                self.after(5000, self.show_showdown)
                
                # 不需要创建决策按钮
                return
            
            # 创建操作按钮 - 替换开始按钮
            for widget in self.action_frame.winfo_children():
                widget.destroy()
                
            action_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
            action_button_frame.pack(pady=10)

            self.fold_button = tk.Button(
                action_button_frame, text="弃牌",
                command=self.fold_action,
                font=('Arial', 14), bg='#F44336', fg='white', width=10
            )
            self.fold_button.pack(side=tk.LEFT, padx=(0, 10))

            self.play_button = tk.Button(
                action_button_frame, text="下注Bet",
                command=self.play_action,
                font=('Arial', 14), bg='#4CAF50', fg='white', width=10
            )
            self.play_button.pack(side=tk.LEFT)
            
            # 禁用下注区域
            self.ante_display.unbind("<Button-1>")
            self.pair_plus_display.unbind("<Button-1>")
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")
            
            # 禁用Jackpot和6 Card的Checkbutton
            self.jackpot_check.config(state=tk.DISABLED)
            self.six_card_check.config(state=tk.DISABLED)
            
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
            y=self.card_positions[card_id]["current"][1] + 20
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
        for i, card_label in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                # 标记玩家牌已翻开
                self.game.cards_revealed["player"][i] = True
        
        # 更新玩家牌型
        self.update_hand_labels()
    
    def reveal_dealer_cards(self):
        """翻开庄家牌（带动画）"""
        for i, card_label in enumerate(self.dealer_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                # 标记庄家牌已翻开
                self.game.cards_revealed["dealer"][i] = True
        
        # 更新庄家牌型
        self.update_hand_labels()
    
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
        
        if step <= steps // 2:
            # 第一阶段：从背面翻转到侧面（宽度减小）
            width = 100 - (step * 20)
            if width <= 0:
                width = 1
            # 创建缩放后的背面图像
            back_img = Image.new('RGBA', (width, 140), (0, 0, 0, 0))
            orig_back = self.back_image
            # 这里简化处理，实际应该缩放图片
            card_label.config(image=orig_back)
        else:
            # 第二阶段：从侧面翻转到正面（宽度增加）
            width = (step - steps // 2) * 20
            if width <= 0:
                width = 1
            # 创建缩放后的正面图像
            card_label.config(image=front_img)
        
        # 更新卡片显示
        card_label.place(width=width)
        
        # 下一步
        step += 1
        card_label.after(50, lambda: self.animate_flip(card_label, front_img, step))
    
    def play_action(self):
        """玩家选择下注Bet"""
        # Bet下注等于Ante
        play_bet = self.game.ante
        
        if play_bet > self.balance:
            messagebox.showerror("错误", "余额不足")
            return
            
        self.balance -= play_bet
        self.update_balance()
        self.game.play_bet = play_bet
        
        # 更新Play Bet显示
        self.play_var.set(str(play_bet))
        
        # 更新本局下注显示
        total_bet = self.ante + self.pair_plus + play_bet + self.jackpot_bet + self.six_card_bet
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        
        # 进入摊牌阶段
        self.game.stage = "showdown"
        self.stage_label.config(text="阶段: 摊牌")
        self.status_label.config(text="摊牌中...")
        self.after(1000, self.show_showdown)
    
    def fold_action(self):
        self.game.folded = True
        self.status_label.config(text="您已弃牌 ~ 游戏结束")

        # 保存下注金额用于结算
        ante_bet = int(self.ante_var.get())
        pair_plus_bet = int(self.pair_plus_var.get())
        
        # 重置显示金额为0
        self.ante_var.set("0")
        self.play_var.set("0")
        
        # 翻开庄家牌
        self.reveal_dealer_cards()
        
        # 更新庄家牌型
        self.update_hand_labels()
        
        # 结算Pair Plus (已修复)
        player_eval = evaluate_three_card_hand(self.game.player_hand)
        pair_plus_win = 0
        if player_eval[0] in PAIR_PLUS_PAYOUT:
            payout = PAIR_PLUS_PAYOUT[player_eval[0]]
            # 修正：包括本金返还
            pair_plus_win = pair_plus_bet * (payout + 1)
            self.balance += pair_plus_win
            self.update_balance()
            self.pair_plus_var.set(str(int(pair_plus_win)))
        
        # 结算Bonus (如果下注了Jackpot)
        bonus_win = 0
        bonus_text = ""
        if self.game.jackpot_bet:
            bonus_win = self.calculate_bonus()
            if bonus_win > 0:
                self.balance += bonus_win
                self.update_balance()
                player_hand_type = HAND_RANK_NAMES.get(player_eval[0], "高牌")
                bonus_text = f"恭喜中了JP大奖${bonus_win:.2f} ~ 牌型{player_hand_type}"
        
        # 结算6 Card (如果下注了)
        six_card_win = 0
        six_card_text = ""
        if self.game.six_card_bet:
            six_card_win = self.calculate_six_card_bonus()
            if six_card_win > 0:
                self.balance += six_card_win
                self.update_balance()
                # 获取6张牌的最佳牌型
                _, hand_type = self.get_best_six_card_hand_type()
                six_card_text = f"恭喜中了6 Card大奖${six_card_win:.2f} ~ 牌型{hand_type}"
        
        # 更新Jackpot彩池
        self.update_jackpot(0, 0, ante_bet, 0, 0)
        
        # 设置背景色
        self.ante_display.config(bg='white')  # 输
        self.pair_plus_display.config(bg='gold' if pair_plus_win > 0 else 'white')
        
        # 计算总赢取金额（不包括输掉的Ante）
        total_win = pair_plus_win + bonus_win + six_card_win
        self.last_win = total_win
        
        # 更新上局获胜金额显示
        self.last_win_label.config(text=f"上局获胜: ${total_win:.2f}")
        
        # 构建主消息
        result_text = "本局您选择弃牌"
        
        # 添加中奖信息
        if bonus_text and six_card_text:
            result_text = bonus_text + "\n" + six_card_text
        elif bonus_text:
            result_text = bonus_text
        elif six_card_text:
            result_text = six_card_text

        self.result_label.config(text=result_text, fg='white')
        
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
        
    def get_best_six_card_hand_type(self):
        all_cards = self.game.player_hand + self.game.dealer_hand

        if self.is_six_card_super_royal(all_cards):
            # 返回中文牌型名称
            return SIX_CARD_PAYOUT["6_card_super_royal"] * (self.game.six_card_bet / 10), "6张牌超级皇家同花顺"

        best_value, best_name = self.evaluate_best_five_card_hand(all_cards)
        # 将英文牌型名称转换为中文
        chinese_name = self.six_card_hand_names.get(best_name, best_name)
        return best_value, chinese_name
        
    def show_showdown(self):
        # 翻开庄家牌
        self.reveal_dealer_cards()
        
        # 更新庄家牌型
        self.update_hand_labels()
        
        # 结算
        winnings, details = self.calculate_winnings()
        self.last_win = winnings
        
        # 更新余额
        self.balance += winnings
        self.update_balance()
        
        # 更新下注显示金额
        self.ante_var.set(str(int(details["ante"])))
        self.pair_plus_var.set(str(int(details["pair_plus"])))
        self.play_var.set(str(int(details["play"])))
        
        # 设置背景色：赢为金色，平局为浅蓝色，输为白色
        for bet_type in ["ante", "pair_plus", "play"]:
            widget = self.bet_widgets.get(bet_type)
            if not widget:
                continue

            # 对应的下注金额，如果是 play（Bet），取 self.game.play_bet
            bet_amount = (
                self.game.play_bet if bet_type == "play"
                else getattr(self.game, bet_type)
            )
            win_amount = details[bet_type]

            # 赢（任何注项赢都染金色）
            if details[bet_type] > 0 and details[bet_type] != self.game.ante:  # 赢
                widget.config(bg='gold')
            # 平局且确实有下注（注额>0）
            elif win_amount == bet_amount and bet_amount > 0:
                widget.config(bg='light blue')
            # 其他情况（输了，或根本没下注）都保持白色
            else:
                widget.config(bg='white')
        
        # 构建主消息
        dealer_qualifies = self.game.dealer_qualifies()
        comparison = compare_hands(self.game.player_hand, self.game.dealer_hand)
        
        if not dealer_qualifies:
            base_text = "本局您赢了"
        else:
            if comparison > 0:  # 玩家赢
                if dealer_qualifies != True:
                    base_text = "本局Ante退还"
                else:
                    base_text = "本局您赢了"
            elif comparison < 0:  # 玩家输
                base_text = "本局您输了"
            else:  # 平局
                base_text = "本局Push"
        
        # 获取Bonus和6 Card的中奖信息
        bonus_win = details["bonus"]
        six_card_win = details["six_card"]
        bonus_text = ""
        six_card_text = ""
        
        if bonus_win > 0:
            player_eval = evaluate_three_card_hand(self.game.player_hand)
            player_hand_type = HAND_RANK_NAMES.get(player_eval[0], "高牌")
            bonus_text = f"恭喜中了JP大奖${bonus_win:.2f}~ 牌型{player_hand_type}"
        
        if six_card_win > 0:
            # 获取6张牌的最佳牌型
            _, hand_type = self.get_best_six_card_hand_type()
            six_card_text = f"恭喜中了6 Card大奖${six_card_win:.2f} ~ 牌型{hand_type}"
        
        # 组合消息
        result_text = base_text
        if bonus_text and six_card_text:
            result_text = bonus_text + "\n" + six_card_text
        elif bonus_text:
            result_text = bonus_text
        elif six_card_text:
            result_text = six_card_text

        self.result_label.config(text=result_text, fg='white')
        self.status_label.config(text="游戏结束")
        
        # 更新上局获胜金额
        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")
        
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
    
    def calculate_winnings(self):
        """计算赢得的金额 (已修复)"""
        winnings = 0
        details = {
            "ante": 0,
            "pair_plus": 0,
            "play": 0,
            "bonus": 0,
            "six_card": 0
        }
        bonus_win = 0
        six_card_win = 0
        
        # 1. 结算Pair Plus (已修复)
        player_eval = evaluate_three_card_hand(self.game.player_hand)
        if player_eval[0] in PAIR_PLUS_PAYOUT:
            payout = PAIR_PLUS_PAYOUT[player_eval[0]]
            pair_plus_win = self.game.pair_plus * (payout + 1)
            winnings += pair_plus_win
            details["pair_plus"] = pair_plus_win
        
        # 2. 结算Ante和Bet
        dealer_qualifies = self.game.dealer_qualifies()
        comparison = compare_hands(self.game.player_hand, self.game.dealer_hand)
        
        ante_result = 0
        play_result = 0
        
        if not dealer_qualifies:
            # 庄家不合格：Ante支付1:1，Play退还
            ante_result = self.game.ante
            if comparison > 0:
                play_result = self.game.play_bet* 2
            elif comparison == 0:
                play_result = self.game.play_bet
            else:
                play_result = 0
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
        
        # 3. 结算Bonus (如果下注了Jackpot)
        if self.game.jackpot_bet:
            bonus_win = self.calculate_bonus()
            winnings += bonus_win
            details["bonus"] = bonus_win
        
        # 4. 结算6 Card (如果下注了)
        if self.game.six_card_bet:
            six_card_win = self.calculate_six_card_bonus()
            winnings += six_card_win
            details["six_card"] = six_card_win
        
        # 5. 更新Jackpot彩池
        self.update_jackpot(winnings, details["ante"], self.game.ante, details["play"], self.game.play_bet)
        
        return winnings, details
    
    def update_jackpot(self, winnings, ante_win, ante_bet, play_win, play_bet):
        """更新Jackpot彩池金额"""
        # 计算本局贡献: (获胜金额 * 0.01 + Push金额 * 0.05 + 输的金额 * 0.1)
        # 获胜金额 = 玩家赢得的净盈利（不包括本金）
        win_amount = winnings - (ante_bet + self.game.pair_plus + play_bet + self.game.jackpot_bet + self.game.six_card_bet)
        
        # Push金额 = 平局时退还的本金部分
        push_amount = 0
        if ante_win == ante_bet:  # Ante平局
            push_amount += ante_bet
        if play_win == play_bet:  # Bet平局
            push_amount += play_bet
        
        # 输的金额 = 输掉的下注金额
        loss_amount = 0
        if ante_win == 0:  # Ante输
            loss_amount += ante_bet
        if play_win == 0:  # Bet输
            loss_amount += play_bet
        
        # 计算贡献值
        jackpot_contribution = (win_amount * 0.01) + (push_amount * 0.05) + (loss_amount * 0.1)
        
        # 更新Jackpot金额
        self.game.jackpot_amount += jackpot_contribution
        self.jackpot_var.set(f"${self.game.jackpot_amount:.2f}")
        
        # 保存到文件
        save_jackpot(self.game.jackpot_amount)
    
    def calculate_bonus(self):
        """计算Bonus奖励"""
        cards = self.game.player_hand
        values = sorted([c.value for c in cards], reverse=True)
        suits = [c.suit for c in cards]
        
        # 检查是否黑桃同花大顺 (Q-K-A 黑桃)
        if values == [14, 13, 12] and len(set(suits)) == 1 and suits[0] == '♠':
            bonus = self.game.jackpot_amount
            # 重置Jackpot为初始值
            self.game.jackpot_amount = self.game.initial_jackpot
            self.jackpot_var.set(f"${self.game.jackpot_amount:.2f}")
            save_jackpot(self.game.jackpot_amount)
            return bonus
        
        # 检查是否同花大顺 (Q-K-A 其他花色)
        if values == [14, 13, 12] and len(set(suits)) == 1:
            return self.game.jackpot_amount * 0.1
        
        # 检查其他牌型
        hand_rank, _ = evaluate_three_card_hand(cards)
        
        if hand_rank == 6:  # 同花顺
            return 500
        elif hand_rank == 5:  # 三条
            return 400
        elif hand_rank == 4:  # 顺子
            return 40
        
        return 0
    
    def calculate_six_card_bonus(self):
        all_cards = self.game.player_hand + self.game.dealer_hand

        # 先检查6-Card Super Royal
        if self.is_six_card_super_royal(all_cards):
            return SIX_CARD_PAYOUT["6_card_super_royal"] * (self.game.six_card_bet / 10)

        # 其余牌型：直接解包
        best_value, _ = self.evaluate_best_five_card_hand(all_cards)
        return best_value * (self.game.six_card_bet / 10)
        
    def is_six_card_super_royal(self, cards):
        """检查是否是6-Card Super Royal (9-10-J-Q-K-A 同花顺)"""
        # 首先检查花色是否全部相同
        suits = set(card.suit for card in cards)
        if len(suits) != 1:
            return False
        
        # 检查是否包含9-10-J-Q-K-A
        required_ranks = {9, 10, 11, 12, 13, 14}  # 对应9,10,J,Q,K,A
        card_ranks = set(card.value for card in cards)
        
        return card_ranks == required_ranks
    
    def evaluate_best_five_card_hand(self, cards):
        """评估6张牌中最好的5张牌组合，返回 (最佳支付值, 牌型名称)"""
        from itertools import combinations

        best_value = 0
        best_name = "other"
        # 遍历所有5张组合
        for combo in combinations(cards, 5):
            val = self.evaluate_five_card_hand(list(combo))
            if val > best_value:
                best_value = val
                # 根据 payout 表反查牌型名称
                for name, payout in SIX_CARD_PAYOUT.items():
                    if payout == val:
                        best_name = name
                        break

        return best_value, best_name
        
    def evaluate_five_card_hand(self, cards):
        """评估5张牌的牌型"""
        # 按点数排序
        values = sorted([c.value for c in cards], reverse=True)
        suits = [c.suit for c in cards]
        
        # 检查同花
        is_flush = len(set(suits)) == 1
        
        # 检查顺子
        is_straight = True
        for i in range(1, 5):
            if values[i] != values[i-1] - 1:
                is_straight = False
                break
        
        # 检查皇家同花顺 (10-J-Q-K-A)
        is_royal = is_straight and values[0] == 14 and values[4] == 10
        
        # 检查同花顺
        if is_flush and is_straight:
            if is_royal:
                return SIX_CARD_PAYOUT["royal_flush"]
            return SIX_CARD_PAYOUT["straight_flush"]
        
        # 检查四条
        if values[0] == values[3] or values[1] == values[4]:
            return SIX_CARD_PAYOUT["four_of_a_kind"]
        
        # 检查葫芦 (三条+对子)
        if (values[0] == values[2] and values[3] == values[4]) or \
           (values[0] == values[1] and values[2] == values[4]):
            return SIX_CARD_PAYOUT["full_house"]
        
        # 检查同花
        if is_flush:
            return SIX_CARD_PAYOUT["flush"]
        
        # 检查顺子
        if is_straight:
            return SIX_CARD_PAYOUT["straight"]
        
        # 检查三条
        if values[0] == values[2] or values[1] == values[3] or values[2] == values[4]:
            return SIX_CARD_PAYOUT["three_of_a_kind"]
        
        return SIX_CARD_PAYOUT["other"]

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
        
        # 收集所有需要翻转的卡片
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
        """重置Trips和Ante的投注金额为0"""
        self.ante_var.set("0")
        self.pair_plus_var.set("0")
        
        # 更新显示
        self.status_label.config(text="已重置所有下注金额")
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 短暂高亮显示重置效果
        self.ante_display.config(bg='#FFCDD2')  # 浅红色
        self.pair_plus_display.config(bg='#FFCDD2')
        self.after(500, lambda: [self.ante_display.config(bg='white'), 
                                self.pair_plus_display.config(bg='white')])
    
    def _do_reset(self, auto_reset=False):
        """真正的重置游戏界面"""
        # 重置游戏状态
        self.game.reset_game()
        self.stage_label.config(text="阶段: 下注")
        self.status_label.config(text="设置下注金额并开始游戏")
        self.result_label.config(text="")
        
        # 重置标签显示
        self.player_label.config(text="玩家")
        self.dealer_label.config(text="庄家")
        
        # 重置下注金额为0
        self.ante_var.set("0")
        self.pair_plus_var.set("0")
        self.play_var.set("0")
        self.jackpot_bet_var.set(self.last_jackpot_state)
        self.six_card_bet_var.set(self.last_six_card_state)  # 重置6 Card下注
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 清空活动卡片列表（在收牌动画后已经清空，这里确保一下）
        self.active_card_labels = []
        
        # 恢复下注区域
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.pair_plus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("pair_plus"))
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
        
        # 启用Jackpot和6 Card的Checkbutton
        self.jackpot_check.config(state=tk.NORMAL)
        self.six_card_check.config(state=tk.NORMAL)
        
        # 重置本局下注显示
        self.current_bet_label.config(text="本局下注: $0.00")
        
        # 如果是自动重置，显示消息
        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))

def main(initial_balance=1000, username="Guest"):
    app = ThreeCardPokerGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    # 独立运行时的示例调用
    final_balance = main()
    print(f"Final balance: {final_balance}")