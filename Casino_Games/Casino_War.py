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
import json
import os
import math
import sys
import time
import random
import uuid
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP

# Shared continuous shuffler discovery (same project layout as Blackjack and
# Dragon Tiger): A_Tools/Card/CSM_Shuffler.py.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_CSM_CANDIDATES = [
    os.path.abspath(os.path.join(_THIS_DIR, '..', 'A_Tools', 'Card')),
    os.path.abspath(os.path.join(_THIS_DIR, '..', 'Card')),
    _THIS_DIR,
]
_CARD_TOOLS_DIR = next((p for p in _CSM_CANDIDATES
                        if os.path.isfile(os.path.join(p, 'CSM_Shuffler.py'))), None)
if _CARD_TOOLS_DIR is None:
    raise ModuleNotFoundError('找不到 CSM_Shuffler.py，已檢查：' + '; '.join(_CSM_CANDIDATES))
if _CARD_TOOLS_DIR not in sys.path:
    sys.path.insert(0, _CARD_TOOLS_DIR)

from CSM_Shuffler import CSMError, ContinuousShuffleMachine  # type: ignore

CASINO_WAR_VERSION = 'V6-SEVEN-TIER-PROGRESSIVE'

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

TIE_PAYOUTS = {1: 10, 2: 25, 3: 50, 4: 200}
MAX_TIES = 4
JACKPOT_MINIMUM = 82188.59
CASINO_WAR_PROGRESSIVE_KEY = 'CSO'  # Casino War only; Caribbean Stud uses a different pool.
# Ordered highest award first. Amounts are total returns on the $2.50 wager;
# no separate principal is returned. Share these rows with the rules window.
JACKPOT_PAYOUTS = (
    ('五张同花色、同点数', 'exact', 5, 'pool', '1'),
    ('四张同花色、同点数', 'exact', 4, 'pool', '0.10'),
    ('五张同点数', 'rank', 5, 'fixed', '6000'),
    ('五张同花', 'suit', 5, 'fixed', '3000'),
    ('四张同点数', 'rank', 4, 'fixed', '1500'),
    ('三张同花色、同点数', 'exact', 3, 'fixed', '1000'),
    ('四张同花', 'suit', 4, 'fixed', '300'),
)

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


def load_jackpot():
    path = str(_progressive_file)
    default = 82188.59
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item.get('Games') == CASINO_WAR_PROGRESSIVE_KEY:
                    return float(item.get('jackpot', default))
    except:
        pass
    return default


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
        if item.get('Games') == CASINO_WAR_PROGRESSIVE_KEY:
            item['jackpot'] = jackpot
            found = True
            break
    if not found:
        data.append({"Games": CASINO_WAR_PROGRESSIVE_KEY, "jackpot": jackpot})
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)


def casino_war_log_path() -> str:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Casino_War.json")


def save_casino_war_history(player_card, dealer_card, result_info=None,
                            player_war_card=None, dealer_war_card=None):
    """
    保存一局历史记录。
    :param player_card: 玩家初始牌 (Card)
    :param dealer_card: 庄家初始牌 (Card)
    :param result_info: 包含 winner 和 surrender 的字典
    :param player_war_card: 战争时玩家最后一张牌 (Card)，若无则为 None
    :param dealer_war_card: 战争时庄家最后一张牌 (Card)，若无则为 None
    """
    log_path = casino_war_log_path()
    data = {
        "history_record": {
            "player_win": 0,
            "dealer_win": 0,
            "war": 0,
            "war_fail": 0,
            "war_success": 0,
            "war_push": 0,
            "surrender": 0,
            "game": 0
        },
        "history": []
    }
    # 读取现有数据
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict) and "history_record" in loaded:
                    # 补全可能缺失的字段
                    for key in data["history_record"]:
                        if key not in loaded["history_record"]:
                            loaded["history_record"][key] = 0
                    data["history_record"] = loaded["history_record"]
                    if "history" in loaded:
                        data["history"] = loaded["history"]
                elif isinstance(loaded, list):
                    data["history"] = loaded
                    # 从历史记录重建统计（旧版兼容）
                    stats = {k: 0 for k in data["history_record"]}
                    stats["game"] = len(loaded)
                    for rec in loaded:
                        if "result" in rec and "winner" in rec["result"]:
                            winner = rec["result"]["winner"]
                            # 判断是否战争：检查 war_cards 是否有值
                            war_cards = rec.get("war_cards", {})
                            has_war = war_cards.get("player_war_card") is not None or war_cards.get("dealer_war_card") is not None
                            if has_war:
                                stats["war"] += 1
                                if winner == "player":
                                    stats["war_success"] += 1
                                elif winner == "dealer":
                                    stats["war_fail"] += 1
                                elif winner == "war_push":
                                    stats["war_push"] += 1
                            else:
                                if winner == "player":
                                    stats["player_win"] += 1
                                elif winner == "dealer":
                                    stats["dealer_win"] += 1
                                elif winner == "surrender":
                                    stats["surrender"] += 1
                    data["history_record"] = stats
        except Exception as e:
            print(f"读取历史文件出错: {e}")

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

    winner = result_info.get("winner") if result_info else None
    surrender = result_info.get("surrender", False) if result_info else False

    # 判断是否发生战争
    has_war = player_war_card is not None or dealer_war_card is not None

    if has_war:
        stats["war"] += 1
        if winner == "player":
            stats["war_success"] += 1
        elif winner == "dealer":
            stats["war_fail"] += 1
        elif winner == "war_push":
            stats["war_push"] += 1
        elif winner == "surrender":
            stats["surrender"] += 1
    else:
        if winner == "player":
            stats["player_win"] += 1
        elif winner == "dealer":
            stats["dealer_win"] += 1
        elif winner == "surrender":
            stats["surrender"] += 1
        # 其他情况（如 "push"）忽略

    # 构建新记录（移除了 deck_order 和 start_position）
    record = {
        "game_id": new_game_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "player_card": str(player_card),
        "dealer_card": str(dealer_card),
        "war_cards": {
            "player_war_card": str(player_war_card) if player_war_card else None,
            "dealer_war_card": str(dealer_war_card) if dealer_war_card else None
        },
        "result": result_info if result_info else {}
    }
    if winner is not None:
        record["result"]["winner"] = winner

    data["history"].append(record)

    # 只保留最近50条
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
    SUIT_SYMBOLS = {
        'Spade': '♠', 'Heart': '♥', 'Diamond': '♦', 'Club': '♣',
    }

    def __init__(self, csm, game_id):
        self.csm = csm
        self.game_id = str(game_id)
        self.card_buffer = []
        self.current_batch_id = None
        self.used_by_batch = {}
        self.round_open = False
        self.round_id = None

    def _clear_local_csm_state(self):
        self.round_id = None
        self.round_open = False
        self.card_buffer = []
        self.current_batch_id = None
        self.used_by_batch = {}

    def start_round(self):
        if self.round_open:
            raise RuntimeError('上一局尚未结束。')
        try:
            self.round_id = self.csm.begin_round(
                self.game_id, self.current_batch_id if self.card_buffer else None)
            self.used_by_batch = {}
            self.round_open = True
            if not self.card_buffer:
                self._request_next_chamber()
        except Exception:
            # CSM may already have rebuilt all warehouses after the primary error.
            # Drop every local lease/round reference so stale IDs are never reused.
            self._clear_local_csm_state()
            raise

    def _request_next_chamber(self):
        packet = self.csm.acquire_chamber(self.game_id, self.round_id)
        self.current_batch_id = packet['batch_id']
        self.card_buffer = list(packet['cards'])
        if not self.card_buffer:
            raise CSMError('自动洗牌机返回了空仓。')

    def deal(self, n=1):
        if not self.round_open:
            raise RuntimeError('牌局尚未开始。')
        dealt = []
        for _ in range(max(0, int(n))):
            if len(self.card_buffer) <= 3:
                self._request_next_chamber()
            record = self.card_buffer.pop(0)
            self.used_by_batch.setdefault(self.current_batch_id, []).append(record['card_id'])
            try:
                suit = self.SUIT_SYMBOLS[record['suit']]
                dealt.append(Card(suit, record['rank']))
            except (KeyError, TypeError, ValueError) as exc:
                raise CSMError(f'自动洗牌机返回无效牌张：{record!r}') from exc
        return dealt

    def finish_round(self):
        if not self.round_open:
            return
        rid = self.round_id
        try:
            for batch_id in list(self.used_by_batch):
                card_ids = self.used_by_batch[batch_id]
                if card_ids:
                    self.csm.return_cards(self.game_id, batch_id, card_ids)
                del self.used_by_batch[batch_id]
        except Exception:
            # Do not call end_round with a round ID that may have been erased by
            # CSM automatic recovery; preserve the primary error instead.
            self._clear_local_csm_state()
            raise
        try:
            self.csm.end_round(self.game_id, rid)
        finally:
            self.round_id = None
            self.round_open = False

    def close(self):
        try:
            self.csm.release_game(self.game_id, force_shuffle=True)
        finally:
            self._clear_local_csm_state()


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



class CasinoWarGame:
    """Two independent bets against a shared dealer, using the project's CSM.

    The initial tie counts as tie 1. At most three war deals follow it.
    A main-bet war costs one additional ante once; ties 2 and 3 are free.
    A surrendered main bet returns half once. Its purchased tie side bet
    continues through side-only wars with no fee or additional main return.
    Returns include wagered principal. No money is credited here.
    """
    SEATS = ('Player1', 'Player2')

    def __init__(self, csm, game_id):
        self.deck = Deck(csm, game_id)
        self.progressive_amount = load_jackpot()
        self.reset_game()

    @staticmethod
    def empty_bet():
        return dict(ante=0.0, tie=0.0, jackpot=0.0, war=0.0)

    def reset_game(self):
        if self.deck.round_open:
            raise RuntimeError('自动洗牌机的上一局尚未结束。')
        self.stage = 'betting'
        self.bets = {s: self.empty_bet() for s in self.SEATS}
        self.decisions = {s: 'inactive' for s in self.SEATS}
        self.tie_counts = {s: 0 for s in self.SEATS}
        self.hands = {s: [] for s in self.SEATS}
        self.dealer_hand = []
        self.player_rounds = {s: [] for s in self.SEATS}
        self.dealer_rounds = []
        self.results = {}
        self.surrendered = {s: False for s in self.SEATS}
        self.side_results = {}
        self.deal_log = []
        self.total_charged = 0.0
        self.war_round = 0
        self.settlement = None
        self._next_deal = None

    @property
    def active_seats(self):
        return tuple(s for s in self.SEATS if self.bets[s]['ante'] > 0)

    def start_round(self, bets, balance, high_bet_mode=False):
        if self.stage != 'betting':
            raise ValueError('上一局尚未完成。')
        minimum, maximum, side_max = (100, 50000, 12500) if high_bet_mode else (10, 10000, 2500)
        clean = {}
        for seat in self.SEATS:
            b = self.empty_bet()
            for kind in ('ante', 'tie', 'jackpot'):
                value = float(bets.get(seat, {}).get(kind, 0))
                if not math.isfinite(value) or value < 0 or round(value, 2) != value:
                    raise ValueError('下注金额必须是非负数，且最多两位小数。')
                b[kind] = value
            if b['ante'] == 0 and (b['tie'] or b['jackpot']):
                raise ValueError(f'{seat} 的边注需要同时购买主注。')
            if b['ante'] and not minimum <= b['ante'] <= maximum:
                raise ValueError(f'每手主注须为 ${minimum:,}–${maximum:,}。')
            if b['tie'] > side_max:
                raise ValueError(f'每手平局边注最高 ${side_max:,}。')
            if b['jackpot'] not in (0.0, 2.5):
                raise ValueError('平局累进大奖每手为 $2.50。')
            clean[seat] = b
        total = round(sum(sum(b.values()) for b in clean.values()), 2)
        if not any(b['ante'] for b in clean.values()):
            raise ValueError('请至少在一位玩家下注主注。')
        if balance < total:
            raise ValueError('余额不足以支付本局下注。')
        self.deck.start_round()
        self.bets = clean
        self.total_charged = total
        self.stage = 'dealing'
        for seat in self.active_seats:
            self.decisions[seat] = 'playing'
        # Delay the initial draw until the progressive chip animation finishes.
        self._next_deal = ('initial',)
        return total

    def _draw(self, side, count, burned=False):
        cards = self.deck.deal(count)
        self.deal_log.extend(dict(round=self.war_round, side=side,
                                  burned=burned, card=card) for card in cards)
        return cards

    def initial_sequence(self):
        if self._next_deal != ('initial',):
            raise RuntimeError('首轮发牌已开始。')
        self._next_deal = None
        sequence = []
        for side in (*self.active_seats, 'Dealer'):
            card = self._draw(side, 1)[0]
            if side == 'Dealer':
                self.dealer_hand = [card]
                self.dealer_rounds.append([card])
            else:
                self.hands[side] = [card]
                self.player_rounds[side].append([card])
            sequence.append((side, 2, card, False))
        return sequence

    @staticmethod
    def compare(player, dealer):
        return (player.value > dealer.value) - (player.value < dealer.value)

    def compare_initial(self):
        if self.stage != 'dealing' or not self.dealer_hand:
            raise RuntimeError('首轮牌尚未发完。')
        dealer = self.dealer_hand[-1]
        for seat in self.active_seats:
            comp = self.compare(self.hands[seat][-1], dealer)
            if comp == 0:
                self.tie_counts[seat] = 1
                self.decisions[seat] = 'pending'
            else:
                self.results[seat] = 'player' if comp > 0 else 'dealer'
                self.decisions[seat] = 'done'
        self.stage = 'decision' if any(d == 'pending' for d in self.decisions.values()) else 'ready_settle'

    def decide(self, seat, action, balance):
        if self.stage != 'decision' or self.decisions.get(seat) != 'pending':
            raise ValueError('这手牌当前不需要决定。')
        if action == 'surrender':
            self.surrendered[seat] = True
            self.decisions[seat] = 'side_war' if self.bets[seat]['tie'] else 'done'
            self.results[seat] = 'surrender'
            return 0.0
        if action != 'war':
            raise ValueError('未知决定。')
        fee = self.bets[seat]['ante']
        if balance < fee:
            raise ValueError('余额不足以支付战争费，请选择投降。')
        self.bets[seat]['war'] = fee
        self.total_charged = round(self.total_charged + fee, 2)
        self.decisions[seat] = 'war'
        return fee

    def prepare_war(self):
        if self.stage not in ('decision', 'war_continue'):
            raise RuntimeError('当前不能开战。')
        if any(d == 'pending' for d in self.decisions.values()):
            raise RuntimeError('请先完成两位玩家的决定。')
        seats = tuple(s for s in self.SEATS if self.decisions[s] in ('war', 'side_war'))
        if not seats:
            self.stage = 'ready_settle'
            return ()
        if any(self.tie_counts[s] >= MAX_TIES for s in seats):
            raise RuntimeError('已达到四次平局上限。')
        self.war_round += 1
        self.stage = 'war_dealing'
        self._next_deal = ('war', seats)
        return seats

    def war_sequence(self):
        if not self._next_deal or self._next_deal[0] != 'war':
            raise RuntimeError('战争发牌已开始。')
        _, seats = self._next_deal
        self._next_deal = None
        sequence = []
        # Each participating player gets three burns then one comparison card;
        # the shared dealer gets its own three burns then one comparison card.
        for side in (*seats, 'Dealer'):
            burns = self._draw(side, 3, burned=True)
            card = self._draw(side, 1)[0]
            packet = burns + [card]
            if side == 'Dealer':
                self.dealer_hand = packet
                self.dealer_rounds.append(packet)
            else:
                self.hands[side] = packet
                self.player_rounds[side].append(packet)
            sequence.extend((side, i + 1, c, i < 3) for i, c in enumerate(packet))
        return sequence

    def compare_war(self):
        if self.stage != 'war_dealing' or self._next_deal is not None:
            raise RuntimeError('战争牌尚未发完。')
        dealer = self.dealer_hand[-1]
        for seat in self.SEATS:
            if self.decisions[seat] not in ('war', 'side_war'):
                continue
            comp = self.compare(self.hands[seat][-1], dealer)
            if comp == 0:
                self.tie_counts[seat] += 1
                if self.tie_counts[seat] == MAX_TIES:
                    self.side_results[seat] = 'war_push'
                    if not self.surrendered[seat]:
                        self.results[seat] = 'war_push'
                    self.decisions[seat] = 'done'
            else:
                self.side_results[seat] = 'player' if comp > 0 else 'dealer'
                if not self.surrendered[seat]:
                    self.results[seat] = self.side_results[seat]
                self.decisions[seat] = 'done'
        self.stage = 'war_continue' if any(d in ('war', 'side_war') for d in self.decisions.values()) else 'ready_settle'

    @staticmethod
    def progressive_award(cards, pool):
        """Pay one highest qualifying tier from this seat's comparison cards.

        Counts mean at least N cards, anywhere in the final revealed group.
        Burns and other seats' cards must not be passed to this evaluator.
        """
        if len(cards) < 3:
            return 0.0, None
        counts = {
            'rank': max(Counter(c.rank for c in cards).values()),
            'exact': max(Counter((c.rank, c.suit) for c in cards).values()),
            'suit': max(Counter(c.suit for c in cards).values()),
        }
        pool_amount = Decimal(str(pool))
        for name, group, minimum, kind, value in JACKPOT_PAYOUTS:
            if counts[group] >= minimum:
                amount = Decimal(value)
                if kind == 'pool':
                    amount *= pool_amount
                return float(min(pool_amount, amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), name
        return 0.0, None

    def settle(self):
        if self.settlement is not None:
            return self.settlement
        if self.stage != 'ready_settle':
            raise RuntimeError('牌局尚未完成。')
        hands, total = {}, 0.0
        non_jackpot = sum(b['ante'] + b['tie'] + b['war'] for b in self.bets.values())
        jackpot_stakes = sum(b['jackpot'] for b in self.bets.values())
        pool = Decimal(str(self.progressive_amount))
        for seat in self.active_seats:
            b, result = self.bets[seat], self.results[seat]
            if result == 'surrender':
                main = b['ante'] * .5
            elif result == 'dealer':
                main = 0.0
            else:
                main = b['ante'] * 2 + b['war']
            reward = b['ante'] * 9 if result == 'war_push' else 0.0
            ties = self.tie_counts[seat]
            side_return = b['tie'] * (TIE_PAYOUTS[ties] + 1) if ties else 0.0
            bonus, bonus_name = 0.0, None
            if b['jackpot']:
                # Pair each of THIS seat's comparison cards with the dealer
                # from the same round. Later dealer cards may belong solely
                # to another seat's war and are excluded from this hand.
                cards = [card for index, packet in enumerate(self.player_rounds[seat])
                         for card in (packet[-1], self.dealer_rounds[index][-1])]
                bonus, bonus_name = self.progressive_award(cards, pool)
                pool -= Decimal(str(bonus))
                if any(bonus_name == name and kind == 'pool'
                       for name, _group, _minimum, kind, _value in JACKPOT_PAYOUTS):
                    pool = max(Decimal(str(JACKPOT_MINIMUM)), pool)
            returned = round(main + reward + side_return + bonus, 2)
            hands[seat] = dict(winner=result, ties=ties, main=round(main, 2),
                               reward=round(reward, 2), tie=round(side_return, 2),
                               jackpot=bonus, jackpot_name=bonus_name, returned=returned,
                               surrendered=self.surrendered[seat], side_winner=self.side_results.get(seat))
            total += returned
        contribution = Decimal(str(non_jackpot)) * Decimal('0.001') + Decimal(str(jackpot_stakes)) * Decimal('0.95')
        self.progressive_amount = float(max(Decimal(str(JACKPOT_MINIMUM)), Decimal(str(pool)) + contribution)
                                        .quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        self.settlement = dict(hands=hands, total_return=round(total, 2),
                               total_charged=self.total_charged, progressive_amount=self.progressive_amount)
        self.stage = 'settling'
        return self.settlement

    def finish_round(self):
        self.deck.finish_round()

    def close(self):
        self.deck.close()


def save_casino_war_round(game):
    """Keep the existing history entry shape and add both seats and all burns."""
    seat = game.active_seats[0]
    player_rounds = game.player_rounds[seat]
    result = dict(game.settlement['hands'][seat])
    result.update(surrender=result['winner'] == 'surrender',
                  hands=game.settlement['hands'], bets=game.bets,
                  total_charged=game.total_charged,
                  total_return=game.settlement['total_return'],
                  deal_sequence=[dict(round=row['round'], side=row['side'],
                                      burned=row['burned'], card=str(row['card'])) for row in game.deal_log],
                  player_rounds={s: [[str(c) for c in packet] for packet in game.player_rounds[s]]
                                 for s in game.active_seats},
                  dealer_rounds=[[str(c) for c in packet] for packet in game.dealer_rounds])
    save_casino_war_history(player_rounds[0][-1], game.dealer_rounds[0][-1], result,
                           player_rounds[-1][-1] if len(player_rounds) > 1 else None,
                           game.dealer_rounds[-1][-1] if len(player_rounds) > 1 else None)


class CasinoWarGUI(tk.Frame):
    WIDTH, HEIGHT = 1150, 750
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    DEAL_CARD_MS = 224 / .85
    DEAL_MOVE_MS = (128 / .75) / .85
    BET_CHIP_RADIUS = 16 * 4 / 3
    HOUSE_CHIP_POS = (575, 43)
    TABLE_GREEN = '#4b1e22'
    PROGRESSIVE_LAMP_WIDTH = 122.0 * .8
    FIVE_PLUS_ONE_DIAMETER = 122.0 * 2 / 3
    ZONE_COLORS = {'Player1': '#35634B', 'Player2': '#204536'}
    SEAT_NAMES = {'Player1': '玩家1', 'Player2': '玩家2', 'Dealer': '庄家'}

    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = username, float(initial_balance)
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.csm_game_id = f"CasinoWar:{self.username or 'local'}:{uuid.uuid4().hex}"
        self.csm = ContinuousShuffleMachine()
        self.game = CasinoWarGame(self.csm, self.csm_game_id)
        self.bets = {s: self.game.empty_bet() for s in self.game.SEATS}
        self.last_bet, self.last_win = None, 0.0
        self.high_bet_mode, self.selected_chip = False, 10.0
        self.csm_faulted = False
        self._jobs, self._closing = set(), False
        self._credited = self._return_persisted = self._crediting = False
        self._restart_job = self._restart_deadline = None
        self._motion_count = self._chip_serial = 0
        self._decision_busy = self._settlement_started = False
        self._main_resolved, self._side_resolved = set(), set()
        self.visual_chips, self.lamps = {}, {}
        self._face_photos, self._pil_cards, self._flip_photos = {}, {}, {}
        self.card_items, self.bet_spots, self.action_buttons = {}, {}, {}
        self._display_cards = {}
        self._load_assets()
        self._create_widgets()
        self._refresh()
        self.bind('<Destroy>', self._on_destroy, add='+')

    @property
    def game_in_progress(self):
        return self.game.stage != 'betting' or self._motion_count > 0

    def _create_widgets(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT, bg=ROOT_BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.control_buttons = {}
        c = self.canvas
        self._text(575, 18, '赌场战争  CASINO WAR', 16, GOLD)
        c.create_rectangle(355, 44, 795, 197, fill=self.TABLE_GREEN, outline='')
        self.title_items = {'Dealer': self._text(575, 57, '庄家', 16, PANEL_BG)}
        for seat, x0, x1 in (('Player1', 22, 566), ('Player2', 582, 1128)):
            c.create_rectangle(x0, 230, x1, 617, fill=self.ZONE_COLORS[seat], outline='')
            self.title_items[seat] = self._text((x0+x1)/2, 244, self.SEAT_NAMES[seat], 16, PANEL_BG)
        self._draw_limit_table()
        self._draw_progressive_panel()
        c.create_rectangle(22, 200, 1128, 226, fill='#173C2E', outline='#65784B', width=1)
        c.create_line(25, 201, 1125, 201, fill='#E0C879', width=2)
        c.create_line(25, 225, 1125, 225, fill='#0C241B', width=2)
        self.rule_item = self._text(575, 213, 'A 最大 · 最多连续4次平局 · 首次平局可选择开战或投降', 13, GOLD)
        for seat, x0, x1 in (('Player1', 22, 566), ('Player2', 582, 1128)):
            self._draw_progressive_lamp(seat, x0+103, 438)
            self._draw_spot(seat, 'tie', x0+113, 544, '平局注')
            self._draw_main_bet_pair(seat, x0+303, 448, 514)
            self.action_buttons[(seat, 'war')] = self.create_control_button(
                x0+410, 419, x1-15, 477, '开战', lambda s=seat: self.play_action(s),
                '#397A48', font_size=14, draw_shadow=False)
            self.action_buttons[(seat, 'surrender')] = self.create_control_button(
                x0+410, 488, x1-15, 546, '投降', lambda s=seat: self.fold_action(s),
                '#9B403A', font_size=14, draw_shadow=False)
        self._draw_bottom_controls()
        for side in ('Dealer', *self.game.SEATS):
            for index in (2,):
                x, y = self.card_position(side, index)
                c.create_rectangle(x, y, x+self.CARD_WIDTH, y+self.CARD_HEIGHT,
                                   outline='#7B9374', dash=(3, 3), tags='card_slots')

    def _status(self, message):
        self.current_status = message

    def _refresh(self):
        c = self.canvas
        c.itemconfigure(self.balance_item, text=f'余额: ${self.balance:,.2f}')
        total = self.game.total_charged if self.game.stage != 'betting' else sum(sum(b.values()) for b in self.bets.values())
        c.itemconfigure(self.total_item, text=f'本局下注: ${total:,.2f}' if total else f'上局返还: ${self.last_win:,.2f}')
        limits = ('$100', '$50,000', '$12,500') if self.high_bet_mode else ('$10', '$10,000', '$2,500')
        for item, value in zip(self.limit_value_items, limits):
            c.itemconfigure(item, text=value)
        self._render_chips()
        betting = self.game.stage == 'betting' and self._motion_count == 0 and not self.csm_faulted
        self.set_control_button_state(self.clear_button, betting)
        self.set_control_button_state(self.repeat_button, betting and bool(self.last_bet))
        self.set_control_button_state(self.start_button, betting)
        restarting = self.game.stage in ('await_restart', 'returning', 'credit_pending', 'sweeping')
        c.itemconfigure(self.repeat_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button, state='normal' if restarting else 'hidden')
        self.set_control_button_state(self.restart_button, self.game.stage in ('await_restart', 'credit_pending'))
        for (seat, action), button in self.action_buttons.items():
            self.set_control_button_state(button, self.game.stage == 'decision' and not self._decision_busy
                                          and self.game.decisions[seat] == 'pending')

    def add_chip_to_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count or self.csm_faulted:
            return
        if kind in ('war', 'reward'):
            return
        new = {s: dict(b) for s, b in self.bets.items()}
        if kind == 'jackpot':
            new[seat][kind] = 0.0 if new[seat][kind] else 2.5
        else:
            limit = (50000 if self.high_bet_mode else 10000) if kind == 'ante' else (12500 if self.high_bet_mode else 2500)
            new[seat][kind] = min(limit, new[seat][kind] + self.selected_chip)
        self._apply_bet_layout(new)

    def reset_single_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count or kind in ('war', 'reward'):
            return
        new = {s: dict(b) for s, b in self.bets.items()}
        if kind == 'ante':
            new[seat] = self.game.empty_bet()
        else:
            new[seat][kind] = 0.0
        self._apply_bet_layout(new)

    def start_game(self):
        if self.game.stage != 'betting' or self._motion_count or self.csm_faulted:
            return
        try:
            charged = self.game.start_round(self.bets, self.balance, self.high_bet_mode)
        except ValueError as exc:
            messagebox.showwarning('无法开始', str(exc), parent=self)
            return
        except (CSMError, OSError, RuntimeError) as exc:
            self._abort_csm_round(exc)
            return
        self.game.stage = 'progressive'
        self.balance = round(self.balance - charged, 2)
        self.bets = {s: dict(b) for s, b in self.game.bets.items()}
        self.last_bet = {s: dict(b) for s, b in self.bets.items()}
        self._credited = self._return_persisted = self._settlement_started = False
        self._decision_busy = False
        self._main_resolved.clear()
        self._side_resolved.clear()
        self._cancel_restart_timer()
        self.canvas.delete('cards')
        self.card_items.clear()
        self._display_cards.clear()
        self._flip_photos.clear()
        self._load_assets()
        for side, item in self.title_items.items():
            self.canvas.itemconfigure(item, text=self.SEAT_NAMES[side])
        if not self._persist_balance():
            self._abort_csm_round(RuntimeError('本局下注扣款保存失败。'), refund=charged)
            return
        self._status('发牌中 · 首次平局可选择开战或投降')
        self._refresh()
        self._start_progressive_lamps()

    def _start_progressive_lamps(self):
        participants = {s for s in self.game.SEATS if self.bets[s]['jackpot']}
        pending = set(participants)
        def filled(seat):
            pending.discard(seat)
            if not pending and self.game.stage == 'progressive':
                self._collect_progressive_and_deal()
        for seat in self.game.SEATS:
            if seat in pending:
                self.lamps[seat]['filled_callback'] = lambda s=seat: filled(s)
                self._set_lamp_mode(seat, 'fill')
            else:
                self._set_lamp_mode(seat, 'off')
        if not participants:
            self._schedule(0, self._collect_progressive_and_deal)

    def _collect_progressive_and_deal(self):
        transfers = []
        for seat in self.game.SEATS:
            chip = self.visual_chips.pop((seat, 'jackpot', 'stake'), None)
            if chip:
                transfers.append(dict(amount=chip['amount'], start=chip['xy'], target=self.HOUSE_CHIP_POS))
        def deal():
            self.game.stage = 'dealing'
            try:
                sequence = self.game.initial_sequence()
            except (CSMError, OSError, RuntimeError) as exc:
                self._abort_csm_round(exc)
                return
            self._deal_sequence(sequence, 0, self._after_initial_reveal)
        self._run_chip_batch(transfers, deal)

    def _deal_sequence(self, sequence, offset, complete):
        if offset == len(sequence):
            complete()
            return
        side, index, card, burned = sequence[offset]
        key = (side, index)
        x, y = self.card_position(side, index)
        rotated = index == 4
        item = self.canvas.create_image(575, 52, image=self._card_photo('back', rotated),
                                       anchor='nw', tags=('cards', 'cards_'+side))
        self.card_items[key] = item
        self._display_cards[key] = card
        def next_card():
            self._schedule(max(0, round(self.DEAL_CARD_MS - self.DEAL_MOVE_MS)),
                           self._deal_sequence, sequence, offset + 1, complete)
        def move(step=0):
            fraction = step / 6
            self.canvas.coords(item, 575+(x-575)*fraction, 52+(y-52)*fraction)
            if step < 6:
                self._schedule(round(self.DEAL_MOVE_MS*(step+1)/6)-round(self.DEAL_MOVE_MS*step/6), move, step+1)
            elif burned:
                # Each new burn overlaps the previous one by width - 20px.
                # No text overlays: the three backs remain visibly stacked.
                next_card()
            else:
                self._reveal_next([key], 0, next_card)
        move()


    def _after_initial_reveal(self):
        self.game.compare_initial()
        if self.game.stage != 'decision':
            self._settle()
            return
        # Finish the already-decided hand's chip movements BEFORE enabling
        # the other hand's war/surrender buttons. Profits stay on the table.
        self.game.stage = 'initial_settling'
        transfers = []
        for seat in self.game.active_seats:
            if self.game.decisions[seat] != 'done':
                continue
            transfers.extend(self._main_settlement_transfers(seat))
            self._side_resolved.add(seat)
            transfers.extend(self._outcome_transfers(seat, 'tie', self.bets[seat]['tie'], 0))
            self._set_lamp_mode(seat, 'off')
        def ready():
            self.game.stage = 'decision'
            self._status('首次平局 · 请选择开战或投降')
            self._refresh()
        self._refresh()
        self._run_chip_batch(transfers, ready)


    def play_action(self, seat='Player1'):
        self._decide(seat, 'war')

    def fold_action(self, seat='Player1'):
        self._decide(seat, 'surrender')

    def _decide(self, seat, action):
        if self._decision_busy:
            return
        try:
            fee = self.game.decide(seat, action, self.balance)
        except ValueError as exc:
            messagebox.showwarning('无法决定', str(exc), parent=self)
            return
        self._decision_busy = True
        transfers = []
        if action == 'surrender':
            # Collect the WHOLE ante and send a separate half-ante refund
            # to the upper-left win position, at the same time.
            transfers.extend(self._main_settlement_transfers(seat))
            if self.game.decisions[seat] == 'side_war':
                self._status('主注已投降 · 平局边注自动进入战争')
        elif fee:
            self.balance = round(self.balance - fee, 2)
            self.bets[seat]['war'] = fee
            if not self._persist_balance():
                self._abort_csm_round(RuntimeError('战争费扣款保存失败。'))
                return
            war_center = self.bet_spots[(seat, 'war')]['center']
            main_center = self.bet_spots[(seat, 'ante')]['center']
            locked_profit = (main_center[0]-32, main_center[1]-30)
            transfers.extend([
                dict(amount=fee, start=self._rack_position(), target=war_center,
                     arrive=lambda: self._set_visual(seat, 'war', 'stake', fee)),
                dict(amount=fee, start=self.HOUSE_CHIP_POS, target=locked_profit, duration=440,
                     arrive=lambda: self._set_visual(seat, 'ante', 'profit', fee, locked_profit))])
        def done():
            self._decision_busy = False
            self._refresh()
            if not any(d == 'pending' for d in self.game.decisions.values()):
                self._begin_war()
        self._refresh()
        self._run_chip_batch(transfers, done)


    def _begin_war(self):
        seats = self.game.prepare_war()
        if not seats:
            self._settle()
            return
        self._status(f'战争第{self.game.war_round}轮 · 每方先烧3张再发1张')
        self._refresh()
        def deal():
            try:
                sequence = self.game.war_sequence()
            except (CSMError, OSError, RuntimeError) as exc:
                self._abort_csm_round(exc)
                return
            self._deal_sequence(sequence, 0, self._after_war_reveal)
        self._move_previous_cards((*seats, 'Dealer'), deal)


    def _after_war_reveal(self):
        self.game.compare_war()
        if self.game.stage == 'war_continue':
            self.game.stage = 'war_main_settling'
            transfers = []
            for seat in self.game.active_seats:
                if self.game.decisions[seat] == 'done':
                    transfers.extend(self._main_settlement_transfers(seat))
            def again():
                self.game.stage = 'war_continue'
                self._refresh()
                self._schedule(900, self._begin_war)
            self._refresh()
            self._run_chip_batch(transfers, again)
        else:
            self._settle()


    def _main_settlement_transfers(self, seat):
        """Resolve each main wager once; all positive returns stay collectible."""
        if seat in self._main_resolved or seat not in self.game.results:
            return []
        self._main_resolved.add(seat)
        b, winner = self.bets[seat], self.game.results[seat]
        transfers = []
        if winner == 'dealer':
            for key in [key for key in self.visual_chips if key[0] == seat and key[1] in ('ante', 'war')]:
                chip = self.visual_chips.pop(key)
                transfers.append(dict(amount=chip['amount'], start=chip['xy'], target=self.HOUSE_CHIP_POS, duration=440))
        elif winner == 'surrender':
            center = self.bet_spots[(seat, 'ante')]['center']
            chip = self.visual_chips.pop((seat, 'ante', 'stake'), None)
            if chip:
                transfers.append(dict(amount=chip['amount'], start=chip['xy'], target=self.HOUSE_CHIP_POS, duration=440))
            refund = round(b['ante']*.5, 2)
            win_position = (center[0]-32, center[1]-30)
            transfers.append(dict(amount=refund, start=self.HOUSE_CHIP_POS, target=win_position, duration=440,
                arrive=lambda: self._set_visual(seat, 'ante', 'profit', refund, win_position)))
        elif not b['war']:
            transfers.extend(self._outcome_transfers(seat, 'ante', b['ante'], b['ante']*2))
        if winner == 'war_push':
            reward = b['ante']*9
            center = self.bet_spots[(seat, 'reward')]['center']
            transfers.append(dict(amount=reward, start=self.HOUSE_CHIP_POS, target=center, duration=440,
                arrive=lambda: self._set_visual(seat, 'reward', 'bonus', reward, center)))
        return transfers

    def _card_photo(self, key, rotated=False):
        if not rotated:
            return self._face_photos[key]
        if key not in self._rotated_photos:
            self._rotated_photos[key] = ImageTk.PhotoImage(
                self._pil_cards[key].transpose(Image.Transpose.ROTATE_270), master=self)
        return self._rotated_photos[key]

    def _move_previous_cards(self, sides, complete):
        """Keep all dealt cards, moving the latest group before the next deal.

        Comparison 1 goes to the far left. After tie 2, the first war packet
        slides intact to the far right. After tie 3, the second war packet
        slides beside comparison 1. The final packet is dealt between them.
        No burned card is exposed and horizontal cards keep their orientation.
        """
        motions = []
        for side in sides:
            if self.game.war_round == 1:
                keys = [(side, 2)]
            else:
                keys = [(side, index) for index in (1, 2, 3, 4)]
            for key in keys:
                item = self.card_items[key]
                if self.game.war_round == 1:
                    target = self.card_position(side, 0)
                    new_key = (side, 0)
                else:
                    packet = self.game.war_round-1
                    target = self._archive_card_position(side, packet, key[1])
                    new_key = (side, packet, key[1])
                motions.append(dict(key=key, new_key=new_key, item=item,
                                    start=tuple(self.canvas.coords(item)), target=target))
        self._motion_count += 1
        self._refresh()
        duration, steps = 360, 15
        def frame(index=0):
            fraction = index/steps
            eased = fraction*fraction*(3-2*fraction)
            for motion in motions:
                sx, sy = motion['start']
                tx, ty = motion['target']
                self.canvas.coords(motion['item'], sx+(tx-sx)*eased, sy+(ty-sy)*eased)
                self.canvas.tag_raise(motion['item'])
            if index < steps:
                self._schedule(round(duration*(index+1)/steps)-round(duration*index/steps), frame, index+1)
                return
            for motion in motions:
                key, new_key = motion['key'], motion['new_key']
                self.card_items[new_key] = self.card_items.pop(key)
                self._display_cards[new_key] = self._display_cards.pop(key)
            self._motion_count -= 1
            self._refresh()
            complete()
        frame()


    def _settle(self):
        if self._settlement_started:
            return
        self._settlement_started = True
        settlement = self.game.settle()
        self.last_win = settlement['total_return']
        self.progressive_amount_var.set(f'${self.game.progressive_amount:,.2f}')
        self._status('本局已结算 · 点击再来一局收取全部筹码')
        try:
            save_jackpot(self.game.progressive_amount)
        except (OSError, ValueError) as exc:
            messagebox.showerror('奖池保存失败', str(exc), parent=self)
        try:
            save_casino_war_round(self.game)
        except (OSError, ValueError, TypeError) as exc:
            messagebox.showerror('历史保存失败', str(exc), parent=self)
        try:
            self.game.finish_round()
        except (CSMError, OSError, RuntimeError) as exc:
            # The monetary outcome is final. Keep its return collectible even
            # when CSM recovery is required; only the NEXT deal is disabled.
            self.csm_faulted = True
            messagebox.showerror('自动洗牌机', f'归还牌张失败，下局已暂停：{exc}', parent=self)
        transfers = []
        for seat, outcome in settlement['hands'].items():
            b = self.bets[seat]
            transfers.extend(self._main_settlement_transfers(seat))
            if seat not in self._side_resolved:
                self._side_resolved.add(seat)
                transfers.extend(self._outcome_transfers(seat, 'tie', b['tie'], outcome['tie']))
            if outcome['jackpot']:
                center = self.bet_spots[(seat, 'jackpot')]['center']
                transfers.append(dict(amount=outcome['jackpot'], start=(957, 128), target=center, rectangular=True, duration=600,
                    arrive=lambda s=seat, a=outcome['jackpot']: self._set_visual(s, 'jackpot', 'bonus', a, rectangular=True)))
                self._set_lamp_mode(seat, 'win')
            else:
                self._set_lamp_mode(seat, 'off')
        self._refresh()
        self._run_chip_batch(transfers, self._await_next_round)

    def _await_next_round(self):
        if self.game.stage != 'settling':
            return
        self.game.stage = 'await_restart'
        self._cancel_restart_timer()
        awarded = any(o['jackpot'] or o['reward'] for o in self.game.settlement['hands'].values())
        if awarded:
            self._restart_caption('再来一局')
        else:
            self._restart_deadline = time.monotonic() + 30
        self._refresh()
        if not awarded:
            self._restart_tick()

    def _finish_round(self):
        if self.game.stage != 'sweeping':
            return
        for seat in self.game.SEATS:
            self._set_lamp_mode(seat, 'off')
        self.game.reset_game()
        self.bets = {s: self.game.empty_bet() for s in self.game.SEATS}
        self._display_cards.clear()
        for side, item in self.title_items.items():
            self.canvas.itemconfigure(item, text=self.SEAT_NAMES[side])
        self._status('自动洗牌机已暂停，请重新打开游戏' if self.csm_faulted else 'A 最大 · 最多连续4次平局')
        self._refresh()

    def _abort_csm_round(self, exc, refund=None):
        self._cancel_jobs()
        self._restart_job = self._restart_deadline = None
        refunded = self.game.total_charged if refund is None else refund
        # start_round can fail BEFORE any funds have actually been deducted.
        if refund is None and not self.game.active_seats:
            refunded = 0.0
        self.balance = round(self.balance + refunded, 2)
        self._motion_count = 0
        self._decision_busy = False
        self.canvas.delete('cards')
        self.canvas.delete('moving_chips')
        self.card_items.clear()
        self._display_cards.clear()
        self.visual_chips.clear()
        for lamp in self.lamps.values():
            lamp['job'] = None
            lamp['mode'] = 'off'
        try:
            self.game.close()
            self.game.reset_game()
        except (CSMError, OSError, RuntimeError) as close_exc:
            self.csm_faulted = True
            self.game.stage = 'betting'
            exc = RuntimeError(f'{exc}；归还牌张失败：{close_exc}')
        self.bets = {s: self.game.empty_bet() for s in self.game.SEATS}
        self.last_win = 0.0
        self._persist_balance()
        self._status(f'本局取消 · 已退还 ${refunded:,.2f}')
        self._refresh()
        messagebox.showerror('自动洗牌机', f'本局已取消并退还 ${refunded:,.2f}。\n{exc}', parent=self)

    def reset_game(self, auto_reset=False):
        if self.game.stage == 'betting':
            self.reset_bets()
        elif self.game.stage == 'await_restart':
            self._return_all_chips()

    def on_close(self):
        if self._closing or self._crediting:
            return
        settled = self.game.stage in ('settling', 'await_restart', 'returning', 'credit_pending', 'sweeping')
        if self.game_in_progress and not settled:
            messagebox.showinfo('牌局进行中', '请先完成本局决定和结算。', parent=self)
            return
        if settled:
            if not self._credit_round_return():
                return
        elif not self._persist_balance():
            return
        try:
            self.game.close()
        except (CSMError, OSError, RuntimeError) as exc:
            messagebox.showerror('自动洗牌机', f'归还或洗牌失败：{exc}', parent=self)
            return
        self._closing = True
        self._cancel_restart_timer()
        self._cancel_jobs()
        self._unbind_enter()
        if callable(self.on_back):
            self.on_back(float(self.balance))
        else:
            self.winfo_toplevel().destroy()


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
        self._rotated_photos = {}
        size = (self.CARD_WIDTH, self.CARD_HEIGHT)
        self.original_images = {}
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'A_Tools', 'Card', 'Poker2')
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


    @staticmethod
    def _row_layout(side):
        left, right, top = {'Dealer':(355,795,74), 'Player1':(22,566,260),
                            'Player2':(582,1128,260)}[side]
        # All four comparison groups fit inside the existing card region.
        # The dealer has exactly 80 + 3*120 pixels available in one row.
        initial = left if side == 'Dealer' else left+37
        third = initial+80+(0 if side == 'Dealer' else 10)
        second = right-120-(0 if side == 'Dealer' else 12)
        return dict(initial=initial, third=third, second=second,
                    final=(third+second)/2, center=(left+right)/2, top=top)

    @staticmethod
    def _archive_card_position(side, packet, index):
        layout = CasinoWarGUI._row_layout(side)
        base = layout['second'] if packet == 1 else layout['third']
        if index in (1, 2, 3):
            return base+(index-1)*20, layout['top']
        return base+4, layout['top']+16

    def card_position(self, side, index):
        layout = CasinoWarGUI._row_layout(side)
        if index == 0:
            return layout['initial'], layout['top']
        round_number = getattr(getattr(self, 'game', None), 'war_round', 0)
        base = layout['final'] if round_number >= 3 else layout['center']-60
        if index in (1, 2, 3):
            return base+(index-1)*20, layout['top']
        return base+4, layout['top']+16




    def _reveal_next(self, sequence, offset, complete):
        if offset == len(sequence):
            complete()
            return
        side, index = sequence[offset]
        card = self._display_cards[(side, index)]
        item = self.card_items[(side, index)]
        x, y = self.card_position(side, index)
        rotated = index == 4
        face_key = (card.suit, card.rank)
        def flip(step=0):
            source = self._pil_cards['back' if step < 5 else face_key]
            # Form the NORMAL flip first, then rotate its entire frame 90°.
            # The horizontal card therefore collapses vertically to a line.
            fraction = abs(1-step/5)
            width = max(1, round(self.CARD_WIDTH*fraction))
            frame = source.resize((width, self.CARD_HEIGHT), Image.Resampling.LANCZOS)
            if rotated:
                frame = frame.transpose(Image.Transpose.ROTATE_270)
            photo = ImageTk.PhotoImage(frame, master=self)
            self._flip_photos[item] = photo
            full_width, full_height = (self.CARD_HEIGHT, self.CARD_WIDTH) if rotated else (self.CARD_WIDTH, self.CARD_HEIGHT)
            self.canvas.itemconfigure(item, image=photo)
            self.canvas.coords(item, x+(full_width-frame.width)/2, y+(full_height-frame.height)/2)
            if step < 10:
                self._schedule(32, flip, step+1)
            else:
                self.canvas.itemconfigure(item, image=self._card_photo(face_key, rotated))
                self._flip_photos.pop(item, None)
                self._reveal_next(sequence, offset+1, complete)
        flip()




    def _draw_limit_table(self):
        # 保留原加勒比的标题 + 三列限红表，改成深绿/金色。
        c = self.canvas
        x0,x1,y0 = 30,349,75
        c.create_rectangle(x0,y0,x1,181,fill='#183B30',outline=GOLD,width=1,tags='limits')
        c.create_rectangle(x0,y0,x1,y0+29,fill='#40634B',outline=GOLD,tags='limits')
        self._text((x0+x1)/2,y0+14,'下注上限',13,PANEL_BG,tags='limits')
        titles = ('主注最低','主注最高','边注最高')
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
        tk.Label(panel,text='平局累进大奖',font=('Arial',24,'bold'),
                 bg='#315C40',fg='#F6D675').pack(fill=tk.X)
        self.progressive_amount_var = tk.StringVar(self,f'${self.game.progressive_amount:,.2f}')
        self.progressive_display = ProgressiveSevenSegmentDisplay(panel,self.progressive_amount_var,
            font=('Arial',24,'bold'),bg='#123C30',fg='#FFE29A')
        self.progressive_display.pack(pady=10)


    def _register_spot(self, seat, kind, cx, cy, border, label, angle=0):
        c,tag = self.canvas,'spot_'+seat+'_'+kind
        self._text(cx,cy,label,14,PANEL_BG,angle=angle,tags=tag)
        self.bet_spots[(seat,kind)] = dict(tag=tag,center=(cx,cy),border=border)
        c.tag_bind(tag,'<Button-1>',lambda _e,s=seat,k=kind:self.add_chip_to_bet(s,k))
        c.tag_bind(tag,'<Button-3>',lambda _e,s=seat,k=kind:self.reset_single_bet(s,k))
        c.tag_bind(tag,'<Enter>',lambda _e:c.configure(cursor='hand2'))
        c.tag_bind(tag,'<Leave>',lambda _e:c.configure(cursor=''))


    @staticmethod
    def _make_ante_ship():
        """Draw the reference's white sails, gold hull and waves on transparent RGBA.

        The symbol is generated in code, so no extra image asset is required.
        The reference's chips and badges are intentionally omitted.
        """
        sample = 6
        layer = Image.new('RGBA', (160*sample, 128*sample), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        def curve(start, segments):
            points = [start]
            previous = start
            for segment in segments:
                if segment[0] == 'L':
                    previous = (segment[1], segment[2])
                    points.append(previous)
                else:
                    _, ax, ay, bx, by, ex, ey = segment
                    px, py = previous
                    for step in range(1, 19):
                        t = step / 18
                        u = 1 - t
                        points.append((u*u*u*px + 3*u*u*t*ax + 3*u*t*t*bx + t*t*t*ex,
                                       u*u*u*py + 3*u*u*t*ay + 3*u*t*t*by + t*t*t*ey))
                    previous = (ex, ey)
            return [(round(x*sample), round(y*sample)) for x, y in points]

        def stroke(start, segments, color, width=1):
            draw.line(curve(start, segments), fill=color, width=max(1, round(width*sample)), joint='curve')

        def shape(start, segments, color, outline=None, width=.7):
            points = curve(start, segments)
            draw.polygon(points, fill=color)
            if outline:
                draw.line(points+[points[0]], fill=outline, width=max(1, round(width*sample)), joint='curve')

        ivory, edge = '#fffdf7', '#d1c5c4'
        gold, highlight = '#e9ae2d', '#ffe284'
        # Gold masts and the long bowsprit, behind the sails.
        stroke((50, 23), [('L', 47, 87)], gold, 1.5)
        stroke((76, 28), [('L', 77, 88)], gold, 1.5)
        stroke((101, 42), [('L', 102, 88)], gold, 1.3)
        stroke((27, 80), [('L', 1, 67)], gold, 1.7)
        stroke((94, 83), [('L', 123, 76)], gold, 1.5)
        # Three narrow, flowing pennants.
        shape((50, 24), [('C', 58, 19, 63, 27, 72, 24),
                         ('C', 66, 28, 61, 25, 56, 28), ('L', 50, 29)], gold)
        stroke((53, 24), [('C', 60, 22, 64, 26, 70, 24)], highlight, .8)
        shape((76, 29), [('C', 82, 25, 87, 32, 98, 29),
                         ('C', 91, 35, 84, 29, 77, 34)], gold)
        stroke((78, 29), [('C', 85, 28, 90, 32, 96, 29)], highlight, .7)
        shape((101, 43), [('C', 107, 39, 112, 44, 122, 41),
                          ('C', 117, 47, 108, 44, 101, 48)], gold)
        # The broad triangular stern sail at the far left.
        shape((3, 66), [('C', 12, 55, 27, 41, 44, 33),
                        ('C', 35, 43, 29, 59, 28, 74), ('L', 3, 66)], ivory, edge)
        # Two curved sails on the left mast.
        shape((43, 36), [('C', 39, 46, 37, 55, 35, 62),
                         ('C', 44, 60, 53, 60, 63, 62),
                         ('C', 64, 52, 64, 43, 65, 35),
                         ('C', 58, 36, 50, 36, 43, 36)], ivory, edge)
        shape((36, 63), [('C', 34, 69, 35, 76, 39, 81),
                         ('C', 48, 78, 56, 78, 64, 81),
                         ('C', 62, 74, 62, 68, 63, 62),
                         ('C', 52, 61, 44, 62, 36, 63)], ivory, edge)
        # The taller center mast has a small topsail and two square sails.
        shape((70, 28), [('L', 83, 29), ('L', 83, 36), ('L', 69, 36)], ivory, edge)
        shape((68, 38), [('C', 76, 38, 84, 39, 92, 38),
                         ('C', 91, 46, 92, 52, 94, 59),
                         ('C', 83, 57, 75, 58, 67, 59),
                         ('C', 68, 51, 68, 44, 68, 38)], ivory, edge)
        shape((67, 61), [('C', 76, 59, 85, 59, 94, 61),
                         ('C', 92, 68, 92, 76, 94, 82),
                         ('C', 84, 80, 75, 80, 65, 83),
                         ('C', 68, 76, 68, 69, 67, 61)], ivory, edge)
        # Smaller bow sail, leaning forward.
        shape((98, 52), [('C', 104, 52, 110, 51, 114, 49),
                         ('C', 115, 57, 118, 64, 122, 71),
                         ('C', 114, 73, 106, 75, 97, 74),
                         ('C', 99, 68, 99, 60, 98, 52)], ivory, edge)
        # Gold gunwale and dark hull, with a clear crescent-shaped bow.
        shape((22, 79), [('C', 47, 86, 87, 87, 120, 77),
                         ('L', 113, 89), ('C', 85, 95, 51, 96, 32, 87),
                         ('L', 22, 79)], gold)
        shape((34, 89), [('C', 57, 94, 88, 92, 111, 88),
                         ('L', 103, 100), ('C', 80, 106, 54, 103, 42, 98),
                         ('L', 34, 89)], '#725d79')
        stroke((26, 81), [('C', 54, 89, 87, 89, 118, 79)], highlight, 1.3)
        shape((108, 95), [('L', 108, 105), ('L', 115, 106), ('L', 111, 100)], gold)
        # Two rows of pale waves, matching the reference without a betting ring.
        for y, alpha in ((109, 210), (118, 175)):
            for x in (35, 56, 77, 98):
                stroke((x, y), [('C', x+6, y+5, x+14, y+5, x+21, y)],
                       (245, 237, 242, alpha), .9)
        return layer.resize((240, 192), Image.Resampling.LANCZOS)

    def _draw_main_bet_pair(self, seat, cx, ante_y, play_y):
        """The ship alone is the clickable ante; escrow positions have no artwork."""
        if not hasattr(self, '_ante_ship_image'):
            self._ante_ship_image = self._make_ante_ship()
            self._ante_ship_photo = ImageTk.PhotoImage(self._ante_ship_image, master=self)
        x0, y0 = cx-115, ante_y-40
        tag = 'spot_'+seat+'_ante'
        image_item = self.canvas.create_image(x0, y0, image=self._ante_ship_photo,
                                              anchor='nw', tags=tag)
        center = (cx, ante_y+47)
        self.bet_spots[(seat, 'ante')] = dict(tag=tag, center=center, border=image_item)
        # The war fee and fourth-tie reward are accounting/animation positions,
        # not side bets: no circle, label, click binding or betting control.
        self.bet_spots[(seat, 'war')] = dict(tag='escrow_'+seat, center=(cx+54, center[1]), border=None)
        self.bet_spots[(seat, 'reward')] = dict(tag='reward_'+seat, center=(cx, center[1]+88), border=None)

        def on_ship(event):
            x = round(self.canvas.canvasx(event.x)-x0)
            y = round(self.canvas.canvasy(event.y)-y0)
            return (0 <= x < self._ante_ship_image.width and 0 <= y < self._ante_ship_image.height
                    and self._ante_ship_image.getpixel((x, y))[3] > 24)

        def click(event, clear=False):
            if not on_ship(event):
                return
            if clear:
                self.reset_single_bet(seat, 'ante')
            else:
                self.add_chip_to_bet(seat, 'ante')

        self.canvas.tag_bind(tag, '<Button-1>', click)
        self.canvas.tag_bind(tag, '<Button-3>', lambda event: click(event, True))
        self.canvas.tag_bind(tag, '<Motion>', lambda event: self.canvas.configure(cursor='hand2' if on_ship(event) else ''))
        self.canvas.tag_bind(tag, '<Leave>', lambda _event: self.canvas.configure(cursor=''))




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
        for char,angle in zip('平局累进大奖',(150,126,102,78,54,30)):
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
        if abs(value)>=1000:return CasinoWarGUI._compact(value)
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


    def _restart_tick(self):
        self._restart_job=None
        if self.game.stage!='await_restart' or self._restart_deadline is None:return
        remaining=max(0,self._restart_deadline-time.monotonic())
        self._restart_caption(f'再来一局({math.ceil(remaining)})')
        if remaining<=0:
            self._return_all_chips()
            return
        self._restart_job=self._schedule(max(1,min(1000,math.ceil(remaining*1000))),self._restart_tick)




    def _return_all_chips(self):
        if self.game.stage=='credit_pending':
            self._complete_chip_return()
            return
        if self.game.stage!='await_restart':return
        self._cancel_restart_timer()
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

        dialog.title('赌场战争 (Casino War) 规则')

        dialog.configure(bg='#faf5e8')

        dialog.resizable(False, False)

        dialog.transient(parent)



        width, height = 1000, 670

        parent.update_idletasks()

        px, py = parent.winfo_rootx(), parent.winfo_rooty()

        pw, ph = max(1, parent.winfo_width()), max(1, parent.winfo_height())

        dialog.geometry(f'{width}x{height}+{px + (pw-width)//2}+{py + (ph-height)//2}')



        manual_pages = [('玩法',
          '自动洗牌机 · 双玩家牌桌 · 两手分别结算',
          [['一局流程',
            '',
            [('下注', '每位玩家购买主注，可选平局注及$2.50平局累进大奖。'),
             ('初始发牌', '已下注的玩家和庄家各发一张。A最大，2最小，花色不分大小。'),
             ('首次平局', '先结算已分胜负的手牌，再让平局的玩家选择开战或投降。'),
             ('开战', '额外支付主注1倍的战争费，筹码放在主注右侧。\n庄家同时派主注1倍到主注左上方，暂时不能收取。'),
             ('投降', '原注全部收走，同时把原注50%派到获胜位置。\n如有平局注，自动继续战争；不再收战争费，主注不再赔付，也无九倍奖励。'),
             ('结算', '主注按每手的结果先后结算，平局注及平局累进大奖于最后派彩。\n点击再来一局收取筹码。')],
            []]]),
         ('战争 & 连续平局',
          '首次平局计为第1次，最多连续4次。',
          [['战争发牌',
            '',
            [('玩家', '初始牌移到最左侧。烧3张牌，每张错开20px叠放；\n新比牌旋转90°，放在三张烧牌正中间。'),
             ('庄家', '庄家同样先移牌、烧3张叠放，再将第4张旋转90°置于正中间。'),
             ('两手同时开战', '每位参战玩家各烧3张再发1张，然后庄家烧3张再发1张。\n两手共用该张庄家战争牌，各自比较和记录连续平局次数。'),
             ('第2、3次平局', '无须再次询问或重复支付战争费。第2次平局将整组牌移到最右侧；\n第3次平局将整组牌移到初始牌右侧，第4次比牌在两组牌中间发。'),
             ('第4次平局', '立即结束，无第5次比牌。返还主注、战争费和庄家暂存赔付，\n另外奖励主注9倍，奖励筹码放在原始主注下方。')],
            []]]),
         ('下注 & 限红',
          '点击筹码后点击下注区域；右键清除单项。',
          [['下注限红',
            '',
            [],
            [('限红',
              ['项目', '普通模式', '高额模式'],
              [['主注', '$10–$10,000', '$100–$50,000'],
               ['平局注', '最高$2,500', '最高$12,500'],
               ['平局累进大奖', '每手$2.50', '每手$2.50'],
               ['战争费', '首次开战收主注1倍', '只收一次']])]]]),
         ('主注 & 平局注赔率',
          '赔率为净盈利；以下返还金额均包括本金。',
          [['主注结算',
            '',
            [],
            [('主注示例（主注$10）',
              ['结果', '玩家支付', '返还'],
              [['首轮赢', '$10', '$20'],
               ['首轮输', '$10', '$0'],
               ['投降', '$10', '$5'],
               ['战争赢', '$20（主注+战争费）', '$30（两注本金+庄家赔付）'],
               ['战争输', '$20', '$0（庄家暂存赔付也收走）'],
               ['连续4次平局', '$20', '$120（$30返还+$90奖励）']])]],
           ['平局边注',
            '',
            [('结算方式', '以这手最终达到的连续平局次数，按最高一档派彩，不累加各档。\n无平局则输；投降后仍自动继续战争追踪边注。\n直到两手结束才派彩；派彩包括边注本金。')],
            [('',
              ['连续平局次数', '净盈利赔率', '$10边注返还'],
              [['1次', '10:1', '$110'],
               ['2次', '25:1', '$260'],
               ['3次', '50:1', '$510'],
               ['4次', '200:1', '$2,010']])]]]),
         ('平局累进大奖',
          '七档奖金 · 累计全部明牌 · 每手只赔最高一档',
          [['判奖方式',
            '',
            [('参与', '每手下注$2.50并实际进行战争才参与判奖，包含投降后继续的边注战争。'),
             ('判奖牌', '累计该玩家与庄家在该手实际参与的每轮比牌明牌，包括最后不平局的牌。\n最多8张，不计烧牌、另一位玩家的牌或该手结束后的庄家牌。'),
             ('判奖规则', '数量均指至少N张，不必连续；同局符合多项时，只赔表内最高一档。\n同花指相同花色（♠、♥、♦、♣），不是相同红黑颜色。'),
             ('派彩', '普通和高额模式采用相同奖金，最终结算时统一派彩。\n表内为总到账奖金，$2.50大奖注本金不另外退；未达七档牌型则无奖金。'),
             ('奖池', '百分比奖金按该手结算时的奖池计算，先派彩再加入本局入池金额。\n两手依次结算；使用赌场战争专属奖池，保留原入池及最低奖池补足规则。')],
            [('奖金',
              ['牌型', '奖金'],
              [[name, f'{Decimal(value) * 100:.0f}%奖池' if kind == 'pool'
                else f'${Decimal(value):,.0f}']
               for name, _group, _minimum, kind, value in JACKPOT_PAYOUTS])]]])]

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

        tk.Label(header, text='赌场战争 (Casino War) 规则', font=(font_name, 20, 'bold'),

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
        return CasinoWarGUI(
            parent, actual_balance, actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("赌场战争")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = CasinoWarGUI(root, actual_balance, actual_user)
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
