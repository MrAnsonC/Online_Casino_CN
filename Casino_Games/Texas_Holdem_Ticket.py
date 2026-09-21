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
from tkinter import ttk, messagebox
from tkinter import font as tkfont
from PIL import Image, ImageTk, ImageDraw, ImageFont
from collections import Counter
from itertools import combinations
from fractions import Fraction
import json
import math
import os
import random
import secrets
import subprocess
import sys
import threading
from datetime import datetime

WINDOW_GEOMETRY = "1150x750+50+10"
HOUSE_EDGE = 0.06  # 6% fixed house edge, within requested 3-10% band
# Keep the exact original Auto_Texas_Holdem card dimensions.
CARD_SIZE = (82, 115)
HOLE_CARD_SPACING = 88
COMMUNITY_CARD_SPACING = 84

# Original Auto_Texas_Holdem UI palette.
ROOT_BG = "#1B3D31"
TABLE_PANEL_BG = "#2A4A3C"
TABLE_BG = TABLE_PANEL_BG
COMMUNITY_BG = "#204B55"  # 公共牌独立深青蓝背景，和玩家区域区分
TEXT = "#FFFFFF"
GOLD = "#D4AF37"
PANEL_BG = "#F2E6C9"
MARKET_ALT_BG = "#75FC80"
MARKET_ALT_BG2 = "#75CDFC"  # 下注项目斑马纹：浅蓝色
MARKET_SEPARATOR_BG = "#000000"
MARKET_SEPARATOR_HEIGHT = 2
HEADER_BG = "#D8B46A"
TITLE_FG = "#2A1B08"
ACCENT_GOLD = "#A88100"
DARK = TITLE_FG
WIN = "#D9F2D9"
LOSE = "#F5D4D4"
BURN_BG = "#6B3034"

SUITS = ('♠', '♥', '♦', '♣')
RANKS = ('2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A')
RANK_VALUE = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_NAMES = {
    8: '同花顺', 7: '四条', 6: '葫芦', 5: '同花', 4: '顺子',
    3: '三条', 2: '两对', 1: '一对', 0: '高牌'
}
HAND_KEYS = {
    8: 'straight_flush', 7: 'four_kind', 6: 'full_house', 5: 'flush',
    4: 'straight', 3: 'three_kind', 2: 'two_pair', 1: 'pair', 0: 'high_card'
}
HAND_KEY_TO_NAME = {v: HAND_NAMES[k] for k, v in HAND_KEYS.items()}
HAND_KEY_TO_NAME['royal_flush'] = '皇家同花顺'
HAND_MARKET_ORDER = (
    'high_card', 'pair', 'two_pair', 'three_kind', 'straight', 'flush',
    'full_house', 'four_kind', 'straight_flush', 'royal_flush'
)


def is_royal_flush_value(value):
    """True when the evaluated best hand is an A-high straight flush (TJQKA)."""
    return bool(value and value[0] == 8 and len(value) > 1 and value[1] == 14)


def hand_market_keys(value):
    """Market categories hit by one evaluated hand.

    A royal flush deliberately hits BOTH 皇家同花顺 and 同花顺.  This keeps the
    existing 同花顺 market/probability unchanged while adding the new, more
    specific 皇家同花顺 market requested by the game rules.
    """
    if is_royal_flush_value(value):
        return ('straight_flush', 'royal_flush')
    return (HAND_KEYS[value[0]],)


def hand_display_name(value):
    return '皇家同花顺' if is_royal_flush_value(value) else HAND_NAMES[value[0]]


def hole_pattern_code(hand):
    """Return AA/AK/27/22 for a matching two-card hole hand, else None."""
    if len(hand) != 2:
        return None
    ranks = tuple(sorted((hand[0].value, hand[1].value)))
    for code, pattern in SPECIFIED_HOLE_PATTERNS.items():
        if ranks == tuple(sorted(pattern)):
            return code
    return None


def specified_holders(hole_hands, code):
    pattern = tuple(sorted(SPECIFIED_HOLE_PATTERNS[code]))
    return [
        i for i, hand in enumerate(hole_hands)
        if len(hand) == 2 and tuple(sorted((hand[0].value, hand[1].value))) == pattern
    ]

# Before any card is exposed, H2H equity is exactly 20% for each of five symmetric players.
# Public-card / suit-count markets below are calculated exactly by combinatorics.
# The pre-deal winner-category baseline is kept as a fixed 5-player table. It can be
# replaced by an audited exact table without changing any sportsbook logic.
PREDEAL_WINNER_TYPE_PROBS = {
    'high_card': 0.0018458,
    'pair': 0.1960444,
    'two_pair': 0.3239268,
    'three_kind': 0.1259784,
    'straight': 0.1499266,
    'flush': 0.0972256,
    'full_house': 0.0961926,
    'four_kind': 0.0074054,
    'straight_flush': 0.0014544,
    # Exact probability at least one of 5 players can make a royal flush.
    # Existing straight_flush remains inclusive of royal flushes.
    'royal_flush': 404 / math.comb(52, 5),
}

# Stage-1 half-time tables are fixed baseline tables, analogous to the existing
# pre-deal full-game winner-type table above.  Once the 10 hole cards are known
# (Stage 2), every half-time and half/full price is recomputed deterministically
# from the remaining deck; no Monte Carlo is used in the live dynamic prices.
PREDEAL_HALF_WINNER_TYPE_PROBS = {
    'high_card': 0.05414867,
    'pair': 0.66328400,
    'two_pair': 0.15760200,
    'three_kind': 0.08869033,
    'straight': 0.01863667,
    'flush': 0.00929567,
    'full_house': 0.00707000,
    'four_kind': 0.00119400,
    'straight_flush': 0.00007867,
    # With a 3-card flop, at most one player can complete a royal flush.
    'royal_flush': 20 / math.comb(52, 5),
}

# Exact five-card hand-category distribution for one player's half-time hand
# (2 hole cards + the 3-card flop).  Before any cards are exposed, those five
# cards are a uniformly distributed 5-card subset of the 52-card deck.
_PREDEAL_5CARD_TOTAL = math.comb(52, 5)
PREDEAL_HALF_PLAYER_TYPE_PROBS = {
    'high_card': 1302540 / _PREDEAL_5CARD_TOTAL,
    'pair': 1098240 / _PREDEAL_5CARD_TOTAL,
    'two_pair': 123552 / _PREDEAL_5CARD_TOTAL,
    'three_kind': 54912 / _PREDEAL_5CARD_TOTAL,
    'straight': 10200 / _PREDEAL_5CARD_TOTAL,
    'flush': 5108 / _PREDEAL_5CARD_TOTAL,
    'full_house': 3744 / _PREDEAL_5CARD_TOTAL,
    'four_kind': 624 / _PREDEAL_5CARD_TOTAL,
    'straight_flush': 40 / _PREDEAL_5CARD_TOTAL,
    'royal_flush': 4 / _PREDEAL_5CARD_TOTAL,
}

# Exact best-five category distribution from seven uniformly distributed cards.
# Correct Stage-1 baseline for each individual player's full-game 2 hole + 5 board.
_PREDEAL_7CARD_TOTAL = math.comb(52, 7)
PREDEAL_FULL_PLAYER_TYPE_PROBS = {
    'high_card': 23294460 / _PREDEAL_7CARD_TOTAL,
    'pair': 58627800 / _PREDEAL_7CARD_TOTAL,
    'two_pair': 31433400 / _PREDEAL_7CARD_TOTAL,
    'three_kind': 6461620 / _PREDEAL_7CARD_TOTAL,
    'straight': 6180020 / _PREDEAL_7CARD_TOTAL,
    'flush': 4047644 / _PREDEAL_7CARD_TOTAL,
    'full_house': 3473184 / _PREDEAL_7CARD_TOTAL,
    'four_kind': 224848 / _PREDEAL_7CARD_TOTAL,
    'straight_flush': 41584 / _PREDEAL_7CARD_TOTAL,
    'royal_flush': 4324 / _PREDEAL_7CARD_TOTAL,
}
# Per-player Stage-1 hit rates.  A tie is a wildcard for the half/full market:
# both “赢” and “输” selections for that leg count as hit, and payout is NOT
# divided by the number of tied players.
PREDEAL_HALF_FULL_PROBS = {
    'WW': 0.11440933,  # 半赢 / 全赢
    'WL': 0.09734667,  # 半赢 / 全输
    'LW': 0.10405000,  # 半输 / 全赢
    'LL': 0.72022367,  # 半输 / 全输
}

# 指定起手牌特别市场。阶段2以后会依据10张已知手牌与所有未来公牌
# 做确定性完整枚举。阶段1没有任何牌可见，因此使用固定的5人桌
# pre-deal基准。出现率本身是精确组合值；胜率基准是固定的5-way
# starting-hand calibration，不在每局运行 Monte Carlo。
SPECIFIED_HOLE_PATTERNS = {
    'AA': (14, 14),
    'AK': (13, 14),
    '27': (2, 7),
    '22': (2, 2),
}
# Exact probability that at least one of five labelled 2-card hands has the
# specified rank pattern (suits ignored). Same-rank and distinct-rank classes
# are symmetric by rank.
PREDEAL_SPECIFIED_PRESENCE = {
    'AA': 0.022587496537076368,
    'AK': 0.05944845871648786,
    '27': 0.05944845871648786,
    '22': 0.022587496537076368,
}
# Fixed 5-player (four random opponents) win calibration used only before any
# card is exposed. Stage2 replaces these with exact C(42,5) live enumeration.
PREDEAL_SPECIFIED_WIN_RATE = {
    'AA': 0.5590,
    'AK': 0.34725,
    '27': 0.14125,
    '22': 0.1790,
}
PREDEAL_SPECIFIED_RESULT_PROBS = {
    hand: {
        'win': PREDEAL_SPECIFIED_PRESENCE[hand] * PREDEAL_SPECIFIED_WIN_RATE[hand],
        'lose': PREDEAL_SPECIFIED_PRESENCE[hand] * (1.0 - PREDEAL_SPECIFIED_WIN_RATE[hand]),
    }
    for hand in SPECIFIED_HOLE_PATTERNS
}


def get_data_file_path():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(os.path.dirname(here), 'A_Tools/Account/saving_data.json'),
        os.path.join(here, 'A_Tools/Account/saving_data.json'),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]


def load_user_data():
    try:
        with open(get_data_file_path(), 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def update_balance_in_json(username, new_balance):
    if not username or username == 'Guest':
        return
    users = load_user_data()
    changed = False
    for user in users:
        if user.get('user_name') == username:
            user['cash'] = f"{float(new_balance):.2f}"
            changed = True
            break
    if changed:
        try:
            with open(get_data_file_path(), 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=4)
        except OSError:
            pass


def money(v):
    return f"${float(v):,.2f}"


class Card:
    __slots__ = ('suit', 'rank', 'value', 'suit_i')
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.value = RANK_VALUE[rank]
        self.suit_i = SUITS.index(suit)
    def __repr__(self):
        return f"{self.rank}{self.suit}"
    def key(self):
        return self.value, self.suit_i


class Deck:
    def __init__(self):
        # Keep the original shuffled 52-card order AND the cut position so the
        # completed round can expose an auditable shoe record on right-click.
        self.full_deck, self.cut_position = self._load_shuffle()
        self.cut_position = int(self.cut_position) % 52
        # 与原始 Auto_Texas_Holdem 的牌靴记录字段保持一致。
        self.start_pos = self.cut_position
        self.card_sequence = self.full_deck[self.start_pos:] + self.full_deck[:self.start_pos]
        self.pointer = 0

    def _load_shuffle(self):
        here = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(os.path.dirname(here), 'A_Tools', 'Card', 'shuffle.py'),
            os.path.join(here, 'A_Tools', 'Card', 'shuffle.py'),
        ]
        script = next((p for p in candidates if os.path.exists(p)), None)
        if script:
            try:
                env = os.environ.copy(); env['PYTHONIOENCODING'] = 'utf-8'
                result = subprocess.run(
                    [sys.executable, script, 'false', '1'], capture_output=True,
                    text=True, encoding='utf-8', env=env, check=True, timeout=30
                )
                data = json.loads(result.stdout)
                raw = data.get('deck', [])
                cards = [Card(d['suit'], d['rank']) for d in raw]
                if len(cards) == 52:
                    cut = int(data.get('cut_position', 0)) % 52
                    return cards, cut
            except Exception:
                pass
        cards = [Card(s, r) for s in SUITS for r in RANKS]
        rng = secrets.SystemRandom(); rng.shuffle(cards)
        return cards, secrets.randbelow(52)

    def deal(self, n=1):
        if self.pointer + n > len(self.card_sequence):
            raise RuntimeError('牌堆不足')
        out = self.card_sequence[self.pointer:self.pointer+n]
        self.pointer += n
        return out

    def remaining(self):
        return self.card_sequence[self.pointer:]


POW5 = [5 ** i for i in range(13)]
STRAIGHT_HIGH_TABLE = [0] * (1 << 15)
TOP5_TABLE = [None] * (1 << 15)
for _m in range(1 << 15):
    mm = _m | ((1 << 1) if (_m & (1 << 14)) else 0)
    sh = 0
    for high in range(14, 4, -1):
        needed = 0
        for d in range(5): needed |= 1 << (high - d)
        if mm & needed == needed:
            sh = high; break
    STRAIGHT_HIGH_TABLE[_m] = sh
    TOP5_TABLE[_m] = tuple(r for r in range(14, 1, -1) if _m & (1 << r))[:5]

from functools import lru_cache

@lru_cache(maxsize=None)
def _rank_key_from_code(code):
    counts = [0] * 15
    x = code
    for i in range(13):
        counts[i+2] = x % 5
        x //= 5
    for r in range(14,1,-1):
        if counts[r] == 4:
            kicker = next(k for k in range(14,1,-1) if k != r and counts[k])
            return (7,r,kicker)
    trips = [r for r in range(14,1,-1) if counts[r] >= 3]
    if trips:
        t = trips[0]
        ps = [r for r in range(14,1,-1) if r != t and counts[r] >= 2]
        if ps: return (6,t,ps[0])
    mask = 0
    for r in range(2,15):
        if counts[r]: mask |= 1 << r
    sh = STRAIGHT_HIGH_TABLE[mask]
    if sh: return (4,sh)
    if trips:
        t=trips[0]; ks=[r for r in range(14,1,-1) if r != t and counts[r]][:2]
        return (3,t,*ks)
    pairs=[r for r in range(14,1,-1) if counts[r] >= 2]
    if len(pairs)>=2:
        a,b=pairs[:2];k=next(r for r in range(14,1,-1) if r not in (a,b) and counts[r])
        return (2,a,b,k)
    if pairs:
        a=pairs[0];ks=[r for r in range(14,1,-1) if r != a and counts[r]][:3]
        return (1,a,*ks)
    vals=[r for r in range(14,1,-1) if counts[r]][:5]
    return (0,*vals)

def _card_code(card):
    return POW5[card.value-2]

def _hole_state(h):
    code=_card_code(h[0])+_card_code(h[1])
    sc=[0,0,0,0];sm=[0,0,0,0]
    for c in h:
        sc[c.suit_i]+=1;sm[c.suit_i]|=1<<c.value
    return code,tuple(sc),tuple(sm)

def _eval_from_state(code, sc0,sc1,sc2,sc3, sm0,sm1,sm2,sm3):
    rk=_rank_key_from_code(code)
    # Only flush-capable hands need suit-specific work.
    if sc0<5 and sc1<5 and sc2<5 and sc3<5:
        return rk
    for sc,sm in ((sc0,sm0),(sc1,sm1),(sc2,sm2),(sc3,sm3)):
        if sc>=5:
            sh=STRAIGHT_HIGH_TABLE[sm]
            if sh:return (8,sh)
    if rk[0] >= 6:
        return rk
    for sc,sm in ((sc0,sm0),(sc1,sm1),(sc2,sm2),(sc3,sm3)):
        if sc>=5:return (5,*TOP5_TABLE[sm])
    return rk

def hand_key7(cards):
    code=0;sc=[0,0,0,0];sm=[0,0,0,0]
    for c in cards:
        code += _card_code(c);sc[c.suit_i]+=1;sm[c.suit_i]|=1<<c.value
    return _eval_from_state(code,sc[0],sc[1],sc[2],sc[3],sm[0],sm[1],sm[2],sm[3])

def same_color(cards):
    # red = hearts/diamonds, black = spades/clubs
    colors = [0 if c.suit in ('♥', '♦') else 1 for c in cards]
    return len(set(colors)) == 1


def suit_diversity(cards):
    return len(set(c.suit_i for c in cards))


def odds_from_probability(p, edge=HOUSE_EDGE):
    if p <= 0:
        return None
    return max(0.01, (1.0 - edge) / p - 1.0)


def h2h_odds(hit_probability, equity, edge=HOUSE_EDGE):
    """Price profit odds so hit_prob + odds*equity ~= RTP, respecting split odds/k."""
    if equity <= 0:
        return None
    return max(0.01, ((1.0 - edge) - hit_probability) / equity)


def exact_public_suit_probs(deck_cards):
    total = math.comb(len(deck_cards), 5)
    same_col = 0; ge3 = 0; ge4 = 0
    suit_counts = Counter(c.suit_i for c in deck_cards)
    # Enumerate suit-count compositions only, not card combinations.
    n = len(deck_cards)
    counts = [suit_counts[i] for i in range(4)]
    for a in range(6):
        for b in range(6-a):
            for c in range(6-a-b):
                d = 5-a-b-c
                if d < 0: continue
                xs = [a,b,c,d]
                ways = 1
                ok = True
                for i, x in enumerate(xs):
                    if x > counts[i]: ok = False; break
                    ways *= math.comb(counts[i], x)
                if not ok or ways == 0: continue
                div = sum(1 for x in xs if x)
                if div >= 3: ge3 += ways
                if div >= 4: ge4 += ways
                red = b + c  # SUITS order spade, heart, diamond, club
                if red in (0,5): same_col += ways
    return {
        'community_same_color_yes': same_col/total,
        'community_same_color_no': 1-same_col/total,
        'community_ge3_suits': ge3/total,
        'community_ge4_suits': ge4/total,
    }


def exact_suited_player_count_probs():
    """Exact probabilities that >=3/4/5 of five 2-card hands are individually suited."""
    from functools import lru_cache

    @lru_cache(None)
    def rec(a,b,c,d, hands_left, suited_count):
        if hands_left == 0:
            return {suited_count: Fraction(1,1)}
        rem = a+b+c+d
        denom = math.comb(rem, 2)
        counts = [a,b,c,d]
        out = {}
        # unordered suit pair for next player's two cards
        for s1 in range(4):
            for s2 in range(s1,4):
                if s1 == s2:
                    ways = math.comb(counts[s1],2)
                    if ways == 0: continue
                    nc = counts.copy(); nc[s1] -= 2; add=1
                else:
                    ways = counts[s1]*counts[s2]
                    if ways == 0: continue
                    nc = counts.copy(); nc[s1]-=1; nc[s2]-=1; add=0
                sub = rec(nc[0],nc[1],nc[2],nc[3],hands_left-1,suited_count+add)
                w = Fraction(ways,denom)
                for k,v in sub.items(): out[k] = out.get(k,Fraction(0,1))+w*v
        return out

    dist = rec(13,13,13,13,5,0)
    def ge(k): return float(sum(v for c,v in dist.items() if c>=k))
    return {'hole_ge3_suited':ge(3),'hole_ge4_suited':ge(4),'hole_ge5_suited':ge(5)}


def exact_hole_pair_count_probs():
    """Exact probabilities that >=1/2/3 of five labelled hole hands are pocket pairs."""
    from functools import lru_cache

    @lru_cache(None)
    def rec(counts, hands_left):
        if hands_left == 0:
            return {0: Fraction(1, 1)}
        counts = tuple(counts)
        remaining = sum(counts)
        denom = math.comb(remaining, 2)
        out = {}

        # A pocket pair: choose two cards from the same rank.
        for i, c in enumerate(counts):
            if c < 2:
                continue
            ways = math.comb(c, 2)
            nc = list(counts); nc[i] -= 2
            sub = rec(tuple(sorted(nc, reverse=True)), hands_left - 1)
            weight = Fraction(ways, denom)
            for k, v in sub.items():
                out[k + 1] = out.get(k + 1, Fraction(0, 1)) + weight * v

        # A non-pair: choose one card from each of two different ranks.
        for i in range(len(counts)):
            if not counts[i]:
                continue
            for j in range(i + 1, len(counts)):
                if not counts[j]:
                    continue
                ways = counts[i] * counts[j]
                nc = list(counts); nc[i] -= 1; nc[j] -= 1
                sub = rec(tuple(sorted(nc, reverse=True)), hands_left - 1)
                weight = Fraction(ways, denom)
                for k, v in sub.items():
                    out[k] = out.get(k, Fraction(0, 1)) + weight * v
        return out

    dist = rec((4,) * 13, 5)
    return {
        'hole_pair_ge1': float(sum(v for k, v in dist.items() if k >= 1)),
        'hole_pair_ge2': float(sum(v for k, v in dist.items() if k >= 2)),
        'hole_pair_ge3': float(sum(v for k, v in dist.items() if k >= 3)),
    }


def exact_repeated_hole_rank_pattern_probs():
    """Exact probability that >=2 / >=3 players share the same two hole-card ranks.

    Suits are ignored and the two ranks are unordered, so A-Q matches any other A-Q.
    This is exact combinatorics: equality moments for labelled hands are converted to
    the seven possible equality-partition types of five players.
    """
    patterns = [(a, b) for a in range(13) for b in range(a, 13)]

    def denom(k):
        d = 1
        for j in range(k):
            d *= math.comb(52 - 2*j, 2)
        return d

    def ways(counts, pat):
        a, b = pat
        if a == b:
            return math.comb(counts[a], 2) if counts[a] >= 2 else 0
        return counts[a] * counts[b]

    def take(counts, pat):
        c = list(counts); a, b = pat
        c[a] -= 1; c[b] -= 1
        return tuple(c)

    q2 = Fraction(
        13 * (math.comb(4, 2) * math.comb(2, 2))
        + math.comb(13, 2) * (16 * 9),
        denom(2)
    )
    q3 = Fraction(math.comb(13, 2) * (16 * 9 * 4), denom(3))
    q4 = Fraction(math.comb(13, 2) * (16 * 9 * 4), denom(4))

    # q22 = P(H1=H2 and H3=H4)
    num22 = 0
    for a_pat in patterns:
        c = (4,) * 13
        w1 = ways(c, a_pat)
        if not w1: continue
        c = take(c, a_pat)
        w2 = ways(c, a_pat)
        if not w2: continue
        c = take(c, a_pat)
        wa = w1 * w2
        for b_pat in patterns:
            w3 = ways(c, b_pat)
            if not w3: continue
            c2 = take(c, b_pat)
            w4 = ways(c2, b_pat)
            if w4: num22 += wa * w3 * w4
    q22 = Fraction(num22, denom(4))

    # q32 = P(H1=H2=H3 and H4=H5)
    num32 = 0
    for a_pat in patterns:
        c = (4,) * 13; wa = 1; ok = True
        for _ in range(3):
            w = ways(c, a_pat)
            if not w:
                ok = False; break
            wa *= w; c = take(c, a_pat)
        if not ok: continue
        for b_pat in patterns:
            w4 = ways(c, b_pat)
            if not w4: continue
            c2 = take(c, b_pat)
            w5 = ways(c2, b_pat)
            if w5: num32 += wa * w4 * w5
    q32 = Fraction(num32, denom(5))

    # Equality partition probabilities for 5 labelled players.
    p41 = 5 * q4
    p32 = 10 * q32
    p311 = 10 * q3 - p32 - 4 * p41
    p221 = 15 * (q22 - p32/5 - p41/5)
    p2111 = 10 * (q2 - p221/5 - 3*p311/10 - 2*p32/5 - 3*p41/5)
    p11111 = Fraction(1, 1) - (p2111 + p221 + p311 + p32 + p41)
    return {
        'hole_rank_match_ge2': float(1 - p11111),
        'hole_rank_match_ge3': float(p311 + p32 + p41),
    }


def flop_three_flags(cards):
    """Three-card flop categories. Straight/flush include straight flush."""
    ranks = [c.value for c in cards]
    suits = [c.suit_i for c in cards]
    cnt = Counter(ranks)
    values = sorted(set(ranks))
    trips = (len(cnt) == 1)
    pair = (sorted(cnt.values()) == [1, 2])
    straight = False
    if len(values) == 3:
        straight = (values[-1] - values[0] == 2) or set(values) == {2, 3, 14}
    flush = (len(set(suits)) == 1)
    straight_flush = straight and flush
    return {
        'pair': pair,
        'straight': straight,
        'flush': flush,
        'trips': trips,
        'straight_flush': straight_flush,
    }


def exact_flop_three_probs(deck_cards):
    total = 0
    counts = Counter()
    for cards in combinations(deck_cards, 3):
        total += 1
        flags = flop_three_flags(cards)
        for key, hit in flags.items():
            if hit: counts[key] += 1
    return {key: counts[key] / total for key in ('pair','straight','flush','trips','straight_flush')}


def exact_two_card_rank_pair_prob(deck_cards):
    """Exact probability that the future Turn and River have the same rank."""
    n = len(deck_cards)
    if n < 2:
        return 0.0
    rank_counts = Counter(c.value for c in deck_cards)
    good = sum(math.comb(v, 2) for v in rank_counts.values())
    return good / math.comb(n, 2)


def exact_flop_later_rank_match_probs(deck_cards):
    """Exact Stage-1/2 rank-overlap probabilities between Flop (3) and Turn/River (2).

    Market keys ALWAYS mean ``flop-card count _ turn+river-card count``:
      1_1 = 翻1+转河1
      1_2 = 翻1+转河2
      2_1 = 翻2+转河1
      2_2 = 翻2+转河2
      3_1 = 翻3+转河1

    The first number is therefore limited by the three-card Flop, while the second
    number is limited by the two later public cards (Turn + River).  In particular,
    this market never describes "3张转牌"; Turn itself is exactly one card.
    """
    n = len(deck_cards)
    market_keys = ('1_1', '1_2', '2_1', '2_2', '3_1')
    if n < 5:
        return {key: 0.0 for key in market_keys}

    wanted = {
        (1, 1): '1_1',
        (1, 2): '1_2',
        (2, 1): '2_1',
        (2, 2): '2_2',
        (3, 1): '3_1',
    }
    hits = Counter()
    total = 0
    full_rank_counts = Counter(c.value for c in deck_cards)

    # Flop is an unordered 3-card set; Turn/River is an unordered 2-card set.
    # Every (Flop set, later set) path has equal probability, so exact counting is
    # C(n,3) * C(n-3,2) without enumerating individual ordered deals.
    for flop in combinations(deck_cards, 3):
        remaining_counts = full_rank_counts.copy()
        flop_values = [c.value for c in flop]
        for value in flop_values:
            remaining_counts[value] -= 1
        flop_rank_set = set(flop_values)

        ranks = [r for r, count in remaining_counts.items() if count > 0]
        for i, r1 in enumerate(ranks):
            c1 = remaining_counts[r1]
            if c1 >= 2:
                ways = math.comb(c1, 2)
                later_values = (r1, r1)
                later_rank_set = {r1}
                flop_matched = sum(1 for v in flop_values if v in later_rank_set)
                later_matched = 2 if r1 in flop_rank_set else 0
                key = wanted.get((flop_matched, later_matched))
                if key:
                    hits[key] += ways
                total += ways
            for r2 in ranks[i + 1:]:
                ways = c1 * remaining_counts[r2]
                later_rank_set = {r1, r2}
                flop_matched = sum(1 for v in flop_values if v in later_rank_set)
                later_matched = int(r1 in flop_rank_set) + int(r2 in flop_rank_set)
                key = wanted.get((flop_matched, later_matched))
                if key:
                    hits[key] += ways
                total += ways

    return {key: hits[key] / total for key in market_keys}


PREDEAL_SUITED_PROBS = exact_suited_player_count_probs()
PREDEAL_PUBLIC_PROBS = exact_public_suit_probs([Card(s,r) for s in SUITS for r in RANKS])
PREDEAL_HOLE_PAIR_PROBS = exact_hole_pair_count_probs()
PREDEAL_HOLE_RANK_MATCH_PROBS = exact_repeated_hole_rank_pattern_probs()
_FULL_DECK_FOR_PROPS = [Card(s,r) for s in SUITS for r in RANKS]
PREDEAL_FLOP_PROBS = exact_flop_three_probs(_FULL_DECK_FOR_PROPS)
PREDEAL_TURN_RIVER_PAIR_PROB = exact_two_card_rank_pair_prob(_FULL_DECK_FOR_PROPS)
PREDEAL_FLOP_LATER_RANK_MATCH_PROBS = exact_flop_later_rank_match_probs(_FULL_DECK_FOR_PROPS)
# A board-only 5-card hand has the standard exact 5-card category distribution.
# straight_flush remains inclusive of royal_flush, matching the existing market rules.
PREDEAL_COMMUNITY_HAND_TYPE_PROBS = dict(PREDEAL_HALF_PLAYER_TYPE_PROBS)


def analyze_future_boards(hole_hands, known_board, remaining_cards):
    """Exact deterministic enumeration of every possible remaining community set."""
    need = 5 - len(known_board)
    if need < 0: raise ValueError('公共牌超过5张')
    hole_states=[_hole_state(h) for h in hole_hands]
    base_code=sum(_card_code(c) for c in known_board)
    base_sc=[0,0,0,0];base_sm=[0,0,0,0]
    for c in known_board:
        base_sc[c.suit_i]+=1;base_sm[c.suit_i]|=1<<c.value
    rc=[(c,_card_code(c),c.suit_i,1<<c.value) for c in remaining_cards]
    total=0;eq=[0.0]*5;hit=[0]*5;type_counts=Counter();player_type_counts=[Counter() for _ in range(5)];same_color_count=0;ge3_count=0;ge4_count=0;remaining_same_suit=0
    spec_holders={code:specified_holders(hole_hands,code) for code in SPECIFIED_HOLE_PATTERNS}
    spec_counts={code:{'win':0,'lose':0} for code in SPECIFIED_HOLE_PATTERNS}
    iterable=combinations(rc,need) if need else [()]
    for extra in iterable:
        code=base_code;sc=base_sc.copy();sm=base_sm.copy(); board=list(known_board)
        for c,cc,si,bit in extra:
            code+=cc;sc[si]+=1;sm[si]|=bit;board.append(c)
        vals=[]
        for hc,hsc,hsm in hole_states:
            vals.append(_eval_from_state(code+hc,
                sc[0]+hsc[0],sc[1]+hsc[1],sc[2]+hsc[2],sc[3]+hsc[3],
                sm[0]|hsm[0],sm[1]|hsm[1],sm[2]|hsm[2],sm[3]|hsm[3]))
        for i,v in enumerate(vals):
            for market_key in hand_market_keys(v): player_type_counts[i][market_key] += 1
        best=max(vals);winners=[i for i,v in enumerate(vals) if v==best];share=1.0/len(winners)
        for i in winners:eq[i]+=share;hit[i]+=1
        winner_set=set(winners)
        for code,holders in spec_holders.items():
            if not holders:
                continue
            # A tied-best holder counts as 获胜. If multiple holders exist, the
            # win/lose propositions may both be true in the same board outcome.
            if any(i in winner_set for i in holders):
                spec_counts[code]['win'] += 1
            if any(i not in winner_set for i in holders):
                spec_counts[code]['lose'] += 1
        for market_key in hand_market_keys(best): type_counts[market_key] += 1
        # board suit/color properties from counters
        div=sum(1 for x in sc if x)
        if div>=3:ge3_count+=1
        if div>=4:ge4_count+=1
        red=sc[1]+sc[2]
        if red in (0,5):same_color_count+=1
        if need==2 and extra[0][2]==extra[1][2]:remaining_same_suit+=1
        total+=1
    result={'total':total,'equity':[x/total for x in eq],'hit':[x/total for x in hit],
      'winner_types':{k:v/total for k,v in type_counts.items()},
      'player_types':[{k:counts.get(k,0)/total for k in HAND_KEY_TO_NAME} for counts in player_type_counts],
      'community_same_color_yes':same_color_count/total,'community_same_color_no':1-same_color_count/total,
      'community_ge3_suits':ge3_count/total,'community_ge4_suits':ge4_count/total,
      'specified_hand_results':{
          code:{kind:count/total for kind,count in counts.items()}
          for code,counts in spec_counts.items()
      }}
    if need==2:
        result['remaining_same_suit']=remaining_same_suit/total;result['remaining_diff_suit']=1-result['remaining_same_suit']
    return result

def _card_bit52(card):
    return 1 << (card.suit_i * 13 + (card.value - 2))


def analyze_half_flops(hole_hands, remaining_cards, *, with_masks=False):
    """Exact Stage-2 half-time analysis over every C(n,3) possible flop.

    Half-time uses exactly each player's two hole cards plus the three flop cards.
    """
    total = 0
    equity = [0.0] * 5
    hit = [0] * 5
    type_counts = Counter()
    player_type_counts = [Counter() for _ in range(5)]
    masks = {} if with_masks else None
    for flop in combinations(remaining_cards, 3):
        board = list(flop)
        vals = [hand_key7(h + board) for h in hole_hands]
        for i, value in enumerate(vals):
            for market_key in hand_market_keys(value):
                player_type_counts[i][market_key] += 1
        best = max(vals)
        winners = [i for i, v in enumerate(vals) if v == best]
        share = 1.0 / len(winners)
        winner_mask = 0
        for i in winners:
            equity[i] += share
            hit[i] += 1
            winner_mask |= 1 << i
        for market_key in hand_market_keys(best):
            type_counts[market_key] += 1
        if masks is not None:
            key = _card_bit52(flop[0]) | _card_bit52(flop[1]) | _card_bit52(flop[2])
            masks[key] = winner_mask
        total += 1
    result = {
        'total': total,
        'equity': [x / total for x in equity],
        'hit': [x / total for x in hit],
        'winner_types': {k: v / total for k, v in type_counts.items()},
        'player_types': [
            {k: counts.get(k, 0) / total for k in HAND_KEY_TO_NAME}
            for counts in player_type_counts
        ],
    }
    if masks is not None:
        result['winner_masks'] = masks
    return result


def analyze_hole_stage_exact(hole_hands, remaining_cards):
    """Exact Stage-2 full/half/half-full calculation.

    Full-game results enumerate all C(42,5) final community-card sets.
    Half-time results enumerate all C(42,3) flops.
    Half/full joint events use every possible split of a final five-card board into
    a three-card flop plus two later cards: C(42,5) * C(5,3) paths.

    The expensive 5-player full-hand evaluation is done only once per final board;
    half-time winner masks are precomputed by flop and then looked up by a 52-bit
    card mask.  This preserves exact counting without Monte Carlo.
    """
    half = analyze_half_flops(hole_hands, remaining_cards, with_masks=True)
    half_masks = half.pop('winner_masks')

    hole_states = [_hole_state(h) for h in hole_hands]
    rc = [(c, _card_code(c), c.suit_i, 1 << c.value, _card_bit52(c)) for c in remaining_cards]
    triples = tuple(combinations(range(5), 3))

    total = 0
    eq = [0.0] * 5
    hit = [0] * 5
    type_counts = Counter()
    player_type_counts = [Counter() for _ in range(5)]
    community_type_counts = Counter()
    same_color_count = 0
    ge3_count = 0
    ge4_count = 0
    mask_pair_counts = [[0] * 32 for _ in range(32)]

    for extra in combinations(rc, 5):
        code = 0
        sc = [0, 0, 0, 0]
        sm = [0, 0, 0, 0]
        for _c, cc, si, bit, _bit52 in extra:
            code += cc
            sc[si] += 1
            sm[si] |= bit

        vals = []
        for hc, hsc, hsm in hole_states:
            vals.append(_eval_from_state(
                code + hc,
                sc[0] + hsc[0], sc[1] + hsc[1], sc[2] + hsc[2], sc[3] + hsc[3],
                sm[0] | hsm[0], sm[1] | hsm[1], sm[2] | hsm[2], sm[3] | hsm[3]
            ))
        for i, value in enumerate(vals):
            for market_key in hand_market_keys(value):
                player_type_counts[i][market_key] += 1
        best = max(vals)
        winners = [i for i, v in enumerate(vals) if v == best]
        share = 1.0 / len(winners)
        full_mask = 0
        for i in winners:
            eq[i] += share
            hit[i] += 1
            full_mask |= 1 << i
        for market_key in hand_market_keys(best):
            type_counts[market_key] += 1

        # New 全场 > 公牌 > 公牌牌型 market: evaluate only the five board cards.
        board_value = _eval_from_state(
            code, sc[0], sc[1], sc[2], sc[3], sm[0], sm[1], sm[2], sm[3]
        )
        for market_key in hand_market_keys(board_value):
            community_type_counts[market_key] += 1

        div = sum(1 for x in sc if x)
        if div >= 3:
            ge3_count += 1
        if div >= 4:
            ge4_count += 1
        red = sc[1] + sc[2]
        if red in (0, 5):
            same_color_count += 1

        bits = [x[4] for x in extra]
        for a, b, c in triples:
            half_mask = half_masks[bits[a] | bits[b] | bits[c]]
            mask_pair_counts[half_mask][full_mask] += 1
        total += 1

    full = {
        'total': total,
        'equity': [x / total for x in eq],
        'hit': [x / total for x in hit],
        'winner_types': {k: v / total for k, v in type_counts.items()},
        'player_types': [
            {k: counts.get(k, 0) / total for k in HAND_KEY_TO_NAME}
            for counts in player_type_counts
        ],
        'community_same_color_yes': same_color_count / total,
        'community_same_color_no': 1 - same_color_count / total,
        'community_ge3_suits': ge3_count / total,
        'community_ge4_suits': ge4_count / total,
        'community_hand_types': {
            key: community_type_counts.get(key, 0) / total for key in HAND_KEY_TO_NAME
        },
    }

    # Half/full event labels: W=win, L=lose.  When a player is in a tied-best
    # group for a leg, both W and L are considered valid for that leg.
    joint_counts = [dict(WW=0, WL=0, LW=0, LL=0) for _ in range(5)]
    for hm in range(1, 32):
        hc = hm.bit_count()
        for fm in range(1, 32):
            n = mask_pair_counts[hm][fm]
            if not n:
                continue
            fc = fm.bit_count()
            for p in range(5):
                hb = bool(hm & (1 << p))
                fb = bool(fm & (1 << p))
                half_w = hb
                half_l = (not hb) or hc > 1
                full_w = fb
                full_l = (not fb) or fc > 1
                if half_w and full_w:
                    joint_counts[p]['WW'] += n
                if half_w and full_l:
                    joint_counts[p]['WL'] += n
                if half_l and full_w:
                    joint_counts[p]['LW'] += n
                if half_l and full_l:
                    joint_counts[p]['LL'] += n

    denom = total * 10
    half_full = [
        {key: value / denom for key, value in counts.items()}
        for counts in joint_counts
    ]
    return full, half, half_full


def analyze_special_duel(h1, h2, known_board, remaining_cards):
    need=5-len(known_board)
    total=0; eq=[0.0,0.0]; hit=[0,0]
    for extra in combinations(remaining_cards,need):
        board=list(known_board)+list(extra)
        a=hand_key7(h1+board); b=hand_key7(h2+board)
        total+=1
        if a>b: eq[0]+=1; hit[0]+=1
        elif b>a: eq[1]+=1; hit[1]+=1
        else:
            eq[0]+=.5;eq[1]+=.5;hit[0]+=1;hit[1]+=1
    return {'equity':[x/total for x in eq],'hit':[x/total for x in hit],'total':total}


class Ticket:
    __slots__=('stage','market','selection','label','amount','odds','meta','purchase_time',
               'settled','won','result_text','return_amount','split')
    def __init__(self, stage, market, selection, label, amount, odds, meta=None):
        self.stage=stage; self.market=market; self.selection=selection; self.label=label
        self.amount=float(amount); self.odds=float(odds); self.meta=meta or {}
        self.purchase_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.settled=False; self.won=None; self.result_text='待结算'; self.return_amount=0.0; self.split=1


class TexasHoldemSportsbook(tk.Frame):
    def __init__(self,parent,initial_balance=10000,username='Guest',on_back=None,on_balance_change=None):
        super().__init__(parent,bg=ROOT_BG,width=1150,height=750)
        self.pack_propagate(False)
        self.parent=parent; self.username=username; self.balance=float(initial_balance)
        self.on_back=on_back; self.on_balance_change=on_balance_change
        self.deck=None; self.holes=[[] for _ in range(5)]; self.board=[]; self.burns=[]
        self.stage='predeal'; self.tickets=[]; self.market_rows=[]; self.market_by_iid={}
        self.selected_chip=100.0; self.calculating=False; self.destroyed=False
        self.current_scope='full'; self.current_market_tab='h2h'; self.odds_history={}
        self.accordion_state={}
        self.ticket_detail_state={}
        self.sales_open=False
        self.animating=False; self._anim_after_ids=[]
        self.auto_reset_timer=None
        self.card_images={}; self.original_images={}; self.back_image=None
        self.player_card_frames=[]; self.player_labels=[]; self.board_frame=None; self.burn_frame=None
        self._load_assets(); self._build_ui(); self.new_round()
        top=self.winfo_toplevel()
        try: top.geometry(WINDOW_GEOMETRY); top.resizable(False,False)
        except tk.TclError: pass

    # ---------- assets ----------
    def _find_card_dir(self):
        here=os.path.dirname(os.path.abspath(__file__))
        roots=[here,os.path.dirname(here),os.path.dirname(os.path.dirname(here))]
        for root in roots:
            for folder in ('Poker1','Poker2'):
                p=os.path.join(root,'A_Tools','Card',folder)
                if os.path.exists(os.path.join(p,'Background.png')): return p
        return None

    def _fallback(self,card=None,back=False):
        size=CARD_SIZE
        img=Image.new('RGB',size,'#253e66' if back else '#f4efe4'); d=ImageDraw.Draw(img)
        d.rectangle((1,1,size[0]-2,size[1]-2),outline='#D4AF37',width=2)
        if not back and card:
            color='#b2202a' if card.suit in ('♥','♦') else '#111'
            try: f=ImageFont.truetype('arial.ttf',16)
            except: f=ImageFont.load_default()
            d.text((5,5),f'{card.rank}{card.suit}',fill=color,font=f)
        return img

    def _load_assets(self):
        directory=self._find_card_dir(); suit_name={'♠':'Spade','♥':'Heart','♦':'Diamond','♣':'Club'}
        if directory:
            try:
                resample=getattr(Image,'Resampling',Image).LANCZOS
                back_orig=Image.open(os.path.join(directory,'Background.png')).convert('RGBA')
                back=back_orig.resize(CARD_SIZE,resample)
                self.original_images['back']=back_orig; self.back_image=ImageTk.PhotoImage(back,master=self)
                for s in SUITS:
                    for r in RANKS:
                        p=os.path.join(directory,f'{suit_name[s]}{r}.png')
                        orig=Image.open(p).convert('RGBA')
                        img=orig.resize(CARD_SIZE,resample)
                        self.original_images[(s,r)]=orig;self.card_images[(s,r)]=ImageTk.PhotoImage(img,master=self)
                return
            except Exception:
                self.card_images.clear();self.original_images.clear();self.back_image=None
        b=self._fallback(back=True);self.original_images['back']=b;self.back_image=ImageTk.PhotoImage(b,master=self)
        for s in SUITS:
            for r in RANKS:
                c=Card(s,r);img=self._fallback(c);self.original_images[(s,r)]=img;self.card_images[(s,r)]=ImageTk.PhotoImage(img,master=self)

    # ---------- UI ----------
    def _build_ui(self):
        """Original Auto_Texas_Holdem visual language with fixed five-player zones."""
        main_frame=tk.Frame(self,bg=ROOT_BG)
        main_frame.pack(fill=tk.BOTH,expand=True,padx=10,pady=10)

        # ---------------- left: cards only ----------------
        table_canvas=tk.Canvas(main_frame,bg=ROOT_BG,width=500,height=730,highlightthickness=0)
        table_canvas.pack(side=tk.LEFT,fill=tk.Y)
        table_canvas.pack_propagate(False)
        table_canvas.create_rectangle(3,3,496,726,fill=ROOT_BG,outline=GOLD,width=5)

        # Fixed four-row layout requested for the 5-player table:
        # row 1: P1 / P2; row 2: centred P3; row 3: P4 / P5;
        # bottom row: full-width community cards.  Player zones remain 225x155
        # and every card image remains exactly CARD_SIZE (82x115).
        player_specs=[
            (1,15,18,225,155), (2,260,18,225,155),
            (3,138,183,225,155),
            (4,15,348,225,155), (5,260,348,225,155),
        ]
        for number,x,y,w,h in player_specs:
            box=tk.Frame(table_canvas,bg=TABLE_PANEL_BG,bd=2,relief=tk.RAISED,width=w,height=h)
            box.place(x=x,y=y,width=w,height=h);box.pack_propagate(False);box.grid_propagate(False)
            # Canvas labels let half/full hand names be highlighted independently
            # without changing the fixed player-zone geometry.
            lab=tk.Canvas(box,bg=TABLE_PANEL_BG,highlightthickness=0,bd=0,width=w-18,height=22)
            lab.place(x=9,y=4,width=w-18,height=22)
            cf=tk.Frame(box,bg=TABLE_PANEL_BG,width=190,height=CARD_SIZE[1])
            cf.place(x=14,y=28,width=190,height=CARD_SIZE[1]);cf.pack_propagate(False);cf.grid_propagate(False)
            cf.card_origin_x=2;cf.card_spacing=HOLE_CARD_SPACING
            self.player_labels.append(lab);self.player_card_frames.append(cf)

        community_box=tk.Frame(table_canvas,bg=COMMUNITY_BG,bd=2,relief=tk.RAISED,width=450,height=155)
        community_box.place(x=25,y=513,width=450,height=155);community_box.pack_propagate(False);community_box.grid_propagate(False)
        tk.Label(community_box,text='公共牌',font=('Arial',13,'bold'),bg=COMMUNITY_BG,fg=TEXT,anchor='w').place(x=10,y=5,width=420,height=21)
        self.board_frame=tk.Frame(community_box,bg=COMMUNITY_BG,width=430,height=CARD_SIZE[1])
        self.board_frame.place(x=8,y=30,width=430,height=CARD_SIZE[1]);self.board_frame.pack_propagate(False);self.board_frame.grid_propagate(False)
        self.board_frame.card_origin_x=4;self.board_frame.card_spacing=COMMUNITY_CARD_SPACING
        self.burn_frame=tk.Frame(table_canvas,bg=ROOT_BG,width=1,height=1)  # burn cards intentionally hidden

        # ---------------- right: original Auto_Texas_Holdem panel style ----------------
        right_panel=tk.Frame(main_frame,bg=ROOT_BG,width=620)
        right_panel.pack(side=tk.RIGHT,fill=tk.BOTH,expand=True,padx=(10,0));right_panel.pack_propagate(False)

        info_card=tk.Frame(right_panel,bg=PANEL_BG,bd=1,relief=tk.SOLID)
        info_card.pack(fill=tk.X,pady=(0,3))
        info_header=tk.Frame(info_card,bg=HEADER_BG);info_header.pack(fill=tk.X)
        tk.Label(info_header,text='游戏信息',font=('Arial',12,'bold'),bg=HEADER_BG,fg=TITLE_FG).pack(pady=3)
        info_body=tk.Frame(info_card,bg=PANEL_BG);info_body.pack(fill=tk.X,padx=10,pady=6)
        info_body.columnconfigure(0,weight=1);info_body.columnconfigure(1,weight=1)
        self.balance_label=tk.Label(info_body,text='',font=('Arial',13,'bold'),bg=PANEL_BG,fg='black',anchor='w')
        self.balance_label.grid(row=0,column=0,sticky='w')
        self.stage_label=tk.Label(info_body,text='',font=('Arial',12,'bold'),bg=PANEL_BG,fg=ACCENT_GOLD,anchor='e')
        self.stage_label.grid(row=0,column=1,sticky='e')
        self.status=tk.Label(info_body,text='',font=('Arial',9,'bold'),bg=PANEL_BG,fg=TITLE_FG,anchor='w',justify=tk.LEFT,wraplength=575)
        self.status.grid(row=1,column=0,columnspan=2,sticky='ew',pady=(5,0))

        # Original circular chip rack.  No extra "current amount" text is shown below it.
        chip_card=tk.Frame(right_panel,bg=PANEL_BG,bd=1,relief=tk.SOLID);chip_card.pack(fill=tk.X,pady=3)
        chip_header=tk.Frame(chip_card,bg=HEADER_BG);chip_header.pack(fill=tk.X)
        tk.Label(chip_header,text='筹码',font=('Arial',12,'bold'),bg=HEADER_BG,fg=TITLE_FG).pack(pady=3)
        self.chip_container=tk.Frame(chip_card,bg=PANEL_BG);self.chip_container.pack(fill=tk.X,padx=8,pady=5)
        chip_specs=[
            (10,'$10','#ffa500','black'),(25,'$25','#00ff00','black'),(100,'$100','#000000','white'),
            (500,'$500','#FF7DDA','black'),(1000,'$1K','#ffffff','black'),(5000,'$5K','#ff0000','white'),
            (10000,'$10K','#00fbff','black'),(50000,'$50K','#00ffae','black'),(100000,'$100K','#c7a14a','black'),
        ]
        for i in range(len(chip_specs)):self.chip_container.columnconfigure(i,weight=1)
        self.chip_buttons_ui={}
        for i,(value,label,bg,fg) in enumerate(chip_specs):
            cell=tk.Frame(self.chip_container,bg=PANEL_BG);cell.grid(row=0,column=i,padx=1,pady=1,sticky='nsew')
            cv=tk.Canvas(cell,width=48,height=48,bg=PANEL_BG,highlightthickness=0,cursor='hand2');cv.pack(anchor='center')
            cv.create_oval(2,2,46,46,fill=bg,outline='black',width=2,tags='disc')
            cv.create_text(24,24,text=label.replace('$',''),fill=fg,font=('Arial',8 if value>=100000 else 9,'bold'))
            cv.bind('<Button-1>',lambda e,x=value:self.select_chip(x));self.chip_buttons_ui[value]=cv

        # Betting/ticket card: same framed palette as the original Auto_Texas_Holdem.
        bet_card=tk.Frame(right_panel,bg=PANEL_BG,bd=1,relief=tk.SOLID)
        bet_card.pack(fill=tk.BOTH,expand=True,pady=(3,0))
        bet_header=tk.Frame(bet_card,bg=HEADER_BG);bet_header.pack(fill=tk.X)
        tk.Label(bet_header,text='德州彩卷项目',font=('Arial',12,'bold'),bg=HEADER_BG,fg=TITLE_FG).pack(pady=3)

        bet_body=tk.Frame(bet_card,bg=TABLE_PANEL_BG,bd=2,relief=tk.RAISED)
        bet_body.pack(fill=tk.BOTH,expand=True,padx=4,pady=4)

        # Higher-level navigation.  Stage 1/2: Full / Half / Purchase.
        # Stage 3: Full / Purchase (half-time is already known after the flop).
        self.scope_tabs_frame=tk.Frame(bet_body,bg=TABLE_PANEL_BG)
        self.scope_tabs_frame.pack(fill=tk.X,padx=6,pady=(6,2))
        self.scope_buttons={}

        # Second-level market tabs depend on the higher-level page.
        self.category_tabs_frame=tk.Frame(bet_body,bg=TABLE_PANEL_BG)
        self.category_tabs_frame.pack(fill=tk.X,padx=6,pady=(1,3))
        self.tab_buttons={}

        # Header and scrolling rows share the same grid column, so every value is
        # directly under its heading.  The scrollbar has its own matching column.
        market_shell=tk.Frame(bet_body,bg=PANEL_BG)
        self.market_shell=market_shell
        market_shell.pack(fill=tk.BOTH,expand=True,padx=6,pady=(2,4))
        market_shell.grid_rowconfigure(1,weight=1);market_shell.grid_columnconfigure(0,weight=1)
        self.market_header=tk.Frame(market_shell,bg=HEADER_BG,height=30)
        self.market_header.grid(row=0,column=0,sticky='ew');self.market_header.grid_propagate(False)
        self.market_header_labels=[]
        for col,text in enumerate(('选择','历史赔率','获胜概率','固定赔率:1')):
            lbl=tk.Label(self.market_header,text=text,bg=HEADER_BG,fg=TITLE_FG,font=('Arial',9,'bold'),anchor='w' if col==0 else 'center')
            lbl.grid(row=0,column=col,sticky='nsew',padx=(7,2) if col==0 else 2)
            self.market_header_labels.append(lbl)
        for col,weight in enumerate((18,16,12,10)):
            self.market_header.grid_columnconfigure(col,weight=weight,uniform='marketcols')
        self.market_header.grid_rowconfigure(0,weight=1)

        self.market_canvas=tk.Canvas(market_shell,bg=PANEL_BG,highlightthickness=0)
        self.market_scroll=ttk.Scrollbar(market_shell,orient='vertical',command=self.market_canvas.yview)
        self.market_canvas.configure(yscrollcommand=self.market_scroll.set)
        self.market_canvas.grid(row=1,column=0,sticky='nsew');self.market_scroll.grid(row=1,column=1,sticky='ns')
        # Reserve the scrollbar width beside the header so its four columns line up
        # exactly with the four columns in the scrolling content.
        tk.Frame(market_shell,bg=HEADER_BG,width=17,height=30).grid(row=0,column=1,sticky='ns')

        self.market_inner=tk.Frame(self.market_canvas,bg=PANEL_BG)
        self.market_window=self.market_canvas.create_window((0,0),window=self.market_inner,anchor='nw')
        self.market_inner.bind('<Configure>',lambda e:self.market_canvas.configure(scrollregion=self.market_canvas.bbox('all')))
        self.market_canvas.bind('<Configure>',self._on_market_canvas_configure)
        self.market_canvas.bind('<MouseWheel>',self._on_market_mousewheel)
        self.market_inner.bind('<MouseWheel>',self._on_market_mousewheel)
        self.market_canvas.bind('<Button-4>',lambda e:self._scroll_market_units(-1))
        self.market_canvas.bind('<Button-5>',lambda e:self._scroll_market_units(1))

        # Rules and the stage action now share one fixed-height row.  The rules
        # button is deliberately compact while the sale/deal action consumes the
        # remaining width, so both controls stay visually parallel.
        footer=tk.Frame(bet_body,bg=TABLE_PANEL_BG);footer.pack(fill=tk.X,padx=6,pady=(2,6))
        footer.grid_columnconfigure(0,weight=0,minsize=78)
        footer.grid_columnconfigure(1,weight=1)
        footer.grid_rowconfigure(0,minsize=48)
        self.rule_btn=tk.Button(footer,text='规则',command=self.show_rules,bg='#4B8BBE',fg='white',font=('Arial',9,'bold'),bd=1)
        self.rule_btn.grid(row=0,column=0,sticky='nsew',padx=(0,5),pady=0)
        self.action_btn=tk.Button(footer,text='',command=self.advance_stage,bg='#4CAF50',fg='white',font=('Arial',11,'bold'),bd=1)
        self.action_btn.grid(row=0,column=1,sticky='nsew',pady=0)
        self.action_btn.bind('<Button-3>',self.show_card_sequence)
        # No Return button: page exit remains the host/window responsibility.

        # Compatibility object used by worker toggles.
        self.buy_btn=tk.Button(self);self.buy_btn.pack_forget();self.tree=None
        self.select_chip(100);self.update_balance()
        self._rebuild_scope_tabs();self._rebuild_category_tabs();self._update_market_header()

    def _available_scopes(self):
        if self.stage in ('predeal','holes'):
            return [('full','全场'),('half','半场'),('purchase','购买记录')]
        return [('full','全场'),('purchase','购买记录')]

    def _rebuild_scope_tabs(self):
        if not hasattr(self,'scope_tabs_frame'):
            return
        for w in self.scope_tabs_frame.winfo_children():
            w.destroy()
        self.scope_buttons={}
        allowed=[k for k,_ in self._available_scopes()]
        if self.current_scope not in allowed:
            self.current_scope='full'
        for key,label in self._available_scopes():
            b=tk.Button(
                self.scope_tabs_frame,text=label,command=lambda k=key:self.switch_scope(k),
                font=('Arial',10,'bold'),bd=1,padx=5,pady=6,cursor='hand2'
            )
            b.pack(side=tk.LEFT,padx=1,fill=tk.X,expand=True)
            self.scope_buttons[key]=b
        self._style_scope_tabs()

    def _style_scope_tabs(self):
        # The three top-level pages deliberately use different selected colours.
        # This makes 全场 / 半场 / 购买记录 distinguishable at a glance.
        selected_colors={'full':'#315546','half':'#315B72','purchase':'#7A5A2D'}
        hover_colors={'full':'#3D6758','half':'#3D6B86','purchase':'#92713C'}
        for k,b in getattr(self,'scope_buttons',{}).items():
            active=(k==self.current_scope)
            b.config(
                bg=selected_colors.get(k,'#315546') if active else PANEL_BG,
                fg='white' if active else TITLE_FG,
                activebackground=hover_colors.get(k,HEADER_BG) if active else HEADER_BG
            )

    def _category_specs(self):
        if self.current_scope=='full':
            return [('h2h','头VS头'),('hand','牌型'),('public','公牌'),('special','特别事项')]
        if self.current_scope=='half':
            return [('h2h','头VS头'),('hand','牌型'),('public','公牌'),('half_full','半全场')]
        return []

    def _rebuild_category_tabs(self):
        if not hasattr(self,'category_tabs_frame'):
            return
        for w in self.category_tabs_frame.winfo_children():
            w.destroy()
        self.tab_buttons={}
        specs=self._category_specs()
        valid=[k for k,_ in specs]
        if valid and self.current_market_tab not in valid:
            self.current_market_tab=valid[0]
        if self.current_scope=='purchase':
            self.category_tabs_frame.pack_forget()
            return
        if not self.category_tabs_frame.winfo_manager():
            self.category_tabs_frame.pack(fill=tk.X,padx=6,pady=(1,3),before=self.market_shell)
        for key,label in specs:
            b=tk.Button(
                self.category_tabs_frame,text=label,command=lambda k=key:self.switch_market_tab(k),
                font=('Arial',9,'bold'),bd=1,padx=5,pady=5,cursor='hand2'
            )
            b.pack(side=tk.LEFT,padx=1,fill=tk.X,expand=True)
            self.tab_buttons[key]=b
        self._style_tabs()

    def _style_tabs(self):
        for k,b in getattr(self,'tab_buttons',{}).items():
            active=(k==self.current_market_tab)
            b.config(bg='#315546' if active else PANEL_BG,fg='white' if active else TITLE_FG,
                     activebackground='#315546' if active else HEADER_BG)

    def _set_header_columns(self, texts, weights):
        for w in self.market_header.winfo_children():
            w.destroy()
        self.market_header_labels=[]
        for col in range(6):
            self.market_header.grid_columnconfigure(col, weight=0, uniform='')
        for col,(text,weight) in enumerate(zip(texts,weights)):
            lbl=tk.Label(self.market_header,text=text,bg=HEADER_BG,fg=TITLE_FG,
                         font=('Arial',9,'bold'),anchor='center')
            lbl.grid(row=0,column=col,sticky='nsew',padx=2)
            self.market_header_labels.append(lbl)
            self.market_header.grid_columnconfigure(col,weight=weight,uniform='marketcols')
        self.market_header.grid_rowconfigure(0,weight=1)

    def _update_market_header(self):
        if not hasattr(self,'market_header'): return
        if self.current_scope=='purchase':
            self._set_header_columns(('购买记录详情',),(1,))
        else:
            self._set_header_columns(
                ('选择','历史赔率','获胜概率','固定赔率:1'),
                (18,16,12,10)
            )

    def switch_scope(self,key):
        allowed={k for k,_ in self._available_scopes()}
        if key not in allowed:
            return
        self.current_scope=key
        if key!='purchase':
            valid=[k for k,_ in self._category_specs()]
            if self.current_market_tab not in valid:
                self.current_market_tab=valid[0]
        self._style_scope_tabs();self._rebuild_category_tabs();self._update_market_header();self.render_market_rows()

    def switch_market_tab(self,key):
        if self.current_scope=='purchase':
            return
        valid={k for k,_ in self._category_specs()}
        if key not in valid:
            return
        self.current_market_tab=key;self._style_tabs();self._update_market_header();self.render_market_rows()

    def _market_group(self,row):
        if row.get('scope','full')=='half':
            if row.get('market')=='half_h2h': return 'h2h'
            if row.get('market') in ('half_winner_type','half_player_type'): return 'hand'
            if row.get('market')=='flop_pattern': return 'public'
            if row.get('market')=='half_full': return 'half_full'
            return 'half_full'
        m=row.get('market')
        if m=='h2h': return 'h2h'
        if m in ('winner_type','player_type'): return 'hand'
        if m in ('community_same_color','community_suit_diversity','remaining_suit_relation',
                 'turn_river_pair','board_rank_pairing','community_hand_type'): return 'public'
        return 'special'

    def select_chip(self,v):
        self.selected_chip=float(v)
        for val,cv in getattr(self,'chip_buttons_ui',{}).items():
            cv.itemconfigure('disc',width=4 if val==v else 2,outline='#D4AF37' if val==v else '#444')

    def _on_market_canvas_configure(self,event):
        """Keep the embedded market frame at least as tall as the viewport.

        Tk Canvas can vertically offset a scrollregion that is shorter than the
        visible viewport.  That was the cause of collapsed Accordion headers
        appearing at the bottom with a large blank block above them.  Giving the
        embedded window a viewport-height minimum keeps every collapsed page
        anchored at y=0 while still allowing long pages to scroll normally.
        """
        try:
            self.market_inner.update_idletasks()
            req_h=max(1,self.market_inner.winfo_reqheight())
            target_h=max(int(event.height),req_h)
            self.market_canvas.itemconfigure(self.market_window,width=int(event.width),height=target_h)
            self.market_canvas.configure(scrollregion=(0,0,int(event.width),target_h))
        except tk.TclError:
            pass

    def _scroll_market_units(self,units):
        if hasattr(self,'market_canvas'):
            self.market_canvas.yview_scroll(int(units),'units')
        return 'break'

    def _on_market_mousewheel(self,event):
        delta=getattr(event,'delta',0)
        if delta:
            units=-int(delta/120)
            if units==0: units=-1 if delta>0 else 1
            return self._scroll_market_units(units)
        return 'break'

    def _bind_market_wheel(self,widget):
        widget.bind('<MouseWheel>',self._on_market_mousewheel)
        widget.bind('<Button-4>',lambda e:self._scroll_market_units(-1))
        widget.bind('<Button-5>',lambda e:self._scroll_market_units(1))

    def _configure_row_columns(self,line,purchase=False):
        weights=(9,25,12,10,12,13) if purchase else (18,16,12,10)
        for col in range(6):
            line.grid_columnconfigure(col,weight=0,uniform='')
        for col,weight in enumerate(weights):
            line.grid_columnconfigure(col,weight=weight,uniform='marketcols')
        line.grid_rowconfigure(0,weight=1)

    def _winner_summary(self, half=False):
        """Return the currently known table winner(s) and winning hand category."""
        if half:
            if len(self.board) < 3:
                return None
            vals, best, winners = self._half_result()
        else:
            if len(self.board) < 5:
                return None
            vals, best, winners = self._global_result()
        if not winners or best is None:
            return None
        names=' / '.join(f'玩家{i+1}' for i in winners)
        if len(winners)==1:
            return f'{names}获胜 · {hand_display_name(best)}'
        return f'{names}平局 · {hand_display_name(best)}'

    def _result_line(self, half=False):
        """Return concise showdown wording used by purchase records.

        Required display format:
          半场: 玩家2 · 对子
          全场: 玩家5 · 同花
        Multiple tied winners are retained as 玩家X / 玩家Y.
        """
        summary=self._winner_summary(half=half)
        if not summary:
            return None
        # _winner_summary returns "玩家X获胜 · 牌型" or "玩家X / 玩家Y平局 · 牌型".
        summary=summary.replace('获胜 · ',' · ').replace('平局 · ',' · ').replace('一对','对子')
        prefix='半场' if half else '全场'
        return f'{prefix}: {summary}'

    def _public_market_result_detail(self, t):
        """Return only the actual public-card outcome for pure board markets.

        These purchase records must never fall through to a player's showdown
        result.  Keep the wording compact, e.g. ``公牌 · 对子`` or
        ``公牌 · 翻2+转河1``.
        """
        if t.market == 'flop_pattern':
            if len(self.board) < 3:
                return '待结算'
            flags = flop_three_flags(self.board[:3])
            for key, label in (
                ('straight_flush', '同花顺'),
                ('trips', '三条'),
                ('straight', '顺子'),
                ('flush', '同花'),
                ('pair', '对子'),
            ):
                if flags.get(key):
                    return f'公牌 · {label}'
            return '公牌 · 其他'

        if t.market == 'community_same_color':
            if not self.board:
                return '待结算'
            colors = {0 if c.suit in ('♥', '♦') else 1 for c in self.board}
            # Once both colours have appeared, "same colour" can no longer recover.
            if len(colors) > 1:
                return '公牌 · 不同颜色'
            if len(self.board) < 5:
                return '待结算'
            return '公牌 · 同一颜色'

        if t.market == 'community_suit_diversity':
            if len(self.board) < 5:
                return '待结算'
            return f'公牌 · {suit_diversity(self.board)}种花色'

        if t.market == 'remaining_suit_relation':
            if len(self.board) < 5:
                return '待结算'
            label = '转河同花色' if self.board[3].suit_i == self.board[4].suit_i else '转河不同花色'
            return f'公牌 · {label}'

        if t.market == 'turn_river_pair':
            if len(self.board) < 5:
                return '待结算'
            label = '转河对子' if self.board[3].value == self.board[4].value else '转河非对子'
            return f'公牌 · {label}'

        if t.market == 'board_rank_pairing':
            if len(self.board) < 5:
                return '待结算'
            key = self._board_rank_match_pattern()
            if key:
                label = self.BOARD_RANK_PAIRING_LABELS[key]
            else:
                flop_ranks = {c.value for c in self.board[:3]}
                later_ranks = {c.value for c in self.board[3:5]}
                label = '其他配对' if flop_ranks & later_ranks else '无配对'
            return f'公牌 · {label}'

        if t.market == 'community_hand_type':
            if len(self.board) < 5:
                return '待结算'
            value = hand_key7(self.board)
            return f'公牌 · {hand_display_name(value).replace("一对", "对子")}'

        return None

    PURE_PUBLIC_MARKETS = frozenset({
        'flop_pattern', 'community_same_color', 'community_suit_diversity',
        'remaining_suit_relation', 'turn_river_pair', 'board_rank_pairing',
        'community_hand_type',
    })

    def _ticket_result_detail(self,t):
        """Purchase-record result using the concise table-result format.

        Pure public-card tickets are deliberately isolated from player showdown
        text: their 下注结果 is always the corresponding board outcome, e.g.
        ``公牌 · 对子`` or ``公牌 · 翻2+转河1配对``.
        """
        status=t.result_text
        if t.market in self.PURE_PUBLIC_MARKETS:
            return self._public_market_result_detail(t) or '待结算'
        if t.market=='half_full':
            half=self._result_line(half=True)
            full=self._result_line(half=False)
            if half and full:
                half_body=half.split(': ',1)[1]
                full_body=full.split(': ',1)[1]
                return f'半全场: {half_body}  ~  {full_body}'
            if half:
                return half
            if full:
                return full
        elif t.market in ('half_h2h','half_winner_type','half_player_type'):
            half=self._result_line(half=True)
            if half:
                return half
        else:
            full=self._result_line(half=False)
            if full:
                return full
        if t.settled:
            return status
        return '待结算'

    def _row_bet_content(self,row):
        """Primary wording shown for a market row and saved on the ticket."""
        market=row.get('market','')
        label=str(row.get('selection_label','')).replace(' / ','/').replace('一对','对子')
        if market=='h2h':
            return f"玩家{int(row['selection'])+1} · 头VS头"
        if market=='half_h2h':
            return f"玩家{int(row['selection'])+1} · 半头VS头"
        if market=='half_full':
            meta=row.get('meta') or {}; p=int(meta.get('player',0))
            return f"玩家{p+1} · 半全场 ({label})"
        if market=='half_player_type':
            meta=row.get('meta') or {}; p=int(meta.get('player',0))
            return f"玩家{p+1} · 半场独立牌型({label})"
        if market=='half_winner_type':
            return f"半场 · 赢家牌型({label})"
        if market=='player_type':
            meta=row.get('meta') or {}; p=int(meta.get('player',0))
            return f"玩家{p+1} · 全场独立牌型({label})"
        if market=='winner_type':
            return f"全场 · 赢家牌型({label})"
        if market=='flop_pattern':
            short=label.replace('（包括同花顺）','')
            return f"翻牌3张 · {short}"
        if market=='board_rank_pairing':
            return f"公牌配对 · {label}"
        if market=='community_hand_type':
            return f"公牌牌型 · {label}"
        if market=='turn_river_pair':
            return f"公牌 · 转牌河牌2张({label})"
        if market=='community_same_color':
            return f"公牌 · 同一颜色({label})"
        if market=='community_suit_diversity':
            return f"公牌 · 不同花色({label})"
        if market=='remaining_suit_relation':
            return f"公牌 · 剩余2张({label})"
        if market=='special_duel':
            return f"{label} · {row.get('market_label','特殊对决')}"
        if market=='hole_suited_count':
            return f"特别事项 · 同花手牌({label})"
        if market=='hole_pair_count':
            return f"特别事项 · 对子手牌({label})"
        if market=='hole_rank_pattern_match':
            return f"特别事项 · 相同手牌点数({label})"
        if market=='specified_hand_result':
            meta=row.get('meta') or {}
            hand=str(meta.get('hand_code',''))
            outcome='胜' if str(meta.get('outcome',''))=='win' else '败'
            return f"特别事项 · 手牌{hand} · {outcome}"
        return f"{row.get('market_label','项目')}({label})"

    def _ticket_scope_category(self,t):
        # Compact purchase records use the exact player/content wording locked at purchase.
        return t.label

    def _ticket_compact_statuses(self,t):
        """Return one or two compact status icons for the purchase-record summary.

        Ordinary tickets have one state: ✓ won, ✕ lost, ? unresolved.
        半全场 has two independent legs (half / full), so each leg is shown
        separately.  This lets a ticket display e.g. ✓ ? after the flop when
        the half-time condition is already correct but the full-time result is
        still unknown.
        """
        green='#13752B'
        red='#B00020'
        blue='#1565C0'

        if t.market!='half_full':
            if not t.settled:
                return [('?',blue)]
            return [('✓',green)] if t.won else [('✕',red)]

        meta=t.meta or {}
        p=int(meta.get('player',0))
        code=str(meta.get('half_full_code',''))
        if len(code)!=2 or not (0 <= p < 5):
            if not t.settled:
                return [('?',blue),('?',blue)]
            icon=('✓',green) if t.won else ('✕',red)
            return [icon,icon]

        # Half-time leg is objectively known once the flop (3 public cards) is open.
        if len(self.board)>=3 and all(len(h)==2 for h in self.holes):
            try:
                _hv,_hb,half_winners=self._half_result()
                half_ok=self._tie_wildcard_leg_matches(p,half_winners,code[0])
                half_state=('✓',green) if half_ok else ('✕',red)
            except Exception:
                half_state=('?',blue)
        else:
            half_state=('?',blue)

        # Full-time leg is known only after all five community cards are open.
        if len(self.board)>=5 and all(len(h)==2 for h in self.holes):
            try:
                _vals,_best,full_winners=self._global_result()
                full_ok=self._tie_wildcard_leg_matches(p,full_winners,code[1])
                full_state=('✓',green) if full_ok else ('✕',red)
            except Exception:
                full_state=('?',blue)
        else:
            full_state=('?',blue)
        return [half_state,full_state]

    def _toggle_ticket_detail(self,index):
        # Purchase records are compact by default.  Clicking one ticket expands
        # only that ticket into the seven-field detail view.
        self.ticket_detail_state[index]=not self.ticket_detail_state.get(index,False)
        pos=self.market_canvas.yview()[0] if hasattr(self,'market_canvas') else 0.0
        self.render_market_rows(reset_scroll=False)
        try:self.market_canvas.yview_moveto(pos)
        except tk.TclError:pass

    def _render_purchase_records(self):
        stage_names={'predeal':'阶段1','holes':'阶段2','flop':'阶段3'}
        if not self.tickets:
            lab=tk.Label(self.market_inner,text='本局尚未购买德州彩卷。',bg=PANEL_BG,fg='#777',font=('Arial',11,'bold'),pady=25)
            lab.pack(fill=tk.X);self._bind_market_wheel(lab);return

        for index,t in enumerate(self.tickets, start=1):
            expanded=self.ticket_detail_state.get(index,False)
            card=tk.Frame(self.market_inner,bg=PANEL_BG,bd=1,relief=tk.SOLID,cursor='hand2')
            card.pack(fill=tk.X,padx=7,pady=(6,3))
            self._bind_market_wheel(card)

            # Default compact record: exactly two visual rows.
            # Row 1 is the heading; row 2 is the ticket summary.
            summary=tk.Frame(card,bg=PANEL_BG,cursor='hand2')
            summary.pack(fill=tk.X,padx=5,pady=(4,4));self._bind_market_wheel(summary)
            for col,weight in enumerate((24,23,9,18)):
                summary.grid_columnconfigure(col,weight=weight,uniform='ticket_summary')

            return_title='已返还' if t.settled else '预计返还'
            headers=('下注内容','下注金额 @赔率','状态',return_title)
            values=(
                self._ticket_scope_category(t),
                f'{money(t.amount)}  @{t.odds:.2f}:1',
                None,
                money(t.return_amount) if t.settled else f"({money(t.amount*(1.0+t.odds))})",
            )
            for col,title_text in enumerate(headers):
                lab=tk.Label(summary,text=title_text,bg=PANEL_BG,fg=TITLE_FG,font=('Arial',9,'bold'),anchor='center',cursor='hand2')
                lab.grid(row=0,column=col,sticky='nsew',padx=2,pady=(0,3));self._bind_market_wheel(lab)
                lab.bind('<Button-1>',lambda e,i=index:self._toggle_ticket_detail(i))

            for col,value in enumerate(values):
                if col==2:
                    # Status cell: ordinary tickets have one icon; 半全场 shows
                    # two independently-coloured leg icons (half / full).
                    status_cell=tk.Frame(summary,bg=PANEL_BG,cursor='hand2')
                    status_cell.grid(row=1,column=col,sticky='nsew',padx=2,pady=(0,1))
                    self._bind_market_wheel(status_cell)
                    status_cell.bind('<Button-1>',lambda e,i=index:self._toggle_ticket_detail(i))
                    icon_wrap=tk.Frame(status_cell,bg=PANEL_BG,cursor='hand2')
                    icon_wrap.place(relx=.5,rely=.5,anchor='center')
                    self._bind_market_wheel(icon_wrap)
                    icon_wrap.bind('<Button-1>',lambda e,i=index:self._toggle_ticket_detail(i))
                    for icon_text,icon_color in self._ticket_compact_statuses(t):
                        icon=tk.Label(icon_wrap,text=icon_text,bg=PANEL_BG,fg=icon_color,
                                      font=('Arial',13,'bold'),padx=1,cursor='hand2')
                        icon.pack(side=tk.LEFT)
                        self._bind_market_wheel(icon)
                        icon.bind('<Button-1>',lambda e,i=index:self._toggle_ticket_detail(i))
                    continue
                fg=('#13752B' if t.settled else '#111') if col==3 else '#111'
                lab=tk.Label(summary,text=value,bg=PANEL_BG,fg=fg,font=('Arial',9,'bold'),anchor='center',cursor='hand2')
                lab.grid(row=1,column=col,sticky='nsew',padx=2,pady=(0,1));self._bind_market_wheel(lab)
                lab.bind('<Button-1>',lambda e,i=index:self._toggle_ticket_detail(i))
            summary.bind('<Button-1>',lambda e,i=index:self._toggle_ticket_detail(i))
            card.bind('<Button-1>',lambda e,i=index:self._toggle_ticket_detail(i))

            # Expanded state adds the requested full ticket details below the two
            # compact rows; collapsing returns immediately to the two-line form.
            if not expanded:
                continue

            divider=tk.Frame(card,bg=HEADER_BG,height=2,cursor='hand2')
            divider.pack(fill=tk.X,padx=5,pady=(1,4));self._bind_market_wheel(divider)
            divider.bind('<Button-1>',lambda e,i=index:self._toggle_ticket_detail(i))

            body=tk.Frame(card,bg=PANEL_BG)
            body.pack(fill=tk.X,padx=8,pady=(0,6));self._bind_market_wheel(body)
            body.grid_columnconfigure(0,weight=0,minsize=76)
            body.grid_columnconfigure(1,weight=1)
            details=(
                ('下注阶段',stage_names.get(t.stage,t.stage)),
                ('下注时间',t.purchase_time),
                ('下注金额',money(t.amount)),
                ('下注内容',t.label),
                ('下注赔率',f'{t.odds:.2f}:1'),
                ('下注结果',self._ticket_result_detail(t)),
                ('下注返还',money(t.return_amount) if t.settled else '—'),
            )
            for row_i,(name,value) in enumerate(details):
                name_lab=tk.Label(body,text=name,bg=PANEL_BG,fg=TITLE_FG,font=('Arial',9,'bold'),anchor='w')
                name_lab.grid(row=row_i,column=0,sticky='nw',padx=(0,7),pady=2);self._bind_market_wheel(name_lab)
                if name=='下注返还' and t.settled and t.return_amount>0:
                    fg='#13752B'
                elif name=='下注结果' and t.won is False:
                    fg='#8B1A1A'
                elif name=='下注结果' and t.won is True:
                    fg='#13752B'
                else:
                    fg='#222'
                value_lab=tk.Label(body,text=value,bg=PANEL_BG,fg=fg,font=('Arial',9,'bold' if name in ('下注结果','下注返还') else 'normal'),
                                   anchor='w',justify=tk.LEFT,wraplength=445)
                value_lab.grid(row=row_i,column=1,sticky='ew',pady=2);self._bind_market_wheel(value_lab)

    def _accordion_group_name(self,row):
        return row.get('accordion_group') or row.get('market_label','项目')

    def _toggle_accordion(self,state_key):
        current=self.accordion_state.get(state_key,False)
        pos=self.market_canvas.yview()[0] if hasattr(self,'market_canvas') else 0.0
        self.accordion_state[state_key]=not current
        self.render_market_rows(reset_scroll=False)
        try:self.market_canvas.yview_moveto(pos)
        except tk.TclError:pass

    def _render_market_item(self,row,indent=0):
        key=(row.get('scope','full'),row['market'],str(row['selection']))
        hist=self.odds_history.get(key,[])

        # Zebra rows: original PANEL_BG, then light blue, alternating for every
        # actual selectable bet row. Accordion headers keep their dark header colour.
        zebra_index=getattr(self,'_market_zebra_index',0)
        row_bg=MARKET_ALT_BG2 if zebra_index % 2 == 0 else MARKET_ALT_BG
        self._market_zebra_index=zebra_index+1

        line=tk.Frame(
            self.market_inner,
            bg=row_bg,
            bd=0,
            height=56
        )
        line.pack(
            fill=tk.X,
            padx=(8+int(indent),8),
            pady=0
        )
        line.pack_propagate(False)
        line.grid_propagate(False)
        self._configure_row_columns(line);self._bind_market_wheel(line)

        left=tk.Frame(line,bg=row_bg);left.grid(row=0,column=0,sticky='nsew',padx=(7,2),pady=3)
        self._bind_market_wheel(left)
        content=self._row_bet_content(row)
        a=tk.Label(left,text=content,bg=row_bg,fg='#111',font=('Arial',9,'bold'),anchor='w',wraplength=175)
        a.pack(fill=tk.BOTH,expand=True,pady=(2,0));self._bind_market_wheel(a)

        htxt=', '.join(f'{x:.2f}' for x in hist[-5:]) if hist else '—'
        hist_lab=tk.Label(line,text=htxt,bg=row_bg,fg='#13752B',font=('Arial',9,'bold'),wraplength=145,justify=tk.CENTER)
        hist_lab.grid(row=0,column=1,sticky='nsew',padx=3,pady=5);self._bind_market_wheel(hist_lab)
        prob_lab=tk.Label(line,text=f"{row['prob']*100:.2f}%",bg=row_bg,fg='#222',font=('Arial',10,'bold'))
        prob_lab.grid(row=0,column=2,sticky='nsew',padx=3,pady=5);self._bind_market_wheel(prob_lab)

        od=row['odds']
        enabled=bool(self.sales_open and not self.calculating and not self.animating and self.stage!='settled')
        ob=tk.Button(
            line,text=f'{od:.2f}',command=lambda r=row:self.buy_market_row(r),
            bg='#EEF0F6' if enabled else '#D0D0D0',fg='#081235' if enabled else '#777777',
            disabledforeground='#777777',font=('Arial',12,'bold'),bd=0,
            cursor='hand2' if enabled else '',activebackground='#DDE5FF',
            state=tk.NORMAL if enabled else tk.DISABLED
        )
        ob.grid(row=0,column=3,sticky='nsew',padx=7,pady=9);self._bind_market_wheel(ob)
        separator = tk.Frame(
            self.market_inner,
            bg=MARKET_SEPARATOR_BG,
            height=MARKET_SEPARATOR_HEIGHT
        )
        separator.pack(
            fill=tk.X,
            padx=(8+int(indent),8),
            pady=0
        )
        separator.pack_propagate(False)
        self._bind_market_wheel(separator)

    def _finish_market_layout(self,reset_scroll=True):
        """Synchronize Canvas geometry and keep collapsed Accordions at the top."""
        try:
            self.market_inner.update_idletasks()
            viewport_h=max(1,self.market_canvas.winfo_height())
            viewport_w=max(1,self.market_canvas.winfo_width())
            content_h=max(1,self.market_inner.winfo_reqheight())
            target_h=max(viewport_h,content_h)
            self.market_canvas.itemconfigure(self.market_window,width=viewport_w,height=target_h)
            self.market_canvas.configure(scrollregion=(0,0,viewport_w,target_h))
            if reset_scroll:
                self.market_canvas.yview_moveto(0.0)
        except tk.TclError:
            pass

    def _render_nested_player_groups(self, group_rows, parent_state_key):
        # Second-level accordions used by 独立牌型: one collapsible section/player.
        subgroups={}
        order=[]
        loose=[]
        for row in group_rows:
            sub=row.get('subaccordion_group')
            if not sub:
                loose.append(row);continue
            if sub not in subgroups:
                subgroups[sub]=[];order.append(sub)
            subgroups[sub].append(row)
        for row in loose:
            self._render_market_item(row,indent=8)
        for sub in order:
            rows=subgroups[sub]
            state_key=tuple(parent_state_key)+('sub',sub)
            if state_key not in self.accordion_state:
                self.accordion_state[state_key]=False
            opened=self.accordion_state[state_key]
            header=tk.Frame(self.market_inner,bg='#565863',height=38,cursor='hand2')
            header.pack(fill=tk.X,padx=(12,4),pady=(1,2));header.pack_propagate(False)
            title=tk.Label(header,text=f'{sub} ({len(rows)})',bg='#565863',fg='white',font=('Arial',9,'bold'),anchor='w',padx=10,cursor='hand2')
            title.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
            arrow=tk.Label(header,text='▲' if opened else '▼',bg='#565863',fg='white',font=('Arial',10,'bold'),width=4,cursor='hand2')
            arrow.pack(side=tk.RIGHT,fill=tk.Y)
            for w in (header,title,arrow):
                w.bind('<Button-1>',lambda e,k=state_key:self._toggle_accordion(k))
                self._bind_market_wheel(w)
            if opened:
                for row in rows:
                    self._render_market_item(row,indent=12)

    def render_market_rows(self,reset_scroll=True):
        if not hasattr(self,'market_inner'): return
        for w in self.market_inner.winfo_children(): w.destroy()
        self._update_market_header()
        if self.current_scope=='purchase':
            self._render_purchase_records()
            self._finish_market_layout(reset_scroll)
            return

        self._market_zebra_index=0
        rows=[r for r in self.market_rows
              if r.get('scope','full')==self.current_scope and self._market_group(r)==self.current_market_tab]
        if not rows:
            lab=tk.Label(self.market_inner,text='当前阶段没有此类德州彩卷',bg=PANEL_BG,fg='#777',font=('Arial',11,'bold'),pady=25)
            lab.pack(fill=tk.X);self._bind_market_wheel(lab)
            self._finish_market_layout(reset_scroll)
            return

        groups={}
        order=[]
        for row in rows:
            name=self._accordion_group_name(row)
            if name not in groups:
                groups[name]=[];order.append(name)
            groups[name].append(row)

        single_group_page=(len(order)==1)
        for name in order:
            group_rows=groups[name]
            distinct={str(r.get('selection')) for r in group_rows}
            subnames=[]
            for r in group_rows:
                sub=r.get('subaccordion_group')
                if sub and sub not in subnames: subnames.append(sub)

            direct_section=single_group_page or (self.stage=='flop' and len(distinct)<=1 and not subnames)
            if direct_section:
                if subnames:
                    self._render_nested_player_groups(group_rows,(self.current_scope,self.current_market_tab,name))
                else:
                    for direct_row in group_rows:
                        self._render_market_item(direct_row)
                spacer=tk.Frame(self.market_inner,bg=PANEL_BG,height=3)
                spacer.pack(fill=tk.X);self._bind_market_wheel(spacer)
                continue

            state_key=(self.current_scope,self.current_market_tab,name)
            if state_key not in self.accordion_state:
                self.accordion_state[state_key]=False
            opened=self.accordion_state[state_key]
            count=len(subnames) if subnames else len(distinct)
            header=tk.Frame(self.market_inner,bg='#3F404A',height=42,cursor='hand2')
            header.pack(fill=tk.X,pady=(1,3));header.pack_propagate(False)
            title=tk.Label(header,text=f'{name} ({count})',bg='#3F404A',fg='white',font=('Arial',10,'bold'),anchor='w',padx=10,cursor='hand2')
            title.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
            arrow=tk.Label(header,text='▲' if opened else '▼',bg='#3F404A',fg='white',font=('Arial',11,'bold'),width=4,cursor='hand2')
            arrow.pack(side=tk.RIGHT,fill=tk.Y)
            for w in (header,title,arrow):
                w.bind('<Button-1>',lambda e,k=state_key:self._toggle_accordion(k))
                self._bind_market_wheel(w)
            if opened:
                if subnames:
                    self._render_nested_player_groups(group_rows,state_key)
                else:
                    for row in group_rows:
                        self._render_market_item(row)
                sep=tk.Frame(self.market_inner,bg=PANEL_BG,height=4);sep.pack(fill=tk.X);self._bind_market_wheel(sep)

        self._finish_market_layout(reset_scroll)

    def buy_market_row(self,row):
        if not self.sales_open or self.calculating or self.animating or self.stage=='settled': return
        amt=round(float(self.selected_chip),2)
        balance=round(float(self.balance),2)
        # Exact-balance purchase is valid.  A half-cent tolerance protects against
        # binary float residue from host balance updates.
        if amt<=0 or amt-balance>0.005:
            messagebox.showwarning('余额不足','余额不足，无法购买这张德州彩卷。');return
        self.balance=round(max(0.0,balance-amt),2);self.update_balance()
        ticket_meta=dict(row.get('meta') or {})
        content=self._row_bet_content(row)
        ticket_meta['display_content']=content
        t=Ticket(self.stage,row['market'],row['selection'],content,amt,row['odds'],ticket_meta)
        self.tickets.append(t)
        self.status.config(text=f"已购买：{row['selection_label']}  {money(amt)} @ {row['odds']:.2f}:1")
        if self.current_scope=='purchase': self.render_market_rows()

    def show_ticket_history(self):
        self.switch_scope('purchase')

    def update_balance(self):
        self.balance_label.config(text=f'余额：{money(self.balance)}')
        update_balance_in_json(self.username,self.balance)
        if callable(self.on_balance_change): self.on_balance_change(float(self.balance))

    def _clear_cards(self):
        for frame in self.player_card_frames+[self.board_frame]:
            for w in frame.winfo_children(): w.destroy()

    def _card_target_x(self,frame,index):
        return int(getattr(frame,'card_origin_x',2) + index*getattr(frame,'card_spacing',HOLE_CARD_SPACING))

    def _show_card(self,frame,card,face=True,index=0):
        img=self.card_images[(card.suit,card.rank)] if face else self.back_image
        lab=tk.Label(frame,image=img,bg=frame.cget('bg'),bd=0,highlightthickness=0)
        lab.image=img
        lab.place(x=self._card_target_x(frame,index),y=0,width=CARD_SIZE[0],height=CARD_SIZE[1])
        return lab

    def _draw_player_label(self,index):
        """Draw 玩家X - 半场牌型 & 全场牌型 with per-stage winner highlighting.

        Half-time is fixed once the flop is visible.  Full-time remains 待定 until
        all five community cards are out; this avoids presenting a turn-only hand
        as the final full-game category.  A winning stage hand is marked with a
        pale-yellow highlighter rectangle and black text.
        """
        if not (0 <= index < len(self.player_labels)):
            return
        canvas=self.player_labels[index]
        try:
            canvas.delete('all')
        except tk.TclError:
            return
        # Shrink only the label font when unusually long categories (for example
        # 皇家同花顺) would exceed the fixed 207px label rail.  Card/player-box
        # dimensions remain unchanged.
        half_preview=''
        full_preview=''
        if len(self.board) >= 3 and len(self.holes[index]) >= 2:
            hv, _hb, _hw=self._half_result()
            half_preview=hand_display_name(hv[index]) if index < len(hv) else '待定'
            full_preview=(hand_display_name(self._global_result()[0][index]) if len(self.board) >= 5 else '待定')
        preview=f'玩家{index+1}' + (f' - {half_preview} & {full_preview}' if half_preview else '')
        font_size=10
        font=tkfont.Font(family='Arial',size=font_size,weight='bold')
        max_width=max(1,int(float(canvas.cget('width')) or 207))
        while font_size>8 and font.measure(preview)>max_width:
            font_size-=1; font.configure(size=font_size)
        x=0; y=11
        def segment(text,fg=TEXT,highlight=False):
            nonlocal x
            width=max(1,font.measure(text))
            if highlight:
                canvas.create_rectangle(x-1,2,x+width+1,20,fill='#FFF2A8',outline='')
                fg='#111111'
            canvas.create_text(x,y,text=text,font=font,fill=fg,anchor='w')
            x += width

        segment(f'玩家{index+1}')
        if len(self.board) < 3 or len(self.holes[index]) < 2:
            return

        half_vals, _half_best, half_winners=self._half_result()
        half_name=hand_display_name(half_vals[index]) if index < len(half_vals) else '待定'
        segment(' - ')
        segment(half_name,highlight=index in half_winners)
        segment(' & ')

        if len(self.board) >= 5:
            vals,best,full_winners=self._global_result()
            full_name=hand_display_name(vals[index])
            segment(full_name,highlight=index in full_winners)
        else:
            segment('待定',fg='#D9D9D9')

    def _draw_all_player_labels(self):
        for i in range(len(self.player_labels)):
            self._draw_player_label(i)

    def render_cards(self):
        self._clear_cards()
        for i,h in enumerate(self.holes):
            for j,c in enumerate(h):
                self._show_card(self.player_card_frames[i],c,face=(self.stage!='predeal'),index=j)
        for j,c in enumerate(self.board): self._show_card(self.board_frame,c,True,index=j)
        self._draw_all_player_labels()

    def _cancel_animation(self):
        for aid in self._anim_after_ids:
            try:self.after_cancel(aid)
            except tk.TclError:pass
        self._anim_after_ids.clear();self.animating=False

    def _animate_cards(self,sequence,callback):
        """Animate each card from the left edge of its own player/community zone.

        sequence items are (frame, card, target_index).  The back slides from x=-82
        into its fixed target, then flips face-up.  Player frames never resize.
        """
        self._cancel_animation();self.animating=True;self.action_btn.config(state=tk.DISABLED);self.render_market_rows()

        def deal_one(i=0):
            if self.destroyed:return
            if i>=len(sequence):
                aid=self.after(160,lambda:self._finish_animation(callback));self._anim_after_ids.append(aid);return
            frame,card,target_index=sequence[i]
            target_x=self._card_target_x(frame,target_index);start_x=-CARD_SIZE[0]
            lab=tk.Label(frame,image=self.back_image,bg=frame.cget('bg'),bd=0,highlightthickness=0)
            lab.image=self.back_image;lab.place(x=start_x,y=0,width=CARD_SIZE[0],height=CARD_SIZE[1])
            steps=9
            def slide(step=0):
                if self.destroyed or not lab.winfo_exists():return
                if step>=steps:
                    lab.place(x=target_x,y=0,width=CARD_SIZE[0],height=CARD_SIZE[1])
                    face=self.card_images[(card.suit,card.rank)];lab.config(image=face);lab.image=face
                    aid=self.after(95,lambda:deal_one(i+1));self._anim_after_ids.append(aid);return
                x=start_x+(target_x-start_x)*(step+1)/steps
                lab.place(x=int(x),y=0,width=CARD_SIZE[0],height=CARD_SIZE[1])
                aid=self.after(16,lambda:slide(step+1));self._anim_after_ids.append(aid)
            slide()
        deal_one()

    def _finish_animation(self,callback):
        self.animating=False;self._anim_after_ids.clear();self._draw_all_player_labels();self.render_market_rows()
        if callable(callback):callback()

    # ---------- markets ----------
    def set_markets(self, rows):
        self.market_rows=[];self.market_by_iid.clear()
        for row in rows:
            p=row['prob'];od=row.get('odds')
            if od is None:od=odds_from_probability(p)
            if od is None or p<=0:continue
            item=dict(row);item.setdefault('scope','full')
            if 'accordion_group' not in item:
                item['accordion_group']=item.get('market_label','项目')
            item['odds']=od;self.market_rows.append(item)
            key=(item.get('scope','full'),item['market'],str(item['selection']))
            hist=self.odds_history.setdefault(key,[])
            if not hist or abs(hist[-1]-od)>1e-9:hist.append(od)
        self.render_market_rows()

    def _h2h_rows(self,analysis,label='头VS头'):
        out=[]
        for i in range(5):
            eq=analysis['equity'][i];hit=analysis['hit'][i]
            od=h2h_odds(hit,eq)
            if od is None or eq<=0: continue  # draw dead omitted
            out.append({'market':'h2h','market_label':label,'selection':i,'selection_label':f'玩家{i+1}',
                        'prob':eq,'odds':od,'meta':{'hit':hit,'equity':eq}})
        return out

    def _winner_type_rows(self,probs):
        out=[]
        for key in HAND_MARKET_ORDER:
            p=probs.get(key,0)
            if p>0:
                out.append({'market':'winner_type','market_label':'赢家牌型','accordion_group':'赢家牌型',
                            'selection':key,'selection_label':HAND_KEY_TO_NAME[key],'prob':p})
        return out

    def _full_player_type_rows(self,probs_by_player):
        # Each player's own 2 hole + 5 community cards, independent of table result.
        if isinstance(probs_by_player,dict):
            probs_by_player=[dict(probs_by_player) for _ in range(5)]
        out=[]
        for pidx,probs in enumerate(probs_by_player):
            for key in HAND_MARKET_ORDER:
                p=probs.get(key,0)
                if p>0:
                    out.append({'market':'player_type','market_label':'独立牌型','accordion_group':'独立牌型',
                                'subaccordion_group':f'玩家{pidx+1}','selection':f'{pidx}:{key}',
                                'selection_label':HAND_KEY_TO_NAME[key],'prob':p,
                                'meta':{'player':pidx,'hand_type':key}})
        return out

    def _flop_pattern_rows(self, probs):
        labels=(
            ('pair','对子'),
            ('straight','顺子（包括同花顺）'),
            ('flush','同花（包括同花顺）'),
            ('trips','三条'),
            ('straight_flush','同花顺'),
        )
        return [
            {'scope':'half','market':'flop_pattern','market_label':'翻牌的3张',
             'accordion_group':'翻牌的3张','selection':key,
             'selection_label':label,'prob':probs.get(key,0.0)}
            for key,label in labels if probs.get(key,0.0)>0
        ]

    BOARD_RANK_PAIRING_LABELS = {
        # key 语义固定为：翻牌参与配对张数 _ 转牌+河牌参与配对张数。
        # 这样 UI 不会再出现不可能的“转牌3张”。
        '1_1': '翻1+转河1配对',
        '1_2': '翻1+转河2配对',
        '2_1': '翻2+转河1配对',
        '2_2': '翻2+转河2配对',
        '3_1': '翻3+转河1配对',
    }

    def _board_rank_pairing_rows(self, probs):
        rows=[]
        for key in ('1_1','1_2','2_1','2_2','3_1'):
            p=float(probs.get(key,0.0) or 0.0)
            if p>0:
                rows.append({
                    'market':'board_rank_pairing','market_label':'公牌配对',
                    'accordion_group':'转牌&翻河牌配对','selection':key,
                    'selection_label':self.BOARD_RANK_PAIRING_LABELS[key],'prob':p,
                    'meta':{'match_pattern':key}
                })
        return rows

    def _community_hand_type_rows(self, probs):
        rows=[]
        for key in HAND_MARKET_ORDER:
            p=float(probs.get(key,0.0) or 0.0)
            if p>0:
                rows.append({
                    'market':'community_hand_type','market_label':'公牌牌型',
                    'accordion_group':'公牌牌型','selection':key,
                    'selection_label':HAND_KEY_TO_NAME[key],'prob':p,
                    'meta':{'hand_type':key}
                })
        return rows

    def _turn_river_pair_row(self, p):
        return {'market':'turn_river_pair','market_label':'转牌和河牌的2张',
                'selection':'pair','selection_label':'对子','prob':p}

    def _half_h2h_rows(self,analysis):
        out=[]
        for i in range(5):
            eq=analysis['equity'][i];hit=analysis['hit'][i]
            od=h2h_odds(hit,eq)
            if od is None or eq<=0:continue
            out.append({
                'scope':'half','market':'half_h2h','market_label':'半场头VS头',
                'accordion_group':'半场头VS头','selection':i,'selection_label':f'玩家{i+1}',
                'prob':eq,'odds':od,'meta':{'hit':hit,'equity':eq}
            })
        return out

    def _half_winner_type_rows(self,probs):
        out=[]
        for key in HAND_MARKET_ORDER:
            p=probs.get(key,0)
            if p>0:
                out.append({'scope':'half','market':'half_winner_type','market_label':'赢家牌型',
                            'accordion_group':'赢家牌型','selection':key,
                            'selection_label':HAND_KEY_TO_NAME[key],'prob':p})
        return out

    def _half_player_type_rows(self,probs_by_player):
        # Each player's own 2 hole + 3-card flop, independent of who wins half-time.
        if isinstance(probs_by_player,dict):
            probs_by_player=[dict(probs_by_player) for _ in range(5)]
        out=[]
        for pidx,probs in enumerate(probs_by_player):
            for key in HAND_MARKET_ORDER:
                p=probs.get(key,0)
                if p>0:
                    out.append({'scope':'half','market':'half_player_type','market_label':'独立牌型',
                                'accordion_group':'独立牌型','subaccordion_group':f'玩家{pidx+1}',
                                'selection':f'{pidx}:{key}','selection_label':HAND_KEY_TO_NAME[key],'prob':p,
                                'meta':{'player':pidx,'hand_type':key}})
        return out

    def _half_full_rows(self,probs_by_player):
        labels=(('WW','半赢 / 全赢'),('WL','半赢 / 全输'),('LW','半输 / 全赢'),('LL','半输 / 全输'))
        rows=[]
        for pidx in range(5):
            probs=probs_by_player[pidx]
            for code,label in labels:
                p=probs.get(code,0.0)
                if p<=0:continue
                rows.append({
                    'scope':'half','market':'half_full','market_label':'半全场',
                    'accordion_group':f'玩家{pidx+1} · 半全场',
                    'selection':f'{pidx}:{code}','selection_label':label,'prob':p,
                    'meta':{'player':pidx,'half_full_code':code}
                })
        return rows

    def _specified_hand_rows(self, result_probs, *, predeal=False):
        rows=[]
        for hand in ('AA','AK','27','22'):
            probs=result_probs.get(hand,{})
            for outcome,label in (('win','获胜'),('lose','获败')):
                p=float(probs.get(outcome,0.0) or 0.0)
                if p<=0:
                    continue
                # Promotional exception requested by the rules: Stage1 only,
                # 手牌27并且获胜 is priced to 105% RTP.
                if predeal and hand=='27' and outcome=='win':
                    od=odds_from_probability(p,edge=-0.05)
                else:
                    od=odds_from_probability(p)
                rows.append({
                    'market':'specified_hand_result',
                    'market_label':'指定手牌获胜/败',
                    'accordion_group':'指定手牌获胜/败',
                    'selection':f'{hand}:{outcome}',
                    'selection_label':f'手牌{hand} · {label}',
                    'prob':p,'odds':od,
                    'meta':{'hand_code':hand,'outcome':outcome,'predeal':bool(predeal),
                            'rtp':1.05 if predeal and hand=='27' and outcome=='win' else 1.0-HOUSE_EDGE}
                })
        return rows

    def predeal_half_markets(self):
        rows=[]
        # Pre-deal symmetry: each player's equity is exactly 20%.
        for i in range(5):
            rows.append({
                'scope':'half','market':'half_h2h','market_label':'半场头VS头',
                'accordion_group':'半场头VS头','selection':i,'selection_label':f'玩家{i+1}',
                'prob':0.2,'odds':odds_from_probability(0.2),'meta':{'predeal':True}
            })
        rows+=self._half_winner_type_rows(PREDEAL_HALF_WINNER_TYPE_PROBS)
        rows+=self._half_player_type_rows([dict(PREDEAL_HALF_PLAYER_TYPE_PROBS) for _ in range(5)])
        rows+=self._half_full_rows([dict(PREDEAL_HALF_FULL_PROBS) for _ in range(5)])
        return rows

    def predeal_markets(self):
        rows=[]
        for i in range(5):
            rows.append({'market':'h2h','market_label':'头VS头','selection':i,'selection_label':f'玩家{i+1}',
                         'prob':0.2,'odds':odds_from_probability(0.2),'meta':{'predeal':True}})
        rows += self._winner_type_rows(PREDEAL_WINNER_TYPE_PROBS)
        rows += self._full_player_type_rows([dict(PREDEAL_FULL_PLAYER_TYPE_PROBS) for _ in range(5)])
        for key,label in [('community_same_color_yes','是'),('community_same_color_no','否')]:
            rows.append({'market':'community_same_color','market_label':'公共牌同一颜色','selection':key.endswith('yes'),'selection_label':label,'prob':PREDEAL_PUBLIC_PROBS[key]})
        for key,label,k in [('community_ge3_suits','至少3种','ge3'),('community_ge4_suits','至少4种','ge4')]:
            rows.append({'market':'community_suit_diversity','market_label':'公共牌不同花色','selection':k,'selection_label':label,'prob':PREDEAL_PUBLIC_PROBS[key]})
        rows += self._flop_pattern_rows(PREDEAL_FLOP_PROBS)
        rows.append(self._turn_river_pair_row(PREDEAL_TURN_RIVER_PAIR_PROB))
        # Stage 1 only: new full-game public-card markets are appended at the bottom.
        rows += self._board_rank_pairing_rows(PREDEAL_FLOP_LATER_RANK_MATCH_PROBS)
        rows += self._community_hand_type_rows(PREDEAL_COMMUNITY_HAND_TYPE_PROBS)

        for key,label,k in [('hole_ge3_suited','至少3家','ge3'),('hole_ge4_suited','至少4家','ge4'),('hole_ge5_suited','5家','ge5')]:
            rows.append({'market':'hole_suited_count','market_label':'玩家手牌同花家数','selection':k,'selection_label':label,'prob':PREDEAL_SUITED_PROBS[key]})
        for key,label,k in [('hole_pair_ge1','最少1家','ge1'),('hole_pair_ge2','最少2家','ge2'),('hole_pair_ge3','最少3家','ge3')]:
            rows.append({'market':'hole_pair_count','market_label':'玩家手牌是对子','selection':k,'selection_label':label,'prob':PREDEAL_HOLE_PAIR_PROBS[key]})
        for key,label,k in [('hole_rank_match_ge2','最少2家','ge2'),('hole_rank_match_ge3','最少3家','ge3')]:
            rows.append({'market':'hole_rank_pattern_match','market_label':'玩家手牌点数组合相同','selection':k,'selection_label':label,'prob':PREDEAL_HOLE_RANK_MATCH_PROBS[key]})
        rows += self._specified_hand_rows(PREDEAL_SPECIFIED_RESULT_PROBS,predeal=True)
        return rows+self.predeal_half_markets()

    def hole_markets_from_analysis(self,a,flop_probs,turn_river_pair_prob,rank_pair_probs,half,half_full):
        rows=self._h2h_rows(a)+self._winner_type_rows(a['winner_types'])+self._full_player_type_rows(a['player_types'])
        for sel,label,key in [(True,'是','community_same_color_yes'),(False,'否','community_same_color_no')]:
            rows.append({'market':'community_same_color','market_label':'公共牌同一颜色','selection':sel,'selection_label':label,'prob':a[key]})
        rows += [
            {'market':'community_suit_diversity','market_label':'公共牌不同花色','selection':'ge3','selection_label':'至少3种','prob':a['community_ge3_suits']},
            {'market':'community_suit_diversity','market_label':'公共牌不同花色','selection':'ge4','selection_label':'至少4种','prob':a['community_ge4_suits']},
        ]
        rows += self._flop_pattern_rows(flop_probs)
        rows.append(self._turn_river_pair_row(turn_river_pair_prob))
        # Stage 2 only: these two groups are not offered once the Flop is exposed.
        rows += self._board_rank_pairing_rows(rank_pair_probs)
        rows += self._community_hand_type_rows(a.get('community_hand_types',{}))
        rows += self._half_h2h_rows(half)
        rows += self._half_winner_type_rows(half['winner_types'])
        rows += self._half_player_type_rows(half['player_types'])
        rows += self._half_full_rows(half_full)
        rows += self._specified_hand_rows(a.get('specified_hand_results',{}),predeal=False)
        return rows

    def flop_markets_from_analysis(self,a,special,turn_river_pair_prob):
        rows=self._h2h_rows(a)+self._winner_type_rows(a['winner_types'])+self._full_player_type_rows(a['player_types'])
        rows += [
            {'market':'remaining_suit_relation','market_label':'剩余2张公共牌','selection':'same','selection_label':'同一花色','prob':a['remaining_same_suit']},
            {'market':'remaining_suit_relation','market_label':'剩余2张公共牌','selection':'different','selection_label':'不同花色','prob':a['remaining_diff_suit']},
            self._turn_river_pair_row(turn_river_pair_prob),
        ]
        top=sorted(range(5),key=lambda i:a['equity'][i],reverse=True)[:2]
        for j,pidx in enumerate(top):
            eq=special['equity'][j];hit=special['hit'][j];od=h2h_odds(hit,eq)
            if eq>0 and od is not None:
                rows.append({'market':'special_duel','market_label':f'特殊对决 P{top[0]+1} vs P{top[1]+1}',
                             'selection':pidx,'selection_label':f'玩家{pidx+1}','prob':eq,'odds':od,
                             'meta':{'duel_players':top,'equity':eq,'hit':hit}})
        return rows

    def buy_selected(self):
        # Legacy compatibility: purchases now happen by clicking the fixed-odds button.
        return

    def refresh_ticket_text(self,settlement=None):
        if self.current_scope=='purchase': self.render_market_rows()

    # ---------- game flow ----------
    def _cancel_auto_reset(self):
        timer=getattr(self,'auto_reset_timer',None)
        if timer:
            try:self.after_cancel(timer)
            except tk.TclError:pass
            self.auto_reset_timer=None

    def _schedule_auto_reset(self):
        self._cancel_auto_reset()
        if self.stage=='settled' and not self.destroyed:
            self.auto_reset_timer=self.after(30000,self._auto_press_new_round)

    def _auto_press_new_round(self):
        self.auto_reset_timer=None
        if self.stage=='settled' and not self.destroyed:
            # Behave exactly like a left-click on the 再来一局 action button.
            self.advance_stage()

    def show_card_sequence(self, event=None):
        """右键显示本局牌序：730x750内完整显示52张牌，每行9张，共6行。"""

        if self.stage != 'settled':
            return 'break'

        # 取消30秒自动再来一局
        if self.auto_reset_timer:
            try:
                self.after_cancel(self.auto_reset_timer)
            except tk.TclError:
                pass
            self.auto_reset_timer = None

        if not hasattr(self, 'deck') or self.deck is None:
            messagebox.showinfo("提示", "没有牌序信息")
            return 'break'

        if not hasattr(self.deck, 'full_deck') or not self.deck.full_deck:
            messagebox.showinfo("提示", "没有牌序信息")
            return 'break'

        # ---------------------------------------------------------
        # 窗口
        # ---------------------------------------------------------
        win = tk.Toplevel(self)
        win.title("本局牌序")
        win.geometry("730x750")
        win.resizable(False, False)
        win.configure(bg='#f0f0f0')

        cut_pos = int(
            getattr(
                self.deck,
                'start_pos',
                getattr(self.deck, 'cut_position', 0)
            )
        )

        # 标题尽量压缩高度
        tk.Label(
            win,
            text=f"本局切牌位置: {cut_pos + 1}",
            font=('Arial', 13, 'bold'),
            bg='#f0f0f0'
        ).pack(pady=(5, 2))

        # ---------------------------------------------------------
        # 主牌区
        # 不需要Scrollbar
        # ---------------------------------------------------------
        main_frame = tk.Frame(
            win,
            bg='#f0f0f0'
        )
        main_frame.pack(
            fill=tk.BOTH,
            expand=True,
            padx=5,
            pady=(0, 3)
        )

        card_frame = tk.Frame(
            main_frame,
            bg='#f0f0f0'
        )
        card_frame.pack(
            fill=tk.BOTH,
            expand=True,
            padx=3,
            pady=0
        )

        # ---------------------------------------------------------
        # 保持60×90
        # ---------------------------------------------------------
        small_size = (60, 90)
        small_images = {}

        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.LANCZOS

        # ---------------------------------------------------------
        # 生成小牌图片
        # ---------------------------------------------------------
        for i, card in enumerate(self.deck.full_deck):

            key = (card.suit, card.rank)

            if key in self.original_images:
                try:
                    orig = self.original_images[key]

                    small = orig.resize(
                        small_size,
                        resample
                    )

                    small_images[i] = ImageTk.PhotoImage(
                        small,
                        master=win
                    )

                except Exception:
                    pass

            # 没有图片时使用备用牌面
            if i not in small_images:

                img = Image.new(
                    'RGB',
                    small_size,
                    'blue'
                )

                draw = ImageDraw.Draw(img)

                try:
                    font = ImageFont.truetype(
                        "arial.ttf",
                        11
                    )
                except Exception:
                    font = ImageFont.load_default()

                text = f"{card.rank}{card.suit}"

                try:
                    bbox = draw.textbbox(
                        (0, 0),
                        text,
                        font=font
                    )

                    tw = bbox[2] - bbox[0]
                    th = bbox[3] - bbox[1]

                except Exception:
                    tw = 30
                    th = 12

                draw.text(
                    (
                        (small_size[0] - tw) // 2,
                        (small_size[1] - th) // 2
                    ),
                    text,
                    fill="white",
                    font=font
                )

                small_images[i] = ImageTk.PhotoImage(
                    img,
                    master=win
                )

        # 防止图片被回收
        win.small_card_images = small_images

        # ---------------------------------------------------------
        # 52张
        #
        # 第1行  1-9
        # 第2行 10-18
        # 第3行 19-27
        # 第4行 28-36
        # 第5行 37-45
        # 第6行 46-52
        # ---------------------------------------------------------
        cards_per_row = 9
        total_rows = 6
        card_sequence = self.deck.full_deck

        # 六行平均分配高度
        for row in range(total_rows):
            card_frame.rowconfigure(row, weight=1)

        # 九列平均分配宽度
        for col in range(cards_per_row):
            card_frame.columnconfigure(
                col,
                weight=1,
                uniform='deck_columns'
            )

        for row in range(total_rows):

            start_index = row * cards_per_row

            cards_this_row = min(
                cards_per_row,
                len(card_sequence) - start_index
            )

            if cards_this_row <= 0:
                break

            for col in range(cards_this_row):

                card_index = start_index + col

                is_cut = (card_index == cut_pos)

                bg_color = (
                    '#ADD8E6'
                    if is_cut
                    else '#f0f0f0'
                )

                card_container = tk.Frame(
                    card_frame,
                    bg=bg_color
                )

                card_container.grid(
                    row=row,
                    column=col,
                    padx=2,
                    pady=1
                )

                # -------------------------
                # 扑克牌
                # -------------------------
                card_label = tk.Label(
                    card_container,
                    image=small_images[card_index],
                    bg=bg_color,
                    borderwidth=2 if is_cut else 1,
                    relief='solid'
                )

                card_label.image = small_images[card_index]
                card_label.pack()

                # -------------------------
                # 牌序号码
                # -------------------------
                tk.Label(
                    card_container,
                    text=str(card_index + 1),
                    bg=bg_color,
                    fg='black',
                    font=(
                        'Arial',
                        8,
                        'bold' if is_cut else 'normal'
                    ),
                    pady=0
                ).pack(
                    fill=tk.X,
                    pady=0
                )

        return 'break'

    def new_round(self):
        self._cancel_auto_reset()
        self._cancel_animation();self.deck=Deck();self.holes=[[] for _ in range(5)];self.board=[];self.burns=[];self.stage='predeal';self.tickets=[]
        # History and purchase records belong to one round only; pressing 再来一局 starts
        # a fresh round and removes every previous ticket/detail entry.
        self.odds_history={};self.accordion_state={};self.ticket_detail_state={}
        self.current_scope='full';self.current_market_tab='h2h'
        self._rebuild_scope_tabs();self._rebuild_category_tabs()
        self.calculating=False;self.sales_open=True;self.render_cards();self.set_markets(self.predeal_markets())
        self.status.config(text='阶段1：5家手牌派出前');self.stage_label.config(text='阶段1')
        self.action_btn.config(text='停止售票 · 玩家发张',state=tk.NORMAL)

    def _deal_holes(self):
        for _round in range(2):
            for p in range(5):self.holes[p].extend(self.deck.deal(1))

    def _close_sales_for_transition(self):
        self.sales_open=False
        self.render_market_rows()

    def advance_stage(self):
        if self.calculating or self.animating:return
        if self.stage=='predeal':
            self._close_sales_for_transition()
            self._deal_holes();self.stage='holes';self._clear_cards()
            seq=[]
            for round_i in range(2):
                for p in range(5):seq.append((self.player_card_frames[p],self.holes[p][round_i],round_i))
            self.status.config(text='阶段1已停止售票。庄家正在明牌派出5家手牌…');self.stage_label.config(text='阶段1 · 派牌中')
            self._animate_cards(seq,self._after_hole_animation)
        elif self.stage=='holes':
            self._close_sales_for_transition()
            self.burns.extend(self.deck.deal(1));new_flop=self.deck.deal(3);self.board.extend(new_flop);self.stage='flop'
            self._rebuild_scope_tabs();self._rebuild_category_tabs()
            # Keep all five hands fixed; only clear the community zone for its animation.
            for w in self.board_frame.winfo_children():w.destroy()
            self.status.config(text='阶段2已停止售票。庄家烧1张牌，正在明牌派3张公共牌…');self.stage_label.config(text='阶段2 · 开牌中')
            self._animate_cards([(self.board_frame,c,i) for i,c in enumerate(new_flop)],self._after_flop_animation)
        elif self.stage=='flop':
            self._close_sales_for_transition()
            self.burns.extend(self.deck.deal(1));turn=self.deck.deal(1)[0];self.board.append(turn)
            self.burns.extend(self.deck.deal(1));river=self.deck.deal(1)[0];self.board.append(river);self.stage='settled'
            self._rebuild_scope_tabs();self._rebuild_category_tabs()
            self.status.config(text='阶段3已停止售票。庄家烧牌后明牌派 Turn，再烧牌后明牌派 River…');self.stage_label.config(text='阶段3 · 最终开牌')
            self._animate_cards([(self.board_frame,turn,3),(self.board_frame,river,4)],self._after_final_animation)
        elif self.stage=='settled':self.new_round()

    def _after_hole_animation(self):
        self._settle_known_tickets('holes')
        self.status.config(text='阶段2资料计算中：精确计算所有 C(42,5) 种公共牌…');self.stage_label.config(text='阶段2 · 计算中');self._calculate_hole_stage()

    def _after_flop_animation(self):
        self._settle_known_tickets('flop')
        self.status.config(text='阶段3资料计算中：精确计算剩余公共牌…');self.stage_label.config(text='阶段3 · 计算中');self._calculate_flop_stage()

    def _after_final_animation(self):
        self.sales_open=False;self.set_markets([]);self.settle_tickets()

    def _run_worker(self,func,done):
        self.calculating=True;self.action_btn.config(state=tk.DISABLED);self.buy_btn.config(state=tk.DISABLED)
        def work():
            try:r=func();self.after(0,lambda:done(r))
            except Exception as e:self.after(0,lambda:messagebox.showerror('计算错误',str(e)))
            finally:self.after(0,self._worker_finished)
        threading.Thread(target=work,daemon=True).start()
    def _worker_finished(self):
        self.calculating=False
        if self.stage!='settled':self.action_btn.config(state=tk.NORMAL);self.buy_btn.config(state=tk.NORMAL)
        self.render_market_rows()

    def _calculate_hole_stage(self):
        holes=[list(h) for h in self.holes];remaining=list(self.deck.remaining())
        def calc():
            a,half,half_full=analyze_hole_stage_exact(holes,remaining)
            flop_probs=exact_flop_three_probs(remaining)
            tr_pair=exact_two_card_rank_pair_prob(remaining)
            rank_pair_probs=exact_flop_later_rank_match_probs(remaining)
            return a,flop_probs,tr_pair,rank_pair_probs,half,half_full
        def done(res):
            a,flop_probs,tr_pair,rank_pair_probs,half,half_full=res
            self.sales_open=True
            self.set_markets(self.hole_markets_from_analysis(a,flop_probs,tr_pair,rank_pair_probs,half,half_full))
            self.status.config(text=f"阶段2：10张手牌已知；全场 C(42,5) + 半场 C(42,3) + 半全场精确组合已完成")
            self.stage_label.config(text='阶段2');self.action_btn.config(text='停止售票 · 翻牌三张')
        self._run_worker(calc,done)

    def _calculate_flop_stage(self):
        holes=[list(h) for h in self.holes];board=list(self.board);remaining=list(self.deck.remaining())
        def calc():
            a=analyze_future_boards(holes,board,remaining)
            top=sorted(range(5),key=lambda i:a['equity'][i],reverse=True)[:2]
            sp=analyze_special_duel(holes[top[0]],holes[top[1]],board,remaining)
            tr_pair=exact_two_card_rank_pair_prob(remaining)
            return a,sp,top,tr_pair
        def done(res):
            a,sp,top,tr_pair=res
            self._settle_draw_dead_tickets(a)
            self._rebuild_scope_tabs();self._rebuild_category_tabs()
            self.sales_open=True;self.set_markets(self.flop_markets_from_analysis(a,sp,tr_pair));self.status.config(text=f"阶段3：已知14张牌；精确枚举 {a['total']:,} 种 Turn/River，特殊对决=P{top[0]+1} vs P{top[1]+1}")
            self.stage_label.config(text='阶段3');self.action_btn.config(text='停止售票 · 转牌河牌两张')
        self._run_worker(calc,done)

    # ---------- settlement ----------
    def _global_result(self):
        vals=[hand_key7(h+self.board) for h in self.holes];best=max(vals);wins=[i for i,v in enumerate(vals) if v==best]
        return vals,best,wins

    def _hole_rank_pattern_max_count(self):
        pats=[]
        for h in self.holes:
            pats.append(tuple(sorted((h[0].value,h[1].value))))
        return max(Counter(pats).values()) if pats else 0

    def _half_result(self):
        if len(self.board)<3:
            return [],None,[]
        vals=[hand_key7(h+self.board[:3]) for h in self.holes]
        best=max(vals);winners=[i for i,v in enumerate(vals) if v==best]
        return vals,best,winners

    def _board_rank_match_pattern(self):
        """Return the final-board Flop-vs-Turn/River rank-overlap key."""
        if len(self.board)<5:
            return None
        flop=self.board[:3]
        later=self.board[3:5]
        flop_values=[c.value for c in flop]
        later_values=[c.value for c in later]
        flop_set=set(flop_values)
        later_set=set(later_values)
        flop_matched=sum(1 for value in flop_values if value in later_set)
        later_matched=sum(1 for value in later_values if value in flop_set)
        return {(1,1):'1_1',(1,2):'1_2',(2,1):'2_1',(2,2):'2_2',(3,1):'3_1'}.get(
            (flop_matched,later_matched)
        )

    @staticmethod
    def _tie_wildcard_leg_matches(player,winners,desired):
        """For half/full only: a tied-best player satisfies either W or L."""
        in_winners=player in winners
        tied=in_winners and len(winners)>1
        if tied:return True
        return in_winners if desired=='W' else not in_winners

    def ticket_is_win(self,t,vals,best,winners):
        if t.market=='half_h2h':
            _hv,_hb,hw=self._half_result();p=int(t.selection)
            if p in hw:return True,len(hw)
            return False,1
        if t.market=='half_player_type':
            if len(self.board)<3:return False,1
            meta=t.meta or {}; p=int(meta.get('player',0)); wanted=str(meta.get('hand_type',''))
            value=hand_key7(self.holes[p] + self.board[:3])
            return wanted in hand_market_keys(value),1
        if t.market=='half_winner_type':
            _hv,hb,_hw=self._half_result()
            return bool(hb is not None and t.selection in hand_market_keys(hb)),1
        if t.market=='half_full':
            meta=t.meta or {};p=int(meta.get('player',0));code=str(meta.get('half_full_code',''))
            if len(code)!=2:return False,1
            _hv,_hb,hw=self._half_result()
            half_ok=self._tie_wildcard_leg_matches(p,hw,code[0])
            full_ok=self._tie_wildcard_leg_matches(p,winners,code[1])
            return half_ok and full_ok,1
        if t.market=='h2h':
            p=t.selection
            if p in winners:return True,len(winners)
            return False,1
        if t.market=='player_type':
            meta=t.meta or {}; p=int(meta.get('player',0)); wanted=str(meta.get('hand_type',''))
            value=hand_key7(self.holes[p]+self.board)
            return wanted in hand_market_keys(value),1
        if t.market=='winner_type':return t.selection in hand_market_keys(best),1
        if t.market=='community_same_color':return same_color(self.board)==t.selection,1
        if t.market=='community_suit_diversity':
            d=suit_diversity(self.board);return (d>=3 if t.selection=='ge3' else d>=4),1
        if t.market=='hole_suited_count':
            n=sum(1 for h in self.holes if h[0].suit_i==h[1].suit_i)
            threshold={'ge3':3,'ge4':4,'ge5':5}[t.selection];return n>=threshold,1
        if t.market=='hole_pair_count':
            n=sum(1 for h in self.holes if h[0].value==h[1].value)
            threshold={'ge1':1,'ge2':2,'ge3':3}[t.selection];return n>=threshold,1
        if t.market=='hole_rank_pattern_match':
            threshold={'ge2':2,'ge3':3}[t.selection]
            return self._hole_rank_pattern_max_count()>=threshold,1
        if t.market=='specified_hand_result':
            meta=t.meta or {};code=str(meta.get('hand_code',''));outcome=str(meta.get('outcome',''))
            holders=specified_holders(self.holes,code) if code in SPECIFIED_HOLE_PATTERNS else []
            if not holders:
                return False,1
            winner_set=set(winners)
            if outcome=='win':
                return any(i in winner_set for i in holders),1
            if outcome=='lose':
                return any(i not in winner_set for i in holders),1
            return False,1
        if t.market=='flop_pattern':
            flags=flop_three_flags(self.board[:3]);return bool(flags.get(t.selection,False)),1
        if t.market=='turn_river_pair':
            return len(self.board)>=5 and self.board[3].value==self.board[4].value,1
        if t.market=='board_rank_pairing':
            return self._board_rank_match_pattern()==t.selection,1
        if t.market=='community_hand_type':
            if len(self.board)<5:return False,1
            value=hand_key7(self.board)
            return t.selection in hand_market_keys(value),1
        if t.market=='remaining_suit_relation':
            same=self.board[3].suit_i==self.board[4].suit_i;return same==(t.selection=='same'),1
        if t.market=='special_duel':
            pair=t.meta.get('duel_players',[])
            if len(pair)!=2:return False,1
            a,b=pair;va=vals[a];vb=vals[b]
            if va==vb:return t.selection in pair,2
            winner=a if va>vb else b
            return t.selection==winner,1
        return False,1

    def _apply_ticket_result(self,t,won,split=1):
        if t.settled:
            return 0.0
        t.settled=True;t.won=bool(won);t.split=max(1,int(split))
        if won:
            profit=t.amount*(t.odds/t.split)
            ret=t.amount+profit
            t.return_amount=ret
            t.result_text='中奖' + (f'（平分/{t.split}）' if t.split>1 else '')
            return ret
        t.return_amount=0.0;t.result_text='未中奖'
        return 0.0

    def _credit_returns(self,amount):
        if amount>0:
            self.balance=round(self.balance+amount,2)
            self.update_balance()
        if self.current_scope=='purchase':
            self.render_market_rows()

    def _settle_known_tickets(self,checkpoint):
        """Settle props as soon as their result is objectively known on the table."""
        total_return=0.0
        for t in self.tickets:
            if t.settled:
                continue
            known=False; won=False; split=1
            if checkpoint in ('holes','flop') and t.market in ('hole_suited_count','hole_pair_count','hole_rank_pattern_match'):
                vals=[hand_key7(h + self.board) if len(self.board)>=5 else None for h in self.holes]
                # ticket_is_win only needs holes for these markets; dummy final args are safe.
                won,split=self.ticket_is_win(t,vals,(0,),[]);known=True
            elif checkpoint in ('holes','flop') and t.market=='specified_hand_result':
                meta=t.meta or {};code=str(meta.get('hand_code',''))
                # If the ten exposed hole cards contain no requested starting hand,
                # every Stage1 ticket for that hand is immediately dead.
                if code in SPECIFIED_HOLE_PATTERNS and not specified_holders(self.holes,code):
                    won=False;split=1;known=True
            elif checkpoint=='flop' and t.market in ('half_h2h','half_winner_type','half_player_type'):
                won,split=self.ticket_is_win(t,[],(0,),[]);known=True
            elif checkpoint=='flop' and t.market=='half_full':
                meta=t.meta or {};p=int(meta.get('player',0));code=str(meta.get('half_full_code',''))
                if len(code)==2:
                    _hv,_hb,hw=self._half_result()
                    if not self._tie_wildcard_leg_matches(p,hw,code[0]):
                        won=False;split=1;known=True
            elif checkpoint=='flop' and t.market=='flop_pattern':
                won,split=self.ticket_is_win(t,[],(0,),[]);known=True
            elif checkpoint=='flop' and t.market=='community_same_color':
                colors={0 if c.suit in ('♥','♦') else 1 for c in self.board}
                if len(colors)>1:
                    won=(t.selection is False);known=True
            elif checkpoint=='flop' and t.market=='community_suit_diversity':
                threshold=3 if t.selection=='ge3' else 4
                d=suit_diversity(self.board)
                if d>=threshold:
                    won=True;known=True
                elif min(4,d+(5-len(self.board)))<threshold:
                    won=False;known=True
            if known:
                total_return += self._apply_ticket_result(t,won,split)
        self._credit_returns(total_return)
        if total_return>0:
            self.status.config(text=f'已有彩卷完成结算，本阶段即时返还 {money(total_return)}')

    def _settle_draw_dead_tickets(self,analysis):
        """After the flop exact enumeration, immediately settle mathematically dead bets."""
        total_return=0.0
        winner_probs=analysis.get('winner_types',{})
        player_probs=analysis.get('player_types',[])
        for t in self.tickets:
            if t.settled:
                continue
            if t.market=='h2h' and analysis['hit'][int(t.selection)]<=0.0:
                total_return += self._apply_ticket_result(t,False,1)
            elif t.market=='winner_type' and winner_probs.get(t.selection,0.0)<=0.0:
                total_return += self._apply_ticket_result(t,False,1)
            elif t.market=='player_type':
                meta=t.meta or {};p=int(meta.get('player',0));wanted=str(meta.get('hand_type',''))
                if 0<=p<len(player_probs) and player_probs[p].get(wanted,0.0)<=0.0:
                    total_return += self._apply_ticket_result(t,False,1)
            elif t.market=='specified_hand_result':
                meta=t.meta or {};code=str(meta.get('hand_code',''));outcome=str(meta.get('outcome',''))
                p=analysis.get('specified_hand_results',{}).get(code,{}).get(outcome,0.0)
                if p<=0.0:
                    total_return += self._apply_ticket_result(t,False,1)
        self._credit_returns(total_return)

    def settle_tickets(self):
        self.sales_open=False
        vals,best,winners=self._global_result();new_return=0.0
        for t in self.tickets:
            if t.settled:
                continue
            won,split=self.ticket_is_win(t,vals,best,winners)
            new_return += self._apply_ticket_result(t,won,split)
        self._credit_returns(new_return)
        total_return=sum(t.return_amount for t in self.tickets)
        winner_text='/'.join(f'玩家{i+1}' for i in winners)
        self.status.config(text=f"结算完成：{winner_text} · {hand_display_name(best)}；本局彩卷累计返还 {money(total_return)}")
        # Keep the completed round's purchase records visible through settlement.
        # They are deleted only when the player explicitly presses “再来一局”,
        # where new_round() clears tickets/detail state for the fresh round.
        self.stage_label.config(text='结算完成');self.action_btn.config(text='再来一局',state=tk.NORMAL);self.render_cards();self.render_market_rows()
        self.buy_btn.config(state=tk.DISABLED)
        self._schedule_auto_reset()
        self.status.config(text=self.status.cget('text')+'；30秒后自动再来一局，右键“再来一局”可查看牌靴记录并取消自动重开')

    def show_rules(self):
        # Caribbean-style scrollable instruction window adapted to 德州彩卷.
        win=tk.Toplevel(self)
        win.title('五人德州扑克对决 游戏规则')
        win.geometry('800x700')
        win.resizable(False,False)
        win.configure(bg='#F0F0F0')

        main_frame=tk.Frame(win,bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH,expand=True,padx=10,pady=10)
        scrollbar=ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT,fill=tk.Y)
        canvas=tk.Canvas(main_frame,bg='#F0F0F0',highlightthickness=0,yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
        scrollbar.config(command=canvas.yview)
        content_frame=tk.Frame(canvas,bg='#F0F0F0')
        canvas_window=canvas.create_window((0,0),window=content_frame,anchor='nw')

        tk.Label(content_frame,text='五人德州扑克对决 游戏规则',
                 font=('微软雅黑',15,'bold'),bg='#F0F0F0',fg='#1B3D31',pady=8).pack(fill=tk.X,padx=10)

        rules_text=f'''
1. 游戏基本规则

   - 本游戏固定为5名自动玩家，每名玩家有2张手牌，共用5张公共牌。
   - 全场按标准德州扑克规则，从玩家2张手牌与5张公共牌共7张牌中选出最佳5张。
   - 半场只使用玩家2张手牌 + Flop 3张公共牌，共5张牌直接比较。
   - 玩家购买的是“德州彩卷”；每张彩卷在购买时锁定当时固定赔率。
   - 没有下注倒计时，由玩家自行按“停止售票”进入下一阶段。

2. 三个售票阶段

   阶段1 — 玩家手牌派出前
   - 所有玩家手牌与公共牌仍未知，可购买全场、半场及阶段1开放项目。
   - 按“停止售票 · 玩家发张”后，庄家明牌派出5家各2张手牌。

   阶段2 — 10张玩家手牌全部明牌后
   - 系统依据已知10张牌重新计算动态赔率。
   - 全场精确枚举剩余5张公共牌组合；半场精确枚举所有可能Flop。
   - 按“停止售票 · 翻牌三张”后，烧1张牌，再明牌派出3张Flop。

   阶段3 — Flop 3张公开后
   - 半场已经确定，因此只开放全场与购买记录。
   - 系统精确枚举剩余 翻牌/和牌 组合并更新全场赔率。
   - 按“停止售票 · 转牌河牌两张”后：烧1张→Turn；再烧1张→River；随后结算。

3. 全场彩卷

   头VS头
   - 购买某一玩家成为真实5人局最终赢家。
   - 若多人平分底池，买到任一平分赢家均中奖；利润赔率按平分人数除分。

   牌型
   - 赢家牌型：购买最终获胜玩家/并列赢家所使用的最终牌型。
   - 独立牌型：先选择玩家1~5，再购买该玩家自己的2张手牌 + 5张公牌所形成的最佳5张牌型。
   - 独立牌型只看指定玩家自己的牌型，与该玩家是否赢得全场无关。

   公牌
   - 包含公共牌颜色、花色数量、Turn/River关系等当阶段开放项目。
   - 阶段1、阶段2额外开放“转牌&翻河牌配对”与“公牌牌型”；公牌牌型只使用5张公共牌判断。

   特别事项
   - 阶段1、阶段2提供“指定手牌获胜/败”：AA、AK、27、22。
   - 阶段1“任一家27并且获胜”采用105% RTP特别定价；阶段2恢复一般赌场优势。
   - 包含玩家手牌对子数量、相同点数组合、特殊两家对决等当阶段开放项目。

4. 半场彩卷（仅阶段1与阶段2）

   头VS头
   - 只比较每家2张手牌 + Flop 3张，共5张牌。

   牌型
   - 赢家牌型：购买半场最佳玩家/并列最佳玩家的5张牌牌型。
   - 独立牌型：先选择玩家1~5，再购买该玩家自己的2张手牌 + Flop 3张所形成的5张牌牌型。

   公牌
   - “公牌”分页位于“牌型”和“半全场”之间。
   - 原全场“翻牌的3张”项目完整移到这里，并在Flop公开后结算。

   半全场
   - 每家可购买：半赢/全赢、半赢/全输、半输/全赢、半输/全输。
   - 若某阶段出现平局，该玩家在该阶段同时视为“赢”与“输”条件成立。
   - 半全场平局命中不会按平局人数除分。

5. 固定赔率、购买与返还

   - 除阶段1“手牌27 · 胜”采用105% RTP特别定价外，其余动态赔率按赌场优势 {HOUSE_EDGE*100:.1f}% 定价。
   - 普通项目利润赔率由当前概率换算，画面显示为“固定赔率:1”。
   - 使用右侧筹码选择购买金额，再点击对应固定赔率按钮购买。
   - 购买成功后赔率永久锁定；后续赔率变化只影响新购买的彩卷。
   - 普通中奖返还 = 下注金额 + 下注金额 × 固定利润赔率。
   - 购买记录显示内容、金额、赔率、预计/已返还；点击记录可展开完整资料。

6. 动态概率与即时结算

   - 阶段2与阶段3动态赔率使用确定性组合枚举，不以Monte Carlo模拟次数估算。
   - 阶段1完全未知时，对称/单人牌型等项目使用精确对称或组合概率；部分5人赢家联合分布使用程序内固定基准表。
   - 当某张彩卷在River前已经客观确定结果，会立即结算并把返还加入余额。
   - 尚未提前结算的彩卷在River完成后统一结算。
   - 一局结束后按“再来一局”开始新局；上一局购买记录不会带入新局。

7. 标准德州牌型（由高至低）

   皇家同花顺 → 同花顺 → 四条 → 葫芦 → 同花 → 顺子 → 三条 → 两对 → 对子 → 高牌
'''
        tk.Label(content_frame,text=rules_text,font=('微软雅黑',11),bg='#F0F0F0',fg='#111',
                 justify=tk.LEFT,padx=10,pady=10,anchor='w').pack(fill=tk.X,padx=10,pady=5)

        tk.Label(content_frame,text='牌型说明',font=('微软雅黑',14,'bold'),bg='#F0F0F0').pack(fill=tk.X,padx=10,pady=(16,8))
        table=tk.Frame(content_frame,bg='#F0F0F0')
        table.pack(fill=tk.X,padx=20,pady=5)
        headers=('牌型','说明')
        data=(
            ('皇家同花顺','同一花色的10、J、Q、K、A；同时也命中“同花顺”彩卷'),
            ('同花顺','同一花色的五张连续点数；包含皇家同花顺'),('四条','四张相同点数'),('葫芦','三条 + 一对'),
            ('同花','五张同一花色'),('顺子','五张连续点数'),('三条','三张相同点数'),
            ('两对','两组对子'),('对子','两张相同点数'),('高牌','以上牌型均未形成'),
        )
        for c,h in enumerate(headers):
            tk.Label(table,text=h,font=('微软雅黑',10,'bold'),bg='#4B8BBE',fg='white',padx=10,pady=5).grid(row=0,column=c,sticky='nsew',padx=1,pady=1)
        for r,row_data in enumerate(data,start=1):
            bg='#E0E0E0' if r%2==0 else '#F0F0F0'
            for c,text in enumerate(row_data):
                tk.Label(table,text=text,font=('微软雅黑',10),bg=bg,padx=10,pady=5,anchor='center').grid(row=r,column=c,sticky='nsew',padx=1,pady=1)
        table.columnconfigure(0,weight=1);table.columnconfigure(1,weight=3)

        notes='''
注：
* “赢家牌型”与“独立牌型”是不同市场。独立牌型只看指定玩家自己的牌型，不要求该玩家获胜。
* 皇家同花顺是额外的精确市场；皇家同花顺出现时，“皇家同花顺”和原有“同花顺”两种彩卷都会命中。
* 半场永远只看2张手牌 + Flop 3张；全场看2张手牌 + 5张公共牌的最佳5张。
* 头VS头与半全场的平局处理规则不同，请以对应章节为准。
* 固定赔率是利润赔率；例如 $100 @3.90:1，普通中奖总返还为 $490。
'''
        tk.Label(content_frame,text=notes,font=('微软雅黑',10),bg='#F0F0F0',justify=tk.LEFT,padx=10,pady=10).pack(fill=tk.X,padx=10,pady=5)

        def sync_scroll(_event=None):
            content_frame.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox('all'))
        content_frame.bind('<Configure>',sync_scroll)
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(canvas_window,width=e.width))
        sync_scroll()

        ttk.Button(win,text='关闭',command=win.destroy).pack(pady=10)
        win.bind('<MouseWheel>',lambda e:canvas.yview_scroll(int(-1*(e.delta/120)),'units'))
        win.bind('<Button-4>',lambda e:canvas.yview_scroll(-1,'units'))
        win.bind('<Button-5>',lambda e:canvas.yview_scroll(1,'units'))

    def on_close(self):
        if self.destroyed:return
        self.destroyed=True;self._cancel_auto_reset();self._cancel_animation();update_balance_in_json(self.username,self.balance)
        if callable(self.on_balance_change):self.on_balance_change(float(self.balance))
        if callable(self.on_back):self.on_back(float(self.balance))
        else:
            try:self.winfo_toplevel().destroy()
            except tk.TclError:pass


def main(initial_balance=10000,username='Guest',*,parent=None,balance=None,user=None,on_back=None,on_balance_change=None):
    actual_balance=float(initial_balance if balance is None else balance);actual_user=username if user is None else user
    if parent is not None:
        page=TexasHoldemSportsbook(parent,actual_balance,actual_user,on_back,on_balance_change);page.pack(fill='both',expand=True);return page
    root=tk.Tk();root.title("五人德州扑克对决");root.geometry(WINDOW_GEOMETRY);root.resizable(False,False);root.configure(bg=ROOT_BG)
    page=TexasHoldemSportsbook(root,actual_balance,actual_user);page.pack(fill='both',expand=True)
    root.protocol('WM_DELETE_WINDOW',page.on_close);root.mainloop();return page.balance


if __name__=='__main__':
    print('最终余额:',main())
