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

from A_Tools.Progressive.secure_json import (
    DATA_PATH as _progressive_file,
    install_secure_json as _install_progressive_secure_json,
)
_install_progressive_secure_json()
del _install_progressive_secure_json

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont

# ==================== Progressive 七段显示器：7 位整数 + 2 位小数 ====================
class ProgressiveSevenSegmentReadout:
    """用 Canvas 多边形绘制七段数字，无须安装数码管字体。"""

    INTEGER_DIGITS = 7
    SEGMENTS = {
        '0': 'abcdef', '1': 'bc', '2': 'abdeg', '3': 'abcdg',
        '4': 'bcfg', '5': 'acdfg', '6': 'acdefg', '7': 'abc',
        '8': 'abcdefg', '9': 'abcdfg',
    }

    def __init__(self, canvas, width, height, fg='#FFE29A'):
        self.canvas = canvas
        self.width = float(width)
        self.height = float(height)
        self.foreground = fg
        self.background = '#08150F'
        self.inactive = '#243025'
        self.text = None
        self._tag = 'progressive_seven_segment_' + str(id(self))
        self._content_tag = self._tag + '_content'
        self._digit_items = []
        self._separator_items = []

    @classmethod
    def format_amount(cls, value):
        """整数按实际位数居中，不为前置零留空；固定两位小数。"""
        from decimal import Decimal, ROUND_HALF_UP
        amount = Decimal(str(value).replace('$', '').replace(',', '').strip())
        if not amount.is_finite():
            raise ValueError('Progressive amount must be finite')
        amount = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        sign = '−' if amount < 0 else ''
        integer, fraction = format(abs(amount), '.2f').split('.')
        groups = [integer[max(0, i-3):i] for i in range(len(integer), 0, -3)]
        return '$' + sign + ','.join(reversed(groups)) + '.' + fraction

    @staticmethod
    def _polygons():
        def horizontal(y):
            return ((.18, y), (.82, y), (.96, y+.09),
                    (.82, y+.18), (.18, y+.18), (.04, y+.09))

        def vertical(x, y):
            return ((x+.09, y), (x+.18, y+.12), (x+.18, y+.68),
                    (x+.09, y+.80), (x, y+.68), (x, y+.12))

        return dict(a=horizontal(0), b=vertical(.82, .15),
                    c=vertical(.82, 1.05), d=horizontal(1.82),
                    e=vertical(0, 1.05), f=vertical(0, .15),
                    g=horizontal(.91))

    def set_amount(self, value):
        text = self.format_amount(value)
        if text == self.text:
            return
        previous = self.text
        self.text = text
        if previous is None or len(previous) != len(text) or ('−' in previous) != ('−' in text):
            self._build()
        else:
            self._paint_digits()

    def resize(self, width, height):
        width, height = float(width), float(height)
        if (width, height) != (self.width, self.height):
            self.width, self.height = width, height
            if self.text is not None:
                self._build()

    def _build(self):
        c = self.canvas
        c.delete(self._tag)
        self._digit_items = []
        self._separator_items = []
        c.create_rectangle(0, 0, self.width, self.height,
                           fill=self.background, outline='#4A5B3C', width=1,
                           tags=self._tag)
        padding = min(4.0, self.height / 10.0)
        # 只计算实际显示的字符；未使用的整数位不会占据宽度。
        # 每位数字宽度相同；千位用撇形 DP，小数分隔仍用圆点。
        advances = [1.20 if ch in self.SEGMENTS else .85 if ch == '$' else
                    .36 if ch in '.,' else .65 for ch in self.text]
        units = sum(advances) - .20
        digit_width = min(max(1.0, self.width-2*padding) / units,
                          max(1.0, self.height-2*padding) * .72)
        digit_height = min(max(1.0, self.height-2*padding), digit_width / .58)
        x = (self.width-units*digit_width) / 2.0
        y = (self.height-digit_height) / 2.0
        shapes = self._polygons()
        for char, advance in zip(self.text, advances):
            if char in self.SEGMENTS:
                items = {}
                for segment, points in shapes.items():
                    coordinates = [v for px, py in points
                                   for v in (x+px*digit_width, y+py*digit_height/2.0)]
                    items[segment] = c.create_polygon(
                        *coordinates, fill=self.inactive, outline='',
                        tags=(self._tag, self._content_tag, 'progressive_digit'))
                self._digit_items.append(items)
            elif char == ',':
                # 独立于数字单元的撇形千位分隔符，向左下方收尖；不是圆点。
                mark_x = x + advance*digit_width*.12
                mark_width = advance*digit_width*.74
                points = ((.45, .78), (1.0, .80), (.83, .89),
                          (.09, 1.0), (0, .97), (.41, .86))
                coordinates = [v for px, py in points
                               for v in (mark_x+px*mark_width, y+py*digit_height)]
                item = c.create_polygon(*coordinates, fill=self.foreground, outline='',
                                        tags=(self._tag, self._content_tag, 'progressive_modified_dp',
                                              'progressive_thousands_separator'))
                self._separator_items.append((len(self._digit_items), item))
            elif char == '.':
                diameter = max(1.0, digit_width * .18)
                dot_x = x + (advance*digit_width-diameter)/2.0
                c.create_oval(dot_x, y+digit_height-diameter,
                              dot_x+diameter, y+digit_height,
                              fill=self.foreground, outline='',
                              tags=(self._tag, self._content_tag, 'progressive_decimal'))
            elif char == '−':
                c.create_rectangle(x, y+digit_height*.46,
                                   x+digit_width*.48, y+digit_height*.54,
                                   fill=self.foreground, outline='',
                                   tags=(self._tag, self._content_tag))
            else:
                # 货币符号的右边紧邻首位数字，不夹带空槽。
                c.create_text(x+advance*digit_width-1, y+digit_height*.53,
                              text='$', anchor='e', fill=self.foreground,
                              font=('Arial', -max(8, round(digit_height*.78)), 'bold'),
                              tags=(self._tag, self._content_tag, 'progressive_currency'))
            x += advance*digit_width
        self._paint_digits()
        # 根据实际字体和图形边界，把钱符号及整串金额一起居中。
        bounds = c.bbox(self._content_tag)
        if bounds is not None:
            c.move(self._content_tag, (self.width-bounds[0]-bounds[2])/2.0, 0)

    def _paint_digits(self):
        digits = (char for char in self.text if char in self.SEGMENTS)
        for char, items in zip(digits, self._digit_items):
            active = self.SEGMENTS[char]
            for segment, item in items.items():
                self.canvas.itemconfigure(
                    item, state='normal',
                    fill=self.foreground if segment in active else self.inactive)


class ProgressiveSevenSegmentDisplay(tk.Canvas):
    """绑定原有 StringVar，金额更新时立即点亮正确的七段数字。"""

    INTEGER_DIGITS = 7

    def __init__(self, master, textvariable, font=('Arial', 20, 'bold'),
                 bg='#F2E6C9', fg='#A88100', **kwargs):
        self._variable = textvariable
        self._closed = False
        kwargs.setdefault('width', 300)
        kwargs.setdefault('highlightthickness', 0)
        kwargs.setdefault('bd', 0)
        super().__init__(master, bg=bg, **kwargs)
        size = font[1] if isinstance(font, (tuple, list)) and len(font) > 1 else 20
        pixels = abs(size) if size < 0 else size*self.winfo_fpixels('1p')
        if 'height' not in kwargs:
            self.configure(height=max(28, min(44, round(pixels*1.3))))
        self._readout = ProgressiveSevenSegmentReadout(
            self, self.cget('width'), self.cget('height'), fg=fg)
        self._readout.set_amount(textvariable.get())
        self._trace = textvariable.trace_add('write', self._changed)
        self.bind('<Configure>', self._resized, add='+')
        self.bind('<Destroy>', self._on_destroy, add='+')

    @classmethod
    def _format_amount(cls, value):
        return ProgressiveSevenSegmentReadout.format_amount(value)

    def _changed(self, *_):
        if not self._closed:
            self._readout.set_amount(self._variable.get())

    def set_amount_immediately(self, value):
        """大奖扣款时同步显示余额，保留原有派彩动画接口。"""
        if not self._closed:
            self._variable.set(value)

    def _resized(self, event):
        if event.widget is self and not self._closed:
            self._readout.resize(event.width, event.height)

    def _on_destroy(self, event):
        if event.widget is not self or self._closed:
            return
        self._closed = True
        try:
            self._variable.trace_remove('write', self._trace)
        except tk.TclError:
            pass
# ==================== Progressive 七段显示器结束 ====================


import random
import json
import os
import math
import secrets
import subprocess, sys
import time
from itertools import product, combinations
from collections import Counter

# =========================================================
# 基础数据（取自 Wild_Five_Card_Poker）
# =========================================================
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

BLIND_PAYOUT = {
    10: 100,   # 五条
    9: 50,     # 同花大顺
    8: 10,     # 同花顺
    7: 5,      # 四条
    6: 3,      # 葫芦
    5: 2,      # 同花
    4: 1,      # 顺子
}

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
# Progressive 文件加载与保存 (Key: 'Wild_Progressive_2.50')
# =========================================================
def load_wild_jackpot():
    path = str(_progressive_file)
    default_jackpot = 271288.59
    if not os.path.exists(path):
        return True, default_jackpot
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for game_key in ('Wild_Progressive_2.50', 'Progressive_2.50'):
                for item in data:
                    if item.get('Games') == game_key:
                        return False, float(item.get('jackpot', default_jackpot))
    except Exception:
        return True, default_jackpot
    return True, default_jackpot

def save_wild_jackpot(jackpot):
    path = str(_progressive_file)
    data = []
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = []
    found = False
    for item in data:
        if item.get('Games') == 'Wild_Progressive_2.50':
            item['jackpot'] = jackpot
            found = True
            break
    if not found:
        data.append({"Games": "Wild_Progressive_2.50", "jackpot": jackpot})
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# =========================================================
# 牌局历史日志（Wild Five Card Poker）
# =========================================================
def wild_five_log_path() -> str:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Wild_Five_Card_Poker.json")

def save_wild_five_history(deck, player_initial_cards, dealer_initial_cards,
                           player_final_cards, dealer_final_cards,
                           public_cards, player_discard=None, dealer_discard=None,
                           result_info=None):
    log_path = wild_five_log_path()
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

    # 读取已有数据
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

    # 生成 game_id
    max_id = 0
    for rec in data["history"]:
        if "game_id" in rec and isinstance(rec["game_id"], int):
            if rec["game_id"] > max_id:
                max_id = rec["game_id"]
    new_game_id = max_id + 1

    stats = data["history_record"]
    stats["game"] += 1

    # 处理胜者统计（修正 fold 判断）
    winner = None
    if result_info:
        if "winner" in result_info:
            winner = result_info["winner"]
            if winner == "player":
                stats["player_win"] += 1
            elif winner == "dealer":
                stats["dealer_win"] += 1
            elif winner == "fold":
                stats["fold"] += 1
            elif winner == "push":
                stats["push"] += 1
        # 兼容旧版 fold 字段（如果有）
        elif result_info.get("fold", False):
            winner = "fold"
            stats["fold"] += 1

    # 构建记录，增加四个新字段
    record = {
        "game_id": new_game_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "deck_order": [str(c) for c in deck.full_deck],
        "cut_position": deck.cut_position,
        # 原始手牌
        "player_cards_ori": [str(c) for c in player_initial_cards],
        "dealer_cards_ori": [str(c) for c in dealer_initial_cards],
        # 最终最佳牌型（5张）
        "player_cards_aft": [str(c) for c in player_final_cards] if player_final_cards else [],
        "dealer_cards_aft": [str(c) for c in dealer_final_cards] if dealer_final_cards else [],
        # 公共牌及弃牌信息
        "public_cards": [str(c) for c in public_cards],
        "player_discard": str(player_discard) if player_discard else None,
        "dealer_discard": str(dealer_discard) if dealer_discard else None,
        "result": result_info if result_info else {}
    }
    if winner is not None:
        record["result"]["winner"] = winner

    data["history"].append(record)

    # 保留最近50局
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
            return "JOKER"
        return f"{self.rank}{self.suit}"

    def __eq__(self, other):
        return isinstance(other, Card) and self.suit == other.suit and self.rank == other.rank and self.is_joker == other.is_joker

    def __hash__(self):
        return hash((self.suit, self.rank, self.is_joker))

def card_copy(card):
    new_card = Card(card.suit, card.rank)
    for attr in ('source', 'deal_index', 'is_public', 'is_discard'):
        if hasattr(card, attr):
            setattr(new_card, attr, getattr(card, attr))
    return new_card

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

# =========================================================
# 手牌评估（Wild Five Card Poker）
# =========================================================
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

    for idx_pos, card_idx in enumerate(joker_indices):
        trial[card_idx] = cards[card_idx]

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
    """
    庄家自动弃牌决策（优化版）
    逻辑顺序：
    1. 若已是顺子、同花、葫芦、同花顺、同花大顺、五条 → 不弃
    2. 若有四张同花（含Joker） → 弃异花色最小牌
    3. 若有“外顺听牌”（四张连续且两端可补牌，例如2-3-4-5或10-J-Q-K） → 弃掉不在四连张中的第五张牌
    4. 若已有对子、两对、三条、四条 → 弃最小单张
    5. 默认 → 弃最小非Joker牌
    """
    # 1. 已为强牌，不弃
    rank_name = best_hand_from_cards(cards)[0]
    made_hands = {"顺子", "同花", "葫芦", "同花顺", "同花大顺", "五条"}
    if rank_name in made_hands:
        return None

    # 2. 四张同花（含Joker）→ 弃异花色
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

    # 3. outside straight（四张连续，且非A-2-3-4或J-Q-K-A，因为A=14天然排除）
    # 获取所有非Joker牌的点数（去重）
    values = [c.value for c in cards if not c.is_joker]
    unique_vals = sorted(set(values))
    four_straight_vals = None
    for i in range(len(unique_vals) - 3):
        if unique_vals[i + 3] - unique_vals[i] == 3:
            four_straight_vals = set(unique_vals[i:i + 4])
            break
    if four_straight_vals:
        # 弃掉不在这四张连续牌中的非Joker牌
        discard_candidates = [c for c in cards if not c.is_joker and c.value not in four_straight_vals]
        if discard_candidates:
            return min(discard_candidates, key=lambda c: c.value)
        # 如果无多余非Joker（即所有非Joker都在四连中），则不可能，因为手牌只有5张

    # 4. 已有对子/两对/三条/四条 → 弃最小单张
    freq = Counter(c.value for c in cards if not c.is_joker)
    counts = sorted(freq.values(), reverse=True)
    if counts and ((counts[0] == 2 and counts.count(2) >= 2) or counts[0] in (3, 4)) and len([v for v in counts if v == 1]) >= 1:
        singles = [c for c in cards if freq.get(c.value, 0) == 1 and not c.is_joker]
        if singles:
            return min(singles, key=lambda c: c.value)
        return min(cards, key=lambda c: c.value if not c.is_joker else 100)

    # 5. 默认：弃最小非Joker牌
    singles = [c for c in cards if freq.get(c.value, 0) == 1 and not c.is_joker]
    if singles:
        return min(singles, key=lambda c: c.value)
    return min(cards, key=lambda c: c.value if not c.is_joker else 100)

# =========================================================
# 游戏逻辑类（Wild Five Card Poker）
# =========================================================

ROOT_BG = "#1b3d31"
CYAN = "#007502"
TEXT = "#ffffff"
RED = "#ff2a23"
BLACK = "#050505"
DARK_BLUE = "#173f66"
GOLD = "#D4AF37"
PANEL_BG = "#F2E6C9"
HEADER_BG = "#D8B46A"
TITLE_FG = "#2A1B08"


class WildFivePokerGame:
    """Wild 原有规则的双手牌版本；实际取牌顺序与动画共用 deal_sequence。"""
    SEATS = ('Player1', 'Player2')
    MIN_PROGRESSIVE = 271288.59

    def __init__(self):
        self.progressive_amount = load_wild_jackpot()[1]
        self.min_progressive = self.MIN_PROGRESSIVE
        self.reset_game()

    @staticmethod
    def empty_bet():
        return dict(ante=0.0, blind=0.0, original_five=0.0,
                    public_pair=0.0, jackpot=0.0, play=0.0)

    def reset_game(self):
        self.deck = None
        self.deal_sequence = []
        self.hands = {s: [] for s in self.SEATS}
        self.initial_hands = {s: [] for s in self.SEATS}
        self.dealer_hand = []
        self.dealer_initial_hand = []
        self.public_cards = []
        self.discards = {s: None for s in self.SEATS}
        self.dealer_discard = None
        self.bets = {s: self.empty_bet() for s in self.SEATS}
        self.decisions = {s: 'inactive' for s in self.SEATS}
        self.stage = 'betting'
        self.settlement = None
        self.refunded_bets = {}

    def start_round(self, bets, balance, high_bet_mode=False):
        if self.stage != 'betting':
            raise ValueError('本局尚未结束。')
        minimum, maximum, side_max = (100, 50000, 12500) if high_bet_mode else (10, 10000, 2500)
        prepared, refunded = {}, {}
        for seat in self.SEATS:
            b = {k: float(bets[seat].get(k, 0)) for k in self.empty_bet()}
            if any(not math.isfinite(v) or v < 0 for v in b.values()):
                raise ValueError('下注金额必须是有限的非负数。')
            if not b['ante']:
                if any(b.values()): refunded[seat] = dict(b)
                prepared[seat] = self.empty_bet()
                continue
            if not minimum <= b['ante'] <= maximum:
                raise ValueError(f'每手前注须为 ${minimum:,} 至 ${maximum:,}。')
            if b['blind'] != b['ante']:
                raise ValueError('盲注必须等于前注。')
            if any(b[k] > side_max for k in ('original_five', 'public_pair')):
                raise ValueError('边注超出限额。')
            if b['jackpot'] not in (0, 2.5):
                raise ValueError('累进大奖每手固定 $2.50。')
            if b['play']:
                raise ValueError('请在看牌和选牌后选择一倍或三倍加注。')
            prepared[seat] = b
        if not any(b['ante'] for b in prepared.values()):
            raise ValueError('请至少为一手牌下前注。')
        charged = round(sum(sum(b.values()) for b in prepared.values()), 2)
        # 留够每手最低一倍加注；三倍加注在点击时检查余额。
        reserve = sum(b['ante'] for b in prepared.values())
        if charged + reserve > balance:
            raise ValueError('余额不足以支付下注及每手最低一倍加注。')
        deck = Deck()
        hands, dealer, public = {s: [] for s in self.SEATS}, [], []
        active_seats = tuple(s for s in self.SEATS if prepared[s]['ante'])
        sequence = [(side, i) for i in range(5) for side in (*active_seats, 'Dealer')]
        sequence += [('Public', 0), ('Public', 1)]
        for side, index in sequence:
            card = deck.deal(1)[0]
            if side == 'Dealer': dealer.append(card)
            elif side == 'Public': public.append(card)
            else: hands[side].append(card)
        self.deck, self.hands, self.dealer_hand, self.public_cards = deck, hands, dealer, public
        self.initial_hands = {s: [card_copy(c) for c in h] for s, h in hands.items()}
        self.dealer_initial_hand = [card_copy(c) for c in dealer]
        self.deal_sequence, self.bets, self.refunded_bets = sequence, prepared, refunded
        self.decisions = {s: 'pending' if prepared[s]['ante'] else 'inactive' for s in self.SEATS}
        self.stage = 'dealing'
        return charged

    def decide(self, seat, action, balance, multiplier=1):
        if self.stage != 'decision' or self.decisions.get(seat) != 'pending':
            raise ValueError('这手牌当前不能操作。')
        if action not in ('play', 'fold') or multiplier not in (1, 3):
            raise ValueError('无效的决定。')
        cost = self.bets[seat]['ante'] * multiplier if action == 'play' else 0.0
        remaining = sum(self.bets[s]['ante'] for s in self.SEATS
                        if s != seat and self.decisions[s] == 'pending')
        if cost + remaining > balance:
            raise ValueError('余额不足；须为另一手保留最低一倍加注。')
        self.bets[seat]['play'] = cost
        self.decisions[seat] = action
        return cost

    def pool(self, side):
        hand = self.dealer_hand if side == 'Dealer' else self.hands[side]
        discard = self.dealer_discard if side == 'Dealer' else self.discards[side]
        pool = []
        for c in hand:
            if c != discard:
                cc = card_copy(c); cc.source = 'hand'; pool.append(cc)
        if discard is not None:
            for c in self.public_cards:
                cc = card_copy(c); cc.source = 'public'; pool.append(cc)
        return pool

    def dealer_qualifies(self):
        return bool(self.dealer_hand) and best_hand_from_cards(self.pool('Dealer'))[1] > 0

    def settle(self):
        if self.settlement is not None: return self.settlement
        if self.stage != 'showdown' or 'pending' in self.decisions.values():
            raise ValueError('两手完成决定并开牌后才能结算。')
        dealer_pool = self.pool('Dealer')
        dealer_high = best_hand_from_cards(dealer_pool)[1] == HAND_RANK['高牌']
        outcomes, total_bonus = {}, 0.0
        pool_amount = self.progressive_amount
        for seat in self.SEATS:
            if self.decisions[seat] == 'inactive': continue
            b, hand = self.bets[seat], self.initial_hands[seat]
            initial_rank = best_hand_with_joker(hand)[1]
            d = dict(ante=0.0, blind=0.0, play=0.0,
                     original_five=0.0, public_pair=0.0, bonus=0.0)
            original_mult = ORIGINAL_FIVE_PAYOUT.get(initial_rank, 0)
            public_mult = get_public_pair_payout(self.public_cards)
            if original_mult: d['original_five'] = b['original_five'] * (original_mult + 1)
            if public_mult: d['public_pair'] = b['public_pair'] * (public_mult + 1)
            if b['jackpot'] and not any(c.is_joker for c in hand):
                # 两手百分比奖金均使用同一局开始时的奖池金额。
                d['bonus'] = round({9: pool_amount, 8: pool_amount * .1,
                                    7: 1250.0, 6: 375.0, 5: 250.0}.get(initial_rank, 0.0), 2)
            total_bonus += d['bonus']
            if self.decisions[seat] == 'fold':
                winner, message = 'fold', '已弃牌'
            else:
                player_pool = self.pool(seat)
                comparison = compare_hands_best(player_pool, dealer_pool)
                if comparison > 0:
                    d['ante'], d['play'] = b['ante'] * 2, b['play'] * 2
                    blind_mult = BLIND_PAYOUT.get(best_hand_from_cards(player_pool)[1], 0)
                    d['blind'] = b['blind'] * (blind_mult + 1)
                    winner, message = 'player', '玩家获胜'
                elif comparison == 0:
                    for kind in ('ante', 'blind', 'play'): d[kind] = b[kind]
                    winner, message = 'push', '平局：主注退回'
                else:
                    winner, message = 'dealer', '庄家获胜'
                if dealer_high:
                    d['ante'] = b['ante']
                    message += '；庄家高牌，前注退回'
            d = {k: round(v, 2) for k, v in d.items()}
            returned = round(sum(d.values()), 2)
            outcomes[seat] = dict(winner=winner, message=message, details=d,
                                  returned=returned, stake=sum(b.values()),
                                  net=round(returned - sum(b.values()), 2))
        contribution = sum(sum(b[k] for k in ('ante','blind','play','original_five','public_pair')) * .001
                           + b['jackpot'] * .95 for b in self.bets.values())
        self.progressive_amount = round(max(self.MIN_PROGRESSIVE,
            max(self.MIN_PROGRESSIVE, pool_amount - total_bonus) + contribution), 2)
        self.stage = 'settled'
        self.settlement = dict(hands=outcomes, returned=round(sum(o['returned'] for o in outcomes.values()), 2))
        return self.settlement


class WildFivePokerUI(tk.Frame):
    WIDTH, HEIGHT = 1150, 750
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    DEAL_CARD_MS = 224 / .85
    DEAL_MOVE_MS = (128 / .75) / .85
    BET_CHIP_RADIUS = 16 * 4 / 3
    HOUSE_CHIP_POS = (575, 43)
    TABLE_GREEN = '#4b1e22'
    PROGRESSIVE_LAMP_WIDTH = 122.0 * .8
    ZONE_COLORS = {'Player1':'#2A5541','Player2':'#204536'}
    SEAT_NAMES = {'Player1': '玩家1', 'Player2': '玩家2', 'Dealer': '庄家手牌'}

    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = username, float(initial_balance)
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game = WildFivePokerGame()
        self.bets = {s: self.game.empty_bet() for s in self.game.SEATS}
        self.last_bet = None
        self.last_win = 0.0
        self.high_bet_mode = False
        self.selected_chip = 10.0
        self._jobs = set()
        self._closing = False
        self._credited = False
        self._return_persisted = False
        self._crediting = False
        self._restart_job = None
        self._restart_deadline = None
        self._side_resolved = set()
        self._motion_count = 0
        self._chip_serial = 0
        self._decision_busy = False
        self._settlement_started = False
        self._showdown_started = False
        self._public_cards_revealed = False
        self.visual_chips = {}
        self.lamps = {}
        self.last_round_snapshot = None
        self._history_available = False
        self._notice_level = 0.0
        self._notice_target = False
        self._notice_job = None
        self._notice_item = None
        self._notice_source = None
        self._notice_photo = None
        self._blind_seats = set()
        self._sorted_sides = set()
        self._face_photos, self._pil_cards, self._flip_photos = {}, {}, {}
        self.card_items, self.bet_spots, self.action_buttons = {}, {}, {}
        self._load_assets()
        self._create_widgets()
        self._refresh()
        self.bind('<Destroy>', self._on_destroy, add='+')

    @property
    def game_in_progress(self):
        return self.game.stage != 'betting' or self._motion_count > 0

    def _schedule(self, delay, callback, *args):
        def run():
            self._jobs.discard(job)
            if not self._closing:
                callback(*args)
        job = self.after(delay, run)
        self._jobs.add(job)
        return job

    def _cancel_jobs(self):
        for job in tuple(self._jobs):
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self._jobs.clear()

    def _on_destroy(self, event):
        if event.widget is self:
            self._closing = True
            self._cancel_jobs()
            self._unbind_enter()

    def _unbind_enter(self):
        binding=getattr(self,'_enter_binding',None)
        if binding:
            try:
                self.winfo_toplevel().unbind('<Return>',binding)
            except tk.TclError:
                pass
            self._enter_binding=None

    def _load_assets(self):
        size = (self.CARD_WIDTH, self.CARD_HEIGHT)
        self.current_poker_folder = ('Poker2' if self.current_poker_folder=='Poker1' else 'Poker1') if hasattr(self,'current_poker_folder') else random.choice(['Poker1','Poker2'])
        folder = self.current_poker_folder
        self.original_images = {}
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'A_Tools', 'Card', folder)
        suits = {'♠':'Spade', '♥':'Heart', '♦':'Diamond', '♣':'Club'}
        try:
            font = ImageFont.truetype('DejaVuSans-Bold.ttf', 23)
        except OSError:
            font = ImageFont.load_default()
        for key in ['back'] + [(s, r) for s in SUITS for r in RANKS] + [('JOKER','JOKER')]:
            filename = 'Background.png' if key == 'back' else 'JOKER-A.png' if key[0]=='JOKER' else f'{suits[key[0]]}{key[1]}.png'
            try:
                with Image.open(os.path.join(base, filename)) as source:
                    original = source.convert('RGBA')  # 保留 PNG 的 alpha，禁止转 RGB/铺白底。
                    self.original_images[key] = original.copy()
                    im = original.resize(size, Image.Resampling.LANCZOS)
            except (OSError, ValueError):
                im = Image.new('RGBA', size, (0,0,0,0))
                draw = ImageDraw.Draw(im)
                draw.rounded_rectangle((1,1,size[0]-2,size[1]-2), radius=6,
                    fill=DARK_BLUE if key=='back' else '#fffaf0',outline=GOLD,width=2)
                if key == 'back':
                    for y in range(12, 104, 12):
                        draw.line((10,y,70,y), fill=GOLD)
                else:
                    suit, rank = key
                    text = '★' if suit=='JOKER' else rank + suit
                    try:
                        draw.text((7,10), text, font=font, fill=RED if suit in '♥♦' else BLACK)
                        draw.text((14,62), '★' if suit=='JOKER' else suit, font=font, fill=RED if suit in '♥♦' else BLACK)
                    except UnicodeEncodeError:
                        draw.text((7,10), '★' if suit=='JOKER' else rank+suits[suit][0], font=font, fill=BLACK)
            self.original_images.setdefault(key,im.copy())
            self._pil_cards[key] = im
            self._face_photos[key] = ImageTk.PhotoImage(im, master=self)
        self._public_photos = {key:ImageTk.PhotoImage(im.resize(self.card_size('Public'),Image.Resampling.LANCZOS),master=self) for key,im in self._pil_cards.items()}

    def _text(self, x, y, text, size=12, color=TEXT, **kw):
        return self.canvas.create_text(x, y, text=text, fill=color, font=('Arial', size, 'bold'), **kw)

    def _create_widgets(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT, bg=ROOT_BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.control_buttons = {}
        self.selected_discards = {s: None for s in self.game.SEATS}
        self._card_origins = {}
        self._discard_photos = {}
        self._faded_photos = {}
        self._final_usage = {}
        self._hand_usage_keys = {}
        self._settled_card_photos = {}
        self._usage_owner = None
        self._hovered_usage_seat = None
        self._default_usage_owner = 'Dealer'
        self.canvas.bind('<Motion>', self._on_hand_usage_hover, add='+')
        self.canvas.bind('<Leave>', self._on_hand_usage_leave, add='+')
        c = self.canvas
        self._text(187,44,'王牌五张扑克',16,GOLD)
        c.create_rectangle(355,10,795,163,fill=self.TABLE_GREEN,outline='')
        self.title_items = {'Dealer': self._text(575,23,'庄家',16,PANEL_BG)}
        for seat,x0,x1 in (('Player1',22,566),('Player2',582,1128)):
            c.create_rectangle(x0,262,x1,617,fill=self.ZONE_COLORS[seat],outline='')
            self.title_items[seat] = self._text((x0+x1)/2,276,self.SEAT_NAMES[seat],20,PANEL_BG)
        self._draw_limit_table()
        self._text(957,44,'Wild Five Card Poker',14,GOLD)
        self._draw_progressive_panel()
        # 公共牌在三方手牌之间；保留加勒比的金边说明栏。
        c.create_rectangle(22,191,1128,258,fill=ROOT_BG,outline='#65784B',width=1)
        c.create_line(25,192,1125,192,fill='#E0C879',width=2)
        c.create_line(25,257,1125,257,fill='#0C241B',width=2)
        self._text(250,225,'前注与盲注相等',20,GOLD)
        self._text(897,225,'庄家不及格时退回前注',20,GOLD)
        # 公共牌区使用深绿圆角底板；两张牌的位置保持不变。
        c.create_polygon(
            490, 173, 644, 173,
            658, 173, 658, 187,
            658, 287, 658, 301,
            644, 301, 490, 301,
            476, 301, 476, 287,
            476, 187, 476, 173,
            smooth=True, splinesteps=16, fill='#234838',
            outline='#667B55', width=1, tags='public_zone')
        for seat,x0,x1 in (('Player1',22,566),('Player2',582,1128)):
            self._draw_wild_spot(seat,'original_five',x0+215,472,'原始5',40)
            self._draw_wild_spot(seat,'public_pair',x0+325,472,'公共对子',40)
            self._draw_wild_spot(seat,'ante',x0+215,575,'前注',40)
            self._draw_wild_spot(seat,'blind',x0+325,575,'盲注',40)
            self._text(x0+270,575,'＝',19,PANEL_BG)
            self._draw_progressive_lamp(seat,x0+70,473)
            self._draw_wild_spot(seat,'play',x0+105,575,'加注',40)
            # 与 Caribbean 相同的宽度、高度和字号，三项决定纵向排列。
            for action,top,caption,color in (
                ('play1',419,'下注1X','#397A48'),
                ('play3',488,'下注3X','#2B6639'),
                ('fold',557,'弃牌','#9B403A')):
                command = (lambda s=seat:self.fold_action(s)) if action=='fold' else (
                    lambda s=seat,m=(1 if action=='play1' else 3):self.raise_action(m,s))
                self.action_buttons[(seat,action)] = self.create_control_button(
                    x0+410,top,x1-15,top+58,caption,command,color,font_size=14,draw_shadow=False)
        self._draw_bottom_controls()
        for side in ('Dealer',*self.game.SEATS,'Public'):
            for index in range(2 if side=='Public' else 5):
                x,y = self.card_position(side,index)
                w,h = self.card_size(side)
                c.create_rectangle(x,y,x+w,y+h,outline='#B59C6A' if side=='Public' else '#7B9374',dash=(3,3),tags='card_slots')

    def _draw_chips(self):
        self.canvas.delete('rack')
        specs=([(100,BLACK),(500,'#FF7DDA'),(1000,TEXT),(5000,RED),(10000,'#00fbff'),(50000,'#00ffae')]
               if self.high_bet_mode else [(10,'#ffa500'),(25,'#00ff00'),(100,BLACK),(500,'#FF7DDA'),(1000,TEXT),(2500,RED)])
        self.chip_specs=specs
        diameter,gap=56,8
        start=(self.WIDTH-(len(specs)*diameter+(len(specs)-1)*gap))/2
        for i,(amount,color) in enumerate(specs):
            x=start+i*(diameter+gap)
            tag='rack_'+str(i)
            self.canvas.create_oval(x,646,x+56,702,fill='#182F25',
                outline=GOLD if amount==self.selected_chip else '#6C7850',width=3,tags=('rack',tag))
            self.canvas.create_oval(x+5,651,x+51,697,fill=color,outline=PANEL_BG,width=2,tags=('rack',tag))
            self._text(x+28,674,self._compact(amount),10,TEXT if color in (BLACK,RED) else BLACK,tags=('rack',tag))
            self.canvas.tag_bind(tag,'<Button-1>',lambda _e,a=amount:self.select_chip(a))

    @staticmethod
    def _compact(amount):
        """K/M筹码取两位有效数字并截断；有省略才加+，不改动真实金额。"""
        from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
        value=Decimal(str(amount)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        if value==Decimal('2.50'):return '2.50'
        if abs(value)>=1000000:
            divisor,suffix=Decimal(1000000),'M'
        elif abs(value)>=1000:
            divisor,suffix=Decimal(1000),'K'
        else:
            label=format(value,'f')
            return label.rstrip('0').rstrip('.') if '.' in label else label
        scaled=value/divisor
        precision=Decimal(1).scaleb(abs(scaled).adjusted()-1)
        shown=scaled.quantize(precision,rounding=ROUND_DOWN)
        label=format(shown,'f')
        if '.' in label:label=label.rstrip('0').rstrip('.')
        return label+suffix+('+' if shown!=scaled else '')

    def select_chip(self, amount):
        if self.game.stage == 'betting':
            self.selected_chip = amount
            self._draw_chips()

    def _status(self, message):
        # 记录阶段供调试，不在筹码下方绘制说明文字。
        self.current_status=message

    def _refresh(self):
        c = self.canvas
        c.itemconfigure(self.balance_item,text=f'余额: ${self.balance:,.2f}')
        total = sum(sum(b.values()) for b in self.bets.values())
        c.itemconfigure(self.total_item,text=f'本局下注: ${total:,.2f}' if total else f'上局返还: ${self.last_win:,.2f}')
        limits = ('$100','$50,000','$12,500') if self.high_bet_mode else ('$10','$10,000','$2,500')
        for item,value in zip(self.limit_value_items,limits): c.itemconfigure(item,text=value)
        self._render_chips()
        betting = self.game.stage=='betting' and self._motion_count==0
        self.set_control_button_state(self.clear_button,betting)
        self.set_control_button_state(self.repeat_button,betting and bool(self.last_bet))
        self.set_control_button_state(self.start_button,betting)
        restarting = self.game.stage in ('await_restart','returning','credit_pending','sweeping')
        c.itemconfigure(self.repeat_button,state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button,state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button,state='normal' if restarting else 'hidden')
        self.set_control_button_state(self.restart_button,self.game.stage in ('await_restart','credit_pending'))
        for (seat,action),button in self.action_buttons.items():
            enabled = self.game.stage=='decision' and not self._decision_busy and self.game.decisions[seat]=='pending'
            self.set_control_button_state(button,enabled)
        self._status('请点击一张牌选择弃牌，或保留全部手牌；再选择下注或弃牌。' if self.game.stage=='decision' else self.game.stage)

    def add_chip_to_bet(self, seat, kind):
        if self.game.stage!='betting' or self._motion_count: return
        new = {s:dict(b) for s,b in self.bets.items()}; b = new[seat]
        if kind=='jackpot': b[kind] = 0 if b[kind] else 2.5
        elif kind=='play': return  # 看牌后才选择一倍或三倍加注。
        else:
            main = kind in ('ante','blind')
            limit = (50000 if self.high_bet_mode else 10000) if main else (12500 if self.high_bet_mode else 2500)
            b[kind] = min(limit,b[kind]+self.selected_chip)
            if main: b['ante'] = b['blind'] = b[kind]
        self._apply_bet_layout(new)

    def reset_single_bet(self, seat, kind):
        if self.game.stage!='betting' or self._motion_count: return
        new = {s:dict(b) for s,b in self.bets.items()}
        if kind in ('ante','blind'): new[seat]['ante'] = new[seat]['blind'] = 0.0
        else: new[seat][kind] = 0.0
        self._apply_bet_layout(new)

    def reset_bets(self):
        if self.game.stage=='betting' and not self._motion_count:
            self._apply_bet_layout({s:self.game.empty_bet() for s in self.game.SEATS})

    def apply_last_bet(self):
        if self.game.stage=='betting' and not self._motion_count and self.last_bet:
            self._apply_bet_layout(self.last_bet)

    def toggle_high_bet_limits(self, event=None):
        if self.game.stage != 'betting' or self._motion_count:
            return
        if not self.high_bet_mode:
            password = simpledialog.askstring('高额下注', '请输入密码：', parent=self)
            if password is None:
                return
            if password.strip() != time.strftime('%H%M'):
                messagebox.showerror('错误','密码错误',parent=self)
                return
        self.high_bet_mode = not self.high_bet_mode
        self.reset_bets()
        self.last_bet = None
        self.selected_chip = 100 if self.high_bet_mode else 10
        self._draw_chips()
        self._refresh()

    def _persist_balance(self):
        try:
            if self.username and self.username!='Guest':
                update_balance_in_json(self.username,self.balance)
            if callable(self.on_balance_change):
                self.on_balance_change(float(self.balance))
        except Exception as exc:
            messagebox.showerror('余额保存失败',str(exc),parent=self)
            return False
        return True

    def card_position(self, side, index):
        if side=='Public': return 484+index*86,181
        if side=='Dealer':
            # 右侧预留38像素，最右张牌可从80像素宽横放为112像素宽。
            return 357+index*80,40
        # 两手略向两边展开，为同尺寸公共牌和横放弃牌留出中间空间。
        return (36 if side=='Player1' else 668)+index*85,294

    def start_game(self):
        if self.game.stage!='betting' or self._motion_count:return
        try:charged=self.game.start_round(self.bets,self.balance,self.high_bet_mode)
        except ValueError as exc:
            messagebox.showwarning('无法开始',str(exc),parent=self);return
        # 所有状态先锁定，避免 ENTER/快速双击重复扣款。
        self.game.stage='progressive'
        self._history_available=False
        self._close_card_sequence()
        self._fade_dealer_notice(False)
        self.balance=round(self.balance-charged,2)
        self.bets={s:dict(b) for s,b in self.game.bets.items()}
        self.last_bet={s:dict(b) for s,b in self.bets.items()}
        self._credited=False;self._return_persisted=False;self._settlement_started=False;self._side_resolved=set()
        self._cancel_restart_timer()
        self._blind_seats={s for s in self.game.SEATS if self.game.decisions[s]=='play'}
        self._sorted_sides=set();self._decision_busy=False;self._showdown_started=False
        self._public_cards_revealed = False
        self.canvas.delete('cards');self.card_items.clear();self._flip_photos.clear()
        self._load_assets()
        for side,item in self.title_items.items():
            self.canvas.itemconfigure(item,text='庄家' if side=='Dealer' else self.SEAT_NAMES[side])
        refunds=[]
        for seat,refunded in self.game.refunded_bets.items():
            self._set_lamp_mode(seat,'off')
            for kind,amount in refunded.items():
                chip=self.visual_chips.pop((seat,kind,'stake'),None)
                if chip:
                    refunds.append(dict(amount=chip['amount'],start=chip['xy'],
                        target=self._rack_position(),duration=440))
        # 下注阶段只摆放筹码，尚未扣余额；这里只扣合格手牌，退款不可重复加钱。
        self.game.stage='refunding' if refunds else 'progressive'
        self._persist_balance();self._refresh()
        self._run_chip_batch(refunds,self._start_progressive_lamps)

    def _start_progressive_lamps(self):
        self.game.stage='progressive'
        participants=[seat for seat in self.game.SEATS if self.bets[seat]['jackpot']]
        pending=set(participants)
        def filled(seat):
            pending.discard(seat)
            if not pending and self.game.stage=='progressive':
                self._collect_progressive_and_deal()
        for seat in self.game.SEATS:
            if seat in pending:
                self.lamps[seat]['filled_callback']=lambda s=seat:filled(s)
                self._set_lamp_mode(seat,'fill')
            else:self._set_lamp_mode(seat,'off')
        self._refresh()
        if not participants:self._schedule(0,self._collect_progressive_and_deal)

    def _deal_next(self, sequence, offset):
        if offset==len(sequence):
            # Wild 原版看牌时庄家和公共牌均盖住，玩家可先决定弃哪一张。
            reveal = [(s,i) for s in self.game.SEATS if self.game.decisions[s]=='pending' for i in range(5)]
            self._reveal_next(reveal,0,self._after_initial_reveal)
            return
        side,index = sequence[offset]
        x,y = self.card_position(side,index)
        photo = self._public_photos['back'] if side=='Public' else self._face_photos['back']
        item = self.canvas.create_image(575,52,image=photo,anchor='nw',tags='cards')
        self.card_items[(side,index)] = item
        def move(step=0):
            p = step/6
            self.canvas.coords(item,575+(x-575)*p,52+(y-52)*p)
            if step<6:
                self._schedule(round(self.DEAL_MOVE_MS*(step+1)/6)-round(self.DEAL_MOVE_MS*step/6),move,step+1)
            else:
                self._schedule(round(self.DEAL_CARD_MS)-round(self.DEAL_MOVE_MS),self._deal_next,sequence,offset+1)
        move()

    def _reveal_next(self, sequence, offset, complete):
        if offset==len(sequence): complete(); return
        side,index = sequence[offset]
        hand = self.game.dealer_hand if side=='Dealer' else self.game.public_cards if side=='Public' else self.game.hands[side]
        card, item = hand[index], self.card_items[(side,index)]
        x,y = self.card_position(side,index); w,h = self.card_size(side)
        def flip(step=0):
            width = max(1,round(w*abs(1-step/5)))
            source = self._pil_cards['back' if step<5 else self._card_image_key(card)]
            photo = ImageTk.PhotoImage(source.resize((width,h),Image.Resampling.LANCZOS),master=self)
            self._flip_photos[item] = photo
            self.canvas.itemconfigure(item,image=photo)
            self.canvas.coords(item,x+(w-width)/2,y)
            if step<10: self._schedule(32,flip,step+1)
            else:
                photos = self._public_photos if side=='Public' else self._face_photos
                self.canvas.itemconfigure(item,image=photos[self._card_image_key(card)])
                self._flip_photos.pop(item,None)
                self._reveal_next(sequence,offset+1,complete)
        flip()

    def _ready_for_decisions(self):
        for seat in self.game.SEATS:
            if self.game.decisions[seat]!='pending': continue
            self._update_hand_title(seat)
            for index in range(len(self.game.hands[seat])):
                item = self.card_items[(seat,index)]
                self._card_origins[(seat,index)] = tuple(self.canvas.coords(item))
                self.canvas.tag_bind(item,'<Button-1>',lambda _e,s=seat,i=index:self.toggle_player_discard(s,i))
                self.canvas.tag_bind(item,'<Enter>',lambda _e:self.canvas.configure(cursor='hand2'))
                self.canvas.tag_bind(item,'<Leave>',lambda _e:self.canvas.configure(cursor=''))
        self._enable_decisions()

    def play_action(self, seat='Player1'):
        self.raise_action(1,seat)

    def fold_action(self, seat='Player1'):
        self._decide(seat,'fold',1)

    def _decide(self, seat, action, multiplier=1):
        if self.game.stage!='decision' or self._decision_busy or self.game.decisions.get(seat)!='pending': return
        try: cost = self.game.decide(seat,action,self.balance,multiplier)
        except ValueError as exc:
            messagebox.showwarning('无法加注',str(exc),parent=self); return
        self._decision_busy = True
        self._update_hand_title(seat)
        self.balance = round(self.balance-cost,2)
        self.bets[seat]['play'] = self.game.bets[seat]['play']
        self._persist_balance(); self._refresh()
        def done():
            self._decision_busy = False; self._refresh(); self._maybe_showdown()
        def chips():
            if action=='fold':
                transfers = []
                for kind in ('ante','blind','play'):
                    chip = self.visual_chips.pop((seat,kind,'stake'),None)
                    if chip: transfers.append(dict(amount=chip['amount'],start=chip['xy'],target=self.HOUSE_CHIP_POS,duration=280))
                self._run_chip_batch(transfers,done)
            else:
                def arrived(): self._set_visual(seat,'play','stake',cost); done()
                self._animate_chip(cost,self._rack_position(),self.bet_spots[(seat,'play')]['center'],arrived)
        discard = self.game.discards[seat]
        if discard is not None: self._move_discard(seat,discard,chips)
        else: chips()

    def _maybe_showdown(self):
        if self._showdown_started or self._decision_busy or 'pending' in self.game.decisions.values(): return
        self._showdown_started = True; self.game.stage = 'showdown'; self._refresh()
        self.game.dealer_discard = dealer_discard_card(self.game.dealer_initial_hand)
        self._reveal_next([('Dealer',i) for i in range(5)],0,self._after_dealer_reveal)

    def _settle(self):
        if self._settlement_started: return
        self._settlement_started = True
        jackpot_before = self.game.progressive_amount
        result = self.game.settle()
        self.game.stage = 'settling'; self.last_win = result['returned']
        try: save_wild_jackpot(self.game.progressive_amount)
        except Exception as exc: messagebox.showerror('奖池保存失败',str(exc),parent=self)
        self._update_hand_title('Dealer')
        self._render_hand_usage()
        self._fade_dealer_notice(not self.game.dealer_qualifies())
        transfers, awards = [], []; round_id = time.time_ns()
        for seat,outcome in result['hands'].items():
            self._update_hand_title(seat)
            for kind in ('ante','blind','play','original_five','public_pair'):
                transfers.extend(self._outcome_transfers(seat,kind,self.game.bets[seat][kind],outcome['details'][kind]))
            bonus = outcome['details']['bonus']
            if bonus:
                self._set_lamp_mode(seat,'win'); awards.append((seat,bonus))
            info = dict(outcome,seat=seat,round_id=round_id,bets=dict(self.game.bets[seat]),
                        fold=self.game.decisions[seat]=='fold')
            try:
                save_wild_five_history(self.game.deck,self.game.initial_hands[seat],self.game.dealer_initial_hand,
                    sort_hand_for_display(best_hand_from_cards(self.game.pool(seat))[3]),
                    sort_hand_for_display(best_hand_from_cards(self.game.pool('Dealer'))[3]),
                    self.game.public_cards,self.game.discards[seat],self.game.dealer_discard,info)
            except Exception as exc: messagebox.showerror('历史记录保存失败',str(exc),parent=self)
        self._refresh()
        self._run_chip_batch(transfers,lambda:self._pay_progressive_awards(awards,jackpot_before))

    def _pay_progressive_awards(self, awards, pool_amount, index=0):
        if index==len(awards):
            # 扣款复制完成后，沿用原有奖池补底及本局贡献规则。
            self.progressive_amount_var.set(f'${self.game.progressive_amount:,.2f}')
            self._await_next_round()
            return
        seat,amount=awards[index]
        target=self.bet_spots[(seat,'jackpot')]['center']
        panel=self.progressive_panel
        origin=(panel.winfo_rootx()-self.canvas.winfo_rootx()+panel.winfo_width()/2,
                panel.winfo_rooty()-self.canvas.winfo_rooty()+panel.winfo_height()+20)
        frame_tag='jackpot_award_frame_'+seat
        # 空框先出现在上方奖池下方，数字填入后才移动整枚筹码。
        self._draw_chip(frame_tag,amount,*origin,rectangular=True,show_amount=False)
        self._motion_count+=1
        def copy_amount():
            remaining=round(pool_amount-amount,2)
            self.progressive_display.set_amount_immediately(f'${remaining:,.2f}')
            display=self.progressive_display
            start=(display.winfo_rootx()-self.canvas.winfo_rootx()+display.winfo_width()/2,
                   display.winfo_rooty()-self.canvas.winfo_rooty()+display.winfo_height()/2)
            number=self._text(*start,self._jackpot_label(amount),11,'#FFF0C3',tags='jackpot_amount_copy')
            def deliver_chip():
                self.canvas.delete(number);self.canvas.delete(frame_tag)
                self._motion_count-=1
                def arrived():
                    self._set_visual(seat,'jackpot','bonus',amount,target,True)
                    self._refresh()
                    self._schedule(200,self._pay_progressive_awards,awards,remaining,index+1)
                self._animate_chip(amount,origin,target,arrived,rectangular=True,duration=440)
            def move(step=0):
                progress=step/28
                eased=progress*progress*(3-2*progress)
                self.canvas.coords(number,start[0]+(origin[0]-start[0])*eased,
                    start[1]+(origin[1]-start[1])*eased)
                self.canvas.tag_raise(number)
                if step<28:
                    self._schedule(round(440*(step+1)/28)-round(440*step/28),move,step+1)
                else:
                    self._schedule(150,deliver_chip)
            move()
        # 生成空框 → 奖池扣款 → 复制奖金数字 → 整枚筹码移至中奖灯中心。
        self._schedule(150,copy_amount)

    def reset_game(self, auto_reset=False):
        # 兼容原入口；通常由全部筹码回到筹码区自动开放下一局。
        if self.game.stage=='betting':
            self._fade_dealer_notice(False)
            self.reset_bets()

    def on_close(self):
        if self._closing or self._crediting:return
        settled=self.game.stage in ('settling','await_restart','returning','credit_pending','sweeping')
        if self.game_in_progress and not settled:
            messagebox.showinfo('牌局进行中','请先完成两手牌的决定和结算。',parent=self)
            return
        # 已结算的返还金额必须先保存成功，才允许中断动画并关闭。
        if settled:
            if not self._credit_round_return():return
        elif not self._persist_balance():return
        self._closing=True
        self._cancel_restart_timer()
        self._cancel_jobs()
        self._unbind_enter()
        if callable(self.on_back):
            self.on_back(float(self.balance))
        else:
            self.winfo_toplevel().destroy()

    def _draw_limit_table(self):
        # 保留原加勒比的标题 + 三列限红表，改成深绿/金色。
        c = self.canvas
        x0,x1,y0 = 30,349,75
        c.create_rectangle(x0,y0,x1,181,fill=ROOT_BG,outline=GOLD,width=2,tags='limits')
        c.create_rectangle(x0,y0,x1,y0+29,fill=ROOT_BG,outline=GOLD,tags='limits')
        self._text((x0+x1)/2,y0+14,'下注上限',13,PANEL_BG,tags='limits')
        titles = ('前注最低','前注最高','边注最高')
        self.limit_value_items = []
        for col,title in enumerate(titles):
            left=x0+col*(x1-x0)/3
            right=x0+(col+1)*(x1-x0)/3
            c.create_rectangle(left,y0+29,right,y0+66,outline='#77906B',tags='limits')
            c.create_rectangle(left,y0+66,right,181,outline='#77906B',tags='limits')
            self._text((left+right)/2,y0+47,title,11,PANEL_BG,tags='limits')
            self.limit_value_items.append(self._text((left+right)/2,y0+86,'',12,GOLD,tags='limits'))
        c.tag_bind('limits','<Button-1>',self.toggle_high_bet_limits)
        c.tag_bind('limits','<Enter>',lambda _e:c.configure(cursor='hand2'))
        c.tag_bind('limits','<Leave>',lambda _e:c.configure(cursor=''))

    def _draw_progressive_panel(self):
        panel = tk.Frame(self.canvas,bg=ROOT_BG,highlightbackground=GOLD,highlightthickness=2)
        self.progressive_panel=panel
        self.canvas.create_window(957,128,window=panel,width=322,height=118)
        tk.Label(panel,text='累进大奖',font=('Arial',24,'bold'),
                 bg=ROOT_BG,fg='#F6D675').pack(fill=tk.X)
        self.progressive_amount_var = tk.StringVar(self,f'${self.game.progressive_amount:,.2f}')
        self.progressive_display = ProgressiveSevenSegmentDisplay(panel,self.progressive_amount_var,
            font=('Arial',24,'bold'),bg=ROOT_BG,fg='#FFE29A')
        self.progressive_display.pack(pady=10)

    def _register_spot(self, seat, kind, cx, cy, border, label, angle=0):
        c,tag = self.canvas,'spot_'+seat+'_'+kind
        self._text(cx,cy,label,14,PANEL_BG,angle=angle,tags=tag)
        self.bet_spots[(seat,kind)] = dict(tag=tag,center=(cx,cy),border=border)
        c.tag_bind(tag,'<Button-1>',lambda _e,s=seat,k=kind:self.add_chip_to_bet(s,k))
        c.tag_bind(tag,'<Button-3>',lambda _e,s=seat,k=kind:self.reset_single_bet(s,k))
        c.tag_bind(tag,'<Enter>',lambda _e:c.configure(cursor='hand2'))
        c.tag_bind(tag,'<Leave>',lambda _e:c.configure(cursor=''))

    def _draw_bottom_controls(self):
        c=self.canvas
        c.create_rectangle(0,625,1150,748,fill=ROOT_BG,outline='#6C7850',width=2,tags='controls')
        self.balance_item=self._text(10,665,'',18,TEXT,anchor='w',tags='controls')
        self.total_item=self._text(10,710,'',18,TEXT,anchor='w',tags='controls')
        self.clear_button=self.create_control_button(278,650,344,704,'清除',self.reset_bets,'#9B403A',font_size=11,draw_shadow=False)
        self._draw_chips()
        self.info_button=self.create_control_button(810,650,855,695,'?',self.show_game_instructions,DARK_BLUE,font_size=17,draw_shadow=False)
        self.repeat_button=self.create_control_button(862,638,1000,708,'重复下注',self.apply_last_bet,'#536A43',font_size=11,draw_shadow=False)
        self.start_button=self.create_control_button(1012,628,1138,720,'开牌',self.start_game,HEADER_BG,
            fg=TITLE_FG,font_size=14,subtext='Enter',subtext_font_size=10,draw_shadow=False)
        self.restart_button=self.create_control_button(862,638,1138,708,'再来一局(30)',self._return_all_chips,
            HEADER_BG,fg=TITLE_FG,font_size=17,draw_shadow=False)
        c.tag_bind(self.restart_button,'<Button-3>',self._inspect_completed_round)
        c.itemconfigure(self.restart_button,state='hidden')
        # 筹码区下方不放文字，也没有返回按钮。
        self._enter_binding=self.winfo_toplevel().bind('<Return>',lambda _e:
            self._return_all_chips() if self.game.stage in ('await_restart','credit_pending') else self.start_game(),add='+')

    def _sort_revealed_hands(self, sides, complete):
        """沿用 Wild 的鬼牌排序，只移动牌面，不改变发牌记录/庄家明牌。"""
        motions=[]
        for side in sides:
            hand=self.game.dealer_hand if side=='Dealer' else self.game.hands[side]
            if not hand or side in self._sorted_sides:
                continue
            ordered=sort_hand_for_display(hand)
            for target_index,card in enumerate(ordered):
                original_index=next(i for i,c in enumerate(hand) if c is card)
                item=self.card_items.get((side,original_index))
                if item is None:
                    continue
                start=self.canvas.coords(item)
                target=self.card_position(side,target_index)
                motions.append((item,start,target))
            self._sorted_sides.add(side)
        if not motions:
            complete()
            return
        def step(frame=0):
            fraction=frame/15
            for item,(x,y),(tx,ty) in motions:
                self.canvas.coords(item,x+(tx-x)*fraction,y+(ty-y)*fraction)
            if frame<15:
                self._schedule(64,step,frame+1)
            else:
                complete()
        step()

    def _after_initial_reveal(self):
        sides=[s for s in self.game.SEATS if self.game.decisions[s]=='pending']
        self._sort_revealed_hands(sides,self._ready_for_decisions)

    def _after_dealer_reveal(self):
        def sorted_dealer():
            if self.game.dealer_discard is not None:
                self._move_discard('Dealer',self.game.dealer_discard,self._reveal_public)
            else: self._reveal_public()
        self._sort_revealed_hands(['Dealer'],sorted_dealer)

    @staticmethod
    def shade_color(color, factor):
        color = color.lstrip('#')
        if len(color) != 6:
            return '#555555'
        values = [int(color[i:i + 2], 16) for i in (0, 2, 4)]
        values = [max(0, min(255, int(value * factor))) for value in values]
        return '#' + ''.join(f'{value:02x}' for value in values)

    def create_control_button(self, x0, y0, x1, y1, text, command, fill,
                              fg='white', font_size=11, subtext=None,
                              subtext_font_size=10, draw_shadow=True):
        tag = f'control_button_{len(self.control_buttons)}'
        shadow = self.canvas.create_rectangle(x0 + 5, y0 + 6, x1 + 5, y1 + 6,
                                              fill='#070605', outline='#070605',
                                              width=1, tags=(tag, 'controls')) if draw_shadow else None
        rim = self.canvas.create_rectangle(x0, y0, x1, y1,
                                           fill=self.shade_color(fill, 0.55),
                                           outline='#b7a58d', width=2,
                                           tags=(tag, 'controls'))
        face = self.canvas.create_rectangle(x0 + 4, y0 + 4, x1 - 4, y1 - 4,
                                            fill=fill,
                                            outline=self.shade_color(fill, 1.25),
                                            width=2, tags=(tag, 'controls'))
        highlight = self.canvas.create_line(x0 + 8, y0 + 8, x1 - 8, y0 + 8,
                                            fill=self.shade_color(fill, 1.45), width=2,
                                            tags=(tag, 'controls'))
        center_y = (y0 + y1) / 2 - 1
        text_y = center_y - 12 if subtext else center_y
        text_id = self.canvas.create_text((x0 + x1) / 2, text_y, text=text,
                                          font=('Arial', font_size, 'bold'), fill=fg,
                                          tags=(tag, 'controls'))
        subtext_id = None
        subtext_center_y = None
        if subtext:
            subtext_center_y = center_y + 16
            subtext_id = self.canvas.create_text((x0 + x1) / 2, subtext_center_y,
                                                 text=subtext,
                                                 font=('Arial', subtext_font_size, 'bold'),
                                                 fill=fg, tags=(tag, 'controls'))
        self.control_buttons[tag] = {
            'shadow': shadow, 'rim': rim, 'face': face, 'highlight': highlight,
            'text': text_id, 'subtext': subtext_id, 'command': command,
            'fill': fill, 'fg': fg, 'enabled': True, 'pressed': False,
            'center_y': text_y, 'subtext_center_y': subtext_center_y,
        }

        def enter(_event=None):
            button = self.control_buttons.get(tag)
            if button and button['enabled'] and not button['pressed']:
                self.canvas.itemconfigure(button['face'], fill=self.shade_color(button['fill'], 1.12))

        def leave(_event=None):
            button = self.control_buttons.get(tag)
            if button and button['enabled'] and not button['pressed']:
                self.canvas.itemconfigure(button['face'], fill=button['fill'])

        def press(_event=None):
            button = self.control_buttons.get(tag)
            if not button or not button['enabled']:
                return
            button['pressed'] = True
            self.canvas.itemconfigure(button['face'], fill=self.shade_color(button['fill'], 0.72))
            self.canvas.itemconfigure(button['highlight'], fill=self.shade_color(button['fill'], 0.8))
            x, _y = self.canvas.coords(button['text'])
            self.canvas.coords(button['text'], x, button['center_y'] + 2)
            if button.get('subtext'):
                sx, _sy = self.canvas.coords(button['subtext'])
                self.canvas.coords(button['subtext'], sx, button['subtext_center_y'] + 2)

        def release(_event=None):
            button = self.control_buttons.get(tag)
            if not button or not button['enabled'] or not button['pressed']:
                return
            button['pressed'] = False
            self.canvas.itemconfigure(button['face'], fill=button['fill'])
            self.canvas.itemconfigure(button['highlight'], fill=self.shade_color(button['fill'], 1.45))
            x, _y = self.canvas.coords(button['text'])
            self.canvas.coords(button['text'], x, button['center_y'])
            if button.get('subtext'):
                sx, _sy = self.canvas.coords(button['subtext'])
                self.canvas.coords(button['subtext'], sx, button['subtext_center_y'])
            button['command']()

        self.canvas.tag_bind(tag, '<Enter>', enter)
        self.canvas.tag_bind(tag, '<Leave>', leave)
        self.canvas.tag_bind(tag, '<ButtonPress-1>', press)
        self.canvas.tag_bind(tag, '<ButtonRelease-1>', release)
        return tag

    def set_control_button_state(self, tag, enabled):
        button = self.control_buttons.get(tag)
        if not button:
            return
        button['enabled'] = bool(enabled)
        button['pressed'] = False
        x, _y = self.canvas.coords(button['text'])
        self.canvas.coords(button['text'], x, button['center_y'])
        if button.get('subtext'):
            sx, _sy = self.canvas.coords(button['subtext'])
            self.canvas.coords(button['subtext'], sx, button['subtext_center_y'])
        if enabled:
            self.canvas.itemconfigure(button['face'], fill=button['fill'])
            self.canvas.itemconfigure(button['rim'], fill=self.shade_color(button['fill'], 0.55))
            self.canvas.itemconfigure(button['highlight'], fill=self.shade_color(button['fill'], 1.45))
            self.canvas.itemconfigure(button['text'], fill=button['fg'])
            if button.get('subtext'):
                self.canvas.itemconfigure(button['subtext'], fill=button['fg'])
        else:
            self.canvas.itemconfigure(button['face'], fill='#4a4743')
            self.canvas.itemconfigure(button['rim'], fill='#262422')
            self.canvas.itemconfigure(button['highlight'], fill='#66615b')
            self.canvas.itemconfigure(button['text'], fill='#9b9690')
            if button.get('subtext'):
                self.canvas.itemconfigure(button['subtext'], fill='#9b9690')

    def _gradient_polygon(self, points, top_color, bottom_color, tag):
        """在凸多边形内部逐行着色，产生金属斜面；完全由 Canvas 绘制。"""
        c=self.canvas
        vertices=list(zip(points[::2],points[1::2]))
        top=min(y for x,y in vertices);bottom=max(y for x,y in vertices)
        a=tuple(int(top_color[i:i+2],16) for i in (1,3,5))
        b=tuple(int(bottom_color[i:i+2],16) for i in (1,3,5))
        body=c.create_polygon(*points,fill=top_color,outline='',tags=tag)
        for y in range(math.ceil(top),math.floor(bottom)+1):
            hits=[]
            for (x1,y1),(x2,y2) in zip(vertices,vertices[1:]+vertices[:1]):
                if min(y1,y2)<=y<max(y1,y2):
                    hits.append(x1+(y-y1)*(x2-x1)/(y2-y1))
            if len(hits)>=2:
                f=(y-top)/max(1,bottom-top)
                color='#'+''.join(f'{round(v+(w-v)*f):02x}' for v,w in zip(a,b))
                c.create_line(min(hits),y,max(hits),y,fill=color,width=1,tags=tag)
        border=c.create_polygon(*points,fill='',outline='#F6CE68',width=2,tags=tag)
        return border

    def _draw_progressive_lamp(self, seat, cx, cy):
        c=self.canvas;tag='spot_'+seat+'_jackpot'
        # 正视的2D圆环，无投影、侧壁和椭圆透视。弧形文字位于红环内部。
        radius=self.PROGRESSIVE_LAMP_WIDTH/2
        scale=.8
        body=c.create_oval(cx-radius,cy-radius,cx+radius,cy+radius,
            fill='#B8303B',outline='#CD4550',width=2,tags=tag)
        center=c.create_oval(cx-27*scale,cy-27*scale,cx+27*scale,cy+27*scale,
            fill='#681923',outline='#781F28',width=2,tags=tag)
        segments=[]
        for i in range(16):
            segments.append(c.create_arc(cx-56*scale,cy-56*scale,cx+56*scale,cy+56*scale,start=i*22.5,
                extent=16,style=tk.ARC,width=4,outline='#A33038',tags=tag))
        for char,angle in zip('累进大奖',(132,104,76,48)):
            radians=math.radians(angle)
            self._text(cx+42*scale*math.cos(radians),cy-42*scale*math.sin(radians),char,10,PANEL_BG,
                angle=angle-90,tags=tag)
        label='每局$2.50'
        for index,char in enumerate(label):
            angle=220+100*index/(len(label)-1)
            radians=math.radians(angle)
            self._text(cx+42*scale*math.cos(radians),cy-42*scale*math.sin(radians),char,9,PANEL_BG,
                angle=angle-270,tags=tag)
        self.bet_spots[(seat,'jackpot')]=dict(tag=tag,center=(cx,cy),border=body)
        self.lamps[seat]=dict(body=body,center=center,segments=segments,mode='off',step=0,job=None)
        c.tag_bind(tag,'<Button-1>',lambda _e,s=seat:self.add_chip_to_bet(s,'jackpot'))
        c.tag_bind(tag,'<Button-3>',lambda _e,s=seat:self.reset_single_bet(s,'jackpot'))
        c.tag_bind(tag,'<Enter>',lambda _e:c.configure(cursor='hand2'))
        c.tag_bind(tag,'<Leave>',lambda _e:c.configure(cursor=''))
        self._set_lamp_mode(seat,'off')

    def _set_lamp_mode(self, seat, mode):
        lamp=self.lamps[seat]
        if lamp['mode']==mode:
            return
        if lamp['mode']=='spin':
            lamp['spin_step']=lamp['step']
        if lamp['job'] is not None:
            try:self.after_cancel(lamp['job'])
            except tk.TclError:pass
            self._jobs.discard(lamp['job']);lamp['job']=None
        lamp['mode']=mode
        if mode=='spin':lamp['step']=lamp.get('spin_step',lamp['step'])
        elif mode=='fill':
            lamp['filled']=set()
            lamp['fill_ticks']=0
            lamp['fill_colors']=[self.canvas.itemcget(item,'outline') for item in lamp['segments']]
        elif mode=='win':lamp['step']=0
        self._paint_lamp(seat)

    def _paint_lamp(self, seat):
        lamp=self.lamps[seat];mode=lamp['mode'];step=lamp['step'];c=self.canvas
        on=mode=='steady' or mode=='win' and step%2==0
        c.itemconfigure(lamp['body'],fill='#E33D48' if on else '#B8303B')
        c.itemconfigure(lamp['center'],fill='#681923')
        for i,item in enumerate(lamp['segments']):
            if mode=='spin':
                distance=(i-step)%16
                color={0:'#FFE6D9',1:'#FF9485',2:'#FF534F',3:'#E93B44'}.get(distance,'#9C2832')
            elif mode=='fill':
                color='#FF8B79' if i in lamp['filled'] else lamp['fill_colors'][i]
            else:color='#FF8B79' if on else '#A33038'
            c.itemconfigure(item,outline=color)
        if mode in ('spin','fill','win') and not self._closing:
            def tick():
                lamp['job']=None;lamp['step']+=1
                if mode=='fill':
                    lamp['filled'].add(lamp['step']%16)
                    lamp['fill_ticks']+=1
                    if lamp['fill_ticks']==16:
                        lamp['spin_step']=lamp['step']
                        self._set_lamp_mode(seat,'steady')
                        callback=lamp.pop('filled_callback',None)
                        if callback:callback()
                        return
                self._paint_lamp(seat)
            lamp['job']=self._schedule(250 if mode=='win' else 75,tick)

    def _chip_color(self, amount):
        return next((col for value,col in reversed(self.chip_specs) if amount>=value),HEADER_BG)

    @staticmethod
    def _jackpot_label(amount):
        value=round(float(amount),2)
        if abs(value)>=1000:return WildFivePokerUI._compact(value)
        return f'{value:.0f}' if value.is_integer() else f'{value:.2f}'

    def _draw_chip(self, tag, amount, x, y, rectangular=False, extra_tags=(), show_amount=True):
        c=self.canvas;tags=(tag,*extra_tags)
        if rectangular:
            # 大奖筹码只显示中奖数字，不带货币符号；整数省略 .00。
            label=self._jackpot_label(amount);width=max(96,10*len(label)+16)
            c.create_rectangle(x-width/2,y-18,x+width/2,y+18,fill='#731D2A',outline='#000000',width=1,tags=tags)
            if show_amount:self._text(x,y,label,11,'#FFF0C3',tags=tags)
        else:
            radius=self.BET_CHIP_RADIUS;color=self._chip_color(amount)
            c.create_oval(x-radius,y-radius,x+radius,y+radius,fill=color,outline='#000000',width=1,tags=tags)
            label=self._compact(amount)
            self._text(x,y,label,10 if len(label)>=5 else 12,TEXT if color in (BLACK,RED) else BLACK,tags=tags)

    def _render_chips(self):
        self.canvas.delete('bet_chips')
        # 本金先画、盈利后画；盈利位于原筹码左上方。
        for key,chip in sorted(self.visual_chips.items(),key=lambda kv:kv[0][2]!='stake'):
            seat,kind,role=key
            if chip['amount']>0:
                self._draw_chip('chip_'+seat+'_'+kind+'_'+role,chip['amount'],*chip['xy'],
                    rectangular=chip.get('rectangular',False),
                    extra_tags=('bet_chips',self.bet_spots[(seat,kind)]['tag']))

    def _rack_position(self, index=None, total=1):
        if index is not None:
            return 575+(index-(total-1)/2)*min(28,140/max(1,total-1)),674
        index=next((i for i,(value,_) in enumerate(self.chip_specs) if value==self.selected_chip),None)
        if index is None:return (575,674)
        width=len(self.chip_specs)*56+(len(self.chip_specs)-1)*8
        return (self.WIDTH-width)/2+index*64+28,674

    def _animate_chip(self, amount, start, target, complete=None, rectangular=False, duration=220):
        if not amount:
            if complete:complete()
            return
        self._motion_count+=1;self._chip_serial+=1
        tag=f'moving_chip_{self._chip_serial}'
        self._draw_chip(tag,amount,*start,rectangular,extra_tags=('moving_chips',))
        self._refresh()
        steps=max(1,round(duration/16));last=list(start)
        def frame(index):
            fraction=index/steps;eased=fraction*fraction*(3-2*fraction)
            x=start[0]+(target[0]-start[0])*eased
            y=start[1]+(target[1]-start[1])*eased
            self.canvas.move(tag,x-last[0],y-last[1]);last[:]=[x,y]
            self.canvas.tag_raise(tag)
            if index<steps:self._schedule(round(duration*(index+1)/steps)-round(duration*index/steps),frame,index+1)
            else:
                self.canvas.delete(tag);self._motion_count-=1
                if complete:complete()
                self._refresh()
        self._schedule(round(duration/steps),frame,1)

    def _run_chip_batch(self, transfers, complete):
        if not transfers:
            complete();return
        pending=[len(transfers)]
        def arrived(transfer):
            if transfer.get('arrive'):transfer['arrive']()
            pending[0]-=1
            if not pending[0]:complete()
        for transfer in transfers:
            self._animate_chip(transfer['amount'],transfer['start'],transfer['target'],
                lambda t=transfer:arrived(t),transfer.get('rectangular',False),transfer.get('duration',220))

    def _set_visual(self, seat, kind, role, amount, xy=None, rectangular=False):
        key=(seat,kind,role)
        if amount:
            self.visual_chips[key]=dict(amount=float(amount),xy=xy or self.bet_spots[(seat,kind)]['center'],rectangular=rectangular)
        else:self.visual_chips.pop(key,None)

    def _apply_bet_layout(self, new_bets):
        """提交下注设置；筹码从选中面额的位置飞入，清除时原路返回。"""
        previous=self.bets;self.bets={s:dict(b) for s,b in new_bets.items()}
        transfers=[]
        for seat in self.game.SEATS:
            for kind in self.game.empty_bet():
                old=previous[seat][kind];new=self.bets[seat][kind]
                delta=new-old
                if not delta:continue
                center=self.bet_spots[(seat,kind)]['center']
                if delta>0:
                    transfers.append(dict(amount=delta,start=self._rack_position(),target=center,
                        arrive=lambda s=seat,k=kind,a=new:self._set_visual(s,k,'stake',a)))
                else:
                    self._set_visual(seat,kind,'stake',new)
                    transfers.append(dict(amount=-delta,start=center,target=self._rack_position(),duration=440))
            self._set_lamp_mode(seat,'spin' if self.bets[seat]['jackpot'] else 'off')
        self._run_chip_batch(transfers,self._refresh)
        self._refresh()

    @staticmethod
    def hand_type_text(hand):
        return best_hand_from_cards(hand)[0]

    def _update_hand_title(self, side):
        name = '庄家' if side=='Dealer' else self.SEAT_NAMES[side]
        if self.game.settlement is not None or self._public_cards_revealed:
            hand = self.game.pool(side)
        else:
            hand = self.game.dealer_hand if side=='Dealer' else self.game.hands[side]
            discard = self.game.dealer_discard if side=='Dealer' else self.game.discards[side]
            hand = [card for card in hand if card != discard]
        # 四张有效手牌尚不足以组成牌型，公共牌翻开前仅显示原座位名称。
        caption = name
        if len(hand) >= 5:
            caption = f'{name} - {self.hand_type_text(hand)}'
        self.canvas.itemconfigure(self.title_items[side],text=caption)

    def _collect_progressive_and_deal(self):
        for seat in self.game.SEATS:
            chip=self.visual_chips.pop((seat,'jackpot','stake'),None)
            if chip:self._animate_chip(chip['amount'],chip['xy'],self.HOUSE_CHIP_POS,duration=280)
        self.game.stage='dealing';self._refresh()
        # 动画与实际取牌共用同一顺序，跳过未下注玩家，轮流发五轮手牌后发公共牌。
        self._deal_next(self.game.deal_sequence,0)

    def _enable_decisions(self):
        self.game.stage='decision';self._refresh();self._maybe_showdown()

    def _outcome_transfers(self, seat, kind, stake, returned):
        """本金留位，盈利派至左上；输注立即飞向统一庄家收筹码点，平局不动。"""
        if not stake:return []
        key=(seat,kind,'stake');center=self.bet_spots[(seat,kind)]['center']
        if returned<=0:
            chip=self.visual_chips.pop(key,None)
            return [dict(amount=chip['amount'],start=chip['xy'],target=self.HOUSE_CHIP_POS,duration=280)] if chip else []
        profit=round(returned-stake,2)
        if profit<=0:return []
        target=(center[0]-32,center[1]-30)
        return [dict(amount=profit,start=self.HOUSE_CHIP_POS,target=target,duration=440,
            arrive=lambda:self._set_visual(seat,kind,'profit',profit,target))]

    def _cancel_restart_timer(self):
        if self._restart_job is not None:
            try:self.after_cancel(self._restart_job)
            except tk.TclError:pass
            self._jobs.discard(self._restart_job)
            self._restart_job=None
        self._restart_deadline=None
        if hasattr(self,'restart_button'):
            self._restart_caption('再来一局')

    def _restart_caption(self, text):
        self.canvas.itemconfigure(self.control_buttons[self.restart_button]['text'],text=text)

    def _await_next_round(self):
        if self.game.stage!='settling':return
        self.game.stage='await_restart'
        # 到结算完成才冻结牌序；说明按钮不再提供这个入口。
        deck=self.game.deck
        self.last_round_snapshot=dict(full_deck=tuple(deck.full_deck),start_pos=deck.start_pos,
            images={key:im.copy() for key,im in self.original_images.items()})
        self._history_available=True
        self._cancel_restart_timer()
        jackpot_won=any(outcome['details']['bonus']>0 for outcome in self.game.settlement['hands'].values())
        if jackpot_won:
            self._restart_caption('再来一局')
        else:
            self._restart_deadline=time.monotonic()+30
        self._refresh()
        if not jackpot_won:self._restart_tick()

    def _restart_tick(self):
        self._restart_job=None
        if self.game.stage!='await_restart' or self._restart_deadline is None:return
        remaining=max(0,self._restart_deadline-time.monotonic())
        self._restart_caption(f'再来一局({math.ceil(remaining)})')
        if remaining<=0:
            self._return_all_chips()
            return
        self._restart_job=self._schedule(max(1,min(1000,math.ceil(remaining*1000))),self._restart_tick)

    def _inspect_completed_round(self, event=None):
        if self.game.stage!='await_restart':return
        self._cancel_restart_timer()
        self.show_card_sequence()

    def _return_all_chips(self):
        if self.game.stage=='credit_pending':
            self._complete_chip_return()
            return
        if self.game.stage!='await_restart':return
        self._cancel_restart_timer()
        self._history_available=False
        self._close_card_sequence()
        self.game.stage='returning'
        chips=list(self.visual_chips.values());self.visual_chips.clear();transfers=[]
        for index,chip in enumerate(chips):
            target=self._rack_position(index,len(chips))
            def arrived(chip=chip,target=target,index=index):
                # 筹码先回到筹码区，全部到位后才入账；向右移走的是扑克牌。
                self._draw_chip(f'returned_chip_{index}',chip['amount'],*target,
                    chip.get('rectangular',False),extra_tags=('returned_chips',))
            transfers.append(dict(amount=chip['amount'],start=chip['xy'],target=target,
                rectangular=chip.get('rectangular',False),duration=600,arrive=arrived))
        self._refresh();self._run_chip_batch(transfers,self._complete_chip_return)

    def _credit_round_return(self):
        """动画正常完成或用户关闭时共用；只加钱一次，保存失败可重试。"""
        if self._crediting:return False
        if self._return_persisted:return True
        self._crediting=True
        try:
            if not self._credited:
                self.balance=round(self.balance+self.last_win,2)
                self._credited=True
            self._return_persisted=self._persist_balance()
            return self._return_persisted
        finally:
            self._crediting=False

    def _complete_chip_return(self):
        if self.game.stage not in ('returning','credit_pending'):return
        self.game.stage='credit_pending'
        if not self._credit_round_return():
            self._refresh()
            return
        self.game.stage='sweeping'
        self._refresh()
        self.canvas.delete('returned_chips')
        self._sweep_all_cards()

    def _sweep_all_cards(self):
        """入账后，庄家和玩家的全部已显示扑克牌一起在0.2秒内向右移走。"""
        self._fade_dealer_notice(False)
        if not self.card_items:
            self._finish_round()
            return
        self._motion_count+=1
        distance=self.WIDTH+self.CARD_WIDTH
        previous=[0.0]
        def frame(index=0):
            fraction=index/13
            offset=distance*fraction*fraction*(3-2*fraction)
            self.canvas.move('cards',offset-previous[0],0)
            previous[0]=offset
            if index<13:
                self._schedule(round(200*(index+1)/13)-round(200*index/13),frame,index+1)
            else:
                self.canvas.delete('cards')
                self.card_items.clear();self._flip_photos.clear()
                self._motion_count-=1
                self._finish_round()
        frame()

    def _finish_round(self):
        if self.game.stage!='sweeping':return
        for seat in self.game.SEATS:self._set_lamp_mode(seat,'off')
        self._fade_dealer_notice(False)
        self.game.reset_game()
        self.selected_discards = {s:None for s in self.game.SEATS}
        self._card_origins.clear(); self._discard_photos.clear()
        self._faded_photos.clear(); self._final_usage.clear()
        self._hand_usage_keys.clear()
        self._settled_card_photos.clear()
        self._usage_owner = None
        self._hovered_usage_seat = None
        self._default_usage_owner = 'Dealer'
        self._public_cards_revealed = False
        self._history_available=False
        self.bets={s:self.game.empty_bet() for s in self.game.SEATS}
        for side,item in self.title_items.items():
            self.canvas.itemconfigure(item,text='庄家' if side=='Dealer' else self.SEAT_NAMES[side])
        self._refresh()

    def _close_card_sequence(self):
        current=getattr(self,'_sequence_window',None)
        if current is not None:
            try:
                if current.winfo_exists():current.destroy()
            except tk.TclError:pass
        self._sequence_window=None

    def _make_dealer_notice(self):
        """使用透明 RGBA 浮层，在牌桌内淡入，透明部分保留原始牌面。"""
        scale=3;width,height=210,48
        layer=Image.new('RGBA',(width*scale,height*scale),(0,0,0,0))
        draw=ImageDraw.Draw(layer)
        draw.rounded_rectangle((1,1,width*scale-2,height*scale-2),radius=10*scale,
            fill=(45,12,16,238),outline=(225,185,99,255),width=2*scale)
        candidates=['msyhbd.ttc','msyh.ttc','simhei.ttf','Arial Unicode.ttf',
            '/System/Library/Fonts/PingFang.ttc',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
            '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc']
        # Linux 字体由本机 fontconfig 定位；不下载字体，也不依赖额外素材。
        if sys.platform.startswith('linux'):
            try:
                result=subprocess.run(['fc-list','-f','%{file}\n',':lang=zh'],
                    capture_output=True,text=True,timeout=1,check=False)
                if result.returncode==0:
                    candidates[:0]=[line.strip() for line in result.stdout.splitlines() if line.strip()]
            except (OSError,subprocess.TimeoutExpired):pass
        font=None
        for path in candidates:
            try:font=ImageFont.truetype(path,22*scale);break
            except OSError:continue
        self._notice_text_item=None
        if font is not None:
            text='庄家不及格';box=draw.textbbox((0,0),text,font=font)
            draw.text(((width*scale-(box[2]-box[0]))/2-box[0],
                       (height*scale-(box[3]-box[1]))/2-box[1]),text,font=font,fill='#FFF1D1')
        else:
            # 极少数无可供 Pillow 使用的中文字体的系统，交由 Tk 原生字体回退。
            self._notice_text_item=self._text(575,111,'庄家不及格',16,'#FFF1D1',state='hidden',tags='dealer_notice')
        self._notice_source=layer.resize((width,height),Image.Resampling.LANCZOS)
        self._notice_item=self.canvas.create_image(575,111,state='hidden',tags='dealer_notice')

    def _draw_dealer_notice(self):
        alpha=self._notice_level
        if self._notice_item is None:return
        if alpha<=0:
            self.canvas.itemconfigure('dealer_notice',state='hidden');return
        layer=self._notice_source.copy()
        layer.putalpha(self._notice_source.getchannel('A').point(lambda value:round(value*alpha)))
        self._notice_photo=ImageTk.PhotoImage(layer,master=self)
        self.canvas.itemconfigure(self._notice_item,image=self._notice_photo,state='normal')
        self.canvas.tag_raise('dealer_notice')
        if self._notice_text_item is not None:
            background=(75,30,34);foreground=(255,241,209)
            color='#'+''.join(f'{round(a+(b-a)*alpha):02x}' for a,b in zip(background,foreground))
            self.canvas.itemconfigure(self._notice_text_item,state='normal',fill=color)
            self.canvas.tag_raise(self._notice_text_item)

    def _fade_dealer_notice(self, visible):
        target=1.0 if visible else 0.0
        if self._notice_target==visible and (self._notice_job is not None or self._notice_level==target):return
        if self._notice_job is not None:
            try:self.after_cancel(self._notice_job)
            except tk.TclError:pass
            self._jobs.discard(self._notice_job);self._notice_job=None
        self._notice_target=visible
        if self._notice_source is None:
            if not visible:return
            self._make_dealer_notice()
        start=self._notice_level
        def step(frame):
            self._notice_job=None
            self._notice_level=start+(target-start)*frame/12
            self._draw_dealer_notice()
            if frame<12:self._notice_job=self._schedule(25,step,frame+1)
        step(0)

    def show_card_sequence(self, event=None):
        if self.game.stage!='await_restart' or not self._history_available:return
        snapshot=self.last_round_snapshot
        if not snapshot:
            messagebox.showinfo('提示','尚无已结算牌局的牌序。',parent=self);return
        current=getattr(self,'_sequence_window',None)
        if current is not None and current.winfo_exists():current.lift();return
        # 原加勒比窗口：730×750，九张一排，切牌位置高亮，滚动显示53张原始牌序（含鬼牌）。
        win=tk.Toplevel(self);self._sequence_window=win
        win.title('上局牌序');win.geometry('730x750');win.resizable(0,0);win.configure(bg='#f0f0f0')
        cut_pos=snapshot['start_pos']
        tk.Label(win,text=f'上局切牌位置: {cut_pos+1}',font=('Arial',14,'bold'),bg='#f0f0f0').pack(pady=10)
        main_frame=tk.Frame(win,bg='#f0f0f0');main_frame.pack(fill=tk.BOTH,expand=True,padx=10,pady=5)
        scrollbar=ttk.Scrollbar(main_frame);scrollbar.pack(side=tk.RIGHT,fill=tk.Y)
        canvas=tk.Canvas(main_frame,bg='#f0f0f0',yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT,fill=tk.BOTH,expand=True);scrollbar.config(command=canvas.yview)
        content_frame=tk.Frame(canvas,bg='#f0f0f0');canvas.create_window((0,0),window=content_frame,anchor='nw')
        card_frame=tk.Frame(content_frame,bg='#f0f0f0');card_frame.pack(fill=tk.BOTH,expand=True,padx=20,pady=5)
        small_images={}
        for i,card in enumerate(snapshot['full_deck']):
            key=self._card_image_key(card)
            original=(snapshot['images'].get(key) or snapshot['images'].get((card.suit,card.rank))
                or self.original_images.get(key) or self.original_images['back'])
            small_images[i]=ImageTk.PhotoImage(original.resize((60,90),Image.Resampling.LANCZOS),master=win)
        win._card_images=small_images
        for row in range(math.ceil(len(snapshot['full_deck'])/9)):
            row_frame=tk.Frame(card_frame,bg='#f0f0f0');row_frame.pack(fill=tk.X)
            for col in range(9):
                idx=row*9+col
                if idx>=len(snapshot['full_deck']):break
                container=tk.Frame(row_frame,bg='#f0f0f0');container.grid(row=0,column=col,padx=5)
                bg='light blue' if idx==cut_pos else '#f0f0f0'
                tk.Label(container,image=small_images[idx],bg=bg,borderwidth=1,relief='solid').pack()
                tk.Label(container,text=str(idx+1),bg=bg,font=('Arial',9)).pack()
        content_frame.update_idletasks();canvas.configure(scrollregion=canvas.bbox('all'))

    def show_game_instructions(self):

        """Show the game manual in the shared card-based rules window."""

        import os

        import tkinter.font as tkfont

        from PIL import Image, ImageTk



        parent = self.winfo_toplevel()

        current = getattr(self, '_game_instruction_dialog', None)

        if current is not None:

            try:

                if current.winfo_exists():

                    current.lift()

                    current.focus_force()

                    return

            except tk.TclError:

                pass



        dialog = tk.Toplevel(parent)

        self._game_instruction_dialog = dialog

        dialog.title('王牌五张扑克 · 完整图解玩法')

        dialog.configure(bg='#faf5e8')

        dialog.resizable(False, False)

        dialog.transient(parent)



        width, height = 1000, 670

        parent.update_idletasks()

        px, py = parent.winfo_rootx(), parent.winfo_rooty()

        pw, ph = max(1, parent.winfo_width()), max(1, parent.winfo_height())

        dialog.geometry(f'{width}x{height}+{px + (pw-width)//2}+{py + (ph-height)//2}')



        manual_pages = [
            (
                '玩法',
                '了解游戏目标，以及一局从下注到结算的完整顺序。',
                [
                    [
                        '游戏目标',
                        '',
                        [
                            ('本局目标', '使用万能牌与公共牌组成最佳五张牌，与庄家比较并争取独立边注。'),
                        ],
                        [],
                    ],
                    [
                        '一局如何进行',
                        '',
                        [
                            ('玩家下注', '两手分别下注；前注与盲注相等，可选原始5、公共对子及累进大奖。'),
                            ('发牌顺序', '按玩家1、玩家2、庄家轮流发牌，跳过未下注玩家，共五轮，再发两张公共牌。'),
                            ('玩家决策', '可弃一张手牌，再选择 1X 或 3X 加注。'),
                            ('庄家开牌', '庄家亮牌并按策略决定是否弃一张牌。'),
                            ('结算', '组成最佳五张牌比大小，并分别结算边注。'),
                        ],
                        [],
                    ],
                    [
                        '一局完整流程',
                        '',
                        [
                            ('下注阶段', '前注：每局必须下注。\n盲注：自动等于前注金额，无需单独下注。\n原始五：可选边注，基于玩家初始 5 张手牌。\n公共对子：可选边注，基于 2 张公共牌。\n累进大奖：可选 $2.50 下注，按玩家原始 5 张手牌（不含 鬼牌）派彩。'),
                            ('发牌', '每轮按玩家1、玩家2、庄家顺序发牌，跳过未下注玩家，重复五轮后发两张公共牌。'),
                            ('玩家弃牌', '玩家先亮出 5 张手牌。\n点击某张牌 → 选中（下移十像素），再次点击可取消。\n选定后进入加注阶段。\n也可以选择不弃牌。'),
                            ('玩家加注', '选定弃牌（或不弃）后，必须选择加注倍数：\n1X 前注 → 加注金额 = 前注 × 1\n3X 前注 → 加注金额 = 前注 × 3'),
                            ('庄家行动', '庄家按策略自动弃掉 1 张手牌（或不弃）。\n弃牌仅在庄家亮牌后显示。'),
                            ('摊牌与比牌', '玩家1、玩家2分别与庄家比牌；弃一张时，用剩余四张与两张公共牌取最佳五张，不弃牌则保留原五张。\n先比牌型，再比点数；\n完全相同为平局。\n鬼牌按可组成的最佳牌型评估。'),
                            ('结算与再来一局', '玩家赢 → 按赔付表派彩；\n平局 → 前注 / 盲注 / 加注全额返还；\n玩家输 → 已下注金额输掉；\n30 秒无操作 → 自动收回筹码并开放下一局下注；累进大奖获奖时等候手动继续。'),
                        ],
                        [],
                    ],
                    [
                        '发牌顺序',
                        '',
                        [
                            ('公共牌', '五轮手牌发完后才发两张公共牌，背面朝下，摊牌时才翻开。'),
                            ('玩家手牌', '5 张，先背面朝下发出，发完后自动翻转并排序。'),
                            ('庄家手牌', '5 张，全程背面朝下，摊牌时才翻开。'),
                        ],
                        [],
                    ],
                    [
                        '玩家弃牌操作',
                        '',
                        [
                            ('选择弃牌', '点击一张手牌 → 下移十像素 → 表示已选中。\n再次点击同一张 → 取消选中。\n每次最多弃 1 张。'),
                            ('移动动画', '选择弃牌并加注后，该牌会移到所属手牌的最右侧，再旋转九十度横放。\n此后玩家牌池 = 剩余 4 张手牌 + 2 张公共牌。'),
                        ],
                        [],
                    ],
                    [
                        '庄家弃牌策略（自动）',
                        '',
                        [
                            ('已有成牌 · 不弃', '若庄家已组成顺子、同花、葫芦、同花顺、同花大顺、五条，则不弃牌。'),
                            ('四张同花', '若持有 4 张同花（含 鬼牌），弃掉异花色的最小牌。'),
                            ('外顺听牌', '若持有四张连续且两端可补牌的顺子（如 2-3-4-5 / 10-J-Q-K），弃掉不在四连中的第五张。'),
                            ('对子 / 两对 / 三条 / 四条', '保留对子结构，弃掉最小单张。'),
                            ('默认', '弃掉最小的非 鬼牌。'),
                        ],
                        [],
                    ],
                    [
                        '鬼牌 万能牌',
                        '',
                        [
                            ('任意替代', '鬼牌 可替代任意点数 / 花色。\n评估时会枚举所有可能，选取能使牌型最大的组合。'),
                            ('不可作为独立牌型', '含 鬼牌 的手牌仍按最终 5 张实体牌型计算。'),
                        ],
                        [],
                    ],
                ],
            ),
            (
                '下注 & 限红',
                '各项目限红如下。',
                [
                    [
                        '下注项目',
                        '',
                        [],
                        [
                            (
                                '下注项目与限红',
                                ['项目', '限红', '作用'],
                                [
                                    ['前注', '普通：$10–$10,000\n高额：$100–$50,000', '每局必须下注。'],
                                    ['盲注', '普通：$10–$10,000\n高额：$100–$50,000', '盲注自动等于前注金额。\n仅在玩家赢时按最终牌型派彩（详见「比牌与赔率」页）。'],
                                    ['原始五', '普通：每项最高$2,500\n高额：每项最高$12,500', '基于玩家初始 5 张手牌（不加入公共牌）派彩。'],
                                    ['公共对子', '普通：每项最高$2,500\n高额：每项最高$12,500', '基于 2 张公共牌的组合派彩。'],
                                    ['累进大奖', '每局$2.50', '固定 $2.50 下注。\n按玩家初始 5 张手牌（不含 鬼牌）派彩。'],
                                ],
                            ),
                        ],
                    ],
                ],
            ),
            (
                '获胜条件 & 赔率',
                '按下列表格核对各项判定条件、胜负结果及赔率。',
                [
                    [
                        '比牌规则',
                        '',
                        [],
                        [
                            (
                                '比牌与及格线',
                                ['判断', '规则'],
                                [
                                    ['庄家及格线', '庄家最终牌型为对子或以上及格；\n高牌不及格。'],
                                    ['组牌', '保留五张手牌，或用剩余四张与两张公牌选最佳五张。'],
                                    ['比大小', '先比牌型，再比点数；\n完全相同为平局。'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '盲注赔率表',
                        '',
                        [],
                        [
                            (
                                '',
                                ['玩家最终牌型', '赔率', '返还公式'],
                                [
                                    ['五条', '100 : 1', '盲注 × 101'],
                                    ['同花大顺', '50 : 1', '盲注 × 51'],
                                    ['同花顺', '10 : 1', '盲注 × 11'],
                                    ['四条', '5 : 1', '盲注 × 6'],
                                    ['葫芦', '3 : 1', '盲注 × 4'],
                                    ['同花', '2 : 1', '盲注 × 3'],
                                    ['顺子', '1 : 1', '盲注 × 2'],
                                    ['三条', '平局', '盲注 × 1'],
                                    ['两对', '平局', '盲注 × 1'],
                                    ['对子', '平局', '盲注 × 1'],
                                    ['高牌', '平局', '盲注 × 1'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '原始五赔率表',
                        '',
                        [],
                        [
                            (
                                '',
                                ['初始牌型', '赔率', '返还公式'],
                                [
                                    ['五条', '1000 : 1', '下注 × 1001'],
                                    ['同花大顺', '500 : 1', '下注 × 501'],
                                    ['同花顺', '250 : 1', '下注 × 251'],
                                    ['四条', '100 : 1', '下注 × 101'],
                                    ['葫芦', '50 : 1', '下注 × 51'],
                                    ['同花', '25 : 1', '下注 × 26'],
                                    ['顺子', '10 : 1', '下注 × 11'],
                                    ['三条', '5 : 1', '下注 × 6'],
                                    ['两对', '5 : 1', '下注 × 6'],
                                    ['对子', '未中奖', '本金归庄'],
                                    ['高牌', '未中奖', '本金归庄'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '公共对子赔率表',
                        '',
                        [],
                        [
                            (
                                '',
                                ['公共牌组合', '赔率', '返还公式'],
                                [
                                    ['A - A', '23 : 1', '下注 × 24'],
                                    ['A - K（同花）', '19 : 1', '下注 × 20'],
                                    ['A - Q 或 A - J（同花）', '16 : 1', '下注 × 17'],
                                    ['A - K（非同花）', '11 : 1', '下注 × 12'],
                                    ['K-K / Q-Q / J-J', '8 : 1', '下注 × 9'],
                                    ['其中一张为 鬼牌', '6 : 1', '下注 × 7'],
                                    ['A - Q 或 A - J（非同花）', '4 : 1', '下注 × 5'],
                                    ['10-10 到 2-2（对子）', '2 : 1', '下注 × 3'],
                                    ['其他（无组合）', '未中奖', '本金归庄'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '累进大奖赔率表',
                        '',
                        [],
                        [
                            (
                                '',
                                ['情形／项目', '赔率／结算规则'],
                                [
                                    ['参与条件', '固定 $2.50 下注，且玩家原始 5 张手牌中不含 鬼牌。'],
                                    ['', '以玩家初始 5 张手牌评估牌型，不加入公共牌。'],
                                ],
                            ),
                            (
                                '',
                                ['初始牌型', '奖励'],
                                [
                                    ['皇家同花顺', '奖池 100%'],
                                    ['同花顺', '奖池 10%'],
                                    ['四条', '$1,250'],
                                    ['葫芦', '$375'],
                                    ['同花', '$250'],
                                    ['其他', '未中奖'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '庄家资格与主注结算',
                        '',
                        [],
                        [
                            (
                                '前注 / 加注结算',
                                ['获胜条件', '前注', '相关下注'],
                                [
                                    ['庄家高牌（不及格）', '前注退还', '盲注与加注仍按比牌结果'],
                                    ['庄家及格、玩家胜', '前注赢 1:1', '加注赢 1:1；\n盲注按最终牌型表'],
                                    ['平局', '前注退还', '盲注与加注退还'],
                                    ['庄家及格、玩家负', '前注输', '盲注与加注输'],
                                ],
                            ),
                        ],
                    ],
                ],
            ),
            (
                '牌型等级表',
                '牌型由强到弱排列；\n同级牌型继续比较相关点数。',
                [
                    [
                        '11 种牌型',
                        '下方图片展示牌型示例；\n同一牌型也可能由其他牌面组成。',
                        [],
                        [
                            (
                                '牌型与示例',
                                ['等级', '牌型', '说明', '牌例'],
                                [
                                    [
                                        '1',
                                        '五条',
                                        '四张同点 + 鬼牌',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', 'A'),
                                                ('♣', 'A'),
                                                ('♦', 'A'),
                                                ('♠', 'A'),
                                                ('JOKER', 'JOKER'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '2',
                                        '同花大顺',
                                        '同花色的 10-J-Q-K-A',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', 'A'),
                                                ('♥', 'K'),
                                                ('♥', 'Q'),
                                                ('♥', 'J'),
                                                ('♥', '10'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '3',
                                        '同花顺',
                                        '同花色顺子',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', '6'),
                                                ('♥', '7'),
                                                ('♥', '8'),
                                                ('♥', '9'),
                                                ('♥', '10'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '4',
                                        '四条',
                                        '四张同点',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', 'A'),
                                                ('♣', 'A'),
                                                ('♦', 'A'),
                                                ('♠', 'A'),
                                                ('♥', 'K'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '5',
                                        '葫芦',
                                        '三条 + 一对',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', 'A'),
                                                ('♣', 'A'),
                                                ('♦', 'A'),
                                                ('♥', 'K'),
                                                ('♠', 'K'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '6',
                                        '同花',
                                        '五张同花色',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♣', 'K'),
                                                ('♣', '10'),
                                                ('♣', '8'),
                                                ('♣', '7'),
                                                ('♣', '5'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '7',
                                        '顺子',
                                        '五张连续',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', '6'),
                                                ('♠', '7'),
                                                ('♦', '8'),
                                                ('♣', '9'),
                                                ('♠', '10'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '8',
                                        '三条',
                                        '三张同点',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', 'A'),
                                                ('♣', 'A'),
                                                ('♠', 'A'),
                                                ('♠', 'K'),
                                                ('♥', 'Q'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '9',
                                        '两对',
                                        '两组对子',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', 'A'),
                                                ('♣', 'A'),
                                                ('♦', 'K'),
                                                ('♠', 'K'),
                                                ('♥', '7'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '10',
                                        '对子',
                                        '一组对子',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', 'A'),
                                                ('♣', 'A'),
                                                ('♠', 'K'),
                                                ('♣', 'J'),
                                                ('♥', '7'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '11',
                                        '高牌',
                                        '无任何组合',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', 'A'),
                                                ('♣', 'K'),
                                                ('♦', 'Q'),
                                                ('♠', '9'),
                                                ('♥', '7'),
                                            ),
                                        ),
                                    ],
                                ],
                            ),
                        ],
                    ],
                    [
                        '同牌型如何分胜负',
                        '',
                        [
                            ('比较方法', '本游戏顺序：五条 ＞ 同花大顺 ＞ 同花顺 ＞ 四条 ＞ 葫芦 ＞ 同花 ＞ 顺子 ＞ 三条 ＞ 两对 ＞ 对子 ＞ 高牌。\n鬼牌 可代替任意点数或花色；\n按可组成的最佳五张牌型比较。\n同牌型再比关键点数与踢脚。'),
                        ],
                        [],
                    ],
                ],
            ),
            (
                '特别事项',
                '补充说明特殊牌、模式差异和金额结算方式。',
                [
                    [
                        '特别规则补充',
                        '',
                        [
                            ('需留意的规则', '鬼牌 是万能牌；\n牌型顺序包含五条与同花大顺，详见牌型等级表。'),
                        ],
                        [],
                    ],
                    [
                        '特殊下注规则',
                        '',
                        [
                            ('盲注', '自动'),
                        ],
                        [],
                    ],
                ],
            ),
        ]



        BG = '#faf5e8'

        HEADER = '#f1e7cd'

        SIDEBAR = '#f2e8d0'

        PANEL = '#fffdf7'

        PANEL_2 = '#f5ecd6'

        BORDER = '#c9b88a'

        GOLD = '#a8842c'

        GOLD_BAR = '#e7d36c'

        TEXT = '#3a2f1e'

        MUTED = '#7a6a50'

        font_name = getattr(self, 'cn_font', 'Microsoft YaHei UI')



        header = tk.Frame(dialog, bg=HEADER, height=76)

        header.pack(fill=tk.X, side=tk.TOP)

        header.pack_propagate(False)

        tk.Label(header, text='王牌五张扑克 · 完整图解玩法', font=(font_name, 20, 'bold'),

                 fg=GOLD, bg=HEADER, anchor='w', wraplength=795,

                 justify=tk.LEFT).place(x=24, y=6, width=795, height=41)

        tk.Label(header, text='玩法 · 下注 · 获胜条件 · 牌型 · 特别事项',

                 font=(font_name, 14), fg=MUTED, bg=HEADER, anchor='w').place(x=26, y=46)



        def close_dialog():

            try:

                self._game_instruction_dialog = None

            except Exception:

                pass

            try:

                dialog.destroy()

            except tk.TclError:

                pass



        tk.Button(header, text='关闭', command=close_dialog,

                  font=(font_name, 14, 'bold'), bg='#e8dcc0', fg=TEXT,

                  activebackground='#d9c895', relief=tk.FLAT, bd=0,

                  cursor='hand2').place(x=850, y=17, width=120, height=42)

        tk.Frame(dialog, bg=GOLD_BAR, height=3).pack(fill=tk.X, side=tk.TOP)



        body = tk.Frame(dialog, bg=BG)

        body.pack(fill=tk.BOTH, expand=True)

        sidebar = tk.Frame(body, bg=SIDEBAR, width=205)

        sidebar.pack(side=tk.LEFT, fill=tk.Y)

        sidebar.pack_propagate(False)

        tk.Label(sidebar, text='说明目录', font=(font_name, 16, 'bold'),

                 fg=GOLD, bg=SIDEBAR, anchor='w').pack(fill=tk.X, padx=18, pady=(17, 10))



        scroll_host = tk.Frame(body, bg=BG)

        scroll_host.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(scroll_host, bg=BG, highlightthickness=0, bd=0, yscrollincrement=36)

        scrollbar = tk.Scrollbar(scroll_host, orient=tk.VERTICAL, command=canvas.yview,

                                 bg='#ded3b7', troughcolor=BG, activebackground=GOLD_BAR,

                                 relief=tk.FLAT, bd=0, width=13)

        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 8), pady=10)

        content = tk.Frame(canvas, bg=BG)

        content_window = canvas.create_window((0, 0), window=content, anchor='nw')



        def sync_scrollregion(_event=None):

            canvas.configure(scrollregion=canvas.bbox('all'))



        def fit_content_width(event):

            canvas.itemconfigure(content_window, width=event.width)



        content.bind('<Configure>', sync_scrollregion)

        canvas.bind('<Configure>', fit_content_width)



        def add_rule(parent_frame, title, detail):

            row = tk.Frame(parent_frame, bg=PANEL)

            row.pack(fill=tk.X, padx=16, pady=5)

            tk.Frame(row, bg=GOLD_BAR, width=5).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 11))

            text_box = tk.Frame(row, bg=PANEL)

            text_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

            if title:
                tk.Label(text_box, text=title, font=(font_name, 15, 'bold'),

                         fg=TEXT, bg=PANEL, anchor='w', justify=tk.LEFT,

                         wraplength=650).pack(fill=tk.X)

            if detail:

                tk.Label(text_box, text=detail, font=(font_name, 14),

                         fg=MUTED, bg=PANEL, anchor='w', justify=tk.LEFT,

                         wraplength=650).pack(fill=tk.X, pady=(3, 0))



        def add_table(parent_frame, title, headers, rows):

            block = tk.Frame(parent_frame, bg=PANEL_2,

                             highlightbackground=BORDER, highlightthickness=1, bd=0)

            block.pack(fill=tk.X, padx=16, pady=8)

            if title:
                tk.Label(block, text=title, font=(font_name, 14, 'bold'),

                         fg=TEXT, bg=GOLD_BAR, anchor='w', justify=tk.LEFT,

                         wraplength=675, padx=11, pady=7).pack(fill=tk.X)

            grid = tk.Frame(block, bg=PANEL_2)

            grid.pack(fill=tk.X)

            count = max([len(headers)] + [len(row) for row in rows]) if rows else len(headers)

            table_font = tkfont.Font(family=font_name, size=14)

            minimums = []

            preferences = []

            for col in range(count):

                picture_width = max((len(row[col][1]) * 74 + 6

                                     for row in rows if col < len(row)

                                     and isinstance(row[col], (tuple, list))

                                     and len(row[col]) == 2 and row[col][0] == '__CARD_IMAGES__'),

                                    default=0)

                minimums.append(max(62, picture_width))

                text_width = max((table_font.measure(str(row[col]))

                                  for row in ([headers] if headers else []) + rows

                                  if col < len(row) and isinstance(row[col], str)), default=0)

                preferences.append(1 if picture_width else max(50, min(text_width, 260)))

            available = 700

            remaining = max(0, available - sum(minimums))

            total_preference = sum(preferences) or 1

            column_widths = [minimums[col] + remaining * preferences[col] // total_preference

                             for col in range(count)]

            if column_widths:

                column_widths[-1] += available - sum(column_widths)

            for col, width in enumerate(column_widths):

                grid.grid_columnconfigure(col, minsize=width)

            matrix = ([headers] if headers else []) + rows

            for r, row in enumerate(matrix):

                for c in range(count):

                    value = row[c] if c < len(row) else ''

                    head = bool(headers) and r == 0

                    bg = GOLD_BAR if head else (PANEL if r % 2 else '#fbf6e9')

                    fg = TEXT if head else MUTED

                    if isinstance(value, (tuple, list)) and len(value) == 2 and value[0] == '__CARD_IMAGES__':

                        image_cell = tk.Frame(grid, bg=bg, borderwidth=1, relief=tk.SOLID)

                        image_cell.grid(row=r, column=c, sticky='nsew')

                        game_dir = os.path.dirname(os.path.abspath(__file__))

                        search_roots = (game_dir, os.path.dirname(game_dir),

                                        os.path.dirname(os.path.dirname(game_dir)))

                        card_dir = next((os.path.join(root, 'A_Tools', 'Card', 'Poker1')

                                         for root in search_roots

                                         if os.path.isdir(os.path.join(root, 'A_Tools', 'Card', 'Poker1'))),

                                        os.path.join(search_roots[1], 'A_Tools', 'Card', 'Poker1'))

                        suits = {'♠': 'Spade', '♥': 'Heart', '♦': 'Diamond', '♣': 'Club'}

                        for suit, rank in value[1]:

                            filename = 'JOKER-A.png' if suit == 'JOKER' else f'{suits.get(suit, suit)}{rank}.png'

                            path = os.path.join(card_dir, filename)

                            try:

                                with Image.open(path) as source_image:

                                    card_width = 70

                                    card_height = max(1, round(source_image.height * card_width / source_image.width))

                                    small_image = source_image.resize((card_width, card_height), Image.LANCZOS)

                                photo = ImageTk.PhotoImage(small_image)

                                image_label = tk.Label(image_cell, image=photo, bg=bg, bd=0)

                                image_label.image = photo

                                image_label.pack(side=tk.LEFT, padx=2, pady=3)

                            except Exception:

                                # Keep the example cell image-only if an asset is unavailable.

                                tk.Label(image_cell, text='', bg='#fffdf7', width=3, height=2,

                                         borderwidth=1, relief=tk.SOLID).pack(side=tk.LEFT, padx=2, pady=3)

                    else:

                        tk.Message(grid, text=value, font=(font_name, 14, 'bold' if head else 'normal'),

                                   fg=fg, bg=bg, anchor='w', justify=tk.LEFT,

                                   width=max(42, column_widths[c] - 16),

                                   padx=7, pady=5, borderwidth=1,

                                   relief=tk.SOLID).grid(row=r, column=c, sticky='nsew')



        def render_page(index):

            for child in content.winfo_children():

                child.destroy()

            for idx, button in enumerate(nav_buttons):

                button.configure(bg='#e6d9b9' if idx == index else SIDEBAR,

                                 fg=GOLD if idx == index else MUTED)

            page_title, subtitle, cards = manual_pages[index]

            top = tk.Frame(content, bg=BG)

            top.pack(fill=tk.X, padx=14, pady=(7, 2))

            tk.Label(top, text=page_title, font=(font_name, 20, 'bold'),

                     fg=GOLD, bg=BG, anchor='w', justify=tk.LEFT,

                     wraplength=690).pack(fill=tk.X)

            if subtitle:

                tk.Label(top, text=subtitle, font=(font_name, 14),

                         fg=MUTED, bg=BG, anchor='w', justify=tk.LEFT,

                         wraplength=690).pack(fill=tk.X, pady=(3, 0))

            for card_title, card_subtitle, rules, tables in cards:

                card = tk.Frame(content, bg=PANEL, highlightbackground=BORDER,

                                highlightcolor=BORDER, highlightthickness=1, bd=0)

                card.pack(fill=tk.X, padx=10, pady=7)

                head = tk.Frame(card, bg=PANEL)

                head.pack(fill=tk.X, padx=16, pady=(12, 5))

                tk.Label(head, text=card_title, font=(font_name, 16, 'bold'),

                         fg=GOLD, bg=PANEL, anchor='w', justify=tk.LEFT,

                         wraplength=680).pack(fill=tk.X)

                if card_subtitle:

                    tk.Label(head, text=card_subtitle, font=(font_name, 14),

                             fg=MUTED, bg=PANEL, anchor='w', justify=tk.LEFT,

                             wraplength=680).pack(fill=tk.X)

                for rule_title, detail in rules:

                    add_rule(card, rule_title, detail)

                for table_title, table_headers, rows in tables:

                    add_table(card, table_title, table_headers, rows)

                tk.Frame(card, bg=PANEL, height=6).pack(fill=tk.X)

            content.update_idletasks()

            canvas.configure(scrollregion=canvas.bbox('all'))

            canvas.yview_moveto(0)



        nav_buttons = []

        for index, (page_title, _subtitle, _cards) in enumerate(manual_pages):

            button = tk.Button(sidebar, text=page_title, command=lambda i=index: render_page(i),

                               font=(font_name, 14), fg=MUTED, bg=SIDEBAR,

                               activebackground='#e8d49a', activeforeground=GOLD,

                               relief=tk.FLAT, bd=0, anchor='w', padx=18, pady=10,

                               cursor='hand2')

            button.pack(fill=tk.X)

            nav_buttons.append(button)



        def on_mousewheel(event):

            canvas.yview_scroll(int(-event.delta / 120), 'units')

            return 'break'



        dialog.bind('<MouseWheel>', on_mousewheel)

        dialog.bind('<Button-4>', lambda _e: (canvas.yview_scroll(-1, 'units'), 'break')[1])

        dialog.bind('<Button-5>', lambda _e: (canvas.yview_scroll(1, 'units'), 'break')[1])

        dialog.bind('<Escape>', lambda _e: close_dialog())

        dialog.protocol('WM_DELETE_WINDOW', close_dialog)

        if nav_buttons:

            render_page(0)

        dialog.after(30, dialog.focus_force)

    def _draw_wild_spot(self, seat, kind, cx, cy, label, radius):
        tag = 'spot_'+seat+'_'+kind
        border = self.canvas.create_oval(cx-radius,cy-radius,cx+radius,cy+radius,
            fill=self.ZONE_COLORS[seat],outline=PANEL_BG,width=2,tags=tag)
        self._register_spot(seat,kind,cx,cy,border,label)
        # 放大的下注圈使用清晰字号，完整圆圈均可点击。
        if kind in ('original_five','public_pair','play'):
            for item in self.canvas.find_withtag(tag):
                if self.canvas.type(item)=='text': self.canvas.itemconfigure(item,font=('Arial',12 if kind=='public_pair' else 14,'bold'))

    def card_size(self, side):
        return self.CARD_WIDTH,self.CARD_HEIGHT

    @staticmethod
    def _card_image_key(card):
        # shuffle.py 的鬼牌可记为 ('JOKER','A') 或 ('JOKER','JOKER')。
        return ('JOKER','JOKER') if card.is_joker else (card.suit,card.rank)

    def _is_discard(self, side, index):
        if side == 'Public':
            return False
        hand = self.game.dealer_hand if side=='Dealer' else self.game.hands[side]
        discard = self.game.dealer_discard if side=='Dealer' else self.game.discards[side]
        return discard is not None and hand[index] == discard

    def toggle_player_discard(self, seat, index):
        if self.game.stage!='decision' or self._decision_busy or self.game.decisions.get(seat)!='pending': return
        previous = self.selected_discards[seat]
        if previous is not None:
            self.canvas.coords(self.card_items[(seat,previous)],*self._card_origins[(seat,previous)])
        selected = None if previous==index else index
        self.selected_discards[seat] = selected
        self.game.discards[seat] = None if selected is None else self.game.hands[seat][selected]
        self._update_hand_title(seat)
        if selected is not None:
            x,y = self._card_origins[(seat,selected)]
            item = self.card_items[(seat,selected)]
            self.canvas.coords(item,x,y+10)
            self.canvas.tag_raise(item)

    def raise_action(self, multiplier, seat='Player1'):
        self._decide(seat,'play',multiplier)

    def _move_discard(self, side, card, complete):
        hand = self.game.dealer_hand if side=='Dealer' else self.game.hands[side]
        selected = next(i for i,c in enumerate(hand) if c==card)
        item = self.card_items[(side,selected)]
        source = self._pil_cards[self._card_image_key(card)]
        # 其余四张从左到右排好，弃牌移到最右侧，移动结束才转九十度。
        kept = [c for c in sort_hand_for_display(hand) if c!=card]
        motions = []
        for position,c in enumerate(kept):
            original = next(i for i,v in enumerate(hand) if v==c)
            other = self.card_items[(side,original)]
            tx,ty = self.card_position(side,position)
            motions.append((other,tuple(self.canvas.coords(other)),(tx,ty)))
        start = tuple(self.canvas.coords(item))
        right_x,y = self.card_position(side,4)
        # 横放牌宽112、四张竖牌宽335，左右相邻并限制在所属牌区内。
        target = (right_x if side=='Dealer' else right_x-4,y+16)
        motions.append((item,start,target))
        self.canvas.tag_raise(item)
        def move(frame=0):
            p = frame/18; eased = p*p*(3-2*p)
            for moving,(x,y),(tx,ty) in motions:
                self.canvas.coords(moving,x+(tx-x)*eased,y+(ty-y)*eased)
            if frame<18: self._schedule(16,move,frame+1)
            else:
                def rotate(step=0):
                    image = source.rotate(-90*step/9,resample=Image.Resampling.BICUBIC,expand=True)
                    if step == 9:
                        # 移到最右侧且完全打横后才淡化，后续阶段持续保持。
                        image = self._faded_card_image(image)
                    photo = ImageTk.PhotoImage(image,master=self)
                    self._discard_photos[side] = photo
                    self.canvas.itemconfigure(item,image=photo)
                    # 固定最右侧牌位的左上角；旋转时不为了扩展后的宽度移动牌位。
                    self.canvas.coords(item,*target)
                    if step<9: self._schedule(20,rotate,step+1)
                    else: complete()
                rotate()
        move()

    def _reveal_public(self):
        def revealed():
            self._public_cards_revealed = True
            for seat in self.game.SEATS:
                if self.game.hands[seat]:
                    self._update_hand_title(seat)
            self._settle()
        self._reveal_next([('Public',i) for i in range(2)],0,revealed)

    @staticmethod
    def _faded_card_image(source):
        # 每次从原图计算alpha，保持45%不透明度，避免多次淡化累积。
        faded = source.convert('RGBA').copy()
        faded.putalpha(faded.getchannel('A').point(lambda value:round(value*.45)))
        return faded

    def _fade_card_item(self, item, source):
        faded = self._faded_card_image(source)
        photo = ImageTk.PhotoImage(faded,master=self)
        self._faded_photos[item] = photo
        self.canvas.itemconfigure(item,image=photo)

    def _render_hand_usage(self):
        """结算默认显示庄家用牌；鼠标停在玩家手牌时切换查看者。"""
        if self.game.settlement is None:
            return
        self.canvas.delete('hand_usage')
        self._hand_usage_keys.clear()
        users = {}
        for owner in ('Dealer', *self.game.SEATS):
            hand = self.game.dealer_hand if owner == 'Dealer' else self.game.hands[owner]
            if not hand:
                continue
            best = best_hand_from_cards(self.game.pool(owner))[3]
            used = set()
            for card in best:
                public_index = next((i for i, c in enumerate(self.game.public_cards) if c == card), None) if getattr(card, 'source', '') == 'public' else None
                side = 'Public' if public_index is not None else owner
                index = public_index if public_index is not None else next(
                    i for i, c in enumerate(hand) if c == card)
                key = side, index
                used.add(key)
                if owner == 'Dealer' or self.game.decisions[owner] == 'play':
                    users.setdefault(key, []).append(owner)
            self._hand_usage_keys[owner] = used
        self._final_usage = {key: tuple(owners) for key, owners in users.items()}
        self._default_usage_owner = 'Dealer'
        if not any(side == 'Public' for side, _ in self._hand_usage_keys.get('Dealer', set())):
            self._default_usage_owner = next((seat for seat in self.game.SEATS if self.game.hands[seat]), 'Dealer')
        self._faded_photos.clear()
        self._settled_card_photos.clear()
        for (side, index), item in self.card_items.items():
            hand = self.game.public_cards if side == 'Public' else self.game.dealer_hand if side == 'Dealer' else self.game.hands[side]
            card = hand[index]
            source = self._pil_cards[self._card_image_key(card)].convert('RGBA').resize(
                self.card_size(side), Image.Resampling.LANCZOS)
            discard = None if side == 'Public' else self.game.dealer_discard if side == 'Dealer' else self.game.discards[side]
            if discard is not None and card == discard:
                source = source.rotate(-90, resample=Image.Resampling.BICUBIC, expand=True)
            self._settled_card_photos[item] = ImageTk.PhotoImage(source, master=self)
            self._fade_card_item(item, source)
        self._usage_owner = None
        self._apply_hand_usage(self._default_usage_owner)
        self._on_hand_usage_hover()

    def _apply_hand_usage(self, owner, hovered_seat=None):
        """横放弃牌持续淡化；玩家其余未用手牌只在悬停时淡化。"""
        used = self._hand_usage_keys.get(owner, set())
        for key, item in self.card_items.items():
            side, index = key
            unused_public = side == 'Public' and key not in used
            unused_hand = (side == owner and key not in used
                           and (side == 'Dealer' or side == hovered_seat))
            faded = self._is_discard(side,index) or unused_public or unused_hand
            photos = self._faded_photos if faded else self._settled_card_photos
            self.canvas.itemconfigure(item, image=photos[item])
        self._usage_owner = owner
        self._hovered_usage_seat = hovered_seat

    def _on_hand_usage_hover(self, event=None):
        if (self.game.settlement is None or not self._hand_usage_keys
                or self.game.stage not in ('settled', 'settling', 'await_restart')):
            return
        current = set(self.canvas.find_withtag('current'))
        seat = next((side for (side, _), item in self.card_items.items()
                     if item in current and side in self.game.SEATS
                     and self.game.hands[side]), None)
        owner = seat or self._default_usage_owner
        if owner != self._usage_owner or seat != self._hovered_usage_seat:
            self._apply_hand_usage(owner,seat)

    def _on_hand_usage_leave(self, event=None):
        if (self.game.settlement is not None and self._hand_usage_keys
                and self.game.stage in ('settled', 'settling', 'await_restart')
                and (self._usage_owner != self._default_usage_owner
                     or self._hovered_usage_seat is not None)):
            self._apply_hand_usage(self._default_usage_owner)


def main(initial_balance=10000, username="Guest", *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """嵌入现有 Tk 根窗口；未传 parent 时仍可独立运行。"""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return WildFivePokerUI(
            parent, actual_balance, actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("王牌五张扑克")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = WildFivePokerUI(root, actual_balance, actual_user)
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
