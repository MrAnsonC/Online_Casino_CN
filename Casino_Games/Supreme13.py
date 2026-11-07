import sys
from importlib import import_module
from pathlib import Path

# 与 UTH 一样，先定位项目并启用账户组件，再载入 JSON 及界面模块。
_SCRIPT_DIR = Path(__file__).resolve().parent
_ACCOUNT_ROOT = next((p for p in (_SCRIPT_DIR, *_SCRIPT_DIR.parents)
                      if (p / 'A_Tools' / 'Account' / 'secure_json.py').is_file()), None)
_PROJECT_ROOT = _ACCOUNT_ROOT or _SCRIPT_DIR
if _ACCOUNT_ROOT is not None:
    if str(_ACCOUNT_ROOT) not in sys.path:
        sys.path.insert(0, str(_ACCOUNT_ROOT))
    # 账户组件按已找到的项目路径加载；缺少原项目时仍可使用 Guest。
    _account_module = import_module('A_Tools.Account')
    _account_module.install_secure_json()
    del _account_module

import base64
import io
import json
import math
import os
import random
import secrets
import subprocess
import time

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont

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
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: int(r) if r.isdigit() else 11 if r == 'A' else 10 for r in RANKS}
BLIND13_PAYOUT = {'spade_ace_two': 25, 'suited_ace_two': 10,
                  'unsuited_ace_two': 4, 'natural13': 1}


def project_root() -> str:
    return str(_PROJECT_ROOT)


def user_data_path() -> str:
    if _ACCOUNT_ROOT is None:
        raise RuntimeError('找不到原项目的加密账户组件；请使用 Guest 试玩或放回原项目目录。')
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


def supreme13_log_path():
    directory = Path(project_root()) / 'A_Logs' / 'Json'
    directory.mkdir(parents=True, exist_ok=True)
    return str(directory / 'Supreme13.json')


def save_supreme13_history(game, result):
    """每局写入一次；保留原始牌序、切牌位置、分牌前后手牌和最近50局。"""
    path = supreme13_log_path()
    counters = dict(player_win=0, dealer_win=0, push=0, fold=0, bust=0, game=0)
    data = dict(history_record=dict(counters), history=[])
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        if not isinstance(data, dict) or not isinstance(data.get('history'), list):
            raise ValueError('Supreme13 历史资料格式错误。')
        for key, value in counters.items():
            data.setdefault('history_record', {}).setdefault(key, value)
    stats = data['history_record']
    stats['game'] += 1
    for hand_id, outcome in result['hands'].items():
        key = {'player': 'player_win', 'dealer': 'dealer_win',
               'fold': 'fold', 'push': 'push'}[outcome['winner']]
        stats[key] += 1
        if game.decisions[hand_id] == 'bust':
            stats['bust'] += 1
    record = dict(
        game_id=max((row.get('game_id', 0) for row in data['history']), default=0) + 1,
        timestamp=time.strftime('%Y-%m-%d %H:%M:%S'),
        rules=dict(dealer_always_qualifies=True, ace_value=11,
                   qualifying_range=[8, 18], blind13_payout=dict(BLIND13_PAYOUT)),
        deck_order=[str(card) for card in game.deck.full_deck],
        cut_position=game.deck.cut_position,
        deal_events=list(game.deal_events),
        original_hands={seat: [str(card) for card in hand]
                        for seat, hand in game.original_hands.items()},
        player_hands={seat: [str(card) for card in game.hands[seat]]
                      for seat in game.active_hands},
        dealer_cards=[str(card) for card in game.dealer_hand],
        decisions=dict(game.decisions),
        bets={seat: dict(game.bets[seat]) for seat in game.active_hands},
        result=result,
    )
    data['history'].append(record)
    data['history'] = data['history'][-50:]
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=4)


class Card:
    def __init__(self, suit, rank):
        if suit not in SUITS or rank not in RANK_VALUES:
            raise ValueError('无效的扑克牌。')
        self.suit, self.rank, self.value = suit, rank, RANK_VALUES[rank]

    def __repr__(self):
        return f'{self.rank}{self.suit}'


class Deck:
    def __init__(self):
        shuffle_script = Path(project_root()) / 'A_Tools' / 'Card' / 'shuffle.py'
        self.full_deck = []
        self.cut_position = 0
        if shuffle_script.is_file():
            try:
                env = os.environ.copy()
                env['PYTHONIOENCODING'] = 'utf-8'
                result = subprocess.run([sys.executable, str(shuffle_script), 'false', '1'],
                    capture_output=True, text=True, encoding='utf-8', env=env,
                    check=True, timeout=30)
                data = json.loads(result.stdout)
                cards = [Card(row['suit'], row['rank']) for row in data['deck']]
                cut = data['cut_position']
                if len(cards) != 52 or len({(c.suit, c.rank) for c in cards}) != 52:
                    raise ValueError('洗牌资料须包含52张不同的牌。')
                if isinstance(cut, bool) or not isinstance(cut, int) or not 0 <= cut < 52:
                    raise ValueError('切牌位置错误。')
                self.full_deck, self.cut_position = cards, cut
            except (OSError, subprocess.SubprocessError, json.JSONDecodeError,
                    ValueError, KeyError, TypeError) as exc:
                print(f'无法使用 shuffle.py，将使用本机安全洗牌：{exc}')
        if not self.full_deck:
            self.full_deck = [Card(suit, rank) for suit in SUITS for rank in RANKS]
            self._secure_shuffle()
            self.cut_position = secrets.randbelow(52)
        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + i) % 52 for i in range(52)]
        self.card_sequence = [self.full_deck[i] for i in self.indexes]
        self.pointer = 0

    def _secure_shuffle(self):
        for i in range(len(self.full_deck) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            self.full_deck[i], self.full_deck[j] = self.full_deck[j], self.full_deck[i]

    def deal(self, n=1):
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError('发牌数量必须为正整数。')
        if self.pointer + n > len(self.card_sequence):
            raise ValueError('牌堆剩余牌数不足。')
        cards = self.card_sequence[self.pointer:self.pointer + n]
        self.pointer += n
        return cards


def evaluate_hand(cards):
    if len(cards) != 2:
        raise ValueError('Supreme13 每手须有两张牌。')
    total = sum(card.value for card in cards)
    return total, abs(total - 13), not 8 <= total <= 18


def compare_hands(player, dealer):
    """1=玩家赢，0=平局，-1=玩家输；玩家爆牌优先判输。"""
    total, distance, busted = evaluate_hand(player)
    _, dealer_distance, dealer_busted = evaluate_hand(dealer)
    if busted:
        return -1
    if total == 13 or dealer_busted:
        return 1
    return (dealer_distance > distance) - (dealer_distance < distance)


def blind13_odds(cards):
    if evaluate_hand(cards)[0] != 13:
        return None
    if {card.rank for card in cards} == {'A', '2'}:
        if all(card.suit == '♠' for card in cards):
            return BLIND13_PAYOUT['spade_ace_two']
        if cards[0].suit == cards[1].suit:
            return BLIND13_PAYOUT['suited_ace_two']
        return BLIND13_PAYOUT['unsuited_ace_two']
    return BLIND13_PAYOUT['natural13']


def _amount(value):
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError('金额必须是有效数字。') from None
    if not math.isfinite(number) or number < 0:
        raise ValueError('金额必须是有限的非负数。')
    rounded = round(number, 2)
    if abs(number - rounded) > 0.000001:
        raise ValueError('金额最多保留两位小数。')
    return rounded


class Supreme13Game:
    SEATS = ('Player1', 'Player2')
    SPLIT_SEATS = {'Player1': 'Player1Split', 'Player2': 'Player2Split'}
    HAND_IDS = ('Player1', 'Player1Split', 'Player2', 'Player2Split')

    def __init__(self):
        self.reset_game()

    @staticmethod
    def empty_bet():
        return {'ante': 0.0, 'blind13': 0.0, 'raise': 0.0}

    @property
    def active_hands(self):
        return [seat for seat in self.HAND_IDS if self.decisions[seat] != 'inactive']

    def reset_game(self):
        self.deck = None
        self.hands = {seat: [] for seat in self.HAND_IDS}
        self.dealer_hand = []
        self.original_hands = {}
        self.split_seats = set()
        self.round_deal_sequence = []
        self.deal_events = []
        self.bets = {seat: self.empty_bet() for seat in self.HAND_IDS}
        self.decisions = {seat: 'inactive' for seat in self.HAND_IDS}
        self.stage = 'betting'
        self.settlement = None

    @staticmethod
    def dealer_qualifies_hand(hand):
        return True

    def dealer_qualifies(self):
        return True

    @classmethod
    def deal_sequence(cls, active_seats=None):
        seats = cls.SEATS if active_seats is None else tuple(s for s in cls.SEATS if s in active_seats)
        return [('Dealer', 0)] + [(seat, 0) for seat in seats] + [('Dealer', 1)]

    def _record_deal(self, sequence):
        for side, index in sequence:
            cards = self.dealer_hand if side == 'Dealer' else self.hands[side]
            self.deal_events.append(dict(hand=side, index=index, card=str(cards[index])))
        self.round_deal_sequence.extend(sequence)

    def start_round(self, bets, balance, high_bet_mode=False, *, deck=None):
        if self.stage != 'betting':
            raise ValueError('本局尚未结束。')
        balance = _amount(balance)
        minimum, maximum = (100, 50000) if high_bet_mode else (10, 10000)
        prepared = {seat: self.empty_bet() for seat in self.HAND_IDS}
        for seat in self.HAND_IDS:
            source = bets.get(seat, {})
            if set(source) - set(self.empty_bet()):
                raise ValueError('下注包含不支持的项目。')
            b = {kind: _amount(source.get(kind, 0)) for kind in self.empty_bet()}
            if seat not in self.SEATS:
                if any(b.values()):
                    raise ValueError('分牌注只能在分牌时建立。')
                continue
            if b['raise']:
                raise ValueError('请收到第一张牌后再决定加注。')
            if b['ante'] != b['blind13']:
                raise ValueError('前注与盲注13必须等额下注。')
            if b['ante'] and not minimum <= b['ante'] <= maximum:
                raise ValueError(f'每手前注／盲注13须各为 ${minimum:,} 至 ${maximum:,}。')
            prepared[seat] = b
        active = [seat for seat in self.SEATS if prepared[seat]['ante']]
        if not active:
            raise ValueError('请至少为一位玩家下前注与盲注13。')
        charged = round(sum(sum(b.values()) for b in prepared.values()), 2)
        reserve = sum(prepared[seat]['ante'] for seat in active)
        if round(charged + reserve, 2) > balance:
            raise ValueError('余额不足以支付初始下注及每手至少1倍的后续加注。')
        new_deck = deck if deck is not None else Deck()
        sequence = self.deal_sequence(active)
        drawn = new_deck.deal(len(sequence))
        hands = {seat: [] for seat in self.HAND_IDS}
        dealer = []
        for (side, _), card in zip(sequence, drawn):
            (dealer if side == 'Dealer' else hands[side]).append(card)
        self.deck, self.hands, self.dealer_hand = new_deck, hands, dealer
        self.bets = prepared
        self.decisions = {seat: 'first_pending' if seat in active else 'inactive' for seat in self.HAND_IDS}
        self.stage = 'dealing_first'
        self._record_deal(sequence)
        return charged

    def finish_first_deal(self):
        if self.stage != 'dealing_first':
            raise ValueError('当前不是首张发牌阶段。')
        self.stage = 'first_decision'

    def _minimum_raise_reserve(self, exclude=None):
        return sum(self.bets[seat]['ante'] for seat in self.active_hands if seat != exclude
                   and self.decisions[seat] in ('first_pending', 'checked', 'second_pending')
                   and not self.bets[seat]['raise'])

    def can_split(self, seat):
        return (seat in self.SEATS and seat not in self.split_seats
                and len(self.hands[seat]) == 2
                and self.hands[seat][0].rank == self.hands[seat][1].rank)

    def legal_actions(self, seat):
        if seat not in self.HAND_IDS:
            return ()
        state = self.decisions[seat]
        if self.stage == 'first_decision' and state == 'first_pending':
            return ('raise2', 'check')
        if self.stage != 'second_decision' or state != 'second_pending':
            return ()
        if self.bets[seat]['raise']:
            actions = ['stand']
        else:
            actions = ['fold'] if evaluate_hand(self.hands[seat])[2] else ['raise1', 'fold']
        if self.can_split(seat):
            actions.append('split')
        return tuple(actions)

    def action_cost(self, seat, action):
        if action not in self.legal_actions(seat):
            raise ValueError('当前手牌或阶段不允许这个决定。')
        ante = self.bets[seat]['ante']
        return round({'raise2': ante * 2, 'raise1': ante,
                      'split': ante + self.bets[seat]['raise']}.get(action, 0.0), 2)

    def can_afford_action(self, seat, action, balance):
        try:
            cost = self.action_cost(seat, action)
            reserve = self._minimum_raise_reserve(exclude=seat)
            if action == 'check':
                reserve += self.bets[seat]['ante']
            elif action == 'split' and not self.bets[seat]['raise']:
                reserve += self.bets[seat]['ante'] * 2
            return round(cost + reserve, 2) <= _amount(balance)
        except ValueError:
            return False

    def decide(self, seat, action, balance):
        cost = self.action_cost(seat, action)
        if not self.can_afford_action(seat, action, balance):
            raise ValueError('余额不足；还须为其他未决定的手牌保留至少1倍加注。')
        if action == 'split':
            self._split_hand(seat)
        elif self.stage == 'first_decision':
            self.decisions[seat] = 'raised2' if action == 'raise2' else 'checked'
            self.bets[seat]['raise'] = cost
        else:
            busted = evaluate_hand(self.hands[seat])[2]
            self.decisions[seat] = 'fold' if action == 'fold' else 'bust' if busted else 'play'
            if action == 'raise1':
                self.bets[seat]['raise'] = cost
        return cost

    def deal_second_cards(self):
        if self.stage != 'first_decision' or 'first_pending' in self.decisions.values():
            raise ValueError('请先完成所有首张牌的决定。')
        active = [seat for seat in self.SEATS if self.decisions[seat] != 'inactive']
        cards = self.deck.deal(len(active))
        sequence = []
        for seat, card in zip(active, cards):
            self.hands[seat].append(card)
            self.original_hands[seat] = list(self.hands[seat])
            sequence.append((seat, 1))
        self.stage = 'dealing_second'
        self._record_deal(sequence)
        return sequence

    def _second_state(self, seat):
        busted = evaluate_hand(self.hands[seat])[2]
        if self.can_split(seat):
            return 'second_pending'
        if busted:
            return 'bust'
        return 'play' if self.bets[seat]['raise'] else 'second_pending'

    def finish_second_deal(self):
        if self.stage != 'dealing_second':
            raise ValueError('当前不是第二张发牌阶段。')
        self.stage = 'second_decision'
        for seat in self.active_hands:
            self.decisions[seat] = self._second_state(seat)

    def _split_hand(self, seat):
        """每位玩家最多分一次；原 Blind13 跟随第一手，不另下 Blind13。"""
        extra_cards = self.deck.deal(2)
        child = self.SPLIT_SEATS[seat]
        first, second = self.hands[seat]
        self.hands[seat] = [first, extra_cards[0]]
        self.hands[child] = [second, extra_cards[1]]
        self.bets[child] = dict(ante=self.bets[seat]['ante'], blind13=0.0,
                                **{'raise': self.bets[seat]['raise']})
        self.split_seats.add(seat)
        self.decisions[child] = 'second_pending'
        for hand_id in (seat, child):
            self.decisions[hand_id] = self._second_state(hand_id)
        self.deal_events.append(dict(action='split', source=seat, target=child, card=str(second)))
        self._record_deal([(seat, 1), (child, 1)])

    def begin_showdown(self):
        if self.stage != 'second_decision' or 'second_pending' in self.decisions.values():
            raise ValueError('请先完成所有手牌的决定。')
        self.stage = 'showdown'

    def settle(self):
        if self.settlement is not None:
            return self.settlement
        if self.stage != 'showdown':
            raise ValueError('完成所有决定并开庄家暗牌后才能结算。')
        outcomes = {}
        for seat in self.active_hands:
            hand, bets, decision = self.hands[seat], self.bets[seat], self.decisions[seat]
            details = self.empty_bet()
            if decision == 'fold':
                winner, message = 'fold', '弃牌：本手下注全输'
            elif decision == 'bust':
                winner, message = 'dealer', '玩家爆牌：本手下注全输'
            else:
                comparison = compare_hands(hand, self.dealer_hand)
                if comparison > 0:
                    details['ante'] = bets['ante'] * 2
                    details['raise'] = bets['raise'] * 2
                    odds = None if seat in self.split_seats else blind13_odds(hand)
                    details['blind13'] = bets['blind13'] * (1 if odds is None else odds + 1)
                    winner, message = 'player', '玩家13点获胜' if sum(c.value for c in hand) == 13 else '玩家获胜'
                elif comparison == 0:
                    details = dict(bets)
                    winner, message = 'push', '同距平局：本手下注退回'
                else:
                    winner, message = 'dealer', '庄家获胜'
            details = {kind: round(value, 2) for kind, value in details.items()}
            returned, stake = round(sum(details.values()), 2), round(sum(bets.values()), 2)
            outcomes[seat] = dict(winner=winner, message=message, details=details,
                                  returned=returned, stake=stake, net=round(returned - stake, 2),
                                  total=evaluate_hand(hand)[0])
        returned = round(sum(row['returned'] for row in outcomes.values()), 2)
        stake = round(sum(row['stake'] for row in outcomes.values()), 2)
        self.settlement = dict(hands=outcomes, returned=returned, stake=stake,
                               net=round(returned - stake, 2), dealer_always_qualifies=True)
        self.stage = 'settled'
        return self.settlement


class Supreme13GUI(tk.Frame):
    WIDTH, HEIGHT = 1150, 750
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    DEAL_CARD_MS = 224 / .85
    DEAL_MOVE_MS = (128 / .75) / .85
    BET_CHIP_RADIUS = 16 * 4 / 3
    HOUSE_CHIP_POS = (575, 40)
    TABLE_GREEN = '#4b1e22'
    SPOT_RADIUS = 38
    SEAT_BOUNDS = {'Player1': (22, 566), 'Player2': (582, 1128)}
    ZONE_COLORS = {'Player1': '#2A5541', 'Player2': '#204536'}

    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = username, _amount(initial_balance)
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game = Supreme13Game()
        self.bets = {seat: self.game.empty_bet() for seat in self.game.HAND_IDS}
        self.last_bet = None
        self.last_win = 0.0
        self.high_bet_mode = False
        self.selected_chip = 10.0
        self._jobs = set()
        self._closing = False
        self._credited = False
        self._return_persisted = False
        self._crediting = False
        self._saving_balance = False
        self._pending_balance_action = None
        self._restart_job = None
        self._restart_deadline = None
        self._motion_count = 0
        self._chip_serial = 0
        self._decision_busy = False
        self._settlement_started = False
        self._showdown_started = False
        self._phase_busy = False
        self._revealed_cards = set()
        self.visual_chips = {}
        self.last_round_snapshot = None
        self._history_available = False
        self._face_photos, self._pil_cards, self._flip_photos = {}, {}, {}
        self.card_items, self.bet_spots, self.action_buttons = {}, {}, {}
        self._load_assets()
        self._create_widgets()
        self._refresh()
        self.bind('<Destroy>', self._on_destroy, add='+')

    @property
    def game_in_progress(self):
        return self.game.stage != 'betting' or self._motion_count > 0

    @classmethod
    def _base_seat(cls, hand_id):
        return hand_id[:-5] if hand_id.endswith('Split') else hand_id

    def card_position(self, side, index):
        if side == 'Dealer':
            return 489 + index * 92, 42
        x0, x1 = self.SEAT_BOUNDS[self._base_seat(side)]
        left = x1 - 12 - (2 * self.CARD_WIDTH + 12) if side.endswith('Split') else x0 + 12
        return left + index * (self.CARD_WIDTH + 12), 345

    def _create_widgets(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=ROOT_BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.control_buttons = {}
        c = self.canvas
        self._text(208, 23, 'SUPREME13', 19, GOLD)
        c.create_rectangle(445, 10, 705, 164, fill=self.TABLE_GREEN, outline='')
        self.title_items = {'Dealer': self._text(575, 25, '庄家', 14, PANEL_BG)}
        self.seat_title_items = {}
        self._draw_limit_table()
        self._draw_payout_table()
        with Image.open(io.BytesIO(base64.b64decode(SCORE_GUIDE_PNG))) as guide:
            self._score_guide_photo = ImageTk.PhotoImage(guide.convert('RGB'), master=self)
        c.create_image(23, 172, image=self._score_guide_photo, anchor='nw', tags='score_guide')
        c.create_rectangle(22, 283, 1128, 309, fill='#173C2E', outline='#65784B', width=1)
        self._text(575, 296, 'A = 11   J / Q / K = 10   有效点数 8–18   玩家13点必胜   其他同距退注', 12, GOLD)
        for seat, (x0, x1) in self.SEAT_BOUNDS.items():
            self._draw_player_panel(seat, x0, x1)
        for side in ('Dealer', *self.game.HAND_IDS):
            for index in range(2):
                x, y = self.card_position(side, index)
                c.create_rectangle(x - 2, y - 2, x + self.CARD_WIDTH + 1, y + self.CARD_HEIGHT + 1,
                                   outline='#7B9374', dash=(3, 3), tags=('card_slots', 'slots_' + side))
        self._draw_bottom_controls()

    def _draw_player_panel(self, seat, x0, x1):
        c = self.canvas
        middle = (x0 + x1) // 2
        child = self.game.SPLIT_SEATS[seat]
        c.create_rectangle(x0, 316, x1, 617, fill=self.ZONE_COLORS[seat], outline='')
        self.seat_title_items[seat] = self._text(middle, 330, '玩家', 14, PANEL_BG)
        for hand in (seat, child):
            left, _ = self.card_position(hand, 0)
            self.title_items[hand] = self._text(left + self.CARD_WIDTH + 6, 330, '', 10, PANEL_BG)
        for direction in (-1, 1):
            for top, corner, end in ((501, 72, 106), (511, 68, 92)):
                c.create_line(middle + direction * 38, top, middle + direction * corner, top,
                              middle + direction * end, 534, fill=PANEL_BG,
                              width=4, capstyle='round', joinstyle='round')
        for hand, kind, cx, cy, label in (
                (seat, 'raise', x0 + 98, 501, '加注'),
                (seat, 'blind13', middle, 501, '盲注\n13'),
                (child, 'raise', x1 - 98, 501, '分牌\n加注'),
                (seat, 'ante', middle - 112, 574, '前注'),
                (child, 'ante', middle + 112, 574, '分牌\n前注')):
            self._draw_spot(hand, kind, cx, cy, label)
        for action, cx, top, caption, color in (
                ('primary', middle, 346, '下注2×', '#397A48'),
                ('secondary', middle, 402, '过牌', DARK_BLUE),
                ('split', middle, 551, '分牌', '#9B403A')):
            tag = self.create_control_button(cx - 52, top, cx + 52, top + 46, caption,
                lambda s=seat, a=action: self._action_button(s, a), color,
                font_size=12, draw_shadow=False)
            self.action_buttons[(seat, action)] = tag

    def _draw_limit_table(self):
        c = self.canvas
        x0, x1, y0 = 30, 386, 58
        c.create_rectangle(x0, y0, x1, 164, fill=ROOT_BG, outline=GOLD, width=2, tags='limits')
        c.create_rectangle(x0, y0, x1, y0 + 29, fill=ROOT_BG, outline=GOLD, tags='limits')
        self._text((x0 + x1) / 2, y0 + 14, '下注上限', 13, PANEL_BG, tags='limits')
        self.limit_value_items = []
        for column, title in enumerate(('前注最低', '前注最高', '加注最高')):
            left = x0 + column * (x1 - x0) / 3
            right = x0 + (column + 1) * (x1 - x0) / 3
            c.create_rectangle(left, y0 + 29, right, y0 + 66, outline='#77906B', tags='limits')
            c.create_rectangle(left, y0 + 66, right, 164, outline='#77906B', tags='limits')
            self._text((left + right) / 2, y0 + 47, title, 11, PANEL_BG, tags='limits')
            self.limit_value_items.append(
                self._text((left + right) / 2, y0 + 86, '', 12, GOLD, tags='limits'))
        c.tag_bind('limits', '<Button-1>', self.toggle_high_bet_limits)
        c.tag_bind('limits', '<Enter>', lambda _e: c.configure(cursor='hand2'))
        c.tag_bind('limits', '<Leave>', lambda _e: c.configure(cursor=''))

    def _draw_payout_table(self):
        c = self.canvas
        c.create_rectangle(770, 10, 1120, 164, fill='#123C30', outline=GOLD, width=2)
        self._text(945, 28, '盲注 13 净赢赔率', 13, GOLD)
        rows = [('黑桃 A + 黑桃 2', '25 : 1'), ('同花 A + 2（非黑桃）', '10 : 1'),
                ('不同花 A + 2', '4 : 1'), ('其他原手两张合计13', '1 : 1')]
        for index, (name, payout) in enumerate(rows):
            y = 53 + index * 22
            self._text(786, y, name, 10, PANEL_BG, anchor='w')
            self._text(1104, y, payout, 11, GOLD, anchor='e')
        self._text(945, 145, '其他胜出或平局退还盲注，前注和加注胜出赔 1:1', 9, PANEL_BG)

    def _draw_spot(self, seat, kind, cx, cy, label):
        tag = f'spot_{seat}_{kind}'
        r = self.SPOT_RADIUS
        border = self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
            fill=self.ZONE_COLORS[self._base_seat(seat)], outline=PANEL_BG, width=2, tags=tag)
        label_item = self._text(cx, cy, label, 14, PANEL_BG, justify='center', tags=tag)
        self.bet_spots[(seat, kind)] = dict(tag=tag, center=(cx, cy), border=border,
                                           label_item=label_item, label=label)
        if seat in self.game.SEATS and kind in ('ante', 'blind13'):
            self.canvas.tag_bind(tag, '<Button-1>', lambda _e: self.add_chip_to_bet(seat, kind))
            self.canvas.tag_bind(tag, '<Button-3>', lambda _e: self.reset_single_bet(seat, kind))
            self.canvas.tag_bind(tag, '<Enter>', lambda _e: self.canvas.configure(
                cursor='' if self.game_in_progress else 'hand2'))
            self.canvas.tag_bind(tag, '<Leave>', lambda _e: self.canvas.configure(cursor=''))

    def _draw_bottom_controls(self):
        c = self.canvas
        c.create_rectangle(0, 625, 1150, 748, fill=ROOT_BG, outline='#6C7850', width=2, tags='controls')
        self.balance_item = self._text(10, 665, '', 18, TEXT, anchor='w', tags='controls')
        self.total_item = self._text(10, 710, '', 18, TEXT, anchor='w', tags='controls')
        self.clear_button = self.create_control_button(278, 650, 344, 704, '清除', self.reset_bets,
            '#9B403A', font_size=11, draw_shadow=False)
        self._draw_chips()
        self.info_button = self.create_control_button(810, 650, 855, 695, '?', self.show_game_instructions,
            DARK_BLUE, font_size=17, draw_shadow=False)
        self.repeat_button = self.create_control_button(862, 638, 1000, 708, '重复下注', self.apply_last_bet,
            '#536A43', font_size=11, draw_shadow=False)
        self.start_button = self.create_control_button(1012, 628, 1138, 720, '开牌', self.start_game,
            HEADER_BG, fg=TITLE_FG, font_size=14, draw_shadow=False)
        self.restart_button = self.create_control_button(862, 638, 1138, 708, '再来一局(30)', self._return_all_chips,
            HEADER_BG, fg=TITLE_FG, font_size=17, draw_shadow=False)
        c.tag_bind(self.restart_button, '<Button-3>', self._inspect_completed_round)
        c.itemconfigure(self.restart_button, state='hidden')
        self._enter_binding = self.winfo_toplevel().bind('<Return>', lambda _e:
            self._return_all_chips() if self._pending_balance_action is not None
            or self.game.stage in ('await_restart', 'credit_pending') else self.start_game(), add='+')

    def _decision_hand(self, seat):
        child = self.game.SPLIT_SEATS.get(seat)
        if child and not self.game.legal_actions(seat) and self.game.legal_actions(child):
            return child
        return seat

    def _button_action(self, hand, button):
        if button == 'split':
            return 'split'
        if self.game.stage in ('betting', 'dealing_first', 'first_decision'):
            return 'raise2' if button == 'primary' else 'check'
        if button == 'secondary':
            return 'fold'
        return 'stand' if 'stand' in self.game.legal_actions(hand) else 'raise1'

    def _action_button(self, seat, button):
        hand = seat if button == 'split' else self._decision_hand(seat)
        self._decide(hand, self._button_action(hand, button))

    def _refresh(self):
        c = self.canvas
        c.itemconfigure(self.balance_item, text=f'余额: ${self.balance:,.2f}')
        total = round(sum(sum(b.values()) for b in self.bets.values()), 2)
        c.itemconfigure(self.total_item, text=f'本局下注: ${total:,.2f}' if total else f'上局返还: ${self.last_win:,.2f}')
        minimum, maximum = (100, 50000) if self.high_bet_mode else (10, 10000)
        for item, value in zip(self.limit_value_items, (minimum, maximum, maximum * 2)):
            c.itemconfigure(item, text=f'${value:,}')
        self._render_chips()
        pending_save = self._pending_balance_action is not None
        betting = self.game.stage == 'betting' and self._motion_count == 0 and not pending_save
        self.set_control_button_state(self.clear_button, betting)
        self.set_control_button_state(self.repeat_button, betting and bool(self.last_bet))
        self.set_control_button_state(self.start_button, betting)
        restarting = pending_save or self.game.stage in ('await_restart', 'returning', 'credit_pending', 'sweeping')
        c.itemconfigure(self.repeat_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button, state='normal' if restarting else 'hidden')
        self.set_control_button_state(self.restart_button, not self._saving_balance and (
            pending_save or self.game.stage in ('await_restart', 'credit_pending')))
        if pending_save:
            self._restart_caption('重试保存余额')
        ready = not (pending_save or self._decision_busy or self._phase_busy or self._motion_count)
        captions = {'raise2': '下注2×', 'check': '过牌', 'raise1': '下注1×',
                    'fold': '弃牌', 'stand': '继续', 'split': '分牌'}
        for seat, child in self.game.SPLIT_SEATS.items():
            current = self._decision_hand(seat)
            for button in ('primary', 'secondary', 'split'):
                hand = seat if button == 'split' else current
                action = self._button_action(hand, button)
                tag = self.action_buttons[(seat, button)]
                enabled = ready and self.game.can_afford_action(hand, action, self.balance)
                if button == 'secondary':
                    self.control_buttons[tag]['fill'] = DARK_BLUE if action == 'check' else '#9B403A'
                self.set_control_button_state(tag, enabled)
                c.itemconfigure(self.control_buttons[tag]['text'], text=captions[action])
            for hand in (seat, child):
                selected = ready and current == hand and bool(self.game.legal_actions(hand))
                c.itemconfigure('slots_' + hand, outline='#FFE29A' if selected else '#7B9374')
                c.itemconfigure(self.title_items[hand], fill='#FFE29A' if selected else PANEL_BG)
            self._update_hand_title(seat)
        self._update_hand_title('Dealer')

    def add_chip_to_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count or seat not in self.game.SEATS or kind == 'raise':
            return
        new = {side: dict(bet) for side, bet in self.bets.items()}
        maximum = 50000 if self.high_bet_mode else 10000
        value = min(maximum, new[seat]['ante'] + self.selected_chip)
        new[seat]['ante'] = new[seat]['blind13'] = value
        required = sum(3 * new[side]['ante'] for side in self.game.SEATS)
        if required > self.balance:
            messagebox.showwarning('余额不足', '须同时支付等额的前注、盲注13，并保留1倍加注。', parent=self)
            return
        self._apply_bet_layout(new)

    def reset_single_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count or seat not in self.game.SEATS or kind == 'raise':
            return
        new = {side: dict(bet) for side, bet in self.bets.items()}
        new[seat] = self.game.empty_bet()
        self._apply_bet_layout(new)

    def _apply_bet_layout(self, new_bets):
        if sum(3 * new_bets.get(seat, {}).get('ante', 0) for seat in self.game.SEATS) > self.balance:
            messagebox.showwarning('余额不足', '余额不足以重复这组下注及后续1倍加注。', parent=self)
            return
        previous = self.bets
        self.bets = {seat: dict(new_bets.get(seat, self.game.empty_bet())) for seat in self.game.HAND_IDS}
        transfers = []
        for seat in self.game.HAND_IDS:
            for kind in self.game.empty_bet():
                old, new = previous[seat][kind], self.bets[seat][kind]
                delta = round(new - old, 2)
                if not delta:
                    continue
                center = self.bet_spots[(seat, kind)]['center']
                if delta > 0:
                    transfers.append(dict(amount=delta, start=self._rack_position(), target=center,
                        arrive=lambda s=seat, k=kind, a=new: self._set_visual(s, k, 'stake', a)))
                else:
                    self._set_visual(seat, kind, 'stake', new)
                    transfers.append(dict(amount=-delta, start=center, target=self._rack_position(), duration=440))
        self._run_chip_batch(transfers, self._refresh)
        self._refresh()

    def start_game(self):
        if self.game.stage != 'betting' or self._motion_count or self._pending_balance_action is not None:
            return
        try:
            charged = self.game.start_round(self.bets, self.balance, self.high_bet_mode)
        except (ValueError, OSError) as exc:
            messagebox.showwarning('无法开始', str(exc), parent=self)
            return
        self._history_available = False
        self._close_card_sequence()
        self.balance = round(self.balance - charged, 2)
        self.bets = {seat: dict(bet) for seat, bet in self.game.bets.items()}
        self.last_bet = {seat: self.game.empty_bet() for seat in self.game.HAND_IDS}
        for seat in self.game.SEATS:
            self.last_bet[seat].update(ante=self.bets[seat]['ante'], blind13=self.bets[seat]['blind13'])
        self._credited = self._return_persisted = self._settlement_started = False
        self._decision_busy = self._showdown_started = False
        self._phase_busy = True
        self._cancel_restart_timer()
        self._revealed_cards.clear()
        self.canvas.delete('cards')
        self.card_items.clear()
        self._flip_photos.clear()
        self._load_assets()
        sequence = list(self.game.round_deal_sequence)
        visible = [(side, index) for side, index in sequence if (side, index) != ('Dealer', 1)]
        self._save_and_continue(lambda: self._deal_next(
            sequence, 0, lambda: self._reveal_next(visible, 0, self._first_ready)))

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

    def _reveal_next(self, sequence, offset, complete):
        if offset == len(sequence):
            complete()
            return
        side, index = sequence[offset]
        if (side, index) in self._revealed_cards:
            self._reveal_next(sequence, offset + 1, complete)
            return
        hand = self.game.dealer_hand if side == 'Dealer' else self.game.hands[side]
        card, item = hand[index], self.card_items[(side, index)]
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
                self._update_hand_title(side)
                self._reveal_next(sequence, offset + 1, complete)
        flip()

    def _first_ready(self):
        self.game.finish_first_deal()
        self._phase_busy = False
        self._refresh()

    def _second_ready(self):
        self.game.finish_second_deal()
        self._phase_busy = False
        self._refresh()
        self._maybe_advance()

    def _decide(self, seat, action):
        if (self._pending_balance_action is not None or self._decision_busy or self._phase_busy
                or self._motion_count or action not in self.game.legal_actions(seat)):
            return
        try:
            cost = self.game.decide(seat, action, self.balance)
        except ValueError as exc:
            messagebox.showwarning('无法操作', str(exc), parent=self)
            return
        self._decision_busy = True
        self.balance = round(self.balance - cost, 2)
        self.bets = {side: dict(bet) for side, bet in self.game.bets.items()}
        def continue_decision():
            if action == 'split':
                self._animate_split(seat)
                return
            def done():
                self._decision_busy = False
                self._refresh()
                self._maybe_advance()
            if cost:
                target = self.bet_spots[(seat, 'raise')]['center']
                self._animate_chip(cost, self._rack_position(), target,
                    lambda: (self._set_visual(seat, 'raise', 'stake', self.bets[seat]['raise']), done()))
            elif seat in self.game.split_seats and self.game.legal_actions(self.game.SPLIT_SEATS[seat]):
                # 共用按钮切到分牌手前留出短暂停顿，避免连点一次弃掉两手。
                self._refresh()
                self._schedule(350, done)
            else:
                done()
        self._save_and_continue(continue_decision)

    def _animate_split(self, seat):
        child = self.game.SPLIT_SEATS[seat]
        item = self.card_items.pop((seat, 1))
        self.card_items[(child, 0)] = item
        self._revealed_cards.discard((seat, 1))
        self._revealed_cards.add((child, 0))
        start, target = self.canvas.coords(item), self.card_position(child, 0)
        self._phase_busy = True
        self._refresh()
        transfers = []
        for kind in ('ante', 'raise'):
            amount = self.bets[child][kind]
            if amount:
                transfers.append(dict(amount=amount, start=self._rack_position(),
                    target=self.bet_spots[(child, kind)]['center'],
                    arrive=lambda k=kind, a=amount: self._set_visual(child, k, 'stake', a)))
        def ready_to_deal():
            sequence = [(seat, 1), (child, 1)]
            def revealed():
                self._decision_busy = self._phase_busy = False
                self._update_hand_title(seat)
                self._update_hand_title(child)
                self._refresh()
                self._maybe_advance()
            self._deal_next(sequence, 0, lambda: self._reveal_next(sequence, 0, revealed))
        def move(step=0):
            fraction = step / 12
            self.canvas.coords(item, start[0] + (target[0] - start[0]) * fraction,
                               start[1] + (target[1] - start[1]) * fraction)
            if step < 12:
                self._schedule(20, move, step + 1)
            else:
                self._run_chip_batch(transfers, ready_to_deal)
        move()

    def _maybe_advance(self):
        if self._decision_busy or self._phase_busy or self._motion_count:
            return
        if self.game.stage == 'first_decision' and 'first_pending' not in self.game.decisions.values():
            self._phase_busy = True
            sequence = self.game.deal_second_cards()
            self._refresh()
            self._deal_next(sequence, 0, lambda: self._reveal_next(sequence, 0, self._second_ready))
        elif self.game.stage == 'second_decision' and 'second_pending' not in self.game.decisions.values():
            if self._showdown_started:
                return
            self._showdown_started = self._phase_busy = True
            self.game.begin_showdown()
            self._refresh()
            self._reveal_next([('Dealer', 1)], 0, self._settle)

    @staticmethod
    def hand_type_text(hand, split=False):
        if not hand:
            return ''
        total = sum(card.value for card in hand)
        if len(hand) == 2 and not 8 <= total <= 18:
            return f'{total}爆牌'
        if total == 13:
            return '13点' if split else '天然13点'
        return f'{total}差{abs(total - 13)}'

    def _update_hand_title(self, side):
        if side == 'Dealer':
            visible = [card for index, card in enumerate(self.game.dealer_hand)
                       if ('Dealer', index) in self._revealed_cards]
            value = self.hand_type_text(visible)
            self.canvas.itemconfigure(self.title_items['Dealer'],
                                      text=f'庄家 - {value}' if value else '庄家')
            return
        seat = self._base_seat(side)
        split = seat in self.game.split_seats
        for hand in (seat, self.game.SPLIT_SEATS[seat]):
            visible = [card for index, card in enumerate(self.game.hands[hand])
                       if (hand, index) in self._revealed_cards]
            value = self.hand_type_text(visible, split=split)
            if hand == seat:
                label = f'玩家 - {value}' if value and not split else '玩家'
                self.canvas.itemconfigure(self.seat_title_items[seat], text=label)
            self.canvas.itemconfigure(self.title_items[hand], text=value if split else '')

    def _settle(self):
        if self._settlement_started:
            return
        self._settlement_started = True
        result = self.game.settle()
        self.game.stage = 'settling'
        self.last_win = result['returned']
        transfers = []
        for seat, outcome in result['hands'].items():
            self._update_hand_title(seat)
            for kind, stake in self.game.bets[seat].items():
                if stake:
                    transfers.extend(self._outcome_transfers(seat, kind, stake, outcome['details'][kind]))
        try:
            save_supreme13_history(self.game, result)
        except Exception as exc:
            messagebox.showerror('历史记录保存失败', str(exc), parent=self)
        self._refresh()
        self._run_chip_batch(transfers, self._await_next_round)

    def _await_next_round(self):
        if self.game.stage != 'settling':
            return
        self.game.stage = 'await_restart'
        self._phase_busy = False
        deck = self.game.deck
        self.last_round_snapshot = dict(full_deck=tuple(deck.full_deck), start_pos=deck.start_pos,
            images={key: image.copy() for key, image in self.original_images.items()})
        self._history_available = True
        self._cancel_restart_timer()
        self._restart_deadline = time.monotonic() + 30
        self._refresh()
        self._restart_tick()

    def _return_all_chips(self):
        if self._pending_balance_action is not None:
            self._retry_balance_save()
            return
        if self.game.stage == 'credit_pending':
            self._complete_chip_return()
            return
        if self.game.stage != 'await_restart':
            return
        self._cancel_restart_timer()
        self._history_available = False
        self._close_card_sequence()
        self.game.stage = 'returning'
        chips = list(self.visual_chips.values())
        self.visual_chips.clear()
        transfers = []
        for index, chip in enumerate(chips):
            target = self._rack_position(index, len(chips))
            def arrived(chip=chip, target=target, index=index):
                self._draw_chip(f'returned_chip_{index}', chip['amount'], *target, extra_tags=('returned_chips',))
            transfers.append(dict(amount=chip['amount'], start=chip['xy'], target=target,
                                  duration=600, arrive=arrived))
        self._refresh()
        self._run_chip_batch(transfers, self._complete_chip_return)

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

    def _finish_round(self):
        if self.game.stage != 'sweeping':
            return
        self.game.reset_game()
        self._history_available = self._phase_busy = self._showdown_started = False
        self.bets = {seat: self.game.empty_bet() for seat in self.game.HAND_IDS}
        self.visual_chips.clear()
        self._refresh()

    def reset_game(self, auto_reset=False):
        if self.game.stage == 'betting':
            self.reset_bets()

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


    def _on_destroy(self, event):
        if event.widget is self:
            self._closing = True
            self._pending_balance_action = None
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


    def _text(self, x, y, text, size=12, color=TEXT, **kw):
        return self.canvas.create_text(x, y, text=text, fill=color, font=('Arial', size, 'bold'), **kw)


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


    def _outcome_transfers(self, seat, kind, stake, returned):
        """本金留位，盈利派至左上；输注立即飞向统一庄家收筹码点，平局不动。"""
        if not stake:return []
        key=(seat,kind,'stake');center=self.bet_spots[(seat,kind)]['center']
        if returned<=0:
            chip=self.visual_chips.pop(key,None)
            return [dict(amount=chip['amount'],start=chip['xy'],target=self.HOUSE_CHIP_POS,duration=280)] if chip else []
        profit=round(returned-stake,2)
        if profit<=0:return []
        target=(center[0]-46,center[1]-9)
        return [dict(amount=profit,start=self.HOUSE_CHIP_POS,target=target,duration=440,
            arrive=lambda:self._set_visual(seat,kind,'profit',profit,target))]


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
            self._restart_caption('重试保存余额')
            self._refresh()
            return
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


    def show_card_sequence(self, event=None):
        if self.game.stage!='await_restart' or not self._history_available:return
        snapshot=self.last_round_snapshot
        if not snapshot:
            messagebox.showinfo('提示','尚无已结算牌局的牌序。',parent=self);return
        current=getattr(self,'_sequence_window',None)
        if current is not None and current.winfo_exists():current.lift();return
        # 原加勒比窗口：730×750，九张一排，切牌位置高亮，滚动显示52张原始牌序。
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
            original=snapshot['images'][(card.suit,card.rank)]
            small_images[i]=ImageTk.PhotoImage(original.resize((60,90),Image.Resampling.LANCZOS),master=win)
        win._card_images=small_images
        for row in range(6):
            row_frame=tk.Frame(card_frame,bg='#f0f0f0');row_frame.pack(fill=tk.X)
            for col in range(9 if row<5 else 7):
                idx=row*9+col
                if idx>=52:break
                container=tk.Frame(row_frame,bg='#f0f0f0');container.grid(row=0,column=col,padx=5)
                bg='light blue' if idx==cut_pos else '#f0f0f0'
                tk.Label(container,image=small_images[idx],bg=bg,borderwidth=1,relief='solid').pack()
                tk.Label(container,text=str(idx+1),bg=bg,font=('Arial',9)).pack()
        content_frame.update_idletasks();canvas.configure(scrollregion=canvas.bbox('all'))


    def on_close(self):
        if self._closing or self._crediting or self._saving_balance:return
        if self._pending_balance_action is not None:
            messagebox.showinfo('余额待保存', '请先点击“重试保存余额”，保存成功后继续本局。', parent=self)
            return
        settled=self.game.stage in ('settling','await_restart','returning','credit_pending','sweeping')
        if self.game_in_progress and not settled:
            messagebox.showinfo('牌局进行中','请先完成所有手牌的决定和结算。',parent=self)
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

    def _instruction_pages(self):
        return [
            ('玩法', [
                ('游戏目标', '一副52张牌，不含大小王。可选择下注1手或2手牌。'
                 '\n玩家和庄家各持两张牌，比较合计点数与13的距离；超过13仍可赢。'),
                ('点数与爆牌', 'A固定算11点；J、Q、K算10点；2–10按牌面。'
                 '\n8至18点有效；小于8或大于18爆牌。玩家爆牌即输，即使庄家也爆牌。'),
                ('胜负与平局', '玩家13点必胜，包括双方都是13。其他有效手牌比较与13的距离。'
                 '\n12与14同样差1点，属于平局；14点胜11点。普通平局三项下注均退本金。'
                 '\n庄家始终合格；庄家爆牌而玩家有效时，玩家获胜，前注与加注均赔1:1。'),
                ('初始下注', '点击任一玩家的前注或盲注13，两注会同步等额增加；右键清除两注。'
                 '\n开局前须为每手额外保留至少1倍前注，供第二阶段选择加注。'
                 '\n点击限额表可沿用原项目的高额模式；筹码、重复下注与牌序查看入口保留。'),
            ], []),
            ('两轮决策', [
                ('第一张牌', '先给庄家一张明牌，再依次给玩家1、玩家2各一张明牌，最后给庄家一张暗牌。'
                 '\n未下注的玩家跳过。全部派完并翻开明牌后，才可选择：加注2倍前注，或过牌。'
                 '\n此时不能弃牌或预先加注1倍。'),
                ('第二张牌', '所有玩家完成第一轮决定后，再给每位玩家第二张明牌。'
                 '\n之前过牌的有效手牌：加注1倍前注，或弃牌。弃牌损失本手全部已下注金额。'
                 '\n之前已加注2倍：不再加注或弃牌；有对子时仍可选择分牌或继续。'
                 '\n爆牌且无分牌机会时自动判输，不再收额外加注。'),
                ('摊牌与收款', '所有手牌完成决定后才翻庄家暗牌，并统一派彩。'
                 '\n“再来一局”或ENTER收回筹码并计入余额；30秒后自动继续。'
                 '\n右键“再来一局”暂停倒数并查看上一局52张原始牌序和切牌位置。'),
            ], []),
            ('赔率', [
                ('赔付口径', '下表赔率表示净赢倍数；结算显示的“返还”包含本金。'
                 '\n前注与加注获胜各赔1:1。盲注13在普通胜出或平局时退本金，输牌则收走。'),
                ('Natural13奖金', '只按未分牌的最初两张牌支付最高一项，不叠加。'
                 '\n分牌后的13点仍赢主注，但不付盲注13特别奖金。'),
            ], [('盲注13 净赢赔表', ('最初两张牌', '赔率'), [
                ('黑桃A + 黑桃2', '25 : 1'), ('同花A + 2（非黑桃）', '10 : 1'),
                ('不同花A + 2', '4 : 1'), ('其他合计13点', '1 : 1'),
                ('其他胜出 / 普通平局', '退还本金'), ('输牌 / 弃牌 / 爆牌', '全输'),
            ])]),
            ('分牌', [
                ('什么时候可分', '收到第二张牌后，两张牌的牌面相同才可分牌；J与Q不能当作对子。'
                 '\n即使原对子爆牌仍可选择分牌。每位玩家最多分一次，不允许再次分牌。'),
                ('追加多少', '新增一手须匹配原手的前注与已支付的加注，不另下盲注13。'
                 '\n例如原前注为10且已加注20，分牌再收前注10与加注20，共30。'
                 '\n原手若尚未加注，分牌先收新增前注；同时须有足够余额供两手各加注1倍。'),
                ('分后如何决定', '原对子拆开，每手各补一张牌。若已加注2倍，两手沿用该加注，直接比牌。'
                 '\n若第一阶段过牌，分后每手分别选择加注1倍或弃牌；爆牌的手自动判输。'
                 '\n中间的按钮操作金色虚线框标出的手牌，先处理左侧原手，再处理右侧分牌手。'),
                ('原盲注13归哪手', '原盲注13只跟随第一手：第一手赢或平局退本金；第一手输、弃牌或爆牌则输。'
                 '\n第二手没有盲注13。分后任一手13点均不触发Natural13奖金。'),
            ], []),
            ('结算示例', [
                ('例1：普通胜出', '前注10、盲注13为10、加注10；玩家14点，庄家11点。'
                 '\n返还前注20 + 盲注13本金10 + 加注20 = 50；下注30，净赢20。'),
                ('例2：玩家与庄家都是13', '前注10、盲注13为10、加注20；玩家6+7，庄家10+3。'
                 '\n玩家13必胜。返还前注20 + 盲注13为20 + 加注40 = 80；下注40，净赢40。'),
                ('例3：黑桃A加黑桃2', '前注10、盲注13为10、加注10。'
                 '\n盲注13返还10×(25+1)=260；前注返还20；加注返还20。'
                 '\n共返还300，下注30，净赢270。'),
                ('例4：庄家爆牌', '前注10、盲注13为10、加注10；玩家16点，庄家20点。'
                 '\n庄家始终合格，前注不会因庄家爆牌而只退本金。'
                 '\n返还20 + 10 + 20 = 50；净赢20。'),
                ('例5：普通平局与双爆牌', '玩家12、庄家14：同距平局，退还本手前注、盲注13和加注。'
                 '\n玩家20、庄家20：玩家已爆牌，本手全部下注输，不按平局处理。'),
            ], []),
        ]
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
        instruction_title = '至尊13 · 玩法说明'
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
        tk.Label(header, text='玩法 · 下注 · 赔率 · 分牌 · 结算示例',
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


# 中文 8–18 点数图（1104 × 104 PNG），嵌入以便单文件运行。
SCORE_GUIDE_PNG = (
    b'iVBORw0KGgoAAAANSUhEUgAABFAAAABoCAMAAADhP/TdAAADAFBMVEX/////+dz69efp6t/M2+Tj1rLIw7rywEGQ5vJP+/1N//9M8vuo'
    b'wN2trqqUsM9fuNs9/v8o//8n/f8n+/8I//8C//8A//8A/f1J9/9J7voo+f018vsk8vdI4vM62+g4w9Y1rsWgnZmgiG2Ak7F+fIFnlMpj'
    b'f7JhbpFnZmxOdrpMbbVLarNKabJJaLFIaLFLZ7FIZ7BIZ69HZ7BHZq9IZawvmbQvhaRGZq4qcJJGZK1GY6tCY6lFYqtEYqtEYatEYapF'
    b'YalBYadDYKlCYKlCX6lCX6hCX6dCXqdBX6lBXqhBXqdBXqY4X59zTHFPT2FBXaZESmpAXaZAXKZAXKVAXKRAUYg/XKY/W6U/W6Q/W6M+'
    b'WqM+WaM+WaI+Toc9WaM9WKI8V6E8VZ48Tps9TmM9TWM9TWI8TJo9TGI8TGI8TGE9PU87Vp8xV5E3UZ00To8wRX0wOWIlMWkuL0QiJU4f'
    b'J18fI0gfI0cfI0YfIkUeIUcdJFQdIEUdIEQdH0QiIjwZR2QXKEscH0QcH0McH0EYH0YcHkMcHkIbHkMbHkIcHkEbHkEbHj8XHkX/Av//'
    b'AP//AP7+AP7tAe1uEHMbHUIbHUEbHT0aHUEaHUAaHEAaHT8aHD8aGzkZHT8ZHD8ZHD4YHD4ZHD0ZGz4ZGz0YGz0YGzwYGj0ZGjwYGjwZ'
    b'GjsYGjsZGjgYGDQUG1YWGj8VHDoXGToWGToXGTkWGDkXGDgWGDgWFzgUFzoVGDYVFzYUFzUVFjYUFjUTFjUUFzMUFTYVFTQUFTQTFTQU'
    b'FTMTFTMUFTETFTITFTEVFS0UFDMTFDMTFDIUFC8TES4SGVQSGFQRGFQRGFMQGFMQF1MQFkMPFEMSFDIRFDISFDERFDERFDAPEz8SEzEQ'
    b'EzESEzAREzAQEzAOEjwNFS0SEi8REi8SEi4REi4REioQEi8QEi4MEiwQETERES4QES4PES4RES0PES0PEC0PECwRDi0MDzYHDT8MDScG'
    b'DCUKCScCCTUIBCYAAysEBhkCAhECABQAABkAAAWcKfnZAABzJElEQVR42u29CXwUZbY2nqSXSbCrJRHZPgSKriSVBFDWJEiAAYHASAEC'
    b'YYtZmDtyqdgJXWYko5mOkjsMy4U/yVURIowgDkKHPSZhCYpBEJT7cfNJ0B8gxlGcxhsnIXQ33ZDmf85bVb2lO2lmRlAnZ0YgXd2V6rfO'
    b'ed7nPOe8b4UIRmHJkiX/fj/s17/ml/zbv3faj89+85vfdA7CT9P+bQn/61/fl98MMAJgEmIUfiOUnbwfVvO9pajo+5Od9mOzEzUnP6/p'
    b'HIafpn1fVGT5/v7cvTKAEmOIsKTY0nwf7K9/te8Z2bNXke2vzZ32o7KvmpyW7+1NTZ0j8dOzv9qKevUcucf+1/sSVRbjEiFkiWD54tv/'
    b'vdf27WcWW1HfLg90ybN/9r+d9iOyyyftFlapYGxfeNytzmH5idhn9jwIqr5FNkv9fQjqLyzCkpAlZc3ffPPXe2rf/PXzL+wv9e/SpecD'
    b'PYvsn/21034cBn5w+YTNzqnVlDqEtZ+EG/XNN198fuLk5ZPwr87x+QnYZ/YiCKouEf1fsn/z+b2+Z99801wGgFLz/Tf32L64YLme9EiX'
    b'nr0eeSCiyH7hm077kdjXJ5qdPKWkKaWaVp74/uOPT5z4xmJz2m327y8Hf5bvv+8cyftlF+xFEQ880qtnl0eSmm0nv7jXv/77miUh/37P'
    b'AeXC90hPevZ8JC66Zyeg/IjsxPdOI62kaEVISIhazTib7M5bl40cQ1PM901BI8rlixe/6BzL+wgoPaPjHunZs0u/Ivv3F+45oPw7AMr/'
    b'/uVe2hfnbfVJvYCePBgXTwDl/F867cdgJ0/aTzAAJ+oQYrTaSLAE8h+KUtD2k+199iv4n2gXv7dYLZaLX3SO532x8wRQ4uMeBJLSa+RR'
    b'24V7eyP+994Dyvnr9qJ+QE/6xsV3AsqPyD4+YbexarUMJyFhSiWBEopSKxUKQJfmy+3ASaPZ3Ej+ecl6B+3WN52Icl8BBSCFkBTb9fM/'
    b'a0D57DP7nhE9u/R8BL5zXCeg/GhM0mJpKgygJCRMoVRTNE0jlojwoqA5+8ftwInD6bB+95e/fHPx1h3RbncCyn0FFAyuRyDQRuyxf/bZ'
    b'zxdQzjdjrbhnT8h24joB5ccCJidPnGiyC7SSphUeWKIIC/EwirWfaAdOlnEtDvNX31y03LlzasAvfnHqzh3L+W86h/Z+AopEUvrm2Swf'
    b'fnEvAeU3Nd9+cW+s/jP7SyMiZHriApTaLzrtPtmFD2tqvmi2OZ1ljCIMMERN+8ESEVAYW42fE1z+AuHkTyxDM86bjZfrb9+58ws0SHqO'
    b'dw7vfbBaN6CIJCUCK8hf1N+jX/9tzW/uGaBcqJVqxRI96QSU+2uXv7j8YZPVaT+J0qtaCekORVNyitPG1EwNfML3FJcRTipZZlpJCbXY'
    b'ab78xe07ggwo5y+c7xzk+wsocaI4+0jS95aaC/cQUP5y+R5Y7Vc2qVacEBfnDSiXO+3+mE0s41AAJbQ6IJYQU9LG5pO+n/8W4ORLAidr'
    b'102jWhyNl++IDIUlMorl4uWTp8+cOX2xc6TvmXkDShwEm1RB/u6ehNlf7hWgXKi1fSjWiuPdX1YEFFvNhQsXPu90hXtuJyyMQi2VcUI6'
    b'MgXF2zwB5WMx2WnhGKakZN26kpJSSHparHfuGGU8wVrP6au3wK6e6Rzse2KfX7hQY/MGlLj4eLGCfMhWe+FnAigXL188et0m1YofjYev'
    b'KFlcAgLKra+uf/fV5YvnP6ytqTlaW3v+PODLhYtonR7yg+KJjQ+hqY6hRKoiU6y9Rr6hJ08CmkhwUlqybm1J6TSBnqb+EvDk1C9+MQCx'
    b'5CovIEkRgcV65nLnzfwnBxUaRsr587W1EDk1tecvXP7qu+tf3UJASfAIsvhH4/pJFeSjF3/o+0AApfqLiz+s1dba/iTVij3gRASUnkkv'
    b'vfTGnqrav1y32cFsNst1EV9qjx46dJQADNjFTvun23t2RkmFhDCcMihEoRjbe9InAUywTrxaZCdr168vpdSllI5zAHYMIAIKUVIIsNwR'
    b'jPCH5fTlzgH/JxgJhtraoxgbtecvIoJcv26xYejYrl+/eGjPGy+9lNTTC1BIyIkV5DdstbU/8AV+Ue0XUC78837DhYsXaq5bpFrxo/Fe'
    b'hoDywAO9ej3ySN9+/fuPGDkyKSmvqOil/9hTdf47b3y5cL625tAhgGERYC64SEyn/X135cLFD0xOTq0OoYXbrC92MAq/quyl8zDmF05e'
    b'MTvA3gA0YUpLS9aDrSuhp5VMY5xlt+7woiIrlnquignQAMx9OgHl7u+RSEAIgtTUHJI5iAQggCDfna/as+eloqKiZ5OSRo4Y0b9fv76P'
    b'9Or1wAM+gAL2qFRBtlyvuXDxwg8NKFVfXPCxGtOJC/8sqz1ve6l/RATQEx84AUuIe6AnfFEPi+j5gB98qf0KRtGFL38BfPkQRxgBxoUv'
    b'nXY39mENNrIBQ2HVvNEXO05x/lXZxpMXTn4B3OQ5YRmgybSSUoZmS9choJSWrC2heIY+9QuJmfzCE1hO3bld+2HnmAdn4M8fkhxGRpDv'
    b'r1sIhIDvf1Vbtec/AEHyAEBGjujfHwAEEMQ7giCgHohLaBNqj0oVZNuF2n/wAk9Kf5/wd0u/qPIHKJ9bnWYCK/C1ak58+OGHJ//+4am5'
    b'LtWK49viCZKU6AfRHkHrheYNMIgvvdz4kgRo/NKePYcufH/dE188CMyHnQATFJw02XFRsZoKUSiMgi8XuXOHV/pVZU9caLQ6W1iGAkZS'
    b'sm5dKXWzYRpwlHXr1q1dt34axdG/kAEFmYrgASiW5vO1Fz6HaIE/Os0bP5CCEAAhCPIX5CAygvylLYIABekZ4YMgJHJIDGEwRcf5i7RH'
    b'48UK8neWmr87QBAIZBj5zPztZ4EA5dJ5L/vAyjFG8wfnrQ6H1WoxN165dP7DD8+cP3/m/BlTzZkzH9S8Bz/gT2fOt2tnzpw5dFGuFfuF'
    b'E+Aoj8ZEu+xByR4JhC9dcOwAX/r1HzFCxpc39hyqvUwIjEt/OYP6yyFRggGMOYN2vtOku3L+TPUl7IulaIWCCgtR36Z9MhwEgltMG0Rh'
    b'llnNkO0sYZiSaRSRTkpozskDRQGSUlI6rZSaxqgQPziEkwFGoqAMcNV8bjcfP376i28uHD99/l/2ZhBPRJ88erQGHRQZ9sXLbgS5/t3F'
    b'o1V7XmofQXq2QRDR5CiKeTTBf6w9KlWQbZcPtRMQ4B8Q7Gfkq/3wgw8+eO898sKZS41XzjSAEyAKXjAbGxo+g4NnvG7nJQIoF8942QdW'
    b'KpS3mqw8y3G8YKxpMJut5s/wyBWH9fPzZoeV/PDReUCWdq32kOXoSKwV948PgCcIKQMTyACQGleMH3hpD18ekPDFK0E68tX16258+Qrw'
    b'5cihqiq4fUeO4M088y9uH7xnN+GiYiWWbhQhNE95g4dU8+W9YUbNOZxOh7MAyzprS6aVAi9Zu24abTNzJQAt60pplmNKSgigDBgg5TuE'
    b'p7CCVEO+c9VyG3Dl1len/7XGG32u9sgRwI8qcMHaMwRBrssIcqZqzxsogyR5ySC+COIGEDeEuCMlJiYmLm7g0JTU1NSUoQnxgUMtoT+p'
    b'IFdZDrUbBRcQED4yQYJy5sKlbxvNNuvn+MKVhpqGRjNDGZsOm3Y1CiqVYD3TaL7i9dGLfgDlow/NVKjRXOYYECqaSqWmeOt7Zz78ooHl'
    b'Gqw8zVlr8Pxmq/XD9q7r0HfuWnEQBrgyGEdk8NDE1DGDZYCJCQAw/vDFvwBz9LIbX64T/gL5EcEXDwLzL4Qn1yzuRcWUMoQ13vaSTCg5'
    b'/j1fVbOO1i9ZxsFBrgPcZG1J6Tqs75TQrFOYRmRZiqXpkhLqFy4DACHAgpVjYcAAF6zcuf31Bz/vEf6QcBARQRBAvnIrqYERpN0kxgdA'
    b'ohFA4uKk+XjwwISU1PiYaK1Go9FGxwxNbCfGXBXk7w4FhhOzueGvSB6ckKBYzQ01RoFvuHTmjMnKKVh7gxrIBhDVVjZUbcaDJ6981AGg'
    b'fFBjVoeWwbnoUM7IcxzLMKpQzmE680FjTajqcycbxjhNH7y3y8pQnNn0wQcf+b+uo0dtb4i14keDwhMYm5S4aI1o2uj41MEJA9EGezCY'
    b'DvAlCAHmT3uqznznxpfvSH7kiS+nf/Z4UqZW0pQMFOoQjvNOedyEwrWgR8laW1tYZhqtY0sJHwFGsh4AZf3aUqrJihRlXck0YC6QA6nc'
    b'gML/QhJQxG58+PvOqQED4K9b7/+8hvS0mMR4IoiLgliuXz7imcQEgSCBKAhBkITk1LS0tNSU5MEJCQkSGUlIjNYoNVqtDkyrVEYnt4co'
    b'j8oV5KNHAziI2ahmrB9cbmCxiVqlIpTC1PjBGZODC2XsZjqUvyUQTFDjYQVnfa8NoJw/7WEfmh1mlcrKcHY6lKIZloW0B1Ogw6ffMxtD'
    b'qQYnE8o6G6xWpxFgxmk2my/Vnva12tO1Vdev52GtuB/Sk4QgLH5gglap0cXOmTMnNkarUWrjkj3ISwKgy6DBxESA8c2Q7iZB8hRgqk63'
    b'wRfIjzBDOnr06PHjhK+2/YI/Xau2MyGMIoymRaigQhQhXniiIPsPXMV8xQUn5laxg62EwtrOWoQSVE0AUJCivIQUZX0JpEBr15W6AcXN'
    b'VIiQghKtDCwXfsLjJzrE8ePYCkL85Ojx0wAh4DzXxSTm+sUjFR3JIDKCPBKIg7gpSEKC6PWDBiUkDE0dEx+t1ZIpNy5Biqr4wfEapS6v'
    b'vO4GWl1+rFIztJ0oc1WQr1+vgjBt+wUxytXWqtoGVShkJjTDsJwKEpb3Tldb+VCa0AwnK+cualUo66jy+PR5EVBq3faeVWAFlZoFVKJC'
    b'JYAC463VtdUWIZQy2xFQeJpmqFAVYI1Q1nDl/VpfO3QUa8VdUIwdGBScAJ7EK7VLxVEBK39aq4xOifcdDRldkLwQfHls8MCBwRKYjvHl'
    b'P/bsOXQREySP/EjEF6QwgDBHa3/qVmWngJYwdwSFWLqB/055aSgopnIUe0oq9ChjW1pvSg2x66bRLRxWd1CILSldvxYpSouDR4ABNCkp'
    b'KWX8AgrvCSz8nTuXj//URg1v/SEJQWqOIgmRshiplkuSmPaF1F7tIgiYDCADBz/2GEEQ8HEPr48fOhDnWQ0SkZhYjRwc8YPjlNoXbnxa'
    b'd7Yc7VzdjXKNJiW+vUBDcTaiS/+XbLWH/HzVI41VCjVKr1SosQGyHZ5jVaGCBcJfBJQBEP5cKMULbChttgIYOEwen24LKCYHG8oCjgCV'
    b'wcTHbG0oM/JwRvPhWhdEsS6IAlMARPkOf9X1r1y14oQgLVmjvfGpOCpgdZ/emIPkLcgPA7wMeuyxx4YOHerOkLzuVpD44i3AvOQXXyQC'
    b'c+iniS9VdgYARWnkOEWIqMqyACAeJEVtvM0puDBROeGFPa0Oub++pLSU5owAJiUCQEgJU4JiCh17+zfAWtZhnYdWUdOmtQWUU1j0OSUD'
    b'CgDWh8d/CgAi3WngILWn/SNIsEKqfwCJRg6SMGTU7Ozc3Lw8g8GQN0hEEP82DPIabYzMRLTaVCk2UjS6G3XlZ8+eRX5Sfu5s+af5HQRO'
    b'/KMJYgX58vWqth5cfaQGEhResFKhCleQI584bEY+gQlKKxdKt7YKobQTfmI6AJQqB3AaYDu8tQY5D262w7CE89SarJBEOSXOQwscE0ox'
    b'NMorPoBSdUauFQ8fKOogHVvCmGjNWRiPczAun+LAlJcDosQPHhi8ucEFyEt8QjbeI7hLiwbFufhLjP8KdSCBt1dbfMEWO7mAJOu7Lv7y'
    b'UwCUmktGNdASjuWJ6Eop1JjieHKUMEWI8o6gDlMvdrY6nc5fi3CyvmQay1GMzjxtPXARFhIfmhCTEiDFJQRN1KpfDCihSkq98WTAHVYS'
    b'UO5cZUlN+c6tIx/+KCGkxo0gZy5elnUQTGL8IkjPuxNSIY8RVZCBAwcPzskTvRONUBs8b1F6fDvenarRAZjUiUzkUx0ACnk5JVpZjjhS'
    b'VzcnNja/7uy5c+U3dJrU+HYjZeDwuL6iOHvRlwzUNjitKtWrKlUZHcqg3GHcgxEPgPKeuSwUqAtAyCk+VM2ydKiKplR+AeXMBy57r9aq'
    b'VsH7jcBNkOtQlBqzHtWuS++9j6oMbaqhQnmEqdu3gcrcdpJf5v78B+9/cOj6IbFW/OiwhODRIFUTcwPxpO5prVZnEAcGYDhh4N9l8dmG'
    b'oiRgn4AGRfl5Q+Mfe2yYaI+JGVKgBMktwATAFx8B5gMJX8D5Pvnq4kcfHBFdEgDmCNr7YB/8yEykKPQt4RSrCAlTq9V3BIb17mNTGu/c'
    b'vlXmcP4J2+tFOFm7fpqSLqXYV50c4sg0uqRELUkp00pLpoFnIXqUltClpb/wY6j0IpwIWDg+eZ/HBO8KuT2H5Lt15IOPLn71iUsG+eTM'
    b'oT3eMkhgBAmUxLhVkLj4cYuAggCC5AKPJonMcIMo0EJ21KdPn94PRRJ79pn4QR0ECCY150TMSCOhkZAGBAVfO6tVajTKPJyKbzytTBjU'
    b'QbgNe1SsIFdcP/SB5+1478oehlcraEhFIBPhsSJD0yiUHPzg8JUalYKgAS24qIsK3mjy+PwZBJSDp9932eHGMgUFmY39c4HfY1arrFYn'
    b'H8rcKrM2vvf+QQdmOsCD1AITSrMcQJipCuDFVv2+hx2+TmrF/eJGDcLxC9YGa+bcwMGYo9RCpoiIUn4jVpN6N6dw2cD4vKIRfcS7FPlQ'
    b'v6T8bPedwl+F8JJIbOjgQQgw/6gA86yEL+9/JSZIiC8Xz3z00bEj1VUV4LHVbny5/3a6DBtkr7LKq0qiyqopnvLcoS2MZhmavYQbnTDT'
    b'pk0TmFKyXqcUiAgT6+R+TcRYip5GTZOFE5plJTpSWioDCk0P8ACUU659lwBPDt+Pby0iSDXcjIqq6iPHPvrozEUJQeBuffW+REGe7VBI'
    b'JR4BN76dQszAwY+J7jVs2MD4YciUCbUZOdIwTHTnhHEG2TsjI6Oioh56qDdYVFJu/GMBfVpEjrobn551AQpx9VRNLImbWOWg1AyN9sZZ'
    b'mJOXKuOHdRQig0ZJFeTrXrejGvIamoYQrwHSIEFGKEVDyvP+4fqTKtJCQrFloSoWEhTa2AAUw+p5gtMHfQDlIKY1ACEolYg6LqUOpViW'
    b'q7ry3i4HI5aKQgXGpaCEhgpmT0Cpvl70QJcHHokePuyusOCxBGUejNVZYCX6VD1BXQSUxL8HTwbFG57tExnVWzSA//6AKG1ulQwvqL2I'
    b'+JKcOOyxQQOTUxPj46K1YP7xRS5Qd8Rf/nNPxfsX3fjyFQDM+y58OXQf8eUgoSjsKcx8iCpL0WqvLR8VIeolTgeH+yah9krRpFQs9p0s'
    b'pmnAEaAoaoaeJqIJw9+SWuwRUUQYGTCiX78RtAegiC8b79yxHD52DyHEhSDvA4B85UaQi+9X7PnPDrpBPBHEh4LAlIdG2htEBAHnIQgC'
    b'zuRyroGDEtIRTEb0eSgKoaO3YVSC6HrDDX1l9+wNaPIQWu/IpLx2AUWru1m+NFYr4keMZooIKGMkQNFpMuKTozXldcEBCnxy2PDoRx6I'
    b'eKDoulf42oRQhg6lysxWgWdR4YAcxOg0N5jfP3y6Qa0wNjSYrVZUWW4DStwGtkG1DygoofBEKhFYlglVyZVohA0EFM7Z8HmN0Yr5FQN0'
    b'h6ZCVUYvQKkCQAF+Mmr4wMcGAxUI2gZpnoaB+Z9zKF/D2EmAkjLosbu1QUOAn/SOxBtF7iKgPyDKrxKG+LkaP0RpGLbCKLGsryFeE53Y'
    b'QYLU7goBUYDxKSBdlwjM+5ggVXhkSPcEZI4cOV6lpkNolmwcG+a7IQoVu3jGDGcrL6Y6a7EUrEbRlSzXKaEpSHtKSL1Yx5YCmtDsG9io'
    b'P8AnxRmBgDLCN/HBZcfvfvD+kR+GfhwRu1EJgkhZzHU3gkAS8x8igngkMf66QUQA6eunmYxQkLiUGFJqiQWL0UGeEZ/s14/QvQYPNCT1'
    b'Qy4icpA+RZMGiq8PM/SLktAECAoeBotMejp+SEC3HjhFq9HBb1bKoZFKQmNgmjT5xmj0KfpoTd05cjC5o7iB2Bw4bBRwFACUKs/wtQJO'
    b'MKG843OjALSBYlElVUGq03C6+n3S8Hr48MHTJ1UKngfYgXwoVG2ufc8XUGqPuKzaylFWFgvDQpm1LJS6ZW2FnywCb/7s8EEEFOvB0/VX'
    b'rFSocNsKMGVtUKmqLlUf8bCqW0WPYL149N3ACYwX0VCQoeRkZChl1E0beNeAMgymhT6IJw9F9h3Rv28kAf8RhvihQaHRmGilLnbO0vzy'
    b'urry8vz8fK02YxBwF9ESBw1LjZNmJ6UmOs6Hv/QNJMAQfPESeDFBqjiCACMVkC6eIfpLRYUEMGhHfiA7aGXVwEnUAna0UV7yiZp3tjpb'
    b'W/dgvwmu1llHsIMW1+uUTmNK6VKaKRXFWJ6n2OccLUapv8QLOUYQa1vwuf1P/BpkjIgGUkEQBEnIdwRBALM/+ahqz59e8kSQvkF2pLoQ'
    b'REs6PggFGTR4qOgDiSmpWqXu6fJPpe6GunxNdGpgHx1k6Bf5kAgcAB19itIHEsQY/Bi8LiU8vfuAIeBE9jWMHxgYUAYnxuHF6N1zrRQ3'
    b'ACLlZ8/WGcAhtRg3Z1F7DCJuBo+Oe6Rnl0eKblV5+wYXymKY18gNIwpVqJqmGXNtdTWGvbW20XypQeUu8lINtR7xX4uAsv+45ymtDbcg'
    b'O7KqSD6DrS1q1Et4wQy/DNiLo7YeEi0qlMU6dIO5TKE66Q0o71tbX+qHiDJu8JBhQ4K1QalErS6vy0NtSfNC3VkYJE30lEFD7tYS4w0j'
    b'RX4yIt9gyB8RSfhkUW58YjCXkRatRT+pqzt7Dv6ou6HTzsVLIJPQYwNTEzRKLeDN0rw5MTg5pSYMbKvwtgEYH3gJIPDuk/DlOsEXII0A'
    b'MBX7CML80+HlPKY7NPAFCntl3WIs63S+wbHsDBlO1gKirF0PyU0JQAj8jTsqkZwHq8TAT1oWs+xi0lrfhqH4ARThzp1vqv9RCCH4sc8H'
    b'QewigrzRpp8MEMR77KXBd3MQz1V1IgdJTI6PRh8EkqrVaTWpwyCTAQ8gDpCcoNEsBf+Q2xvOfqqNTgvsowMN/YGJQL5DAKV30aIEEhHD'
    b'BhpG4r0X1TdDkQgoMOm146LDhiSnzk0dlqbVfory4hzNMDG4EgchipSfrcvTarSxQFDqbsQoB3Xk68OGDB6HeNLvpVbr+55DvMvBhnJA'
    b'IRwNLAt/U2ZrK6YlwBwaDldg/FtrjEKDGRJdOlTF8gIu9Tvq8fnj+9sAysFaACLIaGiakB0ZiShrVRUc4MpMNQ1mGaFUKnUokiHPz1c3'
    b'W53m/l16PtB/3LChw4K2x1I12v+5ce7sp4ZYHZa/ynFgUobdvT022tAXASWyb/6i+Pj0/H6Y9cDdSkgM4sOD5mq1daKrnDt3Fi4CwH6Q'
    b'6+CUGKV2qYg38MdSnTI67TGct1KIJScOG+yr8D4o9hv07y/jS5Addv+5p+LQR9/JCdJ3Un70z8KXg/iIwBDhzu07LKqyknKiYOpbK1ms'
    b'6wBmTCPySQkyk3UljIBC7PppFEJLCQX/AVmhKSqWE6zO68KttpDC+METSHgslf8YgpyWsxgig7RFEH+lGC/4Hpn0LNZbnvSsxMTFJwwc'
    b'NDQxUbyJY+KxewxcECa3urqbeZphbr8ZkjxIqav7tBy7Pc7C0XPl5Z9qYcYJ5E2JCYYRmHX360eSmqhnc0UnTByYSzoa8vJycxdNMiSh'
    b'uwLc5Hbgoo8NegwnvDqsheYBaEhxE62ccwMCB0vKKMkadMq4lCEd+PnQYeOwytO/wWlt9oregw46FKgCa68x1xi5UDX4A4S4GnOe47us'
    b'AyDiVQoVbzVj4kI7WVqwVh083D6gVNfXwKewIsyGqnhIpXgVCiacteoYEBMEEarBzJEyNOnlp8xHDnt7wd+st26NjOjZ88FRo4YmBmvD'
    b'hs3VKOcA+GLjTh0ODwzMmGGJd2vDBy4q6i0jfnKyRFei+hhmPxbEp4dkIKUEX/m0Dstz5+pgAhoiHwM8ib2BcEPmJ7jEOYAogxJdXpAo'
    b'5kaj0THHAL48lv40em9RXl6RAchS3tNeBEbCF98dpvwuocYK0kefeBaQRHzZRzKku8eX6msUpbh6h4WcRyECShhT/CdZiC0pmaYmLfY0'
    b'gx1ra6cxVhbX65TCQXiVLUXQYWJnHHXYhVhdeES/ott32uQ9cpFngKvVLYiER8piKtogiNjSvs9DSO3vt5+McJAHvHSQpDxSsjWINRwi'
    b'wfbPHz5oWGJyypgxcKdGj8ZUxnUXUzSa2LxyMmkAbGDgJrt9dIpGiz1S50i1pZy4qk6bMSSQN4H3jejTP6nohWcjJZEkQTrZoEFifzf2'
    b'xRrEKa+fIZgowQxH1F3lUw0BRNHOwcats+iU5TFKZXzqkPZPMzR5FPbfj7x1y9rk4xmQDjewoUwrHephKrWaBkBxMEghVEBTyhy8IpR3'
    b'qoG8OBwNvoCy6/3DHrYL+2F5FS7gUfFOVoF9cWpjq/Vo9ekG0pcSqjpZb3Y66VDGCmxlV1nDYR+r/sJ6q7WoV0TPvgPHDR2eHIwNT05M'
    b'g3GJLa+TgrU8FsZlzLDk4D7uafF5SZGyaC7+RPSUpNyEID48JEuju1lX94LhadIjVHdWE502TBJQxsQTcgnudBbmJpgmym/kAaIMkb/C'
    b'cB9kG5xuQMfv2wfcpU8fQAhIuwb6rkGKezwxbkR/rxaYjpdQS/hiEROkTz4589F7h6urKvbvJwSmGu1wu3bQxqnBRxheHRZGKSD/UQtO'
    b'pxOF2PVEiC2ZpuMlQCHNsGRJ8TrMf9YCX6E4juWec9h5RhvRNap79+4P9yu6c8ePlEI6U6jSaXLCY3n3PV9XASMAAtdeVX34PamYK36z'
    b'i4f3/6m4AyG1i4eQKlK8Z5991kNIjX66yNXuESVXavsYJg9LbjsVkds4WvP0TdTPzmJ5FqWJhNEu55irhWhGB7iRH0vW9upi63SarCEB'
    b'3SkhFzKavOzcZx+Kcnmk6O4uG5grzX+ug+0ZAgop5OQr41PEsyQmj9EoY7G5DWbBs0CcynXKmClD2gu2oeMG9+sZ8UBR6y3rF76ectRa'
    b'YwUmwbEULq5R4wYmTChldFo/O7wLV92QxTxWK7CMAWUAETRQmKpL7o+/vwsB5ZgXoDhwsY4wIBTOJjhRnyW/wFr77qWyULXZKuCyZasZ'
    b'CEqNoKJO1h95t42/vnvcam19qS8KKZMTg4OBYWmEuSE1IR3E55bisCTeNZwkj05wQUhewujREqD0jhyZFz86iMvI0GhiiOyaV4cV/XKN'
    b'6yIS5Rai8k8/xZZF0noXqxySEvBCcpNcnQbEl5NyBwN1kSwlV5w2CUQgf4luy18e8VOh7ulnCXXxn/YfPiMLMJ9c/EjCl30EYfzCy8FG'
    b'igoJwy1RQmje4YDMZYmO1HVKSteJQixTis32qL5OoxzAXUpcy3Wo2BncHqcxVhsR2a17jx49uj3c4+GAkFKKDftSwnNbRhDED7i6CkAQ'
    b'gJBPxCwGrvyjCs8kxt2RCgPQtWsHHanxT8Noii2nRXPiBg4aArctZUzq4LyRvv0evaP6FM0fGsgDSF8Hso86AigQuGPkQzCjYCWSNEvh'
    b'RgFYPtYotRnD2vHG7NmDE+IXuTFjdBsvgayIUOii7KEd+2diagwACsDGC8q4CQRQho9OVmrrMOWpW/r00jo8Bl4ZP6ad0EmcjPJJ36JW'
    b'KwR1W9eosmO72YAGJ664cdJkwY4KgESs8joQUHhKQRpUQqUC8EHXp4/5Akr1wStlKpWxEdIlpoFSmABcTGoWfgNjLUPqYjbzoVSDwBP6'
    b'woeqbzkcZl9/rQa3sVhb9/Tr0rNX3OTgGAqkE3nYCFiXHxsTa4BcEIclJnX43w0oePsGAqC4FFpDQhCAMnxCDDYXxMUrlxJAgfsmXQMw'
    b'KLyViCd54EcxdXIzbyB/Ei9EUvix2aB30TODR4lcZjhOTDDp9uvTWxL6+xY9kzBkYDsCL9gjfUWE+T//xxVe3hXqJJHAeOHLdRd/2bMf'
    b'AUZkMPuRooipjtlZaXUeYxiOCLHTsOkE0xxsW0NFdi0gCLP4FbaUCLEMDcnOjKNOXhfeFdGk28PEegSEFOx0GyAtMrbsRQ7y0UUXgnz1'
    b'UcX2N9pdmNuzZwSx8PBwvzqqKKTGPw2JZVL/PhIFGZk3cCxJZIAJwITS230TxDvRXvAOT0NAgVmNtKR6BC5ONlqtjCfRGXNTJ6SmZU2J'
    b'iY5Pac+hHhuWPHpYtiS7jjS0AZTE6UTx6x3Z3zA4mDiZEK/MR9CAmU50zOF4VXVAmpdiTVmLB0lTSjuRMzmuV88u/fa0Wi3V7x6ubhO7'
    b'ZYAbjEoFNAISmipVaI11F/xTDXkOYgnCC8eGKlRglCpUzTBs2aV3fQDlSLXb8HS0dVd9gxFX/qhQMwllnKyaN5c5ILdymLlQ2uhqeVMx'
    b'LCuY91e3sYpmq9M6Ahyi/xOjk0d3aMkZZPoHiolLsyG1wGGJ0aQF8VFfG5wrpTxw+5IThxJRltywxGA+nZyakZOVlpaAt02coCaI15Cc'
    b'RmrZkD4vVWpjopW6TwmgPI0Uxe+ZUlyAIrYZoMg/1OtgpNihQAhMVNGiYUBfxk+Y8MQTT6RCbg8Me4h3ggQwFh6uDBfNb4LUtWtXMQFw'
    b'4UuRmCCJLXae+dFOM4XtsZTQ6mDpWJ6ZVsqJQiwlCbEUyiYl4ppAVGlRiKUpjmGWWJ2cNiLKjSbtQ8qAaQPkbVFsn5yp3vOn/2izMLdX'
    b'2yK73JEaLjeQ6ZQar4bUBKQgo1PGTEh9YsLU/KQRfXvL7R59esONT5HHebCYAEvcRGz8iIzMe2ZwgPs/PEsTc/OcATKapS6KKt3flDFK'
    b'bOY+V1eujNanZWRlZUxJHp6aMaZDn0qcbegTKU1qKT5OMtDNpwemBOGfYxJIFznJxfG6kgFhDJjulGu0wxKHiU0p4KIDxwQIneTRk/vD'
    b'eI+A8GyuqPZnWMwVeJYODWVZ1kmFlnEKllepgIfgTo6NmMD8lReMu2qwmZZpdTiuVLk/fMQXUHZZBRRddtWYjSzwGkATQA3ulvVz60FS'
    b'5DFbEVCIGisRnjDWUebnsiq+td5qTQJ375c8vkNYGDU+gQzL2U+1mpysrBgcNLiZypi0UXcNKInp4nwQ1deQN326oai32IbY3xAcOI0C'
    b'/jD8iTjlC8SfDMpHx4svp8UAxuCk9alWq5+SNYQ09oJ3aaIzhvs90dgEiW1HidMjtiEkeh4E1+/tMWlKB0chiRklOvDY8eOfQHyZgOVq'
    b'0k01Z8ac2NhYnU6n9CIwmBs8ECFCTUREz649A3fASPjyiR0oShiLwsm0UjUkO4xaQI5SwhJAwY1O8HmAgDFrxRrxNIYO7xrOO1vsACdA'
    b'Th72tR7tJD6AK7fvNLQVUrvi/qjIQLx1VDcHUcYuNeS/UH727E2YdIckj0YAQRs/dowYyITBYyN7lIsKYtyOlQd6aG6S1Dbm2fhRlDt4'
    b'bABAydFqSOeamN24AhduDJDocmlFiF5spY4ZkjV+SMcemjzZBShtcCzR0J8QlL6GXwXln2OGEO6M1QLid8MzorXkouYoM54YNZfwF0SX'
    b'QJGTPH50PxjzpNZb1m/940nF8QaVwmg3qRRcg0rFYKUXkhGjACTjpCrUWIu0wmk2N16qx6U4tPXVMs/z+ALKwUu71KEDrPsPNhqxh58D'
    b'sDIykO/sMh88aBZCVbsOkfM1NJyskTvpGN4fQ4ELO221thY9EtHzkfjpUmE1oEG4iqkhMIIpw5OzpHZirTaro0/6MfEegQv1KzIYkvpE'
    b'uQElqI9DJI8WLwfAI085bCx5MTmHdBSJ+vrYZJjIdCL91Wmyhvs9z/gEw8g+/fqPSCoaIV5OH8PsZM+DUQgoUZK7ex5M8Z2qwGs0S/OJ'
    b'vCR1VNVpYlI8EiSi+pDGCVwIFR7+QN++HQm8I15imdjbe1A4oalSgA6acS5GDUXuZuNK8U8KS8frMdWhjA/26BbO8QAn3uQkGEjB3QtG'
    b'ejWU4fU9gAAotgl6NoOIHGTgkCFIW+uIIV3NGuVnCsfBmmjoSzrYe7sAZag8kGOHiZrnQw/1czd+gFukB/IrgA3sH0vTk6VlYuCK7x2e'
    b'RVpAyC0XtyXBXcDiMzp2K7xAKa1J9Hlz4iJXNjR4bDDeOTZZ8zRZr4OAgleV4+p0S0seBXCTJ8ON32+YPD2+b8+IR1A+Oe8fT6p3kV0K'
    b'yqyC4LQy0mIeBv69fz8cUDfsxxXC1lcPHqyoKCOA4n0aAig73YACH1KpGy4dqD5iphmjmeNUqhoni0sKq94hudCrJO8pO3q0/lK9E7HF'
    b'4TAf8n9lFUcsco/bLBiJlLGBbXQGbl5AGMGgsaNHZcjrE7T64WPv1saBD/UhrCAyqk+fSInw4s1MCfYU0uWQ/iHxQ2NGk9xa7GvOGD12'
    b'FHjXjbPiO54YO8bvWYbl5pNug/yRUt+uYbL7CgaTDoXISCkK4OD0wJeXjL+tztVNBek9AG/auCeemIKWNhz7JvKwuZfEXv4cHXh6W4XX'
    b'O7lIuulwOJbgFrFARiC9gb9Iuwkp5uDqv+emkRfVTMn6UoptcTLLmK6AKOHecNINYIRYt/YghYdXinp5cxCx3SN2Th5wkHJN9OD4QUOG'
    b'J6eMnZBKvtSUJ55IyYiG+RZ3+jgrDTuJqDaWMh4b2ZGC+LnVUsRCvpkvd35kp88ePzqgO46ekpaTkTpqqni7MXCzksmBUTniHFJ3DlJy'
    b'g1g7yNMqozNGdeRXKWOlynB/w+gU7ysfLHU19C7KTQzONycQpMOO8qzhWC2SAWWOZu7o4U8kk4SIAMqotpeRkjJL7mazHAmAJ6KE4nin'
    b'wloDca9icSUO/D2gpv4dkZBgiiKiyDvwT7W5+l0vQNnpDSjV+wGZrMA43v0M96dFlmLe7+ApwfwOchbe+iqWjhxlFRUVB/GfjHXNOwer'
    b'A5qrx21Wu3hCIliuhmWNTc2QVh4DoIy6a0AZO36YISmSCCcw/3tMW4PHBw0omaR9iNymKeLNSB2klPZUgIsajResFcsAS5VDUgOdBzw3'
    b'eXCcKONjo8FE1yCMSzSM6IsyR5F00Att2lxPDsqBZ0lonZOqmQNTU8QpDeiUUu6bwDdg0115rFIzJOAumYgtI5wOp7OFLZ1Wur6EXt0A'
    b'4IGVHVGIJXVj2s6X4M4n0yhIiegZgpNjhYjuD3fv7gUnPXp07xbZtUuXSDkJQkjp3wZSgJ8s8WpI1SrJZkFItj5FFNRG54x/YgLeIPdc'
    b'PEZSrcT1+jADBxqgFNLI3qd/Uj95oN3vTBET4KiovFxx47PBiX5RyeNshKNmyfOHVpszWnxdnOYgn4jNv4E9beVn6z698bRSmzW6I39K'
    b'kfKafgafMEiZmC83oQQz240elTxqpnuyzcjRZ6FrSGpftD4L8rW6c/9NUp65KX6Aba67m+3dACF74FINxvk7RxvUoQrG6GRCId+BVMRa'
    b'XYGSBwAKH6q2ko/vN/Mq2nyoLaC8c/hdt+03mw+K/yrbZeYZRjAf3A/YcvDg8QYakAmVXgAUPL6L7P9W9m47duB/sccNNzOYPDFl/Njx'
    b'gWxsWpyogt7QKRNGTdACuvw3UStyRo+/WxsLbgmZTqS4iCJKlDAIp5wY7ClGZ5HEVJwXyVWnzBWTIAL+WaPHjwUEPCfXFWeO9X8d48Fz'
    b'x09KdAOKxwgk55EZMzff30FfG0VWcJSTxQDnJBgbniodHIN0qlyEm7Nif2953Y0XtJq0tOkzZ6alTXliAiq8g1ybTJEiksHhiGUcPEND'
    b'tkPzrTxZ8EeEWOQoACMCbnxSUgLIQlMznIIuKUn3ibZbD58cp1uXcF0sx3GxmAg9HAhSBgBDeRJ3J0skFGRqxnBlbH4dQInYk3y2/FNX'
    b'2OKEIN0EEh3nZEABJjghwPBAvPYb+azB8ELbsRybIgqiKHqm46Ykudnjh6ZMaGesx5MrGK13pbQwqYkHxFBGFc3VS11efsMAHKUjJ012'
    b'CSWTUzxfn5CYWxQl9UwNnTC2I8cem6EHc60uJjLO8Ax0TLGDQUM2RMHe0Dyc5dqExcTJ/aRutsYDAUP2oBXRowqjmwY4AUrBmy9Z+TLz'
    b'/gqzwJRd2tVopFmgJWhHGhrMn3t//PA7AChl1RUetmuX+DckSYeskNDsh5eq4I/9l8w1V/bvt7JqwC/yRisdxjperWjP9p+Wetz6Jc5K'
    b'aW+0niIK+lnsygEqLDWBKGMyxo6/e5sIU0LRiL6kiNin/0iSQ0cl5SUGDyh6uUAYq8kiVzA2S2QkBPzhosZKSdFZ6ef2TiZKOkh4vUZg'
    b'9uSUoYMHuw+Oae96NDE3kWLn55WLwnCeZrT8baRLO0v23jlbTjjM2fK6T7UaaeqE9zwxcfKU6XOfGjM3z/AfX7a0fPmfL7Q4l9AU42zh'
    b'StaWMHSxtIKYxqpO6bRpDM3ffIlFIVZNcTxvjLXOCO8abozt6gkogCARWs5k4jmWXWLiw6N6POwfUjDhuTr3qenTJ08kFz12ykBl/qdi'
    b'SEpwgbTP50tPGUJ0UYmTeX5j39tNwDk3PUHuEID00XVHxs4y9CWCaNILpFE2r8hgyB42fmLHHuDSyOQrmyrJKufE7RZJJxJRQ4dM6cAf'
    b'h4lzCgplXq4yMdHdhBLEzDmRbFCtjJE0E1xqpIzOGi/WnnDNSgzZso2UjXPa+GTKU4n9ekb0wm62+v0BA/bgITPuSP9OxcGjZuslK6dS'
    b'Mw2H3tllbUQEMFuvACqYHY5a6d3VR6p9Pl9dBoCyvTrQ6d959dWdBBfwj72HLsHftWZzw6ED5EUzB/zlnYr2EYUIKaTHbeGEJyY+MdGv'
    b'PTEuJ5o0IZ6tu5Gfl3dO7hrLCPD+du2JiVMnJubiRhQjIaX4zyT5lqUEfQYvdxqLr4zTi4ocaUyYC/6YRVaKS4Ayvr2rERNoEVA8rnHi'
    b'+AkTp06d4IE2gc8xLkejnUNEQKXYCoOpmHxwbE40Lj8iSX0d2T2TxCgWN7PGwohLNnFi8uS8/2eFKQJyHafDaudYo/K5BiKU4BKdtevX'
    b'rp1Gl/5/uF2BbrHD+Z/PcjRFMYLTzukiwoXF4f8nPBZyHo98p0fXcM7O09KDTxYbw938xRtS8PkZMPqkIk5syiixbxBbjt2A4n0Px+o1'
    b'WjLFnHNxspmBvGdi9uShyROGGkbK6vd81x2ZMFkc/qh+/UibykN9+iUZDBPGTG7fs8a6PCBGox8nvpYmAwpMK3A3YvIlRNFq9WPbPdvU'
    b'oS5ASR/j+c4xWQZ5XWDylI5cfXxGjFKn08XGkirPOeyJvXFTp83JIpEjr1kpP1t+DgInIW38E14j9MSEha5utiP72wtY8x7OjL3LB6r3'
    b'v1NlNput9RDt75CP7CRcY/877xxwvfuAL6BsbxdQfH7Xfhe4EAMCY+74QxWuHreFEyYEHq8FuEe1uD01NrYDmcxH+P07AGXi+MSUySnJ'
    b'hOHmLXIlqRMm3gWgeBBeGVCkIk++8tGn4OcsWUPpCFBkjyZeM/luDnr6UjR5VlGc3FuHqZgLbQDrwLfKn9bB/KWNwaZAWXXIdF/YpInJ'
    b'uf/PYXU4HZXPCcKyFkerQJcyFO4Qi3snlWB/LCQ/CCyY5TBvOOfEsEsckD6HR0R1D78eG97/Qe11z5ynR4TuE4HSRA+DVF6vH6gR2C4e'
    b'8gq+T4QUHhlK7rDpnhE2XvN0XTkRe2RAcYWt/K0ysHegvPzTp0nZQh73QPE/YerkqYlySwfE7Vj32Ikj/FCkuOsIdqH0TcqfP3ZSux4g'
    b'TyCEo0qjKGkoBGVwW0GNJKrNUc5s352mDpUXlBUtGuPxe8kVi6sG8xKndujVmTGaGy5mRCBFBOIMjbZcFHUweupu1MUqY7LG+Tga4Inc'
    b'zVaxv/2AvWQVCQP5o7r6nf0Vd2F3BSguiHATmJ3BvL9J7nFb+NSEqVP828S5o8WF4URaRF/LU2pzxk+ZPOVubeoT6Xl5Y5InTEhJTBwa'
    b'b0iSk9TE6UGfYrxe3OCW3LDx+IobUGCmTMN3iCoLAkpcxsR2zjVxtrj4GVWcoTN9DqbOkg+OMCTODPyVJs+dDvlzll4UbkQ3n+i6WK3u'
    b'pgH33sHKjkYWMjEEXVc2eeqUMQaEk2WxNEXTQD3o2BlMaSkVy+H2a2vJPgXr101j+JK1awFSSmmKYwWnjdOGd0WlROvURcfHawWPnKd7'
    b'OOOMVUbrc56aDHx6nD6GKQvv7tXq5oIUSHgg3fH8PjDZ37zxf5fGanWu75Mz3uMNk6dMFGsqdedEWkC0qrkBxnny1KlTp0yeniwBColb'
    b'l5+NlZoI3D0/vSMjR+b/auLUdj0gR5blEbqll2QNpS5PGY9ihtZ1Ze14AFzbTAnqsJaTMgkY2tTJ4pecIGsr+fOe6NDRJ2bEafLdhb5y'
    b'7G4jE97MpzREkiJgU26I1SjjssZP9RrvCdMXyt1sTR3iw/53DviSiB8WUO7aAPOkHrdJ81KnBrCJc9O0Sq1U/cTSJ+DJpKl/h81MzivK'
    b'y8/L/tWECalZ8l4TfQzZE34V9CkmSb5DmtjG4yvjXYCSpxyd5vlzvjIho73rnJguqoIIKIkzfQ6mtnfQ64rgV44fh17+3+ckIj5eOjRO'
    b'T/pIYybq9TnAFWKUEjH/v1g6mSifYEK+w+os1lEMx2M3PM8xlLq0hFPjGh3ca3od2fiEWVIibutIszedAiEnACc9onROXVyOPtoj5+ke'
    b'zjppzUT9eOk3zEvQmcJ92t1ckGLJHeP15SZlamKxtg20q1wO2yyvQYSAxuwODoRIgAJMMHNiezdteoo830PcjpFv9q9SpKQSG5blkh/M'
    b'L4aU9oZ76kSSgovJ5UzxnfItl9KgcRliExnpfcsJeGW/mpqaOnWoBCgPPZubPGt2+vyJ0gXnuppQ2r350qBlJChfwHXw8t5OdeUv1AGz'
    b'Gz9pZg4+YUNHHhwIgxqdkTnex83mTZK72S7t/2FjHQHl395898APa3uPSj1ufYdmpk73sqmTwJF+BTZ98nT9o6gSYH8W/KWN10+e/vfY'
    b'rEQgmP2TisgjCpKkeEUHCv4UkzNFQMGY1E/CVyZ5AMq4WdOnj5eSImQso9PaO9fEbBkzkvKSZ93NwTY2CWiRa49i/Xj5HBB7mnh9zqxJ'
    b'aONwG8Cz5+TkfpL4npnIT5wcxfKl2Pq6ljxjhxfWljJq3IyNGOmO5UqnAdIwSx0yOSHAEMk4tMNnpj2qc+U8PcLZW5RWP3eSfG0LEnQf'
    b'hz/cpn+2RzeNk5ujH+PzRXK0yKeG6+M1Lk1ogecbfjV9Ftl8DOBaYlwIKDntOsSslNw8iYTk5abIgzkzxTAisg/pkyVpj6trOXdsew4x'
    b'OUssnqAYPHGWa/Ql1QR56/RZ48UmsnMuJ/F7osmz5qfPl6Au8tkX0Cnzc8fj756Z7MqEcsd07JS/mjdcubTcsPTpObj3pE4r7lEanTVp'
    b'+uRJOVlx8qONh2fpJ03w/mRqZqLczXZ07w8c6u+++W/3AFAO7K129bhlT535lNtmLszKXLhw3ty5T82cOemXafqc0fHYNxET/5Q+c7Ln'
    b'G4O3uXifIiP79Ovfv3+fSEnyzJ8/fVZQn545GQg0kEhx1UYdTD6T8eVJerGRjQDI3Keemp4j9ynM0cxt73yzUsXOKoIZKXPv4mBbm+ye'
    b'I8GlJ7ouOWOqPmvy5JlkuH6VIS5Dkt5ELn7mvDF5gCcMLZSuxc1hRT6ytgTApVRNFgMSPFk/jXJwWNa5KSkncgdbjy7sFU3GdPj1Us7T'
    b'rUcE6wQ8mTzddQ1ZcbGfhHf3xZNuPcL5NcqBc2d538qZT6UNz9DnzF0gTfI4itPTPN4Aw60hDeUQN1IKB7dC/DYBR3qC3BTrOZiSN/Qd'
    b'kZSU92zSiN6RrraklLR2TjY9K07slZbuN9hUCWPco+9uptVPCnBN03PEJ++I/f9R/fr369evT5IhGU85dYGk7/XPT50ZjK+nif3Q5Nnf'
    b'uIV6TFz8qAzCnyakEiELLCdr4cLMhV4hNjXb1c1W/UPjiQgor+Jq8h/aXD1u2bNmzpJt5kJsjhj6+ISps+alZ4tGhiVz7qSpMFIzRZt1'
    b'NzZvjGFEVJ/e4soNQnYj++XnTpgX3KfnYuKQNVdDVurgtJiF0+KsyXq5qmNQDl+AbyQd0CL9ndzO+WZ7uvmYeXdxsK3JNEl8NoD7t06f'
    b'B1co/3vBcAlQSL5G3jRvSnYL4Akj4HZJ60X4WC912LNKcbfH9WvXlVKLhVj2tVa7rJzIqNA9ghcQPVw5T48uOifteQUwPjqe96oBiXgS'
    b'wTipaP2v2n6XhbNgXBdK14pLHMZ7fP3pmY8q8z4tL4eX50lfmYTt5HaHZ4onOstnmweA0nvEs6TnJzcvv6ivuCNoVF9D5tR2zoVXkC+t'
    b'5hq+QBzdeePxojzuuTTrnMNZJ5Av5hVJj97xWFA0wpA8jxzLa3O57Xv2uLhHh4/71bwsCTtyYDKet3BheiaJm/R50yeNf/zxoRhRCz1C'
    b'bFb2iAewm63V2nwPwrzi1XsFKDuvSPu49V+4cObctLS5YGmZcb2kLT779sMVsv1HwGgMTnz8lzPnLczKXrQoOzsrkzAYGBgZX9yx799m'
    b'pWLW7DZ8igbiydwgbNaC8djJmZAg716geRTv28JZs7LiJQd7QRmfNX1WZrwcChi17Zxx3oTcZ6NkIj5hXpuDbpbue7CtTdbLD3Ui0SVf'
    b'81wci1nSv6fnSPMoPkAgJmc6vjh/TL7DyTG4AcE6l60ntraULCSGn0tKgZvMaCHKSTevpcTduocbOYSPjOFib1uPKK2T0einT5d+69xZ'
    b'0/VxOqcusofv2p4InZPB8fEZfHLJ8NqCceJKNwzbURmzXEen66W15xptrieGTm93eKZ75I8pC1xDjNvN5OWkpoxJTU1JETU1UWdJbWfA'
    b'Z2WMIp3RRHJdMBlsunxVpK6TNXdy5jj3OzJnBb778lYsriXPUSMMY+bNTcOJL/Ihst1T9kx/l+LGBGLg/fMwGjIz0zMJhmSmz5s19ZeP'
    b'D4aQwUfa9cOFl+IegL3iMsX4Sps7cyGRY7Gb7dud9wxQDuy9B7bzuNzj9jgMILG07BE9H+jSZvsgXL8mAgziS3ziL2emLYARXIQAk40A'
    b'swA+moZdoGiz5/nYFOnZBZL1TcrPTV0wLyibrtcqxcdnyLsXQFYaEz8uc/aCeaLYKcoqspohrhWY1c4ZF0zwkAqnzPc5mNrOwbY2Syo+'
    b'idP1dL/vcYEOrmEflSl9qxbHBhqbYT3wBJUUYCYl09RLWAYXE1PMGy7lxJtpdA+3xUbrZ+HoYM7T7eFwI68ZFp+RI17C7Nk5OTE6Cx/e'
    b'w4eePBzBtALwtDM400UmiMM4PNN1IwEUcfyxEWm2V5b3q3aHJy3LrXCnuG743PS83NQxafMWLFgwf8G8CflSzQdAZ0Igp0DNZNYo1xZb'
    b'8SIfmD1LL2L1fwMn0cIrWq2crmUGuqT5U3KL+rjnNrFqHdnfMAWOzQRChTv59R1p8HbP2aJfE/+GMQIGkpWdTWbXzHkzf+mLIH424n6g'
    b'54jsNPFcM7N/KXezHd95L6L8wL0DlL07UEgpwh63eOn7pmXH9ew5QnrUkrjFcITfRy31dROYeOAvafPSsyR8ycpMR3yZlybbvHlP5Rjy'
    b'8TmkfXHfxRFJ+Yb0KUHiCYQMed5jfr6BNFTVvaATpa+YnMmuTqdYJTjTAhFeSL2z3TMSQJGLmTPbOfjMzA4BZZ5eKlzWndXE6Gf5x5No'
    b't4SiEd+TPsZgdcayklYi4QkwklLy4J0ShgZWoqbZm61tyYkkrGqdupic2fNmY84T3r1HBGvFZX26OP2CWfNmZ+TkxOtinUJ4N2846R4Z'
    b'zjlpTU47Y79ggVwURt7nApS5OdgNepbsOwLIfcOtCLUPKJnuGnzKQvfrE6YskK9hYYrU/CaymAAnElMKzdNS1quNwSb3GLi+HKVU/Msj'
    b'UobrgbkBwB0AZeYzRb3dc1vkQxKCgCMsmJlryCsipYPcKfPc3gs5TCbJYQiCLEyb6UIQBBD/COKxD/fIkUkjevaMcwXYYKmbzVK9Y+/P'
    b'DVD27tzv6nFbhN60YB4ASkTRndbWVuctXIsoP0clEL5I+x96JkiEv8zLJPiCAAMMJnNe6vxc17Oo87JT56YvCNLEkJWXzOAjCXCNbx2m'
    b'NfoY5QsEZM5qldHRSp2oU6BUOKu9M2ZMMLjarbLT2hzMC3zQj8nVbFLymOfn8ucBnjwtERSDMk56z9z/dO6GhMcr3ykRWIblAVPWlqo5'
    b'nit22lh/5IQASpTOSSXkwImyMOd5mCQ8nNNp1Ome0ufoR8foYpc5OXfnPSE13aPCdUaB0uoXzAvyC+nlN87Wk5ItQcTpemnJAxEufjWr'
    b'vbGet9DdJZjqvuXp6RltBxxZzJgM/+fJiifP5FHKkitKoDqtJmf+bD0yJ4Io+bExc+QClXJSZsBrSltk6OvacJ/sR0MQhEweabm5ueiy'
    b'CxdmiQBCEGRemh8O4m8j80dcCEK20drTYLFabzlbW+8URQCgkPCat8jVzbZ/596fH6AApDTKPW5A3xYuhC/cs2eR0wojQcwJ49F6+7Y/'
    b'fCEj+0DPAPjS1yXADAX+siArK3Nh1qJFz8AtemrKwkwxRRKnRLCFgW0BARTXql7cj/pc3bkbkGAgPZCe5l4eo9XG1kn9E8rM9EAnTIf/'
    b'p2eluhvCs33fmTnG4+C8hR1Z+kJ3lxcEeJvjMLVqcSNNgid1QMvJKdOfWtTi5NiS9V4JTymD+z+qGaG0ZJqScwox4V26kW0I/Gxz0pWx'
    b'aidm4i/AnCcyXOA1ujKW/sTJ6WJidDEz9jgFXYRHD213gJMHdLzTodPEDNdnBf5ibsp1DgFFugdZ0zGWMWWLz5LFcMIFc4E3ZLYzPvPc'
    b'6xhmul+cO+Wp9EzfAUeGkur3XAty4vGxkTpdjEEqv0uP05iXid9f2qVafDQDLptZqnRdub+zLTTku6Y28tQMINUigiCAgJ8uAA6SGO8G'
    b'EP8IEiFtlOUHQW5jwLQ6nRA/Vggbq7MIGMoijK7MbLmbrXHnvYrwewwoe3fUyz1uGdnzMxYsQoZiMzstf7NYrAgskvnBF0vDHvcG6IHw'
    b'RUqQPATex2fOXgC3D8FFTJEgR0pfgBPE/Plk+hItQ7IsCFmyq8g5V08iMpRo/fz5+ngxWMk+Rzdw0Vo5WTM+P8OvpWcAfKVNSR1qcG1Q'
    b'kJWRDvwpI50cRcuc4D6YndGhZc3SuPrQR+Wk+/y69Nn66UDDZTzRavTi98qckmd1MNM84AQznlK1zraMoxUKmv+EXs6GhOP+kZFRUd38'
    b'lH67cK8C00ifn75AHxNrDAe+EqNbzIWHs85LsYAmdl4XHunZ09YtIlxBsbxw3engdLpRcB0Z6X6/0HwvUWi+/CJW6Mnz7wBBcl2tKrFK'
    b'5A2TM9MDDU96mhtQFpDhhV+7MBtTitR56TD06empi/JJVkS63adk+jsLfEeNeIulFnf5cRqT4fZl6LHN/SwukBYb3W88TTzAdU2yP6Fi'
    b'Mx+8bP68DEzLFy6c+9RchBFwP18EkR+m0sUvgojPaiI7eeJDhX0Q5NYtd8xYIYIsf2ustyFDWbQgY352htzNVr9j7z0FlI37dt4ze6ta'
    b'7nF7HL40AEqvIqeRNl7bUm/kTG9uP3T0aM35K43NFgCYAPhy2z++9PIjwDzgiS8IMIORvxB99xkZX7LQrZANiy4o7Tl4ztWQiNt1wPS5'
    b'IHMByhNAX84RfyIrelGcW5Dp37Lm5ooTk3tR/cK0tNRUYEzE4JdlZqW5tzbIysjsyHImiXuyYHPEpByfgxDtcZCI1bnwJCcrXbyQKQZH'
    b'C1PqqchivZihnWBmVqlglEzVkqUzOBb3lgzv5stRsGrMw/fM0uekZ43Xmlkbq8mN05nCH47QGVuv82LLiucnoiIjoyK7RIRrdZAY8boY'
    b'fc5C/19onquG8ykAijiSGXrcILyc7ARNngYqrofEDjOyujbggGdmeoxmJtzSuWkwpGm5RSOL8vMWZcDQp2XkviA+SBKf07TI/4kWkm67'
    b'ctda6LMEPCCBHJeTkZmelaNRzqkT93ABDzFIF+RCI3QjGHI5h0GOnJmRNvPxxI6EVPFpTG0RBJMYTwCREYT8bbE0/+3KZ0drjx+t3r9v'
    b'Z73A1uzbt89GGApM1o+7utneunfxvW8jAMqavffuF+7cvt/V47YIGEqXJH4JH0ZbTFZKddXZ9Oa2w43Xjh+r3L5jJ7C0iiNXr14+/+3f'
    b'fPDF6h9f7l6AAXyZTfDlGYnA4GoZ126KwHrJhmL5+QAoOMGRhEJehQWzk0Gj0Qf0bgCLpH4kdZa3/XlBJL7iRxbmZGXMS5P7wiEE0L0B'
    b'3dqx9JxRrrYNzTwfQEmHSyePISPpQb5Gk5OTLsHQFANKKOu8Kcr6Uppilwq//dMyJkyhY2KZWJbjeL5t7Rerxh+xOn3WON2j+iy9juJZ'
    b'zaOQ9L2ni+oRGa4Lj+jaZoNZSHm69+jRvXu3yAgt63TE6p7Sp/v9RvNzPWo4uWKAp5OG1LMIidI9KJcFLcg8XG/ztYyMhRkpHnwP7inu'
    b'zQawXhTZZ0SSlHUU9Xc3tqVlBRhlbI5xr5chD6QFuqIcjgNKhlkTm5f/Qr4hL1ar1CTo56d7AAgiCNzYIBAkoq0M0i6CiCQEqLzTVlNd'
    b'8b2xbOeWnTv/fODY8WtNx97cAfHyqo1VnPrGVCYIST1JaMndbPu338Pw3rvmXgMKmNzjNmIRAEoRFaYIC1OoVSEKmuaaKozg1sKuE+SN'
    b'a+wMbas8sHfHtj/jte6vPnL8/KVvG5vNfvElsADj5xmVAQTetJyM+bMnD4+PiZGelU3wRTkqi0xA4Ey6pXUSdcmPUWr1WeBMAWwugIW8'
    b'sT2ZE8lOriOLDGk5WVkZeWJqXe4i6ZlZGXPT0gKfDsBG/yjZOptUKn2Opeth6sy7QR6gis8f0+pz5FPlpOU7C9sAyrqSUhafJkpR8Acu'
    b'8WFjGa1W6bPliWjhdiZar49hWN0U+EurjdEBqPBcxMM9ukd17x5gg9mHu5Ht3CK0fCuvG65P9/eN0nPFfWckQJG+CaYc5/BRW3XiUMub'
    b'LJGNPuS3+QwNzgq5z8ibbfbJF58UaICBfqaoD+mbhrAd0U9ulMVu97k5/kcZeGD+Dfd6mXJAjqfnxMYoH80ROYh+tjjp4KwzPFdCkF+S'
    b'hrK/V0i9HQhBLMhBGq9cqD1WXbEfonTHjmMnaN5R7+QURqel+s8nygSe54zHETJebeTC1CqFQqEWekFkubrZ7m1s33tA2bFzx7ZLco/b'
    b'M8BQbKdMRiOlYNG/2aYmNiQsLExlOoBjVOygVUbjLtPXX+/fgbZ9G9rWbdv+vEPGl/or/vElkMDrIcC0lyBB5D/+5JPYyZw+f/bw7Gee'
    b'kQjMcC3ZCDU2Fp+VHqNHUpGV498yyYOy3Y+EiZLbJKfAwQzDCPG39BWbJfuL9MWg9382CVBi3LsXeL0RovBRpfYFST5BtQGQznUUAGWl'
    b'L6DAT2uxcEwWCvIw9HTBbWd5rk5oCyhi1Viv1526w+uigTLomFN3BJ24uLjHw/7RxL1FZLdwxiloR+kz/Q2R5/KY3HTxu0jdHudcOpYL'
    b'UEjhR3qbz3nEBndpO/Co3v2wPbU3EJWszEWGPuKGs+4HEPSOikxCWA9w42YrY58my2VIz4Dc7h4tMhD0hFz97OHYjyo9zrCf/w3BfWSQ'
    b'gEKq1eqLIN9eOo8IshcRZDvx923btpMAeLemrEyt4DhWEUZTtKnSpIJgCeNsa3a+uab4GB/GsBwvGIGhPCN3s13aBgF37wFlx721rUfF'
    b'Hrcu/UZ0GcmqKZpRq3AkTlnWOGiFwHNczY4d21atKbTRYQC5KiVjW9P2LG8juKBte3vHDkiQ3n23oqLZabnS/DdPfTdIAcZ3OpEJjBd/'
    b'WTBfnzs7Ris+hfLRZ/RZ2RjrJFcRyYCX4dbJXg+Y6i0+NAYBJYtsgxopb6wc1UesLRblpWX7dXJ9TjYJtbPy4lxPQMnKyo1WxtyQ5ROd'
    b'MiY30304+ymD88s2gLJOfOYo6W7DlYKsmnVaDUA9uvRoWzV2aIdn62P4O3dOscKpU9ztO3e4eO0JXVSPhzu0bj26R+gAUfxGb5ZXUThL'
    b'ei1e84K85YeXAby43+Zp2XPzisT+9igP7I6K7GNYlJWjN/SN6i0/lkdaa9w7KT/LP2ijpIYrF13LZWKGT09Px1XceuQgHqUYvzl1OzII'
    b'Tm1thVRUUpu/vVR7pOpw9YG9e4lTE5fehk7ta6vsLIQDMHoFMkvGVFkWRguCsWbv29uO22zOXQrjbbvN8lKviBH9uojdbEe33uPQvj+A'
    b'smPrAanHrVdEkcAwtDoMH/CuUO/aaqMo57FrjZDlHLeZrzkpCncYZPjGTQHPtdOFLzuu2Y200LLpmpEzbd9yoPrY6fpLX/w1OAHG4wm6'
    b'HXTYEX0XCMzjj8/MyMrJJrMWyZ3BXI4Jf2Ub+vo8ApMsBMC5EWKAoE0b+jLS4B9QsidNBq/OjXGHX674m8QQ1GPTxFkx3TFoNJO96ED2'
    b'XAOp8vgAitx8T15eu7aUV3POmzEzuIg2gNI11gx4oB/F3HFbrF63hOvSo9vDQViPCF0rp/PHvXwhkoycfpS8171LyJCbgm7cnKPR+xmd'
    b'jLxnPfrbpc1PMK95Bm6QoU9klHv8caT7FRlc9MQ1EeAqskXSzRQXlD35JHkeavtC6iPupzaKFKQ9GcSJDMTS3NR45XjF0SPvAgXZWi+w'
    b'J/YdOFbfssMfgviGTb3AG40WYxhrN5kE0/l9ZWGc49i+bTu2XBJYCCOIIggjrl9EL6mb7cC2Hf8SgLJ9x7YdZtLj1mUEz/K8iVZfvfr1'
    b'1VOn7Hu/UzG3Tti2b9l2zMhynKCmb31vdzqb3gzipNtPcBwXRn9dZqGUqO++tW3bljXHj23Z9hZyviNfnzp5tP7Kt38z+6kgeeHL3XfY'
    b'jRiBDTBpGaQ+LeHLokX5I/uL1Nv9lG58wHHeXAAePT5KxusJmeRHcrCN5eijRdqt1LqbYNPB5XOBuMDRSaRajHhy7sYcpVafnS6RpWwM'
    b'Ewg3s5OZ5tUo2xZY1pZw6gLnHLbtCr/uEdwyLfwifQznwhMuJpdsqOTObHoEBhdcm9wKSZN4Na4v5Upv5CROL34j/XSloa7Oc+MPCVDy'
    b'INPUavQ5bQcoM7eo90O9vUYSx7Z3UW5mdo7B/YxScZPhpPy8jByXikruFlxb1gKfYq7fWm7gfrL2ZJArlluWqv37PxbK9m4B7rFly5p6'
    b'2/6tb721ffsaGxu2y2QUeL4mqLj5HnUvNdJ2RRhj21Gm4Owm26WNxXYGwISiaYZhw9j+XXqJ3Ww7t+3Yfl8AZef2e25vbfkWAHtkRBIh'
    b'cSGQ18CAUGyzCXiKmjlVXWzmwgi9wwNc05pgzvkxJX5CEQKUkDPDZ95o4oXaN/EYDDllr6zct2PLlm3w4869FdVHa+uvNDaZ26lQ363A'
    b'29ergIRl43wwSO6fFT8Mn+4DmIGRZIhq8wxvAJ6kvAw/DCVbr4nNJ8rgHAlQYsRV7No43FPJVS0+W1cXo4zJywUj0SlGLSBOi3MGExhQ'
    b'XK1udOtSVvAFlG7dI4TFWiBE+tFuisLH6LNInUekIN0f7tate/d2EqBwI2CS5zdDHET8GKdxycyzxz0aExMdo9fPV+bVvZDv3vhjzqfS'
    b'/gUog8br/aVO4ooZ8lRXD+yOKgLkyMLdhZ9NwtEnRMKQb8jNXgRnyViApZgR7QqpPYPqJ/MjpH576fzRI1X7d2JkbXnr2Mc057zm5BSC'
    b's6kaXtl4jWdN+7aTf3FhKKQq1KbKNzt08Df31dA06gO8YDSduvp9vRGZPSU0FdoZVbPFZsdOABU7oovYzfbmvQ/r7TsRUFbveOs+2GZc'
    b'LJjUr+iEnVMwRo5DzsY0fsizLB1GWYptrKLMKAiY8IQxjuIgTvinGuA4pqu0guPgVKxt9fZiGwen2ogHUd+F21BmOrGfvHnrli1bNm/e'
    b'vHHzFpwpduw9EABfCMS038HbbgGJpEdPPvmsuBQA8SUXp8TcfOnTmPm7Q+DZvEw/DCUbH2MnVjykXqtyUnnA+RoPxtz4vyKe5GtDlFht'
    b'xdw/fvh8vfTxrJccLVTp+vXtIQouPFYvL4gV2jKU8E9YXa4+OzeevTNgANl3mr+l0+fKOU+P7l0jwrXa8IjAkkqPrjpCUTy/kj599rj4'
    b'GGnlEe5bJdZNcHNFjVsKhS+jdPe+IVL6G5+cXBGfo8haGVen+7P5uUhBFj3jWoiR92zSyHb7yVyPnveUQdoiiI+OajY3fnup9ujhin07'
    b'MZS2bNm0afNmcLCtxC0rgIGoseigCKPUVM2ObVv2fqwKE45tfGtjcUElH8Zw5EnBwcRMhQnOJajVpECnpptN4OeMQiFUmlmFxXJilxG4'
    b'joKBaRoXA265H1G9YzUASvGObffDNr2L0mxRKxcmqtMm2y3bO1uu2ZqcbAh/zMaocXd23KNdxdqKgzjf6iYGSA6tUhCp27b9rVX1gkpB'
    b'w2c3FhcXiPquQsF4nWu79Dfiy6ZNm9Zs2rIVFfWde995p8luOd+INMrSAX/psIMXqHLPBx7o5dkAk/isjC/55MnhEjoBR5fyeY/NYfT6'
    b'HM3Tn5Z7VjzE3oibkCdkw8G8OnkX2TlzyIOPpd28IITJxzMMuBtKaYcUhWbqY43hPoDSo1u4nYnJjE/Xx7C4h/2dO78YcOeWbtxsKefp'
    b'HhnOGMHNy3ht18CIEn59hi5X/jrAnfSTJcjQiksZ68rzxH5CQA39uJiYhHGz0+HdgCB57v0LonORrWWL5Msrd9Lnj5QeMyqOab74mMAc'
    b'mYPILe2+pT1/Qqp/GeSWJ4I0253N9bXVFXsP7CVlmC3gOGBbtmz145bFdpZUFsIUmJKwph3wCoAAX79mSz1wijIsAH9v+jqYGMTMBjg4'
    b'SiUUZDfcmZ02u80pQPJzjQsh+gkauwfl2Hc33Zeg3lF8/wBl26adFustgQpRU2qSqYTRTat2FBQgarPX7HQISQk5nlewTauCON0aOypT'
    b'apgGYGTVu95e82eLmqZoe/GW0zbbNSdF25Dv8NfWdHyqrX9uchgpoWXDNYEt27lm5/6KXfurar+9mw7ewAmSKPC65byRTz4rTaHAxiUF'
    b'xiNlgXBJhyTAc4WR+DQvos1mw8GldfIDBW947TcKiYqIR7ktjqNqDh/i1R6glEyjKmPLfLddI1VjXSyr01IsPg9D3HSaoqhROhPkPD26'
    b'ao27GKBFGtaiDcRRIG3i9mj1LjwBuhOjBAQhy2RcEIn/RkDJ1ue63pedSXrf8OtiZTknWx6THOlkkgqCbT24VubJx+PjPHXUdoTUYPvJ'
    b'iJLa3Hilpmp/RfV+LOSuqeeZE5WVx65d27GlY1/acsQomE6hkmo1GnnjpY2vHhcUnIK7VnyNByZNhagQCLhrQbj4puMCbxQUjNNqt9st'
    b'JtvOTQUFhQXNCtq+VwB6z+JMWsaxrXDJO+8PntxfQNm2dWNzmULJOe3YqIPK1LGd39ubjjnZMP4YjDawOrUaMTcoEFjTyDEcZ6TUp1Df'
    b'tdh2FttplU3NOAqOCTDWvIq2mCDNvLYlmCs7wbJsGGU0nlKrTtkb39x0oMluO75qwxb48Pbt1adMNRVHzrfpgPHBl2CXUKPW90AvT4E3'
    b'8ZcZWKmUguWZZ9KVL0gPDXctMTorPkQBom+20uB6sILHjujnxKPEsl5wODkl7mi/fr1Hbcfb1q4vVT+HgOKz03SkzqlhnM7PaSXtFmWB'
    b'Cop1nofDry9R6kbl6OdrWGPbPSBdJ2Ec2tl6N6Do4zXS93FDJPlKCCge3AygJxof61z3KemSzV7kGpNnFmGX0JO4MleUQQJUYiL+rn4y'
    b'c3Pj+b/ZLDtf/XMNbzwA9LX47Ws227FVhIKssrFhxjLsbjC9HUyMfU082UWQV9kpyhLGNRWgkkpRDMyarCI4Er5lr82iRi6iRrHQWFlh'
    b'q6+0nQhjEFBu8azzazV7mwnhnVe2bt32LwgoW7dt3fSBAKHL8ozC+HWz3V5tY2iOZxVqywYbwzn5UzZBMAmssXJLxwO0CpIklQr1XdRx'
    b'1cyHcNsFi4KxFzSxYRIbVKmB7AQz1idolUrSdyFjtR0sA+7DW3ZsxS6BQgdDOY8fq9y3dcMmuHE7ZAHm26bmuxR421tC7SHwPh6vjH2a'
    b'pARy86j4KGMyZ+vHkU7xs14EhjSkkMlepCh5NyHpUXBkAxSp+aRtFXldqXpGbFmbx412ZR0Kfgn1npNRshKeGHWUWis9OEPrpGLySH1G'
    b'+5W2WwCKQvbNH673sOFibdgTTNBuSLQqJ0faI1UPgPLf+YaleXPmaLW5mU/+8nE5ifnHFua2QZCmxiv1tUerIYnZgZ0gG7bWX6U4J6Tf'
    b'CsF+uXqTzcQxrNBEJrYN1zgRHdSmvR1PT1vfPoHsQa0WjKarp059/OcmmD1PAeteZmNUNrvdAXm9U80EBSibmozqMCDuCjUHZOREZRnL'
    b'C7w6TKi002HNbAh3iwoTblEK045N27beT0B5e+v9sS1bt6wBGFC7yjm8ncMfKOOBJi6ENYUxrbTKbgJQKN7S8bl2XrgMTIc5RYRcmrXz'
    b'YZyjDKB/mY1VnSgDugmvA5gXB3FdG9+/eurrU1ZaQU7F2QVwHlUYY9mARwsdtIIjAu+BLai9bNm8adPrG9Agjd761ls791UcOVp/6Uqj'
    b'2dyRwBvsEurw8HBJtNSSh8eJS4zqtLq8Z3If1dRJTxyv+5+zHgTGA1D0OfmOm04mjMYNUIitX7fWD6BQLGv0AQXIVhYvU8YK4VqhldMw'
    b't8Qaz1PDdTq9XvuxrlskY9VmilRCJ8RGtgsouR6AMtu1YObs2f9xV4mBhuQREpIrcZCMJ2OUpNEdhuCRvv/Iwty2Dakygry1DW4huYGv'
    b'b9qEYuqWrZveLcNIBfYQhkqqqZkFD4DEpLF465pCkpNjocVUvbVDv4RTIfnmVCpIb9RqJd3UrGIc4NPOAhur+P5yGTmqYByFHZ+quIkL'
    b'UxtbW+9Q9B27rdn0oQmjRc1fO86HMHaLgnIKKnBWtXB0w5b7FNJvE0B5a8t9sze2N35/wgSDSso8QmWjpcxoslXuM4bRVhulsvMhbCut'
    b'MO3bGMSprtlZou+iwGu3myDHOWEM45zFdkbtxHkAZgLUd4O4quImRqlW08BQMS21vbWLMzbbmDDh6MY1hcXLLG591/NDb8rXsXHjRnDO'
    b'NWs2bNy85c23tu/cvr3R3nz+2yvtCLxBLKGOQAuXjeCL8kGIoWgl4MsMaY10nXuJdJ0mJtetWvw/QBReGabGkgJaaak/QIlljbo2gGLk'
    b'tLoTuq7hXOsyreYq8hNR5MA6T9cuXLFWBAq/ffsBASVdaXBxrXPlL4gLZmJjdBrtk1IS41ZS8Yv3dBORiGAX5rYRUs8frdq/fd9OrMPA'
    b'LYIbtGHDxo1v+HUAuNsKlQryFBpTEpONYXY1mVTAnDdeA05hVAjOj01G044g3LLQpaRSRBN0MirL30wK2mg0o5IqUmclayvs+FRrLvEM'
    b'ljAZmHNhGlYZ608IgtFyrbheoMu2XuK4+qpTFze+9/3xjfctnt+634CyZfPGLW/tQ4XLbLM5jm9cvaGyct+aNdtNrHGHjaW/bgaqYQwL'
    b'BgberOGpEIoGJkH0XbtIS8OU9C4HHUKJN5OD1DUYQFljN3IsS4XhnALE9k/bm7Y+3wiMp6W43m43OynaidOKUL8h8NWASV9wmyjwrkaB'
    b'd/ua7ftwK9+jIn/pGF/kBMnVwdsVzIUvPbFK4QYYjbxEGhOkfM2juWSif4aEe4u1xengKAUulYKRUbNtV/eIgOKjrOJjSGNisOEtnLE7'
    b'Gfb2nVMxEoLEM8YIhBsZUJa1CyjUOBFKCP/IfUYTOyNWKklpZAqC5kcH6eku5t6VkPq3K7VVFVUVBEFkIbWl5a2NvnfIj22sMBpPESX1'
    b'qiBwwqXVFtuffuukFd9gTNM0AA0AQRh3LQhn2nDEKHyMSioKqUbB9jHhOnAP+CaB+CTPG7/mGNvqIPxydaMN/BGmOrFeYdq69dixyo3F'
    b'b204Ztu7eWPTtY1vIMS9tWHLvy6gAMPchDP6mtXFxcWFGxBgNsKYbHrbdmD19o+b9+5sbtyKuliHmLthXxmQv1ZnK68wfWwUhNNlkK5g'
    b'SwtjuoY+IAm8fP2azUEQFI5mWZ5Sl3399dVTVy07N7wJyS4dVvZ2JfEBBW0yftxsuxTUjdtc4yXwbnltwzW77djy1Rs2YK/CgROmmv2H'
    b'jrdZ43jLZwn1LW8BBvHFuwOmLYFRosA7OPHxJ3Mgihfl3XRaHU5ni8DFMoyOpsKYknVtNl1i2QLGG1B6dNPadTF68ljjLpD28Ax/J1am'
    b'GdqPtVhTlpiH7vOAq3t6YGaEMILqyJOkmBuudF1sRITEQWSw/PsW5pqbvq39m82y/dUt4DD7IAFdvrLFZqss3oxW3OQSUrcGcdM2bj2B'
    b'HkMmJ4WSsS1fs8YGeQptW+ZgXLOTIji6u3Gr45RaquqGKYwfM1g9VlG88ZJA2zjGeUrFtrIhXBDn2rxl9S6TCTzPZnc4bLZr2yFTWwM0'
    b'ePOWDcUQIMWrcXrG/zZvvr+AsnXTj88KN2zatGHVBvjv9a3X3t7Q8Qc2HDayeJ8ZhWA60Wx7b0f9tWtOLszoeNVGs07u6i2Bv2pkjZVB'
    b'nGq5hYX7T/RdVHaYxtdNMCtBrlrQxLpYqoJtKgzmi2w+QSs9BN6mNy08CrzimAMfppzHKvftfn0FSjBbtxGF9/il9itIvvjiTpBcIYkh'
    b'6rOEushhvWnFvh5iz2Grmw+gKHnWN21BbkEPz9PhIp8eUeGM0wEoPUrmJPxiYB5iKpM7PNYeSJTt1iOCe1XjTmJQKMIcRkaQnq5ukP7t'
    b'Lcz1RZDmpm+v1B8/8u6BHdgK8jp4yjEUUq8RIfXjd1dcs3AMa7y2Cgd6lVtIDcaZXt/6MfqSWl1mwjnFtH+riaFVlKWywMao7A5iqKQG'
    b'4wFrmgRIj2lGQfG8UHZ5L6CBzammnIUwRVlQSaXDBCelKNuxIRh3evvtzRtWLS8sKCwsLn79xxe2W3+0gOJpxWuCeddqC+MKdpWaP11Q'
    b'XHCNVRhfARDgiL6rsO1SMPZgfODNSxYnTEC3jETgZS8BoFAKtXCpwMaqmiWBN8hTbdrwnizw4jYBnO0EFYYCbzPxc7fAu1fyZMjrX3ll'
    b'1YpXCL5s3b5337tHjuMSpObAAm9AAcZH4C1ymiFRuGkm5ru8B/tQFJUcz/oACnKL7Nxx+BTSbj26d9HyzspYoCzY3Z87nOLrGW0upjC5'
    b'ubpiPiLQgp7u4WVceFc/xVz3sjrvhbl+hVRzc+OVS6eJjioiyCurVr3yyitEDceBPuAtpF7j1Zhc8NeKN60qWOYWUoO6aYfJrVeoRGZL'
    b'N202IWFhvik0swqTySgeZRwFQcyMFi5Mbbp9+w5F37Y0m4zVgAbLGhnmYj0fwtosKuqWUc3ZBLVwbFVQV7bhRx2qPw1ACdL+3Gz53xOm'
    b'MlLOYQSkIn82lZkqjWG03UYpbEII08qEARkOYoK6ZmNDwqRWoav2TasO2G0WmEQ22Bm1WOgT9d2g0LDRS+Bdc4blm210GFClVQWFzze5'
    b'BF5PdCJtu+RCXkd8wcAhJaRtO7a9+b/W5tq7FXhRgOnVrwWu2gHvxunVbPdZ3oO7QiqdHOkt8QSULmyVNlefq8WNDbph36xOaK1ndTHj'
    b'AFPyhms12mx9NmQxcbrFtwJXjbE5LuKRNj3tHS2ra7Y7/1Z7pHr/9r07tm5FsH1lxSoCIK+7xmmLR+R6CancLhtLGS1lCspWvMZTSA2G'
    b'oGwiSqoagEnMbvj3XznY3Aw+wV6r5zx6EIJhKKuO8wzWCmmFuKSeOODOy3/ZfkxgTJvref74u99feuWw5diGn0MM/owAZeOmDcWrN2x9'
    b'e1/lsXpsQsL7s2HLvo2bTFzZ1iaW/ryZZm1GRRBOsGGLiVOHoOyCC7fC6MbVBwqff+4aH8YdI71IRBFjUaIN5rpWeQm8uzZvstUXNnFh'
    b'/LHi43Z7Ewq8AIGccHx1O+cgYYNS05uNROBdgQLvtuKtO/ZVHKo6eiWQAOO1hPpQg8PBMc85AVOAoFiRoXg/+atUrWud4bN/gbihbB5A'
    b'h+4TfBY6edyOTnA6+Fhd9IMPii2pvXpGRABz0XXpEXC5MfcnqqOFuSikmv/27ZXPDlVUHdi7HaACQ7EGbmfLtS0b4Mu7BiLQbTtgNH59'
    b'ygK3WBRSi6/ZjkFaoW4qRiGVcgupG4PgAQd2GS2ikmoBNtK8dXVhYUGxRUHb1xhZUkfkyywsY1u1qeOTwXWoVVKNB7DJtHUj8oxXNqyu'
    b'tO3csOba8Q0btqxGETGIU/1EAKVw84afja1ZvXp1cXFhYeFK8WfUPpt2rtxy0bZje3PTBpNQtmN1R+dYva9MpRZuO+/wilMWoLfVu8rs'
    b'thYnEyZU1vMw+VGiwMYfLw7iggobZYH31FUUeLdvKCxeZmcUps2ywFtmPHHVVr86qK/nJfBeW/ManOxaZeHKlavx4/tOmGr2Vh2tFdc4'
    b'tsEXu2MZzVD0jHqUUByxPk/qWVvChfDOxZz3/gXduoebuHDMTDRG+UHpACla7rrTujRW96Coqj6o+zfndV1EoKU8PbppnAx7x08t19Lc'
    b'dOV4o83y5po1Jt64d+XKlcUrCypbNqxe/RoOXYtLSA3GQ9dsdgupuCdXITqCTU3Zf2tnQsRZAIVUc2EwA736dZtRFSI2aitUxn2X7C3H'
    b'HbhqplKgbBztNCkYoqQGc7LlZTUfN2MLm8PW0nLM/VVWF8K3LAQnWvPzib/NhT8zQPEb0xBtK+GP4sING49uDSJyV1eUMeh/tII3lp34'
    b'+uQuNcWyTBjVvBr1XfZrp8BbUN8NBgQKmySBF/0cBd7izYXHwB1tz3sJvMG5+QafDt7CwuMWIDcieBY4iMD79u7Xlq8mNaS3dh6oJAUk'
    b'aQ21cyljLGVpnCoZiuE9n9RDFhurHY42+xd0D7czqH50DXfvf9Kje1REuI4rc7Y67e+9WvzqNafzOhsecGlgtx7hXDHlsbK//mh1xb7t'
    b'W8DrXnul+PVjzRTrbCFC6okKGC8bz50Qv2xxvUtIDeauvbb5hCikmkxfX0UhdfXGwnohjL/2vI+QGsQ4v7amkYc8lGEVlCCUnTh/DZd1'
    b'sAqFsM9OKyxcCOukw3j4z7gvqIlg8xurlxcWFMA8V1j88461fwlA8bTg7ufKZkbtFnh5yMaBtDKmHW59txn+sgcFAltQ4A1zC7yrCyst'
    b'arVls0vglRolg5o3D6PAa5cF3qYCi5EKYewFEqCgwMsbjaa9UlQAWyOT/krw+o0bWhxm9bSSklKeY/ChgT4KSikbwjscgs9yY6J+PEIK'
    b'1OGfuHbEx+2no/AxGbHcYp7nuVhdeES3wHjSReekuKYNW97YCJe0shiuBxjVa6+RL+QjpG4utnNhqprNMGcXFzwvC6k1VUHdtGofIRUy'
    b'YCQohb5CajDTgI0NoSy3sSe19YTJKFh4cAYVLRy/hEoqnpUoqZRQWbyh0/6VASU4e+VNm00UeNEJjftsto9N39ne2mcEzkv03TCi7wbl'
    b'Ta+02BgPgXdN4THIV0yVxQWiwCs38AYFKIUeAi8n2CCdUlBAdgow/Ap+20STzXrCyAtu2yj+teKo1clRpWvX4hayJSVrvQWUEiGMdt50'
    b'lPksN8YNZeldVuywi8XnGrtQ4mHc0j6qq9j+0jWqe4/AeNJV62TolkKipnpcjwiCnkIqy5k2NDIKtcK0ddWGVfUOIqTeQiE1GIKyocBH'
    b'SD28uhCgt6xyVSHuYuQWUoMBlFWVAu6aTlMKUYI1Nn1dVnbCdqwQXje9cpoXju1vvlT8ruXwis5g8QMor7/Sad72X4WFy//r9a1vV1a2'
    b'tDRVrigofH3zKwUrXqnhTK8A+/24kSH6blNBhydascFH4H2+vkylMO59/pVlDrLYVBZ4C4O5rOUeAq9Svev3jSxjIZex4pjd3uISeI8t'
    b'9/PZVVsh6aEZQBJcIbjOO98pMaoVhxxWq8CYvAGla6yZthKB9xZ9zKtxDTEFn76DD9JoZ/N7wBMgeK8Ur1j+++Ur2g7PXmPZVakjFVuP'
    b'V3yt5riwsrdXFHoLqcGMzh/2uoTUqyikvr7MDgNb/9vlK/ahkMrLQuryoEa63qJ2C6mC6Q+v7N79esHy1/9Qadu2YtWxyhUrVyx/ZcXy'
    b'P3SGire93gkogW3VihUrli8vLFxB/k1eanz7Dxsu2bZusTStOCiYtq7sGFDeJgJvqyzw7q00qimns6Xl7YJrngLvsWDc/MVG1kvgfXv5'
    b'NbuAYLRCFniNxhPf246v8H8p9VZHsZor8d2/YP1axJMQ3nnTuu85Zpfn/gX4GFKBbm22WK2WVgisto0m3dDa2/Me8p0ZVOXNlte/bGmp'
    b'bHthr5+g1R5C6rKdXztZoH4rSEeqS0hteTGY+7XiNUB5t5D6Oi6WuG2zNa055i2kFgRzsj+885cmsSG1peVYJUQIOAP5JTCvvNIJJJ2A'
    b'8k+w1a+8guCyvGDl6sLC1RsqX18ZjJfvN8kCr1BW81VVE/AVXG9WttlGEYGX520o8Bav7vhcboE3TBR4l+PCV66+sLDFq4O3YLX/qzdb'
    b'nSyFxZ21MqLg9tRr15cK6pAZTrPDXLlY996DHmoIbii7RzejsrJ409uHl9HXA3aaBHoqT1Q4xepCdIyOKWRpakZlsc9FrXxN6kg1AUSi'
    b'kLq8sJ4L4yEh9BZSg8GAlau+9RRSv9hnxAZVmmI+sFNeQuqO4mDu9cpXVhQWLFtGpFTvm7Pa5+9O8wWUDas77e6tMMi3NTFqaaMoFHgt'
    b'DE1CX7AxssB7FQXegmDOtaaeCLxOSeCtX17YIoWfp8BrC3Cu4n1Wq51iS9aXlIhboiCarF1XamTDFEucVqd5cSxb6fQEjW49IrDZnhFa'
    b'VhcWtDCLOaAo3XsE9/QMfMhXhJanMGlQs5ROzdO6Ft8xK35XlEoVspBaWHiMD+OPFxY0sQrTLtx0iwipy4IYHFwX4S2kQr4EaQtj57Al'
    b'FYVUShRSCzud94eyDZ2A8nfaSum/Dt+2co3Z1tzoEniPNYF9bCpr8hF49wXh5StXtljcAu8pe/HqAgAUoXI5EXhtssBrLghwKcUtVoeg'
    b'Ll1faiwtKREZSkmpkVeHqJc5HWY+lqt38rqIh71YCD5LVGDY1yoLK5fqrod37xmODzPu4ImBD4uPIQ1nnZySOWWiqTunwug7XFtAWWbz'
    b'EVKXL68kSRx+MbeQ2hQM3C6XhdSwMALfxm/Kdn3cZLE1HTayppVHeeHwzub6wgpL5fJg72+n/Z2A8trKTvvh7I+/+13hH1/bvHV3JcoI'
    b'L/+ugPy0spo3/fEax5xoZFgLEXg7PNHy19wCr0oRRl97cWVBCxtWtnv589JzWSSBN9Cp/vgG7txGl5YwNCeQx5AKAqsOUbAOh3Uxu9jh'
    b'5LQRkd7bOHaHrEV33ckxi78s/FInsF0jGFYb3iVKkmL9wAoRa7t36xqh5Ww8RS3RsKySFowUK3B0S6HPFb280yQKqVZRSH1t5fLdxjC2'
    b'pQD+8hRSC4MZ6MJjFkqWuVFIfW3r5tf+WAjjXWnb8sfiY5Uv/3F54crlhS93uuQPZ691Aso9suUo7xYULJd/Wrny2paXV9fbtm60NC4/'
    b'aNy1+Y8dn2K3S+D9GgXeAy+vLrBhz23x70gHLz5aQQVZ1bGA4be80mq1qaeVAM0JU1LwdmVIiJI56rRa2RlOG6uNiAKUkCvA3UTr0b2r'
    b'hnXWx8burpzBmMK7cK1lAqcLj+gS2U2s8PhY9+7dorpEaGOF60toiqt0APGgaJ45xTF8W0BZufyPREiVuIhx9/Llu00K1lZQeEygLJ5C'
    b'ajBj/GKZW0itrBRHmfySAhjcFws7nbATUH7GtgLB5cVlf1hRULBiVeVry4MBpQNugddo+qrmlRXPO2jFideXr/QSePctXxHgV65c0WJ1'
    b'LlGXlqoXs7RaqVRTzBIrZDuO52IdTHgEIARwju6+ho8nXuZkuMrdOmNs+Iyjah0rGAUuVhsOsNI1Mqqby6Iiu0ZgwxsnfCzEUgAnXy5r'
    b'YVieok8p7jC0QH3pG9R/KPYSUq/914rlm0+EMY7nC3yE1LeDGJ8VK/+w8uWCguefX1aAUuoK72Oddu8ABUtinXY/rTDItzXJdWYi8B4v'
    b'WGZjqK//AC97CbzLAp5g+WbrTaeOhgTktrgnphPgxOpw8Eyj9sEHH8T/Hnww3MPEzY8iwpWXFjMtlRyzL4S9RM9gKEqHPaxGnmPFXdfw'
    b'w7jdLbtYKAMGA29g+JYvlxdCTqamdBStADak1n3p+z09hdQak1EwwWtf0aztt9d4XyG100l+CvYKAkoB8vFO+ynYqiZb87cugXd34fI1'
    b'NSd2Fvh28O4uCHiCwkqH9ahaYCk74ojVin86WvYtp9lXjf6MbEAr8Lxgo9kvC16n/8QW8PTNlt2AGZBh6SCfWYyb1Epv5RdzseR1dmll'
    b'y25I8Ja/vHJZbOxzS2OXzli6dMaylW0vhwiplEtI3Vq4/J0vTm94cZ+RNb18WBDe3dlc/7v9lsrCznv/k7CVBZ2A8lOyl59/nmi6u7GF'
    b'dx9E2csvL395+fIq3vQyCrzfMmwzCrzPt3MKSHo4YDkOq9jl4bACnBTsfk5H+RgtmQ6NYSjd7sKCSo7iOfWMyucLt37Z0vJHYTFLtpN0'
    b'fwbeyS55bnfLl/BmCQNWtrS8trtld+Xu3ZV+/KzAR0j9I0pNLy5f/uJu28aXC49Vvvj7wgLgOS923vpOQOm0H8hw0WpBQcEyj1n72sYX'
    b'i+ttr6+yXCs8aNy1oZ35vPBPVvKMHqe1Be1o5RuF8O7CzV+uLCxY9tvfPoeGpGQpsSWLZ4BxHMcuqcTwr5xB0zMqCySBeTPWrVq+rNy9'
    b'Eq9n+eu7v4Sfv9z9Oi6s9cCMgsJCstDW71X97lVJSG1qaanc7XGdz8PbCzqJSSegdNp9MIy83z3/MgTv8hX7/thuGBYeBXJSD8zktUKC'
    b'Tb8XXxXrT6+99trruKfzbtkqiX35JVAOMUX5sqWywI1sBQVE/1z+R1K5cv14V6Tr5RcLnv/tb4F6FXTix88DUH73x5c77edjv+vg+B9v'
    b'AqJYHS2/93Ps94WivehlCBMvim8o+F1BQecQd1pA5/rdv4X8ZlknoPwr2Yu7EU8cu1/sHIpO++cDym9Cljz3X7/vHIl/Gfv9yy9ubrGa'
    b'KzvxpNP++c71X88tCVmydGthp/0rWUHBckkm7bRO+6fa1qVLQoTfPPd6Z9Lzr0ZTOq3T/vkJz+bnfiOEGIVfL33ut893Wqd1Wqf9A/bb'
    b'55b+WjCGCEZhyZLF/9ZpndZpnfYP2OIlSwBM/n+90501VIKJHQAAAABJRU5ErkJggg=='
)


# 保留既有项目 import 名称；实际实现均为 Supreme13。
ThreeCardPokerGame = Supreme13Game
ThreeCardPokerGUI = Supreme13GUI


def main(initial_balance=10000, username='Guest', *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """兼容原入口：可嵌入现有Tk窗口，也可独立运行Guest试玩。"""
    actual_balance = _amount(initial_balance if balance is None else balance)
    actual_user = username if user is None else user
    if parent is not None:
        return Supreme13GUI(parent, actual_balance, actual_user,
                            on_back=on_back, on_balance_change=on_balance_change)
    root = tk.Tk()
    root.title('Supreme13')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)
    page = Supreme13GUI(root, actual_balance, actual_user,
                        on_balance_change=on_balance_change)
    page.pack(fill=tk.BOTH, expand=True)
    page.on_back = lambda final_balance: root.destroy()
    root.protocol('WM_DELETE_WINDOW', page.on_close)
    root.mainloop()
    return page.balance


if __name__ == '__main__':
    final_balance = main()
    print(f'Final balance: {final_balance}')

