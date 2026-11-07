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

# Blackjack Multiply — Classic canvas UI, original Multiply rules, CSM
import json
import math
import os
import random
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter import font as tkfont

# Project layout:
#   A_Tools/Card/CSM_Shuffler.py
#   A_Tools/Casino_Games/Blackjack_Classic_CSM.py
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

BLACKJACK_VERSION = "MULTIPLY-CLASSIC-UI-CSM-V3"

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageTk = None
    ImageDraw = None
    ImageFont = None

# -----------------------------------------------------------------------------
# Balance compatibility with the Baccarat module
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
# CSM-backed ENHC Blackjack shoe / hand helpers
# -----------------------------------------------------------------------------
class BlackjackEngine:
    SUITS = ('Club', 'Diamond', 'Heart', 'Spade')
    RANKS = ('A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K')

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

    def draw_card(self):
        if not self.round_open:
            raise RuntimeError('牌局尚未开始。')
        if len(self.card_buffer) <= 3:
            self._request_next_chamber()
        record = self.card_buffer.pop(0)
        self.used_by_batch.setdefault(self.current_batch_id, []).append(record['card_id'])
        return record['suit'], record['rank']

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

    @staticmethod
    def burn_value(card):
        rank = card[1]
        if rank == 'A':
            return 1
        if rank in ('10', 'J', 'Q', 'K'):
            return 10
        return int(rank)

    @staticmethod
    def split_value(card):
        rank = card[1]
        if rank == 'A':
            return 11
        if rank in ('10', 'J', 'Q', 'K'):
            return 10
        return int(rank)

    @staticmethod
    def hand_value(cards):
        total = 0
        aces = 0
        for _suit, rank in cards:
            if rank == 'A':
                total += 11
                aces += 1
            elif rank in ('10', 'J', 'Q', 'K'):
                total += 10
            else:
                total += int(rank)
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total, aces > 0

    @classmethod
    def is_blackjack(cls, cards):
        return len(cards) == 2 and cls.hand_value(cards)[0] == 21

# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

class MultiplyRules:
    """Tuple-card version of the rules in the supplied Blackjack_Multiply.py."""
    MAX_SPECIAL_CARDS = 5
    CARD_COUNT_TIERS = ((0.75, 2), (0.90, 3), (0.97, 4), (1.0, 5))
    MULTIPLIER_TIERS = ((0.60, 2.5), (0.85, 5.0), (0.975, 10.0), (0.995, 25.0), (1.0, 50.0))

    @classmethod
    def generate_offer(cls):
        roll = random.random()
        count = next(count for threshold, count in cls.CARD_COUNT_TIERS if roll < threshold)
        all_cards = [(suit, rank) for suit in BlackjackEngine.SUITS for rank in BlackjackEngine.RANKS]
        cards = random.sample(all_cards, count)
        roll = random.random()
        multiplier = next(mult for threshold, mult in cls.MULTIPLIER_TIERS if roll < threshold)
        return cards, multiplier

    @staticmethod
    def match_count(cards, special_cards):
        targets = set(special_cards)
        return sum(card in targets for card in cards)

    @classmethod
    def apply_multiplier(cls, base_return, cards, special_cards, multiplier, stake=0.0):
        matches = cls.match_count(cards, special_cards)
        coefficient = float(multiplier) * matches if matches else 1.0
        principal = min(max(0.0, float(stake)), max(0.0, float(base_return)))
        profit = max(0.0, float(base_return)-principal)
        return dict(final_return=round(principal+profit*coefficient, 2),
            multiplier=float(multiplier), match_count=matches, coefficient=coefficient)

    @classmethod
    def settle_main(cls, cards, dealer_cards, stake, special_cards, multiplier, from_split=False):
        player_total, _ = BlackjackEngine.hand_value(cards)
        dealer_total, _ = BlackjackEngine.hand_value(dealer_cards)
        natural = not from_split and BlackjackEngine.is_blackjack(cards)
        dealer_bj = BlackjackEngine.is_blackjack(dealer_cards)
        if natural and dealer_bj:
            state, base_return, label = 'push', stake, '双方Blackjack 平局'
        elif dealer_bj or player_total > 21:
            state, base_return, label = 'lose', 0.0, '庄家Blackjack' if dealer_bj else '玩家爆牌'
        elif natural:
            state, base_return, label = 'win', stake * 2.5, 'Blackjack 3:2'
        elif dealer_total > 21 and len(dealer_cards) == 3:
            state, base_return, label = 'push', stake, '庄家三张爆牌 主注平局'
        elif dealer_total > 21 or player_total > dealer_total:
            state, base_return, label = 'win', stake * 2.0, '主注获胜'
        elif player_total == dealer_total:
            state, base_return, label = 'push', stake, '同点平局'
        else:
            state, base_return, label = 'lose', 0.0, '主注输'
        if state == 'win':
            result = cls.apply_multiplier(base_return, cards, special_cards, multiplier, stake=stake)
            if result['match_count']:
                label += f' · 加倍 ×{multiplier:g} ×{result["match_count"]}张'
        else:
            result = dict(final_return=float(base_return), multiplier=float(multiplier),
                match_count=cls.match_count(cards, special_cards), coefficient=1.0)
        result.update(settlement=state, label=label)
        return result

class BubbleBlackjackGame(tk.Frame):
    CASHOUT_FACTOR = 0.90
    WIDTH = 1150
    HEIGHT = 750
    GAME_X0 = 12
    GAME_X1 = 1138
    HISTORY_X0 = 778  # compatibility only; no right-side panel in Blackjack
    HISTORY_X1 = 1138

    BG = '#1B3D31'
    PANEL = '#183B30'
    PANEL_LINE = '#6C7850'
    FELT = '#083f38'
    FELT_2 = '#0c5148'
    LINE = '#c3d5ca'
    GOLD = '#D4AF37'
    PLAYER_BLUE = '#3d67d8'
    DEALER_RED = '#d94a4e'
    TIE_GREEN = '#43a665'
    PUSH_BLUE = '#b9dcff'

    MIN_BET = 100.0
    MAX_MAIN_BET = 500_000.0
    MAX_SIDE_BET = 100_000.0
    MAX_SPLIT_ACTIONS = 3       # one original hand, up to three splits
    MAX_HANDS = 4
    SEATS = ('Player1',)
    SEAT_NAMES = {'Player1': '玩家'}
    SEAT_BOUNDS = {'Player1': (22.0, 1128.0)}
    ZONE_COLORS = {'Player1': '#35634B'}
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    SIDE_BET_DIAMETER = 122.0 * 2 / 3
    BLACKJACK_PROFIT = 1.5      # 3:2
    INSURANCE_PROFIT = 2.0      # 2:1
    SPLIT_ACES_ONE_CARD_ONLY = True
    SIDE_BET_KEYS = ('Perfect Pair', '21+3', '3 Card Bust', 'Crazy 7', 'Hot 21', 'Bust!')
    SIDE_BET_LABELS = {
        'Perfect Pair': '完美对子',
        '21+3': '21+3',
        '3 Card Bust': '3张爆牌',
        'Crazy 7': '疯狂7',
        'Hot 21': '热辣21',
        'Bust!': '爆牌！',
    }
    SIDE_BET_ODDS_TEXT = {
        'Perfect Pair': '25/12/6:1',
        '21+3': '100/40/30/10/5:1',
        '3 Card Bust': '9:2 (4.5:1)',
        'Crazy 7': '2000/500/150/25/5:1',
        'Hot 21': '500/100/20/4/2/1:1',
        'Bust!': '250/100/50/9/2/1:1',
    }

    M_CHIP_COLOR = '#102d47'

    CHIP_SPECS = [
        (100, '#202020', '100'),
        (500, '#FF7DDA', '500'),
        (1000, '#ab0058', '1K'),
        (5000, '#ba3438', '5K'),
        (10000, '#70439a', '10K'),
        (50000, '#FFD166', '50K'),
        (250000, '#ffffff', '250K'),
    ]


    # Shared HCI geometry for stationary chips, split hands and animations.
    WAGER_CHIP_RADIUS = 30.0
    INSURANCE_CHIP_RADIUS = 20.0
    CHIP_RIM_INSET = 3.0
    CHIP_GAP = 4.0
    CHIP_PITCH = 2 * WAGER_CHIP_RADIUS + CHIP_GAP
    MAIN_BET_RADIUS = 48.0
    MAIN_BET_Y = 557.0
    MAIN_RING_START = 140.0
    MAIN_RING_EXTENT = 260.0
    MAIN_WAGER_LIFT = 72.0
    CARD_WAGER_GAP = 6.0

    def __init__(self, parent, balance=10000, user=None, on_back=None,
                 on_balance_change=None, close_returns_to_parent=False):
        super().__init__(parent, bg=self.BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username = user
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        # V23: casino_games explicitly opts in to turning the root-window X
        # into a page-level Back action. Other embedded hosts keep their own X.
        self.close_returns_to_parent = bool(close_returns_to_parent)
        self.balance = float(balance)
        self.final_balance = float(balance)

        # Pick a CJK-capable UI font at runtime so Chinese labels render on both
        # Windows and Linux/macOS development environments.
        try:
            families = set(tkfont.families(self))
        except Exception:
            families = set()
        self.cn_font = next((name for name in (
            'Microsoft YaHei UI', 'Microsoft YaHei', '微软雅黑', 'Noto Sans CJK SC',
            'SimHei', '黑体', 'Arial Unicode MS') if name in families), 'Arial')
        self.chip_font = next((name for name in ('Arial', 'Liberation Sans', 'DejaVu Sans')
                               if name in families), 'Arial')
        self._chip_fonts = {}

        # One stable local game identity is used so an orderly restart can
        # recover any chamber lease left by the previous instance.
        import uuid
        self.csm_game_id = f"MultiplyBlackjack:{self.username or 'local'}:{uuid.uuid4().hex}"
        self.csm = ContinuousShuffleMachine()
        self.engine = BlackjackEngine(self.csm, self.csm_game_id)
        self.selected_chip = 1000.0
        self.current_bet = 0.0
        self.current_bets = {seat: 0.0 for seat in self.SEATS}
        self.last_bets = {seat: 0.0 for seat in self.SEATS}
        self.round_original_bets = {seat: 0.0 for seat in self.SEATS}
        self.split_actions_by_seat = {seat: 0 for seat in self.SEATS}
        self.seat_insurance = {seat: dict(bet=0.0, returned=0.0, visible=False) for seat in self.SEATS}
        self.insurance_resolved = False
        self.ace_decision_seat = None
        self.ace_decision_queue = []
        self.seat_deal_sequences = {seat: [] for seat in self.SEATS}
        self.round_initial_cards = {}
        self.current_side_bets = self._empty_side_bets()
        self.last_bet = 0.0
        self.last_side_bets = self._empty_side_bets()
        self.last_win_amount = 0.0
        self.show_last_win = False
        self.round_original_bet = 0.0
        self.round_side_bets = self._empty_side_bets()
        self.insurance_bet = 0.0
        self.insurance_result = ''
        self.insurance_return_amount = 0.0
        self.insurance_chip_visible = False
        self.flash_insurance_rule = False
        self.ace_decision_mode = None  # None / 'insurance' / 'even_money'
        self.bet_layout_mode = 'home'
        self.previous_round_cards_present = False
        self.hands = []
        self.active_hand_index = 0
        self.dealer_cards = []
        self.round_deal_sequence = []
        self.side_bet_results = {}
        self.side_bet_return_amounts = {}
        # V10: record the ACTUAL winning tier even when the player did not wager.
        # These maps drive unconditional side-bet flashes/odds badges at settlement.
        self.side_bet_hit_odds = {}
        self.side_bet_hit_labels = {}
        # V18: resolved losing side-bet chips are physically collected upward
        # during live play and must no longer be drawn at their betting spots.
        self.side_bet_early_collected = set()
        self.split_actions = 0
        self.round_active = False
        self.accept_bets = False
        self.animation_running = False
        # True only while the dealer is actively revealing/drawing cards.  V16 uses
        # this to recolour the already-visible side-bet pointed markers.
        self.dealer_phase_active = False
        self.settlement_running = False
        self.dealer_three_card_main_push = False
        self._dealer_notice_source = None
        self._dealer_notice_photo = None
        self._dealer_notice_image_item = None
        self._dealer_notice_text_item = None
        self._dealer_notice_level = 0.0
        self._dealer_notice_target = False
        self._dealer_notice_job = None
        self.settlement_visual_stage = None
        self.pending_profit_chips = set()
        self._opening_wager_animation = False
        self.settlement_flash_step = 0
        self.flash_mode = None
        self.flash_winning_side_bets = set()
        self.flash_main_bet = False
        self.flash_main_push_only = False
        # V6: main-game settlement is tracked per player hand instead of one
        # global MAIN spot. This lets a losing split hand disappear while other
        # winning split hands keep their own base/double chips and flash.
        self.flash_winning_hand_indices = set()
        self.hand_zone_bounds = []
        # V7: exact positions of each split-hand wager inside the Evoplay MAIN oval.
        # Used both for drawing the 1–5 base chips / Double chip and settlement flash.
        self.main_wager_positions = {}
        self.bet_chip_animation_count = 0
        self.pending_bet_animation = {(seat, key): 0.0 for seat in self.SEATS for key in ('MAIN',)+self.SIDE_BET_KEYS}
        self._closing = False
        self.last_result_lines = []  # internal only; never shown to the player
        self.runtime_data_file = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..',
                'A_Logs',
                'Json',
                'Blackjack_Multiply.json'
            )
        )
        self.shoe_resumed = False

        self.card_items = []
        self.temp_images = []
        self.external_card_images = {}
        self.external_card_pil = {}
        self.external_golden_card_images = {}
        self.external_golden_card_pil = {}
        self.golden_card_asset_dir = None
        self.external_back_image = None
        self.external_back_pil = None
        self.card_asset_dir = None
        self._temp_flip_images = {}
        self._round_anim_item = None

        self.chip_selector_items = {}
        self.chip_selector_centers = {}
        self.action_buttons = {}
        self.decision_buttons = {}
        self.control_buttons = {}
        self.bet_spots = {}
        self.side_bet_spots = {}
        self.after_ids = []

        self.special_cards = []
        self.special_multiplier = 1.0
        self.special_card_photos = {}
        self._special_offer_running = False
        self._special_offer_preview = None
        self._special_offer_render_state = None
        self.load_original_card_assets()
        self.create_ui()
        self.select_chip(self.selected_chip)
        self.shoe_resumed = self.load_runtime_store()
        self.update_display()

        top = self.winfo_toplevel()
        self._host_toplevel = top
        self._embedded_wm_delete_previous = None
        self._embedded_wm_delete_installed = False
        # V23: Blackjack may be embedded by casino_games.py in the SAME Tk root.
        # Save the root-level key bindings so they can be restored before
        # on_back() replaces this game Frame with CasinoGamesPage.
        try:
            self._previous_return_binding = top.bind('<Return>') or ''
            self._previous_escape_binding = top.bind('<Escape>') or ''
        except tk.TclError:
            self._previous_return_binding = ''
            self._previous_escape_binding = ''
        self._host_bindings_restored = False

        self._host_bindings_restored = False

        try:
            top.bind('<Return>', self.handle_enter)
            top.bind('<Escape>', lambda _e: self.exit_game())
        except tk.TclError:
            pass
        try:
            top.bind('<Return>', self.handle_enter)
            top.bind('<Escape>', lambda _e: self.exit_game())
        except tk.TclError:
            pass

        self.accept_bets = True
        self.update_display()

    # ------------------------------------------------------------------ assets
    def find_original_card_asset_dir(self):
        current = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(current, 'A_Tools', 'Card', 'Poker2'),
            os.path.join(os.path.dirname(current), 'A_Tools', 'Card', 'Poker2'),
            os.path.join(os.path.dirname(os.path.dirname(current)), 'A_Tools', 'Card', 'Poker2'),
        ]
        for directory in candidates:
            if os.path.isdir(directory) and os.path.exists(os.path.join(directory, 'Background.png')):
                return directory
        return None

    def load_original_card_assets(self):
        if Image is None or ImageTk is None:
            return
        directory = self.find_original_card_asset_dir()
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        self._load_golden_card_assets(directory)
        if directory:
            try:
                for suit in BlackjackEngine.SUITS:
                    for rank in BlackjackEngine.RANKS:
                        path = os.path.join(directory, f'{suit}{rank}.png')
                        if not os.path.exists(path):
                            continue
                        base = Image.open(path).convert('RGBA').resize((self.CARD_WIDTH, self.CARD_HEIGHT), resample)
                        self.external_card_pil[(suit, rank)] = base
                        self.external_card_images[(suit, rank)] = ImageTk.PhotoImage(base, master=self)
                back_path = os.path.join(directory, 'Background.png')
                if os.path.exists(back_path):
                    back = Image.open(back_path).convert('RGBA').resize((self.CARD_WIDTH, self.CARD_HEIGHT), resample)
                    self.external_back_pil = back
                    self.external_back_image = ImageTk.PhotoImage(back, master=self)
                if self.external_card_images and self.external_back_image is not None:
                    self.card_asset_dir = directory
                    return
            except Exception:
                self.external_card_images.clear()
                self.external_card_pil.clear()
                self.external_back_image = None
                self.external_back_pil = None

        # Fallback art
        try:
            self.external_back_pil = self._make_fallback_card_pil(None, False)
            self.external_back_image = ImageTk.PhotoImage(self.external_back_pil, master=self)
            for suit in BlackjackEngine.SUITS:
                for rank in BlackjackEngine.RANKS:
                    card = (suit, rank)
                    base = self._make_fallback_card_pil(card, True)
                    self.external_card_pil[card] = base
                    self.external_card_images[card] = ImageTk.PhotoImage(base, master=self)
        except Exception:
            self.external_card_images.clear()
            self.external_card_pil.clear()
            self.external_back_image = None
            self.external_back_pil = None

    def _load_golden_card_assets(self, directory):
        """Use Bet Stacker's Poker2/Golden/{suit}{rank}.png face assets."""
        if Image is None or ImageTk is None:
            return
        golden_directory = os.path.join(directory, 'Golden') if directory else None
        self.golden_card_asset_dir = golden_directory
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        for suit in BlackjackEngine.SUITS:
            for rank in BlackjackEngine.RANKS:
                card = (suit, rank)
                path = os.path.join(golden_directory, f'{suit}{rank}.png') if golden_directory else None
                base = None
                if path and os.path.isfile(path):
                    try:
                        with Image.open(path) as source_image:
                            base = source_image.convert('RGBA').resize(
                                (self.CARD_WIDTH, self.CARD_HEIGHT), resample)
                    except (OSError, ValueError):
                        pass
                if base is None:
                    # Missing artwork must retain the Golden appearance.
                    base = self._make_fallback_card_pil(card, golden=True)
                self.external_golden_card_pil[card] = base
                self.external_golden_card_images[card] = ImageTk.PhotoImage(base, master=self)

    def _make_fallback_card_pil(self, card, face_up=True, golden=False):
        face_color = '#ffedaa' if golden else '#f4efe4'
        face_border = '#d5a52d' if golden else '#d7cbb9'
        image = Image.new('RGBA', (100, 140), face_color if face_up else '#253e66')
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((2, 2, 97, 137), radius=8,
                               outline=face_border if face_up else '#d7c46a', width=3)
        if not face_up:
            draw.rectangle((12, 12, 87, 127), outline='#e4d490', width=2)
            draw.line((16, 16, 83, 123), fill='#e4d490', width=2)
            draw.line((83, 16, 16, 123), fill='#e4d490', width=2)
            return image.resize((self.CARD_WIDTH, self.CARD_HEIGHT), getattr(Image, 'Resampling', Image).LANCZOS)
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
        return image.resize((self.CARD_WIDTH, self.CARD_HEIGHT), getattr(Image, 'Resampling', Image).LANCZOS)

    # --------------------------------------------------------------------- UI
    def create_ui(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=self.BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_rectangle(0, 0, self.WIDTH, self.HEIGHT,
                                     fill=self.BG, outline='', tags='static')
        self.draw_animation_panel()
        self.draw_board()
        self.draw_bottom_controls()

    def draw_animation_panel(self):
        c = self.canvas
        self.animation_panel = (22, 44, 1128, 617)
        c.create_text(575, 18, text='加倍黑杰克  MULTIPLY BLACKJACK',
                      font=(self.cn_font, 16, 'bold'), fill=self.GOLD, tags='static')
        self.dealer_zone_rect = c.create_rectangle(355, 44, 795, 197,
                                                   fill='#4b1e22', outline='', tags='static')
        c.create_text(575, 57, text='庄家', font=(self.cn_font, 16, 'bold'),
                      fill='#F2E6C9', tags='static')
        self.seat_zone_rects = {}
        self.seat_title_items = {}
        for seat, (x0, x1) in self.SEAT_BOUNDS.items():
            self.seat_zone_rects[seat] = c.create_rectangle(
                x0, 252, x1, 617, fill=self.ZONE_COLORS[seat], outline='', tags='static')
            self.seat_title_items[seat] = c.create_text(
                (x0+x1)/2, 266, text=self.SEAT_NAMES[seat],
                font=(self.cn_font, 16, 'bold'), fill='#F2E6C9', tags='static')
        # Same three-column limit table and gold/green palette as Caribbean Stud.
        c.create_rectangle(30, 75, 349, 181, fill='#183B30', outline=self.GOLD, tags='static')
        c.create_rectangle(30, 75, 349, 104, fill='#40634B', outline=self.GOLD, tags='static')
        c.create_text(189.5, 89, text='下注上限', font=(self.cn_font, 13, 'bold'),
                      fill='#F2E6C9', tags='static')
        for col, (label, amount) in enumerate((('主注最低', self.MIN_BET),
                                               ('主注最高', self.MAX_MAIN_BET),
                                               ('边注最高', self.MAX_SIDE_BET))):
            left, right = 30+col*319/3, 30+(col+1)*319/3
            c.create_rectangle(left, 104, right, 141, outline='#77906B', tags='static')
            c.create_rectangle(left, 141, right, 181, outline='#77906B', tags='static')
            c.create_text((left+right)/2, 122, text=label, font=(self.cn_font, 11, 'bold'),
                          fill='#F2E6C9', tags='static')
            c.create_text((left+right)/2, 161, text=f'${amount:,.0f}',
                          font=(self.cn_font, 12, 'bold'), fill=self.GOLD, tags='static')
        self.insurance_positions = {'Player1': (575.0, 224.0)}
        self.dealer_total_text = c.create_text(575, 193, text='', state='hidden')
        self.rule_strip_bounds = (22.0, 200.0, 1128.0, 248.0)
        self.rule_strip_rect = c.create_rectangle(*self.rule_strip_bounds,
            fill='#173C2E', outline='#65784B', tags='round_rule_strip')
        c.create_line(25, 201, 1125, 201, fill='#E0C879', width=2, tags='round_rule_strip')
        c.create_line(25, 247, 1125, 247, fill='#0C241B', width=2, tags='round_rule_strip')
        self.rule_strip_text = c.create_text(575, 224,
            text='庄家任何17点停牌   保险2:1   黑杰克3:2   庄家3张爆牌主注平局',
            font=(self.cn_font, 13, 'bold'), fill=self.GOLD, tags='rule_strip_text')
        self.rule_strip_left_text = c.create_text(545, 224, text='', state='hidden')
        self.rule_strip_right_text = c.create_text(605, 224, text='', state='hidden')
        self.rule_strip_chip_pos = (575, 224)  # legacy helper compatibility
        self.draw_special_offer()
        self.shoe_origin = (575, 52)  # identical to Caribbean Stud's deal origin

    def draw_board(self):
        c = self.canvas
        self.bet_spots, self.side_bet_spots = {}, {}
        for seat, (x0, x1) in self.SEAT_BOUNDS.items():
            cx = (x0+x1)/2
            # MAIN stays circular; side titles have their own row below the amount.
            radius = self.SIDE_BET_DIAMETER/2
            layouts = {'MAIN': self._bet_surface_layout(cx, main=True)}
            for kind, x in zip(self.SIDE_BET_KEYS, (135, 285, 435, 715, 865, 1015)):
                layouts[kind] = self._bet_surface_layout(x)
            for index, (kind, (bounds, label_pos, chip_pos)) in enumerate(layouts.items()):
                key = (seat, kind)
                tag = f'bet_{seat}_{index}'
                fill = '#2677A6' if kind=='MAIN' else '#173B32'
                outline = '#B9D8E8' if kind=='MAIN' else self.GOLD
                shape = self._draw_bet_surface(bounds, fill, outline, tag, kind == 'MAIN')
                label = None
                if kind!='MAIN':
                    label = c.create_text(*label_pos, text=self.SIDE_BET_LABELS[kind],
                        font=(self.cn_font, -14, 'bold'), fill='#F2E6C9',
                        tags=(tag, 'betting_spot_label'))
                spot = dict(key=key, bounds=bounds, label_pos=label_pos, chip_pos=chip_pos,
                    rect=shape, label=label, tag=tag, shape='oval' if kind == 'MAIN' else 'rounded_rect', normal_fill=fill,
                    normal_outline=outline, normal_width=2)
                self.bet_spots[key] = spot
                if spot['shape'] == 'oval':
                    self._decorate_main_bet_surface(spot)
                if kind != 'MAIN':
                    self.side_bet_spots[key] = spot
                c.tag_bind(tag, '<Button-1>', lambda _e, s=seat, k=kind: self._place_seat_bet(s, k))
                c.tag_bind(tag, '<Button-3>', lambda _e, s=seat, k=kind: self._clear_seat_bet(s, k))
                c.tag_bind(tag, '<Enter>', lambda _e: c.configure(cursor='hand2'))
                c.tag_bind(tag, '<Leave>', lambda _e: c.configure(cursor=''))
        self.bet_layout_mode = 'home'
        self.update_bet_chips()

    def draw_bottom_controls(self):
        c = self.canvas
        c.create_rectangle(0, 625, 1150, 748, fill=self.BG, outline='#6C7850', width=2,
                           tags='controls')
        self.balance_text = c.create_text(10, 665, anchor='w', text='',
            font=(self.cn_font, 18, 'bold'), fill='white', tags='controls')
        self.total_bet_text = c.create_text(10, 710, anchor='w', text='',
            font=(self.cn_font, 18, 'bold'), fill='white', tags='controls')
        self.clear_button = self._create_canvas_button(278, 650, 344, 704, '清除',
            self.clear_bets, '#9B403A', tag='control_clear', font_size=11)
        diameter, gap = 56, 8
        chip_x = (self.WIDTH-(len(self.CHIP_SPECS)*diameter+(len(self.CHIP_SPECS)-1)*gap))/2
        for value, color, label in self.CHIP_SPECS:
            tag = f'chip_select_{value}'
            outer = c.create_oval(chip_x, 646, chip_x+56, 702, fill='#182F25',
                outline='#6C7850', width=3, tags=(tag, 'chip_selector'))
            inner = c.create_oval(chip_x+5, 651, chip_x+51, 697, fill=color,
                outline='#F2E6C9', width=2, tags=(tag, 'chip_selector'))
            text = c.create_text(chip_x+28, 674, text=label,
                font=self._fit_chip_font(label, 25), fill=self.contrast_text_color(color),
                tags=(tag, 'chip_selector'))
            self.chip_selector_items[value] = (outer, inner, text)
            self.chip_selector_centers[float(value)] = (chip_x+28, 674)
            c.tag_bind(tag, '<Button-1>', lambda _e, v=value: self.select_chip(v))
            chip_x += diameter+gap
        self.info_button = self._create_canvas_button(810, 650, 855, 695, '?',
            self.show_game_instructions, '#173f66', tag='control_info', font_size=17)
        self.repeat_button = self._create_canvas_button(862, 638, 1000, 708, '重复下注',
            self.repeat_last_bet, '#536A43', tag='control_repeat', font_size=11)
        self.deal_button = self._create_canvas_button(1012, 628, 1138, 720, '开牌\nENTER',
            self.deal_cards, '#D8B46A', fg='#2A1B08', tag='control_deal', font_size=14)
        specs = (('hit', '要牌', self.hit, '#397A48'),
                 ('stand', '停牌', self.stand, "#FC003F"),
                 ('double', '加倍', self.double, '#A57A36'),
                 ('split', '分牌', self.split, '#635182'),
                 ('surrender', '投降\n退还45%', self.instant_surrender, '#9B403A'))
        for seat, (x0, x1) in self.SEAT_BOUNDS.items():
            for index, (action, label, command, color) in enumerate(specs):
                left = 278+index*174
                self.action_buttons[(seat, action)] = self._create_canvas_button(
                    left, 638, left+164, 720, label,
                    lambda s=seat, cmd=command: self._invoke_seat_action(s, cmd), color,
                    tag=f'action_{seat}_{action}', font_size=12)
            for action, left, right, label, accept in (
                    ('accept', 405, 565, '购买保险', True),
                    ('decline', 585, 745, '不购买', False)):
                self.decision_buttons[(seat, action)] = self._create_canvas_button(
                    left, 642, right, 716, label, lambda a=accept: self._resolve_ace_decision(a),
                    '#A57A36' if accept else '#173f66', tag=f'decision_{seat}_{action}', font_size=12)
        self._set_round_control_visibility(False)

    def _create_canvas_button(self, x0, y0, x1, y1, text, command, color,
                              fg='white', tag=None, font_size=12):
        tag = tag or f'button_{len(self.control_buttons)}'
        c = self.canvas
        rim = c.create_rectangle(x0, y0, x1, y1, fill=self._shade_color(color, .55),
            outline='#b7a58d', width=2, tags=(tag, 'ui_button'))
        face = c.create_rectangle(x0+4, y0+4, x1-4, y1-4, fill=color,
            outline=self._shade_color(color, 1.25), width=2, tags=(tag, 'ui_button'))
        highlight = c.create_line(x0+8, y0+8, x1-8, y0+8,
            fill=self._shade_color(color, 1.45), width=2, tags=(tag, 'ui_button'))
        y = (y0+y1)/2-1
        text_id = c.create_text((x0+x1)/2, y, text=text, font=(self.cn_font, font_size, 'bold'),
                                fill=fg, justify='center', tags=(tag, 'ui_button'))
        button = dict(rect=face, rim=rim, highlight=highlight, text=text_id, tag=tag,
                      command=command, color=color, fg=fg, enabled=True, visible=True,
                      pressed=False, text_y=y)
        self.control_buttons[tag] = button
        def inside(event):
            if event is None or not button['visible']:
                return False
            x, pointer_y = c.canvasx(event.x), c.canvasy(event.y)
            return x0-1 <= x <= x1+1 and y0-1 <= pointer_y <= y1+1
        def enter(_event=None):
            c.configure(cursor='hand2' if button['enabled'] else '')
            if button['enabled'] and not button['pressed']:
                c.itemconfigure(face, fill=self._shade_color(color, 1.12))
        def leave(event=None):
            # Canvas Enter/Leave also fires between a button's own layers.
            if inside(event):
                return
            c.configure(cursor='')
            self._set_button(button, button['enabled'])
        def press(event=None):
            if button['enabled'] and inside(event):
                button['pressed'] = True
                c.itemconfigure(face, fill=self._shade_color(color, .72))
                c.coords(text_id, (x0+x1)/2, y+2)
        def release(event=None):
            if not button['pressed']:
                return
            activate = button['enabled'] and inside(event)
            self._set_button(button, button['enabled'])
            if activate:
                command()
        c.tag_bind(tag, '<Enter>', enter)
        c.tag_bind(tag, '<Leave>', leave)
        # Receive clicks for the full button bounds regardless of the top item.
        c.bind('<ButtonPress-1>', press, add='+')
        c.bind('<ButtonRelease-1>', release, add='+')
        return button

    def _set_button(self, button, enabled, text=None):
        if not button:
            return
        button['enabled'], button['pressed'] = bool(enabled), False
        c, color = self.canvas, button['color']
        x, _y = c.coords(button['text'])
        c.coords(button['text'], x, button['text_y'])
        if text is not None:
            c.itemconfigure(button['text'], text=text)
        c.itemconfigure(button['rect'], fill=color if enabled else '#4a4743')
        c.itemconfigure(button['rim'], fill=self._shade_color(color, .55) if enabled else '#262422')
        c.itemconfigure(button['highlight'], fill=self._shade_color(color, 1.45) if enabled else '#66615b')
        c.itemconfigure(button['text'], fill=button['fg'] if enabled else '#9b9690')

    def _button_state(self, button, visible):
        if button:
            button['visible'] = bool(visible)
            if not visible and button['pressed']:
                self._set_button(button, button['enabled'])
            self.canvas.itemconfigure(button['tag'], state='normal' if visible else 'hidden')

    def _raise_visible_bottom_controls(self, in_round):
        self.canvas.tag_raise('chip_selector')
        for button in self.control_buttons.values():
            self.canvas.tag_raise(button['tag'])
        for name in ('balance_text', 'total_bet_text'):
            item = getattr(self, name, None)
            if item:
                self.canvas.tag_raise(item)

    def _set_round_control_visibility(self, in_round):
        # A single bottom strip switches between the rack, actions and insurance.
        in_round = bool(in_round or (self.animation_running and not self.accept_bets))
        decision = bool(in_round and self.ace_decision_mode)
        self.canvas.itemconfigure('chip_selector', state='hidden' if in_round else 'normal')
        for button in (self.clear_button, self.repeat_button, self.deal_button, self.info_button):
            self._button_state(button, not in_round)
        for (seat, _action), button in self.action_buttons.items():
            self._button_state(button, in_round and not decision)
        for (seat, _action), button in self.decision_buttons.items():
            self._button_state(button, decision)
        self._raise_visible_bottom_controls(in_round)

    def _set_rules_strip_visible(self, visible):
        self.canvas.itemconfigure('round_rule_strip', state='normal')
        self._refresh_rule_strip_text()

    def _refresh_rule_strip_text(self):
        # The full line stays in place even when an insurance chip lands on it.
        self.canvas.itemconfigure(self.rule_strip_text, state='normal')
        for item in (self.rule_strip_left_text, self.rule_strip_right_text):
            self.canvas.itemconfigure(item, state='hidden')

    def _set_rule_strip_text_color(self, color):
        for item in (self.rule_strip_text, self.rule_strip_left_text, self.rule_strip_right_text):
            try: self.canvas.itemconfigure(item, fill=color)
            except tk.TclError: pass

    def _render_insurance_chip(self):
        self.canvas.delete('insurance_chip')
        self._refresh_rule_strip_text()
        for seat, info in self.seat_insurance.items():
            if not info['visible'] or info['bet']<=0:
                continue
            if self.settlement_running and info['returned']<=0:
                continue
            returned = info['returned'] if self.settlement_running else None
            self._draw_outcome_rows(self._outcome_chip_rows(('insurance',seat),
                info['bet'],returned,self.insurance_positions[seat],self.INSURANCE_CHIP_RADIUS,('insurance_chip',)))

    def _animate_insurance_chip_to_rule(self, seat, on_complete=None):
        amount = self.seat_insurance[seat]['bet']
        sx, sy = self._selected_chip_origin()
        self._animate_settlement_chips([(sx, sy, amount, self.INSURANCE_CHIP_RADIUS)],
            self.insurance_positions[seat], 220, f'insurance_chip_fly_{seat}', on_complete)

    def _show_ace_decision(self, mode):
        self.ace_decision_mode = mode
        self._set_round_control_visibility(True)

    def _resolve_ace_decision(self, accept):
        mode, seat = self.ace_decision_mode, self.ace_decision_seat
        if not mode or self.animation_running or self.settlement_running:
            return
        hand = next(hand for hand in self.hands if hand['seat']==seat and hand['contains_original'])
        if mode == 'even_money' and accept:
            credit = hand['base_bet']*2.0
            self.balance += credit
            hand.update(status='even_money', result='Even Money +1:1', settlement='win',
                        base_settlement='win', settlement_return=credit)
        elif mode == 'insurance' and accept:
            amount = self.round_original_bets[seat]/2.0
            if self.balance+1e-9 < amount:
                return
            self.balance -= amount
            self.seat_insurance[seat].update(bet=amount, visible=False)
            self.insurance_bet += amount
            self.animation_running = True
            self.save_balance()
            self.update_display()
            def landed():
                self.seat_insurance[seat]['visible'] = True
                self.insurance_chip_visible = True
                self.animation_running = False
                self.ace_decision_mode = self.ace_decision_seat = None
                self.render_cards()
                self._next_ace_decision()
            self._animate_insurance_chip_to_rule(seat, landed)
            return
        self.ace_decision_mode = self.ace_decision_seat = None
        self.save_balance()
        self.render_cards()
        self._next_ace_decision()

    def _animate_betting_station(self, to_round, on_complete=None):
        self.bet_layout_mode = 'round' if to_round else 'home'
        self._update_main_spot_visibility()
        if callable(on_complete):
            on_complete()

    def _animate_previous_round_cards_out(self, on_complete=None):
        """At the next 开牌, slide the previous round's cards upper-left for 0.20 s."""
        if not self.canvas.find_withtag('dealt_card'):
            self.previous_round_cards_present = False
            if callable(on_complete): on_complete()
            return
        # Remove old status/point overlays immediately; only the actual cards
        # perform the requested 0.20 s upper-left exit.
        self.canvas.delete('hand_label'); self.canvas.delete('hand_zone')
        bbox = self.canvas.bbox('dealt_card')
        if not bbox:
            if callable(on_complete): on_complete()
            return
        cx=(bbox[0]+bbox[2])/2; cy=(bbox[1]+bbox[3])/2
        dx_total=70.0-cx; dy_total=55.0-cy
        last=[0.0]; steps=10; frame_ms=20
        def frame(step=1):
            t=min(1.0,step/steps); e=t*t
            de=e-last[0]; last[0]=e
            self.canvas.move('dealt_card', dx_total*de, dy_total*de)
            if step < steps: self._queue(frame_ms, frame, step+1)
            else:
                self.canvas.delete('dealt_card')
                self.previous_round_cards_present=False
                if callable(on_complete): on_complete()
        self._queue(frame_ms, frame, 1)

    @staticmethod
    def contrast_text_color(color):
        # Choose the higher-contrast foreground using linear sRGB luminance.
        rgb = [int(color[i:i+2], 16)/255.0 for i in (1, 3, 5)]
        linear = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb]
        luminance = sum(v*w for v, w in zip(linear, (.2126, .7152, .0722)))
        black_contrast = (luminance+.05)/.05
        white_contrast = 1.05/(luminance+.05)
        return '#000000' if black_contrast >= white_contrast else '#FFFFFF'

    @staticmethod
    def format_money(value):
        return f'${float(value):,.2f}'

    def save_balance(self):
        if self.username:
            update_balance_in_json(self.username, self.balance)
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))

    @staticmethod
    def _compact_amount(amount):
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

    @classmethod
    def bet_chip_color(cls, amount):
        amount = float(amount)
        if amount >= 1_000_000:
            return cls.M_CHIP_COLOR
        color = cls.CHIP_SPECS[0][1]
        for threshold, chip_color, _label in cls.CHIP_SPECS:
            if amount >= threshold:
                color = chip_color
            else:
                break
        return color

    def _draw_baccarat_chip(self, cx, cy, amount, tags, radius=None, force_color=None):
        radius = self.WAGER_CHIP_RADIUS if radius is None else float(radius)
        color = force_color or self.bet_chip_color(amount)
        label = self._compact_amount(amount)
        chip_tags = (tags,) if isinstance(tags, str) else tuple(tags)
        if 'wager_chip' not in chip_tags:
            chip_tags += ('wager_chip',)
        outer = self.canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
            fill='#F7F3E8', outline='#111820', width=2, tags=chip_tags)
        # The light rim also separates dark denominations from the green felt.
        # Preserve the three-item animation contract: outer, face, amount text.
        inset = self.CHIP_RIM_INSET
        inner = self.canvas.create_oval(cx-radius+inset, cy-radius+inset,
            cx+radius-inset, cy+radius-inset,
            fill=color, outline='', tags=chip_tags)
        text = self.canvas.create_text(cx, cy, text=label,
            font=self._fit_chip_font(label, radius),
            fill=self.contrast_text_color(color), tags=chip_tags)
        return outer, inner, text


    def _decorate_main_bet_surface(self, spot):
        """Draw the circular blue MAIN spot and its Chinese open-ring title."""
        c = self.canvas
        left, top, right, bottom = spot['bounds']
        cx, cy = (left + right) / 2, (top + bottom) / 2
        radius = (right - left) / 2
        spot['surface_tag'] = f"{spot['tag']}_surface"
        spot['title_tag'] = f"{spot['tag']}_title"
        c.addtag_withtag(spot['surface_tag'], spot['rect'])
        surface_tags = (spot['tag'], spot['surface_tag'], 'betting_spot')

        # Layer smaller circles to make the same blue-to-light gradient as Premiere.
        outer, centre = (23, 92, 152), (221, 226, 196)
        for step in range(1, 25):
            t = step / 24.0
            color = '#' + ''.join(
                f'{round(a + (b - a) * t):02x}'
                for a, b in zip(outer, centre)
            )
            r = radius * (1.0 - 0.96 * t)
            c.create_oval(
                cx-r, cy-r, cx+r, cy+r,
                fill=color, outline='', tags=surface_tags,
            )

        # Draw a 260-degree ring, leaving the bottom open for the title.
        ring = []
        for step in range(65):
            degrees = self.MAIN_RING_START + self.MAIN_RING_EXTENT * step / 64
            theta = math.radians(degrees)
            ring.extend((cx + radius * math.cos(theta),
                         cy + radius * math.sin(theta)))
        for color, width in (('#A5BED4', 9), ('#19345D', 6)):
            c.create_line(
                *ring, fill=color, width=width,
                capstyle=tk.ROUND, tags=surface_tags,
            )

        key = spot['key']
        if isinstance(key, tuple):
            seat = key[0]
        else:
            seats = getattr(self, 'SEATS', ('Player1',))
            seat = seats[0] if seats else 'Player1'
        seat_names = getattr(self, 'SEAT_NAMES', {})
        title = "玩家主注"
        for index, char in enumerate(title):
            # Place each character on the circular edge inside the bottom opening.
            degrees = 122.0 - index * 64.0 / max(1, len(title) - 1)
            theta = math.radians(degrees)
            c.create_text(
                cx + radius * math.cos(theta),
                cy + radius * math.sin(theta),
                text=char,
                angle=90.0-degrees,
                font=(self.cn_font, -14, 'bold'),
                fill='#F2E6C9',
                tags=(spot['tag'], spot['title_tag'], 'betting_spot_label'),
            )
    def _bet_surface_layout(self, x, main=False):
        if main:
            r, y = self.MAIN_BET_RADIUS, self.MAIN_BET_Y
            return (x-r, y-r, x+r, y+r), (x, y+r+10), (x, y)
        return (x-60, 535, x+60, 616), (x, 608), (x, 566)

    def _draw_bet_surface(self, bounds, fill, outline, tag, main=False):
        if main:
            return self.canvas.create_oval(
                *bounds, fill=fill, outline='', width=0,
                tags=(tag, 'betting_spot'))
        left, top, right, bottom = bounds
        corner = 10
        return self.canvas.create_polygon(
            left+corner, top, right-corner, top, right, top,
            right, top+corner, right, bottom-corner, right, bottom,
            right-corner, bottom, left+corner, bottom, left, bottom,
            left, bottom-corner, left, top+corner, left, top,
            smooth=True, splinesteps=16, fill=fill, outline=outline,
            width=2, tags=(tag, 'betting_spot'))

    def _wager_center_x(self, center, geometry, right_slots=1):
        """Fit the whole principal/profit group inside its hand's lane."""
        left, right, _center, _order, count = geometry
        if count > 1:
            center += (2-right_slots)*self.CHIP_PITCH/2
        lower = left+2*self.CHIP_PITCH+self.WAGER_CHIP_RADIUS+4
        upper = right-right_slots*self.CHIP_PITCH-self.WAGER_CHIP_RADIUS-4
        return max(lower, min(center, upper))


    def _position_chip_items(self, items, cx, cy, radius):
        """Keep animation geometry identical to the chip's initial drawing."""
        inset = self.CHIP_RIM_INSET
        self.canvas.coords(items[0], cx-radius, cy-radius, cx+radius, cy+radius)
        self.canvas.coords(items[1], cx-radius+inset, cy-radius+inset,
                           cx+radius-inset, cy+radius-inset)
        self.canvas.coords(items[2], cx, cy)


    def _fit_chip_font(self, label, radius):
        """Measure the complete label (including '+') inside the circular face.

        Negative Tk font sizes are pixels: the fitted label cannot grow beyond
        its chip when Windows/macOS display scaling changes the point size.
        """
        maximum = max(8, min(18, round(float(radius)*.62)))
        text_radius = max(4.0, float(radius)-4.0)
        for size in range(maximum, 3, -1):
            key = (self.chip_font, size)
            font = self._chip_fonts.get(key)
            if font is None:
                font = tkfont.Font(root=self.canvas, family=self.chip_font,
                                   size=-size, weight='bold')
                self._chip_fonts[key] = font
            # Canvas text has a small horizontal bbox padding. Fit its corners,
            # rather than merely its width, so the text clears the circular rim.
            width = font.measure(label)+4
            height = font.metrics('linespace')+2
            if math.hypot(width/2, height/2) <= text_radius:
                return font
        return font

    def _selected_chip_origin(self):
        return self.chip_selector_centers.get(float(self.selected_chip), (575.0, 674.0))

    def _animate_selected_chip_to_spot(self, spot_key, on_complete=None, amount=None):
        """Fly the selected rack chip to a betting area in exactly 0.20 s.

        ``amount`` may be smaller than the selected denomination when a click is
        silently clamped to the remaining table limit.
        """
        spot = self.bet_spots.get(spot_key)
        if not spot:
            if callable(on_complete):
                on_complete()
            return
        sx, sy = self._selected_chip_origin()
        tx, ty = spot['chip_pos']
        selected_amount = float(self.selected_chip)
        amount = selected_amount if amount is None else float(amount)
        selected_color = next((color for value, color, _ in self.CHIP_SPECS
                               if float(value) == selected_amount), self.bet_chip_color(selected_amount))
        items = self._draw_baccarat_chip(
            sx, sy, amount, tags=('bet_chip_fly',), radius=self.WAGER_CHIP_RADIUS, force_color=selected_color)
        self.canvas.tag_raise('bet_chip_fly')
        steps = 10
        frame_ms = 20

        def frame(step=1):
            ratio = min(1.0, step / float(steps))
            # ease-out keeps the casino-chip movement crisp while still visibly animated
            eased = 1.0 - (1.0 - ratio) ** 2
            cx = sx + (tx - sx) * eased
            cy = sy + (ty - sy) * eased
            r = self.WAGER_CHIP_RADIUS
            self.canvas.coords(items[0], cx-r, cy-r, cx+r, cy+r)
            self.canvas.coords(items[1], cx-r+3, cy-r+3, cx+r-3, cy+r-3)
            self.canvas.coords(items[2], cx, cy)
            if step < steps:
                self._queue(frame_ms, frame, step + 1)
            else:
                for item in items:
                    try:
                        self.canvas.delete(item)
                    except tk.TclError:
                        pass
                if callable(on_complete):
                    on_complete()
        self._queue(frame_ms, frame, 1)

    def _animate_amount_chip_to_spot(self, spot_key, amount, on_complete=None):
        """V16 repeat-bet animation from the chip rack to one betting spot."""
        spot = self.bet_spots.get(spot_key)
        amount = float(amount)
        if not spot or amount <= 0.0:
            if callable(on_complete):
                on_complete()
            return

        # If the repeated amount exactly matches a rack denomination, originate
        # from that physical chip.  Otherwise use the closest lower denomination
        # (or the smallest chip) so the motion still visibly begins in the rack.
        values = sorted(float(value) for value, _color, _label in self.CHIP_SPECS)
        source_value = next((value for value in values if abs(value - amount) < 1e-9), None)
        if source_value is None:
            lower = [value for value in values if value <= amount + 1e-9]
            source_value = max(lower) if lower else min(values)
        sx, sy = self.chip_selector_centers.get(source_value, (575.0, 674.0))
        tx, ty = spot['chip_pos']
        items = self._draw_baccarat_chip(
            sx, sy, amount, tags=('bet_chip_fly',), radius=self.WAGER_CHIP_RADIUS,
            force_color=self.bet_chip_color(amount))
        self.canvas.tag_raise('bet_chip_fly')
        steps = 10
        frame_ms = 20

        def frame(step=1):
            ratio = min(1.0, step / float(steps))
            eased = 1.0 - (1.0 - ratio) ** 2
            cx = sx + (tx - sx) * eased
            cy = sy + (ty - sy) * eased
            r = self.WAGER_CHIP_RADIUS
            self.canvas.coords(items[0], cx-r, cy-r, cx+r, cy+r)
            self.canvas.coords(items[1], cx-r+3, cy-r+3, cx+r-3, cy+r-3)
            self.canvas.coords(items[2], cx, cy)
            if step < steps:
                self._queue(frame_ms, frame, step + 1)
            else:
                for item in items:
                    try:
                        self.canvas.delete(item)
                    except tk.TclError:
                        pass
                if callable(on_complete):
                    on_complete()

        self._queue(frame_ms, frame, 1)

    def _bet_amount_for_spot(self, spot_key):
        seat, kind = spot_key
        if kind == 'MAIN':
            if self.round_active:
                amount = self.round_original_bets[seat] if self._special_offer_running else 0.0
            else:
                amount = self.current_bets[seat]
        elif self.round_active:
            if spot_key in self.side_bet_early_collected:
                return 0.0
            amount = self.round_side_bets.get(spot_key, 0.0)
            if self.settlement_running:
                amount = min(amount, self.side_bet_return_amounts.get(spot_key,0.0))
        else:
            amount = self.current_side_bets[spot_key]
        if not self.round_active:
            amount -= self.pending_bet_animation.get(spot_key, 0.0)
        return max(0.0, amount)

    def update_bet_chips(self):
        self.canvas.delete('bet_chip_dynamic')
        if self.settlement_visual_stage=='returning':
            return
        for key, spot in self.bet_spots.items():
            amount = self._bet_amount_for_spot(key)
            if amount > 0:
                self._draw_baccarat_chip(*spot['chip_pos'], amount,
                    tags=('bet_chip_dynamic', spot['tag'], 'principal_chip'), radius=self.WAGER_CHIP_RADIUS)
            if self.round_active and key[1]!='MAIN':
                stake = self.round_side_bets.get(key,0.0)
                returned = self.side_bet_return_amounts.get(key,0.0)
                rows = self._outcome_chip_rows(('side',*key), stake, returned,
                    spot['chip_pos'], self.WAGER_CHIP_RADIUS, ('bet_chip_dynamic',spot['tag']))
                self._draw_outcome_rows([row for row in rows if row['role']=='profit'])
        self.canvas.tag_raise('bet_chip_dynamic')

    def _finish_bet_chip_animation(self, spot_key, amount):
        self.pending_bet_animation[spot_key] = max(
            0.0, float(self.pending_bet_animation.get(spot_key, 0.0)) - float(amount))
        self.bet_chip_animation_count = max(0, self.bet_chip_animation_count - 1)
        self.update_display()
        self.save_balance()

    def _restore_betting_spot_label_colors(self):
        """Restore normal white text after settlement flash phases."""
        for spot in getattr(self, 'bet_spots', {}).values():
            label = spot.get('label')
            if label:
                try: self.canvas.itemconfigure(label, fill='#F2E6C9')
                except tk.TclError: pass
        self._set_rule_strip_text_color(self.GOLD)

    def _draw_side_bet_progress_badges(self):
        self.canvas.delete('side_bet_progress_badge')

    def _collect_losing_side_bet_upward(self, key):
        """Collect one resolved losing side-bet chip upward during live play."""
        if key[1] in ('Bust!', '3 Card Bust') or key in self.side_bet_early_collected:
            return
        stake = float(self.round_side_bets.get(key, 0.0))
        spot = self.bet_spots.get(key)
        if stake <= 0.0 or not spot:
            return
        self.side_bet_early_collected.add(key)
        # Remove the stationary chip first, then animate a clone upward.
        self.update_bet_chips()
        x, y = spot['chip_pos']
        safe = ''.join(ch if ch.isalnum() else '_' for ch in f'{key[0]}_{key[1]}')
        self._animate_settlement_chips(
            [(x, y, stake, self.WAGER_CHIP_RADIUS)], lambda sx, sy: (sx, -35.0), 300,
            f'side_bet_collect_{safe}')

    def _draw_side_bet_win_odds_badges(self):
        self.canvas.delete('side_bet_win_odds')

    def _settlement_losing_chip_sources(self):
        """Return visible losing wager components as (x,y,amount,radius)."""
        sources=[]
        # Side bets that were actually staked but did not return anything.
        for key in self.round_side_bets:
            if key in self.side_bet_early_collected:
                continue
            stake=float(self.round_side_bets.get(key,0.0))
            returned=float(self.side_bet_return_amounts.get(key,0.0))
            spot=self.bet_spots.get(key)
            if stake>0.0 and returned<=0.0 and spot:
                x,y=spot['chip_pos']; sources.append((x,y,stake,self.WAGER_CHIP_RADIUS))

        # MAIN is component based so an OBO hand can lose its Original Bet while
        # its Double/supplemental component remains for refund.
        layout=self._main_split_wager_layout(len(self.hands)) if self.hands else []
        for idx,hand in enumerate(self.hands):
            if idx>=len(layout): break
            if float(hand.get('base_bet',0.0))>0 and hand.get('base_settlement')=='lose':
                x,y=layout[idx]['base']; sources.append((x,y,float(hand['base_bet']),self.WAGER_CHIP_RADIUS))
            if float(hand.get('double_added',0.0))>0 and hand.get('double_settlement')=='lose':
                x,y=layout[idx]['double']; sources.append((x,y,float(hand['double_added']),self.WAGER_CHIP_RADIUS))

        for seat, info in self.seat_insurance.items():
            if info['bet']>0 and info['returned']<=0:
                x,y=self.insurance_positions[seat]
                sources.append((x,y,info['bet'],self.INSURANCE_CHIP_RADIUS))
        return sources

    def _settlement_return_chip_sources(self):
        return [(*row['pos'],row['amount'],row['radius'])
                for row in self._settlement_chip_rows()]

    def _animate_settlement_chips(self, sources, destination, duration_ms, tag, on_complete=None):
        """Animate Baccarat-style amount chips from settlement positions."""
        self.canvas.delete(tag)
        if not sources:
            if callable(on_complete): on_complete()
            return
        duration_ms=max(20,int(duration_ms)); frame_ms=20
        steps=max(1,int(round(duration_ms/frame_ms)))
        drawn=[]
        for sx,sy,amount,radius in sources:
            items=self._draw_baccarat_chip(sx,sy,amount,tags=(tag,),radius=radius)
            drawn.append((float(sx),float(sy),float(radius),items))
        self.canvas.tag_raise(tag)

        def frame(step=1):
            t=min(1.0,step/float(steps))
            e=1.0-(1.0-t)**2
            for sx,sy,r,items in drawn:
                if callable(destination):
                    tx,ty=destination(sx,sy)
                else:
                    tx,ty=destination
                cx=sx+(tx-sx)*e; cy=sy+(ty-sy)*e
                self.canvas.coords(items[0],cx-r,cy-r,cx+r,cy+r)
                self.canvas.coords(items[1],cx-r+3,cy-r+3,cx+r-3,cy+r-3)
                self.canvas.coords(items[2],cx,cy)
            self.canvas.tag_raise(tag)
            if step<steps:
                self._queue(frame_ms,frame,step+1)
            else:
                self.canvas.delete(tag)
                if callable(on_complete): on_complete()
        self._queue(frame_ms,frame,1)

    def _animate_losing_chips_out(self):
        # Starts simultaneously with the first settlement flash and ends in 0.30 s.
        self._animate_settlement_chips(
            self._settlement_losing_chip_sources(),
            lambda sx,sy:(sx,-35.0), 300, 'settlement_loss_fly')

    def _finish_flash_with_chip_return(self):
        """Return the displayed principal and profit chips once each."""
        if not self.settlement_running or self.settlement_visual_stage=='returning':
            return
        sources = self._settlement_return_chip_sources()
        self.settlement_visual_stage = 'returning'
        for tag in ('bet_chip_dynamic','hand_wager','insurance_chip','win_flash_area'):
            self.canvas.delete(tag)
        def done():
            self.settlement_running = False
            self._reset_after_round()
        self._animate_settlement_chips(sources,(575.0,674.0),200,'settlement_return_fly',done)

    def run_settlement_flash(self):
        """Compatibility entry point: render a steady outcome without flashing."""
        if self.settlement_running:
            self._render_settlement_chips()

    def select_chip(self, value):
        if self.round_active or self.animation_running or self.settlement_running:
            return
        self.selected_chip = float(value)
        for chip_value, (outer, _inner, _text) in self.chip_selector_items.items():
            selected = float(chip_value) == self.selected_chip
            self.canvas.itemconfigure(outer, outline=self.GOLD if selected else '#6C7850',
                                      width=4 if selected else 3)

    def place_bet(self, seat='Player1'):
        self._place_seat_bet(seat, 'MAIN')

    def place_side_bet(self, key, seat='Player1'):
        self._place_seat_bet(seat, key)

    def clear_side_bet(self, key, seat='Player1'):
        self._clear_seat_bet(seat, key)

    def clear_bets(self):
        if not self._can_change_bets() or self.bet_chip_animation_count:
            return
        self.balance += sum(self.current_bets.values())+sum(self.current_side_bets.values())
        self.current_bets = {seat: 0.0 for seat in self.SEATS}
        self.current_side_bets = self._empty_side_bets()
        self.pending_bet_animation = {key: 0.0 for key in self.bet_spots}
        self._sync_main_totals()
        self.update_display()
        self.save_balance()

    def repeat_last_bet(self):
        if not self._can_change_bets() or self.bet_chip_animation_count:
            return
        targets = {(seat, 'MAIN'): self.last_bets[seat] for seat in self.SEATS}
        targets.update(self.last_side_bets)
        additions = {key: max(0.0, value-(self.current_bets[key[0]] if key[1]=='MAIN'
                                        else self.current_side_bets[key]))
                     for key, value in targets.items()}
        needed = sum(additions.values())
        if needed <= 0:
            return
        if self.balance+1e-9 < needed:
            messagebox.showwarning('无法重复下注', '余额不足。', parent=self.winfo_toplevel())
            return
        self.balance -= needed
        self.show_last_win = False
        for key, amount in additions.items():
            if amount <= 0:
                continue
            if key[1] == 'MAIN':
                self.current_bets[key[0]] += amount
            else:
                self.current_side_bets[key] += amount
            self.pending_bet_animation[key] += amount
            self.bet_chip_animation_count += 1
        self._sync_main_totals()
        self.update_display()
        for key, amount in additions.items():
            if amount > 0:
                self._animate_amount_chip_to_spot(key, amount,
                    lambda k=key, a=amount: self._finish_bet_chip_animation(k, a))

    # -------------------------------------------------------------- Multiply_Blackjack.json
    def save_runtime_store(self, burn_complete=True):
        data = {
            'version': 2,
            'shoe': {
                'mode': 'CSM',
                'decks': 8,
                'chambers': 15,
                'game_id': self.csm_game_id,
            },
        }

        try:
            os.makedirs(os.path.dirname(self.runtime_data_file), exist_ok=True)

            with open(self.runtime_data_file, 'w', encoding='utf-8') as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def load_runtime_store(self):
        # The encrypted CSM state is authoritative.  Blackjack deliberately
        # keeps no duplicate deck order in Multiply_Blackjack.json.
        try:
            self.csm.status()
            return True
        except (OSError, TypeError, ValueError, CSMError):
            return False

    def draw_round_card(self):
        try:
            card = self.engine.draw_card()
        except (CSMError, OSError) as exc:
            self.accept_bets = False
            self.animation_running = True
            self.update_display()
            messagebox.showerror('自动洗牌机',
                                 f'本局发牌已暂停：{exc}\n请退出本局以归还牌张；系统不会放宽取仓规则。',
                                 parent=self.winfo_toplevel())
            raise
        self.round_deal_sequence.append(card)
        return card

    def _face_photo(self, card, golden=False):
        images = self.external_golden_card_images if golden else self.external_card_images
        return images.get(tuple(card))

    def _create_scaled_flip_image(self, card, width, height, use_back=False, golden=False):
        if Image is None or ImageTk is None:
            return self.external_back_image if use_back else self._face_photo(card, golden=golden)
        base = self._oriented_card_pil(card, use_back=use_back, golden=golden)
        if base is None:
            return self.external_back_image if use_back else self._face_photo(card, golden=golden)
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        image = base.resize((max(1, int(width)), max(1, int(height))), resample)
        return ImageTk.PhotoImage(image, master=self)

    def _animate_card_from_shoe(self, card, target_x, target_y, on_complete=None,
                                flip=True, tag='round_animation_card', rotation=0, golden=False):
        """Deal the oriented back, then flip on the same oriented axis.

        Double's 90-degree card remains horizontal throughout its movement and
        reveal: its height collapses, rather than reverting to an upright flip.
        """
        sx,sy = self.shoe_origin
        width,height = self._card_dimensions(rotation)
        back = self._oriented_card_photo(card,rotation,use_back=True)
        if back is not None:
            card_id = self.canvas.create_image(sx,sy,image=back,anchor='nw',
                tags=(tag,'animation_card'))
        else:
            card_id = self.canvas.create_rectangle(sx,sy,sx+width,sy+height,
                fill='#253e66',outline='#d7c46a',width=2,tags=(tag,'animation_card'))
        self._round_anim_item = card_id

        def finish():
            self._temp_flip_images.pop(card_id,None)
            self.canvas.delete(card_id)
            self._render_card(card,target_x,target_y,tags=(tag,'animation_card'),rotation=rotation,golden=golden)
            self._raise_wager_chips()
            if callable(on_complete):
                on_complete()

        def flip_step(step=0):
            if self._closing:
                return
            if step>12:
                finish()
                return
            use_back = step<=6
            ratio = 1-step/6 if use_back else (step-6)/6
            fw = width if rotation%180 else max(1,round(width*ratio))
            fh = max(1,round(height*ratio)) if rotation%180 else height
            x,y = target_x+(width-fw)/2,target_y+(height-fh)/2
            if self.canvas.type(card_id)=='image':
                base = self._oriented_card_pil(card,rotation,use_back,golden)
                resample = getattr(Image,'Resampling',Image).LANCZOS
                photo = ImageTk.PhotoImage(base.resize((fw,fh),resample),master=self)
                self._temp_flip_images[card_id] = photo
                self.canvas.itemconfigure(card_id,image=photo)
                self.canvas.coords(card_id,x,y)
            else:
                self.canvas.coords(card_id,x,y,x+fw,y+fh)
                self.canvas.itemconfigure(card_id,fill='#253e66' if use_back else
                    ('#ffedaa' if golden else '#f4efe4'))
            self._raise_wager_chips()
            self._queue(20,flip_step,step+1)

        def move_step(step=0):
            if self._closing:
                return
            t = min(1.0,step/24.0)
            eased = 1-(1-t)**3
            x,y = sx+(target_x-sx)*eased,sy+(target_y-sy)*eased
            if self.canvas.type(card_id)=='image':
                self.canvas.coords(card_id,x,y)
            else:
                self.canvas.coords(card_id,x,y,x+width,y+height)
            self._raise_wager_chips()
            if step<24:
                self._queue(12,move_step,step+1)
            elif flip:
                flip_step()
            elif callable(on_complete):
                on_complete()
        move_step()

    def _animate_back_from_shoe(self, target_x, target_y, on_complete=None):
        sx, sy = self.shoe_origin
        if self.external_back_image is not None:
            item = self.canvas.create_image(sx, sy, image=self.external_back_image,
                                            anchor='nw', tags=('burn_card','animation_card'))
        else:
            item = self.canvas.create_rectangle(sx,sy,sx+self.CARD_WIDTH,sy+self.CARD_HEIGHT,fill='#253e66',outline='#d7c46a',
                                                tags=('burn_card','animation_card'))
        def step(i=0):
            t=min(1.0,i/20.0); e=1-(1-t)**3
            x=sx+(target_x-sx)*e; y=sy+(target_y-sy)*e
            if self.canvas.type(item)=='image': self.canvas.coords(item,x,y)
            else: self.canvas.coords(item,x,y,x+self.CARD_WIDTH,y+self.CARD_HEIGHT)
            if i<20: self._queue(12,step,i+1)
            elif callable(on_complete): on_complete()
        step(0)

    def _draw_single_temp_card(self, card, x, y, tag, face_up=True):
        if face_up and card in self.external_card_images:
            item = self.canvas.create_image(x, y, image=self.external_card_images[card],
                                            anchor='nw', tags=(tag, 'temp_card'))
            self.card_items.append(item)
            return item
        if not face_up and self.external_back_image is not None:
            item = self.canvas.create_image(x, y, image=self.external_back_image,
                                            anchor='nw', tags=(tag, 'temp_card'))
            self.card_items.append(item)
            return item
        fill = '#f4efe4' if face_up else '#253e66'
        rect = self.canvas.create_rectangle(x, y, x + 100, y + 140, fill=fill,
                                            outline='#d7cbb9', width=2,
                                            tags=(tag, 'temp_card'))
        if face_up and card is not None:
            suit, rank = card
            symbol = {'Club': '♣', 'Diamond': '♦', 'Heart': '♥', 'Spade': '♠'}.get(suit, suit[:1])
            fg = '#c22631' if suit in ('Diamond', 'Heart') else '#111111'
            tid = self.canvas.create_text(x + 50, y + 70, text=f'{rank}\n{symbol}',
                                          font=('Arial', 22, 'bold'), fill=fg,
                                          justify='center', tags=(tag, 'temp_card'))
            self.card_items.extend((rect, tid))
        else:
            self.card_items.append(rect)
        return rect

    def clear_card_display(self):
        for tag in ('dealt_card','temp_card','hand_label','hand_zone','hand_wager',
                    'animation_card','split_lane_animation'):
            self.canvas.delete(tag)
        self.card_items.clear(); self._temp_flip_images.clear()
        self.previous_round_cards_present = False
        if hasattr(self, 'dealer_total_text'):
            self.canvas.itemconfigure(self.dealer_total_text, text='')

    def _hand_centers(self, count=None):
        geometry = self._seat_hand_geometry()
        return [geometry[i][2] for i in range(len(self.hands))]

    def _main_split_wager_layout(self, count=None, hands_snapshot=None):
        hands = self.hands if hands_snapshot is None else hands_snapshot
        geometry = self._seat_hand_geometry(hands)
        result = []
        for index, hand in enumerate(hands):
            x,y = self._player_card_position(hand, geometry[index], 0)
            cx = self._wager_center_x(x+self.CARD_WIDTH/2, geometry[index], right_slots=1)
            # Leave clear space between the first card and its enlarged chip.
            cy = y+self.CARD_HEIGHT+self.WAGER_CHIP_RADIUS+self.CARD_WAGER_GAP
            double = (cx+self.CHIP_PITCH,cy)  # Double uses the shared chip spacing.
            result.append({'base': (cx,cy), 'double': double})
        return result

    def _component_return_amount(self, hand, component):
        """Keep displayed base/double profits consistent with the credited payout."""
        amount = float(hand.get('base_bet' if component == 'base' else 'double_added', 0.0))
        stake = self.hand_stake(hand)
        if amount <= 0 or stake <= 0:
            return 0.0
        return float(hand.get('settlement_return', 0.0)) * amount / stake

    def _draw_main_hand_wagers(self):
        self.main_wager_positions = {}
        rows = self._main_wager_rows()
        for index,pos in enumerate(self._main_split_wager_layout()):
            self.main_wager_positions[index] = dict(base=pos['base'],double=pos['double'],
                show_base=any(row['key'][:3]==('main',index,'base') for row in rows),
                show_double=any(row['key'][:3]==('main',index,'double') for row in rows))
        self._draw_outcome_rows(rows)

    def _player_card_target(self, hand_index, card_index):
        return self._player_card_position(self.hands[hand_index],
                                          self._seat_hand_geometry()[hand_index], card_index)

    @staticmethod
    def _hand_total_badge_text(cards, blackjack=False, soft_stand=False):
        """Text for the pointed total badge.

        * A true two-card natural is shown as ``黑杰克``.
        * A soft hand still in play shows both totals (for example 7/17).
        * Once a soft hand stands, show only the best total with Ace counted as 11.
        """
        if not cards:
            return ''
        if blackjack:
            return '黑杰克'
        hard = 0
        aces = 0
        for _suit, rank in cards:
            if rank == 'A':
                hard += 1
                aces += 1
            elif rank in ('10', 'J', 'Q', 'K'):
                hard += 10
            else:
                hard += int(rank)
        best = hard
        if aces and hard + 10 <= 21:
            best = hard + 10
        if soft_stand and best != hard:
            return str(best)
        return f'{hard}/{best}' if best != hard else str(hard)

    def _player_hand_badge_fill(self, hand_index):
        if not 0<=hand_index<len(self.hands):
            return '#ffffff'
        hand = self.hands[hand_index]
        settlement = hand.get('settlement')
        if settlement == 'cashout' or hand.get('status') == 'surrendered':
            return '#b9dcff'
        if settlement == 'win' or hand.get('status')=='even_money':
            return '#b9efb4'
        if settlement in ('push', 'refund'):
            return '#b9dcff'
        if settlement=='lose' or hand.get('status')=='bust':
            return '#e34848'
        if hand.get('status')=='stood':
            return '#f2b0b0'
        return '#ffffff'

    def _draw_hand_total_badge(self, hand_index, left, right, active=False):
        hand = self.hands[hand_index]
        if not hand['cards']:
            return
        card_x, card_y = self._player_card_target(hand_index, 0)
        tip_x, y = card_x-6, card_y+self.CARD_HEIGHT/2
        box_right, box_left = tip_x-10, tip_x-62
        points = (tip_x, y, box_right, y-18, box_left, y-18,
                  box_left, y+18, box_right, y+18)
        text_x = (box_left+box_right)/2
        total, soft = BlackjackEngine.hand_value(hand['cards'])
        surrendered = hand.get('status') == 'surrendered' or hand.get('settlement') == 'cashout'
        natural = not surrendered and not hand['from_split'] and BlackjackEngine.is_blackjack(hand['cards'])
        self.canvas.create_polygon(*points,
            fill='#000000' if natural else self._player_hand_badge_fill(hand_index), outline='',
            tags=('hand_label', 'hand_total_badge', 'player_hand_overlay', f'player_score_{hand_index}'))
        self.canvas.create_text(text_x, y,
            text="投降" if surrendered else self._hand_total_badge_text(hand['cards'], blackjack=natural,
                                           soft_stand=soft and total<=21 and hand['status']=='stood'),
            font=('Segoe UI Emoji', 18) if surrendered else (self.cn_font, 10 if natural else 12, 'bold'),
            fill='#FFFFFF' if natural else '#111111',
            tags=('hand_label', 'hand_total_badge', 'player_hand_overlay', f'player_score_{hand_index}'))

    def _dealer_card_target(self, card_index):
        count = max(1, len(self.dealer_cards))
        # Original Classic's 42px overlapping row, centred in the dealer zone.
        # Compress only unusually long rows to retain room for the point badge.
        step = min(42.0, (292-self.CARD_WIDTH)/max(1, count-1))
        width = self.CARD_WIDTH+(count-1)*step
        return 575-width/2+card_index*step, 74.0

    def _draw_dealer_total_badge(self):
        if not self.dealer_cards:
            return
        card_x,card_y = self._dealer_card_target(len(self.dealer_cards)-1)
        tip_x,y = card_x+self.CARD_WIDTH+6,card_y+self.CARD_HEIGHT/2
        box_left,box_right = tip_x+10,tip_x+62
        total, soft = BlackjackEngine.hand_value(self.dealer_cards)
        natural = BlackjackEngine.is_blackjack(self.dealer_cards)
        fill = '#000000' if natural else self._dealer_badge_fill()
        self.canvas.create_polygon(tip_x,y,box_left,y-18,box_right,y-18,
                                   box_right,y+18,box_left,y+18,
                                   fill=fill, outline='', tags=('hand_label', 'dealer_total_badge'))
        self.canvas.create_text((box_left+box_right)/2, y,
            text=self._hand_total_badge_text(self.dealer_cards,
                blackjack=natural,
                soft_stand=soft and len(self.dealer_cards)>=2 and 17<=total<=21),
            font=(self.cn_font, 12, 'bold'), fill='#FFFFFF' if natural else '#111111',
            tags=('hand_label', 'dealer_total_badge'))

    def _draw_amount_chip(self, cx, cy, amount, label='', behind=False):
        self._draw_baccarat_chip(cx, cy, amount, tags=('hand_wager',),
                                 force_color='#5b2f79' if behind else None)
        if label:
            self.canvas.create_text(cx,cy+self.WAGER_CHIP_RADIUS+9,text=label,
                font=(self.cn_font,-12,'bold'),fill='#ffe898',tags=('hand_wager',))

    def render_cards(self):
        for tag in ('dealt_card', 'hand_label', 'hand_zone', 'hand_wager',
                    'split_lane_animation'):
            self.canvas.delete(tag)
        for index, card in enumerate(self.dealer_cards):
            self._render_card(card, *self._dealer_card_target(index),
                              tags=('dealt_card', 'dealer_dealt_card'))
        self._draw_dealer_total_badge()
        geometry = self._seat_hand_geometry()
        self.hand_zone_bounds = []
        for index, hand in enumerate(self.hands):
            left, right, cx, order, n = geometry[index]
            self.hand_zone_bounds.append((left, 256, right, 534))
            for j, card in enumerate(hand['cards']):
                self._render_card(card, *self._player_card_target(index, j),
                    tags=('dealt_card', 'player_dealt_card', f'player_card_{index}_{j}'),
                    rotation=90 if hand.get('double_card_index')==j else 0,
                    golden=card in self.special_cards)
            self._draw_hand_total_badge(index, left, right)
        self._draw_main_hand_wagers()
        self._render_insurance_chip()
        self._raise_visible_bottom_controls(self.round_active)
        self._raise_wager_chips()
        self.canvas.tag_raise('dealer_push_notice')

    def _render_card(self, card, x, y, tags=('dealt_card',), rotation=0, golden=False):
        if golden:
            tags = (*((tags,) if isinstance(tags, str) else tags), 'golden_card')
        photo = self._oriented_card_photo(card, rotation, golden=golden)
        if photo is not None:
            return self.canvas.create_image(x,y,image=photo,anchor='nw',tags=tags)
        width,height = self._card_dimensions(rotation)
        suit,rank = card
        fg = '#c22631' if suit in ('Diamond','Heart') else '#111111'
        symbol = {'Club':'♣','Diamond':'♦','Heart':'♥','Spade':'♠'}.get(suit,suit[:1])
        self.canvas.create_rectangle(x,y,x+width,y+height,
            fill='#ffedaa' if golden else '#f4efe4',
            outline='#d5a52d' if golden else '#d7cbb9',width=2,tags=tags)
        self.canvas.create_text(x+width/2,y+height/2,text=f'{rank}\n{symbol}',
            font=('Arial',18,'bold'),fill=fg,justify='center',angle=(-rotation)%360,tags=tags)

    # --------------------------------------------------------------- round setup
    def handle_enter(self, _event=None):
        if not self.round_active:
            self.deal_cards()
        else:
            # Enter never chooses insurance/even-money or a hand action. It only
            # repairs the correct currently-active control layer if necessary.
            self._set_round_control_visibility(True); self._raise_visible_bottom_controls(True)
            self.update_display()
        return 'break'

    def new_hand(self, cards=None, base_bet=0.0, contains_original=False,
                 from_split=False, split_aces=False, needs_split_draw=False, seat='Player1'):
        return {
            'seat': seat,
            'cards': list(cards or []),
            'base_bet': float(base_bet),
            'double_added': 0.0,
            'double_card_index': None,
            'contains_original': bool(contains_original),
            'from_split': bool(from_split),
            'split_aces': bool(split_aces),
            'needs_split_draw': bool(needs_split_draw),
            'status': 'active',
            'result': '',
            'cashout_credit': 0.0,
            'cashout_visual_stage': None,
            # Keep each wager component for chip animations. Multiply loses
            # both the base and added Double stake to a dealer Blackjack.
            'settlement': None,
            'base_settlement': None,
            'double_settlement': None,
            'settlement_return': 0.0,
        }

    @staticmethod
    def hand_stake(hand):
        return float(hand.get('base_bet', 0.0)) + float(hand.get('double_added', 0.0))

    def deal_cards(self):
        if not self._can_change_bets() or self.bet_chip_animation_count:
            return
        if not any(self.current_bets.values()):
            messagebox.showwarning('最低下注', '请先放置主注。', parent=self.winfo_toplevel())
            return
        for seat in self.SEATS:
            main = self.current_bets[seat]
            if main and not self.MIN_BET<=main<=self.MAX_MAIN_BET:
                messagebox.showwarning('最低下注',
                    f'{self.SEAT_NAMES[seat]}主注最低为 {self.format_money(self.MIN_BET)}。',
                    parent=self.winfo_toplevel())
                return
        if self.engine.remaining_cards() < 30:
            messagebox.showerror('自动洗牌机', '目前可用牌不足 30 张，请稍后再试。', parent=self.winfo_toplevel())
            return
        try:
            self.engine.start_round()
        except (CSMError, OSError, RuntimeError) as exc:
            messagebox.showerror('自动洗牌机', f'无法开始牌局：{exc}', parent=self.winfo_toplevel())
            return
        # A side-only family is inactive; refund its side wagers before committing.
        for seat in self.SEATS:
            if not self.current_bets[seat]:
                for kind in self.SIDE_BET_KEYS:
                    key = (seat, kind)
                    self.balance += self.current_side_bets[key]
                    self.current_side_bets[key] = 0.0
        self.save_balance()
        # Keep the blue MAIN circle and its chip in place until the offer ends.
        self._special_offer_running = True
        self.accept_bets, self.animation_running = False, True
        self.update_display()
        if self.canvas.find_withtag('dealt_card'):
            self._animate_previous_round_cards_out(self._begin_round_after_bet_layout)
        else:
            self._begin_round_after_bet_layout()

    def _begin_round_after_bet_layout(self):
        self.dealer_three_card_main_push = False
        self._fade_dealer_push_notice(False)
        self.round_active = True
        self.generate_special_offer()
        self.last_bets = dict(self.current_bets)
        self.last_side_bets = dict(self.current_side_bets)
        self.round_original_bets = dict(self.current_bets)
        self.round_side_bets = dict(self.current_side_bets)
        self.current_bets = {seat: 0.0 for seat in self.SEATS}
        self.current_side_bets = self._empty_side_bets()
        self._sync_main_totals()
        self.insurance_bet = self.insurance_return_amount = 0.0
        self.insurance_result = ''
        self.insurance_chip_visible = self.flash_insurance_rule = False
        self.insurance_resolved = False
        self.seat_insurance = {seat: dict(bet=0.0, returned=0.0, visible=False) for seat in self.SEATS}
        self.ace_decision_mode = self.ace_decision_seat = None
        self.ace_decision_queue = []
        self.split_actions = 0
        self.split_actions_by_seat = {seat: 0 for seat in self.SEATS}
        self.dealer_cards, self.round_deal_sequence = [], []
        self.seat_deal_sequences = {seat: [] for seat in self.SEATS}
        self.round_initial_cards = {}
        self.side_bet_results, self.side_bet_return_amounts = {}, {}
        self.side_bet_hit_odds, self.side_bet_hit_labels = {}, {}
        self.side_bet_early_collected, self.flash_winning_side_bets = set(), set()
        self.flash_main_bet = self.flash_main_push_only = False
        self.flash_winning_hand_indices = set()
        self.settlement_running, self.dealer_phase_active = False, False
        self.settlement_flash_step, self.flash_mode = 0, None
        self.last_result_lines = []
        self.pending_profit_chips = set()
        self.settlement_visual_stage = None
        self._opening_wager_animation = True
        self.hands = [self.new_hand(base_bet=self.round_original_bets[seat],
            contains_original=True, seat=seat) for seat in self.SEATS if self.round_original_bets[seat]>0]
        self.active_hand_index = 0
        self.render_cards()
        self.update_display()
        # Each active family receives its first card, then the shared dealer upcard,
        # then each family's second card. ENHC remains one exposed dealer card.
        sequence = list(range(len(self.hands)))+['D']+list(range(len(self.hands)))
        def step(index=0):
            if index == len(sequence):
                self.animation_running = False
                self._after_initial_deal()
                return
            callback = lambda: self._queue(80, step, index+1)
            if sequence[index] == 'D':
                self._deal_dealer_card_animated(callback)
            else:
                self._deal_player_card_animated(sequence[index], callback)
        # Finish the offer, hide MAIN, lift its chip, then deal the first card.
        self._play_special_offer_animation(lambda: self._animate_starting_wagers(step))

    def _after_initial_deal(self):
        self.round_initial_cards = {hand['seat']: list(hand['cards']) for hand in self.hands}
        self._settle_initial_side_bets()
        for hand in self.hands:
            natural = BlackjackEngine.is_blackjack(hand['cards'])
            if natural:
                hand['status'] = 'blackjack'
            if self.dealer_cards[0][1] == 'A':
                self.ace_decision_queue.append((hand['seat'], 'insurance'))
        self.render_cards()
        self._next_ace_decision()

    def _deal_player_card_animated(self, hand_index, on_complete=None):
        hand = self.hands[hand_index]
        card = self.draw_round_card()
        card_index = len(hand['cards'])
        hand['cards'].append(card)
        self.seat_deal_sequences[hand['seat']].append(card)
        tx, ty = self._player_card_target(hand_index, card_index)
        def done():
            self.canvas.delete('round_animation_card')
            self._maybe_settle_crazy7()
            self.render_cards()
            self.update_display()
            if callable(on_complete):
                on_complete()
        self._animate_card_from_shoe(card, tx, ty, on_complete=done, tag='round_animation_card',
            rotation=90 if hand.get('double_card_index')==card_index else 0,
            golden=card in self.special_cards)

    def _deal_dealer_card_animated(self, on_complete=None):
        card = self.draw_round_card()
        index = len(self.dealer_cards)
        self.dealer_cards.append(card)
        for seat in self.SEATS:
            if self.round_original_bets[seat]>0:
                self.seat_deal_sequences[seat].append(card)
        tx, ty = self._dealer_card_target(index)
        def done():
            self.canvas.delete('round_animation_card')
            self._maybe_settle_crazy7()
            self.render_cards()
            self.update_display()
            if callable(on_complete):
                on_complete()
        self._animate_card_from_shoe(card, tx, ty, on_complete=done, tag='round_animation_card')

    def _prepare_active_split_hand(self, on_ready=None):
        hand=self.active_hand()
        if not hand or not hand.get('needs_split_draw',False):
            if callable(on_ready): on_ready()
            return
        hand['needs_split_draw']=False
        self.animation_running=True
        def after_draw():
            total,_=BlackjackEngine.hand_value(hand['cards'])
            if hand.get('split_aces',False):
                # Exactly one card after a split Ace. Another Ace is the sole
                # exception and remains active so the player can re-split it.
                if len(hand['cards'])==2 and hand['cards'][1][1]=='A' and self.can_split(hand):
                    hand['status']='active'; hand['result']='分A后再A：可继续分牌'
                else:
                    hand['status']='stood'; hand['result']='分A一张停牌'
            elif total>21:
                hand['status']='bust'; hand['result']='爆牌'
            elif total==21:
                hand['status']='stood'; hand['result']='21点'
            self.animation_running=False; self.render_cards(); self.update_display()
            if hand['status']!='active': self._queue(180,self._advance_hand)
            elif callable(on_ready): on_ready()
        self._deal_player_card_animated(self.active_hand_index,on_complete=after_draw)

    def _project_player_card_positions(self, hands_snapshot, count=None):
        geometry = self._seat_hand_geometry(hands_snapshot)
        return {(index, j): self._player_card_position(hand, geometry[index], j)
                for index, hand in enumerate(hands_snapshot) for j in range(len(hand['cards']))}

    def _finish_split_without_animation(self, hand_index, left, right):
        self.canvas.delete('split_lane_animation')
        self.canvas.delete('split_wager_animation')
        if self.hands[hand_index] is not left:
            self.hands[hand_index] = left
            self.hands.insert(hand_index+1, right)
        self.animation_running = False
        self.render_cards()
        self.update_display()
        self._prepare_active_split_hand()

    def _animate_split_sequence(self, hand_index, left, right):
        self.canvas.delete('split_lane_animation')
        old = self.hands
        preview = old[:hand_index]+[left, right]+old[hand_index+1:]
        starts = self._project_player_card_positions(old)
        ends = self._project_player_card_positions(preview)
        start_tags, end_tags = {}, {}
        for (index, j), position in starts.items():
            target = (index, j) if index<hand_index else ((index+1, j) if index>hand_index
                else (hand_index, 0) if j==0 else (hand_index+1, 0))
            tag = f'player_card_{index}_{j}'
            if self.canvas.find_withtag(tag):
                start_tags[tag], end_tags[tag] = position, ends[target]
        old_wagers = self._main_split_wager_layout(hands_snapshot=old)
        new_wagers = self._main_split_wager_layout(hands_snapshot=preview)
        self.canvas.delete('hand_wager')
        for index,hand in enumerate(old):
            target = index if index<=hand_index else index+1
            for component, amount in (('base',hand['base_bet']),('double',hand['double_added'])):
                if amount<=0:
                    continue
                tag = f'split_wager_move_{index}_{component}'
                self._draw_baccarat_chip(*old_wagers[index][component], amount,
                    tags=('hand_wager','split_wager_animation',tag),radius=self.WAGER_CHIP_RADIUS)
                start_tags[tag] = old_wagers[index][component]
                end_tags[tag] = new_wagers[target][component]
        new_tag = 'split_wager_new'
        start = self._selected_chip_origin()
        self._draw_baccarat_chip(*start, right['base_bet'],
            tags=('hand_wager','split_wager_animation',new_tag),radius=self.WAGER_CHIP_RADIUS)
        start_tags[new_tag],end_tags[new_tag] = start,new_wagers[hand_index+1]['base']
        # Commit both reserved wagers before animation so closing midway refunds
        # the newly added stake as well as the original hand's stake.
        self.hands = preview
        self.canvas.delete('hand_label')
        self.canvas.delete('hand_zone')
        self._animate_canvas_positions(start_tags, end_tags, duration_ms=280,
            arc_lifts={f'player_card_{hand_index}_0': 12, f'player_card_{hand_index}_1': 22},
            on_complete=lambda: self._finish_split_without_animation(hand_index, left, right))

    def split(self):
        hand = self.active_hand()
        if not self.can_split(hand) or self.animation_running or self.ace_decision_mode:
            return
        self.animation_running = True
        self.balance -= hand['base_bet']
        self.split_actions += 1
        self.split_actions_by_seat[hand['seat']] += 1
        self.save_balance()
        first, second = hand['cards']
        is_aces = first[1]==second[1]=='A'
        left = self.new_hand([first], hand['base_bet'], hand['contains_original'],
            from_split=True, split_aces=is_aces, needs_split_draw=True, seat=hand['seat'])
        right = self.new_hand([second], hand['base_bet'], False,
            from_split=True, split_aces=is_aces, needs_split_draw=True, seat=hand['seat'])
        self.update_display()
        self._animate_split_sequence(self.active_hand_index, left, right)

    def active_hand(self):
        if not self.round_active or not (0 <= self.active_hand_index < len(self.hands)):
            return None
        return self.hands[self.active_hand_index]

    def can_hit(self, hand):
        return bool(hand and hand['status'] == 'active' and not hand.get('split_aces', False))

    def can_double(self, hand):
        return bool(
            hand and hand['status'] == 'active' and len(hand['cards']) == 2
            and not hand.get('split_aces', False)
            and self.balance + 1e-9 >= hand['base_bet']
        )

    def can_split(self, hand):
        if not hand or hand['status']!='active' or len(hand['cards'])!=2:
            return False
        seat = hand['seat']
        count = sum(h['seat']==seat for h in self.hands)
        if count>=self.MAX_HANDS or self.split_actions_by_seat[seat]>=self.MAX_SPLIT_ACTIONS:
            return False
        return bool(self.balance+1e-9>=hand['base_bet'] and
            BlackjackEngine.split_value(hand['cards'][0])==BlackjackEngine.split_value(hand['cards'][1]))

    def can_surrender(self, hand):
        return bool(hand and hand['status'] == 'active'
            and len(hand['cards']) == 2 and not hand.get('double_added', 0.0)
            and not BlackjackEngine.is_blackjack(hand['cards']))

    def hit(self):
        hand=self.active_hand()
        if not self.can_hit(hand) or self.animation_running: return
        self.animation_running=True
        # V10: visually and functionally lock ALL five action buttons before
        # the first animation frame. They are re-enabled only by update_display
        # after the dealt-card animation has completed and the next action exists.
        self.update_display(); self._raise_visible_bottom_controls(True)
        def after():
            total,_=BlackjackEngine.hand_value(hand['cards'])
            if total>21: hand['status']='bust'; hand['result']='爆牌'
            elif total==21: hand['status']='stood'; hand['result']='21点'
            self.animation_running=False; self.render_cards(); self.update_display()
            if hand['status']!='active': self._queue(220,self._advance_hand)
        self._deal_player_card_animated(self.active_hand_index,on_complete=after)

    def stand(self):
        hand = self.active_hand()
        if not hand or hand['status'] != 'active' or self.animation_running:
            return
        hand['status'] = 'stood'
        hand['result'] = '停牌'
        self.render_cards()
        self.update_display()
        self._advance_hand()

    def double(self):
        hand=self.active_hand()
        if not self.can_double(hand) or self.animation_running: return
        # Lock every player decision immediately on the click; no button may stay
        # actionable during the Double wager/card animation.
        self.animation_running=True
        for button in self.action_buttons.values():
            self._set_button(button, False)
        self._raise_visible_bottom_controls(True)
        hand['double_card_index']=len(hand['cards'])
        add=hand['base_bet']; self.balance-=add; hand['double_added']+=add; self.save_balance()
        self.render_cards(); self.update_display()
        def after():
            total,_=BlackjackEngine.hand_value(hand['cards'])
            hand['status']='bust' if total>21 else 'stood'
            hand['result']='加倍爆牌' if total>21 else '加倍停牌'
            self.animation_running=False; self.render_cards(); self.update_display()
            self._queue(250,self._advance_hand)
        self._deal_player_card_animated(self.active_hand_index,on_complete=after)

    def _move_canvas_tag(self, tag, dx, dy):
        """Move every canvas item carrying *tag*; works for image and fallback cards."""
        try:
            self.canvas.move(tag, dx, dy)
        except tk.TclError:
            pass

    def _animate_canvas_positions(self, start_positions, end_positions,
                                  duration_ms=200, easing='smooth',
                                  arc_lifts=None, on_complete=None):
        """Animate a mapping of canvas tags from start to end positions."""
        if not start_positions:
            if callable(on_complete):
                on_complete()
            return
        arc_lifts = dict(arc_lifts or {})
        current = {key: tuple(value) for key, value in start_positions.items()}
        steps = max(1, int(round(float(duration_ms) / 20.0)))
        frame_ms = max(1, int(round(float(duration_ms) / steps)))

        def ease_value(t):
            if easing == 'out':
                return 1.0 - (1.0 - t) ** 3
            if easing == 'in':
                return t ** 3
            return t * t * (3.0 - 2.0 * t)

        def frame(step=1):
            ratio = min(1.0, step / float(steps))
            eased = ease_value(ratio)
            for key, start in start_positions.items():
                end = end_positions[key]
                lift = float(arc_lifts.get(key, 0.0))
                x = start[0] + (end[0] - start[0]) * eased
                y = start[1] + (end[1] - start[1]) * eased - 4.0 * lift * eased * (1.0 - eased)
                prev_x, prev_y = current[key]
                self._move_canvas_tag(key, x - prev_x, y - prev_y)
                current[key] = (x, y)
            if step < steps:
                self._queue(frame_ms, frame, step + 1)
            elif callable(on_complete):
                on_complete()

        self._queue(frame_ms, frame, 1)

    def surrender_offer(self, hand):
        """Return 90% of the current valuation, rounded to cents."""
        return (round(self.hand_stake(hand) / 2.0 * self.CASHOUT_FACTOR, 2), 0.0, 0.0, 0.0) if self.can_surrender(hand) else (0.0, 0.0, 0.0, 0.0)

    def instant_surrender(self):
        hand = self.active_hand()
        if (not self.can_surrender(hand) or self.animation_running
                or self.settlement_running or self.ace_decision_mode):
            return
        hand_index = self.active_hand_index
        credit, _win_prob, _bust_prob, _ = self.surrender_offer(hand)
        layout = self._main_split_wager_layout()[hand_index]
        payout_position = (layout['base'][0]-self.CHIP_PITCH, layout['base'][1])
        wagers = [(*layout[component], float(stake), self.WAGER_CHIP_RADIUS)
                  for component, stake in (('base', hand['base_bet']),
                                           ('double', hand['double_added'])) if stake > 0]
        payout = [(*payout_position, credit, self.WAGER_CHIP_RADIUS)] if credit > 0 else []
        # Credit once, before animations, so leaving the game cannot lose or
        # refund an already resolved cash-out payment.
        self.balance += credit
        hand.update(status='surrendered', cashout_credit=credit,
            result=f'投降返还45% {self.format_money(credit)}', settlement='cashout',
            base_settlement='cashout',
            double_settlement='cashout' if hand['double_added'] > 0 else None,
            settlement_return=credit, cashout_visual_stage='paying')
        self.animation_running = True
        self.save_balance()
        self.last_result_lines.append(
            f'投降：退还半注的90%（主注45%） {self.format_money(credit)}')
        self.render_cards()
        self.update_display()

        def finished():
            hand['cashout_visual_stage'] = 'returned'
            self.animation_running = False
            self.render_cards()
            self.update_display()
            self._advance_hand()

        def return_payment():
            hand['cashout_visual_stage'] = 'returning'
            self.render_cards()
            self.update_display()
            self._animate_settlement_chips(payout, (575.0, 674.0), 200,
                f'cashout_return_fly_{hand_index}', finished)

        def collect_wagers():
            hand['cashout_visual_stage'] = 'collecting'
            self.render_cards()
            self.update_display()
            self._animate_settlement_chips(wagers, lambda sx, sy: (sx, -35.0), 300,
                f'cashout_collect_fly_{hand_index}', return_payment)

        def paid():
            hand['cashout_visual_stage'] = 'display'
            self.render_cards()
            self.update_display()
            self._queue(300, collect_wagers)

        sources = [(575.0, 43.0, credit, self.WAGER_CHIP_RADIUS)] if credit > 0 else []
        self._animate_settlement_chips(sources, payout_position, 440,
            f'cashout_payment_fly_{hand_index}', paid)

    @staticmethod
    def _same_color(card_a, card_b):
        red = {'Diamond', 'Heart'}
        return (card_a[0] in red) == (card_b[0] in red)

    @staticmethod
    def _rank_number_for_straight(card):
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
    def _is_three_card_straight(cls, cards):
        vals = sorted(cls._rank_number_for_straight(card) for card in cards)
        if vals == [1, 2, 3] or vals == [11, 12, 13]:
            return True
        # Ace may also be high in Q-K-A.
        high_vals = sorted(14 if v == 1 else v for v in vals)
        return len(set(vals)) == 3 and (vals[2] - vals[0] == 2 or high_vals == [12, 13, 14])

    @staticmethod
    def _three_card_totals(cards):
        totals = {0}
        for _suit, rank in cards:
            if rank == 'A':
                choices = (1, 11)
            elif rank in ('10', 'J', 'Q', 'K'):
                choices = (10,)
            else:
                choices = (int(rank),)
            totals = {base + value for base in totals for value in choices}
        return totals

    def _maybe_settle_crazy7(self):
        for seat in self.SEATS:
            if self.round_original_bets[seat]>0:
                self._maybe_settle_crazy7_for_seat(seat)

    def _maybe_settle_crazy7_for_seat(self, seat):
        """Synchronise Crazy 7 progressively from round cards 0 -> 2 -> 3.

        Card 0 decides whether the bet is already dead.  If it is a 7, show the
        currently secured 5:1 tier while waiting for card 2.  If card 2 is not a
        7, 5:1 is final; if card 2 is a 7, show the secured 25:1/150:1 tier while
        waiting for card 3.  Card 3 then performs the final odds synchronisation:
        another 7 upgrades to 500:1/2000:1, otherwise the card-2 tier remains.
        Provisional tiers only update the pointed odds marker; money is credited
        exactly once when the tier becomes final.
        """
        key = (seat, 'Crazy 7')
        if key in self.side_bet_results:
            return
        seq = self.seat_deal_sequences[seat]
        if not seq:
            return

        c0 = seq[0]
        if c0[1] != '7':
            self.side_bet_hit_odds.pop(key, None)
            self.side_bet_hit_labels.pop(key, None)
            # V19: record the loss immediately for logic purposes, but do NOT
            # collect the Crazy 7 chip while the opening cards are still flying.
            # It joins the other resolved losing side bets after the initial deal.
            self._credit_side_bet(key, None, '第0张非7', collect_loss=False)
            self.save_balance()
            return

        # Card 0 is a 7: 5:1 is already secured, but it is provisional until
        # target card 2 is known.
        self.side_bet_hit_odds[key] = 5.0
        self.side_bet_hit_labels[key] = '第一目标7'
        if len(seq) < 3:
            return

        c2 = seq[2]
        if c2[1] != '7':
            self._credit_side_bet(key, 5, '第一目标7')
            self.save_balance()
            return

        # Cards 0 and 2 are both 7.  The secured tier is 25:1, or 150:1 when
        # those two target cards share a suit.  Keep it provisional until card 3.
        if c0[0] == c2[0]:
            provisional_odds, provisional_label = 150.0, '前两目标同花7'
        else:
            provisional_odds, provisional_label = 25.0, '前两目标7'
        self.side_bet_hit_odds[key] = provisional_odds
        self.side_bet_hit_labels[key] = provisional_label
        if len(seq) < 4:
            return

        c3 = seq[3]
        if c3[1] == '7':
            if c0[0] == c2[0] == c3[0]:
                result = (2000, '目标三张同花7')
            else:
                result = (500, '目标三张7')
        else:
            result = (provisional_odds, provisional_label)

        # Final card is known: overwrite the provisional marker with the final
        # correct tier, then settle/credit exactly once.
        self.side_bet_hit_odds.pop(key, None)
        self.side_bet_hit_labels.pop(key, None)
        self._credit_side_bet(key, *result)
        self.save_balance()

    def _settle_bust_side_bet_for_seat(self, seat):
        key = (seat, 'Bust!')
        if key in self.side_bet_results:
            return
        total, _ = BlackjackEngine.hand_value(self.dealer_cards)
        if total <= 21:
            self._credit_side_bet(key, None, '庄家未爆')
        else:
            count = len(self.dealer_cards)
            if count >= 8:
                odds = 250
            elif count == 7:
                odds = 100
            elif count == 6:
                odds = 50
            elif count == 5:
                odds = 9
            elif count == 4:
                odds = 2
            else:
                odds = 1
            self._credit_side_bet(key, odds, f'庄家{count}张爆牌')
        self.save_balance()

    def _credit_side_bet(self, key, profit_odds, label, collect_loss=True):
        """Resolve one side bet tier even when no wager was placed.

        A hit is a table event, not a wager event: V10 records the winning tier
        for settlement flashing/odds display regardless of stake. Money is only
        credited when an actual wager exists.  ``collect_loss=False`` lets a
        known loss be recorded during dealing while deferring its chip pickup
        until the common side-bet collection stage.
        """
        if key in self.side_bet_results:
            return
        stake = float(self.round_side_bets.get(key, 0.0))
        if profit_odds is None:
            self.side_bet_results[key] = '输'
            self.side_bet_return_amounts[key] = 0.0
            if collect_loss:
                self._collect_losing_side_bet_upward(key)
            return
        odds = float(profit_odds)
        self.side_bet_hit_odds[key] = odds
        self.side_bet_hit_labels[key] = str(label)
        if stake > 0.0:
            credit = stake * (1.0 + odds)
            self.balance += credit
            self.side_bet_return_amounts[key] = credit
            self.side_bet_results[key] = f'{label} {odds:g}:1 +{self.format_money(credit - stake)}'
            self._animate_side_bet_profit(key)
        else:
            self.side_bet_return_amounts[key] = 0.0
            self.side_bet_results[key] = f'{label} {odds:g}:1'

    def _settle_initial_side_bets(self):
        for seat in self.round_initial_cards:
            self._settle_initial_side_bets_for_seat(seat)

    def _has_dealer_bust_wager(self):
        # Dealer-dependent side bets require the dealer to finish under S17,
        # even when every player hand has busted or surrendered.
        return any(self.round_side_bets.get((seat, kind), 0.0) > 0
                   for seat in self.SEATS for kind in ('Bust!', '3 Card Bust'))

    def _settle_dealer_bust_side_bets(self):
        total, _ = BlackjackEngine.hand_value(self.dealer_cards)
        three_card_bust = len(self.dealer_cards) == 3 and total > 21
        for seat in self.SEATS:
            if self.round_original_bets[seat] <= 0:
                continue
            self._settle_bust_side_bet_for_seat(seat)
            self._credit_side_bet((seat, '3 Card Bust'),
                4.5 if three_card_bust else None,
                '庄家3张爆牌' if three_card_bust else '未中')

    # -------------------------------------------------------------- dealer phase
    def _advance_hand(self):
        if not self.round_active: return
        for idx in range(self.active_hand_index+1,len(self.hands)):
            if self.hands[idx]['status']=='active':
                self.active_hand_index=idx; self.render_cards(); self.update_display()
                self._prepare_active_split_hand()
                return
        self._start_dealer_turn()

    def _all_hands_bust_or_surrendered(self):
        if not self.hands:
            return False
        for hand in self.hands:
            total, _ = BlackjackEngine.hand_value(hand.get('cards', ()))
            if hand.get('status') in ('surrendered', 'even_money'):
                continue
            if hand.get('status') == 'bust' or total > 21:
                continue
            return False
        return True

    def _single_natural_blackjack(self):
        # All remaining live families are natural BJs; no ordinary hand needs a dealer total.
        live = [h for h in self.hands if h['status'] not in ('surrendered', 'even_money', 'bust')]
        return bool(live) and all(not h['from_split'] and BlackjackEngine.is_blackjack(h['cards']) for h in live)

    def _resolve_finished_hands_after_insurance_probe(self):
        # Use the same dealer-BJ accounting even when every player hand busted.
        if BlackjackEngine.is_blackjack(self.dealer_cards[:2]):
            self._resolve_dealer_blackjack()
        else:
            self._resolve_normal_round()

    def _start_dealer_turn(self):
        if not self.round_active or self.animation_running:
            return
        dealer_bust_wager = self._has_dealer_bust_wager()
        all_dead = self._all_hands_bust_or_surrendered()
        natural = self._single_natural_blackjack()
        up_rank = self.dealer_cards[0][1] if self.dealer_cards else None
        possible_blackjack = up_rank in ('A', '10', 'J', 'Q', 'K')
        self.animation_running = True
        self.render_cards()
        self.update_display()
        if (not dealer_bust_wager and ((all_dead and self.insurance_bet <= 0)
                or (natural and not possible_blackjack))):
            self._queue(220, self._resolve_normal_round)
            return
        self.dealer_phase_active = True
        def after_second():
            if BlackjackEngine.is_blackjack(self.dealer_cards[:2]):
                resolver = self._resolve_dealer_blackjack
            elif not dealer_bust_wager and (all_dead or natural):
                resolver = self._resolve_normal_round
            else:
                resolver = self._dealer_draw_until_done
            self._queue(260, resolver)
        self._deal_dealer_card_animated(on_complete=after_second)

    def _dealer_draw_until_done(self):
        total,_soft=BlackjackEngine.hand_value(self.dealer_cards)
        if total < 17:
            self._deal_dealer_card_animated(on_complete=lambda:self._queue(180,self._dealer_draw_until_done))
            return
        self._queue(260,self._resolve_normal_round)

    def _resolve_dealer_blackjack(self):
        """In Multiply a dealer Blackjack loses the entire doubled main wager."""
        self._settle_main_round(dealer_bj=True)

    def _resolve_normal_round(self):
        self._settle_main_round(dealer_bj=False)

    def _calculate_last_win_amount(self):
        """Total money returned to the player's balance for this round.

        V16 intentionally includes returned stake: normal wins, Blackjack returns,
        PUSH, OBO/refunds, instant cashout/Even Money, side-bet credits and insurance
        credits.  Losing wagers contribute zero.
        """
        returned_total = sum(
            max(0.0, float(hand.get('settlement_return', 0.0)))
            for hand in self.hands
        )
        returned_total += sum(
            max(0.0, float(self.side_bet_return_amounts.get(key, 0.0)))
            for key in self.side_bet_return_amounts
        )
        returned_total += max(0.0, float(self.insurance_return_amount))
        return returned_total

    def _finish_round(self, dealer_bj=False):
        # Payouts are already credited by the original game evaluators. These
        # motions only display principal and profit; they never change balance.
        for seat in self.SEATS:
            key = (seat, 'Crazy 7')
            if self.round_original_bets[seat] > 0 and key not in self.side_bet_results:
                self._credit_side_bet(key, self.side_bet_hit_odds.get(key),
                    self.side_bet_hit_labels.get(key, '未中'))
        self.insurance_resolved = True
        for info in self.seat_insurance.values():
            info['returned'] = info['bet']*(1+self.INSURANCE_PROFIT) if dealer_bj else 0.0
        self.animation_running = False
        self.save_balance()
        self.last_win_amount = self._calculate_last_win_amount()
        self.show_last_win = True
        self.settlement_running = True
        self.settlement_visual_stage = 'paying'
        self.flash_mode = None
        self.flash_winning_side_bets = set()
        self.flash_winning_hand_indices = set()
        self.flash_main_bet = self.flash_main_push_only = self.flash_insurance_rule = False
        self.canvas.delete('win_flash_area')
        profits = [row for row in self._settlement_chip_rows()
                   if row['role']=='profit' and row['key'][0]!='side']
        self.pending_profit_chips.update(row['key'] for row in profits)
        self.render_cards()
        self.update_display()
        self._animate_losing_chips_out()
        self._fade_dealer_push_notice(self.dealer_three_card_main_push)
        def display_outcome():
            self.settlement_visual_stage = 'display'
            self._render_settlement_chips()
            self._queue(1800,self._finish_flash_with_chip_return)
        if not profits:
            self._queue(440 if self.pending_profit_chips else 300,display_outcome)
            return
        pending = [len(profits)]
        def arrived(row):
            self.pending_profit_chips.discard(row['key'])
            self._render_settlement_chips()
            pending[0] -= 1
            if not pending[0]:
                display_outcome()
        for index,row in enumerate(profits):
            self._animate_settlement_chips([(575,43,row['amount'],row['radius'])],
                row['pos'],440,f'settlement_profit_fly_{index}',lambda r=row:arrived(r))

    def _reset_after_round(self):
        if self._closing: return
        try:
            self.engine.finish_round()
        except (CSMError, OSError) as exc:
            self.accept_bets = False
            messagebox.showerror('自动洗牌机', f'本局牌张归还失败，游戏已暂停：{exc}',
                                 parent=self.winfo_toplevel())
            return
        # Preserve the visible dealer/player cards exactly as they finished.
        # They are removed only on the NEXT 开牌 via the 0.20 s upper-left exit.
        self.previous_round_cards_present = bool(self.canvas.find_withtag('dealt_card'))
        self.canvas.delete('hand_wager'); self.canvas.delete('insurance_chip')
        self._fade_dealer_push_notice(False)
        self.dealer_three_card_main_push = False
        self._set_rules_strip_visible(False)

        self.settlement_visual_stage=None; self.pending_profit_chips=set()
        self._opening_wager_animation=False
        self.round_active=False; self.round_original_bet=0.0
        self.round_side_bets=self._empty_side_bets()
        self.side_bet_results={}; self.side_bet_return_amounts={}
        self.side_bet_hit_odds={}; self.side_bet_hit_labels={}
        self.side_bet_early_collected=set()
        self.flash_winning_side_bets=set(); self.flash_main_bet=False; self.flash_main_push_only=False
        self.flash_winning_hand_indices=set(); self.flash_insurance_rule=False
        self.settlement_running=False; self.settlement_flash_step=0; self.flash_mode=None
        self.dealer_phase_active=False
        self.round_deal_sequence=[]; self.insurance_bet=0.0; self.insurance_result=''
        self.insurance_return_amount=0.0; self.insurance_chip_visible=False; self.ace_decision_mode=None
        self.hands=[]; self.dealer_cards=[]; self.active_hand_index=0; self.split_actions=0
        self.round_original_bets={seat:0.0 for seat in self.SEATS}
        self.split_actions_by_seat={seat:0 for seat in self.SEATS}
        self.seat_deal_sequences={seat:[] for seat in self.SEATS}
        self.round_initial_cards={}
        self.seat_insurance={seat:dict(bet=0.0,returned=0.0,visible=False) for seat in self.SEATS}
        self.insurance_resolved=False
        self.ace_decision_seat=None; self.ace_decision_queue=[]
        self._sync_main_totals()

        def after_layout():
            self._set_round_control_visibility(False); self.canvas.itemconfigure('chip_selector',state='normal')
            self._raise_visible_bottom_controls(False); self.select_chip(self.selected_chip)
            self.save_runtime_store(burn_complete=True)
            self.accept_bets=True
            self.update_display(); self._set_round_control_visibility(False); self._raise_visible_bottom_controls(False)
        self._animate_betting_station(False,on_complete=after_layout)

    def _hand_short_status(self, hand):
        mapping = {
            'bust': '爆',
            'blackjack': 'BJ',
            'even_money': 'Even',
        }
        return mapping.get(hand.get('status'), '')

    def update_display(self):
        if self._closing:
            return
        self._update_main_spot_visibility()
        self.canvas.itemconfigure(self.balance_text, text=f'余额: ${self.balance:,.2f}')
        if self.show_last_win:
            text = f'上局返还: {self.format_money(self.last_win_amount)}'
        else:
            total = (sum(self.hand_stake(h) for h in self.hands)+self.insurance_bet+
                     sum(self.round_side_bets.values())) if self.round_active else (
                         sum(self.current_bets.values())+sum(self.current_side_bets.values()))
            text = f'本局下注: ${float(total):,.0f}'
        self.canvas.itemconfigure(self.total_bet_text, text=text)
        self.update_bet_chips()
        self._render_insurance_chip()
        self._draw_side_bet_progress_badges()
        betting = self._can_change_bets() and self.bet_chip_animation_count==0
        pending = self.current_bet>0 or any(self.current_side_bets.values())
        previous = self.last_bet>0 or any(self.last_side_bets.values())
        self._set_button(self.clear_button, betting and pending)
        self._set_button(self.repeat_button, betting and previous)
        self._set_button(self.deal_button, betting and any(self.current_bets.values()))
        self._set_round_control_visibility(self.round_active)
        hand = self.active_hand()
        active = bool(hand and hand['status']=='active' and not hand['needs_split_draw'] and
            not self.animation_running and not self.settlement_running and not self.ace_decision_mode)
        for seat in self.SEATS:
            own_turn = active and hand['seat']==seat
            for action, allowed, label in (
                ('hit', own_turn and self.can_hit(hand), '要牌'),
                ('stand', own_turn, '停牌'),
                ('double', own_turn and self.can_double(hand), '加倍'),
                ('split', own_turn and self.can_split(hand), '分牌')):
                self._set_button(self.action_buttons[(seat, action)], allowed, label)
            cashout = own_turn and self.can_surrender(hand)
            label = '投降\n退还45%'
            if cashout:
                label = f'投降返还\n{self.format_money(self.surrender_offer(hand)[0])}'
            self._set_button(self.action_buttons[(seat, 'surrender')], cashout, label)
            deciding = self.ace_decision_mode and self.ace_decision_seat==seat and not self.animation_running
            is_even = self.ace_decision_mode=='even_money'
            affordable = self.balance+1e-9>=self.round_original_bets[seat]/2
            self._set_button(self.decision_buttons[(seat, 'accept')], deciding and (is_even or affordable),
                             '立刻获胜' if is_even else '购买保险')
            self._set_button(self.decision_buttons[(seat, 'decline')], bool(deciding), '赌！' if is_even else '不购买')
            highlighted = bool(own_turn or deciding)
            self.canvas.itemconfigure(self.seat_title_items[seat], fill='#F6D675' if highlighted else '#F2E6C9')
        for spot in self.bet_spots.values():
            self.canvas.itemconfigure(spot['rect'], fill=spot['normal_fill'])
        self.draw_special_offer()
        self._raise_wager_chips()

    @staticmethod
    def _instruction_pages():
        """Multiply content for the same directory/card/table manual as Classic."""
        return [
            (
                '玩法',
                '了解游戏目标，以及一局从下注、抽奖到发牌和结算的完整顺序。',
                [
                    ('游戏目标', '', [
                        ('本局目标', '让手牌尽量接近21点而不爆牌，并按加倍黑杰克的规则击败庄家。'),
                        ('基础牌值', 'A可计1或11；J、Q、K计10；其余牌按牌面计点。超过21点为爆牌。'),
                    ], []),
                    ('一局如何进行', '', [
                        ('玩家下注', '选择筹码，放置主注，并可选择完美对子、21+3、3张爆牌、疯狂7、热辣21或爆牌！边注。'),
                        ('加倍牌抽奖', '开牌后先锁定下注，在右上角抽取2–5张加倍牌和本局倍数。'),
                        ('筹码与发牌', '抽奖结束后，蓝色主注区消失，主注筹码向上移动。筹码到位后，依次发玩家第一张、庄家明牌和玩家第二张。'),
                        ('玩家决策', '选择要牌、停牌、加倍、分牌或投降。庄家明牌为A时，先选择是否购买保险。'),
                        ('庄家与结算', '庄家任何17点停牌。按主注、加倍牌、边注和保险的规则分别结算。'),
                    ], []),
                    ('玩家决策按钮', '', [
                        ('要牌  HIT', '再要一张牌。玩家爆牌后结束本手；21点自动停牌。'),
                        ('停牌  STAND', '结束本手。分牌后依次操作下一手，全部手牌结束后进入庄家回合。'),
                        ('加倍  DOUBLE', '每手仅两张牌时可用，包括普通分牌后的手牌。追加同额主注，只补一张牌后自动停牌；分A后不可加倍。'),
                        ('分牌  SPLIT', '两张同点值的牌可追加同额主注分成两手，10、J、Q、K按相同点值处理。每局最多分牌3次，共4手。'),
                        ('投降  SURRENDER', '仅首两张普通手牌时可用，退还半注的90%（主注45%）。边注仍独立结算；投降返还不应用加倍牌。'),
                        ('购买保险 / 不购买', '庄家明牌A时可用，包括玩家天然Blackjack。保险金额为原始主注的一半。'),
                    ], []),
                    ('分牌后的手牌', '', [
                        ('补牌顺序', '先为当前手补一张并完成本手操作，再为下一手补牌。每手主注与加倍追加金额分别结算。'),
                        ('分A规则', '每手只补一张后停牌；若补到A，可在最多3次分牌的上限内继续分A。'),
                        ('分牌21点', '分牌后两张21点属于普通21点，不按天然Blackjack的3:2赔付。'),
                    ], []),
                ],
            ),
            (
                '下注 & 限红',
                '各项目限红与筹码操作如下。',
                [
                    ('下注项目', '', [], [
                        ('下注项目与限红', ['项目', '限红'], [
                            ['主注', '$100–$500,000'],
                            ['完美对子', '每项最高$100,000'],
                            ['21+3', '每项最高$100,000'],
                            ['3张爆牌', '每项最高$100,000'],
                            ['疯狂7', '每项最高$100,000'],
                            ['热辣21', '每项最高$100,000'],
                            ['爆牌！', '每项最高$100,000'],
                        ]),
                    ]),
                    ('筹码操作', '', [
                        ('选择与放置', '点击下方筹码选择面额，左键点击下注区放置筹码。'),
                        ('清除下注', '右键点击边注可清除该项；右键点击主注可清除主注及边注。“清除”按钮清除本次全部下注。'),
                        ('重复下注', '按上局的原始主注及边注补齐下注。上局分牌、加倍追加和保险不会自动重复。'),
                        ('开牌', '点击“开牌”或按ENTER。主注必须符合限红；抽奖、筹码移动和发牌期间，下注与决策均锁定。'),
                    ], []),
                ],
            ),
            (
                '获胜条件 & 赔率',
                '先计算不含本金的净赢金额，再按加倍牌匹配结果乘倍，最后加回本金。',
                [
                    ('主注与保险', '以下返还金额包含本金；加倍后的主注包含追加金额。', [], [
                        ('主注结算', ['条件', '基础返还 / 处理'], [
                            ['普通主注获胜', '主注×2；有加倍牌匹配时再应用加倍'],
                            ['玩家天然Blackjack，庄家非Blackjack', '主注×2.5（3:2）；有匹配时再应用加倍'],
                            ['同点数 / 双方Blackjack', '平局，返还主注；不应用加倍'],
                            ['庄家恰好三张牌爆牌', '普通手牌主注平局；天然Blackjack按胜局结算'],
                            ['庄家四张或以上爆牌', '未爆牌、未投降的普通手牌按胜局结算'],
                            ['玩家爆牌 / 普通输局', '主注返还0'],
                            ['庄家Blackjack，玩家非Blackjack', '主注全输，包括加倍追加金额'],
                            ['投降', '返还半注的90%（主注45%）；不应用加倍'],
                            ['保险中奖（庄家Blackjack）', '保险注×3（净赢2:1）'],
                        ]),
                    ]),
                    ('加倍牌与赔率', '每局抽取2–5张加倍牌；花色和点数均相同才算匹配。', [
                        ('本局倍数', '可出现X2.5、X5、X10、X25或X50。'),
                        ('获胜返还公式', '有匹配时：最终返还 = 本金 +（基础净赢 × 本局倍数 × 匹配张数）。没有匹配时按普通赔率结算。'),
                        ('匹配计数', '各手分别计算匹配张数与最终返还。八副牌中重复出现的同花色、同点数手牌，可重复计入该手匹配张数。'),
                        ('分牌结算', '结算时，每手牌的筹码独立计算加倍获胜，仅使用本手主注（含加倍追加）与本手匹配张数，不合并其他手的筹码或匹配张数。'),
                        ('计算示例', '主注$2,000取得Blackjack，基础净赢$3,000；本局X2.5，匹配1张，净赢$7,500，加本金共返还$9,500。'),
                        ('适用项目', '仅获胜主注的净赢应用加倍；本金、平局、投降、边注和保险不乘倍。'),
                    ], []),
                    ('边注赔付表', '边注赔率表示净赢赔率；中奖另退边注本金。', [], [
                        ('完美对子：玩家首两张牌', ['牌型 / 条件', '赔率'], [
                            ['同花色同点对子', '25:1'],
                            ['同颜色同点对子', '12:1'],
                            ['不同颜色同点对子', '6:1'],
                        ]),
                        ('21+3：玩家首两张牌与庄家明牌', ['牌型 / 条件', '赔率'], [
                            ['三张同花同点', '100:1'],
                            ['同花顺', '40:1'],
                            ['三条', '30:1'],
                            ['顺子', '10:1'],
                            ['同花', '5:1'],
                        ]),
                        ('3张爆牌：庄家最终手牌', ['条件', '赔率'], [
                            ['庄家恰好3张手牌爆牌', '固定9:2（4.5:1）'],
                            ['庄家未爆牌或以其他张数爆牌', '输'],
                        ]),
                        ('疯狂7：第0、2、3张目标牌', ['条件', '赔率'], [
                            ['三张目标牌同花7', '2000:1'],
                            ['三张目标牌为7，非全部同花', '500:1'],
                            ['前两张目标牌同花7', '150:1'],
                            ['前两张目标牌为7，非同花', '25:1'],
                            ['仅第一张目标牌为7', '5:1'],
                        ]),
                        ('热辣21：玩家首两张牌与庄家明牌', ['牌型 / 条件', '赔率'], [
                            ['同花三7', '500:1'],
                            ['三7，非全部同花', '100:1'],
                            ['同花21点', '20:1'],
                            ['21点', '4:1'],
                            ['20点', '2:1'],
                            ['19点', '1:1'],
                        ]),
                        ('爆牌！：庄家最终爆牌张数', ['张数', '赔率'], [
                            ['8张或以上', '250:1'],
                            ['7张', '100:1'],
                            ['6张', '50:1'],
                            ['5张', '9:1'],
                            ['4张', '2:1'],
                            ['3张', '1:1'],
                        ]),
                    ]),
                ],
            ),
            (
                '牌型等级表',
                '查看天然Blackjack、普通点数与爆牌的牌例。',
                [
                    ('点数与牌例', '同一牌型也可能由其他牌面组成。', [], [
                        ('判定与牌例', ['等级', '牌型', '牌例'], [
                            ['1', '天然Blackjack：首两张21点', ('__CARD_IMAGES__', (('♠', 'A'), ('♥', 'K')))],
                            ['2', '普通21点', ('__CARD_IMAGES__', (('♠', '7'), ('♥', '7'), ('♦', '7')))],
                            ['3', '20点', ('__CARD_IMAGES__', (('♠', 'K'), ('♥', 'Q')))],
                            ['4', '爆牌：超过21点', ('__CARD_IMAGES__', (('♠', 'K'), ('♥', 'Q'), ('♦', '2')))],
                        ]),
                    ]),
                    ('同点数如何结算', '', [
                        ('天然Blackjack', '玩家天然Blackjack、庄家非Blackjack时按3:2获胜；双方Blackjack时主注平局。'),
                        ('普通点数', '双方未爆牌且点数相同时，主注平局；否则点数较高者胜。'),
                    ], []),
                ],
            ),
            (
                '特别事项',
                '连续洗牌、特殊爆牌与牌型判定的补充说明。',
                [
                    ('连续洗牌机', '8副完整牌 · CSM · 庄家任何17点停牌', [
                        ('连续供牌', '由CSM连续洗牌机供牌。每局结束后归还已发牌张，下一局继续由洗牌机供牌。'),
                        ('牌张回收', '按洗牌机规则回收与重新混入牌仓，无需手动切牌、烧牌或换靴。'),
                    ], []),
                    ('特别规则', '', [
                        ('庄家三张爆牌', '庄家恰好三张牌爆牌时，未爆牌、未投降的普通手牌主注平局，返还包括加倍追加在内的主注本金。'),
                        ('加倍牌匹配', '花色和点数均须相同；加倍后补到的玩家牌也计入匹配。奖励牌及匹配到的玩家牌使用金色牌面。奖励牌本身不会从CSM牌仓取走。'),
                        ('21+3顺子', '沿用Classic边注规则，A-2-3与Q-K-A均可组成顺子。'),
                        ('疯狂7目标牌', '从0开始计数：第0张为玩家第一张，第1张为庄家明牌，第2张为玩家第二张，第3张为随后发出的第一张牌，可为玩家要牌、分牌补牌、加倍牌或庄家第二张。只按最终达到的最高一档赔付。'),
                        ('3张爆牌边注', '与主注平局分别结算。下注$100中奖时净赢$450，另退本金$100，合计返还$550。'),
                        ('庄家继续补牌', '押了3张爆牌或爆牌！时，即使玩家全部爆牌、投降或已获天然Blackjack，庄家仍按任何17点停牌的规则完成补牌。'),
                        ('独立结算', '完美对子、21+3与热辣21使用分牌前的起始牌；疯狂7使用本局发牌顺序；3张爆牌与爆牌！使用庄家最终手牌。边注不应用右上角倍数，不随分牌追加，均独立于主注胜负结算。'),
                    ], []),
                ],
            ),
        ]

    def show_game_instructions(self):

        """Show the game manual in the shared card-based rules window."""

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

        dialog.title('加倍黑杰克 · 游戏说明')

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

        tk.Label(header, text='加倍黑杰克 · 游戏说明', font=(font_name, 20, 'bold'),

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

                        card_dir = next((os.path.join(root, 'A_Tools', 'Card', 'Poker2')

                                         for root in search_roots

                                         if os.path.isdir(os.path.join(root, 'A_Tools', 'Card', 'Poker2'))),

                                        os.path.join(search_roots[1], 'A_Tools', 'Card', 'Poker2'))

                        suits = {'♠': 'Spade', '♥': 'Heart', '♦': 'Diamond', '♣': 'Club'}

                        for suit, rank in value[1]:

                            filename = 'JOKER-A.png' if suit == 'JOKER' else f'{suits.get(suit, suit)}{rank}.png'

                            path = os.path.join(card_dir, filename)

                            try:

                                with Image.open(path) as source_image:

                                    card_width = 70

                                    card_height = max(1, round(source_image.height * card_width / source_image.width))

                                    small_image = source_image.resize((card_width, card_height), Image.LANCZOS)

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

    def _queue(self, delay_ms, func, *args):
        holder = {'id': None}

        def wrapped():
            aid = holder['id']
            if aid in self.after_ids:
                self.after_ids.remove(aid)
            if not self._closing:
                func(*args)

        aid = self.after(int(delay_ms), wrapped)
        holder['id'] = aid
        self.after_ids.append(aid)
        return aid

    def cancel_pending_callbacks(self):
        for aid in list(self.after_ids):
            try:
                self.after_cancel(aid)
            except (tk.TclError, ValueError):
                pass
        self.after_ids.clear()

    def _install_embedded_close_handler(self, force=False):
        """
        In casino-embedded mode, make the shared root-window X behave like Back.

        V24 installs this AFTER casino_games has finished replace_page().  Some host
        implementations reset WM_DELETE_WINDOW while replacing the current page, so
        installing it before replace_page() is not reliable.  force=True re-applies
        our handler without overwriting the originally saved host protocol.
        """
        if not getattr(self, 'close_returns_to_parent', False):
            return
        if not callable(self.on_back):
            return

        top = getattr(self, '_host_toplevel', None)
        if top is None:
            return

        try:
            if not self._embedded_wm_delete_installed:
                self._embedded_wm_delete_previous = top.tk.call(
                    'wm', 'protocol', top._w, 'WM_DELETE_WINDOW'
                )
                self._embedded_wm_delete_installed = True
            elif not force:
                return

            # Always bind after the host page swap.  In force mode this deliberately
            # overwrites any WM_DELETE_WINDOW callback installed by replace_page().
            top.protocol('WM_DELETE_WINDOW', self.exit_game)
        except tk.TclError:
            if not self._embedded_wm_delete_installed:
                self._embedded_wm_delete_previous = None
            self._embedded_wm_delete_installed = False

    def _restore_host_bindings(self):
        """Restore index.py/casino_games.py root handlers before leaving Blackjack."""
        if getattr(self, '_host_bindings_restored', False):
            return
        self._host_bindings_restored = True
        top = getattr(self, '_host_toplevel', None)
        if top is None:
            return

        try:
            previous = getattr(self, '_previous_return_binding', '')
            top.tk.call('bind', top._w, '<Return>', previous)
        except tk.TclError:
            pass
        try:
            previous = getattr(self, '_previous_escape_binding', '')
            top.tk.call('bind', top._w, '<Escape>', previous)
        except tk.TclError:
            pass

        if getattr(self, '_embedded_wm_delete_installed', False):
            try:
                previous = self._embedded_wm_delete_previous or ''
                top.tk.call('wm', 'protocol', top._w, 'WM_DELETE_WINDOW', previous)
            except tk.TclError:
                pass
            self._embedded_wm_delete_installed = False

    def exit_game(self):
        if self._closing:
            return
        self._closing = True
        self.cancel_pending_callbacks()

        # Refund only unresolved escrow on a forced exit. Already-settled cashouts
        # and Even Money are not refunded again.
        if not self.round_active:
            self.balance += self.current_bet + sum(self.current_side_bets.values())
            self.current_bet = 0.0
            self.current_bets = {seat:0.0 for seat in self.SEATS}
            self.current_side_bets = self._empty_side_bets()
        else:
            unresolved = 0.0
            for hand in self.hands:
                if hand.get('settlement') is None:
                    unresolved += self.hand_stake(hand)
            unresolved += 0.0 if self.insurance_resolved else self.insurance_bet
            for key, stake in self.round_side_bets.items():
                if key not in self.side_bet_results:
                    unresolved += float(stake)
            self.balance += unresolved

        # Return every card still leased to this local Blackjack instance,
        # including an unused remainder of the current chamber.
        try:
            self.engine.close()
        except Exception as exc:
            messagebox.showerror('自动洗牌机',
                                 f'退出时归还或强制洗牌失败，牌仍保留在 CSM 记录中：{exc}',
                                 parent=self.winfo_toplevel())

        try:
            self.save_runtime_store(burn_complete=True)
        except Exception:
            pass
        self.final_balance = float(self.balance)
        try:
            self.save_balance()
        except Exception:
            pass

        # V23: restore the host root's original X/Return/Escape handlers FIRST.
        # When casino_games opted into close_returns_to_parent, on_back() replaces
        # this Frame with CasinoGamesPage in the SAME Tk root. Never destroy it here.
        self._restore_host_bindings()
        if callable(self.on_back):
            self.on_back(self.final_balance)

    def _empty_side_bets(self):
        return {(seat, key): 0.0 for seat in self.SEATS for key in self.SIDE_BET_KEYS}

    def _sync_main_totals(self):
        self.current_bet = sum(self.current_bets.values())
        self.last_bet = sum(self.last_bets.values())
        self.round_original_bet = sum(self.round_original_bets.values())

    def _raise_wager_chips(self):
        """Keep every displayed wager above cards, labels, and table controls."""
        self.canvas.tag_raise('wager_chip')

    @staticmethod
    def _shade_color(color, factor):
        rgb = [max(0, min(255, round(int(color[i:i+2], 16)*factor))) for i in (1, 3, 5)]
        return '#' + ''.join(f'{value:02x}' for value in rgb)

    def _update_main_spot_visibility_original(self):
        playing = bool(self.round_active or self.settlement_running or
                       (self.animation_running and not self.accept_bets))
        for seat in self.SEATS:
            self.canvas.itemconfigure(self.bet_spots[(seat,'MAIN')]['rect'],
                state='hidden' if playing and not self._special_offer_running else 'normal')

    def _update_main_spot_visibility(self):
        self._update_main_spot_visibility_original()
        for spot in self.bet_spots.values():
            if spot.get('shape') == 'oval' and spot.get('surface_tag'):
                state = self.canvas.itemcget(spot['rect'], 'state')
                self.canvas.itemconfigure(spot['surface_tag'], state=state)
                self.canvas.itemconfigure(spot['title_tag'], state=state)
        self._raise_wager_chips()

    def _can_change_bets(self):
        return bool(self.accept_bets and not self.round_active and not self.animation_running
                    and not self.settlement_running)

    def _place_seat_bet(self, seat, kind):
        key = (seat, kind)
        if key not in self.bet_spots or not self._can_change_bets():
            return
        current = self.current_bets[seat] if kind=='MAIN' else self.current_side_bets[key]
        maximum = self.MAX_MAIN_BET if kind=='MAIN' else self.MAX_SIDE_BET
        amount = min(self.selected_chip, max(0.0, maximum-current))
        if amount <= 0:
            return
        if self.balance+1e-9 < amount:
            messagebox.showwarning('余额不足', '余额不足以放置该筹码。', parent=self.winfo_toplevel())
            return
        self.balance -= amount
        if kind == 'MAIN':
            self.current_bets[seat] += amount
        else:
            self.current_side_bets[key] += amount
        self._sync_main_totals()
        self.show_last_win = False
        self.pending_bet_animation[key] += amount
        self.bet_chip_animation_count += 1
        self.update_display()
        self._animate_selected_chip_to_spot(key,
            lambda: self._finish_bet_chip_animation(key, amount), amount=amount)

    def _clear_seat_bet(self, seat, kind):
        if not self._can_change_bets() or self.bet_chip_animation_count:
            return
        keys = [(seat, k) for k in self.SIDE_BET_KEYS] if kind=='MAIN' else [(seat, kind)]
        refund = self.current_bets[seat] if kind=='MAIN' else 0.0
        if kind == 'MAIN':
            self.current_bets[seat] = 0.0
            self.pending_bet_animation[(seat, 'MAIN')] = 0.0
        for key in keys:
            refund += self.current_side_bets[key]
            self.current_side_bets[key] = self.pending_bet_animation[key] = 0.0
        self.balance += refund
        self._sync_main_totals()
        self.update_display()
        self.save_balance()

    def _seat_hand_geometry(self, snapshot=None):
        hands = self.hands if snapshot is None else snapshot
        result = {}
        for seat, (x0, x1) in self.SEAT_BOUNDS.items():
            indices = [i for i, h in enumerate(hands) if h['seat']==seat]
            n = max(1, len(indices))
            lane_width = (x1-x0-24)/n
            for order, index in enumerate(indices):
                left = x0+12+order*lane_width
                right = left+lane_width
                result[index] = (left, right, (left+right)/2, order, n)
        return result

    def _player_card_position(self, hand, geometry, card_index):
        left, right, cx, _order, _n = geometry
        # The first card clears the enlarged MAIN chip.
        # Reserve fan space once; later cards never move cards already dealt.
        main_chip_x, origin_y = self.bet_spots[(hand['seat'],'MAIN')]['chip_pos']
        main_chip_y = origin_y-self.MAIN_WAGER_LIFT
        first_x = (main_chip_x if _n==1 else cx)-self.CARD_WIDTH/2
        first_y = main_chip_y-self.CARD_HEIGHT-self.WAGER_CHIP_RADIUS-self.CARD_WAGER_GAP
        fan_step = min(44.0, max(0.0, (right-8-first_x-self.CARD_WIDTH)/3))
        index = max(0, int(card_index))
        # Keep the normal horizontal step for every card. Cards 5-7 turn
        # downward; card 8 onward turns upward again, 24px per new card.
        x = first_x+fan_step*index
        if index<=3:
            y = first_y-24.0*index
        elif index<=6:
            y = first_y-72.0+24.0*(index-3)
        else:
            y = first_y-24.0*(index-6)
        if hand.get('double_card_index')==index:
            # Keep the card's centre when its dimensions change to 112 x 80.
            x -= (self.CARD_HEIGHT-self.CARD_WIDTH)/2
            y += (self.CARD_HEIGHT-self.CARD_WIDTH)/2
            x += 15
            y -= 15
        return x,y

    def _outcome_chip_rows(self, key, stake, returned, position, radius, tags,
                           profit_position=None):
        stake = max(0.0,float(stake))
        principal = stake if returned is None else min(stake,max(0.0,float(returned)))
        profit = 0.0 if returned is None else max(0.0,round(float(returned)-stake,2))
        rows = []
        if principal>0:
            rows.append(dict(key=(*key,'principal'),role='principal',amount=principal,
                pos=position,radius=radius,tags=(*tags,'principal_chip')))
        if profit>0:
            # All winnings sit to the left of their original wager at the same y.
            dx = -(2*radius+self.CHIP_GAP)
            rows.append(dict(key=(*key,'profit'),role='profit',amount=profit,
                pos=(position[0]+dx,position[1]) if profit_position is None else profit_position,
                radius=radius,
                tags=(*tags,'profit_chip')))
        return rows

    def _draw_outcome_rows(self, rows):
        if self.settlement_visual_stage=='returning':
            return
        for row in sorted(rows,key=lambda row:row['role']!='principal'):
            if row['key'] not in self.pending_profit_chips:
                self._draw_baccarat_chip(*row['pos'],row['amount'],
                    tags=row['tags'],radius=row['radius'])

    def _main_wager_rows(self):
        if not self.round_active or self._opening_wager_animation:
            return []
        rows = []
        layout = self._main_split_wager_layout()
        for index,hand in enumerate(self.hands):
            base_x, base_y = layout[index]['base']
            cashout_stage = hand.get('cashout_visual_stage')
            if cashout_stage is not None:
                # The whole cash-out payment lands in the winnings area first.
                # Original stakes remain until that payment has arrived.
                tags = ('hand_wager', f'hand_wager_{index}')
                if cashout_stage in ('paying', 'display'):
                    for component, stake in (('base', hand['base_bet']),
                                             ('double', hand['double_added'])):
                        rows.extend(self._outcome_chip_rows(
                            ('main', index, component), stake, None,
                            layout[index][component], self.WAGER_CHIP_RADIUS,
                            (*tags, f'{component}_wager', f'hand_{index}_{component}_chip')))
                credit = float(hand.get('cashout_credit', 0.0))
                if cashout_stage in ('display', 'collecting') and credit > 0:
                    rows.append(dict(key=('main', index, 'cashout', 'payout'),
                        role='cashout', amount=credit, pos=(base_x-self.CHIP_PITCH, base_y),
                        radius=self.WAGER_CHIP_RADIUS, tags=(*tags, 'cashout_wager', f'hand_{index}_cashout_chip')))
                # Collected cash-outs stay out of the later round settlement.
                continue
            for component,stake in (('base',hand['base_bet']),('double',hand['double_added'])):
                returned = self._component_return_amount(hand,component) if self.settlement_running else None
                # Left to right: Double profit, base profit, base stake, Double stake.
                # Each 60px chip is separated from its neighbour by 4px.
                profit_position = (base_x-((2*self.CHIP_PITCH) if component=='double' else self.CHIP_PITCH),base_y)
                rows.extend(self._outcome_chip_rows(('main',index,component),stake,returned,
                    layout[index][component],self.WAGER_CHIP_RADIUS,
                    ('hand_wager',f'hand_wager_{index}',f'{component}_wager',
                     f'hand_{index}_{component}_chip'),profit_position=profit_position))
        return rows

    def _animate_starting_wagers(self, on_complete):
        starts,ends = {},{}
        self._opening_wager_animation = True
        layout = self._main_split_wager_layout()
        for index,hand in enumerate(self.hands):
            tag = f'opening_wager_{index}'
            start = self.bet_spots[(hand['seat'],'MAIN')]['chip_pos']
            self._draw_baccarat_chip(*start,hand['base_bet'],
                tags=('opening_wager',tag),radius=self.WAGER_CHIP_RADIUS)
            # Lift the principal chip 60px from its betting spot. The first card
            # is positioned above this landing point with a 10px overlap.
            starts[tag],ends[tag] = start,layout[index]['base']
        def landed():
            self.canvas.delete('opening_wager')
            self._opening_wager_animation = False
            self.render_cards()
            self.update_display()
            on_complete()
        self._animate_canvas_positions(starts,ends,duration_ms=220,on_complete=landed)

    def _animate_side_bet_profit(self, key):
        stake = self.round_side_bets.get(key,0.0)
        rows = self._outcome_chip_rows(('side',*key),stake,
            self.side_bet_return_amounts.get(key,0.0),self.bet_spots[key]['chip_pos'],self.WAGER_CHIP_RADIUS,())
        for row in rows:
            if row['role']=='profit':
                self.pending_profit_chips.add(row['key'])
                def arrived(k=row['key']):
                    self.pending_profit_chips.discard(k)
                    self.update_bet_chips()
                self._animate_settlement_chips([(575,43,row['amount'],self.WAGER_CHIP_RADIUS)],row['pos'],440,
                    f'side_profit_fly_{self.SIDE_BET_KEYS.index(key[1])}',arrived)

    def _dealer_badge_fill(self):
        if not self.dealer_cards:
            return '#ffffff'
        total,_soft = BlackjackEngine.hand_value(self.dealer_cards)
        if total>21:
            return '#e34848'
        if self.settlement_running:
            results = [h.get('settlement') for h in self.hands
                       if h.get('status') not in ('surrendered','even_money')]
            if results and all(result=='push' for result in results):
                return '#b9dcff'
            if results and all(result=='lose' for result in results):
                return '#b9efb4'
            if results and all(result=='win' for result in results):
                return '#e34848'
            return '#f2b0b0'
        if self.dealer_phase_active and len(self.dealer_cards)>=2 and total>=17:
            return '#f2b0b0'
        return '#ffffff'

    def _card_dimensions(self, rotation=0):
        return ((self.CARD_HEIGHT,self.CARD_WIDTH) if rotation%180
                else (self.CARD_WIDTH,self.CARD_HEIGHT))

    def _oriented_card_pil(self, card, rotation=0, use_back=False, golden=False):
        if Image is None:
            return None
        faces = self.external_golden_card_pil if golden else self.external_card_pil
        base = self.external_back_pil if use_back else faces.get(tuple(card))
        if base is None:
            base = self._make_fallback_card_pil(card, not use_back, golden=golden and not use_back)
        return base.rotate(-rotation, expand=True) if rotation else base

    def _oriented_card_photo(self, card, rotation=0, use_back=False, golden=False):
        if not rotation:
            return self.external_back_image if use_back else self._face_photo(card, golden=golden)
        if Image is None or ImageTk is None:
            return None
        if not hasattr(self, '_rotated_card_photos'):
            self._rotated_card_photos = {}
        key = ('back' if use_back else tuple(card),rotation,bool(golden and not use_back))
        if key not in self._rotated_card_photos:
            base = self._oriented_card_pil(card, rotation, use_back, golden)
            self._rotated_card_photos[key] = ImageTk.PhotoImage(base, master=self)
        return self._rotated_card_photos[key]

    def _invoke_seat_action(self, seat, command):
        hand = self.active_hand()
        if (hand and hand['seat']==seat and not self.ace_decision_mode
                and not self.animation_running and not self.settlement_running):
            command()

    def _next_ace_decision(self):
        if self.ace_decision_queue:
            seat, mode = self.ace_decision_queue.pop(0)
            self.ace_decision_seat, self.ace_decision_mode = seat, mode
            self.update_display()
            return
        self.ace_decision_seat = self.ace_decision_mode = None
        self.active_hand_index = -1
        self._advance_hand()

    def _draw_side_odds(self, tag):
        self.canvas.delete(tag)  # payout tiers stay in the ledger, without table labels

    def _settlement_chip_rows(self):
        rows = self._main_wager_rows()
        for key,stake in self.round_side_bets.items():
            if stake>0:
                spot = self.bet_spots[key]
                rows.extend(self._outcome_chip_rows(('side',*key),stake,
                    self.side_bet_return_amounts.get(key,0.0),spot['chip_pos'],self.WAGER_CHIP_RADIUS,
                    ('bet_chip_dynamic',spot['tag'])))
        for seat,info in self.seat_insurance.items():
            if info['bet']>0:
                rows.extend(self._outcome_chip_rows(('insurance',seat),info['bet'],
                    info['returned'],self.insurance_positions[seat],self.INSURANCE_CHIP_RADIUS,('insurance_chip',)))
        return rows

    def _render_settlement_chips(self):
        self.update_bet_chips()
        self.canvas.delete('hand_wager')
        self._draw_main_hand_wagers()
        self._render_insurance_chip()
        self._raise_wager_chips()

    def _settle_initial_side_bets_for_seat(self, seat):
        if len(self.round_initial_cards.get(seat, [])) < 2 or not self.dealer_cards:
            return
        p0, p1 = self.round_initial_cards[seat][:2]
        dealer = self.dealer_cards[0]

        # Perfect Pair: always evaluate so a hit flashes even with zero stake.
        odds = None
        label = '完美对子'
        if p0[1] == p1[1]:
            if p0[0] == p1[0]:
                odds, label = 25, '同花对子'
            elif self._same_color(p0, p1):
                odds, label = 12, '同色对子'
            else:
                odds, label = 6, '杂色对子'
        self._credit_side_bet((seat, 'Perfect Pair'), odds, label)

        trio = [p0, p1, dealer]
        suits_same = len({card[0] for card in trio}) == 1
        ranks_same = len({card[1] for card in trio}) == 1
        straight = self._is_three_card_straight(trio)

        # 21+3: suited trips > straight flush > trips > straight > flush.
        if suits_same and ranks_same:
            result = (100, '三张同花同点')
        elif suits_same and straight:
            result = (40, '同花顺')
        elif ranks_same:
            result = (30, '三条')
        elif straight:
            result = (10, '顺子')
        elif suits_same:
            result = (5, '同花')
        else:
            result = (None, '未中')
        self._credit_side_bet((seat, '21+3'), *result)

        # Hot 21. Exact three 7s have priority. Ace may count as 1 or 11.
        all_sevens = all(card[1] == '7' for card in trio)
        totals = self._three_card_totals(trio)
        if all_sevens and suits_same:
            result = (500, '同花三7')
        elif all_sevens:
            result = (100, '三7')
        elif 21 in totals and suits_same:
            result = (20, '同花21点')
        elif 21 in totals:
            result = (4, '21点')
        elif 20 in totals:
            result = (2, '20点')
        elif 19 in totals:
            result = (1, '19点')
        else:
            result = (None, '未中')
        self._credit_side_bet((seat, 'Hot 21'), *result)

        # V19: if Crazy 7 was already known to lose from target card 0, its
        # collection was intentionally deferred until this same post-deal stage
        # where the other resolved losing side bets are collected.
        if self.side_bet_results.get((seat, 'Crazy 7')) == '输':
            self._collect_losing_side_bet_upward((seat, 'Crazy 7'))

        self.save_balance()

    def generate_special_offer(self):
        self.special_cards, self.special_multiplier = MultiplyRules.generate_offer()
        self._special_offer_render_state = None
        self.draw_special_offer()
        return self.special_cards, self.special_multiplier

    def _play_special_offer_animation(self, on_complete):
        """Animate the preview without changing this round's sampled result."""
        self._special_offer_running = True
        all_cards = [(suit, rank) for suit in BlackjackEngine.SUITS for rank in BlackjackEngine.RANKS]
        multipliers = tuple(multiplier for _threshold, multiplier in MultiplyRules.MULTIPLIER_TIERS)
        count = len(self.special_cards)
        steps, frame_ms = 10, 90
        def frame(index=0):
            if index == steps:
                self._special_offer_preview = None
                self._special_offer_running = False
                self.draw_special_offer()
                self.update_display()
                if callable(on_complete):
                    on_complete()
                return
            self._special_offer_preview = (random.sample(all_cards, count), random.choice(multipliers))
            self.draw_special_offer()
            self._queue(frame_ms, frame, index + 1)
        frame()

    def get_special_match_count(self, cards=None):
        if cards is None:
            cards = [card for hand in self.hands for card in hand['cards']]
        return MultiplyRules.match_count(cards, self.special_cards)

    def apply_special_card_multiplier(self, base_return, cards=None, stake=None):
        hand = self.active_hand() or (self.hands[0] if self.hands else None)
        if cards is None:
            cards = hand['cards'] if hand else []
        if stake is None:
            hand = next((h for h in self.hands if h["cards"] == list(cards)), hand)
            stake = self.hand_stake(hand) if hand else 0.0
        return MultiplyRules.apply_multiplier(base_return, cards, self.special_cards,
            self.special_multiplier, stake=stake)

    def _special_card_photo(self, card):
        if Image is None or ImageTk is None:
            return None
        if card not in self.special_card_photos:
            base = self.external_golden_card_pil.get(card)
            if base is None:
                base = self._oriented_card_pil(card, golden=True)
            size = (50, 70)
            resample = getattr(Image, 'Resampling', Image).LANCZOS
            self.special_card_photos[card] = ImageTk.PhotoImage(base.resize(size, resample), master=self)
        return self.special_card_photos[card]

    def draw_special_offer(self):
        """Five reserved slots fit beside, rather than over, the dealer area."""
        preview = self._special_offer_preview
        shown_cards, multiplier = preview if preview is not None else (self.special_cards, self.special_multiplier)
        cards = tuple(shown_cards[:MultiplyRules.MAX_SPECIAL_CARDS])
        hand_cards = tuple(card for hand in self.hands for card in hand['cards']) if not self._special_offer_running else ()
        matches = self.get_special_match_count(hand_cards)
        state = (cards, multiplier, hand_cards)
        if state == self._special_offer_render_state:
            return
        self._special_offer_render_state = state
        c, tag = self.canvas, 'special_offer'
        c.delete(tag)
        c.create_rectangle(809, 44, 1128, 197, fill=self.PANEL, outline=self.GOLD, tags=tag)
        c.create_rectangle(809, 44, 1128, 72, fill='#40634B', outline=self.GOLD, tags=tag)
        c.create_text(968.5, 58, text='加倍牌与赔率', font=(self.cn_font, 12, 'bold'),
            fill='#F2E6C9', tags=tag)
        c.create_text(968.5, 85, text=f'X{multiplier:g}' if cards else 'X?',
            font=(self.cn_font, 12, 'bold'), fill=self.GOLD, tags=tag)
        for index in range(MultiplyRules.MAX_SPECIAL_CARDS):
            x, y = 825 + index * 59, 100
            card = cards[index] if index < len(cards) else None
            matched = card is not None and card in hand_cards
            outline = '#FFDF69' if matched else '#6C7850'
            c.create_rectangle(x-2, y-2, x+52, y+72, outline=outline,
                width=3 if matched else 1, fill='#163228', tags=tag)
            if card is None:
                c.create_text(x+25, y+35, text='?', font=('Arial', 18, 'bold'),
                    fill='#879879' if not cards else '#40634B', tags=tag)
                continue
            photo = self._special_card_photo(card)
            card_tags = (tag, 'special_offer_card', 'golden_card')
            if photo is not None:
                c.create_image(x, y, image=photo, anchor='nw', tags=card_tags)
            else:
                suit, rank = card
                glyph = {'Club': '♣', 'Diamond': '♦', 'Heart': '♥', 'Spade': '♠'}[suit]
                c.create_rectangle(x, y, x+50, y+70, fill='#ffedaa', outline='#d5a52d', tags=card_tags)
                c.create_text(x+25, y+35, text=f'{rank}\n{glyph}', font=('Arial', 14, 'bold'),
                    fill='#c22631' if suit in ('Heart', 'Diamond') else '#111111', tags=card_tags)
        coefficient = self.special_multiplier * matches if matches else 1
        detail = f'匹配 {matches} 张 · 净赢 ×{coefficient:g}' if hand_cards else '每局2–5张 · 同花色同点数匹配'
        if len(self.hands) > 1 and hand_cards:
            detail = f'共匹配 {matches} 张 · 各手独立结算'
        c.create_text(968.5, 185, text=detail, font=(self.cn_font, 10),
            fill='#FFDF69' if matches else '#F2E6C9', tags=tag)

    def _make_dealer_push_notice(self):
        """Create Cari's transparent dealer-area overlay with the PUSH wording."""
        x, y = 575, 145
        if all(module is not None for module in (Image, ImageTk, ImageDraw, ImageFont)):
            scale, width, height = 3, 310, 48
            layer = Image.new('RGBA', (width * scale, height * scale), (0, 0, 0, 0))
            draw = ImageDraw.Draw(layer)
            draw.rounded_rectangle(
                (1, 1, width * scale - 2, height * scale - 2), radius=10 * scale,
                fill=(45, 12, 16, 238), outline=(185, 220, 255, 255), width=2 * scale)
            candidates = ['msyhbd.ttc', 'msyh.ttc', 'simhei.ttf', 'Arial Unicode.ttf',
                          '/System/Library/Fonts/PingFang.ttc',
                          '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
                          '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc']
            if sys.platform.startswith('linux'):
                import subprocess
                try:
                    result = subprocess.run(
                        ['fc-list', '-f', '%{file}\n', ':lang=zh'],
                        capture_output=True, text=True, timeout=1, check=False)
                    if result.returncode == 0:
                        candidates[:0] = [path.strip() for path in result.stdout.splitlines()
                                          if path.strip()]
                except (OSError, subprocess.TimeoutExpired):
                    pass
            font = None
            for path in candidates:
                try:
                    font = ImageFont.truetype(path, 22 * scale)
                    break
                except OSError:
                    continue
            if font is not None:
                wording = '庄家3张牌爆牌，平局'
                box = draw.textbbox((0, 0), wording, font=font)
                draw.text(((width * scale - (box[2] - box[0])) / 2 - box[0],
                           (height * scale - (box[3] - box[1])) / 2 - box[1]),
                          wording, font=font, fill=self.PUSH_BLUE)
            self._dealer_notice_source = layer.resize(
                (width, height), getattr(Image, 'Resampling', Image).LANCZOS)
            self._dealer_notice_image_item = self.canvas.create_image(
                x, y, state='hidden', tags='dealer_push_notice')
        else:
            font = None
        if font is None:
            # Match Cari's native Tk font fallback when Pillow has no CJK font.
            self._dealer_notice_text_item = self.canvas.create_text(
                x, y, text='庄家3张牌爆牌，平局', font=(self.cn_font, 16, 'bold'),
                fill=self.PUSH_BLUE, state='hidden', tags='dealer_push_notice')

    def _draw_dealer_push_notice(self):
        alpha = self._dealer_notice_level
        if alpha <= 0.0:
            self.canvas.itemconfigure('dealer_push_notice', state='hidden')
            return
        if self._dealer_notice_source is not None:
            layer = self._dealer_notice_source.copy()
            layer.putalpha(self._dealer_notice_source.getchannel('A').point(
                lambda value: round(value * alpha)))
            self._dealer_notice_photo = ImageTk.PhotoImage(layer, master=self)
            self.canvas.itemconfigure(self._dealer_notice_image_item,
                                      image=self._dealer_notice_photo, state='normal')
        if self._dealer_notice_text_item is not None:
            background, foreground = (75, 30, 34), (185, 220, 255)
            color = '#' + ''.join(f'{round(a + (b - a) * alpha):02x}'
                                  for a, b in zip(background, foreground))
            self.canvas.itemconfigure(self._dealer_notice_text_item, fill=color, state='normal')
        self.canvas.tag_raise('dealer_push_notice')

    def _fade_dealer_push_notice(self, visible):
        """Fade in at settlement and out after the return, using Cari's 300 ms timing."""
        if self._closing:
            return
        target = 1.0 if visible else 0.0
        if (self._dealer_notice_target == visible
                and (self._dealer_notice_job is not None or self._dealer_notice_level == target)):
            return
        if self._dealer_notice_job is not None:
            try:
                self.after_cancel(self._dealer_notice_job)
            except tk.TclError:
                pass
            if self._dealer_notice_job in self.after_ids:
                self.after_ids.remove(self._dealer_notice_job)
            self._dealer_notice_job = None
        self._dealer_notice_target = bool(visible)
        if self._dealer_notice_image_item is None and self._dealer_notice_text_item is None:
            if not visible:
                return
            self._make_dealer_push_notice()
        start = self._dealer_notice_level
        def step(frame):
            self._dealer_notice_job = None
            self._dealer_notice_level = start + (target - start) * frame / 12
            self._draw_dealer_push_notice()
            if frame < 12:
                self._dealer_notice_job = self._queue(25, step, frame + 1)
        step(0)


    def _settle_main_round(self, dealer_bj=False):
        # Payout methods can be reached by timers; never credit a round twice.
        if not self.round_active or self.settlement_running:
            return
        self.dealer_three_card_main_push = False
        self._maybe_settle_crazy7()
        self._settle_dealer_bust_side_bets()
        if self.insurance_bet > 0 and not self.insurance_resolved:
            credit = self.insurance_bet * (1.0 + self.INSURANCE_PROFIT) if dealer_bj else 0.0
            self.balance += credit
            self.insurance_return_amount = credit
            self.insurance_result = f'保险返还 {self.format_money(credit)}'
            self.insurance_resolved = True
        for index, hand in enumerate(self.hands):
            if hand.get('settlement') is not None:
                continue
            stake = self.hand_stake(hand)
            result = MultiplyRules.settle_main(hand['cards'], self.dealer_cards,
                stake, self.special_cards, self.special_multiplier,
                from_split=hand.get('from_split', False))
            if (result['settlement'] == 'push' and len(self.dealer_cards) == 3
                    and BlackjackEngine.hand_value(self.dealer_cards)[0] > 21):
                self.dealer_three_card_main_push = True
            returned = result['final_return']
            self.balance += returned
            hand.update(settlement=result['settlement'],
                base_settlement=result['settlement'],
                double_settlement=result['settlement'] if hand['double_added'] else None,
                settlement_return=returned, multiplier=result['coefficient'],
                special_match_count=result['match_count'], result=result['label'])
            self.last_result_lines.append(f'{result["label"]}：返还 {self.format_money(returned)}')
        self._finish_round(dealer_bj=dealer_bj)

# Compatibility wrapper similar to BaccaratGame.
class BlackjackGame(BubbleBlackjackGame):
    def __init__(self, root, username=None, initial_balance=10000,
                 on_back=None, on_balance_change=None, close_returns_to_parent=False):
        super().__init__(
            parent=root,
            balance=initial_balance,
            user=username,
            on_back=on_back,
            on_balance_change=on_balance_change,
            close_returns_to_parent=close_returns_to_parent,
        )
        self.pack(fill=tk.BOTH, expand=True)

class BlackjackGUI(tk.Tk):
    def __init__(self, initial_balance=10000, username='Guest'):
        super().__init__()
        self.title('加倍黑杰克')
        self.balance = float(initial_balance)
        def balance_changed(value):
            self.balance = float(value)
        def closed(value):
            self.balance = float(value)
            self.destroy()
        self.game = BubbleBlackjackGame(self, balance=initial_balance, user=username,
            on_back=closed, on_balance_change=balance_changed)
        self.game.pack(fill=tk.BOTH, expand=True)
        self.protocol('WM_DELETE_WINDOW', self.game.exit_game)

def main(parent=None, balance=10000, user=None, on_back=None,
         on_balance_change=None, username=None, close_returns_to_parent=False, initial_balance=None):
    if initial_balance is not None:
        balance = initial_balance
    if username is not None and user is None:
        user = username

    # Legacy positional compatibility: main(balance, username).
    if parent is not None and not isinstance(parent, tk.Misc):
        legacy_balance = parent
        legacy_user = balance if isinstance(balance, str) and user is None else user
        parent = None
        balance = legacy_balance
        user = legacy_user

    if user is None:
        user = 'Guest'

    # V24 embedded mode: casino_games.py owns the one and only Tk root and calls
    # master.replace_page(game_page).  casino_games installs WM_DELETE_WINDOW only
    # AFTER that replacement is complete, because the host may reset the protocol
    # during replace_page(). Blackjack never destroys/withdraws/iconifies the root.
    if parent is not None:
        game = BubbleBlackjackGame(
            parent=parent,
            balance=balance,
            user=user,
            on_back=on_back,
            on_balance_change=on_balance_change,
            close_returns_to_parent=close_returns_to_parent,
        )
        # Do NOT install WM_DELETE_WINDOW here.  At this point casino_games has not
        # called replace_page(game) yet, and the host may overwrite the protocol.
        return game

    # Standalone mode is kept for direct execution/testing only.
    root = tk.Tk()
    root.title('加倍黑杰克')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)

    def close_standalone(final_balance):
        if callable(on_back):
            try:
                on_back(final_balance)
            except Exception:
                pass
        try:
            root.destroy()
        except tk.TclError:
            pass

    game = BubbleBlackjackGame(
        parent=root,
        balance=balance,
        user=user,
        on_back=close_standalone,
        on_balance_change=on_balance_change,
    )
    game.pack(fill=tk.BOTH, expand=True)
    root.protocol('WM_DELETE_WINDOW', game.exit_game)
    root.mainloop()
    return game.final_balance

if __name__ == '__main__':
    final_balance = main()
    print(f"Final balance: ${final_balance:.2f}")
