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

import copy
import json
import os
import random
import re
import sys
import tempfile
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

# Project layout (same CSM discovery strategy as Blackjack_Classic.py):
#   A_Tools/Card/CSM_Shuffler.py
#   A_Tools/Casino_Games/Dragon_Tiger.py
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_CSM_CANDIDATES = [
    os.path.abspath(os.path.join(_THIS_DIR, '..', 'A_Tools', 'Card')),
    os.path.abspath(os.path.join(_THIS_DIR, '..', 'Card')),
    _THIS_DIR,
]
_CARD_TOOLS_DIR = next((p for p in _CSM_CANDIDATES
                        if os.path.isfile(os.path.join(p, 'CSM_Shuffler.py'))), None)
if _CARD_TOOLS_DIR is None:
    raise ModuleNotFoundError('找不到 CSM_Shuffler.py，已檢查：' + '; '.join(_CSM_CANDIDATES))
if _CARD_TOOLS_DIR not in sys.path:
    sys.path.insert(0, _CARD_TOOLS_DIR)

from CSM_Shuffler import CSMError, ContinuousShuffleMachine  # type: ignore

DRAGON_TIGER_VERSION = 'V25-CSM-R7-DUAL-HISTORY'

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
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../A_Tools/Account/saving_data.json')


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
# Dragon/Tiger rules / CSM / bet settlement
# -----------------------------------------------------------------------------
class DragonTigerEngine:
    SUITS = ('Club', 'Diamond', 'Heart', 'Spade')
    RANKS = ('A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K')
    RED_SUITS = {'Diamond', 'Heart'}
    BLACK_SUITS = {'Club', 'Spade'}

    MODE_NAMES = {
        'classic': '经典龙虎',
        'treasure': '聚宝盆龙虎',
    }

    DISPLAY_NAMES = {
        'Dragon': '龙',
        'Tie': '和局',
        'Tiger': '虎',
        'Both Red': '双方红色',
        'Red Black': '红黑各一',
        'Both Black': '双方黑色',
        'Small': '小(A-9)',
        'Perfect Suited Tie': '完美同花',
        'Big': '大(10-K)',
    }

    ODDS_TEXT = {
        'classic': {
            'Both Red': '2.9:1', 'Red Black': '0.95:1', 'Both Black': '2.9:1',
            'Small': '1:1', 'Perfect Suited Tie': '50:1', 'Big': '0.9:1',
            'Dragon': '1:1*', 'Tie': '10:1', 'Tiger': '1:1*',
        },
        'treasure': {
            'Both Red': '2:1', 'Red Black': '0.75:1', 'Both Black': '2:1',
            'Small': '0.75:1', 'Perfect Suited Tie': '30:1', 'Big': '0.55:1',
            'Dragon': '1:1*', 'Tie': '8:1', 'Tiger': '1:1*',
        },
    }

    MODE_ROWS = {
        'classic': (
            ('Both Red', 'Red Black', 'Both Black'),
            ('Small', 'Perfect Suited Tie', 'Big'),
        ),
        'treasure': (
            ('Both Red', 'Red Black', 'Both Black'),
            ('Small', 'Perfect Suited Tie', 'Big'),
        ),
    }

    # Treasure Pot first chooses which golden condition(s) are active this round.
    # Suit only 34%, rank only 44%, both suit + rank 22%.
    TREASURE_CONDITION_TYPES = ('suit', 'rank', 'both')
    TREASURE_CONDITION_WEIGHTS = (34, 44, 22)

    # Active suit/rank conditions then use their own independent multiplier pools.
    # Suit: 2X 60%, 3X 30%, 4X 10%.
    TREASURE_SUIT_MULTIPLIER_VALUES = (2, 3, 4)
    TREASURE_SUIT_MULTIPLIER_WEIGHTS = (60, 30, 10)
    # Rank: 2X 40%, 3X 30%, 4X 20%, 5X 7%, 8X 3%.
    TREASURE_RANK_MULTIPLIER_VALUES = (2, 3, 4, 5, 8)
    TREASURE_RANK_MULTIPLIER_WEIGHTS = (40, 30, 20, 7, 3)

    def __init__(self, csm, game_id):
        self.decks = 8
        self.csm = csm
        self.game_id = str(game_id)
        self.card_buffer = []
        self.current_batch_id = None
        self.used_by_batch = {}
        self.round_open = False
        self.round_id = None

    def _clear_local_csm_state(self):
        self.round_id = None
        self.round_open = False
        self.card_buffer = []
        self.current_batch_id = None
        self.used_by_batch = {}

    def start_round(self):
        if self.round_open:
            raise RuntimeError('上一局尚未结束。')
        try:
            self.round_id = self.csm.begin_round(
                self.game_id, self.current_batch_id if self.card_buffer else None)
            self.used_by_batch = {}
            self.round_open = True
            if not self.card_buffer:
                self._request_next_chamber()
        except Exception:
            # CSM may already have rebuilt all warehouses after the primary error.
            # Drop every local lease/round reference so stale IDs are never reused.
            self._clear_local_csm_state()
            raise

    def _request_next_chamber(self):
        packet = self.csm.acquire_chamber(self.game_id, self.round_id)
        self.current_batch_id = packet['batch_id']
        self.card_buffer = list(packet['cards'])
        if not self.card_buffer:
            raise CSMError('自动洗牌机返回了空仓。')

    def remaining_cards(self):
        return len(self.card_buffer) + self.csm.available_cards()

    def needs_shuffle(self):
        return False

    @classmethod
    def rank_value(cls, card):
        rank = card[1]
        if rank == 'A':
            return 1
        if rank == 'J':
            return 11
        if rank == 'Q':
            return 12
        if rank == 'K':
            return 13
        return int(rank)

    @classmethod
    def card_value(cls, card):
        """Compatibility helper for the inherited cut/burn animation code.

        Dragon-Tiger compares full card ranks (A=1 ... K=13), so this simply
        aliases rank_value().  The burn routine clamps face cards to 10.
        """
        return cls.rank_value(card)

    @classmethod
    def score(cls, hand):
        return cls.rank_value(hand[0]) if hand else 0

    @classmethod
    def rank_label(cls, value):
        value = int(value)
        return {1: 'A', 11: 'J', 12: 'Q', 13: 'K'}.get(value, str(value))

    def draw_card(self):
        if not self.round_open:
            raise RuntimeError('牌局尚未开始。')
        if len(self.card_buffer) <= 3:
            self._request_next_chamber()
        record = self.card_buffer.pop(0)
        self.used_by_batch.setdefault(self.current_batch_id, []).append(record['card_id'])
        return record['suit'], record['rank']

    def deal_round(self):
        if not self.round_open:
            raise RuntimeError('牌局尚未开始。')
        dragon = [self.draw_card()]
        tiger = [self.draw_card()]
        dragon_score = self.score(dragon)
        tiger_score = self.score(tiger)
        if dragon_score > tiger_score:
            winner = 'Dragon'
        elif tiger_score > dragon_score:
            winner = 'Tiger'
        else:
            winner = 'Tie'
        return {
            'dragon_hand': dragon,
            'tiger_hand': tiger,
            'dragon_score': dragon_score,
            'tiger_score': tiger_score,
            'winner': winner,
            'natural': False,
            'reshuffled': False,
            'shoe_remaining': self.remaining_cards(),
        }

    def finish_round(self):
        if not self.round_open:
            return
        rid = self.round_id
        try:
            for batch_id in list(self.used_by_batch):
                card_ids = self.used_by_batch[batch_id]
                if card_ids:
                    self.csm.return_cards(self.game_id, batch_id, card_ids)
                del self.used_by_batch[batch_id]
        except Exception:
            # Do not call end_round with a round ID that may have been erased by
            # CSM automatic recovery; preserve the primary error instead.
            self._clear_local_csm_state()
            raise
        try:
            self.csm.end_round(self.game_id, rid)
        finally:
            self.round_id = None
            self.round_open = False

    def close(self):
        try:
            self.csm.release_game(self.game_id, force_shuffle=True)
        except Exception:
            # Closing must never resurrect or reuse stale CSM identifiers.
            pass
        finally:
            self._clear_local_csm_state()

    @classmethod
    def result_rank(cls, result):
        winner = result.get('winner')
        if winner == 'Dragon':
            return int(result.get('dragon_score', 0))
        if winner == 'Tiger':
            return int(result.get('tiger_score', 0))
        return int(result.get('dragon_score', result.get('tiger_score', 0)))

    @classmethod
    def side_return_factors(cls, result, mode, current_bets=None):
        del current_bets
        if mode not in ('classic', 'treasure'):
            mode = 'classic'
        dragon = result['dragon_hand'][0]
        tiger = result['tiger_hand'][0]
        ds = int(result['dragon_score'])
        ts = int(result['tiger_score'])
        result_rank = cls.result_rank(result)
        d_red = dragon[0] in cls.RED_SUITS
        t_red = tiger[0] in cls.RED_SUITS
        factors = {}

        color_profit = {
            'classic': {'Both Red': 2.9, 'Red Black': 0.95, 'Both Black': 2.9},
            'treasure': {'Both Red': 2.0, 'Red Black': 0.75, 'Both Black': 2.0},
        }[mode]
        range_profit = {
            'classic': {'Small': 1.0, 'Perfect Suited Tie': 50.0, 'Big': 0.9},
            'treasure': {'Small': 0.75, 'Perfect Suited Tie': 30.0, 'Big': 0.55},
        }[mode]

        if d_red and t_red:
            factors['Both Red'] = 1.0 + color_profit['Both Red']
        elif d_red != t_red:
            factors['Red Black'] = 1.0 + color_profit['Red Black']
        else:
            factors['Both Black'] = 1.0 + color_profit['Both Black']

        if 1 <= result_rank <= 9:
            factors['Small'] = 1.0 + range_profit['Small']
        if ds == ts and dragon[0] == tiger[0]:
            factors['Perfect Suited Tie'] = 1.0 + range_profit['Perfect Suited Tie']
        if 10 <= result_rank <= 13:
            factors['Big'] = 1.0 + range_profit['Big']
        return factors

    @staticmethod
    def _treasure_bonus(result):
        bonus = result.get('_treasure_bonus', {}) if isinstance(result, dict) else {}
        return bonus if isinstance(bonus, dict) else {}

    @classmethod
    def treasure_result_rank_multiplier(cls, result):
        """Compatibility helper: return the point multiplier for the result rank."""
        bonus = cls._treasure_bonus(result)
        selected_rank = bonus.get('rank')
        try:
            rank_mult = int(bonus.get('rank_multiplier', 1))
        except (TypeError, ValueError):
            return 1
        if not selected_rank or rank_mult <= 1:
            return 1
        actual_rank = cls.rank_label(cls.result_rank(result))
        return rank_mult if actual_rank == selected_rank else 1

    @classmethod
    def treasure_profit_multiplier_for_bet(cls, bet_type, result):
        """Return the Treasure profit-odds multiplier for a winning wager.

        Dragon/Tiger rules keep their existing behavior.  The colour bets and
        Small/Big now consume BOTH Treasure conditions: every relevant physical
        card can contribute the selected-suit multiplier and/or selected-rank
        multiplier.  For Small/Big the relevant card is the winning side's card;
        on a Tie, both tied cards are relevant.
        """
        bonus = cls._treasure_bonus(result)
        suit_value = bonus.get('suit')
        rank_value = bonus.get('rank')
        try:
            suit_mult = int(bonus.get('suit_multiplier', 1))
            rank_mult = int(bonus.get('rank_multiplier', 1))
        except (TypeError, ValueError):
            return 1

        dragon = result['dragon_hand'][0]
        tiger = result['tiger_hand'][0]
        winner = result['winner']
        result_rank = cls.result_rank(result)

        def card_multiplier(card):
            m = 1
            if card[0] == suit_value:
                m *= suit_mult
            if card[1] == rank_value:
                m *= rank_mult
            return m

        # Colour wagers concern both physical cards, so both cards may add both
        # the suit and point multipliers.
        if bet_type in ('Both Red', 'Red Black', 'Both Black'):
            return max(1, card_multiplier(dragon) * card_multiplier(tiger))

        # Small / Big are settled from the winning rank (or tied rank).  The
        # winning physical card contributes both conditions; a Tie uses both cards.
        if bet_type in ('Small', 'Big'):
            if winner == 'Dragon':
                cards = (dragon,)
            elif winner == 'Tiger':
                cards = (tiger,)
            else:
                cards = (dragon, tiger)
            multiplier = 1
            for card in cards:
                multiplier *= card_multiplier(card)
            return max(1, multiplier)

        # Perfect suited tie keeps its established rule: suit is per physical card,
        # while the common tied point is multiplied once.
        if bet_type == 'Perfect Suited Tie':
            multiplier = 1
            for card in (dragon, tiger):
                if card[0] == suit_value:
                    multiplier *= suit_mult
            if cls.rank_label(result_rank) == rank_value:
                multiplier *= rank_mult
            return max(1, multiplier)

        if bet_type == 'Dragon':
            cards = (dragon,)
        elif bet_type == 'Tiger':
            cards = (tiger,)
        elif bet_type == 'Tie':
            cards = (dragon, tiger)
        else:
            return 1

        multiplier = 1
        for card in cards:
            if card[0] == suit_value:
                multiplier *= suit_mult
        # Tie represents one tied point for the Tie main bet, so rank is once.
        rank_to_check = cls.rank_label(cls.rank_value(cards[0])) if cards else ''
        if rank_to_check == rank_value:
            multiplier *= rank_mult
        return max(1, multiplier)

    @classmethod
    def main_return_factor(cls, bet_type, result, mode):
        winner = result['winner']
        if bet_type == 'Tie':
            if winner != 'Tie':
                return 0.0
            return 9.0 if mode == 'treasure' else 11.0
        if bet_type in ('Dragon', 'Tiger'):
            if winner == 'Tie':
                return 0.5  # 龙虎主注遇和局输一半，返还一半本金。
            return 2.0 if winner == bet_type else 0.0
        return 0.0

    @classmethod
    def resolve_bets(cls, bets, result, mode, jackpot_amount=0.0):
        del jackpot_amount
        side_factors = cls.side_return_factors(result, mode, bets)
        outcomes = []
        credit = 0.0
        gross_profit = 0.0
        lost_stake = 0.0

        for bet_type, stake in bets.items():
            stake = float(stake)
            if stake <= 0:
                continue
            if bet_type in ('Dragon', 'Tie', 'Tiger'):
                factor = cls.main_return_factor(bet_type, result, mode)
            else:
                factor = float(side_factors.get(bet_type, 0.0))

            # 聚宝盆只放大利润赔率，不放大本金。
            # 特别规则：如果本局和牌，Dragon/Tiger 主注固定只返还 50% 本金，
            # 绝不受本局花色/点数加倍影响；所有边注仍按各自规则正常结算。
            tied_main_half_loss = (
                result.get('winner') == 'Tie' and bet_type in ('Dragon', 'Tiger')
            )
            if mode == 'treasure' and factor > 1.0 and not tied_main_half_loss:
                bonus_mult = cls.treasure_profit_multiplier_for_bet(bet_type, result)
                factor = 1.0 + (factor - 1.0) * bonus_mult

            returned = stake * factor
            if factor > 1.0:
                status = 'win'
                profit = returned - stake
                gross_profit += profit
            elif abs(factor - 1.0) < 1e-9:
                status = 'push'
                profit = 0.0
            elif factor > 0.0:
                status = 'half_loss' if abs(factor - 0.5) < 1e-9 else 'partial_loss'
                profit = returned - stake
                lost_stake += stake - returned
            else:
                status = 'lose'
                profit = -stake
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

        return {
            'credit': credit,
            'gross_profit': gross_profit,
            'lost_stake': lost_stake,
            'net': gross_profit - lost_stake,
            'outcomes': outcomes,
            'side_factors': side_factors,
            'jackpot_win': 0.0,
        }


class DragonTigerBetState:
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
# Canvas interface adapted for Dragon/Tiger
# -----------------------------------------------------------------------------
class BubbleDragonTigerGame(tk.Frame):
    # V25-CSM: temp_finish_data remains the full 300-round history source;
    # last_72_record is a matching rolling cache used only by the Bead Plate.
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
    SPECIAL_STATS = {'classic': (), 'treasure': ()}

    BG = '#17120f'
    PANEL = '#211811'
    PANEL_LINE = '#665240'
    FELT = '#083f38'
    FELT_2 = '#0c5148'
    LINE = '#c3d5ca'
    GOLD = '#e7d36c'
    DRAGON_RED = '#d94a4e'
    TIGER_YELLOW = '#d3a202'
    TIE_GREEN = '#43a665'

    # Result-area flash palette.  The dealing panels flash independently from
    # the betting spots so the winning hand is obvious even with no wager.
    DRAGON_ZONE_BASE = '#4b1e22'
    DRAGON_ZONE_RED = '#c93643'
    DRAGON_ZONE_LIGHT = '#ff9ca2'
    TIGER_ZONE_BASE = '#514514'
    TIGER_ZONE_YELLOW = '#d5ae20'
    TIGER_ZONE_LIGHT = '#ffe98b'
    TIE_FLASH_DARK = '#23874b'
    TIE_FLASH_LIGHT = '#78e49a'

    MIN_BET = 100.0
    MAX_TABLE_BET = 2_000_000.0
    MAX_RECORDS = 300
    BEAD_MAX_RECORDS = 72
    HISTORY_DROP_COUNT = 6

    CHIP_SPECS = [
        (100, '#202020', '100'),
        (500, '#d780c0', '500'),
        (1000, '#ab0058', '1K'),
        (5000, '#ba3438', '5K'),
        (10000, '#70439a', '10K'),
        (30000, '#d0a347', '30K'),
        (50000, '#2e7542', '50K'),
    ]

    MODE_ORDER = ('classic', 'treasure')
    MODE_SHORT = {'classic': '经典版', 'treasure': '聚宝盆'}

    BET_COLORS = {
        'Dragon': '#d94a4e', 'Tie': '#43a665', 'Tiger': '#8f6200',
        'Both Red': '#b8323e', 'Red Black': '#9b6b35', 'Both Black': '#292929',
        'Small': '#487a63', 'Perfect Suited Tie': '#8459a7', 'Big': '#8d6632',
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
        import uuid
        self.csm_game_id = f"DragonTiger:{self.username or 'local'}:{uuid.uuid4().hex}"
        self.csm = ContinuousShuffleMachine()
        self.engine = DragonTigerEngine(self.csm, self.csm_game_id)
        self.bet_state = DragonTigerBetState()
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
        self.settlement_after_id = None
        self.flash_mode = None
        self.flash_winning_keys = set()
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        self.flash_original_text_colors = {}
        self.pre_deal_bets = None
        self.current_result = None
        self.settlement_flash_step = 0
        # V22: on a Tie, keep the original Dragon/Tiger wager chips visible
        # until the complete settlement flash sequence has finished.
        self.settlement_hold_amounts = {}
        self.result_panel_flash_winner = None
        self._closing = False

        # Treasure Pot round state: one suit condition + one rank condition.
        # Any dealt Dragon/Tiger card matching either condition uses Golden artwork.
        self.current_golden_cards = []
        self.current_golden_map = {}
        self.current_treasure_suit = None
        self.current_treasure_rank = None
        self.current_treasure_condition_mode = None
        self.treasure_panel_active = False
        self.treasure_panel_images = []
        self.treasure_animation_refs = {}
        self.treasure_panel_card_items = []
        self.treasure_panel_multiplier_items = []
        self.bet_fee_state = {}
        self.pre_deal_fee_total = 0.0

        self.history_panel_mode = 'roads'
        # V12: Big Road is a 50-column logical board viewed through a
        # horizontally scrollable window.  New results follow the right edge
        # until the dragon manually moves the scrollbar.
        self.big_road_scroll_col = 0
        self.big_road_auto_follow = True
        self.big_road_virtual_cols = 50
        # V12: 14 visible columns makes each Big Road cell ~71% larger than V11's 24-column viewport.
        self.big_road_view_cols = 14
        self.runtime_json_dir = self.get_runtime_json_dir()
        # CSM owns all card/shoe state. temp_finish_data drives every history
        # view except the Bead Plate, which alone uses last_72_record.
        self.runtime_data_file = os.path.join(self.runtime_json_dir, 'Dragon_Tiger.json')
        self.runtime_store = self.load_runtime_store()
        self.history_file = self.runtime_data_file
        self.history_store = self.load_history_store()
        self.history_data = self.history_records_from_store()
        self.last_72_store = self.load_last_72_store()
        self.last_72_data = self.last_72_records_from_store()
        self.statistic_data = self.load_statistic_data()
        self.runtime_store['temp_finish_data'] = copy.deepcopy(self.history_store)
        self.runtime_store['last_72_record'] = copy.deepcopy(self.last_72_store)
        self._write_runtime_store()
        self.treasure_pot_amount = 0.0  # V19: current-round fee only; never persisted

        # Bead Plate text can be toggled between result labels/special marks and
        # the winning point value by clicking anywhere on the bead grid.
        self.bead_show_scores = False

        self.jackpot_file = self.get_jackpot_file()
        self.jackpot_amount = self.load_jackpot()

        # Prefer the original external card artwork. If the project
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
        """Right-side roads plus a compact pie-chart data page."""
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
        # No "大眼仔 / 小路 / 蟑螂路" explanatory labels.  Only Dragon and
        # Tiger headers remain; the three symbol rows follow the standard order.
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
        c.create_text((nx0 + mid_x) / 2, ny0 + header_h / 2, text='龙',
                      font=('Arial', 8, 'bold'), fill=self.DRAGON_RED,
                      tags='history_panel_content')
        c.create_text((mid_x + nx1) / 2, ny0 + header_h / 2, text='虎',
                      font=('Arial', 8, 'bold'), fill=self.TIGER_YELLOW,
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
        return '* 龙/虎遇和输一半'

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

    def _draw_data_page(self):
        c = self.canvas
        x0, x1 = 786, 1130
        c.create_text((x0 + x1) / 2, 82, text='最近 300 局分布',
                      font=('Arial', 13, 'bold'), fill=self.GOLD,
                      tags='history_panel_content')
        for bx0, by0, bx1, by1 in (
            (x0, 102, x1, 310), (x0, 324, x1, 484), (x0, 500, x1, 590),
        ):
            c.create_rectangle(bx0, by0, bx1, by1, fill='#15110f',
                               outline='#7c6754', width=1,
                               tags='history_panel_content')
        self.history_chart_geometry = {
            'winner': (x0, 102, x1, 310),
            'size': (x0, 324, x1, 484),
            'perfect': (x0, 500, x1, 590),
        }

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

    def _build_big_road(self, records):
        """Build the standard Dragon/Tiger Big Road from chronological hands.

        Ties never advance the road.  They are drawn as green diagonal marks
        on the latest Dragon/Tiger cell.  If a shoe starts with ties, those
        ties occupy the top-left cell until the first non-tie result arrives.
        Pair flags from a Tie hand are also retained on that same Big-Road
        cell, matching the normal scoreboard convention.
        """
        sequence = []
        pending_ties = 0
        pending_dragon_pair = False
        pending_tiger_pair = False

        for record in records:
            winner = record.get('winner')
            dragon_pair = bool(record.get('dragon_pair', False))
            tiger_pair = bool(record.get('tiger_pair', False))

            if winner == 'Tie':
                if sequence:
                    payload = sequence[-1][1]
                    payload['ties'] += 1
                    payload['dragon_pair'] = payload['dragon_pair'] or dragon_pair
                    payload['tiger_pair'] = payload['tiger_pair'] or tiger_pair
                else:
                    pending_ties += 1
                    pending_dragon_pair = pending_dragon_pair or dragon_pair
                    pending_tiger_pair = pending_tiger_pair or tiger_pair
                continue

            if winner not in ('Dragon', 'Tiger'):
                continue

            payload = {
                'record': record,
                'ties': pending_ties,
                'dragon_pair': dragon_pair or pending_dragon_pair,
                'tiger_pair': tiger_pair or pending_tiger_pair,
            }
            pending_ties = 0
            pending_dragon_pair = False
            pending_tiger_pair = False
            sequence.append((winner, payload))

        cells = self._place_road_sequence(sequence)

        # A shoe may currently contain only one or more opening ties.  Standard
        # electronic roads show the green tie slash in the top-left cell even
        # before the first Dragon/Tiger circle exists.
        if not cells and pending_ties:
            return [{
                'row': 0, 'col': 0, 'value': 'TieOnly',
                'payload': {
                    'record': None, 'ties': pending_ties,
                    'dragon_pair': pending_dragon_pair,
                    'tiger_pair': pending_tiger_pair,
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
            if winner not in ('Dragon', 'Tiger'):
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
                if winner == 'Dragon':
                    text = str(int(record.get('dragon_score', 0)))
                elif winner == 'Tiger':
                    text = str(int(record.get('tiger_score', 0)))
                elif winner == 'Tie':
                    # A tie has the same score on both sides; use that tied value.
                    text = str(int(record.get('dragon_score', record.get('tiger_score', 0))))
                else:
                    text = ''
            else:
                marker = self._special_marker(record)
                text = marker or {'Dragon': '龙', 'Tiger': '虎', 'Tie': '和'}.get(winner, '')
            bead_text_color = '#111111' if winner == 'Tiger' else 'white'
            self.canvas.create_text(cx, cy, text=text, font=('Arial', 12, 'bold'),
                                    fill=bead_text_color, tags='history_dynamic')

            # Pair markers remain dots only (never text), with stronger colour,
            # a larger radius and a white rim so they remain visible on the bead.
            pair_r = max(4.0, cell * 0.155)
            inset = radius * 0.76
            if record.get('dragon_pair'):
                px, py = cx - inset, cy - inset
                self.canvas.create_oval(px - pair_r, py - pair_r, px + pair_r, py + pair_r,
                                        fill='#145dff', outline='#ffffff', width=2,
                                        tags='history_dynamic')
            if record.get('tiger_pair'):
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

            if winner in ('Dragon', 'Tiger'):
                color = self.DRAGON_RED if winner == 'Dragon' else self.TIGER_YELLOW
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
            if payload.get('dragon_pair'):
                px, py = cx - radius * 0.78, cy - radius * 0.78
                self.canvas.create_oval(px-pair_r, py-pair_r, px+pair_r, py+pair_r,
                                        fill=self.DRAGON_RED, outline='',
                                        tags='history_dynamic')
            if payload.get('tiger_pair'):
                px, py = cx + radius * 0.78, cy + radius * 0.78
                self.canvas.create_oval(px-pair_r, py-pair_r, px+pair_r, py+pair_r,
                                        fill=self.TIGER_YELLOW, outline='',
                                        tags='history_dynamic')

    def _draw_derived_road(self, key, cells, style):
        x0, y0, cell, rows, cols = self.road_geometries[key]
        visible, shift = self._visible_road_cells(cells, cols)
        for item in visible:
            row, col = item['row'], item['col'] - shift
            cx = x0 + col * cell + cell / 2
            cy = y0 + row * cell + cell / 2
            # 龙虎派生路配色：原百家乐蓝色改为龙红，原百家乐红色改为虎黄。
            color = self.TIGER_YELLOW if item['value'] == 'red' else self.DRAGON_RED
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
        counts = {'Dragon': 0, 'Tiger': 0, 'Tie': 0, 'Small': 0, 'Big': 0}
        perfect = 0
        for record in records:
            winner = record.get('winner')
            if winner in ('Dragon', 'Tiger', 'Tie'):
                counts[winner] += 1
            rank = int(record.get('dragon_score' if winner != 'Tiger' else 'tiger_score', 0) or 0)
            if 1 <= rank <= 9:
                counts['Small'] += 1
            if 10 <= rank <= 13:
                counts['Big'] += 1
            dh = record.get('dragon_hand') or []
            th = record.get('tiger_hand') or []
            if dh and th and record.get('dragon_score') == record.get('tiger_score') and dh[0][0] == th[0][0]:
                perfect += 1
        geometry = self.history_chart_geometry
        self._draw_pie_chart(
            geometry['winner'], '龙 / 虎 / 和',
            [('龙', counts['Dragon'], self.DRAGON_RED),
             ('虎', counts['Tiger'], self.TIGER_YELLOW),
             ('和', counts['Tie'], self.TIE_GREEN)])
        self._draw_pie_chart(
            geometry['size'], '小 / 大',
            [('小', counts['Small'], '#55a982'),
             ('大', counts['Big'], '#d18a45')])

        c = self.canvas
        x0, y0, x1, y1 = geometry['perfect']
        c.create_text(x0 + 16, (y0 + y1) / 2, anchor='w', text='完美同花',
                      font=('Arial', 13, 'bold'), fill='#e7dfd5',
                      tags='history_dynamic')
        c.create_text(x1 - 28, (y0 + y1) / 2, anchor='e', text=str(perfect),
                      font=('Arial', 30, 'bold'), fill=self.GOLD,
                      tags='history_dynamic')

    def _draw_pie_chart(self, bounds, title, items):
        c = self.canvas
        x0, y0, x1, y1 = bounds
        c.create_text(x0 + 14, y0 + 18, anchor='w', text=title,
                      font=('Arial', 11, 'bold'), fill='#f2eadf',
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
            for _label, value, color in items:
                value = max(0, int(value))
                if not value:
                    continue
                extent = 360.0 * value / total
                c.create_arc(*bbox, start=start, extent=-extent, fill=color,
                             outline='#15110f', width=2, style=tk.PIESLICE,
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
                          text=f'{label}  {int(value)}  ({percentage:.1f}%)',
                          font=('Arial', 10, 'bold'), fill='#e9e1d8',
                          tags='history_dynamic')

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
        # temp_finish_data remains the source for Big Road, derived roads,
        # predictions and pie charts. Only the Bead Plate uses last_72_record.
        records = self._drawable_history_records(self.history_data)[-self.MAX_RECORDS:]
        if self.history_panel_mode == 'data':
            self._draw_round_statistics(records)
            return
        big_cells = self._build_big_road(records)
        self._draw_big_road(big_cells)
        self._draw_derived_road('eye', self._derive_road(records, 1), 'ring')
        self._draw_derived_road('cockroach', self._derive_road(records, 3), 'slash')
        bead_records = self._drawable_history_records(
            self.last_72_data)[-self.BEAD_MAX_RECORDS:]
        self._draw_bead_plate(bead_records)
        self._draw_derived_road('small', self._derive_road(records, 2), 'dot')
        self._draw_next_round_indicator(records)

    @staticmethod
    def _drawable_history_records(records):
        """Return only valid results that every road renderer can safely draw."""
        drawable = []
        for record in records if isinstance(records, list) else []:
            if not isinstance(record, dict):
                continue
            winner = record.get('winner')
            if winner not in ('Dragon', 'Tie', 'Tiger'):
                continue
            try:
                dragon_score = int(record.get('dragon_score'))
                tiger_score = int(record.get('tiger_score'))
            except (TypeError, ValueError):
                continue
            if not (1 <= dragon_score <= 13 and 1 <= tiger_score <= 13):
                continue
            if ((winner == 'Dragon' and dragon_score <= tiger_score)
                    or (winner == 'Tiger' and tiger_score <= dragon_score)
                    or (winner == 'Tie' and dragon_score != tiger_score)):
                continue
            drawable.append(record)
        return drawable

    def _next_road_color(self, records, candidate, offset):
        simulated = list(records) + [{
            'winner': candidate, 'dragon_pair': False, 'tiger_pair': False,
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
        # 龙虎派生路/问路配色：blue -> Dragon red, red -> Tiger yellow.
        color = self.TIGER_YELLOW if color_name == 'red' else self.DRAGON_RED
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
        # their text labels; the user sees only the predicted symbols under 龙/虎.
        specs = [(1, 'ring'), (2, 'dot'), (3, 'slash')]
        dragon_cx = (geo['x0'] + geo['mid_x']) / 2
        tiger_cx = (geo['mid_x'] + geo['x1']) / 2
        for row, (offset, style) in enumerate(specs):
            cy = geo['top'] + geo['row_h'] * (row + 0.5)
            self._draw_indicator_symbol(dragon_cx, cy,
                                        self._next_road_color(records, 'Dragon', offset), style)
            self._draw_indicator_symbol(tiger_cx, cy,
                                        self._next_road_color(records, 'Tiger', offset), style)

    def find_original_card_asset_dir(self):
        """Locate the original card-asset project A_Tools/Card/Poker1 directory."""
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
        """Use the original 100x140 external card artwork when available."""
        if Image is None or ImageTk is None:
            return
        self.external_card_pil = {}
        self.external_back_pil = None
        card_size = (100, 140)
        directory = self.find_original_card_asset_dir()
        resample = getattr(Image, 'Resampling', Image).LANCZOS

        if directory:
            try:
                for suit in DragonTigerEngine.SUITS:
                    for rank in DragonTigerEngine.RANKS:
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
            for suit in DragonTigerEngine.SUITS:
                for rank in DragonTigerEngine.RANKS:
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
        for suit in DragonTigerEngine.SUITS:
            for rank in DragonTigerEngine.RANKS:
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
        """A dealt card uses Golden artwork when it matches either Treasure condition."""
        if self.game_mode != 'treasure' or not card:
            return False
        suit, rank = tuple(card)
        suit_hit = bool(self.current_treasure_suit and suit == self.current_treasure_suit[0])
        rank_hit = bool(self.current_treasure_rank and rank == self.current_treasure_rank[0])
        return suit_hit or rank_hit

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
        """龙虎每边只发一张牌，单牌居中显示。"""
        x0, y0, _x1, _y1 = self.animation_panel
        y = y0 + 90
        if hand_type == 'Dragon':
            return (x0 + 138, y)
        return (x0 + 510, y)

    def draw_animation_panel(self):
        c = self.canvas
        x0, y0, x1, y1 = self.GAME_X0, 4, self.GAME_X1, 310
        c.create_rectangle(x0, y0, x1, y1, fill=self.PANEL,
                           outline=self.PANEL_LINE, width=2, tags='static')
        self.animation_panel = (x0, y0, x1, y1)
        self.animation_phase_text = c.create_text(
            (x0 + x1) / 2, y0 + 18, text='龙虎 DRAGON TIGER',
            font=('Arial', 16, 'bold'), fill='#d4c3a9', tags='animation')

        self.dragon_zone_rect = c.create_rectangle(
            x0 + 10, y0 + 38, x0 + 366, y1 - 7,
            fill=self.DRAGON_ZONE_BASE, outline='#a56a6d', width=2, tags='animation')
        self.tiger_zone_rect = c.create_rectangle(
            x0 + 382, y0 + 38, x1 - 10, y1 - 7,
            fill=self.TIGER_ZONE_BASE, outline='#b89c45', width=2, tags='animation')
        self.dragon_zone_label = c.create_text(
            x0 + 24, y0 + 53, anchor='w', text='龙 DRAGON',
            font=('Arial', 11, 'bold'), fill='#ffaaaa', tags='animation')
        self.tiger_zone_label = c.create_text(
            x0 + 396, y0 + 53, anchor='w', text='虎 TIGER',
            font=('Arial', 11, 'bold'), fill='#ffe77a', tags='animation')

        dx, dy = self.card_position('Dragon', 0)
        tx, ty = self.card_position('Tiger', 0)
        self.dragon_score_text = c.create_text(
            dx - 18, dy + 70, anchor='e', text='—',
            font=('Arial', 76, 'bold'), fill='white', tags='animation')
        self.tiger_score_text = c.create_text(
            tx + 118, ty + 70, anchor='w', text='—',
            font=('Arial', 76, 'bold'), fill='white', tags='animation')
        self.tie_flash_rect = c.create_rectangle(
            0, 0, 0, 0, fill=self.TIE_FLASH_DARK, outline='',
            state='hidden', tags='animation')
        self.card_item_ids = []
        self.revealed_cards = {'Dragon': [], 'Tiger': []}
        self._temp_flip_images = {}

    def clear_card_display(self):
        for item in self.card_item_ids:
            try:
                self.canvas.delete(item)
            except tk.TclError:
                pass
        self.card_item_ids = []
        self._temp_flip_images = {}
        self.revealed_cards = {'Dragon': [], 'Tiger': []}
        self.canvas.itemconfigure(self.dragon_score_text, text='—')
        self.canvas.itemconfigure(self.tiger_score_text, text='—')

    @staticmethod
    def card_text(card):
        suit, rank = card
        suit_map = {'Club': '♣', 'Diamond': '♦', 'Heart': '♥', 'Spade': '♠'}
        return f'{rank}\n{suit_map.get(suit, suit[:1])}'

    def draw_card(self, hand_type, index, card, face_up=True):
        """Draw one card at the Dragon/Tiger 100x140 display size."""
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
        """经典版与聚宝盆使用完全相同的下注区域，切换时保留全部下注。"""
        if mode == self.game_mode:
            return
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        if mode not in self.MODE_ORDER:
            return
        old_mode = self.game_mode
        entering_treasure = mode == 'treasure' and old_mode != 'treasure'
        leaving_treasure = old_mode == 'treasure' and mode != 'treasure'
        if entering_treasure:
            fee_needed = self.bet_state.total_at_risk() * 0.10
            if fee_needed > self.balance + 1e-9:
                messagebox.showwarning(
                    '聚宝盆费用',
                    f'现有下注切换到聚宝盆需要额外费用 {self.format_money(fee_needed)}，余额不足。',
                    parent=self.winfo_toplevel())
                return
            for bet_type, amount in self.bet_state.bets.items():
                fee = float(amount) * 0.10
                self.balance -= fee
                self.bet_fee_state[bet_type] = fee
                self.treasure_pot_amount += fee
        elif leaving_treasure:
            fee_refund = sum(float(v) for v in self.bet_fee_state.values())
            self.balance += fee_refund
            self.bet_fee_state.clear()
            self.treasure_pot_amount = 0.0

        self.game_mode = mode
        self.undo_stack.clear()
        self.summary_mode = 'bet'
        self.draw_mode_betting_board()
        self.update_mode_selector_style()
        self.update_display()
        self.save_balance()

    def draw_mode_betting_board(self):
        c = self.canvas
        c.delete('board_dynamic')
        c.delete('bet_chip_dynamic')
        self.bet_spots = {}
        rows = DragonTigerEngine.MODE_ROWS[self.game_mode]
        odds = DragonTigerEngine.ODDS_TEXT[self.game_mode]

        c.create_text(30, 363, anchor='w',
                      text=DragonTigerEngine.MODE_NAMES[self.game_mode],
                      font=('Arial', 14, 'bold'), fill=self.GOLD,
                      tags='board_dynamic')
        if self.game_mode == 'lucky7':
            c.create_text(754, 363, anchor='e',
                          text=f'奖池 ${self.jackpot_amount:,.0f}',
                          font=('Arial', 11, 'bold'), fill='#71edb5',
                          tags=('board_dynamic', 'jackpot_display'))
        elif self.game_mode == 'treasure':
            self.treasure_pool_display = c.create_text(754, 363, anchor='e',
                          text=f'聚宝盆 本局 ${self.treasure_pot_amount:,.0f}',
                          font=('Arial', 11, 'bold'), fill='#ffd84a',
                          tags=('board_dynamic', 'treasure_pool_display'))

        # Give the two side-bet bands more breathing room and larger text.
        # The main Dragon/Tie/Tiger band is intentionally shorter so the board
        # reads as two information-rich side-bet rows over one compact main row.
        self.draw_bet_row(rows[0], self.BOARD_INNER_X0, 374, 442, odds)
        self.draw_bet_row(rows[1], self.BOARD_INNER_X0, 446, 514, odds)

        main = ('Dragon', 'Tie', 'Tiger')
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
        outline = '#f0cf54' if bet_type == 'Golden Hunter' else '#d5cbbd'
        outline_width = 2 if bet_type == 'Golden Hunter' else 1
        rect_id = c.create_rectangle(
            x0 + 2, y0 + 2, x1 - 2, y1 - 2,
            fill=fill, outline=outline, width=outline_width,
            tags=('board_dynamic', tag))

        label = DragonTigerEngine.DISPLAY_NAMES.get(bet_type, bet_type)
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
            1012, 628, 1138, 720, '开牌', self.deal_cards, '#d5ad4d',
            fg='#111', font_size=14, subtext='ENTER', subtext_font_size=10)
        c.tag_raise('controls')
        c.tag_raise('chip_selector')
        self.update_control_states()

    def show_game_instructions(self):
        existing = getattr(self, '_intro_window', None)
        try:
            if existing is not None and existing.winfo_exists():
                existing.lift()
                existing.focus_force()
                return
        except tk.TclError:
            pass

        window = tk.Toplevel(self.winfo_toplevel())
        self._intro_window = window
        window.title('龙虎 · 游戏简介')
        window.configure(bg='#120f0d')
        window.resizable(False, False)
        window.transient(self.winfo_toplevel())

        width, height = 860, 720
        try:
            parent = self.winfo_toplevel()
            x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
            y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 2)
            window.geometry(f'{width}x{height}+{x}+{y}')
        except tk.TclError:
            window.geometry(f'{width}x{height}')

        header = tk.Frame(window, bg='#352417', height=96,
                          highlightbackground='#a7844d', highlightthickness=1)
        header.pack(fill='x', padx=12, pady=(12, 8))
        header.pack_propagate(False)
        tk.Label(header, text='龙  虎', bg='#352417', fg='#f2d37b',
                 font=('Arial', 28, 'bold')).place(x=24, y=14)
        tk.Label(header, text='DRAGON  ·  TIGER', bg='#352417', fg='#bda98d',
                 font=('Arial', 10, 'bold')).place(x=27, y=61)
        mode_name = DragonTigerEngine.MODE_NAMES.get(self.game_mode, self.game_mode)
        tk.Label(header, text=f'当前玩法  {mode_name}', bg='#a77a31', fg='#130f0b',
                 padx=18, pady=7, font=('Arial', 12, 'bold')).place(x=630, y=28)

        content = tk.Frame(window, bg='#120f0d')
        content.pack(fill='both', expand=True, padx=12)
        left = tk.Frame(content, bg='#120f0d')
        right = tk.Frame(content, bg='#120f0d')
        left.pack(side='left', fill='both', expand=True, padx=(0, 5))
        right.pack(side='right', fill='both', expand=True, padx=(5, 0))

        def section(parent, title, accent, body, height_px):
            frame = tk.Frame(parent, bg='#201914', height=height_px,
                             highlightbackground='#58483a', highlightthickness=1)
            frame.pack(fill='x', pady=(0, 8))
            frame.pack_propagate(False)
            tk.Frame(frame, bg=accent, width=5).pack(side='left', fill='y')
            inner = tk.Frame(frame, bg='#201914')
            inner.pack(side='left', fill='both', expand=True, padx=14, pady=10)
            tk.Label(inner, text=title, bg='#201914', fg=accent,
                     font=('Arial', 13, 'bold'), anchor='w').pack(fill='x')
            tk.Label(inner, text=body, bg='#201914', fg='#e9dfd4',
                     font=('Arial', 10), justify='left', anchor='nw',
                     wraplength=360).pack(fill='both', expand=True, pady=(7, 0))
            return frame

        section(
            left, '一眼看懂', '#e25a60',
            '龙、虎各发 1 张牌，比较点数大小。\n'
            'A 最小，依次到 K 最大；同点数即为和局。\n'
            '龙／虎主注赔率 1:1；遇和时各输一半。', 128)

        rank_frame = tk.Frame(left, bg='#201914', height=92,
                              highlightbackground='#58483a', highlightthickness=1)
        rank_frame.pack(fill='x', pady=(0, 8))
        rank_frame.pack_propagate(False)
        tk.Label(rank_frame, text='牌面顺序', bg='#201914', fg='#f2d37b',
                 font=('Arial', 12, 'bold')).pack(anchor='w', padx=14, pady=(8, 4))
        ranks = tk.Frame(rank_frame, bg='#201914')
        ranks.pack(fill='x', padx=12)
        for rank in ('A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K'):
            tk.Label(ranks, text=rank, bg='#3b3028', fg='white', width=2,
                     font=('Arial', 9, 'bold'), padx=1, pady=4).pack(side='left', padx=1)

        section(
            left, '边注速查', '#56b58b',
            '小：胜方点数 A–9    ｜    大：胜方点数 10–K\n'
            '完美同花：两张牌点数及花色完全相同\n'
            '颜色注：双方红色／红黑各一／双方黑色', 126)
        section(
            left, '操作与记录', '#70a9d6',
            '左键下注 · 右键清除单区 · Enter 开牌\n'
            '「道路」查看珠盘及派生路；「数据」查看最近 300 局饼图。\n'
            '珠盘独立保留 72 局；第 73 局时按整列移除最旧 6 局。', 120)

        section(
            right, '经典版赔率', '#d6aa58',
            '和局 10:1　｜　完美同花 50:1\n'
            '双方红色 2.9:1　｜　红黑各一 0.95:1\n'
            '双方黑色 2.9:1　｜　小 1:1　｜　大 0.9:1', 120)
        section(
            right, '聚宝盆赔率', '#b884e0',
            '和局 8:1　｜　完美同花 30:1\n'
            '双方红／双方黑 2:1　｜　红黑各一 0.75:1\n'
            '小 0.75:1　｜　大 0.55:1\n'
            '命中黄金花色或点数时，按当局倍率加乘。', 140)
        section(
            right, '黄金条件', '#f0c84d',
            '仅花色 34%　｜　仅点数 44%　｜　两者 22%\n'
            '花色倍率：2X / 3X / 4X\n'
            '点数倍率：2X / 3X / 4X / 5X / 8X', 116)
        section(
            right, '连续洗牌机', '#68c9c0',
            '8 副牌 · 15 仓 CSM 连续洗牌。\n'
            '每局由机器提供牌张，结算后自动归还；不使用本地 JSON 牌靴。', 96)

        footer = tk.Frame(window, bg='#120f0d', height=54)
        footer.pack(fill='x', padx=12, pady=(4, 10))
        tk.Label(footer, text=f'版本 {DRAGON_TIGER_VERSION}', bg='#120f0d',
                 fg='#756b62', font=('Arial', 9)).pack(side='left', padx=4)
        tk.Button(footer, text='知道了', command=window.destroy,
                  bg='#a77a31', fg='#130f0b', activebackground='#d1a750',
                  relief='flat', padx=28, pady=7,
                  font=('Arial', 11, 'bold')).pack(side='right')
        window.protocol('WM_DELETE_WINDOW', window.destroy)
        window.bind('<Escape>', lambda _event: window.destroy())
        window.after(20, window.focus_force)

    def show_help_window(self):
        self.show_game_instructions()

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
        if bet_type == 'Golden Hunter':
            return 5_000.0
        if bet_type in ('Dragon', 'Tiger'):
            return 500_000.0
        if bet_type == 'Tie':
            return 100_000.0
        return 30_000.0

    def _treasure_fee_rate(self, bet_type):
        del bet_type
        return 0.10 if self.game_mode == 'treasure' else 0.0

    def _refresh_treasure_pool_text(self):
        item = getattr(self, 'treasure_pool_display', None)
        if item:
            try:
                self.canvas.itemconfigure(item, text=f'聚宝盆 本局 ${self.treasure_pot_amount:,.0f}')
            except tk.TclError:
                pass

    def _current_round_total_cost(self):
        """本局总支出 = 下注额 + 聚宝盆10%费用。"""
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
            messagebox.showwarning('下注限制', f'下注已自动调整为 {self.format_money(allowed)}。',
                                   parent=self.winfo_toplevel())
        fee = allowed * fee_rate
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
        if self.bet_state.total_at_risk() > 0:
            messagebox.showwarning('重复下注', '请先清除当前下注，再重复上局下注。',
                                   parent=self.winfo_toplevel())
            return
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
            # Tie is a visual push for Dragon/Tiger during settlement: the
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
        color = cls.CHIP_SPECS[0][1]
        for threshold, chip_color, _label in cls.CHIP_SPECS:
            if amount >= threshold:
                color = chip_color
            else:
                break
        return color

    # ------------------------------------------------------- Treasure Pot mode
    def _prepare_treasure_round(self, on_complete=None):
        """Choose this round's active golden condition(s), then reveal their cards.

        Round-type probabilities are mutually exclusive and total 100%:
          - suit only: 34%
          - rank only: 44%
          - suit + rank: 22%
        Multiplier distributions remain independent for suit and rank.
        """
        rng = random.SystemRandom()
        condition_mode = rng.choices(
            DragonTigerEngine.TREASURE_CONDITION_TYPES,
            weights=DragonTigerEngine.TREASURE_CONDITION_WEIGHTS,
            k=1,
        )[0]
        self.current_treasure_condition_mode = condition_mode
        self.current_treasure_suit = None
        self.current_treasure_rank = None
        self.current_golden_cards = []

        if condition_mode in ('suit', 'both'):
            suit = rng.choice(DragonTigerEngine.SUITS)
            suit_mult = int(rng.choices(
                DragonTigerEngine.TREASURE_SUIT_MULTIPLIER_VALUES,
                weights=DragonTigerEngine.TREASURE_SUIT_MULTIPLIER_WEIGHTS, k=1)[0])
            self.current_treasure_suit = (suit, suit_mult)
            self.current_golden_cards.append((('SuitOnly', suit), suit_mult))

        if condition_mode in ('rank', 'both'):
            rank = rng.choice(DragonTigerEngine.RANKS)
            rank_mult = int(rng.choices(
                DragonTigerEngine.TREASURE_RANK_MULTIPLIER_VALUES,
                weights=DragonTigerEngine.TREASURE_RANK_MULTIPLIER_WEIGHTS, k=1)[0])
            self.current_treasure_rank = (rank, rank_mult)
            self.current_golden_cards.append((('RankOnly', rank), rank_mult))

        self.current_golden_map = {}
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
        x0, y0, x1, y1 = self.HISTORY_X0, 4, self.HISTORY_X1, 620
        c = self.canvas
        c.create_rectangle(x0, y0, x1, y1, fill='#17120f', outline='#d0aa3f', width=3,
                           tags='treasure_panel')
        c.create_text((x0+x1)/2, 34, text='聚宝盆', font=('Arial', 22, 'bold'),
                      fill='#ffd84a', tags='treasure_panel')
        c.create_text((x0+x1)/2, 72, text='本局黄金条件', font=('Arial', 13, 'bold'),
                      fill='#e8d8b4', tags='treasure_panel')
        for (descriptor, _mult), (px, _py) in zip(
                self.current_golden_cards, self._treasure_panel_positions()):
            kind_tag, _value = descriptor
            label = '花色' if kind_tag == 'SuitOnly' else '点数'
            c.create_text(px + 50, 118, text=label, font=('Arial', 12, 'bold'),
                          fill='white', tags='treasure_panel')
        c.create_text((x0+x1)/2, 390,
                      text='命中花色或点数会增加倍数',
                      font=('Arial', 12, 'bold'), fill='#e8d8b4', justify='center',
                      tags='treasure_panel')
        c.tag_raise('treasure_panel')

    def _treasure_panel_positions(self):
        """Return centered panel positions for one or two active condition cards."""
        if len(self.current_golden_cards) <= 1:
            return [(908, 145)]
        return [(837, 145), (1007, 145)]

    def _make_treasure_condition_pil(self, kind, value):
        """Draw a formal-size Treasure condition card without corner indices.

        The card uses the same 100x140 proportion as the dealt poker cards, with
        a gold body. Suit conditions are drawn as vector shapes (not Unicode), so
        Windows font availability cannot turn Club/Diamond/Heart/Spade into tofu.
        Rank conditions show one large centred A-K value only.
        """
        if Image is None or ImageDraw is None:
            return None

        width, height = 100, 140
        gold_fill = '#d3a202'
        outer_line = '#3b302d'
        pale_line = '#fff4cf'
        inner_gold = '#b88900'
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Formal poker-card frame: dark outside edge + two inset keylines.
        draw.rounded_rectangle((1, 1, width - 2, height - 2), radius=13,
                               fill=gold_fill, outline=outer_line, width=4)
        draw.rounded_rectangle((7, 7, width - 8, height - 8), radius=10,
                               outline=pale_line, width=2)
        draw.rounded_rectangle((12, 12, width - 13, height - 13), radius=8,
                               outline=inner_gold, width=2)

        def draw_suit(suit):
            red = suit in ('Diamond', 'Heart')
            fill = '#b61f2b' if red else '#171313'
            cx, cy = width / 2, height / 2

            if suit == 'Diamond':
                draw.polygon([(cx, cy - 36), (cx + 27, cy),
                              (cx, cy + 36), (cx - 27, cy)], fill=fill)
                return

            if suit == 'Heart':
                # Two lobes and a lower point; generous overlap removes seams.
                draw.ellipse((cx - 31, cy - 29, cx + 1, cy + 5), fill=fill)
                draw.ellipse((cx - 1, cy - 29, cx + 31, cy + 5), fill=fill)
                draw.polygon([(cx - 30, cy - 9), (cx + 30, cy - 9),
                              (cx, cy + 39)], fill=fill)
                return

            if suit == 'Club':
                draw.ellipse((cx - 15, cy - 38, cx + 15, cy - 8), fill=fill)
                draw.ellipse((cx - 34, cy - 15, cx - 4, cy + 15), fill=fill)
                draw.ellipse((cx + 4, cy - 15, cx + 34, cy + 15), fill=fill)
                draw.ellipse((cx - 16, cy - 12, cx + 16, cy + 20), fill=fill)
                draw.polygon([(cx - 7, cy + 10), (cx + 7, cy + 10),
                              (cx + 14, cy + 38), (cx - 14, cy + 38)], fill=fill)
                return

            # Spade: pointed crown, two lower lobes, then the stem.
            draw.polygon([(cx, cy - 42), (cx - 31, cy + 2),
                          (cx + 31, cy + 2)], fill=fill)
            draw.ellipse((cx - 31, cy - 10, cx + 2, cy + 23), fill=fill)
            draw.ellipse((cx - 2, cy - 10, cx + 31, cy + 23), fill=fill)
            draw.polygon([(cx - 7, cy + 12), (cx + 7, cy + 12),
                          (cx + 16, cy + 40), (cx - 16, cy + 40)], fill=fill)

        if kind == 'suit':
            draw_suit(str(value))
        else:
            # Prefer Windows Arial Bold, then common Linux/macOS fallbacks.
            font_rank = None
            if ImageFont is not None:
                font_candidates = (
                    r'C:\Windows\Fonts\arialbd.ttf',
                    r'C:\Windows\Fonts\calibrib.ttf',
                    'arialbd.ttf', 'Arial Bold.ttf',
                    'DejaVuSans-Bold.ttf', 'LiberationSans-Bold.ttf',
                )
                for candidate in font_candidates:
                    try:
                        font_rank = ImageFont.truetype(candidate, 64)
                        break
                    except Exception:
                        continue
                if font_rank is None:
                    try:
                        font_rank = ImageFont.load_default(size=54)
                    except TypeError:
                        font_rank = ImageFont.load_default()
            draw.text((width / 2, height / 2 + 1), str(value),
                      fill='#171313', font=font_rank, anchor='mm')
        return image

    def _treasure_condition_pil(self, descriptor):
        kind_tag, value = tuple(descriptor)
        kind = 'suit' if kind_tag == 'SuitOnly' else 'rank'
        return self._make_treasure_condition_pil(kind, value)

    def _animate_treasure_card_fade(self, index, on_complete):
        if self._closing or not self.treasure_panel_active:
            return
        if index >= len(self.current_golden_cards):
            self._queue_animation(20, self._animate_treasure_multiplier_drop, on_complete)
            return

        descriptor, _mult = self.current_golden_cards[index]
        px, py = self._treasure_panel_positions()[index]
        c = self.canvas
        base = self._treasure_condition_pil(descriptor)
        steps = 20
        frame_ms = 25

        if base is None or ImageTk is None:
            kind_tag, value = descriptor
            rect = c.create_rectangle(px, py, px+100, py+140, fill='#d3a202',
                                      outline='#3b302d', width=4,
                                      stipple='gray75', tags='treasure_panel')
            inner1 = c.create_rectangle(px+7, py+7, px+93, py+133, outline='#f7edd0', width=2,
                                        tags='treasure_panel')
            inner2 = c.create_rectangle(px+12, py+12, px+88, py+128, outline='#b89417', width=1,
                                        tags='treasure_panel')
            if kind_tag == 'SuitOnly':
                text = {'Club':'♣', 'Diamond':'♦', 'Heart':'♥', 'Spade':'♠'}.get(value, value)
                fg = '#c22631' if value in ('Diamond','Heart') else '#111111'
                font = ('Arial', 42, 'bold')
            else:
                text, fg = value, '#111111'
                font = ('Arial', 38, 'bold')
            txt = c.create_text(px+50, py+70, text=text,
                                font=font, fill=fg,
                                tags='treasure_panel')
            self.treasure_panel_card_items.extend((rect, inner1, inner2, txt))
            self._queue_animation(500, self._animate_treasure_card_fade, index + 1, on_complete)
            return

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
                final_photo = ImageTk.PhotoImage(base, master=self)
                self.treasure_animation_refs[item] = final_photo
                c.itemconfigure(item, image=final_photo)
                self._queue_animation(0, self._animate_treasure_card_fade, index + 1, on_complete)
        fade_step(0)

    def _animate_treasure_multiplier_drop(self, on_complete):
        """Drop the two multiplier badges from above, matching the Baccarat animation."""
        if self._closing or not self.treasure_panel_active:
            return
        c = self.canvas
        positions = self._treasure_panel_positions()
        self.treasure_panel_multiplier_items = []
        start_y = 78
        finals = []
        for (_descriptor, mult), (px, py) in zip(self.current_golden_cards, positions):
            cx = px + 77
            final_y = py + 12
            oval = c.create_oval(cx-18, start_y-18, cx+18, start_y+18,
                                 fill='#ffffff', outline='#d6d6d6', width=2,
                                 tags='treasure_panel')
            text = c.create_text(cx, start_y, text=f'{mult}X', font=('Arial', 11, 'bold'),
                                 fill='#000000', tags='treasure_panel')
            self.treasure_panel_multiplier_items.extend((oval, text))
            finals.append((oval, text, cx, final_y))
        c.tag_raise('treasure_panel')

        steps = 20
        frame_ms = 25
        def drop_step(step=0):
            if self._closing or not self.treasure_panel_active:
                return
            ratio = min(1.0, step / float(steps))
            eased = 1.0 - (1.0 - ratio) ** 3
            for oval, text, cx, final_y in finals:
                cy = start_y + (final_y - start_y) * eased
                c.coords(oval, cx-18, cy-18, cx+18, cy+18)
                c.coords(text, cx, cy)
            if step < steps:
                self._queue_animation(frame_ms, drop_step, step + 1)
            elif callable(on_complete):
                self._queue_animation(0, on_complete)
        drop_step(0)

    def _hide_treasure_panel(self):
        self.treasure_panel_active = False
        self.canvas.delete('treasure_panel')
        self.treasure_panel_images = []
        self.treasure_animation_refs = {}
        self.treasure_panel_card_items = []
        self.treasure_panel_multiplier_items = []
        self.current_treasure_suit = None
        self.current_treasure_rank = None
        self.current_treasure_condition_mode = None
        self._draw_history_content()
        self.update_history_table()

    def _gold_multiplier_for_revealed(self, bet_type):
        """Return the currently visible Treasure multiplier without spoilers."""
        if self.game_mode != 'treasure':
            return 1
        ds = list(self.revealed_cards.get('Dragon', []))
        ts = list(self.revealed_cards.get('Tiger', []))
        dragon = ds[0] if ds else None
        tiger = ts[0] if ts else None
        suit_value = self.current_treasure_suit[0] if self.current_treasure_suit else None
        suit_mult = int(self.current_treasure_suit[1]) if self.current_treasure_suit else 1
        rank_value = self.current_treasure_rank[0] if self.current_treasure_rank else None
        rank_mult = int(self.current_treasure_rank[1]) if self.current_treasure_rank else 1

        def card_mult(card):
            if not card:
                return 1
            m = 1
            if card[0] == suit_value:
                m *= suit_mult
            if card[1] == rank_value:
                m *= rank_mult
            return m

        if bet_type in ('Dragon', 'Tiger'):
            # Display is card-driven, not result-driven: if that side's dealt card
            # is golden, keep showing the amplified *would-win* odds and gold frame
            # even when that side ultimately loses the hand.  The only exception
            # is a Tie, where Dragon/Tiger main bets are fixed half-losses and must
            # never advertise a Treasure-amplified return.
            if dragon and tiger and dragon[1] == tiger[1]:
                return 1
            side_card = dragon if bet_type == 'Dragon' else tiger
            return card_mult(side_card)

        # These wagers depend on both dealt cards, so wait until both are visible.
        if bet_type in ('Both Red', 'Red Black', 'Both Black'):
            if not (dragon and tiger):
                return 1
            d_red = dragon[0] in DragonTigerEngine.RED_SUITS
            t_red = tiger[0] in DragonTigerEngine.RED_SUITS
            winning_color_bet = 'Both Red' if (d_red and t_red) else ('Red Black' if d_red != t_red else 'Both Black')
            if bet_type != winning_color_bet:
                return 1
            return max(1, card_mult(dragon) * card_mult(tiger))

        if bet_type == 'Tie':
            m = 1
            for card in (dragon, tiger):
                if card and card[0] == suit_value:
                    m *= suit_mult
            if dragon and tiger and dragon[1] == tiger[1] == rank_value:
                m *= rank_mult
            return m

        if bet_type == 'Perfect Suited Tie':
            m = 1
            for card in (dragon, tiger):
                if card and card[0] == suit_value:
                    m *= suit_mult
            if dragon and tiger and dragon[1] == tiger[1] == rank_value:
                m *= rank_mult
            return m

        if bet_type in ('Small', 'Big'):
            # Both cards are required to know the winning/tied rank and winning side.
            if not (dragon and tiger):
                return 1
            if isinstance(self.current_result, dict):
                visible_result_rank = DragonTigerEngine.result_rank(self.current_result)
                winner = self.current_result.get('winner')
            else:
                dv = DragonTigerEngine.rank_value(dragon)
                tv = DragonTigerEngine.rank_value(tiger)
                visible_result_rank = max(dv, tv)
                winner = 'Dragon' if dv > tv else ('Tiger' if tv > dv else 'Tie')

            if bet_type == 'Small' and not (1 <= visible_result_rank <= 9):
                return 1
            if bet_type == 'Big' and not (10 <= visible_result_rank <= 13):
                return 1

            cards = (dragon,) if winner == 'Dragon' else ((tiger,) if winner == 'Tiger' else (dragon, tiger))
            m = 1
            for card in cards:
                m *= card_mult(card)
            return max(1, m)

        return 1

    def _base_profit_odds_for_treasure(self, bet_type):
        return {'Dragon':1.0, 'Tiger':1.0, 'Tie':8.0,
                'Both Red':2.0, 'Red Black':0.75, 'Both Black':2.0,
                'Small':0.75, 'Perfect Suited Tie':30.0, 'Big':0.55}.get(bet_type)

    def update_golden_bet_visuals(self):
        """Restore Baccarat-style golden outlines and live profit-odds badges."""
        self.canvas.delete('golden_bet_dynamic')
        for _key, spot in self.bet_spots.items():
            rect = spot.get('rect_id')
            if rect:
                try:
                    self.canvas.itemconfigure(rect,
                                              outline=spot.get('normal_outline', '#d5cbbd'),
                                              width=spot.get('normal_outline_width', 1))
                except tk.TclError:
                    pass
            odds_item = spot.get('odds_item')
            if odds_item:
                try:
                    self.canvas.itemconfigure(odds_item, state='normal')
                    self.canvas.coords(odds_item, spot.get('odds_base_x'), spot.get('odds_y'))
                except tk.TclError:
                    pass

        if self.game_mode != 'treasure' or not (self.current_treasure_suit or self.current_treasure_rank):
            return

        for bet_type in ('Both Red', 'Red Black', 'Both Black',
                         'Small', 'Perfect Suited Tie', 'Big',
                         'Dragon', 'Tie', 'Tiger'):
            spot = self.bet_spots.get((bet_type, None))
            if not spot:
                continue
            mult = self._gold_multiplier_for_revealed(bet_type)
            if mult <= 1:
                continue
            rect = spot.get('rect_id')
            if rect:
                try:
                    self.canvas.itemconfigure(rect, outline='#ffd42a', width=4)
                except tk.TclError:
                    pass
            base = self._base_profit_odds_for_treasure(bet_type)
            if base is None:
                continue
            latest = base * mult
            odds_item = spot.get('odds_item')
            bx = spot.get('odds_base_x', (spot['bounds'][0] + spot['bounds'][2]) / 2)
            by = spot.get('odds_y', spot['bounds'][3] - 13)
            if odds_item:
                try:
                    self.canvas.itemconfigure(odds_item, state='hidden')
                except tk.TclError:
                    pass
            x0, _y0, x1, _y1 = spot['bounds']
            half_w = min(40.0, max(29.0, (x1-x0) * 0.17))
            self.canvas.create_oval(bx-half_w, by-15, bx+half_w, by+15,
                                    fill='#e3b51d', outline='#fff2a3', width=2,
                                    tags=('golden_bet_dynamic', spot['tag']))
            self.canvas.create_text(bx, by, text=f'{latest:g}:1',
                                    font=('Arial', 12 if not spot.get('main') else 14, 'bold'),
                                    fill='#201700', tags=('golden_bet_dynamic', spot['tag']))
        self.canvas.tag_raise('golden_bet_dynamic')
        self.canvas.tag_raise('bet_chip_dynamic')

    # ---------------------------------------------------------- shoe / cut / burn
    def _show_cut_dialog(self, second=False):
        """Casino-style visual cut with a physical packet-swap animation.

        The dragon drags a yellow cut card anywhere in the valid 65..349
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
            cv.create_text(380, 65, text='切牌完成',
                           font=('微软雅黑', 20, 'bold'), fill='#ffe365',
                           tags='cut_done')
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
        """Legacy host entry point; CSM mode has no manual cut or burn flow."""
        del second
        if self._closing or self.engine.round_open:
            return
        self.animation_running = False
        self.settlement_running = False
        self.accept_bets = True
        self.canvas.itemconfigure(self.animation_phase_text, text='龙虎 DRAGON TIGER')
        self.update_display()

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
            burn_value = min(10, DragonTigerEngine.card_value(card) or 10)
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
        target_y = 112 + row * 148
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
        self.canvas.itemconfigure(self.animation_phase_text, text='龙虎 DRAGON TIGER')
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
        try:
            self.engine.start_round()
        except (CSMError, OSError, RuntimeError) as exc:
            messagebox.showerror('自动洗牌机', f'无法开始牌局：{exc}',
                                 parent=self.winfo_toplevel())
            return

        self.accept_bets = False
        self.animation_running = True
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

        if self.game_mode == 'treasure':
            # The Treasure panel owns the screen first. One or two active condition
            # cards fade in, then their multiplier badges fall together. Only after
            # that animation completes may the real Dragon card be dealt.
            self.canvas.itemconfigure(self.animation_phase_text, text='聚宝盆…')
            self._prepare_treasure_round(on_complete=self._begin_actual_round_deal)
        else:
            self.current_golden_cards = []
            self.current_golden_map = {}
            self._begin_actual_round_deal()

    def _begin_actual_round_deal(self):
        if self._closing:
            return
        try:
            self.current_result = self.engine.deal_round()
        except (CSMError, OSError, RuntimeError) as exc:
            self.accept_bets = False
            self.animation_running = False
            self.update_display()
            messagebox.showerror(
                '自动洗牌机',
                f'本局发牌已暂停：{exc}\n请退出本局以归还牌张；系统不会放宽取仓规则。',
                parent=self.winfo_toplevel())
            return
        if self.game_mode == 'treasure':
            bonus = {}
            if self.current_treasure_suit:
                bonus['suit'], bonus['suit_multiplier'] = self.current_treasure_suit
            if self.current_treasure_rank:
                bonus['rank'], bonus['rank_multiplier'] = self.current_treasure_rank
            self.current_result['_treasure_bonus'] = bonus
        self.canvas.itemconfigure(self.animation_phase_text, text='发牌中…')
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
        """龙虎严格一边一张：先龙、后虎，每张到位后翻开。"""
        self.initial_card_ids = []
        sequence = (('Dragon', 0), ('Tiger', 0))

        def deal_step(position=0):
            if self._closing or not self.current_result:
                return
            if position >= len(sequence):
                self._queue_animation(180, self.finish_deal)
                return
            hand_type, index = sequence[position]
            hand_key = 'dragon_hand' if hand_type == 'Dragon' else 'tiger_hand'
            real_card = self.current_result[hand_key][index]

            def arrived(info):
                self._flip_card_original(
                    info, real_card,
                    on_complete=lambda: self._queue_animation(100, deal_step, position + 1)
                )
            self._animate_card_entrance_original(hand_type, index, rotated=False, on_arrive=arrived)
        deal_step(0)

    def _deal_initial_cards_original(self):
        # Backward-compatible helper retained for callers outside the main flow.
        self.initial_card_ids = []
        for hand_type in ('Dragon', 'Tiger'):
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
        # Dragon opens card #1 first.
        self._flip_card_original(self.initial_card_ids[1], self.current_result['dragon_hand'][1])
        self._queue_animation(500, self._reveal_initial_phase3_original)

    def _reveal_initial_phase2_original(self):
        # Dragon opens card #0 second.
        self._flip_card_original(self.initial_card_ids[0], self.current_result['dragon_hand'][0])
        self._queue_animation(500, self._reveal_initial_phase4_original)

    def _reveal_initial_phase3_original(self):
        self._flip_card_original(self.initial_card_ids[2], self.current_result['tiger_hand'][0])
        self._queue_animation(500, self._reveal_initial_phase2_original)

    def _reveal_initial_phase4_original(self):
        self._flip_card_original(self.initial_card_ids[3], self.current_result['tiger_hand'][1])
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
        rotated = False
        steps = 12
        orig_w, orig_h = (100, 140)
        if step > steps:
            final_image = self._face_photo(real_card, rotated=False)
            if final_image is not None:
                self.canvas.itemconfigure(card_id, image=final_image)
            self.revealed_cards.setdefault(hand_type, []).append(real_card)
            target = self.dragon_score_text if hand_type == 'Dragon' else self.tiger_score_text
            self.canvas.itemconfigure(target, text=real_card[1])
            if self.game_mode == 'treasure':
                self.update_golden_bet_visuals()
            target_x, target_y = self.card_position(hand_type, index)
            self.canvas.coords(card_id, target_x, target_y)
            self._temp_flip_images.pop(card_id, None)
            if callable(on_complete):
                on_complete()
            return
        half = steps // 2
        if step <= half:
            ratio = 1 - (step / float(half))
            use_back = True
        else:
            ratio = (step - half) / float(half)
            use_back = False
        width = max(1, int(orig_w * ratio))
        image = self._create_scaled_flip_image(real_card, width, orig_h,
                                               use_back=use_back, rotated=rotated)
        if image is not None:
            self._temp_flip_images[card_id] = image
            self.canvas.itemconfigure(card_id, image=image)
            target_x, target_y = self.card_position(hand_type, index)
            self.canvas.coords(card_id, target_x + (orig_w - width) / 2, target_y)
        self._queue_animation(20, self._flip_card_original, card_info, real_card, step + 1, on_complete)

    def _process_extra_cards_original(self):
        if self.current_result and len(self.current_result['dragon_hand']) > 2:
            self._deal_extra_card_original('Dragon', 2)
            self._queue_animation(1200, self._process_tiger_extra_original)
        else:
            self._process_tiger_extra_original()

    def _process_tiger_extra_original(self):
        if self.current_result and len(self.current_result['tiger_hand']) > 2:
            self._deal_extra_card_original('Tiger', 2)
            self._queue_animation(1200, self.finish_deal)
        else:
            self.finish_deal()

    def _deal_extra_card_original(self, hand_type, index):
        hand_key = 'dragon_hand' if hand_type == 'Dragon' else 'tiger_hand'
        card = self.current_result[hand_key][index]

        def arrived(info):
            self._flip_card_original(info, card)

        self._animate_card_entrance_original(hand_type, index, rotated=True,
                                             on_arrive=arrived)

    def reveal_card(self, hand_type, index, card):
        if self._closing:
            return
        self.draw_card(hand_type, index, card, face_up=True)
        self.revealed_cards.setdefault(hand_type, []).append(card)
        target = self.dragon_score_text if hand_type == 'Dragon' else self.tiger_score_text
        self.canvas.itemconfigure(target, text=card[1])
        if self.game_mode == 'treasure':
            self.update_golden_bet_visuals()

    def finish_deal(self):
        if self._closing or not self.current_result:
            return
        self.animation_after_ids.clear()
        result = self.current_result
        self.canvas.itemconfigure(self.dragon_score_text, text=DragonTigerEngine.rank_label(result['dragon_score']))
        self.canvas.itemconfigure(self.tiger_score_text, text=DragonTigerEngine.rank_label(result['tiger_score']))


        settle = DragonTigerEngine.resolve_bets(
            self.pre_deal_bets, result, self.game_mode, self.jackpot_amount)
        self.balance += settle['credit']

        self.last_win_amount = settle['credit']
        self.last_net = settle['net'] - float(self.pre_deal_fee_total or 0.0)
        self.add_history(result)
        self.update_statistic_data(result)

        self.flash_winning_keys = set()
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        for outcome in settle['outcomes']:
            key = tuple(outcome['key'])
            if outcome['return_factor'] > 1.0:
                self.flash_winning_keys.add(key)
                self.flash_winner_amounts[key] = float(outcome['return_amount'])
                self.flash_original_amounts[key] = float(self.pre_deal_bets.get(key[0], 0.0))

        # Flash every objectively winning active side area too, even without a chip.
        for bet_type, factor in settle['side_factors'].items():
            key = (bet_type, None)
            if factor > 1.0 and key in self.bet_spots:
                self.flash_winning_keys.add(key)

        main_factor = DragonTigerEngine.main_return_factor(result['winner'], result, self.game_mode)
        _ = main_factor  # compatibility no-op; winner area is handled explicitly below
        winner_key = (result['winner'], None)
        if result['winner'] in ('Dragon', 'Tie', 'Tiger') and winner_key in self.bet_spots:
            factor = DragonTigerEngine.main_return_factor(result['winner'], result, self.game_mode)
            if factor > 1.0:
                self.flash_winning_keys.add(winner_key)

        # V22: if the round is a Tie, Dragon and Tiger wagers remain visibly
        # on their original betting spots for the whole settlement animation.
        # They disappear only in finish_settlement().
        self.settlement_hold_amounts = {}
        if result.get('winner') == 'Tie':
            for bet_type in ('Dragon', 'Tiger'):
                amount = float(self.pre_deal_bets.get(bet_type, 0.0))
                if amount > 0:
                    self.settlement_hold_amounts[(bet_type, None)] = amount

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
        # At this point both Dragon/Tiger cards are definitely revealed. Rebuild
        # Treasure badges after the normal display refresh so Small/Big Treasure
        # multipliers and their gold outlines remain visible during settlement.
        if self.game_mode == 'treasure':
            self.update_golden_bet_visuals()
            self.canvas.tag_raise('golden_bet_dynamic')
            self.canvas.tag_raise('bet_chip_dynamic')
        self.save_balance()


        # Always flash the winning card zone, even when the dragon placed no
        # wager on the winning outcome. Betting areas still flash when applicable.
        self.settlement_flash_step = 0
        self.run_settlement_flash()

    def _sync_golden_badges_for_flash(self, light_phase):
        """Make Treasure golden odds badges flash with their winning areas."""
        if self.game_mode != 'treasure':
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

    def run_settlement_flash(self):
        if self._closing or not self.settlement_running:
            return
        if self.settlement_flash_step >= 6:
            self.finish_settlement()
            return
        # Rebuild Treasure badges before every flash frame.  Golden status belongs
        # to the dealt card, not to whether the betting area won, so a losing
        # golden Tiger/Dragon area keeps its theoretical winning odds + gold frame.
        if self.game_mode == 'treasure':
            self.update_golden_bet_visuals()
            self.canvas.tag_raise('golden_bet_dynamic')
        self.flash_mode = 'win' if self.settlement_flash_step % 2 == 0 else 'original'
        self.flash_result_panels(self.settlement_flash_step % 2 == 0)
        self.canvas.delete('win_flash_area')
        if self.flash_mode == 'original':
            self.restore_flash_text_colors()
            self._sync_golden_badges_for_flash(False)
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
        self.update_bet_chips()
        self.canvas.tag_raise('bet_chip_dynamic')
        self.canvas.tag_raise('controls')
        self.settlement_flash_step += 1
        self.settlement_after_id = self.after(450, self.run_settlement_flash)

    def _set_zone_text_colors(self, dragon_color=None, tiger_color=None):
        """Set title + score colors together for each dealing zone."""
        if dragon_color is not None:
            for item in (getattr(self, 'dragon_zone_label', None),
                         getattr(self, 'dragon_score_text', None)):
                if item is not None:
                    self.canvas.itemconfigure(item, fill=dragon_color)
        if tiger_color is not None:
            for item in (getattr(self, 'tiger_zone_label', None),
                         getattr(self, 'tiger_score_text', None)):
                if item is not None:
                    self.canvas.itemconfigure(item, fill=tiger_color)

    def flash_result_panels(self, light_phase):
        winner = self.result_panel_flash_winner
        self.canvas.itemconfigure(self.tie_flash_rect, state='hidden')
        self.canvas.itemconfigure(self.dragon_zone_rect, fill=self.DRAGON_ZONE_BASE,
                                  outline='#a56a6d')
        self.canvas.itemconfigure(self.tiger_zone_rect, fill=self.TIGER_ZONE_BASE,
                                  outline='#b89c45')
        self._set_zone_text_colors('#ffaaaa', '#ffe77a')
        self.canvas.itemconfigure(self.dragon_score_text, fill='white')
        self.canvas.itemconfigure(self.tiger_score_text, fill='white')
        if winner == 'Dragon' and light_phase:
            self.canvas.itemconfigure(self.dragon_zone_rect, fill=self.DRAGON_ZONE_LIGHT,
                                      outline='#ffe8ea')
            self._set_zone_text_colors(dragon_color='black')
        elif winner == 'Tiger' and light_phase:
            self.canvas.itemconfigure(self.tiger_zone_rect, fill=self.TIGER_ZONE_LIGHT,
                                      outline='#fff2b4')
            self._set_zone_text_colors(tiger_color='black')
        elif winner == 'Tie' and light_phase:
            self.canvas.itemconfigure(self.dragon_zone_rect, fill=self.TIE_FLASH_LIGHT,
                                      outline='#dcffe6')
            self.canvas.itemconfigure(self.tiger_zone_rect, fill=self.TIE_FLASH_LIGHT,
                                      outline='#dcffe6')
            self._set_zone_text_colors('black', 'black')

    def restore_result_panel_colors(self):
        if hasattr(self, 'dragon_zone_rect'):
            self.canvas.itemconfigure(self.dragon_zone_rect, fill=self.DRAGON_ZONE_BASE,
                                      outline='#a56a6d')
        if hasattr(self, 'tiger_zone_rect'):
            self.canvas.itemconfigure(self.tiger_zone_rect, fill=self.TIGER_ZONE_BASE,
                                      outline='#b89c45')
        if hasattr(self, 'dragon_zone_label'):
            self.canvas.itemconfigure(self.dragon_zone_label, fill='#ffaaaa')
        if hasattr(self, 'tiger_zone_label'):
            self.canvas.itemconfigure(self.tiger_zone_label, fill='#ffe77a')
        if hasattr(self, 'dragon_score_text'):
            self.canvas.itemconfigure(self.dragon_score_text, fill='white')
        if hasattr(self, 'tiger_score_text'):
            self.canvas.itemconfigure(self.tiger_score_text, fill='white')
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
        try:
            self.engine.finish_round()
        except (CSMError, OSError) as exc:
            self.accept_bets = False
            self.animation_running = False
            self.settlement_running = False
            self.update_display()
            messagebox.showerror('自动洗牌机', f'本局牌张归还失败，游戏已暂停：{exc}',
                                 parent=self.winfo_toplevel())
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
        self.pre_deal_bets = None
        self.settlement_running = False
        self.animation_running = False
        self.canvas.itemconfigure(self.animation_phase_text, text='龙虎 DRAGON TIGER')
        if self.game_mode == 'treasure':
            self._hide_treasure_panel()
            self.current_golden_cards = []
            self.current_golden_map = {}
            self.treasure_pot_amount = 0.0
            self.update_golden_bet_visuals()
            self._refresh_treasure_pool_text()
        self.accept_bets = True
        self.update_display()

    @classmethod
    def result_color(cls, winner):
        return {'Dragon': cls.DRAGON_RED, 'Tiger': cls.TIGER_YELLOW,
                'Tie': cls.TIE_GREEN}.get(winner, '#888888')

    @staticmethod
    def result_description(result):
        winner_text = {'Dragon': '龙胜', 'Tiger': '虎胜', 'Tie': '和局'}.get(result['winner'], result['winner'])
        ds = DragonTigerEngine.rank_label(result['dragon_score'])
        ts = DragonTigerEngine.rank_label(result['tiger_score'])
        return f'{winner_text}  龙 {ds} : 虎 {ts}'

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
        return {'total_game': 0, 'dragon_win': 0, 'tiger_win': 0, 'tie_win': 0}

    @classmethod
    def new_runtime_store(cls):
        return {
            'temp_finish_data': cls.new_history_store(),
            'last_72_record': cls.new_history_store(),
            'statistic_data': cls._default_statistic_data(),
        }

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
                print(f'保存 Dragon_Tiger 失败：{exc}')
                self._last_runtime_save_error = message
            return False
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    def load_runtime_store(self):
        """读取记录，并自动忽略旧版 JSON 中的牌靴/temp_data。"""
        store = self.new_runtime_store()
        last_72_missing = True
        try:
            with open(self.runtime_data_file, 'r', encoding='utf-8') as handle:
                raw = json.load(handle)
            if isinstance(raw, dict):
                last_72_missing = not isinstance(raw.get('last_72_record'), dict)
                for key in ('temp_finish_data', 'last_72_record', 'statistic_data'):
                    if isinstance(raw.get(key), dict):
                        store[key] = raw[key]
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        self._last_72_missing = last_72_missing
        return store

    def get_history_file(self):
        return getattr(self, 'runtime_data_file',
                       os.path.join(self.get_runtime_json_dir(), 'Dragon_Tiger.json'))

    def load_temp_data(self):
        """Compatibility helper: CSM encrypted state is the sole shoe state."""
        try:
            self.csm.status()
            return True
        except (CSMError, OSError, TypeError, ValueError):
            return False

    def save_temp_data(self, burn_complete=True):
        """Compatibility no-op: card state must never be duplicated in JSON."""
        del burn_complete

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
        for record in raw_records:
            if not isinstance(record, dict):
                continue
            winner = record.get('winner')
            if winner not in ('Dragon', 'Tie', 'Tiger'):
                continue
            try:
                ps = int(record.get('dragon_score', 0))
                bs = int(record.get('tiger_score', 0))
            except (TypeError, ValueError):
                continue
            if not (1 <= ps <= 13 and 1 <= bs <= 13):
                continue
            if ((winner == 'Dragon' and ps <= bs)
                    or (winner == 'Tiger' and bs <= ps)
                    or (winner == 'Tie' and ps != bs)):
                continue
            item = copy.deepcopy(record)
            item['dragon_score'] = ps
            item['tiger_score'] = bs
            normalized['records'].append(item)
        if len(normalized['records']) > cls.MAX_RECORDS:
            del normalized['records'][:-cls.MAX_RECORDS]
        return normalized

    def load_history_store(self):
        raw = self.runtime_store.get('temp_finish_data', self.new_history_store())
        return self.normalize_history_store(raw)

    def load_last_72_store(self):
        if getattr(self, '_last_72_missing', False):
            seeded = self.new_history_store()
            seeded['records'] = copy.deepcopy(
                self.history_store.get('records', [])[-self.BEAD_MAX_RECORDS:])
            return seeded
        raw = self.runtime_store.get('last_72_record', self.new_history_store())
        normalized = self.normalize_history_store(raw)
        while len(normalized['records']) > self.BEAD_MAX_RECORDS:
            del normalized['records'][:self.HISTORY_DROP_COUNT]
        return normalized

    def save_history_store(self):
        self.runtime_store['temp_finish_data'] = copy.deepcopy(self.history_store)
        self.runtime_store['last_72_record'] = copy.deepcopy(self.last_72_store)
        self._write_runtime_store()

    def history_records_from_store(self):
        return list(self.history_store.get('records', []))

    def last_72_records_from_store(self):
        return list(self.last_72_store.get('records', []))

    def clear_temp_finish_data(self):
        """Clear both synchronized history stores while preserving statistics."""
        self.history_store = self.new_history_store()
        self.history_data = []
        self.last_72_store = self.new_history_store()
        self.last_72_data = []
        self.runtime_store['temp_finish_data'] = self.new_history_store()
        self.runtime_store['last_72_record'] = self.new_history_store()
        self._write_runtime_store()
        self.update_history_table()

    def clear_shoe_temp_sections(self):
        """Compatibility no-op: CSM has no shoe boundary and history is rolling."""
        self._write_runtime_store()

    def add_history(self, result):
        special_by_mode = {}
        for mode in self.MODE_ORDER:
            factors = DragonTigerEngine.side_return_factors(result, mode)
            special_by_mode[mode] = [name for name, factor in factors.items() if factor > 1.0]
        record = {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'winner': result['winner'],
            'dragon_score': int(result['dragon_score']),
            'tiger_score': int(result['tiger_score']),
            'natural': False,
            'mode': self.game_mode,
            'dragon_pair': False,
            'tiger_pair': False,
            'specials': special_by_mode.get(self.game_mode, []),
            'special_by_mode': special_by_mode,
            'dragon_hand': [list(card) for card in result.get('dragon_hand', [])],
            'tiger_hand': [list(card) for card in result.get('tiger_hand', [])],
        }
        if self.game_mode == 'treasure' and result.get('_treasure_bonus'):
            record['treasure_bonus'] = copy.deepcopy(result['_treasure_bonus'])
        records = self.history_store.setdefault('records', [])
        records.append(record)
        if len(records) > self.MAX_RECORDS:
            del records[:-self.MAX_RECORDS]

        bead_records = self.last_72_store.setdefault('records', [])
        bead_records.append(copy.deepcopy(record))
        while len(bead_records) > self.BEAD_MAX_RECORDS:
            del bead_records[:self.HISTORY_DROP_COUNT]

        self.big_road_auto_follow = True
        self.save_history_store()
        self.history_data = self.history_records_from_store()
        self.last_72_data = self.last_72_records_from_store()

    def load_statistic_data(self):
        defaults = self._default_statistic_data()
        raw = self.runtime_store.get('statistic_data', {})
        if isinstance(raw, dict):
            for key in ('total_game', 'dragon_win', 'tiger_win', 'tie_win'):
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
            'dragon_win': max(0, int(self.statistic_data.get('dragon_win', 0))),
            'tiger_win': max(0, int(self.statistic_data.get('tiger_win', 0))),
            'tie_win': max(0, int(self.statistic_data.get('tie_win', 0))),
        }
        self.statistic_data = dict(self.runtime_store['statistic_data'])
        self._write_runtime_store()

    def update_statistic_data(self, result):
        self.statistic_data['total_game'] = int(self.statistic_data.get('total_game', 0)) + 1
        if result['winner'] == 'Dragon':
            self.statistic_data['dragon_win'] = int(self.statistic_data.get('dragon_win', 0)) + 1
        elif result['winner'] == 'Tiger':
            self.statistic_data['tiger_win'] = int(self.statistic_data.get('tiger_win', 0)) + 1
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
        if self.settlement_after_id is not None:
            try:
                self.after_cancel(self.settlement_after_id)
            except (tk.TclError, ValueError):
                pass
            self.settlement_after_id = None

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
        try:
            self.engine.close()
        except Exception as exc:
            messagebox.showerror('自动洗牌机',
                                 f'退出时归还或强制洗牌失败，牌仍保留在 CSM 记录中：{exc}',
                                 parent=self.winfo_toplevel())
        self.final_balance = float(self.balance)
        try:
            self.save_balance()
        except Exception:
            pass
        if callable(self.on_back):
            self.on_back(self.final_balance)


# Backward-style wrapper for projects that expect a game class taking root.
class DragonTigerGame(BubbleDragonTigerGame):
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


# Compatibility aliases for Dragon/Tiger integrations.
DragonTigerV1 = BubbleDragonTigerGame
DragonTigerV2 = BubbleDragonTigerGame


def main(parent=None, balance=10000, user=None, on_back=None,
         on_balance_change=None, username=None, game_mode='classic'):
    """Open Dragon/Tiger embedded in a Parent page or in a standalone Tk window.

    Embedded:
        game = main(parent=parent_frame, balance=10000, user='name', on_back=callback)
        game.pack(fill='both', expand=True)

    Standalone:
        main(balance=10000, user='name')
    """
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
        return BubbleDragonTigerGame(
            parent=parent,
            balance=balance,
            user=user,
            on_back=on_back,
            on_balance_change=on_balance_change,
            game_mode=game_mode,
        )

    root = tk.Tk()
    root.title('龙虎 Dragon Tiger')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)

    def close_standalone(final_balance):
        _ = final_balance
        try:
            root.destroy()
        except tk.TclError:
            pass

    game = BubbleDragonTigerGame(
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
    main()
