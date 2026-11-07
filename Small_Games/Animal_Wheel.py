"""Animal Wheel · 动物摩天轮。

保留 main / EmbeddedGamePage 和加密账户余额接入。
界面和动物全部由 Tk Canvas 绘制，不需要额外图片或第三方包。
规则：30 秒下注（可立即封盘）-> 暗场跑灯 -> 结果图案 -> 结算弹窗 -> 下一轮。
仅摩天轮动物可下注：左键追加，右键撤销；右侧表格只读。
Enter 可立即封盘，需松键后再次按下；下注期间灯光每秒顺时针移动一格。
结算卡居右自动收起，游戏通过窗口标题栏 X 关闭。
历史保存在 A_Logs/Json/animal_wheel.json。
设计概率：每项投注 RTP 99.5%；狗/企鹅抽中后的派对触发率均为
2137 / 80595 = 2.651529251194%。倍率含本金，派对按各动物原倍率赔付。
开奖、派对及动画直接使用 secrets.randbelow，无种子，无历史频率修正。
"""

from __future__ import annotations

import json
import logging
import math
import os
import secrets
import sys
import time
import tkinter as tk
import uuid
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from fractions import Fraction
from pathlib import Path
from tkinter import messagebox
from typing import Callable, Optional


VERSION = "AnimalWheel-7.0-RTP995"
GAME_TITLE = "动物摩天轮"
BETTING_SECONDS = 30
RESULT_SECONDS = 4
SETTLEMENT_DELAY = 1
IDLE_LIGHT_SECONDS = 1
HISTORY_LIMIT = 1000
CHIPS = (20, 100, 1000, 5000)
RTP = Fraction(199, 200)
TOTAL_WEIGHT = 810000
PARTY_NUMERATOR = 2137
PARTY_DENOMINATOR = 80595
LAND = ("dog", "panda", "monkey", "rabbit")
SEA = ("penguin", "turtle", "seal", "whale")


@dataclass(frozen=True)
class Animal:
    key: str
    name: str
    multiplier: int
    draw_weight: int
    color: str


# 顺时针座舱顺序。draw_weight 是触发派对之前的抽选权重。
ANIMALS = (
    Animal("dog", "小狗", 5, 161190, "#F5AB56"),
    Animal("panda", "熊猫", 5, 156916, "#777993"),
    Animal("monkey", "猴子", 5, 156916, "#C98654"),
    Animal("rabbit", "兔子", 5, 156916, "#F4A7C9"),
    Animal("penguin", "企鹅", 10, 80595, "#657BAF"),
    Animal("turtle", "乌龟", 15, 51593, "#8BC96E"),
    Animal("seal", "海豹", 25, 30101, "#EC9DB6"),
    Animal("whale", "鲸鱼", 45, 15773, "#40BFEF"),
)
ANIMAL_BY_KEY = {a.key: a for a in ANIMALS}
FINAL_WEIGHTS = {
    "dog": 156916, "panda": 156916, "monkey": 156916,
    "rabbit": 156916, "penguin": 78458, "turtle": 51593,
    "seal": 30101, "whale": 15773,
    "land_party": 4274, "sea_party": 2137,
}
assert sum(a.draw_weight for a in ANIMALS) == TOTAL_WEIGHT
assert sum(FINAL_WEIGHTS.values()) == TOTAL_WEIGHT


def instruction_pages():
    """与 Blackjack_Classic 相同的目录 / 卡片 / 表格说明结构。"""
    return (
        ("玩法", "了解一局从下注、跑灯到结算的完整顺序。", (
            ("游戏目标", "", (
                ("选择动物", "在摩天轮上为一个或多个动物下注。开出的动物或派对决定哪些投注获胜。"),
            ), ()),
            ("一局如何进行", "", (
                ("下注", "每轮有30秒下注时间。先选择筹码，再点击摩天轮上的动物。"),
                ("封盘与跑灯", "倒计时结束，或点击“开始转动” / 按 Enter 后立即封盘。封盘后不能追加或撤销投注。"),
                ("公布结果", "中心显示开奖结果；对应动物与派对亮灯。"),
                ("结算与下一轮", "右侧结算卡显示下注、获胜金额与净收益，并自动收起进入下一轮。"),
            ), ()),
        )),
        ("下注", "筹码、鼠标操作与立即开奖。", (
            ("筹码与动物", "", (
                ("选择筹码", "可选20、100、1,000或5,000。一次点击追加所选筹码的金额。"),
                ("左键下注", "只在摩天轮动物上下注。重复点击可追加，同一轮可同时押多个动物。"),
                ("右键撤销", "右键点击动物，删除该动物本轮全部下注并退回余额。封盘后不能撤销。"),
                ("右侧明细", "本轮投注表只显示动物、倍率与已下注金额，点击表格不会下注。"),
            ), ()),
            ("快捷操作", "", (
                ("重复上轮投注", "将上一轮整组投注追加到当前轮；只有存在上一轮投注且余额足够时才能使用。"),
                ("开始转动 / Enter", "在下注期间立即封盘。Enter 需松开后再次按下；长按不会连续启动，开奖与结算期间按键无效。"),
            ), ()),
        )),
        ("获胜条件", "动物结果与返还金额的计算方式。", (
            ("如何判断获胜", "", (
                ("动物结果", "开出单个动物时，只有该动物的投注获胜。"),
                ("派对结果", "开出派对时，对应四个动物的投注同时获胜。"),
                ("未下注或未命中", "未下注的动物不产生奖励，未命中的投注不返还。"),
            ), ()),
            ("动物倍率", "倍率包含本金。", (), (
                ("八个动物", ("动物", "返还倍率"),
                 tuple((a.name, f"{a.multiplier}倍") for a in ANIMALS)),
            )),
            ("金额计算", "", (
                ("获胜金额", "获胜动物的下注金额 × 对应倍率。多项获胜时，逐项计算后相加。"),
                ("净收益", "本局获胜金额减去本局全部下注金额。"),
                ("例子", "下注鲸鱼20，单独开出鲸鱼：获胜金额为20 × 45 = 900。若本局另有其他投注，净收益还需扣除这些下注。"),
            ), ()),
        )),
        ("派对", "两种派对的触发动物、获胜项目与赔付方式。", (
            ("陆地派对", "", (
                ("触发动物", "陆地派对只会由小狗触发。"),
                ("同时获胜", "小狗、熊猫、猴子、兔子的投注全部获胜，分别按各自5倍返还。"),
            ), ()),
            ("海洋派对", "", (
                ("触发动物", "海洋派对只会由企鹅触发。"),
                ("同时获胜", "企鹅、乌龟、海豹、鲸鱼的投注全部获胜，分别按10、15、25、45倍返还。"),
            ), ()),
            ("派对结算", "", (
                ("按动物分别计算", "派对只改变获胜项目，各动物仍使用原倍率。只计算实际下注的项目。"),
            ), ()),
        )),
        ("特别事项", "金额显示、记录、灯光与关闭游戏。", (
            ("显示与操作", "", (
                ("金额显示", "账号余额显示到小数点后两位；下注和结算金额显示整数。"),
                ("等待灯光", "下注期间，灯光每秒顺时针移动一格。"),
                ("结果显示", "中心结果图案持续亮起；外围中奖动物与派对闪灯。"),
                ("最近开奖", "底部显示最近的开奖结果，派对使用各自图案。"),
            ), ()),
            ("关闭游戏", "", (
                ("标题栏 X", "未封盘时关闭窗口，会退回本轮下注；已封盘时关闭，会按本轮结果完成结算。"),
                ("关闭说明", "点击本窗口的“关闭 ESC”、按 Esc 或点击标题栏 X，仅关闭说明窗口。"),
            ), ()),
        )),
    )


# ---- 原项目账户接入：仍通过 install_secure_json 读写同一 cash 字段 ----
_account_directory: Optional[Path] = None


def _ensure_account_storage() -> Path:
    global _account_directory
    if _account_directory is not None:
        return _account_directory
    here = Path(__file__).resolve().parent
    project = next((p for p in (here, *here.parents)
                    if (p / "A_Tools/Account/secure_json.py").is_file()), None)
    if project is None:
        raise RuntimeError("找不到加密账户模块，请把本文件放回原项目的游戏目录。")
    if str(project) not in sys.path:
        sys.path.insert(0, str(project))
    from A_Tools.Account import install_secure_json
    install_secure_json()
    _account_directory = project / "A_Tools" / "Account"
    return _account_directory


def get_data_file_path() -> str:
    return str(_ensure_account_storage() / "saving_data.json")


def get_history_file_path() -> str:
    # 与 Stock_Market.py 相同的日志目录，使用独立的游戏文件。
    project = _ensure_account_storage().parent.parent
    return str(project / "A_Logs" / "Json" / "animal_wheel.json")


def load_user_data() -> list:
    # 与最新 Penalty.py 一样使用内置 open + json.load。
    # Path.open 走 io.open，可能绕过 install_secure_json 安装的文件钩子，
    # 让 json.load 读到加密封装，从而误报“账户文件格式异常”。
    path = get_data_file_path()  # 先安装账户钩子，再查找内置 open。
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return []
    if not isinstance(data, list) or any(not isinstance(u, dict) for u in data):
        raise ValueError("账户文件格式异常，已停止余额写入。")
    return data


def save_user_data(users: list) -> None:
    path = get_data_file_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(users, file, ensure_ascii=False, indent=4)


def update_balance_in_json(username: str, new_balance: float) -> None:
    cents = to_cents(new_balance)
    if cents < 0:
        raise ValueError("余额不能为负数。")
    users = load_user_data()
    for user in users:
        if user.get("user_name") == username:
            user["cash"] = f"{Decimal(cents) / 100:.2f}"
            break
    else:
        users.append({"user_name": username, "cash": f"{Decimal(cents) / 100:.2f}"})
    # 不再吞掉写入错误：未写入成功时不能继续扣款或发奖。
    save_user_data(users)


def to_cents(value) -> int:
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError("金额必须是有限数字。")
        return int((number * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, OverflowError) as exc:
        raise ValueError("无效金额。") from exc


def money(cents: int) -> str:
    return f"{Decimal(cents) / 100:,.2f}"


def whole_money(cents: int) -> str:
    """下注和返还显示整数；存储、结算仍保留精确到分的金额。"""
    return f"{(Decimal(cents)/100).quantize(Decimal('1'), rounding=ROUND_HALF_UP):,}"


@dataclass(frozen=True)
class Outcome:
    base: str
    party: Optional[str] = None

    def __post_init__(self):
        if self.base not in ANIMAL_BY_KEY:
            raise ValueError("未知动物。")
        if self.party not in (None, "land_party", "sea_party"):
            raise ValueError("未知派对。")
        if self.party == "land_party" and self.base != "dog":
            raise ValueError("陆地派对只能由狗触发。")
        if self.party == "sea_party" and self.base != "penguin":
            raise ValueError("海洋派对只能由企鹅触发。")

    @property
    def winners(self) -> tuple[str, ...]:
        if self.party == "land_party":
            return LAND
        if self.party == "sea_party":
            return SEA
        return (self.base,)

    @property
    def title(self) -> str:
        if self.party == "land_party":
            return "陆地派对"
        if self.party == "sea_party":
            return "海洋派对"
        return ANIMAL_BY_KEY[self.base].name


def draw_outcome(rng=None) -> Outcome:
    """secrets 无偏整数抽样：先选动物，再仅对狗、企鹅抽对应派对。

    正常游戏不传 rng，直接使用 secrets.randbelow 的系统随机源；
    rng 参数仅保留作测试注入，以逐一核对区间边界。
    """
    randbelow = secrets.randbelow if rng is None else rng.randrange
    ticket = randbelow(TOTAL_WEIGHT)
    cumulative = 0
    for animal in ANIMALS:
        cumulative += animal.draw_weight
        if ticket < cumulative:
            party = None
            if animal.key in ("dog", "penguin"):
                if randbelow(PARTY_DENOMINATOR) < PARTY_NUMERATOR:
                    party = "land_party" if animal.key == "dog" else "sea_party"
            return Outcome(animal.key, party)
    raise AssertionError("开奖权重未覆盖全部区间。")


@dataclass(frozen=True)
class SpinPlan:
    start: int
    indices: tuple[int, ...]
    delays: tuple[float, ...]


def build_spin_plan(target: int, rng=None) -> SpinPlan:
    """只编排灯光，不参与开奖。起点以 secrets.randbelow(8) 等概率抽取。"""
    if target not in range(8):
        raise ValueError("无效落点。")
    randbelow = secrets.randbelow if rng is None else rng.randrange
    start = randbelow(8)
    loops = 3 + randbelow(3)
    if randbelow(5) == 0:  # 偶尔额外跑一整圈，保持原落点。
        loops += 1
    steps = loops*8 + (target-start)%8
    fast = .035 + randbelow(26)/1000
    slow = .24 + randbelow(91)/1000
    burst = 8+randbelow(steps-20) if randbelow(4) == 0 else -10
    linger = 8+randbelow(steps-20) if randbelow(6) == 0 else -10
    delays = []
    for i in range(steps):
        # 起步加速，途中偶发加速 / 留灯，最后十二格平滑减速。
        if i < 6:
            delay = fast + .12*(1-i/6)**2
        elif i >= steps-12:
            delay = fast + slow*((i-(steps-12)+1)/12)**2
        else:
            delay = fast * (.90+randbelow(21)/100)
        if burst <= i < burst+4 and i < steps-12:
            delay *= .55
        if i == linger and i < steps-12:
            delay += .11
        delays.append(max(.02,delay))
    return SpinPlan(start,tuple((start+i+1)%8 for i in range(steps)),tuple(delays))


@dataclass(frozen=True)
class RoundRecord:
    number: int
    timestamp: str
    outcome: Outcome
    stake_cents: int
    payout_cents: int
    bets: tuple[tuple[str, int], ...]
    round_id: str = ""
    record_id: str = ""

    @property
    def net_cents(self) -> int:
        return self.payout_cents - self.stake_cents

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id, "round_id": self.round_id,
            "number": self.number, "settled_at": self.timestamp,
            "result": self.outcome.party or self.outcome.base,
            "base_animal": self.outcome.base,
            "stake_cents": self.stake_cents, "payout_cents": self.payout_cents,
            "bets_cents": dict(self.bets),
        }

    @classmethod
    def from_dict(cls, row: dict):
        result = row["result"]
        if result not in FINAL_WEIGHTS:
            raise ValueError("未知历史开奖结果。")
        outcome = Outcome(row["base_animal"], result if result.endswith("_party") else None)
        if (outcome.party or outcome.base) != result:
            raise ValueError("历史开奖结果不一致。")
        bets = row["bets_cents"]
        if (not isinstance(bets, dict) or set(bets) != set(ANIMAL_BY_KEY)
                or any(type(v) is not int or v < 0 for v in bets.values())):
            raise ValueError("历史投注格式错误。")
        for key in ("number", "stake_cents", "payout_cents"):
            if type(row[key]) is not int or row[key] < 0:
                raise ValueError("历史金额或序号格式错误。")
        if (sum(bets.values()) != row["stake_cents"] or row["payout_cents"] !=
                sum(bets[k]*ANIMAL_BY_KEY[k].multiplier for k in outcome.winners)):
            raise ValueError("历史结算金额不一致。")
        for key in ("round_id", "record_id", "settled_at"):
            if not isinstance(row[key], str) or not row[key]:
                raise ValueError("历史局号格式错误。")
        datetime.strptime(row["round_id"], "%Y%m%d-%H%M%S")
        return cls(row["number"], row["settled_at"], outcome,
                   row["stake_cents"], row["payout_cents"], tuple(bets.items()),
                   row["round_id"], row["record_id"])


class HistoryStore:
    """最近 1000 局 + 永久的十类互斥结果计数；path=None 供独立模型测试。"""

    def __init__(self, path=None):
        self.path = os.fspath(path) if path is not None else None
        self.data = self._read() if self.path else self._empty()

    @staticmethod
    def _empty():
        return {"schema_version": 1, "total_rounds": 0,
                "outcome_counts": dict.fromkeys(FINAL_WEIGHTS, 0), "recent_rounds": []}

    def _read(self):
        try:
            with open(self.path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            return self._empty()
        try:
            if not isinstance(data, dict) or data.get("schema_version") != 1:
                raise ValueError("历史版本不受支持。")
            counts, total, rows = data["outcome_counts"], data["total_rounds"], data["recent_rounds"]
            if (not isinstance(counts, dict) or set(counts) != set(FINAL_WEIGHTS)
                    or any(type(v) is not int or v < 0 for v in counts.values())
                    or type(total) is not int or total != sum(counts.values())
                    or not isinstance(rows, list) or len(rows) != min(total, HISTORY_LIMIT)):
                raise ValueError("历史累计统计不一致。")
            records = [RoundRecord.from_dict(row) for row in rows]
            if len({r.record_id for r in records}) != len(records):
                raise ValueError("历史中存在重复记录。")
            return data
        except (KeyError, TypeError, ValueError) as exc:
            # 损坏的数据不能当成空历史覆盖，否则永久统计会丢失。
            raise ValueError(f"战果文件格式异常，请检查 {self.path}：{exc}") from exc

    @property
    def total_rounds(self):
        return self.data["total_rounds"]

    @property
    def counts(self):
        return dict(self.data["outcome_counts"])

    @property
    def records(self):
        return [RoundRecord.from_dict(row) for row in self.data["recent_rounds"]]

    def append(self, record: RoundRecord):
        # 重新读取再更新；同一局重试写入只计一次，永久统计不随 1000 局截断。
        old = self._read() if self.path else self.data
        if any(row["record_id"] == record.record_id for row in old["recent_rounds"]):
            self.data = old
            return
        counts = dict(old["outcome_counts"])
        counts[record.outcome.party or record.outcome.base] += 1
        data = {
            "schema_version": 1, "updated_at": record.timestamp,
            "total_rounds": old["total_rounds"] + 1, "outcome_counts": counts,
            "recent_rounds": ([record.to_dict()] + old["recent_rounds"])[:HISTORY_LIMIT],
        }
        if self.path:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            temporary = self.path + "." + uuid.uuid4().hex + ".tmp"
            try:
                with open(temporary, "w", encoding="utf-8") as file:
                    json.dump(data, file, ensure_ascii=False, indent=2)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(temporary, self.path)
            finally:
                if os.path.exists(temporary):
                    os.remove(temporary)
        self.data = data


class FerrisModel:
    """无 GUI 的金额/回合模型，分为下注、开奖、结果三阶段。"""

    def __init__(self, initial_balance, persist: Callable[[float], None], rng=None,
                 *, history_store=None, round_clock=None):
        self.balance_cents = to_cents(initial_balance)
        if self.balance_cents < 0:
            raise ValueError("初始余额不能为负数。")
        self.persist = persist
        self.rng = rng  # None 时 draw_outcome 直接调用 secrets.randbelow。
        self.bets = {a.key: 0 for a in ANIMALS}
        self.previous_bets = dict(self.bets)
        self.phase = "betting"
        self.history_store = history_store if history_store is not None else HistoryStore()
        self.round_clock = round_clock or datetime.now
        self.number = self.history_store.total_rounds + 1
        self.round_id = self.round_clock().strftime("%Y%m%d-%H%M%S")
        self._record_id = uuid.uuid4().hex
        self._pending_record = None
        self._payout_committed = False
        self.outcome: Optional[Outcome] = None
        self.record: Optional[RoundRecord] = None
        self.history: deque[RoundRecord] = deque(self.history_store.records, maxlen=HISTORY_LIMIT)

    @property
    def stake_cents(self) -> int:
        return sum(self.bets.values())

    def _commit_balance(self, cents: int) -> None:
        if cents < 0:
            raise ValueError("余额不足。")
        if cents != self.balance_cents:
            self.persist(float(Decimal(cents) / 100))
            self.balance_cents = cents

    def _require_betting(self) -> None:
        if self.phase != "betting":
            raise ValueError("本轮已停止下注，请等待下一轮。")

    def place_bets(self, additions: dict[str, int]) -> None:
        self._require_betting()
        if not additions or any(k not in self.bets or type(v) is not int or v < 0
                                for k, v in additions.items()):
            raise ValueError("无效投注。")
        amount = sum(additions.values())
        if amount <= 0:
            raise ValueError("请先选择投注。")
        self._commit_balance(self.balance_cents - amount)
        for key, cents in additions.items():
            self.bets[key] += cents

    def clear_bets(self) -> None:
        self._require_betting()
        self._commit_balance(self.balance_cents + self.stake_cents)
        self.bets = dict.fromkeys(self.bets, 0)

    def remove_bet(self, key: str) -> int:
        self._require_betting()
        if key not in self.bets:
            raise ValueError("未知动物。")
        refund = self.bets[key]
        self._commit_balance(self.balance_cents + refund)
        self.bets[key] = 0
        return refund

    def repeat_bets(self) -> None:
        if not any(self.previous_bets.values()):
            raise ValueError("还没有上一轮投注记录。")
        self.place_bets(self.previous_bets)

    def begin_spin(self) -> Outcome:
        self._require_betting()
        self.outcome = draw_outcome(self.rng)
        self.phase = "spinning"
        return self.outcome

    def settle(self) -> RoundRecord:
        if self.record is not None:
            return self.record  # 同一轮重复回调或退出时不会重复发奖。
        if self.phase != "spinning" or self.outcome is None:
            raise ValueError("尚未开奖。")
        if self._pending_record is None:
            payout = sum(self.bets[key] * ANIMAL_BY_KEY[key].multiplier
                         for key in self.outcome.winners)
            self._pending_record = RoundRecord(
                self.number, self.round_clock().isoformat(timespec="seconds"), self.outcome,
                self.stake_cents, payout, tuple(self.bets.items()), self.round_id, self._record_id,
            )
        if not self._payout_committed:
            self._commit_balance(self.balance_cents + self._pending_record.payout_cents)
            self._payout_committed = True
        # 余额已到账而日志写入失败时，重试只补写日志，绝不再次发奖。
        self.history_store.append(self._pending_record)
        self.record = self._pending_record
        if self.stake_cents:
            self.previous_bets = dict(self.bets)
        self.history = deque(self.history_store.records, maxlen=HISTORY_LIMIT)
        self.phase = "result"
        return self.record

    def next_round(self) -> None:
        if self.phase != "result":
            raise ValueError("上一轮尚未结算。")
        self.number = self.history_store.total_rounds + 1
        self.round_id = self.round_clock().strftime("%Y%m%d-%H%M%S")
        self._record_id = uuid.uuid4().hex
        self._pending_record = None
        self._payout_committed = False
        self.bets = dict.fromkeys(self.bets, 0)
        self.outcome = None
        self.record = None
        self.phase = "betting"

    def prepare_close(self) -> None:
        # 未封盘可退还；已封盘按原定结果结算，不能退出重抽。
        if self.phase == "betting":
            self.clear_bets()
        elif self.phase == "spinning":
            self.settle()


class Theme:
    BG = "#FFF0F8"
    PANEL = "#FFFFFF"
    INK = "#343153"
    MUTED = "#9387A2"
    PINK = "#F065A8"
    PURPLE = "#7760D7"
    BLUE = "#3F91F4"
    CYAN = "#73D8F8"
    GOLD = "#FFCD5A"
    GREEN = "#36A58C"
    RIGHT_BG = "#F5F1FC"
    RIGHT_CARD = "#FFFFFF"
    RIGHT_ROW = "#EDE7F8"
    RIGHT_SELECTED = "#FCE5F0"
    RIGHT_TEXT = "#343153"
    RIGHT_MUTED = "#9387A2"
    RIGHT_ACCENT = "#7760D7"
    RIGHT_HOVER = "#8D76E5"
    RIGHT_GOLD = "#E361A1"
    RIGHT_BORDER = "#DCD1EE"
    FONT = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC")


class AnimalWheelGame:
    WINDOW_WIDTH = 1150
    WINDOW_HEIGHT = 750

    def __init__(self, root, initial_balance: float, username: str, *,
                 balance_writer=None, rng=None, on_balance_change=None, history_store=None,
                 animation_rng=None):
        self.root = root
        self.username = username
        writer = balance_writer or (lambda value: update_balance_in_json(username, value))
        store = history_store if history_store is not None else HistoryStore(get_history_file_path())
        self.model = FerrisModel(initial_balance, writer, rng, history_store=store)
        self._on_balance_change = on_balance_change
        self._last_notified_balance = self.balance
        self._closed = False
        self._job = None
        now = time.monotonic()
        self._deadline = now + BETTING_SECONDS
        self._idle_next = now + IDLE_LIGHT_SECONDS
        self._enter_held = False
        self._enter_release_job = None
        self._spin_next = 0.0
        self._spin_step = 0
        self._spin_steps = 0
        self._spin_plan = None
        self._animation_rng = animation_rng  # 动画独立取样，不能覆盖已抽定的结果。
        self._lit_index = secrets.randbelow(8)
        self._hover = None
        self._display_stamp = None
        self._payment_error = False
        self._result_started = 0.0
        self._brightness = 1.0
        self._compact_art = False
        self._popups = {}
        self.selected_chip = CHIPS[0]
        self.balance_var = tk.StringVar(master=root, value=money(self.model.balance_cents))
        self._configure_root()
        self.container = tk.Frame(root, bg=Theme.BG)
        self.container.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(self.container, bg=Theme.BG, highlightthickness=0,takefocus=True)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        if sys.platform == "darwin":
            self.canvas.bind("<Button-2>", self._on_right_click)
            self.canvas.bind("<Control-Button-1>", self._on_right_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)
        for key in ("Return", "KP_Enter"):
            self.canvas.bind(f"<KeyPress-{key}>", self._on_enter_press)
            self.canvas.bind(f"<KeyRelease-{key}>", self._on_enter_release)
        self.canvas.bind("<FocusOut>", self._on_key_focus_out)
        self.canvas.focus_set()
        self.root.bind("<Destroy>", self._on_destroy, add="+")
        self._scale, self._ox, self._oy = 1.0, 0.0, 0.0
        self._regions = []
        self._tick()

    @property
    def balance(self) -> float:
        return self.model.balance_cents / 100.0

    @balance.setter
    def balance(self, value) -> None:
        # 兼容宿主对 game.balance 的直接同步；游戏内部资金变动走持久化提交。
        cents = to_cents(value)
        if cents < 0:
            raise ValueError("余额不能为负数。")
        self.model.balance_cents = cents
        if hasattr(self, "canvas"):
            self.update_display()

    @property
    def current_bet(self) -> float:
        return self.model.stake_cents / 100.0

    @property
    def game_active(self) -> bool:
        return self.model.phase == "spinning"

    @property
    def game_running(self) -> bool:
        return self.model.phase == "spinning"

    def _configure_root(self):
        self.root.configure(bg=Theme.BG)
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title(GAME_TITLE)
            self.root.geometry("1150x750+50+10")
            self.root.minsize(920, 600)
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        else:
            self.root.configure(width=self.WINDOW_WIDTH, height=self.WINDOW_HEIGHT)
            self.root.pack_propagate(False)
            self.root.grid_propagate(False)

    def _on_resize(self, _event=None):
        self.draw_scene()

    def _world(self, x, y):
        return (x - self._ox) / self._scale, (y - self._oy) / self._scale

    def _coords(self, values):
        return [v * self._scale + (self._ox if i % 2 == 0 else self._oy)
                for i, v in enumerate(values)]

    def _shade(self, color):
        if not color or self._brightness >= 1:
            return color
        color = {"white": "#FFFFFF", "black": "#000000"}.get(color, color)
        if not color.startswith("#") or len(color) != 7:
            return color
        rgb = [int(color[i:i+2], 16) for i in (1,3,5)]
        return "#" + "".join(f"{round(c*self._brightness+b*(1-self._brightness)):02x}"
                               for c,b in zip(rgb,(18,13,37)))

    @contextmanager
    def _light(self, brightness):
        previous = self._brightness
        self._brightness = brightness
        try:
            yield
        finally:
            self._brightness = previous

    @contextmanager
    def _local_art(self, x, y, size):
        previous = self._scale,self._ox,self._oy,self._compact_art
        self._ox += x*self._scale
        self._oy += y*self._scale
        self._scale *= size
        self._compact_art = size < .6
        try:
            yield
        finally:
            self._scale,self._ox,self._oy,self._compact_art = previous

    def _oval(self, x0, y0, x1, y1, fill, outline="", width=1):
        return self.canvas.create_oval(*self._coords((x0, y0, x1, y1)),
                                       fill=self._shade(fill), outline=self._shade(outline),
                                       width=max(1, width * self._scale))

    def _line(self, points, fill, width=1, **kw):
        return self.canvas.create_line(*self._coords(points), fill=self._shade(fill),
                                       width=max(1, width * self._scale), **kw)

    def _poly(self, points, fill, outline="", width=1, **kw):
        return self.canvas.create_polygon(*self._coords(points), fill=self._shade(fill),
                                          outline=self._shade(outline),
                                          width=max(1, width * self._scale), **kw)

    def _round(self, x0, y0, x1, y1, radius=16, fill="white", outline="", width=1):
        r = min(radius, (x1-x0)/2, (y1-y0)/2)
        points = (x0+r,y0, x1-r,y0, x1,y0, x1,y0+r, x1,y1-r,
                  x1,y1, x1-r,y1, x0+r,y1, x0,y1, x0,y1-r,
                  x0,y0+r, x0,y0)
        return self._poly(points, fill, outline, width, smooth=True, splinesteps=16)

    def _text(self, x, y, text, size=12, color=Theme.INK, bold=False,
              anchor="center", width=0):
        return self.canvas.create_text(*self._coords((x, y)), text=str(text),
                                       # 负字号为像素，避免系统 DPI 改变字形/座舱比例。
                                       font=(Theme.FONT, -max(1 if self._compact_art else 8, round(size*self._scale*4/3)),
                                             "bold" if bold else "normal"),
                                       fill=self._shade(color), anchor=anchor,
                                       width=round(width*self._scale) if width else 0)

    def _star(self, x, y, radius, color):
        points = []
        for i in range(10):
            angle = -math.pi/2 + i*math.pi/5
            r = radius if i % 2 == 0 else radius*.45
            points.extend((x+math.cos(angle)*r, y+math.sin(angle)*r))
        self._poly(points, color)

    def _animal(self, key, x, y, size=1.0):
        """自绘八种动物，坐标以约 56x56 的图标空间计。"""
        def oval(a,b,c,d,fill,outline="",width=1):
            self._oval(x+a*size,y+b*size,x+c*size,y+d*size,fill,outline,width*size)
        def poly(points,fill):
            self._poly([v*size+(x if i%2==0 else y) for i,v in enumerate(points)],fill)
        def line(points,fill,width=1):
            self._line([v*size+(x if i%2==0 else y) for i,v in enumerate(points)],fill,width*size)
        def eyes(left=-10,right=10,yy=-1):
            for xx in (left,right):
                oval(xx-2.9,yy-3.3,xx+2.9,yy+3.3,"#293149")
                oval(xx-1.8,yy-2.5,xx-.2,yy-.9,"white")
        if key == "dog":
            poly((-24,-10,-24,-31,-8,-20),"#F6A64A")
            poly((24,-10,24,-31,8,-20),"#F6A64A")
            poly((-21,-16,-21,-26,-12,-20),"#FAD6B0")
            poly((21,-16,21,-26,12,-20),"#FAD6B0")
            oval(-26,-24,26,23,"#F6AF56")
            oval(-23,-2,23,23,"#FFF1D5")
            oval(-20,-11,-5,4,"#FFF1D5");oval(5,-11,20,4,"#FFF1D5")
            eyes();oval(-4,4,4,10,"#47383C")
            line((0,9,0,13,-5,15),"#47383C",1.5)
            line((0,13,5,15),"#47383C",1.5)
        elif key == "panda":
            oval(-29,-29,-8,-8,"#3E4259");oval(8,-29,29,-8,"#3E4259")
            oval(-26,-24,26,25,"#FFFFFD")
            oval(-20,-12,-3,9,"#3E4259");oval(3,-12,20,9,"#3E4259")
            for xx in (-11,11):
                oval(xx-3,-5,xx+3,2,"white");oval(xx-1,-4,xx+2,1,"#222A40")
            oval(-4,9,4,14,"#3E4259");line((-6,18,0,20,6,18),"#3E4259",1.5)
        elif key == "monkey":
            oval(-34,-13,-13,12,"#C97C42");oval(13,-13,34,12,"#C97C42")
            oval(-29,-8,-18,6,"#FFCD99");oval(18,-8,29,6,"#FFCD99")
            oval(-26,-27,26,25,"#BD743E")
            oval(-22,-14,22,23,"#FFD3A3")
            oval(-18,-18,0,3,"#FFD3A3");oval(0,-18,18,3,"#FFD3A3")
            eyes();oval(-3,7,3,11,"#9D6143")
            line((-10,13,-6,17,0,18,6,17,10,13),"#9D6143",1.5)
        elif key == "rabbit":
            oval(-20,-39,-3,-5,"#FFFFFE");oval(3,-39,20,-5,"#FFFFFE")
            oval(-15,-33,-7,-10,"#F8AACD");oval(7,-33,15,-10,"#F8AACD")
            oval(-25,-16,25,26,"#FFFFFE");eyes(-10,10,2)
            oval(-21,7,-12,12,"#F9CFDF");oval(12,7,21,12,"#F9CFDF")
            poly((-4,9,4,9,0,14),"#E78EAF")
            line((0,14,-4,17),"#B8869F");line((0,14,4,17),"#B8869F")
        elif key == "penguin":
            oval(-22,-28,22,27,"#39465D")
            oval(-17,-13,17,25,"#FFFDF1")
            oval(-17,-19,2,2,"#FFFDF1");oval(-2,-19,17,2,"#FFFDF1")
            eyes(-9,9,-8);poly((-5,1,5,1,0,8),"#F6B74B")
            poly((-20,7,-31,20,-18,18),"#39465D")
            poly((20,7,31,20,18,18),"#39465D")
            oval(-18,23,-3,30,"#F8BA51");oval(3,23,18,30,"#F8BA51")
        elif key == "turtle":
            for xx,yy in ((-3,17),(17,17),(-3,-4),(18,-4)):
                oval(xx-6,yy-3,xx+6,yy+10,"#9ED66C")
            oval(-16,-16,30,21,"#75B652","#B8E987",2)
            poly((-1,-12,15,-12,22,2,14,16,-1,16,-9,2),"#A2D770")
            line((-9,2,22,2),"#75B652",1.5)
            line((6,-12,6,16),"#75B652",1.5)
            oval(-35,-21,-8,7,"#ACDF7A")
            oval(-29,-12,-24,-6,"#394B44")
            line((-30,-1,-25,2,-19,1),"#5B854D",1.5)
        elif key == "seal":
            oval(-22,-25,22,28,"#F4A8BE")
            oval(-20,-24,20,9,"#FFE1C5")
            poly((-19,10,-34,23,-12,22),"#F4A8BE")
            poly((19,10,34,23,12,22),"#F4A8BE")
            eyes(-9,9,-7);oval(-4,0,4,6,"#70525C")
            for sign in (-1,1):
                line((sign*7,3,sign*19,0),"#B77886")
                line((sign*7,7,sign*18,10),"#B77886")
        elif key == "whale":
            poly((17,-3,29,-17,26,-27,35,-21,44,-25,41,-13,31,0,24,12),"#65D5F6")
            oval(-32,-20,28,24,"#37BEEC")
            oval(-25,11,18,26,"#CEFAFF")
            oval(-32,-20,28,20,"#37BEEC")
            oval(-21,-6,-14,2,"#1B719E");oval(-20,-5,-18,-3,"white")
            oval(4,9,19,22,"#199ECE")
            line((-4,-22,-4,-34),"#A2EBFF",3)
            oval(-14,-36,-3,-28,"#A2EBFF");oval(-4,-39,7,-30,"#A2EBFF")

    def _button(self, name, box, label, *, fill=Theme.PURPLE,
                foreground="white", enabled=True, size=12,hover_fill=Theme.PINK,
                disabled_fill="#F2EDF6",disabled_foreground="#A59AB5"):
        x0,y0,x1,y1 = box
        if not enabled:
            fill,foreground = disabled_fill,disabled_foreground
        elif self._hover == name:
            fill = hover_fill
        self._round(x0,y0,x1,y1,12,fill)
        self._text((x0+x1)/2,(y0+y1)/2,label,size,foreground,True)
        self._regions.append((name,box,enabled))

    def draw_scene(self):
        if self._closed:
            return
        width,height = self.canvas.winfo_width(),self.canvas.winfo_height()
        if width < 10 or height < 10:
            return
        self._scale = min(width/self.WINDOW_WIDTH,height/self.WINDOW_HEIGHT)
        self._ox = (width-self.WINDOW_WIDTH*self._scale)/2
        self._oy = (height-self.WINDOW_HEIGHT*self._scale)/2
        modal = self._is_settlement_visible()
        self._brightness = 1.0
        self.canvas.configure(bg=Theme.BG)
        self.canvas.delete("all")
        self._regions = []
        self._round(0,0,1150,750,0,Theme.BG)
        self._oval(25,26,59,60,"#EADFFF",Theme.PURPLE,3)
        self._line((42,27,42,59),Theme.PINK,2)
        self._line((26,43,58,43),Theme.PINK,2)
        self._oval(36,37,48,49,Theme.PINK)
        self._text(77,34,GAME_TITLE,22,Theme.INK,True,"w")
        self._text(78,61,"ANIMAL WHEEL  ·  选中你的幸运动物",9,Theme.MUTED,False,"w")
        self._round(423,22,718,72,18,"#F0E7FF")
        self._text(571,34,"当前局号",8,Theme.MUTED)
        self._text(571,55,self.model.round_id,14,Theme.PURPLE,True)
        self._round(749,17,1126,77,18,Theme.RIGHT_BG)
        self._text(774,32,"账号余额",8,Theme.RIGHT_MUTED,False,"w")
        self._text(774,55,money(self.model.balance_cents),18,Theme.RIGHT_TEXT,True,"w")
        self._round(749,100,1126,635,24,Theme.RIGHT_BG)
        with self._light(self._left_brightness()):
            self._round(24,100,727,635,24,"white")
            self._text(47,123,"幸运转盘",10,Theme.MUTED,True,"w")
            self._button("rules",(648,110,708,141),"规则",fill="#F1EBFA",foreground=Theme.PURPLE,size=10)
            self._draw_wheel()
        self._draw_betting_panel()
        self._draw_bottom()
        if modal:
            with self._light(1.0):
                self._draw_settlement()

    def _draw_wheel(self):
        cx,cy,orbit = 374,345,181
        self._poly((cx-15,cy+10,cx+15,cy+10,477,600,436,600),"#AEDCFC")
        self._poly((cx-15,cy+10,cx+15,cy+10,312,600,271,600),"#C3B9FA")
        self._round(271,594,477,608,7,"#9BA9EE")
        self._oval(cx-181,cy-181,cx+181,cy+181,"#EFF9FF","#D4D8FF",8)
        self._oval(cx-143,cy-143,cx+143,cy+143,"#F5F0FF","#717FEE",20)
        for i in range(8):
            a = math.radians(-90+i*45)
            self._line((cx,cy,cx+orbit*math.cos(a),cy+orbit*math.sin(a)),"#B3D8FA",7)
        self._oval(cx-120,cy-120,cx+120,cy+120,"#FDF8FF","#BCEAFB",9)
        for i in range(32):
            a = math.radians(-90+i*360/32)
            x,y = cx+143*math.cos(a),cy+143*math.sin(a)
            active = self.model.phase in ("betting","spinning") and self._lit_index >= 0 and i//4 == self._lit_index
            fill = Theme.GOLD if active else ("white" if i%2 else "#E3FAFF")
            with self._light(1.0 if active else self._brightness):
                self._oval(x-4,y-4,x+4,y+4,fill)
        self._oval(cx-92,cy-92,cx+92,cy+92,"#E3D7FF")
        self._oval(cx-83,cy-83,cx+83,cy+83,"#FFF7E9","white",4)
        if self.model.phase == "betting":
            left = max(0,math.ceil(self._deadline-time.monotonic()))
            self._text(cx,cy+4,f"{left}s",39,Theme.PURPLE,True)
        elif self.model.phase == "result" or self._payment_error:
            # 中心结果持续亮起；外围动物与派对继续闪灯。
            with self._light(1.0):
                self._oval(cx-83,cy-83,cx+83,cy+83,"#FFF7E9","white",4)
                self._draw_outcome_icon(self.model.outcome,cx,cy,146)
        winners = self.model.outcome.winners if self.model.phase == "result" else ()
        for i,animal in enumerate(ANIMALS):
            a = math.radians(-90+i*45)
            x,y = cx+orbit*math.cos(a),cy+orbit*math.sin(a)
            key = animal.key
            selected = self.model.bets[key] > 0
            lit = key in winners or (self.model.phase in ("betting","spinning") and self._lit_index == i)
            hovering = self._hover == "animal:"+key and self.model.phase == "betting"
            brightness = self._brightness
            if lit:
                brightness = self._result_light() if key in winners else 1.0
            with self._light(brightness):
                if lit:
                    self._oval(x-56,y-56,x+56,y+56,"#FFE9A1")
                self._oval(x-49,y-48,x+49,y+50,"#D5D6F7")
                fill = "#FFE3A2" if lit else ("#FFE0EE" if selected or hovering else "#DCF2FF")
                edge = "#F7B744" if lit else (Theme.PINK if selected else "#7EACF7")
                self._oval(x-47,y-49,x+47,y+45,fill,edge,3)
                self._animal(key,x,y-8,.75)
                self._round(x-39,y+23,x+39,y+43,8,"white")
                self._text(x,y+33,f"{animal.name}  {animal.multiplier}倍",9,Theme.BLUE,True)
                if selected:
                    cents = self.model.bets[key]
                    label = whole_money(cents)
                    self._round(x-31,y-59,x+31,y-37,10,"#FFB65C")
                    self._text(x,y-48,label,10,"white",True)
            self._regions.append(("animal:"+key,(x-48,y-50,x+48,y+47),self._can_bet()))
        self._draw_party("sea_party",136,590)
        self._draw_party("land_party",614,590)

    def _left_brightness(self):
        return .28 if self.model.phase != "betting" else 1.0

    def _result_light(self):
        return 1.0 if int(time.monotonic()*4)%2 == 0 else .48

    def _draw_outcome_icon(self, outcome, x, y, diameter):
        if outcome.party:
            self._draw_party(outcome.party,x,y+diameter*.155,
                             size=diameter/164,active=False)
        else:
            span = {"dog":58,"panda":60,"monkey":68,"rabbit":68,
                    "penguin":62,"turtle":68,"seal":68,"whale":78}[outcome.base]
            self._animal(outcome.base,x,y,diameter/span)

    def _draw_party(self, party, cx, floor, *, size=1.0, active=None):
        if active is None:
            active = (self.model.phase == "result" and self.model.outcome is not None
                      and self.model.outcome.party == party)
        brightness = self._result_light() if active else self._brightness
        with self._local_art(cx,floor,size), self._light(brightness):
            self._draw_party_art(party,active)

    def _draw_party_art(self, party, active):
        """轮架两侧的海洋 / 陆地玻璃圆顶，派对开出时与四个动物同步闪灯。"""
        cx,floor = 0,0
        sea = party == "sea_party"
        flash = active and int(time.monotonic()*4)%2 == 0
        rim = "#F5BF43" if active else ("#8BAEEA" if sea else "#E8B799")
        accent = "#407BDF" if sea else "#DB846A"
        label = "海洋派对" if sea else "陆地派对"

        def dome(rx, ry, bottom, fill, outline="", width=1):
            points = []
            for i in range(33):
                angle = math.pi + i*math.pi/32
                points.extend((cx+rx*math.cos(angle), bottom+ry*math.sin(angle)))
            return self._poly(points,fill,outline,width)

        self._oval(cx-82,floor+12,cx+82,floor+27,"#EAE5F7")
        if active:
            dome(87,90,floor+4,"#FFE59A" if flash else "#FFF2CA")
        dome(75,79,floor,"#FFFFFF",rim,3)
        dome(69,73,floor,"#D6F3FF" if sea else "#FFF0C9")
        dome(62,64,floor,"#A8DFFF" if sea else "#E3F5BF")

        if sea:
            # 海水、波浪、珊瑚和海星，对应影片左下角 Sea Carnival。
            self._oval(cx-59,floor-28,cx+61,floor+8,"#75BFFA")
            self._line((cx-55,floor-14,cx-37,floor-20,cx-17,floor-13,
                        cx+4,floor-19,cx+23,floor-13,cx+48,floor-21),
                       "#C1F4FF",3,smooth=True)
            for points in (
                (-27,-5,-30,-28,-22,-47),(-29,-26,-43,-39,-43,-48),
                (-28,-19,-10,-34,-8,-42),(-39,-35,-50,-34),
            ):
                self._line(tuple(v+(cx if i%2==0 else floor) for i,v in enumerate(points)),
                           "#EE8B99",5,capstyle=tk.ROUND,smooth=True)
            for points in (
                (15,-8,11,-29,19,-57),(12,-29,1,-42,2,-52),
                (15,-40,28,-47,28,-56),(12,-22,30,-31,38,-31),
            ):
                self._line(tuple(v+(cx if i%2==0 else floor) for i,v in enumerate(points)),
                           "#8F91E7",5,capstyle=tk.ROUND,smooth=True)
            self._oval(cx-48,floor-11,cx-10,floor+4,"#84A5F1")
            self._oval(cx+15,floor-16,cx+56,floor+5,"#63B1E9")
            self._star(cx+3,floor-11,15,"#FFF6C5")
            for dx,dy,r in ((-46,-61,3),(40,-44,4),(49,-23,2)):
                self._oval(cx+dx-r,floor+dy-r,cx+dx+r,floor+dy+r,"#DDFCFF","white")
        else:
            # 草地、树丛和小花，对应影片右下角 Land Party。
            self._oval(cx-60,floor-21,cx+60,floor+7,"#A5D86F")
            self._line((cx-6,floor-5,cx-6,floor-47),"#BA9B58",7)
            self._oval(cx-40,floor-49,cx+8,floor-10,"#58C67A")
            self._oval(cx-24,floor-66,cx+20,floor-22,"#71D28A")
            self._oval(cx-5,floor-45,cx+38,floor-8,"#69CA6B")
            self._oval(cx-50,floor-25,cx-18,floor-1,"#C3EB82")
            self._oval(cx+21,floor-29,cx+54,floor-1,"#B8E77A")
            for dx,dy in ((-20,-12),(13,-13),(34,-9)):
                x,y = cx+dx,floor+dy
                for i in range(5):
                    a = i*math.tau/5
                    px,py = x+5*math.cos(a),y+5*math.sin(a)
                    self._oval(px-4,py-4,px+4,py+4,"#FFFCE8")
                self._oval(x-3,y-3,x+3,y+3,"#F7C75C")

        # 弧面高光与圆顶灯泡。
        self._line((cx-56,floor-37,cx-49,floor-54,cx-34,floor-64),
                   "white",5,capstyle=tk.ROUND,smooth=True)
        self._oval(cx+31,floor-62,cx+42,floor-52,"#FFFBE1")
        for i in range(9):
            a = math.pi + (i+.5)*math.pi/9
            x,y = cx+75*math.cos(a),floor+79*math.sin(a)
            self._oval(x-2.5,y-2.5,x+2.5,y+2.5,
                       "#FFFDE4" if flash else (Theme.GOLD if active else "white"))
        self._round(cx-82,floor-1,cx+82,floor+28,9,
                    "#F4BC51" if flash else accent,"white",2)
        self._text(cx,floor+13,label,14,"white",True)

    def _right_button(self,name,box,label,*,primary=True,enabled=True,size=12):
        self._button(name,box,label,
                     fill=Theme.RIGHT_ACCENT if primary else Theme.RIGHT_ROW,
                     foreground="white" if primary else Theme.RIGHT_TEXT,
                     hover_fill=Theme.RIGHT_HOVER if primary else Theme.RIGHT_BORDER,
                     disabled_fill=Theme.RIGHT_ROW,disabled_foreground="#B0A1C2",
                     enabled=enabled,size=size)

    def _draw_betting_panel(self):
        enabled = self._can_bet()
        self._text(774,135,"本轮投注",17,Theme.RIGHT_TEXT,True,"w")
        self._text(790,176,"动物",9,Theme.RIGHT_MUTED,False,"w")
        self._text(955,176,"倍率",9,Theme.RIGHT_MUTED,False,"e")
        self._text(1086,176,"已下注",9,Theme.RIGHT_MUTED,False,"e")
        for i,animal in enumerate(ANIMALS):
            y = 211+i*39
            cents = self.model.bets[animal.key]
            fill = Theme.RIGHT_SELECTED if cents else (Theme.RIGHT_ROW if i%2==0 else Theme.RIGHT_BG)
            self._round(774,y-16,1102,y+16,8,fill)
            self._draw_outcome_icon(Outcome(animal.key),792,y,25)
            self._text(811,y,animal.name,10,Theme.RIGHT_TEXT,False,"w")
            self._text(955,y,f"×{animal.multiplier}",10,Theme.RIGHT_ACCENT,True,"e")
            self._text(1086,y,whole_money(cents),11,Theme.RIGHT_GOLD if cents else Theme.RIGHT_MUTED,True,"e")
            # 此表仅显示；点击、右键及悬停都不注册下注区域。
        self._text(774,532,"返还倍率含本金",9,Theme.RIGHT_MUTED,False,"w")
        self._text(1102,532,f"本局下注 {whole_money(self.model.stake_cents)}",12,Theme.RIGHT_GOLD,True,"e")
        if self._payment_error:
            self._right_button("retry",(774,565,1102,610),"重试保存结算",size=11)
        else:
            self._right_button("repeat",(774,565,930,610),"重复上轮投注",primary=False,
                               enabled=enabled and any(self.model.previous_bets.values()))
            self._right_button("start",(946,565,1102,610),"开始转动",enabled=enabled)

    def _draw_bottom(self):
        with self._light(self._left_brightness()):
            self._round(24,650,727,730,20,"#FFE2EF")
            self._text(48,674,"① 选筹码",11,Theme.PURPLE,True,"w")
            self._text(48,698,"② 点动物",10,Theme.MUTED,False,"w")
            for i,amount in enumerate(CHIPS):
                x = 158+i*134
                selected = self.selected_chip==amount
                enabled = self._can_bet()
                self._button("chip:"+str(amount),(x,666,x+119,716),f"{amount:,}",
                             fill=Theme.BLUE if selected else "white",
                             foreground="white" if selected else Theme.PURPLE,
                             enabled=enabled,size=15)
        self._round(749,650,1126,730,20,Theme.RIGHT_BG)
        self._text(771,669,"最近开奖",10,Theme.RIGHT_MUTED,True,"w")
        for i,record in enumerate(list(self.model.history)[:7]):
            x,y = 792+i*47,705
            self._oval(x-17,y-17,x+17,y+17,"#FFF0F7")
            self._draw_outcome_icon(record.outcome,x,y,31)

    def _is_settlement_visible(self):
        return (self.model.phase == "result" and self.model.record is not None
                and time.monotonic()-self._result_started >= SETTLEMENT_DELAY)

    def _draw_settlement(self):
        # 结算只占右侧控制面板；左侧完整展示开奖结果与闪灯。
        self._regions = [(n,b,on) for n,b,on in self._regions if b[2] <= 727]
        self._round(749,100,1126,635,24,Theme.RIGHT_BG)
        self._draw_settlement_card()

    def _draw_settlement_card(self):
        """影片式结算卡：图案、局号、获胜金额、下注；不生成联网榜单。"""
        record = self.model.record
        self._round(771,170,1110,581,20,"#E4DAEF")
        self._round(765,163,1105,573,20,Theme.RIGHT_CARD,Theme.RIGHT_BORDER,1)
        self._oval(889,190,985,286,"#F5FBFF",Theme.RIGHT_ACCENT,3)
        self._draw_outcome_icon(record.outcome,937,238,79)
        left = max(0,math.ceil(self._deadline-time.monotonic()))
        self._text(1086,186,f"{left}s",11,Theme.RIGHT_MUTED,True,"e")
        if record.stake_cents == 0:
            title = f"开出 {record.outcome.title} · 本局未下注"
        elif record.payout_cents:
            title = f"恭喜，开出 {record.outcome.title}！"
        else:
            title = "很遗憾，本局未中奖"
        self._text(937,312,title,14,Theme.RIGHT_TEXT,True)
        self._text(937,340,record.round_id,10,Theme.RIGHT_MUTED)
        self._line((789,362,1081,362),Theme.RIGHT_BORDER,1)
        self._text(937,385,"本局获胜金额",11,Theme.RIGHT_MUTED)
        self._text(937,423,whole_money(record.payout_cents),30,Theme.RIGHT_GOLD,True)
        self._text(790,470,"本局下注",11,Theme.RIGHT_MUTED,False,"w")
        self._text(1080,470,whole_money(record.stake_cents),15,Theme.RIGHT_TEXT,True,"e")
        net = ("+" if record.net_cents > 0 else "")+whole_money(record.net_cents)
        self._round(785,501,1085,551,12,Theme.RIGHT_BG)
        self._text(800,526,"本局净收益",11,Theme.RIGHT_MUTED,False,"w")
        self._text(1070,526,net,17,Theme.RIGHT_ACCENT if record.net_cents>=0 else "#F6A9A9",True,"e")

    def _hit(self, x, y):
        for name,box,enabled in reversed(self._regions):
            x0,y0,x1,y1=box
            if enabled and x0<=x<=x1 and y0<=y<=y1:
                return name
        return None

    def _on_motion(self, event):
        name = self._hit(*self._world(event.x,event.y))
        if name != self._hover:
            self._hover = name
            self.canvas.configure(cursor="hand2" if name else "")
            self.draw_scene()

    def _on_leave(self, _event):
        self._hover = None
        self.draw_scene()

    def _can_bet(self):
        return (not self._closed and not self._payment_error
                and self.model.phase == "betting" and time.monotonic() < self._deadline)

    def _on_enter_press(self, _event=None):
        if self._closed:
            return "break"
        if self._enter_release_job is not None:
            self.root.after_cancel(self._enter_release_job)
            self._enter_release_job = None
        # 系统长按重复事件不会重抽，也不能穿过结算阶段启动下一局。
        if self._enter_held:
            return "break"
        self._enter_held = True
        if self._can_bet():
            try:
                self._start_spin()
            except Exception as exc:
                logging.warning("键盘启动未完成：%s",exc)
            self.update_display()
        return "break"

    def _on_enter_release(self, _event=None):
        if self._closed:
            return "break"
        if self._enter_release_job is not None:
            self.root.after_cancel(self._enter_release_job)
        # X11 长按会产生紧邻的 Release/Press；到空闲时再解锁以过滤此情况。
        self._enter_release_job = self.root.after_idle(self._release_enter)
        return "break"

    def _release_enter(self):
        self._enter_release_job = None
        self._enter_held = False

    def _on_key_focus_out(self, _event=None):
        if self._enter_release_job is not None:
            self.root.after_cancel(self._enter_release_job)
        self._release_enter()

    def _on_right_click(self, event):
        if self._closed:
            return "break"
        self.canvas.focus_set()
        name = self._hit(*self._world(event.x,event.y))
        if not name or not name.startswith("animal:"):
            return "break"
        if not self._can_bet():
            return "break"
        else:
            key = name.split(":",1)[1]
            try:
                self.model.remove_bet(key)
            except Exception as exc:
                logging.warning("撤销投注未完成：%s",exc)
        self.update_display()
        return "break"

    def _on_click(self, event):
        if self._closed:
            return
        self.canvas.focus_set()
        name = self._hit(*self._world(event.x,event.y))
        if not name:
            return
        if name == "rules":
            self.show_rules(); return
        if name == "retry":
            self._settle(); return
        # 即使 Tk 因窗口拖动迟到处理点击，也不能在封盘后下注。
        if not self._can_bet():
            self.draw_scene(); return
        try:
            if name.startswith("chip:"):
                self.selected_chip=int(name.split(":",1)[1])
            elif name.startswith("animal:"):
                key=name.split(":",1)[1]
                self.model.place_bets({key:self.selected_chip*100})
            elif name=="repeat":
                self.model.repeat_bets()
            elif name=="start":
                self._start_spin()
        except Exception as exc:
            logging.warning("投注操作未完成：%s",exc)
        self.update_display()

    def _start_spin(self):
        # 按钮、Enter 与自动倒计时共用此入口；每局只抽一次。
        if self._closed or self._payment_error or self.model.phase != "betting":
            return False
        outcome=self.model.begin_spin()
        now=time.monotonic()
        self._deadline=now
        self._spin_step=0
        target=next(i for i,a in enumerate(ANIMALS) if a.key==outcome.base)
        self._spin_plan=build_spin_plan(target,self._animation_rng)
        self._lit_index=self._spin_plan.start
        self._spin_steps=len(self._spin_plan.indices)
        self._spin_next=now+.14
        return True

    def _settle(self):
        was_settled = self.model.phase == "result"
        try:
            self.model.settle()
        except Exception as exc:
            self._payment_error=True
            logging.error("结算保存失败：%s",exc)
            self.update_display()
            return
        self._payment_error=False
        if not was_settled:
            self._result_started = time.monotonic()
            self._deadline = self._result_started+RESULT_SECONDS
        self.update_display()

    def _tick(self):
        self._job=None
        if self._closed:
            return
        now=time.monotonic()
        if not self._payment_error:
            if self.model.phase=="betting" and now>=self._deadline:
                self._start_spin()
            elif self.model.phase=="betting" and now>=self._idle_next:
                steps = 1+int((now-self._idle_next)//IDLE_LIGHT_SECONDS)
                self._lit_index = (self._lit_index+steps)%8
                self._idle_next += steps*IDLE_LIGHT_SECONDS
            elif self.model.phase=="spinning" and now>=self._spin_next:
                if self._spin_step>=self._spin_steps:
                    self._settle()
                else:
                    self._lit_index=self._spin_plan.indices[self._spin_step]
                    delay=self._spin_plan.delays[self._spin_step]
                    self._spin_step+=1
                    self._spin_next=now+delay
            elif self.model.phase=="result" and now>=self._deadline:
                self.model.next_round()
                self._deadline=now+BETTING_SECONDS
                self._idle_next=now+IDLE_LIGHT_SECONDS
                self._lit_index=secrets.randbelow(8)
                self.update_display()
        stamp=(self.model.phase,math.ceil(self._deadline-now),self._lit_index,
               int(now*4) if self.model.phase=="result" else 0,self._payment_error)
        if stamp!=self._display_stamp:
            self._display_stamp=stamp
            self.draw_scene()
        self._job=self.root.after(20 if self.model.phase=="spinning" else 50,self._tick)

    def update_display(self):
        self.balance_var.set(money(self.model.balance_cents))
        if self.balance!=self._last_notified_balance:
            self._last_notified_balance=self.balance
            if callable(self._on_balance_change):
                try:
                    self._on_balance_change(self.balance)
                except Exception:
                    logging.exception("余额通知回调失败")
        self.draw_scene()

    def _popup(self, key, title, geometry):
        current=self._popups.get(key)
        if current is not None and current.winfo_exists():
            current.lift();current.focus_set()
            return None
        top=tk.Toplevel(self.root)
        top.title(title)
        top.geometry(geometry)
        top.configure(bg=Theme.BG)
        top.transient(self.root.winfo_toplevel())
        self._popups[key]=top
        def close():
            self._popups.pop(key,None)
            top.destroy()
        top.protocol("WM_DELETE_WINDOW",close)
        return top

    def show_rules(self):
        """复用 Blackjack 的侧栏目录、可滚动卡片和表格说明布局。"""
        top=self._popup("rules",f"{GAME_TITLE} · 游戏说明","1000x670")
        if top is None:
            return
        parent=self.root.winfo_toplevel()
        parent.update_idletasks()
        width=min(1000,max(700,top.winfo_screenwidth()-40))
        height=min(670,max(450,top.winfo_screenheight()-40))
        x=max(0,parent.winfo_rootx()+(parent.winfo_width()-width)//2)
        y=max(0,parent.winfo_rooty()+(parent.winfo_height()-height)//2)
        top.geometry(f"{width}x{height}+{x}+{y}")
        top.resizable(False,False)
        bg,header_bg,sidebar_bg=Theme.BG,"#EFE7FC","#F4EAF7"
        panel,alternate,border="white","#F6F1FC",Theme.RIGHT_BORDER
        accent,bar,text,muted=Theme.PURPLE,"#C5AFF0",Theme.INK,Theme.MUTED
        font=Theme.FONT
        pages=instruction_pages()

        def close_dialog():
            self._popups.pop("rules",None)
            top.destroy()
            if not self._closed:
                self.canvas.focus_set()

        header=tk.Frame(top,bg=header_bg,height=76)
        header.pack(fill=tk.X,side=tk.TOP);header.pack_propagate(False)
        tk.Label(header,text=f"{GAME_TITLE} · 游戏说明",font=(font,20,"bold"),
                 fg=accent,bg=header_bg,anchor="w").place(x=24,y=6,width=width-205,height=41)
        tk.Label(header,text="玩法 · 下注 · 获胜条件 · 派对 · 特别事项",font=(font,13),
                 fg=muted,bg=header_bg,anchor="w").place(x=26,y=46)
        tk.Button(header,text="关闭  ESC",command=close_dialog,font=(font,13,"bold"),
                  bg="#E2D6F4",fg=text,activebackground=bar,relief=tk.FLAT,bd=0,
                  cursor="hand2").place(x=width-150,y=17,width=120,height=42)
        tk.Frame(top,bg=bar,height=3).pack(fill=tk.X,side=tk.TOP)
        body=tk.Frame(top,bg=bg);body.pack(fill=tk.BOTH,expand=True)
        sidebar=tk.Frame(body,bg=sidebar_bg,width=205)
        sidebar.pack(side=tk.LEFT,fill=tk.Y);sidebar.pack_propagate(False)
        tk.Label(sidebar,text="说明目录",font=(font,16,"bold"),fg=accent,bg=sidebar_bg,
                 anchor="w").pack(fill=tk.X,padx=18,pady=(17,10))
        scroll_host=tk.Frame(body,bg=bg)
        scroll_host.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
        canvas=tk.Canvas(scroll_host,bg=bg,highlightthickness=0,bd=0,yscrollincrement=36)
        scroll=tk.Scrollbar(scroll_host,orient=tk.VERTICAL,command=canvas.yview,
                            bg="#E3D8F3",troughcolor=bg,activebackground=bar,relief=tk.FLAT,bd=0,width=13)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT,fill=tk.BOTH,expand=True,padx=(10,0),pady=10)
        scroll.pack(side=tk.RIGHT,fill=tk.Y,padx=(0,8),pady=10)
        content=tk.Frame(canvas,bg=bg)
        content_window=canvas.create_window((0,0),window=content,anchor="nw")
        content.bind("<Configure>",lambda _e:canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",lambda e:canvas.itemconfigure(content_window,width=e.width))
        wrap=max(310,width-320)

        def add_rule(card,title,detail):
            row=tk.Frame(card,bg=panel);row.pack(fill=tk.X,padx=16,pady=5)
            tk.Frame(row,bg=bar,width=5).pack(side=tk.LEFT,fill=tk.Y,padx=(0,11))
            box=tk.Frame(row,bg=panel);box.pack(side=tk.LEFT,fill=tk.X,expand=True)
            if title:
                tk.Label(box,text=title,font=(font,14,"bold"),fg=text,bg=panel,
                         anchor="w",justify=tk.LEFT,wraplength=wrap).pack(fill=tk.X)
            if detail:
                tk.Label(box,text=detail,font=(font,13),fg=muted,bg=panel,
                         anchor="w",justify=tk.LEFT,wraplength=wrap).pack(fill=tk.X,pady=(3,0))

        def add_table(card,title,headers,rows):
            block=tk.Frame(card,bg=alternate,highlightbackground=border,highlightthickness=1,bd=0)
            block.pack(fill=tk.X,padx=16,pady=8)
            if title:
                tk.Label(block,text=title,font=(font,14,"bold"),fg=text,bg=bar,anchor="w",
                         padx=11,pady=7).pack(fill=tk.X)
            grid=tk.Frame(block,bg=alternate);grid.pack(fill=tk.X)
            columns=len(headers)
            for col in range(columns):
                grid.grid_columnconfigure(col,weight=1,uniform="rules")
            for row_index,row in enumerate((headers,*rows)):
                cell_bg=bar if row_index==0 else (panel if row_index%2 else alternate)
                for col,value in enumerate(row):
                    tk.Message(grid,text=value,font=(font,13,"bold" if row_index==0 else "normal"),
                               fg=text if row_index==0 else muted,bg=cell_bg,anchor="w",justify=tk.LEFT,
                               width=max(90,wrap//columns-16),padx=7,pady=5,borderwidth=1,
                               relief=tk.SOLID).grid(row=row_index,column=col,sticky="nsew")

        nav=[]
        def render_page(index):
            for child in content.winfo_children():
                child.destroy()
            for i,button in enumerate(nav):
                button.configure(bg="#E5D8F4" if i==index else sidebar_bg,fg=accent if i==index else muted)
            title,subtitle,cards=pages[index]
            page_head=tk.Frame(content,bg=bg);page_head.pack(fill=tk.X,padx=14,pady=(7,2))
            tk.Label(page_head,text=title,font=(font,20,"bold"),fg=accent,bg=bg,
                     anchor="w").pack(fill=tk.X)
            tk.Label(page_head,text=subtitle,font=(font,13),fg=muted,bg=bg,anchor="w",
                     justify=tk.LEFT,wraplength=wrap).pack(fill=tk.X,pady=(3,0))
            for card_title,card_subtitle,rules,tables in cards:
                card=tk.Frame(content,bg=panel,highlightbackground=border,highlightthickness=1,bd=0)
                card.pack(fill=tk.X,padx=10,pady=7)
                head=tk.Frame(card,bg=panel);head.pack(fill=tk.X,padx=16,pady=(12,5))
                tk.Label(head,text=card_title,font=(font,16,"bold"),fg=accent,bg=panel,anchor="w",
                         justify=tk.LEFT,wraplength=wrap).pack(fill=tk.X)
                if card_subtitle:
                    tk.Label(head,text=card_subtitle,font=(font,13),fg=muted,bg=panel,
                             anchor="w",wraplength=wrap).pack(fill=tk.X)
                for rule_title,detail in rules:
                    add_rule(card,rule_title,detail)
                for table_title,headers,rows in tables:
                    add_table(card,table_title,headers,rows)
                tk.Frame(card,bg=panel,height=6).pack(fill=tk.X)
            content.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"));canvas.yview_moveto(0)

        for index,(title,_,_) in enumerate(pages):
            button=tk.Button(sidebar,text=title,command=lambda i=index:render_page(i),font=(font,14),
                             fg=muted,bg=sidebar_bg,activebackground=bar,activeforeground=accent,
                             relief=tk.FLAT,bd=0,anchor="w",padx=18,pady=10,cursor="hand2")
            button.pack(fill=tk.X);nav.append(button)

        def on_wheel(event):
            if event.delta:
                canvas.yview_scroll((-1 if event.delta>0 else 1)*max(1,abs(int(event.delta/120))),"units")
            return "break"

        top.bind("<MouseWheel>",on_wheel)
        top.bind("<Button-4>",lambda _e:(canvas.yview_scroll(-1,"units"),"break")[1])
        top.bind("<Button-5>",lambda _e:(canvas.yview_scroll(1,"units"),"break")[1])
        top.bind("<Escape>",lambda _e:close_dialog())
        top.protocol("WM_DELETE_WINDOW",close_dialog)
        render_page(0)
        top.focus_set()
        return top

    def _cleanup(self):
        if self._closed:
            return
        self._closed=True
        if self._enter_release_job is not None:
            try:
                self.root.after_cancel(self._enter_release_job)
            except tk.TclError:
                pass
            self._enter_release_job=None
        self._enter_held=False
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job=None
        for top in list(self._popups.values()):
            try:
                top.destroy()
            except tk.TclError:
                pass
        self._popups.clear()

    def on_closing(self):
        if self._closed:
            return
        try:
            self.model.prepare_close()
        except Exception as exc:
            messagebox.showerror("余额尚未保存",f"请重试后再离开：\n{exc}",parent=self.root)
            return
        self.update_display()
        self._cleanup()
        finish=getattr(self.root,"finish",None)
        if callable(finish):
            finish(self.balance)
        else:
            self.root.destroy()

    def _on_destroy(self, event):
        if event.widget is not self.root or self._closed:
            return
        # 宿主若直接销毁页面，也处理尚未结束的投注，且取消全部计时器。
        try:
            self.model.prepare_close()
            if callable(self._on_balance_change):
                self._on_balance_change(self.balance)
        except Exception:
            logging.exception("页面销毁时结算失败")
        self._cleanup()


# 保留旧宿主引用的类名；新接入可直接使用 AnimalWheelGame。
FerrisWheelGame = AnimalWheelGame
RocketGame = AnimalWheelGame


def main(
    initial_balance: float = 1000.0,
    username: str = "Guest",
    *,
    parent=None,
    balance: Optional[float] = None,
    user: Optional[str] = None,
    on_back: Optional[Callable[[float], None]] = None,
    on_balance_change: Optional[Callable[[float], None]] = None,
):
    _ensure_account_storage()
    effective_balance=float(balance if balance is not None else initial_balance)
    effective_user=str(user if user is not None else username)
    if parent is not None:
        try:
            from .small_games import EmbeddedGamePage
        except ImportError:
            from small_games import EmbeddedGamePage
        page=EmbeddedGamePage(parent,title=GAME_TITLE,username=effective_user,
                              balance=effective_balance,on_back=on_back,
                              on_balance_change=on_balance_change)
        game=AnimalWheelGame(page.host,effective_balance,effective_user)
        page.attach_game(game)
        return page
    root=tk.Tk()
    game=AnimalWheelGame(root,effective_balance,effective_user,
                    on_balance_change=on_balance_change)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    main(10000.0,"test_user")
