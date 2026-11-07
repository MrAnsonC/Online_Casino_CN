# Lunar Poker: Caribbean UI migration, 2026-10-04.
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
# 仿轮盘 UI 颜色（取自 Three_Card_Poker）
# =========================================================
ROOT_BG = "#1B3D31"
CYAN = "#007502"
TEXT = "#ffffff"
RED = "#ff2a23"
BLACK = "#050505"
DARK_BLUE = "#173f66"
BET_BLUE = "#326D9C"
GOLD = "#D4AF37"
PANEL_BG = "#F2E6C9"
HEADER_BG = "#D8B46A"
TITLE_FG = "#2A1B08"

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    9: '皇家同花顺',
    8: '同花顺',
    7: '四条',
    6: '葫芦',
    5: '同花',
    4: '顺子',
    3: '三条',
    2: '两对',
    1: '对子',
    0: '高牌'
}

RAISE_PAYOUT = {
    9: 100,  # 皇家同花顺
    8: 50,
    7: 20,
    6: 7,
    5: 5,
    4: 4,
    3: 3,
    2: 2,
    1: 1,
    0: 1
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
# Progressive 文件加载与保存 (Key: 'CSP')
# =========================================================
def load_jackpot():
    path = str(_progressive_file)
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
        return True, default_jackpot
    return True, default_jackpot

def save_jackpot(jackpot):
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
            item['jackpot'] = jackpot
            found = True
            break
    if not found:
        data.append({"Games": "Progressive_2.50", "jackpot": jackpot})
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# =========================================================
# 牌局历史日志（加勒比扑克）
# =========================================================
def lunar_log_path() -> str:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Lunar_Poker.json")

def save_lunar_history(deck, player_cards, dealer_cards, result_info=None):
    log_path = lunar_log_path()
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
# 扑克牌类与牌堆（与 Three_Card_Poker 一致）
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
        if not isinstance(n, int) or n < 0 or self.pointer+n > len(self.indexes):
            raise ValueError('牌堆中没有足够的牌。')
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt

# =========================================================
# 五张牌评估与比较（保留原逻辑）
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

def best_five_cards(cards):
    """比较及显示共用同一组最佳五张；第六张不参与平局判定。"""
    if len(cards) < 5:
        return list(cards)
    return list(max(combinations(cards, 5), key=lambda group: evaluate_five_card_hand(group)))

def evaluate_best_hand(cards):
    return evaluate_five_card_hand(best_five_cards(cards))

def compare_hands(hand1, hand2):
    first, second = evaluate_best_hand(hand1), evaluate_best_hand(hand2)
    return (first > second) - (first < second)

def sort_hand_for_display(hand, hand_eval):
    rank = hand_eval[0]
    if rank in [4,8,9]:  # 顺子类
        values = [c.value for c in hand]
        if 14 in values and 2 in values and len(set(values)) == 5:
            return sorted(hand, key=lambda c: 1 if c.value == 14 else c.value)
        else:
            return sorted(hand, key=lambda c: c.value)
    else:
        counts = Counter(c.value for c in hand)
        return sorted(hand, key=lambda c: (counts[c.value], c.value), reverse=True)

# =========================================================
# 游戏逻辑类（加勒比扑克）
# =========================================================
# 两手牌状态相互独立；整桌共用一副牌、庄家手牌及累进奖池。
SUPER_BONUS_PAYOUT = {
    "四条": 250,          # 四条 250:1
    "五张脸牌": 120,      # 五张脸牌 (J,Q,K) 120:1
    "葫芦": 100,          # 葫芦 100:1
    "同花": 60,           # 同花 60:1 (含同花顺/皇家同花顺)
    "顺子": 30,           # 顺子 30:1
    "三条": 8,            # 三条 8:1
    "Ace-king-queen": 5,  # 手牌中有A,K,Q 5:1
    "同颜色": 2            # 五张牌同色（红或黑）2:1
}
INSTANT_PAYOUT = {
    9: 1000,  # 皇家同花顺 1000:1
    8: 200    # 同花顺 200:1
}

def evaluate_super_bonus(hand):
    """
    评估一手5张牌是否符合超级赌注赔付条件
    返回 (赔付名称, 赔付倍数) 或 (None, 0)
    """
    if not hand or len(hand) < 5:
        return None, 0

    # 检查四条
    rank, values = evaluate_five_card_hand(hand)
    if rank == 7:
        return "四条", SUPER_BONUS_PAYOUT["四条"]

    # 检查五张脸牌 (J, Q, K)
    face_cards = [c for c in hand if c.rank in ['J', 'Q', 'K']]
    if len(face_cards) == 5:
        return "五张脸牌", SUPER_BONUS_PAYOUT["五张脸牌"]

    # 检查葫芦
    if rank == 6:
        return "葫芦", SUPER_BONUS_PAYOUT["葫芦"]

    # 检查同花/同花顺/皇家同花顺
    if rank in [5, 8, 9]:  # 同花、同花顺、皇家同花顺
        return "同花", SUPER_BONUS_PAYOUT["同花"]

    # 检查顺子
    if rank == 4:
        return "顺子", SUPER_BONUS_PAYOUT["顺子"]

    # 检查三条
    if rank == 3:
        return "三条", SUPER_BONUS_PAYOUT["三条"]

    # 检查 Ace-King-Queen (手牌中同时有A、K、Q)
    ranks_in_hand = [c.rank for c in hand]
    if 'A' in ranks_in_hand and 'K' in ranks_in_hand and 'Q' in ranks_in_hand:
        return "Ace-king-queen", SUPER_BONUS_PAYOUT["Ace-king-queen"]

    # 检查同颜色 (全红或全黑)
    suits_in_hand = [c.suit for c in hand]
    all_red = all(s in ['♥', '♦'] for s in suits_in_hand)
    all_black = all(s in ['♠', '♣'] for s in suits_in_hand)
    if all_red or all_black:
        return "同颜色", SUPER_BONUS_PAYOUT["同颜色"]

    return None, 0

class LunarPokerGame:
    """双玩家共用庄家；每家拥有独立换牌决定及不可重复的结算记录。"""
    SEATS = ('Player1', 'Player2')
    MIN_PROGRESSIVE = 271288.59

    def __init__(self):
        self.progressive_amount = load_jackpot()[1]
        self.min_progressive = self.MIN_PROGRESSIVE
        self.reset_game()

    @staticmethod
    def empty_bet():
        return dict(ante=0.0, super_bonus=0.0, dealer_super_bonus=0.0, jackpot=0.0, play=0.0,
                    player_change=0.0, dealer_change=0.0)

    def reset_game(self):
        self.deck = None
        self.deal_sequence = []
        self.hands = {s: [] for s in self.SEATS}
        self.original_hands = {s: [] for s in self.SEATS}
        self.dealer_hand = []
        self.original_dealer_hand = []
        self.bets = {s: self.empty_bet() for s in self.SEATS}
        self.decisions = {s: 'inactive' for s in self.SEATS}
        self.dealer_choices = {s: 'inactive' for s in self.SEATS}
        self.change_used = {s: False for s in self.SEATS}
        self.buy_used = {s: False for s in self.SEATS}
        self.instant_returns = {}
        self.outcomes = {}
        self.stage = 'betting'
        self.settlement = None
        self.side_returns = {}
        self.dealer_side_returns = {}
        self.refunded_bets = {}
        self.dealer_exchanged = False
        self.discarded_cards = []

    @staticmethod
    def dealer_qualifies_hand(hand):
        return (len(hand) == 5 and (evaluate_five_card_hand(hand)[0] >= 1
                or {'A', 'K'}.issubset({c.rank for c in hand})))

    def dealer_qualifies(self):
        return self.dealer_qualifies_hand(self.dealer_hand)

    def start_round(self, bets, balance, high_bet_mode=False):
        if self.stage != 'betting':
            raise ValueError('本局尚未结束。')
        minimum, maximum = (100, 50000) if high_bet_mode else (10, 10000)
        prepared, refunded = {}, {}
        for seat in self.SEATS:
            b = {k: float(bets[seat].get(k, 0)) for k in self.empty_bet()}
            if any(not math.isfinite(v) or v < 0 for v in b.values()):
                raise ValueError('下注金额必须是有限的非负数。')
            if b['play']:
                raise ValueError('下注阶段不能下注加注，请在开牌后的玩家决定阶段选择“下注2X”。')
            if b['player_change'] or b['dealer_change']:
                raise ValueError('P、D 费用只在本局对应的决定阶段支付。')
            if not b['ante']:
                if any(b.values()): refunded[seat] = dict(b)
                prepared[seat] = self.empty_bet()
                continue
            if not minimum <= b['ante'] <= maximum:
                raise ValueError(f'每手前注须为 ${minimum:,} 至 ${maximum:,}。')
            if any(b[k] > b['ante'] or b[k] > maximum
                   for k in ('super_bonus', 'dealer_super_bonus')):
                raise ValueError('玩家及庄家超级红利各自不得超过该手前注。')
            if b['jackpot'] not in (0, 2.5):
                raise ValueError('累进大奖每手固定 $2.50。')
            prepared[seat] = b
        if not any(b['ante'] for b in prepared.values()):
            raise ValueError('请至少为一手牌下前注。')
        charged = round(sum(sum(b.values()) for b in prepared.values()), 2)
        reserve = sum(2*b['ante'] for b in prepared.values() if b['ante'])
        if charged+reserve > balance:
            raise ValueError('余额不足以支付下注及两手可能需要的加注。')
        deck = Deck()
        hands, dealer = {s: [] for s in self.SEATS}, []
        active = tuple(s for s in self.SEATS if prepared[s]['ante'])
        sequence = [(side, i) for i in range(5) for side in (*active, 'Dealer')]
        for side, _ in sequence:
            (dealer if side == 'Dealer' else hands[side]).extend(deck.deal(1))
        self.deck, self.hands, self.dealer_hand = deck, hands, dealer
        self.original_hands = {s: list(h) for s, h in hands.items()}
        self.deal_sequence, self.bets, self.refunded_bets = sequence, prepared, refunded
        self.decisions = {s: ('pending' if prepared[s]['ante'] else 'inactive') for s in self.SEATS}
        self.stage = 'dealing'
        return charged

    def pending_raise_reserve(self, exclude=None):
        return sum(self.bets[s]['ante']*2 for s in self.SEATS
                   if s != exclude and self.decisions[s] == 'pending')

    def decide(self, seat, action, balance):
        if self.stage != 'decision' or self.decisions.get(seat) != 'pending':
            return 0.0
        if action not in ('play', 'fold'):
            raise ValueError('无效的决定。')
        cost = self.bets[seat]['ante']*2 if action == 'play' else 0.0
        if cost > balance:
            raise ValueError('余额不足以加注。')
        self.bets[seat]['play'], self.decisions[seat] = cost, action
        return cost

    def buy_or_exchange(self, seat, indices, balance):
        if self.stage != 'decision' or self.decisions.get(seat) != 'pending' or self.change_used[seat]:
            raise ValueError('每手只可买牌或换牌一次。')
        selected = sorted(set(indices))
        hand = self.hands[seat]
        if len(hand) != 5 or any(not isinstance(i, int) or i < 0 or i >= 5 for i in selected):
            raise ValueError('选择的手牌无效。')
        cost = self.bets[seat]['ante']
        if cost+self.pending_raise_reserve() > balance:
            raise ValueError('余额不足以支付买牌/换牌费用并保留两手加注。')
        buying = len(selected) <= 1
        new = self.deck.deal(1 if buying else len(selected))
        discarded = [] if buying else [hand[i] for i in selected]
        kept = list(hand) if buying else [c for i, c in enumerate(hand) if i not in selected]
        self.hands[seat] = kept + new
        self.discarded_cards.extend(discarded)
        self.change_used[seat], self.buy_used[seat] = True, buying
        self.bets[seat]['player_change'] = cost
        return dict(mode='buy' if buying else 'exchange', cost=cost,
                    discarded=discarded, kept=kept, new=new, selected=selected)

    def check_instant(self, seat):
        if seat in self.instant_returns:
            return self.instant_returns[seat]
        if self.decisions[seat] not in ('pending', 'play'):
            return 0.0
        rank = evaluate_five_card_hand(self.original_hands[seat])[0]
        if rank not in INSTANT_PAYOUT:
            return 0.0
        # 保留原 Lunar 的立即支付金额；该手无需支付加注。
        returned = self.bets[seat]['ante'] * INSTANT_PAYOUT[rank]
        self.instant_returns[seat] = returned
        self.decisions[seat] = 'instant'
        return returned

    def settle_super_bonus(self, seat):
        if seat not in self.side_returns:
            _, multiplier = evaluate_super_bonus(self.original_hands[seat])
            stake = self.bets[seat]['super_bonus']
            self.side_returns[seat] = round(stake*(multiplier+1), 2) if multiplier else 0.0
        return self.side_returns[seat]

    def settle_dealer_super_bonus(self, seat):
        """庄家边注独立按初始五张判奖，换牌及玩家弃牌不改变结果。"""
        if len(self.original_dealer_hand) != 5:
            raise ValueError('庄家初始五张牌开牌后才能结算庄家超级红利。')
        if seat not in self.dealer_side_returns:
            _, multiplier = evaluate_super_bonus(self.original_dealer_hand)
            stake = self.bets[seat]['dealer_super_bonus']
            self.dealer_side_returns[seat] = round(stake*(multiplier+1), 2) if multiplier else 0.0
        return self.dealer_side_returns[seat]

    def prepare_dealer_choices(self):
        if self.stage != 'showdown' or 'pending' in self.decisions.values():
            raise ValueError('两家完成玩家决定并开庄家牌后才可决定庄家换牌。')
        self.original_dealer_hand = list(self.dealer_hand)
        self.dealer_choices = {s: ('pending' if self.decisions[s] == 'play'
                                  and not self.dealer_qualifies() else 'inactive') for s in self.SEATS}
        self.stage = 'dealer_decision'

    def choose_dealer_exchange(self, seat, exchange, balance):
        if self.stage != 'dealer_decision' or self.dealer_choices.get(seat) != 'pending':
            return 0.0
        cost = self.bets[seat]['ante'] if exchange else 0.0
        if cost > balance:
            raise ValueError('余额不足支付庄家换牌费用。')
        self.bets[seat]['dealer_change'] = cost
        self.dealer_choices[seat] = 'exchange' if exchange else 'skip'
        return cost

    def exchange_dealer_card(self):
        if self.dealer_exchanged:
            return None
        if self.stage != 'dealer_decision' or 'pending' in self.dealer_choices.values():
            raise ValueError('请等待每家完成庄家换牌决定。')
        if not any(v == 'exchange' for v in self.dealer_choices.values()):
            return None
        index = max(range(5), key=lambda i: self.dealer_hand[i].value)
        new = self.deck.deal(1)[0]
        old = self.dealer_hand[index]
        self.dealer_hand[index] = new
        self.discarded_cards.append(old)
        self.dealer_exchanged = True
        return index, old, new

    def settle_seat(self, seat, after_exchange=False):
        if seat in self.outcomes:
            return self.outcomes[seat]
        if self.stage != 'dealer_decision' or 'pending' in self.dealer_choices.values():
            raise ValueError('每家完成庄家换牌决定后才能结算。')
        if self.decisions[seat] == 'inactive':
            return None
        chose_exchange = self.dealer_choices[seat] == 'exchange'
        if chose_exchange != after_exchange or (after_exchange and not self.dealer_exchanged):
            raise ValueError('该手必须使用其选择对应的庄家手牌结算。')
        dealer = self.dealer_hand if after_exchange else self.original_dealer_hand
        b, hand = self.bets[seat], self.hands[seat]
        rank = evaluate_best_hand(hand)[0]
        d = dict(ante=0.0, play=0.0, super_bonus=self.settle_super_bonus(seat),
                 dealer_super_bonus=self.settle_dealer_super_bonus(seat), bonus=0.0)
        if self.decisions[seat] == 'instant':
            d['ante'], d['play'] = self.instant_returns[seat], b['play']
            winner, message = 'player', '原始同花顺/皇家同花顺立即支付'
        elif self.decisions[seat] == 'fold':
            winner, message = 'fold', '已弃牌'
        elif not self.dealer_qualifies_hand(dealer):
            d['ante'], d['play'] = b['ante']*2, b['play']
            winner, message = 'player', ('庄家换牌后仍不及格' if after_exchange else '庄家不及格') + '：前注1:1，加注退回'
        else:
            comparison = compare_hands(hand, dealer)
            if comparison > 0 or (comparison == 0 and after_exchange and self.buy_used[seat]):
                d['ante'], d['play'] = b['ante'], b['play']*(RAISE_PAYOUT[rank]+1)
                winner, message = 'player', '玩家获胜：前注退回，加注按牌型支付'
            elif comparison == 0:
                d['ante'], d['play'] = b['ante'], b['play']
                winner, message = 'push', '平局：前注、加注退回'
            else:
                d['ante'], d['play'] = 0.0, 0.0
                winner, message = 'dealer', ('庄家换牌后获胜' if after_exchange else '庄家获胜') + '：前注及加注全输'
        original_rank = evaluate_five_card_hand(self.original_hands[seat])[0]
        if b['jackpot']:
            d['bonus'] = round({9: self.progressive_amount, 8: self.progressive_amount*.1,
                                7: 1250.0, 6: 375.0, 5: 250.0}.get(original_rank, 0.0), 2)
        d = {k: round(v, 2) for k, v in d.items()}
        returned, stake = round(sum(d.values()), 2), round(sum(b.values()), 2)
        outcome = dict(winner=winner, message=message, details=d, returned=returned,
                       stake=stake, net=round(returned-stake, 2), after_exchange=after_exchange,
                       dealer_cards=[str(c) for c in dealer],
                       original_cards=[str(c) for c in self.original_hands[seat]])
        self.outcomes[seat] = outcome
        return outcome

    def settle(self):
        if self.settlement is not None:
            return self.settlement
        if self.stage != 'dealer_decision' or 'pending' in self.dealer_choices.values():
            raise ValueError('请先完成庄家换牌决定及每家结算。')
        active = [s for s in self.SEATS if self.decisions[s] != 'inactive']
        if any(s not in self.outcomes for s in active):
            raise ValueError('先依次完成原庄家及换牌庄家的分家结算。')
        total_bonus = sum(r['details']['bonus'] for r in self.outcomes.values())
        contribution = sum((sum(b.values())-b['jackpot'])*.001+b['jackpot']*.95 for b in self.bets.values())
        self.progressive_amount = round(max(self.MIN_PROGRESSIVE,
            max(self.MIN_PROGRESSIVE, self.progressive_amount-total_bonus)+contribution), 2)
        self.stage = 'settled'
        self.settlement = dict(hands=dict(self.outcomes),
            returned=round(sum(r['returned'] for r in self.outcomes.values()), 2))
        return self.settlement


class LunarPokerGUI(tk.Frame):
    WIDTH, HEIGHT = 1150, 750
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    DEAL_CARD_MS = 224 / .85
    DEAL_MOVE_MS = (128 / .75) / .85
    BET_CHIP_RADIUS = 16 * 4 / 3
    HOUSE_CHIP_POS = (575, 43)
    TABLE_GREEN = '#4b1e22'
    PROGRESSIVE_LAMP_WIDTH = 94.0
    FIVE_PLUS_ONE_DIAMETER = 122.0 * 2 / 3
    ZONE_COLORS = {'Player1':'#35634B','Player2':'#204536'}
    SEAT_NAMES = {'Player1': '玩家1', 'Player2': '玩家2', 'Dealer': '庄家手牌'}

    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = username, float(initial_balance)
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game = LunarPokerGame()
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
        self._dealer_side_resolved = set()
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
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=ROOT_BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.control_buttons = {}
        self.selected_cards = {s: set() for s in self.game.SEATS}
        self._faded_photos = {}
        c = self.canvas
        self._text(575, 18, '月亮扑克  LUNAR POKER', 16, GOLD)
        c.create_rectangle(355, 44, 795, 197, fill=self.TABLE_GREEN, outline='')
        self.title_items = {'Dealer': self._text(575, 57, '庄家', 16, PANEL_BG)}
        for seat, x0, x1 in (('Player1',22,566), ('Player2',582,1128)):
            c.create_rectangle(x0,230,x1,617,fill=self.ZONE_COLORS[seat],outline='')
            self.title_items[seat] = self._text((x0+x1)/2,244,self.SEAT_NAMES[seat],16,PANEL_BG)
        self._draw_limit_table()
        self._draw_progressive_panel()
        c.create_rectangle(22,200,1128,226,fill='#173C2E',outline='#65784B',width=1)
        c.create_line(25,201,1125,201,fill='#E0C879',width=2)
        c.create_line(25,225,1125,225,fill='#0C241B',width=2)
        self._text(575,213,'庄家须持 A＋K 或以上牌型才合格',13,GOLD)
        for seat, x0, x1 in (('Player1',22,566), ('Player2',582,1128)):
            for kind, cx, label, fill in (('dealer_change',x0+77,'D','#B8303B'),
                                          ('player_change',x0+269,'P',BET_BLUE)):
                tag = 'spot_'+seat+'_'+kind
                border = c.create_oval(cx-34,393,cx+34,461,fill=fill,outline=GOLD,width=2,tags=tag)
                self._register_spot(seat,kind,cx,427,border,label)
            self._draw_progressive_lamp(seat,x0+173,431)
            self._draw_main_bet_pair(seat,x0+188,505,575)
            self.action_buttons[(seat,'change')] = self.create_control_button(
                x0+392,398,x1-15,447,'换牌/买牌',lambda s=seat:self.change_action(s),
                '#8D6741',font_size=12,draw_shadow=False)
            self.action_buttons[(seat,'play')] = self.create_control_button(
                x0+392,458,x1-15,507,'下注2X',lambda s=seat:self.play_action(s),
                '#397A48',font_size=13,draw_shadow=False)
            self.action_buttons[(seat,'fold')] = self.create_control_button(
                x0+392,518,x1-15,567,'弃牌',lambda s=seat:self.fold_action(s),
                '#9B403A',font_size=13,draw_shadow=False)
        self._draw_bottom_controls()
        for side in ('Dealer',*self.game.SEATS):
            for index in range(5 if side=='Dealer' else 6):
                x,y = self.card_position(side,index)
                c.create_rectangle(x,y,x+self.CARD_WIDTH,y+self.CARD_HEIGHT,
                    outline='#7B9374',dash=(3,3),tags='card_slots')



    def _draw_spot(self, seat, kind, cx, cy, label):
        tag = 'spot_'+seat+'_'+kind
        radius = self.FIVE_PLUS_ONE_DIAMETER / 2
        border = self.canvas.create_oval(cx-radius,cy-radius,cx+radius,cy+radius,
            fill=self.ZONE_COLORS[seat],outline=GOLD,width=2,tags=tag)
        self._register_spot(seat,kind,cx,cy,border,label)


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
        limits = ('$100','$50,000','≤前注') if self.high_bet_mode else ('$10','$10,000','≤前注')
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
            dealer_phase = self.game.stage=='dealer_decision'
            waiting = self.game.dealer_choices[seat]=='pending' if dealer_phase else self.game.decisions[seat]=='pending'
            enabled = self.game.stage in ('decision','dealer_decision') and waiting and not self._decision_busy
            if action=='change': enabled = enabled and not dealer_phase and not self.game.change_used[seat]
            self.set_control_button_state(button,enabled)
            text = ('为庄家换牌' if action=='play' else '直接结算') if dealer_phase and action!='change' else {
                'change':'换牌/买牌','play':'下注2X','fold':'弃牌'}[action]
            c.itemconfigure(self.control_buttons[button]['text'],text=text)



    def add_chip_to_bet(self, seat, kind):
        if self.game.stage!='betting' or self._motion_count or kind in ('play','player_change','dealer_change'): return
        new = {s:dict(b) for s,b in self.bets.items()}
        b = new[seat]
        if kind=='jackpot': b[kind] = 0 if b[kind] else 2.5
        else:
            limit = (50000 if self.high_bet_mode else 10000) if kind=='ante' else b['ante']
            if not limit: return
            b[kind] = min(limit,b[kind]+self.selected_chip)
        self._apply_bet_layout(new)


    def reset_single_bet(self, seat, kind):
        if self.game.stage!='betting' or self._motion_count or kind=='play':return
        new={s:dict(b) for s,b in self.bets.items()}
        if kind=='ante':new[seat]=self.game.empty_bet()
        else:new[seat][kind]=0.0
        self._apply_bet_layout(new)


    def reset_bets(self):
        if self.game.stage=='betting' and not self._motion_count:
            self._apply_bet_layout({s:self.game.empty_bet() for s in self.game.SEATS})


    def apply_last_bet(self):
        if self.game.stage=='betting' and not self._motion_count and self.last_bet:
            new={s:dict(b) for s,b in self.last_bet.items()}
            for b in new.values():
                b['play']=b['player_change']=b['dealer_change']=0.0
            self._apply_bet_layout(new)


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
        if side == 'Dealer':
            return 365+index*85, 74
        return (42 if side == 'Player1' else 604)+index*85, 260



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
        self._dealer_side_resolved=set()
        self._cancel_restart_timer()
        self._sorted_sides=set();self._decision_busy=False;self._showdown_started=False
        self.canvas.delete('cards');self.card_items.clear();self._flip_photos.clear()
        self._load_assets()
        self.selected_cards = {s:set() for s in self.game.SEATS}
        self._faded_photos.clear()
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
            reveal = [('Dealer',0)] + [(s,i) for s in self.game.SEATS
                if self.game.decisions[s]=='pending' for i in range(5)]
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
        card = self.game.dealer_hand[index] if side=='Dealer' else self.game.hands[side][index]
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
        # 此时玩家手牌已翻开及排好；先完成超级红利动画，再开放决定按钮。
        self.game.stage='side_settling';self._refresh()
        seats=[s for s in self.game.SEATS if self.game.decisions[s]=='pending']
        self._settle_side_bets(seats,self._enable_decisions)


    def play_action(self, seat='Player1'):
        if self.game.stage=='dealer_decision': self._choose_dealer_exchange(seat,True)
        else: self._decide(seat,'play')

    def fold_action(self, seat='Player1'):
        if self.game.stage=='dealer_decision': self._choose_dealer_exchange(seat,False)
        else: self._decide(seat,'fold')

    def _decide(self, seat, action):
        if self.game.stage!='decision' or self._decision_busy or self.game.decisions.get(seat)!='pending':return
        try:cost=self.game.decide(seat,action,self.balance)
        except ValueError as exc:
            messagebox.showwarning('无法加注',str(exc),parent=self);return
        self._clear_selection(seat)
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
        self._open_dealer_rest()


    def _settle(self):
        if self._settlement_started: return
        self._settlement_started = True
        jackpot_before = self.game.progressive_amount
        result = self.game.settle()
        self.game.stage = 'settling'
        self.last_win = result['returned']
        try: save_jackpot(self.game.progressive_amount)
        except Exception as exc: messagebox.showerror('奖池保存失败',str(exc),parent=self)
        self._update_hand_title('Dealer')
        self._fade_dealer_notice(not self.game.dealer_qualifies())
        awards,round_id = [],time.time_ns()
        for seat,outcome in result['hands'].items():
            if outcome['details']['bonus']:
                self._set_lamp_mode(seat,'win')
                awards.append((seat,outcome['details']['bonus']))
            info = dict(outcome,seat=seat,round_id=round_id,bets=dict(self.game.bets[seat]),
                        fold=self.game.decisions[seat]=='fold',buy_used=self.game.buy_used[seat],
                        discarded_cards=[str(c) for c in self.game.discarded_cards])
            try:
                dealer = [Card(text[-1],text[:-1]) for text in outcome['dealer_cards']]
                save_lunar_history(self.game.deck,self.game.hands[seat],dealer,info)
            except Exception as exc: messagebox.showerror('历史记录保存失败',str(exc),parent=self)
        self._refresh()
        self._pay_progressive_awards(awards,jackpot_before)

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
        c.create_rectangle(x0,y0,x1,181,fill='#183B30',outline=GOLD,width=1,tags='limits')
        c.create_rectangle(x0,y0,x1,y0+29,fill='#40634B',outline=GOLD,tags='limits')
        self._text((x0+x1)/2,y0+14,'下注上限',13,PANEL_BG,tags='limits')
        titles = ('前注最低','前注最高','超级红利')
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
        panel = tk.Frame(self.canvas,bg='#123C30',highlightbackground=GOLD,highlightthickness=2)
        self.progressive_panel=panel
        self.canvas.create_window(957,128,window=panel,width=322,height=118)
        tk.Label(panel,text='累进大奖',font=('Arial',24,'bold'),
                 bg='#315C40',fg='#F6D675').pack(fill=tk.X)
        self.progressive_amount_var = tk.StringVar(self,f'${self.game.progressive_amount:,.2f}')
        self.progressive_display = ProgressiveSevenSegmentDisplay(panel,self.progressive_amount_var,
            font=('Arial',24,'bold'),bg='#123C30',fg='#FFE29A')
        self.progressive_display.pack(pady=10)

    def _register_spot(self, seat, kind, cx, cy, border, label, angle=0):
        c,tag = self.canvas,'spot_'+seat+'_'+kind
        self._text(cx,cy,label,14,PANEL_BG,angle=angle,tags=tag)
        self.bet_spots[(seat,kind)] = dict(tag=tag,center=(cx,cy),border=border)
        if kind == 'play':
            return  # 加注区只显示决定阶段的筹码，不接受下注阶段的点击。
        c.tag_bind(tag,'<Button-1>',lambda _e,s=seat,k=kind:self.add_chip_to_bet(s,k))
        c.tag_bind(tag,'<Button-3>',lambda _e,s=seat,k=kind:self.reset_single_bet(s,k))
        c.tag_bind(tag,'<Enter>',lambda _e:c.configure(cursor='hand2'))
        c.tag_bind(tag,'<Leave>',lambda _e:c.configure(cursor=''))

    def _draw_main_bet_pair(self, seat, cx, ante_y, play_y):
        """短前注、宽加注长方形；两侧红/蓝超级红利分别连接两个主注。"""
        c = self.canvas
        for kind, cy, label, width, height in (('ante',ante_y,'前注',142,51),
                                              ('play',play_y,'加注',175,68)):
            left,right = cx-width/2,cx+width/2
            tag = 'spot_'+seat+'_'+kind
            border = c.create_rectangle(left,cy-height/2,right,cy+height/2,
                                         fill=BET_BLUE,outline=GOLD,width=2,tags=tag)
            self._register_spot(seat,kind,cx,cy,border,label)
        cy = (ante_y+play_y)/2
        self._draw_super_bonus_spot(seat,'dealer_super_bonus',cx-139,cy,'#B8303B',cx,-1)
        self._draw_super_bonus_spot(seat,'super_bonus',cx+139,cy,BET_BLUE,cx,1)

    def _draw_super_bonus_spot(self, seat, kind, bx, cy, fill, main_cx, side):
        c = self.canvas
        tag = 'spot_'+seat+'_'+kind
        radius = 38
        # 上、下两条线分别连接前注与加注，止于圆形边界。
        for width,dy in ((142,-23),(175,23)):
            start_x = main_cx+side*width/2
            end_x = bx-side*math.sqrt(radius*radius-dy*dy)
            c.create_line(start_x,cy+dy,end_x,cy+dy,fill=GOLD,width=2,
                          tags=(tag,'bonus_connection_'+seat+'_'+kind))
        border = c.create_oval(bx-radius,cy-radius,bx+radius,cy+radius,
                               fill=fill,outline=GOLD,width=2,tags=tag)
        self.bet_spots[(seat,kind)] = dict(tag=tag,center=(bx,cy),border=border)
        c.create_polygon(bx+4,cy-26,bx-11,cy+1,bx,cy+1,bx-5,cy+26,
                         bx+12,cy-5,bx+2,cy-5,fill=PANEL_BG,outline='',tags=tag)
        for text,dx,dy in (('超',-22,-17),('级',22,-17),('红',-22,17),('利',22,17)):
            self._text(bx+dx,cy+dy,text,10,PANEL_BG,tags=tag)
        c.tag_bind(tag,'<Button-1>',lambda _e:self.add_chip_to_bet(seat,kind))
        c.tag_bind(tag,'<Button-3>',lambda _e:self.reset_single_bet(seat,kind))
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
            fg=TITLE_FG,font_size=14,subtext='ENTER',subtext_font_size=10,draw_shadow=False)
        self.restart_button=self.create_control_button(862,638,1138,708,'再来一局(30)',self._return_all_chips,
            HEADER_BG,fg=TITLE_FG,font_size=17,draw_shadow=False)
        c.tag_bind(self.restart_button,'<Button-3>',self._inspect_completed_round)
        c.itemconfigure(self.restart_button,state='hidden')
        # 筹码区下方不放文字，也没有返回按钮。
        self._enter_binding=self.winfo_toplevel().bind('<Return>',lambda _e:
            self._return_all_chips() if self.game.stage in ('await_restart','credit_pending') else self.start_game(),add='+')


    def _sort_revealed_hands(self, sides, complete):
        motions = []
        for side in sides:
            hand = self.game.dealer_hand if side=='Dealer' else self.game.hands[side]
            if not hand or side in self._sorted_sides: continue
            best = best_five_cards(hand)
            ordered = sort_hand_for_display(best,evaluate_five_card_hand(best)) + [c for c in hand if c not in best]
            remapped = {}
            for target_index,card in enumerate(ordered):
                original_index = next(i for i,c in enumerate(hand) if c is card)
                item = self.card_items[(side,original_index)]
                motions.append((item,self.canvas.coords(item),self.card_position(side,target_index)))
                remapped[(side,target_index)] = item
                if target_index>=5: self._fade_card_item(item,self._pil_cards[(card.suit,card.rank)])
                self.canvas.tag_raise(item)
            for key in [k for k in self.card_items if k[0]==side]: self.card_items.pop(key)
            self.card_items.update(remapped)
            if side=='Dealer': self.game.dealer_hand = ordered
            else: self.game.hands[side] = ordered
            self._sorted_sides.add(side)
        def done():
            for side in sides:
                self._update_hand_title(side)
                if side!='Dealer': self._bind_hand_cards(side)
            complete()
        self._move_card_batch(motions,960,done)

    def _after_initial_reveal(self):
        sides=[s for s in self.game.SEATS if self.game.decisions[s]=='pending']
        self._sort_revealed_hands(sides,self._ready_for_decisions)

    def _after_dealer_reveal(self):
        self._sort_revealed_hands(['Dealer'],self._begin_dealer_decisions)


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
        # 保留上下弧形文字，放大圆环并增加字距，文字与外圈灯环分开。
        radius=self.PROGRESSIVE_LAMP_WIDTH/2
        body=c.create_oval(cx-radius,cy-radius,cx+radius,cy+radius,
            fill='#B8303B',outline='#F0C878',width=2,tags=tag)
        center_radius=radius*.43
        center=c.create_oval(cx-center_radius,cy-center_radius,cx+center_radius,cy+center_radius,
            fill='#4A101A',outline='#D56C70',width=1,tags=tag)
        segments=[]
        light_radius=radius-5
        for i in range(16):
            segments.append(c.create_arc(cx-light_radius,cy-light_radius,cx+light_radius,cy+light_radius,
                start=i*22.5,extent=16,style=tk.ARC,width=4,outline='#C85861',tags=tag))
        text_radius=radius-15
        for char,angle in zip('累进大奖',(132,104,76,48)):
            radians=math.radians(angle)
            c.create_text(cx+text_radius*math.cos(radians),cy-text_radius*math.sin(radians),
                text=char,fill='#FFF1D6',angle=angle-90,
                font=(getattr(self,'cn_font','Microsoft YaHei UI'),10,'bold'),tags=tag)
        # 两个中文字之间留较大间距，数字和小数点按各自宽度排列。
        for char,angle in zip('每局$2.50',(207,235,259,280,295,310,331)):
            radians=math.radians(angle)
            c.create_text(cx+text_radius*math.cos(radians),cy-text_radius*math.sin(radians),
                text=char,fill='#FFE3A5',angle=angle-270,
                font=(getattr(self,'cn_font','Microsoft YaHei UI'),9,'bold'),tags=tag)
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
        c.itemconfigure(lamp['center'],fill='#4A101A')
        for i,item in enumerate(lamp['segments']):
            if mode=='spin':
                distance=(i-step)%16
                color={0:'#FFF2D5',1:'#FFC6A3',2:'#FF957A',3:'#EC6264'}.get(distance,'#8C2B37')
            elif mode=='fill':
                color='#FFD6A3' if i in lamp['filled'] else lamp['fill_colors'][i]
            else:color='#FFD6A3' if on else '#C85861'
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
        if abs(value)>=1000:return LunarPokerGUI._compact(value)
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
        best = best_five_cards(hand)
        rank,_ = evaluate_five_card_hand(best)
        if rank==0 and {'A','K'}.issubset({c.rank for c in best}): return '高牌A+K'
        return HAND_RANK_NAMES[rank]

    def _update_hand_title(self, side):
        hand=self.game.dealer_hand if side=='Dealer' else self.game.hands[side]
        name='庄家' if side=='Dealer' else self.SEAT_NAMES[side]
        self.canvas.itemconfigure(self.title_items[side],text=f'{name} - {self.hand_type_text(hand)}')

    def _collect_progressive_and_deal(self):
        for seat in self.game.SEATS:
            chip=self.visual_chips.pop((seat,'jackpot','stake'),None)
            if chip:self._animate_chip(chip['amount'],chip['xy'],self.HOUSE_CHIP_POS,duration=280)
        self.game.stage='dealing';self._refresh()
        # 动画与实际取牌共用同一顺序，未下注的一家没有牌也没有空节拍。
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

    def _settle_side_bets(self, seats, complete):
        transfers = []
        for seat in seats:
            if seat in self._side_resolved: continue
            self._side_resolved.add(seat)
            stake = self.game.bets[seat]['super_bonus']
            returned = self.game.settle_super_bonus(seat)
            transfers.extend(self._outcome_transfers(seat,'super_bonus',stake,returned))
            instant = self.game.check_instant(seat)
            if instant: transfers.extend(self._outcome_transfers(seat,'ante',self.bets[seat]['ante'],instant))
        def done():
            for seat in seats: self._update_hand_title(seat)
            self._refresh()
            complete()
        self._run_chip_batch(transfers,done)

    def _open_dealer_rest(self):
        self.game.stage='showdown';self._refresh()
        self._reveal_next([('Dealer',i) for i in range(1,5)],0,self._after_dealer_reveal)

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
            self._notice_text_item=self._text(575,145,'庄家不及格',16,'#FFF1D1',state='hidden',tags='dealer_notice')
        self._notice_source=layer.resize((width,height),Image.Resampling.LANCZOS)
        self._notice_item=self.canvas.create_image(575,145,state='hidden',tags='dealer_notice')

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

    def _fade_dealer_notice(self, visible, immediate=False):
        target=1.0 if visible else 0.0
        if not immediate and self._notice_target==visible and (self._notice_job is not None or self._notice_level==target):return
        if self._notice_job is not None:
            try:self.after_cancel(self._notice_job)
            except tk.TclError:pass
            self._jobs.discard(self._notice_job);self._notice_job=None
        self._notice_target=visible
        if self._notice_source is None:
            if not visible:return
            self._make_dealer_notice()
        if immediate:
            self._notice_level=target
            self._draw_dealer_notice()
            return
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
        """显示月亮扑克的游戏规则。"""
        import os
        import tkinter as tk
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
        dialog.title('月亮扑克 游戏规则')
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
                '每手玩家牌分别与庄家比牌，两手牌各自决定，共用一副牌和庄家手牌。',
                [
                    (
                        '下注与派牌', '',
                        [
                            (
                                '设置下注',
                                '选择筹码后，点击前注下注。\n'
                                '右侧蓝色闪电为玩家超级红利，左侧红色闪电为庄家超级红利。\n'
                                '中间的累进大奖每手固定下注 $2.50。\n'
                                '加注只可在开牌后的玩家决定阶段选择“下注2X”，金额固定为该手前注的两倍。\n'
                                '未下前注的一家不参加派牌。'
                            ),
                            (
                                '初始派牌',
                                '每家初始获得五张牌，最右侧第六张只保留虚线位置。\n'
                                '庄家先打开一张牌，再打开所有参与的玩家手牌并排序。\n'
                                '每手玩家牌开牌后，分别选择弃牌、下注2X或换牌/买牌。'
                            ),
                            (
                                '玩家决定',
                                '弃牌：失去前注，不再支付加注。\n'
                                '下注2X：支付前注的两倍，继续与庄家比牌。\n'
                                '换牌/买牌：根据选牌数量进行换牌或买牌。\n'
                                '两手玩家牌完成决定后，庄家才打开剩余四张牌。'
                            ),
                        ], []
                    ),
                    (
                        '买牌与换牌', '',
                        [
                            (
                                '选择手牌',
                                '点击一张手牌，该牌会向下移动 10px；再次点击可取消选择。\n'
                                '选择 0–1 张：买入一张牌。\n'
                                '选择 2–5 张：换掉所选手牌。'
                            ),
                            (
                                '买牌',
                                '新牌先放入第六张位置，已选手牌恢复原位。\n'
                                '随后选出最佳五张牌并重新排序，未采用的一张牌变暗。\n'
                                '比牌只使用最佳五张牌。'
                            ),
                            (
                                '换牌',
                                '所选手牌向右移走，保留的手牌向左补齐。\n'
                                '补发等量新牌，接在保留手牌后面打开，再进行排序。'
                            ),
                            (
                                '费用与次数',
                                '每手只可买牌或换牌一次，费用等于该手前注。\n'
                                '费用筹码放在蓝色 P 圈，费用不退回。\n'
                                '买牌或换牌后，只可选择弃牌或下注2X。'
                            ),
                        ], []
                    ),
                    (
                        '庄家换牌', '',
                        [
                            (
                                '分别决定',
                                '庄家不及格时，继续比牌的每家分别选择“为庄家换牌”或“直接结算”。\n'
                                '选择为庄家换牌的一家支付等于自己前注的费用，筹码放在红色 D 圈。\n'
                                '必须等待每家完成决定，才进行庄家换牌。'
                            ),
                            (
                                '结算顺序',
                                '先按庄家换牌前的手牌结算选择直接结算的一家。\n'
                                '之后庄家换掉当前高牌中点数最大的一张牌，再结算选择为庄家换牌的一家。\n'
                                '两家均选择换牌时，各自支付费用，庄家共换一张牌。'
                            ),
                        ], []
                    ),
                ]
            ),
            (
                '下注与结算',
                '先判断庄家是否及格，再比较双方牌型。',
                [
                    (
                        '下注限额', '', [],
                        [
                            (
                                '前注限额', ['模式', '最低', '最高'],
                                [['普通模式', '$10', '$10,000'], ['高额模式', '$100', '$50,000']]
                            ),
                            (
                                '其他下注', ['项目', '金额'],
                                [
                                    ['加注', '前注的两倍'],
                                    ['买牌/换牌费用', '前注的金额'],
                                    ['庄家换牌费用', '前注的金额'],
                                    ['玩家超级红利', '不超过该手前注'],
                                    ['庄家超级红利', '不超过该手前注'],
                                    ['累进大奖', '每手 $2.50'],
                                ]
                            ),
                        ]
                    ),
                    (
                        '主注结算', '',
                        [
                            (
                                '庄家不及格',
                                '庄家须有对子或以上牌型，或同时持有 A、K 才及格。\n'
                                '庄家不及格，包括换牌后仍不及格：前注净赢 1:1，加注退回。\n'
                                '前注净赢 1:1，即连同本金总返还前注的两倍。'
                            ),
                            (
                                '庄家及格',
                                '玩家获胜：前注退回，加注按玩家牌型赔率支付。\n'
                                '双方平局：前注及加注退回。\n'
                                '庄家获胜（包括换牌后获胜）：前注及加注全输。\n'
                                '已买牌的玩家与换牌后的庄家平局时，按玩家获胜处理。'
                            ),
                            (
                                '初始同花顺立即支付',
                                '玩家初始五张牌为皇家同花顺：返还前注金额 × 1000。\n'
                                '玩家初始五张牌为同花顺：返还前注金额 × 200。\n'
                                '该手无需支付加注或继续作出决定。'
                            ),
                        ],
                        [
                            (
                                '加注赔率（净赢）', ['牌型', '赔率'],
                                [
                                    ['皇家同花顺', '100:1'], ['同花顺', '50:1'],
                                    ['四条', '20:1'], ['葫芦', '7:1'], ['同花', '5:1'],
                                    ['顺子', '4:1'], ['三条', '3:1'], ['两对', '2:1'],
                                    ['对子 / 高牌', '1:1'],
                                ]
                            ),
                        ]
                    ),
                ]
            ),
            (
                '超级红利',
                '玩家超级红利与庄家超级红利分别下注，使用相同的获胜条件和赔率。',
                [
                    (
                        '判奖方式', '',
                        [
                            (
                                '玩家超级红利',
                                '右侧蓝色闪电为玩家超级红利。\n'
                                '按玩家初始五张牌判奖，在初始手牌打开后结算。'
                            ),
                            (
                                '庄家超级红利',
                                '左侧红色闪电为庄家超级红利。\n'
                                '按庄家初始五张牌判奖，在初始五张牌打开后结算。'
                            ),
                            (
                                '独立结算',
                                '两种超级红利不受玩家弃牌、买牌或任何换牌决定影响。\n'
                                '中奖返还包含本金；未中奖则失去该项下注。\n'
                                '同时符合多个条件时，按赔付表自上而下的第一个适用条件支付。'
                            ),
                        ],
                        [
                            (
                                '超级红利赔率（净赢）', ['条件', '赔率'],
                                [
                                    ['四条', '250:1'], ['五张脸牌（J/Q/K）', '120:1'],
                                    ['葫芦', '100:1'], ['同花（含同花顺及皇家同花顺）', '60:1'],
                                    ['顺子', '30:1'], ['三条', '8:1'],
                                    ['同时含 A、K、Q', '5:1'], ['五张牌全红或全黑', '2:1'],
                                ]
                            ),
                        ]
                    ),
                ]
            ),
            (
                '累进大奖',
                '每手固定下注 $2.50，按该玩家的初始五张牌判奖。',
                [
                    (
                        '参与与奖金', '',
                        [
                            (
                                '参与方式',
                                '开牌前点击累进大奖灯，可加入或取消该手的累进大奖下注。\n'
                                '买牌、换牌、弃牌及庄家是否及格，均不改变累进大奖的判奖手牌。'
                            ),
                        ],
                        [
                            (
                                '累进大奖奖金', ['牌型', '奖金'],
                                [
                                    ['皇家同花顺', '奖池金额的 100%'],
                                    ['同花顺', '奖池金额的 10%'],
                                    ['四条', '$1,250'], ['葫芦', '$375'], ['同花', '$250'],
                                ]
                            ),
                        ]
                    ),
                ]
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
        tk.Label(header, text='月亮扑克 游戏规则', font=(font_name, 20, 'bold'),
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


    def _fade_card_item(self, item, source):
        faded = source.convert('RGBA').copy()
        faded.putalpha(faded.getchannel('A').point(lambda value:round(value*.45)))
        photo = ImageTk.PhotoImage(faded,master=self)
        self._faded_photos[item] = photo
        self.canvas.itemconfigure(item,image=photo)

    def _move_card_batch(self, motions, duration, complete):
        if not motions:
            complete()
            return
        self._motion_count += 1
        steps = max(1,round(duration/16))
        def frame(index=0):
            p = index/steps
            eased = p*p*(3-2*p)
            for item,(x,y),(tx,ty) in motions:
                self.canvas.coords(item,x+(tx-x)*eased,y+(ty-y)*eased)
            if index<steps:
                self._schedule(round(duration*(index+1)/steps)-round(duration*index/steps),frame,index+1)
            else:
                self._motion_count -= 1
                complete()
        frame()

    def _bind_hand_cards(self, seat):
        for index in range(len(self.game.hands[seat])):
            item = self.card_items[(seat,index)]
            self.canvas.tag_bind(item,'<Button-1>',lambda _e,s=seat,i=index:self.toggle_card_selection(s,i))

    def toggle_card_selection(self, seat, index):
        if self.game.stage!='decision' or self._decision_busy or self.game.decisions[seat]!='pending' or self.game.change_used[seat]: return
        selected = self.selected_cards[seat]
        if index in selected: selected.remove(index)
        else: selected.add(index)
        x,y = self.card_position(seat,index)
        self.canvas.coords(self.card_items[(seat,index)],x,y+(10 if index in selected else 0))
        self._refresh()

    def _clear_selection(self, seat):
        for index in self.selected_cards[seat]:
            self.canvas.coords(self.card_items[(seat,index)],*self.card_position(seat,index))
        self.selected_cards[seat].clear()

    def change_action(self, seat='Player1'):
        if self.game.stage!='decision' or self._decision_busy or self.game.decisions[seat]!='pending' or self.game.change_used[seat]: return
        previous = list(self.game.hands[seat])
        try: change = self.game.buy_or_exchange(seat,self.selected_cards[seat],self.balance)
        except ValueError as exc:
            messagebox.showwarning('无法买牌/换牌',str(exc),parent=self)
            return
        self._decision_busy = True
        self.balance = round(self.balance-change['cost'],2)
        self.bets[seat] = dict(self.game.bets[seat])
        if change['mode']=='buy': self._clear_selection(seat)
        else: self.selected_cards[seat].clear()
        self._persist_balance()
        self._refresh()
        target = self.bet_spots[(seat,'player_change')]['center']
        def paid():
            self._set_visual(seat,'player_change','stake',change['cost'])
            self._animate_player_change(seat,previous,change)
        self._animate_chip(change['cost'],self._rack_position(),target,paid)

    def _animate_player_change(self, seat, previous, change):
        self._sorted_sides.discard(seat)
        if change['mode']=='buy':
            self._deal_change_cards(seat,5,1,self._finish_player_change)
            return
        selected = change['selected']
        removed = [self.card_items[(seat,i)] for i in selected]
        motions = [(item,self.canvas.coords(item),(self.WIDTH+self.CARD_WIDTH,self.canvas.coords(item)[1])) for item in removed]
        def discarded():
            for item in removed: self.canvas.delete(item)
            remapped = {}
            motions = []
            for new_index,card in enumerate(change['kept']):
                old_index = previous.index(card)
                item = self.card_items[(seat,old_index)]
                remapped[(seat,new_index)] = item
                motions.append((item,self.canvas.coords(item),self.card_position(seat,new_index)))
            for key in [k for k in self.card_items if k[0]==seat]: self.card_items.pop(key)
            self.card_items.update(remapped)
            self._move_card_batch(motions,240,lambda:self._deal_change_cards(seat,len(change['kept']),len(change['new']),self._finish_player_change))
        self._move_card_batch(motions,200,discarded)

    def _deal_change_cards(self, side, start_index, count, complete):
        def deal(offset=0):
            if offset==count:
                self._reveal_next([(side,i) for i in range(start_index,start_index+count)],0,lambda:complete(side))
                return
            index = start_index+offset
            item = self.canvas.create_image(575,52,image=self._face_photos['back'],anchor='nw',tags='cards')
            self.card_items[(side,index)] = item
            self._move_card_batch([(item,(575,52),self.card_position(side,index))],220,lambda:deal(offset+1))
        deal()

    def _finish_player_change(self, seat):
        def done():
            self._decision_busy = False
            self._refresh()
        self._sort_revealed_hands([seat],done)

    def _begin_dealer_decisions(self):
        self.game.prepare_dealer_choices()
        self._decision_busy = True
        self._fade_dealer_notice(not self.game.dealer_qualifies())
        self._refresh()
        def done():
            self._decision_busy = False
            self._refresh()
            self._maybe_resolve_dealer_choices()
        self._settle_dealer_side_bets(done)

    def _settle_dealer_side_bets(self, complete):
        transfers = []
        for seat in self.game.SEATS:
            if self.game.decisions[seat]=='inactive' or seat in self._dealer_side_resolved:
                continue
            self._dealer_side_resolved.add(seat)
            stake = self.game.bets[seat]['dealer_super_bonus']
            returned = self.game.settle_dealer_super_bonus(seat)
            transfers.extend(self._outcome_transfers(seat,'dealer_super_bonus',stake,returned))
        self._run_chip_batch(transfers,complete)

    def _choose_dealer_exchange(self, seat, exchange):
        if self._decision_busy or self.game.dealer_choices.get(seat)!='pending': return
        try: cost = self.game.choose_dealer_exchange(seat,exchange,self.balance)
        except ValueError as exc:
            messagebox.showwarning('无法为庄家换牌',str(exc),parent=self)
            return
        self._decision_busy = True
        self.balance = round(self.balance-cost,2)
        self.bets[seat] = dict(self.game.bets[seat])
        self._persist_balance()
        self._refresh()
        def done():
            if cost: self._set_visual(seat,'dealer_change','stake',cost)
            self._decision_busy = False
            self._refresh()
            self._maybe_resolve_dealer_choices()
        self._animate_chip(cost,self._rack_position(),self.bet_spots[(seat,'dealer_change')]['center'],done)

    def _maybe_resolve_dealer_choices(self):
        if self._decision_busy or 'pending' in self.game.dealer_choices.values(): return
        self._decision_busy = True
        self._refresh()
        unchanged = [s for s in self.game.SEATS if self.game.decisions[s]!='inactive' and self.game.dealer_choices[s]!='exchange']
        self._settle_seat_batch(unchanged,False,self._exchange_dealer_for_remaining)

    def _settle_seat_batch(self, seats, after_exchange, complete):
        transfers = []
        for seat in seats:
            outcome = self.game.settle_seat(seat,after_exchange)
            self._update_hand_title(seat)
            for kind in ('ante','play'):
                if kind=='ante' and self.game.decisions[seat]=='instant': continue
                transfers.extend(self._outcome_transfers(seat,kind,self.bets[seat][kind],outcome['details'][kind]))
            for kind in ('player_change','dealer_change'):
                transfers.extend(self._outcome_transfers(seat,kind,self.bets[seat][kind],0))
        self._refresh()
        self._run_chip_batch(transfers,complete)

    def _exchange_dealer_for_remaining(self):
        change = self.game.exchange_dealer_card()
        if change is None:
            self._decision_busy = False
            self._settle()
            return
        self._fade_dealer_notice(False, immediate=True)
        index,_,_ = change
        old_item = self.card_items[('Dealer',index)]
        start = self.canvas.coords(old_item)
        def removed():
            self.canvas.delete(old_item)
            self.card_items.pop(('Dealer',index))
            self._sorted_sides.discard('Dealer')
            self._deal_change_cards('Dealer',index,1,self._finish_dealer_change)
        self._move_card_batch([(old_item,start,(self.WIDTH+self.CARD_WIDTH,start[1]))],200,removed)

    def _finish_dealer_change(self, side):
        def sorted_dealer():
            self._fade_dealer_notice(not self.game.dealer_qualifies())
            seats = [s for s in self.game.SEATS if self.game.dealer_choices[s]=='exchange']
            def done():
                self._decision_busy = False
                self._settle()
            self._settle_seat_batch(seats,True,done)
        self._sort_revealed_hands(['Dealer'],sorted_dealer)


def main(initial_balance=10000, username="Guest", *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """嵌入现有 Tk 根窗口；未传 parent 时仍可独立运行。"""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return LunarPokerGUI(
            parent, actual_balance, actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("月亮扑克")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = LunarPokerGUI(root, actual_balance, actual_user)
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
