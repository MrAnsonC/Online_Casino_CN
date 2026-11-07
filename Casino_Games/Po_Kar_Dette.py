# -*- coding: utf-8 -*-
"""Po Kar Dette — 四副牌、四张公共牌的 Tk 游戏。

在原项目中，将本文件放在 Roulette_American.py 同一目录。大厅入口沿用
main(initial_balance, username, *, parent, balance, user, on_back, on_balance_change)。
嵌入进入／退出沿用 Ultimate_Texas_Holdem：返回 Frame，由大厅管理页面及主窗口。
使用带 Tkinter 的 Python 3.8+，执行 python Po_Kar_Dette.py 即可独立运行。
Guest 可独立试玩。共享牌靴被其他窗口占用时，访客使用单独的内存牌桌。

下注 ID 沿用轮盘的 straight_N、outside_0..5（Low、Even、Red、Black、
Odd、High）和 column_2/1/0（T/M/B）。四个花色使用 suit_diamonds、
suit_hearts、suit_clubs、suit_spades。牌使用百家乐的 (suit, rank) 顺序。

账户沿用 A_Tools/Account/saving_data.json 的 user_name 与两位小数 cash。
余额沿用 UTH：以大厅传入金额开始，扣注、返还及离桌时通过宿主加密 JSON 保存并回传大厅。
旧版账户内的 _Po_Kar_Dette 待付回执仅用于兼容恢复，新局不再写入该字段。
本桌记录写入 A_Logs/Json/Po_Kar_Dette.json：累计局数、最近10局和可恢复牌序。
"""

from __future__ import annotations

import errno
import json
import math
import os
import random
import re
import shutil
import sys
import time
import tkinter as tk
import uuid
from collections import Counter, deque
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
from tkinter import messagebox, simpledialog
from typing import Optional

try:
    from PIL import Image, ImageTk, ImageDraw, ImageChops, ImageFilter
except ImportError:
    Image = ImageTk = ImageDraw = ImageChops = ImageFilter = None


SUITS = ("Club", "Diamond", "Heart", "Spade")
RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
SYMBOL = {"Club": "♣", "Diamond": "♦", "Heart": "♥", "Spade": "♠"}
RED_SUITS = frozenset(("Heart", "Diamond"))
BLACK_SUITS = frozenset(("Club", "Spade"))
POINTS = dict(zip(RANKS, (1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 0, 0, 0)))
BURN_VALUES = dict(zip(RANKS, (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10)))
DECKS = 4
SHOE_SIZE = DECKS * len(SUITS) * len(RANKS)
CUT_MIN_TAIL = (SHOE_SIZE * 17 + 99) // 100
CUT_MAX_TAIL = SHOE_SIZE * 23 // 100
LOW, EVEN, RED, BLACK, ODD, HIGH = (f"outside_{i}" for i in range(6))
TOP, MIDDLE, BOTTOM = "column_2", "column_1", "column_0"
POKER_ORDER = "poker_order"
MAX_HISTORY = 10
# 同点数指相同牌面：10 / J / Q / K 分别判定，不合并为百家乐的 0 点。
POKER_PAYOUTS = (
    ("suited_nines", "4张同花9", 2_700_000),
    ("suited_four", "4张同花点数，但非9", 225_000),
    ("four_nines", "4张9，但非4张同花9", 5_500),
    ("four_kind", "4张点数一样，但非9且非同花四条", 450),
    ("straight_flush", "4张同花顺", 900),
    ("straight", "4张顺子，但非同花顺", 12),
    ("flush", "4张同花，但非同花顺且非四同花点数", 7),
)
POKER_CATEGORIES = {key: (label, payout) for key, label, payout in POKER_PAYOUTS}


# 仅 0 与 7–30 的单独数字格属于内注，其余每个下注格均属于外注。
@dataclass(frozen=True)
class LimitProfile:
    name: str
    chips: tuple
    number_max: int
    outside_max: int

    @property
    def minimum(self):
        return self.chips[0]

    def maximum(self, key):
        return self.number_max if BET_SPOTS[key]["type"] == "straight" else self.outside_max


NORMAL = LimitProfile("普通", (10, 25, 100, 500, 1000, 2500), 2500, 10000)
HIGH_LIMITS = LimitProfile("高额", (100, 500, 1000, 5000, 10000, 50000), 12500, 50000)
NORMAL_COLORS = ("#ffa500", "#00ff00", "#050505", "#ff7dda", "#ffffff", "#ff2a23")
HIGH_COLORS = ("#050505", "#ff7dda", "#ffffff", "#ff2a23", "#00fbff", "#00ffae")


def build_bet_spots():
    """同一份定义供结算、下注格、赔率显示和帮助使用。赔率为净赢倍数。"""
    spots = {}

    def add(key, kind, label, payout, numbers=(), suits=()):
        spots[key] = dict(id=key, type=kind, label=label, payout=payout,
                          numbers=frozenset(str(n) for n in numbers),
                          suits=frozenset(suits))

    straight = {
        0: 100, 7: 20, 8: 20, **dict.fromkeys(range(9, 19), 15),
        19: 20, 20: 23, 21: 25, 22: 30, 23: 40, 24: 50, 25: 60,
        26: 80, 27: 100, 28: 150, 29: 200, 30: 300,
    }
    for number, payout in straight.items():
        add(f"straight_{number}", "straight", str(number), payout, [number])
    add(LOW, "high_low", "小 1–6", 7, range(1, 7))
    add(HIGH, "high_low", "大 31–36", 200, range(31, 37))
    for key, label, first in ((TOP, "上排", 1), (MIDDLE, "中排", 2),
                              (BOTTOM, "下排", 3)):
        add(key, "column", label, 2, range(first, 37, 3))
    add(ODD, "odd_even", "单", 1, range(1, 37, 2))
    add(EVEN, "odd_even", "双", 1, range(0, 37, 2))
    add(RED, "color", "红", 12, suits=RED_SUITS)
    add(BLACK, "color", "黑", 12, suits=BLACK_SUITS)
    add(POKER_ORDER, "poker", "扑克顺序", 0)  # 按实际最高档牌型动态结算。
    for suit, plural, label in (("Diamond", "diamonds", "方块"), ("Heart", "hearts", "红桃"),
                                ("Club", "clubs", "梅花"), ("Spade", "spades", "黑桃")):
        add("suit_" + plural, "suit", label, 210, suits=[suit])
    return spots


BET_SPOTS = build_bet_spots()


@dataclass(frozen=True)
class Outcome:
    cards: tuple
    total: int
    color: str
    winners: frozenset
    pushes: frozenset
    poker_category: str = ""
    poker_payout: int = 0

    @property
    def poker_label(self):
        return POKER_CATEGORIES[self.poker_category][0] if self.poker_category else "未中奖"


def evaluate_poker_order(cards):
    """只看四张牌的组合，不要求发牌顺序；A 可作 A234 或 JQKA，不允许循环。"""
    ranks = [rank for suit, rank in cards]
    same_suit = len({suit for suit, rank in cards}) == 1
    same_rank = len(set(ranks)) == 1
    if same_rank:
        if ranks[0] == "9":
            category = "suited_nines" if same_suit else "four_nines"
        else:
            category = "suited_four" if same_suit else "four_kind"
    else:
        values = sorted({RANKS.index(rank) + 1 for rank in ranks})
        straight = (len(values) == 4 and
                    (values[-1] - values[0] == 3 or values == [1, 11, 12, 13]))
        category = ("straight_flush" if straight and same_suit else "straight" if straight
                    else "flush" if same_suit else "")
    return category, POKER_CATEGORIES[category][1] if category else 0


def evaluate_hand(cards):
    cards = tuple(cards)
    if (len(cards) != 4 or any(not isinstance(c, (tuple, list)) or len(c) != 2
                               or c[0] not in SUITS or c[1] not in RANKS for c in cards)):
        raise ValueError("每局需要四张有效的 (花色, 牌面) 扑克牌。")
    cards = tuple(tuple(c) for c in cards)
    suits = frozenset(suit for suit, rank in cards)
    total = sum(POINTS[rank] for suit, rank in cards)
    color = "Red" if suits <= RED_SUITS else "Black" if suits <= BLACK_SUITS else "Mixed"
    winners = {key for key, spot in BET_SPOTS.items()
               if str(total) in spot["numbers"] or suits <= spot["suits"]}
    category, poker_payout = evaluate_poker_order(cards)
    if category:
        winners.add(POKER_ORDER)
    return Outcome(cards, total, color, frozenset(winners), frozenset(), category, poker_payout)


@dataclass(frozen=True)
class BetResult:
    spot_id: str
    stake: int
    returned: int
    status: str

    @property
    def net_profit(self):
        return self.returned - self.stake


@dataclass(frozen=True)
class Settlement:
    bets: tuple

    @property
    def total_stake(self):
        return sum(bet.stake for bet in self.bets)

    @property
    def total_return(self):
        return sum(bet.returned for bet in self.bets)

    @property
    def net_profit(self):
        return self.total_return - self.total_stake


def settle_bets(bets, outcome, multiplier=1):
    """新桌直接结算各格实押金额。可传原版倍数复算旧局。"""
    if type(multiplier) is not int or multiplier not in (1, 2, 5, 10, 20, 50, 100):
        raise ValueError("无效的下注倍数。")
    lines = []
    for key, amount in bets.items():
        if key not in BET_SPOTS:
            raise ValueError(f"无效的下注区域：{key}")
        if type(amount) is not int or amount <= 0:
            raise ValueError("筹码必须为正整数。")
        stake = amount * multiplier
        if key in outcome.winners:
            payout = outcome.poker_payout if key == POKER_ORDER else BET_SPOTS[key]["payout"]
            status, returned = "win", stake * (payout + 1)
        elif key in outcome.pushes:
            status, returned = "push", stake
        else:
            status, returned = "lose", 0
        lines.append(BetResult(key, stake, returned, status))
    return Settlement(tuple(lines))


class Shoe:
    """四副牌的可恢复牌靴，切牌及烧牌流程与百家乐一致。

    黄色切牌为边界，不进入 208 张真实扑克牌。新靴必须先切牌、烧牌，
    发牌跨过边界时完成当前局，下一局重新切牌；不暗中洗牌或跳过烧牌。
    """

    def __init__(self, rng=None, state=None):
        self.rng = random.SystemRandom() if rng is None else rng
        self.shuffle_count = 0
        if not self._restore(state):
            self.new_shoe()

    def new_shoe(self):
        self.deck = [(s, r) for _ in range(DECKS) for s in SUITS for r in RANKS]
        self.rng.shuffle(self.deck)
        self.cut_threshold = self.rng.randint(CUT_MIN_TAIL, CUT_MAX_TAIL)
        self.shuffle_count += 1
        self.current_index = 0
        self.cut_position = None
        self.cut_complete = False
        self.burn_complete = False
        self.burn_rule = "baccarat"

    def cut_shoe(self, cut_position, cut_threshold=None):
        if self.current_index or self.cut_complete:
            raise ValueError("此牌靴已经切牌，不能再次移动牌序。")
        cut = int(cut_position)
        tail = self.cut_threshold if cut_threshold is None else int(cut_threshold)
        if not 0 < cut < SHOE_SIZE or not CUT_MIN_TAIL <= tail <= CUT_MAX_TAIL:
            raise ValueError("切点或黄色切牌位置无效。")
        self.deck = self.deck[cut:] + self.deck[:cut]
        self.cut_position, self.cut_threshold = cut, tail
        self.cut_complete = True

    @property
    def indicator(self):
        return self.deck[0]

    @property
    def burn_count(self):
        value = BURN_VALUES[self.indicator[1]]
        # 旧版已烧好半数的牌靴继续沿用原牌序；新靴统一使用百家乐规则。
        return (value + 1) // 2 if self.burn_rule == "half" else value

    @property
    def marker_index(self):
        return len(self.deck) - self.cut_threshold

    @property
    def ready(self):
        return self.cut_complete and self.burn_complete and not self.needs_shuffle()

    def remaining_cards(self):
        return len(self.deck) - self.current_index

    def needs_shuffle(self):
        return self.remaining_cards() <= self.cut_threshold

    def draw_card(self):
        if not self.cut_complete or self.current_index >= len(self.deck):
            raise RuntimeError("请先完成切牌。")
        card = self.deck[self.current_index]
        self.current_index += 1
        return card

    def finish_burn(self):
        if not self.cut_complete or self.current_index != 1 + self.burn_count:
            raise RuntimeError("烧牌尚未完成，不能开放下注。")
        self.burn_complete = True

    def deal_round(self):
        if not self.ready:
            raise ShoePreparationRequired("请先完成新牌靴的切牌和烧牌。")
        if self.remaining_cards() < 4:
            raise RuntimeError("牌靴状态异常，当前局无法发足四张牌。")
        return tuple(self.draw_card() for _ in range(4))

    def snapshot(self):
        return dict(deck=[list(card) for card in self.deck], current_index=self.current_index,
                    cut_threshold=self.cut_threshold, marker_index=self.marker_index,
                    cut_position=self.cut_position, cut_complete=self.cut_complete,
                    burn_complete=self.burn_complete, burn_rule=self.burn_rule,
                    burn_count=self.burn_count, remaining_cards=self.remaining_cards(),
                    shuffle_count=self.shuffle_count)

    def _restore(self, state):
        if not isinstance(state, dict):
            return False
        try:
            deck = [tuple(card) for card in state["deck"]]
            copies = Counter(deck)
            if len(deck) != SHOE_SIZE or any(copies[s, r] != DECKS for s in SUITS for r in RANKS):
                return False
            index, tail, count = state["current_index"], state["cut_threshold"], state["shuffle_count"]
            cut_done = state.get("cut_complete", True)
            burn_done = state.get("burn_complete", False)
            rule = state.get("burn_rule", "half")
            cut = state.get("cut_position")
            if (any(type(n) is not int for n in (index, tail, count)) or count < 1
                    or not CUT_MIN_TAIL <= tail <= CUT_MAX_TAIL
                    or type(cut_done) is not bool or type(burn_done) is not bool
                    or rule not in ("half", "baccarat")
                    or (cut is not None and (type(cut) is not int or not 0 < cut < SHOE_SIZE))):
                return False
            value = BURN_VALUES[deck[0][1]]
            first = 1 + ((value + 1) // 2 if rule == "half" else value)
            if burn_done:
                if not cut_done or not first <= index <= SHOE_SIZE - tail + 3 or (index-first) % 4:
                    return False
            elif not 0 <= index <= (first if cut_done else 0):
                return False
        except (KeyError, TypeError, ValueError):
            return False
        self.deck, self.current_index, self.cut_threshold, self.shuffle_count = deck, index, tail, count
        self.cut_position, self.cut_complete = cut, cut_done
        self.burn_complete, self.burn_rule = burn_done, rule
        return True


# 沿用 UTH 的账户接口：通过项目组件安装 JSON 钩子，在原路径对真实文件调用
# json.load / json.dump。账户实现和密钥由宿主提供。
@lru_cache(maxsize=1)
def _account_root():
    for parent in Path(__file__).resolve().parents:
        if (parent / "A_Tools" / "Account" / "secure_json.py").is_file():
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            from A_Tools.Account import install_secure_json # type: ignore
            install_secure_json()
            return parent
    return None


# 与 UTH 一样，在首次使用 json.load / json.dump 前安装项目的账户加密钩子。
# 无项目组件时仍允许 Guest 独立试玩，实名账户入口仍要求宿主加密组件。
_account_root()


def project_root():
    root = _account_root()
    if root is None:
        raise RuntimeError("Cannot locate encrypted account storage")
    return str(root)


def user_data_path():
    return os.path.join(project_root(), "A_Tools", "Account", "saving_data.json")


def game_log_path():
    root = _account_root() or Path(__file__).resolve().parent
    return root / "A_Logs" / "Json" / "Po_Kar_Dette.json"


def _recover_file(path):
    """上一次写入中断时，仅恢复写入前保存的原始字节。"""
    backup = path.with_name(path.name + ".pkd-backup")
    if backup.exists():
        if backup.stat().st_size:
            os.replace(backup, path)
        else:
            path.unlink(missing_ok=True)
            backup.unlink()
    return backup


def _read_json(path, default):
    _recover_file(path)
    if not path.exists():
        return default
    with open(str(path), "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path, value):
    # 钩子可能按完整路径选择加密策略，始终把原文件名交给它。
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = _recover_file(path)
    temp = backup.with_suffix(".pkd-copy")
    try:
        if path.exists():
            shutil.copyfile(path, temp)
        else:
            temp.write_bytes(b"")
        os.replace(temp, backup)
        with open(str(path), "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=4)
        backup.unlink()
    except Exception:
        _recover_file(path)
        raise
    finally:
        temp.unlink(missing_ok=True)


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


def _cash(value):
    if isinstance(value, str) and "," in value:
        # 兼容 UTH 保存的带千位分隔符、两位小数的 cash。
        value = value.strip()
        if not re.fullmatch(r"[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?", value):
            raise ValueError("无效的账户金额。")
        value = value.replace(",", "")
    try:
        cash = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("无效的账户金额。") from exc
    if not cash.is_finite() or cash < 0:
        raise ValueError("无效的账户金额。")
    return cash


def _account(users, username):
    return next((u for u in users if u.get("user_name") == username), None)


def load_balance(username, default_balance=1_000_000.0):
    """兼容旧调用；大厅嵌入入口不再用账户文件覆盖传入的余额。"""
    initial = _cash(default_balance)
    if not username or username == "Guest":
        return float(initial)
    users = load_user_data()
    user = _account(users, username)
    return float(_cash(user["cash"])) if user is not None and "cash" in user else float(initial)


def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:,.2f}"
            break
    save_user_data(users)


class BetError(ValueError):
    """可由玩家修改下注后重试的错误。"""


class ShoeBusy(BetError):
    """另一局正在使用共享牌靴，Tk 在事件循环中重试。"""


class ShoePreparationRequired(BetError):
    """当前牌靴需在界面完成切牌／烧牌后才能发牌。"""


class TableStore:
    """牌靴与最近十局记录；余额读写、格式和回调沿用 UTH。

    开桌时短暂读取记录。封盘至入账期间独占共享牌靴，空闲窗口可以并存。
    大厅传入金额是本次会话余额，不从账户文件重载覆盖。
    """

    # 只为迁移旧版已扣款但未返还的受保护回执保留；新局不写入此字段。
    ACCOUNT_STATE_KEY = "_Po_Kar_Dette"

    def __init__(self, username, initial_balance, on_balance_change=None):
        self.username = username
        self.path = game_log_path()
        if _account_root() is None and username != "Guest":
            raise RuntimeError("Cannot locate encrypted account storage")
        self._lock = None
        self.data = {"Total": 0, "Red": 0, "Black": 0, "Mixed": 0,
                     "Record1": {}, "HistoryCount": 0}
        self.balance = _cash(initial_balance)
        self.on_balance_change = on_balance_change
        self._active_round = None
        self._credited = False
        self._return_persisted = False
        self._crediting = False
        self.synced = self.path is None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.journal = self.path.with_name("Po_Kar_Dette_pending.json")
            if self._try_lock():
                try:
                    self._load_shared_state()
                finally:
                    self.release()
            elif username == "Guest":
                self.path = None
                self.synced = True

    def _try_lock(self):
        if self._lock is not None:
            return True
        try:
            handle = open(self.path.with_suffix(".lock"), "a+b")
        except PermissionError as exc:
            if self.username == "Guest" or getattr(exc, "winerror", None) in (32, 33):
                return False
            raise
        try:
            if sys.platform == "win32":
                import msvcrt
                if handle.tell() == 0:
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK) or getattr(exc, "winerror", None) in (32, 33):
                return False
            raise
        self._lock = handle
        return True

    def _load_shared_state(self):
        self.data = _read_json(self.path, self.data)
        if not isinstance(self.data, dict):
            raise ValueError("牌桌记录格式错误。")
        self._trim_history()
        self.recover()
        self.synced = True

    def persist_balance(self):
        """移植 UTH 的 _persist_balance：加密账户保存后，以 float 回传大厅。"""
        if self.username and self.username != 'Guest':
            update_balance_in_json(self.username, float(self.balance))
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))

    def sync_for_exit(self):
        """沿用 UTH：保存并回传当前会话余额，不重新读取旧余额。"""
        self.persist_balance()

    def reserve_round(self):
        """成功时持锁至本局入账；返回另一窗口已经推进的牌靴。"""
        if not self.path:
            return None
        if not self._try_lock():
            if self.username == "Guest":
                self.path = None  # 忙碌时，访客沿用自己的模拟筹码在内存中开桌。
                return None
            raise ShoeBusy("正在等待上一局完成结算。")
        before = self.data.get("temp_data")
        try:
            self._load_shared_state()
            current = self.data.get("temp_data")
            if before != current:
                return current
            return None
        except Exception:
            self.release()
            raise

    def release(self):
        if self._lock is not None:
            self._lock.close()
            self._lock = None

    def _trim_history(self):
        """兼容旧 Record / Record2，只保留最近十局，不删除累计局数。"""
        old = self.data.get("Record1", self.data.get("Record", self.data.get("Record2", {})))
        if not isinstance(old, dict):
            raise ValueError("牌局历史格式错误。")
        keys = sorted(k for k in old if re.fullmatch(r"[0-9]+_Data", str(k)))
        keys.sort(key=lambda key: int(key.split("_", 1)[0]))
        entries = [old[key] for key in keys if isinstance(old[key], dict)
                   and old[key].get("result") not in (None, "")][:MAX_HISTORY]
        trimmed = {f"{i:02d}_Data": item for i, item in enumerate(entries, 1)}
        changed = (self.data.get("Record1") != trimmed or "Record" in self.data
                   or "Record2" in self.data or self.data.get("HistoryCount") != len(entries))
        self.data = dict(self.data, Record1=trimmed, HistoryCount=len(entries))
        self.data.pop("Record", None)
        self.data.pop("Record2", None)
        if changed and self.path:
            _write_json(self.path, self.data)

    def _record_round(self, record):
        if self.data.get("last_round_id") == record["id"]:
            return
        color = record["color"]
        total = int(self.data.get("Total", 0)) + 1
        entry = {k: record[k] for k in ("result", "color", "cards")}
        entry.update(round_id=record["id"], round_number=total,
                     poker_category=record.get("poker_category", ""),
                     poker_payout=record.get("poker_payout", 0))
        old = self.data.get("Record1", {})
        entries = [old[f"{i:02d}_Data"] for i in range(1, MAX_HISTORY + 1)
                   if old.get(f"{i:02d}_Data", {}).get("result") not in (None, "")]
        records = [entry] + entries[:MAX_HISTORY - 1]
        data = dict(self.data, Record1={f"{i:02d}_Data": item
                                      for i, item in enumerate(records, 1)},
                    Total=total, HistoryCount=len(records))
        data.pop("Record2", None)
        data.pop("Record", None)
        data[color] = int(data.get(color, 0)) + 1
        data["last_round_id"] = record["id"]
        data["temp_data"] = record["shoe"]
        if self.path:
            _write_json(self.path, data)
        self.data = data

    def remember_shoe(self, shoe):
        state = shoe.snapshot()
        before = self.data.get("temp_data")
        if state == before:
            return True
        if not self.path:
            self.data = dict(self.data, temp_data=state)
            return True
        if self._lock is not None:
            data = dict(self.data, temp_data=state)
            _write_json(self.path, data)
            self.data = data
            return True
        if self.synced and self._try_lock():
            try:
                live = _read_json(self.path, self.data)
                if live.get("temp_data") != before:
                    return False  # 封盘／准备牌靴时接上其他窗口已推进的牌序。
                self.data = dict(live, temp_data=state)
                _write_json(self.path, self.data)
                return True
            finally:
                self.release()
        return False

    def _finish_history(self, round_id, pending):
        if self.data.get("last_round_id") != round_id:
            if not isinstance(pending, dict) or pending.get("id") != round_id:
                raise RuntimeError("牌局记录缺失，账户中的结算回执已保留。")
            self._record_round(pending)

    def recover(self):
        """只迁移旧版账户回执；新局使用 UTH 的内存入账标志和统一保存接口。"""
        if not self.path:
            return
        pending = _read_json(self.journal, None)
        if not self.username or self.username == "Guest":
            return
        users = load_user_data()
        changed = False
        recovered_credit = 0
        for account in users:
            state = account.get(self.ACCOUNT_STATE_KEY)
            if state is None:
                continue
            if not isinstance(state, dict):
                raise ValueError("账户内的牌桌恢复资料格式错误。")
            if "held" in state:
                credit = state["held"]
                if type(credit) is not int or credit <= 0:
                    raise ValueError("账户内的待退筹码无效。")
            else:
                round_id = state.get("round_id")
                if not isinstance(round_id, str) or not round_id:
                    raise ValueError("账户内的牌局回执无效。")
                self._finish_history(round_id, pending)
                # 旧版仅带 round_id 的回执已支付过；带 returned 的回执记录尚未返还的金额。
                credit = state.get("returned", 0)
                if type(credit) is not int or credit < 0:
                    raise ValueError("账户内的待付金额无效。")
            account["cash"] = f"{_cash(account['cash']) + credit:,.2f}"
            if account.get("user_name") == self.username:
                recovered_credit += credit
            del account[self.ACCOUNT_STATE_KEY]
            changed = True
        if changed:
            save_user_data(users)
            self.balance += recovered_credit
        if pending is not None:
            self.journal.unlink(missing_ok=True)

    def open_round(self, receipt, record):
        """采用 UTH 的扣注流程；保存与回调均使用同一份会话余额。"""
        after = self.balance - receipt.total_stake
        if after < 0:
            raise BetError("余额不足。")
        self._active_round = record
        self._credited = False
        self._return_persisted = False
        self.balance = after
        self.persist_balance()
        self._record_round(record)

    def credit_return(self, round_id, returned):
        """移植 UTH 的 _credit_round_return：只加一次，保存失败重试不重复派彩。"""
        if self._return_persisted:
            return
        if self._crediting:
            raise BetError("正在保存本局返还，请稍后重试。")
        if not self._active_round or self._active_round.get("id") != round_id:
            raise RuntimeError("无法核对本局结算回执。")
        self._crediting = True
        try:
            self._record_round(self._active_round)
            if not self._credited:
                self.balance += returned
                self._credited = True
            self.persist_balance()
            self._return_persisted = True
        finally:
            self._crediting = False


class Table:
    """独立于 Tk 的下注与封盘状态。封盘后先结算保存，再向界面公开牌面。"""

    def __init__(self, store, rng=None):
        self.store = store
        self.shoe = Shoe(rng, store.data.get("temp_data"))
        self.current_bets = {}
        self.last_bets = {}
        self.limits = NORMAL
        self.phase = "result"
        self.outcome = None
        self.settlement = None
        self._round_id = None
        self.next_round()

    @property
    def held(self):
        return sum(self.current_bets.values())

    def collect_return(self):
        if self.phase in ("awaiting_collection", "locked") and self._round_id is not None:
            self.store.credit_return(self._round_id, self.settlement.total_return)
            self.phase = "result"
            self.store.release()

    def next_round(self):
        self.collect_return()
        if self.phase != "result":
            return
        self.store.remember_shoe(self.shoe)
        self.current_bets = {}
        self.phase = "betting"

    def prepare_shoe(self):
        """切牌至烧牌完成期间独占牌靴，防止两个窗口改变同一份牌序。"""
        self._require_betting()
        latest = self.store.reserve_round()
        try:
            if latest is not None:
                self.shoe = Shoe(self.shoe.rng, latest)
            if self.shoe.ready:
                self.store.release()
                return False
            if self.shoe.needs_shuffle():
                self.shoe.new_shoe()
            self.phase = "preparing_shoe"
            self.store.remember_shoe(self.shoe)
            return True
        except Exception:
            self.phase = "betting"
            self.store.release()
            raise

    def finish_shoe_preparation(self):
        self.shoe.finish_burn()
        self.store.remember_shoe(self.shoe)
        self.phase = "betting"
        self.store.release()

    def _require_betting(self):
        if self.phase != "betting":
            raise BetError("已经停止下注。")

    def _check_bets(self, bets):
        for key, amount in bets.items():
            if key not in BET_SPOTS or type(amount) is not int:
                raise BetError("无效的下注区域或金额。")
            limit = self.limits.maximum(key)
            if not self.limits.minimum <= amount <= limit:
                raise BetError(f'{BET_SPOTS[key]["label"]} 每格可押 ${self.limits.minimum:,} 至 ${limit:,}。')
        if sum(bets.values()) > self.store.balance:
            raise BetError("余额不足以支付本局下注。")

    def set_high_limits(self, enabled):
        self._require_betting()
        profile = HIGH_LIMITS if enabled else NORMAL
        if self.limits is not profile:
            self.current_bets.clear()
            self.last_bets.clear()
            self.limits = profile

    def place_bet(self, spot_id, amount):
        self._require_betting()
        if spot_id not in BET_SPOTS or type(amount) is not int or amount not in self.limits.chips:
            raise BetError("请选择本档筹码与有效下注格。")
        limit = self.limits.maximum(spot_id)
        existing = self.current_bets.get(spot_id, 0)
        if existing >= limit:
            raise BetError(f"本格已达上限 ${limit:,}。")
        bets = dict(self.current_bets)
        bets[spot_id] = min(limit, existing + amount)
        self._check_bets(bets)
        self.current_bets = bets
        return bets[spot_id] - existing

    def clear_bets(self, spot_id=None):
        self._require_betting()
        if spot_id is None:
            self.current_bets.clear()
        else:
            self.current_bets.pop(spot_id, None)

    def repeat_bets(self):
        self._require_betting()
        if not self.last_bets:
            raise BetError("尚无上局下注。")
        self._check_bets(self.last_bets)
        self.current_bets = dict(self.last_bets)

    def deal(self):
        self._require_betting()
        latest_shoe = self.store.reserve_round()
        try:
            if latest_shoe is not None:
                self.shoe = Shoe(self.shoe.rng, latest_shoe)
            self._check_bets(self.current_bets)
            if not self.shoe.ready:
                raise ShoePreparationRequired("请先完成新牌靴的切牌和烧牌。")
        except Exception:
            self.store.release()
            raise
        self.phase = "locked"
        self.outcome = self.settlement = None
        start = self.shoe.current_index
        self.outcome = evaluate_hand(self.shoe.deal_round())
        marker = self.shoe.marker_index
        self.round_cut_card_offset = marker - start if start < marker <= self.shoe.current_index else None
        self.settlement = settle_bets(self.current_bets, self.outcome)
        record = dict(id=uuid.uuid4().hex, result=str(self.outcome.total),
                      color=self.outcome.color, cards=[list(c) for c in self.outcome.cards],
                      shoe=self.shoe.snapshot(), poker_category=self.outcome.poker_category,
                      poker_payout=self.outcome.poker_payout)
        self._round_id = record["id"]
        self.store.open_round(self.settlement, record)
        if self.current_bets:
            self.last_bets = dict(self.current_bets)
        self.phase = "awaiting_collection"
        return self.outcome, self.settlement


# 从所附 Baccarat 程式移植的独立切牌场景。
class BaccaratCutScene:
    """A small 2.5D scene; all visible faces share the same world projection.

    Cards stand along X, so the long faces show paper edges, not stretched
    card backs. Only the actual end faces receive the background.png texture.
    The two opaque separator cards never enter the playable 208-card deck.
    """

    WIDTH, HEIGHT = 900, 460
    LENGTH, DEPTH, CARD_H = 330.0, 140.0, 144.0
    ORIGIN_X, ORIGIN_Y = 360.0, 335.0
    PHASES = (('插入黄色切牌', .40), ('双手移开透明牌架', .70),
              ('双手扶稳前后两段', .80), ('后段移至前方', .75), ('错位调换前后段', 1.05),
              ('换手后合拢牌叠', 1.75), ('双手整理牌叠', .30),
              ('抽出黑色挡牌', 1.05), ('黑色挡牌移至牌尾', .60), ('放好黑色挡牌', .50),
              ('取出牌尾黄色切牌', 1.05), ('黄色切牌移至尾部位置', .50),
              ('插入尾部黄色切牌', .60), ('双手放回透明牌架', 1.10), ('整理完成', .25))
    SEPARATOR_GAP = 8.0
    CUT_MIN, CUT_MAX, CARD_COUNT = 33, 174, SHOE_SIZE
    TRANSFER_CLEARANCE = 110.0
    HAND_CLEARANCE = 76.0
    HOLDER_TRAVEL = 172.0

    def __init__(self, back):
        self.back = back
        self._background = None
        self._hand_images = None
        self._hand_sprite_cache = {}
        self._finger_image_cache = {}
        self._finger_parts = None

    @staticmethod
    def project(x, y, z=0):
        return (BaccaratCutScene.ORIGIN_X+x-.52*y,
                BaccaratCutScene.ORIGIN_Y-.32*y-z)

    @classmethod
    def pose(cls, split, phase, progress, marker_final=None):
        """Keep the dealer's hands independent of the player's yellow tab.

        B first clears A and the supporting hand by a full card depth. A then
        slides right while B moves left in a separate lane. Both packets rest
        on the table during the handover; the left hand releases A, goes above
        the cards, and grips B before pushing it back. No hand is left at the
        seam, and even extreme cuts stay inside the viewport.
        """
        t = cls.ease(progress)
        front = -cls.DEPTH-cls.TRANSFER_CLEARANCE
        rear, gap = cls.LENGTH-split, cls.SEPARATOR_GAP
        marker_final = cls.LENGTH*.85 if marker_final is None else marker_final
        pose = dict(a_x=0, a_y=0, a_z=0, b_x=split, b_y=0, b_z=0,
                    marker_x=split, marker_y=0, marker_raise=24,
                    black_x=cls.LENGTH+2, black_y=0, black_z=0,
                    holder_shift=1, left_grip=0, right_grip=0,
                    left_open=0, right_open=0)
        if phase == 0:
            pose.update(marker_raise=32-8*t, holder_shift=0)
        elif phase == 1:
            pose.update(holder_shift=t)
        elif phase == 2:
            # Regrip first; only then open a small gap between the packets.
            separate = cls.ease((progress-.72)/.28)
            pose.update(b_x=split+20*separate)
        elif phase == 3:
            pose.update(b_x=split+20, b_y=front*t)
        elif phase == 4:
            pose.update(a_x=(rear+gap)*t, b_x=(split+20)*(1-t), b_y=front)
        elif phase == 5:
            # Park both packets until both hands have reached their new ends.
            join = cls.ease((progress-.72)/.28)
            pose.update(a_x=rear+gap, b_x=0, b_y=front*(1-join))
        else:
            pose.update(a_x=rear+gap, b_x=0)

        # The two separators follow their own packets through the entire cut.
        pose.update(marker_x=pose['a_x']+split,
                    black_x=pose['b_x']+rear+2,
                    black_y=pose['b_y'], black_z=pose['b_z'])
        if phase == 7:
            pose.update(black_y=front*cls.ease((progress-.48)/.52))
        elif phase == 8:
            # Close the seam only once the whole black card is outside it.
            pose.update(a_x=rear+gap*(1-t), marker_x=cls.LENGTH+gap*(1-t),
                        black_x=rear+2+(split+4)*t, black_y=front)
        elif phase >= 9:
            pose.update(a_x=rear, marker_x=cls.LENGTH,
                        black_x=cls.LENGTH+6, black_y=0)
            if phase == 9:
                pose.update(black_y=front*(1-t))
            elif phase == 10:
                pose.update(marker_y=front*cls.ease((progress-.48)/.52))
            elif phase == 11:
                pose.update(marker_x=cls.LENGTH+(marker_final-cls.LENGTH)*t,
                            marker_y=front)
            elif phase == 12:
                pose.update(marker_x=marker_final, marker_y=front*(1-t))
            else:
                pose.update(marker_x=marker_final,
                            holder_shift=1-cls.ease((progress-.50)/.50) if phase == 13 else 0)

        def separator_grip(x, y, top):
            return (x, y, top-8)
        def travel(first, last, amount):
            # Open before leaving; arrive before closing. The travelling
            # part is one continuous arc, not three stop/start movements.
            return cls.clear_hand_path(first, last, (amount-.16)/.68)
        def opening(amount):
            return cls.ease(amount/.16)*(1-cls.ease((amount-.84)/.16))
        a, b = pose['a_x'], pose['b_x']
        left = cls.packet_contact(0, a, pose['a_y'], pose['a_z'])
        right = cls.packet_contact(1, b+rear, pose['b_y'], pose['b_z'])
        yellow_grip = separator_grip(pose['marker_x'], pose['marker_y'],
                                     cls.CARD_H+pose['marker_raise'])
        black_grip = separator_grip(pose['black_x'], pose['black_y'],
                                    pose['black_z']+cls.CARD_H+8)
        if phase == 0:
            left, right = cls.holder_contact(0, 0), cls.holder_contact(0, 1)
        elif phase == 1:
            left = cls.holder_contact(pose['holder_shift'], 0)
            right = cls.holder_contact(pose['holder_shift'], 1)
        elif phase == 2:
            amount = max(0, min(1, progress/.72))
            left = travel(cls.holder_contact(1, 0), left, amount)
            right = travel(cls.holder_contact(1, 1), right, amount)
            pose.update(left_open=opening(amount), right_open=opening(amount))
        elif phase == 5:
            amount = max(0, min(1, progress/.72))
            left = travel(cls.packet_contact(0, rear+gap),
                          cls.packet_contact(0, b, pose['b_y']), amount)
            right = travel(cls.packet_contact(1, rear, front),
                           cls.packet_contact(1, cls.LENGTH+gap), amount)
            pose.update(left_open=opening(amount), right_open=opening(amount))
        elif phase == 6:
            left = cls.packet_contact(0, b)
            right = cls.packet_contact(1, a+split)
        elif phase >= 7:
            left = cls.packet_contact(0, 0)
            if phase == 7:
                regrip = max(0, min(1, progress/.48))
                right = travel(cls.packet_contact(1, cls.LENGTH+gap), black_grip, regrip)
                pose['right_grip'] = cls.ease(regrip)
                pose['right_open'] = opening(regrip)
            elif phase in (8, 9):
                right, pose['right_grip'] = black_grip, 1
            elif phase == 10:
                regrip = max(0, min(1, progress/.48))
                right = travel(black_grip, yellow_grip, regrip)
                pose['right_grip'] = 1
                pose['right_open'] = opening(regrip)
            elif phase in (11, 12):
                right, pose['right_grip'] = yellow_grip, 1
            elif phase == 13:
                regrip = max(0, min(1, progress/.50))
                left = travel(left, cls.holder_contact(pose['holder_shift'], 0), regrip)
                right = travel(yellow_grip, cls.holder_contact(pose['holder_shift'], 1), regrip)
                pose['right_grip'] = 1-cls.ease(regrip)
                pose.update(left_open=opening(regrip), right_open=opening(regrip))
            else:
                left, right = cls.holder_contact(0, 0), cls.holder_contact(0, 1)
        pose.update(left_hand=left, right_hand=right)
        return pose

    @classmethod
    def holder_contact(cls, shift=0, side=0):
        """Opposed finger/thumb contacts on the two clear side panels."""
        x = -8 if side == 0 else cls.LENGTH+cls.SEPARATOR_GAP+10
        y = cls.DEPTH+6 if side == 0 else 0
        return (x, y+cls.HOLDER_TRAVEL*shift, cls.CARD_H+10)

    @classmethod
    def packet_contact(cls, side, x, y=0, z=0):
        # The supporting left hand stays on the far upper corner, away from
        # the foreground transfer lane. The right hand presses the outer end.
        return (x+(-3 if side == 0 else 3),
                y+(cls.DEPTH-4 if side == 0 else -4), z+cls.CARD_H+3)

    @classmethod
    def clear_hand_path(cls, first, last, progress):
        """A raised cubic arc with continuous direction and soft endpoints."""
        ceiling = max(first[2], last[2], cls.CARD_H)+cls.HAND_CLEARANCE
        # The parked holder is already behind the deck. Do not lift a hand
        # there out of the viewport; rise further while coming forward.
        def raised_height(point):
            visible_top = cls.ORIGIN_Y-.32*point[1]-76
            return max(point[2], min(ceiling, visible_top))
        start_top, end_top = raised_height(first), raised_height(last)
        t = max(0., min(1., progress))
        t = t*t*t*(10+t*(-15+6*t))
        u = 1-t
        c1, c2 = (first[0], first[1], start_top), (last[0], last[1], end_top)
        return tuple(u*u*u*a+3*u*u*t*b+3*u*t*t*c+t*t*t*d
                     for a, b, c, d in zip(first, c1, c2, last))

    @staticmethod
    def ease(value):
        value = max(0.0, min(1.0, value))
        return value*value*(3.0 - 2.0*value)

    @staticmethod
    def texture_quad(target, texture, corners):
        """Map an image onto a projected card without an extra dependency."""
        if texture is None:
            return
        x0 = math.floor(min(p[0] for p in corners))
        y0 = math.floor(min(p[1] for p in corners))
        x1 = math.ceil(max(p[0] for p in corners))
        y1 = math.ceil(max(p[1] for p in corners))
        if x1 <= x0 or y1 <= y0:
            return
        source = ((0, 0), (texture.width, 0),
                  (texture.width, texture.height), (0, texture.height))
        rows = []
        for (px, py), (u, v) in zip(corners, source):
            x, y = px-x0, py-y0
            rows.extend(([x, y, 1, 0, 0, 0, -u*x, -u*y, u],
                         [0, 0, 0, x, y, 1, -v*x, -v*y, v]))
        for column in range(8):
            pivot = max(range(column, 8), key=lambda r: abs(rows[r][column]))
            rows[column], rows[pivot] = rows[pivot], rows[column]
            divisor = rows[column][column]
            if abs(divisor) < 1e-9:
                return
            rows[column] = [v/divisor for v in rows[column]]
            for r in range(8):
                if r != column:
                    factor = rows[r][column]
                    rows[r] = [a-factor*b for a, b in zip(rows[r], rows[column])]
        warped = texture.convert('RGBA').transform(
            (x1-x0, y1-y0), getattr(Image, 'Transform', Image).PERSPECTIVE,
            tuple(row[-1] for row in rows),
            resample=getattr(Image, 'Resampling', Image).BICUBIC)
        mask = Image.new('L', warped.size)
        ImageDraw.Draw(mask).polygon([(x-x0, y-y0) for x, y in corners], fill=255)
        warped.putalpha(ImageChops.multiply(warped.getchannel('A'), mask))
        target.paste(warped, (x0, y0), warped)

    @staticmethod
    def _bezier(start, segments, steps=10):
        points, current = [start], start
        for c1, c2, end in segments:
            for i in range(1, steps+1):
                t, u = i/steps, 1-i/steps
                points.append(tuple(u*u*u*current[k]+3*u*u*t*c1[k]
                                    +3*u*t*t*c2[k]+t*t*t*end[k] for k in (0, 1)))
            current = end
        return points

    HAND_SIZE = (224, 160)
    HAND_ANCHOR = (174, 78)
    _HAND_PNGS = (
        (
            'iVBORw0KGgoAAAANSUhEUgAAAOAAAACgCAYAAAAVdWCNAAA8T0lEQVR42u29eZRl+VHf+Y2I3+/e+97LzNq6q9Xq1opoSVUSQrSE'
            'LbxUixkbRiNsw0zWIGRgZmQkG5CNjYSxwc5KNmM8moPHPmDhsfECNq4cD8cgMyzG6sJGYCTZCNQlqRFaWlur9srM99699/eLiPnj'
            'd19WtRCgFVU193NOnu7Ofpn5lhs34hfxjQhgZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRk'
            'ZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZOQPGhrfgk/pvfLx7Rj5TMDjW/AJMxrdyMjIyMjIeGQYGRkZbzbjGXBk'
            'ZDS+kZGRkZGRkZGRMfQb3/CR24KtrS1+AOAHzpxRInIA8LNn5cGHHqIHAKPtbbvFrtexHjty++MOOru5KY8xxt8lKffGra3gvsU+'
            '3rBHDzjyGTC+s5tCp3cUAH7xu/7iMzema19Th/gnm/W1O6u66ZnpPe2y++Ue9nPPecV3nH+s4W7xgw+CH7h40vHQQ44zZxwg0I0r'
            'afRQowGOfFzD29pinDnjROQ//tdeecc9x6bfEWHfcMfabIZsqGZTTGZT1JMGEMFe23Uu9N9y0p9Tw88uHrXf/MLXvnb++3tXL9fV'
            'mTOEkyfpwYceIgB44OQNo6VisT4a4MgfinPemZPnaeX1/uP3fcvLg9l316Cn9SnpdDpN0+mEq6bmqqngRG5tZwbEyaTmatJgv08A'
            '83sd9OvZ9Fch4Te7lB9JWS8+stzfb4+c704Pv/+TuSHsnDxPmwAefOjEwbX4IGDbt9bZczTAkU/lnOeEnR2m06cVAH7h+/7yCycx'
            'flcN+vJrV6+h6/tufToNa2tTmkwbzA4fAksEiGDzuSvgCAFS1WaqEqNIVQVIjOhUsVimDOHrAF039wUzelVbZrUsMAPJwkDXVNNH'
            'GeH9HPi9jPzInMOHn4+7r6ye18fj7NlN+WQNejTAkVvI452k1QX+hq2/9PRDG7PXRqJXiHq8ePlqr0w8W5vwJArqEFHFiGYyQagi'
            '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'
            'K7wBq116N57/OSvrvz7uRUibm5u8euzx48f9xImdYV3YY0J62lpdA1u/85ecPw8CNrH6PTf93d/xvm2eOFGFQ/z0nOmLiO1FMDuR'
            'U3paHatjsRIilpzNO3Ms3a1VQwtQR+aZma2KoXezfc26724dCe9D5Dq5d6GSjyLyW//5L7z512/ljObj2QAJgK+trd2Zkj+X2T4f'
            'wH1wPNfdn01E98CdVskZM9PSUEsX9ufzkwCu/x4Hcdra2qLzw4H+woULdPz4cb/J69zqHzZ9DpINVLK55YbwMe/XAa986UunVy99'
            '4Eg2ozBpco++vYZrLfD+fO4cPulwfphq5ngc9QnS7f4CDuHQ4X7S3wfDFzHjBea430zvi7GaVrH6zivXrnzvKoT9FN+bP/RjEz4Z'
            'o3zw1GM24ton8h47gDMAYQs4f37z4EZ48wN/N8878gd/w5DBoAJ+l+Uy69X6M9en619/5MjTDw0/Q+Nb9zkzSt4qLYyEx36NzuVx'
            'cmHSYIirUFHH635k5HNvkGH0fCMjIyMjIyMjIyMjIyMjIyMjI7cmY+JuZGRkZGRkZGRkZGRkZDxwjnzWPvdRcP45gse3YGR0EiMj'
            'IyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMj'
            'IyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMj'
            'IyMjIyMjIyMjIyMjIyMjIyMjIyMjI59p/n/AfGE2upyWEQAAAABJRU5ErkJggg=='
        ),
        (
            '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'
            'U8QQABiOHj6c3v/AX2QK2iLuzN33faFeyjODdG0pGuyplAN+WkxDbG5uMra20P3Tv/e6Sb30lV0nkTyrDaM9IoauTxSSwo1r9LGn'
            'NL+EmglVNYGrK/K1zyEpAAkRta/Qz6fYnc6Nq9pSSsajEQnB85DEkGOEpBC1XYM9aGQPmNn7YPgLU7qgqleIbVfyJi5jImOz5Bxr'
            'SBQcWVPrfPrqP7x/bxEKHtLZUagcI/JH1eRWielZVe1vMeA2U10G8QoT+eF0daa6J2YXiOwvAHp/MrwP4He/4c1//JfXH8KNjQ0H'
            'AE+EPP/myZN+6+zZ9M3f8PX/fDJZelnX9Rj2IyEtuKGmnSbZMdMPA/ZBVfugGT6QRB5xzA++69y5L7x8+fKPpiQxpsT7xJnFGmpa'
            'HOBh6y6QABvB9J4uhH+G3A+UYoBPUCuCAHzz3332ymT94M9ptK8lIwfn95dSxiSIfciNagCqOdfzlYer8mKTapg+YFXAFDEKptMZ'
            'qqVJbhQTIwG9Ej6gsD+pnHuzJXtnVLwPt7zj4ZwvfXILTxvHj9cX5nPG7bcDQPpY4eN1RqdPsEcgAPaiF20cjS3eKGK1iJw30DkA'
            '71WiD3ovj6hWl7a3t3c/ys+oHfP7JuPJLSIqaso07JbPncHM584L1swMiAAmMP3fuxDuxlNkHOnTaR5w/wB/45d+3t9C1OelIDcY'
            '0Qgi6ya6QsQj590KMa+EmGpVZWPygI0cY0zEYyZMPNPIVHwMYn0Ml31VPQDm86b8Zu/t7WlX33/dxtzrPDH43ntP7pOBjx07ZsA2'
            'jh//CId/a/+PR1URh59D589v0IULF2jxcz6GEdHmJmjxe48dO2YfYefhpwzPe97zqvvuu0/wMV7P5uYm33vvvfuv/9y5c+78+fNh'
            'XNffV1XVT6SkQU0dUZ4tzuktOQL8fii6aMbDfrbruu8oHvBT9H42N0FbWx//4Tt5Eh64zR/AgXGNepzazntmO3jklqu/+PrXNx/J'
            'u1y4cIGuO/D2BHkZ+kQLVp/KS/H65wUAwy7Fj/bMFu9xfWV5+ZyqHRMRYmaXQ1Fb6MU8RER/CsK7ALxPlf+squhds9ns4sfTyioG'
            '+LjnhI/2RNe8EXD8+LZhCzg9jJP9dQ7xJsD7G3OzKpvhKZLkP4nO2Mf7vDyAdOjAoR8MMfxIjKFhdu9jwn2qeBsYb6/b+n272N0p'
            'j/jT46JYJBhkeU01D6psVB7/p+wzp4MH71hfXVr9xtV69dkf5b/jwVj9EHZSOdgFBZ88uOvCyye6uFRQ8BnpCT1KNFJQUFBQUFBQ'
            'UFBQUFBQ8HEn1AUFBQUFBQUFBQUFBQUFBQWfcShFkSfX8y+0qs8w8GfYAS8oKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgo'
            'KCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgo'
            'KCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoeALw/wHE'
            'AmFCrnTS5gAAAABJRU5ErkJggg=='
        ),
        (
            'iVBORw0KGgoAAAANSUhEUgAAAOAAAACgCAYAAAAVdWCNAAA6bUlEQVR42u29ebxlWVUm+K219z7nDm+KeBkROSeQgkgiIghaKmai'
            'ZVcXDlXd7QuHqm7EAZRCaaUUu7T75bPpLlu0bNuqtrDp1p+2WsZTqy0pRbAlo0UcSgTRDEZJkpwjMiJexHt3OGfvtVb/sfe9ESSg'
            'kAw57e/3Y4jIm2+496y91vrWt74NVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRU'
            'VFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFR8YqDyn8fb70OP'
            '0Pf+eO8rPYZ+j0f0w6u/b4bVs+kz8j7bw/xsnhCfB9dnpeJREHwf67VPiGzonsAPiT3MD/gJVyY9zAC0T2Mg1wCsWD4Q9Bgvj8jM'
            'CADfdvIkdj5zh9unemDVQ67i4wbgYw7b29tsJ0581IFrJ0648vf0GXrPPpX3rQZhxWO/BD1xYstdHohvf/3/cvU7fvY11/zOT39P'
            '+1HBmLPjo7WnfFw3zI/1fu6x1uN8xmFmhFtvJdrZ0f/3ta+6YcOH72odf007Gl0XRiOQ6YMg/jPy7peuP/7K31v8TnbihMPW7Ua0'
            'o0/Az7cGYMWnJ+sdP74rAPAHO6/43mHw24dXx4fJObgQzHmP4JkGgyGSKhLsz0H8ujkGuzcef9mFxdd5y1u2/Zkzp2xr64QSUR3V'
            '1ACs+FuzHkC3bd/sXrhzMr3hx19+ZTu1n2qJv8kHbysrK/1gOGBiR5oS2JGx9wqAB00IoW0wS+kuNf41gv7qk77p+//iozLq7i7f'
            'duR2OnPmJtva2qpBWQOwYpn1trbc8d2c9W57zSv/YZL4byWm69n7bnVlxbWDluAdaZ8w8s4GK2M0q2N4YqiY9bEzg4V2ZYyDeacG'
            'vAPAb2tKvz+b0e1f+JLv2/tYZe5tt97qztx0yraO7ypVQUMNwCdc1jPQbbduuxfu7KRffNWrxlcfjj+qkr6vF6N2MOjacRsAAjqx'
            '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'
            'qG1M5Z/8xzf97olnPWvo7r//jemywPpkTlB6mKcubW1t8enTp+mWkyf107BYupyj1aCrJMzf3gNmx10sbonFZSMDs8wWXmJJFxmx'
            'jC1MEJqAQ4cOISXBbD5dLqtiwXyWUUFWz6D4aGrxDzVj5pAO5tMA+6OTJ0+mW27Z1p/5mTc+3AB4uA/6ctB8chmQ4EXmvJw9XDAm'
            'APBQZvJjzdEqagb8WzPgYDB4PYG+HYYOhJBD0QzL9duH/qR0OSuKKzYP21d95VfS+vqhJVHDjpdETN74cSXbLR3X4Jy3EBphR02K'
            '3Vt/7Cde+4LHsrFrRc2AD5OEMb/IalRMc5f8KGhJYVnZ51vY5uU7ENQ21tdAUJtOJ+C85a75RiG38B6kMjynxfiBAKgKEcE8HGaz'
            '6e8AwK3b2w47OzVzVDxxApDyfdHLLfClXwRwycNz4Yq93ILP1Z7zjI21VcymE8euR9O2ed7GDFZeKl/yug6Ld6zErDAjdowYe8dM'
            'c1L99WXUV1Q8kQIQgOatHRMiJpDx4oq+Bf1yGS2zyJowGIIPuP2976P9yfSbnvr0G98XJ+kaH/hJMH4KEa5n5usIOGbAYWZeNQvO'
            'l7sjRBnDAaObd7/1cz//8+9/PN03XlED8BPPgEaemZwRRpdukDU1s1Ru78pXPyw1KLpgOwSEcHF//83vuv32X3vX7bcDwDse+vW/'
            '+qu/eryx0W661F6VklxHwOcY0ucwhRtj312h2v9PAOjUqVNUH4OKJxIJQwBstWmeKsxfAqJnm+ELiPA0AFcD5ABcdrUzJQBqZkTE'
            'zAQlohAl/cP5fP57N910U7jpppvkcinVJ0DBP6bdlCtqAH4msDYajZ7siW5KIs83s+ca6OlMdMVy/wyUmIiJ6T8dTCZfVv7y45WP'
            'tL29vcxwi6XOEydOKOVWswZhxRM6ABmXrsjWjxVI4/H4KBI+35x9GcxuMbPneu/XBsPhN5w5c+Y3UEYaDzcL14+/ouIjg4JLX+o/'
            '1uGw1rY3rq6ufh0eYTOpiorHYwn6twXlwtalZq2Kike4bHX1baiHekVFRQ3AioqKioqKioqKioqKioqKioqKioqKioqKioqKioqK'
            'ioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqK'
            'ioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKiopHN/5/3YwUuU28'
            'KsIAAAAASUVORK5CYII='
        ),
        (
            'iVBORw0KGgoAAAANSUhEUgAAAOAAAACgCAYAAAAVdWCNAAA61UlEQVR42u29e7SlWVUf+ptzre/79j6POqcep/oN3XSLUA3yaMHH'
            'xdENgYRcRePjlDcaNRivxBuNMUQTb4inT4IOwVcgaoSLIZiRmFEHx71XEa5PugQV0FZprQoBoaG76aaqu6rOa+/vsdac8/6x1t5V'
            '3bEDdGM3dK/fGDW669TZe5+9zze/Oedv/uZvAQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUF'
            'BQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFnx50'
            'yZ/P9nEPfY6/6t8+39/HF8Lv5kl3QT5Z36s9gscZCh6La+9J8znzkyjrPdJfsD1Jb1gFjwH8k+i92qN8bAm+zyyj2aP4fEuF8STJ'
            'gI/0cfTXcFegjY0NNrMnQg9EpVIo+Fz0ufTXTAyQnTjh7MQJ9z8E5IkTbmNjg0sAFjxZg++vrwY2o4cG3Tvf8H3Nn/771151+1te'
            'd+WlgXfixLp7klQa5QJ9gr8/e/wDb4OxdSPR8eMy+7nuOvGGv2VRvg2mLzTiI2E6RT+d3t2L/vp2DL/wN37wpz5hGxuMW281IrIv'
            'oGvJnmy/3xKAn2cwM9raOs5ra8foxS/ejLOvf/TEm1ZG6NZh+ioP+lLPjK5rEaKaxAgJgUwE5/cm59sQN1+y8bNvnGXD48e3pHyy'
            'JQMW/JXBtsVra6folvtvNKyv60Mz1sf/608/38B/l0m/eez9NaEf0A0hAFCNkVWM2HuYinVtp/v7+3UMkXrT/9ov0A98zQ/9/Kfe'
            'vXGzv2XzpFBhCksAPqkDDqCtE+u8duoY3XLrrfJXlYd/+tafWR2P7Ub2/qUAXkHA85ZGDff7ExAo1FVD7IiiKYa9Cbr9CaZRiGsP'
            'RLG+621vf180xsZV/i7vqn94y2ve8C4AOLG+7o5vlWxYAvBJF3QneG3t1INKSgD4k1/80TVX+2fUjp9X1c1zFHgGmK5zzl2x2NQI'
            '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'
        ),
    )

    # Shoulder/elbow motion is solved in 3D, then projected. A planar IK
    # elbow has only two possible positions and produced the conspicuous
    # right-angle bends. The swivel plane here stays mostly in depth.
    ARM_LENGTHS = (340.0, 240.0)
    ARM_SHOULDERS = ((-60.0, 80.0, 190.0), (960.0, 80.0, 190.0))
    OPEN_HAND_CONTACT = (164, 67)
    PINCH_HAND_CONTACT = (175, 79)

    @classmethod
    def hand_rig(cls, side, contact, grip=0, opening=0):
        anchor = cls.project(*contact)
        grip, opening = (max(0., min(1., value)) for value in (grip, opening))
        upper, fore = cls.ARM_LENGTHS
        sx, sy, sz = cls.ARM_SHOULDERS[0]
        local_anchor = (anchor[0] if side == 0 else cls.WIDTH-anchor[0], anchor[1])
        reach, wrist_y = 99+11*grip, 6-12*grip
        wrist_depth = .28*(contact[1]-cls.DEPTH)

        def solve(wrist):
            delta = (wrist[0]-sx, wrist[1]-sy, wrist[2]-sz)
            distance = math.sqrt(sum(v*v for v in delta))
            direction = tuple(v/max(.001, distance) for v in delta)
            safe = max(abs(upper-fore)+.001, min(upper+fore-.001, distance))
            along = (upper*upper-fore*fore+safe*safe)/(2*safe)
            radius = math.sqrt(max(0., upper*upper-along*along))
            screen_length = max(.001, math.hypot(delta[0], delta[1]))
            normal = (-delta[1]/screen_length, delta[0]/screen_length, 0.)
            depth_axis = (direction[1]*normal[2]-direction[2]*normal[1],
                          direction[2]*normal[0]-direction[0]*normal[2],
                          direction[0]*normal[1]-direction[1]*normal[0])
            # Ten percent of the elbow swivel is visible in the image; the
            # rest bends away from the viewer. No branch switch or elbow pop.
            bend = tuple(.10*a-math.sqrt(.99)*b for a, b in zip(normal, depth_axis))
            return tuple(a+b*along+c*radius for a, b, c in
                         zip((sx, sy, sz), direction, bend))

        angle = 0.
        for _ in range(10):
            co, si = math.cos(angle), math.sin(angle)
            wrist = (local_anchor[0]-reach*co-wrist_y*si,
                     local_anchor[1]-reach*si+wrist_y*co, wrist_depth)
            elbow = solve(wrist)
            fore_angle = math.atan2(wrist[1]-elbow[1], wrist[0]-elbow[0])
            # Independent wrist flexion; use a soft limit instead of suddenly
            # hitting the previous +/-31 degree clamp.
            desired = .82*fore_angle-.055*opening
            angle = .45*math.tanh(desired/.45)
        co, si = math.cos(angle), math.sin(angle)
        wrist = (local_anchor[0]-reach*co-wrist_y*si,
                 local_anchor[1]-reach*si+wrist_y*co, wrist_depth)
        elbow = solve(wrist)
        def mirror(point):
            return (point[0] if side == 0 else cls.WIDTH-point[0], point[1], point[2])
        joints = tuple(mirror(p) for p in ((sx, sy, sz), elbow, wrist))
        return dict(anchor=anchor, shoulder=joints[0][:2], elbow=joints[1][:2],
                    wrist=joints[2][:2], joints_3d=joints,
                    angle=angle if side == 0 else -angle, side=side,
                    grip=grip, opening=opening)

    @classmethod
    def arm_polygons(cls, rig):
        """One tailored sleeve outline with a rounded elbow and fixed widths."""
        shoulder, elbow, wrist = (rig[k] for k in ('shoulder', 'elbow', 'wrist'))
        def normal(start, end):
            dx, dy = end[0]-start[0], end[1]-start[1]
            length = max(.001, math.hypot(dx, dy))
            return (-dy/length, dx/length)
        n1, n2 = normal(shoulder, elbow), normal(elbow, wrist)
        n = (n1[0]+n2[0], n1[1]+n2[1])
        norm = max(.001, math.hypot(*n))
        n = (n[0]/norm, n[1]/norm)
        def offset(point, axis, width):
            return (point[0]+axis[0]*width, point[1]+axis[1]*width)
        def mix(a, b, t):
            return tuple(x+(y-x)*t for x, y in zip(a, b))
        tangent = (wrist[0]-shoulder[0], wrist[1]-shoulder[1])
        tangent_length = max(.001, math.hypot(*tangent))
        tangent = tuple(v/tangent_length for v in tangent)
        rounding = min(14., math.dist(shoulder, elbow)*.18, math.dist(elbow, wrist)*.18)
        outline = []
        for sign in (1, -1):
            first = offset(shoulder, n1, sign*29)
            bend = offset(elbow, n, sign*25)
            last = offset(wrist, n2, sign*20)
            points = cls._bezier(first, [
                (mix(first, bend, .55), offset(bend, tangent, -rounding), bend),
                (offset(bend, tangent, rounding), mix(bend, last, .60), last)], steps=8)
            outline.extend(points if sign == 1 else reversed(points))
        return (outline,)

    @staticmethod
    def sleeve_details(rig):
        """A quiet seam and short elbow folds, not a long centre-line wire."""
        ex, ey = rig['elbow']
        wx, wy = rig['wrist']
        dx, dy = wx-ex, wy-ey
        length = max(.001, math.hypot(dx, dy))
        nx, ny = -dy/length, dx/length
        seam = [(ex+nx*13, ey+ny*13),
                (wx+nx*13-dx*.06, wy+ny*13-dy*.06)]
        folds = [[(ex+dx*t-nx*10, ey+dy*t-ny*10),
                  (ex+dx*(t+.04)+nx*6, ey+dy*(t+.04)+ny*6)] for t in (.04, .08)]
        return [seam]+folds

    @classmethod
    def holder_rails(cls, shift):
        p = cls.project
        y, end = cls.HOLDER_TRAVEL*shift, cls.LENGTH+cls.SEPARATOR_GAP+10
        near, far, top = y-4, y+cls.DEPTH+10, cls.CARD_H+10
        # An actual U-shaped case: both end panels have a rim to clamp.
        return ([p(-8, far), p(end, far), p(end, far, top), p(-8, far, top)],
                [p(-8, near), p(-8, far), p(-8, far, top), p(-8, near, top)],
                [p(end, near), p(end, far), p(end, far, top), p(end, near, top)])

    @classmethod
    def finger_point(cls, x, y, grip, opening):
        """Local joint motion shared by the raster and Canvas hand paths."""
        pinch = grip*(1-opening)
        upper = y < 74
        pivot = (134., 54.) if upper else (132., 81.)
        angle = (.28*pinch-.16*opening) if upper else (-.12*pinch+.20*opening)
        weight = cls.ease((x-128)/16)
        xx, yy = x-pivot[0], y-pivot[1]
        co, si = math.cos(angle), math.sin(angle)
        return (x+(xx*co-yy*si-xx)*weight,
                y+(xx*si+yy*co-yy)*weight)

    def _finger_image(self, grip, opening):
        """Move the index and thumb as separate pieces of the same hand.

        Overlapping joint roots stay under the palm. Rigid finger rotations
        preserve rounded fingertips and skin detail; no photo cross-fade or
        inverse warp can leave a floating fingertip or a pointed skin tear.
        """
        key = (round(grip*24), round(opening*20))
        if key not in self._finger_image_cache:
            if self._hand_images is None:
                self._hand_images = self._make_hand_images()
            source = self._hand_images[0]
            grip, opening = key[0]/24, key[1]/20
            if not key[0] and not key[1]:
                posed = source
            else:
                if self._finger_parts is None:
                    parts = []
                    for box in ((0, 0, 140, 160), (128, 0, 224, 74), (128, 74, 224, 160)):
                        mask = Image.new('L', source.size)
                        ImageDraw.Draw(mask).rectangle(box, fill=255)
                        part = source.copy()
                        part.putalpha(ImageChops.multiply(source.getchannel('A'), mask))
                        parts.append(part)
                    self._finger_parts = tuple(parts)
                palm, index, thumb = self._finger_parts
                pinch = grip*(1-opening)
                resample = getattr(Image, 'Resampling', Image)
                index = index.rotate(-math.degrees(.28*pinch-.16*opening),
                                     resample=resample.BICUBIC, center=(134, 54))
                thumb = thumb.rotate(-math.degrees(-.12*pinch+.20*opening),
                                     resample=resample.BICUBIC, center=(132, 81))
                posed = Image.new('RGBA', source.size)
                posed.alpha_composite(index)
                posed.alpha_composite(thumb)
                posed.alpha_composite(palm)
            if len(self._finger_image_cache) >= 96:
                self._finger_image_cache.pop(next(iter(self._finger_image_cache)))
            self._finger_image_cache[key] = posed
        return self._finger_image_cache[key]

    def _hand_sprite(self, rig, scale):
        """Articulated fingers, a rigid palm, and an independently flexing wrist."""
        angle = round(math.degrees(rig['angle'])*2)/2
        amount, opened = round(rig['grip']*24), round(rig['opening']*20)
        key = (rig['side'], angle, amount, opened, scale)
        if key not in self._hand_sprite_cache:
            resample = getattr(Image, 'Resampling', Image)
            source = self._finger_image(amount/24, opened/20)
            cx = self.OPEN_HAND_CONTACT[0]+(self.PINCH_HAND_CONTACT[0]-self.OPEN_HAND_CONTACT[0])*amount/24
            cy = self.OPEN_HAND_CONTACT[1]+(self.PINCH_HAND_CONTACT[1]-self.OPEN_HAND_CONTACT[1])*amount/24
            if rig['side']:
                source = source.transpose(getattr(Image, 'Transpose', Image).FLIP_LEFT_RIGHT)
                cx = source.width-1-cx
            layer = Image.new('RGBA', (360, 360))
            layer.alpha_composite(source, (round(180-cx), round(180-cy)))
            sprite = layer.rotate(-angle, resample=resample.BICUBIC)
            bounds = sprite.getbbox()
            sprite = sprite.crop(bounds)
            sprite = sprite.resize((round(sprite.width*scale), round(sprite.height*scale)),
                                   resample.LANCZOS)
            offset = ((bounds[0]-180)*scale, (bounds[1]-180)*scale)
            if len(self._hand_sprite_cache) >= 160:
                self._hand_sprite_cache.pop(next(iter(self._hand_sprite_cache)))
            self._hand_sprite_cache[key] = (sprite, offset)
        return self._hand_sprite_cache[key]

    @classmethod
    def fallback_hand(cls, rig):
        """Fixed local hand silhouette for installations without Pillow."""
        shape = cls._bezier((-111, -16), [
            ((-88, -16), (-72, -34), (-49, -33)),
            ((-24, -34), (12, -24), (17, -6)),
            ((18, -1), (10, 1), (7, -5)),
            ((-1, -18), (-29, -17), (-38, -13)),
            ((-44, -9), (-44, 5), (-35, 9)),
            ((-21, 13), (-2, 7), (1, 12)),
            ((8, 26), (-33, 27), (-48, 21)),
            ((-70, 14), (-93, 22), (-111, 20))])
        co, si = math.cos(rig['angle']), math.sin(rig['angle'])
        direction = 1 if rig['side'] == 0 else -1
        points = []
        for x, y in shape:
            x, y = cls.finger_point(x+164, y+67, rig['grip'], rig['opening'])
            x -= 164+11*rig['grip']
            y -= 67+12*rig['grip']
            points.append((rig['anchor'][0]+direction*x*co-y*si,
                           rig['anchor'][1]+direction*x*si+y*co))
        return points

    def _make_hand_images(self):
        """Load the two natural grip poses embedded in this standalone file."""
        import base64
        from io import BytesIO
        return tuple(Image.open(BytesIO(base64.b64decode(data))).convert('RGBA')
                     for data in self._HAND_PNGS)

    @classmethod
    def separator_quads(cls, x, y, z, packets):
        """Clip a separator against every packet along the actual viewing ray.

        Projecting a box onto this card's plane accounts for packets in front
        of the card as well as the packet containing it. Painting order alone
        cannot hide the inserted area of an upright card reliably.
        """
        def cross(a, b, p):
            return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
        def hull(points):
            points = sorted(set(points))
            lower, upper = [], []
            for point in points:
                while len(lower) > 1 and cross(lower[-2], lower[-1], point) <= 1e-8:
                    lower.pop()
                lower.append(point)
            for point in reversed(points):
                while len(upper) > 1 and cross(upper[-2], upper[-1], point) <= 1e-8:
                    upper.pop()
                upper.append(point)
            return lower[:-1]+upper[:-1]
        def half_plane(points, a, b, inside):
            output = []
            if not points:
                return output
            previous = points[-1]
            prev_side = cross(a, b, previous)
            prev_keep = prev_side >= -1e-8 if inside else prev_side <= 1e-8
            for point in points:
                side = cross(a, b, point)
                keep = side >= -1e-8 if inside else side <= 1e-8
                if keep != prev_keep:
                    ratio = prev_side/(prev_side-side)
                    output.append(tuple(v+(w-v)*ratio for v, w in zip(previous, point)))
                if keep:
                    output.append(point)
                previous, prev_side, prev_keep = point, side, keep
            return output
        def area(points):
            return abs(sum(a[0]*b[1]-b[0]*a[1]
                           for a, b in zip(points, points[1:]+points[:1])))*.5

        visible = [[(y, z), (y+cls.DEPTH, z),
                    (y+cls.DEPTH, z+cls.CARD_H+8), (y, z+cls.CARD_H+8)]]
        for px, py, length, pz in packets:
            if px > x+1e-8:
                continue
            projected = []
            for xx in (px, min(px+length, x)):
                distance = (x-xx)/.52
                for yy in (py, py+cls.DEPTH):
                    for zz in (pz, pz+cls.CARD_H):
                        projected.append((yy+distance, zz-.32*distance))
            occluder = hull(projected)
            remaining = []
            for polygon in visible:
                inner = polygon
                for start, end in zip(occluder, occluder[1:]+occluder[:1]):
                    outer = half_plane(inner, start, end, False)
                    if len(outer) >= 3 and area(outer) > 1e-6:
                        remaining.append(outer)
                    inner = half_plane(inner, start, end, True)
                    if len(inner) < 3 or area(inner) <= 1e-6:
                        break
            visible = remaining
        return [[cls.project(x, yy, zz) for yy, zz in polygon] for polygon in visible]

    @classmethod
    def cut_limits(cls):
        return cls.LENGTH*cls.CUT_MIN/cls.CARD_COUNT, cls.LENGTH*cls.CUT_MAX/cls.CARD_COUNT

    @staticmethod
    def contains_point(polygon, x, y):
        signs = [(b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0])
                 for a, b in zip(polygon, polygon[1:]+polygon[:1])]
        return bool(signs) and (min(signs) >= -1e-6 or max(signs) <= 1e-6)

    @classmethod
    def top_cut_position(cls, screen_x, screen_y):
        """Invert the same projection used to draw the closed deck's top."""
        depth = (cls.ORIGIN_Y-cls.CARD_H-screen_y)/.32
        world_x = screen_x-cls.ORIGIN_X+.52*depth
        low, high = cls.cut_limits()
        if not -1e-7 <= depth <= cls.DEPTH+1e-7 or not low-1e-7 <= world_x <= high+1e-7:
            return None
        return max(cls.CUT_MIN, min(cls.CUT_MAX, round(world_x/cls.LENGTH*cls.CARD_COUNT)))

    def render(self, split, a_x=0, a_z=0, b_x=None, b_z=0,
               marker_x=None, marker_y=0, marker_raise=32, hands=True,
               a_y=0, b_y=0, black_x=None, black_y=0, black_z=0,
               holder_shift=0, left_hand=None, right_hand=None,
               left_grip=0, right_grip=0, left_open=0, right_open=0):
        if Image is None or ImageDraw is None:
            return None
        scale = 1.25
        size = (int(self.WIDTH*scale), int(self.HEIGHT*scale))
        resample = getattr(Image, 'Resampling', Image)
        if self._background is None:
            self._background = Image.new('RGBA', size, '#0b4038')
            glow = Image.new('RGBA', (300, 154))
            gd = ImageDraw.Draw(glow)
            gd.ellipse((25, 35, 280, 147), fill=(29, 102, 75, 72))
            glow = glow.filter(ImageFilter.GaussianBlur(18)).resize(size, resample.BILINEAR)
            self._background.alpha_composite(glow)
        image = self._background.copy()
        draw = ImageDraw.Draw(image)
        b_x = split if b_x is None else b_x
        marker_x = split if marker_x is None else marker_x
        black_x = self.LENGTH+2 if black_x is None else black_x
        parts = ((a_x, a_y, split, a_z), (b_x, b_y, self.LENGTH-split, b_z))
        p = self.project
        xy = lambda point: tuple(v*scale for v in point)

        def poly(points, fill, outline=None, width=1):
            points = [xy(q) for q in points]
            draw.polygon(points, fill=fill)
            if outline:
                draw.line(points+[points[0]], fill=outline, width=max(1, round(width*scale)))

        def line(points, fill, width=1):
            draw.line([xy(q) for q in points], fill=fill, width=max(1, round(width*scale)))

        # Contact shadows follow the footprint, not a huge oval under a flying box.
        shadow = Image.new('RGBA', (self.WIDTH//2, self.HEIGHT//2))
        sd = ImageDraw.Draw(shadow)
        for x, y, length, z in ((a_x, a_y, split, a_z),
                                (b_x, b_y, self.LENGTH-split, b_z)):
            footprint = [p(x, y), p(x+length, y), p(x+length, y+self.DEPTH), p(x, y+self.DEPTH)]
            sd.polygon([((px+3)/2, (py+6)/2) for px, py in footprint], fill=(0, 20, 16, 95))
        image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(3)).resize(size, resample.BILINEAR))

        # The player's yellow tab never drives either dealer hand.
        left_world = left_hand or self.holder_contact(holder_shift, 0)
        right_world = right_hand or self.holder_contact(holder_shift, 1)
        rigs = [self.hand_rig(side, world, grip, opening) for side, world, grip, opening in
                ((0, left_world, left_grip, left_open), (1, right_world, right_grip, right_open))]

        # Clear, open-front holder: the far rail and rear plate slide away
        # sideways before cutting, then return around the squared B+A stack.
        rails = self.holder_rails(holder_shift)
        glass = Image.new('RGBA', size)
        gd = ImageDraw.Draw(glass)
        for rail in rails:
            gd.polygon([xy(q) for q in rail], fill=(190, 222, 222, 25))
            gd.line([xy(q) for q in rail+[rail[0]]], fill=(183, 215, 216, 155), width=2)
        image.alpha_composite(glass)

        def packet(x, y, length, z):
            d, h = self.DEPTH, self.CARD_H
            front = [p(x, y, z), p(x+length, y, z), p(x+length, y, z+h), p(x, y, z+h)]
            top = [p(x, y, z+h), p(x+length, y, z+h),
                   p(x+length, y+d, z+h), p(x, y+d, z+h)]
            poly(front, '#dfddcf', '#a9ab9b', .7)
            poly(top, '#f2f0e4', '#c1c4b3', .7)
            # Subtle grouped paper edges avoid the thick pinstripe/moire pattern.
            count = max(5, round(length/3.0))
            for i in range(1, count):
                edge_x = x+length*i/count
                line([p(edge_x, y, z+1), p(edge_x, y, z+h-1)],
                     '#c8c9bb' if i % 4 else '#bfc1b2', .6)
                line([p(edge_x, y, z+h), p(edge_x, y+d, z+h)], '#dedfd0', .6)
            face = [p(x, y+d, z+h), p(x, y, z+h), p(x, y, z), p(x, y+d, z)]
            poly(face, '#fbf7eb', '#d4d3c2', .7)
            inner = [p(x-.1, y+d-3, z+h-3), p(x-.1, y+3, z+h-3),
                     p(x-.1, y+3, z+3), p(x-.1, y+d-3, z+3)]
            self.texture_quad(image, self.back, [xy(q) for q in inner])
            line([p(x, y, z), p(x+length, y, z)], '#959f8d', 1)
            line([p(x, y+d, z+h), p(x+length, y+d, z+h)], '#f9f8ef', 1)

        def separator(x, y, z, yellow=False):
            for corners in self.separator_quads(x, y, z, parts):
                poly(corners, '#eccd42' if yellow else '#1e2124')

        # Occlusion is already resolved geometrically for the separators.
        objects = [(a_y+.32*(a_x+split/2)-a_z*.5,
                    lambda: packet(a_x, a_y, split, a_z)),
                   (b_y+.32*(b_x+(self.LENGTH-split)/2)-b_z*.5,
                    lambda: packet(b_x, b_y, self.LENGTH-split, b_z)),
                   (-1000+.001*(black_y+.32*black_x-black_z*.5),
                    lambda: separator(black_x, black_y, black_z)),
                   (-1000+.001*(marker_y+.32*marker_x-(marker_raise-8)*.5),
                    lambda: separator(marker_x, marker_y, marker_raise-8, True))]
        if hands:
            def paint_hand(index):
                rig = rigs[index]
                # Keep each wrist, cuff and forearm in the same layer. A
                # foreground hand must never be detached from its sleeve by
                # drawing the intervening packet between those two pieces.
                for points in self.arm_polygons(rig):
                    poly(points, '#182a2d', '#263b3c', .7)
                for detail in self.sleeve_details(rig):
                    line(detail, '#213639', .8)
                anchor = rig['anchor']
                sprite, offset = self._hand_sprite(rig, scale)
                pos = (round(anchor[0]*scale+offset[0]), round(anchor[1]*scale+offset[1]))
                image.alpha_composite(sprite, pos)

            for index, world in enumerate((left_world, right_world)):
                # Fingers wrap around the exposed rim/end. Clearance is
                # guaranteed by the path, not by changing depth mid-motion.
                objects.append((-1002-index*.01, lambda index=index: paint_hand(index)))
        for _, paint in sorted(objects, key=lambda entry: entry[0], reverse=True):
            paint()

        return image.resize((self.WIDTH, self.HEIGHT), resample.BICUBIC)




# Tk 牌桌。尺寸与底部操作条取自 UTH，绿色下注毡按实桌照片重绘。
ROOT_BG, GOLD, PANEL_BG = "#1B3D31", "#D4AF37", "#F2E6C9"
TEXT, DARK_BLUE, HEADER_BG, TITLE_FG = "#ffffff", "#173f66", "#D8B46A", "#2A1B08"
BG, FELT = ROOT_BG, "#176343"
INK, EDGE, MUTED = "#fff6df", "#d1dbad", "#bccbbc"
YELLOW, CRIMSON, LIGHT_FELT = "#ffe044", "#ff4644", "#438d52"
FONT = {"win32": "Microsoft YaHei UI", "darwin": "PingFang SC"}.get(sys.platform, "Noto Sans CJK SC")
W, H = 1150, 750
TAB_TOP, NUM_TOP, NUM_BOTTOM, SUIT_BOTTOM, BOARD_BOTTOM = 186, 246, 458, 538, 622
FELT_LEFT, FELT_RIGHT = 24, 1134
CARD_W, CARD_H = 108, 151.2
CARD_POSITIONS = tuple((429 + 130 * i - CARD_W/2, 130 - CARD_H/2) for i in range(4))
# 统一牌左上角起点，使牌心对齐第 2、3 张公共牌的中线，从画面顶部之外发出。
CARD_DEAL_ORIGIN = ((CARD_POSITIONS[1][0] + CARD_POSITIONS[2][0]) / 2, -CARD_H - 8)
SUIT_FONT = {"win32": "Segoe UI Symbol", "darwin": "Apple Symbols"}.get(sys.platform, "DejaVu Sans")
# 七段数字从顶端起顺时针标为 a 至 f，中段为 g。
LED_SHAPES = (
    (4, 4, 8, 0, 29, 0, 33, 4, 29, 8, 8, 8),
    (34, 5, 37, 8, 37, 24, 33, 29, 30, 25, 30, 10),
    (33, 32, 37, 36, 37, 54, 33, 58, 30, 54, 30, 36),
    (4, 58, 8, 54, 29, 54, 33, 58, 29, 62, 8, 62),
    (3, 32, 7, 36, 7, 52, 3, 57, 0, 54, 0, 36),
    (3, 5, 7, 9, 7, 25, 3, 29, 0, 25, 0, 9),
    (4, 31, 8, 27, 29, 27, 33, 31, 29, 35, 8, 35),
)
LED_LIT = {
    "0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg", "5": "acdfg",
    "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg", "-": "g",
}
# 数字牌的两侧列和中列分别在哪些高度画花色，按牌高的比例给出。
PIP_ROWS = {
    "A": ((), (.50,)), "2": ((), (.23, .77)), "3": ((), (.23, .50, .77)),
    "4": ((.23, .77), ()), "5": ((.23, .77), (.50,)),
    "6": ((.23, .50, .77), ()), "7": ((.23, .50, .77), (.36,)),
    "8": ((.23, .50, .77), (.36, .64)), "9": ((.20, .40, .60, .80), (.50,)),
    "10": ((.20, .40, .60, .80), (.30, .70)),
}
CHIP_SIZE = 56
HOUSE_CHIP_POS = (575, 43)
COLOR_FIELDS = {RED: "#ff2a23", BLACK: "#050505"}


def felt_x(fraction):
    return FELT_LEFT + fraction * (FELT_RIGHT - FELT_LEFT)


@dataclass(frozen=True)
class FeltCell:
    key: str
    left: float
    right: float
    top: float
    bottom: float
    number: Optional[int] = None

    @property
    def center(self):
        y = (self.top + self.bottom) / 2
        return felt_x((self.left + self.right) / 2), y

    @property
    def group_member(self):
        return self.number is not None and self.key in (LOW, HIGH)

    def corners(self):
        return (felt_x(self.left), self.top, felt_x(self.right), self.top,
                felt_x(self.right), self.bottom, felt_x(self.left), self.bottom)

    def contains(self, x, y):
        return (self.top + 1 < y < self.bottom - 1
                and felt_x(self.left) + 1 < x < felt_x(self.right) - 1)


def build_felt():
    cells = [FeltCell(LOW, 1/14, 3/14, TAB_TOP, NUM_TOP),
             FeltCell(HIGH, 11/14, 13/14, TAB_TOP, NUM_TOP),
             FeltCell("straight_0", 0, 1/14, NUM_TOP, NUM_BOTTOM, 0)]
    height = (NUM_BOTTOM - NUM_TOP) / 3
    for row, group in enumerate((TOP, MIDDLE, BOTTOM)):
        y = NUM_TOP + row * height
        for col in range(12):
            number = 1 + row + 3 * col
            if number <= 6:
                key = LOW
            elif number >= 31:
                key = HIGH
            else:
                key = f"straight_{number}"
            cells.append(FeltCell(key, (col+1)/14, (col+2)/14, y, y+height, number))
        cells.append(FeltCell(group, 13/14, 1, y, y+height))
    suit_keys = ("suit_diamonds", "suit_hearts", "suit_clubs", "suit_spades")
    for col, (suit, outside) in enumerate(zip(suit_keys, (EVEN, RED, BLACK, ODD))):
        cells.append(FeltCell(suit, col/4, (col+1)/4, NUM_BOTTOM, SUIT_BOTTOM))
    # 红、扑克顺序、黑连续排列；四个花色的原有落点保留。
    for key, left, right in ((EVEN, 0, 1/4), (RED, 1/4, 5/12),
                             (POKER_ORDER, 5/12, 7/12), (BLACK, 7/12, 3/4), (ODD, 3/4, 1)):
        cells.append(FeltCell(key, left, right, SUIT_BOTTOM, BOARD_BOTTOM))
    return tuple(cells)


FELT_CELLS = build_felt()


def chip_label(amount):
    # 沿用 UTH 的两位有效数字和省略标记，不改变真实金额。
    value = Decimal(str(amount)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
    if value == Decimal("2.50"):
        return "2.50"
    if abs(value) >= 1_000_000:
        divisor, suffix = Decimal(1_000_000), "M"
    elif abs(value) >= 1000:
        divisor, suffix = Decimal(1000), "K"
    else:
        label = format(value, "f")
        return label.rstrip("0").rstrip(".") if "." in label else label
    scaled = value/divisor
    precision = Decimal(1).scaleb(abs(scaled).adjusted()-1)
    shown = scaled.quantize(precision, rounding=ROUND_DOWN)
    label = format(shown, "f")
    if "." in label:
        label = label.rstrip("0").rstrip(".")
    return label+suffix+("+" if shown != scaled else "")


@dataclass(frozen=True)
class ChipTransfer:
    key: str
    role: str
    amount: int
    start: tuple
    target: tuple
    duration: int


class PoKarDetteGameGUI(tk.Frame):
    DEAL_MOVE_MS = (128 / 0.75) / 0.85
    DEAL_CARD_MS = 224 / 0.85
    FLIP_MS = 32
    FLASH_INTERVAL_MS = 1000
    FLASH_COUNT = 3
    BET_CHIP_RADIUS = 16 * 4 / 3

    def __init__(self, parent, initial_balance=10_000, username="Guest",
                 on_back=None, on_balance_change=None):
        super().__init__(parent, bg=BG, width=W, height=H)
        self.pack_propagate(False)
        self.parent = parent
        self.root = self.winfo_toplevel()
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.username = username
        self._closed = False
        self._job = self._instruction_window = None
        self._enter_bindings = {}
        self.store = None
        try:
            self.store = TableStore(username, initial_balance, on_balance_change=on_balance_change)
            self.table = Table(self.store)
            self.selected_bet_amount = self.table.limits.minimum
            self.revealed = 0
            self.round_state = "betting"
            self._hover_cell = None
            self._note = ""
            self.scale_factor, self.offset_x, self.offset_y = 1., 0., 0.
            self._chrome_geometry = None
            self.bet_spots = []
            self.control_buttons = {}
            self._chip_cells = {}
            self._last_chip_cells = {}
            self._last_win = 0
            self._result_flash_job = None
            self._result_flash_state = False
            self._flash_count = 0
            self._result_flash_spot_ids = frozenset()
            self._visual_chips = {}
            self._bet_layouts = deque()
            self._transfers = ()
            self._transfer_positions = {}
            self._sweep_offset = 0
            self._card_motion = None
            self._cut_dialog = None
            self._pending_cut_threshold = None
            self._cut_notice_seen = False
            self._cut_notice_active = False
            self._cut_notice_popup = None
            self._round_cut_card_offset = None
            self._burn_motion = None
            self._burn_visual_count = 0
            self._card_folder = "Poker2"
            self._images = {}
            self._photos = {}
            self._card_root = next((p / "A_Tools" / "Card" for p in Path(__file__).resolve().parents
                                    if (p / "A_Tools" / "Card").is_dir()), None)
            self.canvas = tk.Canvas(self, width=W, height=H, bg=BG, bd=0,
                                    highlightthickness=0, takefocus=True)
            self.board_canvas = self.canvas
            self._create_chrome()
            self.canvas.pack(fill="both", expand=True)
            self.canvas.bind("<Configure>", lambda _: self._paint())
            self.canvas.bind("<Motion>", self._motion)
            self.canvas.bind("<Leave>", self._leave)
            self.canvas.bind("<Button-1>", self.on_board_click)
            self.canvas.bind("<Button-3>", self.on_board_right_click)
            self.canvas.bind("<Control-Button-1>", self.on_board_right_click)
            self.canvas.bind("<Map>", lambda _: self.canvas.focus_set(), add="+")
            # 与 UTH 一样，仅追加本页的回车处理，离开时按绑定 ID 移除。
            for sequence in ("<Return>", "<KP_Enter>"):
                self._enter_bindings[sequence] = self.winfo_toplevel().bind(
                    sequence, self._on_enter, add="+")
            self.bind("<Destroy>", self._on_destroy, add="+")
            if not self.table.shoe.ready:
                self.round_state = "preparing_shoe"
                self._job = self.after(180, self.start_new_shoe_cut)
        except Exception:
            if self.store:
                self.store.release()
            self._closed = True
            self._unbind_enter()
            super().destroy()
            raise

    @property
    def balance(self):
        return float(self.store.balance)

    @balance.setter
    def balance(self, value):
        self.store.balance = _cash(value)

    def _persist_balance(self):
        """沿用 UTH 的保存结果接口，失败时保留当前金额供重试。"""
        try:
            self.store.persist_balance()
        except Exception as exc:
            messagebox.showerror('余额保存失败', str(exc), parent=self)
            return False
        return True

    @property
    def current_bets(self):
        return self.table.current_bets

    def _text(self, x, y, value, size, color=INK, *, family=None, weight="bold",
              anchor="center", tags=(), angle=0):
        return self.canvas.create_text(
            x, y, text=value, fill=color, anchor=anchor, tags=tags, angle=angle,
            font=(family or FONT, -max(1, round(size * self.scale_factor)), weight))

    def _uth_text(self, x, y, text, size=12, color=TEXT, **kw):
        return self.canvas.create_text(x, y, text=text, fill=color, font=('Arial', size, 'bold'), **kw)

    def _draw_limit_table(self):
        # UTH 限额表的标题、坐标、字号和颜色。
        c = self.canvas
        x0,x1,y0 = 30,349,75
        c.create_rectangle(x0,y0,x1,181,fill=ROOT_BG,outline=GOLD,width=2,tags='limits')
        c.create_rectangle(x0,y0,x1,y0+29,fill=ROOT_BG,outline=GOLD,tags='limits')
        self._uth_text((x0+x1)/2,y0+14,'下注上限',13,PANEL_BG,tags='limits')
        titles = ('每注最低','外注最高','内注最高')
        self.limit_value_items = []
        for col,title in enumerate(titles):
            left=x0+col*(x1-x0)/3
            right=x0+(col+1)*(x1-x0)/3
            c.create_rectangle(left,y0+29,right,y0+66,outline='#77906B',tags='limits')
            c.create_rectangle(left,y0+66,right,181,outline='#77906B',tags='limits')
            self._uth_text((left+right)/2,y0+47,title,11,PANEL_BG,tags='limits')
            self.limit_value_items.append(self._uth_text((left+right)/2,y0+86,'',12,GOLD,tags='limits'))
        c.tag_bind('limits','<Button-1>',self.toggle_high_bet_limits)
        c.tag_bind('limits','<Enter>',lambda _e:c.configure(cursor='hand2'))
        c.tag_bind('limits','<Leave>',lambda _e:c.configure(cursor=''))

    def _draw_bottom_controls(self):
        c=self.canvas
        c.create_rectangle(0,625,1150,748,fill=ROOT_BG,outline='#6C7850',width=2,tags='controls')
        self.balance_item=self._uth_text(10,665,'',18,TEXT,anchor='w',tags='controls')
        self.total_item=self._uth_text(10,710,'',18,TEXT,anchor='w',tags='controls')
        self.clear_button=self.create_control_button(278,650,344,704,'清除',self.clear_bets,'#9B403A',font_size=11,draw_shadow=False)
        self._draw_chips()
        self.info_button=self.create_control_button(810,650,855,695,'?',self.show_game_instructions,DARK_BLUE,font_size=17,draw_shadow=False)
        self.repeat_button=self.create_control_button(862,638,1000,708,'重复下注',self._repeat_last_bet,'#536A43',font_size=11,draw_shadow=False)
        self.start_button=self.create_control_button(1012,628,1138,720,'开牌',self.start_game,HEADER_BG,
            fg=TITLE_FG,font_size=14,subtext='Enter',subtext_font_size=10,draw_shadow=False)

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

    def _create_chrome(self):
        """保留 UTH 控件本身，窗口缩放时根据原坐标重排，事件仍绑定在原控件上。"""
        self._draw_limit_table()
        self._draw_bottom_controls()
        c = self.canvas
        c.addtag_withtag("chrome", "all")
        self._base_chrome = {}
        for item in c.find_withtag("chrome"):
            font = c.tk.splitlist(c.itemcget(item, "font")) if c.type(item) == "text" else None
            self._base_chrome[item] = (tuple(c.coords(item)), font)

    def _draw_chips(self):
        # UTH 筹码栏的外圈、面额圆、文字和间距。
        c = self.canvas
        diameter, gap = CHIP_SIZE, 8
        chips = self.table.limits.chips
        colors = HIGH_COLORS if self.table.limits is HIGH_LIMITS else NORMAL_COLORS
        start = (W - (len(chips)*diameter + (len(chips)-1)*gap)) / 2
        self._rack_items = []
        for i, (amount, color) in enumerate(zip(chips, colors)):
            x = start + i*(diameter + gap)
            tag = f"rack_{i}"
            tags = ("rack", tag)
            rim = c.create_oval(x, 646, x+56, 702, fill="#182F25",
                                outline=GOLD if amount == self.selected_bet_amount else "#6C7850",
                                width=3, tags=tags)
            face = c.create_oval(x+5, 651, x+51, 697, fill=color, outline=PANEL_BG, width=2, tags=tags)
            label = self._uth_text(x+28, 674, chip_label(amount), 10,
                                   TEXT if color in ("#050505", "#ff2a23") else "#050505", tags=tags)
            self._rack_items.append((rim, face, label))
            c.tag_bind(tag, "<Button-1>", lambda _e, index=i: self._select_chip(self.table.limits.chips[index]))

    def _chip(self, x, y, amount, color, tags):
        # 桌面和动画筹码沿用 UTH 的半径、单黑边及字级。
        c, r = self.canvas, self.BET_CHIP_RADIUS
        face = c.create_oval(x-r, y-r, x+r, y+r, fill=color,
                             outline="#000000", width=1, tags=tags)
        fg = TEXT if color in ("#050505", "#ff2a23") else "#050505"
        text = chip_label(amount)
        size = 10 if len(text) >= 5 else 12
        label = c.create_text(x, y, text=text, fill=fg, tags=tags,
                              font=("Arial", max(1, round(size*self.scale_factor)), "bold"))
        return face, label

    def _layout_chrome(self):
        c = self.canvas
        for item, (coords, font) in self._base_chrome.items():
            actual = []
            for x, y in zip(coords[::2], coords[1::2]):
                actual.extend(self._screen(x, y))
            c.coords(item, *actual)
            if font:
                family, size, *style = font
                c.itemconfigure(item, font=(family, max(1, round(int(size)*self.scale_factor)), *style))
        for button in self.control_buttons.values():
            button["center_y"] = c.coords(button["text"])[1]
            if button["subtext"]:
                button["subtext_center_y"] = c.coords(button["subtext"])[1]

    def _sync_chrome(self):
        c, profile = self.canvas, self.table.limits
        cash = self.store.balance
        c.itemconfigure(self.balance_item, text=f"余额: ${cash:,.2f}")
        total = self.table.held
        c.itemconfigure(self.total_item, text=f"本局下注: ${total:,.2f}" if total else f"上局返还: ${self._last_win:,.2f}")
        for item, value in zip(self.limit_value_items, (profile.minimum, profile.outside_max, profile.number_max)):
            c.itemconfigure(item, text=f"${value:,}")
        colors = HIGH_COLORS if profile is HIGH_LIMITS else NORMAL_COLORS
        for (rim, face, label), amount, color in zip(self._rack_items, profile.chips, colors):
            selected = amount == self.selected_bet_amount
            c.itemconfigure(rim, outline=GOLD if selected else "#6C7850")
            c.itemconfigure(face, fill=color)
            c.itemconfigure(label, text=chip_label(amount), fill=TEXT if color in ("#050505", "#ff2a23") else "#050505")
        betting = self.round_state == "betting"
        for tag, enabled in ((self.clear_button, betting),
                             (self.repeat_button, betting and bool(self.table.last_bets)),
                             (self.start_button, betting or self.round_state == "credit_pending")):
            self.set_control_button_state(tag, enabled)
        c.itemconfigure(self.control_buttons[self.start_button]["text"],
                        text="重试入账" if self.round_state == "credit_pending" else "开牌")

    def _fit_items(self, tag):
        self.canvas.scale(tag, 0, 0, self.scale_factor, self.scale_factor)
        self.canvas.move(tag, self.offset_x, self.offset_y)

    def _paint(self):
        c = self.canvas
        w, h = c.winfo_width(), c.winfo_height()
        if self._closed or min(w, h) < 40:
            return
        if self._cut_notice_active:
            self._sync_chrome()
            return
        if self._chrome_geometry != (w, h):
            self.scale_factor = min(w/W, h/H)
            self.offset_x = (w-W*self.scale_factor)/2
            self.offset_y = (h-H*self.scale_factor)/2
            self._layout_chrome()
            self._photos.clear()
            self._chrome_geometry = (w, h)
        for tag in ("scene", "public_card", "table_chip", "moving_chips"):
            c.delete(tag)
        self._draw_board()
        self._draw_header()
        c.addtag_withtag("scene", "!chrome")
        self._fit_items("scene")
        self._render_cards()
        if self.round_state == "burning":
            self._render_burn_cards()
        self._sync_chrome()
        c.tag_raise("chrome")
        self._render_wagers()

    def _draw_header(self):
        c = self.canvas
        self._text(30, 35, "Po Kar Dette", 33, "#eed091", family="Georgia", anchor="w")
        c.create_rectangle(356, 8, 892, 226, fill="#1c4335", outline="#9e966b", tags="card_tray")
        c.create_rectangle(359, 11, 889, 223, outline="#385944", tags="card_tray")
        self._text(371, 27, "公共牌", 24, INK, anchor="w")
        for x, y in CARD_POSITIONS:
            c.create_rectangle(x, y, x+CARD_W, y+CARD_H, fill="#193c30", outline="#53705a",
                               dash=(4, 4), tags="card_slot")
        self._draw_scoreboard()

    def _draw_scoreboard(self):
        c = self.canvas
        c.create_polygon(908, 8, 1127, 8, 1135, 16, 1135, 172, 1127, 180,
                         908, 180, 900, 172, 900, 16, fill="#19231e", outline="#ba9b60",
                         width=2, tags="scoreboard")
        c.create_polygon(910, 12, 1125, 12, 1131, 18, 1131, 170, 1125, 176,
                         910, 176, 904, 170, 904, 18, fill="#101e19", outline="#4c513d",
                         tags="scoreboard")
        for left, right in ((917, 980), (1055, 1118)):
            c.create_line(left, 26, right, 26, fill="#6d6040", tags="scoreboard")
        self._text(1017, 25, "总点数", 15, "#e9d5a0", tags="scoreboard")
        # 只累计已完全翻开的牌，翻面过程及未开牌不泄露点数。
        current = (sum(POINTS[rank] for suit, rank in self.table.outcome.cards[:self.revealed])
                   if self.table.outcome is not None and self.revealed else None)
        digits = f"{current:02d}" if current is not None else "--"
        left = 1017 - (37 * len(digits) + 10 * (len(digits) - 1)) / 2
        for char in digits:
            for segment, shape in zip("abcdefg", LED_SHAPES):
                lit = segment in LED_LIT[char]
                if not lit and char == "-":
                    continue
                points = [v + (left if i % 2 == 0 else 40) for i, v in enumerate(shape)]
                c.create_polygon(points, fill="#ffd075" if lit else "#1d2c23", outline="",
                                 tags=("scoreboard", "current_points", f"score_{digits}"))
            # 八段数码管的小数点保持熄灭，游戏只显示整数点数。
            c.create_oval(left+39, 98, left+43, 102, fill="#1d2c23", outline="", tags="scoreboard")
            left += 47
        c.create_line(912, 112, 1123, 112, fill="#655c40", tags="scoreboard")
        self._text(1017, 125, "最近点数", 14, "#d9caa3", tags="scoreboard")
        records = self.store.data.get("Record1", {})
        # 开牌时记录已经写入，只在第四张翻完后把它列入最近点数。
        first = 2 if self.round_state == "dealing" and self.revealed < 4 else 1
        for slot in range(6):
            value = records.get(f"{first + slot:02d}_Data", {}).get("result")
            filled = value not in (None, "")
            latest = filled and slot == 0
            x = 911 + slot * 36
            c.create_rectangle(x, 139, x+32, 168, fill="#463a24" if latest else "#1c3027",
                               outline="#ceac69" if latest else "#384a3d", tags="scoreboard")
            color = "#ffdf96" if latest else ("#e4eadb" if filled else "#607065")
            self._text(x+16, 153, str(value) if filled else "–", 18, color, family="Arial",
                       tags=("scoreboard", "recent_points", f"recent_{slot}"))

    def _card_art(self, card, width):
        if Image is None or self._card_root is None:
            return None
        key = (card, max(1, round(width*self.scale_factor)), max(1, round(CARD_H*self.scale_factor)))
        if key in self._photos:
            return self._photos[key]
        if card not in self._images:
            name = "Background.png" if card is None else f"{card[0]}{card[1]}.png"
            self._images[card] = None
            try:
                with Image.open(self._card_root / self._card_folder / name) as source:
                    self._images[card] = source.convert("RGBA")
            except (OSError, ValueError):
                pass
        source = self._images[card]
        if source is None:
            return None
        photo = ImageTk.PhotoImage(source.resize(key[1:], getattr(Image, "Resampling", Image).LANCZOS), master=self.canvas)
        self._photos[key] = photo
        return photo

    def _draw_card(self, index, x, y, card, width=CARD_W, tags=None):
        c = self.canvas
        tags = ("public_card", f"public_{index}") if tags is None else tags
        art = self._card_art(card, width)
        if art is not None:
            c.create_image(x, y, image=art, anchor="nw", tags=tags)
            return
        # 没有宿主牌图时，直接按每一帧的宽度绘制牌面和牌背。
        if width < 5:
            c.create_rectangle(x, y, x+width, y+CARD_H, fill="#f5eddd", outline="", tags=tags)
            return
        face_scale = CARD_W/120
        r, right, bottom = min(8*face_scale, width/5), x+width, y+CARD_H
        c.create_polygon(x+r, y, right-r, y, right, y, right, y+r,
                         right, bottom-r, right, bottom, right-r, bottom,
                         x+r, bottom, x, bottom, x, bottom-r, x, y+r, x, y,
                         smooth=True, splinesteps=8, fill=DARK_BLUE if card is None else "#fffbf2",
                         outline="#d4c8a9", width=1, tags=tags)
        if card is None:
            c.create_rectangle(x+width*.05, y+6*face_scale, right-width*.05, bottom-6*face_scale,
                               outline="#cbb47e", tags=tags)
            for row in range(8):
                for col in range(5):
                    cx, cy = x + width*(.16 + col*.17), y + CARD_H*(.14 + row*.103)
                    dx = width*.055
                    c.create_polygon(cx, cy-6*face_scale, cx+dx, cy, cx, cy+6*face_scale, cx-dx, cy,
                                     fill="#345c70", outline="", tags=tags)
            return
        suit, rank = card
        symbol = SYMBOL[suit]
        color = "#b62238" if suit in RED_SUITS else "#192721"
        for cx, cy, angle in ((x+width*.13, y+19*face_scale, 0),
                              (x+width*.87, bottom-19*face_scale, 180)):
            self._text(cx, cy, rank, min(25*face_scale, width*.21), color,
                       family="Georgia", angle=angle, tags=tags)
            self._text(cx, cy+(19 if angle == 0 else -19)*face_scale, symbol, min(17*face_scale, width*.15),
                       color, family=SUIT_FONT, weight="normal", angle=angle, tags=tags)
        if rank in PIP_ROWS:
            side, middle = PIP_ROWS[rank]
            size = (55 if rank == "A" else 28) * face_scale
            for column, rows in ((.32, side), (.50, middle), (.68, side)):
                for row in rows:
                    self._text(x+width*column, y+CARD_H*row, symbol, min(size, width*size/CARD_W),
                               color, family=SUIT_FONT, weight="normal", angle=180 if row > .5 else 0,
                               tags=tags)
        else:
            c.create_rectangle(x+width*.25, y+CARD_H*.23, x+width*.75, y+CARD_H*.77,
                               outline="#c7b990", tags=tags)
            self._text(x+width*.5, y+CARD_H*.45, rank, min(50*face_scale, width*.42),
                       color, family="Georgia", tags=tags)
            self._text(x+width*.5, y+CARD_H*.64, symbol, min(27*face_scale, width*.23),
                       color, family=SUIT_FONT, weight="normal", tags=tags)

    def _render_cards(self):
        self.canvas.delete("public_card")
        if self.revealed == 0 and self._card_motion is None:
            return
        for i, (x, y) in enumerate(CARD_POSITIONS):
            card = self.table.outcome.cards[i] if i < self.revealed else None
            width = CARD_W
            if self._card_motion is not None:
                phase, index, step = self._card_motion
                if i > index:
                    continue
                if phase == "deal":
                    if i == index:
                        start_x, start_y = CARD_DEAL_ORIGIN
                        x, y = start_x+(x-start_x)*step/6, start_y+(y-start_y)*step/6
                elif i == index:
                    width = max(1, round(CARD_W*abs(1-step/5)))
                    x += (CARD_W-width)/2
                    if step >= 5:
                        card = self.table.outcome.cards[i]
            self._draw_card(i, x, y, card, width)
        self._fit_items("public_card")
        if self._sweep_offset:
            self.canvas.move("public_card", self._sweep_offset*self.scale_factor, 0)

    def _draw_cell(self, cell, flash=False):
        c, key, n = self.canvas, cell.key, cell.number
        spot = BET_SPOTS[key]
        cx, cy = cell.center
        group = key in (LOW, HIGH)
        fill = COLOR_FIELDS.get(key, LIGHT_FELT if group else FELT)
        if key not in COLOR_FIELDS and self.round_state == "betting" and self._hover_cell and key == self._hover_cell.key:
            fill = "#548f50" if group else "#277a50"
        tags = ("result_flash", f"flash_{key}") if flash else ("felt_face", f"field_{key}")
        c.create_rectangle(felt_x(cell.left), cell.top, felt_x(cell.right), cell.bottom,
                           fill="#ffffff" if flash else fill, outline="#000000" if flash else EDGE, width=2, tags=tags)
        def label(x, y, value, size, color, family=None):
            return self._text(x, y, value, size, "#000000" if flash else color, family=family,
                              tags=tags if flash else ("felt_label",))
        odds = "7–2,700,000:1" if key == POKER_ORDER else f'{spot["payout"]}:1'
        if n is not None:
            label(cx, cy if cell.group_member else cy-10, n, 47 if n == 0 else 35,
                  CRIMSON if n == 0 else YELLOW, "Arial")
            if not cell.group_member:
                label(cx, cy+19, odds, 14, INK, "Arial")
        elif group:
            label(cx, cy-9, spot["label"], 19, "#ffedbe")
            label(cx, cy+14, odds, 14, INK, "Arial")
        elif key in (TOP, MIDDLE, BOTTOM):
            label(cx, cy-10, spot["label"], 24, "#ffbf93")
            label(cx, cy+19, odds, 14, INK, "Arial")
        elif key == POKER_ORDER:
            label(cx, cy-14, spot["label"], 25, "#ffe8a1")
            label(cx, cy+12, odds, 14, INK, "Arial")
        elif spot["type"] == "suit":
            suit = next(iter(spot["suits"]))
            label(cx, cy-12, spot["label"], 25, "#ff9697" if suit in RED_SUITS else "#f1eedb")
            for dx in (-62, 62):
                label(cx+dx, cy+12, SYMBOL[suit], 28, CRIMSON if suit in RED_SUITS else "#101e19", "DejaVu Sans")
            label(cx, cy+18, odds, 16, INK, "Arial")
        else:
            label(cx, cy-12, spot["label"], 28, INK if key in (RED, BLACK) else YELLOW)
            label(cx, cy+19, odds, 15, INK, "Arial")

    def _draw_board(self):
        c = self.canvas
        c.create_rectangle(0, 184, W, 625, fill="#20593e", outline="")
        self.bet_spots = []
        for cell in FELT_CELLS:
            self._draw_cell(cell)
            if not cell.group_member:
                self.bet_spots.append(dict(BET_SPOTS[cell.key], kind="cell", center=self._screen(*cell.center),
                    bounds=(*self._screen(felt_x(cell.left), cell.top), *self._screen(felt_x(cell.right), cell.bottom))))
        # Roulette 的中奖格白底黑字层。组合显示中奖组名及实际开出的数字。
        for cell in FELT_CELLS:
            if cell.key in self._result_flash_spot_ids and (not cell.group_member or cell.number == self.table.outcome.total):
                self._draw_cell(cell, flash=True)
        c.itemconfigure("result_flash", state="normal" if self._result_flash_state else "hidden")
        if self._note:
            self._text(W/2, 236, self._note, 13, "#ffebac")
        if (self.revealed == 4 and self.table.outcome is not None
                and self.table.outcome.poker_category):
            result = self.table.outcome
            self._text(624, 216, f"扑克顺序 · {result.poker_label} · {result.poker_payout:,}:1",
                       12, "#ffe8a1", tags="poker_result")

    def _stake_center(self, key):
        cell = self._chip_cells.get(key)
        if cell is None:
            cell = next(c for c in FELT_CELLS if c.key == key and not c.group_member)
        return cell.center

    def _render_wagers(self):
        c = self.canvas
        c.delete("table_chip")
        c.delete("moving_chips")
        colors = HIGH_COLORS if self.table.limits is HIGH_LIMITS else NORMAL_COLORS
        palette = tuple(reversed(tuple(zip(self.table.limits.chips, colors))))

        def draw(amount, xy, tags):
            color = next((color for value, color in palette if amount >= value), HEADER_BG)
            self._chip(*xy, amount, color, tags)

        for (key, role), (amount, xy) in self._visual_chips.items():
            draw(amount, xy, ("table_chip", f"{role}_{key}"))
        self._fit_items("table_chip")
        for i, transfer in enumerate(self._transfers):
            if i in self._transfer_positions:
                draw(transfer.amount, self._transfer_positions[i], ("moving_chips", f"transfer_{i}"))
        self._fit_items("moving_chips")


    def _screen(self, x, y):
        return self.offset_x+x*self.scale_factor, self.offset_y+y*self.scale_factor

    def _world(self, x, y):
        return (x-self.offset_x)/self.scale_factor, (y-self.offset_y)/self.scale_factor

    def _cell_at(self, x, y):
        return next((cell for cell in FELT_CELLS if cell.contains(x, y)), None)

    def _spot_at(self, x, y):
        cell = self._cell_at(*self._world(x, y))
        return cell.key if cell else None

    def _motion(self, event):
        cell = self._cell_at(*self._world(event.x, event.y)) if self.round_state == "betting" else None
        if cell != self._hover_cell:
            self._hover_cell = cell
            self._note = ""
            self.canvas.configure(cursor="hand2" if cell or "limits" in self.canvas.gettags("current") else "")
            self._paint()

    def _leave(self, event):
        if self._hover_cell is not None:
            self._hover_cell = None
            self._note = ""
            self.canvas.configure(cursor="")
            self._paint()

    def on_board_click(self, event):
        self.canvas.focus_set()
        if self.round_state == "betting":
            cell = self._cell_at(*self._world(event.x, event.y))
            if cell:
                self._hover_cell = cell
                self.place_bet(cell.key, cell)
        return "break"

    def on_board_right_click(self, event):
        key = self._spot_at(event.x, event.y)
        if key is not None and self.round_state == "betting":
            self.clear_single_bet(key)
        return "break"

    def _on_enter(self, event):
        if (not self._closed and self.winfo_ismapped() and self.root.grab_current() is None
                and event.widget.winfo_toplevel() == self.root):
            self.start_game()
            return "break"

    def _select_chip(self, amount):
        if self.round_state == "betting" and amount in self.table.limits.chips:
            self.selected_bet_amount = amount
            self._note = ""
            self._paint()

    def toggle_high_bet_limits(self, event=None):
        if self.round_state != "betting":
            return
        enable = self.table.limits is NORMAL
        if enable:
            password = simpledialog.askstring("高额下注", "请输入密码", show="*", parent=self.root)
            if password is None:
                return
            if password.strip() != time.strftime("%H%M"):
                messagebox.showerror("高额下注", "密码错误。", parent=self.root)
                return
        self.table.set_high_limits(enable)
        self._cancel_job()
        self._bet_layouts.clear()
        self._transfers = ()
        self._transfer_positions.clear()
        self._visual_chips.clear()
        self._chip_cells.clear()
        self._last_chip_cells.clear()
        self.selected_bet_amount = self.table.limits.minimum
        self._note = f"已切换至{self.table.limits.name}档，当前下注及上局重复记录已清空。"
        self._paint()

    def _action(self, func, *args):
        if self.round_state != "betting":
            return False
        try:
            added = func(*args)
        except BetError as exc:
            self._note = str(exc)
            self._paint()
            return False
        self._note = ""
        if added is not None and added < self.selected_bet_amount:
            key = args[0]
            self._note = f'{BET_SPOTS[key]["label"]} 本次放入 ${added:,}，已达本格上限 ${self.table.limits.maximum(key):,}。'
        return True

    def place_bet(self, spot_id, cell=None):
        if self._action(self.table.place_bet, spot_id, self.selected_bet_amount):
            if cell is not None and not cell.group_member:
                self._chip_cells[spot_id] = cell
            self._queue_bet_layout()

    def clear_bets(self):
        if self._action(self.table.clear_bets):
            self._chip_cells.clear()
            self._queue_bet_layout()

    def clear_single_bet(self, spot_id):
        if self._action(self.table.clear_bets, spot_id):
            self._chip_cells.pop(spot_id, None)
            self._queue_bet_layout()

    def _repeat_last_bet(self):
        if self._action(self.table.repeat_bets):
            self._chip_cells = self._last_chip_cells.copy()
            self._queue_bet_layout()

    def _queue_bet_layout(self):
        # 每次点击即时验资并记录落点。动画依次合并筹码，快点或连续选不同面额也不会吞注。
        layout = {(key, "stake"): (amount, self._stake_center(key)) for key, amount in self.current_bets.items()}
        chip = self.table.limits.chips.index(self.selected_bet_amount)
        self._bet_layouts.append((layout, (415+64*chip, 674)))
        if not self._transfers:
            self._next_bet_layout()
        else:
            self._sync_chrome()

    def _next_bet_layout(self):
        while self._bet_layouts:
            layout, rack = self._bet_layouts.popleft()
            transfers = []
            for tag in dict.fromkeys((*self._visual_chips, *layout)):
                key, _role = tag
                old, origin = self._visual_chips.get(tag, (0, rack))
                new, target = layout.get(tag, (0, origin))
                if old > new:
                    transfers.append(ChipTransfer(key, "withdraw", old-new, origin, rack, 440))
                if old < new:
                    transfers.append(ChipTransfer(key, "place", new-old, rack, target, 220))
                staying = min(old, new)
                if staying and origin != target:
                    transfers.append(ChipTransfer(key, "move", staying, origin, target, 220))
                    staying = 0
                if staying:
                    self._visual_chips[tag] = staying, origin
                else:
                    self._visual_chips.pop(tag, None)
            if transfers:
                def arrived(final_layout=layout):
                    self._visual_chips = final_layout
                    self._next_bet_layout()
                self._run_transfers(transfers, arrived)
                return
        if self.round_state == "closing_bets":
            self._deal_when_ready()
        else:
            self._paint()

    def _cancel_job(self):
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None

    def _show_cut_dialog(self, second=False):
        """Cut B before A, move black to the tail, then reinsert yellow."""
        dialog = tk.Toplevel(self.winfo_toplevel())
        self._cut_dialog = dialog
        dialog.title('切牌')
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.configure(bg='#0b4038')
        self.update_idletasks()
        width, height = BaccaratCutScene.WIDTH, BaccaratCutScene.HEIGHT+68
        x = max(0, self.winfo_rootx()+(self.winfo_width()-width)//2)
        y = max(0, self.winfo_rooty()+(self.winfo_height()-height)//2)
        dialog.geometry(f'{width}x{height}+{x}+{y}')
        cv = tk.Canvas(dialog, width=width, height=BaccaratCutScene.HEIGHT,
                       bg='#0b4038', highlightthickness=0, cursor='arrow')
        cv.pack(fill=tk.X, side=tk.TOP)
        back = None
        if Image is not None and self._card_root is not None:
            try:
                with Image.open(self._card_root / self._card_folder / "Background.png") as source:
                    back = source.convert("RGBA")
            except (OSError, ValueError):
                pass
        scene = BaccaratCutScene(back)
        rng = random.SystemRandom()
        selected = {'value': rng.randint(60, 150)}
        state = {'running': False, 'photo': None, 'image': None, 'closed': False,
                 'dragging': False, 'drag_x': 0, 'drag_value': None, 'confirmed': None}
        pending = set()
        result = [None]
        total = float(scene.CARD_COUNT)
        tail_count = self._pending_cut_threshold or self.table.shoe.cut_threshold
        marker_final = scene.LENGTH*(total-tail_count)/total

        def schedule(delay, callback):
            holder = {}
            def run():
                pending.discard(holder.get('id'))
                if not state['closed'] and not self._closed:
                    callback()
            holder['id'] = dialog.after(delay, run)
            pending.add(holder['id'])

        def close_dialog():
            if state['closed']:
                return
            state['closed'] = True
            for after_id in list(pending):
                try:
                    dialog.after_cancel(after_id)
                except tk.TclError:
                    pass
            pending.clear()
            try:
                dialog.grab_release()
                dialog.destroy()
            except tk.TclError:
                pass
            if self._cut_dialog is dialog:
                self._cut_dialog = None

        # The exit path also cancels this dialog's own timers before destruction.
        dialog._close_cut_scene = close_dialog

        def polygon(points, fill, outline='#aaa48e'):
            cv.create_polygon(*[v for point in points for v in point],
                              fill=fill, outline=outline, tags='cut_scene_fallback')

        def render(**pose):
            split = scene.LENGTH*selected['value']/total
            frame = scene.render(split, **pose)
            if frame is not None and ImageTk is not None:
                state['photo'] = ImageTk.PhotoImage(frame, master=cv)
                if state['image'] is None:
                    state['image'] = cv.create_image(0, 0, anchor='nw', image=state['photo'])
                    cv.tag_lower(state['image'])
                else:
                    cv.itemconfigure(state['image'], image=state['photo'])
            else:
                # Share separator geometry with the Pillow path.
                cv.delete('cut_scene_fallback')
                p = scene.project
                a, ay, az = pose.get('a_x', 0), pose.get('a_y', 0), pose.get('a_z', 0)
                b, by, bz = pose.get('b_x', split), pose.get('b_y', 0), pose.get('b_z', 0)
                d, h = scene.DEPTH, scene.CARD_H
                parts = ((a, ay, split, az), (b, by, scene.LENGTH-split, bz))
                black_x, black_y, black_z = (pose.get('black_x', scene.LENGTH+2),
                                        pose.get('black_y', 0), pose.get('black_z', 0))
                mx, my, raised = pose.get('marker_x', split), pose.get('marker_y', 0), pose.get('marker_raise', 32)
                shift = pose.get('holder_shift', 0)
                left = pose.get('left_hand', scene.holder_contact(shift, 0))
                right = pose.get('right_hand', scene.holder_contact(shift, 1))
                grips = (pose.get('left_grip', 0), pose.get('right_grip', 0))
                openings = (pose.get('left_open', 0), pose.get('right_open', 0))
                rigs = [scene.hand_rig(side, world, grips[side], openings[side])
                        for side, world in enumerate((left, right))]
                for rail in scene.holder_rails(shift):
                    polygon(rail, '', '#b7d7d8')

                def packet(xx, yy, length, zz):
                    polygon([p(xx, yy, zz), p(xx+length, yy, zz),
                             p(xx+length, yy, zz+h), p(xx, yy, zz+h)], '#e8e3d5')
                    polygon([p(xx, yy, zz+h), p(xx+length, yy, zz+h),
                             p(xx+length, yy+d, zz+h), p(xx, yy+d, zz+h)], '#faf6e8')
                    polygon([p(xx, yy+d, zz+h), p(xx, yy, zz+h),
                             p(xx, yy, zz), p(xx, yy+d, zz)], '#f5eee1')
                    for i in range(1, max(2, int(length/4))):
                        edge = xx+i*4
                        cv.create_line(*p(edge, yy, zz), *p(edge, yy, zz+h),
                                       fill='#b8b6a8', tags='cut_scene_fallback')

                def separator(xx, yy, zz, yellow=False):
                    for corners in scene.separator_quads(xx, yy, zz, parts):
                        color = '#eccd42' if yellow else '#1e2124'
                        polygon(corners, color, color)

                def hand(side):
                    rig = rigs[side]
                    for points in scene.arm_polygons(rig):
                        polygon(points, '#182a2d', '#263b3c')
                    for detail in scene.sleeve_details(rig):
                        cv.create_line(*[v for p in detail for v in p], fill='#213639',
                                       width=1, tags='cut_scene_fallback')
                    polygon(scene.fallback_hand(rigs[side]), '#c68f73', '#825c4c')

                objects = [(yy+.32*(xx+length/2)-zz*.5,
                            lambda part=part: packet(*part))
                           for part in parts for xx, yy, length, zz in (part,)]
                objects.append((-1000+.001*(black_y+.32*black_x-black_z*.5),
                                lambda: separator(black_x, black_y, black_z)))
                objects.append((-1000+.001*(my+.32*mx-(raised-8)*.5),
                                lambda: separator(mx, my, raised-8, True)))
                for side in (0, 1):
                    objects.append((-1002-side*.01, lambda side=side: hand(side)))
                for _, paint in sorted(objects, key=lambda item: item[0], reverse=True):
                    paint()
            cv.tag_raise('cut_prompt')

        render()
        prompt = cv.create_text(scene.WIDTH/2, 26, text='拖动黄色卡片选择位置，确认后由庄家切牌',
                                font=('微软雅黑', 16, 'bold'), fill='#fff0b8', tags='cut_prompt')
        for limit in (scene.CUT_MIN, scene.CUT_MAX):
            world_x = scene.LENGTH*limit/total
            cv.create_line(*scene.project(world_x, 0, scene.CARD_H+1),
                           *scene.project(world_x, scene.DEPTH, scene.CARD_H+1),
                           fill='#c89667', width=2, dash=(4, 3), tags='cut_bounds')

        def select(value):
            selected['value'] = max(scene.CUT_MIN, min(scene.CUT_MAX, round(value)))
            render()

        def start_drag(event):
            if state['running']:
                return 'break'
            state['dragging'] = False
            split = scene.LENGTH*selected['value']/total
            tab = scene.separator_quads(split, 0, 32-8,
                                        ((0, 0, split, 0), (split, 0, scene.LENGTH-split, 0)))
            if not any(scene.contains_point(face, event.x, event.y) for face in tab):
                return 'break'
            # Keep the grabbed point attached to the cursor. Neither dealer
            # hand follows the pointer, and pressing the deck does not cut it.
            state.update(dragging=True, drag_x=event.x, drag_value=selected['value'])
            cv.configure(cursor='sb_h_double_arrow')
            return 'break'

        def move_cut(event):
            if not state['running'] and state['dragging']:
                select(state['drag_value']+(event.x-state['drag_x'])/scene.LENGTH*total)
            return 'break'

        def stop_drag(_event=None):
            state['dragging'] = False
            cv.configure(cursor='arrow')
            return 'break'

        def hover(event):
            if state['running'] or state['dragging']:
                return
            split = scene.LENGTH*selected['value']/total
            tab = scene.separator_quads(split, 0, 24,
                                        ((0, 0, split, 0), (split, 0, scene.LENGTH-split, 0)))
            over_tab = any(scene.contains_point(face, event.x, event.y) for face in tab)
            cv.configure(cursor='sb_h_double_arrow' if over_tab else 'arrow')

        def finish():
            result[0] = state['confirmed']
            schedule(320, close_dialog)

        def begin(value=None):
            if state['running'] or self._closed:
                return 'break'
            if value is not None:
                selected['value'] = max(scene.CUT_MIN, min(scene.CUT_MAX, int(value)))
            state.update(running=True, dragging=False, confirmed=int(selected['value']))
            cv.itemconfigure(prompt, text='稍等，很快就完成了')
            confirm_btn.config(state=tk.DISABLED)
            cv.configure(cursor='arrow')
            cv.delete('cut_bounds')
            split = scene.LENGTH*state['confirmed']/total

            def phase(index=0):
                if index == len(scene.PHASES):
                    finish()
                    return
                _, duration = scene.PHASES[index]
                started = time.monotonic()
                def frame():
                    frame_start = time.monotonic()
                    progress = min(1.0, (frame_start-started)/duration)
                    render(**scene.pose(split, index, progress, marker_final))
                    if progress < 1:
                        work_ms = (time.monotonic()-frame_start)*1000
                        schedule(max(1, round(1000/30-work_ms)), frame)
                    else:
                        phase(index+1)
                frame()
            phase()
            return 'break'

        def random_confirm(_event=None):
            return begin(rng.randint(scene.CUT_MIN, scene.CUT_MAX))

        cv.bind('<Button-1>', start_drag)
        cv.bind('<B1-Motion>', move_cut)
        cv.bind('<ButtonRelease-1>', stop_drag)
        cv.bind('<Motion>', hover)
        confirm_btn = tk.Button(dialog, text='确定切牌', command=begin, width=18,
                                font=('微软雅黑', 13, 'bold'), bg='#d8bd4b', fg='#15110d',
                                activebackground='#ead56f', relief=tk.FLAT, bd=0, pady=8)
        confirm_btn.pack(pady=(4, 12))
        dialog.bind('<Return>', random_confirm)
        dialog.bind('<KP_Enter>', random_confirm)
        schedule(20, dialog.focus_force)
        dialog.protocol('WM_DELETE_WINDOW', begin)
        try:
            self.wait_window(dialog)
        finally:
            close_dialog()
        return int(result[0] if result[0] is not None else
                   state['confirmed'] if state['confirmed'] is not None else selected['value'])


    CUT_NOTICE_HOLD_MS = 3000
    CUT_NOTICE_FADE_MS = 360

    def _cut_card_notice_due(self):
        offset = self._round_cut_card_offset
        return (offset is not None and not self._cut_notice_seen
                and self.revealed >= offset)

    def _clear_cut_card_notice(self):
        popup = self._cut_notice_popup
        self._cut_notice_popup = None
        if popup is not None:
            try:
                popup.destroy()
            except tk.TclError:
                pass
        self.canvas.delete('cut_card_notice')
        self.canvas.delete('cut_card_popup')
        self._cut_notice_active = False

    def _show_cut_card_notice(self, on_complete):
        """Withdraw marker, fade in, hold 3s, fade out, slide down, resume.

        The continuation is the only way back into the paused deal, so neither
        settlement nor squeeze bindings can run while this sequence is active.
        """
        if self._closed or self._cut_notice_active:
            return
        self._cut_notice_seen = True
        self._cut_notice_active = True
        c = self.canvas
        previous_phase = self._note
        self._note = "取出黄色切牌 · 本局完成后换靴"
        x0, y0, x1, y1 = 356, 8, 892, 226
        centre_x, centre_y = (x0+x1)/2, (y0+y1)/2+10
        tag = ('cut_card_notice', 'animation')
        shadow = c.create_oval(0, 0, 0, 0, fill='#090f13', outline='', tags=tag)
        side = c.create_polygon(0, 0, 0, 0, fill='#a77f0b', outline='#84650b', tags=tag)
        face = c.create_polygon(0, 0, 0, 0, fill='#f4d640', outline='#b18c18', width=2, tags=tag)
        shine = c.create_line(0, 0, 0, 0, fill='#fff4a3', width=3, tags=tag)
        inner = c.create_polygon(0, 0, 0, 0, fill='', outline='#dfb727', width=1, tags=tag)

        def paint(cy, amount=1.0):
            half_w, half_h = 51*(.32+.68*amount), 76
            skew = 13*(1-amount)+4
            points = [(centre_x-half_w, cy-half_h+skew),
                      (centre_x+half_w, cy-half_h),
                      (centre_x+half_w, cy+half_h-skew),
                      (centre_x-half_w, cy+half_h)]
            flatten = lambda pts: [v for p in pts for v in p]
            c.coords(side, *flatten([(x+5, y+4) for x, y in points]))
            c.coords(face, *flatten(points))
            c.coords(shine, *flatten(points[:2]))
            c.coords(inner, *flatten([(centre_x+(x-centre_x)*.87,
                                       cy+(y-cy)*.90) for x, y in points]))
            c.coords(shadow, centre_x-half_w-6, cy+half_h+7,
                     centre_x+half_w+12, cy+half_h+20)

        def animate(duration, callback, completed):
            steps = max(1, int(duration/16))
            def frame(step=0):
                if self._closed or not self._cut_notice_active:
                    return
                callback(BaccaratCutScene.ease(step/steps))
                if step < steps:
                    self._queue_animation(round(duration/steps), frame, step+1)
                else:
                    completed()
            frame()

        def resume():
            if self._closed:
                return
            self._clear_cut_card_notice()
            self._note = previous_phase
            on_complete()

        def slide_away():
            if self._closed:
                return
            popup = self._cut_notice_popup
            self._cut_notice_popup = None
            if popup is not None:
                popup.destroy()
            c.delete('cut_card_popup')
            animate(560, lambda t: paint(centre_y+(H+100-centre_y)*t), resume)

        def show_popup():
            if self._closed:
                return
            popup = tk.Toplevel(self.winfo_toplevel())
            self._cut_notice_popup = popup
            popup.withdraw()
            popup.overrideredirect(True)
            popup.transient(self.winfo_toplevel())
            popup.configure(bg='#d2b766')
            tk.Label(popup, text='下轮更换牌靴', font=('微软雅黑', 17, 'bold'),
                     bg='#163c37', fg='#fff0b8', padx=24, pady=17).pack(padx=1, pady=1)
            popup.update_idletasks()
            pw, ph = popup.winfo_reqwidth(), popup.winfo_reqheight()
            px = int(c.winfo_rootx()+centre_x-pw/2)
            py = int(c.winfo_rooty()+centre_y-ph/2)
            popup.geometry(f'{pw}x{ph}+{max(0, px)}+{max(0, py)}')
            native_alpha = True
            try:
                popup.attributes('-alpha', 0.0)
            except tk.TclError:
                native_alpha = False
            if native_alpha:
                popup.deiconify()
                popup.lift()
            else:
                # Some Tk window managers lack per-window opacity.
                popup.destroy()
                self._cut_notice_popup = None
                c.create_rectangle(centre_x-145, centre_y-34, centre_x+145, centre_y+34,
                                   fill='#f4d640', outline='', tags='cut_card_popup')
                c.create_text(centre_x, centre_y, text='下轮更换牌靴',
                              font=('微软雅黑', 17, 'bold'), fill='#f4d640',
                              tags=('cut_card_popup', 'cut_notice_text'))

            def opacity(amount):
                if native_alpha:
                    popup.attributes('-alpha', amount)
                else:
                    # A color fade keeps the fallback nonblocking and readable.
                    def blend(a, b):
                        av, bv = c.winfo_rgb(a), c.winfo_rgb(b)
                        return '#'+''.join(f'{round((x+(y-x)*amount)/257):02x}'
                                           for x, y in zip(av, bv))
                    plate = c.find_withtag('cut_card_popup')[0]
                    c.itemconfigure(plate, fill=blend('#f4d640', '#163c37'))
                    c.itemconfigure('cut_notice_text', fill=blend('#f4d640', '#fff0b8'))

            def fade_out():
                animate(self.CUT_NOTICE_FADE_MS, lambda t: opacity(1-t), slide_away)

            # The full three seconds start AFTER the popup is fully visible.
            animate(self.CUT_NOTICE_FADE_MS, opacity,
                    lambda: self._queue_animation(self.CUT_NOTICE_HOLD_MS, fade_out))

        # Use the same centre-top shoe origin as normal card entrances.
        paint(-160, 0)
        animate(560, lambda t: paint(-160+(centre_y+160)*t, t), show_popup)


    def _refresh_scoreboard(self):
        self.canvas.delete("scoreboard")
        self._draw_scoreboard()
        self._fit_items("scoreboard")

    def _queue_animation(self, delay, callback, *args):
        if not self._closed:
            self._job = self.after(delay, callback, *args)

    def start_new_shoe_cut(self, second=False):
        """先独占牌靴，再显示移植的切牌场景；保存每一步烧牌进度。"""
        self._job = None
        if self._closed or self.round_state not in ("betting", "preparing_shoe"):
            return
        self.round_state = "preparing_shoe"
        self._note = "正在准备牌靴"
        self._paint()
        try:
            preparing = self.table.prepare_shoe()
        except ShoeBusy as exc:
            self._note = str(exc)
            self._paint()
            self._job = self.after(250, self.start_new_shoe_cut, second)
            return
        except BetError as exc:
            self.round_state = "betting"
            self._note = str(exc)
            self._paint()
            return
        except Exception as exc:
            self._storage_error(exc)
            return
        if not preparing:
            self.round_state = "betting"
            self._note = ""
            self._paint()
            return
        try:
            shoe = self.table.shoe
            if not shoe.cut_complete:
                self._pending_cut_threshold = shoe.cut_threshold
                position = self._show_cut_dialog(second)
                if self._closed:
                    return
                shoe.cut_shoe(position, self._pending_cut_threshold)
                self._pending_cut_threshold = None
                self.store.remember_shoe(shoe)
            self._cut_notice_seen = False
            self._round_cut_card_offset = None
            self.round_state = "burning"
            self._note = "切牌完成 · 烧牌"
            self._paint()
            self._start_initial_burn_animation()
        except Exception as exc:
            if not self._closed:
                self._storage_error(exc)

    def _burn_card_position(self, total, index=0):
        """沿用百家乐的指示牌与背牌扇形排列，适配四张公共牌区域。"""
        spread = 20
        width = 2 * CARD_W + 16 + max(0, total-1) * spread
        left = (356 + 892 - width) / 2
        return (left if index == 0 else left + CARD_W + 16 + (index-1)*spread, 54)

    def _render_burn_cards(self):
        self.canvas.delete("burn_card")
        shoe = self.table.shoe
        if shoe.current_index == 0:
            return
        x, y = self._burn_card_position(shoe.burn_count)
        width, face = CARD_W, shoe.indicator
        motion = self._burn_motion
        if motion is not None and motion[0] == "indicator":
            _, x, y, width, face = motion
        self._draw_card(0, x, y, face, width, tags=("burn_card", "burn_indicator"))
        for index in range(self._burn_visual_count):
            x, y = self._burn_card_position(shoe.burn_count, index+1)
            self._draw_card(index+1, x, y, None, tags=("burn_card", f"burn_{index}"))
        if motion is not None and motion[0] == "back":
            _, index, x, y = motion
            self._draw_card(index+1, x, y, None, tags=("burn_card", "burn_moving_back"))
        self._fit_items("burn_card")

    def _start_initial_burn_animation(self):
        """百家乐流程：取首张，翻开，按其点值额外发出背面烧牌。"""
        shoe = self.table.shoe
        try:
            if shoe.current_index == 0:
                shoe.draw_card()
                self.store.remember_shoe(shoe)
        except Exception as exc:
            self._storage_error(exc)
            return
        self._burn_visual_count = shoe.current_index-1
        target_x, target_y = self._burn_card_position(shoe.burn_count)
        start_x, start_y = CARD_DEAL_ORIGIN
        def move(step=0):
            self._job = None
            if self._closed or self.round_state != "burning":
                return
            ratio = min(1.0, step/30.0)
            self._burn_motion = ("indicator", start_x+(target_x-start_x)*ratio,
                                 start_y+(target_y-start_y)*ratio, CARD_W, None)
            self._render_burn_cards()
            if step < 30:
                self._queue_animation(10, move, step+1)
            else:
                self._flip_burn_card(shoe.indicator)
        move()

    def _flip_burn_card(self, card, step=0):
        self._job = None
        if self._closed or self.round_state != "burning":
            return
        steps, half = 12, 6
        total = self.table.shoe.burn_count
        x, y = self._burn_card_position(total)
        if step > steps:
            self._burn_motion = None
            self._note = f"烧牌指示：{SYMBOL[card[0]]}{card[1]} · 额外烧 {total} 张"
            self._paint()
            self._queue_animation(500, self._burn_back_cards, total,
                                  self.table.shoe.current_index-1)
            return
        ratio = 1-step/half if step <= half else (step-half)/half
        width = max(1, CARD_W*ratio)
        self._burn_motion = ("indicator", x+(CARD_W-width)/2, y, width,
                             None if step <= half else card)
        self._render_burn_cards()
        self._queue_animation(20, self._flip_burn_card, card, step+1)

    def _burn_back_cards(self, total, index):
        self._job = None
        if self._closed or self.round_state != "burning":
            return
        if index >= total:
            self._queue_animation(700, self._finish_initial_burn)
            return
        try:
            self.table.shoe.draw_card()
            self.store.remember_shoe(self.table.shoe)
        except Exception as exc:
            self._storage_error(exc)
            return
        start_x, start_y = CARD_DEAL_ORIGIN
        target_x, target_y = self._burn_card_position(total, index+1)
        def move(step=0):
            self._job = None
            if self._closed or self.round_state != "burning":
                return
            ratio = min(1.0, step/24.0)
            self._burn_motion = ("back", index, start_x+(target_x-start_x)*ratio,
                                 start_y+(target_y-start_y)*ratio)
            self._render_burn_cards()
            if step < 24:
                self._queue_animation(10, move, step+1)
            else:
                self._burn_visual_count = index+1
                self._burn_motion = None
                self._render_burn_cards()
                self._queue_animation(100, self._burn_back_cards, total, index+1)
        move()

    def _finish_initial_burn(self):
        self._job = None
        if self._closed or self.round_state != "burning":
            return
        try:
            self.table.finish_shoe_preparation()
        except Exception as exc:
            self._storage_error(exc)
            return
        self._burn_motion = None
        self.canvas.delete("burn_card")
        self.round_state = "betting"
        self._note = ""
        self._paint()

    def _open_betting(self):
        if self._closed:
            return
        self._cancel_job()
        try:
            self.table.next_round()
        except Exception as exc:
            self._storage_error(exc)
            return
        self.round_state = "betting"
        self.revealed = 0
        self._card_motion = None
        self._photos.clear()
        self._images.clear()
        self._chip_cells.clear()
        self._visual_chips.clear()
        self._sweep_offset = 0
        self._note = ""
        self._hover_cell = None
        self._paint()
        if not self.table.shoe.ready:
            self.round_state = "preparing_shoe"
            self.start_new_shoe_cut()

    def start_game(self):
        if self._closed:
            return
        if self.round_state == "credit_pending":
            self._complete_chip_return()
            return
        if self.round_state != "betting":
            return
        self.round_state = "closing_bets"
        self._note = ""
        if self._transfers:
            self._sync_chrome()
        else:
            self._deal_when_ready()

    def _deal_when_ready(self):
        self._job = None
        if self._closed or self.round_state != "closing_bets":
            return
        try:
            self.table.deal()
        except ShoeBusy as exc:
            if self._note != str(exc):
                self._note = str(exc)
                self._paint()
            self._job = self.after(250, self._deal_when_ready)
            return
        except ShoePreparationRequired:
            self.round_state = "preparing_shoe"
            self.start_new_shoe_cut()
            return
        except BetError as exc:
            if self.table.phase != "betting":
                self._storage_error(exc)
                return
            self.round_state = "betting"
            self._note = str(exc)
            self._paint()
            return
        except Exception as exc:
            self._storage_error(exc)
            return
        if self.current_bets:
            self._last_chip_cells = self._chip_cells.copy()
        self.round_state = "dealing"
        self._note = ""
        self._card_motion = ("deal", 0, 0)
        self._round_cut_card_offset = self.table.round_cut_card_offset
        self._cut_notice_seen = False
        self._paint()
        self._animate_card("deal", 0, 0)

    def _animate_card(self, phase, index, step):
        """每张牌先从发牌点到位，再从中线翻开，翻完才发下一张。"""
        self._job = None
        if self._closed or self.round_state != "dealing":
            return
        if (phase == "deal" and step == 0 and self._cut_card_notice_due()):
            self._show_cut_card_notice(lambda: self._animate_card(phase, index, step))
            return
        self._card_motion = (phase, index, step)
        self._render_cards()
        if phase == "deal" and step < 6:
            delay = round(self.DEAL_MOVE_MS*(step+1)/6) - round(self.DEAL_MOVE_MS*step/6)
            following = (phase, index, step+1)
        elif phase == "deal":
            delay = round(self.DEAL_CARD_MS) - round(self.DEAL_MOVE_MS)
            following = ("flip", index, 0)
        elif step < 10:
            delay, following = self.FLIP_MS, (phase, index, step+1)
        else:
            self.revealed = index+1
            self._refresh_scoreboard()
            if self.revealed == len(CARD_POSITIONS):
                self._card_motion = None
                if self._cut_card_notice_due():
                    self._show_cut_card_notice(self._begin_payout)
                else:
                    self._begin_payout()
                return
            delay, following = 0, ("deal", index+1, 0)
        self._job = self.after(delay, self._animate_card, *following)

    def _stop_result_flash(self):
        if self._result_flash_job is not None:
            self.after_cancel(self._result_flash_job)
            self._result_flash_job = None
        self._result_flash_state = False
        self._result_flash_spot_ids = frozenset()
        self.canvas.itemconfigure("result_flash", state="hidden")

    def _result_flash_tick(self):
        self._result_flash_job = None
        if self._closed or self.round_state != "result":
            return
        self._result_flash_state = not self._result_flash_state
        self.canvas.itemconfigure("result_flash", state="normal" if self._result_flash_state else "hidden")
        if self._result_flash_state:
            self._flash_count += 1
        elif self._flash_count == self.FLASH_COUNT:
            self._return_winnings()
            return
        self._result_flash_job = self.after(self.FLASH_INTERVAL_MS, self._result_flash_tick)

    def _run_transfers(self, transfers, complete):
        """使用 UTH 的缓入缓出曲线并行移动筹码，以 16ms 为一帧。"""
        self._transfers = tuple(transfers)
        self._transfer_positions = {i: t.start for i, t in enumerate(transfers)}
        self._paint()
        if not transfers:
            complete()
            return
        started = time.monotonic()
        longest = max(t.duration for t in transfers)

        def frame():
            self._job = None
            if self._closed:
                return
            elapsed = (time.monotonic()-started)*1000
            for i, t in enumerate(self._transfers):
                if i not in self._transfer_positions:
                    continue
                fraction = min(1, elapsed/t.duration)
                eased = fraction*fraction*(3-2*fraction)
                x = t.start[0] + (t.target[0]-t.start[0])*eased
                y = t.start[1] + (t.target[1]-t.start[1])*eased
                old_x, old_y = self._transfer_positions[i]
                tag = f"transfer_{i}"
                self.canvas.move(tag, (x-old_x)*self.scale_factor, (y-old_y)*self.scale_factor)
                self._transfer_positions[i] = (x, y)
                if fraction == 1 and t.role == "loss":
                    self.canvas.delete(tag)
                    del self._transfer_positions[i]
            if elapsed < longest:
                self._job = self.after(max(1, min(16, math.ceil(longest-elapsed))), frame)
            else:
                self._transfers = ()
                self._transfer_positions.clear()
                self.canvas.delete("moving_chips")
                complete()

        self._job = self.after(16, frame)

    def _begin_payout(self):
        self.round_state = "settling"
        self._last_win = self.table.settlement.total_return
        # 输注回到 UTH 的庄家收筹点，净赢送到本金左上方。全部到位才亮第一下。
        transfers = []
        self._visual_chips.clear()
        for row in self.table.settlement.bets:
            key, center = row.spot_id, self._stake_center(row.spot_id)
            if row.returned == 0:
                transfers.append(ChipTransfer(key, "loss", row.stake, center, HOUSE_CHIP_POS, 280))
            else:
                self._visual_chips[key, "stake"] = row.stake, center
                if row.net_profit > 0:
                    target = (center[0]-32, center[1]-30)
                    transfers.append(ChipTransfer(key, "profit", row.net_profit, HOUSE_CHIP_POS, target, 440))

        def done():
            for t in transfers:
                if t.role == "profit":
                    self._visual_chips[t.key, t.role] = t.amount, t.target
            self.round_state = "result"
            self._result_flash_spot_ids = self.table.outcome.winners
            self._result_flash_state = False
            self._flash_count = 0
            self._paint()
            self._result_flash_tick()

        self._run_transfers(transfers, done)

    def _return_winnings(self):
        """闪烁结束后沿用 UTH 的 600ms 回筹动画，全部到位才入账并结束本局。"""
        if self._closed or self.round_state != "result":
            return
        self._stop_result_flash()
        self._cancel_job()
        chips = tuple(self._visual_chips.items())
        self._visual_chips.clear()
        self.round_state = "returning"
        transfers = []
        count = len(chips)
        for index, ((key, role), (amount, origin)) in enumerate(chips):
            # 直接采用 UTH 的 _rack_position(index, total) 落点公式。
            target = (575 + (index-(count-1)/2)*min(28, 140/max(1, count-1)), 674)
            transfers.append(ChipTransfer(key, role, amount, origin, target, 600))

        def arrived():
            if self._closed or self.round_state != "returning":
                return
            for (tag, _chip), transfer in zip(chips, transfers):
                self._visual_chips[tag] = transfer.amount, transfer.target
            self._paint()
            self._complete_chip_return()

        self._run_transfers(transfers, arrived)

    def _complete_chip_return(self):
        if self.round_state not in ("returning", "credit_pending"):
            return
        try:
            self.table.collect_return()
        except Exception as exc:
            self.round_state = "credit_pending"
            self._paint()
            messagebox.showerror("入账未完成", str(exc), parent=self.root)
            return
        self._open_betting()


    def _storage_error(self, exc):
        self._cancel_job()
        self._stop_result_flash()
        self.round_state = ("credit_pending" if self.table.phase in ("locked", "awaiting_collection")
                            and self.table._round_id is not None else "error")
        self._paint()
        messagebox.showerror("牌桌错误", str(exc), parent=self.root)

    def _instruction_pages(self):
        spots = BET_SPOTS

        def odds(key):
            return f'{spots[key]["payout"]}:1'

        straight_rows = [(str(n), odds(f"straight_{n}")) for n in (0, 7, 8)]
        straight_rows.append(("9–18（各自单押）", odds("straight_9")))
        straight_rows.extend((str(n), odds(f"straight_{n}")) for n in range(19, 31))
        rows = [(spots[key]["label"], "、".join(sorted(spots[key]["numbers"], key=int)), odds(key))
                for key in (TOP, MIDDLE, BOTTOM)]
        limits = [(p.name, f"${p.minimum:,}", f"${p.outside_max:,}", f"${p.number_max:,}")
                  for p in (NORMAL, HIGH_LIMITS)]
        return [
            ("基本玩法", "用四张公共牌的点数、颜色和花色决定各区域的输赢。", [
                ("一局怎样进行", "", [
                    ("下注", "选择筹码，点击格内下注。可以同时押多个区域，下注不限时。"),
                    ("开牌", "点击「开牌」或按回车封盘。从左到右发四张公共牌，每一张到位并翻开后再发下一张。"),
                    ("计分", "将四张牌的点数直接相加，总点数为 0 至 36。0 点算双。"),
                    ("派彩", "庄家先收走输注，并把净赢筹码派到中奖本金左上方。筹码到位后，中奖格闪白三次。")],
                 [("单张牌的点值", ("牌面", "点值"), [("A", "1"), ("2–9", "按牌面"), ("10、J、Q、K", "0")])], None),
                ("牌靴", "四副标准牌，共 208 张。", [
                    ("切牌与烧牌", "切牌标记按初始 208 张计算，在靴尾预留 36–47 张。可拖动黄色卡片选择切点或按 Enter 随机切牌；切牌后翻开第一张指示牌，再按其烧牌值额外烧牌。"),
                    ("换靴", "烧牌时 A 算 1，2–9 按牌面，10、J、Q、K 算 10。遇切牌位置后发完本局四张，下局换靴。")], [], None)]),
            ("下注区图解", "各格的文字标出下注项目，数字注放在数字格内。", [
                ("桌面落点", "", [
                    ("数字", "0 和 7–30 可以单押。点击 1–6 任一数字或上方「小」都是同一笔组合注；31–36 与「大」同理。合计筹码在最后落注的格心。"),
                    ("花色与颜色", "方块、红桃、梅花、黑桃各要求四张均为该花色。押红或黑只需四张同色，可以混合该颜色的两种花色。")],
                 [], "felt"),
                ("三条横排", "0 不属于任何一排。", [], [("各排覆盖点数", ("下注", "总点数", "净赔率"), rows)], None)]),
            ("赔率与限额", "赔率为净赢倍数，每一格独立计算。", [
                ("下注上限", "每个下注格独立累计，点击左上限额表切换档位。", [
                    ("内注最高", "仅用于数字 0 和 7–30 的每一个单押格。"),
                    ("外注最高", "用于其余每个下注格：小、大、三条横排、单双、红黑、四个花色及扑克顺序。")],
                 [("各档限额", ("档位", "每注最低", "外注最高", "内注最高"), limits),
                  ("筹码面额", ("档位", "可选筹码"), [(p.name, "、".join(f"{n:,}" for n in p.chips)) for p in (NORMAL, HIGH_LIMITS)])], None),
                ("数字区", "", [], [("六数字组合", ("下注", "净赔率"), [(spots[k]["label"], odds(k)) for k in (LOW, HIGH)]),
                                      ("单押总点数", ("总点数", "净赔率"), straight_rows)], None),
                ("扑克顺序", "红与黑之间的独立外注，四张牌命中任一牌型即可获胜，只赔付实际最高档。", [
                    ("同点数", "按相同牌面判定，10、J、Q、K 是不同牌面。四张同花点数是四张花色与牌面均相同的牌。"),
                    ("顺子", "四张连续且互异的牌面，不限制发牌顺序。A 可作 A234 或 JQKA，不允许 QKA2 等循环。")],
                 [("最高档实际类别", ("实际牌型", "净赔率"),
                   [(label, f"{payout:,}:1") for key, label, payout in POKER_PAYOUTS])], None),
                ("外区", "", [], [("外区净赔率", ("下注", "中奖条件", "净赔率"), [
                    ("单 / 双", "四张总点数为奇数 / 偶数，0 点属于双", odds(EVEN)),
                    ("红 / 黑", "四张牌均为所押颜色", odds(RED)),
                    ("方块 / 红桃 / 梅花 / 黑桃", "四张牌均为所押花色", odds("suit_hearts")),
                    ("上排 / 中排 / 下排", "总点数位于所押横排", odds(TOP))])], None)]),
            ("筹码与操作", "从屏幕下方选择筹码，手动决定何时开牌。", [
                ("下注阶段", "", [
                    ("放入或撤回", "左键点击下注格，筹码从选中的面额飞到格心。右键撤回整格，「清除」撤回全部，「重复下注」恢复上局的下注组合。"),
                    ("小与大组合注", "点击 1–6 任一数字，筹码合并到「小 1–6」格；点击 31–36 任一数字，筹码合并到「大 31–36」格。各组合内共用一份外注上限。"),
                    ("达到上限", "筹码面额超过本格剩余额度时，仅放入剩余可押金额；余额不足时保留原注。"),
                    ("切换档位", "点击左上限额表可切换普通档与高额档。进入高额档须输入本机当前时间的四位时分。切档后清空本局及可重复的上局下注。")], [], None),
                ("结算之后", "", [
                    ("总点数与最近点数", "每张公共牌完全翻开后，立即显示已完全开牌的累计点数；未开牌不计入。最近六局从左到右排列，金框标出最新一局。JSON 保留累计局数及最近10局。"),
                    ("自动回筹", "第三次闪白结束后，中奖本金和净赢筹码先返回底部筹码区，全部到位并成功入账后再开放下一局下注。遇黄色切牌则先切新靴并烧牌。"),
                    ("入账与离桌", "正常结算后自动进入下一局。若写入账户失败，「开牌」临时显示「重试入账」；重试不会重复派彩。结算后直接离桌也会收到本局返还。")], [], None)]),
            ("结算示例", "中奖含本金返还＝实押金额 ×（净赔率＋1）。本局净额＝所有返还之和减去实押总额。", [
                ("相同点数，不同花色", "", [], [("中奖区域", ("四张公共牌", "点数", "中奖区域"), [
                    ("A♥、2♦、3♥、9♦", "15", "15、单、下排、红"),
                    ("A♥、2♥、3♥、9♥", "15", "15、单、下排、红、红桃"),
                    ("7♠、8♣、9♠、6♣", "30", "30、双、下排、黑"),
                    ("10♥、J♦、Q♣、K♠", "0", "0、双")])], None),
                ("实押与返还", "", [], [("金额示例", ("下注", "结果", "含本金返还", "本局净额"), [
                    ("红 $10", "四张均为红牌", "$130", "+$120"),
                    ("0 和双各 $10", "总点数 0", "$1,010＋$20＝$1,030", "+$1,010"),
                    ("大 31–36 $10", "总点数 30", "$0", "−$10")])], None)])]


    def show_game_instructions(self):
        """参考卡片式说明布局；所有赔率、返还与结算示例均用表格显示。"""
        import tkinter as tk
        import tkinter.font as tkfont

        current = getattr(self, '_instruction_window', None)
        if current is not None:
            try:
                if current.winfo_exists():
                    current.lift()
                    current.focus_set()
                    return
            except tk.TclError:
                pass

        parent = self.winfo_toplevel()
        parent.update_idletasks()
        dialog = tk.Toplevel(parent)
        self._instruction_window = dialog
        title = 'Po Kar Dette · 完整图解玩法'
        dialog.title(title)
        dialog.transient(parent)
        BG, HEADER, SIDEBAR = '#faf5e8', '#f1e7cd', '#f2e8d0'
        PANEL, PANEL_2, BORDER = '#fffdf7', '#f5ecd6', '#c9b88a'
        GOLD, GOLD_BAR, TEXT, MUTED = '#a8842c', '#e7d36c', '#3a2f1e', '#7a6a50'
        font_name = FONT
        dialog.configure(bg=BG)
        screen_w, screen_h = parent.winfo_screenwidth(), parent.winfo_screenheight()
        width, height = min(1000, screen_w - 30), min(670, screen_h - 50)
        x = max(0, min(screen_w - width, parent.winfo_rootx() + (parent.winfo_width() - width) // 2))
        y = max(0, min(screen_h - height, parent.winfo_rooty() + (parent.winfo_height() - height) // 2))
        dialog.geometry(f'{width}x{height}+{x}+{y}')
        dialog.resizable(False, False)

        manual_pages = self._instruction_pages()

        def close_dialog():
            if getattr(self, '_instruction_window', None) is dialog:
                self._instruction_window = None
            dialog.destroy()

        header = tk.Frame(dialog, bg=HEADER)
        header.pack(fill=tk.X)
        tk.Button(header, text='关闭  ESC', command=close_dialog,
                  font=(font_name, 13, 'bold'), bg='#e8dcc0', fg=TEXT,
                  activebackground=GOLD_BAR, relief=tk.FLAT, bd=0,
                  padx=14, pady=10, cursor='hand2').pack(side=tk.RIGHT, padx=20)
        title_box = tk.Frame(header, bg=HEADER)
        title_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=24, pady=10)
        tk.Label(title_box, text=title, font=(font_name, 20, 'bold'),
                 fg=GOLD, bg=HEADER, anchor='w').pack(fill=tk.X)
        tk.Label(title_box, text='玩法 · 下注 · 派奖 · 图解 · 结算示例',
                 font=(font_name, 12), fg=MUTED, bg=HEADER, anchor='w').pack(fill=tk.X, pady=(4, 0))
        tk.Frame(dialog, bg=GOLD_BAR, height=3).pack(fill=tk.X)
        body = tk.Frame(dialog, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)
        sidebar = tk.Frame(body, bg=SIDEBAR, width=180)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text='说明目录', font=(font_name, 16, 'bold'),
                 fg=GOLD, bg=SIDEBAR, anchor='w').pack(fill=tk.X, padx=18, pady=(17, 10))
        host = tk.Frame(body, bg=BG)
        host.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(host, bg=BG, highlightthickness=0, yscrollincrement=28)
        ys = tk.Scrollbar(host, orient=tk.VERTICAL, command=canvas.yview)
        xs = tk.Scrollbar(host, orient=tk.HORIZONTAL, command=canvas.xview)
        canvas.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        canvas.grid(row=0, column=0, sticky='nsew')
        ys.grid(row=0, column=1, sticky='ns')
        xs.grid(row=1, column=0, sticky='ew')
        host.grid_rowconfigure(0, weight=1)
        host.grid_columnconfigure(0, weight=1)
        content = tk.Frame(canvas, bg=BG)
        content_window = canvas.create_window((0, 0), window=content, anchor='nw')
        content.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(content_window, width=max(760, event.width)))

        def label(parent_frame, value, size=13, bold=False, color=MUTED, bg=PANEL):
            widget = tk.Label(parent_frame, text=value, font=(font_name, size, 'bold' if bold else 'normal'),
                              fg=color, bg=bg, anchor='w', justify=tk.LEFT, wraplength=700)
            widget.pack(fill=tk.X)
            return widget

        def add_rule(parent_frame, heading, detail):
            row = tk.Frame(parent_frame, bg=PANEL)
            row.pack(fill=tk.X, padx=16, pady=7)
            tk.Frame(row, bg=GOLD_BAR, width=5).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 11))
            box = tk.Frame(row, bg=PANEL)
            box.pack(side=tk.LEFT, fill=tk.X, expand=True)
            label(box, heading, 14, True, TEXT)
            label(box, detail)

        def add_table(parent_frame, heading, headers, rows):
            block = tk.Frame(parent_frame, bg=PANEL_2, highlightbackground=BORDER, highlightthickness=1)
            block.pack(fill=tk.X, padx=16, pady=8)
            tk.Label(block, text=heading, font=(font_name, 14, 'bold'),
                     fg=TEXT, bg=GOLD_BAR, anchor='w', justify=tk.LEFT,
                     wraplength=670, padx=10, pady=8).pack(fill=tk.X)
            grid = tk.Frame(block, bg=BORDER)
            grid.pack(fill=tk.X)
            matrix = [headers] + rows
            count = len(headers)
            table_font = tkfont.Font(family=font_name, size=12)
            preferences = [max(55, min(260, max(table_font.measure(line)
                           for row in matrix for line in str(row[col]).split('\n'))))
                           for col in range(count)]
            available = 694
            remainder = available - 70 * count
            widths = [70 + remainder * value // sum(preferences) for value in preferences]
            widths[-1] += available - sum(widths)
            for col, column_width in enumerate(widths):
                grid.grid_columnconfigure(col, minsize=column_width, weight=1)
            for r, row in enumerate(matrix):
                for col, value in enumerate(row):
                    bg = GOLD_BAR if r == 0 else (PANEL if r % 2 else '#fbf6e9')
                    tk.Label(grid, text=value, font=(font_name, 12, 'bold' if r == 0 else 'normal'),
                             fg=TEXT if r == 0 else MUTED, bg=bg, anchor='w', justify=tk.LEFT,
                             wraplength=widths[col] - 16, padx=7, pady=7,
                             relief=tk.SOLID, borderwidth=1).grid(row=r, column=col, sticky='nsew')

        def draw_illustration(parent_frame, illustration):
            # 图解与桌面共用格子数据，保持组合注、横排与实桌落点一一对应。
            cv = tk.Canvas(parent_frame, width=700, height=235, bg="#20593e",
                           highlightbackground=BORDER, highlightthickness=1)
            cv.pack(fill=tk.X, padx=16, pady=(4, 10))
            def redraw(event):
                cv.delete("all")
                width = max(1, event.width-12)
                for cell in FELT_CELLS:
                    left, right = 6+width*cell.left, 6+width*cell.right
                    top, bottom = 5+(cell.top-TAB_TOP)*.51, 5+(cell.bottom-TAB_TOP)*.51
                    fill = COLOR_FIELDS.get(cell.key, LIGHT_FELT if cell.key in (LOW, HIGH) else FELT)
                    cv.create_rectangle(left, top, right, bottom, fill=fill, outline=EDGE)
                    caption = str(cell.number) if cell.number is not None else BET_SPOTS[cell.key]["label"]
                    cv.create_text((left+right)/2, (top+bottom)/2, text=caption,
                                   font=(font_name, 11, "bold"), fill="#fff0b8")
            cv.bind("<Configure>", redraw)


        def render_page(index):
            for child in content.winfo_children():
                child.destroy()
            for idx, button in enumerate(nav_buttons):
                button.configure(bg='#e6d9b9' if idx == index else SIDEBAR,
                                 fg=GOLD if idx == index else MUTED)
            page_title, subtitle, cards = manual_pages[index]
            top = tk.Frame(content, bg=BG)
            top.pack(fill=tk.X, padx=18, pady=(16, 7))
            label(top, page_title, 20, True, GOLD, BG)
            label(top, subtitle, bg=BG)
            for card_title, card_subtitle, rules, tables, illustration in cards:
                card = tk.Frame(content, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
                card.pack(fill=tk.X, padx=10, pady=7)
                head = tk.Frame(card, bg=PANEL)
                head.pack(fill=tk.X, padx=16, pady=(12, 6))
                label(head, card_title, 16, True, GOLD)
                if card_subtitle:
                    label(head, card_subtitle)
                if illustration:
                    draw_illustration(card, illustration)
                for heading, detail in rules:
                    add_rule(card, heading, detail)
                for heading, headers, rows in tables:
                    add_table(card, heading, headers, rows)
                tk.Frame(card, bg=PANEL, height=8).pack(fill=tk.X)
            content.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox('all'))
            canvas.yview_moveto(0)
            canvas.xview_moveto(0)

        nav_buttons = []
        for index, (page_title, _subtitle, _cards) in enumerate(manual_pages):
            button = tk.Button(sidebar, text=page_title, command=lambda i=index: render_page(i),
                               font=(font_name, 14), fg=MUTED, bg=SIDEBAR,
                               activebackground='#e8d49a', activeforeground=GOLD,
                               relief=tk.FLAT, bd=0, anchor='w', padx=18, pady=10, cursor='hand2')
            button.pack(fill=tk.X)
            nav_buttons.append(button)

        def on_mousewheel(event):
            number = getattr(event, 'num', None)
            delta = getattr(event, 'delta', 0)
            if number in (4, 5):
                steps = -1 if number == 4 else 1
            elif delta:
                steps = max(1, int(abs(delta) / 120)) * (-1 if delta > 0 else 1)
            else:
                return
            canvas.yview_scroll(steps, 'units')
            return 'break'

        dialog.bind('<MouseWheel>', on_mousewheel)
        dialog.bind('<Button-4>', on_mousewheel)
        dialog.bind('<Button-5>', on_mousewheel)
        dialog.bind('<Escape>', lambda _e: close_dialog())
        dialog.protocol('WM_DELETE_WINDOW', close_dialog)
        render_page(0)
        dialog.focus_set()

    def _cancel_jobs(self):
        """沿用 UTH 的销毁清理方式，取消本页尚未执行的动画回调。"""
        for name in ("_job", "_result_flash_job"):
            job = getattr(self, name, None)
            if job is not None:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
                setattr(self, name, None)

    def _unbind_enter(self):
        """仅移除本页追加的回车绑定，不接管或重写宿主的事件设置。"""
        for sequence, binding in self._enter_bindings.items():
            if binding:
                try:
                    self.winfo_toplevel().unbind(sequence, binding)
                except tk.TclError:
                    pass
        self._enter_bindings.clear()

    def _on_destroy(self, event):
        if event.widget is self:
            self._closed = True
            self._cancel_jobs()
            self._unbind_enter()
            if self.store:
                self.store.release()

    def _end_session(self, return_balance=False):
        self._cancel_job()
        self._stop_result_flash()
        if self.table.phase == "awaiting_collection":
            self.table.collect_return()
        elif self.table.phase == "preparing_shoe":
            self.store.remember_shoe(self.table.shoe)
            if return_balance:
                self.store.persist_balance()
            self.store.release()
        elif self.table.phase == "locked":
            self.table.collect_return()
            if return_balance and self.table.phase == "locked":
                self.store.persist_balance()
            self.store.release()
        else:
            if self.table.phase == "betting":
                self.table.clear_bets()
            if return_balance:
                self.store.sync_for_exit()

    def _close_windows(self):
        if self._cut_dialog is not None:
            self._cut_dialog._close_cut_scene()
        self._clear_cut_card_notice()
        if self._instruction_window is not None and self._instruction_window.winfo_exists():
            self._instruction_window.destroy()
        self._unbind_enter()

    def on_close(self):
        """结清本桌后，像 UTH 一样交给 on_back 切回大厅。"""
        if self._closed:
            return
        try:
            self._end_session(return_balance=True)
        except ShoeBusy as exc:
            if self.round_state != "leaving":
                self.round_state = "leaving"
                self._note = str(exc)
                self._paint()
            self._job = self.after(250, self.on_close)
            return
        except Exception as exc:
            self.round_state = ("credit_pending" if self.table.phase in ("locked", "awaiting_collection")
                                and self.table._round_id is not None else "error")
            self._paint()
            messagebox.showerror("账户同步未完成", f"请重试入账后离桌。\n{exc}", parent=self.root)
            return
        self._close_windows()
        self._closed = True
        self._cancel_jobs()
        self.store.release()
        if callable(self.on_back):
            self.on_back(float(self.balance))
        else:
            self.winfo_toplevel().destroy()

    def destroy(self):
        # 大厅也可能直接销毁嵌入页；撤回未封盘筹码并释放当前牌桌。
        if not self._closed:
            try:
                self._end_session()
            finally:
                self._close_windows()
                self._closed = True
                self.store.release()
                super().destroy()
        else:
            super().destroy()


def main(initial_balance=10_000, username="Guest", *, parent=None,
         balance=None, user=None, on_back=None, on_balance_change=None):
    """采用 UTH 的嵌入入口：直接返回 Frame，不设置宿主 Tk 或安排页面布局。"""
    actual_balance = float(_cash(initial_balance if balance is None else balance))
    actual_user = username if user is None else user
    if actual_user != "Guest":
        project_root()  # 与轮盘一致，缺少项目账户组件时停止账户模式。
    if parent is not None:
        return PoKarDetteGameGUI(
            parent, actual_balance, actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
    root = tk.Tk()
    try:
        page = PoKarDetteGameGUI(root, initial_balance=actual_balance, username=actual_user)
    except Exception:
        root.destroy()
        raise
    page.pack(fill=tk.BOTH, expand=True)
    # 与 UTH 一样，只有独立运行的新窗口安装自己的关闭回调。
    page.on_back = lambda final_balance: root.destroy()
    root.protocol("WM_DELETE_WINDOW", page.on_close)
    root.mainloop()
    return page.balance


if __name__ == "__main__":
    print(f"Final balance: {main()}")
