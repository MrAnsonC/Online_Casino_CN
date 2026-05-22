import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import json
import os
import secrets
import subprocess
import sys
from itertools import combinations, product
from collections import Counter

# ------------------------- 基础数据 -------------------------
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
RANK_VALUES['JOKER'] = 99

HAND_RANK = {
    "五条": 10,
    "同花大顺": 9,
    "同花顺": 8,
    "四条": 7,
    "葫芦": 6,
    "同花": 5,
    "顺子": 4,
    "三条": 3,
    "两对": 2,
    "对子": 1,
    "高牌": 0
}
HAND_RANK_NAMES = {v: k for k, v in HAND_RANK.items()}

# 盲注赔率（玩家赢时生效，倍数 = 赔率:1，下注1赢赔率，共返还下注+赔率）
BLIND_PAYOUT = {
    10: 100,   # 五条
    9: 50,     # 同花大顺
    8: 10,     # 同花顺
    7: 5,      # 四条
    6: 3,      # 葫芦
    5: 2,      # 同花1
    4: 1,      # 顺子
    # 其他牌型为 0
}

# 原始五赔率（单独边注，达到牌型即按赔率:1支付）
ORIGINAL_FIVE_PAYOUT = {
    10: 1000,  # 五条
    9: 500,    # 同花大顺
    8: 250,    # 同花顺
    7: 100,    # 四条
    6: 50,     # 葫芦
    5: 25,     # 同花
    4: 10,     # 顺子
    3: 5,      # 三条
    2: 5,      # 两对
    # 其他牌型为 0 (输)
}

ANTE_PAYOUT = 1
PPAIR_PAYOUTS = [
    ("A-A", 23),
    ("A-K (同花)", 19),
    ("A-Q (同花) 或 A-J (同花)", 16),
    ("A-K", 11),
    ("K-K, Q-Q, 或 J-J", 8),
    ("其中一张为Joker", 6),
    ("A-Q 或 A-J", 4),
    ("其他对子 (10-10 到 2-2)", 2),
]

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
        if user.get('user_name') == username:
            user['cash'] = f"{new_balance:.2f}"
            break
    save_user_data(users)

def card_copy(card):
    new_card = Card(card.suit, card.rank)
    for attr in ('source', 'deal_index', 'is_public', 'is_discard'):
        if hasattr(card, attr):
            setattr(new_card, attr, getattr(card, attr))
    return new_card

# ------------------------- 卡牌 -------------------------
class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.is_joker = (suit == 'JOKER') or (rank == 'JOKER')
        self.value = 99 if self.is_joker else RANK_VALUES[rank]

    def __repr__(self):
        if self.is_joker:
            return "JOKER"
        return f"{self.rank}{self.suit}"

    def __eq__(self, other):
        return isinstance(other, Card) and self.suit == other.suit and self.rank == other.rank and self.is_joker == other.is_joker

    def __hash__(self):
        return hash((self.suit, self.rank, self.is_joker))

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
                capture_output=True,
                text=True,
                encoding='utf-8',
                env=env,
                check=True,
                timeout=30
            )
            shuffle_data = json.loads(result.stdout)
            self.full_deck = [Card(d["suit"], d["rank"]) for d in shuffle_data["deck"]]
            self.cut_position = shuffle_data["cut_position"]
        except Exception:
            self.full_deck = [Card(s, r) for s in SUITS for r in RANKS] + [Card('JOKER', 'JOKER')]
            self._secure_shuffle()
            self.cut_position = secrets.randbelow(len(self.full_deck))
        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + i) % len(self.full_deck) for i in range(len(self.full_deck))]
        self.pointer = 0

    def _secure_shuffle(self):
        for i in range(len(self.full_deck) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            self.full_deck[i], self.full_deck[j] = self.full_deck[j], self.full_deck[i]

    def deal(self, n=1):
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt

# ------------------------- 手牌评估 -------------------------
def _rank_counts(cards):
    values = [c.value for c in cards]
    return Counter(values)

def evaluate_fixed_hand(cards):
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    is_flush = len(set(suits)) == 1

    uniq = sorted(set(values))
    is_straight = False
    straight_high = 0
    if len(uniq) == 5:
        if uniq[-1] - uniq[0] == 4:
            is_straight = True
            straight_high = uniq[-1]
        elif uniq == [2, 3, 4, 5, 14]:
            is_straight = True
            straight_high = 5

    freq = Counter(values)
    by_cnt = sorted(freq.items(), key=lambda x: (x[1], x[0]), reverse=True)
    counts = sorted(freq.values(), reverse=True)

    if is_flush and is_straight:
        if set(values) == {10, 11, 12, 13, 14}:
            return "同花大顺", HAND_RANK["同花大顺"], [14]
        return "同花顺", HAND_RANK["同花顺"], [straight_high]

    if counts[0] == 5:
        return "五条", HAND_RANK["五条"], [by_cnt[0][0]]
    if counts[0] == 4:
        four = by_cnt[0][0]
        kicker = max(v for v in values if v != four)
        return "四条", HAND_RANK["四条"], [four, kicker]
    if counts[0] == 3 and counts[1] == 2:
        trips = by_cnt[0][0]
        pair = by_cnt[1][0]
        return "葫芦", HAND_RANK["葫芦"], [trips, pair]
    if is_flush:
        return "同花", HAND_RANK["同花"], values
    if is_straight:
        return "顺子", HAND_RANK["顺子"], [straight_high]
    if counts[0] == 3:
        trips = by_cnt[0][0]
        kickers = sorted([v for v in values if v != trips], reverse=True)
        return "三条", HAND_RANK["三条"], [trips] + kickers
    if counts[0] == 2 and counts[1] == 2:
        pair_vals = sorted([v for v, cnt in freq.items() if cnt == 2], reverse=True)
        kicker = max(v for v, cnt in freq.items() if cnt == 1)
        return "两对", HAND_RANK["两对"], pair_vals + [kicker]
    if counts[0] == 2:
        pair = by_cnt[0][0]
        kickers = sorted([v for v in values if v != pair], reverse=True)
        return "对子", HAND_RANK["对子"], [pair] + kickers
    return "高牌", HAND_RANK["高牌"], values

def best_hand_with_joker(cards):
    """
    输入 5 张牌，返回:
    (牌型名, 牌型值, 比较值列表, 最佳替换后的 5 张牌, 替换后数值列表)
    其中最佳5张牌中的 Joker 保留原 Joker 牌面（显示用），但评估时已按最佳替换计算。
    """
    joker_indices = [i for i, c in enumerate(cards) if c.is_joker]
    if not joker_indices:
        rank_name, rank_val, cmp_vals = evaluate_fixed_hand(cards)
        return rank_name, rank_val, cmp_vals, [card_copy(c) for c in cards], [c.value for c in cards]

    possible_values = list(range(2, 15))
    possible_suits = SUITS
    best = None

    for values_combo in product(possible_values, repeat=len(joker_indices)):
        for suits_combo in product(possible_suits, repeat=len(joker_indices)):
            trial = [card_copy(c) for c in cards]
            for idx_pos, card_idx in enumerate(joker_indices):
                trial[card_idx] = Card(suits_combo[idx_pos], RANKS[values_combo[idx_pos] - 2])
            rank_name, rank_val, cmp_vals = evaluate_fixed_hand(trial)
            key = (rank_val, cmp_vals)
            if best is None or key > best[0]:
                best = (key, rank_name, rank_val, cmp_vals, trial, [c.value for c in trial])

    _, rank_name, rank_val, cmp_vals, trial, eff_vals = best

    # 将 trial 中的 Joker 位置替换回原 Joker 对象（保持显示为 Joker 牌面）
    for idx_pos, card_idx in enumerate(joker_indices):
        trial[card_idx] = cards[card_idx]   # 恢复为原始 Joker

    return rank_name, rank_val, cmp_vals, trial, eff_vals

def compare_hands_best(cards1, cards2):
    h1 = best_hand_from_cards(cards1)
    h2 = best_hand_from_cards(cards2)
    if h1[1] > h2[1]:
        return 1
    if h1[1] < h2[1]:
        return -1
    for a, b in zip(h1[2], h2[2]):
        if a > b:
            return 1
        if a < b:
            return -1
    return 0

def best_hand_from_cards(cards):
    if len(cards) == 5:
        rank_name, rank_val, cmp_vals, eff_cards, eff_vals = best_hand_with_joker(cards)
        return rank_name, rank_val, cmp_vals, eff_cards, tuple(range(5)), [getattr(c, 'source', '') == 'public' for c in eff_cards], eff_vals

    best = None
    for idxs in combinations(range(len(cards)), 5):
        subset = [cards[i] for i in idxs]
        rank_name, rank_val, cmp_vals, eff_cards, eff_vals = best_hand_with_joker(subset)
        key = (rank_val, cmp_vals)
        if best is None or key > best[0]:
            used_public = [getattr(c, 'source', '') == 'public' for c in subset]
            best = (key, rank_name, rank_val, cmp_vals, eff_cards, idxs, used_public, eff_vals)
    _, rank_name, rank_val, cmp_vals, eff_cards, idxs, used_public, eff_vals = best
    return rank_name, rank_val, cmp_vals, eff_cards, idxs, used_public, eff_vals

def sort_hand_for_display(hand):
    rank_name, rank_val, cmp_vals, best_cards, eff_vals = best_hand_with_joker(hand)

    cards_with_eff = []
    for i, card in enumerate(hand):
        eff = eff_vals[i]
        cards_with_eff.append((card, eff))

    if rank_val in [9, 8, 4]:
        values = [x[1] for x in cards_with_eff]
        if set(values) == {14, 2, 3, 4, 5}:
            cards_with_eff.sort(key=lambda x: 1 if x[1] == 14 else x[1])
        else:
            cards_with_eff.sort(key=lambda x: x[1])
        return [x[0] for x in cards_with_eff]

    counter = Counter([x[1] for x in cards_with_eff])
    cards_with_eff.sort(key=lambda x: (counter[x[1]], x[1]), reverse=True)
    return [x[0] for x in cards_with_eff]

def classify_hand_for_display(cards):
    return best_hand_with_joker(cards)[0]

def get_public_pair_payout(public_cards):
    if len(public_cards) != 2:
        return 0
    c1, c2 = public_cards
    r1, r2 = c1.rank, c2.rank
    s1, s2 = c1.suit, c2.suit

    if c1.is_joker or c2.is_joker:
        return 6
    if r1 == r2:
        if r1 == 'A':
            return 23
        if r1 in ('K', 'Q', 'J'):
            return 8
        if r1 in ('10', '9', '8', '7', '6', '5', '4', '3', '2'):
            return 2
        return 0

    suited = (s1 == s2)
    ranks = {r1, r2}
    if ranks == {'A', 'K'} and suited:
        return 19
    if ranks in ({'A', 'Q'}, {'A', 'J'}) and suited:
        return 16
    if ranks == {'A', 'K'} and not suited:
        return 11
    if ranks in ({'A', 'Q'}, {'A', 'J'}) and not suited:
        return 4
    return 0

def is_four_card_flush(cards):
    """判断是否至少有4张同花（含Joker作为万能花色）"""
    suits = [c.suit for c in cards if not c.is_joker]
    if not suits:
        return False
    suit_counts = Counter(suits)
    max_suit_cnt = max(suit_counts.values())
    joker_count = sum(1 for c in cards if c.is_joker)
    if max_suit_cnt + joker_count >= 4:
        return True
    return False

def is_outside_straight_draw(cards):
    """判断是否为两头顺听牌（包含Joker）"""
    values = [c.value for c in cards if not c.is_joker]
    joker_cnt = sum(1 for c in cards if c.is_joker)
    if joker_cnt > 0:
        for v in range(2, 15):
            all_vals = sorted(values + [v])
            uniq_vals = sorted(set(all_vals))
            for i in range(len(uniq_vals) - 3):
                if uniq_vals[i+3] - uniq_vals[i] == 3:
                    return True
        return False
    else:
        values = sorted(set(values))
        if len(values) < 4:
            return False
        for i in range(len(values) - 3):
            if values[i+3] - values[i] == 3:
                return True
        return False
    
def dealer_discard_card(cards):
    rank_name = best_hand_from_cards(cards)[0]

    made_hands = {"顺子", "同花", "葫芦", "同花顺", "同花大顺", "五条"}
    if rank_name in made_hands:
        return None

    if is_four_card_flush(cards):
        real_suits = [c.suit for c in cards if not c.is_joker]
        if real_suits:
            keep_suit = Counter(real_suits).most_common(1)[0][0]
        else:
            keep_suit = None
        candidates = [c for c in cards if not c.is_joker and c.suit != keep_suit]
        if candidates:
            return min(candidates, key=lambda c: c.value)
        non_jokers = [c for c in cards if not c.is_joker]
        if non_jokers:
            return min(non_jokers, key=lambda c: c.value)
        return None

    if is_outside_straight_draw(cards):
        freq = Counter(c.value for c in cards if not c.is_joker)
        singles = [c for c in cards if freq.get(c.value, 0) == 1 and not c.is_joker]
        if singles:
            return min(singles, key=lambda c: c.value)
        return min(cards, key=lambda c: c.value if not c.is_joker else 100)

    freq = Counter(c.value for c in cards if not c.is_joker)
    counts = sorted(freq.values(), reverse=True)

    if counts and ((counts[0] == 2 and counts.count(2) >= 2) or counts[0] in (3, 4)) and len([v for v in counts if v == 1]) >= 1:
        singles = [c for c in cards if freq.get(c.value, 0) == 1 and not c.is_joker]
        if singles:
            return min(singles, key=lambda c: c.value)
        return min(cards, key=lambda c: c.value if not c.is_joker else 100)

    singles = [c for c in cards if freq.get(c.value, 0) == 1 and not c.is_joker]
    if singles:
        return min(singles, key=lambda c: c.value)
    return min(cards, key=lambda c: c.value if not c.is_joker else 100)

# ------------------------- 游戏逻辑 -------------------------
class Wild_Five_Poker:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.player_hand = []
        self.dealer_hand = []
        self.public_cards = []          # 2张公共牌
        self.player_initial_hand = []
        self.ante = 0
        self.blind = 0
        self.original_five_bet = 0
        self.public_pair_bet = 0
        self.play_bet = 0
        self.stage = "pre_flop"
        self.folded = False
        self.player_discard = None
        self.dealer_discard = None

    def deal_initial(self):
        self.player_hand = self.deck.deal(5)
        self.dealer_hand = self.deck.deal(5)
        self.public_cards = self.deck.deal(2)      # 2张公共牌
        self.player_initial_hand = [card_copy(c) for c in self.player_hand]

# ------------------------- GUI -------------------------
class WildFivePokerGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("⺩牌五張撲克")
        self.geometry("1320x790+40+10")
        self.resizable(False, False)
        self.configure(bg='#35654d')

        self.username = username
        self.balance = initial_balance
        self.game = Wild_Five_Poker()

        self.card_images = {}
        self.original_images = {}
        self.selected_chip = None
        self.chip_buttons = []
        self.chip_texts = {}
        self.bet_widgets = {}
        self.active_card_labels = []
        self.auto_reset_timer = None
        self.restart_btn = None
        self._resetting = False
        self.animation_queue = []
        self.betting_enabled = True   
        self.animation_in_progress = False
        self.player_selected_label = None
        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------- 生命周期 -------------------------
    def cancel_auto_reset_timer(self):
        if self.auto_reset_timer:
            try:
                self.after_cancel(self.auto_reset_timer)
            except Exception:
                pass
            self.auto_reset_timer = None

    def on_close(self):
        self.cancel_auto_reset_timer()
        self.destroy()
        self.quit()

    # ------------------------- 资源 -------------------------
    def _load_assets(self):
        card_size = (100, 150)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        cls = type(self)
        next_folder = getattr(cls, "_next_poker_folder", "Poker1")
        self.current_poker_folder = next_folder
        cls._next_poker_folder = "Poker2" if next_folder == "Poker1" else "Poker1"

        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', self.current_poker_folder)
        suit_mapping = {'♠': 'Spade', '♥': 'Heart', '♦': 'Diamond', '♣': 'Club', 'JOKER': 'JOKER'}

        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_img_orig = Image.open(back_path)
            self.original_images["back"] = back_img_orig
            self.back_image = ImageTk.PhotoImage(back_img_orig.resize(card_size))
        except Exception:
            img_orig = Image.new('RGB', card_size, 'black')
            self.original_images["back"] = img_orig
            self.back_image = ImageTk.PhotoImage(img_orig)

        for suit in SUITS + ['JOKER']:
            for rank in RANKS:
                filename = "JOKER-A.png" if suit == 'JOKER' else f"{suit_mapping[suit]}{rank}.png"
                path = os.path.join(card_dir, filename)
                try:
                    if os.path.exists(path):
                        img = Image.open(path)
                        self.original_images[(suit, rank)] = img
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img.resize(card_size))
                    else:
                        img_orig = Image.new('RGB', card_size, 'blue')
                        draw = ImageDraw.Draw(img_orig)
                        text = "JOKER" if suit == 'JOKER' else f"{rank}{suit}"
                        try:
                            font = ImageFont.truetype("arial.ttf", 20)
                        except Exception:
                            font = ImageFont.load_default()
                        draw.text((10, 10), text, fill="white", font=font)
                        self.original_images[(suit, rank)] = img_orig
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
                except Exception:
                    pass

    def _card_image_for(self, card):
        return self.card_images.get((card.suit, card.rank), self.back_image)

    def _create_card_label(self, parent, card, face_up=False, y_offset=0, border=0):
        img = self._card_image_for(card) if face_up else self.back_image
        lbl = tk.Label(parent, image=img, bg='#2a4a3c', bd=border)
        lbl.image = img
        lbl.card = card
        lbl.is_face_up = face_up
        lbl.base_y = y_offset
        return lbl

    # ------------------------- UI -------------------------
    def _create_widgets(self):
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 庄家区
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=35, y=10, width=785, height=240)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18),
                                     bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)

        dealer_body = tk.Frame(dealer_frame, bg='#2a4a3c')
        dealer_body.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.dealer_body = dealer_body
        self.dealer_cards_area = tk.Frame(dealer_body, bg='#2a4a3c', width=560, height=190)
        self.dealer_cards_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        self.dealer_cards_area.pack_propagate(False)
        self.dealer_discard_area = tk.Frame(dealer_body, bg='#2a4a3c', width=150, height=190)
        self.dealer_discard_area.pack(side=tk.RIGHT, fill=tk.Y)
        self.dealer_discard_area.pack_propagate(False)
        tk.Label(self.dealer_discard_area, text="弃牌区", bg='#2a4a3c', fg='white',
                 font=('Arial', 18, 'bold')).pack(anchor='n')
        self.dealer_discard_slot = tk.Frame(self.dealer_discard_area, bg='#2a4a3c')
        self.dealer_discard_slot.pack(expand=True, fill=tk.X)

        # 公共牌区（2张牌）
        public_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        public_frame.place(x=35, y=265, width=300, height=220)
        public_frame.lift()
        tk.Label(public_frame, text="公共牌", font=('Arial', 18), bg='#2a4a3c', fg='white').pack(anchor='w', padx=10, pady=5)
        self.public_cards_area = tk.Frame(public_frame, bg='#2a4a3c', width=250, height=190)
        self.public_cards_area.pack(expand=True)
        self.public_cards_area.pack_propagate(False)
        self.public_card_labels = []

        self.ante_info_label0 = tk.Label(
            table_canvas, 
            text="鬼牌可以替代任意花色点数的牌\n\n要使用公共牌的前提是\n     您需要在加注前选择要弃的牌\n\n庄家必须有对子或更好才合格\n     不合格的 底注以平局结算", 
            font=('Arial', 22), 
            bg='#35654d', 
            fg='#FFD700',
            justify='left'   
        )

        # 更新以获取宽度
        self.ante_info_label0.update_idletasks()
        label_width = self.ante_info_label0.winfo_width()

        # 获取 canvas 宽度
        table_canvas.update_idletasks()
        canvas_width = table_canvas.winfo_width()

        center_x = (canvas_width - label_width) // 2
        self.ante_info_label0.place(x=center_x + 580, y=260, anchor='n')

        # 玩家区
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=35, y=500, width=785, height=240)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 18),
                                     bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)

        player_body = tk.Frame(player_frame, bg='#2a4a3c')
        player_body.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.player_body = player_body
        self.player_cards_area = tk.Frame(player_body, bg='#2a4a3c', width=560, height=190)
        self.player_cards_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        self.player_cards_area.pack_propagate(False)
        self.player_discard_area = tk.Frame(player_body, bg='#2a4a3c', width=150, height=190)
        self.player_discard_area.pack(side=tk.RIGHT, fill=tk.Y)
        self.player_discard_area.pack_propagate(False)
        tk.Label(self.player_discard_area, text="弃牌区", bg='#2a4a3c', fg='white',
                 font=('Arial', 18, 'bold')).pack(anchor='n')
        self.player_discard_slot = tk.Frame(self.player_discard_area, bg='#2a4a3c')
        self.player_discard_slot.pack(expand=True, fill=tk.X)

        # 控制区
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=310, padx=10, pady=5)
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

        limits_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        limits_frame.pack(fill=tk.X, pady=5)
        header_frame = tk.Frame(limits_frame, bg='#2a4a3c')
        header_frame.pack(fill=tk.X, padx=10, pady=(5, 0))
        for text in ("底注最低", "底注最高", "边注最高"):
            tk.Label(header_frame, text=text, font=('Arial', 12, 'bold'),
                     bg='#2a4a3c', fg='white', width=10).pack(side=tk.LEFT, expand=True)
        value_frame = tk.Frame(limits_frame, bg='#2a4a3c')
        value_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        for text in ("$10", "$10,000", "$2,500"):
            tk.Label(value_frame, text=text, font=('Arial', 12, 'bold'),
                     bg='#2a4a3c', fg='#FFD700', width=10).pack(side=tk.LEFT, expand=True)

        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=8)

        row1 = tk.Frame(bet_frame, bg='#2a4a3c')
        row1.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(row1, text="原始五:", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT)
        self.original_five_var = tk.StringVar(value="0")
        self.original_five_display = tk.Label(row1, textvariable=self.original_five_var, font=('Arial', 14),
                                              bg='white', width=7, relief=tk.SUNKEN)
        self.original_five_display.pack(side=tk.LEFT, padx=5)
        self.original_five_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("original_five"))
        self.bet_widgets["original_five"] = self.original_five_display

        tk.Label(row1, text="  ", bg='#2a4a3c').pack(side=tk.LEFT, padx=5)
        tk.Label(row1, text="公共对子:", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT)
        self.public_pair_var = tk.StringVar(value="0")
        self.public_pair_display = tk.Label(row1, textvariable=self.public_pair_var, font=('Arial', 14),
                                            bg='white', width=7, relief=tk.SUNKEN)
        self.public_pair_display.pack(side=tk.LEFT, padx=5)
        self.public_pair_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("public_pair"))
        self.bet_widgets["public_pair"] = self.public_pair_display

        row2 = tk.Frame(bet_frame, bg='#2a4a3c')
        row2.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(row2, text="底注:", font=('Arial', 14), bg='#2a4a3c', fg='white',padx=11).pack(side=tk.LEFT)
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
        tk.Label(row2, text=" :盲注", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT)
        self.bet_widgets["blind"] = self.blind_display

        row3 = tk.Frame(bet_frame, bg='#2a4a3c')
        row3.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(row3, text="加注:", font=('Arial', 14), bg='#2a4a3c', fg='white',padx=11).pack(side=tk.LEFT)
        self.play_var = tk.StringVar(value="0")
        self.play_display = tk.Label(row3, textvariable=self.play_var, font=('Arial', 14),
                                     bg='white', width=7, relief=tk.SUNKEN)
        self.play_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["play"] = self.play_display

        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        self.action_frame.pack(fill=tk.X)

        start_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_frame.pack(pady=5)
        self.reset_bets_button = tk.Button(start_frame, text="重置金额", command=self.reset_bets,
                                           font=('Arial', 14), bg='#F44336', fg='white', width=10)
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))
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

    def _rebuild_chips(self):
        for widget in self.chip_container.winfo_children():
            widget.destroy()
        self.chip_buttons = []
        self.selected_chip = None
        chip_configs = [
            ('$10', 'orange', 'black'),
            ('$25', '#00ff00', 'black'),
            ('$100', 'black', 'white'),
            ('$500', '#FF7DDA', 'black'),
            ('$1K', 'white', 'black'),
            ('$2.5K', 'red', 'white')
        ]
        default = "$10"
        for text, bg, fg in chip_configs:
            chip_canvas = tk.Canvas(self.chip_container, width=57, height=57, bg='#2a4a3c', highlightthickness=0)
            chip_canvas.create_oval(2, 2, 55, 55, fill=bg, outline='black')
            chip_canvas.create_text(27.5, 27.5, text=text, fill=fg, font=('Arial', 14, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text
        self.select_chip(default)

    def select_chip(self, chip_text):
        self.selected_chip = chip_text
        for chip in self.chip_buttons:
            chip.delete("highlight")
            for item in chip.find_all():
                if chip.type(item) == 'oval':
                    x1, y1, x2, y2 = chip.coords(item)
                    chip.create_oval(x1, y1, x2, y2, outline='black', width=2)
                    break
        for chip in self.chip_buttons:
            for item in chip.find_all():
                if chip.type(item) == 'text' and chip.itemcget(item, 'text') == chip_text:
                    oval = [i for i in chip.find_all() if chip.type(i) == 'oval'][0]
                    x1, y1, x2, y2 = chip.coords(oval)
                    chip.create_oval(x1, y1, x2, y2, outline='gold', width=3, tags="highlight")
                    break

    def add_chip_to_bet(self, bet_type):
        if not self.betting_enabled:
            return 
        if not self.selected_chip:
            return

        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K', '')) * 1000
        else:
            chip_value = float(chip_text)

        max_ante = 10000
        max_side = 2500

        if bet_type == "ante":
            current = float(self.ante_var.get())
            new_val = current + chip_value
            if new_val > max_ante:
                new_val = max_ante
                messagebox.showwarning("下注限制", f"底注上限为 {max_ante}")
            self.ante_var.set(str(int(new_val)))
            self.blind_var.set(str(int(new_val)))

        elif bet_type == "original_five":
            current = float(self.original_five_var.get())
            new_val = current + chip_value
            if new_val > max_side:
                new_val = max_side
                messagebox.showwarning("下注限制", f"原始五上限为 {max_side}")
            self.original_five_var.set(str(int(new_val)))

        elif bet_type == "public_pair":
            current = float(self.public_pair_var.get())
            new_val = current + chip_value
            if new_val > max_side:
                new_val = max_side
                messagebox.showwarning("下注限制", f"公共对子上限为 {max_side}")
            self.public_pair_var.set(str(int(new_val)))

    # ------------------------- 动画/显示 -------------------------
    def _clear_hand_areas(self):
        for w in self.player_cards_area.winfo_children():
            w.destroy()
        for w in self.dealer_cards_area.winfo_children():
            w.destroy()
        for w in self.player_discard_slot.winfo_children():
            w.destroy()
        for w in self.dealer_discard_slot.winfo_children():
            w.destroy()
        for w in self.public_cards_area.winfo_children():
            w.destroy()
        self.player_card_labels = []
        self.dealer_card_labels = []
        self.public_card_labels = []

    def animate_deal(self):
        self.animation_queue = []
        for i, card in enumerate(self.game.player_hand):
            self.animation_queue.append(("player", i, card))
        for i, card in enumerate(self.game.dealer_hand):
            self.animation_queue.append(("dealer", i, card))
        for i, card in enumerate(self.game.public_cards):
            self.animation_queue.append(("public", i, card))

        self.animation_in_progress = True
        self._process_animation_queue()

    def _process_animation_queue(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            self.after(500, self.reveal_player_cards)
            return

        who, idx, card = self.animation_queue.pop(0)

        if who == "player":
            parent = self.player_cards_area
            labels = self.player_card_labels
        elif who == "dealer":
            parent = self.dealer_cards_area
            labels = self.dealer_card_labels
        else:  # public
            parent = self.public_cards_area
            labels = self.public_card_labels

        lbl = self._create_card_label(parent, card, face_up=False)
        lbl.place(x=0, y=0, width=120, height=180)
        labels.append(lbl)

        target_x = idx * 110
        target_y = 0
        self._animate_move(lbl, target_x, target_y)

    def _animate_move(self, label, target_x, target_y, step=0, steps=20, start_x=0, start_y=0):
        if step > steps:
            label.place(x=target_x, y=target_y, width=120, height=180)
            self._process_animation_queue()
            return
        cur_x = start_x + (target_x - start_x) * step / steps
        cur_y = start_y + (target_y - start_y) * step / steps
        label.place(x=cur_x, y=cur_y, width=120, height=180)
        self.after(20, lambda: self._animate_move(label, target_x, target_y, step + 1, steps, start_x, start_y))

    def flip_card_animation(self, label):
        if label is None or not label.winfo_exists():
            return

        card = label.card
        front_img = self._card_image_for(card)

        def animate(step=0):
            if self._resetting or not label.winfo_exists():
                return
            try:
                if step > 10:
                    if label.winfo_exists():
                        label.config(image=front_img)
                        label.image = front_img
                        label.is_face_up = True
                        label.place(width=120, height=180)
                    return

                if step <= 5:
                    width = 120 - step * 12
                    if width < 1:
                        width = 1
                    if label.winfo_exists():
                        label.config(image=self.back_image)
                        label.image = self.back_image
                else:
                    width = (step - 5) * 12
                    if width < 1:
                        width = 1
                    if label.winfo_exists():
                        label.config(image=front_img)
                        label.image = front_img

                if label.winfo_exists():
                    label.place(width=width, height=180)

                self.after(50, lambda: animate(step + 1))
            except tk.TclError:
                return

        animate(0)

    def reveal_player_cards(self):
        for label in self.player_card_labels:
            if label.winfo_exists() and not label.is_face_up:
                self.flip_card_animation(label)
        self.after(1000, self.start_player_sort_animation)

    def reveal_dealer_cards(self, after_flip=None):
        to_flip = [lbl for lbl in self.dealer_card_labels if lbl.winfo_exists() and not lbl.is_face_up]
        if not to_flip:
            if after_flip:
                after_flip()
            return

        for lbl in to_flip:
            self.flip_card_animation(lbl)

        self.after(1000, after_flip if after_flip else lambda: None)

    def reveal_public_cards(self):
        for lbl in self.public_card_labels:
            if lbl.winfo_exists() and not lbl.is_face_up:
                self.flip_card_animation(lbl)

    def start_player_sort_animation(self):
        player_eval = best_hand_with_joker(self.game.player_hand)
        sorted_player = sort_hand_for_display(self.game.player_hand)

        labels = list(self.player_card_labels)
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
                        label.place(x=target_positions[label], y=0, width=120, height=180)
                self.game.player_hand = sorted_player
                self.player_label.config(text=f"玩家 - {player_eval[0]}")
                self.enable_player_actions()
                return

            for label, start_x, dx in anim_data:
                if label.winfo_exists():
                    label.place(x=start_x + dx * step, y=0, width=120, height=180)

            self.after(interval, lambda: animate_step(step + 1))

        animate_step(1)

    def enable_player_actions(self, preserve_selection=False):
        for w in self.action_frame.winfo_children():
            w.destroy()

        self.game.stage = "decision"

        if not preserve_selection:
            self.player_selected_label = None
            self.game.player_discard = None
        else:
            if self.player_selected_label is not None and self.player_selected_label.winfo_exists():
                self.game.player_discard = self.player_selected_label.card
            else:
                self.player_selected_label = None
                self.game.player_discard = None

        action_bar = tk.Frame(self.action_frame, bg='#2a4a3c')
        action_bar.pack(pady=5)

        self.fold_button = tk.Button(
            action_bar, text="弃牌", command=self.fold_action,
            font=('Arial', 14), bg='#F44336', fg='white', width=8
        )
        self.fold_button.pack(side=tk.LEFT, padx=(0, 8))

        self.raise1_button = tk.Button(
            action_bar, text="1X底注", command=lambda: self.raise_action(1),
            font=('Arial', 14), bg='#4CAF50', fg='white', width=8
        )
        self.raise1_button.pack(side=tk.LEFT, padx=4)

        self.raise3_button = tk.Button(
            action_bar, text="3X底注", command=lambda: self.raise_action(3),
            font=('Arial', 14), bg='#2E7D32', fg='white', width=8
        )
        self.raise3_button.pack(side=tk.LEFT, padx=4)

        for label in getattr(self, "player_card_labels", []):
            if not label.winfo_exists():
                continue
            try:
                label.unbind("<Button-1>")
            except Exception:
                pass
            label.bind("<Button-1>", lambda e, l=label: self.toggle_player_discard(l))

            try:
                base_y = int(getattr(label, "base_y", 0))
                if preserve_selection and label is self.player_selected_label:
                    label.place_configure(y=base_y + 10)
                    label.lift()
                else:
                    label.place_configure(y=base_y)
            except tk.TclError:
                pass

        self.status_label.config(text="请做出你的选择")
        self.stage_label.config(text="决策")

    def move_selected_card_to_discard(self, after_done=None):
        label = self.player_selected_label
        if label is None or not label.winfo_exists():
            if after_done:
                after_done()
            return

        card = getattr(label, "card", None)
        if card is None:
            if after_done:
                after_done()
            return

        self.game.player_discard = card
        self.player_selected_label = None

        try:
            start_x = label.winfo_rootx() - self.winfo_rootx()
            start_y = label.winfo_rooty() - self.winfo_rooty()
        except tk.TclError:
            if after_done:
                after_done()
            return

        target_x = 680
        target_y = 560

        ghost = tk.Label(self, image=label.image, bg='#2a4a3c', bd=0)
        ghost.image = label.image
        ghost.place(x=start_x, y=start_y, width=120, height=180)

        try:
            label.unbind("<Button-1>")
        except Exception:
            pass
        try:
            if label in self.player_card_labels:
                self.player_card_labels.remove(label)
        except Exception:
            pass
        try:
            label.destroy()
        except tk.TclError:
            pass

        steps = 18
        dx = (target_x - start_x) / steps
        dy = (target_y - start_y) / steps

        def animate(step=0):
            if not ghost.winfo_exists():
                if after_done:
                    after_done()
                return

            if step >= steps:
                try:
                    ghost.destroy()
                except tk.TclError:
                    pass

                final_lbl = self._create_card_label(self, card, face_up=True)
                final_lbl.place(x=target_x, y=target_y, width=120, height=180)
                final_lbl.lift()

                if after_done:
                    after_done()
                return

            try:
                ghost.place(
                    x=start_x + dx * step,
                    y=start_y + dy * step,
                    width=120,
                    height=180
                )
            except tk.TclError:
                if after_done:
                    after_done()
                return

            self.after(15, lambda: animate(step + 1))

        animate(0)

    def move_dealer_card_to_discard(self, after_done=None):
        discard_card = self.game.dealer_discard
        if discard_card is None:
            if after_done:
                after_done()
            return

        target_label = None
        for lbl in self.dealer_card_labels:
            if hasattr(lbl, 'card') and lbl.card == discard_card:
                target_label = lbl
                break

        if target_label is None or not target_label.winfo_exists():
            if after_done:
                after_done()
            return

        try:
            start_x = target_label.winfo_rootx() - self.winfo_rootx()
            start_y = target_label.winfo_rooty() - self.winfo_rooty()
        except tk.TclError:
            if after_done:
                after_done()
            return

        target_x = 680
        target_y = 70

        ghost = tk.Label(self, image=target_label.image, bg='#2a4a3c', bd=0)
        ghost.image = target_label.image
        ghost.place(x=start_x, y=start_y, width=120, height=180)

        try:
            target_label.destroy()
        except tk.TclError:
            pass

        if target_label in self.dealer_card_labels:
            self.dealer_card_labels.remove(target_label)

        steps = 18
        dx = (target_x - start_x) / steps
        dy = (target_y - start_y) / steps

        def animate(step=0):
            if not ghost.winfo_exists():
                if after_done:
                    after_done()
                return

            if step >= steps:
                try:
                    ghost.destroy()
                except tk.TclError:
                    pass

                final_lbl = self._create_card_label(self, discard_card, face_up=True)
                final_lbl.place(x=target_x, y=target_y, width=120, height=180)
                final_lbl.lift()

                if after_done:
                    after_done()
                return

            try:
                ghost.place(
                    x=start_x + dx * step,
                    y=start_y + dy * step,
                    width=120,
                    height=180
                )
            except tk.TclError:
                if after_done:
                    after_done()
                return

            self.after(15, lambda: animate(step + 1))

        animate(0)

    def _get_discard_position(self, slot_frame):
        children = slot_frame.winfo_children()
        num_discards = len(children)
        card_width = 120
        spacing = 10
        slot_frame.update_idletasks()
        slot_width = slot_frame.winfo_width()
        if slot_width <= 0:
            slot_width = 250
        x = slot_width - card_width - (num_discards * (card_width + spacing))
        if x < 0:
            x = 0
        y = 0
        return x, y

    def _add_discard_card(self, slot_frame, card):
        children = slot_frame.winfo_children()
        num_discards = len(children)
        card_width = 120
        spacing = 10
        slot_frame.update_idletasks()
        slot_width = slot_frame.winfo_width()
        if slot_width <= 0:
            slot_width = 250
        x = slot_width - card_width - (num_discards * (card_width + spacing))
        if x < 0:
            x = 0
        lbl = self._create_card_label(slot_frame, card, face_up=True)
        lbl.place(x=x, y=0, width=120, height=180)

    def toggle_player_discard(self, label):
        if self.game.folded or self.game.stage != "decision":
            return
        if label is None or not label.winfo_exists():
            return

        base_y = int(getattr(label, "base_y", 0))

        if self.player_selected_label is label:
            try:
                label.place_configure(y=base_y)
            except tk.TclError:
                pass
            self.player_selected_label = None
            self.game.player_discard = None
            return

        if self.player_selected_label is not None and self.player_selected_label.winfo_exists():
            try:
                old_base_y = int(getattr(self.player_selected_label, "base_y", 0))
                self.player_selected_label.place_configure(y=old_base_y)
            except tk.TclError:
                pass

        self.player_selected_label = label
        self.game.player_discard = label.card
        try:
            label.place_configure(y=base_y + 10)
            label.lift()
        except tk.TclError:
            pass

    def _disable_action_buttons(self):
        for w in self.action_frame.winfo_children():
            for btn in w.winfo_children():
                if isinstance(btn, tk.Button):
                    btn.config(state=tk.DISABLED)

    def fold_action(self):
        self._disable_action_buttons()
        self.game.folded = True
        self.game.stage = "showdown"
        self.status_label.config(text="您已弃牌，庄家继续开牌...")
        self.after(200, self.showdown_sequence)

    def raise_action(self, multiplier):
        self._disable_action_buttons()

        play_bet = self.game.ante * multiplier
        if play_bet > self.balance:
            messagebox.showerror("错误", "余额不足")
            self.enable_player_actions(preserve_selection=True)
            return

        self.balance -= play_bet
        self.update_balance()
        self.game.play_bet = play_bet
        self.play_var.set(str(int(play_bet)))

        total = self.game.ante + self.game.blind + self.game.original_five_bet + self.game.public_pair_bet + play_bet
        self.current_bet_label.config(text=f"本局下注: ${total:.2f}")

        def continue_to_showdown():
            self.game.stage = "showdown"
            self.status_label.config(text="摊牌中...")
            self.after(200, self.showdown_sequence)

        if self.player_selected_label is not None or self.game.player_discard is not None:
            self.move_selected_card_to_discard(after_done=continue_to_showdown)
        else:
            continue_to_showdown()

    def showdown_sequence(self):
        self.stage_label.config(text="摊牌")
        self.status_label.config(text="庄家开牌中...")
        self.reveal_dealer_cards(after_flip=self.start_dealer_sort_animation)

    def start_dealer_sort_animation(self):
        dealer_sorted = sort_hand_for_display(self.game.dealer_hand)

        labels = list(self.dealer_card_labels)
        start_positions = {}
        for label in labels:
            if label.winfo_exists():
                info = label.place_info()
                start_positions[label] = float(info.get('x', 0))

        target_positions = {}
        for idx, card in enumerate(dealer_sorted):
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
                        label.place(x=target_positions[label], y=0, width=120, height=180)
                self.game.dealer_hand = dealer_sorted
                self.game.dealer_discard = dealer_discard_card(self.game.dealer_hand)
                self.after_dealer_sort()
                return

            for label, start_x, dx in anim_data:
                if label.winfo_exists():
                    label.place(x=start_x + dx * step, y=0, width=120, height=180)

            self.after(interval, lambda: animate_step(step + 1))

        animate_step(1)

    def after_dealer_sort(self):
        if self.game.dealer_discard is not None:
            self.move_dealer_card_to_discard(after_done=self._after_dealer_discard_animation)
        else:
            self._after_dealer_discard_animation()

    def _after_dealer_discard_animation(self):
        public_open = (
            self.game.player_discard is not None
            or self.game.dealer_discard is not None
            or self.game.folded
        )

        if public_open:
            self.reveal_public_cards()
            self.status_label.config(text="公共牌已翻开")
        else:
            self.status_label.config(text="双方保留五张牌")

        self.after(1100, lambda: self._finish_showdown(public_open))

    def _finish_showdown(self, public_open):
        if self._resetting:
            return
        self.render_final_cards(public_open)
        self.settle_game(public_open)

    def _clear_final_card_views(self):
        for w in self.player_cards_area.winfo_children():
            w.destroy()
        for w in self.dealer_cards_area.winfo_children():
            w.destroy()

    def render_final_cards(self, public_open):
        self._clear_final_card_views()

        player_pool = [card_copy(c) for c in self.game.player_hand if c != self.game.player_discard]
        dealer_pool = [card_copy(c) for c in self.game.dealer_hand if c != self.game.dealer_discard]

        if self.game.player_discard is not None:
            for c in self.game.public_cards:
                c2 = card_copy(c)
                c2.source = 'public'
                player_pool.append(c2)
        if self.game.dealer_discard is not None:
            for c in self.game.public_cards:
                c3 = card_copy(c)
                c3.source = 'public'
                dealer_pool.append(c3)

        if len(player_pool) >= 5:
            p_best = best_hand_from_cards(player_pool)
            p_rank_name, p_cards_unsorted = p_best[0], p_best[3]
        else:
            p_rank_name = classify_hand_for_display(self.game.player_hand)
            p_cards_unsorted = [card_copy(c) for c in self.game.player_hand]

        if len(dealer_pool) >= 5:
            d_best = best_hand_from_cards(dealer_pool)
            d_rank_name, d_cards_unsorted = d_best[0], d_best[3]
        else:
            d_rank_name = classify_hand_for_display(self.game.dealer_hand)
            d_cards_unsorted = [card_copy(c) for c in self.game.dealer_hand]

        p_cards = sort_hand_for_display(p_cards_unsorted)
        d_cards = sort_hand_for_display(d_cards_unsorted)

        self.player_label.config(text=f"玩家 - {p_rank_name}")
        self.dealer_label.config(text=f"庄家 - {d_rank_name}")

        if public_open:
            for i, card in enumerate(self.game.public_cards):
                lbl = self._create_card_label(self.public_cards_area, card, face_up=True)
                lbl.place(x=i * 110, y=0, width=120, height=180)

        for i, card in enumerate(p_cards):
            lbl = self._create_card_label(self.player_cards_area, card, face_up=True)
            y_offset = 10 if getattr(card, 'source', '') == 'public' else 0
            lbl.place(x=i * 110, y=y_offset, width=120, height=180)

        for i, card in enumerate(d_cards):
            lbl = self._create_card_label(self.dealer_cards_area, card, face_up=True)
            y_offset = 10 if getattr(card, 'source', '') == 'public' else 0
            lbl.place(x=i * 110, y=y_offset, width=120, height=180)

        if self.game.player_discard is not None:
            self._add_discard_card(self.player_discard_slot, self.game.player_discard)
        if self.game.dealer_discard is not None:
            self._add_discard_card(self.dealer_discard_slot, self.game.dealer_discard)

        if self.game.player_discard is not None:
            public_count = sum(1 for c in p_cards if getattr(c, 'source', '') == 'public')
            if public_count == 2:
                player_hand_cards = self.game.player_hand
                final_non_public = [c for c in p_cards if getattr(c, 'source', '') != 'public']
                replaced_card = None
                for c in player_hand_cards:
                    if c is self.game.player_discard:
                        continue
                    if not any(c == fc for fc in final_non_public):
                        replaced_card = c
                        break
                if replaced_card is not None:
                    lbl = self._create_card_label(self, replaced_card, face_up=True, border=0)
                    lbl.config(bd=0, relief=tk.FLAT, highlightthickness=0, padx=0, pady=0)
                    lbl.place(x=715, y=575, width=100, height=150)
                    lbl.lift()

        if self.game.dealer_discard is not None:
            public_count = sum(1 for c in d_cards if getattr(c, 'source', '') == 'public')
            if public_count == 2:
                dealer_hand_cards = self.game.dealer_hand
                final_non_public = [c for c in d_cards if getattr(c, 'source', '') != 'public']
                replaced_card = None
                for c in dealer_hand_cards:
                    if c is self.game.dealer_discard:
                        continue
                    if not any(c == fc for fc in final_non_public):
                        replaced_card = c
                        break
                if replaced_card is not None:
                    lbl = self._create_card_label(self, replaced_card, face_up=True, border=0)
                    lbl.config(bd=0, relief=tk.FLAT, highlightthickness=0, padx=0, pady=0)
                    lbl.place(x=715, y=85, width=100, height=150)
                    lbl.lift()

    # ------------------------- 结算（修改重点） -------------------------
    def settle_game(self, public_open):
        # 构建玩家和庄家的最终牌池（原代码保持不变）
        player_pool = [card_copy(c) for c in self.game.player_hand if c != self.game.player_discard]
        dealer_pool = [card_copy(c) for c in self.game.dealer_hand if c != self.game.dealer_discard]

        if self.game.player_discard is not None:
            for c in self.game.public_cards:
                c2 = card_copy(c)
                c2.source = 'public'
                player_pool.append(c2)
        if self.game.dealer_discard is not None:
            for c in self.game.public_cards:
                c3 = card_copy(c)
                c3.source = 'public'
                dealer_pool.append(c3)

        # 获取庄家最终手牌的牌型等级
        dealer_best = best_hand_from_cards(dealer_pool)
        dealer_rank_val = dealer_best[1]
        is_dealer_high = (dealer_rank_val == HAND_RANK["高牌"])   # HAND_RANK["高牌"] = 0

        details = {
            "ante": 0,
            "blind": 0,
            "play": 0,
            "original_five": 0,
            "public_pair": 0
        }

        # 原始五边注（基于初始手牌）
        details["original_five"] = self.calculate_original_five(self.game.player_initial_hand)
        # 公共对子边注
        details["public_pair"] = self.calculate_public_pair(self.game.public_cards)

        # 比牌逻辑（底注、盲注、加注）
        if not self.game.folded:
            comp = compare_hands_best(player_pool, dealer_pool)
            if comp == 1:      # 玩家赢
                details["ante"] = self.game.ante * 2
                details["play"] = self.game.play_bet * 2
                # 盲注赔付（按玩家牌型）
                if len(player_pool) >= 5:
                    player_best = best_hand_from_cards(player_pool)
                    player_rank_val = player_best[1]
                else:
                    player_best = best_hand_with_joker(self.game.player_hand)
                    player_rank_val = player_best[1]
                payout_mult = BLIND_PAYOUT.get(player_rank_val, 0)
                details["blind"] = self.game.blind * (payout_mult + 1)
            elif comp == 0:    # 平局
                details["ante"] = self.game.ante
                details["blind"] = self.game.blind
                details["play"] = self.game.play_bet
            # comp == -1 玩家输：各项保持0，无需额外赋值
        else:
            # 玩家弃牌：底注、盲注、加注全部输掉（初始为0）
            pass

        # ========== 新增：庄家最终手牌为高牌时，底注强制按平局处理 ==========
        if is_dealer_high:
            details["ante"] = self.game.ante   # 只返还底注本金，不加倍
            self.status_label.config(text="庄家牌型是高牌，底注平局")
        else:
            self.status_label.config(text="游戏结束")

        # 计算总赢取金额并更新余额（后续代码保持不变）
        winnings = sum(details.values())
        self.balance += winnings
        self.update_balance()

        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")
        self._update_bet_display(details)
        self.show_restart_button()

    def calculate_original_five(self, hand):
        """原始五边注：基于初始手牌，根据牌型获得赔率（不返还本金，输则0）"""
        if self.game.original_five_bet == 0:
            return 0
        # 获取手牌最佳牌型（不含公共牌）
        rank_name, rank_val, _, _, _ = best_hand_with_joker(hand)
        payout_mult = ORIGINAL_FIVE_PAYOUT.get(rank_val, 0)
        if payout_mult > 0:
            # 注意：原始五是纯奖励，不返还本金，例如下注1，赢100，共拿回101？根据需求：“以上都是{}:1，例如五条，1000:1=下注1，获胜1000，共返还1001。”
            # 实际上“获胜1000”是指净赢1000，加上本金共1001。因此返回 下注 * (赔率+1)
            return self.game.original_five_bet * (payout_mult + 1)
        else:
            return 0

    def calculate_public_pair(self, public_cards):
        if self.game.public_pair_bet == 0:
            return 0
        mult = get_public_pair_payout(public_cards)
        if mult:
            return self.game.public_pair_bet * (mult + 1)
        else:
            return 0

    def _update_bet_display(self, details):
        if details["original_five"] > 0:
            self.original_five_display.config(bg='gold')
            self.original_five_var.set(str(int(details["original_five"])))
        else:
            self.original_five_display.config(bg='white')
            self.original_five_var.set("0")

        if details["public_pair"] > 0:
            self.public_pair_display.config(bg='gold')
            self.public_pair_var.set(str(int(details["public_pair"])))
        else:
            self.public_pair_display.config(bg='white')
            self.public_pair_var.set("0")

        if details["ante"] > 0:
            self.ante_display.config(bg='gold' if details["ante"] > self.game.ante else 'light blue')
            self.ante_var.set(str(int(details["ante"])))
        else:
            self.ante_display.config(bg='white')
            self.ante_var.set("0")

        if details["blind"] > 0:
            self.blind_display.config(bg='gold' if details["blind"] > self.game.blind else 'light blue')
            self.blind_var.set(str(int(details["blind"])))
        else:
            self.blind_display.config(bg='white')
            self.blind_var.set("0")

        if details["play"] > 0:
            self.play_display.config(bg='gold' if details["play"] > self.game.play_bet else 'light blue')
            self.play_var.set(str(int(details["play"])))
        else:
            self.play_display.config(bg='white')
            self.play_var.set("0")

    # ------------------------- 按钮/重置 -------------------------
    def show_restart_button(self):
        for w in self.action_frame.winfo_children():
            w.destroy()
        self.stage_label.config(text="结算")
        self.restart_btn = tk.Button(self.action_frame, text="再来一局", command=self.reset_game,
                                     font=('Arial', 14), bg='#2196F3', fg='white', width=15)
        self.restart_btn.pack(pady=5)
        self.restart_btn.bind("<Button-3>", self.show_card_sequence)
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def _animate_reset_collect_cards(self, callback=None):
        moving_cards = []
        for area in (
            self.player_cards_area,
            self.dealer_cards_area,
            self.public_cards_area,
            self.player_discard_slot,
            self.dealer_discard_slot
        ):
            for w in area.winfo_children():
                if isinstance(w, tk.Label) and w.winfo_exists():
                    moving_cards.append(w)

        if not moving_cards:
            if callback:
                callback()
            return

        self.update_idletasks()
        target_x = self.winfo_width() + 200

        for card in moving_cards:
            card.target_pos = (target_x, card.winfo_y())

        self._animate_card_out_step(moving_cards, callback)

    def _animate_card_out_step(self, moving_cards, callback):
        all_done = True
        for card in moving_cards[:]:
            if not card.winfo_exists():
                moving_cards.remove(card)
                continue

            current_x = card.winfo_x()
            target_x, target_y = card.target_pos
            dx = target_x - current_x

            if abs(dx) < 5:
                card.destroy()
                moving_cards.remove(card)
                continue

            new_x = current_x + dx * 0.2
            card.place(x=new_x, y=target_y)
            all_done = False

        if not all_done:
            self.after(20, lambda: self._animate_card_out_step(moving_cards, callback))
        else:
            if callback:
                callback()

    def reset_game(self, auto_reset=False):
        self.cancel_auto_reset_timer()
        if self.restart_btn and self.restart_btn.winfo_exists():
            self.restart_btn.config(state=tk.DISABLED)

        self._resetting = True

        for after_id in self.tk.eval('after info').split():
            try:
                self.after_cancel(after_id)
            except Exception:
                pass

        self._animate_reset_collect_cards(callback=lambda: self._do_reset(auto_reset))

    def _do_reset(self, auto_reset=False):
        fixed_discard_positions = [(680, 70), (680, 560), (715, 85), (715, 575)]
        for child in self.winfo_children():
            if isinstance(child, tk.Label):
                try:
                    x = child.winfo_x()
                    y = child.winfo_y()
                    if (x, y) in fixed_discard_positions:
                        child.destroy()
                except tk.TclError:
                    pass

        self._clear_hand_areas()
        self.game.reset_game()

        self.stage_label.config(text="翻牌前")
        self.status_label.config(text="设置下注金额并开始游戏")
        self.player_label.config(text="玩家")
        self.dealer_label.config(text="庄家")

        self.ante_var.set("0")
        self.blind_var.set("0")
        self.original_five_var.set("0")
        self.public_pair_var.set("0")
        self.play_var.set("0")
        self.current_bet_label.config(text="本局下注: $0.00")

        self._resetting = False
        self.player_selected_label = None

        for widget in self.bet_widgets.values():
            widget.config(bg='white')

        for w in self.action_frame.winfo_children():
            w.destroy()

        start_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_frame.pack(pady=5)

        self.reset_bets_button = tk.Button(start_frame, text="重置金额", command=self.reset_bets,
                                        font=('Arial', 14), bg='#F44336', fg='white', width=10)
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))

        self.start_button = tk.Button(start_frame, text="开始游戏", command=self.start_game,
                                    font=('Arial', 14), bg='#4CAF50', fg='white', width=10)
        self.start_button.pack(side=tk.LEFT)

        self.betting_enabled = True

        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))

    def reset_bets(self):
        self.ante_var.set("0")
        self.original_five_var.set("0")
        self.public_pair_var.set("0")
        self.play_var.set("0")
        self.status_label.config(text="已重置所有下注金额")
        for w in self.bet_widgets.values():
            w.config(bg='white')

    def show_card_sequence(self, event):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None

        win = tk.Toplevel(self)
        win.title("本局牌序")
        win.geometry("650x600")
        win.resizable(0, 0)
        win.configure(bg='#f0f0f0')

        deck = self.game.deck
        cut_pos = deck.cut_position
        card_sequence = deck.full_deck

        tk.Label(win, text=f"本局切牌位置: {cut_pos + 1}", font=('Arial', 14, 'bold'),
                 bg='#f0f0f0').pack(pady=(10, 5))

        main_frame = tk.Frame(win, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        canvas = tk.Canvas(main_frame, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)

        content_frame = tk.Frame(canvas, bg='#f0f0f0')
        canvas.create_window((0, 0), window=content_frame, anchor='nw')

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
                back_img = self.original_images.get("back")
                if back_img is not None:
                    small_img = back_img.resize(small_size, Image.LANCZOS)
                    small_images[i] = ImageTk.PhotoImage(small_img)

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
                    card_label = tk.Label(card_container, image=small_images[card_index], bg=bg_color,
                                          borderwidth=1, relief="solid")
                    card_label.image = small_images[card_index]
                    card_label.pack()
                else:
                    card = card_sequence[card_index]
                    tk.Label(card_container, text=f"{card.rank}{card.suit}", bg=bg_color,
                             width=6, height=3, borderwidth=1, relief="solid").pack()

                tk.Label(card_container, text=str(card_index + 1), bg=bg_color,
                         font=('Arial', 9)).pack()

        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)

    def start_game(self):
        try:
            ante = int(float(self.ante_var.get()))
            original_five = int(float(self.original_five_var.get()))
            public_pair = int(float(self.public_pair_var.get()))
        except Exception:
            messagebox.showerror("错误", "请输入有效的下注金额")
            return

        min_ante, max_ante, max_side = 10, 10000, 2500
        if ante < min_ante:
            messagebox.showerror("错误", f"底注至少需要{min_ante}")
            return
        if ante > max_ante:
            ante = max_ante
            self.ante_var.set(str(max_ante))
            messagebox.showwarning("下注限制", f"底注上限为{max_ante}，已自动调整")
        if original_five > max_side:
            original_five = max_side
            self.original_five_var.set(str(max_side))
            messagebox.showwarning("下注限制", f"原始五上限为{max_side}，已自动调整")
        if public_pair > max_side:
            public_pair = max_side
            self.public_pair_var.set(str(max_side))
            messagebox.showwarning("下注限制", f"公共对子上限为{max_side}，已自动调整")

        blind = ante
        total_bet = ante + blind + original_five + public_pair
        if total_bet > self.balance:
            messagebox.showerror("错误", "余额不足")
            return

        self.balance -= total_bet
        self.update_balance()
        self.betting_enabled = False
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        self.last_win_label.config(text="上局获胜: $0.00")

        self._load_assets()
        self.game.reset_game()
        self.game.deal_initial()
        self.game.stage = "dealing"
        self.game.ante = ante
        self.game.blind = blind
        self.game.original_five_bet = original_five
        self.game.public_pair_bet = public_pair
        self.game.play_bet = 0

        self._clear_hand_areas()
        for w in self.action_frame.winfo_children():
            w.destroy()

        self.stage_label.config(text="发牌中")
        self.status_label.config(text="正在发牌...")
        self.animate_deal()

        self.ante_display.config(bg='white')
        self.blind_display.config(bg='white')
        self.original_five_display.config(bg='white')
        self.public_pair_display.config(bg='white')
        self.play_display.config(bg='white')

    # ------------------------- 游戏规则说明 -------------------------
    def show_game_instructions(self):
        """显示游戏规则说明"""
        win = tk.Toplevel(self)
        win.title("⺩牌五張撲克 游戏规则")
        win.geometry("750x700")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')

        # 主框架及滚动条
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        canvas = tk.Canvas(main_frame, bg='#F0F0F0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)

        content_frame = tk.Frame(canvas, bg='#F0F0F0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')

        # ================== 游戏规则文本 ==================
        rules_text = """
    ⺩牌五張撲克游戏规则

    1. 下注阶段（开始前）：
    - 底注（Ante）：每局必须下注（$10 ~ $10,000）
    - 盲注（Blind）：自动等于底注金额
    - 原始五（Original Five）：可选边注，基于玩家初始5张手牌（$0 ~ $2,500）
    - 公共对子（Public Pair）：可选边注，基于2张公共牌（$0 ~ $2,500）

    2. 发牌与弃牌：
    - 玩家和庄家各发5张手牌，另发2张公共牌（牌面朝下）
    - 玩家先亮出自己的5张手牌，然后可以选择弃掉1张手牌（点击牌选中，再次点击取消）
    - 选定弃牌（或不弃）后，玩家必须选择加注倍数：
            * 1X底注：加注金额 = 底注 × 1
            * 3X底注：加注金额 = 底注 × 3

    3. 庄家行动：
    - 庄家根据其手牌策略，可能也会弃掉1张手牌（不需要玩家操作）

    4. 摊牌与比牌：
    - 如果玩家弃牌，则直接结算边注，底注/盲注/加注全部输掉
    - 否则双方翻开手牌和公共牌，各自从“手牌+公共牌”中选出最佳5张组合：
            * 若玩家/庄家弃了1张手牌，则公共牌可加入该方牌池
            * 若未弃牌，则只能使用自己的5张手牌
    - 比较双方最佳牌型（含Joker万能牌），牌型相同则比较牌点

    5. 赔付规则：
    - 加注：玩家赢 → 各赢1倍（返还2倍下注额）；平局 → 返还本金；输 → 输掉
    - 底注：玩家赢(庄家对子或以上牌型) → 各赢1倍（返还2倍下注额）；平局或庄家高牌 → 返还本金；输 → 输掉
    - 盲注（玩家赢时）：
        按玩家最终手牌牌型赔付（赔率:1，含本金），详见下方【盲注赔率表】
    - 原始五（边注）：
        基于玩家初始5张手牌（不组合公共牌），达成牌型即奖励，详见【原始五赔率表】
    - 公共对子（边注）：
        基于2张公共牌，达成对子或特殊组合即奖励，详见【公共对子赔率表】

    6. 其他说明：
    - Joker 为万能牌，可替代任何点数/花色
    - 牌型等级：五条 > 同花大顺 > 同花顺 > 四条 > 葫芦 > 同花 > 顺子 > 三条 > 两对 > 对子 > 高牌
    - 右键点击“再来一局”按钮可查看本局牌序
    - 30秒无操作自动开始新游戏
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

        # ================== 盲注赔率表 ==================
        tk.Label(
            content_frame,
            text="赔率表",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')

        blind_frame = tk.Frame(content_frame, bg='#F0F0F0')
        blind_frame.pack(fill=tk.X, padx=20, pady=5)

        blind_headers = ["牌型", "盲注赔率", "原始五赔率"]
        blind_data = [
            ("五条", "100:1", "1000:1"),
            ("同花大顺", "50:1", "500:1"),
            ("同花顺", "10:1", "250:1"),
            ("四条", "5:1", "100:1"),
            ("葫芦", "3:1", "50:1"),
            ("同花", "2:1", "25:1"),
            ("顺子", "1:1", "10:1"),
            ("三条", "平局", "5:1"),
            ("两对", "平局", "5:1"),
            ("其他牌型", "平局", "输")
        ]
        for col, h in enumerate(blind_headers):
            tk.Label(
                blind_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        for r, row_data in enumerate(blind_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    blind_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        for c in range(len(blind_headers)):
            blind_frame.columnconfigure(c, weight=1)

        # ================== 公共对子赔率表 ==================
        tk.Label(
            content_frame,
            text="公共对子赔率表",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')

        pair_frame = tk.Frame(content_frame, bg='#F0F0F0')
        pair_frame.pack(fill=tk.X, padx=20, pady=5)

        pair_headers = ["组合", "赔率"]
        pair_data = [
            ("A-A", "23:1"),
            ("A-K（同花）", "19:1"),
            ("A-Q 或 A-J（同花）", "16:1"),
            ("A-K（非同花）", "11:1"),
            ("K-K, Q-Q, J-J", "8:1"),
            ("含 Joker", "6:1"),
            ("A-Q 或 A-J（非同花）", "4:1"),
            ("其他对子（10-10 到 2-2）", "2:1")
        ]

        for col, h in enumerate(pair_headers):
            tk.Label(
                pair_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#2E8B57',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        for r, row_data in enumerate(pair_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    pair_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        for c in range(len(pair_headers)):
            pair_frame.columnconfigure(c, weight=1)

        # ================== 注释 ==================
        notes = """
    【注】
    • 所有赔率格式均为“赔率:1”，例如下注$1赢得$100，共返还$101（本金+奖金）。
    • 原始五边注使用玩家初始5张手牌（不加入公共牌），即使最终手牌发生变化也以初始手牌为准。
    • 盲注的赔付仅当玩家最终手牌（含公共牌）达到对应牌型时才支付额外奖金，与比牌输赢无关（但前提是玩家赢）。
    • Joker 为万能牌，可提升所有牌型（五条、顺子、同花等）。
    • 公共对子赔率中的“含Joker”指至少有一张公共牌是Joker。
    • 加注倍数可选择1倍或3倍底注；若玩家弃牌则加注无效。
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

        # 关闭按钮
        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)

        # 绑定鼠标滚轮
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

# ------------------------- 入口 -------------------------
def main(initial_balance=10000, username="Guest"):
    app = WildFivePokerGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")