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

# =========================================================
# 基础数据（来自 DJ_Wild）
# =========================================================
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
RANK_VALUES['JOKER'] = 99

HAND_RANK = {
    "五张王牌": 11,
    "皇家同花顺": 10,
    "五条": 9,
    "同花顺": 8,
    "四条": 7,
    "葫芦": 6,
    "同花": 5,
    "顺子": 4,
    "三条": 3,
    "两对": 2,
    "一对": 1,
    "高牌": 0
}
HAND_RANK_NAMES = {v: k for k, v in HAND_RANK.items()}

BLIND_PAYOUT = {
    "五张王牌": 1000, "皇家同花顺": 50, "五条": 10, "同花顺": 9,
    "四条": 4, "葫芦": 3, "同花": 2, "顺子": 1,
}
BONUS_PAYOUT = {
    ("五张王牌", True): 2000, ("皇家同花顺", True): 90, ("皇家同花顺", False): 1000,
    ("五条", True): 70, ("同花顺", True): 25, ("同花顺", False): 200,
    ("四条", True): 6, ("四条", False): 60, ("葫芦", True): 5, ("葫芦", False): 30,
    ("同花", True): 4, ("同花", False): 25, ("顺子", True): 3, ("顺子", False): 20,
    ("三条", True): 1, ("三条", False): 6,
}
DOUBLE_SIDE_PAYOUT = {
    "皇家同花顺": 10000, "五条": 10000, "同花顺": 5000, "四条": 500,
    "葫芦": 400, "同花": 100, "顺子": 100, "三条": 9,
}
WILD_PAYOUT = {5: 600, 4: 60, 3: 6, 2: 3, 1: 1}

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
# 牌局历史日志（DJ Wild）
# =========================================================
def dj_wild_log_path() -> str:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "DJ_Wild.json")

def save_dj_wild_history(deck, player_cards, dealer_cards, result_info=None):
    log_path = dj_wild_log_path()
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

    max_id = 0
    for rec in data["history"]:
        if "game_id" in rec and isinstance(rec["game_id"], int):
            if rec["game_id"] > max_id:
                max_id = rec["game_id"]
    new_game_id = max_id + 1

    stats = data["history_record"]
    stats["game"] += 1

    winner = None
    if result_info:
        if result_info.get("fold", False):
            winner = "fold"
            stats["fold"] += 1
        elif "winner" in result_info:
            winner = result_info["winner"]
            if winner == "player":
                stats["player_win"] += 1
            elif winner == "dealer":
                stats["dealer_win"] += 1
            elif winner == "push":
                stats["push"] += 1

    record = {
        "game_id": new_game_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "deck_order": [str(c) for c in deck.full_deck],
        "cut_position": deck.cut_position,
        "player_cards": [str(c) for c in player_cards],
        "dealer_cards": [str(c) for c in dealer_cards],
        "result": result_info if result_info else {}
    }
    if winner is not None:
        record["result"]["winner"] = winner
    data["history"].append(record)

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
            return f"JOKER({self.rank})"
        return f"{self.rank}{self.suit}"

    def is_wild(self):
        return self.rank == '2' or self.is_joker

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
                capture_output=True, text=True, encoding='utf-8',
                env=env, check=True, timeout=30
            )
            shuffle_data = json.loads(result.stdout)
            self.full_deck = [Card(d["suit"], d["rank"]) for d in shuffle_data["deck"]]
            self.cut_position = shuffle_data["cut_position"]
        except Exception:
            self.full_deck = [Card(s, r) for s in SUITS for r in RANKS] + [Card('JOKER', 'JOKER')]
            self._secure_shuffle()
            self.cut_position = secrets.randbelow(53)
        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + i) % len(self.full_deck) for i in range(len(self.full_deck))]
        self.pointer = 0
        self.card_sequence = [self.full_deck[i] for i in self.indexes]

    def _secure_shuffle(self):
        for i in range(len(self.full_deck)-1, 0, -1):
            j = secrets.randbelow(i+1)
            self.full_deck[i], self.full_deck[j] = self.full_deck[j], self.full_deck[i]

    def deal(self, n=1):
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt

# =========================================================
# DJ Wild 手牌评估（万能牌枚举法）
# =========================================================
def best_hand_with_wildcards(cards):
    wild_indices = [i for i, c in enumerate(cards) if c.is_wild()]

    if len(wild_indices) == 5:
        return "五张王牌", HAND_RANK["五张王牌"], [99] * 5, cards, [99] * 5

    non_wild_cards = [c for i, c in enumerate(cards) if i not in wild_indices]
    flush_suit = None
    if non_wild_cards and len(set(c.suit for c in non_wild_cards)) == 1:
        flush_suit = non_wild_cards[0].suit
    default_suit = '♠'

    possible_values = list(range(2, 15))
    best_rank = -1
    best_cmp = []
    best_hand = None
    best_eff = None

    for value_combo in product(possible_values, repeat=len(wild_indices)):
        temp_cards = []
        temp_values = []

        vi = 0
        for i in range(5):
            c = cards[i]
            if i in wild_indices:
                v = value_combo[vi]
                if c.is_joker:
                    suit = flush_suit if flush_suit else default_suit
                    new_rank = RANKS[v - 2]
                    new_card = Card(suit, new_rank)
                else:  # 普通2
                    new_card = Card(c.suit, RANKS[v - 2])
                temp_cards.append(new_card)
                temp_values.append(v)
                vi += 1
            else:
                temp_cards.append(Card(c.suit, c.rank))
                temp_values.append(c.value)

        if flush_suit:
            for tc in temp_cards:
                tc.suit = flush_suit

        rank_name, rank_val, cmp_vals = evaluate_fixed_hand(temp_cards)

        if rank_val > best_rank or (rank_val == best_rank and cmp_vals > best_cmp):
            best_rank = rank_val
            best_cmp = cmp_vals
            best_hand = temp_cards[:]
            best_eff = temp_values[:]

    if best_hand is None:
        rank_name, rank_val, cmp_vals = evaluate_fixed_hand(cards)
        return rank_name, rank_val, cmp_vals, cards, [c.value for c in cards]

    rank_name = HAND_RANK_NAMES.get(best_rank, "高牌")
    return rank_name, best_rank, best_cmp, best_hand, best_eff

def evaluate_fixed_hand(cards):
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    is_flush = len(set(suits)) == 1
    is_straight = False
    straight_high = 0
    unique_vals = sorted(set(values))
    if len(unique_vals) == 5:
        if unique_vals[-1] - unique_vals[0] == 4:
            is_straight = True
            straight_high = unique_vals[-1]
        elif unique_vals == [2,3,4,5,14]:
            is_straight = True
            straight_high = 5
    if is_flush and is_straight and values[0]==14 and values[-1]==10:
        return "皇家同花顺", HAND_RANK["皇家同花顺"], [14]
    if is_flush and is_straight:
        return "同花顺", HAND_RANK["同花顺"], [straight_high]
    freq = {}
    for v in values:
        freq[v] = freq.get(v, 0) + 1
    sorted_freq = sorted(freq.items(), key=lambda x: (x[1], x[0]), reverse=True)
    if sorted_freq[0][1] == 5:
        return "五条", HAND_RANK["五条"], [sorted_freq[0][0]]
    if sorted_freq[0][1] == 4:
        return "四条", HAND_RANK["四条"], [sorted_freq[0][0], sorted_freq[1][0]]
    if sorted_freq[0][1] == 3 and sorted_freq[1][1] == 2:
        return "葫芦", HAND_RANK["葫芦"], [sorted_freq[0][0], sorted_freq[1][0]]
    if is_flush:
        return "同花", HAND_RANK["同花"], values
    if is_straight:
        return "顺子", HAND_RANK["顺子"], [straight_high]
    if sorted_freq[0][1] == 3:
        return "三条", HAND_RANK["三条"], [sorted_freq[0][0], sorted_freq[1][0], sorted_freq[2][0]]
    if sorted_freq[0][1] == 2 and sorted_freq[1][1] == 2:
        return "两对", HAND_RANK["两对"], [sorted_freq[0][0], sorted_freq[1][0], sorted_freq[2][0]]
    if sorted_freq[0][1] == 2:
        return "一对", HAND_RANK["一对"], [sorted_freq[0][0], sorted_freq[1][0], sorted_freq[2][0], sorted_freq[3][0]]
    return "高牌", HAND_RANK["高牌"], values

def compare_hands_best(hand1, hand2):
    _, rank1, vals1, _, _ = best_hand_with_wildcards(hand1)
    _, rank2, vals2, _, _ = best_hand_with_wildcards(hand2)
    if rank1 > rank2:
        return 1
    if rank1 < rank2:
        return -1
    for a,b in zip(vals1, vals2):
        if a > b:
            return 1
        if a < b:
            return -1
    return 0

def sort_hand_for_display(hand, hand_eval):
    _, rank_val, _, _, eff_vals = hand_eval
    cards_with_eff = [(hand[i], eff_vals[i], hand[i].is_wild()) for i in range(len(hand))]

    if rank_val in [HAND_RANK["顺子"], HAND_RANK["同花顺"], HAND_RANK["皇家同花顺"]]:
        effs = [eff for _, eff, _ in cards_with_eff]
        if 14 in effs and 2 in effs and len(set(effs)) == 5:
            cards_with_eff.sort(key=lambda x: 1 if x[1] == 14 else x[1])
        else:
            cards_with_eff.sort(key=lambda x: x[1])
        return [c for c, _, _ in cards_with_eff]

    from collections import Counter
    cnt = Counter(eff for _, eff, _ in cards_with_eff)
    cards_with_eff.sort(key=lambda x: (cnt[x[1]], x[1], not x[2]), reverse=True)
    return [c for c, _, _ in cards_with_eff]

# =========================================================
# 游戏逻辑类（DJ Wild）
# =========================================================
class DJWildGame:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.player_hand = []
        self.dealer_hand = []
        self.ante = 0
        self.blind = 0
        self.bonus_bet = 0
        self.double_side_bet = 0
        self.play_bet = 0
        self.stage = "pre_flop"
        self.folded = False
        self.cards_revealed = {
            "player": [False]*5,
            "dealer": [False]*5
        }

    def deal_initial(self):
        self.player_hand = self.deck.deal(5)
        self.dealer_hand = self.deck.deal(5)


# Caribbean Stud 的 Canvas 桌面配色。
ROOT_BG = '#1B3D31'
CYAN = '#007502'
TEXT = '#ffffff'
RED = '#ff2a23'
BLACK = '#050505'
DARK_BLUE = '#173f66'
GOLD = '#D4AF37'
PANEL_BG = '#F2E6C9'
HEADER_BG = '#D8B46A'
TITLE_FG = '#2A1B08'

class DJWildTableGame:
    """双手牌桌状态；DJ Wild 的牌型、赔付表与单手版本一致。"""

    SEATS = ('Player1', 'Player2')

    def __init__(self):
        self.reset_game()

    @staticmethod
    def empty_bet():
        return dict(ante=0.0, blind=0.0, bonus=0.0, double_side=0.0, wild=0.0, play=0.0)

    def reset_game(self):
        self.deck = None
        self.deal_sequence = []
        self.hands = {seat: [] for seat in self.SEATS}
        self.dealer_hand = []
        self.bets = {seat: self.empty_bet() for seat in self.SEATS}
        self.decisions = {seat: 'inactive' for seat in self.SEATS}
        self.stage = 'betting'
        self.settlement = None
        self.side_returns = {}
        self.wild_returns = {}
        self.refunded_bets = {}
        self._evaluations = {}

    @staticmethod
    def betting_cost(bets):
        active = [b for b in bets.values() if b['ante']]
        return round(sum(sum(b.values()) for b in active)
                     + sum(2*b['ante'] for b in active if not b['play']), 2)

    def start_round(self, bets, balance, high_bet_mode=False):
        if self.stage != 'betting':
            raise ValueError('本局尚未结束。')
        minimum, maximum, side_max = (100, 50000, 12500) if high_bet_mode else (10, 10000, 2500)
        prepared, refunded = {}, {}
        for seat in self.SEATS:
            b = {key: float(bets[seat].get(key, 0)) for key in self.empty_bet()}
            if any(not math.isfinite(v) or v < 0 for v in b.values()):
                raise ValueError('下注金额必须是有限的非负数。')
            if not b['ante']:
                if any(b.values()):
                    refunded[seat] = dict(b)
                prepared[seat] = self.empty_bet()
                continue
            if not minimum <= b['ante'] <= maximum:
                raise ValueError(f'每手前注须为 ${minimum:,} 至 ${maximum:,}。')
            if b['blind'] != b['ante']:
                raise ValueError('盲注必须等于前注。')
            if any(b[kind] > side_max for kind in ('bonus', 'double_side', 'wild')):
                raise ValueError(f'每项边注最高为 ${side_max:,}。')
            if b['play'] not in (0, b['ante']*2):
                raise ValueError('加注必须为前注的两倍。')
            prepared[seat] = b
        if not any(b['ante'] for b in prepared.values()):
            raise ValueError('请至少为一手牌下前注。')
        if not math.isfinite(balance) or self.betting_cost(prepared) > balance:
            raise ValueError('余额不足以支付前注、盲注、边注及两手可能需要的两倍加注。')
        # 发牌成功后才提交下注，未参加的一手不消耗牌或动画节拍。
        deck = Deck()
        hands = {seat: [] for seat in self.SEATS}
        dealer = []
        active = tuple(s for s in self.SEATS if prepared[s]['ante'])
        sequence = [(side, i) for i in range(5) for side in (*active, 'Dealer')]
        for side, _index in sequence:
            (dealer if side == 'Dealer' else hands[side]).extend(deck.deal(1))
        self.deck, self.hands, self.dealer_hand = deck, hands, dealer
        self.deal_sequence, self.bets, self.refunded_bets = sequence, prepared, refunded
        self.decisions = {s: ('inactive' if not prepared[s]['ante'] else
                             'play' if prepared[s]['play'] else 'pending') for s in self.SEATS}
        self.stage = 'dealing'
        return round(sum(sum(b.values()) for b in prepared.values()), 2)

    def decide(self, seat, action, balance):
        if self.stage != 'decision' or self.decisions.get(seat) != 'pending':
            return 0.0
        if action not in ('play', 'fold'):
            raise ValueError('无效的决定。')
        cost = self.bets[seat]['ante']*2 if action == 'play' else 0.0
        reserve = sum(2*self.bets[s]['ante'] for s in self.SEATS
                      if s != seat and self.decisions[s] == 'pending')
        if cost and cost+reserve > balance:
            raise ValueError('余额不足以加注及保留另一手的两倍加注。')
        self.bets[seat]['play'], self.decisions[seat] = cost, action
        return cost

    def hand_eval(self, side):
        if side not in self._evaluations:
            hand = self.dealer_hand if side == 'Dealer' else self.hands[side]
            self._evaluations[side] = best_hand_with_wildcards(hand)
        return self._evaluations[side]

    def settle_bonus(self, seat):
        if seat in self.side_returns:
            return self.side_returns[seat]
        stake, hand = self.bets[seat]['bonus'], self.hands[seat]
        returned = 0.0
        if stake:
            name = self.hand_eval(seat)[0]
            if not any(c.is_wild() for c in hand):
                payout = BONUS_PAYOUT.get((name, False), 0)
            else:
                natural = 0
                if not any(c.is_joker for c in hand):
                    natural = BONUS_PAYOUT.get((evaluate_fixed_hand(hand)[0], False), 0)
                payout = max(natural, BONUS_PAYOUT.get((name, True), 0))
            returned = round(stake*(payout+1), 2) if payout else 0.0
        self.side_returns[seat] = returned
        return returned

    def wild_count(self, seat):
        # 按原始手牌统计；即使 2 没有作替代，也算一张万能牌。
        return sum(card.is_wild() for card in self.hands[seat])

    def settle_wild(self, seat):
        if seat not in self.wild_returns:
            stake = self.bets[seat]['wild']
            payout = WILD_PAYOUT.get(self.wild_count(seat), 0)
            self.wild_returns[seat] = round(stake*(payout+1), 2) if payout else 0.0
        return self.wild_returns[seat]

    def settle(self):
        if self.settlement is not None:
            return self.settlement
        if self.stage != 'showdown' or 'pending' in self.decisions.values():
            raise ValueError('完成两手决定并开牌后才能结算。')
        outcomes = {}
        dealer_eval = self.hand_eval('Dealer')
        for seat in self.SEATS:
            if self.decisions[seat] == 'inactive':
                continue
            b, player_eval = self.bets[seat], self.hand_eval(seat)
            details = self.empty_bet()
            details['bonus'] = self.settle_bonus(seat)
            details['wild'] = self.settle_wild(seat)
            if self.decisions[seat] == 'fold':
                # 红利及万能牌边注独立于主注，弃牌不撤销已开牌的边注奖励。
                winner, message = 'fold', '已弃牌：红利及万能牌边注独立结算'
            else:
                player_key, dealer_key = player_eval[1:3], dealer_eval[1:3]
                comparison = (player_key > dealer_key)-(player_key < dealer_key)
                if comparison > 0:
                    details['ante'], details['play'] = b['ante']*2, b['play']*2
                    details['blind'] = b['blind']*(BLIND_PAYOUT.get(player_eval[0], 0)+1)
                    winner, message = 'player', '玩家获胜'
                elif comparison == 0:
                    for kind in ('ante', 'blind', 'play'):
                        details[kind] = b[kind]
                    winner, message = 'push', '平局：前注、盲注、加注退回'
                else:
                    winner, message = 'dealer', '庄家获胜'
                if b['double_side'] and min(player_eval[1], dealer_eval[1]) >= HAND_RANK['三条']:
                    lower_name = HAND_RANK_NAMES[min(player_eval[1], dealer_eval[1])]
                    payout = DOUBLE_SIDE_PAYOUT.get(lower_name, 0)
                    if payout:
                        details['double_side'] = b['double_side']*(payout+1)
            returned, stake = round(sum(details.values()), 2), round(sum(b.values()), 2)
            outcomes[seat] = dict(winner=winner, message=message, details=details,
                                  returned=returned, stake=stake, net=round(returned-stake, 2))
        self.stage = 'settled'
        self.settlement = dict(hands=outcomes,
                               returned=round(sum(r['returned'] for r in outcomes.values()), 2))
        return self.settlement



class DJWildGUI(tk.Frame):
    WIDTH, HEIGHT = 1150, 750
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    DEAL_CARD_MS = 224 / .85
    DEAL_MOVE_MS = (128 / .75) / .85
    BET_CHIP_RADIUS = 16 * 4 / 3
    HOUSE_CHIP_POS = (575, 43)
    TABLE_GREEN = '#4b1e22'
    ZONE_COLORS = {'Player1':'#35634B','Player2':'#204536'}
    SEAT_NAMES = {'Player1': '玩家1', 'Player2': '玩家2', 'Dealer': '庄家手牌'}

    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = username, float(initial_balance)
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game = DJWildTableGame()
        self.bets = {s: self.game.empty_bet() for s in self.game.SEATS}
        self.last_bet = None
        self.last_win = 0.0
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
        self._chip_serial = 0
        self._decision_busy = False
        self._settlement_started = False
        self._showdown_started = False
        self.visual_chips = {}
        self.last_round_snapshot = None
        self._history_available = False
        self._blind_seats = set()
        self._sorted_sides = set()
        self._revealed_cards = set()
        self._face_photos, self._pil_cards, self._flip_photos = {}, {}, {}
        self._faded_photos, self._wild_label_items = {}, {}
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
        for key in ['back'] + [(s, r) for s in SUITS for r in RANKS] + [('JOKER', 'JOKER')]:
            filename = ('Background.png' if key == 'back' else 'JOKER-A.png'
                        if key == ('JOKER', 'JOKER') else f'{suits[key[0]]}{key[1]}.png')
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
                elif key == ('JOKER', 'JOKER'):
                    try:
                        joker_font = ImageFont.truetype('DejaVuSans-Bold.ttf', 13)
                    except OSError:
                        joker_font = ImageFont.load_default()
                    draw.text((8, 12), 'JOKER', font=joker_font, fill=RED)
                    draw.text((26, 60), '*', font=font, fill=RED)
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

    def _create_widgets(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=ROOT_BG, highlightthickness=0)
        self.canvas.place(x=0, y=0, width=self.WIDTH, height=self.HEIGHT)
        self.control_buttons = {}
        c = self.canvas
        self._text(575, 18, 'DJ WILD 梭哈扑克', 16, GOLD)
        c.create_rectangle(355, 44, 795, 197, fill=self.TABLE_GREEN, outline='')
        self.title_items = {'Dealer': self._text(575, 57, '庄家', 16, PANEL_BG)}
        self._draw_limit_table()
        c.create_rectangle(22, 200, 1128, 226, fill='#173C2E', outline='#65784B', width=1)
        c.create_line(25, 201, 1125, 201, fill='#E0C879', width=2)
        c.create_line(25, 225, 1125, 225, fill='#0C241B', width=2)
        self._text(575, 213, '2 与 JOKER 为万能牌 · 庄家任意牌型均合格 · 加注为前注的 2 倍', 13, GOLD)
        for seat, x0, x1 in (('Player1', 22, 566), ('Player2', 582, 1128)):
            c.create_rectangle(x0, 230, x1, 617, fill=self.ZONE_COLORS[seat], outline='')
            self.title_items[seat] = self._text((x0+x1)/2, 244, self.SEAT_NAMES[seat], 16, PANEL_BG)
            # 加注与前注等大，位于前注、盲注之间的下方；双向仍对齐等号。
            self._draw_wild_spot(seat, 'bonus', x0+85, 446, '红利', 40)
            self._draw_double_side_spot(seat, x0+235, 421)
            self._draw_wild_spot(seat, 'play', x0+235, 576, '加注', 40)
            self._draw_wild_spot(seat, 'ante', x0+180, 510, '前注', 40)
            self._draw_wild_spot(seat, 'blind', x0+290, 510, '盲注', 40)
            self._text(x0+235, 510, '＝', 19, PANEL_BG)
            self._draw_wild_count_spot(seat, x0+85, 561)
            self.action_buttons[(seat, 'play')] = self.create_control_button(
                x0+410, 419, x1-15, 477, '下注2X',
                lambda s=seat: self.play_action(s), '#397A48', font_size=14, draw_shadow=False)
            self.action_buttons[(seat, 'fold')] = self.create_control_button(
                x0+410, 488, x1-15, 546, '弃牌',
                lambda s=seat: self.fold_action(s), '#9B403A', font_size=14, draw_shadow=False)
        self._draw_bottom_controls()
        for side in ('Dealer', *self.game.SEATS):
            for index in range(5):
                x, y = self.card_position(side, index)
                c.create_rectangle(x, y, x+self.CARD_WIDTH, y+self.CARD_HEIGHT,
                                   outline='#7B9374', dash=(3, 3), tags='card_slots')

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
        self.set_control_button_state(self.clear_button, betting)
        self.set_control_button_state(self.repeat_button, betting and bool(self.last_bet))
        self.set_control_button_state(self.start_button, betting)
        restarting = self.game.stage in ('await_restart', 'returning', 'credit_pending', 'sweeping')
        c.itemconfigure(self.repeat_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button, state='normal' if restarting else 'hidden')
        self.set_control_button_state(self.restart_button, self.game.stage in ('await_restart', 'credit_pending'))
        for seat in self.game.SEATS:
            ready = self.game.stage == 'decision' and not self._decision_busy and self.game.decisions[seat] == 'pending'
            for action in ('play', 'fold'):
                tag = self.action_buttons[(seat, action)]
                # 右侧按钮只用于看牌后的决定，预下注由加注圈单独切换。
                self.set_control_button_state(tag, ready)

    def add_chip_to_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count:
            return
        new = {s: dict(b) for s, b in self.bets.items()}
        b = new[seat]
        if kind == 'play':
            self.set_pre_play(seat, not bool(b['play']))
            return
        main = kind in ('ante', 'blind')
        limit = (50000 if self.high_bet_mode else 10000) if main else (12500 if self.high_bet_mode else 2500)
        b[kind] = min(limit, b[kind]+self.selected_chip)
        if main:
            b['ante'] = b['blind'] = b[kind]
            if b['play']:
                b['play'] = b['ante']*2
        if self.game.betting_cost(new) > self.balance:
            messagebox.showwarning('无法下注', '余额不足；须保留每手可能需要的两倍加注。', parent=self)
            return
        self._apply_bet_layout(new)

    def reset_single_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count:
            return
        new = {s: dict(b) for s, b in self.bets.items()}
        if kind in ('ante', 'blind'):
            new[seat]['ante'] = new[seat]['blind'] = new[seat]['play'] = 0.0
        else:
            new[seat][kind] = 0.0
        self._apply_bet_layout(new)

    def reset_bets(self):
        if self.game.stage=='betting' and not self._motion_count:
            self._apply_bet_layout({s:self.game.empty_bet() for s in self.game.SEATS})

    def apply_last_bet(self):
        if self.game.stage != 'betting' or self._motion_count or not self.last_bet:
            return
        if self.game.betting_cost(self.last_bet) > self.balance:
            messagebox.showwarning('无法重复下注', '余额不足以重复上局下注及保留两倍加注。', parent=self)
            return
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

    def card_position(self, side, index):
        center={'Dealer':575,'Player1':294,'Player2':855}[side]
        return center-210+index*85,74 if side=='Dealer' else 260

    def start_game(self):
        if self.game.stage != 'betting' or self._motion_count:
            return
        try:
            charged = self.game.start_round(self.bets, self.balance, self.high_bet_mode)
        except ValueError as exc:
            messagebox.showwarning('无法开始', str(exc), parent=self)
            return
        self.game.stage = 'refunding'
        self._history_available = False
        self._close_card_sequence()
        self.balance = round(self.balance-charged, 2)
        self.bets = {s: dict(b) for s, b in self.game.bets.items()}
        self.last_bet = {s: dict(b) for s, b in self.bets.items()}
        self._credited = self._return_persisted = self._settlement_started = False
        self._side_resolved = set()
        self._cancel_restart_timer()
        self._blind_seats = {s for s in self.game.SEATS if self.game.decisions[s] == 'play'}
        self._sorted_sides, self._revealed_cards = set(), set()
        self._decision_busy = self._showdown_started = False
        self.canvas.delete('cards')
        self.card_items.clear()
        self._flip_photos.clear()
        self._faded_photos.clear()
        self._wild_label_items.clear()
        self._load_assets()
        for side, item in self.title_items.items():
            self.canvas.itemconfigure(item, text='庄家' if side == 'Dealer' else self.SEAT_NAMES[side])
        refunds = []
        for seat, refunded in self.game.refunded_bets.items():
            for kind in refunded:
                chip = self.visual_chips.pop((seat, kind, 'stake'), None)
                if chip:
                    refunds.append(dict(amount=chip['amount'], start=chip['xy'],
                                        target=self._rack_position(), duration=440))
        self._persist_balance()
        self._refresh()
        self._run_chip_batch(refunds, self._begin_deal)

    def _deal_next(self, sequence, offset):
        if offset==len(sequence):
            reveal = [(s,i) for s in self.game.SEATS
                if self.game.decisions[s]=='pending' for i in range(5)]
            self._reveal_next(reveal,0,self._after_initial_reveal)
            return
        side,index = sequence[offset]
        x,y = self.card_position(side,index)
        item = self.canvas.create_image(575,52,image=self._face_photos['back'],anchor='nw',tags='cards')
        self.card_items[(side,index)] = item
        def move(step=0):
            p=step/6
            self.canvas.coords(item,575+(x-575)*p,52+(y-52)*p)
            if step<6:
                self._schedule(round(self.DEAL_MOVE_MS*(step+1)/6)-round(self.DEAL_MOVE_MS*step/6),move,step+1)
            else:
                self._schedule(round(self.DEAL_CARD_MS)-round(self.DEAL_MOVE_MS),self._deal_next,sequence,offset+1)
        move()

    def _reveal_next(self, sequence, offset, complete):
        if offset==len(sequence):
            complete()
            return
        side,index = sequence[offset]
        card = self.game.dealer_hand[index] if side=='Dealer' else self.game.hands[side][index]
        item = self.card_items[(side,index)]
        x,y = self.card_position(side,index)
        def flip(step=0):
            fraction = abs(1-step/5)
            width = max(1,round(self.CARD_WIDTH*fraction))
            source = self._pil_cards['back' if step<5 else self._card_image_key(card)]
            photo = ImageTk.PhotoImage(source.resize((width,self.CARD_HEIGHT),Image.Resampling.LANCZOS),master=self)
            self._flip_photos[item] = photo
            self.canvas.itemconfigure(item,image=photo)
            self.canvas.coords(item,x+(self.CARD_WIDTH-width)/2,y)
            if step<10:
                self._schedule(32,flip,step+1)
            else:
                self.canvas.itemconfigure(item,image=self._face_photos[self._card_image_key(card)])
                self._flip_photos.pop(item,None)
                self._revealed_cards.add((side,index))
                self._reveal_next(sequence,offset+1,complete)
        flip()

    def _ready_for_decisions(self):
        self.game.stage = 'side_settling'
        self._refresh()
        seats = [s for s in self.game.SEATS if self.game.decisions[s] == 'pending']
        self._settle_side_bets(seats, self._enable_decisions, include_wild=True)

    def play_action(self, seat='Player1'):
        self._decide(seat, 'play')

    def fold_action(self, seat='Player1'):
        self._decide(seat,'fold')

    def _decide(self, seat, action):
        if self.game.stage!='decision' or self._decision_busy or self.game.decisions.get(seat)!='pending':return
        try:cost=self.game.decide(seat,action,self.balance)
        except ValueError as exc:
            messagebox.showwarning('无法加注',str(exc),parent=self);return
        self._decision_busy=True
        self.balance=round(self.balance-cost,2)
        self.bets[seat]['play']=self.game.bets[seat]['play']
        self._persist_balance();self._refresh()
        def done():
            self._decision_busy=False;self._refresh();self._maybe_showdown()
        if action=='fold':
            transfers=[]
            for kind in ('ante','blind','play'):
                chip=self.visual_chips.pop((seat,kind,'stake'),None)
                if chip:transfers.append(dict(amount=chip['amount'],start=chip['xy'],target=self.HOUSE_CHIP_POS,duration=280))
            self._run_chip_batch(transfers,done)
        else:
            target=self.bet_spots[(seat,'play')]['center']
            def arrived():
                self._set_visual(seat,'play','stake',cost);done()
            self._animate_chip(cost,self._rack_position(),target,arrived)
        self._refresh()

    def _maybe_showdown(self):
        if self._showdown_started or self._decision_busy or 'pending' in self.game.decisions.values():return
        self._showdown_started=True;self.game.stage='showdown';self._refresh()
        sequence=[(s,i) for s in self.game.SEATS if s in self._blind_seats for i in range(5)]
        self._reveal_next(sequence,0,self._after_blind_reveal)

    def _after_blind_reveal(self):
        self._sort_revealed_hands([s for s in self.game.SEATS if s in self._blind_seats],self._finish_blind_reveal)

    def _settle(self):
        if self._settlement_started:
            return
        self._settlement_started = True
        result = self.game.settle()
        self.game.stage, self.last_win = 'settling', result['returned']
        self._update_hand_title('Dealer')
        transfers, round_id = [], time.time_ns()
        for seat, outcome in result['hands'].items():
            self._update_hand_title(seat)
            for kind in ('ante', 'blind', 'play', 'double_side'):
                if kind == 'double_side' and (seat, kind) in self._side_resolved:
                    continue
                transfers.extend(self._outcome_transfers(seat, kind, self.game.bets[seat][kind], outcome['details'][kind]))
            if (seat, 'wild') not in self._side_resolved:
                # 预下注的万能牌边注到最终结算才派彩；非预下注已派过的不重复派。
                self._side_resolved.add((seat, 'wild'))
                transfers.extend(self._outcome_transfers(seat, 'wild', self.game.bets[seat]['wild'], outcome['details']['wild']))
            info = dict(outcome, seat=seat, round_id=round_id, bets=dict(self.game.bets[seat]),
                        fold=self.game.decisions[seat] == 'fold', winnings=outcome['returned'],
                        total_winnings=outcome['returned'], wild_count=self.game.wild_count(seat))
            try:
                save_dj_wild_history(self.game.deck, self.game.hands[seat], self.game.dealer_hand, info)
            except Exception as exc:
                messagebox.showerror('历史记录保存失败', str(exc), parent=self)
        self._status(' · '.join(f'{self.SEAT_NAMES[s]}：{r["message"]}' for s, r in result['hands'].items()))
        self._refresh()
        self._run_chip_batch(transfers, self._await_next_round)

    def reset_game(self, auto_reset=False):
        # 兼容原入口；通常由全部筹码回到筹码区自动开放下一局。
        if self.game.stage=='betting':
            self.reset_bets()

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

    def _register_spot(self, seat, kind, cx, cy, border, label, angle=0):
        c,tag = self.canvas,'spot_'+seat+'_'+kind
        self._text(cx,cy,label,14,PANEL_BG,angle=angle,tags=tag)
        self.bet_spots[(seat,kind)] = dict(tag=tag,center=(cx,cy),border=border)
        c.tag_bind(tag,'<Button-1>',lambda _e,s=seat,k=kind:self.add_chip_to_bet(s,k))
        c.tag_bind(tag,'<Button-3>',lambda _e,s=seat,k=kind:self.reset_single_bet(s,k))
        c.tag_bind(tag,'<Enter>',lambda _e:c.configure(cursor='hand2'))
        c.tag_bind(tag,'<Leave>',lambda _e:c.configure(cursor=''))

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

    def _sort_revealed_hands(self, sides, complete):
        """按 DJ Wild 的最佳万能牌组合排序，只移动牌面，不修改原始发牌记录。"""
        motions=[]
        for side in sides:
            hand=self.game.dealer_hand if side=='Dealer' else self.game.hands[side]
            if not hand or side in self._sorted_sides:
                continue
            ordered=sort_hand_for_display(hand,self.game.hand_eval(side))
            for target_index,card in enumerate(ordered):
                original_index=next(i for i,c in enumerate(hand) if c is card)
                item=self.card_items.get((side,original_index))
                if item is None:
                    continue
                start=self.canvas.coords(item)
                target=self.card_position(side,target_index)
                motions.append((item,start,target))
            self._sorted_sides.add(side)
        if not motions:
            self._render_wild_substitutions(sides)
            complete()
            return
        def step(frame=0):
            fraction=frame/15
            for item,(x,y),(tx,ty) in motions:
                self.canvas.coords(item,x+(tx-x)*fraction,y+(ty-y)*fraction)
            if frame<15:
                self._schedule(64,step,frame+1)
            else:
                self._render_wild_substitutions(sides)
                complete()
        step()

    def _after_initial_reveal(self):
        sides=[s for s in self.game.SEATS if self.game.decisions[s]=='pending']
        self._sort_revealed_hands(sides,self._ready_for_decisions)

    def _finish_blind_reveal(self):
        self.game.stage = 'side_settling'
        self._refresh()
        self._settle_side_bets([s for s in self.game.SEATS if s in self._blind_seats], self._open_dealer_rest)

    def _after_dealer_reveal(self):
        self._sort_revealed_hands(['Dealer'],self._settle)

    def _fade_card_item(self, item, source):
        # 与 UTH 相同：将原 alpha 乘以 .45，保留 PNG 边缘及牌桌底色。
        faded = source.convert('RGBA').copy()
        faded.putalpha(faded.getchannel('A').point(lambda value: round(value*.45)))
        photo = ImageTk.PhotoImage(faded, master=self)
        self._faded_photos[item] = photo
        self.canvas.itemconfigure(item, image=photo)

    @staticmethod
    def _wild_substitution_text(card, replacement, rank_name):
        if not card.is_wild() or (card.value == replacement.value and card.suit == replacement.suit):
            return None
        # 同花顺/皇家同花顺同时依赖点数与花色，显示完整替代牌。
        if rank_name in ('同花顺', '皇家同花顺'):
            return replacement.rank+replacement.suit
        # 纯同花只标花色，其余牌型只标需要补齐的点数。
        if rank_name == '同花' or (card.value == replacement.value and card.suit != replacement.suit):
            return replacement.suit
        return replacement.rank

    def _render_wild_substitutions(self, sides):
        """按最佳手牌的原始索引标记已翻开的万能牌，标记随牌一起收走。"""
        for side in sides:
            hand = self.game.dealer_hand if side == 'Dealer' else self.game.hands[side]
            if not hand or not all((side, i) in self._revealed_cards for i in range(5)):
                continue
            tag = 'wild_substitution_'+side
            self.canvas.delete(tag)
            rank_name, _rank, _values, effective, _effective_values = self.game.hand_eval(side)
            for index, (card, replacement) in enumerate(zip(hand, effective)):
                item = self.card_items.get((side, index))
                if item is None:
                    continue
                self._wild_label_items.pop((side, index), None)
                text = self._wild_substitution_text(card, replacement, rank_name)
                if text is None:
                    self._faded_photos.pop(item, None)
                    self.canvas.itemconfigure(item, image=self._face_photos[self._card_image_key(card)])
                    continue
                self._fade_card_item(item, self._pil_cards[self._card_image_key(card)])
                x, y = self.canvas.coords(item)
                cx, cy = x+self.CARD_WIDTH/2, y+self.CARD_HEIGHT/2
                tags = ('cards', 'wild_substitutions', tag)
                color = '#FF8B82' if text.endswith(('♥', '♦')) else '#FFE29A'
                font_size = 23 if len(text) >= 3 else 27 if len(text) == 2 else 30
                shadow = self._text(cx+1, cy+2, text, font_size, BLACK, tags=tags)
                label = self._text(cx, cy, text, font_size, color, tags=tags)
                self._wild_label_items[(side, index)] = (shadow, label)

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

    def _draw_chip(self, tag, amount, x, y, rectangular=False, extra_tags=(), show_amount=True):
        c=self.canvas;tags=(tag,*extra_tags)
        if rectangular:
            # 矩形筹码只显示中奖数字，不带货币符号；整数省略 .00。
            label=self._compact(amount);width=max(96,10*len(label)+16)
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
        self._run_chip_batch(transfers,self._refresh)
        self._refresh()

    @staticmethod
    def hand_type_text(hand):
        return best_hand_with_wildcards(hand)[0]

    def _update_hand_title(self, side):
        name = '庄家' if side == 'Dealer' else self.SEAT_NAMES[side]
        self.canvas.itemconfigure(self.title_items[side], text=f'{name} - {self.game.hand_eval(side)[0]}')

    def _enable_decisions(self):
        self.game.stage='decision';self._refresh();self._maybe_showdown()

    def _outcome_transfers(self, seat, kind, stake, returned):
        """本金留位，盈利派至左上；输注立即飞向统一庄家收筹码点，平局不动。"""
        if not stake:return []
        key=(seat,kind,'stake');center=self.bet_spots[(seat,kind)]['center']
        if returned<=0:
            chip=self.visual_chips.pop(key,None)
            return [dict(amount=chip['amount'],start=chip['xy'],target=self.HOUSE_CHIP_POS,duration=280)] if chip else []
        profit=round(returned-stake,2)
        if profit<=0:return []
        # 上方边注已靠近手牌，盈利筹码的顶边须留在牌区下方。
        safe_y=self.card_position(seat,0)[1]+self.CARD_HEIGHT+self.BET_CHIP_RADIUS+4
        target=(center[0]-32,max(center[1]-30,safe_y))
        return [dict(amount=profit,start=self.HOUSE_CHIP_POS,target=target,duration=440,
            arrive=lambda:self._set_visual(seat,kind,'profit',profit,target))]

    def _settle_side_bets(self, seats, complete, include_wild=False):
        transfers = []
        for seat in seats:
            for kind in (('bonus', 'wild') if include_wild else ('bonus',)):
                if (seat, kind) in self._side_resolved:
                    continue
                self._side_resolved.add((seat, kind))
                returned = self.game.settle_bonus(seat) if kind == 'bonus' else self.game.settle_wild(seat)
                transfers.extend(self._outcome_transfers(seat, kind, self.game.bets[seat][kind], returned))
            # 双向坏注要求双方至少三条；玩家两对或以下时已确定输注。
            # 与本手红利同一批收走，预下注手牌也须等到实际开牌后才判断。
            key = (seat, 'double_side')
            stake = self.game.bets[seat]['double_side']
            if stake and key not in self._side_resolved and self.game.hand_eval(seat)[1] < HAND_RANK['三条']:
                self._side_resolved.add(key)
                transfers.extend(self._outcome_transfers(seat, 'double_side', stake, 0.0))
        def done():
            for seat in seats:
                self._update_hand_title(seat)
            self._refresh()
            complete()
        self._run_chip_batch(transfers, done)

    def _open_dealer_rest(self):
        self.game.stage = 'showdown'
        self._refresh()
        # DJ Wild 庄家无明牌：决定完成后才翻开全部五张。
        self._reveal_next([('Dealer', i) for i in range(5)], 0, self._after_dealer_reveal)

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
        if self.game.stage != 'settling':
            return
        self.game.stage = 'await_restart'
        deck = self.game.deck
        self.last_round_snapshot = dict(full_deck=tuple(deck.full_deck), start_pos=deck.start_pos,
            images={key: im.copy() for key, im in self.original_images.items()})
        self._history_available = True
        self._cancel_restart_timer()
        self._restart_deadline = time.monotonic()+30
        self._refresh()
        self._restart_tick()

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
                self._faded_photos.clear();self._wild_label_items.clear()
                self._motion_count-=1
                self._finish_round()
        frame()

    def _finish_round(self):
        if self.game.stage != 'sweeping':
            return
        self.game.reset_game()
        self._history_available = False
        self._revealed_cards.clear()
        self.bets = {s: self.game.empty_bet() for s in self.game.SEATS}
        for side, item in self.title_items.items():
            self.canvas.itemconfigure(item, text='庄家' if side == 'Dealer' else self.SEAT_NAMES[side])
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
        # 原加勒比窗口：730×750，九张一排，切牌位置高亮，滚动显示53张原始牌序（含 JOKER）。
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
            original=snapshot['images'][self._card_image_key(card)]
            small_images[i]=ImageTk.PhotoImage(original.resize((60,90),Image.Resampling.LANCZOS),master=win)
        win._card_images=small_images
        total = len(snapshot['full_deck'])
        for row in range(math.ceil(total/9)):
            row_frame=tk.Frame(card_frame,bg='#f0f0f0');row_frame.pack(fill=tk.X)
            for col in range(9):
                idx=row*9+col
                if idx>=total:break
                container=tk.Frame(row_frame,bg='#f0f0f0');container.grid(row=0,column=col,padx=5)
                bg='light blue' if idx==cut_pos else '#f0f0f0'
                tk.Label(container,image=small_images[idx],bg=bg,borderwidth=1,relief='solid').pack()
                tk.Label(container,text=str(idx+1),bg=bg,font=('Arial',9)).pack()
        content_frame.update_idletasks();canvas.configure(scrollregion=canvas.bbox('all'))

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
        dialog.title('DJ Wild 梭哈扑克 游戏规则')
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
                '两手独立对同一手庄家牌；可只玩一手。只有边注而没有前注的玩家不参加，筹码退回。结算后点击“再来一局”收筹码入账，右键可查看完整53张牌序并停止倒计时。',
                [
                    [
                        '游戏目标',
                        '',
                        [
                            ('本局目标', '利用 2 与 JOKER 的万能牌能力组成最佳五张牌，争取胜过庄家。'),
                        ],
                        [],
                    ],
                    [
                        '一局如何进行',
                        '',
                        [
                            ('玩家下注', '分别设置玩家1、玩家2的前注（盲注自动同步）及可选边注，点击“开牌”。'),
                            ('玩家决策', '查看已发的手牌，依牌桌提示选择继续、加注或弃牌。'),
                            ('庄家开牌', '两手完成加注或弃牌后，庄家亮出全部五张牌；本游戏没有公共牌。'),
                            ('结算', '按比牌结果与各下注项目的条件分别结算。'),
                        ],
                        [],
                    ],
                    [
                        '万能牌（Wild Card）',
                        '',
                        [
                            ('', '• 所有点数 2 的牌 以及 JOKER 均为万能牌。\n• 万能牌可以变成任意点数（2~A）和任意花色，用于组成最佳牌型。'),
                        ],
                        [],
                    ],
                    [
                        '游戏流程',
                        '',
                        [
                            (
                                '',
                                '下注阶段：设置底注（盲注自动同步）、可选下注（红利、双向坏注、万能牌），点击“开牌”。\n发牌：一副53张牌（含1张JOKER）。每轮按玩家1、玩家2、庄家顺序发牌，各五张；未下注的玩家不取牌。\n翻牌：未预下注的玩家牌翻开并结算红利与万能牌边注；预下注2X的手牌在两手决定完成后翻开。庄家五张牌全程盖住，直到摊牌。\n决策阶段（仅当未预下注时）：\n• 弃牌：输掉底注、盲注，红利与万能牌边注独立结算，双向坏注输掉。\n• 下注2倍：支付底注×2作为加注，进入摊牌。\n摊牌：庄家牌全部翻开，比较玩家与庄家最终5张牌（使用万能牌的最佳组合）。\n• 玩家赢：底注、盲注、加注均按赔率支付（盲注见下方赔率表）。\n• 平局：退还所有下注（红利、双向坏注与万能牌边注单独结算）。\n• 玩家输：底注、盲注、加注输掉。',
                            ),
                        ],
                        [],
                    ],
                ],
            ),
            (
                '下注 & 限红',
                '各项目按每手限红；左键加筹码、右键清除。前注与盲注同步。点击加注圈或圈内筹码预下注2X，再点一次取消；右侧按钮只用于看牌后的决定。开始时预留每手可能需要的两倍加注。',
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
                                    ['底注', '普通：$10–$10,000\n高额：$100–$50,000', '参与主注比牌。'],
                                    ['盲注', '普通：$10–$10,000\n高额：$100–$50,000', '按盲注牌型及比牌结果结算。'],
                                    ['加注', '普通：最高$20,000\n高额：最高$100,000', '继续与庄家比牌。'],
                                    ['红利', '普通：每项最高$2,500\n高额：每项最高$12,500', '按玩家手牌（包括万能牌）判奖。'],
                                    ['双向坏注', '普通：每项最高$2,500\n高额：每项最高$12,500', '比较双方牌型，以较低牌型判奖。'],
                                    ['万能牌', '普通：每项最高$2,500\n高额：每项最高$12,500', '只统计玩家原始五张牌中的2与JOKER张数；点击∞符号下注。'],
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
                        '比牌规则',
                        '',
                        [],
                        [
                            (
                                '比牌与及格线',
                                ['判断', '规则'],
                                [
                                    ['组成牌型', '2 与 JOKER 可作万能牌，分别取双方最强五张牌。'],
                                    ['比大小', '先比牌型，再比相应牌点和踢脚。'],
                                    ['完全相同', '双方平局。'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '红利结算',
                        '',
                        [],
                        [
                            (
                                '',
                                ['情形／项目', '赔率／结算规则'],
                                [
                                    ['红利结算', '仅根据玩家手牌（含万能牌）支付。'],
                                    ['', '赔付倍率区分“无万能牌”（即手牌中无JOKER且2不作为万能，仅视为普通2）和“有万能牌”两种情况，取较高者。'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '万能牌边注结算',
                        '只计算玩家原始五张牌中的2与JOKER，是否实际作替代、庄家牌型及主注输赢均不影响此边注。非预下注在开牌后、开放选择前派彩；预下注在最终结算时派彩。',
                        [],
                        [
                            (
                                '万能牌张数与赔率',
                                ['万能牌张数', '净赢赔率', '含本金返还'],
                                [
                                    ['5张', '600:1', '下注额 × 601'],
                                    ['4张', '60:1', '下注额 × 61'],
                                    ['3张', '6:1', '下注额 × 7'],
                                    ['2张', '3:1', '下注额 × 4'],
                                    ['1张', '1:1', '下注额 × 2'],
                                    ['0张', '-', '0（边注输掉）'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '双向坏注结算',
                        '',
                        [],
                        [
                            (
                                '',
                                ['情形／项目', '赔率／结算规则'],
                                [
                                    ['双向坏注结算', '需要玩家和庄家牌型等级均 ≥ 三条。玩家两对或以下已确定输注，在玩家开牌后与红利同一批收走；预下注手牌须等到实际开牌。'],
                                    ['', '取两者中较低的牌型等级，按下方赔付表支付。'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '注意：赔率 X:1 表示净赢 X 倍；中奖返还为下注额 × (X+1)，包含本金。',
                        '',
                        [],
                        [
                            (
                                '',
                                ['注意'],
                                [
                                    ['赔率 X:1 表示净赢 X 倍；中奖返还为下注额 × (X+1)，包含本金。'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '赔付表汇总',
                        '',
                        [],
                        [
                            (
                                '',
                                ['牌型', '盲注#', '红利(有万能牌)##', '红利(无万能牌)', '双向坏注'],
                                [
                                    ['五张王牌', '1000:1', '2000:1', '-', '-'],
                                    ['皇家同花顺', '50:1', '90:1', '1000:1', '10000:1'],
                                    ['五条', '10:1', '70:1', '-', '10000:1'],
                                    ['同花顺', '9:1', '25:1', '200:1', '5000:1'],
                                    ['四条', '4:1', '6:1', '60:1', '500:1'],
                                    ['葫芦', '3:1', '5:1', '30:1', '400:1'],
                                    ['同花', '2:1', '4:1', '25:1', '100:1'],
                                    ['顺子', '1:1', '3:1', '20:1', '100:1'],
                                    ['三条', '平局', '1:1', '6:1', '9:1'],
                                    ['其他', '赢主注时退回', '-', '-', '-'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '庄家资格与主注结算',
                        '',
                        [],
                        [
                            (
                                '底注 / 加注结算',
                                ['获胜条件', '底注 / Ante', '相关下注'],
                                [
                                    ['玩家牌型较大', '底注赢 1:1', '加注赢 1:1；\n盲注依牌型表'],
                                    ['双方完全相同', '底注退还', '盲注与加注退还'],
                                    ['玩家牌型较小', '底注输', '盲注与加注输'],
                                    ['玩家弃牌', '底注输', '盲注输；\n红利及万能牌边注另计；双向坏注输'],
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
                        '12 种牌型',
                        '下方图片展示牌型示例；\n同一牌型也可能由其他牌面组成。',
                        [],
                        [
                            (
                                '牌型等级与牌例（由高至低）',
                                ['等级', '牌型', '牌例'],
                                [
                                    [
                                        '1',
                                        '五张王牌',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('JOKER', 'A'),
                                                ('♠', '2'),
                                                ('♥', '2'),
                                                ('♦', '2'),
                                                ('♣', '2'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '2',
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
                                        '3',
                                        '五条',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('JOKER', 'A'),
                                                ('♠', '9'),
                                                ('♥', '9'),
                                                ('♦', '9'),
                                                ('♣', '9'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '4',
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
                                        '5',
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
                                        '6',
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
                                        '7',
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
                                        '8',
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
                                        '9',
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
                                        '10',
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
                                        '11',
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
                                        '12',
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
                    [
                        '同牌型如何分胜负',
                        '',
                        [
                            ('比较方法', '本游戏顺序：五张王牌 ＞ 皇家同花顺 ＞ 五条 ＞ 同花顺 ＞ 四条 ＞ 葫芦 ＞ 同花 ＞ 顺子 ＞ 三条 ＞ 两对 ＞ 对子 ＞ 高牌。\n所有 2 与 JOKER 均为万能牌；\n先按最佳牌型比较，同牌型再比点数与踢脚。'),
                        ],
                        [],
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
                            (
                                '',
                                '注：\n• 所有赔付倍率为盈利倍数，实际返还金额 = 下注额 × (赔率倍数 + 1)。\n• 红利结算时，系统会分别计算“无万能牌”（即2视为普通2）和“有万能牌”的最佳牌型，取赔付较高的结果。\n• 双向坏注：需要双方牌型均 ≥ 三条，且只对较低的牌型支付。\n# 盲注的获胜条件是击败庄家。\n## JOKER 始终视为万能牌；\n普通 2 在无万能牌计算时视为普通2，在有万能牌计算时可变为任意牌。',
                            ),
                        ],
                        [],
                    ],
                    [
                        '特别规则补充',
                        '',
                        [
                            ('需留意的规则', '普通 2 与 JOKER 都是万能牌；\n实际替代其他牌时，原牌面淡化至45%。纯同花只显示花色；同花顺、皇家同花顺同时显示替代点数与花色；其余牌型显示替代点数。\n红利比较“使用万能牌”和“将 2 当普通牌”的结果，取较高赔付。\n万能牌边注按原始手牌的2与JOKER张数判奖，不要求这些牌实际作替代。'),
                        ],
                        [],
                    ],
                    [
                        '特殊下注规则',
                        '',
                        [
                            ('盲注', '自动等于底注'),
                            ('加注', '底注×2；\n可预下注'),
                            ('底注', '必须下注，自动同步为盲注的金额。'),
                            ('盲注', '金额自动等于底注，无需单独设置。'),
                            ('红利', '可选下注，根据玩家手牌（包括万能牌）支付，赢则同时赢取红利注。'),
                            ('双向坏注', '可选下注，同时比较玩家与庄家牌型，取较低牌型支付。'),
                            ('万能牌', '可选下注，统计玩家原始手牌中的2与JOKER；∞符号为下注区，筹码放在中心。'),
                            ('加注', '决策阶段可选，金额为底注×2。'),
                            ('下注类型', '也可提前预下注，直接进入摊牌（盲注模式）。'),
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
        tk.Label(header, text='DJ Wild 梭哈扑克 游戏规则', font=(font_name, 20, 'bold'),
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
        self.canvas.place(x=max(0, (self.winfo_width()-self.WIDTH)//2),
                          y=max(0, (self.winfo_height()-self.HEIGHT)//2),
                          width=self.WIDTH, height=self.HEIGHT)

    def _draw_wild_spot(self, seat, kind, cx, cy, label, radius):
        tag = 'spot_'+seat+'_'+kind
        border = self.canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
            fill=self.ZONE_COLORS[seat], outline=PANEL_BG, width=2, tags=tag)
        self._register_spot(seat, kind, cx, cy, border, label)

    def _draw_double_side_spot(self, seat, cx, cy):
        # 按参考图描绘上下尖嘴及左右斜边，保留中间的竖直连接面。
        tag = 'spot_'+seat+'_double_side'
        # 中间连接面原宽24px，现在加宽20px为44px，外侧尖嘴保留。
        outline = ((22, -43), (-34, -11), (-22, -11), (-22, 43),
                   (34, 11), (22, 11), (22, -43))
        points = [value for x, y in outline for value in (cx+x, cy+y)]
        border = self.canvas.create_polygon(*points, fill=self.ZONE_COLORS[seat],
                                            outline=PANEL_BG, width=2, tags=tag)
        self._register_spot(seat, 'double_side', cx, cy, border, '双向\n坏注')
        for item in self.canvas.find_withtag(tag):
            if self.canvas.type(item) == 'text':
                self.canvas.itemconfigure(item, font=('Arial', 9, 'bold'))

    def _draw_wild_count_spot(self, seat, cx, cy):
        tag = 'spot_'+seat+'_wild'
        # 透明感的开放式 ∞ 轮廓；同色命中面让符号中心及两侧均可下注。
        self.canvas.create_rectangle(cx-52, cy-26, cx+52, cy+26,
                                     fill=self.ZONE_COLORS[seat], outline='', tags=tag)
        points = []
        for index in range(65):
            angle = 2*math.pi*index/64
            points.extend((cx+48*math.sin(angle), cy+21*math.sin(2*angle)))
        border = self.canvas.create_line(*points, fill=PANEL_BG, width=3, smooth=True, tags=tag)
        self._register_spot(seat, 'wild', cx, cy, border, '')
        self._text(cx-32, cy, '万', 14, PANEL_BG, tags=tag)
        self._text(cx+32, cy, '能', 14, PANEL_BG, tags=tag)

    def set_pre_play(self, seat, enabled):
        if self.game.stage != 'betting' or self._motion_count or not self.bets[seat]['ante']:
            return
        new = {s: dict(b) for s, b in self.bets.items()}
        new[seat]['play'] = new[seat]['ante']*2 if enabled else 0.0
        if self.game.betting_cost(new) > self.balance:
            messagebox.showwarning('无法预下注', '余额不足以支付下注及保留另一手的两倍加注。', parent=self)
            return
        self._apply_bet_layout(new)

    def _begin_deal(self):
        self.game.stage = 'dealing'
        self._refresh()
        self._deal_next(self.game.deal_sequence, 0)

    @staticmethod
    def _card_image_key(card):
        return ('JOKER', 'JOKER') if card.is_joker else (card.suit, card.rank)

def main(initial_balance=10000, username="Guest", *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """嵌入现有 Tk 根窗口；未传 parent 时仍可独立运行。"""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return DJWildGUI(
            parent, actual_balance, actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("DJ Wild")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = DJWildGUI(root, actual_balance, actual_user)
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
