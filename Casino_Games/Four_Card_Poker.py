import sys as _account_sys
from pathlib import Path as _AccountPath
_account_root = next((p for p in (_AccountPath(__file__).resolve().parent, *_AccountPath(__file__).resolve().parents) if (p / "A_Tools" / "Account" / "secure_json.py").is_file()), None)
if _account_root is None:
    raise RuntimeError("Cannot locate encrypted account storage")
if str(_account_root) not in _account_sys.path:
    _account_sys.path.insert(0, str(_account_root))
from A_Tools.Account import install_secure_json as _install_secure_json
_install_secure_json()
del _install_secure_json, _account_root, _AccountPath, _account_sys

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
import math
import hashlib
import time
import secrets
import subprocess, sys
from collections import Counter
from itertools import combinations

# =========================================================
# 颜色常量（保持 Caribbean 风格，但下注区沿用原始风格）
# =========================================================
ROOT_BG = "#1B3D31"
PANEL_BG = "#F2E6C9"
HEADER_BG = "#D8B46A"
TITLE_FG = "#2A1B08"
GOLD = "#D4AF37"

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    7: '四条', 
    6: '同花顺', 
    5: '三条', 
    4: '同花', 
    3: '顺子', 
    2: '两对', 
    1: '对子', 
    0: '高牌'
}

ANTE_BONUS_PAYOUT = {7: 25, 6: 20, 5: 2}
ACE_PLUS_PAYOUT = {7: 51, 6: 41, 5: 9, 4: 6, 3: 5, 2: 4, 1: 2}
SUPER_BONUS_PAYOUT = {7: {'A': 200, 'other': 30}, 6: 15, 5: 2, 4: 1.5, 3: 1}
QUEENS_PLUS_PAYOUT = {7: 50, 6: 30, 5: 9, 4: 4, 3: 3, 2: 2, 1: 1}

# =========================================================
# 文件操作（用户余额）
# =========================================================
def get_data_file_path():
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'A_Tools/Account/saving_data.json')

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
# 牌局历史日志（四张牌扑克）
# =========================================================
def four_card_log_path() -> str:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Four_Card_Poker.json")

def save_four_card_history(deck, player_cards, dealer_cards, game_mode, result_info=None):
    log_path = four_card_log_path()
    data = {
        "history_record": {"player_win": 0, "dealer_win": 0, "push": 0, "fold": 0, "game": 0},
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
                    data["history"] = loaded
                    stats = {"player_win": 0, "dealer_win": 0, "fold": 0, "push": 0, "game": len(loaded)}
                    for rec in loaded:
                        if "result" in rec and "winner" in rec["result"]:
                            winner = rec["result"]["winner"]
                            if winner == "player": stats["player_win"] += 1
                            elif winner == "dealer": stats["dealer_win"] += 1
                            elif winner == "fold": stats["fold"] += 1
                            elif winner == "push": stats["push"] += 1
                    data["history_record"] = stats
        except Exception as e:
            print(f"读取历史文件出错: {e}")

    max_id = max((rec["game_id"] for rec in data["history"] if "game_id" in rec), default=0)
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
            if winner == "player": stats["player_win"] += 1
            elif winner == "dealer": stats["dealer_win"] += 1
            elif winner == "push": stats["push"] += 1

    record = {
        "game_id": new_game_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "game_mode": game_mode,
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
            self.full_deck = [Card(d["suit"], d["rank"]) for d in shuffle_data["deck"]]
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
# 四张牌评估与比较
# =========================================================
def evaluate_four_card_hand(cards):
    if not cards or len(cards) < 4:
        return (0, [])
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    is_flush = len(set(suits)) == 1
    values_asc = sorted([c.value for c in cards])
    is_straight = False
    straight_values = None
    if len(set(values_asc)) == 4:
        if values_asc[-1] - values_asc[0] == 3:
            is_straight = True
            straight_values = sorted(values, reverse=True)
        elif values_asc == [2,3,4,14]:
            is_straight = True
            straight_values = [4,3,2,1]
    if is_straight and is_flush:
        return (6, straight_values)
    value_count = {}
    for v in values:
        value_count[v] = value_count.get(v, 0) + 1
    sorted_counts = sorted(value_count.items(), key=lambda x: (x[1], x[0]), reverse=True)
    sorted_values = [item[0] for item in sorted_counts]
    if sorted_counts[0][1] == 4: return (7, sorted_values)
    if sorted_counts[0][1] == 3: return (5, sorted_values)
    if is_flush: return (4, values)
    if is_straight: return (3, straight_values)
    if sorted_counts[0][1] == 2 and sorted_counts[1][1] == 2: return (2, sorted_values)
    if sorted_counts[0][1] == 2: return (1, sorted_values)
    return (0, values)

def compare_hands(hand1, hand2):
    rank1, values1 = evaluate_four_card_hand(hand1)
    rank2, values2 = evaluate_four_card_hand(hand2)
    if rank1 > rank2: return 1
    if rank1 < rank2: return -1
    for v1, v2 in zip(values1, values2):
        if v1 > v2: return 1
        if v1 < v2: return -1
    v1_full = sorted([c.value for c in hand1], reverse=True)
    v2_full = sorted([c.value for c in hand2], reverse=True)
    for v1, v2 in zip(v1_full, v2_full):
        if v1 > v2: return 1
        if v1 < v2: return -1
    return 0

def get_best_four_card_hand(cards):
    best_hand = None
    best_rank = -1
    best_values = []
    for combo in combinations(cards, 4):
        rank, values = evaluate_four_card_hand(list(combo))
        if rank > best_rank or (rank == best_rank and values > best_values):
            best_hand = list(combo)
            best_rank = rank
            best_values = values
    return best_hand, best_rank, best_values

def sort_hand_by_rank(hand):
    if not hand or len(hand) < 4:
        return hand
    rank, _ = evaluate_four_card_hand(hand)
    if rank in [0, 4]:
        return sorted(hand, key=lambda c: c.value, reverse=True)
    elif rank == 1:
        counts = {}
        for card in hand:
            counts[card.value] = counts.get(card.value, 0) + 1
        pair_value = None
        singles = []
        for value, count in counts.items():
            if count == 2:
                pair_value = value
            else:
                singles.append(value)
        sorted_hand = []
        for card in hand:
            if card.value == pair_value:
                sorted_hand.append(card)
        for value in sorted(singles, reverse=True):
            for card in hand:
                if card.value == value and card not in sorted_hand:
                    sorted_hand.append(card)
                    break
        return sorted_hand
    elif rank == 2:
        counts = {}
        for card in hand:
            counts[card.value] = counts.get(card.value, 0) + 1
        pair_values = [v for v,c in counts.items() if c == 2]
        pair_values_sorted = sorted(pair_values, reverse=True)
        sorted_hand = []
        for value in pair_values_sorted:
            for card in hand:
                if card.value == value and card not in sorted_hand:
                    sorted_hand.append(card)
        for value in pair_values_sorted:
            for card in hand:
                if card.value == value and card not in sorted_hand:
                    sorted_hand.append(card)
        return sorted_hand
    elif rank == 5:
        counts = {}
        for card in hand:
            counts[card.value] = counts.get(card.value, 0) + 1
        three_value = None
        single_value = None
        for value, count in counts.items():
            if count == 3:
                three_value = value
            else:
                single_value = value
        sorted_hand = []
        for card in hand:
            if card.value == three_value:
                sorted_hand.append(card)
        for card in hand:
            if card.value == single_value and card not in sorted_hand:
                sorted_hand.append(card)
                break
        return sorted_hand
    elif rank in [3, 6]:
        sorted_by_value = sorted(hand, key=lambda c: c.value)
        if sorted_by_value[0].value == 2 and sorted_by_value[-1].value == 14:
            aces = [c for c in sorted_by_value if c.value == 14]
            non_aces = [c for c in sorted_by_value if c.value != 14]
            return aces + non_aces
        else:
            return sorted_by_value
    elif rank == 7:
        counts = {}
        for card in hand:
            counts[card.value] = counts.get(card.value, 0) + 1
        four_value = None
        for value, count in counts.items():
            if count == 4:
                four_value = value
                break
        sorted_hand = []
        for card in hand:
            if card.value == four_value:
                sorted_hand.append(card)
        return sorted_hand
    else:
        return sorted(hand, key=lambda c: c.value, reverse=True)

def dealer_qualifies(dealer_hand):
    if not dealer_hand or len(dealer_hand) < 5:
        return False
    best_hand, rank, _ = get_best_four_card_hand(dealer_hand)
    if rank >= 1:
        return True
    if rank == 0:
        max_card = max(card.value for card in best_hand)
        return max_card >= 13
    return False

# =========================================================
# 游戏逻辑类
# =========================================================
class FourCardGame:
    def __init__(self, game_mode="basic"):
        self.game_mode = game_mode
        self.reset_game()
    
    def reset_game(self):
        self.deck = Deck()
        self.player_hand = []
        self.dealer_hand = []
        self.player_best_hand = []
        self.dealer_best_hand = []
        self.player_discarded = []
        self.dealer_discarded = []
        self.ante = 0
        self.ace_plus_bet = 0
        self.super_bonus_bet = 0
        self.queens_plus_bet = 0
        self.play_bet = 0
        self.stage = "pre_flop"
        self.folded = False
        self.cards_revealed = {
            "player": [False]*5,
            "dealer": [False]*(6 if self.game_mode == "basic" else 5)
        }
    
    def deal_initial(self):
        if self.game_mode == "basic":
            self.player_hand = self.deck.deal(5)
            self.dealer_hand = self.deck.deal(6)
        else:
            self.player_hand = self.deck.deal(5)
            self.dealer_hand = self.deck.deal(5)
    
    def select_best_hands(self):
        self.player_best_hand, _, _ = get_best_four_card_hand(self.player_hand)
        self.player_discarded = [c for c in self.player_hand if c not in self.player_best_hand]
        self.dealer_best_hand, _, _ = get_best_four_card_hand(self.dealer_hand)
        self.dealer_discarded = [c for c in self.dealer_hand if c not in self.dealer_best_hand]
        return 0, 0

# =========================================================
# 主GUI类
# =========================================================
class FourCardPokerGUI(tk.Frame):
    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG)
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.configure(bg=ROOT_BG)

        self.username = username
        self.balance = initial_balance
        self.game_mode = "basic"
        self.game = FourCardGame(self.game_mode)
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
        self.auto_reset_timer = None
        self.buttons_disabled = False
        self.win_details = {"ante":0,"play":0,"ante_bonus":0,"ace_plus":0,"super_bonus":0,"queens_plus":0}
        self.bet_widgets = {}
        self.ante_var = tk.StringVar(value="0")
        self.ace_plus_var = tk.StringVar(value="0")
        self.super_bonus_var = tk.StringVar(value="0")
        self.queens_plus_var = tk.StringVar(value="0")
        self.play_var = tk.StringVar(value="0")
        
        # 使用 trace_add 替代弃用的 trace
        self.ante_var.trace_add('write', self.on_ante_changed)
        self.last_game_bet = None
        self.high_bet_mode = False
        self.game_in_progress = False

        self._load_assets()
        self._create_widgets()

    def on_close(self):
        timer = getattr(self, "auto_reset_timer", None)
        if timer:
            try:
                self.after_cancel(timer)
            except tk.TclError:
                pass
        try:
            update_balance_in_json(self.username, self.balance)
        except Exception:
            pass
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))
        if callable(self.on_back):
            self.on_back(float(self.balance))


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
        self.card_images = {}
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

    # ---------- 添加筹码 ----------
    def add_chip_to_bet(self, bet_type):
        if not self.selected_chip:
            return
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K','')) * 1000
        else:
            chip_value = float(chip_text)

        ante_max = 50000 if self.high_bet_mode else 10000
        side_max = 12500 if self.high_bet_mode else 2500
        limits = {"ante": ante_max, "ace_plus": side_max, "super_bonus": side_max, "queens_plus": side_max}
        if bet_type in limits:
            var = self.__getattribute__(f"{bet_type}_var")
            current = float(var.get())
            limit = limits[bet_type]
            if current >= limit:
                names = {"ante":"底注","ace_plus":"Ace+","super_bonus":"超级红利","queens_plus":"Queens+"}
                messagebox.showwarning("下注限制", f"{names[bet_type]}已满，不能再下注！")
                return
            new_amount = current + chip_value
            if new_amount > limit:
                new_amount = limit
                if current > 0:
                    names = {"ante":"底注","ace_plus":"Ace+","super_bonus":"超级红利","queens_plus":"Queens+"}
                    messagebox.showwarning("下注限制", f"{names[bet_type]}已达上限，自动调整为 {int(new_amount)}")
            var.set(str(int(new_amount)))

    # ---------- 重置单个下注（右键） ----------
    def reset_single_bet(self, bet_type, event):
        if bet_type == "ante":
            self.ante_var.set("0")
        elif bet_type == "ace_plus":
            self.ace_plus_var.set("0")
        elif bet_type == "queens_plus":
            self.queens_plus_var.set("0")
        # 注意：super_bonus 不单独重置，由 ante 变化自动同步
        # 但为安全，若点击 super_bonus 的右键，也重置 ante
        if bet_type == "super_bonus":
            self.ante_var.set("0")
        # 获取当前点击的控件，闪一下
        widget = event.widget if event else None
        if widget and widget.winfo_exists():
            original_bg = widget.cget('bg')
            widget.config(bg='#FFCDD2')
            self.after(500, lambda: widget.config(bg=original_bg) if widget.winfo_exists() else None)

    # ---------- 按钮框架管理 ----------
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
            state=tk.NORMAL if self.last_game_bet is not None else tk.DISABLED
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

        # 庄家区域 - 根据游戏模式调整宽度和位置
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        self.dealer_frame = dealer_frame  # 保存引用
        if self.game_mode == "basic":
            dealer_frame.place(x=10, y=50, width=700, height=230)
        else:
            dealer_frame.place(x=60, y=50, width=600, height=230)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial',18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 中间提示
        self.ante_info_label = tk.Label(
            table_canvas,
            text="庄家无条件合格 平局玩家获胜\n玩家和庄家比较最佳4张牌",
            font=('Arial',22),
            bg=ROOT_BG,
            fg='#FFD700'
        )
        self.ante_info_label.update_idletasks()
        label_width = self.ante_info_label.winfo_width()
        table_canvas.update_idletasks()
        canvas_width = table_canvas.winfo_width()
        center_x = (canvas_width - label_width)//2
        self.ante_info_label.place(x=center_x+360, y=310, anchor='n')

        # 玩家区域
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=60, y=430, width=600, height=230)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial',18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # ---------- 右侧控制面板 ----------
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

        # ---------- 游戏模式切换（重新设计） ----------
        mode_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        mode_card.pack(fill=tk.X, pady=3)
        header_mode = tk.Frame(mode_card, bg=HEADER_BG)
        header_mode.pack(fill=tk.X)
        tk.Label(header_mode, text="游戏模式", font=('Arial',13,'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_mode = tk.Frame(mode_card, bg=PANEL_BG)
        body_mode.pack(fill=tk.X, padx=10, pady=8)

        # 基本版按钮
        self.basic_mode_btn = tk.Button(
            body_mode,
            text="基本版",
            command=lambda: self.set_game_mode("basic"),
            font=('Arial',12,'bold'),
            bg='#4CAF50' if self.game_mode == 'basic' else '#cccccc',
            fg='white' if self.game_mode == 'basic' else 'black',
            relief=tk.RAISED, bd=2, cursor="hand2",
            width=8
        )
        self.basic_mode_btn.pack(side=tk.LEFT, padx=5, pady=5, expand=True, fill=tk.X)

        # 疯狂版按钮
        self.crazy_mode_btn = tk.Button(
            body_mode,
            text="疯狂版",
            command=lambda: self.set_game_mode("crazy"),
            font=('Arial',12,'bold'),
            bg='#4CAF50' if self.game_mode == 'crazy' else '#cccccc',
            fg='white' if self.game_mode == 'crazy' else 'black',
            relief=tk.RAISED, bd=2, cursor="hand2",
            width=8
        )
        self.crazy_mode_btn.pack(side=tk.LEFT, padx=5, pady=5, expand=True, fill=tk.X)
        
        # 限红信息（点击切换高额模式）
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

        # ---------- 下注区域（采用新布局，合并筹码行） ----------
        bet_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        bet_card.pack(fill=tk.X, pady=3)
        header_bet = tk.Frame(bet_card, bg=HEADER_BG)
        header_bet.pack(fill=tk.X)
        tk.Label(header_bet, text="筹码与下注", font=('Arial',13,'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        bet_frame = tk.Frame(bet_card, bg=PANEL_BG)
        bet_frame.pack(fill=tk.X, padx=10, pady=8)

        # 筹码行（放在下注区内部）
        chip_row = tk.Frame(bet_frame, bg=PANEL_BG)
        chip_row.pack(fill=tk.X, pady=5, padx=5)
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

        # 基本版界面
        self.basic_frame = tk.Frame(bet_frame, bg=PANEL_BG)
        # 第一行：庄家6张牌提示
        self.basic_dealer_info_frame = tk.Frame(self.basic_frame, bg=PANEL_BG)
        basic_dealer_info_label = tk.Label(self.basic_dealer_info_frame, text="庄家发6张手牌", 
                                         font=('Arial', 14), bg=PANEL_BG, fg='black')
        basic_dealer_info_label.pack() 
        self.basic_dealer_info_frame.pack(fill=tk.X, pady=2)

        # 第二行：Ante 和 Ace+
        self.basic_bet_row_frame = tk.Frame(self.basic_frame, bg=PANEL_BG)
        # Ante
        ante_frame = tk.Frame(self.basic_bet_row_frame, bg=PANEL_BG)
        ante_label = tk.Label(ante_frame, text="  底注:", font=('Arial', 14), bg=PANEL_BG, fg='black')
        ante_label.pack(side=tk.LEFT)
        self.ante_display = tk.Label(ante_frame, textvariable=self.ante_var, font=('Arial', 14), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.bet_widgets["ante_basic"] = self.ante_display
        ante_frame.pack(side=tk.LEFT, padx=20)

        # Ace+
        ace_plus_frame = tk.Frame(self.basic_bet_row_frame, bg=PANEL_BG)
        ace_plus_label = tk.Label(ace_plus_frame, text="A对子+:", font=('Arial', 14), bg=PANEL_BG, fg='black')
        ace_plus_label.pack(side=tk.LEFT)
        self.ace_plus_display = tk.Label(ace_plus_frame, textvariable=self.ace_plus_var, font=('Arial', 14), 
                                        bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.ace_plus_display.pack(side=tk.LEFT, padx=5)
        self.ace_plus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ace_plus"))
        self.ace_plus_display.bind("<Button-3>", lambda e: self.reset_single_bet("ace_plus", e))
        self.bet_widgets["ace_plus_basic"] = self.ace_plus_display
        ace_plus_frame.pack(side=tk.LEFT, padx=20)

        self.basic_bet_row_frame.pack(fill=tk.X, pady=2)

        # 第三行：加注
        self.basic_play_frame = tk.Frame(self.basic_frame, bg=PANEL_BG)
        play_label = tk.Label(self.basic_play_frame, text="      加注:", font=('Arial', 14), bg=PANEL_BG, fg='black')
        play_label.pack(side=tk.LEFT)
        self.basic_play_display = tk.Label(self.basic_play_frame, textvariable=self.play_var, font=('Arial', 14), 
                                         bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.basic_play_display.pack(side=tk.LEFT, padx=5)
        # 加注不绑定点击（由游戏逻辑控制）
        self.bet_widgets["play_basic"] = self.basic_play_display
        self.basic_play_frame.pack(fill=tk.X, pady=2)

        # 疯狂版界面
        self.crazy_frame = tk.Frame(bet_frame, bg=PANEL_BG)
        # 第一行：Q对子+ 和 庄家5张牌提示
        self.crazy_qplus_frame = tk.Frame(self.crazy_frame, bg=PANEL_BG)
        queens_plus_label = tk.Label(self.crazy_qplus_frame, text=" Q对子+:", font=('Arial', 14), bg=PANEL_BG, fg='black')
        queens_plus_label.pack(side=tk.LEFT)
        self.queens_plus_display = tk.Label(self.crazy_qplus_frame, textvariable=self.queens_plus_var, font=('Arial', 14), 
                                          bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.queens_plus_display.pack(side=tk.LEFT, padx=5)
        self.queens_plus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("queens_plus"))
        self.queens_plus_display.bind("<Button-3>", lambda e: self.reset_single_bet("queens_plus", e))
        self.bet_widgets["queens_plus_crazy"] = self.queens_plus_display

        crazy_dealer_info_label = tk.Label(self.crazy_qplus_frame, text="庄家发5张手牌", 
                                         font=('Arial', 14), bg=PANEL_BG, fg='black')
        crazy_dealer_info_label.pack(side=tk.LEFT, padx=5)
        self.crazy_qplus_frame.pack(fill=tk.X, pady=2)

        # 第二行：底注 = 超级红利
        self.crazy_ante_super_frame = tk.Frame(self.crazy_frame, bg=PANEL_BG)
        ante_label2 = tk.Label(self.crazy_ante_super_frame, text="      底注:", font=('Arial', 14), bg=PANEL_BG, fg='black')
        ante_label2.pack(side=tk.LEFT)
        self.ante_display2 = tk.Label(self.crazy_ante_super_frame, textvariable=self.ante_var, font=('Arial', 14), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.ante_display2.pack(side=tk.LEFT, padx=5)
        self.ante_display2.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display2.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.bet_widgets["ante_crazy"] = self.ante_display2

        equals_label = tk.Label(self.crazy_ante_super_frame, text=" = ", font=('Arial', 14), bg=PANEL_BG, fg='black')
        equals_label.pack(side=tk.LEFT, padx=5)

        self.super_bonus_display = tk.Label(self.crazy_ante_super_frame, textvariable=self.super_bonus_var, font=('Arial', 14), 
                                          bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.super_bonus_display.pack(side=tk.LEFT, padx=5)
        # 超级红利点击时也添加底注（方便操作）
        self.super_bonus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        # 右键重置底注
        self.super_bonus_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.bet_widgets["super_bonus_crazy"] = self.super_bonus_display

        super_bonus_label = tk.Label(self.crazy_ante_super_frame, text=":超级红利", font=('Arial', 14), bg=PANEL_BG, fg='black')
        super_bonus_label.pack(side=tk.LEFT)
        self.crazy_ante_super_frame.pack(fill=tk.X, pady=2)

        # 第三行：加注
        self.crazy_play_frame = tk.Frame(self.crazy_frame, bg=PANEL_BG)
        crazy_play_label = tk.Label(self.crazy_play_frame, text="      加注:", font=('Arial', 14), bg=PANEL_BG, fg='black')
        crazy_play_label.pack(side=tk.LEFT)
        self.crazy_play_display = tk.Label(self.crazy_play_frame, textvariable=self.play_var, font=('Arial', 14), 
                                         bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.crazy_play_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["play_crazy"] = self.crazy_play_display
        self.crazy_play_frame.pack(fill=tk.X, pady=2)

        # 初始显示基本版，隐藏疯狂版
        self.basic_frame.pack(fill=tk.X, pady=2)
        self.crazy_frame.pack_forget()

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

        # 底部信息
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

    def update_bet_display(self):
        """根据当前游戏模式显示基本版或疯狂版下注界面"""
        if self.game_mode == "basic":
            self.basic_frame.pack(fill=tk.X, pady=2)
            self.crazy_frame.pack_forget()
        else:
            self.crazy_frame.pack(fill=tk.X, pady=2)
            self.basic_frame.pack_forget()

    def on_ante_changed(self, *args):
        """当底注变化时，若为疯狂版则自动更新超级红利为相同值"""
        if self.game_mode == "crazy":
            try:
                ante = int(self.ante_var.get())
            except ValueError:
                ante = 0
            # 只有当超级红利与底注不同时才更新，避免循环
            current_super = self.super_bonus_var.get()
            if current_super != str(ante):
                self.super_bonus_var.set(str(ante))

    # ---------- 游戏模式切换 ----------
    def set_game_mode(self, mode):
        """切换到指定游戏模式（basic 或 crazy）"""
        if self.game_in_progress:
            return
        if mode == self.game_mode:
            return  # 已经是该模式，无需切换

        # 更新模式
        self.game_mode = mode
        self.game = FourCardGame(self.game_mode)

        # 更新按钮高亮状态
        self.basic_mode_btn.config(
            bg='#4CAF50' if mode == 'basic' else '#cccccc',
            fg='white' if mode == 'basic' else 'black'
        )
        self.crazy_mode_btn.config(
            bg='#4CAF50' if mode == 'crazy' else '#cccccc',
            fg='white' if mode == 'crazy' else 'black'
        )

        # 更新下注界面
        self.update_bet_display()
        self.reset_bets()
        if self.game_mode == "crazy":
            try:
                ante = int(self.ante_var.get())
            except:
                ante = 0
            self.super_bonus_var.set(str(ante))

        # 调整庄家牌桌区域尺寸和位置
        if self.game_mode == "basic":
            self.dealer_frame.place(x=10, y=50, width=700, height=230)
            self.ante_info_label.config(text="庄家无条件合格 平局玩家获胜\n玩家和庄家比较最佳4张牌")
        else:
            self.dealer_frame.place(x=60, y=50, width=600, height=230)
            self.ante_info_label.config(text="庄家需至少高牌K或以上才合格 不合格退还底注\n玩家和庄家比较最佳4张牌")

        # 清空牌桌
        for widget in self.dealer_cards_frame.winfo_children():
            widget.destroy()
        for widget in self.player_cards_frame.winfo_children():
            widget.destroy()

        self.dealer_label.config(text="庄家")
        self.player_label.config(text="玩家")
        self.stage_label.config(text="翻牌前")
        self.status_label.config(text=f"已切换到{'基本版' if self.game_mode=='basic' else '疯狂版'}")

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
        for i,(text,bg_color,fg_color) in enumerate(chip_configs):
            cell = tk.Frame(self.chip_container, bg=PANEL_BG)
            cell.grid(row=0, column=i, padx=2, pady=2, sticky='nsew')
            chip_canvas = tk.Canvas(cell, width=50, height=50, bg=PANEL_BG, highlightthickness=0)
            chip_canvas.pack(anchor='center')
            chip_canvas.create_oval(2,2,49,49, fill=bg_color, outline='black')
            chip_canvas.create_text(25.5,25.5, text=text, fill=fg_color, font=('Arial',12,'bold'))
            chip_canvas.bind("<Button-1>", lambda e,t=text: self.select_chip(t))
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text
        self.select_chip(default)

    # ---------- 预下注切换（点击加注） ----------
    def toggle_play_bet(self, event=None):
        # 原版中点击加注只是显示当前值，这里不实现预下注，保持为空
        pass

    # ---------- 游戏规则说明 ----------
    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("四张牌扑克游戏规则")
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

        if self.game_mode == "basic":
            rules_text = """
            四张牌扑克 基本版 规则

            1. 下注:
               - 底注（必须）
               - A对子+（可选）

            2. 流程:
               - 发牌：玩家5张，庄家6张
               - 玩家选择最佳4张，弃掉1张
               - 决策：弃牌 或 下注1/2/3倍
               - 庄家开牌（无需资格）
               - 比较最佳4张牌

            3. 结算:
               - 底注/加注：玩家赢或平局得1:1，输则失去
               - Ante Bonus（无论输赢）：
                 三条 2:1，同花顺 20:1，四条 25:1
               - A对子+：见赔率表
            """
        else:
            rules_text = """
            四张牌扑克 疯狂版 规则

            1. 下注:
               - 底注（必须）
               - 超级红利 = 底注（自动）
               - Q对子+（可选）

            2. 流程:
               - 发牌：玩家5张，庄家5张
               - 玩家选择最佳4张，弃掉1张
               - 决策：弃牌 或 下注1/2/3倍
               - 庄家需有K或以上才合格
               - 比较最佳4张牌

            3. 结算:
               - 底注：庄家不合格则退还，否则按比较结果
               - 加注：按比较结果
               - 超级红利：与加注绑定，按牌型赔付（见赔率表）
               - Q对子+：独立结算，见赔率表
            """
        tk.Label(content_frame, text=rules_text, font=('微软雅黑',11),
                 bg='#F0F0F0', justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X, padx=10, pady=5)

        tk.Label(content_frame, text="赔付表汇总", font=('微软雅黑',14,'bold'),
                 bg='#F0F0F0').pack(fill=tk.X, padx=10, pady=(20,10), anchor='center')

        payout_frame = tk.Frame(content_frame, bg='#F0F0F0')
        payout_frame.pack(fill=tk.X, padx=20, pady=5)

        if self.game_mode == "basic":
            headers = ["牌型","底注额外红利","A对子+"]
            data = [
                ("四条","25:1","50:1"),
                ("同花顺","20:1","40:1"),
                ("三条","2:1","8:1"),
                ("同花","-","5:1"),
                ("顺子","-","4:1"),
                ("两对","-","3:1"),
                ("对子A","-","1:1")
            ]
        else:
            headers = ["牌型","超级红利","Q对子+"]
            data = [
                ("四条A","200:1","50:1"),
                ("四条2-K","30:1","50:1"),
                ("同花顺","15:1","30:1"),
                ("三条","2:1","9:1"),
                ("同花","1.5:1","4:1"),
                ("顺子","1:1","3:1"),
                ("两对","-","2:1"),
                ("Queens对子或以上","-","1:1")
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
        注:
        * 庄家需有高牌K或以上才合格（疯狂版）
        * 下注倍数可选择1/2/3倍
        * 高额模式下所有下注上限×5
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
        if self.game.player_best_hand and len(self.game.player_best_hand)==4:
            eval_ = evaluate_four_card_hand(self.game.player_best_hand)
            name = HAND_RANK_NAMES.get(eval_[0], "")
            self.player_label.config(text=f"玩家 - {name}" if name else "玩家")
        if (self.game.stage=="showdown" or self.game.folded) and self.game.dealer_best_hand and len(self.game.dealer_best_hand)==4:
            eval_ = evaluate_four_card_hand(self.game.dealer_best_hand)
            name = HAND_RANK_NAMES.get(eval_[0], "")
            self.dealer_label.config(text=f"庄家 - {name}" if name else "庄家")

    # ---------- 重置下注 ----------
    def reset_bets(self):
        self.ante_var.set("0")
        self.play_var.set("0")
        self.ace_plus_var.set("0")
        self.super_bonus_var.set("0")
        self.queens_plus_var.set("0")
        self.status_label.config(text="已重置所有下注金额")
        # 遍历所有 bet_widgets 进行闪烁
        for widget in self.bet_widgets.values():
            if widget and widget.winfo_exists():
                original_bg = widget.cget('bg')
                widget.config(bg='#FFCDD2')
                # 使用闭包捕获 widget 和 original_bg
                def restore(w=widget, bg=original_bg):
                    if w and w.winfo_exists():
                        w.config(bg=bg)
                self.after(500, restore)

    # ---------- 重复上局下注 ----------
    def apply_last_bet(self):
        if self.last_game_bet is None:
            return
        ante = self.last_game_bet.get('ante', 0)
        ace = self.last_game_bet.get('ace_plus', 0)
        super_ = self.last_game_bet.get('super_bonus', 0)
        queens = self.last_game_bet.get('queens_plus', 0)
        if self.high_bet_mode:
            ante_max, side_max = 50000, 12500
            min_ante = 100
        else:
            ante_max, side_max = 10000, 2500
            min_ante = 10
        ante = min(max(ante, min_ante), ante_max)
        ace = min(ace, side_max)
        super_ = min(super_, side_max)
        queens = min(queens, side_max)
        self.ante_var.set(str(ante))
        self.ace_plus_var.set(str(ace))
        self.super_bonus_var.set(str(super_))
        self.queens_plus_var.set(str(queens))
        if self.game_mode == "crazy":
            self.super_bonus_var.set(str(ante))
        self.status_label.config(text="已应用上次下注金额")
        # 闪烁底注标签（只闪烁一个，比如ante_display）
        if self.ante_display and self.ante_display.winfo_exists():
            self.ante_display.config(bg='#E8F5E9')
            self.after(800, lambda: self.ante_display.config(bg='white') if self.ante_display.winfo_exists() else None)

    # ---------- 开始游戏 ----------
    def start_game(self):
        try:
            ante = int(self.ante_var.get())
            ace_plus = int(self.ace_plus_var.get())
            super_bonus = int(self.super_bonus_var.get())
            queens_plus = int(self.queens_plus_var.get())

            if self.high_bet_mode:
                ante_max, side_max, min_ante = 50000, 12500, 100
            else:
                ante_max, side_max, min_ante = 10000, 2500, 10

            if ante < min_ante:
                messagebox.showerror("错误", f"底注至少需要{min_ante}块")
                return
            if ante > ante_max:
                ante = ante_max
                self.ante_var.set(str(ante_max))
                messagebox.showwarning("下注限制", f"底注上限为{ante_max}，已自动调整")
            if self.game_mode == "basic":
                if ace_plus > side_max:
                    ace_plus = side_max
                    self.ace_plus_var.set(str(side_max))
                    messagebox.showwarning("下注限制", f"A对子+上限为{side_max}，已自动调整")
            else:
                if super_bonus != ante:
                    super_bonus = ante
                    self.super_bonus_var.set(str(ante))
                    messagebox.showwarning("下注限制", "超级红利必须等于底注金额，已自动调整")
                if queens_plus > side_max:
                    queens_plus = side_max
                    self.queens_plus_var.set(str(side_max))
                    messagebox.showwarning("下注限制", f"Q对子+上限为{side_max}，已自动调整")

            total_bet = ante + (ace_plus if self.game_mode=="basic" else super_bonus + queens_plus)
            if (total_bet + ante) > self.balance:
                messagebox.showerror("错误", "余额不足以支付所有下注！")
                return
            self.balance -= total_bet
            self.game_in_progress = True
            self.update_balance()

            self.last_game_bet = {
                'ante': ante,
                'ace_plus': ace_plus if self.game_mode=="basic" else 0,
                'super_bonus': super_bonus if self.game_mode=="crazy" else 0,
                'queens_plus': queens_plus if self.game_mode=="crazy" else 0
            }
            if self.repeat_bet_btn:
                self.repeat_bet_btn.config(state=tk.NORMAL)

            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            self.last_win_label.config(text="上局获胜: $0.00")

            self.game.reset_game()
            self.game.deal_initial()
            self.game.ante = ante
            if self.game_mode == "basic":
                self.game.ace_plus_bet = ace_plus
            else:
                self.game.super_bonus_bet = super_bonus
                self.game.queens_plus_bet = queens_plus
            self.game.play_bet = 0

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
            dealer_count = 6 if self.game_mode=="basic" else 5
            for i in range(dealer_count):
                card_id = f"dealer_{i}"
                self.card_positions[card_id] = {"current": (50,50), "target": (i*110,0)}
                self.animation_queue.append(card_id)

            # 禁用下注标签的点击事件（只禁用当前可见的）
            for widget in self.bet_widgets.values():
                if widget and widget.winfo_exists():
                    widget.unbind("<Button-1>")
                    widget.unbind("<Button-3>")

            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")

            self.clear_btn_frame()

            action_frame = tk.Frame(self.btn_frame, bg=PANEL_BG)
            action_frame.pack(fill=tk.X, expand=True)  # 填满宽度

            # 创建四个按钮，统一宽度和字体
            btn_kw = {
                'font': ('Arial', 12, 'bold'),
                'state': tk.DISABLED,
                'relief': tk.RAISED,
                'bd': 2,
                'width': 10,   # 统一宽度，保证平均
            }

            self.fold_button = tk.Button(
                action_frame, text="弃牌", command=self.fold_action,
                bg='#F44336', fg='white', **btn_kw
            )
            self.play_1x_button = tk.Button(
                action_frame, text="下注1倍", command=lambda: self.play_action(1),
                bg='#4CAF50', fg='white', **btn_kw
            )
            self.play_2x_button = tk.Button(
                action_frame, text="下注2倍", command=lambda: self.play_action(2),
                bg='#2196F3', fg='white', **btn_kw
            )
            self.play_3x_button = tk.Button(
                action_frame, text="下注3倍", command=lambda: self.play_action(3),
                bg='#FF9800', fg='white', **btn_kw
            )

            # 用 grid 均匀分布
            action_frame.columnconfigure(0, weight=1)
            action_frame.columnconfigure(1, weight=1)
            action_frame.columnconfigure(2, weight=1)
            action_frame.columnconfigure(3, weight=1)

            self.fold_button.grid(row=0, column=0, padx=3, sticky='ew')
            self.play_1x_button.grid(row=0, column=1, padx=3, sticky='ew')
            self.play_2x_button.grid(row=0, column=2, padx=3, sticky='ew')
            self.play_3x_button.grid(row=0, column=3, padx=3, sticky='ew')

            self.stage_label.config(text="派牌")
            self.status_label.config(text="派牌中...")
            self.animate_deal()

        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")

    # ---------- 动画发牌 ----------
    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            self.after(500, self.reveal_initial_cards)
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

    # ---------- 翻开初始牌 ----------
    def reveal_initial_cards(self):
        for i, lbl in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(lbl, "card") and not lbl.is_face_up:
                self.flip_card_animation(lbl)
                self.game.cards_revealed["player"][i] = True
        if self.game_mode == "basic":
            dealer_children = self.dealer_cards_frame.winfo_children()
            if dealer_children:
                first = dealer_children[0]
                if hasattr(first, "card") and not first.is_face_up:
                    self.flip_card_animation(first)
                    self.game.cards_revealed["dealer"][0] = True
        self.update_hand_labels()
        self.after(1500, self.after_reveal)

    def after_reveal(self):
        self.sort_player_hand()

    # ---------- 翻转动画 ----------
    def flip_card_animation(self, card_label):
        card = card_label.card
        front_img = self.card_images.get((card.suit, card.rank), self.back_image)
        self.animate_flip(card_label, front_img, 0)

    def animate_flip(self, card_label, front_img, step):
        steps = 12
        orig_w, orig_h = 100, 140

        # 结束条件：恢复正面全尺寸图片
        if step > steps:
            card_label.is_face_up = True
            self.animation_in_progress = False
            tx, ty = card_label.target_pos if hasattr(card_label, 'target_pos') else (0, 0)
            card_label.place(x=tx, y=ty, width=orig_w, height=orig_h)
            card_label.config(image=front_img)
            return

        # 计算当前帧的宽度比例（前半段背面缩窄，后半段正面展开）
        half = steps // 2
        if step <= half:
            ratio = 1 - (step / float(half))        # 1 → 0
            use_back = True
        else:
            ratio = (step - half) / float(half)     # 0 → 1
            use_back = False

        w = max(1, int(orig_w * ratio))            # 当前宽度（至少1px）

        # 从缓存的原始图像生成缩放后的 PhotoImage
        # 注意：front_img 是完整正面图，但我们需要根据 use_back 选择图像源
        if use_back:
            # 使用背面图像（从 original_images 中获取“back”）
            img_key = "back"
            if img_key in self.original_images:
                pil_img = self.original_images[img_key].resize((w, orig_h), Image.LANCZOS)
            else:
                # 若没有背面原始图，则用当前 back_image 的原始尺寸? 这里直接使用 self.back_image 的原始图像？但 self.back_image 已经是 PhotoImage，无法缩放。
                # 保险做法：使用已加载的背面 PIL 原图（若存在）
                pil_img = self.original_images.get("back", Image.new('RGB', (orig_w, orig_h), 'green'))
                pil_img = pil_img.resize((w, orig_h), Image.LANCZOS)
        else:
            # 正面：从 original_images 中获取对应牌的原图（卡牌原图未缩放）
            # 根据 card_label.card 获取 key
            card = card_label.card
            key = (card.suit, card.rank)
            pil_img = self.original_images.get(key)
            if pil_img is None:
                # 容错：用 front_img 的原始图像？但 front_img 是 PhotoImage，无法获取原图。
                # 这里我们假设 original_images 中一定有该牌，因为 _load_assets 已加载。
                # 若没有，则生成一个占位图
                pil_img = Image.new('RGB', (orig_w, orig_h), 'gray')
            pil_img = pil_img.resize((w, orig_h), Image.LANCZOS)

        # 转换为 PhotoImage 并保存引用防止被垃圾回收
        scaled_img = ImageTk.PhotoImage(pil_img)
        if not hasattr(self, '_temp_flip_images'):
            self._temp_flip_images = {}
        self._temp_flip_images[card_label] = scaled_img   # 用 card_label 作为 key

        # 更新 Label 显示
        tx, ty = card_label.target_pos if hasattr(card_label, 'target_pos') else (0, 0)
        offset = (orig_w - w) // 2      # 水平居中
        card_label.config(image=scaled_img)
        card_label.place(x=tx + offset, y=ty, width=w, height=orig_h)

        # 继续下一帧
        self.after(30, lambda: self.animate_flip(card_label, front_img, step + 1))

    # ---------- 排序玩家手牌 ----------
    def sort_player_hand(self):
        """
        玩家手牌排序动画：最佳4张按牌型排序，弃牌放最后并斜放。
        流程：获取当前标签 → 计算目标位置 → 逐步移动 → 最后旋转弃牌。
        """
        # 1. 选出最佳4张和弃牌
        self.game.select_best_hands()

        # 2. 获取当前所有牌标签（已正面朝上）
        labels = list(self.player_cards_frame.winfo_children())
        if not labels:
            return

        # 3. 记录当前 x 坐标
        current_pos = {}
        for lbl in labels:
            if lbl.winfo_exists():
                current_pos[lbl] = lbl.winfo_x()

        # 4. 排序最佳手牌，并拼接弃牌（玩家只有1张弃牌）
        sorted_best = sort_hand_by_rank(self.game.player_best_hand)
        discarded = self.game.player_discarded  # 列表，长度=1
        final_order = sorted_best + discarded   # 总长度5

        # 5. 计算每个标签的目标 x 坐标
        target_pos = {}
        for idx, card in enumerate(final_order):
            for lbl in labels:
                if hasattr(lbl, 'card') and lbl.card == card:
                    target_pos[lbl] = idx * 110
                    break

        # 6. 准备移动数据
        steps = 20
        interval = 30
        data = []
        for lbl in labels:
            if lbl in target_pos:
                start_x = current_pos.get(lbl, lbl.winfo_x())
                dx = (target_pos[lbl] - start_x) / steps
                data.append((lbl, start_x, dx))

        if not data:
            self._finalize_player_sort(labels)
            return

        # 7. 逐步移动
        def step(cnt):
            if cnt > steps:
                # 最终定位
                for lbl, start_x, dx in data:
                    if lbl.winfo_exists():
                        lbl.place(x=target_pos[lbl])
                self._finalize_player_sort(labels)
                return
            for lbl, start_x, dx in data:
                if lbl.winfo_exists():
                    lbl.place(x=start_x + dx * cnt)
            self.after(interval, lambda: step(cnt + 1))

        step(1)

    def _finalize_player_sort(self, labels):
        """玩家排序完成后的收尾工作：斜放弃牌，更新标签，启用决策按钮"""
        discarded = self.game.player_discarded
        for lbl in labels:
            if not lbl.winfo_exists():
                continue
            if hasattr(lbl, 'card') and lbl.card in discarded:
                card = lbl.card
                orig = self.original_images.get((card.suit, card.rank), self.original_images["back"])
                rotated = orig.rotate(45, expand=True)
                resized = rotated.resize((110, 140), Image.LANCZOS)
                photo = ImageTk.PhotoImage(resized)
                lbl.config(image=photo)
                lbl.image = photo  # 保持引用
        self.update_hand_labels()
        self.after(500, self.after_sort)  # 启用决策按钮

    def _sort_player_hand_internal(self):
        self.game.select_best_hands()
        self.game.player_best_hand = sort_hand_by_rank(self.game.player_best_hand)
        self.game.player_discarded = sorted(self.game.player_discarded, key=lambda c: c.value, reverse=True)

        for widget in self.player_cards_frame.winfo_children():
            widget.destroy()

        for i, card in enumerate(self.game.player_best_hand):
            lbl = tk.Label(self.player_cards_frame, image=self.back_image, bg='#2a4a3c')
            lbl.place(x=i*110, y=0, width=110, height=140)
            lbl.card = card
            lbl.is_face_up = False
            self.active_card_labels.append(lbl)

        if self.game.player_discarded:
            discarded = self.game.player_discarded[0]
            lbl = tk.Label(self.player_cards_frame, image=self.back_image, bg='#2a4a3c')
            lbl.place(x=4*110, y=0, width=110, height=140)
            lbl.card = discarded
            lbl.is_face_up = False
            lbl.is_discarded = True
            self.active_card_labels.append(lbl)

        for lbl in self.player_cards_frame.winfo_children():
            if hasattr(lbl, 'card'):
                card = lbl.card
                front = self.card_images.get((card.suit, card.rank), self.back_image)
                lbl.config(image=front)
                lbl.is_face_up = True
                if hasattr(lbl, 'is_discarded') and lbl.is_discarded:
                    orig = self.original_images.get((card.suit, card.rank), self.original_images["back"])
                    rotated = orig.rotate(45, expand=True)
                    resized = rotated.resize((110,140), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(resized)
                    lbl.config(image=photo)
                    lbl.image = photo
        self.update_hand_labels()
        self.after(500, self.after_sort)

    def after_sort(self):
        self.enable_decision_buttons()
        self.stage_label.config(text="决策")
        self.status_label.config(text="请选择下注倍数或弃牌")

    def enable_decision_buttons(self):
        ante = self.game.ante
        max_multiplier = 0
        for m in [1,2,3]:
            if self.balance >= ante*m:
                max_multiplier = m
            else:
                break
        if self.fold_button:
            self.fold_button.config(state=tk.NORMAL)
        for btn, m in [(self.play_1x_button,1),(self.play_2x_button,2),(self.play_3x_button,3)]:
            if btn:
                btn.config(state=tk.NORMAL if max_multiplier >= m else tk.DISABLED)

    # ---------- 决策动作 ----------
    def fold_action(self):
        self.disable_decision_buttons()
        self.game.folded = True
        self.status_label.config(text="您已弃牌 ~ 游戏结束")
        self.ante_var.set("0")
        self.play_var.set("0")
        self._save_history({"fold": True})
        self.reveal_dealer_cards()

    def play_action(self, multiplier):
        self.disable_decision_buttons()
        play_bet = self.game.ante * multiplier
        if play_bet > self.balance:
            messagebox.showerror("错误", "余额不足")
            return
        self.balance -= play_bet
        self.update_balance()
        self.game.play_bet = play_bet
        self.play_var.set(str(play_bet))
        total = self.game.ante + play_bet
        if self.game_mode == "basic":
            total += self.game.ace_plus_bet
        else:
            total += self.game.super_bonus_bet + self.game.queens_plus_bet
        self.current_bet_label.config(text=f"本局下注: ${total:.2f}")
        self.game.stage = "showdown"
        self.stage_label.config(text="摊牌")
        self.status_label.config(text="摊牌中...")
        self.after(1000, self.show_showdown)

    def disable_decision_buttons(self):
        for btn in [self.fold_button, self.play_1x_button, self.play_2x_button, self.play_3x_button]:
            if btn:
                try:
                    btn.config(state=tk.DISABLED)
                except tk.TclError:
                    pass  # 按钮已被销毁，忽略

    # ---------- 摊牌 ----------
    def show_showdown(self):
        self.reveal_dealer_cards()

    def reveal_dealer_cards(self):
        for i, lbl in enumerate(self.dealer_cards_frame.winfo_children()):
            if hasattr(lbl, "card") and not lbl.is_face_up:
                self.flip_card_animation(lbl)
                self.game.cards_revealed["dealer"][i] = True
        self.update_hand_labels()
        self.after(1000, self.after_dealer_reveal)

    def after_dealer_reveal(self):
        self.sort_dealer_hand()

    def sort_dealer_hand(self):
        """
        庄家手牌排序动画：最佳4张排序，弃牌（1~2张）放最后并斜放。
        """
        # 1. 选出最佳4张和弃牌
        self.game.select_best_hands()

        # 2. 获取当前所有牌标签
        labels = list(self.dealer_cards_frame.winfo_children())
        if not labels:
            return

        # 3. 记录当前 x 坐标
        current_pos = {}
        for lbl in labels:
            if lbl.winfo_exists():
                current_pos[lbl] = lbl.winfo_x()

        # 4. 排序最佳手牌，并拼接弃牌（基本版2张，疯狂版1张）
        sorted_best = sort_hand_by_rank(self.game.dealer_best_hand)
        discarded = self.game.dealer_discarded
        final_order = sorted_best + discarded

        # 5. 计算目标位置
        target_pos = {}
        for idx, card in enumerate(final_order):
            for lbl in labels:
                if hasattr(lbl, 'card') and lbl.card == card:
                    target_pos[lbl] = idx * 110
                    break

        # 6. 移动动画
        steps = 20
        interval = 30
        data = []
        for lbl in labels:
            if lbl in target_pos:
                start_x = current_pos.get(lbl, lbl.winfo_x())
                dx = (target_pos[lbl] - start_x) / steps
                data.append((lbl, start_x, dx))

        if not data:
            self._finalize_dealer_sort(labels)
            return

        def step(cnt):
            if cnt > steps:
                for lbl, start_x, dx in data:
                    if lbl.winfo_exists():
                        lbl.place(x=target_pos[lbl])
                self._finalize_dealer_sort(labels)
                return
            for lbl, start_x, dx in data:
                if lbl.winfo_exists():
                    lbl.place(x=start_x + dx * cnt)
            self.after(interval, lambda: step(cnt + 1))

        step(1)

    def _finalize_dealer_sort(self, labels):
        """庄家排序完成：斜放弃牌，更新标签，进入结算"""
        discarded = self.game.dealer_discarded
        for lbl in labels:
            if not lbl.winfo_exists():
                continue
            if hasattr(lbl, 'card') and lbl.card in discarded:
                card = lbl.card
                orig = self.original_images.get((card.suit, card.rank), self.original_images["back"])
                rotated = orig.rotate(45, expand=True)
                resized = rotated.resize((110, 140), Image.LANCZOS)
                photo = ImageTk.PhotoImage(resized)
                lbl.config(image=photo)
                lbl.image = photo
        self.update_hand_labels()
        self.after(500, self.settle_game)  # 进入结算

    # ---------- 结算 ----------
    def settle_game(self):
        winnings, details = self.calculate_winnings()
        self.last_win = winnings
        self.balance += winnings
        self.update_balance()

        self.ante_var.set(str(int(details["ante"])))
        self.play_var.set(str(int(details["play"])))
        if self.game_mode == "basic":
            self.ace_plus_var.set(str(int(details["ace_plus"])))
        else:
            self.super_bonus_var.set(str(int(details["super_bonus"])))
            self.queens_plus_var.set(str(int(details["queens_plus"])))

        for key, widget in self.bet_widgets.items():
            if not widget or not widget.winfo_exists():
                continue
            # 根据key判断
            if "ante" in key:
                bet = self.game.ante
                win = details["ante"]
            elif "play" in key:
                bet = self.game.play_bet
                win = details["play"]
            elif "ace" in key:
                bet = self.game.ace_plus_bet
                win = details["ace_plus"]
            elif "super" in key:
                bet = self.game.super_bonus_bet
                win = details["super_bonus"]
            elif "queens" in key:
                bet = self.game.queens_plus_bet
                win = details["queens_plus"]
            else:
                continue
            if win > bet:
                widget.config(bg='gold')
            elif win == bet and bet > 0:
                widget.config(bg='light blue')
            else:
                widget.config(bg='white')

        comp = compare_hands(self.game.player_best_hand, self.game.dealer_best_hand)
        if self.game.folded:
            msg = "您已弃牌"
            winner = "fold"
        else:
            if comp > 0:
                msg = "本局您赢了"
                winner = "player"
            elif comp < 0:
                msg = "本局您输了"
                winner = "dealer"
            else:
                msg = "本局平局 (Push)"
                winner = "push"
        self.status_label.config(text=msg)
        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")

        self._save_history({"winner": winner, "winnings": winnings})
        self.show_restart_button()

    # ---------- 结算计算 ----------
    def calculate_winnings(self):
        """
        结算各下注项的收益（含本金）。
        返回: (winnings, details) 其中 details 记录每项的返还金额。
        """
        winnings = 0
        details = {
            "ante": 0,
            "play": 0,
            "ante_bonus": 0,
            "ace_plus": 0,
            "super_bonus": 0,
            "queens_plus": 0
        }

        # ---------- 玩家弃牌（Fold）特殊处理 ----------
        if self.game.folded:
            if self.game_mode == "basic":
                # 底注输，加注无，Ante Bonus不支付，仅Ace+独立结算
                details["ante"] = 0
                details["play"] = 0
                details["ante_bonus"] = 0
                if self.game.ace_plus_bet > 0:
                    ace_win = self.calculate_ace_plus()   # 含本金或0
                    winnings += ace_win
                    details["ace_plus"] = ace_win
                else:
                    details["ace_plus"] = 0
            else:  # crazy
                # 底注输，超级红利输，加注无，仅Queens+独立结算
                details["ante"] = 0
                details["play"] = 0
                details["super_bonus"] = 0
                if self.game.queens_plus_bet > 0:
                    queens_win = self.calculate_queens_plus()   # 含本金或0
                    winnings += queens_win
                    details["queens_plus"] = queens_win
                else:
                    details["queens_plus"] = 0
            return winnings, details

        # ---------- 非弃牌（正常Play） ----------
        if self.game_mode == "basic":
            # ----- 基本版 -----
            comp = compare_hands(self.game.player_best_hand, self.game.dealer_best_hand)
            if comp >= 0:
                ante_result = self.game.ante * 2          # 赢，含本金
                play_result = self.game.play_bet * 2      # 加注赢，含本金
            else:
                ante_result = 0
                play_result = 0
            winnings += ante_result + play_result
            details["ante"] = ante_result
            details["play"] = play_result

            # Ante Bonus（额外红利，与输赢无关，但有牌型才支付）
            bonus = self.calculate_ante_bonus()
            winnings += bonus
            details["ante"] += bonus          # 将红利合并计入ante项
            details["ante_bonus"] = bonus

            # Ace+ 独立结算
            if self.game.ace_plus_bet > 0:
                ace_win = self.calculate_ace_plus()
                winnings += ace_win
                details["ace_plus"] = ace_win
            else:
                details["ace_plus"] = 0

        else:  # ----- 疯狂版 -----
            dealer_qual = dealer_qualifies(self.game.dealer_hand)
            comp = compare_hands(self.game.player_best_hand, self.game.dealer_best_hand)

            # 1. 底注
            if not dealer_qual:
                # 庄家不合格：底注退还（Push）
                ante_result = self.game.ante
            else:
                if comp > 0:
                    ante_result = self.game.ante * 2
                elif comp == 0:
                    ante_result = self.game.ante
                else:
                    ante_result = 0
            winnings += ante_result
            details["ante"] = ante_result

            # 2. 加注
            if not dealer_qual:
                # 庄家不合格：根据比较结果结算加注
                if comp > 0:
                    play_result = self.game.play_bet * 2       # 赢
                elif comp == 0:
                    play_result = self.game.play_bet           # Push
                else:
                    play_result = 0                            # 输
            else:
                if comp > 0:
                    play_result = self.game.play_bet * 2
                elif comp == 0:
                    play_result = self.game.play_bet
                else:
                    play_result = 0
            winnings += play_result
            details["play"] = play_result

            # 3. 超级红利（与加注绑定，但赔付按牌型）
            if self.game.super_bonus_bet > 0:
                if not dealer_qual:
                    if comp > 0:
                        super_win = self.calculate_super_bonus()   # 含本金
                    elif comp == 0:
                        super_win = self.game.super_bonus_bet      # Push
                    else:
                        super_win = 0                              # 输
                else:
                    if comp > 0:
                        super_win = self.calculate_super_bonus()
                    elif comp == 0:
                        super_win = self.game.super_bonus_bet
                    else:
                        super_win = 0
                winnings += super_win
                details["super_bonus"] = super_win
            else:
                details["super_bonus"] = 0

            # 4. Queens+（独立结算，与庄家是否合格无关）
            if self.game.queens_plus_bet > 0:
                queens_win = self.calculate_queens_plus()
                winnings += queens_win
                details["queens_plus"] = queens_win
            else:
                details["queens_plus"] = 0

        return winnings, details

    def calculate_ante_bonus(self):
        if not self.game.player_best_hand:
            return 0
        rank, _ = evaluate_four_card_hand(self.game.player_best_hand)
        if rank in [5,6,7]:
            return self.game.ante * ANTE_BONUS_PAYOUT[rank]
        return 0

    def calculate_ace_plus(self):
        if not self.game.player_best_hand:
            return 0
        rank, _ = evaluate_four_card_hand(self.game.player_best_hand)
        if rank == 1:
            values = [c.value for c in self.game.player_best_hand]
            if values.count(14) >= 2:
                return self.game.ace_plus_bet * ACE_PLUS_PAYOUT[1]
            else:
                return 0
        if rank in ACE_PLUS_PAYOUT:
            return self.game.ace_plus_bet * ACE_PLUS_PAYOUT[rank]
        return 0

    def calculate_super_bonus(self):
        if not self.game.player_best_hand:
            return 0
        rank, _ = evaluate_four_card_hand(self.game.player_best_hand)
        if rank == 7:
            values = [c.value for c in self.game.player_best_hand]
            if values.count(14) == 4:
                return self.game.super_bonus_bet * (SUPER_BONUS_PAYOUT[7]['A'] + 1)
            else:
                return self.game.super_bonus_bet * (SUPER_BONUS_PAYOUT[7]['other'] + 1)
        elif rank in SUPER_BONUS_PAYOUT:
            return self.game.super_bonus_bet * (SUPER_BONUS_PAYOUT[rank] + 1)
        else:
            return self.game.super_bonus_bet

    def calculate_queens_plus(self):
        if not self.game.player_best_hand:
            return 0
        rank, _ = evaluate_four_card_hand(self.game.player_best_hand)
        if rank == 1:
            values = [c.value for c in self.game.player_best_hand]
            cnt = {}
            for v in values:
                cnt[v] = cnt.get(v,0)+1
            for v,c in cnt.items():
                if c >= 2 and v >= 12:
                    return self.game.queens_plus_bet * (QUEENS_PLUS_PAYOUT[1] + 1)
            return 0
        if rank in QUEENS_PLUS_PAYOUT:
            return self.game.queens_plus_bet * (QUEENS_PLUS_PAYOUT[rank] + 1)
        return 0

    # ---------- 保存历史（使用排序后的手牌） ----------
    def _save_history(self, result_info=None):
        try:
            deck = self.game.deck
            if deck is None:
                return
            # 强制对玩家和庄家的最佳手牌及弃牌进行排序，确保保存的是最终排序后的顺序
            if self.game.player_best_hand:
                self.game.player_best_hand = sort_hand_by_rank(self.game.player_best_hand)
            if self.game.player_discarded:
                self.game.player_discarded = sorted(self.game.player_discarded, key=lambda c: c.value, reverse=True)
            if self.game.dealer_best_hand:
                self.game.dealer_best_hand = sort_hand_by_rank(self.game.dealer_best_hand)
            if self.game.dealer_discarded:
                self.game.dealer_discarded = sorted(self.game.dealer_discarded, key=lambda c: c.value, reverse=True)

            # 构造完整手牌顺序：最佳4张（已排序） + 弃牌（已排序）
            sorted_player = list(self.game.player_best_hand) + list(self.game.player_discarded)
            sorted_dealer = list(self.game.dealer_best_hand) + list(self.game.dealer_discarded)
            save_four_card_history(deck, sorted_player, sorted_dealer, self.game_mode, result_info)
        except Exception as e:
            print(f"保存历史记录出错: {e}")

    # ---------- 重新开始 ----------
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
            self.disable_decision_buttons()
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
        self.play_var.set("0")
        if self.game_mode == "basic":
            self.ace_plus_var.set("0")
        else:
            self.super_bonus_var.set("0")
            self.queens_plus_var.set("0")
        # 重置所有 bet_widgets 背景
        for widget in self.bet_widgets.values():
            if widget and widget.winfo_exists():
                widget.config(bg='white')
        self.active_card_labels = []

        # 重新绑定事件（对所有 bet_widgets 中可点击的重新绑定，但我们需要区分哪些是可点击的）
        # 简便：对所有标签绑定，如果绑定时会覆盖，我们只绑定那些需要交互的
        # 我们根据 key 判断，但也可以直接绑定，因为方法会检查类型
        for key, widget in self.bet_widgets.items():
            if not widget or not widget.winfo_exists():
                continue
            # 根据 key 决定绑定
            if "ante" in key:
                widget.bind("<Button-1>", lambda e, k="ante": self.add_chip_to_bet(k))
                widget.bind("<Button-3>", lambda e, k="ante": self.reset_single_bet(k, e))
            elif "ace" in key:
                widget.bind("<Button-1>", lambda e, k="ace_plus": self.add_chip_to_bet(k))
                widget.bind("<Button-3>", lambda e, k="ace_plus": self.reset_single_bet(k, e))
            elif "queens" in key:
                widget.bind("<Button-1>", lambda e, k="queens_plus": self.add_chip_to_bet(k))
                widget.bind("<Button-3>", lambda e, k="queens_plus": self.reset_single_bet(k, e))
            elif "super" in key:
                # 超级红利绑定底注
                widget.bind("<Button-1>", lambda e, k="ante": self.add_chip_to_bet(k))
                widget.bind("<Button-3>", lambda e, k="ante": self.reset_single_bet(k, e))
            # play 标签不绑定

        for chip in self.chip_buttons:
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e,t=text: self.select_chip(t))

        self.clear_btn_frame()
        self.add_main_buttons()
        self.current_bet_label.config(text="本局下注: $0.00")
        self.game_in_progress = False
        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))
        else:
            self.status_label.config(text="设置下注金额并开始游戏")

    def animate_collect_cards(self, auto_reset):
        self.disable_decision_buttons()
        self.animate_move_cards_out(auto_reset)

    def animate_move_cards_out(self, auto_reset):
        # 清理已经销毁的标签
        self.active_card_labels = [lbl for lbl in self.active_card_labels if lbl and lbl.winfo_exists()]
        if not self.active_card_labels:
            self._do_reset(auto_reset)
            return
        for lbl in self.active_card_labels:
            if lbl and lbl.winfo_exists():
                lbl.target_pos = (1200, lbl.winfo_y())
        self.animate_card_out_step(auto_reset)

    def animate_card_out_step(self, auto_reset):
        all_done = True
        for lbl in self.active_card_labels[:]:
            if not lbl or not lbl.winfo_exists():
                if lbl in self.active_card_labels:
                    self.active_card_labels.remove(lbl)
                continue
            if not hasattr(lbl, 'target_pos'):
                self.active_card_labels.remove(lbl)
                continue
            try:
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
            except tk.TclError:
                if lbl in self.active_card_labels:
                    self.active_card_labels.remove(lbl)
                continue
        if not all_done:
            self.after(20, lambda: self.animate_card_out_step(auto_reset))
        else:
            self._do_reset(auto_reset)

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
def main(initial_balance=10000, username="Guest", *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """嵌入现有 Tk 根窗口；未传 parent 时仍可独立运行。"""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return FourCardPokerGUI(
            parent, actual_balance, actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("Four Card Poker")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = FourCardPokerGUI(root, actual_balance, actual_user)
    page.pack(fill="both", expand=True)

    def close_standalone():
        try:
            update_balance_in_json(page.username, page.balance)
        except Exception:
            pass
        root.destroy()

    page.on_back = lambda final_balance: close_standalone()
    root.protocol("WM_DELETE_WINDOW", page.on_close)
    root.mainloop()
    return page.balance


if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")
