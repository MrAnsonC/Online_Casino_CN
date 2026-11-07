"""Super Pan 9 — two player seats against a fixed-rule casino dealer.

Drop into the original game's directory to reuse A_Tools account encryption,
card art and CSM_Shuffler.py. main() retains the original embedding/callback API.
Guest mode never writes account data; every game still requires CSM_Shuffler.py.

Rules: remove 7/8/9/10; three initial cards; P1 then P2 may draw once,
except 9 automatically stands; dealer draws on 0–5 and stands on 6–9.
Wins return stake + 95% profit, ties return stake, losses return zero.
"""

import json
import math
import os
import random
import subprocess
import sys
import time
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont

ROOT_BG = '#1B3D31'
TEXT, RED, BLACK = '#ffffff', '#ff2a23', '#050505'
DARK_BLUE, GOLD = '#173f66', '#D4AF37'
PANEL_BG, HEADER_BG, TITLE_FG = '#F2E6C9', '#D8B46A', '#2A1B08'
SUITS = ['♠', '♥', '♦', '♣']
ALL_RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
RANKS = ['A', '2', '3', '4', '5', '6', 'J', 'Q', 'K']
RANK_VALUES = {rank: index for index, rank in enumerate(ALL_RANKS, 1)}
DECK_COUNT = 8  # Matches Blackjack's shared CSM; only RANKS enter game hands.
WIN_PROFIT_RATE = Decimal('0.95')
CENT = Decimal('0.01')
_secure_account_ready = False


def money(value):
    """Validate finite currency and round half up to cents."""
    try:
        amount = Decimal(str(value))
        if not amount.is_finite():
            raise ValueError('金额必须是有限数值。')
        return amount.quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError('金额格式不正确。') from exc


def project_root():
    directory = Path(__file__).resolve().parent
    for candidate in (directory, *directory.parents):
        if (candidate / 'A_Tools').is_dir():
            return candidate
    return directory.parent


def get_data_file_path():
    """Named accounts must use the existing encrypted storage, never plaintext."""
    global _secure_account_ready
    root = project_root()
    if not (root / 'A_Tools' / 'Account' / 'secure_json.py').is_file():
        raise RuntimeError('找不到原项目的加密账户组件，请把程序放回原游戏目录。')
    if not _secure_account_ready:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from A_Tools.Account import install_secure_json
        install_secure_json()
        _secure_account_ready = True
    return str(root / 'A_Tools' / 'Account' / 'saving_data.json')


def load_user_data():
    with open(get_data_file_path(), 'r', encoding='utf-8') as stream:
        users = json.load(stream)
    if not isinstance(users, list):
        raise ValueError('账户数据格式不正确，未修改账户文件。')
    return users


def save_user_data(users):
    with open(get_data_file_path(), 'w', encoding='utf-8') as stream:
        json.dump(users, stream, ensure_ascii=False, indent=4)


def update_balance_in_json(username, new_balance):
    if not username or username == 'Guest':
        return
    users = load_user_data()
    for user in users:
        if user.get('user_name') == username:
            user['cash'] = format(money(new_balance), '.2f')
            save_user_data(users)
            return
    raise ValueError(f'找不到账户 {username}，未修改账户文件。')


class Card:
    def __init__(self, suit, rank):
        if suit not in SUITS or rank not in RANK_VALUES:
            raise ValueError('无效扑克牌。')
        self.suit, self.rank = suit, rank
        self.value = RANK_VALUES[rank]

    @property
    def points(self):
        return self.value if self.value < 10 else 0

    def __repr__(self):
        return f'{self.rank}{self.suit}'


class CSMDeck:
    """Same chamber/round lease protocol used by Blackjack_Classic.BlackjackEngine.

    CSM remains the only source of cards and authoritative shoe state. Excluded
    ranks are consumed from the leased chamber, tracked by ID, and returned
    along with played cards at round end; no local shoe is generated or shuffled.
    The <=3-card chamber handoff is delegated to acquire_chamber, as in Blackjack.
    """
    SUIT_SYMBOLS = dict(Club='♣', Diamond='♦', Heart='♥', Spade='♠')

    def __init__(self, csm=None, game_id=None):
        import uuid
        self.game_id = game_id or f'SuperPan9:{uuid.uuid4().hex}'
        if csm is None:
            directory = Path(__file__).resolve().parent
            candidates = [project_root() / 'A_Tools' / 'Card',
                          directory.parent / 'A_Tools' / 'Card',
                          directory.parent / 'Card', directory]
            tools_dir = next((path for path in candidates
                              if (path / 'CSM_Shuffler.py').is_file()), None)
            if tools_dir is None:
                raise ModuleNotFoundError(
                    '找不到 CSM_Shuffler.py。请将本程序放回原游戏目录，'
                    '并保留 Blackjack_Classic 使用的 A_Tools/Card/CSM_Shuffler.py。')
            if str(tools_dir) not in sys.path:
                sys.path.insert(0, str(tools_dir))
            from CSM_Shuffler import ContinuousShuffleMachine
            csm = ContinuousShuffleMachine()
        self.csm = csm
        self.failed = False
        self._clear_local_csm_state()
        self.dealt_cards = []
        self.excluded_count = 0
        self.last_round_id = None
        self.csm.status()

    def _clear_local_csm_state(self):
        self.round_id = None
        self.round_open = False
        self.card_buffer = []
        self.current_batch_id = None
        self.used_by_batch = {}

    def start_round(self):
        if self.failed:
            raise RuntimeError('连续洗牌机状态异常，请先退出以释放本游戏的牌仓。')
        if self.round_open:
            raise RuntimeError('上一局牌张尚未归还。')
        try:
            self.round_id = self.csm.begin_round(
                self.game_id, self.current_batch_id if self.card_buffer else None)
            self.last_round_id = self.round_id
            self.used_by_batch = {}
            self.dealt_cards = []
            self.excluded_count = 0
            self.round_open = True
            if not self.card_buffer:
                self._request_next_chamber()
        except Exception:
            # CSM recovery may have invalidated every old batch and round ID.
            self._clear_local_csm_state()
            self.failed = True
            raise

    def _request_next_chamber(self):
        packet = self.csm.acquire_chamber(self.game_id, self.round_id)
        self.current_batch_id = packet['batch_id']
        self.card_buffer = list(packet['cards'])
        if not self.card_buffer:
            raise RuntimeError('连续洗牌机返回了空仓。')

    def remaining_cards(self):
        return len(self.card_buffer) + self.csm.available_cards()

    def draw_card(self):
        if self.failed or not self.round_open:
            raise RuntimeError('连续洗牌机牌局未开启或已暂停。')
        try:
            while True:
                if len(self.card_buffer) <= 3:
                    self._request_next_chamber()
                record = self.card_buffer.pop(0)
                self.used_by_batch.setdefault(self.current_batch_id, []).append(record['card_id'])
                suit = self.SUIT_SYMBOLS.get(record['suit'], record['suit'])
                card = Card(suit, record['rank'])
                if card.rank not in RANKS:
                    self.excluded_count += 1
                    continue
                self.dealt_cards.append(card)
                return card
        except Exception:
            self._clear_local_csm_state()
            self.failed = True
            raise

    def deal(self, n=1):
        if not isinstance(n, int) or n < 0:
            raise ValueError('发牌数量必须是非负整数。')
        return [self.draw_card() for _ in range(n)]

    def finish_round(self):
        if self.failed:
            raise RuntimeError('洗牌机曾报告异常，须先退出并释放牌仓。')
        if not self.round_open:
            return
        rid = self.round_id
        try:
            for batch_id in list(self.used_by_batch):
                ids = self.used_by_batch[batch_id]
                if ids:
                    self.csm.return_cards(self.game_id, batch_id, ids)
                del self.used_by_batch[batch_id]
        except Exception:
            self._clear_local_csm_state()
            self.failed = True
            raise
        try:
            self.csm.end_round(self.game_id, rid)
        except Exception:
            self._clear_local_csm_state()
            self.failed = True
            raise
        else:
            self.round_id = None
            self.round_open = False
            # Keep the unused current chamber for the next round, just like Blackjack.

    def close(self):
        try:
            self.csm.release_game(self.game_id, force_shuffle=True)
        except Exception:
            self.failed = True
            self._clear_local_csm_state()
            raise
        else:
            self._clear_local_csm_state()
            self.failed = False


Deck = CSMDeck


def hand_points(cards):
    return sum(card.points for card in cards) % 10


def sort_hand_for_display(hand, hand_eval=None):
    """Stable rank-only sort; preserve actual deal order and duplicate identities."""
    return sorted(hand, key=lambda card: RANK_VALUES[card.rank])


class SuperPan9Game:
    SEATS = ('Player1', 'Player2')

    def __init__(self, deck_factory=None):
        self.deck_factory = deck_factory or CSMDeck
        self._shoe = None
        self.reset_game()

    @staticmethod
    def empty_bet():
        return {'main': 0.0}

    def reset_game(self):
        self.deck = None
        self.hands = {seat: [] for seat in self.SEATS}
        self.dealer_hand = []
        self.bets = {seat: self.empty_bet() for seat in self.SEATS}
        self.decisions = {seat: 'inactive' for seat in self.SEATS}
        self.round_deal_sequence = []
        self.draw_sequence = []
        self.current_turn = None
        self.dealer_decision = None
        self.stage = 'betting'
        self.settlement = None

    @classmethod
    def deal_sequence(cls, active_seats=None):
        active = cls.SEATS if active_seats is None else active_seats
        seats = [seat for seat in cls.SEATS if seat in active]
        return [(side, index) for index in range(3) for side in (*seats, 'Dealer')]

    def start_round(self, bets, balance, high_bet_mode=False):
        if self.stage != 'betting':
            raise ValueError('本局尚未结束。')
        minimum, maximum = (100, 50000) if high_bet_mode else (10, 10000)
        prepared = {}
        for seat in self.SEATS:
            value = bets.get(seat, {}).get('main', 0)
            stake = money(value)
            raw = Decimal(str(value))
            if raw != stake or stake < 0:
                raise ValueError('下注金额必须为非负数，最多两位小数。')
            if stake and not minimum <= stake <= maximum:
                raise ValueError(f'每手主注须为 ${minimum:,} 至 ${maximum:,}。')
            prepared[seat] = {'main': float(stake)}
        charge = sum((money(b['main']) for b in prepared.values()), Decimal(0))
        if charge <= 0:
            raise ValueError('请至少为一位玩家下注。')
        if charge > money(balance):
            raise ValueError('余额不足以支付两位玩家的下注。')
        # Commit only after the complete initial deal succeeds.
        if self._shoe is None:
            self._shoe = self.deck_factory()
        deck = self._shoe
        hands = {seat: [] for seat in self.SEATS}
        dealer = []
        targets = dict(hands, Dealer=dealer)
        active = [seat for seat in self.SEATS if prepared[seat]['main'] > 0]
        sequence = self.deal_sequence(active)
        try:
            deck.start_round()
            for side, _ in sequence:
                targets[side].extend(deck.deal())
        except Exception:
            deck.close()
            raise
        self.deck, self.hands, self.dealer_hand = deck, hands, dealer
        self.bets, self.round_deal_sequence = prepared, sequence
        self.decisions = {s: 'pending' if s in active else 'inactive' for s in self.SEATS}
        self.stage = 'dealing'
        return float(charge)

    def begin_next_turn(self):
        if self.stage not in ('dealing', 'player_done'):
            raise ValueError('当前阶段不能开始下一位玩家。')
        self.current_turn = next((s for s in self.SEATS if self.decisions[s] == 'pending'), 'Dealer')
        self.stage = 'dealer_reveal' if self.current_turn == 'Dealer' else 'player_reveal'
        return self.current_turn

    def player_revealed(self, seat):
        if self.stage != 'player_reveal' or self.current_turn != seat:
            raise ValueError('尚未轮到这位玩家。')
        self.stage = 'decision'
        if hand_points(self.hands[seat]) == 9:
            self.decide(seat, 'stand')
            return True
        return False

    def decide(self, seat, action, balance=None):
        if (self.stage != 'decision' or self.current_turn != seat
                or self.decisions.get(seat) != 'pending'):
            raise ValueError('尚未轮到这位玩家，或本手已经完成。')
        if action not in ('hit', 'stand'):
            raise ValueError('只能选择要牌或不要牌。')
        if hand_points(self.hands[seat]) == 9:
            action = 'stand'
        if action == 'hit':
            self.hands[seat].extend(self.deck.deal())
            self.draw_sequence.append((seat, 3))
        self.decisions[seat] = action
        self.stage = 'player_done'
        return action

    def play_dealer(self):
        if self.stage != 'dealer_reveal' or self.current_turn != 'Dealer':
            raise ValueError('玩家决定尚未全部完成。')
        if hand_points(self.dealer_hand) <= 5:
            self.dealer_hand.extend(self.deck.deal())
            self.draw_sequence.append(('Dealer', 3))
            self.dealer_decision = 'hit'
        else:
            self.dealer_decision = 'stand'
        self.stage = 'showdown'
        return self.dealer_decision

    def settle(self):
        if self.settlement is not None:
            return self.settlement
        if self.stage != 'showdown' or any(v == 'pending' for v in self.decisions.values()):
            raise ValueError('必须完成所有补牌后才能结算。')
        outcomes = {}
        dealer_points = hand_points(self.dealer_hand)
        for seat in self.SEATS:
            if self.decisions[seat] == 'inactive':
                continue
            stake = money(self.bets[seat]['main'])
            points = hand_points(self.hands[seat])
            if points > dealer_points:
                winner, message = 'player', '获胜 · 赔付 0.95:1'
                returned = stake + money(stake * WIN_PROFIT_RATE)
            elif points == dealer_points:
                winner, message, returned = 'push', '平局 · 退回本金', stake
            else:
                winner, message, returned = 'dealer', '落败 · 没收下注', Decimal(0)
            outcomes[seat] = dict(winner=winner, message=message, points=points,
                dealer_points=dealer_points, stake=float(stake), returned=float(returned),
                net=float(returned - stake), details={'main': float(returned)})
        self.settlement = {'hands': outcomes,
            'returned': float(sum((money(o['returned']) for o in outcomes.values()), Decimal(0)))}
        self.stage = 'settled'
        return self.settlement


def save_super_pan9_history(game, username):
    # One record per round, with both seats, original deal order and decisions.
    directory = project_root() / 'A_Logs' / 'Json'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'Super_Pan_9.json'
    data = {'history': []}
    if path.exists():
        with path.open('r', encoding='utf-8') as stream:
            data = json.load(stream)
        if not isinstance(data, dict) or not isinstance(data.get('history'), list):
            raise ValueError('Super Pan 9 历史格式不正确。')
    data['history'].append(dict(round_id=time.time_ns(), username=username,
        timestamp=time.strftime('%Y-%m-%d %H:%M:%S'),
        shuffler='CSM_Shuffler', game_id=game.deck.game_id,
        csm_round_id=game.deck.last_round_id,
        initial_deal=game.round_deal_sequence, draws=game.draw_sequence,
        dealt_cards=[str(c) for c in game.deck.dealt_cards],
        excluded_count=game.deck.excluded_count,
        player_cards={seat: [str(c) for c in hand] for seat, hand in game.hands.items()},
        dealer_cards=[str(c) for c in game.dealer_hand],
        decisions=game.decisions, dealer_decision=game.dealer_decision,
        result=game.settlement))
    data['history'] = data['history'][-50:]
    with path.open('w', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)


class SuperPan9GUI(tk.Frame):
    WIDTH, HEIGHT = 1150, 750
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    DEAL_CARD_MS, DEAL_MOVE_MS = 260, 195
    BET_CHIP_RADIUS = 16 * 4 / 3
    HOUSE_CHIP_POS = (575, 43)
    TABLE_GREEN = '#4b1e22'
    SEAT_BOUNDS = {'Player1': (22, 566), 'Player2': (582, 1128)}
    ZONE_COLORS = {'Player1': '#35634B', 'Player2': '#204536'}
    SEAT_NAMES = {'Player1': '玩家1', 'Player2': '玩家2', 'Dealer': '赌场'}

    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        if money(initial_balance) < 0:
            raise ValueError('余额不能为负数。')
        self.username, self.balance = username, float(money(initial_balance))
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game = SuperPan9Game()
        self.bets = {s: self.game.empty_bet() for s in self.game.SEATS}
        self.last_bet, self.last_win = None, 0.0
        self.high_bet_mode, self.selected_chip = False, 10.0
        self._jobs = set()
        self._closing = self._crediting = self._credited = self._return_persisted = False
        self._restart_job = self._restart_deadline = None
        self._motion_count = self._chip_serial = 0
        self._decision_busy = self._settlement_started = False
        self._history_available = False
        self.last_round_snapshot = None
        self.visual_chips = {}
        self.revealed_sides = set()
        self._face_photos, self._pil_cards, self._flip_photos = {}, {}, {}
        self.card_items, self.bet_spots, self.action_buttons = {}, {}, {}
        self._load_assets()
        self._create_widgets()
        self._status('请选择筹码并下注；未下注的玩家将跳过。')
        self._refresh()
        self.bind('<Destroy>', self._on_destroy, add='+')

    @property
    def game_in_progress(self):
        return self.game.stage != 'betting' or self._motion_count > 0

    def _create_widgets(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=ROOT_BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.control_buttons = {}
        c = self.canvas
        self._text(575, 21, 'SUPER PAN 9', 21, GOLD)
        self._draw_limit_table()
        c.create_rectangle(382, 48, 768, 230, fill=self.TABLE_GREEN, outline=GOLD)
        self.title_items = {'Dealer': self._text(575, 67, '赌场 · 等待发牌', 16, PANEL_BG)}
        self.dealer_action_item = self._text(575, 216, '0–5 点要牌 · 6–9 点停牌', 11, PANEL_BG)
        self._text(946, 91, '赢 0.95 : 1', 22, GOLD)
        self._text(946, 129, '平局 · 退回本金', 13, PANEL_BG)
        self._text(946, 163, 'A = 1   J / Q / K = 0', 12, PANEL_BG)
        self._text(946, 192, '移除 7 / 8 / 9 / 10', 12, PANEL_BG)
        c.create_rectangle(22, 239, 1128, 272, fill='#173C2E', outline='#65784B')
        self.status_item = self._text(575, 255, '', 13, GOLD)
        self.point_items, self.seat_panel_items = {}, {}
        for seat, (x0, x1) in self.SEAT_BOUNDS.items():
            center = (x0 + x1) / 2
            self.seat_panel_items[seat] = c.create_rectangle(x0, 282, x1, 617,
                fill=self.ZONE_COLORS[seat], outline='#65784B', width=2)
            self.title_items[seat] = self._text(center, 303, self.SEAT_NAMES[seat], 17, PANEL_BG)
            tag = 'spot_' + seat + '_main'
            cx, cy = center - 93, 535
            # A large numeral marks the wager; the entire original area is
            # clickable, including the numeral's hole and spaces around chips.
            bounds = (cx-59, cy-46, cx+59, cy+46)
            c.create_rectangle(*bounds, fill=self.ZONE_COLORS[seat], outline='', tags=tag)
            border = self._draw_main_nine(seat, cx, cy, tag)
            self._register_spot(seat, 'main', cx, cy, border, None)
            self.bet_spots[(seat, 'main')]['bounds'] = bounds
            self.point_items[seat] = self._text(cx-105, cy, '—', 30, GOLD)
            self.action_buttons[(seat, 'hit')] = self.create_control_button(
                center+12, 480, center+137, 524, '要牌',
                lambda s=seat: self._decide(s, 'hit'), '#397A48', font_size=15, draw_shadow=False)
            self.action_buttons[(seat, 'stand')] = self.create_control_button(
                center+12, 538, center+137, 582, '不要牌',
                lambda s=seat: self._decide(s, 'stand'), '#865C38', font_size=15, draw_shadow=False)
        c.bind('<Button-1>', self._click_bet_area, add='+')
        c.bind('<Button-3>', self._clear_bet_area, add='+')
        self._draw_bottom_controls()
        for side in ('Dealer', *self.game.SEATS):
            for index in range(4):
                x, y = self.card_position(side, index)
                c.create_rectangle(x, y, x+self.CARD_WIDTH, y+self.CARD_HEIGHT,
                    outline='#7B9374', dash=(3, 3), tags='card_slots')

    def _draw_main_nine(self, seat, cx, cy, tag):
        """Clean ivory numeral inside a fine circular wager frame."""
        c = self.canvas
        radius = 45
        border = c.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
            fill=self.ZONE_COLORS[seat], outline='#E4BD64', width=2, tags=tag)
        c.create_text(cx, cy+2, text='9', font=('Arial', 48, 'bold'),
                      fill='#F7EAD0', anchor='center', tags=tag)
        return border

    def _draw_limit_table(self):
        c = self.canvas
        c.create_rectangle(30, 64, 355, 217, fill='#183B30', outline=GOLD, tags='limits')
        self._text(192, 85, '主注限额', 15, GOLD, tags='limits')
        self.limit_value_item = self._text(192, 121, '', 17, PANEL_BG, tags='limits')
        self._text(192, 158, 'CSM 连续洗牌 · A～6 / J / Q / K', 11, PANEL_BG, tags='limits')
        self._text(192, 191, '左键下注 · 右键清除该手', 11, PANEL_BG, tags='limits')
        c.tag_bind('limits', '<Button-1>', self.toggle_high_bet_limits)

    def _status(self, message):
        self.current_status = message
        if hasattr(self, 'status_item'):
            self.canvas.itemconfigure(self.status_item, text=message)

    def _refresh(self):
        c = self.canvas
        c.itemconfigure(self.balance_item, text=f'余额: ${self.balance:,.2f}')
        total = sum(b['main'] for b in self.bets.values())
        c.itemconfigure(self.total_item, text=f'本局下注: ${total:,.2f}' if total else f'上局返还: ${self.last_win:,.2f}')
        c.itemconfigure(self.limit_value_item, text='$100 – $50,000' if self.high_bet_mode else '$10 – $10,000')
        self._render_chips()
        betting = self.game.stage == 'betting' and self._motion_count == 0
        self.set_control_button_state(self.clear_button, betting)
        self.set_control_button_state(self.repeat_button, betting and bool(self.last_bet))
        self.set_control_button_state(self.start_button, betting or self.game.stage == 'funding_pending')
        c.itemconfigure(self.control_buttons[self.start_button]['text'],
                        text='重试保存' if self.game.stage == 'funding_pending' else '开牌')
        restarting = self.game.stage in ('await_restart', 'returning', 'credit_pending', 'sweeping')
        c.itemconfigure(self.repeat_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button, state='normal' if restarting else 'hidden')
        self.set_control_button_state(self.restart_button, self.game.stage in ('await_restart', 'credit_pending'))
        for (seat, action), button in self.action_buttons.items():
            enabled = (self.game.stage == 'decision' and not self._decision_busy
                       and self.game.current_turn == seat and self.game.decisions[seat] == 'pending')
            self.set_control_button_state(button, enabled)
        for seat, item in self.seat_panel_items.items():
            active = self.game.current_turn == seat and self.game.stage in ('decision', 'player_reveal')
            c.itemconfigure(item, outline=GOLD if active else '#65784B', width=3 if active else 2)

    def add_chip_to_bet(self, seat, kind='main'):
        if self.game.stage != 'betting' or self._motion_count or kind != 'main':
            return
        new = {s: dict(b) for s, b in self.bets.items()}
        maximum = 50000 if self.high_bet_mode else 10000
        new[seat]['main'] = min(maximum, new[seat]['main'] + self.selected_chip)
        self._apply_bet_layout(new)

    def _bet_spot_at(self, x, y):
        """Hit test the complete wager area, independent of the topmost item."""
        for key, spot in self.bet_spots.items():
            x0, y0, x1, y1 = spot['bounds']
            if x0 <= x <= x1 and y0 <= y <= y1:
                return key
        return None

    def _click_bet_area(self, event):
        spot = self._bet_spot_at(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        if spot is not None:
            self.add_chip_to_bet(*spot)
            return 'break'

    def _clear_bet_area(self, event):
        spot = self._bet_spot_at(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        if spot is not None:
            self.reset_single_bet(*spot)
            return 'break'

    def reset_single_bet(self, seat, kind='main'):
        if self.game.stage == 'betting' and not self._motion_count:
            new = {s: dict(b) for s, b in self.bets.items()}
            new[seat]['main'] = 0.0
            self._apply_bet_layout(new)

    def _apply_bet_layout(self, new_bets):
        if sum(money(b['main']) for b in new_bets.values()) > money(self.balance):
            messagebox.showwarning('余额不足', '两位玩家的总下注不能超过余额。', parent=self)
            return
        previous, self.bets = self.bets, {s: dict(b) for s, b in new_bets.items()}
        transfers = []
        for seat in self.game.SEATS:
            old, new = previous[seat]['main'], self.bets[seat]['main']
            delta = new - old
            if not delta:
                continue
            center = self.bet_spots[(seat, 'main')]['center']
            if delta > 0:
                transfers.append(dict(amount=delta, start=self._rack_position(), target=center,
                    arrive=lambda s=seat, a=new: self._set_visual(s, 'main', 'stake', a)))
            else:
                self._set_visual(seat, 'main', 'stake', new)
                transfers.append(dict(amount=-delta, start=center, target=self._rack_position(), duration=440))
        self._run_chip_batch(transfers, self._refresh)
        self._refresh()

    def _persist_balance(self):
        try:
            update_balance_in_json(self.username, self.balance)
        except Exception as exc:
            messagebox.showerror('余额保存失败', str(exc), parent=self)
            return False
        if callable(self.on_balance_change):
            try:
                self.on_balance_change(float(self.balance))
            except Exception as exc:
                # Account write already succeeded; never debit or credit again.
                messagebox.showwarning('余额界面更新失败', str(exc), parent=self)
        return True

    def card_position(self, side, index):
        center = 575 if side == 'Dealer' else sum(self.SEAT_BOUNDS[side]) / 2
        return center - 167.5 + index*85, 92 if side == 'Dealer' else 329

    def start_game(self):
        if self.game.stage == 'funding_pending':
            self._begin_funded_round()
            return
        if self.game.stage != 'betting' or self._motion_count:
            return
        # Lock before starting the shuffle so repeat clicks cannot debit twice.
        self.set_control_button_state(self.start_button, False)
        try:
            if self.username and self.username != 'Guest':
                get_data_file_path()
            charged = self.game.start_round(self.bets, self.balance, self.high_bet_mode)
        except Exception as exc:
            self._refresh()
            messagebox.showwarning('无法开始', str(exc), parent=self)
            return
        self.balance = float(money(self.balance) - money(charged))
        self.bets = {s: dict(b) for s, b in self.game.bets.items()}
        self.last_bet = {s: dict(b) for s, b in self.bets.items()}
        self.last_win = 0.0
        self._credited = self._return_persisted = self._settlement_started = False
        self._decision_busy = False
        self.revealed_sides.clear()
        self._history_available = False
        self._close_card_sequence()
        self._cancel_restart_timer()
        self.canvas.delete('cards')
        self.card_items.clear()
        self._flip_photos.clear()
        self._load_assets()
        for side, item in self.title_items.items():
            caption = self.SEAT_NAMES[side] + ' · 盖牌'
            if side in self.game.SEATS and self.game.decisions[side] == 'inactive':
                caption = self.SEAT_NAMES[side] + ' · 未下注'
            self.canvas.itemconfigure(item, text=caption)
        for item in self.point_items.values():
            self.canvas.itemconfigure(item, text='—')
        self.canvas.itemconfigure(self.dealer_action_item, text='0–5 点要牌 · 6–9 点停牌')
        self.game.stage = 'funding_pending'
        self._begin_funded_round()

    def _begin_funded_round(self):
        if not self._persist_balance():
            self._status('下注余额尚未保存，请点击“重试保存”。')
            self._refresh()
            return
        self.game.stage = 'dealing'
        self._status('各发三张盖牌，依次由玩家1、玩家2、赌场行动。')
        self._refresh()
        self._deal_next(self.game.round_deal_sequence, 0, self._next_turn)

    def _deal_next(self, sequence, offset, complete):
        if offset == len(sequence):
            complete()
            return
        side, index = sequence[offset]
        x, y = self.card_position(side, index)
        item = self.canvas.create_image(575, 43, image=self._face_photos['back'], anchor='nw', tags='cards')
        self.card_items[(side, index)] = item
        def move(step=0):
            fraction = step/6
            self.canvas.coords(item, 575+(x-575)*fraction, 43+(y-43)*fraction)
            if step < 6:
                self._schedule(round(self.DEAL_MOVE_MS/6), move, step+1)
            else:
                self._schedule(max(1, round(self.DEAL_CARD_MS-self.DEAL_MOVE_MS)),
                               self._deal_next, sequence, offset+1, complete)
        move()

    def _reveal_next(self, sequence, offset, complete):
        if offset == len(sequence):
            complete()
            return
        side, index = sequence[offset]
        hand = self.game.dealer_hand if side == 'Dealer' else self.game.hands[side]
        card, item = hand[index], self.card_items[(side, index)]
        x, y = self.canvas.coords(item)
        def flip(step=0):
            width = max(1, round(self.CARD_WIDTH*abs(1-step/5)))
            source = self._pil_cards['back' if step < 5 else (card.suit, card.rank)]
            photo = ImageTk.PhotoImage(source.resize((width, self.CARD_HEIGHT), Image.Resampling.LANCZOS), master=self)
            self._flip_photos[item] = photo
            self.canvas.itemconfigure(item, image=photo)
            self.canvas.coords(item, x+(self.CARD_WIDTH-width)/2, y)
            if step < 10:
                self._schedule(24, flip, step+1)
            else:
                self.canvas.itemconfigure(item, image=self._face_photos[(card.suit, card.rank)])
                self.canvas.coords(item, x, y)
                self._flip_photos.pop(item, None)
                self._reveal_next(sequence, offset+1, complete)
        flip()

    def _sort_revealed_hand(self, side, complete):
        hand = self.game.dealer_hand if side == 'Dealer' else self.game.hands[side]
        motions = []
        for target_index, card in enumerate(sort_hand_for_display(hand)):
            original_index = next(i for i, candidate in enumerate(hand) if candidate is card)
            item = self.card_items[(side, original_index)]
            motions.append((item, self.canvas.coords(item), self.card_position(side, target_index)))
        def step(frame=0):
            fraction = frame/12
            for item, (x, y), (tx, ty) in motions:
                self.canvas.coords(item, x+(tx-x)*fraction, y+(ty-y)*fraction)
            if frame < 12:
                self._schedule(25, step, frame+1)
            else:
                self.revealed_sides.add(side)
                self._update_hand_title(side)
                complete()
        step()

    def _next_turn(self):
        side = self.game.begin_next_turn()
        self._status(f'{self.SEAT_NAMES[side]}开牌。')
        self._refresh()
        finished = self._dealer_revealed if side == 'Dealer' else lambda: self._player_revealed(side)
        self._reveal_next([(side, i) for i in range(3)], 0,
                         lambda: self._sort_revealed_hand(side, finished))

    def _player_revealed(self, seat):
        auto_stand = self.game.player_revealed(seat)
        self._refresh()
        if auto_stand:
            self._status(f'{self.SEAT_NAMES[seat]} 9 点，自动不要牌。')
            self._schedule(700, self._next_turn)
        else:
            self._status(f'{self.SEAT_NAMES[seat]} {hand_points(self.game.hands[seat])} 点，请选择要牌或不要牌。')

    def _decide(self, seat, action):
        if (self.game.stage != 'decision' or self._decision_busy
                or self.game.current_turn != seat):
            return
        self._decision_busy = True
        try:
            actual = self.game.decide(seat, action)
        except Exception as exc:
            self._decision_busy = False
            if getattr(self.game.deck, 'failed', False):
                self._pause_csm_error(exc)
                return
            messagebox.showwarning('无法决定', str(exc), parent=self)
            self._refresh()
            return
        self._status(f'{self.SEAT_NAMES[seat]}：' + ('要一张牌。' if actual == 'hit' else '不要牌。'))
        self._refresh()
        def done():
            self._decision_busy = False
            self._update_hand_title(seat)
            self._refresh()
            self._schedule(500, self._next_turn)
        if actual == 'hit':
            self._draw_extra_card(seat, done)
        else:
            done()

    def _draw_extra_card(self, side, complete):
        sequence = [(side, 3)]
        self._deal_next(sequence, 0, lambda: self._reveal_next(sequence, 0,
            lambda: self._sort_revealed_hand(side, complete)))

    def _dealer_revealed(self):
        initial_points = hand_points(self.game.dealer_hand)
        try:
            action = self.game.play_dealer()
        except Exception as exc:
            self._pause_csm_error(exc)
            return
        caption = f'初始 {initial_points} 点 · ' + ('按规则补一张' if action == 'hit' else '按规则停牌')
        self.canvas.itemconfigure(self.dealer_action_item, text=caption)
        self._status('赌场' + caption + '。')
        self._refresh()
        if action == 'hit':
            self._schedule(650, self._draw_extra_card, 'Dealer', self._settle)
        else:
            self._schedule(650, self._settle)

    def _update_hand_title(self, side):
        if side not in self.revealed_sides:
            return
        hand = self.game.dealer_hand if side == 'Dealer' else self.game.hands[side]
        if side == 'Dealer':
            self.canvas.itemconfigure(self.title_items[side], text=f'赌场 · {hand_points(hand)} 点')
        else:
            self.canvas.itemconfigure(self.title_items[side], text=self.SEAT_NAMES[side])
            self.canvas.itemconfigure(self.point_items[side], text=str(hand_points(hand)))

    def _settle(self):
        if self._settlement_started:
            return
        result = self.game.settle()
        self._settlement_started = True
        self.game.stage = 'settling'
        self.last_win = result['returned']
        self._update_hand_title('Dealer')
        transfers = []
        for seat, outcome in result['hands'].items():
            self._update_hand_title(seat)
            transfers.extend(self._outcome_transfers(seat, 'main', outcome['stake'], outcome['returned']))
        if self.username and self.username != 'Guest':
            try:
                save_super_pan9_history(self.game, self.username)
            except Exception as exc:
                messagebox.showwarning('牌局记录未保存', str(exc), parent=self)
        self._status(f'结算完成 · 赌场 {hand_points(self.game.dealer_hand)} 点 · 总返还 ${self.last_win:,.2f}')
        self._refresh()
        self._run_chip_batch(transfers, self._await_next_round)

    def _await_next_round(self):
        if self.game.stage != 'settling':
            return
        self.game.stage = 'await_restart'
        deck = self.game.deck
        self.last_round_snapshot = dict(cards=tuple(deck.dealt_cards),
            sequence=tuple(self.game.round_deal_sequence+self.game.draw_sequence),
            images={key: im.copy() for key, im in self.original_images.items()})
        self._history_available = True
        self._cancel_restart_timer()
        self._restart_deadline = time.monotonic()+30
        self._refresh()
        self._restart_tick()

    def _sweep_all_cards(self):
        if not self.card_items:
            self._finish_round()
            return
        self._motion_count += 1
        previous = [0.0]
        def frame(index=0):
            fraction = index/13
            offset = (self.WIDTH+self.CARD_WIDTH)*fraction*fraction*(3-2*fraction)
            self.canvas.move('cards', offset-previous[0], 0)
            previous[0] = offset
            if index < 13:
                self._schedule(16, frame, index+1)
            else:
                self.canvas.delete('cards')
                self.card_items.clear()
                self._flip_photos.clear()
                self._motion_count -= 1
                self._finish_round()
        frame()

    def _finish_round(self):
        if self.game.stage != 'sweeping':
            return
        self.game.reset_game()
        self.revealed_sides.clear()
        self._history_available = False
        self.bets = {s: self.game.empty_bet() for s in self.game.SEATS}
        self.visual_chips.clear()
        for side, item in self.title_items.items():
            self.canvas.itemconfigure(item, text=self.SEAT_NAMES[side])
        for item in self.point_items.values():
            self.canvas.itemconfigure(item, text='—')
        self.canvas.itemconfigure(self.dealer_action_item, text='0–5 点要牌 · 6–9 点停牌')
        self._status('请选择筹码并下注；未下注的玩家将跳过。')
        self._refresh()

    def reset_game(self, auto_reset=False):
        if self.game.stage == 'betting':
            self.reset_bets()

    def show_game_instructions(self):
        messagebox.showinfo('Super Pan 9 游戏说明',
            '沿用 Blackjack_Classic 的 CSM 连续洗牌机，跨局供牌。\n'
            '7、8、9、10 不进入手牌；所有取出的牌按编号归还洗牌机。\n\n'
            '1. 玩家1、玩家2分别下注；未下注者不发牌并跳过。\n'
            '2. 参与的玩家与赌场各发3张盖牌。\n'
            '3. 玩家1先翻牌，按 A、2～6、J、Q、K 排序并显示点数。\n'
            '   可选要牌或不要牌；9点自动不要牌，最多补1张。\n'
            '4. 玩家1完成后，玩家2按同样规则行动。\n'
            '5. 两位玩家完成后赌场开牌；0～5点补1张，6～9点停牌。\n'
            '6. A算1点，J/Q/K算0点，2～6按牌面计分；总和取个位。\n'
            '7. 比赌场大：净赢下注的95%；相同：退回本金；小：输掉下注。\n'
            '   所有相同点数均为平局，包括0点；不比较花色、牌数或牌型。\n'
            '8. 盈利按分四舍五入；下注100，获胜返还195。\n\n'
            '左键主注区加筹码，右键清除该手；双方共用当前账户余额。\n'
            '补牌不加注。结算后点击“再来一局”收回筹码并入账。\n'
            '右键“再来一局”可查看上局实际发牌顺序。', parent=self)

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
        self.current_poker_folder = ('Poker2' if self.current_poker_folder=='Poker1' else 'Poker1') if hasattr(self,'current_poker_folder') else random.choice(['Poker1','Poker2'])
        folder = self.current_poker_folder
        self.original_images = {}
        base = str(project_root() / 'A_Tools' / 'Card' / folder)
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


    def _register_spot(self, seat, kind, cx, cy, border, label, angle=0):
        c,tag = self.canvas,'spot_'+seat+'_'+kind
        if label is not None:
            self._text(cx,cy,label,14,PANEL_BG,
                       angle=angle,justify='center',tags=tag)
        self.bet_spots[(seat,kind)] = dict(tag=tag,center=(cx,cy),border=border)
        # Main wagers use canvas coordinate hit testing so fills, holes,
        # numerals and chip overlays all trigger exactly one wager action.
        if kind != 'main':
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


    @staticmethod
    def _chip_label(amount):
        value=round(float(amount),2)
        if abs(value)>=1000:return SuperPan9GUI._compact(value)
        return f'{value:.0f}' if value.is_integer() else f'{value:.2f}'


    def _draw_chip(self, tag, amount, x, y, rectangular=False, extra_tags=(), show_amount=True):
        c=self.canvas;tags=(tag,*extra_tags)
        if rectangular:
            # 保留原筹码绘制接口，支持长金额标签。
            label=self._chip_label(amount);width=max(96,10*len(label)+16)
            c.create_rectangle(x-width/2,y-18,x+width/2,y+18,fill='#731D2A',outline='#000000',width=1,tags=tags)
            if show_amount:self._text(x,y,label,11,'#FFF0C3',tags=tags)
        else:
            radius=self.BET_CHIP_RADIUS;color=self._chip_color(amount)
            c.create_oval(x-radius,y-radius,x+radius,y+radius,fill=color,outline='#000000',width=1,tags=tags)
            label=self._compact(amount)
            self._text(x,y,label,10 if len(label)>=5 else 12,TEXT if color in (BLACK,RED) else BLACK,tags=tags)


    def _render_chips(self):
        self.canvas.delete('bet_chips')
        # 本金先画；95%净盈利位于左上方。
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


    def _outcome_transfers(self, seat, kind, stake, returned):
        """本金留位，盈利派至左上；输注立即飞向统一庄家收筹码点，平局不动。"""
        if not stake:return []
        key=(seat,kind,'stake');center=self.bet_spots[(seat,kind)]['center']
        if returned<=0:
            chip=self.visual_chips.pop(key,None)
            return [dict(amount=chip['amount'],start=chip['xy'],target=self.HOUSE_CHIP_POS,duration=280)] if chip else []
        profit=round(returned-stake,2)
        if profit<=0:return []
        target=(center[0]-32,center[1]-30)
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
                self.balance=float(money(self.balance)+money(self.last_win))
                self._credited=True
            self._return_persisted=self._persist_balance()
            return self._return_persisted
        finally:
            self._crediting=False


    def _close_card_sequence(self):
        current=getattr(self,'_sequence_window',None)
        if current is not None:
            try:
                if current.winfo_exists():current.destroy()
            except tk.TclError:pass
        self._sequence_window=None

    def _pause_csm_error(self, exc):
        self._decision_busy = False
        self.game.stage = 'csm_error'
        self._status('连续洗牌机异常，本局暂停。关闭游戏将退回本局下注并释放牌仓。')
        self._refresh()
        messagebox.showerror('连续洗牌机', f'{exc}\n本局尚未结算，请关闭游戏归还牌张及下注。', parent=self)

    def _complete_chip_return(self):
        if self.game.stage not in ('returning', 'credit_pending'):
            return
        self.game.stage = 'credit_pending'
        if not self._credit_round_return():
            self._refresh()
            return
        try:
            self.game.deck.finish_round()
        except Exception as exc:
            self.game.stage = 'csm_return_error'
            self._status('余额已入账；归还牌张失败，请关闭游戏释放牌仓。')
            self._refresh()
            messagebox.showerror('连续洗牌机', f'牌张归还失败：{exc}\n余额已入账，不会重复派彩。请关闭游戏。', parent=self)
            return
        self.game.stage = 'sweeping'
        self.canvas.delete('returned_chips')
        self._refresh()
        self._sweep_all_cards()

    def show_card_sequence(self, event=None):
        if self.game.stage != 'await_restart' or not self._history_available:
            return
        snapshot = self.last_round_snapshot
        if not snapshot:
            return
        current = getattr(self, '_sequence_window', None)
        if current is not None and current.winfo_exists():
            current.lift()
            return
        window = tk.Toplevel(self)
        self._sequence_window = window
        window.title('上局实际发牌顺序 · Super Pan 9')
        window.configure(bg=ROOT_BG)
        window.resizable(False, False)
        tk.Label(window, text='上局已发出的牌（不显示连续洗牌机内未发牌张）',
                 bg=ROOT_BG, fg=GOLD, font=('Arial', 13, 'bold')).pack(padx=15, pady=15)
        frame = tk.Frame(window, bg=ROOT_BG)
        frame.pack(padx=15, pady=10)
        window._card_images = []
        for i, (card, (side, index)) in enumerate(zip(snapshot['cards'], snapshot['sequence'])):
            photo = ImageTk.PhotoImage(snapshot['images'][(card.suit, card.rank)].resize(
                (60, 84), Image.Resampling.LANCZOS), master=window)
            window._card_images.append(photo)
            cell = tk.Frame(frame, bg=ROOT_BG)
            cell.grid(row=i//6, column=i%6, padx=10, pady=8)
            tk.Label(cell, image=photo, bg=ROOT_BG).pack()
            label = f'{i+1}. {self.SEAT_NAMES[side]}' + (' 补牌' if index == 3 else '')
            tk.Label(cell, text=label, bg=ROOT_BG, fg=TEXT).pack()

    def on_close(self):
        if self._closing or self._crediting:
            return
        settled = self.game.settlement is not None
        if not getattr(self, '_close_pending', False):
            interrupted = self.game.stage == 'csm_error'
            if self.game_in_progress and not settled and not interrupted and self.game.stage != 'funding_pending':
                messagebox.showinfo('牌局进行中', '请先完成两位玩家的决定和结算。', parent=self)
                return
            self._close_refund_due = interrupted or self.game.stage == 'funding_pending'
            self._close_pending = True
            self._cancel_restart_timer()
            self._cancel_jobs()
        self.game.stage = 'closing_pending'
        self._status('正在保存余额并释放牌仓；失败时可再次关闭重试。')
        self._refresh()
        shoe = self.game._shoe
        if shoe is not None and not getattr(self, '_csm_released', False):
            try:
                shoe.close()
                self._csm_released = True
            except Exception as exc:
                messagebox.showerror('连续洗牌机', f'退出时释放牌仓失败：{exc}\n请再次关闭以重试。', parent=self)
                return
        if settled:
            if not self._credit_round_return():
                return
        elif self._close_refund_due:
            if not getattr(self, '_abort_refunded', False):
                stake = sum((money(b['main']) for b in self.game.bets.values()), Decimal(0))
                self.balance = float(money(self.balance) + stake)
                self._abort_refunded = True
            if not self._persist_balance():
                return
        elif not self._persist_balance():
            return
        self._closing = True
        self._cancel_restart_timer()
        self._cancel_jobs()
        self._unbind_enter()
        self._close_card_sequence()
        if callable(self.on_back):
            self.on_back(float(self.balance))
        else:
            self.winfo_toplevel().destroy()

    def _on_destroy(self, event):
        if event.widget is not self:
            return
        self._closing = True
        self._cancel_jobs()
        self._unbind_enter()
        # Normal exits go through on_close; this only releases an externally
        # destroyed Frame's leases and never duplicates normal payouts.
        if self.game._shoe is not None and not getattr(self, '_csm_released', False):
            try:
                self.game._shoe.close()
                self._csm_released = True
            except Exception as exc:
                print(f'Super Pan 9: CSM release on destroy failed: {exc}', file=sys.stderr)


# Keep the original imported class names available to existing menu/launcher code.
ThreeCardPokerGame = SuperPan9Game
ThreeCardPokerGUI = SuperPan9GUI


def main(initial_balance=10000, username='Guest', *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """Original embedding API; account callbacks receive a numeric balance."""
    actual_balance = initial_balance if balance is None else balance
    actual_user = username if user is None else user
    if parent is not None:
        return SuperPan9GUI(parent, actual_balance, actual_user,
                           on_back=on_back, on_balance_change=on_balance_change)
    root = tk.Tk()
    root.title('Super Pan 9 · 超级大满贯 9')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)
    page = SuperPan9GUI(root, actual_balance, actual_user, on_balance_change=on_balance_change)
    page.pack(fill='both', expand=True)
    def close_standalone(final_balance):
        if callable(on_back):
            on_back(final_balance)
        root.destroy()
    page.on_back = close_standalone
    root.protocol('WM_DELETE_WINDOW', page.on_close)
    root.mainloop()
    return page.balance


if __name__ == '__main__':
    print(f'Final balance: {main()}')


