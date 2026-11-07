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
from collections import Counter
from itertools import combinations

# =========================================================
# 仿轮盘 UI 颜色与常量（取自 Ultimate_Texas_Holdem）
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

# 扑克牌花色和点数（保持不变）
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    7: '迷你皇家同花顺',
    6: '同花顺',
    5: '三条',
    4: '顺子',
    3: '同花',
    2: '对子',
    1: '高牌'
}

# Pair Plus支付表（原逻辑）
PAIR_PLUS_PAYOUT = {
    7: 100,  # 迷你皇家同花顺 100:1
    6: 40,   # 同花顺 40:1
    5: 30,   # 三条 30:1
    4: 6,    # 顺子 6:1
    3: 3,    # 同花 3:1
    2: 1     # 对子 1:1
}

# 6 Card支付表（原逻辑）
SIX_CARD_PAYOUT = {
    "6_card_super_royal": 10001,
    "royal_flush": 1001,
    "straight_flush": 201,
    "four_of_a_kind": 51,
    "full_house": 21,
    "flush": 16,
    "straight": 11,
    "three_of_a_kind": 6,
    "other": 0
}

# =========================================================
# 文件操作辅助函数（保持原样）
# =========================================================
def get_data_file_path():
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'A_Tools/Account/saving_data.json')

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

# =========================================================
# Progressive 文件加载与保存（修改：使用新Key和默认值）
# =========================================================
def load_progressive():
    path = str(_progressive_file)
    default_progressive = 271288.59
    min_progressive = 271288.59
    if not os.path.exists(path):
        return True, default_progressive
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item.get('Games') == 'Progressive_2.50':
                    progressive_amount = float(item.get('jackpot', default_progressive))
                    return False, max(progressive_amount, min_progressive)
    except Exception:
        return True, default_progressive
    return True, default_progressive

def save_progressive(progressive):
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
        if item.get('Games') == 'Progressive_2.50':
            item['jackpot'] = progressive
            found = True
            break
    if not found:
        data.append({"Games": "Progressive_2.50", "jackpot": progressive})
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def three_card_poker_log_path() -> str:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Three_Card_Poker.json")

def save_three_card_history(deck, player_cards, dealer_cards, progressive_cards, result_info=None):
    """
    记录三张牌扑克牌局历史
    """
    log_path = three_card_poker_log_path()
    
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
            print(f"读取历史文件出错: {e}，将使用全新记录")
    
    # 计算新的 game_id
    max_id = 0
    for rec in data["history"]:
        if "game_id" in rec and isinstance(rec["game_id"], int):
            if rec["game_id"] > max_id:
                max_id = rec["game_id"]
    new_game_id = max_id + 1
    
    # 更新统计
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
    
    # 构建记录
    record = {
        "game_id": new_game_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "deck_order": [str(c) for c in deck.full_deck],
        "cut_position": deck.cut_position,
        "player_cards": [str(c) for c in player_cards],
        "dealer_cards": [str(c) for c in dealer_cards],
        "progressive_cards": [str(c) for c in progressive_cards] if progressive_cards else [],
        "result": result_info if result_info else {}
    }
    if winner is not None:
        record["result"]["winner"] = winner
    elif "winner" not in record["result"]:
        pass
    
    data["history"].append(record)
    
    # 只保留最新50局
    if len(data["history"]) > 50:
        data["history"] = data["history"][-50:]
    
    # 写回文件
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# =========================================================
# 扑克牌类与牌堆（原样）
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
        except (subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
                json.JSONDecodeError,
                ValueError,
                KeyError) as e:
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
# 手牌评估函数（原样）
# =========================================================
def evaluate_three_card_hand(cards):
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]

    # 迷你皇家同花顺 (Q-K-A同花)
    if len(set(suits)) == 1 and values == [14, 13, 12]:
        return (7, [14])

    # 同花顺
    if len(set(suits)) == 1:
        if values == [14, 3, 2]:
            return (6, [3])
        if values[0] - values[1] == 1 and values[1] - values[2] == 1:
            return (6, [values[0]])

    # 三条
    if values[0] == values[1] == values[2]:
        return (5, [values[0]])

    # 顺子
    if values == [14, 3, 2]:
        return (4, [3])
    if values[0] - values[1] == 1 and values[1] - values[2] == 1:
        return (4, [values[0]])

    # 同花
    if len(set(suits)) == 1:
        return (3, values)

    # 对子
    if values[0] == values[1]:
        return (2, [values[0], values[2]])
    elif values[1] == values[2]:
        return (2, [values[1], values[0]])

    return (1, values)  # 高牌

def compare_hands(hand1, hand2):
    rank1, values1 = evaluate_three_card_hand(hand1)
    rank2, values2 = evaluate_three_card_hand(hand2)
    if rank1 > rank2:
        return 1
    elif rank1 < rank2:
        return -1
    else:
        for v1, v2 in zip(values1, values2):
            if v1 > v2:
                return 1
            elif v1 < v2:
                return -1
        return 0

# =========================================================
# 游戏逻辑类（添加 progressive_cards）
# =========================================================

def evaluate_five_card_hand(cards):
    if not cards or len(cards) < 5:
        return (0, [])
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    is_flush = len(set(suits)) == 1

    values_asc = sorted([c.value for c in cards])
    is_straight = False
    straight_values = None
    if len(set(values_asc)) == 5:
        if values_asc[-1] - values_asc[0] == 4:
            is_straight = True
            straight_values = sorted(values, reverse=True)
        elif values_asc == [2,3,4,5,14]:
            is_straight = True
            straight_values = [5,4,3,2,1]

    is_royal = is_straight and is_flush and values[0] == 14 and values[4] == 10
    if is_straight and is_flush:
        return (9 if is_royal else 8, straight_values)

    value_count = {}
    for v in values:
        value_count[v] = value_count.get(v, 0) + 1
    sorted_counts = sorted(value_count.items(), key=lambda x: (x[1], x[0]), reverse=True)
    sorted_values = [item[0] for item in sorted_counts]

    if sorted_counts[0][1] == 4:
        return (7, sorted_values)
    if sorted_counts[0][1] == 3 and sorted_counts[1][1] == 2:
        return (6, sorted_values)
    if is_flush:
        return (5, values)
    if is_straight:
        return (4, straight_values)
    if sorted_counts[0][1] == 3:
        return (3, sorted_values)
    if sorted_counts[0][1] == 2 and sorted_counts[1][1] == 2:
        return (2, sorted_values)
    if sorted_counts[0][1] == 2:
        return (1, sorted_values)
    return (0, values)


def sort_hand_for_display(hand, hand_eval=None):
    """Only rearrange displayed cards; original deal order remains immutable."""
    rank = (hand_eval or evaluate_three_card_hand(hand))[0]
    if rank in (4, 6, 7):
        low_ace = {c.value for c in hand} == {14, 2, 3}
        return sorted(hand, key=lambda c: 1 if low_ace and c.value == 14 else c.value)
    counts = Counter(c.value for c in hand)
    return sorted(hand, key=lambda c: (counts[c.value], c.value), reverse=True)

class ThreeCardPokerGame:
    SEATS = ('Player1', 'Player2')
    MIN_PROGRESSIVE = 271288.59

    def __init__(self):
        self.progressive_amount = load_progressive()[1]
        self.min_progressive = self.MIN_PROGRESSIVE
        self.reset_game()

    @staticmethod
    def empty_bet():
        return dict(ante=0.0, six_card=0.0, pair_plus=0.0, same_color=0.0, jackpot=0.0, play=0.0)

    @staticmethod
    def pair_plus_limit(has_ante, high_bet_mode=False):
        if high_bet_mode:
            return 25000 if has_ante else 50000
        return 2500 if has_ante else 5000

    def reset_game(self):
        self.deck = None
        self.hands = {seat: [] for seat in self.SEATS}
        self.dealer_hand = []
        self.progressive_cards = []
        self.round_deal_sequence = []
        self.bets = {seat: self.empty_bet() for seat in self.SEATS}
        self.decisions = {seat: 'inactive' for seat in self.SEATS}
        self.stage = 'betting'
        self.settlement = None
        self.side_returns = {}
        self.refunded_bets = {}

    @staticmethod
    def dealer_qualifies_hand(hand):
        return len(hand) == 3 and (evaluate_three_card_hand(hand)[0] > 1
                                  or max(c.value for c in hand) >= 12)

    def dealer_qualifies(self):
        return self.dealer_qualifies_hand(self.dealer_hand)

    @classmethod
    def deal_sequence(cls, active_seats=None):
        seats = cls.SEATS if active_seats is None else tuple(s for s in cls.SEATS if s in active_seats)
        return [(side, index) for index in range(3)
                for side in (*seats, 'Dealer', 'Progressive')
                if side != 'Progressive' or index < 2]

    def start_round(self, bets, balance, high_bet_mode=False):
        if self.stage != 'betting':
            raise ValueError('本局尚未结束。')
        minimum, maximum, side_max = (100, 50000, 12500) if high_bet_mode else (10, 10000, 2500)
        prepared = {}
        refunded = {}
        for seat in self.SEATS:
            b = {k: float(bets[seat].get(k, 0)) for k in self.empty_bet()}
            if any(not math.isfinite(v) or v < 0 for v in b.values()):
                raise ValueError('下注金额必须是有限的非负数。')
            if b['ante'] == 0 and b['pair_plus'] == 0:
                if any(b.values()):
                    refunded[seat] = dict(b)
                prepared[seat] = self.empty_bet()
                continue
            elif b['ante'] and not minimum <= b['ante'] <= maximum:
                raise ValueError(f'每手前注须为 ${minimum:,} 至 ${maximum:,}。')
            pair_max = self.pair_plus_limit(b['ante'] > 0, high_bet_mode)
            if b['pair_plus'] > pair_max:
                raise ValueError(f'对子加注不能超过 ${pair_max:,.0f}。')
            if any(b[kind] > side_max for kind in ('six_card', 'same_color')) or b['jackpot'] not in (0, 2.5):
                raise ValueError('边注超出限额，累进大奖每手固定 $2.50。')
            if b['play'] not in (0, b['ante']):
                raise ValueError('加注必须为与前注相同的金额。')
            prepared[seat] = b
        if not any(b['ante'] or b['pair_plus'] for b in prepared.values()):
            raise ValueError('请至少为一手牌下前注或对子加注。')
        charged = sum(sum(b.values()) for b in prepared.values())
        reserve = sum(b['ante'] for b in prepared.values() if b['ante'] and not b['play'])
        if charged + reserve > balance:
            raise ValueError('余额不足以支付下注及两手可能需要的加注。')
        # 洗牌、发牌成功后才提交状态及扣款。
        deck = Deck()
        hands = {seat: [] for seat in self.SEATS}
        dealer, progressive = [], []
        targets = dict(hands, Dealer=dealer, Progressive=progressive)
        active_seats = [s for s in self.SEATS if prepared[s]['ante'] or prepared[s]['pair_plus']]
        sequence = self.deal_sequence(active_seats)
        for side, _ in sequence:
            targets[side].extend(deck.deal(1))
        self.deck, self.hands, self.dealer_hand = deck, hands, dealer
        self.progressive_cards = progressive
        self.round_deal_sequence = sequence
        self.bets = prepared
        self.refunded_bets = refunded
        self.decisions = {s: ('inactive' if not (prepared[s]['ante'] or prepared[s]['pair_plus']) else
                             'side_only' if not prepared[s]['ante'] else
                             'play' if prepared[s]['play'] else 'pending') for s in self.SEATS}
        self.stage = 'dealing'
        return charged

    def decide(self, seat, action, balance):
        if self.stage != 'decision' or self.decisions.get(seat) != 'pending':
            return 0.0
        if action not in ('play', 'fold'):
            raise ValueError('无效的决定。')
        cost = self.bets[seat]['ante'] if action == 'play' else 0.0
        if cost > balance:
            raise ValueError('余额不足以加注。')
        self.bets[seat]['play'] = cost
        self.decisions[seat] = action
        return cost

    @staticmethod
    def pair_plus_return(hand, stake):
        payout = PAIR_PLUS_PAYOUT.get(evaluate_three_card_hand(hand)[0])
        return round(stake * (payout + 1), 2) if payout is not None else 0.0

    @staticmethod
    def six_card_return(hand, dealer, stake):
        if not stake:
            return 0.0
        cards = hand + dealer
        if len({c.suit for c in cards}) == 1 and {c.value for c in cards} == {9,10,11,12,13,14}:
            return round(stake * SIX_CARD_PAYOUT['6_card_super_royal'], 2)
        payouts = {9: 1001, 8: 201, 7: 51, 6: 21, 5: 16, 4: 11, 3: 6}
        best = max(payouts.get(evaluate_five_card_hand(list(combo))[0], 0)
                   for combo in combinations(cards, 5))
        return round(stake * best, 2)

    @staticmethod
    def same_color_return(hand, dealer, stake):
        """红黑颜色判奖；六张同色赔4:1，否则玩家三张同色赔3:1。

        每局只支付最高一项，返还金额包含本金。♥♦为红色，♠♣为黑色。
        """
        if not stake or len(hand) != 3:
            return 0.0
        red_suits = ('♥', '♦')
        player_red = hand[0].suit in red_suits
        if not all((card.suit in red_suits) == player_red for card in hand):
            return 0.0
        six_same = len(dealer) == 3 and all(
            (card.suit in red_suits) == player_red for card in dealer)
        payout = 4 if six_same else 3
        return round(stake * (payout + 1), 2)

    def settle_side_bet(self, seat, kind):
        key = (seat, kind)
        if key not in self.side_returns:
            hand, b = self.hands[seat], self.bets[seat]
            if kind == 'pair_plus':
                returned = self.pair_plus_return(hand, b[kind])
            elif kind == 'six_card':
                returned = self.six_card_return(hand, self.dealer_hand, b[kind])
            elif kind == 'same_color':
                returned = self.same_color_return(hand, self.dealer_hand, b[kind])
            else:
                raise ValueError(f'未知边注：{kind}')
            self.side_returns[key] = returned
        return self.side_returns[key]

    def settle(self):
        if self.settlement is not None:
            return self.settlement
        if self.stage != 'showdown' or 'pending' in self.decisions.values():
            raise ValueError('两手完成决定并开牌后才能结算。')
        outcomes = {}
        total_bonus = 0.0
        jackpot_snapshot = self.progressive_amount
        for seat in self.SEATS:
            if self.decisions[seat] == 'inactive':
                continue
            b, hand = self.bets[seat], self.hands[seat]
            rank = evaluate_three_card_hand(hand)[0]
            d = dict(ante=0.0, ante_bonus=0.0, play=0.0, bonus=0.0,
                     six_card=0.0, pair_plus=0.0, same_color=0.0)
            if self.decisions[seat] == 'fold':
                winner, message = 'fold', '已弃牌'
            elif self.decisions[seat] == 'side_only':
                winner, message = 'side_only', '仅结算边注'
            elif not self.dealer_qualifies():
                d['ante'], d['play'] = b['ante'] * 2, b['play']
                winner, message = 'player', '庄家不及格：前注赢，加注退回'
            else:
                comparison = compare_hands(hand, self.dealer_hand)
                if comparison > 0:
                    d['ante'], d['play'] = b['ante']*2, b['play']*2
                    winner, message = 'player', '玩家获胜'
                elif comparison == 0:
                    d['ante'], d['play'] = b['ante'], b['play']
                    winner, message = 'push', '平局：前注、加注退回'
                else:
                    winner, message = 'dealer', '庄家获胜'
            if self.decisions[seat] == 'play':
                d['ante_bonus'] = b['ante'] * {7: 5, 6: 5, 5: 4, 4: 1}.get(rank, 0)
            # 已购买的边注在弃牌后仍会结算。
            d['pair_plus'] = self.settle_side_bet(seat, 'pair_plus')
            d['six_card'] = self.settle_side_bet(seat, 'six_card')
            d['same_color'] = self.settle_side_bet(seat, 'same_color')
            if b['jackpot']:
                progressive_rank = evaluate_five_card_hand(hand + self.progressive_cards)[0]
                d['bonus'] = round({9: jackpot_snapshot, 8: jackpot_snapshot * .1,
                                    7: 1250.0, 6: 375.0, 5: 250.0}.get(progressive_rank, 0.0), 2)
            total_bonus += d['bonus']
            returned = round(sum(d.values()), 2)
            outcomes[seat] = dict(winner=winner, message=message, details=d,
                                  returned=returned, stake=sum(b.values()),
                                  net=round(returned-sum(b.values()), 2))
        contribution = sum(sum(b.values())*.001+b['jackpot']*.95
                           for b in self.bets.values())
        self.progressive_amount = round(max(self.MIN_PROGRESSIVE,
            max(self.MIN_PROGRESSIVE, jackpot_snapshot-total_bonus)+contribution), 2)
        self.stage = 'settled'
        self.settlement = dict(hands=outcomes, returned=round(sum(r['returned'] for r in outcomes.values()), 2))
        return self.settlement


class ThreeCardPokerGUI(tk.Frame):
    WIDTH, HEIGHT = 1150, 750
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    DEAL_CARD_MS = 224 / .85
    DEAL_MOVE_MS = (128 / .75) / .85
    BET_CHIP_RADIUS = 16 * 4 / 3
    HOUSE_CHIP_POS = (575, 43)
    TABLE_GREEN = '#4b1e22'
    PROGRESSIVE_LAMP_WIDTH = 122.0 * .8
    SIDE_BET_DIAMETER = 122.0 * 2 / 3
    SEAT_BOUNDS = {'Player1': (22, 566), 'Player2': (582, 1128)}
    ANTE_X_OFFSET = 303
    ZONE_COLORS = {'Player1':'#35634B','Player2':'#204536'}
    SEAT_NAMES = {'Player1': '玩家1', 'Player2': '玩家2', 'Dealer': '庄家手牌', 'Progressive': '累进大奖牌'}

    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = username, float(initial_balance)
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game = ThreeCardPokerGame()
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
        for key in ['back'] + [(s, r) for s in SUITS for r in RANKS]:
            filename = 'Background.png' if key == 'back' else f'{suits[key[0]]}{key[1]}.png'
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
                    text = rank + suit
                    try:
                        draw.text((7,10), text, font=font, fill=RED if suit in '♥♦' else BLACK)
                        draw.text((14,62), suit, font=font, fill=RED if suit in '♥♦' else BLACK)
                    except UnicodeEncodeError:
                        draw.text((7,10), rank+suits[suit][0], font=font, fill=BLACK)
            self.original_images.setdefault(key,im.copy())
            self._pil_cards[key] = im
            self._face_photos[key] = ImageTk.PhotoImage(im, master=self)

    def _text(self, x, y, text, size=12, color=TEXT, **kw):
        return self.canvas.create_text(x, y, text=text, fill=color, font=('Arial', size, 'bold'), **kw)


    def _create_widgets(self):
        self.canvas=tk.Canvas(self,width=self.WIDTH,height=self.HEIGHT,bg=ROOT_BG,highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH,expand=True)
        self.control_buttons={}
        c=self.canvas
        # 同行四块独立内容：限红表 / 庄家牌区 / 累进牌区 / 数字奖池。
        self._text(575,18,'三张牌扑克  THREE CARD POKER',16,GOLD)
        c.create_rectangle(355,44,630,197,fill=self.TABLE_GREEN,outline='')
        self.title_items={'Dealer':self._text(493,57,'庄家',16,PANEL_BG)}
        c.create_rectangle(637,44,825,197,fill='#6B5220',outline='',tags='progressive_card_area')
        self._text(731,57,'累进',16,GOLD,tags='progressive_card_area')
        for seat,(x0,x1) in self.SEAT_BOUNDS.items():
            c.create_rectangle(x0,230,x1,617,fill=self.ZONE_COLORS[seat],outline='')
            self.title_items[seat]=self._text(x0+self.ANTE_X_OFFSET,244,self.SEAT_NAMES[seat],16,PANEL_BG)
        self._draw_limit_table()
        self._draw_progressive_panel()
        # 赌场桌面 BAR，有明暗边框；不属于任何一个手牌区域。
        c.create_rectangle(22,200,1128,226,fill='#173C2E',outline='#65784B',width=1)
        c.create_line(25,201,1125,201,fill='#E0C879',width=2)
        c.create_line(25,225,1125,225,fill='#0C241B',width=2)
        self._text(575,213,'庄家须持 Q 高牌或以上牌型才及格',13,GOLD)
        for seat,(x0,x1) in self.SEAT_BOUNDS.items():
            card_x,card_y=self.card_position(seat,0)
            lamp_x=card_x-self.PROGRESSIVE_LAMP_WIDTH/2-28
            self._draw_progressive_lamp(seat,lamp_x,card_y+self.CARD_HEIGHT/2)
            self._draw_spot(seat,'six_card',x0+70,544,'六张牌\n外注')
            self._draw_spot(seat,'pair_plus',x0+120,438,'对子\n加注')
            self._draw_same_color_spot(seat,x0+170,544)
            self._draw_main_bet_pair(seat,x0+self.ANTE_X_OFFSET,435,529)
            self.action_buttons[(seat,'play')]=self.create_control_button(
                x0+410,419,x1-15,477,'下注1倍',lambda s=seat:self.play_action(s),'#397A48',font_size=14,draw_shadow=False)
            self.action_buttons[(seat,'fold')]=self.create_control_button(
                x0+410,488,x1-15,546,'弃牌',lambda s=seat:self.fold_action(s),'#9B403A',font_size=14,draw_shadow=False)
        self._draw_bottom_controls()
        for side in ('Dealer','Progressive',*self.game.SEATS):
            for index in range(2 if side=='Progressive' else 3):
                x,y=self.card_position(side,index)
                c.create_rectangle(x,y,x+self.CARD_WIDTH,y+self.CARD_HEIGHT,
                    outline=GOLD if side=='Progressive' else '#7B9374',dash=(3,3),tags='card_slots')



    def _draw_spot(self, seat, kind, cx, cy, label):
        tag = 'spot_'+seat+'_'+kind
        radius = self.SIDE_BET_DIAMETER / 2
        border = self.canvas.create_oval(cx-radius,cy-radius,cx+radius,cy+radius,
            fill=self.ZONE_COLORS[seat],outline=GOLD,width=2,tags=tag)
        self._register_spot(seat,kind,cx,cy,border,label)

    def _draw_same_color_spot(self, seat, cx, cy):
        c,tag=self.canvas,'spot_'+seat+'_same_color'
        half=self.SIDE_BET_DIAMETER/2
        border=c.create_rectangle(cx-half,cy-half,cx+half,cy+half,
            fill=self.ZONE_COLORS[seat],outline='',tags=tag)
        # 上下白线、左右红线；文字横排，分别使用红色与白色。
        c.create_line(cx-half,cy-half,cx+half,cy-half,fill=TEXT,width=3,tags=tag)
        c.create_line(cx-half,cy+half,cx+half,cy+half,fill=TEXT,width=3,tags=tag)
        c.create_line(cx-half,cy-half,cx-half,cy+half,fill=RED,width=3,tags=tag)
        c.create_line(cx+half,cy-half,cx+half,cy+half,fill=RED,width=3,tags=tag)
        self._text(cx-13,cy,'同',18,RED,tags=tag)
        self._text(cx+13,cy,'色',18,TEXT,tags=tag)
        self._register_spot(seat,'same_color',cx,cy,border,None)


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
        c=self.canvas
        c.itemconfigure(self.balance_item,text=f'余额: ${self.balance:,.2f}')
        total=sum(sum(b.values()) for b in self.bets.values())
        text=f'本局下注: ${total:,.2f}' if total else f'上局返还: ${self.last_win:,.2f}'
        c.itemconfigure(self.total_item,text=text)
        limits=('$100','$50,000','$12,500') if self.high_bet_mode else ('$10','$10,000','$2,500')
        pair_without_ante=self.game.pair_plus_limit(False,self.high_bet_mode)
        pair_with_ante=self.game.pair_plus_limit(True,self.high_bet_mode)
        limits+= (f'${pair_without_ante:,}（没下注前注）\n${pair_with_ante:,}（有下注前注）',)
        for item,value in zip(self.limit_value_items,limits):c.itemconfigure(item,text=value)
        self._render_chips()
        betting=self.game.stage=='betting' and self._motion_count==0
        self.set_control_button_state(self.clear_button,betting)
        self.set_control_button_state(self.repeat_button,betting and bool(self.last_bet))
        self.set_control_button_state(self.start_button,betting)
        restarting=self.game.stage in ('await_restart','returning','credit_pending','sweeping')
        c.itemconfigure(self.repeat_button,state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button,state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button,state='normal' if restarting else 'hidden')
        self.set_control_button_state(self.restart_button,self.game.stage in ('await_restart','credit_pending'))
        for (seat,action),button in self.action_buttons.items():
            self.set_control_button_state(button,self.game.stage=='decision' and not self._decision_busy
                and self.game.decisions[seat]=='pending')



    def add_chip_to_bet(self, seat, kind):
        if self.game.stage!='betting' or self._motion_count:return
        new={s:dict(b) for s,b in self.bets.items()};b=new[seat]
        if kind=='jackpot':b[kind]=0 if b[kind] else 2.5
        elif kind=='play':
            if not b['ante']:return
            b[kind]=0 if b[kind] else b['ante']
        else:
            maximum=50000 if self.high_bet_mode else 10000
            limit=(maximum if kind=='ante' else
                   self.game.pair_plus_limit(b['ante']>0,self.high_bet_mode) if kind=='pair_plus' else
                   12500 if self.high_bet_mode else 2500)
            if kind=='ante' and b['pair_plus']>self.game.pair_plus_limit(True,self.high_bet_mode):
                messagebox.showwarning('下注限制','请先降低对子加注金额，再设置前注。',parent=self)
                return
            b[kind]=min(limit,b[kind]+self.selected_chip)
            if kind=='ante' and b['play']:b['play']=b['ante']
        self._apply_bet_layout(new)


    def reset_single_bet(self, seat, kind):
        if self.game.stage!='betting' or self._motion_count:return
        new={s:dict(b) for s,b in self.bets.items()}
        if kind=='ante':
            new[seat]['ante']=0.0;new[seat]['play']=0.0
        else:new[seat][kind]=0.0
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
        if side == 'Progressive':
            return 648 + index * 85, 74
        center = 493 if side == 'Dealer' else self.SEAT_BOUNDS[side][0]+self.ANTE_X_OFFSET
        return center-self.CARD_WIDTH/2+(index-1)*(self.CARD_WIDTH+5), 74 if side == 'Dealer' else 260



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
        self._blind_seats={s for s in self.game.SEATS if self.game.decisions[s] in ('play','side_only')}
        self._sorted_sides=set();self._decision_busy=False;self._showdown_started=False
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
        # 下注阶段只摆放筹码，尚未扣余额；这里只扣及格手牌，退款不可重复加钱。
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
            reveal = [(s,i) for s in self.game.SEATS
                if self.game.decisions[s]=='pending' for i in range(3)]
            self._reveal_next(reveal,0,self._after_initial_reveal)
            return
        side,index = sequence[offset]
        x,y = self.card_position(side,index)
        item = self.canvas.create_image(575,52,image=self._face_photos['back'],anchor='nw',tags='cards')
        self.card_items[(side,index)] = item
        def move(step=0):
            p=step/6
            self.canvas.coords(item,575+(x-575)*p,52+(y-52)*p)
            if step<6:
                self._schedule(round(self.DEAL_MOVE_MS*(step+1)/6)-round(self.DEAL_MOVE_MS*step/6),move,step+1)
            else:
                self._schedule(round(self.DEAL_CARD_MS)-round(self.DEAL_MOVE_MS),self._deal_next,sequence,offset+1)
        move()

    def _reveal_next(self, sequence, offset, complete):
        if offset==len(sequence):
            complete()
            return
        side,index = sequence[offset]
        card = (self.game.dealer_hand if side=='Dealer' else
                self.game.progressive_cards if side=='Progressive' else self.game.hands[side])[index]
        item = self.card_items[(side,index)]
        x,y = self.card_position(side,index)
        def flip(step=0):
            fraction = abs(1-step/5)
            width = max(1,round(self.CARD_WIDTH*fraction))
            source = self._pil_cards['back' if step<5 else (card.suit,card.rank)]
            photo = ImageTk.PhotoImage(source.resize((width,self.CARD_HEIGHT),Image.Resampling.LANCZOS),master=self)
            self._flip_photos[item] = photo
            self.canvas.itemconfigure(item,image=photo)
            self.canvas.coords(item,x+(self.CARD_WIDTH-width)/2,y)
            if step<10:
                self._schedule(32,flip,step+1)
            else:
                self.canvas.itemconfigure(item,image=self._face_photos[(card.suit,card.rank)])
                self._flip_photos.pop(item,None)
                self._reveal_next(sequence,offset+1,complete)
        flip()

    def _ready_for_decisions(self):
        # 非盲注手牌翻开并排序后，同时处理对子加注及同色输注，再开放决定按钮。
        self.game.stage='side_settling';self._refresh()
        seats=[s for s in self.game.SEATS if self.game.decisions[s]=='pending']
        self._settle_side_bets(seats,self._enable_decisions,('pair_plus','same_color'),
            same_color_losses_only=True)


    def play_action(self, seat='Player1'):
        self._decide(seat,'play')

    def fold_action(self, seat='Player1'):
        self._decide(seat,'fold')

    def _decide(self, seat, action):
        if self.game.stage!='decision' or self._decision_busy or self.game.decisions.get(seat)!='pending':return
        try:cost=self.game.decide(seat,action,self.balance)
        except ValueError as exc:
            messagebox.showwarning('无法加注',str(exc),parent=self);return
        self._decision_busy=True
        self.balance=round(self.balance-cost,2)
        self.bets[seat]['play']=self.game.bets[seat]['play']
        self._persist_balance();self._refresh()
        def done():
            self._decision_busy=False;self._refresh();self._maybe_showdown()
        if action=='fold':
            transfers=[]
            for kind in ('ante','play'):
                chip=self.visual_chips.pop((seat,kind,'stake'),None)
                if chip:transfers.append(dict(amount=chip['amount'],start=chip['xy'],target=self.HOUSE_CHIP_POS,duration=280))
            self._run_chip_batch(transfers,done)
        else:
            target=self.bet_spots[(seat,'play')]['center']
            def arrived():
                self._set_visual(seat,'play','stake',cost);done()
            self._animate_chip(cost,self._rack_position(),target,arrived)
        self._refresh()


    def _maybe_showdown(self):
        if self._showdown_started or self._decision_busy or 'pending' in self.game.decisions.values():return
        self._showdown_started=True;self.game.stage='showdown';self._refresh()
        sequence=[(s,i) for s in self.game.SEATS if s in self._blind_seats for i in range(3)]
        self._reveal_next(sequence,0,self._after_blind_reveal)



    def _after_blind_reveal(self):
        self._sort_revealed_hands([s for s in self.game.SEATS if s in self._blind_seats],self._finish_blind_reveal)


    def _settle(self):
        if self._settlement_started:return
        self._settlement_started=True
        jackpot_before=self.game.progressive_amount
        result=self.game.settle()
        self.game.stage='settling';self.last_win=result['returned']
        try:save_progressive(self.game.progressive_amount)
        except Exception as exc:messagebox.showerror('奖池保存失败',str(exc),parent=self)
        self._update_hand_title('Dealer')
        self._fade_dealer_notice(not self.game.dealer_qualifies())
        transfers=[];awards=[];round_id=time.time_ns()
        for seat,outcome in result['hands'].items():
            self._update_hand_title(seat)
            for kind in ('ante','play'):
                transfers.extend(self._outcome_transfers(seat,kind,self.game.bets[seat][kind],outcome['details'][kind]))
            ante_bonus=outcome['details']['ante_bonus']
            if ante_bonus:
                cx,cy=self.bet_spots[(seat,'ante')]['center']
                target=(cx+32,cy-30)
                transfers.append(dict(amount=ante_bonus,start=self.HOUSE_CHIP_POS,target=target,duration=440,
                    arrive=lambda s=seat,a=ante_bonus,xy=target:self._set_visual(s,'ante','ante_bonus',a,xy)))
            bonus=outcome['details']['bonus']
            if bonus:
                self._set_lamp_mode(seat,'win')
                awards.append((seat,bonus))
            info=dict(outcome,seat=seat,round_id=round_id,bets=dict(self.game.bets[seat]),
                fold=self.game.decisions[seat]=='fold',progressive_cards=[str(c) for c in self.game.progressive_cards])
            try:save_three_card_history(self.game.deck,self.game.hands[seat],self.game.dealer_hand,self.game.progressive_cards,info)
            except Exception as exc:messagebox.showerror('历史记录保存失败',str(exc),parent=self)
        self._refresh()
        # 全部派彩到位后保留桌面结果；累进大奖中奖时仅等玩家手动继续。
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
        # 对子加注单列显示两种上限；无前注在上，有前注在下。
        c = self.canvas
        x0,x1,y0 = 30,349,75
        c.create_rectangle(x0,y0,x1,181,fill='#183B30',outline=GOLD,width=1,tags='limits')
        c.create_rectangle(x0,y0,x1,y0+29,fill='#40634B',outline=GOLD,tags='limits')
        self._text((x0+x1)/2,y0+14,'下注上限',13,PANEL_BG,tags='limits')
        columns = (('前注最低',60),('前注最高',68),('六张牌/同色\n最高',66),('对子加注\n最高',125))
        self.limit_value_items = []
        left=x0
        for col,(title,width) in enumerate(columns):
            right=left+width
            c.create_rectangle(left,y0+29,right,y0+66,outline='#77906B',tags='limits')
            c.create_rectangle(left,y0+66,right,181,outline='#77906B',tags='limits')
            self._text((left+right)/2,y0+47,title,8 if col==2 else 9,PANEL_BG,justify='center',tags='limits')
            self.limit_value_items.append(self._text((left+right)/2,y0+86,'',8 if col==3 else 10,
                GOLD,justify='center',tags='limits'))
            left=right
        c.tag_bind('limits','<Button-1>',self.toggle_high_bet_limits)
        c.tag_bind('limits','<Enter>',lambda _e:c.configure(cursor='hand2'))
        c.tag_bind('limits','<Leave>',lambda _e:c.configure(cursor=''))

    def _draw_progressive_panel(self):
        panel = tk.Frame(self.canvas,bg='#123C30',highlightbackground=GOLD,highlightthickness=2)
        self.progressive_panel=panel
        self.canvas.create_window(982,128,window=panel,width=290,height=118)
        tk.Label(panel,text='累进大奖',font=('Arial',24,'bold'),
                 bg='#315C40',fg='#F6D675').pack(fill=tk.X)
        self.progressive_amount_var = tk.StringVar(self,f'${self.game.progressive_amount:,.2f}')
        self.progressive_display = ProgressiveSevenSegmentDisplay(panel,self.progressive_amount_var,
            font=('Arial',24,'bold'),bg='#123C30',fg='#FFE29A')
        self.progressive_display.pack(pady=10)

    def _register_spot(self, seat, kind, cx, cy, border, label, angle=0):
        c,tag = self.canvas,'spot_'+seat+'_'+kind
        if label is not None:
            self._text(cx,cy,label,12 if kind in ('six_card','pair_plus') else 14,PANEL_BG,
                       angle=angle,justify='center',tags=tag)
        self.bet_spots[(seat,kind)] = dict(tag=tag,center=(cx,cy),border=border)
        c.tag_bind(tag,'<Button-1>',lambda _e,s=seat,k=kind:self.add_chip_to_bet(s,k))
        c.tag_bind(tag,'<Button-3>',lambda _e,s=seat,k=kind:self.reset_single_bet(s,k))
        c.tag_bind(tag,'<Enter>',lambda _e:c.configure(cursor='hand2'))
        c.tag_bind(tag,'<Leave>',lambda _e:c.configure(cursor=''))

    def _draw_main_bet_pair(self, seat, cx, ante_y, play_y):
        c = self.canvas
        color, fill = '#FFF5DE', self.ZONE_COLORS[seat]
        ante_tag, play_tag = 'spot_'+seat+'_ante', 'spot_'+seat+'_play'
        join_y = ante_y + 42
        play = c.create_rectangle(cx-83, join_y, cx+83, play_y+52,
            fill=fill, outline=color, width=3, tags=play_tag)
        c.create_polygon(cx,join_y,cx+56,play_y,cx,play_y+52,cx-56,play_y,
            fill=fill, outline=color, width=3, tags=play_tag)
        ante = c.create_polygon(cx,ante_y-42,cx+43,ante_y,cx,join_y,cx-43,ante_y,
            fill=fill, outline=color, width=3, tags=ante_tag)
        self._register_spot(seat,'ante',cx,ante_y,ante,'前注')
        self._register_spot(seat,'play',cx,play_y,play,'加注')


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
            fg=TITLE_FG,font_size=14,subtext='ENTER',subtext_font_size=10,draw_shadow=False)
        self.restart_button=self.create_control_button(862,638,1138,708,'再来一局(30)',self._return_all_chips,
            HEADER_BG,fg=TITLE_FG,font_size=17,draw_shadow=False)
        c.tag_bind(self.restart_button,'<Button-3>',self._inspect_completed_round)
        c.itemconfigure(self.restart_button,state='hidden')
        # 筹码区下方不放文字，也没有返回按钮。
        self._enter_binding=self.winfo_toplevel().bind('<Return>',lambda _e:
            self._return_all_chips() if self.game.stage in ('await_restart','credit_pending') else self.start_game(),add='+')


    def _sort_revealed_hands(self, sides, complete):
        """只移动三张手牌的显示位置，不改变实际发牌记录。"""
        motions=[]
        for side in sides:
            hand=self.game.dealer_hand if side=='Dealer' else self.game.hands[side]
            if not hand or side in self._sorted_sides:
                continue
            ordered=sort_hand_for_display(hand,evaluate_three_card_hand(hand))
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

    def _finish_blind_reveal(self):
        # 盲注手牌排序后，同时处理对子加注及同色输注，再翻开庄家及累进大奖牌。
        self.game.stage='side_settling';self._refresh()
        self._settle_side_bets([s for s in self.game.SEATS if s in self._blind_seats],
            self._open_dealer_rest,('pair_plus','same_color'),same_color_losses_only=True)


    def _after_dealer_reveal(self):
        def settle_dealer_side_bets():
            self._settle_side_bets([s for s in self.game.SEATS
                if self.game.decisions[s]!='inactive'],self._settle,('six_card','same_color'))
        self._sort_revealed_hands(['Dealer'],settle_dealer_side_bets)


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
        if abs(value)>=1000:return ThreeCardPokerGUI._compact(value)
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
        # 本金先画；常规盈利位于左上方，前注额外奖励位于右上方。
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
        return HAND_RANK_NAMES[evaluate_three_card_hand(hand)[0]]

    def _update_hand_title(self, side):
        hand=self.game.dealer_hand if side=='Dealer' else self.game.hands[side]
        name='庄家' if side=='Dealer' else self.SEAT_NAMES[side]
        self.canvas.itemconfigure(self.title_items[side],text=f'{name} - {self.hand_type_text(hand)}')

    def _collect_progressive_and_deal(self):
        for seat in self.game.SEATS:
            chip=self.visual_chips.pop((seat,'jackpot','stake'),None)
            if chip:self._animate_chip(chip['amount'],chip['xy'],self.HOUSE_CHIP_POS,duration=280)
        self.game.stage='dealing';self._refresh()
        sequence=self.game.round_deal_sequence
        self._deal_next(sequence,0)

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

    def _settle_side_bets(self, seats, complete, kinds=('pair_plus',), same_color_losses_only=False):
        transfers=[]
        for seat in seats:
            for kind in kinds:
                key=(seat,kind)
                if key in self._side_resolved:continue
                if kind=='same_color' and same_color_losses_only:
                    hand=self.game.hands[seat]
                    if len(hand)!=3 or len({card.suit in ('♥','♦') for card in hand})==1:
                        continue
                self._side_resolved.add(key)
                stake=self.game.bets[seat][kind]
                returned=self.game.settle_side_bet(seat,kind)
                transfers.extend(self._outcome_transfers(seat,kind,stake,returned))
        def done():
            for seat in seats:self._update_hand_title(seat)
            self._refresh();complete()
        self._run_chip_batch(transfers,done)

    def _open_dealer_rest(self):
        self.game.stage='showdown';self._refresh()
        sequence=[('Dealer',i) for i in range(3)]
        if any(b['jackpot'] for b in self.game.bets.values()):
            sequence += [('Progressive',i) for i in range(2)]
        self._reveal_next(sequence,0,self._after_dealer_reveal)

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
            self._notice_text_item=self._text(493,145,'庄家不及格',16,'#FFF1D1',state='hidden',tags='dealer_notice')
        self._notice_source=layer.resize((width,height),Image.Resampling.LANCZOS)
        self._notice_item=self.canvas.create_image(493,145,state='hidden',tags='dealer_notice')

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
        # 原加勒比窗口：730×750，九张一排，切牌位置高亮，滚动显示52张原始牌序。
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
            original=snapshot['images'][(card.suit,card.rank)]
            small_images[i]=ImageTk.PhotoImage(original.resize((60,90),Image.Resampling.LANCZOS),master=win)
        win._card_images=small_images
        for row in range(6):
            row_frame=tk.Frame(card_frame,bg='#f0f0f0');row_frame.pack(fill=tk.X)
            for col in range(9 if row<5 else 7):
                idx=row*9+col
                if idx>=52:break
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
        dialog.title('三张牌扑克 · 完整图解玩法')
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
                '玩家与庄家各持三张牌，以最终牌型决定主注胜负。',
                [
                    (
                        '游戏目标',
                        '',
                        [
                            (
                                '与庄家比牌',
                                '使用一副不含大小王的52张扑克牌。\n'
                                '有下注的玩家和庄家各获三张牌，不换牌；未下注的玩家不发牌。\n'
                                '另发两张累进大奖牌，仅用于累进大奖判奖。\n'
                                '选择加注后，先判断庄家是否及格，再进行主注结算。'
                            ),
                            (
                                '主注与边注',
                                '前注：参加主注比牌时设置的下注。\n'
                                '加注：继续与庄家比牌时支付的下注。\n'
                                '对子加注、六张牌外注与累进大奖：'
                                '分别按对应牌型独立判奖。\n'
                                '同色：按玩家三张牌及庄家三张牌的红黑颜色独立判奖。\n'
                                '\n'
                                '也可不下前注，只下对子加注，'
                                '并按需搭配其他边注。'
                            ),
                        ],
                        [],
                    ),
                    (
                        '一局如何进行',
                        '',
                        [
                            (
                                '① 设置下注',
                                '先选择筹码，设置前注或对子加注。\n'
                                '可另外下注六张牌外注、同色，或点击累进大奖灯。\n'
                                '已设置前注时，可提前设置等额加注。'
                            ),
                            (
                                '② 开始发牌',
                                '点击“开牌”。\n'
                                '依次发给有下注的玩家、庄家、累进；未下注的玩家跳过，累进只发前两轮。\n'
                                '庄家获三张牌，暂时全部盖住。\n'
                                '另发两张累进大奖牌；至少一家下注累进大奖时才翻开，否则保持盖牌。'
                            ),
                            (
                                '③ 弃牌或继续',
                                '有前注且未设置预加注时，可选择：\n'
                                '• 弃牌：失去前注，不再追加下注。\n'
                                '• 下注1倍：支付与前注相同的金额，继续比牌。\n'
                                '\n'
                                '已设置预加注，或前注为0且已下对子加注时，'
                                '发牌后自动进入摊牌。'
                            ),
                            (
                                '④ 开牌结算',
                                '庄家牌亮出；至少一家下注累进大奖时，累进牌才亮出。\n'
                                '主注按庄家资格及双方三张牌牌力结算。\n'
                                '对子加注、六张牌外注、同色及累进大奖分别判奖。\n'
                                '弃牌后，已购买的四项边注仍会结算。'
                            ),
                        ],
                        [],
                    ),
                ],
            ),
            (
                '下注 & 限红',
                '下注前请确认当前模式、下注金额及可用余额。',
                [
                    (
                        '下注项目',
                        '',
                        [],
                        [
                            (
                                '每项下注的用途',
                                ['项目', '下注方式', '作用'],
                                [
                                    [
                                        '前注',
                                        '参加主注比牌时设置',
                                        '与庄家比较三张牌',
                                    ],
                                    [
                                        '加注',
                                        '固定为前注的1倍',
                                        '继续与庄家比牌',
                                    ],
                                    [
                                        '对子加注',
                                        '可单独下注\n也可搭配前注',
                                        '按玩家自己的三张牌判奖',
                                    ],
                                    [
                                        '六张牌外注',
                                        '可选',
                                        '按玩家三张牌＋庄家三张牌判奖',
                                    ],
                                    [
                                        '同色',
                                        '可选',
                                        '按玩家三张牌及双方六张牌的红黑颜色判奖',
                                    ],
                                    [
                                        '累进大奖',
                                        '可选\n每局$2.50',
                                        '按玩家三张牌＋两张累进牌判奖',
                                    ],
                                ],
                            ),
                        ],
                    ),
                    (
                        '普通模式与高额模式',
                        '',
                        [],
                        [
                            (
                                '下注限额',
                                ['项目', '普通模式', '高额模式'],
                                [
                                    ['牌桌前注最低', '$10', '$100'],
                                    ['前注最高', '$10,000', '$50,000'],
                                    ['对子加注最高\n无前注时', '$5,000', '$50,000'],
                                    ['对子加注最高\n有前注时', '$2,500', '$25,000'],
                                    ['六张牌外注最高', '$2,500', '$12,500'],
                                    ['同色最高', '$2,500', '$12,500'],
                                    ['加注金额', '与前注相同', '与前注相同'],
                                    ['累进大奖费用', '$2.50', '$2.50'],
                                ],
                            ),
                        ],
                    ),
                    (
                        '下注操作',
                        '',
                        [
                            (
                                '添加或清除筹码',
                                '先选择筹码，再左键点击前注、对子加注'
                                '、六张牌外注或同色区域增加下注。\n'
                                '下注阶段可右键点击对应区域，将金额清零。\n'
                                '使用“重置下注”后，请另行确认累进大奖勾选状态。'
                            ),
                            (
                                '设置预加注',
                                '先设置前注，再点击加注区域。\n'
                                '每次点击会在0与前注金额之间切换。\n'
                                '预加注开启后，金额会随前注调整。\n'
                                '开始游戏时，预加注与其他下注一并扣除。'
                            ),
                            (
                                '不下前注时',
                                '前注为0时，必须设置对子加注才能开始。\n'
                                '可同时购买六张牌外注、同色或累进大奖。\n'
                                '本局不参与前注与加注比牌，也没有前注额外奖励。\n'
                                '不能只购买六张牌外注、同色或累进大奖开局。'
                            ),
                            (
                                '余额要求',
                                '开始游戏时，扣除已设置的全部下注。\n'
                                '未设置预加注时，加注金额暂不扣除。\n'
                                '看牌后选择“下注1倍”，'
                                '还需有足够余额支付与前注相同的金额。'
                            ),
                            (
                                '重复下注',
                                '“重复下注”恢复上次开局时的下注设置。\n'
                                '恢复后请确认当前限额，再点击“开牌”。\n'
                                '上次看牌后才追加的加注，'
                                '不会因此变成下一局的预加注。'
                            ),
                        ],
                        [],
                    ),
                ],
            ),
            (
                '获胜条件 & 赔率',
                '赔率表示净赢倍数；各项返还金额的计算方式见下方说明。',
                [
                    (
                        '庄家资格与主注结算',
                        '',
                        [
                            (
                                '庄家何时及格',
                                '满足以下任一条件即及格：\n'
                                '• 持有对子或更高牌型。\n'
                                '• 牌型为高牌，最高一张为Q、K或A。\n'
                                '\n'
                                '只有在高牌且最高点数为J或以下时，庄家才不及格。\n'
                                '例如2-2-5属于对子，即使没有Q、K或A也及格。'
                            ),
                            (
                                '比牌范围',
                                '主注只比较玩家自己的三张牌与庄家自己的三张牌。\n'
                                '先比较牌型，牌型相同再比较相关点数。\n'
                                '两张累进大奖牌不参与主注比牌。'
                            ),
                        ],
                        [
                            (
                                '主注结算结果',
                                ['情形', '前注', '加注'],
                                [
                                    ['玩家弃牌', '失去前注', '不再追加'],
                                    ['庄家不及格', '净赢1:1\n并退本金', '退还本金'],
                                    ['庄家及格\n玩家胜', '净赢1:1\n并退本金', '净赢1:1\n并退本金'],
                                    ['庄家及格\n双方平局', '退还本金', '退还本金'],
                                    ['庄家及格\n玩家负', '失去前注', '失去加注'],
                                ],
                            ),
                        ],
                    ),
                    (
                        '前注额外奖励',
                        '符合指定三张牌牌型时，在常规主注结算之外另加奖励。',
                        [
                            (
                                '奖励条件',
                                '必须已下前注，并继续进入摊牌。\n'
                                '奖励按玩家自己的三张牌计算。\n'
                                '无论主注获胜、平局或落败，符合牌型均可获得奖励。\n'
                                '庄家是否及格，不影响此项奖励。\n'
                                '弃牌时不发放前注额外奖励。'
                            ),
                            (
                                '奖励金额',
                                '下表列出额外奖金，不重复计算前注本金。\n'
                                '这笔奖金会与前注常规返还合并，显示在Ante格子。\n'
                                '\n'
                                '例如前注$10，玩家持三条且主注获胜：\n'
                                '常规返还2倍，额外奖励4倍，合计6倍。\n'
                                'Ante：$10 * 6 = $60。'
                            ),
                        ],
                        [
                            (
                                '额外奖励表',
                                ['玩家三张牌牌型', '额外奖金'],
                                [
                                    ['迷你皇家同花顺', '前注×5'],
                                    ['同花顺', '前注×5'],
                                    ['三条', '前注×4'],
                                    ['顺子', '前注×1'],
                                    ['同花、对子及高牌', '无额外奖励'],
                                ],
                            ),
                        ],
                    ),
                    (
                        '对子加注',
                        '仅使用玩家自己的三张牌判奖。',
                        [
                            (
                                '判奖条件',
                                '对子或以上中奖，高牌不中奖。\n'
                                '无需击败庄家，也不要求庄家及格。\n'
                                '即使弃牌，已购买的对子加注仍会结算。'
                            ),
                            (
                                '返还金额',
                                '中奖返还包含对子加注本金。\n'
                                '例如下注$10并组成顺子，赔率为6:1：\n'
                                '净赢$60，连同本金共返还$70。'
                            ),
                        ],
                        [
                            (
                                '对子加注赔率表',
                                ['玩家三张牌牌型', '净赢赔率', '含本金返还'],
                                [
                                    ['迷你皇家同花顺', '100:1', '下注×101'],
                                    ['同花顺', '40:1', '下注×41'],
                                    ['三条', '30:1', '下注×31'],
                                    ['顺子', '6:1', '下注×7'],
                                    ['同花', '3:1', '下注×4'],
                                    ['对子', '1:1', '下注×2'],
                                    ['高牌', '不中奖', '0'],
                                ],
                            ),
                        ],
                    ),
                    (
                        '同色',
                        '按红黑颜色判奖，不要求花色相同。',
                        [
                            (
                                '判奖条件',
                                '红桃♥、方块♦属于红色；黑桃♠、梅花♣属于黑色。\n'
                                '玩家三张牌全红或全黑，赔付3:1。\n'
                                '玩家三张牌与庄家三张牌，共六张全红或全黑，赔付4:1。\n'
                                '符合六张同色时只按4:1赔付一次，不叠加3:1。'
                            ),
                            (
                                '独立结算',
                                '玩家三张牌翻开并排序后，与对子加注同时结算；红黑混色收走同色下注。\n'
                                '玩家三张牌全红或全黑，保留下注至庄家开牌后结算。\n'
                                '不要求主注获胜，也不要求庄家及格；弃牌后仍会结算。\n'
                                '两张累进大奖牌不参与同色判奖。\n'
                                '返还包含本金：下注$10，3:1返还$40，4:1返还$50。'
                            ),
                        ],
                        [
                            (
                                '同色赔率表',
                                ['条件', '净赢赔率', '含本金返还'],
                                [
                                    ['双方六张牌全红或全黑', '4:1', '下注×5'],
                                    ['仅玩家三张牌全红或全黑', '3:1', '下注×4'],
                                    ['玩家三张牌红黑混色', '不中奖', '0'],
                                ],
                            ),
                        ],
                    ),
                    (
                        '六张牌外注',
                        '使用玩家三张牌与庄家三张牌，共六张牌判奖。',
                        [
                            (
                                '组合方式',
                                '若六张牌为同花色的9-10-J-Q-K-A，'
                                '按六张超级皇家同花顺赔付。\n'
                                '其他情况从六张牌中选出最佳五张，按下表赔付。\n'
                                '每局只按最高符合项目赔付一次，不叠加各个组合。'
                            ),
                            (
                                '独立结算',
                                '不要求玩家主注获胜，也不要求庄家及格。\n'
                                '弃牌后仍会结算。\n'
                                '两张累进大奖牌不参与六张牌外注。'
                            ),
                        ],
                        [
                            (
                                '六张牌外注赔率表',
                                ['牌型', '净赢赔率', '含本金返还'],
                                [
                                    ['六张超级皇家同花顺\n同花色9-10-J-Q-K-A', '10000:1', '下注×10001'],
                                    ['皇家同花顺', '1000:1', '下注×1001'],
                                    ['同花顺', '200:1', '下注×201'],
                                    ['四条', '50:1', '下注×51'],
                                    ['葫芦', '20:1', '下注×21'],
                                    ['同花', '15:1', '下注×16'],
                                    ['顺子', '10:1', '下注×11'],
                                    ['三条', '5:1', '下注×6'],
                                    ['两对、对子及高牌', '不中奖', '0'],
                                ],
                            ),
                        ],
                    ),
                    (
                        '累进大奖',
                        '开局前勾选参与，每局费用为$2.50。',
                        [
                            (
                                '使用哪些牌',
                                '玩家自己的三张牌＋两张累进大奖牌，共五张。\n'
                                '不使用庄家的三张牌。\n'
                                '必须按这五张牌组成的实际牌型判奖。'
                            ),
                            (
                                '独立判奖',
                                '无需击败庄家，也不要求庄家及格。\n'
                                '即使玩家弃牌，已参与的累进大奖仍会判奖。'
                            ),
                            (
                                '奖金计算',
                                '下表列出直接发放的奖金，不另退$2.50参与费用。\n'
                                '百分比奖励以本次派彩计算时的奖池金额为基准。\n'
                                '普通模式与高额模式使用相同奖金标准。'
                            ),
                        ],
                        [
                            (
                                '累进大奖奖金表',
                                ['五张牌牌型', '奖金'],
                                [
                                    ['皇家同花顺', '当前奖池的100%'],
                                    ['同花顺', '当前奖池的10%'],
                                    ['四条', '$1,250'],
                                    ['葫芦', '$375'],
                                    ['同花', '$250'],
                                    ['顺子及以下', '不中奖'],
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            (
                '牌型等级表',
                '以下为三张牌的等级顺序，适用于主注比牌及对子加注。',
                [
                    (
                        '七种牌型',
                        '由强到弱排列；图片为牌型示例，不代表唯一组成方式。',
                        [],
                        [
                            (
                                '牌型与牌例',
                                ['等级', '牌型', '说明', '牌例'],
                                [
                                    [
                                        '1',
                                        '迷你皇家同花顺',
                                        '同花A-K-Q',
                                        (
                                            '__CARD_IMAGES__',
                                            (('♥', 'A'), ('♥', 'K'), ('♥', 'Q'))
                                        ),
                                    ],
                                    [
                                        '2',
                                        '同花顺',
                                        '同花且连续',
                                        (
                                            '__CARD_IMAGES__',
                                            (('♣', '8'), ('♣', '7'), ('♣', '6'))
                                        ),
                                    ],
                                    [
                                        '3',
                                        '三条',
                                        '三张同点',
                                        (
                                            '__CARD_IMAGES__',
                                            (('♥', '9'), ('♣', '9'), ('♠', '9'))
                                        ),
                                    ],
                                    [
                                        '4',
                                        '顺子',
                                        '连续非同花',
                                        (
                                            '__CARD_IMAGES__',
                                            (('♥', '7'), ('♠', '6'), ('♦', '5'))
                                        ),
                                    ],
                                    [
                                        '5',
                                        '同花',
                                        '同花不连续',
                                        (
                                            '__CARD_IMAGES__',
                                            (('♣', 'K'), ('♣', '10'), ('♣', '7'))
                                        ),
                                    ],
                                    [
                                        '6',
                                        '对子',
                                        '两张同点',
                                        (
                                            '__CARD_IMAGES__',
                                            (('♥', 'A'), ('♣', 'A'), ('♠', 'K'))
                                        ),
                                    ],
                                    [
                                        '7',
                                        '高牌',
                                        '无上述牌型',
                                        (
                                            '__CARD_IMAGES__',
                                            (('♥', 'A'), ('♣', 'K'), ('♦', 'J'))
                                        ),
                                    ],
                                ],
                            ),
                        ],
                    ),
                    (
                        '同牌型如何分胜负',
                        '',
                        [
                            (
                                '点数与花色',
                                '通常点数顺序：A＞K＞Q＞J＞10＞9＞…＞2。\n'
                                '花色不分大小，也不用于打破平局。'
                            ),
                            (
                                '顺子与同花顺',
                                '比较顺子最高点数。\n'
                                'A-K-Q为最大三张顺子；同花色时为迷你皇家同花顺。\n'
                                '3-2-A按3高计算，是最小三张顺子。\n'
                                'K-A-2不算顺子。'
                            ),
                            (
                                '三条与对子',
                                '三条：比较三张相同牌的点数。\n'
                                '对子：先比较对子点数，相同时再比较剩余单牌。'
                            ),
                            (
                                '同花与高牌',
                                '将三张牌从大到小逐张比较。\n'
                                '最高牌相同则比较第二张，再比较第三张。\n'
                                '双方牌型及全部比较点数相同，即为平局。'
                            ),
                            (
                                '高牌示例说明',
                                '不同花色的A-K-J属于A高牌：\n'
                                '没有对子，不构成顺子，也不是同花。\n'
                                '\n'
                                'A-K-Q点数连续，属于顺子，不能作为高牌示例。\n'
                                '若A-K-Q还是同一花色，则属于迷你皇家同花顺。'
                            ),
                        ],
                        [],
                    ),
                ],
            ),
            (
                '特别事项',
                '区分三张牌与五张牌判定，并核对每局返还金额。',
                [
                    (
                        '预加注与高额模式',
                        '',
                        [
                            (
                                '预加注会自动继续',
                                '预加注表示看牌前已决定支付与前注相同的金额继续。\n'
                                '发牌后自动进入摊牌。\n'
                                '本局不再出现弃牌或加注的选择。'
                            ),
                            (
                                '高额模式的变化',
                                '提高前注、对子加注、六张牌外注与同色限额，'
                                '并更换可选筹码。\n'
                                '主注、前注额外奖励及各项边注的赔付标准保持一致。\n'
                                '累进大奖参与费用保持为$2.50。\n'
                                '切换模式后，请重新确认下注设置。'
                            ),
                        ],
                        [],
                    ),
                    (
                        '牌型使用范围',
                        '',
                        [
                            (
                                '三张牌的特殊顺序',
                                '三张牌比牌时：三条大于顺子，顺子大于同花。\n'
                                '主注与对子加注使用“牌型等级表”中的七种牌型。'
                            ),
                            (
                                '五张牌边注',
                                '六张牌外注通常从六张中选最佳五张。\n'
                                '累进大奖使用玩家三张牌与两张累进牌组成的五张牌。\n'
                                '这两项按各自五张牌赔付表判奖，'
                                '不套用三张牌的等级顺序。'
                            ),
                            (
                                '迷你皇家与皇家同花顺',
                                '迷你皇家同花顺：同花色的A-K-Q，共三张。\n'
                                '皇家同花顺：同花色的A-K-Q-J-10，共五张。\n'
                                '持有三张迷你皇家同花顺，'
                                '不代表已组成累进大奖所需的五张皇家同花顺。'
                            ),
                        ],
                        [],
                    ),
                    (
                        '金额核对',
                        '',
                        [
                            (
                                '各下注格子的金额格式',
                                '显示格式：\n'
                                '$本金 * 返还倍数 = $该格子获胜总金额\n'
                                '\n'
                                '这里的本金是该格子原先下注的金额。\n'
                                '返还倍数包含应退本金及对应奖金。\n'
                                'Ante格子的返还倍数还包含前注额外奖励。\n'
                                '\n'
                                '例如净赢赔率1:1，含本金返还倍数为2。\n'
                                '只退本金时，返还倍数为1。\n'
                                '没有任何返还时，返还倍数为0。'
                            ),
                            (
                                '返还金额与净利润',
                                '每个格子的获胜总金额，表示该项结算返还，'
                                '不等于净利润。\n'
                                '“上局获胜”显示各项结算返还的合计。\n'
                                '累进大奖按奖金表直接发放。\n'
                                '\n'
                                '本局净盈亏＝结算返还总额－本局实际扣除的全部下注。'
                            ),
                            (
                                '示例一：庄家不及格',
                                '前注$10，加注$10，未购买边注。\n'
                                '玩家：A-K-J，不同花色，高牌。\n'
                                '庄家：J-8-4，不同花色，高牌，庄家不及格。\n'
                                '\n'
                                '前注获胜，加注退还；玩家没有前注额外奖励。\n'
                                'Ante：$10 * 2 = $20\n'
                                'Play：$10 * 1 = $10\n'
                                '\n'
                                '合计返还：$20＋$10＝$30。\n'
                                '本局净赢：$30－$20＝$10。'
                            ),
                            (
                                '示例二：玩家三条获胜',
                                '前注$10，加注$10，未购买边注。\n'
                                '玩家：9-9-9，三条。\n'
                                '庄家：8-8-2，对子，庄家及格。\n'
                                '\n'
                                '玩家三条大于庄家对子，前注与加注均获胜。\n'
                                'Ante常规返还2倍，另加三条奖励4倍，共6倍。\n'
                                'Ante：$10 * 6 = $60\n'
                                'Play：$10 * 2 = $20\n'
                                '\n'
                                '合计返还：$60＋$20＝$80。\n'
                                '本局净赢：$80－$20＝$60。'
                            ),
                            (
                                '示例三：玩家顺子 VS 庄家三条',
                                '前注$10，加注$10，未购买边注。\n'
                                '玩家：9-8-7，不同花色，顺子。\n'
                                '庄家：Q-Q-Q，三条，庄家及格。\n'
                                '\n'
                                '三张牌规则中，三条大于顺子，玩家主注落败。\n'
                                '前注与加注的常规返还均为0。\n'
                                '玩家已继续摊牌，仍获得顺子额外奖励1倍前注。\n'
                                'Ante：$10 * 1 = $10\n'
                                'Play：$10 * 0 = $0\n'
                                '\n'
                                'Ante的$10来自顺子额外奖励，并非退还前注本金。\n'
                                '合计返还：$10＋$0＝$10。\n'
                                '本局净盈亏：$10－$20＝-$10，即净输$10。'
                            ),
                            (
                                '示例四：迷你皇家同花顺获胜',
                                '前注$10，加注$10，未购买边注。\n'
                                '玩家：同花色A-K-Q，迷你皇家同花顺。\n'
                                '庄家：9-9-2，对子，庄家及格。\n'
                                '\n'
                                '玩家获胜，前注与加注均按1:1赔付。\n'
                                'Ante常规返还2倍，另加牌型奖励5倍，共7倍。\n'
                                'Ante：$10 * 7 = $70\n'
                                'Play：$10 * 2 = $20\n'
                                '\n'
                                '合计返还：$70＋$20＝$90。\n'
                                '本局净赢：$90－$20＝$70。'
                            ),
                        ],
                        [],
                    ),
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
        tk.Label(header, text='三张牌扑克 · 完整图解玩法', font=(font_name, 20, 'bold'),
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

        tk.Button(header, text='关闭  ESC', command=close_dialog,
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


def main(initial_balance=10000, username="Guest", *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """嵌入现有 Tk 根窗口；未传 parent 时仍可独立运行。"""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return ThreeCardPokerGUI(
            parent, actual_balance, actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("三张牌扑克")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = ThreeCardPokerGUI(root, actual_balance, actual_user)
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
