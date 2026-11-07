import sys
from importlib import import_module
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_ACCOUNT_ROOT = next((p for p in (_SCRIPT_DIR, *_SCRIPT_DIR.parents)
                      if (p / 'A_Tools' / 'Account' / 'secure_json.py').is_file()), None)
_PROJECT_ROOT = _ACCOUNT_ROOT or _SCRIPT_DIR
if _ACCOUNT_ROOT is not None:
    if str(_ACCOUNT_ROOT) not in sys.path:
        sys.path.insert(0, str(_ACCOUNT_ROOT))
    _account_module = import_module('A_Tools.Account')
    _account_module.install_secure_json()
    del _account_module

import json
import math
import os
import random
import time
import uuid
from decimal import Decimal, ROUND_HALF_UP, localcontext

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont

ROOT_BG = '#1B3D31'
TEXT, RED, BLACK = '#ffffff', '#ff2a23', '#050505'
DARK_BLUE, GOLD = '#173f66', '#D4AF37'
PANEL_BG, HEADER_BG, TITLE_FG = '#F2E6C9', '#D8B46A', '#2A1B08'
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {rank: index + 2 for index, rank in enumerate(RANKS)}
SUIT_SYMBOLS = {'Spade': '♠', 'Heart': '♥', 'Diamond': '♦', 'Club': '♣',
                **{suit: suit for suit in SUITS}}
CSM_DECKS, CSM_CARD_COUNT = 8, 416


def project_root():
    return str(_PROJECT_ROOT)


def user_data_path():
    if _ACCOUNT_ROOT is None:
        raise RuntimeError('找不到原项目的加密账户组件；请使用 Guest 或放回原项目目录。')
    return os.path.join(project_root(), 'A_Tools', 'Account', 'saving_data.json')


def get_data_file_path():
    return user_data_path()


def load_user_data():
    path = get_data_file_path()
    if not os.path.isfile(path):
        raise RuntimeError('找不到现有账户资料。')
    with open(path, 'r', encoding='utf-8') as handle:
        users = json.load(handle)
    if not isinstance(users, list):
        raise ValueError('账户资料格式错误。')
    return users


def save_user_data(users):
    with open(get_data_file_path(), 'w', encoding='utf-8') as handle:
        json.dump(users, handle, ensure_ascii=False, indent=4)


def update_balance_in_json(username, new_balance):
    users = load_user_data()
    user = next((row for row in users if row.get('user_name') == username), None)
    if user is None:
        raise ValueError(f'找不到账户：{username}')
    user['cash'] = f'{_amount(new_balance):,.2f}'
    save_user_data(users)








def _make_csm():
    """Locate the original shared CSM; deliberately do not invent its internals."""
    candidates = []
    for parent in (_SCRIPT_DIR, *_SCRIPT_DIR.parents):
        for candidate in (parent / 'A_Tools' / 'Card', parent / 'Card', parent):
            if candidate not in candidates:
                candidates.append(candidate)
    found = next((path for path in candidates if (path / 'CSM_Shuffler.py').is_file()), None)
    if found is None:
        raise ModuleNotFoundError(
            '找不到 CSM_Shuffler.py。请将本档放回原项目，保留 '
            'A_Tools/Card/CSM_Shuffler.py，或将该模块放在本档旁边。'
            '\n本游戏需要原项目的8副牌／416张连续洗牌机。')
    if str(found) not in sys.path:
        sys.path.insert(0, str(found))
    machine = import_module('CSM_Shuffler').ContinuousShuffleMachine()
    # Blackjack_Classic also constructs this shared machine without arguments.
    # Do not mutate encrypted state, pass guessed constructor flags, or maintain
    # a competing local 416-card deck. Check the count if the API exposes it.
    try:
        state = machine.status()
        if isinstance(state, dict):
            decks = state.get('decks', state.get('num_decks'))
            if decks is not None and int(decks) != CSM_DECKS:
                raise ValueError('现有 CSM 不是8副牌，请先在原项目设定为8副牌／416张。')
            total = state.get('total_cards')
            if total is not None and int(total) != CSM_CARD_COUNT:
                raise ValueError('现有 CSM 的总牌数不是416张，请先检查8副完整牌设定。')
    except (AttributeError, NotImplementedError):
        pass
    return machine


class Card:
    def __init__(self, suit, rank, card_id=None, batch_id=None):
        suit = SUIT_SYMBOLS.get(suit, suit)
        rank = str(rank)
        if suit not in SUITS or rank not in RANK_VALUES:
            raise ValueError('无效的扑克牌。')
        self.suit, self.rank, self.value = suit, rank, RANK_VALUES[rank]
        self.card_id, self.batch_id = card_id, batch_id

    def __repr__(self):
        return f'{self.rank}{self.suit}'


class CSMDeck:
    """Blackjack_Classic's CSM lifecycle, with Card objects and audit metadata.

    Keep the remaining chamber between rounds. At <=3 buffered cards request
    the next chamber exactly as BlackjackEngine does; the shared CSM owns the
    lease/remainder policy. Return only actual drawn card_ids grouped by batch.
    On exit release_game(force_shuffle=True) also releases unused chamber cards.
    """
    def __init__(self, csm=None, game_id=None):
        self.decks = CSM_DECKS
        self.total_cards = CSM_CARD_COUNT
        self.csm = _make_csm() if csm is None else csm
        self.game_id = str(game_id or f'HiLo:local:{uuid.uuid4().hex}')
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
            self._clear_local_csm_state()
            raise

    def _request_next_chamber(self):
        packet = self.csm.acquire_chamber(self.game_id, self.round_id)
        self.current_batch_id = packet['batch_id']
        self.card_buffer = list(packet['cards'])
        if not self.card_buffer:
            raise RuntimeError('自动洗牌机返回了空仓。')

    def remaining_cards(self):
        return len(self.card_buffer) + self.csm.available_cards()

    def needs_shuffle(self):
        return False

    def draw_card(self):
        if not self.round_open:
            raise RuntimeError('牌局尚未开始。')
        try:
            if len(self.card_buffer) <= 3:
                self._request_next_chamber()
            record = self.card_buffer[0]
            card = Card(record['suit'], record['rank'], record['card_id'], self.current_batch_id)
            self.card_buffer.pop(0)
            self.used_by_batch.setdefault(self.current_batch_id, []).append(record['card_id'])
            return card
        except Exception:
            # The CSM may have rebuilt its warehouses. Never reuse stale IDs.
            self._clear_local_csm_state()
            raise

    def deal(self, n=1):
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError('发牌数量必须为正整数。')
        return [self.draw_card() for _ in range(n)]

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
            # Do not end an erased round after automatic CSM recovery.
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
            self.csm.release_game(self.game_id, force_shuffle=True)
        finally:
            self._clear_local_csm_state()


# Ordinary HiLo rules. Money is held in integer cents; no float multiplication.
ZERO = Decimal('0.00')
ACTION_LABELS = {'ge': '大于等于', 'le': '小于等于', 'eq': '等于',
                 'gt': '大于', 'lt': '小于', 'skip': '过牌', 'cash_out': '兑现'}
PRICING_POOL = 415
CARDS_PER_RANK = 32
SAME_RANK_CARDS = 31

# Precomputed once from the former 415-card formula, HALF_UP to 2dp.
# (action, favorable cards, gross x100, net odds x100, probability percent x100)
# Gameplay reads these literals; it does not calculate odds or probabilities.
FIXED_HILO_ODDS = {
    '2': (('gt', 384, 108, 8, 9253), ('eq', 31, 1339, 1239, 747)),
    '3': (('ge', 383, 108, 8, 9229), ('le', 63, 659, 559, 1518)),
    '4': (('ge', 351, 118, 18, 8458), ('le', 95, 437, 337, 2289)),
    '5': (('ge', 319, 130, 30, 7687), ('le', 127, 327, 227, 3060)),
    '6': (('ge', 287, 145, 45, 6916), ('le', 159, 261, 161, 3831)),
    '7': (('ge', 255, 163, 63, 6145), ('le', 191, 217, 117, 4602)),
    '8': (('ge', 223, 186, 86, 5373), ('le', 223, 186, 86, 5373)),
    '9': (('ge', 191, 217, 117, 4602), ('le', 255, 163, 63, 6145)),
    '10': (('ge', 159, 261, 161, 3831), ('le', 287, 145, 45, 6916)),
    'J': (('ge', 127, 327, 227, 3060), ('le', 319, 130, 30, 7687)),
    'Q': (('ge', 95, 437, 337, 2289), ('le', 351, 118, 18, 8458)),
    'K': (('ge', 63, 659, 559, 1518), ('le', 383, 108, 8, 9229)),
    'A': (('eq', 31, 1339, 1239, 747), ('lt', 384, 108, 8, 9253)),
}


def _amount(value):
    if isinstance(value, bool):
        raise ValueError('金额必须是有效数字。')
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0:
            raise ValueError
        with localcontext() as context:
            context.prec = max(28, len(number.as_tuple().digits) + max(0, number.adjusted()) + 8)
            rounded = number.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        if rounded != number:
            raise ValueError('金额最多保留两位小数。')
        return rounded
    except (ValueError, TypeError, ArithmeticError):
        raise ValueError('金额必须是有限非负数，最多两位小数。') from None


def _money(value):
    number = Decimal(str(value))
    with localcontext() as context:
        context.prec = max(28, len(number.as_tuple().digits) + max(0, number.adjusted()) + 8)
        return number.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def _cents(value):
    value = _amount(value)
    with localcontext() as context:
        context.prec = max(28, len(value.as_tuple().digits) + 8)
        return int(value * 100)


def _from_cents(value):
    sign = '-' if value < 0 else ''
    whole, fraction = divmod(abs(value), 100)
    return Decimal(f'{sign}{whole}.{fraction:02d}')


def _sum_amounts(values):
    return _from_cents(sum(_cents(value) for value in values))


def _add_money(first, second):
    return _from_cents(_cents(first) + _cents(second))


def _subtract_money(first, second):
    return _from_cents(_cents(first) - _cents(second))


def _external_amount(value):
    """Preserve host float callbacks only when no monetary digits are lost."""
    result = float(value)
    return result if math.isfinite(result) and Decimal(str(result)) == value else value


class RollingCSMDeck(CSMDeck):
    """Retain all displayed physical cards until they leave the left side.

    Each draw and each group of returned cards uses a short machine round.
    Returned groups re-enter circulation after end_round. Unused <=3-card
    chamber tails are returned before acquiring a replacement chamber.
    """
    def start_round(self):
        carry = {batch: list(ids) for batch, ids in self.used_by_batch.items()}
        super().start_round()
        self.used_by_batch = carry

    def _request_next_chamber(self):
        if self.card_buffer:
            try:
                self.csm.return_cards(self.game_id, self.current_batch_id,
                    [record['card_id'] for record in self.card_buffer])
                self.card_buffer = []
            except Exception:
                self._clear_local_csm_state()
                raise
        super()._request_next_chamber()
        if len(self.card_buffer) <= 3:
            raise RuntimeError('CSM返回的牌仓不足4张，无法沿用剩余3张时取下一仓的规则。')

    def _open_return_step(self):
        if self.round_open:return
        try:
            self.round_id=self.csm.begin_round(self.game_id,
                self.current_batch_id if self.card_buffer else None)
            self.round_open=True
        except Exception:
            self._clear_local_csm_state()
            raise

    def recycle_cards(self, cards):
        cards=list(cards)
        if not cards:return
        grouped={};seen=set()
        for card in cards:
            if card.card_id in seen or card.card_id not in self.used_by_batch.get(card.batch_id, []):
                raise RuntimeError('实体牌不在持有记录中，不能重复还牌。')
            seen.add(card.card_id)
            grouped.setdefault(card.batch_id, []).append(card.card_id)
        opened=not self.round_open
        self._open_return_step()
        try:
            for batch, ids in grouped.items():
                self.csm.return_cards(self.game_id,batch,ids)
                self.used_by_batch[batch]=[item for item in self.used_by_batch[batch] if item not in ids]
                if not self.used_by_batch[batch]:self.used_by_batch.pop(batch)
            if opened:self.finish_step()
        except Exception:
            self._clear_local_csm_state()
            raise

    def recycle(self, card):
        self.recycle_cards([card])

    def finish_step(self):
        if not self.round_open:
            raise RuntimeError('CSM取牌回合尚未开始。')
        try:
            self.csm.end_round(self.game_id, self.round_id)
        except Exception:
            self._clear_local_csm_state()
            raise
        self.round_id = None
        self.round_open = False

    def finish_round(self):
        if not self.round_open and self.used_by_batch:
            self._open_return_step()
        super().finish_round()


def hilo_offers(card_or_rank):
    rank = card_or_rank.rank if isinstance(card_or_rank, Card) else str(card_or_rank)
    if rank not in FIXED_HILO_ODDS:
        raise ValueError('无效的牌点。')
    result = []
    for action, favorable, multiplier_cents, net_cents, probability_cents in FIXED_HILO_ODDS[rank]:
        result.append(dict(action=action, label=ACTION_LABELS[action], favorable=favorable,
            total=415, multiplier_cents=multiplier_cents,
            multiplier=_from_cents(multiplier_cents),
            profit_odds=_from_cents(net_cents),
            probability_percent=_from_cents(probability_cents)))
    return result


def matches_prediction(action, previous, following):
    first = previous.value if isinstance(previous, Card) else RANK_VALUES[str(previous)]
    second = following.value if isinstance(following, Card) else RANK_VALUES[str(following)]
    if action == 'ge': return second >= first
    if action == 'le': return second <= first
    if action == 'eq': return second == first
    if action == 'gt': return second > first
    if action == 'lt': return second < first
    raise ValueError('无效的预测。')


class HiLoGame:
    SEATS = ('Player1', 'Player2', 'Player3')
    HAND_IDS = SEATS
    BET_KINDS = ('main',)

    def __init__(self, deck=None):
        self.deck = RollingCSMDeck() if deck is None else deck
        self.reset_game()

    @staticmethod
    def empty_bet():
        return {'main': ZERO}

    @property
    def active_hands(self):
        return [seat for seat in self.SEATS if self.bets[seat]['main']]

    @property
    def current_card(self):
        return self.cards[-1] if self.cards else None

    def pot(self, seat):
        return _from_cents(self.pot_cents[seat])

    def reset_game(self):
        if getattr(self, 'stage', None) in ('seed_ready', 'decision', 'ready'):
            raise ValueError('请先完成本局。')
        self.round_key = uuid.uuid4().hex
        self.cards, self.deal_events, self.decisions, self.return_events = [], [], [], []
        self.table_start=0
        self.bets = {seat: self.empty_bet() for seat in self.SEATS}
        self.states = {seat: 'inactive' for seat in self.SEATS}
        self.pot_cents = {seat: 0 for seat in self.SEATS}
        self.choices = {seat: None for seat in self.SEATS}
        self.wins = {seat: 0 for seat in self.SEATS}
        self.skips = {seat: 0 for seat in self.SEATS}
        self.last_outcomes = {seat: '' for seat in self.SEATS}
        self.stage, self.settlement, self.abort_reason = 'betting', None, None

    @classmethod
    def validate_bets(cls, bets, balance, high_bet_mode=False):
        if not isinstance(bets, dict) or set(bets) - set(cls.SEATS):
            raise ValueError('下注包含不支持的位置。')
        minimum, maximum = (100, 50000) if high_bet_mode else (10, 10000)
        prepared = {}
        for seat in cls.SEATS:
            row = bets.get(seat, {})
            if not isinstance(row, dict) or set(row) - {'main'}:
                raise ValueError('普通HiLo只使用主注。')
            stake = _amount(row.get('main', 0))
            if stake and not minimum <= stake <= maximum:
                raise ValueError(f'每手主注须为 ${minimum:,} 至 ${maximum:,}。')
            prepared[seat] = {'main': stake}
        cost = _sum_amounts(row['main'] for row in prepared.values())
        if not cost:
            raise ValueError('请至少选择一手主注。')
        if cost > _amount(balance):
            raise ValueError('余额不足以支付本局下注。')
        return prepared, cost

    def start_round(self, bets, balance, high_bet_mode=False):
        if self.stage != 'betting':
            raise ValueError('上一局尚未结束。')
        prepared, cost = self.validate_bets(bets, balance, high_bet_mode)
        self.deck.start_round()
        self.bets = prepared
        for seat in self.SEATS:
            self.pot_cents[seat] = _cents(prepared[seat]['main'])
            self.states[seat] = 'pending' if self.pot_cents[seat] else 'inactive'
        self.stage = 'seed_ready'
        return cost

    def _record_card(self, card, outcomes, seed=False):
        self.cards.append(card)
        self.deal_events.append(dict(index=len(self.cards), card=str(card), rank=card.rank,
            suit=card.suit, card_id=card.card_id, batch_id=card.batch_id,
            seed=seed, outcomes=outcomes))

    def reveal_initial(self):
        if self.stage != 'seed_ready':
            raise ValueError('当前不是起始牌阶段。')
        card = self.deck.draw_card()
        self.deck.finish_step()
        self._record_card(card, {}, seed=True)
        self.stage = 'decision'
        return card

    def offers(self):
        return hilo_offers(self.current_card) if self.current_card else []

    def legal_actions(self, seat):
        if self.stage != 'decision' or self.states.get(seat) != 'pending':
            return ()
        actions=tuple(row['action'] for row in self.offers())+('skip',)
        if self.pot_cents[seat]>_cents(self.bets[seat]['main']):actions+=('cash_out',)
        return actions

    def _apply_choice(self, seat, action):
        self.decisions.append(dict(seat=seat, after_card=len(self.cards), action=action,
                                   held=str(self.pot(seat))))
        if action == 'cash_out':
            self.states[seat], self.choices[seat] = 'cashed_out', None
            self.last_outcomes[seat] = 'cash_out'
        else:
            self.states[seat], self.choices[seat] = 'ready', action

    def _refresh_stage(self):
        if any(state == 'pending' for state in self.states.values()):
            self.stage = 'decision'
        elif any(state == 'ready' for state in self.states.values()):
            self.stage = 'ready'
        else:
            self.stage = 'complete'

    def decide(self, seat, action):
        if action not in self.legal_actions(seat):
            raise ValueError('当前不能进行该操作。')
        self._apply_choice(seat, action)
        self._refresh_stage()

    def decide_all(self, action):
        """Apply one choice to undecided hands; previously made choices stay locked."""
        legal = tuple(row['action'] for row in self.offers()) + ('skip', 'cash_out')
        if self.stage != 'decision' or action not in legal:
            raise ValueError('当前不能进行全部操作。')
        seats = [seat for seat in self.SEATS if action in self.legal_actions(seat)]
        if not seats:raise ValueError('没有可以进行该操作的未选择手牌。')
        for seat in seats:
            self._apply_choice(seat, action)
        self._refresh_stage()
        return seats

    def draw_next(self):
        if self.stage != 'ready':
            raise ValueError('请先完成所有仍在局中的手牌决定。')
        previous = self.current_card
        offers = {row['action']: row for row in self.offers()}
        held_ids={card_id for ids in self.deck.used_by_batch.values() for card_id in ids}
        self.deck.start_round()
        card = self.deck.draw_card()
        if card.card_id is not None and card.card_id in held_ids:
            # The lease is inconsistent. A forced release must recover it;
            # do not try returning either copy with a stale batch record.
            self.deck._clear_local_csm_state()
            raise RuntimeError('CSM重复发出了仍在桌面的实体牌。')
        self.deck.finish_step()
        outcomes = {}
        for seat in self.SEATS:
            if self.states[seat] != 'ready':
                continue
            action, before = self.choices[seat], self.pot_cents[seat]
            multiplier = None
            if action == 'skip':
                result = 'skip'
                self.skips[seat] += 1
                self.states[seat] = 'pending'
            elif matches_prediction(action, previous, card):
                multiplier = offers[action]['multiplier_cents']
                self.pot_cents[seat] = (before * multiplier + 50) // 100
                self.wins[seat] += 1
                self.states[seat], result = 'pending', 'win'
            else:
                self.pot_cents[seat] = 0
                self.states[seat], result = 'lost', 'loss'
            self.choices[seat] = None
            self.last_outcomes[seat] = result
            outcomes[seat] = dict(action=action, result=result,
                before=str(_from_cents(before)), after=str(self.pot(seat)),
                multiplier=None if multiplier is None else str(_from_cents(multiplier)))
        self._record_card(card, outcomes)
        self._refresh_stage()
        return card

    def recycle_before(self, first_visible):
        """Return only the contiguous history prefix removed by the card row."""
        if (isinstance(first_visible,bool) or not isinstance(first_visible,int)
                or not self.table_start<=first_visible<=max(0,len(self.cards)-3)):
            raise ValueError('还牌范围必须保留最新牌及前两张。')
        cards=self.cards[self.table_start:first_visible]
        self.deck.recycle_cards(cards)
        if cards:
            self.return_events.append(dict(after_card=len(self.cards),
                indices=list(range(self.table_start+1,first_visible+1)),
                cards=[dict(card_id=card.card_id,batch_id=card.batch_id) for card in cards]))
        self.table_start=first_visible

    def abort_round(self, reason):
        if self.stage == 'betting' or self.settlement is not None:
            return
        self.abort_reason = str(reason)
        for seat in self.active_hands:
            if self.states[seat] in ('pending', 'ready'):
                self.states[seat], self.choices[seat] = 'void', None
                self.last_outcomes[seat] = 'void'
        self.stage = 'complete'

    def resolved_return(self, seat):
        return self.pot(seat) if self.states[seat] in ('cashed_out', 'void') else ZERO

    def settle(self):
        if self.settlement is not None:
            return self.settlement
        if self.stage != 'complete':
            raise ValueError('本局尚有未完成的决定。')
        hands = {}
        for seat in self.active_hands:
            stake, returned = self.bets[seat]['main'], self.resolved_return(seat)
            hands[seat] = dict(state=self.states[seat], stake=stake, returned=returned,
                net=_subtract_money(returned, stake), wins=self.wins[seat], skips=self.skips[seat])
        stake = _sum_amounts(row['stake'] for row in hands.values())
        returned = _sum_amounts(row['returned'] for row in hands.values())
        self.settlement = dict(hands=hands, stake=stake, returned=returned,
            net=_subtract_money(returned, stake), card_count=len(self.cards), abort_reason=self.abort_reason)
        self.stage = 'settled'
        return self.settlement


def _json_safe(value):
    if isinstance(value, Decimal): return format(value, '.2f')
    if isinstance(value, dict): return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)): return [_json_safe(item) for item in value]
    return value


def save_hilo_history(game, result):
    directory = Path(project_root()) / 'A_Logs' / 'Json'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'HiLo.json'
    data = dict(history_record=dict(game=0, win=0, loss=0, skip=0), history=[])
    if path.is_file():
        with path.open('r', encoding='utf-8') as handle:
            data = json.load(handle)
        if not isinstance(data, dict) or not isinstance(data.get('history'), list):
            raise ValueError('HiLo历史资料格式错误。')
    if any(row.get('round_key') == game.round_key for row in data['history']):
        return
    stats = data.setdefault('history_record', {})
    for key in ('game', 'win', 'loss', 'skip'): stats.setdefault(key, 0)
    stats['game'] += 1
    stats['win'] += sum(game.wins.values())
    stats['skip'] += sum(game.skips.values())
    stats['loss'] += sum(state == 'lost' for state in game.states.values())
    data['history'].append(_json_safe(dict(
        game_id=max((row.get('game_id', 0) for row in data['history']), default=0) + 1,
        round_key=game.round_key, timestamp=time.strftime('%Y-%m-%d %H:%M:%S'),
        rules=dict(rank_order=RANKS, pricing_pool=415, same_rank=31, other_rank=32,
                   gross_multiplier='fixed table, precomputed ROUND_HALF_UP 2dp',
                   unlimited_decisions=True, skip_changes_money=False),
        shoe=dict(mode='CSM', decks=8, total_cards=416, game_id=game.deck.game_id),
        bets=game.bets, deal_events=game.deal_events, return_events=game.return_events,
        decisions=game.decisions, result=result)))
    data['history'] = data['history'][-50:]
    with path.open('w', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=4)


class HiLoGUI(tk.Frame):
    WIDTH, HEIGHT = 1150, 750
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    ROW_CAPACITY, ROW_STEP, ROW_X, ROW_Y = 10, 112, 30, 325
    BET_CHIP_RADIUS = 16 * 4 / 3
    HOUSE_CHIP_POS = (575, 45)
    SEAT_BOUNDS = {'Player1': (22, 378), 'Player2': (396, 752), 'Player3': (770, 1128)}

    def __init__(self, parent, initial_balance, username='Guest', on_back=None,
                 on_balance_change=None, *, deck=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = username, _amount(initial_balance)
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game = HiLoGame(deck if deck is not None else RollingCSMDeck(
            game_id=f'HiLo:{username or "local"}:{uuid.uuid4().hex}'))
        self.engine = self.game.deck
        self.bets = {seat: self.game.empty_bet() for seat in self.game.SEATS}
        self.last_bet, self.last_win = None, ZERO
        self.high_bet_mode, self.selected_chip = False, Decimal('10')
        self._jobs, self._closing = set(), False
        self._pending_balance_action, self._saving_balance = None, False
        self._restart_job = self._restart_deadline = None
        self._motion_count = self._chip_serial = 0
        self._phase_busy = self._decision_busy = self._settlement_started = False
        self._round_paid = False
        self._machine_fault = self._machine_released = self._history_available = False
        self._claimed_returns = {seat: ZERO for seat in self.game.SEATS}
        self._display_pots = {seat: ZERO for seat in self.game.SEATS}
        self._shown_draws, self._visible_card = 0, None
        self._visible_wins = self._visible_skips = 0
        self._face_photos, self._pil_cards, self._flip_photos = {}, {}, {}
        self.card_items, self.bet_spots, self.action_buttons = {}, {}, {}
        self.slot_labels, self._window_start, self._scrolling = {}, 0, False
        self.visual_chips, self.last_round_snapshot = {}, None
        self.card_poses = {}
        import tkinter.font as tkfont
        families = set(tkfont.families(self))
        self.cn_font = next((name for name in ('Microsoft YaHei UI', 'Microsoft YaHei',
            'Noto Sans CJK SC', 'WenQuanYi Zen Hei', 'Arial Unicode MS') if name in families), 'Arial')
        self._load_assets()
        self._create_widgets()
        self._refresh()
        self.bind('<Destroy>', self._on_destroy, add='+')

    @property
    def game_in_progress(self):
        return self.game.stage != 'betting' or self._motion_count > 0

    def _text(self, x, y, text, size=12, color=TEXT, **kwargs):
        return self.canvas.create_text(x, y, text=text, fill=color,
                                      font=(self.cn_font, size, 'bold'), **kwargs)

    def _create_widgets(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=ROOT_BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.control_buttons = {}
        c = self.canvas
        self._text(575, 28, 'HiLo', 27, GOLD)
        self._text(575, 65, 'CSM · 8副牌 / 416张', 12, PANEL_BG)
        self.status_item = self._text(575, 108, '', 17, GOLD, width=400, justify='center')
        c.create_rectangle(800,12,1128,244,fill='#123C30',outline=GOLD,width=2)
        self._text(964,33,'本局累计',13,GOLD)
        self.stat_items = []
        for y, caption in ((75,'发牌次数'),(115,'成功手次'),(155,'过牌手次'),(199,'桌面返还合计')):
            self._text(818,y,caption,11,PANEL_BG,anchor='w')
            self.stat_items.append(self._text(1110,y,'',12,GOLD,anchor='e'))
        self._draw_limit_table()
        c.create_rectangle(22,261,1128,301,fill='#173C2E',outline='#65784B')
        self._text(575,281,'2 < 3 < … < 10 < J < Q < K < A    ·    可过牌    ·    有盈利可兑现    ·    次数不限',14,GOLD)
        self._reset_card_row()
        self.pot_items = {}
        for seat,(x0,x1) in self.SEAT_BOUNDS.items():
            cx,cy = x0+64,541
            tag = f'spot_{seat}_main'
            border = c.create_oval(cx-40,cy-40,cx+40,cy+40,fill='#327057',outline=PANEL_BG,width=2,tags=tag)
            label = self._text(cx,cy,'主注',15,PANEL_BG,tags=tag)
            self.bet_spots[(seat,'main')] = dict(tag=tag,center=(cx,cy),border=border,label_item=label,label='主注')
            c.tag_bind(tag,'<Button-1>',lambda _e,s=seat:self.add_chip_to_bet(s))
            c.tag_bind(tag,'<Button-3>',lambda _e,s=seat:self.reset_single_bet(s))
            self.pot_items[seat] = self._text(cx,604,'',10,GOLD,width=126)
            for index,left in enumerate((x0+131,x0+244)):
                self.action_buttons[(seat,f'predict{index}')] = self.create_control_button(
                    left,474,left+103,537,'',lambda s=seat,i=index:self._choose_option(s,i),
                    '#397A48' if index==0 else DARK_BLUE,font_size=11,
                    subtext=' ',subtext_font_size=10,draw_shadow=False)
            for action,left,caption,fill in (('skip',x0+131,'过牌','#536A43'),
                                              ('cash_out',x0+244,'兑现',HEADER_BG)):
                self.action_buttons[(seat,action)] = self.create_control_button(
                    left,555,left+103,601,caption,lambda s=seat,a=action:self._decide(s,a),fill,
                    fg=TITLE_FG if action=='cash_out' else TEXT,font_size=12,draw_shadow=False)
        bounds=list(self.SEAT_BOUNDS.values())
        for (_,right),(next_left,_) in zip(bounds,bounds[1:]):
            x=(right+next_left)/2
            c.create_line(x,454,x,617,fill='#8FA68E',width=1,dash=(5,5))
        self._draw_bottom_controls()

    def _panel_box(self, x0, y0, x1, y1, radius=10, **options):
        """A soft corner panel drawn with native Canvas items only."""
        points = (x0+radius,y0, x1-radius,y0, x1,y0, x1,y0+radius,
                  x1,y1-radius, x1,y1, x1-radius,y1, x0+radius,y1,
                  x0,y1, x0,y1-radius, x0,y0+radius, x0,y0)
        return self.canvas.create_polygon(*points, smooth=True, splinesteps=24,
                                          tags='insight_panel', **options)

    def _refresh_insight_panel(self):
        """Swap tips, offers and the round report without flashing each frame."""
        stage = self.game.stage
        if stage == 'betting':
            mode = 'betting'
        elif self._phase_busy and not self._settlement_started:
            mode = 'dealing'
        elif self._settlement_started or stage in ('complete', 'settled'):
            mode = 'settlement'
        else:
            mode = 'offers' if self._visible_card else 'dealing'
        total = _sum_amounts(row['main'] for row in self.bets.values())
        key = (mode, self.game.round_key, total, self.selected_chip,
               str(self._visible_card), len(self.game.cards), self._round_paid,
               tuple(self.game.states.items()), tuple(self.game.choices.items()),
               self._pending_balance_action is not None,
               bool(self._motion_count or self._decision_busy))
        if key == getattr(self, '_insight_key', None):
            return
        self._insight_key = key
        c = self.canvas
        c.delete('insight_panel')
        self._panel_box(22,12,350,244,fill='#12372D',outline='#527662',width=1)
        c.create_line(42,13,92,13,fill=GOLD,width=3,tags='insight_panel')
        muted, cream = '#AAC1B2', '#F5EEDB'

        def label(x, y, value, size=11, color=cream, **options):
            return self._text(x,y,value,size,color,tags='insight_panel',**options)

        def money(value):
            return f'${value:,.2f}' if value < 1000000 else '$'+self._compact(value)

        if mode == 'betting':
            count = sum(bool(row['main']) for row in self.bets.values())
            label(42,35,'牌桌热身',13,GOLD,anchor='w')
            label(330,35,'准备开局',9,muted,anchor='e')
            label(42,77,'下一张，会是什么？',16,anchor='w')
            for left,right in ((38,178),(190,334)):
                self._panel_box(left,106,right,162,8,fill='#1D4738',outline='')
            label(50,120,'已选主注',9,muted,anchor='w')
            label(50,145,f'{count} / 3 手',14,anchor='w')
            label(202,120,'本局下注',9,muted,anchor='w')
            label(202,145,money(total),12,GOLD,anchor='w')
            tips = ('花色只负责颜值，牌点决定大小。',
                    '2 最小，A 最大；中间牌同点也算赢。',
                    '三手独立做决定，共用下一张新牌。',
                    '过牌只换参考牌，累计金额保持不变。')
            tip_index = int(total / max(Decimal('1'), _amount(self.selected_chip))) % len(tips)
            label(42,182,'桌边小知识',9,GOLD,anchor='w')
            label(42,201,tips[tip_index],10,muted,anchor='nw',width=286,justify='left')
        elif mode == 'settlement':
            result = self.game.settlement
            returned = result['returned'] if result else _sum_amounts(
                self.game.resolved_return(seat) for seat in self.game.SEATS)
            net = result['net'] if result else _subtract_money(returned,total)
            badge = ('' if self._round_paid else '待保存' if
                     self._pending_balance_action is not None else '结算中')
            label(42,35,'本局战报',13,GOLD,anchor='w')
            label(330,35,badge,9,muted,anchor='e')
            label(42,67,'安全收官 · 本局退回' if self.game.abort_reason else '牌局落幕 · 本局返还',10,muted,anchor='w')
            label(42,99,money(returned),21,GOLD,anchor='w')
            label(42,138,'本局净额',10,muted,anchor='w')
            sign = '+' if net > 0 else '−' if net < 0 else ''
            label(330,138,sign+money(abs(net)),12,
                  '#96D3B1' if net >= 0 else '#E5B0A5',anchor='e')
            c.create_line(42,158,330,158,fill='#365C49',tags='insight_panel')
            label(42,180,'猜中手次',10,muted,anchor='w')
            label(168,180,str(sum(self.game.wins.values())),13,anchor='e')
            label(198,180,'过牌手次',10,muted,anchor='w')
            label(330,180,str(sum(self.game.skips.values())),13,anchor='e')
            footer = ('右键「再来一局」回看完整牌序' if self._round_paid
                      else '全部主注结束，筹码统一返回下注区')
            label(42,214,footer,9,muted,anchor='w',width=286)
        elif mode == 'dealing':
            label(42,35,'下一张，见真章',13,GOLD,anchor='w')
            label(42,78,'所有选择已锁定' if self._visible_card else '先翻开一张参考牌',14,anchor='w')
            self._panel_box(38,105,334,177,8,fill='#1D4738',outline='')
            for index,suit in enumerate(SUITS):
                label(75+index*73,140,suit,27,'#D8A49A' if suit in '♥♦' else '#D3C59A')
            label(42,204,f'正在翻开第 {max(1,len(self.game.cards))} 张牌…',10,muted,anchor='w')
        else:
            card = self._visible_card
            label(42,35,'下一张预测',13,GOLD,anchor='w')
            label(330,35,f'参考 {card.rank}{card.suit}',11,
                  '#E5B0A5' if card.suit in '♥♦' else cream,anchor='e')
            arrows = {'ge':'↑','gt':'↑','le':'↓','lt':'↓','eq':'='}
            for index,offer in enumerate(hilo_offers(card)):
                top = 60+index*82
                accent = '#91CFAB' if index == 0 else '#9FC5E0'
                self._panel_box(38,top,334,top+72,8,fill='#1D4738',outline='#355C49',width=1)
                label(50,top+18,f"{arrows[offer['action']]}  {offer['label']}",12,anchor='w')
                label(322,top+18,f"{offer['multiplier']:.2f}×",14,GOLD,anchor='e')
                label(50,top+40,f"胜率 {offer['probability_percent']:.2f}%",9,muted,anchor='w')
                label(322,top+40,f"净赢 {offer['profit_odds']:.2f}:1",9,muted,anchor='e')
                c.create_line(51,top+58,321,top+58,fill='#102D24',width=4,tags='insight_panel')
                end = 51+270*float(offer['probability_percent'])/100
                c.create_line(51,top+58,end,top+58,fill=accent,width=4,tags='insight_panel')
            pending = sum(state == 'pending' for state in self.game.states.values())
            locked = sum(state == 'cashed_out' for state in self.game.states.values())
            footer = f'待选择 {pending} 手 · 已兑现 {locked} 手'
            label(42,231,footer,9,muted,anchor='w')

    def _draw_limit_table(self):
        c = self.canvas
        x0,x1,y0,y1 = 376,774,148,244
        c.create_rectangle(x0,y0,x1,y1,fill=ROOT_BG,outline=GOLD,width=2,tags='limits')
        self._text(575,164,'下注限额',12,PANEL_BG,tags='limits')
        self.limit_value_items=[]
        for column,caption in enumerate(('每手最低','每手最高')):
            left,right=x0+column*(x1-x0)/2,x0+(column+1)*(x1-x0)/2
            c.create_rectangle(left,181,right,y1,outline='#77906B',tags='limits')
            self._text((left+right)/2,197,caption,10,PANEL_BG,tags='limits')
            self.limit_value_items.append(self._text((left+right)/2,224,'',12,GOLD,tags='limits'))
        c.tag_bind('limits','<Button-1>',self.toggle_high_bet_limits)

    def _draw_bottom_controls(self):
        c=self.canvas
        c.create_rectangle(0,625,1150,748,fill=ROOT_BG,outline='#6C7850',width=2)
        self.balance_item=self._text(10,665,'',16,TEXT,anchor='w')
        self.total_item=self._text(10,710,'',15,TEXT,anchor='w')
        self.clear_button=self.create_control_button(278,650,344,704,'清除',self.reset_bets,
            '#9B403A',font_size=11,draw_shadow=False)
        self._draw_chips()
        self.info_button=self.create_control_button(810,650,855,695,'?',self.show_game_instructions,
            DARK_BLUE,font_size=17,draw_shadow=False)
        self.repeat_button=self.create_control_button(862,638,1000,708,'重复下注',self.apply_last_bet,
            '#536A43',font_size=11,draw_shadow=False)
        self.start_button=self.create_control_button(1012,628,1138,720,'开牌',self.start_game,
            HEADER_BG,fg=TITLE_FG,font_size=14,draw_shadow=False)
        self.all_action_buttons={}
        for index,left in enumerate((862,1005)):
            tag=self.create_control_button(
                left,633,left+133,686,'',lambda i=index:self._choose_all_option(i),
                '#397A48' if index==0 else DARK_BLUE,font_size=11,
                subtext=' ',subtext_font_size=10,draw_shadow=False)
            self.all_action_buttons[f'predict{index}']=tag
            button=self.control_buttons[tag]
            button['center_y']+=5;button['subtext_center_y']-=5
            c.coords(button['text'],left+66.5,button['center_y'])
            c.coords(button['subtext'],left+66.5,button['subtext_center_y'])
        for action,left,caption,fill in (('skip',862,'过牌','#536A43'),
                                          ('cash_out',1005,'兑现',HEADER_BG)):
            self.all_action_buttons[action]=self.create_control_button(
                left,696,left+133,741,caption,lambda a=action:self._decide_all(a),fill,
                fg=TITLE_FG if action=='cash_out' else TEXT,font_size=12,draw_shadow=False)
        self.restart_button=self.create_control_button(862,638,1138,708,'再来一局',self._return_all_chips,
            HEADER_BG,fg=TITLE_FG,font_size=17,draw_shadow=False)
        c.tag_bind(self.restart_button,'<Button-3>',lambda _e:self.show_card_sequence())
        c.itemconfigure(self.restart_button,state='hidden')
        self._enter_binding=self.winfo_toplevel().bind('<Return>',self._handle_enter,add='+')

    def _handle_enter(self,_event=None):
        if self._pending_balance_action is not None or self.game.stage in ('await_restart','credit_pending'):
            self._return_all_chips()
        elif self.game.stage=='betting':self.start_game()

    def card_position(self,side,index):
        return self.ROW_X+(index-self._window_start)*self.ROW_STEP,self.ROW_Y

    def _add_card_slot(self,index):
        x,y=self.card_position('Table',index)
        tags=('card_row',f'slot_{index}')
        self.canvas.create_rectangle(x-2,y-2,x+82,y+114,
            outline='#7B9374',dash=(3,3),tags=(*tags,f'slot_border_{index}'))
        self.slot_labels[index]=self._text(x+40,y+56,f'第{index+1}张',12,
            PANEL_BG,justify='center',tags=tags)

    def _reset_card_row(self):
        self.canvas.delete('card_row')
        self.card_items.clear();self.slot_labels.clear()
        self._window_start,self._scrolling=0,False
        for index in range(self.ROW_CAPACITY):self._add_card_slot(index)

    def _scroll_card_row(self,complete):
        """At slot eight, slide out the first five and retain two predecessors."""
        current=len(self.game.cards)-1
        if current<self._window_start+self.ROW_CAPACITY-3:
            complete();return
        first=self._window_start;target=current-2
        for index in range(first+self.ROW_CAPACITY,target+self.ROW_CAPACITY):
            self._add_card_slot(index)
        self._scrolling=True
        distance=(target-first)*self.ROW_STEP
        travelled=[0.0]
        def move(step=0):
            t=step/16;eased=t*t*(3-2*t);offset=distance*eased
            self.canvas.move('card_row',travelled[0]-offset,0);travelled[0]=offset
            if step<16:self._schedule(22,move,step+1);return
            self._window_start=target
            for index in range(first,target):
                self.canvas.delete(f'slot_{index}');self.slot_labels.pop(index,None)
                item=self.card_items.pop(('Table',index),None)
                if item is not None:
                    self.canvas.delete(item);self._flip_photos.pop(item,None)
            self._scrolling=False
            try:self.game.recycle_before(target)
            except Exception as exc:
                self._machine_error(exc,'自动还牌中止');return
            self._refresh();complete()
        move()

    def _remaining_return(self,seat=None):
        seats=self.game.SEATS if seat is None else (seat,)
        return _sum_amounts(max(ZERO,_subtract_money(self.game.resolved_return(s),self._claimed_returns[s])) for s in seats)

    def _refresh(self):
        c=self.canvas
        c.itemconfigure(self.balance_item,text=f'余额: ${self.balance:,.2f}')
        total=_sum_amounts(row['main'] for row in self.bets.values())
        c.itemconfigure(self.total_item,
            text=f'本局获胜: ${self.last_win:,.2f}' if self._round_paid else f'本局下注: ${total:,.2f}',
            fill=GOLD if self._round_paid else TEXT)
        limits=(100,50000) if self.high_bet_mode else (10,10000)
        for item,value in zip(self.limit_value_items,limits):c.itemconfigure(item,text=f'${value:,}')
        pending=self._pending_balance_action is not None
        ready=not(pending or self._phase_busy or self._decision_busy or self._motion_count)
        betting=self.game.stage=='betting' and ready
        self.set_control_button_state(self.clear_button,betting)
        ending=pending or self.game.stage in ('settling','await_restart','returning','credit_pending','sweeping')
        for tag,enabled in ((self.repeat_button,betting and bool(self.last_bet)),(self.start_button,betting)):
            c.itemconfigure(tag,state='normal' if self.game.stage=='betting' and not ending else 'hidden')
            self.set_control_button_state(tag,enabled)
        c.itemconfigure(self.restart_button,state='normal' if ending else 'hidden')
        self.set_control_button_state(self.restart_button,not self._saving_balance and (
            pending or (ready and self.game.stage in ('await_restart','credit_pending'))))
        self._restart_caption('重试保存余额' if pending else '重试归还牌张' if self.game.stage=='credit_pending'
                              else '统一结算中' if self.game.stage=='settling'
                              else '收取本局筹码' if self._remaining_return() else '再来一局')
        offers=hilo_offers(self._visible_card) if self._visible_card else []
        deciding=ready and self.game.stage=='decision' and any(
            self.game.states[s]=='pending' for s in self.game.SEATS)
        for action,tag in self.all_action_buttons.items():
            offer=offers[int(action[-1])] if action.startswith('predict') and offers else None
            if action.startswith('predict'):
                c.itemconfigure(self.control_buttons[tag]['text'],text=offer['label'] if offer else ('大于等于' if action=='predict0' else '小于等于'))
                c.itemconfigure(self.control_buttons[tag]['subtext'],text=f"返还 {offer['multiplier']:.2f}×" if offer else '—')
            c.itemconfigure(tag,state='normal' if self.game.stage!='betting' and not ending else 'hidden')
            enabled=bool(deciding and (offer or action in ('skip','cash_out')))
            if action=='cash_out':enabled=enabled and any('cash_out' in self.game.legal_actions(s) for s in self.game.SEATS)
            self.set_control_button_state(tag,enabled)
        rank=self._visible_card.rank if self._visible_card else None
        c.itemconfigure(self.status_item,text=f'{rank} · '+(' / '.join(row['label'] for row in offers)) if rank else '随机起始牌 · 每张自由选择')
        self._refresh_insight_panel()
        held=_sum_amounts(self._display_pots.values())
        for item,value in zip(self.stat_items,(str(self._shown_draws),str(self._visible_wins),str(self._visible_skips),'$'+self._compact(held))):
            c.itemconfigure(item,text=value)
        for seat in self.game.SEATS:
            for index in range(2):
                tag=self.action_buttons[(seat,f'predict{index}')]
                offer=offers[index] if offers else None
                c.itemconfigure(self.control_buttons[tag]['text'],text=offer['label'] if offer else ('大于等于' if index==0 else '小于等于'))
                c.itemconfigure(self.control_buttons[tag]['subtext'],text=f"返还 {offer['multiplier']:.2f}×" if offer else '—')
                enabled=bool(ready and offer and offer['action'] in self.game.legal_actions(seat))
                self.set_control_button_state(tag,enabled)
                selected=bool(offer and self.game.choices[seat]==offer['action'])
                c.itemconfigure(self.control_buttons[tag]['rim'],outline=GOLD if selected else '#b7a58d' if enabled else '#677169')
            for action in ('skip','cash_out'):
                enabled=ready and action in self.game.legal_actions(seat)
                self.set_control_button_state(self.action_buttons[(seat,action)],enabled)
                selected=self.game.choices[seat]==action
                c.itemconfigure(self.control_buttons[self.action_buttons[(seat,action)]]['rim'],outline=GOLD if selected else '#b7a58d' if enabled else '#677169')
            shown=self._display_pots[seat]
            locked=self.game.states[seat]=='cashed_out'
            spot=self.bet_spots[(seat,'main')]
            c.itemconfigure(spot['label_item'],fill=GOLD if locked else PANEL_BG)
            c.itemconfigure(spot['border'],outline=GOLD if locked else PANEL_BG)
            caption=''
            if self.game.stage!='betting' and self.bets[seat]['main']:
                if locked:
                    caption=f'${self.game.resolved_return(seat):,.2f}'
                elif self.game.states[seat]=='lost':
                    # Keep the previous text and color until the round settles.
                    if not self._settlement_started:continue
                    caption='本局已输'
                elif self.game.states[seat]=='void':
                    caption=('已退回' if self._round_paid else '待退回')+f'\n${self.game.resolved_return(seat):,.2f}'
                else:caption=f'${shown:,.2f}'
            c.itemconfigure(self.pot_items[seat],text=caption,
                            fill='#AABAAF' if self.game.states[seat]=='lost' else GOLD)
        for index,item in self.slot_labels.items():
            c.itemconfigure(item,text=f'第{index+1}张')
            # Only rectangle items have an outline in native Tk.
            # The label is tagged separately from the rectangle below.
            c.itemconfigure(f'slot_border_{index}',outline=GOLD if index==self._shown_draws-1 else '#7B9374')
        self._render_chips()

    def add_chip_to_bet(self,seat,kind='main'):
        if self.game.stage!='betting' or self._motion_count or self._pending_balance_action is not None:return
        new={s:dict(row) for s,row in self.bets.items()}
        maximum=Decimal('50000' if self.high_bet_mode else '10000')
        new[seat]['main']=min(maximum,_add_money(new[seat]['main'],_amount(self.selected_chip)))
        self._apply_bet_layout(new)

    def reset_single_bet(self,seat,kind='main'):
        if self.game.stage!='betting' or self._motion_count or self._pending_balance_action is not None:return
        new={s:dict(row) for s,row in self.bets.items()};new[seat]=self.game.empty_bet()
        self._apply_bet_layout(new)

    def _apply_bet_layout(self,new_bets):
        if self.game.stage!='betting' or self._motion_count or self._pending_balance_action is not None:return
        new={s:{'main':_amount(new_bets.get(s,{}).get('main',0))} for s in self.game.SEATS}
        if _sum_amounts(row['main'] for row in new.values())>self.balance:
            messagebox.showwarning('余额不足','余额不足以支付这组下注。',parent=self);return
        previous,self.bets=self.bets,new;transfers=[]
        for seat in self.game.SEATS:
            old,current=previous[seat]['main'],new[seat]['main']
            delta=_subtract_money(current,old);center=self.bet_spots[(seat,'main')]['center']
            if delta>0:
                transfers.append(dict(amount=delta,start=self._rack_position(),target=center,
                    arrive=lambda s=seat,a=current:self._set_visual(s,'main','stake',a)))
            elif delta<0:
                self._set_visual(seat,'main','stake',current)
                transfers.append(dict(amount=-delta,start=center,target=self._rack_position(),duration=320))
        self._run_chip_batch(transfers,self._refresh);self._refresh()

    def reset_bets(self):self._apply_bet_layout({s:self.game.empty_bet() for s in self.game.SEATS})
    def apply_last_bet(self):
        if self.last_bet:self._apply_bet_layout(self.last_bet)

    def start_game(self):
        if self.game.stage!='betting' or self._motion_count or self._pending_balance_action is not None:return
        try:cost=self.game.start_round(self.bets,self.balance,self.high_bet_mode)
        except ValueError as exc:
            messagebox.showwarning('无法开始',str(exc),parent=self);return
        except Exception as exc:
            try:self.engine.close()
            except Exception:pass
            messagebox.showerror('自动洗牌机',str(exc),parent=self);return
        self.balance=_subtract_money(self.balance,cost)
        self.bets={s:dict(row) for s,row in self.game.bets.items()}
        self.last_bet={s:dict(row) for s,row in self.bets.items()}
        self._claimed_returns={s:ZERO for s in self.game.SEATS}
        self._display_pots={s:row['main'] for s,row in self.bets.items()}
        self._shown_draws,self._visible_card=0,None
        self._visible_wins=self._visible_skips=0
        self._settlement_started=self._machine_fault=self._machine_released=self._history_available=False
        self._round_paid=False
        self._phase_busy=True;self._decision_busy=False
        self._close_card_sequence();self.card_poses.clear()
        self._reset_card_row();self._flip_photos.clear()
        self._load_assets()
        self._save_and_continue(self._deal_one)

    def _deal_one(self):
        if self._closing or self.game.stage not in ('seed_ready','ready'):return
        self._phase_busy=True
        try:
            if self.game.stage=='seed_ready':self.game.reveal_initial()
            else:self.game.draw_next()
        except Exception as exc:
            self._machine_error(exc,'发牌中止');return
        index=len(self.game.cards)-1
        self.canvas.delete('cards');self.card_items.clear();self._flip_photos.clear()
        for old in range(self._window_start,index):
            card=self.game.cards[old];x,y=self.card_position('Table',old)
            self.card_items[('Table',old)]=self.canvas.create_image(x,y,
                image=self._face_photos[(card.suit,card.rank)],anchor='nw',tags=('cards','card_row'))
        x,y=self.card_position('Table',index)
        item=self.canvas.create_image(575,45,image=self._face_photos['back'],anchor='nw',tags=('cards','card_row'))
        self.card_items[('Table',index)]=item
        self._refresh()
        def move(step=0):
            t=step/8;self.canvas.coords(item,575+(x-575)*t,45+(y-45)*t)
            if step<8:self._schedule(20,move,step+1)
            else:self._flip_card(index,item,x,y)
        move()

    def _machine_error(self,exc,caption):
        self._machine_fault=True;self._phase_busy=False;self._scrolling=False
        self.game.abort_round(f'{caption}：{exc}')
        messagebox.showerror('自动洗牌机',f'本局已停止：{exc}\n将退回各手此前已确认的累计金额，已兑现的手牌不会重复入账。',parent=self)
        self._display_pots={s:max(ZERO,_subtract_money(self.game.pot(s),self._claimed_returns[s])) for s in self.game.SEATS}
        self._settle()

    def _flip_card(self,index,item,x,y):
        card=self.game.cards[index]
        def flip(step=0):
            width=max(1,round(self.CARD_WIDTH*abs(1-step/5)))
            source=self._pil_cards['back' if step<5 else (card.suit,card.rank)]
            photo=ImageTk.PhotoImage(source.resize((width,self.CARD_HEIGHT),Image.Resampling.LANCZOS),master=self)
            self._flip_photos[item]=photo
            self.canvas.itemconfigure(item,image=photo)
            self.canvas.coords(item,x+(self.CARD_WIDTH-width)/2,y)
            if step<10:self._schedule(25,flip,step+1)
            else:
                self.canvas.itemconfigure(item,image=self._face_photos[(card.suit,card.rank)])
                self._flip_photos.pop(item,None);self._after_card()
        flip()

    def _after_card(self):
        self._shown_draws=len(self.game.cards);self._visible_card=self.game.current_card
        self._visible_wins=sum(self.game.wins.values());self._visible_skips=sum(self.game.skips.values())
        self._display_pots={s:max(ZERO,_subtract_money(self.game.pot(s),self._claimed_returns[s])) for s in self.game.SEATS}
        self._phase_busy=False;self._decision_busy=True
        self._refresh()
        self._pose_failed_card(lambda:self._animate_pots(lambda:self._scroll_card_row(self._after_results)))

    def _pose_failed_card(self,complete):
        if self.game.stage!='complete' or not any(v=='loss' for v in self.game.last_outcomes.values()):complete();return
        index=len(self.game.cards)-1;card=self.game.cards[index]
        item=self.card_items[('Table',index)];source=self._pil_cards[(card.suit,card.rank)]
        x,y=self.card_position('Table',index)
        rotated=source.rotate(-20,resample=Image.Resampling.BICUBIC,expand=True)
        photo=ImageTk.PhotoImage(rotated,master=self);self._flip_photos[item]=photo
        self.canvas.itemconfigure(item,image=photo)
        self.canvas.coords(item,x+(80-rotated.width)/2,y+(112-rotated.height)/2+10)
        self.card_poses[index]=dict(clockwise_degrees=20,down_pixels=10)
        complete()

    def _choose_option(self,seat,index):
        if self._visible_card:
            self._decide(seat,hilo_offers(self._visible_card)[index]['action'])

    def _choose_all_option(self,index):
        if self._visible_card:
            self._decide_all(hilo_offers(self._visible_card)[index]['action'])

    def _can_decide(self):
        return not(self._closing or self._pending_balance_action is not None or self._decision_busy
                   or self._phase_busy or self._motion_count)

    def _decide(self,seat,action):
        if not self._can_decide():return
        if action not in self.game.legal_actions(seat):return
        self._decision_busy=True;self.game.decide(seat,action)
        self._after_results()

    def _decide_all(self,action):
        if not self._can_decide() or not any(action in self.game.legal_actions(s) for s in self.game.SEATS):return
        self._decision_busy=True;self.game.decide_all(action)
        self._after_results()

    def _after_results(self):
        self._decision_busy=False;self._refresh()
        if self.game.stage=='complete':self._settle()
        elif self.game.stage=='ready':
            self._phase_busy=True;self._refresh();self._schedule(100,self._deal_one)

    def _profit_transfers(self,seat,target_profit):
        key=(seat,'main','profit');previous=self.visual_chips.get(key,{}).get('amount',ZERO)
        delta=_subtract_money(target_profit,previous)
        if not delta:return []
        cx,cy=self.bet_spots[(seat,'main')]['center'];target=(cx-36,cy-27)
        if delta>0:return [dict(amount=delta,start=self.HOUSE_CHIP_POS,target=target,duration=280,
            arrive=lambda:self._set_visual(seat,'main','profit',target_profit,target))]
        source=self.visual_chips[key]['xy'];self._set_visual(seat,'main','profit',target_profit,target)
        return [dict(amount=-delta,start=source,target=self.HOUSE_CHIP_POS,duration=240)]

    def _animate_pots(self,complete):
        transfers=[]
        for seat in self.game.active_hands:
            if self._claimed_returns[seat] or self.game.states[seat]=='cashed_out':continue
            stake=self.bets[seat]['main'];pot=self.game.pot(seat)
            transfers.extend(self._profit_transfers(seat,max(ZERO,_subtract_money(pot,stake))))
            if self.game.states[seat]=='lost':
                chip=self.visual_chips.pop((seat,'main','stake'),None)
                if chip:transfers.append(dict(amount=chip['amount'],start=chip['xy'],target=self.HOUSE_CHIP_POS,duration=240))
        self._refresh();self._run_chip_batch(transfers,complete)

    def _claim_seats(self,seats,complete):
        if self.game.settlement is None:
            raise ValueError('请等待全部主注结束后统一收款。')
        if self._pending_balance_action is not None:return
        selected=[s for s in seats if self._remaining_return(s)>0]
        if not selected:complete();return
        amount=_sum_amounts(self._remaining_return(s) for s in selected)
        self.balance=_add_money(self.balance,amount)
        for seat in selected:
            self._claimed_returns[seat]=self.game.resolved_return(seat)
            self._display_pots[seat]=ZERO
        def after_save():
            chips=[(key,chip) for key,chip in self.visual_chips.items() if key[0] in selected]
            transfers=[]
            for index,(key,chip) in enumerate(chips):
                self.visual_chips.pop(key,None)
                transfers.append(dict(amount=chip['amount'],start=chip['xy'],target=self._rack_position(index,len(chips)),duration=440))
            self._refresh();self._run_chip_batch(transfers,complete)
        self._save_and_continue(after_save)

    def _settle(self):
        if self._settlement_started:return
        self._settlement_started=True;self._decision_busy=True
        result=self.game.settle();self.last_win=result['returned'];self.game.stage='settling'
        try:self.engine.finish_round()
        except Exception as exc:
            self._machine_fault=True;messagebox.showerror('自动洗牌机',f'本局还牌失败：{exc}\n重开前将重新归还牌张。',parent=self)
        try:save_hilo_history(self.game,result)
        except Exception as exc:messagebox.showerror('历史记录保存失败',str(exc),parent=self)
        def paid():
            self._claim_seats(self.game.active_hands,self._await_next_round)
        self._animate_pots(paid)

    def _await_next_round(self):
        self.game.stage='await_restart';self._decision_busy=self._phase_busy=False
        self._round_paid=True
        self._history_available=True
        self.last_round_snapshot=dict(cards=tuple(self.game.cards),images={key:image.copy() for key,image in self.original_images.items()})
        self._refresh()

    def _return_all_chips(self):
        if self._pending_balance_action is not None:self._retry_balance_save();return
        if not self._can_decide():return
        if self.game.stage=='credit_pending':self._complete_chip_return();return
        if self.game.stage!='await_restart':return
        if self._remaining_return():
            self._decision_busy=True;self._claim_seats(self.game.active_hands,self._await_next_round);return
        self._close_card_sequence();self._history_available=False
        self.game.stage='returning';self._complete_chip_return()

    def _complete_chip_return(self):
        self.game.stage='sweeping';self._refresh()
        self._reset_card_row();self._flip_photos.clear();self.card_poses.clear()
        if self._machine_fault:
            try:self.engine.close()
            except Exception as exc:
                self.game.stage='credit_pending';self._refresh()
                messagebox.showerror('自动洗牌机',f'归还牌张失败：{exc}\n请点击按钮重试。',parent=self);return
        self.game.reset_game()
        self.bets={s:self.game.empty_bet() for s in self.game.SEATS}
        self._claimed_returns={s:ZERO for s in self.game.SEATS}
        self._display_pots={s:ZERO for s in self.game.SEATS}
        self._round_paid=False
        self._settlement_started=False
        self._visible_card=None;self._shown_draws=self._visible_wins=self._visible_skips=0
        self._decision_busy=self._phase_busy=False;self.visual_chips.clear();self._refresh()

    def _persist_balance(self):
        try:
            if self.username and self.username!='Guest':update_balance_in_json(self.username,self.balance)
            if callable(self.on_balance_change):self.on_balance_change(_external_amount(self.balance))
        except Exception as exc:
            messagebox.showerror('余额保存失败',str(exc),parent=self);return False
        return True

    @staticmethod
    def _compact(amount):
        value=_amount(amount)
        if value>=Decimal('1e12'):return format(value,'.1E').replace('E+','E')
        if value>=1000000:
            with localcontext() as context:
                context.prec=max(28,len(value.as_tuple().digits)+8)
                return f'{value/1000000:.2f}'.rstrip('0').rstrip('.')+'M'
        if value>=1000:return f'{value/1000:.2f}'.rstrip('0').rstrip('.')+'K'
        return format(value,'f').rstrip('0').rstrip('.')

    def show_card_sequence(self,event=None):
        if self.game.stage!='await_restart' or not self._history_available:return
        current=getattr(self,'_sequence_window',None)
        if current is not None and current.winfo_exists():current.lift();return
        snapshot=self.last_round_snapshot
        win=tk.Toplevel(self);self._sequence_window=win;win.title('上局实际发牌')
        win.geometry('760x590');win.resizable(False,False);win.configure(bg=ROOT_BG)
        caption=tk.Label(win,font=(self.cn_font,13,'bold'),bg=ROOT_BG,fg=GOLD);caption.pack(pady=12)
        host=tk.Frame(win,bg=ROOT_BG);host.pack(fill=tk.BOTH,expand=True)
        controls=tk.Frame(win,bg=ROOT_BG);controls.pack(pady=12)
        page=[0];pages=max(1,(len(snapshot['cards'])+31)//32)
        def render():
            for child in host.winfo_children():child.destroy()
            win._images=[];caption.configure(text=f'上局实际发牌 · 共{len(snapshot["cards"])}张 · 第{page[0]+1}/{pages}页')
            for offset,card in enumerate(snapshot['cards'][page[0]*32:page[0]*32+32]):
                photo=ImageTk.PhotoImage(snapshot['images'][(card.suit,card.rank)].resize((60,84),Image.Resampling.LANCZOS),master=win)
                win._images.append(photo);cell=tk.Frame(host,bg=ROOT_BG);cell.grid(row=offset//8,column=offset%8,padx=12,pady=6)
                tk.Label(cell,image=photo,bg=ROOT_BG).pack()
                tk.Label(cell,text=f'第{page[0]*32+offset+1}张',font=(self.cn_font,9),bg=ROOT_BG,fg=PANEL_BG).pack()
        def turn(delta):page[0]=max(0,min(pages-1,page[0]+delta));render()
        tk.Button(controls,text='上一页',command=lambda:turn(-1),width=14).pack(side=tk.LEFT,padx=12)
        tk.Button(controls,text='下一页',command=lambda:turn(1),width=14).pack(side=tk.LEFT,padx=12)
        render()

    def _instruction_pages(self):
        return [
            ('玩法',[
                ('牌点与目标','2最小，依次为3、4、5、6、7、8、9、10、J、Q、K、A；花色不影响大小。\n先下注并随机亮出一张起始牌，然后预测下一张牌。'),
                ('每张自由选择','按钮由左至右排列：当前3–K为“大于等于／小于等于”，同点数两种选择都算猜中。\n当前2为“大于／等于”；当前A为“等于／小于”。'),
                ('1–3手独立操作','可以选择任意1–3手下注；各手分别决定。所有仍在局中的手牌完成决定后，共同发出下一张牌。\n每手一经选择立即锁定，等待其他手时也不能更改；右下角四个按钮只处理尚未选择的手牌。')],[]),
            ('兑现与过牌',[
                ('兑现','该手已有尚未兑现的盈利时，才可在下一次预测前兑现；尚未赢过或只过牌时按钮变暗。\n猜中后，累计返还金额按该次固定倍率增加，并作为下一次预测的金额。猜错损失该手未兑现的全部金额。'),
                ('过牌','不想预测当前牌时可选择“过牌”。系统换一张参考牌，不计该手输赢、不增加倍率，也不改变累计金额。\n同一张新牌仍会结算其他手已经选择的高低预测。'),
                ('不限次数','没有发牌次数上限；可以持续预测或过牌，直到兑现或猜错。\n牌列显示10个位置，发到倒数第3格时向左滚动，保留最新牌及它前面的2张；结束后可右键底部按钮分页查看完整牌序。'),
                ('统一操作','右下角四个按钮与各手的预测、过牌、兑现按钮相同，只替尚未选择的手牌作决定。\n已锁定的选择、已兑现或已输的手牌均不受影响。'),
                ('桌面金额','主注下方以两位小数显示本金加尚未兑现的奖金，例如$186.00。\n兑现后该手四个按钮变灰，“主注”文字变金色，金额锁定、筹码留在原位，等待其他手结束。')],[]),
            ('赔率',[
                ('固定赔率','各牌点及方向的赔率和概率已预先算好，直接使用固定表。\n历史已开牌、当前桌上牌张及CSM内剩余牌数均不会改变赔率。'),
                ('倍率与小数','固定返还倍率保留两位小数；不另外扣佣。\n净赢赔率 = 总返还倍率 − 1。例如显示返还1.86×，相当于净赢0.86:1。\n每次猜中后用当前累计返还乘以显示倍率，金额四舍五入保留两位小数。'),
                ('示例','当前8：大于等于及小于等于各有223张有利牌，返还倍率1.86×。\n当前2或A：猜等于有31张，返还13.39×；猜另一方向有384张，返还1.08×。\n主注100，按1.86×猜中后累计返还186；之后过牌仍为186。')],[]),
            ('收款与牌张',[
                ('收款','点击“兑现”只锁定该手金额，不会立刻加入余额。全部主注兑现或输掉后，统一保存余额并把返还筹码送回下注区。\n筹码返回后，“本局下注”切换为“本局获胜”（包含返还本金）；左上角战报另列本局净额。\n金额保存失败时点击重试，不会重复加钱。结束后点击“再来一局”清理桌面。'),
                ('牌张','使用8副牌、共416张的连续洗牌机。桌面仍显示的牌暂不还入；每次左滑后，已移出的牌按原批次自动返回CSM。\n牌局结束时归还其余牌张。8是普通牌，同点数按所选按钮判断。'),
                ('异常与退出','请先兑现或完成本局后退出。发牌异常时，新预测不计输赢，退回该手此前已确认的累计金额。')],[]),
        ]

    def on_close(self):
        if self._closing or self._saving_balance:return
        if self._pending_balance_action is not None:
            messagebox.showinfo('余额待保存','请先点击“重试保存余额”。',parent=self);return
        if self.game.stage not in ('betting','await_restart','credit_pending'):
            messagebox.showinfo('牌局进行中','请先兑现仍在局中的手牌。',parent=self);return
        if self._remaining_return():
            messagebox.showinfo('尚有待收筹码','请先兑现尚留在桌面的筹码。',parent=self);return
        try:self.engine.close();self._machine_released=True
        except Exception as exc:
            self._machine_fault=True;messagebox.showerror('自动洗牌机',f'归还牌张失败：{exc}',parent=self);return
        if not self._persist_balance():return
        self._closing=True;self._cancel_jobs();self._unbind_enter();self._close_card_sequence()
        dialog=getattr(self,'_game_instruction_dialog',None)
        if dialog is not None and dialog.winfo_exists():dialog.destroy()
        if callable(self.on_back):self.on_back(_external_amount(self.balance))
        else:self.winfo_toplevel().destroy()

    def _on_destroy(self,event):
        if event.widget is not self:return
        was_closing=self._closing;self._closing=True;self._pending_balance_action=None
        self._cancel_jobs();self._unbind_enter()
        if not self._machine_released:
            try:self.engine.close();self._machine_released=True
            except Exception as exc:print(f'HiLo归还牌张失败：{exc}',file=sys.stderr)
        if not was_closing and self.game.stage!='betting':
            self.game.abort_round('宿主窗口关闭，退回尚未确定的累计金额')
            self.balance=_add_money(self.balance,self._remaining_return())
            for seat in self.game.SEATS:self._claimed_returns[seat]=self.game.resolved_return(seat)
            try:
                if self.username and self.username!='Guest':update_balance_in_json(self.username,self.balance)
                if callable(self.on_balance_change):self.on_balance_change(_external_amount(self.balance))
            except Exception as exc:print(f'HiLo关闭时保存余额失败：{exc}',file=sys.stderr)


    def _draw_chip(self, tag, amount, x, y, extra_tags=()):
        color, radius = self._chip_color(amount), self.BET_CHIP_RADIUS
        tags = (tag, *extra_tags)
        self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius,
            fill=color, outline=BLACK, width=1, tags=tags)
        label = self._compact(amount)
        self._text(x, y, label, 10 if len(label) >= 5 else 12,
                   TEXT if color in (BLACK, RED) else BLACK, tags=tags)


    def _render_chips(self):
        self.canvas.delete('bet_chips')
        for (seat, kind, role), chip in sorted(self.visual_chips.items(), key=lambda item: item[0][2] != 'stake'):
            if chip['amount'] > 0:
                self._draw_chip(f'chip_{seat}_{kind}_{role}', chip['amount'], *chip['xy'],
                    extra_tags=('bet_chips', self.bet_spots[(seat, kind)]['tag']))


    def _animate_chip(self, amount, start, target, complete=None, duration=220):
        if not amount:
            if complete:
                complete()
            return
        self._motion_count += 1
        self._chip_serial += 1
        tag = f'moving_chip_{self._chip_serial}'
        self._draw_chip(tag, amount, *start, extra_tags=('moving_chips',))
        self._refresh()
        steps, last = max(1, round(duration / 16)), list(start)
        def frame(index):
            fraction = index / steps
            eased = fraction * fraction * (3 - 2 * fraction)
            x, y = start[0] + (target[0] - start[0]) * eased, start[1] + (target[1] - start[1]) * eased
            self.canvas.move(tag, x - last[0], y - last[1])
            last[:] = [x, y]
            self.canvas.tag_raise(tag)
            if index < steps:
                self._schedule(round(duration * (index + 1) / steps) - round(duration * index / steps), frame, index + 1)
            else:
                self.canvas.delete(tag)
                self._motion_count -= 1
                if complete:
                    complete()
                self._refresh()
        self._schedule(round(duration / steps), frame, 1)


    def _run_chip_batch(self, transfers, complete):
        if not transfers:
            complete()
            return
        pending = [len(transfers)]
        def arrived(transfer):
            if transfer.get('arrive'):
                transfer['arrive']()
            pending[0] -= 1
            if not pending[0]:
                complete()
        for transfer in transfers:
            self._animate_chip(transfer['amount'], transfer['start'], transfer['target'],
                complete=lambda row=transfer: arrived(row), duration=transfer.get('duration', 220))


    def _set_visual(self, seat, kind, role, amount, xy=None):
        key = (seat, kind, role)
        if amount:
            self.visual_chips[key] = dict(amount=_amount(amount), xy=xy or self.bet_spots[(seat, kind)]['center'])
        else:
            self.visual_chips.pop(key, None)


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
        self.original_images = {}
        base = os.path.join(project_root(), 'A_Tools', 'Card', 'Poker2')
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


    def select_chip(self, amount):
        if self.game.stage == 'betting':
            self.selected_chip = amount
            self._draw_chips()


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


    def _save_and_continue(self, complete):
        """先保存本次余额，再开始派牌或筹码动画；失败时保留同一项操作。"""
        if self._pending_balance_action is not None:
            return
        self._pending_balance_action = complete
        self._retry_balance_save()


    def _retry_balance_save(self):
        if self._closing or self._saving_balance or self._pending_balance_action is None:
            return
        self._saving_balance = True
        self._refresh()
        try:
            saved = self._persist_balance()
        finally:
            self._saving_balance = False
        if not saved:
            self._refresh()
            return
        complete = self._pending_balance_action
        self._pending_balance_action = None
        self._restart_caption('再来一局')
        if not self._closing:
            complete()
            self._refresh()


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
                                          font=(self.cn_font, font_size, 'bold'), fill=fg,
                                          tags=(tag, 'controls'))
        subtext_id = None
        subtext_center_y = None
        if subtext:
            subtext_center_y = center_y + 16
            subtext_id = self.canvas.create_text((x0 + x1) / 2, subtext_center_y,
                                                 text=subtext,
                                                 font=(self.cn_font, subtext_font_size, 'bold'),
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
            self.canvas.itemconfigure(button['face'], fill=button['fill'],
                                      outline=self.shade_color(button['fill'], 1.25))
            self.canvas.itemconfigure(button['rim'], fill=self.shade_color(button['fill'], 0.55),
                                      outline='#b7a58d')
            self.canvas.itemconfigure(button['highlight'], fill=self.shade_color(button['fill'], 1.45))
            self.canvas.itemconfigure(button['text'], fill=button['fg'])
            if button.get('subtext'):
                self.canvas.itemconfigure(button['subtext'], fill=button['fg'])
        else:
            self.canvas.itemconfigure(button['face'], fill='#414B45', outline='#59645D')
            self.canvas.itemconfigure(button['rim'], fill='#353D38', outline='#677169')
            self.canvas.itemconfigure(button['highlight'], fill='#637067')
            self.canvas.itemconfigure(button['text'], fill='#A1AAA4')
            if button.get('subtext'):
                self.canvas.itemconfigure(button['subtext'], fill='#A1AAA4')


    def _chip_color(self, amount):
        return next((col for value,col in reversed(self.chip_specs) if amount>=value),HEADER_BG)


    def _rack_position(self, index=None, total=1):
        if index is not None:
            return 575+(index-(total-1)/2)*min(28,140/max(1,total-1)),674
        index=next((i for i,(value,_) in enumerate(self.chip_specs) if value==self.selected_chip),None)
        if index is None:return (575,674)
        width=len(self.chip_specs)*56+(len(self.chip_specs)-1)*8
        return (self.WIDTH-width)/2+index*64+28,674


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


    def _close_card_sequence(self):
        current=getattr(self,'_sequence_window',None)
        if current is not None:
            try:
                if current.winfo_exists():current.destroy()
            except tk.TclError:pass
        self._sequence_window=None


    def show_game_instructions(self):
        import tkinter.font as tkfont

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
        instruction_title = 'HiLo · 玩法说明'
        dialog.title(instruction_title)
        dialog.resizable(False, False)
        dialog.transient(parent)
        width, height = 1000, 670
        parent.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        dialog.geometry(f'{width}x{height}+{max(0, x)}+{max(0, y)}')

        bg, header_bg, sidebar_bg = '#faf5e8', '#f1e7cd', '#f2e8d0'
        panel, table_bg, border = '#fffdf7', '#f5ecd6', '#c9b88a'
        gold, gold_bar = '#a8842c', '#e7d36c'
        text, muted = '#3a2f1e', '#7a6a50'
        font_name = getattr(self, 'cn_font', 'Microsoft YaHei UI')
        dialog.configure(bg=bg)
        pages = self._instruction_pages()

        def close_dialog():
            self._game_instruction_dialog = None
            dialog.destroy()

        header = tk.Frame(dialog, bg=header_bg, height=76)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)
        tk.Label(header, text=instruction_title, font=(font_name, 20, 'bold'),
                 fg=gold, bg=header_bg, anchor='w', wraplength=795,
                 justify=tk.LEFT).place(x=24, y=6, width=795, height=41)
        tk.Label(header, text='玩法 · 1–3手下注 · 大小比较 · 兑现 · 过牌',
                 font=(font_name, 14), fg=muted, bg=header_bg,
                 anchor='w').place(x=26, y=46)
        tk.Button(header, text='关闭  ESC', command=close_dialog,
                  font=(font_name, 14, 'bold'), bg='#e8dcc0', fg=text,
                  activebackground='#d9c895', relief=tk.FLAT, bd=0,
                  cursor='hand2').place(x=850, y=17, width=120, height=42)
        tk.Frame(dialog, bg=gold_bar, height=3).pack(fill=tk.X, side=tk.TOP)

        body = tk.Frame(dialog, bg=bg)
        body.pack(fill=tk.BOTH, expand=True)
        sidebar = tk.Frame(body, bg=sidebar_bg, width=205)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text='说明目录', font=(font_name, 16, 'bold'),
                 fg=gold, bg=sidebar_bg, anchor='w').pack(fill=tk.X, padx=18, pady=(17, 10))
        scroll_host = tk.Frame(body, bg=bg)
        scroll_host.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(scroll_host, bg=bg, highlightthickness=0, bd=0, yscrollincrement=36)
        scrollbar = tk.Scrollbar(scroll_host, orient=tk.VERTICAL, command=canvas.yview,
                                 bg='#ded3b7', troughcolor=bg, activebackground=gold_bar,
                                 relief=tk.FLAT, bd=0, width=13)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 8), pady=10)
        content = tk.Frame(canvas, bg=bg)
        content_window = canvas.create_window((0, 0), window=content, anchor='nw')
        content.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(content_window, width=event.width))

        def add_rule(heading, detail):
            card = tk.Frame(content, bg=panel, highlightbackground=border,
                            highlightcolor=border, highlightthickness=1, bd=0)
            card.pack(fill=tk.X, padx=10, pady=7)
            tk.Label(card, text=heading, font=(font_name, 16, 'bold'),
                     fg=gold, bg=panel, anchor='w', justify=tk.LEFT,
                     wraplength=680).pack(fill=tk.X, padx=16, pady=(12, 5))
            row = tk.Frame(card, bg=panel)
            row.pack(fill=tk.X, padx=16, pady=(5, 12))
            tk.Frame(row, bg=gold_bar, width=5).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 11))
            tk.Label(row, text=detail, font=(font_name, 14), fg=muted, bg=panel,
                     anchor='w', justify=tk.LEFT, wraplength=650).pack(
                         side=tk.LEFT, fill=tk.X, expand=True)

        def add_table(heading, columns, rows):
            block = tk.Frame(content, bg=table_bg,
                             highlightbackground=border, highlightthickness=1, bd=0)
            block.pack(fill=tk.X, padx=16, pady=8)
            tk.Label(block, text=heading, font=(font_name, 14, 'bold'),
                     fg=text, bg=gold_bar, anchor='w', justify=tk.LEFT,
                     wraplength=675, padx=11, pady=7).pack(fill=tk.X)
            grid = tk.Frame(block, bg=table_bg)
            grid.pack(fill=tk.X)
            table_font = tkfont.Font(root=dialog, family=font_name, size=14)
            matrix = [columns, *rows]
            preferences = [max(50, min(260, max(table_font.measure(str(row[col]))
                                               for row in matrix)))
                           for col in range(len(columns))]
            available = 700
            remaining = available - 62 * len(columns)
            total_preference = sum(preferences)
            widths = [62 + remaining * preference // total_preference
                      for preference in preferences]
            widths[-1] += available - sum(widths)
            for column, column_width in enumerate(widths):
                grid.grid_columnconfigure(column, minsize=column_width)
            for row_index, values in enumerate(matrix):
                head = row_index == 0
                cell_bg = gold_bar if head else (panel if row_index % 2 else '#fbf6e9')
                for column, value in enumerate(values):
                    tk.Message(grid, text=value, font=(font_name, 14, 'bold' if head else 'normal'),
                               fg=text if head else muted, bg=cell_bg,
                               anchor='w', justify=tk.LEFT, width=widths[column] - 16,
                               padx=7, pady=5, borderwidth=1, relief=tk.SOLID).grid(
                                   row=row_index, column=column, sticky='nsew')

        def render_page(index):
            for child in content.winfo_children():
                child.destroy()
            for number, button in enumerate(nav_buttons):
                button.configure(bg='#e6d9b9' if number == index else sidebar_bg,
                                 fg=gold if number == index else muted)
            page_title, rules, tables = pages[index]
            tk.Label(content, text=page_title, font=(font_name, 20, 'bold'),
                     fg=gold, bg=bg, anchor='w', justify=tk.LEFT,
                     wraplength=690).pack(fill=tk.X, padx=14, pady=(7, 2))
            for heading, detail in rules:
                add_rule(heading, detail)
            for heading, columns, rows in tables:
                add_table(heading, columns, rows)
            content.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox('all'))
            canvas.yview_moveto(0)

        nav_buttons = []
        for index, (title, _rules, _tables) in enumerate(pages):
            button = tk.Button(sidebar, text=title, command=lambda i=index: render_page(i),
                               font=(font_name, 14), fg=muted, bg=sidebar_bg,
                               activebackground='#e8d49a', activeforeground=gold,
                               relief=tk.FLAT, bd=0, anchor='w', padx=18, pady=10,
                               cursor='hand2')
            button.pack(fill=tk.X)
            nav_buttons.append(button)

        def on_mousewheel(event):
            delta = event.delta
            if delta:
                direction = -1 if delta > 0 else 1
                canvas.yview_scroll(direction * max(1, abs(delta) // 120), 'units')
            return 'break'

        dialog.bind('<MouseWheel>', on_mousewheel)
        dialog.bind('<Button-4>', lambda _e: (canvas.yview_scroll(-1, 'units'), 'break')[1])
        dialog.bind('<Button-5>', lambda _e: (canvas.yview_scroll(1, 'units'), 'break')[1])
        dialog.bind('<Escape>', lambda _e: close_dialog())
        dialog.protocol('WM_DELETE_WINDOW', close_dialog)
        render_page(0)
        dialog.after(30, dialog.focus_force)


# Preserve existing launcher/import names when replacing the original file.
HiLoMojoGame = HiLoGame
HiLoMojoGUI = HiLoGUI


def main(initial_balance=10000, username='Guest', *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """Supreme13-compatible entry point; supports standalone and embedded modes."""
    actual_balance = _amount(initial_balance if balance is None else balance)
    actual_user = username if user is None else user
    if parent is not None:
        return HiLoGUI(parent, actual_balance, actual_user,
                           on_back=on_back, on_balance_change=on_balance_change)
    root = tk.Tk()
    root.title('HiLo')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)
    try:
        page = HiLoGUI(root, actual_balance, actual_user,
                           on_balance_change=on_balance_change)
    except Exception as exc:
        messagebox.showerror('HiLo 无法启动', str(exc), parent=root)
        root.destroy()
        raise
    page.pack(fill=tk.BOTH, expand=True)
    page.on_back = lambda final_balance: root.destroy()
    root.protocol('WM_DELETE_WINDOW', page.on_close)
    root.mainloop()
    return _external_amount(page.balance)


if __name__ == '__main__':
    final_balance = main()
    print(f'Final balance: {final_balance}')
