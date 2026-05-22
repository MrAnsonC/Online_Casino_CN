import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
import math
import secrets
import subprocess, sys
from itertools import product

# ------------------------- 基础数据 -------------------------
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
RANK_VALUES['JOKER'] = 99

HAND_RANK = {
    "五张王牌": 11,
    "皇家同花顺": 10,
    "五条": 9,
    "同花顺": 8,
    "四条": 7,
    "葫芦": 6,
    "同花": 5,
    "顺子": 4,
    "三条": 3,
    "两对": 2,
    "一对": 1,
    "高牌": 0
}
HAND_RANK_NAMES = {v: k for k, v in HAND_RANK.items()}

# 赔率表（省略，与之前相同）
BLIND_PAYOUT = {
    "五张王牌": 1000, "皇家同花顺": 50, "五条": 10, "同花顺": 9,
    "四条": 4, "葫芦": 3, "同花": 2, "顺子": 1,
}
BONUS_PAYOUT = {
    ("五张王牌", True): 2000, ("皇家同花顺", True): 90, ("皇家同花顺", False): 1000,
    ("五条", True): 70, ("同花顺", True): 25, ("同花顺", False): 200,
    ("四条", True): 6, ("四条", False): 60, ("葫芦", True): 5, ("葫芦", False): 30,
    ("同花", True): 4, ("同花", False): 25, ("顺子", True): 3, ("顺子", False): 20,
    ("三条", True): 1, ("三条", False): 6,
}
DOUBLE_SIDE_PAYOUT = {
    "皇家同花顺": 10000, "五条": 10000, "同花顺": 5000, "四条": 500,
    "葫芦": 400, "同花": 100, "顺子": 100, "三条": 9,
}

# ------------------------- 辅助函数 -------------------------
def get_data_file_path():
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'saving_data.json')

def save_user_data(users):
    with open(get_data_file_path(), 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_user_data():
    path = get_data_file_path()
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:.2f}"
            break
    save_user_data(users)

# ------------------------- 卡牌 -------------------------
class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.is_joker = (suit == 'JOKER') or (rank == 'JOKER')
        self.value = 99 if self.is_joker else RANK_VALUES[rank]

    def __repr__(self):
        if self.is_joker:
            return f"JOKER({self.rank})"
        return f"{self.rank}{self.suit}"

    def is_wild(self):
        return self.rank == '2' or self.is_joker

# ------------------------- 牌堆 -------------------------
class Deck:
    def __init__(self):
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
        shuffle_script = os.path.join(card_dir, 'shuffle.py')
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        try:
            result = subprocess.run(
                [sys.executable, shuffle_script, 'true', '1'],
                capture_output=True, text=True, encoding='utf-8',
                env=env, check=True, timeout=30
            )
            shuffle_data = json.loads(result.stdout)
            self.full_deck = [Card(d["suit"], d["rank"]) for d in shuffle_data["deck"]]
            self.cut_position = shuffle_data["cut_position"]
        except Exception:
            self.full_deck = [Card(s, r) for s in SUITS for r in RANKS] + [Card('JOKER', 'JOKER')]
            print(self.full_deck)
            self._secure_shuffle()
            self.cut_position = secrets.randbelow(53)
        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + i) % len(self.full_deck) for i in range(len(self.full_deck))]
        self.pointer = 0

    def _secure_shuffle(self):
        for i in range(len(self.full_deck)-1, 0, -1):
            j = secrets.randbelow(i+1)
            self.full_deck[i], self.full_deck[j] = self.full_deck[j], self.full_deck[i]

    def deal(self, n=1):
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt

# ------------------------- 手牌评估（万能牌枚举法） -------------------------
def best_hand_with_wildcards(cards):
    """
    返回 (等级名称, 等级值, 比较值列表, 最佳5张牌, 有效点数列表)
    万能牌（2 或 JOKER）可变为任意点数（2~14）和任意花色
    """
    wild_indices = [i for i, c in enumerate(cards) if c.is_wild()]

    # 全是万能牌 -> 五张王牌
    if len(wild_indices) == 5:
        return "五张王牌", HAND_RANK["五张王牌"], [99] * 5, cards, [99] * 5

    # 确定同花花色（如果非万能牌已经同花）
    non_wild_cards = [c for i, c in enumerate(cards) if i not in wild_indices]
    flush_suit = None
    if non_wild_cards and len(set(c.suit for c in non_wild_cards)) == 1:
        flush_suit = non_wild_cards[0].suit
    default_suit = '♠'  # 默认花色

    possible_values = list(range(2, 15))
    best_rank = -1
    best_cmp = []
    best_hand = None
    best_eff = None

    for value_combo in product(possible_values, repeat=len(wild_indices)):
        temp_cards = []
        temp_values = []

        vi = 0
        for i in range(5):
            c = cards[i]
            if i in wild_indices:
                v = value_combo[vi]
                # 关键修复：JOKER 必须变成普通牌，不再保留 JOKER 属性
                if c.is_joker:
                    # 花色：优先使用同花花色，否则默认
                    suit = flush_suit if flush_suit else default_suit
                    new_rank = RANKS[v - 2]
                    new_card = Card(suit, new_rank)   # 普通牌，不是 JOKER
                else:  # 普通2（万能牌）
                    new_card = Card(c.suit, RANKS[v - 2])
                temp_cards.append(new_card)
                temp_values.append(v)
                vi += 1
            else:
                temp_cards.append(Card(c.suit, c.rank))
                temp_values.append(c.value)

        # 若之前已确定同花，强制所有牌的花色统一（包括普通2）
        if flush_suit:
            for tc in temp_cards:
                tc.suit = flush_suit

        rank_name, rank_val, cmp_vals = evaluate_fixed_hand(temp_cards)

        if rank_val > best_rank or (rank_val == best_rank and cmp_vals > best_cmp):
            best_rank = rank_val
            best_cmp = cmp_vals
            best_hand = temp_cards[:]
            best_eff = temp_values[:]

    if best_hand is None:
        rank_name, rank_val, cmp_vals = evaluate_fixed_hand(cards)
        return rank_name, rank_val, cmp_vals, cards, [c.value for c in cards]

    rank_name = HAND_RANK_NAMES.get(best_rank, "高牌")
    return rank_name, best_rank, best_cmp, best_hand, best_eff

def evaluate_fixed_hand(cards):
    """评估5张固定牌（无万能牌）"""
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    is_flush = len(set(suits)) == 1
    # 顺子检测
    is_straight = False
    straight_high = 0
    unique_vals = sorted(set(values))
    if len(unique_vals) == 5:
        if unique_vals[-1] - unique_vals[0] == 4:
            is_straight = True
            straight_high = unique_vals[-1]
        elif unique_vals == [2,3,4,5,14]:
            is_straight = True
            straight_high = 5
    # 皇家同花顺
    if is_flush and is_straight and values[0]==14 and values[-1]==10:
        return "皇家同花顺", HAND_RANK["皇家同花顺"], [14]
    if is_flush and is_straight:
        return "同花顺", HAND_RANK["同花顺"], [straight_high]
    # 频率统计
    freq = {}
    for v in values:
        freq[v] = freq.get(v, 0) + 1
    sorted_freq = sorted(freq.items(), key=lambda x: (x[1], x[0]), reverse=True)
    if sorted_freq[0][1] == 5:
        return "五条", HAND_RANK["五条"], [sorted_freq[0][0]]
    if sorted_freq[0][1] == 4:
        return "四条", HAND_RANK["四条"], [sorted_freq[0][0], sorted_freq[1][0]]
    if sorted_freq[0][1] == 3 and sorted_freq[1][1] == 2:
        return "葫芦", HAND_RANK["葫芦"], [sorted_freq[0][0], sorted_freq[1][0]]
    if is_flush:
        return "同花", HAND_RANK["同花"], values
    if is_straight:
        return "顺子", HAND_RANK["顺子"], [straight_high]
    if sorted_freq[0][1] == 3:
        return "三条", HAND_RANK["三条"], [sorted_freq[0][0], sorted_freq[1][0], sorted_freq[2][0]]
    if sorted_freq[0][1] == 2 and sorted_freq[1][1] == 2:
        return "两对", HAND_RANK["两对"], [sorted_freq[0][0], sorted_freq[1][0], sorted_freq[2][0]]
    if sorted_freq[0][1] == 2:
        return "一对", HAND_RANK["一对"], [sorted_freq[0][0], sorted_freq[1][0], sorted_freq[2][0], sorted_freq[3][0]]
    return "高牌", HAND_RANK["高牌"], values

def compare_hands_best(hand1, hand2):
    _, rank1, vals1, _, _ = best_hand_with_wildcards(hand1)
    _, rank2, vals2, _, _ = best_hand_with_wildcards(hand2)
    if rank1 > rank2:
        return 1
    if rank1 < rank2:
        return -1
    for a,b in zip(vals1, vals2):
        if a > b:
            return 1
        if a < b:
            return -1
    return 0

def sort_hand_for_display(hand, hand_eval):
    _, rank_val, _, _, eff_vals = hand_eval
    cards_with_eff = [(hand[i], eff_vals[i], hand[i].is_wild()) for i in range(len(hand))]

    # 顺子 / 同花顺 / 皇家同花顺：按点数升序
    if rank_val in [HAND_RANK["顺子"], HAND_RANK["同花顺"], HAND_RANK["皇家同花顺"]]:
        effs = [eff for _, eff, _ in cards_with_eff]
        if 14 in effs and 2 in effs and len(set(effs)) == 5:
            cards_with_eff.sort(key=lambda x: 1 if x[1] == 14 else x[1])
        else:
            cards_with_eff.sort(key=lambda x: x[1])
        return [c for c, _, _ in cards_with_eff]

    # 非顺子类：先按出现次数，再按点数；同点数时，天然牌优先于万能牌
    from collections import Counter
    cnt = Counter(eff for _, eff, _ in cards_with_eff)
    cards_with_eff.sort(key=lambda x: (cnt[x[1]], x[1], not x[2]), reverse=True)
    return [c for c, _, _ in cards_with_eff]

# ------------------------- 游戏逻辑 -------------------------
class DJWildGame:
    def __init__(self):
        self.reset_game()
    def reset_game(self):
        self.deck = Deck()
        self.player_hand = []
        self.dealer_hand = []
        self.ante = self.blind = self.bonus_bet = self.double_side_bet = self.play_bet = 0
        self.stage = "pre_flop"
        self.folded = False
    def deal_initial(self):
        self.player_hand = self.deck.deal(5)
        self.dealer_hand = self.deck.deal(5)

# ------------------------- GUI -------------------------
class DJWildGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("DJ Wild梭哈扑克")
        self.geometry("1150x650+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')

        self.username = username
        self.balance = initial_balance
        self.game = DJWildGame()
        self.card_images = {}
        self.active_card_labels = []
        self.selected_chip = None
        self.chip_buttons = []
        self.last_win = 0
        self.auto_reset_timer = None
        self.bet_widgets = {}
        self._resetting = False
        self.restart_btn = None
        self.animation_queue = []      # 用于发牌动画队列
        self.animation_in_progress = False

        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------- 辅助 -------------------------
    def cancel_auto_reset_timer(self):
        if self.auto_reset_timer:
            try:
                self.after_cancel(self.auto_reset_timer)
            except:
                pass
            self.auto_reset_timer = None

    def on_close(self):
        self.cancel_auto_reset_timer()
        self.destroy()
        self.quit()

    def _load_assets(self):
        card_size = (100, 150)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # 每次开局交替：Poker1 -> Poker2 -> Poker1 -> ...
        cls = type(self)
        next_folder = getattr(cls, "_next_poker_folder", "Poker1")
        self.current_poker_folder = next_folder
        cls._next_poker_folder = "Poker2" if next_folder == "Poker1" else "Poker1"

        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', self.current_poker_folder)
        suit_mapping = {'♠': 'Spade', '♥': 'Heart', '♦': 'Diamond', '♣': 'Club', 'JOKER': 'JOKER'}

        self.original_images = {}

        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_img_orig = Image.open(back_path)
            self.original_images["back"] = back_img_orig
            back_img = back_img_orig.resize(card_size)
            self.back_image = ImageTk.PhotoImage(back_img)
        except Exception:
            img_orig = Image.new('RGB', card_size, 'black')
            self.original_images["back"] = img_orig
            self.back_image = ImageTk.PhotoImage(img_orig)

        for suit in SUITS + ['JOKER']:
            for rank in RANKS:
                if suit == 'JOKER':
                    filename = "JOKER-A.png"
                else:
                    filename = f"{suit_mapping[suit]}{rank}.png"

                path = os.path.join(card_dir, filename)
                try:
                    if os.path.exists(path):
                        img = Image.open(path)
                        self.original_images[(suit, rank)] = img
                        img_resized = img.resize(card_size)
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_resized)
                    else:
                        img_orig = Image.new('RGB', card_size, 'blue')
                        draw = ImageDraw.Draw(img_orig)
                        text = f"{rank}{suit}" if suit != 'JOKER' else "JOKER"
                        try:
                            font = ImageFont.truetype("arial.ttf", 20)
                        except:
                            font = ImageFont.load_default()
                        draw.text((10, 10), text, fill="white", font=font)
                        self.original_images[(suit, rank)] = img_orig
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
                except Exception as e:
                    print(f"Error loading {path}: {e}")

    def _create_widgets(self):
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=50, y=20, width=600, height=250)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.info_label = tk.Label(table_canvas, text="庄家在任何情况都会合格\n\"2\"和\"鬼牌\"均为万能牌，可以代替任何扑克", font=('Arial', 24),
                                   bg='#35654d', fg='#FFD700')
        self.info_label.place(x=350, y=320, anchor='center')

        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=50, y=365, width=600, height=250)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=250, padx=10, pady=5)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)

        info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=5)
        self.balance_label = tk.Label(info_frame, text=f"余额: ${self.balance:.2f}",
                                      font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=5)
        self.stage_label = tk.Label(info_frame, text="翻牌前", font=('Arial', 18, 'bold'),
                                    bg='#2a4a3c', fg='#FFD700')
        self.stage_label.pack(side=tk.RIGHT, padx=20, pady=5)

        chips_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        chips_frame.pack(fill=tk.X, pady=5)
        self.chips_label = tk.Label(chips_frame, text="筹码:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        self.chips_label.pack(anchor='w', padx=10, pady=5)
        self.chip_container = tk.Frame(chips_frame, bg='#2a4a3c')
        self.chip_container.pack(fill=tk.X, pady=5, padx=5)
        self._rebuild_chips()

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

        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=10)

        row1 = tk.Frame(bet_frame, bg='#2a4a3c')
        row1.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(row1, text="红利:", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT)
        self.bonus_var = tk.StringVar(value="0")
        self.bonus_display = tk.Label(row1, textvariable=self.bonus_var, font=('Arial', 14),
                                      bg='white', width=7, relief=tk.SUNKEN)
        self.bonus_display.pack(side=tk.LEFT, padx=5)
        self.bonus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bonus"))
        self.bet_widgets["bonus"] = self.bonus_display

        tk.Label(row1, text="  ", bg='#2a4a3c').pack(side=tk.LEFT, padx=5)
        tk.Label(row1, text="双向坏注:", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT)
        self.double_side_var = tk.StringVar(value="0")
        self.double_side_display = tk.Label(row1, textvariable=self.double_side_var, font=('Arial', 14),
                                            bg='white', width=7, relief=tk.SUNKEN)
        self.double_side_display.pack(side=tk.LEFT, padx=5)
        self.double_side_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("double_side"))
        self.bet_widgets["double_side"] = self.double_side_display

        row2 = tk.Frame(bet_frame, bg='#2a4a3c')
        row2.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(row2, text="底注:", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT)
        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(row2, textvariable=self.ante_var, font=('Arial', 14),
                                     bg='white', width=7, relief=tk.SUNKEN)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.bet_widgets["ante"] = self.ante_display

        tk.Label(row2, text="=", bg='#2a4a3c', font=('Arial', 14), fg='white').pack(side=tk.LEFT, padx=10)
        self.blind_var = tk.StringVar(value="0")
        self.blind_display = tk.Label(row2, textvariable=self.blind_var, font=('Arial', 14),
                                      bg='white', width=7, relief=tk.SUNKEN)
        self.blind_display.pack(side=tk.LEFT, padx=5)
        tk.Label(row2, text=":盲注", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT)
        self.bet_widgets["blind"] = self.blind_display

        row3 = tk.Frame(bet_frame, bg='#2a4a3c')
        row3.pack(fill=tk.X, padx=10, pady=3)
        self.play_label = tk.Label(row3, text="加注:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        self.play_label.pack(side=tk.LEFT)
        self.play_var = tk.StringVar(value="0")
        self.play_display = tk.Label(row3, textvariable=self.play_var, font=('Arial', 14),
                                     bg='white', width=7, relief=tk.SUNKEN)
        self.play_display.pack(side=tk.LEFT, padx=5)
        self.play_display.bind("<Button-1>", self.toggle_play_bet)
        self.bet_widgets["play"] = self.play_display

        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        self.action_frame.pack(fill=tk.X)
        start_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_frame.pack(pady=5)
        self.reset_bets_button = tk.Button(start_frame, text="重置金额", command=self.reset_bets,
                                           font=('Arial', 14), bg='#F44336', fg='white', width=10)
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0,10))
        self.start_button = tk.Button(start_frame, text="开始游戏", command=self.start_game,
                                      font=('Arial', 14), bg='#4CAF50', fg='white', width=10)
        self.start_button.pack(side=tk.LEFT)

        self.status_label = tk.Label(control_frame, text="设置下注金额并开始游戏",
                                     font=('Arial', 14), bg='#2a4a3c', fg='white')
        self.status_label.pack(pady=5, fill=tk.X)

        bet_info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_info_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.current_bet_label = tk.Label(bet_info_frame, text="本局下注: $0.00",
                                          font=('Arial', 12), bg='#2a4a3c', fg='white')
        self.current_bet_label.pack(pady=5, padx=10, anchor='w')
        self.last_win_label = tk.Label(bet_info_frame, text="上局获胜: $0.00",
                                       font=('Arial', 12), bg='#2a4a3c', fg='#FFD700')
        self.last_win_label.pack(pady=5, padx=10, anchor='w', side=tk.LEFT)
        rules_btn = tk.Button(bet_info_frame, text="ℹ️", command=self.show_game_instructions,
                              font=('Arial', 8), bg='#4B8BBE', fg='white')
        rules_btn.pack(side=tk.RIGHT, padx=10, pady=5)

        self.ante_var.trace_add('write', self._sync_blind)

    def _sync_blind(self, *args):
        try:
            ante = int(self.ante_var.get())
        except:
            ante = 0
        self.blind_var.set(str(ante))

    def toggle_play_bet(self, event=None):
        if self.game.stage != "pre_flop":
            return
        try:
            ante = int(self.ante_var.get())
        except:
            ante = 0
        if ante == 0:
            return
        if self.play_var.get() == "0":
            self.play_var.set(str(ante * 2))
        else:
            self.play_var.set("0")

    def add_chip_to_bet(self, bet_type):
        if not self.selected_chip:
            return
        chip_text = self.selected_chip.replace('$','')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K','')) * 1000
        else:
            chip_value = float(chip_text)
        max_ante = 10000
        max_side = 2500
        if bet_type == "ante":
            new_val = int(self.ante_var.get()) + chip_value
            if new_val > max_ante:
                new_val = max_ante
                messagebox.showwarning("下注限制", f"底注上限为{max_ante}，已自动调整")
            self.ante_var.set(str(int(new_val)))
        elif bet_type == "bonus":
            new_val = int(self.bonus_var.get()) + chip_value
            if new_val > max_side:
                new_val = max_side
                messagebox.showwarning("下注限制", f"红利上限为{max_side}，已自动调整")
            self.bonus_var.set(str(int(new_val)))
        elif bet_type == "double_side":
            new_val = int(self.double_side_var.get()) + chip_value
            if new_val > max_side:
                new_val = max_side
                messagebox.showwarning("下注限制", f"双向坏注上限为{max_side}，已自动调整")
            self.double_side_var.set(str(int(new_val)))

    def _rebuild_chips(self):
        for widget in self.chip_container.winfo_children():
            widget.destroy()
        self.chip_buttons = []
        self.selected_chip = None
        chip_configs = [('$10','orange','black'),("$25",'#00ff00','black'),("$100",'black','white'),
                        ("$500","#FF7DDA",'black'),("$1K",'white','black'),("$2.5K",'red','white')]
        default = "$10"
        self.chip_texts = {}
        for text, bg, fg in chip_configs:
            chip_canvas = tk.Canvas(self.chip_container, width=57, height=57, bg='#2a4a3c', highlightthickness=0)
            chip_canvas.create_oval(2,2,55,55, fill=bg, outline='black')
            chip_canvas.create_text(27.5,27.5, text=text, fill=fg, font=('Arial',14,'bold'))
            chip_canvas.bind("<Button-1>", lambda e,t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text
        self.select_chip(default)

    def select_chip(self, chip_text):
        self.selected_chip = chip_text
        for chip in self.chip_buttons:
            chip.delete("highlight")
            for item in chip.find_all():
                if chip.type(item)=='oval':
                    x1,y1,x2,y2 = chip.coords(item)
                    chip.create_oval(x1,y1,x2,y2, outline='black', width=2)
                    break
        for chip in self.chip_buttons:
            for item in chip.find_all():
                if chip.type(item)=='text' and chip.itemcget(item,'text') == chip_text:
                    oval = [i for i in chip.find_all() if chip.type(i)=='oval'][0]
                    x1,y1,x2,y2 = chip.coords(oval)
                    chip.create_oval(x1,y1,x2,y2, outline='gold', width=3, tags="highlight")
                    break

    # ------------------------- 发牌动画  -------------------------
    def animate_deal(self):
        """依次发牌：先玩家5张，再庄家5张"""
        self.animation_queue = []
        for i in range(5):
            self.animation_queue.append(("player", i, self.game.player_hand[i]))
        for i in range(5):
            self.animation_queue.append(("dealer", i, self.game.dealer_hand[i]))
        self.animation_in_progress = True
        self._process_animation_queue()

    def _process_animation_queue(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            self.after(500, self.reveal_player_cards)
            return

        who, idx, card = self.animation_queue.pop(0)

        if who == "player":
            frame = self.player_cards_frame
            target_x = idx * 110
            target_y = 0
        else:
            frame = self.dealer_cards_frame
            target_x = idx * 110
            target_y = 0

        label = tk.Label(frame, image=self.back_image, bg='#2a4a3c')
        label.card = card
        label.is_face_up = False
        self.active_card_labels.append(label)

        # 第 0 张牌直接放到位，不做 _animate_move
        if idx == 0:
            label.place(x=target_x, y=target_y, width=120, height=180)
            self._process_animation_queue()
            return

        label.place(x=0, y=0, width=110, height=120)
        self._animate_move(label, target_x, target_y)

    def _animate_move(self, label, target_x, target_y, step=0, steps=20, start_x=0, start_y=0):
        if step > steps:
            label.place(x=target_x, y=target_y, width=120, height=180)
            self._process_animation_queue()
            return

        cur_x = start_x + (target_x - start_x) * step / steps
        cur_y = start_y + (target_y - start_y) * step / steps
        label.place(x=cur_x, y=cur_y, width=120, height=180)
        self.after(20, lambda: self._animate_move(label, target_x, target_y, step + 1, steps, start_x, start_y))

    # ------------------------- 翻牌与排序 -------------------------
    def reveal_player_cards(self):
        for label in self.player_cards_frame.winfo_children():
            if hasattr(label, 'card') and not label.is_face_up:
                self.flip_card_animation(label)
        self.after(1000, self.start_player_sort_animation)

    def start_player_sort_animation(self):
        player_eval = best_hand_with_wildcards(self.game.player_hand)
        sorted_player = sort_hand_for_display(self.game.player_hand, player_eval)

        labels = list(self.player_cards_frame.winfo_children())
        start_positions = {}
        for label in labels:
            if label.winfo_exists():
                info = label.place_info()
                start_positions[label] = float(info.get('x', 0))

        target_positions = {}
        for idx, card in enumerate(sorted_player):
            for label in labels:
                if hasattr(label, 'card') and label.card == card:
                    target_positions[label] = idx * 110
                    break

        duration = 1500
        steps = 30
        interval = duration // steps

        anim_data = []
        for label in start_positions:
            start_x = start_positions[label]
            target_x = target_positions[label]
            dx = (target_x - start_x) / steps
            anim_data.append((label, start_x, dx))

        def animate_step(step):
            if step > steps or self._resetting:
                for label, _, _ in anim_data:
                    if label.winfo_exists():
                        target_x = target_positions[label]
                        label.place(x=target_x, y=0, width=120, height=180)

                self.game.player_hand = sorted_player
                self.after_player_sort()
                return

            for label, start_x, dx in anim_data:
                if label.winfo_exists():
                    new_x = start_x + dx * step
                    label.place(x=new_x, y=0, width=120, height=180)

            self.after(interval, lambda: animate_step(step + 1))

        animate_step(1)

    def after_player_sort(self):
        player_eval = best_hand_with_wildcards(self.game.player_hand)
        self.player_label.config(text=f"玩家 - {player_eval[0]}")
        if self.game.play_bet == 0 and not self.game.folded:
            for w in self.action_frame.winfo_children():
                if isinstance(w, tk.Frame):
                    for btn in w.winfo_children():
                        if isinstance(btn, tk.Button):
                            btn.config(state=tk.NORMAL)
        else:
            self.show_showdown()

    def play_action(self):
        for w in self.action_frame.winfo_children():
            if isinstance(w, tk.Frame):
                for btn in w.winfo_children():
                    if isinstance(btn, tk.Button):
                        btn.config(state=tk.DISABLED)
        play_bet = self.game.ante * 2
        if play_bet > self.balance:
            messagebox.showerror("错误", "余额不足")
            return
        self.balance -= play_bet
        self.update_balance()
        self.game.play_bet = play_bet
        self.play_var.set(str(play_bet))
        total = self.game.ante + self.game.blind + self.game.bonus_bet + self.game.double_side_bet + play_bet
        self.current_bet_label.config(text=f"本局下注: ${total:.2f}")
        self.game.stage = "showdown"
        self.stage_label.config(text="摊牌")
        self.status_label.config(text="摊牌中...")
        self.show_showdown()

    def fold_action(self):
        for w in self.action_frame.winfo_children():
            if isinstance(w, tk.Frame):
                for btn in w.winfo_children():
                    if isinstance(btn, tk.Button):
                        btn.config(state=tk.DISABLED)
        self.game.folded = True
        self.status_label.config(text="您已弃牌")
        self.reveal_dealer_cards(after_flip=self.start_dealer_sort_animation)

    def start_dealer_sort_animation(self):
        dealer_eval = best_hand_with_wildcards(self.game.dealer_hand)
        sorted_dealer = sort_hand_for_display(self.game.dealer_hand, dealer_eval)

        labels = list(self.dealer_cards_frame.winfo_children())
        start_positions = {}
        for label in labels:
            if label.winfo_exists():
                info = label.place_info()
                start_positions[label] = float(info.get('x', 0))

        target_positions = {}
        for idx, card in enumerate(sorted_dealer):
            for label in labels:
                if hasattr(label, 'card') and label.card == card:
                    target_positions[label] = idx * 110
                    break

        duration = 1500
        steps = 30
        interval = duration // steps

        anim_data = []
        for label in start_positions:
            start_x = start_positions[label]
            target_x = target_positions[label]
            dx = (target_x - start_x) / steps
            anim_data.append((label, start_x, dx))

        def animate_step(step):
            if step > steps or self._resetting:
                for label, _, _ in anim_data:
                    if label.winfo_exists():
                        target_x = target_positions[label]
                        label.place(x=target_x, y=0, width=120, height=180)

                self.game.dealer_hand = sorted_dealer
                self.after_dealer_sort()
                return

            for label, start_x, dx in anim_data:
                if label.winfo_exists():
                    new_x = start_x + dx * step
                    label.place(x=new_x, y=0, width=120, height=180)

            self.after(interval, lambda: animate_step(step + 1))

        animate_step(1)

    def after_dealer_sort(self):
        dealer_eval = best_hand_with_wildcards(self.game.dealer_hand)
        self.dealer_label.config(text=f"庄家 - {dealer_eval[0]}")
        if self.game.folded:
            self.settle_fold()
        else:
            self.settle_game()

    def reveal_dealer_cards(self, after_flip=None):
        to_flip = [lbl for lbl in self.dealer_cards_frame.winfo_children()
                   if hasattr(lbl, 'card') and not lbl.is_face_up]
        if not to_flip:
            if after_flip:
                after_flip()
            return
        for lbl in to_flip:
            self.flip_card_animation(lbl)
        self.after(1000, after_flip if after_flip else lambda: None)

    def flip_card_animation(self, label):
        card = label.card
        front_img = self.card_images.get((card.suit, card.rank), self.back_image)
        def animate(step=0):
            if step > 10:
                label.config(image=front_img)
                label.is_face_up = True
                label.place(width=120, height=180)
                return
            if step <= 5:
                width = 120 - step*12
                if width<1: width=1
                label.config(image=self.back_image)
            else:
                width = (step-5)*12
                if width<1: width=1
                label.config(image=front_img)
            label.place(width=width, height=180)
            self.after(50, lambda: animate(step+1))
        animate(0)

    def show_showdown(self):
        self.game.stage = "showdown"
        self.stage_label.config(text="摊牌")
        self.status_label.config(text="摊牌中...")
        self.reveal_dealer_cards(after_flip=self.start_dealer_sort_animation)

    def _animate_sort_moves(self, labels, target_pos, step=0, steps=20, after_callback=None):
        if step > steps:
            for lbl in labels:
                lbl.place(x=target_pos[lbl], y=0, width=120, height=180)
            if after_callback:
                after_callback()
            return
        for lbl in labels:
            cur_x = lbl.winfo_x()
            target_x = target_pos[lbl]
            new_x = cur_x + (target_x - cur_x) / steps
            lbl.place(x=new_x, y=0, width=120, height=180)
        self.after(20, lambda: self._animate_sort_moves(labels, target_pos, step+1, steps, after_callback))

    # ------------------------- 结算 -------------------------
    def settle_game(self):
        player_best = best_hand_with_wildcards(self.game.player_hand)
        dealer_best = best_hand_with_wildcards(self.game.dealer_hand)
        player_rank_name, player_rank_val, _, _, _ = player_best
        dealer_rank_name, dealer_rank_val, _, _, _ = dealer_best

        comp = compare_hands_best(self.game.player_hand, self.game.dealer_hand)
        winnings = 0
        details = {"ante":0, "blind":0, "play":0, "bonus":0, "double_side":0}

        if comp == 1:
            details["ante"] = self.game.ante * 2
            details["play"] = self.game.play_bet * 2
        elif comp == 0:
            details["ante"] = self.game.ante
            details["play"] = self.game.play_bet
        winnings += details["ante"] + details["play"]

        if comp == 1:
            blind_payout = BLIND_PAYOUT.get(player_rank_name, 0)
            details["blind"] = self.game.blind * (blind_payout + 1)
        elif comp == 0:
            details["blind"] = self.game.blind
        winnings += details["blind"]

        bonus_win = self.calculate_bonus(self.game.player_hand)
        details["bonus"] = bonus_win
        winnings += bonus_win

        double_win = self.calculate_double_side(player_rank_val, dealer_rank_val)
        details["double_side"] = double_win
        winnings += double_win

        self.balance += winnings
        self.update_balance()
        self.last_win = winnings
        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")
        self._update_bet_display(details)
        self.show_restart_button()

    def settle_fold(self):
        bonus_win = self.calculate_bonus(self.game.player_hand)
        if bonus_win > 0:
            self.balance += bonus_win
            self.update_balance()
            self.bonus_display.config(bg='gold')
            self.bonus_var.set(str(int(bonus_win)))
        else:
            self.bonus_display.config(bg='white')
            self.bonus_var.set("0")
        self.ante_display.config(bg='white')
        self.ante_var.set("0")
        self.blind_display.config(bg='white')
        self.blind_var.set("0")
        self.play_display.config(bg='white')
        self.play_var.set("0")
        self.double_side_display.config(bg='white')
        self.double_side_var.set("0")
        self.last_win = bonus_win
        self.last_win_label.config(text=f"上局获胜: ${bonus_win:.2f}")
        self.show_restart_button()

    def _update_bet_display(self, details):
        # 底注
        if details["ante"] > self.game.ante:
            self.ante_display.config(bg='gold')
            self.ante_var.set(str(int(details["ante"])))
        elif details["ante"] == self.game.ante and self.game.ante > 0:
            self.ante_display.config(bg='light blue')
            self.ante_var.set(str(int(details["ante"])))
        else:
            self.ante_display.config(bg='white')
            self.ante_var.set("0")
        # 加注
        if details["play"] > self.game.play_bet:
            self.play_display.config(bg='gold')
            self.play_var.set(str(int(details["play"])))
        elif details["play"] == self.game.play_bet and self.game.play_bet > 0:
            self.play_display.config(bg='light blue')
            self.play_var.set(str(int(details["play"])))
        else:
            self.play_display.config(bg='white')
            self.play_var.set("0")
        # 盲注
        if details["blind"] > self.game.blind:
            self.blind_display.config(bg='gold')
            self.blind_var.set(str(int(details["blind"])))
        elif details["blind"] == self.game.blind and self.game.blind > 0:
            self.blind_display.config(bg='light blue')
            self.blind_var.set(str(int(details["blind"])))
        else:
            self.blind_display.config(bg='white')
            self.blind_var.set("0")
        # 红利
        if details["bonus"] > 0:
            self.bonus_display.config(bg='gold')
            self.bonus_var.set(str(int(details["bonus"])))
        else:
            self.bonus_display.config(bg='white')
            self.bonus_var.set("0")
        # 双向坏注
        if details["double_side"] > 0:
            self.double_side_display.config(bg='gold')
            self.double_side_var.set(str(int(details["double_side"])))
        else:
            self.double_side_display.config(bg='white')
            self.double_side_var.set("0")

    def calculate_bonus(self, hand):
        """计算红利奖金，返回总返还（本金+盈利）"""
        if self.game.bonus_bet == 0:
            return 0

        # 如果没有万能牌，直接正常结算（无万能牌）
        if not any(c.is_wild() for c in hand):
            rank_name, _, _, _, _ = best_hand_with_wildcards(hand)
            payout = BONUS_PAYOUT.get((rank_name, False), 0)
            return self.game.bonus_bet * (payout + 1) if payout else 0

        # 有万能牌，分情况比较
        payout_a = 0  # 情况A：万能牌不变（仅当没有JOKER时有效）
        if not any(c.is_joker for c in hand):
            # 构建“万能牌不变”的手牌：将2视为普通2，其他牌不变
            hand_no_wild = []
            for c in hand:
                if c.rank == '2' and not c.is_joker:
                    hand_no_wild.append(Card(c.suit, '2'))   # 普通2
                else:
                    hand_no_wild.append(Card(c.suit, c.rank))
            # 评估固定手牌（无万能牌）
            rank_name_a, _, _ = evaluate_fixed_hand(hand_no_wild)
            payout_a = BONUS_PAYOUT.get((rank_name_a, False), 0)

        # 情况B：万能牌可变，得到最佳牌型（有万能牌）
        rank_name_b, _, _, _, _ = best_hand_with_wildcards(hand)
        payout_b = BONUS_PAYOUT.get((rank_name_b, True), 0)

        # 取较大赔付倍率，相等时优先采用情况A（无万能牌）
        final_payout = payout_a if payout_a >= payout_b else payout_b

        if final_payout:
            return self.game.bonus_bet * (final_payout + 1)
        return 0

    def calculate_double_side(self, player_rank_val, dealer_rank_val):
        """计算双向坏注奖金，返回总返还（本金+盈利）"""
        if self.game.double_side_bet == 0:
            return 0
        if player_rank_val < 3 or dealer_rank_val < 3:
            return 0
        lower_rank = min(player_rank_val, dealer_rank_val)
        lower_rank_name = HAND_RANK_NAMES[lower_rank]
        payout = DOUBLE_SIDE_PAYOUT.get(lower_rank_name, 0)
        if payout:
            # 返回本金 + 盈利
            return self.game.double_side_bet * (payout + 1)
        return 0

    def show_restart_button(self):
        for w in self.action_frame.winfo_children():
            w.destroy()
        self.stage_label.config(text="结算")
        self.status_label.config(text="游戏结束")
        self.restart_btn = tk.Button(self.action_frame, text="再来一局", command=self.reset_game,
                                     font=('Arial',14), bg='#2196F3', fg='white', width=15)
        self.restart_btn.pack(pady=5)
        self.restart_btn.bind("<Button-3>", self.show_card_sequence)
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    # ------------------------- 收牌动画（向右移出） -------------------------
    def animate_collect_cards(self, auto_reset):
        self.active_card_labels = [lbl for lbl in self.active_card_labels if lbl.winfo_exists()]
        if not self.active_card_labels:
            self._do_reset(auto_reset)
            return
        for lbl in self.active_card_labels:
            lbl.target_pos = (1200, lbl.winfo_y())
        self.animate_card_out_step(auto_reset)

    def animate_card_out_step(self, auto_reset):
        all_done = True
        for lbl in self.active_card_labels[:]:
            if not hasattr(lbl, 'target_pos') or not lbl.winfo_exists():
                if lbl in self.active_card_labels:
                    self.active_card_labels.remove(lbl)
                continue
            cur_x = lbl.winfo_x()
            target_x = lbl.target_pos[0]
            dx = target_x - cur_x
            if abs(dx) < 5:
                lbl.destroy()
                if lbl in self.active_card_labels:
                    self.active_card_labels.remove(lbl)
                continue
            new_x = cur_x + dx * 0.2
            lbl.place(x=new_x)
            all_done = False
        if not all_done:
            self.after(20, lambda: self.animate_card_out_step(auto_reset))
        else:
            self._do_reset(auto_reset)

    def reset_game(self, auto_reset=False):
        self.cancel_auto_reset_timer()
        if self.restart_btn and self.restart_btn.winfo_exists():
            self.restart_btn.config(state=tk.DISABLED)
        self._resetting = True
        for after_id in self.tk.eval('after info').split():
            try:
                self.after_cancel(after_id)
            except:
                pass
        if self.active_card_labels:
            self.animate_collect_cards(auto_reset)
            return
        self._do_reset(auto_reset)

    def _do_reset(self, auto_reset=False):
        for w in self.dealer_cards_frame.winfo_children():
            w.destroy()
        for w in self.player_cards_frame.winfo_children():
            w.destroy()
        self.active_card_labels = []
        self.game.reset_game()
        self.stage_label.config(text="翻牌前")
        self.status_label.config(text="设置下注金额并开始游戏")
        self.player_label.config(text="玩家")
        self.dealer_label.config(text="庄家")
        self.ante_var.set("0")
        self.bonus_var.set("0")
        self.double_side_var.set("0")
        self.play_var.set("0")
        self.current_bet_label.config(text="本局下注: $0.00")
        self._resetting = False

        # 重置所有下注背景为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')

        # 恢复下注控件绑定
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.bonus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bonus"))
        self.double_side_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("double_side"))
        self.play_display.bind("<Button-1>", self.toggle_play_bet)
        for chip in self.chip_buttons:
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))

        # 重建开始按钮区
        for w in self.action_frame.winfo_children():
            w.destroy()
        start_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_frame.pack(pady=5)
        self.reset_bets_button = tk.Button(start_frame, text="重置金额", command=self.reset_bets,
                                           font=('Arial',14), bg='#F44336', fg='white', width=10)
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0,10))
        self.start_button = tk.Button(start_frame, text="开始游戏", command=self.start_game,
                                      font=('Arial',14), bg='#4CAF50', fg='white', width=10)
        self.start_button.pack(side=tk.LEFT)

        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))

    def reset_bets(self):
        self.ante_var.set("0")
        self.bonus_var.set("0")
        self.double_side_var.set("0")
        self.play_var.set("0")
        self.status_label.config(text="已重置所有下注金额")
        for w in self.bet_widgets.values():
            w.config(bg='white')
        self.after(500, lambda: self.ante_display.config(bg='white'))
        self.after(500, lambda: self.bonus_display.config(bg='white'))
        self.after(500, lambda: self.double_side_display.config(bg='white'))
        self.after(500, lambda: self.play_display.config(bg='white'))

    def show_game_instructions(self):
        """显示游戏规则和赔付表的详细窗口"""
        win = tk.Toplevel(self)
        win.title("DJ Wild梭哈扑克 - 游戏规则与赔付表")
        win.geometry("1000x750")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')

        # 主框架 + 滚动条
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        canvas = tk.Canvas(main_frame, bg='#F0F0F0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)

        content_frame = tk.Frame(canvas, bg='#F0F0F0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')

        # ========== 规则文本 ==========
        rules_text = """
        DJ Wild梭哈扑克 游戏规则

        1. 万能牌（Wild Card）：
        - 所有点数 2 的牌 以及 JOKER 均为万能牌。
        - 万能牌可以变成任意点数（2~A）和任意花色，用于组成最佳牌型。

        2. 下注类型：
        a. 底注：必须下注，自动同步为盲注的金额。
        b. 盲注：金额自动等于底注，无需单独设置。
        c. 红利：可选下注，根据玩家手牌（包括万能牌）支付，赢则同时赢取红利注。
        d. 双向坏注：可选下注，同时比较玩家与庄家牌型，取较低牌型支付。
        e. 加注：决策阶段可选，金额为底注×2。

        3. 游戏流程：
        a. 下注阶段：设置底注（盲注自动同步）、可选下注（红利、双向坏注），点击“开始游戏”。
        b. 发牌：玩家和庄家各发5张牌，所有牌面朝下。
        c. 翻牌：玩家牌全部翻开，系统自动结算红利（若下注）。
        d. 决策阶段（仅当未预下加注时）：
            - 弃牌：输掉底注、盲注，但红利和双向坏注仍可能赢。
            - 下注2倍：支付底注×2作为加注，进入摊牌。
        e. 摊牌：庄家牌全部翻开，比较玩家与庄家最终5张牌（使用万能牌的最佳组合）。
            - 玩家赢：底注、盲注、加注均按赔率支付（盲注见下方赔率表）。
            - 平局：退还所有下注（红利、双向坏注单独结算）。
            - 玩家输：底注、盲注、加注输掉。

        4. 红利结算：
        - 仅根据玩家手牌（含万能牌）支付。
        - 赔付倍率区分“无万能牌”（即手牌中无JOKER且2不作为万能，仅视为普通2）和“有万能牌”两种情况，取较高者。

        5. 双向坏注结算：
        - 需要玩家和庄家牌型等级均 ≥ 三条。
        - 取两者中较低的牌型等级，按下方赔付表支付。

        6. 注意：盲注赔率、红利赔率、双向坏注赔率均基于下注额 × 赔付倍数（含本金返回）。
        """

        tk.Label(content_frame, text=rules_text, font=('微软雅黑', 11),
                bg='#F0F0F0', justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X, padx=10, pady=5)

        # ========== 标题 ==========
        tk.Label(content_frame, text="赔付表汇总", font=('微软雅黑', 14, 'bold'),
                bg='#F0F0F0').pack(fill=tk.X, padx=10, pady=(20, 10), anchor='center')

        bonus_frame = tk.Frame(content_frame, bg='#F0F0F0')
        bonus_frame.pack(fill=tk.X, padx=20, pady=5)

        bonus_headers = ["牌型", "盲注#", "红利(有万能牌)##", "红利(无万能牌)", "双向坏注"]
        bonus_data = [
            ("五张王牌", "1000:1", "2000:1", "-", "-"),
            ("皇家同花顺", "50:1", "90:1", "1000:1", "10000:1"),
            ("五条", "10:1", "70:1", "-", "10000:1"),
            ("同花顺", "9:1", "25:1", "200:1", "5000:1"),
            ("四条", "4:1", "6:1", "60:1", "500:1"),
            ("葫芦", "3:1", "5:1", "30:1", "400:1"),
            ("同花", "2:1", "4:1", "25:1", "100:1"),
            ("顺子", "1:1", "3:1", "20:1", "100:1"),
            ("三条", "平局", "1:1", "6:1", "9:1"),
            ("其他", "平局", "平局", "平局", "平局")
        ]

        for col, h in enumerate(bonus_headers):
            tk.Label(bonus_frame, text=h, font=('微软雅黑', 10, 'bold'),
                    bg='#4B8BBE', fg='white', padx=10, pady=5,
                    anchor='center', justify='center').grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
        for r, row in enumerate(bonus_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row):
                tk.Label(bonus_frame, text=txt, font=('微软雅黑', 10), bg=bg,
                        padx=10, pady=5, anchor='center').grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
        for c in range(len(bonus_headers)):
            bonus_frame.columnconfigure(c, weight=1)

        # ========== 补充说明 ==========
        notes = """
        注：
        - 所有赔付倍率为盈利倍数，实际返还金额 = 下注额 × (赔率倍数 + 1)。
        - 红利结算时，系统会分别计算“无万能牌”（即2视为普通2）和“有万能牌”的最佳牌型，取赔付较高的结果。
        - 双向坏注：需要双方牌型均 ≥ 三条，且只对较低的牌型支付。

        #  盲注的获胜条件是击败庄家。
        ## JOKER 始终视为万能牌；普通 2 在无万能牌计算时视为普通2，在有万能牌计算时可变为任意牌。
        """
        tk.Label(content_frame, text=notes, font=('微软雅黑', 10),
                bg='#F0F0F0', justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X, padx=10, pady=10)

        # 更新滚动区域
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

        # 关闭按钮
        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)

        # 鼠标滚轮绑定
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def show_card_sequence(self, event):
        """显示本局牌序窗口 - 右键点击时取消30秒计时"""
        # 取消30秒自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None

        win = tk.Toplevel(self)
        win.title("本局牌序")
        win.geometry("650x600")
        win.resizable(0,0)
        win.configure(bg='#f0f0f0')

        # 获取牌堆信息
        deck = self.game.deck
        cut_pos = deck.cut_position
        card_sequence = deck.full_deck   # 牌堆中所有牌（按切牌后顺序）

        cut_label = tk.Label(
            win,
            text=f"本局切牌位置: {cut_pos + 1}",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0'
        )
        cut_label.pack(pady=(10, 5))

        main_frame = tk.Frame(win, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        canvas = tk.Canvas(main_frame, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)

        content_frame = tk.Frame(canvas, bg='#f0f0f0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')

        card_frame = tk.Frame(content_frame, bg='#f0f0f0')
        card_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        small_size = (60, 90)
        small_images = {}

        for i, card in enumerate(card_sequence):
            key = (card.suit, card.rank)
            if key in self.original_images:
                orig_img = self.original_images[key]
                small_img = orig_img.resize(small_size, Image.LANCZOS)
                small_images[i] = ImageTk.PhotoImage(small_img)
            else:
                # 找不到原图时使用背面占位
                if "back" in self.original_images:
                    back_img = self.original_images["back"]
                    small_img = back_img.resize(small_size, Image.LANCZOS)
                    small_images[i] = ImageTk.PhotoImage(small_img)

        # 7行，前6行每行8张，第7行5张
        for row in range(7):
            row_frame = tk.Frame(card_frame, bg='#f0f0f0')
            row_frame.pack(fill=tk.X, pady=5)

            cards_in_row = 8 if row < 6 else 5
            for col in range(cards_in_row):
                card_index = row * 8 + col
                if card_index >= len(card_sequence):
                    break

                card_container = tk.Frame(row_frame, bg='#f0f0f0')
                card_container.grid(row=0, column=col, padx=5, pady=5)

                bg_color = 'light blue' if card_index == cut_pos else '#f0f0f0'

                if card_index in small_images:
                    card_label = tk.Label(
                        card_container,
                        image=small_images[card_index],
                        bg=bg_color,
                        borderwidth=1,
                        relief="solid"
                    )
                    card_label.image = small_images[card_index]
                    card_label.pack()
                else:
                    card = card_sequence[card_index]
                    card_label = tk.Label(
                        card_container,
                        text=f"{card.rank}{card.suit}",
                        bg=bg_color,
                        width=6,
                        height=3,
                        borderwidth=1,
                        relief="solid"
                    )
                    card_label.pack()

                pos_label = tk.Label(
                    card_container,
                    text=str(card_index + 1),
                    bg=bg_color,
                    font=('Arial', 9)
                )
                pos_label.pack()

        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)

    def start_game(self):
        try:
            ante = int(self.ante_var.get())
            bonus = int(self.bonus_var.get())
            double_side = int(self.double_side_var.get())
            play = int(self.play_var.get())
        except:
            messagebox.showerror("错误", "请输入有效的下注金额")
            return

        min_ante, max_ante, max_side = 10, 10000, 2500
        if ante < min_ante:
            messagebox.showerror("错误", f"底注至少需要{min_ante}")
            return
        if ante > max_ante:
            self.ante_var.set(str(max_ante))
            ante = max_ante
            messagebox.showwarning("下注限制", f"底注上限为{max_ante}，已自动调整")
        if bonus > max_side:
            self.bonus_var.set(str(max_side))
            bonus = max_side
            messagebox.showwarning("下注限制", f"红利上限为{max_side}，已自动调整")
        if double_side > max_side:
            self.double_side_var.set(str(max_side))
            double_side = max_side
            messagebox.showwarning("下注限制", f"双向坏注上限为{max_side}，已自动调整")

        blind = ante
        total_bet = ante + blind + bonus + double_side + play
        if total_bet > self.balance:
            messagebox.showerror("错误", "余额不足")
            return

        self.balance -= total_bet
        self.update_balance()

        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        self.last_win_label.config(text="上局获胜: $0.00")

        # 每一局重新载入图片，并按 Poker1 -> Poker2 -> Poker1... 交替
        self._load_assets()

        self.game.reset_game()
        self.game.deal_initial()
        self.game.ante = ante
        self.game.blind = blind
        self.game.bonus_bet = bonus
        self.game.double_side_bet = double_side
        self.game.play_bet = play

        for w in self.dealer_cards_frame.winfo_children():
            w.destroy()
        for w in self.player_cards_frame.winfo_children():
            w.destroy()
        self.active_card_labels = []

        for w in self.action_frame.winfo_children():
            w.destroy()

        if play == 0:
            self.stage_label.config(text="决策")
            self.status_label.config(text="做出决策: 弃牌或下注2倍")
            action_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
            action_frame.pack(pady=5)
            self.fold_button = tk.Button(action_frame, text="弃牌", command=self.fold_action,
                                        state=tk.DISABLED, font=('Arial', 14), bg='#F44336', fg='white', width=10)
            self.fold_button.pack(side=tk.LEFT, padx=(0, 10))
            self.play_button = tk.Button(action_frame, text="下注2倍", command=self.play_action,
                                        state=tk.DISABLED, font=('Arial', 14), bg='#4CAF50', fg='white', width=10)
            self.play_button.pack(side=tk.LEFT)
        else:
            self.game.stage = "showdown"
            self.stage_label.config(text="摊牌")
            self.status_label.config(text="盲注模式，等待结算")

        self.ante_display.unbind("<Button-1>")
        self.bonus_display.unbind("<Button-1>")
        self.double_side_display.unbind("<Button-1>")
        self.play_display.unbind("<Button-1>")
        for chip in self.chip_buttons:
            chip.unbind("<Button-1>")

        self.animate_deal()

def main(initial_balance=10000, username="Guest"):
    app = DJWildGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")