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
import subprocess
import sys
import time
from collections import Counter

# =========================================================
# 纵横交叉扑克 (Criss Cross Poker) - UTH Canvas UI
# =========================================================
ROOT_BG = "#1B3D31"
TEXT = "#ffffff"
GOLD = "#D4AF37"
PANEL_BG = "#F2E6C9"
HEADER_BG = "#D8B46A"
TITLE_FG = "#2A1B08"
RED = "#ff2a23"
BLACK = "#050505"
DARK_BLUE = "#173f66"

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {rank: value for value, rank in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    10: '皇家同花顺',
    9: '同花顺',
    8: '四条',
    7: '葫芦',
    6: '同花',
    5: '顺子',
    4: '三条',
    3: '两对',
    2: '对子J+',
    1: '对子10-',
    0: '高牌',
}

# 加注（横／纵／中）赔率。返回金额 = 本金 + 赔率利润。
MAIN_BET_PAYOUT = {
    10: 500,
    9: 100,
    8: 40,
    7: 12,
    6: 8,
    5: 5,
    4: 3,
    3: 2,
    2: 1,
}

# 五牌红利：只看五张公共牌，即使玩家弃牌仍独立结算。
FIVE_CARD_BONUS_PAYOUT = {
    10: 250,
    9: 100,
    8: 40,
    7: 15,
    6: 10,
    5: 6,
    4: 4,
    3: 3,
    2: 1,
    1: 1,
}

# =========================================================
# 用户余额文件
# =========================================================
def get_data_file_path():
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'A_Tools/Account/saving_data.json')


def save_user_data(users):
    with open(get_data_file_path(), 'w', encoding='utf-8') as file:
        json.dump(users, file, ensure_ascii=False, indent=4)


def load_user_data():
    path = get_data_file_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception:
        return []


def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user.get('user_name') == username:
            user['cash'] = f"{new_balance:.2f}"
            break
    save_user_data(users)


# =========================================================
# Progressive 文件（沿用原 Progressive_2.50 逻辑）
# =========================================================
def load_jackpot():
    path = str(_progressive_file)
    default_jackpot = 271288.59
    if not os.path.exists(path):
        return True, default_jackpot
    try:
        with open(path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        for item in data:
            if item.get('Games') == 'Progressive_2.50':
                return False, float(item.get('jackpot', default_jackpot))
    except Exception:
        pass
    return True, default_jackpot


def save_jackpot(jackpot):
    path = str(_progressive_file)
    data = []
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except Exception:
            data = []

    found = False
    for item in data:
        if item.get('Games') == 'Progressive_2.50':
            item['jackpot'] = jackpot
            found = True
            break
    if not found:
        data.append({'Games': 'Progressive_2.50', 'jackpot': jackpot})

    with open(path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


# =========================================================
# 历史记录
# =========================================================
def criss_cross_log_path():
    log_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'A_Logs',
        'Json',
    )
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, 'Criss_Cross_Poker.json')


def save_criss_cross_history(
    deck,
    community_cards,
    player_cards,
    total_return,
    horizontal_eval,
    vertical_eval,
    five_bonus_eval,
    folded,
    *,
    seat=None,
    round_id=None,
    bets=None,
):
    path = criss_cross_log_path()
    data = {'history_record': {'game': 0, 'win': 0, 'fold': 0, 'lose': 0}, 'history': []}
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as file:
                loaded = json.load(file)
            if isinstance(loaded, dict):
                data['history_record'].update(loaded.get('history_record', {}))
                data['history'] = loaded.get('history', [])
        except Exception as exc:
            print(f'读取 Criss Cross 历史记录失败: {exc}')

    stats = data['history_record']
    stats['game'] = int(stats.get('game', 0)) + 1
    if folded:
        stats['fold'] = int(stats.get('fold', 0)) + 1
    elif horizontal_eval[0] >= 2 or vertical_eval[0] >= 2:
        stats['win'] = int(stats.get('win', 0)) + 1
    else:
        stats['lose'] = int(stats.get('lose', 0)) + 1

    next_id = max(
        (record.get('game_id', 0) for record in data['history'] if isinstance(record, dict)),
        default=0,
    ) + 1
    data['history'].append({
        'game_id': next_id,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'deck_order': [str(card) for card in deck.full_deck],
        'cut_position': deck.cut_position,
        'community_cards': [str(card) for card in community_cards],
        'player_cards': [str(card) for card in player_cards],
        'horizontal_hand': HAND_RANK_NAMES.get(horizontal_eval[0], '高牌'),
        'vertical_hand': HAND_RANK_NAMES.get(vertical_eval[0], '高牌'),
        'five_card_bonus_hand': HAND_RANK_NAMES.get(five_bonus_eval[0], '高牌'),
        'total_return': total_return,
        'folded': folded,
        'seat': seat,
        'round_id': round_id,
        'bets': bets,
    })
    data['history'] = data['history'][-50:]

    with open(path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


# =========================================================
# 扑克牌与牌堆
# =========================================================
class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.value = RANK_VALUES[rank]

    def __repr__(self):
        return f'{self.rank}{self.suit}'


class Deck:
    def __init__(self):
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
        shuffle_script = os.path.join(card_dir, 'shuffle.py')
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        try:
            result = subprocess.run(
                [sys.executable, shuffle_script, 'false', '1'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                env=env,
                check=True,
                timeout=30,
            )
            shuffle_data = json.loads(result.stdout)
            if 'deck' not in shuffle_data or 'cut_position' not in shuffle_data:
                raise ValueError('Invalid shuffle data format')
            self.full_deck = [Card(item['suit'], item['rank']) for item in shuffle_data['deck']]
            self.cut_position = int(shuffle_data['cut_position'])
        except Exception as exc:
            print(f'Error calling shuffle.py: {exc}. Using fallback shuffle.')
            self.full_deck = [Card(suit, rank) for suit in SUITS for rank in RANKS]
            self._secure_shuffle()
            self.cut_position = secrets.randbelow(52)

        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + index) % 52 for index in range(52)]
        self.pointer = 0
        self.card_sequence = [self.full_deck[index] for index in self.indexes]

    def _secure_shuffle(self):
        for index in range(len(self.full_deck) - 1, 0, -1):
            other = secrets.randbelow(index + 1)
            self.full_deck[index], self.full_deck[other] = self.full_deck[other], self.full_deck[index]

    def deal(self, count=1):
        if self.pointer + count > len(self.indexes):
            raise RuntimeError('牌堆已没有足够的牌。')
        cards = [self.full_deck[self.indexes[self.pointer + offset]] for offset in range(count)]
        self.pointer += count
        return cards


# =========================================================
# 五张牌评估
# =========================================================
def evaluate_hand(cards):
    if len(cards) != 5:
        raise ValueError(f'evaluate_hand 需要正好 5 张牌，实际收到 {len(cards)} 张。')

    values = sorted((card.value for card in cards), reverse=True)
    counts = Counter(values)
    suits = [card.suit for card in cards]
    flush = len(set(suits)) == 1

    unique_values = sorted(set(values), reverse=True)
    if unique_values == [14, 5, 4, 3, 2]:
        straight_high = 5
    elif len(unique_values) == 5 and unique_values[0] - unique_values[4] == 4:
        straight_high = unique_values[0]
    else:
        straight_high = None

    if flush and straight_high:
        if straight_high == 14:
            return 10, [14, 13, 12, 11, 10]
        return 9, [straight_high]

    grouped = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    if grouped[0][1] == 4:
        quad = grouped[0][0]
        kicker = max(value for value in values if value != quad)
        return 8, [quad, kicker]

    triples = sorted((value for value, count in counts.items() if count == 3), reverse=True)
    pairs = sorted((value for value, count in counts.items() if count == 2), reverse=True)
    if triples and pairs:
        return 7, [triples[0], pairs[0]]

    if flush:
        return 6, values
    if straight_high:
        return 5, [straight_high]
    if triples:
        kickers = sorted((value for value in values if value != triples[0]), reverse=True)
        return 4, [triples[0]] + kickers
    if len(pairs) >= 2:
        kicker = max(value for value in values if value not in pairs[:2])
        return 3, [pairs[0], pairs[1], kicker]
    if len(pairs) == 1:
        pair = pairs[0]
        kickers = sorted((value for value in values if value != pair), reverse=True)
        if pair >= 11:
            return 2, [pair] + kickers
        # 所有 10 或以下对子统一显示为“对子10-”。
        # 主注仍不获胜；五牌红利是否赔付会另外检查对子点数是否至少为 6。
        return 1, [pair] + kickers
    return 0, values


def calculate_criss_cross_returns(
    *,
    ante_horizontal,
    ante_vertical,
    raise_horizontal,
    raise_vertical,
    raise_middle,
    five_card_bonus,
    horizontal_eval,
    vertical_eval,
    five_bonus_eval,
    folded,
):
    """纯规则函数：计算除 Progressive 以外的所有返还金额。"""
    details = {
        'ante_horizontal': 0.0,
        'ante_vertical': 0.0,
        'raise_horizontal': 0.0,
        'raise_vertical': 0.0,
        'raise_middle': 0.0,
        'five_card_bonus': 0.0,
    }

    if not folded:
        horizontal_rank = horizontal_eval[0]
        vertical_rank = vertical_eval[0]

        if horizontal_rank in MAIN_BET_PAYOUT:
            details['ante_horizontal'] = ante_horizontal * 2
            details['raise_horizontal'] = raise_horizontal * (1 + MAIN_BET_PAYOUT[horizontal_rank])

        if vertical_rank in MAIN_BET_PAYOUT:
            details['ante_vertical'] = ante_vertical * 2
            details['raise_vertical'] = raise_vertical * (1 + MAIN_BET_PAYOUT[vertical_rank])

        qualifying = [
            hand_eval
            for hand_eval in (horizontal_eval, vertical_eval)
            if hand_eval[0] in MAIN_BET_PAYOUT
        ]
        if qualifying:
            best_eval = max(qualifying)
            details['raise_middle'] = raise_middle * (1 + MAIN_BET_PAYOUT[best_eval[0]])

    five_bonus_rank = five_bonus_eval[0]
    if five_bonus_rank == 1:
        # “对子10-”只在对子点数为 6 至 10 时符合五牌红利 1:1。
        pair_value = five_bonus_eval[1][0] if five_bonus_eval[1] else 0
        if pair_value >= 6:
            details['five_card_bonus'] = five_card_bonus * (1 + FIVE_CARD_BONUS_PAYOUT[1])
    elif five_bonus_rank in FIVE_CARD_BONUS_PAYOUT:
        details['five_card_bonus'] = five_card_bonus * (1 + FIVE_CARD_BONUS_PAYOUT[five_bonus_rank])

    return sum(details.values()), details


# =========================================================
# 游戏状态
# =========================================================
class CrissCrossPokerGame:
    def __init__(self):
        self.progressive_amount = load_jackpot()[1]
        self.min_progressive = 271288.59
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.community_cards = []
        self.player_hole = []
        self.ante_horizontal = 0
        self.ante_vertical = 0
        self.five_card_bonus = 0
        self.raise_horizontal = 0
        self.raise_vertical = 0
        self.raise_middle = 0
        self.jackpot_bet = 0
        self.stage = 'pre_flop'
        self.folded = False
        self.cards_revealed = {
            'player': [False, False],
            'community': [False, False, False, False, False],
        }
        self.cut_position = self.deck.start_pos
        self.card_sequence = self.deck.card_sequence

    def deal_initial(self):
        # 按需求：先把 5 张公共牌派到 Middle，再派玩家 2 张牌。
        self.community_cards = self.deck.deal(5)
        self.player_hole = self.deck.deal(2)

    def horizontal_cards(self):
        return self.player_hole + [
            self.community_cards[0],
            self.community_cards[1],
            self.community_cards[4],
        ]

    def vertical_cards(self):
        return self.player_hole + [
            self.community_cards[2],
            self.community_cards[3],
            self.community_cards[4],
        ]

    def progressive_cards(self):
        # 公共牌按发牌順序编号，从 0 开始。
        return self.player_hole + [self.community_cards[i] for i in (0, 2, 4)]

    def evaluate_horizontal(self):
        return evaluate_hand(self.horizontal_cards())

    def evaluate_vertical(self):
        return evaluate_hand(self.vertical_cards())

    def evaluate_five_card_bonus(self):
        return evaluate_hand(self.community_cards)


# =========================================================
# GUI
# =========================================================

class CrissCrossPokerTableGame:
    """两家共用公共牌、牌堆、余额和奖池；每家的手牌与决定独立。"""
    SEATS = ('Player1', 'Player2')
    BET_KEYS = ('ante_horizontal', 'ante_vertical', 'five_card_bonus',
                'raise_horizontal', 'raise_vertical', 'raise_middle', 'jackpot')
    MIN_PROGRESSIVE = 271288.59
    PROGRESSIVE_PUBLIC_INDICES = (0, 2, 4)

    def __init__(self):
        self.progressive_amount = load_jackpot()[1]
        self.min_progressive = self.MIN_PROGRESSIVE
        self.reset_game()

    @classmethod
    def empty_bet(cls):
        return {kind: 0.0 for kind in cls.BET_KEYS}

    def reset_game(self):
        self.deck = None
        self.community_cards = []
        self.hands = {seat: [] for seat in self.SEATS}
        self.bets = {seat: self.empty_bet() for seat in self.SEATS}
        self.decisions = {seat: 'inactive' for seat in self.SEATS}
        self.cards_revealed = {'Public': [False] * 5, **{s: [False] * 2 for s in self.SEATS}}
        self.stage, self.street = 'betting', 'horizontal'
        self.deal_sequence = []
        self.settlement = None

    def start_round(self, bets, balance, high_bet_mode=False):
        if self.stage != 'betting':
            raise ValueError('本局尚未结束。')
        minimum, maximum, max_bonus = (100, 50000, 12500) if high_bet_mode else (10, 10000, 2500)
        prepared = {}
        for seat in self.SEATS:
            b = {k: float(bets[seat].get(k, 0)) for k in self.BET_KEYS}
            name = '玩家1' if seat == 'Player1' else '玩家2'
            if any(not math.isfinite(v) or v < 0 for v in b.values()):
                raise ValueError(f'{name}下注金额必须是有限的非负数。')
            if not any(b.values()):
                prepared[seat] = b
                continue
            if not minimum <= b['ante_horizontal'] <= maximum:
                raise ValueError(f'{name}每份前注须为 ${minimum:,} 至 ${maximum:,}。')
            if b['ante_horizontal'] != b['ante_vertical']:
                raise ValueError(f'{name}横、纵两份前注必须相等。')
            if b['five_card_bonus'] > max_bonus:
                raise ValueError(f'{name}五牌红利超出限额。')
            if b['jackpot'] not in (0, 2.5):
                raise ValueError(f'{name}累进大奖每局固定 $2.50。')
            if any(b[k] for k in ('raise_horizontal', 'raise_vertical', 'raise_middle')):
                raise ValueError('开牌前不能预下注横、纵、中加注。')
            prepared[seat] = b
        active = tuple(s for s in self.SEATS if prepared[s]['ante_horizontal'])
        if not active:
            raise ValueError('请至少为一家设置两份前注。')
        charged = round(sum(sum(b.values()) for b in prepared.values()), 2)
        if not math.isfinite(balance) or charged > balance:
            raise ValueError(f'余额不足！初始下注需要 ${charged:,.2f}。')
        deck = Deck()
        public = deck.deal(5)
        hands = {s: [] for s in self.SEATS}
        sequence = [('Public', i) for i in range(5)]
        for index in range(2):
            for seat in active:
                hands[seat].append(deck.deal(1)[0])
                sequence.append((seat, index))
        self.deck, self.community_cards, self.hands = deck, public, hands
        self.bets, self.deal_sequence = prepared, sequence
        self.decisions = {s: 'pending' if s in active else 'inactive' for s in self.SEATS}
        self.stage, self.street = 'dealing', 'horizontal'
        return charged

    def decide(self, seat, action, balance, multiplier=0):
        if self.stage != 'decision' or self.decisions.get(seat) != 'pending':
            raise ValueError('这家当前不能操作。')
        if action == 'fold':
            self.decisions[seat] = 'fold'
            return 0.0
        if action != 'raise' or multiplier not in (1, 2, 3):
            raise ValueError('每轮只允许加注 1X、2X、3X 或弃牌。')
        amount = round(self.bets[seat]['ante_horizontal'] * multiplier, 2)
        if amount > balance:
            raise ValueError('余额不足！')
        self.bets[seat]['raise_' + self.street] = amount
        self.decisions[seat] = 'raised'
        return amount

    def horizontal_cards(self, seat):
        return self.hands[seat] + [self.community_cards[i] for i in (0, 1, 4)]

    def vertical_cards(self, seat):
        return self.hands[seat] + [self.community_cards[i] for i in (2, 3, 4)]

    def progressive_cards(self, seat):
        # 公共牌按发牌顺序编号，从 0 开始。
        return self.hands[seat] + [self.community_cards[i] for i in self.PROGRESSIVE_PUBLIC_INDICES]

    def settle(self):
        if self.settlement is not None:
            return self.settlement
        if self.stage != 'showdown' or 'pending' in self.decisions.values():
            raise ValueError('两家须先完成决定。')
        five_eval = evaluate_hand(self.community_cards)
        outcomes, total_return, contribution = {}, 0.0, 0.0
        pool = self.progressive_amount
        for seat in self.SEATS:
            if self.decisions[seat] == 'inactive':
                continue
            b = self.bets[seat]
            horizontal_eval = evaluate_hand(self.horizontal_cards(seat))
            vertical_eval = evaluate_hand(self.vertical_cards(seat))
            returned, details = calculate_criss_cross_returns(
                **{k: b[k] for k in self.BET_KEYS if k != 'jackpot'},
                horizontal_eval=horizontal_eval, vertical_eval=vertical_eval,
                five_bonus_eval=five_eval, folded=self.decisions[seat] == 'fold')
            bonus = 0.0
            if b['jackpot']:
                rank, _ = evaluate_hand(self.progressive_cards(seat))
                bonus = max(pool, 10000.0) if rank == 10 else max(pool * .1, 1000.0) if rank == 9 else {8: 1250.0, 7: 375.0, 6: 250.0}.get(rank, 0.0)
                bonus = round(bonus, 2)
                pool -= bonus
            details['bonus'] = bonus
            returned = round(returned + bonus, 2)
            outcomes[seat] = dict(details=details, returned=returned,
                horizontal_eval=horizontal_eval, vertical_eval=vertical_eval,
                five_bonus_eval=five_eval, folded=self.decisions[seat] == 'fold')
            total_return += returned
            contribution += sum(b[k] for k in self.BET_KEYS if k != 'jackpot') * .001 + b['jackpot'] * .95
        self.progressive_amount = round(max(self.MIN_PROGRESSIVE, pool) + contribution, 2)
        self.settlement = dict(hands=outcomes, returned=round(total_return, 2))
        return self.settlement

class CrissCrossPokerGUI(tk.Frame):

    """UTH Canvas 牌桌界面，接入两家独立操作的 Criss Cross Poker 规则。"""

    WIDTH, HEIGHT = 1150, 750

    CARD_WIDTH, CARD_HEIGHT = 80, 112

    DEAL_CARD_MS = 224 / .85

    DEAL_MOVE_MS = (128 / .75) / .85

    BET_CHIP_RADIUS = 16 * 4 / 3

    HOUSE_CHIP_POS = (575, 43)

    TABLE_GREEN = '#4b1e22'

    PROGRESSIVE_LAMP_WIDTH = 122.0 * .8

    SEATS = CrissCrossPokerTableGame.SEATS

    ZONE_COLORS = {'Player1': '#2A5541', 'Player2': '#204536'}

    SEAT_NAMES = {'Player1': '玩家1', 'Player2': '玩家2'}

    BET_KEYS = ('ante_horizontal', 'ante_vertical', 'five_card_bonus',
                'raise_horizontal', 'raise_vertical', 'raise_middle', 'jackpot')

    CROSS_POSITIONS = {0: (443, 128), 1: (627, 128), 2: (535, 8),
                       3: (535, 248), 4: (535, 128)}

    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = username, float(initial_balance)
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game = CrissCrossPokerTableGame()
        self.game.stage = 'betting'
        self.bets = {s: self._empty_bet() for s in self.SEATS}
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
        self._motion_count = 0
        self._chip_serial = 0
        self._decision_busy = False
        self._settlement_started = False
        self.visual_chips, self.lamps = {}, {}
        self.last_round_snapshot = None
        self._history_available = False
        self._face_photos, self._pil_cards, self._flip_photos = {}, {}, {}
        self.card_items, self.bet_spots, self.action_buttons = {}, {}, {}
        self._card_origins = {}
        self._faded_photos = {}
        self._load_assets()
        self._create_widgets()
        self._refresh()
        self.bind('<Configure>', self._center_table, add='+')
        self.bind('<Destroy>', self._on_destroy, add='+')

    @staticmethod
    def _empty_bet():
        return {kind: 0.0 for kind in CrissCrossPokerGUI.BET_KEYS}

    @property
    def game_in_progress(self):
        return self.game.stage != 'betting' or self._motion_count > 0

    def card_size(self, side):
        return self.CARD_WIDTH, self.CARD_HEIGHT

    @staticmethod
    def _card_image_key(card):
        return card.suit, card.rank

    def card_position(self, side, index):
        if side == 'Public':
            return self.CROSS_POSITIONS[index]
        return (40 if side == 'Player1' else 600) + index * 92, 402

    def _create_widgets(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=ROOT_BG, highlightthickness=0)
        self.canvas.place(x=0, y=0, width=self.WIDTH, height=self.HEIGHT)
        self.control_buttons = {}
        c = self.canvas
        self._text(187, 44, '纵横交叉扑克', 16, GOLD)
        self._draw_limit_table()
        self._text(957, 44, 'Criss Cross Poker', 14, GOLD)
        self._draw_progressive_panel()
        c.create_rectangle(22, 191, 1128, 309, fill=ROOT_BG, outline='#65784B')
        c.create_line(25, 192, 1125, 192, fill='#E0C879', width=2)
        c.create_line(25, 308, 1125, 308, fill='#0C241B', width=2)
        self._text(219, 208, '获胜条件', 11, '#D8C796')
        self._text(219, 239, '横、纵：J 对子或以上\n中：取较高的及格牌型', 14, GOLD,
                   justify=tk.CENTER)
        self._text(931, 208, '操作顺序', 11, '#D8C796')
        self._text(931, 239, '横 → 纵 → 中\n1X / 2X / 3X 或弃牌', 14, GOLD,
                   justify=tk.CENTER)
        for left, right in ((60, 378), (772, 1090)):
            c.create_line(left, 265, right, 265, fill='#42604A')
        self.street_item = self._text(219, 282, '下注阶段', 13, PANEL_BG)
        self._text(931, 282, '各家决定后翻牌', 12, PANEL_BG)
        # 用统一深绿牌区和独立牌位替代大块米色十字底板。
        self._rounded_panel(416, 2, 734, 365, 14, '#234838', '#667B55', 'public_panel')
        self._text(470, 32, '公共牌', 11, '#D8C796', tags='public_panel')
        self.title_items, self.hand_summary_items, self.ante_equal_items = {}, {}, {}
        for seat, x0, x1 in (('Player1', 22, 566), ('Player2', 582, 1128)):
            c.create_rectangle(x0, 366, x1, 623, fill=self.ZONE_COLORS[seat], outline='')
            self.title_items[seat] = self._text(x0 + 110, 378, self.SEAT_NAMES[seat], 15, PANEL_BG)
            summary_left = 42 if seat == 'Player1' else 754
            self.hand_summary_items[seat] = self._draw_hand_summary_table(seat, summary_left, 315)
            # 金字塔三行共用中心轴，横、纵前注以及三枚加注均左右对称。
            center_x = x0 + 296
            self._draw_bonus_diamond(seat, center_x, 414)
            self._draw_bet_spot(seat, 'ante_horizontal', center_x - 48, 487, '前注\n横', '#B8303B')
            self._draw_bet_spot(seat, 'ante_vertical', center_x + 48, 487, '前注\n纵', '#B8303B')
            self.ante_equal_items[seat] = self._text(center_x, 487, '＝', 21, PANEL_BG)
            self._draw_bet_spot(seat, 'raise_horizontal', center_x - 78, 576, '加注\n横', '#153EAA')
            self._draw_bet_spot(seat, 'raise_middle', center_x, 576, '加注\n中', '#153EAA')
            self._draw_bet_spot(seat, 'raise_vertical', center_x + 78, 576, '加注\n纵', '#153EAA')
            self._draw_progressive_lamp(seat, x0 + 107, 567)
            for action, top, caption, color in (
                    (3, 376, '下注3X', '#2B6639'), (2, 438, '下注2X', '#397A48'),
                    (1, 500, '下注1X', '#488955'), ('fold', 562, '弃牌', '#9B403A')):
                command = (lambda s=seat: self.fold_game(s)) if action == 'fold' else (
                    lambda s=seat, m=action: self.place_cross_bet(m, s))
                self.action_buttons[(seat, action)] = self.create_control_button(
                    x0 + 430, top, x1 - 15, top + 50, caption, command, color,
                    font_size=13, draw_shadow=False)
        self._draw_bottom_controls()
        for side in self.SEATS:
            for index in range(2):
                x, y = self.card_position(side, index)
                w, h = self.card_size(side)
                c.create_rectangle(x, y, x + w, y + h, outline='#B59C6A',
                                   dash=(3, 3), tags='card_slots')
        for index, (x, y) in self.CROSS_POSITIONS.items():
            w, h = self.card_size('Public')
            c.create_rectangle(x - 3, y - 3, x + w + 3, y + h + 3,
                               fill='#193A2D', outline='#78916A',
                               width=1, dash=(4, 3), tags='cross_slots')
            self._text(x + w/2, y + h/2, {0: '横', 1: '横', 2: '纵', 3: '纵', 4: '中'}[index],
                       12, '#B4BE98', tags='cross_slots')

    def _draw_bet_spot(self, seat, kind, cx, cy, label, fill):
        tag = 'spot_' + seat + '_' + kind
        border = self.canvas.create_oval(cx - 34, cy - 34, cx + 34, cy + 34,
                    fill=fill, outline=PANEL_BG, width=2, tags=tag)
        self._register_spot(seat, kind, cx, cy, border, label)
        for item in self.canvas.find_withtag(tag):
            if self.canvas.type(item) == 'text':
                self.canvas.itemconfigure(item, font=('Arial', 12, 'bold'),
                                          justify=tk.CENTER, anchor=tk.CENTER)

    def _refresh(self):
        c = self.canvas
        c.itemconfigure(self.balance_item, text=f'余额: ${self.balance:,.2f}')
        total = round(sum(sum(b.values()) for b in self.bets.values()), 2)
        c.itemconfigure(self.total_item, text=f'本局下注: ${total:,.2f}' if total else f'上局返还: ${self.last_win:,.2f}')
        limits = ('$100', '$50,000', '$12,500') if self.high_bet_mode else ('$10', '$10,000', '$2,500')
        for item, value in zip(self.limit_value_items, limits):
            c.itemconfigure(item, text=value)
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
        for (seat, action), tag in self.action_buttons.items():
            ready = (self.game.stage == 'decision' and not self._decision_busy and not self._motion_count
                     and self.game.decisions[seat] == 'pending')
            affordable = action == 'fold' or self.balance >= self.game.bets[seat]['ante_horizontal'] * action
            self.set_control_button_state(tag, ready and affordable)
        street = {'horizontal': '横', 'vertical': '纵', 'middle': '中'}[self.game.street]
        caption = f'{street}加注 · 1X / 2X / 3X' if self.game.stage == 'decision' else {
            'betting': '下注阶段', 'progressive': '累进大奖确认', 'dealing': '发牌中',
            'revealing': '公共牌开牌中', 'showdown': '开牌中', 'settling': '结算中',
            'await_restart': '已结算', 'returning': '筹码回收中',
            'credit_pending': '返还入账', 'sweeping': '准备下一局',
        }.get(self.game.stage, self.game.stage)
        c.itemconfigure(self.street_item, text=caption)
        self._update_current_hand_summaries()
        self._status(caption)

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
        self.last_bet = None
        self.selected_chip = 100 if self.high_bet_mode else 10
        self._draw_chips()
        self.reset_bets()
        self._refresh()

    def reset_bets(self):
        if not self.game_in_progress:
            self._apply_bet_layout({s: self._empty_bet() for s in self.SEATS})

    def apply_last_bet(self):
        if not self.game_in_progress and self.last_bet:
            self._apply_bet_layout(self.last_bet)

    def add_chip_to_bet(self, seat='Player1', kind=None):
        if kind is None:
            kind, seat = seat, 'Player1'
        if self.game_in_progress:
            return
        new = {s: dict(b) for s, b in self.bets.items()}
        b = new[seat]
        if kind == 'ante':
            kind = 'ante_horizontal'
        if kind == 'jackpot':
            b[kind] = 0.0 if b[kind] else 2.5
        elif kind in ('ante_horizontal', 'ante_vertical'):
            limit = 50000 if self.high_bet_mode else 10000
            b['ante_horizontal'] = b['ante_vertical'] = min(limit, b[kind] + self.selected_chip)
        elif kind == 'five_card_bonus':
            limit = 12500 if self.high_bet_mode else 2500
            b[kind] = min(limit, b[kind] + self.selected_chip)
        else:
            return
        self._apply_bet_layout(new)

    def reset_single_bet(self, seat='Player1', kind=None):
        if kind is None:
            kind, seat = seat, 'Player1'
        if self.game_in_progress:
            return
        new = {s: dict(b) for s, b in self.bets.items()}
        if kind in ('ante', 'ante_horizontal', 'ante_vertical'):
            new[seat]['ante_horizontal'] = new[seat]['ante_vertical'] = 0.0
        elif kind in ('five_card_bonus', 'jackpot'):
            new[seat][kind] = 0.0
        else:
            return
        self._apply_bet_layout(new)

    def start_game(self):
        if self.game_in_progress:
            return
        try:
            charged = self.game.start_round(self.bets, self.balance, self.high_bet_mode)
        except (ValueError, RuntimeError) as exc:
            messagebox.showwarning('无法开始', str(exc), parent=self)
            return
        self.balance = round(self.balance - charged, 2)
        self.bets = {s: dict(b) for s, b in self.game.bets.items()}
        self.last_bet = {s: dict(b) for s, b in self.bets.items()}
        self._credited = self._return_persisted = self._settlement_started = False
        self._decision_busy = False
        self._history_available = False
        self._cancel_restart_timer()
        self._close_card_sequence()
        self.canvas.delete('cards')
        self.card_items.clear()
        self._card_origins.clear()
        self._flip_photos.clear()
        self._faded_photos.clear()
        self._load_assets()
        self._reset_titles()
        self._persist_balance()
        self.game.stage = 'progressive'
        self._refresh()
        pending = {s for s in self.SEATS if self.bets[s]['jackpot']}
        def filled(seat):
            pending.discard(seat)
            if not pending:
                self._collect_progressive_and_deal()
        for seat in self.SEATS:
            if seat in pending:
                self.lamps[seat]['filled_callback'] = lambda s=seat: filled(s)
                self._set_lamp_mode(seat, 'fill')
            else:
                self._set_lamp_mode(seat, 'off')
        if not pending:
            self._schedule(0, self._collect_progressive_and_deal)

    def _collect_progressive_and_deal(self):
        if self.game.stage != 'progressive':
            return
        self.game.stage = 'dealing'
        transfers = []
        for seat in self.SEATS:
            chip = self.visual_chips.pop((seat, 'jackpot', 'stake'), None)
            if chip:
                transfers.append(dict(amount=chip['amount'], start=chip['xy'],
                                      target=self.HOUSE_CHIP_POS, duration=280))
        self._refresh()
        self._run_chip_batch(transfers, lambda: self._deal_next(self.game.deal_sequence, 0))

    def _deal_next(self, sequence, offset):
        if offset == len(sequence):
            self._reveal_next([(s, i) for s in self.SEATS if self.game.hands[s] for i in range(2)], 0, self._after_initial_reveal)
            return
        side, index = sequence[offset]
        x, y = self.card_position(side, index)
        self._card_origins[(side, index)] = (x, y)
        photos = self._public_photos if side == 'Public' else self._face_photos
        item = self.canvas.create_image(575, 52, image=photos['back'], anchor='nw', tags='cards')
        self.card_items[(side, index)] = item
        def move(step=0):
            p = step / 6
            self.canvas.coords(item, 575 + (x - 575) * p, 52 + (y - 52) * p)
            if step < 6:
                self._schedule(round(self.DEAL_MOVE_MS * (step + 1) / 6) - round(self.DEAL_MOVE_MS * step / 6), move, step + 1)
            else:
                self._schedule(round(self.DEAL_CARD_MS) - round(self.DEAL_MOVE_MS), self._deal_next, sequence, offset + 1)
        move()

    def _reveal_next(self, sequence, offset, complete):
        if offset == len(sequence):
            complete()
            return
        side, index = sequence[offset]
        cards = self.game.community_cards if side == 'Public' else self.game.hands[side]
        revealed = self.game.cards_revealed[side]
        if revealed[index]:
            self._reveal_next(sequence, offset + 1, complete)
            return
        card, item = cards[index], self.card_items[(side, index)]
        x, y = self.card_position(side, index)
        w, h = self.card_size(side)
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
                photos = self._public_photos if side == 'Public' else self._face_photos
                self.canvas.itemconfigure(item, image=photos[self._card_image_key(card)])
                self.canvas.coords(item, x, y)
                self._flip_photos.pop(item, None)
                revealed[index] = True
                self._update_current_hand_summaries()
                self._reveal_next(sequence, offset + 1, complete)
        flip()

    def _after_initial_reveal(self):
        self._decision_busy = False
        self.game.stage = 'decision'
        self._refresh()

    def place_cross_bet(self, multiplier, seat='Player1'):
        self._decide(seat, 'raise', multiplier)

    def move_and_reveal(self, indices, target_map, callback):
        # 公共牌已经发到最终位置；后续每轮只在原位翻牌。
        sequence = [('Public', i) for i in indices if not self.game.cards_revealed['Public'][i]]
        self._reveal_next(sequence, 0, callback)

    def fold_game(self, seat='Player1'):
        self._decide(seat, 'fold')

    def show_showdown(self):
        if self._settlement_started or self.game.stage != 'showdown':
            return
        self._settlement_started = True
        pool_before = self.game.progressive_amount
        result = self.game.settle()
        self.game.stage = 'settling'
        self.last_win = result['returned']
        try:
            save_jackpot(self.game.progressive_amount)
        except Exception as exc:
            messagebox.showerror('奖池保存失败', str(exc), parent=self)
        self._render_hand_usage()
        transfers, awards = [], []
        round_id = time.time_ns()
        for seat, outcome in result['hands'].items():
            details = outcome['details']
            self.canvas.itemconfigure(self.title_items[seat], text=self.SEAT_NAMES[seat])
            for kind in self.BET_KEYS:
                if kind != 'jackpot':
                    transfers.extend(self._outcome_transfers(seat, kind, self.bets[seat][kind], details[kind]))
            if details['bonus']:
                self._set_lamp_mode(seat, 'win')
                awards.append((seat, details['bonus']))
            try:
                save_criss_cross_history(self.game.deck, self.game.community_cards, self.game.hands[seat],
                    outcome['returned'], outcome['horizontal_eval'], outcome['vertical_eval'],
                    outcome['five_bonus_eval'], outcome['folded'], seat=seat, round_id=round_id,
                    bets=dict(self.bets[seat]))
            except Exception as exc:
                messagebox.showerror('历史记录保存失败', str(exc), parent=self)
        self._refresh()
        self._run_chip_batch(transfers, lambda: self._pay_progressive_awards(awards, pool_before))

    def _render_hand_usage(self):
        self._faded_photos.clear()
        for seat in self.SEATS:
            if self.game.decisions[seat] == 'fold':
                for index, card in enumerate(self.game.hands[seat]):
                    self._fade_card_item(self.card_items[(seat, index)], self._pil_cards[self._card_image_key(card)])

    def _sweep_all_cards(self):
        if not self.card_items:
            self._finish_round()
            return
        self._motion_count += 1
        distance = self.WIDTH + self.CARD_WIDTH
        previous = [0.0]
        def frame(index=0):
            fraction = index / 13
            offset = distance * fraction * fraction * (3 - 2 * fraction)
            self.canvas.move('cards', offset - previous[0], 0)
            previous[0] = offset
            if index < 13:
                self._schedule(round(200 * (index + 1) / 13) - round(200 * index / 13), frame, index + 1)
            else:
                self.canvas.delete('cards')
                self.card_items.clear()
                self._flip_photos.clear()
                self._motion_count -= 1
                self._finish_round()
        frame()

    def _reset_titles(self):
        for seat in self.SEATS:
            self.canvas.itemconfigure(self.title_items[seat], text=self.SEAT_NAMES[seat])
            for key, item in self.hand_summary_items[seat].items():
                self.canvas.itemconfigure(item, text='待发牌' if key == 'status' else '—')

    def _finish_round(self):
        if self.game.stage != 'sweeping':
            return
        for seat in self.SEATS:
            self._set_lamp_mode(seat, 'off')
        self.game.reset_game()
        self.bets = {s: self._empty_bet() for s in self.SEATS}
        self._card_origins.clear()
        self._faded_photos.clear()
        self._history_available = False
        self._decision_busy = False
        self._reset_titles()
        self._refresh()

    def reset_game(self, auto_reset=False):
        if self.game.stage in ('await_restart', 'credit_pending'):
            self._return_all_chips()
        elif self.game.stage == 'betting':
            self.reset_bets()

    def _rounded_panel(self, x0, y0, x1, y1, radius, fill, outline, tag):
        points = (x0+radius, y0, x1-radius, y0, x1, y0, x1, y0+radius,
                  x1, y1-radius, x1, y1, x1-radius, y1, x0+radius, y1,
                  x0, y1, x0, y1-radius, x0, y0+radius, x0, y0)
        return self.canvas.create_polygon(*points, smooth=True, splinesteps=16,
                    fill=fill, outline=outline, width=1, tags=tag)

    def _draw_hand_summary_table(self, seat, x, y):
        c = self.canvas
        tag = 'hand_summary_' + seat
        boundaries = (x, x + 90, x + 222, x + 354)
        c.create_rectangle(x, y, x + 354, y + 44,
                           fill=ROOT_BG, outline='#78916A', tags=tag)
        c.create_rectangle(x + 1, y + 1, x + 353, y + 20,
                           fill='#2A5541', outline='', tags=tag)
        c.create_line(x, y + 20, x + 354, y + 20, fill='#78916A', tags=tag)
        for divider in boundaries[1:-1]:
            c.create_line(divider, y, divider, y + 44, fill='#78916A', tags=tag)
        centers = [(left + right) / 2 for left, right in zip(boundaries, boundaries[1:])]
        for cx, caption in zip(centers, (self.SEAT_NAMES[seat], '横向牌型', '纵向牌型')):
            self._text(cx, y + 10, caption, 11, PANEL_BG, tags=tag)
        return {key: self._text(cx, y + 32, text, 12, GOLD, tags=tag)
                for key, cx, text in zip(('status', 'horizontal', 'vertical'),
                                         centers, ('待发牌', '—', '—'))}

    def _draw_bonus_diamond(self, seat, cx, cy):
        tag = 'spot_' + seat + '_five_card_bonus'
        # 原菱形对角线 56，放大 50% 后为 84；字体同步由 10 放大到 15。
        border = self.canvas.create_polygon(cx, cy-42, cx+42, cy, cx, cy+42, cx-42, cy,
                    fill='#FCF7E8', outline='#B8303B', width=3, tags=tag)
        self._register_spot(seat, 'five_card_bonus', cx, cy, border, '五牌\n红利')
        for item in self.canvas.find_withtag(tag):
            if self.canvas.type(item) == 'text':
                self.canvas.itemconfigure(item, fill='#2A1B08', font=('Arial', 15, 'bold'))

    @staticmethod
    def _visible_hand_name(cards):
        """只有五张可见牌才判顺子/同花；不足五张时按已形成的对子等显示。"""
        if len(cards) == 5:
            return HAND_RANK_NAMES[evaluate_hand(cards)[0]]
        counts = Counter(card.value for card in cards)
        groups = sorted(counts.values(), reverse=True)
        if groups and groups[0] == 4:
            rank = 8
        elif groups and groups[0] == 3:
            rank = 4
        elif groups.count(2) == 2:
            rank = 3
        elif 2 in groups:
            pair_value = next(value for value, count in counts.items() if count == 2)
            rank = 2 if pair_value >= 11 else 1
        else:
            rank = 0
        return HAND_RANK_NAMES[rank]

    def _update_current_hand_summaries(self):
        visible = self.game.cards_revealed['Public']
        for seat in self.SEATS:
            hand = self.game.hands[seat]
            horizontal_name = vertical_name = '—'
            if not hand:
                status = '待发牌' if self.game.stage == 'betting' else '未下注'
            elif not all(self.game.cards_revealed[seat]):
                status = '翻牌中'
            else:
                horizontal = hand + [self.game.community_cards[i] for i in (0, 1, 4) if visible[i]]
                vertical = hand + [self.game.community_cards[i] for i in (2, 3, 4) if visible[i]]
                status = {'fold': '弃牌', 'raised': '已加注'}.get(self.game.decisions[seat], '当前')
                horizontal_name = self._visible_hand_name(horizontal)
                vertical_name = self._visible_hand_name(vertical)
            for key, text in (('status', status), ('horizontal', horizontal_name), ('vertical', vertical_name)):
                self.canvas.itemconfigure(self.hand_summary_items[seat][key], text=text)

    def _decide(self, seat, action, multiplier=0):
        if self.game.stage != 'decision' or self._decision_busy or self._motion_count or self.game.decisions.get(seat) != 'pending':
            return
        try:
            amount = self.game.decide(seat, action, self.balance, multiplier)
        except ValueError as exc:
            messagebox.showwarning('无法操作', str(exc), parent=self)
            return
        self._decision_busy = True
        self.balance = round(self.balance - amount, 2)
        self.bets[seat] = dict(self.game.bets[seat])
        self._persist_balance()
        self._update_decision_titles()
        self._refresh()
        def done():
            self._decision_busy = False
            self._refresh()
            self._advance_round()
        if action == 'raise':
            kind = 'raise_' + self.game.street
            def arrived():
                self._set_visual(seat, kind, 'stake', amount)
                done()
            self._animate_chip(amount, self._rack_position(), self.bet_spots[(seat, kind)]['center'], arrived)
        else:
            transfers = []
            for kind in ('ante_horizontal', 'ante_vertical', 'raise_horizontal', 'raise_vertical', 'raise_middle'):
                chip = self.visual_chips.pop((seat, kind, 'stake'), None)
                if chip:
                    transfers.append(dict(amount=chip['amount'], start=chip['xy'],
                                          target=self.HOUSE_CHIP_POS, duration=280))
            self._run_chip_batch(transfers, done)

    def _advance_round(self):
        if self._decision_busy or self.game.stage != 'decision' or 'pending' in self.game.decisions.values():
            return
        continuing = any(d == 'raised' for d in self.game.decisions.values())
        street = self.game.street
        if not continuing or street == 'middle':
            self.game.stage = 'showdown'
            indices = [i for i in (0, 1, 2, 3, 4) if not self.game.cards_revealed['Public'][i]]
            self._refresh()
            self.move_and_reveal(indices, self.CROSS_POSITIONS, self.show_showdown)
            return
        self.game.stage = 'revealing'
        indices = [0, 1] if street == 'horizontal' else [2, 3]
        def revealed():
            self.game.street = 'vertical' if street == 'horizontal' else 'middle'
            self.game.decisions = {s: 'pending' if d == 'raised' else d for s, d in self.game.decisions.items()}
            self.game.stage = 'decision'
            self._update_decision_titles()
            self._refresh()
        self._refresh()
        self.move_and_reveal(indices, self.CROSS_POSITIONS, revealed)

    def _update_decision_titles(self):
        for seat in self.SEATS:
            self.canvas.itemconfigure(self.title_items[seat], text=self.SEAT_NAMES[seat])

    def _instruction_pages(self):
        """简明规则；多步说明使用换行，不重复展示相同结算规则。"""
        progressive_indices = '、'.join(map(str, self.game.PROGRESSIVE_PUBLIC_INDICES))
        examples = (
            ('皇家同花顺', (('♠', 'A'), ('♠', 'K'), ('♠', 'Q'), ('♠', 'J'), ('♠', '10'))),
            ('同花顺', (('♥', '9'), ('♥', '8'), ('♥', '7'), ('♥', '6'), ('♥', '5'))),
            ('四条', (('♠', '9'), ('♥', '9'), ('♦', '9'), ('♣', '9'), ('♠', '2'))),
            ('葫芦', (('♠', 'K'), ('♥', 'K'), ('♦', 'K'), ('♣', '5'), ('♦', '5'))),
            ('同花', (('♥', 'A'), ('♥', '10'), ('♥', '8'), ('♥', '5'), ('♥', '2'))),
            ('顺子', (('♠', '9'), ('♥', '8'), ('♦', '7'), ('♣', '6'), ('♠', '5'))),
            ('三条', (('♠', 'Q'), ('♥', 'Q'), ('♦', 'Q'), ('♣', '8'), ('♦', '2'))),
            ('两对', (('♠', 'J'), ('♥', 'J'), ('♦', '4'), ('♣', '4'), ('♠', 'A'))),
            ('对子', (('♠', 'A'), ('♥', 'A'), ('♦', '10'), ('♣', '7'), ('♠', '2'))),
            ('高牌', (('♠', 'A'), ('♥', 'K'), ('♦', '9'), ('♣', '6'), ('♠', '3'))),
        )
        return [
            ('玩法与操作', '', [
                ['操作', '', [
                    ('下注', '选择筹码，左键增加，右键清除。\n'
                             '同一家横、纵前注相等；可只下注一家。\n'
                             '五牌红利可选；累进大奖每家 $2.50。'),
                    ('开牌', '先发5张公共牌至十字牌位。\n'
                             '再为已下注玩家各发2张手牌并翻开。'),
                    ('决定', '横 → 纵 → 中，每轮选 1X / 2X / 3X 或弃牌。\n'
                             '各家决定后，依次翻开横、纵、中心公共牌。'),
                    ('下一局', '点击「再来一局」或 Enter 回收筹码并入账。\n'
                               '普通牌局30秒后自动回收；大奖获奖后手动回收。\n'
                               '右键「再来一局」查看牌序。'),
                ], []],
                ['下注限额', '', [], [('', ['项目', '普通', '高额'], [
                    ['每份前注', '$10–$10,000', '$100–$50,000'],
                    ['五牌红利', '最高 $2,500', '最高 $12,500'],
                    ['累进大奖', '$2.50 / 家', '$2.50 / 家'],
                ])]],
            ]),
            ('取牌与赔率', '', [
                ['取牌', '', [], [('', ['项目', '五张牌组合'], [
                    ['横牌组', '2张手牌 + 公共牌0、1、4'],
                    ['纵牌组', '2张手牌 + 公共牌2、3、4'],
                    ['五牌红利', '全部5张公共牌'],
                    ['累进大奖', f'2张手牌 + 公共牌{progressive_indices}\n按发牌顺序编号，从0开始。'],
                ])]],
                ['结算', '', [
                    ('前注', '横、纵分别需 J 对子或以上，赢 1:1。'),
                    ('加注', '横、纵按各自牌型；中取较高的及格牌型。\n'
                             '未达门槛或弃牌，相关前注与加注输。'),
                    ('边注', '五牌红利与累进大奖独立结算，弃牌后仍有效。'),
                    ('赔率', '下表列净赢；前注、加注和五牌红利获胜另退本金。\n'
                             '累进大奖按表列金额派奖，不另退 $2.50。'),
                ], []],
                ['赔率表', '', [], [('', ['牌型', '加注', '五牌红利', '累进大奖'], [
                    ['皇家同花顺', '500:1', '250:1', '100%奖池\n最低$10,000'],
                    ['同花顺', '100:1', '100:1', '10%奖池\n最低$1,000'],
                    ['四条', '40:1', '40:1', '$1,250'],
                    ['葫芦', '12:1', '15:1', '$375'],
                    ['同花', '8:1', '10:1', '$250'],
                    ['顺子', '5:1', '6:1', '—'],
                    ['三条', '3:1', '4:1', '—'],
                    ['两对', '2:1', '3:1', '—'],
                    ['J或以上对子', '1:1', '1:1', '—'],
                    ['6–10对子', '输', '1:1', '—'],
                    ['其他', '输', '输', '—'],
                ])]],
            ]),
            ('牌型', '', [
                ['牌型由强至弱', '', [], [('', ['等级', '牌型', '牌例'],
                    [[str(index), name, ('__CARD_IMAGES__', cards)]
                     for index, (name, cards) in enumerate(examples, 1)])]],
            ]),
        ]

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

    def select_chip(self, amount):
        if self.game.stage == 'betting':
            self.selected_chip = amount
            self._draw_chips()

    def _status(self, message):
        # 记录阶段供调试，不在筹码下方绘制说明文字。
        self.current_status=message

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

    def on_close(self):
        if self._closing or self._crediting:return
        settled=self.game.stage in ('settling','await_restart','returning','credit_pending','sweeping')
        if self.game_in_progress and not settled:
            messagebox.showinfo('牌局进行中','请先完成已下注手牌的决定和结算。',parent=self)
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
        # 沿用 UTH 的标题 + 三列限红表，改成深绿/金色。
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
        self.canvas.create_window(954,130,window=panel,width=322,height=118)
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
        if abs(value)>=1000:return CrissCrossPokerGUI._compact(value)
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
        for seat in self.SEATS:
            for kind in self._empty_bet():
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
        """本金留位，盈利派至本金附近；输注立即飞向统一庄家收筹码点，平局不动。"""
        if not stake:return []
        key=(seat,kind,'stake');center=self.bet_spots[(seat,kind)]['center']
        if returned<=0:
            chip=self.visual_chips.pop(key,None)
            return [dict(amount=chip['amount'],start=chip['xy'],target=self.HOUSE_CHIP_POS,duration=280)] if chip else []
        profit=round(returned-stake,2)
        if profit<=0:return []
        target=(center[0]+32,center[1]-30) if kind in ('five_card_bonus','ante_vertical') else (center[0]-32,center[1]-30)
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

    def _fade_card_item(self, item, source):
        # 用alpha淡化，不破坏牌面原图，也不把透明PNG的边缘铺成白底。
        faded = source.convert('RGBA').copy()
        faded.putalpha(faded.getchannel('A').point(lambda value:round(value*.45)))
        photo = ImageTk.PhotoImage(faded,master=self)
        self._faded_photos[item] = photo
        self.canvas.itemconfigure(item,image=photo)

    def _center_table(self, event=None):
        # Keep the original 1150×750 composition centered when embedded.
        self.canvas.place(x=max(0, (self.winfo_width()-self.WIDTH)//2),
                          y=max(0, (self.winfo_height()-self.HEIGHT)//2),
                          width=self.WIDTH, height=self.HEIGHT)

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

        dialog.title('纵横交叉扑克 游戏规则')

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

        tk.Label(header, text='纵横交叉扑克 游戏规则', font=(font_name, 20, 'bold'),

                 fg=GOLD, bg=HEADER, anchor='w', wraplength=795,

                 justify=tk.LEFT).place(x=24, y=6, width=795, height=41)

        tk.Label(header, text='操作 · 取牌 · 赔率 · 牌型',

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

    @staticmethod
    def _build_payout_table(parent, column, title, rows):
        frame = tk.Frame(parent, bg='#F0F0F0', bd=1, relief=tk.SOLID)
        frame.grid(row=0, column=column, padx=8, sticky='nsew')
        tk.Label(frame, text=title, bg='#4B8BBE', fg='white', font=('微软雅黑', 11, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='nsew', pady=1
        )
        for row_index, (hand, payout) in enumerate(rows, start=1):
            background = '#E0E0E0' if row_index % 2 == 0 else '#F7F7F7'
            tk.Label(frame, text=hand, bg=background, padx=8, pady=4).grid(
                row=row_index, column=0, sticky='nsew', padx=1, pady=1
            )
            tk.Label(frame, text=payout, bg=background, padx=8, pady=4).grid(
                row=row_index, column=1, sticky='nsew', padx=1, pady=1
            )
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

def main(
    initial_balance=10000,
    username='Guest',
    *,
    parent=None,
    balance=None,
    user=None,
    on_back=None,
    on_balance_change=None,
):
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return CrissCrossPokerGUI(
            parent,
            actual_balance,
            actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title('纵横交叉扑克')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)
    page = CrissCrossPokerGUI(root, actual_balance, actual_user)
    page.pack(fill='both', expand=True)

    def close_standalone():
        try:
            update_balance_in_json(page.username, page.balance)
        except Exception:
            pass
        root.destroy()

    page.on_back = lambda _final_balance: close_standalone()
    root.protocol('WM_DELETE_WINDOW', page.on_close)
    root.mainloop()
    return page.balance


if __name__ == '__main__':
    final_balance = main()
    print(f'Final balance: {final_balance}')
