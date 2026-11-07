"""Shoot Poker with Dragon_Tiger_Phoenix's UI and parent-window interface.

Account encryption, card artwork and CSM stay under the existing A_Tools tree.
The original main(initial_balance, username) entry point still returns a balance.
"""

import sys as _account_sys
from pathlib import Path as _AccountPath

_account_root = next((p for p in (_AccountPath(__file__).resolve().parent,
                                 *_AccountPath(__file__).resolve().parents)
                      if (p / 'A_Tools' / 'Account' / 'secure_json.py').is_file()), None)
if _account_root is None:
    raise RuntimeError('Cannot locate encrypted account storage')
_PROJECT_ROOT = str(_account_root)
if _PROJECT_ROOT not in _account_sys.path:
    _account_sys.path.insert(0, _PROJECT_ROOT)
from A_Tools.Account import install_secure_json as _install_secure_json

_install_secure_json()
del _install_secure_json, _account_root, _AccountPath, _account_sys

import copy
import json
import math
import os
import random
import sys
import tempfile
import time
import tkinter as tk
import uuid
from datetime import datetime
from tkinter import messagebox, ttk

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_CSM_CANDIDATES = list(dict.fromkeys((
    os.path.abspath(os.path.join(_THIS_DIR, '..', 'A_Tools', 'Card')),
    os.path.abspath(os.path.join(_THIS_DIR, '..', 'Card')),
    _THIS_DIR,
    os.path.join(_PROJECT_ROOT, 'A_Tools', 'Card'),
)))
_CARD_TOOLS_DIR = next((p for p in _CSM_CANDIDATES
                        if os.path.isfile(os.path.join(p, 'CSM_Shuffler.py'))), None)
if _CARD_TOOLS_DIR is None:
    raise ModuleNotFoundError('找不到 CSM_Shuffler.py，已检查：' + '; '.join(_CSM_CANDIDATES))
if _CARD_TOOLS_DIR not in sys.path:
    sys.path.insert(0, _CARD_TOOLS_DIR)
from CSM_Shuffler import CSMError, ContinuousShuffleMachine

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
except ImportError:
    Image = ImageTk = ImageDraw = ImageFont = None

SHOOT_POKER_VERSION = 'DTP-UI-PARENT-V5'


def get_data_file_path():
    return os.path.join(_PROJECT_ROOT, 'A_Tools', 'Account', 'saving_data.json')


def load_user_data():
    with open(get_data_file_path(), 'r', encoding='utf-8') as handle:
        users = json.load(handle)
    if not isinstance(users, list):
        raise ValueError('账号数据格式错误，未覆盖原文件。')
    return users


def save_user_data(users):
    with open(get_data_file_path(), 'w', encoding='utf-8') as handle:
        json.dump(users, handle, ensure_ascii=False, indent=4)


def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if isinstance(user, dict) and user.get('user_name') == username:
            user['cash'] = f'{new_balance:.2f}'
            save_user_data(users)
            return True
    return False


class ShootDragonGate:
    """Original shooting rules with the DTP chamber/round ownership protocol.

    GUI instances always receive a CSM.  The local-deck constructor remains for
    callers using the original rules class; it is never an automatic CSM fallback.
    """

    SUITS = ('Club', 'Diamond', 'Heart', 'Spade')
    RANKS = ('A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K')
    RANK_BETS = tuple(f'rank_{rank}' for rank in RANKS)
    RESULTS = ('射中', '射偏', '撞柱')
    DISPLAY_NAMES = {
        'suit_Club': '♣ 梅花', 'suit_Diamond': '♦ 方块',
        'suit_Heart': '♥ 红心', 'suit_Spade': '♠ 黑桃',
        'misc_red': '红色', 'misc_black': '黑色',
        'misc_small': '小 (A–7)', 'misc_big': '大 (8–K)',
        'shoot_射中': '射中', 'shoot_射偏': '射偏', 'shoot_撞柱': '撞柱',
    }
    DISPLAY_NAMES.update({f'rank_{rank}': rank for rank in RANKS})
    MODE_NAMES = {'shootdragon': '射龙门'}
    MODE_ROWS = {'shootdragon': (
        ('suit_Club', 'suit_Diamond', 'suit_Heart', 'suit_Spade'),
        ('misc_red', 'misc_small', 'misc_big', 'misc_black'),
    )}
    ODDS_TEXT = {'shootdragon': {
        'suit_Club': '3.5:1', 'suit_Diamond': '3.5:1',
        'suit_Heart': '3.5:1', 'suit_Spade': '3.5:1',
        'misc_red': '0.95:1', 'misc_small': '0.95:1',
        'misc_big': '0.95:1', 'misc_black': '0.95:1',
        'shoot_射中': '流动赔率', 'shoot_射偏': '流动赔率', 'shoot_撞柱': '流动赔率',
    }}
    ODDS_TEXT['shootdragon'].update({key: '11:1' for key in RANK_BETS})
    ODDS_TABLE = {
        0: (None, 0.1, 13.5), 1: (None, 0.1, 5.6),
        2: (11, 0.2, 5.6), 3: (5, 0.35, 5.6),
        4: (3, 0.5, 5.6), 5: (2, 0.75, 5.6),
        6: (1.5, 1, 5.6), 7: (1, 1.5, 5.6),
        8: (0.75, 2, 5.6), 9: (0.5, 3, 5.6),
        10: (0.35, 5, 5.6), 11: (0.2, 11, 5.6),
        12: (0.1, None, 5.6),
    }

    def __init__(self, decks=3, external_deck=None, csm=None, game_id=None):
        self.decks = int(decks)
        self.csm = csm
        self.game_id = str(game_id or f'ShootPoker:local:{uuid.uuid4().hex}')
        self.card_buffer = []
        self.current_batch_id = None
        self.used_by_batch = {}
        self.round_open = False
        self.round_id = None
        self.first_card = self.second_card = self.third_card = None
        self.diff = self.result = None
        self.cut_position = self.used_cards = self.round_counter = 0
        self.deck = []
        self.total_cards = 0
        if csm is not None:
            if external_deck is not None:
                raise ValueError('CSM 模式不可混用外部牌靴。')
        elif external_deck is not None:
            self.deck = [self.normalize_card(card) for card in external_deck]
            self.total_cards = len(self.deck)
        else:
            self.create_deck(self.decks)

    @classmethod
    def normalize_card(cls, card):
        if isinstance(card, dict):
            suit, rank = card['suit'], card['rank']
        else:
            suit, rank = card
        suit = {'♣': 'Club', '♦': 'Diamond', '♥': 'Heart', '♠': 'Spade'}.get(suit, suit)
        rank = str(rank).upper()
        if suit not in cls.SUITS or rank not in cls.RANKS:
            raise ValueError(f'无效牌张：{suit!r}, {rank!r}')
        return suit, rank

    @classmethod
    def card_value(cls, card):
        rank = cls.normalize_card(card)[1]
        return cls.RANKS.index(rank) + 1

    rank_value = card_value

    def create_deck(self, decks=3):
        if self.csm is not None:
            raise RuntimeError('CSM 模式不创建本地牌靴。')
        if int(decks) <= 0:
            raise ValueError('牌副数必须大于零。')
        self.deck = [(suit, rank) for _ in range(int(decks))
                     for suit in self.SUITS for rank in self.RANKS]
        random.shuffle(self.deck)
        self.total_cards = len(self.deck)
        self.cut_position = 0
        return self.deck

    def advanced_shuffle(self, cut_pos):
        if self.csm is not None:
            raise RuntimeError('CSM 自动维护牌仓，无需手动切牌。')
        if self.round_open:
            raise RuntimeError('牌局中不可切牌。')
        if not self.deck:
            self.create_deck(self.decks)
        cut_pos = int(cut_pos) % len(self.deck)
        self.deck = self.deck[cut_pos:] + self.deck[:cut_pos]
        burn_count = 1 + min(10, self.card_value(self.deck[0]))
        self.deck = self.deck[burn_count:]
        self.total_cards = len(self.deck)
        self.cut_position = self.round_counter = 0
        self.used_cards = burn_count

    def _clear_local_csm_state(self):
        self.round_id = None
        self.round_open = False
        self.card_buffer = []
        self.current_batch_id = None
        self.used_by_batch = {}

    def start_round(self):
        if self.round_open:
            raise RuntimeError('上一局尚未结束。')
        self.first_card = self.second_card = self.third_card = None
        self.diff = self.result = None
        try:
            if self.csm is None:
                if self.remaining_cards() < 3:
                    raise RuntimeError('牌靴剩余不足三张，请先重新洗牌。')
            else:
                self.round_id = self.csm.begin_round(
                    self.game_id, self.current_batch_id if self.card_buffer else None)
            self.used_by_batch = {}
            self.round_open = True
            if self.csm is not None and not self.card_buffer:
                self._request_next_chamber()
        except Exception:
            self._clear_local_csm_state()
            raise

    def _request_next_chamber(self):
        packet = self.csm.acquire_chamber(self.game_id, self.round_id)
        self.current_batch_id = packet['batch_id']
        self.card_buffer = list(packet['cards'])
        if not self.card_buffer:
            raise CSMError('自动洗牌机返回了空仓。')

    def remaining_cards(self):
        if self.csm is None:
            return max(0, len(self.deck) - self.cut_position)
        return len(self.card_buffer) + self.csm.available_cards()

    def needs_shuffle(self):
        return self.csm is None and self.remaining_cards() < 3

    def draw_card(self):
        if not self.round_open:
            raise RuntimeError('牌局尚未开始。')
        if self.csm is None:
            if self.cut_position >= len(self.deck):
                raise RuntimeError('牌靴已用完。')
            card = self.deck[self.cut_position]
            self.cut_position += 1
            return self.normalize_card(card)
        if not self.card_buffer:
            self._request_next_chamber()
        record = self.card_buffer.pop(0)
        self.used_by_batch.setdefault(self.current_batch_id, []).append(record['card_id'])
        return self.normalize_card(record)

    def deal_first_two(self):
        if not self.round_open or self.first_card is not None or self.second_card is not None:
            raise RuntimeError('当前牌局不可重复发门柱牌。')
        self.first_card = self.draw_card()
        self.second_card = self.draw_card()
        self.diff = abs(self.card_value(self.first_card) - self.card_value(self.second_card))
        return self.first_card, self.second_card

    def reveal_third_card(self):
        if not self.round_open or self.first_card is None or self.second_card is None:
            raise RuntimeError('请先发前两张牌。')
        if self.third_card is not None:
            raise RuntimeError('本局第三张牌已开。')
        self.third_card = self.draw_card()
        self.result = self.result_for_values(
            self.card_value(self.first_card), self.card_value(self.second_card),
            self.card_value(self.third_card))
        self.round_counter += 1
        return self.round_result()

    @staticmethod
    def result_for_values(first, second, third):
        if third in (first, second):
            return '撞柱'
        return '射中' if min(first, second) < third < max(first, second) else '射偏'

    def deal_initial(self):
        if self.csm is None and self.round_open and self.third_card is not None:
            self.finish_round()
        if not self.round_open:
            self.start_round()
        self.deal_first_two()
        return self.reveal_third_card()

    def get_odds_for_shoot(self):
        if self.diff is None:
            raise RuntimeError('门柱牌尚未发出。')
        return self.ODDS_TABLE[self.diff]

    def odds_by_bet(self):
        odds = {key: (11.0 if key.startswith('rank_') else
                     3.5 if key.startswith('suit_') else 0.95)
                for key in self.DISPLAY_NAMES if not key.startswith('shoot_')}
        if self.diff is not None:
            odds.update(zip(('shoot_射中', 'shoot_射偏', 'shoot_撞柱'),
                            self.get_odds_for_shoot()))
        else:
            odds.update({f'shoot_{name}': None for name in self.RESULTS})
        return odds

    def round_result(self):
        if self.third_card is None:
            raise RuntimeError('第三张牌尚未开出。')
        return {
            'winner': self.result, 'diff': self.diff,
            'first_card': self.first_card, 'second_card': self.second_card,
            'third_card': self.third_card,
            'first_score': self.card_value(self.first_card),
            'second_score': self.card_value(self.second_card),
            'third_score': self.card_value(self.third_card),
        }

    @classmethod
    def return_factors(cls, result):
        first = cls.card_value(result['first_card'])
        second = cls.card_value(result['second_card'])
        third_card = cls.normalize_card(result['third_card'])
        third = cls.card_value(third_card)
        winner = cls.result_for_values(first, second, third)
        factors = {key: 0.0 for key in cls.DISPLAY_NAMES}
        factors[f'rank_{third_card[1]}'] = 12.0
        factors[f'suit_{third_card[0]}'] = 4.5
        factors['misc_red' if third_card[0] in ('Diamond', 'Heart') else 'misc_black'] = 1.95
        factors['misc_small' if third <= 7 else 'misc_big'] = 1.95
        odds = dict(zip(cls.RESULTS, cls.ODDS_TABLE[abs(first - second)]))
        if odds[winner] is not None:
            factors[f'shoot_{winner}'] = 1.0 + odds[winner]
        return factors

    @classmethod
    def resolve_bets(cls, bets, result, _mode=None):
        factors = cls.return_factors(result)
        outcomes = []
        for key, raw_stake in bets.items():
            stake = float(raw_stake)
            if key not in cls.DISPLAY_NAMES or not math.isfinite(stake) or stake <= 0:
                raise ValueError(f'无效下注：{key!r}')
            returned = round(stake * factors[key], 2)
            outcomes.append({
                'key': (key, None), 'label': cls.DISPLAY_NAMES[key],
                'stake': stake, 'return_factor': factors[key],
                'return_amount': returned, 'profit': round(returned - stake, 2),
                'status': 'win' if factors[key] > 1 else 'lose',
            })
        credit = round(sum(item['return_amount'] for item in outcomes), 2)
        return {
            'credit': credit,
            'gross_profit': round(sum(max(0, item['profit']) for item in outcomes), 2),
            'lost_stake': round(sum(max(0, -item['profit']) for item in outcomes), 2),
            'net': round(credit - sum(float(value) for value in bets.values()), 2),
            'outcomes': outcomes, 'side_factors': factors,
        }

    def finish_round(self):
        if not self.round_open:
            return
        if self.csm is None:
            self.round_open = False
            return
        rid = self.round_id
        try:
            for batch_id in list(self.used_by_batch):
                card_ids = self.used_by_batch[batch_id]
                if card_ids:
                    self.csm.return_cards(self.game_id, batch_id, card_ids)
                del self.used_by_batch[batch_id]
        except Exception:
            self._clear_local_csm_state()
            raise
        try:
            self.csm.end_round(self.game_id, rid)
        except Exception:
            self._clear_local_csm_state()
            raise
        finally:
            self.round_id = None
            self.round_open = False

    def close(self):
        try:
            if self.csm is not None:
                self.csm.release_game(self.game_id, force_shuffle=True)
        finally:
            self._clear_local_csm_state()


class ShootPokerBetState:
    """DTP's bet container, preserving Shoot Poker's original chip amounts."""

    def __init__(self):
        self.bets = {}

    def total_at_risk(self):
        return round(sum(float(value) for value in self.bets.values()), 2)

    def current_area_bet(self, bet_type, _param=None):
        return float(self.bets.get(bet_type, 0.0))

    def add_bet(self, bet_type, amount, _param=None):
        amount = round(float(amount), 2)
        if not math.isfinite(amount) or amount <= 0:
            return False
        self.bets[bet_type] = round(self.current_area_bet(bet_type) + amount, 2)
        return True

    def remove_amount(self, bet_type, amount, _param=None):
        current = self.current_area_bet(bet_type)
        amount = float(amount)
        if not math.isfinite(amount):
            return 0.0
        removed = round(min(current, max(0.0, amount)), 2)
        left = round(current - removed, 2)
        if left > 0:
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


class BubbleShootPokerGame(tk.Frame):
    """Shoot rules in the DTP window, parent interface and Canvas design."""

    WIDTH, HEIGHT = 1150, 750
    GAME_X0, GAME_X1 = 12, 770
    HISTORY_X0, HISTORY_X1 = 778, 1138
    BOARD_INNER_X0, BOARD_INNER_X1 = 22, 760
    TABLE_WIDTH, TABLE_HEIGHT = 754, 302
    RANK_ROW_Y = (322, 394)
    SUIT_ROW_Y, MISC_ROW_Y, SHOOT_ROW_Y = (398, 460), (464, 526), (530, 614)
    CHIP_MOVE_DURATION_MS, CHIP_MOVE_STEPS = 200, 10
    BG, PANEL, PANEL_LINE = '#17120f', '#211811', '#665240'
    FELT, FELT_2, LINE, GOLD = '#083f38', '#0c5148', '#c3d5ca', '#e7d36c'
    MAX_RECORDS, BEAD_MAX_RECORDS, HISTORY_DROP_COUNT = 300, 72, 6
    RESULT_COLORS = {'射中': '#d94a4e', '射偏': '#d3a202', '撞柱': '#2878d0'}
    CHIP_SPECS = [
        (100, '#202020', '100'),
        (500, '#d780c0', '500'), (1000, '#ab0058', '1K'),
        (5000, '#ba3438', '5K'), (10000, '#70439a', '10K'),
        (30000, '#d0a347', '30K'), (50000, '#2e7542', '50K'),
    ]
    BET_COLORS = {
        'suit_Club': '#222222', 'suit_Spade': '#222222',
        'suit_Diamond': '#bd2632', 'suit_Heart': '#bd2632',
        'misc_red': '#bd2632', 'misc_black': '#222222',
        'misc_small': '#6d4aa2', 'misc_big': '#8d6632',
        'shoot_射中': '#d94a4e', 'shoot_射偏': '#a57900', 'shoot_撞柱': '#2878d0',
    }
    CARD_SIZE = (100, 140)

    def __init__(self, parent, balance=1000000, user='Guest', on_back=None,
                 on_balance_change=None, game_mode='shootdragon', csm=None):
        super().__init__(parent, bg=self.BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.root = self
        self.username = user
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.balance = round(float(balance), 2)
        if not math.isfinite(self.balance) or self.balance < 0:
            raise ValueError('余额必须为非负有限数值。')
        self.final_balance = self.balance
        self.game_mode = 'shootdragon'
        self.csm = csm if csm is not None else ContinuousShuffleMachine()
        self.csm_game_id = f'ShootPoker:{self.username or "local"}:{uuid.uuid4().hex}'
        self.engine = ShootDragonGate(csm=self.csm, game_id=self.csm_game_id)
        self.game = self.engine
        self.bet_state = ShootPokerBetState()
        self.current_bets = self.bet_state.bets
        self.selected_chip = 1000.0
        self.undo_stack = []
        self.last_round_bets = []
        self.bet_spots = {}
        self.chip_selector_items = {}
        self.control_buttons = {}
        self.phase = 'ready'
        self.accept_bets = self.betting_enabled = False
        self.animation_running = self.settlement_running = False
        self.animation_after_ids = set()
        self.chip_motion_after_ids = set()
        self.chip_motion_serial = 0
        self.chip_motion_records = {}
        self.pending_bet_visual_amounts = {}
        self._closing = False
        self._round_settled = True
        self.pre_deal_bets = None
        self.current_result = None
        self.last_win_amount = self.last_net = 0.0
        self.summary_mode = 'bet'
        self.flash_mode = None
        self.flash_winning_keys = set()
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        self.flash_original_text_colors = {}
        self.settlement_hold_amounts = {}
        self._temp_flip_images = {}
        self.card_images = {}
        self.card_pil = {}
        self.back_image = self.back_pil = None
        self.bead_show_scores = False
        self.history_panel_mode = 'roads'
        self.big_road_scroll_col = 0
        self.big_road_auto_follow = True
        self.big_road_virtual_cols = 50
        self.big_road_view_cols = 14
        self.runtime_json_dir = self.get_runtime_json_dir()
        self.runtime_data_file = os.path.join(self.runtime_json_dir, 'Shoot_Poker.json')
        self.runtime_store = self.load_runtime_store()
        self.history_store = self.normalize_history_store(self.runtime_store['temp_finish_data'])
        self.history_data = list(self.history_store['records'])
        self.last_72_store = self.load_last_72_store()
        self.last_72_data = list(self.last_72_store['records'])
        self.statistic_data = self.load_statistic_data()
        self._load_assets()
        self.create_ui()
        self.select_chip(self.selected_chip)
        self.update_display()
        self.top = self.winfo_toplevel()
        try:
            self.top.geometry('1150x750+50+10')
            self.top.resizable(False, False)
        except tk.TclError:
            pass
        self._enter_binding = self.top.bind('<Return>', self.handle_enter_deal, add='+')
        self._escape_binding = self.top.bind('<Escape>', lambda _e: self.exit_game(), add='+')
        self._queue_animation(100, self.start_game)

    @property
    def current_bet(self):
        return self.bet_state.total_at_risk()

    @property
    def last_win(self):
        return self.last_win_amount

    def create_ui(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=self.BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_rectangle(0, 0, self.WIDTH, self.HEIGHT,
                                     fill=self.BG, outline='', tags='static')
        self.draw_history_panel()
        self._draw_table_labels()
        self.draw_board()
        self.draw_bottom_controls()
        self.canvas.bind('<Button-1>', self._handle_bead_click, add='+')

    def draw_board(self):
        self.canvas.create_rectangle(self.GAME_X0, 316, self.GAME_X1, 620,
                                     fill=self.FELT, outline=self.LINE, width=2, tags='static')
        rank_width = (self.BOARD_INNER_X1 - self.BOARD_INNER_X0) / len(ShootDragonGate.RANKS)
        for point, key in enumerate(ShootDragonGate.RANK_BETS, start=1):
            x0 = self.BOARD_INNER_X0 + (point - 1) * rank_width
            self.draw_bet_spot(key, x0, self.RANK_ROW_Y[0], x0 + rank_width, self.RANK_ROW_Y[1],
                               self._rank_hint_color(point, show_outcomes=False))
        rows = ShootDragonGate.MODE_ROWS[self.game_mode]
        bounds = (self.SUIT_ROW_Y, self.MISC_ROW_Y)
        for keys, (y0, y1) in zip(rows, bounds):
            width = (self.BOARD_INNER_X1 - self.BOARD_INNER_X0) / len(keys)
            for index, key in enumerate(keys):
                x0 = self.BOARD_INNER_X0 + index * width
                self.draw_bet_spot(key, x0, y0, x0 + width, y1,
                                   self.BET_COLORS[key], main=False)
        keys = ('shoot_射中', 'shoot_射偏', 'shoot_撞柱')
        width = (self.BOARD_INNER_X1 - self.BOARD_INNER_X0) / len(keys)
        for index, key in enumerate(keys):
            x0 = self.BOARD_INNER_X0 + index * width
            self.draw_bet_spot(key, x0, self.SHOOT_ROW_Y[0], x0 + width, self.SHOOT_ROW_Y[1],
                               self.BET_COLORS[key], main=True)

    @staticmethod
    def spot_tag(bet_type, _param=None):
        return 'spot_' + bet_type

    def draw_bet_spot(self, key, x0, y0, x1, y1, fill, main=False):
        tag = self.spot_tag(key)
        rect = self.canvas.create_rectangle(x0 + 2, y0 + 2, x1 - 2, y1 - 2,
                                            fill=fill, outline='#d5cbbd', width=1,
                                            tags=('board_dynamic', tag))
        middle_x, middle_y = (x0 + x1) / 2, (y0 + y1) / 2
        label = self.canvas.create_text(
            middle_x, middle_y - (14 if main else 12),
            text=ShootDragonGate.DISPLAY_NAMES[key],
            font=('Arial', 26 if main else 18, 'bold'), fill='white',
            tags=('board_dynamic', tag))
        odds = self.canvas.create_text(
            middle_x, middle_y + (18 if main else 14), text='',
            font=('Arial', 18 if main else 13, 'bold'), fill='white',
            tags=('board_dynamic', tag))
        self.bet_spots[(key, None)] = {
            'bounds': (x0 + 2, y0 + 2, x1 - 2, y1 - 2), 'tag': tag,
            'rect_id': rect, 'label_item': label, 'odds_item': odds,
            'fill': fill, 'fg': 'white', 'enabled': False, 'main': bool(main),
            'chip_pos': (middle_x, middle_y), 'chip_radius': 20,
        }
        self.canvas.tag_bind(tag, '<Button-1>', lambda _e, k=key: self.place_bet(k))
        self.canvas.tag_bind(tag, '<Button-3>', lambda _e, k=key: self.clear_single_bet(k))
        self.canvas.tag_bind(tag, '<Enter>', lambda _e: self.canvas.configure(cursor='hand2'))
        self.canvas.tag_bind(tag, '<Leave>', lambda _e: self.canvas.configure(cursor=''))

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
            1012, 628, 1138, 720, '开牌', self.handle_deal_action, '#d5ad4d',
            fg='#111', font_size=14, subtext='ENTER', subtext_font_size=10)
        c.tag_bind(self.clear_button, '<Button-3>', lambda _e: self.undo_last_bet())
        c.tag_bind(self.info_button, '<Button-3>', self.show_remaining_cards)
        c.tag_raise('controls')
        c.tag_raise('chip_selector')
        self.update_control_states()

    def update_control_states(self):
        betting = (self.phase == 'betting' and self.accept_bets and not self._closing
                   and not self.animation_running and not self.settlement_running)
        for attr in ('clear_button',):
            self.set_control_button_state(getattr(self, attr), betting and self.current_bet > 0)
        repeatable = any(self.engine.odds_by_bet().get(key) is not None
                         for key, _param, _amount in self.last_round_bets)
        self.set_control_button_state(self.repeat_button,
                                      betting and self.current_bet == 0 and repeatable)
        self.set_control_button_state(self.deal_button,
                                      not self._closing and self.phase in ('ready', 'betting'))
        text = {'ready': '发门柱牌', 'betting': '开第三张', 'dealing': '发牌中…',
                'revealing': '开牌中…', 'shooting': '射球中…', 'settling': '结算中…', 'paused': '已暂停',
                'closing': '已退出'}.get(self.phase, '发牌中…')
        self.canvas.itemconfigure(self.control_buttons[self.deal_button]['text'], text=text)
        odds = self.engine.odds_by_bet()
        for (key, _param), spot in self.bet_spots.items():
            available = betting and odds[key] is not None
            spot['enabled'] = available
            self.canvas.itemconfigure(spot['rect_id'],
                                      fill=spot['fill'] if available else self.shade_color(spot['fill'], 0.48),
                                      outline='#d5cbbd', width=1)
            for item in (spot['label_item'], spot['odds_item']):
                self.canvas.itemconfigure(item, fill=spot['fg'] if available else '#aaaaaa')
            odds_text = f'{odds[key]:g}:1' if odds[key] is not None else ('不可下注' if self.engine.diff is not None else '待门柱牌')
            self.canvas.itemconfigure(spot['odds_item'], text=odds_text)

    def bet_limit_for(self, bet_type):
        return 250000.0 if bet_type.startswith('shoot_') else 50000.0

    def place_bet(self, bet_type, amount=None, record_undo=True):
        if (self.phase != 'betting' or not self.accept_bets or self._closing
                or self.animation_running or self.settlement_running):
            return False
        if ((bet_type, None) not in self.bet_spots
                or self.engine.odds_by_bet().get(bet_type) is None):
            return False
        requested = float(self.selected_chip if amount is None else amount)
        if not math.isfinite(requested) or requested <= 0:
            return False
        current = self.bet_state.current_area_bet(bet_type)
        allowed = round(max(0.0, min(requested, self.bet_limit_for(bet_type) - current,
                                    self.balance)), 2)
        if allowed <= 0:
            messagebox.showwarning('下注限制', '余额不足或该区域已达到下注上限。',
                                   parent=self.winfo_toplevel())
            return False
        key = (bet_type, None)
        self.pending_bet_visual_amounts[key] = self.pending_bet_visual_amounts.get(key, 0.0) + allowed
        self.bet_state.add_bet(bet_type, allowed)
        self.balance = round(self.balance - allowed, 2)
        if record_undo:
            self.undo_stack.append((bet_type, None, allowed))
        self.summary_mode = 'bet'
        self.update_display()
        self._animate_amount_chip(
            allowed, self._chip_rack_source_position(), self.bet_spots[key]['chip_pos'],
            on_complete=lambda k=key, a=allowed: self._complete_pending_bet_visual(k, a),
            bet_key=key)
        self.save_balance()
        return True

    def clear_single_bet(self, bet_type, _param=None):
        if not self.accept_bets or self.phase != 'betting' or self._closing:
            return
        refunded = self.bet_state.clear_area(bet_type)
        if refunded <= 0:
            return
        self._cancel_chip_motions((bet_type, None))
        self.balance = round(self.balance + refunded, 2)
        self.summary_mode = 'bet'
        self.undo_stack = [item for item in self.undo_stack if item[0] != bet_type]
        self.update_display()
        self.save_balance()

    def undo_last_bet(self):
        if not self.accept_bets or self.phase != 'betting' or self._closing:
            return
        while self.undo_stack:
            key, _param, amount = self.undo_stack.pop()
            removed = self.bet_state.remove_amount(key, amount)
            if removed > 0:
                self._cancel_chip_motions((key, None))
                self.balance = round(self.balance + removed, 2)
                self.summary_mode = 'bet'
                self.update_display()
                self.save_balance()
                return

    def clear_bets(self):
        if not self.accept_bets or self.phase != 'betting' or self._closing:
            return
        refunded = self.bet_state.clear_all()
        if refunded <= 0:
            return
        self._cancel_chip_motions()
        self.balance = round(self.balance + refunded, 2)
        self.summary_mode = 'bet'
        self.undo_stack.clear()
        self.update_display()
        self.save_balance()

    reset_bets = clear_bets

    def snapshot_bets(self):
        return [(key, None, float(amount)) for key, amount in self.current_bets.items() if amount > 0]

    def repeat_last_bets(self):
        if self.phase != 'betting' or not self.accept_bets or self.current_bet > 0 or self._closing:
            return
        odds = self.engine.odds_by_bet()
        repeatable = [(key, amount) for key, _param, amount in self.last_round_bets
                      if odds.get(key) is not None]
        required = round(sum(amount for _key, amount in repeatable), 2)
        if required > self.balance:
            messagebox.showwarning('余额不足', f'重复下注需要 {self.format_money(required)}。',
                                   parent=self.winfo_toplevel())
            return
        for key, amount in repeatable:
            if not self.place_bet(key, amount=amount):
                break

    def update_display(self):
        self.canvas.itemconfigure(self.balance_text, text=f'余额: {self.format_money(self.balance)}')
        label = (f'上局获胜: {self.format_money(self.last_win_amount)}' if self.summary_mode == 'win'
                 else f'本局下注: {self.format_money(self.current_bet)}')
        self.canvas.itemconfigure(self.total_bet_text, text=label)
        self.update_bet_chips()
        self.update_history_table()
        self.update_control_states()

    def update_bet_chips(self):
        self.canvas.delete('bet_chip_dynamic')
        for key, spot in self.bet_spots.items():
            amount = self.bet_state.current_area_bet(key[0])
            if not self.settlement_running:
                amount = max(0.0, amount - self.pending_bet_visual_amounts.get(key, 0.0))
            # Keep tied winning wagers on the felt until finish_settlement().
            if self.settlement_running and key in self.settlement_hold_amounts:
                amount = self.settlement_hold_amounts[key]
            if key in self.flash_winner_amounts:
                if self.flash_mode == 'win':
                    amount = self.flash_winner_amounts[key]
                elif self.flash_mode == 'original':
                    amount = self.flash_original_amounts.get(key, amount)
            if amount <= 0:
                continue
            x0, y0, x1, y1 = spot['bounds']
            # All wager chips share the same size and centred position.
            x, y = spot['chip_pos']
            radius = spot['chip_radius']
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
        for value, color, _label in reversed(cls.CHIP_SPECS):
            if amount >= value:
                return color
        return cls.CHIP_SPECS[0][1]


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


    def _animate_amount_chip(self, amount, start_xy, target_xy, on_complete=None, bet_key=None):
        """Animate one compact chip from start_xy to target_xy in 0.2 seconds."""
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
        motion = {'key': bet_key, 'after_id': None}
        self.chip_motion_records[tag] = motion
        x, y = map(float, start_xy)
        tx, ty = map(float, target_xy)
        radius = 19.0
        chip_color = self.bet_chip_color(amount)
        text_color = self.contrast_text_color(chip_color)

        outer = self.canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill='#292522', outline='#151311', width=1,
            tags=(tag, 'chip_motion'))
        inner = self.canvas.create_oval(
            x - radius + 3, y - radius + 3, x + radius - 3, y + radius - 3,
            fill=chip_color, outline='#e2ddd5', width=1,
            tags=(tag, 'chip_motion'))
        text = self.canvas.create_text(
            x, y, text=self._compact_amount(amount),
            font=('Arial', 9, 'bold'), fill=text_color,
            tags=(tag, 'chip_motion'))
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
            if self._closing or tag not in self.chip_motion_records:
                return
            ratio = min(1.0, max(0.0, step / steps))
            eased = ratio * ratio * (3.0 - 2.0 * ratio)
            cx = x + (tx - x) * eased
            cy = y + (ty - y) * eased
            if not place_items(cx, cy):
                return
            if step >= steps:
                self.chip_motion_records.pop(tag, None)
                try:
                    self.canvas.delete(tag)
                except tk.TclError:
                    pass
                if callable(on_complete):
                    on_complete()
                return
            motion['after_id'] = self._schedule_chip_motion(frame_ms, lambda: frame(step + 1))

        place_items(x, y)
        motion['after_id'] = self._schedule_chip_motion(frame_ms, lambda: frame(1))
        return tag


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


    def _cancel_chip_motions(self, key=None):
        """Clear pending visual copies without changing the booked wagers."""
        for tag, motion in list(self.chip_motion_records.items()):
            if key is not None and motion['key'] != key:
                continue
            token = motion['after_id']
            if token is not None:
                try:
                    self.after_cancel(token)
                except (tk.TclError, ValueError):
                    pass
                self.chip_motion_after_ids.discard(token)
            self.canvas.delete(tag)
            self.chip_motion_records.pop(tag, None)
        if key is None:
            self.pending_bet_visual_amounts.clear()
        else:
            self.pending_bet_visual_amounts.pop(key, None)

    def handle_enter_deal(self, _event=None):
        button = self.control_buttons.get(self.deal_button)
        if button and button['enabled']:
            button['command']()
        return 'break'

    def handle_deal_action(self):
        if self.phase == 'ready':
            self.start_game()
        elif self.phase == 'betting':
            self.reveal_third_card()

    def start_game(self):
        if self._closing or self.phase != 'ready':
            return
        self.phase = 'dealing'
        self._cancel_chip_motions()
        self.accept_bets = self.betting_enabled = False
        self.animation_running = True
        self._round_settled = False
        self.pre_deal_bets = self.current_result = None
        self._temp_flip_images.clear()
        self.clear_card_display()
        self.update_display()
        try:
            self.engine.start_round()
            self.engine.deal_first_two()
        except Exception as exc:
            self._pause_game('无法发门柱牌', exc)
            return
        self.current_shoot_odds = dict(zip(ShootDragonGate.RESULTS, self.engine.get_odds_for_shoot()))
        self._animate_card_entrance(None, self._get_card_positions(0),
                                    card=self.engine.first_card,
                                    on_complete=lambda: self._animate_card_entrance(
                                        None, self._get_card_positions(1), card=self.engine.second_card,
                                        on_complete=self.enable_betting_phase))

    def enable_betting_phase(self):
        if self._closing or self.phase != 'dealing':
            return
        self.phase = 'betting'
        self.accept_bets = self.betting_enabled = True
        self.animation_running = False
        self.update_rank_bet_colors()
        self.update_display()

    def reveal_third_card(self):
        if self._closing or self.phase != 'betting' or not self.accept_bets:
            return
        self.phase = 'revealing'
        self._cancel_chip_motions()
        self.accept_bets = self.betting_enabled = False
        self.animation_running = True
        self.pre_deal_bets = copy.deepcopy(self.current_bets)
        self.last_round_bets = self.snapshot_bets()
        self.undo_stack.clear()
        self.update_display()
        try:
            self.current_result = self.engine.reveal_third_card()
        except Exception as exc:
            self._pause_game('无法开第三张', exc)
            return
        self._animate_card_entrance(None, self._get_card_positions(2),
                                    card=self.engine.third_card,
                                    on_complete=lambda: self._queue_animation(250, self._play_shot_animation))

    def _animate_card_entrance(self, card_id, target_pos, card=None, on_complete=None):
        if card_id is None:
            if self.back_image is None:
                self._draw_card_fallback(target_pos, None, face_up=False)
                self._queue_animation(300, self._flip_card, None, card, on_complete)
                return
            card_id = self.table_canvas.create_image(self.TABLE_WIDTH / 2, -80, image=self.back_image,
                                                      tags='playing_card')
        def move_step(step=0):
            ratio = min(1.0, step / 30.0)
            self.table_canvas.coords(card_id, self.TABLE_WIDTH / 2 + (target_pos[0] - self.TABLE_WIDTH / 2) * ratio,
                                      -80 + (target_pos[1] + 80) * ratio)
            if step < 30:
                self._queue_animation(10, move_step, step + 1)
            elif card is not None:
                self._flip_card(card_id, card, on_complete)
            elif callable(on_complete):
                on_complete()
        move_step()

    def _flip_card(self, card_id, card, on_complete=None, step=0):
        if card is None:
            return
        if card_id is None:
            index = (2 if self.phase == 'revealing' else
                     (0 if card is self.engine.first_card else 1))
            self._draw_card_fallback(self._get_card_positions(index), card, face_up=True)
            self.table_canvas.itemconfigure(self.card_score_texts[index], text=card[1])
            if callable(on_complete):
                on_complete()
            return
        if step > 12:
            self.table_canvas.itemconfigure(card_id, image=self.card_images[tuple(card)])
            index = (2 if self.phase == 'revealing' else
                     (0 if card is self.engine.first_card else 1))
            self.table_canvas.itemconfigure(self.card_score_texts[index], text=card[1])
            self._temp_flip_images.pop(card_id, None)
            if callable(on_complete):
                on_complete()
            return
        use_back = step <= 6
        ratio = 1 - step / 6.0 if use_back else (step - 6) / 6.0
        image = self._create_scaled_image(card, max(1, int(self.CARD_SIZE[0] * ratio)),
                                           self.CARD_SIZE[1], use_back)
        self._temp_flip_images[card_id] = image
        self.table_canvas.itemconfigure(card_id, image=image)
        self._queue_animation(20, self._flip_card, card_id, card, on_complete, step + 1)

    def _create_scaled_image(self, card, width, height, use_back=False):
        base = self.back_pil if use_back else self.card_pil[tuple(card)]
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        return ImageTk.PhotoImage(base.resize((max(1, int(width)), int(height)), resample), master=self)

    def _apply_round_settlement(self):
        if self._round_settled or self.engine.third_card is None:
            return None
        result = self.current_result or self.engine.round_result()
        bets = self.pre_deal_bets if self.pre_deal_bets is not None else self.current_bets
        settled = ShootDragonGate.resolve_bets(bets, result)
        self.balance = round(self.balance + settled['credit'], 2)
        self.last_win_amount, self.last_net = settled['credit'], settled['net']
        self.current_bets.clear()
        self._round_settled = True
        self.summary_mode = 'win'
        self.add_history(result)
        self.save_balance()
        return settled

    def resolve_bets(self):
        if self._closing or self._round_settled:
            return
        settled = self._apply_round_settlement()
        if settled is None or self.phase == 'paused':
            return
        self.phase = 'settling'
        self.animation_running = False
        self.settlement_running = True
        self.flash_winning_keys = {key for key, factor in settled['side_factors'].items() if factor > 1}
        self.flash_winning_keys = {(key, None) for key in self.flash_winning_keys}
        self.flash_winner_amounts = {tuple(item['key']): item['return_amount']
                                     for item in settled['outcomes'] if item['return_factor'] > 1}
        self.flash_original_amounts = {tuple(item['key']): item['stake']
                                       for item in settled['outcomes'] if item['return_factor'] > 1}
        self.update_display()
        self.run_settlement_flash(0)

    def run_settlement_flash(self, step=0):
        if self._closing or not self.settlement_running:
            return
        if step >= 6:
            self.finish_settlement()
            return
        light = step % 2 == 0
        self.flash_mode = 'win' if light else 'original'
        for key in self.flash_winning_keys:
            spot = self.bet_spots[key]
            self.canvas.itemconfigure(spot['rect_id'], fill='#ffffff' if light else spot['fill'],
                                      outline='#111111' if light else '#d5cbbd',
                                      width=2 if light else 1)
            for item in (spot['label_item'], spot['odds_item']):
                self.canvas.itemconfigure(item, fill='#111111' if light else spot['fg'])
        self.update_bet_chips()
        self._queue_animation(450, self.run_settlement_flash, step + 1)

    def finish_settlement(self):
        try:
            self.engine.finish_round()
        except Exception as exc:
            self._pause_game('本局牌张归还失败', exc)
            return
        self.settlement_running = False
        self.flash_mode = None
        self.flash_winning_keys.clear()
        self.flash_winner_amounts.clear()
        self.flash_original_amounts.clear()
        self.pre_deal_bets = None
        self.restore_table_colors()
        self.phase = 'ready'
        self.update_display()
        self._queue_animation(700, self.start_game)

    def _pause_game(self, action, exc):
        self.cancel_pending_callbacks()
        self.phase = 'paused'
        self.accept_bets = self.betting_enabled = False
        self.animation_running = self.settlement_running = False
        self.update_display()
        messagebox.showerror('射龙门', f'{action}：{exc}', parent=self.winfo_toplevel())

    def _queue_animation(self, delay, callback, *args):
        if self._closing:
            return None
        token = [None]
        def invoke():
            self.animation_after_ids.discard(token[0])
            if not self._closing:
                callback(*args)
        token[0] = self.after(delay, invoke)
        self.animation_after_ids.add(token[0])
        return token[0]

    def cancel_pending_callbacks(self):
        for after_id in list(self.animation_after_ids):
            try:
                self.after_cancel(after_id)
            except (tk.TclError, ValueError):
                pass
        self.animation_after_ids.clear()
        self._cancel_chip_motions()

    def _draw_table_labels(self):
        x0, y0, x1, y1 = self.GAME_X0, 4, self.GAME_X1, 310
        self.animation_panel = (x0, y0, x1, y1)
        self.canvas.create_rectangle(x0, y0, x1, y1, fill=self.FELT,
                                      outline=self.LINE, width=2, tags='static')
        # One clipped playfield keeps the legacy goal and ball above the
        # betting rows while cards enter from outside the visible table.
        self.table_canvas = tk.Canvas(self.canvas, width=self.TABLE_WIDTH,
                                      height=self.TABLE_HEIGHT, bg=self.FELT,
                                      highlightthickness=0, borderwidth=0)
        self.table_window = self.canvas.create_window(
            x0 + 2, y0 + 2, anchor='nw', window=self.table_canvas,
            width=self.TABLE_WIDTH, height=self.TABLE_HEIGHT, tags='animation')
        c = self.table_canvas
        left, top = self._scene_point((240, 45))
        right, bottom = self._scene_point((760, 350))
        self.draw_soccer_net(c, left=left, right=right, top=top, bottom=bottom)
        self.card_score_texts = []
        labels = ('第一张 · 左门柱', '第二张 · 右门柱', '第三张 · 射球牌')
        for index, label in enumerate(labels):
            cx, _cy = self._get_card_positions(index)
            c.create_text(cx, 20, text=label, font=('Arial', 11, 'bold'),
                          fill=self.GOLD, tags='animation')
            score = c.create_text(cx, 234, text='—', font=('Arial', 13, 'bold'),
                                  fill='white', tags='animation')
            self.card_score_texts.append(score)

    @classmethod
    def _scene_point(cls, point):
        """Map the original 1000x400 goal scene into the DTP-sized playfield."""
        return (point[0] * cls.TABLE_WIDTH / 1000,
                point[1] * cls.TABLE_HEIGHT / 400)

    @classmethod
    def _scene_length(cls, length):
        return length * min(cls.TABLE_WIDTH / 1000, cls.TABLE_HEIGHT / 400)

    @classmethod
    def _get_card_positions(cls, card_index):
        # The original two gatepost cards flank the third card in the centre.
        return cls._scene_point(((270, 200), (730, 200), (500, 200))[card_index])

    _normalize_card = staticmethod(ShootDragonGate.normalize_card)

    def _load_assets(self):
        if Image is None or ImageTk is None:
            return
        directory = self.find_original_card_asset_dir()
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        for suit in ShootDragonGate.SUITS:
            for rank in ShootDragonGate.RANKS:
                card = (suit, rank)
                path = os.path.join(directory, f'{suit}{rank}.png') if directory else None
                try:
                    if path is None:
                        raise FileNotFoundError
                    with Image.open(path) as image:
                        base = image.convert('RGBA').resize(self.CARD_SIZE, resample)
                except (OSError, ValueError):
                    base = self._make_fallback_card_pil(card).resize(self.CARD_SIZE, resample)
                self.card_pil[card] = base
                self.card_images[card] = ImageTk.PhotoImage(base, master=self)
        try:
            if directory is None:
                raise FileNotFoundError
            with Image.open(os.path.join(directory, 'Background.png')) as image:
                self.back_pil = image.convert('RGBA').resize(self.CARD_SIZE, resample)
        except (OSError, ValueError):
            self.back_pil = self._make_fallback_card_pil(None, face_up=False).resize(self.CARD_SIZE, resample)
        self.back_image = ImageTk.PhotoImage(self.back_pil, master=self)

    def find_original_card_asset_dir(self):
        candidates = [os.path.join(os.path.dirname(_THIS_DIR), 'A_Tools', 'Card', 'Poker1'),
                      os.path.join(_PROJECT_ROOT, 'A_Tools', 'Card', 'Poker1'),
                      os.path.join(_THIS_DIR, 'A_Tools', 'Card', 'Poker1')]
        return next((directory for directory in candidates if os.path.isdir(directory)), None)

    def _draw_card_fallback(self, position, card, face_up=True):
        x, y = position
        tag = f'fallback_card_{int(x)}_{int(y)}'
        c = self.table_canvas
        c.delete(tag)
        w, h = self.CARD_SIZE
        c.create_rectangle(x - w / 2, y - h / 2, x + w / 2, y + h / 2,
                           fill='#f4efe4' if face_up else '#253e66',
                           outline=self.GOLD, width=2, tags=(tag, 'playing_card'))
        if face_up:
            suit, rank = card
            symbol = {'Club': '♣', 'Diamond': '♦', 'Heart': '♥', 'Spade': '♠'}[suit]
            color = '#c22631' if suit in ('Diamond', 'Heart') else '#111111'
            c.create_text(x, y, text=f'{rank}\n{symbol}', font=('Arial', 28, 'bold'),
                          fill=color, tags=(tag, 'playing_card'))
        else:
            c.create_text(x, y, text='SP', font=('Arial', 26, 'bold'),
                          fill=self.GOLD, tags=(tag, 'playing_card'))

    def draw_history_panel(self):
        c = self.canvas
        x0, x1 = self.HISTORY_X0, self.HISTORY_X1
        c.create_rectangle(x0, 4, x1, 620, fill=self.PANEL,
                           outline=self.PANEL_LINE, width=2, tags='static')
        c.create_text((x0 + x1) / 2, 20, text='历史记录',
                      font=('Arial', 15, 'bold'), fill='#d4c3a9', tags='static')
        self.history_panel_bounds = (x0, 4, x1, 620)
        panel_x0, panel_x1 = 786, 1130
        panel_w = panel_x1 - panel_x0
        big_cell = panel_w / self.big_road_view_cols
        self.road_geometries = {'big': (panel_x0, 42, big_cell, 6, self.big_road_view_cols)}
        self._draw_road_grid(*self.road_geometries['big'])
        self._draw_big_road_scrollbar(panel_x0, 42 + 6 * big_cell + 5, panel_w)
        bead_x0 = panel_x0 + (panel_w - 12 * 27) / 2
        self.road_geometries['bead'] = (bead_x0, 218, 27, 6, 12)
        self._draw_road_grid(*self.road_geometries['bead'])
        self.history_chart_geometry = {'winner': (panel_x0, 392, panel_x1, 610)}
        c.create_rectangle(panel_x0, 392, panel_x1, 610, fill='#15110f',
                           outline='#7c6754', width=1, tags='history_panel_content')

    @classmethod
    def result_color(cls, winner):
        return cls.RESULT_COLORS.get(winner, '#888888')

    def _draw_bead_plate(self, records):
        x0, y0, cell, rows, cols = self.road_geometries['bead']
        for index, record in enumerate(records[-rows * cols:]):
            cx, cy = x0 + (index // rows + 0.5) * cell, y0 + (index % rows + 0.5) * cell
            radius = cell * 0.39
            color = self.result_color(record['winner'])
            self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                    fill=color, outline='white', tags='history_dynamic')
            text = str(record['third_score']) if self.bead_show_scores else {'射中': '中', '射偏': '偏', '撞柱': '柱'}[record['winner']]
            self.canvas.create_text(cx, cy, text=text, font=('Arial', 11, 'bold'),
                                    fill=self.contrast_text_color(color), tags='history_dynamic')

    def _build_big_road(self, records):
        return self._place_road_sequence([(record['winner'], record) for record in records])

    def _draw_big_road(self, cells):
        x0, y0, size, _rows, view_cols = self.road_geometries['big']
        max_col = max((item['col'] for item in cells), default=0)
        base = max(0, max_col - self.big_road_virtual_cols + 1)
        if self.big_road_auto_follow:
            self.big_road_scroll_col = max(0, max_col - base - view_cols + 1)
        self.big_road_scroll_col = min(max(0, self.big_road_scroll_col),
                                      self.big_road_virtual_cols - view_cols)
        self._update_big_road_scroll_thumb()
        for item in cells:
            col = item['col'] - base - self.big_road_scroll_col
            if not 0 <= col < view_cols:
                continue
            cx, cy = x0 + (col + 0.5) * size, y0 + (item['row'] + 0.5) * size
            radius = size * 0.37
            self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                    outline=self.result_color(item['value']), width=2,
                                    tags='history_dynamic')

    def update_history_table(self):
        self.canvas.delete('history_dynamic')
        self._draw_big_road(self._build_big_road(self.history_data))
        self._draw_bead_plate(self.last_72_data)
        counts = {key: 0 for key in ShootDragonGate.RESULTS}
        for record in self.history_data:
            counts[record['winner']] += 1
        self._draw_pie_chart(self.history_chart_geometry['winner'], '过去300局出现百分比',
                              [(key, counts[key], self.result_color(key)) for key in counts])

    def get_runtime_json_dir(self):
        target = os.path.join(_PROJECT_ROOT, 'A_Logs', 'Json')
        os.makedirs(target, exist_ok=True)
        return target

    @staticmethod
    def new_history_store():
        return {'records': []}

    @staticmethod
    def _default_statistic_data():
        return {'total_game': 0, 'shoot_win': 0, 'miss_win': 0, 'pillar_win': 0}

    @classmethod
    def new_runtime_store(cls):
        return {'temp_finish_data': cls.new_history_store(),
                'last_72_record': cls.new_history_store(),
                'statistic_data': cls._default_statistic_data()}

    @classmethod
    def normalize_history_store(cls, data):
        output = cls.new_history_store()
        raw = data.get('records', []) if isinstance(data, dict) else []
        if not isinstance(raw, list):
            return output
        for record in raw:
            if not isinstance(record, dict) or record.get('winner') not in ShootDragonGate.RESULTS:
                continue
            try:
                first, second, third = (int(record[key]) for key in
                                        ('first_score', 'second_score', 'third_score'))
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            if not all(1 <= value <= 13 for value in (first, second, third)):
                continue
            if record['winner'] != ShootDragonGate.result_for_values(first, second, third):
                continue
            item = copy.deepcopy(record)
            item.update(first_score=first, second_score=second, third_score=third,
                        diff=abs(first - second))
            output['records'].append(item)
        output['records'] = output['records'][-cls.MAX_RECORDS:]
        return output

    def load_runtime_store(self):
        store = self.new_runtime_store()
        self._last_72_missing = True
        try:
            with open(self.runtime_data_file, 'r', encoding='utf-8') as handle:
                raw = json.load(handle)
            if isinstance(raw, dict):
                self._last_72_missing = not isinstance(raw.get('last_72_record'), dict)
                for key in store:
                    if isinstance(raw.get(key), dict):
                        store[key] = raw[key]
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        return store

    def load_last_72_store(self):
        if self._last_72_missing:
            return {'records': copy.deepcopy(self.history_data[-self.BEAD_MAX_RECORDS:])}
        store = self.normalize_history_store(self.runtime_store['last_72_record'])
        while len(store['records']) > self.BEAD_MAX_RECORDS:
            del store['records'][:self.HISTORY_DROP_COUNT]
        return store

    def load_statistic_data(self):
        defaults = self._default_statistic_data()
        raw = self.runtime_store['statistic_data']
        for key in ('shoot_win', 'miss_win', 'pillar_win'):
            try:
                defaults[key] = max(0, int(raw.get(key, 0)))
            except (TypeError, ValueError, OverflowError):
                pass
        defaults['total_game'] = sum(defaults[key] for key in ('shoot_win', 'miss_win', 'pillar_win'))
        return defaults

    def add_history(self, result):
        record = copy.deepcopy(result)
        record['time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for key in ('first_card', 'second_card', 'third_card'):
            record[key] = list(record[key])
        self.history_store['records'].append(record)
        self.history_store['records'] = self.history_store['records'][-self.MAX_RECORDS:]
        self.last_72_store['records'].append(copy.deepcopy(record))
        while len(self.last_72_store['records']) > self.BEAD_MAX_RECORDS:
            del self.last_72_store['records'][:self.HISTORY_DROP_COUNT]
        key = {'射中': 'shoot_win', '射偏': 'miss_win', '撞柱': 'pillar_win'}[record['winner']]
        self.statistic_data[key] += 1
        self.statistic_data['total_game'] += 1
        self.history_data = list(self.history_store['records'])
        self.last_72_data = list(self.last_72_store['records'])
        self.big_road_auto_follow = True
        self.runtime_store = {'temp_finish_data': self.history_store,
                              'last_72_record': self.last_72_store,
                              'statistic_data': self.statistic_data}
        self._write_runtime_store()

    def save_balance(self):
        try:
            if self.username:
                update_balance_in_json(self.username, self.balance)
            if callable(self.on_balance_change):
                self.on_balance_change(float(self.balance))
        except Exception as exc:
            if not self._closing:
                self._pause_game('余额保存失败', exc)
            else:
                messagebox.showerror('余额保存失败', str(exc), parent=self.winfo_toplevel())
            return False
        return True

    def update_balance(self):
        self.update_display()
        self.save_balance()

    def show_remaining_cards(self, _event=None):
        try:
            count = self.engine.remaining_cards()
            leased = len(self.engine.card_buffer)
        except Exception as exc:
            messagebox.showerror('自动洗牌机', str(exc), parent=self.winfo_toplevel())
            return
        messagebox.showinfo('自动洗牌机',
                            f'本游戏当前仓剩余 {leased} 张。\n洗牌机当前可用总数 {count} 张。\n牌张由 CSM 持续管理，每局结束后归还。',
                            parent=self.winfo_toplevel())

    def show_game_instructions(self):
        """Game rules dialog with the Baccarat instruction layout."""
        parent = self.winfo_toplevel()
        existing = getattr(self, '_intro_window', None)
        try:
            if existing is not None and existing.winfo_exists():
                existing.lift()
                existing.focus_force()
                return
        except tk.TclError:
            pass

        dialog = tk.Toplevel(parent)
        self._intro_window = dialog
        engine = ShootDragonGate
        mode = self.game_mode
        mode_title = engine.MODE_NAMES.get(mode, mode)
        odds_rows = []
        for diff, values in engine.ODDS_TABLE.items():
            values = ['—' if value is None else f'{value:g}' for value in values]
            odds_rows.append((f'门柱点数差 {diff}', ' / '.join(values)))
        info = {
            'title': '射龙门', 'subtitle': '玩法 · 下注区 · 赔率 · 限红 · 历史记录',
            'intro': [
                ('两阶段发牌', '先翻开第一张和第二张门柱牌；玩家下注后，按 Enter 开第三张。'),
                ('胜负判定', '第三张点数在两张门柱之间为射中；等于任一门柱为撞柱；其余为射偏。'),
                ('第三张点数下注', 'A–K 每格独立预测第三张的点数，押中净赢 11 倍并退回本金；例如下注 $100，押中共返还 $1,200。'),
            ],
            'main_classic': odds_rows,
            'specials': [
                ('流动赔率', '射击赔率由前两张门柱牌的点数差决定；每局以桌面显示的赔率结算。'),
                ('不可下注', '点数差 0 或 1 时无法射中；点数差 12 时无法射偏。相应区域自动停用。'),
                ('退出结算', '第三张尚未开出时退出退回下注；第三张已经开出时退出完成本局结算。'),
            ],
            'history': [
                ('右侧记录', '右侧显示大路、珠盘路，以及射中／射偏／撞柱三项占比饼图。'),
                ('珠盘容量', '独立保留 72 局；超过时按整列移除最旧 6 局。单击珠盘可切换结果文字与第三张点数。'),
                ('统计范围', '历史记录最多保留最近 300 局；大路下方可拖动滚动条。'),
            ],
            'extra': [
                ('点数顺序', 'A=1、J=11、Q=12、K=13；花色不影响射中／射偏／撞柱的判定。'),
                ('判定例子', '2 / K / 7 → 射中；2 / K / K → 撞柱；5 / 8 / 2 → 射偏。'),
                ('连续洗牌机', '与龙虎凤使用相同的 CSM 牌仓机制；每局结束后归还牌张。'),
            ],
            'main_bets': ('shoot_射中', 'shoot_射偏', 'shoot_撞柱'),
        }
        dialog.title(f"{info['title']} · 游戏说明 · {mode_title}")
        dialog.configure(bg='#0a1414')
        dialog.resizable(False, False)
        dialog.transient(parent)
        win_w, win_h = 1000, 650
        parent.update_idletasks()
        pos_x = parent.winfo_rootx() + (max(1, parent.winfo_width()) - win_w) // 2
        pos_y = parent.winfo_rooty() + (max(1, parent.winfo_height()) - win_h) // 2
        dialog.geometry(f'{win_w}x{win_h}+{pos_x}+{pos_y}')
        font_name = getattr(self, 'cn_font', 'Microsoft YaHei UI')
        bg, sidebar_bg, panel, border = '#0a1414', '#0e1a1a', '#132020', '#3d5a55'
        gold, fg, muted = '#f0d48b', '#eef4f4', '#a8bdbd'

        header = tk.Frame(dialog, bg='#0f1c1c', height=82)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text=f"{info['title']}  {mode_title}", bg='#0f1c1c',
                 fg=gold, font=(font_name, 20, 'bold')).place(x=24, y=10)
        tk.Label(header, text=info['subtitle'], bg='#0f1c1c', fg=muted,
                 font=(font_name, 14)).place(x=25, y=48)
        close_btn = tk.Button(header, text='关闭  ESC', font=(font_name, 14, 'bold'),
                              bg='#2a3330', fg=fg, activebackground='#3a4644',
                              activeforeground='white', relief=tk.FLAT, bd=0,
                              cursor='hand2')
        close_btn.place(x=850, y=20, width=120, height=42)
        tk.Frame(dialog, bg=gold, height=3).pack(fill=tk.X)

        body = tk.Frame(dialog, bg=bg)
        body.pack(fill=tk.BOTH, expand=True)
        sidebar = tk.Frame(body, bg=sidebar_bg, width=220)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        tk.Frame(body, bg=border, width=1).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(sidebar, text='主题', bg=sidebar_bg, fg=gold,
                 font=(font_name, 14, 'bold'), anchor='w').pack(fill=tk.X, padx=16, pady=(18, 10))

        wrap = tk.Frame(body, bg=bg)
        wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        canvas = tk.Canvas(wrap, bg=bg, highlightthickness=0, bd=0, yscrollincrement=40)
        bar = tk.Scrollbar(wrap, orient=tk.VERTICAL, command=canvas.yview,
                           bg='#1f2a29', troughcolor='#0d1515', activebackground=gold,
                           relief=tk.FLAT, bd=0, width=12)
        canvas.configure(yscrollcommand=bar.set)
        canvas.grid(row=0, column=0, sticky='nsew', padx=(0, 4), pady=6)
        bar.grid(row=0, column=1, sticky='ns', padx=(0, 8), pady=6)
        content = tk.Frame(canvas, bg=bg)
        content_id = canvas.create_window((0, 0), window=content, anchor='nw')
        content.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(content_id, width=e.width))

        def wheel(event):
            delta = getattr(event, 'delta', 0)
            units = -int(delta / 120) if delta else (1 if event.num == 5 else -1)
            if units:
                canvas.yview_scroll(units, 'units')
            return 'break'

        for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            dialog.bind(sequence, wheel)

        def title(text, note=''):
            row = tk.Frame(content, bg=bg)
            row.pack(fill=tk.X, padx=24, pady=(14, 0))
            tk.Label(row, text=text, bg=bg, fg=gold,
                     font=(font_name, 18, 'bold')).pack(side=tk.LEFT)
            if note:
                tk.Label(row, text=note, bg=bg, fg=muted,
                         font=(font_name, 12)).pack(side=tk.RIGHT)
            tk.Frame(content, bg=border, height=1).pack(fill=tk.X, padx=24, pady=(10, 16))

        def card(heading):
            block = tk.Frame(content, bg=panel, highlightbackground=border,
                             highlightthickness=1)
            block.pack(fill=tk.X, padx=24, pady=(0, 16))
            tk.Label(block, text=heading, bg=panel, fg=gold,
                     font=(font_name, 16, 'bold'), anchor='w').pack(
                         fill=tk.X, padx=22, pady=(16, 10))
            return block

        def rule(block, heading, description):
            line = tk.Frame(block, bg=panel)
            line.pack(fill=tk.X, padx=22, pady=(0, 14))
            tk.Frame(line, bg=gold, width=4).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 16))
            text_box = tk.Frame(line, bg=panel)
            text_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(text_box, text=heading, bg=panel, fg=fg, anchor='w',
                     font=(font_name, 15, 'bold')).pack(fill=tk.X)
            tk.Label(text_box, text=description, bg=panel, fg=muted,
                     anchor='w', justify=tk.LEFT, wraplength=630,
                     font=(font_name, 14)).pack(fill=tk.X, pady=(5, 0))

        def table(block, heading, rows):
            grid = tk.Frame(block, bg='#1a2a2a', highlightbackground='#2b3d3d',
                            highlightthickness=1)
            grid.pack(fill=tk.X, padx=16, pady=(4, 16))
            tk.Label(grid, text=heading, bg=gold, fg='#111111', anchor='w',
                     font=(font_name, 14, 'bold'), padx=16, pady=8).pack(fill=tk.X)
            cells = tk.Frame(grid, bg='#1a2a2a')
            cells.pack(fill=tk.X)
            cells.grid_columnconfigure(0, weight=1)
            cells.grid_columnconfigure(1, minsize=165)
            for i, (label, value) in enumerate(rows):
                shade = '#162424' if i % 2 == 0 else '#1a2a2a'
                tk.Label(cells, text=label, bg=shade, fg=fg, anchor='w',
                         font=(font_name, 14), padx=18, pady=10).grid(
                             row=i, column=0, sticky='nsew', padx=(0, 1), pady=(0, 1))
                tk.Label(cells, text=value, bg=shade, fg=gold,
                         font=(font_name, 14, 'bold'), padx=8, pady=10).grid(
                             row=i, column=1, sticky='nsew', pady=(0, 1))

        def page_rules():
            title('玩法与胜负规则', 'A < 2 < … < 10 < J < Q < K')
            block = card('基本流程')
            for heading, desc in info['intro']:
                rule(block, heading, desc)
            block = card('牌面与附加条件')
            for heading, desc in info['extra'][:2]:
                rule(block, heading, desc)

        def page_board():
            title('下注区示意', '读取当前模式的真实下注区与赔率')
            block = card('下注位置')
            board = tk.Canvas(block, width=680, height=352, bg=panel, highlightthickness=0)
            board.pack(padx=12, pady=(4, 16))
            board.create_rectangle(6, 6, 674, 346, fill='#0e3d3d', outline='#3d6a68', width=2)
            board.create_text(24, 28, anchor='w', text=f'{mode_title} · 下注区',
                              font=(font_name, 14, 'bold'), fill=fg)
            rows = engine.MODE_ROWS.get(mode, ())
            odds = self._instruction_odds_text()

            def band(keys, y0, y1, widths=None):
                if not keys:
                    return
                left, right = 22, 658
                fractions = widths or [1.0 / len(keys)] * len(keys)
                cursor = left
                for i, key in enumerate(keys):
                    end = right if i == len(keys) - 1 else cursor + (right-left) * fractions[i]
                    colour = self.bet_spots.get((key, None), {}).get(
                        'fill', self.BET_COLORS.get(key, '#45665c'))
                    board.create_rectangle(cursor+2, y0+2, end-2, y1-2,
                                           fill=colour, outline='#d5cbbd')
                    label = engine.DISPLAY_NAMES.get(key, key)
                    board.create_text((cursor+end)/2, y0+24, text=label,
                                      font=(font_name, 12, 'bold'), fill='white')
                    board.create_text((cursor+end)/2, y1-17, text=odds.get(key, ''),
                                      font=(font_name, 11, 'bold'), fill='#f6e6b8')
                    cursor = end

            band(engine.RANK_BETS, 44, 114)
            if rows:
                band(rows[0], 118, 182)
            if len(rows) > 1:
                band(rows[1], 186, 250)
            band(info['main_bets'], 254, 336)
            block = card('操作')
            for heading, desc in (
                ('A–K 点数下注', '顶部每格押第三张点数，赔率均为 11:1；蓝／红／黄分别提示撞柱／射中／射偏。花色行在点数下注下方、红黑与大小下注上方。'),
                ('左键下注', '点击下注区投入当前选中的筹码。'),
                ('右键清除', '右键点击下注区，退还该区域尚未开牌的下注。'),
                ('清除 / 重复 / 开牌', '底部按钮可清除本局、重复上局下注或开牌；右键清除按钮可撤销最近一笔。Enter 也可开牌。'),
            ):
                rule(block, heading, desc)

        def page_main():
            title('射击赔率', '净利润赔率；— 表示不可下注；返还另含本金')
            block = card('门柱点数差与赔率')
            table(block, '点数差 · 射中 / 射偏 / 撞柱', info['main_classic'])
            block = card('判定示例')
            rule(block, '例子', info['extra'][1][1])

        def page_side():
            title('边注赔率表', f'{mode_title} · 以实际下注区为准')
            odds = self._instruction_odds_text()
            main = set(info['main_bets'])
            table(card('第三张点数下注'), '预测点数 · 净利润赔率', [
                (engine.DISPLAY_NAMES[key], odds[key]) for key in engine.RANK_BETS
            ])
            rule(card('点数下注赔付'), '押中返还', '净赢 11 倍，另退本金；押 $100 中了共返还 $1,200。每格只看第三张点数，不受花色或射击结果影响。')
            for group_name, keys in zip(('花色下注', '红黑／大小下注'), engine.MODE_ROWS.get(mode, ())):
                selected = [(engine.DISPLAY_NAMES.get(key, key), odds.get(key, ''))
                            for key in keys if key not in main]
                if selected:
                    table(card(group_name), '下注条件 · 净利润赔率', selected)

        def page_limits():
            title('下注限制与操作', '以各区域下注上限为准')
            table(card('限红'), '下注区 · 上限', [
                ('筹码', '100 / 500 / 1K / 5K\n10K / 30K / 50K'),
                ('每个点数／花色／红黑／大小区域', '$50,000'),
                ('每个射击区域', '$250,000'),
            ])
            block = card('下注操作')
            for heading, desc in (
                ('筹码与调整', '使用与龙虎凤相同的七种筹码。超出余额或限红时，系统自动调整到可下注金额。'),
                ('筹码移动', '点击下注区后，筹码从底部选中的筹码位置飞入该区域；落下后显示该区域累计下注。'),
                ('清除 / 撤销', '开牌前可右键清除单区下注；清除按钮左键退回本局下注，右键撤销最近一笔。'),
                ('重复下注', '重复上局注额，仍受当前余额及限红限制；本局不可能出现的射击结果会被跳过。'),
                ('开牌', '点击开牌或按 Enter；结算后自动发下一局的门柱牌。'),
                ('金额显示', '下注、撤销或清除后显示本局下注；结算后显示上局获胜。新的下注操作会替换上局获胜显示。'),
            ):
                rule(block, heading, desc)

        def page_history():
            title('历史记录说明', '右侧面板')
            block = card('道路与数据')
            for heading, desc in info['history']:
                rule(block, heading, desc)

        def page_notes():
            title('重要提示', mode_title)
            block = card('结算与机器')
            for heading, desc in info['specials'] + info['extra'][2:]:
                rule(block, heading, desc)

        themes = (
            ('玩法与胜负规则', page_rules), ('下注区示意', page_board),
            ('主注赔率', page_main), ('边注赔率表', page_side),
            ('下注限制与操作', page_limits), ('历史记录说明', page_history),
            ('重要提示', page_notes),
        )
        buttons = {}
        current = [None]

        def select_theme(name):
            if current[0] == name:
                return
            current[0] = name
            for key, button in buttons.items():
                active = key == name
                button.configure(bg='#1e3433' if active else sidebar_bg,
                                 fg=gold if active else muted)
            for child in content.winfo_children():
                child.destroy()
            for key, builder in themes:
                if key == name:
                    builder()
                    break
            canvas.update_idletasks()
            canvas.yview_moveto(0)

        for name, _builder in themes:
            button = tk.Button(sidebar, text=name, command=lambda n=name: select_theme(n),
                               font=(font_name, 14), fg=muted, bg=sidebar_bg,
                               activebackground='#24403e', activeforeground=gold,
                               relief=tk.FLAT, bd=0, anchor='w', padx=20, pady=12,
                               cursor='hand2')
            button.pack(fill=tk.X)
            buttons[name] = button
        select_theme(themes[0][0])

        def close():
            self._intro_window = None
            try:
                dialog.destroy()
            except tk.TclError:
                pass

        close_btn.configure(command=close)
        dialog.protocol('WM_DELETE_WINDOW', close)
        dialog.bind('<Escape>', lambda _event: close())
        dialog.after(30, dialog.focus_force)

    def exit_game(self):
        if self._closing:
            return self.final_balance
        self._closing = True
        self.cancel_pending_callbacks()
        self.phase = 'closing'
        self.accept_bets = self.betting_enabled = False
        self.animation_running = self.settlement_running = False
        if self.engine.third_card is not None and not self._round_settled:
            self._apply_round_settlement()
        else:
            self.balance = round(self.balance + self.bet_state.clear_all(), 2)
        try:
            self.engine.close()
        except Exception as exc:
            messagebox.showerror('自动洗牌机', f'退出时归还牌张失败：{exc}', parent=self.winfo_toplevel())
        for sequence, binding in (('<Return>', self._enter_binding), ('<Escape>', self._escape_binding)):
            if binding:
                try:
                    self.top.unbind(sequence, binding)
                except tk.TclError:
                    pass
        intro = getattr(self, '_intro_window', None)
        if intro is not None:
            try:
                intro.destroy()
            except tk.TclError:
                pass
            self._intro_window = None
        self.final_balance = float(self.balance)
        self.save_balance()
        if callable(self.on_back):
            self.on_back(self.final_balance)
        else:
            self.destroy()
        return self.final_balance

    on_close = exit_game


    # Reused DTP Canvas controls, card artwork and history helpers.

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

    def select_chip(self, amount):
        self.selected_chip = float(amount)
        for value, items in self.chip_selector_items.items():
            outer, _inner, _text = items
            selected = float(value) == float(amount)
            self.canvas.itemconfigure(outer,
                                      outline='#ffda42' if selected else '#6d6259',
                                      width=5 if selected else 3)
        self.canvas.tag_raise('chip_selector')

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
        if amount >= 1000:
            value = amount / 1000
            return f'{value:.0f}K' if abs(value - round(value)) < 0.01 else f'{value:.1f}K'
        return str(int(round(amount))) if abs(amount - round(amount)) < 0.01 else f'{amount:.1f}'

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
                # A new Dragon/Tiger (or red/blue derived-road) streak starts
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

    def _draw_pie_chart(self, bounds, title, items):
        c = self.canvas
        x0, y0, x1, y1 = bounds
        c.create_text((x0 + x1) / 2, y0 + 18, text=title,
                      font=('Arial', 13, 'bold'), fill='#f2eadf',
                      tags='history_dynamic')
        height = y1 - y0
        radius = min(62, max(38, (height - 52) / 2))
        cx = x0 + 78
        cy = (y0 + y1) / 2 + 10
        bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
        total = sum(max(0, int(value)) for _label, value, _color in items)
        if total <= 0:
            c.create_oval(*bbox, fill='#302a25', outline='#75695d', width=2,
                          tags='history_dynamic')
            c.create_text(cx, cy, text='0', font=('Arial', 18, 'bold'),
                          fill='#8f857b', tags='history_dynamic')
        else:
            start = 90.0
            for label, value, color in items:
                value = max(0, int(value))
                if not value:
                    continue
                extent = 360.0 * value / total
                c.create_arc(*bbox, start=start, extent=-extent, fill=color,
                             outline='#15110f', width=2, style=tk.PIESLICE,
                             tags='history_dynamic')
                middle = math.radians(start - extent / 2.0)
                label_radius = radius * (0.70 if extent < 38 else 0.55)
                label_x = cx + math.cos(middle) * label_radius
                label_y = cy - math.sin(middle) * label_radius
                c.create_text(
                    label_x, label_y, text=label,
                    font=('Arial', 9 if extent < 38 else 12, 'bold'),
                    fill=self.contrast_text_color(color),
                    tags='history_dynamic')
                start -= extent

        legend_x = x0 + 166
        row_gap = min(35, max(25, (height - 52) / max(1, len(items))))
        legend_y = y0 + 48
        for index, (label, value, color) in enumerate(items):
            y = legend_y + index * row_gap
            c.create_rectangle(legend_x, y - 6, legend_x + 13, y + 7,
                               fill=color, outline='#e5ddd3', width=1,
                               tags='history_dynamic')
            percentage = (100.0 * int(value) / total) if total else 0.0
            c.create_text(legend_x + 22, y, anchor='w',
                          text=f'{label}  {int(value)}次  {percentage:.1f}%',
                          font=('Arial', 14, 'bold'), fill='#e9e1d8',
                          tags='history_dynamic')

    def _write_runtime_store(self):
        """Write both history stores safely, including the Windows fallback."""
        temp_path = None
        try:
            self.runtime_store = {
                'temp_finish_data': copy.deepcopy(
                    self.runtime_store.get('temp_finish_data', self.new_history_store())),
                'last_72_record': copy.deepcopy(
                    self.runtime_store.get('last_72_record', self.new_history_store())),
                'statistic_data': dict(
                    self.runtime_store.get('statistic_data', self._default_statistic_data())),
            }
            payload = json.dumps(self.runtime_store, ensure_ascii=False, indent=4)
            directory = os.path.dirname(self.runtime_data_file)
            os.makedirs(directory, exist_ok=True)
            descriptor, temp_path = tempfile.mkstemp(
                prefix=os.path.basename(self.runtime_data_file) + '.',
                suffix='.tmp', dir=directory)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())

            replace_error = None
            for attempt in range(6):
                try:
                    os.replace(temp_path, self.runtime_data_file)
                    temp_path = None
                    replace_error = None
                    break
                except OSError as exc:
                    replace_error = exc
                    if getattr(exc, 'winerror', None) != 5 and not isinstance(exc, PermissionError):
                        raise
                    time.sleep(0.05 * (attempt + 1))

            if replace_error is not None:
                # Windows can deny replacement while still allowing the already
                # existing file to be updated. This fallback avoids the repeated
                # WinError 5 loop caused by os.replace().
                with open(self.runtime_data_file, 'w', encoding='utf-8') as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
            self._last_runtime_save_error = None
            return True
        except OSError as exc:
            message = f'{type(exc).__name__}: {exc}'
            if message != getattr(self, '_last_runtime_save_error', None):
                print(f'保存 Shoot_Poker 失败：{exc}')
                self._last_runtime_save_error = message
            return False
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass


    def _rank_hint_color(self, point, show_outcomes=True):
        if (not show_outcomes or self.engine.first_card is None
                or self.engine.second_card is None):
            return '#435850'
        first = self.engine.card_value(self.engine.first_card)
        second = self.engine.card_value(self.engine.second_card)
        low, high = min(first, second), max(first, second)
        winner = ('撞柱' if point in (first, second) else
                  ('射中' if low < point < high else '射偏'))
        return self.BET_COLORS[f'shoot_{winner}']

    def update_rank_bet_colors(self, show_outcomes=True):
        for point, key in enumerate(ShootDragonGate.RANK_BETS, start=1):
            spot = self.bet_spots[(key, None)]
            color = self._rank_hint_color(point, show_outcomes=show_outcomes)
            spot['fill'] = color
            self.canvas.itemconfigure(spot['rect_id'],
                                      fill=color if spot['enabled'] else self.shade_color(color, 0.48))
            for item in (spot['label_item'], spot['odds_item']):
                self.canvas.itemconfigure(item, fill=spot['fg'] if spot['enabled'] else '#aaaaaa')

    def clear_card_display(self):
        self.table_canvas.delete('playing_card')
        self.table_canvas.delete('shot_ball')
        self._temp_flip_images.clear()
        self.restore_table_colors()
        for text_id in self.card_score_texts:
            self.table_canvas.itemconfigure(text_id, text='—')
        self.update_rank_bet_colors(show_outcomes=False)

    def restore_table_colors(self):
        for text_id in self.card_score_texts:
            self.table_canvas.itemconfigure(text_id, fill='white')

    def _instruction_odds_text(self):
        odds = dict(ShootDragonGate.ODDS_TEXT[self.game_mode])
        if self.engine.diff is not None:
            for key, value in self.engine.odds_by_bet().items():
                odds[key] = '不可下注' if value is None else f'{value:g}:1'
        return odds

    def show_help_window(self):
        self.show_game_instructions()


    def draw_soccer_net(self, canvas, left=240, right=760, top=45, bottom=350):
        """在指定canvas上绘制3D足球门网，位置限定在(left, top)-(right, bottom)区域内"""
        # 清除旧网格（使用标签方便管理）
        canvas.delete('soccer_net')

        # ---------- 原始3D坐标定义（与tt.py完全一致） ----------
        # 前框 (z = 40)
        flt = (60, 75, 40)
        frt = (196, 75, 40)
        flb = (60, 176, 40)
        frb = (196, 176, 40)
        # 后框 (z = 0)
        blt = (40, 55, 0)
        brt = (216, 55, 0)
        blb = (40, 156, 0)
        brb = (216, 156, 0)

        # ---------- 辅助函数：原始tp映射 + 线性缩放到目标矩形 ----------
        # 原始tp: (x, -y+200)   (根据tt.py中的transform+project)
        def orig_tp(p):
            x, y, z = p
            return (x, -y + 200)

        # 计算原始坐标的范围（通过经验值）
        # 原始x范围: 40~216, 原始y范围(经过tp后): y_min=24, y_max=145
        orig_x_min, orig_x_max = 40, 216
        orig_y_min, orig_y_max = 24, 145
        target_x_min, target_x_max = left, right
        target_y_min, target_y_max = top, bottom

        def map_point(p):
            ox, oy = orig_tp(p)
            nx = target_x_min + (ox - orig_x_min) / (orig_x_max - orig_x_min) * (target_x_max - target_x_min)
            ny = target_y_min + (oy - orig_y_min) / (orig_y_max - orig_y_min) * (target_y_max - target_y_min)
            return (nx, ny)

        def draw_line(p1, p2, **kwargs):
            x1, y1 = map_point(p1)
            x2, y2 = map_point(p2)
            canvas.create_line(x1, y1, x2, y2, tags='soccer_net', **kwargs)

        def draw_polygon(points, **kwargs):
            pts = []
            for p in points:
                x, y = map_point(p)
                pts.extend([x, y])
            # 只画轮廓，不填充（避免覆盖原有背景）
            canvas.create_polygon(pts, tags='soccer_net', outline=kwargs.get('outline', 'white'),
                                  fill='', width=kwargs.get('width', 1))

        # ---------- 绘制门框（白色粗线） ----------
        edges = [
            (flt, frt), (flt, flb), (frt, frb), (flb, frb),
            (flt, blt), (frt, brt), (flb, blb), (frb, brb),
            (blb, brb), (blt, blb), (brt, brb),
        ]
        for e in edges:
            draw_line(e[0], e[1], fill="white", width=3)

        # ---------- 网格辅助函数 ----------
        def grid(p1, p2, p3, p4, cols, rows):
            for i in range(1, cols):
                t = i / cols
                a = (
                    p1[0] + (p2[0] - p1[0]) * t,
                    p1[1] + (p2[1] - p1[1]) * t,
                    p1[2] + (p2[2] - p1[2]) * t,
                )
                b = (
                    p4[0] + (p3[0] - p4[0]) * t,
                    p4[1] + (p3[1] - p4[1]) * t,
                    p4[2] + (p3[2] - p4[2]) * t,
                )
                draw_line(a, b, fill="#c8ffd0", width=1)

            for i in range(1, rows):
                t = i / rows
                a = (
                    p1[0] + (p4[0] - p1[0]) * t,
                    p1[1] + (p4[1] - p1[1]) * t,
                    p1[2] + (p4[2] - p1[2]) * t,
                )
                b = (
                    p2[0] + (p3[0] - p2[0]) * t,
                    p2[1] + (p3[1] - p2[1]) * t,
                    p2[2] + (p3[2] - p2[2]) * t,
                )
                draw_line(a, b, fill="#c8ffd0", width=1)

        # 绘制四个面的网格（前、左、右、底）
        grid(flt, frt, frb, flb, 18, 10)   # 前
        grid(flt, blt, blb, flb, 6, 10)    # 左
        grid(brt, frt, frb, brb, 6, 10)    # 右
        grid(flb, frb, brb, blb, 18, 6)    # 底

        # 将网格置于底层（不影响后续卡片等元素）
        canvas.tag_lower('soccer_net')


    def _build_shot_plan(self):
        """Keep the original shot paths and scale their coordinates together."""
        original = self._build_original_shot_plan()
        return {key: (value if key == 'kind' else self._scene_point(value))
                for key, value in original.items()}


    def _build_original_shot_plan(self):
        """
        根据前三张牌，决定足球的射门路径。
        射偏时：根据第三张牌大于高牌或小于低牌，决定飞向高牌或低牌所在侧的外侧。
        """
        v1 = self.game.card_value(self.game.first_card)
        v2 = self.game.card_value(self.game.second_card)
        v3 = self.game.card_value(self.game.third_card)

        low = min(v1, v2)
        high = max(v1, v2)

        # 第一张牌的位置 x=270，第二张牌的位置 x=730
        left_pos_x = 270
        right_pos_x = 730

        # 判断 low 和 high 分别对应哪一张牌
        low_is_left = (v1 == low)
        high_is_left = (v1 == high)

        start = (500, 385)
        approach_ctrl = (500, 155)

        # 1) 射中：第三张在两者之间
        if low < v3 < high:
            t = (v3 - low) / float(high - low) if high != low else 0.5
            target_x = int(320 + 360 * t)   # 320~680
            target_y = int(205 - 35 * (1 - abs(2 * t - 1)))
            return {
                "kind": "hit",
                "start": start,
                "control": approach_ctrl,
                "end": (target_x, target_y),
            }

        # 2) 撞柱：第三张等于其中一张
        if v3 == v1 or v3 == v2:
            match_is_left = (left_pos_x if v3 == v1 else right_pos_x) < 500
            impact_x = 248 if match_is_left else 752
            impact_y = int(105 + ((v3 - 1) / 12.0) * 150)
            bounce_end_x = 185 if match_is_left else 815
            bounce_end_y = max(85, impact_y - 25)
            bounce_ctrl_x = impact_x - 55 if match_is_left else impact_x + 55
            bounce_ctrl_y = impact_y - 60
            return {
                "kind": "pillar",
                "start": start,
                "control": approach_ctrl,
                "impact": (impact_x, impact_y),
                "bounce_control": (bounce_ctrl_x, bounce_ctrl_y),
                "bounce_end": (bounce_end_x, bounce_end_y),
            }

        # 3) 射偏
        # 根据 v3 与 low/high 的关系决定飞向哪一侧
        if v3 > high:
            # 大于高牌：飞向高牌所在侧的外侧
            if high_is_left:
                # 高牌在左边，球飞向左侧外部
                side = "left"
            else:
                # 高牌在右边，球飞向右侧外部
                side = "right"
        else:  # v3 < low
            # 小于低牌：飞向低牌所在侧的外侧
            if low_is_left:
                side = "left"
            else:
                side = "right"

        # 确定落点坐标范围
        if side == "left":
            # 左侧外部范围 x: 40~250，y 根据 v3 点数映射
            end_x = random.randint(140, 200)
        else:
            # 右侧外部范围 x: 750~900
            end_x = random.randint(800, 860)

        # y 坐标随点数变化（点数越小越靠上，点数越大越靠下）
        end_y = int(75 + ((v3 - 1) / 12.0) * 195)

        return {
            "kind": "miss",
            "start": start,
            "control": approach_ctrl,
            "end": (end_x, end_y),
        }


    def _draw_soccer_ball(self, cx, cy, r, tag='shot_ball', with_shadow=False):
        """
        绘制足球，with_shadow 参数保留用于其他场景，下落动画中阴影由单独方法控制。
        """
        c = self.table_canvas

        if with_shadow:
            # 简单阴影（保留兼容，但当前不使用）
            shadow_w = r * 1.9
            shadow_h = max(3, r * 0.32)
            c.create_oval(
                cx - shadow_w / 2, cy + r * 0.65,
                cx + shadow_w / 2, cy + r * 0.65 + shadow_h,
                fill='#123b18', outline='', tags=tag
            )

        # 球体主色
        c.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill='#F0F0F0', outline='#111111',
            width=max(1, int(r * 0.1)), tags=tag
        )
        # 左下暗部增加立体感
        c.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            start=180, extent=180, fill='#DDDDDD', outline='', tags=tag
        )

        # 黑色五边形风格
        pts_center = [
            cx, cy - r * 0.42,
            cx + r * 0.38, cy - r * 0.12,
            cx + r * 0.22, cy + r * 0.34,
            cx - r * 0.22, cy + r * 0.34,
            cx - r * 0.38, cy - r * 0.12,
        ]
        c.create_polygon(pts_center, fill='#111111', outline='#333333', width=1, tags=tag)

        c.create_polygon(
            cx - r * 0.72, cy - r * 0.04,
            cx - r * 0.47, cy - r * 0.28,
            cx - r * 0.31, cy - r * 0.02,
            cx - r * 0.45, cy + r * 0.28,
            fill='#111111', outline='#333333', width=1, tags=tag
        )
        c.create_polygon(
            cx + r * 0.72, cy - r * 0.04,
            cx + r * 0.47, cy - r * 0.28,
            cx + r * 0.31, cy - r * 0.02,
            cx + r * 0.45, cy + r * 0.28,
            fill='#111111', outline='#333333', width=1, tags=tag
        )
        c.create_polygon(
            cx, cy + r * 0.72,
            cx + r * 0.25, cy + r * 0.50,
            cx + r * 0.12, cy + r * 0.22,
            cx - r * 0.12, cy + r * 0.22,
            cx - r * 0.25, cy + r * 0.50,
            fill='#111111', outline='#333333', width=1, tags=tag
        )

        # 缝线
        line_width = max(1, int(r * 0.06))
        c.create_line(cx, cy - r * 0.42, cx, cy + r * 0.22,
                      fill='#555555', width=line_width, tags=tag)
        c.create_line(cx - r * 0.35, cy - r * 0.18, cx + r * 0.35, cy - r * 0.18,
                      fill='#555555', width=line_width, tags=tag)
        c.create_line(cx - r * 0.22, cy + r * 0.20, cx + r * 0.22, cy + r * 0.20,
                      fill='#555555', width=line_width, tags=tag)

        # 高光
        highlight_r = r * 0.32
        c.create_oval(
            cx - r * 0.45, cy - r * 0.45,
            cx - r * 0.45 + highlight_r, cy - r * 0.45 + highlight_r,
            fill='#FFFFFF', outline='', tags=tag
        )
        c.create_oval(
            cx - r * 0.58, cy - r * 0.58,
            cx - r * 0.58 + highlight_r * 0.5, cy - r * 0.58 + highlight_r * 0.5,
            fill='#FFFFFF', outline='', tags=tag
        )


    def _play_shot_animation(self):
        """
        第三张牌翻开后播放足球射门动画，射门结束后下落，下落完成后结算。
        """
        if self._closing or self.phase != 'revealing' or self.engine.third_card is None:
            return
        self.phase = 'shooting'
        self.update_control_states()
        self.table_canvas.delete('shot_ball')
        plan = self._build_shot_plan()

        if plan["kind"] == "pillar":
            # 撞柱：先飞向门柱，再弹出，最后下落
            def after_bounce(end_x, end_y, final_r):
                # 弹出动画结束，开始下落
                self._drop_ball_and_settle(end_x, end_y, final_r, self.resolve_bets)

            def do_bounce():
                self._animate_shot_phase(
                    plan["impact"],
                    plan["bounce_control"],
                    plan["bounce_end"],
                    frames=12,
                    start_r=25,
                    end_r=25,
                    on_done=after_bounce
                )

            self._animate_shot_phase(
                plan["start"],
                plan["control"],
                plan["impact"],
                frames=16,
                start_r=60,
                end_r=25,
                on_done=lambda x, y, r: do_bounce()
            )
        else:
            # 射中 / 射偏：直接飞向目标点，然后下落
            def after_shot(end_x, end_y, final_r):
                self._drop_ball_and_settle(end_x, end_y, final_r, self.resolve_bets)

            self._animate_shot_phase(
                plan["start"],
                plan["control"],
                plan["end"],
                frames=22,
                start_r=60,
                end_r=25,
                on_done=after_shot
            )


    def _animate_shot_phase(self, start, control, end, frames=22, start_r=60, end_r=25, on_done=None):
        """
        二次贝塞尔曲线动画，足球半径从 start_r 线性变化到 end_r。
        动画结束时调用 on_done(终点x, 终点y, 最终半径)
        """
        canvas = self.table_canvas
        start_r, end_r = self._scene_length(start_r), self._scene_length(end_r)

        def step(i=0):
            t = i / float(frames)
            inv = 1.0 - t

            x = inv * inv * start[0] + 2 * inv * t * control[0] + t * t * end[0]
            y = inv * inv * start[1] + 2 * inv * t * control[1] + t * t * end[1]

            r = max(self._scene_length(25), start_r + (end_r - start_r) * t)

            canvas.delete('shot_ball')
            # 飞行阶段不画阴影（避免空中阴影）
            self._draw_soccer_ball(x, y, r, tag='shot_ball', with_shadow=False)

            if i < frames:
                self._queue_animation(20, step, i + 1)
            else:
                if on_done:
                    on_done(end[0], end[1], r)

        step()


    def _drop_ball_and_settle(self, x, y, r, on_complete):
        """
        足球从当前位置 (x, y) 垂直下落至按旧版 y=325 缩放的落地点，同时阴影从小变大。
        下落完成后足球停留在落地位置，然后调用 on_complete。
        """
        canvas = self.table_canvas
        target_y = self._scene_point((0, 325))[1]
        frames = 15
        start_y = y
        start_shadow_scale = 0.2   # 阴影初始很小
        end_shadow_scale = 1.5     # 落地时阴影较大

        def step(i=0):
            t = i / float(frames)
            current_y = start_y + (target_y - start_y) * t
            shadow_scale = start_shadow_scale + (end_shadow_scale - start_shadow_scale) * t
            shadow_w = r * 1.8 * shadow_scale
            shadow_h = max(3, r * 0.32 * shadow_scale)

            canvas.delete('shot_ball')
            # 画阴影（在足球下方）
            shadow_x = x
            shadow_y = current_y + r * 0.65
            canvas.create_oval(
                shadow_x - shadow_w / 2, shadow_y,
                shadow_x + shadow_w / 2, shadow_y + shadow_h,
                fill='#123b18', outline='', tags='shot_ball'
            )
            # 画足球（不带阴影，阴影已单独绘制）
            self._draw_soccer_ball(x, current_y, r, tag='shot_ball', with_shadow=False)

            if i < frames:
                self._queue_animation(20, step, i + 1)
            else:
                # 下落完成，足球停留在当前位置，不要删除
                if on_complete:
                    on_complete()

        step()


class ShootDragonGateGUI(tk.Tk):
    """Keep the original standalone constructor and balance attribute."""

    def __init__(self, initial_balance=1000000, username='Guest',
                 on_back=None, on_balance_change=None):
        super().__init__()
        self.title('射龙门 Shoot Poker')
        self.geometry('1150x750+50+10')
        self.resizable(False, False)
        def finish(final_balance):
            try:
                if callable(on_back):
                    on_back(final_balance)
            finally:
                self.destroy()
        try:
            self.game_frame = BubbleShootPokerGame(self, balance=initial_balance, user=username,
                                                   on_back=finish,
                                                   on_balance_change=on_balance_change)
        except Exception:
            self.destroy()
            raise
        self.game_frame.pack(fill=tk.BOTH, expand=True)
        self.protocol('WM_DELETE_WINDOW', self.on_close)

    @property
    def balance(self):
        return self.game_frame.balance

    @balance.setter
    def balance(self, value):
        self.game_frame.balance = round(float(value), 2)

    def on_close(self):
        return self.game_frame.exit_game()


class ShootPokerGame(BubbleShootPokerGame):
    def __init__(self, root, username='Guest', initial_balance=1000000,
                 on_back=None, on_balance_change=None, game_mode='shootdragon'):
        super().__init__(root, balance=initial_balance, user=username, on_back=on_back,
                         on_balance_change=on_balance_change, game_mode=game_mode)
        self.pack(fill=tk.BOTH, expand=True)


ShootPokerEngine = ShootDragonGate


def main(parent=None, balance=1000000, user=None, on_back=None,
         on_balance_change=None, username=None, game_mode='shootdragon',
         initial_balance=None):
    """Use the DTP parent-first interface; keep original standalone calls.

    Embedded (does not create Tk or start another mainloop):
        game = main(parent=parent_frame, balance=10000, user='name', on_back=callback)
        game.pack(fill='both', expand=True)

    Original standalone calls still return the final numeric balance:
        main(10000, 'name')
        main(initial_balance=10000, username='name')
    """
    if username is not None and user is None:
        user = username
    if parent is not None and not isinstance(parent, tk.Misc):
        legacy_balance = parent
        legacy_user = balance if isinstance(balance, str) and user is None else user
        parent = None
        balance = legacy_balance
        user = legacy_user
    if initial_balance is not None:
        balance = initial_balance
    if parent is not None:
        return BubbleShootPokerGame(parent, balance=balance, user=user, on_back=on_back,
                                    on_balance_change=on_balance_change, game_mode=game_mode)
    app = ShootDragonGateGUI(balance, user, on_back=on_back,
                              on_balance_change=on_balance_change)
    app.mainloop()
    return app.balance


if __name__ == '__main__':
    print(f'Final balance: {main():.2f}')
