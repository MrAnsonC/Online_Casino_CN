"""Hawaiian Hold'em, WSGC alternate method 1, using the uploaded UTH UI.

Install beside the original UTH module in the existing project; its A_Tools
account encryption, card assets/shuffle and shared $2.50 Progressive are used.

Rules: three starting hole cards; optional 1X/2X pre-flop raise; each player
discards after the flop; dealer chooses its best remaining pair after the
complete board. Player wins exact ties. Ante has no qualification threshold.
Big Kahuna is fixed to PDF pay table B. Progressive uses the original three
player hole cards (including the discard) and board cards four and five.
"""

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
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageEnhance

# ==================== Progressive 向下翻牌数字 ====================
class ProgressiveFlipDisplay(tk.Canvas):
    """金额更新时逐位向下翻牌；每步 600ms 翻动 + 200ms 停留。

    每位仅允许 n -> (n + 1) % 10。更新中收到的新金额在下一步
    接管目标，不中断正在翻动的牌。StringVar 始终保存真实金额。
    """
    FLIP_MS = 600
    HOLD_MS = 200
    FRAME_MS = 16
    INTEGER_DIGITS = 6  # 6 位整数 + 2 位小数，共 8 位数字

    def __init__(self, master, textvariable, font=('Arial', 20, 'bold'),
                 bg='#F2E6C9', fg='#A88100', **kwargs):
        import time as _flip_time
        import math as _flip_math
        from tkinter import font as _tk_font
        self._clock = _flip_time.monotonic
        self._cos = _flip_math.cos
        self._pi = _flip_math.pi
        self._variable = textvariable
        self._foreground = fg
        self._job = None
        self._closed = False
        self._phase = 'idle'
        self._progress = 1.0
        self._glyphs = {}
        self._photos = []
        super().__init__(master, bg=bg, highlightthickness=0, bd=0, **kwargs)
        metrics = _tk_font.Font(root=self, font=font)
        pixels = max(12, abs(round(metrics.actual('size') * self.winfo_fpixels('1p'))))
        self._card_width = max(18, metrics.measure('0') + 6)
        self._card_height = max(28, metrics.metrics('linespace') + 8)
        self._card_height += self._card_height % 2
        self._font = None
        for name in ('arialbd.ttf', 'Arial Bold.ttf', 'DejaVuSans-Bold.ttf',
                     '/System/Library/Fonts/Supplemental/Arial Bold.ttf'):
            try:
                self._font = ImageFont.truetype(name, pixels)
                break
            except OSError:
                pass
        if self._font is None:
            try:
                self._font = ImageFont.load_default(size=pixels)
            except TypeError:
                self._font = ImageFont.load_default()
        self._target = self._format_amount(textvariable.get())
        self._digits = self._extract(self._target)
        self._next = self._digits[:]
        self._layout = self._target
        self._draw()
        self._trace = textvariable.trace_add('write', self._changed)
        self.bind('<Destroy>', self._on_destroy, add='+')

    @classmethod
    def _format_amount(cls, value):
        """补足八位数字；货币符号、逗号和小数点不计入位数。

        超出六位整数时保留完整金额，避免截断真实大奖数值。
        """
        from decimal import Decimal, ROUND_HALF_UP
        amount = Decimal(str(value).replace('$', '').replace(',', '').strip())
        amount = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        sign = '-' if amount < 0 else ''
        integer, fraction = format(abs(amount), '.2f').split('.')
        integer = integer.zfill(cls.INTEGER_DIGITS)
        groups = [integer[max(0, i-3):i] for i in range(len(integer), 0, -3)]
        return '$' + sign + ','.join(reversed(groups)) + '.' + fraction

    @staticmethod
    def _extract(text):
        return [int(c) for c in text if c in '0123456789']

    def _changed(self, *_):
        if self._closed:
            return
        self._target = self._format_amount(self._variable.get())
        if self._phase == 'idle' and self._job is None:
            # 合并同一个事件处理函数内的多次金额更新。
            self._job = self.after_idle(self._begin)

    def set_amount_immediately(self, value):
        """中奖扣款直接显示准确余额，避免复制奖金时仍显示翻动中的旧数字。"""
        if self._closed:return
        if self._job is not None:
            self.after_cancel(self._job)
            self._job=None
        self._phase='hold'
        self._variable.set(value)
        self._digits=self._extract(self._target)
        self._next=self._digits[:]
        self._layout=self._target
        self._phase='idle'
        self._progress=1.0
        self._draw()

    def _begin(self):
        self._job = None
        if self._closed:
            return
        goal = self._extract(self._target)
        width = max(len(goal), len(self._digits))
        self._digits = [0] * (width - len(self._digits)) + self._digits
        goal = [0] * (width - len(goal)) + goal
        if self._digits == goal:
            self._digits = self._extract(self._target)
            self._next = self._digits[:]
            self._layout = self._target
            self._phase = 'idle'
            self._draw()
            return
        # 按右侧小数位对齐；缩位时保留前导零，全部到位后才收起。
        raw = ''.join(str(n) for n in goal)
        if '.' in self._target:
            decimals = len(self._target.rsplit('.', 1)[1])
        else:
            decimals = 0
        integer = raw[:-decimals] if decimals else raw
        groups = [integer[max(0, i-3):i] for i in range(len(integer), 0, -3)]
        grouped = ','.join(reversed(groups))
        prefix = self._target[:next((i for i, c in enumerate(self._target)
                                    if c in '0123456789'), len(self._target))]
        self._layout = prefix + grouped + ('.' + raw[-decimals:] if decimals else '')
        self._next = [(old + 1) % 10 if old != wanted else old
                      for old, wanted in zip(self._digits, goal)]
        self._phase = 'flip'
        self._started = self._clock()
        self._tick()

    def _tick(self):
        self._job = None
        if self._closed:
            return
        elapsed = (self._clock() - self._started) * 1000.0
        self._progress = min(1.0, elapsed / self.FLIP_MS)
        self._draw()
        if elapsed >= self.FLIP_MS:
            self._digits = self._next[:]
            self._phase = 'hold'
            self._job = self.after(self.HOLD_MS, self._begin)
        else:
            self._job = self.after(min(self.FRAME_MS, max(1, round(self.FLIP_MS - elapsed))),
                                   self._tick)

    def _rgb(self, color):
        return tuple(value // 257 for value in self.winfo_rgb(color))

    def _glyph(self, char):
        if char not in self._glyphs:
            bg = self._rgb(self.cget('bg'))
            canvas = Image.new('RGB', (self._card_width, self._card_height), bg)
            draw = ImageDraw.Draw(canvas)
            if char in '0123456789':
                draw.rounded_rectangle((0, 0, self._card_width-1, self._card_height-1), radius=3,
                                       fill=tuple(min(255, c+8) for c in bg),
                                       outline=tuple(max(0, c-35) for c in bg))
            box = draw.textbbox((0, 0), char, font=self._font)
            # 所有字符共用数字的文字基线；逗号、小数点不能单独垂直居中。
            digit_box = draw.textbbox((0, 0), '0', font=self._font)
            text_y = (self._card_height-(digit_box[3]-digit_box[1]))/2-digit_box[1]
            draw.text(((self._card_width-(box[2]-box[0]))/2-box[0],
                       text_y),
                      char, font=self._font, fill=self._rgb(self._foreground))
            self._glyphs[char] = canvas
        return self._glyphs[char]

    def _draw(self):
        self.delete('all')
        self._photos = []
        x = 0
        index = 0
        half = self._card_height // 2
        for char in self._layout:
            if char in '0123456789':
                old = self._glyph(str(self._digits[index]))
                new = self._glyph(str(self._next[index]))
                frame = old.copy()
                if self._phase == 'flip' and self._digits[index] != self._next[index]:
                    p = self._progress
                    # 新牌上半部在后，旧牌下半部在后；翻片绕中轴向下。
                    frame.paste(new.crop((0, 0, self._card_width, half)), (0, 0))
                    if p < 0.5:
                        height = max(1, round(half * self._cos(self._pi * p)))
                        flap = old.crop((0, 0, self._card_width, half))
                        frame.paste(flap.resize((self._card_width, height), Image.Resampling.LANCZOS),
                                    (0, half-height))
                    else:
                        height = max(1, round(half * -self._cos(self._pi * p)))
                        flap = new.crop((0, half, self._card_width, self._card_height))
                        frame.paste(flap.resize((self._card_width, height), Image.Resampling.LANCZOS),
                                    (0, half))
                ImageDraw.Draw(frame).line((1, half, self._card_width-2, half),
                                           fill=self._rgb(self.cget('bg')))
                index += 1
                advance = self._card_width + 2
            else:
                frame = self._glyph(char)
                advance = self._card_width if char == '$' else max(6, self._card_width // 2)
                frame = frame.crop(((self._card_width-advance)//2, 0,
                                    (self._card_width-advance)//2+advance, self._card_height))
            photo = ImageTk.PhotoImage(frame, master=self)
            self._photos.append(photo)
            self.create_image(x, 0, image=photo, anchor='nw')
            x += advance
        super().configure(width=max(1, x), height=self._card_height)

    def configure(self, cnf=None, **kwargs):
        result = super().configure(cnf, **kwargs)
        if hasattr(self, '_layout') and ('bg' in kwargs or 'background' in kwargs or
                isinstance(cnf, dict) and ('bg' in cnf or 'background' in cnf)):
            self._glyphs.clear()
            self._draw()
        return result

    config = configure

    def _on_destroy(self, event):
        if event.widget is not self or self._closed:
            return
        self._closed = True
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        try:
            self._variable.trace_remove('write', self._trace)
        except tk.TclError:
            pass
# ==================== Progressive 翻牌控件结束 ====================


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

# Hawaiian Hold’em 替代方式1与固定B表
GAME_MODE_NAMES = {
    'payout_b': '固定 B 表',
}

# WSGC Hawaiian Hold-em Rules, alternate method 1; odds are net winnings.
# Fixed pay table B; 0X/1X/2X raise and player-wins-ties rule.
BIG_KAHUNA_PAYOUTS = {
    'payout_b': {9: 400, 8: 50, 7: 20, 6: 6, 5: 4, 4: 3, 3: 1},
}

# Ante always plays: no UTH dealer-qualification refund.
HAWAIIAN_VARIANT = 'alternate_1'

def project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def user_data_path() -> str:
    return os.path.join(project_root(), "A_Tools/Account/saving_data.json")

def hawaiian_log_path() -> str:
    log_dir = os.path.join(project_root(), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Hawaiian_Holdem.json")

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




# =========================================================
# 历史记录保存（只保存，不显示）
# =========================================================

def save_hawaiian_history(deck, player_cards, dealer_cards, community_cards, result_info=None):
    """
    记录当前牌局历史，包含 game_id、统计信息，并只保留最新50局。
    
    参数：
        deck: Deck 实例
        player_cards, dealer_cards, community_cards: Card 列表
        result_info: 字典，可包含 'winner'（'player'/'dealer'/'push'）或 'fold'（弃牌标识）
    """
    log_path = hawaiian_log_path()
    
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
# Hawaiian Hold’em 规则与原 UTH 双手牌界面
# =========================================================






class HawaiianTableGame:
    """Two Hawaiian Hold'em hands share one dealer, board and account.

    The PDF leaves its dealer-discard edge case unspecified. This implementation
    evaluates each legal two-card remainder against the complete board and
    discards the card that leaves the strongest final five-card hand. Three
    dealer hole cards can never be used together in the main game. Progressive
    uses the player's original three cards, including the discarded card.
    """
    SEATS = ('Player1', 'Player2')
    MIN_PROGRESSIVE = 271288.59

    def __init__(self, mode='payout_b'):
        if mode not in GAME_MODE_NAMES:
            raise ValueError('未知 Big Kahuna 赔率表。')
        self.mode = mode
        self.progressive_amount = load_jackpot()[1]
        self.reset_game()

    @property
    def pre_flop_multipliers(self):
        return (1, 2)

    @property
    def main_bet_name(self):
        return '前注'

    @property
    def initial_public_count(self):
        return 0

    @property
    def kahuna_payout(self):
        return BIG_KAHUNA_PAYOUTS[self.mode]

    def set_mode(self, mode):
        if self.stage != 'betting':
            raise ValueError('请在本局结束后切换赔率表。')
        if mode not in GAME_MODE_NAMES:
            raise ValueError('未知 Big Kahuna 赔率表。')
        self.mode = mode

    @staticmethod
    def empty_bet():
        # `trips` is the inherited UI slot, now exclusively Big Kahuna.
        return dict(ante=0.0, trips=0.0, jackpot=0.0, play=0.0)

    def reset_game(self):
        self.deck = None
        # Preserve original three-card order for display, audit and Progressive.
        self.hands = {s: [] for s in self.SEATS}
        self.dealer_hand, self.public_cards, self.deal_sequence = [], [], []
        self.discards = {s: None for s in ('Dealer', *self.SEATS)}
        self.bets = {s: self.empty_bet() for s in self.SEATS}
        self.decisions = {s: 'inactive' for s in self.SEATS}
        self.stage, self.street = 'betting', 'pre_flop'
        self.settlement = None
        self.refunded_bets = {}

    def start_round(self, bets, balance, high_bet_mode=False):
        if self.stage != 'betting':
            raise ValueError('本局尚未结束。')
        minimum, maximum, side_max = (100, 50000, 12500) if high_bet_mode else (10, 10000, 2500)
        prepared, refunded = {}, {}
        for seat in self.SEATS:
            b = {k: float(bets.get(seat, {}).get(k, 0)) for k in self.empty_bet()}
            if any(not math.isfinite(v) or v < 0 for v in b.values()):
                raise ValueError('下注金额必须是有限的非负数。')
            if not b['ante']:
                if any(b.values()):
                    refunded[seat] = dict(b)
                prepared[seat] = self.empty_bet()
                continue
            if not minimum <= b['ante'] <= maximum:
                raise ValueError(f'每手前注须为 ${minimum:,} 至 ${maximum:,}。')
            if b['trips'] > side_max:
                raise ValueError('Big Kahuna 边注超出限额。')
            if b['jackpot'] not in (0, 2.5):
                raise ValueError('累进大奖每手固定 $2.50。')
            if b['play'] not in (0, *(round(b['ante'] * m, 2) for m in self.pre_flop_multipliers)):
                raise ValueError('替代方式 1 只允许不加注、追加前注的 1 倍或 2 倍。')
            prepared[seat] = b
        if not any(b['ante'] for b in prepared.values()):
            raise ValueError('请至少为一手牌下前注。')
        charged = round(sum(sum(b.values()) for b in prepared.values()), 2)
        if not math.isfinite(balance) or balance < charged:
            raise ValueError('余额不足以支付本局下注。')
        deck = Deck()
        active = tuple(s for s in self.SEATS if prepared[s]['ante'])
        sequence = [('Public', i) for i in range(5)]
        sequence += [(side, i) for i in range(3) for side in (*active, 'Dealer')]
        hands, dealer, public = {s: [] for s in self.SEATS}, [], []
        for side, _index in sequence:
            card = deck.deal(1)[0]
            (public if side == 'Public' else dealer if side == 'Dealer' else hands[side]).append(card)
        self.deck, self.hands, self.dealer_hand, self.public_cards = deck, hands, dealer, public
        self.deal_sequence, self.bets, self.refunded_bets = sequence, prepared, refunded
        self.discards = {s: None for s in ('Dealer', *self.SEATS)}
        self.decisions = {s: 'play' if prepared[s]['play'] else 'pending' if prepared[s]['ante'] else 'inactive'
                          for s in self.SEATS}
        self.street, self.stage = 'pre_flop', 'dealing'
        return charged

    def decide(self, seat, action, balance, multiplier=0):
        if (self.stage != 'decision' or self.street != 'pre_flop'
                or self.decisions.get(seat) != 'pending'):
            raise ValueError('当前不能加注；加注只在翻牌前进行一次。')
        if action == 'check':
            self.decisions[seat] = 'checked'
            return 0.0
        if action != 'play' or multiplier not in self.pre_flop_multipliers:
            raise ValueError('请选择不加注、加注 1X 或加注 2X。')
        cost = round(self.bets[seat]['ante'] * multiplier, 2)
        if not math.isfinite(balance) or cost > balance:
            raise ValueError('余额不足以支付所选加注。')
        self.bets[seat]['play'] = cost
        self.decisions[seat] = 'play'
        return cost

    def discard(self, seat, index):
        if (self.stage != 'discard' or seat not in self.SEATS
                or self.decisions[seat] == 'inactive' or self.discards[seat] is not None):
            raise ValueError('这手牌当前不能弃牌。')
        if type(index) is not int or not 0 <= index < 3:
            raise ValueError('请选择三张底牌中的一张。')
        self.discards[seat] = index

    def all_players_discarded(self):
        return all(self.discards[s] is not None for s in self.SEATS
                   if self.decisions[s] != 'inactive')

    def kept_cards(self, side):
        hand = self.dealer_hand if side == 'Dealer' else self.hands[side]
        discarded = self.discards[side]
        return [c for i, c in enumerate(hand) if i != discarded]

    def pool(self, side):
        return self.kept_cards(side) + self.public_cards

    def choose_dealer_discard(self):
        if self.stage != 'showdown' or not self.all_players_discarded():
            raise ValueError('玩家必须先弃牌，并进入最后开牌阶段。')
        if len(self.dealer_hand) != 3 or len(self.public_cards) != 5:
            raise ValueError('庄家三张底牌和五张公共牌必须齐全。')
        if self.discards['Dealer'] is None:
            # Tie-break: discard the lowest-value unused hole card.
            self.discards['Dealer'] = max(range(3), key=lambda i: (
                find_best_5([c for j, c in enumerate(self.dealer_hand) if j != i]
                            + self.public_cards)[0], -self.dealer_hand[i].value, -i))
        return self.discards['Dealer']

    def dealer_qualifies(self):
        # Kept for compatibility with the inherited presentation code.
        return True

    def progressive_cards(self, seat):
        return self.hands[seat] + self.public_cards[3:5]

    def settle(self):
        if self.settlement is not None:
            return self.settlement
        if (self.stage != 'showdown' or not self.all_players_discarded()
                or any(d == 'pending' for d in self.decisions.values())):
            raise ValueError('所有已下注手牌须先完成加注决定和弃牌。')
        self.choose_dealer_discard()
        dealer_eval, _ = find_best_5(self.pool('Dealer'))
        outcomes, returned, contribution = {}, 0.0, 0.0
        pool = self.progressive_amount
        for seat in self.SEATS:
            if self.decisions[seat] == 'inactive':
                continue
            b = self.bets[seat]
            player_eval, _ = find_best_5(self.pool(seat))
            rank = player_eval[0]
            tied = player_eval == dealer_eval
            winner = 'player' if player_eval >= dealer_eval else 'dealer'
            details = dict(ante=0.0, play=0.0, trips=0.0, bonus=0.0)
            if winner == 'player':
                details['ante'], details['play'] = b['ante'] * 2, b['play'] * 2
            if rank in self.kahuna_payout:
                details['trips'] = b['trips'] * (1 + self.kahuna_payout[rank])
            pg_rank = None
            if b['jackpot']:
                pg_rank, _ = evaluate_hand(self.progressive_cards(seat))
                award = pool if pg_rank == 9 else pool * .1 if pg_rank == 8 else {7: 1250, 6: 375, 5: 250}.get(pg_rank, 0)
                details['bonus'] = round(award, 2)
                pool = round(pool - details['bonus'], 2)
            hand_return = round(sum(details.values()), 2)
            outcomes[seat] = dict(details=details, returned=hand_return, winner=winner, tied=tied,
                                  player_rank=rank, dealer_rank=dealer_eval[0], progressive_rank=pg_rank,
                                  player_discard_index=self.discards[seat],
                                  dealer_discard_index=self.discards['Dealer'])
            returned += hand_return
            contribution += sum(b[k] for k in ('ante', 'play', 'trips')) * .001
            if b['jackpot']:
                contribution += 2.21
        self.progressive_amount = round(max(self.MIN_PROGRESSIVE, pool + contribution), 2)
        self.settlement = dict(hands=outcomes, returned=round(returned, 2), mode=self.mode,
                               variant=HAWAIIAN_VARIANT, dealer_qualification=False)
        return self.settlement


class HawaiianGUI(tk.Frame):
    WIDTH, HEIGHT = 1150, 750
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    MODE_TRANSITION_MS = 360
    MODE_FRAME_MS = 16
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
        self.game = HawaiianTableGame()
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
        self._mode_indicator_x = 822.0
        self._mode_weights = {mode: float(mode == self.game.mode) for mode in GAME_MODE_NAMES}
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
            self._face_photos[key] = ImageTk.PhotoImage(im.resize(self.card_size('Dealer'), Image.Resampling.LANCZOS), master=self)
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

    def reset_bets(self):
        if self.game.stage=='betting' and not self._motion_count:
            self._apply_bet_layout({s:self.game.empty_bet() for s in self.game.SEATS})

    def apply_last_bet(self):
        if self.game.stage=='betting' and not self._motion_count and self.last_bet:
            self._apply_bet_layout(self._bets_for_mode(self.last_bet))

    def _bets_for_mode(self, bets):
        return {s: {k: float(bets[s].get(k, 0)) for k in self.game.empty_bet()}
                for s in self.game.SEATS}


    def select_game_mode(self, mode):
        if mode != 'payout_b':
            raise ValueError('Big Kahuna 固定使用 B 表。')


    def _capture_mode_content(self):
        """只记录随模式改变的 Canvas 内容，不截屏、不重建整个牌桌。"""
        c = self.canvas
        items = [(self.mode_description_item, ROOT_BG), (self.total_item, ROOT_BG)]
        for seat in self.game.SEATS:
            background = self.ZONE_COLORS[seat]
            items.append((self.bet_spots[(seat, 'trips')]['label'], background))
            button = self.control_buttons[self.action_buttons[(seat, 'raise_high')]]
            items.extend((button[key], background) for key in
                         ('shadow', 'rim', 'face', 'highlight', 'text', 'subtext')
                         if button.get(key) is not None)
        snapshots = []
        for item, background in items:
            kind = c.type(item)
            options = ('fill', 'outline') if kind in ('rectangle', 'polygon', 'oval') else ('fill',)
            snapshot = dict(item=item, background=background,
                            state='hidden' if c.itemcget(item, 'state') == 'hidden' else 'normal',
                            colors={key: c.itemcget(item, key) for key in options})
            if kind == 'text':
                snapshot['text'] = c.itemcget(item, 'text')
            snapshots.append(snapshot)
        return snapshots


    def _mix_mode_color(self, start, target, progress):
        a, b = self.canvas.winfo_rgb(start), self.canvas.winfo_rgb(target)
        return '#' + ''.join(f'{round((x+(y-x)*progress)/257):02x}' for x, y in zip(a, b))

    def _paint_mode_transition(self):
        transition = self._mode_transition
        if transition is None:
            return 1.0
        progress = min(1.0, max(0.0, (time.monotonic()-transition['started'])*1000/self.MODE_TRANSITION_MS))
        eased = progress*progress*(3-2*progress)
        self._mode_indicator_x = transition['start_x'] + (transition['target_x']-transition['start_x'])*eased
        self._mode_weights = {
            mode: weight+(float(mode == self.game.mode)-weight)*eased
            for mode, weight in transition['weights'].items()
        }
        self._refresh_mode_selector()
        for old, new in transition['content']:
            if old['state'] == new['state'] == 'hidden':
                continue
            background = new['background']
            changed_text = 'text' in old and old['text'] != new['text']
            options = dict(state='normal')
            if changed_text:
                options['text'] = old['text'] if progress < .5 else new['text']
            for key in new['colors']:
                start = (old['colors'][key] or background) if old['state'] != 'hidden' else background
                target = (new['colors'][key] or background) if new['state'] != 'hidden' else background
                if changed_text:
                    phase = progress*2 if progress < .5 else (progress-.5)*2
                    amount = phase*phase*(3-2*phase)
                    start, target = (start, background) if progress < .5 else (background, target)
                else:
                    amount = eased
                options[key] = self._mix_mode_color(start, target, amount)
            self.canvas.itemconfigure(new['item'], **options)
        return progress

    def _animate_mode_transition(self):
        self._mode_transition_job = None
        if self._closing or self._mode_transition is None:
            return
        if self._paint_mode_transition() >= 1.0:
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

    def _restore_mode_content(self):
        if self._mode_transition is None:
            return
        for _old, target in self._mode_transition['content']:
            options = dict(target['colors'], state=target['state'])
            if 'text' in target:
                options['text'] = target['text']
            self.canvas.itemconfigure(target['item'], **options)

    def _finish_mode_transition(self):
        if self._mode_transition is None:
            return
        self._cancel_mode_transition_job()
        self._restore_mode_content()
        self._mode_transition = None
        self._refresh()
        # 转场后再更新已打开的说明，避免重建说明页阻塞动画帧。
        self._refresh_mode_instructions()

    def _refresh_mode_instructions(self):
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
            if self.username and self.username!='Guest':
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
        self._fade_dealer_notice(False)
        self.balance=round(self.balance-charged,2)
        self.bets={s:dict(b) for s,b in self.game.bets.items()}
        self.last_bet={s:dict(b) for s,b in self.bets.items()}
        self._credited=False;self._return_persisted=False;self._settlement_started=False;self._side_resolved=set()
        self._cancel_restart_timer()
        # 所有玩家均须看三张底牌并在翻牌后弃一张；预设加注也不盖牌。
        self._blind_seats=set()
        self.selected_discards={s:None for s in self.game.SEATS}
        self._discard_photos.clear();self._card_origins.clear()
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
        self._card_origins[(side,index)] = (x,y)
        if side in self.game.SEATS:
            self.canvas.tag_bind(item,'<Button-1>',lambda _e,s=side,i=index:self.discard_action(s,i))
        def move(step=0):
            p = step/6
            self.canvas.coords(item,575+(x-575)*p,52+(y-52)*p)
            if step<6:
                self._schedule(round(self.DEAL_MOVE_MS*(step+1)/6)-round(self.DEAL_MOVE_MS*step/6),move,step+1)
            else:
                self._schedule(round(self.DEAL_CARD_MS)-round(self.DEAL_MOVE_MS),self._deal_next,sequence,offset+1)
        move()


    def _reveal_initial_cards(self):
        reveal = [(s, i) for s in self.game.SEATS if self.game.hands[s] for i in range(3)]
        # PDF step 8 says "other two cards": dealer starts one up, two down.
        reveal.append(('Dealer', 0))
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
            self._fade_dealer_notice(False)
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
        self.progressive_display = ProgressiveFlipDisplay(panel,self.progressive_amount_var,
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

    def _draw_mode_selector(self):
        # Table B remains fixed in the rules; leave the area below the pool clear.
        self.mode_buttons = {}
        self._mode_hover = self._mode_pressed = None
        self.mode_description_item = self._text(967, 292, '', 10, '#C7CBB2', state='hidden')


    def _rounded_rectangle(self, x0, y0, x1, y1, radius, **options):
        return self.canvas.create_polygon(
            x0+radius, y0, x1-radius, y0, x1, y0, x1, y0+radius,
            x1, y1-radius, x1, y1, x1-radius, y1, x0+radius, y1,
            x0, y1, x0, y1-radius, x0, y0+radius, x0, y0,
            smooth=True, splinesteps=24, **options)

    def _mode_indicator_pointer(self, event, action):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        for index, mode in enumerate(GAME_MODE_NAMES):
            if 822+index*98 <= x <= 918+index*98 and 232 <= y <= 270:
                self._mode_pointer(mode, action)
                return
        self._mode_pointer(None, 'leave')

    def _mode_pointer(self, mode, action):
        enabled = self.game.stage == 'betting' and not self._motion_count
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
            if enabled and pressed == mode:
                self.select_game_mode(mode)
        self._refresh_mode_selector()

    def _refresh_mode_selector(self):
        # Table B is fixed for every round and cannot be switched from the UI.
        return None


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
        if abs(value)>=1000:return HawaiianGUI._compact(value)
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
        # 动画与实际取牌共用同一顺序：先发五张公共牌，再轮流发三轮底牌。
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







    def _fade_dealer_notice(self, visible):
        # No dealer-qualification banner in the selected PDF rules.
        self.canvas.delete('dealer_notice')


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

    def _draw_wild_spot(self, seat, kind, cx, cy, label, radius):
        tag = 'spot_'+seat+'_'+kind
        border = self.canvas.create_oval(cx-radius,cy-radius,cx+radius,cy+radius,
            fill=self.ZONE_COLORS[seat],outline=PANEL_BG,width=2,tags=tag)
        self._register_spot(seat,kind,cx,cy,border,label)
        # 放大的下注圈使用清晰字号，完整圆圈均可点击。
        if kind in ('trips','player_pair','play'):
            for item in self.canvas.find_withtag(tag):
                if self.canvas.type(item)=='text': self.canvas.itemconfigure(item,font=('Arial',12 if kind=='player_pair' else 14,'bold'))

    def card_size(self, side):
        return self.CARD_WIDTH, self.CARD_HEIGHT


    def _fade_card_item(self, item, source):
        # 用alpha淡化，不破坏牌面原图，也不把透明PNG的边缘铺成白底。
        faded = source.convert('RGBA').copy()
        faded.putalpha(faded.getchannel('A').point(lambda value:round(value*.45)))
        photo = ImageTk.PhotoImage(faded,master=self)
        self._faded_photos[item] = photo
        self.canvas.itemconfigure(item,image=photo)

    def _instruction_pages(self):
        """Hawaiian alternate method 1; fixed Big Kahuna B; UTH table design."""
        payout_rows = [[HAND_RANK_NAMES[rank], f'{odds}:1', f'边注 × {odds + 1}']
                       for rank, odds in self.game.kahuna_payout.items()]
        return [
            ('玩法', 'Hawaiian Hold’em · 替代方式 1 · 平局玩家赢', [
                ['目标与起手', '', [
                    ('游戏目标', '用弃牌后保留的两张底牌和五张公共牌选最佳五张，与庄家比较。'),
                    ('三张底牌', '玩家、庄家各拿三张底牌。两手玩家共用庄家及公共牌。'),
                    ('首次亮牌', '所有已下注玩家的三张底牌均翻开；庄家首张明牌，另外两张在最后翻开。PDF 第8条称其为“另外两张牌”。'),
                ], []],
                ['完整流程', '', [
                    ('1 · 下注', '下注 Ante；Big Kahuna 和累进大奖均可选。加注圈可预设 1X 或 2X。'),
                    ('2 · 翻牌前决定', '看底牌后选择不加注、追加 Ante 的 1 倍或 2 倍。每手只有一次决定。已预设加注的手牌直接锁定。'),
                    ('3 · 翻开前三张', '全部玩家完成决定后，翻开前三张公共牌。'),
                    ('4 · 玩家弃一张', '点击要弃掉的底牌，或点击“弃第1/2/3张”。每手必须弃一张；选择后锁定。'),
                    ('5 · 最后开牌', '所有玩家完成弃牌后，才翻开第4、5张公共牌及庄家另外两张底牌。'),
                    ('6 · 庄家弃一张', '庄家比较三种合法弃牌方案，保留与完整公共牌组成最佳五张牌的两张底牌。弃掉的牌不参与主注及 Big Kahuna。'),
                    ('7 · 结算', '不设庄家资格门槛；玩家牌大或完全相同都算玩家赢。'),
                ], []],
            ]),
            ('下注 & 限红', '沿用上传 UTH 的下注上限及高额模式。', [
                ['下注项目', '', [], [('', ['项目', '普通模式', '高额模式'], [
                    ['Ante 前注', '$10–$10,000', '$100–$50,000'],
                    ['加注', '0X / 1X / 2X Ante', '0X / 1X / 2X Ante'],
                    ['Big Kahuna', '每手最高 $2,500', '每手最高 $12,500'],
                    ['累进大奖', '每手固定 $2.50', '每手固定 $2.50'],
                ])]],
                ['操作', '', [
                    ('点击下注圈', '左键增加筹码，右键清除。加注圈在 0X → 1X → 2X → 0X 间循环。'),
                    ('高额模式', '沿用原 UTH：点击下注上限面板，输入本机当前时分 HHMM；切换时清空下注。'),
                    ('参加条件', '该手必须有 Ante 才参加；无 Ante 的边注会在开局时退回。无需另下 Blind 或玩家对子注。'),
                    ('金额说明', '1X/2X 是额外追加金额。例如 Ante 100、加注2X，主注合计为300。'),
                ], []],
            ]),
            ('获胜条件 & 赔率', '固定 Big Kahuna B 表；所有赔率均指净盈利，中奖另退本金。', [
                ['主注结算', '没有庄家及格 / 不及格判定。', [], [('', ['结果', 'Ante', '加注'], [
                    ['玩家胜', '1:1', '1:1'], ['完全平局', '玩家赢，1:1', '玩家赢，1:1'],
                    ['玩家负', '输', '输'],
                ])]],
                ['Big Kahuna · 固定 B 表', '玩家保留两张底牌＋五张公共牌选最佳五张；独立于主注输赢。三条以下不中奖。',
                 [], [('', ['玩家最终牌型', '净赢赔率', '返还总额'], payout_rows)]],
            ]),
            ('牌型等级表', '牌型由强到弱排列；\n同级牌型继续比较相关点数。', [['10 种牌型', '下方图片展示牌型示例；\n同一牌型也可能由其他牌面组成。', [], [('牌型与示例', ['等级', '牌型', '说明', '牌例'], [['1', '皇家同花顺', '同花色的 10-A', ('__CARD_IMAGES__', (('♥', '10'), ('♥', 'J'), ('♥', 'Q'), ('♥', 'K'), ('♥', 'A')))], ['2', '同花顺', '同花色顺子', ('__CARD_IMAGES__', (('♥', '6'), ('♥', '7'), ('♥', '8'), ('♥', '9'), ('♥', '10')))], ['3', '四条', '四张同点', ('__CARD_IMAGES__', (('♥', 'A'), ('♣', 'A'), ('♦', 'A'), ('♠', 'A'), ('♥', 'K')))], ['4', '葫芦', '三条 + 一对', ('__CARD_IMAGES__', (('♥', 'A'), ('♣', 'A'), ('♦', 'A'), ('♥', 'K'), ('♠', 'K')))], ['5', '同花', '五张同花色', ('__CARD_IMAGES__', (('♣', 'K'), ('♣', '10'), ('♣', '8'), ('♣', '7'), ('♣', '5')))], ['6', '顺子', '五张连续', ('__CARD_IMAGES__', (('♥', '6'), ('♠', '7'), ('♦', '8'), ('♣', '9'), ('♠', '10')))], ['7', '三条', '三张同点', ('__CARD_IMAGES__', (('♥', 'A'), ('♣', 'A'), ('♠', 'A'), ('♠', 'K'), ('♥', 'Q')))], ['8', '两对', '两组对子', ('__CARD_IMAGES__', (('♥', 'A'), ('♣', 'A'), ('♦', 'K'), ('♠', 'K'), ('♥', '7')))], ['9', '对子', '一组对子', ('__CARD_IMAGES__', (('♥', 'A'), ('♣', 'A'), ('♠', 'K'), ('♣', 'J'), ('♥', '7')))], ['10', '高牌', '无任何组合', ('__CARD_IMAGES__', (('♥', 'A'), ('♣', 'K'), ('♦', 'Q'), ('♠', '9'), ('♥', '7')))]])]]]),
            ('累进大奖', '沿用 UTH 奖金及奖池规则，改用指定的五张牌。', [
                ['用牌规则', '', [
                    ('固定五张', '玩家最初三张底牌＋公共牌第4、5张。包含后来弃掉的那张底牌，不使用前三张公共牌。'),
                    ('独立评估', '这五张牌直接评估牌型；不从八张牌中选牌，也不使用庄家牌。'),
                ], []],
                ['奖金表', '$2.50 下注先收取；中奖按下表支付奖金。', [], [('', ['五张牌型', '奖金'], [
                    ['皇家同花顺', '当前累进奖池 100%'], ['同花顺', '当前累进奖池 10%'],
                    ['四条', '$1,250'], ['葫芦', '$375'], ['同花', '$250'],
                    ['其他', '不中奖'],
                ])]],
            ]),
            ('操作与记录', '保留 UTH 筹码动画、大奖翻牌数字及牌序窗口。', [
                ['弃牌显示', '', [
                    ('弃掉的牌', '变暗，移到该手最右侧，并旋转90°；另两张牌向左排列。庄家与玩家均使用这个效果。'),
                    ('结算用牌', '默认高亮庄家采用的牌；鼠标移到玩家底牌可查看该手最佳五张。弃牌始终保持变暗和横放。'),
                ], []],
                ['再来一局', '', [
                    ('回收与入账', '结算后点击“再来一局”，筹码回收后只入账一次；30秒无操作自动回收。大奖中奖后不自动倒计时。'),
                    ('上局牌序', '结算后右键“再来一局”查看完整52张牌序和切牌位置。'),
                    ('牌局记录', '独立写入 Hawaiian_Holdem.json，包含原始三张底牌、弃牌、保留牌和累进大奖用牌。'),
                ], []],
            ]),
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

        instruction_title = 'Hawaiian Hold’em · 替代方式 1 · Big Kahuna B'
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
        self._hand_usage_keys = {}
        self._settled_card_photos = {}
        self._usage_owner = None
        self._default_usage_owner = 'Dealer'
        self.canvas.bind('<Motion>', self._on_hand_usage_hover, add='+')
        self.canvas.bind('<Leave>', self._on_hand_usage_leave, add='+')
        self._revealed_public = 0
        c = self.canvas
        self._text(187, 44, '夏威夷扑克', 16, GOLD)
        c.create_rectangle(435, 10, 747, 163, fill=self.TABLE_GREEN, outline='')
        self.title_items = {'Dealer': self._text(575, 23, '庄家', 16, PANEL_BG)}
        self._draw_limit_table()
        self._text(957, 44, 'Hawaiian Hold’em', 14, GOLD)
        self._draw_progressive_panel()
        c.create_rectangle(22, 191, 1128, 309, fill=ROOT_BG, outline='#65784B')
        c.create_line(25, 192, 1125, 192, fill='#E0C879', width=2)
        c.create_line(25, 308, 1125, 308, fill='#0C241B', width=2)
        self._text(182, 229, '不设庄家及格线\n平局玩家赢', 17, GOLD)
        self._draw_mode_selector()
        self.street_item = self._text(182, 279, '下注阶段', 14, PANEL_BG)
        # Five board cards retain their positions on a dark green rounded panel.
        c.create_polygon(
            366, 173, 784, 173,
            798, 173, 798, 187,
            798, 287, 798, 301,
            784, 301, 366, 301,
            352, 301, 352, 287,
            352, 187, 352, 173,
            smooth=True, splinesteps=16, fill='#234838',
            outline='#667B55', width=1)
        for seat, x0, x1 in (('Player1', 22, 566), ('Player2', 582, 1128)):
            c.create_rectangle(x0, 316, x1, 617, fill=self.ZONE_COLORS[seat], outline='')
            self.title_items[seat] = self._text(x0+220, 330, self.SEAT_NAMES[seat], 18, PANEL_BG)
            self._draw_wild_spot(seat, 'trips', x0+354, 490, 'Big\nKahuna', 40)
            self._draw_wild_spot(seat, 'ante', x0+240, 575, '前注', 40)
            # Hawaiian has no mandatory Blind bet.
            self._draw_progressive_lamp(seat, x0+354, 392)
            self._draw_wild_spot(seat, 'play', x0+130, 575, '加注', 40)
            for action, top, caption, color in (
                ('raise_high', 419, '加注2X', '#2B6639'),
                ('raise_low', 488, '加注1X', '#397A48'),
                ('check', 557, '不加注', '#173f66')):
                self.action_buttons[(seat, action)] = self.create_control_button(
                    x0+410, top, x1-15, top+58, caption,
                    lambda s=seat, a=action: self._action_click(s, a),
                    color, font_size=14, draw_shadow=False)
        self._draw_bottom_controls()
        for side in ('Dealer', *self.game.SEATS, 'Public'):
            for index in range(5 if side == 'Public' else 3):
                x, y = self.card_position(side, index)
                w, h = self.card_size(side)
                c.create_rectangle(x, y, x+w, y+h,
                    outline='#B59C6A' if side == 'Public' else '#7B9374',
                    dash=(3, 3), tags='card_slots')


    def card_position(self, side, index):
        if side == 'Public':
            return 363 + index * 86, 181
        if side == 'Dealer':
            return 447 + index * (self.CARD_WIDTH + 8), 40
        return (32 if side == 'Player1' else 592) + index * (self.CARD_WIDTH + 8), 347


    @staticmethod
    def _card_image_key(card):
        return card.suit, card.rank

    def _refresh(self):
        c = self.canvas
        c.itemconfigure(self.balance_item, text=f'余额: ${self.balance:,.2f}')
        total = sum(sum(b.values()) for b in self.bets.values())
        c.itemconfigure(self.total_item, text=f'本局下注: ${total:,.2f}' if total else f'上局返还: ${self.last_win:,.2f}')
        limits = ('$100', '$50,000', '$12,500') if self.high_bet_mode else ('$10', '$10,000', '$2,500')
        for item, value in zip(self.limit_value_items, limits):
            c.itemconfigure(item, text=value)
        self._render_chips()
        betting = self.game.stage == 'betting' and self._motion_count == 0
        self._refresh_mode_selector()
        self.set_control_button_state(self.clear_button, betting)
        self.set_control_button_state(self.repeat_button, betting and bool(self.last_bet))
        self.set_control_button_state(self.start_button, betting)
        restarting = self.game.stage in ('await_restart', 'returning', 'credit_pending', 'sweeping')
        c.itemconfigure(self.repeat_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button, state='normal' if restarting else 'hidden')
        self.set_control_button_state(self.restart_button, self.game.stage in ('await_restart', 'credit_pending'))
        discarding = self.game.stage == 'discard'
        captions = ('弃第1张', '弃第2张', '弃第3张') if discarding else ('加注2X', '加注1X', '不加注')
        for seat in self.game.SEATS:
            ready = (not self._decision_busy and self._motion_count == 0
                     and ((discarding and self.game.hands[seat] and self.game.discards[seat] is None)
                          or (self.game.stage == 'decision' and self.game.decisions[seat] == 'pending')))
            for index, action in enumerate(('raise_high', 'raise_low', 'check')):
                tag = self.action_buttons[(seat, action)]
                c.itemconfigure(tag, state='normal')
                button = self.control_buttons[tag]
                c.itemconfigure(button['text'], text=captions[index])
                button['fill'] = '#8C5340' if discarding else DARK_BLUE if action == 'check' else '#2B6639' if index == 0 else '#397A48'
                multiplier = 2 if index == 0 else 1 if index == 1 else 0
                affordable = discarding or self.game.bets[seat]['ante'] * multiplier <= self.balance
                self.set_control_button_state(tag, bool(ready and affordable))
        caption = '已结算' if restarting else {
            'betting': '下注阶段', 'decision': '翻牌前 · 0X / 1X / 2X',
            'discard': '翻牌后 · 点击底牌弃一张', 'revealing': '正在翻开前三张公共牌',
            'showdown': '最后开牌 · 庄家弃一张', 'settling': '派彩中',
            'progressive': '累进大奖下注', 'refunding': '退回未参与手牌下注', 'dealing': '发牌中',
        }.get(self.game.stage, '牌局进行中')
        c.itemconfigure(self.street_item, text=caption)
        self._status(caption)
        if self._mode_transition is not None:
            self._paint_mode_transition()


    def _after_initial_reveal(self):
        self._revealed_public = self.game.initial_public_count
        self.game.stage = 'decision'
        self._update_visible_titles()
        self._refresh()
        self._maybe_showdown()

    def _action_click(self, seat, action):
        if self.game.stage == 'discard':
            self.discard_action(seat, {'raise_high': 0, 'raise_low': 1, 'check': 2}[action])
        elif self.game.stage == 'decision':
            self._decide(seat, 'check' if action == 'check' else 'play',
                         2 if action == 'raise_high' else 1 if action == 'raise_low' else 0)


    def raise_action(self, multiplier, seat='Player1'):
        if self.game.stage == 'betting':
            self.set_pre_raise(seat, multiplier)
            return
        self._decide(seat, 'play', multiplier)

    def play_action(self, multiplier=0, seat='Player1'):
        if self.game.stage == 'betting':
            self.set_pre_raise(seat, multiplier)
            return
        self._decide(seat, 'play' if multiplier else 'check', multiplier)

    @staticmethod
    def _betting_cost(bets):
        return round(sum(sum(b.values()) for b in bets.values() if b['ante']), 2)


    def _next_raise_multiplier(self, seat):
        b = self.bets[seat]
        current = round(b['play']/b['ante']) if b['ante'] else 0
        cycle = (0, *self.game.pre_flop_multipliers)
        return cycle[(cycle.index(current)+1) % len(cycle)] if current in cycle else 1


    def cycle_raise_bet(self, seat):
        self.set_pre_raise(seat, self._next_raise_multiplier(seat))

    def set_pre_raise(self, seat, multiplier):
        if self.game.stage != 'betting' or self._motion_count or multiplier not in (0, *self.game.pre_flop_multipliers):
            return
        new = {s: dict(b) for s, b in self.bets.items()}
        b = new[seat]
        if multiplier and not b['ante']:
            return
        b['play'] = round(b['ante']*multiplier, 2)
        if multiplier and self._betting_cost(new) > self.balance:
            messagebox.showwarning('无法加注', '余额不足以支付所选下注。', parent=self)
            return
        self._apply_bet_layout(new)


    def add_chip_to_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count or kind not in self.game.empty_bet():
            return
        if kind == 'play':
            self.cycle_raise_bet(seat)
            return
        new = {s: dict(b) for s, b in self.bets.items()}
        b = new[seat]
        if kind == 'jackpot':
            b[kind] = 0 if b[kind] else 2.5
        else:
            limit = (50000 if self.high_bet_mode else 10000) if kind == 'ante' else (12500 if self.high_bet_mode else 2500)
            multiplier = round(b['play'] / b['ante']) if kind == 'ante' and b['ante'] else 0
            b[kind] = min(limit, b[kind] + self.selected_chip)
            if kind == 'ante':
                b['play'] = round(b['ante'] * multiplier, 2)
        self._apply_bet_layout(new)


    def reset_single_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count or kind not in self.game.empty_bet():
            return
        new = {s: dict(b) for s, b in self.bets.items()}
        new[seat][kind] = 0.0
        if kind == 'ante':
            new[seat]['play'] = 0.0
        self._apply_bet_layout(new)


    def fold_action(self, seat='Player1'):
        # Hawaiian has a one-card discard, not a UTH whole-hand fold.
        return None


    def _decide(self, seat, action, multiplier=0):
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
        self._update_visible_titles()
        self._refresh()
        def done():
            self._decision_busy = False
            self._refresh()
            self._maybe_showdown()
        if cost:
            def arrived():
                self._set_visual(seat, 'play', 'stake', cost)
                done()
            self._animate_chip(cost, self._rack_position(), self.bet_spots[(seat, 'play')]['center'], arrived)
        else:
            done()


    def _maybe_showdown(self):
        if self._decision_busy or self._showdown_started:
            return
        if self.game.stage == 'decision':
            if 'pending' in self.game.decisions.values():
                return
            self.game.stage, self.game.street = 'revealing', 'flop'
            self._refresh()
            def flop_revealed():
                self._revealed_public = 3
                self.game.stage = 'discard'
                self._update_visible_titles()
                self._refresh()
            self._reveal_next([('Public', i) for i in range(3)], 0, flop_revealed)
            return
        if self.game.stage != 'discard' or not self.game.all_players_discarded():
            return
        self._showdown_started = True
        self.game.stage, self.game.street = 'showdown', 'river'
        self._refresh()
        def revealed_all():
            self._revealed_public = 5
            discarded = self.game.choose_dealer_discard()
            self._animate_discard('Dealer', discarded, self._settle)
        self._reveal_next([('Public', 3), ('Public', 4), ('Dealer', 1), ('Dealer', 2)], 0, revealed_all)

    def discard_action(self, seat, index):
        if self.game.stage != 'discard' or self._decision_busy or self._motion_count:
            return
        try:
            self.game.discard(seat, index)
        except ValueError:
            return
        self.selected_discards[seat] = index
        self._decision_busy = True
        self.canvas.configure(cursor='')
        self._refresh()
        def done():
            self._decision_busy = False
            self._update_visible_titles()
            self._refresh()
            self._maybe_showdown()
        self._animate_discard(seat, index, done)

    def _animate_discard(self, side, discarded, complete):
        """Move the kept pair left and the discarded card right, dimmed and 90°."""
        hand = self.game.dealer_hand if side == 'Dealer' else self.game.hands[side]
        kept = [i for i in range(3) if i != discarded]
        order = kept + [discarded]
        width, height = self.card_size(side)
        positions = {i: self.card_position(side, slot) for slot, i in enumerate(order)}
        x, y = positions[discarded]
        positions[discarded] = (x, y + (height - width) / 2)
        starts = {i: tuple(self.canvas.coords(self.card_items[(side, i)])) for i in range(3)}
        source = self._pil_cards[self._card_image_key(hand[discarded])].resize((width, height), Image.Resampling.LANCZOS)
        self._motion_count += 1
        duration, steps = 360, 22
        def frame(step=0):
            p = step / steps
            eased = p * p * (3 - 2 * p)
            for i in range(3):
                item = self.card_items[(side, i)]
                sx, sy = starts[i]
                tx, ty = positions[i]
                self.canvas.coords(item, sx + (tx - sx) * eased, sy + (ty - sy) * eased)
            darkened = ImageEnhance.Brightness(source).enhance(1 - .65 * eased)
            rotated = darkened.rotate(-90 * eased, resample=Image.Resampling.BICUBIC, expand=True)
            photo = ImageTk.PhotoImage(rotated, master=self)
            self._discard_photos[(side, discarded)] = photo
            self.canvas.itemconfigure(self.card_items[(side, discarded)], image=photo)
            self.canvas.tag_raise(self.card_items[(side, discarded)])
            if step < steps:
                self._schedule(round(duration * (step + 1) / steps) - round(duration * step / steps), frame, step + 1)
            else:
                self._card_origins.update({(side, i): xy for i, xy in positions.items()})
                self._motion_count -= 1
                complete()
        frame()


    def _update_visible_titles(self):
        for seat in self.game.SEATS:
            if not self.game.hands[seat]:
                continue
            caption = self.SEAT_NAMES[seat]
            if self.game.stage == 'discard' and self.game.discards[seat] is None:
                caption += ' · 请选择弃牌'
            elif self.game.discards[seat] is not None and self._revealed_public >= 3:
                cards = self.game.kept_cards(seat) + self.game.public_cards[:self._revealed_public]
                caption += ' - ' + HAND_RANK_NAMES[find_best_5(cards)[0][0]]
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
        self.game.stage, self.last_win = 'settling', result['returned']
        try:
            save_progressive(self.game.progressive_amount)
        except Exception as exc:
            messagebox.showerror('奖池保存失败', str(exc), parent=self)
        for side in ('Dealer', *self.game.SEATS):
            self._update_hand_title(side)
        self._render_hand_usage()
        transfers, awards, round_id = [], [], time.time_ns()
        for seat, outcome in result['hands'].items():
            for kind in ('ante', 'play', 'trips'):
                transfers.extend(self._outcome_transfers(seat, kind, self.game.bets[seat][kind], outcome['details'][kind]))
            bonus = outcome['details']['bonus']
            if bonus:
                self._set_lamp_mode(seat, 'win')
                awards.append((seat, bonus))
            info = dict(outcome, seat=seat, round_id=round_id, bets=dict(self.game.bets[seat]),
                        fold=False, total_winnings=outcome['returned'], mode=self.game.mode,
                        variant=HAWAIIAN_VARIANT, dealer_qualification=False,
                        main_bet_name='前注', side_bet_name='Big Kahuna',
                        player_kept_cards=[str(c) for c in self.game.kept_cards(seat)],
                        player_discard=str(self.game.hands[seat][self.game.discards[seat]]),
                        dealer_kept_cards=[str(c) for c in self.game.kept_cards('Dealer')],
                        dealer_discard=str(self.game.dealer_hand[self.game.discards['Dealer']]),
                        progressive_cards=[str(c) for c in self.game.progressive_cards(seat)])
            try:
                save_hawaiian_history(self.game.deck, self.game.hands[seat], self.game.dealer_hand, self.game.public_cards, info)
            except Exception as exc:
                messagebox.showerror('历史记录保存失败', str(exc), parent=self)
        self._refresh()
        self._run_chip_batch(transfers, lambda: self._pay_progressive_awards(awards, jackpot_before))


    def _render_hand_usage(self):
        """Keep all discarded cards dark/sideways while highlighting a best five."""
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
                index = public_index if public_index is not None else next(i for i, c in enumerate(hand) if c is card)
                key = side, index
                used.add(key)
                users.setdefault(key, []).append(owner)
            self._hand_usage_keys[owner] = used
        self._final_usage = {key: tuple(owners) for key, owners in users.items()}
        self._default_usage_owner = 'Dealer'
        self._faded_photos.clear()
        self._settled_card_photos.clear()
        for (side, index), item in self.card_items.items():
            if side != 'Public' and self.game.discards[side] == index:
                photo = self._discard_photos[(side, index)]
                self._settled_card_photos[item] = self._faded_photos[item] = photo
                self.canvas.itemconfigure(item, image=photo)
                continue
            hand = self.game.public_cards if side == 'Public' else self.game.dealer_hand if side == 'Dealer' else self.game.hands[side]
            source = self._pil_cards[self._card_image_key(hand[index])].convert('RGBA').resize(self.card_size(side), Image.Resampling.LANCZOS)
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
        if self.game.stage == 'discard':
            current = set(self.canvas.find_withtag('current'))
            selectable = any(item in current and side in self.game.SEATS and self.game.discards[side] is None
                             for (side, _), item in self.card_items.items())
            self.canvas.configure(cursor='hand2' if selectable and not self._decision_busy else '')
            return
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

def main(initial_balance=10000, username="Guest", *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """嵌入现有 Tk 根窗口；未传 parent 时仍可独立运行。"""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return HawaiianGUI(
            parent, actual_balance, actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("夏威夷扑克")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = HawaiianGUI(root, actual_balance, actual_user)
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
