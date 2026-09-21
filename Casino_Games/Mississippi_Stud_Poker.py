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
import secrets
import subprocess, sys
import time
from collections import Counter
from itertools import combinations

# =========================================================
# 仿 Caribbean_Stud_Poker UI 颜色
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
    5: '顺子', 4: '三条', 3: '两对', 2: 'Jacks或更好对子', 1: '对子6-10', 0: '高牌'
}

# 主注赔率表（Ante + 3rd/4th/5th 总和）
MAIN_BET_PAYOUT = {
    10: 500,   # 皇家同花顺 500:1
    9: 100,    # 同花顺 100:1
    8: 40,     # 四条 40:1
    7: 10,     # 葫芦 10:1
    6: 6,      # 同花 6:1
    5: 4,      # 顺子 4:1
    4: 3,      # 三条 3:1
    3: 2,      # 两对 2:1
    2: 1,      # Jacks或更好对子 1:1
    1: 0       # 对子6-10 Push（返还本金）
}

# 3 Card Bonus 边注赔率表（基于3张公共牌）
BONUS3_PAYOUT = {
    40: 40,    # 同花顺 40:1
    30: 30,    # 三条 30:1
    6: 6,      # 顺子 6:1
    3: 3,      # 同花 3:1
    1: 1       # 对子 1:1
}

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
# Progressive 文件加载与保存 (Key: 'MSP')
# =========================================================
def load_jackpot():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
    default_jackpot = 271288.59
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
# 历史记录（Mississippi_Stud_Poker.json）
# =========================================================
def mississippi_log_path() -> str:
    """返回日志文件路径"""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Mississippi_Stud_Poker.json")

def save_mississippi_history(deck, comm_cards, player_cards, win_amount, hand_rank, hand_name, result_status, fold):
    """
    保存牌局历史到 Mississippi_Stud_Poker.json
    history_record 包含 game, win, lose 及各牌型计数
    history 每条记录包含：
        game_id, timestamp, deck_order, cut_position,
        comm_cards, player_cards, win_amount, is_win
    """
    log_path = mississippi_log_path()
    # 初始化数据结构
    data = {
        "history_record": {
            "game": 0,
            "win": 0,
            "push": 0,
            "fold": 0,
            "lose": 0,
            "royal_flush": 0,
            "straight_flush": 0,
            "four_of_a_kind": 0,
            "full_house": 0,
            "flush": 0,
            "straight": 0,
            "three_of_a_kind": 0,
            "two_pair": 0,
            "pair_jack_or_better": 0,
            "pair_6_10": 0,
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
                    # 确保所有字段存在
                    for key in data["history_record"]:
                        if key not in loaded["history_record"]:
                            loaded["history_record"][key] = 0
                    data["history_record"] = loaded["history_record"]
                    if "history" in loaded:
                        data["history"] = loaded["history"]
                elif isinstance(loaded, list):
                    # 旧格式迁移（仅 history 列表）
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
            print(f"读取历史文件出错: {e}，将使用全新记录")

    stats = data["history_record"]
    stats["game"] += 1
    if fold:
        stats["fold"] += 1
    else:
        if result_status == "Win":
            stats["win"] += 1
        elif result_status == "Push":
            stats["push"] += 1
        elif result_status == "Lose":
            stats["lose"] += 1

    # 根据 hand_rank 增加牌型计数
    rank_to_key = {
        10: 'royal_flush',
        9: 'straight_flush',
        8: 'four_of_a_kind',
        7: 'full_house',
        6: 'flush',
        5: 'straight',
        4: 'three_of_a_kind',
        3: 'two_pair',
        2: 'pair_jack_or_better',
        1: 'pair_6_10',
        0: 'high_card'
    }
    key = rank_to_key.get(hand_rank, 'high_card')
    stats[key] = stats.get(key, 0) + 1

    # 生成新 game_id
    max_id = 0
    for rec in data["history"]:
        if "game_id" in rec and isinstance(rec["game_id"], int):
            if rec["game_id"] > max_id:
                max_id = rec["game_id"]
    new_game_id = max_id + 1

    # 构建记录
    record = {
        "game_id": new_game_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "deck_order": [str(c) for c in deck.full_deck],
        "cut_position": deck.cut_position,
        "comm_cards": [str(c) for c in comm_cards],
        "player_cards": [str(c) for c in player_cards],
        "win_amount": win_amount,
        "result": result_status        # "Win"/"Push"/"Lose"
    }
    data["history"].append(record)

    # 保留最新50局
    if len(data["history"]) > 50:
        data["history"] = data["history"][-50:]

    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# =========================================================
# 扑克牌类与牌堆（同 Caribbean_Stud_Poker）
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
# Mississippi 评估函数（原样）
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
        if pair >= 11:
            return (2, [pair] + kickers)
        elif pair >= 6:
            return (1, [pair] + kickers)
        else:
            return (0, values[:5])
    return (0, values[:5])

def evaluate_3card_hand(cards):
    """评估3张牌的牌型，返回数值等级：40同花顺，30三条，6顺子，3同花，1对子，0高牌"""
    if len(cards) != 3:
        return 0
    values = [c.value for c in cards]
    suits = [c.suit for c in cards]
    flush = len(set(suits)) == 1
    values.sort()
    if values == [2,3,14]:
        straight = True
    elif values[0]+1 == values[1] and values[1]+1 == values[2]:
        straight = True
    else:
        straight = False
    three = values[0]==values[1]==values[2]
    pair = values[0]==values[1] or values[1]==values[2] or values[0]==values[2]
    if three:
        return 30
    elif flush and straight:
        return 40
    elif straight:
        return 6
    elif flush:
        return 3
    elif pair:
        return 1
    else:
        return 0

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
# Mississippi 游戏逻辑类（保留原游戏流程）
# =========================================================
class MississippiStudGame:
    def __init__(self):
        self.reset_game()
        self.progressive_amount = load_jackpot()[1]
        self.min_progressive = 271288.59

    def reset_game(self):
        self.deck = Deck()
        self.community_cards = []
        self.player_hole = []
        self.ante = 0
        self.bonus3 = 0
        self.street3 = 0
        self.street4 = 0
        self.street5 = 0
        self.stage = "pre_flop"  # pre_flop, street3, street4, street5, showdown
        self.folded = False
        self.cards_revealed = {
            "player": [False, False],
            "community": [False, False, False]
        }
        self.cut_position = self.deck.start_pos
        self.card_sequence = self.deck.card_sequence

    def deal_initial(self):
        self.player_hole = self.deck.deal(2)
        self.community_cards = self.deck.deal(3)

    def evaluate_final_hand(self):
        cards = self.player_hole + self.community_cards
        return evaluate_hand(cards)[0]

    def evaluate_community_3(self):
        return evaluate_3card_hand(self.community_cards)

# =========================================================
# 主GUI类（仿 Caribbean_Stud_Poker 风格）
# =========================================================
class MississippiStudGUI(tk.Frame):
    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG)
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.configure(bg=ROOT_BG)

        self.username = username
        self.balance = initial_balance
        self.game = MississippiStudGame()
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
        self.last_jackpot_state = 0
        self.win_details = {
            "ante": 0,
            "bonus3": 0,
            "street3": 0,
            "street4": 0,
            "street5": 0
        }
        self.bet_widgets = {}
        self.jackpot_bet_var = tk.IntVar(value=0)
        self.game_in_progress = False
        self.high_bet_mode = False

        self.ante_var = tk.StringVar(value="0")
        self.bonus3_var = tk.StringVar(value="0")
        self.street3_var = tk.StringVar(value="0")
        self.street4_var = tk.StringVar(value="0")
        self.street5_var = tk.StringVar(value="0")

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


    # ---------- 加载扑克牌（交替 Poker1/Poker2） ----------
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

    # ---------- 添加筹码到下注 ----------
    def add_chip_to_bet(self, bet_type):
        if not self.selected_chip:
            return
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K','')) * 1000
        else:
            chip_value = float(chip_text)

        if bet_type == "ante":
            current = float(self.ante_var.get())
            limit = 50000 if self.high_bet_mode else 10000
            if current >= limit:
                messagebox.showwarning("下注限制", "底注已满，不能再下注！")
                return
            new_amount = current + chip_value
            if new_amount > limit:
                new_amount = limit
                if current > 0:
                    messagebox.showwarning("下注限制", f"底注已达上限，自动调整为 {int(new_amount)}")
            self.ante_var.set(str(int(new_amount)))
        elif bet_type == "bonus3":
            current = float(self.bonus3_var.get())
            limit = 12500 if self.high_bet_mode else 2500
            if current >= limit:
                messagebox.showwarning("下注限制", "公牌加注已满，不能再下注！")
                return
            new_amount = current + chip_value
            if new_amount > limit:
                new_amount = limit
                if current > 0:
                    messagebox.showwarning("下注限制", f"公牌加注已达上限，自动调整为 {int(new_amount)}")
            self.bonus3_var.set(str(int(new_amount)))

    # ---------- 重置单个下注（右键） ----------
    def reset_single_bet(self, bet_type, event):
        if bet_type == "ante":
            self.ante_var.set("0")
        elif bet_type == "bonus3":
            self.bonus3_var.set("0")
        if bet_type in self.bet_widgets:
            widget = self.bet_widgets[bet_type]
            original_bg = widget.cget('bg')
            widget.config(bg='#FFCDD2')
            self.after(500, lambda: widget.config(bg=original_bg))

    # ---------- 清空按钮框架 ----------
    def clear_btn_frame(self):
        for widget in self.btn_frame.winfo_children():
            widget.destroy()

    # ---------- 添加主按钮 ----------
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

        # 公共牌区域
        community_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        community_frame.place(x=180, y=60, width=375, height=230)
        self.community_label = tk.Label(community_frame, text="公共牌", font=('Arial',18), bg='#2a4a3c', fg='white')
        self.community_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.community_cards_frame = tk.Frame(community_frame, bg='#2a4a3c')
        self.community_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 中间提示（密西西比特有：对子规则）
        self.ante_info_label = tk.Label(
            table_canvas,
            text="对子5或以下获败\n对子6-10平局\n对子JACK或以上获胜",
            font=('Arial',26),
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
        player_frame.place(x=230, y=450, width=270, height=230)
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

        # 筹码按钮行
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

        # ---------- 下注行布局（按需求） ----------
        # 第一行：累进大奖 (左)  | 三街 (右)
        row1 = tk.Frame(body_combined, bg=PANEL_BG)
        row1.grid(row=1, column=0, columnspan=2, sticky='ew', pady=2)
        self.jackpot_check = tk.Checkbutton(
            row1, text="累进大奖 ($2.50)", variable=self.jackpot_bet_var,
            font=('Arial',12,"bold"), bg=PANEL_BG, fg='black', selectcolor=PANEL_BG
        )
        self.jackpot_check.pack(side=tk.LEFT, padx=10)

        tk.Label(row1, text="三街:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=(43,5))
        self.street3_display = tk.Label(row1, textvariable=self.street3_var, font=('Arial',12),
                                        bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.street3_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["street3"] = self.street3_display

        # 第二行：公牌加注 (左) | 四街 (右)
        row2 = tk.Frame(body_combined, bg=PANEL_BG)
        row2.grid(row=2, column=0, columnspan=2, sticky='ew', pady=2)
        tk.Label(row2, text="公牌加注:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=10)
        self.bonus3_display = tk.Label(row2, textvariable=self.bonus3_var, font=('Arial',12),
                                       bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.bonus3_display.pack(side=tk.LEFT, padx=5)
        self.bonus3_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bonus3"))
        self.bonus3_display.bind("<Button-3>", lambda e: self.reset_single_bet("bonus3", e))
        self.bet_widgets["bonus3"] = self.bonus3_display

        tk.Label(row2, text="四街:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=(26,5))
        self.street4_display = tk.Label(row2, textvariable=self.street4_var, font=('Arial',12),
                                        bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.street4_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["street4"] = self.street4_display

        # 第三行：底注 (左) | 五街 (右)
        row3 = tk.Frame(body_combined, bg=PANEL_BG)
        row3.grid(row=3, column=0, columnspan=2, sticky='ew', pady=2)
        tk.Label(row3, text="         底注:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=7)
        self.ante_display = tk.Label(row3, textvariable=self.ante_var, font=('Arial',12),
                                     bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.ante_display.pack(side=tk.LEFT, padx=9)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.bet_widgets["ante"] = self.ante_display

        tk.Label(row3, text="五街:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=(21,5))
        self.street5_display = tk.Label(row3, textvariable=self.street5_var, font=('Arial',12),
                                        bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.street5_display.pack(side=tk.LEFT, padx=6)
        self.bet_widgets["street5"] = self.street5_display

        # ========== 操作卡片（统一内部元素尺寸） ==========
        action_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        action_card.pack(fill=tk.X, pady=3)
        header_action = tk.Frame(action_card, bg=HEADER_BG)
        header_action.pack(fill=tk.X)
        tk.Label(header_action, text="操作", font=('Arial',13,'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_action = tk.Frame(action_card, bg=PANEL_BG)
        body_action.pack(fill=tk.X, padx=10, pady=8)

        # 状态标签：统一宽度和高度（字符单位）
        self.status_label = tk.Label(
            body_action, text="设置下注金额并开始游戏", font=('Arial',12,'bold'),
            bg=PANEL_BG, fg='#2A1B08', height=1, width=30
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
            bg='#4B8BBE', fg='white', font=('Arial',12), width=2, height=1, relief=tk.FLAT
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

    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("密西西比梭哈扑克 游戏规则")
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

        # 规则文本
        rules_text = """
        密西西比梭哈扑克 游戏规则

        1. 下注阶段:
        - 底注: 必须下注
        - 公牌加注: 基于3张公共牌的牌型支付
        - 累进大奖: 可选 $2.50 下注，根据玩家最终5张牌型赢取奖金

        2. 游戏流程:
        a. 设置底注和公牌加注，选择是否参与累进大奖
        b. 点击「开始游戏」→ 发牌（玩家2张底牌 + 3张公共牌面朝下）
        c. 翻开玩家底牌，玩家决定：
            - 弃牌: 输掉所有下注（累进大奖仍可能中奖）
            - 下注1x/2x/3x（底注倍数）进入「三街」阶段
        d. 翻开第一张公共牌，再次选择弃牌或下注1x/2x/3x（四街）
        e. 翻开第二张公共牌，再次选择弃牌或下注1x/2x/3x（五街）
        f. 翻开第三张公共牌，摊牌结算

        3. 结算规则:
        - 主注（底注 + 三街 + 四街 + 五街）根据最终5张牌型支付（见下方赔率表）
        - 公牌加注根据3张公共牌牌型支付（见下方赔率表）
        - 累进大奖根据玩家最终5张牌型支付（见下方赔率表）

        4. 赔率表:
        """
        tk.Label(content_frame, text=rules_text, font=('微软雅黑', 11),
                bg='#F0F0F0', justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X, padx=10, pady=5)

        # ---- 创建统一赔率表格 ----
        table_frame = tk.Frame(content_frame, bg='#F0F0F0')
        table_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ["牌型", "主注赔率", "公牌加注", "累进大奖"]
        header_bg = '#4B8BBE'
        header_fg = 'white'
        for col, h in enumerate(headers):
            lbl = tk.Label(table_frame, text=h, font=('微软雅黑', 10, 'bold'),
                        bg=header_bg, fg=header_fg, padx=8, pady=5, anchor='center')
            lbl.grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 数据行（牌型、主注赔率、公牌加注、累进大奖）
        payout_data = [
            # 牌型        主注赔率     公牌加注    累进大奖
            ("皇家同花顺", "500:1",      "40:1",    "100% 奖池"),
            ("同花顺",    "100:1",      "40:1",    "10% 奖池"),
            ("四条",      "40:1",       "-",       "$1,250"),
            ("葫芦",      "10:1",       "-",       "$375"),
            ("同花",      "6:1",        "3:1",     "$250"),
            ("顺子",      "4:1",        "6:1",     "-"),
            ("三条",      "3:1",        "30:1",    "-"),
            ("两对",      "2:1",        "-",       "-"),
            ("Jack+对子", "1:1",        "-",       "-"),
            ("对子6-10",  "返还本金",   "-",     "-"),
            ("对子",      "-",        "1:1",     "-"),
            ("其他",      "输",         "输",      "-"),
        ]

        for row_idx, row_data in enumerate(payout_data, start=1):
            bg_color = '#E0E0E0' if row_idx % 2 == 0 else '#F0F0F0'
            for col_idx, cell_text in enumerate(row_data):
                lbl = tk.Label(table_frame, text=cell_text, font=('微软雅黑', 10),
                            bg=bg_color, padx=8, pady=5, anchor='center')
                lbl.grid(row=row_idx, column=col_idx, sticky='nsew', padx=1, pady=1)

        # 设置列权重（让表格均匀分布）
        for col in range(len(headers)):
            table_frame.columnconfigure(col, weight=1)

        # 额外注释
        notes = """
        注:
        • 主注 = 底注 + 三街 + 四街 + 五街的总和。
        • 公牌加注仅根据3张公共牌判定，与玩家手牌无关。
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
        visible_cards = self.game.player_hole + self.game.community_cards[:community_revealed]
        num_cards = len(visible_cards)
        if num_cards < 3:
            player_hand_name = ""
        else:
            values = [c.value for c in visible_cards]
            counts = Counter(values)
            mult_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
            if num_cards == 3:
                if mult_counts[0][1] == 3:
                    player_hand_name = "三条"
                elif mult_counts[0][1] == 2:
                    pair_val = mult_counts[0][0]
                    rank_str = RANKS[pair_val - 2]
                    player_hand_name = f"对子{rank_str}"
                else:
                    player_hand_name = "高牌"
            elif num_cards == 4:
                if mult_counts[0][1] == 4:
                    player_hand_name = "四条"
                elif mult_counts[0][1] == 3:
                    player_hand_name = "三条"
                elif mult_counts[0][1] == 2:
                    pairs = [v for v, cnt in mult_counts if cnt == 2]
                    if len(pairs) == 2:
                        player_hand_name = "两对"
                    else:
                        pair_val = pairs[0]
                        rank_str = RANKS[pair_val - 2]
                        player_hand_name = f"对子{rank_str}"
                else:
                    player_hand_name = "高牌"
            else:  # 5 cards
                rank, comp = evaluate_hand(visible_cards)
                if rank in (0,1,2):
                    pair_vals = [v for v, cnt in counts.items() if cnt == 2]
                    if pair_vals:
                        pair_val = max(pair_vals)
                        rank_str = RANKS[pair_val - 2]
                        player_hand_name = f"对子{rank_str}"
                    else:
                        player_hand_name = "高牌"
                else:
                    player_hand_name = HAND_RANK_NAMES.get(rank, "")
        self.player_label.config(text=f"玩家 - {player_hand_name}" if player_hand_name else "玩家")

    # ---------- 开始游戏 ----------
    def start_game(self):
        try:
            ante = int(self.ante_var.get())
            bonus3 = int(self.bonus3_var.get())
            jackpot = self.jackpot_bet_var.get()
            self.last_jackpot_state = jackpot
            jackpot_cost = 2.5 if jackpot else 0

            min_ante = 100 if self.high_bet_mode else 10
            max_ante = 50000 if self.high_bet_mode else 10000
            max_bonus = 12500 if self.high_bet_mode else 2500

            if ante < min_ante:
                messagebox.showerror("错误", f"底注至少需要 {min_ante} 块")
                return
            if ante > max_ante:
                ante = max_ante
                self.ante_var.set(str(max_ante))
                messagebox.showwarning("下注限制", f"底注上限为 {max_ante}，已自动调整")
            if bonus3 > max_bonus:
                bonus3 = max_bonus
                self.bonus3_var.set(str(max_bonus))

            total_bet = ante + bonus3 + jackpot_cost
            if (total_bet+ante*3) > self.balance:
                messagebox.showerror("错误", f"余额不足！需要 ${total_bet+ante*3:.2f}")
                return

            # 扣除初始下注
            self.balance -= total_bet
            self.game_in_progress = True
            self.update_balance()

            # 保存本次下注（用于重复）
            self.last_bet = {
                'ante': ante,
                'bonus3': bonus3,
                'jackpot': jackpot
            }
            if self.repeat_bet_btn:
                self.repeat_bet_btn.config(state=tk.NORMAL)

            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            self.last_win_label.config(text="上局获胜: $0.00")

            self.game.reset_game()
            self.game.ante = ante
            self.game.bonus3 = bonus3
            self.game.jackpot_bet = jackpot
            self.game.street3 = 0
            self.game.street4 = 0
            self.game.street5 = 0
            self.game.folded = False
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
            # 3张公共牌
            for i in range(3):
                card_id = f"community_{i}"
                self.card_positions[card_id] = {"current": (50,50), "target": (i*110,0)}
                self.animation_queue.append(card_id)
            # 2张玩家牌
            for i in range(2):
                card_id = f"player_{i}"
                self.card_positions[card_id] = {"current": (50,50), "target": (i*110,0)}
                self.animation_queue.append(card_id)

            # 禁用下注控件
            self.ante_display.unbind("<Button-1>")
            self.bonus3_display.unbind("<Button-1>")
            self.jackpot_check.config(state=tk.DISABLED)
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")

            # 清空操作按钮，准备显示街下注按钮
            self.clear_btn_frame()
            self.stage_label.config(text="第三街")
            self.status_label.config(text="手牌已翻开，请选择下注或弃牌")

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

    # ---------- 翻开玩家牌 ----------
    def reveal_player_cards(self):
        for i, lbl in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(lbl, "card") and not lbl.is_face_up:
                self.flip_card_animation(lbl)
                self.game.cards_revealed["player"][i] = True
        self.update_hand_labels()
        self.after(1000, self.show_street3_buttons)

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

    # ---------- 显示第三街下注按钮（统一尺寸） ----------
    def show_street3_buttons(self):
        self.game.stage = "street3"
        self.stage_label.config(text="第三街")
        self.status_label.config(text="请选择下注倍数或弃牌")

        self.clear_btn_frame()
        btn_frame = tk.Frame(self.btn_frame, bg=PANEL_BG)
        btn_frame.pack()
        ante = self.game.ante

        btn1 = tk.Button(btn_frame, text="1倍", command=lambda: self.place_street_bet(1),
                         font=('Arial',12,'bold'), bg='#4CAF50', fg='white', width=7, height=1)
        btn1.pack(side=tk.LEFT, padx=5)
        if self.balance < ante:
            btn1.config(state=tk.DISABLED)

        btn2 = tk.Button(btn_frame, text="2倍", command=lambda: self.place_street_bet(2),
                         font=('Arial',12,'bold'), bg='#4CAF50', fg='white', width=7, height=1)
        btn2.pack(side=tk.LEFT, padx=5)
        if self.balance < ante*4:
            btn2.config(state=tk.DISABLED)

        btn3 = tk.Button(btn_frame, text="3倍", command=lambda: self.place_street_bet(3),
                         font=('Arial',12,'bold'), bg='#4CAF50', fg='white', width=7, height=1)
        btn3.pack(side=tk.LEFT, padx=5)
        if self.balance < ante*5:
            btn3.config(state=tk.DISABLED)

        tk.Button(btn_frame, text="弃牌", command=self.fold_game,
                  font=('Arial',12,'bold'), bg='#F44336', fg='white', width=7, height=1).pack(side=tk.LEFT, padx=5)

    # ---------- 下注街 ----------
    def place_street_bet(self, multiplier):
        # 清除按钮防止重复点击
        self.clear_btn_frame()

        ante = self.game.ante
        amount = ante * multiplier

        if self.game.stage == "street3":
            bet_var = "street3"
            next_stage = "street4"
            community_index = 0
            display_var = self.street3_var
        elif self.game.stage == "street4":
            bet_var = "street4"
            next_stage = "street5"
            community_index = 1
            display_var = self.street4_var
        else:  # street5
            bet_var = "street5"
            next_stage = "showdown"
            community_index = 2
            display_var = self.street5_var

        if amount > self.balance:
            messagebox.showerror("错误", "余额不足！")
            # 重新显示当前阶段按钮
            if self.game.stage == "street3":
                self.show_street3_buttons()
            elif self.game.stage == "street4":
                self.show_next_street_buttons()
            else:
                self.show_next_street_buttons()
            return

        self.balance -= amount
        self.update_balance()
        setattr(self.game, bet_var, amount)
        display_var.set(str(amount))

        total_bet = self.game.ante + self.game.bonus3 + self.game.street3 + self.game.street4 + self.game.street5
        jackpot_cost = 2.5 if self.game.jackpot_bet else 0
        self.current_bet_label.config(text=f"本局下注: ${total_bet + jackpot_cost:.2f}")

        # 翻开公共牌
        self.reveal_community_card(community_index)

        if next_stage == "showdown":
            self.game.stage = "showdown"
            self.after(2000, self.show_showdown)
        else:
            self.game.stage = next_stage
            self.stage_label.config(text="第四街" if next_stage=="street4" else "第五街")
            self.status_label.config(text="请选择下注倍数或弃牌")
            self.after(1500, self.show_next_street_buttons)

    # ---------- 显示后续街按钮（统一尺寸） ----------
    def show_next_street_buttons(self):
        self.clear_btn_frame()
        btn_frame = tk.Frame(self.btn_frame, bg=PANEL_BG)
        btn_frame.pack()
        ante = self.game.ante

        if self.game.stage == "street4":
            # 四街
            btn1 = tk.Button(btn_frame, text="1倍", command=lambda: self.place_street_bet(1),
                             font=('Arial',12,'bold'), bg='#4CAF50', fg='white', width=7, height=1)
            btn1.pack(side=tk.LEFT, padx=5)
            if self.balance < ante:
                btn1.config(state=tk.DISABLED)

            btn2 = tk.Button(btn_frame, text="2倍", command=lambda: self.place_street_bet(2),
                             font=('Arial',12,'bold'), bg='#4CAF50', fg='white', width=7, height=1)
            btn2.pack(side=tk.LEFT, padx=5)
            if self.balance < ante*3:
                btn2.config(state=tk.DISABLED)

            btn3 = tk.Button(btn_frame, text="3倍", command=lambda: self.place_street_bet(3),
                             font=('Arial',12,'bold'), bg='#4CAF50', fg='white', width=7, height=1)
            btn3.pack(side=tk.LEFT, padx=5)
            if self.balance < ante*4:
                btn3.config(state=tk.DISABLED)

        elif self.game.stage == "street5":
            # 五街
            btn1 = tk.Button(btn_frame, text="1倍", command=lambda: self.place_street_bet(1),
                             font=('Arial',12,'bold'), bg='#4CAF50', fg='white', width=7, height=1)
            btn1.pack(side=tk.LEFT, padx=5)
            if self.balance < ante:
                btn1.config(state=tk.DISABLED)

            btn2 = tk.Button(btn_frame, text="2倍", command=lambda: self.place_street_bet(2),
                             font=('Arial',12,'bold'), bg='#4CAF50', fg='white', width=7, height=1)
            btn2.pack(side=tk.LEFT, padx=5)
            if self.balance < ante*2:
                btn2.config(state=tk.DISABLED)

            btn3 = tk.Button(btn_frame, text="3倍", command=lambda: self.place_street_bet(3),
                             font=('Arial',12,'bold'), bg='#4CAF50', fg='white', width=7, height=1)
            btn3.pack(side=tk.LEFT, padx=5)
            if self.balance < ante*3:
                btn3.config(state=tk.DISABLED)

        tk.Button(btn_frame, text="弃牌", command=self.fold_game,
                  font=('Arial',12,'bold'), bg='#F44336', fg='white', width=7, height=1).pack(side=tk.LEFT, padx=5)

    # ---------- 翻开公共牌 ----------
    def reveal_community_card(self, index):
        for i, lbl in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(lbl, "card") and not lbl.is_face_up and i == index:
                self.flip_card_animation(lbl)
                self.game.cards_revealed["community"][i] = True
                break
        self.update_hand_labels()

    # ---------- 弃牌 ----------
    def fold_game(self):
        self.clear_btn_frame()
        self.game.folded = True
        self.status_label.config(text="玩家弃牌，结算边注...")
        # 翻开所有公共牌（为了结算公牌加注）
        for i, lbl in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(lbl, "card") and not lbl.is_face_up:
                self.flip_card_animation(lbl)
                self.game.cards_revealed["community"][i] = True
        self.update_hand_labels()
        self.after(2000, self.show_showdown)

    # ---------- 摊牌结算 ----------
    def show_showdown(self):
        # 确保所有公共牌翻开
        for i, lbl in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(lbl, "card") and not lbl.is_face_up:
                self.flip_card_animation(lbl)
                self.game.cards_revealed["community"][i] = True

        self.update_hand_labels()

        final_rank = self.game.evaluate_final_hand()
        bonus3_rank = self.game.evaluate_community_3()

        winnings, details = self.calculate_winnings(final_rank, bonus3_rank)

        # 如果下注了累进大奖，计算奖金
        bonus_win = 0
        if self.game.jackpot_bet:
            bonus_win = self.calculate_bonus(final_rank)
            if bonus_win > 0:
                winnings += bonus_win
                details["bonus"] = bonus_win
                messagebox.showinfo("恭喜获得累进大奖！", f"您赢得了 ${bonus_win:,.2f} 奖金！")
                self.progressive_display.config(bg='gold')

        # 更新奖池（即使没有中奖也要更新）
        self.update_jackpot()

        self.balance += winnings
        self.update_balance()
        self.last_win = winnings
        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")

        # 更新下注显示（显示赢取金额）
        self.ante_var.set(str(int(details["ante"])))
        self.bonus3_var.set(str(int(details["bonus3"])))
        self.street3_var.set(str(int(details["street3"])))
        self.street4_var.set(str(int(details["street4"])))
        self.street5_var.set(str(int(details["street5"])))

        # 高亮赢注
        for bet_type, widget in self.bet_widgets.items():
            if bet_type in ["ante","street3","street4","street5"]:
                if self.game.folded:
                    widget.config(bg='white')
                else:
                    amt = getattr(self.game, bet_type, 0)
                    if details[bet_type] > amt:
                        widget.config(bg='gold')
                    elif details[bet_type] == amt and amt > 0:
                        widget.config(bg='light blue')
                    else:
                        widget.config(bg='white')
            elif bet_type == "bonus3":
                if details["bonus3"] > 0:
                    widget.config(bg='gold')
                else:
                    widget.config(bg='white')

        self.status_label.config(text="游戏结束。")
        self.stage_label.config(text="结束")

        # 显示再来一局按钮（统一尺寸）
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

        # ---------- 保存历史记录 ----------
        hand_name = HAND_RANK_NAMES.get(final_rank, "高牌")
        if self.game.folded:
            result_status = "Fold"
        else:
            if final_rank >= 2:
                result_status = "Win"
            elif final_rank == 1:
                result_status = "Push"
            else:  # final_rank == 0
                result_status = "Lose"

        save_mississippi_history(
            deck=self.game.deck,
            comm_cards=self.game.community_cards,
            player_cards=self.game.player_hole,
            win_amount=winnings,
            hand_rank=final_rank,
            hand_name=hand_name,
            result_status=result_status,
            fold=self.game.folded
        )

    # ---------- 计算主注和公牌加注赢利 ----------
    def calculate_winnings(self, final_rank, bonus3_rank):
        details = {k:0 for k in self.win_details}
        total = 0

        # 主注部分
        if not self.game.folded:
            main_total = self.game.ante + self.game.street3 + self.game.street4 + self.game.street5
            payout_mult = MAIN_BET_PAYOUT.get(final_rank, -1)
            if payout_mult >= 0:
                details["ante"] = self.game.ante * (1 + payout_mult)
                details["street3"] = self.game.street3 * (1 + payout_mult)
                details["street4"] = self.game.street4 * (1 + payout_mult)
                details["street5"] = self.game.street5 * (1 + payout_mult)
                total += details["ante"] + details["street3"] + details["street4"] + details["street5"]
            else:
                # 输，无返还
                details["ante"] = details["street3"] = details["street4"] = details["street5"] = 0
        else:
            details["ante"] = details["street3"] = details["street4"] = details["street5"] = 0

        # 公牌加注
        if self.game.bonus3 > 0:
            if bonus3_rank in BONUS3_PAYOUT:
                payout = BONUS3_PAYOUT[bonus3_rank]
                details["bonus3"] = self.game.bonus3 * (1 + payout)
            else:
                details["bonus3"] = 0
            total += details["bonus3"]

        return total, details

    # ---------- 累进大奖 ----------
    def calculate_bonus(self, rank):
        if not self.game.player_hole or len(self.game.player_hole) < 2:
            return 0
        # 玩家最终5张牌
        cards = self.game.player_hole + self.game.community_cards
        rank_eval, _ = evaluate_hand(cards)
        jackpot = self.game.progressive_amount
        bonus = 0

        # 只保留以下五种牌型，其余不支付
        if rank_eval == 10:          # 皇家同花顺 → 奖池的100%
            bonus = max(jackpot, 10000.0)      # 保留最低奖池保护
            self.game.progressive_amount -= bonus
        elif rank_eval == 9:         # 同花顺 → 奖池的10%
            bonus = max(jackpot * 0.1, 1000.0) # 保留最低奖池保护
            self.game.progressive_amount -= bonus
        elif rank_eval == 8:         # 四条 → $1250
            bonus = 1250.0
            self.game.progressive_amount -= bonus
        elif rank_eval == 7:         # 葫芦 → $375
            bonus = 375.0
            self.game.progressive_amount -= bonus
        elif rank_eval == 6:         # 同花 → $250
            bonus = 250.0
            self.game.progressive_amount -= bonus
        # 其他牌型（顺子、三条等）不再支付奖金

        # 保证奖池不低于最低值（271288.59）
        if self.game.progressive_amount < 271288.59:
            self.game.progressive_amount = 271288.59

        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")
        save_jackpot(self.game.progressive_amount)
        return bonus

    def update_jackpot(self):
        jackpot_cost = 2.5 if self.game.jackpot_bet else 0
        total = self.game.ante + self.game.bonus3 + self.game.street3 + self.game.street4 + self.game.street5
        rate = 0.001
        self.game.progressive_amount += total * rate + jackpot_cost * 0.95
        if self.game.progressive_amount < 271288.59:
            self.game.progressive_amount = 271288.59
        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")
        save_jackpot(self.game.progressive_amount)

    # ---------- 重置 ----------
    def reset_bets(self):
        self.ante_var.set("0")
        self.bonus3_var.set("0")
        self.street3_var.set("0")
        self.street4_var.set("0")
        self.street5_var.set("0")
        self.jackpot_bet_var.set(0)
        self.status_label.config(text="已重置所有下注金额")
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.ante_display.config(bg='#FFCDD2')
        self.bonus3_display.config(bg='#FFCDD2')
        self.after(500, lambda: self.ante_display.config(bg='white'))
        self.after(500, lambda: self.bonus3_display.config(bg='white'))

    def apply_last_bet(self):
        if self.last_bet is None:
            return
        ante = self.last_bet['ante']
        bonus3 = self.last_bet['bonus3']
        jack = self.last_bet['jackpot']

        if self.high_bet_mode:
            max_ante, max_bonus = 50000, 12500
            min_ante = 100
        else:
            max_ante, max_bonus = 10000, 2500
            min_ante = 10
        if ante < min_ante:
            ante = min_ante
        if ante > max_ante:
            ante = max_ante
        if bonus3 > max_bonus:
            bonus3 = max_bonus
        self.ante_var.set(str(ante))
        self.bonus3_var.set(str(bonus3))
        self.jackpot_bet_var.set(jack)
        self.status_label.config(text="已应用上次下注金额")
        self.ante_display.config(bg='#E8F5E9')
        self.bonus3_display.config(bg='#E8F5E9')
        self.after(800, lambda: self.ante_display.config(bg='white'))
        self.after(800, lambda: self.bonus3_display.config(bg='white'))

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
        self.community_label.config(text="公共牌")
        self.ante_var.set("0")
        self.bonus3_var.set("0")
        self.street3_var.set("0")
        self.street4_var.set("0")
        self.street5_var.set("0")
        self.jackpot_bet_var.set(self.last_jackpot_state)
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.progressive_display.config(bg=PANEL_BG)
        self.active_card_labels = []

        # 重新绑定下注事件
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.bonus3_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bonus3"))
        self.bonus3_display.bind("<Button-3>", lambda e: self.reset_single_bet("bonus3", e))
        self.jackpot_check.config(state=tk.NORMAL)
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
        return MississippiStudGUI(
            parent, actual_balance, actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("Mississippi Stud Poker")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = MississippiStudGUI(root, actual_balance, actual_user)
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
