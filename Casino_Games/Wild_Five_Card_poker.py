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
import random
import json
import os
import math
import secrets
import subprocess, sys
import time
from itertools import product, combinations
from collections import Counter

# =========================================================
# 基础数据（取自 Wild_Five_Card_Poker）
# =========================================================
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
RANK_VALUES['JOKER'] = 99

HAND_RANK = {
    "五条": 10,
    "同花大顺": 9,
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
HAND_RANK_NAMES = {v: k for k, v in HAND_RANK.items()}

BLIND_PAYOUT = {
    10: 100,   # 五条
    9: 50,     # 同花大顺
    8: 10,     # 同花顺
    7: 5,      # 四条
    6: 3,      # 葫芦
    5: 2,      # 同花
    4: 1,      # 顺子
}

ORIGINAL_FIVE_PAYOUT = {
    10: 1000,  # 五条
    9: 500,    # 同花大顺
    8: 250,    # 同花顺
    7: 100,    # 四条
    6: 50,     # 葫芦
    5: 25,     # 同花
    4: 10,     # 顺子
    3: 5,      # 三条
    2: 5,      # 两对
}

ANTE_PAYOUT = 1
PPAIR_PAYOUTS = [
    ("A-A", 23),
    ("A-K (同花)", 19),
    ("A-Q (同花) 或 A-J (同花)", 16),
    ("A-K", 11),
    ("K-K, Q-Q, 或 J-J", 8),
    ("其中一张为Joker", 6),
    ("A-Q 或 A-J", 4),
    ("其他对子 (10-10 到 2-2)", 2),
]

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
# Progressive 文件加载与保存 (Key: 'Wild_Progressive_2.50')
# =========================================================
def load_wild_jackpot():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
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
        return True, default_jackpot
    return True, default_jackpot

def save_wild_jackpot(jackpot):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
    data = []
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = []
    found = False
    for item in data:
        if item.get('Games') == 'Wild_Progressive_2.50':
            item['jackpot'] = jackpot
            found = True
            break
    if not found:
        data.append({"Games": "Wild_Progressive_2.50", "jackpot": jackpot})
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# =========================================================
# 牌局历史日志（Wild Five Card Poker）
# =========================================================
def wild_five_log_path() -> str:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Wild_Five_Card_Poker.json")

def save_wild_five_history(deck, player_initial_cards, dealer_initial_cards,
                           player_final_cards, dealer_final_cards,
                           public_cards, player_discard=None, dealer_discard=None,
                           result_info=None):
    log_path = wild_five_log_path()
    data = {
        "history_record": {
            "player_win": 0,
            "dealer_win": 0,
            "push": 0,
            "fold": 0,
            "game": 0
        },
        "history": []
    }

    # 读取已有数据
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
            print(f"读取历史文件出错: {e}")

    # 生成 game_id
    max_id = 0
    for rec in data["history"]:
        if "game_id" in rec and isinstance(rec["game_id"], int):
            if rec["game_id"] > max_id:
                max_id = rec["game_id"]
    new_game_id = max_id + 1

    stats = data["history_record"]
    stats["game"] += 1

    # 处理胜者统计（修正 fold 判断）
    winner = None
    if result_info:
        if "winner" in result_info:
            winner = result_info["winner"]
            if winner == "player":
                stats["player_win"] += 1
            elif winner == "dealer":
                stats["dealer_win"] += 1
            elif winner == "fold":
                stats["fold"] += 1
            elif winner == "push":
                stats["push"] += 1
        # 兼容旧版 fold 字段（如果有）
        elif result_info.get("fold", False):
            winner = "fold"
            stats["fold"] += 1

    # 构建记录，增加四个新字段
    record = {
        "game_id": new_game_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "deck_order": [str(c) for c in deck.full_deck],
        "cut_position": deck.cut_position,
        # 原始手牌
        "player_cards_ori": [str(c) for c in player_initial_cards],
        "dealer_cards_ori": [str(c) for c in dealer_initial_cards],
        # 最终最佳牌型（5张）
        "player_cards_aft": [str(c) for c in player_final_cards] if player_final_cards else [],
        "dealer_cards_aft": [str(c) for c in dealer_final_cards] if dealer_final_cards else [],
        # 公共牌及弃牌信息
        "public_cards": [str(c) for c in public_cards],
        "player_discard": str(player_discard) if player_discard else None,
        "dealer_discard": str(dealer_discard) if dealer_discard else None,
        "result": result_info if result_info else {}
    }
    if winner is not None:
        record["result"]["winner"] = winner

    data["history"].append(record)

    # 保留最近50局
    if len(data["history"]) > 50:
        data["history"] = data["history"][-50:]

    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# =========================================================
# 卡牌（支持 JOKER）
# =========================================================
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

def card_copy(card):
    new_card = Card(card.suit, card.rank)
    for attr in ('source', 'deal_index', 'is_public', 'is_discard'):
        if hasattr(card, attr):
            setattr(new_card, attr, getattr(card, attr))
    return new_card

# =========================================================
# 牌堆（带 JOKER）
# =========================================================
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

# =========================================================
# 手牌评估（Wild Five Card Poker）
# =========================================================
def _rank_counts(cards):
    values = [c.value for c in cards]
    return Counter(values)

def evaluate_fixed_hand(cards):
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    is_flush = len(set(suits)) == 1

    uniq = sorted(set(values))
    is_straight = False
    straight_high = 0
    if len(uniq) == 5:
        if uniq[-1] - uniq[0] == 4:
            is_straight = True
            straight_high = uniq[-1]
        elif uniq == [2, 3, 4, 5, 14]:
            is_straight = True
            straight_high = 5

    freq = Counter(values)
    by_cnt = sorted(freq.items(), key=lambda x: (x[1], x[0]), reverse=True)
    counts = sorted(freq.values(), reverse=True)

    if is_flush and is_straight:
        if set(values) == {10, 11, 12, 13, 14}:
            return "同花大顺", HAND_RANK["同花大顺"], [14]
        return "同花顺", HAND_RANK["同花顺"], [straight_high]

    if counts[0] == 5:
        return "五条", HAND_RANK["五条"], [by_cnt[0][0]]
    if counts[0] == 4:
        four = by_cnt[0][0]
        kicker = max(v for v in values if v != four)
        return "四条", HAND_RANK["四条"], [four, kicker]
    if counts[0] == 3 and counts[1] == 2:
        trips = by_cnt[0][0]
        pair = by_cnt[1][0]
        return "葫芦", HAND_RANK["葫芦"], [trips, pair]
    if is_flush:
        return "同花", HAND_RANK["同花"], values
    if is_straight:
        return "顺子", HAND_RANK["顺子"], [straight_high]
    if counts[0] == 3:
        trips = by_cnt[0][0]
        kickers = sorted([v for v in values if v != trips], reverse=True)
        return "三条", HAND_RANK["三条"], [trips] + kickers
    if counts[0] == 2 and counts[1] == 2:
        pair_vals = sorted([v for v, cnt in freq.items() if cnt == 2], reverse=True)
        kicker = max(v for v, cnt in freq.items() if cnt == 1)
        return "两对", HAND_RANK["两对"], pair_vals + [kicker]
    if counts[0] == 2:
        pair = by_cnt[0][0]
        kickers = sorted([v for v in values if v != pair], reverse=True)
        return "对子", HAND_RANK["对子"], [pair] + kickers
    return "高牌", HAND_RANK["高牌"], values

def best_hand_with_joker(cards):
    joker_indices = [i for i, c in enumerate(cards) if c.is_joker]
    if not joker_indices:
        rank_name, rank_val, cmp_vals = evaluate_fixed_hand(cards)
        return rank_name, rank_val, cmp_vals, [card_copy(c) for c in cards], [c.value for c in cards]

    possible_values = list(range(2, 15))
    possible_suits = SUITS
    best = None

    for values_combo in product(possible_values, repeat=len(joker_indices)):
        for suits_combo in product(possible_suits, repeat=len(joker_indices)):
            trial = [card_copy(c) for c in cards]
            for idx_pos, card_idx in enumerate(joker_indices):
                trial[card_idx] = Card(suits_combo[idx_pos], RANKS[values_combo[idx_pos] - 2])
            rank_name, rank_val, cmp_vals = evaluate_fixed_hand(trial)
            key = (rank_val, cmp_vals)
            if best is None or key > best[0]:
                best = (key, rank_name, rank_val, cmp_vals, trial, [c.value for c in trial])

    _, rank_name, rank_val, cmp_vals, trial, eff_vals = best

    for idx_pos, card_idx in enumerate(joker_indices):
        trial[card_idx] = cards[card_idx]

    return rank_name, rank_val, cmp_vals, trial, eff_vals

def compare_hands_best(cards1, cards2):
    h1 = best_hand_from_cards(cards1)
    h2 = best_hand_from_cards(cards2)
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

def best_hand_from_cards(cards):
    if len(cards) == 5:
        rank_name, rank_val, cmp_vals, eff_cards, eff_vals = best_hand_with_joker(cards)
        return rank_name, rank_val, cmp_vals, eff_cards, tuple(range(5)), [getattr(c, 'source', '') == 'public' for c in eff_cards], eff_vals

    best = None
    for idxs in combinations(range(len(cards)), 5):
        subset = [cards[i] for i in idxs]
        rank_name, rank_val, cmp_vals, eff_cards, eff_vals = best_hand_with_joker(subset)
        key = (rank_val, cmp_vals)
        if best is None or key > best[0]:
            used_public = [getattr(c, 'source', '') == 'public' for c in subset]
            best = (key, rank_name, rank_val, cmp_vals, eff_cards, idxs, used_public, eff_vals)
    _, rank_name, rank_val, cmp_vals, eff_cards, idxs, used_public, eff_vals = best
    return rank_name, rank_val, cmp_vals, eff_cards, idxs, used_public, eff_vals

def sort_hand_for_display(hand):
    rank_name, rank_val, cmp_vals, best_cards, eff_vals = best_hand_with_joker(hand)

    cards_with_eff = []
    for i, card in enumerate(hand):
        eff = eff_vals[i]
        cards_with_eff.append((card, eff))

    if rank_val in [9, 8, 4]:
        values = [x[1] for x in cards_with_eff]
        if set(values) == {14, 2, 3, 4, 5}:
            cards_with_eff.sort(key=lambda x: 1 if x[1] == 14 else x[1])
        else:
            cards_with_eff.sort(key=lambda x: x[1])
        return [x[0] for x in cards_with_eff]

    counter = Counter([x[1] for x in cards_with_eff])
    cards_with_eff.sort(key=lambda x: (counter[x[1]], x[1]), reverse=True)
    return [x[0] for x in cards_with_eff]

def classify_hand_for_display(cards):
    return best_hand_with_joker(cards)[0]

def get_public_pair_payout(public_cards):
    if len(public_cards) != 2:
        return 0
    c1, c2 = public_cards
    r1, r2 = c1.rank, c2.rank
    s1, s2 = c1.suit, c2.suit

    if c1.is_joker or c2.is_joker:
        return 6
    if r1 == r2:
        if r1 == 'A':
            return 23
        if r1 in ('K', 'Q', 'J'):
            return 8
        if r1 in ('10', '9', '8', '7', '6', '5', '4', '3', '2'):
            return 2
        return 0

    suited = (s1 == s2)
    ranks = {r1, r2}
    if ranks == {'A', 'K'} and suited:
        return 19
    if ranks in ({'A', 'Q'}, {'A', 'J'}) and suited:
        return 16
    if ranks == {'A', 'K'} and not suited:
        return 11
    if ranks in ({'A', 'Q'}, {'A', 'J'}) and not suited:
        return 4
    return 0

def is_four_card_flush(cards):
    suits = [c.suit for c in cards if not c.is_joker]
    if not suits:
        return False
    suit_counts = Counter(suits)
    max_suit_cnt = max(suit_counts.values())
    joker_count = sum(1 for c in cards if c.is_joker)
    if max_suit_cnt + joker_count >= 4:
        return True
    return False

def is_outside_straight_draw(cards):
    values = [c.value for c in cards if not c.is_joker]
    joker_cnt = sum(1 for c in cards if c.is_joker)
    if joker_cnt > 0:
        for v in range(2, 15):
            all_vals = sorted(values + [v])
            uniq_vals = sorted(set(all_vals))
            for i in range(len(uniq_vals) - 3):
                if uniq_vals[i+3] - uniq_vals[i] == 3:
                    return True
        return False
    else:
        values = sorted(set(values))
        if len(values) < 4:
            return False
        for i in range(len(values) - 3):
            if values[i+3] - values[i] == 3:
                return True
        return False

def dealer_discard_card(cards):
    """
    庄家自动弃牌决策（优化版）
    逻辑顺序：
    1. 若已是顺子、同花、葫芦、同花顺、同花大顺、五条 → 不弃
    2. 若有四张同花（含Joker） → 弃异花色最小牌
    3. 若有“outside straight”（四张连续且两端可补牌，例如2-3-4-5或10-J-Q-K） → 弃掉不在四连张中的第五张牌
    4. 若已有对子、两对、三条、四条 → 弃最小单张
    5. 默认 → 弃最小非Joker牌
    """
    # 1. 已为强牌，不弃
    rank_name = best_hand_from_cards(cards)[0]
    made_hands = {"顺子", "同花", "葫芦", "同花顺", "同花大顺", "五条"}
    if rank_name in made_hands:
        return None

    # 2. 四张同花（含Joker）→ 弃异花色
    if is_four_card_flush(cards):
        real_suits = [c.suit for c in cards if not c.is_joker]
        if real_suits:
            keep_suit = Counter(real_suits).most_common(1)[0][0]
        else:
            keep_suit = None
        candidates = [c for c in cards if not c.is_joker and c.suit != keep_suit]
        if candidates:
            return min(candidates, key=lambda c: c.value)
        non_jokers = [c for c in cards if not c.is_joker]
        if non_jokers:
            return min(non_jokers, key=lambda c: c.value)
        return None

    # 3. outside straight（四张连续，且非A-2-3-4或J-Q-K-A，因为A=14天然排除）
    # 获取所有非Joker牌的点数（去重）
    values = [c.value for c in cards if not c.is_joker]
    unique_vals = sorted(set(values))
    four_straight_vals = None
    for i in range(len(unique_vals) - 3):
        if unique_vals[i + 3] - unique_vals[i] == 3:
            four_straight_vals = set(unique_vals[i:i + 4])
            break
    if four_straight_vals:
        # 弃掉不在这四张连续牌中的非Joker牌
        discard_candidates = [c for c in cards if not c.is_joker and c.value not in four_straight_vals]
        if discard_candidates:
            return min(discard_candidates, key=lambda c: c.value)
        # 如果无多余非Joker（即所有非Joker都在四连中），则不可能，因为手牌只有5张

    # 4. 已有对子/两对/三条/四条 → 弃最小单张
    freq = Counter(c.value for c in cards if not c.is_joker)
    counts = sorted(freq.values(), reverse=True)
    if counts and ((counts[0] == 2 and counts.count(2) >= 2) or counts[0] in (3, 4)) and len([v for v in counts if v == 1]) >= 1:
        singles = [c for c in cards if freq.get(c.value, 0) == 1 and not c.is_joker]
        if singles:
            return min(singles, key=lambda c: c.value)
        return min(cards, key=lambda c: c.value if not c.is_joker else 100)

    # 5. 默认：弃最小非Joker牌
    singles = [c for c in cards if freq.get(c.value, 0) == 1 and not c.is_joker]
    if singles:
        return min(singles, key=lambda c: c.value)
    return min(cards, key=lambda c: c.value if not c.is_joker else 100)

# =========================================================
# 游戏逻辑类（Wild Five Card Poker）
# =========================================================
class WildFivePokerGame:
    def __init__(self):
        self.reset_game()
        self.progressive_amount = load_wild_jackpot()[1]
        self.min_progressive = 271288.59

    def reset_game(self):
        self.deck = Deck()
        self.player_hand = []
        self.dealer_hand = []
        self.public_cards = []
        self.player_initial_hand = []
        self.ante = 0
        self.blind = 0
        self.original_five_bet = 0
        self.public_pair_bet = 0
        self.play_bet = 0
        self.jackpot_bet = 0  # 是否参与累进大奖
        self.stage = "pre_flop"
        self.folded = False
        self.player_discard = None
        self.dealer_discard = None

    def deal_initial(self):
        self.public_cards = self.deck.deal(2)
        self.player_hand = self.deck.deal(5)
        self.dealer_hand = self.deck.deal(5)
        self.player_initial_hand = [card_copy(c) for c in self.player_hand]
        self.dealer_initial_hand = [card_copy(c) for c in self.dealer_hand]

# =========================================================
# 主 GUI（基于 DJ_Wild 的 UI，融入 Wild Five Card Poker）
# =========================================================
ROOT_BG = "#1B3D31"
PANEL_BG = "#F2E6C9"
HEADER_BG = "#D8B46A"
TITLE_FG = "#2A1B08"
GOLD = "#D4AF37"

class WildFivePokerUI(tk.Frame):
    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG)
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.configure(bg=ROOT_BG)

        self.username = username
        self.balance = initial_balance
        self.game = WildFivePokerGame()
        self.card_images = {}
        self._temp_flip_images = {} 
        self.original_images = {}
        self.animation_queue = []
        self.animation_in_progress = False
        self.card_positions = {}
        self.active_card_labels = []
        self.selected_chip = None
        self.chip_buttons = []
        self.chip_texts = {}
        self.last_win = 0
        self.last_bet = None
        self.repeat_bet_btn = None
        self.auto_reset_timer = None
        self.buttons_disabled = False
        self.win_details = {
            "ante": 0,
            "blind": 0,
            "play": 0,
            "original_five": 0,
            "public_pair": 0
        }
        self.bet_widgets = {}
        self.game_in_progress = False

        self.high_bet_mode = False
        self._load_assets()
        self._create_widgets()

        self.ante_var.trace_add('write', self.on_ante_changed)

        self.player_selected_label = None

    def on_close(self):
        timer = getattr(self, "auto_reset_timer", None)
        if timer:
            try:
                self.after_cancel(timer)
            except tk.TclError:
                pass
        try:
            update_balance_in_json(self.username, self.balance)
        except Exception:
            pass
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))
        if callable(self.on_back):
            self.on_back(float(self.balance))


    # ---------- 加载扑克牌（交替 Poker1/Poker2） ----------
    def _load_assets(self):
        card_size = (100, 140)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not hasattr(self, 'current_poker_folder'):
            self.current_poker_folder = random.choice(['Poker1', 'Poker2'])
        else:
            self.current_poker_folder = 'Poker2' if self.current_poker_folder == 'Poker1' else 'Poker1'
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', self.current_poker_folder)
        suit_mapping = {'♠':'Spade','♥':'Heart','♦':'Diamond','♣':'Club', 'JOKER':'JOKER'}
        self.original_images = {}
        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_img_orig = Image.open(back_path)
            self.original_images["back"] = back_img_orig
            back_img = back_img_orig.resize(card_size)
            self.back_image = ImageTk.PhotoImage(back_img)
        except:
            img_orig = Image.new('RGB', card_size, 'black')
            self.original_images["back"] = img_orig
            self.back_image = ImageTk.PhotoImage(img_orig)
        for suit in SUITS + ['JOKER']:
            for rank in RANKS:
                if suit == 'JOKER':
                    filename = "JOKER-A.png"
                else:
                    suit_name = suit_mapping.get(suit, suit)
                    filename = f"{suit_name}{rank}.png"
                path = os.path.join(card_dir, filename)
                try:
                    if os.path.exists(path):
                        img = Image.open(path)
                        self.original_images[(suit, rank)] = img
                        img_resized = img.resize(card_size)
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_resized)
                    else:
                        img_orig = Image.new('RGB', card_size, 'blue')
                        draw = ImageDraw.Draw(img_orig)
                        try:
                            font = ImageFont.truetype("arial.ttf", 20)
                        except:
                            font = ImageFont.load_default()
                        text = f"{rank}{suit}" if suit != 'JOKER' else "JOKER"
                        tw, th = draw.textsize(text, font=font)
                        draw.text(((card_size[0]-tw)//2, (card_size[1]-th)//2), text, fill="white", font=font)
                        self.original_images[(suit, rank)] = img_orig
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
                except:
                    img_orig = Image.new('RGB', card_size, 'red')
                    draw = ImageDraw.Draw(img_orig)
                    try:
                        font = ImageFont.truetype("arial.ttf", 20)
                    except:
                        font = ImageFont.load_default()
                    draw.text((10,10), "Error", fill="white", font=font)
                    self.original_images[(suit, rank)] = img_orig
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)

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

    # ---------- 筹码选择 ----------
    def select_chip(self, chip_text):
        self.selected_chip = chip_text
        for chip in self.chip_buttons:
            chip.delete("highlight")
            for item_id in chip.find_all():
                if chip.type(item_id) == 'oval':
                    x1,y1,x2,y2 = chip.coords(item_id)
                    chip.create_oval(x1,y1,x2,y2, outline='black', width=2)
                    break
        for chip in self.chip_buttons:
            text_id = None
            oval_id = None
            for item_id in chip.find_all():
                t = chip.type(item_id)
                if t == 'text':
                    text_id = item_id
                elif t == 'oval':
                    oval_id = item_id
            if text_id and chip.itemcget(text_id, 'text') == chip_text:
                x1,y1,x2,y2 = chip.coords(oval_id)
                chip.create_oval(x1,y1,x2,y2, outline='#2f00ff', width=3, tags="highlight")
                break

    # ---------- 添加筹码到下注区域 ----------
    def add_chip_to_bet(self, bet_type):
        if not self.selected_chip:
            return
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K','')) * 1000
        else:
            chip_value = float(chip_text)

        limits = {
            "ante": (50000 if self.high_bet_mode else 10000),
            "original_five": (12500 if self.high_bet_mode else 2500),
            "public_pair": (12500 if self.high_bet_mode else 2500)
        }
        if bet_type in limits:
            current = float(self.__getattribute__(f"{bet_type}_var").get())
            limit = limits[bet_type]
            if current >= limit:
                names = {"ante":"底注","original_five":"原始五","public_pair":"公共对子"}
                messagebox.showwarning("下注限制", f"{names[bet_type]}已满，不能再下注！")
                return
            new_amount = current + chip_value
            if new_amount > limit:
                new_amount = limit
                if current > 0:
                    names = {"ante":"底注","original_five":"原始五","public_pair":"公共对子"}
                    messagebox.showwarning("下注限制", f"{names[bet_type]}已达上限，自动调整为 {int(new_amount)}")
            self.__getattribute__(f"{bet_type}_var").set(str(int(new_amount)))

    # ---------- 重置单个下注（右键） ----------
    def reset_single_bet(self, bet_type, event):
        if bet_type == "ante":
            self.ante_var.set("0")
        elif bet_type == "original_five":
            self.original_five_var.set("0")
        elif bet_type == "public_pair":
            self.public_pair_var.set("0")
        if bet_type in self.bet_widgets:
            widget = self.bet_widgets[bet_type]
            original_bg = widget.cget('bg')
            widget.config(bg='#FFCDD2')
            self.after(500, lambda: widget.config(bg=original_bg))

    def clear_btn_frame(self):
        for widget in self.btn_frame.winfo_children():
            widget.destroy()

    def add_main_buttons(self):
        self.clear_btn_frame()
        self.reset_bets_button = tk.Button(
            self.btn_frame, text="重设金额", command=self.reset_bets,
            font=('Arial',12,'bold'), bg='#F44336', fg='white',
            relief=tk.RAISED, bd=2, cursor="hand2", width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=5)

        self.repeat_bet_btn = tk.Button(
            self.btn_frame, text="重复上局下注", command=self.apply_last_bet,
            font=('Arial',12,'bold'), bg='#FFC107', fg='black',
            relief=tk.RAISED, bd=2, cursor="hand2", width=12,
            state=tk.NORMAL if self.last_bet is not None else tk.DISABLED
        )
        self.repeat_bet_btn.pack(side=tk.LEFT, padx=5)

        self.start_button = tk.Button(
            self.btn_frame, text="开始游戏", command=self.start_game,
            font=('Arial',12,'bold'), bg='#4CAF50', fg='white',
            relief=tk.RAISED, bd=2, cursor="hand2", width=10
        )
        self.start_button.pack(side=tk.LEFT, padx=5)

    # ---------- 创建主界面 ----------
    def _create_widgets(self):
        main_frame = tk.Frame(self, bg=ROOT_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        table_canvas = tk.Canvas(main_frame, bg=ROOT_BG, highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        table_canvas.create_rectangle(0,0,725,720, fill=ROOT_BG, outline=GOLD, width=5)

        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=10, y=20, width=700, height=220)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial',18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        public_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        public_frame.place(x=10, y=250, width=250, height=220)
        self.public_label = tk.Label(public_frame, text="公共牌", font=('Arial',18), bg='#2a4a3c', fg='white')
        self.public_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.public_cards_frame = tk.Frame(public_frame, bg='#2a4a3c')
        self.public_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.ante_info_label = tk.Label(
            table_canvas,
            text='鬼牌为万能牌\n选择弃一张牌后加注\n庄家高牌时底注平局',
            font=('Arial', 18),
            bg=ROOT_BG,
            fg='#FFD700',
            justify='left'
        )
        self.ante_info_label.place(x=380, y=250, anchor='n')

        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=10, y=480, width=700, height=220)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial',18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # ========== 重新设计的弃牌区（带背景框，更醒目） ==========
        def create_discard_zone(x, y, title):
            """创建一个弃牌区框架，并返回框架对象"""
            frame = tk.Frame(
                self,
                bg='#3a1a1a',               # 深红色背景
                bd=3,
                relief=tk.GROOVE,
                highlightbackground='#ff6666',
                highlightcolor='#ff6666',
                highlightthickness=2
            )
            frame.place(x=x, y=y, width=150, height=220)

            # 标题文字
            title_label = tk.Label(
                frame,
                text=title,
                font=('Arial', 14, 'bold'),
                bg='#3a1a1a',
                fg='#ff9999'
            )
            title_label.pack(pady=(10, 2))

            # 额外装饰线（可选）
            sep = tk.Frame(frame, height=2, bg='#ff6666')
            sep.pack(fill=tk.X, padx=10, pady=5)

            return frame

        # 庄家弃牌区（位置对应庄家弃牌动画目标 y≈85）
        self.discard_zone_dealer = create_discard_zone(570, 30, "庄家弃牌")
        # 玩家弃牌区（位置对应玩家弃牌动画目标 y≈545）
        self.discard_zone_player = create_discard_zone(570, 490, "玩家弃牌")

        right_panel = tk.Frame(main_frame, bg=ROOT_BG, width=400)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        right_panel.pack_propagate(False)

        info_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        info_card.pack(fill=tk.X, pady=3)
        header_info = tk.Frame(info_card, bg=HEADER_BG)
        header_info.pack(fill=tk.X)
        body_info = tk.Frame(info_card, bg=PANEL_BG)
        body_info.pack(fill=tk.X, padx=10, pady=8)

        self.balance_label = tk.Label(body_info, text=f"余额: ${self.balance:,.2f}", font=('Arial',16,'bold'),
                                      bg=PANEL_BG, fg='black')
        self.balance_label.pack(side=tk.LEFT)
        self.stage_label = tk.Label(body_info, text="翻牌前", font=('Arial',16,'bold'),
                                    bg=PANEL_BG, fg='#A88100')
        self.stage_label.pack(side=tk.RIGHT)

        # ========== Progressive 累进大奖卡片 ==========
        progressive_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        progressive_card.pack(fill=tk.X, pady=3)
        header_prog = tk.Frame(progressive_card, bg=HEADER_BG)
        header_prog.pack(fill=tk.X)
        tk.Label(header_prog, text="累进大奖", font=('Arial',13,'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_prog = tk.Frame(progressive_card, bg=PANEL_BG)
        body_prog.pack(fill=tk.X, padx=10, pady=8)
        self.progressive_amount_var = tk.StringVar()
        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")
        self.progressive_display = tk.Label(body_prog, textvariable=self.progressive_amount_var,
                                            font=('Arial',20,'bold'), bg=PANEL_BG, fg='#A88100')
        self.progressive_display.pack(anchor='center')

        # 限红信息卡片（可点击切换高额模式）
        limit_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        limit_card.pack(fill=tk.X, pady=3)
        header_limit = tk.Frame(limit_card, bg=HEADER_BG)
        header_limit.pack(fill=tk.X)
        tk.Label(header_limit, text="下注上限", font=('Arial',13,'bold'),
                 bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_limit = tk.Frame(limit_card, bg=PANEL_BG)
        body_limit.pack(fill=tk.X, padx=10, pady=8)

        table_frame = tk.Frame(body_limit, bg=PANEL_BG, bd=2, relief=tk.SOLID)
        table_frame.pack(fill=tk.X)
        titles = ["底注最低","底注最高","边注最高"]
        for col,title in enumerate(titles):
            lbl = tk.Label(table_frame, text=title, font=('Arial',11,'bold'),
                           bg=PANEL_BG, fg='#2A1B08', borderwidth=1, relief=tk.SOLID, padx=5, pady=5)
            lbl.grid(row=0, column=col, sticky="nsew", padx=0, pady=0)
        self.min_ante_label = tk.Label(table_frame, text="$10", font=('Arial',12,'bold'),
                                       bg=PANEL_BG, fg="#A88100", borderwidth=1, relief=tk.SOLID, padx=5, pady=5)
        self.min_ante_label.grid(row=1, column=0, sticky="nsew")
        self.max_ante_label = tk.Label(table_frame, text="$10,000", font=('Arial',12,'bold'),
                                       bg=PANEL_BG, fg="#A88100", borderwidth=1, relief=tk.SOLID, padx=5, pady=5)
        self.max_ante_label.grid(row=1, column=1, sticky="nsew")
        self.max_side_label = tk.Label(table_frame, text="$2,500", font=('Arial',12,'bold'),
                                       bg=PANEL_BG, fg="#A88100", borderwidth=1, relief=tk.SOLID, padx=5, pady=5)
        self.max_side_label.grid(row=1, column=2, sticky="nsew")
        for col in range(3):
            table_frame.columnconfigure(col, weight=1)
        for w in [limit_card, header_limit, body_limit, table_frame,
                  self.min_ante_label, self.max_ante_label, self.max_side_label]:
            w.bind("<Button-1>", self.toggle_high_bet_limits)

        combined_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        combined_card.pack(fill=tk.X, pady=3)
        header_combined = tk.Frame(combined_card, bg=HEADER_BG)
        header_combined.pack(fill=tk.X)
        tk.Label(header_combined, text="筹码与下注", font=('Arial',13,'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_combined = tk.Frame(combined_card, bg=PANEL_BG)
        body_combined.pack(fill=tk.X, padx=10, pady=8)
        body_combined.columnconfigure(0, weight=1)
        body_combined.columnconfigure(1, weight=1)
        body_combined.columnconfigure(2, weight=1)

        # 筹码按钮行
        chip_row = tk.Frame(body_combined, bg=PANEL_BG)
        chip_row.grid(row=0, column=0, columnspan=3, pady=(0,8), sticky='ew')
        for i in range(6):
            chip_row.columnconfigure(i, weight=1)
        self.chip_container = chip_row

        chip_configs = [
            ('$10','#ffa500','black'),
            ("$25",'#00ff00','black'),
            ("$100",'#000000','white'),
            ("$500","#FF7DDA",'black'),
            ("$1K",'#ffffff','black'),
            ("$2.5K",'#ff0000','white'),
        ]
        self.chip_buttons = []
        self.chip_texts = {}
        for i,(text,bg_color,fg_color) in enumerate(chip_configs):
            cell = tk.Frame(chip_row, bg=PANEL_BG)
            cell.grid(row=0, column=i, padx=2, pady=2, sticky='nsew')
            chip_canvas = tk.Canvas(cell, width=50, height=50, bg=PANEL_BG, highlightthickness=0)
            chip_canvas.pack(anchor='center')
            chip_canvas.create_oval(2,2,49,49, fill=bg_color, outline='black')
            chip_canvas.create_text(25.5,25.5, text=text, fill=fg_color, font=('Arial',12,'bold'))
            chip_canvas.bind("<Button-1>", lambda e,t=text: self.select_chip(t))
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text
        self.select_chip("$10")

        # 累进大奖复选框（放在第一行）
        self.jackpot_bet_var = tk.IntVar(value=0)
        row0 = tk.Frame(body_combined, bg=PANEL_BG)
        row0.grid(row=1, column=0, columnspan=3, sticky='ew', padx=40, pady=2)
        self.jackpot_check = tk.Checkbutton(
            row0, text="累进大奖 ($2.50)", variable=self.jackpot_bet_var,
            font=('Arial',12,"bold"), bg=PANEL_BG, fg='black', selectcolor=PANEL_BG
        )
        self.jackpot_check.pack(side=tk.LEFT)

        # 原始五和公共对子行
        row1 = tk.Frame(body_combined, bg=PANEL_BG)
        row1.grid(row=2, column=0, columnspan=3, sticky='ew', pady=4)
        tk.Label(row1, text="      原始五:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT)
        self.original_five_var = tk.StringVar(value="0")
        self.original_five_display = tk.Label(row1, textvariable=self.original_five_var, font=('Arial',12),
                                              bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.original_five_display.pack(side=tk.LEFT, padx=5)
        self.original_five_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("original_five"))
        self.original_five_display.bind("<Button-3>", lambda e: self.reset_single_bet("original_five", e))
        self.bet_widgets["original_five"] = self.original_five_display

        tk.Label(row1, text="公共对子:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=(20,5))
        self.public_pair_var = tk.StringVar(value="0")
        self.public_pair_display = tk.Label(row1, textvariable=self.public_pair_var, font=('Arial',12),
                                            bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.public_pair_display.pack(side=tk.LEFT, padx=5)
        self.public_pair_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("public_pair"))
        self.public_pair_display.bind("<Button-3>", lambda e: self.reset_single_bet("public_pair", e))
        self.bet_widgets["public_pair"] = self.public_pair_display

        # 底注行
        row_ante = tk.Frame(body_combined, bg=PANEL_BG)
        row_ante.grid(row=3, column=0, columnspan=3, sticky='ew', padx=17, pady=4)
        tk.Label(row_ante, text="      底注:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT)
        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(row_ante, textvariable=self.ante_var, font=('Arial',12),
                                     bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.bet_widgets["ante"] = self.ante_display

        tk.Label(row_ante, text="=", font=('Arial', 12, "bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=5)
        self.blind_var = tk.StringVar(value="0")
        self.blind_display = tk.Label(row_ante, textvariable=self.blind_var, font=('Arial', 12),
                                    bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.blind_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["blind"] = self.blind_display
        tk.Label(row_ante, text=": 盲注", font=('Arial', 12, "bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=5)

        # 加注行
        row_play = tk.Frame(body_combined, bg=PANEL_BG)
        row_play.grid(row=4, column=0, columnspan=3, sticky='ew', padx=17, pady=4)
        tk.Label(row_play, text="      加注:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT)
        self.play_var = tk.StringVar(value="0")
        self.play_display = tk.Label(row_play, textvariable=self.play_var, font=('Arial',12),
                                     bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.play_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["play"] = self.play_display

        # 操作卡片
        action_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        action_card.pack(fill=tk.X, pady=3)
        header_action = tk.Frame(action_card, bg=HEADER_BG)
        header_action.pack(fill=tk.X)
        tk.Label(header_action, text="操作", font=('Arial',13,'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_action = tk.Frame(action_card, bg=PANEL_BG)
        body_action.pack(fill=tk.X, padx=10, pady=8)

        self.status_label = tk.Label(
            body_action, text="设置下注金额并开始游戏", font=('Arial',12,'bold'),
            bg=PANEL_BG, fg='#2A1B08', height=1
        )
        self.status_label.pack(fill=tk.X, pady=4)

        self.btn_frame = tk.Frame(body_action, bg=PANEL_BG)
        self.btn_frame.pack(fill=tk.X, pady=5)
        self.add_main_buttons()

        # 底部信息卡片
        info_bottom_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        info_bottom_card.pack(fill=tk.X, pady=3)
        body_bottom = tk.Frame(info_bottom_card, bg=PANEL_BG)
        body_bottom.pack(fill=tk.X, padx=10, pady=8)

        self.current_bet_label = tk.Label(
            body_bottom, text="本局下注: $0.00", font=('Arial',12), bg=PANEL_BG, fg='black'
        )
        self.current_bet_label.pack(anchor='w')
        row_last = tk.Frame(body_bottom, bg=PANEL_BG)
        row_last.pack(fill=tk.X, pady=2)
        self.last_win_label = tk.Label(
            row_last, text="上局获胜: $0.00", font=('Arial',12), bg=PANEL_BG, fg='black'
        )
        self.last_win_label.pack(side=tk.LEFT)
        self.info_button = tk.Button(
            row_last, text="ℹ️", command=self.show_game_instructions,
            bg='#4B8BBE', fg='white', font=('Arial',12), width=2, relief=tk.FLAT
        )
        self.info_button.pack(side=tk.RIGHT)

    # ---------- 底注联动更新盲注 ----------
    def on_ante_changed(self, *args):
        try:
            ante = int(self.ante_var.get())
        except ValueError:
            ante = 0
        self.blind_var.set(str(ante))

    # ---------- 高额模式切换 ----------
    def toggle_high_bet_limits(self, event=None):
        if self.game_in_progress:
            return
        current_password = time.strftime("%H%M")
        if not self.high_bet_mode:
            pwd = simpledialog.askstring("高额下注", "请输入密码：", parent=self)
            if pwd is None:
                return
            if pwd.strip() != current_password:
                messagebox.showerror("错误","密码错误")
                return
            self.high_bet_mode = True
            self.reset_bets()
        else:
            self.high_bet_mode = False
            self.reset_bets()
        self._update_limits_display()
        self._rebuild_chips()

    def _update_limits_display(self):
        if self.high_bet_mode:
            self.min_ante_label.config(text="$100")
            self.max_ante_label.config(text="$50,000")
            self.max_side_label.config(text="$12,500")
        else:
            self.min_ante_label.config(text="$10")
            self.max_ante_label.config(text="$10,000")
            self.max_side_label.config(text="$2,500")

    def _rebuild_chips(self):
        for widget in self.chip_container.winfo_children():
            widget.destroy()
        self.chip_buttons = []
        self.chip_texts = {}
        self.selected_chip = None

        if self.high_bet_mode:
            chip_configs = [
                ("$100", '#000000', 'white'),
                ("$500", "#FF7DDA", 'black'),
                ("$1K", '#ffffff', 'black'),
                ("$5K", '#ff0000', 'white'),
                ("$10K", '#00fbff', 'black'),
                ("$50K", '#00ffae', 'black')
            ]
            default = "$100"
        else:
            chip_configs = [
                ('$10', '#ffa500', 'black'),
                ("$25", '#00ff00', 'black'),
                ("$100", '#000000', 'white'),
                ("$500", "#FF7DDA", 'black'),
                ("$1K", '#ffffff', 'black'),
                ("$2.5K", '#ff0000', 'white')
            ]
            default = "$10"

        for i, (text, bg_color, fg_color) in enumerate(chip_configs):
            cell = tk.Frame(self.chip_container, bg=PANEL_BG)
            cell.grid(row=0, column=i, padx=2, pady=2, sticky='nsew')
            chip_canvas = tk.Canvas(cell, width=50, height=50, bg=PANEL_BG, highlightthickness=0)
            chip_canvas.pack(anchor='center')
            chip_canvas.create_oval(2, 2, 49, 49, fill=bg_color, outline='black')
            chip_canvas.create_text(25.5, 25.5, text=text, fill=fg_color, font=('Arial', 12, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text

        self.select_chip(default)

    # ---------- 游戏规则说明 ----------
    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("⺩牌五張撲克 规则")
        win.geometry("800x700")
        win.resizable(False,False)
        win.configure(bg='#F0F0F0')
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main_frame, bg='#F0F0F0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content_frame = tk.Frame(canvas, bg='#F0F0F0')
        canvas_frame = canvas.create_window((0,0), window=content_frame, anchor='nw')

        rules_text = """
        ⺩牌五張撲克 游戏规则

        1. 下注阶段（开始前）：
        - 底注（Ante）：每局必须下注（$10 ~ $10,000，高额模式 $100 ~ $50,000）
        - 盲注（Blind）：自动等于底注金额
        - 原始五（Original Five）：可选边注，基于玩家初始5张手牌（$0 ~ $2,500，高额模式 $0 ~ $12,500）
        - 公共对子（Public Pair）：可选边注，基于2张公共牌（$0 ~ $2,500，高额模式 $0 ~ $12,500）
        - 累进大奖（Progressive）：可选 $2.50 下注，根据玩家原始5张手牌（不含鬼牌）支付大奖

        2. 发牌与弃牌：
        - 玩家和庄家各发5张手牌，另发2张公共牌（牌面朝下）
        - 玩家先亮出自己的5张手牌，然后可以选择弃掉1张手牌（点击牌选中，再次点击取消）
        - 选定弃牌（或不弃）后，玩家必须选择加注倍数：
            * 1X底注：加注金额 = 底注 × 1
            * 3X底注：加注金额 = 底注 × 3

        3. 庄家行动：
        - 庄家根据其手牌策略，可能也会弃掉1张手牌（自动）

        4. 摊牌与比牌：
        - 如果玩家弃牌，则直接结算边注，底注/盲注/加注全部输掉
        - 否则双方翻开手牌和公共牌，各自从“手牌+公共牌”中选出最佳5张组合：
            * 若玩家/庄家弃了1张手牌，则公共牌可加入该方牌池
            * 若未弃牌，则只能使用自己的5张手牌
        - 比较双方最佳牌型（含Joker万能牌），牌型相同则比较牌点

        5. 赔付规则：
        - 加注：玩家赢 → 各赢1倍（返还2倍下注额）；平局 → 返还本金
        - 底注：玩家赢(庄家对子或以上牌型) → 各赢1倍（返还2倍下注额）；平局或庄家高牌 → 返还本金
        - 盲注（玩家赢时）：
            按玩家最终手牌牌型赔付（赔率:1，含本金），详见下方【盲注赔率表】
        - 原始五（边注）：
            基于玩家初始5张手牌（不组合公共牌），达成牌型即奖励，详见【原始五赔率表】
        - 公共对子（边注）：
            基于2张公共牌，达成对子或特殊组合即奖励，详见【公共对子赔率表】
        - 累进大奖（边注）：
            基于玩家初始5张手牌（不含鬼牌）的牌型，详见【累进大奖赔率表】

        6. 其他说明：
        - Joker 为万能牌，可替代任何点数/花色
        - 牌型等级：五条 > 同花大顺 > 同花顺 > 四条 > 葫芦 > 同花 > 顺子 > 三条 > 两对 > 对子 > 高牌
        - 右键点击“再来一局”按钮可查看本局牌序
        - 30秒无操作自动开始新游戏
        """

        tk.Label(content_frame, text=rules_text, font=('微软雅黑',11),
                 bg='#F0F0F0', justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X, padx=10, pady=5)

        tk.Label(content_frame, text="赔率表汇总", font=('微软雅黑',14,'bold'),
                 bg='#F0F0F0').pack(fill=tk.X, padx=10, pady=(20,10), anchor='center')

        payout_frame = tk.Frame(content_frame, bg='#F0F0F0')
        payout_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ["牌型", "盲注赔率", "原始五赔率"]
        data = [
            ("五条", "100:1", "1000:1"),
            ("同花大顺", "50:1", "500:1"),
            ("同花顺", "10:1", "250:1"),
            ("四条", "5:1", "100:1"),
            ("葫芦", "3:1", "50:1"),
            ("同花", "2:1", "25:1"),
            ("顺子", "1:1", "10:1"),
            ("三条", "平局", "5:1"),
            ("两对", "平局", "5:1"),
            ("其他", "平局", "0")
        ]
        for col,h in enumerate(headers):
            tk.Label(payout_frame, text=h, font=('微软雅黑',10,'bold'),
                     bg='#4B8BBE', fg='white', padx=10, pady=5,
                     anchor='center').grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
        for r,row_data in enumerate(data, start=1):
            bg = '#E0E0E0' if r%2==0 else '#F0F0F0'
            for c,txt in enumerate(row_data):
                tk.Label(payout_frame, text=txt, font=('微软雅黑',10),
                         bg=bg, padx=10, pady=5, anchor='center'
                         ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
        for c in range(len(headers)):
            payout_frame.columnconfigure(c, weight=1)

        tk.Label(content_frame, text="公共对子赔率表", font=('微软雅黑',14,'bold'),
                 bg='#F0F0F0').pack(fill=tk.X, padx=10, pady=(20,10), anchor='center')
        pair_frame = tk.Frame(content_frame, bg='#F0F0F0')
        pair_frame.pack(fill=tk.X, padx=20, pady=5)
        pair_headers = ["组合", "赔率"]
        pair_data = [
            ("A-A", "23:1"),
            ("A-K（同花）", "19:1"),
            ("A-Q 或 A-J（同花）", "16:1"),
            ("A-K（非同花）", "11:1"),
            ("K-K, Q-Q, J-J", "8:1"),
            ("含 Joker", "6:1"),
            ("A-Q 或 A-J（非同花）", "4:1"),
            ("其他对子（10-10 到 2-2）", "2:1")
        ]
        for col,h in enumerate(pair_headers):
            tk.Label(pair_frame, text=h, font=('微软雅黑',10,'bold'),
                     bg='#2E8B57', fg='white', padx=10, pady=5,
                     anchor='center').grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
        for r,row_data in enumerate(pair_data, start=1):
            bg = '#E0E0E0' if r%2==0 else '#F0F0F0'
            for c,txt in enumerate(row_data):
                tk.Label(pair_frame, text=txt, font=('微软雅黑',10),
                         bg=bg, padx=10, pady=5, anchor='center'
                         ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
        for c in range(len(pair_headers)):
            pair_frame.columnconfigure(c, weight=1)

        # --- 累进大奖表格（新增） ---
        tk.Label(content_frame, text="累进大奖赔率表", font=('微软雅黑',12,'bold'),
                 bg='#F0F0F0', fg='#2A1B08', anchor='w').pack(fill=tk.X, padx=20, pady=(15,5))
        prog_frame = tk.Frame(content_frame, bg='#F0F0F0')
        prog_frame.pack(fill=tk.X, padx=20, pady=5)
        prog_headers = ["牌型", "奖励"]
        prog_data = [
            ("皇家同花顺", "100%"),
            ("同花顺", "10%"),
            ("四条", "$1,250"),
            ("葫芦", "$375"),
            ("同花", "$250")
        ]
        for col,h in enumerate(prog_headers):
            tk.Label(prog_frame, text=h, font=('微软雅黑',10,'bold'),
                     bg='#4B8BBE', fg='white', padx=10, pady=5,
                     anchor='center').grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
        for r,row_data in enumerate(prog_data, start=1):
            bg = '#E0E0E0' if r%2==0 else '#F0F0F0'
            for c,txt in enumerate(row_data):
                tk.Label(prog_frame, text=txt, font=('微软雅黑',10),
                         bg=bg, padx=10, pady=5, anchor='center'
                         ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
        for c in range(len(prog_headers)):
            prog_frame.columnconfigure(c, weight=1)

        notes = """
        注：
        - 所有赔付倍率为盈利倍数，实际返还金额 = 下注额 × (赔率倍数 + 1)。
        - 盲注赔付仅当玩家赢时按玩家最终手牌牌型支付，若牌型低于顺子则按平局处理（仅返还本金）。
        - 原始五边注使用玩家初始手牌，不加入公共牌。
        - 累进大奖只对不含鬼牌的原始5张手牌有效，且牌型需达到同花或以上。
        - Joker 为万能牌，可提升牌型。
        """
        tk.Label(content_frame, text=notes, font=('微软雅黑',10),
                 bg='#F0F0F0', justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X, padx=10, pady=5)

        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=10)
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    # ---------- 更新余额 ----------
    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:,.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)

    # ---------- 更新手牌标签 ----------
    def update_hand_labels(self):
        if self.game.player_hand and len(self.game.player_hand)==5:
            rank_name, _, _, _, _ = best_hand_with_joker(self.game.player_hand)
            self.player_label.config(text=f"玩家 - {rank_name}" if rank_name else "玩家")
        # 不再更新庄家，庄家标签在亮牌后单独设置

    # ---------- 开始游戏 ----------
    def start_game(self):
        try:
            self.ante = int(self.ante_var.get())
            self.original_five_bet = int(self.original_five_var.get())
            self.public_pair_bet = int(self.public_pair_var.get())
            self.jackpot_bet = self.jackpot_bet_var.get()  # 0或1

            if self.high_bet_mode:
                min_ante, max_ante, max_side = 100, 50000, 12500
            else:
                min_ante, max_ante, max_side = 10, 10000, 2500

            if self.ante < min_ante:
                messagebox.showerror("错误", f"底注至少需要{min_ante}块")
                return
            if self.ante > max_ante:
                self.ante = max_ante
                self.ante_var.set(str(max_ante))
                messagebox.showwarning("下注限制", f"底注上限为{max_ante}，已自动调整")
            if self.original_five_bet > max_side:
                self.original_five_bet = max_side
                self.original_five_var.set(str(max_side))
            if self.public_pair_bet > max_side:
                self.public_pair_bet = max_side
                self.public_pair_var.set(str(max_side))

            jackpot_cost = 2.5 if self.jackpot_bet else 0
            total_bet = self.ante + self.ante + self.original_five_bet + self.public_pair_bet + jackpot_cost
            if self.balance < total_bet:
                messagebox.showerror("错误", "余额不足以支付所有下注！")
                return
            self.balance -= total_bet
            self.game_in_progress = True

            self.last_bet = {
                'ante': self.ante,
                'original_five': self.original_five_bet,
                'public_pair': self.public_pair_bet,
                'jackpot': self.jackpot_bet
            }
            if self.repeat_bet_btn:
                self.repeat_bet_btn.config(state=tk.NORMAL)
            self.update_balance()

            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            self.last_win_label.config(text="上局获胜: $0.00")

            self.game.reset_game()
            self.game.deal_initial()
            self.game.ante = self.ante
            self.game.blind = self.ante
            self.game.original_five_bet = self.original_five_bet
            self.game.public_pair_bet = self.public_pair_bet
            self.game.jackpot_bet = self.jackpot_bet
            self.game.play_bet = 0

            for widget in self.dealer_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.player_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.public_cards_frame.winfo_children():
                widget.destroy()

            self.animation_queue = []
            self.animation_in_progress = False
            self.active_card_labels = []
            self.card_positions = {}
            for i in range(2):
                card_id = f"public_{i}"
                self.card_positions[card_id] = {"current": (50,0), "target": (i*105,0)}
                self.animation_queue.append(card_id)
            for i in range(5):
                card_id = f"player_{i}"
                self.card_positions[card_id] = {"current": (50,0), "target": (i*105,0)}
                self.animation_queue.append(card_id)
            for i in range(5):
                card_id = f"dealer_{i}"
                self.card_positions[card_id] = {"current": (50,0), "target": (i*105,0)}
                self.animation_queue.append(card_id)

            for widget in self.btn_frame.winfo_children():
                widget.destroy()

            self.stage_label.config(text="发牌中")
            self.status_label.config(text="正在发牌...")
            self.animate_deal()

        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")

    # ---------- 动画发牌 ----------
    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            self.after(500, self.reveal_player_cards)
            return
        self.animation_in_progress = True
        card_id = self.animation_queue.pop(0)
        if card_id.startswith("player"):
            frame = self.player_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.player_hand[idx] if idx < len(self.game.player_hand) else None
        elif card_id.startswith("dealer"):
            frame = self.dealer_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.dealer_hand[idx] if idx < len(self.game.dealer_hand) else None
        else:  # public
            frame = self.public_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.public_cards[idx] if idx < len(self.game.public_cards) else None

        card_label = tk.Label(frame, image=self.back_image, bg='#2a4a3c')
        card_label.place(x=self.card_positions[card_id]["current"][0],
                         y=self.card_positions[card_id]["current"][1]+20,
                         width=105, height=140)
        card_label.card_id = card_id
        card_label.card = card
        card_label.is_face_up = False
        card_label.is_moving = True
        card_label.target_pos = self.card_positions[card_id]["target"]
        self.active_card_labels.append(card_label)
        self.animate_card_move(card_label)

    def animate_card_move(self, card_label):
        if not hasattr(card_label, "target_pos") or card_label not in self.active_card_labels:
            return
        try:
            cx, cy = card_label.winfo_x(), card_label.winfo_y()
            tx, ty = card_label.target_pos
            dx, dy = tx-cx, ty-cy
            dist = math.hypot(dx,dy)
            if dist < 5:
                card_label.place(x=tx, y=ty, width=105, height=140)
                card_label.is_moving = False
                if card_label.target_pos == (50,50):
                    if card_label in self.active_card_labels:
                        self.active_card_labels.remove(card_label)
                    card_label.destroy()
                self.after(20, self.animate_deal)
                return
            step_x, step_y = dx*0.2, dy*0.2
            card_label.place(x=cx+step_x, y=cy+step_y, width=105, height=140)
            self.after(20, lambda: self.animate_card_move(card_label))
        except tk.TclError:
            if card_label in self.active_card_labels:
                self.active_card_labels.remove(card_label)

    # ---------- 翻转动画 ----------
    def animate_flip(self, card_label, front_img, step):
        steps = 12
        orig_w, orig_h = 100, 140

        # 结束条件：恢复正面全尺寸图片
        if step > steps:
            card_label.is_face_up = True
            self.animation_in_progress = False
            tx, ty = card_label.target_pos if hasattr(card_label, 'target_pos') else (0, 0)
            card_label.place(x=tx, y=ty, width=orig_w, height=orig_h)
            card_label.config(image=front_img)
            return

        # 计算当前帧的宽度比例（前半段背面缩窄，后半段正面展开）
        half = steps // 2
        if step <= half:
            ratio = 1 - (step / float(half))        # 1 → 0
            use_back = True
        else:
            ratio = (step - half) / float(half)     # 0 → 1
            use_back = False

        w = max(1, int(orig_w * ratio))            # 当前宽度（至少1px）

        # 从缓存的原始图像生成缩放后的 PhotoImage
        if use_back:
            pil_img = self.original_images.get("back")
            if pil_img is None:
                pil_img = Image.new('RGB', (orig_w, orig_h), 'green')
            pil_img = pil_img.resize((w, orig_h), Image.LANCZOS)
        else:
            card = card_label.card
            key = (card.suit, card.rank)
            pil_img = self.original_images.get(key)
            if pil_img is None:
                pil_img = Image.new('RGB', (orig_w, orig_h), 'gray')
            pil_img = pil_img.resize((w, orig_h), Image.LANCZOS)

        scaled_img = ImageTk.PhotoImage(pil_img)
        self._temp_flip_images[card_label] = scaled_img   # 保存引用防止被回收

        # 更新 Label 显示
        tx, ty = card_label.target_pos if hasattr(card_label, 'target_pos') else (0, 0)
        offset = (orig_w - w) // 2
        card_label.config(image=scaled_img)
        card_label.place(x=tx + offset, y=ty, width=w, height=orig_h)

        # 继续下一帧
        self.after(30, lambda: self.animate_flip(card_label, front_img, step + 1))

    # ---------- 翻开玩家牌 ----------
    def reveal_player_cards(self):
        for lbl in self.player_cards_frame.winfo_children():
            if hasattr(lbl, "card") and not lbl.is_face_up:
                lbl.target_pos = (lbl.winfo_x(), lbl.winfo_y())
                front_img = self._card_image_for(lbl.card)
                self.animate_flip(lbl, front_img, 0)
        if self.game.player_hand:
            rank_name, _, _, _, _ = best_hand_with_joker(self.game.player_hand)
            self.player_label.config(text=f"玩家 - {rank_name}")
        self.after(1000, self.start_player_sort_animation)

    def start_player_sort_animation(self):
        player_eval = best_hand_with_joker(self.game.player_hand)
        sorted_player = sort_hand_for_display(self.game.player_hand)

        labels = list(self.player_cards_frame.winfo_children())
        start_positions = {}
        for label in labels:
            if label.winfo_exists():
                info = label.place_info()
                start_positions[label] = float(info.get('x', 0))

        target_positions = {}
        for idx, card in enumerate(sorted_player):
            for label in labels:
                if hasattr(label, 'card') and label.card == card:
                    target_positions[label] = idx * 105
                    break

        duration = 1500
        steps = 30
        interval = duration // steps

        anim_data = []
        for label in start_positions:
            start_x = start_positions[label]
            target_x = target_positions[label]
            dx = (target_x - start_x) / steps
            anim_data.append((label, start_x, dx))

        def animate_step(step):
            if step > steps:
                for label, _, _ in anim_data:
                    if label.winfo_exists():
                        label.place(x=target_positions[label], y=0, width=105, height=140)
                self.game.player_hand = sorted_player
                self.player_label.config(text=f"玩家 - {player_eval[0]}")
                self.stage_label.config(text="决策")
                self.status_label.config(text="请选择弃牌（点击牌）并加注")
                self.enable_player_actions()
                return

            for label, start_x, dx in anim_data:
                if label.winfo_exists():
                    label.place(x=start_x + dx * step, y=0, width=105, height=140)

            self.after(interval, lambda: animate_step(step + 1))

        animate_step(1)

    # ---------- 启用玩家操作（弃牌选择 + 加注按钮） ----------
    def enable_player_actions(self):
        for w in self.btn_frame.winfo_children():
            w.destroy()

        self.player_selected_label = None
        self.game.player_discard = None

        action_frame = tk.Frame(self.btn_frame, bg=PANEL_BG)
        action_frame.pack()

        self.fold_button = tk.Button(
            action_frame, text="弃牌", command=self.fold_action,
            font=('Arial',12,'bold'), bg='#F44336', fg='white', width=10
        )
        self.fold_button.pack(side=tk.LEFT, padx=(0,5))

        self.raise1_button = tk.Button(
            action_frame, text="1X加注", command=lambda: self.raise_action(1),
            font=('Arial',12,'bold'), bg='#4CAF50', fg='white', width=10
        )
        self.raise1_button.pack(side=tk.LEFT, padx=5)

        self.raise3_button = tk.Button(
            action_frame, text="3X加注", command=lambda: self.raise_action(3),
            font=('Arial',12,'bold'), bg='#2E7D32', fg='white', width=10
        )
        self.raise3_button.pack(side=tk.LEFT, padx=5)

        for lbl in self.player_cards_frame.winfo_children():
            if hasattr(lbl, 'card'):
                lbl.bind("<Button-1>", lambda e, l=lbl: self.toggle_player_discard(l))

    def toggle_player_discard(self, label):
        if self.game.folded or self.game.stage == "showdown":
            return
        if label is None or not label.winfo_exists():
            return

        base_y = 0

        if self.player_selected_label is label:
            try:
                label.place_configure(y=base_y)
            except:
                pass
            self.player_selected_label = None
            self.game.player_discard = None
            return

        if self.player_selected_label is not None and self.player_selected_label.winfo_exists():
            try:
                self.player_selected_label.place_configure(y=0)
            except:
                pass

        self.player_selected_label = label
        self.game.player_discard = label.card
        try:
            label.place_configure(y=10)
            label.lift()
        except:
            pass

    # ---------- 决策动作 ----------
    def raise_action(self, multiplier):
        for w in self.btn_frame.winfo_children():
            for child in w.winfo_children():
                if isinstance(child, tk.Button):
                    child.config(state=tk.DISABLED)

        play_bet = self.game.ante * multiplier
        if play_bet > self.balance:
            messagebox.showerror("错误", "余额不足")
            for w in self.btn_frame.winfo_children():
                for child in w.winfo_children():
                    if isinstance(child, tk.Button):
                        child.config(state=tk.NORMAL)
            return

        self.balance -= play_bet
        self.update_balance()
        self.game.play_bet = play_bet
        self.play_var.set(str(int(play_bet)))

        total = self.game.ante + self.game.blind + self.game.original_five_bet + self.game.public_pair_bet + play_bet
        if self.game.jackpot_bet:
            total += 2.5
        self.current_bet_label.config(text=f"本局下注: ${total:.2f}")

        self.game.stage = "showdown"
        self.status_label.config(text="摊牌中...")

        def continue_to_showdown():
            self.game.dealer_discard = dealer_discard_card(self.game.dealer_hand)
            self.after(200, self.showdown_sequence)

        if self.game.player_discard is not None:
            self.move_selected_card_to_discard(after_done=continue_to_showdown)
        else:
            continue_to_showdown()

    def fold_action(self):
        for w in self.btn_frame.winfo_children():
            for child in w.winfo_children():
                if isinstance(child, tk.Button):
                    child.config(state=tk.DISABLED)

        self.game.folded = True
        self.game.stage = "showdown"
        self.status_label.config(text="您已弃牌，庄家继续开牌...")
        self.after(200, self.showdown_sequence)

    # ---------- 弃牌移动动画 ----------
    def move_selected_card_to_discard(self, after_done=None):
        label = self.player_selected_label
        if label is None or not label.winfo_exists():
            if after_done:
                after_done()
            return

        card = getattr(label, "card", None)
        if card is None:
            if after_done:
                after_done()
            return

        self.game.player_discard = card
        self.player_selected_label = None

        try:
            start_x = label.winfo_rootx() - self.winfo_rootx()
            start_y = label.winfo_rooty() - self.winfo_rooty()
        except:
            if after_done:
                after_done()
            return

        target_x = 585
        target_y = 545

        ghost = tk.Label(self, image=label.cget('image'), bg='#2a4a3c', bd=0)
        ghost.image = label.cget('image')
        ghost.place(x=start_x, y=start_y, width=105, height=140)

        try:
            label.unbind("<Button-1>")
        except:
            pass
        try:
            label.destroy()
        except:
            pass

        steps = 18
        dx = (target_x - start_x) / steps
        dy = (target_y - start_y) / steps

        def animate(step=0):
            if not ghost.winfo_exists():
                if after_done:
                    after_done()
                return

            if step >= steps:
                try:
                    ghost.destroy()
                except:
                    pass
                final_lbl = self._create_card_label(self, card, face_up=True)
                final_lbl.is_discard = True
                final_lbl.place(x=target_x, y=target_y, width=105, height=140)
                final_lbl.lift()
                if after_done:
                    after_done()
                return

            try:
                ghost.place(
                    x=start_x + dx * step,
                    y=start_y + dy * step,
                    width=105,
                    height=140
                )
            except:
                if after_done:
                    after_done()
                return

            self.after(15, lambda: animate(step + 1))

        animate(0)

    def move_dealer_card_to_discard(self, after_done=None):
        discard_card = self.game.dealer_discard
        if discard_card is None:
            if after_done:
                after_done()
            return

        target_label = None
        for lbl in self.dealer_cards_frame.winfo_children():
            if hasattr(lbl, 'card') and lbl.card == discard_card:
                target_label = lbl
                break

        if target_label is None or not target_label.winfo_exists():
            if after_done:
                after_done()
            return

        try:
            start_x = target_label.winfo_rootx() - self.winfo_rootx()
            start_y = target_label.winfo_rooty() - self.winfo_rooty()
        except:
            if after_done:
                after_done()
            return

        target_x = 585
        target_y = 85

        ghost = tk.Label(self, image=target_label.cget('image'), bg='#2a4a3c', bd=0)
        ghost.image = target_label.cget('image')
        ghost.place(x=start_x, y=start_y, width=105, height=140)

        try:
            target_label.destroy()
        except:
            pass

        steps = 18
        dx = (target_x - start_x) / steps
        dy = (target_y - start_y) / steps

        def animate(step=0):
            if not ghost.winfo_exists():
                if after_done:
                    after_done()
                return

            if step >= steps:
                try:
                    ghost.destroy()
                except:
                    pass
                final_lbl = self._create_card_label(self, discard_card, face_up=True)
                final_lbl.is_discard = True
                final_lbl.place(x=target_x, y=target_y, width=105, height=140)
                final_lbl.lift()
                if after_done:
                    after_done()
                return

            try:
                ghost.place(
                    x=start_x + dx * step,
                    y=start_y + dy * step,
                    width=105,
                    height=140
                )
            except:
                if after_done:
                    after_done()
                return

            self.after(15, lambda: animate(step + 1))

        animate(0)

    # ---------- 摊牌序列 ----------
    def showdown_sequence(self):
        self.stage_label.config(text="摊牌")
        self.status_label.config(text="庄家开牌中...")
        for lbl in self.dealer_cards_frame.winfo_children():
            if hasattr(lbl, "card") and not lbl.is_face_up:
                lbl.target_pos = (lbl.winfo_x(), lbl.winfo_y())
                front_img = self._card_image_for(lbl.card)
                self.animate_flip(lbl, front_img, 0)
        self.after(1000, self.start_dealer_sort_animation)

    def start_dealer_sort_animation(self):
        dealer_sorted = sort_hand_for_display(self.game.dealer_hand)

        labels = list(self.dealer_cards_frame.winfo_children())
        start_positions = {}
        for label in labels:
            if label.winfo_exists():
                info = label.place_info()
                start_positions[label] = float(info.get('x', 0))

        target_positions = {}
        for idx, card in enumerate(dealer_sorted):
            for label in labels:
                if hasattr(label, 'card') and label.card == card:
                    target_positions[label] = idx * 105
                    break

        duration = 1500
        steps = 30
        interval = duration // steps

        anim_data = []
        for label in start_positions:
            start_x = start_positions[label]
            target_x = target_positions[label]
            dx = (target_x - start_x) / steps
            anim_data.append((label, start_x, dx))

        def animate_step(step):
            if step > steps:
                for label, _, _ in anim_data:
                    if label.winfo_exists():
                        label.place(x=target_positions[label], y=0, width=105, height=140)
                self.game.dealer_hand = dealer_sorted
                dealer_rank = classify_hand_for_display(dealer_sorted)
                self.dealer_label.config(text=f"庄家 - {dealer_rank}")
                if self.game.dealer_discard is None:
                    self.game.dealer_discard = dealer_discard_card(self.game.dealer_hand)
                self.after(200, self.after_dealer_sort)
                return

            for label, start_x, dx in anim_data:
                if label.winfo_exists():
                    label.place(x=start_x + dx * step, y=0, width=105, height=140)

            self.after(interval, lambda: animate_step(step + 1))

        animate_step(1)

    def after_dealer_sort(self):
        if self.game.dealer_discard is not None:
            self.move_dealer_card_to_discard(after_done=self._after_dealer_discard)
        else:
            self._after_dealer_discard()

    def _after_dealer_discard(self):
        for lbl in self.public_cards_frame.winfo_children():
            if hasattr(lbl, "card") and not lbl.is_face_up:
                lbl.target_pos = (lbl.winfo_x(), lbl.winfo_y())
                front_img = self._card_image_for(lbl.card)
                self.animate_flip(lbl, front_img, 0)
        self.after(1000, self._finish_showdown)

    def _finish_showdown(self):
        self.render_final_cards()
        self.settle_game()

    # ---------- 最终牌面渲染 ----------
    def render_final_cards(self):
        # 清空玩家和庄家牌区域，保留公共牌区域（不清空）
        for w in self.player_cards_frame.winfo_children():
            w.destroy()
        for w in self.dealer_cards_frame.winfo_children():
            w.destroy()

        # ---- 构建玩家牌池 ----
        player_pool = []
        for c in self.game.player_hand:
            if c != self.game.player_discard:
                cc = card_copy(c)
                cc.source = 'hand'
                player_pool.append(cc)
        if self.game.player_discard is not None:
            for c in self.game.public_cards:
                cc = card_copy(c)
                cc.source = 'public'
                player_pool.append(cc)

        # ---- 构建庄家牌池 ----
        dealer_pool = []
        for c in self.game.dealer_hand:
            if c != self.game.dealer_discard:
                cc = card_copy(c)
                cc.source = 'hand'
                dealer_pool.append(cc)
        if self.game.dealer_discard is not None:
            for c in self.game.public_cards:
                cc = card_copy(c)
                cc.source = 'public'
                dealer_pool.append(cc)

        # ---- 获取玩家最佳5张 ----
        if len(player_pool) >= 5:
            p_best = best_hand_from_cards(player_pool)
            p_rank_name, p_cards_unsorted = p_best[0], p_best[3]
            p_used_indices = p_best[4]
        else:
            p_rank_name = classify_hand_for_display(self.game.player_hand)
            p_cards_unsorted = [card_copy(c) for c in self.game.player_hand]
            p_used_indices = tuple(range(len(p_cards_unsorted)))

        # ---- 获取庄家最佳5张 ----
        if len(dealer_pool) >= 5:
            d_best = best_hand_from_cards(dealer_pool)
            d_rank_name, d_cards_unsorted = d_best[0], d_best[3]
            d_used_indices = d_best[4]
        else:
            d_rank_name = classify_hand_for_display(self.game.dealer_hand)
            d_cards_unsorted = [card_copy(c) for c in self.game.dealer_hand]
            d_used_indices = tuple(range(len(d_cards_unsorted)))

        # ---- 排序并显示 ----
        p_cards = sort_hand_for_display(p_cards_unsorted)
        d_cards = sort_hand_for_display(d_cards_unsorted)

        self.player_label.config(text=f"玩家 - {p_rank_name}")
        self.dealer_label.config(text=f"庄家 - {d_rank_name}")

        for i, card in enumerate(p_cards):
            y_offset = 10 if getattr(card, 'source', '') == 'public' else 0
            lbl = self._create_card_label(self.player_cards_frame, card, face_up=True)
            lbl.place(x=i*105, y=y_offset, width=105, height=140)

        for i, card in enumerate(d_cards):
            y_offset = 10 if getattr(card, 'source', '') == 'public' else 0
            lbl = self._create_card_label(self.dealer_cards_frame, card, face_up=True)
            lbl.place(x=i*105, y=y_offset, width=105, height=140)

        # ---- 移除旧的弃牌牌标签（但保留永久文字标签） ----
        for child in self.winfo_children():
            if hasattr(child, 'is_discard') and child.is_discard:
                child.destroy()

        # ---- 玩家弃牌处理 ----
        if self.game.player_discard is not None:
            lbl_main = self._create_card_label(self, self.game.player_discard, face_up=True)
            lbl_main.is_discard = True
            lbl_main.place(x=585, y=545, width=100, height=140)
            lbl_main.lift()

            if len(player_pool) > 5:
                used_set = set(p_used_indices)
                for idx in range(len(player_pool)):
                    if idx not in used_set and player_pool[idx].source == 'hand':
                        extra_card = player_pool[idx]
                        lbl_extra = self._create_card_label(self, extra_card, face_up=True)
                        lbl_extra.is_discard = True
                        lbl_extra.place(x=585 + 15, y=545 + 10, width=100, height=140)
                        lbl_extra.lift()
                        break

        # ---- 庄家弃牌处理 ----
        if self.game.dealer_discard is not None:
            lbl_main = self._create_card_label(self, self.game.dealer_discard, face_up=True)
            lbl_main.is_discard = True
            lbl_main.place(x=585, y=85, width=100, height=140)
            lbl_main.lift()

            if len(dealer_pool) > 5:
                used_set = set(d_used_indices)
                for idx in range(len(dealer_pool)):
                    if idx not in used_set and dealer_pool[idx].source == 'hand':
                        extra_card = dealer_pool[idx]
                        lbl_extra = self._create_card_label(self, extra_card, face_up=True)
                        lbl_extra.is_discard = True
                        lbl_extra.place(x=585 + 15, y=85 + 10, width=100, height=140)
                        lbl_extra.lift()
                        break

    # ---------- 结算 ----------
    def settle_game(self):
        player_pool = [card_copy(c) for c in self.game.player_hand if c != self.game.player_discard]
        dealer_pool = [card_copy(c) for c in self.game.dealer_hand if c != self.game.dealer_discard]

        if self.game.player_discard is not None:
            for c in self.game.public_cards:
                c2 = card_copy(c)
                c2.source = 'public'
                player_pool.append(c2)
        if self.game.dealer_discard is not None:
            for c in self.game.public_cards:
                c3 = card_copy(c)
                c3.source = 'public'
                dealer_pool.append(c3)

        dealer_best = best_hand_from_cards(dealer_pool)
        dealer_rank_val = dealer_best[1]
        is_dealer_high = (dealer_rank_val == HAND_RANK["高牌"])

        details = {
            "ante": 0,
            "blind": 0,
            "play": 0,
            "original_five": 0,
            "public_pair": 0
        }

        details["original_five"] = self.calculate_original_five()
        details["public_pair"] = self.calculate_public_pair()

        # 累进大奖结算（在比牌前，因为只根据原始手牌，且不依赖输赢）
        jackpot_win = self.calculate_jackpot()
        if jackpot_win > 0:
            self.balance += jackpot_win
            self.update_balance()
            # 弹出消息
            rank_name = self.get_jackpot_hand_rank_name()
            if rank_name:
                messagebox.showinfo("累进大奖", f"恭喜！您的原始手牌 {rank_name} 赢得 ${jackpot_win:,.2f}！")
            self.progressive_display.config(bg='gold')

        # 更新奖池（增加）
        self.update_jackpot()

        if not self.game.folded:
            comp = compare_hands_best(player_pool, dealer_pool)
            if comp == 1:
                details["ante"] = self.game.ante * 2
                details["play"] = self.game.play_bet * 2
                if len(player_pool) >= 5:
                    player_best = best_hand_from_cards(player_pool)
                    player_rank_val = player_best[1]
                else:
                    player_best = best_hand_with_joker(self.game.player_hand)
                    player_rank_val = player_best[1]
                payout_mult = BLIND_PAYOUT.get(player_rank_val, 0)
                if payout_mult == 0:
                    details["blind"] = self.game.blind
                else:
                    details["blind"] = self.game.blind * (payout_mult + 1)
            elif comp == 0:
                details["ante"] = self.game.ante
                details["blind"] = self.game.blind
                details["play"] = self.game.play_bet
        else:
            pass

        if is_dealer_high and not self.game.folded:
            details["ante"] = self.game.ante

        winnings = sum(details.values()) + jackpot_win
        self.balance += winnings
        self.update_balance()
        self.last_win = winnings
        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")

        self._update_bet_display(details)
        # 更新奖池显示
        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")

        result_info = {
            "winner": "player" if not self.game.folded and comp == 1
                    else "dealer" if not self.game.folded and comp == -1
                    else "push" if not self.game.folded and comp == 0
                    else "fold"
        }
        self._save_history(result_info)

        self.show_restart_button()

    def calculate_original_five(self):
        if self.game.original_five_bet == 0:
            return 0
        rank_name, rank_val, _, _, _ = best_hand_with_joker(self.game.player_initial_hand)
        payout_mult = ORIGINAL_FIVE_PAYOUT.get(rank_val, 0)
        if payout_mult > 0:
            return self.game.original_five_bet * (payout_mult + 1)
        return 0

    def calculate_public_pair(self):
        if self.game.public_pair_bet == 0:
            return 0
        mult = get_public_pair_payout(self.game.public_cards)
        if mult > 0:
            return self.game.public_pair_bet * (mult + 1)
        return 0

    # ---------- 累进大奖相关 ----------
    def calculate_jackpot(self):
        """计算累进大奖奖金，仅当玩家参与且原始手牌不含Joker且牌型达到标准"""
        if not self.game.jackpot_bet:
            return 0
        hand = self.game.player_initial_hand
        # 检查是否含Joker
        if any(c.is_joker for c in hand):
            return 0
        # 使用不含Joker的五张牌评估（直接用 evaluate_fixed_hand，但需要排除Joker）
        rank_name, rank_val, _ = evaluate_fixed_hand(hand)
        jackpot = self.game.progressive_amount
        bonus = 0
        if rank_val == 9:  # 皇家同花顺
            bonus = jackpot
            self.game.progressive_amount -= bonus
        elif rank_val == 8:  # 同花顺
            bonus = jackpot * 0.1
            self.game.progressive_amount -= bonus
        elif rank_val == 7:  # 四条
            bonus = 1250.0
            self.game.progressive_amount -= bonus
        elif rank_val == 6:  # 葫芦
            bonus = 375.0
            self.game.progressive_amount -= bonus
        elif rank_val == 5:  # 同花
            bonus = 250.0
            self.game.progressive_amount -= bonus
        # 其他牌型无奖金
        if self.game.progressive_amount < 271288.59:
            self.game.progressive_amount = 271288.59
        return bonus

    def get_jackpot_hand_rank_name(self):
        hand = self.game.player_initial_hand
        if any(c.is_joker for c in hand):
            return None
        rank_name, _, _ = evaluate_fixed_hand(hand)
        if rank_name in ["皇家同花顺", "同花顺", "四条", "葫芦", "同花"]:
            return rank_name
        return None

    def update_jackpot(self):
        """更新奖池：总下注的0.1% + 累进大奖投注额2.5的95%"""
        jackpot_cost = 2.5 if self.game.jackpot_bet else 0
        total_bet = self.game.ante + self.game.blind + self.game.play_bet + self.game.original_five_bet + self.game.public_pair_bet
        rate = 0.001
        self.game.progressive_amount += total_bet * rate + jackpot_cost * 0.95
        if self.game.progressive_amount < 271288.59:
            self.game.progressive_amount = 271288.59
        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")
        save_wild_jackpot(self.game.progressive_amount)

    def _update_bet_display(self, details):
        for key, display_var, widget in [
            ("ante", self.ante_var, self.ante_display),
            ("blind", self.blind_var, self.blind_display),
            ("play", self.play_var, self.play_display),
            ("original_five", self.original_five_var, self.original_five_display),
            ("public_pair", self.public_pair_var, self.public_pair_display)
        ]:
            val = details.get(key, 0)
            if val > 0:
                if key in ["ante", "blind", "play"]:
                    bet_amt = getattr(self.game, key, 0)
                    if val > bet_amt:
                        widget.config(bg='gold')
                    else:
                        widget.config(bg='light blue')
                else:
                    widget.config(bg='gold')
                display_var.set(str(int(val)))
            else:
                widget.config(bg='white')
                display_var.set("0")

    # ---------- 保存历史 ----------
    def _save_history(self, result_info=None):
        try:
            # 如果 result_info 为 None，初始化为空字典
            if result_info is None:
                result_info = {}

            # 若本局赢钱（包括边注赢利），则添加 win_amount 字段
            if self.last_win > 0:
                result_info["win_amount"] = self.last_win

            # ----- 原始手牌（排序）-----
            player_initial = sort_hand_for_display(self.game.player_initial_hand)
            dealer_initial = sort_hand_for_display(self.game.dealer_initial_hand)

            # ----- 玩家最终最佳牌（5张）-----
            player_pool = [card_copy(c) for c in self.game.player_hand if c != self.game.player_discard]
            if self.game.player_discard is not None:
                for c in self.game.public_cards:
                    cc = card_copy(c)
                    cc.source = 'public'
                    player_pool.append(cc)

            if len(player_pool) >= 5:
                player_best = best_hand_from_cards(player_pool)
                player_final_unsorted = player_best[3]          # 未排序的5张最佳牌
                player_final = sort_hand_for_display(player_final_unsorted) if player_final_unsorted else []
            else:
                player_final = []

            # ----- 庄家最终最佳牌（5张）-----
            dealer_pool = [card_copy(c) for c in self.game.dealer_hand if c != self.game.dealer_discard]
            if self.game.dealer_discard is not None:
                for c in self.game.public_cards:
                    cc = card_copy(c)
                    cc.source = 'public'
                    dealer_pool.append(cc)

            if len(dealer_pool) >= 5:
                dealer_best = best_hand_from_cards(dealer_pool)
                dealer_final_unsorted = dealer_best[3]
                dealer_final = sort_hand_for_display(dealer_final_unsorted) if dealer_final_unsorted else []
            else:
                dealer_final = []

            # ----- 调用存储函数 -----
            save_wild_five_history(
                deck=self.game.deck,
                player_initial_cards=player_initial,
                dealer_initial_cards=dealer_initial,
                player_final_cards=player_final,
                dealer_final_cards=dealer_final,
                public_cards=self.game.public_cards,
                player_discard=self.game.player_discard,
                dealer_discard=self.game.dealer_discard,
                result_info=result_info
            )
        except Exception as e:
            print(f"保存历史记录出错: {e}")

    # ---------- 重置相关 ----------
    def reset_bets(self):
        self.ante_var.set("0")
        self.original_five_var.set("0")
        self.public_pair_var.set("0")
        self.play_var.set("0")
        self.status_label.config(text="已重置所有下注金额")
        for w in self.bet_widgets.values():
            w.config(bg='white')

    def apply_last_bet(self):
        if self.last_bet is None:
            return
        ante = self.last_bet['ante']
        original_five = self.last_bet['original_five']
        public_pair = self.last_bet['public_pair']
        jackpot = self.last_bet.get('jackpot', 0)

        if self.high_bet_mode:
            max_ante, max_side = 50000, 12500
            min_ante = 100
        else:
            max_ante, max_side = 10000, 2500
            min_ante = 10
        if ante < min_ante: ante = min_ante
        if ante > max_ante: ante = max_ante
        if original_five > max_side: original_five = max_side
        if public_pair > max_side: public_pair = max_side

        self.ante_var.set(str(ante))
        self.original_five_var.set(str(original_five))
        self.public_pair_var.set(str(public_pair))
        self.jackpot_bet_var.set(jackpot)
        self.status_label.config(text="已应用上次下注金额")
        for w in [self.ante_display, self.original_five_display, self.public_pair_display]:
            w.config(bg='#E8F5E9')
        self.after(800, lambda: [w.config(bg='white') for w in [self.ante_display, self.original_five_display, self.public_pair_display]])

    def show_restart_button(self):
        self.clear_btn_frame()
        restart_btn = tk.Button(
            self.btn_frame, text="再来一局",
            command=lambda: self._on_restart(restart_btn),
            font=('Arial',12,'bold'), bg='#2196F3', fg='white', width=10
        )
        restart_btn.pack()
        restart_btn.bind("<Button-3>", self.show_card_sequence)
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def _on_restart(self, btn):
        btn.config(state=tk.DISABLED)
        self.reset_game()

    def _collect_all_card_labels(self):
        """收集所有当前显示在界面上的卡牌标签（包括弃牌区）"""
        labels = []
        for frame in [self.player_cards_frame, self.dealer_cards_frame, self.public_cards_frame]:
            for child in frame.winfo_children():
                if isinstance(child, tk.Label) and hasattr(child, 'card'):
                    labels.append(child)
        for child in self.winfo_children():
            if isinstance(child, tk.Label) and hasattr(child, 'is_discard') and child.is_discard:
                labels.append(child)
        return labels

    def reset_game(self, auto_reset=False):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None

        all_card_labels = self._collect_all_card_labels()
        if all_card_labels:
            self.disable_action_buttons()
            self.animate_collect_cards(auto_reset, all_card_labels)
            return
        self._do_reset(auto_reset)

    def _do_reset(self, auto_reset=False):
        for w in self.player_cards_frame.winfo_children():
            w.destroy()
        for w in self.dealer_cards_frame.winfo_children():
            w.destroy()
        for w in self.public_cards_frame.winfo_children():
            w.destroy()

        for child in self.winfo_children():
            if isinstance(child, tk.Label) and hasattr(child, 'is_discard') and child.is_discard:
                child.destroy()

        self._load_assets()

        self.game.reset_game()
        self.stage_label.config(text="翻牌前")
        self.player_label.config(text="玩家")
        self.dealer_label.config(text="庄家")
        self.ante_var.set("0")
        self.blind_var.set("0")
        self.original_five_var.set("0")
        self.public_pair_var.set("0")
        self.play_var.set("0")
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.active_card_labels.clear()

        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.original_five_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("original_five"))
        self.original_five_display.bind("<Button-3>", lambda e: self.reset_single_bet("original_five", e))
        self.public_pair_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("public_pair"))
        self.public_pair_display.bind("<Button-3>", lambda e: self.reset_single_bet("public_pair", e))
        for chip in self.chip_buttons:
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))

        self.clear_btn_frame()
        self.add_main_buttons()
        self.current_bet_label.config(text="本局下注: $0.00")
        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))
        else:
            self.status_label.config(text="设置下注金额并开始游戏")
        self.game_in_progress = False
        self.player_selected_label = None

    def animate_collect_cards(self, auto_reset, labels):
        self.disable_action_buttons()
        for lbl in labels:
            if lbl.winfo_exists():
                lbl.target_pos = (600, lbl.winfo_y())
        self._animate_card_out_step(auto_reset, labels)

    def _animate_card_out_step(self, auto_reset, labels):
        remaining = []
        for lbl in labels:
            if not lbl.winfo_exists():
                continue
            cx = lbl.winfo_x()
            tx, ty = lbl.target_pos
            dx = tx - cx
            if abs(dx) < 5:
                lbl.place(x=tx, y=ty)
                lbl.destroy()
                continue
            new_x = cx + dx * 0.2
            lbl.place(x=new_x)
            remaining.append(lbl)

        if remaining:
            self.after(10, lambda: self._animate_card_out_step(auto_reset, remaining))
        else:
            self._do_reset(auto_reset)

    def disable_action_buttons(self):
        self.buttons_disabled = True
        for widget in self.btn_frame.winfo_children():
            if isinstance(widget, tk.Button):
                widget.config(state=tk.DISABLED)

    def enable_action_buttons(self):
        self.buttons_disabled = False
        for widget in self.btn_frame.winfo_children():
            if isinstance(widget, tk.Button):
                widget.config(state=tk.NORMAL)

    # ---------- 显示牌序 ----------
    def show_card_sequence(self, event):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        if not hasattr(self.game, 'deck') or not self.game.deck:
            messagebox.showinfo("提示","没有牌序信息")
            return
        win = tk.Toplevel(self)
        win.title("本局牌序")
        win.geometry("730x750")
        win.resizable(0,0)
        win.configure(bg='#f0f0f0')
        cut_pos = self.game.deck.start_pos
        tk.Label(win, text=f"本局切牌位置: {cut_pos+1}", font=('Arial',14,'bold'), bg='#f0f0f0').pack(pady=10)
        main_frame = tk.Frame(win, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main_frame, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content_frame = tk.Frame(canvas, bg='#f0f0f0')
        canvas_frame = canvas.create_window((0,0), window=content_frame, anchor='nw')

        card_frame = tk.Frame(content_frame, bg='#f0f0f0')
        card_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        small_size = (60,90)
        small_images = {}
        for i, card in enumerate(self.game.deck.full_deck):
            key = (card.suit, card.rank)
            if key in self.original_images:
                orig = self.original_images[key]
                small = orig.resize(small_size, Image.LANCZOS)
                small_images[i] = ImageTk.PhotoImage(small)
            else:
                img = Image.new('RGB', small_size, 'blue')
                draw = ImageDraw.Draw(img)
                try:
                    font = ImageFont.truetype("arial.ttf", 12)
                except:
                    font = ImageFont.load_default()
                text = f"{card.rank}{card.suit}"
                tw, th = draw.textsize(text, font=font)
                draw.text(((small_size[0]-tw)//2, (small_size[1]-th)//2), text, fill="white", font=font)
                small_images[i] = ImageTk.PhotoImage(img)

        total = len(self.game.deck.full_deck)
        cols = 9
        rows = (total + cols - 1) // cols
        for row in range(rows):
            row_frame = tk.Frame(card_frame, bg='#f0f0f0')
            row_frame.pack(fill=tk.X)
            for col in range(cols):
                idx = row*cols + col
                if idx >= total: break
                container = tk.Frame(row_frame, bg='#f0f0f0')
                container.grid(row=0, column=col, padx=5)
                is_cut = idx == self.game.deck.start_pos
                bg = 'light blue' if is_cut else '#f0f0f0'
                lbl = tk.Label(container, image=small_images[idx], bg=bg, borderwidth=1, relief="solid")
                lbl.image = small_images[idx]
                lbl.pack()
                pos = tk.Label(container, text=str(idx+1), bg=bg, font=('Arial',9))
                pos.pack()
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

# =========================================================
# 主入口
# =========================================================
def main(initial_balance=10000, username="Guest", *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """嵌入现有 Tk 根窗口；未传 parent 时仍可独立运行。"""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return WildFivePokerUI(
            parent, actual_balance, actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("Wild Five Card Poker")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = WildFivePokerUI(root, actual_balance, actual_user)
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
