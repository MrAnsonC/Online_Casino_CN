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

# Blackjack Premiere — Classic UI with Premiere player/banker rules
import json
import math
import os
import sys
import random
import tkinter as tk
from functools import lru_cache
from tkinter import messagebox
from tkinter import font as tkfont

BLACKJACK_VERSION = "PREMIERE_V16_CLASSIC_UI"

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageTk = None
    ImageDraw = None
    ImageFont = None


# Project layout:
#   A_Tools/Card/CSM_Shuffler.py
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
# 8-deck ENHC Blackjack shoe / hand helpers
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
    MAX_TABLE_BET = 1_100_000.0  # compatibility only; independent limits are enforced below
    MAX_SPLIT_ACTIONS = 3       # casino-style maximum 4 player hands
    MAX_HANDS = 4
    BLACKJACK_PROFIT = 1.5      # 3:2
    INSURANCE_PROFIT = 2.0      # 2:1
    SPLIT_ACES_ONE_CARD_ONLY = True
    SIDE_BET_KEYS = ('Super Pair', '21+3', 'Super Tie', 'Crazy 7', 'Hot 21', 'Bust!')
    SIDE_BET_LABELS = {
        'Super Pair': '超级对子',
        '21+3': '21+3',
        'Super Tie': '超级平局',
        'Crazy 7': '疯狂7',
        'Hot 21': '热辣21',
        'Bust!': '爆牌！',
    }
    SIDE_BET_ODDS_TEXT = {
        'Super Pair': '50/5/3:1',
        '21+3': '100/40/30/10/5:1',
        'Super Tie': '50/15/8/3/1:1',
        'Crazy 7': '玩家主注疯狂7:2000/500/150/25/5:1；庄家主注富豪17:30/15/2:1',
        'Hot 21': '500/100/20/4/2/1:1',
        'Bust!': '玩家主注:250/100/50/9/2/1:1；庄家主注核爆:250/150/100/30/15/5:1',
    }

    M_CHIP_COLOR = '#102d47'
    SEATS = ('Player1',)
    SEAT_NAMES = {'Player1': '玩家'}
    SEAT_BOUNDS = {'Player1': (22.0, 1128.0)}
    ZONE_COLORS = {'Player1': '#35634B'}
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    SIDE_BET_DIAMETER = 122.0 * 2 / 3

    # phase_text is intentionally restricted to these five messages only.
    PHASE_BETTING = '双向黑杰克 · 请下注'
    PHASE_INSURANCE = '双向黑杰克 · 保险？'
    PHASE_EVEN_MONEY = '双向黑杰克 · 立刻获胜？'
    PHASE_PLAYING = '双向黑杰克 · 游戏中'
    PHASE_SETTLING = '双向黑杰克 · 结算中'

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
    MAIN_WAGER_LIFT = 72.0
    CARD_WAGER_GAP = 6.0
    DEALER_WAGER_OVERLAP = 10.0
    MAIN_BET_CENTER = (575.0, 557.0)
    MAIN_BET_RADIUS = 48.0
    MAIN_RING_START = 140.0
    MAIN_RING_EXTENT = 260.0
    DEALER_CARD_Y = 74.0

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

        import uuid
        self.csm_game_id = f"Premiere_Blackjack:{self.username or 'local'}:{uuid.uuid4().hex}"
        self.csm = ContinuousShuffleMachine()
        self.engine = BlackjackEngine(self.csm, self.csm_game_id)
        self.selected_chip = 1000.0
        # Premiere has two mutually-exclusive MAIN wager directions.  current_bet
        # remains one amount so the Classic settlement/animation framework stays
        # compatible; these side flags decide which physical MAIN spot owns it.
        self.main_bet_side = None          # None / 'player' / 'dealer'
        self._main_selection_animation_running = False
        self.round_main_bet_side = None    # locked direction for the live round
        # V10: PLAYER and BANKER each own an independent repeat-bet memory slot.
        # A slot is written only when a wager is actually locked into a live round.
        self.repeat_bet_memory = {
            'player': {'main': 0.0, 'sides': {key: 0.0 for key in self.SIDE_BET_KEYS}},
            'dealer': {'main': 0.0, 'sides': {key: 0.0 for key in self.SIDE_BET_KEYS}},
        }
        self.current_bet = 0.0
        self.current_side_bets = {key: 0.0 for key in self.SIDE_BET_KEYS}
        self.last_win_amount = 0.0
        self.show_last_win = False
        self.round_original_bet = 0.0
        self.round_side_bets = {key: 0.0 for key in self.SIDE_BET_KEYS}
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
        self.dealer_had_soft_17 = False
        self.round_deal_sequence = []
        self.round_initial_player_cards = []
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
        self.insurance_resolved = False
        self._banker_notice_source = None
        self._banker_notice_photo = None
        self._banker_notice_image_item = None
        self._banker_notice_text_item = None
        self._banker_notice_wording = ''
        self._banker_notice_level = 0.0
        self._banker_notice_target = False
        self._banker_notice_job = None
        self._opening_wager_animation = False
        self.settlement_flash_step = 0
        self.flash_mode = None
        self.flash_winning_side_bets = set()
        self.flash_main_bet = False
        self.flash_main_push_only = False
        # Text notices used by BANKER-main special push outcomes.
        # 17-point push: player bust + dealer 17.
        self.banker_17_main_push = False
        # Double-bust push: both player and dealer bust.
        self.banker_double_bust_main_push = False
        # V6: main-game settlement is tracked per player hand instead of one
        # global MAIN spot. This lets a losing split hand disappear while other
        # winning split hands keep their own base/double chips and flash.
        self.flash_winning_hand_indices = set()
        self.hand_zone_bounds = []
        # V7: exact positions of each split-hand wager inside the Evoplay MAIN oval.
        # Used both for drawing the 1–4 base chips / Double chip and settlement flash.
        self.main_wager_positions = {}
        self.bet_chip_animation_count = 0
        self.pending_bet_animation = {'MAIN_PLAYER': 0.0, 'MAIN_DEALER': 0.0, **{key: 0.0 for key in self.SIDE_BET_KEYS}}
        self._closing = False
        self.last_result_lines = []  # internal only; never shown to the player
        self.runtime_data_file = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..',
                'A_Logs',
                'Json',
                'Blackjack_Premiere.json'
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
        self.canvas.itemconfigure(self.phase_text, text=self.PHASE_BETTING)
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
        c.create_text(575, 18, text='双向黑杰克  PREMIERE BLACKJACK',
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
            text='庄家任何17点停牌   保险2:1   黑杰克3:2   最多分牌3次',
            font=(self.cn_font, 13, 'bold'), fill=self.GOLD, tags='rule_strip_text')
        self.rule_strip_left_text = c.create_text(400, 224, text='', state='hidden')
        self.rule_strip_right_text = c.create_text(700, 224, text='', state='hidden')
        self.rule_strip_chip_pos = (575, 224)  # legacy helper compatibility
        self.shoe_origin = (575, 52)  # identical to Caribbean Stud's deal origin
        # Keep Premiere's status API while using Classic's fixed table title.
        self.phase_text = c.create_text(575, 18, text=self.PHASE_BETTING,
                                       state='hidden', tags='phase_status')
        self.player_zone_rect = self.seat_zone_rects['Player1']
        self.player_zone_title = self.seat_title_items['Player1']
        self.player_zone_home = self.player_zone_round = (22, 252, 1128, 617)
        self.player_label_home = self.player_label_round = (575, 266)
        self.player_zone_mode = 'home'
        self._refresh_rule_strip_text()


    def draw_board(self):
        """Two circular, open-ring MAIN areas and the six side-bet boxes."""
        c = self.canvas
        x, y = self.MAIN_BET_CENTER
        self.bet_layout_home = {
            'MAIN_DEALER': self._main_bet_surface_layout(x, y-110),
            'MAIN_PLAYER': self._main_bet_surface_layout(x, y),
        }
        for key, side_x in zip(self.SIDE_BET_KEYS, (135, 285, 435, 715, 865, 1015)):
            self.bet_layout_home[key] = self._bet_surface_layout(side_x)
        self.bet_layout_round = dict(self.bet_layout_home)
        self.main_selected_home = {key: self._main_bet_surface_layout(x, y)
                                   for key in ('MAIN_PLAYER', 'MAIN_DEALER')}
        self.main_hidden_home = {key: self.bet_layout_home[key]
                                 for key in self.main_selected_home}
        self.bet_layout_round.update(self.main_selected_home)
        self.bet_layout_mode = 'home'
        self.main_split_labels = {'MAIN_PLAYER': '玩家主注', 'MAIN_DEALER': '庄家主注'}
        self.main_selected_labels = dict(self.main_split_labels)
        self.bet_spots, self.side_bet_spots = {}, {}
        for index, key in enumerate(('MAIN_PLAYER', 'MAIN_DEALER') + self.SIDE_BET_KEYS):
            main = key in self.main_selected_home
            bounds, label_pos, chip_pos = self.bet_layout_home[key]
            fill = '#175C98' if main else '#173B32'
            outline = ('#19345D' if key == 'MAIN_PLAYER' else '#F3373C') if main else self.GOLD
            tag = f'premiere_bet_{index}'
            shape = self._draw_bet_surface(bounds, fill, outline, tag, main)
            label = c.create_text(*label_pos,
                text=self.main_split_labels[key] if main else self.SIDE_BET_LABELS[key],
                font=(self.cn_font, -14, 'bold'), fill='#F2E6C9',
                tags=(tag, 'betting_spot_label'))
            self.bet_spots[key] = dict(key=key, bounds=bounds, label_pos=label_pos,
                chip_pos=chip_pos, rect=shape, label=label, tag=tag, shape='main_circle' if main else 'rounded_rect',
                normal_fill=fill, normal_outline=outline, normal_width=2)
            if main:
                self._decorate_main_bet_surface(self.bet_spots[key])
                side = 'player' if key == 'MAIN_PLAYER' else 'dealer'
                c.tag_bind(tag, '<Button-1>', lambda _e, s=side: self.place_main_bet(s))
                c.tag_bind(tag, '<Button-3>', lambda _e: self.clear_bets())
            else:
                self.side_bet_spots[key] = self.bet_spots[key]
                c.tag_bind(tag, '<Button-1>', lambda _e, k=key: self.place_side_bet(k))
                c.tag_bind(tag, '<Button-3>', lambda _e, k=key: self.clear_side_bet(k))
            c.tag_bind(tag, '<Enter>', lambda _e: c.configure(cursor='hand2'))
            c.tag_bind(tag, '<Leave>', lambda _e: c.configure(cursor=''))
        self._refresh_premiere_bet_labels()
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
        self.repeat_player_button = self._create_canvas_button(862, 628, 1000, 671,
            '重复下注(玩家)', lambda: self.repeat_last_bet('player'),
            '#536A43', tag='control_repeat_player', font_size=9)
        self.repeat_dealer_button = self._create_canvas_button(862, 675, 1000, 718,
            '重复下注(庄家)', lambda: self.repeat_last_bet('dealer'),
            '#9B403A', tag='control_repeat_dealer', font_size=9)
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
                self.action_buttons[action] = self._create_canvas_button(
                    left, 638, left+164, 720, label,
                    command, color,
                    tag=f'action_{seat}_{action}', font_size=12)
            for action, left, right, label, accept in (
                    ('accept', 405, 565, '购买保险', True),
                    ('decline', 585, 745, '不购买', False)):
                self.decision_buttons[action] = self._create_canvas_button(
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
        in_round = bool(in_round or (self.animation_running and not self.accept_bets))
        decision = bool(in_round and self.ace_decision_mode)
        side = self.round_main_bet_side if self.round_active else self.main_bet_side
        actions = bool(in_round and not decision and side == 'player')
        self.canvas.itemconfigure('chip_selector', state='hidden' if in_round else 'normal')
        for button in (self.clear_button, self.repeat_player_button,
                       self.repeat_dealer_button, self.deal_button, self.info_button):
            self._button_state(button, not in_round)
        for button in self.action_buttons.values():
            self._button_state(button, actions)
        for button in self.decision_buttons.values():
            self._button_state(button, decision)
        self._raise_visible_bottom_controls(in_round)

    def _set_rules_strip_visible(self, visible):
        self.canvas.itemconfigure('round_rule_strip', state='normal')
        self._refresh_rule_strip_text()


    def _refresh_rule_strip_text(self):
        # Reserve the same centre gap from the start for BANKER/insurance chips.
        # Neither the strip nor its text anchors move when a wager is selected.
        rule_side = self.round_main_bet_side
        if rule_side not in ('player', 'dealer'):
            rule_side = self.main_bet_side
        if rule_side == 'dealer':
            left = '玩家庄家软17要牌 / 硬17停牌'
            right = '黑杰克 3:2   庄家17点主注平局'
        else:
            left = '庄家软17要牌 / 硬17停牌'
            right = '保险2:1   黑杰克 3:2'
        self.canvas.itemconfigure(self.rule_strip_text, state='hidden')
        for item, x, text, anchor in (
                (self.rule_strip_left_text, 400, left, 'e'),
                (self.rule_strip_right_text, 700, right, 'w')):
            self.canvas.coords(item, x, 224)
            self.canvas.itemconfigure(item, text=text, anchor=anchor,
                font=(self.cn_font, -14, 'bold'), fill=self.GOLD, state='normal')

    def _set_rule_strip_text_color(self, color):
        for item in (self.rule_strip_text, self.rule_strip_left_text, self.rule_strip_right_text):
            try: self.canvas.itemconfigure(item, fill=color)
            except tk.TclError: pass

    def _render_insurance_chip(self):
        self.canvas.delete('insurance_chip')
        if not self.insurance_chip_visible or self.insurance_bet <= 0:
            return
        returned = self.insurance_return_amount if self.settlement_running else None
        self._draw_outcome_rows(self._outcome_chip_rows(('insurance',),
            self.insurance_bet, returned, self.rule_strip_chip_pos, self.INSURANCE_CHIP_RADIUS, ('insurance_chip',)))
        self._raise_wager_chips()

    def _animate_insurance_chip_to_rule(self, on_complete=None):
        sx, sy = self._selected_chip_origin()
        def landed():
            self.insurance_chip_visible = True
            self._render_insurance_chip()
            if callable(on_complete):
                on_complete()
        self._animate_settlement_chips([(sx, sy, self.insurance_bet, self.INSURANCE_CHIP_RADIUS)],
            self.rule_strip_chip_pos, 220, 'insurance_chip_fly', landed)

    def _show_ace_decision(self, mode):
        self.ace_decision_mode = mode
        if mode == 'even_money':
            self._set_button(self.decision_buttons['accept'], True, '立刻获胜')
            self._set_button(self.decision_buttons['decline'], True, '赌！')
            self.canvas.itemconfigure(self.phase_text, text=self.PHASE_EVEN_MONEY)
        else:
            can_buy = self.balance + 1e-9 >= self.round_original_bet / 2.0
            self._set_button(self.decision_buttons['accept'], can_buy, '购买保险')
            self._set_button(self.decision_buttons['decline'], True, '不购买')
            self.canvas.itemconfigure(self.phase_text, text=self.PHASE_INSURANCE)
        self._set_round_control_visibility(True); self._raise_visible_bottom_controls(True)

    def _resolve_ace_decision(self, accept):
        mode = self.ace_decision_mode
        if not mode or self.settlement_running:
            return
        hand = self.hands[0] if self.hands else None
        if mode == 'even_money':
            self.ace_decision_mode = None
            if accept and hand:
                hand['status'] = 'even_money'; hand['result'] = 'Even Money +1:1'
                hand['settlement'] = 'win'; hand['base_settlement'] = 'win'
                hand['double_settlement'] = None
                hand['settlement_return'] = self.round_original_bet * 2.0
                self.balance += self.round_original_bet * 2.0; self.save_balance()
                self.render_cards(); self.update_display()
                # V16: without a Bust! wager, Even Money is final immediately;
                # the dealer does not draw a second card.  A live Bust! wager still
                # requires the ordinary dealer run so that side bet can resolve.
                if not self._needs_full_dealer_for_side_bets():
                    self._queue(250, self._finish_even_money_without_dealer_card)
                else:
                    self._queue(250, self._start_dealer_turn)
            elif hand:
                hand['status'] = 'blackjack'
                self.render_cards(); self.update_display()
                self._queue(250, self._start_dealer_turn)
            return

        # Insurance decision.
        if accept:
            amount = self.round_original_bet / 2.0
            if self.balance + 1e-9 < amount:
                return
            self.balance -= amount; self.insurance_bet = amount
            self.insurance_result = '保险待定'; self.save_balance()
            self.ace_decision_mode = None
            self.animation_running = True
            self._set_round_control_visibility(True); self.update_display()
            def done():
                self.animation_running = False
                self.canvas.itemconfigure(self.phase_text, text=self.PHASE_PLAYING)
                self.update_display(); self._raise_visible_bottom_controls(True)
            self._animate_insurance_chip_to_rule(done)
        else:
            self.ace_decision_mode = None
            self.insurance_result = '未购买保险'
            self.canvas.itemconfigure(self.phase_text, text=self.PHASE_PLAYING)
            self.update_display(); self._raise_visible_bottom_controls(True)

    @staticmethod
    def _main_spot_key(side):
        return 'MAIN_DEALER' if side == 'dealer' else 'MAIN_PLAYER'

    def _display_main_side(self):
        return self.round_main_bet_side if self.round_active else self.main_bet_side

    def _main_wager_bounds(self):
        side = self._display_main_side()
        if side in ('player', 'dealer'):
            return self.bet_spots[self._main_spot_key(side)]['bounds']
        pb, db = (self.bet_spots[key]['bounds'] for key in ('MAIN_PLAYER', 'MAIN_DEALER'))
        return min(pb[0], db[0]), min(pb[1], db[1]), max(pb[2], db[2]), max(pb[3], db[3])

    def _refresh_main_selector_geometry(self):
        if not self.bet_spots or self._main_selection_animation_running:
            return
        selected = self._display_main_side()
        playing = bool(self.round_active or (self.animation_running and not self.accept_bets))
        for side, key in (('player', 'MAIN_PLAYER'), ('dealer', 'MAIN_DEALER')):
            spot = self.bet_spots[key]
            layout = self.main_selected_home if selected == side else self.bet_layout_home
            bounds, label_pos, chip_pos = layout[key]
            spot.update(bounds=bounds, label_pos=label_pos, chip_pos=chip_pos)
            visible = not playing and (selected is None or selected == side)
            self._position_main_bet_surface(spot, bounds)
            self._set_main_bet_surface_visible(spot, visible)
            if visible:
                self.canvas.tag_raise(spot['surface_tag'])
                self.canvas.tag_raise(spot['title_tag'])
        key = self._main_spot_key(selected)
        self.bet_spot_bounds = self._main_wager_bounds()
        self.bet_spot_rect, self.bet_spot_label = self.bet_spots[key]['rect'], self.bet_spots[key]['label']

    def _refresh_premiere_bet_labels(self):
        if not self.bet_spots:
            return
        self._refresh_main_selector_geometry()
        selected = self._display_main_side()
        for key, spot in self.bet_spots.items():
            disabled = selected is None and key in self.SIDE_BET_KEYS
            self.canvas.itemconfigure(spot['rect'],
                fill='#24352f' if disabled else spot['normal_fill'],
                outline='' if spot['shape'] == 'main_circle' else (
                    '#65784B' if disabled else spot['normal_outline']),
                width=0 if spot['shape'] == 'main_circle' else spot['normal_width'])
            self.canvas.itemconfigure(spot['label'], fill='#87918e' if disabled else '#F2E6C9')
        self.canvas.itemconfigure(self.bet_spots['Crazy 7']['label'],
                                  text='富豪17' if selected == 'dealer' else '疯狂7')
        self.canvas.itemconfigure(self.bet_spots['Bust!']['label'],
                                  text='核爆！' if selected == 'dealer' else '爆牌！')
        self._refresh_rule_strip_text()
        # update_display draws the chips BEFORE refreshing the selector. Raise
        # them last so a refreshed MAIN background cannot cover its wager.
        self._raise_wager_chips()

    def _animate_main_selection(self, side, on_complete=None):
        self._animate_main_choice(side, selecting=True, on_complete=on_complete)

    def _animate_main_deselection(self, side, on_complete=None):
        self._animate_main_choice(side, selecting=False, on_complete=on_complete)


    def _animate_betting_station(self, to_round, on_complete=None):
        # Classic's dealer/player zones and six side circles stay fixed.
        self.bet_layout_mode = self.player_zone_mode = 'round' if to_round else 'home'
        self._refresh_premiere_bet_labels()
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


    def _main_bet_surface_layout(self, x, y):
        radius = self.MAIN_BET_RADIUS
        return (x-radius, y-radius, x+radius, y+radius), (x, y+radius+10), (x, y)

    def _main_circle_point(self, bounds, degrees, scale=1.0):
        left, top, right, bottom = bounds
        cx, cy = (left+right)/2, (top+bottom)/2
        theta = math.radians(degrees)
        radius = (right-left)/2 * scale
        return cx+radius*math.cos(theta), cy+radius*math.sin(theta)

    def _main_circle_points(self, bounds, scale=1.0, start=0.0, extent=360.0):
        return tuple(value for step in range(65)
                     for value in self._main_circle_point(
                         bounds, start+extent*step/64, scale))

    def _decorate_main_bet_surface(self, spot):
        """Draw the reference's blue centre, interrupted ring and curved title.

        Native canvas items keep this available even when Pillow is absent.
        Surface and title tags deliberately exclude the wager chip items.
        """
        c = self.canvas
        spot['surface_tag'] = f"{spot['tag']}_surface"
        spot['title_tag'] = f"{spot['tag']}_title"
        c.addtag_withtag(spot['surface_tag'], spot['rect'])
        tags = (spot['tag'], spot['surface_tag'], 'betting_spot')
        spot['surface_layers'] = [(spot['rect'], 1.0)]
        outer, centre = (23, 92, 152), (221, 226, 196)
        for step in range(1, 25):
            t = step/24.0
            color = '#' + ''.join(f'{round(a+(b-a)*t):02x}'
                                  for a, b in zip(outer, centre))
            scale = 1.0-0.96*t
            item = c.create_polygon(*self._main_circle_points(spot['bounds'], scale),
                                    fill=color, outline='', tags=tags)
            spot['surface_layers'].append((item, scale))
        ring_color = spot['normal_outline']
        ring_edge = '#FF9295' if spot['key'] == 'MAIN_DEALER' else '#A5BED4'
        ring = self._main_circle_points(spot['bounds'],
            start=self.MAIN_RING_START, extent=self.MAIN_RING_EXTENT)
        spot['ring_items'] = [
            c.create_line(*ring,
                          fill=ring_edge, width=9, capstyle=tk.ROUND, tags=tags),
            c.create_line(*ring,
                          fill=ring_color, width=6, capstyle=tk.ROUND, tags=tags),
        ]
        title = self.main_split_labels[spot['key']]
        spot['curved_title'] = []
        for index, char in enumerate(title):
            # Keep all four characters on the ring's radius, inside the
            # bottom opening (40-140 degrees), clear of both rounded ends.
            theta = 122.0-index*64.0/max(1, len(title)-1)
            item = c.create_text(0, 0, text=char, font=(self.cn_font, -14, 'bold'),
                fill='#FF6266' if spot['key'] == 'MAIN_DEALER' else '#F2E6C9',
                tags=(spot['tag'], spot['title_tag'], 'betting_spot_label'))
            spot['curved_title'].append((item, theta))
        # The old single text item remains as a compatibility handle.
        c.itemconfigure(spot['label'], state='hidden')
        self._position_main_bet_surface(spot, spot['bounds'])

    def _position_main_bet_surface(self, spot, bounds):
        for item, scale in spot['surface_layers']:
            self.canvas.coords(item, *self._main_circle_points(bounds, scale))
        ring = self._main_circle_points(bounds,
            start=self.MAIN_RING_START, extent=self.MAIN_RING_EXTENT)
        for item in spot['ring_items']:
            self.canvas.coords(item, *ring)
        for item, theta in spot['curved_title']:
            x, y = self._main_circle_point(bounds, theta)
            before = self._main_circle_point(bounds, theta+0.5)
            after = self._main_circle_point(bounds, theta-0.5)
            angle = math.degrees(math.atan2(before[1]-after[1], after[0]-before[0]))
            self.canvas.coords(item, x, y)
            self.canvas.itemconfigure(item, angle=angle)
        self.canvas.coords(spot['label'], *spot['label_pos'])

    def _set_main_bet_surface_visible(self, spot, visible):
        state = 'normal' if visible else 'hidden'
        self.canvas.itemconfigure(spot['surface_tag'], state=state)
        self.canvas.itemconfigure(spot['title_tag'], state=state)
        self.canvas.itemconfigure(spot['label'], state='hidden')

    def _bet_surface_layout(self, x, main=False):
        """Reserve distinct rows for an amount and its betting-area title."""
        if main:
            return self._main_bet_surface_layout(x, self.MAIN_BET_CENTER[1])
        return (x-60, 535, x+60, 616), (x, 608), (x, 566)

    def _draw_bet_surface(self, bounds, fill, outline, tag, main=False):
        if main:
            return self.canvas.create_polygon(*self._main_circle_points(bounds),
                fill=fill, outline='', tags=(tag, 'betting_spot'))
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

    def _animate_selected_chip_to_spot(self, spot_key, on_complete=None, target_pos=None, amount=None):
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
        tx, ty = target_pos or spot['chip_pos']
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

    def _animate_amount_chip_to_spot(self, spot_key, amount, on_complete=None, target_pos=None):
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
        tx, ty = target_pos or spot['chip_pos']
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
        if spot_key in ('MAIN_PLAYER', 'MAIN_DEALER'):
            if self.round_active or self._opening_wager_animation:
                return 0.0
            expected = self._main_spot_key(self.main_bet_side) if self.main_bet_side else None
            amount = self.current_bet if spot_key == expected else 0.0
        elif self.round_active:
            if spot_key in self.side_bet_early_collected:
                return 0.0
            amount = self.round_side_bets.get(spot_key, 0.0)
            if self.settlement_running:
                amount = min(amount, self.side_bet_return_amounts.get(spot_key, 0.0))
        else:
            amount = self.current_side_bets.get(spot_key, 0.0)
        if not self.round_active:
            amount -= self.pending_bet_animation.get(spot_key, 0.0)
        return max(0.0, amount)

    def update_bet_chips(self):
        self.canvas.delete('bet_chip_dynamic')
        if self.settlement_visual_stage == 'returning':
            return
        for key, spot in self.bet_spots.items():
            amount = self._bet_amount_for_spot(key)
            if amount > 0:
                self._draw_baccarat_chip(*spot['chip_pos'], amount,
                    tags=('bet_chip_dynamic', spot['tag'], 'principal_chip'), radius=self.WAGER_CHIP_RADIUS)
            if self.round_active and key in self.SIDE_BET_KEYS:
                rows = self._outcome_chip_rows(('side', key), self.round_side_bets.get(key, 0.0),
                    self.side_bet_return_amounts.get(key, 0.0), spot['chip_pos'], self.WAGER_CHIP_RADIUS,
                    ('bet_chip_dynamic', spot['tag']))
                self._draw_outcome_rows([row for row in rows if row['role'] == 'profit'])
        self._raise_wager_chips()

    def _finish_bet_chip_animation(self, spot_key, amount):
        self.pending_bet_animation[spot_key] = max(
            0.0, float(self.pending_bet_animation.get(spot_key, 0.0)) - float(amount))
        self.bet_chip_animation_count = max(0, self.bet_chip_animation_count - 1)
        self.update_display()
        self.save_balance()

    def _restore_betting_spot_label_colors(self):
        for spot in self.bet_spots.values():
            self.canvas.itemconfigure(spot['label'], fill='#F2E6C9')
        self._set_rule_strip_text_color(self.GOLD)

    def _draw_side_bet_progress_badges(self):
        self.canvas.delete('side_bet_progress_badge')

    def _collect_losing_side_bet_upward(self, key):
        """Collect one resolved losing side-bet chip upward during live play."""
        if key == 'Bust!' or key in self.side_bet_early_collected:
            return
        stake = float(self.round_side_bets.get(key, 0.0))
        spot = self.bet_spots.get(key)
        if stake <= 0.0 or not spot:
            return
        self.side_bet_early_collected.add(key)
        # Remove the stationary chip first, then animate a clone upward.
        self.update_bet_chips()
        x, y = spot['chip_pos']
        safe = ''.join(ch if ch.isalnum() else '_' for ch in key)
        self._animate_settlement_chips(
            [(x, y, stake, self.WAGER_CHIP_RADIUS)], lambda sx, sy: (sx, -35.0), 300,
            f'side_bet_collect_{safe}')

    def _draw_side_bet_win_odds_badges(self):
        self.canvas.delete('side_bet_win_odds')

    def _settlement_losing_chip_sources(self):
        """Return visible losing wager components as (x,y,amount,radius)."""
        sources=[]
        # Side bets that were actually staked but did not return anything.
        for key in self.SIDE_BET_KEYS:
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
        for idx,hand in enumerate(self.hands[:4]):
            if idx>=len(layout): break
            if float(hand.get('base_bet',0.0))>0 and hand.get('base_settlement')=='lose':
                x,y=layout[idx]['base']; sources.append((x,y,float(hand['base_bet']),self.WAGER_CHIP_RADIUS))
            if float(hand.get('double_added',0.0))>0 and hand.get('double_settlement')=='lose':
                x,y=layout[idx]['double']; sources.append((x,y,float(hand['double_added']),self.WAGER_CHIP_RADIUS))

        if self.insurance_bet>0.0 and self.insurance_return_amount<=0.0:
            x,y=self.rule_strip_chip_pos; sources.append((x,y,float(self.insurance_bet),self.INSURANCE_CHIP_RADIUS))
        return sources

    def _settlement_return_chip_sources(self):
        return [(*row['pos'], row['amount'], row['radius'])
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

    def place_main_bet(self, side):
        if side not in ('player', 'dealer'):
            return
        if (not self.accept_bets or self.round_active or self.animation_running
                or self.settlement_running or self._main_selection_animation_running):
            return
        if self.main_bet_side is not None and self.main_bet_side != side:
            return

        remaining_limit = max(0.0, self.MAX_MAIN_BET - float(self.current_bet))
        if remaining_limit <= 1e-9:
            return
        # If the selected chip would cross the limit, silently place only the
        # exact remaining amount so this MAIN lands on its $500K cap.
        amount = min(float(self.selected_chip), remaining_limit)
        if self.balance + 1e-9 < amount:
            messagebox.showwarning('余额不足', '余额不足以放置该筹码。', parent=self.winfo_toplevel())
            return

        first_selection = self.main_bet_side is None
        self.main_bet_side = side
        self.show_last_win = False
        self.balance -= amount
        self.current_bet += amount
        spot_key = self._main_spot_key(side)
        self.pending_bet_animation[spot_key] += amount
        self.bet_chip_animation_count += 1

        target_pos = None
        if first_selection:
            target_pos = tuple(self.main_selected_home[spot_key][2])
            self._animate_main_selection(side)
        else:
            self._refresh_premiere_bet_labels()

        self.update_display()
        if abs(amount - float(self.selected_chip)) < 1e-9:
            self._animate_selected_chip_to_spot(
                spot_key,
                lambda k=spot_key, a=amount: self._finish_bet_chip_animation(k, a),
                target_pos=target_pos)
        else:
            self._animate_amount_chip_to_spot(
                spot_key, amount,
                lambda k=spot_key, a=amount: self._finish_bet_chip_animation(k, a),
                target_pos=target_pos)

    def place_bet(self):
        # Compatibility with older callers: default to the PLAYER direction.
        self.place_main_bet('player')

    def place_side_bet(self, key):
        if (key not in self.SIDE_BET_KEYS or not self.accept_bets or self.round_active
                or self.animation_running or self.settlement_running
                or self._main_selection_animation_running):
            return
        if self.main_bet_side not in ('player', 'dealer'):
            messagebox.showwarning(
                '请选择主注',
                '边注会在选择“玩家”或“庄家”主注后开放。',
                parent=self.winfo_toplevel())
            return
        current_side_amount = float(self.current_side_bets.get(key, 0.0))
        remaining_limit = max(0.0, self.MAX_SIDE_BET - current_side_amount)
        if remaining_limit <= 1e-9:
            return
        # Each side-bet owns its own $100K cap. Oversized chip clicks are silently
        # reduced to the exact remaining capacity of this one betting spot.
        amount = min(float(self.selected_chip), remaining_limit)
        if self.balance + 1e-9 < amount:
            messagebox.showwarning('余额不足', '余额不足以放置该筹码。', parent=self.winfo_toplevel())
            return

        self.show_last_win = False
        self.balance -= amount
        self.current_side_bets[key] += amount
        self.pending_bet_animation[key] += amount
        self.bet_chip_animation_count += 1
        self.update_display()
        if abs(amount - float(self.selected_chip)) < 1e-9:
            self._animate_selected_chip_to_spot(
                key, lambda k=key, a=amount: self._finish_bet_chip_animation(k, a))
        else:
            self._animate_amount_chip_to_spot(
                key, amount, lambda k=key, a=amount: self._finish_bet_chip_animation(k, a))

    def clear_side_bet(self, key):
        if (key not in self.SIDE_BET_KEYS or not self.accept_bets or self.round_active
                or self.animation_running or self.settlement_running
                or self.bet_chip_animation_count > 0):
            return
        amount = self.current_side_bets.get(key, 0.0)
        if amount > 0:
            self.balance += amount
            self.current_side_bets[key] = 0.0
            self.pending_bet_animation[key] = 0.0
            self.update_display()
            self.save_balance()

    def clear_bets(self):
        if (not self.accept_bets or self.round_active or self.animation_running
                or self.settlement_running or self.bet_chip_animation_count > 0
                or self._main_selection_animation_running):
            return
        refund = self.current_bet + sum(self.current_side_bets.values())
        if refund <= 0:
            return

        selected_side = self.main_bet_side
        self.balance += refund
        self.current_bet = 0.0
        self.current_side_bets = {key: 0.0 for key in self.SIDE_BET_KEYS}
        self.pending_bet_animation = {
            'MAIN_PLAYER': 0.0, 'MAIN_DEALER': 0.0,
            **{key: 0.0 for key in self.SIDE_BET_KEYS}}
        # Remove all chips immediately, but keep the selected-side state until its
        # 0.20 s reverse MAIN animation has visually returned to the two choices.
        self.update_bet_chips()
        self.save_balance()

        if selected_side in ('player', 'dealer'):
            self._animate_main_deselection(
                selected_side,
                on_complete=lambda: (self._refresh_premiere_bet_labels(), self.update_display()))
        else:
            self.main_bet_side = None
            self._refresh_premiere_bet_labels()
            self.update_display()

    def repeat_last_bet(self, side):
        """Replace all pending wagers with the saved wager for *side*.

        Both repeat buttons stay usable whenever their own memory exists. If the
        requested direction matches the currently-selected MAIN direction, the
        central MAIN selector stays in place and only the wager chips are replayed.
        Switching directions performs the ordinary MAIN deselect/select transition.
        """
        if side not in ('player', 'dealer'):
            return
        if (not self.accept_bets or self.round_active or self.animation_running
                or self.settlement_running or self.bet_chip_animation_count > 0
                or self._main_selection_animation_running):
            return

        memory = self.repeat_bet_memory.get(side, {})
        saved_main = min(float(memory.get('main', 0.0)), self.MAX_MAIN_BET)
        saved_sides = {
            key: min(float(memory.get('sides', {}).get(key, 0.0)), self.MAX_SIDE_BET)
            for key in self.SIDE_BET_KEYS
        }
        if saved_main < self.MIN_BET:
            return

        target_total = saved_main + sum(saved_sides.values())
        current_refund = self.current_bet + sum(self.current_side_bets.values())
        # Check against the balance that will exist after the current pending
        # wager is removed, so a failed repeat never destroys the live wager.
        if self.balance + current_refund + 1e-9 < target_total:
            messagebox.showwarning('无法重复下注', '余额不足。', parent=self.winfo_toplevel())
            return

        current_side = self.main_bet_side
        same_side = current_side == side
        self.show_last_win = False

        # First remove every current pending wager and refund it.  Chip graphics
        # disappear immediately; MAIN geometry is handled separately below.
        self.balance += current_refund
        self.current_bet = 0.0
        self.current_side_bets = {key: 0.0 for key in self.SIDE_BET_KEYS}
        self.pending_bet_animation = {
            'MAIN_PLAYER': 0.0, 'MAIN_DEALER': 0.0,
            **{key: 0.0 for key in self.SIDE_BET_KEYS}}
        self.update_bet_chips()
        self.save_balance()

        def apply_saved_wager(animate_selection):
            target_main_key = self._main_spot_key(side)
            self.main_bet_side = side

            self.balance -= target_total
            self.current_bet = saved_main
            self.current_side_bets = dict(saved_sides)

            wagers = {target_main_key: saved_main, **saved_sides}
            for key, amount in wagers.items():
                if amount <= 0.0:
                    continue
                self.pending_bet_animation[key] += amount
                self.bet_chip_animation_count += 1

            main_target_pos = None
            if animate_selection:
                main_target_pos = tuple(self.main_selected_home[target_main_key][2])
                self._animate_main_selection(side)
            else:
                # Same-side repeat deliberately keeps the existing MAIN selector
                # geometry fixed: no reverse/forward MAIN conversion animation.
                self._refresh_premiere_bet_labels()

            self.update_display()
            for key, amount in wagers.items():
                if amount <= 0.0:
                    continue
                self._animate_amount_chip_to_spot(
                    key, amount,
                    lambda k=key, a=amount: self._finish_bet_chip_animation(k, a),
                    target_pos=(main_target_pos if key == target_main_key else None))

        if same_side:
            # Keep the selected central MAIN exactly where it is; only replay chips.
            apply_saved_wager(False)
        elif current_side in ('player', 'dealer'):
            # Opposite direction: current chips are already gone. Return the MAIN
            # selector to PLAYER/BANKER, then select the requested memory direction.
            self._animate_main_deselection(
                current_side,
                on_complete=lambda: apply_saved_wager(True))
        else:
            # No current MAIN direction: ordinary first-selection animation.
            apply_saved_wager(True)

    # -------------------------------------------------------------- Blackjack_Premiere.json
    def save_runtime_store(self, burn_complete=True):
        data = {
            'version': 2,
            'variant': 'Premiere_Blackjack',
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
        # CSM 的加密状态是唯一牌序来源，不在游戏存档复制独立牌靴。
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
        dialog.title('双向黑杰克 · 切牌')
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
        """兼容旧主程序的入口；连续洗牌机不需要切牌或烧牌。"""
        if self._closing or self.round_active:
            return
        self.animation_running = False
        self.accept_bets = True
        self.canvas.itemconfigure(self.phase_text, text=self.PHASE_BETTING)
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
            item = self.canvas.create_rectangle(sx,sy,sx+100,sy+140,fill='#253e66',outline='#d7c46a',
                                                tags=('burn_card','animation_card'))
        def step(i=0):
            t=min(1.0,i/20.0); e=1-(1-t)**3
            x=sx+(target_x-sx)*e; y=sy+(target_y-sy)*e
            if self.canvas.type(item)=='image': self.canvas.coords(item,x,y)
            else: self.canvas.coords(item,x,y,x+100,y+140)
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
        self.canvas.itemconfigure(self.phase_text, text=self.PHASE_PLAYING)

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
            self.canvas.itemconfigure(self.phase_text, text=self.PHASE_PLAYING)
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
        self.canvas.itemconfigure(self.phase_text, text=self.PHASE_BETTING)
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
        for tag in ('dealt_card','temp_card','hand_label','hand_zone','hand_wager','animation_card','split_lane_animation'):
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
            if self.round_main_bet_side == 'dealer':
                # Keep BANKER's chip at the opening-card landing point.
                # Later dealer draws may recenter the cards, never this chip.
                cx = self.WIDTH/2
                cy = (self.DEALER_CARD_Y+self.CARD_HEIGHT+self.WAGER_CHIP_RADIUS
                      - self.DEALER_WAGER_OVERLAP)
            else:
                x,y = self._player_card_position(hand, geometry[index], 0)
                cx = self._wager_center_x(x+self.CARD_WIDTH/2, geometry[index], right_slots=1)
                # PLAYER wagers retain their clear gap below the first card.
                cy = y+self.CARD_HEIGHT+self.WAGER_CHIP_RADIUS+self.CARD_WAGER_GAP
            double = (cx+self.CHIP_PITCH,cy)  # Double uses the shared chip spacing.
            result.append({'base': (cx,cy), 'double': double})
        return result

    def _component_return_amount(self, hand, component):
        """Return the displayed settlement amount for one base/Double chip."""
        if self.round_main_bet_side == 'dealer' and component == 'base':
            state = hand.get('base_settlement')
            if state in ('win', 'push', 'refund'):
                return max(0.0, float(hand.get('settlement_return', 0.0)))
            return 0.0
        if component == 'base':
            amount = float(hand.get('base_bet', 0.0))
            state = hand.get('base_settlement')
        else:
            amount = float(hand.get('double_added', 0.0))
            state = hand.get('double_settlement')
        if amount <= 0.0 or not state:
            return 0.0
        if state == 'win':
            # Only an unsplit natural Blackjack receives 3:2. Split 21 is 1:1.
            natural = (component == 'base'
                       and hand.get('status') != 'even_money'
                       and not hand.get('from_split', False)
                       and BlackjackEngine.is_blackjack(hand.get('cards', ())))
            return amount * (1.0 + self.BLACKJACK_PROFIT) if natural else amount * 2.0
        if state in ('push', 'refund'):
            return amount
        if state == 'cashout':
            stake = self.hand_stake(hand)
            total_return = float(hand.get('settlement_return', 0.0))
            return (total_return * amount / stake) if stake > 0 else 0.0
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
        if self.round_main_bet_side == 'dealer' and self.settlement_running:
            # The cards belong to the automated player; the wager belongs to BANKER.
            if settlement == 'win': return '#e34848'
            if settlement == 'lose': return '#b9efb4'
            if settlement in ('push', 'refund'): return '#b9dcff'
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
        return self.WIDTH/2-width/2+card_index*step, self.DEALER_CARD_Y

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
                soft_stand=soft and len(self.dealer_cards)>=2 and 18<=total<=21),
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
                    rotation=90 if hand.get('double_card_index')==j else 0)
            self._draw_hand_total_badge(index, left, right)
        self._draw_main_hand_wagers()
        self._render_insurance_chip()
        self._raise_visible_bottom_controls(self.round_active)
        self._raise_wager_chips()
        self.canvas.tag_raise('banker_push_notice')

    def _render_card(self, card, x, y, tags=('dealt_card',), rotation=0):
        photo = self._oriented_card_photo(card, rotation)
        if photo is not None:
            return self.canvas.create_image(x,y,image=photo,anchor='nw',tags=tags)
        width,height = self._card_dimensions(rotation)
        suit,rank = card
        fg = '#c22631' if suit in ('Diamond','Heart') else '#111111'
        symbol = {'Club':'♣','Diamond':'♦','Heart':'♥','Spade':'♠'}.get(suit,suit[:1])
        self.canvas.create_rectangle(x,y,x+width,y+height,
            fill='#f4efe4',outline='#d7cbb9',width=2,tags=tags)
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
                 from_split=False, split_aces=False, needs_split_draw=False):
        return {
            'cards': list(cards or []),
            'base_bet': float(base_bet),
            'double_added': 0.0,
            'contains_original': bool(contains_original),
            'from_split': bool(from_split),
            'split_aces': bool(split_aces),
            'needs_split_draw': bool(needs_split_draw),
            'status': 'active',
            'result': '',
            'cashout_credit': 0.0,
            # Component-level settlement state is needed for ENHC/OBO.  In a
            # dealer Blackjack, the Original Bet may lose while a double chip
            # on that same hand is refunded.
            'settlement': None,
            'base_settlement': None,
            'double_settlement': None,
            'settlement_return': 0.0,
        }

    @staticmethod
    def hand_stake(hand):
        return float(hand.get('base_bet', 0.0)) + float(hand.get('double_added', 0.0))

    def deal_cards(self):
        if (not self.accept_bets or self.round_active or self.animation_running
                or self.settlement_running or self.bet_chip_animation_count > 0
                or self._main_selection_animation_running):
            return
        if self.main_bet_side not in ('player', 'dealer'):
            messagebox.showwarning('请选择主注', '必须先选择“主注-玩家”或“主注-庄家”中的一个。',
                                   parent=self.winfo_toplevel()); return
        if self.current_bet + 1e-9 < self.MIN_BET:
            messagebox.showwarning('最低下注', f'主注最低下注为 {self.format_money(self.MIN_BET)}。',
                                   parent=self.winfo_toplevel()); return
        if self.engine.remaining_cards() < 30:
            messagebox.showerror('自动洗牌机', '目前可用牌不足 30 张，请稍后再试。',
                                 parent=self.winfo_toplevel()); return
        try:
            self.engine.start_round()
        except (CSMError, OSError, RuntimeError) as exc:
            messagebox.showerror('自动洗牌机', f'无法开始牌局：{exc}',
                                 parent=self.winfo_toplevel()); return

        # Lock betting immediately, but DO NOT move current_bet into round state
        # yet.  This keeps the MAIN chip continuously visible while the entire
        # station animates to its in-round geometry (fixes the old brief vanish).
        self.accept_bets=False; self.animation_running=True
        self._set_button(self.deal_button, False)
        self.canvas.itemconfigure(self.phase_text,text=self.PHASE_PLAYING)
        self.update_display()
        # Bottom strip switches immediately when Enter/click is pressed, even
        # while the 0.20 s table animation is still running.
        self._set_round_control_visibility(True)
        for button in self.action_buttons.values():
            self._set_button(button, False)
        self._raise_visible_bottom_controls(True)

        def after_old_cards():
            self._animate_betting_station(True, on_complete=self._begin_round_after_bet_layout)
        if self.canvas.find_withtag('dealt_card'):
            self._animate_previous_round_cards_out(after_old_cards)
        else:
            after_old_cards()

    def _begin_round_after_bet_layout(self):
        self.settlement_visual_stage = None
        self.pending_profit_chips = set()
        self._opening_wager_animation = True
        self.insurance_resolved = False
        self.round_active=True
        self.round_main_bet_side=self.main_bet_side
        # V10: save this ACTUAL launched round into the repeat slot belonging to
        # its MAIN direction. PLAYER and BANKER histories never overwrite each other.
        if self.round_main_bet_side in ('player', 'dealer'):
            self.repeat_bet_memory[self.round_main_bet_side] = {
                'main': float(self.current_bet),
                'sides': {key: float(self.current_side_bets.get(key, 0.0))
                          for key in self.SIDE_BET_KEYS},
            }
        # The strip may have been painted one animation frame earlier using the
        # pre-round state. Refresh immediately after locking the MAIN direction.
        self._refresh_rule_strip_text()
        self.round_original_bet=self.current_bet; self.round_side_bets=dict(self.current_side_bets)
        self.current_bet=0.0; self.current_side_bets={key:0.0 for key in self.SIDE_BET_KEYS}
        self.main_bet_side=None
        self.insurance_bet=0.0; self.insurance_result=''; self.insurance_return_amount=0.0
        self.insurance_chip_visible=False; self.flash_insurance_rule=False; self.ace_decision_mode=None
        self.split_actions=0; self.dealer_cards=[]; self.dealer_had_soft_17=False; self.round_deal_sequence=[]; self.side_bet_results={}
        self.side_bet_return_amounts={}; self.side_bet_hit_odds={}; self.side_bet_hit_labels={}
        self.side_bet_early_collected=set()
        self.flash_winning_side_bets=set(); self.flash_main_bet=False; self.flash_main_push_only=False
        self.banker_17_main_push=False
        self.banker_double_bust_main_push=False
        self._fade_banker_push_notice(False)
        self.flash_winning_hand_indices=set(); self.settlement_running=False; self.settlement_flash_step=0
        self.dealer_phase_active=False
        self.flash_mode=None
        self.hands=[self.new_hand(base_bet=self.round_original_bet,contains_original=True)]
        self.active_hand_index=0; self.last_result_lines=[]
        self.canvas.itemconfigure(self.phase_text,text=self.PHASE_PLAYING)
        self._set_round_control_visibility(True)
        # Render the MAIN wager at the exact moved chip position BEFORE removing
        # the old destination chip, so there is no one-frame disappearance.
        self.render_cards(); self.update_display(); self._raise_visible_bottom_controls(True)

        sequence=('P','D','P')
        def deal_step(index=0):
            if index>=len(sequence):
                self.animation_running=False; self.render_cards(); self._after_initial_deal(); return
            who=sequence[index]
            if who=='P':
                self._deal_player_card_animated(0,on_complete=lambda:self._queue(80,deal_step,index+1))
            else:
                self._deal_dealer_card_animated(on_complete=lambda:self._queue(80,deal_step,index+1))
        self._animate_starting_wagers(deal_step)

    def _after_initial_deal(self):
        hand=self.hands[0]; upcard=self.dealer_cards[0]
        self.round_initial_player_cards = list(hand.get('cards', ())[:2])
        self._settle_initial_side_bets()
        player_bj=BlackjackEngine.is_blackjack(hand['cards']); dealer_ace=upcard[1]=='A'

        if self.round_main_bet_side == 'dealer':
            # BANKER main bet never exposes player decisions or insurance. A natural
            # player Blackjack is frozen so the dealer second card can determine
            # the priority settlement conditions.
            if player_bj:
                hand['status']='blackjack'; hand['result']='玩家Blackjack'
                self.render_cards(); self.update_display()
                self._queue(260, self._start_dealer_turn)
            else:
                self.canvas.itemconfigure(self.phase_text,text=self.PHASE_PLAYING)
                self.update_display()
                self._queue(180, self._auto_play_player_for_dealer_main)
            return

        # PLAYER main bet keeps Classic insurance / Even Money behaviour.
        if dealer_ace:
            self._show_ace_decision('even_money' if player_bj else 'insurance')
            self.update_display(); return
        if player_bj:
            hand['status']='blackjack'; self.render_cards(); self.update_display()
            self._queue(350,self._start_dealer_turn); return
        self.canvas.itemconfigure(self.phase_text,text=self.PHASE_PLAYING); self.update_display()

    def _auto_play_player_for_dealer_main(self):
        # BANKER direction: automated player hand uses H17 logic — hit below 17,
        # hit soft 17, stand hard 17 and every 18+ total.
        if not self.round_active or self.round_main_bet_side != 'dealer':
            return
        hand = self.hands[0] if self.hands else None
        if not hand or self.animation_running:
            return
        total, soft = BlackjackEngine.hand_value(hand['cards'])
        if total > 21:
            hand['status']='bust'; hand['result']='自动爆牌'
            self.render_cards(); self.update_display()
            self._queue(180, self._start_dealer_turn)
            return
        if total == 21 or total > 17 or (total == 17 and not soft):
            hand['status']='stood'; hand['result']=f'自动停牌 {total}'
            self.render_cards(); self.update_display()
            self._queue(180, self._start_dealer_turn)
            return

        self.animation_running=True
        self.update_display(); self._raise_visible_bottom_controls(True)
        def after():
            self.animation_running=False
            total2, soft2 = BlackjackEngine.hand_value(hand['cards'])
            if total2 > 21:
                hand['status']='bust'; hand['result']='自动爆牌'
            elif total2 == 21 or total2 > 17 or (total2 == 17 and not soft2):
                hand['status']='stood'; hand['result']=f'自动停牌 {total2}'
            self.render_cards(); self.update_display()
            if hand['status'] == 'active':
                self._queue(160, self._auto_play_player_for_dealer_main)
            else:
                self._queue(180, self._start_dealer_turn)
        self._deal_player_card_animated(0, on_complete=after)

    def _deal_player_card_animated(self, hand_index, on_complete=None):
        if not (0 <= hand_index < len(self.hands)):
            if callable(on_complete): on_complete()
            return
        hand=self.hands[hand_index]
        card=self.draw_round_card(); card_index=len(hand['cards']); hand['cards'].append(card)
        tx,ty=self._player_card_target(hand_index,card_index)
        def done():
            self.canvas.delete('round_animation_card')
            self._maybe_settle_crazy7(); self.render_cards(); self.update_display()
            if callable(on_complete): on_complete()
        self._animate_card_from_shoe(card,tx,ty,on_complete=done,flip=True,
            tag='round_animation_card', rotation=90 if hand.get('double_card_index')==card_index else 0)

    def _deal_dealer_card_animated(self, on_complete=None):
        card=self.draw_round_card(); card_index=len(self.dealer_cards); self.dealer_cards.append(card)
        tx,ty=self._dealer_card_target(card_index)
        def done():
            self.canvas.delete('round_animation_card')
            self._maybe_settle_crazy7()
            self._update_fortune17_progress()
            self.render_cards(); self.update_display()
            if callable(on_complete): on_complete()
        self._animate_card_from_shoe(card,tx,ty,on_complete=done,flip=True,tag='round_animation_card')

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
        if not hand or hand['status'] != 'active' or len(hand['cards']) != 2:
            return False
        if len(self.hands) >= self.MAX_HANDS or self.split_actions >= self.MAX_SPLIT_ACTIONS:
            return False
        if self.balance + 1e-9 < hand['base_bet']:
            return False
        return BlackjackEngine.split_value(hand['cards'][0]) == BlackjackEngine.split_value(hand['cards'][1])

    def can_surrender(self, hand):
        if not hand or hand['status'] != 'active' or not hand['cards']:
            return False
        if BlackjackEngine.is_blackjack(hand['cards']) and not hand.get('from_split', False):
            return False
        return BlackjackEngine.hand_value(hand['cards'])[0] <= 21

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
        hand['double_card_index'] = len(hand['cards'])
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
        """Move every canvas item carrying *tag*; supports image and fallback cards."""
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
        """Animate tagged canvas objects between exact top-left positions."""
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
                y = (start[1] + (end[1] - start[1]) * eased
                     - 4.0 * lift * eased * (1.0 - eased))
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
        if not self.can_split(hand) or self.animation_running:
            return

        # Lock all decisions before the first animation frame.
        self.animation_running = True
        for button in self.action_buttons.values():
            self._set_button(button, False)
        self._raise_visible_bottom_controls(True)

        add = hand['base_bet']
        self.balance -= add
        self.split_actions += 1
        self.save_balance()

        first, second = hand['cards'][0], hand['cards'][1]
        is_aces = first[1] == 'A' and second[1] == 'A'
        left = self.new_hand(
            cards=[first], base_bet=hand['base_bet'],
            contains_original=hand.get('contains_original', False),
            from_split=True, split_aces=is_aces, needs_split_draw=True)
        right = self.new_hand(
            cards=[second], base_bet=hand['base_bet'],
            contains_original=False, from_split=True,
            split_aces=is_aces, needs_split_draw=True)

        # The Classic animation reserves both hands before its first frame.
        self.update_display()
        self._animate_split_sequence(self.active_hand_index, left, right)

    @staticmethod
    @lru_cache(maxsize=None)
    def _infinite_player_distribution(total, soft):
        """Infinite-deck player outcome under normal Hit<17 / Stand>=17."""
        total=int(total); soft=bool(soft)
        if total>21: return (0,0,0,0,0,1.0)
        if total>=17:
            arr=[0.0]*6
            if 17<=total<=21: arr[total-17]=1.0
            else: arr[5]=1.0
            return tuple(arr)
        outcomes=[(11,1/13)]+[(v,1/13) for v in range(2,10)]+[(10,4/13)]
        result=[0.0]*6
        for value,prob in outcomes:
            raw=total+value; high=(1 if soft else 0)+(1 if value==11 else 0)
            while raw>21 and high>0: raw-=10; high-=1
            sub=BubbleBlackjackGame._infinite_player_distribution(raw,high>0)
            for i,p in enumerate(sub): result[i]+=prob*p
        return tuple(result)

    @staticmethod
    @lru_cache(maxsize=None)
    def _infinite_dealer_distribution(total, soft):
        """Infinite-deck H17 dealer distribution: hard 17..21,bust; soft 17 hits."""
        total=int(total); soft=bool(soft)
        if total>21: return (0,0,0,0,0,1.0)
        if total>17 or (total==17 and not soft):
            arr=[0.0]*6; arr[total-17 if total<=21 else 5]=1.0; return tuple(arr)
        outcomes=[(11,1/13)]+[(v,1/13) for v in range(2,10)]+[(10,4/13)]
        result=[0.0]*6
        for value,prob in outcomes:
            raw=total+value; high=(1 if soft else 0)+(1 if value==11 else 0)
            while raw>21 and high>0: raw-=10; high-=1
            sub=BubbleBlackjackGame._infinite_dealer_distribution(raw,high>0)
            for i,p in enumerate(sub): result[i]+=prob*p
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
        """Return (max win probability, bust probability) using Hit/Stand only.

        This deliberately ignores the real shoe.  At every future player state it
        compares standing now with taking another card and follows whichever path
        produces the higher probability of an outright win.  Pushes are not wins.
        """
        total=int(total); soft=bool(soft); dealer_total=int(dealer_total); dealer_soft=bool(dealer_soft)
        if total > 21:
            return 0.0, 1.0
        ddist = BubbleBlackjackGame._infinite_dealer_distribution(dealer_total, dealer_soft)
        stand_win = ddist[5] + sum(ddist[:max(0, total - 17)])
        if total >= 21:
            return max(0.0, min(1.0, stand_win)), 0.0

        outcomes=((11,1/13),)+tuple((v,1/13) for v in range(2,10))+((10,4/13),)
        hit_win=0.0; hit_bust=0.0
        for value,prob in outcomes:
            raw=total+value
            high=(1 if soft else 0)+(1 if value==11 else 0)
            while raw>21 and high>0:
                raw-=10; high-=1
            if raw>21:
                hit_bust += prob
                continue
            child_win,child_bust=BubbleBlackjackGame._infinite_optimal_hit_stand(
                raw, high>0, dealer_total, dealer_soft)
            hit_win += prob*child_win
            hit_bust += prob*child_bust

        if hit_win > stand_win + 1e-12:
            return max(0.0,min(1.0,hit_win)), max(0.0,min(1.0,hit_bust))
        return max(0.0,min(1.0,stand_win)), 0.0

    def surrender_offer(self, hand):
        """Return 90% of the current valuation, rounded to cents."""
        if not self.can_surrender(hand) or not self.dealer_cards:
            return 0.0,0.0,1.0,0.0
        ptotal,psoft=BlackjackEngine.hand_value(hand['cards'])
        dtotal,dsoft=self._upcard_state(self.dealer_cards[0])
        win,bust=self._infinite_optimal_hit_stand(ptotal,psoft,dtotal,dsoft)
        credit = round((self.hand_stake(hand)*win*2.0) * self.CASHOUT_FACTOR, 2)
        return credit,win,bust,0.0

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

    @staticmethod
    def _pair_kind(cards):
        if len(cards) < 2 or cards[0][1] != cards[1][1]:
            return None
        return 'perfect' if cards[0][0] == cards[1][0] else 'pair'

    @classmethod
    def _super_pair_result(cls, player_cards, dealer_cards):
        """超级对子: both pairs 50:1; one perfect pair 5:1; one pair 3:1."""
        if len(player_cards) < 2 or len(dealer_cards) < 2:
            return (None, '资料不足')
        pk = cls._pair_kind(player_cards[:2])
        dk = cls._pair_kind(dealer_cards[:2])
        if pk and dk:
            return (50, '双方首2张为对子')
        if pk == 'perfect' or dk == 'perfect':
            return (5, '一方完美对子')
        if pk or dk:
            return (3, '一方对子')
        return (None, '未中')

    @classmethod
    def _super_tie_result(cls, player_cards, dealer_cards, dealer_main=False):
        """超级平局 final-total tiers; both-bust tier exists only on BANKER main."""
        if not player_cards or not dealer_cards:
            return (None, '资料不足')
        player_total, _ = BlackjackEngine.hand_value(player_cards)
        dealer_total, _ = BlackjackEngine.hand_value(dealer_cards)
        player_bj = BlackjackEngine.is_blackjack(player_cards)
        dealer_bj = BlackjackEngine.is_blackjack(dealer_cards)
        if player_bj and dealer_bj:
            return (50, '双方黑杰克平局')
        # Natural two-card 黑杰克 outranks an ordinary multi-card 21. If exactly
        # one side has a natural 黑杰克, Super Tie loses rather than treating the
        # equal numeric total as any kind of tie.
        if player_total == 21 and dealer_total == 21 and (player_bj != dealer_bj):
            return (None, '黑杰克与普通21点：超级平局输')
        # The 15:1 tier applies only when both 21-point hands are non-Blackjack.
        if player_total == 21 and dealer_total == 21 and not player_bj and not dealer_bj:
            return (15, '双方普通21点平局')
        if player_total == 20 and dealer_total == 20:
            return (8, '20点平局')
        if player_total == dealer_total and 17 <= player_total <= 19:
            return (3, f'{player_total}点平局')
        if dealer_main and player_total > 21 and dealer_total > 21:
            return (1, '双方都爆牌')
        return (None, '未中')

    @staticmethod
    def _nuclear_bust_result(player_cards, dealer_cards):
        """核爆!: BANKER-main only, paid when both sides bust by combined card count."""
        if not player_cards or not dealer_cards:
            return (None, '资料不足')
        player_total, _ = BlackjackEngine.hand_value(player_cards)
        dealer_total, _ = BlackjackEngine.hand_value(dealer_cards)
        if player_total <= 21 or dealer_total <= 21:
            return (None, '未同时爆牌')
        count = len(player_cards) + len(dealer_cards)
        if count >= 12:
            odds = 250
        elif count == 11:
            odds = 150
        elif count == 10:
            odds = 100
        elif count == 9:
            odds = 30
        elif count == 8:
            odds = 15
        else:  # minimum possible combined bust is normally 6 cards
            odds = 5
        return (odds, f'双方共{count}张爆牌')

    def _settle_initial_side_bets(self):
        if not self.hands or len(self.hands[0]['cards']) < 2 or not self.dealer_cards:
            return
        p0, p1 = self.hands[0]['cards'][:2]
        dealer = self.dealer_cards[0]

        trio = [p0, p1, dealer]
        suits_same = len({card[0] for card in trio}) == 1
        ranks_same = len({card[1] for card in trio}) == 1
        straight = self._is_three_card_straight(trio)

        # 21+3 remains exactly the Classic schedule.
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
        self._credit_side_bet('21+3', *result)

        # Hot 21 remains exactly the Classic schedule.
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
        self._credit_side_bet('Hot 21', *result)

        # Super Pair needs the dealer's SECOND card and Super Tie needs final totals,
        # so both intentionally remain unresolved here.
        if self.side_bet_results.get('Crazy 7') == '输':
            self._collect_losing_side_bet_upward('Crazy 7')

        self.save_balance()

    def _settle_super_pair_side_bet(self):
        key = 'Super Pair'
        if key in self.side_bet_results:
            return
        if not self.hands or len(self.hands[0].get('cards', ())) < 2 or len(self.dealer_cards) < 2:
            return
        player_opening = self.round_initial_player_cards or self.hands[0]['cards'][:2]
        self._credit_side_bet(key, *self._super_pair_result(
            player_opening[:2], self.dealer_cards[:2]))
        self.save_balance()

    def _settle_super_tie_side_bet(self):
        key = 'Super Tie'
        if key in self.side_bet_results:
            return
        if not self.hands or not self.dealer_cards:
            return
        # If PLAYER main was split, the side bet follows hand #1's final result;
        # BANKER main never splits, so its comparison is unambiguous.
        player_cards = self.hands[0].get('cards', ())
        self._credit_side_bet(key, *self._super_tie_result(
            player_cards, self.dealer_cards,
            dealer_main=(self.round_main_bet_side == 'dealer')))
        self.save_balance()

    def _maybe_settle_crazy7(self):
        """Synchronise Crazy 7 progressively from round cards 0 -> 2 -> 3.

        Card 0 decides whether the bet is already dead.  If it is a 7, show the
        currently secured 5:1 tier while waiting for card 2.  If card 2 is not a
        7, 5:1 is final; if card 2 is a 7, show the secured 25:1/150:1 tier while
        waiting for card 3.  Card 3 then performs the final odds synchronisation:
        another 7 upgrades to 500:1/2000:1, otherwise the card-2 tier remains.
        Provisional tiers only update the pointed odds marker; money is credited
        exactly once when the tier becomes final.
        """
        key = 'Crazy 7'
        if self.round_main_bet_side == 'dealer':
            # The same physical spot becomes 富豪17 in BANKER-main rounds. Its
            # progress is driven only by the dealer hand, never by player cards.
            self._update_fortune17_progress()
            return
        if self.round_main_bet_side != 'player':
            return
        if key in self.side_bet_results:
            return
        seq = self.round_deal_sequence
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

    def _update_fortune17_progress(self):
        """Update the shared 疯狂7/富豪17 odds marker during BANKER-main play.

        富豪17 observes DEALER cards only. Once the dealer has ever shown soft 17,
        15:1 is secured and displayed immediately. If the dealer later finishes on
        hard 17, the secured tier upgrades to 30:1. A final hard 17 without any
        earlier soft 17 is the 2:1 tier. Money is credited only at final settlement.
        """
        key = 'Crazy 7'
        if self.round_main_bet_side != 'dealer' or key in self.side_bet_results:
            return
        if len(self.dealer_cards) < 2:
            return

        total, soft = BlackjackEngine.hand_value(self.dealer_cards)
        if total == 17 and soft:
            self.dealer_had_soft_17 = True

        if self.dealer_had_soft_17:
            if total == 17 and not soft:
                odds, label = 30.0, '曾有软17，最终硬17'
            else:
                odds, label = 15.0, '庄家曾经有软17'
            self.side_bet_hit_odds[key] = odds
            self.side_bet_hit_labels[key] = label
        elif total == 17 and not soft:
            # H17 means a visible hard 17 is already the dealer's final hand, so
            # the 2:1 tier can be displayed as soon as that card is shown.
            self.side_bet_hit_odds[key] = 2.0
            self.side_bet_hit_labels[key] = '庄家最终硬17'
        else:
            self.side_bet_hit_odds.pop(key, None)
            self.side_bet_hit_labels.pop(key, None)

    def _settle_fortune17_side_bet(self):
        """Finalise 富豪17 for BANKER-main using only the dealer's hand path."""
        key = 'Crazy 7'
        if self.round_main_bet_side != 'dealer' or key in self.side_bet_results:
            return
        if len(self.dealer_cards) < 2:
            return

        self._update_fortune17_progress()
        total, soft = BlackjackEngine.hand_value(self.dealer_cards)
        final_hard_17 = (total == 17 and not soft)

        if self.dealer_had_soft_17 and final_hard_17:
            result = (30, '曾有软17并最终硬17')
        elif self.dealer_had_soft_17:
            result = (15, '曾有软17但最终不是硬17')
        elif final_hard_17:
            result = (2, '庄家最终硬17')
        else:
            result = (None, '庄家没有符合富豪17条件')
            self.side_bet_hit_odds.pop(key, None)
            self.side_bet_hit_labels.pop(key, None)

        self._credit_side_bet(key, *result)
        self.save_balance()

    def _settle_bust_side_bet(self):
        key = 'Bust!'
        if key in self.side_bet_results:
            return

        if self.round_main_bet_side == 'dealer':
            if not self.hands:
                return
            result = self._nuclear_bust_result(self.hands[0].get('cards', ()), self.dealer_cards)
            self._credit_side_bet(key, *result)
            self.save_balance()
            return

        # PLAYER main keeps Classic 爆牌! unchanged: dealer bust card-count schedule.
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

    @classmethod
    def _banker_main_result(cls, player_cards, dealer_cards):
        """Return (state, profit_odds, label) for 主注-庄家.

        Point comparisons apply when neither side is bust; the explicit player-bust
        rules then handle dealer 17 versus dealer 18-21, making those requested
        tiers reachable without conflicting with the raw numeric bust total.
        """
        player_total, _ = BlackjackEngine.hand_value(player_cards)
        dealer_total, _ = BlackjackEngine.hand_value(dealer_cards)
        player_bj = BlackjackEngine.is_blackjack(player_cards)
        dealer_bj = BlackjackEngine.is_blackjack(dealer_cards)
        player_bust = player_total > 21
        dealer_bust = dealer_total > 21

        if player_bj and not dealer_bj:
            return ('lose', 0.0, '玩家Blackjack，庄家不是：输')
        if player_bj and dealer_bj:
            return ('push', 0.0, '双方Blackjack：平局')
        if dealer_bj:
            return ('win', 1.5, '庄家Blackjack 3:2')
        if dealer_bust and not player_bust:
            return ('lose', 0.0, '庄家爆牌、玩家未爆：输')

        if not player_bust and not dealer_bust:
            if dealer_total == player_total:
                return ('push', 0.0, f'{dealer_total}点平局')
            if dealer_total < player_total:
                return ('lose', 0.0, f'庄家{dealer_total} < 玩家{player_total}：输')
            return ('win', 1.0, f'庄家{dealer_total} > 玩家{player_total}：赢1:1')

        if player_bust and not dealer_bust:
            if 18 <= dealer_total <= 21:
                return ('win', 1.0, f'玩家爆牌；庄家{dealer_total}：赢1:1')
            if dealer_total == 17:
                return ('push', 0.0, '玩家爆牌；庄家17：平局')

        if player_bust and dealer_bust:
            return ('push', 0.0, '双方同时爆牌：平局')

        return ('lose', 0.0, '未满足庄家主注赢/和条件')

    def _needs_full_dealer_for_side_bets(self):
        return any(float(self.round_side_bets.get(key, 0.0)) > 0.0
                   for key in ('Super Pair', 'Super Tie', 'Bust!'))

    # -------------------------------------------------------------- dealer phase
    def _advance_hand(self):
        if not self.round_active: return
        for idx in range(self.active_hand_index+1,len(self.hands)):
            if self.hands[idx]['status']=='active':
                self.active_hand_index=idx; self.render_cards(); self.update_display()
                self._prepare_active_split_hand()
                return
        self._start_dealer_turn()

    def _has_bust_wager(self):
        return float(self.round_side_bets.get('Bust!', 0.0)) > 0.0

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
        if len(self.hands) != 1:
            return False
        hand = self.hands[0]
        return bool(
            not hand.get('from_split', False)
            and BlackjackEngine.is_blackjack(hand.get('cards', ()))
            and hand.get('status') in ('blackjack', 'active')
        )

    def _finish_even_money_without_dealer_card(self):
        if not self.round_active or self._needs_full_dealer_for_side_bets():
            return
        # The one-card dealer cannot be bust; record Bust! as a non-hit even when
        # there was no wager, matching the existing settlement bookkeeping.
        self._settle_bust_side_bet()
        self.last_result_lines.append('Even Money 1:1；庄家不抽第二张牌')
        self._finish_round(dealer_bj=False)

    def _resolve_finished_hands_after_insurance_probe(self):
        """Resolve insurance after exactly one dealer draw, without OBO overrides."""
        dealer_bj = BlackjackEngine.is_blackjack(self.dealer_cards[:2])
        self._maybe_settle_crazy7()
        self._settle_super_pair_side_bet()
        self._settle_bust_side_bet()
        self._settle_super_tie_side_bet()
        lines = ['保险判定：庄家只开第二张牌']

        if self.insurance_bet > 0.0:
            if dealer_bj:
                credit = self.insurance_bet * (1.0 + self.INSURANCE_PROFIT)
                self.balance += credit
                self.insurance_return_amount = credit
                self.insurance_result = f'保险胜 +{self.format_money(credit - self.insurance_bet)}'
            else:
                self.insurance_return_amount = 0.0
                self.insurance_result = f'保险输 -{self.format_money(self.insurance_bet)}'
            lines.append(self.insurance_result)

        for idx, hand in enumerate(self.hands):
            if hand.get('status') == 'surrendered':
                lines.append(f'手{idx + 1}：{hand["result"]}')
                continue
            stake = self.hand_stake(hand)
            total, _ = BlackjackEngine.hand_value(hand.get('cards', ()))
            if hand.get('status') == 'bust' or total > 21:
                hand['settlement'] = 'lose'
                hand['base_settlement'] = 'lose'
                hand['double_settlement'] = 'lose' if hand.get('double_added', 0.0) > 0 else None
                hand['settlement_return'] = 0.0
                hand['result'] = f'爆牌 -{self.format_money(stake)}'
                lines.append(f'手{idx + 1}：爆牌')

        self.last_result_lines.extend(lines)
        self._finish_round(dealer_bj=dealer_bj, phase_text='本局结算完成')

    def _start_dealer_turn(self):
        if not self.round_active or self.animation_running:
            return

        banker_mode = self.round_main_bet_side == 'dealer'
        bust_wager = self._has_bust_wager()
        full_side_resolution = self._needs_full_dealer_for_side_bets()
        all_dead = self._all_hands_bust_or_surrendered()
        natural = self._single_natural_blackjack()
        up_rank = self.dealer_cards[0][1] if self.dealer_cards else None

        # PLAYER direction preserves Classic shortcuts only when no new side bet
        # requires the dealer's second/final cards. BANKER direction always completes
        # the dealer hand because its own settlement depends on the dealer total.
        if not banker_mode and not full_side_resolution:
            if all_dead and self.insurance_bet <= 0.0:
                self.animation_running = True
                self.canvas.itemconfigure(self.phase_text, text=self.PHASE_SETTLING)
                self.render_cards(); self.update_display()
                self._queue(220, self._resolve_normal_round)
                return
            if natural and up_rank not in ('A', '10', 'J', 'Q', 'K'):
                self.animation_running = True
                self.canvas.itemconfigure(self.phase_text, text=self.PHASE_SETTLING)
                self.render_cards(); self.update_display()
                self._queue(220, self._resolve_normal_round)
                return

        self.dealer_phase_active=True
        self.animation_running=True
        self.canvas.itemconfigure(self.phase_text,text=self.PHASE_PLAYING)
        self.render_cards(); self.update_display()

        def after_second():
            self._settle_super_pair_side_bet()
            dealer_bj = BlackjackEngine.is_blackjack(self.dealer_cards[:2])

            if banker_mode:
                if dealer_bj:
                    self._queue(220, self._resolve_banker_main_round)
                else:
                    self._queue(220, self._dealer_draw_until_done)
                return

            if not full_side_resolution:
                if all_dead and self.insurance_bet > 0.0:
                    self._queue(260, self._resolve_finished_hands_after_insurance_probe)
                    return
                if natural:
                    self._queue(260, self._resolve_dealer_blackjack if dealer_bj else self._resolve_normal_round)
                    return
            if dealer_bj:
                self._queue(260,self._resolve_dealer_blackjack)
            else:
                self._queue(260,self._dealer_draw_until_done)
        self._deal_dealer_card_animated(on_complete=after_second)

    def _dealer_draw_until_done(self):
        total, soft = BlackjackEngine.hand_value(self.dealer_cards)
        if total < 17 or (total == 17 and soft):
            self.canvas.itemconfigure(self.phase_text,text=self.PHASE_PLAYING)
            self._deal_dealer_card_animated(on_complete=lambda:self._queue(180,self._dealer_draw_until_done))
            return
        if self.round_main_bet_side == 'dealer':
            self._queue(260,self._resolve_banker_main_round)
        else:
            self._queue(260,self._resolve_normal_round)

    def _resolve_banker_main_round(self):
        """Settle 主注-庄家 exactly once after the dealer hand is final."""
        if not self.hands:
            return
        self._maybe_settle_crazy7()
        self._settle_fortune17_side_bet()
        self._settle_super_pair_side_bet()
        self._settle_bust_side_bet()
        self._settle_super_tie_side_bet()

        hand = self.hands[0]
        stake = float(self.round_original_bet)
        state, profit_odds, label = self._banker_main_result(hand.get('cards', ()), self.dealer_cards)
        hand['double_added'] = 0.0
        hand['double_settlement'] = None
        hand['settlement'] = state
        hand['base_settlement'] = state

        if state == 'win':
            credit = stake * (1.0 + float(profit_odds))
            self.balance += credit
            hand['settlement_return'] = credit
            hand['result'] = f'{label} +{self.format_money(credit - stake)}'
        elif state == 'push':
            self.balance += stake
            hand['settlement_return'] = stake
            hand['result'] = label
        else:
            hand['settlement_return'] = 0.0
            hand['result'] = f'{label} -{self.format_money(stake)}'

        player_total, _ = BlackjackEngine.hand_value(hand.get('cards', ()))
        dealer_total, _ = BlackjackEngine.hand_value(self.dealer_cards)
        self.banker_17_main_push = bool(
            state == 'push' and player_total > 21 and dealer_total == 17
        )
        self.banker_double_bust_main_push = bool(
            state == 'push' and player_total > 21 and dealer_total > 21
        )
        self.last_result_lines.extend([
            f'主注-庄家：{label}',
            f'玩家 {player_total}' + (' 爆牌' if player_total > 21 else ''),
            f'庄家 {dealer_total}' + (' 爆牌' if dealer_total > 21 else ''),
        ])
        self._finish_round(dealer_bj=BlackjackEngine.is_blackjack(self.dealer_cards))

    def _resolve_dealer_blackjack(self):
        dealer_bj = True
        self._maybe_settle_crazy7()
        self._settle_super_pair_side_bet()
        self._settle_bust_side_bet()
        self._settle_super_tie_side_bet()
        lines = ['庄家 Blackjack']

        if self.insurance_bet > 0:
            insurance_credit = self.insurance_bet * (1.0 + self.INSURANCE_PROFIT)
            self.balance += insurance_credit
            self.insurance_return_amount = insurance_credit
            self.insurance_result = f'保险胜 +{self.format_money(insurance_credit - self.insurance_bet)}'
            lines.append(f'保险胜：{self.format_money(insurance_credit)}返还')
        elif self.insurance_result:
            self.insurance_result = '未购买保险'

        for idx, hand in enumerate(self.hands):
            status = hand['status']
            if status in ('surrendered', 'even_money'):
                lines.append(f'手{idx + 1}：{hand["result"]}')
                continue

            stake = self.hand_stake(hand)
            split_two_card_21 = bool(
                hand.get('from_split', False)
                and len(hand.get('cards', ())) == 2
                and BlackjackEngine.hand_value(hand['cards'])[0] == 21
            )
            natural = (not hand.get('from_split', False)
                       and BlackjackEngine.is_blackjack(hand['cards']))
            if natural and hand.get('contains_original', False):
                # Only an unsplit two-card 21 is Blackjack. Dealer BJ pushes it.
                self.balance += hand['base_bet']
                hand['settlement'] = 'push'
                hand['base_settlement'] = 'push'
                hand['double_settlement'] = None
                hand['settlement_return'] = hand['base_bet']
                hand['result'] = 'Blackjack 和局'
                lines.append(f'手{idx + 1}：Blackjack Push')
                continue

            if hand.get('contains_original', False):
                refund = max(0.0, stake - hand['base_bet'])
                # ENHC/OBO: the Original Bet loses. Any double added after the
                # original wager is supplemental and therefore returned.
                if refund > 0:
                    self.balance += refund
                hand['settlement'] = 'lose'
                hand['base_settlement'] = 'lose'
                hand['double_settlement'] = 'refund' if hand.get('double_added', 0.0) > 0 else None
                hand['settlement_return'] = refund
                prefix = '分牌21非Blackjack；' if split_two_card_21 else ''
                hand['result'] = f'{prefix}庄BJ：Original Bet输，额外退 {self.format_money(refund)}'
                lines.append(f'手{idx + 1}：{prefix}Original Bet输；额外退 {self.format_money(refund)}')
            else:
                # This hand is a supplemental split hand. It loses to dealer
                # Blackjack as a hand result (including split two-card 21), but
                # OBO returns the supplemental split/double money.
                self.balance += stake
                hand['settlement'] = 'refund'
                hand['base_settlement'] = 'refund'
                hand['double_settlement'] = 'refund' if hand.get('double_added', 0.0) > 0 else None
                hand['settlement_return'] = stake
                prefix = '分牌21非Blackjack；庄BJ判负；' if split_two_card_21 else ''
                hand['result'] = f'{prefix}OBO退 {self.format_money(stake)}'
                lines.append(f'手{idx + 1}：{prefix}分牌/加倍本金退 {self.format_money(stake)}')

        self.last_result_lines.extend(lines)
        self._finish_round(dealer_bj=dealer_bj)

    def _resolve_normal_round(self):
        self._maybe_settle_crazy7()
        self._settle_super_pair_side_bet()
        self._settle_bust_side_bet()
        self._settle_super_tie_side_bet()
        dealer_total, _ = BlackjackEngine.hand_value(self.dealer_cards)
        dealer_bust = dealer_total > 21
        lines = [f'庄家 {dealer_total}' + (' 爆牌' if dealer_bust else '')]

        if self.insurance_bet > 0:
            self.insurance_return_amount = 0.0
            self.insurance_result = f'保险输 -{self.format_money(self.insurance_bet)}'
            lines.append(self.insurance_result)

        for idx, hand in enumerate(self.hands):
            if hand['status'] in ('surrendered', 'even_money'):
                lines.append(f'手{idx + 1}：{hand["result"]}')
                continue

            stake = self.hand_stake(hand)
            player_total, _ = BlackjackEngine.hand_value(hand['cards'])
            natural = (not hand.get('from_split', False)
                       and BlackjackEngine.is_blackjack(hand['cards']))

            split_two_card_21 = bool(
                hand.get('from_split', False)
                and len(hand.get('cards', ())) == 2
                and player_total == 21
            )
            if hand['status'] == 'bust' or player_total > 21:
                hand['settlement'] = 'lose'
                hand['base_settlement'] = 'lose'
                hand['double_settlement'] = 'lose' if hand.get('double_added', 0.0) > 0 else None
                hand['settlement_return'] = 0.0
                hand['result'] = f'爆牌 -{self.format_money(stake)}'
                lines.append(f'手{idx + 1}：爆牌')
            elif natural:
                credit = stake * (1.0 + self.BLACKJACK_PROFIT)
                self.balance += credit
                hand['settlement'] = 'win'
                hand['base_settlement'] = 'win'
                hand['double_settlement'] = 'win' if hand.get('double_added', 0.0) > 0 else None
                hand['settlement_return'] = credit
                hand['result'] = f'Blackjack 3:2 +{self.format_money(credit - stake)}'
                lines.append(f'手{idx + 1}：Blackjack 3:2')
            elif dealer_bust or player_total > dealer_total:
                # A two-card 21 created by a split is deliberately NOT Blackjack:
                # it pays the ordinary 1:1 main-game win.
                credit = stake * 2.0
                self.balance += credit
                hand['settlement'] = 'win'
                hand['base_settlement'] = 'win'
                hand['double_settlement'] = 'win' if hand.get('double_added', 0.0) > 0 else None
                hand['settlement_return'] = credit
                if split_two_card_21:
                    hand['result'] = f'分牌21 胜1:1 +{self.format_money(stake)}'
                    lines.append(f'手{idx + 1}：分牌21 胜1:1')
                else:
                    hand['result'] = f'胜 +{self.format_money(stake)}'
                    lines.append(f'手{idx + 1}：胜 {player_total}')
            elif player_total == dealer_total:
                self.balance += stake
                hand['settlement'] = 'push'
                hand['base_settlement'] = 'push'
                hand['double_settlement'] = 'push' if hand.get('double_added', 0.0) > 0 else None
                hand['settlement_return'] = stake
                hand['result'] = '分牌21 和局 Push' if split_two_card_21 else '和局 Push'
                lines.append(f'手{idx + 1}：{"分牌21 " if split_two_card_21 else ""}Push {player_total}')
            else:
                hand['settlement'] = 'lose'
                hand['base_settlement'] = 'lose'
                hand['double_settlement'] = 'lose' if hand.get('double_added', 0.0) > 0 else None
                hand['settlement_return'] = 0.0
                hand['result'] = f'输 -{self.format_money(stake)}'
                lines.append(f'手{idx + 1}：输 {player_total}')

        self.last_result_lines.extend(lines)
        self._finish_round(dealer_bj=False)

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
            for key in self.SIDE_BET_KEYS
        )
        returned_total += max(0.0, float(self.insurance_return_amount))
        return returned_total

    def _finish_round(self, dealer_bj=False, phase_text=None):
        # Payouts are already credited by the original game evaluators. These
        # motions only display principal and profit; they never change balance.
        self.animation_running = False
        self.save_balance()
        self.last_win_amount = self._calculate_last_win_amount()
        self.show_last_win = True
        self.insurance_resolved = True
        self.canvas.itemconfigure(self.phase_text, text=self.PHASE_SETTLING)
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
        self._fade_banker_push_notice(
            self.banker_17_main_push or self.banker_double_bust_main_push)
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
        self._fade_banker_push_notice(False)
        self._set_rules_strip_visible(False)

        returning_side = self.round_main_bet_side
        self.settlement_visual_stage = None
        self.pending_profit_chips = set()
        self._opening_wager_animation = False
        self.insurance_resolved = False
        self.round_active=False; self.round_original_bet=0.0
        self.round_main_bet_side=None
        # Keep the completed round's direction selected while the table returns to
        # HOME. After that movement finishes, _animate_main_deselection performs the
        # requested 0.20 s central-main -> two-choice reverse animation.
        self.main_bet_side=returning_side if returning_side in ('player','dealer') else None
        self._main_selection_animation_running=False
        self.round_side_bets={key:0.0 for key in self.SIDE_BET_KEYS}
        self.side_bet_results={}; self.side_bet_return_amounts={}
        self.side_bet_hit_odds={}; self.side_bet_hit_labels={}
        self.side_bet_early_collected=set()
        self.flash_winning_side_bets=set(); self.flash_main_bet=False; self.flash_main_push_only=False
        self.banker_17_main_push=False
        self.banker_double_bust_main_push=False
        self.flash_winning_hand_indices=set(); self.flash_insurance_rule=False
        self.settlement_running=False; self.settlement_flash_step=0; self.flash_mode=None
        self.dealer_phase_active=False
        self.round_deal_sequence=[]; self.round_initial_player_cards=[]; self.dealer_had_soft_17=False
        self.insurance_bet=0.0; self.insurance_result=''
        self.insurance_return_amount=0.0; self.insurance_chip_visible=False; self.ace_decision_mode=None
        self.hands=[]; self.dealer_cards=[]; self.active_hand_index=0; self.split_actions=0

        # Do not permit a fresh click until both the board return and the reverse MAIN
        # selector animation are complete.
        self.accept_bets=False

        def finish_reset():
            self._refresh_premiere_bet_labels()
            self._set_round_control_visibility(False)
            self.canvas.itemconfigure('chip_selector',state='normal')
            self._raise_visible_bottom_controls(False)
            self.select_chip(self.selected_chip)
            self.save_runtime_store(burn_complete=True)
            self.accept_bets=True
            self.canvas.itemconfigure(self.phase_text,text=self.PHASE_BETTING)
            self.update_display()
            self._set_round_control_visibility(False)
            self._raise_visible_bottom_controls(False)

        def after_layout():
            if returning_side in ('player', 'dealer'):
                self._animate_main_deselection(returning_side, on_complete=finish_reset)
            else:
                self.main_bet_side=None
                finish_reset()

        self._animate_betting_station(False,on_complete=after_layout)

    def _hand_short_status(self, hand):
        mapping = {
            'bust': '爆',
            'blackjack': 'BJ',
            'even_money': 'Even',
        }
        return mapping.get(hand.get('status'), '')

    def update_display(self):
        if self._closing: return
        self.canvas.itemconfigure(self.balance_text,text=f'余额: {self.format_money(self.balance)}')
        if self.show_last_win:
            self.canvas.itemconfigure(
                self.total_bet_text,
                text=f'上局获胜: {self.format_money(self.last_win_amount)}')
        elif self.round_active:
            round_bet=(sum(self.hand_stake(h) for h in self.hands)
                       + self.insurance_bet + sum(self.round_side_bets.values()))
            self.canvas.itemconfigure(
                self.total_bet_text,
                text=f'本局下注: ${float(round_bet):,.0f}')
        else:
            pending=self.current_bet+sum(self.current_side_bets.values())
            self.canvas.itemconfigure(
                self.total_bet_text,
                text=f'本局下注: ${float(pending):,.0f}')
        self.update_bet_chips(); self._render_insurance_chip()
        self._draw_side_bet_progress_badges()

        can_bet=(self.accept_bets and not self.round_active and not self.animation_running
                 and not self.settlement_running and not self._main_selection_animation_running)
        pending_any=self.current_bet>0 or any(v>0 for v in self.current_side_bets.values())
        player_memory = self.repeat_bet_memory.get('player', {})
        dealer_memory = self.repeat_bet_memory.get('dealer', {})
        player_repeat_ready = float(player_memory.get('main', 0.0)) >= self.MIN_BET
        dealer_repeat_ready = float(dealer_memory.get('main', 0.0)) >= self.MIN_BET
        no_chip_flying=self.bet_chip_animation_count==0
        self._set_button(self.clear_button,can_bet and pending_any and no_chip_flying)
        self._set_button(
            self.repeat_player_button,
            can_bet and player_repeat_ready and no_chip_flying)
        self._set_button(
            self.repeat_dealer_button,
            can_bet and dealer_repeat_ready and no_chip_flying)
        self._set_button(self.deal_button,can_bet and no_chip_flying and self.main_bet_side in ('player','dealer') and self.current_bet>=self.MIN_BET)

        if self.ace_decision_mode=='insurance':
            self._set_button(self.decision_buttons.get('accept'),
                             self.balance+1e-9>=self.round_original_bet/2.0,'购买保险')
            self._set_button(self.decision_buttons.get('decline'),True,'不购买')
        elif self.ace_decision_mode=='even_money':
            self._set_button(self.decision_buttons.get('accept'),True,'立刻获胜')
            self._set_button(self.decision_buttons.get('decline'),True,'赌！')

        self._set_round_control_visibility(self.round_active)
        hand=self.active_hand()
        active=bool(self.round_active and self.round_main_bet_side == 'player'
                    and not self.animation_running and not self.settlement_running
                    and not self.ace_decision_mode and hand and hand['status']=='active'
                    and not hand.get('needs_split_draw',False))
        self._set_button(self.action_buttons.get('hit'),active and self.can_hit(hand),'要牌')
        self._set_button(self.action_buttons.get('stand'),active,'停牌')
        self._set_button(self.action_buttons.get('double'),active and self.can_double(hand),'加倍')
        self._set_button(self.action_buttons.get('split'),active and self.can_split(hand),'分牌')
        surrender_enabled=active and self.can_surrender(hand); cashout_text='兑现金额\n$0.00'
        if surrender_enabled:
            credit,win_prob,_bust,_=self.surrender_offer(hand); cashout_text=f'兑现金额\n{self.format_money(credit)}'
        self._set_button(self.action_buttons.get('surrender'),surrender_enabled,cashout_text)
        for _key,spot in self.bet_spots.items():
            self.canvas.itemconfigure(spot['rect'],fill=spot['normal_fill'])
        self._refresh_premiere_bet_labels()

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

        dialog.title('双向黑杰克 · 游戏说明')

        dialog.configure(bg='#faf5e8')

        dialog.resizable(False, False)

        dialog.transient(parent)



        width, height = 1000, 670

        parent.update_idletasks()

        px, py = parent.winfo_rootx(), parent.winfo_rooty()

        pw, ph = max(1, parent.winfo_width()), max(1, parent.winfo_height())

        dialog.geometry(f'{width}x{height}+{px + (pw-width)//2}+{py + (ph-height)//2}')



        manual_pages = [
            (
                '玩法',
                '了解游戏目标，以及一局从下注到结算的完整顺序。',
                [
                    [
                        '游戏目标',
                        '',
                        [
                            ('本局目标', '尽量让手牌接近 21 点而不爆牌，并按本变体规则击败庄家。'),
                        ],
                        [],
                    ],
                    [
                        '一局如何进行',
                        '',
                        [
                            ('玩家下注', '设置主注和可选边注，开始一局。'),
                            ('玩家决策', '根据手牌选择要牌、停牌、加倍、分牌等可用操作。'),
                            ('庄家开牌', '庄家依本游戏的停牌规则补牌并亮出结果。'),
                            ('结算', '比较点数并按本游戏的主注、保险及边注规则结算。'),
                        ],
                        [],
                    ],
                    [
                        '游戏玩法与连续洗牌说明',
                        '8副完整牌 · ENHC · H17',
                        [
                            ('庄家 H17', '不论选择哪一个主注，庄家均为H17：17以下要牌，软17继续要牌，硬17停牌。'),
                            ('边注开放条件', '桌面有六个边注下注格，未选择主注时全部锁定。\n选择任一主注后才开放。'),
                            ('连续发牌', '牌张跨局保留在连续洗牌系统中，不建立或切换独立牌靴。'),
                            ('牌张回收', '每局结束后，已发出的牌进入弃牌区，由连续洗牌机按规则重新混入牌仓。'),
                            ('无需换靴', '不使用剩余牌阈值、切牌或烧牌流程；\n下一局直接由连续洗牌机供牌。'),
                        ],
                        [],
                    ],
                ],
            ),
            (
                '下注 & 限红',
                '各项目限红如下。',
                [
                    [
                        '下注项目',
                        '',
                        [],
                        [
                            (
                                '下注项目与限红',
                                ['项目', '限红'],
                                [
                                    ['玩家主注／庄家主注', '$100–$500,000'],
                                    ['超级对子', '每项最高$100,000'],
                                    ['21+3', '每项最高$100,000'],
                                    ['超级平局', '每项最高$100,000'],
                                    ['疯狂7', '每项最高$100,000'],
                                    ['热辣21', '每项最高$100,000'],
                                    ['爆牌！', '每项最高$100,000'],
                                ],
                            ),
                        ],
                    ],
                ],
            ),
            (
                '获胜条件 & 赔率',
                '按下列表格核对各项判定条件、胜负结果及赔率。',
                [
                    [
                        '比牌规则',
                        '',
                        [],
                        [
                            (
                                '比牌与及格线',
                                ['判断', '规则'],
                                [
                                    ['牌值', 'A 可计 1 或 11；\nJ、Q、K 计 10；\n总点数超过 21 为爆牌。'],
                                    ['比大小', '玩家与庄家均未爆牌时，点数更接近 21 者胜。'],
                                    ['同点数', '视作平局；\n天然黑杰克及变体的特殊情况按主注结算表。'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '游戏玩法与连续洗牌说明',
                        '8副完整牌 · ENHC · H17',
                        [],
                        [
                            (
                                '',
                                ['情形／项目', '赔率／结算规则'],
                                [
                                    ['主注必须二选一', '未下注时中央主注分成上方“庄家手牌”和下方“玩家手牌”。'],
                                    ['', '选择任一方向后，另一方向退出。'],
                                    ['', '清除下注或结算结束后，恢复为上下二选一。'],
                                    ['主注-玩家', '玩家自行操作手牌，可要牌、停牌、加倍、分牌、即时兑现'],
                                    ['', '庄家A明牌时可购买保险，玩家天然黑杰克遇庄家A时可选择立刻获胜或赌庄家结果。'],
                                    ['玩家手牌由系统自动接管', '17以下要牌、软17要牌、硬17停牌；'],
                                    ['主注-庄家', '不开放保险、加倍、分牌、投降。'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '主注结算',
                        '两种主注分别按以下实际条件判定',
                        [],
                        [
                            (
                                '主注-玩家',
                                ['条件', '赔率'],
                                [
                                    ['玩家未分牌的两张牌天然黑杰克', '3:2'],
                                    ['玩家爆牌', '输'],
                                    ['庄家天然黑杰克；\n玩家不是', '输'],
                                    ['双方天然黑杰克', '平局'],
                                    ['庄家爆牌；\n玩家未爆牌', '1:1'],
                                    ['双方未爆：玩家点数较高', '1:1'],
                                    ['双方未爆：点数相同', '平局'],
                                    ['双方未爆：玩家点数较低', '输'],
                                    ['分牌后两张牌组成21点', '1:1'],
                                    ['保险：庄家天然黑杰克', '2:1'],
                                ],
                            ),
                            (
                                '主注-庄家',
                                ['条件', '赔率'],
                                [
                                    ['玩家黑杰克、庄家非黑杰克', '输'],
                                    ['双方黑杰克', '平局'],
                                    ['庄家黑杰克', '3:2'],
                                    ['庄家爆牌、玩家未爆', '输'],
                                    ['双方未爆且同点', '平局'],
                                    ['双方未爆：庄家点数较低', '输'],
                                    ['双方未爆：庄家点数较高', '1:1'],
                                    ['玩家爆牌；\n庄家18–21', '1:1'],
                                    ['玩家爆牌；\n庄家17', '平局'],
                                    ['双方同时爆牌', '平局'],
                                ],
                            ),
                        ],
                    ],
                ],
            ),
            (
                '牌型等级表',
                '牌型由强到弱排列；\n同级牌型继续比较相关点数。',
                [
                    [
                        '点数与牌例',
                        '下方图片展示牌型示例；\n同一牌型也可能由其他牌面组成。',
                        [],
                        [
                            (
                                '判定与牌例',
                                ['等级', '牌型', '牌例'],
                                [
                                    [
                                        '1',
                                        '天然黑杰克',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♠', 'A'),
                                                ('♥', 'K'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '2',
                                        '普通 21 点',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♠', '7'),
                                                ('♥', '7'),
                                                ('♦', '7'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '3',
                                        '20 点',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♠', 'K'),
                                                ('♥', 'Q'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '4',
                                        '爆牌',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♠', 'K'),
                                                ('♥', 'Q'),
                                                ('♦', '2'),
                                            ),
                                        ),
                                    ],
                                ],
                            ),
                        ],
                    ],
                    [
                        '同牌型如何分胜负',
                        '',
                        [
                            ('比较方法', 'A 可计 1 或 11，J、Q、K 计 10；\n玩家与庄家注项分别按主注表结算。'),
                        ],
                        [],
                    ],
                ],
            ),
            (
                '特别事项',
                '补充说明特殊牌、模式差异和金额结算方式。',
                [
                    [
                        '游戏玩法与连续洗牌说明',
                        '8副完整牌 · ENHC · H17',
                        [
                            ('连续洗牌机', '使用8副完整52张牌，共416张；\n所有牌局均由CSM_Shuffler连续洗牌机发牌。'),
                        ],
                        [],
                    ],
                    [
                        '特殊下注规则',
                        '',
                        [
                            ('限红', '没有选择主注时，边注保持锁定。'),
                        ],
                        [],
                    ],
                ],
            ),
        ]



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

        tk.Label(header, text='双向黑杰克 · 游戏说明', font=(font_name, 20, 'bold'),

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

    def _raise_wager_chips(self):
        """Keep every displayed wager above cards, labels, and table controls."""
        self.canvas.tag_raise('wager_chip')

    @staticmethod
    def _shade_color(color, factor):
        rgb = [max(0, min(255, round(int(color[i:i+2], 16)*factor))) for i in (1, 3, 5)]
        return '#' + ''.join(f'{value:02x}' for value in rgb)

    def _render_settlement_chips(self):
        self.update_bet_chips()
        self.canvas.delete('hand_wager')
        self._draw_main_hand_wagers()
        self._render_insurance_chip()
        self._raise_wager_chips()

    def _animate_main_choice(self, side, selecting, on_complete=None):
        """Move the selected open-ring MAIN area in 0.20 seconds."""
        key = self._main_spot_key(side)
        spot = self.bet_spots[key]
        start = tuple(spot['bounds'])
        target = (self.main_selected_home if selecting else self.bet_layout_home)[key]
        self._main_selection_animation_running = True
        other_key = self._main_spot_key('player' if side == 'dealer' else 'dealer')
        self._set_main_bet_surface_visible(self.bet_spots[other_key], False)

        def frame(step=1):
            t = min(1.0, step / 10.0)
            e = t*t*(3.0-2.0*t)
            bounds = tuple(a+(b-a)*e for a, b in zip(start, target[0]))
            x, y = (bounds[0]+bounds[2])/2, (bounds[1]+bounds[3])/2
            spot.update(bounds=bounds, label_pos=(x, y+(bounds[3]-bounds[1])/2+10),
                        chip_pos=(x, y))
            self._position_main_bet_surface(spot, bounds)
            self._raise_wager_chips()
            if step < 10:
                self._queue(20, frame, step+1)
                return
            self._main_selection_animation_running = False
            if not selecting:
                self.main_bet_side = None
            self._refresh_premiere_bet_labels()
            self.update_display()
            if callable(on_complete):
                on_complete()
        self._queue(20, frame, 1)

    def _seat_hand_geometry(self, snapshot=None):
        hands = self.hands if snapshot is None else snapshot
        count = max(1, len(hands))
        lane_width = (1128-22-24)/count
        return {index: (34+index*lane_width, 34+(index+1)*lane_width,
                        34+(index+0.5)*lane_width, index, count)
                for index in range(len(hands))}

    def _player_card_position(self, hand, geometry, card_index):
        left, right, cx, _order, _n = geometry
        # The first card clears the enlarged MAIN chip.
        # Reserve fan space once; later cards never move cards already dealt.
        main_chip_x, origin_y = self.MAIN_BET_CENTER
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

    def _animate_starting_wagers(self, on_complete):
        starts,ends = {},{}
        self._opening_wager_animation = True
        layout = self._main_split_wager_layout()
        for index,hand in enumerate(self.hands):
            tag = f'opening_wager_{index}'
            start = self.bet_spots[self._main_spot_key(self.round_main_bet_side)]['chip_pos']
            self._draw_baccarat_chip(*start,hand['base_bet'],
                tags=('opening_wager',tag),radius=self.WAGER_CHIP_RADIUS)
            # Move toward the selected side's first card. The chip's top
            # overlaps that card's bottom by 10px.
            starts[tag],ends[tag] = start,layout[index]['base']
        def landed():
            self.canvas.delete('opening_wager')
            self._opening_wager_animation = False
            self.render_cards()
            self.update_display()
            on_complete()
        self._animate_canvas_positions(starts,ends,duration_ms=220,on_complete=landed)

    def _dealer_badge_fill(self):
        if not self.dealer_cards:
            return '#ffffff'
        total,_soft = BlackjackEngine.hand_value(self.dealer_cards)
        if total>21:
            return '#e34848'
        if self.settlement_running and self.round_main_bet_side == 'dealer':
            state = self.hands[0].get('settlement') if self.hands else None
            return {'win': '#b9efb4', 'lose': '#e34848',
                    'push': '#b9dcff', 'refund': '#b9dcff'}.get(state, '#ffffff')
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

    def _animate_side_bet_profit(self, key):
        rows = self._outcome_chip_rows(('side', key), self.round_side_bets.get(key, 0.0),
            self.side_bet_return_amounts.get(key, 0.0), self.bet_spots[key]['chip_pos'], self.WAGER_CHIP_RADIUS, ())
        for row in rows:
            if row['role'] == 'profit':
                self.pending_profit_chips.add(row['key'])
                def arrived(k=row['key']):
                    self.pending_profit_chips.discard(k)
                    self.update_bet_chips()
                self._animate_settlement_chips([(575, 43, row['amount'], self.WAGER_CHIP_RADIUS)], row['pos'],
                    440, f'side_profit_fly_{self.SIDE_BET_KEYS.index(key)}', arrived)

    def _settlement_chip_rows(self):
        rows = self._main_wager_rows()
        for key, stake in self.round_side_bets.items():
            if stake > 0:
                spot = self.bet_spots[key]
                rows.extend(self._outcome_chip_rows(('side', key), stake,
                    self.side_bet_return_amounts.get(key, 0.0), spot['chip_pos'], self.WAGER_CHIP_RADIUS,
                    ('bet_chip_dynamic', spot['tag'])))
        if self.insurance_bet > 0:
            rows.extend(self._outcome_chip_rows(('insurance',), self.insurance_bet,
                self.insurance_return_amount, self.rule_strip_chip_pos, self.INSURANCE_CHIP_RADIUS, ('insurance_chip',)))
        return rows

    def _make_banker_push_notice(self):
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
                wording = self._banker_notice_wording
                box = draw.textbbox((0, 0), wording, font=font)
                draw.text(((width * scale - (box[2] - box[0])) / 2 - box[0],
                           (height * scale - (box[3] - box[1])) / 2 - box[1]),
                          wording, font=font, fill=self.PUSH_BLUE)
            self._banker_notice_source = layer.resize(
                (width, height), getattr(Image, 'Resampling', Image).LANCZOS)
            self._banker_notice_image_item = self.canvas.create_image(
                x, y, state='hidden', tags='banker_push_notice')
        else:
            font = None
        if font is None:
            # Match Cari's native Tk font fallback when Pillow has no CJK font.
            self._banker_notice_text_item = self.canvas.create_text(
                x, y, text=self._banker_notice_wording, font=(self.cn_font, 16, 'bold'),
                fill=self.PUSH_BLUE, state='hidden', tags='banker_push_notice')

    def _draw_banker_push_notice(self):
        alpha = self._banker_notice_level
        if alpha <= 0.0:
            self.canvas.itemconfigure('banker_push_notice', state='hidden')
            return
        if self._banker_notice_source is not None:
            layer = self._banker_notice_source.copy()
            layer.putalpha(self._banker_notice_source.getchannel('A').point(
                lambda value: round(value * alpha)))
            self._banker_notice_photo = ImageTk.PhotoImage(layer, master=self)
            self.canvas.itemconfigure(self._banker_notice_image_item,
                                      image=self._banker_notice_photo, state='normal')
        if self._banker_notice_text_item is not None:
            background, foreground = (75, 30, 34), (185, 220, 255)
            color = '#' + ''.join(f'{round(a + (b - a) * alpha):02x}'
                                  for a, b in zip(background, foreground))
            self.canvas.itemconfigure(self._banker_notice_text_item, fill=color, state='normal')
        self.canvas.tag_raise('banker_push_notice')

    def _fade_banker_push_notice(self, visible):
        """Use Free Double's 300ms dealer-area fade for the two BANKER push rules."""
        if self._closing:
            return
        wording = ('17点平局' if self.banker_17_main_push else
                   '双爆平局' if self.banker_double_bust_main_push else '')
        visible = bool(visible and wording)
        target = 1.0 if visible else 0.0
        changed = visible and wording != self._banker_notice_wording
        if (not changed and self._banker_notice_target == visible
                and (self._banker_notice_job is not None or self._banker_notice_level == target)):
            return
        if self._banker_notice_job is not None:
            try:
                self.after_cancel(self._banker_notice_job)
            except tk.TclError:
                pass
            if self._banker_notice_job in self.after_ids:
                self.after_ids.remove(self._banker_notice_job)
            self._banker_notice_job = None
        if changed:
            self.canvas.delete('banker_push_notice')
            self._banker_notice_wording = wording
            self._banker_notice_source = self._banker_notice_photo = None
            self._banker_notice_image_item = self._banker_notice_text_item = None
        self._banker_notice_target = visible
        if self._banker_notice_image_item is None and self._banker_notice_text_item is None:
            if not visible:
                return
            self._make_banker_push_notice()
        start = self._banker_notice_level
        def step(frame):
            self._banker_notice_job = None
            self._banker_notice_level = start + (target-start)*frame/12
            self._draw_banker_push_notice()
            if frame < 12:
                self._banker_notice_job = self._queue(25, step, frame+1)
        step(0)

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
        try:
            self.engine.close()
        except (CSMError, OSError):
            pass

        # Refund only unresolved escrow on a forced exit. Already-settled cashouts
        # and Even Money are not refunded again.
        if not self.round_active:
            self.balance += self.current_bet + sum(self.current_side_bets.values())
            self.current_bet = 0.0
            self.current_side_bets = {key: 0.0 for key in self.SIDE_BET_KEYS}
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
    root.title('双向黑杰克')
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
