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
import re
import secrets
import tkinter as tk
import sys
from datetime import datetime
from tkinter import messagebox

# Project layout compatibility (same strategy as Blackjack_Classic.py):
#   A_Tools/Card/CSM_Shuffler.py
#   Casino_Games/Baccarat_Special.py  (or A_Tools/Casino_Games/Baccarat_Special.py)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_CSM_CANDIDATES = [
    os.path.abspath(os.path.join(_THIS_DIR, '..', 'A_Tools', 'Card')),
    os.path.abspath(os.path.join(_THIS_DIR, '..', 'Card')),
    os.path.abspath(os.path.join(_THIS_DIR, 'A_Tools', 'Card')),
    _THIS_DIR,
]
_CARD_TOOLS_DIR = next(
    (path for path in _CSM_CANDIDATES
     if os.path.isfile(os.path.join(path, 'CSM_Shuffler.py'))),
    None,
)
if _CARD_TOOLS_DIR is None:
    raise ModuleNotFoundError(
        '找不到 CSM_Shuffler.py，已检查：' + '; '.join(_CSM_CANDIDATES)
    )
if _CARD_TOOLS_DIR not in sys.path:
    sys.path.insert(0, _CARD_TOOLS_DIR)

from CSM_Shuffler import ContinuousShuffleMachine  # type: ignore
from shuffle import generate_shuffled_deck  # type: ignore

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
# Baccarat rules / shoe / bet settlement
# -----------------------------------------------------------------------------
class BaccaratEngine:
    SUITS = ('Club', 'Diamond', 'Heart', 'Spade')
    RANKS = ('A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K')

    MODE_NAMES = {
        'always6': '永6点',
        'always7': '永7点',
        'always8': '永8点',
        'always9': '永9点',
        'one_deck': '单副版',
    }

    DISPLAY_NAMES = {
        'Player': '闲家',
        'Tie': '和局',
        'Banker': '庄家',
        'Pair Player': '闲家对子',
        'Pair Banker': '庄家对子',
        'Tie 0': '0',
        'Tie 1': '1',
        'Tie 2': '2',
        'Tie 3': '3',
        'Tie 4': '4',
        'Tie 5': '5',
        'Tie 6': '6',
        'Tie 7': '7',
        'Tie 8': '8',
        'Tie 9': '9',
    }

    TIE_POINT_PROFIT_ODDS = {
        'always6': {
            0: 235, 1: 275, 2: 295, 3: 275, 4: 165,
            5: 150, 6: 18, 7: 55, 8: 105, 9: 100,
        },
        'always7': {
            0: 250, 1: 300, 2: 310, 3: 275, 4: 165,
            5: 150, 6: 60, 7: 17, 8: 108, 9: 105,
        },
        'always8': {
            0: 250, 1: 300, 2: 310, 3: 275, 4: 165,
            5: 150, 6: 62, 7: 55, 8: 30, 9: 105,
        },
        'always9': {
            0: 250, 1: 300, 2: 310, 3: 275, 4: 165,
            5: 150, 6: 60, 7: 57, 8: 110, 9: 30,
        },
        'one_deck': {
            0: 180, 1: 230, 2: 245, 3: 210, 4: 130,
            5: 115, 6: 50, 7: 45, 8: 90, 9: 80,
        },
    }

    ODDS_TEXT = {
        'always6': {
            'Tie 0': '235:1', 'Tie 1': '275:1', 'Tie 2': '295:1',
            'Tie 3': '275:1', 'Tie 4': '165:1', 'Tie 5': '150:1',
            'Tie 6': '18:1', 'Tie 7': '55:1', 'Tie 8': '105:1',
            'Tie 9': '100:1',
            'Pair Player': '11:1', 'Pair Banker': '10:1',
            'Player': '1.02:1', 'Tie': '8:1', 'Banker': '0.91:1',
        },
        'always7': {
            'Tie 0': '250:1', 'Tie 1': '300:1', 'Tie 2': '310:1',
            'Tie 3': '275:1', 'Tie 4': '165:1', 'Tie 5': '150:1',
            'Tie 6': '60:1', 'Tie 7': '17:1', 'Tie 8': '108:1',
            'Tie 9': '105:1',
            'Pair Player': '11:1', 'Pair Banker': '10:1',
            'Player': '1.18:1', 'Tie': '8:1', 'Banker': '0.78:1',
        },
        'always9': {
            'Tie 0': '250:1', 'Tie 1': '300:1', 'Tie 2': '310:1',
            'Tie 3': '275:1', 'Tie 4': '165:1', 'Tie 5': '150:1',
            'Tie 6': '60:1', 'Tie 7': '57:1', 'Tie 8': '110:1',
            'Tie 9': '30:1',
            'Pair Player': '11:1', 'Pair Banker': '10:1',
            'Player': '1.65:1', 'Tie': '9:1', 'Banker': '0.56:1',
        },
        'always8': {
            'Tie 0': '250:1', 'Tie 1': '300:1', 'Tie 2': '310:1',
            'Tie 3': '275:1', 'Tie 4': '165:1', 'Tie 5': '150:1',
            'Tie 6': '62:1', 'Tie 7': '55:1', 'Tie 8': '30:1',
            'Tie 9': '105:1',
            'Pair Player': '11:1', 'Pair Banker': '10:1',
            'Player': '1.48:1', 'Tie': '9:1', 'Banker': '0.62:1',
        },
        'one_deck': {
            'Tie 0': '180:1', 'Tie 1': '230:1', 'Tie 2': '245:1',
            'Tie 3': '210:1', 'Tie 4': '130:1', 'Tie 5': '115:1',
            'Tie 6': '50:1', 'Tie 7': '45:1', 'Tie 8': '90:1',
            'Tie 9': '80:1',
            'Pair Player': '15:1', 'Pair Banker': '15:1',
            'Player': '1:1', 'Tie': '9:1', 'Banker': '0.95:1',
        },
    }

    MODE_ROWS = {
        'always6': (
            ('Tie 1', 'Tie 2', 'Tie 3', 'Tie 4', 'Tie 5', 'Tie 6', 'Tie 7', 'Tie 8'),
            ('Tie 0', 'Pair Player', 'Pair Banker', 'Tie 9'),
        ),
        'always7': (
            ('Tie 1', 'Tie 2', 'Tie 3', 'Tie 4', 'Tie 5', 'Tie 6', 'Tie 7', 'Tie 8'),
            ('Tie 0', 'Pair Player', 'Pair Banker', 'Tie 9'),
        ),
        'always9': (
            ('Tie 1', 'Tie 2', 'Tie 3', 'Tie 4', 'Tie 5', 'Tie 6', 'Tie 7', 'Tie 8'),
            ('Tie 0', 'Pair Player', 'Pair Banker', 'Tie 9'),
        ),
        'always8': (
            ('Tie 1', 'Tie 2', 'Tie 3', 'Tie 4', 'Tie 5', 'Tie 6', 'Tie 7', 'Tie 8'),
            ('Tie 0', 'Pair Player', 'Pair Banker', 'Tie 9'),
        ),
        'one_deck': (
            ('Tie 1', 'Tie 2', 'Tie 3', 'Tie 4', 'Tie 5', 'Tie 6', 'Tie 7', 'Tie 8'),
            ('Tie 0', 'Pair Player', 'Pair Banker', 'Tie 9'),
        ),
    }

    VALID_MODES = ('always6', 'always7', 'always8', 'always9', 'one_deck')
    CSM_MODES = ('always6', 'always7', 'always8', 'always9')
    _SHUFFLE_SUIT_MAP = {
        '♠': 'Spade', '♥': 'Heart', '♦': 'Diamond', '♣': 'Club',
        'Spade': 'Spade', 'Heart': 'Heart', 'Diamond': 'Diamond', 'Club': 'Club',
    }

    def __init__(self, mode='always6'):
        self.mode = mode if mode in self.VALID_MODES else 'always6'
        self.csm = None
        self.game_id = 'SPECIAL-BACCARAT-' + secrets.token_hex(12)
        self._batches = []
        self._active_round_id = None
        self._used_by_batch = {}
        self._one_deck_cards = []
        self._one_deck_index = 0
        self._one_deck_round_active = False
        if self.mode in self.CSM_MODES:
            self._ensure_csm()
            self._request_fresh_cards()

    def _ensure_csm(self):
        if self.csm is None:
            self.csm = ContinuousShuffleMachine()
        return self.csm

    def set_mode(self, mode):
        if mode not in self.VALID_MODES:
            raise ValueError('Unsupported special baccarat mode')
        self.mode = mode
        if mode in self.CSM_MODES:
            self._ensure_csm()

    def _clear_local_csm_state(self):
        self._batches = []
        self._active_round_id = None
        self._used_by_batch = {}

    def _request_fresh_cards(self):
        if self.mode == 'one_deck':
            self._one_deck_cards = []
            self._one_deck_index = 0
            self._one_deck_round_active = False
            return
        csm = self._ensure_csm()
        self.release_all_cards(force_shuffle=False)
        rid = None
        try:
            rid = csm.begin_round(self.game_id)
            packet = csm.acquire_chamber(self.game_id, rid)
            self._batches = [self._packet_to_local(packet)]
        except Exception:
            self._clear_local_csm_state()
            raise
        else:
            csm.end_round(self.game_id, rid)

    @staticmethod
    def _packet_to_local(packet):
        return {
            'batch_id': packet['batch_id'],
            'warehouse_id': packet['warehouse_id'],
            'cards': list(packet.get('cards', [])),
            'index': 0,
        }

    def fresh_lease(self):
        if self.mode in self.CSM_MODES:
            self._request_fresh_cards()
        else:
            # 单副版在每局真正开始时才调用 shuffle.py，确保每局都是全新一副牌。
            self._one_deck_cards = []
            self._one_deck_index = 0
            self._one_deck_round_active = False

    def release_all_cards(self, force_shuffle=False):
        if self.csm is not None:
            try:
                self.csm.release_game(self.game_id, force_shuffle=force_shuffle)
            except Exception:
                if self._batches:
                    raise
            finally:
                self._clear_local_csm_state()
        else:
            self._clear_local_csm_state()
        self._one_deck_cards = []
        self._one_deck_index = 0
        self._one_deck_round_active = False

    def remaining_cards(self):
        if self.mode == 'one_deck':
            return max(0, len(self._one_deck_cards) - self._one_deck_index)
        return sum(max(0, len(b['cards']) - b['index']) for b in self._batches)

    def _prepare_one_deck(self):
        raw_cards, warnings = generate_shuffled_deck(
            has_joker=False, deck_count=1, algorithm='fisher')
        if warnings:
            print('shuffle.py：' + '; '.join(str(item) for item in warnings))
        if len(raw_cards) != 52:
            raise RuntimeError(f'单副版洗牌结果应为52张，实际为{len(raw_cards)}张。')
        converted = []
        for item in raw_cards:
            suit = self._SHUFFLE_SUIT_MAP.get(str(item.get('suit', '')))
            rank = str(item.get('rank', ''))
            if suit not in self.SUITS or rank not in self.RANKS:
                raise RuntimeError(f'shuffle.py 返回无效扑克牌：{item!r}')
            converted.append((suit, rank))
        self._one_deck_cards = converted
        self._one_deck_index = 0
        self._one_deck_round_active = True

    def _draw_one_deck_card(self):
        if not self._one_deck_round_active:
            raise RuntimeError('单副版本局尚未开始。')
        if self._one_deck_index >= len(self._one_deck_cards):
            raise RuntimeError('单副版牌组已用完。')
        card = self._one_deck_cards[self._one_deck_index]
        self._one_deck_index += 1
        return card


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

    def _acquire_extra_batch(self):
        if not self._active_round_id:
            raise RuntimeError('No active CSM round')
        packet = self.csm.acquire_chamber(self.game_id, self._active_round_id)
        self._batches.append(self._packet_to_local(packet))

    def _prefetch_at_six(self):
        if not self._batches:
            self._acquire_extra_batch()
            return
        current = self._batches[0]
        remaining = max(0, len(current['cards']) - current['index'])
        if remaining <= 6 and len(self._batches) < 2:
            self._acquire_extra_batch()

    def draw_card(self):
        if self.mode == 'one_deck':
            return self._draw_one_deck_card()
        if not self._active_round_id:
            raise RuntimeError('No active CSM round')
        self._prefetch_at_six()
        while self._batches and self._batches[0]['index'] >= len(self._batches[0]['cards']):
            self._batches.pop(0)
        if not self._batches:
            self._acquire_extra_batch()
        batch = self._batches[0]
        item = batch['cards'][batch['index']]
        batch['index'] += 1
        self._used_by_batch.setdefault(batch['batch_id'], []).append(item['card_id'])
        return (item['suit'], item['rank'])

    def _fixed_banker_card(self):
        if self.mode not in self.CSM_MODES:
            raise RuntimeError('单副版没有固定庄家首张牌。')
        rank = {
            'always6': '6',
            'always7': '7',
            'always8': '8',
            'always9': '9',
        }[self.mode]
        return ('Spade', rank)

    def _complete_baccarat_draws(self, player, banker):
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
        winner = 'Player' if p_score > b_score else ('Banker' if b_score > p_score else 'Tie')
        return p_score, b_score, winner, natural

    def deal_round(self):
        if self.mode == 'one_deck':
            if self._one_deck_round_active:
                raise RuntimeError('上一局尚未完成。')

            # 每局重新调用 shuffle.py 生成完整的一副52张牌。
            self._prepare_one_deck()

            # 派牌顺序：
            # 玩家[1] → 庄家[0] → 玩家[0] → 庄家[1]
            player_1 = self.draw_card()
            banker_0 = self.draw_card()
            player_0 = self.draw_card()
            banker_1 = self.draw_card()

            # 再按照正常 hand 索引归位
            player = [player_0, player_1]
            banker = [banker_0, banker_1]

            p_score, b_score, winner, natural = self._complete_baccarat_draws(
                player, banker
            )

            return {
                'player_hand': player,
                'banker_hand': banker,
                'player_score': p_score,
                'banker_score': b_score,
                'winner': winner,
                'natural': natural,
                'reshuffled': True,
                'shoe_remaining': self.remaining_cards(),
            }

        if self._active_round_id is not None:
            raise RuntimeError('上一局尚未完成。')
        csm = self._ensure_csm()
        buffered = self._batches[0]['batch_id'] if self._batches else None
        self._active_round_id = csm.begin_round(self.game_id, buffered_batch=buffered)
        self._used_by_batch = {}
        if not self._batches:
            self._acquire_extra_batch()
        self._prefetch_at_six()

        # 永6/永7/永8/永9保留特殊规则：庄家首张固定，其他牌来自CSM。
        player = [self.draw_card()]
        banker = [self._fixed_banker_card()]
        player.append(self.draw_card())
        banker.append(self.draw_card())
        p_score, b_score, winner, natural = self._complete_baccarat_draws(player, banker)
        self._prefetch_at_six()
        return {
            'player_hand': player, 'banker_hand': banker,
            'player_score': p_score, 'banker_score': b_score,
            'winner': winner, 'natural': natural, 'reshuffled': False,
            'shoe_remaining': self.remaining_cards(),
        }

    def finish_round(self):
        if self.mode == 'one_deck':
            # 本局结束即丢弃整副牌；下一局会重新由 shuffle.py 生成并洗牌。
            self._one_deck_round_active = False
            self._one_deck_cards = []
            self._one_deck_index = 0
            return

        rid = self._active_round_id
        if rid is None:
            return
        csm = self._ensure_csm()
        try:
            for batch_id, card_ids in list(self._used_by_batch.items()):
                if card_ids:
                    csm.return_cards(self.game_id, batch_id, card_ids)
        except Exception:
            self._clear_local_csm_state()
            raise
        else:
            try:
                csm.end_round(self.game_id, rid)
            finally:
                self._active_round_id = None
                self._used_by_batch = {}
                self._batches = [b for b in self._batches if b['index'] < len(b['cards'])]


    @staticmethod
    def _pair_flags(result):
        p = result['player_hand']
        b = result['banker_hand']
        return p[0][1] == p[1][1], b[0][1] == b[1][1]

    @classmethod
    def side_return_factors(cls, result, mode):
        """Return total-return multipliers for Pair and exact Tie-point bets."""
        if mode not in cls.VALID_MODES:
            raise ValueError('Unsupported special baccarat mode')

        factors = {}
        player_pair, banker_pair = cls._pair_flags(result)
        if mode == 'one_deck':
            if player_pair:
                factors['Pair Player'] = 16.0
            if banker_pair:
                factors['Pair Banker'] = 16.0
        else:
            if player_pair:
                factors['Pair Player'] = 12.0
            if banker_pair:
                factors['Pair Banker'] = 11.0

        # Tie 0..9 wins only when the round ends in a Tie at that exact score.
        # Example: a Tie 7 wager wins only when Player 7 : Banker 7.
        if result.get('winner') == 'Tie':
            tie_point = int(result.get('player_score', -1))
            profit_odds = cls.TIE_POINT_PROFIT_ODDS[mode].get(tie_point)
            if profit_odds is not None:
                factors[f'Tie {tie_point}'] = float(profit_odds) + 1.0

        return factors


    @classmethod
    def main_return_factor(cls, bet_type, result, mode):
        """Return the total-return multiplier for Player, Tie, or Banker."""
        if mode not in cls.VALID_MODES:
            raise ValueError('Unsupported special baccarat mode')

        winner = result['winner']
        profit_odds = {
            'always6': {'Player': 1.02, 'Banker': 0.91, 'Tie': 8.0},
            'always7': {'Player': 1.18, 'Banker': 0.78, 'Tie': 8.0},
            'always9': {'Player': 1.65, 'Banker': 0.56, 'Tie': 9.0},
            'always8': {'Player': 1.48, 'Banker': 0.62, 'Tie': 9.0},
            'one_deck': {'Player': 1.0, 'Banker': 0.95, 'Tie': 9.0},
        }[mode]

        if bet_type == 'Tie':
            return 1.0 + profit_odds['Tie'] if winner == 'Tie' else 0.0
        if bet_type == 'Player':
            if winner == 'Tie':
                return 1.0
            return 1.0 + profit_odds['Player'] if winner == 'Player' else 0.0
        if bet_type == 'Banker':
            if winner == 'Tie':
                return 1.0
            return 1.0 + profit_odds['Banker'] if winner == 'Banker' else 0.0
        return 0.0

    @classmethod
    def resolve_bets(cls, bets, result, mode):
        side_factors = cls.side_return_factors(result, mode)
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

        return {
            'credit': credit,
            'gross_profit': gross_profit,
            'lost_stake': lost_stake,
            'net': gross_profit - lost_stake,
            'outcomes': outcomes,
            'side_factors': side_factors,
        }


class BaccaratBetState:
    def __init__(self):
        self.bets = {}

    def total_at_risk(self):
        return sum(float(value) for value in self.bets.values())

    def current_area_bet(self, bet_type):
        return float(self.bets.get(bet_type, 0.0))

    def add_bet(self, bet_type, amount):
        if amount <= 0:
            return False
        self.bets[bet_type] = self.current_area_bet(bet_type) + float(amount)
        return True


    def clear_area(self, bet_type):
        return float(self.bets.pop(bet_type, 0.0))

    def clear_all(self):
        amount = self.total_at_risk()
        self.bets.clear()
        return amount


# -----------------------------------------------------------------------------
# Sicbo-style embedded Canvas interface, adapted for Baccarat
# -----------------------------------------------------------------------------
class BubbleBaccaratGame(tk.Frame):
    # Special Baccarat: Always6/7/8/9 plus One Deck are supported.
    WIDTH = 1150
    HEIGHT = 750

    # V12 layout: column-scrolling bead plate and 70% larger Big Road viewport.
    GAME_X0 = 12
    GAME_X1 = 770
    HISTORY_X0 = 778
    HISTORY_X1 = 1138
    BOARD_INNER_X0 = 22
    BOARD_INNER_X1 = 760


    BG = '#17120f'
    PANEL = '#211811'
    PANEL_LINE = '#665240'
    FELT = '#083f38'
    LINE = '#c3d5ca'
    GOLD = '#e7d36c'
    PLAYER_BLUE = '#3d67d8'
    BANKER_RED = '#d94a4e'
    TIE_GREEN = '#43a665'

    # Result-area flash palette.  The dealing panels flash independently from
    # the betting spots so the winning hand is obvious even with no wager.
    PLAYER_ZONE_BASE = '#102d47'
    PLAYER_ZONE_LIGHT = '#83cfff'
    BANKER_ZONE_BASE = '#4b1e22'
    BANKER_ZONE_LIGHT = '#ff9ca2'
    TIE_FLASH_DARK = '#23874b'
    TIE_FLASH_LIGHT = '#78e49a'

    MAX_TABLE_BET = 2_000_000.0
    MAX_RECORDS = 300
    BEAD_RECORDS = 72
    BEAD_TRIM_BATCH = 6

    # Wager and winning-return chips use the same 0.2-second motion.
    CHIP_MOVE_DURATION_MS = 200
    CHIP_MOVE_STEPS = 10


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

    MODE_ORDER = ('always6', 'always7', 'always8', 'always9', 'one_deck')
    MODE_SHORT = {
        'always6': '永6点', 'always7': '永7点', 'always8': '永8点',
        'always9': '永9点', 'one_deck': '单副版',
    }

    BET_COLORS = {
        'Player': '#345fc4',
        'Tie': '#43a665',
        'Banker': '#c94349',
        'Pair Player': '#a943a6',
        'Pair Banker': '#a943a6',
    }

    # Exact Tie-point bets all use the Tie green family. Lower points are lighter;
    # higher points are progressively darker. draw_bet_spot() automatically picks
    # black or white text according to the resulting background luminance.
    TIE_POINT_COLORS = {
        'Tie 0': '#c9efd4',
        'Tie 1': '#b5e6c5',
        'Tie 2': '#a0ddb6',
        'Tie 3': '#8bd4a6',
        'Tie 4': '#76c997',
        'Tie 5': '#61bd87',
        'Tie 6': '#4cab77',
        'Tie 7': '#398d63',
        'Tie 8': '#286f50',
        'Tie 9': '#18513b',
    }

    def __init__(self, parent, balance=10000, user=None, on_back=None,
                 on_balance_change=None, game_mode='always6'):
        super().__init__(parent, bg=self.BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username = user
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.balance = float(balance)
        self.final_balance = float(balance)
        self.summary_mode = 'bet'
        self.last_win_amount = 0.0

        self.game_mode = game_mode if game_mode in self.MODE_ORDER else 'always6'
        self.engine = BaccaratEngine(self.game_mode)
        self.bet_state = BaccaratBetState()
        self.selected_chip = 1000.0
        self.last_round_bets = []
        self.bet_spots = {}
        self.chip_selector_items = {}
        self.control_buttons = {}
        self.mode_button_items = {}

        self.accept_bets = True
        self.animation_running = False
        self.settlement_running = False
        self.animation_after_ids = []
        self.chip_motion_after_ids = set()
        self.chip_motion_serial = 0
        self.pending_bet_visual_amounts = {}
        self.settlement_return_animating = False
        self.settlement_return_keys = set()
        self.settlement_after_id = None
        self.flash_mode = None
        self.flash_winning_keys = set()
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        self.flash_original_text_colors = {}
        self.pre_deal_bets = None
        self.current_result = None
        self.settlement_flash_step = 0
        self.settlement_hold_amounts = {}
        self.push_return_amounts = {}
        self.result_panel_flash_winner = None
        self._closing = False

        self.history_panel_mode = 'roads'
        self.big_road_scroll_col = 0
        self.big_road_auto_follow = True
        self.big_road_virtual_cols = 50
        self.big_road_view_cols = 14
        self.runtime_json_dir = self.get_runtime_json_dir()
        self.runtime_data_file = os.path.join(self.runtime_json_dir, 'Baccarat_Special.json')
        self.runtime_store = self.load_runtime_store()
        self.history_store = self.load_history_store()
        self.history_data = self.history_records_from_store()
        self.bead_store = self.load_bead_store()
        self.bead_data = self.bead_records_from_store()
        self.statistic_data = self.load_statistic_data()
        self.bead_show_scores = False

        # Prefer the original Baccarat artwork; fall back to generated cards.
        self.external_card_images = {}
        self.external_card_images_rotated = {}
        self.external_back_image = None
        self.card_asset_dir = None
        self.always_card_pil = {}
        self.always_card_images = {}
        self.load_original_card_assets()
        self.load_always_fixed_card_assets()

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
        """Right-side history panel with Roads/Data tabs."""
        c = self.canvas
        x0, y0, x1, y1 = self.HISTORY_X0, 4, self.HISTORY_X1, 620
        c.create_rectangle(x0, y0, x1, y1, fill=self.PANEL,
                           outline=self.PANEL_LINE, width=2, tags='static')
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
        if self.game_mode == 'one_deck':
            return '* 单副牌 · 每局洗牌'
        fixed = {'always6': '6', 'always7': '7', 'always8': '8', 'always9': '9'}[self.game_mode]
        return f'* 庄家首张固定{fixed}点'

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
                text = {'Player': '闲', 'Banker': '庄', 'Tie': '和'}.get(winner, '')
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


    def update_history_table(self):
        if not hasattr(self, 'canvas'):
            return
        self.canvas.delete('history_dynamic')
        note_item = getattr(self, 'road_asterisk_note_item', None)
        if note_item is not None:
            try:
                self.canvas.itemconfigure(note_item, text=self._asterisk_note_text())
            except tk.TclError:
                pass
        records = list(self.history_data[-self.MAX_RECORDS:])
        if self.history_panel_mode == 'data':
            self._draw_round_statistics(records)
            return
        big_cells = self._build_big_road(records)
        self._draw_big_road(big_cells)
        self._draw_derived_road('eye', self._derive_road(records, 1), 'ring')
        self._draw_derived_road('cockroach', self._derive_road(records, 3), 'slash')
        self._draw_bead_plate(list(self.bead_data))
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


    def find_always_fixed_card_path(self, filename):
        candidates = []
        if self.card_asset_dir:
            candidates.extend([
                os.path.join(self.card_asset_dir, filename),
                os.path.join(os.path.dirname(self.card_asset_dir), filename),
            ])
        current = os.path.dirname(os.path.abspath(__file__))
        candidates.extend([
            os.path.join(current, filename),
            os.path.join(current, 'A_Tools', 'Card', 'Poker1', filename),
            os.path.join(os.path.dirname(current), 'A_Tools', 'Card', 'Poker1', filename),
            os.path.join(os.path.dirname(os.path.dirname(current)), 'A_Tools', 'Card', 'Poker1', filename),
        ])
        for path in candidates:
            if path and os.path.isfile(path):
                return path
        return None

    def load_always_fixed_card_assets(self):
        self.always_card_pil = {}
        self.always_card_images = {}
        mapping = {
            'always6': ('Always6.png', ('Spade', '6')),
            'always7': ('Always7.png', ('Spade', '7')),
            'always8': ('Always8.png', ('Spade', '8')),
            'always9': ('Always9.png', ('Spade', '9')),
        }
        if Image is None or ImageTk is None:
            return
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        for mode, (filename, fallback_card) in mapping.items():
            try:
                path = self.find_always_fixed_card_path(filename)
                if path:
                    base = Image.open(path).convert('RGBA').resize((100, 140), resample)
                    self.always_card_pil[mode] = base
                    self.always_card_images[mode] = ImageTk.PhotoImage(base, master=self)
                    continue
            except Exception:
                pass
            fallback = self.external_card_pil.get(fallback_card)
            if fallback is not None:
                self.always_card_pil[mode] = fallback
                try:
                    self.always_card_images[mode] = ImageTk.PhotoImage(fallback, master=self)
                except Exception:
                    pass

    def _fixed_banker_photo(self):
        return self.always_card_images.get(self.game_mode)

    def _draw_fixed_banker_card(self):
        if not self.current_result:
            return
        card = tuple(self.current_result['banker_hand'][0])
        x, y = self.card_position('Banker', 0)
        image = self._fixed_banker_photo()
        if image is not None:
            item = self.canvas.create_image(
                x, y, image=image, anchor='nw', tags=('animation_card', 'animation'))
            self.card_item_ids.append(item)
        else:
            self.draw_card('Banker', 0, card, face_up=True)
        self.revealed_cards['Banker'] = [card]
        self.canvas.itemconfigure(
            self.banker_score_text,
            text=str(BaccaratEngine.score(self.revealed_cards['Banker'])))


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
            (x0 + x1) / 2, y0 + 18, text='特殊百家乐  SPECIAL BACCARAT',
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
        if mode == self.game_mode or mode not in self.MODE_ORDER:
            return
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return

        refund = self.bet_state.clear_all()
        if refund > 0:
            self.balance += refund
        self.pending_bet_visual_amounts.clear()

        try:
            self.engine.release_all_cards(force_shuffle=False)
            self.game_mode = mode
            self.engine.set_mode(mode)
            self.engine.fresh_lease()
        except Exception as exc:
            messagebox.showerror('牌组错误', f'切换模式时无法准备牌组：{exc}',
                                 parent=self.winfo_toplevel())
            return

        self.history_store = self.load_history_store()
        self.history_data = self.history_records_from_store()
        self.bead_store = self.load_bead_store()
        self.bead_data = self.bead_records_from_store()
        self.statistic_data = self.load_statistic_data()
        self.big_road_scroll_col = 0
        self.big_road_auto_follow = True
        self.summary_mode = 'bet'
        self.draw_mode_betting_board()
        self.update_mode_selector_style()
        self.update_history_table()
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

        # Row 1: exact Tie points 1..8.
        self.draw_bet_row(rows[0], self.BOARD_INNER_X0, 374, 430, odds)
        # Row 2: 0 | Player Pair | Banker Pair | 9.
        self.draw_bet_row(rows[1], self.BOARD_INNER_X0, 434, 494, odds)

        # Row 3 remains the original Player / Tie / Banker main-bet row.
        y0, y1 = 498, 602
        main = ('Player', 'Tie', 'Banker')
        x0, x1 = self.BOARD_INNER_X0, self.BOARD_INNER_X1
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
        fill = self.TIE_POINT_COLORS.get(
            bet_type, self.BET_COLORS.get(bet_type, '#45665c'))
        text_color = self.contrast_text_color(fill) if bet_type.startswith('Tie ') else 'white'
        rect_id = c.create_rectangle(
            x0 + 2, y0 + 2, x1 - 2, y1 - 2,
            fill=fill, outline='#d5cbbd', width=1,
            tags=('board_dynamic', tag))

        label = BaccaratEngine.DISPLAY_NAMES.get(bet_type, bet_type)
        if main:
            label_item = c.create_text(
                (x0 + x1) / 2, y0 + 27, text=label,
                font=('Arial', 23, 'bold'), fill=text_color,
                tags=('board_dynamic', tag))
            odds_item = c.create_text(
                (x0 + x1) / 2, y1 - 15, text=odds_text,
                font=('Arial', 18, 'bold'), fill=text_color,
                tags=('board_dynamic', tag))
            odds_y = y1 - 15
        else:
            label_item = c.create_text(
                (x0 + x1) / 2, y0 + 23, text=label,
                font=('Arial', 15, 'bold'), fill=text_color,
                tags=('board_dynamic', tag))
            odds_item = c.create_text(
                (x0 + x1) / 2, y1 - 13, text=odds_text,
                font=('Arial', 11, 'bold'), fill=text_color,
                tags=('board_dynamic', tag))
            odds_y = y1 - 13

        chip_y = (y0 + y1) / 2
        self.register_spot(
            bet_type, x0 + 2, y0 + 2, x1 - 2, y1 - 2,
            ((x0 + x1) / 2, chip_y), label)
        spot = self.bet_spots[(bet_type, None)]
        spot.update({
            'rect_id': rect_id, 'label_item': label_item, 'odds_item': odds_item,
            'base_odds': odds_text, 'odds_y': odds_y,
            'odds_base_x': (x0 + x1) / 2, 'main': bool(main),
            'normal_outline': '#d5cbbd', 'normal_outline_width': 1,
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
        mode_name = BaccaratEngine.MODE_NAMES[self.game_mode]
        odds = BaccaratEngine.ODDS_TEXT[self.game_mode]
        tie_odds = '  '.join(
            f'{point}点和 {odds[f"Tie {point}"]}' for point in range(10))
        if self.game_mode == 'one_deck':
            mode_rule = (
                '• 每局使用一副完整52张牌，并由 shuffle.py 重新洗牌。\n'
                '• 初始发牌/牌堆取牌顺序：玩家第1张 → 庄家第1张 → 玩家第2张 → 庄家第2张。\n'
                '• 初始四张完成后，再按标准百家乐规则补牌。\n'
            )
        else:
            fixed = {'always6': '6', 'always7': '7', 'always8': '8', 'always9': '9'}[self.game_mode]
            mode_rule = f'• 庄家第一张牌固定为黑桃{fixed}。\n'
        text = (
            '【基本规则】\n'
            '• A=1，2–9按牌面，10/J/Q/K=0，只取总点数个位。\n'
            '• 闲家0–5补牌、6–7停牌；8/9为天牌。\n'
            '• 庄家按标准第三张牌规则补牌。\n'
            '• 和局时闲家/庄家主注退回本金。\n\n'
            '【数字和局 0–9】\n'
            '• 数字代表本局最终和局点数；只有双方以该点数结束才中奖。\n'
            '• 例如下注数字7，只有本局最终为 闲7 : 庄7 才获胜。\n\n'
            f'【{mode_name}】\n'
            f'{mode_rule}'
            f'• 数字和局赔率：{tie_odds}\n'
            f"• 闲家：{odds['Player']}\n"
            f"• 和局：{odds['Tie']}\n"
            f"• 庄家：{odds['Banker']}\n"
            f"• 闲家对子：{odds['Pair Player']}\n"
            f"• 庄家对子：{odds['Pair Banker']}\n\n"
            '操作：左键下注；右键清除单区；清除按钮清空本局；Enter开牌。'
        )
        messagebox.showinfo('特殊百家乐玩法说明', text, parent=self.winfo_toplevel())


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


    def _animate_amount_chip(self, amount, start_xy, target_xy, on_complete=None):
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
            if self._closing:
                return
            ratio = min(1.0, max(0.0, step / steps))
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
            self._animate_amount_chip(amount, start, target, on_complete=one_finished)
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
        if bet_type in ('Player', 'Banker'):
            return 500_000.0
        if bet_type == 'Tie':
            return 100_000.0
        return 30_000.0


    def place_bet(self, bet_type, amount=None):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return False
        if (bet_type, None) not in self.bet_spots:
            return False
        requested = float(amount if amount is not None else self.selected_chip)

        if requested < 100.0 or abs(requested / 100.0 - round(requested / 100.0)) > 1e-9:
            messagebox.showwarning('下注单位', '下注只接受100及100的倍数。',
                                   parent=self.winfo_toplevel())
            return False

        area_current = self.bet_state.current_area_bet(bet_type)
        table_current = self.bet_state.total_at_risk()
        raw_allowed = min(
            requested,
            self.bet_limit_for(bet_type) - area_current,
            self.MAX_TABLE_BET - table_current,
            self.balance,
        )
        allowed = float(int(max(0.0, raw_allowed) // 100.0) * 100)
        if allowed < 100.0:
            return False
        if allowed < requested:
            area_remaining = max(0.0, self.bet_limit_for(bet_type) - area_current)
            table_remaining = max(0.0, self.MAX_TABLE_BET - table_current)
            clipped_by_area_limit = (
                area_remaining + 1e-9 < requested
                and area_remaining <= table_remaining + 1e-9
                and area_remaining <= self.balance + 1e-9
            )
            if not clipped_by_area_limit:
                messagebox.showwarning(
                    '下注限制', f'下注已自动调整为 {self.format_money(allowed)}。',
                    parent=self.winfo_toplevel())

        key = (bet_type, None)
        self.pending_bet_visual_amounts[key] = (
            self.pending_bet_visual_amounts.get(key, 0.0) + allowed)
        self.bet_state.add_bet(bet_type, allowed)
        self.balance -= allowed
        self.summary_mode = 'bet'
        self.update_display()

        source = self._chip_rack_source_position()
        target = tuple(self.bet_spots[key]['chip_pos'])
        self._animate_amount_chip(
            allowed, source, target,
            on_complete=lambda k=key, a=allowed: self._complete_pending_bet_visual(k, a))
        self.save_balance()
        return True

    def clear_single_bet(self, bet_type):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        refunded = self.bet_state.clear_area(bet_type)
        if refunded <= 0:
            return
        self.balance += refunded
        self.pending_bet_visual_amounts.pop((bet_type, None), None)
        self.update_display()
        self.save_balance()


    def clear_bets(self):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        refunded = self.bet_state.clear_all()
        if refunded <= 0:
            return
        self.balance += refunded
        self.pending_bet_visual_amounts.clear()
        self.update_display()
        self.save_balance()

    def snapshot_bets(self):
        return [(bet_type, None, float(amount))
                for bet_type, amount in self.bet_state.bets.items() if amount > 0]

    def repeat_last_bets(self):
        if (not self.accept_bets or self.animation_running or self.settlement_running
                or not self.last_round_bets):
            return

        self.clear_bets()
        active = {key[0] for key in self.bet_spots}
        repeatable = [(bt, p, amt) for bt, p, amt in self.last_round_bets if bt in active]
        required = sum(amt for _bt, _p, amt in repeatable)
        if self.balance + 1e-9 < required:
            messagebox.showwarning(
                '余额不足',
                f'重复上局下注需要 {self.format_money(required)}，当前余额为 {self.format_money(self.balance)}。',
                parent=self.winfo_toplevel())
            return
        for bet_type, _param, amount in repeatable:
            self.place_bet(bet_type, amount=amount)

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
            self.canvas.itemconfigure(
                self.total_bet_text,
                text=f'上局返还: {self.format_money(self.last_win_amount)}')
        else:
            self.canvas.itemconfigure(
                self.total_bet_text,
                text=f'本局下注: {self.format_money(self.bet_state.total_at_risk())}')
        self.update_bet_chips()
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


    # ---------------------------------------------------------- shoe / cut / burn


    # ------------------------------------------------------------ dealing/settle
    def handle_enter_deal(self, _event=None):
        button = self.control_buttons.get(getattr(self, 'deal_button', None))
        if button and button['enabled']:
            button['command']()
        return 'break'

    def deal_cards(self):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return

        self.accept_bets = False
        self.animation_running = True
        self.pending_bet_visual_amounts.clear()
        current_bets = self.snapshot_bets()
        if current_bets:
            self.last_round_bets = current_bets
        self.pre_deal_bets = copy.deepcopy(self.bet_state.bets)
        self.clear_card_display()
        self.current_result = None
        self.result_panel_flash_winner = None
        self.restore_result_panel_colors()
        self.canvas.itemconfigure(self.tie_flash_rect, state='hidden')
        self.update_control_states()
        self._begin_actual_round_deal()

    def _begin_actual_round_deal(self):
        if self._closing:
            return
        self.engine.set_mode(self.game_mode)
        self.current_result = self.engine.deal_round()
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
        return (self.external_card_images_rotated.get(card) if rotated
                else self.external_card_images.get(card))

    def _deal_initial_sequence_original(self):
        """Deal and reveal initial cards in the same order as the actual deck draw.

        Always6/Always7/Always8/Always9 retain the fixed Banker first card. One Deck has no fixed
        card and strictly displays P1 -> B1 -> P2 -> B2 before any third card.
        """
        self.initial_card_ids = []
        if self.game_mode == 'one_deck':
            sequence = (('Player', 1), ('Banker', 0), ('Player', 0), ('Banker', 1))
        else:
            if self.current_result:
                self._draw_fixed_banker_card()
            # Fixed Banker #1 is already visible; animate the remaining real draws.
            sequence = (('Player', 1), ('Player', 0), ('Banker', 1))

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


    def _create_scaled_flip_image(self, card, width, height, use_back=False, rotated=False):
        if Image is None or ImageTk is None:
            return self._back_photo(rotated) if use_back else self._face_photo(card, rotated)
        base = self.external_back_pil if use_back else self.external_card_pil.get(tuple(card))
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
        if rotated:
            width = orig_w
            height = max(1, int(orig_h * ratio))
        else:
            width = max(1, int(orig_w * ratio))
            height = orig_h

        image = self._create_scaled_flip_image(
            real_card, width, height, use_back=use_back, rotated=rotated)
        if image is not None:
            self._temp_flip_images[card_id] = image
            self.canvas.itemconfigure(card_id, image=image)
            target_x, target_y = self.card_position(hand_type, index)
            if rotated:
                self.canvas.coords(card_id, target_x, target_y + (orig_h - height) / 2)
            else:
                self.canvas.coords(card_id, target_x + (orig_w - width) / 2, target_y)
        self._queue_animation(
            20, self._flip_card_original, card_info, real_card, step + 1, on_complete)


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


    def finish_deal(self):
        if self._closing or not self.current_result:
            return
        self.animation_after_ids.clear()
        result = self.current_result
        self.canvas.itemconfigure(self.player_score_text, text=str(result['player_score']))
        self.canvas.itemconfigure(self.banker_score_text, text=str(result['banker_score']))

        settle = BaccaratEngine.resolve_bets(self.pre_deal_bets, result, self.game_mode)
        self.balance += settle['credit']
        self.last_win_amount = settle['credit']
        self.add_history(result)
        self.update_statistic_data(result)
        try:
            self.engine.finish_round()
        except Exception as exc:
            print(f'结束本局牌组失败：{exc}')

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

        for bet_type, factor in settle['side_factors'].items():
            key = (bet_type, None)
            if factor > 1.0 and key in self.bet_spots:
                self.flash_winning_keys.add(key)

        winner_key = (result['winner'], None)
        if winner_key in self.bet_spots:
            factor = BaccaratEngine.main_return_factor(
                result['winner'], result, self.game_mode)
            if factor > 1.0:
                self.flash_winning_keys.add(winner_key)

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

        self.settlement_flash_step = 0
        self.run_settlement_flash()


    def run_settlement_flash(self):
        if self._closing or not self.settlement_running:
            return
        if self.settlement_flash_step >= 6:
            self.settlement_after_id = None
            if not self._start_winning_chip_return():
                self.finish_settlement()
            return
        self.flash_mode = 'win' if self.settlement_flash_step % 2 == 0 else 'original'
        self.flash_result_panels(self.settlement_flash_step % 2 == 0)
        self.canvas.delete('win_flash_area')
        if self.flash_mode == 'original':
            self.restore_flash_text_colors()
        else:
            for key in self.flash_winning_keys:
                spot = self.bet_spots.get(key)
                if not spot:
                    continue
                x0, y0, x1, y1 = spot['bounds']

                # Exact Tie-point spots whose normal label/odds text is black
                # flash with the inverse palette: black background + white text.
                # Darker Tie-point spots (normal white text) keep the standard
                # white-background + black-text settlement flash.
                bet_type = key[0]
                invert_tie_point = (
                    bet_type.startswith('Tie ')
                    and self.contrast_text_color(
                        self.TIE_POINT_COLORS.get(bet_type, '#000000')) == 'black'
                )
                flash_fill = '#000000' if invert_tie_point else '#ffffff'
                flash_outline = '#ffffff' if invert_tie_point else '#111111'
                flash_text = 'white' if invert_tie_point else 'black'

                self.canvas.create_rectangle(
                    x0, y0, x1, y1, fill=flash_fill, outline=flash_outline, width=2,
                    tags=('win_flash_area', 'settlement_flash'))
                self.raise_spot_content_above_flash(spot, flash_text)
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

    def raise_spot_content_above_flash(self, spot, flash_text_color='black'):
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
                self.canvas.itemconfigure(item_id, fill=flash_text_color)
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
        self.canvas.itemconfigure(self.animation_phase_text, text='特殊百家乐  SPECIAL BACCARAT')
        self.accept_bets = True
        self.update_display()

    @classmethod
    def result_color(cls, winner):
        return {'Player': cls.PLAYER_BLUE, 'Banker': cls.BANKER_RED,
                'Tie': cls.TIE_GREEN}.get(winner, '#888888')


    # ------------------------------------------------------------------ history
    def get_runtime_json_dir(self):
        # Baccarat_Special.json is always stored relative to this game file:
        #   <current game directory>/../A_Logs/Json/Baccarat_Special.json
        target = os.path.abspath(os.path.join(_THIS_DIR, '..', 'A_Logs', 'Json'))
        os.makedirs(target, exist_ok=True)
        return target


    @staticmethod
    def _default_statistic_data():
        return {'total_game': 0, 'player_win': 0, 'banker_win': 0, 'tie_win': 0}

    @classmethod
    def new_runtime_store(cls):
        return {
            'Always6_temp_finish_data': cls.new_history_store(),
            'Always6_72_games': cls.new_history_store(),
            'Always6_statistic_data': cls._default_statistic_data(),
            'Always7_temp_finish_data': cls.new_history_store(),
            'Always7_72_games': cls.new_history_store(),
            'Always7_statistic_data': cls._default_statistic_data(),
            'Always9_temp_finish_data': cls.new_history_store(),
            'Always9_72_games': cls.new_history_store(),
            'Always9_statistic_data': cls._default_statistic_data(),
            'Always8_temp_finish_data': cls.new_history_store(),
            'Always8_72_games': cls.new_history_store(),
            'Always8_statistic_data': cls._default_statistic_data(),
            'One_Deck_temp_finish_data': cls.new_history_store(),
            'One_Deck_72_games': cls.new_history_store(),
            'One_Deck_statistic_data': cls._default_statistic_data(),
        }

    def _mode_data_prefix(self, mode=None):
        mode = mode or self.game_mode
        return {
            'always6': 'Always6',
            'always7': 'Always7',
            'always8': 'Always8',
            'always9': 'Always9',
            'one_deck': 'One_Deck',
        }.get(mode, 'Always6')

    def _write_runtime_store(self):
        try:
            os.makedirs(os.path.dirname(self.runtime_data_file), exist_ok=True)
            temp_path = self.runtime_data_file + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as handle:
                json.dump(self.runtime_store, handle, ensure_ascii=False, indent=4)
            os.replace(temp_path, self.runtime_data_file)
        except OSError as exc:
            print(f'保存 Baccarat_Special 失败：{exc}')

    def load_runtime_store(self):
        store = self.new_runtime_store()
        changed = False

        # Prefer the new Baccarat_Special.json path. If it does not exist yet,
        # import the previous Baccarat_Special.json once so existing mode
        # history/statistics are not lost during the rename/path migration.
        source_path = self.runtime_data_file
        if not os.path.isfile(source_path):
            legacy_candidates = [
                os.path.join(self.runtime_json_dir, 'Baccarat_Special.json'),
                os.path.join(_CARD_TOOLS_DIR, 'A_Logs', 'Json', 'Baccarat_Special.json'),
            ]
            for candidate in legacy_candidates:
                if os.path.isfile(candidate):
                    source_path = candidate
                    changed = True
                    break

        try:
            with open(source_path, 'r', encoding='utf-8') as handle:
                raw = json.load(handle)
            if isinstance(raw, dict):
                for key in store:
                    if isinstance(raw.get(key), dict):
                        store[key] = raw[key]
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return store

        # Every *_temp_finish_data section is capped to the latest 300 rounds,
        # including modes other than the one currently selected.
        for key in tuple(store):
            if not key.endswith('_temp_finish_data'):
                continue
            normalized = self.normalize_history_store(store.get(key))
            if normalized != store.get(key):
                store[key] = normalized
                changed = True

        # Bead Plate owns a separate rolling dataset for each mode. On the first
        # upgrade from an older JSON file, seed it from that mode's newest 72
        # temp-finish records so the existing Bead Plate history is preserved.
        for prefix in ('Always6', 'Always7', 'Always8', 'Always9', 'One_Deck'):
            bead_key = prefix + '_72_games'
            temp_key = prefix + '_temp_finish_data'
            if not isinstance(raw, dict) or bead_key not in raw:
                source_records = store.get(temp_key, {}).get('records', [])
                store[bead_key] = {'records': copy.deepcopy(source_records[-self.BEAD_RECORDS:])}
                changed = True
            else:
                normalized = self.normalize_bead_store(store.get(bead_key))
                if normalized != store.get(bead_key):
                    store[bead_key] = normalized
                    changed = True

        if changed:
            self.runtime_store = store
            self._write_runtime_store()
        return store



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
            if not isinstance(record, dict) or record.get('winner') not in ('Player','Tie','Banker'):
                continue
            item = copy.deepcopy(record)
            try:
                item['player_score'] = int(item.get('player_score', 0))
                item['banker_score'] = int(item.get('banker_score', 0))
            except (TypeError, ValueError):
                continue
            normalized['records'].append(item)
        return normalized

    def load_history_store(self):
        key = self._mode_data_prefix() + '_temp_finish_data'
        return self.normalize_history_store(self.runtime_store.get(key, self.new_history_store()))

    def save_history_store(self):
        key = self._mode_data_prefix() + '_temp_finish_data'
        self.runtime_store[key] = copy.deepcopy(self.history_store)
        self._write_runtime_store()

    def history_records_from_store(self):
        return list(self.history_store.get('records', []))

    @classmethod
    def normalize_bead_store(cls, data):
        normalized = cls.new_history_store()
        if not isinstance(data, dict):
            return normalized
        raw_records = data.get('records', [])
        if not isinstance(raw_records, list):
            return normalized
        for record in raw_records[-cls.BEAD_RECORDS:]:
            if not isinstance(record, dict) or record.get('winner') not in ('Player', 'Tie', 'Banker'):
                continue
            item = copy.deepcopy(record)
            try:
                item['player_score'] = int(item.get('player_score', 0))
                item['banker_score'] = int(item.get('banker_score', 0))
            except (TypeError, ValueError):
                continue
            normalized['records'].append(item)
        return normalized

    def load_bead_store(self):
        key = self._mode_data_prefix() + '_72_games'
        return self.normalize_bead_store(self.runtime_store.get(key, self.new_history_store()))

    def bead_records_from_store(self):
        return list(self.bead_store.get('records', []))

    def save_bead_store(self):
        key = self._mode_data_prefix() + '_72_games'
        self.runtime_store[key] = copy.deepcopy(self.bead_store)


    def add_history(self, result):
        player_pair, banker_pair = BaccaratEngine._pair_flags(result)
        record = {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'winner': result['winner'],
            'player_score': int(result['player_score']),
            'banker_score': int(result['banker_score']),
            'natural': bool(result.get('natural', False)),
            'mode': self.game_mode,
            'player_pair': bool(player_pair),
            'banker_pair': bool(banker_pair),
            'player_hand': [list(card) for card in result.get('player_hand', [])],
            'banker_hand': [list(card) for card in result.get('banker_hand', [])],
        }
        records = self.history_store.setdefault('records', [])
        records.append(record)
        self.big_road_auto_follow = True
        if len(records) > self.MAX_RECORDS:
            # Each newly completed round can exceed the 300-round cap by one.
            # Remove exactly the oldest record for this mode, preserving a
            # rolling window of the latest 300 rounds.
            del records[0]

        bead_records = self.bead_store.setdefault('records', [])
        bead_records.append(copy.deepcopy(record))
        if len(bead_records) > self.BEAD_RECORDS:
            # The Bead Plate window advances by one complete six-hand column.
            # When hand 73 arrives, remove hands 1..6 together (72 -> 67).
            del bead_records[:self.BEAD_TRIM_BATCH]

        # Persist both history datasets in one atomic JSON rewrite.
        key = self._mode_data_prefix() + '_temp_finish_data'
        self.runtime_store[key] = copy.deepcopy(self.history_store)
        self.save_bead_store()
        self._write_runtime_store()
        self.history_data = self.history_records_from_store()
        self.bead_data = self.bead_records_from_store()

    def load_statistic_data(self):
        defaults = self._default_statistic_data()
        raw = self.runtime_store.get(self._mode_data_prefix() + '_statistic_data', {})
        if isinstance(raw, dict):
            for key in defaults:
                try: defaults[key] = max(0, int(raw.get(key, 0)))
                except (TypeError, ValueError): defaults[key] = 0
        return defaults

    def save_statistic_data(self):
        data = {key: max(0, int(self.statistic_data.get(key, 0))) for key in self._default_statistic_data()}
        self.runtime_store[self._mode_data_prefix() + '_statistic_data'] = data
        self.statistic_data = dict(data)
        self._write_runtime_store()

    def update_statistic_data(self, result):
        self.statistic_data['total_game'] = int(self.statistic_data.get('total_game', 0)) + 1
        key = {'Player':'player_win', 'Banker':'banker_win', 'Tie':'tie_win'}[result['winner']]
        self.statistic_data[key] = int(self.statistic_data.get(key, 0)) + 1
        self.save_statistic_data()


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


    def on_close(self):
        self.exit_game()

    def exit_game(self):
        if self._closing:
            return

        self._closing = True

        # 停止所有尚未完成的 after / 动画回调
        self.cancel_pending_callbacks()
        self.animation_running = False
        self.accept_bets = False

        # 如果玩家还有尚未结算的下注，退出时退回余额
        outstanding = self.bet_state.total_at_risk()
        if outstanding > 0:
            self.balance += outstanding

        self.bet_state.bets.clear()
        self.final_balance = float(self.balance)

        # 保存最终余额
        try:
            self.save_balance()
        except Exception:
            pass

        # 特殊百家乐退出时，把当前占用的牌直接归还 CRE / CSM
        try:
            self.engine.release_all_cards(force_shuffle=False)
        except Exception as exc:
            print(f'CSM 退出归还失败：{exc}')

        # 与 Baccarat 一样：
        # 归还牌完成后，通过 on_back 返回上一级 tk 窗口
        if callable(self.on_back):
            self.on_back(self.final_balance)


# Backward-style wrapper for projects that expect a game class taking root.
class BaccaratGame(BubbleBaccaratGame):
    def __init__(self, root, username=None, initial_balance=10000,
                 on_back=None, on_balance_change=None, game_mode='always6'):
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
         on_balance_change=None, username=None, game_mode='always6'):
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
    root.title('特殊百家乐')
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
