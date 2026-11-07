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
from tkinter import messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
from decimal import Decimal, ROUND_HALF_UP

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

# ========================== 全局常量和样式 ==========================
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
    1: '对子(J-A)',
    0: '高牌'
}

# This application's requested NET odds: a win returns stake + stake * odds.
# The listed numbers retain each version's hand categories and schedule; unlike
# the published total-return convention, this custom rule returns stake separately.
# Sources: https://wizardofodds.com/games/video-poker/tables/
# jacks-or-better/ (9/6), deuces-wild/ (Illinois Deuces), bonus-poker/ (8/5).
VIDEO_POKER_VERSIONS = {
    'jacks': {
        'name': '经典JACK或以上', 'english_name': 'Jacks or Better', 'table': '9/6',
        'feature': {
            'badge': '经典高对', 'accent': '#F1D38B',
            'title': 'J、Q、K、A 对子即可获奖',
            'detail': '无万能牌；两对、顺子等牌型奖励更高。',
        },
        'rules': '使用 52 张标准扑克，没有万能牌。\nJ、Q、K、A 对子起奖，两对净赔率 2:1。\n葫芦 9:1、同花 6:1，同花顺 50:1。',
        'payouts': {9: 800, 8: 50, 7: 25, 6: 9, 5: 6, 4: 4, 3: 3, 2: 2, 1: 1},
    },
    'deuces': {
        'name': '万能二点', 'english_name': 'Deuces Wild', 'table': 'Illinois Deuces',
        'feature': {
            'badge': '万能牌', 'accent': '#9DDED2',
            'title': '每张「2」都可代替任意牌',
            'detail': '三条起奖，并有五条与四张 2 特别奖。',
        },
        'rules': '使用 52 张牌，所有「2」都是万能牌。\n三条起奖，对子与两对不中奖。\n四条 4:1、葫芦 4:1、同花 3:1。\n自然皇家同花顺、四张 2、万能皇家同花顺、五条分别计奖。',
        'payouts': {9: 800, 'four_deuces': 200, 'wild_royal': 25, 'five_kind': 15,
                    8: 9, 7: 4, 6: 4, 5: 3, 4: 2, 3: 1},
    },
    'bonus': {
        'name': '四条奖励', 'english_name': 'Bonus Poker', 'table': '8/5',
        'feature': {
            'badge': '四条加奖', 'accent': '#F6BC87',
            'title': '四条按 A、2–4、5–K 分档',
            'detail': '四条 A 奖励最高，四条 2–4 次之。',
        },
        'rules': '使用 52 张标准扑克，没有万能牌。\nJ、Q、K、A 对子起奖，两对净赔率 2:1。\n四条 A 为 80:1；四条 2–4 为 40:1；四条 5–K 为 25:1。\n葫芦 8:1、同花 5:1。',
        'payouts': {9: 800, 8: 50, 'four_aces': 80, 'four_low': 40, 'four_high': 25,
                    6: 8, 5: 5, 4: 4, 3: 3, 2: 2, 1: 1},
    },
}
PAYOUT_NAMES = dict(HAND_RANK_NAMES, four_deuces='四张 2', wild_royal='万能皇家同花顺',
                    five_kind='五条', four_aces='四条 A', four_low='四条 2–4', four_high='四条 5–K')
DEFAULT_VERSION = 'jacks'
STRAIGHT_OR_BETTER = {4, 5, 6, 7, 8, 9, 'four_deuces', 'wild_royal', 'five_kind',
                      'four_aces', 'four_low', 'four_high'}

def round_currency(amount):
    return float(Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

def deal_double_hand():
    """Unique hearts, dealer 3–K, with at least one higher and one lower choice."""
    rng = secrets.SystemRandom()
    dealer = rng.choice(RANKS[1:-1])
    remaining = [rank for rank in RANKS if rank != dealer]
    while True:
        players = rng.sample(remaining, 4)
        if min(RANK_VALUES[r] for r in players) < RANK_VALUES[dealer] < max(RANK_VALUES[r] for r in players):
            return [Card('♥', rank) for rank in [dealer] + players]

def payout_name(category, version):
    if version == 'deuces' and category == 9:
        return '自然皇家同花顺'
    return PAYOUT_NAMES[category]

# ========================== Progressive 加载/保存（与 Three Card Poker 共用） ==========================
PROGRESSIVE_MIN = 271288.59
PROGRESSIVE_DEFAULT = 271288.59
PROGRESSIVE_KEY = "Progressive_2.50"

def load_progressive():
    """从 Progressive.json 加载奖池金额，若文件不存在或条目缺失则返回默认值"""
    path = str(_progressive_file)
    if not os.path.exists(path):
        return PROGRESSIVE_DEFAULT
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item.get('Games') == PROGRESSIVE_KEY:
                    amount = float(item.get('jackpot', PROGRESSIVE_DEFAULT))
                    return max(amount, PROGRESSIVE_MIN)
    except Exception:
        pass
    return PROGRESSIVE_DEFAULT

def save_progressive(amount):
    """保存奖池金额到 Progressive.json"""
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
        if item.get('Games') == PROGRESSIVE_KEY:
            item['jackpot'] = max(amount, PROGRESSIVE_MIN)
            found = True
            break
    if not found:
        data.append({"Games": PROGRESSIVE_KEY, "jackpot": max(amount, PROGRESSIVE_MIN)})
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# ========================== 文件操作（用户余额） ==========================
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

# ========================== 历史记录（Video_Poker.json） ==========================
def video_poker_log_path() -> str:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Video_Poker.json")

def save_video_poker_history(deck, ori_cards, aft_cards, bet, win_amount, hand_rank, hand_name, is_win,
                            version=DEFAULT_VERSION, payout_category=None, main_win=0,
                            progressive_win=0, double_rounds=None, cashout_reason=''):
    """
    保存牌局历史。
    history_record 包含 game, win, lose 以及各牌型计数（含 pair_2_10 和 pair_j_a）。
    """
    log_path = video_poker_log_path()
    # 初始化数据结构
    data = {
        "history_record": {
            "game": 0,
            "win": 0,
            "lose": 0,
            # 牌型计数（英文键）
            "royal_flush": 0,
            "straight_flush": 0,
            "four_of_a_kind": 0,
            "full_house": 0,
            "flush": 0,
            "straight": 0,
            "three_of_a_kind": 0,
            "two_pair": 0,
            "pair_j_a": 0,
            "pair_2_10": 0,
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
            print(f"读取历史文件出错: {e}，将使用全新记录")

    stats = data["history_record"]
    stats["game"] += 1
    if win_amount > 0:
        stats["win"] += 1
    else:
        stats["lose"] += 1

    # 根据 hand_name 增加牌型计数
    # hand_name 可能值：皇家同花顺, 同花顺, 四条, 葫芦, 同花, 顺子, 三条, 两对, 对子(J-A), 对子(2-10), 高牌
    name_to_key = {
        '皇家同花顺': 'royal_flush',
        '同花顺': 'straight_flush',
        '四条': 'four_of_a_kind',
        '葫芦': 'full_house',
        '同花': 'flush',
        '顺子': 'straight',
        '三条': 'three_of_a_kind',
        '两对': 'two_pair',
        '对子(J-A)': 'pair_j_a',
        '对子(2-10)': 'pair_2_10',
        '高牌': 'high_card',
        '五条': 'five_of_a_kind',
        '四张 2': 'four_deuces',
        '万能皇家同花顺': 'wild_royal_flush',
        '四条A＋2–4': 'four_of_a_kind',
        '四条2–4＋A–4': 'four_of_a_kind',
        '四条 A': 'four_of_a_kind',
        '四条 2–4': 'four_of_a_kind',
        '四条 5–K': 'four_of_a_kind',
        '四条A＋5–K': 'four_of_a_kind',
        '四条2–4＋5–K': 'four_of_a_kind',
        '自然皇家同花顺': 'royal_flush'
    }
    key = name_to_key.get(hand_name, 'high_card')
    if hand_name not in name_to_key and hand_name.startswith('对子('):
        pair = RANK_VALUES.get(hand_name[3:-1], 0)
        key = 'pair_j_a' if pair >= 11 else 'pair_2_10'
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
        "ori_cards": [str(c) for c in ori_cards],
        "aft_cards": [str(c) for c in aft_cards],
        "win_amount": win_amount,
        "bet": bet,
        "version": version,
        "version_name": VIDEO_POKER_VERSIONS[version]['name'],
        "version_english_name": VIDEO_POKER_VERSIONS[version]['english_name'],
        "paytable": VIDEO_POKER_VERSIONS[version]['table'],
        "odds_type": "net",
        "payout_category": payout_category,
        "main_win": main_win,
        "progressive_win": progressive_win,
        "base_win_amount": main_win + progressive_win,
        "double_rounds": double_rounds or [],
        "cashout_reason": cashout_reason,
        "hand_rank": hand_rank,
        "hand_name": hand_name,
        "is_win": is_win
    }
    data["history"].append(record)

    # 保留最新50局
    if len(data["history"]) > 50:
        data["history"] = data["history"][-50:]

    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ========================== 扑克牌类与牌堆 ==========================
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
        self._index_deck()

    def _index_deck(self):
        self.start_pos = self.cut_position
        size = len(self.full_deck)
        self.indexes = [(self.start_pos + i) % size for i in range(size)]
        self.pointer = 0

    def _secure_shuffle(self):
        for i in range(len(self.full_deck) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            self.full_deck[i], self.full_deck[j] = self.full_deck[j], self.full_deck[i]

    def deal(self, n=1):
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt

# ========================== 五张牌评估（用于 Progressive） ==========================
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
        pair_value = sorted_counts[0][0]
        if pair_value >= 11:
            return (1, sorted_values)
        else:
            return (0, sorted_values)
    return (0, values)

def evaluate_video_poker_hand(cards, version=DEFAULT_VERSION):
    """Return the paying category, evaluating wild cards under the selected rules."""
    if len(cards) != 5:
        return 0
    payouts = VIDEO_POKER_VERSIONS[version]['payouts']
    if version != 'deuces':
        rank, values = evaluate_five_card_hand(cards)
        if rank != 7 or version != 'bonus':
            return rank
        quad = values[0]
        if quad == 14:
            return 'four_aces'
        if quad in (2, 3, 4):
            return 'four_low'
        return 'four_high'
    natural = [c for c in cards if c.rank != '2']
    wilds = 5 - len(natural)
    counts = Counter(c.value for c in natural)
    values = set(counts)
    flush = len({c.suit for c in natural}) <= 1
    unique = len(values) == len(natural)
    straights = [set(range(low, low + 5)) for low in range(2, 11)] + [{14, 2, 3, 4, 5}]
    straight = unique and any(values <= run for run in straights)
    royal = flush and unique and values <= {10, 11, 12, 13, 14}
    maximum = max(counts.values(), default=0) + wilds
    full_house = any(
        all(v in (three, pair) for v in values)
        and counts.get(three, 0) <= 3 and counts.get(pair, 0) <= 2
        and 3 - counts.get(three, 0) + 2 - counts.get(pair, 0) == wilds
        for three in range(2, 15) for pair in range(2, 15) if three != pair)
    possible = {
        9: royal and wilds == 0,
        'four_deuces': wilds == 4,
        'wild_royal': royal and wilds > 0,
        'five_kind': maximum == 5,
        8: flush and straight,
        7: maximum >= 4,
        6: full_house,
        5: flush,
        4: straight,
        3: maximum >= 3,
    }
    # Paytable order resolves equal returns in favor of the stronger hand.
    return next((key for key in payouts if possible.get(key)), 0)


def automatic_hold_mask(cards, version=DEFAULT_VERSION):
    """Always hold wild twos, plus made hands or the three cards forming trips."""
    wild_holds = [version == 'deuces' and card.rank == '2' for card in cards]
    category = evaluate_video_poker_hand(cards, version)
    if category in STRAIGHT_OR_BETTER:
        return [True] * len(cards)
    if category != 3:
        return wild_holds
    natural = [c for c in cards if version != 'deuces' or c.rank != '2']
    counts = Counter(c.value for c in natural)
    target = max(counts, key=lambda value: (counts[value], value))
    return [c.value == target or held for c, held in zip(cards, wild_holds)]


# Shared manual layout; only the selected mode's notes and examples are inserted.
MODE_INSTRUCTION_NOTES = {
    'jacks': [
        ('高对起奖', '只有 J、Q、K、A 的对子中奖。\n2–10 的对子与高牌不中奖。'),
        ('普通牌面', '所有牌都按实际点数和花色使用。\n「2」是普通牌，不带 WILD 标记。'),
        ('四条判奖', '任何点数的四条均为 25:1。\n第五张牌不影响四条赔率。'),
    ],
    'deuces': [
        ('万能牌与 WILD 标记', '每张「2」可代替任意点数和花色，组成最佳中奖牌型。\n万能牌带有 45° 的 WILD 斜条，主牌与原始手牌缩略图均显示。'),
        ('万能牌自动保留', '原始手牌无论是什么牌型，所有「2」都会自动保留。\n玩家可点击牌面或保留按钮，逐张取消保留。'),
        ('特别牌型', '自然皇家同花顺不能使用万能牌。\n使用「2」组成的皇家同花顺，按万能皇家同花顺判奖。\n四张 2 和五条按各自独立赔率判奖。'),
        ('三条保留', '当中奖牌型为三条时，只保留组成三条的三张牌。\n「2」可以计入这三张；玩家可逐张取消保留。'),
        ('封印的累进大奖', '本模式的大奖灯处于封印状态，不可参加。\n不显示 $2.50 筹码，不扣除大奖下注。'),
        ('翻倍中的「2」', '翻倍画面的「2」是普通点数，最小且不带 WILD 标记。\n庄家只能是 3–K，玩家可抽到 2 或 A。'),
    ],
    'bonus': [
        ('高对起奖', '只有 J、Q、K、A 的对子中奖。\n2–10 的对子与高牌不中奖。'),
        ('四条分档', '四条 A：80:1。\n四条 2、3 或 4：40:1。\n四条 5–K：25:1。\n第五张牌不影响上述赔率。'),
        ('普通牌面', '没有万能牌，所有牌按实际点数和花色使用。\n「2」也是普通牌，不带 WILD 标记。'),
    ],
}

def build_video_poker_instructions(version_key=DEFAULT_VERSION):
    """Current-mode manual, with explicit newline characters in multiline details."""
    version = VIDEO_POKER_VERSIONS[version_key]
    examples = {
        9: ('同一花色的\n10、J、Q、K、A', '♠♠♠♠♠', '10 J Q K A'),
        8: ('同一花色的\n五张连续牌', '♥♥♥♥♥', '6 7 8 9 10'),
        7: ('四张同点数', '♥♣♦♠♥', 'A A A A K'),
        6: ('三张同点数\n加一对', '♥♣♦♠♥', 'A A A K K'),
        5: ('五张同一花色\n点数不连续', '♣♣♣♣♣', 'K 10 8 7 5'),
        4: ('五张连续牌\n可有不同花色', '♥♠♦♣♠', '6 7 8 9 10'),
        3: ('三张同点数', '♥♣♠♦♥', 'A A A K 7'),
        2: ('两组不同点数\n的对子', '♥♣♦♠♥', 'A A K K 7'),
        1: ('J、Q、K、A\n的一个对子', '♥♣♠♦♥', 'J J K 9 4'),
        'four_aces': ('四张 A\n第五张不限', '♥♣♦♠♥', 'A A A A K'),
        'four_low': ('四张 2、3 或 4\n第五张不限', '♥♣♦♠♥', '3 3 3 3 K'),
        'four_high': ('四张 5–K\n第五张不限', '♥♣♦♠♥', 'K K K K A'),
    }
    if version_key == 'deuces':
        examples = {
            9: ('同花色 10–A\n不使用万能牌', '♠♠♠♠♠', '10 J Q K A'),
            'four_deuces': ('原始牌中\n有四张「2」', '♥♣♦♠♥', '2 2 2 2 K'),
            'wild_royal': ('使用万能牌\n组成同花色 10–A', '♥♥♥♥♠', '10 J Q K 2'),
            'five_kind': ('使用万能牌\n组成五张同点数', '♥♣♦♠♥', 'A A A 2 2'),
            8: ('万能牌可补成\n同花色的顺子', '♥♥♥♠♦', '5 6 7 2 2'),
            7: ('四张同点数\n可使用万能牌', '♥♣♦♠♥', 'K K K 2 9'),
            6: ('三条加一对\n可使用万能牌', '♥♣♦♠♥', 'K K 9 9 2'),
            5: ('五张同一花色\n万能牌可补花色', '♥♥♥♥♠', '3 6 9 K 2'),
            4: ('五张连续牌\n万能牌可补点数', '♥♣♦♠♥', '5 6 7 8 2'),
            3: ('三张同点数\n万能牌可计入', '♥♣♦♠♥', 'K K 2 8 4'),
        }
    paytable = [[payout_name(key, version_key), f'{odds}:1', f'主注 × {odds + 1}']
                for key, odds in version['payouts'].items()]
    paytable.append(['其他', '未中奖', '不返还'])
    hand_rows = []
    for number, key in enumerate(version['payouts'], 1):
        description, suits, ranks = examples[key]
        hand_rows.append([str(number), payout_name(key, version_key), description,
                          ('__CARD_IMAGES__', tuple(zip(suits, ranks.split())))])
    progressive_enabled = version_key != 'deuces'
    progressive_rule = '按原始五张的实际点数和花色判奖，不使用抽牌结果。\n大奖获胜金额立即加进余额，不参与翻倍。'
    progressive_card = ['累进大奖 · 原始手牌', '', [('判定方式', progressive_rule)], [
        ('每局参加金额 $2.50', ['原始牌型', '大奖奖励'], [
            ['皇家同花顺', '当前奖池的 100%'], ['同花顺', '当前奖池的 10%'],
            ['四条', '$1,250'], ['葫芦', '$375'], ['同花', '$250'],
        ]),
    ]] if progressive_enabled else ['累进大奖 · 封印', '', [
        ('不可参加', '万能二点模式的大奖灯处于封印状态。\n无法下注，也不会扣除 $2.50。'),
    ], []]
    bet_rule = '选择 100／200／500／1K／5K／10K 筹码。\n选中的筹码即为本局主注，重复点击不会累加。'
    bet_rule += ('\n可点击大奖灯参加或取消，每局额外下注 $2.50。' if progressive_enabled else
                 '\n本模式大奖灯封印，不能下注累进大奖。')
    deal_rule = '点击「开牌」，发出并翻开五张牌。'
    if progressive_enabled:
        deal_rule += '\n如参加大奖，先播放筹码移动与灯环动画，再发牌。'
    reward_rule = '主注按最终五张判奖。\n底部「本局下注」切换成「本局获胜」。\n主注奖金暂存，可翻倍或点击「再来一局」全额领取。'
    if progressive_enabled:
        reward_rule += '\n大奖按原始五张判奖，获胜立即入余额，不参与翻倍。'
    hold_lines = ['点击扑克或下方按钮，切换「保留」。',
                  '顺子或以上自动保留全部五张。',
                  '三条仅自动保留组成三条的三张。']
    if version_key == 'deuces':
        hold_lines.append('无论是什么牌型，所有「2」都会自动保留。')
    hold_lines.append('任何自动保留都可以逐张手动取消。')
    return [
        ('玩法', f"当前版本：{version['name']}", [
            ['本版本玩法', '', [
                ('本版本规则', version['rules']),
                ('本局目标', '保留需要的牌，再换掉其余牌。\n以最终五张的牌型赢取当前版本的主注奖励。'),
                ('派彩口径', '净赢 = 主注 × 净赔率。\n中奖时本金另返，总返还 = 主注 ×（净赔率＋1）。\n例如下注 100，1:1 净赢 100，总返还 200。\n「本局获胜」显示可领取或用于翻倍的总金额。'),
            ], []],
            ['一局完整流程', '', [
                ('下注', bet_rule),
                ('开牌', deal_rule),
                ('保留', '\n'.join(hold_lines)),
                ('换牌', '点击「换牌」，只替换未保留的扑克。\n全部保留时直接进入判奖。'),
                ('判奖', reward_rule),
                ('翻倍', '只以尚未入账的主注奖金为赌注，包含主注本金。\n发出五张不同点数的红桃，先打开最左侧庄家牌（红底）。\n庄家只能是 3–K；右侧至少一张较大、至少一张较小。\n选择一张：大于庄家则金额翻倍，否则归零。\nA 最大，2 最小，无平局；赢后可继续翻倍或退出。\n输牌提示保留 2.5 秒，然后自动退出翻倍画面。'),
                ('退出', '只在进入翻倍画面后启用。\n庄家尚未开牌：全额领取。\n庄家已开牌、玩家未选牌：领取当前主注赌注的一半。\n选牌获胜后：全额领取翻倍后的主注奖金。\n输牌后也可立即退出；退出后按钮恢复禁用。'),
                ('再来一局', '自动领取尚未入账的主注奖金，再进入下注阶段。\n底部恢复「本局下注」，筹码面额沿用上局。\n可参加大奖的模式自动沿用参与选择。\n翻倍等待选牌或输牌等待退出时，此按钮禁用。'),
            ], []],
        ]),
        ('下注 & 限红', '固定筹码与独立大奖下注。', [
            ['下注项目', '', [], [('下注项目与限红', ['项目', '下注额', '作用'], [
                ['主注', '$100／$200／$500\n$1,000／$5,000／$10,000', '按最终五张牌型兑奖。\n发牌后锁定筹码。'],
                (['累进大奖', '每局 $2.50', '按原始五张的实际牌面兑奖。\n获胜立即入余额，不参与翻倍。'] if progressive_enabled else
                 ['累进大奖', '封印', '本模式不可参加。\n不扣除大奖下注。']),
            ])]],
            ['大奖参与动画', '', [
                (('自动参与', '手动参加，或点击「再来一局」恢复参加时，\n$2.50 筹码从灯下方移入灯中。\n开牌后灯环跑满，筹码收走，再发牌。') if progressive_enabled else
                 ('封印状态', '大奖灯静止显示封印，不播放参与动画。\n切回可参加大奖的模式后，可重新点击参加。')),
            ], []],
        ]),
        ('获胜条件 & 赔率', f"以下主注赔率仅适用于{version['name']}。", [
            [f"{version['name']} · 主注赔率", '', [], [
                ('最终手牌', ['牌型', '净赔率', '含本金总返还'], paytable),
            ]],
            progressive_card,
        ]),
        ('牌型', f"{version['name']}的中奖牌型与对应示例。", [
            ['本版本中奖牌型', '示例按本版本规则解释；兑奖以主注赔率表为准。', [], [
                ('牌型示例', ['序', '牌型', '组成条件', '示例'], hand_rows),
            ]],
        ]),
        ('特别事项', f"{version['name']}的专属规则。", [
            ['本版本特别规则', '', MODE_INSTRUCTION_NOTES[version_key], []],
            ['操作提示', '', [
                ('原始手牌', '底部五张缩略图保留本局最初发出的牌。\n换牌和翻倍不会修改原始手牌记录。'),
                ('快捷操作', '数字键 1–5 切换保留，翻倍时选择对应位置的牌。\nEnter 执行右下角当前按钮。'),
            ], []],
        ]),
    ]


# ========================== 游戏逻辑类 ==========================
class VideoPokerGame:
    def __init__(self):
        self.reset_game()

    def reset_game(self, version=DEFAULT_VERSION):
        self.version = version
        self.deck = None
        self.player_hand = []
        self.bet_amount = 0
        self.stage = "betting"
        self.hold_status = [False] * 5
        self.final_hand = False

    def deal_initial(self):
        if self.deck is None:
            self.deck = Deck()
        self.player_hand = self.deck.deal(5)

    def draw_cards(self):
        for i in range(5):
            if not self.hold_status[i]:
                self.player_hand[i] = self.deck.deal(1)[0]
        self.final_hand = True

# ========================== 经典机台立体按钮 ==========================
class MachineButton(tk.Canvas):
    """Canvas 绘制的机台按键，保留 Tk 的 config/state/invoke 接口。"""
    def __init__(self, master, text, command, width=140, height=44,
                 face='#397A48', fg=PANEL_BG, font=('Arial', 11, 'bold'),
                 bg=ROOT_BG, state=tk.NORMAL):
        super().__init__(master, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0, takefocus=1)
        self._text, self._command = text, command
        self._face, self._fg, self._font = face, fg, font
        self._state, self._pressed = state, False
        self._width, self._height = width, height
        self.bind('<ButtonPress-1>', self._press)
        self.bind('<ButtonRelease-1>', self._release)
        self.bind('<Leave>', self._leave)
        self.bind('<space>', lambda _e: self.invoke())
        self._paint()

    @staticmethod
    def _shade(color, factor):
        rgb = [int(color[i:i+2], 16) for i in (1, 3, 5)]
        return '#' + ''.join(f'{max(0, min(255, round(c*factor))):02x}' for c in rgb)

    def _paint(self):
        self.delete('all')
        enabled = self._state != tk.DISABLED
        face = self._face if enabled else '#263C34'
        face = self._shade(face, .78) if self._pressed else face
        w, h = self._width, self._height
        self.create_rectangle(2, 3, w-1, h-1, fill='#071A14', outline='')
        self.create_rectangle(1, 1, w-4, h-4, fill=self._shade(face, .6),
                              outline=GOLD if enabled else '#52634E', width=1)
        self.create_rectangle(4, 4, w-7, h-7, fill=face,
                              outline=self._shade(face, 1.25), width=1)
        self.create_line(7, 6, w-10, 6, fill=self._shade(face, 1.6))
        self.create_text((w-4)/2, (h-4)/2 + (2 if self._pressed else 0),
                         text=self._text, fill=self._fg if enabled else '#819284',
                         font=self._font, justify=tk.CENTER)
        super().configure(cursor='hand2' if enabled else '')

    def configure(self, cnf=None, **kwargs):
        if isinstance(cnf, dict):
            kwargs = dict(cnf, **kwargs)
        elif cnf is not None:
            return super().configure(cnf, **kwargs)
        for key, attribute in (('text', '_text'), ('command', '_command'),
                               ('state', '_state'), ('face', '_face'), ('fg', '_fg')):
            if key in kwargs:
                setattr(self, attribute, kwargs.pop(key))
        if kwargs:
            super().configure(**kwargs)
        self._pressed = False
        self._paint()

    config = configure

    def cget(self, key):
        if key in ('state', 'text', 'command'):
            return getattr(self, '_' + key)
        return super().cget(key)

    def _press(self, _event):
        if self._state != tk.DISABLED:
            self._pressed = True
            self._paint()

    def _release(self, event):
        active = self._pressed and 0 <= event.x < self._width and 0 <= event.y < self._height
        self._pressed = False
        self._paint()
        if active:
            self.invoke()

    def _leave(self, _event):
        self._pressed = False
        self._paint()

    def invoke(self):
        if self._state != tk.DISABLED and callable(self._command):
            return self._command()


# ========================== 主GUI类 ==========================
class VersionButton(MachineButton):
    """Chinese mode name with a persistent selection highlight."""
    def __init__(self, master, name, command):
        # Tkinter owns _name and overwrites it with e.g. !versionbutton.
        self._display_name = name
        self._selected = self._hover = False
        super().__init__(master, name, command, width=336, height=31,
                         font=('Microsoft YaHei UI', 11, 'bold'), bg='#102B29')
        self.bind('<Enter>', self._enter)

    def _enter(self, _event):
        self._hover = True
        self._paint()

    def _leave(self, _event):
        self._hover = self._pressed = False
        self._paint()

    def configure(self, cnf=None, **kwargs):
        if isinstance(cnf, dict):
            kwargs = dict(cnf, **kwargs)
            cnf = None
        if 'selected' in kwargs:
            self._selected = bool(kwargs.pop('selected'))
        return super().configure(cnf, **kwargs)

    config = configure

    def _paint(self):
        self.delete('all')
        enabled = self._state != tk.DISABLED
        selected = self._selected
        face = '#315A3E' if selected else '#244538' if self._hover and enabled else '#16372F'
        if self._pressed and enabled:
            face = self._shade(face, .82)
        border = GOLD if selected else '#648069' if enabled and self._hover else '#385C4A'
        self.create_rectangle(1, 1, 334, 29, fill=face, outline=border, width=2 if selected else 1)
        if selected:
            self.create_rectangle(2, 2, 5, 28, fill=GOLD, outline='')
        self.create_text(17, 15, text='✓' if selected else '○',
                         fill=GOLD if selected else '#769880', font=('Arial', 11, 'bold'))
        self.create_text(31, 15, text=self._display_name, anchor='w',
                         fill='#FFE29A' if selected else PANEL_BG if enabled else '#A2B6A5',
                         font=('Microsoft YaHei UI', 11, 'bold'))
        tk.Canvas.configure(self, cursor='hand2' if enabled else '')


class ModeFeatureCard(tk.Canvas):
    """Inset feature card; content and accent follow the selected mode."""
    def __init__(self, master):
        super().__init__(master, width=336, height=82, bg='#102B29',
                         highlightthickness=0, bd=0, takefocus=0)

    def _rounded_box(self, x1, y1, x2, y2, radius, fill):
        self.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline='')
        self.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=fill, outline='')
        for x in (x1, x2 - radius * 2):
            for y in (y1, y2 - radius * 2):
                self.create_oval(x, y, x + radius * 2, y + radius * 2, fill=fill, outline='')

    def show_version(self, version):
        feature = version['feature']
        accent = feature['accent']
        self.delete('all')
        self._rounded_box(1, 5, 335, 81, 10, '#041B17')
        self._rounded_box(1, 1, 335, 78, 10, '#627A55')
        self._rounded_box(2, 2, 334, 77, 9, '#153C33')
        self.create_line(16, 3, 320, 3, fill='#90A777')
        self.create_line(8, 16, 8, 62, fill=accent, width=3)
        self.create_oval(17, 10, 33, 26, fill='#2A5141', outline='')
        self.create_text(25, 18, text='◆', fill=accent, font=('Arial', 8, 'bold'))
        self.create_text(39, 18, text='模式特色', anchor='w', fill='#B9CBAF',
                         font=('Microsoft YaHei UI', 9))
        self._rounded_box(247, 9, 321, 27, 6, '#294D3F')
        self.create_text(284, 18, text=feature['badge'], fill=accent,
                         font=('Microsoft YaHei UI', 9, 'bold'))
        self.create_text(18, 40, text=feature['title'], anchor='w', fill=accent,
                         font=('Microsoft YaHei UI', 11, 'bold'))
        self.create_text(18, 62, text=feature['detail'], anchor='w', fill='#D5E1CE',
                         font=('Microsoft YaHei UI', 9))


class VideoPokerGUI(tk.Frame):
    WIDTH, HEIGHT = 1150, 750
    CARD_SIZE = (126, 176)
    THUMB_SIZE = (38, 53)
    PROGRESSIVE_CHIP_START = (575, 292)
    BET_CHIP_RADIUS = 16 * 4 / 3
    HOUSE_CHIP_POS = (575, 43)
    PROGRESSIVE_CHIP_MS = 220
    CHIP_VALUES = (100, 200, 500, 1000, 5000, 10000)
    DOUBLE_STAGES = ('double_dealing', 'double_choose', 'double_ready', 'double_lost')
    PROGRESSIVE_LAMP_WIDTH = 122.0 * .8
    SCREEN_BG = '#092D25'
    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG)
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.configure(bg=ROOT_BG)

        self.username = username
        self.balance = float(initial_balance)
        self.game = VideoPokerGame()
        self.card_images = {}
        self.original_images = {}
        self.back_image = None
        self.grey_back = None
        self.animation_queue = []
        self.animation_in_progress = False
        self.selected_chip = self.CHIP_VALUES[0]
        self.selected_version = DEFAULT_VERSION
        self.round_version = DEFAULT_VERSION
        self.chip_buttons = []
        self.chip_texts = {}
        self.last_win = 0
        self.pending_win = 0
        self._round_result = None
        self._round_finalized = False
        self.double_hand = []
        self.double_rounds = []
        self._double_choice = None
        self._double_job = None
        self._double_exit_job = None
        self.buttons_disabled = False
        self._jobs = set()
        self._closing = False
        self._key_bindings = []
        self.lamps = {}
        self.bet_spots = {}
        self.round_progressive_active = False
        self._progressive_chip_xy = None
        self._progressive_chip_motion = False
        self._progressive_chip_job = None
        self.hold_buttons = []
        self.card_containers = []
        self.cn_font = 'Microsoft YaHei UI'

        self.game_in_progress = False

        self.bottom_labels = []
        self.hold_labels = []
        self.player_label = None
        self.initial_hand = []          # 保存初始发牌时的5张牌（原始手牌）
        self.initial_thumbnails = []    # 缩略图标签列表

        # ---------- Progressive 相关 ----------
        self.progressive_var = tk.IntVar(value=0)        # 大奖灯参与状态
        self.progressive_amount = load_progressive()     # 当前奖池金额
        self.min_progressive = PROGRESSIVE_MIN
        self.last_progressive_state = 0                  # 用于重置时恢复

        self._load_assets()
        self._create_widgets()
        self._bind_machine_keys()
        self.bind('<Destroy>', self._on_destroy, add='+')

    def _schedule(self, delay, callback):
        def run():
            self._jobs.discard(job)
            if not self._closing:
                callback()
        job = self.after(delay, run)
        self._jobs.add(job)
        return job

    def _on_destroy(self, event):
        if event.widget is not self:
            return
        if self._round_result is not None and not self._round_finalized:
            self._collect_pending_win(render=False)
        self._closing = True
        self._cancel_ui_callbacks()

    def _cancel_ui_callbacks(self):
        for job in tuple(self._jobs):
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self._jobs.clear()
        for sequence, binding in self._key_bindings:
            try:
                self.winfo_toplevel().unbind(sequence, binding)
            except tk.TclError:
                pass
        self._key_bindings.clear()
        self._double_job = self._double_exit_job = self._progressive_chip_job = None
        self._progressive_chip_motion = False
        dialog = getattr(self, '_game_instruction_dialog', None)
        self._game_instruction_dialog = None
        if dialog is not None:
            try:
                if dialog.winfo_exists():
                    dialog.destroy()
            except tk.TclError:
                pass

    def _bind_machine_keys(self):
        top = self.winfo_toplevel()
        def run(event, command):
            if self._closing or not self.winfo_viewable():
                return
            focus = top.focus_get()
            if focus is not None and focus.winfo_toplevel() is not top:
                return
            if isinstance(focus, (tk.Entry, tk.Text)):
                return
            command()
            return 'break'
        for sequence, command in [('<Return>', lambda: self.start_button.invoke())] + [
                (str(i+1), lambda index=i: self.on_card_click(index)) for i in range(5)]:
            binding = top.bind(sequence, lambda event, action=command: run(event, action), add='+')
            self._key_bindings.append((sequence, binding))

    def on_close(self):
        """Window close returns through the launcher's callback, as in cari."""
        if self._closing:
            return
        if self._round_result is not None and not self._round_finalized:
            self._collect_pending_win(render=False)
        try:
            update_balance_in_json(self.username, self.balance)
        except Exception:
            pass
        self._closing = True
        self._cancel_ui_callbacks()
        final_balance = float(self.balance)
        if callable(self.on_balance_change):
            self.on_balance_change(final_balance)
        if callable(self.on_back):
            self.on_back(final_balance)
        else:
            self.winfo_toplevel().destroy()


    # ---------- 加载扑克牌 ----------
    def _load_assets(self):
        """沿用项目 PNG 牌面；缺少素材时绘制可辨认的白底纸牌。"""
        size = self.CARD_SIZE
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        old_folder = getattr(self, 'current_poker_folder', None)
        self.current_poker_folder = ('Poker2' if old_folder == 'Poker1' else 'Poker1') if old_folder else random.choice(['Poker1', 'Poker2'])
        folder = os.path.join(base, 'A_Tools', 'Card', self.current_poker_folder)
        suits = {'♠': 'Spade', '♥': 'Heart', '♦': 'Diamond', '♣': 'Club'}
        def font_at(points):
            for name in ('DejaVuSans-Bold.ttf', 'arial.ttf'):
                try:
                    return ImageFont.truetype(name, points)
                except OSError:
                    pass
            return ImageFont.load_default()
        small_font, large_font = font_at(23), font_at(58)
        self.original_images, self.card_images = {}, {}
        for key in ['back'] + [(s, r) for s in SUITS for r in RANKS]:
            filename = 'Background.png' if key == 'back' else f'{suits[key[0]]}{key[1]}.png'
            try:
                with Image.open(os.path.join(folder, filename)) as original:
                    image = original.convert('RGBA').copy()
            except (OSError, ValueError):
                image = Image.new('RGBA', size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(image)
                draw.rounded_rectangle((1, 1, size[0]-2, size[1]-2), radius=8,
                    fill=DARK_BLUE if key == 'back' else '#FFFBEE', outline=GOLD, width=2)
                if key == 'back':
                    for y in range(13, size[1]-12, 12):
                        draw.line((12, y, size[0]-13, y), fill='#647F94', width=2)
                    draw.rounded_rectangle((18, 45, size[0]-19, size[1]-46), radius=5,
                                           outline=GOLD, width=2)
                    draw.text((size[0]/2, size[1]/2), 'VP', font=small_font,
                              fill='#F6D675', anchor='mm')
                else:
                    suit, rank = key
                    color = '#B51F2A' if suit in '♥♦' else '#14251F'
                    try:
                        draw.text((9, 9), rank+suit, font=small_font, fill=color)
                        draw.text((size[0]/2, size[1]/2), suit, font=large_font,
                                  fill=color, anchor='mm')
                    except UnicodeEncodeError:
                        draw.text((9, 9), rank+suits[suit][0], font=small_font, fill=color)
            self.original_images[key] = image
            photo = ImageTk.PhotoImage(image.resize(size, Image.Resampling.LANCZOS), master=self)
            if key == 'back':
                self.back_image = photo
                self.grey_back = ImageTk.PhotoImage(image.convert('L').convert('RGBA').resize(size), master=self)
                self.thumb_back = ImageTk.PhotoImage(image.resize(self.THUMB_SIZE, Image.Resampling.LANCZOS), master=self)
            else:
                self.card_images[key] = photo
        self.wild_card_images = {
            (suit, '2'): ImageTk.PhotoImage(
                self._card_art(Card(suit, '2'), size, version='deuces'), master=self)
            for suit in SUITS
        }

    @staticmethod
    def _wild_ribbon(image):
        """A 45-degree emerald ribbon, clipped to the card's existing silhouette."""
        image = image.convert('RGBA').copy()
        original_alpha = image.getchannel('A')
        scale = image.width / 126
        width, height = max(1, round(136 * scale)), max(1, round(25 * scale))
        ribbon = Image.new('RGBA', (width, height), '#164A3C')
        draw = ImageDraw.Draw(ribbon)
        draw.rectangle((0, 0, width - 1, height - 1), outline='#E8CA70',
                       width=max(1, round(2 * scale)))
        for name in ('arialbd.ttf', 'DejaVuSans-Bold.ttf', 'arial.ttf'):
            try:
                font = ImageFont.truetype(name, max(6, round(16 * scale)))
                break
            except OSError:
                pass
        else:
            font = ImageFont.load_default()
        draw.text((width / 2, height / 2), 'WILD', font=font, fill='#FFF1A4', anchor='mm')
        ribbon = ribbon.rotate(-45, resample=Image.Resampling.BICUBIC, expand=True)
        layer = Image.new('RGBA', image.size, (0, 0, 0, 0))
        layer.alpha_composite(ribbon, (round(image.width * .74 - ribbon.width / 2),
                                       round(image.width * .26 - ribbon.height / 2)))
        layer = Image.composite(layer, Image.new('RGBA', image.size), original_alpha)
        image.alpha_composite(layer)
        image.putalpha(original_alpha)
        return image

    def _card_art(self, card, size, *, version=None, allow_wild=True):
        image = self.original_images[(card.suit, card.rank)].resize(size, Image.Resampling.LANCZOS)
        version = self._active_version() if version is None else version
        if allow_wild and version == 'deuces' and card.rank == '2':
            image = self._wild_ribbon(image)
        return image

    def _card_photo(self, card, size=None, *, version=None):
        version = self._active_version() if version is None else version
        if size is None:
            faces = self.wild_card_images if version == 'deuces' and card.rank == '2' else self.card_images
            return faces.get((card.suit, card.rank), self.back_image)
        return ImageTk.PhotoImage(self._card_art(card, size, version=version), master=self)

    # ---------- 筹码选择 ----------
    def select_chip(self, amount):
        """固定筹码直接决定整局主注，不累加金额。"""
        if self.game_in_progress or amount not in self.CHIP_VALUES:
            return
        self.selected_chip = amount
        self.bet_var.set(str(amount))
        self._refresh_amount_display()
        for chip in self.chip_buttons:
            selected = self.chip_texts[chip] == amount
            chip.itemconfigure('rim', outline=GOLD if selected else '#64785B', width=3 if selected else 1)
        self._refresh_paytable()

    def _selected_bet(self):
        return self.selected_chip if self.selected_chip in self.CHIP_VALUES else self.CHIP_VALUES[0]







    def clear_btn_frame(self):
        for widget in self.btn_frame.winfo_children():
            widget.destroy()

    def add_main_buttons(self):
        self.clear_btn_frame()
        self.start_button = MachineButton(self.btn_frame, '开牌\nDEAL', self.start_game,
            width=132, height=68, face=HEADER_BG, fg=TITLE_FG, font=('Arial', 13, 'bold'))
        self.start_button.place(x=0, y=0)
        self.start_button.config(state=tk.DISABLED if self._progressive_chip_motion else tk.NORMAL)
        self._refresh_risk_buttons()
        self.draw_button = self.start_button
        self._refresh_holds()


    def add_draw_button(self):
        self.draw_button = self.start_button
        self.draw_button.config(text='换牌\nDRAW', command=self.draw_action, state=tk.DISABLED)

    # ---------- 创建主界面 ----------
    def _create_widgets(self):
        self.configure(width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.canvas = c = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
            bg=ROOT_BG, highlightthickness=0)
        c.pack(fill=tk.BOTH, expand=True)
        c.create_rectangle(14, 12, 1136, 738, fill='#15392D', outline=GOLD, width=3)
        c.create_rectangle(21, 19, 1129, 731, outline='#65784B', width=1)
        c.create_line(35, 72, 1115, 72, fill=GOLD)
        self.main_title = c.create_text(575, 42, text='视频扑克', fill='#F6D675',
                                       font=(self.cn_font, 24, 'bold'))
        self.english_title = c.create_text(1110, 43, text='VIDEO POKER', anchor='e',
                                          fill='#C7CFA7', font=('Arial', 16, 'bold'))
        self._draw_paytable()

        # 奖池与 cari 参与灯放在机台正中央。
        c.create_rectangle(411, 82, 739, 312, fill='#123C30', outline=GOLD)
        c.create_rectangle(411, 82, 739, 112, fill='#315C40', outline=GOLD)
        c.create_text(575, 97, text='累进大奖  PROGRESSIVE', fill='#F6D675', font=('Arial', 14, 'bold'))
        self.progressive_amount_var = tk.StringVar(self, f'${self.progressive_amount:,.2f}')
        self.progressive_display = ProgressiveSevenSegmentDisplay(c, self.progressive_amount_var,
            font=('Arial', 21, 'bold'), bg='#123C30', fg='#FFE29A')
        self.progressive_display.place(x=575, y=144, anchor='center')
        self._draw_progressive_lamp('Player', 575, 221)
        self._draw_progressive_chip(*self.PROGRESSIVE_CHIP_START)

        # 右侧选择玩法版本；实际派彩和左侧配表共用同一份版本数据。
        c.create_rectangle(758, 82, 1118, 312, fill='#102B29', outline=GOLD)
        c.create_rectangle(758, 82, 1118, 112, fill='#315C40', outline=GOLD)
        c.create_text(938, 97, text='视频扑克 · 版本选择', fill=PANEL_BG, font=('Arial', 13, 'bold'))
        self.version_buttons = {}
        for i, (key, version) in enumerate(VIDEO_POKER_VERSIONS.items()):
            button = VersionButton(c, version['name'],
                lambda selected=key: self.select_version(selected))
            button.place(x=770, y=116 + i*33)
            self.version_buttons[key] = button
        self.version_feature_card = ModeFeatureCard(c)
        self.version_feature_card.place(x=770, y=222)
        self._refresh_versions()

        c.create_rectangle(32, 316, 1118, 607, fill=self.SCREEN_BG, outline='#65784B')
        # 扑克上方只显示当前牌型，居中；没有阶段或操作提示文字。
        self.player_label = tk.Label(c, text='', bg=self.SCREEN_BG, fg=GOLD,
            font=('Arial', 16, 'bold'), anchor='center')
        self.player_label.place(x=100, y=320, width=950, height=28)
        for i in range(5):
            x = 133 + i*184
            # 标记有独立的上方空间，绝不叠放在牌面控件内。
            held = tk.Label(c, text='保留  HELD', bg=GOLD, fg=TITLE_FG, font=('Arial', 10, 'bold'))
            self.hold_labels.append(held)
            container = tk.Frame(c, bg=self.SCREEN_BG, highlightbackground='#607B58', highlightthickness=2)
            container.place(x=x, y=379, width=148, height=182)
            self.card_containers.append(container)
            label = tk.Label(container, image=self.back_image, bg=self.SCREEN_BG,
                             bd=0, padx=0, pady=0, cursor='hand2')
            label.place(x=9, y=1)
            label.bind('<Button-1>', lambda _e, index=i: self.on_card_click(index))
            self.bottom_labels.append(label)
            button = MachineButton(c, f'保留  HOLD {i+1}', lambda index=i: self.on_card_click(index),
                width=148, height=34, face='#315C40', state=tk.DISABLED, bg=self.SCREEN_BG)
            button.place(x=x, y=569)
            self.hold_buttons.append(button)

        self.double_button = MachineButton(c, '翻倍', self.start_double,
            width=78, height=50, face=HEADER_BG, fg=TITLE_FG, font=('Arial', 12, 'bold'),
            state=tk.DISABLED, bg=self.SCREEN_BG)
        self.double_button.place(x=1032, y=404)
        self.exit_button = MachineButton(c, '退出', self.cash_out_round,
            width=78, height=50, face='#315C40', font=('Arial', 12, 'bold'),
            state=tk.DISABLED, bg=self.SCREEN_BG)
        self.exit_button.place(x=1032, y=466)

        # 加高的底部操作栏：说明 / 两行金额 / 六枚筹码 / 原始牌 / 阶段按钮。
        c.create_rectangle(32, 617, 1118, 727, fill=self.SCREEN_BG, outline='#65784B')
        for x in (390, 706, 958):
            c.create_line(x, 627, x, 717, fill='#49684F')
        self.info_button = MachineButton(c, '?', self.show_game_instructions,
            width=42, height=68, face=DARK_BLUE, bg=self.SCREEN_BG)
        self.info_button.place(x=42, y=640)
        self.balance_label = tk.Label(c, text=f'余额：${self.balance:,.2f}', bg=self.SCREEN_BG,
            fg=GOLD, font=('Arial', 16, 'bold'), anchor='w')
        self.balance_label.place(x=95, y=635, width=287, height=36)
        self.round_amount_label = tk.Label(c, text='', bg=self.SCREEN_BG, fg=GOLD,
            font=('Arial', 16, 'bold'), anchor='w')
        self.round_amount_label.place(x=95, y=675, width=287, height=36)
        self.bet_var = tk.StringVar(self, str(self.selected_chip))
        self.chip_container = tk.Frame(c, bg=self.SCREEN_BG)
        self.chip_container.place(x=398, y=644, width=300, height=60)
        for i in range(5):
            label = tk.Label(c, image=self.thumb_back, bg=self.SCREEN_BG, bd=0, padx=0, pady=0)
            label.place(x=727+i*44, y=636, width=38, height=53)
            self.initial_thumbnails.append(label)
        tk.Label(c, text='原始手牌', bg=self.SCREEN_BG, fg=PANEL_BG,
            font=('Arial', 11, 'bold')).place(x=722, y=696, width=223, height=20)
        self._rebuild_chips()
        self.btn_frame = tk.Frame(c, bg=self.SCREEN_BG)
        self.btn_frame.place(x=974, y=640, width=132, height=68)
        self.progressive_var.trace_add('write', self._update_progressive_display)
        self.add_main_buttons()
        self._refresh_paytable()

    def _text(self, x, y, text, size=12, color=TEXT, **kwargs):
        return self.canvas.create_text(x, y, text=text, fill=color,
            font=('Arial', size, 'bold'), **kwargs)

    def _active_version(self):
        return self.round_version if self.game_in_progress else self.selected_version

    def _main_stake(self):
        bet = self.game.bet_amount if self.game_in_progress else self._selected_bet()
        return bet

    def select_version(self, version):
        if self._closing or self.game_in_progress or self.game.stage != 'betting':
            return
        if version not in VIDEO_POKER_VERSIONS:
            return
        self.selected_version = version
        self._draw_paytable()
        self._refresh_paytable()
        self._refresh_versions()
        # Reopen the manual with the newly selected paytable.
        dialog = getattr(self, '_game_instruction_dialog', None)
        if dialog is not None and dialog.winfo_exists():
            dialog.destroy()
            self._game_instruction_dialog = None

    def _refresh_versions(self):
        active = self._active_version()
        version = VIDEO_POKER_VERSIONS[active]
        for key, button in self.version_buttons.items():
            selected = key == active
            button.config(selected=selected,
                state=tk.DISABLED if self.game_in_progress else tk.NORMAL)
        self.version_feature_card.show_version(version)
        self._update_progressive_display()

    def _draw_paytable(self):
        c = self.canvas
        c.delete('paytable')
        c.create_rectangle(32, 82, 392, 302, fill='#102B29', outline=GOLD, tags='paytable')
        c.create_rectangle(32, 82, 392, 109, fill='#315C40', outline=GOLD, tags='paytable')
        for x, text, anchor in ((44, '牌型', 'w'), (225, '净赔率', 'center'), (380, '本注总返还', 'e')):
            c.create_text(x, 96, text=text, anchor=anchor, fill=PANEL_BG,
                          font=('Arial', 10, 'bold'), tags='paytable')
        self.paytable_items = {}
        payouts = VIDEO_POKER_VERSIONS[self._active_version()]['payouts']
        row_height = 190 / len(payouts)
        row_font = ('Arial', 9 if len(payouts) > 11 else 10, 'bold')
        for row, (category, multiplier) in enumerate(payouts.items()):
            y = 111 + row * row_height
            background = c.create_rectangle(34, y, 390, y + row_height - 1,
                fill='#15382F' if row%2 == 0 else '#102B29', outline='', tags='paytable')
            label = payout_name(category, self._active_version())
            name = c.create_text(44, y + row_height/2, text=label, anchor='w',
                fill='#FFE29A', font=row_font, tags='paytable')
            odds = c.create_text(225, y + row_height/2, text=f'{multiplier}:1',
                fill='#FFE29A', font=row_font, tags='paytable')
            amount = c.create_text(380, y + row_height/2, text='', anchor='e',
                fill='#FFE29A', font=row_font, tags='paytable')
            self.paytable_items[category] = (background, name, odds, amount)
        self._paytable_rank = None

    def _refresh_paytable(self, *args):
        stake = self._main_stake()
        payouts = VIDEO_POKER_VERSIONS[self._active_version()]['payouts']
        for row, (category, items) in enumerate(self.paytable_items.items()):
            self.canvas.itemconfigure(items[-1], text=f'${stake * (payouts[category] + 1):,.0f}')
            active = category == self._paytable_rank
            self.canvas.itemconfigure(items[0], fill='#A77D28' if active else ('#15382F' if row%2 == 0 else '#102B29'))
            for item in items[1:]:
                self.canvas.itemconfigure(item, fill='#10251C' if active else '#FFE29A')

    def _refresh_holds(self):
        if self.double_hand and self.game.stage != 'betting':
            choosing = self.game.stage == 'double_choose'
            for i, button in enumerate(self.hold_buttons):
                self.hold_labels[i].place_forget()
                button.config(text='庄家' if i == 0 else '玩家' if i == self._double_choice else '选择',
                    state=tk.NORMAL if choosing and i > 0 else tk.DISABLED,
                    face=HEADER_BG if i == self._double_choice else '#315C40',
                    fg=TITLE_FG if i == self._double_choice else PANEL_BG)
            return
        enabled = self.game.stage == 'dealt' and not self.buttons_disabled
        for i, button in enumerate(self.hold_buttons):
            held = self.game.hold_status[i]
            button.config(text=f'已保留  HELD {i+1}' if held else f'保留  HOLD {i+1}',
                face=HEADER_BG if held else '#315C40', fg=TITLE_FG if held else PANEL_BG,
                state=tk.NORMAL if enabled else tk.DISABLED)
            self.card_containers[i].config(highlightbackground=GOLD if held else '#607B58')
            if held:
                self.hold_labels[i].place(x=133+i*184, y=351, width=148, height=22)
            else:
                self.hold_labels[i].place_forget()

    def _update_progressive_display(self, *args):
        if not self._progressive_available():
            self._cancel_progressive_motion()
            self.last_progressive_state = 0
            if self.progressive_var.get():
                self.progressive_var.set(0)
            self.canvas.delete('progressive_stake')
            self._progressive_chip_xy = None
            self.lamps['Player'].pop('filled_callback', None)
            self._set_lamp_mode('Player', 'sealed')
            if hasattr(self, 'start_button') and self.game.stage == 'betting':
                self.start_button.config(state=tk.NORMAL)
            return
        if self.game_in_progress or self._progressive_chip_motion:
            return
        participating = bool(self.progressive_var.get())
        self._set_lamp_mode('Player', 'spin' if participating else 'off')
        target = self.bet_spots[('Player', 'jackpot')]['center'] if participating else self.PROGRESSIVE_CHIP_START
        self._move_progressive_chip(target)

    def _progressive_available(self):
        return self._active_version() != 'deuces'

    def _cancel_progressive_motion(self):
        if self._progressive_chip_job is not None:
            self.after_cancel(self._progressive_chip_job)
            self._jobs.discard(self._progressive_chip_job)
            self._progressive_chip_job = None
        self._progressive_chip_motion = False

    def toggle_progressive(self, event=None):
        if self._progressive_available() and not self.game_in_progress and not self._progressive_chip_motion and not self._closing:
            self.progressive_var.set(0 if self.progressive_var.get() else 1)

    def cancel_progressive(self, event=None):
        if self._progressive_available() and not self.game_in_progress and not self._progressive_chip_motion and not self._closing:
            self.progressive_var.set(0)

    def _begin_deal(self):
        if self._closing or self.game.stage != 'progressive':
            return
        self.game.stage = 'dealing'
        self.animation_queue = list(range(5))
        self.animate_deal()

    # ---------- 固定面额筹码 ----------
    def _rebuild_chips(self):
        for widget in self.chip_container.winfo_children():
            widget.destroy()
        self.chip_buttons, self.chip_texts = [], {}
        colors = ('#050505', '#397A48', '#FF7DDA', '#FFFFFF', '#B72828', '#00FBFF')
        for i, (amount, color) in enumerate(zip(self.CHIP_VALUES, colors)):
            chip = tk.Canvas(self.chip_container, width=48, height=48, bg=self.SCREEN_BG,
                             highlightthickness=0, cursor='hand2')
            chip.place(x=i*50, y=6)
            chip.create_oval(1, 1, 47, 47, fill='#182F25', outline='#64785B', tags='rim')
            chip.create_oval(5, 5, 43, 43, fill=color, outline=PANEL_BG)
            label = f'{amount//1000}K' if amount >= 1000 else str(amount)
            chip.create_text(24, 24, text=label, fill=PANEL_BG if i in (0, 1, 4) else BLACK,
                             font=('Arial', 9, 'bold'))
            chip.bind('<Button-1>', lambda _e, value=amount: self.select_chip(value))
            self.chip_buttons.append(chip)
            self.chip_texts[chip] = amount
        self.select_chip(self.selected_chip)

    def _refresh_amount_display(self):
        if self._round_result is not None or self.game.stage == 'settled':
            text = f'本局获胜：${self.last_win:,.2f}'
        else:
            amount = self.game.bet_amount if self.game_in_progress else self._selected_bet()
            text = f'本局下注：${amount:,.2f}'
        self.round_amount_label.config(text=text)

    def _draw_progressive_chip(self, x, y):
        """沿用 cari 的 2.50 筹码：单层金色圆面、黑边、黑字，无货币符号。"""
        if not self._progressive_available():
            return
        c = self.canvas
        tag = 'progressive_stake'
        c.delete(tag)
        radius = self.BET_CHIP_RADIUS
        c.create_oval(x-radius, y-radius, x+radius, y+radius,
                      fill=HEADER_BG, outline=BLACK, width=1, tags=tag)
        self._text(x, y, '2.50', 12, BLACK, tags=tag)
        c.tag_bind(tag, '<Button-1>', self.toggle_progressive)
        c.tag_bind(tag, '<Button-3>', self.cancel_progressive)
        self._progressive_chip_xy = (x, y)

    def _move_progressive_chip(self, target, complete=None, duration=None):
        """从现有位置平滑移动；下注时入灯，取消时退回，跑满后收走。"""
        if self._closing or not self._progressive_available() or self._progressive_chip_motion:
            return
        if self._progressive_chip_xy is None:
            self._draw_progressive_chip(*self.PROGRESSIVE_CHIP_START)
        start = self._progressive_chip_xy
        if start == target:
            if complete:
                complete()
            return
        duration = self.PROGRESSIVE_CHIP_MS if duration is None else duration
        steps = max(1, round(duration/16))
        self._progressive_chip_motion = True
        if hasattr(self, 'start_button') and self.game.stage == 'betting':
            self.start_button.config(state=tk.DISABLED)
        last = list(start)
        def frame(index):
            self._progressive_chip_job = None
            if self._closing:
                self._progressive_chip_motion = False
                return
            fraction = index/steps
            eased = fraction*fraction*(3-2*fraction)
            x = start[0] + (target[0]-start[0])*eased
            y = start[1] + (target[1]-start[1])*eased
            self.canvas.move('progressive_stake', x-last[0], y-last[1])
            self.canvas.tag_raise('progressive_stake')
            self._progressive_chip_xy = (x, y)
            last[:] = [x, y]
            if index < steps:
                delay = round(duration*(index+1)/steps)-round(duration*index/steps)
                self._progressive_chip_job = self._schedule(delay, lambda: frame(index+1))
            else:
                self._progressive_chip_motion = False
                if complete:
                    complete()
                elif self.game.stage == 'betting':
                    self.start_button.config(state=tk.NORMAL)
        self._progressive_chip_job = self._schedule(round(duration/steps), lambda: frame(1))

    def _collect_progressive_chip(self):
        """灯环跑满才收筹码，收完后进入开牌。"""
        if self._closing or self.game.stage != 'progressive':
            return
        def collected():
            self.canvas.delete('progressive_stake')
            self._progressive_chip_xy = None
            self._begin_deal()
        self._move_progressive_chip(self.HOUSE_CHIP_POS, collected, duration=280)

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
        c.tag_bind(tag,'<Button-1>',self.toggle_progressive)
        c.tag_bind(tag,'<Button-3>',self.cancel_progressive)
        c.tag_bind(tag,'<Enter>',lambda _e:c.configure(cursor='hand2' if self._progressive_available() else ''))
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
        c.delete('progressive_seal')
        if mode == 'sealed':
            c.itemconfigure(lamp['body'], fill='#3C4942', outline='#738477')
            c.itemconfigure(lamp['center'], fill='#172D25', outline='#566D5C')
            for item in lamp['segments']:
                c.itemconfigure(item, outline='#59695C')
            cx, cy = self.bet_spots[(seat, 'jackpot')]['center']
            for start, end in ((-1, 1), (1, -1)):
                c.create_line(cx-34, cy+34*start, cx+34, cy+34*end,
                              fill='#87917B', width=6, tags='progressive_seal')
                c.create_line(cx-34, cy+34*start, cx+34, cy+34*end,
                              fill='#3C4942', width=2, tags='progressive_seal')
            c.create_oval(cx-26, cy-18, cx+26, cy+18, fill='#243A2D',
                          outline='#D8BC70', width=2, tags='progressive_seal')
            c.create_text(cx, cy, text='封印', fill='#E7CE88',
                          font=(self.cn_font, 13, 'bold'), tags='progressive_seal')
            c.create_text(cx, cy+65, text='本模式不可下注', fill='#B5C0AA',
                          font=(self.cn_font, 10), tags='progressive_seal')
            return
        c.itemconfigure(lamp['body'], outline='#CD4550')
        c.itemconfigure(lamp['center'], outline='#781F28')
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

        dialog.title('视频扑克 · 完整图解玩法')

        dialog.configure(bg='#faf5e8')

        dialog.resizable(False, False)

        dialog.transient(parent)



        width, height = 1000, 670

        parent.update_idletasks()

        px, py = parent.winfo_rootx(), parent.winfo_rooty()

        pw, ph = max(1, parent.winfo_width()), max(1, parent.winfo_height())

        dialog.geometry(f'{width}x{height}+{px + (pw-width)//2}+{py + (ph-height)//2}')



        version_key = self._active_version()
        version = VIDEO_POKER_VERSIONS[version_key]
        manual_pages = build_video_poker_instructions(version_key)
        dialog.title(f"视频扑克 · {version['name']}玩法说明")

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

        tk.Label(header, text=f"视频扑克 · {version['name']}玩法说明", font=(font_name, 20, 'bold'),

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

                text_width = max((table_font.measure(line)

                                  for row in ([headers] if headers else []) + rows

                                  if col < len(row) and isinstance(row[col], str)

                                  for line in row[col].splitlines()), default=0)

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
                            photo = self._card_photo(Card(suit, rank), (70, 98), version=version_key)
                            image_label = tk.Label(image_cell, image=photo, bg=bg, bd=0)
                            image_label.image = photo
                            image_label.pack(side=tk.LEFT, padx=2, pady=3)

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

        self._schedule(30, lambda: dialog.focus_force() if dialog.winfo_exists() else None)
    # ---------- 更新余额 ----------
    def update_balance(self):
        self.balance_label.config(text=f"余额：${self.balance:,.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)

    # ---------- 辅助：获取牌型显示名称 ----------
    def get_hand_display_name(self, cards):
        category = evaluate_video_poker_hand(cards, self._active_version())
        if category:
            return payout_name(category, self._active_version())
        counts = Counter(c.value for c in cards)
        pairs = [v for v, n in counts.items() if n == 2]
        if len(pairs) == 2:
            return '两对'
        if pairs:
            return f'对子({RANKS[max(pairs)-2]})'
        if self._active_version() == 'deuces' and any(c.rank == '2' for c in cards):
            return f'对子({RANKS[max(counts)-2]})'
        return '高牌'

    # ---------- 切换保留 ----------
    def toggle_hold(self, idx):
        if self.game.stage != 'dealt' or self.buttons_disabled or not 0 <= idx < 5:
            return
        self.game.hold_status[idx] = not self.game.hold_status[idx]
        self._refresh_holds()

    # ---------- 开始游戏 ----------
    def start_game(self):
        if self.game_in_progress or self._progressive_chip_motion or self._closing:
            return
        bet = self._selected_bet()
        prog_active = self._progressive_available() and bool(self.progressive_var.get())
        if self.balance < bet + (2.5 if prog_active else 0):
            messagebox.showerror('错误', '余额不足', parent=self)
            return
        # Lock the version before preparing the deck; debit only after success.
        self.game_in_progress = True
        self.buttons_disabled = True
        self.round_version = self.selected_version
        self.pending_win = 0
        self._round_result = None
        self._round_finalized = False
        self.double_hand = []
        self.double_rounds = []
        self._double_choice = None
        self.game.reset_game(self.round_version)
        self.game.bet_amount = bet
        self.game.stage = 'preparing'
        self.round_progressive_active = prog_active
        self.start_button.config(state=tk.DISABLED)
        self._refresh_versions()
        self._refresh_risk_buttons()
        try:
            self.game.deal_initial()
        except Exception:
            self._deal_failed()
            return
        self._commit_initial_deal()

    def _deal_failed(self):
        self.game_in_progress = False
        self.buttons_disabled = False
        self.game.stage = 'betting'
        self.add_main_buttons()
        self._refresh_versions()
        messagebox.showerror('无法开牌', '本局尚未扣款，请重新开牌。', parent=self)

    def _commit_initial_deal(self):
        if self._closing or self.game.stage != 'preparing':
            return
        total_required = self.game.bet_amount + (2.5 if self.round_progressive_active else 0)
        self.last_progressive_state = int(self.round_progressive_active)
        self.balance -= total_required
        self.update_balance()
        self.game.stage = 'progressive'
        self._paytable_rank = None
        self.player_label.config(text='')
        self._refresh_amount_display()
        self.initial_hand = [Card(c.suit, c.rank) for c in self.game.player_hand]
        for thumbnail in self.initial_thumbnails:
            thumbnail.config(image=self.thumb_back)
            thumbnail.image = self.thumb_back
        for label in self.bottom_labels:
            label.config(image=self.back_image)
        self.add_draw_button()
        self._refresh_holds()
        self._refresh_paytable()
        if self.round_progressive_active:
            self.lamps['Player']['filled_callback'] = self._collect_progressive_chip
            self._set_lamp_mode('Player', 'fill')
        else:
            self._set_lamp_mode('Player', 'off' if self._progressive_available() else 'sealed')
            self._begin_deal()

    # ---------- 发牌动画 ----------
    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            self._schedule(500, self.reveal_player_cards)
            return
        self.animation_in_progress = True
        idx = self.animation_queue.pop(0)
        card = self.game.player_hand[idx]
        self.bottom_labels[idx].config(image=self._card_photo(card))
        self._schedule(200, self.animate_deal)

    def reveal_player_cards(self):
        if self.game.stage != 'dealing':
            return
        # 成牌保留五张；三条只保留组成三条的三张，仍可逐张手动取消。
        self.game.hold_status = automatic_hold_mask(self.initial_hand, self.round_version)
        self.update_hand_label()
        self.game.stage = "dealt"
        self._refresh_versions()
        self.draw_button.config(state=tk.NORMAL)
        self.buttons_disabled = False
        self._refresh_holds()

        # 首次开牌结束，更新“原始手牌”缩略图
        small_size = self.THUMB_SIZE
        for i, card in enumerate(self.initial_hand):
            if (card.suit, card.rank) in self.original_images:
                photo = self._card_photo(card, small_size, version=self.round_version)
                self.initial_thumbnails[i].config(image=photo)
                self.initial_thumbnails[i].image = photo
            else:
                img = Image.new('RGB', small_size, 'blue')
                draw = ImageDraw.Draw(img)
                draw.text((10,10), f"{card.rank}{card.suit}", fill='white')
                photo = ImageTk.PhotoImage(img)
                self.initial_thumbnails[i].config(image=photo)
                self.initial_thumbnails[i].image = photo

    def update_hand_label(self):
        if self.game.player_hand:
            display_name = self.get_hand_display_name(self.game.player_hand)
            self.player_label.config(text=display_name)
            category = evaluate_video_poker_hand(self.game.player_hand, self._active_version())
            self._paytable_rank = category or None
            self._refresh_paytable()
        else:
            self.player_label.config(text='')

    # ---------- 抽牌（带逐张动画） ----------
    def draw_action(self):
        if self.game.stage != 'dealt' or self.buttons_disabled or self._closing:
            return
        # ----- 修改点：禁用扑克牌点击 -----
        self.buttons_disabled = True
        self.game.stage = 'drawing'
        self._refresh_versions()
        self._refresh_holds()
        # --------------------------------
        self.draw_button.config(state=tk.DISABLED)
        self.player_label.config(text='')

        for i in range(5):
            if not self.game.hold_status[i]:
                self.bottom_labels[i].config(image=self.grey_back)

        self.game.draw_cards()
        self.animation_queue = [i for i in range(5) if not self.game.hold_status[i]]
        if not self.animation_queue:
            self._schedule(500, self.show_showdown)
        else:
            self.animate_draw()

    def animate_draw(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            self._schedule(500, self.show_showdown)
            return
        self.animation_in_progress = True
        idx = self.animation_queue.pop(0)
        card = self.game.player_hand[idx]
        self.bottom_labels[idx].config(image=self._card_photo(card))
        self._schedule(200, self.animate_draw)

    def update_progressive_pool(self):
        """每局结束后，根据下注金额增加奖池贡献"""
        bet = self.game.bet_amount          # 主注
        prog_active = self.round_progressive_active
        prog_bet = 2.5 if prog_active else 0
        total_bet = bet + prog_bet
        # 贡献 = 总下注的0.1% + 累进下注的95%
        contribution = total_bet * 0.001 + prog_bet * 0.95
        self.progressive_amount += contribution
        if self.progressive_amount < self.min_progressive:
            self.progressive_amount = self.min_progressive
        save_progressive(self.progressive_amount)
        self.progressive_amount_var.set(f"${self.progressive_amount:,.2f}")

    # ---------- 结算 ----------
    def show_showdown(self):
        if self.game.stage != 'drawing' or self._closing:
            return
        self.game.stage = 'reward'
        self.animation_in_progress = False
        display_name = self.get_hand_display_name(self.game.player_hand)
        self.player_label.config(text=display_name)
        rank, _ = evaluate_five_card_hand(self.game.player_hand)
        category = evaluate_video_poker_hand(self.game.player_hand, self.round_version)
        self._paytable_rank = category or None
        self._refresh_paytable()
        main_win = self.calculate_winnings()
        progressive_win = round_currency(self.calculate_progressive_win()) if self.round_progressive_active else 0
        self._round_result = {
            'hand': [Card(c.suit, c.rank) for c in self.game.player_hand],
            'rank': rank, 'category': category, 'name': display_name,
            'main_win': main_win, 'progressive_win': progressive_win,
        }
        # The progressive award is banked now and never enters the double-up stake.
        self.pending_win = round_currency(main_win)
        self.last_win = round_currency(main_win + progressive_win)
        if progressive_win > 0:
            self.balance = round_currency(self.balance + progressive_win)
            self.update_balance()
            self._set_lamp_mode('Player', 'win')
        self.update_progressive_pool()
        self._refresh_amount_display()
        self._refresh_holds()
        self._refresh_risk_buttons()
        self.start_button.config(text='再来一局\nNEXT HAND', command=self.reset_game, state=tk.NORMAL)
        # A positive award waits for the player's collect/double decision.
        if self.pending_win <= 0:
            self._settle_round(0, 'progressive_only' if progressive_win > 0 else 'no_win')

    def calculate_winnings(self):
        category = evaluate_video_poker_hand(self.game.player_hand, self.round_version)
        odds = VIDEO_POKER_VERSIONS[self.round_version]['payouts'].get(category, 0)
        return self.game.bet_amount * (odds + 1) if odds > 0 else 0

    def _refresh_risk_buttons(self):
        if not hasattr(self, 'double_button'):
            return
        can_double = (not self._closing and not self._round_finalized
                      and self.game.stage in ('reward', 'double_ready') and self.pending_win > 0)
        can_exit = (not self._closing and not self._round_finalized
                    and self.game.stage in self.DOUBLE_STAGES)
        self.double_button.config(state=tk.NORMAL if can_double else tk.DISABLED)
        self.exit_button.config(state=tk.NORMAL if can_exit else tk.DISABLED)

    def on_card_click(self, index):
        if self.game.stage == 'double_choose':
            self.choose_double_card(index)
        else:
            self.toggle_hold(index)

    def start_double(self):
        if (self._closing or self._round_finalized or self.pending_win <= 0
                or self.game.stage not in ('reward', 'double_ready')):
            return
        try:
            cards = deal_double_hand()
            if len(cards) != 5 or len({c.value for c in cards}) != 5 or any(c.suit != '♥' for c in cards):
                raise ValueError('Invalid double hand')
            if not 3 <= cards[0].value <= 13 or not min(c.value for c in cards[1:]) < cards[0].value < max(c.value for c in cards[1:]):
                raise ValueError('Invalid dealer or comparison choices')
        except Exception:
            messagebox.showerror('无法翻倍', '未开始翻倍，奖金仍可全额领取。', parent=self)
            return
        self.game.stage = 'double_dealing'
        self.last_win = self.pending_win
        self.double_hand = cards
        self._double_choice = None
        self.buttons_disabled = True
        self.double_rounds.append({
            'stake': self.pending_win, 'cards': [str(c) for c in cards],
            'dealer_rank': cards[0].rank, 'dealer_opened': False,
            'selected_index': None, 'outcome': 'pending',
        })
        for i, label in enumerate(self.bottom_labels):
            label.config(image=self.back_image, bg=self.SCREEN_BG)
            self.card_containers[i].config(bg=self.SCREEN_BG, highlightbackground='#607B58')
        self.player_label.config(text='')
        self._refresh_amount_display()
        self._refresh_holds()
        self._refresh_risk_buttons()
        self.start_button.config(state=tk.DISABLED)
        self._double_job = self._schedule(220, self._reveal_double_dealer)

    def _reveal_double_dealer(self):
        self._double_job = None
        if self._closing or self.game.stage != 'double_dealing':
            return
        self.game.stage = 'double_choose'
        self.double_rounds[-1]['dealer_opened'] = True
        dealer = self.double_hand[0]
        self.bottom_labels[0].config(image=self.card_images[('♥', dealer.rank)], bg='#A32635')
        self.card_containers[0].config(bg='#A32635', highlightbackground='#F46C73')
        self.player_label.config(text=f'庄家是{dealer.rank}，请选择 1 张')
        self._refresh_holds()
        self._refresh_risk_buttons()

    def choose_double_card(self, index):
        if (self._closing or self._round_finalized or self.game.stage != 'double_choose'
                or not isinstance(index, int) or not 1 <= index <= 4):
            return
        # Lock before painting so a second click cannot resolve the same bet again.
        self.game.stage = 'double_ready'
        self._double_choice = index
        dealer, player = self.double_hand[0], self.double_hand[index]
        record = self.double_rounds[-1]
        record['selected_index'] = index
        record['player_rank'] = player.rank
        won = player.value > dealer.value
        self.game.stage = 'double_ready' if won else 'double_lost'
        self.pending_win = self.last_win = round_currency(record['stake'] * 2) if won else 0
        record.update(outcome='win' if won else 'lose', return_amount=self.pending_win)
        for i, card in enumerate(self.double_hand):
            self.bottom_labels[i].config(image=self.card_images[('♥', card.rank)],
                bg='#A32635' if i == 0 else self.SCREEN_BG)
            self.card_containers[i].config(bg='#A32635' if i == 0 else self.SCREEN_BG,
                highlightbackground='#F46C73' if i == 0 else GOLD if i == index else '#607B58')
        self.player_label.config(text=f'庄家是{dealer.rank}，您选择了 {player.rank}，您赢了！继续吗？'
                                 if won else f'庄家是{dealer.rank}，您选择了 {player.rank}，下局加油')
        self._refresh_amount_display()
        self._refresh_holds()
        self._refresh_risk_buttons()
        self.start_button.config(state=tk.NORMAL if won else tk.DISABLED)
        if not won:
            self._double_exit_job = self._schedule(2500, self._auto_exit_double)

    def _auto_exit_double(self):
        self._double_exit_job = None
        if self.game.stage == 'double_lost' and not self._closing:
            self.cash_out_round()

    def cash_out_round(self):
        """Only the active double screen exposes an exit/collect action."""
        if self._closing or self._round_finalized or self.game.stage not in self.DOUBLE_STAGES:
            return
        self._collect_pending_win()

    def _collect_pending_win(self, render=True):
        if self._round_result is None or self._round_finalized:
            return
        opened = self.game.stage == 'double_choose'
        amount = round_currency(self.pending_win / 2) if opened else self.pending_win
        reason = ('double_lose' if self.game.stage == 'double_lost' else
                  'exit_after_open' if opened else
                  'exit_before_open' if self.game.stage == 'double_dealing' else 'collect_win')
        if self.game.stage in ('double_dealing', 'double_choose'):
            self.double_rounds[-1].update(outcome=reason, return_amount=amount)
        self._settle_round(amount, reason, render=render)

    def _settle_round(self, amount, reason, render=True):
        """Credit the final award and write exactly one history row for the main hand."""
        if self._round_result is None or self._round_finalized:
            return
        result = self._round_result
        if self._double_job is not None:
            self.after_cancel(self._double_job)
            self._jobs.discard(self._double_job)
            self._double_job = None
        if self._double_exit_job is not None:
            self.after_cancel(self._double_exit_job)
            self._jobs.discard(self._double_exit_job)
            self._double_exit_job = None
        self._round_finalized = True
        self.game.stage = 'settled'
        # Progressive was already paid in show_showdown; only credit the main award.
        self.last_win = round_currency(amount + result['progressive_win'])
        self.pending_win = 0
        self.balance = round_currency(self.balance + amount)
        if render:
            self.update_balance()
        elif self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)
        save_video_poker_history(
            deck=self.game.deck, ori_cards=self.initial_hand, aft_cards=result['hand'],
            bet=self.game.bet_amount, win_amount=self.last_win,
            hand_rank=result['rank'], hand_name=result['name'], is_win=self.last_win > 0,
            version=self.round_version, payout_category=result['category'],
            main_win=result['main_win'], progressive_win=result['progressive_win'],
            double_rounds=self.double_rounds, cashout_reason=reason,
        )
        if render:
            if self.double_hand:
                self.double_hand = []
                self._double_choice = None
                for i, card in enumerate(result['hand']):
                    self.bottom_labels[i].config(image=self._card_photo(card), bg=self.SCREEN_BG)
                    self.card_containers[i].config(bg=self.SCREEN_BG, highlightbackground='#607B58')
                self.player_label.config(text=result['name'])
            self._refresh_amount_display()
            self._refresh_holds()
            self._refresh_risk_buttons()
            self.start_button.config(text='再来一局\nNEXT HAND', command=self.reset_game, state=tk.NORMAL)

    # ---------- 累进大奖计算 ----------
    def calculate_progressive_win(self):
        """基于原始手牌（self.initial_hand）计算累进大奖赢额，并更新奖池"""
        if not self._progressive_available():
            return 0
        if not self.initial_hand or len(self.initial_hand) != 5:
            return 0
        rank, _ = evaluate_five_card_hand(self.initial_hand)
        # 修改后的赔付映射（仅保留指定牌型）
        payout_map = {
            9: ('jackpot', 1.0),      # 皇家同花顺：奖池100%
            8: ('jackpot', 0.1),      # 同花顺：奖池10%
            7: ('fixed', 1250),       # 四条：$1250
            6: ('fixed', 375),        # 葫芦：$375
            5: ('fixed', 250)         # 同花：$250
        }
        if rank not in payout_map:
            return 0
        mode, value = payout_map[rank]
        if mode == 'jackpot':
            win_amount = self.progressive_amount * value
        else:
            win_amount = value

        if win_amount <= 0:
            return 0

        # 从奖池扣除
        self.progressive_amount -= win_amount
        if self.progressive_amount < self.min_progressive:
            self.progressive_amount = self.min_progressive
        save_progressive(self.progressive_amount)
        self.progressive_amount_var.set(f"${self.progressive_amount:,.2f}")

        # 显示中奖消息
        hand_name = HAND_RANK_NAMES.get(rank, "未知牌型")
        if mode == 'jackpot':
            msg = f"原始手牌{hand_name}！赢得奖池的{int(value*100)}%：${win_amount:,.2f}"
        else:
            msg = f"原始手牌{hand_name}！赢得${win_amount:,.2f}"
        # 中奖由参与灯闪烁和主界面金额显示，不弹出阻塞动画的对话框。
        return win_amount

    # ---------- 重置游戏 ----------
    def reset_game(self, auto_reset=False):
        if self.game.stage not in ('betting', 'settled', 'reward', 'double_ready') or self._progressive_chip_motion or self._closing:
            return
        if self._round_result is not None and not self._round_finalized:
            self._collect_pending_win()
        self._load_assets()
        for label in self.bottom_labels:
            label.config(image=self.back_image)
        for label in self.initial_thumbnails:
            label.config(image=self.thumb_back)
            label.image = self.thumb_back
        self.initial_hand = []
        self.pending_win = 0
        self._round_result = None
        self._round_finalized = False
        self.double_hand = []
        self.double_rounds = []
        self._double_choice = None
        for container in self.card_containers:
            container.config(bg=self.SCREEN_BG, highlightbackground='#607B58')
        for label in self.bottom_labels:
            label.config(bg=self.SCREEN_BG)
        self.game.reset_game(self.selected_version)
        self.game_in_progress = False
        self.buttons_disabled = False
        self._refresh_versions()
        self._paytable_rank = None
        self.player_label.config(text='')
        # 筹码保持当前选择；大奖选择自动沿用上一局，开始发牌时才扣款。
        self.select_chip(self.selected_chip)
        self._draw_progressive_chip(*self.PROGRESSIVE_CHIP_START)
        self.progressive_var.set(self.last_progressive_state)
        self.progressive_display.config(bg='#123C30')
        self.add_main_buttons()
        self._refresh_holds()

    def disable_action_buttons(self):
        self.buttons_disabled = True
        for widget in self.btn_frame.winfo_children():
            if isinstance(widget, (tk.Button, MachineButton)):
                widget.config(state=tk.DISABLED)

# ========================== 主入口 ==========================
def main(initial_balance=10000, username="Guest", *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """嵌入现有 Tk 根窗口；未传 parent 时仍可独立运行。"""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return VideoPokerGUI(
            parent, actual_balance, actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("视频扑克")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = VideoPokerGUI(root, actual_balance, actual_user)
    page.pack(fill="both", expand=True)

    root.protocol("WM_DELETE_WINDOW", page.on_close)
    root.mainloop()
    return page.balance


if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")
