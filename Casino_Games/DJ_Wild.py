import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
import math
import secrets
import subprocess, sys
import time
from itertools import product, combinations

# =========================================================
# 基础数据（来自 DJ_Wild）
# =========================================================
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

# =========================================================
# 文件操作（用户余额）
# =========================================================
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
    try:
        with open(path, 'r', encoding='utf-8') as f:
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

# =========================================================
# 牌局历史日志（DJ Wild）
# =========================================================
def dj_wild_log_path() -> str:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "DJ_Wild.json")

def save_dj_wild_history(deck, player_cards, dealer_cards, result_info=None):
    log_path = dj_wild_log_path()
    data = {
        "history_record": {
            "player_win": 0,
            "dealer_win": 0,
            "push": 0,
            "fold": 0,
            "game": 0
        },
        "history": []
    }
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict) and "history_record" in loaded:
                    for key in data["history_record"]:
                        if key not in loaded["history_record"]:
                            loaded["history_record"][key] = 0
                    data["history_record"] = loaded["history_record"]
                    if "history" in loaded:
                        data["history"] = loaded["history"]
                elif isinstance(loaded, list):
                    # 旧格式迁移
                    data["history"] = loaded
                    stats = {"player_win": 0, "dealer_win": 0, "fold": 0, "push": 0, "game": len(loaded)}
                    for rec in loaded:
                        if "result" in rec and "winner" in rec["result"]:
                            winner = rec["result"]["winner"]
                            if winner == "player":
                                stats["player_win"] += 1
                            elif winner == "dealer":
                                stats["dealer_win"] += 1
                            elif winner == "fold":
                                stats["fold"] += 1
                            elif winner == "push":
                                stats["push"] += 1
                    data["history_record"] = stats
        except Exception as e:
            print(f"读取历史文件出错: {e}")

    max_id = 0
    for rec in data["history"]:
        if "game_id" in rec and isinstance(rec["game_id"], int):
            if rec["game_id"] > max_id:
                max_id = rec["game_id"]
    new_game_id = max_id + 1

    stats = data["history_record"]
    stats["game"] += 1

    winner = None
    if result_info:
        if result_info.get("fold", False):
            winner = "fold"
            stats["fold"] += 1
        elif "winner" in result_info:
            winner = result_info["winner"]
            if winner == "player":
                stats["player_win"] += 1
            elif winner == "dealer":
                stats["dealer_win"] += 1
            elif winner == "push":
                stats["push"] += 1

    record = {
        "game_id": new_game_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "deck_order": [str(c) for c in deck.full_deck],
        "cut_position": deck.cut_position,
        "player_cards": [str(c) for c in player_cards],
        "dealer_cards": [str(c) for c in dealer_cards],
        "result": result_info if result_info else {}
    }
    if winner is not None:
        record["result"]["winner"] = winner
    data["history"].append(record)

    if len(data["history"]) > 50:
        data["history"] = data["history"][-50:]

    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# =========================================================
# 卡牌（支持 JOKER）
# =========================================================
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

# =========================================================
# 牌堆（带 JOKER）
# =========================================================
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
            self._secure_shuffle()
            self.cut_position = secrets.randbelow(53)
        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + i) % len(self.full_deck) for i in range(len(self.full_deck))]
        self.pointer = 0
        self.card_sequence = [self.full_deck[i] for i in self.indexes]

    def _secure_shuffle(self):
        for i in range(len(self.full_deck)-1, 0, -1):
            j = secrets.randbelow(i+1)
            self.full_deck[i], self.full_deck[j] = self.full_deck[j], self.full_deck[i]

    def deal(self, n=1):
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt

# =========================================================
# DJ Wild 手牌评估（万能牌枚举法）
# =========================================================
def best_hand_with_wildcards(cards):
    wild_indices = [i for i, c in enumerate(cards) if c.is_wild()]

    if len(wild_indices) == 5:
        return "五张王牌", HAND_RANK["五张王牌"], [99] * 5, cards, [99] * 5

    non_wild_cards = [c for i, c in enumerate(cards) if i not in wild_indices]
    flush_suit = None
    if non_wild_cards and len(set(c.suit for c in non_wild_cards)) == 1:
        flush_suit = non_wild_cards[0].suit
    default_suit = '♠'

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
                if c.is_joker:
                    suit = flush_suit if flush_suit else default_suit
                    new_rank = RANKS[v - 2]
                    new_card = Card(suit, new_rank)
                else:  # 普通2
                    new_card = Card(c.suit, RANKS[v - 2])
                temp_cards.append(new_card)
                temp_values.append(v)
                vi += 1
            else:
                temp_cards.append(Card(c.suit, c.rank))
                temp_values.append(c.value)

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
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    is_flush = len(set(suits)) == 1
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
    if is_flush and is_straight and values[0]==14 and values[-1]==10:
        return "皇家同花顺", HAND_RANK["皇家同花顺"], [14]
    if is_flush and is_straight:
        return "同花顺", HAND_RANK["同花顺"], [straight_high]
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

    if rank_val in [HAND_RANK["顺子"], HAND_RANK["同花顺"], HAND_RANK["皇家同花顺"]]:
        effs = [eff for _, eff, _ in cards_with_eff]
        if 14 in effs and 2 in effs and len(set(effs)) == 5:
            cards_with_eff.sort(key=lambda x: 1 if x[1] == 14 else x[1])
        else:
            cards_with_eff.sort(key=lambda x: x[1])
        return [c for c, _, _ in cards_with_eff]

    from collections import Counter
    cnt = Counter(eff for _, eff, _ in cards_with_eff)
    cards_with_eff.sort(key=lambda x: (cnt[x[1]], x[1], not x[2]), reverse=True)
    return [c for c, _, _ in cards_with_eff]

# =========================================================
# 游戏逻辑类（DJ Wild）
# =========================================================
class DJWildGame:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.player_hand = []
        self.dealer_hand = []
        self.ante = 0
        self.blind = 0
        self.bonus_bet = 0
        self.double_side_bet = 0
        self.play_bet = 0
        self.stage = "pre_flop"
        self.folded = False
        self.cards_revealed = {
            "player": [False]*5,
            "dealer": [False]*5
        }

    def deal_initial(self):
        self.player_hand = self.deck.deal(5)
        self.dealer_hand = self.deck.deal(5)

# =========================================================
# 主 GUI（仿 Caribbean_Stud_Poker 风格，融合 DJ Wild）
# =========================================================
ROOT_BG = "#1B3D31"
PANEL_BG = "#F2E6C9"
HEADER_BG = "#D8B46A"
TITLE_FG = "#2A1B08"
GOLD = "#D4AF37"

class DJWildGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("DJ Wild 梭哈扑克")
        self.geometry("1150x750+50+10")
        self.resizable(0,0)
        self.configure(bg=ROOT_BG)

        self.username = username
        self.balance = initial_balance
        self.game = DJWildGame()
        self.card_images = {}
        self.original_images = {}
        self.animation_queue = []
        self.animation_in_progress = False
        self.card_positions = {}
        self.active_card_labels = []
        self.selected_chip = None
        self.chip_buttons = []
        self.chip_texts = {}
        self.last_win = 0
        self.last_bet = None
        self.repeat_bet_btn = None
        self.auto_reset_timer = None
        self.buttons_disabled = False
        self.win_details = {
            "ante": 0,
            "blind": 0,
            "play": 0,
            "bonus": 0,
            "double_side": 0
        }
        self.bet_widgets = {}
        self.game_in_progress = False

        # 高额模式
        self.high_bet_mode = False
        # 动态密码（时间四位）
        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # 底注联动更新盲注（盲注自动等于底注）
        self.ante_var.trace_add('write', self.on_ante_changed)

    def on_close(self):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
        self.destroy()
        self.quit()

    # ---------- 加载扑克牌（交替 Poker1/Poker2） ----------
    def _load_assets(self):
        card_size = (100, 140)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not hasattr(self, 'current_poker_folder'):
            self.current_poker_folder = random.choice(['Poker1', 'Poker2'])
        else:
            self.current_poker_folder = 'Poker2' if self.current_poker_folder == 'Poker1' else 'Poker1'
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', self.current_poker_folder)
        suit_mapping = {'♠':'Spade','♥':'Heart','♦':'Diamond','♣':'Club', 'JOKER':'JOKER'}
        self.original_images = {}
        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_img_orig = Image.open(back_path)
            self.original_images["back"] = back_img_orig
            back_img = back_img_orig.resize(card_size)
            self.back_image = ImageTk.PhotoImage(back_img)
        except:
            img_orig = Image.new('RGB', card_size, 'black')
            self.original_images["back"] = img_orig
            self.back_image = ImageTk.PhotoImage(img_orig)
        for suit in SUITS + ['JOKER']:
            for rank in RANKS:
                if suit == 'JOKER':
                    filename = "JOKER-A.png"
                else:
                    suit_name = suit_mapping.get(suit, suit)
                    filename = f"{suit_name}{rank}.png"
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
                        try:
                            font = ImageFont.truetype("arial.ttf", 20)
                        except:
                            font = ImageFont.load_default()
                        text = f"{rank}{suit}" if suit != 'JOKER' else "JOKER"
                        tw, th = draw.textsize(text, font=font)
                        draw.text(((card_size[0]-tw)//2, (card_size[1]-th)//2), text, fill="white", font=font)
                        self.original_images[(suit, rank)] = img_orig
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
                except:
                    img_orig = Image.new('RGB', card_size, 'red')
                    draw = ImageDraw.Draw(img_orig)
                    try:
                        font = ImageFont.truetype("arial.ttf", 20)
                    except:
                        font = ImageFont.load_default()
                    draw.text((10,10), "Error", fill="white", font=font)
                    self.original_images[(suit, rank)] = img_orig
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)

    # ---------- 筹码选择 ----------
    def select_chip(self, chip_text):
        self.selected_chip = chip_text
        for chip in self.chip_buttons:
            chip.delete("highlight")
            for item_id in chip.find_all():
                if chip.type(item_id) == 'oval':
                    x1,y1,x2,y2 = chip.coords(item_id)
                    chip.create_oval(x1,y1,x2,y2, outline='black', width=2)
                    break
        for chip in self.chip_buttons:
            text_id = None
            oval_id = None
            for item_id in chip.find_all():
                t = chip.type(item_id)
                if t == 'text':
                    text_id = item_id
                elif t == 'oval':
                    oval_id = item_id
            if text_id and chip.itemcget(text_id, 'text') == chip_text:
                x1,y1,x2,y2 = chip.coords(oval_id)
                chip.create_oval(x1,y1,x2,y2, outline='#2f00ff', width=3, tags="highlight")
                break

    # ---------- 添加筹码到下注区域 ----------
    def add_chip_to_bet(self, bet_type):
        if not self.selected_chip:
            return
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K','')) * 1000
        else:
            chip_value = float(chip_text)

        limits = {
            "ante": (50000 if self.high_bet_mode else 10000),
            "bonus": (12500 if self.high_bet_mode else 2500),
            "double_side": (12500 if self.high_bet_mode else 2500)
        }
        if bet_type in limits:
            current = float(self.__getattribute__(f"{bet_type}_var").get())
            limit = limits[bet_type]
            if current >= limit:
                names = {"ante":"底注","bonus":"红利","double_side":"双向坏注"}
                messagebox.showwarning("下注限制", f"{names[bet_type]}已满，不能再下注！")
                return
            new_amount = current + chip_value
            if new_amount > limit:
                new_amount = limit
                if current > 0:
                    names = {"ante":"底注","bonus":"红利","double_side":"双向坏注"}
                    messagebox.showwarning("下注限制", f"{names[bet_type]}已达上限，自动调整为 {int(new_amount)}")
            self.__getattribute__(f"{bet_type}_var").set(str(int(new_amount)))

    # ---------- 重置单个下注（右键） ----------
    def reset_single_bet(self, bet_type, event):
        if bet_type == "ante":
            self.ante_var.set("0")
        elif bet_type == "bonus":
            self.bonus_var.set("0")
        elif bet_type == "double_side":
            self.double_side_var.set("0")
        if bet_type in self.bet_widgets:
            widget = self.bet_widgets[bet_type]
            original_bg = widget.cget('bg')
            widget.config(bg='#FFCDD2')
            self.after(500, lambda: widget.config(bg=original_bg))

    def clear_btn_frame(self):
        for widget in self.btn_frame.winfo_children():
            widget.destroy()

    def add_main_buttons(self):
        self.clear_btn_frame()
        self.reset_bets_button = tk.Button(
            self.btn_frame, text="重设金额", command=self.reset_bets,
            font=('Arial',12,'bold'), bg='#F44336', fg='white',
            relief=tk.RAISED, bd=2, cursor="hand2", width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=5)

        self.repeat_bet_btn = tk.Button(
            self.btn_frame, text="重复上局下注", command=self.apply_last_bet,
            font=('Arial',12,'bold'), bg='#FFC107', fg='black',
            relief=tk.RAISED, bd=2, cursor="hand2", width=12,
            state=tk.NORMAL if self.last_bet is not None else tk.DISABLED
        )
        self.repeat_bet_btn.pack(side=tk.LEFT, padx=5)

        self.start_button = tk.Button(
            self.btn_frame, text="开始游戏", command=self.start_game,
            font=('Arial',12,'bold'), bg='#4CAF50', fg='white',
            relief=tk.RAISED, bd=2, cursor="hand2", width=10
        )
        self.start_button.pack(side=tk.LEFT, padx=5)

    # ---------- 创建主界面 ----------
    def _create_widgets(self):
        main_frame = tk.Frame(self, bg=ROOT_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧牌桌
        table_canvas = tk.Canvas(main_frame, bg=ROOT_BG, highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        table_canvas.create_rectangle(0,0,725,720, fill=ROOT_BG, outline=GOLD, width=5)

        # 庄家区域
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=60, y=60, width=600, height=230)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial',18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 中间提示（显示万能牌规则）
        self.ante_info_label = tk.Label(
            table_canvas,
            text='扑克牌"2"和"鬼牌"均为万能牌\n可替代任意花色点数的扑克\n\n庄家任意牌型均为及格',
            font=('Arial', 26),
            bg=ROOT_BG,
            fg='#FFD700'
        )
        self.ante_info_label.update_idletasks()
        label_width = self.ante_info_label.winfo_width()
        table_canvas.update_idletasks()
        canvas_width = table_canvas.winfo_width()
        center_x = (canvas_width - label_width)//2
        self.ante_info_label.place(x=center_x+360, y=290, anchor='n')

        # 玩家区域
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=60, y=450, width=600, height=230)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial',18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 右侧控制面板
        right_panel = tk.Frame(main_frame, bg=ROOT_BG, width=400)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        right_panel.pack_propagate(False)

        # 信息卡片
        info_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        info_card.pack(fill=tk.X, pady=3)
        header_info = tk.Frame(info_card, bg=HEADER_BG)
        header_info.pack(fill=tk.X)
        body_info = tk.Frame(info_card, bg=PANEL_BG)
        body_info.pack(fill=tk.X, padx=10, pady=8)

        self.balance_label = tk.Label(body_info, text=f"余额: ${self.balance:,.2f}", font=('Arial',16,'bold'),
                                      bg=PANEL_BG, fg='black')
        self.balance_label.pack(side=tk.LEFT)
        self.stage_label = tk.Label(body_info, text="翻牌前", font=('Arial',16,'bold'),
                                    bg=PANEL_BG, fg='#A88100')
        self.stage_label.pack(side=tk.RIGHT)

        # ================== 赔率速查表卡片 ==================
        odds_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        odds_card.pack(fill=tk.X, pady=3)
        header_odds = tk.Frame(odds_card, bg=HEADER_BG)
        header_odds.pack(fill=tk.X)
        tk.Label(header_odds, text="赔率速查表", font=('Arial',13,'bold'),
                bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_odds = tk.Frame(odds_card, bg=PANEL_BG)
        body_odds.pack(fill=tk.X, padx=8, pady=5)

        # 表头（5列）
        headers = ["牌型", "盲注", "红利(有万能)", "红利(无万能)", "双向坏注"]
        for col, text in enumerate(headers):
            tk.Label(body_odds, text=text, font=('Arial',9,'bold'),
                    bg='#D8B46A', fg='#2A1B08', borderwidth=1, relief=tk.SOLID,
                    padx=4, pady=2, width=10).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 创建两行数据，存储标签引用
        self.odds_rows = []
        default_data = [
            ("皇家同花顺", "50:1", "90:1", "1000:1", "10000:1"),
            ("五条", "10:1", "70:1", "-", "10000:1")
        ]
        for r, row_data in enumerate(default_data, start=1):
            row_labels = []
            for c, text in enumerate(row_data):
                bg_color = '#F0F0F0' if r % 2 == 0 else '#E8E8E8'
                lbl = tk.Label(body_odds, text=text, font=('Arial',9),
                            bg=bg_color, padx=4, pady=2, relief=tk.SOLID, borderwidth=1, width=10)
                lbl.grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                row_labels.append(lbl)
            self.odds_rows.append(row_labels)

        # 列权重均匀分配
        for col in range(5):
            body_odds.columnconfigure(col, weight=1)

        # 限红信息卡片（可点击切换高额模式）
        limit_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        limit_card.pack(fill=tk.X, pady=3)
        header_limit = tk.Frame(limit_card, bg=HEADER_BG)
        header_limit.pack(fill=tk.X)
        tk.Label(header_limit, text="下注上限", font=('Arial',13,'bold'),
                 bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_limit = tk.Frame(limit_card, bg=PANEL_BG)
        body_limit.pack(fill=tk.X, padx=10, pady=8)

        table_frame = tk.Frame(body_limit, bg=PANEL_BG, bd=2, relief=tk.SOLID)
        table_frame.pack(fill=tk.X)
        titles = ["底注最低","底注最高","边注最高"]
        for col,title in enumerate(titles):
            lbl = tk.Label(table_frame, text=title, font=('Arial',11,'bold'),
                           bg=PANEL_BG, fg='#2A1B08', borderwidth=1, relief=tk.SOLID, padx=5, pady=5)
            lbl.grid(row=0, column=col, sticky="nsew", padx=0, pady=0)
        self.min_ante_label = tk.Label(table_frame, text="$10", font=('Arial',12,'bold'),
                                       bg=PANEL_BG, fg="#A88100", borderwidth=1, relief=tk.SOLID, padx=5, pady=5)
        self.min_ante_label.grid(row=1, column=0, sticky="nsew")
        self.max_ante_label = tk.Label(table_frame, text="$10,000", font=('Arial',12,'bold'),
                                       bg=PANEL_BG, fg="#A88100", borderwidth=1, relief=tk.SOLID, padx=5, pady=5)
        self.max_ante_label.grid(row=1, column=1, sticky="nsew")
        self.max_side_label = tk.Label(table_frame, text="$2,500", font=('Arial',12,'bold'),
                                       bg=PANEL_BG, fg="#A88100", borderwidth=1, relief=tk.SOLID, padx=5, pady=5)
        self.max_side_label.grid(row=1, column=2, sticky="nsew")
        for col in range(3):
            table_frame.columnconfigure(col, weight=1)
        # 点击切换高额模式
        for w in [limit_card, header_limit, body_limit, table_frame,
                  self.min_ante_label, self.max_ante_label, self.max_side_label]:
            w.bind("<Button-1>", self.toggle_high_bet_limits)

        # 筹码与下注卡片
        combined_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        combined_card.pack(fill=tk.X, pady=3)
        header_combined = tk.Frame(combined_card, bg=HEADER_BG)
        header_combined.pack(fill=tk.X)
        tk.Label(header_combined, text="筹码与下注", font=('Arial',13,'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_combined = tk.Frame(combined_card, bg=PANEL_BG)
        body_combined.pack(fill=tk.X, padx=10, pady=8)
        body_combined.columnconfigure(0, weight=1)
        body_combined.columnconfigure(1, weight=1)
        body_combined.columnconfigure(2, weight=1)

        # 筹码按钮行
        chip_row = tk.Frame(body_combined, bg=PANEL_BG)
        chip_row.grid(row=0, column=0, columnspan=3, pady=(0,8), sticky='ew')
        for i in range(6):
            chip_row.columnconfigure(i, weight=1)
        self.chip_container = chip_row

        chip_configs = [
            ('$10','#ffa500','black'),
            ("$25",'#00ff00','black'),
            ("$100",'#000000','white'),
            ("$500","#FF7DDA",'black'),
            ("$1K",'#ffffff','black'),
            ("$2.5K",'#ff0000','white'),
        ]
        self.chip_buttons = []
        self.chip_texts = {}
        for i,(text,bg_color,fg_color) in enumerate(chip_configs):
            cell = tk.Frame(chip_row, bg=PANEL_BG)
            cell.grid(row=0, column=i, padx=2, pady=2, sticky='nsew')
            chip_canvas = tk.Canvas(cell, width=50, height=50, bg=PANEL_BG, highlightthickness=0)
            chip_canvas.pack(anchor='center')
            chip_canvas.create_oval(2,2,49,49, fill=bg_color, outline='black')
            chip_canvas.create_text(25.5,25.5, text=text, fill=fg_color, font=('Arial',12,'bold'))
            chip_canvas.bind("<Button-1>", lambda e,t=text: self.select_chip(t))
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text
        self.select_chip("$10")

        # 下注行：底注、盲注（自动同步）、红利、双向坏注、加注
        row_bonus = tk.Frame(body_combined, bg=PANEL_BG)
        row_bonus.grid(row=2, column=0, columnspan=3, sticky='ew', pady=4)
        tk.Label(row_bonus, text="      红利:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT)
        self.bonus_var = tk.StringVar(value="0")
        self.bonus_display = tk.Label(row_bonus, textvariable=self.bonus_var, font=('Arial',12),
                                      bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.bonus_display.pack(side=tk.LEFT, padx=5)
        self.bonus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bonus"))
        self.bonus_display.bind("<Button-3>", lambda e: self.reset_single_bet("bonus", e))
        self.bet_widgets["bonus"] = self.bonus_display

        tk.Label(row_bonus, text="双向坏注:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=(20,5))
        self.double_side_var = tk.StringVar(value="0")
        self.double_side_display = tk.Label(row_bonus, textvariable=self.double_side_var, font=('Arial',12),
                                            bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.double_side_display.pack(side=tk.LEFT, padx=5)
        self.double_side_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("double_side"))
        self.double_side_display.bind("<Button-3>", lambda e: self.reset_single_bet("double_side", e))
        self.bet_widgets["double_side"] = self.double_side_display

        # 第三行：底注 + 盲注（原始 DJ_Wild 格式：底注和盲注并排，中间有 "盲注" 标签）
        row_ante = tk.Frame(body_combined, bg=PANEL_BG)
        row_ante.grid(row=3, column=0, columnspan=3, sticky='ew', pady=4)
        tk.Label(row_ante, text="      底注:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT)
        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(row_ante, textvariable=self.ante_var, font=('Arial',12),
                                     bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.bet_widgets["ante"] = self.ante_display

        tk.Label(row_ante, text="=", font=('Arial', 12, "bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=5)
        self.blind_var = tk.StringVar(value="0")
        self.blind_display = tk.Label(row_ante, textvariable=self.blind_var, font=('Arial', 12),
                                    bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.blind_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["blind"] = self.blind_display
        tk.Label(row_ante, text=": 盲注", font=('Arial', 12, "bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=5)

        # 第四行：加注（可点击切换）
        row_play = tk.Frame(body_combined, bg=PANEL_BG)
        row_play.grid(row=4, column=0, columnspan=3, sticky='ew', pady=4)
        tk.Label(row_play, text="      加注:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT)
        self.play_var = tk.StringVar(value="0")
        self.play_display = tk.Label(row_play, textvariable=self.play_var, font=('Arial',12),
                                     bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.play_display.pack(side=tk.LEFT, padx=5)
        self.play_display.bind("<Button-1>", self.toggle_play_bet)
        self.bet_widgets["play"] = self.play_display

        # 操作卡片
        action_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        action_card.pack(fill=tk.X, pady=3)
        header_action = tk.Frame(action_card, bg=HEADER_BG)
        header_action.pack(fill=tk.X)
        tk.Label(header_action, text="操作", font=('Arial',13,'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_action = tk.Frame(action_card, bg=PANEL_BG)
        body_action.pack(fill=tk.X, padx=10, pady=8)

        self.status_label = tk.Label(
            body_action, text="设置下注金额并开始游戏", font=('Arial',12,'bold'),
            bg=PANEL_BG, fg='#2A1B08', height=1
        )
        self.status_label.pack(fill=tk.X, pady=4)

        self.btn_frame = tk.Frame(body_action, bg=PANEL_BG)
        self.btn_frame.pack(fill=tk.X, pady=5)
        self.add_main_buttons()

        # 底部信息卡片
        info_bottom_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        info_bottom_card.pack(fill=tk.X, pady=3)
        body_bottom = tk.Frame(info_bottom_card, bg=PANEL_BG)
        body_bottom.pack(fill=tk.X, padx=10, pady=8)

        self.current_bet_label = tk.Label(
            body_bottom, text="本局下注: $0.00", font=('Arial',12), bg=PANEL_BG, fg='black'
        )
        self.current_bet_label.pack(anchor='w')
        row_last = tk.Frame(body_bottom, bg=PANEL_BG)
        row_last.pack(fill=tk.X, pady=2)
        self.last_win_label = tk.Label(
            row_last, text="上局获胜: $0.00", font=('Arial',12), bg=PANEL_BG, fg='black'
        )
        self.last_win_label.pack(side=tk.LEFT)
        self.info_button = tk.Button(
            row_last, text="ℹ️", command=self.show_game_instructions,
            bg='#4B8BBE', fg='white', font=('Arial',12), width=2, relief=tk.FLAT
        )
        self.info_button.pack(side=tk.RIGHT)

        # 初始化赔率表为默认
        self.reset_odds_table()

    # ---------- 赔率表更新方法 ----------
    def reset_odds_table(self):
        """重置赔率表为初始状态（皇家同花顺、五条）"""
        default_data = [
            ("皇家同花顺", "50:1", "90:1", "1000:1", "10000:1"),
            ("五条", "10:1", "70:1", "-", "10000:1")
        ]
        for r, row_data in enumerate(default_data):
            for c, text in enumerate(row_data):
                self.odds_rows[r][c].config(text=text)

    def set_odds_row(self, row_index, name, blind, bonus_w, bonus_wo, double):
        """设置赔率表中某一行的所有列"""
        labels = self.odds_rows[row_index]
        labels[0].config(text=name)
        labels[1].config(text=blind)
        labels[2].config(text=bonus_w)
        labels[3].config(text=bonus_wo)
        labels[4].config(text=double)

    def get_hand_ranks(self, hand):
        """返回 (含万能的牌型名, 无万能的牌型名, 是否有Joker)"""
        # 含万能牌型
        rank_w, _, _, _, _ = best_hand_with_wildcards(hand)
        # 检查是否有Joker
        has_joker = any(c.is_joker for c in hand)
        rank_no = None
        if not has_joker:
            # 无Joker时，将2视为普通2，评估无万能牌型
            fixed_cards = []
            for c in hand:
                if c.rank == '2' and not c.is_joker:
                    fixed_cards.append(Card(c.suit, '2'))
                else:
                    fixed_cards.append(Card(c.suit, c.rank))
            rank_no, _, _ = evaluate_fixed_hand(fixed_cards)
        return rank_w, rank_no, has_joker

    def get_payout_values(self, rank_w, rank_no, has_joker):
        """返回 (blind, bonus_with_wild, bonus_without_wild, double_side)"""
        blind = BLIND_PAYOUT.get(rank_w, 0)
        # 盲注：对于三条及以下牌型，赔付为0（平局），用 -1 表示
        if blind == 0 and rank_w in ["三条", "两对", "一对", "高牌"]:
            blind = -1
        # 红利（有万能牌）：始终使用当前牌型在有万能规则下的赔率
        bonus_w = BONUS_PAYOUT.get((rank_w, True), 0)
        # 红利（无万能牌）：始终使用当前牌型在无万能规则下的赔率，无论手牌是否包含Joker
        bonus_wo = BONUS_PAYOUT.get((rank_w, False), 0)
        # 双向坏注
        double = DOUBLE_SIDE_PAYOUT.get(rank_w, 0)
        return blind, bonus_w, bonus_wo, double

    def fmt_payout(self, value):
        """将赔率数值转为显示字符串，-1显示'平局'，0显示'-'，>0显示'X:1'"""
        if value == -1:
            return "平局"
        if value == 0:
            return "-"
        return f"{value}:1"

    def update_odds_table(self):
        """根据当前牌局状态更新赔率速查表"""
        # 判断牌是否已亮
        player_revealed = all(self.game.cards_revealed["player"]) if hasattr(self.game, 'cards_revealed') else False
        dealer_revealed = all(self.game.cards_revealed["dealer"]) if hasattr(self.game, 'cards_revealed') else False

        # 如果游戏未开始或未发牌，显示默认
        if not self.game.player_hand or (not player_revealed and not dealer_revealed):
            self.reset_odds_table()
            return

        # 场景1：仅玩家亮牌 → 行0显示“~庄家手牌~”，行1显示玩家牌型
        if player_revealed and not dealer_revealed:
            self.set_odds_row(0, "~庄家手牌~", "~", "~", "~", "~")
            hand = self.game.player_hand
            rank_w, rank_no, has_joker = self.get_hand_ranks(hand)
            blind, bonus_w, bonus_wo, double = self.get_payout_values(rank_w, rank_no, has_joker)
            self.set_odds_row(1, rank_w,
                            self.fmt_payout(blind),
                            self.fmt_payout(bonus_w),
                            self.fmt_payout(bonus_wo),
                            self.fmt_payout(double))
            return

        # 场景2：玩家和庄家都已亮牌 → 行0显示庄家牌型，行1显示玩家牌型
        if player_revealed and dealer_revealed:
            # 庄家牌型（行0）
            hand = self.game.dealer_hand
            rank_w, rank_no, has_joker = self.get_hand_ranks(hand)
            blind, bonus_w, bonus_wo, double = self.get_payout_values(rank_w, rank_no, has_joker)
            self.set_odds_row(0, rank_w,
                            self.fmt_payout(blind),
                            self.fmt_payout(bonus_w),
                            self.fmt_payout(bonus_wo),
                            self.fmt_payout(double))
            # 玩家牌型（行1）
            hand = self.game.player_hand
            rank_w, rank_no, has_joker = self.get_hand_ranks(hand)
            blind, bonus_w, bonus_wo, double = self.get_payout_values(rank_w, rank_no, has_joker)
            self.set_odds_row(1, rank_w,
                            self.fmt_payout(blind),
                            self.fmt_payout(bonus_w),
                            self.fmt_payout(bonus_wo),
                            self.fmt_payout(double))
            return

        # 其他情况（理论上不会发生）重置为默认
        self.reset_odds_table()

    # ---------- 底注联动更新盲注 ----------
    def on_ante_changed(self, *args):
        try:
            ante = int(self.ante_var.get())
        except ValueError:
            ante = 0
        self.blind_var.set(str(ante))
        # 如果当前加注不为0，则更新为底注×2
        current_play = self.play_var.get()
        if current_play not in ("0", "0.0"):
            self.play_var.set(str(ante * 2))

    # ---------- 加注切换（预下注） ----------
    def toggle_play_bet(self, event=None):
        try:
            ante = int(self.ante_var.get())
        except ValueError:
            ante = 0
        if ante <= 0:
            messagebox.showwarning("提示", "请先设置底注金额")
            return
        current_play = self.play_var.get()
        if current_play in ("0", "0.0"):
            new_play = ante * 2
            self.play_var.set(str(new_play))
        else:
            self.play_var.set("0")

    # ---------- 高额模式切换 ----------
    def toggle_high_bet_limits(self, event=None):
        if self.game_in_progress:
            return
        current_password = time.strftime("%H%M")
        if not self.high_bet_mode:
            pwd = simpledialog.askstring("高额下注", "请输入密码：", parent=self)
            if pwd is None:
                return
            if pwd.strip() != current_password:
                messagebox.showerror("错误","密码错误")
                return
            self.high_bet_mode = True
            self.reset_bets()
        else:
            self.high_bet_mode = False
            self.reset_bets()
        self._update_limits_display()
        self._rebuild_chips()

    def _update_limits_display(self):
        if self.high_bet_mode:
            self.min_ante_label.config(text="$100")
            self.max_ante_label.config(text="$50,000")
            self.max_side_label.config(text="$12,500")
        else:
            self.min_ante_label.config(text="$10")
            self.max_ante_label.config(text="$10,000")
            self.max_side_label.config(text="$2,500")

    def _rebuild_chips(self):
        for widget in self.chip_container.winfo_children():
            widget.destroy()
        self.chip_buttons = []
        self.chip_texts = {}
        self.selected_chip = None

        if self.high_bet_mode:
            chip_configs = [
                ("$100", '#000000', 'white'),
                ("$500", "#FF7DDA", 'black'),
                ("$1K", '#ffffff', 'black'),
                ("$5K", '#ff0000', 'white'),
                ("$10K", '#00fbff', 'black'),
                ("$50K", '#00ffae', 'black')
            ]
            default = "$100"
        else:
            chip_configs = [
                ('$10', '#ffa500', 'black'),
                ("$25", '#00ff00', 'black'),
                ("$100", '#000000', 'white'),
                ("$500", "#FF7DDA", 'black'),
                ("$1K", '#ffffff', 'black'),
                ("$2.5K", '#ff0000', 'white')
            ]
            default = "$10"

        for i, (text, bg_color, fg_color) in enumerate(chip_configs):
            cell = tk.Frame(self.chip_container, bg=PANEL_BG)
            cell.grid(row=0, column=i, padx=2, pady=2, sticky='nsew')
            chip_canvas = tk.Canvas(cell, width=50, height=50, bg=PANEL_BG, highlightthickness=0)
            chip_canvas.pack(anchor='center')
            chip_canvas.create_oval(2, 2, 49, 49, fill=bg_color, outline='black')
            chip_canvas.create_text(25.5, 25.5, text=text, fill=fg_color, font=('Arial', 12, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text

        self.select_chip(default)

    # ---------- 游戏规则说明 ----------
    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("DJ Wild 梭哈扑克 规则")
        win.geometry("800x700")
        win.resizable(False,False)
        win.configure(bg='#F0F0F0')
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main_frame, bg='#F0F0F0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content_frame = tk.Frame(canvas, bg='#F0F0F0')
        canvas_frame = canvas.create_window((0,0), window=content_frame, anchor='nw')

        rules_text = """
        DJ Wild 梭哈扑克 游戏规则

        1. 万能牌（Wild Card）：
        - 所有点数 2 的牌 以及 JOKER 均为万能牌。
        - 万能牌可以变成任意点数（2~A）和任意花色，用于组成最佳牌型。

        2. 下注类型：
        a. 底注：必须下注，自动同步为盲注的金额。
        b. 盲注：金额自动等于底注，无需单独设置。
        c. 红利：可选下注，根据玩家手牌（包括万能牌）支付，赢则同时赢取红利注。
        d. 双向坏注：可选下注，同时比较玩家与庄家牌型，取较低牌型支付。
        e. 加注：决策阶段可选，金额为底注×2。也可提前预下注，直接进入摊牌（盲注模式）。

        3. 游戏流程：
        a. 下注阶段：设置底注（盲注自动同步）、可选下注（红利、双向坏注），点击“开始游戏”。
        b. 发牌：玩家和庄家各发5张牌，所有牌面朝下。
        c. 翻牌：玩家牌全部翻开，系统自动结算红利（若下注）。
        d. 决策阶段（仅当未预下注时）：
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

        tk.Label(content_frame, text=rules_text, font=('微软雅黑',11),
                 bg='#F0F0F0', justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X, padx=10, pady=5)

        tk.Label(content_frame, text="赔付表汇总", font=('微软雅黑',14,'bold'),
                 bg='#F0F0F0').pack(fill=tk.X, padx=10, pady=(20,10), anchor='center')

        payout_frame = tk.Frame(content_frame, bg='#F0F0F0')
        payout_frame.pack(fill=tk.X, padx=20, pady=5)
        headers = ["牌型","盲注#","红利(有万能牌)##","红利(无万能牌)","双向坏注"]
        data = [
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
        for col,h in enumerate(headers):
            tk.Label(payout_frame, text=h, font=('微软雅黑',10,'bold'),
                     bg='#4B8BBE', fg='white', padx=10, pady=5,
                     anchor='center').grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
        for r,row_data in enumerate(data, start=1):
            bg = '#E0E0E0' if r%2==0 else '#F0F0F0'
            for c,txt in enumerate(row_data):
                tk.Label(payout_frame, text=txt, font=('微软雅黑',10),
                         bg=bg, padx=10, pady=5, anchor='center'
                         ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
        for c in range(len(headers)):
            payout_frame.columnconfigure(c, weight=1)

        notes = """
        注：
        - 所有赔付倍率为盈利倍数，实际返还金额 = 下注额 × (赔率倍数 + 1)。
        - 红利结算时，系统会分别计算“无万能牌”（即2视为普通2）和“有万能牌”的最佳牌型，取赔付较高的结果。
        - 双向坏注：需要双方牌型均 ≥ 三条，且只对较低的牌型支付。
        # 盲注的获胜条件是击败庄家。
        ## JOKER 始终视为万能牌；普通 2 在无万能牌计算时视为普通2，在有万能牌计算时可变为任意牌。
        """
        tk.Label(content_frame, text=notes, font=('微软雅黑',10),
                 bg='#F0F0F0', justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X, padx=10, pady=5)

        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=10)
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    # ---------- 更新余额 ----------
    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:,.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)

    # ---------- 更新手牌标签 ----------
    def update_hand_labels(self):
        if self.game.player_hand and len(self.game.player_hand)==5:
            rank_name, _, _, _, _ = best_hand_with_wildcards(self.game.player_hand)
            self.player_label.config(text=f"玩家 - {rank_name}" if rank_name else "玩家")
        if (self.game.stage=="showdown" or self.game.folded) and self.game.dealer_hand and len(self.game.dealer_hand)==5:
            rank_name, _, _, _, _ = best_hand_with_wildcards(self.game.dealer_hand)
            self.dealer_label.config(text=f"庄家 - {rank_name}" if rank_name else "庄家")
        # 更新赔率表
        self.update_odds_table()

    # ---------- 开始游戏 ----------
    def start_game(self):
        try:
            self.ante = int(self.ante_var.get())
            self.bonus_bet = int(self.bonus_var.get())
            self.double_side_bet = int(self.double_side_var.get())
            play_bet = int(self.play_var.get()) if self.play_var.get().lstrip('$').isdigit() else 0

            if self.high_bet_mode:
                min_ante, max_ante, max_side = 100, 50000, 12500
            else:
                min_ante, max_ante, max_side = 10, 10000, 2500

            if self.ante < min_ante:
                messagebox.showerror("错误", f"底注至少需要{min_ante}块")
                return
            if self.ante > max_ante:
                self.ante = max_ante
                self.ante_var.set(str(max_ante))
                messagebox.showwarning("下注限制", f"底注上限为{max_ante}，已自动调整")
            if self.bonus_bet > max_side:
                self.bonus_bet = max_side
                self.bonus_var.set(str(max_side))
            if self.double_side_bet > max_side:
                self.double_side_bet = max_side
                self.double_side_var.set(str(max_side))

            # 总下注 = 底注 + 盲注(同底注) + 红利 + 双向坏注 + 加注
            total_bet = self.ante + self.ante + self.bonus_bet + self.double_side_bet + play_bet
            if self.balance < total_bet:
                messagebox.showerror("错误", "余额不足以支付所有下注！")
                return
            self.balance -= total_bet
            self.game_in_progress = True

            # 记录下注信息（用于重复）
            self.last_bet = {
                'ante': self.ante,
                'bonus': self.bonus_bet,
                'double_side': self.double_side_bet,
                'play': play_bet
            }
            if self.repeat_bet_btn:
                self.repeat_bet_btn.config(state=tk.NORMAL)
            self.update_balance()

            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            self.last_win_label.config(text="上局获胜: $0.00")

            self.game.reset_game()
            self.game.deal_initial()
            self.game.ante = self.ante
            self.game.blind = self.ante
            self.game.bonus_bet = self.bonus_bet
            self.game.double_side_bet = self.double_side_bet
            self.game.play_bet = play_bet

            for widget in self.dealer_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.player_cards_frame.winfo_children():
                widget.destroy()

            self.animation_queue = []
            self.animation_in_progress = False
            self.active_card_labels = []
            self.card_positions = {}
            for i in range(5):
                card_id = f"player_{i}"
                self.card_positions[card_id] = {"current": (50,50), "target": (i*110,0)}
                self.animation_queue.append(card_id)
            for i in range(5):
                card_id = f"dealer_{i}"
                self.card_positions[card_id] = {"current": (50,50), "target": (i*110,0)}
                self.animation_queue.append(card_id)

            for widget in self.btn_frame.winfo_children():
                widget.destroy()

            if play_bet > 0:
                # 预下注模式，直接摊牌（盲注模式）
                self.stage_label.config(text="盲注模式")
                self.status_label.config(text="预下注已设，自动进入摊牌")
            else:
                self.stage_label.config(text="决策")
                self.status_label.config(text="做出决策: 弃牌或下注2倍")
                action_frame = tk.Frame(self.btn_frame, bg=PANEL_BG)
                action_frame.pack()
                self.fold_button = tk.Button(
                    action_frame, text="弃牌", command=self.fold_action,
                    state=tk.DISABLED, font=('Arial',12,'bold'), bg='#F44336', fg='white', width=10
                )
                self.fold_button.pack(side=tk.LEFT, padx=(0,10))
                self.play_button = tk.Button(
                    action_frame, text="下注2倍", command=self.play_action,
                    state=tk.DISABLED, font=('Arial',12,'bold'), bg='#4CAF50', fg='white', width=10
                )
                self.play_button.pack(side=tk.LEFT)

            # 禁用下注控件
            self.ante_display.unbind("<Button-1>")
            self.bonus_display.unbind("<Button-1>")
            self.double_side_display.unbind("<Button-1>")
            self.play_display.unbind("<Button-1>")
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")

            self.animate_deal()

        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")

    # ---------- 动画发牌 ----------
    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            self.after(500, self.reveal_player_cards)
            return
        self.animation_in_progress = True
        card_id = self.animation_queue.pop(0)
        if card_id.startswith("player"):
            frame = self.player_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.player_hand[idx] if idx < len(self.game.player_hand) else None
        else:
            frame = self.dealer_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.dealer_hand[idx] if idx < len(self.game.dealer_hand) else None

        card_label = tk.Label(frame, image=self.back_image, bg='#2a4a3c')
        card_label.place(x=self.card_positions[card_id]["current"][0],
                         y=self.card_positions[card_id]["current"][1]+20,
                         width=110, height=140)
        card_label.card_id = card_id
        card_label.card = card
        card_label.is_face_up = False
        card_label.is_moving = True
        card_label.target_pos = self.card_positions[card_id]["target"]
        self.active_card_labels.append(card_label)
        self.animate_card_move(card_label)

    def animate_card_move(self, card_label):
        if not hasattr(card_label, "target_pos") or card_label not in self.active_card_labels:
            return
        try:
            cx, cy = card_label.winfo_x(), card_label.winfo_y()
            tx, ty = card_label.target_pos
            dx, dy = tx-cx, ty-cy
            dist = math.hypot(dx,dy)
            if dist < 5:
                card_label.place(x=tx, y=ty, width=110, height=140)
                card_label.is_moving = False
                if card_label.target_pos == (50,50):
                    if card_label in self.active_card_labels:
                        self.active_card_labels.remove(card_label)
                    card_label.destroy()
                self.after(20, self.animate_deal)
                return
            step_x, step_y = dx*0.2, dy*0.2
            card_label.place(x=cx+step_x, y=cy+step_y, width=110, height=140)
            self.after(20, lambda: self.animate_card_move(card_label))
        except tk.TclError:
            if card_label in self.active_card_labels:
                self.active_card_labels.remove(card_label)

    # ---------- 翻开玩家牌（带翻转动画） ----------
    def reveal_player_cards(self):
        for i, lbl in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(lbl, "card") and not lbl.is_face_up:
                self.flip_card_animation(lbl)
                self.game.cards_revealed["player"][i] = True
        self.update_hand_labels()
        self.after(1000, self.after_player_reveal)

    def after_player_reveal(self):
        # 排序玩家手牌（无翻转，移动动画）
        self.sort_player_hand_no_flip()

    def sort_player_hand_no_flip(self):
        if not self.game.player_hand:
            return
        player_eval = best_hand_with_wildcards(self.game.player_hand)
        sorted_hand = sort_hand_for_display(self.game.player_hand, player_eval)
        labels = list(self.player_cards_frame.winfo_children())
        start_pos = {l: float(l.place_info()['x']) for l in labels if l.winfo_exists()}
        target = {}
        for idx, card in enumerate(sorted_hand):
            for l in labels:
                if hasattr(l, 'card') and l.card == card:
                    target[l] = idx*110
                    break
        steps = 15
        interval = 50
        data = []
        for l in start_pos:
            dx = (target[l] - start_pos[l]) / steps
            data.append((l, start_pos[l], dx))
        def step(step_count):
            if step_count > steps:
                for l,_,_ in data:
                    if l.winfo_exists():
                        l.place(x=target[l])
                self.game.player_hand = sorted_hand
                # 如果预下注>0，直接进入摊牌
                if self.game.play_bet > 0:
                    self.after(1000, self.show_showdown)
                else:
                    # 启用决策按钮
                    if hasattr(self, 'fold_button') and self.fold_button:
                        try: self.fold_button.config(state=tk.NORMAL)
                        except: pass
                    if hasattr(self, 'play_button') and self.play_button:
                        try: self.play_button.config(state=tk.NORMAL)
                        except: pass
                return
            for l,start_x,dx in data:
                if l.winfo_exists():
                    l.place(x=start_x + dx*step_count)
            self.after(interval, lambda: step(step_count+1))
        step(1)

    def reveal_dealer_first_card(self):
        dealer_children = self.dealer_cards_frame.winfo_children()
        if dealer_children:
            first = dealer_children[0]
            if hasattr(first, "card") and not first.is_face_up:
                self.animation_in_progress = True
                self.flip_card_animation(first)

    # ---------- 翻转动画 ----------
    def flip_card_animation(self, card_label):
        card = card_label.card
        front_img = self.card_images.get((card.suit, card.rank), self.back_image)
        self.animate_flip(card_label, front_img, 0)

    def animate_flip(self, card_label, front_img, step):
        steps = 10
        if step > steps:
            card_label.config(image=front_img)
            card_label.is_face_up = True
            self.animation_in_progress = False
            card_label.place(width=110, height=140)
            return
        if step <= steps//2:
            width = 110 - step*11
            if width <=0: width=1
            card_label.config(image=self.back_image)
        else:
            width = (step - steps//2)*11
            if width<=0: width=1
            card_label.config(image=front_img)
        card_label.place(width=width, height=140)
        self.after(50, lambda: self.animate_flip(card_label, front_img, step+1))

    # ---------- 红利结算（仅计算，不修改余额） ----------
    def calculate_bonus(self, hand):
        if self.game.bonus_bet == 0:
            return 0

        if not any(c.is_wild() for c in hand):
            rank_name, _, _, _, _ = best_hand_with_wildcards(hand)
            payout = BONUS_PAYOUT.get((rank_name, False), 0)
            return self.game.bonus_bet * (payout + 1) if payout else 0

        payout_a = 0
        if not any(c.is_joker for c in hand):
            hand_no_wild = []
            for c in hand:
                if c.rank == '2' and not c.is_joker:
                    hand_no_wild.append(Card(c.suit, '2'))
                else:
                    hand_no_wild.append(Card(c.suit, c.rank))
            rank_name_a, _, _ = evaluate_fixed_hand(hand_no_wild)
            payout_a = BONUS_PAYOUT.get((rank_name_a, False), 0)

        rank_name_b, _, _, _, _ = best_hand_with_wildcards(hand)
        payout_b = BONUS_PAYOUT.get((rank_name_b, True), 0)

        final_payout = payout_a if payout_a >= payout_b else payout_b
        if final_payout:
            return self.game.bonus_bet * (final_payout + 1)
        return 0

    # ---------- 决策动作 ----------
    def play_action(self):
        if hasattr(self, 'fold_button'): self.fold_button.config(state=tk.DISABLED)
        if hasattr(self, 'play_button'): self.play_button.config(state=tk.DISABLED)
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
        self.after(1000, self.show_showdown)

    def fold_action(self):
        if hasattr(self, 'fold_button'): self.fold_button.config(state=tk.DISABLED)
        if hasattr(self, 'play_button'): self.play_button.config(state=tk.DISABLED)
        self.game.folded = True
        self.status_label.config(text="您已弃牌 ~ 游戏结束")
        self.ante_var.set("0")
        self.blind_var.set("0")
        self.play_var.set("0")
        self.reveal_dealer_cards()

    # ---------- 摊牌 ----------
    def show_showdown(self):
        self.game.stage = "showdown"
        self.stage_label.config(text="摊牌")
        self.status_label.config(text="摊牌中...")
        self.reveal_dealer_cards()

    def reveal_dealer_cards(self):
        for i, lbl in enumerate(self.dealer_cards_frame.winfo_children()):
            if hasattr(lbl, "card") and not lbl.is_face_up:
                self.flip_card_animation(lbl)
                self.game.cards_revealed["dealer"][i] = True
        self.update_hand_labels()
        self.after(1000, self.start_both_sort_animation)

    def start_both_sort_animation(self):
        # 排序双方手牌
        player_eval = best_hand_with_wildcards(self.game.player_hand)
        dealer_eval = best_hand_with_wildcards(self.game.dealer_hand)
        sorted_p = sort_hand_for_display(self.game.player_hand, player_eval)
        sorted_d = sort_hand_for_display(self.game.dealer_hand, dealer_eval)
        self.game.player_hand = sorted_p
        self.game.dealer_hand = sorted_d

        p_labels = list(self.player_cards_frame.winfo_children())
        d_labels = list(self.dealer_cards_frame.winfo_children())
        p_target = {}
        for idx, card in enumerate(sorted_p):
            for l in p_labels:
                if hasattr(l, 'card') and l.card == card:
                    p_target[l] = idx*110
                    break
        d_target = {}
        for idx, card in enumerate(sorted_d):
            for l in d_labels:
                if hasattr(l, 'card') and l.card == card:
                    d_target[l] = idx*110
                    break

        all_labels = p_labels + d_labels
        start = {l: float(l.place_info()['x']) for l in all_labels if l.winfo_exists()}
        target = {**p_target, **d_target}
        steps = 20
        interval = 30
        data = []
        for l in start:
            dx = (target[l] - start[l]) / steps
            data.append((l, start[l], dx))
        def step(cnt):
            if cnt > steps:
                for l,_,_ in data:
                    if l.winfo_exists():
                        l.place(x=target[l])
                self.update_hand_labels()
                # 结算
                if self.game.folded:
                    self.settle_fold()
                else:
                    self.settle_showdown()
                return
            for l,start_x,dx in data:
                if l.winfo_exists():
                    l.place(x=start_x + dx*cnt)
            self.after(interval, lambda: step(cnt+1))
        step(1)

    # ---------- 结算 ----------
    def settle_fold(self):
        # 弃牌只可能赢得红利（双向坏注在弃牌时不支付）
        bonus_win = self.calculate_bonus(self.game.player_hand)
        self.balance += bonus_win
        self.update_balance()

        # 清空非红利下注显示
        self.ante_display.config(bg='white')
        self.blind_display.config(bg='white')
        self.play_display.config(bg='white')
        self.double_side_display.config(bg='white')
        self.ante_var.set("0")
        self.blind_var.set("0")
        self.play_var.set("0")
        self.double_side_var.set("0")

        # 显示红利
        if bonus_win > 0:
            self.bonus_display.config(bg='gold')
            self.bonus_var.set(str(int(bonus_win)))
        else:
            self.bonus_display.config(bg='white')
            self.bonus_var.set("0")

        self.last_win = bonus_win
        self.last_win_label.config(text=f"上局获胜: ${bonus_win:.2f}")
        self.show_restart_button()
        self._save_history({"fold": True, "total_winnings": bonus_win})

    def settle_showdown(self):
        winnings, details = self.calculate_winnings()          # 不含红利
        bonus_win = self.calculate_bonus(self.game.player_hand)  # 现在在此处计算红利
        total_winnings = winnings + bonus_win
        self.balance += total_winnings
        self.update_balance()

        # 更新下注显示（非红利部分）
        self.ante_var.set(str(int(details["ante"])))
        self.blind_var.set(str(int(details["blind"])))
        self.play_var.set(str(int(details["play"])))

        # 着色非红利下注
        for bet_type in ["ante", "blind", "play"]:
            widget = self.bet_widgets.get(bet_type)
            if not widget:
                continue
            if bet_type == "ante":
                bet_amt = self.game.ante
                win_amt = details["ante"]
            elif bet_type == "blind":
                bet_amt = self.game.blind
                win_amt = details["blind"]
            else:
                bet_amt = self.game.play_bet
                win_amt = details["play"]
            if win_amt > bet_amt:
                widget.config(bg='gold')
            elif win_amt == bet_amt and bet_amt > 0:
                widget.config(bg='light blue')
            else:
                widget.config(bg='white')

        # 双向坏注
        if details["double_side"] > 0:
            self.double_side_display.config(bg='gold')
            self.double_side_var.set(str(int(details["double_side"])))
        else:
            self.double_side_display.config(bg='white')
            self.double_side_var.set("0")

        # 红利显示
        if bonus_win > 0:
            self.bonus_display.config(bg='gold')
            self.bonus_var.set(str(int(bonus_win)))
        else:
            self.bonus_display.config(bg='white')
            self.bonus_var.set("0")

        # 比较牌型决定胜负
        comp = compare_hands_best(self.game.player_hand, self.game.dealer_hand)
        if comp > 0:
            msg = "本局您赢了"
            winner = "player"
        elif comp < 0:
            msg = "本局您输了"
            winner = "dealer"
        else:
            msg = "本局Push"
            winner = "push"

        self.status_label.config(text=msg)
        self.last_win = total_winnings
        self.last_win_label.config(text=f"上局获胜: ${total_winnings:.2f}")
        self.show_restart_button()
        self._save_history({"winner": winner, "winnings": total_winnings})

    def calculate_winnings(self):
        winnings = 0
        details = {"ante":0,"blind":0,"play":0,"double_side":0}
        comp = compare_hands_best(self.game.player_hand, self.game.dealer_hand)
        if comp > 0:
            # 玩家赢
            ante_result = self.game.ante * 2
            blind_payout = BLIND_PAYOUT.get(best_hand_with_wildcards(self.game.player_hand)[0], 0)
            blind_result = self.game.blind * (blind_payout + 1)
            play_result = self.game.play_bet * 2
        elif comp == 0:
            ante_result = self.game.ante
            blind_result = self.game.blind
            play_result = self.game.play_bet
        else:
            ante_result = 0
            blind_result = 0
            play_result = 0
        winnings += ante_result + blind_result + play_result
        details["ante"] = ante_result
        details["blind"] = blind_result
        details["play"] = play_result

        # 双向坏注
        player_eval = best_hand_with_wildcards(self.game.player_hand)
        dealer_eval = best_hand_with_wildcards(self.game.dealer_hand)
        player_rank_val = player_eval[1]
        dealer_rank_val = dealer_eval[1]
        double_win = self.calculate_double_side(player_rank_val, dealer_rank_val)
        winnings += double_win
        details["double_side"] = double_win

        return winnings, details

    def calculate_double_side(self, player_rank_val, dealer_rank_val):
        if self.game.double_side_bet == 0:
            return 0
        if player_rank_val < 3 or dealer_rank_val < 3:
            return 0
        lower_rank = min(player_rank_val, dealer_rank_val)
        lower_rank_name = HAND_RANK_NAMES[lower_rank]
        payout = DOUBLE_SIDE_PAYOUT.get(lower_rank_name, 0)
        if payout:
            return self.game.double_side_bet * (payout + 1)
        return 0

    # ---------- 历史记录 ----------
    def _save_history(self, result_info=None):
        try:
            deck = self.game.deck
            if deck is None: return
            save_dj_wild_history(deck, self.game.player_hand, self.game.dealer_hand, result_info)
        except Exception as e:
            print(f"保存历史记录出错: {e}")

    # ---------- 重置相关 ----------
    def reset_bets(self):
        self.ante_var.set("0")
        self.bonus_var.set("0")
        self.double_side_var.set("0")
        self.play_var.set("0")
        self.status_label.config(text="已重置所有下注金额")
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.ante_display.config(bg='#FFCDD2')
        self.bonus_display.config(bg='#FFCDD2')
        self.double_side_display.config(bg='#FFCDD2')
        self.after(500, lambda: self.ante_display.config(bg='white'))
        self.after(500, lambda: self.bonus_display.config(bg='white'))
        self.after(500, lambda: self.double_side_display.config(bg='white'))

    def apply_last_bet(self):
        if self.last_bet is None:
            return
        ante = self.last_bet['ante']
        bonus = self.last_bet['bonus']
        double_side = self.last_bet['double_side']
        play = self.last_bet['play']

        if self.high_bet_mode:
            max_ante, max_side = 50000, 12500
            min_ante = 100
        else:
            max_ante, max_side = 10000, 2500
            min_ante = 10
        if ante < min_ante: ante = min_ante
        if ante > max_ante: ante = max_ante
        if bonus > max_side: bonus = max_side
        if double_side > max_side: double_side = max_side

        self.ante_var.set(str(ante))
        self.bonus_var.set(str(bonus))
        self.double_side_var.set(str(double_side))
        self.play_var.set(str(play))
        self.status_label.config(text="已应用上次下注金额")
        self.ante_display.config(bg='#E8F5E9')
        self.bonus_display.config(bg='#E8F5E9')
        self.double_side_display.config(bg='#E8F5E9')
        self.after(800, lambda: self.ante_display.config(bg='white'))
        self.after(800, lambda: self.bonus_display.config(bg='white'))
        self.after(800, lambda: self.double_side_display.config(bg='white'))

    def show_restart_button(self):
        self.clear_btn_frame()
        restart_btn = tk.Button(
            self.btn_frame, text="再来一局",
            command=lambda: self._on_restart(restart_btn),
            font=('Arial',12,'bold'), bg='#2196F3', fg='white', width=10
        )
        restart_btn.pack()
        restart_btn.bind("<Button-3>", self.show_card_sequence)
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def _on_restart(self, btn):
        btn.config(state=tk.DISABLED)
        self.reset_game()

    def reset_game(self, auto_reset=False):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        if self.active_card_labels:
            self.disable_action_buttons()
            self.animate_collect_cards(auto_reset)
            return
        self._do_reset(auto_reset)

    def _do_reset(self, auto_reset=False):
        self._load_assets()
        self.game.reset_game()
        self.stage_label.config(text="翻牌前")
        self.player_label.config(text="玩家")
        self.dealer_label.config(text="庄家")
        self.ante_var.set("0")
        self.blind_var.set("0")
        self.bonus_var.set("0")
        self.double_side_var.set("0")
        self.play_var.set("0")
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.active_card_labels = []

        # 重新绑定事件
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.bonus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bonus"))
        self.bonus_display.bind("<Button-3>", lambda e: self.reset_single_bet("bonus", e))
        self.double_side_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("double_side"))
        self.double_side_display.bind("<Button-3>", lambda e: self.reset_single_bet("double_side", e))
        self.play_display.bind("<Button-1>", self.toggle_play_bet)
        for chip in self.chip_buttons:
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e,t=text: self.select_chip(t))

        self.clear_btn_frame()
        self.add_main_buttons()
        self.current_bet_label.config(text="本局下注: $0.00")
        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))
        else:
            self.status_label.config(text="设置下注金额并开始游戏")
        self.game_in_progress = False
        # 重置赔率表
        self.reset_odds_table()

    def animate_collect_cards(self, auto_reset):
        self.disable_action_buttons()
        self.animate_move_cards_out(auto_reset)

    def animate_move_cards_out(self, auto_reset):
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
            cx = lbl.winfo_x()
            tx, ty = lbl.target_pos
            dx = tx - cx
            if abs(dx) < 5:
                lbl.place(x=tx, y=ty)
                lbl.destroy()
                if lbl in self.active_card_labels:
                    self.active_card_labels.remove(lbl)
                continue
            new_x = cx + dx*0.2
            lbl.place(x=new_x)
            all_done = False
        if not all_done:
            self.after(20, lambda: self.animate_card_out_step(auto_reset))
        else:
            self._do_reset(auto_reset)

    def disable_action_buttons(self):
        self.buttons_disabled = True
        for widget in self.btn_frame.winfo_children():
            if isinstance(widget, tk.Button):
                widget.config(state=tk.DISABLED)

    def enable_action_buttons(self):
        self.buttons_disabled = False
        for widget in self.btn_frame.winfo_children():
            if isinstance(widget, tk.Button):
                widget.config(state=tk.NORMAL)

    # ---------- 显示牌序 ----------
    def show_card_sequence(self, event):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        if not hasattr(self.game, 'deck') or not self.game.deck:
            messagebox.showinfo("提示","没有牌序信息")
            return
        win = tk.Toplevel(self)
        win.title("本局牌序")
        win.geometry("730x750")
        win.resizable(0,0)
        win.configure(bg='#f0f0f0')
        cut_pos = self.game.deck.start_pos
        tk.Label(win, text=f"本局切牌位置: {cut_pos+1}", font=('Arial',14,'bold'), bg='#f0f0f0').pack(pady=10)
        main_frame = tk.Frame(win, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main_frame, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content_frame = tk.Frame(canvas, bg='#f0f0f0')
        canvas_frame = canvas.create_window((0,0), window=content_frame, anchor='nw')

        card_frame = tk.Frame(content_frame, bg='#f0f0f0')
        card_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        small_size = (60,90)
        small_images = {}
        for i, card in enumerate(self.game.deck.full_deck):
            key = (card.suit, card.rank)
            if key in self.original_images:
                orig = self.original_images[key]
                small = orig.resize(small_size, Image.LANCZOS)
                small_images[i] = ImageTk.PhotoImage(small)
            else:
                img = Image.new('RGB', small_size, 'blue')
                draw = ImageDraw.Draw(img)
                try:
                    font = ImageFont.truetype("arial.ttf", 12)
                except:
                    font = ImageFont.load_default()
                text = f"{card.rank}{card.suit}"
                tw, th = draw.textsize(text, font=font)
                draw.text(((small_size[0]-tw)//2, (small_size[1]-th)//2), text, fill="white", font=font)
                small_images[i] = ImageTk.PhotoImage(img)

        # 7行，前6行每行9张，第7行8张？但实际53张，可以按9列排列
        total = len(self.game.deck.full_deck)
        cols = 9
        rows = (total + cols - 1) // cols
        for row in range(rows):
            row_frame = tk.Frame(card_frame, bg='#f0f0f0')
            row_frame.pack(fill=tk.X)
            for col in range(cols):
                idx = row*cols + col
                if idx >= total: break
                container = tk.Frame(row_frame, bg='#f0f0f0')
                container.grid(row=0, column=col, padx=5)
                is_cut = idx == self.game.deck.start_pos
                bg = 'light blue' if is_cut else '#f0f0f0'
                lbl = tk.Label(container, image=small_images[idx], bg=bg, borderwidth=1, relief="solid")
                lbl.image = small_images[idx]
                lbl.pack()
                pos = tk.Label(container, text=str(idx+1), bg=bg, font=('Arial',9))
                pos.pack()
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

# =========================================================
# 主入口
# =========================================================
def main(initial_balance=10000, username="Guest"):
    app = DJWildGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")