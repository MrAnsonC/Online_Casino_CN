import sys as _account_sys
from pathlib import Path as _AccountPath
_account_root = next((p for p in (_AccountPath(__file__).resolve().parent, *_AccountPath(__file__).resolve().parents) if (p / "A_Tools" / "Account" / "secure_json.py").is_file()), None)
if _account_root is None:
    raise RuntimeError("Cannot locate encrypted account storage")
if str(_account_root) not in _account_sys.path:
    _account_sys.path.insert(0, str(_account_root))
from A_Tools.Account import install_secure_json as _install_secure_json
_install_secure_json()
_PROJECT_ROOT = str(_account_root)
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
# UTH 牌桌 UI 颜色
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

# 标准派彩为净赢赔率；中奖返还 = 本金 × (赔率 + 1)。
# Rules: https://www.pokerstars.com/casino/how-to-play/live/side-bet-city/
THREE_CARD_PAYOUT = {9: 100, 8: 40, 3: 35, 4: 5, 5: 4, 1: 1}
FIVE_CARD_PAYOUT = {9: 1000, 8: 250, 7: 100, 6: 50, 5: 40, 4: 25, 3: 7, 2: 4, 1: 1}
SEVEN_CARD_PAYOUT = {9: 500, 8: 100, 7: 50, 6: 7, 5: 5, 4: 4, 3: 3}
ALL_LOSE_PAYOUT = 0.7
BET_TYPES = ("three_card", "five_card", "seven_card", "all_lose")
BET_NAMES = {"three_card": "3张牌", "five_card": "5张牌", "seven_card": "7张牌", "all_lose": "全输"}
GAME_NAME = '霓虹扑克'
HAND_TITLES = {'three_card': '首三张', 'five_card': '四五张', 'seven_card': '六七张'}
DEFAULT_BETTING_STATUS = '设置下注金额并开始游戏'
AUTO_RESET_STATUS = '30秒已到，可设置下一局下注'
PROGRESSIVE_COST = 2.50
MIN_PROGRESSIVE = 271288.59
# 对应：上方3张 + For 5 Cards 的第0张 + For 7 Cards 的第1张。
PROGRESSIVE_CARD_INDICES = (0, 1, 2, 3, 6)
CARD_SIZE = (80, 112)
DEAL_FRAME_MS = 20
FLIP_FRAME_MS = 30
STAGE_PAUSE_MS = 1400

# 继续使用原项目的加密账户接口及 Progressive_2.50 共享奖池。
def get_data_file_path():
    parent_dir = _PROJECT_ROOT
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
# Progressive 文件加载与保存 (Key: 'Progressive_2.50')
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

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.value = RANK_VALUES[rank]
    def __repr__(self):
        return f"{self.rank}{self.suit}"

class Deck:
    def __init__(self):
        parent_dir = _PROJECT_ROOT
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
# 五张牌评估（保留 Side Bet City 原逻辑）
# =========================================================
def evaluate_five_card_hand(cards):
    if not cards or len(cards) != 5:
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


def money(value):
    """所有实际扣款和返还按分取整。"""
    from decimal import Decimal, ROUND_HALF_UP
    return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def evaluate_three_card_hand(cards):
    """3张牌只返回一个最高牌型；顺子、同花各只需3张。"""
    if len(cards) != 3:
        raise ValueError("3张牌评估必须使用3张牌")
    values = sorted((c.value for c in cards), reverse=True)
    counts = Counter(values)
    flush = len({c.suit for c in cards}) == 1
    straight = len(counts) == 3 and (values[0] - values[2] == 2 or values == [14, 3, 2])
    straight_values = [3, 2, 1] if values == [14, 3, 2] else values
    if flush and straight:
        return (9 if values == [14, 13, 12] else 8, straight_values)
    # 3张牌中：三条 > 顺子 > 同花 > 对子 > 高牌。
    if 3 in counts.values():
        return (3, values)
    if straight:
        return (4, straight_values)
    if flush:
        return (5, values)
    if 2 in counts.values():
        return (1, sorted(counts, key=lambda v: (counts[v], v), reverse=True))
    return (0, values)


def evaluate_seven_card_hand(cards):
    """从7张牌的21个五张组合中取最佳结果，不改变原牌顺序。"""
    if len(cards) != 7:
        raise ValueError("7张牌评估必须使用7张牌")
    return max(evaluate_five_card_hand(list(hand)) for hand in combinations(cards, 5))


def get_best_five_cards(cards):
    if len(cards) != 7:
        raise ValueError("需要7张牌")
    return list(max(combinations(cards, 5), key=lambda hand: evaluate_five_card_hand(list(hand))))


def get_hand_payout(bet_type, cards):
    if bet_type == 'three_card':
        rank, _ = evaluate_three_card_hand(cards)
        return THREE_CARD_PAYOUT.get(rank, 0)
    if bet_type == 'five_card':
        if len(cards) != 5:
            raise ValueError("5张牌评估必须使用5张牌")
        rank, values = evaluate_five_card_hand(cards)
        if rank == 1 and values[0] < 11:
            return 0
        return FIVE_CARD_PAYOUT.get(rank, 0)
    if bet_type == 'seven_card':
        rank, _ = evaluate_seven_card_hand(cards)
        return SEVEN_CARD_PAYOUT.get(rank, 0)
    raise ValueError(f"无效的牌型下注: {bet_type}")


def calculate_progressive_payout(cards, jackpot):
    """沿用原程序奖金标准；2.50参与费不另外退还。"""
    if len(cards) != 5:
        raise ValueError("Progressive 必须使用指定的5张牌")
    rank, _ = evaluate_five_card_hand(cards)
    if rank == 9:
        return money(jackpot)
    if rank == 8:
        return money(jackpot * 0.1)
    return {7: 1250.0, 6: 375.0, 5: 250.0}.get(rank, 0.0)


class SideBetCityGame:
    """不依赖界面的发牌、牌型和结算状态。每项下注只结算一次。"""
    def __init__(self):
        self.progressive_amount = money(load_jackpot()[1])
        self.min_progressive = MIN_PROGRESSIVE
        self.reset_game()

    def reset_game(self):
        self.deck = None
        self.cards = []
        self.stage = 'betting'
        self.revealed_count = 0
        self.bets = {key: 0 for key in BET_TYPES}
        self.jackpot_bet = 0
        self.results = {}
        self.pool_updated = False

    @property
    def three_card_hand(self):
        return self.cards[:3]

    @property
    def five_extra_cards(self):
        return self.cards[3:5]

    @property
    def seven_extra_cards(self):
        return self.cards[5:7]

    @property
    def five_card_hand(self):
        return self.cards[:5]

    @property
    def seven_card_hand(self):
        return self.cards[:7]

    @property
    def progressive_hand(self):
        return [self.cards[i] for i in PROGRESSIVE_CARD_INDICES] if len(self.cards) == 7 else []

    @property
    def total_bet(self):
        return money(sum(self.bets.values()) + (PROGRESSIVE_COST if self.jackpot_bet else 0))

    def start_round(self, bets, jackpot_bet=False):
        if self.stage != 'betting':
            raise ValueError("本局尚未结束")
        checked = {}
        for key in BET_TYPES:
            value = float(bets.get(key, 0))
            if not math.isfinite(value) or value < 0 or not value.is_integer():
                raise ValueError("下注金额必须为非负整数")
            checked[key] = int(value)
        if not any(checked.values()):
            raise ValueError("请至少选择一个下注项目")
        deck = Deck()
        # 开局一次取出7张，之后的每个阶段只翻牌，不再发牌。
        cards = deck.deal(7)
        if len(cards) != 7 or len({(c.suit, c.rank) for c in cards}) != 7:
            raise ValueError("牌堆返回了无效的7张牌")
        self.deck = deck
        self.cards = cards
        self.bets = checked
        self.jackpot_bet = int(bool(jackpot_bet))
        self.results = {}
        self.revealed_count = 0
        self.pool_updated = False
        self.stage = 'dealing'

    def advance_stage(self):
        next_stages = {'dealing': ('three_card', 3), 'three_card': ('five_card', 5),
                       'five_card': ('seven_card', 7)}
        if self.stage not in next_stages:
            raise ValueError("没有可翻开的下一阶段")
        self.stage, self.revealed_count = next_stages[self.stage]
        return self.stage

    def hand_result(self, bet_type):
        hands = {'three_card': self.three_card_hand, 'five_card': self.five_card_hand,
                 'seven_card': self.seven_card_hand}
        cards = hands[bet_type]
        if bet_type == 'three_card':
            rank, _ = evaluate_three_card_hand(cards)
        elif bet_type == 'five_card':
            rank, _ = evaluate_five_card_hand(cards)
        else:
            rank, _ = evaluate_seven_card_hand(cards)
        odds = get_hand_payout(bet_type, cards)
        stake = self.bets[bet_type]
        return {'rank': rank, 'hand_name': HAND_RANK_NAMES[rank], 'odds': odds,
                'qualifies': odds > 0, 'stake': stake,
                'return': money(stake * (odds + 1)) if odds > 0 else 0.0}

    def _settle_hand(self, bet_type):
        if bet_type in self.results:
            return {}
        result = self.hand_result(bet_type)
        self.results[bet_type] = result
        return {bet_type: result}

    def _settle_end_bets(self):
        added = {}
        if 'all_lose' not in self.results:
            # 判定依据三个牌型是否中奖，与玩家实际下注哪些项目无关。
            qualifies = all(not self.results[key]['qualifies'] for key in BET_TYPES[:3])
            stake = self.bets['all_lose']
            result = {'qualifies': qualifies, 'stake': stake, 'odds': ALL_LOSE_PAYOUT,
                      'return': money(stake * (1 + ALL_LOSE_PAYOUT)) if qualifies else 0.0}
            self.results['all_lose'] = result
            added['all_lose'] = result
        if 'progressive' not in self.results:
            cards = self.progressive_hand
            rank, _ = evaluate_five_card_hand(cards)
            bonus = calculate_progressive_payout(cards, self.progressive_amount) if self.jackpot_bet else 0.0
            result = {'rank': rank, 'hand_name': HAND_RANK_NAMES[rank],
                      'cards': [str(c) for c in cards], 'qualifies': rank >= 5,
                      'stake': PROGRESSIVE_COST if self.jackpot_bet else 0.0, 'return': bonus}
            self.results['progressive'] = result
            added['progressive'] = result
            if self.jackpot_bet:
                self.progressive_amount = max(MIN_PROGRESSIVE, money(self.progressive_amount - bonus))
        if not self.pool_updated:
            contribution = sum(self.bets.values()) * 0.001 + (PROGRESSIVE_COST * 0.95 if self.jackpot_bet else 0)
            self.progressive_amount = money(max(MIN_PROGRESSIVE, self.progressive_amount) + contribution)
            self.pool_updated = True
        return added

    def settle_stage(self):
        if self.stage not in BET_TYPES[:3]:
            raise ValueError("当前阶段不能结算牌型")
        added = self._settle_hand(self.stage)
        if self.stage == 'seven_card':
            added.update(self._settle_end_bets())
        return added

    def finish_round(self):
        """关闭界面时也结算已锁定的牌局，避免遗漏或重复返还。"""
        if len(self.cards) != 7:
            return {}
        added = {}
        for key in BET_TYPES[:3]:
            added.update(self._settle_hand(key))
        added.update(self._settle_end_bets())
        self.revealed_count = 7
        self.stage = 'complete'
        return added


def side_bet_city_log_path():
    log_dir = os.path.join(_PROJECT_ROOT, 'A_Logs', 'Json')
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, 'Side_Bet_City.json')


def save_side_bet_city_history(game, balance):
    path = side_bet_city_log_path()
    stats = {'game': 0, 'three_card_win': 0, 'five_card_win': 0, 'seven_card_win': 0,
             'all_lose_win': 0, 'progressive_win': 0}
    data = {'history_record': stats, 'history': []}
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            stats.update(loaded.get('history_record', {}))
            data['history'] = loaded.get('history', [])
    stats['game'] += 1
    for key in BET_TYPES + ('progressive',):
        if game.results[key]['return'] > 0:
            stats[f'{key}_win'] += 1
    data['history'].append({
        'game_id': max((rec.get('game_id', 0) for rec in data['history']), default=0) + 1,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'deck_order': [str(c) for c in game.deck.full_deck], 'cut_position': game.deck.cut_position,
        'cards': [str(c) for c in game.cards], 'three_card_hand': [str(c) for c in game.three_card_hand],
        'for_five_cards': [str(c) for c in game.five_extra_cards],
        'for_seven_cards': [str(c) for c in game.seven_extra_cards],
        'seven_card_best_five': [str(c) for c in get_best_five_cards(game.cards)],
        'progressive_indices': list(PROGRESSIVE_CARD_INDICES),
        'progressive_cards': [str(c) for c in game.progressive_hand],
        'bets': dict(game.bets), 'result': dict(game.results), 'total_bet': game.total_bet,
        'total_return': money(sum(result['return'] for result in game.results.values())),
        'balance_after': money(balance),
    })
    data['history'] = data['history'][-50:]
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

class SideBetCityGUI(tk.Frame):
    """UTH 牌桌与控件，配合 Side Bet City 的单人牌型结算。"""

    WIDTH, HEIGHT = 1150, 750
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    DEAL_CARD_MS = 224 / .85
    DEAL_MOVE_MS = (128 / .75) / .85
    BET_CHIP_RADIUS = 16 * 4 / 3
    CASHIER_POS = (575, 43)
    ALL_LOSE_NOTICE_POS = (575, 411)
    PROGRESSIVE_LAMP_WIDTH = 122.0 * .8
    PLAYER = 'Player'
    TABLE_GREEN = '#2A5541'
    HAND_GROUPS = (
        ('three_card', '首三张', 230, 526),
        ('five_card', '四五张', 528, 722),
        ('seven_card', '六七张', 724, 918),
    )

    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = username, money(initial_balance)
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game = SideBetCityGame()
        self.bets = self._empty_bets()
        self.last_bet = None
        self.last_win = 0.0
        self.round_return = 0.0
        self.high_bet_mode = False
        self.selected_chip = 10.0
        self.animation_in_progress = False
        self._game_instruction_dialog = None
        self._sequence_window = None
        self._jobs = set()
        self._round_token = 0
        self._closing = False
        self._credited = False
        self._return_persisted = False
        self._crediting = False
        self._restart_job = None
        self._restart_deadline = None
        self._motion_count = 0
        self._chip_serial = 0
        self._all_lose_collected = False
        self.history_saved = self.pool_saved = False
        self.visual_chips, self.lamps = {}, {}
        self.last_round_snapshot = None
        self._history_available = False
        self._notice_level = 0.0
        self._notice_target = False
        self._notice_job = self._notice_item = self._notice_source = None
        self._notice_photo = self._notice_text_item = None
        self._face_photos, self._pil_cards, self._flip_photos = {}, {}, {}
        self._faded_photos, self._settled_card_photos = {}, {}
        self.card_items, self.bet_spots, self.title_items = {}, {}, {}
        self.bet_summary_items = {}
        self._hand_usage_keys = {}
        self._usage_owner = None
        self.best_five_card_indices = ()
        self._load_assets()
        self._create_widgets()
        self._refresh()
        self.bind('<Configure>', self._center_table, add='+')
        self.bind('<Destroy>', self._on_destroy, add='+')

    @staticmethod
    def _empty_bets():
        return dict.fromkeys((*BET_TYPES, 'jackpot'), 0)

    @property
    def game_in_progress(self):
        return self.game.stage != 'betting' or self._motion_count > 0

    def _schedule(self, delay, callback, *args):
        token = self._round_token
        job = None

        def run():
            self._jobs.discard(job)
            if not self._closing and token == self._round_token:
                callback(*args)

        job = self.after(delay, run)
        self._jobs.add(job)
        return job

    def _cancel_jobs(self):
        self._round_token += 1
        for job in tuple(self._jobs):
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self._jobs.clear()
        for lamp in self.lamps.values():
            lamp['job'] = None
            lamp.pop('filled_callback', None)
        self._restart_job = self._notice_job = None

    def _on_destroy(self, event):
        if event.widget is self:
            self._closing = True
            self._cancel_jobs()
            self._unbind_enter()

    def _unbind_enter(self):
        binding = getattr(self, '_enter_binding', None)
        if binding:
            try:
                self.winfo_toplevel().unbind('<Return>', binding)
            except tk.TclError:
                pass
            self._enter_binding = None

    def _center_table(self, event=None):
        self.canvas.place(x=max(0, (self.winfo_width() - self.WIDTH) // 2),
                          y=max(0, (self.winfo_height() - self.HEIGHT) // 2),
                          width=self.WIDTH, height=self.HEIGHT)

    def _create_widgets(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=ROOT_BG, highlightthickness=0)
        self.canvas.place(x=0, y=0, width=self.WIDTH, height=self.HEIGHT)
        # 保留原入口常用的 Canvas 名称。
        self.table_canvas = self.canvas
        self.control_buttons = {}
        c = self.canvas
        self._text(187, 44, GAME_NAME, 16, GOLD)
        self._text(957, 44, 'Side Bet City', 14, GOLD)
        self._text(575, 45, '单人玩法', 12, PANEL_BG)
        self._text(575, 95, 'SIDE BET CITY', 22, GOLD)
        self._text(575, 127, '3 张 · 5 张 · 7 张 · 全输', 13, PANEL_BG)
        self.street_item = self._text(575, 161, '下注阶段', 14, PANEL_BG)
        self._draw_limit_table()
        self._draw_progressive_panel()

        c.create_rectangle(22, 191, 1128, 387, fill=ROOT_BG, outline='#65784B')
        c.create_line(25, 192, 1125, 192, fill='#E0C879', width=2)
        c.create_line(25, 386, 1125, 386, fill='#0C241B', width=2)
        self._text(125, 230, '最低获胜牌型', 13, GOLD)
        for y, caption in ((270, '3 张：任意一对'),
                           (307, '5 张：J 对或以上'),
                           (344, '7 张：三条')):
            self._text(125, y, caption, 12, PANEL_BG)
        self._text(1020, 249, '累进大奖取牌', 13, GOLD)
        self._text(1020, 281, '① ② ③ ④ ⑦', 14, PANEL_BG)
        self._text(1020, 323, '固定五张牌\n同花或以上中奖', 11, PANEL_BG)

        for kind, title, left, right in self.HAND_GROUPS:
            tag = 'hand_' + kind
            self._rounded_rectangle(left, 224, right, 359, 12,
                                    fill='#234838', outline='#667B55', width=1, tags=tag)
            self.title_items[kind] = self._text((left + right) / 2, 207, title,
                                               14, PANEL_BG, tags=tag)
            c.tag_bind(tag, '<Enter>', lambda _e, k=kind: self._on_hand_usage_hover(k))
            c.tag_bind(tag, '<Leave>', self._on_hand_usage_leave)
        for index in range(7):
            x, y = self.card_position('Cards', index)
            c.create_rectangle(x, y, x + self.CARD_WIDTH, y + self.CARD_HEIGHT,
                               outline='#B59C6A', dash=(3, 3), tags='card_slots')
            selected = index in PROGRESSIVE_CARD_INDICES
            self._text(x + self.CARD_WIDTH / 2, 372, str(index + 1), 10,
                       GOLD if selected else '#91A58B')

        c.create_rectangle(22, 449, 1128, 617, fill=self.TABLE_GREEN, outline='')
        self._text(575, 466, '玩家下注', 16, PANEL_BG, tags='bet_panel_title')
        bet_y, bet_radius = 552, 40
        for kind, cx, detail in (
            ('three_card', 248, '首 3 张'),
            ('five_card', 404, '前 5 张'),
            ('seven_card', 560, '7选5佳'),
            ('all_lose', 716, '⬅ 全输'),
        ):
            tag = 'spot_' + self.PLAYER + '_' + kind
            self._text(cx, 490, detail, 11, GOLD)
            border = c.create_oval(cx - bet_radius, bet_y - bet_radius,
                                   cx + bet_radius, bet_y + bet_radius,
                                   fill=self.TABLE_GREEN, outline=PANEL_BG, width=2, tags=tag)
            self._register_spot(self.PLAYER, kind, cx, bet_y, border, BET_NAMES[kind])
            self.bet_summary_items[kind] = self._text(cx, 607, '', 11, PANEL_BG)
        self._draw_progressive_lamp(self.PLAYER, 948, bet_y)
        self._draw_bottom_controls()

    def _draw_limit_table(self):
        c = self.canvas
        left, right, top = 30, 349, 75
        c.create_rectangle(left, top, right, 181, fill=ROOT_BG, outline=GOLD, width=2, tags='limits')
        c.create_rectangle(left, top, right, top + 29, fill=ROOT_BG, outline=GOLD, tags='limits')
        self._text((left + right) / 2, top + 14, '下注上限', 13, PANEL_BG, tags='limits')
        self.limit_value_items = []
        for col, title in enumerate(('每项下注最低', '每项下注最高')):
            x0 = left + col * (right - left) / 2
            x1 = left + (col + 1) * (right - left) / 2
            c.create_rectangle(x0, top + 29, x1, top + 66, outline='#77906B', tags='limits')
            c.create_rectangle(x0, top + 66, x1, 181, outline='#77906B', tags='limits')
            self._text((x0 + x1) / 2, top + 47, title, 11, PANEL_BG, tags='limits')
            self.limit_value_items.append(self._text((x0 + x1) / 2, top + 86, '', 12, GOLD, tags='limits'))
        c.tag_bind('limits', '<Button-1>', self.toggle_high_bet_limits)
        c.tag_bind('limits', '<Enter>', lambda _e: c.configure(cursor='hand2'))
        c.tag_bind('limits', '<Leave>', lambda _e: c.configure(cursor=''))

    def card_position(self, side, index):
        # 三组牌都属于同一玩家，不存在底牌/公共牌/庄家牌的区分。
        if not 0 <= index < 7:
            raise ValueError('牌位必须为 0–6')
        return 248 + index * 92 + (12 if index >= 3 else 0) + (12 if index >= 5 else 0), 236

    def _status(self, message):
        self.current_status = message

    def _refresh(self):
        if self._closing:
            return
        c, stage = self.canvas, self.game.stage
        c.itemconfigure(self.balance_item, text=f'余额: ${self.balance:,.2f}')
        total = money(sum(self.bets.values()))
        c.itemconfigure(self.total_item, text=f'本局下注: ${total:,.2f}' if total else f'上局返还: ${self.last_win:,.2f}')
        minimum, maximum = self._bet_limits()
        for item, value in zip(self.limit_value_items, (f'${minimum:,}', f'${maximum:,}')):
            c.itemconfigure(item, text=value)
        self._render_chips()
        betting = stage == 'betting' and self._motion_count == 0
        restarting = stage in ('await_restart', 'returning', 'credit_pending', 'sweeping')
        self.set_control_button_state(self.clear_button, betting)
        self.set_control_button_state(self.repeat_button, betting and bool(self.last_bet))
        self.set_control_button_state(self.start_button, betting)
        c.itemconfigure(self.repeat_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button, state='normal' if restarting else 'hidden')
        self.set_control_button_state(self.restart_button, stage in ('await_restart', 'credit_pending'))
        caption = {
            'betting': '下注阶段', 'progressive': '累进大奖准备中', 'dealing': '派牌中',
            'three_card': '3 张牌阶段', 'five_card': '5 张牌阶段', 'seven_card': '7 张牌阶段',
            'complete': '已结算', 'settling': '派彩中', 'await_restart': '已结算',
            'returning': '筹码返回中', 'credit_pending': '重试保存余额', 'sweeping': '收牌中',
        }.get(stage, stage)
        c.itemconfigure(self.street_item, text=caption)
        self._status(caption)
        for kind in BET_TYPES:
            result = self.game.results.get(kind)
            summary = ''
            if result is not None:
                summary = result.get('hand_name', '全输' if result['qualifies'] else '')
            won = result is not None and result['return'] > 0
            c.itemconfigure(self.bet_summary_items[kind], text=summary, fill=GOLD if won else PANEL_BG)
            c.itemconfigure(self.bet_spots[(self.PLAYER, kind)]['border'], outline=GOLD if won else PANEL_BG)

    def _bet_limits(self):
        return (100, 50000) if self.high_bet_mode else (10, 10000)

    def select_chip(self, amount):
        if self.game.stage == 'betting' and not self._motion_count:
            self.selected_chip = amount
            self._draw_chips()

    def add_chip_to_bet(self, seat, kind=None):
        if kind is None:
            kind, seat = seat, self.PLAYER
        if seat != self.PLAYER or kind not in self.bets or self.game_in_progress:
            return
        new_bets = dict(self.bets)
        if kind == 'jackpot':
            new_bets[kind] = 0 if new_bets[kind] else PROGRESSIVE_COST
        else:
            _, maximum = self._bet_limits()
            if new_bets[kind] >= maximum:
                return
            new_bets[kind] = int(min(maximum, new_bets[kind] + self.selected_chip))
        self._apply_bet_layout(new_bets)

    def reset_single_bet(self, seat, kind=None):
        if kind is None:
            kind, seat = seat, self.PLAYER
        if seat != self.PLAYER or kind not in self.bets or self.game_in_progress:
            return
        new_bets = dict(self.bets)
        new_bets[kind] = 0
        self._apply_bet_layout(new_bets)

    def reset_bets(self):
        if not self.game_in_progress:
            self._apply_bet_layout(self._empty_bets())

    def apply_last_bet(self):
        if self.game_in_progress or not self.last_bet:
            return
        minimum, maximum = self._bet_limits()
        restored = {
            kind: min(maximum, max(minimum, amount)) if amount else 0
            for kind, amount in self.last_bet.items() if kind in BET_TYPES
        }
        restored['jackpot'] = self.last_bet['jackpot']
        self._apply_bet_layout(restored)

    def toggle_high_bet_limits(self, event=None):
        if self.game_in_progress:
            return
        if not self.high_bet_mode:
            password = simpledialog.askstring('高额下注', '请输入密码：', parent=self)
            if password is None:
                return
            if password.strip() != time.strftime('%H%M'):
                messagebox.showerror('错误', '密码错误', parent=self)
                return
        self.high_bet_mode = not self.high_bet_mode
        self.reset_bets()
        self.last_bet = None
        self.selected_chip = 100 if self.high_bet_mode else 10
        self._draw_chips()
        self._refresh()

    def _apply_bet_layout(self, new_bets):
        previous, self.bets = self.bets, dict(new_bets)
        transfers = []
        for kind in self._empty_bets():
            old, new = previous[kind], self.bets[kind]
            delta = new - old
            if not delta:
                continue
            center = self.bet_spots[(self.PLAYER, kind)]['center']
            if delta > 0:
                transfers.append(dict(amount=delta, start=self._rack_position(), target=center,
                    arrive=lambda k=kind, a=new: self._set_visual(self.PLAYER, k, 'stake', a)))
            else:
                self._set_visual(self.PLAYER, kind, 'stake', new)
                transfers.append(dict(amount=-delta, start=center, target=self._rack_position(), duration=440))
        self._set_lamp_mode(self.PLAYER, 'spin' if self.bets['jackpot'] else 'off')
        self._run_chip_batch(transfers, self._refresh)
        self._refresh()

    def _persist_balance(self):
        try:
            if self.username and self.username != 'Guest':
                update_balance_in_json(self.username, money(self.balance))
        except Exception as exc:
            messagebox.showerror('余额保存失败', str(exc), parent=self)
            return False
        if callable(self.on_balance_change):
            try:
                self.on_balance_change(float(self.balance))
            except Exception as exc:
                # 界面通知失败不等于账户保存失败，不能因此重复扣款或入账。
                print(f'通知余额变更失败: {exc}')
        return True

    def update_balance(self):
        self.balance = money(self.balance)
        self._refresh()
        return self._persist_balance()

    def start_game(self):
        if self.game_in_progress or self._closing:
            return
        try:
            bets = {kind: self.bets[kind] for kind in BET_TYPES}
            minimum, maximum = self._bet_limits()
            for kind, amount in bets.items():
                if not math.isfinite(amount) or amount < 0 or (amount and not minimum <= amount <= maximum):
                    raise ValueError(f'{BET_NAMES[kind]}下注范围为 ${minimum:,}–${maximum:,}，也可不下注')
            total = money(sum(bets.values()) + (PROGRESSIVE_COST if self.bets['jackpot'] else 0))
            if total > self.balance:
                raise ValueError('余额不足以支付所有下注')
            self.game.start_round(bets, bool(self.bets['jackpot']))
        except (ValueError, OverflowError) as exc:
            messagebox.showwarning('无法开始游戏', str(exc), parent=self)
            return

        before = self.balance
        self.balance = money(before - total)
        if not self._persist_balance():
            self.balance = before
            self.game.reset_game()
            self._refresh()
            return
        self._cancel_jobs()
        self._cancel_restart_timer()
        self._close_card_sequence()
        self._history_available = False
        self.last_bet = dict(self.bets)
        self._credited = self._return_persisted = False
        self.history_saved = self.pool_saved = False
        self._all_lose_collected = False
        self.round_return = 0.0
        self._jackpot_before = self.game.progressive_amount
        self.animation_in_progress = True
        self.canvas.delete('cards')
        self.card_items.clear()
        self._flip_photos.clear()
        self._faded_photos.clear()
        self._settled_card_photos.clear()
        self._hand_usage_keys.clear()
        self._usage_owner = None
        self.best_five_card_indices = ()
        self._fade_all_lose_notice(False)
        self._load_assets()
        for kind, title, _left, _right in self.HAND_GROUPS:
            self.canvas.itemconfigure(self.title_items[kind], text=title)
        self._start_progressive_lamps()

    def _start_progressive_lamps(self):
        self.game.stage = 'progressive'
        if self.bets['jackpot']:
            self.lamps[self.PLAYER]['filled_callback'] = self._collect_progressive_and_deal
            self._set_lamp_mode(self.PLAYER, 'fill')
        else:
            self._set_lamp_mode(self.PLAYER, 'off')
            self._schedule(0, self._collect_progressive_and_deal)
        self._refresh()

    def _collect_progressive_and_deal(self):
        chip = self.visual_chips.pop((self.PLAYER, 'jackpot', 'stake'), None)
        self.game.stage = 'dealing'
        self._refresh()
        transfers = [dict(amount=chip['amount'], start=chip['xy'], target=self.CASHIER_POS, duration=280)] if chip else []
        self._run_chip_batch(transfers, lambda: self._deal_next_card(0))

    def _deal_next_card(self, index):
        if index == 7:
            self.animation_in_progress = False
            self._schedule(500, self.reveal_next_stage)
            return
        x, y = self.card_position('Cards', index)
        group = 'three_card' if index < 3 else 'five_card' if index < 5 else 'seven_card'
        item = self.canvas.create_image(575, 52, image=self._face_photos['back'], anchor='nw',
                                        tags=('cards', 'hand_' + group))
        self.card_items[('Cards', index)] = item

        def move(step=0):
            fraction = step / 6
            self.canvas.coords(item, 575 + (x - 575) * fraction, 52 + (y - 52) * fraction)
            if step < 6:
                self._schedule(round(self.DEAL_MOVE_MS * (step + 1) / 6) - round(self.DEAL_MOVE_MS * step / 6), move, step + 1)
            else:
                self._schedule(round(self.DEAL_CARD_MS) - round(self.DEAL_MOVE_MS), self._deal_next_card, index + 1)

        move()

    def reveal_next_stage(self):
        if self.game.stage not in ('dealing', 'three_card', 'five_card') or self.animation_in_progress:
            return
        stage = self.game.advance_stage()
        self.animation_in_progress = True
        self._refresh()
        indices = {'three_card': (0, 1, 2), 'five_card': (3, 4), 'seven_card': (5, 6)}[stage]
        self._reveal_next(indices, 0, lambda: self._after_stage_reveal(stage))

    def _reveal_next(self, indices, offset, complete):
        if offset == len(indices):
            complete()
            return
        index = indices[offset]
        card, item = self.game.cards[index], self.card_items[('Cards', index)]
        x, y = self.card_position('Cards', index)
        w, h = self.card_size('Cards')

        def flip(step=0):
            width = max(1, round(w * abs(1 - step / 5)))
            source = self._pil_cards['back' if step < 5 else self._card_image_key(card)]
            photo = ImageTk.PhotoImage(source.resize((width, h), Image.Resampling.LANCZOS), master=self)
            self._flip_photos[item] = photo
            self.canvas.itemconfigure(item, image=photo)
            self.canvas.coords(item, x + (w - width) / 2, y)
            if step < 10:
                self._schedule(32, flip, step + 1)
            else:
                self.canvas.itemconfigure(item, image=self._face_photos[self._card_image_key(card)])
                self._flip_photos.pop(item, None)
                self._reveal_next(indices, offset + 1, complete)

        flip()

    def _after_stage_reveal(self, stage):
        if stage != self.game.stage:
            return
        added = self.game.settle_stage()
        self.round_return = money(sum(result['return'] for result in self.game.results.values()))
        transfers = []
        for kind, result in added.items():
            if kind in BET_TYPES:
                transfers.extend(self._outcome_transfers(self.PLAYER, kind, result['stake'], result['return']))
        if not self._all_lose_collected and any(self.game.results[kind]['qualifies']
                                               for kind in BET_TYPES[:3] if kind in self.game.results):
            self._all_lose_collected = True
            if 'all_lose' not in added:
                transfers.extend(self._outcome_transfers(self.PLAYER, 'all_lose', self.game.bets['all_lose'], 0))
        self.update_hand_labels()
        self._refresh()

        def finished():
            self.animation_in_progress = False
            if stage == 'seven_card':
                self._settle_complete()
            else:
                self._schedule(STAGE_PAUSE_MS, self.reveal_next_stage)

        self._run_chip_batch(transfers, finished)

    def update_hand_labels(self):
        for kind in BET_TYPES[:3]:
            if kind in self.game.results:
                self.canvas.itemconfigure(self.title_items[kind],
                    text=f"{HAND_TITLES[kind]} · {self.game.results[kind]['hand_name']}")

    def _persist_round(self):
        errors = []
        if not self.pool_saved:
            try:
                save_jackpot(self.game.progressive_amount)
                self.pool_saved = True
            except Exception as exc:
                errors.append('奖池保存失败')
                print(f'奖池保存失败: {exc}')
        if not self.history_saved:
            try:
                # UTH 风格：筹码返回后才入账；日志记录整局返还后的余额。
                final_balance = self.balance if self._credited else money(self.balance + self.last_win)
                save_side_bet_city_history(self.game, final_balance)
                self.history_saved = True
            except Exception as exc:
                errors.append('历史保存失败')
                print(f'历史保存失败: {exc}')
        return errors

    def _settle_complete(self):
        self.game.finish_round()
        self.game.stage = 'settling'
        self.last_win = self.round_return = money(sum(result['return'] for result in self.game.results.values()))
        self.update_hand_labels()
        self._render_hand_usage()
        progressive = self.game.results['progressive']
        bonus = progressive['return']
        self._set_lamp_mode(self.PLAYER, 'win' if bonus else 'off')
        self._fade_all_lose_notice(self.game.results['all_lose']['qualifies'])
        errors = self._persist_round()
        if errors:
            messagebox.showwarning('保存提示', '牌局已结算；' + '、'.join(errors), parent=self)
        self._refresh()
        self._pay_progressive_awards([(self.PLAYER, bonus)] if bonus else [], self._jackpot_before)

    def _await_next_round(self):
        if self.game.stage != 'settling':
            return
        self.game.stage = 'await_restart'
        deck = self.game.deck
        self.last_round_snapshot = dict(full_deck=tuple(deck.full_deck), start_pos=deck.start_pos,
            images={key: image.copy() for key, image in self.original_images.items()})
        self._history_available = True
        self._cancel_restart_timer()
        won = self.game.results['progressive']['return'] > 0
        if not won:
            self._restart_deadline = time.monotonic() + 30
        self._refresh()
        if not won:
            self._restart_tick()

    def _inspect_completed_round(self, event=None):
        if self.game.stage != 'await_restart':
            return
        self._cancel_restart_timer()
        self.show_card_sequence()

    def _return_all_chips(self):
        if self.game.stage == 'credit_pending':
            self._complete_chip_return()
            return
        if self.game.stage != 'await_restart':
            return
        self._cancel_restart_timer()
        self._history_available = False
        self._close_card_sequence()
        self.game.stage = 'returning'
        chips = list(self.visual_chips.values())
        self.visual_chips.clear()
        transfers = []
        for index, chip in enumerate(chips):
            target = self._rack_position(index, len(chips))

            def arrived(chip=chip, target=target, index=index):
                self._draw_chip(f'returned_chip_{index}', chip['amount'], *target,
                                chip.get('rectangular', False), extra_tags=('returned_chips',))

            transfers.append(dict(amount=chip['amount'], start=chip['xy'], target=target,
                                  rectangular=chip.get('rectangular', False), duration=600, arrive=arrived))
        self._refresh()
        self._run_chip_batch(transfers, self._complete_chip_return)

    def _credit_round_return(self):
        if self._crediting:
            return False
        if self._return_persisted:
            return True
        self._crediting = True
        try:
            if not self._credited:
                self.balance = money(self.balance + self.last_win)
                self._credited = True
            self._return_persisted = self._persist_balance()
            return self._return_persisted
        finally:
            self._crediting = False

    def _complete_chip_return(self):
        if self.game.stage not in ('returning', 'credit_pending'):
            return
        self.game.stage = 'credit_pending'
        if not self._credit_round_return():
            self._refresh()
            return
        self.game.stage = 'sweeping'
        self._refresh()
        self.canvas.delete('returned_chips')
        self._sweep_all_cards()

    def _finish_round(self):
        if self.game.stage != 'sweeping':
            return
        self._set_lamp_mode(self.PLAYER, 'off')
        self._fade_all_lose_notice(False)
        self.game.reset_game()
        self.bets = self._empty_bets()
        self._faded_photos.clear()
        self._settled_card_photos.clear()
        self._hand_usage_keys.clear()
        self._usage_owner = None
        self.best_five_card_indices = ()
        self._all_lose_collected = False
        self.animation_in_progress = False
        self._history_available = False
        for kind, title, _left, _right in self.HAND_GROUPS:
            self.canvas.itemconfigure(self.title_items[kind], text=title)
        self._refresh()

    def reset_game(self, auto_reset=False):
        if self.game.stage in ('await_restart', 'credit_pending'):
            self._return_all_chips()
        elif not self.game_in_progress:
            self.reset_bets()

    def _settle_before_close(self):
        if not self.game.cards:
            return self._persist_balance()
        self._cancel_restart_timer()
        self._cancel_jobs()
        self._motion_count = 0
        self.animation_in_progress = False
        self.canvas.delete('moving_chips')
        self.game.finish_round()
        self.last_win = self.round_return = money(sum(result['return'] for result in self.game.results.values()))
        self.game.stage = 'credit_pending'
        self._persist_round()
        if not self._credit_round_return():
            self._refresh()
            return False
        return True

    def on_close(self):
        if self._closing or self._crediting:
            return
        # 本局七张牌开局已锁定，不需要对抗或任何加注决定，可直接结清。
        if not self._settle_before_close():
            return
        self._closing = True
        self._cancel_jobs()
        self._unbind_enter()
        self._close_card_sequence()
        self._close_instructions()
        if callable(self.on_back):
            self.on_back(float(self.balance))
        else:
            self.winfo_toplevel().destroy()

    def destroy(self):
        if not self._closing:
            if not self._settle_before_close():
                return
            self._closing = True
        self._cancel_jobs()
        self._unbind_enter()
        self._close_card_sequence()
        self._close_instructions()
        super().destroy()

    def _close_instructions(self):
        dialog = self._game_instruction_dialog
        self._game_instruction_dialog = None
        if dialog is not None:
            try:
                if dialog.winfo_exists():
                    dialog.destroy()
            except tk.TclError:
                pass

    def _render_hand_usage(self):
        best = {(card.suit, card.rank) for card in get_best_five_cards(self.game.cards)}
        self.best_five_card_indices = tuple(index for index, card in enumerate(self.game.cards)
                                           if self._card_image_key(card) in best)
        self._hand_usage_keys = {
            'three_card': set(range(3)), 'five_card': set(range(5)),
            'seven_card': set(self.best_five_card_indices),
        }
        self._faded_photos.clear()
        self._settled_card_photos.clear()
        for (_side, index), item in self.card_items.items():
            source = self._pil_cards[self._card_image_key(self.game.cards[index])].convert('RGBA')
            self._settled_card_photos[item] = ImageTk.PhotoImage(source, master=self)
            self._fade_card_item(item, source)
        self._apply_hand_usage('seven_card')

    def _apply_hand_usage(self, kind):
        used = self._hand_usage_keys[kind]
        for (_side, index), item in self.card_items.items():
            photos = self._settled_card_photos if index in used else self._faded_photos
            self.canvas.itemconfigure(item, image=photos[item])
        self._usage_owner = kind

    def _on_hand_usage_hover(self, kind):
        if self.game.stage in ('settling', 'await_restart') and kind in self._hand_usage_keys:
            self._apply_hand_usage(kind)

    def _on_hand_usage_leave(self, event=None):
        if self.game.stage in ('settling', 'await_restart') and self._hand_usage_keys:
            self._apply_hand_usage('seven_card')

    def _load_assets(self):
        size = (self.CARD_WIDTH, self.CARD_HEIGHT)
        self.current_poker_folder = ('Poker2' if self.current_poker_folder=='Poker1' else 'Poker1') if hasattr(self,'current_poker_folder') else random.choice(['Poker1','Poker2'])
        folder = self.current_poker_folder
        self.original_images = {}
        base = os.path.join(_PROJECT_ROOT, 'A_Tools', 'Card', folder)
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
        self._public_photos = {key:ImageTk.PhotoImage(im.resize(self.card_size('Public'),Image.Resampling.LANCZOS),master=self) for key,im in self._pil_cards.items()}

    def _text(self, x, y, text, size=12, color=TEXT, **kw):
        return self.canvas.create_text(x, y, text=text, fill=color, font=('Arial', size, 'bold'), **kw)

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
        label_item = self._text(cx,cy,label,14,PANEL_BG,angle=angle,tags=tag)
        self.bet_spots[(seat,kind)] = dict(tag=tag,center=(cx,cy),border=border,label=label_item)
        c.tag_bind(tag,'<Button-1>',lambda _e,s=seat,k=kind:self.add_chip_to_bet(s,k))
        c.tag_bind(tag,'<Button-3>',lambda _e,s=seat,k=kind:self.reset_single_bet(s,k))
        c.tag_bind(tag,'<Enter>',lambda _e:c.configure(cursor='hand2'))
        c.tag_bind(tag,'<Leave>',lambda _e:c.configure(cursor=''))

    def _rounded_rectangle(self, x0, y0, x1, y1, radius, **options):
        return self.canvas.create_polygon(
            x0+radius, y0, x1-radius, y0, x1, y0, x1, y0+radius,
            x1, y1-radius, x1, y1, x1-radius, y1, x0+radius, y1,
            x0, y1, x0, y1-radius, x0, y0+radius, x0, y0,
            smooth=True, splinesteps=24, **options)

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
        if abs(value)>=1000:return SideBetCityGUI._compact(value)
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

    def _outcome_transfers(self, seat, kind, stake, returned):
        """本金留位，盈利派至左上；未中奖筹码飞向统一结算点。"""
        if not stake:return []
        key=(seat,kind,'stake');center=self.bet_spots[(seat,kind)]['center']
        if returned<=0:
            chip=self.visual_chips.pop(key,None)
            return [dict(amount=chip['amount'],start=chip['xy'],target=self.CASHIER_POS,duration=280)] if chip else []
        profit=round(returned-stake,2)
        if profit<=0:return []
        target=(center[0]-32,center[1]-30)
        return [dict(amount=profit,start=self.CASHIER_POS,target=target,duration=440,
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

    def _restart_tick(self):
        self._restart_job=None
        if self.game.stage!='await_restart' or self._restart_deadline is None:return
        remaining=max(0,self._restart_deadline-time.monotonic())
        self._restart_caption(f'再来一局({math.ceil(remaining)})')
        if remaining<=0:
            self._return_all_chips()
            return
        self._restart_job=self._schedule(max(1,min(1000,math.ceil(remaining*1000))),self._restart_tick)

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
        # UTH 同款牌序窗口：730×750，九张一排，切牌位置高亮，滚动显示52张原始牌序。
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
                dealt_index=(idx-cut_pos)%52
                pos_bg=('light blue' if dealt_index<3 else 'light green' if dealt_index<5 else 'plum' if dealt_index<7 else bg)
                tk.Label(container,text=str(idx+1),bg=pos_bg,font=('Arial',9)).pack()
        content_frame.update_idletasks();canvas.configure(scrollregion=canvas.bbox('all'))

    def card_size(self, side):
        return self.CARD_WIDTH,self.CARD_HEIGHT

    @staticmethod
    def _card_image_key(card):
        return card.suit, card.rank

    def _fade_card_item(self, item, source):
        # 用alpha淡化，不破坏牌面原图，也不把透明PNG的边缘铺成白底。
        faded = source.convert('RGBA').copy()
        faded.putalpha(faded.getchannel('A').point(lambda value:round(value*.45)))
        photo = ImageTk.PhotoImage(faded,master=self)
        self._faded_photos[item] = photo
        self.canvas.itemconfigure(item,image=photo)

    def _sweep_all_cards(self):
        """入账后，七张扑克牌一起在0.2秒内向右移走。"""
        self._fade_all_lose_notice(False)
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

    def _make_all_lose_notice(self):
        """使用透明 RGBA 浮层，在牌桌内淡入，透明部分保留原始牌面。"""
        scale=3;width,height=420,48
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
            try:font=ImageFont.truetype(path,17*scale);break
            except OSError:continue
        self._notice_text_item=None
        if font is not None:
            text='全输：三个阶段均未达中奖条件';box=draw.textbbox((0,0),text,font=font)
            draw.text(((width*scale-(box[2]-box[0]))/2-box[0],
                       (height*scale-(box[3]-box[1]))/2-box[1]),text,font=font,fill='#FFF1D1')
        else:
            # 极少数无可供 Pillow 使用的中文字体的系统，交由 Tk 原生字体回退。
            self._notice_text_item=self._text(*self.ALL_LOSE_NOTICE_POS,'全输：三个阶段均未达中奖条件',14,'#FFF1D1',state='hidden',tags='all_lose_notice')
        self._notice_source=layer.resize((width,height),Image.Resampling.LANCZOS)
        self._notice_item=self.canvas.create_image(*self.ALL_LOSE_NOTICE_POS,state='hidden',tags='all_lose_notice')

    def _draw_all_lose_notice(self):
        alpha=self._notice_level
        if self._notice_item is None:return
        if alpha<=0:
            self.canvas.itemconfigure('all_lose_notice',state='hidden');return
        layer=self._notice_source.copy()
        layer.putalpha(self._notice_source.getchannel('A').point(lambda value:round(value*alpha)))
        self._notice_photo=ImageTk.PhotoImage(layer,master=self)
        self.canvas.itemconfigure(self._notice_item,image=self._notice_photo,state='normal')
        self.canvas.tag_raise('all_lose_notice')
        if self._notice_text_item is not None:
            background=(27,61,49);foreground=(255,241,209)
            color='#'+''.join(f'{round(a+(b-a)*alpha):02x}' for a,b in zip(background,foreground))
            self.canvas.itemconfigure(self._notice_text_item,state='normal',fill=color)
            self.canvas.tag_raise(self._notice_text_item)

    def _fade_all_lose_notice(self, visible):
        target=1.0 if visible else 0.0
        if self._notice_target==visible and (self._notice_job is not None or self._notice_level==target):return
        if self._notice_job is not None:
            try:self.after_cancel(self._notice_job)
            except tk.TclError:pass
            self._jobs.discard(self._notice_job);self._notice_job=None
        self._notice_target=visible
        if self._notice_source is None:
            if not visible:return
            self._make_all_lose_notice()
        start=self._notice_level
        def step(frame):
            self._notice_job=None
            self._notice_level=start+(target-start)*frame/12
            self._draw_all_lose_notice()
            if frame<12:self._notice_job=self._schedule(25,step,frame+1)
        step(0)

    def _instruction_pages(self):
        """Side Bet City玩法和赔率；说明窗口沿用 UTH。"""
        return [('玩法',
          '下注牌型，按固定赔率结算；无需与庄家或其他玩家比牌。',
          [('游戏目标',
            '',
            [('一副牌，三个阶段', '每局使用一副不含大小王的52张扑克牌。\n开局一次锁定7张牌，全部背面派好后，依次揭示3张、5张和7张的结果。'),
             ('牌桌布局', '七张牌从左至右按3＋2＋2摆放。\n首三张：左侧3张牌。\n四五张：中间2张，与首三张组成5张牌。\n六七张：右侧2张，从全部7张中取最佳5张。')],
            []),
           ('一局如何进行',
            '',
            [('开局前', '设置3张牌、5张牌、7张牌或全输下注，可同时选择多项，也可选择累进大奖。\n下注后点击“开牌”（或Enter），本局金额一次扣除。'),
             ('依次揭示', '先揭示首三张并结算3张牌下注；再揭示四五张并结算5张牌下注；最后揭示六七张，结算7张牌、全输与累进大奖。'),
             ('牌型标题', '每个区域只显示该阶段一个最高牌型，例如“首三张 - 高牌”。\n未揭示的区域只显示区域名称，不提前暴露牌型。'),
             ('最佳五张', '第6、7张全部翻开后，默认显示七张牌中的最佳五张，另外两张淡化。\n鼠标停留在各阶段牌组可查看该阶段用牌。\n牌不会重新排序，累进大奖取牌位置也不会改变。')],
            [])]),
         ('下注',
          '四项普通下注分别结算，累进大奖费用固定为每局$2.50。',
          [('下注项目',
            '',
            [],
            [('下注与判定范围',
              ['项目', '判定用牌', '最低中奖牌型'],
              [['3张牌', '首三张', '任意一对'],
               ['5张牌', '最先发出的5张', '一对J/Q/K/A'],
               ['7张牌', '7张中最佳5张', '三条'],
               ['全输', '检查全部三个阶段', '三个阶段均无可赔付牌型'],
               ['累进大奖', '指定的固定5张牌', '同花']]),
             ('下注限额',
              ['项目', '普通模式', '高额模式'],
              [['每项普通下注最低', '$10', '$100'], ['每项普通下注最高', '$10,000', '$50,000']])]),
           ('下注操作',
            '',
            [('筹码与金额', '先选择筹码，再左键点击下注圈增加金额；右键点击可将该项金额清零。'),
             ('锁定与重复下注', '发牌后不能修改本局下注。\n“重复下注”恢复上一局开局时的金额，并按当前模式调整限额。'),
             ('余额要求', '余额须足够支付所选普通下注及累进大奖费用。')],
            [])]),
         ('获胜条件 & 赔率',
          '标准赔率表示净赢倍数；中奖返还包括对应本金。',
          [('最低中奖条件',
            '',
            [('3张牌', '任意一对或更高牌型中奖。\n三张顺子、同花分别只需要3张牌。'),
             ('5张牌', '对子只有J、Q、K、A可中奖；10及以下的单对子不赔付。\n两对或更高牌型可中奖。'),
             ('7张牌', '从全部7张中取最佳5张，三条或更高牌型中奖。\n两对、单对子和高牌均不赔付。'),
             ('全输', '首三张、前五张、全部七张的最佳五张，都没有达到对应赔付门槛，才算全输中奖。\n与玩家实际下注哪些项目无关；其中任一阶段有可赔付牌型，全输即不中奖。')],
            [('标准赔率表',
              ['牌型', '3张牌', '5张牌', '7张牌'],
              [['皇家同花顺', '100:1', '1000:1', '500:1'],
               ['同花顺', '40:1', '250:1', '100:1'],
               ['四条', '—', '100:1', '50:1'],
               ['葫芦', '—', '50:1', '7:1'],
               ['同花', '4:1', '40:1', '5:1'],
               ['顺子', '5:1', '25:1', '4:1'],
               ['三条', '35:1', '7:1', '3:1'],
               ['两对', '—', '4:1', '—'],
               ['一对J/Q/K/A', '任意一对', '1:1', '—'],
               ['任意一对', '1:1', '—', '—']]),
             ('全输赔率', ['项目', '净赢赔率', '中奖返还'], [['全输', '0.7:1', '本金 × 1.7']])]),
           ('累进大奖',
            '固定使用发牌顺序中的指定5张牌。',
            [('固定取牌', '首三张＋第4张＋第7张组成大奖牌组，与7张牌的最佳五张分别评估。'),
             ('奖金计算', '第6、7张全部揭示后判奖。\n奖金直接发放，不另退$2.50参与费用。\n普通与高额模式使用相同奖金标准。')],
            [('累进大奖奖金表',
              ['指定五张牌的牌型', '奖金'],
              [['皇家同花顺', '当前奖池的100%'],
               ['同花顺', '当前奖池的10%'],
               ['四条', '$1,250'],
               ['葫芦', '$375'],
               ['同花', '$250'],
               ['顺子及以下', '不中奖']])])]),
         ('牌型等级表',
          '下列牌例仅代表一种组成方式。',
          [('三张牌的牌型',
            '三张牌中三条高于顺子，顺子高于同花。',
            [],
            [('三张牌从高到低',
              ['等级', '牌型', '牌例'],
              [['1', '皇家同花顺', ('__CARD_IMAGES__', (('♠', 'Q'), ('♠', 'K'), ('♠', 'A')))],
               ['2', '同花顺', ('__CARD_IMAGES__', (('♦', '5'), ('♦', '6'), ('♦', '7')))],
               ['3', '三条', ('__CARD_IMAGES__', (('♠', '8'), ('♥', '8'), ('♦', '8')))],
               ['4', '顺子', ('__CARD_IMAGES__', (('♠', '8'), ('♥', '9'), ('♦', '10')))],
               ['5', '同花', ('__CARD_IMAGES__', (('♠', '2'), ('♠', '7'), ('♠', 'J')))],
               ['6', '对子', ('__CARD_IMAGES__', (('♠', 'J'), ('♥', 'J'), ('♣', '2')))],
               ['7', '高牌', ('__CARD_IMAGES__', (('♠', '2'), ('♥', '7'), ('♦', 'Q')))]])]),
           ('五张牌的牌型',
            '用于评估前五张、七张的最佳五张以及累进大奖。',
            [],
            [('五张牌从高到低',
              ['等级', '牌型', '牌例'],
              [['1',
                '皇家同花顺',
                ('__CARD_IMAGES__', (('♦', '10'), ('♦', 'J'), ('♦', 'Q'), ('♦', 'K'), ('♦', 'A')))],
               ['2', '同花顺', ('__CARD_IMAGES__', (('♣', '4'), ('♣', '5'), ('♣', '6'), ('♣', '7'), ('♣', '8')))],
               ['3',
                '四条',
                ('__CARD_IMAGES__', (('♠', '10'), ('♥', '10'), ('♦', '10'), ('♣', '10'), ('♥', '3')))],
               ['4', '葫芦', ('__CARD_IMAGES__', (('♠', 'Q'), ('♥', 'Q'), ('♣', 'Q'), ('♦', '7'), ('♣', '7')))],
               ['5', '同花', ('__CARD_IMAGES__', (('♠', 'K'), ('♠', 'J'), ('♠', '8'), ('♠', '6'), ('♠', '2')))],
               ['6', '顺子', ('__CARD_IMAGES__', (('♥', '6'), ('♣', '7'), ('♦', '8'), ('♠', '9'), ('♥', '10')))],
               ['7', '三条', ('__CARD_IMAGES__', (('♠', '8'), ('♥', '8'), ('♦', '8'), ('♣', 'K'), ('♥', '4')))],
               ['8', '两对', ('__CARD_IMAGES__', (('♠', 'K'), ('♦', 'K'), ('♥', '6'), ('♣', '6'), ('♦', '9')))],
               ['9', '对子', ('__CARD_IMAGES__', (('♥', 'J'), ('♣', 'J'), ('♠', 'A'), ('♦', '8'), ('♣', '3')))],
               ['10',
                '高牌',
                ('__CARD_IMAGES__', (('♦', 'A'), ('♣', 'K'), ('♥', '10'), ('♠', '7'), ('♦', '4')))]])]),
           ('A与顺子的规则',
            '',
            [('三张牌', '同花色Q-K-A是三张皇家同花顺。\nA-2-3可组成最低三张顺子；K-A-2不算顺子。'),
             ('五张牌', '同花色10-J-Q-K-A是皇家同花顺。\nA-2-3-4-5可组成最低五张顺子；Q-K-A-2-3不算顺子。'),
             ('同级组合', '点数通常为A＞K＞Q＞J＞10＞…＞2；花色不分大小。\n选最佳五张时，同级牌型继续比较对子、三条等相关点数及剩余单牌。')],
            [])]),
         ('特别事项',
          '核对返还金额，并了解结算显示和自动重置。',
          [('结算显示',
            '',
            [('中奖的下注圈',
              '本金筹码留在原位，净赢筹码飞至左上方。\n普通下注圈下方只显示已揭示牌型，未揭示时留空。\n累进大奖灯下方始终留空。'),
             ('未中奖的下注圈', '未中奖筹码飞向结算点。\n前三个下注圈仍显示已揭示牌型；全输只有成立时显示“全输”，否则留空。\n任一阶段有可赔付牌型时，全输筹码即被收走。'),
             ('全输结果浮层',
              '三个阶段均无可赔付牌型时，七张牌结算后显示“全输：三个阶段均未达中奖条件”。'),
             ('自动重置', '普通结果结算后倒计时30秒，再自动收筹码并回到下注阶段。\n累进大奖中奖时保留结果，等玩家点击“再来一局”。\n右键查看牌序会暂停倒计时。'),
             ('牌序窗口', '结算后右键点击“再来一局”可查看本局牌序与切牌位置。')],
            []),
           ('返还与净盈亏',
            '',
            [('返还金额', '“本局下注”表示本局实际扣除的总金额。\n“上局返还”表示整局全部项目的返还总额，包含普通下注中奖时退还的本金。\n净盈亏＝返还总额－本局实际扣款。\n筹码在“再来一局”时飞回筹码区，随后计入余额。\n中途关闭会完成已锁定牌局的结算并保存余额。'),
             ('示例', '3张牌下注$100，开出顺子，赔率5:1，总返还$600。\n全输下注$100且中奖，总返还$170。\n累进大奖奖金按奖金表直接发放。'),
             ('理论返还率', '3张牌96.69%，5张牌95.21%，7张牌94.34%，全输96.29%。\n这是长期理论返还率，不是单局中奖概率；不包含本程序自定义累进大奖。')],
            [])])]

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

        instruction_title = f'{GAME_NAME} 游戏规则'
        dialog.title(instruction_title)

        dialog.configure(bg='#faf5e8')

        dialog.resizable(False, False)

        dialog.transient(parent)

        width, height = 1000, 670

        parent.update_idletasks()

        px, py = parent.winfo_rootx(), parent.winfo_rooty()

        pw, ph = max(1, parent.winfo_width()), max(1, parent.winfo_height())

        dialog.geometry(f'{width}x{height}+{px + (pw-width)//2}+{py + (ph-height)//2}')

        manual_pages = self._instruction_pages()

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

        tk.Label(header, text=instruction_title, font=(font_name, 20, 'bold'),

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

                                photo = ImageTk.PhotoImage(small_image, master=dialog)

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


# 兼容原启动器直接引用旧类名；实际界面和逻辑均为 Side Bet City。
CaribbeanStudGame = SideBetCityGame
CaribbeanStudGUI = SideBetCityGUI


def main(initial_balance=10000, username='Guest', *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """保持原启动器接口：支持嵌入父窗口或独立运行。"""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user
    if parent is not None:
        return SideBetCityGUI(parent, actual_balance, actual_user,
                              on_back=on_back, on_balance_change=on_balance_change)
    root = tk.Tk()
    root.title(f'{GAME_NAME}')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)
    page = SideBetCityGUI(root, actual_balance, actual_user)
    page.pack(fill=tk.BOTH, expand=True)
    page.on_back = lambda final_balance: root.destroy()
    root.protocol('WM_DELETE_WINDOW', page.on_close)
    root.mainloop()
    return page.balance


if __name__ == '__main__':
    final_balance = main()
    print(f'Final balance: {final_balance}')
