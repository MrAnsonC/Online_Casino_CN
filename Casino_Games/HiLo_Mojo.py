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
from decimal import Decimal, ROUND_HALF_UP

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
MAIN_PAYOUT = {1: .5, 2: 1, 3: 2, 4: 4, 5: 7, 6: 10, 7: 20, 8: 40}
# The uploaded photograph: first-card 8 is a BONUS win, while the MAIN pushes.
MOJO_MATCH_PAYOUT = {1: 2, 2: 2, 3: 3, 4: 5, 5: 10, 6: 15, 7: 30, 8: 50}


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


def _amount(value):
    if isinstance(value, bool):
        raise ValueError('金额必须是有效数字。')
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0:
            raise ValueError
        rounded = number.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError, ArithmeticError):
        raise ValueError('金额必须是有限的非负数。') from None
    if number != rounded:
        raise ValueError('金额最多保留两位小数。')
    converted = float(rounded)
    if not math.isfinite(converted):
        raise ValueError('金额过大。')
    return converted


def _money(value):
    return float(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def _return_with_profit(stake, odds):
    return _money(Decimal(str(stake)) * (1 + Decimal(str(odds))))


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
        self.game_id = str(game_id or f'HiLoMojo:local:{uuid.uuid4().hex}')
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


def required_direction(card):
    value = card.value if isinstance(card, Card) else RANK_VALUES[str(card)]
    if value == 8:
        return None
    return 'hi' if value < 8 else 'lo'


class HiLoMojoGame:
    """Three independent betting stations share a single, at-most-eight-card row.

    Both HI and LO may be wagered at a station. Only the first draw uses that
    choice. A surviving station then decides cash_out/continue after each win.
    Cashing out terminates that station's bonus; other stations may continue.
    No bankroll mutation is hidden in this class: start_round returns the debit,
    resolved components expose each hand's return, and settle summarizes the
    entire round. The GUI keeps per-hand receipts to prevent duplicate credits.
    """
    SEATS = ('Player1', 'Player2', 'Player3')
    HAND_IDS = SEATS
    BET_KINDS = ('hi', 'lo', 'mojo')

    def __init__(self, deck=None):
        self.deck = CSMDeck() if deck is None else deck
        self.reset_game()

    @staticmethod
    def empty_bet():
        return dict(hi=0.0, lo=0.0, mojo=0.0)

    @property
    def active_hands(self):
        return [seat for seat in self.SEATS if any(self.bets[seat].values())]

    def reset_game(self):
        if getattr(self, 'stage', 'betting') in ('ready', 'decision'):
            raise ValueError('请先完成本局。')
        self.round_key = uuid.uuid4().hex
        self.cards = []
        self.deal_events = []
        self.decisions = []
        self.bets = {seat: self.empty_bet() for seat in self.SEATS}
        self.states = {seat: 'inactive' for seat in self.SEATS}
        self.components = {seat: {} for seat in self.SEATS}
        self.stage = 'betting'
        self.settlement = None
        self.abort_reason = None

    @classmethod
    def validate_bets(cls, bets, balance, high_bet_mode=False):
        balance = _amount(balance)
        if not isinstance(bets, dict) or set(bets) - set(cls.SEATS):
            raise ValueError('下注包含不支持的玩家位置。')
        minimum, maximum = (100, 50000) if high_bet_mode else (10, 10000)
        prepared = {}
        for seat in cls.SEATS:
            source = bets.get(seat, {})
            if not isinstance(source, dict) or set(source) - set(cls.BET_KINDS):
                raise ValueError('下注仅支持 HI、LO 和 匹对红利。')
            row = {kind: _amount(source.get(kind, 0)) for kind in cls.BET_KINDS}
            for value in row.values():
                if value and not minimum <= value <= maximum:
                    raise ValueError(f'每项下注须为 ${minimum:,} 至 ${maximum:,}。')
            if row['mojo'] and not (row['hi'] or row['lo']):
                raise ValueError('匹对红利 边注须搭配同一位置的 HI 或 LO 主注。')
            prepared[seat] = row
        charged = _money(sum(Decimal(str(value)) for row in prepared.values() for value in row.values()))
        if not charged:
            raise ValueError('请至少下注一项 HI 或 LO 主注。')
        if charged > balance:
            raise ValueError('余额不足以支付本局下注。')
        return prepared, charged

    def start_round(self, bets, balance, high_bet_mode=False):
        if self.stage != 'betting':
            raise ValueError('本局尚未结束。')
        prepared, charged = self.validate_bets(bets, balance, high_bet_mode)
        self.deck.start_round()
        self.bets = prepared
        for seat in self.SEATS:
            self.states[seat] = 'ready' if prepared[seat]['hi'] or prepared[seat]['lo'] else 'inactive'
            self.components[seat] = {
                kind: dict(stake=stake, returned=0.0, status='pending' if stake else 'inactive',
                           profit_odds=None, reason='')
                for kind, stake in prepared[seat].items()}
        self.stage = 'ready'
        return charged

    def _resolve(self, seat, kind, status, odds=None, reason=''):
        row = self.components[seat][kind]
        if row['status'] != 'pending':
            return
        returned = (_return_with_profit(row['stake'], odds) if status == 'win'
                    else row['stake'] if status in ('push', 'void') else 0.0)
        row.update(status=status, returned=returned, profit_odds=odds, reason=reason)

    def _pending_main(self, seat):
        return [kind for kind in ('hi', 'lo') if self.components[seat][kind]['status'] == 'pending']

    def _refresh_stage(self):
        if any(state == 'decision' for state in self.states.values()):
            self.stage = 'decision'
        elif any(state == 'ready' for state in self.states.values()):
            self.stage = 'ready'
        else:
            self.stage = 'complete'

    def draw_card(self):
        if self.stage != 'ready':
            raise ValueError('请先完成所有仍在局中的玩家决定。')
        if len(self.cards) >= 8:
            raise ValueError('每局最多派发8张牌。')
        card = self.deck.draw_card()
        previous = self.cards[-1] if self.cards else None
        self.cards.append(card)
        step = len(self.cards)
        direction = None if previous is None else required_direction(previous)
        self.deal_events.append(dict(index=step, card=str(card), rank=card.rank,
                                     suit=card.suit, card_id=card.card_id,
                                     batch_id=card.batch_id,
                                     required='initial_choice' if previous is None else direction))
        for seat in self.SEATS:
            if self.states[seat] != 'ready':
                continue
            if card.value == 8:
                for kind in self._pending_main(seat):
                    self._resolve(seat, kind, 'push', reason='开出8：主注退回本金')
                self._resolve(seat, 'mojo', 'win' if step == 1 else 'loss',
                              MOJO_MATCH_PAYOUT[1] if step == 1 else None,
                              '首张8' if step == 1 else '开出8，未出现同点')
                self.states[seat] = 'push'
                continue
            if step == 1:
                losing = 'lo' if card.value > 8 else 'hi'
                self._resolve(seat, losing, 'loss', reason='首张高低方向不符')
                won, tied = bool(self._pending_main(seat)), False
            else:
                tied = card.value == previous.value
                won = card.value > previous.value if direction == 'hi' else card.value < previous.value
            if not won:
                for kind in self._pending_main(seat):
                    self._resolve(seat, kind, 'loss', reason='同点主注输' if tied else '高低方向不符')
                self._resolve(seat, 'mojo', 'win' if tied else 'loss',
                              MOJO_MATCH_PAYOUT[step] if tied else None,
                              f'第{step}张同点' if tied else '主注失败，未出现同点')
                self.states[seat] = 'lost'
            elif step == 8:
                for kind in self._pending_main(seat):
                    self._resolve(seat, kind, 'win', MAIN_PAYOUT[8], '连续8张成功')
                self._resolve(seat, 'mojo', 'loss', reason='8张成功，未出现同点')
                self.states[seat] = 'won'
            else:
                self.states[seat] = 'decision'
        self._refresh_stage()
        return card

    def legal_actions(self, seat):
        return ('cash_out', 'continue') if (self.stage == 'decision'
                and self.states.get(seat) == 'decision') else ()

    def decide(self, seat, action):
        if action not in self.legal_actions(seat):
            raise ValueError('当前阶段不允许这个决定。')
        self._apply_decision(seat, action)
        self._refresh_stage()

    def decide_all(self, action):
        """Resolve the remaining hands together before advancing the card row.

        A hand that selected Continue can still join All Cash Out while other
        hands are deciding and the next card has not been drawn.
        """
        if self.stage != 'decision' or action not in ('cash_out', 'continue'):
            raise ValueError('当前阶段不允许全部操作。')
        seats = [seat for seat in self.SEATS if self.states[seat] in ('decision', 'ready')]
        if not seats:
            raise ValueError('没有仍在局中的手牌。')
        for seat in seats:
            if action == 'continue' and self.states[seat] == 'ready':
                continue
            self._apply_decision(seat, action)
        self._refresh_stage()
        return seats

    def _apply_decision(self, seat, action):
        self.decisions.append(dict(seat=seat, after_card=len(self.cards), action=action))
        if action == 'cash_out':
            for kind in self._pending_main(seat):
                self._resolve(seat, kind, 'win', MAIN_PAYOUT[len(self.cards)], '玩家兑现')
            self._resolve(seat, 'mojo', 'loss', reason='玩家兑现，未出现同点')
            self.states[seat] = 'cashed_out'
        else:
            self.states[seat] = 'ready'

    def abort_round(self, reason):
        """Machine/forced-destruction recovery: refund only unresolved stakes."""
        if self.stage == 'betting' or self.settlement is not None:
            return
        self.abort_reason = str(reason)
        for seat in self.active_hands:
            had_pending = False
            for kind, row in self.components[seat].items():
                if row['status'] == 'pending':
                    had_pending = True
                    self._resolve(seat, kind, 'void', reason=self.abort_reason)
            if had_pending:
                self.states[seat] = 'void'
        self.stage = 'complete'

    def settle(self):
        if self.settlement is not None:
            return self.settlement
        if self.stage != 'complete':
            raise ValueError('本局尚有未决定或待派发的牌。')
        outcomes = {}
        for seat in self.active_hands:
            rows = {kind: dict(row) for kind, row in self.components[seat].items()}
            stake = _money(sum(row['stake'] for row in rows.values()))
            returned = _money(sum(row['returned'] for row in rows.values()))
            outcomes[seat] = dict(state=self.states[seat], components=rows,
                                  details={kind: row['returned'] for kind, row in rows.items()},
                                  stake=stake, returned=returned, net=_money(returned - stake))
        stake = _money(sum(row['stake'] for row in outcomes.values()))
        returned = _money(sum(row['returned'] for row in outcomes.values()))
        self.settlement = dict(hands=outcomes, stake=stake, returned=returned,
                               net=_money(returned - stake), card_count=len(self.cards),
                               abort_reason=self.abort_reason)
        self.stage = 'settled'
        return self.settlement


def hilo_mojo_log_path():
    directory = Path(project_root()) / 'A_Logs' / 'Json'
    directory.mkdir(parents=True, exist_ok=True)
    return str(directory / 'HiLoMojo.json')


def save_hilo_mojo_history(game, result):
    """Store actual physical draws, never a fictitious duplicate CSM deck order."""
    path = hilo_mojo_log_path()
    data = dict(history_record=dict(game=0, player_win=0, dealer_win=0, push=0,
                                   void=0, mojo_win=0), history=[])
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        if not isinstance(data, dict) or not isinstance(data.get('history'), list):
            raise ValueError('Hi-Lo Mojo 历史资料格式错误。')
    if any(row.get('round_key') == game.round_key for row in data['history']):
        return
    stats = data.setdefault('history_record', {})
    for key in ('game', 'player_win', 'dealer_win', 'push', 'void', 'mojo_win'):
        stats.setdefault(key, 0)
    stats['game'] += 1
    for seat, outcome in result['hands'].items():
        for kind, component in outcome['components'].items():
            if kind == 'mojo':
                stats['mojo_win'] += component['status'] == 'win'
            elif component['stake']:
                key = {'win': 'player_win', 'loss': 'dealer_win', 'push': 'push', 'void': 'void'}[component['status']]
                stats[key] += 1
    data['history'].append(dict(
        game_id=max((row.get('game_id', 0) for row in data['history']), default=0) + 1,
        round_key=game.round_key, timestamp=time.strftime('%Y-%m-%d %H:%M:%S'),
        rules=dict(ace_high=True, neutral_rank='8', max_cards=8,
                   main_payout=MAIN_PAYOUT, mojo_match_payout=MOJO_MATCH_PAYOUT),
        shoe=dict(mode='CSM', decks=CSM_DECKS, total_cards=CSM_CARD_COUNT,
                  game_id=game.deck.game_id),
        deal_events=list(game.deal_events), decisions=list(game.decisions),
        bets={seat: dict(row) for seat, row in game.bets.items()}, result=result))
    data['history'] = data['history'][-50:]
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=4)


class HiLoMojoGUI(tk.Frame):
    WIDTH, HEIGHT = 1150, 750
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    DEAL_CARD_MS = 224 / .85
    DEAL_MOVE_MS = (128 / .75) / .85
    BET_CHIP_RADIUS = 16 * 4 / 3
    HOUSE_CHIP_POS = (575, 45)
    MAIN_PROFIT_OFFSET = (-44, -29)
    MOJO_PROFIT_OFFSET = (44, -29)
    TABLE_GREEN = '#4b1e22'
    SPOT_RADIUS = 35
    SEAT_BOUNDS = {'Player1': (22, 378), 'Player2': (396, 752), 'Player3': (770, 1128)}
    ZONE_COLORS = {'Player1': '#2A5541', 'Player2': '#244D3D', 'Player3': '#204536'}

    def __init__(self, parent, initial_balance, username='Guest', on_back=None,
                 on_balance_change=None, *, deck=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = username, _amount(initial_balance)
        self.on_back, self.on_balance_change = on_back, on_balance_change
        game_id = f'HiLoMojo:{username or "local"}:{uuid.uuid4().hex}'
        self.game = HiLoMojoGame(deck if deck is not None else CSMDeck(game_id=game_id))
        self.engine = self.game.deck
        self.bets = {seat: self.game.empty_bet() for seat in self.game.SEATS}
        self.last_bet, self.last_win = None, 0.0
        self.high_bet_mode, self.selected_chip = False, 10.0
        self._jobs, self._closing = set(), False
        self._claimed_returns = {seat: 0.0 for seat in self.game.SEATS}
        self._saving_balance = False
        self._pending_balance_action = None
        self._restart_job = self._restart_deadline = None
        self._motion_count = self._chip_serial = 0
        self._decision_busy = self._settlement_started = self._phase_busy = False
        self._history_available = self._machine_released = self._machine_fault = False
        self._seen_results, self._revealed_cards = set(), set()
        self.visual_chips, self.last_round_snapshot = {}, None
        self._face_photos, self._pil_cards, self._flip_photos = {}, {}, {}
        self.card_items, self.bet_spots, self.action_buttons = {}, {}, {}
        self.card_poses = {}
        import tkinter.font as tkfont
        families = set(tkfont.families(self))
        self.cn_font = next((name for name in ('Microsoft YaHei UI', 'Microsoft YaHei',
                            'Noto Sans CJK SC', 'WenQuanYi Zen Hei', 'Arial Unicode MS')
                            if name in families), 'Arial')
        self._load_assets()
        self._create_widgets()
        self._refresh()
        self.bind('<Destroy>', self._on_destroy, add='+')

    @property
    def game_in_progress(self):
        return self.game.stage != 'betting' or self._motion_count > 0

    @staticmethod
    def _base_seat(seat):
        return seat

    def _text(self, x, y, text, size=12, color=TEXT, **kw):
        return self.canvas.create_text(x, y, text=text, fill=color,
                                       font=(self.cn_font, size, 'bold'), **kw)

    def card_position(self, side, index):
        return 178 + index * 120, 325

    def _create_widgets(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=ROOT_BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.control_buttons = {}
        c = self.canvas
        self._text(575, 28, 'HI-LO MOJO', 25, GOLD)
        self._text(575, 65, 'CSM  ·  8副牌  /  416张', 12, PANEL_BG)
        self.status_item = self._text(575, 111, '', 18, GOLD, width=400, justify='center')
        self._draw_limit_table()
        self._draw_payout_tables()
        c.create_rectangle(22, 261, 1128, 307, fill='#173C2E', outline='#65784B')
        self._text(575, 284, 'A 最大 · 2 最小    当前2–7 → 下一张更大    当前9–A → 下一张更小    同点主注输 · 8退主注', 16, GOLD)
        c.create_rectangle(45, 325, 125, 437, fill='#123c30', outline=GOLD, width=2)
        self._text(85, 381, '8', 44, GOLD)
        self._text(148, 380, '→', 22, GOLD)
        self.slot_labels = []
        for index in range(8):
            x, y = self.card_position('Table', index)
            c.create_rectangle(x - 2, y - 2, x + self.CARD_WIDTH + 2, y + self.CARD_HEIGHT + 2,
                               outline='#7B9374', dash=(3, 3), tags=f'slot_{index}')
            self.slot_labels.append(self._text(x + 40, y + self.CARD_HEIGHT / 2,
                f'第{index + 1}张\n{MAIN_PAYOUT[index+1]:g}:1', 13, PANEL_BG,
                justify='center', tags=f'slot_label_{index}'))
        for seat, (x0, x1) in self.SEAT_BOUNDS.items():
            self._draw_eight_station(seat, x0 + 166, 533)
            self._draw_spot(seat, 'mojo', x0 + 279, 533, '匹对\n红利', radius=28)
            button_height, button_gap = 41, 10
            button_top = 533 - (2 * button_height + button_gap) // 2
            for index, (action, caption, fill) in enumerate((
                    ('cash_out', '兑现', '#397A48'), ('continue', '继续', DARK_BLUE))):
                top = button_top + index * (button_height + button_gap)
                self.action_buttons[(seat, action)] = self.create_control_button(
                    x0 + 6, top, x0 + 84, top + button_height, caption,
                    lambda s=seat, a=action: self._decide(s, a), fill,
                    font_size=11, draw_shadow=False)
        self._draw_bet_separators()
        self._draw_bottom_controls()

    def _draw_bet_separators(self):
        bounds = list(self.SEAT_BOUNDS.values())
        # Only divide one hand's bonus area from the next hand's buttons.
        for (_, right), (next_left, _) in zip(bounds, bounds[1:]):
            x = (right + next_left) / 2
            self.canvas.create_line(x, 450, x, 617, fill='#8FA68E',
                width=1, dash=(5, 5), tags='bet_separator')

    def _draw_limit_table(self):
        c = self.canvas
        x0, x1, y0, y1 = 376, 774, 148, 244
        c.create_rectangle(x0, y0, x1, y1, fill=ROOT_BG, outline=GOLD, width=2, tags='limits')
        self._text(575, 164, '下注限额', 12, PANEL_BG, tags='limits')
        self.limit_value_items = []
        for column, caption in enumerate(('每项最低', '主注最高', '边注最高')):
            left, right = x0 + column * (x1 - x0) / 3, x0 + (column + 1) * (x1 - x0) / 3
            c.create_rectangle(left, 181, right, y1, outline='#77906B', tags='limits')
            self._text((left + right) / 2, 197, caption, 10, PANEL_BG, tags='limits')
            self.limit_value_items.append(self._text((left + right) / 2, 224, '', 12, GOLD, tags='limits'))
        c.tag_bind('limits', '<Button-1>', self.toggle_high_bet_limits)
        c.tag_bind('limits', '<Enter>', lambda _e: c.configure(cursor='hand2'))
        c.tag_bind('limits', '<Leave>', lambda _e: c.configure(cursor=''))

    def _draw_payout_tables(self):
        for x0, x1, title, payouts in ((22, 350, '主注兑现 · 净赢赔率', MAIN_PAYOUT),
                                       (800, 1128, '匹对红利 · 净赢赔率', MOJO_MATCH_PAYOUT)):
            self.canvas.create_rectangle(x0, 12, x1, 244, fill='#123C30', outline=GOLD, width=2)
            self._text((x0 + x1) / 2, 33, title, 13, GOLD)
            for index in range(1, 9):
                caption = f'连续成功 {index} 张' if payouts is MAIN_PAYOUT else (
                    '第1张是 8' if index == 1 else f'第{index}张同点')
                self._text(x0 + 18, 61 + (index - 1) * 24, caption, 11, PANEL_BG, anchor='w')
                self._text(x1 - 19, 61 + (index - 1) * 24,
                           f'{payouts[index]:g} : 1', 12, GOLD, anchor='e')

    def _draw_eight_station(self, seat, cx, cy):
        """Upright reference layout: broad lower lobe, oval holes and offset rim.

        A sampled cubic outline keeps the reference's rounded bands and the
        two aligned hole centres, without applying the photograph's tilt.
        """
        tag = f'eight_{seat}'
        start = (0, -77)
        segments = [((43,-77),(57,-57),(57,-38)),
                    ((57,-18),(42,-9),(32,-3)),
                    ((57,8),(70,24),(70,43)),
                    ((70,70),(42,80),(0,80)),
                    ((-42,80),(-70,70),(-70,43)),
                    ((-70,24),(-57,8),(-32,-3)),
                    ((-42,-9),(-57,-18),(-57,-38)),
                    ((-57,-57),(-43,-77),(0,-77))]
        points = [start]
        for control1, control2, end in segments:
            for step in range(1, 17):
                t, u = step / 16, 1 - step / 16
                points.append((u**3*start[0]+3*u*u*t*control1[0]+3*u*t*t*control2[0]+t**3*end[0],
                               u**3*start[1]+3*u*u*t*control1[1]+3*u*t*t*control2[1]+t**3*end[1]))
            start = end
        for dx, dy, color, outline, width in (
                (7, 6, '#78BCA9', PANEL_BG, 1.3),
                (3, 2, ROOT_BG, ROOT_BG, 3.5),
                (0, 0, '#7BBDA8', PANEL_BG, 1.5)):
            self.canvas.create_polygon(*[v for x,y in points for v in (cx+x+dx, cy+y+dy)],
                fill=color, outline=outline, width=width, tags=tag)
        self.canvas.tag_bind(tag, '<Button-1>', lambda event:
            self.add_chip_to_bet(seat, 'hi' if event.y < cy else 'lo'))
        self.canvas.tag_bind(tag, '<Button-3>', lambda event:
            self.reset_single_bet(seat, 'hi' if event.y < cy else 'lo'))
        self.canvas.tag_bind(tag, '<Enter>', lambda _e: self.canvas.configure(
            cursor='' if self.game_in_progress else 'hand2'))
        self.canvas.tag_bind(tag, '<Leave>', lambda _e: self.canvas.configure(cursor=''))
        self._draw_spot(seat, 'hi', cx, cy - 39, 'HI', radius=(32, 24))
        self._draw_spot(seat, 'lo', cx, cy + 37, 'LO', radius=(43, 31))

    def _draw_spot(self, seat, kind, cx, cy, label, radius=None):
        tag, r = f'spot_{seat}_{kind}', radius or self.SPOT_RADIUS
        rx, ry = r if isinstance(r, tuple) else (r, r)
        border = self.canvas.create_oval(cx-rx, cy-ry, cx+rx, cy+ry,
            fill='#CE2A85' if kind in ('hi', 'lo') else '#75B69D',
            outline=PANEL_BG, width=1.5, tags=tag)
        if kind in ('hi', 'lo'):
            # Large, outlined upright letters and directional arrow, as in
            # the supplied felt photograph. All items share one hit target.
            font = ('Arial', 18, 'bold italic')
            for dx, dy in ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,1)):
                self.canvas.create_text(cx-5+dx, cy+dy, text=label,
                    font=font, fill=PANEL_BG, tags=tag)
            item = self.canvas.create_text(cx-5, cy, text=label,
                font=font, fill='#2D817A', tags=tag)
            arrow = [(17,8),(17,-3),(12,-3),(22,-13),(32,-3),(27,-3),(27,8)]
            sign = 1 if kind == 'hi' else -1
            self.canvas.create_polygon(*[v for x,y in arrow for v in (cx+x, cy+sign*y)],
                fill='#77BCAA', outline=PANEL_BG, width=1.5, tags=tag)
        else:
            item = self._text(cx, cy, label, 11, TEXT, justify='center', tags=tag)
        self.bet_spots[(seat, kind)] = dict(tag=tag, center=(cx, cy), border=border,
                                          label_item=item, label=label)
        self.canvas.tag_bind(tag, '<Button-1>', lambda _e: self.add_chip_to_bet(seat, kind))
        self.canvas.tag_bind(tag, '<Button-3>', lambda _e: self.reset_single_bet(seat, kind))
        self.canvas.tag_bind(tag, '<Enter>', lambda _e: self.canvas.configure(
            cursor='' if self.game_in_progress else 'hand2'))
        self.canvas.tag_bind(tag, '<Leave>', lambda _e: self.canvas.configure(cursor=''))

    def _draw_bottom_controls(self):
        c = self.canvas
        c.create_rectangle(0, 625, 1150, 748, fill=ROOT_BG, outline='#6C7850', width=2)
        self.balance_item = self._text(10, 665, '', 16, TEXT, anchor='w')
        self.total_item = self._text(10, 710, '', 15, TEXT, anchor='w')
        self.clear_button = self.create_control_button(278, 650, 344, 704, '清除', self.reset_bets,
            '#9B403A', font_size=11, draw_shadow=False)
        self._draw_chips()
        self.info_button = self.create_control_button(810, 650, 855, 695, '?', self.show_game_instructions,
            DARK_BLUE, font_size=17, draw_shadow=False)
        self.repeat_button = self.create_control_button(862, 638, 1000, 708, '重复下注', self.apply_last_bet,
            '#536A43', font_size=11, draw_shadow=False)
        self.start_button = self.create_control_button(1012, 628, 1138, 720, '开牌', self.start_game,
            HEADER_BG, fg=TITLE_FG, font_size=14, draw_shadow=False)
        self.restart_button = self.create_control_button(862, 638, 1138, 708, '再来一局', self._return_all_chips,
            HEADER_BG, fg=TITLE_FG, font_size=17, draw_shadow=False)
        c.tag_bind(self.restart_button, '<Button-3>', self._inspect_completed_round)
        c.itemconfigure(self.restart_button, state='hidden')
        self._enter_binding = self.winfo_toplevel().bind('<Return>', self._handle_enter, add='+')

    def _handle_enter(self, _event=None):
        if self._pending_balance_action is not None or self.game.stage in ('await_restart', 'credit_pending'):
            self._return_all_chips()
        elif self.game.stage == 'betting':
            self.start_game()

    def _remaining_return(self, seat=None):
        """Resolved returns held on the table until the entire round settles."""
        seats = self.game.SEATS if seat is None else (seat,)
        total = 0.0
        for current in seats:
            if self.game.states[current] in ('inactive', 'ready', 'decision'):
                continue
            returned = _money(sum(row['returned']
                for row in self.game.components.get(current, {}).values()))
            total = _money(total + max(0.0, _money(returned - self._claimed_returns[current])))
        return total

    def _refresh(self):
        c = self.canvas
        c.itemconfigure(self.balance_item, text=f'余额: ${self.balance:,.2f}')
        total = _money(sum(sum(row.values()) for row in self.bets.values()))
        if self.game.settlement is not None and self.game.stage in (
                'await_restart', 'returning', 'credit_pending', 'sweeping'):
            total_text = f'上局返还: ${self.last_win:,.2f}'
        else:
            total_text = f'本局下注: ${total:,.2f}' if total else f'上局返还: ${self.last_win:,.2f}'
        c.itemconfigure(self.total_item, text=total_text)
        minimum, maximum = (100, 50000) if self.high_bet_mode else (10, 10000)
        for item, value in zip(self.limit_value_items, (minimum, maximum, maximum)):
            c.itemconfigure(item, text=f'${value:,}')
        pending_save = self._pending_balance_action is not None
        ready = not (pending_save or self._decision_busy or self._phase_busy or self._motion_count)
        betting = self.game.stage == 'betting' and ready
        self.set_control_button_state(self.clear_button, betting)
        if self.game.stage == 'betting':
            labels = ((self.repeat_button, '重复下注', self.apply_last_bet),
                      (self.start_button, '开牌', self.start_game))
            repeat_enabled, start_enabled = betting and bool(self.last_bet), betting
        else:
            labels = ((self.repeat_button, '全部继续', lambda: self._decide_all('continue')),
                      (self.start_button, '全部兑现', lambda: self._decide_all('cash_out')))
            can_decide = ready and self.game.stage == 'decision'
            repeat_enabled = start_enabled = can_decide
        for tag, caption, command in labels:
            self.control_buttons[tag]['command'] = command
            c.itemconfigure(self.control_buttons[tag]['text'], text=caption)
        self.set_control_button_state(self.repeat_button, repeat_enabled)
        self.set_control_button_state(self.start_button, start_enabled)
        restarting = pending_save or self.game.stage in ('await_restart', 'returning', 'credit_pending', 'sweeping')
        c.itemconfigure(self.repeat_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button, state='normal' if restarting else 'hidden')
        self.set_control_button_state(self.restart_button, not self._saving_balance and (
            pending_save or (ready and self.game.stage in ('await_restart', 'credit_pending'))))
        if pending_save:
            self._restart_caption('重试保存余额')
        elif self.game.stage == 'credit_pending':
            self._restart_caption('重试归还CSM牌张')
        else:
            self._restart_caption('全部兑现' if self._remaining_return() else '再来一局')
        for seat in self.game.SEATS:
            for action in ('cash_out', 'continue'):
                legal = action in self.game.legal_actions(seat)
                self.set_control_button_state(self.action_buttons[(seat, action)],
                    ready and legal)
            for kind in ('hi', 'lo'):
                spot = self.bet_spots[(seat, kind)]
                row = self.game.components.get(seat, {}).get(kind, {})
                c.itemconfigure(spot['label_item'],
                    fill=GOLD if row.get('status') == 'win' else '#2D817A')
        for index in range(8):
            c.itemconfigure(f'slot_{index}', outline=GOLD if index == len(self._revealed_cards) else '#7B9374')
        visible = [card for index, card in enumerate(self.game.cards)
                   if ('Table', index) in self._revealed_cards]
        if visible:
            last = visible[-1]
            if last.value == 8:
                text = '8 · 本局结束'
            else:
                direction = '高于' if required_direction(last) == 'hi' else '低于'
                text = f'{last.rank} · 下一张{direction}{last.rank}'
        else:
            text = '8 · 下一张高于或低于8'
        c.itemconfigure(self.status_item, text=text)
        self._render_chips()

    def add_chip_to_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count or self._pending_balance_action is not None:
            return
        if seat not in self.game.SEATS or kind not in self.game.BET_KINDS:
            return
        new = {side: dict(row) for side, row in self.bets.items()}
        maximum = 50000 if self.high_bet_mode else 10000
        new[seat][kind] = min(maximum, _money(new[seat][kind] + self.selected_chip))
        self._apply_bet_layout(new)

    def reset_single_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count or self._pending_balance_action is not None:
            return
        new = {side: dict(row) for side, row in self.bets.items()}
        new[seat][kind] = 0.0
        if kind in ('hi', 'lo') and not (new[seat]['hi'] or new[seat]['lo']):
            new[seat]['mojo'] = 0.0
        self._apply_bet_layout(new)

    def _apply_bet_layout(self, new_bets):
        if self.game.stage != 'betting' or self._motion_count or self._pending_balance_action is not None:
            return
        new = {seat: dict(new_bets.get(seat, self.game.empty_bet())) for seat in self.game.SEATS}
        if _money(sum(sum(row.values()) for row in new.values())) > self.balance:
            messagebox.showwarning('余额不足', '余额不足以支付这组下注。', parent=self)
            return
        previous, self.bets = self.bets, new
        transfers = []
        for seat in self.game.SEATS:
            for kind in self.game.BET_KINDS:
                old, current = previous[seat][kind], new[seat][kind]
                delta = _money(current - old)
                if not delta:
                    continue
                center = self.bet_spots[(seat, kind)]['center']
                if delta > 0:
                    transfers.append(dict(amount=delta, start=self._rack_position(), target=center,
                        arrive=lambda s=seat, k=kind, a=current: self._set_visual(s, k, 'stake', a)))
                else:
                    self._set_visual(seat, kind, 'stake', current)
                    transfers.append(dict(amount=-delta, start=center, target=self._rack_position(), duration=440))
        self._run_chip_batch(transfers, self._refresh)
        self._refresh()

    def start_game(self):
        if self.game.stage != 'betting' or self._motion_count or self._pending_balance_action is not None:
            return
        try:
            self.game.validate_bets(self.bets, self.balance, self.high_bet_mode)
        except ValueError as exc:
            messagebox.showwarning('无法开始', str(exc), parent=self)
            return
        try:
            charged = self.game.start_round(self.bets, self.balance, self.high_bet_mode)
        except Exception as exc:
            # A start failure can occur after a chamber has been leased.
            try:
                if self.game.stage == 'betting':
                    self.engine.close()
            except Exception:
                pass
            messagebox.showwarning('无法开始', str(exc), parent=self)
            return
        self._machine_released = False
        self._history_available = self._machine_fault = False
        self._close_card_sequence()
        self.balance = _money(self.balance - charged)
        self.bets = {seat: dict(row) for seat, row in self.game.bets.items()}
        self.last_bet = {seat: dict(row) for seat, row in self.bets.items()}
        self._claimed_returns = {seat: 0.0 for seat in self.game.SEATS}
        self._settlement_started = False
        self._decision_busy = False
        self._phase_busy = True
        self._cancel_restart_timer()
        self._seen_results.clear()
        self._revealed_cards.clear()
        self.canvas.delete('cards')
        self.card_items.clear()
        self.card_poses.clear()
        self._flip_photos.clear()
        self._load_assets()
        self._save_and_continue(self._deal_one)

    def _deal_one(self):
        if self.game.stage != 'ready' or self._closing:
            return
        self._phase_busy = True
        try:
            self.game.draw_card()
        except Exception as exc:
            self._machine_fault = True
            self.game.abort_round(f'CSM发牌异常：{exc}')
            self._phase_busy = False
            messagebox.showerror('自动洗牌机', f'本局已停止发牌：{exc}\n已确定的结果保留，未决下注退回。', parent=self)
            self._settle()
            return
        index = len(self.game.cards) - 1
        self._refresh()
        self._deal_next([('Table', index)], 0,
            lambda: self._reveal_next([('Table', index)], 0, self._after_card))

    def _reveal_next(self, sequence, offset, complete):
        if offset == len(sequence):
            complete()
            return
        side, index = sequence[offset]
        card, item = self.game.cards[index], self.card_items[(side, index)]
        x, y = self.card_position(side, index)
        def flip(step=0):
            width = max(1, round(self.CARD_WIDTH * abs(1 - step / 5)))
            source = self._pil_cards['back' if step < 5 else (card.suit, card.rank)]
            photo = ImageTk.PhotoImage(source.resize((width, self.CARD_HEIGHT), Image.Resampling.LANCZOS), master=self)
            self._flip_photos[item] = photo
            self.canvas.itemconfigure(item, image=photo)
            self.canvas.coords(item, x + (self.CARD_WIDTH - width) / 2, y)
            if step < 10:
                self._schedule(32, flip, step + 1)
            else:
                self.canvas.itemconfigure(item, image=self._face_photos[(card.suit, card.rank)])
                self._flip_photos.pop(item, None)
                self._revealed_cards.add((side, index))
                self._reveal_next(sequence, offset + 1, complete)
        flip()

    def _after_card(self):
        self._phase_busy = False
        self._decision_busy = True
        self._pose_last_card(lambda: self._animate_new_results(self._after_results))

    def _last_card_needs_mark(self):
        if not self.game.cards:
            return False
        last = self.game.cards[-1]
        if last.value == 8:
            return True
        if len(self.game.cards) == 1:
            # A shared opening card is only a loss marker when no hand survives.
            return self.game.stage == 'complete' and any(
                state == 'lost' for state in self.game.states.values())
        previous = self.game.cards[-2]
        if last.value == previous.value:
            return True
        return (last.value < previous.value if required_direction(previous) == 'hi'
                else last.value > previous.value)

    def _pose_last_card(self, complete):
        index = len(self.game.cards) - 1
        if index in self.card_poses or not self._last_card_needs_mark():
            complete()
            return
        card = self.game.cards[index]
        item = self.card_items[('Table', index)]
        source = self._pil_cards[(card.suit, card.rank)]
        x, y = self.card_position('Table', index)
        self._motion_count += 1
        self._refresh()
        def frame(step=0):
            fraction = step / 8
            # Pillow's negative angle is clockwise. Keep the rotation pivot
            # at the card centre, then translate that centre down by 10px.
            rotated = source.rotate(-20 * fraction, resample=Image.Resampling.BICUBIC, expand=True)
            photo = ImageTk.PhotoImage(rotated, master=self)
            self._flip_photos[item] = photo
            self.canvas.itemconfigure(item, image=photo)
            self.canvas.coords(item, x + (self.CARD_WIDTH - rotated.width) / 2,
                               y + (self.CARD_HEIGHT - rotated.height) / 2 + 10 * fraction)
            if step < 8:
                self._schedule(20, frame, step + 1)
            else:
                self.card_poses[index] = dict(clockwise_degrees=20, down_pixels=10)
                self._motion_count -= 1
                complete()
        frame()

    def _after_results(self):
        self._decision_busy = False
        self._refresh()
        if self.game.stage == 'complete':
            self._settle()
        elif self.game.stage == 'ready':
            self._phase_busy = True
            self._refresh()
            self._schedule(150, self._deal_one)

    def _animate_new_results(self, complete):
        transfers = []
        for seat in self.game.active_hands:
            for kind, row in self.game.components[seat].items():
                key = (seat, kind)
                if row['status'] == 'pending':
                    # Every confirmed successful card updates the held profit
                    # to this tier's total; tiers are never added together.
                    if (kind in ('hi', 'lo') and self.game.cards
                            and self.game.states[seat] in ('decision', 'ready')
                            and len(self._revealed_cards) == len(self.game.cards)):
                        target = _money(_return_with_profit(row['stake'],
                            MAIN_PAYOUT[len(self.game.cards)]) - row['stake'])
                        transfers.extend(self._profit_transfers(seat, kind, target))
                    continue
                if row['status'] == 'inactive' or key in self._seen_results:
                    continue
                self._seen_results.add(key)
                transfers.extend(self._outcome_transfers(seat, kind, row['stake'], row['returned']))
        self._refresh()
        self._run_chip_batch(transfers, complete)

    def _decide(self, seat, action):
        if (self._pending_balance_action is not None or self._decision_busy or self._phase_busy
                or self._motion_count):
            return
        if action not in self.game.legal_actions(seat):
            return
        self._decision_busy = True
        self.game.decide(seat, action)
        self._animate_new_results(self._after_results)

    def _decide_all(self, action):
        if (self._pending_balance_action is not None or self._decision_busy or self._phase_busy
                or self._motion_count or self.game.stage != 'decision'):
            return
        if action not in ('cash_out', 'continue'):
            return
        self._decision_busy = True
        self.game.decide_all(action)
        self._animate_new_results(self._after_results)

    def _claim_seats(self, seats, complete):
        """At round end, credit each resolved return once, then fly its chips.

        The receipt is recorded before saving. A failed save resumes the same
        animation after retry and cannot credit those funds a second time.
        No station may bank its locked return while another is still playing.
        """
        if self.game.settlement is None or self.game.stage not in ('settling', 'await_restart'):
            return
        selected = [seat for seat in seats if self._remaining_return(seat)]
        if not selected:
            complete()
            return
        amount = _money(sum(self._remaining_return(seat) for seat in selected))
        self.balance = _money(self.balance + amount)
        for seat in selected:
            self._claimed_returns[seat] = _money(sum(
                row['returned'] for row in self.game.components[seat].values()))
        def after_save():
            chips = [(key, chip) for key, chip in self.visual_chips.items() if key[0] in selected]
            transfers = []
            for index, (key, chip) in enumerate(chips):
                self.visual_chips.pop(key, None)
                transfers.append(dict(amount=chip['amount'], start=chip['xy'],
                    target=self._rack_position(index, len(chips)), duration=540))
            self._refresh()
            self._run_chip_batch(transfers, complete)
        self._save_and_continue(after_save)

    def _settle(self):
        if self._settlement_started:
            return
        self._settlement_started = True
        self._decision_busy = True
        result = self.game.settle()
        self.last_win = result['returned']
        self.game.stage = 'settling'
        try:
            self.engine.finish_round()
        except Exception as exc:
            self._machine_fault = True
            messagebox.showerror('自动洗牌机', f'本局结果已确定，但还牌发生异常：{exc}\n收款后将重新释放本游戏的CSM牌张。', parent=self)
        try:
            save_hilo_mojo_history(self.game, result)
        except Exception as exc:
            messagebox.showerror('历史记录保存失败', str(exc), parent=self)
        self._animate_new_results(lambda: self._claim_seats(
            self.game.active_hands, self._await_next_round))

    def _await_next_round(self):
        if self.game.stage != 'settling':
            return
        self.game.stage = 'await_restart'
        self._phase_busy = False
        self._decision_busy = False
        self.last_round_snapshot = dict(cards=tuple(self.game.cards),
            images={key: image.copy() for key, image in self.original_images.items()})
        self._history_available = True
        self._cancel_restart_timer()
        self._refresh()

    def _finish_round(self):
        if self.game.stage != 'sweeping':
            return
        if self._machine_fault:
            try:
                self.engine.close()
            except Exception as exc:
                self._restart_caption('重试归还CSM牌张')
                self.game.stage = 'credit_pending'
                self._refresh()
                messagebox.showerror('自动洗牌机', f'无法释放牌张：{exc}\n请点击按钮重试。', parent=self)
                return
        self.game.reset_game()
        self.card_poses.clear()
        self._history_available = self._phase_busy = self._decision_busy = False
        self.bets = {seat: self.game.empty_bet() for seat in self.game.SEATS}
        self.visual_chips.clear()
        self._refresh()

    def reset_game(self, auto_reset=False):
        if self.game.stage == 'betting':
            self.reset_bets()

    def show_card_sequence(self, event=None):
        if self.game.stage != 'await_restart' or not self._history_available:
            return
        snapshot = self.last_round_snapshot
        current = getattr(self, '_sequence_window', None)
        if current is not None and current.winfo_exists():
            current.lift()
            return
        win = tk.Toplevel(self)
        self._sequence_window = win
        win.title('上局实际发牌')
        win.geometry('860x260')
        win.resizable(False, False)
        win.configure(bg=ROOT_BG)
        tk.Label(win, text='上局实际发牌（从左到右）；开局参考8不占用实体牌',
                 font=(self.cn_font, 14, 'bold'), bg=ROOT_BG, fg=GOLD).pack(pady=16)
        row = tk.Frame(win, bg=ROOT_BG)
        row.pack()
        win._card_images = []
        for index, card in enumerate(snapshot['cards']):
            photo = ImageTk.PhotoImage(snapshot['images'][(card.suit, card.rank)].resize(
                (70, 98), Image.Resampling.LANCZOS), master=win)
            win._card_images.append(photo)
            cell = tk.Frame(row, bg=ROOT_BG)
            cell.pack(side=tk.LEFT, padx=12)
            tk.Label(cell, image=photo, bg=ROOT_BG).pack()
            tk.Label(cell, text=f'第{index+1}张 · {card}', font=(self.cn_font, 10),
                     bg=ROOT_BG, fg=PANEL_BG).pack(pady=8)

    def _instruction_pages(self):
        return [
            ('玩法', [
                ('起点与牌序', 'A最大，2最小，花色不影响大小。桌面8只是开局参考，不取实体牌。'
                 '\n3个下注区共用同一列实体牌，每局最多8张；可自由选择其中1–3手下注。'),
                ('开局下注', '左键增加HI、LO或匹对红利，右键清除；HI和LO可同时下注。'
                 '\nHI首张须为9–A，LO首张须为2–7；首张8令两项主注退回，边注赢2:1。'
                 '\n边注必须搭配同一位置至少一项主注。下注在开牌时扣款，不需后续加注。'),
                ('赢后决定', '每次成功后，可点击“兑现”锁定当前张数的收益，或继续。'
                 '\n兑现后该位置的兑现和继续按钮变灰，获胜主注文字变金色，筹码留在原位。'
                 '\n继续时当前牌2–7则下一张必须更大，当前牌9–A则下一张必须更小。'
                 '\n各下注区独立决定，全部仍在局中的玩家决定后才发下一张。'
                 '\n右下角“全部继续”和“全部兑现”可同时操作仍在局中的手牌。'),
                ('失败、8与同点', '大小方向不符，主注输；连续两张同点数，主注也输。'
                 '\n任何一张开出8，未兑现主注只退原本金，本局停止；之前未兑现的奖金不支付。'
                 '\n8的特殊规则优先，不能把2接8当作主注成功。'),
            ], []),
            ('主注赔率', [('赔付口径', '赔率表示净赢，返还包含本金；按原下注金额计算，不逐次相加。'
                '\n例如主注100连续成功4张后兑现，净赢400，返还500。'
                '\n两边同时下注时，首张失败的一边已输，之后赔率只用于仍在局中的一边。')],
                [('主注兑现', ('连续成功张数', '净赢赔率'),
                  [(str(step), f'{odds:g} : 1') for step, odds in MAIN_PAYOUT.items()])]),
            ('匹对红利', [
                ('获胜条件', '首张是8，或第2–8张与紧邻前一张点数相同，支付下表对应奖金。'
                 '\n只比较点数，不要求同花色。边注独立结算：同点时主注输、边注赢。'),
                ('没有和局', '边注不能和局。首张8是边注获胜；之后开出8则边注输。'
                 '\n主注方向失败、玩家兑现或连续成功8张而没有同点，该位置边注输。'
                 '\n已兑现的位置不再参与其他位置继续发出的牌，不会后来再赢边注。')],
                [('边注净赢赔率', ('结果', '赔率'),
                  [('首张8' if step == 1 else f'第{step}张同点', f'{odds} : 1')
                   for step, odds in MOJO_MATCH_PAYOUT.items()])]),
            ('收款与牌张', [
                ('收款', '每张成功的牌都会将当前档位的盈利筹码派到获胜区，按档位总额更新，不逐档累加。'
                 '\n点击“兑现”或“全部兑现”只锁定收益，余额暂不增加；已兑现手牌不再参与，其他手可继续。'
                 '\n所有主注都已兑现或结束后，系统统一返还筹码并入账。'
                 '\n匹对红利、开出8或连续成功8张也在整局结束时自动结算；点击“再来一局”清理牌面。'
                 '\n右键底部按钮查看上局实际发牌。余额保存失败时请点击重试。'),
                ('牌张', '使用8副完整扑克牌，共416张，不含大小王。'
                 '\n每局最多发8张牌，已用牌会在牌局结束后回收并持续洗匀。'),
                ('退出', '请先完成所有主注的决定，等待整局结算及筹码返还后再退出。'
                 '\n发牌异常会停止本局，已确定的结果保留，未决下注退回。'),
            ], []),
        ]

    def on_close(self):
        if self._closing or self._saving_balance:
            return
        if self._pending_balance_action is not None:
            messagebox.showinfo('余额待保存', '请先点击“重试保存余额”，保存成功后继续。', parent=self)
            return
        settled = self.game.stage in ('settling', 'await_restart', 'returning', 'credit_pending', 'sweeping')
        if self.game_in_progress and not settled:
            messagebox.showinfo('牌局进行中', '请先完成本局的决定和结算。', parent=self)
            return
        if self._remaining_return():
            messagebox.showinfo('尚有待兑现筹码', '请先点击“兑现”或“全部兑现”收回本局筹码。', parent=self)
            return
        try:
            self.engine.close()
            self._machine_released = True
        except Exception as exc:
            self._machine_fault = True
            messagebox.showerror('自动洗牌机', f'归还牌张失败：{exc}\n请再次退出以重试。', parent=self)
            return
        if not self._persist_balance():
            return
        self._closing = True
        self._cancel_restart_timer()
        self._cancel_jobs()
        self._unbind_enter()
        self._close_card_sequence()
        dialog = getattr(self, '_game_instruction_dialog', None)
        if dialog is not None and dialog.winfo_exists():
            dialog.destroy()
        if callable(self.on_back):
            self.on_back(float(self.balance))
        else:
            self.winfo_toplevel().destroy()

    def _on_destroy(self, event):
        if event.widget is not self:
            return
        was_closing = self._closing
        self._closing = True
        self._pending_balance_action = None
        self._cancel_jobs()
        self._unbind_enter()
        if not self._machine_released:
            try:
                self.engine.close()
                self._machine_released = True
            except Exception as exc:
                print(f'Hi-Lo Mojo CSM释放失败：{exc}', file=sys.stderr)
        if not was_closing and self.game.stage != 'betting':
            # A host can destroy the Frame without invoking its close handler.
            # Preserve resolved results, refund only unresolved escrow, and
            # avoid creating dialogs after Tcl has started destroying widgets.
            self.game.abort_round('宿主窗口已关闭，退回未决注')
            if self.game.settlement is None:
                self.last_win = self.game.settle()['returned']
            remaining = self._remaining_return()
            self.balance = _money(self.balance + remaining)
            for seat in self.game.SEATS:
                self._claimed_returns[seat] = _money(sum(
                    row['returned'] for row in self.game.components.get(seat, {}).values()))
            try:
                if self.username and self.username != 'Guest':
                    update_balance_in_json(self.username, self.balance)
                if callable(self.on_balance_change):
                    self.on_balance_change(float(self.balance))
            except Exception as exc:
                print(f'Hi-Lo Mojo关闭时余额保存失败：{exc}', file=sys.stderr)


    # Shared UI, animation, assets and balance helpers retained from Supreme13.

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
            self.visual_chips[key] = dict(amount=float(amount), xy=xy or self.bet_spots[(seat, kind)]['center'])
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


    @staticmethod
    def _compact(amount):
        """K/M筹码取两位有效数字并截断；有省略才加+，不改动真实金额。"""
        from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
        value=Decimal(str(amount)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
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


    def reset_bets(self):
        if self.game.stage=='betting' and not self._motion_count:
            self._apply_bet_layout({s:self.game.empty_bet() for s in self.game.SEATS})


    def apply_last_bet(self):
        if self.game.stage=='betting' and not self._motion_count and self.last_bet:
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
            self.canvas.itemconfigure(button['rim'], fill=self.shade_color(button['fill'], 0.55))
            self.canvas.itemconfigure(button['highlight'], fill='#66615b')
            self.canvas.itemconfigure(button['text'], fill='#9b9690')
            if button.get('subtext'):
                self.canvas.itemconfigure(button['subtext'], fill='#9b9690')


    def _chip_color(self, amount):
        return next((col for value,col in reversed(self.chip_specs) if amount>=value),HEADER_BG)


    def _rack_position(self, index=None, total=1):
        if index is not None:
            return 575+(index-(total-1)/2)*min(28,140/max(1,total-1)),674
        index=next((i for i,(value,_) in enumerate(self.chip_specs) if value==self.selected_chip),None)
        if index is None:return (575,674)
        width=len(self.chip_specs)*56+(len(self.chip_specs)-1)*8
        return (self.WIDTH-width)/2+index*64+28,674


    def _profit_transfers(self, seat, kind, target_profit):
        """Only move the difference to/from the winning area, never the wallet."""
        key = (seat, kind, 'profit')
        previous = self.visual_chips.get(key, {}).get('amount', 0.0)
        delta = _money(target_profit - previous)
        if not delta:
            return []
        center = self.bet_spots[(seat, kind)]['center']
        dx, dy = self.MOJO_PROFIT_OFFSET if kind == 'mojo' else self.MAIN_PROFIT_OFFSET
        target = (center[0] + dx, center[1] + dy)
        if delta > 0:
            return [dict(amount=delta, start=self.HOUSE_CHIP_POS, target=target, duration=360,
                arrive=lambda: self._set_visual(seat, kind, 'profit', target_profit, target))]
        source = self.visual_chips[key]['xy']
        self._set_visual(seat, kind, 'profit', target_profit, target)
        return [dict(amount=-delta, start=source, target=self.HOUSE_CHIP_POS, duration=280)]

    def _outcome_transfers(self, seat, kind, stake, returned):
        """Lose: collect stake and held profit; push: take back only held profit.

        A final win keeps the already-paid tier in place, so confirming a
        cashout or reaching card eight does not issue the same profit again.
        """
        if not stake:
            return []
        transfers = self._profit_transfers(seat, kind, max(0.0, _money(returned - stake)))
        if returned <= 0:
            chip = self.visual_chips.pop((seat, kind, 'stake'), None)
            if chip:
                transfers.append(dict(amount=chip['amount'], start=chip['xy'],
                                      target=self.HOUSE_CHIP_POS, duration=280))
        return transfers


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


    def _inspect_completed_round(self, event=None):
        if self.game.stage!='await_restart':return
        self._cancel_restart_timer()
        self.show_card_sequence()


    def _complete_chip_return(self):
        if self.game.stage not in ('returning','credit_pending'):return
        self.game.stage='sweeping'
        self._refresh()
        self.canvas.delete('returned_chips')
        self._sweep_all_cards()


    def _close_card_sequence(self):
        current=getattr(self,'_sequence_window',None)
        if current is not None:
            try:
                if current.winfo_exists():current.destroy()
            except tk.TclError:pass
        self._sequence_window=None


    def _return_all_chips(self):
        if self._pending_balance_action is not None:
            self._retry_balance_save()
            return
        if self.game.stage == 'credit_pending':
            self._complete_chip_return()
            return
        if (self.game.stage != 'await_restart' or self._decision_busy
                or self._motion_count or self._phase_busy):
            return
        self._cancel_restart_timer()
        if self._remaining_return():
            self._decision_busy = True
            self._claim_seats(self.game.active_hands, self._after_results)
            return
        self._history_available = False
        self._close_card_sequence()
        self.game.stage = 'returning'
        self._refresh()
        self._complete_chip_return()


    def _sweep_all_cards(self):
        if not self.card_items:
            self._finish_round()
            return
        self._motion_count += 1
        previous = [0.0]
        def frame(index=0):
            fraction = index / 13
            offset = (self.WIDTH + self.CARD_WIDTH) * fraction * fraction * (3 - 2 * fraction)
            self.canvas.move('cards', offset - previous[0], 0)
            previous[0] = offset
            if index < 13:
                self._schedule(round(200 * (index + 1) / 13) - round(200 * index / 13), frame, index + 1)
            else:
                self.canvas.delete('cards')
                self.card_items.clear()
                self._flip_photos.clear()
                self._revealed_cards.clear()
                self._motion_count -= 1
                self._finish_round()
        frame()


    def _deal_next(self, sequence, offset, complete):
        if offset == len(sequence):
            complete()
            return
        side, index = sequence[offset]
        x, y = self.card_position(side, index)
        item = self.canvas.create_image(575, 52, image=self._face_photos['back'], anchor='nw', tags='cards')
        self.card_items[(side, index)] = item
        def move(step=0):
            fraction = step / 6
            self.canvas.coords(item, 575 + (x - 575) * fraction, 52 + (y - 52) * fraction)
            if step < 6:
                self._schedule(round(self.DEAL_MOVE_MS * (step + 1) / 6) - round(self.DEAL_MOVE_MS * step / 6), move, step + 1)
            else:
                self._schedule(round(self.DEAL_CARD_MS) - round(self.DEAL_MOVE_MS), self._deal_next,
                               sequence, offset + 1, complete)
        move()


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
        instruction_title = 'Hi-Lo Mojo · 玩法说明'
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
        tk.Label(header, text='玩法 · 1–3手下注 · 兑现 · 匹对红利 · 牌张',
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



def main(initial_balance=10000, username='Guest', *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """Supreme13-compatible entry point; supports standalone and embedded modes."""
    actual_balance = _amount(initial_balance if balance is None else balance)
    actual_user = username if user is None else user
    if parent is not None:
        return HiLoMojoGUI(parent, actual_balance, actual_user,
                           on_back=on_back, on_balance_change=on_balance_change)
    root = tk.Tk()
    root.title('Hi-Lo Mojo')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)
    try:
        page = HiLoMojoGUI(root, actual_balance, actual_user,
                           on_balance_change=on_balance_change)
    except Exception as exc:
        messagebox.showerror('Hi-Lo Mojo 无法启动', str(exc), parent=root)
        root.destroy()
        raise
    page.pack(fill=tk.BOTH, expand=True)
    page.on_back = lambda final_balance: root.destroy()
    root.protocol('WM_DELETE_WINDOW', page.on_close)
    root.mainloop()
    return page.balance


if __name__ == '__main__':
    final_balance = main()
    print(f'Final balance: {final_balance}')
