import copy
import json
import os
import random
import re
import secrets
import tkinter as tk
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from tkinter import messagebox, ttk

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
except ImportError:  # external artwork fallback still works with Canvas primitives
    Image = None
    ImageTk = None
    ImageDraw = None
    ImageFont = None


# -----------------------------------------------------------------------------
# Account-data compatibility with the original project
# -----------------------------------------------------------------------------
def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')


def format_two_decimals(value):
    """
    赔率显示规则：
    - ROUND_HALF_UP 四舍五入到 2 位小数
    - 如果结果刚好是 X.00，则只显示整数 X
    - 否则固定显示 2 位小数

    Examples:
        3.989898 -> '3.99'
        3.984    -> '3.98'
        3.985    -> '3.99'
        4.00     -> '4'
        8.00     -> '8'
        3.90     -> '3.90'
    """
    rounded = Decimal(str(value)).quantize(
        Decimal('0.01'),
        rounding=ROUND_HALF_UP
    )

    if rounded == rounded.to_integral_value():
        return str(int(rounded))

    return f'{rounded:.2f}'


def round_two_decimals_value(value):
    """Round an actual settlement odds value to 2 decimals using ROUND_HALF_UP."""
    return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


class GoldenDice:
    """Two-die helper copied from the uploaded Sicbo.py random-roll pattern."""
    def __init__(self):
        self.value = 1

    def roll(self):
        self.value = secrets.randbelow(6) + 1
        return self.value


def load_user_data():
    try:
        with open(get_data_file_path(), 'r', encoding='utf-8') as handle:
            data = json.load(handle)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def save_user_data(users):
    try:
        with open(get_data_file_path(), 'w', encoding='utf-8') as handle:
            json.dump(users, handle, ensure_ascii=False, indent=4)
    except OSError:
        pass


def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user.get('user_name') == username:
            user['cash'] = f'{new_balance:.2f}'
            break
    save_user_data(users)


# -----------------------------------------------------------------------------
# Baccarat rules / shoe / bet settlement
# -----------------------------------------------------------------------------
class BaccaratEngine:
    SUITS = ('Club', 'Diamond', 'Heart', 'Spade')
    RANKS = ('A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K')

    MODE_NAMES = {
        'classic': '经典百家乐',
        'tiger': '老虎百家乐',
        'ez': '简单百家乐',
        '2to1': '1赔2百家乐',
        'lucky7': '幸运7百家乐',
        'monkey': '猴子百家乐',
        'goldendice': '黄金骰子',
        'treasure': '聚宝盆',
        'xxx': 'XXX',
    }

    DISPLAY_NAMES = {
        'Player': '闲家',
        'Tie': '和局',
        'Banker': '庄家',
        'Pair Player': '闲家对子',
        'Pair Banker': '庄家对子',
        'Any Pair': '任意对子',
        'Dragon P': '闲家龙宝',
        'Dragon B': '庄家龙宝',
        'Perfect Pair': '完美对子',
        'Golden Hunter': '黄金猎手',
        'Golden Duel': '黄金对决',
        'Super Dice': '超级骰子',
        'Small Tiger': '小老虎',
        'Tiger Tie': '老虎和',
        'Big Tiger': '大老虎',
        'Tiger': '老虎',
        'Tiger Pair': '虎对子',
        'Panda 8': '熊猫8点',
        'Divine 9': '神之9点',
        'Dragon 7': '金龙7点',
        'Small Lucky 6': '小幸运6',
        'Lucky 6': '幸运6',
        'Big Lucky 6': '大幸运6',
        'Lucky 7': '幸运7',
        'Super 7': '超级幸运7',
        'Monkey 6': '猴老六',
        'Monkey Tie': '猴老六和',
        'Big Monkey': '猴子六仙',
        'Monkey 7': '猴7点',
        'Lucky Monkey': '幸运猴子',
    }

    # XXX golden-card payout rule: once a winning wager is hit by a golden
    # card, its printed PROFIT odds are multiplied directly by the integer
    # multiplier shown on that card.  No hidden payout-side RTP scale is used.

    # XXX Golden Duel is a separate 6-tier side bet and is EXEMPT from the
    # normal XXX 50% fee. The betting area shows only the overall range
    # 15-500,000:1; tier settlement still uses this six-level payout table.
    # Every two-or-more-digit price ends in 0 or 5 as required.
    GOLDEN_DUEL_PROFIT_ODDS = {
        1: 15,       # both Player and Banker receive >=1 golden card
        2: 35,       # condition 1 + Tie result
        3: 100,      # at least one side has a golden Pair
        4: 3000,     # both sides have golden Pairs
        5: 50000,    # five dealt cards share one identical golden face
        6: 500000,   # six dealt cards share one identical golden face
    }
    GOLDEN_DUEL_TARGET_RTP = 0.95

    # V24 Super Dice is one six-tier side wager.  Tiers are mutually exclusive:
    # the highest matching row is paid once.  It is exempt from the Golden Dice
    # mode's usual 20% wager fee.
    SUPER_DICE_PROFIT_ODDS = {
        1: 2600,  # dice total 9 + both sides Pair + Tie
        2: 2100,  # dice total 8 + both sides Pair + Tie
        3: 325,   # dice total 9 + both sides Pair
        4: 260,   # dice total 8 + both sides Pair
        5: 11,    # dice total 9 + either side Pair (higher tiers excluded)
        6: 9,     # dice total 8 + either side Pair (higher tiers excluded)
    }
    SUPER_DICE_TARGET_RTP = 0.95

    ODDS_TEXT = {
        'classic': {
            'Dragon P': '1–30:1', 'Perfect Pair': '25/250:1', 'Dragon B': '1–30:1',
            'Pair Player': '11:1', 'Any Pair': '5:1', 'Pair Banker': '11:1',
            'Player': '1:1', 'Tie': '8:1', 'Banker': '0.95:1',
        },
        'tiger': {
            'Small Tiger': '22:1', 'Tiger Tie': '35:1', 'Big Tiger': '50:1',
            'Tiger': '12/20:1', 'Tiger Pair': '4/20/100:1',
            'Player': '1:1', 'Tie': '8:1', 'Banker': '1:1*',
        },
        'ez': {
            'Panda 8': '25:1', 'Divine 9': '10/75:1', 'Dragon 7': '40:1',
            'Pair Player': '11:1', 'Dragon P': '1–30:1', 'Dragon B': '1–30:1',
            'Pair Banker': '11:1', 'Player': '1:1', 'Tie': '8:1', 'Banker': '1:1*',
        },
        '2to1': {
            'Dragon P': '1–30:1', 'Perfect Pair': '25/250:1', 'Dragon B': '1–30:1',
            'Pair Player': '11:1', 'Any Pair': '5:1', 'Pair Banker': '11:1',
            'Player': '1:1*', 'Tie': '8:1', 'Banker': '1:1*',
        },
        'lucky7': {
            'Small Lucky 6': '22:1', 'Lucky 6': '12/20:1', 'Big Lucky 6': '50:1',
            'Pair Player': '11:1', 'Lucky 7': '6/15:1', 'Super 7': '30/40/100:1#',
            'Pair Banker': '11:1', 'Player': '1:1', 'Tie': '8:1', 'Banker': '1:1*',
        },
        'monkey': {
            'Monkey 6': '12:1', 'Monkey Tie': '150:1', 'Big Monkey': '5000:1',
            'Pair Player': '11:1', 'Lucky Monkey': '1–75:1', 'Monkey 7': '40:1',
            'Pair Banker': '11:1', 'Player': '1:1', 'Tie': '8:1', 'Banker': '1:1',
        },
        'goldendice': {
            'Super Dice': '9–2600:1',
            'Pair Player': '10:1', 'Pair Banker': '10:1',
            'Player': '1:1', 'Tie': '5:1', 'Banker': '0.95:1',
        },
        'treasure': {
            'Golden Hunter': '3–51000:1',
            'Pair Player': '9:1', 'Pair Banker': '9:1',
            'Player': '1:1', 'Tie': '5:1', 'Banker': '0.95:1',
        },
        'xxx': {
            'Golden Duel': '15-500,000:1',
            'Pair Player': '8:1', 'Pair Banker': '8:1',
            'Player': '1:1', 'Tie': '2.85:1', 'Banker': '0.97:1',
        },
    }

    MODE_ROWS = {
        'classic': (
            ('Dragon P', 'Perfect Pair', 'Dragon B'),
            ('Pair Player', 'Any Pair', 'Pair Banker'),
        ),
        'tiger': (
            ('Small Tiger', 'Tiger Tie', 'Big Tiger'),
            ('Tiger', 'Tiger Pair'),
        ),
        'ez': (
            ('Panda 8', 'Divine 9', 'Dragon 7'),
            ('Pair Player', 'Dragon P', 'Dragon B', 'Pair Banker'),
        ),
        '2to1': (
            ('Dragon P', 'Perfect Pair', 'Dragon B'),
            ('Pair Player', 'Any Pair', 'Pair Banker'),
        ),
        'lucky7': (
            ('Small Lucky 6', 'Lucky 6', 'Big Lucky 6'),
            ('Pair Player', 'Lucky 7', 'Super 7', 'Pair Banker'),
        ),
        'monkey': (
            ('Monkey 6', 'Monkey Tie', 'Big Monkey'),
            ('Pair Player', 'Lucky Monkey', 'Monkey 7', 'Pair Banker'),
        ),
        'goldendice': (
            ('Super Dice',),
            ('Pair Player', 'Pair Banker'),
        ),
        'treasure': (
            ('Golden Hunter',),
            ('Pair Player', 'Pair Banker'),
        ),
        'xxx': (
            ('Golden Duel',),
            ('Pair Player', 'Pair Banker'),
        ),
    }

    def __init__(self, decks=8):
        self.decks = int(decks)
        self.deck = []
        self.current_index = 0
        self.cut_threshold = random.SystemRandom().randint(50, 80)
        self.shuffle_count = 0
        self.new_shoe()

    def new_shoe(self, deck=None):
        if deck is None:
            deck = [
                (suit, rank)
                for _ in range(self.decks)
                for suit in self.SUITS
                for rank in self.RANKS
            ]
            random.SystemRandom().shuffle(deck)
        self.deck = [tuple(card) for card in deck]
        self.current_index = 0
        self.cut_threshold = random.SystemRandom().randint(50, 80)
        self.shuffle_count += 1

    def set_shoe_state(self, deck, current_index=0, cut_threshold=None):
        self.deck = [tuple(card) for card in deck]
        self.current_index = max(0, min(int(current_index), len(self.deck)))
        if cut_threshold is None:
            cut_threshold = random.SystemRandom().randint(50, 80)
        self.cut_threshold = max(50, min(80, int(cut_threshold)))

    def cut_shoe(self, cut_position):
        if not self.deck:
            self.new_shoe()
        cut_position = max(0, min(int(cut_position), len(self.deck) - 1))
        self.deck = self.deck[cut_position:] + self.deck[:cut_position]
        self.current_index = 0
        self.cut_threshold = random.SystemRandom().randint(50, 80)

    def remaining_cards(self):
        return max(0, len(self.deck) - self.current_index)

    def needs_shuffle(self):
        return self.remaining_cards() <= self.cut_threshold

    @staticmethod
    def card_value(card):
        rank = card[1]
        if rank == 'A':
            return 1
        if rank in ('10', 'J', 'Q', 'K'):
            return 0
        return int(rank)

    @classmethod
    def score(cls, hand):
        return sum(cls.card_value(card) for card in hand) % 10

    def draw_card(self):
        if self.current_index >= len(self.deck):
            raise RuntimeError('牌靴已用完，请重新切牌。')
        card = self.deck[self.current_index]
        self.current_index += 1
        return card

    def deal_round(self):
        if self.remaining_cards() < 6:
            raise RuntimeError('剩余牌不足，请重新切牌。')
        reshuffled = False

        player = [self.draw_card()]
        banker = [self.draw_card()]
        player.append(self.draw_card())
        banker.append(self.draw_card())

        p_initial = self.score(player)
        b_initial = self.score(banker)
        natural = p_initial >= 8 or b_initial >= 8

        player_third = None
        if not natural and p_initial <= 5:
            player_third = self.draw_card()
            player.append(player_third)

        if not natural:
            b_score = self.score(banker[:2])
            if player_third is None:
                if b_score <= 5:
                    banker.append(self.draw_card())
            else:
                third = self.card_value(player_third)
                draw = (
                    b_score <= 2
                    or (b_score == 3 and third != 8)
                    or (b_score == 4 and 2 <= third <= 7)
                    or (b_score == 5 and 4 <= third <= 7)
                    or (b_score == 6 and 6 <= third <= 7)
                )
                if draw:
                    banker.append(self.draw_card())

        p_score = self.score(player)
        b_score = self.score(banker)
        if p_score > b_score:
            winner = 'Player'
        elif b_score > p_score:
            winner = 'Banker'
        else:
            winner = 'Tie'

        return {
            'player_hand': player,
            'banker_hand': banker,
            'player_score': p_score,
            'banker_score': b_score,
            'winner': winner,
            'natural': natural,
            'reshuffled': reshuffled,
            'shoe_remaining': self.remaining_cards(),
        }

    @staticmethod
    def _pair_flags(result):
        p = result['player_hand']
        b = result['banker_hand']
        return p[0][1] == p[1][1], b[0][1] == b[1][1]

    @classmethod
    def side_return_factors(cls, result, mode, current_bets=None):
        """Return winning side-bet total-return multipliers.

        A value of 12 means 11:1 profit plus original stake. A value of 1 is a
        push. This mirrors the payout behaviour of the supplied Baccarat.py.
        """
        factors = {}
        p = result['player_hand']
        b = result['banker_hand']
        winner = result['winner']
        ps = result['player_score']
        bs = result['banker_score']
        player_pair, banker_pair = cls._pair_flags(result)

        if mode == 'tiger':
            if player_pair ^ banker_pair:
                factors['Tiger Pair'] = 5
            elif player_pair and banker_pair and p[0][1] != b[0][1]:
                factors['Tiger Pair'] = 21
            elif player_pair and banker_pair and p[0][1] == b[0][1]:
                factors['Tiger Pair'] = 101

            if winner == 'Banker' and bs == 6:
                factors['Tiger'] = 13 if len(b) == 2 else 21
                if len(b) == 2:
                    factors['Small Tiger'] = 23
                else:
                    factors['Big Tiger'] = 51
            if winner == 'Tie' and bs == 6:
                factors['Tiger Tie'] = 36

        elif mode == 'ez':
            if winner == 'Banker' and len(b) == 3 and bs == 7:
                factors['Dragon 7'] = 41
            if winner == 'Player' and len(p) == 3 and ps == 9:
                factors['Divine 9'] = 11
            elif winner == 'Banker' and len(b) == 3 and bs == 9:
                factors['Divine 9'] = 11
            elif winner == 'Tie' and len(p) == 3 and len(b) == 3 and ps == 9 and bs == 9:
                factors['Divine 9'] = 76
            if winner == 'Player' and len(p) == 3 and ps == 8:
                factors['Panda 8'] = 26
            if player_pair:
                factors['Pair Player'] = 12
            if banker_pair:
                factors['Pair Banker'] = 12
            cls._add_dragon_factors(factors, result)

        elif mode == 'monkey':
            monkey_ranks = {'J', 'Q', 'K'}
            pt = p[2] if len(p) >= 3 else None
            bt = b[2] if len(b) >= 3 else None
            if pt and bt and pt[1] not in monkey_ranks and bt[1] in monkey_ranks:
                factors['Monkey 6'] = 13
                if winner == 'Tie':
                    factors['Monkey Tie'] = 151
            if len(p) == 3 and len(b) == 3 and all(card[1] in monkey_ranks for card in p + b):
                factors['Big Monkey'] = 5001
            if len(b) == 3 and bs == 7 and winner == 'Banker':
                factors['Monkey 7'] = 41

            player_monkey = bool(pt and pt[1] in monkey_ranks)
            banker_monkey = bool(bt and bt[1] in monkey_ranks)
            if pt and bt:
                if player_monkey and banker_monkey and pt == bt:
                    factors['Lucky Monkey'] = 76
                elif player_monkey and banker_monkey and pt[1] == bt[1]:
                    factors['Lucky Monkey'] = 26
                elif player_monkey and banker_monkey:
                    factors['Lucky Monkey'] = 11
                elif player_monkey ^ banker_monkey:
                    factors['Lucky Monkey'] = 2
            elif pt and player_monkey:
                factors['Lucky Monkey'] = 4
            elif bt and banker_monkey:
                factors['Lucky Monkey'] = 9

            if player_pair:
                factors['Pair Player'] = 12
            if banker_pair:
                factors['Pair Banker'] = 12

        elif mode in ('classic', '2to1'):
            if player_pair:
                factors['Pair Player'] = 12
            if banker_pair:
                factors['Pair Banker'] = 12
            if player_pair or banker_pair:
                factors['Any Pair'] = 6
            cls._add_dragon_factors(factors, result)
            # Perfect Pair: either side's first two cards must match in both
            # rank and suit. One qualifying side pays 25:1; both qualifying
            # sides in the same hand pay 250:1.
            player_perfect = len(p) >= 2 and p[0] == p[1]
            banker_perfect = len(b) >= 2 and b[0] == b[1]
            if player_perfect and banker_perfect:
                factors['Perfect Pair'] = 251
            elif player_perfect or banker_perfect:
                factors['Perfect Pair'] = 26

        elif mode == 'goldendice':
            # Golden Dice pairs use 10:1 base profit odds.  Their profit odds are
            # later multiplied only when the two dice total 8 or 9.
            if player_pair:
                factors['Pair Player'] = 11
            if banker_pair:
                factors['Pair Banker'] = 11
            tier = cls.super_dice_tier(result)
            profit_odds = cls.SUPER_DICE_PROFIT_ODDS.get(tier)
            if profit_odds is not None:
                factors['Super Dice'] = float(profit_odds) + 1.0

        elif mode in ('treasure', 'xxx'):
            # Treasure and XXX share the golden-card multiplier engine but keep
            # different dedicated side bets and pair prices.
            pair_factor = 10 if mode == 'treasure' else 9
            if player_pair:
                factors['Pair Player'] = pair_factor
            if banker_pair:
                factors['Pair Banker'] = pair_factor

            if mode == 'treasure':
                # Original Treasure Pot side bet: Golden Hunter.
                golden_count = cls.golden_hit_count(result)
                hunter_profit_odds = {2: 3, 3: 25, 4: 155, 5: 3150, 6: 51000}
                if golden_count in hunter_profit_odds:
                    factors['Golden Hunter'] = hunter_profit_odds[golden_count] + 1
            else:
                # XXX-only six-tier Golden Duel.  Exactly one (highest) tier is
                # paid per round, so overlapping conditions never stack.
                tier = cls.golden_duel_tier(result)
                profit_odds = cls.GOLDEN_DUEL_PROFIT_ODDS.get(tier)
                if profit_odds is not None:
                    factors['Golden Duel'] = float(profit_odds) + 1.0

        elif mode == 'lucky7':
            if winner == 'Banker' and bs == 6:
                if len(b) == 2:
                    factors['Small Lucky 6'] = 23
                    factors['Lucky 6'] = 13
                else:
                    factors['Big Lucky 6'] = 51
                    factors['Lucky 6'] = 21
            if player_pair:
                factors['Pair Player'] = 12
            if banker_pair:
                factors['Pair Banker'] = 12
            if winner == 'Player' and ps == 7:
                factors['Lucky 7'] = 7 if len(p) == 2 else 16
            if ps == 7 and bs == 6:
                total_cards = len(p) + len(b)
                factors['Super 7'] = {4: 31, 5: 41, 6: 101}.get(total_cards, 0)

        return {key: factor for key, factor in factors.items() if factor > 0}

    @classmethod
    def _add_dragon_factors(cls, factors, result):
        p = result['player_hand']
        b = result['banker_hand']
        ps = result['player_score']
        bs = result['banker_score']
        winner = result['winner']
        total_cards = len(p) + len(b)
        factor_map = {4: 2, 5: 3, 6: 5, 7: 7, 8: 11, 9: 31}

        if winner == 'Tie' and total_cards == 4 and ps in (8, 9):
            factors['Dragon P'] = 1
            factors['Dragon B'] = 1
            return

        if winner == 'Player':
            if total_cards == 4 and ps in (8, 9):
                factors['Dragon P'] = 2
            elif total_cards != 4:
                factors['Dragon P'] = factor_map.get(ps - bs, 0)
        elif winner == 'Banker':
            if total_cards == 4 and bs in (8, 9):
                factors['Dragon B'] = 2
            elif total_cards != 4:
                factors['Dragon B'] = factor_map.get(bs - ps, 0)

    @staticmethod
    def _golden_map(result):
        mapping = result.get('_golden_multiplier_map', {}) if isinstance(result, dict) else {}
        if isinstance(mapping, dict):
            return mapping
        return {}

    @classmethod
    def golden_hit_count(cls, result):
        mapping = cls._golden_map(result)
        if not mapping:
            return 0
        cards = list(result.get('player_hand', [])) + list(result.get('banker_hand', []))
        return sum(1 for card in cards if tuple(card) in mapping)

    @classmethod
    def golden_duel_tier(cls, result):
        """Return the highest winning XXX Golden Duel tier (0..6).

        Tier 5/6 mean five/six actually dealt cards share the exact same face
        (same suit + rank), and that face is one of the current golden faces.
        A golden Pair means the normal baccarat Pair condition is met and both
        of that side's first two cards are golden.
        """
        mapping = cls._golden_map(result)
        if not mapping:
            return 0
        p = list(result.get('player_hand', []))
        b = list(result.get('banker_hand', []))
        all_cards = p + b

        # Highest jackpots first: identical golden face across 5/6 dealt cards.
        face_counts = {}
        for card in all_cards:
            face = tuple(card)
            face_counts[face] = face_counts.get(face, 0) + 1
        max_golden_same = max(
            (count for face, count in face_counts.items() if face in mapping),
            default=0,
        )
        if max_golden_same >= 6:
            return 6
        if max_golden_same >= 5:
            return 5

        def golden_pair(hand):
            return (len(hand) >= 2
                    and hand[0][1] == hand[1][1]
                    and tuple(hand[0]) in mapping
                    and tuple(hand[1]) in mapping)

        player_golden_pair = golden_pair(p)
        banker_golden_pair = golden_pair(b)
        if player_golden_pair and banker_golden_pair:
            return 4
        if player_golden_pair or banker_golden_pair:
            return 3

        player_has_gold = any(tuple(card) in mapping for card in p)
        banker_has_gold = any(tuple(card) in mapping for card in b)
        if player_has_gold and banker_has_gold:
            if result.get('winner') == 'Tie':
                return 2
            return 1
        return 0

    @classmethod
    def super_dice_tier(cls, result):
        """Return the highest payable Golden Dice / Super Dice tier (0..6)."""
        try:
            dice_total = int(result.get('_golden_dice_total', 0))
        except (TypeError, ValueError, AttributeError):
            return 0
        if dice_total not in (8, 9):
            return 0
        player_pair, banker_pair = cls._pair_flags(result)
        both_pair = player_pair and banker_pair
        any_pair = player_pair or banker_pair
        is_tie = result.get('winner') == 'Tie'
        if dice_total == 9 and both_pair and is_tie:
            return 1
        if dice_total == 8 and both_pair and is_tie:
            return 2
        if dice_total == 9 and both_pair:
            return 3
        if dice_total == 8 and both_pair:
            return 4
        if dice_total == 9 and any_pair:
            return 5
        if dice_total == 8 and any_pair:
            return 6
        return 0

    @classmethod
    def golden_multiplier_for_cards(cls, cards, result):
        mapping = cls._golden_map(result)
        multiplier = 1
        for card in cards:
            multiplier *= int(mapping.get(tuple(card), 1))
        return max(1, int(multiplier))

    @classmethod
    def golden_multiplier_for_bet(cls, bet_type, result):
        if not cls._golden_map(result):
            return 1
        p = list(result.get('player_hand', []))
        b = list(result.get('banker_hand', []))
        if bet_type == 'Player':
            return cls.golden_multiplier_for_cards(p, result)
        if bet_type == 'Banker':
            return cls.golden_multiplier_for_cards(b, result)
        if bet_type == 'Tie':
            return cls.golden_multiplier_for_cards(p + b, result)
        if bet_type == 'Pair Player':
            return cls.golden_multiplier_for_cards(p[:2], result)
        if bet_type == 'Pair Banker':
            return cls.golden_multiplier_for_cards(b[:2], result)
        return 1

    @classmethod
    def main_return_factor(cls, bet_type, result, mode):
        winner = result['winner']
        ps = result['player_score']
        bs = result['banker_score']
        p_len = len(result['player_hand'])
        b_len = len(result['banker_hand'])

        if bet_type == 'Tie':
            if winner != 'Tie':
                return 0.0
            if mode in ('treasure', 'goldendice'):
                return 6.0
            if mode == 'xxx':
                return 3.85
            return 9.0

        if bet_type == 'Player':
            if winner == 'Tie':
                return 0.0 if mode == '2to1' else 1.0
            if winner != 'Player':
                return 0.0
            if mode == '2to1' and p_len == 3 and ps in (8, 9):
                return 3.0
            return 2.0

        if bet_type == 'Banker':
            if winner == 'Tie':
                return 0.0 if mode == '2to1' else 1.0
            if winner != 'Banker':
                return 0.0
            if mode in ('tiger', 'lucky7'):
                return 1.5 if bs == 6 else 2.0
            if mode == 'ez':
                return 1.0 if b_len == 3 and bs == 7 else 2.0
            if mode in ('classic', 'treasure', 'goldendice'):
                return 1.95
            if mode == 'xxx':
                return 1.97
            if mode == '2to1':
                return 3.0 if b_len == 3 and bs in (8, 9) else 2.0
            # monkey mode showed Banker 1:1 in the supplied UI but the old
            # resolve_bets branch omitted it. V3 follows the displayed rule.
            return 2.0

        return 0.0

    @classmethod
    def resolve_bets(cls, bets, result, mode, jackpot_amount=0.0):
        side_factors = cls.side_return_factors(result, mode, bets)
        outcomes = []
        credit = 0.0
        gross_profit = 0.0
        lost_stake = 0.0

        for bet_type, stake in bets.items():
            stake = float(stake)
            if stake <= 0:
                continue
            if bet_type in ('Player', 'Tie', 'Banker'):
                factor = cls.main_return_factor(bet_type, result, mode)
            else:
                factor = float(side_factors.get(bet_type, 0.0))

            # Winning normal wagers may have their PROFIT odds amplified by
            # golden cards.  Each mode's dedicated side bet is excluded.
            dedicated_side_bet = ('Golden Hunter' if mode == 'treasure'
                                  else 'Golden Duel' if mode == 'xxx' else None)
            if mode in ('treasure', 'xxx') and bet_type != dedicated_side_bet and factor > 1.0:
                gold_mult = cls.golden_multiplier_for_bet(bet_type, result)
                # Multiply the wager's PROFIT odds directly by the golden-card
                # multiplier.  Example in XXX: Player 1:1 hit by 4X -> 4.00:1.
                # Banker starts from 0.97:1; any longer decimal result is rounded
                # to two decimal places with ROUND_HALF_UP before settlement.
                amplified_profit_odds = (factor - 1.0) * float(gold_mult)
                factor = 1.0 + round_two_decimals_value(amplified_profit_odds)

            # Golden Dice uses one pre-drawn multiplier per normal wager type.
            # It activates only when the two golden dice total 8 or 9.  The
            # multiplier applies to PROFIT odds, never to the original stake.
            if (mode == 'goldendice' and bet_type in
                    ('Player', 'Banker', 'Tie', 'Pair Player', 'Pair Banker')
                    and factor > 1.0 and bool(result.get('_golden_dice_active'))):
                multipliers = result.get('_golden_dice_multipliers', {})
                try:
                    dice_mult = int(multipliers.get(bet_type, 1))
                except (TypeError, ValueError, AttributeError):
                    dice_mult = 1
                amplified_profit_odds = (factor - 1.0) * max(1, dice_mult)
                factor = 1.0 + round_two_decimals_value(amplified_profit_odds)

            returned = stake * factor
            if factor > 1.0:
                status = 'win'
                profit = returned - stake
                gross_profit += profit
            elif abs(factor - 1.0) < 1e-9:
                status = 'push'
                profit = 0.0
            else:
                status = 'lose'
                profit = 0.0
                lost_stake += stake

            credit += returned
            outcomes.append({
                'key': (bet_type, None),
                'label': cls.DISPLAY_NAMES.get(bet_type, bet_type),
                'status': status,
                'stake': stake,
                'return_factor': factor,
                'profit': profit,
                'return_amount': returned,
            })

        jackpot_win = 0.0
        if mode == 'lucky7' and 'Super 7' in side_factors:
            super_bet = float(bets.get('Super 7', 0.0))
            if super_bet >= 1000:
                p = result['player_hand']
                b = result['banker_hand']
                if (len(p) == 3 and result['player_score'] == 7
                        and all(card[0] == 'Diamond' for card in p)
                        and len(b) == 3 and result['banker_score'] == 6
                        and all(card[0] == 'Spade' for card in b)):
                    jackpot_win = float(jackpot_amount)
                elif (len(p) == 3 and result['player_score'] == 7
                      and all(card[0] in ('Diamond', 'Heart') for card in p)
                      and len(b) == 3 and result['banker_score'] == 6
                      and all(card[0] in ('Spade', 'Club') for card in b)):
                    jackpot_win = float(jackpot_amount) * 0.03

        credit += jackpot_win
        gross_profit += jackpot_win
        return {
            'credit': credit,
            'gross_profit': gross_profit,
            'lost_stake': lost_stake,
            'net': gross_profit - lost_stake,
            'outcomes': outcomes,
            'side_factors': side_factors,
            'jackpot_win': jackpot_win,
        }


class BaccaratBetState:
    def __init__(self):
        self.bets = {}

    def total_at_risk(self):
        return sum(float(value) for value in self.bets.values())

    def current_area_bet(self, bet_type, _param=None):
        return float(self.bets.get(bet_type, 0.0))

    def add_bet(self, bet_type, amount, _param=None):
        if amount <= 0:
            return False
        self.bets[bet_type] = self.current_area_bet(bet_type) + float(amount)
        return True

    def remove_amount(self, bet_type, amount, _param=None):
        current = self.current_area_bet(bet_type)
        removed = min(current, max(0.0, float(amount)))
        left = current - removed
        if left > 1e-9:
            self.bets[bet_type] = left
        else:
            self.bets.pop(bet_type, None)
        return removed

    def clear_area(self, bet_type, _param=None):
        return float(self.bets.pop(bet_type, 0.0))

    def clear_all(self):
        amount = self.total_at_risk()
        self.bets.clear()
        return amount


# -----------------------------------------------------------------------------
# Sicbo-style embedded Canvas interface, adapted for Baccarat
# -----------------------------------------------------------------------------
class BubbleBaccaratGame(tk.Frame):
    # V24: Golden Dice mode (two-die 8/9 trigger, RTP-weighted multipliers, Super Dice);
    # V23: 0.2-second wager/fee chip flights + post-flash winning-chip return;
    # V22: Tie-chip settlement hold + physical casino cut packet swap;
    # V21: Treasure Pot fee-aware total betting, mode-switch bet migration,
    # synchronized golden-badge settlement flashing, and Enter=random casino cut.
    WIDTH = 1150
    HEIGHT = 750

    # V12 layout: column-scrolling bead plate and 70% larger Big Road viewport.
    GAME_X0 = 12
    GAME_X1 = 770
    HISTORY_X0 = 778
    HISTORY_X1 = 1138
    BOARD_INNER_X0 = 22
    BOARD_INNER_X1 = 760

    # Only genuinely mode-specific results belong in the special-data page.
    # Dragon Bonus and Perfect Pair are normal side bets, so they are deliberately
    # excluded from this table and from bead-plate special markers.
    SPECIAL_STATS = {
        'classic': (),
        'tiger': ('Small Tiger', 'Tiger Tie', 'Big Tiger', 'Tiger Pair'),
        'ez': ('Panda 8', 'Divine 9', 'Dragon 7'),
        '2to1': (),
        'lucky7': ('Small Lucky 6', 'Lucky 6', 'Big Lucky 6', 'Lucky 7', 'Super 7'),
        'monkey': ('Monkey 6', 'Monkey Tie', 'Big Monkey', 'Monkey 7', 'Lucky Monkey'),
        'goldendice': (),
        'treasure': (),
        'xxx': (),
    }

    BG = '#17120f'
    PANEL = '#211811'
    PANEL_LINE = '#665240'
    FELT = '#083f38'
    FELT_2 = '#0c5148'
    LINE = '#c3d5ca'
    GOLD = '#e7d36c'
    PLAYER_BLUE = '#3d67d8'
    BANKER_RED = '#d94a4e'
    TIE_GREEN = '#43a665'

    # Result-area flash palette.  The dealing panels flash independently from
    # the betting spots so the winning hand is obvious even with no wager.
    PLAYER_ZONE_BASE = '#102d47'
    PLAYER_ZONE_BLUE = '#2469c9'
    PLAYER_ZONE_LIGHT = '#83cfff'
    BANKER_ZONE_BASE = '#4b1e22'
    BANKER_ZONE_RED = '#c93643'
    BANKER_ZONE_LIGHT = '#ff9ca2'
    TIE_FLASH_DARK = '#23874b'
    TIE_FLASH_LIGHT = '#78e49a'

    MIN_BET = 100.0
    MAX_TABLE_BET = 2_000_000.0
    MAX_RECORDS = 500

    # V23 chip-motion timing. Every wager chip and Treasure/XXX fee chip reaches
    # its destination in 0.2 seconds; winning return chips use the same timing.
    CHIP_MOVE_DURATION_MS = 200
    CHIP_MOVE_STEPS = 10

    # XXX uses probability-only RTP tuning.  RTP is NOT calculated or corrected
    # hand-by-hand.  At the start of each round the game independently chooses:
    #   1) how many distinct golden faces exist this round (4..8), and
    #   2) an integer multiplier (2X..10X) for EACH chosen face.
    # Every one of the 52 card faces is equally likely to become golden.
    # The weights below are fixed long-run probabilities chosen to roughly offset
    # XXX's 50% fee and lower base odds while keeping every round genuinely random.
    # Extreme combinations remain possible: e.g. 8 golden faces can all roll 10X,
    # and 4 golden faces can all roll 2X.
    XXX_COUNT_VALUES = (4, 5, 6, 7, 8)
    # Probabilities: 10%, 20%, 55%, 10%, 5%
    XXX_COUNT_WEIGHTS = (10, 20, 55, 10, 5)

    # XXX 每张黄金牌独立随机倍率
    # 2X / 3X 最常见，之后倍率越高，出现概率逐渐降低。
    XXX_MULTIPLIER_VALUES = (2, 3, 4, 5, 8, 10)

    # 2X 27%
    # 3X 27%
    # 4X 19%
    # 5X 12%
    # 8X  9%
    # 10X 6%
    XXX_MULTIPLIER_WEIGHTS = (30, 24, 19, 12, 9, 6)

    # V24 Golden Dice probability-only RTP tuning.  A multiplier is always drawn
    # but is paid only when the two dice total 8 or 9 (9/36 = 25% trigger rate).
    # Weight means were chosen using standard 8-deck Baccarat frequencies and the
    # mode's 20% fee: Player/Banker ~=98.6%, Tie ~=95%, Pair ~=97% long-run RTP.
    GOLDEN_DICE_MULTIPLIER_VALUES = (2, 3, 5, 10, 20, 50, 100)
    GOLDEN_DICE_MULTIPLIER_WEIGHTS = {
        'Player': (4800, 4800, 300, 60, 25, 10, 5),
        'Banker': (4600, 5000, 300, 60, 25, 10, 5),
        'Tie': (426, 460, 50, 20, 10, 10, 24),
        'Pair Player': (4400, 5200, 300, 60, 25, 10, 5),
        'Pair Banker': (4400, 5200, 300, 60, 25, 10, 5),
    }
    GOLDEN_DICE_BASE_PROFIT_ODDS = {
        'Player': 1.0, 'Banker': 0.95, 'Tie': 5.0,
        'Pair Player': 10.0, 'Pair Banker': 10.0,
    }

    CHIP_SPECS = [
        (100, '#202020', '100'),
        (500, '#d780c0', '500'),
        (1000, '#ab0058', '1K'),
        (5000, '#ba3438', '5K'),
        (10000, '#70439a', '10K'),
        (50000, '#2e7542', '50K'),
        (250000, '#ffffff', '250K'),
    ]
    M_CHIP_COLOR = '#102d47'  # 墨蓝色；金额以 M 显示时使用白字

    MODE_ORDER = ('classic', 'tiger', 'ez', '2to1', 'lucky7', 'monkey', 'goldendice', 'treasure', 'xxx')
    MODE_SHORT = {
        'classic': '经典', 'tiger': '老虎', 'ez': 'EZ', '2to1': '1赔2',
        'lucky7': '幸运7', 'monkey': '猴子', 'goldendice': '黄金骰', 'treasure': '聚宝盆', 'xxx': 'XXX',
    }

    BET_COLORS = {
        'Player': '#345fc4', 'Tie': '#43a665', 'Banker': '#c94349',
        'Dragon P': '#6658a6', 'Dragon B': '#aa5142', 'Perfect Pair': '#b87930',
        'Golden Hunter': '#9b7725', 'Golden Duel': '#8c6a23', 'Super Dice': '#b88720',
        'Pair Player': '#a943a6', 'Any Pair': '#36959b', 'Pair Banker': '#a943a6',
        'Small Tiger': '#b260ad', 'Tiger Tie': '#3e9c52', 'Big Tiger': '#3b9ca6',
        'Tiger': '#ba7730', 'Tiger Pair': '#a943a6',
        'Panda 8': '#d6d6d6', 'Divine 9': '#55a966', 'Dragon 7': '#bb692b',
        'Small Lucky 6': '#b260ad', 'Lucky 6': '#b97732', 'Big Lucky 6': '#3f9aa0',
        'Lucky 7': '#b8a82d', 'Super 7': '#279b70',
        'Monkey 6': '#ba8848', 'Monkey Tie': '#aaa536', 'Big Monkey': '#b76d87',
        'Monkey 7': '#bb692b', 'Lucky Monkey': '#b64c8b',
    }

    def __init__(self, parent, balance=10000, user=None, on_back=None,
                 on_balance_change=None, game_mode='classic'):
        super().__init__(parent, bg=self.BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.root = self
        self.username = user
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.balance = float(balance)
        self.final_balance = float(balance)
        self.summary_mode = 'bet'
        self.last_win_amount = 0.0
        self.last_net = 0.0

        self.game_mode = game_mode if game_mode in self.MODE_ORDER else 'classic'
        self.engine = BaccaratEngine()
        self.bet_state = BaccaratBetState()
        self.selected_chip = 1000.0
        self.undo_stack = []
        self.last_round_bets = []
        self.bet_spots = {}
        self.chip_selector_items = {}
        self.control_buttons = {}
        self.mode_button_items = {}

        self.accept_bets = True
        self.animation_running = False
        self.settlement_running = False
        self.animation_after_ids = []
        # V23 keeps short wager/fee/return chip flights separate from the card
        # animation queue so they can be cancelled cleanly on exit.
        self.chip_motion_after_ids = set()
        self.chip_motion_serial = 0
        self.pending_bet_visual_amounts = {}
        self.settlement_return_animating = False
        self.settlement_return_keys = set()
        self.settlement_after_id = None
        self.reshuffle_confirm_after_id = None
        self.reshuffle_confirm_armed = False
        self.reshuffle_button_rect = None
        self.reshuffle_button_text = None
        self.flash_mode = None
        self.flash_winning_keys = set()
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        self.flash_original_text_colors = {}
        self.pre_deal_bets = None
        self.current_result = None
        self.settlement_flash_step = 0
        # Keep Push wager chips visible until their return animation starts.
        self.settlement_hold_amounts = {}
        self.push_return_amounts = {}
        self.result_panel_flash_winner = None
        self._closing = False

        # Treasure/XXX round state. Treasure uses five unique faces; XXX uses
        # 4-8 unique faces. Duplicate physical copies in the 8-deck shoe may
        # therefore produce repeated matching hits in one hand.
        self.current_golden_cards = []
        self.current_golden_map = {}
        self.treasure_panel_active = False
        self.treasure_panel_images = []
        self.treasure_animation_refs = {}
        self.treasure_panel_card_items = []
        self.treasure_panel_multiplier_items = []
        # Winning Golden Hunter / Golden Duel rule cells flash in sync with
        # their betting area during settlement.  Each entry stores the right-side
        # odds-cell background and odds-text Canvas item for one payable tier.
        self.treasure_panel_rule_cells = {}
        # Golden Dice reuses the same temporary right-side panel lifecycle as
        # Treasure/XXX, but with two dice and five rolling multiplier rows.
        self.golden_dice_objects = [GoldenDice(), GoldenDice()]
        self.current_golden_dice = [1, 1]
        self.golden_dice_active = False
        self.golden_dice_multipliers = {key: 2 for key in self.GOLDEN_DICE_BASE_PROFIT_ODDS}
        self.golden_dice_images = []
        self.golden_dice_panel_items = []
        self.golden_dice_multiplier_text_items = {}
        self.golden_dice_total_text = None
        self.golden_dice_status_text = None
        self.golden_dice_animation_frames_left = 0
        self.golden_dice_animation_delay_ms = 55
        self.bet_fee_state = {}
        self.pre_deal_fee_total = 0.0

        self.history_panel_mode = 'roads'
        # V12: Big Road is a 50-column logical board viewed through a
        # horizontally scrollable window.  New results follow the right edge
        # until the player manually moves the scrollbar.
        self.big_road_scroll_col = 0
        self.big_road_auto_follow = True
        self.big_road_virtual_cols = 50
        # V12: 14 visible columns makes each Big Road cell ~71% larger than V11's 24-column viewport.
        self.big_road_view_cols = 14
        self.runtime_json_dir = self.get_runtime_json_dir()
        # V14: shoe state, current-shoe finished hands, and lifetime statistics
        # live in ONE JSON document.  Only the two temporary sections are reset
        # when the player cuts a new shoe; statistic_data is never deleted.
        self.runtime_data_file = os.path.join(self.runtime_json_dir, 'Baccarat.json')
        self.legacy_temp_data_file = os.path.join(self.runtime_json_dir, 'temp_data.json')
        self.legacy_temp_finish_data_file = os.path.join(self.runtime_json_dir, 'temp_finish_data.json')
        self.legacy_statistic_data_file = os.path.join(self.runtime_json_dir, 'statistic_data.json')
        self.runtime_store = self.load_runtime_store()
        self.history_file = self.runtime_data_file
        self.shoe_resumed = self.load_temp_data()
        self.history_store = self.load_history_store()
        self.history_data = self.history_records_from_store()
        self.statistic_data = self.load_statistic_data()
        self.treasure_pot_amount = 0.0  # V19: current-round fee only; never persisted

        # Bead Plate text can be toggled between result labels/special marks and
        # the winning point value by clicking anywhere on the bead grid.
        self.bead_show_scores = False

        self.jackpot_file = self.get_jackpot_file()
        self.jackpot_amount = self.load_jackpot()

        # Prefer the original Baccarat external card artwork. If the project
        # assets are unavailable, draw the temporary V4-style cards instead.
        self.external_card_images = {}
        self.external_card_images_rotated = {}
        self.external_back_image = None
        self.card_asset_dir = None
        self.golden_card_pil = {}
        self.golden_card_images = {}
        self.golden_card_images_rotated = {}
        self.load_original_card_assets()
        self.load_golden_card_assets()
        self.create_golden_dice_images()

        top = self.winfo_toplevel()
        try:
            top.geometry('1150x750+50+10')
            top.resizable(False, False)
        except tk.TclError:
            pass

        top.bind('<Return>', self.handle_enter_deal)
        self.bind('<Escape>', lambda _event: self.exit_game())

        self.create_ui()
        self.select_chip(self.selected_chip)
        self.update_display()
        if not self.shoe_resumed:
            self.after(180, lambda: self.start_new_shoe_cut(False))

    # ------------------------------------------------------------------ UI base
    def create_ui(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=self.BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_rectangle(0, 0, self.WIDTH, self.HEIGHT,
                                     fill=self.BG, outline='', tags='static')
        self.draw_history_panel()
        self.draw_animation_panel()
        self.draw_board()
        self.draw_bottom_controls()
        self.canvas.bind('<Button-1>', self._handle_bead_click, add='+')

    def draw_history_panel(self):
        """Right-side history panel with Roads/Data tabs."""
        c = self.canvas
        x0, y0, x1, y1 = self.HISTORY_X0, 4, self.HISTORY_X1, 620
        c.create_rectangle(x0, y0, x1, y1, fill=self.PANEL,
                           outline=self.PANEL_LINE, width=2, tags='static')
        self.history_panel_bounds = (x0, y0, x1, y1)
        c.create_text((x0 + x1) / 2, 18, text='历史记录',
                      font=('Arial', 15, 'bold'), fill='#d4c3a9', tags='static')

        self.history_tab_items = {}
        tab_y0, tab_y1 = 34, 62
        mid = (x0 + x1) / 2
        for mode, bx0, bx1, label in (
            ('roads', x0 + 8, mid - 4, '道路'),
            ('data', mid + 4, x1 - 8, '数据'),
        ):
            tag = f'history_tab_{mode}'
            rect = c.create_rectangle(bx0, tab_y0, bx1, tab_y1, fill='#30271f',
                                      outline='#8d765e', width=1,
                                      tags=('static', tag))
            txt = c.create_text((bx0 + bx1) / 2, (tab_y0 + tab_y1) / 2,
                                text=label, font=('Arial', 10, 'bold'),
                                fill='#d9c8af', tags=('static', tag))
            self.history_tab_items[mode] = (rect, txt)
            c.tag_bind(tag, '<Button-1>', lambda _e, m=mode: self.switch_history_panel(m))
            c.tag_bind(tag, '<Enter>', lambda _e: c.configure(cursor='hand2'))
            c.tag_bind(tag, '<Leave>', lambda _e: c.configure(cursor=''))
        self._draw_history_content()

    def switch_history_panel(self, mode):
        if mode not in ('roads', 'data') or mode == self.history_panel_mode:
            return
        self.history_panel_mode = mode
        if mode == 'roads':
            self.big_road_auto_follow = True
        self._draw_history_content()
        self.update_history_table()

    def _update_history_tab_style(self):
        for mode, (rect, txt) in getattr(self, 'history_tab_items', {}).items():
            selected = mode == self.history_panel_mode
            self.canvas.itemconfigure(rect,
                                      fill='#a57e38' if selected else '#30271f',
                                      outline='#f2d77c' if selected else '#8d765e',
                                      width=2 if selected else 1)
            self.canvas.itemconfigure(txt, fill='#111111' if selected else '#d9c8af')

    def _draw_history_content(self):
        self.canvas.delete('history_panel_content')
        self.canvas.delete('history_dynamic')
        self._update_history_tab_style()
        if self.history_panel_mode == 'data':
            self._draw_data_page()
        else:
            self._draw_roads_page()

    def _draw_roads_page(self):
        """Draw the V14 road page with symmetric section boundaries.

        Layout:
          1) Big Road: logical 50 x 6 board with a horizontal scrollbar.
          2) Big Eye Boy / Cockroach Pig: equal left/right halves.
          3) Bead Plate: 12 x 6, using cells 25% smaller than V10.
          4) Small Road / Next-hand indicator: 5/8 and 3/8 widths.

        Road-name captions are intentionally omitted from the grid area.
        """
        c = self.canvas
        panel_x0, panel_x1 = 786, 1130
        panel_w = panel_x1 - panel_x0

        # ----- Row 1: Big Road.  The logical board is 50 columns wide, while
        # a 14-column viewport enlarges each Big Road mark by about 70% vs V11.
        big_x0 = panel_x0
        big_y0 = 72
        big_cell = panel_w / self.big_road_view_cols
        self.road_geometries = {
            'big': (big_x0, big_y0, big_cell, 6, self.big_road_view_cols),
        }
        self._draw_road_grid(*self.road_geometries['big'])
        self._draw_big_road_scrollbar(big_x0, big_y0 + 6 * big_cell + 5, panel_w)

        # ----- Row 2: exact equal halves, with one centred gutter.
        row2_y = 240
        gutter = 6
        half_w = (panel_w - gutter) / 2
        derived_cols = 14
        derived_cell = half_w / derived_cols
        self.road_geometries['eye'] = (
            panel_x0, row2_y, derived_cell, 6, derived_cols)
        self.road_geometries['cockroach'] = (
            panel_x0 + half_w + gutter, row2_y, derived_cell, 6, derived_cols)
        self._draw_road_grid(*self.road_geometries['eye'])
        self._draw_road_grid(*self.road_geometries['cockroach'])

        # ----- Row 3: Bead Plate.  V10 used 36 px cells; V11 uses 27 px
        # cells (25% smaller) and expands the logical width from 9 to 12.
        bead_cell = 27
        bead_cols = 12
        bead_w = bead_cell * bead_cols
        bead_x0 = panel_x0 + (panel_w - bead_w) / 2
        bead_y0 = 320
        self.road_geometries['bead'] = (bead_x0, bead_y0, bead_cell, 6, bead_cols)
        self._draw_road_grid(*self.road_geometries['bead'])

        # ----- Row 4: Small Road 5/8 | Next indicator 3/8.
        row4_y = 490
        row4_h = 66
        row4_gutter = 6
        usable = panel_w - row4_gutter
        small_w = usable * 5 / 8
        next_w = usable - small_w
        small_cols = 20
        small_cell = small_w / small_cols
        self.road_geometries['small'] = (
            panel_x0, row4_y, small_cell, 6, small_cols)
        self._draw_road_grid(*self.road_geometries['small'])

        nx0 = panel_x0 + small_w + row4_gutter
        nx1 = panel_x1
        ny0, ny1 = row4_y, row4_y + row4_h
        c.create_rectangle(nx0, ny0, nx1, ny1, fill='#15110f', outline='#7c6754',
                           width=1, tags='history_panel_content')
        # No "大眼仔 / 小路 / 蟑螂路" explanatory labels.  Only Player and
        # Banker headers remain; the three symbol rows follow the standard order.
        mid_x = (nx0 + nx1) / 2
        header_h = 18
        c.create_line(mid_x, ny0, mid_x, ny1, fill='#514338',
                      tags='history_panel_content')
        c.create_line(nx0, ny0 + header_h, nx1, ny0 + header_h,
                      fill='#7c6754', tags='history_panel_content')
        body_h = ny1 - ny0 - header_h
        row_h = body_h / 3
        for i in range(1, 3):
            y = ny0 + header_h + i * row_h
            c.create_line(nx0, y, nx1, y, fill='#514338', tags='history_panel_content')
        c.create_text((nx0 + mid_x) / 2, ny0 + header_h / 2, text='闲',
                      font=('Arial', 8, 'bold'), fill=self.PLAYER_BLUE,
                      tags='history_panel_content')
        c.create_text((mid_x + nx1) / 2, ny0 + header_h / 2, text='庄',
                      font=('Arial', 8, 'bold'), fill=self.BANKER_RED,
                      tags='history_panel_content')
        self.next_indicator_geometry = {
            'x0': nx0, 'x1': nx1, 'mid_x': mid_x,
            'top': ny0 + header_h, 'row_h': row_h,
        }

        # Explain the asterisk used by main-bet odds.  Keep this directly under
        # the Small Road in white so it is visible without adding another panel.
        self.road_asterisk_note_item = c.create_text(
            (panel_x0 + panel_x1) / 2, row4_y + row4_h + 5,
            anchor='n', width=panel_w - 8,
            text=self._asterisk_note_text(),
            font=('Arial', 28, 'bold'), fill='white', justify='center',
            tags='history_panel_content'
        )

    def _asterisk_note_text(self):
        """Return the current mode's exact meaning for the odds asterisk."""
        notes = {
            'classic': '* 无特殊主注',
            'tiger': '* 庄6半赔',
            'ez': '* 庄三张7点退本',
            '2to1': '* 三张8/9赔2:1',
            'lucky7': '* 庄6半赔',
            'monkey': '* 无特殊主注',
            'goldendice': '骰子8/9激活赔率',
            'treasure': '黄金牌增加赔率',
            'xxx': '黄金牌增加赔率',
        }
        return notes.get(self.game_mode, '* 特殊主注')

    def _draw_big_road_scrollbar(self, x0, y0, width):
        """Draw a functional horizontal scrollbar for the 50-column Big Road."""
        c = self.canvas
        self.big_road_scroll_track = (x0, y0, x0 + width, y0 + 10)
        c.create_rectangle(*self.big_road_scroll_track, fill='#30271f',
                           outline='#7c6754', width=1,
                           tags=('history_panel_content', 'bigroad_scroll'))
        # The thumb represents the visible fraction of the 50-column logical road.
        ratio = min(1.0, self.big_road_view_cols / self.big_road_virtual_cols)
        thumb_w = max(28, width * ratio)
        self.big_road_scroll_thumb_width = thumb_w
        self.big_road_scroll_thumb = c.create_rectangle(
            x0, y0 + 1, x0 + thumb_w, y0 + 9,
            fill='#a57e38', outline='#f2d77c', width=1,
            tags=('history_panel_content', 'bigroad_scroll'))
        c.tag_bind('bigroad_scroll', '<Button-1>', self._set_big_road_scroll_from_event)
        c.tag_bind('bigroad_scroll', '<B1-Motion>', self._set_big_road_scroll_from_event)
        c.tag_bind('bigroad_scroll', '<Enter>', lambda _e: c.configure(cursor='sb_h_double_arrow'))
        c.tag_bind('bigroad_scroll', '<Leave>', lambda _e: c.configure(cursor=''))
        self._update_big_road_scroll_thumb()

    def _set_big_road_scroll_from_event(self, event):
        track = getattr(self, 'big_road_scroll_track', None)
        if not track:
            return
        x0, _y0, x1, _y1 = track
        width = x1 - x0
        thumb_w = getattr(self, 'big_road_scroll_thumb_width', width)
        movable = max(1.0, width - thumb_w)
        # Centre the thumb under the pointer for both click and drag.
        thumb_left = min(max(event.x - thumb_w / 2, x0), x1 - thumb_w)
        fraction = (thumb_left - x0) / movable
        max_start = max(0, self.big_road_virtual_cols - self.big_road_view_cols)
        self.big_road_scroll_col = int(round(fraction * max_start))
        self.big_road_auto_follow = False
        self._update_big_road_scroll_thumb()
        self.update_history_table()

    def _update_big_road_scroll_thumb(self):
        if not getattr(self, 'big_road_scroll_thumb', None):
            return
        track = getattr(self, 'big_road_scroll_track', None)
        if not track:
            return
        x0, y0, x1, _y1 = track
        width = x1 - x0
        thumb_w = getattr(self, 'big_road_scroll_thumb_width', width)
        max_start = max(0, self.big_road_virtual_cols - self.big_road_view_cols)
        start = min(max(0, int(self.big_road_scroll_col)), max_start)
        fraction = (start / max_start) if max_start else 0.0
        left = x0 + fraction * max(0.0, width - thumb_w)
        try:
            self.canvas.coords(self.big_road_scroll_thumb,
                               left, y0 + 1, left + thumb_w, y0 + 9)
        except tk.TclError:
            pass

    def _draw_stats_grid(self, x0, y0, x1, y1, rows):
        c = self.canvas
        value_x = x1 - 92
        c.create_rectangle(x0, y0, x1, y1, fill='#15110f', outline='#7c6754',
                           width=1, tags='history_panel_content')
        c.create_line(value_x, y0, value_x, y1, fill='#514338',
                      tags='history_panel_content')
        row_h = (y1 - y0) / max(1, rows)
        for row in range(1, rows):
            y = y0 + row * row_h
            c.create_line(x0, y, x1, y, fill='#3e352f', tags='history_panel_content')
        return {'x0': x0, 'x1': x1, 'value_x': value_x, 'top': y0, 'row_h': row_h}

    def _draw_data_page(self):
        c = self.canvas
        x0, x1 = 786, 1130
        c.create_text(x0, 82, anchor='w', text='本轮统计',
                      font=('Arial', 12, 'bold'), fill=self.GOLD,
                      tags='history_panel_content')
        self.base_stats_geometry = self._draw_stats_grid(x0, 98, x1, 306, 6)

        mode_name = self.MODE_SHORT.get(self.game_mode, self.game_mode)
        self.history_special_title = c.create_text(
            x0, 334, anchor='w', text=f'{mode_name}特殊数据',
            font=('Arial', 12, 'bold'), fill=self.GOLD,
            tags='history_panel_content')
        # Mode-specific special data never exceeds five entries.  Keep exactly
        # five rows and reuse the old sixth-row space for a guarded reshuffle.
        self.special_stats_geometry = self._draw_stats_grid(x0, 350, x1, 550, 5)
        self._draw_manual_reshuffle_button(x0, 558, x1, 590)

    def _draw_manual_reshuffle_button(self, x0, y0, x1, y1):
        c = self.canvas
        tag = 'manual_reshuffle_button'
        label = '确认再按' if self.reshuffle_confirm_armed else '重新洗牌'
        armed = self.reshuffle_confirm_armed
        self.reshuffle_button_rect = c.create_rectangle(
            x0, y0, x1, y1,
            fill='#d8bd4b' if armed else '#30271f',
            outline='#f2d77c' if armed else '#8d765e', width=2 if armed else 1,
            tags=('history_panel_content', tag))
        self.reshuffle_button_text = c.create_text(
            (x0 + x1) / 2, (y0 + y1) / 2, text=label,
            font=('Arial', 11, 'bold'), fill='#15110d' if armed else '#e7d36c',
            tags=('history_panel_content', tag))
        c.tag_bind(tag, '<Button-1>', self._manual_reshuffle_click)
        c.tag_bind(tag, '<Enter>', lambda _e: c.configure(cursor='hand2'))
        c.tag_bind(tag, '<Leave>', lambda _e: c.configure(cursor=''))

    def _set_manual_reshuffle_button_state(self):
        label = '确认再按' if self.reshuffle_confirm_armed else '重新洗牌'
        armed = self.reshuffle_confirm_armed
        try:
            if self.reshuffle_button_rect is not None:
                self.canvas.itemconfigure(
                    self.reshuffle_button_rect,
                    fill='#d8bd4b' if armed else '#30271f',
                    outline='#f2d77c' if armed else '#8d765e',
                    width=2 if armed else 1)
            if self.reshuffle_button_text is not None:
                self.canvas.itemconfigure(
                    self.reshuffle_button_text, text=label,
                    fill='#15110d' if armed else '#e7d36c')
        except tk.TclError:
            pass

    def _reset_manual_reshuffle_confirm(self):
        self.reshuffle_confirm_after_id = None
        self.reshuffle_confirm_armed = False
        self._set_manual_reshuffle_button_state()

    def _manual_reshuffle_click(self, _event=None):
        if self._closing or self.animation_running or self.settlement_running or not self.accept_bets:
            return 'break'

        if not self.reshuffle_confirm_armed:
            self.reshuffle_confirm_armed = True
            self._set_manual_reshuffle_button_state()
            if self.reshuffle_confirm_after_id is not None:
                try:
                    self.after_cancel(self.reshuffle_confirm_after_id)
                except (tk.TclError, ValueError):
                    pass
            # The second click must arrive within ten seconds.
            self.reshuffle_confirm_after_id = self.after(10_000, self._reset_manual_reshuffle_confirm)
            return 'break'

        # Confirmed second click inside the ten-second window.
        if self.reshuffle_confirm_after_id is not None:
            try:
                self.after_cancel(self.reshuffle_confirm_after_id)
            except (tk.TclError, ValueError):
                pass
            self.reshuffle_confirm_after_id = None
        self.reshuffle_confirm_armed = False
        self._set_manual_reshuffle_button_state()
        self._perform_manual_reshuffle()
        return 'break'

    def _perform_manual_reshuffle(self):
        # Return any un-dealt wagers/fees before replacing the shoe, matching
        # the automatic end-of-shoe path so a manual reshuffle cannot consume
        # a pending stake.
        outstanding = self.bet_state.clear_all()
        fee_refund = sum(float(v) for v in self.bet_fee_state.values())
        self.bet_fee_state.clear()
        if outstanding > 0 or fee_refund > 0:
            self.balance += outstanding + fee_refund
            if fee_refund > 0:
                self.treasure_pot_amount = max(0.0, self.treasure_pot_amount - fee_refund)
        self.undo_stack.clear()
        self.update_display()
        self.start_new_shoe_cut(True)

    def _draw_road_grid(self, x0, y0, cell, rows, cols):
        c = self.canvas
        x1, y1 = x0 + cols * cell, y0 + rows * cell
        c.create_rectangle(x0, y0, x1, y1, fill='#f3efe7', outline='#8d8377',
                           width=1, tags='history_panel_content')
        for r in range(1, rows):
            y = y0 + r * cell
            c.create_line(x0, y, x1, y, fill='#d2cbc1', tags='history_panel_content')
        for col in range(1, cols):
            x = x0 + col * cell
            c.create_line(x, y0, x, y1, fill='#d2cbc1', tags='history_panel_content')

    @staticmethod
    def _place_road_sequence(sequence, rows=6):
        """Lay a logical streak sequence onto a six-row baccarat road.

        ``sequence`` contains ``(value, payload)`` pairs.  Equal consecutive
        values continue downward until the next cell is blocked or the sixth
        row is reached; the streak then turns right on the same row (the
        standard dragon-tail rule).  A changed value starts a new logical
        column at the top.
        """
        placed = []
        occupied = set()
        last_value = None
        row = col = 0
        streak_start_col = -1

        for value, payload in sequence:
            if last_value is None:
                streak_start_col = 0
                row, col = 0, 0
            elif value == last_value:
                below = (row + 1, col)
                if row + 1 < rows and below not in occupied:
                    row += 1
                else:
                    # Dragon tail, or a collision with an earlier tail.
                    next_col = col + 1
                    while (row, next_col) in occupied:
                        next_col += 1
                    col = next_col
            else:
                # A new Player/Banker (or red/blue derived-road) streak starts
                # one logical column to the right of the previous streak.
                streak_start_col += 1
                row, col = 0, streak_start_col
                while (row, col) in occupied:
                    col += 1
                    streak_start_col = col

            occupied.add((row, col))
            placed.append({
                'row': row, 'col': col, 'value': value, 'payload': payload
            })
            last_value = value

        return placed

    def _build_big_road(self, records):
        """Build the standard Baccarat Big Road from chronological hands.

        Ties never advance the road.  They are drawn as green diagonal marks
        on the latest Player/Banker cell.  If a shoe starts with ties, those
        ties occupy the top-left cell until the first non-tie result arrives.
        Pair flags from a Tie hand are also retained on that same Big-Road
        cell, matching the normal scoreboard convention.
        """
        sequence = []
        pending_ties = 0
        pending_player_pair = False
        pending_banker_pair = False

        for record in records:
            winner = record.get('winner')
            player_pair = bool(record.get('player_pair', False))
            banker_pair = bool(record.get('banker_pair', False))

            if winner == 'Tie':
                if sequence:
                    payload = sequence[-1][1]
                    payload['ties'] += 1
                    payload['player_pair'] = payload['player_pair'] or player_pair
                    payload['banker_pair'] = payload['banker_pair'] or banker_pair
                else:
                    pending_ties += 1
                    pending_player_pair = pending_player_pair or player_pair
                    pending_banker_pair = pending_banker_pair or banker_pair
                continue

            if winner not in ('Player', 'Banker'):
                continue

            payload = {
                'record': record,
                'ties': pending_ties,
                'player_pair': player_pair or pending_player_pair,
                'banker_pair': banker_pair or pending_banker_pair,
            }
            pending_ties = 0
            pending_player_pair = False
            pending_banker_pair = False
            sequence.append((winner, payload))

        cells = self._place_road_sequence(sequence)

        # A shoe may currently contain only one or more opening ties.  Standard
        # electronic roads show the green tie slash in the top-left cell even
        # before the first Player/Banker circle exists.
        if not cells and pending_ties:
            return [{
                'row': 0, 'col': 0, 'value': 'TieOnly',
                'payload': {
                    'record': None, 'ties': pending_ties,
                    'player_pair': pending_player_pair,
                    'banker_pair': pending_banker_pair,
                    'tie_only': True,
                },
            }]
        return cells

    def _record_specials_for_mode(self, record, mode):
        by_mode = record.get('special_by_mode', {})
        if isinstance(by_mode, dict):
            values = by_mode.get(mode, [])
            if isinstance(values, list):
                return values
        # Backward compatibility with older records that only stored the mode
        # in which the hand was originally played.
        if record.get('mode', 'classic') == mode:
            values = record.get('specials', [])
            return values if isinstance(values, list) else []
        return []

    def _special_marker(self, record):
        """Compact marker used by the Bead Plate only.

        The marker is intentionally mode-specific.  Switching from Lucky 7 to
        Tiger therefore re-renders the same historical hand with the marker
        for the newly selected mode instead of leaking another mode's symbol.
        """
        selected = set(self._record_specials_for_mode(record, self.game_mode))
        priority = (
            ('Super 7', '7'), ('Lucky 7', '7'), ('Dragon 7', '7'),
            ('Big Lucky 6', '6'), ('Small Lucky 6', '6'), ('Lucky 6', '6'),
            ('Big Tiger', '大'), ('Small Tiger', '小'), ('Tiger Tie', '虎'),
            # Pair outcomes never replace the bead text; pair dots are enough.
            ('Panda 8', '8'),
            ('Big Monkey', '猴'), ('Monkey 7', '7'), ('Monkey 6', '6'),
            ('Lucky Monkey', '猴'),
        )
        for name, marker in priority:
            if name in selected:
                return marker
        return ''

    def _derive_road(self, records, offset):
        """Build Big-Eye Boy / Small Road / Cockroach Pig correctly.

        ``offset`` is 1, 2 or 3 respectively.  The calculation uses the
        *logical* Big-Road streak columns with unlimited depth, not the
        six-row rendered cells.  This distinction is essential when a streak
        forms a dragon tail.

        For a new Big-Road column, compare the depth of the immediately
        previous streak with the streak ``offset + 1`` columns back.  For a
        continuation within the same streak, compare the two cells reached by
        moving ``offset`` logical columns left and then one row up.  In the
        unlimited-depth representation that comparison is blue only when the
        reference streak length is exactly one less than the current streak
        length; otherwise it is red.
        """
        if offset not in (1, 2, 3):
            raise ValueError('derived-road offset must be 1, 2 or 3')

        streaks = []
        derived_sequence = []

        for record in records:
            winner = record.get('winner')
            if winner not in ('Player', 'Banker'):
                # Ties do not create marks in any derived road.
                continue

            if not streaks or streaks[-1]['winner'] != winner:
                streaks.append({'winner': winner, 'length': 1})
                column = len(streaks) - 1

                # Big Eye starts on the first hand of column 3 when column 2
                # has only one hand; Small Road on column 4; Cockroach on 5.
                if column < offset + 1:
                    continue

                previous_depth = streaks[column - 1]['length']
                comparison_depth = streaks[column - offset - 1]['length']
                color = 'red' if previous_depth == comparison_depth else 'blue'
            else:
                streaks[-1]['length'] += 1
                column = len(streaks) - 1
                current_depth = streaks[-1]['length']

                # The other possible starting point is row 2 of the minimum
                # required column: col2 for Big Eye, col3 for Small, col4 for
                # Cockroach.
                if column < offset:
                    continue

                reference_depth = streaks[column - offset]['length']
                color = 'blue' if reference_depth == current_depth - 1 else 'red'

            derived_sequence.append((color, {'source': record}))

        return self._place_road_sequence(derived_sequence)

    def _visible_road_cells(self, cells, cols):
        if not cells:
            return [], 0
        max_col = max(cell['col'] for cell in cells)
        shift = max(0, max_col - cols + 1)
        return [cell for cell in cells if shift <= cell['col'] < shift + cols], shift

    def _handle_bead_click(self, event):
        """Toggle Bead Plate labels between result text and winning points."""
        if getattr(self, 'history_panel_mode', None) != 'roads':
            return
        geometry = getattr(self, 'road_geometries', {}).get('bead')
        if not geometry:
            return
        x0, y0, cell, rows, cols = geometry
        x1, y1 = x0 + cols * cell, y0 + rows * cell
        if x0 <= event.x <= x1 and y0 <= event.y <= y1:
            self.bead_show_scores = not bool(getattr(self, 'bead_show_scores', False))
            self.update_history_table()

    def _draw_bead_plate(self, records):
        x0, y0, cell, rows, cols = self.road_geometries['bead']
        capacity = rows * cols

        # V12: a real bead plate scrolls by a complete 6-hand column, not by
        # one hand.  With a 12 x 6 board, hands 1..72 fill the board.  Hand 73
        # hides hands 1..6, shifts hands 7..72 one column left, and enters at
        # the top of the newest column.  The next shift occurs at hand 79.
        total = len(records)
        if total <= capacity:
            start = 0
        else:
            overflow = total - capacity
            hidden_columns = (overflow + rows - 1) // rows  # ceil(overflow / 6)
            start = hidden_columns * rows
        visible = records[start:start + capacity]

        for index, record in enumerate(visible):
            row = index % rows
            col = index // rows
            cx = x0 + col * cell + cell / 2
            cy = y0 + row * cell + cell / 2
            winner = record.get('winner')
            color = self.result_color(winner)
            radius = max(6, cell * 0.39)
            self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                    fill=color, outline='#ffffff', width=1,
                                    tags='history_dynamic')
            if getattr(self, 'bead_show_scores', False):
                if winner == 'Player':
                    text = str(int(record.get('player_score', 0)))
                elif winner == 'Banker':
                    text = str(int(record.get('banker_score', 0)))
                elif winner == 'Tie':
                    # A tie has the same score on both sides; use that tied value.
                    text = str(int(record.get('player_score', record.get('banker_score', 0))))
                else:
                    text = ''
            else:
                marker = self._special_marker(record)
                text = marker or {'Player': '闲', 'Banker': '庄', 'Tie': '和'}.get(winner, '')
            self.canvas.create_text(cx, cy, text=text, font=('Arial', 12, 'bold'),
                                    fill='white', tags='history_dynamic')

            # Pair markers remain dots only (never text), with stronger colour,
            # a larger radius and a white rim so they remain visible on the bead.
            pair_r = max(4.0, cell * 0.155)
            inset = radius * 0.76
            if record.get('player_pair'):
                px, py = cx - inset, cy - inset
                self.canvas.create_oval(px - pair_r, py - pair_r, px + pair_r, py + pair_r,
                                        fill='#145dff', outline='#ffffff', width=2,
                                        tags='history_dynamic')
            if record.get('banker_pair'):
                px, py = cx + inset, cy + inset
                self.canvas.create_oval(px - pair_r, py - pair_r, px + pair_r, py + pair_r,
                                        fill='#ff2238', outline='#ffffff', width=2,
                                        tags='history_dynamic')

    def _draw_big_road(self, cells):
        x0, y0, cell, rows, _view_cols = self.road_geometries['big']
        virtual_cols = self.big_road_virtual_cols
        view_cols = self.big_road_view_cols

        # A shoe virtually owns 50 columns.  In the unlikely event the logical
        # road exceeds 50 columns, retain the newest 50 rather than drawing over
        # neighbouring panels.
        max_data_col = max((item['col'] for item in cells), default=-1)
        base_col = max(0, max_data_col - virtual_cols + 1)
        local_cells = []
        for item in cells:
            local_col = item['col'] - base_col
            if 0 <= local_col < virtual_cols:
                copied = dict(item)
                copied['local_col'] = local_col
                local_cells.append(copied)

        latest_local = max((item['local_col'] for item in local_cells), default=0)
        max_start = max(0, virtual_cols - view_cols)
        if self.big_road_auto_follow:
            self.big_road_scroll_col = min(max_start, max(0, latest_local - view_cols + 1))
        else:
            self.big_road_scroll_col = min(max_start, max(0, int(self.big_road_scroll_col)))
        start_col = self.big_road_scroll_col
        self._update_big_road_scroll_thumb()

        for item in local_cells:
            if not (start_col <= item['local_col'] < start_col + view_cols):
                continue
            row = item['row']
            col = item['local_col'] - start_col
            cx = x0 + col * cell + cell / 2
            cy = y0 + row * cell + cell / 2
            payload = item['payload']
            ties = int(payload.get('ties', 0))
            winner = item['value']
            radius = cell * 0.37

            if winner in ('Player', 'Banker'):
                color = self.PLAYER_BLUE if winner == 'Player' else self.BANKER_RED
                self.canvas.create_oval(
                    cx - radius, cy - radius, cx + radius, cy + radius,
                    fill='', outline=color, width=2, tags='history_dynamic')

            if ties:
                self.canvas.create_line(
                    cx - radius + 1, cy + radius - 1,
                    cx + radius - 1, cy - radius + 1,
                    fill=self.TIE_GREEN, width=2, tags='history_dynamic')
                if ties > 1:
                    self.canvas.create_text(
                        cx + radius * 0.45, cy - radius * 0.45, text=str(ties),
                        font=('Arial', 6, 'bold'), fill=self.TIE_GREEN,
                        tags='history_dynamic')

            # Big Road has no special-play marker; only standard pair dots.
            pair_r = max(1.7, cell * 0.12)
            if payload.get('player_pair'):
                px, py = cx - radius * 0.78, cy - radius * 0.78
                self.canvas.create_oval(px-pair_r, py-pair_r, px+pair_r, py+pair_r,
                                        fill=self.PLAYER_BLUE, outline='',
                                        tags='history_dynamic')
            if payload.get('banker_pair'):
                px, py = cx + radius * 0.78, cy + radius * 0.78
                self.canvas.create_oval(px-pair_r, py-pair_r, px+pair_r, py+pair_r,
                                        fill=self.BANKER_RED, outline='',
                                        tags='history_dynamic')

    def _draw_derived_road(self, key, cells, style):
        x0, y0, cell, rows, cols = self.road_geometries[key]
        visible, shift = self._visible_road_cells(cells, cols)
        for item in visible:
            row, col = item['row'], item['col'] - shift
            cx = x0 + col * cell + cell / 2
            cy = y0 + row * cell + cell / 2
            color = '#d83838' if item['value'] == 'red' else '#2766c5'
            radius = max(2.5, cell * 0.32)
            if style == 'ring':
                self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                        fill='', outline=color, width=2, tags='history_dynamic')
            elif style == 'dot':
                # Small Road uses a true solid circle (not a diamond/square).
                dot_r = max(3.0, cell * 0.30)
                self.canvas.create_oval(cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r,
                                        fill=color, outline=color, width=1,
                                        tags='history_dynamic')
            else:
                self.canvas.create_line(cx - radius, cy + radius, cx + radius, cy - radius,
                                        fill=color, width=2, tags='history_dynamic')

    def _draw_round_statistics(self, records):
        c = self.canvas
        counts = {'Player': 0, 'Banker': 0, 'Tie': 0, 'player_pair': 0, 'banker_pair': 0}
        for record in records:
            winner = record.get('winner')
            if winner in ('Player', 'Banker', 'Tie'):
                counts[winner] += 1
            if record.get('player_pair'):
                counts['player_pair'] += 1
            if record.get('banker_pair'):
                counts['banker_pair'] += 1

        geo = self.base_stats_geometry
        base_items = [
            ('总局', len(records)), ('闲', counts['Player']), ('庄', counts['Banker']),
            ('和', counts['Tie']), ('闲对', counts['player_pair']), ('庄对', counts['banker_pair']),
        ]
        base_colors = ['#d4c3a9', self.PLAYER_BLUE, self.BANKER_RED,
                       self.TIE_GREEN, '#77a2ff', '#ff898d']
        for row, ((label, value), color) in enumerate(zip(base_items, base_colors)):
            y = geo['top'] + geo['row_h'] * (row + 0.5)
            c.create_text(geo['x0'] + 10, y, anchor='w', text=label,
                          font=('Arial', 10, 'bold'), fill=color, tags='history_dynamic')
            c.create_text((geo['value_x'] + geo['x1']) / 2, y, text=str(value),
                          font=('Arial', 11, 'bold'), fill='#f2eadf', tags='history_dynamic')

        # Every completed hand is evaluated against every game mode when saved,
        # so switching modes reveals that mode's special results even if the hand
        # was originally dealt while another mode was selected.
        special_counts = {}
        for record in records:
            for name in self._record_specials_for_mode(record, self.game_mode):
                special_counts[name] = special_counts.get(name, 0) + 1

        mode_name = self.MODE_SHORT.get(self.game_mode, self.game_mode)
        if getattr(self, 'history_special_title', None):
            try:
                c.itemconfigure(self.history_special_title, text=f'{mode_name}特殊数据')
            except tk.TclError:
                pass
        specials = self.SPECIAL_STATS.get(self.game_mode, ())
        short_names = {
            'Small Tiger': '小老虎', 'Tiger Tie': '老虎和', 'Big Tiger': '大老虎',
            'Tiger Pair': '虎对子', 'Panda 8': '熊猫8', 'Divine 9': '神之9',
            'Dragon 7': '金龙7', 'Small Lucky 6': '小幸运6', 'Lucky 6': '幸运6',
            'Big Lucky 6': '大幸运6', 'Lucky 7': '幸运7', 'Super 7': '超级7',
            'Monkey 6': '猴6', 'Monkey Tie': '猴和', 'Big Monkey': '大猴',
            'Monkey 7': '猴7', 'Lucky Monkey': '幸运猴',
        }
        geo = self.special_stats_geometry
        if not specials:
            y = geo['top'] + geo['row_h'] * 0.5
            c.create_text(geo['x0'] + 10, y, anchor='w', text='无特殊数据',
                          font=('Arial', 10, 'bold'), fill='#8e877f', tags='history_dynamic')
            c.create_text((geo['value_x'] + geo['x1']) / 2, y, text='—',
                          font=('Arial', 11, 'bold'), fill='#8e877f', tags='history_dynamic')
        else:
            for row in range(5):
                y = geo['top'] + geo['row_h'] * (row + 0.5)
                if row < len(specials):
                    name = specials[row]
                    c.create_text(geo['x0'] + 10, y, anchor='w', text=short_names.get(name, name),
                                  font=('Arial', 9, 'bold'), fill='#e7dfd5', tags='history_dynamic')
                    c.create_text((geo['value_x'] + geo['x1']) / 2, y,
                                  text=str(special_counts.get(name, 0)),
                                  font=('Arial', 11, 'bold'), fill='#f2eadf', tags='history_dynamic')

    def update_history_table(self):
        if not hasattr(self, 'canvas'):
            return
        if getattr(self, 'treasure_panel_active', False):
            return
        self.canvas.delete('history_dynamic')
        # Mode switching can change the meaning of the '*' shown beside main
        # bet odds, so refresh the white note even when the road layout itself
        # does not need to be rebuilt.
        note_item = getattr(self, 'road_asterisk_note_item', None)
        if note_item is not None:
            try:
                self.canvas.itemconfigure(note_item, text=self._asterisk_note_text())
            except tk.TclError:
                pass
        # temp_finish_data records are stored oldest -> newest.  Roadmaps must
        # be built in that same chronological order (V8 accidentally reversed
        # them, which made every road structurally wrong).
        records = list(self.history_data[-self.MAX_RECORDS:])
        if self.history_panel_mode == 'data':
            self._draw_round_statistics(records)
            return
        big_cells = self._build_big_road(records)
        self._draw_big_road(big_cells)
        self._draw_derived_road('eye', self._derive_road(records, 1), 'ring')
        self._draw_derived_road('cockroach', self._derive_road(records, 3), 'slash')
        self._draw_bead_plate(records)
        self._draw_derived_road('small', self._derive_road(records, 2), 'dot')
        self._draw_next_round_indicator(records)

    def _next_road_color(self, records, candidate, offset):
        simulated = list(records) + [{
            'winner': candidate, 'player_pair': False, 'banker_pair': False,
            'mode': self.game_mode, 'specials': [],
        }]
        before = self._derive_road(records, offset)
        after = self._derive_road(simulated, offset)
        if len(after) <= len(before):
            return None
        return after[-1]['value']

    def _draw_indicator_symbol(self, cx, cy, color_name, style):
        if color_name not in ('red', 'blue'):
            self.canvas.create_text(cx, cy, text='—', font=('Arial', 9), fill='#766d64',
                                    tags='history_dynamic')
            return
        color = '#d83838' if color_name == 'red' else '#2766c5'
        radius = 5
        if style == 'ring':
            self.canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                                    fill='', outline=color, width=2, tags='history_dynamic')
        elif style == 'dot':
            self.canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                                    fill=color, outline=color, width=1,
                                    tags='history_dynamic')
        else:
            self.canvas.create_line(cx-radius, cy+radius, cx+radius, cy-radius,
                                    fill=color, width=2, tags='history_dynamic')

    def _draw_next_round_indicator(self, records):
        geo = self.next_indicator_geometry
        # Fixed row order: Big Eye Boy, Small Road, Cockroach Pig.  V11 omits
        # their text labels; the user sees only the predicted symbols under 闲/庄.
        specs = [(1, 'ring'), (2, 'dot'), (3, 'slash')]
        player_cx = (geo['x0'] + geo['mid_x']) / 2
        banker_cx = (geo['mid_x'] + geo['x1']) / 2
        for row, (offset, style) in enumerate(specs):
            cy = geo['top'] + geo['row_h'] * (row + 0.5)
            self._draw_indicator_symbol(player_cx, cy,
                                        self._next_road_color(records, 'Player', offset), style)
            self._draw_indicator_symbol(banker_cx, cy,
                                        self._next_road_color(records, 'Banker', offset), style)

    def find_original_card_asset_dir(self):
        """Locate the original Baccarat.py A_Tools/Card/Poker1 directory."""
        current = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(current, 'A_Tools', 'Card', 'Poker1'),
            os.path.join(os.path.dirname(current), 'A_Tools', 'Card', 'Poker1'),
            os.path.join(os.path.dirname(os.path.dirname(current)), 'A_Tools', 'Card', 'Poker1'),
        ]
        for directory in candidates:
            if os.path.isdir(directory) and os.path.exists(os.path.join(directory, 'Background.png')):
                return directory
        return None

    def load_original_card_assets(self):
        """Use the original Baccarat 100x140 external card artwork when available."""
        if Image is None or ImageTk is None:
            return
        self.external_card_pil = {}
        self.external_back_pil = None
        card_size = (100, 140)
        directory = self.find_original_card_asset_dir()
        resample = getattr(Image, 'Resampling', Image).LANCZOS

        if directory:
            try:
                for suit in BaccaratEngine.SUITS:
                    for rank in BaccaratEngine.RANKS:
                        path = os.path.join(directory, f'{suit}{rank}.png')
                        if not os.path.exists(path):
                            continue
                        base = Image.open(path).convert('RGBA').resize(card_size, resample)
                        self.external_card_pil[(suit, rank)] = base
                        self.external_card_images[(suit, rank)] = ImageTk.PhotoImage(base, master=self)
                        self.external_card_images_rotated[(suit, rank)] = ImageTk.PhotoImage(
                            base.rotate(90, expand=True), master=self)
                back_path = os.path.join(directory, 'Background.png')
                if os.path.exists(back_path):
                    back = Image.open(back_path).convert('RGBA').resize(card_size, resample)
                    self.external_back_pil = back
                    self.external_back_image = ImageTk.PhotoImage(back, master=self)
                if self.external_card_images and self.external_back_image is not None:
                    self.card_asset_dir = directory
                    return
            except Exception:
                self.external_card_images.clear()
                self.external_card_images_rotated.clear()
                self.external_card_pil.clear()
                self.external_back_image = None
                self.external_back_pil = None
                self.card_asset_dir = None

        # Temporary fallback only when the original external images do not exist.
        try:
            self.external_back_pil = self._make_fallback_card_pil(None, face_up=False)
            self.external_back_image = ImageTk.PhotoImage(self.external_back_pil, master=self)
            for suit in BaccaratEngine.SUITS:
                for rank in BaccaratEngine.RANKS:
                    card = (suit, rank)
                    base = self._make_fallback_card_pil(card, face_up=True)
                    self.external_card_pil[card] = base
                    self.external_card_images[card] = ImageTk.PhotoImage(base, master=self)
                    self.external_card_images_rotated[card] = ImageTk.PhotoImage(
                        base.rotate(90, expand=True), master=self)
        except Exception:
            self.external_card_images.clear()
            self.external_card_images_rotated.clear()
            self.external_card_pil = {}
            self.external_back_image = None
            self.external_back_pil = None

    def load_golden_card_assets(self):
        """Load A_Tools/Card/Poker1/Golden face art for Treasure Pot.

        The Golden directory is expected to use the same ``SuitRank.png`` names
        as Poker1.  If it is absent during development, generate a visibly gold
        fallback so the game remains testable without project assets.
        """
        if Image is None or ImageTk is None:
            return
        self.golden_card_pil = {}
        self.golden_card_images = {}
        self.golden_card_images_rotated = {}
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        golden_dir = os.path.join(self.card_asset_dir, 'Golden') if self.card_asset_dir else None
        for suit in BaccaratEngine.SUITS:
            for rank in BaccaratEngine.RANKS:
                card = (suit, rank)
                base = None
                if golden_dir:
                    path = os.path.join(golden_dir, f'{suit}{rank}.png')
                    if os.path.exists(path):
                        try:
                            base = Image.open(path).convert('RGBA').resize((100, 140), resample)
                        except Exception:
                            base = None
                if base is None:
                    normal = self.external_card_pil.get(card)
                    if normal is not None:
                        base = normal.copy()
                        draw = ImageDraw.Draw(base) if ImageDraw is not None else None
                        if draw is not None:
                            draw.rounded_rectangle((2, 2, 97, 137), radius=8,
                                                   outline='#f5cf35', width=6)
                            draw.rounded_rectangle((7, 7, 92, 132), radius=6,
                                                   outline='#fff2a0', width=2)
                            draw.ellipse((69, 6, 94, 31), fill='#e6b820',
                                         outline='#fff0a3', width=2)
                            try:
                                font = ImageFont.truetype('DejaVuSans-Bold.ttf', 10)
                            except Exception:
                                font = None
                            draw.text((81.5, 18.5), 'G', fill='#3d2c00',
                                      font=font, anchor='mm')
                if base is None:
                    continue
                self.golden_card_pil[card] = base
                self.golden_card_images[card] = ImageTk.PhotoImage(base, master=self)
                self.golden_card_images_rotated[card] = ImageTk.PhotoImage(
                    base.rotate(90, expand=True), master=self)

    def _is_current_golden(self, card):
        return self.game_mode in ('treasure', 'xxx') and tuple(card) in self.current_golden_map

    def _make_fallback_card_pil(self, card, face_up=True):
        image = Image.new('RGBA', (100, 140), '#f4efe4' if face_up else '#253e66')
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((2, 2, 97, 137), radius=8,
                               outline='#d7cbb9' if face_up else '#d7c46a', width=3)
        if not face_up:
            draw.rectangle((12, 12, 87, 127), outline='#e4d490', width=2)
            draw.line((16, 16, 83, 123), fill='#e4d490', width=2)
            draw.line((83, 16, 16, 123), fill='#e4d490', width=2)
            return image
        suit, rank = card
        suit_map = {'Club': '♣', 'Diamond': '♦', 'Heart': '♥', 'Spade': '♠'}
        color = '#c22631' if suit in ('Diamond', 'Heart') else '#111111'
        try:
            font_big = ImageFont.truetype('DejaVuSans-Bold.ttf', 30)
            font_suit = ImageFont.truetype('DejaVuSans.ttf', 28)
        except Exception:
            font_big = None
            font_suit = None
        draw.text((8, 6), str(rank), fill=color, font=font_big)
        draw.text((9, 42), suit_map.get(suit, suit[:1]), fill=color, font=font_suit)
        draw.text((50, 88), suit_map.get(suit, suit[:1]), fill=color, font=font_suit,
                  anchor='mm')
        return image

    def card_position(self, hand_type, index):
        """100x140 layout: first two cards have a 10px edge gap; third card is centred over them."""
        x0, y0, _x1, _y1 = self.animation_panel
        normal_y = y0 + 82
        rotated_y = y0 + 172
        if hand_type == 'Player':
            # P0 is the right card; P1 sits 10px to its left.
            p0_x = x0 + 246
            p1_x = p0_x - 110
            mid_centre = ((p0_x + 50) + (p1_x + 50)) / 2
            positions = {
                0: (p0_x, normal_y),
                1: (p1_x, normal_y),
                2: (mid_centre - 70, rotated_y),
            }
        else:
            # B0 is the left card; B1 sits 10px to its right.
            b0_x = x0 + 402
            b1_x = b0_x + 110
            mid_centre = ((b0_x + 50) + (b1_x + 50)) / 2
            positions = {
                0: (b0_x, normal_y),
                1: (b1_x, normal_y),
                2: (mid_centre - 70, rotated_y),
            }
        return positions.get(index, positions[0])

    def draw_animation_panel(self):
        c = self.canvas
        x0, y0, x1, y1 = self.GAME_X0, 4, self.GAME_X1, 310
        c.create_rectangle(x0, y0, x1, y1, fill=self.PANEL,
                           outline=self.PANEL_LINE, width=2, tags='static')
        self.animation_panel = (x0, y0, x1, y1)
        self.animation_phase_text = c.create_text(
            (x0 + x1) / 2, y0 + 18, text='百家乐 BACCARAT',
            font=('Arial', 16, 'bold'), fill='#d4c3a9', tags='animation')

        self.player_zone_rect = c.create_rectangle(
            x0 + 10, y0 + 38, x0 + 366, y1 - 7,
            fill=self.PLAYER_ZONE_BASE, outline='#6386a5', width=2, tags='animation')
        self.banker_zone_rect = c.create_rectangle(
            x0 + 382, y0 + 38, x1 - 10, y1 - 7,
            fill=self.BANKER_ZONE_BASE, outline='#a56a6d', width=2, tags='animation')
        self.player_zone_label = c.create_text(
            x0 + 24, y0 + 53, anchor='w', text='闲 PLAYER',
            font=('Arial', 24, 'bold'), fill='#93b9ff', tags='animation')
        self.banker_zone_label = c.create_text(
            x0 + 396, y0 + 53, anchor='w', text='庄 BANKER',
            font=('Arial', 24, 'bold'), fill='#ffaaaa', tags='animation')

        p1_x, p1_y = self.card_position('Player', 1)
        b1_x, b1_y = self.card_position('Banker', 1)
        self.player_score_text = c.create_text(
            p1_x - 12, p1_y + 70, anchor='e', text='0',
            font=('Arial', 86, 'bold'), fill='white', tags='animation')
        self.banker_score_text = c.create_text(
            b1_x + 112, b1_y + 70, anchor='w', text='0',
            font=('Arial', 86, 'bold'), fill='white', tags='animation')
        # Retained only as an invisible compatibility item for older helper calls.
        # V17 keeps the Tie strip disabled; Tie is shown only by flashing both card zones.
        self.tie_flash_rect = c.create_rectangle(
            0, 0, 0, 0, fill=self.TIE_FLASH_DARK, outline='',
            state='hidden', tags='animation')
        self.card_item_ids = []
        self.revealed_cards = {'Player': [], 'Banker': []}
        self._temp_flip_images = {}

    def clear_card_display(self):
        for item in self.card_item_ids:
            try:
                self.canvas.delete(item)
            except tk.TclError:
                pass
        self.card_item_ids = []
        self._temp_flip_images = {}
        self.canvas.delete('dealt_golden_multiplier')
        self.revealed_cards = {'Player': [], 'Banker': []}
        self.canvas.itemconfigure(self.player_score_text, text='0')
        self.canvas.itemconfigure(self.banker_score_text, text='0')

    @staticmethod
    def card_text(card):
        suit, rank = card
        suit_map = {'Club': '♣', 'Diamond': '♦', 'Heart': '♥', 'Spade': '♠'}
        return f'{rank}\n{suit_map.get(suit, suit[:1])}'

    def draw_card(self, hand_type, index, card, face_up=True):
        """Draw one card at the Baccarat 100x140 display size."""
        x, y = self.card_position(hand_type, index)
        rotated = index == 2
        image = None
        if face_up:
            image = self._face_photo(card, rotated=rotated)
        else:
            if rotated and self.external_back_pil is not None and ImageTk is not None:
                image = getattr(self, '_rotated_back_image', None)
                if image is None:
                    self._rotated_back_image = ImageTk.PhotoImage(
                        self.external_back_pil.rotate(90, expand=True), master=self)
                    image = self._rotated_back_image
            else:
                image = self.external_back_image
        if image is not None:
            item = self.canvas.create_image(x, y, image=image, anchor='nw',
                                            tags=('animation_card', 'animation'))
            self.card_item_ids.append(item)
            return item

        # Last resort if Pillow is unavailable.
        w, h = (140, 100) if rotated else (100, 140)
        fill = '#f4efe4' if face_up else '#253e66'
        outline = '#d7cbb9' if face_up else '#d7c46a'
        rect = self.canvas.create_rectangle(x, y, x + w, y + h, fill=fill,
                                            outline=outline, width=2,
                                            tags=('animation_card', 'animation'))
        if face_up:
            suit, _rank = card
            fg = '#c22631' if suit in ('Diamond', 'Heart') else '#111111'
            text = self.card_text(card)
        else:
            fg, text = '#e4d490', '◆\\n◆'
        tid = self.canvas.create_text(x + w / 2, y + h / 2, text=text,
                                      font=('Arial', 20, 'bold'), fill=fg,
                                      justify='center', angle=90 if rotated else 0,
                                      tags=('animation_card', 'animation'))
        self.card_item_ids.extend((rect, tid))
        return rect

    def draw_board(self):
        c = self.canvas
        c.create_rectangle(self.GAME_X0, 316, self.GAME_X1, 620, fill=self.FELT,
                           outline=self.LINE, width=2, tags='static')
        self.draw_mode_selector()
        self.draw_mode_betting_board()

    def draw_mode_selector(self):
        c = self.canvas
        x0, y0, x1, y1 = 18, 322, 764, 350
        gap = 4
        width = (x1 - x0 - gap * (len(self.MODE_ORDER) - 1)) / len(self.MODE_ORDER)
        for index, mode in enumerate(self.MODE_ORDER):
            bx0 = x0 + index * (width + gap)
            bx1 = bx0 + width
            tag = f'mode_button_{mode}'
            rect = c.create_rectangle(bx0, y0, bx1, y1, fill='#30271f',
                                      outline='#8d765e', width=1,
                                      tags=(tag, 'mode_selector', 'static'))
            txt = c.create_text((bx0 + bx1) / 2, (y0 + y1) / 2,
                                text=self.MODE_SHORT[mode], font=('Arial', 10, 'bold'),
                                fill='#d9c8af', tags=(tag, 'mode_selector', 'static'))
            self.mode_button_items[mode] = (rect, txt)
            c.tag_bind(tag, '<Button-1>', lambda _e, m=mode: self.change_game_mode(m))
            c.tag_bind(tag, '<Enter>', lambda _e: c.configure(cursor='hand2'))
            c.tag_bind(tag, '<Leave>', lambda _e: c.configure(cursor=''))
        self.update_mode_selector_style()

    def update_mode_selector_style(self):
        for mode, (rect, txt) in self.mode_button_items.items():
            selected = mode == self.game_mode
            self.canvas.itemconfigure(rect,
                                      fill='#a57e38' if selected else '#30271f',
                                      outline='#f2d77c' if selected else '#8d765e',
                                      width=2 if selected else 1)
            self.canvas.itemconfigure(txt, fill='#111111' if selected else '#d9c8af')

    def change_game_mode(self, mode):
        """Switch mode while preserving Player/Banker/Tie wagers.

        Side wagers are refunded. Any old mode fee is refunded first, then the
        destination mode fee (Treasure 20%, XXX 50%) is charged on retained
        main wagers. This also handles Treasure <-> XXX correctly.
        """
        if mode == self.game_mode:
            return
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        if mode not in self.MODE_ORDER:
            return

        old_mode = self.game_mode
        keep_types = {'Player', 'Banker', 'Tie'}
        side_refund = sum(float(amount) for bt, amount in self.bet_state.bets.items()
                          if bt not in keep_types)
        all_fee_refund = sum(float(v) for v in self.bet_fee_state.values())

        def destination_fee_rate(bt):
            if mode == 'goldendice':
                return 0.0 if bt == 'Super Dice' else 0.20
            if mode == 'treasure':
                return 0.0 if bt == 'Golden Hunter' else 0.20
            if mode == 'xxx':
                return 0.50
            return 0.0

        fee_needed = sum(float(self.bet_state.bets.get(bt, 0.0)) * destination_fee_rate(bt)
                         for bt in keep_types)
        projected_balance = self.balance + side_refund + all_fee_refund
        if fee_needed > projected_balance + 1e-9:
            messagebox.showwarning(
                '模式手续费',
                f'保留闲/庄/和下注需要额外手续费 {self.format_money(fee_needed)}，\n'
                f'当前可用余额不足，无法切换模式。',
                parent=self.winfo_toplevel())
            return

        # Refund all side wagers and every fee charged by the old mode.
        for bet_type in list(self.bet_state.bets):
            if bet_type not in keep_types:
                self.balance += self.bet_state.clear_area(bet_type)
        self.balance += all_fee_refund
        self.bet_fee_state.clear()
        self.treasure_pot_amount = 0.0

        # Charge destination fee on retained main wagers.
        for bet_type in keep_types:
            amount = float(self.bet_state.bets.get(bet_type, 0.0))
            rate = destination_fee_rate(bet_type)
            if amount <= 0 or rate <= 0:
                continue
            fee = amount * rate
            self.balance -= fee
            self.bet_fee_state[bet_type] = fee
            self.treasure_pot_amount += fee

        self.game_mode = mode
        self.current_golden_dice = [1, 1]
        self.golden_dice_active = False
        self.golden_dice_multipliers = {key: 2 for key in self.GOLDEN_DICE_BASE_PROFIT_ODDS}
        self.undo_stack.clear()
        self.pending_bet_visual_amounts.clear()
        self.summary_mode = 'bet'
        self.draw_mode_betting_board()
        self.update_mode_selector_style()
        self._update_deal_button_label()
        self.update_display()
        self.save_balance()

    def draw_mode_betting_board(self):
        c = self.canvas
        c.delete('board_dynamic')
        c.delete('bet_chip_dynamic')
        self.bet_spots = {}
        rows = BaccaratEngine.MODE_ROWS[self.game_mode]
        odds = BaccaratEngine.ODDS_TEXT[self.game_mode]

        c.create_text(30, 363, anchor='w',
                      text=BaccaratEngine.MODE_NAMES[self.game_mode],
                      font=('Arial', 14, 'bold'), fill=self.GOLD,
                      tags='board_dynamic')
        if self.game_mode == 'lucky7':
            c.create_text(754, 363, anchor='e',
                          text=f'奖池 ${self.jackpot_amount:,.0f}',
                          font=('Arial', 11, 'bold'), fill='#71edb5',
                          tags=('board_dynamic', 'jackpot_display'))
        elif self.game_mode in ('goldendice', 'treasure', 'xxx'):
            pool_name = ('黄金骰子' if self.game_mode == 'goldendice'
                         else '聚宝盆' if self.game_mode == 'treasure' else 'XXX')
            self.treasure_pool_display = c.create_text(754, 363, anchor='e',
                          text=f'{pool_name} 手续费 ${self.treasure_pot_amount:,.0f}',
                          font=('Arial', 11, 'bold'), fill='#ffd84a',
                          tags=('board_dynamic', 'treasure_pool_display'))

        # Give the two side-bet bands more breathing room and larger text.
        # The main Player/Tie/Banker band is intentionally shorter so the board
        # reads as two information-rich side-bet rows over one compact main row.
        self.draw_bet_row(rows[0], self.BOARD_INNER_X0, 374, 442, odds)
        self.draw_bet_row(rows[1], self.BOARD_INNER_X0, 446, 514, odds)

        main = ('Player', 'Tie', 'Banker')
        x0, x1 = self.BOARD_INNER_X0, self.BOARD_INNER_X1
        y0, y1 = 518, 602
        widths = (0.4, 0.2, 0.4)
        cursor = x0
        for index, bet_type in enumerate(main):
            width = (x1 - x0) * widths[index]
            bx0 = cursor
            bx1 = x1 if index == len(main) - 1 else cursor + width
            self.draw_bet_spot(
                bet_type, bx0, y0, bx1, y1, odds.get(bet_type, ''), main=True)
            cursor = bx1
        self.update_bet_chips()

    def draw_bet_row(self, bet_types, x0, y0, y1, odds):
        count = len(bet_types)
        if count <= 0:
            return
        width = (self.BOARD_INNER_X1 - x0) / count
        for index, bet_type in enumerate(bet_types):
            bx0 = x0 + index * width
            bx1 = self.BOARD_INNER_X1 if index == count - 1 else bx0 + width
            self.draw_bet_spot(bet_type, bx0, y0, bx1, y1, odds.get(bet_type, ''), main=False)

    @staticmethod
    def spot_tag(key):
        bet_type, param = key
        safe = 'none' if param is None else re.sub(r'[^0-9A-Za-z]+', '_', str(param))
        safe_type = re.sub(r'[^0-9A-Za-z]+', '_', str(bet_type))
        return f'betspot_{safe_type}_{safe}'

    def register_spot(self, bet_type, x0, y0, x1, y1, chip_pos, label):
        key = (bet_type, None)
        self.bet_spots[key] = {
            'bounds': (x0, y0, x1, y1), 'chip_pos': chip_pos,
            'label': label, 'tag': self.spot_tag(key),
        }

    def draw_bet_spot(self, bet_type, x0, y0, x1, y1, odds_text, main=False):
        c = self.canvas
        tag = self.spot_tag((bet_type, None))
        fill = self.BET_COLORS.get(bet_type, '#45665c')
        fg = '#111111' if bet_type == 'Panda 8' else 'white'
        golden_side = bet_type in ('Golden Hunter', 'Golden Duel', 'Super Dice')
        outline = '#f0cf54' if golden_side else '#d5cbbd'
        outline_width = 2 if golden_side else 1
        rect_id = c.create_rectangle(
            x0 + 2, y0 + 2, x1 - 2, y1 - 2,
            fill=fill, outline=outline, width=outline_width,
            tags=('board_dynamic', tag))

        label = BaccaratEngine.DISPLAY_NAMES.get(bet_type, bet_type)
        if main:
            label_item = c.create_text(
                (x0 + x1) / 2, y0 + 27, text=label,
                font=('Arial', 23, 'bold'), fill=fg,
                tags=('board_dynamic', tag))
            odds_item = c.create_text(
                (x0 + x1) / 2, y1 - 15, text=odds_text,
                font=('Arial', 18, 'bold'), fill=fg,
                tags=('board_dynamic', tag))
            odds_y = y1 - 15
        else:
            label_item = c.create_text(
                (x0 + x1) / 2, y0 + 23, text=label,
                font=('Arial', 15, 'bold'), fill=fg,
                tags=('board_dynamic', tag))
            odds_item = c.create_text(
                (x0 + x1) / 2, y1 - 13, text=odds_text,
                font=('Arial', 11, 'bold'), fill=fg,
                tags=('board_dynamic', tag))
            odds_y = y1 - 13

        chip_y = (y0 + y1) / 2
        self.register_spot(
            bet_type, x0 + 2, y0 + 2, x1 - 2, y1 - 2,
            ((x0 + x1) / 2, chip_y), label)
        spot = self.bet_spots[(bet_type, None)]
        spot.update({
            'rect_id': rect_id, 'label_item': label_item, 'odds_item': odds_item,
            'base_odds': odds_text, 'odds_y': odds_y, 'odds_base_x': (x0 + x1) / 2, 'main': bool(main),
            'normal_outline': outline, 'normal_outline_width': outline_width,
        })
        c.tag_bind(tag, '<Button-1>', lambda _e, bt=bet_type: self.place_bet(bt))
        c.tag_bind(tag, '<Button-3>', lambda _e, bt=bet_type: self.clear_single_bet(bt))
        c.tag_bind(tag, '<Enter>', lambda _e: c.configure(cursor='hand2'))
        c.tag_bind(tag, '<Leave>', lambda _e: c.configure(cursor=''))

    # ------------------------------------------------------------- bottom controls
    def draw_bottom_controls(self):
        c = self.canvas
        y0, y1 = 625, 748
        c.create_rectangle(0, y0, 1150, y1, fill=self.BG,
                           outline=self.PANEL_LINE, width=2, tags='controls')
        self.balance_text = c.create_text(10, 665, anchor='w', text='余额: $0.00',
                                          font=('Arial', 18, 'bold'), fill='white',
                                          tags=('dynamic', 'controls'))
        self.total_bet_text = c.create_text(10, 710, anchor='w', text='本局下注: $0.00',
                                            font=('Arial', 18, 'bold'), fill='white',
                                            tags=('dynamic', 'controls'))

        # Compact stacked utility buttons leave the true centre of the 1150px
        # table free for the chip rack.
        self.clear_button = self.create_control_button(
            278, 650, 344, 704, '清除', self.clear_bets, '#7c3b40', font_size=11)

        # Larger chips, with the whole seven-chip rack centred at x=575.
        chip_diameter = 56
        chip_gap = 8
        chip_total_width = len(self.CHIP_SPECS) * chip_diameter + (len(self.CHIP_SPECS) - 1) * chip_gap
        chip_x = (self.WIDTH - chip_total_width) / 2
        chip_y = 646
        for value, color, label in self.CHIP_SPECS:
            tag = f'chip_select_{value}'
            outer = c.create_oval(chip_x, chip_y, chip_x + chip_diameter, chip_y + chip_diameter,
                                  fill='#292522', outline='#6d6259', width=3,
                                  tags=(tag, 'chip_selector', 'controls'))
            inner = c.create_oval(chip_x + 5, chip_y + 5,
                                  chip_x + chip_diameter - 5, chip_y + chip_diameter - 5,
                                  fill=color, outline='#eee3d6', width=2,
                                  tags=(tag, 'chip_selector', 'controls'))
            text_color = self.contrast_text_color(color)
            label_id = c.create_text(chip_x + chip_diameter / 2,
                                     chip_y + chip_diameter / 2, text=label,
                                     font=('Arial', 10, 'bold'), fill=text_color,
                                     tags=(tag, 'chip_selector', 'controls'))
            c.tag_bind(tag, '<Button-1>', lambda _e, v=value: self.select_chip(v))
            self.chip_selector_items[value] = (outer, inner, label_id)
            chip_x += chip_diameter + chip_gap

        self.info_button = self.create_control_button(
            810, 650, 855, 695, '❓', self.show_game_instructions, '#315b72',
            fg='white', font_size=17)
        self.repeat_button = self.create_control_button(
            862, 638, 1000, 708, '重复下注', self.repeat_last_bets, '#5b4938', font_size=11)
        self.deal_button = self.create_control_button(
            1012, 628, 1138, 720, '开始' if self.game_mode == 'goldendice' else '开牌', self.deal_cards, '#d5ad4d',
            fg='#111', font_size=14, subtext='ENTER', subtext_font_size=10)
        c.tag_raise('controls')
        c.tag_raise('chip_selector')
        self.update_control_states()

    def _update_deal_button_label(self):
        button = self.control_buttons.get(getattr(self, 'deal_button', None))
        if not button:
            return
        try:
            self.canvas.itemconfigure(
                button['text'], text='开始' if self.game_mode == 'goldendice' else '开牌')
        except tk.TclError:
            pass

    def show_game_instructions(self):
        # 创建自定义弹窗
        win = tk.Toplevel(self)
        win.title("游戏说明")
        win.geometry("900x700")
        win.resizable(False, False)
        
        # 计算窗口居中位置
        self.update_idletasks()  # 确保获取正确的窗口尺寸
        
        # 获取主窗口位置和尺寸
        main_x = self.winfo_x()
        main_y = self.winfo_y()
        main_width = self.winfo_width()
        main_height = self.winfo_height()
        
        # 获取弹窗尺寸
        popup_width = 900
        popup_height = 700
        
        # 计算居中位置
        x = main_x + (main_width - popup_width) // 2
        y = main_y + (main_height - popup_height) // 2
        
        # 设置弹窗位置
        win.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        
        # 创建主框架和滚动条
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建画布和滚动条
        canvas = tk.Canvas(main_frame, bg='#F0F0F0', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#F0F0F0')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 打包画布和滚动条
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ===== 第一部分：基本玩法（文字） =====
        basic_rules_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        basic_rules_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(
            basic_rules_frame,
            text="🎮 百家乐基本玩法",
            font=('微软雅黑', 16, 'bold'),
            bg='#F0F0F0',
            fg='#2E86AB'
        ).pack(anchor='w', pady=(0, 10))
        
        basic_rules_text = """
        百家乐是一种比较扑克牌点数的赌博游戏，目标是预测哪一方的手牌点数最接近9点，
        或者双方是否以相同点数打成平局。

        【游戏流程】
        1. 玩家在闲家、庄家或和局下注
        2. 双方各发2张牌，根据需要可能补发第三张牌
        3. 计算双方牌面点数，最接近9点的一方获胜
        4. 点数计算：A=1点，2-9按面值计算，10/J/Q/K=0点
        5. 如果总点数超过9，只取个位数（如7+8=15→5点）

        【胜负判定】
        • 闲家胜：闲家点数大于庄家点数
        • 庄家胜：庄家点数大于闲家点数  
        • 和局：双方点数相同
        • 如果任何一方前两张牌点数为8或9（天牌），双方都不补牌
            """
        
        basic_label = tk.Label(
            basic_rules_frame,
            text=basic_rules_text,
            font=('微软雅黑', 14),
            bg='#F0F0F0',
            justify=tk.LEFT,
            wraplength=850
        )
        basic_label.pack(fill=tk.X, padx=10)

        # ===== 第二部分：补牌规则（三个表格） =====
        drawing_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        drawing_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(
            drawing_frame,
            text="⚡ 补牌规则表",
            font=('微软雅黑', 14, 'bold'),
            bg='#F0F0F0',
            fg='#A23B72'
        ).pack(anchor='w', pady=(0, 10))

        # ===== 表格1：闲家补牌处理 =====
        player_drawing_frame = tk.Frame(drawing_frame, bg='#F0F0F0')
        player_drawing_frame.pack(fill=tk.X, padx=10, pady=(0, 15))

        tk.Label(
            player_drawing_frame,
            text="🎯 闲家补牌规则",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0',
            fg='#2E86AB'
        ).pack(anchor='w', pady=(0, 8))

        # 闲家补牌规则表头
        player_headers = ["初始点数", "补牌规则", "备注"]
        player_data = [
            ("0-5点", "必须补一张牌", "强制补牌"),
            ("6-7点", "停止补牌", "停牌"),
            ("8-9点", "自然赢，不补牌", "天牌")
        ]

        # 创建闲家补牌规则表格
        player_table = tk.Frame(player_drawing_frame, bg='#F0F0F0')
        player_table.pack(fill=tk.X)

        # 表头
        for col, header in enumerate(player_headers):
            tk.Label(
                player_table,
                text=header,
                font=('微软雅黑', 16, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=12, pady=8,
                anchor='center',
                width=18
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(player_data, start=1):
            bg = '#E8F4FD' if r % 2 == 0 else '#FFFFFF'
            for c, txt in enumerate(row_data):
                tk.Label(
                    player_table,
                    text=txt,
                    font=('微软雅黑', 14),
                    bg=bg,
                    padx=12, pady=6,
                    anchor='center',
                    width=18
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配列宽度
        for c in range(len(player_headers)):
            player_table.columnconfigure(c, weight=1)

        # ===== 表格2：庄家在闲家没有补牌下的处理 =====
        banker_no_draw_frame = tk.Frame(drawing_frame, bg='#F0F0F0')
        banker_no_draw_frame.pack(fill=tk.X, padx=10, pady=(0, 15))

        tk.Label(
            banker_no_draw_frame,
            text="🎯 庄家补牌规则（闲家没有补牌）",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0',
            fg='#A23B72'
        ).pack(anchor='w', pady=(0, 8))

        # 庄家无补牌规则表头
        banker_no_draw_headers = ["庄家初始点数", "补牌规则", "备注"]
        banker_no_draw_data = [
            ("0-5点", "必须补一张牌", "强制补牌"),
            ("6-7点", "停止补牌", "停牌"),
            ("8-9点", "自然赢，不补牌", "天牌")
        ]

        # 创建庄家无补牌规则表格
        banker_no_draw_table = tk.Frame(banker_no_draw_frame, bg='#F0F0F0')
        banker_no_draw_table.pack(fill=tk.X)

        # 表头
        for col, header in enumerate(banker_no_draw_headers):
            tk.Label(
                banker_no_draw_table,
                text=header,
                font=('微软雅黑', 16, 'bold'),
                bg='#A23B72',
                fg='white',
                padx=12, pady=8,
                anchor='center',
                width=18
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(banker_no_draw_data, start=1):
            bg = '#F5E6F0' if r % 2 == 0 else '#FFFFFF'
            for c, txt in enumerate(row_data):
                tk.Label(
                    banker_no_draw_table,
                    text=txt,
                    font=('微软雅黑', 14),
                    bg=bg,
                    padx=12, pady=6,
                    anchor='center',
                    width=18
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配列宽度
        for c in range(len(banker_no_draw_headers)):
            banker_no_draw_table.columnconfigure(c, weight=1)

        # ===== 表格3：庄家在闲家有补牌下的处理 =====
        banker_with_draw_frame = tk.Frame(drawing_frame, bg='#F0F0F0')
        banker_with_draw_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Label(
            banker_with_draw_frame,
            text="🎯 庄家补牌规则（闲家有补牌）",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0',
            fg='#F18F01'
        ).pack(anchor='w', pady=(0, 8))

        # 庄家有补牌规则表头
        banker_with_draw_headers = ["庄家初始点数", "闲家第三张牌条件", "备注"]
        banker_with_draw_data = [
            ("0-2点", "任何牌", "强制补牌"),
            ("3点", "不是8点", "闲家第三张是8点则不补"),
            ("4点", "2-7点", "闲家第三张是0-1、8-9点则不补"),
            ("5点", "4-7点", "闲家第三张是0-3、8-9点则不补"),
            ("6点", "6-7点", "闲家第三张是0-5、8-9点则不补"),
            ("7点", "任何牌", "停止补牌")
        ]

        # 创建庄家有补牌规则表格
        banker_with_draw_table = tk.Frame(banker_with_draw_frame, bg='#F0F0F0')
        banker_with_draw_table.pack(fill=tk.X)

        # 表头
        for col, header in enumerate(banker_with_draw_headers):
            tk.Label(
                banker_with_draw_table,
                text=header,
                font=('微软雅黑', 16, 'bold'),
                bg='#F18F01',
                fg='white',
                padx=10, pady=8,
                anchor='center',
                width=15
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(banker_with_draw_data, start=1):
            bg = '#FDF0E0' if r % 2 == 0 else '#FFFFFF'
            for c, txt in enumerate(row_data):
                tk.Label(
                    banker_with_draw_table,
                    text=txt,
                    font=('微软雅黑', 14),
                    bg=bg,
                    padx=10, pady=6,
                    anchor='center',
                    width=15
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配列宽度
        for c in range(len(banker_with_draw_headers)):
            banker_with_draw_table.columnconfigure(c, weight=1)

        # 补牌规则说明文字
        drawing_explanation = tk.Label(
            drawing_frame,
            text="💡 说明：当闲家前两张牌点数为8或9点（天牌）时，双方都不补牌，直接比较点数决定胜负。",
            font=('微软雅黑', 14),
            bg='#F0F0F0',
            fg='#666666',
            justify=tk.LEFT,
            wraplength=850
        )
        drawing_explanation.pack(fill=tk.X, padx=10, pady=(15, 0))

        # ===== 第三部分：当前模式特色玩法（文字） =====
        special_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        special_frame.pack(fill=tk.X, padx=10, pady=10)

        # 根据游戏模式设置特色标题和内容
        if self.game_mode == "classic":
            special_title = "🎯 经典百家乐特色玩法"
            special_text = """
        经典百家乐是最传统的玩法，保持原始的游戏规则和赔率结构。

        【主要特色】
        • 庄家获胜时支付0.95:1，收取5%佣金
        • 提供多种边注选项，包括对子和龙宝投注
        • 龙宝投注根据赢方点数差提供不同赔率
        • 完美对子：任一方头两张牌点数及花色完全相同赔25:1；双方都满足赔250:1
                """
        elif self.game_mode == "tiger":
            special_title = "🐯 老虎百家乐特色玩法"
            special_text = """
        老虎百家乐以庄家6点获胜时的特殊赔付规则为特色，增加了游戏的刺激性。

        【主要特色】
        • 庄家以6点获胜时赔付降低为50%
        • 引入老虎系列边注：小老虎、大老虎、老虎和
        • 老虎对子投注提供三种不同层级的赔率
        • 专门针对庄家6点情况的多种投注选项
                """
        elif self.game_mode == "ez":
            special_title = "🎪 简单百家乐特色玩法"
            special_text = """
        简单百家乐取消了庄家佣金，但引入了特殊的平局规则和特色边注。

        【主要特色】
        • 取消庄家5%佣金，庄家赔率为1:1
        • 庄家以3张牌7点获胜时视为平局
        • 引入熊猫8点、神之9点、金龙7点等特色边注
        • 猴子系列投注基于特殊牌型组合
                """
        elif self.game_mode == "2to1":
            special_title = "💰 1赔2百家乐特色玩法"
            special_text = """
        1赔2百家乐在主注获胜条件上增加了特殊赔付，提高了获胜时的回报。

        【主要特色】
        • 闲家或庄家以3张牌8点或9点获胜时赔付2:1
        • 和局时主注视为输注，不退还本金
        • 保留龙宝、对子与完美对子等边注
        • 完美对子：单方同点同花25:1；双方都满足250:1
        • 高风险高回报的游戏体验
                """
        elif self.game_mode == "fabulous4":
            special_title = "✨ 神奇4点百家乐特色玩法"
            special_text = """
        神奇4点百家乐专注于4点获胜时的特殊规则，增加了策略性和趣味性。

        【主要特色】
        • 以1点获胜时赔付2:1
        • 闲家以4点获胜时赔付0.5:1
        • 庄家以4点获胜时视为平局
        • 引入神奇对子系列投注，区分同花和非同花
        • 专门的神奇4点边注提供高额赔率
                """
        elif self.game_mode == "lucky7":
            special_title = "🍀 幸运7百家乐特色玩法"
            special_text = """
        幸运7百家乐围绕数字7和6设计特色玩法，并引入大奖机制。

        【主要特色】
        • 闲家7点获胜时的特殊赔率
        • 庄家6点获胜时的分级赔付
        • 闲家7点杀庄家6点的超级7投注
        • 下注超级7自动参与大奖
        • 多种幸运6和幸运7边注选项
                """
        elif self.game_mode == "monkey":
            special_title = "🐵 猴子百家乐特色玩法"
            special_text = """
        猴子百家乐以猴子牌（J、Q、K）的特殊规则为核心，增加了游戏的趣味性和策略性。

        【主要特色】
        • 庄家以3张牌7点获胜时触发猴7点赔付
        • 闲家补牌不是猴子牌且庄家补牌是猴子牌时触发猴老六
        • 猴老六条件下出现和局时触发猴老六和
        • 双方6张牌都是猴子牌时触发猴子六仙大奖
        • 新增幸运猴子边注，根据补牌情况提供多级赔付
        • 保留经典对子投注选项
                """
        elif self.game_mode == "goldendice":
            special_title = "🎲 黄金骰子百家乐特色玩法"
            special_text = """
        黄金骰子在经典百家乐基础上加入两颗独立骰子与随机黄金倍率。

        【主要特色】
        • 按“开始”后两颗骰子滚动约3.5–4秒；五组倍率在约1秒内由上到下抽取
        • 两骰总点只有8或9才激活倍率；其他点数全部使用基础赔率
        • 倍率只从2X、3X、5X、10X、20X、50X、100X抽取，并按长期RTP权重随机
        • 闲1:1、庄0.95:1、和5:1、闲/庄对子10:1；除超级骰子外，下注额外收20%手续费
        • 超级骰子按骰点8/9与双方对子/和局组合分六档，最高档优先只赔一档，免20%手续费
                """
        elif self.game_mode == "xxx":
            special_title = "🎲 XXX 模式特色玩法"
            special_text = """
        XXX 使用聚宝盆的黄金牌放大机制，但采用独立赔率、50%手续费，并加入XXX专属边注“黄金对决”。黄金牌数量与倍率只按固定概率随机，不会逐局计算RTP。

        【主要特色】
        • 每局按固定概率随机抽取4–8张不重复黄金牌；52个牌面等概率，每张黄金牌再独立随机2X、3X、4X、5X、8X或10X
        • 庄家0.97:1、和局2.85:1、闲/庄对子8:1
        • 黄金对决仅在XXX开放，下注区赔率显示15-500,000:1，六档按最高档优先结算
        • 黄金对决不收50%手续费；其他XXX下注仍收取50%手续费
        • RTP只作为长期概率设计参考；每一局不会按RTP动态修正黄金牌或倍率
                """
        elif self.game_mode == "treasure":
            special_title = "🏆 聚宝盆百家乐特色玩法"
            special_text = """
        聚宝盆使用经典百家乐的补牌与胜负规则，并加入每局重新抽取的黄金扑克。

        【主要特色】
        • 每局开牌时从52种牌面随机抽5种不重复黄金扑克，每种随机获得2X、3X、5X或8X
        • 黄金牌出现于对应获胜方时，将该投注的基础盈利赔率按每张黄金牌倍数连续相乘
        • 闲/庄对子基础赔率为9:1，和局基础赔率为5:1，庄家仍按经典百家乐0.95:1
        • 移除龙宝、完美对子与任意对子；保留原版边注“黄金猎手”
        • 除黄金猎手外，下注时额外收取20%作为本局聚宝盆费用；该费用不写入JSON
        • 黄金猎手最高下注5000且免手续费；2/3/4/5/6张黄金牌分别赔3/25/155/3150/51000:1
                """

        tk.Label(
            special_frame,
            text=special_title,
            font=('微软雅黑', 16, 'bold'),
            bg='#F0F0F0',
            fg='#F18F01'
        ).pack(anchor='w', pady=(0, 10))

        special_label = tk.Label(
            special_frame,
            text=special_text,
            font=('微软雅黑', 14),
            bg='#F0F0F0',
            justify=tk.LEFT,
            wraplength=850
        )
        special_label.pack(fill=tk.X, padx=10)

        # ===== 第四部分：当前模式赔率表（表格） =====
        payout_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        payout_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(
            payout_frame,
            text="💰 赔率表",
            font=('微软雅黑', 16, 'bold'),
            bg='#F0F0F0',
            fg='#C73E1D'
        ).pack(anchor='w', pady=(0, 10))

        # 根据游戏模式设置赔率表
        if self.game_mode == "classic":
            payout_headers = ["投注类型", "赔率", "说明"]
            payout_data = [
                ("闲家", "1:1", "闲家获胜"),
                ("和局", "8:1", "双方点数相同"),
                ("庄家", "0.95:1", "庄家获胜（抽水5%）"),
                ("龙宝", "1-30:1", "根据自然点数或点数差获胜"),
                ("完美对子", "25/250:1", "单方同点同花25:1；双方都同点同花250:1"),
                ("闲家对子", "11:1", "闲家前两张牌点数相同"),
                ("庄家对子", "11:1", "庄家前两张牌点数相同"),
                ("任意对子", "5:1", "任一方前两张牌点数相同")
            ]
            
            # 龙宝赔率详细说明
            dragon_headers = ["点数差", "闲家龙宝赔率", "庄家龙宝赔率"]
            dragon_data = [
                ("自然点和", "退还", "退还"),
                ("自然点赢", "1:1", "1:1"),
                ("4点", "1:1", "1:1"),
                ("5点", "2:1", "2:1"),
                ("6点", "4:1", "4:1"),
                ("7点", "6:1", "6:1"),
                ("8点", "10:1", "10:1"),
                ("9点", "30:1", "30:1")
            ]
            
            # 完美对子赔率详细说明
            perfect_pair_headers = ["获胜情况", "赔率"]
            perfect_pair_data = [
                ("闲家或庄家任一方前两张牌同点数且同花色", "25:1"),
                ("闲家和庄家双方前两张牌都同点数且同花色", "250:1")
            ]
            
        elif self.game_mode == "tiger":
            payout_headers = ["投注类型", "赔率", "说明"]
            payout_data = [
                ("闲家", "1:1", "闲家获胜"),
                ("和局", "8:1", "双方点数相同"),
                ("庄家", "1:1*", "庄家获胜（6点赔付50%）"),
                ("小老虎", "22:1", "庄家2张牌6点获胜"),
                ("老虎和", "35:1", "和局且闲家庄家6点"),
                ("大老虎", "50:1", "庄家3张牌6点获胜"),
                ("老虎", "12(20):1", "庄家2(3)张牌6点获胜"),
                ("虎对子", "4/20/100:1", "对子投注")
            ]
            
            # 老虎对子详细说明
            tiger_pair_headers = ["对子类型", "赔率"]
            tiger_pair_data = [
                ("单方对子", "4:1"),
                ("双方不同对子", "20:1"),
                ("双方相同对子", "100:1")
            ]
            
        elif self.game_mode == "ez":
            payout_headers = ["投注类型", "赔率", "说明"]
            payout_data = [
                ("闲家", "1:1", "闲家获胜"),
                ("和局", "8:1", "双方点数相同"),
                ("庄家", "1:1*", "庄家获胜（3张牌7点获胜 平局）"),
                ("龙宝", "1-30:1", "根据自然点数或点数差获胜"),
                ("熊猫8点", "25:1", "闲家3张牌8点获胜"),
                ("神之9点", "10/75:1", "9点获胜"),
                ("金龙7点", "40:1", "庄家3张牌7点获胜"),
                ("闲家对子", "11:1", "闲家前两张牌点数相同"),
                ("庄家对子", "11:1", "庄家前两张牌点数相同")
            ]

            # 龙宝赔率详细说明
            dragon_headers = ["点数差", "闲家龙宝赔率", "庄家龙宝赔率"]
            dragon_data = [
                ("自然点和", "退还", "退还"),
                ("自然点赢", "1:1", "1:1"),
                ("4点", "1:1", "1:1"),
                ("5点", "2:1", "2:1"),
                ("6点", "4:1", "4:1"),
                ("7点", "6:1", "6:1"),
                ("8点", "10:1", "10:1"),
                ("9点", "30:1", "30:1")
            ]
            
            # 神之9点详细说明
            divine_headers = ["获胜情况", "赔率"]
            divine_data = [
                ("闲家3张牌9点获胜", "10:1"),
                ("庄家3张牌9点获胜", "10:1"),
                ("双方3张牌9点和局", "75:1")
            ]
            
        elif self.game_mode == "2to1":
            payout_headers = ["投注类型", "赔率", "说明"]
            payout_data = [
                ("闲家", "1:1*", "闲家获胜（3张牌8/9点2:1）"),
                ("和局", "8:1", "和局（主注输）"),
                ("庄家", "1:1*", "庄家获胜（3张牌8/9点2:1）"),
                ("龙宝", "1-30:1", "根据自然点数或点数差获胜"),
                ("完美对子", "25/250:1", "单方同点同花25:1；双方都同点同花250:1"),
                ("闲家对子", "11:1", "闲家前两张牌点数相同"),
                ("庄家对子", "11:1", "庄家前两张牌点数相同"),
                ("任意对子", "5:1", "任一方前两张牌点数相同")
            ]

            # 龙宝赔率详细说明
            dragon_headers = ["点数差", "闲家龙宝赔率", "庄家龙宝赔率"]
            dragon_data = [
                ("自然点和", "退还", "退还"),
                ("自然点赢", "1:1", "1:1"),
                ("4点", "1:1", "1:1"),
                ("5点", "2:1", "2:1"),
                ("6点", "4:1", "4:1"),
                ("7点", "6:1", "6:1"),
                ("8点", "10:1", "10:1"),
                ("9点", "30:1", "30:1")
            ]
            
            # 完美对子赔率详细说明
            perfect_pair_headers = ["获胜情况", "赔率"]
            perfect_pair_data = [
                ("闲家或庄家任一方前两张牌同点数且同花色", "25:1"),
                ("闲家和庄家双方前两张牌都同点数且同花色", "250:1")
            ]
            
        elif self.game_mode == "fabulous4":
            payout_headers = ["投注类型", "赔率", "说明"]
            payout_data = [
                ("闲家", "1:1*", "主注分级赔付"),
                ("和局", "8:1", "双方点数相同"),
                ("庄家", "1:1*", "主注分级赔付"),
                ("龙宝", "1-30:1", "根据自然点数或点数差获胜"),
                ("闲家神对", "1-7:1", "分级对子赔付"),
                ("庄家神对", "1-7:1", "分级对子赔付"),
                ("闲神4点", "50:1", "闲家以4点获胜"),
                ("庄神4点", "25:1", "庄家以4点获胜")
            ]
            
            # 神奇对子详细说明
            fab_pair_headers = ["对子类型", "赔率"]
            fab_pair_data = [
                ("同花对子", "7:1"),
                ("非同花对子", "4:1"),
                ("同花非对子", "1:1")
            ]
            
        elif self.game_mode == "lucky7":
            payout_headers = ["投注类型", "赔率", "说明", "大奖参与"]
            payout_data = [
                ("闲家", "1:1", "闲家获胜", "-"),
                ("和局", "8:1", "双方点数相同", "-"),
                ("庄家", "1:1*", "庄家获胜（6点赔付50%）", "-"),
                ("小幸运6", "22:1", "庄家2张牌6点获胜", "-"),
                ("幸运6", "12(20):1", "庄家2(3)张牌6点获胜", "-"),
                ("大幸运6", "50:1", "庄家3张牌6点获胜", "-"),
                ("闲对", "11:1", "闲家前两张牌点数相同", "-"),
                ("幸运7", "6/15:1", "闲家7点获胜", "-"),
                ("超级7", "30/40/100:1", "闲家7点庄家6点", "下注1千或以上参与"),
                ("庄对", "11:1", "庄家前两张牌点数相同", "-")
            ]
            
            # 幸运6和幸运7详细说明
            lucky67_headers = ["获胜情况", "赔率"]
            lucky67_data = [
                ("庄家2张牌6点", "12:1（幸运6）"),
                ("庄家3张牌6点", "20:1（幸运6）"),
                ("闲家2张牌7点", "6:1（幸运7）"),
                ("闲家3张牌7点", "15:1（幸运7）")
            ]
            
            # 超级7详细说明
            super7_headers = ["总牌数", "超级7赔率"]
            super7_data = [
                ("4张牌", "30:1"),
                ("5张牌", "40:1"),
                ("6张牌", "100:1")
            ]

            # 超级7大奖说明
            super7_progressive_headers = ["闲家扑克牌要求", "庄家扑克牌要求", "百分比"]
            super7_progressive_data = [
                ("3张方片♦共7点", "3张黑桃♠共6点", "100%大奖"),
                ("3张红色共7点", "3张黑色共6点", "100%次奖")
            ]

        elif self.game_mode == "monkey":
            payout_headers = ["投注类型", "赔率", "说明"]
            payout_data = [
                ("闲家", "1:1", "闲家获胜"),
                ("和局", "8:1", "双方点数相同"),
                ("庄家", "1:1*", "庄家获胜（3张牌7点平局）"),
                ("猴老六", "12:1", "闲家补牌不是猴子 庄家补牌是猴子"),
                ("猴老六和", "150:1", "满足猴老六条件 + 本局结果为和局"),
                ("猴子六仙", "5000:1", "闲家庄家6张牌都是猴子牌"),
                ("猴7点", "40:1", "庄家3张牌7点获胜"),
                ("幸运猴子", "1-75:1", "根据补牌情况多级赔付"),  # 新增幸运猴子
                ("闲家对子", "11:1", "闲家前两张牌点数相同"),
                ("庄家对子", "11:1", "庄家前两张牌点数相同")
            ]
            
            # 猴子牌定义说明
            monkey_def_headers = ["猴子牌类型", "牌面", "说明"]
            monkey_def_data = [
                ("猴子牌", "J、Q、K", "所有花色的J、Q、K都算猴子牌")
            ]
            
            # 猴子边注触发条件说明
            monkey_trigger_headers = ["边注类型", "触发条件"]
            monkey_trigger_data = [
                ("猴老六", "闲家补牌不是猴子牌 + 庄家补牌是猴子牌"),
                ("猴老六和", "满足猴老六条件 + 本局结果为和局"),
                ("猴子六仙", "闲家3张牌 + 庄家3张牌 = 6张牌都是猴子牌"),
                ("猴7点", "庄家3张牌组成7点并获胜"),
                ("幸运猴子", "根据双方补牌是否为猴子牌决定赔付等级")  # 新增幸运猴子说明
            ]

            # 幸运猴子详细赔率说明
            lucky_monkey_headers = ["补牌情况", "赔付条件", "赔率"]
            lucky_monkey_data = [
                ("双方都补牌", "只有一方是猴子", "1:1"),
                ("仅闲家补牌", "补牌为猴子", "3:1"),
                ("仅庄家补牌", "补牌为猴子", "8:1"),
                ("双方都补牌", "双方都是猴子", "10:1"),
                ("双方都补牌", "双方猴子牌点数相同", "25:1"),
                ("双方都补牌", "双方猴子牌点数花色相同", "75:1")
            ]

        elif self.game_mode == "goldendice":
            payout_headers = ["投注类型", "基础赔率", "说明"]
            payout_data = [
                ("闲家", "1:1", "骰点8/9时盈利赔率乘随机倍率"),
                ("和局", "5:1", "骰点8/9时盈利赔率乘随机倍率"),
                ("庄家", "0.95:1", "骰点8/9时盈利赔率乘随机倍率"),
                ("闲家对子", "10:1", "骰点8/9时盈利赔率乘随机倍率"),
                ("庄家对子", "10:1", "骰点8/9时盈利赔率乘随机倍率"),
                ("超级骰子", "9–2600:1", "六档：骰点8/9 × 对子/双对/和局；最高档优先；免20%手续费"),
                ("手续费", "20%", "除超级骰子外，所有下注均额外收取20%，不储存")
            ]
        elif self.game_mode == "xxx":
            payout_headers = ["投注类型", "基础赔率", "说明"]
            payout_data = [
                ("闲家", "1:1", "闲家获胜；黄金牌放大倍数作用于盈利赔率"),
                ("和局", "2.85:1", "双方点数相同；黄金牌放大倍数作用于盈利赔率"),
                ("庄家", "0.97:1", "庄家获胜；黄金牌放大倍数作用于盈利赔率"),
                ("闲家对子", "8:1", "闲家前两张同点；黄金牌放大倍数作用于盈利赔率"),
                ("庄家对子", "8:1", "庄家前两张同点；黄金牌放大倍数作用于盈利赔率"),
                ("黄金对决", "15-500,000:1", "XXX专属六档边注；最高档优先；最高下注5000；免50%手续费"),
                ("手续费", "50%", "除黄金对决外，每笔下注额外收取50%，不储存")
            ]
        elif self.game_mode == "treasure":
            payout_headers = ["投注类型", "基础赔率", "说明"]
            payout_data = [
                ("闲家", "1:1", "闲家获胜；黄金牌可倍增盈利赔率"),
                ("和局", "5:1", "双方点数相同；黄金牌可倍增盈利赔率"),
                ("庄家", "0.95:1", "经典庄家5%佣金；黄金牌可倍增盈利赔率"),
                ("闲家对子", "9:1", "闲家前两张同点；黄金牌可倍增盈利赔率"),
                ("庄家对子", "9:1", "庄家前两张同点；黄金牌可倍增盈利赔率"),
                ("黄金猎手", "3/25/155/3150/51000:1", "按本局实际发出的黄金牌张数结算；最高下注5000"),
                ("手续费", "20%", "除黄金猎手外，每笔下注额外20%作为本局聚宝盆费用，不储存")
            ]

        # 创建主赔率表格
        payout_table = tk.Frame(payout_frame, bg='#F0F0F0')
        payout_table.pack(fill=tk.X, padx=10)

        # 表头
        for col, header in enumerate(payout_headers):
            tk.Label(
                payout_table,
                text=header,
                font=('微软雅黑', 16, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=8, pady=6,
                anchor='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(payout_data, start=1):
            bg = '#E8F4FD' if r % 2 == 0 else '#FFFFFF'
            for c, txt in enumerate(row_data):
                tk.Label(
                    payout_table,
                    text=txt,
                    font=('微软雅黑', 14),
                    bg=bg,
                    padx=8, pady=4,
                    anchor='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配列宽度
        for c in range(len(payout_headers)):
            payout_table.columnconfigure(c, weight=1)

        # 添加多赔率边注的详细说明表格
        if self.game_mode in ["classic", "tiger", "ez", "2to1", "fabulous4", "lucky7", "monkey"]:
            detail_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
            detail_frame.pack(fill=tk.X, padx=10, pady=5)
            
            tk.Label(
                detail_frame,
                text="📊 边注详细赔率说明",
                font=('微软雅黑', 16, 'bold'),
                bg='#F0F0F0',
                fg='#2E86AB'
            ).pack(anchor='w', pady=(10, 5))

            # 根据模式显示相应的详细赔率表
            if self.game_mode == "classic" or self.game_mode == "2to1" or self.game_mode == "ez":
                # 龙宝赔率表
                dragon_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                dragon_frame.pack(fill=tk.X, padx=20, pady=5)
                
                tk.Label(
                    dragon_frame,
                    text="🐉 龙宝赔率（根据赢方点数差）",
                    font=('微软雅黑', 16, 'bold'),
                    bg='#F0F0F0'
                ).pack(anchor='w', pady=(0, 5))
                
                # 创建龙宝表格
                dragon_table = tk.Frame(dragon_frame, bg='#F0F0F0')
                dragon_table.pack(fill=tk.X)
                
                for col, header in enumerate(dragon_headers):
                    tk.Label(
                        dragon_table,
                        text=header,
                        font=('微软雅黑', 16, 'bold'),
                        bg='#A23B72',
                        fg='white',
                        padx=6, pady=4,
                        anchor='center'
                    ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                
                for r, row_data in enumerate(dragon_data, start=1):
                    bg = '#F5E6F0' if r % 2 == 0 else '#FFFFFF'
                    for c, txt in enumerate(row_data):
                        tk.Label(
                            dragon_table,
                            text=txt,
                            font=('微软雅黑', 14),
                            bg=bg,
                            padx=6, pady=3,
                            anchor='center'
                        ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                
                for c in range(len(dragon_headers)):
                    dragon_table.columnconfigure(c, weight=1)
                    
                # 完美对子赔率表
                perfect_pair_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                perfect_pair_frame.pack(fill=tk.X, padx=20, pady=5)
                
                if not self.game_mode == "ez":
                    tk.Label(
                        perfect_pair_frame,
                        text="💠 完美对子赔率",
                        font=('微软雅黑', 16, 'bold'),
                        bg='#F0F0F0'
                    ).pack(anchor='w', pady=(10, 5))
                
                    perfect_pair_table = tk.Frame(perfect_pair_frame, bg='#F0F0F0')
                    perfect_pair_table.pack(fill=tk.X)
                    
                    for col, header in enumerate(perfect_pair_headers):
                        tk.Label(
                            perfect_pair_table,
                            text=header,
                            font=('微软雅黑', 16, 'bold'),
                            bg='#F18F01',
                            fg='white',
                            padx=6, pady=4,
                            anchor='center'
                        ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                    
                    for r, row_data in enumerate(perfect_pair_data, start=1):
                        bg = '#FDF0E0' if r % 2 == 0 else '#FFFFFF'
                        for c, txt in enumerate(row_data):
                            tk.Label(
                                perfect_pair_table,
                                text=txt,
                                font=('微软雅黑', 14),
                                bg=bg,
                                padx=6, pady=3,
                                anchor='center'
                            ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                    
                    for c in range(len(perfect_pair_headers)):
                        perfect_pair_table.columnconfigure(c, weight=1)
                else:
                    # 神之9点赔率表
                    divine_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                    divine_frame.pack(fill=tk.X, padx=20, pady=5)
                    
                    tk.Label(
                        divine_frame,
                        text="✨ 神之9点赔率",
                        font=('微软雅黑', 16, 'bold'),
                        bg='#F0F0F0'
                    ).pack(anchor='w', pady=(0, 5))
                    
                    # 创建神之9点表格
                    divine_table = tk.Frame(divine_frame, bg='#F0F0F0')
                    divine_table.pack(fill=tk.X)
                    
                    for col, header in enumerate(divine_headers):
                        tk.Label(
                            divine_table,
                            text=header,
                            font=('微软雅黑', 16, 'bold'),
                            bg='#A23B72',
                            fg='white',
                            padx=6, pady=4,
                            anchor='center'
                        ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                    
                    for r, row_data in enumerate(divine_data, start=1):
                        bg = '#F5E6F0' if r % 2 == 0 else '#FFFFFF'
                        for c, txt in enumerate(row_data):
                            tk.Label(
                                divine_table,
                                text=txt,
                                font=('微软雅黑', 14),
                                bg=bg,
                                padx=6, pady=3,
                                anchor='center'
                            ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                    
                    for c in range(len(divine_headers)):
                        divine_table.columnconfigure(c, weight=1)
                        
            elif self.game_mode == "tiger":
                # 老虎对子赔率表
                tiger_pair_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                tiger_pair_frame.pack(fill=tk.X, padx=20, pady=5)
                
                tk.Label(
                    tiger_pair_frame,
                    text="🐯 老虎对子赔率",
                    font=('微软雅黑', 16, 'bold'),
                    bg='#F0F0F0'
                ).pack(anchor='w', pady=(0, 5))
                
                # 创建老虎对子表格
                tiger_pair_table = tk.Frame(tiger_pair_frame, bg='#F0F0F0')
                tiger_pair_table.pack(fill=tk.X)
                
                for col, header in enumerate(tiger_pair_headers):
                    tk.Label(
                        tiger_pair_table,
                        text=header,
                        font=('微软雅黑', 16, 'bold'),
                        bg='#A23B72',
                        fg='white',
                        padx=6, pady=4,
                        anchor='center'
                    ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                
                for r, row_data in enumerate(tiger_pair_data, start=1):
                    bg = '#F5E6F0' if r % 2 == 0 else '#FFFFFF'
                    for c, txt in enumerate(row_data):
                        tk.Label(
                            tiger_pair_table,
                            text=txt,
                            font=('微软雅黑', 14),
                            bg=bg,
                            padx=6, pady=3,
                            anchor='center'
                        ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                
                for c in range(len(tiger_pair_headers)):
                    tiger_pair_table.columnconfigure(c, weight=1)
                    
            elif self.game_mode == "fabulous4":
                # 神奇对子赔率表
                fab_pair_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                fab_pair_frame.pack(fill=tk.X, padx=20, pady=5)
                
                tk.Label(
                    fab_pair_frame,
                    text="✨ 神奇对子赔率",
                    font=('微软雅黑', 16, 'bold'),
                    bg='#F0F0F0'
                ).pack(anchor='w', pady=(0, 5))
                
                # 创建神奇对子表格
                fab_pair_table = tk.Frame(fab_pair_frame, bg='#F0F0F0')
                fab_pair_table.pack(fill=tk.X)
                
                for col, header in enumerate(fab_pair_headers):
                    tk.Label(
                        fab_pair_table,
                        text=header,
                        font=('微软雅黑', 16, 'bold'),
                        bg='#A23B72',
                        fg='white',
                        padx=6, pady=4,
                        anchor='center'
                    ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                
                for r, row_data in enumerate(fab_pair_data, start=1):
                    bg = '#F5E6F0' if r % 2 == 0 else '#FFFFFF'
                    for c, txt in enumerate(row_data):
                        tk.Label(
                            fab_pair_table,
                            text=txt,
                            font=('微软雅黑', 14),
                            bg=bg,
                            padx=6, pady=3,
                            anchor='center'
                        ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                
                for c in range(len(fab_pair_headers)):
                    fab_pair_table.columnconfigure(c, weight=1)
                    
            elif self.game_mode == "lucky7":
                # 幸运6和幸运7赔率表
                lucky67_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                lucky67_frame.pack(fill=tk.X, padx=20, pady=5)
                
                tk.Label(
                    lucky67_frame,
                    text="🍀 幸运6和幸运7赔率",
                    font=('微软雅黑', 16, 'bold'),
                    bg='#F0F0F0'
                ).pack(anchor='w', pady=(0, 5))
                
                # 创建幸运6和幸运7表格
                lucky67_table = tk.Frame(lucky67_frame, bg='#F0F0F0')
                lucky67_table.pack(fill=tk.X)
                
                for col, header in enumerate(lucky67_headers):
                    tk.Label(
                        lucky67_table,
                        text=header,
                        font=('微软雅黑', 16, 'bold'),
                        bg='#A23B72',
                        fg='white',
                        padx=6, pady=4,
                        anchor='center'
                    ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                
                for r, row_data in enumerate(lucky67_data, start=1):
                    bg = '#F5E6F0' if r % 2 == 0 else '#FFFFFF'
                    for c, txt in enumerate(row_data):
                        tk.Label(
                            lucky67_table,
                            text=txt,
                            font=('微软雅黑', 14),
                            bg=bg,
                            padx=6, pady=3,
                            anchor='center'
                        ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                
                for c in range(len(lucky67_headers)):
                    lucky67_table.columnconfigure(c, weight=1)
                    
                # 超级7赔率表
                super7_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                super7_frame.pack(fill=tk.X, padx=20, pady=5)
                
                tk.Label(
                    super7_frame,
                    text="🎰 超级7赔率（根据总牌数）",
                    font=('微软雅黑', 16, 'bold'),
                    bg='#F0F0F0'
                ).pack(anchor='w', pady=(10, 5))
                
                # 创建超级7表格
                super7_progressive_table = tk.Frame(super7_frame, bg='#F0F0F0')
                super7_progressive_table.pack(fill=tk.X)
                
                for col, header in enumerate(super7_headers):
                    tk.Label(
                        super7_progressive_table,
                        text=header,
                        font=('微软雅黑', 16, 'bold'),
                        bg='#F18F01',
                        fg='white',
                        padx=6, pady=4,
                        anchor='center'
                    ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                
                for r, row_data in enumerate(super7_data, start=1):
                    bg = '#FDF0E0' if r % 2 == 0 else '#FFFFFF'
                    for c, txt in enumerate(row_data):
                        tk.Label(
                            super7_progressive_table,
                            text=txt,
                            font=('微软雅黑', 14),
                            bg=bg,
                            padx=6, pady=3,
                            anchor='center'
                        ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                
                for c in range(len(super7_headers)):
                    super7_progressive_table.columnconfigure(c, weight=1)

                # 超级7大奖说明表
                super7_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                super7_frame.pack(fill=tk.X, padx=20, pady=5)
                
                tk.Label(
                    super7_frame,
                    text="🎰 超级7累进大奖赔率",
                    font=('微软雅黑', 16, 'bold'),
                    bg='#F0F0F0'
                ).pack(anchor='w', pady=(10, 5))
                
                # 创建超级7大奖表格
                super7_progressive_table = tk.Frame(super7_frame, bg='#F0F0F0')
                super7_progressive_table.pack(fill=tk.X)
                
                for col, header in enumerate(super7_progressive_headers):
                    tk.Label(
                        super7_progressive_table,
                        text=header,
                        font=('微软雅黑', 16, 'bold'),
                        bg='#F18F01',
                        fg='white',
                        padx=6, pady=4,
                        anchor='center'
                    ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                
                for r, row_data in enumerate(super7_progressive_data, start=1):
                    bg = '#FDF0E0' if r % 2 == 0 else '#FFFFFF'
                    for c, txt in enumerate(row_data):
                        tk.Label(
                            super7_progressive_table,
                            text=txt,
                            font=('微软雅黑', 14),
                            bg=bg,
                            padx=6, pady=3,
                            anchor='center'
                        ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                
                for c in range(len(super7_progressive_headers)):
                    super7_progressive_table.columnconfigure(c, weight=1)

            elif self.game_mode == "monkey":
                # 猴子牌定义说明表
                monkey_def_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                monkey_def_frame.pack(fill=tk.X, padx=20, pady=5)
                
                tk.Label(
                    monkey_def_frame,
                    text="🐵 猴子牌定义说明",
                    font=('微软雅黑', 16, 'bold'),
                    bg='#F0F0F0'
                ).pack(anchor='w', pady=(0, 5))
                
                # 创建猴子牌定义表格
                monkey_def_table = tk.Frame(monkey_def_frame, bg='#F0F0F0')
                monkey_def_table.pack(fill=tk.X)
                
                for col, header in enumerate(monkey_def_headers):
                    tk.Label(
                        monkey_def_table,
                        text=header,
                        font=('微软雅黑', 16, 'bold'),
                        bg='#A23B72',
                        fg='white',
                        padx=6, pady=4,
                        anchor='center'
                    ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                
                for r, row_data in enumerate(monkey_def_data, start=1):
                    bg = '#F5E6F0' if r % 2 == 0 else '#FFFFFF'
                    for c, txt in enumerate(row_data):
                        tk.Label(
                            monkey_def_table,
                            text=txt,
                            font=('微软雅黑', 14),
                            bg=bg,
                            padx=6, pady=3,
                            anchor='center'
                        ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                
                for c in range(len(monkey_def_headers)):
                    monkey_def_table.columnconfigure(c, weight=1)
                    
                # 猴子边注触发条件说明表
                monkey_trigger_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                monkey_trigger_frame.pack(fill=tk.X, padx=20, pady=5)
                
                tk.Label(
                    monkey_trigger_frame,
                    text="🐵 猴子边注触发条件",
                    font=('微软雅黑', 16, 'bold'),
                    bg='#F0F0F0'
                ).pack(anchor='w', pady=(10, 5))
                
                # 创建猴子边注触发条件表格
                monkey_trigger_table = tk.Frame(monkey_trigger_frame, bg='#F0F0F0')
                monkey_trigger_table.pack(fill=tk.X)
                
                for col, header in enumerate(monkey_trigger_headers):
                    tk.Label(
                        monkey_trigger_table,
                        text=header,
                        font=('微软雅黑', 16, 'bold'),
                        bg='#F18F01',
                        fg='white',
                        padx=6, pady=4,
                        anchor='center'
                    ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                
                for r, row_data in enumerate(monkey_trigger_data, start=1):
                    bg = '#FDF0E0' if r % 2 == 0 else '#FFFFFF'
                    for c, txt in enumerate(row_data):
                        tk.Label(
                            monkey_trigger_table,
                            text=txt,
                            font=('微软雅黑', 14),
                            bg=bg,
                            padx=6, pady=3,
                            anchor='center'
                        ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                
                for c in range(len(monkey_trigger_headers)):
                    monkey_trigger_table.columnconfigure(c, weight=1)

                # 新增：幸运猴子详细赔率表
                lucky_monkey_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                lucky_monkey_frame.pack(fill=tk.X, padx=20, pady=5)
                
                tk.Label(
                    lucky_monkey_frame,
                    text="🍀 幸运猴子详细赔率",
                    font=('微软雅黑', 16, 'bold'),
                    bg='#F0F0F0'
                ).pack(anchor='w', pady=(10, 5))
                
                # 创建幸运猴子详细赔率表格
                lucky_monkey_table = tk.Frame(lucky_monkey_frame, bg='#F0F0F0')
                lucky_monkey_table.pack(fill=tk.X)
                
                for col, header in enumerate(lucky_monkey_headers):
                    tk.Label(
                        lucky_monkey_table,
                        text=header,
                        font=('微软雅黑', 16, 'bold'),
                        bg='#FF69B4',
                        fg='white',
                        padx=6, pady=4,
                        anchor='center'
                    ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                
                for r, row_data in enumerate(lucky_monkey_data, start=1):
                    bg = '#FFE6F2' if r % 2 == 0 else '#FFFFFF'
                    for c, txt in enumerate(row_data):
                        tk.Label(
                            lucky_monkey_table,
                            text=txt,
                            font=('微软雅黑', 14),
                            bg=bg,
                            padx=6, pady=3,
                            anchor='center'
                        ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                
                for c in range(len(lucky_monkey_headers)):
                    lucky_monkey_table.columnconfigure(c, weight=1)

        # ===== 第五部分：特别赔付细节（文字） =====
        special_payout_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        special_payout_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(
            special_payout_frame,
            text="💎 特别赔付细节",
            font=('微软雅黑', 14, 'bold'),
            bg='#F0F0F0',
            fg='#C73E1D'
        ).pack(anchor='w', pady=(0, 10))

        # 根据游戏模式设置特别赔付细节
        if self.game_mode == "classic":
            special_payout_text = """
        【特别注意事项】
        • 庄家获胜时支付0.95:1，即收取5%佣金
        • 龙宝投注基于赢方与输方的点数差计算赔率
        • 完美对子只检查闲家与庄家的前两张牌；单方同点同花25:1，双方均同点同花250:1
        • 对子投注只考虑前两张牌是否点数相同
                """
        elif self.game_mode == "tiger":
            special_payout_text = """
        【特别注意事项】
        • 庄家以6点获胜时赔付降低为50%（即0.5:1）
        • 小老虎：庄家以2张牌6点获胜
        • 大老虎：庄家以3张牌6点获胜  
        • 老虎和：和局且庄家点数为6点
        • 老虎对子：单方对子4:1，双方不同对子20:1，双方相同对子100:1
                """
        elif self.game_mode == "ez":
            special_payout_text = """
        【特别注意事项】
        • 庄家以3张牌7点获胜时视为平局，退还本金
        • 熊猫8点：闲家必须用3张牌组成8点并获胜
        • 神之9点：任何一方用3张牌组成9点即赔付，双方都9点赔付更高
        • 金龙7点：庄家必须用3张牌组成7点并获胜
        • 龙宝投注基于赢方与输方的点数差计算赔率
                """
        elif self.game_mode == "2to1":
            special_payout_text = """
        【特别注意事项】
        • 闲家或庄家以3张牌8点或9点获胜时赔付2:1
        • 和局时主注视为输注，不退还本金
        • 其他情况下主注按1:1赔付
                """
        elif self.game_mode == "fabulous4":
            special_payout_text = """
        【特别注意事项】
        • 闲家以1点获胜时赔付2:1，以4点获胜时赔付0.5:1
        • 庄家以1点获胜时赔付2:1，以4点获胜时视为平局
        • 神奇对子区分同花对子、非同花对子和同花非对子
        • 同花指相同花色，对子指相同点数
        • 神奇4点边注不需要同花或对子，只看获胜点数
                """
        elif self.game_mode == "lucky7":
            special_payout_text = """
        【特别注意事项】
        • 庄家以6点获胜时赔付降低为50%（即0.5:1）
        • 下注1000或以上在超级7上自动参与累进大奖
        • 累进大奖头奖条件：闲家3张方片7点 + 庄家3张黑桃6点
        • 累进大奖次奖条件：闲家3张红色7点 + 庄家3张黑色6点
        • 每局下注的1%加入累进大奖池，最低保障500万
                """
        elif self.game_mode == "monkey":
            special_payout_text = """
        【特别注意事项】
        • 庄家以3张牌7点获胜时视为平局，退还本金
        • 猴子牌指J、Q、K，所有花色都算猴子牌
        • 猴老六：闲家补牌不是猴子牌且庄家补牌是猴子牌
        • 猴老六和：满足猴老六条件且本局结果为和局
        • 猴子六仙：双方6张牌都是猴子牌（闲家3张+庄家3张）
        • 猴7点：庄家3张牌组成7点并获胜
        • 幸运猴子：根据补牌情况提供1:1至75:1多级赔付
        • 只有补发的第三张牌才参与猴子牌判定
                """
        elif self.game_mode == "xxx":
            special_payout_text = """
        【特别注意事项】
        • 每局随机4–8张黄金牌；每张独立随机2X、3X、4X、5X、8X或10X；获胜盈利赔率直接乘该倍率
        • 黄金牌放大倍数只作用于获胜投注的盈利赔率；下注区赔率与实际结算统一保留2位小数并四舍五入
        • 除黄金对决外，XXX下注额外收取50%手续费
        • 黄金对决仅在XXX开放，最高下注5000且免50%手续费；下注区赔率显示15-500,000:1，六档按最高命中条件结算
        • 黄金对决：双方各有黄金牌15:1；再加和局35:1；至少一方黄金对子100:1；双方黄金对子3000:1；5张同一黄金牌面50000:1；6张同一黄金牌面500000:1
        • RTP只作为长期概率设计参考；每一局黄金牌数量与每张倍率均独立随机
                """
        elif self.game_mode == "treasure":
            special_payout_text = """
        【特别注意事项】
        • 每局的5种黄金牌面互不重复；各自随机获得2X、3X、5X或8X
        • 8副牌中同一牌面可能出现多次，每次实际发出的黄金牌都会再次乘上对应倍数
        • 黄金倍数只放大获胜投注的盈利赔率，不会修改下注格内原本显示的基础赔率
        • 除黄金猎手外，每笔下注额外收取20%作为本局聚宝盆费用；不会储存
        • 黄金猎手不收20%手续费，最高下注5000
        • 黄金猎手：1张输、2张3:1、3张25:1、4张155:1、5张3150:1、6张51000:1
                """

        special_payout_label = tk.Label(
            special_payout_frame,
            text=special_payout_text,
            font=('微软雅黑', 14),
            bg='#FFF9E6',
            fg='#8B4513',
            justify=tk.LEFT,
            wraplength=850,
            padx=15,
            pady=10,
            relief=tk.RAISED,
            bd=1
        )
        special_payout_label.pack(fill=tk.X, padx=10)

        # 更新滚动区域
        canvas.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

        # 添加关闭按钮
        close_btn = ttk.Button(
            scrollable_frame,
            text="关闭说明",
            command=win.destroy
        )
        close_btn.pack(pady=20)

        # 绑定鼠标滚轮滚动
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def show_help_window(self):
        mode = BaccaratEngine.MODE_NAMES[self.game_mode]
        rows = BaccaratEngine.MODE_ROWS[self.game_mode]
        odds = BaccaratEngine.ODDS_TEXT[self.game_mode]
        side_lines = []
        for bet_type in rows[0] + rows[1]:
            side_lines.append(f'• {BaccaratEngine.DISPLAY_NAMES.get(bet_type, bet_type)}：{odds.get(bet_type, "") }')
        messagebox.showinfo(
            '百家乐 V24 玩法说明',
            '【基本规则】\n'
            '• A=1，2–9按牌面，10/J/Q/K=0，只取总点数个位。\n'
            '• 闲0–5补牌、6–7停牌；8/9为天牌。\n'
            '• 庄家按标准第三张牌规则补牌。\n'
            '• 和局在多数玩法会退回闲/庄本金；1赔2玩法按旧版逻辑不退。\n\n'
            f'【当前玩法：{mode}】\n' + '\n'.join(side_lines) +
            '\n\n操作：左键下注；右键清除单区；清除按钮清空本局；Enter开牌。',
            parent=self.winfo_toplevel())

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
                              subtext_font_size=10):
        tag = f'control_button_{len(self.control_buttons)}'
        shadow = self.canvas.create_rectangle(x0 + 5, y0 + 6, x1 + 5, y1 + 6,
                                              fill='#070605', outline='#070605',
                                              width=1, tags=(tag, 'controls'))
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

    def update_control_states(self):
        enabled = self.accept_bets and not self.animation_running and not self.settlement_running
        for attr in ('clear_button', 'repeat_button', 'deal_button'):
            tag = getattr(self, attr, None)
            if tag:
                self.set_control_button_state(tag, enabled)

    # ---------------------------------------------------------- V23 chip motion
    def _schedule_chip_motion(self, delay_ms, callback):
        """Schedule one chip-motion frame and keep its after-id cancellable."""
        holder = {}

        def run():
            after_id = holder.get('id')
            if after_id is not None:
                self.chip_motion_after_ids.discard(after_id)
            if self._closing:
                return
            callback()

        after_id = self.after(max(0, int(delay_ms)), run)
        holder['id'] = after_id
        self.chip_motion_after_ids.add(after_id)
        return after_id

    def _chip_rack_source_position(self):
        """Return the centre of the currently selected physical chip in the rack."""
        items = self.chip_selector_items.get(self.selected_chip)
        if items:
            try:
                coords = self.canvas.coords(items[1])
                if len(coords) >= 4:
                    return ((coords[0] + coords[2]) / 2.0,
                            (coords[1] + coords[3]) / 2.0)
            except tk.TclError:
                pass
        # Seven-chip rack is centred in the lower control area.
        return (self.WIDTH / 2.0, 674.0)

    def _chip_rack_return_position(self, index=0, total=1):
        """Spread simultaneous winning returns slightly across the chip-rack centre."""
        total = max(1, int(total))
        index = max(0, min(int(index), total - 1))
        if total <= 1:
            offset = 0.0
        else:
            spacing = min(34.0, 150.0 / max(1, total - 1))
            offset = (index - (total - 1) / 2.0) * spacing
        return (self.WIDTH / 2.0 + offset, 674.0)

    def _fee_chip_target_position(self):
        """Top-right fee area used by Treasure and XXX."""
        return (735.0, 363.0)

    def _animate_amount_chip(self, amount, start_xy, target_xy, on_complete=None,
                             role='wager'):
        """Animate one compact chip from start_xy to target_xy in exactly 0.2 s."""
        if self._closing:
            if callable(on_complete):
                on_complete()
            return

        amount = float(amount)
        if amount <= 0:
            if callable(on_complete):
                on_complete()
            return

        self.chip_motion_serial += 1
        tag = f'chip_motion_{self.chip_motion_serial}'
        x, y = map(float, start_xy)
        tx, ty = map(float, target_xy)
        radius = 19.0
        chip_color = self.bet_chip_color(amount)
        text_color = self.contrast_text_color(chip_color)
        outline = '#ffd84a' if role == 'fee' else '#e2ddd5'

        outer = self.canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill='#292522', outline='#151311', width=1,
            tags=(tag, 'chip_motion'))
        inner = self.canvas.create_oval(
            x - radius + 3, y - radius + 3, x + radius - 3, y + radius - 3,
            fill=chip_color, outline=outline, width=2 if role == 'fee' else 1,
            tags=(tag, 'chip_motion'))
        text = self.canvas.create_text(
            x, y, text=self._compact_amount(amount),
            font=('Arial', 9, 'bold'), fill=text_color,
            tags=(tag, 'chip_motion'))
        item_ids = (outer, inner, text)
        steps = max(1, int(self.CHIP_MOVE_STEPS))
        frame_ms = max(1, int(round(self.CHIP_MOVE_DURATION_MS / steps)))

        def place_items(cx, cy):
            try:
                self.canvas.coords(outer, cx - radius, cy - radius,
                                   cx + radius, cy + radius)
                self.canvas.coords(inner, cx - radius + 3, cy - radius + 3,
                                   cx + radius - 3, cy + radius - 3)
                self.canvas.coords(text, cx, cy)
                self.canvas.tag_raise(tag)
            except tk.TclError:
                return False
            return True

        def frame(step):
            if self._closing:
                return
            ratio = min(1.0, max(0.0, step / steps))
            # Smoothstep keeps the motion quick but avoids a mechanical stop.
            eased = ratio * ratio * (3.0 - 2.0 * ratio)
            cx = x + (tx - x) * eased
            cy = y + (ty - y) * eased
            if not place_items(cx, cy):
                return
            if step >= steps:
                try:
                    self.canvas.delete(tag)
                except tk.TclError:
                    pass
                if callable(on_complete):
                    on_complete()
                return
            self._schedule_chip_motion(frame_ms, lambda: frame(step + 1))

        place_items(x, y)
        self._schedule_chip_motion(frame_ms, lambda: frame(1))

    def _complete_pending_bet_visual(self, key, amount):
        pending = max(0.0, float(self.pending_bet_visual_amounts.get(key, 0.0))
                      - float(amount))
        if pending > 1e-9:
            self.pending_bet_visual_amounts[key] = pending
        else:
            self.pending_bet_visual_amounts.pop(key, None)
        if not self._closing:
            self.update_bet_chips()
            self.canvas.tag_raise('controls')

    def _start_winning_chip_return(self):
        """After settlement flashing, fly winning and Push return chips to the rack."""
        if self.settlement_return_animating:
            return True

        returning = []
        for key, amount in self.flash_winner_amounts.items():
            spot = self.bet_spots.get(key)
            if spot and float(amount) > 0:
                returning.append((key, float(amount), spot))
        for bet_type, amount in self.push_return_amounts.items():
            key = (bet_type, None)
            spot = self.bet_spots.get(key)
            if spot and float(amount) > 0:
                returning.append((key, float(amount), spot))
        if not returning:
            return False

        self.settlement_return_animating = True
        self.settlement_return_keys = {key for key, _amount, _spot in returning}
        # Replace the last "original stake" flash frame by the actual returned
        # amount, then hide those static chips while their moving copies travel.
        self.flash_mode = 'win'
        self.update_bet_chips()

        remaining = {'count': len(returning)}

        def one_finished():
            remaining['count'] -= 1
            if remaining['count'] <= 0 and not self._closing:
                self.settlement_return_animating = False
                self.settlement_return_keys.clear()
                self.finish_settlement()

        for index, (_key, amount, spot) in enumerate(returning):
            start = tuple(spot.get('chip_pos', (0.0, 0.0)))
            target = self._chip_rack_return_position(index, len(returning))
            self._animate_amount_chip(amount, start, target,
                                      on_complete=one_finished, role='return')
        return True

    # --------------------------------------------------------------- bet actions
    def select_chip(self, amount):
        self.selected_chip = float(amount)
        for value, items in self.chip_selector_items.items():
            outer, _inner, _text = items
            selected = float(value) == float(amount)
            self.canvas.itemconfigure(outer,
                                      outline='#ffda42' if selected else '#6d6259',
                                      width=5 if selected else 3)
        self.canvas.tag_raise('chip_selector')

    def bet_limit_for(self, bet_type):
        if bet_type in ('Golden Hunter', 'Golden Duel', 'Super Dice'):
            return 5_000.0
        if bet_type in ('Player', 'Banker'):
            return 500_000.0
        if bet_type == 'Tie':
            return 100_000.0
        return 30_000.0

    def _treasure_fee_rate(self, bet_type):
        if self.game_mode == 'goldendice':
            return 0.0 if bet_type == 'Super Dice' else 0.20
        if self.game_mode == 'treasure':
            return 0.0 if bet_type == 'Golden Hunter' else 0.20
        if self.game_mode == 'xxx':
            # XXX Golden Duel is explicitly fee-free; all other XXX wagers pay 50%.
            return 0.0 if bet_type == 'Golden Duel' else 0.50
        return 0.0

    def _refresh_treasure_pool_text(self):
        item = getattr(self, 'treasure_pool_display', None)
        if item:
            try:
                name = ('20%' if self.game_mode in ('goldendice', 'treasure')
                        else ('50%' if self.game_mode == 'xxx' else ''))
                self.canvas.itemconfigure(item, text=f'{name}手续费 ${self.treasure_pot_amount:,.0f}')
            except tk.TclError:
                pass

    def _current_round_total_cost(self):
        """Visible current-round outlay = wagers + active-mode fees."""
        return float(self.bet_state.total_at_risk()) + sum(
            float(v) for v in self.bet_fee_state.values())

    def place_bet(self, bet_type, amount=None, record_undo=True):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return False
        if (bet_type, None) not in self.bet_spots:
            return False
        requested = float(amount if amount is not None else self.selected_chip)

        # V20: every wager must be exactly 100 or a multiple of 100.
        if requested < 100.0 or abs(requested / 100.0 - round(requested / 100.0)) > 1e-9:
            messagebox.showwarning('下注单位', '下注只接受100及100的倍数。',
                                   parent=self.winfo_toplevel())
            return False

        area_current = self.bet_state.current_area_bet(bet_type)
        table_current = self.bet_state.total_at_risk()
        fee_rate = self._treasure_fee_rate(bet_type)
        balance_capacity = self.balance / (1.0 + fee_rate) if fee_rate else self.balance
        raw_allowed = min(requested,
                          self.bet_limit_for(bet_type) - area_current,
                          self.MAX_TABLE_BET - table_current,
                          balance_capacity)
        raw_allowed = max(0.0, raw_allowed)

        # Auto-adjustment must also remain on a 100-unit boundary.  We floor
        # rather than round upward so the adjusted bet never exceeds balance,
        # area limit, or table limit.
        allowed = float(int(raw_allowed // 100.0) * 100)
        if allowed < 100.0:
            return False
        if allowed < requested:
            # If the selected chip is larger than the remaining limit for this
            # betting area, silently place only the maximum amount allowed.
            # Other clipping reasons (for example balance/table capacity) keep
            # the existing warning so they remain visible to the player.
            area_remaining = max(0.0, self.bet_limit_for(bet_type) - area_current)
            table_remaining = max(0.0, self.MAX_TABLE_BET - table_current)
            clipped_by_area_limit = (
                area_remaining + 1e-9 < requested
                and area_remaining <= table_remaining + 1e-9
                and area_remaining <= balance_capacity + 1e-9
            )
            if not clipped_by_area_limit:
                messagebox.showwarning('下注限制', f'下注已自动调整为 {self.format_money(allowed)}。',
                                       parent=self.winfo_toplevel())
        fee = allowed * fee_rate
        key = (bet_type, None)
        # Keep the newly added amount off the static destination chip until the
        # 0.2-second flying chip actually arrives there. Existing chips remain.
        self.pending_bet_visual_amounts[key] = (
            self.pending_bet_visual_amounts.get(key, 0.0) + allowed)
        self.bet_state.add_bet(bet_type, allowed)
        self.balance -= allowed + fee
        if fee > 0:
            self.bet_fee_state[bet_type] = self.bet_fee_state.get(bet_type, 0.0) + fee
            self.treasure_pot_amount += fee
        if record_undo:
            self.undo_stack.append((bet_type, None, allowed))
        self.summary_mode = 'bet'
        self._refresh_treasure_pool_text()
        self.update_display()

        source = self._chip_rack_source_position()
        target = tuple(self.bet_spots[key]['chip_pos'])
        self._animate_amount_chip(
            allowed, source, target,
            on_complete=lambda k=key, a=allowed: self._complete_pending_bet_visual(k, a),
            role='wager')
        if fee > 0:
            self._animate_amount_chip(
                fee, source, self._fee_chip_target_position(), role='fee')

        self.save_balance()
        return True

    def clear_single_bet(self, bet_type, _param=None):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        refunded = self.bet_state.clear_area(bet_type)
        if refunded <= 0:
            return
        fee = float(self.bet_fee_state.pop(bet_type, 0.0))
        self.balance += refunded + fee
        if fee > 0:
            self.treasure_pot_amount = max(0.0, self.treasure_pot_amount - fee)
        self.undo_stack = [item for item in self.undo_stack if item[0] != bet_type]
        self.pending_bet_visual_amounts.pop((bet_type, None), None)
        self._refresh_treasure_pool_text()
        self.update_display()
        self.save_balance()

    def undo_last_bet(self):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        while self.undo_stack:
            bet_type, _param, amount = self.undo_stack.pop()
            removed = self.bet_state.remove_amount(bet_type, amount)
            if removed > 0:
                key = (bet_type, None)
                pending = max(0.0, self.pending_bet_visual_amounts.get(key, 0.0) - removed)
                if pending > 1e-9:
                    self.pending_bet_visual_amounts[key] = pending
                else:
                    self.pending_bet_visual_amounts.pop(key, None)
                fee_rate = self._treasure_fee_rate(bet_type)
                fee = min(float(self.bet_fee_state.get(bet_type, 0.0)), removed * fee_rate)
                if fee > 0:
                    left = self.bet_fee_state.get(bet_type, 0.0) - fee
                    if left > 1e-9:
                        self.bet_fee_state[bet_type] = left
                    else:
                        self.bet_fee_state.pop(bet_type, None)
                    self.treasure_pot_amount = max(0.0, self.treasure_pot_amount - fee)
                self.balance += removed + fee
                self._refresh_treasure_pool_text()
                self.update_display()
                self.save_balance()
                return

    def clear_bets(self):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        refunded = self.bet_state.clear_all()
        fee = sum(float(v) for v in self.bet_fee_state.values())
        if refunded <= 0 and fee <= 0:
            return
        self.balance += refunded + fee
        if fee > 0:
            self.treasure_pot_amount = max(0.0, self.treasure_pot_amount - fee)
        self.bet_fee_state.clear()
        self.undo_stack.clear()
        self.pending_bet_visual_amounts.clear()
        self._refresh_treasure_pool_text()
        self.update_display()
        self.save_balance()

    def snapshot_bets(self):
        return [(bet_type, None, float(amount))
                for bet_type, amount in self.bet_state.bets.items() if amount > 0]

    def repeat_last_bets(self):
        if (not self.accept_bets or self.animation_running or self.settlement_running
                or not self.last_round_bets):
            return

        # Repeat is a replacement operation: refund/remove every wager currently
        # on the table first, then rebuild the table from the stored last-round
        # snapshot. The player no longer has to press Clear manually.
        self.clear_bets()

        active = {key[0] for key in self.bet_spots}
        repeatable = [(bt, p, amt) for bt, p, amt in self.last_round_bets if bt in active]
        required = sum(amt * (1.0 + self._treasure_fee_rate(bt))
                       for bt, _p, amt in repeatable)
        if self.balance + 1e-9 < required:
            messagebox.showwarning('余额不足',
                                   f'重复上局下注需要 {self.format_money(required)}，当前余额为 {self.format_money(self.balance)}。',
                                   parent=self.winfo_toplevel())
            return
        for bet_type, _param, amount in repeatable:
            self.place_bet(bet_type, amount=amount, record_undo=True)

    # ------------------------------------------------------------ display update
    @staticmethod
    def format_money(value):
        if abs(value - round(value)) < 0.005:
            return f'${value:,.0f}'
        return f'${value:,.2f}'

    @staticmethod
    def contrast_text_color(color):
        value = color.lstrip('#')
        if len(value) != 6:
            return 'black'
        red, green, blue = (int(value[i:i + 2], 16) for i in (0, 2, 4))
        luminance = 0.299 * red + 0.587 * green + 0.114 * blue
        return 'black' if luminance >= 150 else 'white'

    @staticmethod
    def _compact_amount(amount):
        if amount >= 1_000_000:
            # Winning chips are compacted in M once they reach 1000K.
            # Exact 100K steps have an exact one-decimal M representation;
            # smaller residuals are intentionally truncated and marked with +.
            hundred_k = 100_000.0
            exact_step = abs(amount / hundred_k - round(amount / hundred_k)) < 1e-9
            truncated_tenths = int(amount // hundred_k) / 10.0
            text = (f'{truncated_tenths:.0f}M' if abs(truncated_tenths - round(truncated_tenths)) < 1e-9
                    else f'{truncated_tenths:.1f}M')
            return text if exact_step else text + '+'
        if amount >= 1000:
            value = amount / 1000
            return f'{value:.0f}K' if abs(value - round(value)) < 0.01 else f'{value:.1f}K'
        return str(int(round(amount))) if abs(amount - round(amount)) < 0.01 else f'{amount:.1f}'

    def update_display(self):
        self.canvas.itemconfigure(self.balance_text, text=f'余额: {self.format_money(self.balance)}')
        if self.summary_mode == 'win':
            self.canvas.itemconfigure(self.total_bet_text,
                                      text=f'上局返还: {self.format_money(self.last_win_amount)}')
        else:
            self.canvas.itemconfigure(self.total_bet_text,
                                      text=f'本局下注: {self.format_money(self._current_round_total_cost())}')
        self.update_bet_chips()
        self._refresh_treasure_pool_text()
        self.update_history_table()
        self.update_control_states()

    def update_bet_chips(self):
        self.canvas.delete('bet_chip_dynamic')
        for key, spot in self.bet_spots.items():
            amount = self.bet_state.current_area_bet(key[0])
            # While a new wager is flying in, show only the amount that had
            # already reached this betting spot.
            pending_in = float(self.pending_bet_visual_amounts.get(key, 0.0))
            if pending_in > 0 and not self.settlement_running:
                amount = max(0.0, amount - pending_in)
            # Tie is a visual push for Player/Banker during settlement: the
            # original wager chips stay on the felt until finish_settlement().
            # This is intentionally independent of whether a particular mode
            # later treats the monetary return differently.
            if self.settlement_running and key in self.settlement_hold_amounts:
                amount = self.settlement_hold_amounts[key]
            if key in self.flash_winner_amounts:
                if self.flash_mode == 'win':
                    amount = self.flash_winner_amounts[key]
                elif self.flash_mode == 'original':
                    amount = self.flash_original_amounts.get(key, amount)
            # The moving copy itself is the winning chip during the 0.2-second
            # return flight, so do not leave a duplicate static chip underneath.
            if self.settlement_return_animating and key in self.settlement_return_keys:
                continue
            if amount <= 0:
                continue
            x0, y0, x1, y1 = spot['bounds']
            # Keep the wager chip in the geometric centre of its betting area.
            x, y = (x0 + x1) / 2, (y0 + y1) / 2
            radius = 20
            x = max(x0 + radius + 1, min(x1 - radius - 1, x))
            y = max(y0 + radius + 1, min(y1 - radius - 1, y))
            chip_color = self.bet_chip_color(amount)
            text_color = self.contrast_text_color(chip_color)
            self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius,
                                    fill='#292522', outline='#151311', width=1,
                                    tags=('bet_chip_dynamic', spot['tag']))
            self.canvas.create_oval(x - radius + 3, y - radius + 3,
                                    x + radius - 3, y + radius - 3,
                                    fill=chip_color, outline='#e2ddd5', width=1,
                                    tags=('bet_chip_dynamic', spot['tag']))
            self.canvas.create_text(x, y, text=self._compact_amount(amount),
                                    font=('Arial', 9, 'bold'), fill=text_color,
                                    tags=('bet_chip_dynamic', spot['tag']))

    @classmethod
    def bet_chip_color(cls, amount):
        # _compact_amount() switches to M at 1,000,000; mirror that visual state
        # with a dark-navy chip. contrast_text_color() then yields white text.
        if amount >= 1_000_000:
            return cls.M_CHIP_COLOR

        color = cls.CHIP_SPECS[0][1]
        for threshold, chip_color, _label in cls.CHIP_SPECS:
            if amount >= threshold:
                color = chip_color
            else:
                break
        return color

    # ------------------------------------------------------- Golden Dice mode
    def create_golden_dice_images(self):
        """Create two-die artwork using the uploaded Sicbo.py drawing geometry."""
        self.golden_dice_images = []
        if Image is None or ImageTk is None or ImageDraw is None:
            return

        def make_die(size, number):
            image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            margin = max(1, size // 28)
            radius = max(3, size // 6)
            draw.rounded_rectangle(
                (margin, margin, size - margin - 1, size - margin - 1),
                radius=radius, fill='#f4df83', outline='#a06c12',
                width=max(2, size // 18))
            quarter, half, three_quarter = size // 4, size // 2, size - size // 4
            positions = {
                1: [(half, half)],
                2: [(quarter, quarter), (three_quarter, three_quarter)],
                3: [(quarter, quarter), (half, half), (three_quarter, three_quarter)],
                4: [(quarter, quarter), (three_quarter, quarter),
                    (quarter, three_quarter), (three_quarter, three_quarter)],
                5: [(quarter, quarter), (three_quarter, quarter), (half, half),
                    (quarter, three_quarter), (three_quarter, three_quarter)],
                6: [(quarter, size // 5), (three_quarter, size // 5),
                    (quarter, half), (three_quarter, half),
                    (quarter, size - size // 5), (three_quarter, size - size // 5)],
            }
            pip = max(2, size // 11)
            for x, y in positions[number]:
                draw.ellipse((x-pip, y-pip, x+pip, y+pip), fill='#4b2b08')
            return ImageTk.PhotoImage(image, master=self)

        for number in range(1, 7):
            self.golden_dice_images.append(make_die(82, number))

    def _draw_golden_dice_multiplier(self, bet_type):
        weights = self.GOLDEN_DICE_MULTIPLIER_WEIGHTS[bet_type]
        return int(random.SystemRandom().choices(
            self.GOLDEN_DICE_MULTIPLIER_VALUES, weights=weights, k=1)[0])

    def _prepare_golden_dice_round(self, on_complete=None):
        """Start the 3.5-4.0 second two-die roll and 1-second odds reel."""
        self.current_golden_map = {}
        self.current_golden_cards = []
        self.current_golden_dice = [die.roll() for die in self.golden_dice_objects]
        self.golden_dice_active = False
        self.golden_dice_multipliers = {
            bet_type: self._draw_golden_dice_multiplier(bet_type)
            for bet_type in self.GOLDEN_DICE_BASE_PROFIT_ODDS
        }
        self._show_golden_dice_panel_shell()

        # Multipliers settle from top to bottom; the last row lands within ~1 sec.
        reel_order = ('Player', 'Banker', 'Pair Player', 'Pair Banker', 'Tie')
        for index, bet_type in enumerate(reel_order):
            self._queue_animation(index * 150, self._animate_golden_dice_multiplier_row,
                                  bet_type, 0)

        duration_ms = 3500 + secrets.randbelow(501)
        self.golden_dice_animation_delay_ms = 55
        self.golden_dice_animation_frames_left = max(1, duration_ms // self.golden_dice_animation_delay_ms)
        self._animate_golden_dice_roll(on_complete)

    def _show_golden_dice_panel_shell(self):
        self.treasure_panel_active = True
        self.canvas.delete('history_dynamic')
        self.canvas.delete('treasure_panel')
        self.treasure_panel_images = []
        self.treasure_animation_refs = {}
        self.treasure_panel_card_items = []
        self.treasure_panel_multiplier_items = []
        self.treasure_panel_rule_cells = {}
        self.golden_dice_panel_items = []
        self.golden_dice_multiplier_text_items = {}
        x0, y0, x1, y1 = self.HISTORY_X0, 4, self.HISTORY_X1, 620
        c = self.canvas
        c.create_rectangle(x0, y0, x1, y1, fill='#17120f', outline='#d0aa3f', width=3,
                           tags='treasure_panel')
        c.create_text((x0+x1)/2, 28, text='黄金骰子', font=('Arial', 22, 'bold'),
                      fill='#ffd84a', tags='treasure_panel')
        c.create_text((x0+x1)/2, 57,
                      text=f'本局手续费 20% · ${self.treasure_pot_amount:,.0f}',
                      font=('Arial', 12, 'bold'), fill='white', tags='treasure_panel')
        c.create_text((x0+x1)/2, 82, text='两骰合计 8 / 9 才激活黄金赔率',
                      font=('Arial', 10, 'bold'), fill='#e8d8b4', tags='treasure_panel')

        centres = ((x0+x1)/2 - 53, 138), ((x0+x1)/2 + 53, 138)
        self.golden_dice_panel_items = []
        for index, (cx, cy) in enumerate(centres):
            if self.golden_dice_images:
                item = c.create_image(cx, cy, image=self.golden_dice_images[0],
                                      tags=('treasure_panel', 'golden_dice_die'))
            else:
                item = c.create_text(cx, cy, text='⚄', font=('Arial', 48, 'bold'),
                                     fill='#ffd84a', tags=('treasure_panel', 'golden_dice_die'))
            self.golden_dice_panel_items.append(item)
        self.golden_dice_total_text = c.create_text(
            (x0+x1)/2, 191, text='骰子转动中…', font=('Arial', 12, 'bold'),
            fill='white', tags='treasure_panel')
        self.golden_dice_status_text = c.create_text(
            (x0+x1)/2, 212, text='等待 8 / 9', font=('Arial', 11, 'bold'),
            fill='#d7c7aa', tags='treasure_panel')

        labels = (
            ('Player', '闲家'), ('Banker', '庄家'),
            ('Pair Player', '闲家对子'), ('Pair Banker', '庄家对子'), ('Tie', '和局'))
        top = 238
        row_h = 31
        c.create_rectangle(x0+22, top-7, x1-22, top+row_h*5-5,
                           fill='#211811', outline='#8d765e', width=1,
                           tags='treasure_panel')
        for index, (bet_type, label) in enumerate(labels):
            cy = top + index * row_h + 9
            if index:
                c.create_line(x0+22, cy-15, x1-22, cy-15, fill='#5d4a39',
                              tags='treasure_panel')
            c.create_text(x0+38, cy, anchor='w', text=label,
                          font=('Arial', 10, 'bold'), fill='white', tags='treasure_panel')
            text_item = c.create_text(x1-40, cy, anchor='e', text='ROLL…',
                                      font=('Arial', 11, 'bold'), fill='#ffd84a',
                                      tags='treasure_panel')
            self.golden_dice_multiplier_text_items[bet_type] = text_item

        c.create_text((x0+x1)/2, 410, text='超级骰子', font=('Arial', 14, 'bold'),
                      fill='#ffd84a', tags='treasure_panel')
        super_rows = (
            ('9点 + 双方对子 + 和局', '2600:1'),
            ('8点 + 双方对子 + 和局', '2100:1'),
            ('9点 + 双方对子', '325:1'),
            ('8点 + 双方对子', '260:1'),
            ('9点 + 任一方对子', '11:1'),
            ('8点 + 任一方对子', '9:1'),
        )
        table_x0, table_x1 = x0 + 14, x1 - 14
        table_y0, row_h = 428, 27
        split_x = table_x0 + (table_x1-table_x0) * 0.68
        c.create_rectangle(table_x0, table_y0, table_x1, table_y0+row_h*6,
                           fill='#211811', outline='#8d765e', tags='treasure_panel')
        c.create_line(split_x, table_y0, split_x, table_y0+row_h*6,
                      fill='#8d765e', tags='treasure_panel')
        for idx, (label, odds) in enumerate(super_rows):
            ry0 = table_y0 + idx*row_h
            if idx:
                c.create_line(table_x0, ry0, table_x1, ry0, fill='#665240',
                              tags='treasure_panel')
            odds_bg = c.create_rectangle(split_x+1, ry0+1, table_x1-1, ry0+row_h-1,
                                         fill='#211811', outline='', tags='treasure_panel')
            c.create_text(table_x0+6, ry0+row_h/2, anchor='w', text=label,
                          font=('Arial', 8, 'bold'), fill='white', tags='treasure_panel')
            odds_text = c.create_text((split_x+table_x1)/2, ry0+row_h/2, text=odds,
                                      font=('Arial', 9, 'bold'), fill='#ffd84a',
                                      tags='treasure_panel')
            self.treasure_panel_rule_cells[idx+1] = (odds_bg, odds_text)
        c.tag_raise('treasure_panel')

    def _set_golden_dice_item_face(self, item, value):
        try:
            if self.golden_dice_images:
                self.canvas.itemconfigure(item, image=self.golden_dice_images[int(value)-1])
            else:
                self.canvas.itemconfigure(item, text=str(int(value)))
        except tk.TclError:
            pass

    def _animate_golden_dice_multiplier_row(self, bet_type, step=0):
        if self._closing or not self.treasure_panel_active or self.game_mode != 'goldendice':
            return
        item = self.golden_dice_multiplier_text_items.get(bet_type)
        if item is None:
            return
        if step < 9:
            value = self.GOLDEN_DICE_MULTIPLIER_VALUES[
                secrets.randbelow(len(self.GOLDEN_DICE_MULTIPLIER_VALUES))]
            try:
                self.canvas.itemconfigure(item, text=f'×{value}', fill='#fff2a3')
            except tk.TclError:
                return
            self._queue_animation(40, self._animate_golden_dice_multiplier_row,
                                  bet_type, step + 1)
            return
        value = int(self.golden_dice_multipliers.get(bet_type, 2))
        try:
            self.canvas.itemconfigure(item, text=f'×{value}', fill='#ffd84a')
        except tk.TclError:
            pass

    def _animate_golden_dice_roll(self, on_complete=None):
        if self._closing or not self.treasure_panel_active or self.game_mode != 'goldendice':
            return
        if self.golden_dice_animation_frames_left > 0:
            for index, item in enumerate(self.golden_dice_panel_items):
                value = secrets.randbelow(6) + 1
                self._set_golden_dice_item_face(item, value)
                base_x = (self.HISTORY_X0+self.HISTORY_X1)/2 + (-53 if index == 0 else 53)
                base_y = 138
                try:
                    self.canvas.coords(item,
                                       base_x + secrets.randbelow(17)-8,
                                       base_y + secrets.randbelow(17)-8)
                except tk.TclError:
                    pass
            self.golden_dice_animation_frames_left -= 1
            self._queue_animation(self.golden_dice_animation_delay_ms,
                                  self._animate_golden_dice_roll, on_complete)
            return

        for index, (item, value) in enumerate(zip(self.golden_dice_panel_items,
                                                  self.current_golden_dice)):
            base_x = (self.HISTORY_X0+self.HISTORY_X1)/2 + (-53 if index == 0 else 53)
            try:
                self.canvas.coords(item, base_x, 138)
            except tk.TclError:
                pass
            self._set_golden_dice_item_face(item, value)

        total = sum(self.current_golden_dice)
        self.golden_dice_active = total in (8, 9)
        try:
            self.canvas.itemconfigure(self.golden_dice_total_text,
                                      text=f'{self.current_golden_dice[0]} + {self.current_golden_dice[1]} = {total}点')
            self.canvas.itemconfigure(
                self.golden_dice_status_text,
                text='黄金赔率已激活！' if self.golden_dice_active else '未中8/9 · 使用基础赔率',
                fill='#ffd84a' if self.golden_dice_active else '#b8aaa0')
        except tk.TclError:
            pass
        for item in self.golden_dice_multiplier_text_items.values():
            try:
                self.canvas.itemconfigure(item,
                    fill='#ffd84a' if self.golden_dice_active else '#746b64')
            except tk.TclError:
                pass
        self._update_golden_dice_board_odds()
        if callable(on_complete):
            self._queue_animation(250, on_complete)

    def _update_golden_dice_board_odds(self):
        if self.game_mode != 'goldendice':
            return
        for bet_type, base_profit in self.GOLDEN_DICE_BASE_PROFIT_ODDS.items():
            spot = self.bet_spots.get((bet_type, None))
            if not spot:
                continue
            if self.golden_dice_active:
                mult = int(self.golden_dice_multipliers.get(bet_type, 1))
                text = f'{format_two_decimals(base_profit * mult)}:1'
                outline, width = '#ffd42a', 4
            else:
                text = spot.get('base_odds', f'{format_two_decimals(base_profit)}:1')
                outline, width = spot.get('normal_outline', '#d5cbbd'), spot.get('normal_outline_width', 1)
            try:
                self.canvas.itemconfigure(spot.get('odds_item'), text=text, state='normal')
                self.canvas.itemconfigure(spot.get('rect_id'), outline=outline, width=width)
            except tk.TclError:
                pass

    # ------------------------------------------------------- Treasure Pot mode
    def _weighted_sample_without_replacement(self, items, weights, count, rng):
        pool = list(items)
        pool_weights = [float(w) for w in weights]
        chosen = []
        for _ in range(min(int(count), len(pool))):
            pick = rng.choices(range(len(pool)), weights=pool_weights, k=1)[0]
            chosen.append(pool.pop(pick))
            pool_weights.pop(pick)
        return chosen

    def _prepare_treasure_round(self, on_complete=None):
        """Prepare Treasure or XXX random-card panel before the real deal."""
        faces = [(suit, rank) for suit in BaccaratEngine.SUITS for rank in BaccaratEngine.RANKS]
        rng = random.SystemRandom()

        if self.game_mode == 'xxx':
            # Probability-only randomisation: choose the count first, then sample
            # that many DISTINCT faces uniformly from the 52-face vocabulary.
            # Each chosen face independently rolls 2X, 3X, 4X, 5X, 8X or 10X.
            # No wager type, outcome, bankroll or current RTP is consulted here.
            count = rng.choices(self.XXX_COUNT_VALUES,
                                weights=self.XXX_COUNT_WEIGHTS, k=1)[0]
            chosen = rng.sample(faces, int(count))
            self.current_golden_cards = [
                (card, rng.choices(self.XXX_MULTIPLIER_VALUES,
                                   weights=self.XXX_MULTIPLIER_WEIGHTS, k=1)[0])
                for card in chosen
            ]
        else:
            chosen = rng.sample(faces, 5)
            multiplier_values = (2, 3, 5, 8)
            multiplier_weights = (55, 25, 14, 6)
            self.current_golden_cards = [
                (card, rng.choices(multiplier_values, weights=multiplier_weights, k=1)[0])
                for card in chosen
            ]

        self.current_golden_map = {tuple(card): int(mult) for card, mult in self.current_golden_cards}
        self._show_treasure_panel_shell()
        self.update_golden_bet_visuals()
        self._animate_treasure_card_fade(0, on_complete)

    def _show_treasure_panel_shell(self):
        self.treasure_panel_active = True
        self.canvas.delete('history_dynamic')
        self.canvas.delete('treasure_panel')
        self.treasure_panel_images = []
        self.treasure_animation_refs = {}
        self.treasure_panel_card_items = []
        self.treasure_panel_multiplier_items = []
        self.treasure_panel_rule_cells = {}
        x0, y0, x1, y1 = self.HISTORY_X0, 4, self.HISTORY_X1, 620
        c = self.canvas
        is_xxx = self.game_mode == 'xxx'
        title = 'XXX' if is_xxx else '聚宝盆'
        cards_label = '本局黄金扑克' if is_xxx else '本局黄金扑克'
        c.create_rectangle(x0, y0, x1, y1, fill='#17120f', outline='#d0aa3f', width=3,
                           tags='treasure_panel')
        c.create_text((x0+x1)/2, 30, text=title, font=('Arial', 22, 'bold'),
                      fill='#ffd84a', tags='treasure_panel')
        fee_pct = '50%' if is_xxx else '20%'
        fee_label = ('本局手续费 50%' if is_xxx else '本局手续费 20%')
        c.create_text((x0+x1)/2, 60, text=f'{fee_label} · ${self.treasure_pot_amount:,.0f}',
                      font=('Arial', 13, 'bold'), fill='white', tags='treasure_panel')
        c.create_text((x0+x1)/2, 87, text=cards_label, font=('Arial', 12, 'bold'),
                      fill='#e8d8b4', tags='treasure_panel')

        if is_xxx:
            # XXX temporary page: Golden Duel rules shown as a two-column table.
            c.create_text((x0+x1)/2, 392, text='黄金对决', font=('Arial',16,'bold'),
                          fill='#ffd84a', tags='treasure_panel')
            duel_rows = (
                ('双方都有最少 1 张黄金牌', '15:1'),
                ('双方都有黄金牌 + 和局', '35:1'),
                ('至少 1 方出现黄金对子', '100:1'),
                ('双方都是黄金对子', '3000:1'),
                ('5 张一样的黄金扑克', '50000:1'),
                ('6 张一样的黄金扑克', '500000:1'),
            )
            table_x0, table_x1 = x0 + 16, x1 - 16
            table_y0 = 414
            row_h = 30
            split_x = table_x0 + (table_x1 - table_x0) * 3 / 5
            table_y1 = table_y0 + row_h * len(duel_rows)
            c.create_rectangle(table_x0, table_y0, table_x1, table_y1,
                               fill='#211811', outline='#8d765e', width=1,
                               tags='treasure_panel')
            c.create_line(split_x, table_y0, split_x, table_y1,
                          fill='#8d765e', width=1, tags='treasure_panel')
            for idx, (label, odds) in enumerate(duel_rows):
                y0_row = table_y0 + idx * row_h
                y1_row = y0_row + row_h
                # Right 2/5 odds cell gets its own background so only the winning
                # payout cell can flash gold while the left rule text stays fixed.
                odds_bg = c.create_rectangle(
                    split_x + 1, y0_row + 1, table_x1 - 1, y1_row - 1,
                    fill='#211811', outline='', tags='treasure_panel')
                if idx:
                    c.create_line(table_x0, y0_row, table_x1, y0_row,
                                  fill='#665240', width=1, tags='treasure_panel')
                cy = y0_row + row_h / 2
                c.create_text(table_x0 + 8, cy, text=label, anchor='w',
                              font=('Arial',9,'bold'), fill='white',
                              tags='treasure_panel')
                odds_text = c.create_text(
                    (split_x + table_x1) / 2, cy, text=odds, anchor='center',
                    font=('Arial',10,'bold'), fill='#ffd84a', tags='treasure_panel')
                self.treasure_panel_rule_cells[idx + 1] = (odds_bg, odds_text)
        else:
            # Treasure temporary page: Golden Hunter payable counts shown as a table.
            # The one-card loss row and all fee/explanation footers are omitted.
            c.create_text((x0+x1)/2, 404, text='黄金猎手', font=('Arial',16,'bold'),
                          fill='#ffd84a', tags='treasure_panel')
            hunter_rows = (
                ('2张牌', '3:1'),
                ('3张牌', '25:1'),
                ('4张牌', '155:1'),
                ('5张牌', '3150:1'),
                ('6张牌', '51000:1'),
            )
            table_x0, table_x1 = x0 + 28, x1 - 28
            table_y0 = 430
            row_h = 31
            split_x = table_x0 + (table_x1 - table_x0) * 3 / 5
            table_y1 = table_y0 + row_h * len(hunter_rows)
            c.create_rectangle(table_x0, table_y0, table_x1, table_y1,
                               fill='#211811', outline='#8d765e', width=1,
                               tags='treasure_panel')
            c.create_line(split_x, table_y0, split_x, table_y1,
                          fill='#8d765e', width=1, tags='treasure_panel')
            for idx, (label, odds) in enumerate(hunter_rows):
                y0_row = table_y0 + idx * row_h
                y1_row = y0_row + row_h
                odds_bg = c.create_rectangle(
                    split_x + 1, y0_row + 1, table_x1 - 1, y1_row - 1,
                    fill='#211811', outline='', tags='treasure_panel')
                if idx:
                    c.create_line(table_x0, y0_row, table_x1, y0_row,
                                  fill='#665240', width=1, tags='treasure_panel')
                cy = y0_row + row_h / 2
                c.create_text(table_x0 + 8, cy, text=label, anchor='w',
                              font=('Arial',11,'bold'), fill='white',
                              tags='treasure_panel')
                odds_text = c.create_text(
                    (split_x + table_x1) / 2, cy, text=odds, anchor='center',
                    font=('Arial',11,'bold'), fill='#ffd84a', tags='treasure_panel')
                self.treasure_panel_rule_cells[idx + 2] = (odds_bg, odds_text)
        c.tag_raise('treasure_panel')

    def _treasure_panel_positions(self):
        """Centre 4-8 cards in two rows; Treasure's five-card layout also stays centred."""
        count = len(self.current_golden_cards)
        panel_center_x = (self.HISTORY_X0 + self.HISTORY_X1) / 2
        card_w = 70
        gap = 12 if count >= 7 else 18
        if count <= 4:
            row_counts = (2, count - 2)
        elif count == 5:
            row_counts = (3, 2)
        elif count == 6:
            row_counts = (3, 3)
        elif count == 7:
            row_counts = (4, 3)
        else:
            row_counts = (4, 4)
        result = []
        for row, row_count in enumerate(row_counts):
            if row_count <= 0:
                continue
            total_w = row_count * card_w + (row_count - 1) * gap
            start_x = panel_center_x - total_w / 2
            y = 112 if row == 0 else 275
            result.extend((start_x + i * (card_w + gap), y) for i in range(row_count))
        return result[:count]

    def _treasure_small_pil(self, card):
        if Image is None:
            return None
        base = self.golden_card_pil.get(tuple(card))
        if base is None:
            base = self.external_card_pil.get(tuple(card))
        if base is None:
            return None
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        return base.convert('RGBA').resize((70, 98), resample)

    def _animate_treasure_card_fade(self, index, on_complete):
        if self._closing or not self.treasure_panel_active:
            return
        if index >= len(self.current_golden_cards):
            self._queue_animation(20, self._animate_treasure_multiplier_drop, on_complete)
            return

        card, _mult = self.current_golden_cards[index]
        px, py = self._treasure_panel_positions()[index]
        c = self.canvas
        base = self._treasure_small_pil(card)
        steps = 20                 # 20 * 25ms = 0.50 seconds
        frame_ms = 25

        if base is None or ImageTk is None:
            # Pillow-less fallback: approximate the 0.5s fade with a staged
            # outline, while preserving the same sequencing duration.
            rect = c.create_rectangle(px, py, px+70, py+98, fill='#f8efd1',
                                      outline='#ffd84a', width=3,
                                      stipple='gray75', tags='treasure_panel')
            txt = c.create_text(px+35, py+49, text=self.card_text(card),
                                font=('Arial',14,'bold'), fill='#222',
                                tags='treasure_panel')
            self.treasure_panel_card_items.extend((rect, txt))
            self._queue_animation(500, self._animate_treasure_card_fade, index + 1, on_complete)
            return

        # Create one canvas image and replace its PhotoImage every frame.  The
        # references dictionary prevents Tk from garbage-collecting the active
        # frame during the animation.
        first = base.copy()
        first.putalpha(0)
        photo = ImageTk.PhotoImage(first, master=self)
        item = c.create_image(px, py, image=photo, anchor='nw', tags='treasure_panel')
        self.treasure_animation_refs[item] = photo
        self.treasure_panel_card_items.append(item)

        def fade_step(step=0):
            if self._closing or not self.treasure_panel_active:
                return
            alpha = max(0, min(255, int(round(255 * step / steps))))
            frame = base.copy()
            # Golden card artwork is opaque in normal use; applying a global
            # alpha gives a clean true fade without changing its RGB colours.
            frame.putalpha(alpha)
            frame_photo = ImageTk.PhotoImage(frame, master=self)
            self.treasure_animation_refs[item] = frame_photo
            try:
                c.itemconfigure(item, image=frame_photo)
            except tk.TclError:
                return
            if step < steps:
                self._queue_animation(frame_ms, fade_step, step + 1)
            else:
                # Keep a stable final image reference and only then start the
                # next card. No overlap between the per-card 0.5-second fades.
                final_photo = ImageTk.PhotoImage(base, master=self)
                self.treasure_animation_refs[item] = final_photo
                c.itemconfigure(item, image=final_photo)
                self._queue_animation(0, self._animate_treasure_card_fade, index + 1, on_complete)

        fade_step(0)

    def _animate_treasure_multiplier_drop(self, on_complete):
        """Drop all current multiplier badges simultaneously over 0.5 seconds."""
        if self._closing or not self.treasure_panel_active:
            return
        c = self.canvas
        positions = self._treasure_panel_positions()
        self.treasure_panel_multiplier_items = []
        start_y = 72
        finals = []
        for (_card, mult), (px, py) in zip(self.current_golden_cards, positions):
            cx = px + 62
            final_y = py + 7
            oval = c.create_oval(cx-14, start_y-14, cx+14, start_y+14,
                                 fill='#ffffff', outline='#d6d6d6', width=2,
                                 tags='treasure_panel')
            text = c.create_text(cx, start_y, text=f'{int(mult)}X', font=('Arial',9,'bold'),
                                 fill='#000000', tags='treasure_panel')
            self.treasure_panel_multiplier_items.extend((oval, text))
            finals.append((oval, text, cx, final_y))
        c.tag_raise('treasure_panel')

        steps = 20                 # 20 * 25ms = 0.50 seconds
        frame_ms = 25
        def drop_step(step=0):
            if self._closing or not self.treasure_panel_active:
                return
            ratio = min(1.0, step / float(steps))
            # Ease-out cubic: fast initial fall, gentle landing.
            eased = 1.0 - (1.0 - ratio) ** 3
            for oval, text, cx, final_y in finals:
                cy = start_y + (final_y - start_y) * eased
                c.coords(oval, cx-14, cy-14, cx+14, cy+14)
                c.coords(text, cx, cy)
            if step < steps:
                self._queue_animation(frame_ms, drop_step, step + 1)
            elif callable(on_complete):
                # The very first Player card may only be dealt after all current
                # multiplier badges have landed.
                self._queue_animation(0, on_complete)
        drop_step(0)

    def _hide_treasure_panel(self):
        self.treasure_panel_active = False
        self.canvas.delete('treasure_panel')
        self.treasure_panel_images = []
        self.treasure_animation_refs = {}
        self.treasure_panel_card_items = []
        self.treasure_panel_multiplier_items = []
        self.treasure_panel_rule_cells = {}
        self._draw_history_content()
        self.update_history_table()

    def _gold_multiplier_for_revealed(self, bet_type):
        mapping = self.current_golden_map
        p = list(self.revealed_cards.get('Player', []))
        b = list(self.revealed_cards.get('Banker', []))
        if bet_type == 'Player': cards = p
        elif bet_type == 'Banker': cards = b
        elif bet_type == 'Tie': cards = p + b
        elif bet_type == 'Pair Player': cards = p[:2]
        elif bet_type == 'Pair Banker': cards = b[:2]
        else: return 1
        m = 1
        for card in cards:
            m *= int(mapping.get(tuple(card), 1))
        return max(1, m)

    def _base_profit_odds_for_treasure(self, bet_type):
        if self.game_mode == 'xxx':
            return {'Player':1.0, 'Banker':0.97, 'Tie':2.85,
                    'Pair Player':8.0, 'Pair Banker':8.0}.get(bet_type)
        return {'Player':1.0, 'Banker':0.95, 'Tie':5.0,
                'Pair Player':9.0, 'Pair Banker':9.0}.get(bet_type)

    def _effective_golden_multiplier(self, bet_type, raw_multiplier):
        # XXX no longer applies a hidden RTP scale to payout odds.  The integer
        # multiplier shown on the falling golden badge is the multiplier used
        # by both the betting-area odds and settlement calculation.
        _ = bet_type
        return float(raw_multiplier)

    def update_golden_bet_visuals(self):
        """Refresh golden borders and temporary golden-odds badges."""
        self.canvas.delete('golden_bet_dynamic')
        for _key, spot in self.bet_spots.items():
            rect = spot.get('rect_id')
            if rect:
                try:
                    self.canvas.itemconfigure(rect,
                                              outline=spot.get('normal_outline','#d5cbbd'),
                                              width=spot.get('normal_outline_width',1))
                except tk.TclError:
                    pass
            odds_item = spot.get('odds_item')
            if odds_item:
                try:
                    self.canvas.itemconfigure(odds_item, state='normal')
                    self.canvas.coords(odds_item, spot.get('odds_base_x'), spot.get('odds_y'))
                except tk.TclError:
                    pass

        if self.game_mode not in ('treasure', 'xxx') or not self.current_golden_map:
            return

        for bet_type in ('Player','Banker','Tie','Pair Player','Pair Banker'):
            spot = self.bet_spots.get((bet_type,None))
            if not spot:
                continue
            raw_mult = self._gold_multiplier_for_revealed(bet_type)
            if raw_mult <= 1:
                continue
            mult = self._effective_golden_multiplier(bet_type, raw_mult)

            rect = spot.get('rect_id')
            if rect:
                self.canvas.itemconfigure(rect, outline='#ffd42a', width=4)
            base = self._base_profit_odds_for_treasure(bet_type)
            if base is None:
                continue
            latest = round_two_decimals_value(base * mult)
            odds_item = spot.get('odds_item')
            bx = spot.get('odds_base_x', (spot['bounds'][0] + spot['bounds'][2]) / 2)
            by = spot.get('odds_y', spot['bounds'][3] - 13)
            if odds_item:
                self.canvas.itemconfigure(odds_item, state='hidden')

            # Golden icon replaces the *visual location* of the printed odds;
            # the base odds item itself is preserved and restored when needed.
            x0, _y0, x1, _y1 = spot['bounds']
            half_w = min(36.0, max(27.0, (x1-x0) * 0.16))
            self.canvas.create_oval(bx-half_w, by-15, bx+half_w, by+15,
                                    fill='#e3b51d', outline='#fff2a3', width=2,
                                    tags=('golden_bet_dynamic', spot['tag']))
            self.canvas.create_text(bx, by, text=f'{format_two_decimals(latest)}:1', font=('Arial',12,'bold'),
                                    fill='#201700', tags=('golden_bet_dynamic', spot['tag']))
        self.canvas.tag_raise('bet_chip_dynamic')

    # ---------------------------------------------------------- shoe / cut / burn
    def _show_cut_dialog(self, second=False):
        """Casino-style visual cut with a physical packet-swap animation.

        The player drags a yellow cut card anywhere in the valid 65..349
        range.  Enter chooses a random legal position.  Confirming does not
        immediately close the dialog: the shoe visibly separates into the two
        packets created by the cut, the front packet is lifted, the packets
        exchange positions, and the lifted packet is lowered back onto the
        shoe.  Only after that animation finishes is the cut position returned
        to start_new_shoe_cut(), which then starts the burn-card procedure.
        """
        dialog_w, dialog_h = 760, 410
        dialog = tk.Toplevel(self.winfo_toplevel())
        dialog.title('切牌')
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.configure(bg='#0b4038')

        self.update_idletasks()
        px, py = self.winfo_rootx(), self.winfo_rooty()
        pw, ph = max(1, self.winfo_width()), max(1, self.winfo_height())
        x = px + (pw - dialog_w) // 2
        y = py + (ph - dialog_h) // 2
        dialog.geometry(f'{dialog_w}x{dialog_h}+{x}+{y}')

        cv = tk.Canvas(dialog, width=760, height=338, bg='#0b4038',
                       highlightthickness=0, cursor='hand2')
        cv.pack(fill=tk.X, side=tk.TOP)

        cv.create_oval(34, 20, 726, 318, fill='#08352f', outline='#1a6e61', width=2,
                       tags='cut_table_static')
        cv.create_text(380, 48, text='拖动黄色切牌卡',
                       font=('微软雅黑', 18, 'bold'), fill='white', tags='cut_instruction')
        cv.create_text(380, 76,
                       text='确认后会将两叠牌交换位置，再进入烧牌流程',
                       font=('微软雅黑', 10), fill='#b7d7cf', tags='cut_instruction')
        if second:
            cv.create_text(380, 96, text='新牌靴', font=('微软雅黑', 10),
                           fill='#e5dba4', tags='cut_instruction')

        shoe_x0, shoe_x1 = 86.0, 674.0
        shoe_y0, shoe_y1 = 132.0, 232.0
        deck_width = shoe_x1 - shoe_x0

        # Wooden shoe/frame remains still while the two card packets move.
        cv.create_rectangle(shoe_x0 - 14, shoe_y0 - 16, shoe_x1 + 16, shoe_y1 + 17,
                            fill='#2a211b', outline='#a48763', width=3,
                            tags='shoe_frame')

        def draw_full_shoe():
            cv.delete('shoe_deck_static')
            cv.create_rectangle(shoe_x0, shoe_y0, shoe_x1, shoe_y1,
                                fill='#eee8dc', outline='#d0c5b2', width=2,
                                tags='shoe_deck_static')
            for i in range(105):
                xx = shoe_x0 + deck_width * i / 104.0
                shade = '#c7bca9' if i % 2 else '#e0d7c8'
                cv.create_line(xx, shoe_y0 + 2, xx, shoe_y1 - 2, fill=shade,
                               tags='shoe_deck_static')
            # Back-design rails help the pack read as a physical shoe rather
            # than a generic slider.
            cv.create_rectangle(shoe_x0 + 8, shoe_y0 + 8, shoe_x1 - 8, shoe_y1 - 8,
                                outline='#b61f2e', width=3, tags='shoe_deck_static')
            cv.create_line(shoe_x0 + 13, shoe_y0 + 13, shoe_x1 - 13, shoe_y1 - 13,
                           fill='#b61f2e', width=2, tags='shoe_deck_static')
            cv.create_line(shoe_x1 - 13, shoe_y0 + 13, shoe_x0 + 13, shoe_y1 - 13,
                           fill='#b61f2e', width=2, tags='shoe_deck_static')

        draw_full_shoe()

        valid_left = shoe_x0 + deck_width * 65 / 416.0
        valid_right = shoe_x0 + deck_width * 349 / 416.0
        cv.create_line(valid_left, shoe_y1 + 28, valid_right, shoe_y1 + 28,
                       fill='#8ec8b8', width=4, tags='cut_rail')
        cv.create_oval(valid_left-4, shoe_y1+24, valid_left+4, shoe_y1+32,
                       fill='#d9eee8', outline='', tags='cut_rail')
        cv.create_oval(valid_right-4, shoe_y1+24, valid_right+4, shoe_y1+32,
                       fill='#d9eee8', outline='', tags='cut_rail')

        rng = random.SystemRandom()
        selected = {'value': rng.randint(120, 300)}
        animating = {'value': False}
        result = [None]

        def value_to_x(value):
            return shoe_x0 + deck_width * value / 416.0

        def x_to_value(xx):
            ratio = (xx - shoe_x0) / float(deck_width)
            value = int(round(ratio * 416))
            return max(65, min(349, value))

        cut_tag = 'casino_cut_card'

        def draw_cut_card():
            cv.delete(cut_tag)
            xx = value_to_x(selected['value'])
            cv.create_rectangle(xx - 7, shoe_y0 - 31, xx + 7, shoe_y1 + 24,
                                fill='#f3df42', outline='#75620b', width=2,
                                tags=cut_tag)
            cv.create_rectangle(xx - 4, shoe_y0 - 26, xx + 4, shoe_y0 - 6,
                                fill='#fff59d', outline='', tags=cut_tag)
            cv.tag_raise(cut_tag)

        def move_cut(event):
            if animating['value']:
                return 'break'
            selected['value'] = x_to_value(event.x)
            draw_cut_card()

        cv.bind('<Button-1>', move_cut)
        cv.bind('<B1-Motion>', move_cut)
        cv.tag_bind(cut_tag, '<B1-Motion>', move_cut)
        cv.tag_bind(cut_tag, '<Button-1>', move_cut)
        draw_cut_card()

        cv.create_text(380, 292, text='ENTER = 随机切牌',
                       font=('微软雅黑', 10, 'bold'), fill='#d9eee8',
                       tags='cut_enter_hint')

        # Packet drawing helpers -------------------------------------------------
        def draw_packet(tag, x0, y0, width, height, edge_count=36):
            width = max(18.0, float(width))
            cv.create_rectangle(x0, y0, x0+width, y0+height,
                                fill='#eee8dc', outline='#d0c5b2', width=2,
                                tags=(tag, 'cut_packet'))
            # Proportional card-edge lines; clamp the number so both packets
            # visibly retain a card-stack texture even at extreme legal cuts.
            lines = max(8, min(edge_count, int(width / 5.0)))
            for i in range(1, lines):
                xx = x0 + width * i / lines
                cv.create_line(xx, y0+3, xx, y0+height-3,
                               fill='#c6baa7' if i % 2 else '#ddd3c3',
                               tags=(tag, 'cut_packet'))
            cv.create_rectangle(x0+5, y0+6, x0+width-5, y0+height-6,
                                outline='#b61f2e', width=2,
                                tags=(tag, 'cut_packet'))

        def ease(t):
            # Smoothstep keeps the packets from looking like linear UI sliders.
            t = max(0.0, min(1.0, float(t)))
            return t*t*(3.0 - 2.0*t)

        confirm_btn = None

        def finish_cut_animation():
            cv.delete('cut_packet')
            cv.delete(cut_tag)
            cv.delete('cut_rail')
            # Show the reassembled shoe for a short beat before burn starts.
            draw_full_shoe()
            cv.itemconfigure('cut_instruction', state='hidden')
            cv.create_text(380, 292, text='准备烧牌…',
                           font=('微软雅黑', 11, 'bold'), fill='white',
                           tags='cut_done')
            result[0] = int(selected['value'])
            dialog.after(260, dialog.destroy)

        def begin_cut_animation(value=None):
            if animating['value']:
                return 'break'
            if value is not None:
                selected['value'] = max(65, min(349, int(value)))
                draw_cut_card()
            animating['value'] = True
            if confirm_btn is not None:
                confirm_btn.config(state=tk.DISABLED, text='切牌中…')
            cv.config(cursor='arrow')
            cv.unbind('<Button-1>')
            cv.unbind('<B1-Motion>')
            cv.delete('shoe_deck_static')
            cv.delete('cut_enter_hint')
            cv.itemconfigure('cut_instruction', state='hidden')
            cv.create_text(380, 55, text='正在切牌',
                           font=('微软雅黑', 18, 'bold'), fill='white', tags='cut_anim_text')
            cv.create_text(380, 82, text='分牌 → 调换 → 合并',
                           font=('微软雅黑', 10), fill='#b7d7cf', tags='cut_anim_text')

            split_x = value_to_x(selected['value'])
            left_w = max(18.0, split_x - shoe_x0)
            right_w = max(18.0, shoe_x1 - split_x)
            # Avoid any visual gap caused by extreme width clamping. Legal
            # 65..349 already guarantees useful widths, so this is defensive.
            left_w = min(deck_width-18.0, left_w)
            right_w = deck_width-left_w

            tag_a, tag_b = 'cut_packet_A', 'cut_packet_B'
            draw_packet(tag_a, shoe_x0, shoe_y0, left_w, shoe_y1-shoe_y0)
            draw_packet(tag_b, shoe_x0+left_w, shoe_y0, right_w, shoe_y1-shoe_y0)
            cv.delete(cut_tag)

            # A = cards before the cut. In a casino cut this packet is lifted,
            # the remaining packet slides into the front, then A is placed at
            # the rear. The engine performs the identical rotation afterwards.
            start_a = [shoe_x0, shoe_y0]
            start_b = [shoe_x0+left_w, shoe_y0]
            lift_y = shoe_y0 - 72.0
            final_b_x = shoe_x0
            final_a_x = shoe_x0 + right_w

            def move_tag_to(tag, current, target_x, target_y):
                dx, dy = target_x-current[0], target_y-current[1]
                cv.move(tag, dx, dy)
                current[0], current[1] = target_x, target_y

            current_a = start_a[:]
            current_b = start_b[:]

            # Phase 1: lift the front packet clear of the shoe.
            phase1_steps, phase1_ms = 14, 22
            def phase1(step=0):
                t = ease(step/phase1_steps)
                move_tag_to(tag_a, current_a, shoe_x0, shoe_y0+(lift_y-shoe_y0)*t)
                cv.tag_raise(tag_a)
                if step < phase1_steps:
                    dialog.after(phase1_ms, phase1, step+1)
                else:
                    phase2(0)

            # Phase 2: slide the remaining packet to the front while the lifted
            # packet travels to the rear position above it.
            phase2_steps, phase2_ms = 18, 22
            def phase2(step=0):
                t = ease(step/phase2_steps)
                move_tag_to(tag_b, current_b,
                            start_b[0] + (final_b_x-start_b[0])*t,
                            shoe_y0)
                move_tag_to(tag_a, current_a,
                            shoe_x0 + (final_a_x-shoe_x0)*t,
                            lift_y)
                cv.tag_raise(tag_a)
                if step < phase2_steps:
                    dialog.after(phase2_ms, phase2, step+1)
                else:
                    phase3(0)

            # Phase 3: lower the first packet into the rear of the shoe.
            phase3_steps, phase3_ms = 14, 22
            def phase3(step=0):
                t = ease(step/phase3_steps)
                move_tag_to(tag_a, current_a, final_a_x,
                            lift_y + (shoe_y0-lift_y)*t)
                cv.tag_raise(tag_a)
                if step < phase3_steps:
                    dialog.after(phase3_ms, phase3, step+1)
                else:
                    # A small compression beat visually seals the two packets.
                    cv.create_line(final_a_x, shoe_y0+3, final_a_x, shoe_y1-3,
                                   fill='#9f927d', width=1, tags='cut_packet')
                    dialog.after(180, finish_cut_animation)

            phase1(0)
            return 'break'

        def confirm():
            begin_cut_animation(selected['value'])

        def random_confirm(_event=None):
            if animating['value']:
                return 'break'
            selected['value'] = rng.randint(65, 349)
            draw_cut_card()
            # Enter is a complete random-cut action, not merely a random cursor
            # move: immediately play the same physical packet-swap animation.
            dialog.after(100, begin_cut_animation, selected['value'])
            return 'break'

        confirm_btn = tk.Button(
            dialog, text='确认切牌', command=confirm, width=18,
            font=('微软雅黑', 13, 'bold'), bg='#d8bd4b', fg='#15110d',
            activebackground='#ead56f', relief=tk.FLAT, bd=0, pady=8)
        confirm_btn.pack(pady=(4, 12))

        dialog.bind('<Return>', random_confirm)
        dialog.bind('<KP_Enter>', random_confirm)
        dialog.after(20, dialog.focus_force)
        # Closing the window is treated like confirming the currently selected
        # cut, and still plays the physical cut animation first.
        dialog.protocol('WM_DELETE_WINDOW', confirm)
        self.wait_window(dialog)
        return int(result[0] if result[0] is not None else selected['value'])

    def start_new_shoe_cut(self, second=False):
        if self._closing or self.animation_running or self.settlement_running:
            return
        self.accept_bets = False
        self.animation_running = True
        self.update_control_states()
        cut_position = self._show_cut_dialog(second)
        # Cutting a new shoe completely resets the two temporary sections in
        # Baccarat.json, while lifetime statistic_data is preserved.
        self.clear_shoe_temp_sections()
        self.engine.new_shoe()
        self.engine.cut_shoe(cut_position)
        self.save_temp_data(burn_complete=False)
        self.clear_card_display()
        self.canvas.itemconfigure(self.animation_phase_text, text='切牌完成 · 烧牌')
        self._start_initial_burn_animation()

    def _start_initial_burn_animation(self):
        if self.engine.remaining_cards() <= 0:
            self._finish_initial_burn()
            return
        first_card = self.engine.draw_card()
        self.save_temp_data(burn_complete=False)
        target_x = (self.GAME_X0 + self.GAME_X1) / 2 - 50
        target_y = 100
        back = self._back_photo(False)
        card_id = self.canvas.create_image((self.GAME_X0 + self.GAME_X1) / 2 - 50, -150,
                                           image=back, anchor='nw',
                                           tags=('burn_card', 'animation'))
        self.card_item_ids.append(card_id)
        info = ('Burn', card_id, 0)
        def arrive():
            self._flip_burn_card(info, first_card, 0)
        def move(step=0):
            ratio = min(1.0, step / 30.0)
            x = (self.GAME_X0 + self.GAME_X1) / 2 - 50
            y = -150 + (target_y + 150) * ratio
            self.canvas.coords(card_id, x, y)
            if step < 30:
                self._queue_animation(10, move, step + 1)
            else:
                arrive()
        move()

    def _flip_burn_card(self, card_info, card, step=0):
        _hand, card_id, _index = card_info
        steps = 12
        if step > steps:
            image = self._face_photo(card, False)
            if image is not None:
                self.canvas.itemconfigure(card_id, image=image)
            burn_value = min(10, BaccaratEngine.card_value(card) or 10)
            # 10/J/Q/K burn 10, A burn 1; numbered cards burn face value.
            rank = card[1]
            burn_value = 10 if rank in ('10', 'J', 'Q', 'K') else (1 if rank == 'A' else int(rank))
            self._queue_animation(500, self._burn_back_cards, burn_value, 0, [])
            return
        half = steps // 2
        if step <= half:
            ratio, use_back = 1 - step / float(half), True
        else:
            ratio, use_back = (step - half) / float(half), False
        width = max(1, int(100 * ratio))
        image = self._create_scaled_flip_image(card, width, 140, use_back=use_back, rotated=False)
        if image is not None:
            self._temp_flip_images[card_id] = image
            self.canvas.itemconfigure(card_id, image=image)
            base_x = (self.GAME_X0 + self.GAME_X1) / 2 - 50
            self.canvas.coords(card_id, base_x + (100 - width) / 2, 100)
        self._queue_animation(20, self._flip_burn_card, card_info, card, step + 1)

    def _burn_back_cards(self, total, index, ids):
        if index >= total or self.engine.remaining_cards() <= 0:
            self._queue_animation(700, self._finish_initial_burn)
            return
        self.engine.draw_card()
        self.save_temp_data(burn_complete=False)
        start_x = (self.GAME_X0 + self.GAME_X1) / 2 - 50
        start_y = -150
        col = index % 5
        row = index // 5
        target_x = 105 + col * 112
        target_y = 242 + row * 148
        card_id = self.canvas.create_image(start_x, start_y, image=self._back_photo(False),
                                           anchor='nw', tags=('burn_card', 'animation'))
        self.card_item_ids.append(card_id)
        ids.append(card_id)
        def move(step=0):
            ratio = min(1.0, step / 24.0)
            self.canvas.coords(card_id,
                               start_x + (target_x - start_x) * ratio,
                               start_y + (target_y - start_y) * ratio)
            if step < 24:
                self._queue_animation(10, move, step + 1)
            else:
                self._queue_animation(100, self._burn_back_cards, total, index + 1, ids)
        move()

    def _finish_initial_burn(self):
        self.canvas.delete('burn_card')
        self.card_item_ids = [item for item in self.card_item_ids
                              if self.canvas.type(item)]
        self.clear_card_display()
        self.save_temp_data(burn_complete=True)
        self.animation_running = False
        self.accept_bets = True
        self.canvas.itemconfigure(self.animation_phase_text, text='百家乐 BACCARAT')
        self.update_display()

    # ------------------------------------------------------------ dealing/settle
    def handle_enter_deal(self, _event=None):
        button = self.control_buttons.get(getattr(self, 'deal_button', None))
        if button and button['enabled']:
            button['command']()
        return 'break'

    def deal_cards(self):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        if self.engine.needs_shuffle():
            outstanding = self.bet_state.clear_all()
            fee_refund = sum(float(v) for v in self.bet_fee_state.values())
            self.bet_fee_state.clear()
            self.pending_bet_visual_amounts.clear()
            if outstanding > 0 or fee_refund > 0:
                self.balance += outstanding + fee_refund
                if fee_refund > 0:
                    self.treasure_pot_amount = max(0.0, self.treasure_pot_amount - fee_refund)
            self.update_display()
            self.start_new_shoe_cut(True)
            return

        self.accept_bets = False
        self.animation_running = True
        self.pending_bet_visual_amounts.clear()
        current_bets = self.snapshot_bets()
        if current_bets:
            self.last_round_bets = current_bets
        self.undo_stack.clear()
        self.pre_deal_bets = copy.deepcopy(self.bet_state.bets)
        self.pre_deal_fee_total = sum(float(v) for v in self.bet_fee_state.values())
        self.bet_fee_state.clear()
        self.clear_card_display()
        self.current_result = None
        self.result_panel_flash_winner = None
        self.restore_result_panel_colors()
        self.canvas.itemconfigure(self.tie_flash_rect, state='hidden')
        self.update_control_states()

        if self.game_mode == 'goldendice':
            self.canvas.itemconfigure(self.animation_phase_text, text='黄金骰子…')
            self._prepare_golden_dice_round(on_complete=self._begin_actual_round_deal)
        elif self.game_mode in ('treasure', 'xxx'):
            phase = '聚宝盆…' if self.game_mode == 'treasure' else 'XXX…'
            self.canvas.itemconfigure(self.animation_phase_text, text=phase)
            self._prepare_treasure_round(on_complete=self._begin_actual_round_deal)
        else:
            self.current_golden_cards = []
            self.current_golden_map = {}
            self._begin_actual_round_deal()

    def _begin_actual_round_deal(self):
        if self._closing:
            return
        self.current_result = self.engine.deal_round()
        if self.game_mode in ('treasure', 'xxx'):
            self.current_result['_golden_multiplier_map'] = dict(self.current_golden_map)
            self.current_result['golden_cards'] = [
                {'card': list(card), 'multiplier': int(mult)}
                for card, mult in self.current_golden_cards
            ]
        elif self.game_mode == 'goldendice':
            self.current_result['_golden_dice'] = list(self.current_golden_dice)
            self.current_result['_golden_dice_total'] = int(sum(self.current_golden_dice))
            self.current_result['_golden_dice_active'] = bool(self.golden_dice_active)
            self.current_result['_golden_dice_multipliers'] = dict(self.golden_dice_multipliers)
        self.save_temp_data()
        self.canvas.itemconfigure(self.animation_phase_text, text='发牌中…')

        # Preserve V17/V18's physical table order: Player-left, Banker-left,
        # Player-right, Banker-right, with each entrance + flip fully complete
        # before the next card. Treasure/XXX reaches here only after all current
        # multiplier badges have landed.
        self._deal_initial_sequence_original()

    def _queue_animation(self, delay, callback, *args):
        after_id = self.after(delay, callback, *args)
        self.animation_after_ids.append(after_id)
        return after_id

    def _back_photo(self, rotated=False):
        if not rotated:
            return self.external_back_image
        image = getattr(self, '_rotated_back_image', None)
        if image is None and self.external_back_pil is not None and ImageTk is not None:
            self._rotated_back_image = ImageTk.PhotoImage(
                self.external_back_pil.rotate(90, expand=True), master=self)
            image = self._rotated_back_image
        return image or self.external_back_image

    def _face_photo(self, card, rotated=False):
        card = tuple(card)
        if self._is_current_golden(card):
            image = self.golden_card_images_rotated.get(card) if rotated else self.golden_card_images.get(card)
            if image is not None:
                return image
        return self.external_card_images_rotated.get(card) if rotated else self.external_card_images.get(card)

    def _deal_initial_sequence_original(self):
        """Deal and reveal the four initial cards strictly one-by-one."""
        self.initial_card_ids = []
        sequence = (('Player', 1), ('Banker', 0), ('Player', 0), ('Banker', 1))

        def deal_step(position=0):
            if self._closing or not self.current_result:
                return
            if position >= len(sequence):
                self._queue_animation(160, self._process_extra_cards_original)
                return

            hand_type, index = sequence[position]
            hand_key = 'player_hand' if hand_type == 'Player' else 'banker_hand'
            real_card = self.current_result[hand_key][index]

            def arrived(info):
                self._flip_card_original(
                    info, real_card,
                    on_complete=lambda: self._queue_animation(80, deal_step, position + 1)
                )

            self._animate_card_entrance_original(
                hand_type, index, rotated=False, on_arrive=arrived
            )

        deal_step(0)

    def _deal_initial_cards_original(self):
        # Backward-compatible helper retained for callers outside the main flow.
        self.initial_card_ids = []
        for hand_type in ('Player', 'Banker'):
            for index in (0, 1):
                self._animate_card_entrance_original(hand_type, index, rotated=False)

    def _animate_card_entrance_original(self, hand_type, index, rotated=False, on_arrive=None):
        target_x, target_y = self.card_position(hand_type, index)
        base_w = 140 if rotated else 100
        start_x = (self.GAME_X0 + self.GAME_X1) / 2 - base_w / 2
        start_y = -110 if rotated else -150
        back = self._back_photo(rotated=rotated)
        card_id = self.canvas.create_image(start_x, start_y, image=back, anchor='nw',
                                           tags=('animation_card', 'animation'))
        self.card_item_ids.append(card_id)
        info = (hand_type, card_id, index)
        self.initial_card_ids.append(info)

        def move_step(step=0):
            if self._closing:
                return
            ratio = min(1.0, step / 30.0)
            x = start_x + (target_x - start_x) * ratio
            y = start_y + (target_y - start_y) * ratio
            self.canvas.coords(card_id, x, y)
            if step < 30:
                self._queue_animation(10, move_step, step + 1)
            elif callable(on_arrive):
                on_arrive(info)

        move_step(0)
        return info

    def _reveal_initial_phase1_original(self):
        if not self.current_result or len(self.initial_card_ids) < 4:
            return
        # Player opens card #1 first.
        self._flip_card_original(self.initial_card_ids[1], self.current_result['player_hand'][1])
        self._queue_animation(500, self._reveal_initial_phase3_original)

    def _reveal_initial_phase2_original(self):
        # Player opens card #0 second.
        self._flip_card_original(self.initial_card_ids[0], self.current_result['player_hand'][0])
        self._queue_animation(500, self._reveal_initial_phase4_original)

    def _reveal_initial_phase3_original(self):
        self._flip_card_original(self.initial_card_ids[2], self.current_result['banker_hand'][0])
        self._queue_animation(500, self._reveal_initial_phase2_original)

    def _reveal_initial_phase4_original(self):
        self._flip_card_original(self.initial_card_ids[3], self.current_result['banker_hand'][1])
        self._queue_animation(160, self._process_extra_cards_original)

    def _create_scaled_flip_image(self, card, width, height, use_back=False, rotated=False):
        if Image is None or ImageTk is None:
            return self._back_photo(rotated) if use_back else self._face_photo(card, rotated)
        if use_back:
            base = self.external_back_pil
        elif self._is_current_golden(card):
            base = self.golden_card_pil.get(tuple(card)) or self.external_card_pil.get(tuple(card))
        else:
            base = self.external_card_pil.get(tuple(card))
        if base is None:
            return self._back_photo(rotated) if use_back else self._face_photo(card, rotated)
        if rotated:
            base = base.rotate(90, expand=True)
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        image = base.resize((max(1, int(width)), max(1, int(height))), resample)
        return ImageTk.PhotoImage(image, master=self)

    def _flip_card_original(self, card_info, real_card, step=0, on_complete=None):
        hand_type, card_id, index = card_info
        rotated = index == 2
        steps = 12
        orig_w, orig_h = ((140, 100) if rotated else (100, 140))

        if step > steps:
            final_image = self._face_photo(real_card, rotated=rotated)
            if final_image is not None:
                self.canvas.itemconfigure(card_id, image=final_image)
            self.revealed_cards.setdefault(hand_type, []).append(real_card)
            score = BaccaratEngine.score(self.revealed_cards[hand_type])
            target = self.player_score_text if hand_type == 'Player' else self.banker_score_text
            self.canvas.itemconfigure(target, text=str(score))
            if self.game_mode in ('treasure', 'xxx'):
                self.update_golden_bet_visuals()
            target_x, target_y = self.card_position(hand_type, index)
            self.canvas.coords(card_id, target_x, target_y)
            self._temp_flip_images.pop(card_id, None)

            # In Treasure Pot, a matched target card must finish its multiplier
            # drop at the card's current top-right position before the dealing
            # sequence is allowed to continue.
            if self.game_mode in ('treasure', 'xxx') and tuple(real_card) in self.current_golden_map:
                self._animate_dealt_golden_multiplier(
                    hand_type, index, real_card, on_complete=on_complete)
            elif callable(on_complete):
                on_complete()
            return

        half = steps // 2
        if step <= half:
            ratio = 1 - (step / float(half))
            use_back = True
        else:
            ratio = (step - half) / float(half)
            use_back = False
        # Upright cards flip by collapsing their width.  The third card is
        # physically rotated 90 degrees, so its flip axis must rotate with it:
        # collapse/expand HEIGHT instead, keeping the card centred vertically.
        if rotated:
            width = orig_w
            height = max(1, int(orig_h * ratio))
        else:
            width = max(1, int(orig_w * ratio))
            height = orig_h

        image = self._create_scaled_flip_image(real_card, width, height,
                                               use_back=use_back, rotated=rotated)
        if image is not None:
            self._temp_flip_images[card_id] = image
            self.canvas.itemconfigure(card_id, image=image)
            target_x, target_y = self.card_position(hand_type, index)
            if rotated:
                self.canvas.coords(card_id, target_x, target_y + (orig_h - height) / 2)
            else:
                self.canvas.coords(card_id, target_x + (orig_w - width) / 2, target_y)
        self._queue_animation(20, self._flip_card_original, card_info, real_card, step + 1, on_complete)

    def _animate_dealt_golden_multiplier(self, hand_type, index, card, on_complete=None):
        """Drop the matched Treasure multiplier onto the card's top-right corner."""
        multiplier = int(self.current_golden_map.get(tuple(card), 1))
        if self.game_mode not in ('treasure', 'xxx') or multiplier <= 1:
            if callable(on_complete):
                on_complete()
            return

        x, y = self.card_position(hand_type, index)
        rotated = index == 2
        card_w = 140 if rotated else 100

        # 相对 V1 版最终位置：
        # 向右移动 20px，向上移动 20px。
        base_end_x = x + card_w - 18
        base_end_y = y + 18

        end_x = base_end_x + 20
        end_y = base_end_y - 20

        # 第三张补牌是 90° 横向牌。
        # 如果补牌命中黄金牌，倍数圆的最终跌落位置额外向下移动 100px。
        if rotated:
            end_y += 100

        start_y = end_y - 48
        radius = 18

        oval = self.canvas.create_oval(
            end_x - radius,
            start_y - radius,
            end_x + radius,
            start_y + radius,
            fill='white',
            outline='black',
            width=3,
            tags=('dealt_golden_multiplier', 'animation')
        )

        text = self.canvas.create_text(
            end_x,
            start_y,
            text=f'{int(multiplier)}X',
            font=('Arial', 12, 'bold'),
            fill='black',
            tags=('dealt_golden_multiplier', 'animation')
        )

        self.canvas.tag_raise(oval)
        self.canvas.tag_raise(text)

        steps = 18

        def drop_step(step=0):
            if self._closing:
                return

            ratio = min(1.0, step / float(steps))

            # Ease-out：
            # 开始跌落较快，接近最终位置时逐渐减速。
            eased = 1.0 - (1.0 - ratio) ** 3
            cy = start_y + (end_y - start_y) * eased

            self.canvas.coords(
                oval,
                end_x - radius,
                cy - radius,
                end_x + radius,
                cy + radius
            )
            self.canvas.coords(text, end_x, cy)

            self.canvas.tag_raise(oval)
            self.canvas.tag_raise(text)

            if step < steps:
                self._queue_animation(20, drop_step, step + 1)
            elif callable(on_complete):
                self._queue_animation(60, on_complete)

        drop_step(0)

    def _process_extra_cards_original(self):
        if self.current_result and len(self.current_result['player_hand']) > 2:
            self._deal_extra_card_original(
                'Player', 2,
                on_complete=lambda: self._queue_animation(80, self._process_banker_extra_original))
        else:
            self._process_banker_extra_original()

    def _process_banker_extra_original(self):
        if self.current_result and len(self.current_result['banker_hand']) > 2:
            self._deal_extra_card_original(
                'Banker', 2,
                on_complete=lambda: self._queue_animation(80, self.finish_deal))
        else:
            self.finish_deal()

    def _deal_extra_card_original(self, hand_type, index, on_complete=None):
        hand_key = 'player_hand' if hand_type == 'Player' else 'banker_hand'
        card = self.current_result[hand_key][index]

        def arrived(info):
            self._flip_card_original(info, card, on_complete=on_complete)

        self._animate_card_entrance_original(hand_type, index, rotated=True,
                                             on_arrive=arrived)

    def reveal_card(self, hand_type, index, card):
        """Compatibility helper; the main deal now uses the original animation."""
        if self._closing:
            return
        self.draw_card(hand_type, index, card, face_up=True)
        self.revealed_cards.setdefault(hand_type, []).append(card)
        score = BaccaratEngine.score(self.revealed_cards[hand_type])
        target = self.player_score_text if hand_type == 'Player' else self.banker_score_text
        self.canvas.itemconfigure(target, text=str(score))

    def finish_deal(self):
        if self._closing or not self.current_result:
            return
        self.animation_after_ids.clear()
        result = self.current_result
        self.canvas.itemconfigure(self.player_score_text, text=str(result['player_score']))
        self.canvas.itemconfigure(self.banker_score_text, text=str(result['banker_score']))

        # Lucky7 jackpot contribution follows the old project convention (0.8%).
        if self.game_mode == 'lucky7':
            self.jackpot_amount += sum(self.pre_deal_bets.values()) * 0.008
            self.save_jackpot()

        settle = BaccaratEngine.resolve_bets(
            self.pre_deal_bets, result, self.game_mode, self.jackpot_amount)
        self.balance += settle['credit']
        if settle['jackpot_win'] > 0:
            self.jackpot_amount = max(5_000_000.0, self.jackpot_amount - settle['jackpot_win'])
            self.save_jackpot()

        self.last_win_amount = settle['credit']
        self.last_net = settle['net'] - float(self.pre_deal_fee_total or 0.0)
        self.add_history(result)
        self.update_statistic_data(result)

        self.flash_winning_keys = set()
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        self.push_return_amounts = {}
        for outcome in settle['outcomes']:
            key = tuple(outcome['key'])
            if outcome['return_factor'] > 1.0:
                self.flash_winning_keys.add(key)
                self.flash_winner_amounts[key] = float(outcome['return_amount'])
                self.flash_original_amounts[key] = float(self.pre_deal_bets.get(key[0], 0.0))
            elif outcome['status'] == 'push':
                self.push_return_amounts[key[0]] = float(outcome['stake'])

        # Flash every objectively winning active side area too, even without a chip.
        for bet_type, factor in settle['side_factors'].items():
            key = (bet_type, None)
            if factor > 1.0 and key in self.bet_spots:
                self.flash_winning_keys.add(key)

        main_factor = BaccaratEngine.main_return_factor(result['winner'], result, self.game_mode)
        _ = main_factor  # compatibility no-op; winner area is handled explicitly below
        winner_key = (result['winner'], None)
        if result['winner'] in ('Player', 'Tie', 'Banker') and winner_key in self.bet_spots:
            factor = BaccaratEngine.main_return_factor(result['winner'], result, self.game_mode)
            if factor > 1.0:
                self.flash_winning_keys.add(winner_key)

        # Keep Push wagers visible through the settlement animation, then fly
        # them back to the bottom chip rack with their returned stake.
        self.settlement_hold_amounts = {
            (bet_type, None): amount
            for bet_type, amount in self.push_return_amounts.items()
            if amount > 0
        }

        self.bet_state.bets.clear()
        self.summary_mode = 'win'
        self.result_panel_flash_winner = result['winner']
        self.canvas.itemconfigure(self.animation_phase_text, text='本局结果')
        self.canvas.itemconfigure(self.tie_flash_rect, state='hidden')

        self.accept_bets = False
        self.settlement_running = True
        self.animation_running = False
        self.flash_mode = None
        self.update_display()
        self.save_balance()

        if settle['jackpot_win'] > 0:
            messagebox.showinfo('累进大奖',
                                f"恭喜！获得大奖 {self.format_money(settle['jackpot_win'])}",
                                parent=self.winfo_toplevel())

        # Always flash the winning card zone, even when the player placed no
        # wager on the winning outcome. Betting areas still flash when applicable.
        self.settlement_flash_step = 0
        self.run_settlement_flash()

    def _sync_golden_badges_for_flash(self, light_phase):
        """Make Treasure golden odds badges flash with their winning areas."""
        if self.game_mode not in ('treasure', 'xxx'):
            return
        for key in self.flash_winning_keys:
            spot = self.bet_spots.get(key)
            if not spot:
                continue
            tag = spot.get('tag')
            if not tag:
                continue
            for item_id in self.canvas.find_withtag(tag):
                try:
                    tags = self.canvas.gettags(item_id)
                    if 'golden_bet_dynamic' not in tags:
                        continue
                    item_type = self.canvas.type(item_id)
                    if item_type == 'oval':
                        self.canvas.itemconfigure(
                            item_id,
                            fill='#fff8cf' if light_phase else '#e3b51d',
                            outline='#111111' if light_phase else '#fff2a3',
                            width=3 if light_phase else 2)
                    elif item_type == 'text':
                        self.canvas.itemconfigure(
                            item_id, fill='#000000' if light_phase else '#201700')
                    self.canvas.tag_raise(item_id)
                except tk.TclError:
                    pass

    def _sync_treasure_rule_table_flash(self, light_phase):
        """Flash the winning Golden Hunter / Golden Duel odds cell.

        The temporary rule table follows the exact same settlement phase as the
        corresponding betting area.  Normal phase = original dark background and
        gold odds text; highlight phase = gold background and black odds text.
        """
        cells = getattr(self, 'treasure_panel_rule_cells', {})
        if not cells or not getattr(self, 'treasure_panel_active', False):
            return

        # Restore every row first so only the highest/actual payable row flashes.
        for bg_item, text_item in cells.values():
            try:
                self.canvas.itemconfigure(bg_item, fill='#211811')
                self.canvas.itemconfigure(text_item, fill='#ffd84a')
            except tk.TclError:
                pass

        if self.game_mode == 'treasure':
            bet_type = 'Golden Hunter'
            tier = BaccaratEngine.golden_hit_count(self.current_result or {})
        elif self.game_mode == 'xxx':
            bet_type = 'Golden Duel'
            tier = BaccaratEngine.golden_duel_tier(self.current_result or {})
        elif self.game_mode == 'goldendice':
            bet_type = 'Super Dice'
            tier = BaccaratEngine.super_dice_tier(self.current_result or {})
        else:
            return

        # Match the betting-area flash exactly: no table flash unless that side-bet
        # area is part of this settlement's winning flash set.
        if (bet_type, None) not in self.flash_winning_keys:
            return
        cell = cells.get(int(tier or 0))
        if not cell:
            return
        bg_item, text_item = cell
        try:
            self.canvas.itemconfigure(
                bg_item, fill='#ffd84a' if light_phase else '#211811')
            self.canvas.itemconfigure(
                text_item, fill='#000000' if light_phase else '#ffd84a')
            self.canvas.tag_raise(text_item)
        except tk.TclError:
            pass

    def run_settlement_flash(self):
        if self._closing or not self.settlement_running:
            return
        if self.settlement_flash_step >= 6:
            self.settlement_after_id = None
            # V23: after the final flash, actual winning-return chips visibly
            # travel back to the bottom chip rack before settlement is cleared.
            if not self._start_winning_chip_return():
                self.finish_settlement()
            return
        self.flash_mode = 'win' if self.settlement_flash_step % 2 == 0 else 'original'
        self.flash_result_panels(self.settlement_flash_step % 2 == 0)
        self.canvas.delete('win_flash_area')
        if self.flash_mode == 'original':
            self.restore_flash_text_colors()
            self._sync_golden_badges_for_flash(False)
            self._sync_treasure_rule_table_flash(False)
        else:
            for key in self.flash_winning_keys:
                spot = self.bet_spots.get(key)
                if not spot:
                    continue
                x0, y0, x1, y1 = spot['bounds']
                self.canvas.create_rectangle(x0, y0, x1, y1, fill='#ffffff',
                                             outline='#111111', width=2,
                                             tags=('win_flash_area', 'settlement_flash'))
                self.raise_spot_content_above_flash(spot)
            # Re-style + raise the golden badges after the white flash layer is
            # created, so the badge itself visibly participates in the flash.
            self._sync_golden_badges_for_flash(True)
            self._sync_treasure_rule_table_flash(True)
        self.update_bet_chips()
        self.canvas.tag_raise('bet_chip_dynamic')
        self.canvas.tag_raise('controls')
        self.settlement_flash_step += 1
        self.settlement_after_id = self.after(450, self.run_settlement_flash)

    def _set_zone_text_colors(self, player_color=None, banker_color=None):
        """Set title + score colors together for each dealing zone."""
        if player_color is not None:
            for item in (getattr(self, 'player_zone_label', None),
                         getattr(self, 'player_score_text', None)):
                if item is not None:
                    self.canvas.itemconfigure(item, fill=player_color)
        if banker_color is not None:
            for item in (getattr(self, 'banker_zone_label', None),
                         getattr(self, 'banker_score_text', None)):
                if item is not None:
                    self.canvas.itemconfigure(item, fill=banker_color)

    def flash_result_panels(self, light_phase):
        """Flash winner card zones without ever hiding the point values.

        Highlight phase:
          * Player win -> pale blue, black title + black score.
          * Banker win -> pale red, black title + black score.
          * Tie -> both pale green, black titles + black scores.

        Normal phase:
          * Restore the original dark Player/Banker panel colours.
          * Restore the normal Player/Banker title colours.
          * Scores are always WHITE on the normal table.
        """
        winner = self.result_panel_flash_winner
        self.canvas.itemconfigure(self.tie_flash_rect, state='hidden')

        # Every frame begins from the real normal-table appearance.
        self.canvas.itemconfigure(self.player_zone_rect, fill=self.PLAYER_ZONE_BASE,
                                  outline='#6386a5')
        self.canvas.itemconfigure(self.banker_zone_rect, fill=self.BANKER_ZONE_BASE,
                                  outline='#a56a6d')
        self._set_zone_text_colors('#93b9ff', '#ffaaaa')
        self.canvas.itemconfigure(self.player_score_text, fill='white')
        self.canvas.itemconfigure(self.banker_score_text, fill='white')

        # Only the highlight frame overrides the winning zone.  The normal
        # frame intentionally needs no extra override, so the large score
        # never disappears between flashes.
        if winner == 'Player' and light_phase:
            self.canvas.itemconfigure(self.player_zone_rect, fill=self.PLAYER_ZONE_LIGHT,
                                      outline='#e3f6ff')
            self._set_zone_text_colors(player_color='black')

        elif winner == 'Banker' and light_phase:
            self.canvas.itemconfigure(self.banker_zone_rect, fill=self.BANKER_ZONE_LIGHT,
                                      outline='#ffe8ea')
            self._set_zone_text_colors(banker_color='black')

        elif winner == 'Tie' and light_phase:
            self.canvas.itemconfigure(self.player_zone_rect, fill=self.TIE_FLASH_LIGHT,
                                      outline='#dcffe6')
            self.canvas.itemconfigure(self.banker_zone_rect, fill=self.TIE_FLASH_LIGHT,
                                      outline='#dcffe6')
            self._set_zone_text_colors('black', 'black')

    def restore_result_panel_colors(self):
        """Restore the normal dark Player/Banker dealing-zone palette."""
        if hasattr(self, 'player_zone_rect'):
            self.canvas.itemconfigure(self.player_zone_rect, fill=self.PLAYER_ZONE_BASE,
                                      outline='#6386a5')
        if hasattr(self, 'banker_zone_rect'):
            self.canvas.itemconfigure(self.banker_zone_rect, fill=self.BANKER_ZONE_BASE,
                                      outline='#a56a6d')
        if hasattr(self, 'player_zone_label'):
            self.canvas.itemconfigure(self.player_zone_label, fill='#93b9ff')
        if hasattr(self, 'banker_zone_label'):
            self.canvas.itemconfigure(self.banker_zone_label, fill='#ffaaaa')
        if hasattr(self, 'player_score_text'):
            self.canvas.itemconfigure(self.player_score_text, fill='white')
        if hasattr(self, 'banker_score_text'):
            self.canvas.itemconfigure(self.banker_score_text, fill='white')
        if hasattr(self, 'tie_flash_rect'):
            self.canvas.itemconfigure(self.tie_flash_rect, state='hidden')

    def raise_spot_content_above_flash(self, spot):
        tag = spot.get('tag')
        if not tag:
            return
        for item_id in self.canvas.find_withtag(tag):
            try:
                item_type = self.canvas.type(item_id)
                tags = self.canvas.gettags(item_id)
            except tk.TclError:
                continue
            if 'win_flash_area' in tags or 'bet_chip_dynamic' in tags:
                continue
            if item_type == 'text':
                if item_id not in self.flash_original_text_colors:
                    self.flash_original_text_colors[item_id] = self.canvas.itemcget(item_id, 'fill')
                self.canvas.itemconfigure(item_id, fill='black')
                self.canvas.tag_raise(item_id)

    def restore_flash_text_colors(self):
        for item_id, color in list(self.flash_original_text_colors.items()):
            try:
                self.canvas.itemconfigure(item_id, fill=color)
            except tk.TclError:
                pass
        self.flash_original_text_colors.clear()

    def finish_settlement(self):
        if self._closing:
            return
        self.settlement_after_id = None
        self.canvas.delete('win_flash_area')
        self.restore_flash_text_colors()
        self.restore_result_panel_colors()
        self.canvas.itemconfigure(self.tie_flash_rect, state='hidden')
        self.flash_mode = None
        self.flash_winning_keys = set()
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        self.settlement_hold_amounts = {}
        self.push_return_amounts = {}
        self.settlement_return_animating = False
        self.settlement_return_keys.clear()
        self.pending_bet_visual_amounts.clear()
        self.pre_deal_bets = None
        self.settlement_running = False
        self.animation_running = False
        self.canvas.itemconfigure(self.animation_phase_text, text='百家乐 BACCARAT')
        if self.game_mode in ('treasure', 'xxx', 'goldendice'):
            self._hide_treasure_panel()
            self.current_golden_cards = []
            self.current_golden_map = {}
            if self.game_mode == 'goldendice':
                self.golden_dice_active = False
                self.current_golden_dice = [1, 1]
                self._update_golden_dice_board_odds()
            self.treasure_pot_amount = 0.0
            self.update_golden_bet_visuals()
            self._refresh_treasure_pool_text()
        if self.engine.needs_shuffle():
            self.accept_bets = False
            self.update_display()
            self.after(350, lambda: self.start_new_shoe_cut(True))
        else:
            self.accept_bets = True
            self.update_display()

    @classmethod
    def result_color(cls, winner):
        return {'Player': cls.PLAYER_BLUE, 'Banker': cls.BANKER_RED,
                'Tie': cls.TIE_GREEN}.get(winner, '#888888')

    @staticmethod
    def result_description(result):
        winner_text = {'Player': '闲胜', 'Banker': '庄胜', 'Tie': '和局'}.get(result['winner'], result['winner'])
        natural = ' · 天牌' if result.get('natural') else ''
        return f"{winner_text}  闲{result['player_score']} : 庄{result['banker_score']}{natural}"

    # ------------------------------------------------------------------ history
    def get_runtime_json_dir(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        target = os.path.join(project_root, 'A_Logs', 'Json')
        try:
            os.makedirs(target, exist_ok=True)
            return target
        except OSError:
            target = os.path.join(current_dir, 'A_Logs', 'Json')
            os.makedirs(target, exist_ok=True)
            return target

    @staticmethod
    def _default_statistic_data():
        return {'total_game': 0, 'player_win': 0, 'banker_win': 0, 'tie_win': 0}

    @classmethod
    def new_runtime_store(cls):
        return {
            'temp_data': {},
            'temp_finish_data': cls.new_history_store(),
            'statistic_data': cls._default_statistic_data(),
        }

    def _write_runtime_store(self):
        """Persist all three data groups into one Baccarat.json file."""
        try:
            os.makedirs(os.path.dirname(self.runtime_data_file), exist_ok=True)
            temp_path = self.runtime_data_file + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as handle:
                json.dump(self.runtime_store, handle, ensure_ascii=False, indent=4)
            os.replace(temp_path, self.runtime_data_file)
        except OSError as exc:
            print(f'保存 Baccarat 失败：{exc}')

    def load_runtime_store(self):
        """Load the single V14 runtime JSON, migrating the three legacy files once.

        Structure::
            {
              "temp_data": {...416-card shoe/current_index...},
              "temp_finish_data": {"records": [...]},
              "statistic_data": {"total_game": ..., ...}
            }
        """
        store = self.new_runtime_store()
        loaded_combined = False
        try:
            with open(self.runtime_data_file, 'r', encoding='utf-8') as handle:
                raw = json.load(handle)
            if isinstance(raw, dict):
                if isinstance(raw.get('temp_data'), dict):
                    store['temp_data'] = raw['temp_data']
                if isinstance(raw.get('temp_finish_data'), dict):
                    store['temp_finish_data'] = raw['temp_finish_data']
                if isinstance(raw.get('statistic_data'), dict):
                    store['statistic_data'] = raw['statistic_data']
                loaded_combined = True
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

        if not loaded_combined:
            # Preserve existing V13 data by importing the old three-file format.
            legacy_specs = (
                ('temp_data', self.legacy_temp_data_file),
                ('temp_finish_data', self.legacy_temp_finish_data_file),
                ('statistic_data', self.legacy_statistic_data_file),
            )
            migrated = False
            for key, path in legacy_specs:
                try:
                    with open(path, 'r', encoding='utf-8') as handle:
                        value = json.load(handle)
                    if isinstance(value, dict):
                        store[key] = value
                        migrated = True
                except (FileNotFoundError, json.JSONDecodeError, OSError):
                    pass
            try:
                os.makedirs(os.path.dirname(self.runtime_data_file), exist_ok=True)
                with open(self.runtime_data_file, 'w', encoding='utf-8') as handle:
                    json.dump(store, handle, ensure_ascii=False, indent=4)
                # Once safely migrated, remove the obsolete split files so only
                # the single combined JSON remains in active use.
                if migrated:
                    for _key, path in legacy_specs:
                        try:
                            if os.path.exists(path):
                                os.remove(path)
                        except OSError:
                            pass
            except OSError as exc:
                print(f'建立 Baccarat 失败：{exc}')
        return store

    def get_history_file(self):
        return getattr(self, 'runtime_data_file',
                       os.path.join(self.get_runtime_json_dir(), 'Baccarat.json'))

    def load_temp_data(self):
        try:
            data = self.runtime_store.get('temp_data', {})
            if not isinstance(data, dict):
                return False
            deck = data.get('deck', [])
            index = int(data.get('current_index', 0))
            threshold = int(data.get('cut_threshold', 60))
            burn_complete = bool(data.get('burn_complete', False))
            if (not isinstance(deck, list) or len(deck) != 416 or not burn_complete
                    or not (0 <= index <= 416) or not (50 <= threshold <= 80)):
                return False
            normalized = []
            for card in deck:
                if not isinstance(card, (list, tuple)) or len(card) != 2:
                    return False
                suit, rank = str(card[0]), str(card[1])
                if suit not in BaccaratEngine.SUITS or rank not in BaccaratEngine.RANKS:
                    return False
                normalized.append((suit, rank))
            self.engine.set_shoe_state(normalized, index, threshold)
            return self.engine.remaining_cards() > self.engine.cut_threshold
        except (TypeError, ValueError):
            return False

    def save_temp_data(self, burn_complete=True):
        self.runtime_store['temp_data'] = {
            'deck': [list(card) for card in self.engine.deck],
            'current_index': int(self.engine.current_index),
            'cut_threshold': int(self.engine.cut_threshold),
            'remaining_cards': int(self.engine.remaining_cards()),
            'burn_complete': bool(burn_complete),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        self._write_runtime_store()

    @classmethod
    def new_history_store(cls):
        return {'records': []}

    @classmethod
    def normalize_history_store(cls, data):
        normalized = cls.new_history_store()
        if not isinstance(data, dict):
            return normalized
        raw_records = data.get('records', [])
        if not isinstance(raw_records, list):
            return normalized
        for record in raw_records[-cls.MAX_RECORDS:]:
            if not isinstance(record, dict):
                continue
            winner = record.get('winner')
            if winner not in ('Player', 'Tie', 'Banker'):
                continue
            try:
                ps = int(record.get('player_score', 0))
                bs = int(record.get('banker_score', 0))
            except (TypeError, ValueError):
                continue
            item = copy.deepcopy(record)
            item['player_score'] = ps
            item['banker_score'] = bs
            normalized['records'].append(item)
        return normalized

    def load_history_store(self):
        raw = self.runtime_store.get('temp_finish_data', self.new_history_store())
        return self.normalize_history_store(raw)

    def save_history_store(self):
        self.runtime_store['temp_finish_data'] = copy.deepcopy(self.history_store)
        self._write_runtime_store()

    def history_records_from_store(self):
        return list(self.history_store.get('records', []))

    def clear_temp_finish_data(self):
        """Clear current-shoe completed hands but preserve shoe/statistic sections."""
        self.history_store = self.new_history_store()
        self.history_data = []
        self.runtime_store['temp_finish_data'] = self.new_history_store()
        self._write_runtime_store()
        self.update_history_table()

    def clear_shoe_temp_sections(self):
        """Player cut: delete BOTH temporary sections, never lifetime statistics."""
        self.runtime_store['temp_data'] = {}
        self.runtime_store['temp_finish_data'] = self.new_history_store()
        self.history_store = self.new_history_store()
        self.history_data = []
        self.big_road_scroll_col = 0
        self.big_road_auto_follow = True
        self._write_runtime_store()
        self.update_history_table()

    def add_history(self, result):
        player_pair, banker_pair = BaccaratEngine._pair_flags(result)
        special_by_mode = {}
        for mode in self.MODE_ORDER:
            factors = BaccaratEngine.side_return_factors(result, mode)
            special_by_mode[mode] = [name for name, factor in factors.items() if factor > 1.0]
        record = {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'winner': result['winner'],
            'player_score': int(result['player_score']),
            'banker_score': int(result['banker_score']),
            'natural': bool(result.get('natural', False)),
            'mode': self.game_mode,
            'player_pair': bool(player_pair),
            'banker_pair': bool(banker_pair),
            'specials': special_by_mode.get(self.game_mode, []),
            'special_by_mode': special_by_mode,
            'player_hand': [list(card) for card in result.get('player_hand', [])],
            'banker_hand': [list(card) for card in result.get('banker_hand', [])],
        }
        records = self.history_store.setdefault('records', [])
        records.append(record)
        # A new result always brings Big Road navigation back to the newest data.
        self.big_road_auto_follow = True
        if len(records) > self.MAX_RECORDS:
            del records[:-self.MAX_RECORDS]
        self.save_history_store()
        self.history_data = self.history_records_from_store()

    def load_statistic_data(self):
        defaults = self._default_statistic_data()
        raw = self.runtime_store.get('statistic_data', {})
        if isinstance(raw, dict):
            for key in ('total_game', 'player_win', 'banker_win', 'tie_win'):
                try:
                    defaults[key] = max(0, int(raw.get(key, 0)))
                except (TypeError, ValueError):
                    defaults[key] = 0
        had_legacy_treasure_value = isinstance(raw, dict) and 'treasure_pot' in raw
        self.runtime_store['statistic_data'] = dict(defaults)
        if had_legacy_treasure_value:
            # V20 migration: Treasure Pot is a per-round UI amount, not a
            # lifetime statistic. Remove the obsolete stored key immediately.
            self._write_runtime_store()
        return defaults

    def save_statistic_data(self):
        # Lifetime statistics only. Treasure Pot fees are strictly per-round
        # display state and must never enter the JSON store.
        self.runtime_store['statistic_data'] = {
            'total_game': max(0, int(self.statistic_data.get('total_game', 0))),
            'player_win': max(0, int(self.statistic_data.get('player_win', 0))),
            'banker_win': max(0, int(self.statistic_data.get('banker_win', 0))),
            'tie_win': max(0, int(self.statistic_data.get('tie_win', 0))),
        }
        self.statistic_data = dict(self.runtime_store['statistic_data'])
        self._write_runtime_store()

    def update_statistic_data(self, result):
        self.statistic_data['total_game'] = int(self.statistic_data.get('total_game', 0)) + 1
        if result['winner'] == 'Player':
            self.statistic_data['player_win'] = int(self.statistic_data.get('player_win', 0)) + 1
        elif result['winner'] == 'Banker':
            self.statistic_data['banker_win'] = int(self.statistic_data.get('banker_win', 0)) + 1
        else:
            self.statistic_data['tie_win'] = int(self.statistic_data.get('tie_win', 0)) + 1
        self.save_statistic_data()

    def get_jackpot_file(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')

    def load_jackpot(self):
        try:
            with open(self.jackpot_file, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get('Games') == 'BCT':
                        return max(5_000_000.0, float(item.get('jackpot', 5_000_000)))
            elif isinstance(data, dict) and data.get('Games') == 'BCT':
                return max(5_000_000.0, float(data.get('jackpot', 5_000_000)))
        except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError):
            pass
        return 5_000_000.0

    def save_jackpot(self):
        try:
            if os.path.exists(self.jackpot_file):
                with open(self.jackpot_file, 'r', encoding='utf-8') as handle:
                    data = json.load(handle)
            else:
                data = []
            if not isinstance(data, list):
                data = []
            found = False
            for item in data:
                if isinstance(item, dict) and item.get('Games') == 'BCT':
                    item['jackpot'] = float(self.jackpot_amount)
                    found = True
                    break
            if not found:
                data.append({'Games': 'BCT', 'jackpot': float(self.jackpot_amount)})
            with open(self.jackpot_file, 'w', encoding='utf-8') as handle:
                json.dump(data, handle, ensure_ascii=False, indent=4)
        except (OSError, json.JSONDecodeError):
            pass

    # ---------------------------------------------------------------- lifecycle
    def save_balance(self):
        if self.username:
            update_balance_in_json(self.username, self.balance)
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))

    def cancel_pending_callbacks(self):
        for after_id in list(self.animation_after_ids):
            try:
                self.after_cancel(after_id)
            except (tk.TclError, ValueError):
                pass
        self.animation_after_ids.clear()
        for after_id in list(self.chip_motion_after_ids):
            try:
                self.after_cancel(after_id)
            except (tk.TclError, ValueError):
                pass
        self.chip_motion_after_ids.clear()
        try:
            self.canvas.delete('chip_motion')
        except (tk.TclError, AttributeError):
            pass
        if self.settlement_after_id is not None:
            try:
                self.after_cancel(self.settlement_after_id)
            except (tk.TclError, ValueError):
                pass
            self.settlement_after_id = None
        if self.reshuffle_confirm_after_id is not None:
            try:
                self.after_cancel(self.reshuffle_confirm_after_id)
            except (tk.TclError, ValueError):
                pass
            self.reshuffle_confirm_after_id = None
        self.reshuffle_confirm_armed = False

    def on_close(self):
        self.exit_game()

    def exit_game(self):
        if self._closing:
            return
        self._closing = True
        self.cancel_pending_callbacks()
        self.animation_running = False
        self.accept_bets = False
        outstanding = self.bet_state.total_at_risk()
        fee_refund = sum(float(v) for v in self.bet_fee_state.values())
        if outstanding > 0 or fee_refund > 0:
            self.balance += outstanding + fee_refund
            if fee_refund > 0:
                self.treasure_pot_amount = max(0.0, self.treasure_pot_amount - fee_refund)
        self.bet_fee_state.clear()
        self.bet_state.bets.clear()
        self.final_balance = float(self.balance)
        try:
            self.save_balance()
        except Exception:
            pass
        if callable(self.on_back):
            self.on_back(self.final_balance)


# Backward-style wrapper for projects that expect a game class taking root.
class BaccaratGame(BubbleBaccaratGame):
    def __init__(self, root, username=None, initial_balance=10000,
                 on_back=None, on_balance_change=None, game_mode='classic'):
        super().__init__(
            parent=root,
            balance=initial_balance,
            user=username,
            on_back=on_back,
            on_balance_change=on_balance_change,
            game_mode=game_mode,
        )
        self.pack(fill=tk.BOTH, expand=True)

def main(parent=None, balance=10000, user=None, on_back=None,
         on_balance_change=None, username=None, game_mode='classic'):
    if username is not None and user is None:
        user = username

    # Compatibility with legacy main(balance, username) style calls.
    if parent is not None and not isinstance(parent, tk.Misc):
        legacy_balance = parent
        legacy_user = balance if isinstance(balance, str) and user is None else user
        parent = None
        balance = legacy_balance
        user = legacy_user

    if parent is not None:
        return BubbleBaccaratGame(
            parent=parent,
            balance=balance,
            user=user,
            on_back=on_back,
            on_balance_change=on_balance_change,
            game_mode=game_mode,
        )

    root = tk.Tk()
    root.title('百家乐')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)

    def close_standalone(final_balance):
        _ = final_balance
        try:
            root.destroy()
        except tk.TclError:
            pass

    game = BubbleBaccaratGame(
        parent=root,
        balance=balance,
        user=user,
        on_back=on_back or close_standalone,
        on_balance_change=on_balance_change,
        game_mode=game_mode,
    )
    game.pack(fill=tk.BOTH, expand=True)
    root.protocol('WM_DELETE_WINDOW', game.exit_game)
    root.mainloop()
    return game


if __name__ == '__main__':
    # Standalone launch starts with a fixed 10,000,000 balance.
    # Embedded/parent launches continue to use the balance supplied by Parent.
    main(balance=10_000_000)
