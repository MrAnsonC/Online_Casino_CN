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
    5: '顺子', 4: '三条', 3: '两对', 2: '对子JACK或以上', 1: '对子6到10', 0: '高牌'
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
        pass
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
# 历史记录（Mississippi_Stud_Poker.json）
# =========================================================
def mississippi_log_path() -> str:
    """返回日志文件路径"""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Mississippi_Stud_Poker.json")

def save_mississippi_history(deck, comm_cards, player_cards, win_amount, hand_rank, hand_name, result_status, fold, *, seat=None, round_id=None, bets=None):
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
    if seat is not None:
        record.update(seat=seat, round_id=round_id, bets=dict(bets or {}))
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
class MississippiStudTableGame:
    """两手独立决策，共用公共牌；赔率沿用原 Mississippi 程序。"""
    SEATS = ('Player1', 'Player2')
    MAIN_KINDS = ('ante', 'street3', 'street4', 'street5')
    MIN_PROGRESSIVE = 271288.59

    def __init__(self):
        self.progressive_amount = load_jackpot()[1]
        self.min_progressive = self.MIN_PROGRESSIVE
        self.reset_game()

    @staticmethod
    def empty_bet():
        return dict(ante=0.0, bonus3=0.0, jackpot=0.0,
                    street3=0.0, street4=0.0, street5=0.0)

    def reset_game(self):
        self.deck = None
        self.hands = {seat: [] for seat in self.SEATS}
        self.community_cards = []
        self.community_revealed = 0
        self.deal_sequence = []
        self.bets = {seat: self.empty_bet() for seat in self.SEATS}
        self.decisions = {seat: 'inactive' for seat in self.SEATS}
        self.refunded_bets = {}
        self.stage = 'betting'
        self.settlement = None

    def start_round(self, bets, balance, high_bet_mode=False):
        if self.stage != 'betting':
            raise ValueError('本局尚未结束。')
        minimum, maximum, side_max = ((100, 50000, 12500) if high_bet_mode
                                      else (10, 10000, 2500))
        prepared, refunded = {}, {}
        for seat in self.SEATS:
            b = {k: float(bets[seat].get(k, 0)) for k in self.empty_bet()}
            if any(not math.isfinite(v) or v < 0 for v in b.values()):
                raise ValueError('下注金额必须是有限的非负数。')
            if any(b[k] for k in ('street3', 'street4', 'street5')):
                raise ValueError('三街、四街、五街须在发牌后逐街下注。')
            if not b['ante']:
                if any(b.values()):
                    refunded[seat] = dict(b)
                prepared[seat] = self.empty_bet()
                continue
            if not minimum <= b['ante'] <= maximum:
                raise ValueError(f'每手前注须为 ${minimum:,} 至 ${maximum:,}。')
            if b['bonus3'] > side_max or b['jackpot'] not in (0, 2.5):
                raise ValueError('边注超出限额，累进大奖每手固定 $2.50。')
            prepared[seat] = b
        active = tuple(s for s in self.SEATS if prepared[s]['ante'])
        if not active:
            raise ValueError('请至少为一手牌下前注。')
        charged = round(sum(sum(b.values()) for b in prepared.values()), 2)
        reserve = 3 * sum(b['ante'] for b in prepared.values())
        if not math.isfinite(balance) or charged + reserve > balance:
            raise ValueError(f'余额不足，含三街最低加注须预留 ${charged+reserve:,.2f}。')
        # 洗牌和发牌成功后才提交状态；GUI 随后一次性扣款。
        deck = Deck()
        hands = {s: [] for s in self.SEATS}
        # 实际取牌与动画共用次序；未参与的一家既不取牌，也不留下空节拍。
        sequence = []
        for index in range(3):
            sequence.append(('Community', index))
            if index < 2:
                sequence.extend((seat, index) for seat in active)
        community = []
        for side, _ in sequence:
            target = community if side == 'Community' else hands[side]
            target.extend(deck.deal(1))
        self.deck, self.hands, self.community_cards = deck, hands, community
        self.bets, self.refunded_bets, self.deal_sequence = prepared, refunded, sequence
        self.decisions = {s: 'pending' if s in active else 'inactive' for s in self.SEATS}
        self.stage = 'dealing'
        return charged

    def decision_requirement(self, seat, multiplier):
        if (self.stage not in ('street3', 'street4', 'street5')
                or self.decisions.get(seat) != 'pending' or multiplier not in (1, 2, 3)):
            return float('inf')
        remaining = 5 - int(self.stage[-1])
        active = [s for s in self.SEATS if self.decisions[s] not in ('fold', 'inactive')]
        reserve = remaining * sum(self.bets[s]['ante'] for s in active)
        reserve += sum(self.bets[s]['ante'] for s in active
                       if s != seat and self.decisions[s] == 'pending')
        return self.bets[seat]['ante'] * multiplier + reserve

    def decide(self, seat, action, balance):
        if (self.stage not in ('street3', 'street4', 'street5')
                or self.decisions.get(seat) != 'pending'):
            return 0.0
        if action == 'fold':
            self.decisions[seat] = 'fold'
            return 0.0
        if isinstance(action, bool) or action not in (1, 2, 3):
            raise ValueError('请选择 1X、2X、3X 或弃牌。')
        if not math.isfinite(balance) or self.decision_requirement(seat, action) > balance:
            raise ValueError('余额不足以支付本次加注及两手后续街的最低加注。')
        cost = self.bets[seat]['ante'] * action
        self.bets[seat][self.stage] = cost
        self.decisions[seat] = 'bet'
        return cost

    def settle(self):
        if self.settlement is not None:
            return self.settlement
        if self.stage != 'showdown' or 'pending' in self.decisions.values():
            raise ValueError('全部手牌完成决定并翻开公共牌后才能结算。')
        outcomes = {}
        bonus3_rank = evaluate_3card_hand(self.community_cards)
        jackpot_snapshot = self.progressive_amount
        for seat in self.SEATS:
            if self.decisions[seat] == 'inactive':
                continue
            b = self.bets[seat]
            rank = evaluate_hand(self.hands[seat] + self.community_cards)[0]
            folded = self.decisions[seat] == 'fold'
            details = {k: 0.0 for k in (*self.MAIN_KINDS, 'bonus3', 'bonus')}
            payout = MAIN_BET_PAYOUT.get(rank, -1)
            if not folded and payout >= 0:
                for kind in self.MAIN_KINDS:
                    details[kind] = round(b[kind] * (1 + payout), 2)
            if bonus3_rank in BONUS3_PAYOUT:
                details['bonus3'] = round(b['bonus3'] * (1 + BONUS3_PAYOUT[bonus3_rank]), 2)
            # 与原版一致：弃牌不取消公牌加注及累进大奖资格。
            if b['jackpot']:
                details['bonus'] = round({
                    10: max(jackpot_snapshot, 10000.0),
                    9: max(jackpot_snapshot * .1, 1000.0),
                    8: 1250.0, 7: 375.0, 6: 250.0,
                }.get(rank, 0.0), 2)
            status = 'Fold' if folded else 'Win' if rank >= 2 else 'Push' if rank == 1 else 'Lose'
            returned = round(sum(details.values()), 2)
            outcomes[seat] = dict(rank=rank, winner=status, details=details,
                                  returned=returned, stake=round(sum(b.values()), 2),
                                  net=round(returned-sum(b.values()), 2))
        awards = sum(o['details']['bonus'] for o in outcomes.values())
        contribution = sum(sum(b[k] for k in (*self.MAIN_KINDS, 'bonus3')) * .001
                           + b['jackpot'] * .95 for b in self.bets.values())
        self.progressive_amount = round(max(self.MIN_PROGRESSIVE, jackpot_snapshot-awards)
                                        + contribution, 2)
        self.stage = 'settled'
        self.settlement = dict(hands=outcomes,
                               returned=round(sum(o['returned'] for o in outcomes.values()), 2))
        return self.settlement


class MississippiStudGUI(tk.Frame):
    WIDTH, HEIGHT = 1150, 750
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    DEAL_CARD_MS = 224 / .85
    DEAL_MOVE_MS = (128 / .75) / .85
    BET_CHIP_RADIUS = 16 * 4 / 3
    HOUSE_CHIP_POS = (575, 43)
    TABLE_GREEN = '#4b1e22'
    PROGRESSIVE_LAMP_WIDTH = 122.0 * .8
    ZONE_COLORS = {'Player1': '#35634B', 'Player2': '#204536'}
    SEAT_NAMES = {'Player1': '玩家1', 'Player2': '玩家2', 'Community': '公共牌'}
    STREET_NAMES = {'street3': '第三街', 'street4': '第四街', 'street5': '第五街'}

    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = username, float(initial_balance)
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game = MississippiStudTableGame()
        self.bets = {s: self.game.empty_bet() for s in self.game.SEATS}
        self.last_bet = None
        self.last_win = 0.0
        self.high_bet_mode = False
        self.selected_chip = 10.0
        self._jobs = set()
        self._closing = self._credited = self._return_persisted = self._crediting = False
        self._restart_job = self._restart_deadline = None
        self._motion_count = self._chip_serial = 0
        self._decision_busy = self._settlement_started = False
        self.visual_chips, self.lamps = {}, {}
        self.push_notices = {}
        self.last_round_snapshot = None
        self._history_available = False
        self._face_photos, self._pil_cards, self._flip_photos = {}, {}, {}
        self.card_items, self.bet_spots, self.action_buttons = {}, {}, {}
        self._load_assets()
        self._create_widgets()
        self._refresh()
        self.bind('<Destroy>', self._on_destroy, add='+')


    @property
    def game_in_progress(self):
        return self.game.stage != 'betting' or self._motion_count > 0


    def _create_widgets(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=ROOT_BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.control_buttons = {}
        c = self.canvas
        self._text(575, 18, '密西西比梭哈扑克  MISSISSIPPI STUD POKER', 16, GOLD)
        c.create_polygon(
            369, 44, 781, 44,
            795, 44, 795, 58,
            795, 183, 795, 197,
            781, 197, 369, 197,
            355, 197, 355, 183,
            355, 58, 355, 44,
            smooth=True, splinesteps=16, fill='#234838',
            outline='#667B55', width=1)
        self.title_items = {'Community': self._text(575, 57, '公共牌', 16, PANEL_BG)}
        for seat, x0, x1 in (('Player1', 22, 566), ('Player2', 582, 1128)):
            c.create_rectangle(x0, 230, x1, 617, fill=self.ZONE_COLORS[seat], outline='')
            self.title_items[seat] = self._text((x0+x1)/2, 244, self.SEAT_NAMES[seat], 16, PANEL_BG)
        self._draw_limit_table()
        self._draw_progressive_panel()
        c.create_rectangle(22, 200, 1128, 226, fill='#173C2E', outline='#65784B', width=1)
        c.create_line(25, 201, 1125, 201, fill='#E0C879', width=2)
        c.create_line(25, 225, 1125, 225, fill='#0C241B', width=2)
        self._text(575, 213, '对子5或以下输  •  对子6到10平局  •  对子JACK或以上赢', 13, GOLD)
        for seat, x0, x1 in (('Player1', 22, 566), ('Player2', 582, 1128)):
            # 灯位于手牌左侧；上排下注圈对齐下排相邻两街的中点。
            self._draw_progressive_lamp(seat, x0+90, 322)
            self._draw_spot(seat, 'ante', x0+133, 446, '前注')
            self._draw_spot(seat, 'bonus3', x0+259, 446, '公牌加注')
            for kind, dx, label in (('street3', 70, '第三街'),
                                    ('street4', 196, '第四街'),
                                    ('street5', 322, '第五街')):
                self._draw_spot(seat, kind, x0+dx, 558, label)
            # 1倍 / 弃牌沿用 Caribbean 原坐标；3倍、2倍逐级排列在 1倍上方。
            left, right = x0+410, x1-15
            for multiplier, top in ((3, 281), (2, 350)):
                self.action_buttons[(seat, multiplier)] = self.create_control_button(
                    left, top, right, top+58, f'下注{multiplier}倍',
                    lambda s=seat, m=multiplier: self.place_street_bet(m, s),
                    '#397A48', font_size=14, draw_shadow=False)
            self.action_buttons[(seat, 1)] = self.create_control_button(
                left, 419, right, 477, '下注1倍', lambda s=seat: self.place_street_bet(1, s),
                '#397A48', font_size=14, draw_shadow=False)
            self.action_buttons[(seat, 'fold')] = self.create_control_button(
                left, 488, right, 546, '弃牌', lambda s=seat: self.fold_action(s),
                '#9B403A', font_size=14, draw_shadow=False)
        self._draw_bottom_controls()
        for side in ('Community', *self.game.SEATS):
            for index in range(3 if side == 'Community' else 2):
                x, y = self.card_position(side, index)
                c.create_rectangle(x, y, x+self.CARD_WIDTH, y+self.CARD_HEIGHT,
                    outline='#7B9374', dash=(3, 3), tags='card_slots')


    def _draw_spot(self, seat, kind, cx, cy, label):
        c, tag = self.canvas, 'spot_'+seat+'_'+kind
        radius = 50
        if kind == 'bonus3':
            # 四个等距顶点构成旋转 45 度的正方形，以紫色区分公牌边注。
            border = c.create_polygon(cx, cy-radius, cx+radius, cy, cx, cy+radius, cx-radius, cy,
                fill='#58366B', outline='#C29ADD', width=3, tags=tag)
            inner = radius-5
            c.create_polygon(cx, cy-inner, cx+inner, cy, cx, cy+inner, cx-inner, cy,
                fill='', outline='#9677AA', width=1, tags=tag)
        elif kind == 'ante':
            border = c.create_rectangle(cx-radius, cy-radius, cx+radius, cy+radius,
                fill=self.ZONE_COLORS[seat], outline=GOLD, width=3, tags=tag)
            c.create_rectangle(cx-radius+5, cy-radius+5, cx+radius-5, cy+radius-5,
                outline='#AFA064', width=1, tags=tag)
        else:
            border = c.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                fill=self.ZONE_COLORS[seat], outline=GOLD, width=3, tags=tag)
            c.create_oval(cx-radius+5, cy-radius+5, cx+radius-5, cy+radius-5,
                outline='#AFA064', width=1, tags=tag)
        # 与 Caribbean 的 5＋1 一致：文字居中，下注筹码也落在同一个中心。
        self._text(cx, cy, label, 14, PANEL_BG, tags=tag)
        self.bet_spots[(seat, kind)] = dict(tag=tag, center=(cx, cy), border=border)
        c.tag_bind(tag, '<Button-1>', lambda _e, s=seat, k=kind: self.add_chip_to_bet(s, k))
        c.tag_bind(tag, '<Button-3>', lambda _e, s=seat, k=kind: self.reset_single_bet(s, k))
        c.tag_bind(tag, '<Enter>', lambda _e: c.configure(cursor='hand2'))
        c.tag_bind(tag, '<Leave>', lambda _e: c.configure(cursor=''))


    def _refresh(self):
        c = self.canvas
        c.itemconfigure(self.balance_item, text=f'余额: ${self.balance:,.2f}')
        total = sum(sum(b.values()) for b in self.bets.values())
        c.itemconfigure(self.total_item, text=f'本局下注: ${total:,.2f}' if total
                        else f'上局返还: ${self.last_win:,.2f}')
        limits = ('$100', '$50,000', '$12,500') if self.high_bet_mode else ('$10', '$10,000', '$2,500')
        for item, value in zip(self.limit_value_items, limits):
            c.itemconfigure(item, text=value)
        self._render_chips()
        betting = self.game.stage == 'betting' and not self._motion_count
        self.set_control_button_state(self.clear_button, betting)
        self.set_control_button_state(self.repeat_button, betting and bool(self.last_bet))
        self.set_control_button_state(self.start_button, betting)
        restarting = self.game.stage in ('await_restart', 'returning', 'credit_pending', 'sweeping')
        c.itemconfigure(self.repeat_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button, state='normal' if restarting else 'hidden')
        self.set_control_button_state(self.restart_button, self.game.stage in ('await_restart', 'credit_pending'))
        for seat in self.game.SEATS:
            decision = self.game.decisions[seat]
            ready = (self.game.stage in self.STREET_NAMES and decision == 'pending'
                     and not self._decision_busy and not self._motion_count)
            for multiplier in (1, 2, 3):
                enabled = ready and self.game.decision_requirement(seat, multiplier) <= self.balance
                self.set_control_button_state(self.action_buttons[(seat, multiplier)], enabled)
            self.set_control_button_state(self.action_buttons[(seat, 'fold')], ready)
            for kind in ('street3', 'street4', 'street5'):
                c.itemconfigure(self.bet_spots[(seat, kind)]['border'],
                    outline='#FFE29A' if ready and kind == self.game.stage else GOLD,
                    width=4 if ready and kind == self.game.stage else 3)
        for notice in self.push_notices.values():
            if notice['level'] > 0:
                c.tag_raise(notice['tag'])


    def _draw_progressive_lamp(self, seat, cx, cy):
        """保留 Caribbean 的红色环灯、动画及上下两段弧形文字。"""
        c, tag = self.canvas, 'spot_'+seat+'_jackpot'
        radius = self.PROGRESSIVE_LAMP_WIDTH/2
        scale = .8
        body = c.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
            fill='#B8303B', outline='#CD4550', width=2, tags=tag)
        center = c.create_oval(cx-27*scale, cy-27*scale, cx+27*scale, cy+27*scale,
            fill='#681923', outline='#781F28', width=2, tags=tag)
        segments = [c.create_arc(cx-56*scale, cy-56*scale, cx+56*scale, cy+56*scale,
                    start=i*22.5, extent=16, style=tk.ARC, width=4, outline='#A33038', tags=tag)
                    for i in range(16)]
        for char, angle in zip('累进大奖', (132, 104, 76, 48)):
            radians = math.radians(angle)
            self._text(cx+42*scale*math.cos(radians), cy-42*scale*math.sin(radians),
                       char, 10, PANEL_BG, angle=angle-90, tags=tag)
        label = '每局$2.50'
        for index, char in enumerate(label):
            angle = 220+100*index/(len(label)-1)
            radians = math.radians(angle)
            self._text(cx+42*scale*math.cos(radians), cy-42*scale*math.sin(radians),
                       char, 9, PANEL_BG, angle=angle-270, tags=tag)
        self.bet_spots[(seat, 'jackpot')] = dict(tag=tag, center=(cx, cy), border=body)
        self.lamps[seat] = dict(body=body, center=center, segments=segments, mode='off', step=0, job=None)
        c.tag_bind(tag, '<Button-1>', lambda _e, s=seat: self.add_chip_to_bet(s, 'jackpot'))
        c.tag_bind(tag, '<Button-3>', lambda _e, s=seat: self.reset_single_bet(s, 'jackpot'))
        c.tag_bind(tag, '<Enter>', lambda _e: c.configure(cursor='hand2'))
        c.tag_bind(tag, '<Leave>', lambda _e: c.configure(cursor=''))
        self._set_lamp_mode(seat, 'off')


    def _make_push_notice(self, seat):
        """沿用 Caribbean 的透明提示浮层，居中放在三个下注位围成区域内。"""
        points = [self.bet_spots[(seat, kind)]['center'] for kind in ('street4', 'ante', 'bonus3')]
        cx = sum(p[0] for p in points)/3
        cy = sum(p[1] for p in points)/3
        tag = 'push_notice_'+seat
        scale, width, height = 3, 230, 48
        layer = Image.new('RGBA', (width*scale, height*scale), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        draw.rounded_rectangle((1, 1, width*scale-2, height*scale-2), radius=10*scale,
            fill=(45, 12, 16, 238), outline=(225, 185, 99, 255), width=2*scale)
        candidates = ['msyhbd.ttc', 'msyh.ttc', 'simhei.ttf', 'Arial Unicode.ttf',
            '/System/Library/Fonts/PingFang.ttc',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
            '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc']
        if sys.platform.startswith('linux'):
            try:
                result = subprocess.run(['fc-list', '-f', '%{file}\n', ':lang=zh'],
                    capture_output=True, text=True, timeout=1, check=False)
                if result.returncode == 0:
                    candidates[:0] = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            except (OSError, subprocess.TimeoutExpired):
                pass
        font = None
        for path in candidates:
            try:
                font = ImageFont.truetype(path, 20*scale)
                break
            except OSError:
                continue
        message = '玩家对子6-10，平局'
        item = self.canvas.create_image(cx, cy, state='hidden', tags=tag)
        text_item = None
        if font is not None:
            box = draw.textbbox((0, 0), message, font=font)
            draw.text(((width*scale-(box[2]-box[0]))/2-box[0],
                       (height*scale-(box[3]-box[1]))/2-box[1]),
                      message, font=font, fill='#FFF1D1')
        else:
            # Pillow 缺少中文字体时，沿用 Caribbean 的 Tk 原生文字回退。
            text_item = self._text(cx, cy, message, 14, '#FFF1D1', state='hidden', tags=tag)
        self.push_notices[seat] = dict(tag=tag, position=(cx, cy), level=0.0,
            target=False, job=None, item=item, text_item=text_item, photo=None,
            source=layer.resize((width, height), Image.Resampling.LANCZOS))


    def _paint_push_notice(self, seat):
        notice = self.push_notices[seat]
        alpha = notice['level']
        if alpha <= 0:
            self.canvas.itemconfigure(notice['tag'], state='hidden')
            return
        layer = notice['source'].copy()
        layer.putalpha(notice['source'].getchannel('A').point(lambda value: round(value*alpha)))
        notice['photo'] = ImageTk.PhotoImage(layer, master=self)
        self.canvas.itemconfigure(notice['item'], image=notice['photo'], state='normal')
        if notice['text_item'] is not None:
            background = tuple(int(self.ZONE_COLORS[seat][i:i+2], 16) for i in (1, 3, 5))
            foreground = (255, 241, 209)
            color = '#'+''.join(f'{round(a+(b-a)*alpha):02x}' for a, b in zip(background, foreground))
            self.canvas.itemconfigure(notice['text_item'], state='normal', fill=color)
        self.canvas.tag_raise(notice['tag'])


    def _fade_push_notice(self, seat, visible, immediate=False):
        if seat not in self.push_notices:
            if not visible:
                return
            self._make_push_notice(seat)
        notice = self.push_notices[seat]
        target = 1.0 if visible else 0.0
        if not immediate and notice['target'] == visible and (notice['job'] is not None or notice['level'] == target):
            return
        if notice['job'] is not None:
            try:
                self.after_cancel(notice['job'])
            except tk.TclError:
                pass
            self._jobs.discard(notice['job'])
            notice['job'] = None
        notice['target'] = visible
        if immediate:
            notice['level'] = target
            self._paint_push_notice(seat)
            return
        start = notice['level']
        def step(frame):
            notice['job'] = None
            notice['level'] = start+(target-start)*frame/12
            self._paint_push_notice(seat)
            if frame < 12:
                notice['job'] = self._schedule(25, step, frame+1)
        step(0)


    def add_chip_to_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count:
            return
        if kind not in ('ante', 'bonus3', 'jackpot'):
            return
        new = {s: dict(b) for s, b in self.bets.items()}
        b = new[seat]
        if kind == 'jackpot':
            b[kind] = 0.0 if b[kind] else 2.5
        else:
            limit = ((50000 if self.high_bet_mode else 10000) if kind == 'ante'
                     else (12500 if self.high_bet_mode else 2500))
            b[kind] = min(limit, b[kind]+self.selected_chip)
        self._apply_bet_layout(new)


    def reset_single_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count:
            return
        if kind not in ('ante', 'bonus3', 'jackpot'):
            return
        new = {s: dict(b) for s, b in self.bets.items()}
        if kind == 'ante':
            new[seat] = self.game.empty_bet()
        else:
            new[seat][kind] = 0.0
        self._apply_bet_layout(new)


    def card_position(self, side, index):
        if side == 'Community':
            return 450+index*85, 74
        center = {'Player1': 294, 'Player2': 855}[side]
        return center-85+index*85, 266


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
        for seat in self.game.SEATS:
            self._fade_push_notice(seat, False, immediate=True)
        self.balance = round(self.balance-charged, 2)
        self.bets = {s: dict(b) for s, b in self.game.bets.items()}
        self.last_bet = {s: dict(b) for s, b in self.bets.items()}
        self._credited = self._return_persisted = self._settlement_started = False
        self._decision_busy = False
        self._cancel_restart_timer()
        self.canvas.delete('cards')
        self.card_items.clear()
        self._flip_photos.clear()
        self._load_assets()
        for side, item in self.title_items.items():
            self.canvas.itemconfigure(item, text=self.SEAT_NAMES[side])
        refunds = []
        for seat in self.game.refunded_bets:
            self._set_lamp_mode(seat, 'off')
            for kind in self.game.empty_bet():
                chip = self.visual_chips.pop((seat, kind, 'stake'), None)
                if chip:
                    refunds.append(dict(amount=chip['amount'], start=chip['xy'],
                                        target=self._rack_position(), duration=440))
        self.game.stage = 'refunding' if refunds else 'progressive'
        self._persist_balance()
        self._refresh()
        self._run_chip_batch(refunds, self._start_progressive_lamps)


    def _deal_next(self, sequence, offset):
        if offset == len(sequence):
            reveal = [(s, i) for s in self.game.SEATS
                      if self.game.decisions[s] == 'pending' for i in range(2)]
            self._reveal_next(reveal, 0, self._after_initial_reveal)
            return
        side, index = sequence[offset]
        x, y = self.card_position(side, index)
        item = self.canvas.create_image(575, 52, image=self._face_photos['back'], anchor='nw', tags='cards')
        self.card_items[(side, index)] = item
        def move(step=0):
            p = step/6
            self.canvas.coords(item, 575+(x-575)*p, 52+(y-52)*p)
            if step < 6:
                self._schedule(round(self.DEAL_MOVE_MS*(step+1)/6)-round(self.DEAL_MOVE_MS*step/6), move, step+1)
            else:
                self._schedule(round(self.DEAL_CARD_MS)-round(self.DEAL_MOVE_MS), self._deal_next, sequence, offset+1)
        move()


    def _reveal_next(self, sequence, offset, complete):
        if offset == len(sequence):
            complete()
            return
        side, index = sequence[offset]
        card = self.game.community_cards[index] if side == 'Community' else self.game.hands[side][index]
        item = self.card_items[(side, index)]
        x, y = self.card_position(side, index)
        def flip(step=0):
            width = max(1, round(self.CARD_WIDTH * abs(1-step/5)))
            source = self._pil_cards['back' if step < 5 else (card.suit, card.rank)]
            photo = ImageTk.PhotoImage(source.resize((width, self.CARD_HEIGHT), Image.Resampling.LANCZOS), master=self)
            self._flip_photos[item] = photo
            self.canvas.itemconfigure(item, image=photo)
            self.canvas.coords(item, x+(self.CARD_WIDTH-width)/2, y)
            if step < 10:
                self._schedule(32, flip, step+1)
            else:
                self.canvas.itemconfigure(item, image=self._face_photos[(card.suit, card.rank)])
                self._flip_photos.pop(item, None)
                if side == 'Community':
                    self.game.community_revealed = max(self.game.community_revealed, index+1)
                self._reveal_next(sequence, offset+1, complete)
        flip()


    def _after_initial_reveal(self):
        self.game.stage = 'street3'
        for seat in self.game.SEATS:
            self._update_hand_title(seat)
        self._refresh()


    def place_street_bet(self, multiplier, seat='Player1'):
        self._decide(seat, multiplier)


    def fold_action(self, seat='Player1'):
        self._decide(seat, 'fold')


    def fold_game(self):
        self.fold_action('Player1')


    def _decide(self, seat, action):
        if (self.game.stage not in self.STREET_NAMES or self._decision_busy or self._motion_count
                or self.game.decisions.get(seat) != 'pending'):
            return
        kind = self.game.stage
        try:
            cost = self.game.decide(seat, action, self.balance)
        except ValueError as exc:
            messagebox.showwarning('无法加注', str(exc), parent=self)
            return
        self._decision_busy = True
        self.balance = round(self.balance-cost, 2)
        self.bets[seat][kind] = self.game.bets[seat][kind]
        self._persist_balance()
        self._refresh()
        def done():
            self._decision_busy = False
            self._update_hand_title(seat)
            self._refresh()
            self._advance_street()
        if action == 'fold':
            transfers = []
            for main_kind in self.game.MAIN_KINDS:
                chip = self.visual_chips.pop((seat, main_kind, 'stake'), None)
                if chip:
                    transfers.append(dict(amount=chip['amount'], start=chip['xy'],
                                          target=self.HOUSE_CHIP_POS, duration=280))
            self._run_chip_batch(transfers, done)
        else:
            target = self.bet_spots[(seat, kind)]['center']
            def arrived():
                self._set_visual(seat, kind, 'stake', cost)
                done()
            self._animate_chip(cost, self._rack_position(), target, arrived)


    def _advance_street(self):
        if self.game.stage not in self.STREET_NAMES or 'pending' in self.game.decisions.values():
            return
        street = int(self.game.stage[-1])
        continuing = any(d == 'bet' for d in self.game.decisions.values())
        self.game.stage = 'revealing'
        self._refresh()
        sequence = [('Community', i) for i in range(self.game.community_revealed,
                                                    street-2 if continuing else 3)]
        def opened():
            for seat in self.game.SEATS:
                self._update_hand_title(seat)
            if street == 5 or not continuing:
                self.game.stage = 'showdown'
                self._schedule(600, self._settle)
            else:
                self.game.stage = f'street{street+1}'
                for seat in self.game.SEATS:
                    if self.game.decisions[seat] == 'bet':
                        self.game.decisions[seat] = 'pending'
            self._refresh()
        self._reveal_next(sequence, 0, opened)


    def _update_hand_title(self, side):
        if side == 'Community':
            return
        if not self.game.hands[side]:
            return
        cards = self.game.hands[side] + self.game.community_cards[:self.game.community_revealed]
        counts = Counter(c.value for c in cards)
        single_pair = max(counts.values()) == 2 and sum(n == 2 for n in counts.values()) == 1
        if single_pair:
            value = next(value for value, count in counts.items() if count == 2)
            name = ('对子5或以下' if value <= 5 else '对子6到10' if value <= 10 else '对子JACK或以上')
        elif len(cards) == 5:
            rank = evaluate_hand(cards)[0]
            name = HAND_RANK_NAMES[rank]
        else:
            groups = sorted(counts.items(), key=lambda p: (p[1], p[0]), reverse=True)
            count = groups[0][1]
            name = ('四条' if count == 4 else '三条' if count == 3
                    else '两对' if sum(n == 2 for n in counts.values()) == 2
                    else '高牌')
        self.canvas.itemconfigure(self.title_items[side], text=f'{self.SEAT_NAMES[side]} - {name}')


    def _settle(self):
        if self._settlement_started or self.game.stage != 'showdown':
            return
        self._settlement_started = True
        jackpot_before = self.game.progressive_amount
        result = self.game.settle()
        self.game.stage = 'settling'
        self.last_win = result['returned']
        for seat in self.game.SEATS:
            self._fade_push_notice(seat, result['hands'].get(seat, {}).get('winner') == 'Push')
        try:
            save_jackpot(self.game.progressive_amount)
        except Exception as exc:
            messagebox.showerror('奖池保存失败', str(exc), parent=self)
        transfers, awards = [], []
        round_id = time.time_ns()
        for seat, outcome in result['hands'].items():
            self._update_hand_title(seat)
            for kind in (*self.game.MAIN_KINDS, 'bonus3'):
                transfers.extend(self._outcome_transfers(seat, kind, self.game.bets[seat][kind],
                                                        outcome['details'][kind]))
            bonus = outcome['details']['bonus']
            self._set_lamp_mode(seat, 'win' if bonus else 'off')
            if bonus:
                awards.append((seat, bonus))
            try:
                save_mississippi_history(
                    self.game.deck, self.game.community_cards, self.game.hands[seat],
                    outcome['returned'], outcome['rank'], HAND_RANK_NAMES[outcome['rank']],
                    outcome['winner'], self.game.decisions[seat] == 'fold',
                    seat=seat, round_id=round_id, bets=self.game.bets[seat])
            except Exception as exc:
                messagebox.showerror('历史记录保存失败', str(exc), parent=self)
        self._refresh()
        self._run_chip_batch(transfers, lambda: self._pay_progressive_awards(awards, jackpot_before))


    def reset_game(self, auto_reset=False):
        if self.game.stage == 'betting':
            self.reset_bets()
        elif self.game.stage in ('await_restart', 'credit_pending'):
            self._return_all_chips()


    def _finish_round(self):
        if self.game.stage != 'sweeping':
            return
        for seat in self.game.SEATS:
            self._set_lamp_mode(seat, 'off')
            self._fade_push_notice(seat, False, immediate=True)
        self.game.reset_game()
        self._history_available = False
        self.bets = {s: self.game.empty_bet() for s in self.game.SEATS}
        for side, item in self.title_items.items():
            self.canvas.itemconfigure(item, text=self.SEAT_NAMES[side])
        self._refresh()


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


    def _draw_limit_table(self):
        # 保留原加勒比的标题 + 三列限红表，改成深绿/金色。
        c = self.canvas
        x0,x1,y0 = 30,349,75
        c.create_rectangle(x0,y0,x1,181,fill='#183B30',outline=GOLD,width=1,tags='limits')
        c.create_rectangle(x0,y0,x1,y0+29,fill='#40634B',outline=GOLD,tags='limits')
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
        panel = tk.Frame(self.canvas,bg='#123C30',highlightbackground=GOLD,highlightthickness=2)
        self.progressive_panel=panel
        self.canvas.create_window(957,128,window=panel,width=322,height=118)
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
        if abs(value)>=1000:return MississippiStudGUI._compact(value)
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


    def _collect_progressive_and_deal(self):
        for seat in self.game.SEATS:
            chip=self.visual_chips.pop((seat,'jackpot','stake'),None)
            if chip:self._animate_chip(chip['amount'],chip['xy'],self.HOUSE_CHIP_POS,duration=280)
        self.game.stage='dealing';self._refresh()
        # 动画与实际取牌共用同一顺序，未下注的一家没有牌也没有空节拍。
        self._deal_next(self.game.deal_sequence,0)


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
        """入账后，公共牌和玩家的全部已显示扑克牌一起在0.2秒内向右移走。"""
        for seat in self.game.SEATS:
            self._fade_push_notice(seat, False)
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
        dialog.title('密西西比梭哈扑克 游戏规则')
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
                            ('本局目标', '逐街下注，并以两张手牌和三张公共牌组成最终五张牌。'),
                        ],
                        [],
                    ],
                    [
                        '一局如何进行',
                        '',
                        [
                            ('玩家下注', '为玩家1、玩家2分别设置前注、公牌加注及可选累进大奖。'),
                            ('玩家决策', '每手在三街、四街、五街选择弃牌或加注；两手决定后开公共牌。'),
                            ('庄家开牌', '依次翻开三张公共牌；\n本游戏没有对战庄家。'),
                            ('结算', '按最终五张牌与公共牌牌型结算。'),
                        ],
                        [],
                    ],
                    [
                        '游戏流程',
                        '',
                        [
                            (
                                '',
                                '设置前注和公牌加注，选择是否参与累进大奖\n点击「开牌」或按 ENTER→ 发牌（玩家2张底牌 + 3张公共牌面朝下）\n翻开玩家底牌，玩家决定：\n• 弃牌: 输掉已下主注（公牌加注、累进大奖仍独立结算）\n• 下注1x/2x/3x（前注倍数）进入「三街」阶段\n翻开第一张公共牌，再次选择弃牌或下注1x/2x/3x（四街）\n翻开第二张公共牌，再次选择弃牌或下注1x/2x/3x（五街）\n翻开第三张公共牌，摊牌结算',
                            ),
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
                                    ['前注', '普通：$10–$10,000\n高额：$100–$50,000', '参与最终五张牌型判奖。'],
                                    ['公牌加注', '普通：每项最高$2,500\n高额：每项最高$12,500', '按三张公共牌的牌型判奖。'],
                                    ['累进大奖', '每手每局$2.50', '按玩家最终五张牌型判奖。'],
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
                        '判奖条件',
                        '',
                        [],
                        [
                            (
                                '判奖规则',
                                ['项目', '判定方式'],
                                [
                                    ['主注', '按玩家两张手牌与三张公共牌组成的最终五张牌型判定。'],
                                    ['公牌加注', '只使用三张公共牌判定。'],
                                    ['累进大奖', '按玩家最终五张牌判奖。'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '结算规则',
                        '',
                        [],
                        [
                            (
                                '',
                                ['情形／项目', '赔率／结算规则'],
                                [
                                    ['结算规则', '主注（前注 + 三街 + 四街 + 五街）根据最终5张牌型支付（见下方赔率表）'],
                                    ['', '公牌加注根据3张公共牌牌型支付（见下方赔率表）'],
                                    ['', '累进大奖根据玩家最终5张牌型支付（见下方赔率表）'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '数据行（牌型、主注赔率、公牌加注、累进大奖）',
                        '',
                        [],
                        [
                            (
                                '',
                                ['牌型', '主注赔率', '公牌加注', '累进大奖'],
                                [
                                    ['皇家同花顺', '500:1', '40:1', '100% 奖池'],
                                    ['同花顺', '100:1', '40:1', '10% 奖池'],
                                    ['四条', '40:1', '-', '$1,250'],
                                    ['葫芦', '10:1', '-', '$375'],
                                    ['同花', '6:1', '3:1', '$250'],
                                    ['顺子', '4:1', '6:1', '-'],
                                    ['三条', '3:1', '30:1', '-'],
                                    ['两对', '2:1', '-', '-'],
                                    ['对子JACK或以上', '1:1', '-', '-'],
                                    ['对子6到10', '返还本金', '-', '-'],
                                    ['对子', '-', '1:1', '-'],
                                    ['其他', '输', '输', '-'],
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
                        '10 种牌型',
                        '下方图片展示牌型示例；\n同一牌型也可能由其他牌面组成。',
                        [],
                        [
                            (
                                '牌型等级与牌例（由高至低）',
                                ['等级', '牌型', '牌例'],
                                [
                                    [
                                        '1',
                                        '皇家同花顺',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♠', 'A'),
                                                ('♠', 'K'),
                                                ('♠', 'Q'),
                                                ('♠', 'J'),
                                                ('♠', '10'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '2',
                                        '同花顺',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', '9'),
                                                ('♥', '8'),
                                                ('♥', '7'),
                                                ('♥', '6'),
                                                ('♥', '5'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '3',
                                        '四条',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♠', '9'),
                                                ('♥', '9'),
                                                ('♦', '9'),
                                                ('♣', '9'),
                                                ('♠', '2'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '4',
                                        '葫芦',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♠', 'K'),
                                                ('♥', 'K'),
                                                ('♦', 'K'),
                                                ('♣', '5'),
                                                ('♦', '5'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '5',
                                        '同花',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', 'A'),
                                                ('♥', '10'),
                                                ('♥', '8'),
                                                ('♥', '5'),
                                                ('♥', '2'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '6',
                                        '顺子',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♠', '9'),
                                                ('♥', '8'),
                                                ('♦', '7'),
                                                ('♣', '6'),
                                                ('♠', '5'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '7',
                                        '三条',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♠', 'Q'),
                                                ('♥', 'Q'),
                                                ('♦', 'Q'),
                                                ('♣', '8'),
                                                ('♦', '2'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '8',
                                        '两对',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♠', 'J'),
                                                ('♥', 'J'),
                                                ('♦', '4'),
                                                ('♣', '4'),
                                                ('♠', 'A'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '9',
                                        '对子',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♠', 'A'),
                                                ('♥', 'A'),
                                                ('♦', '10'),
                                                ('♣', '7'),
                                                ('♠', '2'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '10',
                                        '高牌',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♠', 'A'),
                                                ('♥', 'K'),
                                                ('♦', '9'),
                                                ('♣', '6'),
                                                ('♠', '3'),
                                            ),
                                        ),
                                    ],
                                ],
                            ),
                        ],
                    ],
                ],
            ),
            (
                '特别事项',
                '补充说明特殊牌、模式差异和金额结算方式。',
                [
                    [
                        '补充说明',
                        '',
                        [
                            ('', '注:\n• 主注 = 前注 + 三街 + 四街 + 五街的总和。\n• 公牌加注仅根据3张公共牌判定，与玩家手牌无关。'),
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
        tk.Label(header, text='密西西比梭哈扑克 游戏规则', font=(font_name, 20, 'bold'),
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
        return MississippiStudGUI(
            parent, actual_balance, actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("密西西比梭哈撲克")
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
