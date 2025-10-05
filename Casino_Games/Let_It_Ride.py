import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
from collections import Counter
from itertools import combinations
import math
import secrets
import subprocess, sys

# 扑克牌花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    10: '皇家顺', 9: '同花顺', 8: '四条', 7: '葫芦', 6: '同花',
    5: '顺子', 4: '三条', 3: '两对', 2: '对子10+', 1: '对子', 0: '高牌'
}

# 支付表 - Let It Ride
MAIN_BET_PAYOUT = {
    10: 500,  # 皇家顺 500:1
    9: 200,   # 同花顺 200:1
    8: 50,    # 四条 50:1
    7: 11,    # 葫芦 11:1
    6: 8,     # 同花 8:1
    5: 5,     # 顺子 5:1
    4: 3,     # 三条 3:1
    3: 2,     # 两对 2:1
    2: 1      # 对子10或更高 1:1
}

TRIPS_PAYOUT = {
    10: 100,  # 皇家顺 100:1
    9: 40,    # 同花顺 40:1
    8: 30,    # 四条 30:1
    7: 6,     # 葫芦 6:1
    6: 3,     # 同花 3:1
    5: 6,     # 顺子 6:1
    4: 30     # 三条 30:1
}

# 修改后的Jackpot赔率表
JACKPOT_PAYOUT = {
    10: {"type": "percentage", "value": 1.0, "min": 175000},   # 皇家顺: 100% Jackpot 或 $175,000 (取较高者)
    9: {"type": "percentage", "value": 0.1, "min": 17500},     # 同花顺: 10% Jackpot 或 $17,500 (取较高者)
    8: {"type": "fixed", "value": 7000},    # 四条 $7,000
    7: {"type": "fixed", "value": 5000},    # 葫芦 $5,000
    6: {"type": "fixed", "value": 2500},    # 同花 $2,500
    5: {"type": "fixed", "value": 1000}     # 顺子 $1,000
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
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)
    
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
    default_jackpot = 157301.26
    # 文件不存在时使用默认奖池
    if not os.path.exists(path):
        return True, default_jackpot
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item.get('Games') == 'LetItRide':
                    return False, float(item.get('jackpot', default_jackpot))
    except Exception:
        return True, default_jackpot
    # 未找到 UTH 条目时也使用默认
    return True, default_jackpot

def save_progressive(jackpot):
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
        if item.get('Games') == 'LetItRide':
            item['jackpot'] = jackpot
            found = True
            break
    
    if not found:
        data.append({"Games": "LetItRide", "jackpot": jackpot})
    
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

def evaluate_hand(cards):
    values = sorted((c.value for c in cards), reverse=True)
    counts = Counter(values)
    suits = [c.suit for c in cards]

    unique_vals = sorted(set(values), reverse=True)
    if 14 in unique_vals:
        unique_vals.append(1)
    straight_vals = []
    seq = []
    for v in unique_vals:
        if not seq or seq[-1] - 1 == v:
            seq.append(v)
        else:
            seq = [v]
        if len(seq) >= 5:
            straight_vals = seq[:5]
            break

    flush_suit = next((s for s in SUITS if suits.count(s) >= 5), None)
    flush_cards = [c for c in cards if c.suit == flush_suit] if flush_suit else []

    if flush_cards and straight_vals:
        flush_vals = sorted({c.value for c in flush_cards}, reverse=True)
        if 14 in flush_vals:
            flush_vals.append(1)
        seq2 = []
        for v in flush_vals:
            if not seq2 or seq2[-1] - 1 == v:
                seq2.append(v)
            else:
                seq2 = [v]
            if len(seq2) >= 5:
                return (10, seq2[:5]) if seq2[0] == 14 else (9, seq2[:5])

    counts_list = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    if counts_list[0][1] == 4:
        quad = counts_list[0][0]
        kicker = max(v for v in values if v != quad)
        return (8, [quad, kicker])
    if counts_list[0][1] == 3 and counts_list[1][1] >= 2:
        return (7, [counts_list[0][0], counts_list[1][0]])
    if flush_suit:
        top5 = sorted((c.value for c in flush_cards), reverse=True)[:5]
        return (6, top5)
    if straight_vals:
        return (5, straight_vals)
    if counts_list[0][1] == 3:
        three = counts_list[0][0]
        kickers = [v for v in values if v != three][:2]
        return (4, [three] + kickers)
    pairs = [v for v, cnt in counts_list if cnt == 2]
    if len(pairs) >= 2:
        high, low = pairs[0], pairs[1]
        kicker = max(v for v in values if v not in (high, low))
        return (3, [high, low, kicker])
    if counts_list[0][1] == 2:
        pair = counts_list[0][0]
        kickers = [v for v in values if v != pair][:3]
        # 检查是否是对子10或更高
        if pair >= 10:  # 10, J, Q, K, A
            return (2, [pair] + kickers)
        else:
            return (1, [pair] + kickers)
    return (0, values[:5])

def find_best_5(cards):
    best_eval = None
    best_hand = None
    for combo in combinations(cards, 5):
        ev = evaluate_hand(combo)
        if best_eval is None or ev > best_eval:
            best_eval = ev
            best_hand = combo
    return best_eval, best_hand

class LetItRideGame:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.community_cards = []
        self.player_hole = []
        self.dealer_hole = []  # 在Let It Ride中不使用，但保留结构
        self.bet_a = 0
        self.bet_b = 0
        self.bet_c = 0
        self.trips = 0
        self.participate_jackpot = False
        self.stage = "pre_flop"  # pre_flop, flop, turn, showdown
        self.keep_bet_a = False
        self.keep_bet_b = False
        self.cards_revealed = {
            "player": [False, False, False],
            "community": [False, False]  # 修改为只有2张公共牌
        }
        # 加载Jackpot金额
        self.jackpot_initial, self.progressive_amount = load_jackpot()
        # 记录牌序信息
        self.cut_position = self.deck.start_pos
        self.card_sequence = self.deck.card_sequence
    
    def deal_initial(self):
        """发初始牌：玩家3张，公共牌2张"""
        # 按照新的发牌顺序：玩家第0张，公共牌第0张，玩家第1张，公共牌第1张，玩家第2张
        self.player_hole = [self.deck.deal(1)[0]]  # 玩家第0张
        self.community_cards = [self.deck.deal(1)[0]]  # 公共牌第0张
        self.player_hole.append(self.deck.deal(1)[0])  # 玩家第1张
        self.community_cards.append(self.deck.deal(1)[0])  # 公共牌第1张
        self.player_hole.append(self.deck.deal(1)[0])  # 玩家第2张
    
    def evaluate_hands(self):
        """评估玩家的手牌"""
        player_cards = self.player_hole + self.community_cards
        player_eval, player_best = find_best_5(player_cards)
        return player_eval
    
    def evaluate_current_hand(self, cards, community_revealed_count):
        """评估当前手牌（只考虑已翻开的牌）"""
        if community_revealed_count == 0 and len(cards) < 3:
            return None
        
        # 只使用已翻开的公共牌
        revealed_community = self.community_cards[:community_revealed_count]
        all_cards = cards + revealed_community
        
        # 至少需要3张牌才能评估
        if len(all_cards) < 3:
            return None
            
        best_eval, _ = find_best_5(all_cards)
        return best_eval

class LetItRideGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("任逍遥扑克")
        self.geometry("1020x700+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')
        
        # 下注上限设置
        self.MAIN_BET_MAX = 10000  # A/B/C注上限
        self.TRIPS_BET_MAX = 2500  # 三张手牌加注上限
        
        self.username = username
        self.balance = initial_balance
        self.game = LetItRideGame()
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
        self.win_details = {
            "bet_a": 0,
            "bet_b": 0,
            "bet_c": 0,
            "trips": 0,
            "jackpot": 0
        }
        self.bet_widgets = {}  # 存储下注显示控件
        self.last_jackpot_selection = False  # 记录上局Jackpot选择
        self.bet_refunded = {"a": False, "b": False}  # 跟踪A注和B注是否已退还
        self.current_refund = 0.0  # 本局退还金额
        
        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def show_game_instructions(self):
        """显示游戏规则说明"""
        # 创建自定义弹窗
        win = tk.Toplevel(self)
        win.title("游戏规则")
        win.geometry("900x700")
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
        
        # 游戏标题
        title_label = tk.Label(
            content_frame, 
            text="任逍遥扑克 游戏规则",
            font=('微软雅黑', 16, 'bold'),
            bg='#F0F0F0',
            fg='#2a4a3c'
        )
        title_label.pack(pady=(0, 15))
        
        # 游戏规则文本
        rules_text = """
        任逍遥扑克是一种使用标准扑克牌的赌场游戏。玩家下三个等额的注（A注、B注和C注），
        并可以选择下额外的三张手牌加注和累进大奖。

        游戏流程:
          1. 玩家下三个等额的注（A注、B注和C注）
          2. 玩家可以选择下三张手牌加注和参与累进大奖
          3. 发牌：玩家获得3张底牌，桌上有2张公共牌（面朝下）
          4. 查看底牌后，玩家决定是否收回A注或保留A注
          5. 翻开第一张公共牌后，玩家决定是否收回B注或保留B注
          6. 翻开第二张公共牌，结算所有保留的下注

        牌型排名（从高到低）:
          皇家顺 > 同花顺 > 四条 > 葫芦 > 同花 > 顺子 > 三条 > 两对 > 对子10+ > 对子 > 高牌
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
        
        # 赔率表标题
        tk.Label(
            content_frame, 
            text="赔率表",
            font=('微软雅黑', 14, 'bold'),
            bg='#F0F0F0',
            fg='#2a4a3c'
        ).pack(fill=tk.X, padx=10, pady=(20, 10), anchor='center')
        
        # 创建赔率表格框架
        odds_frame = tk.Frame(content_frame, bg='#F0F0F0', relief=tk.RAISED, bd=1)
        odds_frame.pack(fill=tk.X, padx=20, pady=5)
        
        # 表头
        headers = ["牌型", "主注", "三张手牌加注", "累进大奖"]
        header_bg = '#4B8BBE'
        header_fg = 'white'
        
        for col, header in enumerate(headers):
            header_label = tk.Label(
                odds_frame,
                text=header,
                font=('微软雅黑', 11, 'bold'),
                bg=header_bg,
                fg=header_fg,
                padx=10,
                pady=8,
                width=15
            )
            header_label.grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
        
        # 表格数据
        odds_data = [
            ("皇家顺", "500:1", "100:1", "100%累进大奖 或 $175,000\n(取较高者)"),
            ("同花顺", "200:1", "40:1", "10%累进大奖 或 $17,500\n(取较高者)"),
            ("四条", "50:1", "30:1", "$7,000"),
            ("葫芦", "11:1", "6:1", "$5,000"),
            ("同花", "8:1", "3:1", "$2,500"),
            ("顺子", "5:1", "6:1", "$1,000"),
            ("三条", "3:1", "30:1", "-"),
            ("两对", "2:1", "-", "-"),
            ("对子10+", "1:1", "-", "-")
        ]
        
        for row, row_data in enumerate(odds_data, start=1):
            row_bg = '#E8F4F8' if row % 2 == 0 else '#FFFFFF'
            for col, cell_text in enumerate(row_data):
                cell_label = tk.Label(
                    odds_frame,
                    text=cell_text,
                    font=('微软雅黑', 10),
                    bg=row_bg,
                    padx=10,
                    pady=8,
                    justify=tk.CENTER,
                    wraplength=150
                )
                cell_label.grid(row=row, column=col, sticky='nsew', padx=1, pady=1)
        
        # 配置网格权重
        for col in range(len(headers)):
            odds_frame.columnconfigure(col, weight=1)
        for row in range(len(odds_data) + 1):
            odds_frame.rowconfigure(row, weight=1)
        
        # 注意事项
        notes_text = """
        注意事项:
        - Jackpot奖金需要玩家参与Jackpot下注($20)才有资格获得
        - Jackpot奖金基于玩家的3张底牌和头2张公共牌组成的牌型
        - 对子10+指的是对子为10、J、Q、K或A
        - Trips注基于玩家的3张底牌评估
        """
        
        notes_label = tk.Label(
            content_frame, 
            text=notes_text,
            font=('微软雅黑', 10),
            bg='#F0F0F0',
            justify=tk.LEFT,
            padx=10,
            pady=15
        )
        notes_label.pack(fill=tk.X, padx=10, pady=10)
        
        # 更新滚动区域
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        
        # 添加关闭按钮
        close_btn = ttk.Button(
            win,
            text="关闭",
            command=win.destroy,
            style='TButton'
        )
        close_btn.pack(pady=10)
        
        # 绑定鼠标滚轮滚动
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # 配置按钮样式
        style = ttk.Style()
        style.configure('TButton', font=('微软雅黑', 10))
        
    def on_close(self):
        # 取消自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
        self.destroy()
        self.quit()
        
    def _load_assets(self):
        card_size = (100, 140)
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
                    
    def check_bet_limit(self, bet_type, current_value, chip_value):
        """检查下注是否超过上限，如果超过则自动调整并显示警告"""
        new_value = current_value + chip_value
        
        if bet_type in ["bet_a", "bet_b", "bet_c"]:
            # 主注上限检查
            if new_value > self.MAIN_BET_MAX:
                messagebox.showwarning("下注上限", "主注已达上限，自动调整为 10000")
                return self.MAIN_BET_MAX
        elif bet_type == "trips":
            # 三张手牌加注上限检查
            if new_value > self.TRIPS_BET_MAX:
                messagebox.showwarning("下注上限", "三张手牌加注已达上限，自动调整为 2500")
                return self.TRIPS_BET_MAX
        
        return new_value
    
    def is_bet_full(self, bet_type, current_value):
        """检查下注是否已满"""
        if bet_type in ["bet_a", "bet_b", "bet_c"]:
            return current_value >= self.MAIN_BET_MAX
        elif bet_type == "trips":
            return current_value >= self.TRIPS_BET_MAX
        return False
    
    def add_chip_to_bet(self, bet_type):
        """添加筹码到下注区域"""
        if not self.selected_chip:
            return
            
        # 获取筹码金额
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            # 处理带K的筹码，如1K或2.5K
            chip_value = float(chip_text.replace('K', '')) * 1000
        else:
            chip_value = float(chip_text)
        
        # 检查下注是否已满
        if bet_type in ["bet_a", "bet_b", "bet_c"]:
            current = float(self.bet_a_var.get())
            if self.is_bet_full(bet_type, current):
                messagebox.showwarning("下注已满", "主注已满，不能再下注！")
                return
        elif bet_type == "trips":
            current = float(self.trips_var.get())
            if self.is_bet_full(bet_type, current):
                messagebox.showwarning("下注已满", "三张手牌加注已满，不能再下注！")
                return
        
        # 更新对应的下注变量
        if bet_type == "bet_a":
            current = float(self.bet_a_var.get())
            new_value = self.check_bet_limit(bet_type, current, chip_value)
            self.bet_a_var.set(str(int(new_value)))
            # B和C注自动等于A注
            self.bet_b_var.set(self.bet_a_var.get())
            self.bet_c_var.set(self.bet_a_var.get())
        elif bet_type == "bet_b":
            current = float(self.bet_b_var.get())
            new_value = self.check_bet_limit(bet_type, current, chip_value)
            self.bet_b_var.set(str(int(new_value)))
            # A和C注自动等于B注
            self.bet_a_var.set(self.bet_b_var.get())
            self.bet_c_var.set(self.bet_b_var.get())
        elif bet_type == "bet_c":
            current = float(self.bet_c_var.get())
            new_value = self.check_bet_limit(bet_type, current, chip_value)
            self.bet_c_var.set(str(int(new_value)))
            # A和B注自动等于C注
            self.bet_a_var.set(self.bet_c_var.get())
            self.bet_b_var.set(self.bet_c_var.get())
        elif bet_type == "trips":
            current = float(self.trips_var.get())
            new_value = self.check_bet_limit(bet_type, current, chip_value)
            self.trips_var.set(str(int(new_value)))
    
    def _create_widgets(self):
        # 主框架 - 左右布局
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧牌桌区域 - 使用Canvas提供更好的控制
        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 牌桌背景
        table_bg = table_canvas.create_rectangle(0, 0, 800, 600, fill='#35654d', outline='')
        
        # 公共牌区域 - 固定高度200
        community_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        community_frame.place(x=150, y=100, width=270, height=210)  # 调整位置和宽度以适应2张牌
        community_label = tk.Label(community_frame, text="公共牌", font=('Arial', 18), bg='#2a4a3c', fg='white')
        community_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.community_cards_frame = tk.Frame(community_frame, bg='#2a4a3c')
        self.community_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 玩家区域 - 固定高度200
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=110, y=350, width=350, height=210)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 右侧控制面板
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=300, padx=10, pady=2)
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
            text="翻牌前",
            font=('Arial', 18, 'bold'),
            bg='#2a4a3c',
            fg='#FFD700'
        )
        self.stage_label.pack(side=tk.RIGHT, padx=20, pady=10)
        
        # Progressive显示区域 - 修改后的代码
        progressive_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        progressive_frame.pack(fill=tk.X, pady=5)

        # 使用网格布局确保标签在左边，金额在中间
        progressive_frame.columnconfigure(0, weight=1)  # 标签列
        progressive_frame.columnconfigure(1, weight=2)  # 金额列（更宽）
        progressive_frame.columnconfigure(2, weight=1)  # 空白列（平衡布局）

        # 标签放在左边
        progressive_label = tk.Label(progressive_frame, text="累进大奖:", 
                                font=('Arial', 18), bg='#2a4a3c', fg='gold')
        progressive_label.grid(row=0, column=0, sticky='w', padx=(10, 0), pady=5)

        # 金额放在中间 - 使用StringVar
        self.progressive_amount_var = tk.StringVar()
        self.progressive_amount_var.set(f"${self.game.progressive_amount:.2f}")
        self.progressive_display = tk.Label(progressive_frame, textvariable=self.progressive_amount_var, 
                                    font=('Arial', 22, 'bold'), bg='#2a4a3c', fg='gold')
        self.progressive_display.grid(row=0, column=1, sticky='w', pady=3)
        
        # 筹码区域
        chips_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        chips_frame.pack(fill=tk.X, pady=5)
        
        chips_label = tk.Label(chips_frame, text="筹码:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        chips_label.pack(anchor='w', padx=10, pady=5)
        
        # 单行放置5个筹码 - 增加50%大小
        chip_row = tk.Frame(chips_frame, bg='#2a4a3c')
        chip_row.pack(fill=tk.X, pady=5, padx=5)
        
        chip_configs = [
            ('$10', '#ffa500', 'black'),   # 橙色背景，黑色文字
            ("$25", '#00ff00', 'black'),    # 绿色背景，黑色文字
            ("$100", '#000000', 'white'),   # 黑色背景，白色文字
            ("$500", "#FF7DDA", 'black'),   # 粉色背景，黑色文字
            ("$1K", '#ffffff', 'black'),    # 白色背景，黑色文字
            ("$2.5K", '#ff0000', 'white'),     # 红色背景，白色文字
        ]
        
        self.chip_buttons = []
        self.chip_texts = {}  # 存储每个筹码按钮的文本
        for text, bg_color, fg_color in chip_configs:
            # 使用Canvas创建圆形筹码 - 尺寸改为55x55
            chip_canvas = tk.Canvas(chip_row, width=55, height=55, bg='#2a4a3c', highlightthickness=0)
            
            # 创建圆形（尺寸调整为51x51，在55x55画布中居中）
            chip_canvas.create_oval(2, 2, 54, 54, fill=bg_color, outline='black')
            
            # 创建文本（位置调整为画布中心）
            text_id = chip_canvas.create_text(27.5, 27.5, text=text, fill=fg_color, font=('Arial', 14, 'bold'))
            
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text  # 存储文本
        
        # 默认选中$10筹码
        self.select_chip("$10")

        # 每注限制
        minmax_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        minmax_frame.pack(fill=tk.X, pady=5)
        
        # 标题行
        header_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        header_frame.pack(fill=tk.X, padx=10, pady=(5, 0))
        
        tk.Label(header_frame, text="底注最低", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=10).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="底注最高", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=10).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="边注最高", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=10).pack(side=tk.LEFT, expand=True)
        
        # 数值行
        value_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        value_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        tk.Label(value_frame, text="$10", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=10).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$10,000", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=10).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$2,500", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=10).pack(side=tk.LEFT, expand=True)
        
        # 下注区域
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=5)

        # 第一行：Progressive选项
        progressive_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        progressive_frame.pack(fill=tk.X, padx=20, pady=5)

        self.progressive_var = tk.IntVar()
        self.progressive_cb = tk.Checkbutton(
            progressive_frame, text="累进大奖 ($20.00)", 
            variable=self.progressive_var, font=('Arial', 14),
            bg='#2a4a3c', fg='white', selectcolor='#35654d'
        )
        self.progressive_cb.pack(side=tk.LEFT)

        # 三张扑克标签和显示 
        trips_label = tk.Label(progressive_frame, text="三张手牌加注:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        trips_label.pack(side=tk.LEFT, padx=(20, 0))

        self.trips_var = tk.StringVar(value="0")
        self.trips_display = tk.Label(progressive_frame, textvariable=self.trips_var, font=('Arial', 14), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.trips_display.pack(side=tk.LEFT, padx=5)
        self.trips_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("trips"))
        self.bet_widgets["trips"] = self.trips_display

        # 第二行：A、B、C注
        bottom_bet_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        bottom_bet_frame.pack(fill=tk.X, padx=20, pady=5)

        # A注
        bet_a_label = tk.Label(bottom_bet_frame, text="  A:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        bet_a_label.pack(side=tk.LEFT)

        self.bet_a_var = tk.StringVar(value="0")
        self.bet_a_display = tk.Label(bottom_bet_frame, textvariable=self.bet_a_var, font=('Arial', 14), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.bet_a_display.pack(side=tk.LEFT, padx=5)
        self.bet_a_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bet_a"))
        self.bet_widgets["bet_a"] = self.bet_a_display

        # 等号
        eq_label1 = tk.Label(bottom_bet_frame, text="=", font=('Arial', 14), bg='#2a4a3c', fg='white')
        eq_label1.pack(side=tk.LEFT, padx=5)

        # B注
        bet_b_label = tk.Label(bottom_bet_frame, text="B:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        bet_b_label.pack(side=tk.LEFT)

        self.bet_b_var = tk.StringVar(value="0")
        self.bet_b_display = tk.Label(bottom_bet_frame, textvariable=self.bet_b_var, font=('Arial', 14), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.bet_b_display.pack(side=tk.LEFT, padx=5)
        self.bet_b_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bet_b"))
        self.bet_widgets["bet_b"] = self.bet_b_display

        # 等号
        eq_label2 = tk.Label(bottom_bet_frame, text="=", font=('Arial', 14), bg='#2a4a3c', fg='white')
        eq_label2.pack(side=tk.LEFT, padx=5)

        # C注
        bet_c_label = tk.Label(bottom_bet_frame, text="C:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        bet_c_label.pack(side=tk.LEFT)

        self.bet_c_var = tk.StringVar(value="0")
        self.bet_c_display = tk.Label(bottom_bet_frame, textvariable=self.bet_c_var, font=('Arial', 14), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.bet_c_display.pack(side=tk.LEFT, padx=5)
        self.bet_c_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bet_c"))
        self.bet_widgets["bet_c"] = self.bet_c_display

        # 新增提示文字
        self.hint_label = tk.Label(bet_frame, text="", 
                                font=('Arial', 12), bg='#2a4a3c', fg='#FFD700')
        self.hint_label.pack(pady=(0, 10))

        # 游戏操作按钮框架 - 用于放置所有操作按钮
        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        self.action_frame.pack(fill=tk.X, pady=10)

        # 创建一个框架来容纳重置按钮和开始游戏按钮
        start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_button_frame.pack(pady=5)

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
            font=('Arial', 14), bg='#2a4a3c', fg='white'
        )
        self.status_label.pack(pady=5, fill=tk.X)

        # 本局下注和上局获胜金额显示
        bet_info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_info_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        
        # 第一行：本局下注和本局退还
        row1_frame = tk.Frame(bet_info_frame, bg='#2a4a3c')
        row1_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 本局下注金额 - 设置固定宽度
        self.current_bet_label = tk.Label(
            row1_frame, text="本局下注: $0.00", 
            font=('Arial', 14), bg='#2a4a3c', fg='white',
            width=15, anchor='w'
        )
        self.current_bet_label.pack(side=tk.LEFT, padx=10)
        
        # 本局退还金额 - 设置固定宽度
        self.refund_label = tk.Label(
            row1_frame, text="本局退还: $0.00", 
            font=('Arial', 14), bg='#2a4a3c', fg='light blue',
            width=15, anchor='w'
        )
        self.refund_label.pack(side=tk.LEFT, padx=10)
        
        # 第二行：上局获胜金额和规则按钮
        row2_frame = tk.Frame(bet_info_frame, bg='#2a4a3c')
        row2_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 上局获胜金额 - 设置固定宽度
        self.last_win_label = tk.Label(
            row2_frame, text="  上局获胜: $0.00", 
            font=('Arial', 14), bg='#2a4a3c', fg='#FFD700',
            width=15, anchor='w'
        )
        self.last_win_label.pack(side=tk.LEFT)

        self.info_button = tk.Button(
            row2_frame,
            text="ℹ️",
            command=self.show_game_instructions,
            bg='#4B8BBE',
            fg='white',
            font=('Arial', 12),
            width=2,
            relief=tk.FLAT
        )
        self.info_button.pack(side=tk.RIGHT)
    
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
        """更新玩家的手牌标签显示牌型"""
        # 计算玩家当前牌型
        community_revealed_count = sum(self.game.cards_revealed["community"])
        all_cards = self.game.player_hole + self.game.community_cards[:community_revealed_count]
        
        if len(all_cards) < 3:
            player_hand_name = ""
        else:
            # 根据牌数决定评估方式
            if len(all_cards) < 5:
                # 评估3张或4张牌的牌型
                values = [c.value for c in all_cards]
                counts = Counter(values)
                if 3 in counts.values():
                    player_hand_name = "三条"
                elif list(counts.values()).count(2) == 1:
                    player_hand_name = "对子"
                elif list(counts.values()).count(2) >= 2:
                    player_hand_name = "两对"
                else:
                    player_hand_name = "高牌"
            else:
                # 5张或更多牌，使用标准评估
                player_eval = self.game.evaluate_current_hand(self.game.player_hole, community_revealed_count)
                if player_eval is None:
                    player_hand_name = ""
                else:
                    player_hand_name = HAND_RANK_NAMES.get(player_eval[0], "")
                    
        self.player_label.config(text=f"玩家 - {player_hand_name}" if player_hand_name else "玩家")
    
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
            # 检查并调整下注金额是否超过上限
            bet_a = int(self.bet_a_var.get())
            bet_b = int(self.bet_b_var.get())
            bet_c = int(self.bet_c_var.get())
            trips = int(self.trips_var.get())
            
            # 检查主注上限
            if bet_a > self.MAIN_BET_MAX or bet_b > self.MAIN_BET_MAX or bet_c > self.MAIN_BET_MAX:
                messagebox.showwarning("下注上限", "主注已达上限，自动调整为 10000")
                bet_a = self.MAIN_BET_MAX
                bet_b = self.MAIN_BET_MAX
                bet_c = self.MAIN_BET_MAX
                self.bet_a_var.set(str(bet_a))
                self.bet_b_var.set(str(bet_b))
                self.bet_c_var.set(str(bet_c))
            
            # 检查Trips注上限
            if trips > self.TRIPS_BET_MAX:
                messagebox.showwarning("下注上限", "三张手牌加注已达上限，自动调整为 2500")
                trips = self.TRIPS_BET_MAX
                self.trips_var.set(str(trips))
            
            # 重置退款状态和金额
            self.bet_refunded = {"a": False, "b": False}
            self.current_refund = 0.0
            self.refund_label.config(text="本局退还: $0.00")
            
            self.bet_a = bet_a
            self.bet_b = bet_b
            self.bet_c = bet_c
            self.trips = trips
            self.participate_jackpot = bool(self.progressive_var.get())
            self.last_jackpot_selection = bool(self.progressive_var.get())  # 记录当前选择
            
            # 检查下注至少5块
            if self.bet_a < 5 or self.bet_b < 5 or self.bet_c < 5:
                messagebox.showerror("错误", "A、B、C注至少需要5块")
                return
            
            # 计算总下注
            total_bet = self.bet_a + self.bet_b + self.bet_c + self.trips
            if self.participate_jackpot:
                total_bet += 20
                
            if total_bet > self.balance:
                messagebox.showerror("错误", "余额不足！")
                return
                
            self.balance -= total_bet
            self.update_balance()
            
            # 更新本局下注显示
            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            
            self.game.reset_game()
            self.game.deal_initial()
            self.game.bet_a = self.bet_a
            self.game.bet_b = self.bet_b
            self.game.bet_c = self.bet_c
            self.game.trips = self.trips
            self.game.participate_jackpot = self.participate_jackpot
            
            # 清除所有卡片
            for widget in self.community_cards_frame.winfo_children():
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
            
            # 公共牌 - 放置在中心位置
            for i in range(2):  # 只有2张公共牌
                card_id = f"community_{i}"
                self.card_positions[card_id] = {
                    "current": (50, 50), 
                    "target": (i * 110, 0)  # 水平排列
                }
                self.animation_queue.append(card_id)
            
            # 玩家牌 - 放置在中心位置
            for i in range(3):
                card_id = f"player_{i}"
                self.card_positions[card_id] = {
                    "current": (50, 50), 
                    "target": (i * 100, 0)  # 水平排列
                }
                self.animation_queue.append(card_id)
            
            # 开始动画
            self.animate_deal()
            
            # 更新游戏状态
            self.stage_label.config(text="初始决策")
            self.status_label.config(text="手牌已打开，做出您的决策。")
            
            # 创建操作按钮 - 替换开始按钮
            for widget in self.action_frame.winfo_children():
                widget.destroy()
                
            buttons_container = tk.Frame(self.action_frame, bg='#2a4a3c')
            buttons_container.pack(expand=True, pady=5)

            self.keep_a_button = tk.Button(
                buttons_container, text="保留A注", 
                command=lambda: self.play_action(True, "a"), 
                font=('Arial', 14), bg='#4CAF50', fg='white', width=9,
                state=tk.DISABLED
            )
            self.keep_a_button.pack(side=tk.LEFT, padx=9)
                
            self.pull_a_button = tk.Button(
                buttons_container, text="收回A注", 
                command=lambda: self.play_action(False, "a"), 
                font=('Arial', 14), bg='#F44336', fg='white', width=9,
                state=tk.DISABLED
            )
            self.pull_a_button.pack(side=tk.LEFT, padx=9)
        
            # 禁用下注区域
            self.bet_a_display.unbind("<Button-1>")
            self.bet_b_display.unbind("<Button-1>")
            self.bet_c_display.unbind("<Button-1>")
            self.trips_display.unbind("<Button-1>")
            self.progressive_cb.config(state=tk.DISABLED)
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")
            
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
        if card_id.startswith("community"):
            frame = self.community_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.community_cards[idx] if idx < len(self.game.community_cards) else None
        elif card_id.startswith("player"):
            frame = self.player_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.player_hole[idx] if idx < len(self.game.player_hole) else None
        
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
        
        # 1.5秒后启用决策按钮
        self.after(1500, self.enable_decision_buttons)
    
    def reveal_first_community_card(self):
        """翻开第一张公共牌（带动画）"""
        for i, card_label in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up and i < 1:  # 只翻开第一张
                self.flip_card_animation(card_label)
                # 标记公共牌已翻开
                self.game.cards_revealed["community"][i] = True
        
        # 更新玩家牌型
        self.update_hand_labels()
        
        # 2秒后启用翻牌圈按钮
        self.after(2000, self.enable_flop_buttons)

    def reveal_second_community_card(self):
        """翻开第二张公共牌（带动画）"""
        # 安全地获取社区牌框架中的卡片
        for i, card_label in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up and i >= 1:  # 只翻开第二张
                self.flip_card_animation(card_label)
                # 标记公共牌已翻开
                self.game.cards_revealed["community"][i] = True
        
        # 更新玩家牌型
        self.update_hand_labels()
        
        # 1.5秒后结算
        self.after(1500, self.show_showdown)
    
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
    
    def enable_decision_buttons(self):
        """启用初始决策按钮"""
        self.keep_a_button.config(state=tk.NORMAL)
        self.pull_a_button.config(state=tk.NORMAL)

    def enable_flop_buttons(self):
        """启用翻牌圈决策按钮"""
        self.keep_b_button.config(state=tk.NORMAL)
        self.pull_b_button.config(state=tk.NORMAL)

    def play_action(self, keep_bet, bet_type):
        if bet_type == "a":
            self.game.keep_bet_a = keep_bet
            if not keep_bet:
                # 收回A注
                refund_amount = self.game.bet_a
                self.balance += refund_amount
                self.current_refund += refund_amount
                self.update_balance()
                self.refund_label.config(text=f"本局退还: ${self.current_refund:.2f}")
                self.status_label.config(text="已收回A注")
                # 标记A注已退还
                self.bet_refunded["a"] = True
                # 更新A注显示为"退还"并设置背景色为浅蓝色
                self.bet_a_display.config(text="退还", bg='light blue')
                # 解除StringVar绑定
                self.bet_a_display.config(textvariable=None)
            else:
                self.status_label.config(text="已保留A注")
            
            # 进入翻牌圈
            self.game.stage = "flop"
            self.stage_label.config(text="翻牌圈")
            self.status_label.config(text="翻开第一张公共牌，做出您的决策。")
            
            # 翻开第一张公共牌
            self.reveal_first_community_card()
            
            # 更新操作按钮
            for widget in self.action_frame.winfo_children():
                widget.destroy()
                
            buttons_container = tk.Frame(self.action_frame, bg='#2a4a3c')
            buttons_container.pack(expand=True, pady=5)

            self.keep_b_button = tk.Button(
                buttons_container, text="保留B注", 
                command=lambda: self.play_action(True, "b"), 
                state=tk.DISABLED,
                font=('Arial', 14), bg='#4CAF50', fg='white', width=9
            )
            self.keep_b_button.pack(side=tk.LEFT, padx=9)
                
            self.pull_b_button = tk.Button(
                buttons_container, text="收回B注", 
                command=lambda: self.play_action(False, "b"), 
                state=tk.DISABLED,
                font=('Arial', 14), bg='#F44336', fg='white', width=9
            )
            self.pull_b_button.pack(side=tk.LEFT, padx=9)
        
        elif bet_type == "b":
            self.game.keep_bet_b = keep_bet
            if not keep_bet:
                # 收回B注
                refund_amount = self.game.bet_b
                self.balance += refund_amount
                self.current_refund += refund_amount
                self.update_balance()
                self.refund_label.config(text=f"本局退还: ${self.current_refund:.2f}")
                self.status_label.config(text="已收回B注")
                # 标记B注已退还
                self.bet_refunded["b"] = True
                # 更新B注显示为"退还"并设置背景色为浅蓝色
                self.bet_b_display.config(text="退还", bg='light blue')
                # 解除StringVar绑定
                self.bet_b_display.config(textvariable=None)
            else:
                self.status_label.config(text="已保留B注")
            
            # 进入河牌圈
            self.game.stage = "turn"
            self.stage_label.config(text="河牌圈")
            self.status_label.config(text="翻开第二张公共牌，结算中...")
            
            # 翻开第二张公共牌
            self.reveal_second_community_card()

    def show_showdown(self):
        # 翻开所有未翻开的牌
        for i, card_label in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                # 标记公共牌已翻开
                self.game.cards_revealed["community"][i] = True
        
        # 更新玩家牌型
        self.update_hand_labels()
        
        # 评估手牌
        player_eval = self.game.evaluate_hands()
        
        # 结算
        winnings = self.calculate_winnings(player_eval)
        self.last_win = winnings
        
        # 更新余额
        self.balance += winnings
        self.update_balance()
        
        # 更新下注显示金额
        self.bet_a_var.set(str(int(self.win_details['bet_a'])))
        self.bet_b_var.set(str(int(self.win_details['bet_b'])))
        self.bet_c_var.set(str(int(self.win_details['bet_c'])))
        self.trips_var.set(str(int(self.win_details['trips'])))
        
        # 设置背景色：赢为金色，Push为浅蓝色，输为白色
        for bet_type, widget in self.bet_widgets.items():
            if bet_type in ["bet_a", "bet_b", "bet_c"]:
                # 对于输的部分，金额设为0
                if self.win_details[bet_type] == 0:
                    widget.config(bg='white')  # 输 - 白色背景
                else:
                    # 判断是赢还是Push
                    principal = getattr(self.game, bet_type)
                    
                    # 如果赢取金额等于本金，则是Push（平局）
                    if self.win_details[bet_type] == principal:
                        widget.config(bg='light blue')  # Push - 浅蓝色背景
                    else:
                        widget.config(bg='gold')  # 赢 - 金色背景
            elif bet_type == "trips":
                if self.win_details[bet_type] > 0:
                    widget.config(bg='gold')  # 赢 - 金色背景
                else:
                    widget.config(bg='white')  # 输 - 白色背景
        
        # 显示结果
        result_text = f"赢取金额: ${winnings:.2f}"
        self.status_label.config(text="游戏结束。")
        
        # 更新上局获胜金额
        self.last_win_label.config(text=f"  上局获胜: ${winnings:.2f}")
        
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

    def calculate_winnings(self, player_eval):
        # 重置获胜详情
        self.win_details = {
            "bet_a": 0,
            "bet_b": 0,
            "bet_c": 0,
            "trips": 0,
            "jackpot": 0
        }
        
        total_winnings = 0
        hand_rank = player_eval[0]
        
        # 1. A注结算
        if self.game.keep_bet_a:
            if hand_rank in MAIN_BET_PAYOUT:
                payout = MAIN_BET_PAYOUT[hand_rank]
                self.win_details['bet_a'] = self.game.bet_a * (1 + payout)
            else:
                # 没有获胜牌型，输掉A注
                self.win_details['bet_a'] = 0
        else:
            # 已收回A注，不参与结算
            self.win_details['bet_a'] = self.game.bet_a
        
        total_winnings += self.win_details['bet_a']
        
        # 2. B注结算
        if self.game.keep_bet_b:
            if hand_rank in MAIN_BET_PAYOUT:
                payout = MAIN_BET_PAYOUT[hand_rank]
                self.win_details['bet_b'] = self.game.bet_b * (1 + payout)
            else:
                # 没有获胜牌型，输掉B注
                self.win_details['bet_b'] = 0
        else:
            # 已收回B注，不参与结算
            self.win_details['bet_b'] = self.game.bet_b
        
        total_winnings += self.win_details['bet_b']
        
        # 3. C注结算（始终保留）
        if hand_rank in MAIN_BET_PAYOUT:
            payout = MAIN_BET_PAYOUT[hand_rank]
            self.win_details['bet_c'] = self.game.bet_c * (1 + payout)
        else:
            # 没有获胜牌型，输掉C注
            self.win_details['bet_c'] = 0
        
        total_winnings += self.win_details['bet_c']
        
        # 4. Trips 副注结算
        if self.game.trips > 0:
            # 使用玩家的3张底牌评估Trips
            # 专门评估3张牌的函数
            trips_eval = self.evaluate_3card_hand(self.game.player_hole)
            if trips_eval == "同花顺":
                odds = 40
                self.win_details['trips'] = self.game.trips * (1 + odds)
            elif trips_eval == "三条":
                odds = 30
                self.win_details['trips'] = self.game.trips * (1 + odds)
            elif trips_eval == "顺子":
                odds = 6
                self.win_details['trips'] = self.game.trips * (1 + odds)
            elif trips_eval == "同花":
                odds = 3
                self.win_details['trips'] = self.game.trips * (1 + odds)
            elif trips_eval == "对子":
                odds = 1
                self.win_details['trips'] = self.game.trips * (1 + odds)
            else:
                # 没有匹配的牌型，Trips输
                self.win_details['trips'] = 0
        total_winnings += self.win_details['trips']
        
        # 5. Jackpot 结算 - 使用提供的简化版代码
        if self.game.participate_jackpot:
            progressive_cards = self.game.player_hole + self.game.community_cards[:3]
            pg_eval, _ = evaluate_hand(progressive_cards)
            
            # 定义奖金规则 - 根据您的要求修改
            jackpot_rules = {
                10: {"amount": lambda: max(self.game.progressive_amount, 175000), "message": "皇家顺! 赢得累进大奖 ${amount:.2f}!"},
                9: {"amount": lambda: max(self.game.progressive_amount * 0.1, 17500), "message": "同花顺! 赢得累进大奖 ${amount:.2f}!"},
                8: {"amount": 7000, "message": "四条! 赢得累进大奖 $7,000!"},
                7: {"amount": 5000, "message": "葫芦! 赢得累进大奖 $5,000!"},
                6: {"amount": 2500, "message": "同花! 赢得累进大奖 $2,500!"},
                5: {"amount": 1000, "message": "顺子! 赢得累进大奖 $1,000!"}
            }
            
            if pg_eval in jackpot_rules:
                rule = jackpot_rules[pg_eval]
                
                # 计算奖金金额
                if callable(rule["amount"]):
                    amount = rule["amount"]()
                else:
                    amount = rule["amount"]
                
                self.win_details['jackpot'] = amount
                total_winnings += amount
                
                # 从奖池扣除
                self.game.progressive_amount -= amount
                
                # 显示消息
                messagebox.showinfo("恭喜您获得累进大奖！", rule["message"].format(amount=amount))
            
            # 保存Progressive金额
            save_progressive(self.game.progressive_amount)
            self.progressive_amount_var.set(f"${self.game.progressive_amount:.2f}")
        
        # 计算Jackpot增量 - 按照您的要求修改
        # (玩家的全部下注(不包括Progressive的20块)-A/B退还的金额)*0.08+Progressive的20块(有购买的话)*0.95
        total_bet_without_progressive = self.game.bet_a + self.game.bet_b + self.game.bet_c + self.game.trips
        
        # 计算退还金额
        refund_amount = 0
        if not self.game.keep_bet_a:
            refund_amount += self.game.bet_a
        if not self.game.keep_bet_b:
            refund_amount += self.game.bet_b
        
        # 计算增量
        jackpot_increment = (total_bet_without_progressive - refund_amount) * 0.08
        if self.game.participate_jackpot:
            jackpot_increment += 20 * 0.95  # Progressive的20块 * 0.95
        
        # 更新Jackpot金额
        self.game.progressive_amount += jackpot_increment
        save_progressive(self.game.progressive_amount)
        self.progressive_amount_var.set(f"${self.game.progressive_amount:.2f}")
        
        return total_winnings

    def evaluate_3card_hand(self, cards):
        """专门评估3张牌的牌型"""
        if len(cards) != 3:
            return "高牌"
        
        # 提取点数和花色
        values = sorted([card.value for card in cards], reverse=True)
        suits = [card.suit for card in cards]
        
        # 检查是否同花
        flush = len(set(suits)) == 1
        
        # 检查是否顺子
        # 处理A23的情况
        if values == [14, 3, 2]:
            straight = True
        else:
            # 正常顺子检查
            straight = values[0] - values[1] == 1 and values[1] - values[2] == 1
        
        # 检查是否三条
        three_of_a_kind = values[0] == values[1] == values[2]
        
        # 检查是否对子
        pair = values[0] == values[1] or values[1] == values[2] or values[0] == values[2]
        
        # 确定牌型
        if three_of_a_kind:
            return "三条"
        elif flush and straight:
            return "同花顺"
        elif straight:
            return "顺子"
        elif flush:
            return "同花"
        elif pair:
            return "对子"
        else:
            return "高牌"

    def animate_collect_cards(self, auto_reset):
        """执行收牌动画：先翻转所有牌为背面，然后向右收起"""
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
        """重置所有投注金额为0"""
        self.bet_a_var.set("0")
        self.bet_b_var.set("0")
        self.bet_c_var.set("0")
        self.trips_var.set("0")
        
        # 更新显示
        self.status_label.config(text="已重置所有下注金额")
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 短暂高亮显示重置效果
        self.bet_a_display.config(bg='#FFCDD2')  # 浅红色
        self.bet_b_display.config(bg='#FFCDD2')
        self.bet_c_display.config(bg='#FFCDD2')
        self.trips_display.config(bg='#FFCDD2')
        self.after(500, lambda: [self.bet_a_display.config(bg='white'), 
                                self.bet_b_display.config(bg='white'),
                                self.bet_c_display.config(bg='white'),
                                self.trips_display.config(bg='white')])
    
    def _do_reset(self, auto_reset=False):
        # 重新加载资源（切换扑克牌图片）
        self._load_assets()

        """真正的重置游戏界面"""
        # 重置游戏状态
        self.game.reset_game()
        self.stage_label.config(text="准备下注")
        
        # 重置标签显示
        self.player_label.config(text="玩家")
        
        # 重置下注金额为0
        self.bet_a_var.set("0")
        self.bet_b_var.set("0")
        self.bet_c_var.set("0")
        self.trips_var.set("0")
        # 设置Jackpot复选框为上一局的选择
        self.progressive_var.set(1 if self.last_jackpot_selection else 0)
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 重置退还显示
        self.current_refund = 0.0
        self.refund_label.config(text="本局退还: $0.00")
        
        # 清空活动卡片列表（在收牌动画后已经清空，这里确保一下）
        self.active_card_labels = []
        
        # 恢复下注区域
        self.bet_a_display.config(textvariable=self.bet_a_var)
        self.bet_b_display.config(textvariable=self.bet_b_var)
        self.bet_c_display.config(textvariable=self.bet_c_var)
        self.trips_display.config(textvariable=self.trips_var)
        
        self.bet_a_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bet_a"))
        self.bet_b_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bet_b"))
        self.bet_c_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bet_c"))
        self.trips_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("trips"))
        self.progressive_cb.config(state=tk.NORMAL)
        for chip in self.chip_buttons:
            # 使用存储的文本重新绑定事件
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
        
        # 恢复操作按钮区域
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        
        start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_button_frame.pack(pady=5)

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

    def show_card_sequence(self, event):
        """显示本局牌序窗口 - 右键点击时取消30秒计时"""
        # 取消30秒自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        
        # 确保有牌序信息
        if not hasattr(self.game, 'deck') or not self.game.deck:
            messagebox.showinfo("提示", "没有牌序信息")
            return
            
        win = tk.Toplevel(self)
        win.title("本局牌序")
        win.geometry("650x600")  # 固定窗口大小
        win.resizable(0,0)
        win.configure(bg='#f0f0f0')
        
        # 显示切牌位置
        cut_pos = self.game.deck.start_pos
        cut_label = tk.Label(
            win, 
            text=f"本局切牌位置: {cut_pos + 1}", 
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0'
        )
        cut_label.pack(pady=(10, 5))
        
        # 创建主框架
        main_frame = tk.Frame(win, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建画布用于滚动
        canvas = tk.Canvas(main_frame, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        
        # 创建内部框架放置所有内容
        content_frame = tk.Frame(canvas, bg='#f0f0f0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')
        
        # 创建卡片框架
        card_frame = tk.Frame(content_frame, bg='#f0f0f0')
        card_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 创建缩小版卡片图像
        small_size = (60, 90)
        small_images = {}

        # 尝试加载字体
        from PIL import ImageFont, ImageDraw
        
        # 创建卡片图像
        for i, card in enumerate(self.game.deck.full_deck):
            # 使用花色和点数作为键获取原始图片
            key = (card.suit, card.rank)
            
            if key in self.original_images:
                # 获取原始图像
                orig_img = self.original_images[key]
                
                # 创建缩小版图像
                small_img = orig_img.resize(small_size, Image.LANCZOS)
                small_images[i] = ImageTk.PhotoImage(small_img)
            else:
                # 创建带文字的占位图像
                img = Image.new('RGB', small_size, 'blue')
                draw = ImageDraw.Draw(img)
                text = f"{card.rank}{card.suit}"
                try:
                    font = ImageFont.truetype("arial.ttf", 12)
                except:
                    font = ImageFont.load_default()
                text_width, text_height = draw.textsize(text, font=font)
                x = (small_size[0] - text_width) / 2
                y = (small_size[1] - text_height) / 2
                draw.text((x, y), text, fill="white", font=font)
                small_images[i] = ImageTk.PhotoImage(img)
        
        # 创建表格显示牌序 - 每行8张，共7行
        for row in range(7):  # 7行
            row_frame = tk.Frame(card_frame, bg='#f0f0f0')
            row_frame.pack(fill=tk.X, pady=5)
            
            # 计算该行卡片数量 (前6行8张，最后一行4张)
            cards_in_row = 8 if row < 6 else 4
            
            for col in range(cards_in_row):
                card_index = row * 8 + col
                if card_index >= 52:  # 确保不超过52张
                    break
                    
                # 创建卡片容器
                card_container = tk.Frame(row_frame, bg='#f0f0f0')
                card_container.grid(row=0, column=col, padx=5, pady=5)
                
                # 标记切牌位置 - 显示在原始牌序中的位置
                is_cut_position = card_index == self.game.deck.start_pos
                bg_color = 'light blue' if is_cut_position else '#f0f0f0'
                
                # 显示卡片
                card = self.game.deck.full_deck[card_index]
                card_label = tk.Label(
                    card_container, 
                    image=small_images[card_index], 
                    bg=bg_color,
                    borderwidth=1,
                    relief="solid"
                )
                card_label.image = small_images[card_index]  # 保持引用
                card_label.pack()
                
                # 显示牌位置编号
                pos_label = tk.Label(
                    card_container, 
                    text=str(card_index+1), 
                    bg=bg_color,
                    font=('Arial', 9)
                )
                pos_label.pack()
        
        # 更新滚动区域
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        
        # 绑定鼠标滚轮滚动
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

def main(initial_balance=10000, username="Guest"):
    app = LetItRideGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    # 独立运行时的示例调用
    final_balance = main()
    print(f"Final balance: {final_balance}")