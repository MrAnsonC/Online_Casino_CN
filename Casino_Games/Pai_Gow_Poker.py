import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import json
import os
import secrets
import subprocess
import sys
import webbrowser
from itertools import combinations, product
from collections import Counter

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
    return os.path.join(parent_dir, 'saving_data.json')

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
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
        shuffle_script = os.path.join(card_dir, 'shuffle.py')
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        try:
            result = subprocess.run(
                [sys.executable, shuffle_script, 'true', '1'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                env=env,
                check=True,
                timeout=30
            )
            shuffle_data = json.loads(result.stdout)
            self.full_deck = [Card(d["suit"], d["rank"]) for d in shuffle_data["deck"]]
            self.cut_position = shuffle_data["cut_position"]
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
    # =========================================================
    ace_total = len(groups.get(14, []))
    if ace_total >= 5:
        ace_cards = groups[14]

        if len(ace_cards) >= 2:
            front = ace_cards[:2]
            back = [c for c in hand7 if c not in front]
            return front, back

        front = choose_top_two(hand7)
        back = [c for c in hand7 if c not in front]
        return front, back

    # =========================================================
    # 2) Five Aces
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
                return bet * 5000
            if values == [2, 3, 4, 5, 6, 7, 14]:
                return bet * 5000

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
                        return bet * 1000
                needed = {14, 2, 3, 4, 5, 6, 7}
                if all(v in needed for v in real_values) and len(needed - set(real_values)) == joker_cnt:
                    return bet * 1000

    # 5 cards A
    aces = [c for c in hand7 if c.rank == 'A']
    jokers = [c for c in hand7 if c.is_joker]
    if len(aces) + len(jokers) >= 5:
        return bet * 500

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
class PaiGowPokerGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("牌九扑克")
        self.geometry("1320x790+40+10")
        self.resizable(False, False)
        self.configure(bg='#35654d')

        self.username = username
        self.balance = initial_balance
        self.game = PaiGowPoker()

        self.card_images = {}
        self.original_images = {}
        self.selected_chip = None
        self.chip_buttons = []
        self.chip_texts = {}
        self.bet_widgets = {}
        self.active_card_labels = []
        self.auto_reset_timer = None
        self.restart_btn = None
        self._resetting = False
        self.animation_queue = []
        self.betting_enabled = True
        self.commission_free = tk.BooleanVar(value=False)
        self.animation_in_progress = False
        self.selected_low_indices = []
        self.removing_cards = False      # 新增：卡片移除动画标志

        self.last_bet = None          # 新增：存储上次下注记录
        self.repeat_bet_btn = None    # 新增：重复下注按钮引用

        # 新增边注金额
        self.johor_bet_amount = 0
        self.ace_high_push_bet_amount = 0

        self.card_width = 100
        self.card_height = 150
        self.card_spacing = 5

        self._load_assets()
        self._create_widgets()
        self.after(100, self._show_startup_warning)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------- 生命周期 -------------------------
    def cancel_auto_reset_timer(self):
        if self.auto_reset_timer:
            try:
                self.after_cancel(self.auto_reset_timer)
            except Exception:
                pass
            self.auto_reset_timer = None

    def on_close(self):
        self.cancel_auto_reset_timer()
        self.destroy()
        self.quit()

    # ------------------------- 资源 -------------------------
    def _load_assets(self):
        card_size = (self.card_width, self.card_height)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        cls = type(self)
        next_folder = getattr(cls, "_next_poker_folder", "Poker1")
        self.current_poker_folder = next_folder
        cls._next_poker_folder = "Poker2" if next_folder == "Poker1" else "Poker1"

        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', self.current_poker_folder)
        suit_mapping = {'♠': 'Spade', '♥': 'Heart', '♦': 'Diamond', '♣': 'Club', 'JOKER': 'JOKER'}

        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_img_orig = Image.open(back_path)
            self.original_images["back"] = back_img_orig
            self.back_image = ImageTk.PhotoImage(back_img_orig.resize(card_size))
        except Exception:
            img_orig = Image.new('RGB', card_size, 'black')
            self.original_images["back"] = img_orig
            self.back_image = ImageTk.PhotoImage(img_orig)

        for suit in SUITS + ['JOKER']:
            for rank in RANKS:
                filename = "JOKER-A.png" if suit == 'JOKER' else f"{suit_mapping[suit]}{rank}.png"
                path = os.path.join(card_dir, filename)
                try:
                    if os.path.exists(path):
                        img = Image.open(path)
                        self.original_images[(suit, rank)] = img
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img.resize(card_size))
                    else:
                        img_orig = Image.new('RGB', card_size, 'blue')
                        draw = ImageDraw.Draw(img_orig)
                        text = "JOKER" if suit == 'JOKER' else f"{rank}{suit}"
                        try:
                            font = ImageFont.truetype("arial.ttf", 20)
                        except:
                            font = ImageFont.load_default()
                        draw.text((10, 10), text, fill="white", font=font)
                        self.original_images[(suit, rank)] = img_orig
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
                except:
                    pass

    def _show_startup_warning(self):
        """游戏启动时显示自定义提示窗口（带可点击链接），两行显示。"""
        dialog = tk.Toplevel(self)
        dialog.title("游戏通告")
        dialog.geometry("500x130")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # 第一行文本
        line1 = tk.Label(
            dialog,
            text="本游戏的‘庄家分牌’可能存在问题",
            font=('微软雅黑', 12),
            justify=tk.LEFT
        )
        line1.pack(pady=(10, 0))

        # 第二行文本（组合 Frame）
        line2_frame = tk.Frame(dialog, bg=dialog.cget("bg"))
        line2_frame.pack(pady=5)

        tk.Label(
            line2_frame,
            text="如果发生了，请",
            font=('微软雅黑', 12),
            bg=dialog.cget("bg")
        ).pack(side=tk.LEFT)

        link_lbl = tk.Label(
            line2_frame,
            text="【按我】",
            font=('微软雅黑', 12, 'underline'),
            fg="blue",
            bg=dialog.cget("bg"),
            cursor="hand2"
        )
        link_lbl.pack(side=tk.LEFT)
        link_lbl.bind("<Button-1>", lambda e: self._open_github_issue())

        tk.Label(
            line2_frame,
            text="到Github反馈",
            font=('微软雅黑', 12),
            bg=dialog.cget("bg")
        ).pack(side=tk.LEFT)

        # 确定按钮
        btn = tk.Button(dialog, text="确定", command=dialog.destroy, width=10)
        btn.pack(pady=10)

        # 居中显示
        dialog.update_idletasks()
        w = dialog.winfo_width()
        h = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (w // 2)
        y = (dialog.winfo_screenheight() // 2) - (h // 2)
        dialog.geometry(f'+{x}+{y}')
        dialog.focus_set()

    def _open_github_issue(self):
        """打开 GitHub Issues 页面。"""
        webbrowser.open("https://github.com/MrAnsonC/Online_Casino_CN/issues")

    def _card_image_for(self, card):
        return self.card_images.get((card.suit, card.rank), self.back_image)

    def _create_card_label(self, parent, card, face_up=False, y_offset=0, border=0):
        img = self._card_image_for(card) if face_up else self.back_image
        lbl = tk.Label(parent, image=img, bg='#2a4a3c', bd=border)
        lbl.image = img
        lbl.card = card
        lbl.is_face_up = face_up
        lbl.base_y = y_offset
        return lbl

    def _on_commission_toggle(self):
        self._update_commission_rule_label()
        self._update_ace_push_visibility()   # 新增：根据免佣状态显示/隐藏A高平手边注

    def _update_commission_free_state(self):
        """根据游戏阶段启用/禁用免佣开关"""
        if self.game.stage == "betting":
            self.commission_check.config(state=tk.NORMAL)
        else:
            self.commission_check.config(state=tk.DISABLED)

    def _update_commission_rule_label(self):
        """根据免佣开关状态更新规则说明文本"""
        if self.commission_free.get():
            rule_text = "庄家牌型为高牌A时，底注平局处理"
        else:
            rule_text = "当前底注以0.95:1结算"
        self.commission_rule_label.config(text=rule_text)

    def _update_ace_push_visibility(self):
        """根据免佣模式显示/隐藏A高平手边注控件（使用grid_remove保持布局宽度）"""
        if self.commission_free.get():
            self.ace_push_frame.grid()
        else:
            self.ace_push_frame.grid_remove()
            # 同时将下注金额清零（避免残留）
            self.ace_push_var.set("0")
            self.ace_high_push_bet_amount = 0

    # ------------------------- UI -------------------------
    def _create_widgets(self):
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 庄家区 - 高度350
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=35, y=10, width=785, height=370)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18),
                                    bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)

        dealer_body = tk.Frame(dealer_frame, bg='#2a4a3c')
        dealer_body.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.dealer_cards_area = tk.Frame(dealer_body, bg='#2a4a3c', width=700, height=290)
        self.dealer_cards_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.dealer_cards_area.pack_propagate(False)

        # 玩家区 - 高度350
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=35, y=390, width=785, height=370)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 18),
                                    bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)

        player_body = tk.Frame(player_frame, bg='#2a4a3c')
        player_body.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.player_cards_area = tk.Frame(player_body, bg='#2a4a3c', width=700, height=290)
        self.player_cards_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.player_cards_area.pack_propagate(False)

        # 控制区（右侧）
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=440, padx=10, pady=5)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        control_frame.pack_propagate(False)

        info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=5)
        self.balance_label = tk.Label(info_frame, text=f"余额: ${self.balance:.2f}",
                                    font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=5)
        self.stage_label = tk.Label(info_frame, text="下注阶段", font=('Arial', 18, 'bold'),
                                    bg='#2a4a3c', fg='#FFD700')
        self.stage_label.pack(side=tk.RIGHT, padx=20, pady=5)

        # 筹码区域
        chips_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        chips_frame.pack(fill=tk.X, pady=5)
        self.chips_label = tk.Label(chips_frame, text="筹码:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        self.chips_label.pack(anchor='w', padx=10, pady=5)
        self.chip_container = tk.Frame(chips_frame, bg='#2a4a3c')
        self.chip_container.pack(fill=tk.X, pady=5, padx=5)
        self._rebuild_chips()

        limits_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        limits_frame.pack(fill=tk.X, pady=5)
        header_frame = tk.Frame(limits_frame, bg='#2a4a3c')
        header_frame.pack(fill=tk.X, padx=10, pady=(5, 0))
        for text in ("底注最高", "底注最高", "边注最高"):
            tk.Label(header_frame, text=text, font=('Arial', 12, 'bold'),
                    bg='#2a4a3c', fg='white', width=10).pack(side=tk.LEFT, expand=True)
        value_frame = tk.Frame(limits_frame, bg='#2a4a3c')
        value_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        for text in ("$10", "$25,000", "$2,500"):
            tk.Label(value_frame, text=text, font=('Arial', 12, 'bold'),
                    bg='#2a4a3c', fg='#FFD700', width=10).pack(side=tk.LEFT, expand=True)

        # ----- 免佣开关（动态规则说明）-----
        commission_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        commission_frame.pack(fill=tk.X, pady=5)

        self.commission_check = tk.Checkbutton(
            commission_frame,
            text="免佣模式",
            variable=self.commission_free,
            font=('Arial', 16),
            bg='#2a4a3c',
            fg='white',
            selectcolor='#2a4a3c',
            activebackground='#2a4a3c',
            command=self._on_commission_toggle
        )
        self.commission_check.pack(side=tk.LEFT, padx=(10, 5), pady=5)

        self.commission_rule_label = tk.Label(
            commission_frame,
            text="",
            font=('Arial', 12),
            bg='#2a4a3c',
            fg='#FFD700'
        )
        self.commission_rule_label.pack(side=tk.LEFT, padx=5, pady=5)

        self._update_commission_rule_label()

        # 下注区域
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=8)

        # 第一行：皇帝之财 和 牌九保险
        row_top = tk.Frame(bet_frame, bg='#2a4a3c')
        row_top.pack(fill=tk.X, padx=10, pady=3)

        tk.Label(row_top, text="皇帝之财:", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT, padx=(0,5))
        self.emperor_var = tk.StringVar(value="0")
        self.emperor_display = tk.Label(row_top, textvariable=self.emperor_var, font=('Arial', 14),
                                        bg='white', width=7, relief=tk.SUNKEN)
        self.emperor_display.pack(side=tk.LEFT, padx=5)
        self.emperor_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("emperor"))
        self.bet_widgets["emperor"] = self.emperor_display

        tk.Label(row_top, text="牌九保险:", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT, padx=(15,5))
        self.insurance_var = tk.StringVar(value="0")
        self.insurance_display = tk.Label(row_top, textvariable=self.insurance_var, font=('Arial', 14),
                                        bg='white', width=7, relief=tk.SUNKEN)
        self.insurance_display.pack(side=tk.LEFT, padx=5)
        self.insurance_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("insurance"))
        self.bet_widgets["insurance"] = self.insurance_display

        # ========== 新增行：柔佛州 和 A高平手 ==========
        row_mid = tk.Frame(bet_frame, bg='#2a4a3c')
        row_mid.pack(fill=tk.X, padx=10, pady=3)
        # 设置两列等权重，确保宽度不因某列隐藏而变化
        row_mid.columnconfigure(0, weight=1)
        row_mid.columnconfigure(1, weight=1)

        # 柔佛州（始终显示）
        johor_frame = tk.Frame(row_mid, bg='#2a4a3c')
        johor_frame.grid(row=0, column=0, sticky='ew', padx=(9,5))
        tk.Label(johor_frame, text="  柔佛州:", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT, padx=(0,5))
        self.johor_var = tk.StringVar(value="0")
        self.johor_display = tk.Label(johor_frame, textvariable=self.johor_var, font=('Arial', 14),
                                      bg='white', width=7, relief=tk.SUNKEN)
        self.johor_display.pack(side=tk.LEFT, padx=5)
        self.johor_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("johor"))
        self.bet_widgets["johor"] = self.johor_display

        # A高平手（根据免佣模式动态显示）
        self.ace_push_frame = tk.Frame(row_mid, bg='#2a4a3c')
        self.ace_push_frame.grid(row=0, column=1, sticky='ew', padx=(10,0))
        tk.Label(self.ace_push_frame, text="A高平手:", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT, padx=(0,5))
        self.ace_push_var = tk.StringVar(value="0")
        self.ace_push_display = tk.Label(self.ace_push_frame, textvariable=self.ace_push_var, font=('Arial', 14),
                                         bg='white', width=7, relief=tk.SUNKEN)
        self.ace_push_display.pack(side=tk.LEFT, padx=5)
        self.ace_push_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ace_push"))
        self.bet_widgets["ace_push"] = self.ace_push_display

        # 根据初始免佣状态决定是否显示（使用 grid_remove 保持列宽）
        if not self.commission_free.get():
            self.ace_push_frame.grid_remove()
        # =============================================

        # 第二行：底注
        row_bottom = tk.Frame(bet_frame, bg='#2a4a3c')
        row_bottom.pack(fill=tk.X, padx=80, pady=3)

        tk.Label(row_bottom, text="底注:", font=('Arial', 22), bg='#2a4a3c', fg='white').pack(side=tk.LEFT)
        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(row_bottom, textvariable=self.ante_var, font=('Arial', 22),
                                    bg='white', width=7, relief=tk.SUNKEN)
        self.ante_display.pack(side=tk.LEFT)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.bet_widgets["ante"] = self.ante_display

        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        self.action_frame.pack(fill=tk.X)

        start_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_frame.pack(pady=5)

        # 重置金额按钮
        self.reset_bets_button = tk.Button(start_frame, text="重置金额", command=self.reset_bets,
                                           font=('Arial', 14), bg='#F44336', fg='white', width=10)
        self.reset_bets_button.pack(side=tk.LEFT, padx=(10, 10))

        # 重复上局下注按钮（初始禁用）
        self.repeat_bet_btn = tk.Button(start_frame, text="重复上局下注", command=self.apply_last_bet,
                                        font=('Arial', 14), bg='#4A90E2', fg='white',
                                        activebackground='#3A7BC8', width=12, state=tk.DISABLED)
        self.repeat_bet_btn.pack(side=tk.LEFT, padx=(0, 10))

        # 开始游戏按钮
        self.start_button = tk.Button(start_frame, text="开始游戏", command=self.start_game,
                                      font=('Arial', 14), bg='#4CAF50', fg='white', width=10)
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))

        self.status_label = tk.Label(control_frame, text="设置下注金额并开始游戏",
                                    font=('Arial', 14), bg='#2a4a3c', fg='white')
        self.status_label.pack(pady=5, fill=tk.X)

        bet_info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_info_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.current_bet_label = tk.Label(bet_info_frame, text="本局下注: $0.00",
                                        font=('Arial', 12), bg='#2a4a3c', fg='white')
        self.current_bet_label.pack(pady=5, padx=10, anchor='w')
        self.last_win_label = tk.Label(bet_info_frame, text="上局获胜: $0.00",
                                    font=('Arial', 12), bg='#2a4a3c', fg='#FFD700')
        self.last_win_label.pack(pady=5, padx=10, anchor='w', side=tk.LEFT)
        rules_btn = tk.Button(bet_info_frame, text="ℹ️", command=self.show_game_instructions,
                            font=('Arial', 8), bg='#4B8BBE', fg='white')
        rules_btn.pack(side=tk.RIGHT, padx=10, pady=5)

    def _rebuild_chips(self):
        for widget in self.chip_container.winfo_children():
            widget.destroy()
        self.chip_buttons = []
        self.selected_chip = None
        chip_configs = [
            ('$10', 'orange', 'black'),
            ('$25', '#00ff00', 'black'),
            ('$100', 'black', 'white'),
            ('$500', '#FF7DDA', 'black'),
            ('$1K', 'white', 'black'),
            ('$2.5K', 'red', 'white')
        ]
        default = "$10"
        for text, bg, fg in chip_configs:
            chip_canvas = tk.Canvas(self.chip_container, width=57, height=57, bg='#2a4a3c', highlightthickness=0)
            chip_canvas.create_oval(2, 2, 55, 55, fill=bg, outline='black')
            chip_canvas.create_text(27.5, 27.5, text=text, fill=fg, font=('Arial', 14, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text
        self.select_chip(default)

    def select_chip(self, chip_text):
        self.selected_chip = chip_text
        for chip in self.chip_buttons:
            chip.delete("highlight")
            for item in chip.find_all():
                if chip.type(item) == 'oval':
                    x1, y1, x2, y2 = chip.coords(item)
                    chip.create_oval(x1, y1, x2, y2, outline='black', width=2)
                    break
        for chip in self.chip_buttons:
            for item in chip.find_all():
                if chip.type(item) == 'text' and chip.itemcget(item, 'text') == chip_text:
                    oval = [i for i in chip.find_all() if chip.type(i) == 'oval'][0]
                    x1, y1, x2, y2 = chip.coords(oval)
                    chip.create_oval(x1, y1, x2, y2, outline='gold', width=3, tags="highlight")
                    break

    def add_chip_to_bet(self, bet_type):
        if not self.betting_enabled:
            return
        if not self.selected_chip:
            return

        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K', '')) * 1000
        else:
            chip_value = float(chip_text)

        max_ante = 25000
        max_side = 2500

        if bet_type == "ante":
            current = float(self.ante_var.get())
            new_val = current + chip_value
            if new_val > max_ante:
                new_val = max_ante
                messagebox.showwarning("下注限制", f"底注上限为 {max_ante}")
            self.ante_var.set(str(int(new_val)))
        elif bet_type == "insurance":
            current = float(self.insurance_var.get())
            new_val = current + chip_value
            if new_val > max_side:
                new_val = max_side
                messagebox.showwarning("下注限制", f"牌九保险上限为 {max_side}")
            self.insurance_var.set(str(int(new_val)))
        elif bet_type == "emperor":
            current = float(self.emperor_var.get())
            new_val = current + chip_value
            if new_val > max_side:
                new_val = max_side
                messagebox.showwarning("下注限制", f"皇帝之财上限为 {max_side}")
            self.emperor_var.set(str(int(new_val)))
        elif bet_type == "johor":
            current = float(self.johor_var.get())
            new_val = current + chip_value
            if new_val > max_side:
                new_val = max_side
                messagebox.showwarning("下注限制", f"柔佛州上限为 {max_side}")
            self.johor_var.set(str(int(new_val)))
        elif bet_type == "ace_push":
            if not self.commission_free.get():
                messagebox.showwarning("边注不可用", "A高平手边注仅在免佣模式下可用")
                return
            current = float(self.ace_push_var.get())
            new_val = current + chip_value
            if new_val > max_side:
                new_val = max_side
                messagebox.showwarning("下注限制", f"A高平手上限为 {max_side}")
            self.ace_push_var.set(str(int(new_val)))

    def _clear_hand_areas(self):
        for w in self.player_cards_area.winfo_children():
            w.destroy()
        for w in self.dealer_cards_area.winfo_children():
            w.destroy()
        self.player_card_labels = []
        self.dealer_card_labels = []

    # 发牌动画，修改Y坐标：庄家区内Y=180，玩家区内Y=150（对应全局Y≈190和540）
    def animate_deal(self):
        self.animation_queue = []
        total_width = 7 * self.card_width + 6 * self.card_spacing
        start_x = (700 - total_width) // 2
        if start_x < 0:
            start_x = 20
        for i, card in enumerate(self.game.player_hand):
            x = start_x + i * (self.card_width + self.card_spacing)
            y = 160   # 玩家区内Y坐标
            self.animation_queue.append(("player", i, card, x, y))
        for i, card in enumerate(self.game.dealer_hand):
            x = start_x + i * (self.card_width + self.card_spacing)
            y = 160   # 庄家区内Y坐标
            self.animation_queue.append(("dealer", i, card, x, y))

        self.animation_in_progress = True
        self._process_animation_queue()

    def _process_animation_queue(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            # 根据免佣模式决定下一步
            if hasattr(self, 'use_commission_flow') and self.use_commission_flow:
                self.after(500, self.reveal_all_and_dealer_split)
            else:
                self.after(500, self.reveal_player_cards)
            return

        who, idx, card, target_x, target_y = self.animation_queue.pop(0)

        if who == "player":
            parent = self.player_cards_area
            labels = self.player_card_labels
        else:
            parent = self.dealer_cards_area
            labels = self.dealer_card_labels

        lbl = self._create_card_label(parent, card, face_up=False)
        lbl.place(x=0, y=0, width=self.card_width, height=self.card_height)
        labels.append(lbl)

        self._animate_move(lbl, target_x, target_y, start_x=0, start_y=0)

    def _animate_move(self, label, target_x, target_y, step=0, steps=20, start_x=0, start_y=0):
        if step > steps:
            label.place(x=target_x, y=target_y, width=self.card_width, height=self.card_height)
            self._process_animation_queue()
            return
        cur_x = start_x + (target_x - start_x) * step / steps
        cur_y = start_y + (target_y - start_y) * step / steps
        label.place(x=cur_x, y=cur_y, width=self.card_width, height=self.card_height)
        self.after(15, lambda: self._animate_move(label, target_x, target_y, step + 1, steps, start_x, start_y))

    def flip_card_animation(self, label):
        if label is None or not label.winfo_exists():
            return
        card = label.card
        front_img = self._card_image_for(card)

        def animate(step=0):
            if self._resetting or not label.winfo_exists():
                return
            try:
                if step > 10:
                    if label.winfo_exists():
                        label.config(image=front_img)
                        label.image = front_img
                        label.is_face_up = True
                        label.place(width=self.card_width, height=self.card_height)
                    return
                if step <= 5:
                    width = self.card_width - step * 10
                    if width < 1:
                        width = 1
                    if label.winfo_exists():
                        label.config(image=self.back_image)
                        label.image = self.back_image
                else:
                    width = (step - 5) * 10
                    if width < 1:
                        width = 1
                    if label.winfo_exists():
                        label.config(image=front_img)
                        label.image = front_img
                if label.winfo_exists():
                    label.place(width=width, height=self.card_height)
                self.after(50, lambda: animate(step + 1))
            except tk.TclError:
                return
        animate(0)

    def reveal_all_and_dealer_split(self):
        """免佣模式：同时翻开玩家和庄家所有牌，庄家立即分牌并排序，然后玩家排序并进入分牌阶段"""
        # 同时翻转所有玩家牌
        for label in self.player_card_labels:
            if label.winfo_exists() and not label.is_face_up:
                self.flip_card_animation(label)
        # 同时翻转所有庄家牌
        for label in self.dealer_card_labels:
            if label.winfo_exists() and not label.is_face_up:
                self.flip_card_animation(label)
        # 等待动画完成后再执行庄家分牌（动画约0.5秒，延迟1秒）
        self.after(1000, self.dealer_auto_split_and_sort)

    def dealer_auto_split_and_sort(self):
        """庄家使用 House way 分牌并排序显示"""
        low, high = dealer_way_split(self.game.dealer_hand)
        self.game.dealer_low = low
        self.game.dealer_high = high
        self.sort_dealer_hand_after_split()
        # 免佣模式下，玩家分牌前先显示庄家牌型描述
        dealer_desc = self._format_hand_description(self.game.dealer_low, self.game.dealer_high)
        self.dealer_label.config(text=f"庄家 -  {dealer_desc}")
        self.player_sort_and_enable_split()

    def player_sort_and_enable_split(self):
        """玩家手牌升序排列，然后进入分牌阶段"""
        sorted_hand = sorted(self.game.player_hand, key=lambda c: rank_2_card_value(c))
        labels = self.player_card_labels
        card_to_label = {lbl.card: lbl for lbl in labels if lbl.winfo_exists()}
        start_positions = {}
        for lbl in labels:
            info = lbl.place_info()
            start_positions[lbl] = (float(info.get('x', 0)), float(info.get('y', 0)))
        total_width = 7 * self.card_width + 6 * self.card_spacing
        start_x = (700 - total_width) // 2
        if start_x < 0:
            start_x = 20
        target_positions = {}
        for idx, card in enumerate(sorted_hand):
            lbl = card_to_label[card]
            x = start_x + idx * (self.card_width + self.card_spacing)
            y = start_positions[lbl][1]
            target_positions[lbl] = (x, y)
        steps = 20
        interval = 25
        anim_data = []
        for lbl, (sx, sy) in start_positions.items():
            tx, ty = target_positions[lbl]
            dx = (tx - sx) / steps
            dy = (ty - sy) / steps
            anim_data.append((lbl, sx, sy, dx, dy))

        def animate_step(step):
            if step > steps:
                for lbl, _, _, _, _ in anim_data:
                    if lbl.winfo_exists():
                        x, y = target_positions[lbl]
                        lbl.place(x=x, y=y, width=self.card_width, height=self.card_height)
                # 重新排列 self.player_card_labels 的顺序
                new_labels = []
                for card in sorted_hand:
                    new_labels.append(card_to_label[card])
                self.player_card_labels = new_labels
                self.game.player_hand = sorted_hand
                # 排序完成后，启用玩家分牌
                self.enable_player_split()
                return
            for lbl, sx, sy, dx, dy in anim_data:
                if lbl.winfo_exists():
                    lbl.place(x=sx + dx*step, y=sy + dy*step, width=self.card_width, height=self.card_height)
            self.after(interval, lambda: animate_step(step+1))
        animate_step(1)

    def reveal_player_cards(self):
        for label in self.player_card_labels:
            if label.winfo_exists() and not label.is_face_up:
                self.flip_card_animation(label)
        self.after(1000, self.sort_player_hand_ascending)

    def sort_player_hand_ascending(self):
        sorted_hand = sorted(self.game.player_hand, key=lambda c: rank_2_card_value(c))
        labels = self.player_card_labels
        card_to_label = {lbl.card: lbl for lbl in labels if lbl.winfo_exists()}
        start_positions = {}
        for lbl in labels:
            info = lbl.place_info()
            start_positions[lbl] = (float(info.get('x', 0)), float(info.get('y', 0)))
        total_width = 7 * self.card_width + 6 * self.card_spacing
        start_x = (700 - total_width) // 2
        if start_x < 0:
            start_x = 20
        target_positions = {}
        for idx, card in enumerate(sorted_hand):
            lbl = card_to_label[card]
            x = start_x + idx * (self.card_width + self.card_spacing)
            y = start_positions[lbl][1]
            target_positions[lbl] = (x, y)
        steps = 20
        interval = 25
        anim_data = []
        for lbl, (sx, sy) in start_positions.items():
            tx, ty = target_positions[lbl]
            dx = (tx - sx) / steps
            dy = (ty - sy) / steps
            anim_data.append((lbl, sx, sy, dx, dy))
        def animate_step(step):
            if step > steps:
                for lbl, _, _, _, _ in anim_data:
                    if lbl.winfo_exists():
                        x, y = target_positions[lbl]
                        lbl.place(x=x, y=y, width=self.card_width, height=self.card_height)
                # 重要：重新排列 self.player_card_labels 的顺序，使其与 sorted_hand 一致
                new_labels = []
                for card in sorted_hand:
                    new_labels.append(card_to_label[card])
                self.player_card_labels = new_labels
                self.game.player_hand = sorted_hand
                self.enable_player_split()
                return
            for lbl, sx, sy, dx, dy in anim_data:
                if lbl.winfo_exists():
                    lbl.place(x=sx + dx*step, y=sy + dy*step, width=self.card_width, height=self.card_height)
            self.after(interval, lambda: animate_step(step+1))
        animate_step(1)

    def enable_player_split(self):
        self._update_commission_free_state()
        self.game.stage = "split"
        self.stage_label.config(text="分牌")
        self.status_label.config(text="选择两张牌作为前道，然后提交分牌\n\n提示:'后道'必须比'前道'强，否则判负！")
        self.selected_low_indices = []
        for i, lbl in enumerate(self.player_card_labels):
            y = lbl.winfo_y()
            lbl.base_y = y
            lbl.bind("<Button-1>", lambda e, idx=i: self.toggle_card_selection(idx))

        action_bar = tk.Frame(self.action_frame, bg='#2a4a3c')
        action_bar.pack(pady=5)
        self.auto_split_button = tk.Button(action_bar, text="自动分牌", command=self.auto_split,
                                           font=('Arial', 14), bg='#2196F3', fg='white', width=12)
        self.auto_split_button.pack(side=tk.LEFT, padx=4)
        self.submit_button = tk.Button(action_bar, text="提交分牌", command=self.submit_split,
                                       font=('Arial', 14), bg='#4CAF50', fg='white', width=12)
        self.submit_button.pack(side=tk.LEFT, padx=4)

    def toggle_card_selection(self, idx):
        if self.game.stage != "split":
            return
        lbl = self.player_card_labels[idx]
        orig_y = lbl.base_y
        if idx in self.selected_low_indices:
            self.selected_low_indices.remove(idx)
            lbl.place_configure(y=orig_y)
        else:
            if len(self.selected_low_indices) >= 2:
                messagebox.showwarning("选择错误", "只能选择两张牌作为前道")
                return
            self.selected_low_indices.append(idx)
            lbl.place_configure(y=orig_y - 50)
            lbl.lift()

    def auto_split(self):
        """使用庄家分牌算法自动分牌"""
        low, high = dealer_way_split(self.game.player_hand)   # 调用庄家分牌逻辑
        # 根据分牌结果更新选中索引列表
        self.selected_low_indices = []
        for i, card in enumerate(self.game.player_hand):
            if card in low:
                self.selected_low_indices.append(i)
        # 更新UI：将选中的两张牌上移50像素
        for i, lbl in enumerate(self.player_card_labels):
            orig_y = lbl.base_y
            if i in self.selected_low_indices:
                lbl.place_configure(y=orig_y - 50)
            else:
                lbl.place_configure(y=orig_y)
        self.status_label.config(text="已按赌场方式分牌，可直接提交或修改\n\n提示:'后道'必须比'前道'强，否则判负！")

    def _format_hand_description(self, low_2, high_5):
        # 前道描述
        low_vals = sorted([rank_2_card_value(c) for c in low_2], reverse=True)
        if low_vals[0] == low_vals[1]:
            low_desc = "对子"
        else:
            low_desc = "高牌"
        
        # 后道描述
        high_name, _, _, _, _ = best_hand_with_joker(high_5)
        high_desc = high_name
        return f"{low_desc} & {high_desc}"

    def submit_split(self):
        if len(self.selected_low_indices) != 2:
            messagebox.showwarning("错误", "请选择两张牌作为前道")
            return
        low = [self.game.player_hand[i] for i in self.selected_low_indices]
        high = [self.game.player_hand[i] for i in range(7) if i not in self.selected_low_indices]

        # ---------- 正确的比较函数 ----------
        def check_valid():
            high_type, high_val, high_cmp, _, _ = best_hand_with_joker(high)
            # 前道评估：有效值相等即为对子
            low_vals = sorted([rank_2_card_value(c) for c in low], reverse=True)
            if low_vals[0] == low_vals[1]:
                low_type = 1                     # 对子等级为1
                low_cmp = [low_vals[0]]          # 比较值即为对子的点数
            else:
                low_type = 0                     # 高牌等级为0
                low_cmp = low_vals               # 降序排列的两张牌值
            if high_val > low_type:
                return True
            if high_val < low_type:
                return False
            for h, l in zip(high_cmp, low_cmp):
                if h > l:
                    return True
                if h < l:
                    return False
            return True

        # 记录玩家分牌是否合法（合法为 True）
        valid_split = check_valid()
        if not valid_split:
            # 分牌无效：仍允许提交，但底注直接判负（后续 showndown 处理）
            self.player_invalid_split = True
            self.status_label.config(text="分牌无效，本局底注直接判负")
        else:
            self.player_invalid_split = False

        self.game.player_low = low
        self.game.player_high = high
        self.game.player_split_done = True
        self.game.stage = "dealer_split"

        # 重新排列为两行
        self.sort_player_hand_after_split()

        for w in self.action_frame.winfo_children():
            w.destroy()

        # 更新玩家标签牌型描述
        desc = self._format_hand_description(low, high)
        self.player_label.config(text=f"玩家 -  {desc}")

        self.status_label.config(text="庄家开牌中...")
        self.reveal_dealer_cards()

    def sort_player_hand_after_split(self):
        """将玩家的牌分为两行：第一行（player_row1）为2张低牌，第二行（player_row2）为5张高牌"""
        low_sorted = sorted(self.game.player_low, key=lambda c: rank_2_card_value(c), reverse=True)
        high_sorted = sort_hand_for_display(self.game.player_high)
        # 合并顺序：先低牌（2张）再高牌（5张），但布局时分为两行
        labels = self.player_card_labels
        card_to_label = {lbl.card: lbl for lbl in labels if lbl.winfo_exists()}
        start_positions = {}
        for lbl in labels:
            info = lbl.place_info()
            start_positions[lbl] = (float(info.get('x', 0)), float(info.get('y', 0)))
        total_width = 7 * self.card_width + 6 * self.card_spacing
        start_x = (700 - total_width) // 2
        if start_x < 0:
            start_x = 20

        # 第一行（2张）y=60，第二行（5张）y=220
        row1_y = 0
        row2_y = 160

        target_positions = {}
        # 低牌放在第一行
        for idx, card in enumerate(low_sorted):
            lbl = card_to_label[card]
            x = start_x + idx * (self.card_width + self.card_spacing)
            y = row1_y
            target_positions[lbl] = (x, y)
        # 高牌放在第二行
        for idx, card in enumerate(high_sorted):
            lbl = card_to_label[card]
            x = start_x + idx * (self.card_width + self.card_spacing)
            y = row2_y
            target_positions[lbl] = (x, y)

        steps = 20
        interval = 25
        anim_data = []
        for lbl, (sx, sy) in start_positions.items():
            tx, ty = target_positions[lbl]
            dx = (tx - sx) / steps
            dy = (ty - sy) / steps
            anim_data.append((lbl, sx, sy, dx, dy))

        def animate_step(step):
            if step > steps:
                for lbl, _, _, _, _ in anim_data:
                    if lbl.winfo_exists():
                        x, y = target_positions[lbl]
                        lbl.place(x=x, y=y, width=self.card_width, height=self.card_height)
                return
            for lbl, sx, sy, dx, dy in anim_data:
                if lbl.winfo_exists():
                    lbl.place(x=sx + dx*step, y=sy + dy*step, width=self.card_width, height=self.card_height)
            self.after(interval, lambda: animate_step(step+1))
        animate_step(1)

    def reveal_dealer_cards(self):
        for label in self.dealer_card_labels:
            if label.winfo_exists() and not label.is_face_up:
                self.flip_card_animation(label)
        self.after(1000, self.dealer_split)

    def dealer_split(self):
        low, high = dealer_way_split(self.game.dealer_hand)
        self.game.dealer_low = low
        self.game.dealer_high = high
        self.sort_dealer_hand_after_split()
        self.stage_label.config(text="比牌")
        self.status_label.config(text="比牌中...")
        self.after(1000, self.showdown)

    def sort_dealer_hand_after_split(self):
        """将庄家的牌分为两行：第一行（dealer_row1）为5张高牌，第二行（dealer_row2）为2张低牌"""
        low_sorted = sorted(self.game.dealer_low, key=lambda c: rank_2_card_value(c), reverse=True)
        high_sorted = sort_hand_for_display(self.game.dealer_high)
        labels = self.dealer_card_labels
        card_to_label = {lbl.card: lbl for lbl in labels if lbl.winfo_exists()}
        start_positions = {}
        for lbl in labels:
            info = lbl.place_info()
            start_positions[lbl] = (float(info.get('x', 0)), float(info.get('y', 0)))
        total_width = 7 * self.card_width + 6 * self.card_spacing
        start_x = (700 - total_width) // 2
        if start_x < 0:
            start_x = 20

        # 第一行（5张高牌）y=60，第二行（2张低牌）y=220
        row1_y = 0
        row2_y = 160

        target_positions = {}
        # 高牌放在第一行
        for idx, card in enumerate(high_sorted):
            lbl = card_to_label[card]
            x = start_x + idx * (self.card_width + self.card_spacing)
            y = row1_y
            target_positions[lbl] = (x, y)
        # 低牌放在第二行
        for idx, card in enumerate(low_sorted):
            lbl = card_to_label[card]
            x = start_x + idx * (self.card_width + self.card_spacing)
            y = row2_y
            target_positions[lbl] = (x, y)

        steps = 20
        interval = 25
        anim_data = []
        for lbl, (sx, sy) in start_positions.items():
            tx, ty = target_positions[lbl]
            dx = (tx - sx) / steps
            dy = (ty - sy) / steps
            anim_data.append((lbl, sx, sy, dx, dy))

        def animate_step(step):
            if step > steps:
                for lbl, _, _, _, _ in anim_data:
                    if lbl.winfo_exists():
                        x, y = target_positions[lbl]
                        lbl.place(x=x, y=y, width=self.card_width, height=self.card_height)
                return
            for lbl, sx, sy, dx, dy in anim_data:
                if lbl.winfo_exists():
                    lbl.place(x=sx + dx*step, y=sy + dy*step, width=self.card_width, height=self.card_height)
            self.after(interval, lambda: animate_step(step+1))
        animate_step(1)

    def showdown(self):
        # 先处理玩家无效分牌的情况（直接底注判负，免佣平局不适用）
        if getattr(self, 'player_invalid_split', False):
            player_win = False
            push = False
            # 但边注仍然正常结算，底注直接输掉（无返还）
            ante = self.game.ante
            insurance = self.game.pai_gow_insurance
            emperor = self.game.emperor_treasure
            johor_bet = self.game.johor_bet
            ace_push_bet = self.game.ace_high_push_bet

            # 底注输：赔付0
            ante_win_amount = 0
        else:
            # 正常分牌，进行比牌
            # 0(平局) ，玩家输
            def normalize_result(r):
                return -1 if r == 0 else r

            result_low = normalize_result(compare_2_hand(self.game.player_low, self.game.dealer_low))
            result_high = normalize_result(compare_5_hand(self.game.player_high, self.game.dealer_high))

            # 规则：
            # 1,1   -> 玩家赢
            # -1,-1 -> 玩家输
            # 1,-1 或 -1,1 -> Push
            if result_low == 1 and result_high == 1:
                player_win = True
                push = False
            elif result_low == -1 and result_high == -1:
                player_win = False
                push = False
            else:
                player_win = False
                push = True

            ante = self.game.ante
            insurance = self.game.pai_gow_insurance
            emperor = self.game.emperor_treasure
            johor_bet = self.game.johor_bet
            ace_push_bet = self.game.ace_high_push_bet

            # ---------- 免佣模式特殊处理 ----------
            commission_free = self.commission_free.get()
            # 判断庄家手牌是否为 A-High（7张牌中最佳5张为高牌且最大值为14）
            dealer_hand = self.game.dealer_hand
            dealer_rank_name, dealer_rank_val, dealer_cmp, _, _ = best_hand_with_joker(dealer_hand)
            is_dealer_ace_high = (dealer_rank_name == "高牌" and dealer_cmp[0] == 14)

            if commission_free and is_dealer_ace_high and not getattr(self, 'player_invalid_split', False):
                # 庄家 A-High，无论结果如何，底注按 Push 结算（无效分牌已经直接输，不进入此分支）
                player_win = False
                push = True

            # 计算底注赔付金额
            if player_win:
                if commission_free:
                    ante_win_amount = ante * 2          # 免佣模式赢时赔率 1:1（净赢1倍）
                else:
                    # 非免佣模式赔率 0.95:1（净赢0.95倍）
                    ante_win_amount = ante + int(ante * 0.95)   # 或 ante * 1.95
            elif push:
                ante_win_amount = ante
            else:
                ante_win_amount = 0

        # ========== 边注结算（无论分牌是否有效都正常计算） ==========
        insurance_win_amount = 0
        if insurance > 0:
            payout_mult = get_pai_gow_insurance_payout(self.game.player_hand)
            if payout_mult > 0:
                insurance_win_amount = insurance * (payout_mult + 1)

        emperor_win_amount = 0
        if emperor > 0:
            emperor_win_amount = emperor_treasure_payout(self.game.player_hand, emperor)

        johor_win_amount = 0
        if johor_bet > 0:
            johor_mult = johor_payout(self.game.player_hand)
            if johor_mult > 0:
                johor_win_amount = johor_bet * (johor_mult + 1)

        ace_push_win_amount = 0
        if ace_push_bet > 0 and self.commission_free.get():
            ace_push_mult = ace_high_push_payout(self.game.player_hand, self.game.dealer_hand)
            if ace_push_mult > 0:
                ace_push_win_amount = ace_push_bet * (ace_push_mult + 1)

        total_win = ante_win_amount + insurance_win_amount + emperor_win_amount + johor_win_amount + ace_push_win_amount
        self.balance += total_win
        self.update_balance()

        # 更新底注UI
        if getattr(self, 'player_invalid_split', False):
            self.ante_display.config(bg='red', text='0')
            self.ante_var.set('0')
            result_text = "分牌无效，底注直接判负"
        else:
            if player_win:
                self.ante_display.config(bg='gold', text=str(int(ante_win_amount)))
                self.ante_var.set(str(int(ante_win_amount)))
                result_text = "本局您赢了"
            elif push:
                self.ante_display.config(bg='light blue', text=str(ante))
                self.ante_var.set(str(ante))
                if self.commission_free.get() and is_dealer_ace_high:
                    result_text = '庄家最大牌型为高牌A，底注平局'
                else:
                    result_text = "本局平局，底注退还"
            else:
                self.ante_display.config(bg='white', text='0')
                self.ante_var.set('0')
                result_text = "下局加油"

        # 牌九保险UI
        if insurance_win_amount > 0:
            self.insurance_display.config(bg='gold', text=str(int(insurance_win_amount)))
            self.insurance_var.set(str(int(insurance_win_amount)))
        else:
            self.insurance_display.config(bg='white', text='0')
            self.insurance_var.set('0')

        # 皇帝之财UI
        if emperor_win_amount > 0:
            self.emperor_display.config(bg='gold', text=str(int(emperor_win_amount)))
            self.emperor_var.set(str(int(emperor_win_amount)))
        else:
            self.emperor_display.config(bg='white', text='0')
            self.emperor_var.set('0')

        # 柔佛州UI
        if johor_win_amount > 0:
            self.johor_display.config(bg='gold', text=str(int(johor_win_amount)))
            self.johor_var.set(str(int(johor_win_amount)))
        else:
            self.johor_display.config(bg='white', text='0')
            self.johor_var.set('0')

        # A高平手UI
        if ace_push_win_amount > 0:
            self.ace_push_display.config(bg='gold', text=str(int(ace_push_win_amount)))
            self.ace_push_var.set(str(int(ace_push_win_amount)))
        else:
            self.ace_push_display.config(bg='white', text='0')
            self.ace_push_var.set('0')

        self.status_label.config(text=result_text)
        self.last_win_label.config(text=f"上局获胜: ${total_win:.2f}")

        # 更新庄家标签牌型描述
        dealer_desc = self._format_hand_description(self.game.dealer_low, self.game.dealer_high)
        self.dealer_label.config(text=f"庄家 -  {dealer_desc}")

        self.show_restart_button()

    def show_card_sequence(self, event):
        """右键显示本局牌序及切牌位置，并取消倒计时"""
        # 取消自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None

        win = tk.Toplevel(self)
        win.title("本局牌序")
        win.geometry("650x600")
        win.resizable(False, False)
        win.configure(bg='#f0f0f0')

        deck = self.game.deck
        cut_pos = deck.cut_position
        card_sequence = deck.full_deck

        tk.Label(win, text=f"本局切牌位置: {cut_pos + 1}", font=('Arial', 14, 'bold'),
                bg='#f0f0f0').pack(pady=(10, 5))

        main_frame = tk.Frame(win, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        canvas = tk.Canvas(main_frame, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)

        content_frame = tk.Frame(canvas, bg='#f0f0f0')
        canvas.create_window((0, 0), window=content_frame, anchor='nw')

        card_frame = tk.Frame(content_frame, bg='#f0f0f0')
        card_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 缩小牌面尺寸用于显示序列
        small_size = (60, 90)
        small_images = {}

        for i, card in enumerate(card_sequence):
            key = (card.suit, card.rank)
            if key in self.original_images:
                orig_img = self.original_images[key]
                small_img = orig_img.resize(small_size, Image.Resampling.LANCZOS)
                small_images[i] = ImageTk.PhotoImage(small_img)
            else:
                back_img = self.original_images.get("back")
                if back_img is not None:
                    small_img = back_img.resize(small_size, Image.Resampling.LANCZOS)
                    small_images[i] = ImageTk.PhotoImage(small_img)

        # 展示7行（每行最多8张）
        for row in range(7):
            row_frame = tk.Frame(card_frame, bg='#f0f0f0')
            row_frame.pack(fill=tk.X, pady=5)

            cards_in_row = 8 if row < 6 else 5
            for col in range(cards_in_row):
                card_index = row * 8 + col
                if card_index >= len(card_sequence):
                    break

                card_container = tk.Frame(row_frame, bg='#f0f0f0')
                card_container.grid(row=0, column=col, padx=5, pady=5)

                bg_color = 'light blue' if card_index == cut_pos else '#f0f0f0'
                if card_index in small_images:
                    card_label = tk.Label(card_container, image=small_images[card_index], bg=bg_color,
                                        borderwidth=1, relief="solid")
                    card_label.image = small_images[card_index]
                    card_label.pack()
                else:
                    card = card_sequence[card_index]
                    tk.Label(card_container, text=f"{card.rank}{card.suit}", bg=bg_color,
                            width=6, height=3, borderwidth=1, relief="solid").pack()

                tk.Label(card_container, text=str(card_index + 1), bg=bg_color,
                        font=('Arial', 9)).pack()

        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    # ------------------------- 按钮/重置 -------------------------
    def show_restart_button(self):
        for w in self.action_frame.winfo_children():
            w.destroy()
        self.stage_label.config(text="结算")
        self.restart_btn = tk.Button(self.action_frame, text="再来一局", command=self.reset_game,
                                     font=('Arial', 14), bg='#2196F3', fg='white', width=15)
        self.restart_btn.pack(pady=5)
        self.restart_btn.bind("<Button-3>", self.show_card_sequence)
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def animate_cards_remove(self, callback):
        """将玩家区和庄家区的所有卡片向右移出屏幕，耗时0.5秒，完成后调用callback"""
        all_labels = []
        if hasattr(self, 'player_card_labels'):
            all_labels.extend(self.player_card_labels)
        if hasattr(self, 'dealer_card_labels'):
            all_labels.extend(self.dealer_card_labels)
        if not all_labels:
            callback()
            return

        steps = 20
        interval = 2  # 20*25 = 500ms
        start_positions = []
        for lbl in all_labels:
            if lbl.winfo_exists():
                info = lbl.place_info()
                x = float(info.get('x', 0))
                y = float(info.get('y', 0))
                start_positions.append((lbl, x, y))

        def animate_step(step):
            if step > steps:
                # 动画结束，销毁所有标签
                for lbl, _, _ in start_positions:
                    if lbl.winfo_exists():
                        lbl.destroy()
                callback()
                return
            # 向右移动，每步增加屏幕宽度/步数
            dx = (self.winfo_width() + 200) / steps
            for lbl, orig_x, orig_y in start_positions:
                if lbl.winfo_exists():
                    new_x = orig_x + dx * step
                    lbl.place(x=new_x, y=orig_y, width=self.card_width, height=self.card_height)
            self.after(interval, lambda: animate_step(step+1))

        animate_step(1)

    def reset_game(self, auto_reset=False):
        """重置游戏，并播放卡片移除动画（如果存在卡片）"""
        if self.removing_cards:
            return  # 动画进行中，避免重复调用
        self.cancel_auto_reset_timer()
        if hasattr(self, 'restart_btn') and self.restart_btn and self.restart_btn.winfo_exists():
            self.restart_btn.config(state=tk.DISABLED)

        # 收集所有当前卡片标签
        all_labels = []
        if hasattr(self, 'player_card_labels'):
            all_labels.extend(self.player_card_labels)
        if hasattr(self, 'dealer_card_labels'):
            all_labels.extend(self.dealer_card_labels)

        # 如果有卡片存在，则播放移除动画，否则直接重置
        if all_labels:
            self.removing_cards = True
            self.animate_cards_remove(lambda: self._do_reset(auto_reset))
        else:
            self._do_reset(auto_reset)

    def _do_reset(self, auto_reset=False):
        """实际执行重置逻辑（动画完成后调用）"""
        self.removing_cards = False
        self._resetting = True

        # 取消所有after定时器
        for after_id in self.tk.eval('after info').split():
            try:
                self.after_cancel(after_id)
            except Exception:
                pass

        self._clear_hand_areas()
        self.game.reset_game()
        self.stage_label.config(text="下注阶段")
        self.status_label.config(text="设置下注金额并开始游戏")
        self.player_label.config(text="玩家")
        self.dealer_label.config(text="庄家")

        # 重置所有下注显示
        self.ante_var.set("0")
        self.insurance_var.set("0")
        self.emperor_var.set("0")
        self.johor_var.set("0")
        self.ace_push_var.set("0")
        self.ante_display.config(bg='white')
        self.insurance_display.config(bg='white')
        self.emperor_display.config(bg='white')
        self.johor_display.config(bg='white')
        self.ace_push_display.config(bg='white')
        self.current_bet_label.config(text="本局下注: $0.00")

        # 重置边注金额变量
        self.johor_bet_amount = 0
        self.ace_high_push_bet_amount = 0
        self.game.johor_bet = 0
        self.game.ace_high_push_bet = 0

        self._resetting = False
        self.selected_low_indices = []

        for widget in self.bet_widgets.values():
            widget.config(bg='white')

        for w in self.action_frame.winfo_children():
            w.destroy()

        start_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_frame.pack(pady=5)

        # 重置金额按钮
        self.reset_bets_button = tk.Button(start_frame, text="重置金额", command=self.reset_bets,
                                           font=('Arial', 14), bg='#F44336', fg='white', width=10)
        self.reset_bets_button.pack(side=tk.LEFT, padx=(10, 10))

        # 重复上局下注按钮（根据是否有历史下注决定启用状态）
        self.repeat_bet_btn = tk.Button(start_frame, text="重复上局下注", command=self.apply_last_bet,
                                        font=('Arial', 14), bg='#4A90E2', fg='white',
                                        activebackground='#3A7BC8', width=12,
                                        state=tk.NORMAL if self.last_bet is not None else tk.DISABLED)
        self.repeat_bet_btn.pack(side=tk.LEFT, padx=(0, 10))

        # 开始游戏按钮
        self.start_button = tk.Button(start_frame, text="开始游戏", command=self.start_game,
                                      font=('Arial', 14), bg='#4CAF50', fg='white', width=10)
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))

        self.betting_enabled = True
        self._update_commission_free_state()
        # 更新A高平手可见性
        self._update_ace_push_visibility()

        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))

    def reset_bets(self):
        self.ante_var.set("0")
        self.insurance_var.set("0")
        self.emperor_var.set("0")
        self.johor_var.set("0")
        self.ace_push_var.set("0")
        self.ante_display.config(bg='white')
        self.insurance_display.config(bg='white')
        self.emperor_display.config(bg='white')
        self.johor_display.config(bg='white')
        self.ace_push_display.config(bg='white')
        self.status_label.config(text="已重置所有下注金额")

    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)

    def start_game(self):
        try:
            ante = int(float(self.ante_var.get()))
            insurance = int(float(self.insurance_var.get()))
            emperor = int(float(self.emperor_var.get()))
            johor = int(float(self.johor_var.get()))
            ace_push = int(float(self.ace_push_var.get()))
        except Exception:
            messagebox.showerror("错误", "请输入有效的下注金额")
            return

        min_ante, max_ante, max_side = 10, 25000, 2500
        if ante < min_ante:
            messagebox.showerror("错误", f"底注至少需要{min_ante}")
            return
        if ante > max_ante:
            ante = max_ante
            self.ante_var.set(str(max_ante))
            messagebox.showwarning("下注限制", f"底注上限为{max_ante}，已自动调整")
        if insurance > max_side:
            insurance = max_side
            self.insurance_var.set(str(max_side))
            messagebox.showwarning("下注限制", f"牌九保险上限为{max_side}，已自动调整")
        if emperor > max_side:
            emperor = max_side
            self.emperor_var.set(str(max_side))
            messagebox.showwarning("下注限制", f"皇帝之财上限为{max_side}，已自动调整")
        if johor > max_side:
            johor = max_side
            self.johor_var.set(str(max_side))
            messagebox.showwarning("下注限制", f"柔佛州上限为{max_side}，已自动调整")
        if ace_push > max_side:
            ace_push = max_side
            self.ace_push_var.set(str(max_side))
            messagebox.showwarning("下注限制", f"A高平手上限为{max_side}，已自动调整")

        # 非免佣模式下禁止A高平手下注
        if not self.commission_free.get() and ace_push > 0:
            messagebox.showerror("错误", "A高平手边注仅在免佣模式下可用")
            return

        total_bet = ante + insurance + emperor + johor + ace_push
        if total_bet > self.balance:
            messagebox.showerror("错误", "余额不足")
            return
        
        # 存储本次下注（供“重复上局下注”使用）
        self.last_bet = {
            'ante': ante,
            'insurance': insurance,
            'emperor': emperor,
            'johor': johor,
            'ace_push': ace_push
        }

        self.balance -= total_bet
        self.update_balance()
        self.betting_enabled = False
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        self.last_win_label.config(text="上局获胜: $0.00")

        self._load_assets()
        self.game.reset_game()
        self._update_commission_free_state()
        self.game.deal_initial()
        self.game.ante = ante
        self.game.pai_gow_insurance = insurance
        self.game.emperor_treasure = emperor
        self.game.johor_bet = johor          # 新增
        self.game.ace_high_push_bet = ace_push  # 新增
        self.game.stage = "dealing"

        self.use_commission_flow = self.commission_free.get()

        self._clear_hand_areas()
        for w in self.action_frame.winfo_children():
            w.destroy()

        self.stage_label.config(text="发牌中")
        self.status_label.config(text="正在发牌...")
        self.animate_deal()

        self._update_commission_free_state() 
        for w in self.bet_widgets.values():
            w.config(bg='white')

    def apply_last_bet(self):
        """将上次存储的下注金额填充到各个输入框，注意免佣模式限制"""
        if self.last_bet is None:
            messagebox.showwarning("提示", "没有可重复的上局下注记录")
            return

        # 底注、保险、皇帝之财、柔佛州始终可以填充
        self.ante_var.set(str(self.last_bet['ante']))
        self.insurance_var.set(str(self.last_bet['insurance']))
        self.emperor_var.set(str(self.last_bet['emperor']))
        self.johor_var.set(str(self.last_bet['johor']))

        # A高平手需要检查当前是否免佣模式
        ace_push_value = self.last_bet['ace_push']
        if self.commission_free.get():
            self.ace_push_var.set(str(ace_push_value))

        self.status_label.config(text="已应用上局下注金额")
        # 刷新显示背景为白色
        self.ante_display.config(bg='white')
        self.insurance_display.config(bg='white')
        self.emperor_display.config(bg='white')
        self.johor_display.config(bg='white')
        self.ace_push_display.config(bg='white')

    def show_game_instructions(self):
        """显示牌九扑克游戏规则 + 庄家分牌规则"""
        win = tk.Toplevel(self)
        win.title("牌九扑克 游戏规则")
        win.geometry("950x820")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')

        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        canvas = tk.Canvas(main_frame, bg='#F0F0F0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)

        content_frame = tk.Frame(canvas, bg='#F0F0F0')
        canvas.create_window((0, 0), window=content_frame, anchor='nw')

        # ================== 游戏规则文本 ==================
        rules_text = """
        牌九扑克 (Pai Gow Poker) 游戏规则

        1. 游戏目标：
        将7张牌分成“前道”（2张）和“后道”（5张），后道牌型必须大于前道。
        与庄家比较两手牌，两手全赢才算赢；一赢一输或平局均为庄家赢。

        2. 下注阶段：
        - 底注：必须下注
        - 牌九保险：可选边注，若玩家7张牌为无对子的高牌，按最大牌赔付
        - 皇帝之财：可选边注，根据7张牌中最佳5张组合赔付

        3. 发牌：
        - 玩家和庄家各得7张牌，牌面朝下。
        - 免佣模式：
            庄家按固定策略自动分牌，然后玩家看牌，并选择2张作为前道，其余5张为后道。
        - 经典模式:
            玩家先看牌，并选择2张作为前道，其余5张为后道，选择结束后，庄家按固定策略自动分牌。

        4. 分牌:
        - 如果不懂，可以直接按下'自动分牌'，推荐的组合是没问题的。
        - 要求是前道2张牌，后道5张牌，按一下扑克代表选择该牌为前道。
        - 前道牌在未提交前是可以再选择的，选择的牌会往上移动。
        - 后道的牌必须强于前道，否则会犯规判负。
        - 例子是A-A-8-8-7-6-5，分为A-8+A-8-7-6-5是可以的，但不推荐。

        5. 比牌：
        - 分别比较前道和后道。前道只比对子或高牌点数；后道按标准扑克牌型（含Joker）。
        - 玩家必须前后两道都大于庄家才获胜，否则庄家获胜（平局庄家赢）。

        6. 赔付规则：
        - 主游戏：赢则底注1:1（例如下注$10，赢$10，共收回$20。
        - 边注按以下赔率表（净赔率，不返还本金）。
        - 免佣模式：
            当庄家最佳五张牌为“高牌A”时，底注平局处理（退还底注）。
        - 经典模式:
            底注在获胜时，收取获胜金额的5%手续费。

        7. 其他：
        - Joker 可作为 A 或补全顺子/同花。
        - 右键点击“再来一局”按钮可查看本局牌序
    """
        rules_label = tk.Label(
            content_frame,
            text=rules_text,
            font=('微软雅黑', 11),
            bg='#F0F0F0',
            justify=tk.LEFT,
            padx=10,
            pady=10
        )
        rules_label.pack(fill=tk.X, padx=10, pady=5)

        # ================== 牌九保险赔率表 ==================
        tk.Label(content_frame, text="牌九保险赔率", font=('微软雅黑', 12, 'bold'),
                bg='#F0F0F0').pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')

        insurance_frame = tk.Frame(content_frame, bg='#F0F0F0')
        insurance_frame.pack(fill=tk.X, padx=20, pady=5)

        insurance_headers = ["最大牌点", "赔率"]
        insurance_data = [
            ("9-High", "100:1"),
            ("10-High", "40:1"),
            ("J-High", "10:1"),
            ("Q-High", "7:1"),
            ("K-High", "6:1"),
            ("A-High", "3:1")
        ]
        for col, h in enumerate(insurance_headers):
            tk.Label(
                insurance_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10,
                pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
        for r, row_data in enumerate(insurance_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    insurance_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10,
                    pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
        for c in range(len(insurance_headers)):
            insurance_frame.columnconfigure(c, weight=1)

        # ================== 皇帝之财赔率表 ==================
        tk.Label(content_frame, text="皇帝之财赔率", font=('微软雅黑', 12, 'bold'),
                bg='#F0F0F0').pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')

        emperor_frame = tk.Frame(content_frame, bg='#F0F0F0')
        emperor_frame.pack(fill=tk.X, padx=20, pady=5)

        emperor_headers = ["牌型", "赔率"]
        emperor_data = [
            ("天然7张同花顺（无Joker）", "5000:1"),
            ("7张同花顺（含Joker）", "1000:1"),
            ("五条A", "500:1"),
            ("皇家同花顺", "150:1"),
            ("同花顺", "50:1"),
            ("四条", "25:1"),
            ("葫芦", "5:1"),
            ("同花", "4:1"),
            ("三条", "3:1"),
            ("顺子", "2:1"),
            ("9-High（高牌）", "40:1"),
            ("10-High（高牌）", "5:1"),
            ("J-High（高牌）", "2:1")
        ]
        for col, h in enumerate(emperor_headers):
            tk.Label(
                emperor_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#2E8B57',
                fg='white',
                padx=10,
                pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
        for r, row_data in enumerate(emperor_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    emperor_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10,
                    pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
        for c in range(len(emperor_headers)):
            emperor_frame.columnconfigure(c, weight=1)

        # ================== 柔佛州赔率表 ==================
        tk.Label(content_frame, text="柔佛州赔率", font=('微软雅黑', 12, 'bold'),
                bg='#F0F0F0').pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')

        johor_frame = tk.Frame(content_frame, bg='#F0F0F0')
        johor_frame.pack(fill=tk.X, padx=20, pady=5)

        johor_headers = ["条件", "赔率"]
        johor_data = [
            ("6张同色 + 1张鬼牌", "30:1"),
            ("7张全同色（无鬼牌）", "10:1"),
            ("含有1张鬼牌", "5:1")
        ]
        for col, h in enumerate(johor_headers):
            tk.Label(
                johor_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#8B4513',
                fg='white',
                padx=10,
                pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
        for r, row_data in enumerate(johor_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    johor_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10,
                    pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
        for c in range(len(johor_headers)):
            johor_frame.columnconfigure(c, weight=1)

        # ================== A高平手赔率表 ==================
        tk.Label(content_frame, text="A高平手赔率（免佣模式）", font=('微软雅黑', 12, 'bold'),
                bg='#F0F0F0').pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')

        acepush_frame = tk.Frame(content_frame, bg='#F0F0F0')
        acepush_frame.pack(fill=tk.X, padx=20, pady=5)

        acepush_headers = ["条件", "赔率"]
        acepush_data = [
            ("玩家和庄家都是Ace高牌", "40:1"),
            ("庄家是有小丑牌的Ace高牌", "15:1"),
            ("庄家是没有小丑牌的Ace高牌", "5:1")
        ]
        for col, h in enumerate(acepush_headers):
            tk.Label(
                acepush_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4169E1',
                fg='white',
                padx=10,
                pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
        for r, row_data in enumerate(acepush_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    acepush_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10,
                    pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
        for c in range(len(acepush_headers)):
            acepush_frame.columnconfigure(c, weight=1)

        # ================== House Way 分牌规则表 ==================
        tk.Label(
            content_frame,
            text="庄家 House Way 分牌规则",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')

        house_frame = tk.Frame(content_frame, bg='#F0F0F0')
        house_frame.pack(fill=tk.X, padx=10, pady=5)

        headers = [
            "牌型",
            "如何处理",
            "原始7张",
            "2+5的排序",
            "含Joker的7张",
            "2+5的组合"
        ]

        data = [
            ["5张A",
            "前道优先放两张自然A。",
            "N/A",
            "N/A",
            "A♠ A♥ A♦ A♣ Joker 3♦ 2♣",
            "前：A♠ A♥\n后：A♦ A♣ Joker(A) 3♦ 2♣"],

            ["皇家同花顺",
            "1.能组成两对按两对处理。\n2.后道皇家同花顺，前道放剩余2张。",
            "10♠ J♠ Q♠ K♠ A♠ 3♦ 2♣",
            "前：3♦ 2♣\n后：10♠ J♠ Q♠ K♠ A♠",
            "10♠ J♠ Q♠ K♠ Joker 3♦ 2♣",
            "前：3♦ 2♣\n后：10♠ J♠ Q♠ K♠ Joker(A)"],

            ["同花顺",
            "1.能组成两对按两对处理。\n2.后道同花顺，前道放剩余2张。",
            "9♠ 8♠ 7♠ 6♠ 5♠ K♦ 2♣",
            "前：K♦ 2♣\n后：9♠ 8♠ 7♠ 6♠ 5♠",
            "9♠ 8♠ 7♠ 6♠ Joker K♦ 2♣",
            "前：K♦ 2♣\n后：9♠ 8♠ 7♠ 6♠ Joker(5♠)"],

            ["四条 A/K/Q",
            "1.剩下3张里有对子，对子放前道。\n2.拆成两对。",
            "A♠ A♥ A♦ A♣ K♠ Q♦ 3♣",
            "前：K♠ Q♦\n后：A♠ A♥ A♦ A♣ 3♣",
            "A♠ A♥ A♦ A♣ Joker K♠ Q♦",
            "前：K♠ Q♦\n后：A♠ A♥ A♦ A♣ Joker(A)"],

            ["四条 J/10/9",
            "1.剩下3张里有对子，对子放前道。\n2.剩下3张里有K/A/Joker，前道放最大两张散牌\n 3.拆成两对。",
            "9♠ 9♥ 9♦ 9♣ K♠ Q♦ 3♣",
            "前：K♠ Q♦\n后：9♠ 9♥ 9♦ 9♣ 3♣",
            "9♠ 9♥ 9♦ 9♣ Joker K♠ Q♦",
            "前：K♠ Q♦\n后：9♠ 9♥ 9♦ 9♣ Joker(A)"],

            ["四条 8/7/6",
            "1.剩下3张里有对子，对子放前道。\n2.剩下3张里有Q/K/A/Joker，前道放最大两张散牌\n 3.拆成两对。",
            "8♠ 8♥ 8♦ 8♣ Q♠ J♦ 3♣",
            "前：Q♠ J♦\n后：8♠ 8♥ 8♦ 8♣ 3♣",
            "8♠ 8♥ 8♦ 8♣ Joker Q♠ J♦",
            "前：Q♠ J♦\n后：8♠ 8♥ 8♦ 8♣ Joker(A)"],

            ["四条 5/4/3/2",
            "1.剩下3张里有对子，对子放前道。\n2.前道放最大两张散牌。",
            "5♠ 5♥ 5♦ 5♣ A♠ K♦ 3♣",
            "前：A♠ K♦\n后：5♠ 5♥ 5♦ 5♣ 3♣",
            "5♠ 5♥ 5♦ 5♣ Joker K♠ Q♦",
            "前：K♠ Q♦\n后：5♠ 5♥ 5♦ 5♣ Joker(A)"],

            ["葫芦 + 对子",
            "最大的对子放前道，后道保留其余5张。",
            "A♠ A♥ A♦ K♣ K♦ Q♠ Q♦",
            "前：K♣ K♦\n后：A♠ A♥ A♦ Q♠ Q♦",
            "A♠ A♥ A♦ K♣ K♦ Joker Q♦",
            "前：K♣ K♦\n后：A♠ A♥ A♦ Joker(A) Q♦"],

            ["两组三条（2个3条）",
            "把较大的三条拆成一对放前道。",
            "Q♠ Q♥ Q♦ 9♣ 9♦ 9♠ 3♦",
            "前：Q♠ Q♥\n后：Q♦ 9♣ 9♦ 9♠ 3♦",
            "Q♠ Q♥ Q♦ 9♣ 9♦ 9♠ Joker",
            "前：Q♠ Q♥\n后：Q♦ 9♣ 9♦ 9♠ Joker(A)"],

            ["葫芦",
            "对子放前道，三条+剩下2张放后道。",
            "Q♠ Q♥ Q♦ A♣ K♣ 7♠ 3♦",
            "前：A♣ K♣\n后：Q♠ Q♥ Q♦ 7♠ 3♦",
            "Q♠ Q♥ Q♦ Joker K♣ 7♠ 3♦",
            "前：Joker(A) K♣\n后：Q♠ Q♥ Q♦ 7♠ 3♦"],

            ["同花（7张同花）",
            "7张都同花时，前道放最大的2张同花，后道保留其余5张同花。",
            "A♠ K♠ Q♠ J♠ 9♠ 6♠ 3♠",
            "前：A♠ K♠\n后：Q♠ J♠ 9♠ 6♠ 3♠",
            "A♠ K♠ Q♠ J♠ 9♠ Joker 3♣",
            "前：3♣ A♠\n后：K♠ Q♠ J♠ 9♠ Joker(6♠)"],

            ["同花（6张同花）",
            "1.能组成对子，前道放对子\n2.前道放同花中最大1张+散牌。",
            "A♠ K♠ Q♠ J♠ 9♠ 6♠ 6♦",
            "前：6♠ 6♦\n后：A♠ K♠ Q♠ J♠ 9♠",
            "A♠ K♠ Q♠ J♠ 9♠ 8♠ 3♦",
            "前：A♠ 3♦\n后：K♠ Q♠ J♠ 9♠ 8♠"],

            ["同花（5张同花）",
            "1.能组成两对按两对处理。\n2.同花后道，剩下2张放前道。",
            "A♠ K♠ Q♠ J♠ 9♠ 6♦ 3♣",
            "前：6♦ 3♣\n后：A♠ K♠ Q♠ J♠ 9♠",
            "A♠ K♠ Q♠ J♠ Joker 6♦ 3♣",
            "前：6♦ 3♣\n后：A♠ K♠ Q♠ J♠ Joker(9♠)"],

            ["顺子（7张顺子）",
            "7张都能组成顺子时，前道放最大的2张，后道保留剩下5张。",
            "A♠ 7♥ 6♦ 5♣ 4♠ 3♦ 2♣",
            "前：A♠ 7♥\n后：6♦ 5♣ 4♠ 3♦ 2♣",
            "9♠ 8♥ 7♦ 6♣ Joker K♦ 2♣",
            "前：K♦ 2♣\n后：9♠ 8♥ 7♦ 6♣ Joker(10♠)"],

            ["顺子（6张顺子）",
            "1.能组成对子，前道放对子\n2.前道放顺子中最大1张+散牌。",
            "6♠ 8♥ 9♦ 10♣ J♠ Q♦ K♣",
            "前：K♣ 6♠\n后：8♥ 9♦ 10♣ J♠ Q♦",
            "A♠ 2♥ 3♦ 4♣ 5♠ 6♦ 6♣",
            "前：6♦ 6♣\n后：A♠ 2♥ 3♦ 4♣ 5♠"],

            ["顺子（5张顺子）",
            "1.能组成两对按两对处理。\n2.顺子后道，剩下2张放前道。",
            "2♠ 3♥ 4♦ 5♣ 6♠ K♦ Q♣",
            "前：K♦ Q♣\n后：2♠ 3♥ 4♦ 5♣ 6♠",
            "2♠ 3♥ 4♦ 5♣ 6♠ 6♦ K♣",
            "前：6♠ 6♦\n后：2♠ 3♥ 4♦ 5♣ 6♠"],

            ["三条 A",
            "前道放1张A+最大散牌，剩下5张放后道。",
            "A♠ A♥ A♦ K♣ Q♦ 7♠ 3♦",
            "前：A♠ K♣\n后：A♥ A♦ Q♦ 7♠ 3♦",
            "A♠ A♥ A♦ Joker K♣ 7♠ 3♦",
            "前：A♠ K♣\n后：A♥ A♦ Joker(A) 7♠ 3♦"],

            ["三条（其他）",
            "前道放最大的2张散牌，后道保留三条。",
            "Q♠ Q♥ Q♦ A♣ K♣ 7♠ 3♦",
            "前：A♣ K♣\n后：Q♠ Q♥ Q♦ 7♠ 3♦",
            "Q♠ Q♥ Q♦ Joker K♣ 7♠ 3♦",
            "前：Joker(A) K♣\n后：Q♠ Q♥ Q♦ 7♠ 3♦"],

            ["三对",
            "最强的一对放前道，剩下两对+散牌放后道。",
            "A♠ A♥ K♣ K♦ 7♠ 7♥ 3♦",
            "前：A♠ A♥\n后：K♣ K♦ 7♠ 7♥ 3♦",
            "K♠ K♥ Q♣ Q♦ 7♠ 7♥ Joker",
            "前：K♠ K♥\n后：Q♣ Q♦ 7♠ 7♥ Joker(A)"],

            ["两对 A/K/Q",
            "前道放较小的对子，后道保留较大的对子+散牌。",
            "A♠ A♥ Q♣ Q♦ 9♠ 6♥ 3♦",
            "前：Q♣ Q♦\n后：A♠ A♥ 9♠ 6♥ 3♦",
            "A♠ A♥ Q♣ Q♦ Joker 9♠ 3♦",
            "前：Q♣ Q♦\n后：A♠ A♥ Joker(A) 9♠ 3♦"],

            ["两对 J/10/9",
            "1.剩下3张里有A/Joker，后道保留两对\n 2.前道放最小对子。",
            "J♠ J♥ 10♣ 10♦ A♠ 8♣ 3♦",
            "前：10♣ 10♦\n后：J♠ J♥ A♠ 8♣ 3♦",
            "J♠ J♥ 10♣ 10♦ Joker 8♣ 3♦",
            "前：10♣ 10♦\n后：J♠ J♥ Joker(A) 8♣ 3♦"],

            ["两对 8/7/6",
            "1.剩下3张里有K/A/Joker，后道保留两对\n 2.前道放最小对子。",
            "8♠ 8♥ 7♣ 7♦ K♠ 5♣ 3♦",
            "前：7♣ 7♦\n后：8♠ 8♥ K♠ 5♣ 3♦",
            "8♠ 8♥ 7♣ 7♦ Joker 5♣ 3♦",
            "前：7♣ 7♦\n后：8♠ 8♥ Joker(A) 5♣ 3♦"],

            ["两对 5/4/3",
            "1.剩下3张里有Q/K/A/Joker，后道保留两对\n 2.前道放最小对子。",
            "5♠ 5♥ 4♣ 4♦ Q♠ 8♣ 2♦",
            "前：4♣ 4♦\n后：5♠ 5♥ Q♠ 8♣ 2♦",
            "5♠ 5♥ 4♣ 4♦ Joker 8♣ 2♦",
            "前：4♣ 4♦\n后：5♠ 5♥ Joker(A) 8♣ 2♦"],

            ["一对",
            "前道放最大的2张散牌，对子和剩下3张放后道。",
            "7♠ 7♥ A♣ K♦ 9♣ 5♦ 2♠",
            "前：A♣ K♦\n后：7♠ 7♥ 9♣ 5♦ 2♠",
            "7♠ 7♥ Joker K♦ 9♣ 5♦ 2♠",
            "前：Joker(A) K♦\n后：7♠ 7♥ 9♣ 5♦ 2♠"],

            ["高牌",
            "前道放第2和第3高散牌，后道保留最大牌+其余4张。",
            "A♠ K♥ Q♦ J♣ 9♠ 6♥ 3♦",
            "前：K♥ Q♦\n后：A♠ J♣ 9♠ 6♥ 3♦",
            "Joker K♥ Q♦ J♣ 9♠ 6♥ 3♦",
            "前：K♥ Q♦\n后：Joker(A) J♣ 9♠ 6♥ 3♦"]
        ]

        for col, header in enumerate(headers):
            tk.Label(
                house_frame,
                text=header,
                font=('微软雅黑', 9, 'bold'),
                bg='#8B4513',
                fg='white',
                wraplength=150,
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        for r, row_data in enumerate(data, start=1):
            bg = '#F0F0F0' if r % 2 else '#E0E0E0'
            for c, value in enumerate(row_data):
                tk.Label(
                    house_frame,
                    text=value,
                    font=('微软雅黑', 8),
                    bg=bg,
                    justify=tk.LEFT,
                    anchor='w',
                    wraplength=180,
                    padx=5,
                    pady=3
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        for c in range(len(headers)):
            house_frame.columnconfigure(c, weight=1)

        # ================== 注释 ==================
        notes = """
    【注】
    • 所有赔率格式均为“赔率:1”，例如下注$1赢得$100，共返还$101（本金+奖金）。
    • 皇帝之财边注使用玩家最好的5张/7张手牌，即使最终手牌发生变化也以初始手牌为准。
    • 牌九保险的赔付仅当玩家最好的5张手牌为高牌时才获胜。
    • Joker 为半万能牌，可替代任何点数/花色以形成皇家同花顺/同花顺/同花/顺子。
    • 如果Joker无法成上述的牌型，就只能当A使用。
    • 玩家按下“自动分牌”时，是使用庄家的分牌方式进行，未必是最好但一定合理。
    • ⚠️玩家"提交分牌"前，需确保'后道'比'前道'强，否则系统会判负！⚠️
    """
        notes_label = tk.Label(
            content_frame,
            text=notes,
            font=('微软雅黑', 10),
            bg='#F0F0F0',
            justify=tk.LEFT,
            padx=10,
            pady=10
        )
        notes_label.pack(fill=tk.X, padx=10, pady=5)

        # ================== GitHub反馈链接 ==================
        feedback_frame = tk.Frame(content_frame, bg='#F0F0F0')
        feedback_frame.pack(fill=tk.X, padx=20, pady=(0, 10), anchor='w')

        tk.Label(
            feedback_frame,
            text="• 如遇上任何问题，",
            font=('微软雅黑', 10),
            bg='#F0F0F0'
        ).pack(side=tk.LEFT)

        link_lbl = tk.Label(
            feedback_frame,
            text="【按我】",
            font=('微软雅黑', 10, 'underline'),
            fg='blue',
            bg='#F0F0F0',
            cursor='hand2'
        )
        link_lbl.pack(side=tk.LEFT)

        link_lbl.bind(
            "<Button-1>",
            lambda e: self._open_github_issue()
        )

        tk.Label(
            feedback_frame,
            text="反馈。",
            font=('微软雅黑', 10),
            bg='#F0F0F0'
        ).pack(side=tk.LEFT)

        # 更新滚动区域
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

        # 关闭按钮
        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)

        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

# ------------------------- 入口 -------------------------
def main(initial_balance=10000, username="Guest"):
    app = PaiGowPokerGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")