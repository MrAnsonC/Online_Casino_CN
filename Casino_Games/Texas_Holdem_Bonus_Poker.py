import sys as _account_sys
from pathlib import Path as _AccountPath
_account_root = next((p for p in (_AccountPath(__file__).resolve().parent, *_AccountPath(__file__).resolve().parents) if (p / "A_Tools" / "Account" / "secure_json.py").is_file()), None)
if _account_root is None:
    raise RuntimeError("找不到加密账户组件，请将程式放回原项目目录。")
if str(_account_root) not in _account_sys.path:
    _account_sys.path.insert(0, str(_account_root))
_PROJECT_ROOT = str(_account_root)
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
from collections import Counter
from itertools import combinations
import math
import hashlib
import time
import secrets
import subprocess, sys

# =========================================================
# Wild Five 风格 UI 颜色与常量
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

# 扑克牌花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    9: '皇家同花顺', 8: '同花顺', 7: '四条', 6: '葫芦', 5: '同花',
    4: '顺子', 3: '三条', 2: '两对', 1: '对子', 0: '高牌'
}

# 两种模式只改变前注派彩；赔率为净赢倍数，胜庄时另退前注本金。
GAME_MODE_NAMES = {'classic': '经典模式', 'high_payout': '高赔模式'}
ANTE_PAYOUT = {
    'classic': {rank: 1 for rank in range(4, 10)},
    'high_payout': {9: 50, 8: 10, 7: 5, 6: 2, 5: 1, 4: 0},
}

# 奖金注赔率为净赢倍数，中奖另退奖金注本金。
BONUS_PAYOUT = {
    'AA_AA': 1000, 'AA': 30, 'AKs': 25, 'AQs_AJs': 20,
    'AKo': 15, 'KK_QQ_JJ': 10, 'AQo_AJo': 5, 'other_pairs': 3,
}
# 沿用原程式固定大奖金额；皇家同花顺及同花顺按当前奖池比例支付。
PROGRESSIVE_FIXED_AWARDS = {7: 1250, 6: 375, 5: 250}

def project_root() -> str:
    return _PROJECT_ROOT

def user_data_path() -> str:
    return os.path.join(project_root(), "A_Tools/Account/saving_data.json")

def thb_log_path() -> str:
    log_dir = os.path.join(project_root(), 'A_Logs', 'Json')
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, 'Texas_Holdem_Bonus_Poker.json')

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
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:,.2f}"
            break
    save_user_data(users)

# =========================================================
# Jackpot 文件加载与保存（保持不变）
# =========================================================

def load_jackpot():
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
# 扑克牌类与牌堆（完全保留）
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
        parent_dir = project_root()
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
                raise ValueError("洗牌数据格式无效")
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
            print(f"外部洗牌失败，改用安全随机洗牌：{e}")
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
# 手牌评估（完全保留）
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
                return (9, seq2[:5]) if seq2[0] == 14 else (8, seq2[:5])
    counts_list = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    if counts_list[0][1] == 4:
        quad = counts_list[0][0]
        kicker = max(v for v in values if v != quad)
        return (7, [quad, kicker])
    if counts_list[0][1] == 3 and counts_list[1][1] >= 2:
        return (6, [counts_list[0][0], counts_list[1][0]])
    if flush_suit:
        top5 = sorted((c.value for c in flush_cards), reverse=True)[:5]
        return (5, top5)
    if straight_vals:
        return (4, straight_vals)
    if counts_list[0][1] == 3:
        three = counts_list[0][0]
        kickers = [v for v in values if v != three][:2]
        return (3, [three] + kickers)
    pairs = [v for v, cnt in counts_list if cnt == 2]
    if len(pairs) >= 2:
        high, low = pairs[0], pairs[1]
        kicker = max(v for v in values if v not in (high, low))
        return (2, [high, low, kicker])
    if counts_list[0][1] == 2:
        pair = counts_list[0][0]
        kickers = [v for v in values if v != pair][:3]
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

def evaluate_bonus(player_hole, dealer_hole=()):
    """奖金注只看两张底牌；双方尖牌对子优先，单注仅支付一项。"""
    if len(player_hole) != 2:
        return None
    first, second = player_hole
    ranks = {first.rank, second.rank}
    if first.rank == second.rank:
        if first.rank == 'A':
            key = 'AA_AA' if len(dealer_hole) == 2 and all(c.rank == 'A' for c in dealer_hole) else 'AA'
        elif first.rank in ('K', 'Q', 'J'):
            key = 'KK_QQ_JJ'
        else:
            key = 'other_pairs'
    elif ranks == {'A', 'K'}:
        key = 'AKs' if first.suit == second.suit else 'AKo'
    elif ranks in ({'A', 'Q'}, {'A', 'J'}):
        key = 'AQs_AJs' if first.suit == second.suit else 'AQo_AJo'
    else:
        return None
    return key, BONUS_PAYOUT[key]

# =========================================================
# 历史记录保存（只保存，不显示）
# =========================================================

def save_thb_history(deck, player_cards, dealer_cards, community_cards, result_info=None):
    """
    记录当前牌局历史，包含 game_id、统计信息，并只保留最新50局。
    
    参数：
        deck: Deck 实例
        player_cards, dealer_cards, community_cards: Card 列表
        result_info: 字典，可包含 'winner'（'player'/'dealer'/'push'）或 'fold'（弃牌标识）
    """
    log_path = thb_log_path()
    
    # 初始化数据结构
    data = {
        "history_record": {
            "player_win": 0,
            "dealer_win": 0,
            "push": 0,
            "fold": 0,      # 新增弃牌计数
            "game": 0
        },
        "history": []
    }
    
    # 读取已有记录
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    # 新格式：直接使用
                    if "history_record" in loaded:
                        # 确保所有字段存在（兼容旧版本没有fold的情况）
                        for key in data["history_record"]:
                            if key not in loaded["history_record"]:
                                loaded["history_record"][key] = 0
                        data["history_record"] = loaded["history_record"]
                    if "history" in loaded:
                        data["history"] = loaded["history"]
                elif isinstance(loaded, list):
                    # 旧格式：列表 -> 迁移为字典，并重新计算统计
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
    
    # 解析结果，确定 winner 并更新统计
    winner = None
    if result_info:
        # 优先处理弃牌（fold）
        if result_info.get("fold", False):
            winner = "fold"
            stats["fold"] += 1          # 仅增加弃牌计数，不影响 dealer_win
        elif "winner" in result_info:
            winner = result_info["winner"]
            if winner == "player":
                stats["player_win"] += 1
            elif winner == "dealer":
                stats["dealer_win"] += 1
            elif winner == "push":
                stats["push"] += 1
            # 其他未知值不统计
    
    # 构建当前记录
    record = {
        "game_id": new_game_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "deck_order": [str(c) for c in deck.full_deck],
        "cut_position": deck.cut_position,
        "player_cards": [str(c) for c in player_cards],
        "dealer_cards": [str(c) for c in dealer_cards],
        "community_cards": [str(c) for c in community_cards],
        "result": result_info if result_info else {}
    }
    # 确保 result 中有 winner 字段（若已确定）
    if winner is not None:
        record["result"]["winner"] = winner
    elif "winner" not in record["result"]:
        # 没有 winner 信息，可保留为空或不做处理
        pass
    
    # 追加新记录
    data["history"].append(record)
    
    # 只保留最新 50 局
    if len(data["history"]) > 50:
        data["history"] = data["history"][-50:]
    
    # 写回文件
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# =========================================================
# 德州奖金扑克与双手牌界面
# =========================================================


class THBTableGame:
    """两手德州奖金扑克共用庄家、公共牌、余额及原有累积奖池。"""
    SEATS = ('Player1', 'Player2')
    MIN_PROGRESSIVE = 271288.59
    MAIN_BET_KINDS = ('ante', 'flop', 'turn', 'river')
    WAGER_MULTIPLIERS = {'flop': 2, 'turn': 1, 'river': 1}
    STREET_WAGER = {'pre_flop': 'flop', 'flop': 'turn', 'turn': 'river'}

    def __init__(self, mode='classic'):
        if mode not in GAME_MODE_NAMES:
            raise ValueError('未知游戏模式。')
        self.mode = mode
        self.progressive_amount = load_jackpot()[1]
        self.reset_game()

    def set_mode(self, mode):
        if self.stage != 'betting':
            raise ValueError('请在本局结束后切换游戏模式。')
        if mode not in GAME_MODE_NAMES:
            raise ValueError('未知游戏模式。')
        self.mode = mode

    def ante_return(self, stake, rank, winner):
        """只计算前注返还总额；低牌胜庄退前注，各街下注仍独立赔 1:1。"""
        if winner == 'push':
            return stake
        if winner == 'player':
            return stake * (1 + ANTE_PAYOUT[self.mode].get(rank, 0))
        return 0.0

    @property
    def initial_public_count(self):
        return 0

    @staticmethod
    def empty_bet():
        return dict(ante=0.0, bonus=0.0, jackpot=0.0,
                    flop=0.0, turn=0.0, river=0.0)

    def reset_game(self):
        self.deck = None
        self.hands = {s: [] for s in self.SEATS}
        self.dealer_hand, self.public_cards, self.deal_sequence = [], [], []
        self.bets = {s: self.empty_bet() for s in self.SEATS}
        self.decisions = {s: 'inactive' for s in self.SEATS}
        self.stage, self.street = 'betting', 'pre_flop'
        self.settlement = None
        self.refunded_bets = {}
        self.prepaid_seats = set()

    def start_round(self, bets, balance, high_bet_mode=False):
        if self.stage != 'betting':
            raise ValueError('本局尚未结束。')
        minimum, maximum, side_max = (100, 50000, 12500) if high_bet_mode else (10, 10000, 2500)
        prepared, refunded, prepaid = {}, {}, set()
        for seat in self.SEATS:
            b = {k: float(bets[seat].get(k, 0)) for k in self.empty_bet()}
            if any(not math.isfinite(v) or v < 0 or round(v, 2) != v for v in b.values()):
                raise ValueError('下注金额须为非负数，最多保留两位小数。')
            if any(b[k] for k in self.WAGER_MULTIPLIERS):
                if not b['ante'] or any(
                        b[k] != round(b['ante']*m, 2)
                        for k, m in self.WAGER_MULTIPLIERS.items()):
                    raise ValueError('发牌前须同时下注翻牌两倍、转牌一倍及河牌一倍。')
                prepaid.add(seat)
            if not b['ante']:
                if any(b.values()):
                    refunded[seat] = dict(b)
                prepared[seat] = self.empty_bet()
                continue
            if not minimum <= b['ante'] <= maximum:
                raise ValueError(f'每手前注须为 ${minimum:,} 至 ${maximum:,}。')
            if b['bonus'] > side_max:
                raise ValueError('奖金注超出限额。')
            if b['jackpot'] not in (0, 2.5):
                raise ValueError('累进大奖每手固定 $2.50。')
            prepared[seat] = b
        if not any(b['ante'] for b in prepared.values()):
            raise ValueError('请至少为一手牌下前注。')
        charged = round(sum(sum(b.values()) for b in prepared.values()), 2)
        if not math.isfinite(balance) or charged > balance:
            raise ValueError('余额不足以支付所有已选下注。')
        deck = Deck()
        active = tuple(s for s in self.SEATS if prepared[s]['ante'])
        sequence = [('Public', i) for i in range(5)]
        sequence += [(side, i) for i in range(2) for side in (*active, 'Dealer')]
        hands, dealer, public = {s: [] for s in self.SEATS}, [], []
        for side, _index in sequence:
            card = deck.deal(1)[0]
            (public if side == 'Public' else dealer if side == 'Dealer' else hands[side]).append(card)
        self.deck, self.hands, self.dealer_hand, self.public_cards = deck, hands, dealer, public
        self.deal_sequence, self.bets, self.refunded_bets = sequence, prepared, refunded
        self.prepaid_seats = prepaid
        self.decisions = {s: 'inactive' if not prepared[s]['ante'] else
                          'play' if s in prepaid else 'pending' for s in self.SEATS}
        self.street, self.stage = 'pre_flop', 'dealing'
        return charged

    def decide(self, seat, action, balance, multiplier=0):
        if self.stage != 'decision' or self.decisions.get(seat) != 'pending':
            raise ValueError('这手牌当前不能操作。')
        if self.street not in ('pre_flop', 'flop', 'turn'):
            raise ValueError('河牌翻开后不再下注。')
        if action == 'fold' and self.street == 'pre_flop':
            self.decisions[seat] = 'fold'
            return 0.0
        if action == 'check' and self.street in ('flop', 'turn'):
            self.decisions[seat] = 'checked'
            return 0.0
        kind, required = {'pre_flop': ('flop', 2), 'flop': ('turn', 1), 'turn': ('river', 1)}[self.street]
        if action != 'play' or multiplier != required:
            raise ValueError('翻牌前须下注两倍；转牌前及河牌前各可下注一倍。')
        return self.bet_through(seat, kind, balance)

    def bet_through(self, seat, target_kind, balance):
        """一次支付从当前下注圈到所选下注圈的全部金额，先校验再修改。"""
        if self.stage != 'decision' or self.decisions.get(seat) != 'pending':
            raise ValueError('这手牌当前不能操作。')
        current = self.STREET_WAGER.get(self.street)
        kinds = tuple(self.WAGER_MULTIPLIERS)
        if current is None or target_kind not in kinds or kinds.index(target_kind) < kinds.index(current):
            raise ValueError('只能下注当前或之后的下注圈。')
        selected = kinds[kinds.index(current):kinds.index(target_kind)+1]
        amounts = {k: round(self.bets[seat]['ante']*self.WAGER_MULTIPLIERS[k], 2)
                   for k in selected}
        if any(self.bets[seat][k] not in (0, amount) for k, amount in amounts.items()):
            raise ValueError('已有下注金额不符合前注倍数。')
        cost = round(sum(amount-self.bets[seat][k] for k, amount in amounts.items()), 2)
        if not math.isfinite(balance) or cost > balance:
            raise ValueError('余额不足以支付这次全部下注。')
        self.bets[seat].update(amounts)
        self.decisions[seat] = 'play'
        return cost

    def decisions_for_street(self, street):
        """已支付本街的手牌自动通过，其他未弃牌手牌继续决定。"""
        kind = self.STREET_WAGER[street]
        return {s: d if d in ('fold', 'inactive') else
                'play' if self.bets[s][kind] else 'pending'
                for s, d in self.decisions.items()}

    def pool(self, side):
        return (self.dealer_hand if side == 'Dealer' else self.hands[side]) + self.public_cards

    def progressive_hand(self, seat):
        """只能使用该玩家两张底牌及前三张公共牌，固定五张。"""
        cards = self.hands[seat] + self.public_cards[:3]
        if len(self.hands[seat]) != 2 or len(cards) != 5:
            raise ValueError('累进大奖须使用两张玩家底牌及前三张公共牌。')
        return cards

    def settle(self):
        if self.settlement is not None:
            return self.settlement
        if self.stage != 'showdown' or any(d in ('pending', 'checked') for d in self.decisions.values()):
            raise ValueError('所有已下注手牌须先完成决定。')
        dealer_eval, _ = find_best_5(self.pool('Dealer'))
        outcomes, returned, contribution = {}, 0.0, 0.0
        pool = self.progressive_amount
        for seat in self.SEATS:
            if self.decisions[seat] == 'inactive':
                continue
            b = self.bets[seat]
            player_eval, _ = find_best_5(self.pool(seat))
            rank = player_eval[0]
            details = self.empty_bet()
            folded = self.decisions[seat] == 'fold'
            winner = 'fold' if folded else 'player' if player_eval > dealer_eval else 'push' if player_eval == dealer_eval else 'dealer'
            details['ante'] = self.ante_return(b['ante'], rank, winner)
            if winner == 'player':
                for kind in ('flop', 'turn', 'river'):
                    details[kind] = b[kind] * 2
            elif winner == 'push':
                for kind in self.MAIN_BET_KINDS:
                    details[kind] = b[kind]
            # 奖金注及累进大奖不受主局输赢、平局或弃牌影响。
            bonus = evaluate_bonus(self.hands[seat], self.dealer_hand)
            if bonus:
                details['bonus'] = b['bonus'] * (1 + bonus[1])
            pg_cards = self.progressive_hand(seat)
            pg_rank = evaluate_hand(pg_cards)[0]
            if b['jackpot']:
                award = pool if pg_rank == 9 else pool * .1 if pg_rank == 8 else PROGRESSIVE_FIXED_AWARDS.get(pg_rank, 0)
                details['jackpot'] = round(award, 2)
                pool = round(pool - details['jackpot'], 2)
            details = {kind: round(value, 2) for kind, value in details.items()}
            hand_return = round(sum(details.values()), 2)
            outcomes[seat] = dict(details=details, returned=hand_return, winner=winner,
                                  player_rank=rank, dealer_rank=dealer_eval[0],
                                  bonus_combination=bonus[0] if bonus else None,
                                  progressive_rank=pg_rank,
                                  progressive_cards=[str(c) for c in pg_cards])
            returned += hand_return
            contribution += sum(b[k] for k in (*self.MAIN_BET_KINDS, 'bonus')) * .001
            if b['jackpot']:
                contribution += 2.21
        self.progressive_amount = round(max(self.MIN_PROGRESSIVE, pool + contribution), 2)
        self.settlement = dict(hands=outcomes, returned=round(returned, 2), mode=self.mode)
        return self.settlement

class THBGUI(tk.Frame):
    WIDTH, HEIGHT = 1150, 750
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    MODE_TRANSITION_MS = 360
    MODE_FRAME_MS = 16
    MODE_SELECTOR_LEFT = 822
    MODE_SELECTOR_STEP = 147
    MODE_SELECTOR_WIDTH = 145
    DEAL_CARD_MS = 224 / .85
    DEAL_MOVE_MS = (128 / .75) / .85
    BET_CHIP_RADIUS = 16 * 4 / 3
    HOUSE_CHIP_POS = (575, 43)
    TABLE_GREEN = '#4b1e22'
    PROGRESSIVE_LAMP_WIDTH = 122.0 * .8
    ZONE_COLORS = {'Player1':'#2A5541','Player2':'#204536'}
    SEAT_NAMES = {'Player1': '玩家1', 'Player2': '玩家2', 'Dealer': '庄家手牌'}

    HAND_BADGE_RADIUS = 8
    HAND_BADGE_COLORS = {'Player1':'#91E6C4','Player2':'#F4D27B','Dealer':'#D64545'}

    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = username, float(initial_balance)
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game = THBTableGame()
        self.bets = {s: self.game.empty_bet() for s in self.game.SEATS}
        self.last_bet = None
        self.last_win = 0.0
        self._game_instruction_dialog = None
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
        self._mode_transition = None
        self._mode_transition_job = None
        self._mode_indicator_x = float(self.MODE_SELECTOR_LEFT)
        self._mode_weights = {mode: float(mode == self.game.mode) for mode in GAME_MODE_NAMES}
        self._chip_serial = 0
        self._decision_busy = False
        self._settlement_started = False
        self._showdown_started = False
        self._hidden_hands = set()
        self.visual_chips = {}
        self.lamps = {}
        self.last_round_snapshot = None
        self._history_available = False
        self._sorted_sides = set()
        self._face_photos, self._pil_cards, self._flip_photos = {}, {}, {}
        self.card_items, self.bet_spots, self.action_buttons = {}, {}, {}
        self._load_assets()
        self._create_widgets()
        self._refresh()
        self.bind('<Configure>', self._center_table, add='+')
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
        base = os.path.join(project_root(), 'A_Tools', 'Card', folder)
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
        """沿用原 UTH 筹码的 K／M 单位及两位有效数字格式。"""
        from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
        value = Decimal(str(amount)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        if value == Decimal('2.50'):
            return '2.50'
        if abs(value) >= 1000000:
            divisor, suffix = Decimal(1000000), 'M'
        elif abs(value) >= 1000:
            divisor, suffix = Decimal(1000), 'K'
        else:
            label = format(value, 'f')
            return label.rstrip('0').rstrip('.') if '.' in label else label
        scaled = value / divisor
        precision = Decimal(1).scaleb(abs(scaled).adjusted() - 1)
        shown = scaled.quantize(precision, rounding=ROUND_DOWN)
        label = format(shown, 'f')
        if '.' in label:
            label = label.rstrip('0').rstrip('.')
        return label + suffix + ('+' if shown != scaled else '')

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
        if self.game.stage == 'betting' and not self._motion_count and self.last_bet:
            new = {s: self.game.empty_bet() for s in self.game.SEATS}
            minimum, maximum, side_max = (100, 50000, 12500) if self.high_bet_mode else (10, 10000, 2500)
            for seat in self.game.SEATS:
                previous = self.last_bet[seat]
                if previous['ante'] and not minimum <= previous['ante'] <= maximum:
                    messagebox.showwarning('无法重复下注', '上局前注不符合当前限额。', parent=self)
                    return
                if previous['bonus'] > side_max:
                    messagebox.showwarning('无法重复下注', '上局奖金注超出当前限额。', parent=self)
                    return
                for kind in ('ante', 'bonus', 'jackpot'):
                    new[seat][kind] = previous[kind]
                for kind in self.game.WAGER_MULTIPLIERS:
                    new[seat][kind] = previous[kind]
            if self._betting_cost(new) > self.balance:
                messagebox.showwarning('无法重复下注', '余额不足以重复上局下注。', parent=self)
                return
            self._apply_bet_layout(new)


    def select_game_mode(self, mode):
        if (self._closing or self.game.stage != 'betting' or self._motion_count
                or mode == self.game.mode):
            return
        start_x, weights = self._mode_indicator_x, dict(self._mode_weights)
        self.game.set_mode(mode)
        self._cancel_mode_transition_job()
        self._mode_transition = dict(
            started=time.monotonic(), start_x=start_x, weights=weights,
            target_x=self.MODE_SELECTOR_LEFT + list(GAME_MODE_NAMES).index(mode)*self.MODE_SELECTOR_STEP,
        )
        self._refresh()
        self._animate_mode_transition()

    def _mix_mode_color(self, start, target, progress):
        a, b = self.canvas.winfo_rgb(start), self.canvas.winfo_rgb(target)
        return '#' + ''.join(f'{round((x+(y-x)*progress)/257):02x}' for x, y in zip(a, b))

    def _animate_mode_transition(self):
        self._mode_transition_job = None
        if self._closing or self._mode_transition is None:
            return
        transition = self._mode_transition
        progress = min(1.0, max(0.0,
            (time.monotonic()-transition['started'])*1000/self.MODE_TRANSITION_MS))
        eased = progress*progress*(3-2*progress)
        self._mode_indicator_x = transition['start_x'] + (transition['target_x']-transition['start_x'])*eased
        self._mode_weights = {
            mode: weight+(float(mode == self.game.mode)-weight)*eased
            for mode, weight in transition['weights'].items()
        }
        self._refresh_mode_selector()
        if progress >= 1.0:
            self._finish_mode_transition()
        else:
            self._mode_transition_job = self._schedule(self.MODE_FRAME_MS, self._animate_mode_transition)

    def _cancel_mode_transition_job(self):
        if self._mode_transition_job is not None:
            try:
                self.after_cancel(self._mode_transition_job)
            except tk.TclError:
                pass
            self._jobs.discard(self._mode_transition_job)
            self._mode_transition_job = None

    def _finish_mode_transition(self):
        if self._mode_transition is None:
            return
        self._cancel_mode_transition_job()
        self._mode_transition = None
        self._refresh_mode_selector()
        dialog = self._game_instruction_dialog
        if dialog is not None:
            try:
                visible = dialog.winfo_exists()
                dialog.destroy()
            except tk.TclError:
                visible = False
            self._game_instruction_dialog = None
            if visible:
                self.show_game_instructions()

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
            if self.username and self.username not in ('Guest','游客'):
                update_balance_in_json(self.username,self.balance)
            if callable(self.on_balance_change):
                self.on_balance_change(float(self.balance))
        except Exception as exc:
            messagebox.showerror('余额保存失败',str(exc),parent=self)
            return False
        return True

    def start_game(self):
        if self.game.stage!='betting' or self._motion_count:return
        self._finish_mode_transition()
        try:charged=self.game.start_round(self.bets,self.balance,self.high_bet_mode)
        except ValueError as exc:
            messagebox.showwarning('无法开始',str(exc),parent=self);return
        # 所有状态先锁定，避免 ENTER/快速双击重复扣款。
        self.game.stage='progressive'
        self._history_available=False
        self._close_card_sequence()
        self.balance=round(self.balance-charged,2)
        self.bets={s:dict(b) for s,b in self.game.bets.items()}
        self.last_bet={s:dict(b) for s,b in self.bets.items()}
        self._credited=False;self._return_persisted=False;self._settlement_started=False;self._side_resolved=set()
        self._cancel_restart_timer()
        # 发牌前已付满三项的手牌保留盖牌，直至摊牌。
        self._hidden_hands = set(self.game.prepaid_seats)
        self._revealed_public=0
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
            self._reveal_initial_cards()
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

    def _reveal_initial_cards(self):
        # 公共牌接在全部玩家底牌之后，沿用逐张翻牌动画，完成后才开放决策。
        reveal = [(s, i) for s in self.game.SEATS
                  if self.game.hands[s] and s not in self._hidden_hands for i in range(2)]
        reveal += [('Public', i) for i in range(self.game.initial_public_count)]
        self._reveal_next(reveal, 0, self._after_initial_reveal)

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
            self.reset_bets()

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
        # 保留原加勒比的标题 + 三列限红表，改成深绿/金色。
        c = self.canvas
        x0,x1,y0 = 30,349,75
        c.create_rectangle(x0,y0,x1,181,fill=ROOT_BG,outline=GOLD,width=2,tags='limits')
        c.create_rectangle(x0,y0,x1,y0+29,fill=ROOT_BG,outline=GOLD,tags='limits')
        self._text((x0+x1)/2,y0+14,'下注上限',13,PANEL_BG,tags='limits')
        titles = ('前注最低','前注最高','奖金最高')
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

    def _draw_mode_selector(self):
        """沿用 UTH 的金色滑块，置于右上方累进大奖面板下方。"""
        c = self.canvas
        self._text(967, 208, '游戏模式选择', 14, GOLD)
        self._rounded_rectangle(818, 224, 1118, 266, 12,
            fill='#102C22', outline='#627652', width=1)
        self.mode_buttons = {}
        self._mode_hover = self._mode_pressed = None
        for index, (mode, name) in enumerate(GAME_MODE_NAMES.items()):
            left = self.MODE_SELECTOR_LEFT + index*self.MODE_SELECTOR_STEP
            tag = 'mode_option_'+mode
            face = self._rounded_rectangle(left, 228, left+self.MODE_SELECTOR_WIDTH, 262, 8,
                fill='#16372A', outline='', width=1, tags=tag)
            label = self._text(left+self.MODE_SELECTOR_WIDTH/2, 245, name, 12, '#CCD4BF', tags=tag)
            self.mode_buttons[mode] = dict(tag=tag, face=face, text=label, enabled=True)
            for event, action in (('<Enter>', 'enter'), ('<Leave>', 'leave'),
                                  ('<ButtonPress-1>', 'press'), ('<ButtonRelease-1>', 'release')):
                c.tag_bind(tag, event, lambda _e, m=mode, a=action: self._mode_pointer(m, a))
        self.mode_indicator = self._rounded_rectangle(
            self.MODE_SELECTOR_LEFT, 228, self.MODE_SELECTOR_LEFT+self.MODE_SELECTOR_WIDTH, 262, 8,
            fill='#D8B46A', outline='#F0D18D', width=1, tags='mode_indicator')
        self._mode_indicator_shape = tuple(c.coords(self.mode_indicator))
        for button in self.mode_buttons.values():
            c.tag_raise(button['text'])
        for event, action in (('<Enter>', 'enter'), ('<Leave>', 'leave'),
                              ('<ButtonPress-1>', 'press'), ('<ButtonRelease-1>', 'release')):
            c.tag_bind('mode_indicator', event,
                       lambda e, a=action: self._mode_indicator_pointer(e, a))
        self.mode_description_item = self._text(967, 286, '', 9, '#C7CBB2', justify=tk.CENTER)

    def _mode_indicator_pointer(self, event, action):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        for index, mode in enumerate(GAME_MODE_NAMES):
            left = self.MODE_SELECTOR_LEFT + index*self.MODE_SELECTOR_STEP
            if left <= x <= left+self.MODE_SELECTOR_WIDTH and 228 <= y <= 262:
                self._mode_pointer(mode, action)
                return
        self._mode_pointer(None, 'leave')

    def _mode_pointer(self, mode, action):
        enabled = not self._closing and self.game.stage == 'betting' and not self._motion_count
        if action == 'enter':
            self._mode_hover = mode if enabled else None
            self.canvas.configure(cursor='hand2' if enabled else '')
        elif action == 'leave':
            self._mode_hover = self._mode_pressed = None
            self.canvas.configure(cursor='')
        elif action == 'press' and enabled:
            self._mode_pressed = mode
        elif action == 'release':
            pressed, self._mode_pressed = self._mode_pressed, None
            if enabled and mode in GAME_MODE_NAMES and pressed == mode:
                self.select_game_mode(mode)
        self._refresh_mode_selector()

    def _refresh_mode_selector(self):
        enabled = not self._closing and self.game.stage == 'betting' and not self._motion_count
        if self._mode_transition is None:
            self._mode_indicator_x = self.MODE_SELECTOR_LEFT + list(GAME_MODE_NAMES).index(self.game.mode)*self.MODE_SELECTOR_STEP
            self._mode_weights = {mode: float(mode == self.game.mode) for mode in GAME_MODE_NAMES}
        if not enabled:
            self._mode_hover = self._mode_pressed = None
            self.canvas.configure(cursor='')
        for mode, button in self.mode_buttons.items():
            fill = '#16372A'
            foreground = self._mix_mode_color('#CCD4BF' if enabled else '#8B9C8E',
                                              TITLE_FG, self._mode_weights[mode])
            if enabled and self._mode_hover == mode:
                fill = '#2E513C'
            if enabled and self._mode_pressed == mode:
                fill = '#234431'
            button['enabled'] = enabled
            self.canvas.itemconfigure(button['face'], fill=fill, outline='')
            self.canvas.itemconfigure(button['text'], fill=foreground)
        offset = self._mode_indicator_x-self.MODE_SELECTOR_LEFT
        self.canvas.coords(self.mode_indicator, *(
            value+offset if index % 2 == 0 else value
            for index, value in enumerate(self._mode_indicator_shape)))
        indicator_fill = '#D8B46A'
        if enabled and self._mode_hover == self.game.mode:
            indicator_fill = '#E2C37D'
        if enabled and self._mode_pressed == self.game.mode:
            indicator_fill = '#BD9A58'
        self.canvas.itemconfigure(self.mode_indicator, fill=indicator_fill)
        description = {
            'classic': '前注只支付顺子及以上的获胜牌型\n赔付固定1:1',
            'high_payout': '前注只支付同花及以上的获胜牌型\n赔付由1:1到50:1',
        }[self.game.mode]
        self.canvas.itemconfigure(self.mode_description_item, text=description)

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
        if abs(value)>=1000:return THBGUI._compact(value)
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
        # 动画与实际取牌共用同一顺序，先发五张公共牌，再轮流发两轮玩家和庄家手牌。
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
        jackpot_won=any(outcome['details']['jackpot']>0 for outcome in self.game.settlement['hands'].values())
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
        self.game.reset_game()
        self._hidden_hands.clear()
        self.selected_discards = {s:None for s in self.game.SEATS}
        self._card_origins.clear(); self._discard_photos.clear()
        self._faded_photos.clear(); self._final_usage.clear()
        self._hand_usage_keys.clear()
        self._settled_card_photos.clear()
        self._usage_owner = None
        self._default_usage_owner = 'Dealer'
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

    def _draw_bonus_spot(self, seat, kind, cx, cy, label, radius):
        tag = 'spot_' + seat + '_' + kind
        border = self.canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
            fill=self.ZONE_COLORS[seat], outline=GOLD, width=3, tags=tag)
        self.canvas.create_oval(cx-radius+5, cy-radius+5, cx+radius-5, cy+radius-5,
            outline='#A3B190', width=1, tags=tag)
        self._register_spot(seat, kind, cx, cy, border, label)
        if kind in ('flop', 'turn', 'river'):
            self.canvas.itemconfigure(self.bet_spots[(seat, kind)]['label'], fill='#FFE275')

    def _reference_curve(self, seat, origin, scale, start, segments, color):
        """以原图坐标描绘三次贝塞尔曲线，不用三角形拼接外框。"""
        coordinates = []
        for x, y in (start, *(point for segment in segments for point in segment)):
            coordinates.extend((origin[0] + x*scale, origin[1] + y*scale))
        return self.canvas.create_polygon(
            *coordinates, smooth='raw', splinesteps=48, fill=color,
            outline='#24558B', width=1.15*scale,
            tags=('table_marks', 'reference_outline_'+seat))

    def _draw_reference_spot(self, seat, kind, origin, scale, center, label):
        """按参考图保留圆形下注位的黑、金、绿色外框。"""
        cx, cy = origin[0]+center[0]*scale, origin[1]+center[1]*scale
        tag = 'spot_'+seat+'_'+kind
        self.canvas.create_oval(cx-22.5*scale, cy-22.5*scale,
            cx+22.5*scale, cy+22.5*scale, fill='#006C50',
            outline='#06342D', width=1.2*scale, tags=tag)
        border = self.canvas.create_oval(cx-21.4*scale, cy-21.4*scale,
            cx+21.4*scale, cy+21.4*scale, outline='#A59B29',
            width=1.0*scale, tags=tag)
        self.canvas.create_oval(cx-20.0*scale, cy-20.0*scale,
            cx+20.0*scale, cy+20.0*scale, outline='#3A9470',
            width=1.3*scale, tags=tag)
        self.canvas.create_oval(cx-18.7*scale, cy-18.7*scale,
            cx+18.7*scale, cy+18.7*scale, outline='#164E40',
            width=1.0*scale, tags=tag)
        self._register_spot(seat, kind, cx, cy, border, label)
        self.canvas.itemconfigure(self.bet_spots[(seat,kind)]['label'], fill='#F2ED25')

    def _draw_reference_layout(self, seat, x0):
        """依据上传图的 183×160 坐标，等比例还原蓝红轮廓及下注位置。"""
        origin, scale = (x0+208, 341), 1.7
        red_segments = (
            ((20,68),(32,68),(48,68)),
            ((84,66),(130,67),(169,66)),
            ((169,75),(171,84),(171,91)),
            ((170,98),(164,106),(158,108)),
            ((155,110),(150,112),(146,112)),
            ((143,112),(141,113),(139,114)),
            ((139,116),(141,118),(143,119)),
            ((141,120),(138,120),(136,119)),
            ((133,118),(131,115),(128,114)),
            ((124,112),(117,110),(113,114)),
            ((109,116),(104,123),(101,127)),
            ((99,128),(96,127),(95,125)),
            ((92,119),(88,116),(84,112)),
            ((78,108),(70,103),(59,101)),
            ((57,102),(56,111),(54,114)),
            ((53,117),(51,117),(48,117)),
            ((45,117),(40,114),(37,111)),
            ((34,108),(28,101),(26,97)),
            ((23,95),(18,88),(17,86)),
            ((12,82),(9,75),(7,69)),
        )
        blue_segments = (
            ((55.3,5),(65.7,5),(76,5)),
            ((76,13),(76,21),(77,29)),
            ((82,31),(94,35),(99,36)),
            ((104,36),(106,34),(107,33)),
            ((109,34),(113,37),(117,37)),
            ((120,36),(123,33),(125,33)),
            ((129,36),(136,39),(141,39)),
            ((145,40),(150,40),(153,41)),
            ((154,46),(155,51),(157,57)),
            ((160,61),(166,64),(169,66)),
            ((130,66),(86,66),(49,67)),
            ((48,61),(47,56),(47,49)),
            ((46,35),(46,20),(45,5)),
        )
        self._reference_curve(seat,origin,scale,(7,69),red_segments,'#F11C30')
        self._reference_curve(seat,origin,scale,(45,5),blue_segments,'#2363AA')
        # 星形奖金注保持在原图标识的位置；前注在原图下方筹码的位置。
        bonus_tag = 'spot_'+seat+'_bonus'
        star = ((60,16),(65,31),(82,31),(68,41),(73,55),
                (60,46),(47,55),(52,41),(39,31),(55,31))
        points = tuple(value for x,y in star
                       for value in (origin[0]+x*scale,origin[1]+y*scale))
        star_border = self.canvas.create_polygon(*points,fill='#FAFFFF',
            outline='#BCE1E8',width=.8*scale,tags=bonus_tag)
        bonus_center = (origin[0]+60*scale,origin[1]+36*scale)
        self._text(bonus_center[0]+1.5,bonus_center[1]+1.5,'奖金',16,
                   '#655D07',tags=bonus_tag)
        self._register_spot(seat,'bonus',*bonus_center,star_border,'奖金')
        self.canvas.itemconfigure(self.bet_spots[(seat,'bonus')]['label'],
                                  fill='#F5EF18',font=('Arial',16,'bold'))
        for kind,center,label in (
                ('flop',(44.5,86),'翻牌'),
                ('turn',(95,86),'转牌'),
                ('river',(147,86),'河牌'),
                ('ante',(120,134),'前注')):
            self._draw_reference_spot(seat,kind,origin,scale,center,label)

    def card_size(self, side):
        return self.CARD_WIDTH,self.CARD_HEIGHT

    def _fade_card_item(self, item, source):
        # 用alpha淡化，不破坏牌面原图，也不把透明PNG的边缘铺成白底。
        faded = source.convert('RGBA').copy()
        faded.putalpha(faded.getchannel('A').point(lambda value:round(value*.45)))
        photo = ImageTk.PhotoImage(faded,master=self)
        self._faded_photos[item] = photo
        self.canvas.itemconfigure(item,image=photo)

    def _instruction_pages(self):
        """沿用 UTH 的五页目录、规则卡片、赔率表及牌型图片格式。"""
        mode_name = GAME_MODE_NAMES[self.game.mode]
        if self.game.mode == 'high_payout':
            ante_rule = ('前注只在胜庄时按牌型派彩：皇家同花顺 50:1、同花顺 10:1、'
                         '四条 5:1、葫芦 2:1、同花 1:1；顺子及以下只退前注本金。')
            ante_win_rows = [
                ['玩家胜，'+HAND_RANK_NAMES[rank], f'{odds} : 1', '各 1 : 1']
                for rank, odds in ANTE_PAYOUT['high_payout'].items() if odds
            ] + [['玩家胜，顺子或以下', '只退前注本金', '各 1 : 1']]
            ante_example = ('高赔模式葫芦胜庄',
                '前注十、翻牌二十、转牌十、河牌十，共五十。以葫芦胜庄时，'
                '前注赔 2:1 并退本金，共返还三十；其余三项共返还八十，主局共返还一百一十，净赢六十。')
        else:
            ante_rule = '前注在顺子或以上胜庄时赔 1:1；较低牌型胜庄只退前注本金。'
            ante_win_rows = [
                ['玩家胜，顺子或以上', '1 : 1', '各 1 : 1'],
                ['玩家胜，低于顺子', '只退前注本金', '各 1 : 1'],
            ]
            ante_example = ('经典模式顺子胜庄',
                '前注十、翻牌二十、转牌十、河牌十，共五十。以顺子胜庄时，'
                '前注及三项各街下注各赔 1:1 并退本金，主局共返还一百，净赢五十。')
        main_rows = ante_win_rows + [
            ['玩家输', '输掉本金', '各输掉本金'],
            ['双方平局', '退回本金', '各退回本金'],
            ['玩家弃牌', '输掉前注', '没有后续下注'],
        ]
        rank_rows = [
            ["1","皇家同花顺","同花色的 10-J-Q-K-A",["__CARD_IMAGES__",[["♥","10"],["♥","J"],["♥","Q"],["♥","K"],["♥","A"]]]],
            ["2","同花顺","同花色顺子",["__CARD_IMAGES__",[["♥","6"],["♥","7"],["♥","8"],["♥","9"],["♥","10"]]]],
            ["3","四条","四张同点",["__CARD_IMAGES__",[["♥","A"],["♣","A"],["♦","A"],["♠","A"],["♥","K"]]]],
            ["4","葫芦","三条 + 一对",["__CARD_IMAGES__",[["♥","A"],["♣","A"],["♦","A"],["♥","K"],["♠","K"]]]],
            ["5","同花","五张同花色",["__CARD_IMAGES__",[["♣","K"],["♣","10"],["♣","8"],["♣","7"],["♣","5"]]]],
            ["6","顺子","五张连续",["__CARD_IMAGES__",[["♥","6"],["♠","7"],["♦","8"],["♣","9"],["♠","10"]]]],
            ["7","三条","三张同点",["__CARD_IMAGES__",[["♥","A"],["♣","A"],["♠","A"],["♠","K"],["♥","Q"]]]],
            ["8","两对","两组对子",["__CARD_IMAGES__",[["♥","A"],["♣","A"],["♦","K"],["♠","K"],["♥","7"]]]],
            ["9","一对","一组对子",["__CARD_IMAGES__",[["♥","A"],["♣","A"],["♠","K"],["♣","J"],["♥","7"]]]],
            ["10","高牌","无任何组合",["__CARD_IMAGES__",[["♥","A"],["♣","K"],["♦","Q"],["♠","9"],["♥","7"]]]]
        ]
        return [
            ('玩法', '了解德州奖金扑克从下注到结算的完整顺序。', [
                ['游戏目标', '', [
                    ('本局目标', '玩家与庄家各从两张手牌及五张公共牌中选出最佳五张牌，比较大小。庄家无需最低牌型。'),
                    ('两手分别结算', '玩家1、玩家2为同一账户的两手牌，共用庄家、公共牌与余额；至少一手下前注。')], []],
                ['游戏模式', f'当前模式：{mode_name}', [
                    ('选择模式', '右上方累进大奖下方可选择经典模式或高赔模式，只能在下注阶段、筹码停止移动时切换；两手共用同一模式。新一局保留所选模式，重新打开游戏时默认为经典模式。'),
                    ('前注派彩', ante_rule),
                    ('模式影响范围', '模式只改变前注派彩。翻牌、转牌、河牌注胜庄仍各赔 1:1 并退本金；奖金注及累进大奖按原规则独立结算。')], []],
                ['一局如何进行', '', [
                    ('玩家下注', '先选择筹码，再点击前注圈或奖金星形区；累进大奖灯为每手固定 $2.50 的参与开关。发牌前点击任意翻牌、转牌或河牌圈，都会下齐三项；右键任一圈可一起撤销三项。开局时一次扣除所有已选下注。'),
                    ('玩家决策', '使用手牌下方的下注、过牌或弃牌按钮，也可点击本街或后续亮边的下注圈，提前支付到选定阶段。已经支付的阶段自动通过，未支付的阶段仍须决定；两手完成本街决定后才继续翻牌。'),
                    ('庄家开牌', '河牌翻开后不再下注；庄家亮牌，两手分别与庄家比牌。'),
                    ('结算', '前注、各街下注、奖金注及累进大奖分别结算；回收筹码后统一入账。再来一局按钮右键可查看上局牌序。')], []],
                ['一局完整流程', '', [
                    ('下注阶段', '前注：每手必下，普通限红 $10 起。\n奖金注：可选，按最初两张玩家手牌结算。\n累进大奖：可选，每手每局 $2.50，按两张玩家手牌加前三张公共牌结算。'),
                    ('发牌', '五张公共牌先背面朝下发出；每手玩家与庄家各两张底牌。普通手牌翻开后开放决定。发牌前已付满三项的手牌保持盖牌，不再逐街决定，直到摊牌时才翻开结算。'),
                    ('翻牌前决策', '看过两张手牌后：\n下注前注的两倍，放到翻牌圈；或弃牌，输掉前注。\n奖金注及累进大奖仍按各自规则结算。'),
                    ('翻牌圈决策', '看过前三张公共牌后：\n下注前注的一倍，放到转牌圈；或过牌。\n然后翻开第四张公共牌。'),
                    ('转牌圈决策', '看过第四张公共牌后：\n下注前注的一倍，放到河牌圈；或过牌。\n然后翻开第五张公共牌。'),
                    ('摊牌与比牌', '双方各从七张牌中选出最佳五张。\n先比牌型，再比较组成牌的点数与踢脚牌；完全相同为平局。'),
                    ('结算与再来一局', f'玩家胜出：翻牌、转牌、河牌注各赔 1:1 并退本金。{ante_rule}\n玩家输牌：输掉前注及已下的各街下注。\n平局：前注及各街下注只退本金。\n弃牌：只输掉前注，附加注独立结算。\n结算后 30 秒无操作，自动回收筹码并进入下注阶段；累进大奖中奖时不自动倒计时。')], []],
                ['提前下注操作', 'MAX 按前注倍数计算：翻牌两倍、转牌一倍、河牌一倍；已支付的金额不会再扣一次。', [], [
                    ('点击后续下注圈的效果', ['操作阶段', '点击位置', '自动下注'], [
                        ['发牌前下注', '任意翻牌、转牌或河牌圈', '三项全部下注，共前注四倍；该手盖牌至摊牌'],
                        ['翻牌下注阶段，公共牌未翻开', '转牌圈', '翻牌两倍 + 转牌一倍；河牌注仍需决定'],
                        ['翻牌下注阶段，公共牌未翻开', '河牌圈', '翻牌两倍 + 转牌一倍 + 河牌一倍'],
                        ['转牌下注阶段，已看过前三张公共牌', '河牌圈', '转牌一倍 + 河牌一倍']])]],
                ['发牌顺序', '', [
                    ('公共牌', '共五张；有未支付的阶段时，依次翻开前三张、第四张、第五张。所有活跃手牌已支付余下全部下注时，直接翻完公共牌并摊牌。'),
                    ('玩家手牌', '每手两张；普通手牌发完后翻开。发牌前已选满三项的手牌保留盖牌至摊牌，不会通过玩家标题提前显示牌型。'),
                    ('庄家手牌', '两张；摊牌时才翻开。')], []],
                ['三个决策点', '未提前支付时按下表决定；已支付的阶段自动通过。', [], [
                    ('下注选择与随后翻牌', ['决策点', '可用选择', '随后翻牌'], [
                        ['翻牌前', '下注前注两倍，或弃牌', '前三张公共牌'],
                        ['翻牌圈', '下注前注一倍，或过牌', '第四张公共牌'],
                        ['转牌圈', '下注前注一倍，或过牌', '第五张公共牌'],
                        ['河牌翻开后', '不再下注', '庄家亮牌并结算']])]]
            ]),
            ('下注 & 限红', '普通限红如下；点击主界面限红表可切换高额下注，密码为当前系统时间的四位时分。', [
                ['下注项目', '', [], [
                    ('下注项目与限红', ['项目', '限红', '作用'], [
                        ['前注', '普通：$10–$10,000\n高额：$100–$50,000',
                         '每手必下，作为后续各街下注的基数。\n'+ante_rule],
                        ['翻牌注', '前注的两倍',
                         '常规在看到两张玩家手牌后下注，亦可在发牌前选满三项。\n不下注则弃牌；胜庄时赔 1:1。'],
                        ['转牌注', '前注的一倍',
                         '常规看完前三张公共牌后下注或过牌，亦可提前支付。\n胜庄时赔 1:1。'],
                        ['河牌注', '前注的一倍',
                         '常规看完第四张公共牌后下注或过牌，亦可提前支付。\n胜庄时赔 1:1。'],
                        ['奖金注', '普通：最高 $2,500\n高额：最高 $12,500',
                         '发牌前下注，按两张玩家手牌派彩。\n最高奖同时检查庄家两张手牌；弃牌仍可中奖。'],
                        ['累进大奖', '每手每局 $2.50',
                         '发牌前点击大奖灯参与。\n只用两张玩家手牌加前三张公共牌，共五张。']])]],
                ['金额与操作', '', [
                    ('最大主局下注', '前注十、翻牌二十、转牌十、河牌十，共五十；奖金注与累进大奖另计。'),
                    ('逐街扣款', '开局时扣除所有发牌前已选下注。游戏中点击后续下注圈，一次支付涉及的全部金额，之后自动通过已付阶段，不会重复扣款。余额不足时整次操作取消，可按当前阶段规则弃牌或过牌。'),
                    ('重复下注', '重复上局发牌前设置，包括预先选满的三项；游戏开始后追加的下注不会被重复。'),
                    ('筹码金额', '下注圈内的筹码显示当前已支付或已选的金额；提前下注时，各项筹码分别放入对应圈内。')], []]
            ]),
            ('获胜条件 & 赔率', '主局、奖金注及累进大奖独立结算；按下列表格核对条件、赔率与返还。', [
                ['比牌规则', '', [], [
                    ('比牌与庄家资格', ['判断', '规则'], [
                        ['庄家资格', '无需最低牌型，直接与玩家比牌。'],
                        ['比大小', '双方从两张手牌及五张公共牌中选出最佳五张。\n先比牌型，再比较点数及踢脚牌；花色不分大小。'],
                        ['完全相同', '平局，主局各项退回本金。']])]],
                ['主局赔率表', f'当前模式：{mode_name}。赔率为净赢金额，另退该项本金；前注退本只指前注，各街胜庄仍赔 1:1。', [], [
                    ('前注与各街下注结算', ['获胜条件', '前注', '翻牌、转牌、河牌注'], main_rows)]],
                ['奖金注赔率表', '只看最初两张玩家手牌；最高奖同时检查庄家两张手牌。赔率为净赢金额，中奖另退本金。', [], [
                    ('奖金注赔率与返还', ['手牌组合', '赔率', '返还公式'], [
                        ['玩家与庄家同时 A-A', '1,000 : 1', '下注 × 1,001'],
                        ['玩家 A-A，庄家不是 A-A', '30 : 1', '下注 × 31'],
                        ['A-K（同花）', '25 : 1', '下注 × 26'],
                        ['A-Q / A-J（同花）', '20 : 1', '下注 × 21'],
                        ['A-K（不同花）', '15 : 1', '下注 × 16'],
                        ['K-K / Q-Q / J-J', '10 : 1', '下注 × 11'],
                        ['A-Q / A-J（不同花）', '5 : 1', '下注 × 6'],
                        ['2-2 至 10-10', '3 : 1', '下注 × 4'],
                        ['其他手牌', '未中奖', '本金归庄']])]],
                ['累进大奖赔率表', '大奖赔付为实际返还总额，不另退大奖下注本金。', [], [
                    ('参与与评估方式', ['情形／项目', '结算规则'], [
                        ['参与条件', '发牌前每手固定下注 $2.50。'],
                        ['指定五张牌', '两张玩家手牌 + 前三张公共牌。\n第四、第五张公共牌及庄家手牌均不参与。'],
                        ['主局输牌或弃牌', '大奖资格仍有效，按指定五张牌独立结算。']]),
                    ('指定五张牌的奖励', ['牌型', '返还金额'], [
                        ['皇家同花顺', '当前奖池全额'],
                        ['同花顺', '当前奖池的百分之十'],
                        ['四条', '$1,250'],
                        ['葫芦', '$375'],
                        ['同花', '$250'],
                        ['其他牌型', '未中奖']])]],
                ['结算示例', '', [
                    ante_example,
                    ('低于顺子胜庄', '前注十、翻牌二十、转牌十、河牌十，共五十。若以对子胜庄，前注退十，其余三项各赔 1:1，共返还九十，主局净赢四十。'),
                    ('弃牌后奖金仍有效', '前注十、奖金注十，拿到 2-2 后弃牌：前注损失十，奖金注净赢三十并退本金十，整局净赢二十。')], []]
            ]),
            ('牌型等级表', '牌型由强到弱排列；同级牌型继续比较相关点数。', [
                ['10 种牌型', '下方图片展示牌型示例；同一牌型也可能由其他牌面组成。', [], [
                    ('牌型与示例', ['等级', '牌型', '说明', '牌例'], rank_rows)]]
            ]),
            ('特别事项', '补充说明手牌使用方式、独立结算及特殊金额规则。', [
                ['补充说明', '', [
                    ('A的双重身份', 'A可作最大（10-J-Q-K-A），亦可作最小（A-2-3-4-5）。\n不能用 K-A-2 连成顺子。'),
                    ('主局手牌使用数量', '最佳五张牌可使用零张、一张或两张玩家手牌。'),
                    ('累进大奖固定五张', '必须使用两张玩家手牌加前三张公共牌。\n不从七张牌另选五张，后两张公共牌不能补成大奖牌型。')], []],
                ['特殊下注规则', '', [
                    ('前注退本', '前注表内的退本只针对前注本身。只要主局胜庄，已下的翻牌、转牌、河牌注仍各赔 1:1 并退本金；平局时主局各项才全部只退本金。'),
                    ('奖金注与弃牌分开计算', '主局输牌、平局或弃牌，都不会取消奖金注；奖金注仅按最初两张手牌及其赔率表结算。'),
                    ('奖金只赔一项', '玩家与庄家同时 A-A 时，只赔最高奖，不再叠加玩家 A-A 的赔率。'),
                    ('累进大奖独立结算', '主局输赢、平局或弃牌都不影响已下注的大奖资格。'),
                    ('赔率与返还', '主局及奖金注的赔率表示净赢金额，中奖另退本金。\n累进大奖表列金额为返还总额，不另退 $2.50 本金。'),
                    ('未下前注的手牌', '只有已下前注的手牌参与牌局；未下前注的手牌，其附加注不会单独开局。'),
                    ('高额下注与重复下注', '限红只在下注阶段切换，切换时清除本局及上局重复下注设置。重复下注仅重复发牌前项目，包含发牌前的全额下注设置；其他未支付的阶段仍需决定。')], []]
            ])
        ]

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

        instruction_title = f'德州奖金扑克 · {GAME_MODE_NAMES[self.game.mode]} · 玩法说明'
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

    def _center_table(self, event=None):
        # Keep the original 1150×750 composition centered when embedded.
        self.canvas.place(x=max(0, (self.winfo_width()-self.WIDTH)//2),
                          y=max(0, (self.winfo_height()-self.HEIGHT)//2),
                          width=self.WIDTH, height=self.HEIGHT)

    def _create_widgets(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=ROOT_BG, highlightthickness=0)
        self.canvas.place(x=0, y=0, width=self.WIDTH, height=self.HEIGHT)
        self.control_buttons = {}
        self.selected_discards = {s: None for s in self.game.SEATS}
        self._card_origins, self._discard_photos = {}, {}
        self._faded_photos, self._final_usage = {}, {}
        self._hand_usage_keys, self._settled_card_photos = {}, {}
        self._usage_owner, self._default_usage_owner = None, 'Dealer'
        self.canvas.bind('<Motion>', self._on_hand_usage_hover, add='+')
        self.canvas.bind('<Leave>', self._on_hand_usage_leave, add='+')
        self._revealed_public = 0
        c = self.canvas
        self._text(187, 44, '德州奖金扑克', 18, GOLD)
        c.create_rectangle(465, 10, 685, 163, fill=self.TABLE_GREEN, outline='')
        self.title_items = {'Dealer': self._text(575, 23, '庄家', 16, PANEL_BG)}
        self._draw_limit_table()
        self._text(957, 44, 'Texas Hold’em Bonus Poker', 14, GOLD)
        self._draw_progressive_panel()
        c.create_rectangle(22, 191, 1128, 309, fill=ROOT_BG, outline='#65784B')
        c.create_line(25, 192, 1125, 192, fill='#E0C879', width=2)
        c.create_line(25, 308, 1125, 308, fill='#0C241B', width=2)
        self._text(182, 229, '各街下注胜庄，赔付1:1', 16, GOLD)
        self.street_item = self._text(182, 279, '下注阶段', 13, PANEL_BG)
        self._draw_mode_selector()
        c.create_polygon(366,173,784,173,798,173,798,187,798,287,798,301,
            784,301,366,301,352,301,352,287,352,187,352,173,
            smooth=True, splinesteps=16, fill='#234838', outline='#667B55', width=1)
        for seat, x0, x1 in (('Player1', 22, 566), ('Player2', 582, 1128)):
            c.create_rectangle(x0,316,x1,617,fill=self.ZONE_COLORS[seat],outline='')
            self.title_items[seat] = self._text(x0+110,330,self.SEAT_NAMES[seat],18,PANEL_BG)
            self._draw_reference_layout(seat,x0)
            # 在上版位置继续左移 10px、上移 5px。
            self._draw_progressive_lamp(seat, x0+269.5-30-10, 575-5)
            # UTH 两颗按钮共用上方两张手牌的中线。
            button_cx = (self.card_position(seat, 0)[0]+
                         self.card_position(seat, 1)[0]+self.CARD_WIDTH)/2
            button_cy = 556
            button_top = button_cy-(58*2+11)/2
            for action, offset, caption, color in (
                    ('bet',0,'下注两倍','#397A48'),
                    ('check',69,'弃牌','#9B403A')):
                top = button_top+offset
                self.action_buttons[(seat,action)] = self.create_control_button(
                    button_cx-59.5,top,button_cx+59.5,top+58,caption,
                    lambda s=seat,a=action:self._action_click(s,a),
                    color,font_size=14,draw_shadow=False)
        self._draw_bottom_controls()
        for side in ('Dealer', *self.game.SEATS, 'Public'):
            for index in range(5 if side == 'Public' else 2):
                x, y = self.card_position(side,index)
                w, h = self.card_size(side)
                c.create_rectangle(x,y,x+w,y+h,outline='#B59C6A' if side=='Public' else '#7B9374',
                                   dash=(3,3),tags='card_slots')

    def card_position(self, side, index):
        if side == 'Public':
            return 363+index*86, 181
        if side == 'Dealer':
            return 489+index*92, 40
        return (40 if side == 'Player1' else 600)+index*92, 347

    @staticmethod
    def _card_image_key(card):
        return card.suit, card.rank

    def _refresh(self):
        c = self.canvas
        self._refresh_mode_selector()
        c.itemconfigure(self.balance_item, text=f'余额：${self.balance:,.2f}')
        total = round(sum(sum(b.values()) for b in self.bets.values()), 2)
        c.itemconfigure(self.total_item, text=f'本局下注：${total:,.2f}' if total else f'上局返还：${self.last_win:,.2f}')
        limits = ('$100','$50,000','$12,500') if self.high_bet_mode else ('$10','$10,000','$2,500')
        for item, value in zip(self.limit_value_items,limits):
            c.itemconfigure(item,text=value)
        self._render_chips()
        betting = self.game.stage == 'betting' and self._motion_count == 0
        self.set_control_button_state(self.clear_button,betting)
        self.set_control_button_state(self.repeat_button,betting and bool(self.last_bet))
        self.set_control_button_state(self.start_button,betting)
        restarting = self.game.stage in ('await_restart','returning','credit_pending','sweeping')
        c.itemconfigure(self.repeat_button,state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button,state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button,state='normal' if restarting else 'hidden')
        self.set_control_button_state(self.restart_button,self.game.stage in ('await_restart','credit_pending'))
        street = 'pre_flop' if self.game.stage == 'betting' else self.game.street
        multiplier = 2 if street == 'pre_flop' else 1
        for seat in self.game.SEATS:
            ready = (self.game.stage == 'decision' and not self._decision_busy
                     and not self._motion_count and self.game.decisions[seat] == 'pending')
            for action in ('bet','check'):
                tag = self.action_buttons[(seat,action)]
                button = self.control_buttons[tag]
                caption = ('下注两倍' if multiplier == 2 else '下注一倍') if action == 'bet' else ('弃牌' if street == 'pre_flop' else '过牌')
                c.itemconfigure(button['text'],text=caption)
                if action == 'check':
                    button['fill'] = '#9B403A' if street == 'pre_flop' else DARK_BLUE
                affordable = action == 'check' or self.game.bets[seat]['ante']*multiplier <= self.balance
                self.set_control_button_state(tag,ready and affordable)
            for kind in ('flop','turn','river'):
                kinds = tuple(self.game.WAGER_MULTIPLIERS)
                current = self.game.STREET_WAGER.get(street)
                available = ready and current in kinds and kinds.index(kind) >= kinds.index(current)
                active = available or betting and bool(self.bets[seat][kind])
                c.itemconfigure(self.bet_spots[(seat,kind)]['border'],outline='#FFF3AA' if active else '#A59B29',width=3 if active else 1.7)
        caption = '下注阶段' if self.game.stage == 'betting' else '已结算' if restarting else '摊牌结算' if self.game.stage in ('showdown','settling') else {
            'pre_flop':'翻牌前 · 两倍或弃牌', 'flop':'转牌前 · 一倍或过牌', 'turn':'河牌前 · 一倍或过牌'}[street]
        c.itemconfigure(self.street_item,text=caption)
        self._status(caption)

    def _after_initial_reveal(self):
        self._revealed_public = self.game.initial_public_count
        self.game.stage = 'decision'
        self._update_visible_titles()
        self._refresh()
        self._maybe_showdown()

    def _action_click(self, seat, action):
        if self.game.stage != 'decision':
            return
        if action == 'check':
            self._decide(seat,'fold' if self.game.street == 'pre_flop' else 'check')
        elif action == 'bet':
            self.raise_action(2 if self.game.street == 'pre_flop' else 1,seat)

    def raise_action(self, multiplier, seat='Player1'):
        self._decide(seat,'play',multiplier)

    def play_action(self, multiplier=0, seat='Player1'):
        self._decide(seat,'play' if multiplier else 'check',multiplier)

    @staticmethod
    def _betting_cost(bets):
        return round(sum(sum(b.values()) for b in bets.values()),2)


    def add_chip_to_bet(self, seat, kind):
        if self._motion_count or self._decision_busy:
            return
        if self.game.stage == 'decision':
            kinds = tuple(self.game.WAGER_MULTIPLIERS)
            current = self.game.STREET_WAGER.get(self.game.street)
            if kind in kinds and current in kinds and kinds.index(kind) >= kinds.index(current):
                self._decide(seat,'play',target_kind=kind)
            return
        if self.game.stage != 'betting' or kind not in self.game.empty_bet():
            return
        new = {s:dict(b) for s,b in self.bets.items()}
        b = new[seat]
        prepaid = any(b[k] for k in self.game.WAGER_MULTIPLIERS)
        if kind in self.game.WAGER_MULTIPLIERS:
            if not b['ante']:
                return
            b.update({k: round(b['ante']*m, 2)
                      for k, m in self.game.WAGER_MULTIPLIERS.items()})
        elif kind == 'jackpot':
            b[kind] = 0 if b[kind] else 2.5
        else:
            limit = (50000 if self.high_bet_mode else 10000) if kind == 'ante' else (12500 if self.high_bet_mode else 2500)
            b[kind] = min(limit,round(b[kind]+self.selected_chip,2))
            if kind == 'ante' and prepaid:
                b.update({k: round(b['ante']*m, 2)
                          for k, m in self.game.WAGER_MULTIPLIERS.items()})
        if self._betting_cost(new) > self.balance:
            messagebox.showwarning('无法下注','余额不足以支付这些下注。',parent=self)
            return
        self._apply_bet_layout(new)

    def reset_single_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count or kind not in self.game.empty_bet():
            return
        new = {s:dict(b) for s,b in self.bets.items()}
        if kind in ('ante', *self.game.WAGER_MULTIPLIERS):
            for wager in self.game.WAGER_MULTIPLIERS:
                new[seat][wager] = 0.0
        if kind not in self.game.WAGER_MULTIPLIERS:
            new[seat][kind] = 0.0
        self._apply_bet_layout(new)

    def fold_action(self, seat='Player1'):
        self._decide(seat, 'fold')

    def _decide(self, seat, action, multiplier=0, target_kind=None):
        if (self.game.stage != 'decision' or self._decision_busy or self._motion_count
                or self.game.decisions.get(seat) != 'pending'):
            return
        previous = dict(self.game.bets[seat])
        try:
            cost = (self.game.bet_through(seat,target_kind,self.balance)
                    if action == 'play' and target_kind is not None else
                    self.game.decide(seat,action,self.balance,multiplier))
        except ValueError as exc:
            messagebox.showwarning('无法操作',str(exc),parent=self)
            return
        self._decision_busy = True
        self.balance = round(self.balance-cost,2)
        self.bets[seat] = dict(self.game.bets[seat])
        self._persist_balance()
        self._update_visible_titles()
        self._refresh()
        def done():
            self._decision_busy = False
            self._refresh()
            self._maybe_showdown()
        if action == 'play':
            added = {k: self.game.bets[seat][k]-previous[k]
                     for k in self.game.WAGER_MULTIPLIERS
                     if self.game.bets[seat][k] > previous[k]}
            def arrived():
                for kind in added:
                    self._set_visual(seat,kind,'stake',self.game.bets[seat][kind])
                done()
            transfers = [dict(amount=amount,start=self._rack_position(),
                              target=self.bet_spots[(seat,kind)]['center'])
                         for kind, amount in added.items()]
            self._run_chip_batch(transfers,arrived)
        elif action == 'fold':
            transfers = []
            # 只收走前注；奖金筹码保留，大奖资格也继续有效。
            for main_kind in self.game.MAIN_BET_KINDS:
                chip = self.visual_chips.pop((seat,main_kind,'stake'),None)
                if chip:
                    transfers.append(dict(amount=chip['amount'],start=chip['xy'],target=self.HOUSE_CHIP_POS,duration=280))
            self._run_chip_batch(transfers,done)
        else:
            done()

    def _maybe_showdown(self):
        if self._decision_busy or self._showdown_started or self.game.stage != 'decision':
            return
        if 'pending' in self.game.decisions.values():
            return
        active = [s for s,d in self.game.decisions.items() if d not in ('fold','inactive')]
        future = {'pre_flop': ('turn','river'), 'flop': ('river',)}.get(self.game.street, ())
        more_decisions = any(not self.game.bets[s][k] for s in active for k in future)
        if more_decisions:
            next_street,target_count = ('flop',3) if self.game.street == 'pre_flop' else ('turn',4)
            self.game.stage = 'revealing'
            self._refresh()
            def revealed():
                self._revealed_public = target_count
                self.game.street = next_street
                self.game.decisions = self.game.decisions_for_street(next_street)
                self.game.stage = 'decision'
                self._update_visible_titles()
                self._refresh()
                self._maybe_showdown()
            self._reveal_next([('Public',i) for i in range(self._revealed_public,target_count)],0,revealed)
            return
        # 两手都弃牌时仍翻出牌面，以便独立结算奖金注及累进大奖。
        self._showdown_started = True
        self.game.stage = 'showdown'
        self.game.decisions = {s:'play' if d == 'checked' else d for s,d in self.game.decisions.items()}
        self._refresh()
        remaining = [('Public',i) for i in range(self._revealed_public,5)]
        remaining += [('Dealer',i) for i in range(2)]
        remaining += [(s,i) for s in self.game.SEATS if s in self._hidden_hands for i in range(2)]
        def revealed_all():
            self._revealed_public = 5
            self._hidden_hands.clear()
            self._settle()
        self._reveal_next(remaining,0,revealed_all)

    def _update_visible_titles(self):
        for seat in self.game.SEATS:
            if not self.game.hands[seat]:
                continue
            if seat in self._hidden_hands:
                self.canvas.itemconfigure(self.title_items[seat],text=self.SEAT_NAMES[seat])
                continue
            cards = self.game.hands[seat]+self.game.public_cards[:self._revealed_public]
            caption = self.SEAT_NAMES[seat]
            if len(cards) >= 5:
                caption += ' - '+HAND_RANK_NAMES[find_best_5(cards)[0][0]]
            decision = self.game.decisions[seat]
            self.canvas.itemconfigure(self.title_items[seat], text=caption)

    def _update_hand_title(self, side):
        if side != 'Dealer' and not self.game.hands[side]:
            return
        name = '庄家' if side == 'Dealer' else self.SEAT_NAMES[side]
        rank = find_best_5(self.game.pool(side))[0][0]
        caption = f'{name} - {HAND_RANK_NAMES[rank]}'
        self.canvas.itemconfigure(self.title_items[side], text=caption)

    def _settle(self):
        if self._settlement_started:
            return
        self._settlement_started = True
        jackpot_before = self.game.progressive_amount
        result = self.game.settle()
        self.game.stage,self.last_win = 'settling',result['returned']
        try:
            save_progressive(self.game.progressive_amount)
        except Exception as exc:
            messagebox.showerror('奖池保存失败',str(exc),parent=self)
        for side in ('Dealer',*self.game.SEATS):
            self._update_hand_title(side)
        self._render_hand_usage()
        transfers,awards,round_id = [],[],time.time_ns()
        for seat,outcome in result['hands'].items():
            for kind in (*self.game.MAIN_BET_KINDS,'bonus'):
                transfers.extend(self._outcome_transfers(seat,kind,self.game.bets[seat][kind],outcome['details'][kind]))
            jackpot = outcome['details']['jackpot']
            if jackpot:
                self._set_lamp_mode(seat,'win')
                awards.append((seat,jackpot))
            info = dict(outcome,seat=seat,round_id=round_id,bets=dict(self.game.bets[seat]),
                        fold=self.game.decisions[seat]=='fold',total_winnings=outcome['returned'],
                        mode=self.game.mode,game_name='德州奖金扑克')
            try:
                save_thb_history(self.game.deck,self.game.hands[seat],self.game.dealer_hand,self.game.public_cards,info)
            except Exception as exc:
                messagebox.showerror('历史记录保存失败',str(exc),parent=self)
        self._refresh()
        self._run_chip_batch(transfers,lambda:self._pay_progressive_awards(awards,jackpot_before))

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
            best = find_best_5(self.game.pool(owner))[1]
            used = set()
            for card in best:
                public_index = next((i for i, c in enumerate(self.game.public_cards) if c is card), None)
                side = 'Public' if public_index is not None else owner
                index = public_index if public_index is not None else next(
                    i for i, c in enumerate(hand) if c is card)
                key = side, index
                used.add(key)
                if owner == 'Dealer' or self.game.decisions[owner] == 'play':
                    users.setdefault(key, []).append(owner)
            self._hand_usage_keys[owner] = used
        self._final_usage = {key: tuple(owners) for key, owners in users.items()}
        self._default_usage_owner = 'Dealer'
        self._faded_photos.clear()
        self._settled_card_photos.clear()
        for (side, index), item in self.card_items.items():
            hand = self.game.public_cards if side == 'Public' else self.game.dealer_hand if side == 'Dealer' else self.game.hands[side]
            card = hand[index]
            source = self._pil_cards[self._card_image_key(card)].convert('RGBA').resize(
                self.card_size(side), Image.Resampling.LANCZOS)

            self._settled_card_photos[item] = ImageTk.PhotoImage(source, master=self)
            self._fade_card_item(item, source)
        self._usage_owner = None
        self._apply_hand_usage(self._default_usage_owner)
        self._on_hand_usage_hover()

    def _apply_hand_usage(self, owner):
        """只淡化当前查看者未采用的牌，其他手牌恢复原有不透明度。"""
        used = self._hand_usage_keys.get(owner, set())
        for key, item in self.card_items.items():
            faded = key[0] in (owner, 'Public') and key not in used
            photos = self._faded_photos if faded else self._settled_card_photos
            self.canvas.itemconfigure(item, image=photos[item])
        self._usage_owner = owner

    def _on_hand_usage_hover(self, event=None):
        if (self.game.settlement is None or not self._hand_usage_keys
                or self.game.stage not in ('settled', 'settling', 'await_restart')):
            return
        current = set(self.canvas.find_withtag('current'))
        seat = next((side for (side, _), item in self.card_items.items()
                     if item in current and side in self.game.SEATS
                     and self.game.hands[side]), None)
        owner = seat or self._default_usage_owner
        if owner != self._usage_owner:
            self._apply_hand_usage(owner)

    def _on_hand_usage_leave(self, event=None):
        if (self.game.settlement is not None and self._hand_usage_keys
                and self.game.stage in ('settled', 'settling', 'await_restart')
                and self._usage_owner != self._default_usage_owner):
            self._apply_hand_usage(self._default_usage_owner)

# 兼容原有载入器；两套入口均运行德州奖金扑克。
UTHGUI = THBGUI
UTHTableGame = THBTableGame

def main(initial_balance=10000, username="游客", *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """嵌入现有 Tk 根窗口；未传 parent 时仍可独立运行。"""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return THBGUI(
            parent, actual_balance, actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("德州奖金扑克")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = THBGUI(root, actual_balance, actual_user)
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
    print(f"最终余额：{final_balance:,.2f}")
