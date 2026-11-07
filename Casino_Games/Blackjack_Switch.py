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

# Blackjack Switch — two synchronized main wagers, one switch, H17 / push 22.
# Keep this file beside the original game so Account, CSM and card assets resolve.
# Perfect Pair / 21+3 settle before insurance and the dealer Blackjack peek.
# A dealer 22 pushes only live hands; original naturals win 1:1.
# Bust! retains the original pay table, including dealer totals of 22.
import json
import math
import os
import random
import sys
import tkinter as tk
from functools import lru_cache
from tkinter import messagebox
from tkinter import font as tkfont

# Project layout:
#   A_Tools/Card/CSM_Shuffler.py
#   A_Tools/Casino_Games/Blackjack_Switch.py
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

BLACKJACK_VERSION = "V8-CSM-SWITCH-SKIP-EQUAL-SECOND-CARDS"

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
# CSM-backed Blackjack Switch shoe / hand helpers
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
    MAX_SPLIT_ACTIONS = 1       # per original family; no resplitting
    MAX_HANDS = 2              # per family; two families allow four hands total
    SEATS = ('Player1', 'Player2')
    SEAT_NAMES = {'Player1': '左手', 'Player2': '右手'}
    RIGHT_PLAY_OFFSET_X = 20.0
    SEAT_BOUNDS = {'Player1': (22.0, 574.0), 'Player2': (576.0, 1128.0)}
    ZONE_COLORS = {'Player1': '#35634B', 'Player2': '#305E4D'}
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    SIDE_BET_DIAMETER = 122.0 * 2 / 3
    # Shared geometry keeps static wagers, split hands and flying chips aligned.
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
    BLACKJACK_PROFIT = 1.0      # 1:1
    INSURANCE_PROFIT = 2.0      # 2:1
    SPLIT_ACES_ONE_CARD_ONLY = True
    HAND_SIDE_BET_KEYS = ('Perfect Pair', '21+3')
    SIDE_BET_KEYS = HAND_SIDE_BET_KEYS + ('Dealer 22', 'Bust!')
    SHARED_BUST_KEY = ('Table', 'Bust!')
    SHARED_DEALER_22_KEY = ('Table', 'Dealer 22')
    SIDE_BET_LABELS = {
        'Perfect Pair': '完美对子',
        '21+3': '21+3',
        'Dealer 22': '22点',
        'Bust!': '爆牌！',
    }
    SIDE_BET_ODDS_TEXT = {
        'Perfect Pair': '25/12/6:1',
        '21+3': '100/40/30/10/5:1',
        'Dealer 22': '50/20/8:1',
        'Bust!': '250/100/50/9/2/1:1',
    }

    M_CHIP_COLOR = '#102d47'


    CHIP_SPECS = [
        (100, '#202020', '100'),
        (500, '#FF7DDA', '500'),
        (1000, '#ab0058', '1K'),
        (5000, '#ba3438', '5K'),
        (10000, '#70439a', '10K'),
        (50000, '#FFD166', '50K'),  # amber stays distinct from the green felt
        (250000, '#ffffff', '250K'),
    ]

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
        # Numeric labels use a compact Latin face; tall CJK line metrics should
        # not force an otherwise short amount to become unnecessarily small.
        self.chip_font = next((name for name in ('Arial', 'Liberation Sans', 'DejaVu Sans')
                               if name in families), 'Arial')
        self._chip_fonts = {}

        # One stable local game identity is used so an orderly restart can
        # recover any chamber lease left by the previous instance.
        import uuid
        self.csm_game_id = f"SwitchBlackjack:{self.username or 'local'}:{uuid.uuid4().hex}"
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
        self.ace_decision_mode = None  # None / 'insurance'
        self.bet_layout_mode = 'home'
        self.previous_round_cards_present = False
        self.hands = []
        self.active_hand_index = 0
        self.dealer_cards = []
        self.dealer_hole_hidden = False
        self.dealer_blackjack_checked = False
        self.switch_pending = self.switch_used = False
        self._round_result_committed = False
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
        self.settlement_visual_stage = None
        self.pending_profit_chips = set()
        self._opening_wager_animation = False
        self.settlement_flash_step = 0
        self.flash_mode = None
        self.flash_winning_side_bets = set()
        self.flash_main_bet = False
        self.flash_main_push_only = False
        # Same dealer-area fade used by the supplied Free Double game.
        self.dealer_22_main_push = False
        self._dealer_notice_source = None
        self._dealer_notice_photo = None
        self._dealer_notice_image_item = None
        self._dealer_notice_text_item = None
        self._dealer_notice_level = 0.0
        self._dealer_notice_target = False
        self._dealer_notice_job = None
        # V6: main-game settlement is tracked per player hand instead of one
        # global MAIN spot. This lets a losing split hand disappear while other
        # winning split hands keep their own base/double chips and flash.
        self.flash_winning_hand_indices = set()
        self.hand_zone_bounds = []
        # V7: exact positions of each split-hand wager inside the Evoplay MAIN oval.
        # Used both for drawing the 1–5 base chips / Double chip and settlement flash.
        self.main_wager_positions = {}
        self.bet_chip_animation_count = 0
        self.pending_bet_animation = {
            **{(seat, 'MAIN'): 0.0 for seat in self.SEATS}, **self._empty_side_bets()}
        self._closing = False
        self.last_result_lines = []  # internal only; never shown to the player
        self.runtime_data_file = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..',
                'A_Logs',
                'Json',
                'Blackjack_Switch.json'
            )
        )
        self.shoe_resumed = False

        self.card_items = []
        self.temp_images = []
        self.external_card_images = {}
        self.external_card_pil = {}
        self.external_back_image = None
        self.external_back_pil = None
        self.card_asset_dir = None
        self._temp_flip_images = {}
        self._round_anim_item = None

        self.chip_selector_items = {}
        self.chip_selector_centers = {}
        self.action_buttons = {}
        self.decision_buttons = {}
        self.switch_buttons = {}
        self.control_buttons = {}
        self.bet_spots = {}
        self.side_bet_spots = {}
        self.after_ids = []

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


    def _make_fallback_card_pil(self, card, face_up=True):
        image = Image.new('RGBA', (100, 140), '#f4efe4' if face_up else '#253e66')
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((2, 2, 97, 137), radius=8,
                               outline='#d7cbb9' if face_up else '#d7c46a', width=3)
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

    def draw_history_panel(self):
        """Blackjack deliberately has no history/rules panel."""
        return

    def draw_animation_panel(self):
        c = self.canvas
        self.animation_panel = (22, 44, 1128, 617)
        c.create_text(575, 18, text='换牌黑杰克  BLACKJACK SWITCH',
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
        self.insurance_positions = {'Player1': (72.0, 224.0), 'Player2': (1078.0, 224.0)}
        self.dealer_total_text = c.create_text(575, 193, text='', state='hidden')
        self.rule_strip_bounds = (22.0, 200.0, 1128.0, 248.0)
        self.rule_strip_rect = c.create_rectangle(*self.rule_strip_bounds,
            fill='#173C2E', outline='#65784B', tags='round_rule_strip')
        c.create_line(25, 201, 1125, 201, fill='#E0C879', width=2, tags='round_rule_strip')
        c.create_line(25, 247, 1125, 247, fill='#0C241B', width=2, tags='round_rule_strip')
        self.rule_strip_text = c.create_text(575, 224,
            text='软17要牌 · 硬17停牌   黑杰克1:1   庄家22未爆牌主注平局   每边分牌1次',
            font=(self.cn_font, 15, 'bold'), fill=self.GOLD, tags='rule_strip_text')
        self.rule_strip_left_text = c.create_text(545, 224, text='', state='hidden')
        self.rule_strip_right_text = c.create_text(605, 224, text='', state='hidden')
        self.rule_strip_chip_pos = (575, 224)  # legacy helper compatibility
        self.shoe_origin = (575, 52)  # identical to Caribbean Stud's deal origin


    def draw_board(self):
        c = self.canvas
        self.bet_spots, self.side_bet_spots = {}, {}
        positions = {
            'Player1': {'Perfect Pair': 100, 'MAIN': 245, '21+3': 370},
            'Table': {'Dealer 22': 575, 'Bust!': 575},
            'Player2': {'Perfect Pair': 780, 'MAIN': 905, '21+3': 1040},
        }
        for seat, layout in positions.items():
            for index, (kind, x) in enumerate(layout.items()):
                key, tag = (seat, kind), f'bet_{seat}_{index}'
                bounds, label_pos, chip_pos = self._bet_surface_layout(x, main=kind == 'MAIN')
                chip_radius = self.WAGER_CHIP_RADIUS
                profit_pos = None
                if kind == 'Dealer 22':
                    # Reuse the Bust! dimensions and chip size, translated upward.
                    offset_y = -120.0
                    bounds = tuple(value+offset_y if index % 2 else value
                                   for index, value in enumerate(bounds))
                    label_pos = (label_pos[0], label_pos[1]+offset_y)
                    chip_pos = (chip_pos[0], chip_pos[1]+offset_y)
                fill = '#175C98' if kind == 'MAIN' else '#173B32'
                outline = '#19345D' if kind == 'MAIN' else self.GOLD
                shape = self._draw_bet_surface(bounds, fill, outline, tag, main=kind == 'MAIN')
                label = None
                if kind != 'MAIN':
                    label = c.create_text(*label_pos, text=self.SIDE_BET_LABELS[kind],
                        font=(self.cn_font, -14, 'bold'), fill='#F2E6C9',
                        tags=(tag, 'betting_spot_label'))
                spot = dict(key=key, bounds=bounds, label_pos=label_pos, chip_pos=chip_pos,
                    chip_radius=chip_radius, profit_pos=profit_pos,
                    rect=shape, label=label, tag=tag,
                    shape='oval' if kind == 'MAIN' else 'rounded_rect', normal_fill=fill,
                    normal_outline=outline, normal_width=0 if kind == 'MAIN' else 2)
                self.bet_spots[key] = spot
                if kind == 'MAIN':
                    self._decorate_main_bet_surface(spot)
                else:
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
                 ('surrender', '兑现金额\n$0.00', self.instant_surrender, '#9B403A'))
        for seat, (x0, x1) in self.SEAT_BOUNDS.items():
            for index, (action, label, command, color) in enumerate(specs):
                left = 278+index*174
                self.action_buttons[(seat, action)] = self._create_canvas_button(
                    left, 638, left+164, 720, label,
                    lambda s=seat, cmd=command: self._invoke_seat_action(s, cmd), color,
                    tag=f'action_{seat}_{action}', font_size=12,
                    direction='left' if seat == self.SEATS[0] else 'right')
            for action, left, right, label, accept in (
                    ('accept', 405, 565, '购买两边保险', True),
                    ('decline', 585, 745, '不购买保险', False)):
                self.decision_buttons[(seat, action)] = self._create_canvas_button(
                    left, 642, right, 716, label, lambda a=accept: self._resolve_ace_decision(a),
                    '#A57A36' if accept else '#173f66', tag=f'decision_{seat}_{action}',
                    font_size=11, direction='both')
        for action, left, right, label, command in (
                ('swap', 395, 625, '交换第二张牌', self.switch_cards),
                ('keep', 650, 880, '保留原牌', self.keep_cards)):
            self.switch_buttons[action] = self._create_canvas_button(
                left, 642, right, 716, label, command, '#635182' if action == 'swap' else '#397A48',
                tag=f'switch_{action}', font_size=14, direction='both')
        self._set_round_control_visibility(False)


    def _create_canvas_button(self, x0, y0, x1, y1, text, command, color,
                              fg='white', tag=None, font_size=12, direction=None):
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
                      pressed=False, text_y=y, bounds=(x0, y0, x1, y1),
                      direction=direction, pattern_items=[])
        if direction is not None:
            self._draw_button_chevrons(button)
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
                self._color_button_chevrons(button, self._shade_color(color, 1.12))
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
                self._color_button_chevrons(button, self._shade_color(color, .72))
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

    @staticmethod
    def _blend_color(background, foreground, amount):
        amount = max(0.0, min(1.0, float(amount)))
        return '#' + ''.join(f'{round(int(background[i:i+2], 16)*(1-amount) + int(foreground[i:i+2], 16)*amount):02x}'
                             for i in (1, 3, 5))

    def _draw_button_chevrons(self, button):
        """Parallel, lighter chevrons stay inside the button's inner face."""
        x0, y0, x1, y1 = button['bounds']
        left, top, right, bottom = x0+11, y0+12, x1-11, y1-12
        middle = (top+bottom)/2
        direction = button['direction']
        regions = [(left, right, direction)] if direction != 'both' else [
            (left, (left+right)/2-4, 'left'), ((left+right)/2+4, right, 'right')]
        for start, end, side in regions:
            depth = min(22.0, max(8.0, (end-start)/3))
            spacing = 24.0
            tip = start if side == 'left' else start+depth
            while tip+(depth if side == 'left' else 0) <= end:
                back = tip+depth if side == 'left' else tip-depth
                item = self.canvas.create_line(back, top, tip, middle, back, bottom,
                    fill=self._blend_color(button['color'], '#ffffff', .20), width=5,
                    capstyle=tk.BUTT, joinstyle=tk.MITER,
                    tags=(button['tag'], 'ui_button', 'decision_chevron', f"{button['tag']}_pattern"))
                button['pattern_items'].append(item)
                tip += spacing
        # Pattern lines share the button tag, so hide/show and hit testing are unchanged.
        self.canvas.tag_raise(button['highlight'])
        self.canvas.tag_raise(button['text'])

    def _color_button_chevrons(self, button, face_color):
        amount = .20 if button['enabled'] else .10
        color = self._blend_color(face_color, '#ffffff', amount)
        for item in button.get('pattern_items', ()):
            self.canvas.itemconfigure(item, fill=color)


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
        self._color_button_chevrons(button, color if enabled else '#4a4743')


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
        in_round = bool(in_round or (self.animation_running and not self.accept_bets))
        decision = bool(in_round and self.ace_decision_mode)
        switching = bool(in_round and self.switch_pending and not decision)
        hand = self.active_hand()
        active_seat = hand['seat'] if hand else self.SEATS[0]
        self.canvas.itemconfigure('chip_selector', state='hidden' if in_round else 'normal')
        for button in (self.clear_button, self.repeat_button, self.deal_button, self.info_button):
            self._button_state(button, not in_round)
        for (seat, _action), button in self.action_buttons.items():
            self._button_state(button, in_round and not decision and not switching and seat == active_seat)
        for (seat, _action), button in self.decision_buttons.items():
            self._button_state(button, decision and seat == self.SEATS[0])
        for button in self.switch_buttons.values():
            self._button_state(button, switching)
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
                info['bet'],returned,self.insurance_positions[seat],
                self.INSURANCE_CHIP_RADIUS,('insurance_chip',)))


    def _animate_insurance_chip_to_rule(self, seat, on_complete=None):
        amount = self.seat_insurance[seat]['bet']
        sx, sy = self._selected_chip_origin()
        self._animate_settlement_chips([(sx, sy, amount, self.INSURANCE_CHIP_RADIUS)],
            self.insurance_positions[seat], 220, f'insurance_chip_fly_{seat}', on_complete)


    def _show_ace_decision(self, mode):
        self.ace_decision_mode = mode
        self._set_round_control_visibility(True)


    def _resolve_ace_decision(self, accept):
        if (self.ace_decision_mode != 'insurance' or not self.round_active
                or self.animation_running or self.settlement_running):
            return
        if accept:
            amounts = {seat: self.round_original_bets[seat]/2.0 for seat in self.SEATS}
            cost = sum(amounts.values())
            if self.balance + 1e-9 < cost:
                return
            # Reserve the full paired cost atomically before either chip flies.
            self.balance -= cost
            for seat, amount in amounts.items():
                self.seat_insurance[seat].update(bet=amount, visible=False)
            self.insurance_bet = cost
            self.animation_running = True
            self.save_balance()
            self.update_display()
            pending = [len(amounts)]
            def landed(seat):
                self.seat_insurance[seat]['visible'] = True
                self.insurance_chip_visible = True
                pending[0] -= 1
                if pending[0]:
                    self.render_cards()
                    return
                self.animation_running = False
                self.ace_decision_mode = self.ace_decision_seat = None
                self.render_cards()
                self._next_ace_decision()
            for seat in amounts:
                self._animate_insurance_chip_to_rule(seat, lambda s=seat: landed(s))
            return
        self.ace_decision_mode = self.ace_decision_seat = None
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
        """绘制渐变圆形主注区、开口圆环和中文弧形标签。"""
        c = self.canvas
        left, top, right, bottom = spot['bounds']
        cx, cy = (left + right) / 2, (top + bottom) / 2
        radius = (right - left) / 2

        spot['surface_tag'] = f"{spot['tag']}_surface"
        spot['title_tag'] = f"{spot['tag']}_title"
        c.addtag_withtag(spot['surface_tag'], spot['rect'])
        surface_tags = (spot['tag'], spot['surface_tag'], 'betting_spot')

        # 叠加小圆，形成蓝色到浅色的渐变
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
                fill=color, outline='', tags=surface_tags
            )

        # 画260°圆环，在下方留出开口
        ring = []
        for step in range(65):
            degrees = self.MAIN_RING_START + self.MAIN_RING_EXTENT * step / 64
            theta = math.radians(degrees)
            ring.extend((
                cx + radius * math.cos(theta),
                cy + radius * math.sin(theta)
            ))

        for color, width in (('#A5BED4', 9), (spot['normal_outline'], 6)):
            c.create_line(
                *ring, fill=color, width=width,
                capstyle=tk.ROUND, tags=surface_tags
            )

        # 兼容使用座位编号和直接使用 MAIN 键的版本
        key = spot['key']
        if isinstance(key, tuple):
            seat = key[0]
        else:
            seats = getattr(self, 'SEATS', ('Player1',))
            seat = seats[0] if seats else 'Player1'

        seat_names = getattr(self, 'SEAT_NAMES', {})
        title = "玩家主注"

        for index, char in enumerate(title):
            degrees = 122.0 - index * 64.0 / max(1, len(title) - 1)
            theta = math.radians(degrees)
            c.create_text(
                cx + radius * math.cos(theta),
                cy + radius * math.sin(theta),
                text=char,
                angle=90.0-degrees,
                font=(self.cn_font, -14, 'bold'),
                fill='#F2E6C9',
                tags=(spot['tag'], spot['title_tag'], 'betting_spot_label')
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
        radius = spot.get('chip_radius', self.WAGER_CHIP_RADIUS)
        items = self._draw_baccarat_chip(
            sx, sy, amount, tags=('bet_chip_fly',), radius=radius, force_color=selected_color)
        self.canvas.tag_raise('bet_chip_fly')
        steps = 10
        frame_ms = 20

        def frame(step=1):
            ratio = min(1.0, step / float(steps))
            # ease-out keeps the casino-chip movement crisp while still visibly animated
            eased = 1.0 - (1.0 - ratio) ** 2
            cx = sx + (tx - sx) * eased
            cy = sy + (ty - sy) * eased
            self._position_chip_items(items, cx, cy, radius)
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
        radius = spot.get('chip_radius', self.WAGER_CHIP_RADIUS)
        items = self._draw_baccarat_chip(
            sx, sy, amount, tags=('bet_chip_fly',), radius=radius,
            force_color=self.bet_chip_color(amount))
        self.canvas.tag_raise('bet_chip_fly')
        steps = 10
        frame_ms = 20

        def frame(step=1):
            ratio = min(1.0, step / float(steps))
            eased = 1.0 - (1.0 - ratio) ** 2
            cx = sx + (tx - sx) * eased
            cy = sy + (ty - sy) * eased
            self._position_chip_items(items, cx, cy, radius)
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
            amount = 0.0 if self.round_active else self.current_bets[seat]
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
                    tags=('bet_chip_dynamic', spot['tag'], 'principal_chip'),
                    radius=spot.get('chip_radius', self.WAGER_CHIP_RADIUS))
            if self.round_active and key[1]!='MAIN':
                stake = self.round_side_bets.get(key,0.0)
                returned = self.side_bet_return_amounts.get(key,0.0)
                rows = self._outcome_chip_rows(('side',*key), stake, returned,
                    spot['chip_pos'], spot.get('chip_radius', self.WAGER_CHIP_RADIUS),
                    ('bet_chip_dynamic',spot['tag']), profit_position=spot.get('profit_pos'))
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
        if key[1] in ('Bust!', 'Dealer 22') or key in self.side_bet_early_collected:
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
                x,y=spot['chip_pos']; sources.append((x,y,stake,spot.get('chip_radius',self.WAGER_CHIP_RADIUS)))

        # Animate the base and Double components of each losing hand.
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


    def _make_dealer_22_notice(self):
        """Create Cari's transparent dealer-area overlay with the PUSH wording."""
        x, y = 575, 145
        if all(module is not None for module in (Image, ImageTk, ImageDraw, ImageFont)):
            scale, width, height = 3, 210, 48
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
                wording = '22点平局'
                box = draw.textbbox((0, 0), wording, font=font)
                draw.text(((width * scale - (box[2] - box[0])) / 2 - box[0],
                           (height * scale - (box[3] - box[1])) / 2 - box[1]),
                          wording, font=font, fill=self.PUSH_BLUE)
            self._dealer_notice_source = layer.resize(
                (width, height), getattr(Image, 'Resampling', Image).LANCZOS)
            self._dealer_notice_image_item = self.canvas.create_image(
                x, y, state='hidden', tags='dealer_22_notice')
        else:
            font = None
        if font is None:
            # Match Cari's native Tk font fallback when Pillow has no CJK font.
            self._dealer_notice_text_item = self.canvas.create_text(
                x, y, text='22点平局', font=(self.cn_font, 16, 'bold'),
                fill=self.PUSH_BLUE, state='hidden', tags='dealer_22_notice')

    def _draw_dealer_22_notice(self):
        alpha = self._dealer_notice_level
        if alpha <= 0.0:
            self.canvas.itemconfigure('dealer_22_notice', state='hidden')
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
        self.canvas.tag_raise('dealer_22_notice')

    def _fade_dealer_22_notice(self, visible):
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
            self._make_dealer_22_notice()
        start = self._dealer_notice_level
        def step(frame):
            self._dealer_notice_job = None
            self._dealer_notice_level = start + (target - start) * frame / 12
            self._draw_dealer_22_notice()
            if frame < 12:
                self._dealer_notice_job = self._queue(25, step, frame + 1)
        step(0)

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
                self._position_chip_items(items, cx, cy, r)
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


    # -------------------------------------------------------------- Blackjack_Switch.json
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
        # keeps no duplicate deck order in Blackjack_Switch.json.
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

    def _show_cut_dialog(self, second=False):
        """Baccarat-style physical packet cut animation."""
        dialog_w, dialog_h = 760, 410
        dialog = tk.Toplevel(self.winfo_toplevel())
        dialog.title('经典黑杰克 · 切牌')
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
        cv.create_text(380, 76, text='确认后会将两叠牌交换位置，再进入烧牌流程',
                       font=('微软雅黑', 10), fill='#b7d7cf', tags='cut_instruction')
        if second:
            cv.create_text(380, 96, text='新牌靴', font=('微软雅黑', 10),
                           fill='#e5dba4', tags='cut_instruction')

        shoe_x0, shoe_x1 = 86.0, 674.0
        shoe_y0, shoe_y1 = 132.0, 232.0
        deck_width = shoe_x1 - shoe_x0
        cv.create_rectangle(shoe_x0 - 14, shoe_y0 - 16, shoe_x1 + 16, shoe_y1 + 17,
                            fill='#2a211b', outline='#a48763', width=3, tags='shoe_frame')

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
        def value_to_x(value): return shoe_x0 + deck_width * value / 416.0
        def x_to_value(xx):
            value = int(round((xx - shoe_x0) / float(deck_width) * 416))
            return max(65, min(349, value))
        cut_tag = 'casino_cut_card'
        def draw_cut_card():
            cv.delete(cut_tag)
            xx = value_to_x(selected['value'])
            cv.create_rectangle(xx - 7, shoe_y0 - 31, xx + 7, shoe_y1 + 24,
                                fill='#f3df42', outline='#75620b', width=2, tags=cut_tag)
            cv.create_rectangle(xx - 4, shoe_y0 - 26, xx + 4, shoe_y0 - 6,
                                fill='#fff59d', outline='', tags=cut_tag)
            cv.tag_raise(cut_tag)
        def move_cut(event):
            if animating['value']: return 'break'
            selected['value'] = x_to_value(event.x)
            draw_cut_card()
        cv.bind('<Button-1>', move_cut); cv.bind('<B1-Motion>', move_cut)
        cv.tag_bind(cut_tag, '<B1-Motion>', move_cut); cv.tag_bind(cut_tag, '<Button-1>', move_cut)
        draw_cut_card()
        cv.create_text(380, 292, text='ENTER = 随机切牌',
                       font=('微软雅黑', 10, 'bold'), fill='#d9eee8', tags='cut_enter_hint')

        def draw_packet(tag, x0, y0, width, height, edge_count=36):
            width = max(18.0, float(width))
            cv.create_rectangle(x0, y0, x0+width, y0+height,
                                fill='#eee8dc', outline='#d0c5b2', width=2,
                                tags=(tag, 'cut_packet'))
            lines = max(8, min(edge_count, int(width / 5.0)))
            for i in range(1, lines):
                xx = x0 + width * i / lines
                cv.create_line(xx, y0+3, xx, y0+height-3,
                               fill='#c6baa7' if i % 2 else '#ddd3c3',
                               tags=(tag, 'cut_packet'))
            cv.create_rectangle(x0+5, y0+6, x0+width-5, y0+height-6,
                                outline='#b61f2e', width=2, tags=(tag, 'cut_packet'))
        def ease(t):
            t=max(0.0,min(1.0,float(t))); return t*t*(3.0-2.0*t)
        confirm_btn = None
        def finish_cut_animation():
            cv.delete('cut_packet'); cv.delete(cut_tag); cv.delete('cut_rail')
            draw_full_shoe(); cv.itemconfigure('cut_instruction', state='hidden')
            cv.create_text(380,292,text='准备烧牌…',font=('微软雅黑',11,'bold'),
                           fill='white',tags='cut_done')
            result[0]=int(selected['value']); dialog.after(260, dialog.destroy)
        def begin_cut_animation(value=None):
            nonlocal confirm_btn
            if animating['value']: return 'break'
            if value is not None:
                selected['value']=max(65,min(349,int(value))); draw_cut_card()
            animating['value']=True
            if confirm_btn is not None: confirm_btn.config(state=tk.DISABLED,text='切牌中…')
            cv.config(cursor='arrow'); cv.unbind('<Button-1>'); cv.unbind('<B1-Motion>')
            cv.delete('shoe_deck_static'); cv.delete('cut_enter_hint')
            cv.itemconfigure('cut_instruction', state='hidden')
            cv.create_text(380,55,text='正在切牌',font=('微软雅黑',18,'bold'),fill='white',tags='cut_anim_text')
            cv.create_text(380,82,text='分牌 → 调换 → 合并',font=('微软雅黑',10),fill='#b7d7cf',tags='cut_anim_text')
            split_x=value_to_x(selected['value']); left_w=max(18.0,split_x-shoe_x0)
            left_w=min(deck_width-18.0,left_w); right_w=deck_width-left_w
            tag_a,tag_b='cut_packet_A','cut_packet_B'
            draw_packet(tag_a,shoe_x0,shoe_y0,left_w,shoe_y1-shoe_y0)
            draw_packet(tag_b,shoe_x0+left_w,shoe_y0,right_w,shoe_y1-shoe_y0)
            cv.delete(cut_tag)
            start_a=[shoe_x0,shoe_y0]; start_b=[shoe_x0+left_w,shoe_y0]
            current_a=start_a[:]; current_b=start_b[:]
            lift_y=shoe_y0-72.0; final_b_x=shoe_x0; final_a_x=shoe_x0+right_w
            def move_tag_to(tag,current,tx,ty):
                cv.move(tag,tx-current[0],ty-current[1]); current[0],current[1]=tx,ty
            def phase1(step=0):
                t=ease(step/14); move_tag_to(tag_a,current_a,shoe_x0,shoe_y0+(lift_y-shoe_y0)*t); cv.tag_raise(tag_a)
                dialog.after(22,phase1,step+1) if step<14 else phase2(0)
            def phase2(step=0):
                t=ease(step/18)
                move_tag_to(tag_b,current_b,start_b[0]+(final_b_x-start_b[0])*t,shoe_y0)
                move_tag_to(tag_a,current_a,shoe_x0+(final_a_x-shoe_x0)*t,lift_y); cv.tag_raise(tag_a)
                dialog.after(22,phase2,step+1) if step<18 else phase3(0)
            def phase3(step=0):
                t=ease(step/14); move_tag_to(tag_a,current_a,final_a_x,lift_y+(shoe_y0-lift_y)*t); cv.tag_raise(tag_a)
                if step<14: dialog.after(22,phase3,step+1)
                else:
                    cv.create_line(final_a_x,shoe_y0+3,final_a_x,shoe_y1-3,fill='#9f927d',width=1,tags='cut_packet')
                    dialog.after(180,finish_cut_animation)
            phase1(0); return 'break'
        def confirm(): begin_cut_animation(selected['value'])
        def random_confirm(_event=None):
            if animating['value']: return 'break'
            selected['value']=rng.randint(65,349); draw_cut_card(); dialog.after(100,begin_cut_animation,selected['value']); return 'break'
        confirm_btn=tk.Button(dialog,text='确认切牌',command=confirm,width=18,
                              font=('微软雅黑',13,'bold'),bg='#d8bd4b',fg='#15110d',
                              activebackground='#ead56f',relief=tk.FLAT,bd=0,pady=8)
        confirm_btn.pack(pady=(4,12))
        dialog.bind('<Return>',random_confirm); dialog.bind('<KP_Enter>',random_confirm)
        dialog.after(20,dialog.focus_force); dialog.protocol('WM_DELETE_WINDOW',confirm)
        self.wait_window(dialog)
        return int(result[0] if result[0] is not None else selected['value'])

    def start_new_shoe_cut(self):
        """Legacy entry point retained for hosts; CSM needs no cut or burn."""
        if self._closing or self.round_active:
            return
        self.animation_running = False
        self.accept_bets = True
        self.update_display()

    def _face_photo(self, card):
        return self.external_card_images.get(tuple(card))

    def _create_scaled_flip_image(self, card, width, height, use_back=False):
        if Image is None or ImageTk is None:
            return self.external_back_image if use_back else self._face_photo(card)
        base = self.external_back_pil if use_back else self.external_card_pil.get(tuple(card))
        if base is None:
            return self.external_back_image if use_back else self._face_photo(card)
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        image = base.resize((max(1, int(width)), max(1, int(height))), resample)
        return ImageTk.PhotoImage(image, master=self)

    def _animate_card_from_shoe(self, card, target_x, target_y, on_complete=None,
                                flip=True, tag='round_animation_card', rotation=0):
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
            self._render_card(card,target_x,target_y,tags=(tag,'animation_card'),rotation=rotation)
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
                base = self._oriented_card_pil(card,rotation,use_back)
                resample = getattr(Image,'Resampling',Image).LANCZOS
                photo = ImageTk.PhotoImage(base.resize((fw,fh),resample),master=self)
                self._temp_flip_images[card_id] = photo
                self.canvas.itemconfigure(card_id,image=photo)
                self.canvas.coords(card_id,x,y)
            else:
                self.canvas.coords(card_id,x,y,x+fw,y+fh)
                self.canvas.itemconfigure(card_id,fill='#253e66' if use_back else '#f4efe4')
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


    def _start_initial_burn(self):
        if self.engine.remaining_cards() <= 0:
            self._finish_burn(); return
        face = self.engine.draw_card()
        self.save_runtime_store(burn_complete=False)
        burn_count = BlackjackEngine.burn_value(face)
        self.clear_card_display()

        # V20 burn layout:
        #   row 1: the single face-up burn-value card, centred;
        #   row 2: up to five burned backs, centred;
        #   row 3: the remaining up to five burned backs, centred.
        # Row 2 and row 3 are separated by one full card-height (140 px) of
        # empty space.  A ten-value burn therefore appears as a clean 5 + 5.
        card_w = 100.0
        card_h = 140.0
        gap_x = 15.0
        face_y = 40.0
        row2_y = 195.0
        row3_y = row2_y + card_h * 2.0  # 140px blank gap between the rows

        def row_x(position, row_count):
            total_w = row_count * card_w + max(0, row_count - 1) * gap_x
            start_x = (self.WIDTH - total_w) / 2.0
            return start_x + position * (card_w + gap_x)

        def face_arrived():
            def burn_rest(index=0):
                if index >= burn_count or self.engine.remaining_cards() <= 0:
                    self._queue(500, self._finish_burn); return
                self.engine.draw_card(); self.save_runtime_store(burn_complete=False)
                if index < 5:
                    row_count = min(5, burn_count)
                    position = index
                    ty = row2_y
                else:
                    row_count = max(0, min(5, burn_count - 5))
                    position = index - 5
                    ty = row3_y
                tx = row_x(position, row_count)
                self._animate_back_from_shoe(
                    tx, ty,
                    on_complete=lambda: self._queue(35, burn_rest, index + 1))
            self._queue(350, burn_rest, 0)

        face_x = (self.WIDTH - card_w) / 2.0
        self._animate_card_from_shoe(
            face, face_x, face_y, on_complete=face_arrived, flip=True, tag='burn_card')

    def _finish_burn(self):
        self.canvas.delete('burn_card')
        self.canvas.delete('animation_card')
        self.clear_card_display()
        self.animation_running = False
        self.accept_bets = True
        self.save_runtime_store(burn_complete=True)
        self.update_display()

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
            # Classic anchors the wager below the first card. The right starting
            # family moves above its Perfect Pair spot, as requested.
            center = (self._seat_play_origin(hand['seat'])[0] if geometry[index][4] == 1
                      else geometry[index][2])
            cx = self._wager_center_x(center, geometry[index])
            cy = self.MAIN_BET_Y-self.MAIN_WAGER_LIFT
            double = (cx+self.CHIP_PITCH,cy)
            result.append({'base': (cx,cy), 'double': double})
        return result



    def _component_return_amount(self, hand, component):
        amount = float(hand.get('base_bet' if component == 'base' else 'double_added', 0.0))
        state = hand.get('base_settlement' if component == 'base' else 'double_settlement')
        if state == 'win':
            return amount * 2.0
        if state in ('push', 'refund'):
            return amount
        if state == 'cashout':
            stake = self.hand_stake(hand)
            return float(hand.get('settlement_return', 0.0)) * amount / stake if stake else 0.0
        return 0.0

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
        if settlement == 'win':
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
        natural = not surrendered and self._is_natural_blackjack(hand)
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
        visible = self.dealer_cards[:1] if self.dealer_hole_hidden else self.dealer_cards
        card_x, card_y = self._dealer_card_target(len(self.dealer_cards) - 1)
        tip_x, y = card_x + self.CARD_WIDTH + 6, card_y + self.CARD_HEIGHT / 2
        box_left, box_right = tip_x + 10, tip_x + 62
        total, soft = BlackjackEngine.hand_value(visible)
        natural = not self.dealer_hole_hidden and BlackjackEngine.is_blackjack(visible)
        self.canvas.create_polygon(tip_x, y, box_left, y-18, box_right, y-18,
            box_right, y+18, box_left, y+18,
            fill='#000000' if natural else self._dealer_badge_fill(), outline='',
            tags=('hand_label', 'dealer_total_badge'))
        label = '22' if not self.dealer_hole_hidden and total == 22 else self._hand_total_badge_text(
            visible, blackjack=natural, soft_stand=soft and total >= 18)
        self.canvas.create_text((box_left+box_right)/2, y, text=label,
            font=(self.cn_font, 11, 'bold'), fill='#FFFFFF' if natural else '#111111',
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
                              tags=('dealt_card', 'dealer_dealt_card', f'dealer_card_{index}'),
                              face_up=not (index == 1 and self.dealer_hole_hidden))
        self._draw_dealer_total_badge()
        geometry = self._seat_hand_geometry()
        self.hand_zone_bounds = []
        for index, hand in enumerate(self.hands):
            left, right, cx, order, n = geometry[index]
            self.hand_zone_bounds.append((left, 282, right, 527))
            for j, card in enumerate(hand['cards']):
                self._render_card(card, *self._player_card_target(index, j),
                    tags=('dealt_card', 'player_dealt_card', f'player_card_{index}_{j}'),
                    rotation=90 if hand.get('double_card_index')==j else 0)
            self._draw_hand_total_badge(index, left, right)
        self._draw_main_hand_wagers()
        self._render_insurance_chip()
        self._raise_visible_bottom_controls(self.round_active)
        self._raise_wager_chips()
        self.canvas.tag_raise('dealer_22_notice')

    def _is_current_hand(self, index):
        return bool(self.round_active and self.dealer_blackjack_checked
            and not self.switch_pending and not self.ace_decision_mode
            and not self.dealer_phase_active and not self.settlement_running
            and index == self.active_hand_index and 0 <= index < len(self.hands)
            and self.hands[index]['status'] == 'active')

    def _render_card(self, card, x, y, tags=('dealt_card',), rotation=0, face_up=True):
        photo = self._oriented_card_photo(card, rotation, use_back=not face_up)
        if photo is not None:
            return self.canvas.create_image(x, y, image=photo, anchor='nw', tags=tags)
        width, height = self._card_dimensions(rotation)
        if not face_up:
            return self.canvas.create_rectangle(x, y, x+width, y+height,
                fill='#253e66', outline='#d7c46a', width=2, tags=tags)
        suit, rank = card
        fg = '#c22631' if suit in ('Diamond', 'Heart') else '#111111'
        symbol = {'Club': '♣', 'Diamond': '♦', 'Heart': '♥', 'Spade': '♠'}.get(suit, suit[:1])
        self.canvas.create_rectangle(x, y, x+width, y+height,
            fill='#f4efe4', outline='#d7cbb9', width=2, tags=tags)
        return self.canvas.create_text(x+width/2, y+height/2, text=f'{rank}\n{symbol}',
            font=('Arial', 18, 'bold'), fill=fg, justify='center', angle=(-rotation)%360, tags=tags)


    # --------------------------------------------------------------- round setup
    def handle_enter(self, _event=None):
        if not self.round_active:
            self.deal_cards()
        else:
            # Enter never chooses insurance or Switch or a hand action. It only
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
            'switched': False,
            'split_aces': bool(split_aces),
            'needs_split_draw': bool(needs_split_draw),
            'status': 'active',
            'result': '',
            'cashout_credit': 0.0,
            'cashout_visual_stage': None,
            # Base and Double remain separate for chip animations and cash-outs.
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
        if (not all(self.current_bets.values())
                or abs(self.current_bets[self.SEATS[0]]-self.current_bets[self.SEATS[1]]) > 1e-9):
            messagebox.showwarning('最低下注', '请在两边放置金额相同的主注。', parent=self.winfo_toplevel())
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
                for kind in self.HAND_SIDE_BET_KEYS:
                    key = (seat, kind)
                    self.balance += self.current_side_bets[key]
                    self.current_side_bets[key] = 0.0
        self.save_balance()
        self.accept_bets, self.animation_running = False, True
        self.update_display()
        if self.canvas.find_withtag('dealt_card'):
            self._animate_previous_round_cards_out(self._begin_round_after_bet_layout)
        else:
            self._begin_round_after_bet_layout()


    def _begin_round_after_bet_layout(self):
        self.round_active = True
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
        self.dealer_hole_hidden = self.dealer_blackjack_checked = False
        self.switch_pending = self.switch_used = False
        self._round_result_committed = False
        self.dealer_22_main_push = False
        self._fade_dealer_22_notice(False)
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
        # Dealer has an actual hole card before insurance, peek or Switch.
        sequence = list(range(len(self.hands)))+['D']+list(range(len(self.hands)))+['H']
        def step(index=0):
            if index == len(sequence):
                self.animation_running = False
                self._after_initial_deal()
                return
            callback = lambda: self._queue(80, step, index+1)
            if sequence[index] in ('D', 'H'):
                self._deal_dealer_card_animated(callback, face_down=sequence[index] == 'H')
            else:
                self._deal_player_card_animated(sequence[index], callback)
        self._animate_starting_wagers(step)


    def _after_initial_deal(self):
        # Immutable snapshots: neither Switch nor a later split can change these bets.
        self.round_initial_cards = {hand['seat']: tuple(hand['cards']) for hand in self.hands}
        for hand in self.hands:
            if self._is_natural_blackjack(hand):
                hand['status'] = 'blackjack'
        self.animation_running = True
        self._settle_initial_side_bets()
        self.render_cards()
        self.update_display()
        # Finish the side-bet chip payouts before offering insurance or peeking.
        self._queue(480, self._after_initial_side_bets)

    def _after_initial_side_bets(self):
        if not self.round_active or self._round_result_committed:
            return
        self.animation_running = False
        if self.dealer_cards[0][1] == 'A':
            self.ace_decision_queue = [('Both', 'insurance')]
        self._next_ace_decision()

    @staticmethod
    def _is_natural_blackjack(hand):
        return bool(not hand.get('from_split', False) and not hand.get('switched', False)
                    and BlackjackEngine.is_blackjack(hand.get('cards', ())))

    def _settle_insurance(self, dealer_bj):
        if self.insurance_resolved:
            return
        credit = 0.0
        for info in self.seat_insurance.values():
            info['returned'] = info['bet'] * (1.0 + self.INSURANCE_PROFIT) if dealer_bj else 0.0
            credit += info['returned']
        self.balance += credit
        self.insurance_return_amount = credit
        self.insurance_resolved = True
        if self.insurance_bet:
            self.insurance_result = (f'保险胜 +{self.format_money(credit-self.insurance_bet)}' if dealer_bj
                else f'保险输 -{self.format_money(self.insurance_bet)}')
        else:
            self.insurance_result = '未购买保险'
        self.save_balance()

    def _check_opening_dealer_blackjack(self):
        if (not self.round_active or self.dealer_blackjack_checked
                or self.ace_decision_mode or self.animation_running):
            return
        self.dealer_blackjack_checked = True
        up_rank = self.dealer_cards[0][1]
        if up_rank in ('A', '10', 'J', 'Q', 'K') and BlackjackEngine.is_blackjack(self.dealer_cards):
            self.animation_running = True
            self.dealer_phase_active = True
            self.update_display()
            self._reveal_dealer_hole(self._resolve_dealer_blackjack)
            return
        self._settle_insurance(False)
        if not self._switch_changes_points():
            # Keep the physical cards and natural-BJ eligibility unchanged.
            self._finish_switch_decision()
            return
        self.switch_pending = True
        self.active_hand_index = -1
        self.render_cards()
        self.update_display()

    def _switch_changes_points(self):
        if len(self.hands) != 2 or any(len(hand['cards']) != 2 for hand in self.hands):
            return False
        return (BlackjackEngine.split_value(self.hands[0]['cards'][1])
                != BlackjackEngine.split_value(self.hands[1]['cards'][1]))

    def can_switch(self):
        return bool(self.round_active and self.switch_pending and self.dealer_blackjack_checked
                    and not self.animation_running and not self.settlement_running
                    and not self.ace_decision_mode and len(self.hands) == 2
                    and all(len(hand['cards']) == 2 and not hand['from_split'] for hand in self.hands)
                    and self._switch_changes_points())

    def switch_cards(self):
        if not self.can_switch():
            return
        self.switch_pending = False
        self.switch_used = True
        self.animation_running = True
        starts = {f'player_card_{i}_1': self._player_card_target(i, 1) for i in range(2)}
        ends = {'player_card_0_1': starts['player_card_1_1'],
                'player_card_1_1': starts['player_card_0_1']}
        # Commit before animation; all subsequent natural-BJ checks use switched flags.
        self.hands[0]['cards'][1], self.hands[1]['cards'][1] = (
            self.hands[1]['cards'][1], self.hands[0]['cards'][1])
        for hand in self.hands:
            hand['switched'] = True
        self.canvas.delete('hand_label')
        self.update_display()
        self._animate_canvas_positions(starts, ends, duration_ms=380,
            arc_lifts={'player_card_0_1': 45, 'player_card_1_1': -45},
            on_complete=self._finish_switch_decision)

    def keep_cards(self):
        if self.can_switch():
            self.switch_pending = False
            self._finish_switch_decision()

    def _finish_switch_decision(self):
        self.switch_pending = False
        self.animation_running = False
        for hand in self.hands:
            total, _ = BlackjackEngine.hand_value(hand['cards'])
            hand['status'] = 'blackjack' if self._is_natural_blackjack(hand) else 'stood' if total == 21 else 'active'
            hand['result'] = '黑杰克' if hand['status'] == 'blackjack' else '21点' if total == 21 else ''
        self.active_hand_index = -1
        self.render_cards()
        self.update_display()
        self._advance_hand()

    def _reveal_dealer_hole(self, on_complete=None):
        if not self.dealer_hole_hidden or len(self.dealer_cards) < 2:
            if callable(on_complete):
                on_complete()
            return
        card = self.dealer_cards[1]
        x, y = self._dealer_card_target(1)
        width, height = self.CARD_WIDTH, self.CARD_HEIGHT
        self.canvas.delete('dealer_card_1')
        tag = 'dealer_hole_flip'
        item = self._render_card(card, x, y, tags=(tag, 'animation_card'), face_up=False)
        def frame(step=0):
            if step > 12:
                self.canvas.delete(tag)
                self._temp_flip_images.pop(item, None)
                self.dealer_hole_hidden = False
                self.render_cards()
                self.update_display()
                if callable(on_complete):
                    on_complete()
                return
            back = step <= 6
            ratio = 1-step/6 if back else (step-6)/6
            w = max(1, round(width*ratio))
            px = x + (width-w)/2
            if self.canvas.type(item) == 'image':
                base = self._oriented_card_pil(card, use_back=back)
                resample = getattr(Image, 'Resampling', Image).LANCZOS
                photo = ImageTk.PhotoImage(base.resize((w, height), resample), master=self)
                self._temp_flip_images[item] = photo
                self.canvas.itemconfigure(item, image=photo)
                self.canvas.coords(item, px, y)
            else:
                self.canvas.coords(item, px, y, px+w, y+height)
                self.canvas.itemconfigure(item, fill='#253e66' if back else '#f4efe4')
            self._queue(20, frame, step+1)
        frame()


    def _deal_player_card_animated(self, hand_index, on_complete=None):
        hand = self.hands[hand_index]
        card = self.draw_round_card()
        card_index = len(hand['cards'])
        hand['cards'].append(card)
        self.seat_deal_sequences[hand['seat']].append(card)
        tx, ty = self._player_card_target(hand_index, card_index)
        def done():
            self.canvas.delete('round_animation_card')
            self.render_cards()
            self.update_display()
            if callable(on_complete):
                on_complete()
        self._animate_card_from_shoe(card, tx, ty, on_complete=done, tag='round_animation_card',
            rotation=90 if hand.get('double_card_index')==card_index else 0)


    def _deal_dealer_card_animated(self, on_complete=None, face_down=False):
        card = self.draw_round_card()
        index = len(self.dealer_cards)
        self.dealer_cards.append(card)
        if face_down:
            self.dealer_hole_hidden = True
        for seat in self.SEATS:
            self.seat_deal_sequences[seat].append(card)
        tx, ty = self._dealer_card_target(index)
        def done():
            self.canvas.delete('round_animation_card')
            self.render_cards()
            self.update_display()
            if callable(on_complete):
                on_complete()
        self._animate_card_from_shoe(card, tx, ty, on_complete=done,
            tag='round_animation_card', flip=not face_down)


    def _prepare_active_split_hand(self, on_ready=None):
        hand = self.active_hand()
        if not hand or not hand.get('needs_split_draw', False):
            if callable(on_ready):
                on_ready()
            return
        hand['needs_split_draw'] = False
        self.animation_running = True
        self.update_display()
        def after_draw():
            total, _ = BlackjackEngine.hand_value(hand['cards'])
            if hand.get('split_aces', False):
                hand['status'], hand['result'] = 'stood', '分A一张停牌'
            elif total > 21:
                hand['status'], hand['result'] = 'bust', '爆牌'
            elif total == 21:
                hand['status'], hand['result'] = 'stood', '21点'
            self.animation_running = False
            self.render_cards()
            self.update_display()
            if hand['status'] != 'active':
                self._queue(180, self._advance_hand)
            elif callable(on_ready):
                on_ready()
        self._deal_player_card_animated(self.active_hand_index, on_complete=after_draw)

    def _can_play_hand(self, hand):
        return bool(self.round_active and self.dealer_blackjack_checked and not self.switch_pending
                    and not self.ace_decision_mode and not self.animation_running
                    and not self.settlement_running and hand is self.active_hand()
                    and hand and hand['status'] == 'active' and not hand['needs_split_draw'])

    def active_hand(self):
        if not self.round_active or not (0 <= self.active_hand_index < len(self.hands)):
            return None
        return self.hands[self.active_hand_index]

    def can_hit(self, hand):
        return self._can_play_hand(hand) and not hand.get('split_aces', False)

    def can_double(self, hand):
        return bool(self._can_play_hand(hand) and len(hand['cards']) == 2
            and not hand.get('split_aces', False) and self.balance + 1e-9 >= hand['base_bet'])

    def can_split(self, hand):
        if not self._can_play_hand(hand) or len(hand['cards']) != 2 or hand.get('from_split', False):
            return False
        seat = hand['seat']
        return bool(sum(h['seat'] == seat for h in self.hands) < self.MAX_HANDS
            and self.split_actions_by_seat[seat] < self.MAX_SPLIT_ACTIONS
            and self.balance + 1e-9 >= hand['base_bet']
            and BlackjackEngine.split_value(hand['cards'][0]) == BlackjackEngine.split_value(hand['cards'][1]))


    def can_surrender(self, hand):
        return bool(self._can_play_hand(hand) and hand['cards'] and not self._is_natural_blackjack(hand)
                    and BlackjackEngine.hand_value(hand['cards'])[0] <= 21)

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
        if not self._can_play_hand(hand):
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

    def _project_player_card_positions(self, hands_snapshot, count=None):
        geometry = self._seat_hand_geometry(hands_snapshot)
        return {(index, j): self._player_card_position(hand, geometry[index], j)
                for index, hand in enumerate(hands_snapshot) for j in range(len(hand['cards']))}


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
                    tags=('hand_wager','split_wager_animation',tag))
                start_tags[tag] = old_wagers[index][component]
                end_tags[tag] = new_wagers[target][component]
        new_tag = 'split_wager_new'
        start = self._selected_chip_origin()
        self._draw_baccarat_chip(*start, right['base_bet'],
            tags=('hand_wager','split_wager_animation',new_tag))
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



    @staticmethod
    @lru_cache(maxsize=None)
    def _infinite_dealer_distribution(total, soft):
        """H17 distribution: 17, 18, 19, 20, 21, 22 (push), >22 (bust)."""
        total, soft = int(total), bool(soft)
        if total > 21 or total >= 18 or (total == 17 and not soft):
            result = [0.0] * 7
            result[5 if total == 22 else 6 if total > 22 else total-17] = 1.0
            return tuple(result)
        outcomes = ((11, 1/13),) + tuple((v, 1/13) for v in range(2, 10)) + ((10, 4/13),)
        result = [0.0] * 7
        for value, prob in outcomes:
            raw, high = total+value, int(soft)+int(value == 11)
            while raw > 21 and high:
                raw -= 10
                high -= 1
            sub = BubbleBlackjackGame._infinite_dealer_distribution(raw, high > 0)
            for i, p in enumerate(sub):
                result[i] += prob*p
        return tuple(result)

    @staticmethod
    @lru_cache(maxsize=None)
    def _dealer_distribution_after_peek(up_total, up_soft):
        # Valuation uses the upcard only. Condition on the public no-Blackjack peek;
        # never use the actual hidden card or the live shoe for the cash-out quote.
        outcomes = ((11, 1/13),) + tuple((v, 1/13) for v in range(2, 10)) + ((10, 4/13),)
        allowed = [(value, prob) for value, prob in outcomes
            if not (up_total == 11 and value == 10) and not (up_total == 10 and value == 11)]
        mass = sum(prob for _, prob in allowed)
        result = [0.0] * 7
        for value, prob in allowed:
            raw, high = up_total+value, int(up_soft)+int(value == 11)
            while raw > 21 and high:
                raw -= 10
                high -= 1
            sub = BubbleBlackjackGame._infinite_dealer_distribution(raw, high > 0)
            for i, p in enumerate(sub):
                result[i] += prob*p/mass
        return tuple(result)

    @staticmethod
    def _upcard_state(card):
        rank=card[1]
        if rank=='A': return 11,True
        if rank in ('10','J','Q','K'): return 10,False
        return int(rank),False

    @staticmethod
    @lru_cache(maxsize=None)
    def _infinite_optimal_hit_stand(total, soft, dealer_total, dealer_soft):
        """Return (win, player bust, push) under the best Hit/Stand return."""
        if total > 21:
            return 0.0, 1.0, 0.0
        ddist = BubbleBlackjackGame._dealer_distribution_after_peek(dealer_total, dealer_soft)
        stand_win = ddist[6] + sum(ddist[:max(0, total-17)])
        stand_push = ddist[5] + (ddist[total-17] if 17 <= total <= 21 else 0.0)
        if total >= 21:
            return stand_win, 0.0, stand_push
        hit_win = hit_bust = hit_push = 0.0
        outcomes = ((11, 1/13),) + tuple((v, 1/13) for v in range(2, 10)) + ((10, 4/13),)
        for value, prob in outcomes:
            raw, high = total+value, int(soft)+int(value == 11)
            while raw > 21 and high:
                raw -= 10
                high -= 1
            win, bust, push = BubbleBlackjackGame._infinite_optimal_hit_stand(
                raw, high > 0, dealer_total, dealer_soft)
            hit_win += prob*win
            hit_bust += prob*bust
            hit_push += prob*push
        if 2*hit_win+hit_push > 2*stand_win+stand_push+1e-12:
            return hit_win, hit_bust, hit_push
        return stand_win, 0.0, stand_push

    def surrender_offer(self, hand):
        """Keep the original cash-out feature, using Switch H17/22/peek valuation."""
        if not self.can_surrender(hand) or not self.dealer_cards:
            return 0.0, 0.0, 1.0, 0.0
        total, soft = BlackjackEngine.hand_value(hand['cards'])
        dtotal, dsoft = self._upcard_state(self.dealer_cards[0])
        win, bust, push = self._infinite_optimal_hit_stand(total, soft, dtotal, dsoft)
        credit = round(self.hand_stake(hand)*(2*win+push)*self.CASHOUT_FACTOR, 2)
        return credit, win, bust, push


    def instant_surrender(self):
        hand = self.active_hand()
        if (not self.can_surrender(hand) or self.animation_running
                or self.settlement_running or self.ace_decision_mode):
            return
        hand_index = self.active_hand_index
        credit, win_prob, _bust_prob, _ = self.surrender_offer(hand)
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
            result=f'即时兑现 {self.format_money(credit)}', settlement='cashout',
            base_settlement='cashout',
            double_settlement='cashout' if hand['double_added'] > 0 else None,
            settlement_return=credit, cashout_visual_stage='paying')
        self.animation_running = True
        self.save_balance()
        self.last_result_lines.append(
            f'手{hand_index+1} 即时兑现：获胜概率 {win_prob:.2%}，兑现金额 {self.format_money(credit)}')
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




    def _settle_bust_side_bet(self):
        """The centered Bust! wager belongs to the table and settles once."""
        key = self.SHARED_BUST_KEY
        if key in self.side_bet_results:
            return
        total, _ = BlackjackEngine.hand_value(self.dealer_cards)
        if total <= 21:
            self._credit_side_bet(key, None, '庄家未爆')
        else:
            count = len(self.dealer_cards)
            odds = 250 if count >= 8 else {7: 100, 6: 50, 5: 9, 4: 2}.get(count, 1)
            self._credit_side_bet(key, odds, f'庄家{count}张爆牌')
        self.save_balance()

    def _settle_dealer_22_side_bet(self):
        """Use Free Double's all-card suit/colour tiers: 50, 20, or 8 to 1."""
        key = self.SHARED_DEALER_22_KEY
        if key in self.side_bet_results:
            return
        total, _ = BlackjackEngine.hand_value(self.dealer_cards)
        if total != 22:
            self._credit_side_bet(key, None, '庄家非22点')
        else:
            suits = {card[0] for card in self.dealer_cards}
            colours = {'red' if card[0] in ('Diamond', 'Heart') else 'black'
                       for card in self.dealer_cards}
            if len(suits) == 1:
                odds, label = 50, '22点·全部牌同花'
            elif len(colours) == 1:
                odds, label = 20, '22点·全部牌同色'
            else:
                odds, label = 8, '22点·杂色'
            self._credit_side_bet(key, odds, label)
        self.save_balance()

    def _settle_dealer_dependent_side_bets(self):
        self._settle_dealer_22_side_bet()
        self._settle_bust_side_bet()


    # -------------------------------------------------------------- dealer phase
    def _advance_hand(self):
        if (not self.round_active or self.animation_running or self.settlement_running
                or self.switch_pending or self.ace_decision_mode or not self.dealer_blackjack_checked):
            return
        for idx in range(self.active_hand_index+1, len(self.hands)):
            if self.hands[idx]['status'] == 'active':
                self.active_hand_index = idx
                self.render_cards()
                self.update_display()
                self._prepare_active_split_hand()
                return
        self._start_dealer_turn()

    def _has_bust_wager(self):
        return self.round_side_bets.get(self.SHARED_BUST_KEY, 0.0) > 0

    def _has_dealer_dependent_side_wager(self):
        return (self._has_bust_wager()
                or self.round_side_bets.get(self.SHARED_DEALER_22_KEY, 0.0) > 0)


    def _all_hands_bust_or_surrendered(self):
        if not self.hands:
            return False
        for hand in self.hands:
            total, _ = BlackjackEngine.hand_value(hand.get('cards', ()))
            if hand.get('status') == 'surrendered':
                continue
            if hand.get('status') == 'bust' or total > 21:
                continue
            return False
        return True


    def _single_natural_blackjack(self):
        live = [h for h in self.hands if h['status'] not in ('surrendered', 'bust')]
        return bool(live) and all(self._is_natural_blackjack(h) for h in live)





    def _start_dealer_turn(self):
        if (not self.round_active or self.animation_running or self.settlement_running
                or self.switch_pending or self.ace_decision_mode or not self.dealer_blackjack_checked):
            return
        self.dealer_phase_active = True
        self.animation_running = True
        self.render_cards()
        self.update_display()
        def revealed():
            if not self._has_dealer_dependent_side_wager() and (self._all_hands_bust_or_surrendered()
                                                               or self._single_natural_blackjack()):
                self._queue(260, self._resolve_normal_round)
            else:
                self._queue(180, self._dealer_draw_until_done)
        # The second card is already in the shoe ledger; reveal it, never draw it again.
        self._reveal_dealer_hole(revealed)


    def _dealer_draw_until_done(self):
        if not self.round_active or self._round_result_committed:
            return
        total, soft = BlackjackEngine.hand_value(self.dealer_cards)
        if total < 17 or (total == 17 and soft):
            self._deal_dealer_card_animated(on_complete=lambda: self._queue(180, self._dealer_draw_until_done))
            return
        self._queue(260, self._resolve_normal_round)

    def _resolve_dealer_blackjack(self):
        if not self.round_active or self._round_result_committed:
            return
        self._round_result_committed = True
        self._settle_dealer_dependent_side_bets()
        self._settle_insurance(True)
        lines = ['庄家 Blackjack', self.insurance_result]
        for index, hand in enumerate(self.hands):
            if hand.get('settlement') is not None:
                continue
            natural = self._is_natural_blackjack(hand)
            self._settle_main_hand(hand, 'push' if natural else 'lose',
                '双方Blackjack 和局' if natural else '庄家Blackjack：主注输')
            lines.append(f'手{index+1}：{hand["result"]}')
        self.last_result_lines.extend(lines)
        self._finish_round(dealer_bj=True)

    def _settle_main_hand(self, hand, state, result):
        stake = self.hand_stake(hand)
        credit = stake * (2.0 if state == 'win' else 1.0 if state == 'push' else 0.0)
        self.balance += credit
        hand.update(settlement=state, base_settlement=state,
            double_settlement=state if hand.get('double_added', 0.0) else None,
            settlement_return=credit, result=result)


    def _resolve_normal_round(self):
        if not self.round_active or self._round_result_committed:
            return
        self._round_result_committed = True
        self._settle_dealer_dependent_side_bets()
        self._settle_insurance(False)
        dealer_total, _ = BlackjackEngine.hand_value(self.dealer_cards)
        self.dealer_22_main_push = False
        lines = [f'庄家 {dealer_total}' + ('：未爆牌主注和局' if dealer_total == 22 else '')]
        for index, hand in enumerate(self.hands):
            if hand.get('settlement') is not None:
                continue
            total, _ = BlackjackEngine.hand_value(hand['cards'])
            stake = self.hand_stake(hand)
            if hand['status'] == 'bust' or total > 21:
                state, result = 'lose', f'爆牌 -{self.format_money(stake)}'
            elif self._is_natural_blackjack(hand):
                state, result = 'win', f'Blackjack 1:1 +{self.format_money(stake)}'
            elif dealer_total == 22:
                state, result = 'push', '庄家22点 和局 Push'
                self.dealer_22_main_push = True
            elif dealer_total > 22 or total > dealer_total:
                state, result = 'win', f'胜1:1 +{self.format_money(stake)}'
            elif total == dealer_total:
                state, result = 'push', '和局 Push'
            else:
                state, result = 'lose', f'输 -{self.format_money(stake)}'
            self._settle_main_hand(hand, state, result)
            lines.append(f'手{index+1}：{result}')
        self.last_result_lines.extend(lines)
        self._finish_round(dealer_bj=False)

    def _calculate_last_win_amount(self):
        """Total money returned to the player's balance for this round.

        V16 intentionally includes returned stake: normal wins, Blackjack returns,
        PUSH, instant cashout, side-bet credits and insurance
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
        self._fade_dealer_22_notice(self.dealer_22_main_push)
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
        self._fade_dealer_22_notice(False)
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
        self.dealer_hole_hidden = self.dealer_blackjack_checked = False
        self.switch_pending = self.switch_used = False
        self._round_result_committed = False
        self.dealer_22_main_push = False
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
        betting = self._can_change_bets() and self.bet_chip_animation_count == 0
        self._set_button(self.clear_button, betting and (self.current_bet > 0 or any(self.current_side_bets.values())))
        self._set_button(self.repeat_button, betting and (self.last_bet > 0 or any(self.last_side_bets.values())))
        ready = all(self.current_bets[s] >= self.MIN_BET for s in self.SEATS)
        self._set_button(self.deal_button, betting and ready)
        self._set_round_control_visibility(self.round_active)
        hand = self.active_hand()
        active = self._can_play_hand(hand)
        for seat in self.SEATS:
            own_turn = active and hand['seat'] == seat
            for action, allowed, label in (
                ('hit', own_turn and self.can_hit(hand), '要牌'), ('stand', own_turn, '停牌'),
                ('double', own_turn and self.can_double(hand), '加倍'),
                ('split', own_turn and self.can_split(hand), '分牌')):
                self._set_button(self.action_buttons[(seat, action)], allowed, label)
            cashout = own_turn and self.can_surrender(hand)
            label = f'兑现金额\n{self.format_money(self.surrender_offer(hand)[0])}' if cashout else '兑现金额\n$0.00'
            self._set_button(self.action_buttons[(seat, 'surrender')], cashout, label)
            deciding = bool(self.ace_decision_mode and seat == self.SEATS[0] and not self.animation_running)
            insurance_cost = sum(self.round_original_bets.values())/2.0
            affordable = self.balance+1e-9 >= insurance_cost
            self._set_button(self.decision_buttons[(seat, 'accept')], deciding and affordable,
                             f'购买两边保险\n{self.format_money(insurance_cost)}')
            self._set_button(self.decision_buttons[(seat, 'decline')], deciding, '不购买保险')
            highlighted = bool(self.ace_decision_mode or self.switch_pending or any(
                self._is_current_hand(i) and h['seat'] == seat for i, h in enumerate(self.hands)))
            self.canvas.itemconfigure(self.seat_title_items[seat], fill='#F6D675' if highlighted else '#F2E6C9')
        for button in self.switch_buttons.values():
            self._set_button(button, self.can_switch())
        for spot in self.bet_spots.values():
            self.canvas.itemconfigure(spot['rect'], fill=spot['normal_fill'])
        self._raise_wager_chips()


    def show_game_instructions(self):
        """Switch rules and retained side-bet tables, in a scrollable rules window."""
        dialog = tk.Toplevel(self)
        dialog.title('换牌黑杰克 · 游戏说明')
        dialog.geometry('880x690')
        dialog.configure(bg=self.BG)
        dialog.transient(self.winfo_toplevel())
        tk.Label(dialog, text='换牌黑杰克  BLACKJACK SWITCH', bg=self.BG, fg=self.GOLD,
                 font=(self.cn_font, 20, 'bold')).pack(pady=(16, 10))
        body = tk.Frame(dialog, bg=self.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=22, pady=8)
        scroll = tk.Scrollbar(body)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text = tk.Text(body, bg='#123C30', fg='#F2E6C9', wrap=tk.WORD,
            relief=tk.FLAT, padx=18, pady=14, font=(self.cn_font, 12),
            spacing1=3, spacing3=6, yscrollcommand=scroll.set)
        text.pack(fill=tk.BOTH, expand=True)
        scroll.configure(command=text.yview)
        text.tag_configure('heading', foreground=self.GOLD, font=(self.cn_font, 15, 'bold'))
        sections = [
            ('一、双手下注与顺序',
             '左右主注金额必须相同。点击任一主注，会同时向两边各放一份所选筹码；余额需足够两份。'
             '每边主注最低$100、最高$500,000，每笔边注最高$100,000。\n'
             '牌桌从左到右：左完美对子、左主注、左21+3、中央爆牌！、右完美对子、右主注、右21+3。\n'
             '中央爆牌！上方另设一笔公共的“22点”边注，两项可分别下注。\n'
             '完美对子与21+3按各边独立下注；爆牌！是中央一笔公共边注。右键边注只清除该笔；右键任一主注或点击清除，会清除本局全部下注。\n'
             '起手两边各两张牌，庄家一明一暗。先结算完美对子与21+3，再选择保险、检查庄家黑杰克，最后才可换牌及行动。'),
            ('二、保险与庄家黑杰克',
             '庄家明牌A时，只选择一次是否购买两边保险；每边保险为该边原始主注的一半，'
             '按钮显示两边的总费用，需同时足额购买，保险利润2:1。'
             '一次选择完成后检查黑杰克。明牌为10/J/Q/K时直接检查。\n'
             '庄家起手黑杰克立即结算：玩家原始两张黑杰克主注平局，其余主注输；没有换牌或要牌机会。'
             '已结算的完美对子、21+3不受影响。保险按是否为庄家黑杰克独立结算。'),
            ('三、换牌与玩家行动',
             '确认庄家没有黑杰克后，可交换两边的第二张牌一次，或保留原牌。\n'
             '如果两边第二张牌点值相同（10/J/Q/K均按10点），则自动保留原牌并进入行动，不显示换牌选择。\n'
             '例：左7-10、右10-4，换牌后左7-4、右10-10。换牌后形成的两张21点是普通21点；'
             '使用换牌后两边都不再享有天然黑杰克资格。\n'
             '先完成左边所有手牌，再完成右边。可要牌、停牌、两张牌加倍；加倍后只补一张。'
             '每边原始手最多分牌一次，形成两手，全桌最多四手，不能再分。按相同点值可分牌。'
             '分牌后允许加倍；分A每手只补一张并自动停牌。分牌21点不算黑杰克。\n'
             '动作按钮的浅色箭纹向左表示左边手牌，向右表示右边手牌；保险与换牌使用双向箭纹。'),
            ('四、主注结算',
             '未换牌、未分牌的原始两张A+10点牌才是黑杰克，利润固定1:1。庄家黑杰克时双方平局。\n'
             '庄家软17要牌、硬17停牌。庄家22点时：天然黑杰克赢1:1，其他未爆牌手（含换牌21、分牌21及加倍）'
             '退回全部该手主注；已经爆牌的玩家手仍输。庄家23点或以上，未爆牌手赢1:1。'
             '其余比点数，大者赢1:1，同点平局；玩家爆牌输。\n'
             '保留原版即时兑现功能：报价只按玩家牌和庄家明牌估算，纳入软17要牌、22点平局及已查无黑杰克的条件，'
             '按最优要/停牌预期返还的90%报价；确认兑现后该手即时结算。'),
            ('五、完美对子（每边独立，使用换牌前原始两张）',
             '同花同点对子 25:1；同色同点对子 12:1；异色同点对子 6:1；其余输。'
             '这里的对子按牌面等级，J和Q不构成对子。'),
            ('六、21+3（每边原始两张＋庄家明牌）',
             '三张同花同点 100:1；同花顺 40:1；三条 30:1；顺子 10:1；同花 5:1；其余输。'
             '顺子允许A-2-3、Q-K-A，不允许K-A-2。换牌、加倍及分牌不改变这笔边注。'),
            ('七、爆牌！（中央一笔公共边注）',
             '按庄家的最终牌结算一次，独立于玩家主注是否爆牌或兑现。只要有爆牌边注，庄家都会按规则完成要牌。\n'
             '沿用原版：庄家3张爆牌 1:1；4张 2:1；5张 9:1；6张 50:1；7张 100:1；8张及以上 250:1。'
             '庄家22点仍属于爆牌边注的中奖结果，即使未爆牌的主注与庄家22点平局。庄家21点以下（含黑杰克）边注输。'),
            ('八、22点（爆牌！上方的公共边注）',
             '庄家最终恰好22点才中奖，按全部庄家牌判定，沿用Free Double赔率：'
             '全部同花50:1；否则全部同色20:1；杂色8:1。其余点数输。'
             '与主注及爆牌！分别结算；只要下注22点或爆牌！，庄家均按软17要牌、硬17停牌规则完成要牌。'),
        ]
        for heading, content in sections:
            text.insert(tk.END, heading+'\n', 'heading')
            text.insert(tk.END, content+'\n\n')
        text.configure(state=tk.DISABLED)
        tk.Button(dialog, text='关闭', command=dialog.destroy, bg='#40634B', fg='white',
                  font=(self.cn_font, 12), padx=24).pack(pady=(4, 14))
        dialog.bind('<Escape>', lambda _e: (dialog.destroy(), 'break')[-1])
        dialog.after(30, dialog.focus_set)

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

        # Refund only unresolved escrow on a forced exit. Already-settled
        # cash-outs and side-bet payments are not refunded again.
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
        return {**{(seat, key): 0.0 for seat in self.SEATS for key in self.HAND_SIDE_BET_KEYS},
                self.SHARED_DEALER_22_KEY: 0.0, self.SHARED_BUST_KEY: 0.0}

    def _bet_spot_key(self, seat, kind):
        if kind == 'Dealer 22':
            return self.SHARED_DEALER_22_KEY
        return self.SHARED_BUST_KEY if kind == 'Bust!' else (seat, kind)


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
                state='hidden' if playing else 'normal')

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
        key = self._bet_spot_key(seat, kind)
        if key not in self.bet_spots or not self._can_change_bets():
            return
        main = kind == 'MAIN'
        current = self.current_bets[seat] if main else self.current_side_bets[key]
        maximum = self.MAX_MAIN_BET if main else self.MAX_SIDE_BET
        amount = min(self.selected_chip, max(0.0, maximum-current))
        if amount <= 0:
            return
        keys = [(s, 'MAIN') for s in self.SEATS] if main else [key]
        cost = amount*len(keys)
        if self.balance+1e-9 < cost:
            messagebox.showwarning('余额不足', '两边主注同步下注，需要两份筹码金额。' if main
                else '余额不足以放置该筹码。', parent=self.winfo_toplevel())
            return
        self.balance -= cost
        self.show_last_win = False
        for target in keys:
            if main:
                self.current_bets[target[0]] += amount
            else:
                self.current_side_bets[target] += amount
            self.pending_bet_animation[target] += amount
            self.bet_chip_animation_count += 1
        self._sync_main_totals()
        self.update_display()
        for target in keys:
            self._animate_selected_chip_to_spot(target,
                lambda k=target: self._finish_bet_chip_animation(k, amount), amount=amount)


    def _clear_seat_bet(self, seat, kind):
        if not self._can_change_bets() or self.bet_chip_animation_count:
            return
        key = self._bet_spot_key(seat, kind)
        if key not in self.bet_spots:
            return
        if kind == 'MAIN':
            # A main spot clears the synchronized pair and their attached side wagers.
            self.clear_bets()
            return
        self.balance += self.current_side_bets[key]
        self.current_side_bets[key] = self.pending_bet_animation[key] = 0.0
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


    def _seat_play_origin(self, seat):
        key = (seat, 'MAIN' if seat == self.SEATS[0] else 'Perfect Pair')
        x = self.bet_spots[key]['chip_pos'][0]
        if seat == self.SEATS[1]:
            x += self.RIGHT_PLAY_OFFSET_X
        return x, self.bet_spots[(seat, 'MAIN')]['chip_pos'][1]

    def _player_card_position(self, hand, geometry, card_index):
        left, right, cx, _order, count_in_seat = geometry
        main_chip_x, origin_y = self._seat_play_origin(hand['seat'])
        first_x = (main_chip_x if count_in_seat == 1 else cx)-self.CARD_WIDTH/2
        first_y = (origin_y-self.MAIN_WAGER_LIFT-self.CARD_HEIGHT
                   -self.WAGER_CHIP_RADIUS-self.CARD_WAGER_GAP)
        # Use the full Classic spacing for every hand, including split hands.
        # Never shrink the gap according to lane width or the number of cards.
        fan_step = 44.0
        index = max(0, int(card_index))
        x = first_x+fan_step*index
        if index <= 3:
            y = first_y-24.0*index
        elif index <= 6:
            y = first_y-72.0+24.0*(index-3)
        else:
            y = first_y-24.0*(index-6)
        if hand.get('double_card_index')==index:
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
                        radius=self.WAGER_CHIP_RADIUS,
                        tags=(*tags, 'cashout_wager', f'hand_{index}_cashout_chip')))
                # Collected cash-outs stay out of the later round settlement.
                continue
            for component,stake in (('base',hand['base_bet']),('double',hand['double_added'])):
                returned = self._component_return_amount(hand,component) if self.settlement_running else None
                # Left to right: Double profit, base profit, base stake, Double stake.
                # Each 60px chip has a 4px gap, including during split settlement.
                profit_position = (base_x-self.CHIP_PITCH*(2 if component=='double' else 1),base_y)
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
                tags=('opening_wager',tag))
            # Lift the principal to the same enlarged-chip layout used by cards.
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
        spot = self.bet_spots[key]
        rows = self._outcome_chip_rows(('side',*key),stake,
            self.side_bet_return_amounts.get(key,0.0),spot['chip_pos'],
            spot.get('chip_radius',self.WAGER_CHIP_RADIUS),(), profit_position=spot.get('profit_pos'))
        for row in rows:
            if row['role']=='profit':
                self.pending_profit_chips.add(row['key'])
                def arrived(k=row['key']):
                    self.pending_profit_chips.discard(k)
                    self.update_bet_chips()
                self._animate_settlement_chips([(575,43,row['amount'],row['radius'])],row['pos'],440,
                    f'side_profit_fly_{key[0]}_{self.SIDE_BET_KEYS.index(key[1])}',arrived)


    def _dealer_badge_fill(self):
        if not self.dealer_cards or self.dealer_hole_hidden:
            return '#ffffff'
        total, soft = BlackjackEngine.hand_value(self.dealer_cards)
        if total == 22:
            return '#b9dcff'
        if total > 22:
            return '#e34848'
        if self.settlement_running:
            results = [h.get('settlement') for h in self.hands if h.get('status') != 'surrendered']
            if results and all(result == 'push' for result in results):
                return '#b9dcff'
            if results and all(result == 'lose' for result in results):
                return '#b9efb4'
            if results and all(result == 'win' for result in results):
                return '#e34848'
            return '#f2b0b0'
        if self.dealer_phase_active and (total >= 18 or (total == 17 and not soft)):
            return '#f2b0b0'
        return '#ffffff'


    def _card_dimensions(self, rotation=0):
        return ((self.CARD_HEIGHT,self.CARD_WIDTH) if rotation%180
                else (self.CARD_WIDTH,self.CARD_HEIGHT))


    def _oriented_card_pil(self, card, rotation=0, use_back=False):
        if Image is None:
            return None
        base = self.external_back_pil if use_back else self.external_card_pil.get(tuple(card))
        if base is None:
            base = self._make_fallback_card_pil(card, not use_back)
        return base.rotate(-rotation, expand=True) if rotation else base


    def _oriented_card_photo(self, card, rotation=0, use_back=False):
        if not rotation:
            return self.external_back_image if use_back else self._face_photo(card)
        if Image is None or ImageTk is None:
            return None
        if not hasattr(self, '_rotated_card_photos'):
            self._rotated_card_photos = {}
        key = ('back' if use_back else tuple(card),rotation)
        if key not in self._rotated_card_photos:
            base = self._oriented_card_pil(card, rotation, use_back)
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
            self.ace_decision_seat = seat
            self._show_ace_decision(mode)
            self.update_display()
        else:
            self.ace_decision_mode = self.ace_decision_seat = None
            self._check_opening_dealer_blackjack()


    def _draw_side_odds(self, tag):
        self.canvas.delete(tag)  # payout tiers stay in the ledger, without table labels


    def _settlement_chip_rows(self):
        rows = self._main_wager_rows()
        for key,stake in self.round_side_bets.items():
            if stake>0:
                spot = self.bet_spots[key]
                rows.extend(self._outcome_chip_rows(('side',*key),stake,
                    self.side_bet_return_amounts.get(key,0.0),spot['chip_pos'],
                    spot.get('chip_radius',self.WAGER_CHIP_RADIUS),
                    ('bet_chip_dynamic',spot['tag']), profit_position=spot.get('profit_pos')))
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
        self.save_balance()






# Explicit Switch names and the old names both work with existing launchers.
BubbleBlackjackSwitchGame = BubbleBlackjackGame

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


BlackjackSwitchGame = BlackjackGame

def main(parent=None, balance=10000, user=None, on_back=None,
         on_balance_change=None, username=None, close_returns_to_parent=False):
    if username is not None and user is None:
        user = username

    # Legacy positional compatibility: main(balance, username).
    if parent is not None and not isinstance(parent, tk.Misc):
        legacy_balance = parent
        legacy_user = balance if isinstance(balance, str) and user is None else user
        parent = None
        balance = legacy_balance
        user = legacy_user

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
    root.title('换牌黑杰克')
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
    return game


if __name__ == '__main__':
    main(balance=10_000_000)
