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

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import json
import os
import secrets
import webbrowser
from itertools import combinations, product
from collections import Counter

# =========================================================
# UI 颜色（与 UTH 共用）
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

# ------------------------- 基础数据 -------------------------
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
RANK_VALUES['JOKER'] = 99

HAND_RANK_5 = {
    "五条": 10,
    "皇家同花顺": 9,
    "同花顺": 8,
    "四条": 7,
    "葫芦": 6,
    "同花": 5,
    "顺子": 4,
    "三条": 3,
    "两对": 2,
    "对子": 1,
    "高牌": 0
}

def rank_2_card_value(card):
    if card.is_joker:
        return 14
    return RANK_VALUES[card.rank]

# ------------------------- 辅助函数 -------------------------
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
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user.get('user_name') == username:
            user['cash'] = f"{new_balance:.2f}"
            break
    save_user_data(users)

def card_copy(card):
    new_card = Card(card.suit, card.rank)
    for attr in ('source',):
        if hasattr(card, attr):
            setattr(new_card, attr, getattr(card, attr))
    return new_card

# ------------------------- 卡牌 -------------------------
class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.is_joker = (suit == 'JOKER') or (rank == 'JOKER')
        self.value = 99 if self.is_joker else RANK_VALUES[rank]

    def __repr__(self):
        if self.is_joker:
            return "JOKER"
        return f"{self.rank}{self.suit}"

    def __eq__(self, other):
        return isinstance(other, Card) and self.suit == other.suit and self.rank == other.rank and self.is_joker == other.is_joker

    def __hash__(self):
        return hash((self.suit, self.rank, self.is_joker))

# ------------------------- 牌堆 -------------------------
class Deck:
    def __init__(self):
        try:
            # In a frozen app sys.executable is MyGame.exe, not Python.
            # Call the shared shuffler directly instead of relaunching the app.
            from A_Tools.Card.shuffle import generate_shuffled_deck
            cards, _warnings = generate_shuffled_deck(has_joker=True, deck_count=1)
            self.full_deck = [Card(d["suit"], d["rank"]) for d in cards]
            self.cut_position = secrets.randbelow(len(self.full_deck))
        except Exception:
            self.full_deck = [Card(s, r) for s in SUITS for r in RANKS] + [Card('JOKER', 'JOKER')]
            self._secure_shuffle()
            self.cut_position = secrets.randbelow(len(self.full_deck))
        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + i) % len(self.full_deck) for i in range(len(self.full_deck))]
        self.pointer = 0

    def _secure_shuffle(self):
        for i in range(len(self.full_deck) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            self.full_deck[i], self.full_deck[j] = self.full_deck[j], self.full_deck[i]

    def deal(self, n=1):
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt


# ------------------------- 5张手牌评估（含Joker） -------------------------
def _card_rank_value(card):
    return 14 if card.is_joker else RANK_VALUES[card.rank]


def _sorted_desc(cards):
    return sorted(cards, key=_card_rank_value, reverse=True)


def _straight_high_from_values(values):
    uniq = sorted(set(values))
    if len(uniq) != 5:
        return None
    if uniq == [2, 3, 4, 5, 14]:
        return 5
    if uniq[-1] - uniq[0] == 4:
        return uniq[-1]
    return None


def _evaluate_five_no_joker(cards):
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    is_flush = len(set(suits)) == 1

    straight_high = _straight_high_from_values(values)
    is_straight = straight_high is not None

    freq = Counter(values)
    by_cnt = sorted(freq.items(), key=lambda x: (x[1], x[0]), reverse=True)
    counts = sorted(freq.values(), reverse=True)

    if is_flush and is_straight:
        if set(values) == {10, 11, 12, 13, 14}:
            return "皇家同花顺", HAND_RANK_5["皇家同花顺"], [14]
        return "同花顺", HAND_RANK_5["同花顺"], [straight_high]

    if counts[0] == 5:
        return "五条", HAND_RANK_5["五条"], [by_cnt[0][0]]

    if counts[0] == 4:
        four = by_cnt[0][0]
        kicker = max(v for v in values if v != four)
        return "四条", HAND_RANK_5["四条"], [four, kicker]

    if counts[0] == 3 and counts[1] == 2:
        trips = by_cnt[0][0]
        pair = by_cnt[1][0]
        return "葫芦", HAND_RANK_5["葫芦"], [trips, pair]

    if is_flush:
        return "同花", HAND_RANK_5["同花"], values

    if is_straight:
        return "顺子", HAND_RANK_5["顺子"], [straight_high]

    if counts[0] == 3:
        trips = by_cnt[0][0]
        kickers = sorted([v for v in values if v != trips], reverse=True)
        return "三条", HAND_RANK_5["三条"], [trips] + kickers

    if counts[0] == 2 and counts[1] == 2:
        pair_vals = sorted([v for v, cnt in freq.items() if cnt == 2], reverse=True)
        kicker = max(v for v, cnt in freq.items() if cnt == 1)
        return "两对", HAND_RANK_5["两对"], pair_vals + [kicker]

    if counts[0] == 2:
        pair = by_cnt[0][0]
        kickers = sorted([v for v in values if v != pair], reverse=True)
        return "对子", HAND_RANK_5["对子"], [pair] + kickers

    return "高牌", HAND_RANK_5["高牌"], values


def _best_five_with_joker(cards):
    """
    输入 5 张牌（可含 Joker），返回：
    (牌型名, 牌型值, 比较值列表, 最佳替换后的 5 张牌, 替换后数值列表)

    Joker 规则（按你确认的赌场口径）：
    - Joker 可以代替任意花色和点数，若能组成：
      皇家同花顺 / 同花顺 / 同花 / 顺子，则优先按这些牌型处理
    - 若不能组成上述 4 类牌型，则 Joker 只能当 A 处理
    - 因此：Joker 不能被拿去“自由”凑两对、三条、葫芦、四条等；
      但如果 Joker 当 A 后自然形成这些牌型（例如 AAAA、AAAKK），是允许的
    """
    joker_indices = [i for i, c in enumerate(cards) if c.is_joker]

    if not joker_indices:
        rank_name, rank_val, cmp_vals = _evaluate_five_no_joker(cards)
        return rank_name, rank_val, cmp_vals, [card_copy(c) for c in cards], [c.value for c in cards]

    allowed_special = {"皇家同花顺", "同花顺", "同花", "顺子"}
    possible_values = list(range(2, 15))
    possible_suits = SUITS

    best = None

    for values_combo in product(possible_values, repeat=len(joker_indices)):
        for suits_combo in product(possible_suits, repeat=len(joker_indices)):
            trial = [card_copy(c) for c in cards]

            for idx_pos, card_idx in enumerate(joker_indices):
                trial[card_idx] = Card(suits_combo[idx_pos], RANKS[values_combo[idx_pos] - 2])

            rank_name, rank_val, cmp_vals = _evaluate_five_no_joker(trial)

            # 只有两种情况允许：
            # 1) 所有 Joker 都当 A
            # 2) 形成皇家同花顺 / 同花顺 / 同花 / 顺子
            all_aces = all(RANKS[values_combo[idx_pos] - 2] == 'A' for idx_pos in range(len(joker_indices)))
            if not all_aces and rank_name not in allowed_special:
                continue

            key = (rank_val, cmp_vals)
            if best is None or key > best[0]:
                best = (key, rank_name, rank_val, cmp_vals, trial, [c.value for c in trial])

    if best is None:
        # 极端兜底：全部 Joker 当 A
        trial = [card_copy(c) for c in cards]
        for idx_pos, card_idx in enumerate(joker_indices):
            trial[card_idx] = Card('♠', 'A')
        rank_name, rank_val, cmp_vals = _evaluate_five_no_joker(trial)
        return rank_name, rank_val, cmp_vals, trial, [c.value for c in trial]

    _, rank_name, rank_val, cmp_vals, trial, eff_vals = best
    return rank_name, rank_val, cmp_vals, trial, eff_vals


def best_hand_with_joker(cards):
    """
    兼容 5 张或 7 张牌：
    - 5 张：直接评估
    - 7 张：穷举 21 种 5 张子集，返回最佳 5 张牌型

    返回：
    (牌型名, 牌型值, 比较值列表, 最佳替换后的牌, 替换后数值列表)

    注意：
    - 这里返回的 best_cards / eff_vals 对 7 张输入时，指的是“最佳 5 张子集”的结果
    """
    if len(cards) == 5:
        return _best_five_with_joker(cards)

    if len(cards) == 7:
        best = None
        best_trial = None
        best_eff_vals = None

        for idxs in combinations(range(7), 5):
            subset = [cards[i] for i in idxs]
            rank_name, rank_val, cmp_vals, trial, eff_vals = _best_five_with_joker(subset)
            key = (rank_val, cmp_vals)

            if best is None or key > best[0]:
                best = (key, rank_name, rank_val, cmp_vals)
                best_trial = trial
                best_eff_vals = eff_vals

        if best is None:
            raise ValueError("best_hand_with_joker：7 张牌评估失败")

        _, rank_name, rank_val, cmp_vals = best
        return rank_name, rank_val, cmp_vals, best_trial, best_eff_vals

    raise ValueError("best_hand_with_joker 只接受 5 张或 7 张牌")


def dealer_way_split(hand7):
    """
    按你提供的 House Way 逻辑重写的庄家分牌函数。

    返回:
        (front2, back5)
        front2 -> 前道 2 张
        back5  -> 后道 5 张

    Joker 规则：
    - 本游戏只有 1 张 Joker
    - 如果 Joker 不能用于：
        皇家同花顺 / 同花顺 / 同花 / 顺子
      则 Joker 只能按 A 使用
    - 在前道 2 张里：
        Joker + A => A 对
        两张 Joker => A 对（理论上本游戏不会出现，但保留兜底）
        Joker + 非A => A 高牌
    """

    # =========================================================
    # 基础工具
    # =========================================================
    def rv(card):
        """排序/比较值：Joker 视为 A。"""
        return 14 if card.is_joker else RANK_VALUES[card.rank]

    def sorted_desc(cards):
        """点数从大到小排序，Joker 视为 A。"""
        return sorted(cards, key=lambda c: (rv(c), 1 if c.is_joker else 0), reverse=True)

    def front_eval(front2):
        """
        前道只分：
        - 高牌
        - 对子

        Joker 规则：
        - 两张 Joker => A 对
        - Joker + A => A 对
        - Joker + 非A => 高牌 A-high
        """
        if len(front2) != 2:
            return -1, []

        jokers = [c for c in front2 if c.is_joker]
        naturals = [c for c in front2 if not c.is_joker]

        if len(jokers) == 2:
            return 1, [14]

        if len(jokers) == 1:
            if naturals and naturals[0].rank == 'A':
                return 1, [14]
            if naturals:
                return 0, [14, rv(naturals[0])]
            return 0, [14, 0]

        vals = sorted([rv(c) for c in front2], reverse=True)
        if vals[0] == vals[1]:
            return 1, [vals[0]]
        return 0, vals

    def back_eval(back5):
        """后道 5 张用你现有的 best_hand_with_joker 评估。"""
        rank_name, rank_val, cmp_vals, _, _ = best_hand_with_joker(list(back5))
        return rank_name, rank_val, cmp_vals

    def split_is_legal(front2, back5):
        """后道必须严格大于前道。"""
        _, back_rank, back_cmp = back_eval(back5)
        front_rank, front_cmp = front_eval(front2)

        if back_rank > front_rank:
            return True
        if back_rank < front_rank:
            return False

        for a, b in zip(back_cmp, front_cmp):
            if a > b:
                return True
            if a < b:
                return False
        return False

    def remove_cards(source, cards_to_remove):
        """从 source 中移除 cards_to_remove（按牌面相等移除）。"""
        remaining = list(source)
        for c in cards_to_remove:
            remaining.remove(c)
        return remaining

    def choose_top_two(cards):
        """取两张最大牌。"""
        return sorted_desc(cards)[:2]

    def choose_highest_pair(cards):
        """
        找最大对子。
        Joker 只算 A，因此只允许：
        - A + Joker
        - A + A
        - 其他自然对子
        """
        candidates = []
        for i, j in combinations(range(len(cards)), 2):
            c1, c2 = cards[i], cards[j]
            if c1.is_joker and c2.rank == 'A':
                candidates.append((14, [c1, c2]))
            elif c2.is_joker and c1.rank == 'A':
                candidates.append((14, [c1, c2]))
            elif (not c1.is_joker) and (not c2.is_joker) and c1.rank == c2.rank:
                candidates.append((rv(c1), [c1, c2]))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def choose_lowest_single(cards):
        """取最低单张。"""
        return sorted_desc(cards)[-1]

    def choose_highest_single(cards):
        """取最大单张。"""
        return sorted_desc(cards)[0]

    def build_groups_with_joker_as_ace(cards):
        """
        分组统计：
        - 自然牌按点数分组
        - Joker 先并入 A 组（仅用于统计对/三条/四条/五A）
        """
        groups = {}
        for c in cards:
            groups.setdefault(rv(c), []).append(c)

        for v in groups:
            groups[v].sort(key=rv, reverse=True)

        return groups

    def has_rank_or_joker(cards, threshold):
        """是否存在点数 >= threshold 的牌；Joker 视为 A。"""
        return any(rv(c) >= threshold for c in cards)

    def has_pair_in_cards(cards):
        """判断 3 张牌里是否存在对子（Joker 只跟 A 配对）。"""
        return choose_highest_pair(cards) is not None

    def pairable(a, b):
        """前道/特殊分牌中：两张牌是否能组成对子。"""
        if a.is_joker and b.rank == 'A':
            return True
        if b.is_joker and a.rank == 'A':
            return True
        if (not a.is_joker) and (not b.is_joker) and a.rank == b.rank:
            return True
        return False

    def straight_values_for_length(length):
        """
        生成所有可能的连续点数组合：
        - 允许 A 低：A,2,3,4,5...
        - 允许 A 高：...10,J,Q,K,A
        """
        seqs = []

        # A 低：start = 1
        if length <= 7:
            seqs.append(list(range(1, length + 1)))

        # 一般连续序列：2..14
        for start in range(2, 15 - length + 1):
            seqs.append(list(range(start, start + length)))

        return seqs

    def normalize_card_for_sequence(card, seq_set):
        """
        把单张牌映射到某个顺子序列中的点数：
        - Joker 不能在这里出现（Joker 单独处理）
        - A 根据序列决定是 1 还是 14
        - 非A 只能使用其本身点数
        """
        if card.is_joker:
            return None

        if card.rank == 'A':
            if 1 in seq_set:
                return 1
            if 14 in seq_set:
                return 14
            return None

        v = RANK_VALUES[card.rank]
        if v in seq_set:
            return v
        return None

    def can_form_straight_subset(cards_subset):
        """
        判断某个子集是否能组成“顺子型连续序列”。
        子集大小可以是 5/6/7。
        Joker 最多 1 张，可补任意缺口。
        """
        joker_cnt = sum(1 for c in cards_subset if c.is_joker)
        if joker_cnt > 1:
            return None

        naturals = [c for c in cards_subset if not c.is_joker]

        for seq in straight_values_for_length(len(cards_subset)):
            seq_set = set(seq)
            mapped = set()
            ok = True

            for card in naturals:
                mv = normalize_card_for_sequence(card, seq_set)
                if mv is None:
                    ok = False
                    break
                if mv in mapped:
                    ok = False
                    break
                mapped.add(mv)

            if not ok:
                continue

            missing = seq_set - mapped
            if len(missing) == joker_cnt:
                return seq

        return None

    def can_form_flush_subset(cards_subset):
        """
        判断子集是否可组成同花：
        - 所有非 Joker 牌必须同一花色
        - Joker 可补该花色
        """
        non_jokers = [c for c in cards_subset if not c.is_joker]
        if not non_jokers:
            return None

        suits = {c.suit for c in non_jokers}
        if len(suits) != 1:
            return None

        return next(iter(suits))

    def find_best_royal_or_straight_flush_split():
        """
        先找 5 张牌是否可以组成：
        - 皇家同花顺
        - 同花顺

        只要找到，就保留那 5 张在后道，剩下 2 张在前道。
        """
        target_ranks = {HAND_RANK_5["皇家同花顺"], HAND_RANK_5["同花顺"]}

        best = None

        for idxs in combinations(range(7), 5):
            back_cards = [hand7[i] for i in idxs]
            front_cards = [hand7[i] for i in range(7) if i not in idxs]

            rank_name, rank_val, cmp_vals, _, _ = best_hand_with_joker(back_cards)
            if rank_val not in target_ranks:
                continue

            if not split_is_legal(front_cards, back_cards):
                continue

            front_rank, front_cmp = front_eval(front_cards)
            joker_front_cnt = sum(1 for c in front_cards if c.is_joker)

            key = (
                rank_val,                  # 皇家同花顺 > 同花顺
                tuple(cmp_vals),           # 同型里比高张
                front_rank,                # 前道 pair > high card
                tuple(front_cmp),
                -joker_front_cnt
            )

            if best is None or key > best[0]:
                best = (key, front_cards, back_cards)

        if best is None:
            return None

        return best[1], best[2]

    def find_best_flush_split():
        """
        同花逻辑：
        - 7 张同花：最大的 2 张同花放前道
        - 6 张同花：
            * 如果剩下 1 张能和同花中的 1 张组成对子 -> 前道对子，后道同花
            * 否则 -> 同花中最大的 1 张 + 剩下 1 张放前道，后道同花
        - 5 张同花：
            * 剩下 2 张直接放前道
        """
        best = None

        for k in (7, 6, 5):
            for idxs in combinations(range(7), k):
                subset = [hand7[i] for i in idxs]
                rest = [hand7[i] for i in range(7) if i not in idxs]

                # 关键修正：
                # 如果整手已经是“两对”，则不要用 5 张同花去抢分牌，
                # 交给后面的“两对”分支处理。
                if k == 5 and pair_count == 2:
                    continue

                suit = can_form_flush_subset(subset)
                if suit is None:
                    continue

                subset_sorted = sorted_desc(subset)

                if k == 7:
                    front = subset_sorted[:2]
                    back = [c for c in hand7 if c not in front]

                    if not split_is_legal(front, back):
                        continue

                    front_rank, front_cmp = front_eval(front)
                    back_name, back_rank, back_cmp = back_eval(back)
                    joker_front_cnt = sum(1 for c in front if c.is_joker)

                    key = (
                        7,
                        front_rank,
                        tuple(front_cmp),
                        back_rank,
                        tuple(back_cmp),
                        -joker_front_cnt
                    )

                elif k == 6:
                    if len(rest) != 1:
                        continue
                    lone = rest[0]

                    pair_front = None
                    pair_card_in_subset = None
                    for c in subset:
                        if pairable(c, lone):
                            pair_front = sorted_desc([c, lone])
                            pair_card_in_subset = c
                            break

                    if pair_front is not None:
                        # 取出与 lone 配对的那张同花牌，剩下 5 张仍保持同花
                        back = remove_cards(subset, [pair_card_in_subset])
                        front = pair_front
                    else:
                        # 没有对子，则同花最大一张 + 剩下那张放前道
                        high_card = subset_sorted[0]
                        back = remove_cards(subset, [high_card])
                        front = sorted_desc([high_card, lone])

                    if not split_is_legal(front, back):
                        continue

                    front_rank, front_cmp = front_eval(front)
                    back_name, back_rank, back_cmp = back_eval(back)
                    joker_front_cnt = sum(1 for c in front if c.is_joker)

                    key = (
                        6,
                        front_rank,
                        tuple(front_cmp),
                        back_rank,
                        tuple(back_cmp),
                        -joker_front_cnt
                    )

                else:  # k == 5
                    if len(rest) != 2:
                        continue
                    front = sorted_desc(rest)
                    back = subset

                    if not split_is_legal(front, back):
                        continue

                    front_rank, front_cmp = front_eval(front)
                    back_name, back_rank, back_cmp = back_eval(back)
                    joker_front_cnt = sum(1 for c in front if c.is_joker)

                    key = (
                        5,
                        front_rank,
                        tuple(front_cmp),
                        back_rank,
                        tuple(back_cmp),
                        -joker_front_cnt
                    )

                if best is None or key > best[0]:
                    best = (key, front, back)

        if best is None:
            return None

        return best[1], best[2]

    def find_best_straight_split():
        """
        顺子逻辑：
        - 7 张顺子：
            前道放最大的 2 张，后道剩下 5 张
        - 6 张顺子：
            * 如果剩下 1 张可以在不破坏顺子的情况下与顺子中的一张组成对子
              -> 前道对子，后道保留顺子
            * 否则 -> 前道放顺子中最大的 1 张 + 剩下一张，后道保留顺子
        - 5 张顺子：
            * 剩下 2 张如果是对子 -> 前道对子，后道顺子
            * 否则 -> 前道高牌，后道顺子
        """
        best = None

        for k in (7, 6, 5):
            for idxs in combinations(range(7), k):
                subset = [hand7[i] for i in idxs]
                rest = [hand7[i] for i in range(7) if i not in idxs]

                # 关键修正：
                # 如果整手已经是“两对”，则不要用 5 张顺子去抢分牌，
                # 交给后面的“两对”分支处理。
                if k == 5 and pair_count == 2:
                    continue

                seq = can_form_straight_subset(subset)
                if seq is None:
                    continue

                subset_sorted = sorted_desc(subset)

                if k == 7:
                    # 7 张顺子：前道放最大的 2 张
                    front = subset_sorted[:2]
                    back = [c for c in subset if c not in front]

                    if not split_is_legal(front, back):
                        continue

                    front_rank, front_cmp = front_eval(front)
                    back_name, back_rank, back_cmp = back_eval(back)
                    joker_front_cnt = sum(1 for c in front if c.is_joker)

                    key = (
                        7,
                        front_rank,
                        tuple(front_cmp),
                        back_rank,
                        tuple(back_cmp),
                        -joker_front_cnt
                    )

                elif k == 6:
                    if len(rest) != 1:
                        continue

                    lone = rest[0]

                    # 先尝试：lone + 顺子中的某一张组成对子，
                    # 且移除该顺子牌后，剩下 5 张仍保留顺子
                    pair_front = None
                    pair_card_in_subset = None

                    for c in subset:
                        if not pairable(c, lone):
                            continue

                        back_try = remove_cards(subset, [c])
                        if can_form_straight_subset(back_try) is None:
                            continue

                        pair_front = sorted_desc([c, lone])
                        pair_card_in_subset = c
                        break

                    if pair_front is not None:
                        front = pair_front
                        back = remove_cards(subset, [pair_card_in_subset])
                    else:
                        # 否则：顺子中最大的 1 张 + 剩下一张放前道
                        high_card = subset_sorted[0]
                        back = remove_cards(subset, [high_card])
                        front = sorted_desc([high_card, lone])

                    if not split_is_legal(front, back):
                        continue

                    front_rank, front_cmp = front_eval(front)
                    back_name, back_rank, back_cmp = back_eval(back)
                    joker_front_cnt = sum(1 for c in front if c.is_joker)

                    key = (
                        6,
                        front_rank,
                        tuple(front_cmp),
                        back_rank,
                        tuple(back_cmp),
                        -joker_front_cnt
                    )

                else:  # k == 5
                    if len(rest) != 2:
                        continue

                    front = sorted_desc(rest)
                    back = subset

                    if not split_is_legal(front, back):
                        continue

                    front_rank, front_cmp = front_eval(front)
                    back_name, back_rank, back_cmp = back_eval(back)
                    joker_front_cnt = sum(1 for c in front if c.is_joker)

                    key = (
                        5,
                        front_rank,
                        tuple(front_cmp),
                        back_rank,
                        tuple(back_cmp),
                        -joker_front_cnt
                    )

                if best is None or key > best[0]:
                    best = (key, front, back)

        if best is None:
            return None

        return best[1], best[2]

    def find_best_exhaustive_legal_split():
        """
        最终兜底：穷举所有 2 + 5 切法，找一个合法切法。
        评分原则：
        - 后道尽量强
        - 前道尽量弱
        - 前道尽量少放 Joker
        """
        best = None

        for back_idxs in combinations(range(7), 5):
            back = [hand7[i] for i in back_idxs]
            front = [hand7[i] for i in range(7) if i not in back_idxs]

            if not split_is_legal(front, back):
                continue

            front_rank, front_cmp = front_eval(front)
            back_name, back_rank, back_cmp = back_eval(back)
            joker_front_cnt = sum(1 for c in front if c.is_joker)

            key = (
                back_rank,
                tuple(back_cmp),
                -front_rank,
                tuple(-x for x in front_cmp),
                -joker_front_cnt
            )

            if best is None or key > best[0]:
                best = (key, front, back)

        if best is None:
            # 理论兜底：按原始点数切
            sorted7 = sorted_desc(hand7)
            front = sorted7[1:3]
            back = [sorted7[0]] + sorted7[3:]
            return front, back

        return best[1], best[2]

    # =========================================================
    # 先做分组统计
    # =========================================================
    naturals = [c for c in hand7 if not c.is_joker]
    jokers = [c for c in hand7 if c.is_joker]

    groups = build_groups_with_joker_as_ace(naturals)

    # Joker 先并入 A 组，用于对子/三条/四条/五A判断
    if jokers:
        groups.setdefault(14, [])
        groups[14].extend(jokers)

    for v in groups:
        groups[v].sort(key=rv, reverse=True)

    pair_values = sorted([v for v, cs in groups.items() if len(cs) == 2], reverse=True)
    trip_values = sorted([v for v, cs in groups.items() if len(cs) == 3], reverse=True)
    quad_values = sorted([v for v, cs in groups.items() if len(cs) == 4], reverse=True)

    pair_count = len(pair_values)
    trip_count = len(trip_values)
    quad_count = len(quad_values)

    # =========================================================
    # 1) Five Aces
    #    4 张A + 1张Joker 时，按“五条A”处理
    #    前道优先放两张自然A，Joker 留后道
    # =========================================================
    ace_total = len(groups.get(14, []))
    if ace_total >= 5:
        ace_cards = groups[14]
        natural_aces = [c for c in ace_cards if (not c.is_joker) and c.rank == 'A']

        if len(natural_aces) >= 2:
            front = natural_aces[:2]
        else:
            # 兜底：例如极端情况下只有A+Joker可用
            front = ace_cards[:2]

        back = [c for c in hand7 if c not in front]
        if split_is_legal(front, back):
            return front, back

        return find_best_exhaustive_legal_split()

    # =========================================================
    # 2) Royal Flush / Straight Flush
    #    若整手属于“两对”结构，按 House Way 的两对规则处理；
    #    否则优先把皇家同花顺 / 同花顺保留在后道。
    # =========================================================
    if pair_count != 2:
        sf_split = find_best_royal_or_straight_flush_split()
        if sf_split is not None:
            front, back = sf_split
            if split_is_legal(front, back):
                return front, back

    # =========================================================
    # 3) Four of a Kind
    #
    # 你的新规则：
    # 1. 如果剩下3张中有对子，对子放前道，四条+剩下1张放后道
    # 2. 如果剩下3张中没有对子：
    #    - 四条是A：
    #        * 如果剩下3张中有K/A/包括Joker -> 前道放剩下3张中最大两张，后道四条+最小1张
    #        * 如果没有K/A/包括Joker -> 四条拆成两对，前道一对，后道一对+剩下3张
    #    - 四条是[J/10/9]：
    #        * 如果剩下3张中有K或A（包括Joker） -> 前道放剩下3张中最大两张，后道四条+最小1张
    #        * 如果没有K/A/包括Joker -> 四条拆成两对，前道一对，后道一对+剩下3张
    #    - 四条是[8/7/6]：
    #        * 如果剩下3张中有Q/K/A（包括Joker） -> 前道放剩下3张中最大两张，后道四条+最小1张
    #        * 如果没有Q/K/A/包括Joker -> 四条拆成两对，前道一对，后道一对+剩下3张
    #    - 四条是[5/4/3/2]：
    #        * 后道会是四条+剩下3张中最低点数的1张
    # =========================================================
    if quad_count == 1:
        quad_val = quad_values[0]
        quad_cards = groups[quad_val][:4]
        others = [c for c in hand7 if c not in quad_cards]
        others_sorted = sorted_desc(others)

        def _best_pair_in_others():
            return choose_highest_pair(others_sorted)

        def _front_top_two_from_others():
            return choose_top_two(others_sorted)

        def _back_lowest_card_from_others():
            return others_sorted[-1] if others_sorted else None

        def _split_quad_into_two_pairs():
            # 前道放四条中的前两张，后道放剩下两张 + 其他三张
            front = quad_cards[:2]
            back = [c for c in hand7 if c not in front]
            if split_is_legal(front, back):
                return front, back
            return None

        def _keep_quad_back_with_lowest():
            # 前道放剩下3张中最大的两张，后道四条 + 最低一张
            if len(others_sorted) < 3:
                return None
            lowest = _back_lowest_card_from_others()
            front = _front_top_two_from_others()
            back = quad_cards + [lowest]
            if split_is_legal(front, back):
                return front, back
            return None

        # ---------------------------------------------
        # 先检查“剩下3张中有对子”
        # ---------------------------------------------
        pair_front = _best_pair_in_others()
        if pair_front is not None:
            front = pair_front
            back = [c for c in hand7 if c not in front]
            if split_is_legal(front, back):
                return front, back

            # 若合法性不通过，直接尝试兜底
            return find_best_exhaustive_legal_split()

        # ---------------------------------------------
        # 没有对子时，进入四条点数分支
        # ---------------------------------------------
        high_set_13 = any(rv(c) >= 13 for c in others_sorted)  # K / A / Joker(A)
        high_set_12 = any(rv(c) >= 12 for c in others_sorted)  # Q / K / A / Joker(A)

        # 四条 A
        if quad_val == 14:
            # 若剩余3张中存在 K/A/Joker，则前道取剩余3张中最大的两张，后道四条+最低1张
            if high_set_13:
                kept = _keep_quad_back_with_lowest()
                if kept is not None:
                    return kept

            # 否则四条拆成两对
            split = _split_quad_into_two_pairs()
            if split is not None:
                return split

            return find_best_exhaustive_legal_split()

        # 四条 J / 10 / 9
        if quad_val in (11, 10, 9):
            if high_set_13:
                kept = _keep_quad_back_with_lowest()
                if kept is not None:
                    return kept

            split = _split_quad_into_two_pairs()
            if split is not None:
                return split

            return find_best_exhaustive_legal_split()

        # 四条 8 / 7 / 6
        if quad_val in (8, 7, 6):
            if high_set_12:
                kept = _keep_quad_back_with_lowest()
                if kept is not None:
                    return kept

            split = _split_quad_into_two_pairs()
            if split is not None:
                return split

            return find_best_exhaustive_legal_split()

        # 四条 5 / 4 / 3 / 2
        if quad_val in (5, 4, 3, 2):
            kept = _keep_quad_back_with_lowest()
            if kept is not None:
                return kept

            # 理论兜底：若 back + lowest 失败，再试拆成两对
            split = _split_quad_into_two_pairs()
            if split is not None:
                return split

            return find_best_exhaustive_legal_split()

    # =========================================================
    # 3) 葫芦 + 对子（3条 + 2个对子）
    #    就把最大的对子放前道，剩下 5 张放在后道
    # =========================================================
    if trip_count >= 1 and pair_count >= 2:
        pair_val = pair_values[0]
        front = groups[pair_val][:2]
        back = [c for c in hand7 if c not in front]
        if split_is_legal(front, back):
            return front, back
        return find_best_exhaustive_legal_split()

    # =========================================================
    # 4) 两组三条（2个3条 + 散牌1张）
    #    把最大的三条拆成对子放前道
    # =========================================================
    if trip_count >= 2:
        high_trip = trip_values[0]
        front = groups[high_trip][:2]
        back = [c for c in hand7 if c not in front]
        if split_is_legal(front, back):
            return front, back
        return find_best_exhaustive_legal_split()

    # =========================================================
    # 5) 葫芦（3条 + 1个对子）
    #    把对子放前道，三条 + 剩下 2 张散牌放后道
    # =========================================================
    if trip_count >= 1 and pair_count >= 1:
        pair_val = pair_values[0]
        front = groups[pair_val][:2]
        back = [c for c in hand7 if c not in front]
        if split_is_legal(front, back):
            return front, back
        return find_best_exhaustive_legal_split()

    # =========================================================
    # 6) 同花
    #    - 7 张同花：最大的 2 张同花放前道
    #    - 6 张同花：
    #        * 如果剩下的 1 张能和同花中的某张组成对子 -> 前道对子，后道同花
    #        * 否则 -> 同花中最大的 1 张 + 剩下一张放前道，后道同花
    #    - 5 张同花：剩下的 2 张放前道
    # =========================================================
    flush_split = find_best_flush_split()
    if flush_split is not None:
        front, back = flush_split
        if split_is_legal(front, back):
            return front, back

    # =========================================================
    # 7) 顺子
    #    - 7 张顺子：前道放最大的 2 张，后道放剩下 5 张
    #    - 6 张顺子：
    #        * 如果剩下 1 张可以在不破坏顺子的情况下组成对子 -> 前道对子，后道保留顺子
    #        * 否则 -> 前道放顺子中最大的 1 张 + 剩下一张，后道保留顺子
    #    - 5 张顺子：
    #        * 剩下 2 张若是对子 -> 前道对子，后道顺子
    #        * 否则 -> 前道高牌，后道顺子
    # =========================================================
    straight_split = find_best_straight_split()
    if straight_split is not None:
        front, back = straight_split
        if split_is_legal(front, back):
            return front, back

    # =========================================================
    # 8) 三条 A
    #    前道放一张 A 和最大的散牌，剩下 5 张放后道
    # =========================================================
    if trip_count == 1:
        trip_val = trip_values[0]
        trip_cards = groups[trip_val][:3]
        others = [c for c in hand7 if c not in trip_cards]
        others_sorted = sorted_desc(others)

        if trip_val == 14:
            one_trip = next((c for c in trip_cards if c.rank == 'A'), trip_cards[0])
            top_other = others_sorted[0]
            front = [one_trip, top_other]
        else:
            # =================================================
            # 9) 剩下的三条
            #    前道放最大的 2 张散牌，剩下 5 张放后道
            # =================================================
            front = choose_top_two(others_sorted)

        back = [c for c in hand7 if c not in front]
        if split_is_legal(front, back):
            return front, back

        return find_best_exhaustive_legal_split()

    # =========================================================
    # 10) 三对
    #    最强的一对放前道，剩下两对 + 剩下的散牌放后道
    # =========================================================
    if pair_count >= 3:
        high_pair = pair_values[0]
        front = groups[high_pair][:2]
        back = [c for c in hand7 if c not in front]
        if split_is_legal(front, back):
            return front, back
        return find_best_exhaustive_legal_split()

    # =========================================================
    # 11) 两对
    #    规则修正版：
    #    1. 最大的对子点数是 [A/K/Q]，前道会是较小的对子。
    #
    #    2. 最大的对子点数是 [J/10/9]：
    #       - 如果剩下 3 张中有 [A/Joker]，
    #         两对 + 剩下 3 张中最小的 1 张 放在后道，
    #         前道放剩下的 2 张。
    #       - 如果剩下 3 张中没有 [A/Joker]，
    #         拆开两对，最小的对子放在前道。
    #
    #    3. 最大的对子点数是 [8/7/6]：
    #       - 如果剩下 3 张中有 [K/A/Joker]，
    #         两对 + 剩下 3 张中最小的 1 张 放在后道，
    #         前道放剩下的 2 张。
    #       - 如果剩下 3 张中没有 [K/A/Joker]，
    #         拆开两对，最小的对子放在前道。
    #
    #    4. 最大的对子点数是 [5/4/3]：
    #       - 如果剩下 3 张中有 [Q/K/A/Joker]，
    #         两对 + 剩下 3 张中最小的 1 张 放在后道，
    #         前道放剩下的 2 张。
    #       - 如果剩下 3 张中没有 [Q/K/A/Joker]，
    #         拆开两对，最小的对子放在前道。
    # =========================================================
    if pair_count == 2:
        big_pair_val, small_pair_val = pair_values[0], pair_values[1]
        big_pair_cards = groups[big_pair_val][:2]
        small_pair_cards = groups[small_pair_val][:2]

        remaining = [c for c in hand7 if c not in big_pair_cards and c not in small_pair_cards]
        remaining_sorted = sorted_desc(remaining)

        # A/K/Q 两对：前道较小对子
        if big_pair_val >= 12:
            front = small_pair_cards
            back = [c for c in hand7 if c not in front]
            if split_is_legal(front, back):
                return front, back
            return find_best_exhaustive_legal_split()

        # J/10/9 两对
        if big_pair_val >= 9:
            # 只要剩下3张里有 A 或 Joker：
            # 后道保留两对 + 剩下3张中最小的1张
            if has_rank_or_joker(remaining_sorted, 14):
                low_one = min(remaining, key=rv)
                back = big_pair_cards + small_pair_cards + [low_one]
                front = [c for c in hand7 if c not in back]

                if split_is_legal(front, back):
                    return front, back

            # 否则：拆开两对，前道放最小的对子
            front = small_pair_cards
            back = [c for c in hand7 if c not in front]
            if split_is_legal(front, back):
                return front, back

            return find_best_exhaustive_legal_split()

        # 8/7/6 两对
        if big_pair_val >= 6:
            # 只要剩下3张里有 K / A / Joker：
            # 后道保留两对 + 剩下3张中最小的1张
            if has_rank_or_joker(remaining_sorted, 13):
                low_one = min(remaining, key=rv)
                back = big_pair_cards + small_pair_cards + [low_one]
                front = [c for c in hand7 if c not in back]

                if split_is_legal(front, back):
                    return front, back

            # 否则：拆开两对，前道放最小的对子
            front = small_pair_cards
            back = [c for c in hand7 if c not in front]
            if split_is_legal(front, back):
                return front, back

            return find_best_exhaustive_legal_split()

        # 5/4/3 两对
        if big_pair_val <= 5:
            # 只要剩下3张里有 Q / K / A / Joker：
            # 后道保留两对 + 剩下3张中最小的1张
            if has_rank_or_joker(remaining_sorted, 12):
                low_one = min(remaining, key=rv)
                back = big_pair_cards + small_pair_cards + [low_one]
                front = [c for c in hand7 if c not in back]

                if split_is_legal(front, back):
                    return front, back

            # 否则：拆开两对，前道放最小的对子
            front = small_pair_cards
            back = [c for c in hand7 if c not in front]
            if split_is_legal(front, back):
                return front, back

            return find_best_exhaustive_legal_split()

    # =========================================================
    # 12) 一对
    #    前道放最大的 2 张散牌，对子和剩下 3 张放后道
    # =========================================================
    if pair_count == 1:
        pair_val = pair_values[0]
        pair_cards = groups[pair_val][:2]
        others = [c for c in hand7 if c not in pair_cards]
        others_sorted = sorted_desc(others)
        front = choose_top_two(others_sorted)
        back = [c for c in hand7 if c not in front]

        if split_is_legal(front, back):
            return front, back
        return find_best_exhaustive_legal_split()

    # =========================================================
    # 13) 高牌
    #    前道放最大的第 2 和第 3 大的散牌，剩下 5 张放后道
    # =========================================================
    sorted7_orig = sorted_desc(hand7)
    front = sorted7_orig[1:3]
    back = [sorted7_orig[0]] + sorted7_orig[3:]

    if split_is_legal(front, back):
        return front, back

    return find_best_exhaustive_legal_split()

def sort_hand_for_display(hand):
    """
    用于 UI 显示排序。

    规则：
    - 5 张牌：按最佳牌型的“展示顺序”排序
    - 7 张牌：只做稳定的点数升序显示，避免把 5 张最佳子集的 eff_vals
      错套到 7 张原始牌上
    """
    if len(hand) == 7:
        # 7 张手牌显示时，不做“最佳 5 张”映射排序，
        # 直接按点数升序排，Joker 当 A 处理
        return sorted(
            hand,
            key=lambda c: (rank_2_card_value(c), 1 if c.is_joker else 0)
        )

    if len(hand) != 5:
        return sorted(hand, key=lambda c: rank_2_card_value(c))

    rank_name, rank_val, cmp_vals, best_cards, eff_vals = best_hand_with_joker(hand)

    # 理论兜底：若返回长度异常，就退回原始点数排序
    if not eff_vals or len(eff_vals) != len(hand):
        return sorted(hand, key=lambda c: rank_2_card_value(c), reverse=True)

    cards_with_eff = [(card, eff_vals[i]) for i, card in enumerate(hand)]

    # 顺子 / 同花 / 同花顺 / 皇家同花顺：按点数升序显示更直观
    if rank_val in (HAND_RANK_5["皇家同花顺"], HAND_RANK_5["同花顺"], HAND_RANK_5["顺子"]):
        values = [x[1] for x in cards_with_eff]

        # A-2-3-4-5 轮子顺，A 要放到最前
        if set(values) == {14, 2, 3, 4, 5}:
            cards_with_eff.sort(key=lambda x: (0 if x[1] == 14 else x[1]))
        else:
            cards_with_eff.sort(key=lambda x: x[1])

        return [x[0] for x in cards_with_eff]

    # 其他牌型：按“组别优先，点数其次”显示
    counter = Counter(x[1] for x in cards_with_eff)
    cards_with_eff.sort(key=lambda x: (counter[x[1]], x[1]), reverse=True)
    return [x[0] for x in cards_with_eff]


def compare_5_hand(hand1, hand2):
    h1 = best_hand_with_joker(hand1)
    h2 = best_hand_with_joker(hand2)
    if h1[1] > h2[1]:
        return 1
    if h1[1] < h2[1]:
        return -1
    for a, b in zip(h1[2], h2[2]):
        if a > b:
            return 1
        if a < b:
            return -1
    return 0


def _best_two_card_hand(hand2):
    """
    返回 (牌型等级, 比较值列表)
    牌型等级：对子=1，高牌=0

    严格 Joker 规则：
    - 单个 Joker 视为 A
    - 只有当另一张牌本身就是 A 时，才构成 A 对
    - Joker 不再能“自动”跟任何点数配对
    """
    jokers = [c for c in hand2 if c.is_joker]
    non_jokers = [c for c in hand2 if not c.is_joker]

    if len(jokers) == 0:
        vals = sorted([rank_2_card_value(c) for c in hand2], reverse=True)
        if vals[0] == vals[1]:
            return 1, [vals[0]]
        return 0, vals

    if len(jokers) == 2:
        return 1, [14]

    other = non_jokers[0]
    if other.rank == 'A':
        return 1, [14]

    return 0, [14, rank_2_card_value(other)]


def compare_2_hand(hand1, hand2):
    t1, cmp1 = _best_two_card_hand(hand1)
    t2, cmp2 = _best_two_card_hand(hand2)

    if t1 > t2:
        return 1
    if t1 < t2:
        return -1

    for a, b in zip(cmp1, cmp2):
        if a > b:
            return 1
        if a < b:
            return -1
    return -1


# ------------------------- 边注赔付 -------------------------
PAIGOW_INSURANCE_PAYOUT = {
    9: 100, 10: 40, 11: 10, 12: 7, 13: 6, 14: 3
}

def get_pai_gow_insurance_payout(hand7):
    """
    牌九保险赔付：只有当7张牌的最佳5张牌型为“高牌”时，才根据最大点数赔付。
    返回净赔率（例如 Q 高牌返回 7，表示下注10赢70）。
    """
    rank_name, rank_val, cmp_vals, _, _ = best_hand_with_joker(hand7)
    if rank_val != 0:
        return 0
    max_val = cmp_vals[0]
    return PAIGOW_INSURANCE_PAYOUT.get(max_val, 0)


def emperor_treasure_payout(hand7, bet):
    # Natural 7 cards straight flush
    if all(not c.is_joker for c in hand7):
        suits = [c.suit for c in hand7]
        if len(set(suits)) == 1:
            values = sorted([c.value for c in hand7])
            if values[-1] - values[0] == 6 and len(set(values)) == 7:
                return bet * 5001
            if values == [2, 3, 4, 5, 6, 7, 14]:
                return bet * 5001

    # 7 cards straight flush with Joker
    joker_cnt = sum(1 for c in hand7 if c.is_joker)
    if joker_cnt > 0:
        suits = [c.suit for c in hand7 if not c.is_joker]
        if suits:
            suit_counts = Counter(suits)
            target_suit = suit_counts.most_common(1)[0][0]
            if all(c.suit == target_suit for c in hand7 if not c.is_joker) or len(set(suits)) == 1:
                real_values = [c.value for c in hand7 if not c.is_joker]
                for start in range(2, 15 - 6 + 1):
                    needed = set(range(start, start + 7))
                    if all(v in needed for v in real_values) and len(needed - set(real_values)) == joker_cnt:
                        return bet * 1001
                needed = {14, 2, 3, 4, 5, 6, 7}
                if all(v in needed for v in real_values) and len(needed - set(real_values)) == joker_cnt:
                    return bet * 1001

    # 5 cards A
    aces = [c for c in hand7 if c.rank == 'A']
    jokers = [c for c in hand7 if c.is_joker]
    if len(aces) + len(jokers) >= 5:
        return bet * 501

    # best 5-card hand
    best = None
    for combo in combinations(hand7, 5):
        rank_name, rank_val, cmp_vals, _, _ = best_hand_with_joker(list(combo))
        if best is None or (rank_val, cmp_vals) > (best[1], best[2]):
            best = (rank_name, rank_val, cmp_vals)

    if best is None:
        return 0

    rank_val = best[1]
    payout_map = {10: 500, 9: 150, 8: 50, 7: 25, 6: 5, 5: 4, 3: 3, 4: 2}
    if rank_val == 0:
        max_val = best[2][0] if best[2] else 0
        if max_val == 9:
            return bet * 41
        if max_val == 10:
            return bet * 6
        if max_val == 11:
            return bet * 3
    if rank_val in payout_map:
        return bet * (payout_map[rank_val] + 1)
    return 0


# ======================= 新增边注赔付函数 =======================
def johor_payout(hand7):
    """
    柔佛州边注赔付（净赔率）
    规则：
    1) 6张同色（全黑或全红）+ 1张鬼牌 -> 30:1
    2) 7张全部同色（无鬼牌） -> 10:1
    3) 至少有一张鬼牌 -> 5:1
    注：按优先级取最大赔率，互斥。
    """
    jokers = [c for c in hand7 if c.is_joker]
    non_jokers = [c for c in hand7 if not c.is_joker]

    # 条件3：至少一张鬼牌（最宽松，但若满足更高条件会被覆盖）
    has_joker = len(jokers) > 0

    # 颜色判断：黑色(♠♣) 红色(♥♦)
    def is_black(card):
        return card.suit in ('♠', '♣')
    def is_red(card):
        return card.suit in ('♥', '♦')

    blacks = [c for c in non_jokers if is_black(c)]
    reds = [c for c in non_jokers if is_red(c)]
    # 条件1：6张同色（全黑或全红）+ 1张鬼牌
    if has_joker and (len(blacks) == 6 or len(reds) == 6):
        return 30
    # 条件2：7张全部同色（无鬼牌）
    if not has_joker and (len(blacks) == 7 or len(reds) == 7):
        return 10
    # 条件3：至少一张鬼牌
    if has_joker:
        return 5
    return 0


def ace_high_push_payout(player_hand, dealer_hand):
    """
    A高平手边注赔付（净赔率），仅在免佣模式下调用。
    规则：
    1) 玩家和庄家都是 Ace 高牌 -> 40:1
    2) 庄家是有小丑牌的 Ace 高牌（玩家不是） -> 15:1
    3) 庄家是没有小丑牌的 Ace 高牌（玩家不是） -> 5:1
    注：按优先级取第一个满足的条件。
    """
    # 判断手牌是否为 Ace 高牌（7张中最佳5张为“高牌”且最大牌为A）
    def is_ace_high(hand):
        rank_name, rank_val, cmp_vals, _, _ = best_hand_with_joker(hand)
        return rank_val == 0 and cmp_vals[0] == 14

    player_ace_high = is_ace_high(player_hand)
    dealer_ace_high = is_ace_high(dealer_hand)

    if player_ace_high and dealer_ace_high:
        return 40
    if dealer_ace_high:
        # 判断庄家 Ace 高牌中是否包含 Joker
        dealer_has_joker = any(c.is_joker for c in dealer_hand)
        if dealer_has_joker:
            return 15
        else:
            return 5
    return 0

# ------------------------- 游戏逻辑 -------------------------
class PaiGowPoker:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.player_hand = []
        self.dealer_hand = []
        self.player_low = []
        self.player_high = []
        self.dealer_low = []
        self.dealer_high = []
        self.ante = 0
        self.pai_gow_insurance = 0
        self.emperor_treasure = 0
        self.johor_bet = 0          # 新增
        self.ace_high_push_bet = 0  # 新增
        self.stage = "betting"
        self.player_split_done = False

    def deal_initial(self):
        self.player_hand = self.deck.deal(7)
        self.dealer_hand = self.deck.deal(7)

# ------------------------- GUI -------------------------
import random
import math
import time
import subprocess
import sys


# =========================================================
# Pai Gow 玩法适配：界面与通用交互沿用 UTH，评牌及赔率沿用原牌九文件。
# =========================================================
GAME_MODE_NAMES = {'classic': '经典模式', 'commission_free': '免佣模式'}
BET_NAMES = {'ante': '底注', 'insurance': '牌九保险', 'emperor': '皇帝之财',
             'johor': '柔佛州', 'ace_push': 'A高平手'}


class PaiGowTableGame:
    """两手玩家共用一位庄家、一副含 Joker 的牌及同一个账户。"""
    SEATS = ('Player1', 'Player2')

    def __init__(self, mode='classic'):
        if mode not in GAME_MODE_NAMES:
            raise ValueError('未知游戏模式。')
        self.mode = mode
        self.reset_game()

    @staticmethod
    def empty_bet():
        return {kind: 0.0 for kind in BET_NAMES}

    @staticmethod
    def limits(high_bet_mode=False):
        return (100, 50000, 12500) if high_bet_mode else (10, 25000, 2500)

    def reset_game(self):
        self.deck = None
        self.hands = {s: [] for s in self.SEATS}
        self.dealer_hand, self.dealer_low, self.dealer_high = [], [], []
        self.deal_sequence = []
        self.bets = {s: self.empty_bet() for s in self.SEATS}
        self.decisions = {s: 'inactive' for s in self.SEATS}
        self.splits = {}
        self.refunded_bets = {}
        self.stage = 'betting'
        self.settlement = None
        self._dealer_evaluation = None

    def set_mode(self, mode):
        if self.stage != 'betting':
            raise ValueError('请在本局结束后切换模式。')
        if mode not in GAME_MODE_NAMES:
            raise ValueError('未知游戏模式。')
        self.mode = mode

    def start_round(self, bets, balance, high_bet_mode=False):
        if self.stage != 'betting':
            raise ValueError('本局尚未结束。')
        minimum, maximum, side_max = self.limits(high_bet_mode)
        prepared, refunded = {}, {}
        for seat in self.SEATS:
            try:
                b = {k: float(bets[seat].get(k, 0)) for k in BET_NAMES}
            except (KeyError, TypeError, ValueError, OverflowError):
                raise ValueError('请输入有效的下注金额。') from None
            if any(not math.isfinite(v) or v < 0 for v in b.values()):
                raise ValueError('下注金额必须是有限的非负数。')
            b = {k: round(v, 2) for k, v in b.items()}
            if not b['ante']:
                if any(b.values()):
                    refunded[seat] = dict(b)
                prepared[seat] = self.empty_bet()
                continue
            if not minimum <= b['ante'] <= maximum:
                raise ValueError(f'每手底注须为 ${minimum:,} 至 ${maximum:,}。')
            if any(b[k] > side_max for k in BET_NAMES if k != 'ante'):
                raise ValueError(f'每项边注最高 ${side_max:,}。')
            if self.mode == 'classic' and b['ace_push']:
                raise ValueError('A高平手边注只在免佣模式开放。')
            prepared[seat] = b
        if not any(b['ante'] for b in prepared.values()):
            raise ValueError('请至少为一手牌下底注，不能只购买边注。')
        charged = round(sum(sum(b.values()) for b in prepared.values()), 2)
        if not math.isfinite(balance) or charged > balance:
            raise ValueError('余额不足以支付本局全部下注。')
        deck = Deck()
        active = tuple(s for s in self.SEATS if prepared[s]['ante'])
        sequence = [(side, index) for index in range(7) for side in (*active, 'Dealer')]
        hands, dealer = {s: [] for s in self.SEATS}, []
        for side, _ in sequence:
            card = deck.deal(1)[0]
            (dealer if side == 'Dealer' else hands[side]).append(card)
        self.deck, self.hands, self.dealer_hand = deck, hands, dealer
        self.deal_sequence, self.bets, self.refunded_bets = sequence, prepared, refunded
        self.decisions = {s: 'pending' if prepared[s]['ante'] else 'inactive' for s in self.SEATS}
        self.splits, self.dealer_low, self.dealer_high = {}, [], []
        self.settlement, self.stage = None, 'dealing'
        return charged

    @staticmethod
    def split_is_legal(low, high):
        # 与原 Pai Gow 的 submit_split / House Way 使用同一严格比较规则。
        _, high_rank, high_cmp, _, _ = best_hand_with_joker(high)
        low_rank, low_cmp = _best_two_card_hand(low)
        if high_rank != low_rank:
            return high_rank > low_rank
        for h, l in zip(high_cmp, low_cmp):
            if h != l:
                return h > l
        return False

    def split_dealer(self):
        if not self.dealer_low:
            self.dealer_low, self.dealer_high = dealer_way_split(self.dealer_hand)
        return self.dealer_low, self.dealer_high

    def dealer_is_ace_high(self):
        if self._dealer_evaluation is None:
            self._dealer_evaluation = best_hand_with_joker(self.dealer_hand)
        rank = self._dealer_evaluation
        return rank[1] == 0 and rank[2][0] == 14

    def submit_split(self, seat, low_indices):
        if self.stage != 'decision' or self.decisions.get(seat) != 'pending':
            raise ValueError('这手牌当前不能分牌。')
        if (len(low_indices) != 2 or len(set(low_indices)) != 2 or
                any(type(i) is not int or not 0 <= i < 7 for i in low_indices)):
            raise ValueError('请选择两张牌作为前道。')
        hand = self.hands[seat]
        low = [hand[i] for i in low_indices]
        high = [c for i, c in enumerate(hand) if i not in low_indices]
        valid = self.split_is_legal(low, high)
        self.splits[seat] = dict(low=low, high=high, valid=valid)
        self.decisions[seat] = 'submitted'
        return valid

    def compare_split(self, seat):
        """同一份比牌结果用于玩家牌型配色和最终结算。"""
        self.split_dealer()
        split = self.splits[seat]
        low_result = compare_2_hand(split['low'], self.dealer_low)
        high_result = compare_5_hand(split['high'], self.dealer_high)
        # 同道同点算庄家赢。
        low_result = -1 if low_result == 0 else low_result
        high_result = -1 if high_result == 0 else high_result
        dealer_ace_high = self.dealer_is_ace_high()
        if not split['valid']:
            winner = 'invalid'
        elif self.mode == 'commission_free' and dealer_ace_high:
            winner = 'push'
        elif low_result > 0 and high_result > 0:
            winner = 'player'
        elif low_result < 0 and high_result < 0:
            winner = 'dealer'
        else:
            winner = 'push'
        return dict(winner=winner, valid_split=split['valid'], low_result=low_result,
                    high_result=high_result, dealer_ace_high=dealer_ace_high)

    def settle(self):
        if self.settlement is not None:
            return self.settlement
        if self.stage != 'showdown' or 'pending' in self.decisions.values():
            raise ValueError('所有已下注手牌须先提交分牌。')
        self.split_dealer()
        free = self.mode == 'commission_free'
        outcomes = {}
        for seat in self.SEATS:
            if self.decisions[seat] == 'inactive':
                continue
            b, hand = self.bets[seat], self.hands[seat]
            comparison = self.compare_split(seat)
            winner = comparison['winner']
            details = self.empty_bet()
            details['ante'] = (b['ante'] * (2 if free else 1.95) if winner == 'player'
                               else b['ante'] if winner == 'push' else 0.0)
            insurance = get_pai_gow_insurance_payout(hand) if b['insurance'] else 0
            if insurance:
                details['insurance'] = b['insurance'] * (insurance + 1)
            if b['emperor']:
                details['emperor'] = emperor_treasure_payout(hand, b['emperor'])
            johor = johor_payout(hand) if b['johor'] else 0
            if johor:
                details['johor'] = b['johor'] * (johor + 1)
            ace_push = ace_high_push_payout(hand, self.dealer_hand) if free and b['ace_push'] else 0
            if ace_push:
                details['ace_push'] = b['ace_push'] * (ace_push + 1)
            details = {k: round(v, 2) for k, v in details.items()}
            outcomes[seat] = dict(details=details, returned=round(sum(details.values()), 2),
                                  **comparison)
        self.settlement = dict(hands=outcomes, mode=self.mode,
                               returned=round(sum(o['returned'] for o in outcomes.values()), 2))
        return self.settlement


def save_pai_gow_history(game):
    """沿用 UTH 的项目日志目录，牌九独立保存牌序、两道和结算记录。"""
    def cards(hand):
        return [dict(suit=c.suit, rank=c.rank) for c in hand]
    folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'A_Logs', 'Json')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, 'Pai_Gow_Poker.json')
    records = []
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as stream:
            records = json.load(stream)
        if not isinstance(records, list):
            raise ValueError('牌九历史记录格式不是列表。')
    records.append(dict(time=time.strftime('%Y-%m-%d %H:%M:%S'),
                        mode=game.mode, cut_position=game.deck.start_pos + 1,
                        full_deck=cards(game.deck.full_deck),
                        dealer=dict(hand=cards(game.dealer_hand), low=cards(game.dealer_low), high=cards(game.dealer_high)),
                        players={s: dict(hand=cards(game.hands[s]), low=cards(game.splits[s]['low']),
                                         high=cards(game.splits[s]['high']), bets=game.bets[s],
                                         result=game.settlement['hands'][s]) for s in game.splits},
                        returned=game.settlement['returned']))
    temporary = path + '.tmp'
    with open(temporary, 'w', encoding='utf-8') as stream:
        json.dump(records, stream, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


class PaiGowPokerGUI(tk.Frame):
    """UTH 界面格式的 Pai Gow Poker：七张升序发牌、提交后牌型排序。"""
    WIDTH, HEIGHT = 1150, 750
    CARD_WIDTH, CARD_HEIGHT = 64, 90
    MODE_TRANSITION_MS = 360
    MODE_FRAME_MS = 16
    DEAL_CARD_MS = 224 / .85
    DEAL_MOVE_MS = (128 / .75) / .85
    BET_CHIP_RADIUS = 16 * 4 / 3
    HOUSE_CHIP_POS = (575, 43)
    DEALER_BG = '#4b1e22'
    DEALER_BOUNDS = (327, 58, 823, 284)
    HAND_TABLE_COLORS = {'neutral': '#1B3D31', 'win': '#D8B46A',
                         'loss': '#D98B82', 'push': '#B8D2DD'}
    HAND_TABLE_BORDERS = {'neutral': '#7B8060', 'win': '#EFCE86',
                          'loss': '#E9ABA2', 'push': '#CFE4EB'}
    ZONE_COLORS = {'Player1': '#2A5541', 'Player2': '#204536'}
    SEAT_NAMES = {'Player1': '玩家1', 'Player2': '玩家2', 'Dealer': '庄家'}

    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = username, float(initial_balance)
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game = PaiGowTableGame()
        self.commission_free = tk.BooleanVar(master=self, value=False)
        self.bets = {s: self.game.empty_bet() for s in self.game.SEATS}
        self.last_bet, self.last_win = None, 0.0
        self._game_instruction_dialog = None
        self.high_bet_mode, self.selected_chip = False, 10.0
        self._jobs = set()
        self._closing = self._credited = self._return_persisted = self._crediting = False
        self._restart_job = self._restart_deadline = None
        self._motion_count = self._chip_serial = 0
        self._mode_transition = None
        self._mode_transition_job = None
        self._mode_progress = float(self.game.mode == 'commission_free')
        self._settlement_started = self._showdown_started = False
        self.visual_chips = {}
        self.last_round_snapshot, self._history_available = None, False
        self._pil_cards, self._flip_photos, self._photos = {}, {}, {}
        self.card_items, self.bet_spots, self.action_buttons = {}, {}, {}
        self.display_orders = {s: list(range(7)) for s in ('Dealer', *self.game.SEATS)}
        self.selected_low_indices = {s: [] for s in self.game.SEATS}
        self._sorted_sides = set()
        self._submitted_sorting = set()
        self._hand_type_cache = {}
        self._table_result_cache = {}
        self.invalid_notices = {s: dict(level=0.0, target=False, job=None, item=None,
            text_item=None, source=None, photo=None) for s in self.game.SEATS}
        self._notice_level = 0.0
        self._notice_target = False
        self._notice_job = self._notice_item = self._notice_source = self._notice_photo = None
        self._dealer_revealed = False
        self._dealer_layout_split = False
        self._load_assets()
        self._create_widgets()
        self._refresh()
        self.bind('<Configure>', self._center_table, add='+')
        self.bind('<Destroy>', self._on_destroy, add='+')

    @property
    def game_in_progress(self):
        return self.game.stage != 'betting' or self._motion_count > 0

    @property
    def betting_enabled(self):
        return self.game.stage == 'betting' and self._motion_count == 0

    def card_size(self, side):
        return self.CARD_WIDTH, self.CARD_HEIGHT

    @staticmethod
    def _card_image_key(card):
        return 'joker' if card.is_joker else (card.suit, card.rank)

    def _load_assets(self):
        # 沿用 UTH 的轮换牌背、透明 PNG 与缺图时的本地绘制回退。
        previous = getattr(self, 'current_poker_folder', None)
        self.current_poker_folder = ('Poker2' if previous == 'Poker1' else 'Poker1') if previous else random.choice(['Poker1', 'Poker2'])
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'A_Tools', 'Card', self.current_poker_folder)
        self.original_images, self._pil_cards, self._photos = {}, {}, {}
        suits = {'♠': 'Spade', '♥': 'Heart', '♦': 'Diamond', '♣': 'Club'}
        try:
            font = ImageFont.truetype('DejaVuSans-Bold.ttf', 23)
        except OSError:
            font = ImageFont.load_default()
        for key in ['back', 'joker'] + [(s, r) for s in SUITS for r in RANKS]:
            filename = ('Background.png' if key == 'back' else 'JOKER-A.png' if key == 'joker'
                        else f'{suits[key[0]]}{key[1]}.png')
            try:
                with Image.open(os.path.join(base, filename)) as source:
                    original = source.convert('RGBA')
            except (OSError, ValueError):
                original = Image.new('RGBA', (80, 112), (0, 0, 0, 0))
                draw = ImageDraw.Draw(original)
                draw.rounded_rectangle((1, 1, 78, 110), radius=6,
                                       fill=DARK_BLUE if key == 'back' else '#fffaf0', outline=GOLD, width=2)
                if key == 'back':
                    for y in range(12, 104, 12):
                        draw.line((10, y, 70, y), fill=GOLD)
                elif key == 'joker':
                    draw.text((7, 12), 'A★', font=font, fill='#7547A8')
                    draw.text((7, 65), 'JOKER', font=ImageFont.load_default(), fill='#7547A8')
                else:
                    suit, rank = key
                    try:
                        draw.text((7, 10), rank + suit, font=font, fill=RED if suit in '♥♦' else BLACK)
                        draw.text((14, 62), suit, font=font, fill=RED if suit in '♥♦' else BLACK)
                    except UnicodeEncodeError:
                        draw.text((7, 10), rank + suits[suit][0], font=font, fill=BLACK)
            self.original_images[key] = original
            self._pil_cards[key] = original
        for side in ('Dealer', *self.game.SEATS):
            self._photos[side] = {key: ImageTk.PhotoImage(im.resize(self.card_size(side), Image.Resampling.LANCZOS), master=self)
                                  for key, im in self._pil_cards.items()}

    def _bets_for_mode(self, bets):
        new = {s: {k: round(float(bets[s].get(k, 0)), 2) for k in BET_NAMES}
               for s in self.game.SEATS}
        if self.game.mode == 'classic':
            for b in new.values():
                b['ace_push'] = 0.0
        return new

    def select_game_mode(self, mode):
        if self._closing or not self.betting_enabled or mode == self.game.mode:
            return
        # 沿用 UTH：接续当前可见画面，快速反向切换也不跳回起点。
        before = self._capture_mode_content()
        start = self._mode_progress
        self.game.set_mode(mode)
        self.commission_free.set(mode == 'commission_free')
        self._cancel_mode_transition_job()
        self._restore_mode_content()
        self._mode_transition = None
        self._apply_bet_layout(self._bets_for_mode(self.bets))
        after = self._capture_mode_content()
        self._mode_transition = dict(
            started=time.monotonic(), start=start,
            target=float(mode == 'commission_free'),
            content=[(old, new) for old, new in zip(before, after) if old != new],
        )
        self._animate_mode_transition()

    def _capture_mode_content(self):
        """只记录模式相关的 Canvas 项目；不截屏、不重建整张牌桌。"""
        c = self.canvas
        items = [(self.mode_description_item, ROOT_BG),
                 (self.rule_notice_item, ROOT_BG), (self.total_item, ROOT_BG)]
        items.extend((item, ROOT_BG) for item in self.rule_value_items)
        for seat in self.game.SEATS:
            spot = self.bet_spots[(seat, 'ace_push')]
            # 标签的背景是下注圆本身，并随模式一起变色。
            items.append((spot['border'], self.ZONE_COLORS[seat]))
            items.append((spot['label'], c.itemcget(spot['border'], 'fill')))
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

    def _paint_mode_transition(self):
        transition = self._mode_transition
        if transition is None:
            return 1.0
        progress = min(1.0, max(0.0, (time.monotonic()-transition['started'])*1000/self.MODE_TRANSITION_MS))
        eased = progress*progress*(3-2*progress)
        self._mode_progress = transition['start'] + (transition['target']-transition['start'])*eased
        self._paint_mode_selector()
        for old, new in transition['content']:
            if old['state'] == new['state'] == 'hidden':
                continue
            changed_text = 'text' in old and old['text'] != new['text']
            options = dict(state='normal')
            if changed_text:
                options['text'] = old['text'] if progress < .5 else new['text']
            for key in new['colors']:
                start = (old['colors'][key] or old['background']) if old['state'] != 'hidden' else old['background']
                target = (new['colors'][key] or new['background']) if new['state'] != 'hidden' else new['background']
                if changed_text:
                    phase = progress*2 if progress < .5 else (progress-.5)*2
                    amount = phase*phase*(3-2*phase)
                    start, target = (start, old['background']) if progress < .5 else (new['background'], target)
                else:
                    amount = eased
                options[key] = self._blend_color(start, target, amount)
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
        # 说明页重建放在转场后，避免阻塞动画帧。
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

    def start_game(self):
        if not self.betting_enabled:
            return
        self._finish_mode_transition()
        before = self.balance
        try:
            charged = self.game.start_round(self.bets, self.balance, self.high_bet_mode)
        except ValueError as exc:
            messagebox.showwarning('无法开始', str(exc), parent=self)
            return
        # 先锁定状态再扣款；账户保存失败时回到下注阶段，避免继续使用未保存余额。
        self.game.stage = 'refunding'
        self.balance = round(self.balance - charged, 2)
        if not self._persist_balance():
            self.balance = before
            self.game.reset_game()
            self._refresh()
            return
        self.bets = {s: dict(b) for s, b in self.game.bets.items()}
        self.last_bet = {s: dict(b) for s, b in self.bets.items()}
        self._credited = self._return_persisted = self._settlement_started = self._showdown_started = False
        self._history_available = self._dealer_revealed = False
        self._dealer_layout_split = False
        self.selected_low_indices = {s: [] for s in self.game.SEATS}
        self.display_orders = {s: list(range(7)) for s in ('Dealer', *self.game.SEATS)}
        self._sorted_sides = set()
        self._submitted_sorting = set()
        self._hand_type_cache.clear()
        self._table_result_cache.clear()
        self._fade_dealer_notice(False)
        for seat in self.game.SEATS:
            self._fade_invalid_notice(seat, False)
        self._cancel_restart_timer()
        self._close_card_sequence()
        self.canvas.delete('cards')
        self.canvas.delete('selection')
        self.card_items.clear()
        self._flip_photos.clear()
        self._load_assets()
        for side, item in self.title_items.items():
            self.canvas.itemconfigure(item, text=self.SEAT_NAMES[side])
        refunds = []
        for seat, refunded in self.game.refunded_bets.items():
            for kind in refunded:
                chip = self.visual_chips.pop((seat, kind, 'stake'), None)
                if chip:
                    refunds.append(dict(amount=chip['amount'], start=chip['xy'],
                                        target=self._rack_position(), duration=440))
        self._refresh()
        self._run_chip_batch(refunds, self._begin_deal)

    def _begin_deal(self):
        self.game.stage = 'dealing'
        self._refresh()
        self._deal_next(self.game.deal_sequence, 0)

    def _reveal_next(self, sequence, offset, complete):
        if offset == len(sequence):
            complete()
            return
        side, index = sequence[offset]
        hand = self.game.dealer_hand if side == 'Dealer' else self.game.hands[side]
        card, item = hand[index], self.card_items[(side, index)]
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
                self.canvas.itemconfigure(item, image=self._photos[side][self._card_image_key(card)])
                self._flip_photos.pop(item, None)
                self._reveal_next(sequence, offset + 1, complete)
        flip()

    def _reveal_initial_cards(self):
        # 经典：玩家先提交；免佣：先公开庄家并按 House Way 拆分。
        sequence = [(s, i) for s in self.game.SEATS if self.game.hands[s] for i in range(7)]
        if self.game.mode == 'commission_free':
            sequence = [('Dealer', i) for i in range(7)] + sequence
        self._reveal_next(sequence, 0, self._after_initial_reveal)

    def _after_initial_reveal(self):
        def ready():
            self.game.stage = 'decision'
            self._refresh()
            self._bind_hand_cards()
        def sort_players():
            self.game.stage = 'sorting'
            self._refresh()
            self._sort_revealed_hands(self.game.SEATS, ready)
        if self.game.mode == 'commission_free':
            self._dealer_revealed = True
            low, high = self.game.split_dealer()
            self._arrange_hand('Dealer', sort_hand_for_display(high) + sorted(low, key=lambda c: c.value, reverse=True), sort_players)
        else:
            sort_players()

    def _sort_revealed_hands(self, sides, complete):
        """Caribbean 的15帧×64ms线性排序；只按2至A、Joker排列。"""
        moving_sides = []
        for side in sides:
            hand = self.game.hands[side]
            if not hand or side in self._sorted_sides:
                continue
            self.display_orders[side] = sorted(range(7), key=lambda i: hand[i].value)
            self._sorted_sides.add(side)
            moving_sides.append(side)
        self._animate_hand_positions(moving_sides, complete, frame_ms=64)

    def _bind_hand_cards(self):
        for (side, index), item in self.card_items.items():
            if side in self.game.SEATS:
                self.canvas.tag_bind(item, '<Button-1>', lambda _e, s=side, i=index: self.toggle_card_selection(s, i))
                self.canvas.tag_bind(item, '<Enter>', lambda _e: self.canvas.configure(cursor='hand2'))
                self.canvas.tag_bind(item, '<Leave>', lambda _e: self.canvas.configure(cursor=''))

    def toggle_card_selection(self, seat, index):
        if self.game.stage != 'decision' or self._motion_count or self.game.decisions[seat] != 'pending':
            return
        selected = self.selected_low_indices[seat]
        if index in selected:
            selected.remove(index)
        elif len(selected) < 2:
            selected.append(index)
        else:
            return
        self.canvas.delete('selection_' + seat)
        self._animate_hand_positions([seat], lambda: self._paint_selection(seat))

    def _paint_selection(self, seat):
        tag = 'selection_' + seat
        self.canvas.delete(tag)
        selected = self.selected_low_indices[seat]
        w, h = self.card_size(seat)
        for index in selected:
            x, y = self.card_position(seat, index)
            outline = self.canvas.create_rectangle(x - 2, y - 2, x + w + 2, y + h + 2,
                outline='#FFE287', width=3, tags=('selection', tag))
            self.canvas.tag_bind(outline, '<Button-1>',
                lambda _e, s=seat, i=index: self.toggle_card_selection(s, i))

    def auto_split(self, seat='Player1'):
        if self.game.stage != 'decision' or self._motion_count or self.game.decisions[seat] != 'pending':
            return
        low, _ = dealer_way_split(self.game.hands[seat])
        self.selected_low_indices[seat] = [self.game.hands[seat].index(c) for c in low]
        self.canvas.delete('selection_' + seat)
        self._animate_hand_positions([seat], lambda: self._paint_selection(seat))

    def submit_split(self, seat='Player1'):
        if self.game.stage != 'decision' or self._motion_count or self.game.decisions[seat] != 'pending':
            return
        try:
            self.game.submit_split(seat, self.selected_low_indices[seat])
        except ValueError as exc:
            messagebox.showwarning('无法提交', str(exc), parent=self)
            return
        self.canvas.delete('selection_' + seat)
        split = self.game.splits[seat]
        self._submitted_sorting.add(seat)
        def sorted_and_ready():
            self._submitted_sorting.discard(seat)
            self._maybe_showdown()
        # 保留七张发牌时的点数升序；仅提交后的五张后道按 Caribbean 牌型展示。
        self._arrange_hand(seat, sorted(split['low'], key=lambda c: c.value, reverse=True)
                           + sort_hand_for_display(split['high']), sorted_and_ready, frame_ms=64)

    def _arrange_hand(self, side, cards, complete=None, animate=True, frame_ms=16):
        hand = self.game.dealer_hand if side == 'Dealer' else self.game.hands[side]
        self.display_orders[side] = [hand.index(c) for c in cards]
        if side == 'Dealer':
            self._dealer_layout_split = True
        if not animate:
            for i in range(7):
                self.canvas.coords(self.card_items[(side, i)], *self.card_position(side, i))
            if complete:
                complete()
            return
        self._animate_hand_positions([side], complete, frame_ms=frame_ms)

    def _animate_hand_positions(self, sides, complete=None, frame_ms=16):
        motions = []
        for side in sides:
            for index in range(7):
                item = self.card_items.get((side, index))
                if item is not None:
                    motions.append((item, tuple(self.canvas.coords(item)), self.card_position(side, index)))
        if not motions:
            if complete:
                complete()
            return
        self._motion_count += 1
        self._refresh()
        def move(frame=0):
            fraction = frame / 15
            for item, (x, y), (tx, ty) in motions:
                self.canvas.coords(item, x + (tx - x) * fraction, y + (ty - y) * fraction)
            if frame < 15:
                self._schedule(frame_ms, move, frame + 1)
            else:
                self._motion_count -= 1
                if complete:
                    complete()
                self._refresh()
        move()

    def _maybe_showdown(self):
        if self.game.stage != 'decision' or self._showdown_started or 'pending' in self.game.decisions.values():
            return
        self._showdown_started = True
        self.game.stage = 'showdown'
        self._refresh()
        def arrange_dealer():
            self._dealer_revealed = True
            low, high = self.game.split_dealer()
            self._arrange_hand('Dealer', sort_hand_for_display(high) + sorted(low, key=lambda c: c.value, reverse=True), self._settle)
        if self._dealer_revealed:
            self._settle()
        else:
            self._reveal_next([('Dealer', i) for i in range(7)], 0, arrange_dealer)

    def _settle(self):
        if self._settlement_started:
            return
        self._settlement_started = True
        result = self.game.settle()
        self.game.stage, self.last_win = 'settling', result['returned']
        transfers = []
        for seat, outcome in result['hands'].items():
            for kind in BET_NAMES:
                transfers.extend(self._outcome_transfers(seat, kind, self.game.bets[seat][kind], outcome['details'][kind]))
        try:
            save_pai_gow_history(self.game)
        except Exception as exc:
            messagebox.showerror('历史记录保存失败', str(exc), parent=self)
        self._refresh()
        self._run_chip_batch(transfers, self._await_next_round)

    def _await_next_round(self):
        if self.game.stage != 'settling':
            return
        self.game.stage = 'await_restart'
        deck = self.game.deck
        self.last_round_snapshot = dict(full_deck=tuple(deck.full_deck), start_pos=deck.start_pos,
                                        images={key: im.copy() for key, im in self.original_images.items()})
        self._history_available = True
        self._cancel_restart_timer()
        self._restart_deadline = time.monotonic() + 30
        self._refresh()
        self._restart_tick()

    def _finish_round(self):
        if self.game.stage != 'sweeping':
            return
        self.game.reset_game()
        self.canvas.delete('selection')
        self._history_available = self._dealer_revealed = False
        self._dealer_layout_split = False
        self.selected_low_indices = {s: [] for s in self.game.SEATS}
        self.display_orders = {s: list(range(7)) for s in ('Dealer', *self.game.SEATS)}
        self._sorted_sides = set()
        self._submitted_sorting = set()
        self._hand_type_cache.clear()
        self._table_result_cache.clear()
        self.bets = {s: self.game.empty_bet() for s in self.game.SEATS}
        for side, item in self.title_items.items():
            self.canvas.itemconfigure(item, text=self.SEAT_NAMES[side], font=('Arial', 16 if side == 'Dealer' else 18, 'bold'))
        self._refresh()

    def reset_game(self, auto_reset=False):
        if self.betting_enabled:
            self.reset_bets()

    def _create_hand_table(self, side, x, y, width=144, row_height=40):
        rows = []
        for row in range(2):
            top = y + row * row_height
            tag = 'hand_table_' + side
            face = self.canvas.create_rectangle(x, top, x+width, top+row_height,
                fill=self.HAND_TABLE_COLORS['neutral'],
                outline=self.HAND_TABLE_BORDERS['neutral'], width=1, tags=tag)
            text = self._text(x+width/2, top+row_height/2, '', 10 if side == 'Dealer' else 11,
                              PANEL_BG, width=width-10, tags=tag)
            rows.append(dict(face=face, text=text))
        self.hand_tables[side] = rows

    def _hand_type_text(self, hand, low=False):
        key = (2 if low else 5, tuple(hand))
        if key not in self._hand_type_cache:
            self._hand_type_cache[key] = ('对子' if _best_two_card_hand(hand)[0] else '高牌') if low else best_hand_with_joker(hand)[0]
        return self._hand_type_cache[key]

    def _table_comparison(self, seat):
        if self.game.settlement is not None:
            return self.game.settlement['hands'].get(seat)
        if (self._dealer_revealed and seat in self.game.splits
                and seat not in self._submitted_sorting):
            if seat not in self._table_result_cache:
                self._table_result_cache[seat] = self.game.compare_split(seat)
            return self._table_result_cache[seat]
        return None

    def _hand_row_result(self, seat, kind):
        outcome = self._table_comparison(seat)
        if outcome is None:
            return 'neutral'
        if not outcome['valid_split']:
            return 'loss'
        if self.game.mode == 'commission_free' and outcome['dealer_ace_high']:
            return 'push'
        result = outcome[kind+'_result']
        if result == 0:
            return 'push'
        return 'win' if result > 0 else 'loss'

    def _paint_hand_table(self, side, descriptions, states):
        for row, description, state in zip(self.hand_tables[side], descriptions, states):
            background = '#391D22' if state == 'neutral' and side == 'Dealer' else self.HAND_TABLE_COLORS[state]
            foreground = PANEL_BG if state == 'neutral' else '#000000'
            self.canvas.itemconfigure(row['face'], fill=background, outline=self.HAND_TABLE_BORDERS[state])
            self.canvas.itemconfigure(row['text'], text=description, fill=foreground)

    def _update_hand_tables(self):
        for seat in self.game.SEATS:
            hand = self.game.hands[seat]
            selected = self.selected_low_indices[seat]
            split = self.game.splits.get(seat)
            if split is not None:
                low, high = split['low'], split['high']
            elif len(selected) == 2 and hand:
                low = [hand[i] for i in selected]
                high = [c for i, c in enumerate(hand) if i not in selected]
            else:
                low, high = [], []
            descriptions = ('前道：'+self._hand_type_text(low, True), '后道：'+self._hand_type_text(high)) if low else ('前道：待分牌', '后道：待分牌')
            self._paint_hand_table(seat, descriptions,
                [self._hand_row_result(seat, kind) for kind in ('low', 'high')])
        if self._dealer_revealed and self.game.dealer_low:
            descriptions = ('后道：'+self._hand_type_text(self.game.dealer_high),
                            '前道：'+self._hand_type_text(self.game.dealer_low, True))
        else:
            descriptions = ('后道：待开牌', '前道：待开牌')
        self._paint_hand_table('Dealer', descriptions, ('neutral', 'neutral'))

    def _refresh_dealer_notice(self):
        visible = (self._dealer_revealed and self.game.mode == 'commission_free'
                   and self.game.stage in ('sorting', 'decision', 'showdown', 'settling', 'await_restart')
                   and self.game.dealer_is_ace_high())
        if visible and self.game.settlement is not None:
            visible = any(o['valid_split'] for o in self.game.settlement['hands'].values())
        self._fade_dealer_notice(visible)

    def _player_notice_position(self, seat):
        left, high_y = self._player_slot_position(seat, 'high', 0)
        right, _ = self._player_slot_position(seat, 'high', 6)
        _, low_y = self._player_slot_position(seat, 'low', 0)
        return (left+right+self.CARD_WIDTH)/2, (low_y+self.CARD_HEIGHT+high_y)/2

    def _refresh_invalid_notices(self):
        active = self.game.stage in ('decision', 'showdown', 'settling', 'await_restart')
        for seat in self.game.SEATS:
            split = self.game.splits.get(seat)
            invalid = active and split is not None and not split['valid']
            self._fade_invalid_notice(seat, invalid)

    def _draw_rule_panel(self):
        c = self.canvas
        c.create_rectangle(827, 75, 1118, 181, fill=ROOT_BG, outline=GOLD, width=2)
        self.rule_value_items = []
        for row, title in enumerate(('主注赔率', '开牌顺序', '特殊规则')):
            y0, y1 = 75 + row * 35, 75 + (row + 1) * 35
            c.create_rectangle(827, y0, 909, y1, outline='#77906B')
            c.create_rectangle(909, y0, 1118, y1, outline='#77906B')
            self._text(868, (y0 + y1) / 2, title, 11, PANEL_BG)
            self.rule_value_items.append(self._text(1014, (y0 + y1) / 2, '', 11, GOLD))

    def _draw_mode_selector(self):
        self._text(975, 208, '游戏模式选择', 14, GOLD)
        self._rounded_rectangle(826, 228, 1126, 274, 12, fill='#102C22', outline='#627652', width=1)
        self.mode_buttons = {}
        self._mode_hover = self._mode_pressed = None
        for index, (mode, name) in enumerate(GAME_MODE_NAMES.items()):
            left, tag = 830 + index * 148, 'mode_option_' + mode
            face = self._rounded_rectangle(left, 232, left + 144, 270, 8, fill='#16372A', outline='', width=1, tags=tag)
            label = self._text(left + 72, 251, name, 12, '#CCD4BF', tags=tag)
            self.mode_buttons[mode] = dict(tag=tag, face=face, text=label, enabled=True)
            for action, event in (('enter', '<Enter>'), ('leave', '<Leave>'), ('press', '<ButtonPress-1>'), ('release', '<ButtonRelease-1>')):
                self.canvas.tag_bind(tag, event, lambda _e, m=mode, a=action: self._mode_pointer(m, a))
        self._mode_slider_x = 830.0
        self._mode_slider = self._rounded_rectangle(830, 232,
            974, 270, 8, fill='#D8B46A', outline='#F0D18D',
            width=1, tags='mode_slider')
        self._mode_slider_shape = tuple(self.canvas.coords(self._mode_slider))
        # 滑块移动时仍以鼠标所在的半区决定点击的模式。
        for action, event in (('enter', '<Enter>'), ('enter', '<Motion>'), ('leave', '<Leave>'),
                              ('press', '<ButtonPress-1>'), ('release', '<ButtonRelease-1>')):
            self.canvas.tag_bind('mode_slider', event,
                lambda e, a=action: self._mode_pointer('classic' if e.x < 978 else 'commission_free', a))
        for button in self.mode_buttons.values():
            self.canvas.tag_raise(button['text'])
        self.mode_description_item = self._text(975, 292, '', 10, '#C7CBB2')

    @staticmethod
    def _blend_color(start, end, fraction):
        a = [int(start[i:i+2], 16) for i in (1, 3, 5)]
        b = [int(end[i:i+2], 16) for i in (1, 3, 5)]
        return '#'+''.join(f'{round(x+(y-x)*fraction):02x}' for x, y in zip(a, b))

    def _paint_mode_selector(self):
        enabled = not self._closing and self.betting_enabled
        if not enabled:
            self._mode_hover = self._mode_pressed = None
        for index, (mode, button) in enumerate(self.mode_buttons.items()):
            fill = '#16372A'
            if enabled and self._mode_hover == mode:
                fill = '#2E513C'
            if enabled and self._mode_pressed == mode:
                fill = '#234431'
            weight = 1-abs(self._mode_progress-index)
            foreground = self._blend_color('#CCD4BF' if enabled else '#8B9C8E', TITLE_FG, weight)
            button['enabled'] = enabled
            self.canvas.itemconfigure(button['face'], fill=fill, outline='')
            self.canvas.itemconfigure(button['text'], fill=foreground)
        # 从固定轮廓定位，反复切换不会累积 Canvas.move 的位置误差。
        self._mode_slider_x = 830+148*self._mode_progress
        offset = self._mode_slider_x-830
        self.canvas.coords(self._mode_slider, *(
            value+offset if index % 2 == 0 else value
            for index, value in enumerate(self._mode_slider_shape)))
        fill = '#BD9A58' if enabled and self._mode_pressed == self.game.mode else '#E2C37D' if enabled and self._mode_hover == self.game.mode else '#D8B46A'
        self.canvas.itemconfigure(self._mode_slider, fill=fill)

    def _refresh_mode_selector(self):
        if self._mode_transition is None:
            self._mode_progress = float(self.game.mode == 'commission_free')
        self._paint_mode_selector()
        if self._mode_transition is not None:
            return
        free = self.game.mode == 'commission_free'
        values = ('1:1', '庄家先分牌，再由玩家提交', '庄家A高，底注平局') if free else ('0.95:1', '玩家先提交，再由庄家分牌', '同道同点，庄家获胜')
        for item, value in zip(self.rule_value_items, values):
            self.canvas.itemconfigure(item, text=value)
        self.canvas.itemconfigure(self.mode_description_item, text='庄家先开牌 · A高平手开放' if free else '玩家先分牌 · 获胜利润收5%佣金')
        self.canvas.itemconfigure(self.rule_notice_item, text='庄家A高，底注平局' if free else '后道必须强于前道')

    def _draw_wild_spot(self, seat, kind, cx, cy, label, radius):
        tag = 'spot_' + seat + '_' + kind
        border = self.canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                    fill=self.ZONE_COLORS[seat], outline=PANEL_BG, width=2, tags=tag)
        self._register_spot(seat, kind, cx, cy, border, label)
        self.canvas.itemconfigure(self.bet_spots[(seat, kind)]['label'], font=('Arial', 14 if kind == 'ante' else 11, 'bold'))

    def _create_widgets(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT, bg=ROOT_BG, highlightthickness=0)
        self.canvas.place(x=0, y=0, width=self.WIDTH, height=self.HEIGHT)
        self.control_buttons = {}
        c = self.canvas
        self._text(176, 44, '牌九扑克', 16, GOLD)
        self._draw_limit_table()
        self._text(975, 44, 'Pai Gow Poker', 14, GOLD)
        self._draw_rule_panel()
        c.create_rectangle(22, 191, 1128, 309, fill=ROOT_BG, outline='#65784B')
        c.create_line(25, 192, 1125, 192, fill='#E0C879', width=2)
        c.create_line(25, 308, 1125, 308, fill='#0C241B', width=2)
        self.rule_notice_item = self._text(176, 229, '', 16, GOLD)
        self._text(176, 252, '前道2张 · 后道5张', 12, PANEL_BG)
        self.street_item = self._text(176, 280, '下注阶段', 14, PANEL_BG, width=289)
        self._draw_mode_selector()
        self.dealer_zone_item = self._rounded_rectangle(*self.DEALER_BOUNDS, 12, fill=self.DEALER_BG,
                                outline='#AB716C', width=1, tags='dealer_zone')
        self.title_items = {'Dealer': self._text(575, 72, '庄家', 16, PANEL_BG)}
        self.hand_tables = {}
        self._create_hand_table('Dealer', 353, 186, width=124)
        for seat, x0, x1 in (('Player1', 22, 566), ('Player2', 582, 1128)):
            c.create_rectangle(x0, 316, x1, 617, fill=self.ZONE_COLORS[seat], outline='')
            self.title_items[seat] = self._text((x0+x1)/2, 330, self.SEAT_NAMES[seat], 18, PANEL_BG)
            self._create_hand_table(seat, x0+26, 365)
            for kind, x in (('ante', 54), ('emperor', 162), ('insurance', 270), ('johor', 378), ('ace_push', 486)):
                self._draw_wild_spot(seat, kind, x0+x+15, 584, BET_NAMES[kind], 31)
            for action, top, caption, color in (('auto', 365, '自动分牌', '#397A48'), ('submit', 410, '提交分牌', DARK_BLUE)):
                self.action_buttons[(seat, action)] = self.create_control_button(
                    x0+374, top, x0+518, top+38, caption,
                    lambda s=seat, a=action: self.auto_split(s) if a == 'auto' else self.submit_split(s),
                    color, font_size=13, draw_shadow=False)
        self._draw_bottom_controls()
        self.dealer_slots = {'high': [], 'low': []}
        for row, count in (('high', 7), ('low', 2)):
            for slot in range(count):
                x, y = self._dealer_slot_position(row, slot)
                w, h = self.card_size('Dealer')
                item = c.create_rectangle(x, y, x+w, y+h, outline='#AB716C', dash=(3, 3),
                    tags=('card_slots', 'slots_Dealer_'+row), state='normal')
                self.dealer_slots[row].append(item)
        for seat in self.game.SEATS:
            for row, count in (('low', 2), ('high', 7)):
                for slot in range(count):
                    x, y = self._player_slot_position(seat, row, slot)
                    w, h = self.card_size(seat)
                    c.create_rectangle(x, y, x+w, y+h, outline='#7B9374', dash=(3, 3),
                                       tags=('card_slots', 'slots_'+seat+'_'+row))

    @staticmethod
    def _player_slot_position(seat, row, slot):
        x0 = 22 if seat == 'Player1' else 582
        return (x0+201+slot*78, 356) if row == 'low' else (x0+36+slot*68, 460)

    def _dealer_slot_position(self, row, slot):
        if row == 'low':
            return 504+slot*78, 184
        # 与玩家七张牌位一样，每张64px宽，牌间空隙4px。
        return 339+slot*68, 86

    def card_position(self, side, index):
        order = self.display_orders.get(side, list(range(7)))
        if side == 'Dealer':
            slot = order.index(index)
            if not self._dealer_layout_split:
                return self._dealer_slot_position('high', slot)
            # 五张后道只占首行中间五格，七张牌位及牌区宽度保持固定。
            return self._dealer_slot_position('high', slot+1) if slot < 5 else self._dealer_slot_position('low', slot-5)
        selected = self.selected_low_indices[side]
        if index in selected:
            hand = self.game.hands[side]
            low_order = sorted(selected, key=lambda i: hand[i].value, reverse=True)
            return self._player_slot_position(side, 'low', low_order.index(index))
        if len(selected) == 2:
            high_order = [i for i in order if i not in selected]
            # 五张后道占用七张发牌位的中间五个，左右两端不放牌。
            return self._player_slot_position(side, 'high', high_order.index(index)+1)
        return self._player_slot_position(side, 'high', order.index(index))

    def _refresh(self):
        c = self.canvas
        c.itemconfigure(self.balance_item, text=f'余额: ${self.balance:,.2f}')
        total = round(sum(sum(b.values()) for b in self.bets.values()), 2)
        c.itemconfigure(self.total_item, text=f'本局下注: ${total:,.2f}' if total else f'上局返还: ${self.last_win:,.2f}')
        for item, value in zip(self.limit_value_items, self.game.limits(self.high_bet_mode)):
            c.itemconfigure(item, text=f'${value:,}')
        self._render_chips()
        betting = self.betting_enabled
        self._refresh_mode_selector()
        self.set_control_button_state(self.clear_button, betting)
        self.set_control_button_state(self.repeat_button, betting and bool(self.last_bet))
        self.set_control_button_state(self.start_button, betting)
        restarting = self.game.stage in ('await_restart', 'returning', 'credit_pending', 'sweeping')
        c.itemconfigure(self.repeat_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button, state='normal' if restarting else 'hidden')
        self.set_control_button_state(self.restart_button, self.game.stage in ('await_restart', 'credit_pending'))
        for seat in self.game.SEATS:
            ready = self.game.stage == 'decision' and not self._motion_count and self.game.decisions[seat] == 'pending'
            self.set_control_button_state(self.action_buttons[(seat, 'auto')], ready)
            self.set_control_button_state(self.action_buttons[(seat, 'submit')], ready and len(self.selected_low_indices[seat]) == 2)
            unavailable = self.game.mode == 'classic'
            spot = self.bet_spots[(seat, 'ace_push')]
            c.itemconfigure(spot['border'], outline='#738379' if unavailable else PANEL_BG,
                            fill='#30483B' if unavailable else self.ZONE_COLORS[seat])
            c.itemconfigure(spot['label'], fill='#85998B' if unavailable else PANEL_BG)
        caption = {'betting': '下注阶段', 'refunding': '筹码准备中', 'dealing': '发牌 / 开牌中', 'sorting': '手牌升序排列中',
                   'decision': '请选择两张前道', 'showdown': '庄家分牌中', 'settling': '派彩中',
                   'await_restart': '已结算', 'returning': '返还筹码中', 'credit_pending': '余额保存待重试',
                   'sweeping': '收牌中'}[self.game.stage]
        if self._submitted_sorting:
            caption = '后道按牌型排列中'
        c.itemconfigure(self.street_item, text=caption)
        self._status(caption)
        self._update_hand_tables()
        self._refresh_dealer_notice()
        self._refresh_invalid_notices()
        if self._mode_transition is not None:
            self._paint_mode_transition()

    def add_chip_to_bet(self, seat, kind):
        if not self.betting_enabled or kind not in BET_NAMES:
            return
        if kind == 'ace_push' and self.game.mode == 'classic':
            return
        _, maximum, side_max = self.game.limits(self.high_bet_mode)
        new = {s: dict(b) for s, b in self.bets.items()}
        limit = maximum if kind == 'ante' else side_max
        amount = round(new[seat][kind] + self.selected_chip, 2)
        if amount > limit:
            messagebox.showwarning('下注限制', f'{BET_NAMES[kind]}最高 ${limit:,}。', parent=self)
            return
        new[seat][kind] = amount
        if sum(sum(b.values()) for b in new.values()) > self.balance:
            messagebox.showwarning('余额不足', '余额不足以支付这些下注。', parent=self)
            return
        self._apply_bet_layout(new)

    def reset_single_bet(self, seat, kind):
        if not self.betting_enabled:
            return
        if kind == 'ace_push' and self.game.mode == 'classic':
            return
        new = {s: dict(b) for s, b in self.bets.items()}
        new[seat][kind] = 0.0
        self._apply_bet_layout(new)

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
        self._mode_transition_job = None
        self._mode_transition = None

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

    def _deal_next(self, sequence, offset):
        if offset==len(sequence):
            self._reveal_initial_cards()
            return
        side,index = sequence[offset]
        x,y = self.card_position(side,index)
        photo = self._photos[side]['back']
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
        # 沿用 UTH 的标题和三列限红表。
        c = self.canvas
        x0,x1,y0 = 30,323,75
        c.create_rectangle(x0,y0,x1,181,fill=ROOT_BG,outline=GOLD,width=2,tags='limits')
        c.create_rectangle(x0,y0,x1,y0+29,fill=ROOT_BG,outline=GOLD,tags='limits')
        self._text((x0+x1)/2,y0+14,'下注上限',13,PANEL_BG,tags='limits')
        titles = ('底注最低','底注最高','边注最高')
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

    def _chip_color(self, amount):
        return next((col for value,col in reversed(self.chip_specs) if amount>=value),HEADER_BG)

    @staticmethod
    def _amount_label(amount):
        value=round(float(amount),2)
        if abs(value)>=1000:return PaiGowPokerGUI._compact(value)
        return f'{value:.0f}' if value.is_integer() else f'{value:.2f}'

    def _draw_chip(self, tag, amount, x, y, rectangular=False, extra_tags=(), show_amount=True):
        c=self.canvas;tags=(tag,*extra_tags)
        if rectangular:
            # 大奖筹码只显示中奖数字，不带货币符号；整数省略 .00。
            label=self._amount_label(amount);width=max(96,10*len(label)+16)
            c.create_rectangle(x-width/2,y-18,x+width/2,y+18,fill='#731D2A',outline='#000000',width=1,tags=tags)
            if show_amount:self._text(x,y,label,11,'#FFF0C3',tags=tags)
        else:
            radius=self.BET_CHIP_RADIUS;color=self._chip_color(amount)
            c.create_oval(x-radius,y-radius,x+radius,y+radius,fill=color,outline='#000000',width=1,tags=tags)
            label=self._compact(amount)
            self._text(x,y,label,10 if len(label)>=5 else 12,TEXT if color in (BLACK,RED) else BLACK,tags=tags)

    def _render_chips(self):
        self.canvas.delete('bet_chips')
        # 本金先画、盈利后画；盈利位于原筹码水平左侧，边缘相隔4px。
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
        self._run_chip_batch(transfers,self._refresh)
        self._refresh()

    def _outcome_transfers(self, seat, kind, stake, returned):
        """本金留位，盈利派至水平左侧，并与本金筹码相隔4px；输注立即飞向统一庄家收筹码点，平局不动。"""
        if not stake:return []
        key=(seat,kind,'stake');center=self.bet_spots[(seat,kind)]['center']
        if returned<=0:
            chip=self.visual_chips.pop(key,None)
            return [dict(amount=chip['amount'],start=chip['xy'],target=self.HOUSE_CHIP_POS,duration=280)] if chip else []
        profit=round(returned-stake,2)
        if profit<=0:return []
        target=(center[0]-(2*self.BET_CHIP_RADIUS+4),center[1])
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
        for seat in self.game.SEATS:
            self._fade_invalid_notice(seat, False)
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
        # 沿用 UTH 的牌序窗口：730×750，九张一排，切牌位置高亮，滚动显示含 Joker 的53张原始牌序。
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

    def _center_table(self, event=None):
        # Keep the original 1150×750 composition centered when embedded.
        self.canvas.place(x=max(0, (self.winfo_width()-self.WIDTH)//2),
                          y=max(0, (self.winfo_height()-self.HEIGHT)//2),
                          width=self.WIDTH, height=self.HEIGHT)

    def _make_dealer_notice(self):
        """使用透明 RGBA 浮层，在牌桌内淡入，透明部分保留原始牌面。"""
        scale=3;width,height=210,32
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
            try:font=ImageFont.truetype(path,22*scale);break
            except OSError:continue
        self._notice_text_item=None
        if font is not None:
            text='庄家A高平局';box=draw.textbbox((0,0),text,font=font)
            draw.text(((width*scale-(box[2]-box[0]))/2-box[0],
                       (height*scale-(box[3]-box[1]))/2-box[1]),text,font=font,fill='#FFF1D1')
        else:
            # 极少数无可供 Pillow 使用的中文字体的系统，交由 Tk 原生字体回退。
            self._notice_text_item=self._text(575,180,'庄家A高平局',16,'#FFF1D1',state='hidden',tags='dealer_notice')
        self._notice_source=layer.resize((width,height),Image.Resampling.LANCZOS)
        self._notice_item=self.canvas.create_image(575,180,state='hidden',tags='dealer_notice')

    def _make_invalid_notice(self, seat):
        """使用透明 RGBA 浮层，在牌桌内淡入，透明部分保留原始牌面。"""
        notice = self.invalid_notices[seat]
        tag = 'invalid_notice_'+seat
        cx,cy = self._player_notice_position(seat)
        scale=3;width,height=300,32
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
            try:font=ImageFont.truetype(path,22*scale);break
            except OSError:continue
        notice['text_item']=None
        if font is not None:
            text='错误布道，主注自动输';box=draw.textbbox((0,0),text,font=font)
            draw.text(((width*scale-(box[2]-box[0]))/2-box[0],
                       (height*scale-(box[3]-box[1]))/2-box[1]),text,font=font,fill='#FFF1D1')
        else:
            # 极少数无可供 Pillow 使用的中文字体的系统，交由 Tk 原生字体回退。
            notice['text_item']=self._text(cx,cy,'错误布道，主注自动输',16,'#FFF1D1',state='hidden',tags=tag)
        notice['source']=layer.resize((width,height),Image.Resampling.LANCZOS)
        notice['item']=self.canvas.create_image(cx,cy,state='hidden',tags=tag)

    def _draw_dealer_notice(self):
        alpha=self._notice_level
        if self._notice_item is None:return
        if alpha<=0:
            self.canvas.itemconfigure('dealer_notice',state='hidden');return
        layer=self._notice_source.copy()
        layer.putalpha(self._notice_source.getchannel('A').point(lambda value:round(value*alpha)))
        self._notice_photo=ImageTk.PhotoImage(layer,master=self)
        self.canvas.itemconfigure(self._notice_item,image=self._notice_photo,state='normal')
        self.canvas.tag_raise('dealer_notice')
        if self._notice_text_item is not None:
            background=(75,30,34);foreground=(255,241,209)
            color='#'+''.join(f'{round(a+(b-a)*alpha):02x}' for a,b in zip(background,foreground))
            self.canvas.itemconfigure(self._notice_text_item,state='normal',fill=color)
            self.canvas.tag_raise(self._notice_text_item)

    def _draw_invalid_notice(self, seat):
        notice = self.invalid_notices[seat]
        tag = 'invalid_notice_'+seat
        alpha=notice['level']
        if notice['item'] is None:return
        if alpha<=0:
            self.canvas.itemconfigure(tag,state='hidden');return
        layer=notice['source'].copy()
        layer.putalpha(notice['source'].getchannel('A').point(lambda value:round(value*alpha)))
        notice['photo']=ImageTk.PhotoImage(layer,master=self)
        self.canvas.itemconfigure(notice['item'],image=notice['photo'],state='normal')
        self.canvas.tag_raise(tag)
        if notice['text_item'] is not None:
            background=tuple(int(self.ZONE_COLORS[seat][i:i+2],16) for i in (1,3,5));foreground=(255,241,209)
            color='#'+''.join(f'{round(a+(b-a)*alpha):02x}' for a,b in zip(background,foreground))
            self.canvas.itemconfigure(notice['text_item'],state='normal',fill=color)
            self.canvas.tag_raise(notice['text_item'])

    def _fade_dealer_notice(self, visible):
        target=1.0 if visible else 0.0
        if self._notice_target==visible and (self._notice_job is not None or self._notice_level==target):return
        if self._notice_job is not None:
            try:self.after_cancel(self._notice_job)
            except tk.TclError:pass
            self._jobs.discard(self._notice_job);self._notice_job=None
        self._notice_target=visible
        if self._notice_source is None:
            if not visible:return
            self._make_dealer_notice()
        start=self._notice_level
        def step(frame):
            self._notice_job=None
            self._notice_level=start+(target-start)*frame/12
            self._draw_dealer_notice()
            if frame<12:self._notice_job=self._schedule(25,step,frame+1)
        step(0)

    def _fade_invalid_notice(self, seat, visible):
        notice = self.invalid_notices[seat]
        tag = 'invalid_notice_'+seat
        target=1.0 if visible else 0.0
        if notice['target']==visible and (notice['job'] is not None or notice['level']==target):return
        if notice['job'] is not None:
            try:self.after_cancel(notice['job'])
            except tk.TclError:pass
            self._jobs.discard(notice['job']);notice['job']=None
        notice['target']=visible
        if notice['source'] is None:
            if not visible:return
            self._make_invalid_notice(seat)
        start=notice['level']
        def step(frame):
            notice['job']=None
            notice['level']=start+(target-start)*frame/12
            self._draw_invalid_notice(seat)
            if frame<12:notice['job']=self._schedule(25,step,frame+1)
        step(0)

    def _instruction_pages(self):
        def cards(*items):
            return ('__CARD_IMAGES__', items)
        manual_pages = [
            (
                '玩法',
                '将七张牌分成两张前道与五张后道。\n'
                '分别与庄家的前道及后道比较。',
                [
                    (
                        '游戏目标',
                        '',
                        [
                            (
                                '与庄家比较两道',
                                '玩家和庄家各获七张牌。\n'
                                '前道：两张牌，只比较对子或高牌。\n'
                                '后道：五张牌，按五张扑克牌型比较。\n'
                                '\n'
                                '玩家的后道必须强于前道。\n'
                                '分牌有效后，再分别与庄家的两道比较。'
                            ),
                            (
                                '胜、负与平局',
                                '两道都赢：底注获胜。\n'
                                '一赢一输：底注平局，退还本金。\n'
                                '两道都输：失去底注。\n'
                                '\n'
                                '任何一道完全同点，均算庄家赢该道。\n'
                                '免佣模式另有庄家A高牌平局规则。'
                            ),
                        ],
                        [],
                    ),
                    (
                        '一局如何进行',
                        '',
                        [
                            (
                                '① 选择模式并下注',
                                '选择经典模式或免佣模式。\n'
                                '设置底注，并按需购买边注。\n'
                                '\n'
                                '两种模式均可购买：\n'
                                '• 牌九保险\n'
                                '• 皇帝之财\n'
                                '• 柔佛州\n'
                                '\n'
                                'A高平手边注只在免佣模式开放。'
                            ),
                            (
                                '② 开始发牌',
                                '点击“开牌”。\n'
                                '系统扣除本局全部下注，并开始发牌。\n'
                                '\n'
                                '经典模式：\n'
                                '玩家先分牌，提交后庄家开牌分牌。\n'
                                '\n'
                                '免佣模式：\n'
                                '庄家先亮牌并自动分牌，再由玩家分牌。'
                            ),
                            (
                                '③ 选择两张前道',
                                '点击手牌，选择两张作为前道。\n'
                                '其余五张自动作为后道。\n'
                                '选中的牌会向上移动。\n'
                                '提交前可以重新选择。\n'
                                '\n'
                                '也可点击“自动分牌”，\n'
                                '使用程序的庄家分牌策略。'
                            ),
                            (
                                '④ 提交并结算',
                                '确认前道两张、后道五张。\n'
                                '检查后道是否强于前道。\n'
                                '点击“提交分牌”后进行比牌及结算。\n'
                                '\n'
                                '分牌无效时：\n'
                                '底注直接判负。\n'
                                '已购买的边注仍正常结算。'
                            ),
                        ],
                        [],
                    ),
                ],
            ),
            (
                '下注 & 限红',
                '两种模式使用相同限额。\n'
                '底注必须下注，边注可选。',
                [
                    (
                        '下注项目',
                        '',
                        [],
                        [
                            (
                                '用途与限额',
                                ['项目', '金额限制', '判奖依据'],
                                [
                                    [
                                        '底注',
                                        '$10～$25,000',
                                        '前道与后道的\n比牌结果',
                                    ],
                                    [
                                        '牌九保险',
                                        '可选\n最高$2,500',
                                        '玩家七张牌中的\n最佳五张是否为高牌',
                                    ],
                                    [
                                        '皇帝之财',
                                        '可选\n最高$2,500',
                                        '玩家原始七张牌的\n特殊组合或最佳五张',
                                    ],
                                    [
                                        '柔佛州',
                                        '可选\n最高$2,500',
                                        '玩家七张牌的\n红黑颜色及Joker',
                                    ],
                                    [
                                        'A高平手',
                                        '可选\n最高$2,500',
                                        '仅免佣模式\n'
                                        '双方七张牌的A高牌情况',
                                    ],
                                ],
                            ),
                        ],
                    ),
                    (
                        '经典模式与免佣模式',
                        '',
                        [],
                        [
                            (
                                '模式对照',
                                ['项目', '经典模式', '免佣模式'],
                                [
                                    ['底注获胜\n净赔率', '0.95:1', '1:1'],
                                    ['佣金', '获胜利润的5%', '不收佣金'],
                                    [
                                        '分牌顺序',
                                        '玩家先提交\n庄家后分牌',
                                        '庄家先亮牌分牌\n玩家后分牌',
                                    ],
                                    [
                                        '庄家七张牌的\n最佳五张为A高牌',
                                        '正常比较两道',
                                        '玩家分牌有效时\n底注直接平局',
                                    ],
                                    [
                                        'A高平手边注',
                                        '不可购买',
                                        '可以购买',
                                    ],
                                ],
                            ),
                        ],
                    ),
                    (
                        '下注操作',
                        '',
                        [
                            (
                                '添加与清除筹码',
                                '先选择筹码。\n'
                                '左键点击对应下注区域，增加金额。\n'
                                '下注阶段右键点击对应区域，清除该项金额。\n'
                                '“清除”会清除所有下注金额。'
                            ),
                            (
                                '开局要求',
                                '底注至少$10。\n'
                                '不能只购买边注开局。\n'
                                '边注金额不能为负数，0表示不购买。\n'
                                '\n'
                                '开牌时，一次扣除全部下注。\n'
                                '余额必须足够支付本局全部下注。\n'
                                '本游戏没有看牌后追加的加注项目。'
                            ),
                            (
                                '重复上局下注',
                                '恢复上次开局时的下注金额。\n'
                                '确认金额后，再点击“开牌”。\n'
                                '\n'
                                '经典模式下，A高平手金额保持为0。\n'
                                '模式只能在允许下注时切换。'
                            ),
                        ],
                        [],
                    ),
                ],
            ),
            (
                '获胜条件 & 赔率',
                '赔率表示净赢倍数。\n'
                '中奖时，另外退还该项下注本金。',
                [
                    (
                        '底注结算',
                        '本游戏没有庄家资格门槛。\n'
                        '同道牌力完全相同，算庄家赢该道。',
                        [],
                        [
                            (
                                '有效分牌时的常规结果',
                                ['结果', '经典模式返还', '免佣模式返还'],
                                [
                                    ['两道都赢', '底注×1.95', '底注×2'],
                                    ['一赢一输', '底注×1', '底注×1'],
                                    ['两道都输', '0', '0'],
                                ],
                            ),
                        ],
                    ),
                    (
                        '免佣模式的特殊平局',
                        '',
                        [
                            (
                                '庄家A高牌',
                                '检查庄家完整七张牌中的最佳五张。\n'
                                '必须同时满足：\n'
                                '• 最佳牌型为高牌。\n'
                                '• 最大点数为A。\n'
                                '\n'
                                '玩家分牌有效时，无论两道比牌结果如何，\n'
                                '底注均按平局处理，退还本金。\n'
                                '\n'
                                '仅看庄家分牌后的后道为A高牌，\n'
                                '不足以判断是否触发此规则。\n'
                                '\n'
                                '玩家分牌无效时，底注仍直接判负。'
                            ),
                        ],
                        [],
                    ),
                    (
                        '牌九保险',
                        '按玩家原始七张牌的最佳五张判定。\n'
                        '与底注胜负无关。',
                        [
                            (
                                '中奖条件',
                                '最佳五张必须为高牌。\n'
                                '再按最高点数查表赔付。\n'
                                '\n'
                                '即使七张牌没有对子，\n'
                                '只要能组成顺子或同花，也不符合条件。'
                            ),
                        ],
                        [
                            (
                                '牌九保险赔率',
                                ['最佳五张的最高点数', '净赔率'],
                                [
                                    ['9高牌', '100:1'],
                                    ['10高牌', '40:1'],
                                    ['J高牌', '10:1'],
                                    ['Q高牌', '7:1'],
                                    ['K高牌', '6:1'],
                                    ['A高牌', '3:1'],
                                ],
                            ),
                        ],
                    ),
                    (
                        '皇帝之财',
                        '使用玩家原始七张牌判奖。\n'
                        '不受最终分牌影响。',
                        [
                            (
                                '判奖顺序',
                                '先检查七张同花顺。\n'
                                '再检查五条A。\n'
                                '之后评估最佳五张牌型。\n'
                                '\n'
                                '同一项边注只领取对应的一档赔付。\n'
                                '不同档位的奖金不叠加。\n'
                                '\n'
                                '两对、对子，以及Q／K／A高牌不中奖。'
                            ),
                        ],
                        [
                            (
                                '皇帝之财赔率',
                                ['中奖组合', '净赔率'],
                                [
                                    ['天然七张同花顺\n无Joker', '5000:1'],
                                    ['七张同花顺\n含Joker', '1000:1'],
                                    ['五条A', '500:1'],
                                    ['皇家同花顺', '150:1'],
                                    ['同花顺', '50:1'],
                                    ['四条', '25:1'],
                                    ['葫芦', '5:1'],
                                    ['同花', '4:1'],
                                    ['顺子', '2:1'],
                                    ['三条', '3:1'],
                                    ['9高牌', '40:1'],
                                    ['10高牌', '5:1'],
                                    ['J高牌', '2:1'],
                                ],
                            ),
                        ],
                    ),
                    (
                        '柔佛州',
                        '“同色”表示同为红色或黑色。\n'
                        '不要求同一花色。',
                        [
                            (
                                '颜色与赔付',
                                '黑色：♠、♣。\n'
                                '红色：♥、♦。\n'
                                '\n'
                                '按下表由上至下，取第一个符合的条件。\n'
                                '不同档位不叠加赔付。'
                            ),
                        ],
                        [
                            (
                                '柔佛州赔率',
                                ['玩家七张牌', '净赔率'],
                                [
                                    ['六张同色＋一张Joker', '30:1'],
                                    ['七张同色\n且没有Joker', '10:1'],
                                    ['含Joker\n但未满足上方更高条件', '5:1'],
                                    ['其他情况', '不中奖'],
                                ],
                            ),
                        ],
                    ),
                    (
                        'A高平手',
                        '仅免佣模式可购买。\n'
                        '双方均使用七张牌中的最佳五张判定。',
                        [
                            (
                                'A高牌的含义',
                                '最佳五张为高牌，且最大点数为A。\n'
                                '有对子或更高牌型，就不属于A高牌。\n'
                                '\n'
                                '下表按顺序判奖。\n'
                                '符合多项时不叠加。'
                            ),
                        ],
                        [
                            (
                                'A高平手赔率',
                                ['条件', '净赔率'],
                                [
                                    ['玩家与庄家\n均为A高牌', '40:1'],
                                    [
                                        '仅庄家为A高牌\n庄家七张含Joker',
                                        '15:1',
                                    ],
                                    [
                                        '仅庄家为A高牌\n庄家七张不含Joker',
                                        '5:1',
                                    ],
                                    ['庄家不是A高牌', '不中奖'],
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            (
                '牌型等级表',
                '后道牌型由强到弱排列。\n'
                '牌型相同，再比较相关点数。',
                [
                    (
                        '后道的十一种牌型',
                        '图片为牌型示例。\n'
                        '不表示自动分牌一定会保留该组合。',
                        [],
                        [
                            (
                                '五张牌型：由强到弱',
                                ['等级', '牌型', '牌例'],
                                [
                                    [
                                        '1', '五条A',
                                        cards(
                                            ('♠', 'A'), ('♥', 'A'),
                                            ('♦', 'A'), ('♣', 'A'),
                                            ('JOKER', 'A'),
                                        ),
                                    ],
                                    [
                                        '2', '皇家同花顺',
                                        cards(
                                            ('♠', 'A'), ('♠', 'K'),
                                            ('♠', 'Q'), ('♠', 'J'),
                                            ('♠', '10'),
                                        ),
                                    ],
                                    [
                                        '3', '同花顺',
                                        cards(
                                            ('♥', '9'), ('♥', '8'),
                                            ('♥', '7'), ('♥', '6'),
                                            ('♥', '5'),
                                        ),
                                    ],
                                    [
                                        '4', '四条',
                                        cards(
                                            ('♠', '9'), ('♥', '9'),
                                            ('♦', '9'), ('♣', '9'),
                                            ('♠', '2'),
                                        ),
                                    ],
                                    [
                                        '5', '葫芦',
                                        cards(
                                            ('♠', 'K'), ('♥', 'K'),
                                            ('♦', 'K'), ('♣', '5'),
                                            ('♦', '5'),
                                        ),
                                    ],
                                    [
                                        '6', '同花',
                                        cards(
                                            ('♥', 'A'), ('♥', '10'),
                                            ('♥', '8'), ('♥', '5'),
                                            ('♥', '2'),
                                        ),
                                    ],
                                    [
                                        '7', '顺子',
                                        cards(
                                            ('♠', '9'), ('♥', '8'),
                                            ('♦', '7'), ('♣', '6'),
                                            ('♠', '5'),
                                        ),
                                    ],
                                    [
                                        '8', '三条',
                                        cards(
                                            ('♠', 'Q'), ('♥', 'Q'),
                                            ('♦', 'Q'), ('♣', '8'),
                                            ('♦', '2'),
                                        ),
                                    ],
                                    [
                                        '9', '两对',
                                        cards(
                                            ('♠', 'J'), ('♥', 'J'),
                                            ('♦', '4'), ('♣', '4'),
                                            ('♠', 'A'),
                                        ),
                                    ],
                                    [
                                        '10', '对子',
                                        cards(
                                            ('♠', 'A'), ('♥', 'A'),
                                            ('♦', '10'), ('♣', '7'),
                                            ('♠', '2'),
                                        ),
                                    ],
                                    [
                                        '11', '高牌',
                                        cards(
                                            ('♠', 'A'), ('♥', 'K'),
                                            ('♦', '9'), ('♣', '6'),
                                            ('♠', '3'),
                                        ),
                                    ],
                                ],
                            ),
                        ],
                    ),
                    (
                        '同牌型如何比较',
                        '',
                        [
                            (
                                '前道：对子或高牌',
                                '对子大于任何高牌。\n'
                                '对子之间比较对子的点数。\n'
                                '高牌先比最大一张，再比另一张。\n'
                                '\n'
                                '两张同花不构成同花牌型。\n'
                                '两张点数相连不构成顺子。'
                            ),
                            (
                                '后道：按牌型及相关点数',
                                '四条：先比四条点数，再比单张。\n'
                                '葫芦：先比三条，再比对子。\n'
                                '三条：先比三条，再依次比其余单张。\n'
                                '两对：先比大对，再比小对，最后比单张。\n'
                                '对子：先比对子，再依次比其余单张。\n'
                                '同花、高牌：按点数从大到小逐张比较。\n'
                                '\n'
                                '花色不分大小。\n'
                                '与庄家完全相同，算玩家输该道。'
                            ),
                            (
                                '顺子中的A',
                                'A-K-Q-J-10是最大的五张顺子。\n'
                                '本程序将A-2-3-4-5视为5高顺子。\n'
                                '5高顺子是最小顺子。\n'
                                '\n'
                                'A不能连接K与2形成跨越式顺子。'
                            ),
                        ],
                        [],
                    ),
                    (
                        'Joker的使用范围',
                        '',
                        [
                            (
                                '后道：半万能牌',
                                'Joker可补成以下牌型：\n'
                                '• 皇家同花顺\n'
                                '• 同花顺\n'
                                '• 同花\n'
                                '• 顺子\n'
                                '\n'
                                '其他牌型中，Joker只能当A。\n'
                                '不能任意变成其他点数来凑对子。\n'
                                '\n'
                                '当A后自然形成A对子、三条A、葫芦、\n'
                                '四条A或五条A，均按对应牌型计算。'
                            ),
                            (
                                '前道：固定当A',
                                'Joker＋A：A对子。\n'
                                'Joker＋K：A-K高牌。\n'
                                '\n'
                                'Joker不能在前道任意配成另一张牌的对子。'
                            ),
                        ],
                        [],
                    ),
                ],
            ),
            (
                '特别事项',
                '提交前检查分牌。\n'
                '结算时区分本金、奖金与净盈亏。',
                [
                    (
                        '分牌有效性',
                        '',
                        [
                            (
                                '后道必须严格强于前道',
                                '后道牌型高于前道时，分牌有效。\n'
                                '\n'
                                '若两道都是高牌：\n'
                                '先比最高点数，再比第二高点数。\n'
                                '比较到此仍相同，则分牌无效。\n'
                                '\n'
                                '若两道都是对子：\n'
                                '后道对子的点数必须更高。\n'
                                '\n'
                                '不要把较大的对子放前道，\n'
                                '却让后道只剩较小对子。'
                            ),
                            (
                                '自动分牌',
                                '“自动分牌”使用程序的庄家分牌策略。\n'
                                '它会结合完整七张牌处理各种组合。\n'
                                '推荐结果并不保证赢过庄家。\n'
                                '\n'
                                '下方仅说明有效分牌。\n'
                                '不作为全部庄家策略的固定表。'
                            ),
                        ],
                        [],
                    ),
                    (
                        '图解一：保留对子',
                        '前道A-K高牌，后道7对子。\n'
                        '后道强于前道，分牌有效。',
                        [],
                        [
                            (
                                '两张前道＋五张后道',
                                ['位置', '牌例'],
                                [
                                    [
                                        '前道',
                                        cards(('♠', 'A'), ('♥', 'K')),
                                    ],
                                    [
                                        '后道',
                                        cards(
                                            ('♠', '7'), ('♥', '7'),
                                            ('♦', '9'), ('♣', '5'),
                                            ('♠', '2'),
                                        ),
                                    ],
                                ],
                            ),
                        ],
                    ),
                    (
                        '图解二：拆开两对',
                        '前道Q对子，后道A对子。\n'
                        'A对子更大，分牌有效。',
                        [],
                        [
                            (
                                '两张前道＋五张后道',
                                ['位置', '牌例'],
                                [
                                    [
                                        '前道',
                                        cards(('♣', 'Q'), ('♦', 'Q')),
                                    ],
                                    [
                                        '后道',
                                        cards(
                                            ('♠', 'A'), ('♥', 'A'),
                                            ('♠', '9'), ('♥', '6'),
                                            ('♦', '3'),
                                        ),
                                    ],
                                ],
                            ),
                        ],
                    ),
                    (
                        '图解三：Joker放前道',
                        '前道Joker-K按A-K高牌计算。\n'
                        '后道保留7对子，分牌有效。',
                        [],
                        [
                            (
                                '两张前道＋五张后道',
                                ['位置', '牌例'],
                                [
                                    [
                                        '前道',
                                        cards(('JOKER', 'A'), ('♦', 'K')),
                                    ],
                                    [
                                        '后道',
                                        cards(
                                            ('♠', '7'), ('♥', '7'),
                                            ('♣', '9'), ('♦', '5'),
                                            ('♠', '2'),
                                        ),
                                    ],
                                ],
                            ),
                        ],
                    ),
                    (
                        '金额如何计算',
                        '',
                        [
                            (
                                '净赔率与总返还',
                                '净赔率N:1：净赢下注金额×N。\n'
                                '中奖总返还：下注金额×(N＋1)。\n'
                                '平局：只退本金。\n'
                                '未中奖：返还0。\n'
                                '\n'
                                '本局净盈亏：\n'
                                '各项总返还－开局扣除的全部下注。'
                            ),
                            (
                                '示例一：经典模式底注获胜',
                                '底注$10，未买边注。\n'
                                '玩家两道都赢。\n'
                                '\n'
                                '净赢：$10×0.95＝$9.50。\n'
                                '总返还：$10＋$9.50＝$19.50。'
                            ),
                            (
                                '示例二：免佣模式特殊平局',
                                '底注$10，未买边注。\n'
                                '玩家分牌有效。\n'
                                '庄家七张牌的最佳五张为A高牌。\n'
                                '\n'
                                '无论两道比较结果，底注返还$10。\n'
                                '本局净盈亏为$0。'
                            ),
                            (
                                '示例三：底注输，保险中奖',
                                '底注$10，牌九保险$10。\n'
                                '合计下注$20。\n'
                                '玩家七张牌最佳五张为Q高牌。\n'
                                '底注两道都输。\n'
                                '\n'
                                '底注返还：$0。\n'
                                '保险按7:1赔付。\n'
                                '保险返还：$10×8＝$80。\n'
                                '\n'
                                '本局净赢：$80－$20＝$60。'
                            ),
                            (
                                '无效分牌与边注',
                                '分牌无效时，底注返还0。\n'
                                '已购买的边注仍按原始七张牌各自判奖。\n'
                                '\n'
                                '包括牌九保险、皇帝之财、柔佛州，\n'
                                '以及免佣模式已购买的A高平手。\n'
                                '\n'
                                '各项边注独立结算。\n'
                                '同一边注内的不同档位不叠加。'
                            ),
                        ],
                        [],
                    ),
                    (
                        '其他操作',
                        '',
                        [
                            (
                                '查看牌序',
                                '右键点击“再来一局”按钮，\n'
                                '可查看本局牌序。'
                            ),
                        ],
                        [],
                    ),
                ],
            ),
        ]
        manual_pages[1][2].append((
            'UTH通用操作', '', [
                ('双玩家牌桌', '玩家1和玩家2可独立下注并分别拆牌；至少一手有底注才能开牌。两手共用同一庄家与余额。未下底注的另一手不参加本局，其边注筹码会返回。'),
                ('牌位与升序排列', '玩家七张牌先发到第二行；翻开后按2、3、4、…、Q、K、A、Joker从小到大移动排序。选中的牌立即移到上方居中的前道；选满两张后，剩下五张留在第二行中间五个牌位，两端留空。点击前道已选牌可取消并重新选择。庄家七张牌先全部发到第一行，牌间空隙与玩家相同。第二行的两个前道虚线牌位始终显示，派牌时不使用，并与首行七张牌位居中对齐。翻牌分牌后，五张后道以动画占用第一行中间五格，两端留空；两张前道移至第二行。首行仍保留七张牌位，庄家牌区宽度始终固定。'),
                ('提交后的展示', '前道两张按左大右小排列。提交后五张后道按Caribbean的牌型顺序移动排序：顺子按点数升序（A2345的A在左），其他牌型先展示对子、三条等组合，再展示散牌。三家的标题固定，牌型只显示在各自的两行表格里。'),
                ('牌型表格的颜色', '玩家未比牌时使用深色底与浅色文字。玩家各道比较后，获胜行用金底黑字，落败行用柔和红底黑字。免佣模式庄家A高且玩家分牌有效时，玩家两行均用浅蓝底黑字；同道同点仍按原规则判庄家胜。庄家开牌且玩家提交后，玩家即可显示对应的比较颜色。庄家表格只显示自身后道与前道的牌型，始终使用固定的深色底与浅色文字。'),
                ('错误分牌提示', '提交分牌后，若前道强于后道，或不符合后道必须强于前道的规则，该玩家两行牌之间淡入显示“错误布道，主注自动输”。选牌过程中不显示该提示。无效分牌的主注判输，边注仍按原赔率独立结算；提示在返还筹码及收牌时淡出。'),
                ('高额下注', '沿用UTH的限红切换：点击左上限红表，输入当前本机时分（HHMM）可切换高额限红。高额模式底注$100～$50,000，每项边注最高$12,500；普通模式保留牌九原限红。'),
                ('筹码、结算及下一局', '左键加筹码，右键清除该项。Enter开牌；结算后Enter或“再来一局”返还筹码并收牌。30秒后自动进入下一局；右键“再来一局”暂停倒计时并查看含Joker的53张牌序。派彩先显示在桌上，筹码收回后余额入账。'),
            ], []))
        return manual_pages

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
        instruction_title = f'牌九扑克 · {GAME_MODE_NAMES[self.game.mode]}玩法'
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
                                key = 'joker' if suit == 'JOKER' else (suit, rank)
                                original = self.original_images.get(key, self.original_images['back'])
                                small_image = original.resize((70, 98), Image.Resampling.LANCZOS)
                                photo = ImageTk.PhotoImage(small_image, master=dialog)
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
        dialog.after(30, dialog.focus_force)


def main(initial_balance=10000, username="Guest", *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """保持原 Pai Gow 的嵌入式入口，也支持在原项目中独立运行。"""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user
    if parent is not None:
        return PaiGowPokerGUI(parent, actual_balance, actual_user,
                             on_back=on_back, on_balance_change=on_balance_change)
    root = tk.Tk()
    root.title("牌九扑克")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = PaiGowPokerGUI(root, actual_balance, actual_user,
                         on_back=on_back, on_balance_change=on_balance_change)
    page.pack(fill="both", expand=True)
    root.protocol("WM_DELETE_WINDOW", page.on_close)
    root.mainloop()
    return page.balance


if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")
