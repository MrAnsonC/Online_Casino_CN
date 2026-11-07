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
# 颜色常量（沿用 Mississippi 风格）
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
    5: '顺子', 4: '三条', 3: '两对', 2: '对子10或以上', 1: '对子9或以下', 0: '高牌'
}

# 主注赔率（A注、B注、C注）
MAIN_BET_PAYOUT = {
    10: 500,   # 皇家同花顺 500:1
    9: 200,    # 同花顺 200:1
    8: 50,     # 四条 50:1
    7: 11,     # 葫芦 11:1
    6: 8,      # 同花 8:1
    5: 5,      # 顺子 5:1
    4: 3,      # 三条 3:1
    3: 2,      # 两对 2:1
    2: 1       # 对子10+ 1:1
}

# ======== 修改点：手牌加注（原公牌加注）赔率表 ========
# 基于玩家三张手牌：同花顺40:1，三条30:1，顺子6:1，同花3:1，对子1:1
TRIPS_PAYOUT = {
    9: 40,   # 同花顺
    4: 30,   # 三条
    5: 6,    # 顺子
    6: 3,    # 同花
    1: 1     # 对子
}

# 累进大奖赔率
JACKPOT_PAYOUT = {
    10: {"type": "percentage", "value": 1.0, "min": 0},   # 皇家同花顺 → 100% 奖池
    9: {"type": "percentage", "value": 0.1, "min": 0},    # 同花顺 → 10% 奖池
    8: {"type": "fixed", "value": 1250},                  # 四条 → $1,250
    7: {"type": "fixed", "value": 375},                   # 葫芦 → $375
    6: {"type": "fixed", "value": 250}                    # 同花 → $250
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
# Progressive 加载与保存（Key 改为 'Progressive_2.50'）
# =========================================================
def load_jackpot():
    path = str(_progressive_file)
    default_jackpot = 157301.26
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
# 历史记录（Let_It_Ride.json）
# =========================================================
def letitride_log_path() -> str:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Let_It_Ride.json")

def save_letitride_history(deck, comm_cards, player_cards, win_amount, hand_rank, hand_name, result_status, *, seat=None, round_id=None, bets=None, kept=None, deferred_refund=0):
    """
    保存牌局历史到 Let_It_Ride.json
    history_record 包含 game, win, lose, pair_ten_or_better, pair_2_9 等统计
    history 每条记录包含 game_id, timestamp, deck_order, cut_position,
    comm_cards, player_cards, win_amount, result
    """
    log_path = letitride_log_path()
    data = {
        "history_record": {
            "game": 0,
            "win": 0,
            "lose": 0,
            "royal_flush": 0,
            "straight_flush": 0,
            "four_of_a_kind": 0,
            "full_house": 0,
            "flush": 0,
            "straight": 0,
            "three_of_a_kind": 0,
            "two_pair": 0,
            "pair_ten_or_better": 0,
            "pair_2_9": 0,
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
            print(f"读取历史文件出错: {e}")

    stats = data["history_record"]
    stats["game"] += 1
    if result_status == "Win":
        stats["win"] += 1
    else:
        stats["lose"] += 1

    # 牌型计数
    rank_to_key = {
        10: 'royal_flush',
        9: 'straight_flush',
        8: 'four_of_a_kind',
        7: 'full_house',
        6: 'flush',
        5: 'straight',
        4: 'three_of_a_kind',
        3: 'two_pair',
        2: 'pair_ten_or_better',
        1: 'pair_2_9',
        0: 'high_card'
    }
    key = rank_to_key.get(hand_rank, 'high_card')
    stats[key] = stats.get(key, 0) + 1

    # 生成 game_id
    max_id = 0
    for rec in data["history"]:
        if "game_id" in rec and isinstance(rec["game_id"], int):
            max_id = max(max_id, rec["game_id"])
    new_game_id = max_id + 1

    record = {
        "game_id": new_game_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "deck_order": [str(c) for c in deck.full_deck],
        "cut_position": deck.cut_position,
        "comm_cards": [str(c) for c in comm_cards],
        "player_cards": [str(c) for c in player_cards],
        "win_amount": win_amount,
        "result": result_status   # "Win" / "Lose"
    }
    if seat is not None:
        record.update(seat=seat, round_id=round_id, bets=dict(bets or {}),
                      kept=dict(kept or {}), deferred_refund=deferred_refund)
    data["history"].append(record)

    # 保留最新50局
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
# 评估函数
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
        if pair >= 10:
            return (2, [pair] + kickers)
        else:
            return (1, [pair] + kickers)
    return (0, values[:5])

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
# Let It Ride 游戏逻辑类
# =========================================================
class LetItRideGame:
    def __init__(self):
        self.reset_game()
        self.progressive_amount = load_jackpot()[1]

    def reset_game(self):
        self.deck = Deck()
        self.community_cards = []
        self.player_hole = []
        self.bet_a = 0      # A注
        self.bet_b = 0      # B注
        self.bet_c = 0      # C注
        self.trips = 0      # 手牌加注（原公牌加注）
        self.participate_jackpot = False
        self.keep_bet_a = False
        self.keep_bet_b = False
        self.stage = "pre_flop"
        self.cards_revealed = {
            "player": [False, False, False],
            "community": [False, False]
        }
        self.cut_position = self.deck.start_pos
        self.card_sequence = self.deck.card_sequence

    def deal_initial(self):
        # 修改发牌顺序：先发2张公共牌，再发3张玩家牌
        self.community_cards = self.deck.deal(2)
        self.player_hole = self.deck.deal(3)

    def evaluate_hands(self):
        """评估玩家最终5张牌"""
        cards = self.player_hole + self.community_cards
        return evaluate_hand(cards)[0]

    def evaluate_current_hand(self, community_revealed_count):
        """评估当前可见牌（用于显示牌型）"""
        revealed_community = self.community_cards[:community_revealed_count]
        all_cards = self.player_hole + revealed_community
        if len(all_cards) < 3:
            return None
        best_eval, _ = find_best_5(all_cards)
        return best_eval

# =========================================================
# 主 GUI 类
# =========================================================
def evaluate_3card(cards):
    values = [c.value for c in cards]
    suits = [c.suit for c in cards]
    flush = len(set(suits)) == 1
    vals = sorted(values)
    # 检测顺子
    if vals == [2,3,14] or (vals[0]+1 == vals[1] and vals[1]+1 == vals[2]):
        straight = True
    else:
        straight = False
    # 三条
    if vals[0]==vals[1]==vals[2]:
        return 4  # 三条
    # 同花顺
    if flush and straight:
        return 9  # 同花顺
    # 顺子
    if straight:
        return 5
    # 同花
    if flush:
        return 6
    # 对子
    if vals[0]==vals[1] or vals[1]==vals[2]:
        return 1  # 对子
    else:
        return -1


class LetItRideTableGame:
    """两手各自决定前两注去留，收回本金在本局结束后统一返还。"""
    SEATS = ('Player1', 'Player2')
    MAIN_KINDS = ('bet_a', 'bet_b', 'bet_c')
    MIN_PROGRESSIVE = 271288.59

    def __init__(self):
        self.progressive_amount = load_jackpot()[1]
        self.min_progressive = self.MIN_PROGRESSIVE
        self.reset_game()

    @staticmethod
    def empty_bet():
        return dict(bet_a=0.0, bet_b=0.0, bet_c=0.0, trips=0.0, jackpot=0.0)

    def reset_game(self):
        self.deck = None
        self.hands = {s: [] for s in self.SEATS}
        self.community_cards = []
        self.community_revealed = 0
        self.deal_sequence = []
        self.bets = {s: self.empty_bet() for s in self.SEATS}
        self.kept = {s: dict(bet_a=None, bet_b=None, bet_c=True) for s in self.SEATS}
        self.decisions = {s: 'inactive' for s in self.SEATS}
        self.refunded_bets = {}
        self.stage = 'betting'
        self.trips_settlement = None
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
            if not any(b[k] for k in self.MAIN_KINDS):
                if any(b.values()):
                    refunded[seat] = dict(b)
                prepared[seat] = self.empty_bet()
                continue
            if not (b['bet_a'] == b['bet_b'] == b['bet_c']):
                raise ValueError('每手的三份主注必须等额。')
            if not minimum <= b['bet_a'] <= maximum:
                raise ValueError(f'每份主注须为 ${minimum:,} 至 ${maximum:,}。')
            if b['trips'] > side_max or b['jackpot'] not in (0, 2.5):
                raise ValueError('手牌加注超出限额，累进大奖每手固定 $2.50。')
            prepared[seat] = b
        active = tuple(s for s in self.SEATS if prepared[s]['bet_c'])
        if not active:
            raise ValueError('请至少为一手牌设置三份等额主注。')
        charged = round(sum(sum(b.values()) for b in prepared.values()), 2)
        if not math.isfinite(balance) or charged > balance:
            raise ValueError(f'余额不足，需要 ${charged:,.2f}。')
        deck = Deck()
        hands, community, sequence = {s: [] for s in self.SEATS}, [], []
        # 每轮先发参与的玩家，再发公共牌；第三轮仅补玩家第三张牌。
        for index in range(3):
            sequence.extend((s, index) for s in active)
            if index < 2:
                sequence.append(('Community', index))
        for side, _ in sequence:
            target = community if side == 'Community' else hands[side]
            target.extend(deck.deal(1))
        self.deck, self.hands, self.community_cards = deck, hands, community
        self.bets, self.refunded_bets, self.deal_sequence = prepared, refunded, sequence
        self.decisions = {s: 'pending' if s in active else 'inactive' for s in self.SEATS}
        self.stage = 'dealing'
        return charged

    def decide(self, seat, action):
        if (self.stage not in ('decision_a', 'decision_b')
                or self.decisions.get(seat) != 'pending'):
            return False
        if action not in ('keep', 'withdraw'):
            raise ValueError('请选择保留或收回。')
        kind = 'bet_a' if self.stage == 'decision_a' else 'bet_b'
        self.kept[seat][kind] = action == 'keep'
        self.decisions[seat] = action
        return True

    def settle_trips(self):
        """三张手牌翻开后冻结边注结果，后续主注结算直接复用。"""
        if self.trips_settlement is not None:
            return self.trips_settlement
        active = [s for s in self.SEATS if self.decisions[s] != 'inactive']
        if self.stage != 'trips_settling' or any(len(self.hands[s]) != 3 for s in active):
            raise ValueError('三张手牌翻开后才能结算手牌加注。')
        self.trips_settlement = {}
        for seat in active:
            rank = evaluate_3card(self.hands[seat])
            self.trips_settlement[seat] = (round(self.bets[seat]['trips']*(1+TRIPS_PAYOUT[rank]), 2)
                                           if rank in TRIPS_PAYOUT else 0.0)
        return self.trips_settlement

    def settle(self):
        if self.settlement is not None:
            return self.settlement
        if self.stage != 'showdown' or 'pending' in self.decisions.values():
            raise ValueError('两手完成决定并翻开公共牌后才能结算。')
        if self.trips_settlement is None:
            raise ValueError('手牌加注须在第一注决定前结算。')
        active = [s for s in self.SEATS if self.decisions[s] != 'inactive']
        if any(self.kept[s][k] is None for s in active for k in ('bet_a', 'bet_b')):
            raise ValueError('前两份主注尚未完成决定。')
        snapshot, outcomes = self.progressive_amount, {}
        for seat in active:
            b = self.bets[seat]
            rank = evaluate_hand(self.hands[seat]+self.community_cards)[0]
            details = {k: 0.0 for k in (*self.MAIN_KINDS, 'trips', 'bonus')}
            withdrawn = 0.0
            for kind in self.MAIN_KINDS:
                if not self.kept[seat][kind]:
                    details[kind] = b[kind]
                    withdrawn += b[kind]
                elif rank in MAIN_BET_PAYOUT:
                    details[kind] = round(b[kind]*(1+MAIN_BET_PAYOUT[rank]), 2)
            details['trips'] = self.trips_settlement[seat]
            if b['jackpot'] and rank in JACKPOT_PAYOUT:
                rule = JACKPOT_PAYOUT[rank]
                details['bonus'] = round(snapshot*rule['value'] if rule['type']=='percentage'
                                         else rule['value'], 2)
            returned = round(sum(details.values()), 2)
            outcomes[seat] = dict(rank=rank, winner='Win' if details['bet_c']>b['bet_c'] else 'Lose',
                details=details, withdrawn=round(withdrawn, 2), returned=returned,
                winnings=round(returned-withdrawn, 2), stake=round(sum(b.values()), 2),
                net=round(returned-sum(b.values()), 2))
        awards = sum(o['details']['bonus'] for o in outcomes.values())
        # 已收回的主注不计入奖池贡献，即使暂时仍摆在桌上。
        contribution = sum((sum(self.bets[s][k] for k in self.MAIN_KINDS if self.kept[s][k])
                            + self.bets[s]['trips'])*.001+self.bets[s]['jackpot']*.95 for s in active)
        self.progressive_amount = round(max(self.MIN_PROGRESSIVE, snapshot-awards)+contribution, 2)
        self.stage = 'settled'
        self.settlement = dict(hands=outcomes,
            returned=round(sum(o['returned'] for o in outcomes.values()), 2))
        return self.settlement


class LetItRideGUI(tk.Frame):
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
    DECISION_KINDS = {'decision_a': 'bet_a', 'decision_b': 'bet_b'}
    BET_NAMES = {'bet_a': '第一注', 'bet_b': '第二注', 'bet_c': '第三注'}
    WITHDRAW_OFFSET = (18, -40)

    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = username, float(initial_balance)
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game = LetItRideTableGame()
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
        self._text(575, 18, '任逍遥扑克  LET IT RIDE', 16, GOLD)
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
        self._text(575, 213, '三注等额  •  前两注可收回  •  对子10或以上获胜', 13, GOLD)
        for seat, x0, x1 in (('Player1', 22, 566), ('Player2', 582, 1128)):
            main_centers = (x0+70, x0+196, x0+322)
            self._draw_progressive_lamp(seat, (main_centers[0]+main_centers[1])/2, 446)
            self._draw_spot(seat, 'trips', (main_centers[1]+main_centers[2])/2, 446, '手牌加注')
            for kind, cx in zip(self.game.MAIN_KINDS, main_centers):
                self._draw_spot(seat, kind, cx, 558, self.BET_NAMES[kind])
            for left, right in zip(main_centers, main_centers[1:]):
                self._text((left+right)/2, 558, '=', 18, GOLD, tags='equal_'+seat)
            self.action_buttons[(seat, 'keep')] = self.create_control_button(
                x0+410, 419, x1-15, 477, '保留第一注', lambda s=seat: self.keep_action(s),
                '#397A48', font_size=14, draw_shadow=False)
            self.action_buttons[(seat, 'withdraw')] = self.create_control_button(
                x0+410, 488, x1-15, 546, '收回第一注', lambda s=seat: self.withdraw_action(s),
                '#9B403A', font_size=14, draw_shadow=False)
        self._draw_bottom_controls()
        for side in ('Community', *self.game.SEATS):
            for index in range(2 if side == 'Community' else 3):
                x, y = self.card_position(side, index)
                c.create_rectangle(x, y, x+self.CARD_WIDTH, y+self.CARD_HEIGHT,
                    outline='#7B9374', dash=(3, 3), tags='card_slots')


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
        current = self.DECISION_KINDS.get(self.game.stage)
        for seat in self.game.SEATS:
            ready = bool(current) and self.game.decisions[seat]=='pending' and not self._decision_busy and not self._motion_count
            for action, verb in (('keep', '保留'), ('withdraw', '收回')):
                tag = self.action_buttons[(seat, action)]
                self.set_control_button_state(tag, ready)
                label = verb+self.BET_NAMES[current] if current else verb+'第一注'
                c.itemconfigure(self.control_buttons[tag]['text'], text=label)
            for kind in self.game.MAIN_KINDS:
                c.itemconfigure(self.bet_spots[(seat, kind)]['border'],
                    outline='#FFE29A' if ready and current==kind else GOLD,
                    width=4 if ready and current==kind else 3)


    def add_chip_to_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count:
            return
        new = {s: dict(b) for s, b in self.bets.items()}
        b = new[seat]
        if kind == 'jackpot':
            b[kind] = 0.0 if b[kind] else 2.5
        elif kind in self.game.MAIN_KINDS:
            amount = min(50000 if self.high_bet_mode else 10000, b['bet_a']+self.selected_chip)
            for main_kind in self.game.MAIN_KINDS:
                b[main_kind] = amount
        elif kind == 'trips':
            b[kind] = min(12500 if self.high_bet_mode else 2500, b[kind]+self.selected_chip)
        else:
            return
        self._apply_bet_layout(new)


    def reset_single_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count:
            return
        new = {s: dict(b) for s, b in self.bets.items()}
        if kind in self.game.MAIN_KINDS:
            for main_kind in self.game.MAIN_KINDS:
                new[seat][main_kind] = 0.0
        else:
            new[seat][kind] = 0.0
        self._apply_bet_layout(new)


    def card_position(self, side, index):
        if side == 'Community':
            return 492.5+index*85, 74
        center = {'Player1': 294, 'Player2': 855}[side]
        return center-127.5+index*85, 266


    def _after_initial_reveal(self):
        if self.game.stage != 'dealing':
            return
        self.game.stage = 'trips_settling'
        for seat in self.game.SEATS:
            self._update_hand_title(seat)
        transfers = []
        for seat, returned in self.game.settle_trips().items():
            transfers.extend(self._outcome_transfers(seat, 'trips', self.game.bets[seat]['trips'], returned))
        def done():
            if self.game.stage == 'trips_settling':
                self.game.stage = 'decision_a'
                self._refresh()
        self._refresh()
        self._run_chip_batch(transfers, done)


    def keep_action(self, seat='Player1'):
        self._decide(seat, 'keep')


    def withdraw_action(self, seat='Player1'):
        self._decide(seat, 'withdraw')


    def play_action(self, keep, bet_type, seat='Player1'):
        expected = 'decision_a' if bet_type in ('a', 'bet_a') else 'decision_b'
        if self.game.stage == expected:
            self._decide(seat, 'keep' if keep else 'withdraw')


    def _decide(self, seat, action):
        if (self.game.stage not in self.DECISION_KINDS or self._decision_busy or self._motion_count
                or self.game.decisions.get(seat) != 'pending'):
            return
        kind = self.DECISION_KINDS[self.game.stage]
        if not self.game.decide(seat, action):
            return
        self._decision_busy = True
        self._refresh()
        def done():
            self._decision_busy = False
            self._refresh()
            self._advance_decisions()
        if action == 'keep':
            done()
            return
        # 收回只改变本注的参赌资格：不加余额，原位置右移18px、上移40px。
        chip = self.visual_chips.pop((seat, kind, 'stake'), None)
        amount = chip['amount'] if chip else self.game.bets[seat][kind]
        origin = chip['xy'] if chip else self.bet_spots[(seat, kind)]['center']
        target = (origin[0]+self.WITHDRAW_OFFSET[0], origin[1]+self.WITHDRAW_OFFSET[1])
        def arrived():
            self._set_visual(seat, kind, 'withdrawn', amount, target)
            done()
        self._animate_chip(amount, origin, target, arrived, duration=220)


    def _advance_decisions(self):
        if self.game.stage not in self.DECISION_KINDS or 'pending' in self.game.decisions.values():
            return
        index = 0 if self.game.stage == 'decision_a' else 1
        self.game.stage = 'revealing'
        self._refresh()
        def opened():
            for seat in self.game.SEATS:
                self._update_hand_title(seat)
            if index == 0:
                self.game.stage = 'decision_b'
                for seat in self.game.SEATS:
                    if self.game.decisions[seat] != 'inactive':
                        self.game.decisions[seat] = 'pending'
            else:
                self.game.stage = 'showdown'
                self._schedule(600, self._settle)
            self._refresh()
        self._reveal_next([('Community', index)], 0, opened)


    def _update_hand_title(self, seat):
        if seat == 'Community' or not self.game.hands[seat]:
            return
        cards = self.game.hands[seat]+self.game.community_cards[:self.game.community_revealed]
        counts = Counter(c.value for c in cards)
        if len(cards) == 5:
            name = HAND_RANK_NAMES[evaluate_hand(cards)[0]]
        elif 3 in counts.values():
            name = '三条'
        elif sum(n==2 for n in counts.values()) >= 2:
            name = '两对'
        elif 2 in counts.values():
            value = next(v for v, n in counts.items() if n==2)
            name = '对子10或以上' if value>=10 else '对子9或以下'
        else:
            name = '高牌'
        self.canvas.itemconfigure(self.title_items[seat], text=f'{self.SEAT_NAMES[seat]} - {name}')


    def _settle(self):
        if self._settlement_started or self.game.stage != 'showdown':
            return
        self._settlement_started = True
        jackpot_before = self.game.progressive_amount
        result = self.game.settle()
        self.game.stage = 'settling'
        self.last_win = result['returned']
        try:
            save_jackpot(self.game.progressive_amount)
        except Exception as exc:
            messagebox.showerror('奖池保存失败', str(exc), parent=self)
        transfers, awards = [], []
        round_id = time.time_ns()
        for seat, outcome in result['hands'].items():
            self._update_hand_title(seat)
            # 手牌加注已在三张手牌翻开后派彩，不在局末重复处理筹码。
            for kind in self.game.MAIN_KINDS:
                # 已收回筹码留在右上方暂存位置，既不输掉也不获得主注派彩。
                if kind in self.game.MAIN_KINDS and not self.game.kept[seat][kind]:
                    continue
                transfers.extend(self._outcome_transfers(seat, kind, self.game.bets[seat][kind],
                                                        outcome['details'][kind]))
            bonus = outcome['details']['bonus']
            self._set_lamp_mode(seat, 'win' if bonus else 'off')
            if bonus:
                awards.append((seat, bonus))
            try:
                save_letitride_history(
                    self.game.deck, self.game.community_cards, self.game.hands[seat],
                    outcome['winnings'], outcome['rank'], HAND_RANK_NAMES[outcome['rank']], outcome['winner'],
                    seat=seat, round_id=round_id, bets=self.game.bets[seat],
                    kept=self.game.kept[seat], deferred_refund=outcome['withdrawn'])
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
        self.game.reset_game()
        self._history_available = False
        self.bets = {s: self.game.empty_bet() for s in self.game.SEATS}
        for side, item in self.title_items.items():
            self.canvas.itemconfigure(item, text=self.SEAT_NAMES[side])
        self._refresh()


    def evaluate_3card(self, cards):
        return evaluate_3card(cards)


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
        titles = ('每注最低','每注最高','边注最高')
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
        if abs(value)>=1000:return LetItRideGUI._compact(value)
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
                      if self.game.decisions[s] == 'pending' for i in range(3)]
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


    def _draw_spot(self, seat, kind, cx, cy, label):
        c, tag = self.canvas, 'spot_'+seat+'_'+kind
        radius = 50
        if kind == 'trips':
            # 四个等距顶点构成旋转 45 度的正方形，以紫色区分手牌加注。
            border = c.create_polygon(cx, cy-radius, cx+radius, cy, cx, cy+radius, cx-radius, cy,
                fill='#58366B', outline='#C29ADD', width=3, tags=tag)
            inner = radius-5
            c.create_polygon(cx, cy-inner, cx+inner, cy, cx, cy+inner, cx-inner, cy,
                fill='', outline='#9677AA', width=1, tags=tag)
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
        dialog.title('任逍遥扑克（Let It Ride）游戏规则')
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
                            ('本局目标', '用三张手牌和两张公共牌组成五张牌，并决定是否收回前两注。'),
                        ],
                        [],
                    ],
                    [
                        '一局如何进行',
                        '',
                        [
                            ('玩家下注', '两手分别设置三份等额主注及可选边注。'),
                            ('玩家决策', '三张手牌翻开并完成手牌加注结算后，先决定是否保留 A 注，再决定是否保留 B 注。'),
                            ('庄家开牌', '依次翻开两张公共牌；\n本游戏没有对战庄家。'),
                            ('结算', '按最终五张牌型结算仍保留的下注。'),
                        ],
                        [],
                    ],
                    [
                        '游戏流程',
                        '',
                        [
                            (
                                '',
                                '设置下注，点击「开牌」或按 ENTER→ 发牌（玩家3张 + 公共牌2张面朝下）\n翻开玩家三张手牌，先结算手牌加注，再决定是否保留 A 注\n• 收回：第一注筹码移至下注位右上方暂存，局末统一退回\n• 保留：继续\n翻开第一张公共牌，玩家决定是否保留 B 注\n• 收回：第二注筹码移至下注位右上方暂存，局末统一退回\n• 保留：继续\n翻开第二张公共牌，C 注始终保留，摊牌结算',
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
                                    ['A注／B注／C注', '普通：$10–$10,000\n高额：$100–$50,000', 'A注、B注可在对应阶段收回，C注始终保留。'],
                                    ['手牌加注', '普通：每项最高$2,500\n高额：每项最高$12,500', '三张手牌翻开后、第一注决定前判奖。'],
                                    ['累进大奖', '每手每局$2.50', '按最终五张牌型判奖。'],
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
                                    ['主注', '只依据玩家三张手牌与两张公共牌组成的最终五张牌型。'],
                                    ['手牌加注', '只使用玩家原始三张手牌，不与庄家比较。'],
                                    ['累进大奖', '只按最终五张牌型判奖。'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '结算',
                        '',
                        [],
                        [
                            (
                                '',
                                ['情形／项目', '赔率／结算规则'],
                                [
                                    ['结算', '主注（A+B+C）根据最终5张牌型按赔率表支付'],
                                    ['', '三张手牌翻开后先结算手牌加注，再进行第一注决定；返还筹码留在桌上，局末统一入账'],
                                    ['', '累进大奖根据最终5张牌型支付（见赔率表）'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '各下注项目赔率表',
                        '',
                        [],
                        [
                            (
                                '',
                                ['牌型', '主注赔率', '手牌加注', '累进大奖'],
                                [
                                    ['皇家同花顺', '500:1', '-', '100%'],
                                    ['同花顺', '200:1', '40:1', '10%'],
                                    ['四条', '50:1', '-', '$1,250'],
                                    ['葫芦', '11:1', '-', '$375'],
                                    ['同花', '8:1', '3:1', '$250'],
                                    ['顺子', '5:1', '6:1', '-'],
                                    ['三条', '3:1', '30:1', '-'],
                                    ['两对', '2:1', '-', '-'],
                                    ['对子10+', '1:1', '1:1', '-'],
                                    ['对子2-9', '-', '1:1', '-'],
                                    ['其他', '-', '-', '-'],
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
                            ('', '注:\n• 主注 = A注 + B注 + C注，A注和B注可在相应阶段收回。\n• 手牌加注仅基于玩家3张底牌。\n• 累进大奖奖池金额显示在界面上方。'),
                        ],
                        [],
                    ],
                    [
                        '特殊下注规则',
                        '',
                        [
                            ('A注／B注／C注', '三份等额；\n联动调整'),
                            ('下注', 'A注、B注、C注为等额主注（联动调整）'),
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
        tk.Label(header, text='任逍遥扑克（Let It Ride）游戏规则', font=(font_name, 20, 'bold'),
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
        return LetItRideGUI(
            parent, actual_balance, actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("任逍遥撲克")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = LetItRideGUI(root, actual_balance, actual_user)
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
