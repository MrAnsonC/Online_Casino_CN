"""Ultimate Three Card Poker — shared two-seat Canvas table.

Install in the original game's directory to reuse A_Tools assets, encrypted
account/progressive storage and A_Logs history. Requires Python 3.9+, Pillow
and Tk. Without A_Tools, standalone Guest mode uses local demo data; named
accounts still require the original secure account module.
"""
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_account_storage_ready = False
try:
    from A_Tools.Account import install_secure_json as _install_account_secure_json
except ModuleNotFoundError as exc:
    if exc.name not in ('A_Tools', 'A_Tools.Account'):
        raise
else:
    _install_account_secure_json()
    _account_storage_ready = True

try:
    from A_Tools.Progressive.secure_json import (
        DATA_PATH as _progressive_file,
        install_secure_json as _install_progressive_secure_json,
    )
except ModuleNotFoundError as exc:
    if exc.name not in ('A_Tools', 'A_Tools.Progressive', 'A_Tools.Progressive.secure_json'):
        raise
    _progressive_file = Path(__file__).resolve().parent / '_standalone_data' / 'progressive.json'
else:
    _install_progressive_secure_json()

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
import math
import time
import secrets
import subprocess
from collections import Counter

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

# 扑克牌花色和点数
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

# Pair Plus支付表
PAIR_PLUS_PAYOUT = {
    7: 100,
    6: 40,
    5: 30,
    4: 6,
    3: 3,
    2: 1
}

# 盲注支付表（打败庄家时）
BLIND_PAYOUT = {
    7: 100,
    6: 20,
    5: 10,
    4: 1,
    3: 1,
    2: 0,
    1: 0
}

def load_progressive():
    path = str(_progressive_file)
    default_progressive = 271288.59
    if not os.path.exists(path):
        return True, default_progressive
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item.get('Games') == 'Progressive_2.50':
                    return False, float(item.get('jackpot', default_progressive))
    except Exception:
        return True, default_progressive
    return True, default_progressive

def save_progressive(jackpot):
    path = str(_progressive_file)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
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

def project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def user_data_path() -> str:
    return os.path.join(project_root(), "A_Tools/Account/saving_data.json")

def get_data_file_path():
    return user_data_path()

def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_user_data():
    file_path = get_data_file_path()
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def update_balance_in_json(username, new_balance):
    if not _account_storage_ready:
        raise RuntimeError('命名账户需要原项目的 A_Tools.Account 安全存储模块。')
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:,.2f}"
            break
    save_user_data(users)

def ultimate_three_card_poker_log_path() -> str:
    base = _project_root if _account_storage_ready else Path(__file__).resolve().parent / "_standalone_data"
    log_dir = os.path.join(base, "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Ultimate_Three_Card_Poker.json")

def save_ultimate_history(deck, player_cards, dealer_cards, progressive_cards, result_info=None):
    log_path = ultimate_three_card_poker_log_path()
    
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
        "progressive_cards": [str(c) for c in progressive_cards] if progressive_cards else [],
        "result": result_info if result_info else {}
    }
    if winner is not None:
        record["result"]["winner"] = winner
    elif "winner" not in record["result"]:
        pass
    
    data["history"].append(record)
    
    if len(data["history"]) > 50:
        data["history"] = data["history"][-50:]
    
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

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
            if not os.path.isfile(shuffle_script):
                raise FileNotFoundError(shuffle_script)
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
            self.full_deck = [Card(d["suit"], d["rank"]) for d in shuffle_data["deck"]]
            self.cut_position = shuffle_data["cut_position"]
        except Exception as e:
            if not isinstance(e, FileNotFoundError):
                print(f"Error calling shuffle.py: {e}. Using fallback shuffle.")
            self.full_deck = [Card(s, r) for s in SUITS for r in RANKS]
            self._secure_shuffle()
            self.cut_position = secrets.randbelow(52)
        if len(self.full_deck) != 52 or len({(c.suit, c.rank) for c in self.full_deck}) != 52:
            raise ValueError('洗牌器必须返回 52 张不重复的牌。')
        if isinstance(self.cut_position, bool) or not isinstance(self.cut_position, int) or not 0 <= self.cut_position < 52:
            raise ValueError('切牌位置必须为 0 至 51 的整数。')
        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + i) % 52 for i in range(52)]
        self.pointer = 0
        self.card_sequence = [self.full_deck[i] for i in self.indexes]

    def _secure_shuffle(self):
        for i in range(len(self.full_deck) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            self.full_deck[i], self.full_deck[j] = self.full_deck[j], self.full_deck[i]

    def deal(self, n=1):
        if isinstance(n, bool) or not isinstance(n, int) or n < 0 or self.pointer + n > 52:
            raise ValueError('发牌张数无效或牌堆不足。')
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt

def evaluate_three_card_hand(cards):
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    if len(set(suits)) == 1 and values == [14, 13, 12]:
        return (7, [14])
    if len(set(suits)) == 1:
        if values == [14, 3, 2]:
            return (6, [3])
        if values[0] - values[1] == 1 and values[1] - values[2] == 1:
            return (6, [values[0]])
    if values[0] == values[1] == values[2]:
        return (5, [values[0]])
    if values == [14, 3, 2]:
        return (4, [3])
    if values[0] - values[1] == 1 and values[1] - values[2] == 1:
        return (4, [values[0]])
    if len(set(suits)) == 1:
        return (3, values)
    if values[0] == values[1]:
        return (2, [values[0], values[2]])
    elif values[1] == values[2]:
        return (2, [values[1], values[0]])
    return (1, values)

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

def classify_five_card_hand(cards):
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    is_flush = len(set(suits)) == 1
    is_straight = False
    if len(set(values)) == 5:
        if values[0] - values[4] == 4:
            is_straight = True
        elif values == [14, 5, 4, 3, 2]:
            is_straight = True
    if is_flush and is_straight:
        if values == [14, 13, 12, 11, 10]:
            return 'royal_flush'
        else:
            return 'straight_flush'
    if values[0] == values[3] or values[1] == values[4]:
        return 'four_of_a_kind'
    if (values[0] == values[2] and values[3] == values[4]) or \
       (values[0] == values[1] and values[2] == values[4]):
        return 'full_house'
    if is_flush:
        return 'flush'
    if is_straight:
        return 'straight'
    if values[0] == values[2] or values[1] == values[3] or values[2] == values[4]:
        return 'three_of_a_kind'
    return None

def sort_hand_for_display(hand, hand_eval=None):
    """Only rearrange displayed cards; original deal order remains immutable."""
    rank = (hand_eval or evaluate_three_card_hand(hand))[0]
    if rank in (4, 6, 7):
        low_ace = {c.value for c in hand} == {14, 2, 3}
        return sorted(hand, key=lambda c: 1 if low_ace and c.value == 14 else c.value)
    counts = Counter(c.value for c in hand)
    return sorted(hand, key=lambda c: (counts[c.value], c.value), reverse=True)

class ThreeCardPokerGame:
    """Rules and accounting; no Tk dependencies and no account writes."""

    SEATS = ('Player1', 'Player2')
    MIN_PROGRESSIVE = 271288.59

    def __init__(self):
        self.progressive_amount = load_progressive()[1]
        self.min_progressive = self.MIN_PROGRESSIVE
        self.reset_game()

    @staticmethod
    def empty_bet():
        return dict(ante=0.0, blind=0.0, pair_plus=0.0, jackpot=0.0, play=0.0)

    @staticmethod
    def limits(high_bet_mode=False):
        return (100, 50000, 12500) if high_bet_mode else (10, 10000, 2500)

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

    @staticmethod
    def dealer_qualifies_hand(hand):
        return len(hand) == 3 and (evaluate_three_card_hand(hand)[0] > 1
                                  or max(c.value for c in hand) >= 12)

    def dealer_qualifies(self):
        return self.dealer_qualifies_hand(self.dealer_hand)

    @classmethod
    def deal_sequence(cls, active_seats=None):
        seats = cls.SEATS if active_seats is None else tuple(s for s in cls.SEATS if s in active_seats)
        # Match Three Card Poker: deal one card to each side per pass.
        return [(side, index) for index in range(3)
                for side in (*seats, 'Dealer', 'Progressive')
                if side != 'Progressive' or index < 2]

    def start_round(self, bets, balance, high_bet_mode=False):
        if self.stage != 'betting':
            raise ValueError('本局尚未结束。')
        minimum, maximum, side_max = self.limits(high_bet_mode)
        prepared = {}
        for seat in self.SEATS:
            b = {k: float(bets.get(seat, {}).get(k, 0)) for k in self.empty_bet()}
            if any(not math.isfinite(v) or v < 0 or abs(v * 100 - round(v * 100)) > 1e-6
                   for v in b.values()):
                raise ValueError('下注金额必须是非负数，最多两位小数。')
            if not any(b.values()):
                prepared[seat] = b
                continue
            if not minimum <= b['ante'] <= maximum:
                raise ValueError(f'每手前注须为 ${minimum:,} 至 ${maximum:,}；边注需要前注。')
            if b['blind'] != b['ante']:
                raise ValueError('前注和盲注必须相等。')
            if b['pair_plus'] > side_max or b['jackpot'] not in (0, 2.5):
                raise ValueError(f'对子加注最高 ${side_max:,}，累进大奖每手固定 $2.50。')
            if b['play'] != 0:
                raise ValueError('请在看牌后选择下注 1 倍或 3 倍。')
            prepared[seat] = b
        if not any(b['ante'] for b in prepared.values()):
            raise ValueError('请至少为一手牌下前注。')
        charged = round(sum(sum(b.values()) for b in prepared.values()), 2)
        reserve = sum(b['ante'] for b in prepared.values())
        if not math.isfinite(balance) or charged + reserve > balance:
            raise ValueError('余额不足以支付下注及每手最低一倍加注。')
        deck = Deck()
        hands = {seat: [] for seat in self.SEATS}
        dealer, progressive = [], []
        targets = dict(hands, Dealer=dealer, Progressive=progressive)
        sequence = self.deal_sequence([s for s in self.SEATS if prepared[s]['ante']])
        for side, _ in sequence:
            targets[side].extend(deck.deal(1))
        self.deck, self.hands, self.dealer_hand = deck, hands, dealer
        self.progressive_cards, self.round_deal_sequence = progressive, sequence
        self.bets = prepared
        self.decisions = {s: 'pending' if prepared[s]['ante'] else 'inactive' for s in self.SEATS}
        self.stage = 'dealing'
        return charged

    def can_raise(self, seat, multiplier, balance):
        if multiplier not in (1, 3) or self.decisions.get(seat) != 'pending':
            return False
        if multiplier == 3 and evaluate_three_card_hand(self.hands[seat])[0] < 2:
            return False
        reserve = sum(self.bets[s]['ante'] for s in self.SEATS
                      if s != seat and self.decisions[s] == 'pending')
        return self.bets[seat]['ante'] * multiplier + reserve <= balance

    def decide(self, seat, action, balance, multiplier=1):
        if self.stage != 'decision' or self.decisions.get(seat) != 'pending':
            raise ValueError('当前手牌不在决策阶段。')
        if action not in ('play', 'fold'):
            raise ValueError('无效的决定。')
        if action == 'play':
            if multiplier not in (1, 3):
                raise ValueError('加注只可选择 1 倍或 3 倍。')
            if multiplier == 3 and evaluate_three_card_hand(self.hands[seat])[0] < 2:
                raise ValueError('只有对子或以上牌型才可以下注 3 倍。')
            if not self.can_raise(seat, multiplier, balance):
                raise ValueError('余额不足；须为其他未决定的手牌保留一倍加注。')
        cost = round(self.bets[seat]['ante'] * multiplier, 2) if action == 'play' else 0.0
        self.bets[seat]['play'] = cost
        self.decisions[seat] = action
        return cost

    @staticmethod
    def pair_plus_return(hand, stake):
        payout = PAIR_PLUS_PAYOUT.get(evaluate_three_card_hand(hand)[0])
        return round(stake * (payout + 1), 2) if payout is not None else 0.0

    def settle_side_bet(self, seat, kind):
        if kind != 'pair_plus':
            raise ValueError('未知边注。')
        key = (seat, kind)
        if key not in self.side_returns:
            self.side_returns[key] = self.pair_plus_return(self.hands[seat], self.bets[seat][kind])
        return self.side_returns[key]

    def settle(self):
        if self.settlement is not None:
            return self.settlement
        if self.stage != 'showdown' or 'pending' in self.decisions.values():
            raise ValueError('所有手牌完成决定并开牌后才能结算。')
        outcomes, total_bonus = {}, 0.0
        jackpot_snapshot = self.progressive_amount
        for seat in self.SEATS:
            if self.decisions[seat] == 'inactive':
                continue
            b, hand = self.bets[seat], self.hands[seat]
            rank = evaluate_three_card_hand(hand)[0]
            d = dict(ante=0.0, blind=0.0, play=0.0, pair_plus=0.0, bonus=0.0)
            if self.decisions[seat] == 'fold':
                winner, message = 'fold', '已弃牌；边注独立结算'
            else:
                comparison = compare_hands(hand, self.dealer_hand)
                winner = 'player' if comparison > 0 else 'dealer' if comparison < 0 else 'push'
                message = {'player': '玩家获胜', 'dealer': '庄家获胜', 'push': '平局：主注退回'}[winner]
                if not self.dealer_qualifies():
                    d['ante'] = b['ante']
                    message += '；庄家不及格，前注退回'
                else:
                    d['ante'] = b['ante'] * (2 if comparison > 0 else 1 if comparison == 0 else 0)
                d['play'] = b['play'] * (2 if comparison > 0 else 1 if comparison == 0 else 0)
                d['blind'] = (b['blind'] * (BLIND_PAYOUT[rank] + 1) if comparison > 0
                              else b['blind'] if comparison == 0 else 0.0)
            d['pair_plus'] = self.settle_side_bet(seat, 'pair_plus')
            if b['jackpot']:
                progressive_rank = classify_five_card_hand(hand + self.progressive_cards)
                d['bonus'] = round({'royal_flush': jackpot_snapshot,
                                    'straight_flush': jackpot_snapshot * .1,
                                    'four_of_a_kind': 1250.0, 'full_house': 375.0,
                                    'flush': 250.0}.get(progressive_rank, 0.0), 2)
            total_bonus += d['bonus']
            returned = round(sum(d.values()), 2)
            stake = round(sum(b.values()), 2)
            outcomes[seat] = dict(winner=winner, message=message, details=d,
                                  returned=returned, stake=stake, net=round(returned - stake, 2))
        contribution = sum(sum(b.values()) * .001 + b['jackpot'] * .95 for b in self.bets.values())
        # Each seat uses the same opening pool; replenish once after all awards.
        self.progressive_amount = round(max(self.MIN_PROGRESSIVE, jackpot_snapshot - total_bonus)
                                        + contribution, 2)
        self.stage = 'settled'
        self.settlement = dict(hands=outcomes, returned=round(sum(o['returned'] for o in outcomes.values()), 2))
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
    PLAYER_ZONES = {'Player1': (22, 566), 'Player2': (582, 1128)}
    CARD_GAP = 5
    ZONE_COLORS = {'Player1':'#35634B','Player2':'#204536'}
    SEAT_NAMES = {'Player1': '玩家1', 'Player2': '玩家2', 'Dealer': '庄家手牌', 'Progressive': '累进大奖牌'}

    # Lifecycle and integration

    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = username, float(initial_balance)
        self.on_back, self.on_balance_change = on_back, on_balance_change
        if username and username != 'Guest' and not _account_storage_ready:
            raise RuntimeError('命名账户需要原项目的 A_Tools.Account 安全存储模块。')
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

    def on_close(self):
        if self._closing or self._crediting:return
        settled=self.game.stage in ('settling','await_restart','returning','credit_pending','sweeping')
        if self.game_in_progress and not settled:
            messagebox.showinfo('牌局进行中','请先完成所有已下注手牌的决定和结算。',parent=self)
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

    # Table, assets and controls

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

    def _center_table(self, event=None):
        self.canvas.place(x=max(0, (self.winfo_width() - self.WIDTH) // 2),
                          y=max(0, (self.winfo_height() - self.HEIGHT) // 2),
                          width=self.WIDTH, height=self.HEIGHT)

    def _create_widgets(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=ROOT_BG, highlightthickness=0)
        self.canvas.place(x=0, y=0, width=self.WIDTH, height=self.HEIGHT)
        self.bind('<Configure>', self._center_table, add='+')
        self.control_buttons = {}
        c = self.canvas
        self._text(575, 18, '终极三张牌扑克  ULTIMATE THREE CARD POKER', 16, GOLD)
        c.create_rectangle(355, 44, 630, 197, fill=self.TABLE_GREEN, outline='')
        self.title_items = {'Dealer': self._text(493, 57, '庄家', 16, PANEL_BG)}
        c.create_rectangle(637, 44, 825, 197, fill='#6B5220', outline='')
        self._text(731, 57, '累进', 16, GOLD)
        self._draw_limit_table()
        self._draw_progressive_panel()
        c.create_rectangle(22, 200, 1128, 226, fill='#173C2E', outline='#65784B')
        c.create_line(25, 201, 1125, 201, fill='#E0C879', width=2)
        c.create_line(25, 225, 1125, 225, fill='#0C241B', width=2)
        self._text(575, 213, '庄家 Q 高牌及格 · 不及格退前注 · 对子或以上可下注 3 倍', 13, GOLD)
        for seat, (x0, x1) in self.PLAYER_ZONES.items():
            c.create_rectangle(x0, 230, x1, 617, fill=self.ZONE_COLORS[seat], outline='')
            self.title_items[seat] = self._text((x0 + x1) / 2, 245, self.SEAT_NAMES[seat], 16, PANEL_BG)
            left_x, right_x = x0 + 180, x0 + 310
            upper_y, lower_y = 442, 548
            side_bet_gap = lower_y - upper_y
            lamp_y = (upper_y + lower_y) / 2
            self._draw_progressive_lamp(seat, x0 + 75, lamp_y)
            self._draw_spot(seat, 'ante', left_x, upper_y, '前注')
            self._draw_spot(seat, 'blind', right_x, upper_y, '盲注')
            self._draw_spot(seat, 'play', left_x, lower_y, '加注')
            self._draw_spot(seat, 'pair_plus', x0 + 75, lamp_y - side_bet_gap, '对子\n加注')
            self._text((left_x + right_x) / 2, upper_y, '＝', 22, PANEL_BG)
            for action, top, caption, color in (
                    ('play3', 411, '下注3倍', '#2B6639'),
                    ('play1', 480, '下注1倍', '#397A48'),
                    ('fold', 549, '弃牌', '#9B403A')):
                self.action_buttons[(seat, action)] = self.create_control_button(
                    x0 + 410, top, x1 - 15, top + 58, caption,
                    lambda s=seat, a=action: self.fold_action(s) if a == 'fold'
                    else self.play_action(3 if a == 'play3' else 1, s),
                    color, font_size=14, draw_shadow=False)
        self._draw_bottom_controls()
        for side in ('Dealer', 'Progressive', *self.game.SEATS):
            for index in range(2 if side == 'Progressive' else 3):
                x, y = self.card_position(side, index)
                c.create_rectangle(x, y, x + self.CARD_WIDTH, y + self.CARD_HEIGHT,
                                   outline=GOLD if side == 'Progressive' else '#7B9374',
                                   dash=(3, 3), tags='card_slots')

    def card_position(self, side, index):
        if side == 'Progressive':
            return 648 + index * 85, 74
        if side == 'Dealer':
            return 368 + index * 85, 74
        x0, x1 = self.PLAYER_ZONES[side]
        hand_width = 3 * self.CARD_WIDTH + 2 * self.CARD_GAP
        left = (x0 + x1 - hand_width) / 2
        return left + index * (self.CARD_WIDTH + self.CARD_GAP), 266

    def _draw_spot(self, seat, kind, cx, cy, label):
        tag = 'spot_'+seat+'_'+kind
        radius = self.SIDE_BET_DIAMETER / 2
        border = self.canvas.create_oval(cx-radius,cy-radius,cx+radius,cy+radius,
            fill=self.ZONE_COLORS[seat],outline=GOLD,width=2,tags=tag)
        self._register_spot(seat,kind,cx,cy,border,label)

    def _register_spot(self, seat, kind, cx, cy, border, label, angle=0):
        c,tag = self.canvas,'spot_'+seat+'_'+kind
        self._text(cx,cy,label,12 if kind == 'pair_plus' else 14,PANEL_BG,
                   angle=angle,justify='center',tags=tag)
        self.bet_spots[(seat,kind)] = dict(tag=tag,center=(cx,cy),border=border)
        c.tag_bind(tag,'<Button-1>',lambda _e,s=seat,k=kind:self.add_chip_to_bet(s,k))
        c.tag_bind(tag,'<Button-3>',lambda _e,s=seat,k=kind:self.reset_single_bet(s,k))
        c.tag_bind(tag,'<Enter>',lambda _e:c.configure(cursor='hand2'))
        c.tag_bind(tag,'<Leave>',lambda _e:c.configure(cursor=''))

    def _draw_limit_table(self):
        c = self.canvas
        x0, x1, y0 = 30, 349, 75
        c.create_rectangle(x0, y0, x1, 181, fill='#183B30', outline=GOLD, tags='limits')
        c.create_rectangle(x0, y0, x1, y0 + 29, fill='#40634B', outline=GOLD, tags='limits')
        self._text((x0 + x1) / 2, y0 + 14, '下注上限', 13, PANEL_BG, tags='limits')
        self.limit_value_items = []
        left = x0
        for title, width in (('前注最低', 96), ('前注最高', 106), ('对子加注最高', 117)):
            right = left + width
            c.create_rectangle(left, y0 + 29, right, y0 + 66, outline='#77906B', tags='limits')
            c.create_rectangle(left, y0 + 66, right, 181, outline='#77906B', tags='limits')
            self._text((left + right) / 2, y0 + 47, title, 10, PANEL_BG, tags='limits')
            self.limit_value_items.append(self._text((left + right) / 2, y0 + 86, '', 11, GOLD, tags='limits'))
            left = right
        c.tag_bind('limits', '<Button-1>', self.toggle_high_bet_limits)
        c.tag_bind('limits', '<Enter>', lambda _e: c.configure(cursor='hand2'))
        c.tag_bind('limits', '<Leave>', lambda _e: c.configure(cursor=''))

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

    def _status(self, message):
        # 记录阶段供调试，不在筹码下方绘制说明文字。
        self.current_status=message

    def _refresh(self):
        c = self.canvas
        c.itemconfigure(self.balance_item, text=f'余额: ${self.balance:,.2f}')
        total = sum(sum(b.values()) for b in self.bets.values())
        c.itemconfigure(self.total_item, text=f'本局下注: ${total:,.2f}' if total else f'上局返还: ${self.last_win:,.2f}')
        for item, value in zip(self.limit_value_items, self.game.limits(self.high_bet_mode)):
            c.itemconfigure(item, text=f'${value:,}')
        self._render_chips()
        betting = self.game.stage == 'betting' and self._motion_count == 0
        self.set_control_button_state(self.clear_button, betting)
        self.set_control_button_state(self.repeat_button, betting and bool(self.last_bet))
        self.set_control_button_state(self.start_button, betting)
        restarting = self.game.stage in ('await_restart', 'returning', 'credit_pending', 'sweeping')
        c.itemconfigure(self.repeat_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button, state='normal' if restarting else 'hidden')
        self.set_control_button_state(self.restart_button, self.game.stage in ('await_restart', 'credit_pending'))
        for (seat, action), button in self.action_buttons.items():
            ready = self.game.stage == 'decision' and not self._decision_busy and self.game.decisions[seat] == 'pending'
            affordable = action == 'fold' or ready and self.game.can_raise(seat, 3 if action == 'play3' else 1, self.balance)
            self.set_control_button_state(button, ready and affordable)

    # Betting and decisions

    def select_chip(self, amount):
        if self.game.stage == 'betting':
            self.selected_chip = amount
            self._draw_chips()

    def add_chip_to_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count:
            return
        new = {s: dict(b) for s, b in self.bets.items()}
        b = new[seat]
        if kind == 'jackpot':
            b[kind] = 0 if b[kind] else 2.5
        elif kind == 'play':
            return
        else:
            main = kind in ('ante', 'blind')
            _, maximum, side_max = self.game.limits(self.high_bet_mode)
            b[kind] = min(maximum if main else side_max, b[kind] + self.selected_chip)
            if main:
                b['ante'] = b['blind'] = b[kind]
        self._apply_bet_layout(new)

    def reset_single_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count:
            return
        new = {s: dict(b) for s, b in self.bets.items()}
        if kind in ('ante', 'blind'):
            new[seat]['ante'] = new[seat]['blind'] = new[seat]['play'] = 0.0
        else:
            new[seat][kind] = 0.0
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

    def start_game(self):
        if self.game.stage != 'betting' or self._motion_count:
            return
        try:
            charged = self.game.start_round(self.bets, self.balance, self.high_bet_mode)
        except ValueError as exc:
            messagebox.showwarning('无法开始', str(exc), parent=self)
            return
        self.game.stage = 'progressive'
        self._history_available = False
        self._close_card_sequence()
        self._fade_dealer_notice(False)
        self.balance = round(self.balance - charged, 2)
        self.bets = {s: dict(b) for s, b in self.game.bets.items()}
        self.last_bet = {s: dict(b) for s, b in self.bets.items()}
        self._credited = self._return_persisted = self._settlement_started = False
        self._side_resolved, self._sorted_sides = set(), set()
        self._decision_busy = self._showdown_started = False
        self._cancel_restart_timer()
        self.canvas.delete('cards')
        self.card_items.clear()
        self._flip_photos.clear()
        self._load_assets()
        for side, item in self.title_items.items():
            self.canvas.itemconfigure(item, text='庄家' if side == 'Dealer' else self.SEAT_NAMES[side])
        self._persist_balance()
        self._refresh()
        self._start_progressive_lamps()

    def play_action(self, multiplier=1, seat='Player1'):
        self._decide(seat, 'play', multiplier)

    def fold_action(self, seat='Player1'):
        self._decide(seat, 'fold')

    def _decide(self, seat, action, multiplier=1):
        if self.game.stage != 'decision' or self._decision_busy or self.game.decisions.get(seat) != 'pending':
            return
        try:
            cost = self.game.decide(seat, action, self.balance, multiplier)
        except ValueError as exc:
            messagebox.showwarning('无法操作', str(exc), parent=self)
            return
        self._decision_busy = True
        self.balance = round(self.balance - cost, 2)
        self.bets[seat]['play'] = self.game.bets[seat]['play']
        self._persist_balance()
        self._refresh()
        def done():
            self._decision_busy = False
            self._refresh()
            self._maybe_showdown()
        if action == 'fold':
            transfers = []
            for kind in ('ante', 'blind', 'play'):
                chip = self.visual_chips.pop((seat, kind, 'stake'), None)
                if chip:
                    transfers.append(dict(amount=chip['amount'], start=chip['xy'], target=self.HOUSE_CHIP_POS, duration=280))
            self._run_chip_batch(transfers, done)
        else:
            def arrived():
                self._set_visual(seat, 'play', 'stake', cost)
                done()
            self._animate_chip(cost, self._rack_position(), self.bet_spots[(seat, 'play')]['center'], arrived)

    # Dealing, reveals and settlement

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

    def _collect_progressive_and_deal(self):
        for seat in self.game.SEATS:
            chip=self.visual_chips.pop((seat,'jackpot','stake'),None)
            if chip:self._animate_chip(chip['amount'],chip['xy'],self.HOUSE_CHIP_POS,duration=280)
        self.game.stage='dealing';self._refresh()
        sequence=self.game.round_deal_sequence
        self._deal_next(sequence,0)

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

    def _ready_for_decisions(self):
        # 非盲注手牌翻开并排序后，先完成对子加注动画，再开放决定按钮。
        self.game.stage='side_settling';self._refresh()
        seats=[s for s in self.game.SEATS if self.game.decisions[s]=='pending']
        self._settle_side_bets(seats,self._enable_decisions)

    def _enable_decisions(self):
        self.game.stage='decision';self._refresh();self._maybe_showdown()

    def _maybe_showdown(self):
        if self._showdown_started or self._decision_busy or 'pending' in self.game.decisions.values():
            return
        self._showdown_started = True
        self._open_dealer_rest()

    def _open_dealer_rest(self):
        self.game.stage='showdown';self._refresh()
        sequence=[('Dealer',i) for i in range(3)]
        if any(b['jackpot'] for b in self.game.bets.values()):
            sequence += [('Progressive',i) for i in range(2)]
        self._reveal_next(sequence,0,self._after_dealer_reveal)

    def _after_dealer_reveal(self):
        self._sort_revealed_hands(['Dealer'], self._settle)

    def _settle_side_bets(self, seats, complete, kinds=('pair_plus',)):
        transfers=[]
        for seat in seats:
            for kind in kinds:
                key=(seat,kind)
                if key in self._side_resolved:continue
                self._side_resolved.add(key)
                stake=self.game.bets[seat][kind]
                returned=self.game.settle_side_bet(seat,kind)
                transfers.extend(self._outcome_transfers(seat,kind,stake,returned))
        def done():
            for seat in seats:self._update_hand_title(seat)
            self._refresh();complete()
        self._run_chip_batch(transfers,done)

    def _settle(self):
        if self._settlement_started:
            return
        self._settlement_started = True
        jackpot_before = self.game.progressive_amount
        result = self.game.settle()
        self.game.stage, self.last_win = 'settling', result['returned']
        try:
            save_progressive(self.game.progressive_amount)
        except Exception as exc:
            messagebox.showerror('奖池保存失败', str(exc), parent=self)
        self._update_hand_title('Dealer')
        self._fade_dealer_notice(not self.game.dealer_qualifies())
        transfers, awards, round_id = [], [], time.time_ns()
        for seat, outcome in result['hands'].items():
            self._update_hand_title(seat)
            for kind in ('ante', 'blind', 'play'):
                transfers.extend(self._outcome_transfers(seat, kind, self.game.bets[seat][kind], outcome['details'][kind]))
            bonus = outcome['details']['bonus']
            if bonus:
                self._set_lamp_mode(seat, 'win')
                awards.append((seat, bonus))
            info = dict(outcome, seat=seat, round_id=round_id, bets=dict(self.game.bets[seat]),
                        fold=self.game.decisions[seat] == 'fold', total_winnings=outcome['returned'])
            try:
                save_ultimate_history(self.game.deck, self.game.hands[seat], self.game.dealer_hand,
                                      self.game.progressive_cards, info)
            except Exception as exc:
                messagebox.showerror('历史记录保存失败', str(exc), parent=self)
        self._refresh()
        self._run_chip_batch(transfers, lambda: self._pay_progressive_awards(awards, jackpot_before))

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

    @staticmethod
    def hand_type_text(hand):
        return HAND_RANK_NAMES[evaluate_three_card_hand(hand)[0]]

    def _update_hand_title(self, side):
        hand = self.game.dealer_hand if side == 'Dealer' else self.game.hands[side]
        if not hand:
            return
        name = '庄家' if side == 'Dealer' else self.SEAT_NAMES[side]
        caption = f'{name} - {self.hand_type_text(hand)}'
        if side != 'Dealer' and self.game.decisions[side] == 'fold':
            caption += '（弃牌）'
        self.canvas.itemconfigure(self.title_items[side], text=caption)

    # Chips and Progressive lamps

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

    # Return, account credit and next round

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

    def reset_game(self, auto_reset=False):
        # 兼容原入口；通常由全部筹码回到筹码区自动开放下一局。
        if self.game.stage=='betting':
            self._fade_dealer_notice(False)
            self.reset_bets()

    # Dealer notices, history and manual

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

    def _close_card_sequence(self):
        current=getattr(self,'_sequence_window',None)
        if current is not None:
            try:
                if current.winfo_exists():current.destroy()
            except tk.TclError:pass
        self._sequence_window=None

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
        dialog.title('终极三张牌扑克 · 完整图解玩法')
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
                            ('本局目标', '以三张牌争取胜过庄家，并按庄家资格和下注类型结算。'),
                        ],
                        [],
                    ],
                    [
                        '一局如何进行',
                        '',
                        [
                            ('玩家下注', '设置前注与可选边注，开始一局。'),
                            ('玩家决策', '查看已发的手牌，依牌桌提示选择继续、加注或弃牌。'),
                            ('庄家开牌', '庄家亮牌，同时翻开累进大奖牌。'),
                            ('结算', '按比牌结果与各下注项目的条件分别结算。'),
                        ],
                        [],
                    ],
                    [
                        '一局完整流程',
                        '',
                        [
                            ('下注阶段', '前注（Ante）：每手参与的牌必须下注；可只玩一手。\n盲注（Blind）：自动等于前注金额，无需单独下注。\n对子加注（Pair Plus）：可选边注，与庄家无关，按玩家牌型派彩。\n累进大奖（Progressive）：可选 $2.50 下注。'),
                            ('发牌', '按轮次依序向已下注的玩家1、玩家2、庄家、累进牌区各发 1 张。\n前两轮包含累进牌，第三轮只发玩家及庄家；未下注玩家跳过。\n玩家看牌后决定；庄家与累进牌在摊牌时翻开。'),
                            ('玩家决策', '查看自己 3 张牌后，选择：\n• 弃牌：输掉前注 / 盲注，保留对子加注与累进大奖的结算。\n• 下注 1 倍：加注金额 = 前注 × 1。\n• 下注 3 倍：仅当手牌为「一对」或更好时可用。'),
                            ('摊牌与比牌', '双方比较各自 3 张手牌：先比牌型，再比点数；\n完全相同为平局。\n庄家最高牌 Q 或以上及格，低于 Q 不及格。'),
                            ('结算', '按「庄家是否及格」与「比牌结果」结算前注 / 盲注 / 加注；\n对子加注、累进大奖独立结算（不受庄家影响）。'),
                            ('再来一局', '点击「再来一局」或 30 秒无操作，筹码回收并入账后进入下一局。\n累进大奖中奖时等待手动继续；右键「再来一局」查看上局牌序。'),
                        ],
                        [],
                    ],
                    [
                        '发牌顺序',
                        '',
                        [
                            ('累进大奖扑克', '2 张共用累进牌，前两轮各发 1 张，背面朝下，摆放在庄家右侧。\n摊牌时与庄家手牌一起翻开。'),
                            ('玩家手牌', '3 张，正面朝上发出，发完自动翻牌。\n发牌同时显示玩家牌型名称。'),
                            ('庄家手牌', '3 张，全程背面朝下，直到摊牌时才翻开。'),
                        ],
                        [],
                    ],
                    [
                        '玩家决策按钮',
                        '',
                        [
                            ('弃牌', '放弃本局比牌。\n前注、盲注输掉；\n对子加注、累进大奖照常结算。'),
                            ('下注 1 倍', '加注金额 = 前注 × 1。\n庄家不及格时，加注按牌型比较正常结算。'),
                            ('下注 3 倍', '加注金额 = 前注 × 3。\n仅当手牌为「对子」或更高牌型时按钮可用。'),
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
                                    ['前注（Ante）', '普通：$10–$10,000\n高额：$100–$50,000', '每手参与的牌必须下注；可只玩一手。'],
                                    ['盲注（Blind）', '普通：$10–$10,000\n高额：$100–$50,000', '盲注自动等于前注金额（`盲注 = 前注`）。\n仅当玩家赢庄家时，按玩家最终牌型支付。'],
                                    ['对子加注（Pair Plus）', '普通：每项最高$2,500\n高额：每项最高$12,500', '基于玩家 3 张手牌的牌型派彩，与庄家无关。'],
                                    ['累进大奖（Progressive）', '每局$2.50', '固定 $2.50 下注。\n以「玩家 3 张 + 累进牌 2 张」组成的 5 张牌型派彩。'],
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
                                    ['庄家及格线', '庄家 Q 高牌或以上及格；\n低于 Q 不及格。'],
                                    ['比大小', '双方各选最佳三张牌，先比牌型，再依次比牌点。'],
                                    ['完全相同', '双方平局。'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '对子加注（Pair Plus）支付表',
                        '',
                        [],
                        [
                            (
                                '',
                                ['玩家最终牌型', '赔率', '返还公式'],
                                [
                                    ['迷你皇家同花顺', '100 : 1', '下注 × 101'],
                                    ['同花顺', '40 : 1', '下注 × 41'],
                                    ['三条', '30 : 1', '下注 × 31'],
                                    ['顺子', '6 : 1', '下注 × 7'],
                                    ['同花', '3 : 1', '下注 × 4'],
                                    ['对子', '1 : 1', '下注 × 2'],
                                    ['高牌', '未中奖', '本金归庄'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '盲注（Blind）支付表（需打败庄家）',
                        '',
                        [],
                        [
                            (
                                '',
                                ['玩家最终牌型', '赔率', '返还公式'],
                                [
                                    ['迷你皇家同花顺', '100 : 1', '盲注 × 101'],
                                    ['同花顺', '20 : 1', '盲注 × 21'],
                                    ['三条', '10 : 1', '盲注 × 11'],
                                    ['顺子', '1 : 1', '盲注 × 2'],
                                    ['同花', '1 : 1', '盲注 × 2'],
                                    ['对子', '平局', '盲注 × 1'],
                                    ['高牌', '平局', '盲注 × 1'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '累进大奖（Progressive）支付表',
                        '',
                        [],
                        [
                            (
                                '',
                                ['情形／项目', '赔率／结算规则'],
                                [
                                    ['参与条件', '固定 $2.50 下注。'],
                                    ['', '以「玩家 3 张 + 累进牌 2 张」组成的 5 张牌型派彩。'],
                                ],
                            ),
                            (
                                '',
                                ['5 张组合牌型', '奖励'],
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
                        '额外说明',
                        '',
                        [],
                        [
                            (
                                '',
                                ['情形／项目', '赔率／结算规则'],
                                [
                                    ['平局（Push）', '前注 / 盲注 / 加注全额返还，不输不赢。'],
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
                                ['获胜条件', '前注 / Ante', '相关下注'],
                                [
                                    ['庄家不及格', '前注退还', '加注仍按比牌结果；\n盲注胜出时按牌型表'],
                                    ['庄家及格、玩家胜', '前注赢 1:1', '加注赢 1:1；\n盲注按牌型表'],
                                    ['双方平局', '前注退还', '盲注与加注退还'],
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
                        '7 种牌型',
                        '下方图片展示牌型示例；\n同一牌型也可能由其他牌面组成。',
                        [],
                        [
                            (
                                '牌型与示例',
                                ['等级', '牌型', '说明', '牌例'],
                                [
                                    [
                                        '1',
                                        '迷你皇家同花顺',
                                        '同花色的 A-K-Q',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', 'Q'),
                                                ('♥', 'K'),
                                                ('♥', 'A'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '2',
                                        '同花顺',
                                        '同花色三张连续',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', '6'),
                                                ('♥', '7'),
                                                ('♥', '8'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '3',
                                        '三条',
                                        '三张同点数',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', 'A'),
                                                ('♣', 'A'),
                                                ('♠', 'A'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '4',
                                        '顺子',
                                        '三张连续（花色不同）',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', '6'),
                                                ('♠', '7'),
                                                ('♦', '8'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '5',
                                        '同花',
                                        '三张同花色（不连续）',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♣', 'K'),
                                                ('♣', '8'),
                                                ('♣', '5'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '6',
                                        '对子',
                                        '两张同点数',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', 'A'),
                                                ('♣', 'A'),
                                                ('♠', 'K'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '7',
                                        '高牌',
                                        '无任何组合',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', 'A'),
                                                ('♠', 'K'),
                                                ('♦', 'J'),
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
                            ('比较方法', '牌型顺序：迷你皇家同花顺 ＞ 同花顺 ＞ 三条 ＞ 顺子 ＞ 同花 ＞ 对子 ＞ 高牌。\n同牌型按关键点数比较；\nA-2-3 按 3 高，Q-K-A 同花为最高牌型。\n花色不分大小。'),
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
                        '额外说明',
                        '',
                        [
                            ('A 的用法', 'A 可作为最大点（A-K-Q）也可作为 1 用（A-2-3），形成顺子 / 同花顺。\n迷你皇家同花顺专指「同花色的 A-K-Q」，比同花顺更大。'),
                        ],
                        [],
                    ],
                    [
                        '特别规则补充',
                        '',
                        [
                            ('需留意的规则', '迷你皇家同花顺专指同花色 Q-K-A；\n加注按钮可能受玩家牌型限制。'),
                        ],
                        [],
                    ],
                    [
                        '特殊下注规则',
                        '',
                        [
                            ('盲注（Blind）', '自动'),
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
        tk.Label(header, text='终极三张牌扑克 · 完整图解玩法', font=(font_name, 20, 'bold'),
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
                        for suit, rank in value[1]:
                            try:
                                source_image = self.original_images[(suit, rank)]
                                card_width = 70
                                card_height = max(1, round(source_image.height * card_width / source_image.width))
                                small_image = source_image.resize((card_width, card_height), Image.Resampling.LANCZOS)
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

UltimateThreeCardPokerGame = ThreeCardPokerGame
UltimateThreeCardPokerGUI = ThreeCardPokerGUI

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
    root.title("终极三张牌扑克")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = ThreeCardPokerGUI(root, actual_balance, actual_user)
    page.pack(fill="both", expand=True)

    def close_standalone():
        root.destroy()

    page.on_back = lambda final_balance: close_standalone()
    root.protocol("WM_DELETE_WINDOW", page.on_close)
    root.mainloop()
    return page.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")
