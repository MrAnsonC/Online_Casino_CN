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
from collections import Counter
from itertools import combinations

# =========================================================
# 颜色常量（沿用 Mississippi 风格）
# =========================================================
ROOT_BG = "#1B3D31"
CYAN = "#007502"
TEXT = "#ffffff"
RED = "#ff2a23"
BLACK = "#050505"
DARK_BLUE = "#173f66"
GOLD = "#D4AF37"
PANEL_BG = "#F2E6C9"
HEADER_BG = "#D8B46A"
TITLE_FG = "#2A1B08"

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    10: '皇家同花顺', 9: '同花顺', 8: '四条', 7: '葫芦', 6: '同花',
    5: '顺子', 4: '三条', 3: '两对', 2: '对子(10-A)', 1: '对子(2-9)', 0: '高牌'
}

# 主注赔率（A注、B注、C注）
MAIN_BET_PAYOUT = {
    10: 500,   # 皇家同花顺 500:1
    9: 200,    # 同花顺 200:1
    8: 50,     # 四条 50:1
    7: 11,     # 葫芦 11:1
    6: 8,      # 同花 8:1
    5: 5,      # 顺子 5:1
    4: 3,      # 三条 3:1
    3: 2,      # 两对 2:1
    2: 1       # 对子10+ 1:1
}

# ======== 修改点：手牌加注（原公牌加注）赔率表 ========
# 基于玩家三张手牌：同花顺40:1，三条30:1，顺子6:1，同花3:1，对子1:1
TRIPS_PAYOUT = {
    9: 40,   # 同花顺
    4: 30,   # 三条
    5: 6,    # 顺子
    6: 3,    # 同花
    1: 1     # 对子
}

# 累进大奖赔率
JACKPOT_PAYOUT = {
    10: {"type": "percentage", "value": 1.0, "min": 0},   # 皇家同花顺 → 100% 奖池
    9: {"type": "percentage", "value": 0.1, "min": 0},    # 同花顺 → 10% 奖池
    8: {"type": "fixed", "value": 1250},                  # 四条 → $1,250
    7: {"type": "fixed", "value": 375},                   # 葫芦 → $375
    6: {"type": "fixed", "value": 250}                    # 同花 → $250
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
# Progressive 加载与保存（Key 改为 'Progressive_2.50'）
# =========================================================
def load_jackpot():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
    default_jackpot = 157301.26
    if not os.path.exists(path):
        return True, default_jackpot
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item.get('Games') == 'Progressive_2.50':
                    return False, float(item.get('jackpot', default_jackpot))
    except Exception:
        pass
    return True, default_jackpot

def save_jackpot(jackpot):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
    data = []
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = []
    found = False
    for item in data:
        if item.get('Games') == 'Progressive_2.50':
            item['jackpot'] = jackpot
            found = True
            break
    if not found:
        data.append({"Games": "Progressive_2.50", "jackpot": jackpot})
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# =========================================================
# 历史记录（Let_It_Ride.json）
# =========================================================
def letitride_log_path() -> str:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Let_It_Ride.json")

def save_letitride_history(deck, comm_cards, player_cards, win_amount, hand_rank, hand_name, result_status):
    """
    保存牌局历史到 Let_It_Ride.json
    history_record 包含 game, win, lose, pair_ten_or_better, pair_2_9 等统计
    history 每条记录包含 game_id, timestamp, deck_order, cut_position,
    comm_cards, player_cards, win_amount, result
    """
    log_path = letitride_log_path()
    data = {
        "history_record": {
            "game": 0,
            "win": 0,
            "lose": 0,
            "royal_flush": 0,
            "straight_flush": 0,
            "four_of_a_kind": 0,
            "full_house": 0,
            "flush": 0,
            "straight": 0,
            "three_of_a_kind": 0,
            "two_pair": 0,
            "pair_ten_or_better": 0,
            "pair_2_9": 0,
            "high_card": 0
        },
        "history": []
    }

    # 读取已有记录
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
                    stats = {"game": len(loaded), "win": 0, "lose": 0}
                    for rec in loaded:
                        if "win_amount" in rec:
                            if rec["win_amount"] > 0:
                                stats["win"] += 1
                            else:
                                stats["lose"] += 1
                    data["history_record"].update(stats)
        except Exception as e:
            print(f"读取历史文件出错: {e}")

    stats = data["history_record"]
    stats["game"] += 1
    if result_status == "Win":
        stats["win"] += 1
    else:
        stats["lose"] += 1

    # 牌型计数
    rank_to_key = {
        10: 'royal_flush',
        9: 'straight_flush',
        8: 'four_of_a_kind',
        7: 'full_house',
        6: 'flush',
        5: 'straight',
        4: 'three_of_a_kind',
        3: 'two_pair',
        2: 'pair_ten_or_better',
        1: 'pair_2_9',
        0: 'high_card'
    }
    key = rank_to_key.get(hand_rank, 'high_card')
    stats[key] = stats.get(key, 0) + 1

    # 生成 game_id
    max_id = 0
    for rec in data["history"]:
        if "game_id" in rec and isinstance(rec["game_id"], int):
            max_id = max(max_id, rec["game_id"])
    new_game_id = max_id + 1

    record = {
        "game_id": new_game_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "deck_order": [str(c) for c in deck.full_deck],
        "cut_position": deck.cut_position,
        "comm_cards": [str(c) for c in comm_cards],
        "player_cards": [str(c) for c in player_cards],
        "win_amount": win_amount,
        "result": result_status   # "Win" / "Lose"
    }
    data["history"].append(record)

    # 保留最新50局
    if len(data["history"]) > 50:
        data["history"] = data["history"][-50:]

    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# =========================================================
# 扑克牌类与牌堆
# =========================================================
class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.value = RANK_VALUES[rank]
    def __repr__(self):
        return f"{self.rank}{self.suit}"

class Deck:
    def __init__(self):
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
        shuffle_script = os.path.join(card_dir, 'shuffle.py')
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        try:
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
            self.full_deck = [
                Card(d["suit"], d["rank"])
                for d in shuffle_data["deck"]
            ]
            self.cut_position = shuffle_data["cut_position"]
        except Exception as e:
            print(f"Error calling shuffle.py: {e}. Using fallback shuffle.")
            self.full_deck = [Card(s, r) for s in SUITS for r in RANKS]
            self._secure_shuffle()
            self.cut_position = secrets.randbelow(52)
        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + i) % 52 for i in range(52)]
        self.pointer = 0
        self.card_sequence = [self.full_deck[i] for i in self.indexes]

    def _secure_shuffle(self):
        for i in range(len(self.full_deck) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            self.full_deck[i], self.full_deck[j] = self.full_deck[j], self.full_deck[i]

    def deal(self, n=1):
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt

# =========================================================
# 评估函数
# =========================================================
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
    if len(counts_list) > 1 and counts_list[0][1] == 3 and counts_list[1][1] >= 2:
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
        if pair >= 10:
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

# =========================================================
# Let It Ride 游戏逻辑类
# =========================================================
class LetItRideGame:
    def __init__(self):
        self.reset_game()
        self.progressive_amount = load_jackpot()[1]

    def reset_game(self):
        self.deck = Deck()
        self.community_cards = []
        self.player_hole = []
        self.bet_a = 0      # A注
        self.bet_b = 0      # B注
        self.bet_c = 0      # C注
        self.trips = 0      # 手牌加注（原公牌加注）
        self.participate_jackpot = False
        self.keep_bet_a = False
        self.keep_bet_b = False
        self.stage = "pre_flop"
        self.cards_revealed = {
            "player": [False, False, False],
            "community": [False, False]
        }
        self.cut_position = self.deck.start_pos
        self.card_sequence = self.deck.card_sequence

    def deal_initial(self):
        # 修改发牌顺序：先发2张公共牌，再发3张玩家牌
        self.community_cards = self.deck.deal(2)
        self.player_hole = self.deck.deal(3)

    def evaluate_hands(self):
        """评估玩家最终5张牌"""
        cards = self.player_hole + self.community_cards
        return evaluate_hand(cards)[0]

    def evaluate_current_hand(self, community_revealed_count):
        """评估当前可见牌（用于显示牌型）"""
        revealed_community = self.community_cards[:community_revealed_count]
        all_cards = self.player_hole + revealed_community
        if len(all_cards) < 3:
            return None
        best_eval, _ = find_best_5(all_cards)
        return best_eval

# =========================================================
# 主 GUI 类
# =========================================================
class LetItRideGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("任逍遥扑克")
        self.geometry("1150x750+50+10")
        self.resizable(0,0)
        self.configure(bg=ROOT_BG)

        self.username = username
        self.balance = initial_balance
        self.game = LetItRideGame()
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
        self.high_bet_mode = False
        self.game_in_progress = False

        # 下注变量
        self.bet_a_var = tk.StringVar(value="0")
        self.bet_b_var = tk.StringVar(value="0")
        self.bet_c_var = tk.StringVar(value="0")
        self.trips_var = tk.StringVar(value="0")
        self.jackpot_var = tk.IntVar(value=0)

        self.bet_widgets = {}
        self.win_details = {
            "bet_a": 0,
            "bet_b": 0,
            "bet_c": 0,
            "trips": 0,
            "jackpot": 0
        }
        self.last_jackpot_state = 0
        self.bet_refunded = {"a": False, "b": False}
        self.current_refund = 0.0

        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
        self.destroy()
        self.quit()

    # ---------- 加载扑克牌 ----------
    def _load_assets(self):
        card_size = (100, 140)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not hasattr(self, 'current_poker_folder'):
            self.current_poker_folder = random.choice(['Poker1', 'Poker2'])
        else:
            self.current_poker_folder = 'Poker2' if self.current_poker_folder == 'Poker1' else 'Poker1'
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', self.current_poker_folder)
        suit_mapping = {'♠':'Spade','♥':'Heart','♦':'Diamond','♣':'Club'}
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
        for suit in SUITS:
            for rank in RANKS:
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
                        text = f"{rank}{suit}"
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

    # ---------- 添加筹码到某注 ----------
    def add_chip_to_bet(self, bet_type):
        if not self.selected_chip:
            return
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K','')) * 1000
        else:
            chip_value = float(chip_text)

        limit_main = 50000 if self.high_bet_mode else 10000
        limit_trips = 12500 if self.high_bet_mode else 2500
        min_bet = 100 if self.high_bet_mode else 10

        if bet_type in ["bet_a", "bet_b", "bet_c"]:
            # 三个主注联动等额
            current = float(self.bet_a_var.get())
            if current >= limit_main:
                messagebox.showwarning("下注限制", "主注已满，不能再下注！")
                return
            new_amount = current + chip_value
            if new_amount > limit_main:
                new_amount = limit_main
                if current > 0:
                    messagebox.showwarning("下注限制", f"自动调整为上限 {limit_main}")
            new_amount = int(new_amount)
            self.bet_a_var.set(str(new_amount))
            self.bet_b_var.set(str(new_amount))
            self.bet_c_var.set(str(new_amount))
        elif bet_type == "trips":
            current = float(self.trips_var.get())
            if current >= limit_trips:
                messagebox.showwarning("下注限制", "手牌加注已满，不能再下注！")
                return
            new_amount = current + chip_value
            if new_amount > limit_trips:
                new_amount = limit_trips
                if current > 0:
                    messagebox.showwarning("下注限制", f"自动调整为上限 {limit_trips}")
            self.trips_var.set(str(int(new_amount)))

    def sync_bets(self):
        """A、B、C注联动等额（以A注为准）"""
        val = int(self.bet_a_var.get())
        self.bet_b_var.set(str(val))
        self.bet_c_var.set(str(val))

    # ---------- 重置单个下注（右键） ----------
    def reset_single_bet(self, bet_type, event):
        if bet_type in ["bet_a", "bet_b", "bet_c"]:
            self.bet_a_var.set("0")
            self.bet_b_var.set("0")
            self.bet_c_var.set("0")
        elif bet_type == "trips":
            self.trips_var.set("0")
        if bet_type in self.bet_widgets:
            widget = self.bet_widgets[bet_type]
            original_bg = widget.cget('bg')
            widget.config(bg='#FFCDD2')
            self.after(500, lambda: widget.config(bg=original_bg))

    # ---------- 清空按钮框架 ----------
    def clear_btn_frame(self):
        for widget in self.btn_frame.winfo_children():
            widget.destroy()

    # ---------- 主按钮 ----------
    def add_main_buttons(self):
        self.clear_btn_frame()
        self.reset_bets_button = tk.Button(
            self.btn_frame, text="重设金额", command=self.reset_bets,
            font=('Arial',12,'bold'), bg='#F44336', fg='white',
            relief=tk.RAISED, bd=2, cursor="hand2", width=10, height=1
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=5)

        self.repeat_bet_btn = tk.Button(
            self.btn_frame, text="重复上局下注", command=self.apply_last_bet,
            font=('Arial',12,'bold'), bg='#FFC107', fg='black',
            relief=tk.RAISED, bd=2, cursor="hand2", width=10, height=1,
            state=tk.NORMAL if self.last_bet is not None else tk.DISABLED
        )
        self.repeat_bet_btn.pack(side=tk.LEFT, padx=5)

        self.start_button = tk.Button(
            self.btn_frame, text="开始游戏", command=self.start_game,
            font=('Arial',12,'bold'), bg='#4CAF50', fg='white',
            relief=tk.RAISED, bd=2, cursor="hand2", width=10, height=1
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

        # 公共牌区域（2张）
        community_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        community_frame.place(x=230, y=60, width=270, height=230)
        self.community_label = tk.Label(community_frame, text="公共牌", font=('Arial',18), bg='#2a4a3c', fg='white')
        self.community_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.community_cards_frame = tk.Frame(community_frame, bg='#2a4a3c')
        self.community_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 中间提示
        info_label = tk.Label(
            table_canvas,
            text="打开玩家三张手牌时，可收回A注\n打开第一张公共牌时，可收回B注\n对子10或以上获胜",
            font=('Arial',22),
            bg=ROOT_BG,
            fg='#FFD700'
        )
        info_label.place(x=370, y=310, anchor='n')

        # 玩家区域（3张）
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=180, y=450, width=375, height=230)
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
        self.stage_label = tk.Label(body_info, text="准备下注", font=('Arial',16,'bold'),
                                    bg=PANEL_BG, fg='#A88100')
        self.stage_label.pack(side=tk.RIGHT)

        # 累进大奖卡片
        progressive_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        progressive_card.pack(fill=tk.X, pady=3)
        header_prog = tk.Frame(progressive_card, bg=HEADER_BG)
        header_prog.pack(fill=tk.X)
        tk.Label(header_prog, text="累进大奖", font=('Arial',13,'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_prog = tk.Frame(progressive_card, bg=PANEL_BG)
        body_prog.pack(fill=tk.X, padx=10, pady=8)
        self.progressive_amount_var = tk.StringVar()
        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")
        self.progressive_display = tk.Label(body_prog, textvariable=self.progressive_amount_var,
                                            font=('Arial',20,'bold'), bg=PANEL_BG, fg='#A88100')
        self.progressive_display.pack(anchor='center')

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

        # 筹码行
        chip_row = tk.Frame(body_combined, bg=PANEL_BG)
        chip_row.grid(row=0, column=0, columnspan=2, pady=(0,8), sticky='ew')
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

        # ---------- 下注行布局（按用户要求） ----------
        # 第一行：累进大奖 (左) | 手牌加注 (右)
        row1 = tk.Frame(body_combined, bg=PANEL_BG)
        row1.grid(row=1, column=0, columnspan=2, sticky='ew', pady=2)
        self.jackpot_check = tk.Checkbutton(
            row1, text="累进大奖 ($2.50)", variable=self.jackpot_var,
            font=('Arial',12,"bold"), bg=PANEL_BG, fg='black', selectcolor=PANEL_BG
        )
        self.jackpot_check.pack(side=tk.LEFT, padx=10)

        # ======== 修改点：标签改为“手牌加注” ========
        tk.Label(row1, text="手牌加注:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=(45,5))
        self.trips_display = tk.Label(row1, textvariable=self.trips_var, font=('Arial',12),
                                      bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.trips_display.pack(side=tk.LEFT, padx=5)
        self.trips_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("trips"))
        self.trips_display.bind("<Button-3>", lambda e: self.reset_single_bet("trips", e))
        self.bet_widgets["trips"] = self.trips_display

        # 第二行：纯文本 "A注 = B注 = C注"
        row2 = tk.Frame(body_combined, bg=PANEL_BG)
        row2.grid(row=2, column=0, columnspan=2, sticky='ew', pady=2)
        label_text = tk.Label(row2, text="A注       =       B注       =       C注", font=('Arial',14,'bold'),
                              bg=PANEL_BG, fg='black')
        label_text.pack(anchor='center')

        # 第三行：三个下注格，中间用等号分隔
        row3 = tk.Frame(body_combined, bg=PANEL_BG)
        row3.grid(row=3, column=0, columnspan=2, sticky='ew', padx=28, pady=2)

        self.bet_a_display = tk.Label(row3, textvariable=self.bet_a_var, font=('Arial',12),
                                      bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.bet_a_display.pack(side=tk.LEFT, padx=5)
        self.bet_a_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bet_a"))
        self.bet_a_display.bind("<Button-3>", lambda e: self.reset_single_bet("bet_a", e))
        self.bet_widgets["bet_a"] = self.bet_a_display

        tk.Label(row3, text="=", font=('Arial',16,'bold'), bg=PANEL_BG, fg='black').pack(side=tk.LEFT, padx=5)

        self.bet_b_display = tk.Label(row3, textvariable=self.bet_b_var, font=('Arial',12),
                                      bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.bet_b_display.pack(side=tk.LEFT, padx=5)
        self.bet_b_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bet_b"))
        self.bet_b_display.bind("<Button-3>", lambda e: self.reset_single_bet("bet_b", e))
        self.bet_widgets["bet_b"] = self.bet_b_display

        tk.Label(row3, text="=", font=('Arial',16,'bold'), bg=PANEL_BG, fg='black').pack(side=tk.LEFT, padx=5)

        self.bet_c_display = tk.Label(row3, textvariable=self.bet_c_var, font=('Arial',12),
                                      bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.bet_c_display.pack(side=tk.LEFT, padx=5)
        self.bet_c_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bet_c"))
        self.bet_c_display.bind("<Button-3>", lambda e: self.reset_single_bet("bet_c", e))
        self.bet_widgets["bet_c"] = self.bet_c_display

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
            bg=PANEL_BG, fg='#2A1B08', height=1, width=30
        )
        self.status_label.pack(fill=tk.X, pady=4)

        self.btn_frame = tk.Frame(body_action, bg=PANEL_BG)
        self.btn_frame.pack(fill=tk.X, pady=5)
        self.add_main_buttons()

        # ---------- 底部信息（分三行） ----------
        info_bottom_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        info_bottom_card.pack(fill=tk.X, pady=3)
        body_bottom = tk.Frame(info_bottom_card, bg=PANEL_BG)
        body_bottom.pack(fill=tk.X, padx=10, pady=8)

        # 第一行：本局下注
        self.current_bet_label = tk.Label(
            body_bottom, text="本局下注: $0.00", font=('Arial',12), bg=PANEL_BG, fg='black'
        )
        self.current_bet_label.pack(anchor='w')

        # 第二行：上局获胜
        self.refund_label = tk.Label(
            body_bottom, text="本局退还: $0.00", font=('Arial',12), bg=PANEL_BG, fg='#007502'
        )
        self.refund_label.pack(anchor='w')

        # 第三行：本局退还（左）+ ℹ️按钮（右）
        row_bottom = tk.Frame(body_bottom, bg=PANEL_BG)
        row_bottom.pack(fill=tk.X)
        self.last_win_label = tk.Label(
            row_bottom, text="上局获胜: $0.00", font=('Arial',12), bg=PANEL_BG, fg='#007502' 
        )
        self.last_win_label.pack(side=tk.LEFT)
        self.info_button = tk.Button(
            row_bottom, text="ℹ️", command=self.show_game_instructions,
            bg='#4B8BBE', fg='white', font=('Arial',12), width=2, relief=tk.FLAT
        )
        self.info_button.pack(side=tk.RIGHT)

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

    # ---------- 游戏规则 ----------
    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("任逍遥扑克 游戏规则")
        win.geometry("850x750")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main_frame, bg='#F0F0F0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content_frame = tk.Frame(canvas, bg='#F0F0F0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')

        rules_text = """
        任逍遥扑克（Let It Ride）游戏规则

        1. 下注：
        - A注、B注、C注为等额主注（联动调整）
        - 手牌加注（原公牌加注）为可选边注，基于玩家三张底牌牌型支付
        - 累进大奖为可选 $2.50 下注，基于最终五张牌型赢取奖金

        2. 游戏流程：
        a. 设置下注，点击「开始游戏」→ 发牌（玩家3张 + 公共牌2张面朝下）
        b. 翻开玩家牌，玩家决定是否保留 A 注
            - 收回：退还 A 注下注
            - 保留：继续
        c. 翻开第一张公共牌，玩家决定是否保留 B 注
            - 收回：退还 B 注下注
            - 保留：继续
        d. 翻开第二张公共牌，C 注始终保留，摊牌结算

        3. 结算：
        - 主注（A+B+C）根据最终5张牌型按赔率表支付
        - 手牌加注根据玩家3张底牌牌型支付
        - 累进大奖根据最终5张牌型支付（见赔率表）

        4. 赔率表：
        """
        tk.Label(content_frame, text=rules_text, font=('微软雅黑', 11),
                bg='#F0F0F0', justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X, padx=10, pady=5)

        # 赔率表格
        table_frame = tk.Frame(content_frame, bg='#F0F0F0')
        table_frame.pack(fill=tk.X, padx=20, pady=5)
        # ======== 修改点：列头“公牌加注”改为“手牌加注” ========
        headers = ["牌型", "主注赔率", "手牌加注", "累进大奖"]
        header_bg = '#4B8BBE'
        header_fg = 'white'
        for col, h in enumerate(headers):
            lbl = tk.Label(table_frame, text=h, font=('微软雅黑', 10, 'bold'),
                        bg=header_bg, fg=header_fg, padx=8, pady=5, anchor='center')
            lbl.grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # ======== 修改点：更新手牌加注列赔率 ========
        payout_data = [
            ("皇家同花顺", "500:1", "-", "100%"),
            ("同花顺", "200:1", "40:1", "10%"),
            ("四条", "50:1", "-", "$1,250"),
            ("葫芦", "11:1", "-", "$375"),
            ("同花", "8:1", "3:1", "$250"),
            ("顺子", "5:1", "6:1", "-"),
            ("三条", "3:1", "30:1", "-"),
            ("两对", "2:1", "-", "-"),
            ("对子10+", "1:1", "1:1", "-"),
            ("对子2-9", "-", "1:1", "-"),   # 主注对子10+，手牌加注对子统一1:1
            ("其他", "-", "-", "-")
        ]

        for row_idx, row_data in enumerate(payout_data, start=1):
            bg_color = '#E0E0E0' if row_idx % 2 == 0 else '#F0F0F0'
            for col_idx, cell_text in enumerate(row_data):
                lbl = tk.Label(table_frame, text=cell_text, font=('微软雅黑', 10),
                            bg=bg_color, padx=8, pady=5, anchor='center')
                lbl.grid(row=row_idx, column=col_idx, sticky='nsew', padx=1, pady=1)

        for col in range(len(headers)):
            table_frame.columnconfigure(col, weight=1)

        notes = """
        注:
        • 主注 = A注 + B注 + C注，A注和B注可在相应阶段收回。
        • 手牌加注仅基于玩家3张底牌。
        • 累进大奖奖池金额显示在界面上方。
        """
        tk.Label(content_frame, text=notes, font=('微软雅黑', 10),
                bg='#F0F0F0', justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X, padx=10, pady=5)

        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=10)
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    # ---------- 更新余额 ----------
    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:,.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)

    # ---------- 更新手牌标签 ----------
    def update_hand_labels(self):
        community_revealed = sum(self.game.cards_revealed["community"])
        all_cards = self.game.player_hole + self.game.community_cards[:community_revealed]
        if len(all_cards) < 3:
            hand_name = ""
        else:
            if len(all_cards) < 5:
                values = [c.value for c in all_cards]
                counts = Counter(values)
                if 3 in counts.values():
                    hand_name = "三条"
                elif list(counts.values()).count(2) >= 2:
                    hand_name = "两对"
                elif 2 in counts.values():
                    # 找出对子的点数（可能多个对子，取最大值）
                    pair_values = [v for v, cnt in counts.items() if cnt == 2]
                    max_pair = max(pair_values)
                    if max_pair >= 10:
                        hand_name = "对子(10-A)"
                    else:
                        hand_name = "对子(2-9)"
                else:
                    hand_name = "高牌"
            else:
                rank = evaluate_hand(all_cards)[0]
                hand_name = HAND_RANK_NAMES.get(rank, "")
        self.player_label.config(text=f"玩家 - {hand_name}" if hand_name else "玩家")

    # ---------- 开始游戏 ----------
    def start_game(self):
        try:
            bet_a = int(self.bet_a_var.get())
            bet_b = int(self.bet_b_var.get())
            bet_c = int(self.bet_c_var.get())
            trips = int(self.trips_var.get())
            jackpot = self.jackpot_var.get()
            self.last_jackpot_state = jackpot
            jackpot_cost = 2.50 if jackpot else 0

            min_bet = 100 if self.high_bet_mode else 10
            max_main = 50000 if self.high_bet_mode else 10000
            max_trips = 12500 if self.high_bet_mode else 2500

            # 同步（以A注为准）
            if bet_a != bet_b or bet_a != bet_c:
                bet_a = max(bet_a, bet_b, bet_c)
                self.bet_a_var.set(str(bet_a))
                self.sync_bets()

            if bet_a < min_bet:
                messagebox.showerror("错误", f"每注至少需要 {min_bet} 块")
                return
            if bet_a > max_main:
                bet_a = max_main
                self.bet_a_var.set(str(bet_a))
                self.sync_bets()
                messagebox.showwarning("下注限制", f"主注上限为 {max_main}，已自动调整")
            if trips > max_trips:
                trips = max_trips
                self.trips_var.set(str(trips))

            total_bet = bet_a + bet_b + bet_c + trips + jackpot_cost
            if total_bet > self.balance:
                messagebox.showerror("错误", f"余额不足！需要 ${total_bet:.2f}")
                return

            # 扣除下注
            self.balance -= total_bet
            self.game_in_progress = True
            self.update_balance()

            self.last_bet = {
                'bet_a': bet_a,
                'bet_b': bet_b,
                'bet_c': bet_c,
                'trips': trips,
                'jackpot': jackpot
            }
            if self.repeat_bet_btn:
                self.repeat_bet_btn.config(state=tk.NORMAL)

            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            self.last_win_label.config(text="上局获胜: $0.00")
            self.refund_label.config(text="本局退还: $0.00")
            self.current_refund = 0.0
            self.bet_refunded = {"a": False, "b": False}

            self.game.reset_game()
            self.game.bet_a = bet_a
            self.game.bet_b = bet_b
            self.game.bet_c = bet_c
            self.game.trips = trips
            self.game.participate_jackpot = bool(jackpot)
            self.game.deal_initial()

            # 清空牌面
            for widget in self.community_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.player_cards_frame.winfo_children():
                widget.destroy()

            self.animation_queue = []
            self.animation_in_progress = False
            self.active_card_labels = []
            self.card_positions = {}
            # 2张公共牌
            for i in range(2):
                card_id = f"community_{i}"
                self.card_positions[card_id] = {"current": (50,50), "target": (i*110,0)}
                self.animation_queue.append(card_id)
            for i in range(3):
                card_id = f"player_{i}"
                self.card_positions[card_id] = {"current": (50,50), "target": (i*110,0)}
                self.animation_queue.append(card_id)

            # 禁用下注控件
            self.bet_a_display.unbind("<Button-1>")
            self.bet_b_display.unbind("<Button-1>")
            self.bet_c_display.unbind("<Button-1>")
            self.trips_display.unbind("<Button-1>")
            self.jackpot_check.config(state=tk.DISABLED)
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")

            self.clear_btn_frame()
            self.stage_label.config(text="初始决策")
            self.status_label.config(text="手牌已翻开，决定保留或收回 A 注")

            self.animate_deal()

        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")

    # ---------- 动画 ----------
    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            self.after(500, self.reveal_player_cards)
            return
        self.animation_in_progress = True
        card_id = self.animation_queue.pop(0)
        if card_id.startswith("community"):
            frame = self.community_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.community_cards[idx] if idx < len(self.game.community_cards) else None
        else:
            frame = self.player_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.player_hole[idx] if idx < len(self.game.player_hole) else None

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

    def reveal_player_cards(self):
        for i, lbl in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(lbl, "card") and not lbl.is_face_up:
                self.flip_card_animation(lbl)
                self.game.cards_revealed["player"][i] = True
        self.update_hand_labels()
        self.after(1000, self.show_initial_buttons)

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

    # ---------- 初始决策按钮 ----------
    def show_initial_buttons(self):
        self.game.stage = "initial"
        self.stage_label.config(text="初始决策")
        self.status_label.config(text="保留或收回 A 注")
        self.clear_btn_frame()
        btn_frame = tk.Frame(self.btn_frame, bg=PANEL_BG)
        btn_frame.pack()
        tk.Button(btn_frame, text="保留 A 注", command=lambda: self.play_action(True, "a"),
                  font=('Arial',12,'bold'), bg='#4CAF50', fg='white', width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="收回 A 注", command=lambda: self.play_action(False, "a"),
                  font=('Arial',12,'bold'), bg='#F44336', fg='white', width=10).pack(side=tk.LEFT, padx=5)

    # ---------- 翻牌圈按钮 ----------
    def show_flop_buttons(self):
        self.game.stage = "flop"
        self.stage_label.config(text="翻牌圈")
        self.status_label.config(text="保留或收回 B 注")
        self.clear_btn_frame()
        btn_frame = tk.Frame(self.btn_frame, bg=PANEL_BG)
        btn_frame.pack()
        tk.Button(btn_frame, text="保留 B 注", command=lambda: self.play_action(True, "b"),
                  font=('Arial',12,'bold'), bg='#4CAF50', fg='white', width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="收回 B 注", command=lambda: self.play_action(False, "b"),
                  font=('Arial',12,'bold'), bg='#F44336', fg='white', width=10).pack(side=tk.LEFT, padx=5)

    # ---------- 执行决策 ----------
    def play_action(self, keep, bet_type):
        self.clear_btn_frame()

        if bet_type == "a":
            self.game.keep_bet_a = keep
            if not keep:
                refund = self.game.bet_a
                self.balance += refund
                self.current_refund += refund
                self.update_balance()
                self.refund_label.config(text=f"本局退还: ${self.current_refund:.2f}")
                self.bet_refunded["a"] = True
                self.bet_a_display.config(text="退还", bg='light blue')
                self.bet_a_display.config(textvariable=None)
            else:
                self.status_label.config(text="已保留 A 注")
            # 翻开第一张公共牌
            self.reveal_community_card(0)
            self.after(1500, self.show_flop_buttons)

        elif bet_type == "b":
            self.game.keep_bet_b = keep
            if not keep:
                refund = self.game.bet_b
                self.balance += refund
                self.current_refund += refund
                self.update_balance()
                self.refund_label.config(text=f"本局退还: ${self.current_refund:.2f}")
                self.bet_refunded["b"] = True
                self.bet_b_display.config(text="退还", bg='light blue')
                self.bet_b_display.config(textvariable=None)
            else:
                self.status_label.config(text="已保留 B 注")
            # 翻开第二张公共牌并结算
            self.reveal_community_card(1)
            self.after(1500, self.show_showdown)

    # ---------- 翻开公共牌 ----------
    def reveal_community_card(self, index):
        for i, lbl in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(lbl, "card") and not lbl.is_face_up and i == index:
                self.flip_card_animation(lbl)
                self.game.cards_revealed["community"][i] = True
                break
        self.update_hand_labels()

    # ---------- 摊牌结算 ----------
    def show_showdown(self):
        # 确保所有公共牌翻开
        for i, lbl in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(lbl, "card") and not lbl.is_face_up:
                self.flip_card_animation(lbl)
                self.game.cards_revealed["community"][i] = True

        self.update_hand_labels()

        final_rank = self.game.evaluate_hands()
        winnings, details = self.calculate_winnings(final_rank)
        self.last_win = winnings

        self.balance += winnings
        self.update_balance()

        # 更新下注显示（保留已退还的视觉状态）
        if not self.bet_refunded.get("a", False):
            self.bet_a_var.set(str(int(details["bet_a"])))
        if not self.bet_refunded.get("b", False):
            self.bet_b_var.set(str(int(details["bet_b"])))
        self.bet_c_var.set(str(int(details["bet_c"])))
        self.trips_var.set(str(int(details["trips"])))

        # 高亮赢注
        for bet_type, widget in self.bet_widgets.items():
            if bet_type in ["bet_a","bet_b","bet_c"]:
                if self.bet_refunded.get(bet_type[-1], False):
                    widget.config(bg='light blue')  # 已退还
                else:
                    amt = getattr(self.game, f"bet_{bet_type[-1]}", 0)
                    if details[bet_type] > amt:
                        widget.config(bg='gold')
                    elif details[bet_type] == amt and amt > 0:
                        widget.config(bg='light blue')
                    else:
                        widget.config(bg='white')
            elif bet_type == "trips":
                if details["trips"] > 0:
                    widget.config(bg='gold')
                else:
                    widget.config(bg='white')

        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")
        self.status_label.config(text="游戏结束。")
        self.stage_label.config(text="结束")

        # 判断结果状态（以C注是否盈利为准）
        result_status = "Win" if details["bet_c"] > self.game.bet_c else "Lose"
        hand_name = HAND_RANK_NAMES.get(final_rank, "高牌")
        # 保存历史记录
        save_letitride_history(
            deck=self.game.deck,
            comm_cards=self.game.community_cards,
            player_cards=self.game.player_hole,
            win_amount=winnings,
            hand_rank=final_rank,
            hand_name=hand_name,
            result_status=result_status
        )

        # 更新累进大奖
        self.update_jackpot()

        # 显示再来一局
        self.clear_btn_frame()
        restart_btn = tk.Button(
            self.btn_frame, text="再来一局",
            command=self.reset_game,
            font=('Arial',12,'bold'), bg='#2196F3', fg='white', width=10
        )
        restart_btn.pack()
        restart_btn.bind("<Button-3>", self.show_card_sequence)

        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
        self.game_in_progress = False

    # ---------- 计算赢利 ----------
    def calculate_winnings(self, final_rank):
        """
        计算本局赢利
        final_rank: 最终5张牌的牌型等级（0~10）
        返回 (总赢利, 各注明细)
        """
        details = {k: 0 for k in self.win_details}
        total = 0

        # 主注（A、B、C）—— 保留的 A/B 与 C 同赔率
        for bet_key in ["bet_a", "bet_b", "bet_c"]:
            bet = getattr(self.game, bet_key)
            if bet_key == "bet_c":
                kept = True
            else:
                kept = getattr(self.game, f"keep_bet_{bet_key[-1]}", False)

            if kept:
                if final_rank in MAIN_BET_PAYOUT:
                    payout = MAIN_BET_PAYOUT[final_rank]
                    details[bet_key] = bet * (1 + payout)   # 本金 + 赢利
                else:
                    details[bet_key] = 0                    # 牌型不中，输掉本金
            else:
                details[bet_key] = 0                        # 已收回，结算不计
            total += details[bet_key]

        # ========== 手牌加注（Trips）==========
        if self.game.trips > 0:
            trip_rank = self.evaluate_3card(self.game.player_hole)
            if trip_rank in TRIPS_PAYOUT:
                payout = TRIPS_PAYOUT[trip_rank]
                details["trips"] = self.game.trips * (1 + payout)
            else:
                details["trips"] = 0
            total += details["trips"]

        # ========== 累进大奖 ==========
        if self.game.participate_jackpot:
            jackpot_win = self.calculate_jackpot(final_rank)
            details["jackpot"] = jackpot_win
            total += jackpot_win

        return total, details

    # ======== 修改点：评估三张手牌，增加对子识别 ========
    def evaluate_3card(self, cards):
        values = [c.value for c in cards]
        suits = [c.suit for c in cards]
        flush = len(set(suits)) == 1
        vals = sorted(values)
        # 检测顺子
        if vals == [2,3,14] or (vals[0]+1 == vals[1] and vals[1]+1 == vals[2]):
            straight = True
        else:
            straight = False
        # 三条
        if vals[0]==vals[1]==vals[2]:
            return 4  # 三条
        # 同花顺
        if flush and straight:
            return 9  # 同花顺
        # 顺子
        if straight:
            return 5
        # 同花
        if flush:
            return 6
        # 对子
        if vals[0]==vals[1] or vals[1]==vals[2]:
            return 1  # 对子
        else:
            return -1

    def calculate_jackpot(self, rank):
        if rank not in JACKPOT_PAYOUT:
            return 0
        rule = JACKPOT_PAYOUT[rank]
        if rule["type"] == "percentage":
            amount = self.game.progressive_amount * rule["value"]
        else:
            amount = rule["value"]
        # 扣除奖池
        self.game.progressive_amount -= amount
        if self.game.progressive_amount < 271288.59:
            self.game.progressive_amount = 271288.59
        save_jackpot(self.game.progressive_amount)
        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")
        messagebox.showinfo("恭喜获得累进大奖！", f"您赢得了 ${amount:,.2f} 奖金！")
        return amount

    def update_jackpot(self):
        # 计算实际未收回的下注额（A注和B注根据是否保留决定）
        actual_bet_a = self.game.bet_a if self.game.keep_bet_a else 0
        actual_bet_b = self.game.bet_b if self.game.keep_bet_b else 0
        actual_bet_c = self.game.bet_c  # C注从不收回
        actual_trips = self.game.trips  # 手牌加注从不收回
        total_bet = actual_bet_a + actual_bet_b + actual_bet_c + actual_trips
        jackpot_cost = 2.50 if self.game.participate_jackpot else 0
        increment = total_bet * 0.001 + jackpot_cost * 0.95
        self.game.progressive_amount += increment
        if self.game.progressive_amount < 271288.59:
            self.game.progressive_amount = 271288.59
        save_jackpot(self.game.progressive_amount)
        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")

    # ---------- 重置 ----------
    def reset_bets(self):
        self.bet_a_var.set("0")
        self.bet_b_var.set("0")
        self.bet_c_var.set("0")
        self.trips_var.set("0")
        self.status_label.config(text="已重置所有下注金额")
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.bet_a_display.config(bg='#FFCDD2')
        self.bet_b_display.config(bg='#FFCDD2')
        self.bet_c_display.config(bg='#FFCDD2')
        self.trips_display.config(bg='#FFCDD2')
        self.after(500, lambda: [w.config(bg='white') for w in self.bet_widgets.values()])

    def apply_last_bet(self):
        if self.last_bet is None:
            return
        bet_a = self.last_bet['bet_a']
        bet_b = self.last_bet['bet_b']
        bet_c = self.last_bet['bet_c']
        trips = self.last_bet['trips']
        jack = self.last_bet['jackpot']
        max_main = 50000 if self.high_bet_mode else 10000
        max_trips = 12500 if self.high_bet_mode else 2500
        min_bet = 100 if self.high_bet_mode else 10
        if bet_a < min_bet: bet_a = min_bet
        if bet_a > max_main: bet_a = max_main
        if trips > max_trips: trips = max_trips
        self.bet_a_var.set(str(bet_a))
        self.sync_bets()
        self.trips_var.set(str(trips))
        self.jackpot_var.set(jack)
        self.status_label.config(text="已应用上次下注金额")
        for w in [self.bet_a_display, self.bet_b_display, self.bet_c_display, self.trips_display]:
            w.config(bg='#E8F5E9')
        self.after(800, lambda: [w.config(bg='white') for w in self.bet_widgets.values()])

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
        self.stage_label.config(text="准备下注")
        self.player_label.config(text="玩家")
        self.community_label.config(text="公共牌")
        self.bet_a_var.set("0")
        self.bet_b_var.set("0")
        self.bet_c_var.set("0")
        self.trips_var.set("0")
        self.jackpot_var.set(self.last_jackpot_state)
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.active_card_labels = []

        # 恢复绑定
        self.bet_a_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bet_a"))
        self.bet_a_display.bind("<Button-3>", lambda e: self.reset_single_bet("bet_a", e))
        self.bet_b_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bet_b"))
        self.bet_b_display.bind("<Button-3>", lambda e: self.reset_single_bet("bet_b", e))
        self.bet_c_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bet_c"))
        self.bet_c_display.bind("<Button-3>", lambda e: self.reset_single_bet("bet_c", e))
        self.trips_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("trips"))
        self.trips_display.bind("<Button-3>", lambda e: self.reset_single_bet("trips", e))
        self.jackpot_check.config(state=tk.NORMAL)
        for chip in self.chip_buttons:
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e,t=text: self.select_chip(t))

        self.clear_btn_frame()
        self.add_main_buttons()
        self.current_bet_label.config(text="本局下注: $0.00")
        self.refund_label.config(text="本局退还: $0.00")
        self.last_win_label.config(text="上局获胜: $0.00")
        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))
        else:
            self.status_label.config(text="设置下注金额并开始游戏")
        self.game_in_progress = False

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

        for row in range(6):
            row_frame = tk.Frame(card_frame, bg='#f0f0f0')
            row_frame.pack(fill=tk.X)
            cards_in_row = 9 if row<5 else 7
            for col in range(cards_in_row):
                idx = row*9+col
                if idx>=52: break
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
    app = LetItRideGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")