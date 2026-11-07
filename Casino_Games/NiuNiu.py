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

"""牛牛：庄家手牌居上，两位玩家分别对庄；全部发牌、开牌及排牌后逐手结算。"""
import copy
import json
import os
import random
import re
import tkinter as tk
from collections import Counter
from itertools import combinations
import math
import time
from datetime import datetime
from tkinter import messagebox, ttk
try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
except ImportError:
    Image = ImageTk = ImageDraw = ImageFont = None

def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../A_Tools/Account/saving_data.json')
def load_user_data():
    with open(get_data_file_path(), 'r', encoding='utf-8') as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError('账户资料格式错误。')
    return data

def save_user_data(users):
    with open(get_data_file_path(), 'w', encoding='utf-8') as handle:
        json.dump(users, handle, ensure_ascii=False, indent=4)

def update_balance_in_json(username,new_balance):
    users=load_user_data()
    for user in users:
        if user.get('user_name')==username: user['cash']=f'{new_balance:.2f}'; break
    save_user_data(users)

class NiuNiuBetState:
    def __init__(self):
        self.bets = {}

    def total_stake(self):
        return sum(map(float, self.bets.values()))

    def total_at_risk(self):
        return sum(float(stake) * NiuNiuEngine.max_loss_multiplier(bet_type)
                   for bet_type, stake in self.bets.items())

    def current_area_bet(self, bet_type, _param=None):
        return float(self.bets.get(bet_type, 0))

    def add_bet(self, bet_type, amount, _param=None):
        self.bets[bet_type] = self.current_area_bet(bet_type) + float(amount)

    def clear_area(self, bet_type, _param=None):
        return float(self.bets.pop(bet_type, 0)) * NiuNiuEngine.max_loss_multiplier(bet_type)

    def clear_all(self):
        total = self.total_at_risk()
        self.bets.clear()
        return total


# Preserve the original project's imports and launch interface.
SangongBetState = NiuNiuBetState

class NiuNiuEngine:
    SUITS = ('Club', 'Diamond', 'Heart', 'Spade')
    RANKS = ('A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K')
    SIDES = ('Player1', 'Player2', 'Banker')
    PLAYERS = ('Player1', 'Player2')
    CARDS_PER_HAND = 5
    POWER = {rank: index for index, rank in enumerate(RANKS, 1)}
    SUIT_POWER = {'Diamond': 0, 'Club': 1, 'Heart': 2, 'Spade': 3}
    # A is first for display only; its value for counting a bull remains one.
    DISPLAY_POWER = dict(POWER, A=14)
    BET_TYPES = tuple(seat+' '+suffix for seat in ('Player1', 'Player2')
                      for suffix in ('Super', 'TwoPair', 'Trips', 'Player', 'Player Multiple', 'Banker', 'Banker Multiple'))

    def __init__(self):
        self.new_shoe()

    def new_shoe(self):
        self.deck = [(suit, rank) for suit in self.SUITS for rank in self.RANKS]
        random.SystemRandom().shuffle(self.deck)

    def remaining_cards(self):
        return len(self.deck)

    def needs_shuffle(self):
        return len(self.deck) < len(self.SIDES) * self.CARDS_PER_HAND

    def deal_round(self):
        if self.needs_shuffle():
            self.new_shoe()
        before = list(self.deck)
        hands = {side: [] for side in self.SIDES}
        for _ in range(self.CARDS_PER_HAND):
            for side in self.SIDES:
                hands[side].append(self.deck.pop())
        return {'hands': hands, 'deck_order': before, 'shoe_remaining': len(self.deck),
                'settled': False}

    @staticmethod
    def point_value(rank):
        if rank == 'A':
            return 1
        if rank in ('10', 'J', 'Q', 'K'):
            return 10
        return int(rank)

    @classmethod
    def display_sort_key(cls, card):
        return cls.DISPLAY_POWER[card[1]], cls.SUIT_POWER[card[0]]

    @classmethod
    def bull_indices(cls, hand):
        if len(hand) != cls.CARDS_PER_HAND:
            raise ValueError('牛牛每方必须有五张牌。')
        # Sorting candidate indices makes the chosen 3+2 arrangement independent
        # of deal order and guarantees a stable result when it is evaluated again.
        ordered = sorted(range(len(hand)), key=lambda i: cls.display_sort_key(hand[i]), reverse=True)
        for indices in combinations(ordered, 3):
            if sum(cls.point_value(hand[i][1]) for i in indices) % 10 == 0:
                return tuple(indices)
        return None

    @classmethod
    def arrange_indices(cls, hand):
        triple = cls.bull_indices(hand)
        if triple is None:
            return sorted(range(len(hand)), key=lambda i: cls.display_sort_key(hand[i]), reverse=True)
        rest = [i for i in range(len(hand)) if i not in triple]
        return (sorted(triple, key=lambda i: cls.display_sort_key(hand[i]), reverse=True)
                + sorted(rest, key=lambda i: cls.display_sort_key(hand[i]), reverse=True))

    @classmethod
    def arrange_hand(cls, hand):
        return [hand[i] for i in cls.arrange_indices(hand)]

    @classmethod
    def evaluate(cls, hand, side=None):
        triple = cls.bull_indices(hand)
        counts = Counter(card[1] for card in hand)
        highest = max((cls.POWER[rank], cls.SUIT_POWER[suit]) for suit, rank in hand)
        quads = [rank for rank, count in counts.items() if count == 4]
        if quads:
            return {'name': '四条', 'key': (11, cls.POWER[quads[0]], *highest),
                    'point': 10, 'kind': 'four_kind', 'bull_indices': triple}
        if triple is None:
            return {'name': '无牛', 'key': (0, *highest), 'point': 0,
                    'kind': 'no_bull', 'bull_indices': None}
        point = sum(cls.point_value(hand[i][1]) for i in range(len(hand)) if i not in triple) % 10
        level = point or 10
        name = '牛牛' if level == 10 else '牛' + '一二三四五六七八九'[level - 1]
        return {'name': name, 'key': (level, *highest), 'point': level,
                'kind': 'bull', 'bull_indices': triple}

    @classmethod
    def compare(cls, player_hand, banker_hand, player_side='Player1'):
        player = cls.evaluate(player_hand, player_side)
        banker = cls.evaluate(banker_hand, 'Banker')
        winner = player_side if player['key'] > banker['key'] else 'Banker' if player['key'] < banker['key'] else 'Tie'
        return winner, player, banker

    @classmethod
    def bet_spec(cls, bet_type):
        if bet_type not in cls.BET_TYPES:
            raise ValueError('未知的牛牛下注区域：' + str(bet_type))
        seat, suffix = bet_type.split(' ', 1)
        kind = ('two_pair' if suffix == 'TwoPair' else 'trips' if suffix == 'Trips'
                else 'super' if suffix == 'Super' else 'multiple' if suffix.endswith(' Multiple') else 'single')
        target = 'Banker' if suffix.startswith('Banker') else seat
        return seat, target, kind

    @classmethod
    def max_loss_multiplier(cls, bet_type):
        _seat, _target, kind = cls.bet_spec(bet_type)
        return 11.0 if kind == 'super' else 5.0 if kind == 'multiple' else 1.0

    @staticmethod
    def side_bet_odds(hand, kind):
        counts = sorted(Counter(rank for _suit, rank in hand).values())
        if kind == 'two_pair':
            return 15.0 if counts == [1, 2, 2] else 0.0
        if kind == 'trips':
            return 30.0 if counts == [1, 1, 3] else 0.0
        raise ValueError('未知的牌型边注。')

    @classmethod
    def comparisons(cls, hands):
        return {seat: cls.compare(hands[seat], hands['Banker'], seat) for seat in cls.PLAYERS}

    @classmethod
    def profit_odds(cls, evaluation, kind):
        if kind == 'single':
            return 0.5 if evaluation['kind'] == 'bull' and evaluation['point'] == 6 else 1.0
        if kind == 'multiple':
            if evaluation['kind'] == 'four_kind':
                return 5.0
            if evaluation['point'] == 10:
                return 3.0
            return 2.0 if evaluation['point'] >= 7 else 1.0
        if kind == 'super':
            return 11.0 if evaluation['kind'] == 'four_kind' else float(max(1, evaluation['point']))
        raise ValueError('未知的牛牛下注种类。')

    @classmethod
    def winning_spots(cls, hands):
        comparisons = cls.comparisons(hands)
        winners = set()
        for bet_type in cls.BET_TYPES:
            seat, target, kind = cls.bet_spec(bet_type)
            if kind in ('two_pair', 'trips'):
                won = cls.side_bet_odds(hands[seat], kind) > 0
            else:
                won = comparisons[seat][0] == target
            if won:
                winners.add((bet_type, None))
        return winners

    @classmethod
    def settle(cls, bets, hands):
        comparisons = cls.comparisons(hands)
        credit = held_total = 0.0
        outcomes = []
        for bet_type, value in bets.items():
            seat, target, kind = cls.bet_spec(bet_type)
            stake = float(value)
            if stake < 0 or not math.isfinite(stake):
                raise ValueError('下注金额必须是有限的非负数。')
            if not stake:
                continue
            held = stake * cls.max_loss_multiplier(bet_type)
            reserve = held - stake
            held_total += held
            winner, player, banker = comparisons[seat]
            evaluations = {seat: player, 'Banker': banker}
            profit = loss = commission = 0.0
            if kind in ('two_pair', 'trips'):
                odds = cls.side_bet_odds(hands[seat], kind)
                profit, loss = (stake * odds, 0.0) if odds else (0.0, stake)
                returned, refund, status = ((stake + profit, 0.0, 'win') if odds else (0.0, 0.0, 'lose'))
            elif winner == 'Tie':
                returned, refund, status = stake, reserve, 'tie'
            elif winner == target:
                odds = 1.0 if kind == 'single' and target == 'Banker' else cls.profit_odds(evaluations[target], kind)
                commission = 0.05 if kind in ('multiple', 'super') and odds > 1 else 0.0
                profit = stake * odds * (1 - commission)
                returned, refund, status = stake + profit, reserve, 'win'
            else:
                loss = stake * (1.0 if kind == 'single' else cls.profit_odds(evaluations[winner], kind))
                returned, refund, status = 0.0, held - loss, 'lose'
            amount = round(returned + refund, 2)
            credit += amount
            outcomes.append({'key': (bet_type, None), 'seat': seat, 'target': target, 'kind': kind,
                             'stake': stake, 'return_factor': returned / stake,
                             'return_amount': round(returned, 2), 'reserve_held': reserve,
                             'reserve_refund': round(refund, 2), 'reserve_forfeit': round(reserve - refund, 2),
                             'credit_amount': amount, 'profit': round(profit, 2), 'loss': round(loss, 2),
                             'commission_rate': commission, 'status': status})
        return {'credit': round(credit, 2), 'liability': 0.0,
                'net': round(credit - held_total, 2), 'held_total': held_total,
                'comparisons': {seat: comparison[0] for seat, comparison in comparisons.items()},
                'outcomes': outcomes}


SangongEngine = NiuNiuEngine

# UTH palette and canvas composition. All game rules above are the original
# NiuNiu rules; there is no dependency on the UTH module or its jackpots.
ROOT_BG = '#1B3D31'
TEXT = '#ffffff'
RED = '#ff2a23'
BLACK = '#050505'
DARK_BLUE = '#173f66'
GOLD = '#D4AF37'
PANEL_BG = '#F2E6C9'
HEADER_BG = '#D8B46A'
TITLE_FG = '#2A1B08'
SUITS = ['♠', '♥', '♦', '♣']
RANKS = list(NiuNiuEngine.RANKS)
SUIT_SYMBOLS = {'Spade': '♠', 'Heart': '♥', 'Diamond': '♦', 'Club': '♣'}


class NiuNiuTableGame:
    """NiuNiu rules behind the UTH table's round lifecycle."""
    SEATS = NiuNiuEngine.PLAYERS
    SIDES = NiuNiuEngine.SIDES
    MIN_BET = 100.0
    MAX_TABLE_BET = 2_000_000.0

    def __init__(self):
        self.engine = NiuNiuEngine()
        self.reset_game()

    @staticmethod
    def bet_limit_for(bet_type):
        return 500_000.0 if NiuNiuEngine.bet_spec(bet_type)[2] == 'single' else 50_000.0

    @classmethod
    def validate_bets(cls, bets, balance=None):
        normalized = {}
        targets = {}
        for bet_type, raw in bets.items():
            seat, target, kind = NiuNiuEngine.bet_spec(bet_type)
            amount = float(raw)
            if not math.isfinite(amount) or amount < 0:
                raise ValueError('下注金额必须是有限的非负数。')
            if not amount:
                continue
            if amount < cls.MIN_BET or abs(amount / cls.MIN_BET - round(amount / cls.MIN_BET)) > 1e-9:
                raise ValueError('每项下注须为100的整数倍。')
            if amount > cls.bet_limit_for(bet_type):
                raise ValueError('已超过该下注区限额。')
            if kind not in ('two_pair', 'trips'):
                if seat in targets and targets[seat] != target:
                    raise ValueError('同一组主注只可选择玩家或庄家其中一方。')
                targets[seat] = target
            normalized[bet_type] = amount
        if sum(normalized.values()) > cls.MAX_TABLE_BET:
            raise ValueError('全桌基础下注总额上限为2,000,000。')
        required = round(sum(amount * NiuNiuEngine.max_loss_multiplier(bet_type)
                             for bet_type, amount in normalized.items()), 2)
        if balance is not None:
            available = float(balance)
            if not math.isfinite(available) or available < 0 or required > available:
                raise ValueError('余额不足以承担下注本金及最大赔付预留金。')
        return normalized, required

    def start_round(self, bets, balance):
        if self.stage != 'betting':
            raise ValueError('牌局已经开始。')
        normalized, charged = self.validate_bets(bets, balance)
        result = self.engine.deal_round()
        result['sort_complete'] = False
        self.bets = normalized
        self.result = result
        self.hands = result['hands']
        self.deal_sequence = [(side, index) for index in range(NiuNiuEngine.CARDS_PER_HAND)
                              for side in self.SIDES]
        self.stage = 'dealing'
        return charged

    def settle(self):
        if self.settlement is not None:
            return self.settlement
        if not self.result or not self.result.get('sort_complete'):
            raise ValueError('五张牌全部翻开并完成排牌后才可结算。')
        self.settlement = NiuNiuEngine.settle(self.bets, self.hands)
        self.result['settled'] = True
        self.stage = 'settling'
        return self.settlement

    def reset_game(self):
        self.stage = 'betting'
        self.bets = {}
        self.hands = {side: [] for side in self.SIDES}
        self.result = None
        self.settlement = None
        self.deal_sequence = []


class NiuNiuGUI(tk.Frame):
    """UTH's green/gold table, controls and animation, with NiuNiu gameplay."""
    WIDTH, HEIGHT = 1150, 750
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    DEAL_CARD_MS = 224 / .85
    DEAL_MOVE_MS = (128 / .75) / .85
    BET_CHIP_RADIUS = 23
    HOUSE_CHIP_POS = (575, 43)
    TABLE_GREEN = '#4b1e22'
    ZONE_COLORS = {'Player1': '#2A5541', 'Player2': '#204536'}
    SEAT_NAMES = {'Player1': '玩家1', 'Player2': '玩家2', 'Banker': '庄家'}
    MIN_BET = NiuNiuTableGame.MIN_BET
    MAX_TABLE_BET = NiuNiuTableGame.MAX_TABLE_BET
    CHIP_SPECS = [(100, '#202020'), (500, '#d780c0'), (1000, '#ab0058'),
                  (5000, '#ba3438'), (10000, '#70439a'), (50000, '#2e7542')]
    # Baccarat's rounded panel treatment; the NiuNiu wager keys stay unchanged.
    BET_FELT = '#083f38'
    BET_CREAM = '#f8ecd3'
    BET_INK = '#110b07'
    WAGER_CHIP_RADIUS = 23
    M_CHIP_COLOR = '#102d47'
    BET_CHIP_SPECS = [(100, '#202020', '100'), (500, '#d780c0', '500'),
        (1000, '#ab0058', '1K'), (5000, '#ba3438', '5K'), (10000, '#70439a', '10K'),
        (50000, '#2e7542', '50K'), (250000, '#ffffff', '250K')]

    def __init__(self, parent, balance=10000, user=None, on_back=None,
                 on_balance_change=None, game_mode=None):
        if Image is None or ImageTk is None:
            raise RuntimeError('牛牛的UTH介面需要Pillow，请先安装Pillow。')
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.root = self
        self.username, self.balance = user, float(balance)
        self.final_balance = self.balance
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game_mode = 'niuniu'
        self.game = NiuNiuTableGame()
        self.engine = self.game.engine
        self.bet_state = NiuNiuBetState()
        self.last_bet = None
        self.last_round_bets = []
        self.last_win = self.last_net = 0.0
        self.selected_chip = 1000.0
        self._game_instruction_dialog = None
        self._jobs = set()
        self._closing = False
        self._credited = self._return_persisted = self._crediting = False
        self._restart_job = self._restart_deadline = None
        self._motion_count = self._chip_serial = 0
        self._settlement_started = False
        self._flash_job = None
        self._win_flash_complete = None
        self.settlement_flash_step = 0
        self.flash_white = False
        self.visual_chips = {}
        self.last_round_snapshot = None
        self._history_available = False
        self._face_photos, self._pil_cards, self._flip_photos = {}, {}, {}
        self.card_items, self.bet_spots = {}, {}
        self.grouped_card_sides = set()
        self.pre_deal_bets = {}
        self.current_result = None
        self.hovered_bet_type = None
        self._cursor_kind = None
        self.winning_spot_keys = set()
        self.history_file = os.path.join(self.get_runtime_json_dir(), 'NiuNiu.json')
        self._load_assets()
        self._create_widgets()
        self._refresh()
        self.bind('<Configure>', self._center_table, add='+')
        self.bind('<Destroy>', self._on_destroy, add='+')

    @property
    def bets(self):
        return self.bet_state.bets

    @property
    def game_in_progress(self):
        return self.game.stage != 'betting' or self._motion_count > 0

    @property
    def accept_bets(self):
        return not self._closing and self.game.stage == 'betting' and not self._motion_count

    @property
    def animation_running(self):
        return self.game.stage in ('dealing', 'revealing', 'sorting', 'sweeping')

    @property
    def settlement_running(self):
        return self.game.stage in ('settling', 'await_restart', 'returning', 'credit_pending')

    @property
    def last_win_amount(self):
        return self.last_win

    def _draw_chips(self):
        self.canvas.delete('rack')
        self.chip_specs = list(self.CHIP_SPECS)
        diameter, gap = 56, 8
        start = (self.WIDTH - (len(self.chip_specs)*diameter + (len(self.chip_specs)-1)*gap))/2
        for index, (amount, color) in enumerate(self.chip_specs):
            x = start + index*(diameter+gap)
            tag = 'rack_' + str(index)
            self.canvas.create_oval(x, 646, x+56, 702, fill='#182F25',
                outline=GOLD if amount == self.selected_chip else '#6C7850', width=3, tags=('rack', tag))
            self.canvas.create_oval(x+5, 651, x+51, 697, fill=color, outline=PANEL_BG, width=2, tags=('rack', tag))
            self._text(x+28, 674, self._compact(amount), 10,
                       self.contrast_text_color(color), tags=('rack', tag))
            self.canvas.tag_bind(tag, '<Button-1>', lambda _e, a=amount: self.select_chip(a))

    def select_chip(self, amount):
        if not self._closing and self.game.stage == 'betting':
            self.selected_chip = float(amount)
            self._draw_chips()

    def _draw_limit_table(self):
        c = self.canvas
        x0, x1, y0 = 30, 326, 75
        c.create_rectangle(x0, y0, x1, 181, fill=ROOT_BG, outline=GOLD, width=2)
        c.create_rectangle(x0, y0, x1, y0+29, fill=ROOT_BG, outline=GOLD)
        self._text((x0+x1)/2, y0+14, '下注上限', 13, PANEL_BG)
        for col, (title, value) in enumerate((('最低', '$100'), ('平倍最高', '$500,000'), ('其他最高', '$50,000'))):
            left, right = x0+col*(x1-x0)/3, x0+(col+1)*(x1-x0)/3
            c.create_rectangle(left, y0+29, right, y0+66, outline='#77906B')
            c.create_rectangle(left, y0+66, right, 181, outline='#77906B')
            self._text((left+right)/2, y0+47, title, 11, PANEL_BG)
            self._text((left+right)/2, y0+86, value, 11, GOLD)

    def _draw_payout_panel(self):
        c = self.canvas
        c.create_rectangle(824, 75, 1120, 181, fill=ROOT_BG, outline=GOLD, width=2)
        self._text(972, 94, '倍数赔付', 16, '#F6D675')
        self._text(972, 126, '翻倍 1–5 : 1', 17, '#FFE29A')
        self._text(972, 158, '超级牛牛 1–11 : 1', 15, PANEL_BG)

    def _create_widgets(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=ROOT_BG, highlightthickness=0)
        self.canvas.place(x=0, y=0, width=self.WIDTH, height=self.HEIGHT)
        self.control_buttons = {}
        c = self.canvas
        self._text(178, 44, '牛牛', 18, GOLD)
        self._text(972, 44, 'NIU NIU', 14, GOLD)
        c.create_rectangle(340, 10, 810, 201, fill=self.TABLE_GREEN, outline='')
        self.title_items = {'Banker': self._text(575, 28, '庄家', 16, PANEL_BG)}
        self._draw_limit_table()
        self._draw_payout_panel()
        c.create_rectangle(22, 184, 1128, 207, fill=ROOT_BG, outline='#65784B')
        self.street_item = self._text(164, 195, '下注阶段', 12, PANEL_BG)
        self.reserve_notice_item = self._text(575, 195, '翻倍&超级牛牛均需要支付预留金', 12, GOLD)
        self.reserve_item = self._text(976, 195, '', 10, PANEL_BG)
        self.result_items = {}
        for seat, x0, x1 in (('Player1', 22, 566), ('Player2', 582, 1128)):
            c.create_rectangle(x0, 215, x1, 391, fill=self.ZONE_COLORS[seat], outline='')
            self.title_items[seat] = self._text((x0+x1)/2, 231, self.SEAT_NAMES[seat], 18, PANEL_BG)
            self.result_items[seat] = self._text((x0+x1)/2, 376, '', 12, GOLD)
        self.draw_board()
        self._draw_bottom_controls()
        self.deal_button = self.start_button
        self.balance_text, self.total_bet_text = self.balance_item, self.total_item
        self._draw_card_slots()

    def _draw_card_slots(self):
        self.canvas.delete('card_slots')
        for side in self.game.SIDES:
            for index in range(NiuNiuEngine.CARDS_PER_HAND):
                x, y = self.card_position(side, index)
                self.canvas.create_rectangle(x, y, x+self.CARD_WIDTH, y+self.CARD_HEIGHT,
                    outline='#7B9374', dash=(3, 3), tags='card_slots')
        self.canvas.tag_lower('card_slots', 'cards') if self.card_items else None

    def card_size(self, side):
        return self.CARD_WIDTH, self.CARD_HEIGHT

    def card_position(self, side, index):
        center = {'Banker': 575, 'Player1': 294, 'Player2': 855}[side]
        gap = 20 if side in self.grouped_card_sides else 0
        width = 5*self.CARD_WIDTH + 4*8 + gap
        x = center-width/2 + index*(self.CARD_WIDTH+8) + (gap if index >= 3 else 0)
        return x, 59 if side == 'Banker' else 246

    @staticmethod
    def _card_image_key(card):
        return SUIT_SYMBOLS.get(card[0], card[0]), card[1]

    def _bet_is_available(self, bet_type):
        if not self.accept_bets or bet_type not in NiuNiuEngine.BET_TYPES:
            return False
        seat, target, kind = NiuNiuEngine.bet_spec(bet_type)
        if kind in ('two_pair', 'trips'):
            return True
        for other, stake in self.bets.items():
            other_seat, other_target, other_kind = NiuNiuEngine.bet_spec(other)
            if stake > 0 and seat == other_seat and other_kind not in ('two_pair', 'trips') and target != other_target:
                return False
        return True

    def _spot_pointer(self, bet_type):
        self.hovered_bet_type = bet_type
        # Motion locks wagering without turning a departing chip into a
        # forbidden-pointer effect. Only conflicting idle bets use that icon.
        if bet_type is None or self.game.stage != 'betting' or self._motion_count:
            kind = ''
        else:
            kind = 'hand2' if self._bet_is_available(bet_type) else 'forbidden'
        if kind == self._cursor_kind:
            return
        for cursor in (['no', 'notallowed', 'X_cursor'] if kind == 'forbidden' else [kind]):
            try:
                self.canvas.configure(cursor=cursor)
                self._cursor_kind = kind
                break
            except tk.TclError:
                continue

    def bet_limit_for(self, bet_type):
        return self.game.bet_limit_for(bet_type)

    def add_chip_to_bet(self, bet_type, amount=None):
        if not self._bet_is_available(bet_type):
            return False
        try:
            requested = float(self.selected_chip if amount is None else amount)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(requested) or requested < self.MIN_BET or abs(requested/100-round(requested/100)) > 1e-9:
            return False
        held = self.bet_state.total_at_risk()
        multiplier = NiuNiuEngine.max_loss_multiplier(bet_type)
        room = min(requested, self.bet_limit_for(bet_type)-self.bets.get(bet_type, 0),
                   self.MAX_TABLE_BET-self.bet_state.total_stake(), (self.balance-held)/multiplier)
        allowed = float(int(max(0, room)//100)*100)
        if allowed < self.MIN_BET:
            messagebox.showwarning('下注限制', '余额不足以承担下注及预留金，或已达到该区限额。', parent=self)
            return False
        new_bets = dict(self.bets)
        new_bets[bet_type] = new_bets.get(bet_type, 0)+allowed
        return self._apply_bet_layout(new_bets)

    def place_bet(self, bet_type, amount=None, record_undo=True):
        return self.add_chip_to_bet(bet_type, amount)

    place_base_bet = place_bet

    def _set_visual(self, bet_type, role, amount, xy=None):
        key = (bet_type, role)
        spot = self.bet_spots[(bet_type, None)]
        if amount > 0:
            self.visual_chips[key] = dict(amount=float(amount),
                xy=xy or (spot['reserve_pos'] if role == 'reserve' else spot['center']),
                role=role, radius=spot['wager_radius'])
        else:
            self.visual_chips.pop(key, None)

    def _apply_bet_layout(self, new_bets):
        if not self.accept_bets:
            return False
        try:
            normalized, _cost = self.game.validate_bets(new_bets, self.balance)
        except (TypeError, ValueError) as exc:
            messagebox.showwarning('无法下注', str(exc), parent=self)
            return False
        previous = dict(self.bets)
        self.bets.clear()
        self.bets.update(normalized)
        transfers = []
        for bet_type in NiuNiuEngine.BET_TYPES:
            old, new = previous.get(bet_type, 0), normalized.get(bet_type, 0)
            for role, factor in (('stake', 1), ('reserve', NiuNiuEngine.max_loss_multiplier(bet_type)-1)):
                delta = (new-old)*factor
                if not delta:
                    continue
                spot = self.bet_spots[(bet_type, None)]
                center = spot['reserve_pos'] if role == 'reserve' else spot['center']
                if delta > 0:
                    transfers.append(dict(amount=delta, start=self._rack_position(), target=center,
                        radius=spot['wager_radius'],
                        arrive=lambda b=bet_type, r=role, a=new*factor: self._set_visual(b, r, a)))
                else:
                    self._set_visual(bet_type, role, new*factor)
                    transfers.append(dict(amount=-delta, start=center, target=self._rack_position(),
                        radius=spot['wager_radius'], duration=440))
        self._run_chip_batch(transfers, self._refresh)
        self._refresh()
        return True

    def reset_bets(self):
        return self._apply_bet_layout({}) if self.accept_bets else False

    clear_bets = reset_bets

    def reset_single_bet(self, bet_type, _param=None):
        if not self.accept_bets:
            return False
        new_bets = dict(self.bets)
        new_bets.pop(bet_type, None)
        return self._apply_bet_layout(new_bets)

    clear_single_bet = reset_single_bet

    def apply_last_bet(self):
        return self._apply_bet_layout(self.last_bet) if self.accept_bets and self.last_bet else False

    repeat_last_bets = apply_last_bet

    def snapshot_bets(self):
        return [(bet_type, None, float(stake)) for bet_type, stake in self.bets.items() if stake > 0]

    def _render_chips(self):
        self.canvas.delete('bet_chips')
        for index, ((bet_type, role), chip) in enumerate(sorted(self.visual_chips.items(), key=lambda item: item[0][1] != 'stake')):
            if chip['amount'] <= 0:
                continue
            spot = self.bet_spots[(bet_type, None)]
            tag = 'bet_chip_' + str(index)
            tags = ('bet_chips', tag, spot['tag'])
            self._draw_amount_chip(chip['amount'], *chip['xy'], tags=tags, radius=chip['radius'])

    update_bet_chips = _render_chips

    def _refresh(self):
        if self._closing:
            return
        c = self.canvas
        c.itemconfigure(self.balance_item, text=f'余额: ${self.balance:,.2f}')
        held = self.bet_state.total_at_risk()
        completed = self.game.stage in ('settling', 'await_restart', 'returning', 'credit_pending', 'sweeping')
        c.itemconfigure(self.total_item, text=f'上局返还: ${self.last_win:,.2f}' if completed or not held else f'本局下注: ${held:,.2f}')
        stake = self.bet_state.total_stake()
        c.itemconfigure(self.reserve_item, text=f'本金 ${stake:,.0f} · 预留 ${held-stake:,.0f}' if not completed else f'本局净额 ${self.last_net:+,.2f}')
        captions = {'betting': '下注阶段', 'dealing': '发牌中…', 'revealing': '开牌中…',
                    'sorting': '排牌中…', 'settling': '派彩中…', 'await_restart': '已结算',
                    'returning': '筹码返回中…', 'credit_pending': '返还金额待保存', 'sweeping': '收牌中…'}
        self.current_status = captions[self.game.stage]
        c.itemconfigure(self.street_item, text=self.current_status)
        betting = self.accept_bets
        self.set_control_button_state(self.clear_button, betting)
        self.set_control_button_state(self.repeat_button, betting and bool(self.last_bet))
        self.set_control_button_state(self.start_button, betting)
        restarting = self.game.stage in ('await_restart', 'returning', 'credit_pending', 'sweeping')
        c.itemconfigure(self.repeat_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button, state='normal' if restarting else 'hidden')
        self.set_control_button_state(self.restart_button, self.game.stage in ('await_restart', 'credit_pending'))
        for key, spot in self.bet_spots.items():
            spot['enabled'] = self._bet_is_available(key[0])
        self._render_chips()
        self._spot_pointer(self.hovered_bet_type)

    update_display = _refresh
    update_control_states = _refresh

    def _persist_balance(self):
        try:
            if self.username and self.username != 'Guest':
                update_balance_in_json(self.username, self.balance)
            if callable(self.on_balance_change):
                self.on_balance_change(float(self.balance))
            self.final_balance = float(self.balance)
        except Exception as exc:
            messagebox.showerror('余额保存失败', str(exc), parent=self)
            return False
        return True

    save_balance = _persist_balance

    def start_game(self):
        if not self.accept_bets:
            return
        try:
            charged = self.game.start_round(self.bets, self.balance)
        except ValueError as exc:
            messagebox.showwarning('无法开始', str(exc), parent=self)
            return
        self.balance = round(self.balance-charged, 2)
        self.current_result = self.game.result
        self.pre_deal_bets = dict(self.game.bets)
        if self.pre_deal_bets:
            self.last_bet = dict(self.pre_deal_bets)
            self.last_round_bets = self.snapshot_bets()
        self._credited = self._return_persisted = self._settlement_started = False
        self.settlement_flash_step = 0
        self.flash_white = False
        self._flash_job = self._win_flash_complete = None
        self._history_available = False
        self.winning_spot_keys.clear()
        self._cancel_restart_timer()
        self._close_card_sequence()
        self.canvas.delete('cards')
        self.card_items.clear()
        self._flip_photos.clear()
        self.grouped_card_sides.clear()
        self._load_assets()
        self._draw_card_slots()
        for side, item in self.title_items.items():
            self.canvas.itemconfigure(item, text=self.SEAT_NAMES[side], fill=PANEL_BG)
        for item in self.result_items.values():
            self.canvas.itemconfigure(item, text='')
        for spot in self.bet_spots.values():
            self._set_bet_spot_outline(spot)
        self._persist_balance()
        self._refresh()
        self._deal_next(self.game.deal_sequence, 0)

    deal_cards = start_game

    def handle_enter_deal(self, _event=None):
        if self.game.stage in ('await_restart', 'credit_pending'):
            self._return_all_chips()
        else:
            self.start_game()

    def _reveal_initial_cards(self):
        self.game.stage = 'revealing'
        self._refresh()
        sequence = [(side, index) for side in self.game.SIDES for index in range(5)]
        self._reveal_next(sequence, 0, self._arrange_hands)

    def _arrange_hands(self):
        self.game.stage = 'sorting'
        self._refresh()
        hands = self.game.hands
        self.grouped_card_sides = {side for side in self.game.SIDES if NiuNiuEngine.bull_indices(hands[side]) is not None}
        moves, ordered_hands, ordered_items = [], {}, {}
        for side in self.game.SIDES:
            indices = NiuNiuEngine.arrange_indices(hands[side])
            ordered_hands[side] = [hands[side][index] for index in indices]
            for target_index, old_index in enumerate(indices):
                item = self.card_items[(side, old_index)]
                sx, sy = self.canvas.coords(item)
                tx, ty = self.card_position(side, target_index)
                moves.append((item, sx, sy, tx, ty))
                ordered_items[(side, target_index)] = item
        self._draw_card_slots()
        def frame(index=0):
            fraction = index/20
            eased = fraction*fraction*(3-2*fraction)
            for item, sx, sy, tx, ty in moves:
                self.canvas.coords(item, sx+(tx-sx)*eased, sy+(ty-sy)*eased)
            if index < 20:
                self._schedule(24, frame, index+1)
            else:
                self.game.hands.update(ordered_hands)
                self.card_items = ordered_items
                self.game.result['sort_complete'] = True
                self._schedule(120, self._settle)
        frame()

    def _settle(self):
        if self._settlement_started:
            return
        result = self.game.settle()
        self._settlement_started = True
        self.last_win, self.last_net = result['credit'], result['net']
        for side, item in self.title_items.items():
            evaluation = NiuNiuEngine.evaluate(self.game.hands[side], side)
            self.canvas.itemconfigure(item, text=self.SEAT_NAMES[side]+' · '+evaluation['name'],
                                      fill=GOLD if evaluation['name'] in ('牛牛', '四条') else PANEL_BG)
        for seat, winner in result['comparisons'].items():
            self.canvas.itemconfigure(self.result_items[seat], text='和局' if winner == 'Tie' else '玩家胜' if winner == seat else '庄家胜')
        self.winning_spot_keys = NiuNiuEngine.winning_spots(self.game.hands)
        for key in self.winning_spot_keys:
            self._set_bet_spot_outline(self.bet_spots[key], GOLD, 3)
        transfers = []
        for outcome in result['outcomes']:
            bet_type = outcome['key'][0]
            spot = self.bet_spots[(bet_type, None)]
            if outcome['status'] == 'lose':
                chip = self.visual_chips.pop((bet_type, 'stake'), None)
                if chip:
                    transfers.append(dict(amount=chip['amount'], start=chip['xy'], target=self.HOUSE_CHIP_POS,
                        radius=chip['radius'], duration=280))
            if outcome['reserve_held']:
                self._set_visual(bet_type, 'reserve', outcome['reserve_refund'])
                if outcome['reserve_forfeit'] > 0:
                    transfers.append(dict(amount=outcome['reserve_forfeit'], start=spot['reserve_pos'],
                        target=self.HOUSE_CHIP_POS, radius=spot['wager_radius'], duration=280))
            if outcome['profit'] > 0:
                target = spot['profit_pos']
                transfers.append(dict(amount=outcome['profit'], start=self.HOUSE_CHIP_POS, target=target, duration=440,
                    radius=spot['wager_radius'],
                    arrive=lambda b=bet_type, a=outcome['profit'], xy=target: self._set_visual(b, 'profit', a, xy)))
        try:
            self._save_sangong_history(self.game.result, result)
        except Exception as exc:
            messagebox.showerror('历史记录保存失败', str(exc), parent=self)
        self._refresh()
        pending = {'flash', 'chips'}
        def completed(part):
            pending.discard(part)
            if not pending and not self._closing:
                self._await_next_round()
        self._start_win_flash(lambda: completed('flash'))
        self._run_chip_batch(transfers, lambda: completed('chips'))

    finish_deal = _settle

    def _start_win_flash(self, complete):
        self.settlement_flash_step = 0
        self._win_flash_complete = complete
        if not self.winning_spot_keys:
            self._win_flash_complete = None
            complete()
            return
        self._flash_sangong()

    def _flash_sangong(self):
        self._flash_job = None
        if self._closing or self.game.stage != 'settling':
            return
        if self.settlement_flash_step >= 6:
            self._set_sangong_flash(False)
            complete, self._win_flash_complete = self._win_flash_complete, None
            if complete:
                complete()
            return
        self._set_sangong_flash(self.settlement_flash_step % 2 == 0)
        self.settlement_flash_step += 1
        self._flash_job = self._schedule(450, self._flash_sangong)

    def _set_sangong_flash(self, white):
        self.flash_white = bool(white)
        for key in self.winning_spot_keys:
            spot = self.bet_spots.get(key)
            if not spot:
                continue
            self.canvas.itemconfigure(spot['border'], fill='#ffffff' if white else spot['base_fill'])
            foreground = '#111111' if white else spot['foreground']
            for item in spot['text_items']:
                self.canvas.itemconfigure(item, fill=foreground)
            self.canvas.itemconfigure(spot['inner_frame_id'],
                outline='#ffffff' if white else spot['normal_inner_outline'])

    def _await_next_round(self):
        if self.game.stage != 'settling':
            return
        self.game.stage = 'await_restart'
        # The NiuNiu engine pops the end of the shoe. Reverse it for the same
        # left-to-right reading order as UTH's completed-round deck window.
        self.last_round_snapshot = dict(full_deck=tuple(reversed(self.game.result['deck_order'])),
            start_pos=0, images={key: im.copy() for key, im in self.original_images.items()})
        self._history_available = True
        self._cancel_restart_timer()
        self._restart_deadline = time.monotonic()+30
        self._refresh()
        self._restart_tick()

    def _finish_round(self):
        if self.game.stage != 'sweeping':
            return
        self.game.reset_game()
        self._set_sangong_flash(False)
        self._flash_job = self._win_flash_complete = None
        self.bets.clear()
        self.visual_chips.clear()
        self.current_result = None
        self.grouped_card_sides.clear()
        self._history_available = False
        self.winning_spot_keys.clear()
        for side, item in self.title_items.items():
            self.canvas.itemconfigure(item, text=self.SEAT_NAMES[side], fill=PANEL_BG)
        for item in self.result_items.values():
            self.canvas.itemconfigure(item, text='')
        for spot in self.bet_spots.values():
            self._set_bet_spot_outline(spot)
        self._draw_card_slots()
        self._refresh()

    def reset_game(self, auto_reset=False):
        if self.game.stage == 'betting':
            self.reset_bets()
        elif self.game.stage in ('await_restart', 'credit_pending'):
            self._return_all_chips()

    def exit_game(self):
        self.on_close()

    def cancel_pending_callbacks(self):
        self._cancel_jobs()

    def _instruction_pages(self):
        # Filled from the original NiuNiu rules, rendered by UTH's manual UI.
        manual_pages = [
                ('玩法', '上方为庄家手牌，下方为玩家1和玩家2。\n每位玩家只与庄家比较，玩家之间不比较。', [
                    ('发牌与排牌', '', [
                        ('一局十五张牌', '使用不含大小王的52张牌，庄家、玩家1和玩家2各发五张。\n座位固定；不足十五张时，下一局发牌前重新洗牌。'),
                        ('固定结算顺序', '十五张背面牌全部发完 → 逐张翻开 → 自动排牌 → 逐手结算。\n有牛时先放凑成10、20或30的三张，其余两张放第四、第五位，两组之间留出间隔。\n无牛时从左到右按A、K、Q、J、10……3、2排列。\n排牌动画完成前不结算；同一局只结算一次。'),
                    ], []),
                    ('牌型', '', [
                        ('算牛', 'A为1点，2至10按牌面计算，J、Q、K各为10点。\n三张凑成整十后，另两张合计的个位数为牛几；整十为牛牛。\n找不到整十三张组合为无牛。'),
                        ('比较大小', '四条＞牛牛＞牛九＞……＞牛一＞无牛。\n同牛数比最大单牌：K＞Q＞J＞10＞……＞2＞A。\n同点数比花色：黑桃＞红心＞梅花＞方块；四条先比四张相同牌。\n完全相同则主注退回。显示排序的A在前，不改变计点及比牌规则。'),
                    ], []),
                ]),
                ('下注区', '每位玩家正下方有一组对应下注区，共两组。采用圆角分格、浅色边注及蓝红主注；获胜区每450毫秒交替亮白，共三次，完成后才开放下一局。', [
                    ('三行圆角下注区', '', [
                        ('第一行', '超级牛牛：沿用原版超级牛牛规则，押该玩家对庄家获胜。'),
                        ('第二行', '两对、三条：只看该玩家的五张牌，与主注输赢无关。'),
                        ('第三行', '平倍(玩家)、翻倍(玩家)、平倍(庄家)、翻倍(庄家)。\n该组内押庄家，只比较庄家与这组对应玩家。\n例如玩家1区押庄家、玩家2区押玩家，可同时存在并独立结算。'),
                        ('下注操作', '各下注项可独立下注，不要求先下平倍。\n同一组内选择玩家或庄家后，对方平倍、翻倍立即禁止下注，鼠标显示禁止光标，颜色保持不变。\n清除该方全部下注后，对方重新开放；两对和三条不受此限制。\n左键下注，右键清除该区；清除会移走该区本金和预留金筹码，尚未扣款。'),
                    ], [('限红', ['项目', '上限', '说明'], [
                        ['平倍', '每区500,000', '玩家与庄家分别计额'],
                        ['其他下注', '每区50,000', '基础下注额，不含预留金'],
                        ['全桌下注', '2,000,000', '基础下注总额'],
                    ])]),
                ]),
                ('赔率', '赔付表示赢款:本金；3:2代表下注2、赢3、共返还5。', [
                    ('基础及牌型边注', '', [], [('固定赔率', ['下注', '赔率', '条件'], [
                        ['平倍(玩家)', '1:1*', '牛六赢，收取50%赢款手续费'],
                        ['平倍(庄家)', '1:1', '庄家击败对应玩家'],
                        ['两对', '15:1', '恰好两对加一张单牌'],
                        ['三条', '30:1', '恰好三张同点数加两张不同单牌'],
                    ])]),
                    ('翻倍与超级牛牛', '', [], [('多档赔率（抽佣前）', ['获胜牌型', '翻倍 1-5:1', '超级牛牛 1-11:1'], [
                        ['无牛、牛一', '1:1', '1:1'],
                        ['牛二至牛六', '1:1', '2:1 至 6:1'],
                        ['牛七至牛九', '2:1', '7:1 至 9:1'],
                        ['牛牛', '3:1', '10:1'],
                        ['四条', '5:1', '11:1'],
                    ])]),
                    ('判奖说明', '', [
                        ('沿用原版抽佣', '翻倍及超级牛牛高于1:1的赢款扣5%。\n两对和三条按固定赔率支付，不抽佣；葫芦和四条不算这两项边注。'),
                    ], []),
                ]),
                ('预留金', '翻倍下注在正常本金以外，额外扣留4倍下注额。\n每项翻倍下注的预留金显示在该格右下角；超级牛牛显示在赔率左侧。预留金、盈利及本金筹码在同一区内大小一致，移动时也保持大小。', [
                    ('扣留、返还与没收', '', [
                        ('下注100翻倍', '翻倍格内显示100筹码，该格右下角预留400。\n下注阶段先摆放筹码，“本局下注”显示500，包含本金和预留金。开牌时才一次扣除500。\n“上局返还”包括本金、赢款以及未被没收的预留金返还，不重复累计。'),
                        ('获胜或和局', '获胜时结算本金与赢款，同时退回全部400预留金。\n和局退回本金及全部预留金。'),
                        ('败给牛牛', '按3倍输款共扣300，其中本金100、预留金200。\n其余200预留金退回。败给四条时共输500，400预留金全部没收。'),
                        ('超级牛牛', '保留原版最大11倍输款机制：本金以外另预留10倍。\n预留金显示在该格赔率左侧，结算时按实际输款返还剩余部分。'),
                        ('清除、重复和退出', '下注阶段清除对应本金及预留金筹码，尚未扣除余额。\n重复下注同时恢复预留金；余额不足时不下注。\n开牌后须完成结算才可退出；已结算时退出会先将返还金额保存，且只入账一次。'),
                    ], []),
                ]),
            ]
        manual_pages.append(('操作与牌序', '筹码、开牌与下一局操作。', [('控制列', '', [('下注', '左键加入所选筹码；右键清除单区。底部清除按钮清空全部下注，重复下注恢复上局金额。余额须足以承担本金及预留金。'), ('开牌与下一局', '按Enter或开牌开始。全部开牌和排牌后派彩，点击再来一局或等待30秒，筹码返回后入账，再统一收牌。'), ('检视上局牌序', '右键点击再来一局会暂停倒数，并打开上局牌序。蓝底为本局实际发出的15张牌，按发牌先后排列；其余为牌靴剩余牌。'), ('限红与牌靴', '每项最低100；平倍每区最高500,000，其他每区最高50,000；全桌基础注最高2,000,000。牌靴不足15张时重新洗牌。')], [])]))
        return manual_pages

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
        current = os.path.dirname(os.path.abspath(__file__))
        roots = (current, os.path.dirname(current), os.path.dirname(os.path.dirname(current)))
        candidates = [os.path.join(root, 'A_Tools', 'Card', f) for f in (folder, 'Poker1', 'Poker2') for root in roots]
        base = next((path for path in candidates if os.path.isdir(path)), candidates[0])
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


    def _draw_chip(self, tag, amount, x, y, rectangular=False, extra_tags=(), show_amount=True, radius=None):
        c=self.canvas;tags=(tag,*extra_tags)
        if rectangular:
            label=self._compact(amount);width=max(96,10*len(label)+16)
            c.create_rectangle(x-width/2,y-18,x+width/2,y+18,fill='#731D2A',outline='#000000',width=1,tags=tags)
            if show_amount:self._text(x,y,label,11,'#FFF0C3',tags=tags)
        else:
            self._draw_amount_chip(amount, x, y, tags, radius=radius)


    def _rack_position(self, index=None, total=1):
        if index is not None:
            return 575+(index-(total-1)/2)*min(28,140/max(1,total-1)),674
        index=next((i for i,(value,_) in enumerate(self.chip_specs) if value==self.selected_chip),None)
        if index is None:return (575,674)
        width=len(self.chip_specs)*56+(len(self.chip_specs)-1)*8
        return (self.WIDTH-width)/2+index*64+28,674


    def _animate_chip(self, amount, start, target, complete=None, rectangular=False, duration=220, radius=None):
        if not amount:
            if complete:complete()
            return
        self._motion_count+=1;self._chip_serial+=1
        tag=f'moving_chip_{self._chip_serial}'
        self._draw_chip(tag,amount,*start,rectangular,extra_tags=('moving_chips',),radius=radius)
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
                lambda t=transfer:arrived(t),transfer.get('rectangular',False),transfer.get('duration',220),radius=transfer.get('radius'))


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
                    chip.get('rectangular',False),extra_tags=('returned_chips',),radius=chip['radius'])
            transfers.append(dict(amount=chip['amount'],start=chip['xy'],target=target,
                rectangular=chip.get('rectangular',False),duration=600,arrive=arrived,radius=chip['radius']))
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


    def _close_card_sequence(self):
        current=getattr(self,'_sequence_window',None)
        if current is not None:
            try:
                if current.winfo_exists():current.destroy()
            except tk.TclError:pass
        self._sequence_window=None


    def _center_table(self, event=None):
        # Keep the original 1150×750 composition centered when embedded.
        self.canvas.place(x=max(0, (self.winfo_width()-self.WIDTH)//2),
                          y=max(0, (self.winfo_height()-self.HEIGHT)//2),
                          width=self.WIDTH, height=self.HEIGHT)


    def _deal_next(self, sequence, offset):
        if offset==len(sequence):
            self._reveal_initial_cards()
            return
        side,index = sequence[offset]
        x,y = self.card_position(side,index)
        photo = self._face_photos['back']
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


    def _reveal_next(self, sequence, offset, complete):
        if offset==len(sequence): complete(); return
        side,index = sequence[offset]
        hand = self.game.hands[side]
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
                photos = self._face_photos
                self.canvas.itemconfigure(item,image=photos[self._card_image_key(card)])
                self._flip_photos.pop(item,None)
                if index == 4:
                    evaluation = NiuNiuEngine.evaluate(hand, side)
                    self.canvas.itemconfigure(self.title_items[side], text=self.SEAT_NAMES[side]+' · '+evaluation['name'])
                self._reveal_next(sequence,offset+1,complete)
        flip()


    def on_close(self):
        if self._closing or self._crediting:return
        settled=self.game.stage in ('settling','await_restart','returning','credit_pending','sweeping')
        if self.game_in_progress and not settled:
            messagebox.showinfo('牌局进行中','请先等待本局开牌、排牌及结算完成。',parent=self)
            return
        # 已结算的返还金额必须先保存成功，才允许中断动画并关闭。
        if settled:
            if not self._credit_round_return():return
        elif not self._persist_balance():return
        self._close_card_sequence()
        self._closing=True
        self._cancel_restart_timer()
        self._cancel_jobs()
        self._unbind_enter()
        self.final_balance = float(self.balance)
        if callable(self.on_back):
            self.on_back(float(self.balance))
        else:
            self.winfo_toplevel().destroy()


    def show_card_sequence(self, event=None):
        if self.game.stage!='await_restart' or not self._history_available:return
        snapshot=self.last_round_snapshot
        if not snapshot:
            messagebox.showinfo('提示','尚无已结算牌局的牌序。',parent=self);return
        current=getattr(self,'_sequence_window',None)
        if current is not None and current.winfo_exists():current.lift();return
        # UTH's scrollable nine-column deck window, with NiuNiu's shoe order.
        win=tk.Toplevel(self);self._sequence_window=win
        win.title('上局牌序');win.geometry('730x750');win.resizable(0,0);win.configure(bg='#f0f0f0')
        tk.Label(win,text=f'上局牌序：共{len(snapshot["full_deck"])}张 · 蓝底为本局15张已发牌',font=('Arial',14,'bold'),bg='#f0f0f0').pack(pady=10)
        main_frame=tk.Frame(win,bg='#f0f0f0');main_frame.pack(fill=tk.BOTH,expand=True,padx=10,pady=5)
        scrollbar=ttk.Scrollbar(main_frame);scrollbar.pack(side=tk.RIGHT,fill=tk.Y)
        canvas=tk.Canvas(main_frame,bg='#f0f0f0',yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT,fill=tk.BOTH,expand=True);scrollbar.config(command=canvas.yview)
        content_frame=tk.Frame(canvas,bg='#f0f0f0');canvas.create_window((0,0),window=content_frame,anchor='nw')
        card_frame=tk.Frame(content_frame,bg='#f0f0f0');card_frame.pack(fill=tk.BOTH,expand=True,padx=20,pady=5)
        small_images={}
        for i,card in enumerate(snapshot['full_deck']):
            key=self._card_image_key(card)
            original=(snapshot['images'].get(key) or self.original_images.get(key) or self.original_images['back'])
            small_images[i]=ImageTk.PhotoImage(original.resize((60,90),Image.Resampling.LANCZOS),master=win)
        win._card_images=small_images
        for row in range(math.ceil(len(snapshot['full_deck'])/9)):
            row_frame=tk.Frame(card_frame,bg='#f0f0f0');row_frame.pack(fill=tk.X)
            for col in range(9):
                idx=row*9+col
                if idx>=len(snapshot['full_deck']):break
                container=tk.Frame(row_frame,bg='#f0f0f0');container.grid(row=0,column=col,padx=5)
                bg='light blue' if idx<15 else '#f0f0f0'
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

        instruction_title = '牛牛 · 完整图解玩法'
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

                                source_image = self.original_images[(SUIT_SYMBOLS.get(suit, suit), rank)]
                                small_image = source_image.resize((70, 98), Image.Resampling.LANCZOS)

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


    @staticmethod
    def _bet_rounded_points(x0, y0, x1, y1, radius=7):
        # Same twelve-point smooth outline as Baccarat's standard board.
        return (x0+radius, y0, x1-radius, y0, x1, y0, x1, y0+radius,
                x1, y1-radius, x1, y1, x1-radius, y1, x0+radius, y1,
                x0, y1, x0, y1-radius, x0, y0+radius, x0, y0)

    def draw_board(self):
        self.draw_mode_betting_board()

    def draw_mode_betting_board(self):
        c = self.canvas
        c.delete('board_dynamic')
        c.delete('bet_chips')
        self.bet_spots = {}
        c.create_rectangle(12, 391, 1138, 620, fill=self.BET_FELT, outline='',
                           tags=('board_dynamic', 'bet_board_background'))
        for seat, (x0, x1) in (('Player1', (22, 566)), ('Player2', (582, 1128))):
            group = 'bet_group_' + seat
            self._text((x0+x1)/2, 404, self.SEAT_NAMES[seat]+' · 对庄下注', 11,
                       self.BET_CREAM, tags=('board_dynamic', group))
            self._draw_baccarat_spot(seat+' Super', x0+4, 416, x1-4, 466,
                '超级牛牛', 'SUPER NIU NIU', '1-11:1', self.BET_CREAM, '#01479a', False, group)
            for index, (suffix, name, english, odds, fill, ink) in enumerate((
                ('TwoPair', '两对', 'TWO PAIR', '15:1', '#b6e1f6', '#01479a'),
                ('Trips', '三条', 'THREE OF A KIND', '30:1', '#dd3a20', self.BET_CREAM))):
                width = (x1-x0-14)/2
                left = x0+4+index*(width+6)
                self._draw_baccarat_spot(seat+' '+suffix, left, 472, left+width, 522,
                    name, english, odds, fill, ink, False, group)
            specs = (
                ('Player', '平倍(玩家)', 'PLAYER SINGLE', '1:1*', '#0046a0'),
                ('Player Multiple', '翻倍(玩家)', 'PLAYER MULTIPLE', '1-5:1', '#01479a'),
                ('Banker', '平倍(庄家)', 'BANKER SINGLE', '1:1', '#bf0711'),
                ('Banker Multiple', '翻倍(庄家)', 'BANKER MULTIPLE', '1-5:1', '#a80909'))
            width = (x1-x0-26)/4
            for index, (suffix, name, english, odds, fill) in enumerate(specs):
                left = x0+4+index*(width+6)
                self._draw_baccarat_spot(seat+' '+suffix, left, 528, left+width, 614,
                    name, english, odds, fill, self.BET_CREAM, True, group)
        self.update_bet_chips()

    def _draw_baccarat_spot(self, bet_type, x0, y0, x1, y1, label, english,
                            odds, fill, foreground, main, group):
        c = self.canvas
        seat, target, kind = NiuNiuEngine.bet_spec(bet_type)
        tag = self.spot_tag((bet_type, None))
        tags = ('board_dynamic', tag, group)
        c.create_polygon(*self._bet_rounded_points(x0-2, y0-1, x1+2, y1+2),
            smooth=True, fill=self.BET_INK, outline=self.BET_INK, width=2, tags=tags)
        shape = self._bet_rounded_points(x0, y0, x1, y1)
        border = c.create_polygon(*shape, smooth=True, fill=fill,
            outline=self.BET_CREAM, width=1.2, tags=tags)
        frame = c.create_polygon(*shape, smooth=True, fill='', outline=self.BET_CREAM,
            width=1.2, tags=tags+('bet_board_frame',))
        inner = c.create_polygon(*self._bet_rounded_points(x0+2, y0+2, x1-2, y1-2),
            smooth=True, fill='', outline=foreground if kind == 'super' else fill,
            width=.7, tags=tags+('bet_board_frame', 'bet_board_inner_frame'))
        cx, cy = (x0+x1)/2, (y0+y1)/2
        if main:
            label_xy, english_xy, odds_xy = (cx, y0+13), (cx, y0+28), (cx, y1-12)
            chip_pos = (cx, cy)
            anchor = 'center'
        else:
            label_xy, english_xy, odds_xy = (x0+14, y0+13), (x0+14, y1-12), (x1-14, cy)
            chip_pos = (cx, cy)
            anchor = 'w'
        label_item = c.create_text(*label_xy, text=label, fill=foreground,
            font=('Microsoft YaHei UI', -18 if main else -20, 'bold'), anchor=anchor, tags=tags)
        english_item = c.create_text(*english_xy, text=english, fill=foreground,
            font=('Arial', -10 if main else -11, 'bold'), anchor=anchor, tags=tags)
        odds_item = c.create_text(*odds_xy, text=odds, fill=foreground,
            font=('Arial', -14 if main else -20, 'bold'),
            anchor='center' if main else 'e', tags=tags)
        self.register_spot(bet_type, x0, y0, x1, y1, chip_pos, label)
        spot = self.bet_spots[(bet_type, None)]
        spot.update(rect_id=border, border=border, frame_id=frame, inner_frame_id=inner,
            label_item=label_item, odds_item=odds_item, text_items=(label_item, english_item, odds_item),
            base_odds=odds, main=main,
            normal_outline=self.BET_CREAM, normal_outline_width=1.2,
            classic_shape_coords=shape, base_fill=fill, fill=fill, foreground=foreground,
            seat=seat, target=target, kind=kind, center=chip_pos, enabled=True,
            wager_radius=self.WAGER_CHIP_RADIUS,
            normal_inner_outline=foreground if kind == 'super' else fill)
        radius = spot['wager_radius']
        inset = radius+3
        spot['profit_pos'] = (max(x0+inset, cx-2*radius-4),
                              y0+inset if main else cy)
        if kind in ('multiple', 'super'):
            reserve_x, reserve_y = (x1-inset, y1-inset) if kind == 'multiple' else (x1-122, cy)
            spot['reserve_pos'] = (reserve_x+6, reserve_y+6) if kind == 'multiple' else (reserve_x, reserve_y)
        c.tag_bind(tag, '<Button-1>', lambda _e, b=bet_type: self.place_bet(b))
        c.tag_bind(tag, '<Button-3>', lambda _e, b=bet_type: self.clear_single_bet(b))
        c.tag_bind(tag, '<Enter>', lambda _e, b=bet_type: self._spot_pointer(b))
        c.tag_bind(tag, '<Leave>', lambda _e: self._spot_pointer(None))

    def _set_bet_spot_outline(self, spot, color=None, width=None):
        color = spot['normal_outline'] if color is None else color
        width = spot['normal_outline_width'] if width is None else width
        for item in (spot['border'], spot['frame_id']):
            self.canvas.itemconfigure(item, outline=color, width=width)


    def _draw_amount_chip(self, amount, x, y, tags, radius=None):
        """Use identical denomination colours and labels for wagers and fees."""
        radius = self.WAGER_CHIP_RADIUS if radius is None else radius
        color = self.bet_chip_color(amount)
        self.canvas.create_oval(x-radius, y-radius, x+radius, y+radius,
                               fill='#292522', outline='#151311', width=1, tags=tags)
        self.canvas.create_oval(x-radius+3, y-radius+3, x+radius-3, y+radius-3,
                               fill=color, outline='#e2ddd5', width=1, tags=tags)
        self.canvas.create_text(x, y, text=self._compact_amount(amount),
                               font=('Arial', 9, 'bold'),
                               fill=self.contrast_text_color(color), tags=tags)


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


    @classmethod
    def bet_chip_color(cls, amount):
        # _compact_amount() switches to M at 1,000,000; mirror that visual state
        # with a dark-navy chip. contrast_text_color() then yields white text.
        if amount >= 1_000_000:
            return cls.M_CHIP_COLOR

        color = cls.BET_CHIP_SPECS[0][1]
        for threshold, chip_color, _label in cls.BET_CHIP_SPECS:
            if amount >= threshold:
                color = chip_color
            else:
                break
        return color


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
    def _history_card(card):
        return card[1] + {'Club':'♣','Diamond':'♦','Heart':'♥','Spade':'♠'}[card[0]]


    def _save_sangong_history(self, result, settlement):
        default_stats = {'player1_win': 0, 'player2_win': 0, 'dealer_win': 0, 'tie': 0, 'game': 0}
        try:
            with open(self.history_file, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                data = {}
        except (OSError, json.JSONDecodeError):
            data = {}
        raw_stats = data.get('history_record')
        stats = copy.deepcopy(default_stats)
        if isinstance(raw_stats, dict):
            for key in stats:
                try:
                    stats[key] = max(0, int(raw_stats.get(key, 0)))
                except (TypeError, ValueError):
                    stats[key] = 0
        data['history_record'] = stats
        history = data.get('history')
        if not isinstance(history, list):
            history = []
            data['history'] = history
        stats['game'] += 1
        for seat, winner in settlement['comparisons'].items():
            counter = seat.lower()+'_win' if winner == seat else 'dealer_win' if winner == 'Banker' else 'tie'
            stats[counter] += 1
        hands = result['hands']
        history.append({'game_id': stats['game'], 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'game_mode': 'niuniu', 'game_format': 'two_players_vs_banker', 'seat_order': list(NiuNiuEngine.SIDES),
            'deck_order': [self._history_card(c) for c in result['deck_order']],
            'player1_cards': [self._history_card(c) for c in hands['Player1']],
            'player2_cards': [self._history_card(c) for c in hands['Player2']],
            'dealer_cards': [self._history_card(c) for c in hands['Banker']],
            'hand_types': {side: NiuNiuEngine.evaluate(hands[side], side)['name'] for side in NiuNiuEngine.SIDES},
            'bets': copy.deepcopy(self.pre_deal_bets),
            'result': {'comparisons': settlement['comparisons'], 'winnings': settlement['credit'],
                       'liability': 0.0, 'net': settlement['net'],
                       'reserve_refund': sum(o['reserve_refund'] for o in settlement['outcomes']),
                       'reserve_forfeit': sum(o['reserve_forfeit'] for o in settlement['outcomes'])}})
        try:
            with open(self.history_file, 'w', encoding='utf-8') as handle:
                json.dump(data, handle, ensure_ascii=False, indent=4)
        except OSError:
            pass


# Preserve the project's launch classes, aliases and callback signatures.
SangongV13 = NiuNiuGUI
NiuNiuV13 = NiuNiuGUI


class SangongGame(NiuNiuGUI):
    def __init__(self, root, username=None, initial_balance=10000,
                 on_back=None, on_balance_change=None, game_mode=None):
        super().__init__(root, initial_balance, username, on_back, on_balance_change, game_mode)
        self.pack(fill=tk.BOTH, expand=True)


NiuNiuGame = SangongGame


def main(parent=None, balance=10000, user=None, on_back=None,
         on_balance_change=None, username=None, game_mode=None):
    if username is not None and user is None:
        user = username
    if parent is not None and not isinstance(parent, tk.Misc):
        balance, parent = parent, None
    if parent is not None:
        return NiuNiuGUI(parent, balance, user, on_back, on_balance_change, game_mode)
    root = tk.Tk()
    root.title('牛牛')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)
    game = NiuNiuGUI(root, balance, user, on_back, on_balance_change, game_mode)
    game.pack(fill=tk.BOTH, expand=True)
    root.protocol('WM_DELETE_WINDOW', game.on_close)
    root.mainloop()
    return game


if __name__ == '__main__':
    main(balance=10_000_000)
